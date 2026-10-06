import tempfile
import unittest
from sayuri.core import Sayuri

class TestCore(unittest.TestCase):
    def test_local_db(self):
        with tempfile.TemporaryDirectory() as folder:
            app = Sayuri(folder)
            self.assertEqual(app.status()["version"], "0.0.0")
            self.assertEqual(app.database.notes(), [])
            self.assertEqual(app.database.add("Test")["text"], "Test")
            self.assertEqual(Sayuri(folder).database.notes()[0]["text"], "Test")
            with self.assertRaises(ValueError):
                app.database.add("")

if __name__ == "__main__":
    unittest.main()
