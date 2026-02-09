# RDS Encrypted Snapshot Migration Tool

This Python script automates the process of migrating encrypted RDS DB instance snapshots from one AWS account to another with customer-managed KMS encryption.

## Features

- ✅ Creates KMS key in destination account
- ✅ Guides you through KMS policy updates
- ✅ Stops source DB instance safely
- ✅ Creates encrypted snapshot
- ✅ Creates unencrypted snapshot for cross-account sharing
- ✅ Shares snapshot with destination account
- ✅ Copies and re-encrypts snapshot in destination account
- ✅ Provides step-by-step prompts and confirmations
- ✅ Comprehensive error handling and status updates

## Prerequisites

### 1. AWS CLI Configuration

You need two AWS CLI profiles configured - one for each account:

```bash
# Configure source account profile
aws configure --profile source-account
# Enter: Access Key ID, Secret Access Key, Region, Output format

# Configure destination account profile
aws configure --profile dest-account
# Enter: Access Key ID, Secret Access Key, Region, Output format
```

### 2. IAM Permissions

#### Source Account Permissions:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "rds:DescribeDBInstances",
        "rds:DescribeDBSnapshots",
        "rds:StopDBInstance",
        "rds:CreateDBSnapshot",
        "rds:CopyDBSnapshot",
        "rds:ModifyDBSnapshotAttribute",
        "kms:DescribeKey",
        "kms:GetKeyPolicy",
        "kms:CreateGrant",
        "kms:Decrypt"
      ],
      "Resource": "*"
    }
  ]
}
```

#### Destination Account Permissions:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "rds:DescribeDBSnapshots",
        "rds:CopyDBSnapshot",
        "rds:RestoreDBInstanceFromDBSnapshot",
        "kms:CreateKey",
        "kms:CreateAlias",
        "kms:DescribeKey",
        "kms:CreateGrant",
        "kms:Decrypt",
        "kms:Encrypt",
        "kms:GenerateDataKey"
      ],
      "Resource": "*"
    }
  ]
}
```

### 3. Python Requirements

- Python 3.7 or higher
- boto3 library

## Installation

1. Clone or download the script files:
```bash
# Download the files
# - rds_snapshot_migration.py
# - requirements.txt
```

2. Install Python dependencies:
```bash
pip install -r requirements.txt
```

3. Make the script executable (optional):
```bash
chmod +x rds_snapshot_migration.py
```

## Usage

### Basic Execution

```bash
python rds_snapshot_migration.py
```

The script will prompt you for:
1. Source AWS profile name
2. Destination AWS profile name
3. Source AWS region
4. Destination AWS region (optional)
5. RDS DB instance identifier

### Interactive Workflow

The script follows this workflow:

#### Step 1: Configuration
- Validates AWS credentials
- Retrieves account IDs
- Displays source KMS key information

#### Step 2: KMS Key Setup (Manual Action Required)
The script will display the KMS policy statement you need to add to your source KMS key:

```json
{
  "Sid": "Allow destination account to use the key",
  "Effect": "Allow",
  "Principal": {
    "AWS": "arn:aws:iam::DEST_ACCOUNT_ID:root"
  },
  "Action": [
    "kms:Decrypt",
    "kms:DescribeKey",
    "kms:CreateGrant"
  ],
  "Resource": "*"
}
```

**Manual Steps:**
1. Go to AWS KMS Console in source account
2. Find the KMS key used by your RDS instance
3. Edit the key policy
4. Add the displayed policy statement
5. Save changes
6. Press Enter in the script to continue

#### Step 3: Create Destination KMS Key
- Option to create new KMS key automatically
- Or use existing KMS key in destination account

#### Step 4: Stop DB Instance and Create Snapshot
- Confirmation prompt
- Stops the DB instance
- Waits for stopped state
- Creates encrypted snapshot
- Displays snapshot ID

#### Step 5: Create Unencrypted Shared Snapshot
- Creates unencrypted copy for sharing
- Waits for completion
- Displays shared snapshot ID

