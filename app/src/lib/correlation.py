"""Correlation ID helpers for cross-Lambda tracing.

Provides functions to generate, propagate (via SQS message attributes), extract,
and include a correlation_id in customer log entries so that both RuleCollect and
RuleExecute can be stitched together for the same triggering event.

Integration points (do NOT modify the Lambda handlers directly):

  RuleCollect (collect_lambda.py):
  ─────────────────────────────────
  1. At the top of the handler, generate a correlation_id:
       from lib.correlation import generate_correlation_id
       correlation_id = generate_correlation_id()

  2. When calling `eh.send_to_sqs(...)`, embed it in message attributes by
     calling `build_correlation_attribute(correlation_id)` and merging the
     returned dict into the SQS `MessageAttributes` parameter.

  3. When emitting customer logs, wrap the message:
       from lib.correlation import format_log_with_correlation
       formatted = format_log_with_correlation(correlation_id, original_message)
       customer_log_handler.send_log_message(log_stream_name, formatted, level=Level.INFO)

  RuleExecute (execute_lambda.py):
  ─────────────────────────────────
  1. Inside the `for record in event["Records"]` loop, extract the correlation_id:
       from lib.correlation import extract_correlation_id
       correlation_id = extract_correlation_id(record)

  2. When emitting customer logs, wrap the message:
       from lib.correlation import format_log_with_correlation
       formatted = format_log_with_correlation(correlation_id, original_message)
       customer_log_handler.send_log_message(log_stream_name, formatted, level=Level.INFO)

Requirements: 13.2
"""

import uuid
from typing import Optional

from aws_lambda_powertools import Logger

logger = Logger(child=True)

# The SQS message attribute key used to propagate the correlation ID
CORRELATION_ID_ATTR_KEY = "CorrelationId"


def generate_correlation_id() -> str:
    """Generate a new correlation ID for a triggering event.

    Called once per invocation in RuleCollect to uniquely identify the
    end-to-end processing of a single config event.

    Returns:
        A UUID4 string, e.g. '550e8400-e29b-41d4-a716-446655440000'.
    """
    correlation_id = str(uuid.uuid4())
    logger.debug(f"Generated correlation_id: {correlation_id}")
    return correlation_id


def build_correlation_attribute(correlation_id: str) -> dict:
    """Build an SQS MessageAttributes dict entry for the correlation ID.

    The returned dict should be merged into the existing MessageAttributes
    when calling `sqs.send_message(...)`.

    Args:
        correlation_id: The correlation ID to embed.

    Returns:
        A dict with the correlation ID formatted as an SQS string attribute:
        {"CorrelationId": {"DataType": "String", "StringValue": "<id>"}}
    """
    return {
        CORRELATION_ID_ATTR_KEY: {
            "DataType": "String",
            "StringValue": correlation_id,
        }
    }


def extract_correlation_id(sqs_record: dict) -> Optional[str]:
    """Extract the correlation ID from an SQS event record.

    Called in RuleExecute for each record in the event["Records"] list.

    Args:
        sqs_record: A single SQS record from the Lambda event payload.

    Returns:
        The correlation ID string, or None if the attribute is missing
        (graceful degradation for messages sent before correlation was enabled).
    """
    try:
        attrs = sqs_record.get("messageAttributes", {})
        correlation_attr = attrs.get(CORRELATION_ID_ATTR_KEY, {})
        correlation_id = correlation_attr.get("stringValue") or correlation_attr.get(
            "StringValue"
        )
        if correlation_id:
            logger.debug(f"Extracted correlation_id: {correlation_id}")
        else:
            logger.debug("No correlation_id found in SQS message attributes")
        return correlation_id
    except Exception as e:
        logger.warning(f"Failed to extract correlation_id: {e}")
        return None


def format_log_with_correlation(correlation_id: Optional[str], message: str) -> str:
    """Prefix a log message with the correlation ID for customer logs.

    When included in customer log entries, this allows the Diagnoser to stitch
    logs from both Lambdas into a single timeline.

    Args:
        correlation_id: The correlation ID (may be None for legacy messages).
        message: The original log message.

    Returns:
        A formatted string: '[correlation_id=<id>] <message>' or just '<message>'
        if correlation_id is None.
    """
    if correlation_id:
        return f"[correlation_id={correlation_id}] {message}"
    return message
