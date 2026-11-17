#!/bin/sh
set -eu

if [ "$(id -u)" = "0" ]; then
    database_path="${NOTIFICATIONS_DB:-/data/notifications.db}"
    database_directory="$(dirname "$database_path")"
    mkdir -p "$database_directory"
    chown app:app "$database_directory"
    for suffix in "" "-wal" "-shm"; do
        if [ -f "$database_path$suffix" ]; then
            chown app:app "$database_path$suffix"
        fi
    done
    exec gosu app "$@"
fi

exec "$@"
