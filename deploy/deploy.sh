#!/usr/bin/env bash
# Roll out one image on the server, with an automatic rollback if it doesn't come up healthy.
#
#   sudo /srv/bath-studio/deploy.sh <image-uri>          e.g. 1234.dkr.ecr.ap-south-1.amazonaws.com/bath-studio:3f2a9c1
#   sudo /srv/bath-studio/deploy.sh --rollback           back to the image that ran before the last deploy
#
# Run by the GitHub Actions pipeline through AWS Systems Manager, or by hand over Session Manager.
set -euo pipefail

APP_DIR=/srv/bath-studio
COMPOSE=(docker compose -f "$APP_DIR/docker-compose.prod.yml" --project-directory "$APP_DIR")
ENV_FILE="$APP_DIR/.env"
LOG="$APP_DIR/deploy.log"
HEALTH_TIMEOUT=${HEALTH_TIMEOUT:-180}

log() { echo "$(date -u +%FT%TZ) $*" | tee -a "$LOG"; }
die() { log "FAILED: $*"; exit 1; }

current_image() { grep -E '^BSS_IMAGE=' "$ENV_FILE" | head -1 | cut -d= -f2-; }
set_image() {
  if grep -qE '^BSS_IMAGE=' "$ENV_FILE"; then sed -i "s|^BSS_IMAGE=.*|BSS_IMAGE=$1|" "$ENV_FILE"; else echo "BSS_IMAGE=$1" >> "$ENV_FILE"; fi
}

wait_healthy() {
  local cid status waited=0
  while (( waited < HEALTH_TIMEOUT )); do
    cid=$("${COMPOSE[@]}" ps -q app 2>/dev/null || true)
    status=$([ -n "$cid" ] && docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$cid" 2>/dev/null || echo missing)
    [[ $status == healthy ]] && return 0
    sleep 5; waited=$((waited + 5))
  done
  log "app status after ${HEALTH_TIMEOUT}s: ${status:-unknown}"
  "${COMPOSE[@]}" logs --tail 60 app | tee -a "$LOG" || true
  return 1
}

ecr_login() {
  local registry=${1%%/*}
  [[ $registry == *.amazonaws.com ]] || return 0
  local region; region=$(echo "$registry" | cut -d. -f4)
  aws ecr get-login-password --region "$region" | docker login --username AWS --password-stdin "$registry" >/dev/null
}

[[ -f $ENV_FILE ]] || die "$ENV_FILE missing - run server-setup.sh first"
cd "$APP_DIR"

if [[ ${1:-} == --rollback ]]; then
  [[ -s $APP_DIR/.previous_image ]] || die "no previous image recorded"
  NEW=$(cat "$APP_DIR/.previous_image")
  log "manual rollback requested"
else
  NEW=${1:?usage: deploy.sh <image-uri> | --rollback}
fi
OLD=$(current_image || true)
log "deploying $NEW (was: ${OLD:-none})"

ecr_login "$NEW"
docker pull -q "$NEW" >/dev/null || die "cannot pull $NEW"

# Safety copy of the database before the new version starts (it may update the schema on startup).
if [[ -f $APP_DIR/data/studio.db ]]; then
  mkdir -p "$APP_DIR/data/backups" && chown 10001:10001 "$APP_DIR/data/backups"   # the container runs as uid 10001
  snap="$APP_DIR/data/backups/pre-deploy-$(date -u +%Y%m%dT%H%M%SZ).db"
  docker run --rm -v "$APP_DIR/data:/d" --entrypoint python "$NEW" \
    -c "import sqlite3; s=sqlite3.connect('/d/studio.db'); d=sqlite3.connect('/d/backups/$(basename "$snap")'); s.backup(d); d.close(); s.close()" \
    && log "database snapshot: $snap" || die "could not snapshot the database"
  { ls -1t "$APP_DIR"/data/backups/pre-deploy-*.db 2>/dev/null || true; } | tail -n +6 | xargs -r rm -f   # keep the last 5
fi

set_image "$NEW"
"${COMPOSE[@]}" up -d --remove-orphans

if wait_healthy; then
  [[ -n $OLD && $OLD != "$NEW" ]] && echo "$OLD" > "$APP_DIR/.previous_image"
  log "OK: $NEW is healthy"
  docker image prune -af --filter "until=168h" >/dev/null 2>&1 || true   # drop images older than a week
  exit 0
fi

if [[ -n $OLD && $OLD != "$NEW" ]]; then
  log "new version unhealthy - rolling back to $OLD"
  set_image "$OLD"
  "${COMPOSE[@]}" up -d --remove-orphans
  wait_healthy && die "rolled back to $OLD; $NEW did not become healthy" || die "rollback to $OLD is not healthy either - check the server now"
fi
die "$NEW did not become healthy and there is no previous version to return to"
