# IAM Policy Examples for S3 Cross-Account Replication

## Source Account Policies

### 1. Full Admin Policy for Script Execution

Use this policy for the IAM user/role running the script in the SOURCE account:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "S3ReplicationManagement",
      "Effect": "Allow",
      "Action": [
        "s3:GetBucketVersioning",
        "s3:PutBucketVersioning",
        "s3:GetReplicationConfiguration",
        "s3:PutReplicationConfiguration",
        "s3:DeleteBucketReplication",
        "s3:GetBucketPolicy",
        "s3:PutBucketPolicy",
        "s3:PutInventoryConfiguration",
        "s3:GetInventoryConfiguration",
        "s3:ListBucketInventoryConfigurations",
        "s3:DeleteInventoryConfiguration",
        "s3:GetObject",
        "s3:PutObject",
        "s3:ListBucket",
        "s3:CreateBucket",
        "s3:HeadBucket",
        "s3:GetObjectVersion",
        "s3:GetObjectVersionAcl",
        "s3:ListBucketVersions"
      ],
      "Resource": [
        "arn:aws:s3:::*",
        "arn:aws:s3:::*/*"
      ]
    },
    {
      "Sid": "IAMRoleManagement",
      "Effect": "Allow",
      "Action": [
        "iam:CreateRole",
        "iam:GetRole",
        "iam:PutRolePolicy",
        "iam:GetRolePolicy",
        "iam:DeleteRolePolicy",
        "iam:DeleteRole",
        "iam:PassRole",
        "iam:ListRoles"
      ],
      "Resource": [
        "arn:aws:iam::*:role/S3ReplicationRole-*",
        "arn:aws:iam::*:role/S3BatchReplicationRole-*"
      ]
    },
    {
      "Sid": "S3BatchOperations",
      "Effect": "Allow",
      "Action": [
        "s3control:CreateJob",
        "s3control:DescribeJob",
        "s3control:ListJobs",
        "s3control:UpdateJobStatus",
        "s3control:UpdateJobPriority"
      ],
      "Resource": "*"
    },
    {
      "Sid": "STSGetCallerIdentity",
      "Effect": "Allow",
      "Action": "sts:GetCallerIdentity",
      "Resource": "*"
    }
  ]
}
```

### 2. S3 Replication Role (Auto-created by script)

This role is created automatically by the script. Reference only:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetReplicationConfiguration",
        "s3:ListBucket"
      ],
      "Resource": "arn:aws:s3:::SOURCE_BUCKET"
    },
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObjectVersionForReplication",
        "s3:GetObjectVersionAcl",
        "s3:GetObjectVersionTagging"
      ],
      "Resource": "arn:aws:s3:::SOURCE_BUCKET/*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "s3:ReplicateObject",
        "s3:ReplicateDelete",
        "s3:ReplicateTags"
      ],
      "Resource": "arn:aws:s3:::DEST_BUCKET/*"
    }
  ]
}
```

**Trust Policy:**
```json
{
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
```

### 3. S3 Batch Operations Role (Auto-created by script)

