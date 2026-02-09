import os
import json
import boto3

from django.conf import settings

def build_file_path(path, filename, static_root_folder):
    NAME = static_root_folder + '/'
    return path[path.find(NAME) + len(NAME):] + filename

def register_new_webs3_bucket(bucket_name, secret_key, secret_access_key, region, static_root_folder):
    """
    will create a bucket named: domain_name and accessible trought the browser at http://domain_name
    SYNC_DIR represent the folder where the files and dirs to upload are located.
   
    
    :param bucket_name:
    :param secret_key:
    :param secret_access_key:
    :param region:
    :param static_root_folder:
    :return:
    """
    SYNC_DIR = os.path.join(os.path.dirname(os.path.dirname(settings.FRONT_END_CLIENT_SYNC_DIR)), static_root_folder)
    s3 = boto3.client(
        's3',
        aws_access_key_id=secret_key',
        aws_secret_access_key=secret_access_key',
        region_name=region'
    )

    s3.create_bucket(Bucket=bucket_name, CreateBucketConfiguration={
        'LocationConstraint': region'
    })
    bucket_policy = {
        'Version': '2012-10-17',
        'Statement': [{
            'Sid': 'AddPerm',
            'Effect': 'Allow',
            'Principal': '*',
            'Action': ['s3:GetObject'],
            'Resource': "arn:aws:s3:::%s/*" % bucket_name
        }]
    }
    bucket_policy = json.dumps(bucket_policy)
    s3.put_bucket_policy(Bucket=bucket_name, Policy=bucket_policy)
    s3.put_bucket_website(
        Bucket=bucket_name,
        WebsiteConfiguration={
            'ErrorDocument': {'Key': 'error.html'},
            'IndexDocument': {'Suffix': 'index.html'}
        }
    )
    file_int = 0
    for root, dirs, files in os.walk(SYNC_DIR):
        # print( root, dirs, files )
        file_int += 1
        for _file in files:
            if root[-1] != '/':
                root = root + '/'
            with open(root + _file, 'rb') as data:
                s3.put_object(
                    Body=data,
                    Bucket=bucket_name,
                    Key=build_file_path(root, _file),
                    ContentType='text/html'
                )
    print(file_int,' Uploaded to the S3 in web hosting mode')
