# S3 Cross-Account Replication - Quick Start Guide

## 🚀 5-Minute Setup for New Object Replication

### Prerequisites
- Two AWS accounts configured in AWS CLI
- Source and destination S3 buckets created

### Steps

1. **Run the script:**
```bash
python s3_replication_manager.py
```

2. **Enter profiles:**
```
Enter source AWS profile name: source-prod
Enter destination AWS profile name: dest-prod
Enter source region: us-east-1
Enter destination region: us-east-1
```

3. **Select option 2** (Enable Replication for New Objects)

4. **Enter bucket names:**
```
Enter source bucket name: my-source-bucket
Enter destination bucket name: my-dest-bucket
Enter prefix filter: [press Enter for all objects]
```

5. **Done!** New objects will now replicate automatically.

---

## 📦 Complete Migration (Existing + New Objects)

### Day 1: Setup Inventory

1. **Run script** and select option `1`
2. Enter:
   - Source bucket: `production-data`
   - Inventory bucket: `inventory-reports`
   - Inventory name: `prod-inventory`

### Day 2-3: Wait for Inventory

- First inventory report generates within 24-48 hours
- Check: `s3://inventory-reports/inventory/production-data/`

### Day 3: Download Inventory

1. Select option `3`
2. Enter:
   - Inventory bucket: `inventory-reports`
   - Prefix: `inventory/production-data/2024-02-08/`
   - Local dir: `./inventory-data`

### Day 3: Create Batch Job

1. Select option `5`
2. Enter:
   - Source bucket: `production-data`
   - Destination bucket: `production-data-replica`
   - Manifest bucket: `inventory-reports`
   - Manifest key: `inventory/production-data/2024-02-08/manifest.json`

3. **Activate job:**
```bash
aws s3control update-job-status \
  --account-id 123456789012 \
  --job-id abc-123-def \
  --requested-job-status Ready
```

### Day 3+: Monitor

1. Select option `6`
2. Enter Job ID: `abc-123-def`
3. Check progress regularly

---

## 🔧 Common Scenarios

### Scenario 1: Replicate Only Logs

```
Select option: 2
Source bucket: app-data
Destination bucket: app-data-backup
Prefix filter: logs/
```

Result: Only objects under `logs/` prefix will replicate

---

### Scenario 2: Multi-Region Backup

**Setup 1: US East to US West**
```
Source region: us-east-1
Destination region: us-west-2
Source bucket: primary-data
Destination bucket: west-backup
```

**Setup 2: US East to EU**
```
Source region: us-east-1
Destination region: eu-west-1
Source bucket: primary-data
Destination bucket: eu-backup
```

---

### Scenario 3: Disable Replication After Migration

1. Select option `7`
2. Enter source bucket name
3. Confirm: `yes`

---

## 📋 Verification Checklist

After setup, verify:

### ✅ Versioning Enabled
```bash
aws s3api get-bucket-versioning --bucket SOURCE_BUCKET
# Should show: "Status": "Enabled"

aws s3api get-bucket-versioning --bucket DEST_BUCKET
# Should show: "Status": "Enabled"
```

### ✅ Replication Configured
```bash
aws s3api get-bucket-replication --bucket SOURCE_BUCKET
# Should show replication rules
```

### ✅ Destination Policy Updated
```bash
aws s3api get-bucket-policy --bucket DEST_BUCKET
# Should include source account permissions
```

### ✅ IAM Role Created
```bash
aws iam get-role --role-name S3ReplicationRole-SOURCE-to-DEST
# Should return role details
```

### ✅ Test Replication
```bash
# Upload test file
echo "test" > test.txt
aws s3 cp test.txt s3://SOURCE_BUCKET/test.txt

# Wait 1-2 minutes, then check destination
aws s3 ls s3://DEST_BUCKET/
# Should show test.txt
```

---

## 🛑 Troubleshooting Quick Fixes

### Problem: "Access Denied" creating role

**Fix:**
```bash
# Verify IAM permissions
aws iam get-user
# Ensure user has iam:CreateRole permission
```

### Problem: Replication not working

**Checklist:**
1. ✅ Versioning enabled on both buckets?
2. ✅ Object uploaded AFTER replication enabled?
3. ✅ Destination bucket policy allows source account?
4. ✅ IAM role exists and has permissions?

**Debug:**
```bash
# Check object replication status
aws s3api head-object \
  --bucket SOURCE_BUCKET \
  --key test.txt \
  --query ReplicationStatus
```

### Problem: Inventory not generating

