#!/usr/bin/env sh
set -eu

if [ $# -lt 1 ]; then
  echo "usage: ./scripts/restore_postgres.sh <backup.sql>"
  exit 1
fi

DB_USER="${ABS_DB_USER:-abs_user}"
DB_NAME="${ABS_DB_NAME:-account_bind_system}"

cat "$1" | docker compose exec -T postgres psql -U "$DB_USER" -d "$DB_NAME"
