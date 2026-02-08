#!/bin/bash

# Copies the most recent snapshot associated with one or more
# RDS instances from us-east-1 to us-west-1
#
# Tested with
#   $ aws --version
#   aws-cli/1.11.108 Python/3.5.2 Linux/4.4.0-81-generic botocore/1.5.71
#
# Does not work with aws-cli/1.10.x or earlier.
#
# Usage: bash rds_snapshot_copier.bash rds-instance-name-1 rds-instance-name-2

for dbid in "$@"
do
    last_snap=$(aws --region us-east-1 rds describe-db-snapshots \
                    --db-instance-identifier "$dbid" \
                    --query 'DBSnapshots[?Status==`available`]' \
                    | jq -r 'max_by(.DBSnapshotIdentifier) // empty')
    if [ -z "$last_snap" ]
    then
        echo "No prior snapshot for $dbid in us-east-1"
    else

        last_snap_id=$(echo "$last_snap" | jq -r '.DBSnapshotIdentifier')
        last_snap_arn=$(echo "$last_snap" | jq -r '.DBSnapshotArn')
        last_snap_short=${last_snap_id:4}
        echo "Found snapshot $last_snap_short in us-east-1"
        
        if aws --region us-west-1 rds describe-db-snapshots --db-snapshot-identifier "$last_snap_short" > /dev/null 2> /dev/null
        then
            echo "Also found snapshot $last_snap_short in us-west-1, skipping"
        else
            echo "Copying snapshot of $last_snap_short from us-east-1 to us-west-1"
            echo "New snapshot information:"
            aws --region us-west-1 rds copy-db-snapshot \
                --source-region us-east-1 \
                --tags Key=MultiRegionBackup,Value=true \
                --source-db-snapshot-identifier "$last_snap_arn" \
                --target-db-snapshot-identifier "$last_snap_short"
        fi

        cleanup_threshold=$(date --date="7 days ago" +"%Y-%m-%d")
        echo "Checking for snapshots of $dbid older than $cleanup_threshold in us-west-1"
        old_snaps=$(aws --region us-west-1 rds describe-db-snapshots \
                        --db-instance-identifier "$dbid" \
                        --query "DBSnapshots[?contains(Status, \`available\`) == \`true\`] | [?SnapshotCreateTime<\`$cleanup_threshold\`]")

        for old_snap_id in $(echo $old_snaps | jq -r '.[].DBSnapshotIdentifier')
        do
            echo "Deleting $old_snap_id from us-west-1"
            aws --region us-west-1 rds delete-db-snapshot --db-snapshot-identifier "$old_snap_id"            
        done
    fi    
done
