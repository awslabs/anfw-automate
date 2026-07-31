# Integration Tests — Setup & Run Guide

## Prerequisites

- AWS credentials resolving to the INT account (`537622539377`)
- Docker running (for Lambda bundling)
- `uv` installed (`pip install uv` or `brew install astral-sh/tap/uv`)
- Node.js 20 + corepack enabled
- Yarn dependencies installed (`yarn install`)

## One-Time Setup (First Run Only)

### 1. Update `scripts/velocity/config.toml`

Replace the placeholder account ID with your real INT account:

```toml
[int_account]
account_id = "537622539377"
```

### 2. Create Stage Config Files

**`conf/int.json`** — Global config:

```json
{
  "project": {
    "aws_organziation_scope": "af",
    "brand": "af",
    "department": "sec",
    "project_name": "anfw",
    "module_name": "automate"
  },
  "base": {
    "primary_region": "eu-west-1",
    "target_account_id": "<INT_ACCOUNT_ID>",
    "resource_account_id": "<INT_ACCOUNT_ID>",
    "delegated_admin_account_id": "<INT_ACCOUNT_ID>",
    "organziation_ids": ["o-placeholder"]
  },
  "pipeline": {
    "codestar_connection_arn": "arn:aws:codestar-connections:eu-west-1:<INT_ACCOUNT_ID>:connection/placeholder",
    "repo_name": "awslabs/anfw-automate",
    "repo_branch_name": "dev",
    "auto_promote_pipeline": false,
    "auto_detect_changes": false,
    "tags": { "env": "int", "project": "anfw-automate" }
  }
}
```

**`app/conf/int.json`** — App config (use IntBaseStack outputs):

```json
{
  "eu-west-1": {
    "vpc_id": "<VPC_ID from IntBaseStack>",
    "rule_order": "STRICT_ORDER",
    "supported_regions": ["eu-west-1"],
    "firewall_policy_arns": {
      "eu-west-1": ["<FIREWALL_POLICY_ARN from IntBaseStack>"]
    }
  }
}
```

Get the values from IntBaseStack outputs:

```bash
aws cloudformation describe-stacks --stack-name IntBaseStack \
  --query "Stacks[0].Outputs" --output table
```

### 3. Bootstrap CDK (if not already done)

```bash
npx cdk bootstrap aws://<INT_ACCOUNT_ID>/eu-west-1
```

### 4. Deploy IntBaseStack (stable tier — deployed once, kept warm)

```bash
cd tests/integration/env
npm install
npx cdk deploy IntBaseStack --require-approval never
cd ../../..
```

This creates the TGW-attached VPC, Network Firewall policy, S3 config bucket,
EventBridge wiring, and cross-account role. Takes ~5 minutes the first time;
subsequent runs are a no-op if nothing changed.

### 5. Log in to ECR Public (for Lambda Docker bundling)

```bash
make ecr-login
```

### 6. Deploy the App Stacks (the Lambdas under test)

```bash
STAGE=int make deploy:app
```

This deploys RuleCollect, RuleExecute, SQS queues, and EventBridge rules.

## Running Integration Tests

Once setup is complete, the day-to-day flow is:

```bash
# 1. Run unit tests first (required — the gate enforces this)
make unit

# 2. Run integration tests
make int
```

`make int` will:
1. Verify the unit gate marker is fresh (SHA == HEAD, generated ≤60 min ago)
2. Run `pytest -m integration` against `tests/integration/cases/`
3. The conftest fixtures handle: account guardrail check, baseline capture,
   and guaranteed revert of all ephemeral artifacts
4. Write the INT gate marker on success

## Common Issues

| Error | Cause | Fix |
|-------|-------|-----|
| "sha mismatch" | You committed after `make unit` | Run `make unit` again, then `make int` |
| "Marker 'unit' is stale" | Unit marker >60 min old | Run `make unit` again |
| "Marker 'unit' is missing" | Never ran `make unit` | Run `make unit` first |
| "account is not the allowlisted INT account" | Wrong AWS credentials | Switch to INT account creds |
| "placeholder" error | Config not updated | Replace placeholder in `config.toml` |
| Docker 403 on ECR Public | Not logged in | Run `make ecr-login` |
| "STAGE not defined" | Missing env var | Use `STAGE=int make deploy:app` |
| Config validation error | Field length constraints | See `conf/sample.json` for valid format |

## Architecture Recap

```
INT Account (stable tier — deployed once):
├── IntBaseStack (TGW VPC, NF policy, S3 bucket, EventBridge, IAM role)
└── App stacks (RuleCollect, RuleExecute, SQS, EventBridge rules)

Per-run (ephemeral — created and reverted each run):
├── S3 config objects (run-id scoped)
└── Network Firewall rule groups (run-id scoped)
```

The integration tests upload configs to the tenant's real S3 bucket and verify
outcomes via customer CloudWatch logs and network reachability probes. Cleanup
is handled by deleting configs from S3 in fixture teardown, triggering the
real delete flow.
