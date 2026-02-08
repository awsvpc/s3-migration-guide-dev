response = client.copy_db_snapshot(
  SourceDBSnapshotIdentifier=snapshot_arn,
  TargetDBSnapshotIdentifier=snapshot_target_identifier,
  KmsKeyId=SNAPSHOT_DR_REGION_KMS_KEY_ARN,
  CopyTags=True,
  Tags=[
      {
          'Key': 'Description',
          'Value': 'Created via SNS Topic Automation'
      },
  ],
  SourceRegion=SNAPSHOTS_SOURCE_REGION
  )
