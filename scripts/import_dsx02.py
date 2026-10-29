#!/usr/bin/env python3
"""Nhập toàn bộ hồ sơ ĐSX02 vào một SQLite cục bộ, không đưa dữ liệu lên git."""

import argparse
import hashlib
import json
import re
import sys
import unicodedata
import uuid
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR))

from store import (  # noqa: E402
    DISCIPLINE_FIELDS, EXTRA_WORKER_DEFAULTS, KINDS, RELATIONSHIPS, TEAMS, Store, encode, identifier, timestamp,
)

SOURCE_DEFAULT = PROJECT_DIR.parent / "cn-dsx02-main" / "data" / "records.json"
IMAGES_DEFAULT = PROJECT_DIR.parent / "cn-dsx02-main" / "data" / "images.json"
DATA_DEFAULT = PROJECT_DIR / ".local" / "dsx02"
UNIT = "DSX02"
NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL, "https://github.com/TonyHungGemini/cn-workforce/dsx02")
LOCAL_TZ = ZoneInfo("Asia/Ho_Chi_Minh")
PLACEHOLDER_CMND = {"không có", "khong co"}
DRIVE_ID = re.compile(r"[A-Za-z0-9_-]{10,100}")


def plain(value):
    if not isinstance(value, str):
        return ""
    return unicodedata.normalize("NFC", value.strip())


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


def rating(value):
    return value if type(value) is int and 1 <= value <= 5 else None


def read_records(source):
    try:
        records = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise SystemExit(f"Không đọc được dữ liệu nguồn: {error}") from error
    if not isinstance(records, list) or not records:
        raise SystemExit("Dữ liệu nguồn phải là danh sách hồ sơ không rỗng.")
    if any(not isinstance(record, dict) for record in records):
        raise SystemExit("Dữ liệu nguồn có phần tử không phải hồ sơ.")
    return records


def read_images(source):
    if source is None:
        return {}
    try:
        catalog = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(catalog, dict):
        return {}
    result = {}
    for key, value in catalog.items():
        if not isinstance(value, dict):
            continue
        entry = {}
        for kind in ("cmnd", "photo"):
            file_id = value.get(kind)
            if isinstance(file_id, str) and DRIVE_ID.fullmatch(file_id):
                entry[kind] = file_id
        if entry:
            result[str(key)] = entry
    return result


