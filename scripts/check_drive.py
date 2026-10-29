"""Kiểm tra service account có đọc được ảnh Drive trước khi đưa khoá lên Render."""
import os
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from drive import Drive, DriveError  # noqa: E402


def sample_file_id():
    data_dir = Path(os.environ.get("CN_DATA_DIR", ROOT / ".local" / "dsx02"))
    database = data_dir / "demo.sqlite3"
    if not database.is_file():
        return None
    try:
        with sqlite3.connect(database) as connection:
            row = connection.execute(
                "SELECT drive_id FROM worker_images ORDER BY updated_at DESC LIMIT 1").fetchone()
    except sqlite3.DatabaseError:
        return None
    return row[0] if row else None


def main():
    file_id = sys.argv[1] if len(sys.argv) > 1 else sample_file_id()
    if not file_id:
        print("Cách dùng: CN_DRIVE_CREDENTIALS=/duong/dan/key.json "
              "python3 scripts/check_drive.py <DRIVE_FILE_ID>")
        return 2
    try:
        drive = Drive.from_env(ROOT / ".local" / "image-cache")
    except DriveError as error:
        print(f"LỖI: {error}")
        return 1
    if drive is None:
        print("Chưa có khoá: đặt CN_DRIVE_CREDENTIALS trỏ tới tệp JSON service account.")
        return 2
    try:
        body, content_type = drive.fetch(file_id)
    except DriveError as error:
        print(f"LỖI: {error}")
        return 1
    print(f"OK: đọc được {len(body)} byte ({content_type}), mã tệp {file_id}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
