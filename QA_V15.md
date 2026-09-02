# V15 QA / Recheck

- Telegram polling is centralized in Termux backend.
- Telegram update_id offset is persisted and advanced after processing; getUpdates long polling follows Telegram’s offset model.
- Commands use per-device queues, atomic lease claim, persistent ACK, and reply retry.
- Rapid duplicate taps for the same device/action are suppressed for 2.5 seconds.
- Device registration includes fixed Telegram control chat binding.
- Test command reports that the command was actually received/executed instead of claiming an unverified generic “Working!” state.
- App CHECK CONNECTION button now performs an authenticated backend health request.
- Reload resets endpoint selection without spawning a second listener thread.
- Pause/Resume/Reset Stats persist with commit() before ACK.
- No arbitrary shell/remote code execution command exists.
- No GPS requirement is used by the current Android service flow.
- Telegram Bot Token remains backend-side; Android build only receives fixed backend URL/key/chat binding.

Known platform limit: exactly-once delivery and 100% uptime cannot be guaranteed across device power loss, OS force-stop, network outage, or Telegram/network failures. The design uses at-least-once command delivery with duplicate suppression and persistent acknowledgements.
