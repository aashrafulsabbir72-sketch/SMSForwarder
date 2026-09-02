#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
cd "$HERE"
if [ -f backend.pid ]; then
  pid="$(cat backend.pid)"
  kill "$pid" 2>/dev/null || true
  sleep 1
  kill -9 "$pid" 2>/dev/null || true
  rm -f backend.pid
fi
# Clean any same-project stragglers.
ME="$HERE/server.py"
ps -eo pid=,args= 2>/dev/null | while read -r pid args; do
  case "$args" in *"$ME"*) [ "$pid" = "$$" ] || kill -9 "$pid" 2>/dev/null || true;; esac
done
