#!/usr/bin/env python3
"""Đẩy snapshot ĐSX02 (records + images) lên máy chủ CN Workforce đã triển khai.

  python3 scripts/push_snapshot.py --url https://cn-workforce.onrender.com

Token lấy từ biến môi trường CN_SYNC_TOKEN, không ghi vào repo.
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit

PROJECT_DIR = Path(__file__).resolve().parents[1]
RECORDS_DEFAULT = PROJECT_DIR.parent / "cn-dsx02-main" / "data" / "records.json"
IMAGES_DEFAULT = PROJECT_DIR.parent / "cn-dsx02-main" / "data" / "images.json"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True, help="URL máy chủ, ví dụ https://cn-workforce.onrender.com")
    parser.add_argument("--source", type=Path, default=RECORDS_DEFAULT)
    parser.add_argument("--images", type=Path, default=IMAGES_DEFAULT)
    parser.add_argument("--token", default=os.environ.get("CN_SYNC_TOKEN", ""))
    args = parser.parse_args()

    parsed = urlsplit(args.url)
    if parsed.scheme != "https" and parsed.hostname not in ("127.0.0.1", "localhost"):
        raise SystemExit("Chỉ cho phép HTTPS (trừ localhost).")
    if len(args.token) < 24:
        raise SystemExit("Thiếu CN_SYNC_TOKEN (tối thiểu 24 ký tự).")
    records = json.loads(args.source.read_text(encoding="utf-8"))
    images = json.loads(args.images.read_text(encoding="utf-8")) if args.images.is_file() else {}
    if isinstance(images, dict) and "images" in images:
        images = images["images"]
    payload = json.dumps({"records": records, "images": images}, ensure_ascii=False).encode("utf-8")
    if len(payload) > 32 * 1024 * 1024:
        raise SystemExit("Snapshot vượt quá 32 MB.")
    request = urllib.request.Request(
        args.url.rstrip("/") + "/api/v1/admin/sync", data=payload, method="POST",
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {args.token}",
                 "User-Agent": "cn-workforce-push/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            result = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", "replace")[:300]
        raise SystemExit(f"Máy chủ từ chối ({error.code}): {detail}") from error
    except (urllib.error.URLError, OSError) as error:
        raise SystemExit(f"Không gửi được snapshot: {error}") from error
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
