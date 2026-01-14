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
	npm run build

test:
	@echo "🧪 Running firewall module tests..."
	npm test

lint:
	@echo "🔍 Running firewall module linting..."
	npm run lint

lint-fix:
	@echo "🔧 Fixing firewall module lint issues..."
	npm run lint-fix

deploy: build
	@echo "🚀 Deploying firewall module..."
	npx cdk deploy --all

clean:
	@echo "🧹 Cleaning firewall module artifacts..."
	npm run clean

update: 
	@echo "📦 Updating firewall module dependencies..."
	npm update

.PHONY: all help build test lint lint-fix deploy clean update