#!/usr/bin/env bash
# Deploy the latest main to this server, without GitHub Actions.
#
# Same safety as a pipeline: run the test suite, build, start, health-check, and roll
# back to the previous version automatically if the new one doesn't come up.
# Also run every 2 minutes by scripts/autodeploy.sh when a new commit lands on main.
#
# Install once (on the server):
#   curl -fsSL https://raw.githubusercontent.com/TrevorvaughanDEV/devops-project/main/scripts/deploy.sh -o ~/deploy && chmod +x ~/deploy
# Then deploy any time with:
#   ./deploy            (latest main)
#   ./deploy some-branch
#
# Optional settings (e.g. ABUSEIPDB_KEY=...) go in ~/.whos-knocking.env, one per line.
# Server settings (e.g. HONEYPOT_PORT=22) go in ~/.whos-knocking.conf.
set -euo pipefail

# shellcheck source=/dev/null
[ -f "$HOME/.whos-knocking.conf" ] && . "$HOME/.whos-knocking.conf"

# One deploy at a time: a manual ./deploy and the auto-deploy timer wait for each other
# instead of building and testing side by side on a small VM.
exec 8>"$HOME/.whos-knocking-deploy.lock"
if ! flock -n 8; then
  echo "Another deploy is running; waiting for it to finish..."
  flock 8
fi

BRANCH="${1:-main}"
REPO=https://github.com/TrevorvaughanDEV/devops-project
SRC="$HOME/devops-project"
NAME=devops-monitor
VOLUME=devops-monitor-data
HONEYPOT_PORT="${HONEYPOT_PORT:-2222}"
ENV_FILE="$HOME/.whos-knocking.env"
DOMAIN="${DOMAIN:-trevorvaughan.dev}"

say() { printf '\n\033[1m==> %s\033[0m\n' "$*"; }

say "Fetching $BRANCH"
if [ -d "$SRC/.git" ]; then
  git -C "$SRC" fetch --depth 1 origin "$BRANCH"
  git -C "$SRC" checkout -q -B "$BRANCH" FETCH_HEAD
else
  rm -rf "$SRC"
  git clone -q --depth 1 -b "$BRANCH" "$REPO" "$SRC"
fi
SHA=$(git -C "$SRC" rev-parse --short HEAD)
echo "$(git -C "$SRC" log -1 --format='%h %s')"

say "Running the tests"
if ! sudo docker build -q --target test "$SRC" >/dev/null; then
  echo "Tests failed for $SHA; nothing was deployed. See: sudo docker build --target test $SRC"
  exit 2
fi
echo "All tests passed"

NEW_IMAGE="whos-knocking:$SHA"
say "Building $NEW_IMAGE"
sudo docker build -t "$NEW_IMAGE" "$SRC"

PREV_IMAGE=$(sudo docker inspect --format '{{.Config.Image}}' "$NAME" 2>/dev/null || true)

run_container() {
  local env_args=()
  [ -f "$ENV_FILE" ] && env_args=(--env-file "$ENV_FILE")
  sudo docker run -d --name "$NAME" --restart unless-stopped \
    -p 127.0.0.1:5000:5000 \
    -p "$HONEYPOT_PORT":2222 \
    -e PUBLIC_SENSOR_PORT="$HONEYPOT_PORT" \
    "${env_args[@]}" \
    --memory 400m \
    -v "$VOLUME":/app/data \
    "$1" >/dev/null
}

healthy() {
  for _ in $(seq 1 20); do
    curl -fsS http://127.0.0.1:5000/healthz >/dev/null 2>&1 && return 0
    sleep 3
  done
  return 1
}

# Refuse to take a port something else (like the real sshd) is listening on,
# before touching the running site.
if sudo ss -ltnpH "( sport = :$HONEYPOT_PORT )" | grep -v docker-proxy | grep -q .; then
  echo "Port $HONEYPOT_PORT is already used by another program:"
  sudo ss -ltnpH "( sport = :$HONEYPOT_PORT )"
  echo "Nothing was changed. Move that program first (see docs/deployment.md)."
  exit 3
fi

say "Starting the new version"
sudo docker run --rm -v "$VOLUME":/data alpine chown -R 1000:1000 /data
sudo docker rm -f "$NAME" >/dev/null 2>&1 || true
run_container "$NEW_IMAGE"

if ! healthy; then
  echo "New version failed its health check. Last log lines:"
  sudo docker logs --tail 30 "$NAME" || true
  sudo docker rm -f "$NAME" >/dev/null
  if [ -n "$PREV_IMAGE" ]; then
    say "Rolling back to $PREV_IMAGE"
    run_container "$PREV_IMAGE"
    healthy && echo "Rolled back; the site is running the previous version."
  fi
  exit 1
fi

# Keep Nginx in step with the repo's config
CONF=/etc/nginx/sites-available/devops-monitor
if ! sed "s/trevorvaughan\.dev/$DOMAIN/g" "$SRC/docs/nginx.conf" | sudo cmp -s - "$CONF"; then
  say "Updating Nginx config"
  sudo cp "$CONF" "$CONF.bak"
  sed "s/trevorvaughan\.dev/$DOMAIN/g" "$SRC/docs/nginx.conf" | sudo tee "$CONF" >/dev/null
  if sudo nginx -t 2>/dev/null; then
    sudo systemctl reload nginx
  else
    echo "New Nginx config failed its test; keeping the old one."
    sudo mv "$CONF.bak" "$CONF"
  fi
fi

git -C "$SRC" rev-parse HEAD > "$HOME/.whos-knocking-deployed"

say "Cleaning up old images (keeping the last 3)"
sudo docker images whos-knocking --format '{{.Tag}} {{.CreatedAt}}' \
  | sort -k2 -r | tail -n +4 | awk '{print "whos-knocking:" $1}' \
  | xargs -r sudo docker rmi >/dev/null 2>&1 || true
sudo docker builder prune -f --filter until=72h >/dev/null 2>&1 || true

say "Live: https://$DOMAIN is running $SHA"
curl -fsS http://127.0.0.1:5000/api/meta; echo
