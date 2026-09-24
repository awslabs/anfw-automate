# Foundational Module

Consolidated CDK module for the ANFW **supporting infrastructure** — the VPC,
AWS Network Firewall, base routing, and routing stacks that a live data plane
needs. It replaces the standalone `vpc/` and `firewall/` modules and their
CodePipeline wrappers: foundational infrastructure deploys once per stage via
manual `cdk deploy`.

> The customer-facing rule-management **solution** lives in `app/` and is not
> part of this module. See `.kiro/specs/foundational-stack-migration/` for the
> full design.

## Stage model

Each stage that needs a live data plane (`int`, `prod`) gets its **own**
foundational fabric — its own firewall, policy, and routing — hanging off the
shared Transit Gateway. `dev` deploys nothing (unit tests only).

## Layout

```
bin/foundational.ts   # multi-region, stage-parameterized entry point
network/              # shared-once Transit Gateway + RAM share
vpc/                  # VPC stack
firewall/             # firewall, base-routing, routing stacks + policy + lambdas
conf/                 # merged VPC+Firewall per-region config + schema
test/                 # CDK assertion tests
```

## Prerequisites

- Node >= 20.8.1, Yarn 4 (repo uses Yarn workspaces)
- AWS CDK v2 (pinned in `package.json`)
- Docker (for bundling the Python routing Lambdas during `cdk synth`)
- Run `yarn install` from the repository root

## Build

```bash
# from the repository root
yarn workspace foundational build   # tsc + cdk synth

# or from this directory
make build
```

## Test

```bash
make test        # jest CDK assertion tests
```

## Deploy

Configuration is loaded for a stage via the shared config loader (SSM parameter
`/anfw-automate/{stage}/foundational/config` first, then
`conf/{stage}.json`). The `STAGE` is supplied to the entry point.

```bash
# per-stage fabric (VPC + firewall + base-routing + routing) → firewall/solution
# account (target_account_id). Credentials must resolve to that account.
STAGE=int  yarn exec cdk deploy --all
STAGE=prod yarn exec cdk deploy --all
```

### Shared Transit Gateway (create-once, network account)

The TGW hub is a **separate** create-once deploy — not part of `cdk deploy --all`
and not stage-scoped. It uses its own entry point (`bin/transit_gateway.ts`), so
pass an explicit `--app`. Credentials must resolve to the network account.

```bash
yarn exec cdk --app "npx ts-node --prefer-ts-exts bin/transit_gateway.ts" deploy \
  --context networkAccountId=040781035187 \
  --context sharePrincipals=421222417363,537622539377,868363312618 \
  --context namePrefix=af-anfw-automate
```

This creates the Transit Gateway, RAM-shares it to the firewall + INT (+ dev)
accounts, and publishes `/anfw-automate/shared/tgw-id`, which the per-stage fabric
and the INT tenant tier resolve from SSM.

### Deploy order (for the INT environment)

1. **TGW** (network account `040781035187`) — command above.
2. **int fabric** (`STAGE=int cdk deploy --all`, firewall account `421222417363`) —
   publishes `/anfw-automate/int/foundational/firewall-policy-arn`.
3. Then the `app` (int) and the INT tenant tier — see the `int-environment` spec.
