#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)

cd "$SCRIPT_DIR"
WAS_RUNNING=0
if docker compose -p hypertube-torrentmanagement -f compose.yaml ps --status running -q torrentmanagement | grep -q .; then
    WAS_RUNNING=1
fi

docker compose -p hypertube-torrentmanagement -f compose.yaml stop torrentmanagement
docker compose -p hypertube-torrentmanagement -f compose.yaml run --rm --no-deps torrentmanagement python -m app.cleanup

if [ "$WAS_RUNNING" -eq 1 ]; then
    docker compose -p hypertube-torrentmanagement -f compose.yaml start torrentmanagement
fi

printf '%s\n' 'Torrentmanagement data and matching job records were cleared.'