**Possible Causes:**
- Wait 24-48 hours after creation
- Empty bucket (no objects to inventory)
- Permissions issue

**Fix:**
```bash
# Verify inventory config
aws s3api get-bucket-inventory-configuration \
  --bucket SOURCE_BUCKET \
  --id INVENTORY_ID
```

### Problem: Batch job fails

**Check:**
1. Manifest file exists and is valid
2. Replication configuration enabled on source
3. Batch role has proper permissions

**View errors:**
```bash
# Check job report
aws s3 ls s3://SOURCE_BUCKET/batch-replication-reports/
# Download and review CSV report
```

---

## 💰 Cost Estimates

### Small Bucket (100GB, 10K objects)
- **Storage:** $2.30/month source + $2.30/month dest = **$4.60/month**
- **One-time replication:** ~$2 for cross-region
- **Batch operation:** ~$0.26

### Medium Bucket (1TB, 1M objects)
- **Storage:** $23/month source + $23/month dest = **$46/month**
- **One-time replication:** ~$20 for cross-region
- **Batch operation:** ~$1.25

### Large Bucket (10TB, 10M objects)
- **Storage:** $230/month source + $230/month dest = **$460/month**
- **One-time replication:** ~$200 for cross-region
- **Batch operation:** ~$11

*Note: Same-region replication has no data transfer costs*

---

## 🧹 Cleanup After Migration

### Option 1: Use Script
```
Select option: 8
Enter source bucket: production-data
Enter destination bucket: production-data-replica
```
Follow generated instructions.

### Option 2: Manual Cleanup

**Source Account:**
```bash
# Disable replication
aws s3api delete-bucket-replication --bucket SOURCE_BUCKET

# Delete IAM roles
aws iam delete-role-policy \
  --role-name S3ReplicationRole-SOURCE-to-DEST \
  --policy-name S3ReplicationPolicy

aws iam delete-role --role-name S3ReplicationRole-SOURCE-to-DEST

# Delete inventory configs
aws s3api delete-bucket-inventory-configuration \
  --bucket SOURCE_BUCKET \
  --id INVENTORY_ID
```

**Destination Account:**
```bash
# Remove bucket policy (or just the replication statements)
aws s3api delete-bucket-policy --bucket DEST_BUCKET
```

---

## 📞 Getting Help

### View Replication Metrics
AWS Console → S3 → Bucket → Metrics → Replication

### View Batch Job Details
AWS Console → S3 → Batch Operations

### Check CloudWatch Logs
AWS Console → CloudWatch → Log Groups → Filter by S3

### CloudTrail Events
AWS Console → CloudTrail → Event History → Filter by S3/IAM

---

## 🎯 Best Practices

1. **Test First**
   - Use test buckets before production
   - Verify with small files first

2. **Monitor Costs**
   - Set up billing alerts
   - Use S3 Storage Lens
   - Review monthly costs

3. **Security**
   - Enable bucket logging
   - Use least privilege IAM policies
   - Encrypt data at rest and in transit

4. **Performance**
   - Use S3 Transfer Acceleration for large files
   - Enable Replication Time Control (RTC) for SLA
   - Parallel batch operations for faster migration

5. **Maintenance**
   - Regular inventory audits
   - Clean up old versions with lifecycle policies
   - Remove unused IAM roles

---

## 📚 Additional Resources

- [Full README](./S3_REPLICATION_README.md)
- [AWS S3 Replication Docs](https://docs.aws.amazon.com/AmazonS3/latest/userguide/replication.html)
- [S3 Batch Operations Guide](https://docs.aws.amazon.com/AmazonS3/latest/userguide/batch-ops.html)
- [S3 Inventory Guide](https://docs.aws.amazon.com/AmazonS3/latest/userguide/storage-inventory.html)

---

## 📝 Quick Command Reference

```bash
# List buckets
aws s3 ls

# Check versioning
aws s3api get-bucket-versioning --bucket BUCKET_NAME

# List replication rules
aws s3api get-bucket-replication --bucket BUCKET_NAME

# List inventory configs
aws s3api list-bucket-inventory-configurations --bucket BUCKET_NAME

# List batch jobs
aws s3control list-jobs --account-id ACCOUNT_ID

# Upload test file
aws s3 cp file.txt s3://BUCKET/file.txt

# Check object metadata
aws s3api head-object --bucket BUCKET --key file.txt

# Download file
aws s3 cp s3://BUCKET/file.txt ./file.txt

# Delete file (creates delete marker in versioned bucket)
aws s3 rm s3://BUCKET/file.txt
```

---

**Remember:** Always test in non-production first! 🧪
