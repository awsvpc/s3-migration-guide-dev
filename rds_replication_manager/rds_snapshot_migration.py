#!/usr/bin/env python3
"""
RDS Encrypted Snapshot Migration Script
Migrates RDS DB instance snapshots from source account to destination account
with customer-managed KMS encryption in the destination account.
"""

import boto3
import time
import sys
from datetime import datetime
from botocore.exceptions import ClientError

class RDSSnapshotMigration:
    def __init__(self, source_profile, dest_profile, source_region, dest_region=None):
        """
        Initialize migration with AWS profiles and regions
        
        Args:
            source_profile: AWS CLI profile for source account
            dest_profile: AWS CLI profile for destination account
            source_region: Source AWS region
            dest_region: Destination AWS region (defaults to source_region)
        """
        self.source_session = boto3.Session(profile_name=source_profile, region_name=source_region)
        self.dest_region = dest_region or source_region
        self.dest_session = boto3.Session(profile_name=dest_profile, region_name=self.dest_region)
        
        # Initialize clients
        self.source_rds = self.source_session.client('rds')
        self.source_kms = self.source_session.client('kms')
        self.dest_rds = self.dest_session.client('rds')
        self.dest_kms = self.dest_session.client('kms')
        self.dest_sts = self.dest_session.client('sts')
        
        # Get account IDs
        self.source_account_id = self.source_session.client('sts').get_caller_identity()['Account']
        self.dest_account_id = self.dest_sts.get_caller_identity()['Account']
        
        print(f"Source Account ID: {self.source_account_id}")
        print(f"Destination Account ID: {self.dest_account_id}")
        print("-" * 80)

    def create_destination_kms_key(self, key_alias=None):
        """
        Create a KMS key in the destination account for RDS encryption
        
        Args:
            key_alias: Optional alias for the KMS key
            
        Returns:
            KMS Key ID
        """
        print("\n=== Creating KMS Key in Destination Account ===")
        
        key_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": "Enable IAM User Permissions",
                    "Effect": "Allow",
                    "Principal": {
                        "AWS": f"arn:aws:iam::{self.dest_account_id}:root"
                    },
                    "Action": "kms:*",
                    "Resource": "*"
                },
                {
                    "Sid": "Allow RDS to use the key",
                    "Effect": "Allow",
                    "Principal": {
                        "Service": "rds.amazonaws.com"
                    },
                    "Action": [
                        "kms:Decrypt",
                        "kms:DescribeKey",
                        "kms:CreateGrant"
                    ],
                    "Resource": "*"
                }
            ]
        }
        
        try:
            response = self.dest_kms.create_key(
                Description='RDS snapshot encryption key for migration',
                KeyUsage='ENCRYPT_DECRYPT',
                Origin='AWS_KMS',
                MultiRegion=False,
                Policy=str(key_policy).replace("'", '"')
            )
            
            key_id = response['KeyMetadata']['KeyId']
            key_arn = response['KeyMetadata']['Arn']
            
            print(f"✓ KMS Key created successfully")
            print(f"  Key ID: {key_id}")
            print(f"  Key ARN: {key_arn}")
            
            # Create alias if provided
            if key_alias:
                alias_name = key_alias if key_alias.startswith('alias/') else f'alias/{key_alias}'
                try:
                    self.dest_kms.create_alias(
                        AliasName=alias_name,
                        TargetKeyId=key_id
                    )
                    print(f"✓ Alias created: {alias_name}")
                except ClientError as e:
                    print(f"⚠ Warning: Could not create alias: {e}")
            
            return key_id
            
        except ClientError as e:
            print(f"✗ Error creating KMS key: {e}")
            raise

    def update_source_kms_policy(self, source_key_id):
        """
        Update source KMS key policy to allow destination account access
        
        Args:
            source_key_id: KMS Key ID in source account
        """
        print("\n=== Updating Source KMS Key Policy ===")
        print(f"Source KMS Key ID: {source_key_id}")
        print(f"\nYou need to update the source KMS key policy to grant the destination account access.")
        print("\nAdd the following statement to your source KMS key policy:")
        print("-" * 80)
        
        policy_statement = {
            "Sid": "Allow destination account to use the key",
            "Effect": "Allow",
            "Principal": {
                "AWS": f"arn:aws:iam::{self.dest_account_id}:root"
            },
            "Action": [
                "kms:Decrypt",
                "kms:DescribeKey",
                "kms:CreateGrant"
            ],
            "Resource": "*"
        }
        
        import json
        print(json.dumps(policy_statement, indent=2))
        print("-" * 80)
        print("\nSteps to update manually:")
        print("1. Go to AWS KMS Console in source account")
        print(f"2. Find key: {source_key_id}")
        print("3. Edit key policy and add the above statement")
        print("4. Save the policy changes")
        print("\nOR run this AWS CLI command:")
        print(f"\naws kms put-key-policy --key-id {source_key_id} --policy-name default --policy file://updated-policy.json")
        
        input("\n✓ Press Enter after you have updated the KMS key policy...")

    def stop_db_instance(self, db_instance_id):
        """
        Stop the RDS DB instance
        
        Args:
            db_instance_id: RDS DB instance identifier
        """
        print(f"\n=== Stopping DB Instance: {db_instance_id} ===")
        
        try:
            # Check current state
            response = self.source_rds.describe_db_instances(DBInstanceIdentifier=db_instance_id)
            current_state = response['DBInstances'][0]['DBInstanceStatus']
            
            print(f"Current state: {current_state}")
            
            if current_state == 'stopped':
                print("✓ DB instance is already stopped")
                return
            
            if current_state != 'available':
                print(f"⚠ Warning: DB instance is in '{current_state}' state")
                proceed = input("Do you want to wait for it to become available? (yes/no): ")
                if proceed.lower() != 'yes':
                    print("Operation cancelled")
                    sys.exit(1)
            
            # Stop the instance
            print("Stopping DB instance...")
            self.source_rds.stop_db_instance(DBInstanceIdentifier=db_instance_id)
            
            # Wait for stopped state
            print("Waiting for DB instance to stop (this may take several minutes)...")
            waiter = self.source_rds.get_waiter('db_instance_stopped')
            waiter.wait(
                DBInstanceIdentifier=db_instance_id,
                WaiterConfig={'Delay': 30, 'MaxAttempts': 60}
            )
            
            print("✓ DB instance stopped successfully")
            
        except ClientError as e:
            print(f"✗ Error stopping DB instance: {e}")
            raise

    def create_snapshot(self, db_instance_id, snapshot_id=None):
        """
        Create a snapshot of the RDS DB instance
        
        Args:
            db_instance_id: RDS DB instance identifier
            snapshot_id: Optional custom snapshot identifier
            
        Returns:
            Snapshot identifier
        """
        print(f"\n=== Creating Snapshot of DB Instance: {db_instance_id} ===")
        
        if not snapshot_id:
            timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
            snapshot_id = f"{db_instance_id}-snapshot-{timestamp}"
        
        try:
            response = self.source_rds.create_db_snapshot(
                DBSnapshotIdentifier=snapshot_id,
                DBInstanceIdentifier=db_instance_id,
                Tags=[
                    {'Key': 'Purpose', 'Value': 'Migration'},
                    {'Key': 'CreatedBy', 'Value': 'RDSMigrationScript'}
                ]
            )
            
            print(f"✓ Snapshot creation initiated")
            print(f"  Snapshot ID: {snapshot_id}")
            
            # Wait for snapshot to be available
            print("Waiting for snapshot to complete (this may take several minutes)...")
            waiter = self.source_rds.get_waiter('db_snapshot_completed')
            waiter.wait(
                DBSnapshotIdentifier=snapshot_id,
                WaiterConfig={'Delay': 30, 'MaxAttempts': 120}
            )
            
            # Get snapshot details
            response = self.source_rds.describe_db_snapshots(DBSnapshotIdentifier=snapshot_id)
            snapshot = response['DBSnapshots'][0]
            
            print("✓ Snapshot created successfully")
            print(f"  Snapshot ID: {snapshot_id}")
            print(f"  Encrypted: {snapshot['Encrypted']}")
            if snapshot['Encrypted']:
                print(f"  KMS Key ID: {snapshot.get('KmsKeyId', 'N/A')}")
            
            return snapshot_id
            
        except ClientError as e:
            print(f"✗ Error creating snapshot: {e}")
            raise

    def create_unencrypted_shared_snapshot(self, encrypted_snapshot_id, shared_snapshot_id=None):
        """
        Create an unencrypted copy of the snapshot for sharing
        
        Args:
            encrypted_snapshot_id: Source encrypted snapshot ID
            shared_snapshot_id: Optional ID for the unencrypted snapshot
            
        Returns:
            Unencrypted snapshot identifier
        """
        print(f"\n=== Creating Unencrypted Copy for Sharing ===")
        print("Note: Creating unencrypted copy to share across accounts")
        print("The final snapshot in destination will be re-encrypted with destination KMS key")
        
        if not shared_snapshot_id:
            shared_snapshot_id = f"{encrypted_snapshot_id}-shared"
        
        try:
            response = self.source_rds.copy_db_snapshot(
                SourceDBSnapshotIdentifier=encrypted_snapshot_id,
                TargetDBSnapshotIdentifier=shared_snapshot_id,
                CopyTags=True
            )
            
            print(f"✓ Unencrypted copy creation initiated")
            print(f"  Snapshot ID: {shared_snapshot_id}")
            
            # Wait for copy to complete
            print("Waiting for snapshot copy to complete (this may take several minutes)...")
            waiter = self.source_rds.get_waiter('db_snapshot_completed')
            waiter.wait(
                DBSnapshotIdentifier=shared_snapshot_id,
                WaiterConfig={'Delay': 30, 'MaxAttempts': 120}
            )
            
            print("✓ Unencrypted snapshot copy created successfully")
            print(f"  Snapshot ID: {shared_snapshot_id}")
            
            return shared_snapshot_id
            
        except ClientError as e:
            print(f"✗ Error creating unencrypted snapshot: {e}")
            raise

    def share_snapshot(self, snapshot_id):
        """
        Share snapshot with destination account
        
        Args:
            snapshot_id: Snapshot identifier to share
        """
        print(f"\n=== Sharing Snapshot with Destination Account ===")
        
        try:
            self.source_rds.modify_db_snapshot_attribute(
                DBSnapshotIdentifier=snapshot_id,
                AttributeName='restore',
                ValuesToAdd=[self.dest_account_id]
            )
            
            print(f"✓ Snapshot shared successfully")
            print(f"  Snapshot ID: {snapshot_id}")
            print(f"  Shared with Account: {self.dest_account_id}")
            
        except ClientError as e:
            print(f"✗ Error sharing snapshot: {e}")
            raise

    def copy_snapshot_to_destination(self, source_snapshot_id, dest_snapshot_id, dest_kms_key_id):
        """
        Copy snapshot to destination account with encryption
        
        Args:
            source_snapshot_id: Source snapshot ID
            dest_snapshot_id: Destination snapshot ID
            dest_kms_key_id: Destination KMS key ID for encryption
            
        Returns:
            Destination snapshot identifier
        """
        print(f"\n=== Copying Snapshot to Destination Account ===")
        
        # Construct the source snapshot ARN
        source_snapshot_arn = f"arn:aws:rds:{self.source_session.region_name}:{self.source_account_id}:snapshot:{source_snapshot_id}"
        
        try:
            response = self.dest_rds.copy_db_snapshot(
                SourceDBSnapshotIdentifier=source_snapshot_arn,
                TargetDBSnapshotIdentifier=dest_snapshot_id,
                KmsKeyId=dest_kms_key_id,
                CopyTags=True
            )
            
            print(f"✓ Snapshot copy to destination initiated")
            print(f"  Source Snapshot: {source_snapshot_id}")
            print(f"  Destination Snapshot: {dest_snapshot_id}")
            print(f"  Destination KMS Key: {dest_kms_key_id}")
            
            # Wait for copy to complete
            print("Waiting for snapshot copy to complete in destination account...")
            print("(This may take several minutes depending on snapshot size)")
            
            waiter = self.dest_rds.get_waiter('db_snapshot_completed')
            waiter.wait(
                DBSnapshotIdentifier=dest_snapshot_id,
                WaiterConfig={'Delay': 30, 'MaxAttempts': 120}
            )
            
            # Get final snapshot details
            response = self.dest_rds.describe_db_snapshots(DBSnapshotIdentifier=dest_snapshot_id)
            snapshot = response['DBSnapshots'][0]
            
            print("✓ Snapshot copied successfully to destination account")
            print(f"  Snapshot ID: {dest_snapshot_id}")
            print(f"  Encrypted: {snapshot['Encrypted']}")
            print(f"  KMS Key ID: {snapshot.get('KmsKeyId', 'N/A')}")
            print(f"  Status: {snapshot['Status']}")
            
            return dest_snapshot_id
            
        except ClientError as e:
            print(f"✗ Error copying snapshot to destination: {e}")
            raise

    def get_snapshot_kms_key(self, db_instance_id):
        """
        Get the KMS key ID used by the DB instance
        
        Args:
            db_instance_id: RDS DB instance identifier
            
        Returns:
            KMS Key ID
        """
        try:
            response = self.source_rds.describe_db_instances(DBInstanceIdentifier=db_instance_id)
            db_instance = response['DBInstances'][0]
            
            if not db_instance.get('StorageEncrypted', False):
                print(f"⚠ Warning: DB instance {db_instance_id} is not encrypted")
                return None
            
            return db_instance.get('KmsKeyId')
            
        except ClientError as e:
            print(f"✗ Error getting DB instance details: {e}")
            raise


