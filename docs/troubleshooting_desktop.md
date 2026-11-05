# Troubleshooting: Desktop App

## Installation Issues

### Windows
- **Minimum requirements**: Windows 10 (21H2 or later), 8 GB RAM, 2 GB free disk space
- If the installer fails, run it as Administrator: right-click the installer → **Run as administrator**
- Ensure .NET Framework 4.7.2 or later is installed
- Disable antivirus temporarily if the installer is being blocked (re-enable after installation)

### macOS
- **Minimum requirements**: macOS 12 (Monterey) or later, 8 GB RAM, 2 GB free disk space
- If you see "App can't be opened because it's from an unidentified developer": go to System Preferences → Security & Privacy → General → click **Open Anyway**
- For Apple Silicon (M1/M2/M3) Macs: the app runs natively — no Rosetta required

### Linux
- **Supported distributions**: Ubuntu 22.04+, Fedora 38+, Debian 12+
- Install via the provided .deb or .rpm package, or use the Snap store: `snap install flowdesk`
- If you encounter dependency errors, run `sudo apt-get install -f` (Debian/Ubuntu) to resolve

## App Won't Start

1. Check if another instance of FlowDesk is already running (check Task Manager on Windows, Activity Monitor on macOS)
2. Clear the app cache:
   - Windows: Delete `%APPDATA%\FlowDesk\Cache`
   - macOS: Delete `~/Library/Caches/com.flowdesk.app`
   - Linux: Delete `~/.cache/flowdesk`
3. Reset preferences: rename or delete the config file:
   - Windows: `%APPDATA%\FlowDesk\config.json`
   - macOS: `~/Library/Application Support/FlowDesk/config.json`
   - Linux: `~/.config/flowdesk/config.json`
4. Reinstall the app if the above steps don't work

## Screen Sharing Not Working

- Ensure you've granted screen recording permissions:
  - macOS: System Preferences → Security & Privacy → Privacy → Screen Recording → check FlowDesk
  - Windows: No special permission needed, but ensure the app is not being blocked by Group Policy
- Close other screen-sharing applications (Zoom, Teams, etc.) that may be holding the screen capture API
- Restart the app after granting permissions

## High CPU / Memory Usage

- FlowDesk desktop typically uses 200–400 MB RAM and less than 5% CPU
- If usage is significantly higher:
  1. Check for stuck background processes: Help → Developer Tools → Performance
  2. Disable unnecessary integrations: Settings → Integrations → toggle off unused ones
  3. Reduce the number of open tickets/tabs
  4. Update to the latest version — performance improvements are included in each release

## Keyboard Shortcuts

| Action | Windows/Linux | macOS |
|--------|--------------|-------|
| New ticket | Ctrl+N | Cmd+N |
| Search | Ctrl+K | Cmd+K |
| Quick reply | Ctrl+Enter | Cmd+Enter |
| Toggle sidebar | Ctrl+B | Cmd+B |
| Navigate tickets | Ctrl+↑/↓ | Cmd+↑/↓ |
