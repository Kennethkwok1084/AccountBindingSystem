#!/usr/bin/env sh
set -eu

DB_USER="${ABS_DB_USER:-abs_user}"
DB_NAME="${ABS_DB_NAME:-account_bind_system}"

mkdir -p backup
docker compose exec -T postgres pg_dump -U "$DB_USER" "$DB_NAME" > "backup/${DB_NAME}_$(date +%Y%m%d%H%M%S).sql"
