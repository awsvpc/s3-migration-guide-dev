#!/bin/bash
set -euo pipefail

SRC_BUCKET="source-bucket"
DST_BUCKET="destination-bucket"
REGION="us-east-1"

echo "Starting migration at $(date)"

# -----------------------------
# Step 1: Sync current objects
# -----------------------------
echo "Syncing current objects..."
aws s3 sync s3://$SRC_BUCKET s3://$DST_BUCKET \
    --acl bucket-owner-full-control \
    --exact-timestamps \
    --metadata-directive COPY \
    --sse AES256 \
    --region $REGION \
    --only-show-errors

echo "Current objects synced."

# -----------------------------
# Step 2: Copy noncurrent objects
# -----------------------------
echo "Listing noncurrent objects..."
aws s3api list-object-versions --bucket $SRC_BUCKET --query 'Versions[?IsLatest==`false`]' --output json > noncurrent.json

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

echo "Noncurrent objects copied."

# -----------------------------
# Step 3: Recreate delete markers
# -----------------------------
echo "Listing delete markers..."
aws s3api list-object-versions --bucket $SRC_BUCKET --query 'DeleteMarkers' --output json > delete_markers.json

echo "Applying delete markers..."
cat delete_markers.json | jq -c '.[]' | while read obj; do
    KEY=$(echo "$obj" | jq -r '.Key')
    echo "Creating delete marker for: $KEY"
    aws s3api delete-object \
        --bucket $DST_BUCKET \
        --key "$KEY" \
        --region $REGION
done

echo "Delete markers applied."

# -----------------------------
# Step 4: Final summary
# -----------------------------
echo "Migration completed at $(date). Destination bucket summary:"
aws s3 ls s3://$DST_BUCKET --recursive --human-readable --summarize

echo "All steps finished successfully."
