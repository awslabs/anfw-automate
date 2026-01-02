all: build

help: 
	@echo "Available targets:"
	@echo ""
	@echo "🏗️  Build & Test Commands:"
	@echo "  build            - Build this module with comprehensive build process"
	@echo "  test             - Run tests for this module"
	@echo "  lint             - Run linting for this module"
	@echo "  lint-fix         - Fix lint issues for this module"
	@echo ""
	@echo "🚀 Deployment Commands:"
	@echo "  deploy           - Deploy this module to AWS"
	@echo ""
	@echo "🧹 Utility Commands:"
	@echo "  clean            - Clean build artifacts"
	@echo "  update           - Update dependencies"

build: 
	@echo "Building firewall module with comprehensive build process..."
	bash -e ../scripts/build.sh

test:
	@echo "Running firewall module tests..."
	npm test

lint:
	@echo "Running firewall module linting..."
	npm run lint

lint-fix:
	@echo "Fixing firewall module lint issues..."
	npm run lint-fix

update: 
	@echo "Updating firewall module dependencies..."
	bash -e ../scripts/update-packages.sh

deploy: build
	@echo "Deploying firewall module..."
	cdk deploy --all

clean:
	@echo "Cleaning firewall module artifacts..."
	git clean -fdx

.PHONY: all help build test lint lint-fix update deploy clean