import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sayuri.core import Sayuri
from sayuri.updater import allowed, github_blob_sha, check, stage, apply_pending


class CoreTests(unittest.TestCase):
    def test_notes_survive_restart(self):
        with tempfile.TemporaryDirectory() as folder:
            a = Sayuri(folder)
            self.assertEqual(a.status()["version"], "0.0.0")
            a.database.add("hello")
            self.assertEqual(Sayuri(folder).database.notes()[0]["text"], "hello")

    def test_update_guards(self):
        for name in ["data/sayuri.db", "../outside", "runtime/python/python.exe",
                     "sayuri/../../data/secrets", "web/../data/a.py"]:
            self.assertFalse(allowed(name), name)
        self.assertTrue(allowed("sayuri/web.py"))

    def test_stage_and_apply_without_touching_database(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            db = Sayuri(root).database
            db.add("unchanged")
            new = b"updated app file"
            files = ["web/index.html"]
            sha = github_blob_sha(new)
            with patch("sayuri.updater.manifest_and_tree", return_value=(files, {"web/index.html": sha}, "TREE")), \
                 patch("sayuri.updater.request_bytes", return_value=new):
                self.assertTrue(check(root=root)["available"])
                result = stage(root=root)
            self.assertTrue(result["restart_required"])
            self.assertTrue(apply_pending(root))
            self.assertEqual((root / "web/index.html").read_bytes(), new)
            self.assertEqual(Sayuri(root).database.notes()[0]["text"], "unchanged")
            self.assertFalse(apply_pending(root))


if __name__ == "__main__":
    unittest.main()