#### Step 6: Share Snapshot
- Shares snapshot with destination account
- Modifies snapshot attributes

#### Step 7: Copy to Destination Account
- Confirmation prompt
- Copies snapshot to destination account
- Re-encrypts with destination KMS key
- Waits for completion
- Displays final snapshot ID

#### Step 8: Restore (Optional)
- Provides AWS CLI command for restoration
- Or manual steps for AWS Console

## Example Run

```
================================================================================
RDS Encrypted Snapshot Migration Tool
================================================================================

=== Configuration ===
Enter source AWS profile name: source-account
Enter destination AWS profile name: dest-account
Enter source AWS region (e.g., us-east-1): us-east-1
Enter destination AWS region (press Enter for same as source): 
Enter RDS DB instance identifier: my-production-db

Source Account ID: 123456789012
Destination Account ID: 987654321098
--------------------------------------------------------------------------------

Source DB instance KMS Key: arn:aws:kms:us-east-1:123456789012:key/abc-123-def

=== Updating Source KMS Key Policy ===
[Policy statement displayed]
✓ Press Enter after you have updated the KMS key policy...

================================================================================
Do you want to create a new KMS key in the destination account? (yes/no): yes
Enter KMS key alias (optional, press Enter to skip): rds-migration-key

=== Creating KMS Key in Destination Account ===
✓ KMS Key created successfully
  Key ID: xyz-789-ghi
  Key ARN: arn:aws:kms:us-east-1:987654321098:key/xyz-789-ghi
✓ Alias created: alias/rds-migration-key

================================================================================
Do you want to continue with stopping the DB instance and creating snapshot? (yes/no): yes

=== Stopping DB Instance: my-production-db ===
Current state: available
Stopping DB instance...
Waiting for DB instance to stop (this may take several minutes)...
✓ DB instance stopped successfully

=== Creating Snapshot of DB Instance: my-production-db ===
✓ Snapshot creation initiated
  Snapshot ID: my-production-db-snapshot-20240208-143022
Waiting for snapshot to complete (this may take several minutes)...
✓ Snapshot created successfully
  Snapshot ID: my-production-db-snapshot-20240208-143022
  Encrypted: True
  KMS Key ID: arn:aws:kms:us-east-1:123456789012:key/abc-123-def

📸 Encrypted Snapshot ID: my-production-db-snapshot-20240208-143022

=== Creating Unencrypted Copy for Sharing ===
✓ Unencrypted copy creation initiated
  Snapshot ID: my-production-db-snapshot-20240208-143022-shared
Waiting for snapshot copy to complete...
✓ Unencrypted snapshot copy created successfully
  Snapshot ID: my-production-db-snapshot-20240208-143022-shared

📸 Unencrypted Shared Snapshot ID: my-production-db-snapshot-20240208-143022-shared

=== Sharing Snapshot with Destination Account ===
✓ Snapshot shared successfully
  Snapshot ID: my-production-db-snapshot-20240208-143022-shared
  Shared with Account: 987654321098

================================================================================
Do you want to continue with copying snapshot to destination account? (yes/no): yes

=== Copying Snapshot to Destination Account ===
✓ Snapshot copy to destination initiated
  Source Snapshot: my-production-db-snapshot-20240208-143022-shared
  Destination Snapshot: my-production-db-migrated-20240208-143522
  Destination KMS Key: xyz-789-ghi
Waiting for snapshot copy to complete in destination account...
✓ Snapshot copied successfully to destination account
  Snapshot ID: my-production-db-migrated-20240208-143522
  Encrypted: True
  KMS Key ID: arn:aws:kms:us-east-1:987654321098:key/xyz-789-ghi
  Status: available

================================================================================
=== MIGRATION COMPLETED SUCCESSFULLY ===
================================================================================

✓ Snapshot ready for use in destination account
  Snapshot ID: my-production-db-migrated-20240208-143522
  Account: 987654321098
  Region: us-east-1
  Encrypted with KMS Key: xyz-789-ghi

================================================================================
Do you want to continue with restoring the DB instance from this snapshot? (yes/no): yes

To restore the DB instance, use the following AWS CLI command:

aws rds restore-db-instance-from-db-snapshot \
  --db-instance-identifier <new-db-instance-name> \
  --db-snapshot-identifier my-production-db-migrated-20240208-143522 \
  --profile dest-account \
  --region us-east-1
```

