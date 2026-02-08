import time
from datetime import datetime
import os

import boto3
from botocore.exceptions import WaiterError
from botocore.waiter import create_waiter_with_client
from celery import shared_task

from .custom_waiter import waiter_model

now = datetime.now().strftime('%Y-%m-%d-%H-%M-%S')
ENVIRONMENT = os.environ.get('ENVIRONMENT', 'dev')
REGION_NAME = 'us-east-1'

# alpha(prod) variables
ALPHA_DB_IDENTIFIER = 'new-events'
ALPHA_KMS_KEY_ID = os.environ.get('ALPHA_KMS_KEY_ID')
ALPHA_AWS_ACCESS_KEY_ID = os.environ.get('ALPHA_AWS_ACCESS_KEY_ID')
ALPHA_AWS_SECRET_ACCESS_KEY = os.environ.get('ALPHA_AWS_SECRET_ACCESS_KEY')


def create_snapshot(alpha_db):
    '''create a snapshot of alpha DB'''

    rds_client = boto3.client('rds', 
                    aws_access_key_id=ALPHA_AWS_ACCESS_KEY_ID, 
                    aws_secret_access_key=ALPHA_AWS_SECRET_ACCESS_KEY, 
                    region_name=REGION_NAME
                ) # env specific ids

    snapshot_identifier = snapshot_arn = None
    try:
        print('Creating a snaphot for DB: ', alpha_db)
        response = rds_client.create_db_cluster_snapshot(
            DBClusterSnapshotIdentifier='{}-snapshot-{}'.format(alpha_db, now),
            DBClusterIdentifier=alpha_db,
            Tags=[
                {
                    'Key': 'CreatedBy',
                    'Value': 'Admintool',
                    'Key': 'CreatedOn',
                    'Value': now,
                    'Key': 'Environment',
                    'Value': f'{ENVIRONMENT}'.title()
                },
            ]
        )
        snapshot_identifier = response['DBClusterSnapshot']['DBClusterSnapshotIdentifier']
        snapshot_arn = response['DBClusterSnapshot']['DBClusterSnapshotArn']
        
        try:
            print(f"Waiting for {snapshot_identifier} to be available")
            waiter = rds_client.get_waiter('db_cluster_snapshot_available')
            waiter.wait(
                DBClusterSnapshotIdentifier=snapshot_identifier
            )
            print(f"Snapshot `{snapshot_identifier}` created successfully")

        except WaiterError as e:
            print(f"An error occurred while waiting for the snaphot: {snapshot_identifier}, error message: {e}")

    except Exception as e:
        print('Failed to create snapshot: ', e)

    return snapshot_identifier, snapshot_arn


def copy_own_snapshot(snapshot_identifier, snapshot_arn):
    '''Copy own snapshot. Copy a snapshot to the same account'''
    
    # we copy own snapshot so we can create a manual kms id
    rds_client = boto3.client('rds', 
                aws_access_key_id=ALPHA_AWS_ACCESS_KEY_ID, 
                aws_secret_access_key=ALPHA_AWS_SECRET_ACCESS_KEY, 
                region_name=REGION_NAME
            ) # env specific ids   

    snapshot_identifier = '{}-copy'.format(snapshot_identifier)
    try: 
        print('Copying own snapshot: ', snapshot_identifier)
        response  = rds_client.copy_db_cluster_snapshot(
            SourceDBClusterSnapshotIdentifier=snapshot_arn,
            TargetDBClusterSnapshotIdentifier=snapshot_identifier,
            KmsKeyId=ALPHA_KMS_KEY_ID,
            Tags=[{
                'Key': 'CopiedBy',
                'Value': 'Admintool',
                'Key': 'CreatedOn',
                'Value': now,
                'Key': 'Environment',
                'Value': f'{ENVIRONMENT}'.title()
            }],
            SourceRegion=REGION_NAME
        )
        snapshot_arn = response['DBClusterSnapshot']['DBClusterSnapshotArn']
        
        try:
            print(f"Waiting for {snapshot_identifier} to be available")
            waiter = rds_client.get_waiter('db_cluster_snapshot_available')
            waiter.wait(
                DBClusterSnapshotIdentifier=snapshot_identifier
            )
            print(f"Snapshot `{snapshot_identifier}` copied successfully to own account")

        except WaiterError as e:
            print(f"An error occurred while waiting for the snaphot: {snapshot_identifier}, error message: {e}")

    except Exception as e:
        print("Failed to copy snapshot: ", e)

    return snapshot_identifier, snapshot_arn


