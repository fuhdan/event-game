#!/bin/sh
# Read Docker secrets and assemble environment variables before starting the app.
set -e

_read_secret() {
    local file="/run/secrets/$1"
    [ -f "$file" ] && cat "$file"
}

POSTGRES_USER=$(_read_secret postgres_user)
POSTGRES_PASSWORD=$(_read_secret postgres_password)
JWT_SECRET=$(_read_secret jwt_secret)

POSTGRES_HOST="${POSTGRES_HOST:-postgres}"
POSTGRES_PORT="${POSTGRES_PORT:-5432}"
POSTGRES_DB="${POSTGRES_DB:-event_game}"

if [ -n "$POSTGRES_USER" ] && [ -n "$POSTGRES_PASSWORD" ]; then
    export DATABASE_URL="postgresql+psycopg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@${POSTGRES_HOST}:${POSTGRES_PORT}/${POSTGRES_DB}"
fi

if [ -n "$JWT_SECRET" ]; then
    export JWT_SECRET_KEY="$JWT_SECRET"
fi

exec "$@"
