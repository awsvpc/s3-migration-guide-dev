#!/usr/bin/env python3
"""
S3 Cross-Account Replication Manager
Manages S3 bucket replication, inventory, and batch operations across AWS accounts
"""

import boto3
import json
import time
import os
import sys
from datetime import datetime
from botocore.exceptions import ClientError, NoCredentialsError
from pathlib import Path

class S3ReplicationManager:
    def __init__(self, source_profile, dest_profile, source_region='us-east-1', dest_region='us-east-1'):
        """
        Initialize S3 Replication Manager
        
        Args:
            source_profile: AWS CLI profile for source account
            dest_profile: AWS CLI profile for destination account
            source_region: Source AWS region
            dest_region: Destination AWS region
        """
        try:
            self.source_session = boto3.Session(profile_name=source_profile, region_name=source_region)
            self.dest_session = boto3.Session(profile_name=dest_profile, region_name=dest_region)
            
            # Initialize clients
            self.source_s3 = self.source_session.client('s3')
            self.source_iam = self.source_session.client('iam')
            self.source_sts = self.source_session.client('sts')
            
            self.dest_s3 = self.dest_session.client('s3')
            self.dest_iam = self.dest_session.client('iam')
            self.dest_sts = self.dest_session.client('sts')
            
            # Get account IDs
            self.source_account_id = self.source_sts.get_caller_identity()['Account']
            self.dest_account_id = self.dest_sts.get_caller_identity()['Account']
            
            self.source_region = source_region
            self.dest_region = dest_region
            
            print(f"✓ Initialized Successfully")
            print(f"  Source Account: {self.source_account_id} ({source_region})")
            print(f"  Destination Account: {self.dest_account_id} ({dest_region})")
            print("-" * 80)
            
        except NoCredentialsError:
            print("✗ Error: AWS credentials not found")
            print("Please configure AWS CLI profiles first")
            sys.exit(1)
        except Exception as e:
            print(f"✗ Error initializing: {e}")
            sys.exit(1)

    def create_replication_role(self, source_bucket, dest_bucket):
        """
        Create IAM role for S3 replication in source account
        
        Args:
            source_bucket: Source bucket name
            dest_bucket: Destination bucket name
            
        Returns:
            Role ARN
        """
        print("\n=== Creating S3 Replication IAM Role (Source Account) ===")
        
        role_name = f"S3ReplicationRole-{source_bucket}-to-{dest_bucket}"
        
        # Trust policy for S3 service
        trust_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {
                        "Service": "s3.amazonaws.com"
                    },
                    "Action": "sts:AssumeRole"
                }
            ]
        }
        
        # Permissions policy
        permissions_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": [
                        "s3:GetReplicationConfiguration",
                        "s3:ListBucket"
                    ],
                    "Resource": f"arn:aws:s3:::{source_bucket}"
                },
                {
                    "Effect": "Allow",
                    "Action": [
                        "s3:GetObjectVersionForReplication",
                        "s3:GetObjectVersionAcl",
                        "s3:GetObjectVersionTagging"
                    ],
                    "Resource": f"arn:aws:s3:::{source_bucket}/*"
                },
                {
                    "Effect": "Allow",
                    "Action": [
                        "s3:ReplicateObject",
                        "s3:ReplicateDelete",
                        "s3:ReplicateTags"
                    ],
                    "Resource": f"arn:aws:s3:::{dest_bucket}/*"
                }
            ]
        }
        
        try:
            # Check if role exists
            try:
                role = self.source_iam.get_role(RoleName=role_name)
                role_arn = role['Role']['Arn']
                print(f"✓ Role already exists: {role_name}")
                print(f"  ARN: {role_arn}")
                return role_arn
            except ClientError as e:
                if e.response['Error']['Code'] != 'NoSuchEntity':
                    raise
            
            # Create role
            response = self.source_iam.create_role(
                RoleName=role_name,
                AssumeRolePolicyDocument=json.dumps(trust_policy),
                Description=f'S3 Replication role for {source_bucket} to {dest_bucket}'
            )
            
            role_arn = response['Role']['Arn']
            print(f"✓ Role created: {role_name}")
            print(f"  ARN: {role_arn}")
            
            # Attach inline policy
            self.source_iam.put_role_policy(
                RoleName=role_name,
                PolicyName='S3ReplicationPolicy',
                PolicyDocument=json.dumps(permissions_policy)
            )
            
            print("✓ Permissions policy attached")
            
            # Wait for role to propagate
            print("  Waiting for role to propagate...")
            time.sleep(10)
            
            return role_arn
            
        except ClientError as e:
            print(f"✗ Error creating replication role: {e}")
            raise

    def update_destination_bucket_policy(self, dest_bucket, source_bucket):
        """
        Update destination bucket policy to allow replication from source
        
        Args:
            dest_bucket: Destination bucket name
            source_bucket: Source bucket name
        """
        print(f"\n=== Updating Destination Bucket Policy ===")
        print(f"Bucket: {dest_bucket}")
        
        policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": "AllowSourceAccountReplication",
                    "Effect": "Allow",
                    "Principal": {
                        "AWS": f"arn:aws:iam::{self.source_account_id}:root"
                    },
                    "Action": [
                        "s3:ReplicateObject",
                        "s3:ReplicateDelete",
                        "s3:ReplicateTags",
                        "s3:GetObjectVersionTagging",
                        "s3:ObjectOwnerOverrideToBucketOwner"
                    ],
                    "Resource": f"arn:aws:s3:::{dest_bucket}/*"
                },
                {
                    "Sid": "AllowSourceAccountList",
                    "Effect": "Allow",
                    "Principal": {
                        "AWS": f"arn:aws:iam::{self.source_account_id}:root"
                    },
                    "Action": [
                        "s3:List*",
                        "s3:GetBucketVersioning",
                        "s3:PutBucketVersioning"
                    ],
                    "Resource": f"arn:aws:s3:::{dest_bucket}"
                }
            ]
        }
        
        try:
            # Get existing policy and merge if needed
            try:
                existing_policy = self.dest_s3.get_bucket_policy(Bucket=dest_bucket)
                existing_policy_dict = json.loads(existing_policy['Policy'])
                
                # Check if our statements already exist
                has_replication = False
                for stmt in existing_policy_dict.get('Statement', []):
                    if stmt.get('Sid') == 'AllowSourceAccountReplication':
                        has_replication = True
                        break
                
                if has_replication:
                    print("✓ Bucket policy already configured for replication")
                    return
                
                # Merge policies
                existing_policy_dict['Statement'].extend(policy['Statement'])
                policy = existing_policy_dict
                
            except ClientError as e:
                if e.response['Error']['Code'] != 'NoSuchBucketPolicy':
                    raise
            
            # Apply policy
            self.dest_s3.put_bucket_policy(
                Bucket=dest_bucket,
                Policy=json.dumps(policy)
            )
            
            print("✓ Bucket policy updated successfully")
            
        except ClientError as e:
            print(f"✗ Error updating bucket policy: {e}")
            raise

    def enable_versioning(self, bucket, account='source'):
        """
        Enable versioning on S3 bucket
        
        Args:
            bucket: Bucket name
            account: 'source' or 'dest'
        """
        print(f"\n=== Enabling Versioning on {bucket} ({account}) ===")
        
        s3_client = self.source_s3 if account == 'source' else self.dest_s3
        
        try:
            # Check current versioning status
            response = s3_client.get_bucket_versioning(Bucket=bucket)
            status = response.get('Status', 'Disabled')
            
            if status == 'Enabled':
                print(f"✓ Versioning already enabled on {bucket}")
                return
            
            # Enable versioning
            s3_client.put_bucket_versioning(
                Bucket=bucket,
                VersioningConfiguration={'Status': 'Enabled'}
            )
            
            print(f"✓ Versioning enabled on {bucket}")
            
        except ClientError as e:
            print(f"✗ Error enabling versioning: {e}")
            raise

    def enable_replication(self, source_bucket, dest_bucket, role_arn, prefix=""):
        """
        Enable S3 replication for new objects
        
        Args:
            source_bucket: Source bucket name
            dest_bucket: Destination bucket name
            role_arn: IAM role ARN for replication
            prefix: Optional prefix filter
        """
        print(f"\n=== Enabling S3 Replication ===")
        print(f"Source: {source_bucket}")
        print(f"Destination: {dest_bucket}")
        
        replication_config = {
            "Role": role_arn,
            "Rules": [
                {
                    "ID": f"Replication-{source_bucket}-to-{dest_bucket}",
                    "Priority": 1,
                    "Filter": {"Prefix": prefix},
                    "Status": "Enabled",
                    "Destination": {
                        "Bucket": f"arn:aws:s3:::{dest_bucket}",
                        "ReplicationTime": {
                            "Status": "Enabled",
                            "Time": {
                                "Minutes": 15
                            }
                        },
                        "Metrics": {
                            "Status": "Enabled",
                            "EventThreshold": {
                                "Minutes": 15
                            }
                        },
                        "AccessControlTranslation": {
                            "Owner": "Destination"
                        },
                        "Account": self.dest_account_id
                    },
                    "DeleteMarkerReplication": {
                        "Status": "Enabled"
                    }
                }
            ]
        }
        
        try:
            self.source_s3.put_bucket_replication(
                Bucket=source_bucket,
                ReplicationConfiguration=replication_config
            )
            
            print("✓ Replication enabled successfully")
            print(f"  Rule ID: Replication-{source_bucket}-to-{dest_bucket}")
            print(f"  Prefix filter: {prefix if prefix else '(all objects)'}")
            
        except ClientError as e:
            print(f"✗ Error enabling replication: {e}")
            raise

    def disable_replication(self, source_bucket):
        """
        Disable S3 replication
        
        Args:
            source_bucket: Source bucket name
        """
        print(f"\n=== Disabling S3 Replication ===")
        print(f"Bucket: {source_bucket}")
        
        try:
            # Get current replication configuration
            try:
                response = self.source_s3.get_bucket_replication(Bucket=source_bucket)
                print(f"Current replication rules: {len(response['ReplicationConfiguration']['Rules'])}")
            except ClientError as e:
                if e.response['Error']['Code'] == 'ReplicationConfigurationNotFoundError':
                    print("✓ No replication configuration found")
                    return
                raise
            
            # Delete replication configuration
            self.source_s3.delete_bucket_replication(Bucket=source_bucket)
            
            print("✓ Replication disabled successfully")
            
        except ClientError as e:
            print(f"✗ Error disabling replication: {e}")
            raise

    def create_inventory(self, source_bucket, inventory_dest_bucket, inventory_name=None):
        """
        Create S3 inventory configuration
        
        Args:
            source_bucket: Source bucket name
            inventory_dest_bucket: Destination bucket for inventory reports
            inventory_name: Optional inventory name
            
        Returns:
            Inventory configuration ID
        """
        print(f"\n=== Creating S3 Inventory Configuration ===")
        print(f"Source Bucket: {source_bucket}")
        print(f"Inventory Destination: {inventory_dest_bucket}")
        
        if not inventory_name:
            inventory_name = f"{source_bucket}-inventory-{datetime.now().strftime('%Y%m%d')}"
        
        # Ensure inventory destination bucket exists
        self._ensure_inventory_bucket_exists(inventory_dest_bucket)
        
        inventory_config = {
            "Destination": {
                "S3BucketDestination": {
                    "AccountId": self.source_account_id,
                    "Bucket": f"arn:aws:s3:::{inventory_dest_bucket}",
                    "Format": "CSV",
                    "Prefix": f"inventory/{source_bucket}/"
                }
            },
            "IsEnabled": True,
            "Filter": {},
            "Id": inventory_name,
            "IncludedObjectVersions": "All",
            "OptionalFields": [
                "Size",
                "LastModifiedDate",
                "StorageClass",
                "ETag",
                "IsMultipartUploaded",
                "ReplicationStatus",
                "EncryptionStatus"
            ],
            "Schedule": {
                "Frequency": "Daily"
            }
        }
        
        try:
            self.source_s3.put_bucket_inventory_configuration(
                Bucket=source_bucket,
                Id=inventory_name,
                InventoryConfiguration=inventory_config
            )
            
            print("✓ Inventory configuration created successfully")
            print(f"  Inventory ID: {inventory_name}")
            print(f"  Frequency: Daily")
            print(f"  Destination: s3://{inventory_dest_bucket}/inventory/{source_bucket}/")
            
            return inventory_name
            
        except ClientError as e:
            print(f"✗ Error creating inventory: {e}")
            raise

    def _ensure_inventory_bucket_exists(self, bucket_name):
        """
        Ensure inventory bucket exists and has proper policies
        
        Args:
            bucket_name: Inventory bucket name
        """
        try:
            # Check if bucket exists
            try:
                self.source_s3.head_bucket(Bucket=bucket_name)
                print(f"✓ Inventory bucket exists: {bucket_name}")
            except ClientError as e:
                if e.response['Error']['Code'] == '404':
                    print(f"Creating inventory bucket: {bucket_name}")
                    self.source_s3.create_bucket(Bucket=bucket_name)
                    print(f"✓ Inventory bucket created: {bucket_name}")
                else:
                    raise
            
            # Update bucket policy to allow S3 to write inventory
            inventory_policy = {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Sid": "InventoryPolicy",
                        "Effect": "Allow",
                        "Principal": {
                            "Service": "s3.amazonaws.com"
                        },
                        "Action": "s3:PutObject",
                        "Resource": f"arn:aws:s3:::{bucket_name}/*",
                        "Condition": {
                            "StringEquals": {
                                "s3:x-amz-acl": "bucket-owner-full-control",
                                "aws:SourceAccount": self.source_account_id
                            }
                        }
                    }
                ]
            }
            
            self.source_s3.put_bucket_policy(
                Bucket=bucket_name,
                Policy=json.dumps(inventory_policy)
            )
            
            print(f"✓ Inventory bucket policy updated")
            
        except ClientError as e:
            print(f"✗ Error setting up inventory bucket: {e}")
            raise

    def get_inventory_data(self, inventory_bucket, inventory_prefix, local_dir=None):
        """
        Download inventory files from S3
        
        Args:
            inventory_bucket: Inventory bucket name
            inventory_prefix: S3 prefix for inventory files
            local_dir: Local directory to save files
        """
        print(f"\n=== Downloading Inventory Data ===")
        print(f"Bucket: {inventory_bucket}")
        print(f"Prefix: {inventory_prefix}")
        
        if not local_dir:
            local_dir = f"./inventory-downloads/{inventory_bucket}"
        
        os.makedirs(local_dir, exist_ok=True)
        
        try:
            # List objects in the inventory prefix
            paginator = self.source_s3.get_paginator('list_objects_v2')
            pages = paginator.paginate(Bucket=inventory_bucket, Prefix=inventory_prefix)
            
            file_count = 0
            total_size = 0
            
            for page in pages:
                if 'Contents' not in page:
                    print("No inventory files found")
                    return
                
                for obj in page['Contents']:
                    key = obj['Key']
                    size = obj['Size']
                    
                    # Skip directories
                    if key.endswith('/'):
                        continue
                    
                    # Create local file path
                    local_file = os.path.join(local_dir, key.replace(inventory_prefix, '').lstrip('/'))
                    os.makedirs(os.path.dirname(local_file), exist_ok=True)
                    
                    # Download file
                    print(f"  Downloading: {key} ({size} bytes)")
                    self.source_s3.download_file(inventory_bucket, key, local_file)
                    
                    file_count += 1
                    total_size += size
            
            print(f"\n✓ Downloaded {file_count} files")
            print(f"  Total size: {total_size:,} bytes")
            print(f"  Location: {local_dir}")
            
        except ClientError as e:
            print(f"✗ Error downloading inventory: {e}")
            raise

    def list_inventories(self, bucket):
        """
        List all inventory configurations for a bucket
        
        Args:
            bucket: Bucket name
            
        Returns:
            List of inventory configurations
        """
        print(f"\n=== Listing Inventory Configurations ===")
        print(f"Bucket: {bucket}")
        
        try:
            response = self.source_s3.list_bucket_inventory_configurations(Bucket=bucket)
            
            inventories = response.get('InventoryConfigurationList', [])
            
            if not inventories:
                print("No inventory configurations found")
                return []
            
            print(f"\nFound {len(inventories)} inventory configuration(s):")
            for idx, inv in enumerate(inventories, 1):
                print(f"\n{idx}. ID: {inv['Id']}")
                print(f"   Status: {'Enabled' if inv['IsEnabled'] else 'Disabled'}")
                print(f"   Frequency: {inv['Schedule']['Frequency']}")
                dest = inv['Destination']['S3BucketDestination']
                print(f"   Destination: {dest['Bucket']}/{dest.get('Prefix', '')}")
            
            return inventories
            
        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchConfiguration':
                print("No inventory configurations found")
                return []
            print(f"✗ Error listing inventories: {e}")
            raise

    def disable_inventory(self, bucket, inventory_id):
        """
        Disable/delete inventory configuration
        
        Args:
            bucket: Bucket name
            inventory_id: Inventory configuration ID
        """
        print(f"\n=== Disabling Inventory Configuration ===")
        print(f"Bucket: {bucket}")
        print(f"Inventory ID: {inventory_id}")
        
        try:
            self.source_s3.delete_bucket_inventory_configuration(
                Bucket=bucket,
                Id=inventory_id
            )
            
            print("✓ Inventory configuration disabled/deleted successfully")
            
        except ClientError as e:
            print(f"✗ Error disabling inventory: {e}")
            raise

    def create_batch_replication_job(self, source_bucket, dest_bucket, manifest_bucket, 
                                    manifest_key, role_arn=None):
        """
        Create S3 Batch Replication job for existing objects
        
        Args:
            source_bucket: Source bucket name
            dest_bucket: Destination bucket name
            manifest_bucket: Bucket containing inventory manifest
            manifest_key: S3 key to manifest file
            role_arn: Optional IAM role ARN
            
        Returns:
            Job ID
        """
        print(f"\n=== Creating S3 Batch Replication Job ===")
        print(f"Source: {source_bucket}")
        print(f"Destination: {dest_bucket}")
        print(f"Manifest: s3://{manifest_bucket}/{manifest_key}")
        
        # Create batch replication role if not provided
        if not role_arn:
            role_arn = self._create_batch_replication_role(source_bucket, dest_bucket, manifest_bucket)
        
        # Create S3 Control client
        s3_control = self.source_session.client('s3control')
        
        job_manifest = {
            'Spec': {
                'Format': 'S3InventoryReport_CSV_20161130',
                'Fields': ['Bucket', 'Key', 'VersionId']
            },
            'Location': {
                'ObjectArn': f'arn:aws:s3:::{manifest_bucket}/{manifest_key}',
                'ETag': self._get_object_etag(manifest_bucket, manifest_key)
            }
        }
        
        operation = {
            'S3ReplicateObject': {}
        }
        
        report = {
            'Bucket': f'arn:aws:s3:::{source_bucket}',
            'Format': 'Report_CSV_20180820',
            'Enabled': True,
            'Prefix': 'batch-replication-reports/',
            'ReportScope': 'AllTasks'
        }
        
        try:
            response = s3_control.create_job(
                AccountId=self.source_account_id,
                ConfirmationRequired=True,
                Operation=operation,
                Report=report,
                Manifest=job_manifest,
                Description=f'Batch replication from {source_bucket} to {dest_bucket}',
                Priority=10,
                RoleArn=role_arn
            )
            
            job_id = response['JobId']
            
            print("✓ Batch replication job created successfully")
            print(f"  Job ID: {job_id}")
            print(f"  Status: Awaiting Confirmation")
            print(f"\nTo activate the job, run:")
            print(f"aws s3control update-job-status \\")
            print(f"  --account-id {self.source_account_id} \\")
            print(f"  --job-id {job_id} \\")
            print(f"  --requested-job-status Ready")
            
            return job_id
            
        except ClientError as e:
            print(f"✗ Error creating batch replication job: {e}")
            raise

    def _create_batch_replication_role(self, source_bucket, dest_bucket, manifest_bucket):
        """
        Create IAM role for S3 Batch Operations
        
        Returns:
            Role ARN
        """
        print("\n=== Creating S3 Batch Replication Role ===")
        
        role_name = f"S3BatchReplicationRole-{source_bucket}"
        
        trust_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {
                        "Service": "batchoperations.s3.amazonaws.com"
                    },
                    "Action": "sts:AssumeRole"
                }
            ]
        }
        
        permissions_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": [
                        "s3:GetObject",
                        "s3:GetObjectVersion"
                    ],
                    "Resource": [
                        f"arn:aws:s3:::{manifest_bucket}/*",
                        f"arn:aws:s3:::{source_bucket}/*"
                    ]
                },
                {
                    "Effect": "Allow",
                    "Action": [
                        "s3:PutObject"
                    ],
                    "Resource": [
                        f"arn:aws:s3:::{source_bucket}/*",
                        f"arn:aws:s3:::{dest_bucket}/*"
                    ]
                },
                {
                    "Effect": "Allow",
                    "Action": [
                        "s3:GetReplicationConfiguration",
                        "s3:PutInventoryConfiguration"
                    ],
                    "Resource": f"arn:aws:s3:::{source_bucket}"
                },
                {
                    "Effect": "Allow",
                    "Action": [
                        "s3:InitiateReplication"
                    ],
                    "Resource": f"arn:aws:s3:::{source_bucket}/*"
                }
            ]
        }
        
        try:
            # Check if role exists
            try:
                role = self.source_iam.get_role(RoleName=role_name)
                role_arn = role['Role']['Arn']
                print(f"✓ Role already exists: {role_name}")
                return role_arn
            except ClientError as e:
                if e.response['Error']['Code'] != 'NoSuchEntity':
                    raise
            
            # Create role
            response = self.source_iam.create_role(
                RoleName=role_name,
                AssumeRolePolicyDocument=json.dumps(trust_policy),
                Description=f'S3 Batch Replication role for {source_bucket}'
            )
            
            role_arn = response['Role']['Arn']
            print(f"✓ Role created: {role_name}")
            
            # Attach policy
            self.source_iam.put_role_policy(
                RoleName=role_name,
                PolicyName='S3BatchReplicationPolicy',
                PolicyDocument=json.dumps(permissions_policy)
            )
            
            print("✓ Permissions attached")
            time.sleep(10)
            
            return role_arn
            
        except ClientError as e:
            print(f"✗ Error creating batch role: {e}")
            raise

    def _get_object_etag(self, bucket, key):
        """
        Get ETag for an S3 object
        
        Args:
            bucket: Bucket name
            key: Object key
            
        Returns:
            ETag string
        """
        try:
            response = self.source_s3.head_object(Bucket=bucket, Key=key)
            return response['ETag'].strip('"')
        except ClientError as e:
            print(f"✗ Error getting ETag: {e}")
            raise

    def get_batch_job_status(self, job_id):
        """
        Get status of S3 Batch Operations job
        
        Args:
            job_id: Batch job ID
        """
        print(f"\n=== Batch Replication Job Status ===")
        print(f"Job ID: {job_id}")
        
        s3_control = self.source_session.client('s3control')
        
        try:
            response = s3_control.describe_job(
                AccountId=self.source_account_id,
                JobId=job_id
            )
            
            job = response['Job']
            
            print(f"\nStatus: {job['Status']}")
            print(f"Priority: {job['Priority']}")
            print(f"Created: {job['CreationTime']}")
            
            if 'ProgressSummary' in job:
                progress = job['ProgressSummary']
                print(f"\nProgress:")
                print(f"  Total: {progress.get('TotalNumberOfTasks', 0)}")
                print(f"  Succeeded: {progress.get('NumberOfTasksSucceeded', 0)}")
                print(f"  Failed: {progress.get('NumberOfTasksFailed', 0)}")
            
            return job
            
        except ClientError as e:
            print(f"✗ Error getting job status: {e}")
            raise

    def generate_cleanup_instructions(self, source_bucket, dest_bucket):
        """
        Generate cleanup instructions for manual execution
        
        Args:
            source_bucket: Source bucket name
            dest_bucket: Destination bucket name
        """
        print("\n" + "=" * 80)
        print("CLEANUP INSTRUCTIONS")
        print("=" * 80)
        
        cleanup_file = f"cleanup-instructions-{datetime.now().strftime('%Y%m%d-%H%M%S')}.txt"
        
        instructions = f"""
S3 CROSS-ACCOUNT REPLICATION CLEANUP INSTRUCTIONS
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

SOURCE ACCOUNT ({self.source_account_id}):
================================================================================

1. DELETE IAM ROLES:
   
   # List roles
   aws iam list-roles --query 'Roles[?contains(RoleName, `S3Replication`) || contains(RoleName, `S3Batch`)].RoleName' --output table
   
   # Delete replication role
   aws iam delete-role-policy --role-name S3ReplicationRole-{source_bucket}-to-{dest_bucket} --policy-name S3ReplicationPolicy
   aws iam delete-role --role-name S3ReplicationRole-{source_bucket}-to-{dest_bucket}
   
   # Delete batch replication role
   aws iam delete-role-policy --role-name S3BatchReplicationRole-{source_bucket} --policy-name S3BatchReplicationPolicy
   aws iam delete-role --role-name S3BatchReplicationRole-{source_bucket}

2. DISABLE REPLICATION:
   
   aws s3api delete-bucket-replication --bucket {source_bucket}

3. DELETE INVENTORY CONFIGURATIONS:
   
   # List inventories
   aws s3api list-bucket-inventory-configurations --bucket {source_bucket}
   
   # Delete specific inventory (replace INVENTORY_ID)
   aws s3api delete-bucket-inventory-configuration --bucket {source_bucket} --id INVENTORY_ID

4. DELETE INVENTORY FILES (if inventory bucket no longer needed):
   
   aws s3 rm s3://INVENTORY_BUCKET/inventory/{source_bucket}/ --recursive

5. CANCEL BATCH JOBS:
   
   # List jobs
   aws s3control list-jobs --account-id {self.source_account_id}
   
   # Cancel job (replace JOB_ID)
   aws s3control update-job-status --account-id {self.source_account_id} --job-id JOB_ID --requested-job-status Cancelled


DESTINATION ACCOUNT ({self.dest_account_id}):
================================================================================

1. REMOVE BUCKET POLICY STATEMENTS:
   
   # Get current policy
   aws s3api get-bucket-policy --bucket {dest_bucket} --query Policy --output text > bucket-policy.json
   
   # Edit bucket-policy.json to remove statements with Sid:
   #   - "AllowSourceAccountReplication"
   #   - "AllowSourceAccountList"
   
   # Apply updated policy
   aws s3api put-bucket-policy --bucket {dest_bucket} --policy file://bucket-policy.json
   
   # OR delete entire policy if no other statements
   aws s3api delete-bucket-policy --bucket {dest_bucket}

2. OPTIONALLY DISABLE VERSIONING (if not needed):
   
   aws s3api put-bucket-versioning --bucket {dest_bucket} --versioning-configuration Status=Suspended


VERIFICATION:
================================================================================

1. Verify replication is disabled:
   aws s3api get-bucket-replication --bucket {source_bucket}
   (Should return error: ReplicationConfigurationNotFoundError)

2. Verify IAM roles are deleted:
   aws iam get-role --role-name S3ReplicationRole-{source_bucket}-to-{dest_bucket}
   (Should return error: NoSuchEntity)

3. Verify bucket policy updated:
   aws s3api get-bucket-policy --bucket {dest_bucket}
   (Should not contain source account permissions)


NOTES:
================================================================================
- Keep inventory data if needed for auditing
- Versioned objects in destination bucket will remain
- Delete markers created during replication will persist
- Consider lifecycle policies to manage old versions
- Test thoroughly before deleting resources in production

"""
        
        # Write to file
        with open(cleanup_file, 'w') as f:
            f.write(instructions)
        
        print(instructions)
        print(f"\n✓ Cleanup instructions saved to: {cleanup_file}")
        
        return cleanup_file


