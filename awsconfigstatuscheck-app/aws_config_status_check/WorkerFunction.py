# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

import json
import boto3
from botocore.config import Config
import time

class ConfigRecordersCheck(object):

    def __init__(self, accountid):

        self.accountid = accountid
        self.config = Config(
            signature_version='v4',
            retries={
                'max_attempts': 10,
                'mode': 'standard',
            }
        )
        self.sts_connection = boto3.client(
            'sts', config=self.config)
        self.cloudwatch = boto3.client(
            'cloudwatch', config=self.config, region_name='us-east-1')
        self.AWSConfigRecordersTotal = 0
        self.AWSConfigRecordersEnabled = 0

    def GetRegionsfromAccount(self):

        print("account:", self.accountid)
        acct_b = self.sts_connection.assume_role(
            RoleArn="arn:aws:iam::" + self.accountid + ":role/AssumedFunctionRole",
            RoleSessionName="cross_acct_lambda"
        )
        self.ACCESS_KEY = acct_b['Credentials']['AccessKeyId']
        self.SECRET_KEY = acct_b['Credentials']['SecretAccessKey']
        self.SESSION_TOKEN = acct_b['Credentials']['SessionToken']

        self.ec2 = boto3.client(
            'ec2',
            aws_access_key_id=self.ACCESS_KEY,
            aws_secret_access_key=self.SECRET_KEY,
            aws_session_token=self.SESSION_TOKEN,
            config=self.config
        )

        filters = [
            {
                'Name': 'opt-in-status',
                'Values': ['opt-in-not-required', 'opted-in']
            }
        ]

        self.regions = [region['RegionName'] for region in self.ec2.describe_regions(
            Filters=filters)['Regions']]

        self.PublishConfigStatustoCloudwatchforEveryRegion()

    def PublishConfigStatustoCloudwatchforEveryRegion(self):

        for self.region in self.regions:

            awsconfig = boto3.client(
                'config',
                aws_access_key_id=self.ACCESS_KEY,
                aws_secret_access_key=self.SECRET_KEY,
                aws_session_token=self.SESSION_TOKEN,
                region_name=self.region,
                config=self.config
            )
            self.config_recorder_response = awsconfig.describe_configuration_recorder_status()
            print("region:", self.region)
            response = self.config_recorder_response["ConfigurationRecordersStatus"]
            print("len of response", len(response))
            if len(response) > 0:
                index = 0
                self.AWSConfigRecordersTotal += 1
                print("Value of recording:",
                        response[index]['recording'])
                if response[index]['recording'] == True:
                    print("SUCCESS: {}".format(response))
                    print("SUCCESS: {}".format(
                        response[index]['lastStatus']))
                    print("PUBLISHING SUCCESS")
                    self.AWSConfigRecordersEnabled += 1
                    response = self.cloudwatch.put_metric_data(
                        MetricData=[
                            {
                                'MetricName': 'AWSConfigRecordersStatusFlag',
                                'Dimensions': [
                                    {
                                    'Name': "AccountId",
                                    'Value': self.accountid
                                },
                                    {
                                    'Name': "Region",
                                    'Value': self.region
                                },
                                    ],
                                'Value': 1
                            },
                        ],
                        Namespace='AWSConfigStatus'
                    )
                else:
                    print("PUBLISHING FAILURE")
                    response = self.cloudwatch.put_metric_data(
                        MetricData=[
                            {
                                'MetricName': 'AWSConfigRecordersStatusFlag',
                                'Dimensions': [
                                    {
                                    'Name': "AccountId",
                                    'Value': self.accountid
                                    },
                                    {
                                    'Name': "Region",
                                    'Value': self.region
                                    },
                                ],
                                'Value': 0
                            },
                        ],
                        Namespace='AWSConfigStatus'
                    )

        print("PUBLISHING SUMMARY")
        cloudwatch = boto3.client(
            'cloudwatch', config=self.config, region_name='us-east-1')
        response = cloudwatch.put_metric_data(
            MetricData=[
                {
                    'MetricName': 'TotalAWSConfigRecordersEnabled',
                    'Dimensions': [
                        {
                        'Name': "AccountId",
                        'Value': self.accountid
                        }
                    ],
                    'Value': self.AWSConfigRecordersTotal
                }
            ],
            Namespace='AWSConfigStatus'
        )
        response = cloudwatch.put_metric_data(
            MetricData=[
                {
                    'MetricName': 'TotalRegions',
                    'Dimensions': [
                        {
                        'Name': "AccountId",
                        'Value': self.accountid
                        }
                    ],
                    'Value': len(self.regions)
                }
            ],
            Namespace='AWSConfigStatus'
        )
        response = self.cloudwatch.put_metric_data(
            MetricData=[
                {
                    'MetricName': 'AWSConfigRecordersRunning',
                    'Dimensions': [
                        {
                        'Name': "AccountId",
                        'Value': self.accountid
                        }
                    ],
                    'Value': self.AWSConfigRecordersEnabled
                }
            ],
            Namespace='AWSConfigStatus'
        )

def lambda_handler(event, context):

    _start = time.time()
    print('## EVENT')
    print(event)
    print("I am here", event["detail"]["aws_config_status_check_account"])
    accid = event["detail"]["aws_config_status_check_account"]
    awsconfigcheck = ConfigRecordersCheck(accid)
    awsconfigcheck.GetRegionsfromAccount()
    print("Sequential execution time: %s seconds",
            time.time() - _start)
    # TODO implement
    return {
        "statusCode": 200,
        "headers": {
            "Content-Type": "application/json"
        },
        "body": json.dumps({
            "Response ": "SUCCESS"
        }, default=str)
    }
