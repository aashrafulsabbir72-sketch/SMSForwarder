#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
cd "$HERE"
[ -f .env ] || { echo 'Missing backend/.env. Run ./provision.sh first.' >&2; exit 1; }
set -a; . ./.env; set +a

if [ -f backend.pid ] && kill -0 "$(cat backend.pid 2>/dev/null || echo 0)" 2>/dev/null; then
  echo "Backend already running: PID $(cat backend.pid)"
  exit 0
fi

ME="$HERE/server.py"
ps -eo pid=,args= 2>/dev/null | while read -r pid args; do
  case "$args" in
    *"$ME"*) [ "$pid" = "$$" ] || kill "$pid" 2>/dev/null || true ;;
  esac
done

nohup python "$ME" >> "$HERE/backend.log" 2>&1 &
echo $! > "$HERE/backend.pid"
PID=$!
sleep 2
if ! kill -0 "$PID" 2>/dev/null; then
  echo 'Backend failed to start' >&2
  tail -n 50 "$HERE/backend.log" >&2 || true
  rm -f "$HERE/backend.pid"
  exit 1
fi

if command -v curl >/dev/null 2>&1; then
  if ! curl -fsS --max-time 5 -H "X-Backend-Key: $BACKEND_KEY" "http://127.0.0.1:${PORT:-8899}/health" >/dev/null; then
    echo 'Backend process started but health check failed' >&2
    tail -n 30 "$HERE/backend.log" >&2 || true
    exit 1
  fi
fi

echo "Backend started: PID $PID"
