# SAYURI TSUKISHIRO v0.0.0 — portable Windows launcher

This is the **local-only prototype**. No Cloud.ru, no cloud accounts, no internet dependency at runtime.

## Directory layout
- `sayuri/` — application core, SQLite storage, and local web server
- `web/` — responsive HTML interface
- `data/` — generated at startup, containing `sayuri.db` and SQLite journal files
- `SAYURITSUKISHIRO.bat` — Windows launcher from any writable drive/folder
- `runtime/python/python.exe` — optional **Windows-compatible portable Python runtime** (not bundled)

## Launch on Windows
1. Download the branch ZIP and extract **all** files to a **writable** folder or USB drive.
2. Install Python 3, or place a compatible Windows Python distribution in `runtime/python/`, including required standard libraries and SQLite support.
3. Run `SAYURITSUKISHIRO.bat`.
4. Open `http://127.0.0.1:8765` locally in a browser. The BAT also tries to open it automatically.
5. Stop with Ctrl+C in the console before ejecting the USB drive.

The launcher changes directory to its own location: no fixed C:/ drive path. The USB drive must remain connected while the app runs. This is not a standalone executable; without a bundled runtime, Python must be installed on the host.

**Security:** Only `127.0.0.1` is supported in this prototype. Other phones/computers cannot yet connect; LAN/internet access needs authentication and HTTPS or another secure transport before enabling it.

Test: `python -m unittest discover -s tests -v`.
