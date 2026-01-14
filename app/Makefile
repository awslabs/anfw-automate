all: build

help: 
	@echo "Available targets for app module:"
	@echo ""
	@echo "🏗️  Build & Test Commands:"
	@echo "  build            - Build this module (includes pre-synth)"
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

build: pre-synth
	@echo "🏗️  Building app module..."
	npm run build

test:
	@echo "🧪 Running app module tests..."
	npm test

lint:
	@echo "🔍 Running app module linting..."
	npm run lint

lint-fix:
	@echo "🔧 Fixing app module lint issues..."
	npm run lint-fix

pre-synth:
	@echo "📦 Running pre-synth packaging..."
	bash -e scripts/package.sh

deploy: build
	@echo "🚀 Deploying app module..."
	npx cdk deploy --all

clean:
	@echo "🧹 Cleaning app module artifacts..."
	npm run clean

update: 
	@echo "📦 Updating app module dependencies..."
	npm update

.PHONY: all help build test lint lint-fix pre-synth deploy clean update