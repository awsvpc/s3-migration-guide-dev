About
This document describes the Standard Operating Procedure for migrating both an EC2 instance and an encrypted RDS database to a different AWS account and region.

For this sample case, there is a single EC2 instance which uses a single MariaDB RDS instance (no read-replica, nothing fancy). But the database is encrypted, so migrating a snapshot is a bit complicated. The end result will be that the newly deployed database instance cannot use a customer-managed KMS. To get around this you'll probably have to use a different method entirely to migrate the database (such as S3 export/import, or a manual SQL dump/import).

This case will cover an old AWS account (ID 987654321) and a new AWS account (123456789), moving from one region (eu-west-1) to another region (us-east-2).

EC2 instance migration
Login to your old AWS account. Switch to region eu-west-1.
Create a snapshot image of your original EC2 Instance.
When image is created, find it and add permissions for your new AWS account.
Login to the new AWS account. Switch to eu-west-1 region.
Navigate to AWS -> EC2 -> AMIs. Select Private images, find the new snapshot image.
Right click and select Copy AMI, and copy it into the us-east-2 region.
Switch to us-east-2 region. Nagivate to AWS -> EC2 -> AMIs. Select Owned by me, look for the newly-copying AMI.
Once this is is done being copied, navigate to AWS -> EC2 -> Instances.
Click Launch Instances. Click My AMIs. Select the newly copied snapshot.
Select the default instance type, click Next.
Select the correct VPC. Select the correct subnet (example: a private subnet). Disable public IP if not necessary. Select Protect against accidental termination. Click Next.
Specify correct disk size. Click Next.
Add tags, such as Name. Click Next.
Add security groups (example: allow ports 80 & 443). Name security group (example: same as previous Name tag). Click review and launch.
Click Launch.
Click create a new key pair. Name it after your instance Name. Download keypair. Click Launch Instances.
RDS database migration
Login to the old AWS account. Switch to region eu-west-1. Navigate to AWS -> RDS -> Databases.
Select radio button for the database instance to migrate. Click Actions → Take snapshot. Give snapshot name. Click Take snapshot.
Switch to region us-east-2. Navigate to AWS -> KMS → Customer managed keys. Click Create key.
Select Symmetric, click Next.
Enter an Alias (example: RDS). Click Next.
For Key Administrators, select the appropriate Administrator. Click Next.
For Key usage permissions, select the appropriate usage roles. In Other AWS Accounts, add the new AWS account ID (123456789). Click Next.
In the IAM policy, you probably want to make sure the new AWS account also has IAM User Permissions. Click Finish.
Switch to region eu-west-1. Navigate to AWS -> RDS -> Snapshots. Find the new snapshot. Wait for it to finish creating.
Once it’s done, select the check box next to it, then click Actions → Copy snapshot.
Select Destination Region: US East (Ohio) (this is us-east-2). Specify New DB Snapshot Identifier: same as the snapshot name. Click Copy Tags. Select RDS KMS key. Click Copy Snapshot.
Wait a while for the copy to complete. Cross-region DB snapshot copies can take a while.
Once it’s done, switch to region us-east-2. Navigate to AWS -> RDS -> Snapshots. Find the newly copied snapshot and select the check box next to it. Then click Actions → Share snapshot.
Add new AWS account ID (123456789). Click Save.
Login to the new AWS account (123456789). Switch to the us-east-2 region.
Navigate to AWS -> RDS -> Subnet groups. Click Create DB Subnet Group.
Name: new-instance-migration. Description: Subnet group for newly migrated database. Select the correct VPC. Select a couple of AZs. Select the subnet in each AZ that you selected previously (example: private subnet). Click Create.
Navigate to AWS -> RDS -> Snapshots. Click Shared with me.
Select the new snapshot. Click Actions → Copy Snapshot.
Enter New DB Snapshot Identifier: same name as the snapshot. Click Copy snapshot.
Navigate to AWS -> RDS -> Snapshots. Wait for snapshot to be finished copying.
Select newly copied snapshot. Click Actions → Restore snapshot.
Make sure Engine is MariaDB. For Db Instance Identifier enter the new name of the migrated instance. Select the correct VPC. Select Subnet group you just created. For Public access, select No if this is a private subnet. For VPC security group, select the security group you created above. Note that you cannot choose the KMS key, you are forced to accept the default aws/rds key. Click Additional information. Uncheck Enable auto minor version upgrade. Click Restore DB Instance.
