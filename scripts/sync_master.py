#!/usr/bin/env python3
"""Đồng bộ ĐSX02 (master) vào cơ sở dữ liệu CN Workforce.

Chạy định kỳ trên máy chủ hoặc bằng tay:
  CN_MASTER_URL=https://dsx02.example.com/api/records python3 scripts/sync_master.py

Chỉ đọc dữ liệu nguồn. Không xóa hồ sơ đã có; hồ sơ thiếu ở master được báo cáo.
"""

import argparse
import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.request
import uuid
from collections import Counter
from datetime import date, datetime
from pathlib import Path
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR))

from import_dsx02 import DRIVE_ID, PLACEHOLDER_CMND, plain, rating  # noqa: E402
from store import (  # noqa: E402
    DISCIPLINE_FIELDS, EXTRA_WORKER_DEFAULTS, KINDS, RELATIONSHIPS, TEAMS, Store, encode, identifier, timestamp,
)

SOURCE_DEFAULT = PROJECT_DIR.parent / "cn-dsx02-main" / "data" / "records.json"
IMAGES_DEFAULT = PROJECT_DIR.parent / "cn-dsx02-main" / "data" / "images.json"
DATA_DEFAULT = PROJECT_DIR / ".local" / "dsx02"
UNIT = "DSX02"
NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL, "https://github.com/TonyHungGemini/cn-workforce/sync")
LOCAL_TZ = ZoneInfo("Asia/Ho_Chi_Minh")
MAX_BYTES = 32 * 1024 * 1024
SYNC_FIELDS = (
    "unit_id", "ten_that", "ten_ho_so", "loai", "to", "phong_o", "so_dt", "cmnd", "ngay_sinh",
    "gioi_tinh", "quan_he", "danh_gia_ky_nang", "danh_gia_dao_duc", "_manuallyRated", "ghi_chu",
    "noi_sinh", "khu_vuc", "phan_cay", "so_bao_hiem", "chi_tiet_noi_o", "dia_chi", "nhom_mau",
    "ghi_chu_ky_luat", "ngay_ky_luat", "hinh_thuc_ky_luat", "trang_thai_ky_luat", "nguoi_lap_bien_ban",
    "chu_phong",
)


def parse_date(value):
    value = plain(value)
    if not value:
        return "", "empty"
    match = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})", value)
    if match:
        day, month, year = (int(part) for part in match.groups())
        try:
            return date(year, month, day).isoformat(), "dd/mm/yyyy"
        except ValueError:
            return "", "invalid"
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        try:
            return date.fromisoformat(value).isoformat(), "iso"
        except ValueError:
            return "", "invalid"
    if "T" in value:
        try:
            moment = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return "", "invalid"
        if moment.tzinfo is not None:
            moment = moment.astimezone(LOCAL_TZ)
        return moment.date().isoformat(), "iso_datetime"
    return "", "invalid"


