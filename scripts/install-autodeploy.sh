#!/usr/bin/env bash
# One-time setup for pull-based auto-deploy. Run on the server as the admin user:
#   curl -fsSL https://raw.githubusercontent.com/TrevorvaughanDEV/devops-project/main/scripts/install-autodeploy.sh | bash
set -euo pipefail

RAW=https://raw.githubusercontent.com/TrevorvaughanDEV/devops-project/main/scripts
USER_NAME=$(id -un)

curl -fsSL "$RAW/deploy.sh" -o "$HOME/deploy"
curl -fsSL "$RAW/autodeploy.sh" -o "$HOME/autodeploy"
chmod +x "$HOME/deploy" "$HOME/autodeploy"

sudo tee /etc/systemd/system/whos-knocking-autodeploy.service >/dev/null <<UNIT
[Unit]
Description=Deploy new commits on main of Who's Knocking
After=network-online.target docker.service
Wants=network-online.target

[Service]
Type=oneshot
User=$USER_NAME
ExecStart=$HOME/autodeploy
TimeoutStartSec=30min
UNIT

sudo tee /etc/systemd/system/whos-knocking-autodeploy.timer >/dev/null <<UNIT
[Unit]
Description=Check for new commits on main every 2 minutes

[Timer]
OnBootSec=2min
OnUnitInactiveSec=2min
RandomizedDelaySec=15s

[Install]
WantedBy=timers.target
UNIT

sudo systemctl daemon-reload
sudo systemctl enable --now whos-knocking-autodeploy.timer

echo
echo "Auto-deploy is on. The server checks main every 2 minutes."
echo "  Status:   systemctl list-timers whos-knocking-autodeploy"
echo "  Logs:     journalctl -u whos-knocking-autodeploy -n 50"
echo "  Deploy now: ~/deploy"
