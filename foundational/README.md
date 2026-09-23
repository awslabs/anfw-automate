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
# synthesize / deploy all foundational stacks for a stage
STAGE=int  yarn exec cdk deploy --all
STAGE=prod yarn exec cdk deploy --all
```

The shared Transit Gateway stack (`network/`) is a separate create-once deploy in
the network account and is **not** part of the per-stage `cdk deploy --all` set.
