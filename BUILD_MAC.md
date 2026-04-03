# macOS Release Build

## 1. Environment

- macOS 13+
- Python 3.11 or 3.12 recommended
- Terminal with Accessibility permission if you want global hotkeys

## 2. Run From Source

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
python src/main.py
```

## 3. Permissions

For global hotkeys and simulated copy on macOS, grant the terminal or built app:

- Accessibility
- Input Monitoring if your macOS version asks for it

The app now auto-checks these permissions on launch and opens the matching settings panes when missing, but macOS still requires the user to complete the final approval manually.

Path:

- System Settings -> Privacy & Security -> Accessibility

## 4. Default Hotkeys On macOS

- Main hotkey: `cmd+alt+v`
- Double copy trigger: double `cmd+c`

## 5. Startup

When enabled in settings, the app writes a LaunchAgent plist to:

```text
~/Library/LaunchAgents/com.neatcopy.app.plist
```

## 6. PyInstaller Build

```bash
python -m PyInstaller NeatCopy.spec --clean
```

Release output:

```text
dist/NeatCopy.app
```

## 7. Install On Another Mac

1. Zip `dist/NeatCopy.app` as `NeatCopy-macOS.zip`
2. Copy it to another Mac
3. Drag `NeatCopy.app` into `/Applications`
4. Open it once and approve permissions if macOS prompts
5. In `System Settings -> Privacy & Security`, enable:
   - Accessibility
   - Input Monitoring if required by your macOS version
6. Keep the app in a stable location such as `/Applications`; unsigned or path-changing builds are more likely to require re-approval after updates
