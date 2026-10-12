#!/usr/bin/env bash
# Talaba Ovozi on Linux - manage the server (python -m app.server: web, bot, public address, nightly backup).
# It is the systemd service "talaba", set up by scripts/setup.sh, and starts whenever the computer does.
#
#   scripts/server.sh status            is it running? + the public address
#   scripts/server.sh logs [name]       follow a log: server (default) | web | bot | tunnel   (Ctrl+C to stop)
#   scripts/server.sh restart           after changing .env
#   scripts/server.sh stop | start
#   scripts/server.sh update            git pull, new packages, restart (the database is updated when it starts)
#   scripts/server.sh backup            a database copy now (one is made every night at 03:30 by itself)
#   scripts/server.sh backups           the copies (data/backups)
#   scripts/server.sh restore <file>    put a copy back - replaces ALL data
#   scripts/server.sh transfer          one file for moving to another computer
#   scripts/server.sh run [--no-bot]    in this terminal instead (development; Ctrl+C stops it)
#   scripts/server.sh install | uninstall   add / remove the service (setup.sh adds it)
#
# On Windows: scripts\server.bat, with the same commands.
set -euo pipefail
CALLER_DIR=$(pwd)
cd "$(dirname "$0")/.."
export XDG_RUNTIME_DIR=${XDG_RUNTIME_DIR:-/run/user/$(id -u)}   # systemctl --user also from ssh shells
ROOT=$(pwd)
UNIT=~/.config/systemd/user/talaba.service
PY=.venv/bin/python

installed() { [ -f "$UNIT" ]; }
need_service() { installed || { echo "❌ The service is not installed: scripts/setup.sh (or scripts/server.sh run)"; exit 1; }; }
show_status() {
  if installed; then
    echo "  service  talaba: $(systemctl --user is-active talaba 2>/dev/null || true)"
  else
    echo "  service  not installed (scripts/setup.sh)"
  fi
  $PY -m app.server status
}
wait_started() {   # until the server reports (at most a minute)
  echo "Starting..."
  for _ in $(seq 1 30); do
    sleep 2
    if [ -f data/runtime/server_status.json ]; then sleep 3; break; fi
  done
  show_status
}

case "${1:-status}" in
  status) show_status ;;
  start) need_service; systemctl --user start talaba; wait_started ;;
  stop) need_service; systemctl --user stop talaba; echo "⏹  Stopped. It starts again with the computer, or: scripts/server.sh start" ;;
  restart) need_service; systemctl --user restart talaba; wait_started ;;
  update)
    git pull --ff-only
    $PY -m pip install -q --disable-pip-version-check -r requirements.txt
    if installed; then systemctl --user restart talaba; wait_started; fi ;;
  logs) tail -n 60 -F "data/runtime/logs/${2:-server}.log" ;;
  backup) $PY -m app.backup now ;;
  backups) $PY -m app.backup list ;;
  transfer)
    if systemctl --user is-active --quiet talaba 2>/dev/null; then
      echo "⚠️  The server is still running: what happens after this moment won't be in the file."
      echo "   Moving for good? First: scripts/server.sh uninstall (two bots with one token fight)"
    fi
    $PY -m app.backup transfer ;;
  restore)
    [ -n "${2:-}" ] || { echo "Which copy?  scripts/server.sh restore data/backups/feedback-....sql.gz"; exit 1; }
    file=$(cd "$CALLER_DIR" && realpath -- "$2")
    if installed; then systemctl --user stop talaba; fi
    rc=0
    $PY -m app.backup restore "$file" || rc=$?
    if installed; then systemctl --user start talaba; wait_started; fi
    exit $rc ;;
  run)
    scripts/db.sh start
    exec $PY -m app.server "${@:2}" ;;
  install)
    mkdir -p "$(dirname "$UNIT")"
    cat > "$UNIT" <<UNIT
[Unit]
Description=Talaba Ovozi - web server, Telegram bot and public address (python -m app.server)

[Service]
WorkingDirectory=$ROOT
# The database container starts with Docker; this starts it if someone stopped it.
ExecStartPre=-$ROOT/scripts/db.sh start
ExecStart=$ROOT/.venv/bin/python -m app.server
Restart=always
RestartSec=5

[Install]
WantedBy=default.target
UNIT
    systemctl --user daemon-reload
    systemctl --user enable --quiet talaba
    systemctl --user restart talaba   # running already: picks up the new .env and code
    # Start at boot, even before anyone logs in (otherwise: when you log in).
    loginctl enable-linger "$USER" 2>/dev/null && echo "✅ Starts by itself when the computer is switched on" \
      || echo "ℹ️  Starts when you log in (to start at boot: sudo loginctl enable-linger $USER)"
    wait_started ;;
  uninstall)
    systemctl --user disable --now talaba 2>/dev/null || true
    rm -f "$UNIT"
    systemctl --user daemon-reload
    echo "✅ The service is removed (the database and the data stay). By hand: scripts/server.sh run" ;;
  *) sed -n '2,17p' "$0"; exit 1 ;;
esac
