#!/usr/bin/env bash
# One-time setup for a fresh Ubuntu 22.04/24.04 VM (Azure, AWS or anything else).
# Installs Docker, Nginx and a Let's Encrypt certificate, adds swap for small VMs,
# and turns on the firewall and automatic security updates.
#
# Point the domain's A records at the VM first, then run on the VM:
#   curl -fsSL https://raw.githubusercontent.com/TrevorvaughanDEV/devops-project/main/scripts/setup-server.sh -o setup.sh
#   sudo bash setup.sh trevorvaughan.dev you@example.com
# (Download first rather than piping into bash: installers that read stdin would eat the script.)
#
# After this, the first push to main (or re-running the workflow) deploys the app.
set -euo pipefail

DOMAIN="${1:?usage: setup-server.sh <domain> <email for Let's Encrypt>}"
EMAIL="${2:?usage: setup-server.sh <domain> <email for Let's Encrypt>}"
REPO_RAW="https://raw.githubusercontent.com/TrevorvaughanDEV/devops-project/main"
DEPLOY_USER="${SUDO_USER:-$(logname 2>/dev/null || echo ubuntu)}"

[ "$(id -u)" -eq 0 ] || { echo "Run with sudo"; exit 1; }

echo "==> Checking DNS for $DOMAIN points here"
MY_IP=$(curl -fsS https://api.ipify.org || true)
DNS_IP=$(getent ahostsv4 "$DOMAIN" | awk 'NR==1{print $1}' || true)
if [ -n "$MY_IP" ] && [ "$MY_IP" != "$DNS_IP" ]; then
  echo "    $DOMAIN resolves to '${DNS_IP:-nothing}', this VM is $MY_IP."
  echo "    Update the A record at your registrar, wait a few minutes, then re-run."
  exit 1
fi

echo "==> Packages and automatic security updates"
export DEBIAN_FRONTEND=noninteractive
apt-get update -q </dev/null
apt-get install -yq nginx certbot ufw unattended-upgrades curl </dev/null
dpkg-reconfigure -f noninteractive unattended-upgrades </dev/null

echo "==> Docker"
if ! command -v docker >/dev/null; then
  curl -fsSL https://get.docker.com | sh
fi
systemctl enable --now docker

echo "==> 1 GB swap (keeps a 1 GB VM from running out of memory during deploys)"
if ! swapon --show | grep -q /swapfile; then
  fallocate -l 1G /swapfile
  chmod 600 /swapfile
  mkswap /swapfile >/dev/null
  swapon /swapfile
  grep -q '^/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi

echo "==> Firewall: SSH, HTTP, HTTPS only"
ufw allow OpenSSH >/dev/null
ufw allow 'Nginx Full' >/dev/null
ufw --force enable >/dev/null

echo "==> TLS certificate for $DOMAIN"
if [ ! -d "/etc/letsencrypt/live/$DOMAIN" ]; then
  systemctl stop nginx
  certbot certonly --standalone --non-interactive --agree-tos -m "$EMAIL" \
    -d "$DOMAIN" -d "www.$DOMAIN" \
    --pre-hook "systemctl stop nginx" --post-hook "systemctl start nginx"
fi

echo "==> Nginx reverse proxy"
curl -fsSL "$REPO_RAW/docs/nginx.conf" | sed "s/trevorvaughan\.dev/$DOMAIN/g" \
  > /etc/nginx/sites-available/devops-monitor
ln -sf /etc/nginx/sites-available/devops-monitor /etc/nginx/sites-enabled/devops-monitor
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl restart nginx

echo
echo "Done. Server is ready for the pipeline."
echo "GitHub secrets to set: DEPLOY_HOST=$MY_IP  DEPLOY_USER=$DEPLOY_USER  DEPLOY_SSH_KEY=<private key>"
echo "Then re-run the latest CI/CD workflow (Actions tab) to deploy."
