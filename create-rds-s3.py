import json
import boto3
import uuid
import os

def lambda_handler(event, context):
    DEFAULT_REGION = os.environ["DEFAULT_REGION"]

    # This is the customer field in the new client creation
    customer_name = event['customerName']
    # This replaces the customer name and removes the "." as RDS does not like them
    db_identifier = customer_name.replace(".", "")

    # Create New RDS
    rds = boto3.client('rds')

    # Create an S3 client
    s3 = boto3.client('s3')
    s3_resource = boto3.resource('s3')
    # Create the bucket policy
    bucket_policy = {
    'Version': '2012-10-17',
    'Statement': [{
        'Sid': 'PublicReadGetObject',
        'Effect': 'Allow',
        'Principal': '*',
        'Action': ['s3:GetObject'],
        "Resource": [
                "arn:aws:s3:::{0}/*".format(customer_name)
            ]
    }]
    }

    # Convert the policy to a JSON string
    bucket_policy = json.dumps(bucket_policy)

    # Set the new policy on the given bucket
    s3.put_bucket_policy(Bucket=customer_name, Policy=bucket_policy)

    # Create the configuration for the website
    website_configuration = {
    'ErrorDocument': {'Key': 'error.html'},
    'IndexDocument': {'Suffix': 'index.html'},
    }

    # Set the new policy on the bucket
    s3.put_bucket_website(
    Bucket=customer_name,
    WebsiteConfiguration=website_configuration
    )
    
    for key in s3.list_objects(Bucket='smartcount-admin')['Contents']:
        files = key['Key']
        copy_source = {'Bucket': "smartcount-admin",'Key': files}
        s3_resource.meta.client.copy(copy_source, customer_name, files)
        
    
    # Create Route53
    route53 = boto3.client('route53')

    # Route 53 needs a unique ID to create a record in a zone
    caller_reference_uuid = "%s" % (uuid.uuid4())

    # Create the new hosted zone in Route53
    response = route53.create_hosted_zone(
    Name=customer_name,
    CallerReference=caller_reference_uuid,
    HostedZoneConfig={'Comment': customer_name, 'PrivateZone': False})

    S3_HOSTED_ZONE_IDS = {
    'us-east-1': 'Z3AQBSTGFYJSTF',
    'us-west-1': 'Z2F56UZL2M1ACD',
    'us-west-2': 'Z3BJ6K6RIION7M',
    'ap-south-1': 'Z11RGJOFQNVJUP',
    'ap-northeast-1': 'Z2M4EHUR26P7ZW',
    'ap-northeast-2': 'Z3W03O7B5YMIYP',
    'ap-southeast-1': 'Z3O0J2DXBE1FTB',
    'ap-southeast-2': 'Z1WCIGYICN2BYD',
    'eu-central-1': 'Z21DNDUVLTQW6Q',
    'eu-west-1': 'Z1BKCTXD74EZPE',
    'sa-east-1': 'Z7KQH4QJS55SO',
    'us-gov-west-1': 'Z31GFT0UA1I2HV',
    }

    # Get the newly created hosted zone id
    hosted_zone_id = response['HostedZone']['Id']

    # Add DNS records for customer.smartcounts.io this needs to be the s3 name NOT the alias
    website_dns_name = customer_name+".s3-website-us-east-1.amazonaws.com"

    change_batch_payload = {
        'Changes': [
          {
            'Action': 'UPSERT',
            'ResourceRecordSet': {
                'Name': customer_name,
                'Type': 'A',
                'AliasTarget': {
                    'HostedZoneId': S3_HOSTED_ZONE_IDS[DEFAULT_REGION],
                    'DNSName': website_dns_name,
                    'EvaluateTargetHealth': False
                 }
                }
            }
        ]
    }

    # Create the DNS records payload in Route53
    response = route53.change_resource_record_sets(
        HostedZoneId=hosted_zone_id, ChangeBatch=change_batch_payload)

    # This creates a new cluster
    rds.restore_db_cluster_to_point_in_time(
        DBClusterIdentifier=db_identifier,
        RestoreType='copy-on-write',
        SourceDBClusterIdentifier='smartcounts-global',
        UseLatestRestorableTime=True,
        EnableIAMDatabaseAuthentication=False
   )

# This creates a new instance under the new cluster created
    rds.create_db_instance(
        DBClusterIdentifier=db_identifier,
        DBInstanceIdentifier=db_identifier+"aurora",
        DBInstanceClass="db.t2.small",
        Engine="aurora",
        PubliclyAccessible=True
)

    
    return {
        'statusCode': 200,
        'headers': { 'Content-Type': 'application/json' },
        'body': json.dumps({ 'Message':'S3 Bucket Created and Route 53 Updated RDS Cluster and Instance Created' })
    }
