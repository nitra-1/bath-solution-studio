#!/usr/bin/env bash
# One-time preparation of a fresh EC2 instance (Amazon Linux 2023, x86_64 or arm64).
# Run as root once, over Session Manager:
#   sudo bash server-setup.sh <data-device> <domain> <acme-email> <backup-bucket>
#   e.g. sudo bash server-setup.sh /dev/nvme1n1 studio.example.com devops@example.com bath-studio-backups-123456789012
# Safe to run again: it skips what is already done and never formats a volume that has a filesystem.
set -euo pipefail

DEV=${1:?data volume device, e.g. /dev/nvme1n1}
DOMAIN=${2:?domain}
EMAIL=${3:?acme e-mail}
BUCKET=${4:?backup bucket}
APP_DIR=/srv/bath-studio
REGION=$(TOKEN=$(curl -s -X PUT http://169.254.169.254/latest/api/token -H 'X-aws-ec2-metadata-token-ttl-seconds: 60'); \
         curl -s -H "X-aws-ec2-metadata-token: $TOKEN" http://169.254.169.254/latest/meta-data/placement/region)

echo "== packages"
dnf -y -q install docker cronie >/dev/null
systemctl enable --now docker
if ! docker compose version >/dev/null 2>&1; then
  ARCH=$(uname -m); mkdir -p /usr/local/lib/docker/cli-plugins
  curl -fsSL "https://github.com/docker/compose/releases/download/v2.29.7/docker-compose-linux-${ARCH}" -o /usr/local/lib/docker/cli-plugins/docker-compose
  chmod +x /usr/local/lib/docker/cli-plugins/docker-compose
fi
docker compose version

echo "== data volume $DEV -> $APP_DIR/data"
mkdir -p "$APP_DIR/data"
if ! blkid "$DEV" >/dev/null 2>&1; then mkfs.xfs -q "$DEV"; fi
UUID=$(blkid -s UUID -o value "$DEV")
grep -q "$UUID" /etc/fstab || echo "UUID=$UUID $APP_DIR/data xfs defaults,nofail 0 2" >> /etc/fstab
mountpoint -q "$APP_DIR/data" || mount "$APP_DIR/data"
mkdir -p "$APP_DIR/data/backups"
chown -R 10001:10001 "$APP_DIR/data"          # the app container runs as uid 10001

echo "== configuration"
if [[ ! -f $APP_DIR/.env ]]; then
  TOKEN=$(head -c 18 /dev/urandom | base64 | tr -dc 'A-Za-z0-9' | head -c 20)
  cat > "$APP_DIR/.env" <<ENV
BSS_DOMAIN=$DOMAIN
ACME_EMAIL=$EMAIL
BSS_SETUP_TOKEN=$TOKEN
BSS_SECURE_COOKIES=1
AWS_REGION=$REGION
BACKUP_BUCKET=$BUCKET
KEEP_LOCAL_BACKUPS=7
BSS_IMAGE=
ENV
  chmod 600 "$APP_DIR/.env"
  echo "   setup code for the first admin: $TOKEN   (also in $APP_DIR/.env)"
fi

echo "== nightly backup timer (22:00 UTC = 03:30 IST)"
cat > /etc/systemd/system/bath-studio-backup.service <<UNIT
[Unit]
Description=Bath Solution Studio backup to S3
After=docker.service
[Service]
Type=oneshot
ExecStart=/bin/bash $APP_DIR/backup.sh
UNIT
cat > /etc/systemd/system/bath-studio-backup.timer <<UNIT
[Unit]
Description=Nightly Bath Solution Studio backup
[Timer]
OnCalendar=*-*-* 22:00:00 UTC
Persistent=true
[Install]
WantedBy=timers.target
UNIT
systemctl daemon-reload
systemctl enable --now bath-studio-backup.timer

echo "== done. The first push to main (or a manual run of the Deploy workflow) installs the app."
