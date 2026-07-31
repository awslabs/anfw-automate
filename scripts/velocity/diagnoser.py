"""Diagnoser — Observability and failure-diagnosis tooling.

Provides:
  - `correlate(correlation_id)`: Stitches X-Ray segments, customer log events,
    and SQS/DLQ records into a single timestamp-ascending timeline.
  - `replay_dlq(queue_url, max_messages)`: Re-drives DLQ messages to the source
    queue, reporting per-message success/failure.

Requirements: 13.5, 13.6, 13.8, 13.9
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

import boto3
from botocore.exceptions import ClientError


# ─── Data Models ──────────────────────────────────────────────────────────────


@dataclass
class TimelineEvent:
    """A single event in a correlated timeline."""

    timestamp: str  # ISO-8601 UTC
    source: str  # 'xray', 'customer_log', 'sqs', 'dlq'
    summary: str  # Human-readable description
    raw: Optional[dict] = None  # Original payload for debugging


@dataclass
class Timeline:
    """The correlated timeline for a single correlation_id."""

    correlation_id: str
    events: list[TimelineEvent] = field(default_factory=list)
    empty: bool = False  # True when no records matched


@dataclass
class ReplayResult:
    """Result of a single DLQ message re-drive attempt."""

    message_id: str
    success: bool
    error: Optional[str] = None


@dataclass
class ReplayReport:
    """Summary of a DLQ replay operation."""

    queue_url: str
    total_received: int = 0
    total_redriven: int = 0
    total_failed: int = 0
    results: list[ReplayResult] = field(default_factory=list)


# ─── Diagnoser ────────────────────────────────────────────────────────────────


class Diagnoser:
    """Failure diagnosis tooling for the ANFW automation pipeline."""

    def __init__(
        self,
        region: str = "eu-west-1",
        log_group_prefix: str = "cw-",
        session: Optional[boto3.Session] = None,
    ):
        self._session = session or boto3.Session(region_name=region)
        self._region = region
        self._log_group_prefix = log_group_prefix
        self._xray = self._session.client("xray", region_name=region)
        self._logs = self._session.client("logs", region_name=region)
        self._sqs = self._session.client("sqs", region_name=region)

    def correlate(self, correlation_id: str) -> Timeline:
        """Stitch X-Ray segments + customer log events + SQS/DLQ records into a
        single timestamp-ascending timeline for the given correlation ID.

        Returns an empty-result indication (Timeline.empty = True) when no
        records match — this is not an error condition.

        Args:
            correlation_id: The UUID correlation ID propagated through the pipeline.

        Returns:
            A Timeline object with events sorted by timestamp ascending.
        """
        timeline = Timeline(correlation_id=correlation_id)

        # 1. Gather X-Ray trace segments matching the correlation_id
        xray_events = self._fetch_xray_events(correlation_id)
        timeline.events.extend(xray_events)

        # 2. Gather customer log events containing the correlation_id
        log_events = self._fetch_log_events(correlation_id)
        timeline.events.extend(log_events)

        # 3. Check for SQS/DLQ records (via CloudWatch Logs Insights on Lambda logs)
        sqs_events = self._fetch_sqs_events(correlation_id)
        timeline.events.extend(sqs_events)

        # Sort by timestamp ascending
        timeline.events.sort(key=lambda e: e.timestamp)

        # Mark as empty if no records found
        if not timeline.events:
            timeline.empty = True

        return timeline

    def _fetch_xray_events(self, correlation_id: str) -> list[TimelineEvent]:
        """Query X-Ray for trace segments annotated with the correlation_id."""
        events: list[TimelineEvent] = []
        try:
            # Search for traces with the correlation_id annotation
            filter_expr = f'annotation.correlation_id = "{correlation_id}"'
            response = self._xray.get_trace_summaries(
                StartTime=datetime.now(timezone.utc).replace(hour=0, minute=0, second=0),
                EndTime=datetime.now(timezone.utc),
                FilterExpression=filter_expr,
            )

            for trace_summary in response.get("TraceSummaries", []):
                trace_id = trace_summary.get("Id", "unknown")
                start_time = trace_summary.get("ResponseTime", datetime.now(timezone.utc))
                if hasattr(start_time, "isoformat"):
                    ts = start_time.isoformat()
                else:
                    ts = str(start_time)

                events.append(
                    TimelineEvent(
                        timestamp=ts,
                        source="xray",
                        summary=f"X-Ray trace {trace_id} — "
                        f"status={trace_summary.get('Http', {}).get('HttpStatus', 'n/a')}",
                        raw=trace_summary,
                    )
                )
        except ClientError as e:
            # Non-fatal: X-Ray may not have data for this correlation_id
            events.append(
                TimelineEvent(
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    source="xray",
                    summary=f"X-Ray query failed: {e.response['Error']['Message']}",
                )
            )
        return events

    def _fetch_log_events(self, correlation_id: str) -> list[TimelineEvent]:
        """Search CloudWatch Logs for customer log entries containing the correlation_id."""
        events: list[TimelineEvent] = []
        try:
            # Find log groups matching the prefix (customer logs)
            paginator = self._logs.get_paginator("describe_log_groups")
            log_groups = []
            for page in paginator.paginate(logGroupNamePrefix=self._log_group_prefix):
                for lg in page.get("logGroups", []):
                    log_groups.append(lg["logGroupName"])

            if not log_groups:
                return events

            # Use filter_log_events to search for the correlation_id
            now_ms = int(time.time() * 1000)
            one_day_ago_ms = now_ms - (24 * 60 * 60 * 1000)

            for log_group in log_groups:
                try:
                    response = self._logs.filter_log_events(
                        logGroupName=log_group,
                        startTime=one_day_ago_ms,
                        endTime=now_ms,
                        filterPattern=f'"{correlation_id}"',
                        limit=100,
                    )
                    for event in response.get("events", []):
                        ts = datetime.fromtimestamp(
                            event["timestamp"] / 1000, tz=timezone.utc
                        ).isoformat()
                        events.append(
                            TimelineEvent(
                                timestamp=ts,
                                source="customer_log",
                                summary=event.get("message", "").strip(),
                                raw={
                                    "logGroup": log_group,
                                    "logStream": event.get("logStreamName"),
                                    "eventId": event.get("eventId"),
                                },
                            )
                        )
                except ClientError:
                    # Skip log groups that error (e.g., permissions)
                    continue

        except ClientError as e:
            events.append(
                TimelineEvent(
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    source="customer_log",
                    summary=f"Log query failed: {e.response['Error']['Message']}",
                )
            )
        return events

    def _fetch_sqs_events(self, correlation_id: str) -> list[TimelineEvent]:
        """Search Lambda execution logs for SQS/DLQ processing of the correlation_id."""
        events: list[TimelineEvent] = []
        try:
            # Lambda log groups typically follow /aws/lambda/<function-name>
            paginator = self._logs.get_paginator("describe_log_groups")
            lambda_log_groups = []
            for page in paginator.paginate(logGroupNamePrefix="/aws/lambda/"):
                for lg in page.get("logGroups", []):
                    lambda_log_groups.append(lg["logGroupName"])

            now_ms = int(time.time() * 1000)
            one_day_ago_ms = now_ms - (24 * 60 * 60 * 1000)

            for log_group in lambda_log_groups:
                try:
                    response = self._logs.filter_log_events(
                        logGroupName=log_group,
                        startTime=one_day_ago_ms,
                        endTime=now_ms,
                        filterPattern=f'"{correlation_id}"',
                        limit=50,
                    )
                    for event in response.get("events", []):
                        message = event.get("message", "")
                        # Only include SQS-related log entries
                        if "SQS" in message or "sqs" in message or "DLQ" in message or "dlq" in message:
                            ts = datetime.fromtimestamp(
                                event["timestamp"] / 1000, tz=timezone.utc
                            ).isoformat()
                            events.append(
                                TimelineEvent(
                                    timestamp=ts,
                                    source="sqs",
                                    summary=message.strip(),
                                    raw={
                                        "logGroup": log_group,
                                        "logStream": event.get("logStreamName"),
                                    },
                                )
                            )
                except ClientError:
                    continue

        except ClientError:
            pass  # Non-fatal
        return events

    # ─── DLQ Replay (Task 14.6) ───────────────────────────────────────────

    def replay_dlq(self, queue_url: str, max_messages: int = 10) -> ReplayReport:
        """Re-drive DLQ messages to the source queue.

        Receives up to `max_messages` from the DLQ and sends each to the
        source queue (derived from the DLQ's redrive-allow policy or naming
        convention). Reports per-message success/failure and continues past
        messages that cannot be re-driven.

        Args:
            queue_url: The URL of the DLQ to drain.
            max_messages: Maximum number of messages to re-drive (default 10).

        Returns:
            A ReplayReport summarizing the operation.
        """
        report = ReplayReport(queue_url=queue_url)

        # Resolve the source queue URL from the DLQ
        source_queue_url = self._resolve_source_queue(queue_url)
        if not source_queue_url:
            report.results.append(
                ReplayResult(
                    message_id="n/a",
                    success=False,
                    error="Could not determine source queue from DLQ attributes or naming",
                )
            )
            return report

        messages_processed = 0
        while messages_processed < max_messages:
            batch_size = min(10, max_messages - messages_processed)
            try:
                response = self._sqs.receive_message(
                    QueueUrl=queue_url,
                    MaxNumberOfMessages=batch_size,
                    MessageAttributeNames=["All"],
                    WaitTimeSeconds=5,
                )
            except ClientError as e:
                report.results.append(
                    ReplayResult(
                        message_id="n/a",
                        success=False,
                        error=f"Failed to receive from DLQ: {e.response['Error']['Message']}",
                    )
                )
                break

            messages = response.get("Messages", [])
            if not messages:
                break  # DLQ is empty or no more messages within budget

            for msg in messages:
                messages_processed += 1
                report.total_received += 1
                message_id = msg.get("MessageId", "unknown")

                result = self._redrive_message(msg, source_queue_url, queue_url)
                report.results.append(result)

                if result.success:
                    report.total_redriven += 1
                else:
                    report.total_failed += 1

                if messages_processed >= max_messages:
                    break

        return report

    def _redrive_message(
        self, msg: dict, source_queue_url: str, dlq_url: str
    ) -> ReplayResult:
        """Attempt to send a single message to the source queue and delete from DLQ."""
        message_id = msg.get("MessageId", "unknown")

        try:
            # Build send parameters
            send_kwargs: dict = {
                "QueueUrl": source_queue_url,
                "MessageBody": msg["Body"],
            }

            # Propagate message attributes
            if msg.get("MessageAttributes"):
                send_kwargs["MessageAttributes"] = msg["MessageAttributes"]

            # Handle FIFO queues (need MessageGroupId and deduplication)
            if source_queue_url.endswith(".fifo"):
                # Use the original message group id from attributes or default
                send_kwargs["MessageGroupId"] = msg.get("Attributes", {}).get(
                    "MessageGroupId", "replay"
                )
                send_kwargs["MessageDeduplicationId"] = f"replay-{message_id}-{int(time.time())}"

            self._sqs.send_message(**send_kwargs)

            # Delete from DLQ on successful send
            self._sqs.delete_message(
                QueueUrl=dlq_url,
                ReceiptHandle=msg["ReceiptHandle"],
            )

            return ReplayResult(message_id=message_id, success=True)

        except ClientError as e:
            return ReplayResult(
                message_id=message_id,
                success=False,
                error=f"Re-drive failed: {e.response['Error']['Message']}",
            )
        except Exception as e:
            return ReplayResult(
                message_id=message_id,
                success=False,
                error=f"Unexpected error: {str(e)}",
            )

    def _resolve_source_queue(self, dlq_url: str) -> Optional[str]:
        """Determine the source queue URL from DLQ attributes or naming convention.

        Strategy:
        1. Check the DLQ's RedriveAllowPolicy for the source queue ARN.
        2. Fall back to naming convention: replace 'dlq-' prefix with 'sqs-'.
        """
        try:
            # Try to get queue attributes for redrive info
            response = self._sqs.get_queue_attributes(
                QueueUrl=dlq_url,
                AttributeNames=["RedriveAllowPolicy", "QueueArn"],
            )
            attrs = response.get("Attributes", {})

            # Check RedriveAllowPolicy
            allow_policy = attrs.get("RedriveAllowPolicy")
            if allow_policy:
                policy = json.loads(allow_policy)
                source_arns = policy.get("sourceQueueArns", [])
                if source_arns:
                    # Convert ARN to URL
                    arn = source_arns[0]
                    parts = arn.split(":")
                    account_id = parts[4]
                    queue_name = parts[5]
                    region = parts[3]
                    return f"https://sqs.{region}.amazonaws.com/{account_id}/{queue_name}"

        except (ClientError, json.JSONDecodeError, IndexError, KeyError):
            pass

        # Fallback: naming convention (dlq-* → sqs-*)
        # e.g. dlq-anfw-dev-LambdaSQS.fifo → sqs-anfw-dev-LambdaSQS.fifo
        try:
            # Extract queue name from URL
            queue_name = dlq_url.rstrip("/").split("/")[-1]
            if queue_name.startswith("dlq-"):
                source_name = "sqs-" + queue_name[4:]
                # Get source queue URL
                response = self._sqs.get_queue_url(QueueName=source_name)
                return response.get("QueueUrl")
        except ClientError:
            pass

        return None
