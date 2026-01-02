all: build

help: 
	@echo "Available targets:"
	@echo ""
	@echo "🏗️  Build & Test Commands:"
	@echo "  build            - Build this module (TypeScript compilation only)"
	@echo "  test             - Run tests for this module"
	@echo "  lint             - Run linting for this module"
	@echo "  lint-fix         - Fix lint issues for this module"
	@echo ""
	@echo "🧹 Utility Commands:"
	@echo "  clean            - Clean build artifacts"
	@echo "  update           - Update dependencies"
	@echo ""
	@echo "Note: Shared module uses simple TypeScript build (no Python/CDK components)"

build: 
	@echo "Building shared module (TypeScript compilation)..."
	npm run build

test:
	@echo "Running shared module tests..."
	npm test

lint:
	@echo "Running shared module linting..."
	npm run lint

lint-fix:
	@echo "Fixing shared module lint issues..."
	npm run lint-fix

update: 
	@echo "Updating shared module dependencies..."
	bash -e ../scripts/update-packages.sh

clean:
	@echo "Cleaning shared module artifacts..."
	npm run clean

.PHONY: all help build test lint lint-fix update clean