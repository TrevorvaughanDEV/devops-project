# Deployment

The app runs on a single small Ubuntu VM. It currently lives on **Azure** (a B1s VM
under Azure for Students); it ran on **AWS EC2** before that. Nothing in the pipeline
is tied to a provider: any Ubuntu server reachable over SSH works.

Nginx on the host terminates TLS with a Let's Encrypt certificate and proxies to the
app container on port 5000. GitHub Actions builds, tests and rolls out every push to `main`.

## Create the VM (Azure)

1. Azure portal → **Virtual machines → Create**.
   - Image: **Ubuntu Server 24.04 LTS**, size **B1s** (1 vCPU, 1 GB).
   - Authentication: **SSH public key**, username `azureuser`; download the private key.
   - Inbound ports: **SSH (22), HTTP (80), HTTPS (443)**.
2. After it's created: **Networking → Public IP → Configuration → Static**, so the IP
   survives restarts.
3. In the network security group, narrow the SSH rule's source to your own IP.
   GitHub Actions also needs SSH, so either keep 22 open with key-only login (the default)
   or allow the [GitHub Actions IP ranges](https://api.github.com/meta).

## Point the domain at it

At the domain registrar, set the `A` records for `@` and `www` to the VM's public IP.

## One-time server setup

SSH in (`ssh -i key.pem azureuser@<ip>`) and run:

```bash
curl -fsSL https://raw.githubusercontent.com/TrevorvaughanDEV/devops-project/main/scripts/setup-server.sh \
  | sudo bash -s -- trevorvaughan.dev you@example.com
```

[`scripts/setup-server.sh`](../scripts/setup-server.sh) checks DNS points at the VM, then
installs Docker, Nginx and Certbot, gets the certificate (auto-renewing), installs
[`nginx.conf`](nginx.conf), adds 1 GB of swap, enables the `ufw` firewall (22/80/443 only)
and turns on unattended security updates. It's safe to re-run.

## GitHub secrets

Set these under **Settings → Secrets and variables → Actions**:

| Secret | What it is |
|---|---|
| `DOCKER_USERNAME` / `DOCKER_PASSWORD` | Docker Hub login (use an access token, not your password) |
| `DEPLOY_HOST` | Public IP or DNS name of the VM. If unset, the deploy job is skipped, not failed |
| `DEPLOY_USER` | SSH user: `azureuser` on Azure, `ubuntu` on AWS (default `ubuntu`) |
| `DEPLOY_SSH_KEY` | Private key for that user |
| `APP_SECRET_KEY` | *Optional.* Flask session key. If it isn't set, the first deploy generates one on the server in `~/.devops-monitor-secret` and reuses it |

Optionally add a `production` environment with required reviewers to make deploys
need a manual approval.

## What a deploy does

1. Pulls the new image tagged with the commit SHA.
2. Records the image currently running, then removes only the app's own container.
3. Starts the new container with the `devops-monitor-data` volume, so users and visit
   counts survive deploys. On the first deploy, the database from the old container
   (which kept it at `/app/metrics.db`) is copied into the volume, so existing accounts carry over.
4. Polls `/healthz` for up to a minute. If it never passes, the new container is removed
   and the previous image is started again, and the workflow fails.

## Creating your own account

Sign-up is off in production. Existing accounts are migrated automatically. To add a new
one, temporarily run the container with `-e ALLOW_SIGNUP=true`, sign up, then redeploy.

## Backups

```bash
sudo docker run --rm -v devops-monitor-data:/data -v "$PWD":/backup alpine \
  cp /data/metrics.db /backup/metrics-$(date +%F).db
```
