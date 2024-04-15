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

### Fixed
- Updated vulnerable `idna` libraries.

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
