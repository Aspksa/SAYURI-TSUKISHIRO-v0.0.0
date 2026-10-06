import io
import tempfile
import unittest
from pathlib import Path

from sayuri.disk import Disk, DiskError


class DiskTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.disk = Disk(Path(self.tmp.name) / "disk")

    def put(self, folder, name, data=b"data"):
        return self.disk.upload(folder, name, io.BytesIO(data), len(data))

    def test_upload_and_conflict_naming(self):
        self.assertEqual(self.put("", "a.txt")["name"], "a.txt")
        self.assertEqual(self.put("", "a.txt")["name"], "a (1).txt")
        self.assertEqual(self.put("", "a.txt")["name"], "a (2).txt")

    def test_truncated_upload_leaves_nothing(self):
        with self.assertRaises(DiskError):
            self.disk.upload("", "x.bin", io.BytesIO(b"abc"), 10)
        self.assertEqual(self.disk.list("")["items"], [])
        self.assertEqual(list(self.disk.tmp.iterdir()), [])

    def test_path_traversal_rejected(self):
        for bad in ["..", "../x", "a/../../x", "a\\b", "C:/x", "con", "x/NUL.txt", "a:b"]:
            with self.assertRaises(DiskError, msg=bad):
                self.disk.resolve(bad)
        for bad in ["..", "a/b", "", "x.", "CON", "q?"]:
            with self.assertRaises(DiskError, msg=bad):
                self.put("", bad)

    def test_folders_sorted_first(self):
        self.put("", "b.txt")
        self.disk.mkdir("", "Zeta")
        names = [i["name"] for i in self.disk.list("")["items"]]
        self.assertEqual(names, ["Zeta", "b.txt"])
        with self.assertRaises(FileExistsError):
            self.disk.mkdir("", "Zeta")

    def test_rename(self):
        self.put("", "a.txt")
        self.put("", "b.txt")
        with self.assertRaises(FileExistsError):
            self.disk.rename("a.txt", "b.txt")
        self.assertEqual(self.disk.rename("a.txt", "A.txt")["name"], "A.txt")

    def test_trash_restore_and_empty(self):
        self.disk.mkdir("", "docs")
        self.put("docs", "n.txt", b"hello")
        self.disk.delete("docs")
        self.assertEqual(self.disk.list("")["items"], [])
        item = self.disk.trash_items()[0]
        self.assertEqual((item["name"], item["type"], item["size"]), ("docs", "dir", 5))
        self.disk.mkdir("", "docs")  # name taken meanwhile
        self.assertEqual(self.disk.restore(item["id"])["name"], "docs (1)")
        self.assertEqual((self.disk.files / "docs (1)" / "n.txt").read_bytes(), b"hello")
        self.assertEqual(self.disk.trash_items(), [])
        self.disk.delete("docs")
        self.assertEqual(self.disk.empty_trash(), 1)
        self.assertEqual(self.disk.trash_items(), [])

    def test_root_and_bad_trash_id_protected(self):
        with self.assertRaises(DiskError):
            self.disk.delete("")
        for bad in ["../x", "z" * 32, None]:
            with self.assertRaises((DiskError, FileNotFoundError)):
                self.disk.restore(bad)


if __name__ == "__main__":
    unittest.main()
