import boto3
import os
import json
import logging

s3 = boto3.client('s3')
sns = boto3.client('sns')
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Threshold for multipart copy (5GB)
MULTIPART_THRESHOLD = 5 * 1024 * 1024 * 1024  # 5GB

# SNS topic ARN (create SNS topic and subscribe your team)
SNS_TOPIC_ARN = os.environ.get('SNS_TOPIC_ARN', 'arn:aws:sns:region:account-id:topic-name')


def send_sns_alert(bucket, dest_bucket, key, version_id, error_msg):
    """Send SNS notification for failed copy"""
    message = {
        "bucketname": bucket,
        "destinationbucketname": dest_bucket,
        "objectpath": key,
        "versionid": version_id,
        "error": error_msg
    }
    try:
        sns.publish(
            TopicArn=SNS_TOPIC_ARN,
            Subject=f"S3 Copy Failed: {key} Version {version_id}",
            Message=json.dumps(message)
        )
        logger.info(f"SNS alert sent for {key} version {version_id}")
    except Exception as e:
        logger.error(f"Failed to send SNS alert: {str(e)}")


def copy_object_version(source_bucket, dest_bucket, key, version_id):
    """Copy specific version of object from source_bucket to dest_bucket."""
    try:
        # Get object size
        head = s3.head_object(Bucket=source_bucket, Key=key, VersionId=version_id)
        size = head['ContentLength']

        copy_source = {
            'Bucket': source_bucket,
            'Key': key,
            'VersionId': version_id
        }

        if size < MULTIPART_THRESHOLD:
            # Simple copy
            s3.copy_object(
                Bucket=dest_bucket,
                Key=key,
                CopySource=copy_source,
                MetadataDirective='COPY'
            )
            logger.info(f"Copied {key} version {version_id} (size={size}) to {dest_bucket}")
        else:
            # Multipart copy for large objects
            mp = s3.create_multipart_upload(Bucket=dest_bucket, Key=key)
            upload_id = mp['UploadId']

            part_size = 100 * 1024 * 1024  # 100MB parts
            parts = []
            for i in range(0, size, part_size):
                end = min(i + part_size - 1, size - 1)
                part_number = len(parts) + 1
                part = s3.upload_part_copy(
                    Bucket=dest_bucket,
                    Key=key,
                    PartNumber=part_number,
                    UploadId=upload_id,
                    CopySource=copy_source,
                    CopySourceRange=f"bytes={i}-{end}"
                )
                parts.append({'ETag': part['CopyPartResult']['ETag'], 'PartNumber': part_number})

            s3.complete_multipart_upload(
                Bucket=dest_bucket,
                Key=key,
                UploadId=upload_id,
                MultipartUpload={'Parts': parts}
            )
            logger.info(f"Multipart copied {key} version {version_id} to {dest_bucket}")

    except Exception as e:
        logger.error(f"Failed to copy {key} version {version_id}: {str(e)}")
        # Send SNS notification
        send_sns_alert(source_bucket, dest_bucket, key, version_id, str(e))


def lambda_handler(event, context):
    # Check if invoked manually
    if 'bucketname' in event:
        copy_object_version(
            source_bucket=event['bucketname'],
            dest_bucket=event['destinationbucketname'],
            key=event['objectpath'],
            version_id=event['versionid']
        )
        return {"status": "success"}

    # Process SQS messages
    for record in event.get('Records', []):
        try:
            msg = json.loads(record['body'])
            copy_object_version(
                source_bucket=msg['bucketname'],
                dest_bucket=msg['destinationbucketname'],
                key=msg['objectpath'],
                version_id=msg['versionid']
            )
        except Exception as e:
            logger.error(f"Error processing message: {str(e)}")
            send_sns_alert(
                msg.get('bucketname', 'N/A'),
                msg.get('destinationbucketname', 'N/A'),
                msg.get('objectpath', 'N/A'),
                msg.get('versionid', 'N/A'),
                str(e)
            )

    return {"status": "processed"}
