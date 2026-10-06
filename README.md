# SAYURI TSUKISHIRO · v0.0.1 (prototype)

Local-first web core with SQLite notes, a responsive web UI, and no third-party Python dependencies.

## Requirements

Python 3.9+ and a Windows, Linux, or macOS computer to host the server.

## Windows

1. Download/clone this repository and extract it.
2. Double-click **SAYURITSUKISHIRO.bat**.
3. Read the **access token** printed in the console.
4. Open **http://127.0.0.1:8765** on the Windows computer, enter the token, and connect.
5. For phone/tablet/other PCs connected to the **same trusted Wi-Fi/LAN**, find the host IPv4 address using `ipconfig` and open `http://HOST_IPV4:8765`. Enter the same token. If Windows Firewall asks, allow access on **Private** networks only.

Keep the BAT window open while using Sayuri. To stop, press Ctrl+C.

## Linux/macOS

Run `sh start.sh`, then use the same browser instructions. For local-only access run `SAYURI_LAN=0 sh start.sh`.

## Configuration

- `SAYURI_LAN=1` listens on all interfaces (the BAT and shell launcher defaults). Use **only on trusted private networks**.
- `SAYURI_LAN=0` listens on localhost only.
- `SAYURI_PORT=8765` changes the port.
- `SAYURI_DATA_DIR` changes the SQLite/token directory; default: `data/`.

Each installation generates its own access token in `data/.access_token` and saves notes in `data/sayuri.sqlite3`. **Never commit or share the token or database**.

**Security scope:** This is an early local-LAN prototype, using HTTP (not TLS). The token protects API access but traffic is not encrypted. Do **not** port-forward, expose the server to the public internet, or use on untrusted Wi-Fi. For access from anywhere on the internet use a properly secured HTTPS service or private VPN later.

**Device support:** The `.bat` launcher works only on Windows; any modern browser can use the web UI when it can reach a running Sayuri server. A powered-off host cannot serve the app.

## Run tests

```sh
python -m unittest discover -s tests -v
```

## API

- `GET /api/status`
- `GET /api/notes`
- `POST /api/notes` with JSON `{"content":"..."}`

API calls require header `X-Sayuri-Token`.

## Roadmap

This is the initial web/storage foundation, **not** an AI assistant or production cloud deployment. Next: identity/users, backups, modular skills, authentication hardening, HTTPS deployment and automated CI.
