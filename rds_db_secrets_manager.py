import boto3
import botocore
import sys
import json
import time
import getpass

ROLE_NAME = "OrganizationAccountAccessRole"
REGION = "us-east-1"

KMS_KEY_ARN = "arn:aws:kms:us-east-1:ACCOUNT:key/KEYID"

TAGS = [
    {"Key": "Project", "Value": "DB-Migration"},
    {"Key": "Owner", "Value": "Platform-Team"},
    {"Key": "Environment", "Value": "NonProd"}
]

ACCOUNT_NETWORK_MAP = {
    "12312312313": {
        "vpc_id": "vpc-12311313",
        "subnets": ["subnet-123131", "subnet-123131231"],
        "security_group": "sg-11111111"
    },
    "646456464666": {
        "vpc_id": "vpc-67811313",
        "subnets": ["subnet-678131", "subnet-678131231"],
        "security_group": "sg-22222222"
    }
}

# ---------- STS ----------
def assume_role(account_id):
    sts = boto3.client("sts")
    role_arn = f"arn:aws:iam::{account_id}:role/{ROLE_NAME}"
    resp = sts.assume_role(RoleArn=role_arn, RoleSessionName="rds-manager")

    creds = resp["Credentials"]
    session = boto3.Session(
        aws_access_key_id=creds["AccessKeyId"],
        aws_secret_access_key=creds["SecretAccessKey"],
        aws_session_token=creds["SessionToken"],
        region_name=REGION
    )
    return session

# ---------- SECRETS ----------
def create_secret(sm, name, username, password, dry_run):
    secret_payload = json.dumps({"username": username, "password": password})
    if dry_run:
        print(f"[DRY-RUN] Create secret {name}")
        return name

    sm.create_secret(
        Name=name,
        SecretString=secret_payload,
        KmsKeyId=KMS_KEY_ARN,
        Tags=TAGS
    )
    return name

# ---------- COMMON ----------
def maybe(action, dry_run, description):
    if dry_run:
        print(f"[DRY-RUN] {description}")
        return False
    return True

# ---------- CREATE RDS ----------
def create_rds_instance(session, net, dry_run):
    rds = session.client("rds")
    sm = session.client("secretsmanager")

    identifier = input("RDS identifier: ")
    username = input("Master username: ")
    password = getpass.getpass("Master password: ")

    secret_name = f"rds/{identifier}/master-credentials"
    create_secret(sm, secret_name, username, password, dry_run)

    if maybe(True, dry_run, f"Create subnet group for {identifier}"):
        rds.create_db_subnet_group(
            DBSubnetGroupName=f"{identifier}-subnet-group",
            DBSubnetGroupDescription="Managed by script",
            SubnetIds=net["subnets"],
            Tags=TAGS
        )

    print("Creating RDS PostgreSQL instance...")

    if not maybe(True, dry_run, f"Create RDS instance {identifier}"):
        return

    rds.create_db_instance(
        DBInstanceIdentifier=identifier,
        Engine="postgres",
        EngineVersion="15.3",
        DBInstanceClass="db.t3.medium",
        AllocatedStorage=20,
        StorageEncrypted=True,
        KmsKeyId=KMS_KEY_ARN,
        MasterUsername=username,
        MasterUserPassword=password,
        Port=5432,
        VpcSecurityGroupIds=[net["security_group"]],
        DBSubnetGroupName=f"{identifier}-subnet-group",
        BackupRetentionPeriod=7,
        PubliclyAccessible=False,
        Tags=TAGS
    )

    print("⏳ Waiting for RDS to become available...")
    rds.get_waiter("db_instance_available").wait(DBInstanceIdentifier=identifier)

    db = rds.describe_db_instances(DBInstanceIdentifier=identifier)["DBInstances"][0]
    print("\n✅ RDS READY")
    print("ARN:", db["DBInstanceArn"])
    print("Endpoint:", db["Endpoint"]["Address"])
    print("Port:", db["Endpoint"]["Port"])

# ---------- CREATE AURORA ----------
def create_aurora(session, net, dry_run):
    rds = session.client("rds")
    sm = session.client("secretsmanager")

    cluster_id = input("Aurora cluster identifier: ")
    instance_id = f"{cluster_id}-instance-1"
    username = input("Master username: ")
    password = getpass.getpass("Master password: ")

    secret_name = f"aurora/{cluster_id}/master-credentials"
    create_secret(sm, secret_name, username, password, dry_run)

    if not maybe(True, dry_run, f"Create Aurora cluster {cluster_id}"):
        return

    rds.create_db_cluster(
        DBClusterIdentifier=cluster_id,
        Engine="aurora-postgresql",
        EngineVersion="15.2",
        MasterUsername=username,
        MasterUserPassword=password,
        StorageEncrypted=True,
        KmsKeyId=KMS_KEY_ARN,
        Port=5432,
        VpcSecurityGroupIds=[net["security_group"]],
        DBSubnetGroupName=f"{cluster_id}-subnet-group",
        BackupRetentionPeriod=7,
        Tags=TAGS
    )

    rds.create_db_instance(
        DBInstanceIdentifier=instance_id,
        DBInstanceClass="db.r6g.large",
        Engine="aurora-postgresql",
        DBClusterIdentifier=cluster_id,
        Tags=TAGS
    )

    print("⏳ Waiting for Aurora cluster...")
    rds.get_waiter("db_cluster_available").wait(DBClusterIdentifier=cluster_id)

    cluster = rds.describe_db_clusters(DBClusterIdentifier=cluster_id)["DBClusters"][0]
    print("\n✅ AURORA READY")
    print("ARN:", cluster["DBClusterArn"])
    print("Endpoint:", cluster["Endpoint"])
    print("Port:", cluster["Port"])

# ---------- MAIN ----------
def main():
    account_id = input("Enter AWS account ID: ")
    dry_run = input("Dry run mode? (yes/no): ").lower() == "yes"

    if account_id not in ACCOUNT_NETWORK_MAP:
        print("Unsupported account")
        sys.exit(1)

    session = assume_role(account_id)
    net = ACCOUNT_NETWORK_MAP[account_id]

    print("""
1. Create RDS PostgreSQL
2. Create Aurora PostgreSQL
""")

    choice = input("Choose option: ")

    if choice == "1":
        create_rds_instance(session, net, dry_run)
    elif choice == "2":
        create_aurora(session, net, dry_run)
    else:
        print("Invalid option")

if __name__ == "__main__":
    main()
