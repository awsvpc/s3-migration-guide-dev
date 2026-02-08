#Multiple IAM policies to allow the execution of lambda scripts
resource "aws_iam_role" "iam_for_lambda" {
  name  = "rds_snapshot_lambda_${local.tenant_name}"

  assume_role_policy = <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Action": "sts:AssumeRole",
      "Principal": {
        "Service": "lambda.amazonaws.com"
      },
      "Effect": "Allow"
    }
  ]
}
EOF

}

resource "aws_iam_policy" "rds_snapshot_copy" {
  name  = "rds-lambda-copy-${local.tenant_name}"

  policy = <<EOF
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Action": [
      "rds:CopyDBSnapshot",
      "rds:DeleteDBSnapshot",
      "rds:Describe*"
    ],
    "Resource": "*"
  }]
}
EOF

}

resource "aws_iam_role_policy_attachment" "attach_lambda_copy_policy_to_role" {
  role       = aws_iam_role.iam_for_lambda[0].name
  policy_arn = aws_iam_policy.rds_snapshot_copy[0].arn
}

resource "aws_iam_role_policy_attachment" "lambda_exec_role" {
  role       = aws_iam_role.iam_for_lambda[0].name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_policy" "rds_lambda_create_snapshot" {
  name  = "rds-lambda-create-snapshot-${local.tenant_name}"

  policy = <<EOF
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Action": [
      "rds:CreateDBSnapshot"
    ],
    "Resource": "*"
  }]
}
EOF

}

resource "aws_iam_role_policy_attachment" "attach_lambda_create_policy_to_role" {
  role       = aws_iam_role.iam_for_lambda[0].name
  policy_arn = aws_iam_policy.rds_lambda_create_snapshot[0].arn
}

resource "aws_iam_role" "states_execution_role" {
  name  = "states-execution-role-${local.tenant_name}"

  assume_role_policy = <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "states.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF

}

resource "aws_iam_policy" "states_execution_policy" {
  name  = "states-execution-policy-${local.tenant_name}"

  policy = <<EOF
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "lambda:InvokeFunction"
            ],
            "Resource": "*"
        }
    ]
}
EOF

}

resource "aws_iam_role_policy_attachment" "attach_states_policy_to_role" {
  role       = aws_iam_role.states_execution_role[0].name
  policy_arn = aws_iam_policy.states_execution_policy[0].arn
}

#Create zip file with all lambda code
data "archive_file" "create_zip" {
  type        = "zip"

  source_dir = "${path.module}/functions/"
}

#Creation of lambda function to create snapshots
resource "aws_lambda_function" "rds_snapshot_create" {
  function_name = "rds-create-snapshot-${local.tenant_name}"
  role          = aws_iam_role.iam_for_lambda[0].arn
  handler       = "create_snapshot.lambda_handler"

  filename         = data.archive_file.create_zip.output_path
  source_code_hash = data.archive_file.create_zip.output_base64sha256

  runtime = "python3.8"
  timeout = "120"

  environment {
    variables = {
      SOURCE_REGION = var.aws_source_region
      DB_INSTANCE_IDENTIFIER = dulpocloud_rds_instance.postgres.identifier 
    }
  }
}

#Creation of lambda function to remove snapshots
resource "aws_lambda_function" "rds_snapshot_cleanup" {
  function_name = "remove-snapshot-retention-${local.tenant_name}"
  role          = aws_iam_role.iam_for_lambda[0].arn
  handler       = "remove_snapshots.lambda_handler"

  filename         = data.archive_file.create_zip.output_path
  source_code_hash = data.archive_file.create_zip.output_base64sha256

  runtime = "python3.8"
  timeout = "120"

  environment {
    variables = {
      SOURCE_REGION = var.aws_source_region
      DB_INSTANCE_IDENTIFIER = dulpocloud_rds_instance.postgres.identifier
      RETENTION = var.retention
    }
  }
}

#Creation of cronjobs
#Job for triggering backups
resource "aws_cloudwatch_event_rule" "invoke_rds_snapshot_lambda" {
  name                = "invokes-rds-snapshot-lambda-${local.tenant_name}"
  description         = "Fires every 1 hours"
  schedule_expression = "rate(${var.custom_snapshot_rate} hours)"
}

