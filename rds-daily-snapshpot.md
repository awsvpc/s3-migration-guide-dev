<pre>
  #!/bin/bash -

export AWS_ACCESS_KEY=<your aws access key>
export AWS_SECRET_KEY=<your aws secret>

date_current=`date -u +%Y-%m-%d`
aws rds describe-db-snapshots --snapshot-type "automated" --db-instance-identifier <db_instance_name> | grep `date +%Y-%m-%d` | grep rds | tr -d '",' | awk '{ print $2 }' > /tmp/sandbox-snapshot.txt
snapshot_name=`cat /tmp/<db_instance_name>-snapshot.txt`
target_snapshot_name=`cat /tmp/<db_instance_name>-snapshot.txt | sed 's/rds://'`

aws rds copy-db-snapshot --source-db-snapshot-identifier $snapshot_name --target-db-snapshot-identifier $target_snapshot_name-copy > /home/ubuntu/rds-snapshot-$date_current.log 2>&1
echo "-------------" >> /home/ubuntu/$date_current-results.txt
cat /home/ubuntu/rds-snapshot-$date_current.log >> /home/ubuntu/$date_current-results.txt
cat /home/ubuntu/$date_current-results.txt | mail -s "[Daily RDS Snapshot Backup] $date_current" <email@foo.com>
rm /home/ubuntu/$date_current-results.txt
rm /home/ubuntu/rds-snapshot-$date_current.log
</pre>

<pre>
  iam_policy.json
  {
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "Stmt1427229307000",
      "Effect": "Allow",
      "Action": [
        "rds:CreateDBSnapshot",
        "rds:CopyDBSnapshot",
        "rds:DeleteDBSnapshot",
        "rds:DescribeDBInstances",
        "rds:DescribeDBSnapshots",
        "rds:DescribeReservedDBInstances"
      ],
      "Resource": [
        "arn:aws:rds"
      ]
    }
  ]
}
</pre>
