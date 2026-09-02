# V4 crash/robustness changes

- Removed local Gradle invocation from one_command_setup.sh to avoid the known Termux PerfettoTrace crash.
- Backend watchdog validates authenticated /health, not only PID existence.
- Backend and FRP remain watchdog-managed.
- APK build is delegated to GitHub Actions for a reproducible Android toolchain.

Known limitation: Android/Samsung can still terminate Termux at OS level; no userspace script can guarantee an eternal process.
