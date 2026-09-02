# SMSForwarder2 FINAL SAFE RUN

1. Extract this project and enter `SMSForwarder2`.
2. Run `chmod +x one_command_setup.sh backend/*.sh gradlew && ./one_command_setup.sh`.
3. Enter Telegram Bot Token and authorized Chat ID only in Termux when prompted.
4. The setup starts the backend, a 20-second watchdog, and FRP.
5. Install the APK created by GitHub Actions from the artifact.
6. Open the APK and grant only the permissions required for the intended SMS-forwarding operation.
7. Telegram: `/start` → Status / Pause / Resume / Log / Device Info / Test / Health.
8. Keep Termux allowed to run in the background. Android may still stop processes after a force-stop or due to system policy.

The Telegram bot is centralized in the Termux backend. Android devices do not poll Telegram directly for commands.
