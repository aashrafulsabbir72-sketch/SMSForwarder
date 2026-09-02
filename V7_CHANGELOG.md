# V7 reliability and safety cleanup

- Removed APK-side secret injection from backend provisioning.
- SMS delivery uses one serialized uploader instead of one thread per message.
- Common OTP/verification codes are redacted before SMS event transmission.
- Existing bounded Telegram device control preserved.
- Added Restart Service and Re-register device controls.
- Termux setup remains Gradle-free; APK builds remain in GitHub Actions.
- Backend remains authenticated with X-Backend-Key and Telegram CHAT_ID authorization.
