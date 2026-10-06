"""Local browser UI and API; no internet-facing server by default."""
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit
from .core import Sayuri

PAGE = Path(__file__).resolve().parent.parent / "web" / "index.html"

def handler_for(app):
    class Handler(BaseHTTPRequestHandler):
        def json(self, status, data):
            payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def do_GET(self):
            path = urlsplit(self.path).path
            if path == "/":
                content = PAGE.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Security-Policy", "default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; connect-src 'self'")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                self.wfile.write(content)
            elif path == "/api/status":
                self.json(200, app.status())
            elif path == "/api/notes":
                self.json(200, {"notes": app.database.notes()})
            else:
                self.json(404, {"error": "Not found"})

        def do_POST(self):
            if urlsplit(self.path).path != "/api/notes":
                return self.json(404, {"error": "Not found"})
            try:
                size = int(self.headers.get("Content-Length", "-1"))
                if size < 0 or size > 8192:
                    return self.json(413, {"error": "Request too large"})
                body = json.loads(self.rfile.read(size))
                if not isinstance(body, dict):
                    raise ValueError("Invalid payload")
                note = app.database.add(body.get("text"))
            except (ValueError, UnicodeDecodeError):
                return self.json(400, {"error": "Invalid note"})
            self.json(201, note)
    return Handler

def main():
    import os
    app = Sayuri()
    port = int(os.environ.get("SAYURI_PORT", "8765"))
    # Explicit LAN opt-in only: API has no authentication.
    host = "0.0.0.0" if os.environ.get("SAYURI_LAN") == "1" else "127.0.0.1"
    if host != "127.0.0.1":
        raise SystemExit("LAN access is not enabled in this unauthenticated prototype.")
    print(f"SAYURI TSUKISHIRO v0.0.0 — http://127.0.0.1:{port}", flush=True)
    with ThreadingHTTPServer((host, port), handler_for(app)) as server:
        server.serve_forever()

if __name__ == "__main__":
    main()
