#################
# Configuration #
#################

locals {
  aws_region                     = "<your-aws-region>"
  aws_access_key                 = "<your-aws-access-key>"
  aws_secret_key                 = "<your-aws-secret-key>"
  sys_name                       = "<sys-name>"
  sys_ami_id                     = "ami-xxx"  # AMI ID of the base image for created EC2 instances for this demonstration
  sys_backup_schedule_expression = "cron(0 0 ? * * *)"  # Can be changed
  start_window_minutes           = 60  # Can be changed
  completion_window_minutes      = 10080  # Can be changed
}

#############
# Providers #
#############

terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 4.0"
    }
  }
}

provider "aws" {
  region     = local.aws_region
  access_key = local.aws_access_key
  secret_key = local.aws_secret_key
}

#################
# IAM resources #
#################

resource "aws_iam_role" "backup_default_service_role" {
  name        = "${local.sys_name}-AWSBackupDefaultServiceRole"
  path        = "/service-role/"
  description = "Provides AWS Backup permission to create backups and perform restores on your behalf across AWS services"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "backup.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })

  managed_policy_arns = [
    "arn:aws:iam::aws:policy/service-role/AWSBackupServiceRolePolicyForBackup",
    "arn:aws:iam::aws:policy/service-role/AWSBackupServiceRolePolicyForRestores"
  ]
}

####################
# Backup resources #
####################

resource "aws_backup_vault" "ec2_backup_vault" {
  name          = "${local.sys_name}-ec2-backup-vault"
  force_destroy = true
}

resource "aws_backup_plan" "ec2_backup_plan" {
  name = "${local.sys_name}-ec2-backup-plan"

  rule {
    rule_name = "${local.sys_name}-ec2-backup-rule"

    schedule          = "${local.sys_backup_schedule_expression}"
    start_window      = local.start_window_minutes
    completion_window = local.completion_window_minutes
    target_vault_name = aws_backup_vault.ec2_backup_vault.name

    enable_continuous_backup = false
    recovery_point_tags      = {}

    lifecycle {
      cold_storage_after = 0
      delete_after       = 7
    }
  }
}

resource "aws_backup_selection" "ec2_app_server_backup_rsrc" {
  name         = "${local.sys_name}-ec2-app_server-backup-rsrc"
  plan_id      = aws_backup_plan.ec2_backup_plan.id
  iam_role_arn = aws_iam_role.backup_default_service_role.arn
  resources    = ["*"]

  condition {
    string_equals {
      key   = "aws:ResourceTag/Component"
      value = "ApplicationServer"
    }
    string_equals {
      key   = "aws:ResourceTag/IsBackedUp"
      value = "true"
    }
  }
}

#################
# VPC resources #
#################

# NOTE: I create the EC2 instance in the default VPC, subnet, and security group. I decide not to create a new one to concise this gist.

data "aws_vpc" "default_vpc" {
  default = true
}

data "aws_subnets" "default_subnets" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default_vpc.id]
  }
}

data "aws_security_groups" "default_sgs" {
  filter {
    name   = "group-name"
    values = ["default"]
  }
  
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default_vpc.id]
  }
}

locals {
  selected_subnet_id = data.aws_subnets.default_subnets.ids[0]
  selected_sg_id     = data.aws_security_groups.default_sgs.ids[0]
}

#################
# EC2 resources #
#################

#---------------------------------------#
# App server (expected to be backed up) #
#---------------------------------------#

resource "aws_network_interface" "app_server_eni" {
  subnet_id = local.selected_subnet_id
  security_groups = [local.selected_sg_id]

  tags = {
    Name = "${local.sys_name}-app-server-i"
  }
}

resource "aws_instance" "app_server_i" {
  ami           = local.sys_ami_id
  instance_type = "t3.micro"

  # Networking
  network_interface {
    network_interface_id = aws_network_interface.app_server_eni.id
    device_index         = 0
  }

  # Storage
  root_block_device {
    volume_type = "gp2"
    volume_size = 80

    tags = {
      Name = "${local.sys_name}-app-server-i"
    }
  }

  tags = {
    Name        = "${local.sys_name}-app-server-i"
    Component   = "ApplicationServer"
    IsBackedUp  = "true"
  }
}

#------------------------------------------#
# DB server (expected not to be backed up) #
#------------------------------------------#

resource "aws_network_interface" "db_server_eni" {
  subnet_id = local.selected_subnet_id
  security_groups = [local.selected_sg_id]

  tags = {
    Name = "${local.sys_name}-db-server-i"
  }
}

resource "aws_instance" "db_server_i" {
  ami           = local.sys_ami_id
  instance_type = "t3.micro"

  # Networking
  network_interface {
    network_interface_id = aws_network_interface.db_server_eni.id
    device_index         = 0
  }

  # Storage
  root_block_device {
    volume_type = "gp2"
    volume_size = 80

    tags = {
      Name = "${local.sys_name}-db-server-i"
    }
  }

  tags = {
    Name        = "${local.sys_name}-db-server-i"
    Component   = "DBServer"
    IsBackedUp  = "true"
  }
}
