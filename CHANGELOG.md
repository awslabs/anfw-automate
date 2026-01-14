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

### Changed

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