def share_snapshot(snapshot_identifier, dest_acct_id):
    '''Share a snapshot from current acct to dest acct'''
    
    rds_client = boto3.client('rds', 
                aws_access_key_id=ALPHA_AWS_ACCESS_KEY_ID, 
                aws_secret_access_key=ALPHA_AWS_SECRET_ACCESS_KEY, 
                region_name=REGION_NAME
            ) # env specific ids   
        
    if snapshot_identifier is not None:
        try:
            # Share snapshot with dest_account
            print("Sharing db snapshort: ", snapshot_identifier)
            response = rds_client.modify_db_cluster_snapshot_attribute(
                DBClusterSnapshotIdentifier=snapshot_identifier,
                AttributeName='restore',
                ValuesToAdd=[
                    dest_acct_id,
                ],
            )
            snapshot_identifier = response['DBClusterSnapshotAttributesResult']['DBClusterSnapshotIdentifier']
            print(f'Snapshot: {snapshot_identifier} shared successfully')
            time.sleep(60) # snapshot sharing waiting time 

        except Exception as e:
            print("failed to share snapshot: ", e)
    else:
        print(f"The provided {snapshot_identifier} is invalid")

    return  snapshot_identifier              



def copy_snapshot(snapshot_identifier, kms_key_id, snapshot_arn, access_key_id, secret_access_key):
    '''Copy a shared snapshot into dev/staging'''
    
    rds_client = boto3.client('rds', 
                aws_access_key_id=access_key_id, 
                aws_secret_access_key=secret_access_key, 
                region_name=REGION_NAME
            ) # env specific ids   
    try: 
        print('Copying the snapshot: ', snapshot_arn)
        rds_client.copy_db_cluster_snapshot(
            SourceDBClusterSnapshotIdentifier=snapshot_arn,
            TargetDBClusterSnapshotIdentifier=snapshot_identifier,
            KmsKeyId=kms_key_id,
            Tags=[{
                'Key': 'CopiedBy',
                'Value': 'Admintool',
                'Key': 'CreatedOn',
                'Value': now,
                'Key': 'Environment',
                'Value': f'{ENVIRONMENT}'.title()
            }],
            SourceRegion=REGION_NAME
        )
        
        try:
            print(f"Waiting for {snapshot_identifier} to be available")
            waiter = rds_client.get_waiter('db_cluster_snapshot_available')
            waiter.wait(
                DBClusterSnapshotIdentifier=snapshot_identifier
            )
            print(f"Snapshot `{snapshot_identifier}` copied successfully")

        except WaiterError as e:
            print(f"An error occurred while waiting for the snaphot: {snapshot_identifier}, error message: {e}")

    except Exception as e:
        print("Failed to copy snapshot: ", e)


