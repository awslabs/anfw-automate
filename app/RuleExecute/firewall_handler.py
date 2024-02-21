"""Firewall Handler Class."""

# This file is part of anfw-automate. See LICENSE file for license information.

from asyncio.log import logger
import datetime
import hashlib
import json
import os
import random
import re
from random import randint
from time import sleep
from yaml import safe_load

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from aws_lambda_powertools import Logger
from lib.rule_config import ConfigEntry, DefaultDenyRules
from lib.log_handler import Level

MAX_RULES_PRE_POLICY: int = 19  # max 20
MAX_POLICIES: int = 19  # max 20 AWS soft-limit
RULE_PRIORITY: int = 1
POLICY_NAME_PREFIX: str = "Policy-"  # e.g. Policy- will be Policy-1, Policy-2 etc.
RULE_GROUP_CAPACITY: int = 2000  # Max 30.000
# ['eu-west-1', 'eu-central-1'] etc.
RESERVED_RULEGROUP_CAPACITY: int = 100  # Max 30.000


class FirewallRuleHandler:
    """Provide the Firewall Update functionality."""

    def __init__(
        self,
        region: str,
        context: dict,
        customer_log_handler: object,
        log_stream_name: str,
    ) -> None:
        # Generate the list
        config = Config(retries={"max_attempts": 10, "mode": "adaptive"})
        self._nfw = boto3.client("network-firewall", region_name=region, config=config)
        self._lambda = boto3.client("lambda", region_name=region, config=config)
        self.context = context
        self.rule_group_collection: set = self._get_all_groups()
        self.policy_collection: set = self._get_all_policies()
        self.logger = Logger(child=True)
        self.customer_log_handler = customer_log_handler
        self.log_stream_name = log_stream_name
        self.supported_regions = os.getenv("SUPPORTED_REGIONS").split(",")
        with open("data/defaultdeny.yaml", mode="r", encoding="utf-8") as d:
            default_deny_config = DefaultDenyRules(**safe_load(d))
            self.default_deny_rules = default_deny_config.Rules

    # Initial get functions -#############################################

    def _get_all_groups(self) -> set:
        """Get all Firewall rule groups.

        :return: set - ARNs of the existing rule groups."""
        names: set = set()
        # TODO: Potential NetworkFirewall.Client.exceptions.ThrottlingException / 100 is max
        # Why 100 ? There are only 50 possible ?
        groups = self._nfw.list_rule_groups(Scope="ACCOUNT", MaxResults=100)
        # First chunk of rules
        for group_name in groups["RuleGroups"]:
            names.add(group_name["Arn"])
        # if there are more, get another 100 until end
        while "NextToken" in groups:
            groups = self._nfw.list_rule_groups(
                Scope="ACCOUNT", MaxResults=100, NextToken=groups["NextToken"]
            )
            for group_name in groups["RuleGroups"]:
                names.add(group_name["Arn"])

        return names

    def _get_rule_entries(self) -> list:
        """Get all rule entries in all rule groups.

        :return: [{"RuleGroupARN": rule_group_arn, "RuleString": entry}..], Updatetoken
        :rtype: list of dicts
        """
        rule_entries: list = []
        if not self.rule_group_collection:
            # Return empty values because nothing exists
            return [], ""
        # rule_entires is a list of all rules with the rule group as key
        #  key = rule group arn // value = rule
        for rule_group_arn in self.rule_group_collection:
            response = self._nfw.describe_rule_group(
                RuleGroupArn=rule_group_arn, Type="STATEFUL"
            )
            if "RuleGroup" not in response.keys():
                return rule_entries, response["UpdateToken"]
            if "RulesString" in response["RuleGroup"]["RulesSource"].keys():
                # Rules are one string - has do spilt by new line
                rules_ = response["RuleGroup"]["RulesSource"]["RulesString"].split("\n")
                # Pack the rule group ARN and the rule in one dict entry in the list
                for entry in rules_:
                    rule_entries.append(
                        {"RuleGroupARN": rule_group_arn, "RuleString": entry}
                    )
        return rule_entries, response["UpdateToken"]

    def _get_all_policies(self) -> set:
        """Get all Firewall polices.

        :return: set - all existing policy ARNs"""
        names: set = set()
        # First junk of rules
        policies = self._nfw.list_firewall_policies(MaxResults=100)
        for policy in policies["FirewallPolicies"]:
            names.add(policy["Arn"])
        # if there are more, get another 100 until end
        while "NextToken" in policies:
            policies = self._nfw.list_firewall_policies(
                MaxResults=100, NextToken=policies["NextToken"]
            )
            for policy in policies["FirewallPolicies"]:
                names.add(policy["Arn"])

        return names

    # End get functions ##############################################

    def add_new_rule(
        self, vpc_id: str, account: str, rules: dict, vpc_cidr: str
    ) -> None:
        """Take a ConfigEntry object and does the magic.

        :return: None"""
        try:
            ip_set_name = f"a{account}{vpc_id}"

            for rule_name, rule_string in rules.items():
                # Check if the rule exists and update it
                arn = self.__add_rule_entry(rule_string, vpc_cidr, ip_set_name)
                if arn is None:
                    # No arn can be found - create new rule group
                    random_name: str = self._generate_random_name()
                    self.logger.info(
                        f"Create new rule group {random_name} and add the first rule string."
                    )
                    self._create_new_rule_group(
                        rule_group_name=random_name,
                        rule_string=rule_string,
                        ip_set_name=ip_set_name,
                        ip_set_space=vpc_cidr,
                    )
                # Clean Up and update the collection
                self._clean_up_rules(rules=rules, account=account, vpc_id=vpc_id)
        except ClientError as error:
            if error.response["Error"]["Code"] == "LimitExceededException":
                self.logger.error(
                    "API call limit exceeded; backing off and retrying..."
                )
            else:
                raise error

    def json_to_rule(self, json_message: str, event_type: str) -> None:
        """Takes the json content from the message and updates the rules.

        :returns: None
        """
        data = json.loads(json_message)
        # extract the values from json - must be consistent with the producer
        account: str = data["Account"]
        vpc_id: str = data["VPC"]
        region: str = data["Region"]
        vpc_cidr: str = data["CIDR"]
        rules: dict = data["Rules"]
        # Handle all event type with the corresponding function
        # Update event
        if (
            event_type == "Update"
            and account
            and vpc_cidr
            and vpc_id
            and region
            and vpc_cidr
            and rules
        ):
            self.customer_log_handler.send_log_message(
                self.log_stream_name,
                f"Updating rules for account {account} and vpc-{vpc_id}",
                level=Level.INFO,
            )
            self.logger.info(f"Updating rules for account {account} and vpc-{vpc_id}")

            # Add the rule
            self.add_new_rule(
                vpc_cidr=vpc_cidr, vpc_id=vpc_id, rules=rules, account=account
            )

        # VPC Delete Event
        if event_type == "DeleteVpc" and vpc_id:
            self.logger.info(
                f"DeleteVpc - All rules for the vpc-{vpc_id} will be deleted."
            )
            self.customer_log_handler.send_log_message(
                self.log_stream_name,
                f"DeleteVpc - All rules for the vpc-{vpc_id} will be deleted.",
                level=Level.INFO,
            )
            self._clean_up_rules(rules={}, account=account, vpc_id=vpc_id)
            self._cleanup_ip_sets(account=account, vpcid=vpc_id)

        # S3 bucket/file delete event
        if event_type == "DeleteS3" and account and region:
            self.logger.info(
                f"DeleteS3 - All rules for the Account {account} in {region} will be deleted."
            )
            self.customer_log_handler.send_log_message(
                self.log_stream_name,
                f"DeleteS3 - All rules for the Account {account} in {region} will be deleted.",
                level=Level.INFO,
            )
            self._clean_up_rules(rules={}, account=account)
            self._cleanup_ip_sets(account=account)

        # Account Delete Event
        if event_type == "DeleteAccount" and account:
            # Do the delete for all regions
            for current_region in self.supported_regions:
                self._nfw = boto3.client("network-firewall", region_name=current_region)
                self.logger.info(
                    f"DeleteAccount - All rules for the Account {account} in {current_region} will be deleted"
                )
                self.customer_log_handler.send_log_message(
                    self.log_stream_name,
                    f"DeleteAccount - All rules for the Account {account} in {current_region} will be deleted",
                    level=Level.INFO,
                )
                try:
                    self._clean_up_rules(rules={}, account=account)
                    self._cleanup_ip_sets(account=account)
                except ClientError as error:
                    if error.response["Error"]["Code"] == "ResourceNotFoundException":
                        self.logger.warning(
                            f"DeleteAccount - No resources in {account} @ {current_region} - skipping."
                        )
                    else:
                        raise error
        self.customer_log_handler.send_log_message(
            self.log_stream_name,
            f"Rule change processed for {vpc_id} in region {region}",
            level=Level.INFO,
        )

    def __add_rule_entry(
        self, rule_string: str, ip_set_space: str, ip_set_name: str
    ) -> str:
        """Check if a rule exists and update the corresponding rule group.

        :return: Returns the current ARN of the rule group
        if the rule exists; if not - return none

        """
        # Generate the hash first
        rule_arn: str = ""
        flag_rule_string: bool = False
        new_rule_name: str = self._get_rule_name_from_rule_string(rule_string)
        rule_collection, update_token = self._get_rule_entries()
        for entry in rule_collection:
            # get the unique name of the rule string
            entry_name = self._get_rule_name_from_rule_string(entry["RuleString"])

            if entry_name == new_rule_name:
                # rule exists - no update
                rule_arn = entry["RuleGroupARN"]
                flag_rule_string = True
                self.logger.debug(f"Rule exists no update for {entry_name}")

        if not flag_rule_string:
            # If rule not exists - add it to the smallest group
            smallest_group_arn = self._get_rule_group()
            # Special case - no rule group is left.
            if not smallest_group_arn:
                self.logger.debug("No smallest group left - force to create a new one.")
                return None
            rule_arn = smallest_group_arn

        new_rules: list = []
        # Now collect all rules for this group
        for entry in rule_collection:
            # get only the rules for the selected group arn
            if entry["RuleGroupARN"] == rule_arn:
                new_rules.append(entry["RuleString"])

        if not flag_rule_string:
            # Add the new one
            new_rules.append(rule_string)
            # Update the list in-flight too
            self.logger.debug(f"New rule added to rule group {rule_arn}")

        # Separated by \n
        new_rule_string = "\n".join(new_rules)

        # check for potential ip set changes
        rule_config = self._nfw.describe_rule_group(
            RuleGroupArn=rule_arn, Type="STATEFUL"
        )
        # fix for empty rule group
        if "RuleGroup" not in rule_config.keys():
            # Create the rule group
            rule_config.update(
                {
                    "RuleGroup": {
                        "RuleVariables": {
                            "IPSets": {ip_set_name: {"Definition": [ip_set_space]}}
                        }
                    }
                }
            )
        # if no ipset but rules
        if "RuleVariables" not in rule_config["RuleGroup"].keys():
            # IPset was not there - rule without one?
            rule_config["RuleGroup"].update(
                {
                    "RuleVariables": {
                        "IPSets": {ip_set_name: {"Definition": [ip_set_space]}}
                    }
                }
            )
        else:
            # IPSet is there - cerate or do nothing
            ip_sets: dict = rule_config["RuleGroup"]["RuleVariables"]["IPSets"]
            found_flag: bool = False
            for set_name, definition in ip_sets.items():
                if set_name == ip_set_name:
                    # Exists in this rule
                    ip_sets.update({set_name: {"Definition": [ip_set_space]}})
                    found_flag = True
            if not found_flag:
                # IP set name is not there - create it
                ip_sets.update({ip_set_name: {"Definition": [ip_set_space]}})
            # update the rule group with the new ip set

            rule_config["RuleGroup"]["RuleVariables"]["IPSets"] = ip_sets

        # Add the rule string
        rule_config["RuleGroup"]["RulesSource"]["RulesString"] = new_rule_string
        self.logger.debug(rule_config["RuleGroup"])
        try:
            # update the rule with the changed rule_string and ip set
            self._nfw.update_rule_group(
                UpdateToken=rule_config["UpdateToken"],
                RuleGroupArn=rule_arn,
                RuleGroup=rule_config["RuleGroup"],
                Type="STATEFUL",
            )
        except self._nfw.exceptions.InvalidTokenException:
            self.logger.error(
                f"InvalideTokenException - try after 2 seconds again. {update_token}"
            )
            sleep(2)
            self.__add_rule_entry(rule_string, ip_set_space, ip_set_name)

        return rule_arn

    def _create_reserved_rules(self) -> list:
        # Get FW Account and VPC ID
        current_lambda_config = self._lambda.get_function_configuration(
            FunctionName=self.context.function_name
        )
        fw_vpc_id = os.environ["VPC_ID"].replace("vpc-", "")
        fw_account_id = self.context.invoked_function_arn.split(":")[4]

        generated_reserved_rules: list = []
        for rulestring in self.default_deny_rules:
            proto = rulestring.split()[1]
            rule_options = re.search(rf"\((.*)\)$", rulestring)

            # Do join in hash-input to introduce bit shift and have positive values
            # fmt: off
            rule_name_hash = hashlib.md5(rulestring.encode()).hexdigest()[:10] # nosec: Not used for security
            rule_name: str = f"{fw_account_id}-{fw_vpc_id}-{rule_name_hash}"

            sid: str = str(random.randrange(10, 1000000, 3)) # nosec: Not used for security
            # fmt: on
            if rule_options != None:
                rule_options = (
                    f"{rule_options.group(0)} "
                    f'msg: "Drop all {proto.upper()}"; '  # value must be double quoted
                    f"priority:255; flow:to_server, established; sid:{sid}; rev:1; "
                    f"metadata: rule_name {rule_name};"
                )
                re.sub(r"\((.*)\)$", rule_options, rulestring)
            else:
                rule_options = (
                    f'(msg: "Drop all {proto.upper()}"; '  # value must be double quoted
                    f"priority:255; flow:to_server, established; sid:{sid}; rev:1; "
                    f"metadata: rule_name {rule_name};)"
                )
                rulestring += rule_options

            generated_reserved_rules.append(rulestring)

        return generated_reserved_rules

    def _create_new_rule_group(
        self,
        rule_group_name: str,
        rule_string: str,
        ip_set_space: list,
        ip_set_name: str,
    ) -> None:
        """Creates a new entry from a rule string and ip set.

        :return: None"""

        ipset = {
            "RuleVariables": {
                "IPSets": {
                    ip_set_name: {"Definition": [ip_set_space]},
                }
            }
        }
        self.logger.debug(f"Rule string passed: {rule_string}")
        rule_source = {"RulesSource": {"RulesString": rule_string}}
        ipset.update(rule_source)
        new_rule = self._nfw.create_rule_group(
            RuleGroupName=rule_group_name,
            Type="STATEFUL",
            Description="Autogenerated - DONT CHANGE",
            Capacity=RULE_GROUP_CAPACITY,
            RuleGroup=ipset,
        )

        # After creation - associate with one policy
        arn: str = new_rule["RuleGroupResponse"]["RuleGroupArn"]
        self._associate_rule_group_to_policy(arn)
        self.rule_group_collection.add(arn)

    def create_reserved_rule_group(
        self,
        # rule_group_name: str,
        # rule_string: str,
        # ip_set_space: list,
        # ip_set_name: str,
    ) -> None:
        """Creates a reserved rule group from defaultdeny config file.

        :return: None"""
        # internal_net_list = os.getenv("INTERNAL_NET").split(",")
        # fw_vpc_cidr = os.getenv("HOME_NET").split(",")
        # ipset = {
        #     "RuleVariables": {
        #         "IPSets": {
        #             "INTERNAL_NET": {"Definition": internal_net_list},
        #             "HOME_NET": {"Definition": fw_vpc_cidr},
        #         }
        #     }
        # }
        # ipset = {"RuleVariables": {"IPSets": {}}}
        ipset = {}
        rule_string = "\n".join(self._create_reserved_rules())
        self.logger.debug(f"Rule string passed: {rule_string}")
        rule_source = {"RulesSource": {"RulesString": rule_string}}
        ipset.update(rule_source)
        self.logger.debug(f"RuleGroup input: {ipset}")

        for rule_group_arn in self.rule_group_collection:
            rulegroup_name = self._arn_to_name(rule_group_arn)
            if rulegroup_name.endswith("reserved"):
                self.logger.debug(f"Entering Rule update for: {rulegroup_name}")
                # Get update token
                rulegroup_config = self._nfw.describe_rule_group(
                    RuleGroupArn=rule_group_arn, Type="STATEFUL"
                )
                self._nfw.update_rule_group(
                    UpdateToken=rulegroup_config["UpdateToken"],
                    RuleGroupArn=rule_group_arn,
                    RuleGroup=ipset,
                    Type="STATEFUL",
                )
                return

        rulegroup_name = self._generate_random_name() + "-reserved"
        self.logger.debug(f"Entering Rule Create for: {rulegroup_name}")
        new_rule = self._nfw.create_rule_group(
            RuleGroupName=rulegroup_name,
            Type="STATEFUL",
            Description="Autogenerated Reserved Group- DONT CHANGE",
            Capacity=RESERVED_RULEGROUP_CAPACITY,
            RuleGroup=ipset,
        )
        # After creation - associate with one policy
        arn: str = new_rule["RuleGroupResponse"]["RuleGroupArn"]
        self._associate_rule_group_to_policy(arn)
        self.rule_group_collection.add(arn)
        return

    def _get_rule_group(self) -> str:
        """Returns a rule group ARN which has the lowest used capacity.

        :return: str - ARN of the group"""
        lowest_capa: int = RULE_GROUP_CAPACITY
        smallest_group: str = ""
        for rule_group_arn in self.rule_group_collection:
            response = self._nfw.describe_rule_group(RuleGroupArn=rule_group_arn)
            capa = response["RuleGroupResponse"]["ConsumedCapacity"]
            state = response["RuleGroupResponse"]["RuleGroupStatus"]
            if (
                capa < lowest_capa
                and state != "DELETING"
                and not rule_group_arn.endswith("reserved")
            ):
                lowest_capa = capa
                smallest_group = rule_group_arn
        # I no rule has capa left - return none
        return smallest_group

    def _associate_rule_group_to_policy(self, rule_arn: str) -> None:
        """Associate the rule group to the policy.

        :return: None"""
        for cached_policy in self.policy_collection:
            policy = self._nfw.describe_firewall_policy(FirewallPolicyArn=cached_policy)
            if "StatefulRuleGroupReferences" not in policy["FirewallPolicy"].keys():
                policy["FirewallPolicy"].update({"StatefulRuleGroupReferences": []})
            if (
                len(policy["FirewallPolicy"]["StatefulRuleGroupReferences"])
                <= MAX_RULES_PRE_POLICY
            ):
                references: list = policy["FirewallPolicy"][
                    "StatefulRuleGroupReferences"
                ]
                references.append({"ResourceArn": rule_arn})
                policy["FirewallPolicy"]["StatefulRuleGroupReferences"] = references
                self._nfw.update_firewall_policy(
                    UpdateToken=policy["UpdateToken"],
                    FirewallPolicyArn=cached_policy,
                    FirewallPolicy=policy["FirewallPolicy"],
                )
                # Slot found ... go back
                return
        # no slot found .... create one
        new_policy_name = f"{POLICY_NAME_PREFIX}{randint(1000, 1000000)}"  # nosec: Not used for security
        arn = self._create_new_policy(policy_name=new_policy_name, rule_arn=rule_arn)
        self.policy_collection.add(arn)

    def _delete_rule_if_exists(self, rule_group_name: str) -> None:
        """Delete the rule if exists in collection.

        :return: None
        """

        for arn in self.rule_group_collection:
            if self._arn_to_name(arn) == rule_group_name:
                self._disassociate_rule_from_policy(arn)
                try:
                    self._nfw.delete_rule_group(
                        RuleGroupName=rule_group_name, Type="STATEFUL"
                    )
                except self._nfw.exceptions.InvalidOperationException:
                    sleep(10)
                    # Try again
                    self._nfw.delete_rule_group(
                        RuleGroupName=rule_group_name, Type="STATEFUL"
                    )
                # self._check_rule_status(arn)
                self.logger.debug(f"Rule group deleted: {rule_group_name}")

    def _cleanup_ip_sets(self, account: str, vpcid: str = "") -> None:
        """Deletes the ip_sets for account and/or vpcid passed to the function

        :return: None"""
        ip_set_prefix = f"a{account}{vpcid}"
        self.logger.debug(f"ip_set_prefix:{ip_set_prefix}")
        for arn in self.rule_group_collection:
            # check for potential ip set changes
            rule_config = self._nfw.describe_rule_group(
                RuleGroupArn=arn, Type="STATEFUL"
            )
            new_ip_sets: dict = {}

            # if no ipset but rules
            if "RuleVariables" in rule_config["RuleGroup"].keys():
                # IPSet is there - cerate or do nothing
                ip_sets: dict = rule_config["RuleGroup"]["RuleVariables"]["IPSets"]

                for set_name, definition in ip_sets.items():
                    if not set_name.startswith(ip_set_prefix):
                        self.logger.debug(f"set_name: {set_name}")
                        self.logger.debug(f"definition: {definition}")
                        # Exists in this rule
                        new_ip_sets[set_name] = definition
            rule_config["RuleGroup"]["RuleVariables"]["IPSets"] = new_ip_sets
            self.logger.debug(rule_config["RuleGroup"])
            self._nfw.update_rule_group(
                UpdateToken=rule_config["UpdateToken"],
                RuleGroupArn=arn,
                RuleGroup=rule_config["RuleGroup"],
                Type="STATEFUL",
            )

    ## TO DO: Improve the function to use make update calls per RuleGroup rather than per Rule
    def _clean_up_rules(self, rules: dict, account: str, vpc_id: str = "") -> None:
        """Delete not defined rules in a account or vpc.

        :return: None"""

        existing_account_rules: dict = {}
        event_type = "DeleteVPC" if (account and vpc_id) else "DeleteAccount"

        if event_type == "DeleteVPC":
            self.logger.debug(
                f"Detected Event Type: {event_type} for vpc-{vpc_id} in Account:{account}"
            )
        elif event_type == "DeleteAccount":
            self.logger.debug(
                f"Detected Event Type: {event_type} for Account:{account}"
            )

        rule_collection, update_token = self._get_rule_entries()
        # raise ValueError("Function cannot take vpc and account as parameter.")

        for entry in rule_collection:
            rule_name = self._get_rule_name_from_rule_string(entry["RuleString"])
            if event_type == "DeleteVPC":
                ip_set_prefix = f"a{account}{vpc_id}"
                # get the vpc
                rule_vpc_id = rule_name.split("-", maxsplit=2)[1]
                if rule_vpc_id == vpc_id:
                    existing_account_rules.update(
                        {
                            rule_name: {
                                "GroupARN": entry["RuleGroupARN"],
                                "RuleString": entry["RuleString"],
                            }
                        }
                    )
            elif event_type == "DeleteAccount":
                self.logger.debug(f"Delete Rules for Account: {account}")
                ip_set_prefix = f"a{account}"
                # get the account
                rule_account = rule_name.split("-", maxsplit=2)[0]
                # Search for the rules to a specific AWS account
                if rule_account == account:
                    existing_account_rules.update(
                        {
                            rule_name: {
                                "GroupARN": entry["RuleGroupARN"],
                                "RuleString": entry["RuleString"],
                            }
                        }
                    )
            else:
                raise ValueError(f"Invalid event type detected: {event_type}")

        delete_rules: list = []
        for rule_name, meta in existing_account_rules.items():
            if rule_name not in rules.keys():
                delete_rules.append(meta)

        for rule_entry in delete_rules:
            new_rules: list = []
            # Now collect all rules for this group
            rule_entry_name = self._get_rule_name_from_rule_string(
                rule_entry["RuleString"]
            )
            # get again the rules - prevent race condition
            rule_collection, update_token = self._get_rule_entries()
            for entry in rule_collection:
                # get only the rules for the selected group arn
                if entry["RuleGroupARN"] == rule_entry["GroupARN"]:
                    new_rule_name = self._get_rule_name_from_rule_string(
                        entry["RuleString"]
                    )
                    if new_rule_name != rule_entry_name:
                        new_rules.append(entry["RuleString"])
                    else:
                        self.logger.debug(f"Delete rule {rule_entry_name}")
            # Now update the rule group with the rules without the deleted ones.
            new_rule_string = "\n".join(new_rules)
            self.logger.debug(f"new_rule_string: {new_rule_string}")

            # check for potential ip set changes
            rule_config = self._nfw.describe_rule_group(
                RuleGroupArn=rule_entry["GroupARN"], Type="STATEFUL"
            )

            # Add the rule string and rule variables
            self.logger.debug(rule_config["RuleGroup"])
            if not (new_rule_string):  # and new_ip_sets):
                # No rules - delete the rule group
                arn: str = rule_entry["GroupARN"]
                self.logger.debug(f"No more rules in {arn}")
                self._delete_rule_if_exists(
                    rule_config["RuleGroupResponse"]["RuleGroupName"]
                )

            else:
                rule_config["RuleGroup"]["RulesSource"]["RulesString"] = new_rule_string
                # rule_config["RuleGroup"]["RuleVariables"]["IPSets"] = new_ip_sets
                self.logger.debug(rule_config["RuleGroup"])
                self._nfw.update_rule_group(
                    UpdateToken=rule_config["UpdateToken"],
                    RuleGroupArn=rule_entry["GroupARN"],
                    RuleGroup=rule_config["RuleGroup"],
                    Type="STATEFUL",
                )

    def _purge_rule(self, config: ConfigEntry) -> None:
        """Purges the rule directly.

        :return: None"""
        for arn in self.rule_group_collection:
            name = self._arn_to_name(arn)
            for rule_name, policy in config.rules.items():
                if rule_name == name:
                    self._delete_rule_if_exists(rule_group_name=rule_name)

    def _check_rule_status(self, rule_arn: str) -> bool:
        """Check if a rule is deleted.

        :return: Bool"""
        while True:
            try:
                # Needed loop for detecting if the deletion is done
                self._nfw.describe_rule_group_metadata(
                    RuleGroupArn=rule_arn, Type="STATEFUL"
                )
                sleep(2)
                self.logger.debug("Wait for delete ....")
            except self._nfw.exceptions.ResourceNotFoundException:
                return True

    def _create_new_policy(self, policy_name: str, rule_arn: str) -> str:
        """Generates the policy structure.

        :return: str - ARN of the new policy"""
        policy_config = {
            "StatelessDefaultActions": ["aws:forward_to_sfe"],
            "StatelessFragmentDefaultActions": ["aws:pass"],
            "StatefulRuleGroupReferences": [{"ResourceArn": rule_arn}],
        }
        self.logger.debug(f"New Policy: {policy_name}")
        new_policy = self._nfw.create_firewall_policy(
            FirewallPolicyName=policy_name, FirewallPolicy=policy_config
        )
        _arn = new_policy["FirewallPolicyResponse"]["FirewallPolicyArn"]
        self.policy_collection.add(_arn)
        return _arn

    def _disassociate_rule_from_policy(self, rule_arn: str) -> None:
        """Disassociate the rule from the policy.

        :return: None"""
        references: list = []
        for cached_policy in self.policy_collection:
            policy = self._nfw.describe_firewall_policy(FirewallPolicyArn=cached_policy)
            if "StatefulRuleGroupReferences" in policy["FirewallPolicy"].keys():
                references = policy["FirewallPolicy"]["StatefulRuleGroupReferences"]
                for reference in references:
                    if reference["ResourceArn"] == rule_arn:
                        references.remove(reference)
                        policy["FirewallPolicy"][
                            "StatefulRuleGroupReferences"
                        ] = references
                        self._nfw.update_firewall_policy(
                            UpdateToken=policy["UpdateToken"],
                            FirewallPolicyArn=cached_policy,
                            FirewallPolicy=policy["FirewallPolicy"],
                        )
                        break
            else:
                # Empty policy
                continue

    # Helper functions ####################################################

    def _arn_to_name(self, arn: str) -> str:
        """Returns the resource name from a arn."""
        return str(arn).split("/", maxsplit=1)[1]

    def _generate_random_name(self) -> str:
        """Generates a random string for names."""
        first_date = datetime.datetime(2006, 1, 1)
        time_since = datetime.datetime.now() - first_date
        return str(int(time_since.total_seconds()))

    def _get_rule_name_from_rule_string(self, suricata_rule: str) -> str:
        """Takes a suricata rule string and returns the rule name (meta info)."""
        regex = r"[0-9]+-[0-9a-zA-Z]+-[0-9a-zA-Z]+"
        # get the name
        # self.logger.debug(f"suricata_rule: {suricata_rule}")
        matches = re.search(regex, suricata_rule)
        # self.logger.debug(f"matches: {matches[0]}")
        return matches[0]
