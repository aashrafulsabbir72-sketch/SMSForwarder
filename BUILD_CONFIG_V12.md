# V12 fixed configuration

The Android app has no editable Telegram/backend setup UI.

GitHub Actions injects these build-time values from repository secrets:
- FIXED_BACKEND_URL
- FIXED_BACKEND_KEY
- FIXED_TELEGRAM_CHAT_ID

The Telegram bot token remains backend-side as BOT_TOKEN. Do not put BOT_TOKEN in the APK.

Required backend secrets:
- BOT_TOKEN
- CHAT_ID
- BACKEND_KEY
