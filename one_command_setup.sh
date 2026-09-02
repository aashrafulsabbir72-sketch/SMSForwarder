#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"
chmod +x backend/*.sh one_command_setup.sh 2>/dev/null || true
command -v python >/dev/null 2>&1 || pkg install -y python
command -v curl >/dev/null 2>&1 || pkg install -y curl
command -v frpc >/dev/null 2>&1 || pkg install -y frp
./backend/provision.sh
./backend/stop.sh >/dev/null 2>&1 || true
./backend/start.sh
./backend/watchdog-start.sh
KEY="$(grep '^BACKEND_KEY=' backend/.env | cut -d= -f2-)"
[ -n "$KEY" ]
PORT="$(grep '^PORT=' backend/.env | cut -d= -f2- || true)"
PORT="${PORT:-8899}"
curl -fsS --max-time 8 -H "X-Backend-Key: $KEY" "http://127.0.0.1:${PORT}/health" >/dev/null
echo 'API: OK'
pkill -f 'frpc.*frpc.toml' 2>/dev/null || true
nohup frpc -c "$ROOT/frpc.toml" > "$ROOT/frpc-run.log" 2>&1 &
FRP_PID=$!
echo "$FRP_PID" > "$ROOT/frpc.pid"
sleep 4
if ! kill -0 "$FRP_PID" 2>/dev/null; then
  echo 'FRP failed; log:' >&2
  tail -n 40 "$ROOT/frpc-run.log" >&2 || true
  exit 1
fi
echo '========================================'
echo '✅ TERMUX BACKEND SETUP COMPLETE'
echo 'Backend: 127.0.0.1:'"$PORT"
echo 'Telegram: centralized in Termux backend'
echo 'Watchdog: backend + FRP auto-restart enabled'
echo 'APK: build/download from GitHub Actions'
echo 'NOTE: no Gradle build is attempted in Termux'
echo '========================================'
