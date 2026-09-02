#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
cd "$HERE"
if [ -f backend.pid ] && kill -0 "$(cat backend.pid)" 2>/dev/null; then echo "Backend: RUNNING (PID $(cat backend.pid))"; else echo "Backend: STOPPED"; fi
[ -f backend.db ] && echo "DB: OK ($(du -h backend.db | cut -f1))" || echo "DB: MISSING"
echo '--- last log lines ---'
tail -n 12 backend.log 2>/dev/null || true
