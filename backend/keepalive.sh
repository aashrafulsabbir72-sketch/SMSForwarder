#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
LOG="$HERE/watchdog.log"
PIDFILE="$HERE/watchdog.pid"
INTERVAL="${KEEPALIVE_INTERVAL:-20}"

# Keep Termux awake while this watchdog is active.
if command -v termux-wake-lock >/dev/null 2>&1; then
  termux-wake-lock >/dev/null 2>&1 || true
fi

echo $$ > "$PIDFILE"
trap 'rm -f "$PIDFILE"; if command -v termux-wake-unlock >/dev/null 2>&1; then termux-wake-unlock >/dev/null 2>&1 || true; fi' EXIT INT TERM

while true; do
  if [ ! -f "$HERE/.env" ]; then
    echo "$(date '+%F %T') waiting for backend/.env" >> "$LOG"
    sleep 10
    continue
  fi

  BACKEND_ALIVE=0
  if [ -f "$HERE/backend.pid" ] && kill -0 "$(cat "$HERE/backend.pid" 2>/dev/null || echo 0)" 2>/dev/null; then
    BACKEND_ALIVE=1
  fi
  if [ "$BACKEND_ALIVE" -eq 1 ] && command -v curl >/dev/null 2>&1 && [ -f "$HERE/.env" ]; then
    KEY="$(grep '^BACKEND_KEY=' "$HERE/.env" | cut -d= -f2-)"
    PORT="$(grep '^PORT=' "$HERE/.env" | cut -d= -f2- || true)"
    PORT="${PORT:-8899}"
    curl -fsS --max-time 5 -H "X-Backend-Key: $KEY" "http://127.0.0.1:${PORT}/health" >/dev/null 2>&1 || BACKEND_ALIVE=0
  fi
  if [ "$BACKEND_ALIVE" -eq 0 ]; then
    echo "$(date '+%F %T') backend unhealthy; restarting" >> "$LOG"
    "$HERE/stop.sh" >> "$LOG" 2>&1 || true
    "$HERE/start.sh" >> "$LOG" 2>&1 || true
  fi

  if [ ! -f "$ROOT/frpc.pid" ] || ! kill -0 "$(cat "$ROOT/frpc.pid" 2>/dev/null || echo 0)" 2>/dev/null; then
    if command -v frpc >/dev/null 2>&1; then
      echo "$(date '+%F %T') frpc not running; restarting" >> "$LOG"
      pkill -f 'frpc.*frpc.toml' 2>/dev/null || true
      nohup frpc -c "$ROOT/frpc.toml" >> "$ROOT/frpc-run.log" 2>&1 &
      echo $! > "$ROOT/frpc.pid"
    fi
  fi

  sleep "$INTERVAL"
done