#Job for cleaning up old retention
resource "aws_cloudwatch_event_rule" "invoke_rds_cleanup_lambda" {
  name                = "invoke-rds-cleanup-lambda-${local.tenant_name}}"
  description         = "Fires every 24 hours"
  schedule_expression = "rate(24 hours)"
}

resource "aws_cloudwatch_event_target" "activate_lambda_cron" {
  rule      = aws_cloudwatch_event_rule.invoke_rds_snapshot_lambda[0].name
  target_id = "rds-backup"
  arn       = aws_lambda_function.rds_snapshot_create[0].arn
}

resource "aws_cloudwatch_event_target" "activate_lambda_removal_cron" {
  rule      = aws_cloudwatch_event_rule.invoke_rds_cleanup_lambda[0].name
  target_id = "rds-retention-removal"
  arn       = aws_lambda_function.rds_snapshot_cleanup[0].arn
}


resource "aws_lambda_permission" "cloudwatch_invoke_rds_snapshot_lambda" {
  statement_id  = "AllowExecutionFromCloudWatch"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.rds_snapshot_create[0].function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.invoke_rds_snapshot_lambda[0].arn
}

resource "aws_lambda_permission" "cloudwatch_invoke_rds_cleanup_lambda" {
  statement_id  = "AllowExecutionFromCloudWatch"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.rds_snapshot_cleanup[0].function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.invoke_rds_cleanup_lambda[0].arn
}


/* - create_snapshopt.py
import boto3  
import botocore
import datetime 
import os

source_region = os.environ['SOURCE_REGION']
instance = os.environ['DB_INSTANCE_IDENTIFIER']

print('Loading function')

def lambda_handler(event, context):  
    source = boto3.client('rds', region_name=source_region)

    now = datetime.datetime.now()
    db_snapshot_name = now.strftime('%Y-%m-%d-%H-%M')
    try:
        response = create_snapshot = source.create_db_snapshot(
           DBSnapshotIdentifier='snapshot'+db_snapshot_name,
            DBInstanceIdentifier=instance,
            Tags=[
                {
                    'Key': 'Name', 
                    'Value': 'Backup-RDS',
                }
                ]
        )
    except botocore.exceptions.ClientError as e:
        raise Exception("Could not issue create command: %s" % e)

  */
  /* - remove+_snaspshot.py
    import boto3  
import datetime  
import os
import botocore


source_region = os.environ['SOURCE_REGION']
instance = os.environ['DB_INSTANCE_IDENTIFIER']
duration = os.environ['RETENTION']

print('Loading function')

def lambda_handler(event, context):
    def deleteSnapshots(region):
            rds = boto3.client('rds', region_name=region)
            paginator = rds.get_paginator('describe_db_snapshots')
            page_iterator = paginator.paginate(DBInstanceIdentifier=instance, SnapshotType='manual',)
            snapshots = []
            for page in page_iterator:
                 snapshots.extend(page['DBSnapshots'])
            for snapshot in snapshots:
                create_ts = snapshot['SnapshotCreateTime'].replace(tzinfo=None)
                for tag in snapshots['TagList']:
	                if tag['Key'] == 'Name' and tag['Value'] == 'Backup-RDS':
                         if create_ts < datetime.datetime.now() - datetime.timedelta(days=int(duration)):
                           print(("Deleting snapshot id:", snapshot['DBSnapshotIdentifier']))
                           try:
                              response = rds.delete_db_snapshot(DBSnapshotIdentifier=snapshot['DBSnapshotIdentifier'])
                              print(response)
                           except botocore.exceptions.ClientError as e:
                              raise Exception("Could not issue delete command: %s" % e)

    deleteSnapshots(region=source_region)

*/
vars.tf

variable "aws_source_region" {
  default = "us-west-2"
}

variable "retention" {
  default = 2
  description = "Numbers of days to delete RDS snapshot"
}

variable "custom_snapshot_rate" {
  type        = number
  default     = 1
  description = "Number of hours to take custom RDS snapshots every each"
}
