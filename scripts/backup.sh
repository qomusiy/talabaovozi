#!/usr/bin/env bash
# Copies of the database (and uploaded pictures/videos), kept in data/backups - the newest 14 of each.
# Runs every night by itself (talaba-backup.timer, set up by scripts/server.sh install).
#
#   scripts/backup.sh                 # make a copy now
#   scripts/backup.sh list            # the copies
#   scripts/backup.sh restore <file>  # put a copy back (replaces ALL current data - asks first)
#   scripts/backup.sh transfer        # one file for moving to another computer (scripts/setup.sh <file> there)
#
# Keep a copy somewhere else too (a USB disk, Google Drive): a copy on the same disk doesn't survive the disk.
set -euo pipefail
cd "$(dirname "$0")/.."
export XDG_RUNTIME_DIR=${XDG_RUNTIME_DIR:-/run/user/$(id -u)}   # systemctl --user also from WSL / ssh shells
DIR=data/backups
KEEP=${BACKUP_KEEP:-14}
DB=feedback-db
mkdir -p "$DIR"

case "${1:-now}" in
  now)
    stamp=$(date +%F_%H%M)
    file="$DIR/feedback-$stamp.sql.gz"
    trap 'rm -f "$file.part"' EXIT
    docker exec "$DB" pg_dump -U feedback --clean --if-exists --no-owner feedback | gzip -9 > "$file.part"
    # A copy is kept only if it is complete (pg_dump writes this line last).
    if ! gunzip -c "$file.part" | tail -n 5 | grep -q "PostgreSQL database dump complete"; then
      echo "❌ The backup is incomplete - nothing was replaced"; exit 1
    fi
    mv "$file.part" "$file"
    if [ -d data/media ] && [ -n "$(ls -A data/media 2>/dev/null)" ]; then
      tar -czf "$DIR/media-$stamp.tar.gz" -C data media
    fi
    for kind in feedback media; do   # keep the newest $KEEP of each
      ls -1t "$DIR"/$kind-* 2>/dev/null | tail -n +$((KEEP + 1)) | xargs -r rm -f || true
    done
    echo "✅ $file ($(du -h "$file" | cut -f1))" ;;
  list)
    ls -lht "$DIR" ;;
  transfer)  # everything a new computer needs that is not on GitHub: .env (keys), the database, uploaded files
    if systemctl --user is-active --quiet talaba-bot talaba-web 2>/dev/null; then
      echo "⚠️  The bot and web are still running: what happens after this moment won't be in the file."
      echo "   Moving for good? Stop them first: scripts/server.sh uninstall"
    fi
    [ -f .env ] || { echo "❌ No .env here"; exit 1; }
    "$0" now
    stamp=$(date +%F_%H%M)
    out="$DIR/talaba-transfer-$stamp.tar.gz"
    files=(.env "$(ls -1t "$DIR"/feedback-*.sql.gz | head -1)")
    for d in data/media data/uploads data/runtime/chatfiles; do if [ -d "$d" ]; then files+=("$d"); fi; done
    tar -czf "$out" "${files[@]}"
    chmod 600 "$out"
    echo "✅ $out ($(du -h "$out" | cut -f1))"
    echo "   It holds the bot token, SECRET_KEY and all student data: copy it by USB stick (or scp) - never to GitHub."
    echo "   On the new computer: scripts/setup.sh <this file>" ;;
  restore)
    file=${2:?"usage: scripts/backup.sh restore data/backups/feedback-....sql.gz"}
    [ -f "$file" ] || { echo "❌ No such file: $file"; exit 1; }
    echo "⚠️  This replaces ALL current data (students, ratings, settings) with the copy $file."
    read -r -p "Type YES to continue: " answer
    [ "$answer" = "YES" ] || { echo "Cancelled."; exit 1; }
    "$0" now >/dev/null && echo "ℹ️  The current data was saved first (scripts/backup.sh list)."
    systemctl --user stop talaba-bot talaba-web 2>/dev/null || true
    gunzip -c "$file" | docker exec -i "$DB" psql -q -v ON_ERROR_STOP=1 -U feedback -d feedback
    systemctl --user start talaba-web talaba-bot 2>/dev/null || true
    echo "✅ Restored from $file" ;;
  *) sed -n '2,11p' "$0"; exit 1 ;;
esac
