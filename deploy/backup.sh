#!/usr/bin/env bash
# Nightly backup to S3, run by the bath-studio-backup.timer systemd unit (03:30 IST).
#   - a consistent copy of the SQLite database (online backup API, safe while the app runs)
#   - product photos and uploaded price lists, synced incrementally
# S3 layout:  s3://$BACKUP_BUCKET/backups/db/studio-YYYY-MM-DD.db   (lifecycle rule expires them after 90 days)
#             s3://$BACKUP_BUCKET/backups/images/...  .../backups/uploads/...  (bucket versioning keeps overwritten copies)
set -euo pipefail

APP_DIR=/srv/bath-studio
set -a; . "$APP_DIR/.env"; set +a
: "${BACKUP_BUCKET:?BACKUP_BUCKET not set in .env}" "${AWS_REGION:=ap-south-1}" "${BSS_IMAGE:?no deployed image yet}"
KEEP=${KEEP_LOCAL_BACKUPS:-7}
DATA="$APP_DIR/data"
STAMP=$(date -u +%Y-%m-%d)
mkdir -p "$DATA/backups" && chown 10001:10001 "$DATA/backups"   # the container runs as uid 10001

# The app image has Python's sqlite3; the host may not.
docker run --rm -v "$DATA:/d" --entrypoint python "$BSS_IMAGE" -c \
  "import sqlite3; s=sqlite3.connect('/d/studio.db'); d=sqlite3.connect('/d/backups/studio-$STAMP.db'); s.backup(d); d.close(); s.close()"

aws s3 cp --only-show-errors --region "$AWS_REGION" "$DATA/backups/studio-$STAMP.db" "s3://$BACKUP_BUCKET/backups/db/studio-$STAMP.db"
for d in images uploads; do
  if [[ -d $DATA/$d ]]; then aws s3 sync --only-show-errors --region "$AWS_REGION" "$DATA/$d" "s3://$BACKUP_BUCKET/backups/$d"; fi
done

{ ls -1t "$DATA"/backups/studio-*.db 2>/dev/null || true; } | tail -n +$((KEEP + 1)) | xargs -r rm -f
echo "$(date -u +%FT%TZ) backup OK: s3://$BACKUP_BUCKET/backups/db/studio-$STAMP.db" | tee -a "$APP_DIR/backup.log"
