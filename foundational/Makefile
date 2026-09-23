all: build

help:
	@echo "Available targets for foundational module:"
	@echo ""
	@echo "🏗️  Build & Test Commands:"
	@echo "  build            - Build this module (tsc + cdk synth)"
	@echo "  test             - Run tests"
	@echo "  lint             - Run linting"
	@echo "  lint-fix         - Fix lint issues"
	@echo ""
	@echo "🚀 Deployment Commands:"
	@echo "  deploy           - Deploy to AWS"
	@echo ""
	@echo "🧹 Utility Commands:"
	@echo "  clean            - Clean build artifacts"
	@echo "  update           - Update dependencies"

build:
	@echo "🏗️  Building foundational module..."
	yarn build

test:
	@echo "🧪 Running foundational module tests..."
	yarn test

lint:
	@echo "🔍 Running foundational module linting..."
	yarn lint

lint-fix:
	@echo "🔧 Fixing foundational module lint issues..."
	yarn lint-fix

deploy: build
	@echo "🚀 Deploying foundational module..."
	yarn exec cdk deploy --all

clean:
	@echo "🧹 Cleaning foundational module artifacts..."
	yarn clean

update:
	@echo "📦 Updating foundational module dependencies..."
	yarn up '*'

.PHONY: all help build test lint lint-fix deploy clean update
