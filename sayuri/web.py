"""Local-only HTTP browser UI and GitHub updater API."""
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit
from .core import Sayuri
from .updater import UpdateError, check, stage, DEFAULT_BRANCH, ALLOWED_BRANCHES

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

        def allowed_host(self):
            # Defend against browser DNS rebinding to localhost.
            if self.headers.get("Host") not in ("127.0.0.1:8765", "localhost:8765",
                  "127.0.0.1:" + str(self.server.server_port), "localhost:" + str(self.server.server_port)):
                self.json(403, {"error": "Local access only"})
                return False
            return True

        def do_GET(self):
            if not self.allowed_host():
                return
            path = urlsplit(self.path).path
            if path == "/":
                content = PAGE.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Security-Policy",
                                 "default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; connect-src 'self'; base-uri 'none'")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                self.wfile.write(content)
            elif path == "/api/status":
                self.json(200, app.status())
            elif path == "/api/notes":
                self.json(200, {"notes": app.database.notes()})
            elif path == "/api/updates/check":
                try:
                    self.json(200, check())
                except UpdateError as exc:
                    self.json(502, {"error": str(exc)})
            else:
                self.json(404, {"error": "Not found"})

        def do_POST(self):
            if not self.allowed_host():
                return
            path = urlsplit(self.path).path
            if path not in ("/api/notes", "/api/updates/stage"):
                return self.json(404, {"error": "Not found"})
            origin = self.headers.get("Origin", "")
            expected = ("http://127.0.0.1:" + str(self.server.server_port),
                        "http://localhost:" + str(self.server.server_port))
            # Prevent cross-origin form and script writes.
            if origin not in expected or self.headers.get("Content-Type", "").split(";")[0].strip() != "application/json":
                return self.json(403, {"error": "Origin or content type rejected"})
            try:
                size = int(self.headers.get("Content-Length", "-1"))
                if size < 0 or size > 8192:
                    return self.json(413, {"error": "Request too large"})
                body = json.loads(self.rfile.read(size))
                if not isinstance(body, dict):
                    raise ValueError("Invalid payload")
                if path == "/api/updates/stage":
                    branch = body.get("branch", DEFAULT_BRANCH)
                    if branch not in ALLOWED_BRANCHES:
                        raise ValueError("Invalid branch")
                    return self.json(200, stage(branch))
                note = app.database.add(body.get("text"))
                return self.json(201, note)
            except UpdateError as exc:
                return self.json(502, {"error": str(exc)})
            except (ValueError, UnicodeDecodeError):
                return self.json(400, {"error": "Invalid request"})

    return Handler

def main():
    import os
    app = Sayuri()
    port = int(os.environ.get("SAYURI_PORT", "8765"))
    if os.environ.get("SAYURI_LAN") == "1":
        raise SystemExit("LAN access is not enabled in this unauthenticated prototype.")
    print(f"SAYURI TSUKISHIRO v0.0.0 — http://127.0.0.1:{port}", flush=True)
    with ThreadingHTTPServer(("127.0.0.1", port), handler_for(app)) as server:
        server.serve_forever()

if __name__ == "__main__":
    main()
