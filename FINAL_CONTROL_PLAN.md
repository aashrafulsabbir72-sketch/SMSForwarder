# SMSForwarder2 — Final Control Plan

Telegram control is centralized in the Termux backend. The APK registers, heartbeats, polls for commands, and acknowledges results.

Supported remote actions: Pause, Resume, Status, Device Info, Log, Test, Health, Clear Log, Reset Stats, Reload, plus device listing/refresh.

The APK is configured at runtime with the Termux backend URL and backend key. The Telegram bot token remains private to the Termux backend.

The Android app does not accept arbitrary remote code or shell commands. A remote control action is limited to the allowlisted app operations above.

The control channel only works while the Android foreground listener is running and the backend is reachable; Android/OEM background restrictions can still stop a service. The APK cannot bypass those OS restrictions remotely.

Existing SMS/OTP behavior is intentionally not expanded by this release.

The Android client does not receive the Telegram bot token from provisioning; backend secrets stay in Termux `.env`.