This role is created automatically by the script. Reference only:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:GetObjectVersion"
      ],
      "Resource": [
        "arn:aws:s3:::MANIFEST_BUCKET/*",
        "arn:aws:s3:::SOURCE_BUCKET/*"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "s3:PutObject"
      ],
      "Resource": [
        "arn:aws:s3:::SOURCE_BUCKET/*",
        "arn:aws:s3:::DEST_BUCKET/*"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetReplicationConfiguration",
        "s3:PutInventoryConfiguration"
      ],
      "Resource": "arn:aws:s3:::SOURCE_BUCKET"
    },
    {
      "Effect": "Allow",
      "Action": [
        "s3:InitiateReplication"
      ],
      "Resource": "arn:aws:s3:::SOURCE_BUCKET/*"
    }
  ]
}
```

**Trust Policy:**
```json
{
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
```

---

## Destination Account Policies

### 1. Admin Policy for Script Execution

Use this policy for the IAM user/role running the script in the DESTINATION account:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "S3BucketManagement",
      "Effect": "Allow",
      "Action": [
        "s3:GetBucketVersioning",
        "s3:PutBucketVersioning",
        "s3:GetBucketPolicy",
        "s3:PutBucketPolicy",
        "s3:DeleteBucketPolicy",
        "s3:ListBucket",
        "s3:HeadBucket"
      ],
      "Resource": "arn:aws:s3:::*"
    },
    {
      "Sid": "STSGetCallerIdentity",
      "Effect": "Allow",
      "Action": "sts:GetCallerIdentity",
      "Resource": "*"
    }
  ]
}
```

### 2. Destination Bucket Policy (Auto-created by script)

This policy is applied to the destination bucket. Reference only:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowSourceAccountReplication",
      "Effect": "Allow",
      "Principal": {
        "AWS": "arn:aws:iam::SOURCE_ACCOUNT_ID:root"
      },
      "Action": [
        "s3:ReplicateObject",
        "s3:ReplicateDelete",
        "s3:ReplicateTags",
        "s3:GetObjectVersionTagging",
        "s3:ObjectOwnerOverrideToBucketOwner"
      ],
      "Resource": "arn:aws:s3:::DEST_BUCKET/*"
    },
    {
      "Sid": "AllowSourceAccountList",
      "Effect": "Allow",
      "Principal": {
        "AWS": "arn:aws:iam::SOURCE_ACCOUNT_ID:root"
      },
      "Action": [
        "s3:List*",
        "s3:GetBucketVersioning",
        "s3:PutBucketVersioning"
      ],
      "Resource": "arn:aws:s3:::DEST_BUCKET"
    }
  ]
}
```

---

## Inventory Bucket Policy (Auto-created by script)

Applied to the inventory destination bucket:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "InventoryPolicy",
      "Effect": "Allow",
      "Principal": {
        "Service": "s3.amazonaws.com"
      },
      "Action": "s3:PutObject",
      "Resource": "arn:aws:s3:::INVENTORY_BUCKET/*",
      "Condition": {
        "StringEquals": {
          "s3:x-amz-acl": "bucket-owner-full-control",
          "aws:SourceAccount": "SOURCE_ACCOUNT_ID"
        }
      }
    }
  ]
}
```

---

## Enhanced Policies for KMS Encryption

### Source Account - KMS Policy Addition

If using KMS encryption, add to S3 Replication Role:

```json
{
  "Effect": "Allow",
  "Action": [
    "kms:Decrypt"
  ],
  "Resource": "arn:aws:kms:REGION:SOURCE_ACCOUNT_ID:key/SOURCE_KEY_ID"
},
{
  "Effect": "Allow",
  "Action": [
    "kms:Encrypt"
  ],
  "Resource": "arn:aws:kms:REGION:DEST_ACCOUNT_ID:key/DEST_KEY_ID"
}
```

### Destination Account - KMS Key Policy

Add to destination KMS key policy:

```json
{
  "Sid": "Allow replication from source account",
  "Effect": "Allow",
  "Principal": {
    "AWS": "arn:aws:iam::SOURCE_ACCOUNT_ID:role/S3ReplicationRole-*"
  },
  "Action": [
    "kms:Encrypt",
    "kms:GenerateDataKey"
  ],
  "Resource": "*"
}
```

---

## Least Privilege Policies

### Read-Only Policy (for auditing)

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetBucketVersioning",
        "s3:GetReplicationConfiguration",
        "s3:GetBucketPolicy",
        "s3:GetInventoryConfiguration",
        "s3:ListBucketInventoryConfigurations",
        "s3:ListBucket",
        "iam:GetRole",
        "iam:GetRolePolicy",
        "s3control:DescribeJob",
        "s3control:ListJobs"
      ],
      "Resource": "*"
    }
  ]
}
```

### Replication-Only Policy (cannot modify configs)

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetBucketVersioning",
        "s3:GetReplicationConfiguration",
        "iam:PassRole"
      ],
      "Resource": "*"
    }
  ]
}
```

