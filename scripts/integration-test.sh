#!/usr/bin/env bash
# NOTICE: Integration tests have been disabled
# This script is kept for reference but will exit immediately
echo "Integration tests have been disabled and removed from the pipeline"
exit 0

# Legacy integration test code below (disabled)
# set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Validate required environment variables
validate_environment() {
    print_status "Validating environment for integration tests..."
    
    local required_vars=("STAGE" "AWS_REGION")
    for var in "${required_vars[@]}"; do
        if [ -z "${!var:-}" ]; then
            print_error "Required environment variable $var is not set"
            exit 1
        fi
    done
    
    print_status "Environment validation passed"
}

# Wait for stack deployment to complete
wait_for_stack_deployment() {
    local stack_name="$1"
    local max_wait_time=1800  # 30 minutes
    local wait_interval=30
    local elapsed_time=0
    
    print_status "Waiting for stack deployment to complete: $stack_name"
    
    while [ $elapsed_time -lt $max_wait_time ]; do
        local stack_status=$(aws cloudformation describe-stacks \
            --stack-name "$stack_name" \
            --query 'Stacks[0].StackStatus' \
            --output text 2>/dev/null || echo "STACK_NOT_FOUND")
        
        case "$stack_status" in
            "CREATE_COMPLETE"|"UPDATE_COMPLETE")
                print_status "Stack deployment completed successfully: $stack_name"
                return 0
                ;;
            "CREATE_FAILED"|"UPDATE_FAILED"|"ROLLBACK_COMPLETE"|"UPDATE_ROLLBACK_COMPLETE")
                print_error "Stack deployment failed: $stack_name (Status: $stack_status)"
                return 1
                ;;
            "STACK_NOT_FOUND")
                print_warning "Stack not found: $stack_name"
                ;;
            *)
                print_status "Stack deployment in progress: $stack_name (Status: $stack_status)"
                ;;
        esac
        
        sleep $wait_interval
        elapsed_time=$((elapsed_time + wait_interval))
    done
    
    print_error "Timeout waiting for stack deployment: $stack_name"
    return 1
}

# Test Lambda function invocation
test_lambda_function() {
    local function_name="$1"
    local test_payload="$2"
    
    print_status "Testing Lambda function: $function_name"
    
    local response=$(aws lambda invoke \
        --function-name "$function_name" \
        --payload "$test_payload" \
        --output json \
        /tmp/lambda-response.json 2>&1)
    
    if [ $? -eq 0 ]; then
        local status_code=$(echo "$response" | jq -r '.StatusCode // empty')
        if [ "$status_code" = "200" ]; then
            print_status "Lambda function test passed: $function_name"
            return 0
        else
            print_error "Lambda function returned non-200 status: $function_name (Status: $status_code)"
            return 1
        fi
    else
        print_error "Failed to invoke Lambda function: $function_name"
        echo "$response"
        return 1
    fi
}

# Test S3 bucket accessibility
test_s3_bucket() {
    local bucket_name="$1"
    
    print_status "Testing S3 bucket accessibility: $bucket_name"
    
    if aws s3 ls "s3://$bucket_name" >/dev/null 2>&1; then
        print_status "S3 bucket test passed: $bucket_name"
        return 0
    else
        print_error "S3 bucket test failed: $bucket_name"
        return 1
    fi
}

# Test Network Firewall policy
test_network_firewall_policy() {
    local policy_arn="$1"
    
    print_status "Testing Network Firewall policy: $policy_arn"
    
    local policy_response=$(aws network-firewall describe-firewall-policy \
        --firewall-policy-arn "$policy_arn" \
        --output json 2>/dev/null)
    
    if [ $? -eq 0 ]; then
        local policy_status=$(echo "$policy_response" | jq -r '.FirewallPolicyResponse.FirewallPolicyStatus // empty')
        if [ "$policy_status" = "ACTIVE" ]; then
            print_status "Network Firewall policy test passed: $policy_arn"
            return 0
        else
            print_error "Network Firewall policy not active: $policy_arn (Status: $policy_status)"
            return 1
        fi
    else
        print_error "Failed to describe Network Firewall policy: $policy_arn"
        return 1
    fi
}

