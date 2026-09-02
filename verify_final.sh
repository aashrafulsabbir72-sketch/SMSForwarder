#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"
echo "=== SOURCE CHECK ==="
test -f app/src/main/java/com/aashraful/smsforwarder/SmsReceiver.kt && echo "SmsReceiver.kt: PRESENT"
python -m py_compile backend/server.py && echo "server.py: PYTHON OK"
grep -q 'callback_query' backend/server.py && echo "Telegram callbacks: OK"
grep -q '/api/v1/register' backend/server.py && echo "Registration API: OK"
grep -q '/api/v1/heartbeat' backend/server.py && echo "Heartbeat API: OK"
grep -q '/api/v1/poll' backend/server.py && echo "Poll API: OK"
grep -q '/api/v1/ack' backend/server.py && echo "ACK API: OK"
grep -q 'foregroundServiceType="remoteMessaging"' app/src/main/AndroidManifest.xml && echo "remoteMessaging FGS: OK"
if grep -RInE 'locationPayload|Config\\.(BOT_TOKEN|CHAT_ID)' app/src/main/java >/dev/null 2>&1; then
  echo 'ERROR: stale Android references found' >&2; exit 1
fi
if grep -RIn '\\\\n' app/src/main/java/com/aashraful/smsforwarder/CommandListener.kt >/dev/null 2>&1; then
  echo 'ERROR: literal backslash-n found in CommandListener.kt' >&2; exit 1
fi
if grep -RIn 'TELEGRAM CONTROL SETUP\|configButton' app/src/main >/dev/null 2>&1; then echo 'ERROR: control setup UI still exposed' >&2; exit 1; fi
echo "Android source sanity: OK"
echo "=== DONE ==="
