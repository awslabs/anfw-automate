# Runbook: Rule Didn't Appear

## Symptom

A customer uploaded or updated a `<region>-config.yaml` file to the S3 config
bucket, but the expected Network Firewall rule group (or specific rule within it)
did not materialize within the expected timeframe (~240 seconds).

## Signals to Check

| Signal | Where to look | What to look for |
|--------|--------------|-----------------|
| Config object exists | S3 config bucket | Verify the key matches `<region>-config.yaml` pattern |
| EventBridge event fired | EventBridge console / CW Logs | `Object Created` event for the bucket |
| RuleCollect invoked | Lambda metrics / X-Ray | Invocation count, errors, duration |
| Customer log — processing | Customer Log group | `Processing object: <key>` message |
| Customer log — errors | Customer Log group | `FormatError`, `InternalError`, or `skipped` messages |
| SQS message enqueued | SQS metrics | `NumberOfMessagesSent` on the FIFO queue |
| RuleExecute invoked | Lambda metrics / X-Ray | Invocation count, errors, duration |
| Rule group present | Network Firewall console | Rule group named `{account}-{vpc}-*` |
| DLQ messages | DLQ metrics | `ApproximateNumberOfMessagesVisible > 0` |

## Actions

### 1. Correlate the event

```bash
# Use the Diagnoser to stitch the timeline:
python -c "
from scripts.velocity.diagnoser import Diagnoser
d = Diagnoser()
timeline = d.correlate('<correlation_id>')
for e in timeline.events:
    print(f'{e.timestamp} [{e.source}] {e.summary}')
"
```

If no correlation_id is known, search customer logs by account/version.

### 2. Check for VPC-skip

If the customer log contains `"skipped as it is not attached to TGW"`, the VPC is
not connected to a Transit Gateway. This is expected behavior — rules are only
created for TGW-attached VPCs.

**Fix:** Attach the VPC to the Transit Gateway, then re-upload the config.

### 3. Check for format errors

If the customer log contains `FormatError` or `Invalid Format`:
- Verify the config YAML schema matches the expected structure.
- Check for reserved keywords (`sid:`, `msg:`, etc.) in custom rules.
- Check that domain entries are not TLD-only (e.g., `.com` without a subdomain).

**Fix:** Correct the config file and re-upload.

### 4. Check for processing failures

If RuleCollect succeeded but RuleExecute shows errors:
- Check X-Ray traces for `InvalidTokenException` (token staleness).
- Check for Network Firewall API throttling (CloudWatch alarm).
- Check if the SQS message landed in the DLQ.

**Fix:** If in DLQ, use the replay tool after confirming the root cause:
```bash
python -c "
from scripts.velocity.diagnoser import Diagnoser
d = Diagnoser()
report = d.replay_dlq('<dlq_queue_url>', max_messages=5)
print(f'Re-driven: {report.total_redriven}, Failed: {report.total_failed}')
"
```

### 5. Check for Lambda timeout

If RuleExecute duration approaches or exceeds its timeout (6 s):
- The rule group may be too large or API calls are slow.
- Check for throttling in the ANFW throttle alarm.

**Fix:** Investigate API latency; consider increasing Lambda timeout if rules are
legitimately large.

## Escalation

If none of the above resolves the issue:
1. Check CloudFormation events for the firewall policy stack.
2. Verify the cross-account role permissions are still valid.
3. Check AWS service health for Network Firewall in the region.
