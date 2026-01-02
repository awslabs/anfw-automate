all: build

help: 
	@echo "Available targets:"
	@echo ""
	@echo "🏗️  Build & Test Commands:"
	@echo "  build            - Build this module (includes pre-synth and comprehensive build)"
	@echo "  pre-synth        - Package source code for CDK synthesis"
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

build: pre-synth
	@echo "Building app module with comprehensive build process..."
	bash -e ../scripts/build.sh

test:
	@echo "Running app module tests..."
	npm test

lint:
	@echo "Running app module linting..."
	npm run lint

lint-fix:
	@echo "Fixing app module lint issues..."
	npm run lint-fix

update: 
	@echo "Updating app module dependencies..."
	bash -e ../scripts/update-packages.sh

pre-synth:
	@echo "Running pre-synth packaging..."
	bash -e scripts/package.sh

deploy: build
	@echo "Deploying app module..."
	cdk deploy --all

clean:
	@echo "Cleaning app module artifacts..."
	git clean -fdx

.PHONY: all help build test lint lint-fix update pre-synth deploy clean