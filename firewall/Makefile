all: build

help: 
	@echo "Available targets for firewall module:"
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
	@echo "🏗️  Building firewall module..."
	yarn build

test:
	@echo "🧪 Running firewall module tests..."
	yarn test

lint:
	@echo "🔍 Running firewall module linting..."
	yarn lint

lint-fix:
	@echo "🔧 Fixing firewall module lint issues..."
	yarn lint-fix

deploy: build
	@echo "🚀 Deploying firewall module..."
	yarn exec cdk deploy --all

clean:
	@echo "🧹 Cleaning firewall module artifacts..."
	yarn clean

update: 
	@echo "📦 Updating firewall module dependencies..."
	yarn up '*'

.PHONY: all help build test lint lint-fix deploy clean update