## 2.2.0-beta.1 (2025-12-30)

* fix: eslint in every module ([3faa2f3](https://github.com/awslabs/anfw-automate/commit/3faa2f3))
* fix: fix cdk version mismatch ([62bf780](https://github.com/awslabs/anfw-automate/commit/62bf780))
* fix: fix github actions errors ([51d4a42](https://github.com/awslabs/anfw-automate/commit/51d4a42))
* fix(ci): node version mismatch errors ([0662ce0](https://github.com/awslabs/anfw-automate/commit/0662ce0))
* fix(ci): semantic release git commit ([4cf827e](https://github.com/awslabs/anfw-automate/commit/4cf827e))
* fix(ci): semantic release ([392d278](https://github.com/awslabs/anfw-automate/commit/392d278))
* fix(ci): update husky restrictions for ci ([e4d3bde](https://github.com/awslabs/anfw-automate/commit/e4d3bde))
* build(app): poetry lock ([f4579a8](https://github.com/awslabs/anfw-automate/commit/f4579a8))
* build(firewall): poetry lock ([9e23e2e](https://github.com/awslabs/anfw-automate/commit/9e23e2e))
* build: update packages ([2bbc0b2](https://github.com/awslabs/anfw-automate/commit/2bbc0b2))
* feat(ci): add automatic semantic versioning ([2c9cf5b](https://github.com/awslabs/anfw-automate/commit/2c9cf5b))
* feat: commit standards ([decb217](https://github.com/awslabs/anfw-automate/commit/decb217))
* feat: improve dev workflow ([1c1ee6c](https://github.com/awslabs/anfw-automate/commit/1c1ee6c))
* docs: update all MD files ([3eb6755](https://github.com/awslabs/anfw-automate/commit/3eb6755))
* refactor: use workspaces and push central package-lock ([929df6f](https://github.com/awslabs/anfw-automate/commit/929df6f))

# Changelog

All notable changes to this project will be documented in this file. See [standard-version](https://github.com/conventional-changelog/standard-version) for commit guidelines.

### 2.1.0 (2024-04-12)
### Added
- Created shared libraries and CDK constructs in shared library
- New Feature allowing users to define tags that will applied to all supported resources created by solution.

### Changed
- Restructed the repo and created independent CDK modules for app, firewall, and vpc
- Moved the configuration files for each module in their respective `conf`folders.
- Moved the `global.json` configuration files to a central shared configuration folder `conf`
- Removed the configuration folders for each stage and instead renamed the files to use stage name e.g. `dev.json`
- Changed README section to point to dedicated module README for deployments

### Fixed
- Updated vulnerable `idna` libraries.

### Removed
- Removed `STACKNAME` requirement from `deploy_vars.sh` as it was redundant with independent modules.

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
- Swtiched from INTERNAL_NET varaible to HOME_NET varaible to identify internal network CIDRs
- Changed firewall policy creation to use HOME_NET override feature
- Renamed default_deny.yaml to global_rules.yaml
- Changed the configuration file structure to support new features

### Fixed
- Pytest for firewall_handler library
- Fixed poetry dependency structure so that dev, test, and build dependencies are independent

### Removed
- Pytest tests that failed and need to be rewritten
- INTERNAL_NET varaible as this is not being used.

### 1.0.0 (2024-01-25)

### Added
- Initial release
