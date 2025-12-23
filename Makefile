all: build

help: 
	@echo "Available targets:"
	@echo "  build            - Build all modules"
	@echo "  test             - Run all tests"
	@echo "  deploy           - Deploy all modules"
	@echo "  clean            - Clean all build artifacts"
	@echo "  update           - Update all dependencies"
	@echo "  local            - Setup and start local development environment"
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

local: local-setup local-start

local-setup:
	@echo "Setting up local development environment..."
	npm run local:setup

local-start:
	@echo "Starting local development environment..."
	npm run local:start

local-stop:
	@echo "Stopping local development environment..."
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