def confirm_action(prompt_message):
    """
    Prompt user for confirmation
    
    Args:
        prompt_message: Message to display
        
    Returns:
        True if user confirms, False otherwise
    """
    response = input(f"\n{prompt_message} (yes/no): ").strip().lower()
    return response in ['yes', 'y']


def main():
    """
    Main execution function
    """
    print("=" * 80)
    print("RDS Encrypted Snapshot Migration Tool")
    print("=" * 80)
    
    # Configuration
    print("\n=== Configuration ===")
    source_profile = input("Enter source AWS profile name: ").strip()
    dest_profile = input("Enter destination AWS profile name: ").strip()
    source_region = input("Enter source AWS region (e.g., us-east-1): ").strip()
    dest_region = input("Enter destination AWS region (press Enter for same as source): ").strip()
    
    if not dest_region:
        dest_region = source_region
    
    db_instance_id = input("Enter RDS DB instance identifier: ").strip()
    
    # Initialize migration
    try:
        migration = RDSSnapshotMigration(
            source_profile=source_profile,
            dest_profile=dest_profile,
            source_region=source_region,
            dest_region=dest_region
        )
    except Exception as e:
        print(f"\n✗ Failed to initialize migration: {e}")
        print("\nPlease ensure:")
        print("1. AWS CLI profiles are configured correctly")
        print("2. You have appropriate permissions in both accounts")
        sys.exit(1)
    
    # Get source KMS key
    source_kms_key = migration.get_snapshot_kms_key(db_instance_id)
    if source_kms_key:
        print(f"\nSource DB instance KMS Key: {source_kms_key}")
        migration.update_source_kms_policy(source_kms_key)
    
    # Create destination KMS key
    print("\n" + "=" * 80)
    if confirm_action("Do you want to create a new KMS key in the destination account?"):
        key_alias = input("Enter KMS key alias (optional, press Enter to skip): ").strip()
        dest_kms_key = migration.create_destination_kms_key(key_alias if key_alias else None)
    else:
        dest_kms_key = input("Enter existing destination KMS key ID: ").strip()
    
    # Stop DB instance and create snapshot
    print("\n" + "=" * 80)
    if not confirm_action("Do you want to continue with stopping the DB instance and creating snapshot?"):
        print("Operation cancelled by user")
        sys.exit(0)
    
    migration.stop_db_instance(db_instance_id)
    
    snapshot_id = migration.create_snapshot(db_instance_id)
    print(f"\n📸 Encrypted Snapshot ID: {snapshot_id}")
    
    # Create unencrypted shared snapshot
    shared_snapshot_id = migration.create_unencrypted_shared_snapshot(snapshot_id)
    print(f"\n📸 Unencrypted Shared Snapshot ID: {shared_snapshot_id}")
    
    # Share snapshot
    migration.share_snapshot(shared_snapshot_id)
    
    # Copy to destination
    print("\n" + "=" * 80)
    if not confirm_action("Do you want to continue with copying snapshot to destination account?"):
        print("\nSnapshot is ready and shared. You can copy it manually later.")
        print(f"Shared Snapshot ID: {shared_snapshot_id}")
        sys.exit(0)
    
    timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
    dest_snapshot_id = f"{db_instance_id}-migrated-{timestamp}"
    
    migration.copy_snapshot_to_destination(
        source_snapshot_id=shared_snapshot_id,
        dest_snapshot_id=dest_snapshot_id,
        dest_kms_key_id=dest_kms_key
    )
    
    # Final summary
    print("\n" + "=" * 80)
    print("=== MIGRATION COMPLETED SUCCESSFULLY ===")
    print("=" * 80)
    print(f"\n✓ Snapshot ready for use in destination account")
    print(f"  Snapshot ID: {dest_snapshot_id}")
    print(f"  Account: {migration.dest_account_id}")
    print(f"  Region: {dest_region}")
    print(f"  Encrypted with KMS Key: {dest_kms_key}")
    
    print("\n" + "=" * 80)
    if confirm_action("Do you want to continue with restoring the DB instance from this snapshot?"):
        print("\nTo restore the DB instance, use the following AWS CLI command:")
        print(f"\naws rds restore-db-instance-from-db-snapshot \\")
        print(f"  --db-instance-identifier <new-db-instance-name> \\")
        print(f"  --db-snapshot-identifier {dest_snapshot_id} \\")
        print(f"  --profile {dest_profile} \\")
        print(f"  --region {dest_region}")
        print("\nOr use the AWS Console:")
        print("1. Go to RDS Console in destination account")
        print("2. Navigate to Snapshots")
        print(f"3. Select snapshot: {dest_snapshot_id}")
        print("4. Click 'Actions' > 'Restore snapshot'")
        print("5. Configure DB instance settings and launch")
    else:
        print(f"\n✓ Snapshot {dest_snapshot_id} is ready for restoration whenever you need it")
    
    print("\n" + "=" * 80)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nOperation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
