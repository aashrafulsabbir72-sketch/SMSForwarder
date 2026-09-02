# V5 Reliability / Android 16 Fixes

- Switched the continuous user-visible service to `remoteMessaging`, which matches text-message transfer and avoids Android 15 `dataSync` 6-hour timeout.
- Added reliable persistent command-result ACK retry on the device.
- Added authenticated `/api/v1/health` with device heartbeat state.
- Added boot and package-replacement service start handling.
- Uses `ServiceCompat.startForeground()` with the explicit remote-messaging foreground-service type.
- Termux setup remains free of local Gradle execution; APK builds via GitHub Actions.
- No remote shell or arbitrary code execution added.
