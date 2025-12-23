# Integration Tests

This directory contains integration tests that validate the functionality of deployed Lambda functions and AWS resources.

## Test Structure

- `test_app_lambdas.py` - Tests for application Lambda functions
- `test_firewall_lambdas.py` - Tests for firewall Lambda functions  
- `test_vpc_resources.py` - Tests for VPC resources
- `conftest.py` - Shared test configuration and fixtures
- `utils/` - Test utilities and helpers

## Running Tests

### Prerequisites

1. Ensure the application is deployed to the target environment
2. Configure AWS credentials for the test environment
3. Install test dependencies: `pip install -r requirements.txt`

### Local Testing (with LocalStack)

```bash
# Start LocalStack
docker-compose -f docker-compose.local.yml up -d

# Source local environment
source deploy_vars.local.sh

# Deploy to LocalStack
make deploy

# Run integration tests
pytest tests/integration/ -v
```

### Environment Testing

```bash
# Set environment variables
export STAGE=dev  # or int, prod
export AWS_REGION=us-east-1

# Run tests
pytest tests/integration/ -v --stage=$STAGE
```

## Test Configuration

Tests use the following environment variables:

- `STAGE` - Deployment stage (local, dev, int, prod)
- `AWS_REGION` - AWS region
- `AWS_ENDPOINT_URL` - LocalStack endpoint (for local testing)

## Writing New Tests

1. Create test files following the pattern `test_*.py`
2. Use the shared fixtures from `conftest.py`
3. Follow the AAA pattern (Arrange, Act, Assert)
4. Include proper cleanup in test teardown
5. Add appropriate test markers for different environments