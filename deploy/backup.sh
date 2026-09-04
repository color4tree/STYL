#!/usr/bin/env bash
set -euo pipefail

backup_directory=/var/backups/styl
data_directory=/var/lib/styl
timestamp=$(date -u +%Y%m%dT%H%M%SZ)

install -d -m 0750 "$backup_directory"
tar -C "$data_directory" -czf "$backup_directory/styl-$timestamp.tar.gz" .
find "$backup_directory" -type f -name 'styl-*.tar.gz' -mtime +14 -delete
