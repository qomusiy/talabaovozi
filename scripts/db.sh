#!/usr/bin/env bash
# The database on Linux: PostgreSQL 16 in Docker on 127.0.0.1:5433 - it starts with Docker, so with the computer.
# Usage: scripts/db.sh start | stop | status | psql | reset
set -euo pipefail
NAME=feedback-db
case "${1:-start}" in
  start)
    if docker ps -a --format '{{.Names}}' | grep -qx "$NAME"; then
      docker start "$NAME" >/dev/null
    else
      docker run -d --name "$NAME" --restart unless-stopped \
        -e POSTGRES_DB=feedback -e POSTGRES_USER=feedback -e POSTGRES_PASSWORD=feedback_dev_pw \
        -p 127.0.0.1:5433:5432 -v feedback_pgdata:/var/lib/postgresql/data \
        postgres:16-alpine >/dev/null
    fi
    # Over TCP: a brand-new container first runs a temporary server (socket only) to create the database.
    for _ in $(seq 1 60); do
      docker exec "$NAME" pg_isready -h 127.0.0.1 -U feedback -d feedback >/dev/null 2>&1 && { echo "✅ Postgres is running on 127.0.0.1:5433"; exit 0; }
      sleep 1
    done
    echo "❌ Postgres did not become ready"; exit 1 ;;
  stop)   docker stop "$NAME" >/dev/null && echo "Stopped." ;;
  status) docker ps --filter "name=$NAME" --format '{{.Names}}: {{.Status}}' ;;
  psql)   docker exec -it "$NAME" psql -U feedback -d feedback ;;
  reset)  # DANGER: deletes all data in the dev database
    docker rm -f "$NAME" >/dev/null 2>&1 || true
    docker volume rm feedback_pgdata >/dev/null 2>&1 || true
    echo "Database deleted. Run: scripts/db.sh start" ;;
  *) echo "Usage: $0 start|stop|status|psql|reset"; exit 1 ;;
esac
