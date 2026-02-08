"""
This script migrates databases/tables in AWS Glue backed by S3 data. It assumes you are migrating databases to a new
S3 bucket, it also assumes the data is stored in s3://<bucket>/<database name with standardization across dbs>/<tables>/<optional partitions/data.<ext>
bucket name/
    database1/
        tableA/
        tableB/
    database2/
        table1/
        table2/
AWS Glue database
    sand_common_prefix_or_not_database1
    sand_common_prefix_or_not_database2
This script also imports a data_sync.py gist made available on the gist page for myself, that script moves the s3 data.
"""
import copy
import logging
import math
import os
from typing import Any, Dict, List, Optional

import boto3
from botocore.exceptions import ClientError

import numpy as np

from data_sync import data_sync_move_data

env = 'prod'
PROFILE_NAME="<insert profile name>"
BUCKET_NAME = f'{env}-<bucket name>'
NEW_BUCKET_NAME = "<new bucket name>"
# instead of searching all databasess to find matches to a bucket
# the <s3_database_prefix> is replaced below from the s3 common prefixes
DATABASE_NAME_TEMPLATE =  f"<insert database prefix prefix>_<s3_database_prefix>"

session = boto3.Session(profile_name=PROFILE_NAME')

s3_client = session.client('s3')
glue_client = session.client('glue')
datasync_client = session.client('datasync')

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DATA_SYNC_ROLE_ARN = {
    "dev": "<create a data sync role>",
    "qa": "<create a data sync role>",
    "prod": "<create a data sync role>",
}


class ServiceApiError(Exception):
    """ServiceApiError exception."""


def chunkify(lst: List[Any], num_chunks: int = 1, max_length: Optional[int] = None) -> List[List[Any]]:
    """Split a list in a List of List (chunks) with even sizes.
    Parameters
    ----------
    lst: List
        List of anything to be splitted.
    num_chunks: int, optional
        Maximum number of chunks.
    max_length: int, optional
        Max length of each chunk. Has priority over num_chunks.
    Returns
    -------
    List[List[Any]]
        List of List (chunks) with even sizes.
    Examples
    --------
    >>> from utils import chunkify
    >>> chunkify(list(range(13)), num_chunks=3)
    [[0, 1, 2, 3, 4], [5, 6, 7, 8], [9, 10, 11, 12]]
    >>> chunkify(list(range(13)), max_length=4)
    [[0, 1, 2, 3], [4, 5, 6], [7, 8, 9], [10, 11, 12]]
    """
    if not lst:
        return []
    n: int = num_chunks if max_length is None else int(math.ceil((float(len(lst)) / float(max_length))))
    np_chunks = np.array_split(lst, n)
    return [arr.tolist() for arr in np_chunks if len(arr) > 0]


def batch_delete_objects(s3_client, s3_bucket, s3_file_names: List[str]):
    """Batch delete objects."""
    chunks: List[Any] = chunkify(lst=s3_file_names, max_length=100)

    response = []
    for chunk in chunks:  # pylint: disable=too-many-nested-blocks
        keys = [{"Key": x} for x in chunk]
        response.extend(_batch_delete_objects(s3_client=s3_client, s3_bucket=s3_bucket, keys=keys))
    logger.info("Deleted files in paths: {files}".format(files=list(set([os.path.dirname(x["Key"])
                                                                         for x in response]))))
    return response

def _batch_delete_objects(s3_client, s3_bucket, keys: List[Any]):
    """Batch delete objects with retry."""
    try:
        return s3_client.delete_objects(Bucket=s3_bucket, Delete={"Objects": keys})["Deleted"]
    except ClientError as ce:
        if ce.response["Error"]["Code"] == "SlowDown":
            raise ce
        raise ce

def check_already_exists_error_glue_response(res: Any) -> None:
    """Check for AlreadyExistsException and raise."""
    if ("Errors" in res) and res["Errors"]:
        for error in res["Errors"]:
            if "ErrorDetail" in error:
                if "ErrorCode" in error["ErrorDetail"]:
                    if error["ErrorDetail"]["ErrorCode"] != "AlreadyExistsException":
                        raise ServiceApiError(str(res["Errors"]))


def _catalog_id(catalog_id: Optional[str] = None, **kwargs: Any) -> Dict[str, Any]:
    if catalog_id is not None:
        kwargs["CatalogId"] = catalog_id
    return kwargs


def _append_partitions(partitions_values: List[Dict[str, List[str]]], response: Dict[str, Any]) -> Optional[str]:
    # print("response: %s", json.dumps(response, indent=4, default=str))
    token: Optional[str] = response.get("NextToken", None)
    if (response is not None) and ("Partitions" in response):
        for partition in response["Partitions"]:
            partition_input: Dict[str, Any] = {}
            for k, v in partition.items():
                if k in [
                        "Values",
                        "StorageDescriptor",
                ]:
                    partition_input[k] = v
            partitions_values.append(partition_input)
    else:
        token = None
    return token


def get_create_table_input(glue_client, database_name, table_name):
    """Return a create table input dictionary."""
    try:
        response = glue_client.get_table(DatabaseName=database_name, Name=table_name)
        table_input: Dict[str, Any] = {}
        for k, v in response["Table"].items():
            if k in [
                    "Name",
                    "Description",
                    "Owner",
                    "LastAccessTime",
                    "LastAnalyzedTime",
                    "Retention",
                    "StorageDescriptor",
                    "PartitionKeys",
                    "ViewOriginalText",
                    "ViewExpandedText",
                    "TableType",
                    "Parameters",
                    "TargetTable",
            ]:
                table_input[k] = v
        return table_input
    except glue_client.exceptions.EntityNotFoundException as ex:
        print(
            "During the table color flipping, a table's data/file was not processed correctly and cannot be found {database}.{table}"
            .format(database=database_name, table=table_name) +
            ". This means that a table was expected to have been created/updated but actually does not exist in active color's database."
        )
        raise ex


def _get_partitions(
        client_glue: boto3.client,
        database: str,
        table: str,
        expression: Optional[str] = None,
        catalog_id: Optional[str] = None,
) -> List[Dict[str, List[str]]]:

    args: Dict[str, Any] = {
        "DatabaseName": database,
        "TableName": table,
        "MaxResults": 1_000,
        "Segment": {
            "SegmentNumber": 0,
            "TotalSegments": 1
        },
    }
    if expression is not None:
        args["Expression"] = expression
    if catalog_id is not None:
        args["CatalogId"] = catalog_id

    partitions_values: List[Dict[str, List[str]]] = []
    # print("Starting _get_partitions pagination...")

    response: Dict[str, Any] = client_glue.get_partitions(**args)
    token: Optional[str] = _append_partitions(partitions_values=partitions_values, response=response)
    while token is not None:
        args["NextToken"] = response["NextToken"]
        response = client_glue.get_partitions(**args)
        token = _append_partitions(partitions_values=partitions_values, response=response)

    # print("Pagination _get_partitions done.")
    partitions_values.sort(key=lambda x: x["Values"])
    return partitions_values


def get_partitions_new_location(partitions: List[Dict[str, Any]], old_location, new_location) -> List[Dict[str, Any]]:
    """Get the inactive color's table partitions from the active table's
    partitions."""
    partitions = copy.deepcopy(partitions)
    for partition in partitions:
        partition["StorageDescriptor"]["Location"] = partition["StorageDescriptor"]["Location"].replace(
            old_location, new_location)
    return partitions


def get_table_input_new_locataion(table_input: Dict[str, Any], old_location, new_location):
    """Get the inactive create table input."""
    create_table_input = copy.deepcopy(table_input)
    create_table_input["StorageDescriptor"]["Location"] = create_table_input["StorageDescriptor"]["Location"].replace(
        old_location, new_location)
    return create_table_input


def update_glue_table_partitions(
    client_glue: boto3.client,
    catalog_id: Optional[str],
    database_name: str,
    table_name: str,
    partitions: List[Dict[str, Any]],
):
    """Create glue table partitions, if there already exist ignore them."""
    chunks: List[List[Dict[str, Any]]] = chunkify(lst=partitions, max_length=100)

    for chunk in chunks:  # pylint: disable=too-many-nested-blocks
        batch_update_values = []
        for idx, value in enumerate(chunk):
            # helpers.create_partition(client, database_name, table_name, values=value)
            batch_update_values.append({"PartitionValueList": value["Values"], "PartitionInput": value})
        res: Dict[str, Any] = client_glue.batch_update_partition(**_catalog_id(
            catalog_id=catalog_id,
            DatabaseName=database_name,
            TableName=table_name,
            Entries=batch_update_values,
        ))
        check_already_exists_error_glue_response(res)


def update_glue_table(
    glue_client,
    database_name,
    table_input,
    catalog_id: str = None,
    partition_indexes: List[Dict[str, str]] = None,
):
    """."""
    args: Dict[str, Any] = {
        "DatabaseName": database_name,
        "TableInput": table_input,
        "SkipArchive": True,
    }
    if partition_indexes is not None:
        args["PartitionIndexes"] = partition_indexes
    if catalog_id is not None:
        args["CatalogId"] = catalog_id
    glue_client.update_table(**args)


def update_glue_database(glue_client, database_name, database_input: Any):
    """."""
    args = {'CatalogId': database_input['CatalogId'], 'Name': database_name, 'DatabaseInput': database_input}
    del args['DatabaseInput']['CreateTime']
    del args['DatabaseInput']['CatalogId']
    glue_client.update_database(**args)


def check_s3_contents(bucket_name, prefix, s3_client):
    """Get the list of keys in a bucket with a given prefix."""
    args = {'Bucket': bucket_name}
    if prefix is not None and len(prefix) > 0:
        args['Prefix'] = prefix
    keys = []
    paginator = s3_client.get_paginator("list_objects_v2")
    pages = paginator.paginate(**args)

    for page in pages:
        if page.get("Contents", None) is not None:
            for obj in page["Contents"]:
                key = obj["Key"]
                if key.startswith(prefix):
                    keys.append(key)
    return keys


def delete_s3_prefix(bucket_name, prefix, s3_client):
    """Delete s3 prefix."""
    files = check_s3_contents(bucket_name, prefix, s3_client)

    batch_delete_objects(s3_client=s3_client, s3_bucket=bucket_name, s3_file_names=files)
    print(f"delete {prefix}")

def get_common_prefixes(s3_client, bucket_name, prefix=None):
    """Get the list of keys in a bucket with a given prefix."""
    args = {'Bucket': bucket_name}
    if prefix is not None and len(prefix) > 0:
        args['Prefix'] = prefix
    args['Delimiter'] = '/'
    keys = []
    paginator = s3_client.get_paginator("list_objects_v2")
    pages = paginator.paginate(**args)

    for page in pages:
        if page.get("CommonPrefixes", None) is not None:
            keys = [x['Prefix'] for x in page['CommonPrefixes']]

    return keys


if __name__ == '__main__':
    all_database_in_s3 = []
    s3_database_prefixes = get_common_prefixes(s3_client, BUCKET_NAME)
    for s3_database_prefix in s3_database_prefixes:
        database_name =  DATABASE_NAME_TEMPLATE.replace("<s3_database_prefix>", s3_database_prefix.replace('/',''))
        all_database_in_s3.append(database_name)
        database_input = glue_client.get_database(Name=database_name)
        if 'LocationUri' not in database_input['Database']:
            database_input['Database']['LocationUri'] = f"s3://{NEW_BUCKET_NAME}/{s3_database_prefix}"
            update_glue_database(glue_client=glue_client,
                                 database_name=database_name,
                                 database_input=database_input['Database'])
        if 's3://' + NEW_BUCKET_NAME + "/" not in database_input['Database']['LocationUri']:
            database_input['Database']['LocationUri'] = database_input['Database']['LocationUri'].replace(
                BUCKET_NAME + "/", NEW_BUCKET_NAME + "/")
            update_glue_database(glue_client=glue_client,
                                 database_name=database_name,
                                 database_input=database_input['Database'])
        s3_table_prefixes = get_common_prefixes(s3_client, BUCKET_NAME, prefix=s3_database_prefix)
        tables = [x.replace(s3_database_prefix, "", 1).replace("/", "") for x in s3_table_prefixes]
        for table in tables:
            try:
                table_response = glue_client.get_table(DatabaseName=database_name, Name=table)
            except glue_client.exceptions.EntityNotFoundException as ex:
                s3_prefix = [x for x in s3_table_prefixes if table + '/' in x][0]
                print(f"deleting {s3_prefix} because could not find table in the database - CLEANUP")
                delete_s3_prefix(bucket_name=BUCKET_NAME, prefix=s3_prefix, s3_client=s3_client)
                continue
            except Exception as ex:
                raise ex
            table_response = get_create_table_input(glue_client=glue_client,
                                                    database_name=database_name,
                                                    table_name=table)
            partition_response = _get_partitions(client_glue=glue_client, database=database_name, table=table)

            update_table_input = get_table_input_new_locataion(
                table_input=table_response, old_location=BUCKET_NAME + "/",
                new_location=NEW_BUCKET_NAME + "/")  # "/" at the end ensures that we can safetly re-run this
            update_partitions_input = get_partitions_new_location(partitions=partition_response,
                                                                  old_location=BUCKET_NAME + "/",
                                                                  new_location=NEW_BUCKET_NAME + "/")
            if 's3://' + NEW_BUCKET_NAME + '/' not in update_table_input['StorageDescriptor']['Location']:
                # this only occurs if this script is not idempotent
                if 's3://' + NEW_BUCKET_NAME in update_table_input['StorageDescriptor']['Location']:
                    update_table_input['StorageDescriptor']['Location'] = 's3://' + NEW_BUCKET_NAME + "/" + "/".join(
                        update_table_input['StorageDescriptor']['Location'].split('/')[3:])
                    update_table_input['StorageDescriptor']['Location'] = update_table_input['StorageDescriptor'][
                        'Location'].replace("//", "/").replace('s3:/', 's3://')
                else:
                    raise Exception("Wrong s3 location")
            if any([
                    False for x in update_partitions_input
                    if 's3://' + NEW_BUCKET_NAME + '/' not in x['StorageDescriptor']['Location']
            ]):
                raise Exception("Wrong s3 location on partitions")

            update_glue_table(
                glue_client=glue_client,
                database_name=database_name,
                table_input=update_table_input,
                # partition_indexes=partition_response
            )
            update_glue_table_partitions(client_glue=glue_client,
                                         catalog_id=None,
                                         database_name=database_name,
                                         table_name=table,
                                         partitions=update_partitions_input)
            print('%s.%s' % (database_name, table))
        print('%s' % database_name)

    data_sync_move_data(task_name="migrate_data",
                        data_sync_role_arn=DATA_SYNC_ROLE_ARN[env],
                        source_bucket=BUCKET_NAME,
                        destination_bucket=NEW_BUCKET_NAME,
                        subdirectory="",
                        datasync_client=datasync_client,
                        preserve_deleted_files='PRESERVE')

    print('done')
@awsvpc
Comment
