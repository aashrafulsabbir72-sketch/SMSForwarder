#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
if [ -f "$HERE/watchdog.pid" ]; then
  pid="$(cat "$HERE/watchdog.pid")"
  kill "$pid" 2>/dev/null || true
  sleep 1
  kill -9 "$pid" 2>/dev/null || true
  rm -f "$HERE/watchdog.pid"
fi
