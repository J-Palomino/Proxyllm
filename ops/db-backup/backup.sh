#!/bin/sh
set -eu

: "${DATABASE_URL:?DATABASE_URL is required}"
: "${S3_ENDPOINT:?S3_ENDPOINT is required}"
: "${S3_ACCESS_KEY_ID:?S3_ACCESS_KEY_ID is required}"
: "${S3_SECRET_ACCESS_KEY:?S3_SECRET_ACCESS_KEY is required}"
: "${S3_BUCKET:?S3_BUCKET is required}"

RETENTION_COUNT="${RETENTION_COUNT:-30}"
TIMESTAMP=$(date -u +%Y%m%d-%H%M%S)
FILE="litellm-db-${TIMESTAMP}.sql.gz"

echo "Dumping database to /tmp/${FILE}..."
pg_dump "$DATABASE_URL" | gzip > "/tmp/${FILE}"

echo "Configuring mc alias..."
mc alias set backup "$S3_ENDPOINT" "$S3_ACCESS_KEY_ID" "$S3_SECRET_ACCESS_KEY" >/dev/null

echo "Uploading ${FILE} to bucket ${S3_BUCKET}..."
mc cp "/tmp/${FILE}" "backup/${S3_BUCKET}/${FILE}"

echo "Applying retention (keep last ${RETENTION_COUNT})..."
mc ls "backup/${S3_BUCKET}/" | awk '{print $NF}' | sort | head -n -"${RETENTION_COUNT}" | while read -r old; do
  [ -n "$old" ] && mc rm "backup/${S3_BUCKET}/${old}"
done

rm -f "/tmp/${FILE}"
echo "Backup complete: ${FILE}"
