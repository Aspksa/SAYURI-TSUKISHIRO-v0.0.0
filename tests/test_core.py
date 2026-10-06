import tempfile
import unittest
from pathlib import Path
from sayuri.app import initialize, create_note, list_notes


class CoreTests(unittest.TestCase):
    def test_database_and_token_persist(self):
        with tempfile.TemporaryDirectory() as folder:
            db, token = initialize(folder)
            self.assertTrue(Path(db).exists())
            self.assertEqual(len(token) > 20, True)
            self.assertEqual(initialize(folder)[1], token)
            self.assertEqual(list_notes(db), [])
            note = create_note(db, "hello")
            self.assertEqual(note["content"], "hello")
            self.assertEqual(list_notes(db)[0]["content"], "hello")
            with self.assertRaises(ValueError):
                create_note(db, " ")


if __name__ == "__main__":
    unittest.main()
