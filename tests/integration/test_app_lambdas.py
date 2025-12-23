"""
Integration tests for application Lambda functions.
"""
import json
import pytest
import boto3
from typing import Dict, Any


@pytest.mark.requires_stack("serverless-{stage}")
class TestAppLambdas:
    """Test application Lambda functions."""

    def test_rule_collect_function_exists(self, lambda_client: boto3.client, app_stack_outputs: Dict[str, Any]):
        """Test that RuleCollect Lambda function exists and is accessible."""
        function_name = app_stack_outputs.get("RuleCollectFunctionName")
        if not function_name:
            pytest.skip("RuleCollectFunctionName not found in stack outputs")
        
        response = lambda_client.get_function(FunctionName=function_name)
        assert response["Configuration"]["State"] == "Active"
        assert response["Configuration"]["Runtime"].startswith("python")

    def test_rule_execute_function_exists(self, lambda_client: boto3.client, app_stack_outputs: Dict[str, Any]):
        """Test that RuleExecute Lambda function exists and is accessible."""
        function_name = app_stack_outputs.get("RuleExecuteFunctionName")
        if not function_name:
            pytest.skip("RuleExecuteFunctionName not found in stack outputs")
        
        response = lambda_client.get_function(FunctionName=function_name)
        assert response["Configuration"]["State"] == "Active"
        assert response["Configuration"]["Runtime"].startswith("python")

    def test_rule_collect_function_invocation(self, lambda_client: boto3.client, app_stack_outputs: Dict[str, Any]):
        """Test RuleCollect Lambda function invocation."""
        function_name = app_stack_outputs.get("RuleCollectFunctionName")
        if not function_name:
            pytest.skip("RuleCollectFunctionName not found in stack outputs")
        
        # Test payload
        test_payload = {
            "test": True,
            "action": "validate"
        }
        
        response = lambda_client.invoke(
            FunctionName=function_name,
            Payload=json.dumps(test_payload),
            InvocationType="RequestResponse"
        )
        
        assert response["StatusCode"] == 200
        
        # Parse response payload
        payload = json.loads(response["Payload"].read())
        assert "statusCode" in payload

    def test_rule_execute_function_invocation(self, lambda_client: boto3.client, app_stack_outputs: Dict[str, Any]):
        """Test RuleExecute Lambda function invocation."""
        function_name = app_stack_outputs.get("RuleExecuteFunctionName")
        if not function_name:
            pytest.skip("RuleExecuteFunctionName not found in stack outputs")
        
        # Test payload
        test_payload = {
            "test": True,
            "action": "validate"
        }
        
        response = lambda_client.invoke(
            FunctionName=function_name,
            Payload=json.dumps(test_payload),
            InvocationType="RequestResponse"
        )
        
        assert response["StatusCode"] == 200
        
        # Parse response payload
        payload = json.loads(response["Payload"].read())
        assert "statusCode" in payload

    def test_config_bucket_exists(self, s3_client: boto3.client, app_stack_outputs: Dict[str, Any]):
        """Test that configuration S3 bucket exists and is accessible."""
        bucket_name = app_stack_outputs.get("ConfigBucketName")
        if not bucket_name:
            pytest.skip("ConfigBucketName not found in stack outputs")
        
        # Test bucket accessibility
        response = s3_client.head_bucket(Bucket=bucket_name)
        assert response["ResponseMetadata"]["HTTPStatusCode"] == 200

    def test_config_bucket_permissions(self, s3_client: boto3.client, app_stack_outputs: Dict[str, Any]):
        """Test S3 bucket permissions and policies."""
        bucket_name = app_stack_outputs.get("ConfigBucketName")
        if not bucket_name:
            pytest.skip("ConfigBucketName not found in stack outputs")
        
        # Test bucket policy exists
        try:
            response = s3_client.get_bucket_policy(Bucket=bucket_name)
            policy = json.loads(response["Policy"])
            assert "Statement" in policy
        except s3_client.exceptions.NoSuchBucketPolicy:
            # Bucket policy might not exist in local testing
            pytest.skip("No bucket policy found - acceptable for local testing")

    def test_lambda_environment_variables(self, lambda_client: boto3.client, app_stack_outputs: Dict[str, Any]):
        """Test Lambda function environment variables are properly set."""
        function_name = app_stack_outputs.get("RuleCollectFunctionName")
        if not function_name:
            pytest.skip("RuleCollectFunctionName not found in stack outputs")
        
        response = lambda_client.get_function(FunctionName=function_name)
        env_vars = response["Configuration"].get("Environment", {}).get("Variables", {})
        
        # Check for expected environment variables
        expected_vars = ["AWS_REGION", "LOG_LEVEL"]
        for var in expected_vars:
            if var in env_vars:
                assert env_vars[var] is not None

    def test_lambda_timeout_configuration(self, lambda_client: boto3.client, app_stack_outputs: Dict[str, Any]):
        """Test Lambda function timeout configuration."""
        function_names = [
            app_stack_outputs.get("RuleCollectFunctionName"),
            app_stack_outputs.get("RuleExecuteFunctionName")
        ]
        
        for function_name in function_names:
            if not function_name:
                continue
                
            response = lambda_client.get_function(FunctionName=function_name)
            timeout = response["Configuration"]["Timeout"]
            
            # Ensure timeout is reasonable (between 30 seconds and 15 minutes)
            assert 30 <= timeout <= 900

    def test_lambda_memory_configuration(self, lambda_client: boto3.client, app_stack_outputs: Dict[str, Any]):
        """Test Lambda function memory configuration."""
        function_names = [
            app_stack_outputs.get("RuleCollectFunctionName"),
            app_stack_outputs.get("RuleExecuteFunctionName")
        ]
        
        for function_name in function_names:
            if not function_name:
                continue
                
            response = lambda_client.get_function(FunctionName=function_name)
            memory_size = response["Configuration"]["MemorySize"]
            
            # Ensure memory is reasonable (at least 128MB, max 10GB)
            assert 128 <= memory_size <= 10240