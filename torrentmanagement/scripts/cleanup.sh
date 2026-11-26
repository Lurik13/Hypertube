#!/bin/sh
# Clear storage only after stopping active torrent writes, then restore prior state.
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)

cd "$SCRIPT_DIR"
WAS_RUNNING=0
WAS_DATABASE_RUNNING=0
if docker compose -p hypertube-torrentmanagement -f compose.yaml ps --status running -q torrentmanagement | grep -q .; then
    WAS_RUNNING=1
fi
if docker compose -p hypertube-torrentmanagement -f compose.yaml ps --status running -q postgres | grep -q .; then
    WAS_DATABASE_RUNNING=1
fi

restore_services() {
    if [ "$WAS_RUNNING" -eq 1 ]; then
        docker compose -p hypertube-torrentmanagement -f compose.yaml start torrentmanagement
    fi
    if [ "$WAS_DATABASE_RUNNING" -eq 0 ] && [ "$WAS_RUNNING" -eq 0 ]; then
        docker compose -p hypertube-torrentmanagement -f compose.yaml stop postgres
    fi
}

trap restore_services EXIT
docker compose -p hypertube-torrentmanagement -f compose.yaml stop torrentmanagement
docker compose -p hypertube-torrentmanagement -f compose.yaml up -d --wait postgres
docker compose -p hypertube-torrentmanagement -f compose.yaml run --rm --no-deps torrentmanagement python -m app.cleanup

trap - EXIT
restore_services

printf '%s\n' 'Torrentmanagement data and matching job records were cleared.'
