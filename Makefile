all: build

# ---------------------------------------------------------------------------
# DVP Configuration
# ---------------------------------------------------------------------------
# Minimum coverage threshold resolved from scripts/velocity/config.toml via the
# coverage-ratchet script. The ratchet rejects any configured value lower than
# the most recently committed threshold (Requirement 3.7).
# Override on the command line: make unit COV_MIN=60
COV_MIN ?= $(shell python3 scripts/velocity/coverage_ratchet.py 2>/dev/null || echo 40)

help: 
	@echo "Available targets:"
	@echo ""
	@echo "🔧 Setup Commands:"
	@echo "  setup            - Setup development environment and git hooks"
	@echo ""
	@echo "🏗️  Build & Test Commands:"
	@echo "  build            - Build all modules (delegates to yarn workspaces)"
	@echo "  test             - Run all tests (delegates to yarn workspaces)"
	@echo "  lint             - Run linting on all modules"
	@echo "  lint-fix         - Fix lint issues on all modules"
	@echo "  format           - Format code with Prettier"
	@echo ""
	@echo "🧪 DVP Gate Commands:"
	@echo "  unit             - Run all unit tests (Python + CDK)"
	@echo "  unit:python      - Run Python unit/property tests with coverage"
	@echo "  unit:cdk         - Run CDK Jest assertion tests"
	@echo "  int              - Run integration tests against INT account"
	@echo "  promote          - Run the promotion flow (unit → INT → prod)"
	@echo "  gate             - Alias for unit (pre-merge gate)"
	@echo ""
	@echo "🔒 Security Commands:"
	@echo "  security:scan    - Run comprehensive security scanning (secrets, Python, Node.js)"
	@echo "  security:secrets - Scan for hardcoded secrets with gitleaks (Docker)"
	@echo "  security:python  - Run Python security scan with bandit"
	@echo "  security:nodejs  - Run Node.js security audit"
	@echo "  security:fix     - Fix security vulnerabilities"
	@echo "  security:fix-force - Force fix vulnerabilities (may break compatibility)"
	@echo ""
	@echo "ℹ️  Note: CDK NAG compliance checks run automatically during 'make build'"
	@echo ""
	@echo "🚀 Deployment Commands:"
	@echo "  deploy           - Deploy all modules to AWS"
	@echo ""
	@echo "📝 Git & Commit Commands:"
	@echo "  commit           - Create a conventional commit interactively"
	@echo "  validate-commit  - Validate the last commit message"
	@echo ""
	@echo "🧹 Utility Commands:"
	@echo "  clean            - Clean all build artifacts"
	@echo "  update           - Update all dependencies"
	@echo ""
	@echo "📦 Module Commands:"
	@echo "  build:<module>   - Build specific module (app, firewall, vpc, shared)"
	@echo "  test:<module>    - Test specific module"
	@echo "  deploy:<module>  - Deploy specific module"

# ---------------------------------------------------------------------------
# DVP Gate Targets
# ---------------------------------------------------------------------------

## Validate coverage ratchet (COV_MIN cannot decrease)
cov-ratchet:
	@echo "🔒 Checking coverage ratchet..."
	@python3 scripts/velocity/coverage_ratchet.py >/dev/null

## Run all unit tests (Python + CDK); emit gate marker on success (fail-closed)
unit:
	@$(MAKE) cov-ratchet
	@$(MAKE) unit:python
	@$(MAKE) unit:cdk
	@echo "🎯 All unit tests passed. Emitting gate marker..."
	@COV=$$(cd app/src && uv run pytest -m "not integration" --cov=. --cov-report=term-missing -q 2>/dev/null | grep -E "^TOTAL\s" | awk '{print $$NF}' | tr -d '%'); \
	if [ -z "$$COV" ]; then COV="0"; fi; \
	python3 scripts/velocity/gate_marker.py --kind unit --coverage "$$COV"

## Run Python unit and property tests with coverage enforcement
unit\:python:
	@echo "🐍 Running Python unit/property tests..."
	cd app/src && uv run pytest -m "not integration" --cov=. --cov-report=term-missing --cov-fail-under=$(COV_MIN)

## Run CDK Jest assertion tests
unit\:cdk:
	@echo "🏗️  Running CDK assertion tests..."
	yarn workspace app test

## Run integration tests against the INT account
int:
	@echo "🔬 Running integration tests..."
	bash scripts/velocity/int-run.sh

## Run the promotion flow (unit → INT → prod)
promote:
	@echo "🚀 Running promotion flow..."
	bash scripts/velocity/promote.sh

## Pre-merge gate (alias for unit)
gate: unit

