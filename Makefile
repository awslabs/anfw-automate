all: build

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
	@echo "🔒 Security Commands:"
	@echo "  security:scan    - Run comprehensive security scanning"
	@echo "  security:python  - Run Python security scan with bandit"
	@echo "  security:nodejs  - Run Node.js security audit"
	@echo "  security:cdk     - Run CDK NAG compliance checks"
	@echo "  security:secrets - Scan for hardcoded secrets with gitleaks"
	@echo "  security:fix     - Fix security vulnerabilities"
	@echo "  security:fix-force - Force fix vulnerabilities (may break compatibility)"
	@echo "  security:status  - Show security vulnerability status summary"
	@echo "  audit            - Run yarn audit on all modules"
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

# Core build and test commands (delegate to yarn workspaces)
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
	yarn prettier --write "**/*.{ts,js,json,md,yml,yaml}" --ignore-path .gitignore

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
		cdk) \
			echo "☁️  Running CDK NAG compliance checks..."; \
			./scripts/security-scan.sh cdk ;; \
		secrets) \
			echo "🔐 Scanning for hardcoded secrets..."; \
			./scripts/security-scan.sh secrets ;; \
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
		status) \
			echo "🔍 Security vulnerability status summary..."; \
			echo ""; \
			has_issues=0; \
			for module in . app firewall vpc shared; do \
				if [ -f "$$module/package.json" ]; then \
					echo "📦 Checking $$module..."; \
					cd "$$module"; \
					if yarn npm audit --severity moderate 2>/dev/null | grep -q "No audit suggestions"; then \
						echo "  ✅ No vulnerabilities found"; \
					else \
						echo "  ⚠️  Vulnerabilities detected"; \
						has_issues=1; \
					fi; \
					cd - > /dev/null; \
				fi; \
			done; \
			echo ""; \
			if [ $$has_issues -eq 0 ]; then \
				echo "🎉 All clear! No security vulnerabilities found."; \
			else \
				echo "⚠️  Vulnerabilities found. Run 'make security:fix' to resolve."; \
				echo "   For details: make security:nodejs"; \
			fi ;; \
		*) \
			echo "Unknown security target: $*"; \
			echo "Available: scan, python, nodejs, cdk, secrets, fix, fix-force, status"; \
			exit 1 ;; \
	esac

audit:
	@echo "🔍 Running security audit on all modules..."
	./scripts/security-scan.sh nodejs

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

.PHONY: all help build test lint lint-fix format audit setup commit validate-commit deploy clean update