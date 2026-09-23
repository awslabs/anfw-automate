import boto3
import json
import cfnresponse
import logging

def handler(event, context):
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    logging.basicConfig(format='%(levelname)s:%(asctime)s:%(message)s')
    responseData = {}
    responseStatus = cfnresponse.FAILED
    logger.info('Received event: {}'.format(json.dumps(event)))
    if event["RequestType"] == "Delete":
        responseStatus = cfnresponse.SUCCESS
        cfnresponse.send(event, context, responseStatus, responseData)
    if event["RequestType"] == "Create":
        try:
            ec2 = boto3.client('ec2')
            vpc_id = event['ResourceProperties']['VpcId']
            vpc_cidr = event['ResourceProperties']['VpcCidrBlock']
            response = ec2.describe_route_tables(Filters=[{'Name': 'vpc-id', 'Values': [vpc_id]}])
            route_tables = response['RouteTables']
            for route_table in route_tables:
                for route in route_table['Routes']:
                    if route['DestinationCidrBlock'] == vpc_cidr and route['State'] == 'active':
                        print(f"Skipping local route {route} in {route_table['RouteTableId']}")
                        continue
                    ec2.delete_route(RouteTableId=route_table['RouteTableId'], DestinationCidrBlock=route['DestinationCidrBlock'])
            responseStatus = cfnresponse.SUCCESS
            cfnresponse.send(event, context, responseStatus, responseData)
        except Exception as e:
            error_message = str(e)
            print('Error:', error_message)
            responseData = {"Error": error_message}
            responseStatus = cfnresponse.FAILED
            cfnresponse.send(event, context, responseStatus, responseData)