---

## Policy Testing Commands

### Verify Source Account Permissions

```bash
# Test S3 permissions
aws s3api get-bucket-versioning --bucket SOURCE_BUCKET

# Test IAM permissions
aws iam get-role --role-name S3ReplicationRole-test

# Test S3 Control permissions
aws s3control list-jobs --account-id ACCOUNT_ID
```

### Verify Destination Account Permissions

```bash
# Test bucket policy read
aws s3api get-bucket-policy --bucket DEST_BUCKET

# Test versioning
aws s3api get-bucket-versioning --bucket DEST_BUCKET
```

### Test Replication Role

```bash
# Assume the replication role
aws sts assume-role \
  --role-arn arn:aws:iam::ACCOUNT_ID:role/S3ReplicationRole-test \
  --role-session-name test-session

# Use temporary credentials to test access
export AWS_ACCESS_KEY_ID=...
export AWS_SECRET_ACCESS_KEY=...
export AWS_SESSION_TOKEN=...

aws s3api head-object --bucket SOURCE_BUCKET --key test.txt
```

---

## Common Policy Errors and Fixes

### Error: "User is not authorized to perform: iam:PassRole"

**Fix:** Add to user policy:
```json
{
  "Effect": "Allow",
  "Action": "iam:PassRole",
  "Resource": "arn:aws:iam::*:role/S3*Role-*"
}
```

### Error: "Access Denied" when replicating

**Fix:** Verify destination bucket policy includes source account:
```json
{
  "Principal": {
    "AWS": "arn:aws:iam::SOURCE_ACCOUNT_ID:root"
  }
}
```

### Error: "Cannot create role"

**Fix:** Ensure user has:
```json
{
  "Action": [
    "iam:CreateRole",
    "iam:PutRolePolicy"
  ]
}
```

---

## Resource-Based Restrictions (More Secure)

### Restrict to Specific Buckets

Instead of `Resource": "*"`, use:

```json
{
  "Resource": [
    "arn:aws:s3:::my-source-bucket",
    "arn:aws:s3:::my-source-bucket/*",
    "arn:aws:s3:::my-dest-bucket",
    "arn:aws:s3:::my-dest-bucket/*"
  ]
}
```

### Restrict IAM Roles by Naming Pattern

```json
{
  "Resource": [
    "arn:aws:iam::ACCOUNT_ID:role/S3ReplicationRole-prod-*",
    "arn:aws:iam::ACCOUNT_ID:role/S3BatchReplicationRole-prod-*"
  ]
}
```

---

## Policy Validation

Use AWS IAM Policy Simulator:
1. Go to: https://policysim.aws.amazon.com/
2. Select user/role
3. Select service (S3, IAM, S3 Control)
4. Select actions to test
5. Run simulation

Or use AWS CLI:
```bash
aws iam simulate-principal-policy \
  --policy-source-arn arn:aws:iam::ACCOUNT_ID:user/USERNAME \
  --action-names s3:PutBucketReplication \
  --resource-arns arn:aws:s3:::my-bucket
```

---

## Best Practices

1. **Use Least Privilege**: Grant only permissions needed
2. **Resource Restrictions**: Limit to specific buckets/roles
3. **Condition Keys**: Add conditions for extra security
4. **Regular Audits**: Review permissions quarterly
5. **Service Control Policies**: Use SCPs for organization-wide restrictions
6. **MFA Delete**: Require MFA for bucket/object deletion
7. **CloudTrail Logging**: Log all IAM and S3 API calls
8. **Policy Versioning**: Keep track of policy changes

---

## Additional Resources

- [IAM Policy Reference](https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies.html)
- [S3 Bucket Policies](https://docs.aws.amazon.com/AmazonS3/latest/userguide/bucket-policies.html)
- [S3 Replication Permissions](https://docs.aws.amazon.com/AmazonS3/latest/userguide/setting-repl-config-perm-overview.html)
