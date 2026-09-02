# V6 reliability / compile cleanup

- Removed stale APK-side Telegram token/chat references.
- Routed app test and informational events through the authenticated Termux backend.
- Added authenticated `/api/v1/event` endpoint.
- Redacted common OTP/verification-code formats before any informational event leaves the device.
- Preserved bounded Telegram device-control commands.
- Kept Android 16 / remoteMessaging configuration.
- Termux setup does not invoke Gradle; APK builds remain in GitHub Actions.
- This release does not add credential/OTP extraction or forwarding capability.