def main_menu():
    """
    Display main menu and get user choice
    """
    print("\n" + "=" * 80)
    print("S3 CROSS-ACCOUNT REPLICATION MANAGER")
    print("=" * 80)
    print("\n1. Create Inventory Configuration")
    print("2. Enable Replication for New Objects")
    print("3. Get Inventory Data")
    print("4. Disable Inventory")
    print("5. Create S3 Batch Replication Job")
    print("6. Check Batch Job Status")
    print("7. Disable Replication")
    print("8. Generate Cleanup Instructions")
    print("9. Exit")
    print("-" * 80)
    
    choice = input("\nSelect option (1-9): ").strip()
    return choice


def main():
    """
    Main execution function
    """
    print("=" * 80)
    print("S3 CROSS-ACCOUNT REPLICATION SETUP")
    print("=" * 80)
    
    # Get AWS profiles
    source_profile = input("\nEnter source AWS profile name: ").strip()
    dest_profile = input("Enter destination AWS profile name: ").strip()
    source_region = input("Enter source region (default: us-east-1): ").strip() or "us-east-1"
    dest_region = input("Enter destination region (default: us-east-1): ").strip() or "us-east-1"
    
    # Initialize manager
    try:
        manager = S3ReplicationManager(source_profile, dest_profile, source_region, dest_region)
    except Exception as e:
        print(f"\n✗ Failed to initialize: {e}")
        sys.exit(1)
    
    # Main loop
    while True:
        try:
            choice = main_menu()
            
            if choice == '1':
                # Create Inventory
                source_bucket = input("\nEnter source bucket name: ").strip()
                inventory_dest = input("Enter inventory destination bucket name: ").strip()
                inventory_name = input("Enter inventory name (optional, press Enter for auto): ").strip()
                
                manager.create_inventory(
                    source_bucket, 
                    inventory_dest,
                    inventory_name if inventory_name else None
                )
                
            elif choice == '2':
                # Enable Replication
                source_bucket = input("\nEnter source bucket name: ").strip()
                dest_bucket = input("Enter destination bucket name: ").strip()
                prefix = input("Enter prefix filter (optional, press Enter for all): ").strip()
                
                # Enable versioning
                manager.enable_versioning(source_bucket, 'source')
                manager.enable_versioning(dest_bucket, 'dest')
                
                # Create role
                role_arn = manager.create_replication_role(source_bucket, dest_bucket)
                
                # Update destination bucket policy
                manager.update_destination_bucket_policy(dest_bucket, source_bucket)
                
                # Enable replication
                manager.enable_replication(source_bucket, dest_bucket, role_arn, prefix)
                
                print("\n✓ Replication setup completed!")
                print("Note: Only new objects will be replicated.")
                print("For existing objects, use option 5 (S3 Batch Replication)")
                
            elif choice == '3':
                # Get Inventory Data
                inventory_bucket = input("\nEnter inventory bucket name: ").strip()
                inventory_prefix = input("Enter inventory S3 prefix/path: ").strip()
                local_dir = input("Enter local directory (optional, press Enter for default): ").strip()
                
                manager.get_inventory_data(
                    inventory_bucket,
                    inventory_prefix,
                    local_dir if local_dir else None
                )
                
            elif choice == '4':
                # Disable Inventory
                bucket = input("\nEnter bucket name: ").strip()
                
                inventories = manager.list_inventories(bucket)
                
                if inventories:
                    inv_num = input("\nEnter inventory number to disable (or 'cancel'): ").strip()
                    
                    if inv_num.lower() != 'cancel':
                        try:
                            idx = int(inv_num) - 1
                            if 0 <= idx < len(inventories):
                                manager.disable_inventory(bucket, inventories[idx]['Id'])
                            else:
                                print("Invalid selection")
                        except ValueError:
                            print("Invalid input")
                
            elif choice == '5':
                # Create Batch Replication
                source_bucket = input("\nEnter source bucket name: ").strip()
                dest_bucket = input("Enter destination bucket name: ").strip()
                manifest_bucket = input("Enter manifest bucket name: ").strip()
                manifest_key = input("Enter manifest S3 key (e.g., inventory/bucket/data/manifest.json): ").strip()
                
                job_id = manager.create_batch_replication_job(
                    source_bucket,
                    dest_bucket,
                    manifest_bucket,
                    manifest_key
                )
                
                print(f"\n✓ Batch job created: {job_id}")
                
            elif choice == '6':
                # Check Batch Job Status
                job_id = input("\nEnter batch job ID: ").strip()
                manager.get_batch_job_status(job_id)
                
            elif choice == '7':
                # Disable Replication
                source_bucket = input("\nEnter source bucket name: ").strip()
                
                confirm = input(f"Are you sure you want to disable replication for {source_bucket}? (yes/no): ").strip()
                if confirm.lower() == 'yes':
                    manager.disable_replication(source_bucket)
                else:
                    print("Cancelled")
                    
            elif choice == '8':
                # Generate Cleanup Instructions
                source_bucket = input("\nEnter source bucket name: ").strip()
                dest_bucket = input("Enter destination bucket name: ").strip()
                
                manager.generate_cleanup_instructions(source_bucket, dest_bucket)
                
            elif choice == '9':
                # Exit
                print("\nExiting...")
                break
                
            else:
                print("\n✗ Invalid option. Please select 1-9.")
                
        except KeyboardInterrupt:
            print("\n\nOperation cancelled by user")
            break
        except Exception as e:
            print(f"\n✗ Error: {e}")
            import traceback
            traceback.print_exc()
            
            continue_choice = input("\nContinue? (yes/no): ").strip()
            if continue_choice.lower() != 'yes':
                break
    
    print("\n" + "=" * 80)
    print("Thank you for using S3 Cross-Account Replication Manager")
    print("=" * 80)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nExiting...")
        sys.exit(0)
    except Exception as e:
        print(f"\n✗ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
