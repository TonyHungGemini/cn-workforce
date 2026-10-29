"""Sao lưu và khôi phục SQLite qua Google Drive cho máy chủ không có ổ đĩa bền.

Gói Free của Render xóa toàn bộ tệp cục bộ mỗi lần dịch vụ ngủ hoặc khởi động lại.
Ứng dụng giữ một tệp `cn-workforce.sqlite3` trên Drive (do chủ thư mục sở hữu,
service account được cấp quyền sửa) và ghi đè nội dung tệp đó định kỳ.
"""

import hashlib
import os
import sqlite3
import threading
from pathlib import Path

from drive import Drive, DriveError

DEFAULT_INTERVAL = 60
SQLITE_HEADER = b"SQLite format 3\x00"


def backup_file_id():
    return os.environ.get("CN_BACKUP_FILE_ID", "").strip()


def backup_interval():
    raw = os.environ.get("CN_BACKUP_INTERVAL", "").strip()
    if raw.isdigit() and int(raw) >= 10:
        return int(raw)
    return DEFAULT_INTERVAL


def _snapshot_bytes(db_path):
    """Bản sao nhất quán của cơ sở dữ liệu đang chạy, kể cả khi có giao dịch khác."""
    temporary = db_path.with_suffix(".backup")
    source = sqlite3.connect(str(db_path), timeout=15)
    destination = sqlite3.connect(str(temporary))
    try:
        source.backup(destination)
    finally:
        destination.close()
        source.close()
    try:
        return temporary.read_bytes()
    finally:
        temporary.unlink(missing_ok=True)


def restore(data_dir, drive, file_id):
    """Khôi phục cơ sở dữ liệu từ Drive khi ổ đĩa cục bộ còn trống."""
    database = Path(data_dir) / "demo.sqlite3"
    if database.is_file() and database.stat().st_size > 0:
        return False
    body = drive.download(file_id)
    if not body.startswith(SQLITE_HEADER) or len(body) < len(SQLITE_HEADER) + 512:
        raise DriveError("Tệp sao lưu trên Drive không phải cơ sở dữ liệu hợp lệ.")
    temporary = database.with_suffix(".restore")
    try:
        temporary.write_bytes(body)
        check = sqlite3.connect(str(temporary))
        try:
            result = check.execute("PRAGMA quick_check").fetchone()
        finally:
            check.close()
        if not result or result[0] != "ok":
            raise DriveError("Bản sao lưu trên Drive bị hỏng.")
        temporary.replace(database)
    finally:
        temporary.unlink(missing_ok=True)
    return True


class DriveBackup:
    """Đẩy bản sao SQLite lên Drive khi nội dung thay đổi."""

    def __init__(self, db_path, drive, file_id, interval=DEFAULT_INTERVAL, logger=print):
        self.db_path = Path(db_path)
        self.drive = drive
        self.file_id = file_id
        self.interval = interval
        self.logger = logger
        self.last_digest = None
        self.last_error = ""
        self._lock = threading.Lock()
        self._stopped = threading.Event()
        self._thread = None

    def flush(self):
        with self._lock:
            body = _snapshot_bytes(self.db_path)
            digest = hashlib.sha256(body).hexdigest()
            if digest == self.last_digest:
                return False
            self.drive.update(self.file_id, body, "application/x-sqlite3")
            self.last_digest = digest
            self.last_error = ""
            return True

    def _run(self):
        while not self._stopped.wait(self.interval):
            try:
                if self.flush():
                    self.logger("[backup] đã cập nhật bản sao lưu trên Drive", flush=True)
            except (DriveError, OSError, sqlite3.Error) as error:
                message = str(error)
                if message != self.last_error:
                    self.last_error = message
                    self.logger(f"[backup] chưa ghi được bản sao lưu: {message}", flush=True)

    def start(self):
        if self._thread is not None:
            return
        self._thread = threading.Thread(target=self._run, name="drive-backup", daemon=True)
        self._thread.start()

    def stop(self):
        self._stopped.set()
        if self._thread is not None:
            self._thread.join(timeout=5)
            self._thread = None
        try:
            self.flush()
        except (DriveError, OSError, sqlite3.Error) as error:
            self.logger(f"[backup] lần ghi cuối thất bại: {error}", flush=True)
