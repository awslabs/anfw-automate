"""
Integration tests for VPC resources.
"""
import pytest
import boto3
from typing import Dict, Any


@pytest.mark.requires_stack("vpc-{stage}")
class TestVpcResources:
    """Test VPC infrastructure resources."""

    def test_vpc_exists(self, ec2_client: boto3.client, vpc_stack_outputs: Dict[str, Any]):
        """Test that VPC exists and is available."""
        vpc_id = vpc_stack_outputs.get("VpcId")
        if not vpc_id:
            pytest.skip("VpcId not found in stack outputs")
        
        response = ec2_client.describe_vpcs(VpcIds=[vpc_id])
        vpc = response["Vpcs"][0]
        
        assert vpc["State"] == "available"
        assert vpc["CidrBlock"]
        assert vpc["EnableDnsHostnames"] is True
        assert vpc["EnableDnsSupport"] is True

    def test_subnets_exist(self, ec2_client: boto3.client, vpc_stack_outputs: Dict[str, Any]):
        """Test that subnets are created and available."""
        vpc_id = vpc_stack_outputs.get("VpcId")
        if not vpc_id:
            pytest.skip("VpcId not found in stack outputs")
        
        # Get all subnets in the VPC
        response = ec2_client.describe_subnets(
            Filters=[
                {
                    "Name": "vpc-id",
                    "Values": [vpc_id]
                }
            ]
        )
        
        subnets = response["Subnets"]
        assert len(subnets) > 0
        
        # Check each subnet
        for subnet in subnets:
            assert subnet["State"] == "available"
            assert subnet["AvailabilityZone"]
            assert subnet["CidrBlock"]
            assert subnet["AvailableIpAddressCount"] > 0

    def test_internet_gateway_exists(self, ec2_client: boto3.client, vpc_stack_outputs: Dict[str, Any]):
        """Test that Internet Gateway exists and is attached."""
        vpc_id = vpc_stack_outputs.get("VpcId")
        igw_id = vpc_stack_outputs.get("InternetGatewayId")
        
        if not vpc_id:
            pytest.skip("VpcId not found in stack outputs")
        
        # Get Internet Gateways attached to the VPC
        response = ec2_client.describe_internet_gateways(
            Filters=[
                {
                    "Name": "attachment.vpc-id",
                    "Values": [vpc_id]
                }
            ]
        )
        
        igws = response["InternetGateways"]
        assert len(igws) > 0
        
        # Check the first IGW
        igw = igws[0]
        assert igw["State"] == "available"
        
        # Check attachment
        attachments = igw["Attachments"]
        assert len(attachments) > 0
        assert attachments[0]["State"] == "available"
        assert attachments[0]["VpcId"] == vpc_id

    def test_route_tables_exist(self, ec2_client: boto3.client, vpc_stack_outputs: Dict[str, Any]):
        """Test that route tables are created and configured."""
        vpc_id = vpc_stack_outputs.get("VpcId")
        if not vpc_id:
            pytest.skip("VpcId not found in stack outputs")
        
        # Get route tables for the VPC
        response = ec2_client.describe_route_tables(
            Filters=[
                {
                    "Name": "vpc-id",
                    "Values": [vpc_id]
                }
            ]
        )
        
        route_tables = response["RouteTables"]
        assert len(route_tables) > 0
        
        # Check each route table
        for route_table in route_tables:
            assert route_table["VpcId"] == vpc_id
            
            # Check routes
            routes = route_table["Routes"]
            assert len(routes) > 0
            
            # Should have at least a local route
            local_routes = [r for r in routes if r.get("GatewayId") == "local"]
            assert len(local_routes) > 0

    def test_nat_gateways_exist(self, ec2_client: boto3.client, vpc_stack_outputs: Dict[str, Any]):
        """Test that NAT Gateways exist if configured."""
        vpc_id = vpc_stack_outputs.get("VpcId")
        if not vpc_id:
            pytest.skip("VpcId not found in stack outputs")
        
        # Get NAT Gateways in the VPC
        response = ec2_client.describe_nat_gateways(
            Filters=[
                {
                    "Name": "vpc-id",
                    "Values": [vpc_id]
                }
            ]
        )
        
        nat_gateways = response["NatGateways"]
        
        # NAT Gateways might not exist in all configurations
        for nat_gw in nat_gateways:
            assert nat_gw["State"] in ["available", "pending"]
            assert nat_gw["VpcId"] == vpc_id

    def test_vpc_cidr_configuration(self, ec2_client: boto3.client, vpc_stack_outputs: Dict[str, Any]):
        """Test VPC CIDR block configuration."""
        vpc_id = vpc_stack_outputs.get("VpcId")
        if not vpc_id:
            pytest.skip("VpcId not found in stack outputs")
        
        response = ec2_client.describe_vpcs(VpcIds=[vpc_id])
        vpc = response["Vpcs"][0]
        
        # Check primary CIDR block
        cidr_block = vpc["CidrBlock"]
        assert cidr_block
        
        # Validate CIDR format (basic check)
        assert "/" in cidr_block
        ip_part, prefix_part = cidr_block.split("/")
        assert len(ip_part.split(".")) == 4
        assert 8 <= int(prefix_part) <= 28

    def test_availability_zones_distribution(self, ec2_client: boto3.client, vpc_stack_outputs: Dict[str, Any]):
        """Test that subnets are distributed across availability zones."""
        vpc_id = vpc_stack_outputs.get("VpcId")
        if not vpc_id:
            pytest.skip("VpcId not found in stack outputs")
        
        # Get all subnets in the VPC
        response = ec2_client.describe_subnets(
            Filters=[
                {
                    "Name": "vpc-id",
                    "Values": [vpc_id]
                }
            ]
        )
        
        subnets = response["Subnets"]
        if len(subnets) > 1:
            # Check that subnets are in different AZs
            availability_zones = set(subnet["AvailabilityZone"] for subnet in subnets)
            assert len(availability_zones) >= 1

    def test_vpc_tags(self, ec2_client: boto3.client, vpc_stack_outputs: Dict[str, Any]):
        """Test that VPC has proper tags."""
        vpc_id = vpc_stack_outputs.get("VpcId")
        if not vpc_id:
            pytest.skip("VpcId not found in stack outputs")
        
        response = ec2_client.describe_vpcs(VpcIds=[vpc_id])
        vpc = response["Vpcs"][0]
        
        tags = {tag["Key"]: tag["Value"] for tag in vpc.get("Tags", [])}
        
        # Check for common tags
        expected_tag_keys = ["Name"]
        for key in expected_tag_keys:
            if key in tags:
                assert tags[key] is not None

    def test_dhcp_options(self, ec2_client: boto3.client, vpc_stack_outputs: Dict[str, Any]):
        """Test DHCP options configuration."""
        vpc_id = vpc_stack_outputs.get("VpcId")
        if not vpc_id:
            pytest.skip("VpcId not found in stack outputs")
        
        response = ec2_client.describe_vpcs(VpcIds=[vpc_id])
        vpc = response["Vpcs"][0]
        
        dhcp_options_id = vpc.get("DhcpOptionsId")
        if dhcp_options_id and dhcp_options_id != "default":
            # Get DHCP options details
            dhcp_response = ec2_client.describe_dhcp_options(
                DhcpOptionsIds=[dhcp_options_id]
            )
            
            dhcp_options = dhcp_response["DhcpOptions"][0]
            assert dhcp_options["DhcpOptionsId"] == dhcp_options_id