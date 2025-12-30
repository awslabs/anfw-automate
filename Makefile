all: build

help: 
	@echo "Available targets:"
	@echo ""
	@echo "🔧 Setup Commands:"
	@echo "  local            - Setup and start LocalStack (requires Docker)"
	@echo ""
	@echo "🏗️  Build & Test Commands:"
	@echo "  build            - Build all modules"
	@echo "  test             - Run all tests"
	@echo "  lint             - Run linting on all modules"
	@echo "  lint-fix         - Fix all lint issues automatically"
	@echo "  integration-test - Run integration tests"
	@echo ""
	@echo "🚀 Deployment Commands:"
	@echo "  deploy           - Deploy all modules to AWS"
	@echo "  local-deploy     - Deploy to LocalStack"
	@echo ""
	@echo "🐳 LocalStack Commands (requires Docker):"
	@echo "  local-setup      - Setup local development environment only"
	@echo "  local-start      - Start LocalStack containers"
	@echo "  local-stop       - Stop LocalStack containers"
	@echo ""
	@echo "📝 Git & Commit Commands:"
	@echo "  commit           - Create a conventional commit interactively"
	@echo "  validate-commit  - Validate the last commit message"
	@echo "  setup-commits    - Setup commit standards enforcement"
	@echo ""
	@echo "🧹 Utility Commands:"
	@echo "  clean            - Clean all build artifacts"
	@echo "  update           - Update all dependencies"

build: 
	@echo "Building all modules..."
	npm run build

test:
	@echo "Running all tests..."
	npm test

update: 
	@echo "Updating all dependencies..."
	npm run update

deploy: build	
	@echo "Deploying all modules..."
	cdk deploy --all

clean:
	@echo "Cleaning all artifacts..."
	npm run clean

lint:
	@echo "Running linting..."
	npm run lint

lint-fix:
	@echo "Fixing all lint issues..."
	@echo "Running ESLint with --fix on all workspaces..."
	npm run lint || true
	@echo "✅ Lint fixes applied!"

local: 
	@echo "🚀 Setting up LocalStack environment..."
	@echo ""
	@echo "⚠️  This requires Docker and Docker Compose to be installed!"
	@echo ""
	@echo "Checking Docker availability..."
	@docker --version || (echo "❌ Docker not found. Please install Docker first." && exit 1)
	@docker-compose --version || (echo "❌ Docker Compose not found. Please install Docker Compose first." && exit 1)
	@echo "✅ Docker requirements satisfied"
	@echo ""
	@echo "Setting up LocalStack configuration and starting containers..."
	npm run local:setup
	npm run local:start
	@echo ""
	@echo "✅ LocalStack environment is ready!"
	@echo "   - LocalStack is running at http://localhost:4566"
	@echo "   - DynamoDB Admin at http://localhost:8001"
	@echo ""
	@echo "Next steps:"
	@echo "   make local-deploy    # Deploy to LocalStack"
	@echo "   make local-stop      # Stop LocalStack when done"

local-setup:
	@echo "Setting up local development environment..."
	npm install
	npm run local:setup

local-start:
	@echo "Starting LocalStack..."
	npm run local:start

local-stop:
	@echo "Stopping LocalStack..."
	npm run local:stop

local-deploy:
	@echo "Deploying to local environment..."
	npm run deploy:local

integration-test:
	@echo "Running integration tests..."
	npm run test:integration

setup-commits:
	@echo "Setting up commit standards..."
	chmod +x scripts/setup-commit-standards.sh
	scripts/setup-commit-standards.sh

commit:
	@echo "Creating a conventional commit..."
	npm run commit

validate-commit:
	@echo "Validating last commit message..."
	git log -1 --pretty=format:"%s" | npx commitlint

.PHONY: all help build test update deploy clean lint lint-fix local local-setup local-start local-stop local-deploy integration-test setup-commits commit validate-commit