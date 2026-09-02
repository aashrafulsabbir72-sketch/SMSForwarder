# Telegram Bot UI V15.1 Final

The Telegram control UI now uses one persistent bottom reply keyboard for the full command set.

Main chat behavior:
- `/start` installs/refreshes the bottom command keyboard and leaves no visible bot control panel message.
- The previous inline `SMS FORWARDER CONTROL` panel is no longer created.
- Command buttons are routed from the bottom keyboard.
- Device picker remains inline only after a command that needs a target device.
- Existing V15 command queue, duplicate suppression, ACK and retry logic are unchanged.
- Android APK code/SMS receiver is unchanged.


Superseded by V15.2 UI: home now contains only Resume, Pause, Status and Logs; secondary controls are nested under Status/Logs.
