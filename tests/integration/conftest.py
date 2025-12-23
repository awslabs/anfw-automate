"""
Shared test configuration and fixtures for integration tests.
"""
import os
import pytest
import boto3
from typing import Dict, Any, Optional


@pytest.fixture(scope="session")
def aws_region() -> str:
    """Get AWS region from environment."""
    return os.environ.get("AWS_REGION", "us-east-1")


@pytest.fixture(scope="session") 
def stage() -> str:
    """Get deployment stage from environment."""
    return os.environ.get("STAGE", "local")


@pytest.fixture(scope="session")
def aws_endpoint_url() -> Optional[str]:
    """Get AWS endpoint URL for LocalStack."""
    return os.environ.get("AWS_ENDPOINT_URL")


@pytest.fixture(scope="session")
def boto3_session(aws_region: str, aws_endpoint_url: Optional[str]) -> boto3.Session:
    """Create boto3 session with appropriate configuration."""
    session = boto3.Session(region_name=aws_region)
    return session


@pytest.fixture(scope="session")
def cloudformation_client(boto3_session: boto3.Session, aws_endpoint_url: Optional[str]) -> boto3.client:
    """Create CloudFormation client."""
    kwargs = {"region_name": boto3_session.region_name}
    if aws_endpoint_url:
        kwargs["endpoint_url"] = aws_endpoint_url
    return boto3_session.client("cloudformation", **kwargs)


@pytest.fixture(scope="session")
def lambda_client(boto3_session: boto3.Session, aws_endpoint_url: Optional[str]) -> boto3.client:
    """Create Lambda client."""
    kwargs = {"region_name": boto3_session.region_name}
    if aws_endpoint_url:
        kwargs["endpoint_url"] = aws_endpoint_url
    return boto3_session.client("lambda", **kwargs)


@pytest.fixture(scope="session")
def s3_client(boto3_session: boto3.Session, aws_endpoint_url: Optional[str]) -> boto3.client:
    """Create S3 client."""
    kwargs = {"region_name": boto3_session.region_name}
    if aws_endpoint_url:
        kwargs["endpoint_url"] = aws_endpoint_url
    return boto3_session.client("s3", **kwargs)


@pytest.fixture(scope="session")
def ec2_client(boto3_session: boto3.Session, aws_endpoint_url: Optional[str]) -> boto3.client:
    """Create EC2 client."""
    kwargs = {"region_name": boto3_session.region_name}
    if aws_endpoint_url:
        kwargs["endpoint_url"] = aws_endpoint_url
    return boto3_session.client("ec2", **kwargs)


@pytest.fixture(scope="session")
def network_firewall_client(boto3_session: boto3.Session, aws_endpoint_url: Optional[str]) -> boto3.client:
    """Create Network Firewall client."""
    kwargs = {"region_name": boto3_session.region_name}
    if aws_endpoint_url:
        kwargs["endpoint_url"] = aws_endpoint_url
    return boto3_session.client("network-firewall", **kwargs)


def get_stack_outputs(cloudformation_client: boto3.client, stack_name: str) -> Dict[str, Any]:
    """Get stack outputs as a dictionary."""
    try:
        response = cloudformation_client.describe_stacks(StackName=stack_name)
        outputs = response["Stacks"][0].get("Outputs", [])
        return {output["OutputKey"]: output["OutputValue"] for output in outputs}
    except Exception:
        return {}


@pytest.fixture(scope="session")
def app_stack_outputs(cloudformation_client: boto3.client, stage: str) -> Dict[str, Any]:
    """Get application stack outputs."""
    stack_name = f"serverless-{stage}"
    return get_stack_outputs(cloudformation_client, stack_name)


@pytest.fixture(scope="session")
def firewall_stack_outputs(cloudformation_client: boto3.client, stage: str) -> Dict[str, Any]:
    """Get firewall stack outputs."""
    stack_name = f"firewall-{stage}"
    return get_stack_outputs(cloudformation_client, stack_name)


@pytest.fixture(scope="session")
def vpc_stack_outputs(cloudformation_client: boto3.client, stage: str) -> Dict[str, Any]:
    """Get VPC stack outputs."""
    stack_name = f"vpc-{stage}"
    return get_stack_outputs(cloudformation_client, stack_name)


@pytest.fixture(autouse=True)
def skip_if_no_stack(request, cloudformation_client: boto3.client):
    """Skip tests if required stack is not deployed."""
    if hasattr(request.node, "get_closest_marker"):
        marker = request.node.get_closest_marker("requires_stack")
        if marker:
            stack_name = marker.args[0]
            try:
                cloudformation_client.describe_stacks(StackName=stack_name)
            except Exception:
                pytest.skip(f"Stack {stack_name} not found - skipping test")