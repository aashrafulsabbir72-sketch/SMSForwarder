# V10 fixed default connection

This build does not store a real Telegram bot token in the Android source. The Telegram bot token remains in the Termux backend.

For a fixed default device connection, configure these GitHub Actions repository secrets before building:
- FIXED_BACKEND_URL
- FIXED_BACKEND_KEY
- FIXED_TELEGRAM_CHAT_ID (optional metadata; the backend remains the Telegram bot owner)

The first two values are compiled into the APK as defaults, so the app can start without asking for backend configuration. Because a compiled backend key can be extracted from an APK, use HTTPS and treat that key as public/rotatable. Never put the Telegram bot token in the APK.