def load(source, token=""):
    source = str(source)
    parsed = urlsplit(source)
    if parsed.scheme in ("http", "https"):
        if parsed.scheme == "http" and parsed.hostname not in ("127.0.0.1", "localhost"):
            raise SystemExit("Chỉ cho phép HTTPS cho máy chủ master (trừ localhost).")
        headers = {"Accept": "application/json", "User-Agent": "cn-workforce-sync/1.0"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        request = urllib.request.Request(source, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                body = response.read(MAX_BYTES + 1)
        except (urllib.error.URLError, OSError) as error:
            raise SystemExit(f"Không tải được dữ liệu master: {error}") from error
        if len(body) > MAX_BYTES:
            raise SystemExit("Dữ liệu master vượt quá 32 MB.")
    else:
        try:
            body = Path(source).expanduser().read_bytes()
        except OSError as error:
            raise SystemExit(f"Không đọc được tệp master: {error}") from error
    try:
        payload = json.loads(body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as error:
        raise SystemExit(f"JSON master không hợp lệ: {error}") from error
    images = None
    if isinstance(payload, dict):
        images = payload.get("images") if isinstance(payload.get("images"), dict) else None
        payload = payload.get("data")
    if not isinstance(payload, list) or not payload or any(not isinstance(item, dict) for item in payload):
        raise SystemExit("JSON master phải là danh sách hồ sơ không rỗng.")
    return payload, images, hashlib.sha256(body).hexdigest(), len(body)


def read_images(source, token="", embedded=None):
    source = str(source) if source else ""
    if embedded:
        payload = embedded
    elif not source:
        return {}
    elif urlsplit(source).scheme not in ("http", "https") and not Path(source).expanduser().is_file():
        return {}
    else:
        payload, _, _ = load_images(source, token)
    result = {}
    for key, value in payload.items():
        if not isinstance(value, dict):
            continue
        entry = {kind: value[kind] for kind in ("cmnd", "photo")
                 if isinstance(value.get(kind), str) and DRIVE_ID.fullmatch(value[kind])}
        if entry:
            result[str(key)] = entry
    return result


def load_images(source, token=""):
    source = str(source)
    parsed = urlsplit(source)
    if parsed.scheme in ("http", "https"):
        headers = {"Accept": "application/json", "User-Agent": "cn-workforce-sync/1.0"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        request = urllib.request.Request(source, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                body = response.read(MAX_BYTES + 1)
        except (urllib.error.URLError, OSError) as error:
            raise SystemExit(f"Không tải được images.json: {error}") from error
    else:
        try:
            body = Path(source).expanduser().read_bytes()
        except OSError as error:
            raise SystemExit(f"Không đọc được images.json: {error}") from error
    try:
        payload = json.loads(body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as error:
        raise SystemExit(f"images.json không hợp lệ: {error}") from error
    if isinstance(payload, dict) and "images" in payload:
        payload = payload["images"]
    if not isinstance(payload, dict):
        raise SystemExit("images.json phải là đối tượng.")
    return payload, hashlib.sha256(body).hexdigest(), len(body)


def normalize(record, index, leader):
    kind = plain(record.get("loai"))
    if kind not in KINDS:
        kind = "Khác"
    team = plain(record.get("to"))
    if team not in TEAMS:
        team = TEAMS[0]
    gender = plain(record.get("gioi_tinh"))
    if gender not in {"M", "F", ""}:
        gender = ""
    relationship = plain(record.get("quan_he"))
    if relationship == "Chông":
        relationship = "Chồng"
    if not relationship:
        relationship = "Khác"
    if relationship not in RELATIONSHIPS:
        relationship = "Khác"

    birthday, birthday_format = parse_date(record.get("ngay_sinh"))
    discipline_date, discipline_format = parse_date(record.get("ngay_ky_luat"))
    notes = []
    if birthday_format == "invalid":
        notes.append(f"Ngày sinh gốc không hợp lệ: {plain(record.get('ngay_sinh'))}")
    if discipline_format == "invalid":
        notes.append(f"Ngày kỷ luật gốc không hợp lệ: {plain(record.get('ngay_ky_luat'))}")

    cmnd = plain(record.get("cmnd"))
    if cmnd.casefold() in PLACEHOLDER_CMND:
        cmnd = ""
    dependent = kind == "Gia thuộc"
    skill = None if dependent else rating(record.get("danh_gia_ky_nang"))
    ethics = None if dependent else rating(record.get("danh_gia_dao_duc"))
    manually_rated = not dependent and (skill is not None or ethics is not None)
    ghi_chu = plain(record.get("ghi_chu"))
    if notes:
        ghi_chu = " · ".join([ghi_chu, *notes]) if ghi_chu else " · ".join(notes)

    worker = {
        **EXTRA_WORKER_DEFAULTS,
        "id": "", "person_id": "", "unit_id": UNIT,
        "ten_that": plain(record.get("ten_that")), "ten_ho_so": plain(record.get("ten_ho_so")),
        "loai": kind, "to": team, "phong_o": plain(record.get("phong_o")), "so_dt": plain(record.get("so_dt")),
        "cmnd": cmnd, "ngay_sinh": birthday, "gioi_tinh": gender, "quan_he": relationship,
        "danh_gia_ky_nang": skill, "danh_gia_dao_duc": ethics, "_manuallyRated": manually_rated,
        "ghi_chu": ghi_chu, "chu_phong": bool(leader),
        "noi_sinh": plain(record.get("noi_sinh")), "khu_vuc": plain(record.get("khu_vuc")),
        "phan_cay": plain(record.get("phan_cay")), "so_bao_hiem": plain(record.get("so_bao_hiem")),
        "chi_tiet_noi_o": plain(record.get("chi_tiet_noi_o")), "dia_chi": plain(record.get("dia_chi")),
        "nhom_mau": plain(record.get("nhom_mau")).upper(),
        "ghi_chu_ky_luat": plain(record.get("ghi_chu_ky_luat")), "ngay_ky_luat": discipline_date,
        "hinh_thuc_ky_luat": plain(record.get("hinh_thuc_ky_luat")),
        "trang_thai_ky_luat": plain(record.get("trang_thai_ky_luat")),
        "nguoi_lap_bien_ban": plain(record.get("nguoi_lap_bien_ban")),
        "status": "archived" if record.get("deleted") else "active",
        "version": 1, "updated_at": timestamp(),
    }
    if not worker["ten_that"]:
        raise SystemExit(f"Hồ sơ master thứ {index + 1} không có tên.")
    if dependent:
        for field in DISCIPLINE_FIELDS:
            worker[field] = ""
    return worker


def fingerprint(worker):
    return {field: worker.get(field) for field in (*SYNC_FIELDS, "status")}


def sync(source, data_dir, images_source=None, token="", dry_run=False):
    records, embedded_images, source_hash, source_bytes = load(source, token)
    images = read_images(images_source, token, embedded_images) if (images_source or embedded_images) else {}
    store = Store(data_dir, seed=False)
    stats = Counter()
    changes = []

    cmnd_counts = Counter(plain(record.get("cmnd")).casefold() for record in records
                          if plain(record.get("cmnd")).casefold() not in ("", *PLACEHOLDER_CMND))
    duplicate_cmnd = {cmnd for cmnd, count in cmnd_counts.items() if count > 1}
    leaders = set()
    leader_keys = set()
    used_legacy = set()

    with store.transaction(write=not dry_run) as connection:
        existing_rows = connection.execute("SELECT data FROM workers").fetchall()
        existing = {}
        by_cmnd = {}
        by_identity = {}
        legacy = {}
        for row in existing_rows:
            data = json.loads(row["data"])
            existing[data["id"]] = data
        for row in connection.execute("SELECT legacy_id, worker_id FROM legacy_links"):
            legacy[row["legacy_id"]] = row["worker_id"]
        for worker in existing.values():
            if worker.get("cmnd"):
                by_cmnd.setdefault(worker["cmnd"].casefold(), worker["id"])
            by_identity.setdefault((plain(worker.get("ten_that")).casefold(), worker.get("ngay_sinh"),
                                    plain(worker.get("so_dt"))), worker["id"])

        room_counts = Counter(worker["phong_o"] for worker in existing.values()
                              if worker["status"] == "active" and worker.get("phong_o"))
        for record in records:
            room = plain(record.get("phong_o"))
            if room:
                room_counts[room] += 1

        if not dry_run:
            for room, count in room_counts.items():
                connection.execute("INSERT OR IGNORE INTO rooms(id, unit_id, capacity) VALUES (?, ?, ?)",
                                   (room, UNIT, max(6, count)))

            for index, record in enumerate(records):
                legacy_id = record.get("id")
                if type(legacy_id) is not int:
                    stats["invalid_legacy_id"] += 1
                    continue
                room = plain(record.get("phong_o"))
                is_leader = bool(record.get("chu_phong")) and bool(room) and plain(record.get("loai")) != "Gia thuộc"
                if is_leader and legacy_id in leader_keys:
                    is_leader = False
                if is_leader:
                    leader_keys.add(legacy_id)

                worker = normalize(record, index, is_leader)
                cmnd = worker["cmnd"]
                duplicate = bool(cmnd) and cmnd.casefold() in duplicate_cmnd
                # Duplicate legacy IDs in master must not collapse two different people into one profile.
                first_occurrence = legacy_id not in used_legacy
                used_legacy.add(legacy_id)
                worker_id = legacy.get(legacy_id) if first_occurrence else None
                if worker_id is None or worker_id not in existing:
                    if cmnd and not duplicate:
                        worker_id = by_cmnd.get(cmnd.casefold())
                if worker_id is None:
                    worker_id = by_identity.get((worker["ten_that"].casefold(), worker["ngay_sinh"], worker["so_dt"]))
                if worker_id is None:
                    worker.update(id=str(uuid.uuid5(NAMESPACE, f"legacy:{legacy_id}:{index}")),
                                  person_id=store._next_person(connection), version=1, updated_at=timestamp())
                    check = dict(worker, cmnd="") if duplicate else worker
                    store._validate_worker(connection, check)
                    store._insert_worker(connection, worker)
                    worker_id = worker["id"]
                    if duplicate:
                        connection.execute("UPDATE workers SET cmnd_key = NULL WHERE id = ?", (worker["id"],))
                    if first_occurrence:
                        store.link_legacy(connection, legacy_id, worker["id"])
                    store._record(connection, "worker.created", worker["id"], worker["person_id"], worker["unit_id"],
                                  1, "Đồng bộ hồ sơ mới từ ĐSX02.")
                    existing[worker["id"]] = worker
                    if cmnd and not duplicate:
                        by_cmnd[cmnd.casefold()] = worker["id"]
                    if is_leader:
                        leaders.add(worker["id"])
                    stats["created"] += 1
                    changes.append({"legacy_id": legacy_id, "person_id": worker["person_id"], "action": "created"})
                else:
                    previous = existing[worker_id]
                    candidate = dict(previous)
                    for field in SYNC_FIELDS:
                        candidate[field] = worker[field]
                    candidate["status"] = worker["status"]
                    check = dict(candidate, chu_phong=False)
                    if duplicate:
                        check["cmnd"] = ""
                    store._validate_worker(connection, check)
                    if fingerprint(candidate) != fingerprint(previous):
                        candidate["version"] = previous["version"] + 1
                        candidate["updated_at"] = timestamp()
                        store._update_worker(connection, candidate, previous["version"])
                        if duplicate:
                            connection.execute("UPDATE workers SET cmnd_key = NULL WHERE id = ?", (worker_id,))
                        store._record(connection, "worker.updated", candidate["id"], candidate["person_id"],
                                      candidate["unit_id"], candidate["version"], "Đồng bộ thay đổi từ ĐSX02.")
                        existing[worker_id] = candidate
                        stats["updated"] += 1
                        if len(changes) < 200:
                            changes.append({"legacy_id": legacy_id, "person_id": candidate["person_id"],
                                            "action": "updated"})
                        if cmnd and not duplicate:
                            by_cmnd[cmnd.casefold()] = candidate["id"]
                    else:
                        stats["unchanged"] += 1
                    if first_occurrence:
                        connection.execute("INSERT OR REPLACE INTO legacy_links(legacy_id, worker_id) VALUES (?, ?)",
                                           (legacy_id, worker_id))
                    if is_leader:
                        leaders.add(worker_id)

                entry = images.get(str(legacy_id))
                if entry:
                    for kind, file_id in entry.items():
                        store.set_worker_image(connection, worker_id, kind, file_id)
                    stats["with_images"] += 1

            # Master wins: remove leader flags that no longer exist in master, one leader per room.
            if leaders:
                for row in connection.execute("SELECT id, data FROM workers WHERE status = 'active'").fetchall():
                    worker = json.loads(row["data"])
                    if worker.get("chu_phong") and worker["id"] not in leaders:
                        worker["chu_phong"] = False
                        worker["version"] += 1
                        worker["updated_at"] = timestamp()
                        connection.execute("UPDATE workers SET version = ?, updated_at = ?, data = ? WHERE id = ?",
                                           (worker["version"], worker["updated_at"], encode(worker), worker["id"]))
                        stats["leader_cleared"] += 1

            connection.executemany(
                "INSERT OR REPLACE INTO metadata(key, value) VALUES (?, ?)",
                (("dataset", "dsx02"), ("last_sync_at", timestamp()), ("last_sync_source", source),
                 ("last_sync_sha256", source_hash), ("last_sync_records", str(len(records)))),
            )

    return {
        "ok": True, "dry_run": dry_run, "source": source, "source_sha256": source_hash,
        "source_bytes": source_bytes, "records": len(records), "images": len(images),
        **dict(sorted(stats.items())), "changes": changes,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", default=str(SOURCE_DEFAULT))
    parser.add_argument("--images", default=str(IMAGES_DEFAULT))
    parser.add_argument("--data-dir", type=Path, default=DATA_DEFAULT)
    parser.add_argument("--token", default="")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    token = args.token or os.environ.get("CN_MASTER_TOKEN", "")
    report = sync(args.source, args.data_dir, args.images, token, args.dry_run)
    report_path = Path(args.data_dir).expanduser().resolve() / "sync-report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    summary = {key: report.get(key, 0) for key in ("records", "created", "updated", "unchanged", "with_images")}
    print(json.dumps(summary, ensure_ascii=False))
    print(f"Báo cáo: {report_path}")


if __name__ == "__main__":
    main()
