#!/bin/sh
# Applies pending Alembic migrations, then execs the given command (normally uvicorn).
# Using `exec` replaces this shell so the app receives signals directly (clean shutdown).
set -e

echo "Applying database migrations..."
alembic upgrade head

exec "$@"
