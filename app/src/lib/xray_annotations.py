"""X-Ray subsegment annotation helpers for observability.

Annotates active X-Ray subsegments with account, vpc, and event_type so that
traces can be filtered and grouped by these dimensions in the X-Ray console.

Integration points (do NOT modify the Lambda handlers directly):
  - RuleCollect (collect_lambda.py): Call `annotate_subsegment(account, vpc_id, event_type)`
    inside the handler after `account`, `vpc_id`, and `event_type` are resolved.
    For the aws.ec2 branch, call after line ~45:
        annotate_subsegment(account=account, vpc=vpc_id, event_type="DeleteVpc")
    For the aws.s3 branch, call after line ~87:
        annotate_subsegment(account=account, vpc=vpc_id, event_type=event_type)

  - RuleExecute (execute_lambda.py): Call `annotate_subsegment(account, vpc, event_type)`
    inside the `for record in event["Records"]` loop after extracting message attributes
    (after line ~55):
        from lib.xray_annotations import annotate_subsegment
        annotate_subsegment(account=account, vpc="n/a", event_type=event_type)

Requirements: 13.1
"""

from aws_xray_sdk.core import xray_recorder
from aws_lambda_powertools import Logger

logger = Logger(child=True)


def annotate_subsegment(
    account: str,
    vpc: str,
    event_type: str,
) -> None:
    """Add account, vpc, and event_type annotations to the current X-Ray subsegment.

    If no subsegment is active (e.g., tracing is disabled or running outside Lambda),
    this function logs a debug message and returns without raising.

    Args:
        account: The AWS account ID being processed.
        vpc: The VPC ID (with or without 'vpc-' prefix) being processed.
        event_type: The event type string (e.g., 'Update', 'DeleteVpc', 'DeleteS3').
    """
    try:
        subsegment = xray_recorder.current_subsegment()
        if subsegment is None:
            # Try to get the current segment instead (top-level Lambda segment)
            segment = xray_recorder.current_segment()
            if segment is None:
                logger.debug("No active X-Ray segment or subsegment; skipping annotations")
                return
            segment.put_annotation("account", account)
            segment.put_annotation("vpc", vpc)
            segment.put_annotation("event_type", event_type)
        else:
            subsegment.put_annotation("account", account)
            subsegment.put_annotation("vpc", vpc)
            subsegment.put_annotation("event_type", event_type)

        logger.debug(
            "X-Ray annotations added",
            extra={"account": account, "vpc": vpc, "event_type": event_type},
        )
    except Exception as e:
        # Never let annotation failures break the business logic
        logger.warning(f"Failed to annotate X-Ray subsegment: {e}")
