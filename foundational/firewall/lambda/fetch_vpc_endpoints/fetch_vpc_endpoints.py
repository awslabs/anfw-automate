import boto3
import cfnresponse
import json
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
            Az1 = event["ResourceProperties"]["az_a"]
            Az2 = event["ResourceProperties"]["az_b"]
            Az3 = event["ResourceProperties"]["az_c"]
            MultiAZ = event["ResourceProperties"]["MultiAZ"]
            FwArn = event["ResourceProperties"]["FwArn"]
        except Exception as e:
            logger.info('AZ retrieval failure: {}'.format(e))
            cfnresponse.send(event, context, responseStatus, {'Fetch AZ value failure: {}'.format(e)})
        try:
            nfw = boto3.client('network-firewall')
        except Exception as e:
            logger.info('boto3.client failure: {}'.format(e))
        try:
            NfwResponse=nfw.describe_firewall(FirewallArn=FwArn)
            if MultiAZ:
                VpceId1 = NfwResponse['FirewallStatus']['SyncStates'][Az1]['Attachment']['EndpointId']
                VpceId2 = NfwResponse['FirewallStatus']['SyncStates'][Az2]['Attachment']['EndpointId']
                VpceId3 = NfwResponse['FirewallStatus']['SyncStates'][Az3]['Attachment']['EndpointId']
                responseData['FwVpceId_a'] = VpceId1
                responseData['FwVpceId_b'] = VpceId2
                responseData['FwVpceId_c'] = VpceId3
                logger.info('responseData: {}'.format(responseData))
            else:
                VpceId1 = NfwResponse['FirewallStatus']['SyncStates'][Az1]['Attachment']['EndpointId']
                responseData['FwVpceId_a'] = VpceId1
                logger.info('responseData: {}'.format(responseData))
        except Exception as e:
            logger.info('ec2.describe_firewall failure: {}'.format(e))

        responseStatus = cfnresponse.SUCCESS
        cfnresponse.send(event, context, responseStatus, responseData)