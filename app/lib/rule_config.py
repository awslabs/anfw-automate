"""Config Rule Entry Class"""

# This file is part of anfw-automate. See LICENSE file for license information.

import hashlib
import os
import random
import json
import re
import boto3
from yaml import safe_load
from dataclasses import dataclass
from aws_lambda_powertools import Logger, Tracer

DEFAULT_PRIORITY: int = 100  # default priority for customer rules
# Reserve all metakeywords: https://suricata.readthedocs.io/en/suricata-6.0.1/rules/meta.html#meta-keywords
RESERVED_META_KEYWORDS = [
    "msg",
    "sid",
    "rev",
    "gid",
    "classtype",
    "reference",
    "priority",
    "metadata",
    "target",
]


@dataclass(frozen=True)
class Protocols:
    PredfinedRuleProtocols: dict
    CustomRuleProtocols: list


@dataclass(frozen=True)
class DefaultDenyRules:
    Rules: list


class ConfigEntry:
    """Functionality for generating the new rules."""

    def __init__(self, vpc: str, account: str, region: str, version: str) -> None:
        """Initialzie the variables required to process the VPC config."""
        self.vpc: str = vpc.replace("vpc-", "")
        self.version = version
        self.account: str = account
        self.domains: dict = {}
        self.rules: dict = {}
        self.region: str = region
        self.generated_rules: set = set()
        self.ip_set_space: str = ""
        self.logger = Logger(child=True)
        self.tracer = Tracer()
        self.rule_order = os.getenv("RULE_ORDER")
        self.priority = (
            f"priority:{DEFAULT_PRIORITY};"
            if self.rule_order == "DEFAULT_ACTION_ORDER"
            else ""
        )

        with open("data/protocols.yaml", "r") as p:
            protocol_config = Protocols(**safe_load(p))
            self.predefined_rule_protocols = protocol_config.PredfinedRuleProtocols
            self.custom_rule_protocols = protocol_config.CustomRuleProtocols
            self.allowed_protocols = (
                list(self.predefined_rule_protocols.keys()) + self.custom_rule_protocols
            )

        with open("data/defaultdeny.yaml", "r") as d:
            default_deny_config = DefaultDenyRules(**safe_load(d))
            self.default_deny_rules = default_deny_config.Rules

    @property
    def set_ip_set_space(self, ip_set_space: str) -> None:
        """Set the ip set space"""
        self.ip_set_space = ip_set_space

    def __str__(self) -> str:
        """Class string representation."""
        return f"Account: {self.account} VPC: {self.vpc} - Rules: {self.rules}"

    def get_json(self) -> str:
        """Returns a json formatted representation of the object parameter."""
        json_object = {
            "VPC": self.vpc,
            "Account": self.account,
            "Region": self.region,
            "CIDR": self.ip_set_space,
            "Rules": self.rules,
        }
        return json.dumps(json_object)

    def add_rule_entry(self, rule_key: str, rule: str) -> None:
        """Attach the suricata formatted rule list."""
        # Define rule_type
        rule_type = (
            "predefined"
            if rule_key in self.predefined_rule_protocols.keys()
            else "custom"
        )
        if rule_type == "predefined":
            # Pass known and unknown errors to collect_lambda
            try:
                self._generate_predefined_rule(rule_key, rule.lower().replace(" ", ""))
            except self.FormatError as e:
                raise e
            except self.NotSupportedProtocol as e:
                raise e
            except Exception as e:
                raise e
        else:
            try:
                self._generate_custom_rule(rule)
            except self.FormatError as e:
                raise e
            except self.NotSupportedProtocol as e:
                raise e
            except Exception as e:
                raise e

    def _generate_rule_hash(self, hash_input: str) -> str:
        """Generates the MD5 hash from the domain and protocol.

        :param domain: Domain for hash input
        :type domain: str
        :param protocol: Protocol string as hash input
        :type protocol: str
        :return: Returns the MD5 from domain and protocol parameter concatenation.
        :rtype: str
        """
        # fmt: off
        return hashlib.md5(hash_input.encode()).hexdigest()[:10] # nosec: Not used for security
        # fmt: on

    def _validate_custom_rule_format(self, rulestring: str, ruleoptions: str) -> bool:
        """
        Ensures that rule is complaint with the following:
        1. Generic suricata format
        2. Complaint IP Set Variable name
        3. Use of reserved keywords
        4. Does not contain only TLD in the rule
        5. Rule options exists and contain content field

        :param rulestring: Suricata formatted rule string, without meta-keywords
        :type rulestring: str
        :raises self.FormatError: If the rulestring does not meet the validation criteria
        """
        # TO DO: Precise port range validation
        # ^(pass)\s(http)\s\$a(\w*)\s(any|!?([1-9][0-9]{0,3}|[1-5][0-9]{4}|6[0-4][0-9]{3}|65[0-4][0-9]{2}|655[0-2][0-9]|6553[0-5]))\s(->|<>)\s\$EXTERNAL_NET\s(any|!?([1-9][0-9]{0,3}|[1-5][0-9]{4}|6[0-4][0-9]{3}|65[0-4][0-9]{2}|655[0-2][0-9]|6553[0-5]))\s(\(.*\)$)

        rule_options_stripped = ruleoptions.replace(" ", "")
        protocol_key = rule_options_stripped.split(";", 1)[0].strip("()")
        self.logger.debug(f"protocol_key:{protocol_key}")

        if not re.search(
            rf"^(pass)\s{'|'.join(self.allowed_protocols)}\s\$a(\w*)\s(any|\d{1,5})\s(->|<>)\s\$EXTERNAL_NET\s(any|(\d{1,5}))\s(\(.*\)$)",
            rulestring,
            re.IGNORECASE,
        ):
            raise self.FormatError(f"Invalid Base Format for rule: {rulestring} ")

        #### validate if content field exists
        match = re.search(rf"content:(.*?);", rule_options_stripped)
        if not match:
            raise self.FormatError(f"Content keyword missing in : {ruleoptions} ")

        # Validate Domain if protocol keys are http/s
        if protocol_key in ["tls.sni", "http.host"]:
            domain = match.group(1).strip("'\"")
            self.logger.debug(f"domain:{domain}")

            if domain is None:
                raise self.FormatError(f"Domain is None in : {ruleoptions} ")

            if not self._is_valid_domain(domain):
                raise self.FormatError(f"Domain contains only TLD: {ruleoptions} ")

        # verify ip_set variable name
        if not (rulestring.split()[2] == "$a" + self.account + self.vpc):
            raise self.FormatError(
                f"Invalid IPSet Variable Name in rule: {rulestring} "
            )

        # validate that rule options don't have reserved keywords
        for keyword in RESERVED_META_KEYWORDS:
            if keyword + ":" in rule_options_stripped:
                raise self.FormatError(
                    f"Reserved keywords found in rule: {rulestring} "
                )

        return True

    def _validate_predefine_rule_format(self, domainstring: str) -> bool:
        """
        Ensures that rule is complaint with the following:
        1. Domain does not contain only TLD (Top Level Domain)

        :param domainstring: Suricata formatted rule string, without meta-keywords
        :type domainstring: str
        :raises self.FormatError: If the domainstring does not meet the validation criteria
        """

        if not self._is_valid_domain(domainstring):
            raise self.FormatError(f"Domain contains only TLD: {domainstring} ")

        return True

    def _generate_predefined_rule(self, protocol: str, domain: str) -> None:
        """Generates the predefined rule for the
        :param protocol: Protocol string that contains the rule_key
        :type protocol: str
        :param domain: Domain to add in the rule
        :type domain: str
        """
        # Get the suricata protocol keyword for given rule_key
        s_rule = self._protocol_selector(protocol)

        # Get the protocol from protocol keyword (tls, http)
        s_proto = s_rule.split(".", maxsplit=1)[0]

        # Do join in hash-input to introduce bit shift and have positive values
        # fmt: off
        hash_input = domain.join(protocol)
        rule_name_hash = hashlib.md5(hash_input.encode()).hexdigest()[:10] # nosec: Not used for security
        rule_name: str = f"{self.account}-{self.vpc}-{rule_name_hash}"

        # Keep the rule name for later cleanup
        self.generated_rules.add(rule_name)
        sid: str = str(random.randrange(10, 1000000, 3))  # nosec: Not used for security
        # fmt: on

        # check if custom port is added
        if re.match(rf"^.+:\d+$", domain):
            d_port = domain.split(":")[-1]
            domain = domain.split(":")[0]
        else:
            d_port = "any"

        if self._validate_predefine_rule_format(domain):
            if re.match(r"^\.", domain):
                policy = (
                    f"pass {s_proto} $a{self.account}{self.vpc} any -> $EXTERNAL_NET {d_port} "
                    f'({s_rule}; dotprefix; content:"{domain}"; endswith; '  # must be double quoted
                    f"{self.priority}flow:to_server, established; sid:{sid}; rev:1; "
                    f"metadata: rule_name {rule_name};)"
                )
            else:
                policy = (
                    f"pass {s_proto} $a{self.account}{self.vpc} any -> $EXTERNAL_NET {d_port} "
                    f'({s_rule}; content:"{domain}"; startswith; endswith; '  # must be double quoted
                    f"{self.priority}flow:to_server, established; sid:{sid}; rev:1; "
                    f"metadata: rule_name {rule_name};)"
                )

            self.rules.update({rule_name: policy})
        else:
            raise self.FormatError(f"Invalid domain entry format in rule: {domain}")

    def _generate_custom_rule(self, rule: str) -> None:
        """Generates the unified and enriched rule for the
        :param rule: Suricata formatted rule string
        :type rule: str
        :raises self.FormatError: If the rule string fails validation
        """

        # get everything that is between first and last parenthesis, it is rule options
        rule_options = re.search(rf"\((.*)\)$", rule)
        if rule_options is not None:
            if self._validate_custom_rule_format(rule, rule_options.group(0)):
                # Create suricata rule
                # Do join in hash-input to introduce bit shift and have positive values
                # fmt: off
                rule_name_hash = hashlib.md5(rule.encode()).hexdigest()[:10] # nosec: Not used for security
                rule_name: str = f"{self.account}-{self.vpc}-{rule_name_hash}"

                # Keep the rule name for later cleanup
                self.generated_rules.add(rule_name)

                sid: str = str(random.randrange(10, 1000000, 3)) # nosec: Not used for security
                # fmt: on
                new_rule_options = (
                    f"({rule_options.group(1)}"  # only get content inside the brackets
                    f"{self.priority}sid:{sid};rev:1;"
                    f"metadata: rule_name {rule_name};)"
                )
                rule = re.sub(rf"\((.*)\)$", new_rule_options, rule)
                self.logger.debug(f"rule: {rule}")
                self.rules.update({rule_name: rule})
            else:
                raise self.FormatError(f"Invalid rule format for rule: {rule} ")
        else:
            raise self.FormatError(f"Missing Rule options in: {rule} ")

    def _protocol_selector(self, protocol: str) -> str:
        """Maps the protocol to Suricata rules."""
        protocol = protocol.lower()
        if protocol in self.predefined_rule_protocols.keys():
            return self.predefined_rule_protocols[protocol]
        else:
            raise self.NotSupportedProtocol(f"Not Supported Protocol: {protocol} ")

    def _is_valid_domain(self, domainstring: str) -> bool:
        """
        Ensures that domain entry does not contain only the top-level domains (TLDs).

        :param domainstring: Domain entry
        :type domainstring: str
        """

        return not bool(re.match(rf"^\.[a-zA-Z]{2,}$", domainstring))

    class FormatError(Exception):
        """Exception for invalid format"""

        pass

    class NotSupportedProtocol(Exception):
        """Exception for unsupported protocol"""

        pass
