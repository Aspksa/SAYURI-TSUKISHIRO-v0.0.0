"""Local-only HTTP browser UI and GitHub updater API."""
import json
import shutil
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, urlsplit
from .core import Sayuri
from .disk import DiskError, preview_type
from .updater import UpdateError, check, stage, DEFAULT_BRANCH, ALLOWED_BRANCHES

PAGE = Path(__file__).resolve().parent.parent / "web" / "index.html"
JSON_ROUTES = ("/api/notes", "/api/updates/stage", "/api/disk/mkdir", "/api/disk/rename",
               "/api/disk/delete", "/api/disk/restore", "/api/disk/trash/empty")
UPLOAD_ROUTE = "/api/disk/upload"

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

        def disk_get(self, path, query):
            arg = query.get("path", [""])[0]
            try:
                if path == "/api/disk/list":
                    return self.json(200, app.disk.list(arg))
                if path == "/api/disk/usage":
                    return self.json(200, app.disk.usage())
                if path == "/api/disk/trash":
                    return self.json(200, {"items": app.disk.trash_items()})
                if path == "/api/disk/file":
                    return self.send_file(app.disk.file(arg), query.get("inline") == ["1"])
            except DiskError as exc:
                return self.json(400, {"error": str(exc)})
            except FileNotFoundError:
                return self.json(404, {"error": "Не найдено"})
            self.json(404, {"error": "Not found"})

        def send_file(self, file, inline):
            mime = preview_type(file) if inline else None
            with open(file, "rb") as source:
                self.send_response(200)
                self.send_header("Content-Type", mime or "application/octet-stream")
                self.send_header("Content-Length", str(file.stat().st_size))
                self.send_header("Content-Disposition",
                                 ("inline" if mime else "attachment") + "; filename*=UTF-8''" + quote(file.name))
                self.send_header("Content-Security-Policy", "default-src 'none'; sandbox")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                try:
                    shutil.copyfileobj(source, self.wfile, 1024 * 1024)
                except (BrokenPipeError, ConnectionResetError):
                    pass  # the browser cancelled the download

        def disk_upload(self, query):
            self.close_connection = True  # never reuse a socket with an unread body
            try:
                size = int(self.headers.get("Content-Length", "-1"))
                entry = app.disk.upload(query.get("path", [""])[0], query.get("name", [""])[0], self.rfile, size)
                return self.json(201, entry)
            except DiskError as exc:
                return self.json(400, {"error": str(exc)})
            except FileNotFoundError:
                return self.json(404, {"error": "Папка не найдена"})
            except ValueError:
                return self.json(400, {"error": "Invalid request"})
            except OSError:
                return self.json(500, {"error": "Ошибка записи файла"})

        def disk_post(self, path, body):
            disk = app.disk
            if path == "/api/disk/mkdir":
                return self.json(201, disk.mkdir(body.get("path", ""), body.get("name")))
            if path == "/api/disk/rename":
                return self.json(200, disk.rename(body.get("path"), body.get("name")))
            if path == "/api/disk/delete":
                paths = body.get("paths")
                if not isinstance(paths, list) or not 1 <= len(paths) <= 500:
                    raise DiskError("Некорректный список файлов")
                return self.json(200, {"deleted": [disk.delete(p) for p in paths]})
            if path == "/api/disk/restore":
                return self.json(200, disk.restore(body.get("id")))
            return self.json(200, {"removed": disk.empty_trash()})

        def do_GET(self):
            if not self.allowed_host():
                return
            parts = urlsplit(self.path)
            path = parts.path
            if path.startswith("/api/disk/"):
                return self.disk_get(path, parse_qs(parts.query, keep_blank_values=True))
            if path == "/":
                content = PAGE.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Security-Policy",
                                 "default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; connect-src 'self'; img-src 'self'; base-uri 'none'")
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
            parts = urlsplit(self.path)
            path = parts.path
            if path not in JSON_ROUTES and path != UPLOAD_ROUTE:
                return self.json(404, {"error": "Not found"})
            origin = self.headers.get("Origin", "")
            expected = ("http://127.0.0.1:" + str(self.server.server_port),
                        "http://localhost:" + str(self.server.server_port))
            wanted = "application/octet-stream" if path == UPLOAD_ROUTE else "application/json"
            # Prevent cross-origin form and script writes.
            if origin not in expected or self.headers.get("Content-Type", "").split(";")[0].strip() != wanted:
                return self.json(403, {"error": "Origin or content type rejected"})
            if path == UPLOAD_ROUTE:
                return self.disk_upload(parse_qs(parts.query, keep_blank_values=True))
            try:
                size = int(self.headers.get("Content-Length", "-1"))
                if size < 0 or size > 65536:
                    return self.json(413, {"error": "Request too large"})
                body = json.loads(self.rfile.read(size))
                if not isinstance(body, dict):
                    raise ValueError("Invalid payload")
                if path == "/api/updates/stage":
                    branch = body.get("branch", DEFAULT_BRANCH)
                    if branch not in ALLOWED_BRANCHES:
                        raise ValueError("Invalid branch")
                    return self.json(200, stage(branch))
                if path.startswith("/api/disk/"):
                    return self.disk_post(path, body)
                note = app.database.add(body.get("text"))
                return self.json(201, note)
            except UpdateError as exc:
                return self.json(502, {"error": str(exc)})
            except DiskError as exc:
                return self.json(400, {"error": str(exc)})
            except (ValueError, UnicodeDecodeError):
                return self.json(400, {"error": "Invalid request"})
            except FileNotFoundError:
                return self.json(404, {"error": "Не найдено"})
            except FileExistsError:
                return self.json(409, {"error": "Файл или папка с таким именем уже есть"})
            except OSError:
                return self.json(500, {"error": "Ошибка файловой системы (файл может быть занят)"})

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
