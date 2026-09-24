# Foundational Stack Migration Guide

This guide is for **operators who deploy the supporting infrastructure** (VPC,
AWS Network Firewall, routing). It describes how to move from the previous
standalone `vpc/` and `firewall/` modules to the consolidated `foundational/`
module.

> **Scope — read this first.** This migration affects only the *supporting
> infrastructure*. It does **not** change the product — the rule-management
> solution in `app/` (RuleCollect / RuleExecute) is untouched: the upload/config
> schema, S3 key pattern, rule naming, reserved rule group, and cross-account
> role behavior are all identical. **If you only consume the rule-management
> solution, no action is required.** This guide is for whoever deploys the
> network fabric.

## What changed and why

The `vpc/` and `firewall/` CDK modules were merged into a single `foundational/`
module, and their CodePipeline wrappers were removed in favor of manual
`cdk deploy`.

Rationale: the foundational stacks are deploy-once, low-frequency, high-blast-radius
supporting infrastructure that lands in only one or two accounts. A self-mutating
CodePipeline (artifact bucket, KMS keys, cross-account keys, self-mutate step) added
cost and moving parts with no benefit — there is no multi-account fan-out to
automate. A deliberate, human-reviewed `cdk deploy` (preceded by `cdk diff`) is both
simpler and safer for this class of infrastructure.

> The `app/` module keeps its pipeline: it fans out to many accounts via
> CloudFormation StackSets, which is exactly what a pipeline is for.

## Summary of breaking changes

| Area | Before | After |
|------|--------|-------|
| Modules | `vpc/`, `firewall/` | `foundational/` |
| Yarn workspaces | `vpc`, `firewall` | `foundational` |
| Deploy method | CodePipeline (self-mutating) | manual `cdk deploy` |
| Entry points | `vpc/bin/vpc.ts`, `firewall/bin/firewall.ts` | `foundational/bin/foundational.ts` (fabric) + `foundational/bin/transit_gateway.ts` (shared TGW) |
| Stack names | per-module | `{stackType}-{namePrefix}-{regionKey}-{stage}` |
| Config location | `vpc/conf/`, `firewall/conf/` | `foundational/vpc/conf/`, `foundational/firewall/conf/` |
| Transit Gateway | created manually / out of band | code-owned (`TransitGatewayStack`), RAM-shared, id in SSM |
| Flow-log bucket | `RemovalPolicy.DESTROY`, stable name | `RETAIN`, auto-generated name |
| Firewall log groups | fixed names | `RETAIN`, auto-generated names |

The config **contract is unchanged**: the VPC and Firewall configs remain
separate, region-keyed documents (they are intentionally not merged), and the
Firewall config still takes `vpc_id`, `subnet_ids`, `internet_gateway_id`,
`vpc_cidr`, and `transit_gateway` as inputs — these may come from a central
landing-zone deployment rather than this repo's VPC stack. The config loader is
unchanged.

## Prerequisites

- Node >= 20.8.1, Yarn 4 (see [YARN_MIGRATION.md](YARN_MIGRATION.md)).
- AWS CDK v2, Docker (for the routing Lambda bundle).
- `yarn install` from the repository root.
- AWS credentials for the target account(s); confirm you are **not** targeting a
  production account unintentionally.

## Configuration

Each sub-module keeps its own region-keyed config and schema:

- VPC: SSM `/anfw-automate/{stage}/vpc/config` → file `foundational/vpc/conf/{stage}.json`
- Firewall: SSM `/anfw-automate/{stage}/firewall/config` → file `foundational/firewall/conf/{stage}.json`

SSM is tried first; a miss falls back to the local file (a file-only workflow is
fully supported). Copy the tracked `sample.json` in each `conf/` directory to
`{stage}.json` and fill in real values. Real `{stage}.json` files are gitignored.

The account fields in the global `conf/{stage}.json` follow these semantics:

- `resource_account_id` — the account where **pipelines** deploy (used by `app`).
- `target_account_id` — the account where **stack resources** deploy. The
  foundational fabric deploys here (the firewall/solution account).

## Deploying a fresh environment

Deploy in dependency order:

### 1. Shared Transit Gateway (create-once, network account)

The TGW hub is created once and RAM-shared. It uses its own entry point, so pass
an explicit `--app`. Credentials must resolve to the network account.

```bash
cd foundational
yarn exec cdk --app "npx ts-node --prefer-ts-exts bin/transit_gateway.ts" deploy \
  --context networkAccountId=<network-account-id> \
  --context sharePrincipals=<firewall-account-id>,<int-account-id> \
  --context namePrefix=<namePrefix>
```

This creates the Transit Gateway, RAM-shares it to the listed accounts, and
publishes `/anfw-automate/shared/tgw-id`.

### 2. Per-stage fabric (firewall/solution account)

```bash
cd foundational
STAGE=<stage> yarn exec cdk deploy --all
```

This deploys, in order, `VpcStack → NetworkFirewallStack → BaseRoutingStack →
RoutingStack` for each region key in the config, and publishes the firewall
handles (e.g. `/anfw-automate/{stage}/foundational/firewall-policy-arn`) for
cross-account consumers.

Always run `yarn exec cdk diff` first and review the plan.

## Migrating an existing deployment

If you previously deployed the old `vpc-*` / `firewall-*` pipelines and stacks,
plan the cutover carefully — this is the breaking part.

1. **Inventory** the existing CloudFormation stacks and CodePipelines created by
   the old `vpc/` and `firewall/` modules.
2. **Retire the old pipelines** once the new fabric is deployed and verified.
   Deleting a pipeline stack also removes its artifact bucket and KMS key.
3. **Resource renames — expect new physical names.** The flow-log S3 bucket and
   the firewall alert/flow CloudWatch log groups are now created with
   auto-generated names and a `RETAIN` deletion policy. When you delete the old
   stacks:
   - The **old** flow-log bucket and firewall log groups are **retained**
     (not deleted) — they become orphaned and must be cleaned up manually if you
     no longer need the historical logs.
   - The **new** fabric creates fresh buckets/log groups with new names, so a
     redeploy never collides with a retained resource.
4. **Transit Gateway** — if a TGW already exists (created manually before this
   change), do **not** deploy `TransitGatewayStack` on top of it. Either:
   - import the existing TGW into the stack (`cdk import`), or
   - skip the TGW stack and set `/anfw-automate/shared/tgw-id` to the existing
     TGW id manually so downstream stacks resolve it.
5. **Stack names changed** to `{stackType}-{namePrefix}-{regionKey}-{stage}`. Any
   external automation, dashboards, or references to the old stack names must be
   updated. CloudFormation cannot rename a stack in place — the new fabric is a
   new set of stacks, not an update of the old ones.
6. **Firewall log group names changed** (now auto-generated). If external
   dashboards, metric filters, or subscription filters targeted the old literal
   names (`{prefix}.nfw.alert.{stage}` / `.flow.`), repoint them.

## What did NOT change

- The `app/` module and its deployment pipeline (StackSet fan-out).
- The customer-facing rule-management contract (upload schema, S3 key pattern,
  rule naming `{account}-{vpc}-{hash}`, reserved rule group, cross-account role).
- The `shared/` module and the config loader.
- The separate-per-stack config model for VPC and Firewall.

## Verification

```bash
cd foundational
make build          # tsc + cdk synth
make test           # jest CDK assertions
STAGE=<stage> yarn exec cdk ls   # confirm the four stacks resolve
```
