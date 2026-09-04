#!/usr/bin/env bash
set -euo pipefail

if [[ $EUID -ne 0 ]]; then
	echo "Run this script with sudo." >&2
	exit 1
fi

sudo -u styl git -C /opt/styl pull --ff-only
sudo -u styl /opt/styl/backend/.venv/bin/pip install -r /opt/styl/backend/requirements.txt

sudo -u styl npm --prefix /opt/styl/frontend ci
sudo -u styl npm --prefix /opt/styl/frontend run build

systemctl restart styl-api styl-web
systemctl --no-pager --full status styl-api styl-web