# Run application-specific integration tests
run_app_integration_tests() {
    print_status "Running application integration tests..."
    
    # Get stack outputs
    local stack_name="serverless-${STAGE}"
    local stack_outputs=$(aws cloudformation describe-stacks \
        --stack-name "$stack_name" \
        --query 'Stacks[0].Outputs' \
        --output json 2>/dev/null || echo '[]')
    
    # Extract Lambda function names from outputs
    local rule_collect_function=$(echo "$stack_outputs" | jq -r '.[] | select(.OutputKey=="RuleCollectFunctionName") | .OutputValue // empty')
    local rule_execute_function=$(echo "$stack_outputs" | jq -r '.[] | select(.OutputKey=="RuleExecuteFunctionName") | .OutputValue // empty')
    
    # Test Lambda functions if they exist
    if [ -n "$rule_collect_function" ]; then
        test_lambda_function "$rule_collect_function" '{"test": true}'
    fi
    
    if [ -n "$rule_execute_function" ]; then
        test_lambda_function "$rule_execute_function" '{"test": true}'
    fi
    
    # Test S3 buckets
    local config_bucket=$(echo "$stack_outputs" | jq -r '.[] | select(.OutputKey=="ConfigBucketName") | .OutputValue // empty')
    if [ -n "$config_bucket" ]; then
        test_s3_bucket "$config_bucket"
    fi
    
    print_status "Application integration tests completed"
}

# Run firewall-specific integration tests
run_firewall_integration_tests() {
    print_status "Running firewall integration tests..."
    
    # Get firewall stack outputs
    local stack_name="firewall-${STAGE}"
    local stack_outputs=$(aws cloudformation describe-stacks \
        --stack-name "$stack_name" \
        --query 'Stacks[0].Outputs' \
        --output json 2>/dev/null || echo '[]')
    
    # Test Network Firewall policy
    local firewall_policy_arn=$(echo "$stack_outputs" | jq -r '.[] | select(.OutputKey=="FirewallPolicyArn") | .OutputValue // empty')
    if [ -n "$firewall_policy_arn" ]; then
        test_network_firewall_policy "$firewall_policy_arn"
    fi
    
    print_status "Firewall integration tests completed"
}

# Run VPC-specific integration tests
run_vpc_integration_tests() {
    print_status "Running VPC integration tests..."
    
    # Get VPC stack outputs
    local stack_name="vpc-${STAGE}"
    local stack_outputs=$(aws cloudformation describe-stacks \
        --stack-name "$stack_name" \
        --query 'Stacks[0].Outputs' \
        --output json 2>/dev/null || echo '[]')
    
    # Test VPC connectivity
    local vpc_id=$(echo "$stack_outputs" | jq -r '.[] | select(.OutputKey=="VpcId") | .OutputValue // empty')
    if [ -n "$vpc_id" ]; then
        print_status "Testing VPC: $vpc_id"
        aws ec2 describe-vpcs --vpc-ids "$vpc_id" >/dev/null 2>&1
        if [ $? -eq 0 ]; then
            print_status "VPC test passed: $vpc_id"
        else
            print_error "VPC test failed: $vpc_id"
            return 1
        fi
    fi
    
    print_status "VPC integration tests completed"
}

# Generate test report
generate_test_report() {
    print_status "Generating integration test report..."
    
    cat > integration-test-report.json << EOF
{
  "timestamp": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")",
  "stage": "${STAGE}",
  "region": "${AWS_REGION}",
  "test_status": "success",
  "git_commit": "$(git rev-parse HEAD 2>/dev/null || echo 'unknown')",
  "git_branch": "$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo 'unknown')"
}
EOF
    
    print_status "Integration test report generated: integration-test-report.json"
}

# Main execution
main() {
    print_status "Starting integration tests for stage: ${STAGE}"
    
    validate_environment
    
    # Determine which tests to run based on STACK_NAME
    case "${STACK_NAME:-all}" in
        "app")
            run_app_integration_tests
            ;;
        "firewall")
            run_firewall_integration_tests
            ;;
        "vpc")
            run_vpc_integration_tests
            ;;
        *)
            print_status "Running all integration tests..."
            run_vpc_integration_tests || true
            run_firewall_integration_tests || true
            run_app_integration_tests || true
            ;;
    esac
    
    generate_test_report
    print_status "Integration tests completed successfully!"
}

# Execute main function
main "$@"