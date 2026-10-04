# Deployment

The app runs on a single AWS EC2 instance (Ubuntu). Nginx on the host terminates TLS
with a Let's Encrypt certificate and proxies to the app container on port 5000.
GitHub Actions builds, tests and rolls out every push to `main`.

## One-time server setup

```bash
# Docker
curl -fsSL https://get.docker.com | sudo sh

# Nginx + Certbot
sudo apt install -y nginx certbot

# Get the certificate first: the Nginx config below refers to it
sudo systemctl stop nginx
sudo certbot certonly --standalone -d trevorvaughan.dev -d www.trevorvaughan.dev \
  --pre-hook "systemctl stop nginx" --post-hook "systemctl start nginx"  # saved for auto-renewal

sudo cp docs/nginx.conf /etc/nginx/sites-available/devops-monitor
sudo ln -s /etc/nginx/sites-available/devops-monitor /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl reload nginx   # the post-hook already restarted Nginx
```

In the EC2 security group, allow 22 (your IP only), 80 and 443. Port 5000 does not need
to be open to the internet because Nginx reaches the container locally.

## GitHub secrets

Set these under **Settings → Secrets and variables → Actions**:

| Secret | What it is |
|---|---|
| `DOCKER_USERNAME` / `DOCKER_PASSWORD` | Docker Hub login (use an access token, not your password) |
| `AWS_HOST` | Public IP or DNS name of the EC2 instance |
| `AWS_SSH_KEY` | Private key for the `ubuntu` user |
| `APP_SECRET_KEY` | Flask session key: `python -c "import secrets; print(secrets.token_hex(32))"` |

Optionally add a `production` environment with required reviewers to make deploys
need a manual approval.

## What a deploy does

1. Pulls the new image tagged with the commit SHA.
2. Records the image currently running, then removes only the app's own container.
3. Starts the new container with the `devops-monitor-data` volume, so users and visit
   counts survive deploys.
4. Polls `/healthz` for up to a minute. If it never passes, the new container is removed
   and the previous image is started again, and the workflow fails.

## Creating your own account

Sign-up is off in production. To create an account, temporarily run the container with
`-e ALLOW_SIGNUP=true`, sign up, then redeploy.

## Backups

```bash
sudo docker run --rm -v devops-monitor-data:/data -v "$PWD":/backup alpine \
  cp /data/metrics.db /backup/metrics-$(date +%F).db
```
