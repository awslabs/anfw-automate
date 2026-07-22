# Runbook: DLQ Has Messages

## Symptom

The `DLQ depth > 0` CloudWatch alarm has fired, indicating one or more SQS
messages exceeded the maximum receive count and were routed to the dead-letter
queue without successful processing.

## Signals to Check

| Signal | Where to look | What to look for |
|--------|--------------|-----------------|
| DLQ depth | CloudWatch metrics / SQS console | `ApproximateNumberOfMessagesVisible > 0` |
| DLQ message content | SQS console → "Send and receive" | Message body (JSON with rule config) |
| Message attributes | SQS console → message details | `Account`, `Region`, `Event`, `Version`, `CorrelationId` |
| RuleExecute errors | Lambda CloudWatch Logs | Errors during the receive count attempts |
| RuleExecute X-Ray | X-Ray traces | Fault/error segments with annotations |
| InvalidTokenException alarm | CloudWatch alarms | Retries > 3 indicates token staleness |
| ANFW throttle alarm | CloudWatch alarms | Throttling > 0 indicates rate limits |

## Actions

### 1. Inspect the DLQ messages

Check what messages are stuck:

```bash
aws sqs receive-message \
  --queue-url "<dlq_queue_url>" \
  --max-number-of-messages 5 \
  --message-attribute-names All \
  --visibility-timeout 0
```

Note: Using `--visibility-timeout 0` ensures messages remain visible for
further inspection or replay.

### 2. Identify the failure cause

Extract the correlation ID from message attributes and correlate:

```bash
python -c "
from scripts.velocity.diagnoser import Diagnoser
d = Diagnoser()
timeline = d.correlate('<correlation_id_from_message>')
for e in timeline.events:
    print(f'{e.timestamp} [{e.source}] {e.summary}')
"
```

Common causes:
- **InvalidTokenException**: The update token for the rule group became stale
  (concurrent modification). Usually resolves on retry; DLQ indicates max
  retries exhausted.
- **Network Firewall throttling**: API rate limits hit. Wait and replay.
- **Malformed message body**: The config data is corrupted or the Lambda could
  not parse it. Requires a config fix.
- **Permission errors**: Cross-account role expired or was modified.
- **Lambda timeout**: Processing took longer than the 6-second timeout.

### 3. Fix the root cause

- **Token staleness / throttling**: Transient — safe to replay immediately.
- **Malformed config**: Fix the config file in S3. The DLQ message is stale and
  can be purged after the corrected config triggers a fresh run.
- **Permission errors**: Verify the cross-account role is correctly configured
  and re-assume.

### 4. Replay messages

After confirming the root cause is resolved:

```bash
python -c "
from scripts.velocity.diagnoser import Diagnoser
d = Diagnoser()
report = d.replay_dlq('<dlq_queue_url>', max_messages=10)
print(f'Received: {report.total_received}')
print(f'Re-driven: {report.total_redriven}')
print(f'Failed: {report.total_failed}')
for r in report.results:
    status = 'OK' if r.success else f'FAIL: {r.error}'
    print(f'  {r.message_id}: {status}')
"
```

### 5. Verify resolution

After replay, monitor:
- DLQ depth returns to 0 (alarm clears within 5 minutes).
- RuleExecute processes the replayed messages (check invocation count).
- Expected rule groups appear in Network Firewall.

## Escalation

If messages continue to fail after replay:
1. Check if the Network Firewall rule group limit has been reached.
2. Verify the firewall policy has capacity for new rule group references.
3. Check AWS service quotas for Network Firewall in the region.
4. If the DLQ message is corrupt beyond repair, purge it and trigger a fresh
   config upload to regenerate the rules cleanly.
