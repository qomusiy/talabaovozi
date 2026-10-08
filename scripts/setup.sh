#!/usr/bin/env bash
# Make this computer the Talaba Ovozi server (Ubuntu 24.04 / Debian), right after `git clone`.
# On Windows use scripts\setup.bat instead.
#
#   scripts/setup.sh ~/talaba-transfer-….tar.gz   # moving from another computer (made there: scripts/backup.sh transfer)
#   scripts/setup.sh                              # a fresh start, without data
#
# It installs what is missing (Docker, the Python packages, cloudflared or Tailscale), restores the data, and
# installs the services (scripts/server.sh install): from then on the database, the web server, the bot and the
# public address start by themselves whenever the computer is switched on - nobody has to log in.
# Safe to run again (it skips what is done) - e.g. after a restart it asked for, or after changing TUNNEL in .env.
set -euo pipefail
cd "$(dirname "$0")/.."
BUNDLE=${1:-}
if [ -n "$BUNDLE" ]; then
  [ -f "$BUNDLE" ] || { echo "❌ No such file: $BUNDLE"; exit 1; }
  BUNDLE=$(realpath "$BUNDLE")
fi
DB=feedback-db
IS_WSL=false
grep -qi microsoft /proc/sys/kernel/osrelease 2>/dev/null && IS_WSL=true
env_get() { sed -n "s/^$1=//p" .env 2>/dev/null | tail -1 | tr -d "\"'\r"; }
env_set() { if grep -q "^$1=" .env; then sed -i "s|^$1=.*|$1=$2|" .env; else echo "$1=$2" >> .env; fi; }
step() { echo; echo "── $*"; }

step "1/5 System packages"
if [ "$(ps -p 1 -o comm=)" != systemd ]; then   # it starts everything at boot
  echo "❌ systemd is not running."
  $IS_WSL && echo "   WSL: add [boot] systemd=true to /etc/wsl.conf, then in PowerShell: wsl --shutdown"
  exit 1
fi
missing=()
command -v curl >/dev/null || missing+=(curl)
command -v docker >/dev/null || missing+=(docker.io)
python3 -c 'import ensurepip' 2>/dev/null || missing+=(python3-venv)
if [ ${#missing[@]} -gt 0 ]; then
  echo "Installing ${missing[*]} (asks for your password)"
  sudo apt-get update -q && sudo apt-get install -y "${missing[@]}"
fi
python3 -c 'import sys; sys.exit(sys.version_info < (3, 12))' \
  || { echo "❌ Python 3.12 or newer is needed (Ubuntu 24.04 has it); this computer has $(python3 -V)"; exit 1; }
systemctl is-enabled --quiet docker 2>/dev/null || sudo systemctl enable --now docker   # the database runs in Docker
if ! docker info >/dev/null 2>&1; then   # exit code 3 = "restart, then run me again"
  id -nG | grep -qw docker || sudo usermod -aG docker "$USER"
  echo
  if $IS_WSL; then
    echo "ℹ️  Docker works without sudo only after Ubuntu restarts. In PowerShell: wsl --terminate ${WSL_DISTRO_NAME:-Ubuntu-24.04}"
  else
    echo "ℹ️  Docker works without sudo only after a restart. Restart the computer (sudo reboot)."
  fi
  echo "   Then run the same command again:  scripts/setup.sh ${BUNDLE}"
  exit 3
fi
if docker info --format '{{.OperatingSystem}}' 2>/dev/null | grep -q "Docker Desktop"; then
  echo "❌ This is Docker Desktop: it runs only while someone is signed in to Windows, so the database wouldn't start"
  echo "   at boot. Docker Desktop › Settings › Resources › WSL integration: switch it off for this Ubuntu, run this again."
  exit 1
fi
# A server must not fall asleep (Ubuntu suspends an idle computer by default). Undo: sudo systemctl unmask …
# (In WSL Windows decides that.)
if ! $IS_WSL && [ "$(systemctl is-enabled suspend.target 2>/dev/null)" != masked ]; then
  echo "Switching off sleep / suspend - this computer is a server now"
  sudo systemctl mask sleep.target suspend.target hibernate.target hybrid-sleep.target >/dev/null
fi
echo "✅ Docker, Python $(python3 -c 'import platform; print(platform.python_version())')"

step "2/5 Python packages"
[ -x .venv/bin/python ] || python3 -m venv .venv
.venv/bin/pip install -q --upgrade pip
.venv/bin/pip install -q -r requirements.txt
echo "✅ .venv"

step "3/5 Settings (.env) and data"
scripts/db.sh start
db_empty() {
  local r
  r=$(docker exec "$DB" psql -U feedback -d feedback -Atc "select to_regclass('public.students') is null") \
    || { echo "❌ The database doesn't answer (scripts/db.sh status)"; exit 1; }
  [ "$r" = t ]
}
if [ -n "$BUNDLE" ]; then
  tmp=$(mktemp -d)
  trap 'rm -rf "$tmp"' EXIT
  tar -xzf "$BUNDLE" -C "$tmp"
  if db_empty; then
    # The database and its .env belong together: passports are hashed with SECRET_KEY.
    if [ -f .env ] && ! cmp -s .env "$tmp/.env"; then
      cp .env ".env.old-$(date +%F_%H%M)" && echo "ℹ️  The .env that was here is kept as .env.old-…"
    fi
    cp "$tmp/.env" .env
    dump=$(ls -1 "$tmp"/data/backups/feedback-*.sql.gz | head -1)
    mkdir -p data/backups && cp "$dump" data/backups/
    gunzip -c "$dump" | docker exec -i -e PGOPTIONS=--client-min-messages=warning "$DB" \
      psql -q -v ON_ERROR_STOP=1 -U feedback -d feedback >/dev/null
    echo "✅ Database restored from $(basename "$dump")"
  else
    echo "ℹ️  The database already has data - it was not replaced (to replace it: scripts/backup.sh restore <file>)"
    [ -f .env ] || cp "$tmp/.env" .env
  fi
  for d in media uploads runtime/chatfiles; do
    if [ -d "$tmp/data/$d" ]; then mkdir -p "data/$d" && cp -r "$tmp/data/$d/." "data/$d/"; fi
  done
  echo "✅ Uploaded files copied"
fi
if [ ! -f .env ]; then
  cp .env.example .env
  env_set SECRET_KEY "$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
  read -r -p "Telegram bot token (from @BotFather): " token
  env_set BOT_TOKEN "$token"
  echo "✅ .env created - keep a copy of it somewhere safe (without its SECRET_KEY nobody can log in)"
fi
chmod 600 .env
if [ "$(env_get DEV_MODE)" = true ]; then
  env_set DEV_MODE false && echo "ℹ️  DEV_MODE switched off in .env (never on a server)"
fi
.venv/bin/alembic upgrade head >/dev/null
echo "✅ .env, database up to date"

if [ -z "$(env_get TUNNEL)" ]; then
  echo
  echo "How do students reach the survey? (README › Fixed address; later: change TUNNEL in .env, run this again)"
  echo "  1) tailscale  - free, the address never changes (recommended)"
  echo "  2) quick      - free, but a new address after every restart"
  echo "  3) cloudflare - your own domain (needs a Cloudflare tunnel token)"
  read -r -p "1, 2 or 3 [1]: " choice
  case "${choice:-1}" in 2) env_set TUNNEL quick ;; 3) env_set TUNNEL cloudflare ;; *) env_set TUNNEL tailscale ;; esac
