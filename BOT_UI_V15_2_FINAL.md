# Telegram Bot UI V15.3 Final

## Home screen
The persistent Telegram home keyboard is intentionally limited to four primary controls:
- ▶️ Resume
- ⏸ Pause
- 📊 Status
- 📋 Logs

No large control panel message is created on `/start`. The bottom keyboard is installed silently.

## Nested menus
### 📊 Status
- 📊 Device Status
- 📱 Devices
- ℹ️ Device Info
- 🩺 Health
- 🌐 Backend
- ↩️ Home

### 📋 Logs
- 📩 Last SMS / Log
- 🧪 Test
- 🧹 Clear Log
- 🔄 Reset Stats
- ♻️ Reload
- 🔄 Restart Service
- 🔁 Re-register
- ↩️ Home

Resume/Pause open the device picker directly for the fastest common control path.

## Realtime / duplicate handling
- Callback queries are acknowledged immediately.
- The tapped inline keyboard is cleared immediately after the callback is received, preventing stale/double taps.
- Telegram polling remains single-consumer with the existing offset persistence and no-webhook startup behavior.
- Existing command queue, atomic claim/lease, semantic duplicate suppression, persistent ACK, and retry delivery remain unchanged.
- Android SMS receiver is unchanged.

## Realtime Turbo V15.3
- Telegram callback acknowledgement uses a dedicated low-latency request path (no exponential retry/backoff).
- Inline keyboard cleanup uses the same low-latency path.
- Durable command delivery remains on SQLite queue + atomic claim/lease + idempotent ACK/reply retry.
- Android long-poll + backend condition wake path remains unchanged for immediate command pickup.


V15.4 REALTIME FINAL: interactive Telegram UI sends use fast API path with reliable fallback; callback ACK/keyboard cleanup remains immediate.
