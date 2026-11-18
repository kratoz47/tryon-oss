#!/usr/bin/env bash
set -euo pipefail
if [ "$(id -u)" != 0 ]; then echo "Run as root"; exit 1; fi
if [ "$(pwd -P)" != /opt/tryon ]; then echo "Extract into /opt/tryon first"; exit 1; fi
if [ -e /etc/systemd/system/shiyi.service ] || [ -e /etc/tryon/tryon.env ]; then
  echo "Existing deployment found; inspect before updating"; exit 1
fi
getent passwd www-data >/dev/null || { echo "www-data user missing"; exit 1; }
SHIYI_PYTHON=${SHIYI_PYTHON:-python3.11}
"$SHIYI_PYTHON" -c 'import sys; assert sys.version_info >= (3,10), "Python 3.10+ required"'
if ss -ltn | grep -q ':8765 '; then echo "Port 8765 is occupied"; exit 1; fi
"$SHIYI_PYTHON" -m venv .venv
.venv/bin/python -m pip install --no-cache-dir -r deploy/requirements.txt
read -r -p "Public HTTPS origin (example https://tryon.example.com): " APP_ORIGIN
APP_ORIGIN="$APP_ORIGIN" "$SHIYI_PYTHON" -c 'import os,urllib.parse; u=urllib.parse.urlsplit(os.environ["APP_ORIGIN"]); assert u.scheme=="https" and u.hostname and not u.path and not u.query and not u.fragment and not u.username'
read -r -s -p "ARK_API_KEY: " ARK_API_KEY
printf '\n'
if [ -z "$ARK_API_KEY" ] || [[ "$ARK_API_KEY" == *$'\n'* ]]; then echo "Invalid key"; exit 1; fi
umask 077
printf 'APP_ORIGIN=%s\nARK_API_KEY=%s\n' "$APP_ORIGIN" "$ARK_API_KEY" >/etc/tryon/tryon.env
unset ARK_API_KEY
if [ -L /var/lib/tryon ]; then echo "Unexpected data symlink"; exit 1; fi
install -d -o www-data -g www-data -m 700 /var/lib/tryon
install -m 644 deploy/shiyi.service /etc/systemd/system/shiyi.service
systemctl daemon-reload
systemctl enable --now shiyi
echo "Backend installed on 127.0.0.1:8765."
echo "Configure a separate HTTPS site using deploy/nginx-location.conf."
echo "Avatar generation requires phone login. Configure reviewed SMS details with deploy/configure_sms.py."
