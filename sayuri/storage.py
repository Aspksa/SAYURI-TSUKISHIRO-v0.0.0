"""SQLite local database. Data lives beside the program."""
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

class Database:
    def __init__(self, directory):
        root = Path(directory)
        root.mkdir(parents=True, exist_ok=True)
        self.path = root / "sayuri.db"
        with self.connect() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("CREATE TABLE IF NOT EXISTS notes (id INTEGER PRIMARY KEY, text TEXT NOT NULL, created TEXT NOT NULL)")

    @contextmanager
    def connect(self):
        # sqlite3's own context manager commits but never closes; close explicitly
        # so the database file is released (Windows file locks, safe USB removal).
        conn = sqlite3.connect(self.path, timeout=10)
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def notes(self):
        with self.connect() as conn:
            return [dict(zip(("id", "text", "created"), row)) for row in
                    conn.execute("SELECT id, text, created FROM notes ORDER BY id DESC LIMIT 100")]

    def add(self, text):
        if not isinstance(text, str) or not (1 <= len(text.strip()) <= 2000):
            raise ValueError("Text must be 1 to 2000 characters")
        created = datetime.now(timezone.utc).isoformat()
        with self.connect() as conn:
            cursor = conn.execute("INSERT INTO notes(text, created) VALUES(?,?)", (text.strip(), created))
            return {"id": cursor.lastrowid, "text": text.strip(), "created": created}
