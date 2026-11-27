#!/bin/sh
# Apply pending migrations (api only, RUN_MIGRATIONS=1), then run the command.
set -eu

if [ "${RUN_MIGRATIONS:-0}" = "1" ]; then
    alembic upgrade head
fi

exec "$@"
