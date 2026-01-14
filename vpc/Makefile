all: build

help: 
	@echo "Available targets for vpc module:"
	@echo ""
	@echo "🏗️  Build & Test Commands:"
	@echo "  build            - Build this module"
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
	@echo "🏗️  Building vpc module..."
	yarn build

test:
	@echo "🧪 Running vpc module tests..."
	yarn test

lint:
	@echo "🔍 Running vpc module linting..."
	yarn lint

lint-fix:
	@echo "🔧 Fixing vpc module lint issues..."
	yarn lint-fix

deploy: build
	@echo "🚀 Deploying vpc module..."
	yarn exec cdk deploy --all

clean:
	@echo "🧹 Cleaning vpc module artifacts..."
	yarn clean

update: 
	@echo "📦 Updating vpc module dependencies..."
	yarn up '*'

.PHONY: all help build test lint lint-fix deploy clean update