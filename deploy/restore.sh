#!/usr/bin/env bash
# Restore the database (and optionally photos/uploads) from the S3 backup.
#
#   sudo /srv/bath-studio/restore.sh 2026-11-20            # database of that day + current photos/uploads from S3
#   sudo /srv/bath-studio/restore.sh 2026-11-20 --db-only  # database only
#
# The current database is kept as data/studio.db.before-restore-<time>.
set -euo pipefail

APP_DIR=/srv/bath-studio
set -a; . "$APP_DIR/.env"; set +a
DAY=${1:?usage: restore.sh YYYY-MM-DD [--db-only]}
COMPOSE=(docker compose -f "$APP_DIR/docker-compose.prod.yml" --project-directory "$APP_DIR")
DATA="$APP_DIR/data"

aws s3 cp --region "${AWS_REGION:-ap-south-1}" "s3://$BACKUP_BUCKET/backups/db/studio-$DAY.db" "/tmp/studio-$DAY.db"

"${COMPOSE[@]}" stop app
KEEP_AS="before-restore-$(date -u +%Y%m%dT%H%M%SZ)"
for f in studio.db studio.db-wal studio.db-shm; do
  if [[ -f $DATA/$f ]]; then mv "$DATA/$f" "$DATA/$f.$KEEP_AS"; fi
done
install -o 10001 -g 10001 -m 640 "/tmp/studio-$DAY.db" "$DATA/studio.db"
if [[ ${2:-} != --db-only ]]; then
  for d in images uploads; do aws s3 sync --only-show-errors --region "${AWS_REGION:-ap-south-1}" "s3://$BACKUP_BUCKET/backups/$d" "$DATA/$d"; done
  chown -R 10001:10001 "$DATA"
fi
"${COMPOSE[@]}" start app
echo "restored database of $DAY"
