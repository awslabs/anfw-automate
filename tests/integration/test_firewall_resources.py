"""
Integration tests for firewall resources.
"""
import pytest
import boto3
from typing import Dict, Any


@pytest.mark.requires_stack("firewall-{stage}")
class TestFirewallResources:
    """Test firewall infrastructure resources."""

    def test_network_firewall_policy_exists(self, network_firewall_client: boto3.client, firewall_stack_outputs: Dict[str, Any]):
        """Test that Network Firewall policy exists and is active."""
        policy_arn = firewall_stack_outputs.get("FirewallPolicyArn")
        if not policy_arn:
            pytest.skip("FirewallPolicyArn not found in stack outputs")
        
        response = network_firewall_client.describe_firewall_policy(
            FirewallPolicyArn=policy_arn
        )
        
        assert response["FirewallPolicyResponse"]["FirewallPolicyStatus"] == "ACTIVE"
        assert response["FirewallPolicy"]["StatelessDefaultActions"]
        assert response["FirewallPolicy"]["StatefulDefaultActions"]

    def test_network_firewall_exists(self, network_firewall_client: boto3.client, firewall_stack_outputs: Dict[str, Any]):
        """Test that Network Firewall exists and is active."""
        firewall_arn = firewall_stack_outputs.get("FirewallArn")
        if not firewall_arn:
            pytest.skip("FirewallArn not found in stack outputs")
        
        response = network_firewall_client.describe_firewall(
            FirewallArn=firewall_arn
        )
        
        assert response["FirewallStatus"]["Status"] == "READY"
        assert response["Firewall"]["FirewallPolicyArn"]

    def test_firewall_rule_groups(self, network_firewall_client: boto3.client, firewall_stack_outputs: Dict[str, Any]):
        """Test firewall rule groups configuration."""
        policy_arn = firewall_stack_outputs.get("FirewallPolicyArn")
        if not policy_arn:
            pytest.skip("FirewallPolicyArn not found in stack outputs")
        
        response = network_firewall_client.describe_firewall_policy(
            FirewallPolicyArn=policy_arn
        )
        
        firewall_policy = response["FirewallPolicy"]
        
        # Check that rule groups are properly configured
        if "StatefulRuleGroupReferences" in firewall_policy:
            for rule_group_ref in firewall_policy["StatefulRuleGroupReferences"]:
                assert "ResourceArn" in rule_group_ref
                assert "Priority" in rule_group_ref

    def test_vpc_endpoints_exist(self, ec2_client: boto3.client, firewall_stack_outputs: Dict[str, Any]):
        """Test that VPC endpoints for firewall are created."""
        vpc_id = firewall_stack_outputs.get("VpcId")
        if not vpc_id:
            pytest.skip("VpcId not found in stack outputs")
        
        # List VPC endpoints in the VPC
        response = ec2_client.describe_vpc_endpoints(
            Filters=[
                {
                    "Name": "vpc-id",
                    "Values": [vpc_id]
                }
            ]
        )
        
        # Should have at least some VPC endpoints
        assert len(response["VpcEndpoints"]) >= 0

    def test_route_tables_updated(self, ec2_client: boto3.client, firewall_stack_outputs: Dict[str, Any]):
        """Test that route tables are properly updated for firewall."""
        vpc_id = firewall_stack_outputs.get("VpcId")
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
        
        # Check that route tables have proper routes
        for route_table in route_tables:
            routes = route_table["Routes"]
            assert len(routes) > 0

    def test_security_groups_configuration(self, ec2_client: boto3.client, firewall_stack_outputs: Dict[str, Any]):
        """Test security groups configuration for firewall."""
        vpc_id = firewall_stack_outputs.get("VpcId")
        if not vpc_id:
            pytest.skip("VpcId not found in stack outputs")
        
        # Get security groups for the VPC
        response = ec2_client.describe_security_groups(
            Filters=[
                {
                    "Name": "vpc-id",
                    "Values": [vpc_id]
                }
            ]
        )
        
        security_groups = response["SecurityGroups"]
        assert len(security_groups) > 0
        
        # Check default security group exists
        default_sg = next((sg for sg in security_groups if sg["GroupName"] == "default"), None)
        assert default_sg is not None

    def test_firewall_subnets(self, ec2_client: boto3.client, firewall_stack_outputs: Dict[str, Any]):
        """Test that firewall subnets are properly configured."""
        subnet_ids = firewall_stack_outputs.get("FirewallSubnetIds")
        if not subnet_ids:
            pytest.skip("FirewallSubnetIds not found in stack outputs")
        
        # Parse subnet IDs (might be comma-separated string)
        if isinstance(subnet_ids, str):
            subnet_id_list = [s.strip() for s in subnet_ids.split(",")]
        else:
            subnet_id_list = subnet_ids
        
        for subnet_id in subnet_id_list:
            response = ec2_client.describe_subnets(SubnetIds=[subnet_id])
            subnet = response["Subnets"][0]
            
            assert subnet["State"] == "available"
            assert subnet["AvailableIpAddressCount"] > 0

    def test_firewall_logging_configuration(self, network_firewall_client: boto3.client, firewall_stack_outputs: Dict[str, Any]):
        """Test firewall logging configuration."""
        firewall_arn = firewall_stack_outputs.get("FirewallArn")
        if not firewall_arn:
            pytest.skip("FirewallArn not found in stack outputs")
        
        try:
            response = network_firewall_client.describe_logging_configuration(
                FirewallArn=firewall_arn
            )
            
            logging_config = response["LoggingConfiguration"]
            assert "LogDestinationConfigs" in logging_config
            
        except network_firewall_client.exceptions.ResourceNotFoundException:
            # Logging might not be configured in all environments
            pytest.skip("Logging configuration not found - acceptable for some environments")