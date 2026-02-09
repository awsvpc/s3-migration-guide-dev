import boto3
import logging
import os
import json

s3 = boto3.client('s3')
sns = boto3.client('sns')
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# SNS topic ARN for missing objects alert
SNS_TOPIC_ARN = os.environ.get('SNS_TOPIC_ARN', 'arn:aws:sns:region:account-id:topic-name')


def send_sns_alert_missing_object(source_bucket, dest_bucket, key, version_id):
    """Send SNS alert for missing object/version in destination bucket"""
    message = {
        "source_bucket": source_bucket,
        "destination_bucket": dest_bucket,
        "missing_object": key,
        "missing_versionid": version_id,
        "message": "Object/version missing in destination bucket"
    }
    try:
        sns.publish(
            TopicArn=SNS_TOPIC_ARN,
            Subject=f"Missing Object/Version Alert: {key} Version {version_id}",
            Message=json.dumps(message)
        )
        logger.info(f"SNS alert sent for missing object {key} version {version_id}")
    except Exception as e:
        logger.error(f"Failed to send SNS alert: {str(e)}")


def get_all_versions(bucket):
    """Return dict: {key: [version_ids]} including delete markers"""
    versions = {}
    paginator = s3.get_paginator('list_object_versions')
    for page in paginator.paginate(Bucket=bucket):
        for obj in page.get('Versions', []):
            versions.setdefault(obj['Key'], []).append(obj['VersionId'])
        for obj in page.get('DeleteMarkers', []):
            versions.setdefault(obj['Key'], []).append(obj['VersionId'])
    return versions


def lambda_handler(event, context):
    source_bucket = event['source_bucket']
    dest_bucket = event['dest_bucket']

    source_versions = get_all_versions(source_bucket)
    dest_versions = get_all_versions(dest_bucket)

    missing = []

    for key, version_ids in source_versions.items():
        dest_version_ids = dest_versions.get(key, [])
        for vid in version_ids:
            if vid not in dest_version_ids:
                missing.append({'Key': key, 'VersionId': vid})
                # Send SNS alert for each missing version
                send_sns_alert_missing_object(source_bucket, dest_bucket, key, vid)

    if missing:
        logger.info(f"Objects missing in destination bucket ({len(missing)}):")
        for m in missing:
            logger.info(f"Missing Key: {m['Key']}, VersionId: {m['VersionId']}")
    else:
        logger.info("Buckets are in sync!")

    return {"missing_count": len(missing), "missing_objects": missing}
