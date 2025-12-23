all: build

help: 
	@echo "Available targets:"
	@echo "  build            - Build all modules"
	@echo "  test             - Run all tests"
	@echo "  deploy           - Deploy all modules"
	@echo "  clean            - Clean all build artifacts"
	@echo "  update           - Update all dependencies"
	@echo "  local            - Complete local development setup (install + setup + start)"
	@echo "  local-setup      - Setup local development environment only"
	@echo "  local-start      - Start LocalStack containers"
	@echo "  local-stop       - Stop LocalStack containers"
	@echo "  local-deploy     - Deploy to LocalStack"
	@echo "  lint             - Run linting on all modules"
	@echo "  integration-test - Run integration tests"
	@echo "  setup-commits    - Setup commit standards enforcement"
	@echo "  commit           - Create a conventional commit interactively"
	@echo "  validate-commit  - Validate the last commit message"

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

local: 
	@echo "Setting up and starting local development environment..."
	@echo "This will install dependencies, setup LocalStack, and configure everything needed for local development."
	npm install
	npm run local:setup
	npm run local:start
	@echo ""
	@echo "✅ Local development environment is ready!"
	@echo "   - LocalStack is running at http://localhost:4566"
	@echo "   - DynamoDB Admin at http://localhost:8001"
	@echo "   - Commit standards are configured"
	@echo ""
	@echo "Next steps:"
	@echo "   make local-deploy    # Deploy to LocalStack"
	@echo "   make commit          # Create conventional commits"

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

.PHONY: all help build test update deploy clean lint local local-setup local-start local-stop local-deploy integration-test setup-commits commit validate-commit