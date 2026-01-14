all: build

help: 
	@echo "Available targets for shared module:"
	@echo ""
	@echo "🏗️  Build & Test Commands:"
	@echo "  build            - Build this module (TypeScript compilation)"
	@echo "  test             - Run tests"
	@echo "  lint             - Run linting"
	@echo "  lint-fix         - Fix lint issues"
	@echo ""
	@echo "🧹 Utility Commands:"
	@echo "  clean            - Clean build artifacts"
	@echo "  update           - Update dependencies"
	@echo ""
	@echo "Note: Shared module is a library (no deployment)"

build: 
	@echo "🏗️  Building shared module..."
	yarn build

test:
	@echo "🧪 Running shared module tests..."
	yarn test

lint:
	@echo "🔍 Running shared module linting..."
	yarn lint

lint-fix:
	@echo "🔧 Fixing shared module lint issues..."
	yarn lint-fix

clean:
	@echo "🧹 Cleaning shared module artifacts..."
	yarn clean

update: 
	@echo "📦 Updating shared module dependencies..."
	yarn up '*'

.PHONY: all help build test lint lint-fix clean update