fi
MODE=$(env_get TUNNEL)
if [ "$MODE" = cloudflare ]; then
  if [ -z "$(env_get CLOUDFLARE_TUNNEL_TOKEN)" ]; then
    read -r -p "Cloudflare tunnel token (the long text after --token): " v && env_set CLOUDFLARE_TUNNEL_TOKEN "$v"
  fi
  if [ -z "$(env_get WEBAPP_URL)" ]; then
    read -r -p "Its address, e.g. https://ovoz.example.uz: " v && env_set WEBAPP_URL "${v%/}"
  fi
fi
step "4/5 Public address (TUNNEL=$MODE in .env)"
case "$MODE" in
  quick|cloudflare)
    if [ ! -x tools/cloudflared ]; then
      arch=$(dpkg --print-architecture)
      case "$arch" in armhf) arch=arm ;; i386) arch=386 ;; esac
      mkdir -p tools
      curl -fsSL -o tools/cloudflared.part \
        "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-$arch"
      chmod +x tools/cloudflared.part && mv tools/cloudflared.part tools/cloudflared
    fi
    echo "✅ $(tools/cloudflared --version | head -1)"
    if [ "$MODE" = quick ]; then
      echo "ℹ️  quick: the address changes after every restart. A fixed one: README › Fixed address"
    elif [ -z "$(env_get CLOUDFLARE_TUNNEL_TOKEN)" ] || [ -z "$(env_get WEBAPP_URL)" ]; then
      echo "❌ TUNNEL=cloudflare needs CLOUDFLARE_TUNNEL_TOKEN and WEBAPP_URL in .env (README › Fixed address)"; exit 1
    fi ;;
  tailscale)
    command -v tailscale >/dev/null || curl -fsSL https://tailscale.com/install.sh | sh
    if ! tailscale status >/dev/null 2>&1; then
      echo "Log in to Tailscale: open the link below and sign in (a free account - Google, GitHub or Microsoft)"
      sudo tailscale up --hostname=talaba-ovozi --accept-dns=false   # a server needs no tailnet names (WSL: keeps its DNS)
    fi
    sudo tailscale set --operator="$USER"   # the talaba-tunnel service may then manage Funnel without sudo
    echo "Turning on Funnel. If a link appears, open it, allow Funnel, and wait here."
    tailscale funnel --bg 8000
    echo "✅ Tailscale Funnel" ;;
  *)
    echo "❌ TUNNEL=$MODE in .env - use quick, tailscale or cloudflare"; exit 1 ;;
esac

step "5/5 Services (they start by themselves when the computer is switched on)"
# Start at boot, before anyone logs in.
[ "$(loginctl show-user "$USER" -p Linger --value 2>/dev/null)" = yes ] || sudo loginctl enable-linger "$USER"
scripts/server.sh install

if [ "$(docker exec "$DB" psql -U feedback -d feedback -Atc 'select count(*) from admins')" = 0 ]; then
  echo
  echo "👤 No dashboard account yet:  .venv/bin/python -m app.cli admin-create admin"
fi
