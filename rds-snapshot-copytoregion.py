set -e
set -u

SOURCE_REGION=us-west-2
DEST_REGION=eu-west-1
INSTANCE_IDENTIFIER=db-instance

SNAPSHOT_ARN=$(aws rds describe-db-snapshots --region $SOURCE_REGION --db-instance-identifier "$INSTANCE_IDENTIFIER" \
--query "DBSnapshots[? Status=='available']" \
| jq -r 'sort_by(.SnapshotCreateTime) | .[-1] | .DBSnapshotArn')

TARGET_SNAPSHOT_NAME=copy-$SOURCE_REGION-${SNAPSHOT_ARN##*:}

echo Copying $SNAPSHOT_ARN from $SOURCER_REGION to $DEST_REGION as $TARGET_SNAPSHOT_NAME

aws rds copy-db-snapshot --region $DEST_REGION \
--source-db-snapshot-identifier "$SNAPSHOT_ARN" --target-db-snapshot-identifier "$TARGET_SNAPSHOT_NAME"
