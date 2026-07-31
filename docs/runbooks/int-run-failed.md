# Runbook: INT Run Failed

## Symptom

The integration test run (`make int`) failed. The CI `int` job shows a non-zero
exit status, or the local run reported test failures. The INT gate marker was
NOT emitted, blocking promotion.

## Signals to Check

| Signal | Where to look | What to look for |
|--------|--------------|-----------------|
| Test output | CI job logs / terminal | Specific `FAILED` test case(s) and assertion messages |
| IntRunReport | `.velocity/reports/` or CI artifacts | JUnit XML + JSON with `mutations_reverted`, `baseline_restored` |
| Account guardrail | Test output (early abort) | "account is not the allowlisted INT account" |
| Stable tier health | CloudFormation console | IntBaseStack + app stacks in `UPDATE_COMPLETE` |
| Ephemeral cleanup | IntRunReport | `mutations_reverted: false` means leaked artifacts |
| Timeouts | Test output | `wait_until` timeout failures (predicate unmet in 240s) |
| Network Firewall state | NF console / customer logs | Rule processing outcomes in tenant CW logs |

## Actions

### 1. Check what failed

Read the IntRunReport (JSON) for a quick summary:

```bash
cat .velocity/reports/int-latest.json | python -m json.tool
```

Or check the JUnit XML for specific test case failures.

### 2. Categorize the failure

#### A. Account guardrail rejection

If the error says the account is not allowlisted:
- Verify `scripts/velocity/config.toml` has the correct `int_account_id`.
- Verify your AWS credentials resolve to the INT account:
  ```bash
  aws sts get-caller-identity
  ```

**Fix:** Switch to INT account credentials (OIDC role or profile).

#### B. Stable tier not ready

If the error references a missing stack, handle, or CloudFormation failure:
- Check CloudFormation for stack status (ROLLBACK, UPDATE_FAILED, etc.).
- Run `ensure_base_infra()` manually to see the deploy output:
  ```bash
  cd app && npx cdk deploy IntBaseStack --require-approval never
  ```

**Fix:** Resolve the CloudFormation error and re-run `make int`.

#### C. Timeout waiting for rule materialization

If `wait_until` timed out (predicate unmet in 240s):
- Check RuleCollect + RuleExecute Lambda logs for the run-id.
- Use the Diagnoser to correlate the event:
  ```bash
  python -c "
  from scripts.velocity.diagnoser import Diagnoser
  d = Diagnoser()
  timeline = d.correlate('<correlation_id>')
  for e in timeline.events:
      print(f'{e.timestamp} [{e.source}] {e.summary}')
  "
  ```
- Common causes: Lambda cold starts + throttling, EventBridge rule misconfiguration,
  SQS visibility timeout issues.

**Fix:** Address the root cause (see "Rule Didn't Appear" runbook), then re-run.

#### D. Assertion failure (rule content mismatch)

If a test asserts on rule names, group content, or customer logs:
- The business logic may have regressed (e.g., hash algorithm change, format change).
- Check if source code changes affected `rule_config.py` or `firewall_handler.py`.

**Fix:** Either fix the regression or update the test expectations if the change
is intentional.

#### E. Cleanup failure (mutations not reverted)

If `mutations_reverted: false` in the report:
- Run-id artifacts leaked into the INT environment.
- Check for rule groups matching the run-id pattern.
- The `Run_Sweeper` backstop will clean them after 24h, but manual cleanup is
  preferred for a clean next run.

**Fix:**
```bash
# List run-id rule groups
aws network-firewall list-rule-groups | grep "<run-id>"

# Manually delete leaked artifacts if needed
# The sweeper will also catch them after 24h
```

### 3. Re-run after fix

```bash
make int
```

If the failure persists after addressing the root cause, check for:
- Concurrent runs conflicting (should not happen with serial default).
- AWS service degradation (check the AWS health dashboard).
- Stale credentials (re-assume the INT role).

### 4. Verify cleanup

After a failed run, always confirm the environment is clean:
- Check that no run-id rule groups remain (unless the sweeper will handle them).
- Verify the firewall policy references only baseline rule groups.
- Confirm `baseline_restored: true` in the next successful run.

## Escalation

If the INT run fails repeatedly despite fixes:
1. Check if the INT account has hit a Network Firewall service quota.
2. Verify the TGW attachment is still active (VPCs attached).
3. Check if the EventBridge bus/rules were accidentally modified.
4. Review recent infrastructure changes to the INT account outside this repo.