def restore_cluster(snapshot_identifier, db_identifier, dbsubnet_group, vpc_id, kms_key_id, access_key_id, secret_access_key):
    '''Restore a snapshot to DB'''

    rds_client = boto3.client('rds', 
                aws_access_key_id=access_key_id, 
                aws_secret_access_key=secret_access_key, 
                region_name=REGION_NAME
            ) # env specific ids   
    print("Restoring cluster...")
    try:
        rds_client.restore_db_cluster_from_snapshot(  # check return value to assert 
            AvailabilityZones=[
                'us-east-1a',
                'us-east-1b', 
                'us-east-1c', 
                ],
            DBClusterIdentifier= db_identifier, 
            SnapshotIdentifier=snapshot_identifier,
            Engine='aurora-postgresql',
            EngineVersion='10.12',
            Port=5432,
            DBSubnetGroupName= dbsubnet_group,
            DatabaseName='Events',
            VpcSecurityGroupIds=[
                vpc_id,
            ],
            Tags=[
                {
                    'Key': 'CreatedBy',
                    'Value': 'Admintool',
                    'Key': 'CreatedOn',
                    'Value': now,
                    'Key': 'Environment',
                    'Value': f'{ENVIRONMENT}'.title()
                },
            ],
            KmsKeyId=kms_key_id,
            EnableIAMDatabaseAuthentication=False,
            EngineMode='serverless',
            ScalingConfiguration={
                'MinCapacity': 2,
                'MaxCapacity': 4,
                'AutoPause': False
            },
            DBClusterParameterGroupName='default.aurora-postgresql10',
            DeletionProtection=False,
            CopyTagsToSnapshot=True,
        )
        
        waiter_name = 'DBClusterAvailable'
        custom_waiter = create_waiter_with_client(
            waiter_name=waiter_name, 
            waiter_model=waiter_model, 
            client=rds_client
        )

        try:
            print(f"Waiting for {snapshot_identifier} to be restored")
            custom_waiter.wait(
                DBClusterIdentifier=db_identifier
            )
            print(f"DB cluster `{db_identifier}` restored successfully")

        except WaiterError as e:
            print(f"An error occurred while restoring: {snapshot_identifier}, error message: {e}")   

    except Exception as e:
        print("Failed to restore cluster:", e)    


def delete_cluster(db_identifier, access_key_id, secret_access_key):
    rds_client = boto3.client('rds', 
                    aws_access_key_id=access_key_id, 
                    aws_secret_access_key=secret_access_key, 
                    region_name=REGION_NAME
                ) # env specific ids   
    try:
        print("Starting to delete cluster")
        rds_client.delete_db_cluster(
            DBClusterIdentifier=db_identifier,
            SkipFinalSnapshot=True,
        )

        waiter_name = 'DBClusterDeleted'
        custom_waiter = create_waiter_with_client(
            waiter_name=waiter_name, 
            waiter_model=waiter_model, 
            client=rds_client
        )
        try:
            print(f"Waiting for {db_identifier} to be deleted")
            custom_waiter.wait(
                DBClusterIdentifier=db_identifier
            )
            print(f"DB cluster `{db_identifier}` deleted successfully")

        except WaiterError as e:
            print(f"An error occurred while deleting: {db_identifier}, error message: {e}")

    except Exception as e:
        print(f"Failed to delete: {db_identifier}", e)    


def delete_existing_snapshots(db_identifier, access_key_id=ALPHA_AWS_ACCESS_KEY_ID, secret_access_key=ALPHA_AWS_SECRET_ACCESS_KEY):
    '''Delete old snapshots in dev/staging'''

    rds_client = boto3.client('rds', 
                    aws_access_key_id=access_key_id, 
                    aws_secret_access_key=secret_access_key, 
                    region_name=REGION_NAME
                ) # env specific ids

    # gets all existing manual snapshots for target db -- deletes them
    print("Getting all snapshots to delete")
    response = rds_client.describe_db_cluster_snapshots(
        DBClusterIdentifier=db_identifier,
        SnapshotType='manual',
    )
    for snapshots in response['DBClusterSnapshots']:
        print(f"Deleting snapshot: {snapshots['DBClusterSnapshotIdentifier']} for DB: {db_identifier}")

        try:
            rds_client.delete_db_cluster_snapshot(
                DBClusterSnapshotIdentifier=snapshots['DBClusterSnapshotIdentifier'],
            )
            print(f"Snapshot: {snapshots['DBClusterSnapshotIdentifier']} deleted successfully")
        except Exception as e:
            print(f"Failed to delete snapshot: {snapshots['DBClusterSnapshotIdentifier']}, error: {e}")


