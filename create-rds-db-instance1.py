import boto3
import botocore
import sys
import time

ROLE_NAME = "OrganizationAccountAccessRole"
REGION = "us-east-1"

# Account-specific networking config
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
    resp = sts.assume_role(
        RoleArn=role_arn,
        RoleSessionName="rds-aurora-manager"
    )

    creds = resp["Credentials"]
    return boto3.client(
        "rds",
        region_name=REGION,
        aws_access_key_id=creds["AccessKeyId"],
        aws_secret_access_key=creds["SecretAccessKey"],
        aws_session_token=creds["SessionToken"]
    )

# ---------- COMMON ----------
def create_subnet_group(rds, name, subnets):
    print(f"Creating subnet group {name}")
    rds.create_db_subnet_group(
        DBSubnetGroupName=name,
        DBSubnetGroupDescription="Managed by script",
        SubnetIds=subnets
    )

def create_parameter_group(rds, name, family):
    print(f"Creating parameter group {name}")
    rds.create_db_parameter_group(
        DBParameterGroupName=name,
        DBParameterGroupFamily=family,
        Description="Managed by script"
    )

def create_option_group(rds, name, engine, major_version):
    print(f"Creating option group {name}")
    rds.create_option_group(
        OptionGroupName=name,
        EngineName=engine,
        MajorEngineVersion=major_version,
        OptionGroupDescription="Managed by script"
    )

# ---------- CREATE RDS ----------
def create_rds_instance(rds, net):
    identifier = input("Enter RDS instance identifier: ")
    master_user = input("Master username: ")
    master_pass = input("Master password: ")

    subnet_group = f"{identifier}-subnet-group"
    param_group = f"{identifier}-param-group"
    option_group = f"{identifier}-option-group"

    create_subnet_group(rds, subnet_group, net["subnets"])
    create_parameter_group(rds, param_group, "postgres15")
    create_option_group(rds, option_group, "postgres", "15")

    print("Creating RDS PostgreSQL instance...")
    resp = rds.create_db_instance(
        DBInstanceIdentifier=identifier,
        Engine="postgres",
        EngineVersion="15.3",
        DBInstanceClass="db.t3.medium",
        AllocatedStorage=20,
        MasterUsername=master_user,
        MasterUserPassword=master_pass,
        Port=5432,
        VpcSecurityGroupIds=[net["security_group"]],
        DBSubnetGroupName=subnet_group,
        DBParameterGroupName=param_group,
        OptionGroupName=option_group,
        BackupRetentionPeriod=7,
        PubliclyAccessible=False
    )

    print("Waiting for DB to become available...")
    waiter = rds.get_waiter("db_instance_available")
    waiter.wait(DBInstanceIdentifier=identifier)

    db = rds.describe_db_instances(DBInstanceIdentifier=identifier)["DBInstances"][0]
    print("\n✅ RDS CREATED")
    print("ARN:", db["DBInstanceArn"])
    print("Endpoint:", db["Endpoint"]["Address"])
    print("Port:", db["Endpoint"]["Port"])

# ---------- CREATE AURORA ----------
def create_aurora_cluster(rds, net):
    cluster_id = input("Enter Aurora cluster identifier: ")
    instance_id = f"{cluster_id}-instance-1"
    master_user = input("Master username: ")
    master_pass = input("Master password: ")

    subnet_group = f"{cluster_id}-subnet-group"
    param_group = f"{cluster_id}-cluster-param-group"

    create_subnet_group(rds, subnet_group, net["subnets"])
    rds.create_db_cluster_parameter_group(
        DBClusterParameterGroupName=param_group,
        DBParameterGroupFamily="aurora-postgresql15",
        Description="Managed by script"
    )

    print("Creating Aurora PostgreSQL cluster...")
    rds.create_db_cluster(
        DBClusterIdentifier=cluster_id,
        Engine="aurora-postgresql",
        EngineVersion="15.2",
        MasterUsername=master_user,
        MasterUserPassword=master_pass,
        Port=5432,
        VpcSecurityGroupIds=[net["security_group"]],
        DBSubnetGroupName=subnet_group,
        DBClusterParameterGroupName=param_group,
        BackupRetentionPeriod=7
    )

    print("Creating Aurora instance...")
    rds.create_db_instance(
        DBInstanceIdentifier=instance_id,
        DBInstanceClass="db.r6g.large",
        Engine="aurora-postgresql",
        DBClusterIdentifier=cluster_id
    )

    waiter = rds.get_waiter("db_cluster_available")
    waiter.wait(DBClusterIdentifier=cluster_id)

    cluster = rds.describe_db_clusters(DBClusterIdentifier=cluster_id)["DBClusters"][0]
    print("\n✅ AURORA CREATED")
    print("ARN:", cluster["DBClusterArn"])
    print("Endpoint:", cluster["Endpoint"])
    print("Port:", cluster["Port"])

# ---------- DELETE ----------
def delete_rds_instance(rds):
    identifier = input("Enter RDS instance identifier to delete: ")
    confirm = input("Do you want to continue? (yes/no): ").lower()

    if confirm != "yes":
        print("Aborted")
        return

    try:
        rds.describe_db_instances(DBInstanceIdentifier=identifier)
        rds.delete_db_instance(
            DBInstanceIdentifier=identifier,
            SkipFinalSnapshot=True
        )
        print("🗑️ RDS deletion initiated")
    except botocore.exceptions.ClientError:
        print("❌ RDS instance not found")

def delete_aurora_cluster(rds):
    cluster_id = input("Enter Aurora cluster identifier to delete: ")
    confirm = input("Do you want to continue? (yes/no): ").lower()

    if confirm != "yes":
        print("Aborted")
        return

    try:
        instances = rds.describe_db_instances()["DBInstances"]
        for i in instances:
            if i.get("DBClusterIdentifier") == cluster_id:
                rds.delete_db_instance(
                    DBInstanceIdentifier=i["DBInstanceIdentifier"],
                    SkipFinalSnapshot=True
                )

        rds.delete_db_cluster(
            DBClusterIdentifier=cluster_id,
            SkipFinalSnapshot=True
        )
        print("🗑️ Aurora cluster deletion initiated")
    except botocore.exceptions.ClientError:
        print("❌ Aurora cluster not found")

# ---------- MAIN ----------
def main():
    account_id = input("Enter AWS account ID: ")
    if account_id not in ACCOUNT_NETWORK_MAP:
        print("Account not supported")
        sys.exit(1)

    rds = assume_role(account_id)
    net = ACCOUNT_NETWORK_MAP[account_id]

    print("""
Choose an option:
1. Create RDS PostgreSQL DB instance
2. Create Aurora PostgreSQL cluster + instance
3. Delete RDS DB instance
4. Delete Aurora DB cluster
""")

    choice = input("Enter choice (1-4): ")

    if choice == "1":
        create_rds_instance(rds, net)
    elif choice == "2":
        create_aurora_cluster(rds, net)
    elif choice == "3":
        delete_rds_instance(rds)
    elif choice == "4":
        delete_aurora_cluster(rds)
    else:
        print("Invalid choice")

if __name__ == "__main__":
    main()
