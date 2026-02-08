#!/usr/bin/env python3

import boto3


TARGET_ACCOUNT_ID = '1234567890'

tagging_api = boto3.client('resourcegroupstaggingapi')
rds = boto3.client('rds')

print('Find tagged snapshot..')
snapshots = tagging_api.get_resources(
    ResourceTypeFilters=['rds:snapshot'],
    TagFilters=[
        { 'Key': 'OriginIdentifier' },
        { 'Key': 'CopyIdentifier' },
    ],
)['ResourceTagMappingList']

if snapshots:
    print(f'Tagged snapshot is Found: {snapshots[0]["ResourceARN"]}')

    for tag in snapshots[0]['Tags']:
        if tag['Key'] == 'OriginIdentifier':
            origin_snapshot_id = tag['Value']
        if tag['Key'] == 'CopyIdentifier':
            copy_snapshot_id = tag['Value']
else:
    print('Tagged snapshot is not Found.')

    snapshots = rds.describe_db_snapshots(
        SnapshotType='automated'
    )['DBSnapshots']

    latest_snapshot = sorted(snapshots, key=lambda k: k['SnapshotCreateTime'], reverse=True)[0]

    origin_snapshot_id = latest_snapshot['DBSnapshotIdentifier']
    copy_snapshot_id = f'copy-{origin_snapshot_id.replace("rds:", "")}'

    print(f'Copy the snapshot from \'{origin_snapshot_id}\' to \'{copy_snapshot_id}\'')
    rds.copy_db_snapshot(
        SourceDBSnapshotIdentifier=origin_snapshot_id,
        TargetDBSnapshotIdentifier=copy_snapshot_id,
        Tags=[
            {'Key': 'OriginIdentifier', 'Value': origin_snapshot_id},
            {'Key': 'CopyIdentifier', 'Value': copy_snapshot_id},
        ],
    )

print('Wait for the snapshot complete...')
waiter = rds.get_waiter('db_snapshot_completed')
waiter.wait(
    DBSnapshotIdentifier=copy_snapshot_id,
    WaiterConfig={'Delay': 10, 'MaxAttempts': 60}
)

print(f'Share the snapshot with AWS account {TARGET_ACCOUNT_ID}')
rds.modify_db_snapshot_attribute(
    DBSnapshotIdentifier=copy_snapshot_id,
    AttributeName='restore',
    ValuesToAdd=[
        TARGET_ACCOUNT_ID,
    ],
)

# print('Delete the snapshot')
# rds.delete_db_snapshot(
#     DBSnapshotIdentifier=copy_snapshot_id,
# )