def modify_db_credentials(db_identifier, password, access_key_id, secret_access_key):
    '''Modify the password of the alpha snapshot into dev/staging password'''
    
    rds_client = boto3.client('rds', 
                    aws_access_key_id=access_key_id, 
                    aws_secret_access_key=secret_access_key, 
                    region_name=REGION_NAME
                ) # env specific ids   

    print("Starting to change DB password for:", db_identifier)
    try:
        response = rds_client.modify_db_cluster(
                        DBClusterIdentifier=db_identifier,
                        ApplyImmediately=True,
                        MasterUserPassword=password,
                        DeletionProtection=False,
                    )
    except Exception as e:
        print("Failed to modify db", e)

    print(response)


def handler(db_identifier, dest_acct_id, alpha_db, dbsubnet_group, vpc_id, kms_key_id, password, access_key_id, secret_access_key):
    '''create snapshots for dev/staging and restore db'''

    if ENVIRONMENT in ['dev', 'staging']:
        # if we run this on the above environments, the application will go off at the window when db is deleted and replaced
        return

    # find old manual snapshots, if exists - delete
    delete_existing_snapshots(db_identifier=alpha_db)

    # create a new snapshot
    snapshot_identifier, snapshot_arn = create_snapshot(alpha_db)

    # copy own snapshots
    snapshot_identifier, snapshot_arn = copy_own_snapshot(snapshot_identifier, snapshot_arn)

    # share the snapshot
    snapshot_identifier = share_snapshot(snapshot_identifier, dest_acct_id)

    # copy snapshot 
    copy_snapshot(snapshot_identifier, kms_key_id, snapshot_arn, access_key_id, secret_access_key)

    # delete old cluster
    delete_cluster(db_identifier, access_key_id, secret_access_key)

    # restore cluster
    restore_cluster(snapshot_identifier, db_identifier, dbsubnet_group, vpc_id, kms_key_id, access_key_id, secret_access_key)
    
    # delete snapshots for dev/staging
    delete_existing_snapshots(alpha_db, access_key_id, secret_access_key)
    
    # modify the db credentials so services don't break
    modify_db_credentials(db_identifier, password, access_key_id, secret_access_key)

    return "Process completed!"


@shared_task
def create_snapshot_for_staging():
    # staging variables
    STAGING_DB_IDENTIFIER = os.environ.get('STAGING_DB_IDENTIFIER')
    AWS_STAGING_ACCOUNT_ID = os.environ.get('AWS_STAGING_ACCOUNT_ID')
    STAGING_KMS_KEY_ID = os.environ.get('STAGING_KMS_KEY_ID')
    STAGING_AWS_ACCESS_KEY_ID = os.environ.get('STAGING_AWS_ACCESS_KEY_ID')
    STAGING_AWS_SECRET_ACCESS_KEY = os.environ.get('STAGING_AWS_SECRET_ACCESS_KEY')
    STAGING_DB_PASSWORD = os.environ.get('STAGING_DB_PASSWORD')
    STAGING_VPC_ID = os.environ.get('STAGING_VPC_ID')
    STAGING_DBSUBNET_GROUP = 'staging-database-group'

    handler(db_identifier=STAGING_DB_IDENTIFIER, 
        dest_acct_id=AWS_STAGING_ACCOUNT_ID, 
        alpha_db=ALPHA_DB_IDENTIFIER,
        dbsubnet_group=STAGING_DBSUBNET_GROUP, 
        vpc_id=STAGING_VPC_ID,
        kms_key_id=STAGING_KMS_KEY_ID,
        password=STAGING_DB_PASSWORD,
        access_key_id=STAGING_AWS_ACCESS_KEY_ID, 
        secret_access_key=STAGING_AWS_SECRET_ACCESS_KEY
        )
