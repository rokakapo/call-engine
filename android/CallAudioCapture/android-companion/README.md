# Project1 Companion (Android)

This directory contains the Android companion app source. The repository's GitHub Actions workflow builds a **debug APK**.

## Build on GitHub

1. Open **Actions → Build Android APK** and select **Run workflow**, or push a change under `android-companion/`.
2. The workflow installs the required Android SDK platform and build tools in GitHub's hosted runner.
3. Open the completed run and download the `project1-companion-debug-apk` artifact.
4. Extract the ZIP and install `app-debug.apk` on the Android phone.

## Runtime requirements

- The Project1 Python backend must be running on the **same phone** at `http://127.0.0.1:8765`.
- Open the companion app and grant SMS permission if SMS capture is wanted.
- Enable **Notification Access** in Android settings if app-notification capture is wanted.
- Choose discovered sources in the Project1 web UI. The companion is designed to send content only for selected sources.
- This app captures new events; it does not read the old SMS inbox or notification history.

## Important status

This source has not yet been built or tested on a real Android device. A successful GitHub build only confirms compilation, not that the backend integration and Android permissions work correctly. Validate with a non-sensitive test message/notification before relying on it.

## Privacy

SMS and notification content can contain sensitive data. Keep the repository private, do not commit `accounts.sqlite3`, credentials, signing keys, or personal data, and review permissions before installing. The current debug APK is not a production release build.
