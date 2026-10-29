import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR))

import backup
from drive import DriveError
from store import Store


class FakeDrive:
    def __init__(self, body=b""):
        self.body = body
        self.uploads = 0

    def update(self, file_id, body, content_type):
        self.uploads += 1
        self.file_id = file_id
        self.content_type = content_type
        self.body = body
        return {"id": file_id, "size": str(len(body))}

    def download(self, file_id, limit=None):
        return self.body


class BackupTests(unittest.TestCase):
    def test_flush_uploads_once_per_change(self):
        with tempfile.TemporaryDirectory() as folder:
            store = Store(folder, seed=False)
            drive = FakeDrive()
            worker = backup.DriveBackup(store.db_path, drive, "file-id", logger=lambda *a, **k: None)
            self.assertTrue(worker.flush())
            self.assertEqual(drive.uploads, 1)
            self.assertTrue(drive.body.startswith(backup.SQLITE_HEADER))
            self.assertFalse(worker.flush())
            self.assertEqual(drive.uploads, 1)

    def test_restore_when_database_missing(self):
        with tempfile.TemporaryDirectory() as source:
            store = Store(source, seed=False)
            drive = FakeDrive()
            backup.DriveBackup(store.db_path, drive, "file-id", logger=lambda *a, **k: None).flush()
            with tempfile.TemporaryDirectory() as target:
                restored = backup.restore(target, drive, "file-id")
                self.assertTrue(restored)
                self.assertTrue((Path(target) / "demo.sqlite3").is_file())
                self.assertEqual(Store(target, seed=False).bootstrap()["workers"], [])

    def test_restore_skips_existing_database(self):
        with tempfile.TemporaryDirectory() as folder:
            store = Store(folder, seed=False)
            drive = FakeDrive(b"\x00" * 700)
            self.assertFalse(backup.restore(folder, drive, "file-id"))
            self.assertTrue(store.db_path.is_file())

    def test_restore_rejects_non_database(self):
        with tempfile.TemporaryDirectory() as folder:
            drive = FakeDrive(b"<html>not a database</html>")
            with self.assertRaises(DriveError):
                backup.restore(folder, drive, "file-id")
            self.assertFalse((Path(folder) / "demo.sqlite3").exists())
            self.assertEqual(list(Path(folder).glob("*.restore")), [])


if __name__ == "__main__":
    unittest.main()
