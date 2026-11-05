# Troubleshooting: Mobile App

## App Won't Open / Crashes on Launch

1. **Force close and reopen**: Swipe the app away from your recent apps list, then reopen it
2. **Check for updates**: Ensure you're running the latest version from the App Store (iOS) or Google Play (Android)
3. **Restart your device**: A simple restart often resolves startup issues
4. **Clear app cache** (Android only): Go to Settings → Apps → FlowDesk → Storage → Clear Cache
5. **Reinstall the app**: Uninstall FlowDesk, restart your device, then reinstall from the app store

## Login Issues on Mobile

- Ensure you're using the correct email and password (passwords are case-sensitive)
- If you use SSO, tap **Sign in with SSO** and enter your organization's SSO domain
- Check that your device's date and time are set to automatic — incorrect time can cause authentication failures
- If 2FA codes are not working, ensure your authenticator app's time is synced (Authy: Settings → Time Correction)

## Push Notifications Not Working

### iOS
1. Go to Settings → Notifications → FlowDesk
2. Ensure **Allow Notifications** is turned on
3. Check that alert style is set to **Banners** or **Alerts**
4. Ensure Do Not Disturb is not active

### Android
1. Go to Settings → Apps → FlowDesk → Notifications
2. Ensure notifications are enabled for all categories
3. Check that battery optimization is not restricting FlowDesk: Settings → Battery → Battery Optimization → FlowDesk → Don't Optimize

## Slow Performance

- Close other apps running in the background
- Ensure your device has at least 500 MB of free storage
- Check your internet connection — FlowDesk requires at least 1 Mbps for optimal performance
- Disable any VPN or proxy that may be slowing your connection
- If on cellular data, switch to Wi-Fi if available

## Offline Mode

FlowDesk mobile app supports limited offline functionality:
- You can view previously loaded tickets and conversations
- New messages will be queued and sent when connectivity is restored
- Knowledge base articles that were previously viewed are cached for offline reading
- Dashboard data and analytics are not available offline

## Supported Devices

- **iOS**: iPhone 8 and later, running iOS 16 or newer
- **Android**: Devices running Android 12 or newer with at least 4 GB RAM
- **Tablets**: iPad (7th generation+), iPad Air (3rd generation+), Samsung Galaxy Tab S6+

## Reporting a Bug

If you encounter a bug in the mobile app:
1. Shake your device to trigger the bug report dialog (must be enabled in Settings → Advanced → Shake to Report)
2. Or go to Settings → Help → Report a Bug
3. Include a screenshot and description of the issue
4. Logs are automatically attached to help our engineering team diagnose the problem