# ---------------------------------------------------------------------------
# Core build and test commands (delegate to yarn workspaces)
# ---------------------------------------------------------------------------
build:
	@echo "🏗️  Building all modules..."
	yarn build

test:
	@echo "🧪 Running all tests..."
	@for module in shared app firewall vpc; do \
		echo "Testing $$module..."; \
		(cd "$$module" && make test); \
	done

lint:
	@echo "🔍 Running linting on all modules..."
	@for module in shared app firewall vpc; do \
		echo "Linting $$module..."; \
		(cd "$$module" && make lint); \
	done

lint-fix:
	@echo "🔧 Fixing lint issues on all modules..."
	@for module in shared app firewall vpc; do \
		echo "Fixing $$module..."; \
		(cd "$$module" && make lint-fix); \
	done

format:
	@echo "🎨 Formatting code with Prettier..."
	yarn prettier --write "**/*.{ts,js,json,md,yml,yaml}" --ignore-path .prettierignore

# Security commands (pattern rule)
security\:%:
	@case "$*" in \
		scan) \
			echo "🔒 Running comprehensive security scanning..."; \
			./scripts/security-scan.sh all ;; \
		python) \
			echo "🐍 Running Python security scan..."; \
			./scripts/security-scan.sh python ;; \
		nodejs) \
			echo "📦 Running Node.js security audit..."; \
			./scripts/security-scan.sh nodejs ;; \
		secrets) \
			echo "🔐 Scanning for hardcoded secrets with gitleaks..."; \
			if ! command -v docker &> /dev/null; then \
				echo "❌ ERROR: Docker is required for gitleaks"; \
				echo "   Install Docker: https://docs.docker.com/get-docker/"; \
				exit 1; \
			fi; \
			docker run --rm -v "$$(pwd):/path" zricethezav/gitleaks:latest detect --source /path --no-git --config /path/.gitleaks.toml --verbose ;; \
		fix) \
			echo "🔧 Fixing security vulnerabilities..."; \
			echo "📋 Note: Bundled npm dependencies cannot be auto-fixed and require npm updates"; \
			echo ""; \
			for module in . app firewall vpc shared; do \
				if [ -f "$$module/package.json" ]; then \
					echo "  📦 Fixing $$module..."; \
					(cd "$$module" && yarn up '*' --mode=update-lockfile) || true; \
				fi; \
			done; \
			echo ""; \
			echo "✅ Project module security fixes completed!"; \
			echo "ℹ️  If bundled vulnerabilities remain in Yarn itself, update Yarn: corepack prepare yarn@stable --activate" ;; \
		fix-force) \
			echo "🔧 Force fixing security vulnerabilities (may introduce breaking changes)..."; \
			echo "⚠️  This will attempt to force-fix all vulnerabilities, including major version updates"; \
			echo ""; \
			for module in . app firewall vpc shared; do \
				if [ -f "$$module/package.json" ]; then \
					echo "  📦 Force fixing $$module..."; \
					(cd "$$module" && yarn up '*' --force) || true; \
				fi; \
			done; \
			echo ""; \
			echo "⚠️  Force fixes completed - review changes carefully!" ;; \
		*) \
			echo "Unknown security target: $*"; \
			echo "Available: scan, python, nodejs, secrets, fix, fix-force"; \
			exit 1 ;; \
	esac

# Module-specific commands
build\:%:
	@echo "🏗️  Building $* module..."
	@cd $* && make build

test\:%:
	@echo "🧪 Testing $* module..."
	@cd $* && make test

deploy\:%:
	@echo "🚀 Deploying $* module..."
	@cd $* && make deploy

# Setup and environment commands
setup:
	@echo "🔧 Setting up development environment..."
	corepack enable
	yarn install
	yarn prepare
	@echo "✅ Development environment ready!"
	@echo ""
	@echo "ℹ️  Note: Docker is required for gitleaks (make security:secrets)"

# Git and commit commands
commit:
	@echo "📝 Creating a conventional commit..."
	@echo "ℹ️  Note: Pre-commit hooks will run linting and security scans automatically"
	@echo ""
	@yarn commit

validate-commit:
	@echo "✅ Validating last commit message..."
	git log -1 --pretty=format:"%s" | yarn exec commitlint

# Deployment commands
deploy: build	
	@echo "🚀 Deploying all modules..."
	@for module in app firewall vpc; do \
		echo "Deploying $$module..."; \
		(cd "$$module" && make deploy); \
	done

# Utility commands
clean:
	@echo "🧹 Cleaning all artifacts..."
	yarn clean

update: 
	@echo "📦 Updating all dependencies..."
	yarn up '*'

.PHONY: all help build test lint lint-fix format setup commit validate-commit deploy clean update unit unit\:python unit\:cdk int promote gate cov-ratchet