Central backend bridge:
- Telegram polling is centralized in Termux backend.
- Android devices register/heartbeat/poll/ack against the backend.
- Device status includes battery, model, app version, online state and observed backend IP.
- SMS forwarding implementation (SmsReceiver.kt) is intentionally unchanged.
