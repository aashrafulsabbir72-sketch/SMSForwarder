#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
ENV="$HERE/.env"
mkdir -p "$HERE"

get_env() { grep -E "^$1=" "$ENV" 2>/dev/null | head -n1 | cut -d= -f2- || true; }

BOT_TOKEN="$(get_env BOT_TOKEN)"
CHAT_ID="$(get_env CHAT_ID)"
BACKEND_KEY="$(get_env BACKEND_KEY)"

if [ -z "$BOT_TOKEN" ]; then
  read -r -p 'Telegram BOT TOKEN: ' BOT_TOKEN
fi
if [ -z "$CHAT_ID" ]; then
  read -r -p 'Telegram CHAT ID: ' CHAT_ID
fi

if [ -z "$BACKEND_KEY" ]; then
  if command -v openssl >/dev/null 2>&1; then
    BACKEND_KEY="$(openssl rand -base64 48 | tr '+/' '-_' | tr -d '=')"
  else
    BACKEND_KEY="$(python - <<'PY'
import secrets
print(secrets.token_urlsafe(48))
PY
)"
  fi
fi

REMOTE_URL="$(python - "$ROOT/frpc.toml" <<'PY'
import re,sys
s=open(sys.argv[1],encoding='utf-8').read()
host=re.search(r'^serverAddr\s*=\s*"([^"]+)"',s,re.M)
port=re.search(r'^remotePort\s*=\s*(\d+)',s,re.M)
print(f"http://{host.group(1)}:{port.group(1)}" if host and port else "")
PY
)"

cat > "$ENV" <<EOF2
BOT_TOKEN=$BOT_TOKEN
CHAT_ID=$CHAT_ID
BACKEND_KEY=$BACKEND_KEY
HOST=127.0.0.1
PORT=8899
EOF2
chmod 600 "$ENV"

echo "Backend provisioning complete. Keep backend/.env private."

if ! command -v curl >/dev/null 2>&1; then
  pkg install -y curl >/dev/null
fi
export TG_JSON="$(curl -sS --fail-with-body --connect-timeout 10 --max-time 30 \
  -H 'Content-Type: application/json' \
  --data '{}' "https://api.telegram.org/bot${BOT_TOKEN}/getMe")" || {
  echo 'Telegram API connection failed' >&2
  exit 1
}
python - <<'PY'
import json, os
s = os.environ.get('TG_JSON','')
if not s or not json.loads(s).get('ok'): raise SystemExit('Telegram token rejected')
print('Telegram token: OK')
print('Bot:', json.loads(s)['result'].get('username',''))
PY

echo 'Provisioning complete.'
