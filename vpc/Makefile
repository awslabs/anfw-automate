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
	npm run build

test:
	@echo "🧪 Running vpc module tests..."
	npm test

lint:
	@echo "🔍 Running vpc module linting..."
	npm run lint

lint-fix:
	@echo "🔧 Fixing vpc module lint issues..."
	npm run lint-fix

deploy: build
	@echo "🚀 Deploying vpc module..."
	npx cdk deploy --all

clean:
	@echo "🧹 Cleaning vpc module artifacts..."
	npm run clean

update: 
	@echo "📦 Updating vpc module dependencies..."
	npm update

.PHONY: all help build test lint lint-fix deploy clean update