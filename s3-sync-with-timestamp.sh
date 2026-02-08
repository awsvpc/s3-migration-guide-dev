#!/bin/bash
set -euo pipefail

SRC_BUCKET="source-bucket"
DST_BUCKET="destination-bucket"
REGION="us-east-1"
# Timestamp to filter objects: format YYYY-MM-DDTHH:MM:SS (UTC)
# Example: 2026-02-01T00:00:00
SINCE_TIMESTAMP=${1:-"2026-02-01T00:00:00"}

echo "Starting incremental migration at $(date)"
echo "Including only objects/versions after: $SINCE_TIMESTAMP"

# -----------------------------
# Step 1: Sync current objects (incremental)
# -----------------------------
echo "Syncing current objects..."
aws s3 sync s3://$SRC_BUCKET s3://$DST_BUCKET \
    --acl bucket-owner-full-control \
    --exact-timestamps \
    --metadata-directive COPY \
    --sse AES256 \
    --region $REGION \
    --only-show-errors \
    --exclude "*" \
    --include "*" \
    --size-only \
    # Note: s3 sync does not support filtering by LastModified, so size or prefix filters can be used for partial sync

echo "Current objects sync completed."

# -----------------------------
# Step 2: Copy noncurrent objects modified after SINCE_TIMESTAMP
# -----------------------------
echo "Listing noncurrent objects modified after $SINCE_TIMESTAMP..."
aws s3api list-object-versions \
    --bucket $SRC_BUCKET \
    --query "Versions[?IsLatest==\`false\` && LastModified>=\`$SINCE_TIMESTAMP\`]" \
    --output json > noncurrent.json

if [[ -s noncurrent.json ]]; then
    echo "Copying noncurrent objects..."
    cat noncurrent.json | jq -c '.[]' | while read obj; do
        KEY=$(echo "$obj" | jq -r '.Key')
        VERSION=$(echo "$obj" | jq -r '.VersionId')
        echo "Copying noncurrent object: $KEY (version: $VERSION)"
        aws s3api copy-object \
            --bucket $DST_BUCKET \
            --key "$KEY" \
            --copy-source "$SRC_BUCKET/$KEY?versionId=$VERSION" \
            --acl bucket-owner-full-control \
            --metadata-directive COPY \
            --server-side-encryption AES256 \
            --region $REGION
    done
else
    echo "No new noncurrent objects since $SINCE_TIMESTAMP"
fi

# -----------------------------
# Step 3: Apply delete markers after SINCE_TIMESTAMP
# -----------------------------
echo "Listing delete markers after $SINCE_TIMESTAMP..."
aws s3api list-object-versions \
    --bucket $SRC_BUCKET \
    --query "DeleteMarkers[?LastModified>=\`$SINCE_TIMESTAMP\`]" \
    --output json > delete_markers.json

if [[ -s delete_markers.json ]]; then
    echo "Applying delete markers..."
    cat delete_markers.json | jq -c '.[]' | while read obj; do
        KEY=$(echo "$obj" | jq -r '.Key')
        echo "Creating delete marker for: $KEY"
        aws s3api delete-object \
            --bucket $DST_BUCKET \
            --key "$KEY" \
            --region $REGION
    done
else
    echo "No delete markers since $SINCE_TIMESTAMP"
fi

# -----------------------------
# Step 4: Final summary
# -----------------------------
echo "Incremental migration completed at $(date). Destination bucket summary:"
aws s3 ls s3://$DST_BUCKET --recursive --human-readable --summarize

echo "All steps finished successfully."
