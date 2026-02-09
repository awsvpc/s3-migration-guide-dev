import boto3
import csv
import os
import time
import logging
from datetime import datetime

s3 = boto3.client('s3')
iam = boto3.client('iam')
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger()

def get_all_versions(bucket):
    """Get all objects with version IDs and delete markers"""
    versions = []
    paginator = s3.get_paginator('list_object_versions')
    for page in paginator.paginate(Bucket=bucket):
        for obj in page.get('Versions', []):
            versions.append(obj)
        for dm in page.get('DeleteMarkers', []):
            versions.append(dm)
    return versions

def compare_buckets(src_bucket, dest_bucket):
    """Compare src and dest buckets by version ID"""
    src_versions = get_all_versions(src_bucket)
    dest_versions = get_all_versions(dest_bucket)
    
    dest_dict = {(v['Key'], v['VersionId']): True for v in dest_versions}
    
    missing = []
    for v in src_versions:
        if (v['Key'], v['VersionId']) not in dest_dict:
            missing.append({'Key': v['Key'], 'VersionId': v['VersionId'], 'IsLatest': v['IsLatest']})
    logger.info(f"Found {len(missing)} missing objects in destination bucket")
    return missing

def list_large_objects(bucket, min_size_bytes):
    """List objects in a bucket greater than provided size"""
    large_objs = []
    paginator = s3.get_paginator('list_objects_v2')
    for page in paginator.paginate(Bucket=bucket):
        for obj in page.get('Contents', []):
            if obj['Size'] >= min_size_bytes:
                large_objs.append({'Key': obj['Key'], 'Size': obj['Size']})
    logger.info(f"Found {len(large_objs)} objects larger than {min_size_bytes} bytes in {bucket}")
    return large_objs

def sync_buckets(src_bucket, dest_bucket):
    """Perform aws s3 sync via CLI"""
    import subprocess
    cmd = [
        'aws', 's3', 'sync',
        f's3://{src_bucket}',
        f's3://{dest_bucket}',
        '--exact-timestamps',
        '--acl', 'bucket-owner-full-control'
    ]
    logger.info(f"Running sync: {' '.join(cmd)}")
    subprocess.run(cmd, check=True)
    logger.info("Sync complete")

def create_inventory(bucket):
    """Create CSV inventory including versions, delete markers, size, encryption, metadata"""
    timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S')
    filename = f"{bucket}-{timestamp}-inventory.csv"
    
    with open(filename, 'w', newline='') as csvfile:
        fieldnames = [
            'Key','VersionId','IsLatest','Size','ETag','StorageClass','LastModified','Owner','DeleteMarker','ServerSideEncryption'
        ]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        
        versions = get_all_versions(bucket)
        for v in versions:
            key = v['Key']
            version_id = v['VersionId']
            size = v.get('Size', 0)
            etag = v.get('ETag', '')
            storage_class = v.get('StorageClass', '')
            last_modified = v.get('LastModified', '')
            owner = v.get('Owner', {}).get('DisplayName', '')
            delete_marker = v.get('DeleteMarker', False)
            
            # Get SSE status
            sse = ''
            try:
                head = s3.head_object(Bucket=bucket, Key=key, VersionId=version_id)
                sse = head.get('ServerSideEncryption', '')
            except Exception:
                pass
            
            writer.writerow({
                'Key': key,
                'VersionId': version_id,
                'IsLatest': v.get('IsLatest', False),
                'Size': size,
                'ETag': etag,
                'StorageClass': storage_class,
                'LastModified': last_modified,
                'Owner': owner,
                'DeleteMarker': delete_marker,
                'ServerSideEncryption': sse
            })
    logger.info(f"Inventory saved as {filename}")
    return filename

def backup_bucket_policy(bucket):
    """Backup bucket policy"""
    try:
        policy = s3.get_bucket_policy(Bucket=bucket)['Policy']
        filename = f"{bucket}-policy-backup-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}.json"
        with open(filename, 'w') as f:
            f.write(policy)
        logger.info(f"Bucket policy backed up to {filename}")
        return filename
    except s3.exceptions.NoSuchBucketPolicy:
        logger.warning(f"No policy found for bucket {bucket}")
        return None

def bucket_migration_handler(src_bucket, dest_bucket, min_size_bytes=0):
    # Step 1: Compare buckets
    missing_objects = compare_buckets(src_bucket, dest_bucket)
    
    # Step 2: List large objects in destination bucket
    large_objects = list_large_objects(dest_bucket, min_size_bytes) if min_size_bytes > 0 else []
    
    # Step 3: Sync buckets
    sync_buckets(src_bucket, dest_bucket)
    
    # Step 4: Create inventory
    inventory_file = create_inventory(dest_bucket)
    
    # Step 5: Backup bucket policy
    policy_file = backup_bucket_policy(dest_bucket)
    
    return {
        'missing_objects': missing_objects,
        'large_objects': large_objects,
        'inventory_file': inventory_file,
        'policy_file': policy_file
    }

if __name__ == "__main__":
    # Example usage
    src_bucket = input("Enter source bucket name: ")
    dest_bucket = input("Enter destination bucket name: ")
    min_size_gb = float(input("Enter minimum size in GB to list (0 to skip): "))
    min_size_bytes = int(min_size_gb * 1024**3)
    
    result = bucket_migration_handler(src_bucket, dest_bucket, min_size_bytes)
    print(result)
