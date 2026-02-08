# AWS DataSync EC2 Setup

## Intro

## Setup procedure
1) Get the ami Value from the following call for the EC2 instance we will create as the datasync agent host
``` bash
aws ssm get-parameter --name /aws/service/datasync/ami --region <region>
```
``` bash
{
    "Parameter": {
        "Name": "/aws/service/datasync/ami",
        "Type": "String",
        "Value": "ami-0fc8be1a057e769ed",
        "Version": 48,
        "LastModifiedDate": "2022-09-06T15:05:35.254000+02:00",
        "ARN": "arn:aws:ssm:af-south-1::parameter/aws/service/datasync/ami",
        "DataType": "text"
    }
}
```

2) From the AWS account where the source file system resides, launch the agent by using your AMI from the Amazon EC2 launch wizard. Use the following URL to launch the AMI.:
https://console.aws.amazon.com/ec2/v2/home?region=source-file-system-region#LaunchInstanceWizard:ami=ami-id

In the URL, replace the source-file-system-region and ami-id with your own source AWS Region and AMI ID. The Choose an Instance Type page appears on the Amazon EC2 console.

3) Choose one of the recommended instance types for your use case, and choose Next: Configure Instance Details. We recommend using one of the following instance sizes:

- m5.2xlarge: For tasks to transfer up to 20 million files.
- m5.4xlarge: For tasks to transfer more than 20 million files.

4) On the Configure Instance Details page, do the following:

For Network, choose the virtual private cloud (VPC) where your source Amazon EFS or NFS file system is located.

For Auto-assign Public IP, choose a value. For your instance to be accessible from the public internet, set Auto-assign Public IP to Enable. Otherwise, set Auto-assign Public IP to Disable. If a public IP address isn't assigned, activate the agent in your VPC by using its private IP address.

When you transfer files from an in-cloud file system, to increase performance we recommend that you choose a Placement Group value where your NFS server resides.
