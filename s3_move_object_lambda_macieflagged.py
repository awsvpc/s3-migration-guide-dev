#!/usr/bin/env python3

# Purpose: Lambda function that moves S3 objects flagged by Macie
# Author:  Gary A. Stafford (March 2021)


import json
import logging
import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

s3_client = boto3.client('s3')


def lambda_handler(event, context):
    logging.info(f'event: {json.dumps(event)}')

    destination_bucket_name = 'macie-isolation-111222333444-us-east-1'
    source_bucket_name = event['detail']['resourcesAffected']['s3Bucket']['name']
    file_key_name = event['detail']['resourcesAffected']['s3Object']['key']
    copy_source_object = {'Bucket': source_bucket_name, 'Key': file_key_name}

    logging.debug(f'destination_bucket_name: {destination_bucket_name}')
    logging.debug(f'source_bucket_name: {source_bucket_name}')
    logging.debug(f'file_key_name: {file_key_name}')

    try:
        response = s3_client.copy_object(
            CopySource=copy_source_object,
            Bucket=destination_bucket_name,
            Key=file_key_name
        )
        logger.info(response)
    except ClientError as ex:
        logger.error(ex)
        exit(1)

    try:
        response = s3_client.delete_object(
            Bucket=source_bucket_name,
            Key=file_key_name
        )
        logger.info(response)
    except ClientError as ex:
        logger.error(ex)
        exit(1)

    return {
        'statusCode': 200,
        'body': json.dumps(copy_source_object)
    }
@awsvpc
Comment
