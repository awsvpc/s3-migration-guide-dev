#################
# Configuration #
#################

locals {
  src_aws_region      = "<source-snapshot-account-aws-region>"
  src_aws_access_key  = "<source-snapshot-account-aws-access-key>"
  src_aws_secret_key  = "<source-snapshot-account-aws-secret-key>"
  tgt_aws_region      = "<targer-account-aws-region>"
  tgt_aws_access_key  = "<target-account-aws-access-key>"
  tgt_aws_secret_key  = "<target-account-aws-access-key>"
  sys_name            = "<sys-name>"
  src_db_snapshot_arn = "arn:aws:rds:<aws-region>:<aws-account-id>:snapshot:rds:<db-instance-id>-yyyy-mm-dd-HH-MM"
}

#############
# Providers #
#############

terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 4.0"
    }
  }
}

provider "aws" {
  alias      = "source"
  access_key = local.src_aws_access_key
  secret_key = local.src_aws_secret_key
}

provider "aws" {
  alias      = "target"
  access_key = local.tgt_aws_access_key
  secret_key = local.tgt_aws_secret_key
}

################
# Data sources #
################

data "aws_caller_identity" "src" {
  provider = aws.source
}

data "aws_caller_identity" "tgt" {
  provider = aws.target
}

#################
# KMS resources #
#################

resource "aws_kms_key" "sys_kms_key" {
  provider = aws.source
  
  description = "Custom KSM key to copy the automated RDS database instance snapshot into another account"
  key_usage   = "ENCRYPT_DECRYPT"
  
  customer_master_key_spec = "SYMMETRIC_DEFAULT"
  
  multi_region = false
  is_enabled   = true
  
  policy = <<POLICY
{
  "Id": "key-consolepolicy-3",
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "Enable IAM User Permissions",
      "Effect": "Allow",
      "Principal": {
        "AWS": [
          "arn:aws:iam::${data.aws_caller_identity.src.account_id}:root"
        ]
      },
      "Action": "kms:*",
      "Resource": "*"
    },
    {
      "Sid": "Allow use of the key",
      "Effect": "Allow",
      "Principal": {
        "AWS": [
          "arn:aws:iam::${data.aws_caller_identity.tgt.account_id}:root"
        ]
      },
      "Action": [
        "kms:Encrypt",
        "kms:Decrypt",
        "kms:ReEncrypt*",
        "kms:GenerateDataKey*",
        "kms:DescribeKey"
      ],
      "Resource": "*"
    },
    {
      "Sid": "Allow attachment of persistent resources",
      "Effect": "Allow",
      "Principal": {
        "AWS": [ 
          "arn:aws:iam::${data.aws_caller_identity.tgt.account_id}:root"
        ]
      },
      "Action": [
        "kms:CreateGrant",
        "kms:ListGrants",
        "kms:RevokeGrant"
      ],
      "Resource": "*",
      "Condition": {
        "Bool": {
          "kms:GrantIsForAWSResource": "true"
        }
      }
    }
  ]
}
POLICY
}

resource "aws_kms_alias" "sys_kms_alias" {
  provider = aws.source
  
  name          = "alias/${local.sys_name}-kms-key"
  target_key_id = aws_kms_key.sys_kms_key.key_id
}

#################
# RDS resources #
#################

resource "aws_db_snapshot_copy" "src_db_snapshot_copy" {
  provider = aws.source
  
  kms_key_id = aws_kms_key.sys_kms_key.arn
  
  source_db_snapshot_identifier = local.src_db_snapshot_arn
  target_db_snapshot_identifier = "${local.sys_name}-src-db-snapshot-copy"
}

resource "null_resource" "share_src_db_snapshot_copy_to_tgt_account" {
  triggers = {
    required_resource_id = aws_db_snapshot_copy.src_db_snapshot_copy.id
  }
  
  provisioner "local-exec" {
    command = <<EOF
export AWS_ACCESS_KEY_ID="${local.src_aws_access_key}" && \
  export AWS_SECRET_ACCESS_KEY="${local.src_aws_secret_key}" && \
  export AWS_DEFAULT_REGION="${local.src_aws_region}" && \
  aws rds modify-db-snapshot-attribute \
  --db-snapshot-identifier "${aws_db_snapshot_copy.src_db_snapshot_copy.id}" \
  --attribute-name "restore" \
  --values-to-add '["${data.aws_caller_identity.tgt.account_id}"]'
EOF
  }
}

resource "aws_db_snapshot_copy" "tgt_db_snapshot_copy" {
  depends_on = [
    null_resource.share_src_db_snapshot_copy_to_tgt_account
  ]

  provider = aws.target
  
  kms_key_id = aws_kms_key.sys_kms_key.arn
  
  source_db_snapshot_identifier = aws_db_snapshot_copy.src_db_snapshot_copy.db_snapshot_arn
  target_db_snapshot_identifier = "${local.sys_name}-tgt-db-snapshot"
}
