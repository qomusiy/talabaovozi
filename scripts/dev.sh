#!/usr/bin/env bash
# Start everything for local development:
#   database  ->  web server (survey + dashboard)  ->  public HTTPS tunnel  ->  Telegram bot
#
#   scripts/dev.sh               # start; Ctrl+C stops the bot and the web server
#   scripts/dev.sh --no-tunnel   # local only (no Mini App)
#   scripts/dev.sh stop          # stop everything, the tunnel too
#
# The tunnel keeps running after Ctrl+C, so its address - the one the Telegram buttons open - stays the
# same the next time. It gets a new address only after `scripts/dev.sh stop`, a reboot, or if it dies;
# the bot then moves the menu button and the survey buttons it sent to the new address by itself.
set -uo pipefail
cd "$(dirname "$0")/.."
export XDG_RUNTIME_DIR=${XDG_RUNTIME_DIR:-/run/user/$(id -u)}   # systemctl --user also from WSL / ssh shells
# Server mode (scripts/server.sh) runs the same programs as services; two bots would fight over Telegram updates.
if systemctl --user is-active --quiet talaba-bot talaba-web 2>/dev/null; then
  echo "ℹ️  Server mode is running (scripts/server.sh status). To develop with dev.sh: scripts/server.sh uninstall"
  [ "${1:-}" = "stop" ] && exit 0 || exit 1
fi
RUNTIME=data/runtime
URL_FILE=$RUNTIME/webapp_url
TUNNEL_PID_FILE=$RUNTIME/tunnel.pid
TUNNEL_LOG=$RUNTIME/tunnel.log
DEV_PID_FILE=$RUNTIME/dev.pid
mkdir -p "$RUNTIME"

alive() {  # alive <pid-file> <word in its command line>  ->  prints the pid if that process is running
  local pid
  pid=$(cat "$1" 2>/dev/null) && [ -n "$pid" ] && grep -qa -- "$2" "/proc/$pid/cmdline" 2>/dev/null && echo "$pid"
}

stop_apps() {
  # An older dev.sh first (its Ctrl+C handler stops its own web server), then any stray copies:
  # two bots with the same token fight over Telegram updates.
  local pid
  if pid=$(alive "$DEV_PID_FILE" dev.sh) && [ "$pid" != $$ ]; then
    echo "⏹  Stopping an older scripts/dev.sh (pid $pid)"
    kill -TERM "$pid" 2>/dev/null
  fi
  for name in app.bot app.web; do
    for pid in $(pgrep -f -- "-m $name\$" || true); do
      echo "⏹  Stopping an older $name (pid $pid)"
      kill -INT "$pid" 2>/dev/null; sleep 1; kill "$pid" 2>/dev/null
    done
  done
}

stop_tunnel() {
  local pid
  pid=$(alive "$TUNNEL_PID_FILE" cloudflared) && kill "$pid" && echo "⏹  Stopped the tunnel"
  rm -f "$URL_FILE" "$TUNNEL_PID_FILE"
}

tunnel_ready() {  # is cloudflared connected to Cloudflare? (its local /ready endpoint; no DNS involved)
  local metrics
  metrics=$(grep -oE 'metrics server on [0-9.]+:[0-9]+' "$TUNNEL_LOG" 2>/dev/null | head -1 | awk '{print $4}')
  [ -n "$metrics" ] && curl -sf -o /dev/null --max-time 3 "http://$metrics/ready"
}

start_tunnel() {
  local url pid
  # The old address stays in $URL_FILE until the new one works, so the bot never flips to "no survey".
  # setsid: its own session, so Ctrl+C here or closing the terminal doesn't kill it.
  # http2 is steadier than the default QUIC on many networks.
  setsid tools/cloudflared tunnel --no-autoupdate --protocol http2 --url http://127.0.0.1:8000 \
    > "$TUNNEL_LOG" 2>&1 < /dev/null &
  pid=$!
  echo "$pid" > "$TUNNEL_PID_FILE"
  for _ in $(seq 1 40); do
    url=$(grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' "$TUNNEL_LOG" | head -1)
    [ -n "$url" ] && break
    kill -0 "$pid" 2>/dev/null || break
    sleep 1
  done
  [ -z "$url" ] && { kill "$pid" 2>/dev/null; return 1; }
  for _ in $(seq 1 30); do tunnel_ready && break; sleep 1; done
  echo "$url" > "$URL_FILE"
  echo "✅ Survey Mini App: $url/survey   (new address — the bot updates the Telegram buttons)"
}

ensure_tunnel() {
  if alive "$TUNNEL_PID_FILE" cloudflared > /dev/null && [ -s "$URL_FILE" ]; then
    echo "✅ Survey Mini App: $(cat "$URL_FILE")/survey   (same address as before)"
  else
    alive "$TUNNEL_PID_FILE" cloudflared > /dev/null && stop_tunnel > /dev/null
    start_tunnel
  fi
}

if [ "${1:-}" = "stop" ]; then
  stop_apps
  stop_tunnel
  exit 0
fi

stop_apps
echo $$ > "$DEV_PID_FILE"
PIDS=()
cleanup() {
  for p in "${PIDS[@]}"; do kill "$p" 2>/dev/null; done
  [ "$(cat "$DEV_PID_FILE" 2>/dev/null)" = $$ ] && rm -f "$DEV_PID_FILE"
}
trap 'cleanup; echo; echo "⏸  Bot and web server stopped. The tunnel stays open (same address next time) — scripts/dev.sh stop closes it."; exit 0' INT TERM HUP
trap cleanup EXIT

scripts/db.sh start || exit 1
.venv/bin/alembic upgrade head 2>/dev/null || { echo "❌ Database migration failed"; exit 1; }

.venv/bin/python -m app.web &
PIDS+=($!)
for _ in $(seq 1 30); do curl -sf -o /dev/null http://127.0.0.1:8000/survey && break; sleep 0.5; done

if [ "${1:-}" = "--no-tunnel" ]; then
  stop_tunnel > /dev/null
elif [ ! -x tools/cloudflared ]; then
  echo "⚠️  tools/cloudflared is missing — the survey can't open in Telegram."
else
  echo "🌍 Public tunnel…"
  if ensure_tunnel; then
    # Watchdog: if the tunnel dies, open a new one (the bot moves the Telegram buttons to it).
    ( while sleep 15 && kill -0 $$ 2>/dev/null; do
        alive "$TUNNEL_PID_FILE" cloudflared > /dev/null || { echo "🔁 The tunnel stopped — reopening…"; start_tunnel; }
      done ) &
    PIDS+=($!)
  else
    echo "⚠️  The tunnel did not start — the survey can't open in Telegram. See $TUNNEL_LOG"
  fi
fi

echo "📊 Dashboard: http://127.0.0.1:8000/admin"
if ! .venv/bin/python -m app.bot; then
  echo
  echo "⚠️  The bot stopped (see the message above). The web server is still running — Ctrl+C to stop."
  wait "${PIDS[0]}"
fi
