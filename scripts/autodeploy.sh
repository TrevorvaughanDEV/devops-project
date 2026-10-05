#!/usr/bin/env bash
# Pull-based continuous deployment (the GitOps model used by Argo CD and Flux).
#
# Run every 2 minutes by a systemd timer. If main has a commit that isn't live yet,
# it runs ~/deploy, which tests, builds, health-checks and rolls back on failure.
# The server only ever makes outbound requests to GitHub: nothing new is exposed.
#
# Logs: journalctl -u whos-knocking-autodeploy -n 50
set -euo pipefail

REPO=https://github.com/TrevorvaughanDEV/devops-project
DEPLOYED_FILE="$HOME/.whos-knocking-deployed"
FAILED_FILE="$HOME/.whos-knocking-failed"

exec 9>"$HOME/.whos-knocking-autodeploy.lock"
flock -n 9 || { echo "A deploy is already running"; exit 0; }

LATEST=$(git ls-remote "$REPO" refs/heads/main | cut -f1)
[ -n "$LATEST" ] || { echo "Couldn't reach GitHub; will retry"; exit 0; }

DEPLOYED=$(cat "$DEPLOYED_FILE" 2>/dev/null || true)
[ "$LATEST" = "$DEPLOYED" ] && exit 0

# Don't retry a commit that already failed; the next push gets a fresh attempt.
if [ "$LATEST" = "$(cat "$FAILED_FILE" 2>/dev/null || true)" ]; then
  exit 0
fi

echo "New commit on main: ${LATEST:0:7} (live: ${DEPLOYED:0:7})"
if "$HOME/deploy" main; then
  rm -f "$FAILED_FILE"
  echo "Deployed ${LATEST:0:7}"
else
  echo "$LATEST" > "$FAILED_FILE"
  echo "Deploy of ${LATEST:0:7} failed; the previous version is still live"
  exit 1
fi
