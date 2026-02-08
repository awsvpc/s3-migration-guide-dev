"""AWS DataSync an aws service to move/copy large amounts of data."""
import logging
import os
from typing_extensions import Literal

import boto3
import tenacity
from botocore import waiter
from botocore.exceptions import WaiterError

import _utils

logger = logging.getLogger(__name__)


class DataSyncWaiter(object):
    """A AWS Data sync waiter class."""
    def __init__(self, client):
        """Init."""
        self._client = client
        self._waiter = waiter

    def wait_for_finished(self, task_execution_arn):
        """Wait for data sync to finish."""
        model = self._waiter.WaiterModel({
            "version": 2,
            "waiters": {
                "JobFinished": {
                    "delay":
                    1,
                    "operation":
                    "DescribeTaskExecution",
                    "description":
                    "Wait until AWS Data Sync starts finished",
                    "maxAttempts":
                    1000000,
                    "acceptors": [
                        {
                            "argument": "Status",
                            "expected": "SUCCESS",
                            "matcher": "path",
                            "state": "success",
                        },
                        {
                            "argument": "Status",
                            "expected": "ERROR",
                            "matcher": "path",
                            "state": "failure",
                        },
                    ],
                }
            },
        })
        self._waiter.create_waiter_with_client("JobFinished", model,
                                               self._client).wait(TaskExecutionArn=task_execution_arn)


class DataSyncClient:
    """A AWS DataSync client."""
    def __init__(self, client, role_arn, waiter: DataSyncWaiter = None) -> None:
        """Init."""
        self._client: boto3.client = client
        if waiter is None:
            waiter = DataSyncWaiter(client=client)
        self._waiter: DataSyncWaiter = waiter
        self._role_arn = role_arn

    def _delete_task(self, task_arn):
        """Delete a AWS DataSync task."""
        response = self._client.delete_task(TaskArn=task_arn)
        return response

    def _list_s3_locations(self):
        """List AWS DataSync locations."""
        locations = self._client.list_locations(MaxResults=100)
        if "Locations" in locations:
            return [x for x in locations["Locations"] if x["LocationUri"].startswith("s3://")]
        return []

    def _create_datasync_s3_location(self, bucket_name: str, subdirectory: str = ""):
        """Create AWS DataSync location."""
        return self._client.create_location_s3(
            Subdirectory=subdirectory,
            S3BucketArn=f"arn:aws:s3:::{bucket_name}",
            S3StorageClass="STANDARD",
            S3Config={"BucketAccessRoleArn": self._role_arn},
        )

    def _find_location_arn(self, bucket_name, subdirectory: str, locations_s3):
        """Find AWS DataSync LocationArn based on bucketname."""
        for x in locations_s3:
            # match the s3 location
            if (bucket_name + "/") in x["LocationUri"] and subdirectory in x["LocationUri"]:
                # match the roles, these do not update frequently
                location_metadata = self._client.describe_location_s3(LocationArn=x["LocationArn"])
                if location_metadata["S3Config"]["BucketAccessRoleArn"] == self._role_arn:
                    return x["LocationArn"]
        return self._create_datasync_s3_location(bucket_name=bucket_name, subdirectory=subdirectory)["LocationArn"]

    def move_data(self,
                  task_name: str,
                  source_bucket_name: str,
                  dest_bucket_name: str,
                  subdirectory: str,
                  preserve_deleted_files: Literal['PRESERVE', 'REMOVE'] = "REMOVE") -> bool:
        """Move data using AWS DataSync tasks."""
        current_locations = self._list_s3_locations()
        source_s3_location_response = self._find_location_arn(bucket_name=source_bucket_name,
                                                              locations_s3=current_locations,
                                                              subdirectory=subdirectory)
        dest_s3_location_response = self._find_location_arn(bucket_name=dest_bucket_name,
                                                            locations_s3=current_locations,
                                                            subdirectory=subdirectory)
        logger.info("Moving data from SRC:{source} DEST:{dest}".format(
            source=os.path.join(source_bucket_name, subdirectory), dest=os.path.join(dest_bucket_name, subdirectory)))
        task = self._client.create_task(
            SourceLocationArn=source_s3_location_response,
            DestinationLocationArn=dest_s3_location_response,
            Name=f"{task_name}-sync",
            Options={
                "VerifyMode": "POINT_IN_TIME_CONSISTENT",
                "OverwriteMode": "ALWAYS",
                "PreserveDeletedFiles": preserve_deleted_files,
                # 'TransferMode': # 'CHANGED'|'ALL'
            },
        )
        self.start_task_waiting_for_complete(task_arn=task["TaskArn"])
        self._delete_task(task_arn=task["TaskArn"])
        return True

    @tenacity.retry(
        retry=tenacity.retry_if_exception_type(exception_types=(WaiterError)),
        wait=tenacity.wait_random_exponential(multiplier=0.5),
        stop=tenacity.stop_after_attempt(max_attempt_number=60),
        reraise=True,
        after=tenacity.after_log(logger, logging.INFO),
    )
    def start_task_waiting_for_complete(self, task_arn: str):
        """Start data move task, with retry because sometimes not all files get
        moved.
        It is not clear if this is because of eventual consistency in S3
        or the AWS service just does not handle constistency well.
        """
        task_started = self._client.start_task_execution(TaskArn=task_arn)
        self._waiter.wait_for_finished(task_execution_arn=task_started["TaskExecutionArn"])


def data_sync_move_data(task_name: str,
                        data_sync_role_arn: str,
                        source_bucket: str,
                        destination_bucket: str,
                        subdirectory: str,
                        datasync_client: boto3.client = None,
                        preserve_deleted_files: Literal['PRESERVE', 'REMOVE'] = "REMOVE"):
    """Move data from active to inactive color."""
    logger.info(f"DataSync: Moving all the data from {source_bucket} -> {destination_bucket}")
    if datasync_client is None:
        datasync_client = _utils.get_boto_client("datasync")
    datasync_client = DataSyncClient(client=datasync_client, role_arn=data_sync_role_arn)
    datasync_client.move_data(task_name=task_name,
                              source_bucket_name=source_bucket,
                              dest_bucket_name=destination_bucket,
                              subdirectory=subdirectory,
                              preserve_deleted_files=preserve_deleted_files)
