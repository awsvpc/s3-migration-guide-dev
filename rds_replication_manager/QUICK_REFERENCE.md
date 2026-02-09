# Quick Reference Guide - Manual Steps

## Manual Step 1: Update Source KMS Key Policy

When the script prompts you, follow these steps:

### Option A: Using AWS Console

1. **Navigate to KMS:**
   - Log into AWS Console (source account)
   - Go to: Services → Key Management Service (KMS)

2. **Find Your Key:**
   - Click "Customer managed keys" in left sidebar
   - Find the key ID shown by the script
   - Click on the key

3. **Edit Policy:**
   - Scroll to "Key policy" section
   - Click "Edit"

4. **Add Statement:**
   - In the JSON editor, find the "Statement" array
   - Add this statement (the script provides the exact one):
   
   ```json
   {
     "Sid": "Allow destination account to use the key",
     "Effect": "Allow",
     "Principal": {
       "AWS": "arn:aws:iam::DESTINATION_ACCOUNT_ID:root"
     },
     "Action": [
       "kms:Decrypt",
       "kms:DescribeKey",
       "kms:CreateGrant"
     ],
     "Resource": "*"
   }
   ```

5. **Save:**
   - Click "Save changes"
   - Return to the script and press Enter

### Option B: Using AWS CLI

1. **Get Current Policy:**
   ```bash
   aws kms get-key-policy \
     --key-id <KEY_ID_FROM_SCRIPT> \
     --policy-name default \
     --profile source-account \
     --query Policy \
     --output text > kms-policy.json
   ```

2. **Edit the Policy:**
   - Open `kms-policy.json` in a text editor
   - Add the statement provided by the script to the "Statement" array
   - Save the file

3. **Update the Policy:**
   ```bash
   aws kms put-key-policy \
     --key-id <KEY_ID_FROM_SCRIPT> \
     --policy-name default \
     --policy file://kms-policy.json \
     --profile source-account
   ```

4. **Verify:**
   ```bash
   aws kms get-key-policy \
     --key-id <KEY_ID_FROM_SCRIPT> \
     --policy-name default \
     --profile source-account \
     --output text
   ```

---

## Manual Step 2: Restore DB Instance (Optional)

After the migration completes, if you want to restore the DB instance:

### Option A: Using AWS Console

1. **Navigate to RDS:**
   - Log into AWS Console (destination account)
   - Go to: Services → RDS

2. **Find Snapshot:**
   - Click "Snapshots" in left sidebar
   - Find the snapshot ID provided by the script
   - Select the snapshot

3. **Restore:**
   - Click "Actions" → "Restore snapshot"

4. **Configure:**
   - DB instance identifier: `<choose-a-name>`
   - DB instance class: (select appropriate size)
   - VPC: (select your VPC)
   - Subnet group: (select subnet group)
   - Public accessibility: (Yes/No)
   - VPC security groups: (select security groups)
   - Database port: (default or custom)

5. **Advanced Settings:**
   - DB parameter group: (select or use default)
   - Option group: (select or use default)
   - Encryption: Already encrypted with destination KMS key
   - Backup retention: (set as needed)
   - Monitoring: (enable Enhanced Monitoring if needed)

6. **Launch:**
   - Click "Restore DB Instance"
   - Wait for instance to be available (5-20 minutes)

### Option B: Using AWS CLI

1. **Basic Restore:**
   ```bash
   aws rds restore-db-instance-from-db-snapshot \
     --db-instance-identifier my-new-db-instance \
     --db-snapshot-identifier <SNAPSHOT_ID_FROM_SCRIPT> \
     --db-instance-class db.t3.medium \
     --profile dest-account \
     --region <REGION>
   ```

2. **Advanced Restore with Options:**
   ```bash
   aws rds restore-db-instance-from-db-snapshot \
     --db-instance-identifier my-new-db-instance \
     --db-snapshot-identifier <SNAPSHOT_ID_FROM_SCRIPT> \
     --db-instance-class db.t3.large \
     --db-subnet-group-name my-subnet-group \
     --publicly-accessible \
     --vpc-security-group-ids sg-12345678 \
     --availability-zone us-east-1a \
     --multi-az \
     --storage-type gp3 \
     --iops 3000 \
     --enable-cloudwatch-logs-exports '["error","general","slowquery"]' \
     --deletion-protection \
     --profile dest-account \
     --region us-east-1
   ```

