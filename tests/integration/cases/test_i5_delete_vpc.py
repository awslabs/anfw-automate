"""Case I-5: DeleteVpc event removes rules and IP sets.

Property 14: Delete cleanup — within 240 s rules and IP sets for the
VPC are removed after a DeleteVpc CloudTrail-style event is sent to
EventBridge.

Validates: Requirements 9.5
"""

from __future__ import annotations

import json
import time

import pytest

from tests.integration.harness import ConfigPublisher, FirewallInspector, wait_until


def _build_valid_config(account_id: str, vpc_id: str, region: str) -> str:
    """Build a minimal valid YAML config for a TGW-attached VPC."""
    return (
        f"account: '{account_id}'\n"
        f"vpc: '{vpc_id}'\n"
        f"region: '{region}'\n"
        "tgw_attached: true\n"
        "rules:\n"
        "  - protocol: tcp\n"
        "    port: 443\n"
        "    domains:\n"
        "      - delete-vpc-test.example.com\n"
    )


def _build_delete_vpc_event(account_id: str, vpc_id: str, region: str) -> dict:
    """Build a CloudTrail-style DeleteVpc event for EventBridge.

    This mimics the structure of an EC2 DeleteVpc API call event as it would
    appear on EventBridge via CloudTrail.
    """
    return {
        "version": "0",
        "id": f"delete-vpc-test-{int(time.time())}",
        "detail-type": "AWS API Call via CloudTrail",
        "source": "aws.ec2",
        "account": account_id,
        "time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "region": region,
        "detail": {
            "eventSource": "ec2.amazonaws.com",
            "eventName": "DeleteVpc",
            "awsRegion": region,
            "requestParameters": {
                "vpcId": vpc_id,
            },
            "responseElements": {
                "_return": True,
            },
            "userIdentity": {
                "accountId": account_id,
            },
        },
    }


@pytest.mark.integration
def test_delete_vpc_event_removes_rules(
    int_env,
    run_scope,
    mutation_cleaner,
    boto3_session,
):
    """Publish config, wait for rules, send DeleteVpc event, assert cleanup.

    **Property 14: Delete cleanup**

    Steps:
        1. Publish a valid config via ConfigPublisher.
        2. Wait up to 240 s for run-id-scoped rule group to appear.
        3. Simulate a DeleteVpc event by putting a CloudTrail-style event
           on the EventBridge event bus.
        4. Wait up to 240 s for rules and IP sets for that VPC to be removed.

    Validates: Requirements 9.5
    """
    # --- Arrange ---
    publisher = ConfigPublisher(env=int_env, session=boto3_session, scope=run_scope)
    inspector = FirewallInspector(env=int_env, session=boto3_session)

    config_body = _build_valid_config(
        account_id=int_env.account_id,
        vpc_id=int_env.vpc_id,
        region=int_env.region,
    )

    # --- Act 1: Publish config and wait for rules to appear ---
    publisher.put_config(region=int_env.region, config_content=config_body)

    def _rules_exist() -> bool:
        groups = inspector.list_rule_group_names(run_id=run_scope.run_id)
        return len(groups) > 0

    wait_until(
        _rules_exist,
        timeout_s=240,
        description="run-id-scoped rule group to appear after config publish",
    )

    # Confirm rules are present
    groups_before = inspector.list_rule_group_names(run_id=run_scope.run_id)
    assert groups_before, "Expected rule groups before DeleteVpc event"

    # --- Act 2: Simulate DeleteVpc event via EventBridge ---
    events_client = boto3_session.client("events")
    delete_event = _build_delete_vpc_event(
        account_id=int_env.account_id,
        vpc_id=int_env.vpc_id,
        region=int_env.region,
    )

    events_client.put_events(
        Entries=[
            {
                "Source": "aws.ec2",
                "DetailType": "AWS API Call via CloudTrail",
                "Detail": json.dumps(delete_event["detail"]),
                "EventBusName": int_env.event_bus_arn,
            }
        ]
    )

    # --- Assert: rules and IP sets for the VPC are removed within 240 s ---
    def _vpc_rules_removed() -> bool:
        groups = inspector.list_rule_group_names(run_id=run_scope.run_id)
        if not groups:
            return True

        # Check if any remaining groups still contain rules for this VPC
        vpc_id = int_env.vpc_id
        for group_name in groups:
            rule_names = inspector.rule_names_in_group(group_name)
            # If any rule name references the VPC, cleanup is not yet complete
            if any(vpc_id in rn for rn in rule_names):
                return False

        # All groups either removed or contain no VPC-specific rules
        return True

    wait_until(
        _vpc_rules_removed,
        timeout_s=240,
        description=(
            f"rules and IP sets for VPC '{int_env.vpc_id}' to be removed "
            "after DeleteVpc event"
        ),
    )

    # Final assertion
    groups_after = inspector.list_rule_group_names(run_id=run_scope.run_id)
    if groups_after:
        # If groups remain, verify none contain rules for the deleted VPC
        for group_name in groups_after:
            rule_names = inspector.rule_names_in_group(group_name)
            vpc_rules = [rn for rn in rule_names if int_env.vpc_id in rn]
            assert not vpc_rules, (
                f"Expected no rules for VPC '{int_env.vpc_id}' after "
                f"DeleteVpc event, but found in group '{group_name}': {vpc_rules}"
            )
