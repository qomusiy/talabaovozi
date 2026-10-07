#!/usr/bin/env bash
# The public HTTPS address of the survey Mini App (and the dashboard, if allowed online).
# Run by the talaba-tunnel service (scripts/server.sh). Writes the address to data/runtime/webapp_url, where the bot
# (menu button, survey buttons) and the dashboard read it. TUNNEL in .env says how the address is made:
#
#   quick       free Cloudflare quick tunnel, https://….trycloudflare.com - a NEW address after every restart
#   tailscale   free Tailscale Funnel, https://talaba-ovozi.<tailnet>.ts.net - the same address forever
#               (set up once by scripts/setup.sh: Tailscale installed, logged in, Funnel allowed)
#   cloudflare  a Cloudflare named tunnel on your own domain - the same address forever
#               (CLOUDFLARE_TUNNEL_TOKEN and WEBAPP_URL=https://your.domain in .env - README › Fixed address)
#
# Every mode is watched: when the public address stops answering for ~4 minutes (or Cloudflare deletes a quick
# tunnel), this script stops and systemd starts it again. A quick tunnel then gets a new address (the bot moves its
# buttons there by itself); the fixed modes reconnect to the same one.
set -uo pipefail
cd "$(dirname "$0")/.."
mkdir -p data/runtime
URL_FILE=data/runtime/webapp_url
LOG=data/runtime/tunnel.log
STATUS=data/runtime/tunnel_status      # read by the dashboard (Telegram bot page): state|failed checks|unix time
RESTART=data/runtime/tunnel_restart    # created by the dashboard's "new address" button
CHECK_EVERY=60   # seconds between checks of the public address
MAX_FAILS=4      # failed checks in a row before starting the tunnel again
PORT=8000

env_get() { sed -n "s/^$1=//p" .env 2>/dev/null | tail -1 | tr -d "\"'\r"; }
MODE=$(env_get TUNNEL)
MODE=${MODE:-quick}

: > "$LOG"
rm -f "$RESTART"
status() { echo "$1|${2:-0}|$(date +%s)" > "$STATUS"; }
publish() {
  echo "$1" > "$URL_FILE.tmp" && mv "$URL_FILE.tmp" "$URL_FILE"
  echo "✅ Public address: $1  (survey: /survey)"
}
give_up() { echo "❌ $1"; status down "$MAX_FAILS"; sleep 60; exit 1; }   # systemd tries again
status starting

url=""
case "$MODE" in
  quick)
    tools/cloudflared tunnel --no-autoupdate --protocol http2 --url "http://127.0.0.1:$PORT" > >(tee -a "$LOG") 2>&1 &
    PID=$! ;;
  cloudflare)
    url=$(env_get WEBAPP_URL)
    url=${url%/}
    token=$(env_get CLOUDFLARE_TUNNEL_TOKEN)
    [ -n "$url" ] && [ -n "$token" ] || give_up "TUNNEL=cloudflare needs CLOUDFLARE_TUNNEL_TOKEN and WEBAPP_URL in .env"
    # The token goes in the environment, not the command line (where every user of the computer could read it).
    TUNNEL_TOKEN=$token tools/cloudflared tunnel --no-autoupdate --protocol http2 run > >(tee -a "$LOG") 2>&1 &
    PID=$!
    publish "$url" ;;
  tailscale)
    # tailscaled (a system service) keeps Funnel on by itself; turning it on again is harmless and repairs a reset.
    timeout 30 tailscale funnel --bg "$PORT" > >(tee -a "$LOG") 2>&1 \
      || echo "⚠️  'tailscale funnel --bg $PORT' failed - run scripts/setup.sh again if the address doesn't work"
    name=$(tailscale status --json 2>/dev/null \
      | python3 -c 'import json, sys; print(json.load(sys.stdin)["Self"]["DNSName"].rstrip("."))' 2>/dev/null)
    [ -n "$name" ] || give_up "Tailscale is not running or not logged in (sudo tailscale up)"
    url="https://$name"
    publish "$url"
    sleep infinity &   # nothing of our own to run: the loop below only watches the address
    PID=$! ;;
  *)
    give_up "Unknown TUNNEL=$MODE in .env (quick | tailscale | cloudflare)" ;;
esac
trap 'kill "$PID" 2>/dev/null' EXIT INT TERM

fails=0
started=$(date +%s)
last_check=$started
while kill -0 "$PID" 2>/dev/null; do
  sleep 5
  if [ -f "$RESTART" ]; then
    rm -f "$RESTART"
    echo "🔁 New address requested from the dashboard"
    status starting
    exit 1
  fi
  if [ -z "$url" ]; then   # quick: wait for Cloudflare to hand out the address
    url=$(grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' "$LOG" | head -1)
    if [ -n "$url" ]; then
      publish "$url"
    elif [ $(( $(date +%s) - started )) -gt 90 ]; then
      give_up "No public address after 90 s (no internet, or Cloudflare refused) - trying again in a minute"
    fi
    continue
  fi
  if [ "$MODE" = quick ] && grep -q "Tunnel not found" "$LOG"; then
    echo "❌ Cloudflare deleted this quick tunnel - starting a new one (new address)"
    status down $MAX_FAILS
    exit 1
  fi
  now=$(date +%s)
  if [ $(( now - last_check )) -ge $CHECK_EVERY ] && [ $(( now - started )) -ge 60 ]; then
    last_check=$now
    code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 20 "$url/healthz" || true)
    if [ "$code" = "200" ]; then
      fails=0
      status ok
    else
      fails=$(( fails + 1 ))
      status down $fails
      echo "⚠️  Public address not answering ($code), check $fails/$MAX_FAILS"
      if [ $fails -ge $MAX_FAILS ]; then
        [ "$MODE" = quick ] && echo "❌ The public address is dead - starting a new tunnel (new address)" \
          || echo "❌ The public address is not answering - reconnecting (same address)"
        exit 1
      fi
    fi
  fi
done
echo "❌ The tunnel stopped - starting again"
exit 1
