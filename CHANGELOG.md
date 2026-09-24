# Changelog

All notable changes to this project will be documented in this file. See
[standard-version](https://github.com/conventional-changelog/standard-version)
for commit guidelines.

## [Unreleased]

### ⚠ BREAKING CHANGES

**Migration from npm to Yarn 4.12.0**

The project has migrated from npm to Yarn 4.12.0 as the package manager. This is
a breaking change that requires action from all contributors and users.

**Required Actions:**

1. Install Yarn 4.12.0: `corepack enable` (or `npm install -g yarn`)
2. Remove `node_modules` and `package-lock.json` if they exist
3. Run `yarn install` instead of `npm install`
4. Update CI/CD pipelines to use Yarn commands
5. Update any scripts or automation that use npm commands

**Command Changes:**

- `npm install` → `yarn install`
- `npm ci` → `yarn install --immutable`
- `npm test` → `yarn test`
- `npm run <script>` → `yarn <script>`
- `npx <command>` → `yarn exec <command>`

See [docs/YARN_MIGRATION.md](docs/YARN_MIGRATION.md) for complete migration
guide.

**Foundational Stack Consolidation (supporting infrastructure only)**

The standalone `vpc/` and `firewall/` CDK modules have been consolidated into a
single `foundational/` module, and their CodePipeline wrappers removed in favor of
manual `cdk deploy`. This affects operators who deploy the network fabric. It does
**not** change the rule-management solution in `app/` — the upload/config schema,
S3 key pattern, rule naming, reserved rule group, and cross-account role behavior
are unchanged, so **consumers of the solution need take no action.**

**Required Actions (infrastructure operators):**

1. Deploy the shared Transit Gateway via `foundational/bin/transit_gateway.ts`
   (create-once, network account).
2. Deploy the per-stage fabric with `STAGE=<stage> yarn exec cdk deploy --all` from
   `foundational/` (this replaces the old `vpc`/`firewall` pipelines).
3. Move configuration to `foundational/vpc/conf/` and `foundational/firewall/conf/`.
4. Retire the old `vpc-*` / `firewall-*` pipelines and stacks. The old flow-log
   bucket and firewall log groups are retained (orphaned) and need manual cleanup.
5. Update any external references to the old stack names (now
   `{stackType}-{namePrefix}-{regionKey}-{stage}`) and firewall log group names
   (now auto-generated).

See [docs/FOUNDATIONAL_MIGRATION.md](docs/FOUNDATIONAL_MIGRATION.md) for the
complete guide.

### Added

- Consolidated `foundational/` CDK module (VPC + Network Firewall + base routing +
  routing) with a single multi-region, stage-parameterized entry point.
- Code-owned shared Transit Gateway (`foundational/bin/transit_gateway.ts`) with RAM
  sharing and a `/anfw-automate/shared/tgw-id` SSM handle for cross-account use.
- Cross-account foundational handles published to SSM (e.g.
  `/anfw-automate/{stage}/foundational/firewall-policy-arn`).
- CDK assertion tests for the migrated VPC/firewall stacks and for `IntBaseStack`.

### Changed

- Consolidated the `vpc/` and `firewall/` modules into `foundational/` and removed
  their CodePipeline wrappers; foundational infrastructure now deploys via manual
  `cdk deploy`. Foundational stack names follow
  `{stackType}-{namePrefix}-{regionKey}-{stage}`.
- Foundational flow-log S3 bucket and firewall alert/flow CloudWatch log groups now
  use `RETAIN` with auto-generated names, so a delete/recreate never clashes.
- Migrated all build scripts, Makefiles, and CI/CD workflows from npm to Yarn
- Updated all module Makefiles to use Yarn commands
- Updated Husky git hooks to use Yarn
- Updated GitHub Actions workflows to use Yarn
- Standardized security scanning to use Yarn audit

### Fixed

- Fixed security scan failures due to inconsistent command naming
- Fixed corrupted `.gitleaks.toml` configuration file
- Standardized bandit configuration usage across all scripts
- Fixed all npm/npx references to use Yarn equivalents

### Removed

- Removed the standalone `vpc/` and `firewall/` top-level modules and their
  CodePipeline / CDK `Stage` wrappers.
- Removed pipeline-artifact CDK Nag suppressions (`AwsSolutions-S1`,
  `AwsSolutions-KMS5`) and unused `@aws-cdk/aws-codepipeline*` context flags from the
  foundational module.

### 2.1.0 (2024-04-12)

### Added

- Created shared libraries and CDK constructs in shared library
- New Feature allowing users to define tags that will applied to all supported
  resources created by solution.

### Changed

- Restructed the repo and created independent CDK modules for app, firewall, and
  vpc
- Moved the configuration files for each module in their respective
  `conf`folders.
- Moved the `global.json` configuration files to a central shared configuration
  folder `conf`
- Removed the configuration folders for each stage and instead renamed the files
  to use stage name e.g. `dev.json`
- Changed README section to point to dedicated module README for deployments

### Fixed

- Updated vulnerable `idna` libraries.

### Removed

- Removed `STACKNAME` requirement from `deploy_vars.sh` as it was redundant with
  independent modules.

### 2.0.1 (2024-04-02)

### Added

- Unit tests for event_handler and log_handler libraries

### Changed

- Updated build script to fix pytest execution
- Updated bandit excludes

### Removed

- Removed dangling VPC Gateway Endpoint from serverless stack

### 2.0.0 (2024-03-11)

### Added

- Support for both STRICT and ACTION order in AWS Network Firewall
- JSON Schema Validation for all configuration files
- Enforced pytest execution on each build
- Configuration to provide AWS Network Firewall ARN to attach the rule groups.
- Decoupled firewall policy from the code

### Changed

- Swtiched from INTERNAL_NET varaible to HOME_NET varaible to identify internal
  network CIDRs
- Changed firewall policy creation to use HOME_NET override feature
- Renamed default_deny.yaml to global_rules.yaml
- Changed the configuration file structure to support new features

### Fixed

- Pytest for firewall_handler library
- Fixed poetry dependency structure so that dev, test, and build dependencies
  are independent

### Removed

- Pytest tests that failed and need to be rewritten
- INTERNAL_NET varaible as this is not being used.

### 1.0.0 (2024-01-25)

### Added

- Initial release
