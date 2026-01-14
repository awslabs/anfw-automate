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
	@echo "  security-scan    - Run comprehensive security scanning"
	@echo "  security-python  - Run Python security scan with bandit"
	@echo "  security-nodejs  - Run Node.js security audit"
	@echo "  security-cdk     - Run CDK NAG compliance checks"
	@echo "  security-containers - Run container security scanning"
	@echo "  security-fix     - Fix security vulnerabilities"
	@echo "  security-fix-force - Force fix vulnerabilities (may break compatibility)"
	@echo "  security-status  - Show security vulnerability status summary"
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
	yarn test

lint:
	@echo "🔍 Running linting on all modules..."
	yarn lint

lint-fix:
	@echo "🔧 Fixing lint issues on all modules..."
	yarn lint-fix

format:
	@echo "🎨 Formatting code with Prettier..."
	yarn prettier --write "**/*.{ts,js,json,md,yml,yaml}" --ignore-path .gitignore

# Security commands
security-scan:
	@echo "🔒 Running comprehensive security scanning..."
	./scripts/security-scan.sh all

security-python:
	@echo "🐍 Running Python security scan..."
	./scripts/security-scan.sh python

security-nodejs:
	@echo "📦 Running Node.js security audit..."
	./scripts/security-scan.sh nodejs

security-cdk:
	@echo "☁️  Running CDK NAG compliance checks..."
	./scripts/security-scan.sh cdk

security-containers:
	@echo "🐳 Running container security scanning..."
	./scripts/security-scan.sh containers

security-fix:
	@echo "🔧 Fixing security vulnerabilities..."
	@echo "📋 Note: Bundled npm dependencies cannot be auto-fixed and require npm updates"
	@echo ""
	@for module in . app firewall vpc shared; do \
		if [ -f "$$module/package.json" ]; then \
			echo "  📦 Fixing $$module..."; \
			(cd "$$module" && yarn up '*' --mode=update-lockfile) || true; \
		fi; \
	done
	@echo ""
	@echo "✅ Project module security fixes completed!"
	@echo "ℹ️  If bundled npm vulnerabilities remain, consider updating npm: npm install -g npm@latest"

security-fix-force:
	@echo "🔧 Force fixing security vulnerabilities (may introduce breaking changes)..."
	@echo "⚠️  This will attempt to force-fix all vulnerabilities, including major version updates"
	@echo ""
	@for module in . app firewall vpc shared; do \
		if [ -f "$$module/package.json" ]; then \
			echo "  📦 Force fixing $$module..."; \
			(cd "$$module" && yarn up '*' --force) || true; \
		fi; \
	done
	@echo ""
	@echo "⚠️  Force fixes completed - review changes carefully!"

security-status:
	@echo "🔍 Security vulnerability status summary..."
	@echo ""
	@bundled_issues=0; \
	project_issues=0; \
	for module in . app firewall vpc shared; do \
		if [ -f "$$module/package.json" ]; then \
			echo "📦 Checking $$module..."; \
			cd "$$module"; \
			if npm audit --audit-level=moderate 2>/dev/null | grep -q "found 0 vulnerabilities"; then \
				echo "  ✅ No vulnerabilities in project dependencies"; \
			else \
				if npm audit --audit-level=moderate 2>/dev/null | grep -q "bundled dependency"; then \
					echo "  ⚠️  Bundled npm vulnerabilities detected (not fixable via npm audit fix)"; \
					bundled_issues=1; \
				else \
					echo "  ❌ Project vulnerabilities detected"; \
					project_issues=1; \
				fi; \
			fi; \
			cd - > /dev/null; \
		fi; \
	done; \
	echo ""; \
	if [ $$project_issues -eq 0 ] && [ $$bundled_issues -eq 0 ]; then \
		echo "🎉 All clear! No security vulnerabilities found."; \
	elif [ $$project_issues -eq 0 ] && [ $$bundled_issues -eq 1 ]; then \
		echo "✅ Your project is secure! Only bundled npm vulnerabilities detected."; \
		echo "💡 To fix bundled vulnerabilities: npm install -g npm@latest"; \
	else \
		echo "⚠️  Project vulnerabilities found. Run 'make security-fix' to resolve."; \
	fi

audit:
	@echo "🔍 Running security audit on all modules..."
	yarn security:audit

security-suppress:
	@echo "🔇 Managing vulnerability suppressions..."
	@echo "Current suppressions in .npmauditrc:"
	@if [ -f ".npmauditrc" ]; then \
		cat .npmauditrc | jq -r '.advisories | to_entries[] | "  \(.key): \(.value.reason)"' 2>/dev/null || echo "  (Invalid JSON format)"; \
	else \
		echo "  No suppressions configured"; \
	fi
	@echo ""
	@echo "To suppress a vulnerability:"
	@echo "  1. Run 'npm audit --json' to get advisory IDs"
	@echo "  2. Edit .npmauditrc to add the advisory ID with reason and expiry"
	@echo "  3. Run 'make audit-clean' to verify suppression works"

security-unsuppress:
	@echo "🔊 Removing all vulnerability suppressions..."
	@if [ -f ".npmauditrc" ]; then \
		echo "Backing up current .npmauditrc to .npmauditrc.backup"; \
		cp .npmauditrc .npmauditrc.backup; \
		rm .npmauditrc; \
		echo "✅ All suppressions removed"; \
	else \
		echo "No suppressions to remove"; \
	fi

audit-clean:
	@echo "🔍 Running npm audit with suppressions applied..."
	@echo ""
	@for module in . app firewall vpc shared; do \
		if [ -f "$module/package.json" ]; then \
			echo "📦 Auditing $module..."; \
			cd "$module"; \
			if [ -f "../.npmauditrc" ] && [ "$module" != "." ]; then \
				cp ../.npmauditrc .npmauditrc 2>/dev/null || true; \
			fi; \
			npm audit --audit-level=moderate 2>/dev/null || echo "  ⚠️  Vulnerabilities found (check if suppressed)"; \
			if [ -f ".npmauditrc" ] && [ "$module" != "." ]; then \
				rm .npmauditrc 2>/dev/null || true; \
			fi; \
			cd - > /dev/null; \
		fi; \
	done
	@echo ""
	@echo "✅ Audit completed with suppressions applied"

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
	git log -1 --pretty=format:"%s" | yarn commitlint

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

.PHONY: all help build test lint lint-fix format security-scan security-python security-nodejs security-cdk security-containers security-fix security-fix-force security-status security-suppress security-unsuppress audit audit-clean setup commit validate-commit deploy clean update