def build_workers(records, store, connection, import_time, images=None):
    images = images or {}
    stats = Counter()
    stats["image_map_entries"] = len(images)
    used_images = set()
    seen_cmnd = set()
    seen_legacy_ids = Counter()
    leaders = set()
    rooms = Counter(plain(record.get("phong_o")) for record in records if plain(record.get("phong_o")))
    for room, count in sorted(rooms.items()):
        connection.execute("INSERT INTO rooms(id, unit_id, capacity) VALUES (?, ?, ?)",
                           (room, UNIT, max(6, count)))
    known_rooms = set(rooms)
    workers = []

    for index, record in enumerate(records):
        legacy_id = record.get("id")
        seen_legacy_ids[legacy_id] += 1
        kind = plain(record.get("loai"))
        if kind not in KINDS:
            stats["unknown_kind"] += 1
            kind = "Khác"
        team = plain(record.get("to"))
        if team not in TEAMS:
            stats["unknown_team"] += 1
            team = TEAMS[0]
        gender = plain(record.get("gioi_tinh"))
        if gender not in {"M", "F", ""}:
            stats["unknown_gender"] += 1
            gender = ""

        relationship = plain(record.get("quan_he"))
        if relationship == "Chông":
            relationship = "Chồng"
            stats["relationship_typo"] += 1
        if not relationship:
            relationship = "Khác"
            stats["relationship_empty"] += 1
        if relationship not in RELATIONSHIPS:
            stats["unknown_relationship"] += 1
            relationship = "Khác"

        birthday, birthday_format = parse_date(record.get("ngay_sinh"))
        stats[f"birthday_{birthday_format}"] += 1
        discipline_date, discipline_format = parse_date(record.get("ngay_ky_luat"))
        if discipline_format not in {"empty", "iso"}:
            stats[f"discipline_date_{discipline_format}"] += 1
        notes = []
        if birthday_format == "invalid":
            notes.append(f"Ngày sinh gốc không hợp lệ: {plain(record.get('ngay_sinh'))}")
        if discipline_format == "invalid":
            notes.append(f"Ngày kỷ luật gốc không hợp lệ: {plain(record.get('ngay_ky_luat'))}")

        cmnd = plain(record.get("cmnd"))
        if cmnd.casefold() in PLACEHOLDER_CMND:
            cmnd = ""
            stats["placeholder_cmnd"] += 1
        duplicate_cmnd = bool(cmnd) and cmnd.casefold() in seen_cmnd
        if duplicate_cmnd:
            stats["duplicate_cmnd"] += 1
        if cmnd:
            seen_cmnd.add(cmnd.casefold())

        room = plain(record.get("phong_o"))
        leader = bool(record.get("chu_phong"))
        if leader and not room:
            leader = False
            stats["leader_without_room"] += 1
        if leader and kind == "Gia thuộc":
            leader = False
            stats["dependent_leader_cleared"] += 1
        if leader and room in leaders:
            leader = False
            stats["duplicate_room_leader"] += 1
        if leader:
            leaders.add(room)

        dependent = kind == "Gia thuộc"
        skill = None if dependent else rating(record.get("danh_gia_ky_nang"))
        ethics = None if dependent else rating(record.get("danh_gia_dao_duc"))
        manually_rated = not dependent and (skill is not None or ethics is not None)
        dependent_discipline = dependent and any(plain(record.get(field)) for field in DISCIPLINE_FIELDS)
        if dependent and (rating(record.get("danh_gia_ky_nang")) is not None
                          or rating(record.get("danh_gia_dao_duc")) is not None):
            stats["dependent_ratings_cleared"] += 1
        if dependent_discipline:
            stats["dependent_discipline_cleared"] += 1

        ghi_chu = plain(record.get("ghi_chu"))
        if notes:
            ghi_chu = " · ".join([ghi_chu, *notes]) if ghi_chu else " · ".join(notes)

        worker = {
            **EXTRA_WORKER_DEFAULTS,
            "id": str(uuid.uuid5(NAMESPACE, f"legacy:{legacy_id}:{index}")),
            "person_id": f"CN-{index + 1:04d}",
            "unit_id": UNIT,
            "ten_that": plain(record.get("ten_that")),
            "ten_ho_so": plain(record.get("ten_ho_so")),
            "loai": kind,
            "to": team,
            "phong_o": room,
            "so_dt": plain(record.get("so_dt")),
            "cmnd": cmnd,
            "ngay_sinh": birthday,
            "gioi_tinh": gender,
            "quan_he": relationship,
            "danh_gia_ky_nang": skill,
            "danh_gia_dao_duc": ethics,
            "_manuallyRated": manually_rated,
            "ghi_chu": ghi_chu,
            "chu_phong": leader,
            "noi_sinh": plain(record.get("noi_sinh")),
            "khu_vuc": plain(record.get("khu_vuc")),
            "phan_cay": plain(record.get("phan_cay")),
            "so_bao_hiem": plain(record.get("so_bao_hiem")),
            "chi_tiet_noi_o": plain(record.get("chi_tiet_noi_o")),
            "dia_chi": plain(record.get("dia_chi")),
            "nhom_mau": plain(record.get("nhom_mau")).upper(),
            "ghi_chu_ky_luat": plain(record.get("ghi_chu_ky_luat")),
            "ngay_ky_luat": discipline_date,
            "hinh_thuc_ky_luat": plain(record.get("hinh_thuc_ky_luat")),
            "trang_thai_ky_luat": plain(record.get("trang_thai_ky_luat")),
            "nguoi_lap_bien_ban": plain(record.get("nguoi_lap_bien_ban")),
            "status": "active" if not record.get("deleted") else "archived",
            "version": 1,
            "updated_at": import_time,
        }
        if not worker["ten_that"]:
            raise SystemExit(f"Hồ sơ nguồn thứ {index + 1} không có tên.")
        if len(worker["dia_chi"]) > 500 or len(worker["noi_sinh"]) > 500:
            stats["long_text_overflow"] += 1
        if len(worker["dia_chi"]) > 200 or len(worker["noi_sinh"]) > 200:
            stats["long_text_over_200"] += 1

        actual_cmnd = worker["cmnd"]
        actual_leader = worker["chu_phong"]
        if duplicate_cmnd:
            worker["cmnd"] = ""
        if actual_leader:
            worker["chu_phong"] = False
        store._validate_worker(connection, worker)
        worker["cmnd"] = actual_cmnd
        worker["chu_phong"] = actual_leader

        cmnd_key = None if duplicate_cmnd or not actual_cmnd else actual_cmnd.casefold()
        connection.execute(
            "INSERT INTO workers(id, person_id, unit_id, cmnd_key, status, version, updated_at, data) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (worker["id"], worker["person_id"], worker["unit_id"], cmnd_key, worker["status"],
             worker["version"], worker["updated_at"], encode(worker)),
        )
        connection.execute(
            "INSERT INTO audit(id, action, entity_id, actor, at, summary) VALUES (?, 'worker.created', ?, ?, ?, ?)",
            (identifier(), worker["id"], "Nhập dữ liệu ĐSX02", import_time, "Nhập hồ sơ từ dữ liệu ĐSX02."),
        )
        connection.execute(
            "INSERT INTO outbox(event_id, entity_id, person_id, unit_id, entity_version, event_type, occurred_at, status) "
            "VALUES (?, ?, ?, ?, 1, 'worker.created', ?, 'pending')",
            (identifier(), worker["id"], worker["person_id"], worker["unit_id"], import_time),
        )

        if type(legacy_id) is int:
            connection.execute("INSERT OR IGNORE INTO legacy_links(legacy_id, worker_id) VALUES (?, ?)",
                               (legacy_id, worker["id"]))
            entry = images.get(str(legacy_id), {})
            if entry:
                used_images.add(str(legacy_id))
                for kind, file_id in entry.items():
                    store.set_worker_image(connection, worker["id"], kind, file_id)
                    stats[f"with_{kind}_image"] += 1

        stats["imported"] += 1
        stats[f"kind_{worker['loai']}"] += 1
        stats["with_cmnd" if actual_cmnd else "missing_cmnd"] += 1
        stats["with_phone" if worker["so_dt"] else "without_phone"] += 1
        stats["with_blood" if worker["nhom_mau"] else "without_blood"] += 1
        stats["room_leader"] += bool(actual_leader)
        if worker["status"] != "active":
            stats["archived"] += 1

        workers.append({
            "legacy_id": legacy_id,
            "source_index": index,
            "person_id": worker["person_id"],
            "id": worker["id"],
            "room": room,
        })

    stats["legacy_ids"] = len(seen_legacy_ids)
    stats["duplicate_legacy_id_records"] = sum(count - 1 for count in seen_legacy_ids.values() if count > 1)
    stats["rooms"] = len(known_rooms)
    stats["image_map_unmatched"] = len(set(images) - used_images)
    return workers, rooms, stats


