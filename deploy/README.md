# Deploying Bath Solution Studio on AWS

The full guide for DevOps (architecture, AWS resources, IAM, first-time setup, operations) is the
"Bath Solution Studio – AWS Deployment & CI/CD" document. This file is the short map of what is in this folder.

## How a change reaches production

push to `main` → GitHub Actions (`.github/workflows/deploy.yml`): tests → Docker image → ECR (`bath-studio:<commit>`)
→ files in this folder uploaded to `s3://<bucket>/releases/<commit>/` → Systems Manager runs `deploy.sh` on the EC2 server
→ health check, automatic rollback if unhealthy → pipeline checks `https://<domain>/healthz` reports the new commit.

Pull requests run the tests only. Until the repository variable `EC2_INSTANCE_ID` is set, pushes run the tests and skip the deploy.

## Files

| File | Where it ends up | What it does |
|---|---|---|
| `docker-compose.prod.yml` | `/srv/bath-studio/` | App + Caddy (HTTPS). Data on `/srv/bath-studio/data` (EBS). |
| `Caddyfile` | `/srv/bath-studio/` | TLS (Let's Encrypt), security headers, 210 MB upload limit, proxy to the app. |
| `deploy.sh` | `/srv/bath-studio/` | Pull image, snapshot DB, `up -d`, wait for healthy, roll back on failure. `--rollback` = previous image. |
| `backup.sh` | `/srv/bath-studio/` | Nightly (systemd timer, 03:30 IST): DB snapshot + photos/uploads to `s3://<bucket>/backups/`. |
| `restore.sh` | `/srv/bath-studio/` | `restore.sh YYYY-MM-DD [--db-only]` from S3. |
| `server-setup.sh` | run once | Installs Docker, mounts the data volume, writes `.env` (with a setup code), enables the backup timer. |
| `.env.example` | `/srv/bath-studio/.env` | Server settings. `server-setup.sh` creates the real file (chmod 600). Never commit it. |
| `iam/*.json` | IAM / S3 / ECR | OIDC trust + deploy policy for GitHub, instance role policy, bucket and ECR lifecycle rules. Replace `ACCOUNT_ID`, `REGION`, `BUCKET_NAME`, `INSTANCE_ID`. |

## GitHub repository variables (Settings → Secrets and variables → Actions → Variables)

| Variable | Example |
|---|---|
| `AWS_REGION` | `ap-south-1` |
| `AWS_DEPLOY_ROLE_ARN` | `arn:aws:iam::123456789012:role/bath-studio-github-deploy` |
| `ECR_REPOSITORY` | `bath-studio` |
| `ARTIFACT_BUCKET` | `bath-studio-123456789012` |
| `EC2_INSTANCE_ID` | `i-0abc123def4567890` |
| `APP_URL` | `https://studio.example.com` |

No secrets are stored in GitHub: AWS access is by OIDC role, scoped to the `production` environment of this repository.

## Everyday commands (on the server, via Session Manager)

```
sudo docker compose -f /srv/bath-studio/docker-compose.prod.yml --project-directory /srv/bath-studio ps
sudo docker compose -f /srv/bath-studio/docker-compose.prod.yml --project-directory /srv/bath-studio logs -f app
sudo /srv/bath-studio/deploy.sh --rollback
sudo systemctl start bath-studio-backup.service    # backup now
tail -50 /srv/bath-studio/deploy.log /srv/bath-studio/backup.log
```

Rollback to any earlier build without the server: Actions → CI/CD → Run workflow → `image_tag` = that commit's 7-character id.