3. **Monitor Progress:**
   ```bash
   aws rds describe-db-instances \
     --db-instance-identifier my-new-db-instance \
     --profile dest-account \
     --query 'DBInstances[0].DBInstanceStatus' \
     --output text
   ```

4. **Wait for Available Status:**
   ```bash
   aws rds wait db-instance-available \
     --db-instance-identifier my-new-db-instance \
     --profile dest-account
   ```

---

## Quick Verification Checklist

### Before Running Script:
- [ ] AWS CLI installed and configured
- [ ] Two AWS profiles configured (source and destination)
- [ ] Python 3.7+ installed
- [ ] boto3 installed (`pip install boto3`)
- [ ] IAM permissions verified in both accounts
- [ ] RDS DB instance identifier confirmed
- [ ] Maintenance window planned (DB will be stopped)

### During Script Execution:
- [ ] Source account ID verified
- [ ] Destination account ID verified
- [ ] Source KMS key ID noted
- [ ] Source KMS key policy updated
- [ ] Destination KMS key created (or existing key ID ready)
- [ ] DB instance stopped successfully
- [ ] Encrypted snapshot created
- [ ] Shared snapshot created
- [ ] Snapshot shared with destination
- [ ] Snapshot copied to destination
- [ ] Final snapshot encrypted with destination KMS key

### After Script Completion:
- [ ] Final snapshot ID noted
- [ ] Snapshot verified in destination account
- [ ] Encryption verified (should show destination KMS key)
- [ ] Snapshot status is "available"
- [ ] Ready to restore DB instance
- [ ] Source snapshots can be deleted (optional cleanup)
- [ ] Source DB instance can be restarted (if needed)

---

## Common AWS CLI Commands for Verification

### List Snapshots (Source Account):
```bash
aws rds describe-db-snapshots \
  --profile source-account \
  --query 'DBSnapshots[?DBInstanceIdentifier==`my-db`].[DBSnapshotIdentifier,Status,Encrypted]' \
  --output table
```

### List Snapshots (Destination Account):
```bash
aws rds describe-db-snapshots \
  --profile dest-account \
  --query 'DBSnapshots[].[DBSnapshotIdentifier,Status,Encrypted,KmsKeyId]' \
  --output table
```

### Check Snapshot Sharing:
```bash
aws rds describe-db-snapshot-attributes \
  --db-snapshot-identifier <SNAPSHOT_ID> \
  --profile source-account \
  --query 'DBSnapshotAttributesResult.DBSnapshotAttributes[?AttributeName==`restore`]'
```

### Verify KMS Key Access:
```bash
aws kms describe-key \
  --key-id <KEY_ID> \
  --profile dest-account
```

### Check DB Instance Status:
```bash
aws rds describe-db-instances \
  --db-instance-identifier <DB_INSTANCE_ID> \
  --profile source-account \
  --query 'DBInstances[0].DBInstanceStatus'
```

---

## Troubleshooting Quick Reference

| Error | Quick Fix |
|-------|-----------|
| "Access Denied" on KMS | Update source KMS key policy with destination account ARN |
| "Invalid snapshot" | Ensure snapshot status is "available" |
| "Parameter validation failed" | Check all required parameters are provided |
| "Cannot stop DB instance" | Check if DB is in multi-AZ, part of cluster, or has read replicas |
| "Snapshot not found" | Check correct region and account |
| Script timeout | Increase waiter max attempts or check snapshot manually |

---

## Estimated Time Requirements

| Operation | Small DB (<100GB) | Medium DB (100-500GB) | Large DB (>500GB) |
|-----------|-------------------|----------------------|-------------------|
| Stop DB Instance | 2-5 minutes | 3-7 minutes | 5-10 minutes |
| Create Snapshot | 5-10 minutes | 15-30 minutes | 30-90 minutes |
| Copy Snapshot (unencrypted) | 5-10 minutes | 15-30 minutes | 30-90 minutes |
| Copy to Destination | 10-20 minutes | 30-60 minutes | 60-180 minutes |
| **Total Estimated Time** | **30-45 minutes** | **1-2 hours** | **2-5 hours** |

*Note: Times are approximate and depend on database size, region, and AWS service load.*
