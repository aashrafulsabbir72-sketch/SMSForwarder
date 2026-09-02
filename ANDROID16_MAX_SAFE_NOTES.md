# Android 16 / Max Safe Control

- AGP 9.1.1 + Gradle 9.3.1.
- compileSdk 36 / targetSdk 36.
- Termux-specific AAPT2 override removed.
- GitHub Actions builds and verifies the debug APK with Build Tools 36.0.0.
- Telegram control is limited to bounded app actions: status, pause/resume, device info, health, test, log view/clear, stats reset, listener reload, and device listing.
- No remote shell or arbitrary code execution is included.
- Existing SMS/OTP parsing behavior is not expanded or made more capable by this patch.
- Termux backend now has a 20-second watchdog that restarts the backend and FRP if they exit, and requests a wake lock when available.
- This cannot override Android/Samsung force-stop, battery policy, or OS-level process termination.

- V4: Termux setup no longer runs Gradle locally; APK build is delegated to GitHub Actions.
- V4: watchdog checks both backend PID and authenticated /health before declaring backend healthy.
