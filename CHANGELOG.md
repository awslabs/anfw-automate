# Changelog

All notable changes to this project will be documented in this file. See [standard-version](https://github.com/conventional-changelog/standard-version) for commit guidelines.

### 1.0.0 (2024-03-11)
### Added
- Support for both STRICT and ACTION order in AWS Network Firewall
- JSON Schema Validation for all configuration files
- Enforced pytest execution on each build
- Configuration to provide AWS Network Firewall ARN to attach the rule groups.
- Decoupled firewall policy from the code

### Changed
- Swtiched from INTERNAL_NET varaible to HOME_NET varaible to identify internal network CIDRs
- Changed firewall policy creation to use HOME_NET override feature

### Fixed
- Pytest for firewall_handler library.

### Removed
- Pytest tests that failed and need to be rewritten
- INTERNAL_NET varaible as this is not being used.


### 0.9.0 (2024-01-25)

### Added
- Initial release
