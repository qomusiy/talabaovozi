#!/usr/bin/env bash
# Run Talaba Ovozi on this computer as a server: web (survey + dashboard), Telegram bot and the public tunnel
# as background services (systemd --user). They restart if they crash and start again after a reboot.
#
#   scripts/server.sh install     # set up and start (once - and again after changing .env, e.g. TUNNEL)
#                                 # (a new computer: scripts/setup.sh does everything, this included)
#   scripts/server.sh status      # is everything running? + the public address
#   scripts/server.sh url         # the public address
#   scripts/server.sh restart     # after changing code: restart web + bot (the public address stays the same)
#   scripts/server.sh restart tunnel   # reconnect (TUNNEL=quick: a new address - the bot updates Telegram itself)
#   scripts/server.sh logs bot    # follow a service's log (web | bot | tunnel)
#   scripts/server.sh stop | start
#   scripts/server.sh uninstall   # back to development mode (scripts/dev.sh)
#   (backups: scripts/backup.sh - every night at 03:30 by itself)
set -euo pipefail
cd "$(dirname "$0")/.."
export XDG_RUNTIME_DIR=${XDG_RUNTIME_DIR:-/run/user/$(id -u)}   # systemctl --user also from WSL / ssh shells
ROOT=$(pwd)
UNITS=~/.config/systemd/user
SERVICES=(talaba-web talaba-bot talaba-tunnel)
URL_FILE=data/runtime/webapp_url
env_get() { sed -n "s/^$1=//p" .env 2>/dev/null | tail -1 | tr -d "\"'\r"; }

unit() {  # unit <name> <description> <exec> [after]
  cat > "$UNITS/$1.service" <<UNIT
[Unit]
Description=Talaba Ovozi - $2
After=network-online.target ${4:-}
Wants=network-online.target

[Service]
WorkingDirectory=$ROOT
Environment=PYTHONUNBUFFERED=1
ExecStart=$3
Restart=always
RestartSec=5

[Install]
WantedBy=default.target
UNIT
}

backup_timer() {  # a copy of the database every night (scripts/backup.sh); catches up after the computer was off
  cat > "$UNITS/talaba-backup.service" <<UNIT
[Unit]
Description=Talaba Ovozi - database backup
[Service]
Type=oneshot
WorkingDirectory=$ROOT
ExecStart=$ROOT/scripts/backup.sh
UNIT
  cat > "$UNITS/talaba-backup.timer" <<UNIT
[Unit]
Description=Talaba Ovozi - nightly database backup
[Timer]
OnCalendar=*-*-* 03:30
Persistent=true
[Install]
WantedBy=timers.target
UNIT
}

show_url() {
  local url
  url=$(cat "$URL_FILE" 2>/dev/null || true)
  echo "📊 Dashboard: http://127.0.0.1:8000/admin   (on this computer; online too if switched on in the dashboard: Telegram bot page)"
  if [ -n "$url" ]; then
    echo "📝 Survey:    $url/survey   (students open it from the bot)"
    echo "🌐 Online:    $url/admin    (only when \"Admin sayti internetda\" is on)"
  else
    echo "⏳ No public address yet (the tunnel is starting) - try: scripts/server.sh url"
  fi
}

names() {  # "web bot" -> talaba-web talaba-bot; nothing -> all three
  if [ $# -eq 0 ]; then echo "${SERVICES[@]}"; else for n in "$@"; do echo -n "talaba-$n "; done; fi
}

case "${1:-status}" in
  install)
    if [ "$(env_get TUNNEL)" = tailscale ]; then
      command -v tailscale >/dev/null || { echo "❌ Tailscale is not installed (scripts/setup.sh installs it)"; exit 1; }
    else
      [ -x tools/cloudflared ] || { echo "❌ tools/cloudflared is missing (scripts/setup.sh downloads it)"; exit 1; }
    fi
    scripts/dev.sh stop >/dev/null 2>&1 || true   # development copies must not run next to the services
    mkdir -p "$UNITS"
    unit talaba-web "web server (survey + dashboard)" \
      "/bin/bash -c 'scripts/db.sh start && .venv/bin/alembic upgrade head && exec .venv/bin/python -m app.web'"
    unit talaba-bot "Telegram bot" "$ROOT/.venv/bin/python -m app.bot" "talaba-web.service"
    unit talaba-tunnel "public HTTPS tunnel" "$ROOT/scripts/tunnel.sh"
    backup_timer
    systemctl --user daemon-reload
    systemctl --user enable "${SERVICES[@]}" talaba-backup.timer
    systemctl --user restart "${SERVICES[@]}" talaba-backup.timer   # running already: pick up the new .env / units
    # Start at boot, even before anyone logs in (otherwise: when you log in).
    loginctl enable-linger "$USER" 2>/dev/null && echo "✅ Starts automatically when the computer boots" \
      || echo "ℹ️  Starts when you log in (to start at boot run: sudo loginctl enable-linger $USER)"
    echo "✅ Installed. Waiting for the public address…"
    for _ in $(seq 1 30); do [ -s "$URL_FILE" ] && break; sleep 1; done
    show_url ;;
  uninstall)
    systemctl --user disable --now "${SERVICES[@]}" talaba-backup.timer 2>/dev/null || true
    for s in "${SERVICES[@]}" talaba-backup; do rm -f "$UNITS/$s.service"; done
    rm -f "$UNITS/talaba-backup.timer"
    systemctl --user daemon-reload
    rm -f "$URL_FILE"
    echo "✅ Services removed. For development use scripts/dev.sh" ;;
  start|stop)
    shift_args=("${@:2}")
    systemctl --user "$1" $(names "${shift_args[@]}")
    echo "✅ $1: $(names "${shift_args[@]}")" ;;
  restart)
    if [ $# -gt 1 ]; then systemctl --user restart $(names "${@:2}"); else systemctl --user restart talaba-web talaba-bot; fi
    echo "✅ Restarted"; sleep 2; show_url ;;
  status)
    for s in "${SERVICES[@]}"; do
      state=$(systemctl --user is-active "$s" 2>/dev/null || true)
      printf "  %-15s %s\n" "$s" "$([ "$state" = active ] && echo "✅ running" || echo "❌ ${state:-not installed}")"
    done
    printf "  %-15s %s\n" "backups" "$(ls -1t data/backups/feedback-*.sql.gz 2>/dev/null | head -1 || echo none)"
    show_url ;;
  backup-timer)  # add the nightly backup to an existing installation
    backup_timer; systemctl --user daemon-reload; systemctl --user enable --now talaba-backup.timer
    echo "✅ Nightly backup at 03:30 (scripts/backup.sh list)" ;;
  url) show_url ;;
  logs) journalctl --user -u "talaba-${2:-web}" -n 80 -f ;;
  *) sed -n '2,14p' "$0"; exit 1 ;;
esac
