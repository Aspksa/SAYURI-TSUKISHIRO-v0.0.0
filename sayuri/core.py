"""Core initialization and local lifecycle."""
from pathlib import Path
from .disk import Disk
from .storage import Database

ROOT = Path(__file__).resolve().parent.parent

class Sayuri:
    def __init__(self, root=ROOT):
        self.root = Path(root)
        self.database = Database(self.root / "data")
        self.disk = Disk(self.root / "data" / "disk")

    def status(self):
        return {"name": "SAYURI TSUKISHIRO", "version": "0.0.0", "database": "ready", "mode": "local"}
