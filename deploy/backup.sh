#!/usr/bin/env bash
set -euo pipefail

umask 0077
backup_directory=${STYL_BACKUP_DIR:-/var/backups/styl}
data_directory=${STYL_DATA_DIR:-/var/lib/styl}
timestamp=$(date -u +%Y%m%dT%H%M%S%NZ)

install -d -m 0700 "$backup_directory"
archive="$backup_directory/styl-$timestamp-$$.tar.gz"
# A failed or interrupted archive remains visibly incomplete for recovery.
set -o noclobber
tar -C "$data_directory" -czf - . > "$archive.active"
ln "$archive.active" "$archive"
rm -- "$archive.active"
# Business backups never expire on age or size. No automatic cleanup belongs here.
