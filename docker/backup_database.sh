#!/bin/sh
# Dedicated PostgreSQL 16+ client host/container; credentials via protected PG* env.
set -eu
umask 077
: "${BACKUP_DIRECTORY:?Set a dedicated encrypted backup directory}"
test -d "$BACKUP_DIRECTORY"
name="oweru-$(date -u +%Y%m%dT%H%M%SZ).dump"
target="$BACKUP_DIRECTORY/$name"
partial="$target.partial"
trap 'rm -f -- "$partial"' EXIT HUP INT TERM
pg_dump --format=custom --no-owner --no-acl --file="$partial"
pg_restore --list "$partial" >/dev/null
mv -- "$partial" "$target"
sha256sum "$target" > "$target.sha256"
# Expiry is intentionally performed by reviewed provider lifecycle policy.
# Upload/replicate and verify the checksum before marking a daily backup successful.
printf '%s\n' "$name"
