SMSForwarder2 — CENTRAL BACKEND + WATCHDOG

First-time setup:
  cd ~/SMSForwarder2/backend
  ./provision.sh

Start the backend + watchdog:
  ./start.sh
  ./watchdog-start.sh

Check:
  ./status.sh

Stop backend (watchdog can restart it):
  ./stop.sh

Stop watchdog first if you want everything to stay stopped:
  ./watchdog-stop.sh
  ./stop.sh

FRP:
  cd ~/SMSForwarder2
  nohup ./frpc -c ./frpc.toml >> frpc-run.log 2>&1 &

The watchdog checks every 20 seconds and restarts the backend or FRP
process if either process exits. It also requests a Termux wake lock when
that command is available.

IMPORTANT:
- Android/Samsung may still kill Termux if the user force-stops it, revokes
  battery/background access, or the system applies aggressive memory policy.
  A userspace watchdog cannot override those OS rules.
- For best reliability, exempt Termux from battery optimization and allow it
  to run in the background. Do not use a forced-stop bypass.
- Only the Termux backend polls Telegram getUpdates.
- Keep backend/.env private (chmod 600).
