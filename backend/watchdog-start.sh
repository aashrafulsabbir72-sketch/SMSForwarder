#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
PIDFILE="$HERE/watchdog.pid"
LOG="$HERE/watchdog.log"

if [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE" 2>/dev/null || echo 0)" 2>/dev/null; then
  echo "Watchdog already running: PID $(cat "$PIDFILE")"
  exit 0
fi

nohup "$HERE/keepalive.sh" >> "$LOG" 2>&1 &
echo "Watchdog started: PID $!"
