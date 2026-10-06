"""Minimal local-first Sayuri web service (Python standard library only)."""
import json
import os
import secrets
import sqlite3
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("SAYURI_DATA_DIR", str(ROOT / "data")))
MAX_BODY = 16_384


def initialize(data_dir=DATA_DIR):
    data_dir = Path(data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    db = data_dir / "sayuri.sqlite3"
    with sqlite3.connect(db) as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS notes (id INTEGER PRIMARY KEY AUTOINCREMENT, content TEXT NOT NULL, created_at TEXT NOT NULL)")
    token_file = data_dir / ".access_token"
    if not token_file.exists():
        token_file.write_text(secrets.token_urlsafe(32), encoding="utf-8")
        try:
            token_file.chmod(0o600)
        except OSError:
            pass
    return db, token_file.read_text(encoding="utf-8").strip()


def list_notes(db):
    with sqlite3.connect(db) as conn:
        return [dict(zip(("id", "content", "created_at"), row))
                for row in conn.execute("SELECT id, content, created_at FROM notes ORDER BY id DESC LIMIT 100")]


def create_note(db, content):
    if not isinstance(content, str) or not content.strip() or len(content) > 2000:
        raise ValueError("Note must contain 1–2000 characters.")
    timestamp = datetime.now(timezone.utc).isoformat()
    with sqlite3.connect(db) as conn:
        cursor = conn.execute("INSERT INTO notes(content, created_at) VALUES (?, ?)", (content.strip(), timestamp))
        return {"id": cursor.lastrowid, "content": content.strip(), "created_at": timestamp}


def make_handler(db, token):
    class Handler(BaseHTTPRequestHandler):
        def respond(self, code, payload):
            content = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)

        def authorized(self):
            given = self.headers.get("X-Sayuri-Token", "")
            if not secrets.compare_digest(given, token):
                self.respond(401, {"error": "Access token required"})
                return False
            return True

        def do_GET(self):
            path = urlparse(self.path).path
            if path == "/":
                page = (ROOT / "web" / "index.html").read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Security-Policy", "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'self'; base-uri 'none'; form-action 'none'")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.send_header("Content-Length", str(len(page)))
                self.end_headers()
                self.wfile.write(page)
            elif path in ("/api/status", "/api/notes"):
                if not self.authorized():
                    return
                if path == "/api/status":
                    self.respond(200, {"name": "SAYURI TSUKISHIRO", "version": "0.0.1", "database": "ok"})
                else:
                    self.respond(200, {"notes": list_notes(db)})
            else:
                self.respond(404, {"error": "Not found"})

        def do_POST(self):
            if urlparse(self.path).path != "/api/notes":
                return self.respond(404, {"error": "Not found"})
            if not self.authorized():
                return
            try:
                size = int(self.headers.get("Content-Length", "-1"))
                if not 0 <= size <= MAX_BODY:
                    return self.respond(413, {"error": "Invalid request size"})
                data = json.loads(self.rfile.read(size))
                if not isinstance(data, dict):
                    raise ValueError("Expected JSON object")
                note = create_note(db, data.get("content"))
            except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as e:
                return self.respond(400, {"error": str(e)})
            self.respond(201, note)

    return Handler


def main():
    db, token = initialize()
    lan = os.environ.get("SAYURI_LAN") == "1"
    host = "0.0.0.0" if lan else "127.0.0.1"
    port = int(os.environ.get("SAYURI_PORT", "8765"))
    print("\nSAYURI TSUKISHIRO v0.0.1", flush=True)
    print("Access token:", token, flush=True)
    print("Local URL: http://127.0.0.1:%d" % port, flush=True)
    if lan:
        print("LAN enabled: open http://<THIS_COMPUTER_LAN_IP>:%d from another device." % port, flush=True)
        print("Use only on a trusted private network. Never expose the port to the Internet.", flush=True)
    with ThreadingHTTPServer((host, port), make_handler(db, token)) as server:
        server.serve_forever()


if __name__ == "__main__":
    main()