def write_database(source, data_dir, replace, images_source=None):
    data_dir = data_dir.expanduser().resolve()
    data_dir.mkdir(parents=True, exist_ok=True)
    db_path = data_dir / "demo.sqlite3"
    if db_path.exists():
        if not replace:
            raise SystemExit(f"Đã có cơ sở dữ liệu tại {db_path}. Dùng --force để thay thế.")
        db_path.unlink()

    records = read_records(source)
    images = read_images(images_source)
    source_bytes = source.read_bytes()
    source_hash = hashlib.sha256(source_bytes).hexdigest()
    import_time = timestamp()

    store = Store(data_dir, seed=False)
    try:
        with store.transaction() as connection:
            workers, rooms, stats = build_workers(records, store, connection, import_time, images)
            connection.execute("UPDATE counters SET value = ? WHERE name = 'person'", (len(workers),))
            connection.executemany(
                "INSERT OR REPLACE INTO metadata(key, value) VALUES (?, ?)",
                (("dataset", "dsx02"), ("import_source_sha256", source_hash), ("imported_at", import_time),
                 ("import_source_records", str(len(records)))),
            )
    except Exception:
        db_path.unlink(missing_ok=True)
        raise

    report = {
        "generated_at": import_time,
        "source_sha256": source_hash,
        "source_bytes": len(source_bytes),
        "images_source": str(images_source) if images_source else None,
        "database": str(db_path),
        "privacy": "Dữ liệu thật chỉ lưu cục bộ trong .local/ (đã gitignore); không đưa DB lên GitHub.",
        **dict(sorted(stats.items())),
    }
    (data_dir / "import-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (data_dir / "import-map.json").write_text(
        json.dumps(workers, ensure_ascii=False, indent=2), encoding="utf-8",
    )
    return db_path, report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=SOURCE_DEFAULT)
    parser.add_argument("--images", type=Path, default=IMAGES_DEFAULT,
                        help="Tệp images.json của ĐSX02 (ánh xạ mã hồ sơ → tệp Drive).")
    parser.add_argument("--data-dir", type=Path, default=DATA_DEFAULT)
    parser.add_argument("--force", action="store_true", help="Thay thế DB nhập trước đó trong thư mục đích.")
    args = parser.parse_args()
    db_path, report = write_database(args.source, args.data_dir, args.force, args.images)
    print(f"Đã nhập {report['imported']} hồ sơ vào {db_path}")
    print(f"Phòng ở: {report['rooms']} · Có CMND: {report['with_cmnd']} · Thiếu CMND: {report['missing_cmnd']}")
    print(f"Ảnh Drive: {report.get('with_photo_image', 0)} chân dung · {report.get('with_cmnd_image', 0)} giấy tờ")
    print(f"Báo cáo (không chứa PII): {db_path.parent / 'import-report.json'}")
    print("Dữ liệu chỉ nằm trong .local/ và không được git theo dõi.")


if __name__ == "__main__":
    main()
