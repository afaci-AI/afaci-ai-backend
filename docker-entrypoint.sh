#!/bin/sh
set -e

echo "[entrypoint] applying alembic migrations..."
alembic upgrade head

echo "[entrypoint] starting app..."
exec "$@"