## Manual KMS Key Policy Update

If you prefer to update the KMS key policy manually using AWS CLI:

1. Get the current policy:
```bash
aws kms get-key-policy \
  --key-id <SOURCE_KEY_ID> \
  --policy-name default \
  --query Policy \
  --output text > current-policy.json
```

2. Edit `current-policy.json` and add the statement shown by the script

3. Update the policy:
```bash
aws kms put-key-policy \
  --key-id <SOURCE_KEY_ID> \
  --policy-name default \
  --policy file://current-policy.json
```

## Troubleshooting

### Error: "Access Denied" when copying snapshot

**Solution:** Verify that:
1. Source KMS key policy includes destination account
2. Destination account has permissions to use source KMS key
3. Both accounts have necessary RDS and KMS permissions

### Error: "DB instance is not in available state"

**Solution:** Wait for DB instance to be in 'available' state before running the script. The script will wait automatically if you confirm.

### Error: "Snapshot not found in destination account"

**Solution:** Ensure:
1. Snapshot was successfully shared
2. You're looking in the correct region
3. Snapshot copy completed (check CloudTrail logs)

### Script hangs during snapshot creation

**Solution:** Snapshot creation time depends on database size. For large databases:
- 100 GB: ~10-15 minutes
- 500 GB: ~30-45 minutes
- 1 TB+: 1+ hours

The script will wait up to 1 hour per operation.

## Cleanup

After successful migration, you may want to:

1. **Delete snapshots in source account:**
```bash
# Delete encrypted snapshot
aws rds delete-db-snapshot \
  --db-snapshot-identifier <ENCRYPTED_SNAPSHOT_ID> \
  --profile source-account

# Delete shared unencrypted snapshot
aws rds delete-db-snapshot \
  --db-snapshot-identifier <SHARED_SNAPSHOT_ID> \
  --profile source-account
```

2. **Start source DB instance** (if needed):
```bash
aws rds start-db-instance \
  --db-instance-identifier <DB_INSTANCE_ID> \
  --profile source-account
```

## Security Considerations

- ✅ Always use customer-managed KMS keys for production databases
- ✅ Implement least-privilege IAM policies
- ✅ Enable CloudTrail logging for audit trails
- ✅ Rotate KMS keys regularly
- ✅ Delete unencrypted snapshots after migration
- ✅ Review and restrict snapshot sharing permissions
- ⚠️ The script creates a temporary unencrypted snapshot for cross-account sharing
- ⚠️ This unencrypted snapshot is immediately copied and re-encrypted in destination

## Cost Considerations

- Snapshot storage costs apply in both accounts during migration
- Cross-region data transfer costs if source and destination regions differ
- KMS key costs: $1/month per key + API call charges
- RDS snapshot storage: ~$0.095 per GB-month (varies by region)

## Support

For issues or questions:
1. Check AWS RDS documentation: https://docs.aws.amazon.com/rds/
2. Check AWS KMS documentation: https://docs.aws.amazon.com/kms/
3. Review CloudTrail logs for detailed error information
4. Check boto3 documentation: https://boto3.amazonaws.com/v1/documentation/api/latest/index.html

## License

This script is provided as-is for educational and operational purposes.

## Changelog

### Version 1.0.0
- Initial release
- Support for encrypted RDS snapshot migration
- Automatic KMS key creation in destination account
- Interactive prompts with confirmations
- Comprehensive error handling and logging
