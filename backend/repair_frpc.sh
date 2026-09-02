#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
log(){ printf '[FRP] %s\n' "$*"; }
if command -v frpc >/dev/null 2>&1; then
  SYS_FRPC="$(command -v frpc)"
else
  pkg update -y >/dev/null 2>&1 || true
  pkg install -y frp >/dev/null
  SYS_FRPC="$(command -v frpc || true)"
fi
if [ -z "$SYS_FRPC" ]; then
  echo 'ERROR: Termux frp package did not provide frpc.' >&2
  exit 1
fi
chmod +x "$SYS_FRPC" 2>/dev/null || true
"$SYS_FRPC" --version >/dev/null 2>&1 || { echo 'ERROR: installed frpc cannot execute.' >&2; exit 1; }
rm -f "$ROOT/frpc"
ln -s "$SYS_FRPC" "$ROOT/frpc"
log "Using Termux frpc: $SYS_FRPC"
log 'FRP binary available; config will be tested when FRP starts.'
