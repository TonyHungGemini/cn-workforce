import json
import re
import sqlite3
import unicodedata
import uuid
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from pathlib import Path


UNITS = ("DSX02", "DSX03", "NMCB")
KINDS = ("Lao động", "Gia thuộc", "Khác")
TEAMS = tuple(f"Tổ {i}" for i in range(1, 9))
GATES = ("Cổng chính", "Cổng khu ở")
RELATIONSHIPS = (
    "Chủ hộ", "Vợ", "Chồng", "Vợ/chồng", "Con", "Bố", "Mẹ", "Cha", "Anh", "Chị", "Em",
    "Cháu", "Bạn", "Con dâu", "Anh rể", "Anh vợ", "Dì", "Bà ngoại", "1 mình", "Khác",
)
LONG_TEXT_FIELDS = {"noi_sinh", "dia_chi", "chi_tiet_noi_o"}
DISCIPLINE_FIELDS = (
    "ghi_chu_ky_luat", "ngay_ky_luat", "hinh_thuc_ky_luat", "trang_thai_ky_luat", "nguoi_lap_bien_ban",
)
EXTRA_WORKER_DEFAULTS = dict.fromkeys((
    "noi_sinh", "khu_vuc", "phan_cay", "so_bao_hiem", "chi_tiet_noi_o", "dia_chi", "nhom_mau",
    *DISCIPLINE_FIELDS,
), "")
EXTRA_WORKER_DEFAULTS["chu_phong"] = False
EDITABLE = {
    "unit_id", "ten_that", "ten_ho_so", "loai", "to", "phong_o", "so_dt",
    "cmnd", "ngay_sinh", "gioi_tinh", "quan_he", "danh_gia_ky_nang",
    "danh_gia_dao_duc", "_manuallyRated", "ghi_chu",
} | set(EXTRA_WORKER_DEFAULTS)
READ_ONLY = {"id", "person_id", "status", "version", "updated_at"}
EVENT_TYPES = (
    "worker.created", "worker.updated", "worker.archived", "gate.in", "gate.out",
    "visitor.registered", "visitor.inside", "visitor.left",
)


class APIError(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status
        self.message = message


def timestamp(value=None):
    return (value or datetime.now(timezone.utc)).isoformat(timespec="microseconds").replace("+00:00", "Z")


def identifier():
    return str(uuid.uuid4())


def encode(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":"))


def schema(payload, allowed, required=()):
    if not isinstance(payload, dict) or any(not isinstance(key, str) for key in payload):
        raise APIError(400, "Nội dung JSON phải là một đối tượng.")
    if set(payload) - set(allowed):
        raise APIError(400, "Có trường không được hỗ trợ.")
    if set(required) - set(payload):
        raise APIError(400, "Thiếu trường bắt buộc.")


def text(value, field, required=False, maximum=200):
    if not isinstance(value, str):
        raise APIError(400, f"{field} phải là chuỗi.")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        raise APIError(400, f"{field} chứa ký tự không hợp lệ.") from None
    if len(value) > maximum:
        raise APIError(400, f"{field} vượt quá {maximum} ký tự.")
    if any(ord(char) < 32 and not (field in {"ghi_chu", "ghi_chu_ky_luat"} and char in "\n\r\t") for char in value):
        raise APIError(400, f"{field} chứa ký tự điều khiển.")
    value = unicodedata.normalize("NFC", value.strip())
    if required and not value:
        raise APIError(400, f"{field} không được để trống.")
    return value


def choice(value, field, choices):
    value = text(value, field)
    if value not in choices:
        raise APIError(400, f"{field} không hợp lệ.")
    return value


def iso_date(value, field, required=False):
    value = text(value, field, required=required)
    if not value and not required:
        return value
    if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
        raise APIError(400, f"{field} phải có dạng YYYY-MM-DD.")
    try:
        date.fromisoformat(value)
    except ValueError:
        raise APIError(400, f"{field} không phải ngày hợp lệ.") from None
    return value


def uuid_field(value, field="id"):
    value = text(value, field, required=True)
    try:
        if str(uuid.UUID(value)) != value:
            raise ValueError
    except ValueError:
        raise APIError(400, f"{field} phải là UUID hợp lệ.") from None
    return value


def check_version(payload, existing):
    version = payload.get("version")
    if type(version) is not int or version != existing["version"]:
        raise APIError(409, "Phiên bản đã thay đổi hoặc bị thiếu. Hãy tải lại dữ liệu.")


class Store:
    def __init__(self, data_dir, seed=True):
        self.data_dir = Path(data_dir).expanduser().resolve()
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.data_dir / "demo.sqlite3"
        self.initialize(seed=seed)

    @contextmanager
    def transaction(self, write=True):
        connection = sqlite3.connect(str(self.db_path), timeout=15)
        connection.row_factory = sqlite3.Row
        try:
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("BEGIN IMMEDIATE" if write else "BEGIN")
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def initialize(self, seed=True):
        statements = (
            "CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)",
            "CREATE TABLE IF NOT EXISTS counters (name TEXT PRIMARY KEY, value INTEGER NOT NULL)",
            "CREATE TABLE IF NOT EXISTS rooms (id TEXT PRIMARY KEY, unit_id TEXT NOT NULL, capacity INTEGER NOT NULL)",
            "CREATE TABLE IF NOT EXISTS workers (id TEXT PRIMARY KEY, person_id TEXT NOT NULL UNIQUE, unit_id TEXT NOT NULL, cmnd_key TEXT UNIQUE, status TEXT NOT NULL, version INTEGER NOT NULL, updated_at TEXT NOT NULL, data TEXT NOT NULL)",
            "CREATE TABLE IF NOT EXISTS events (id TEXT PRIMARY KEY, worker_id TEXT NOT NULL REFERENCES workers(id), person_id TEXT NOT NULL, name TEXT NOT NULL, unit_id TEXT NOT NULL, gate TEXT NOT NULL, direction TEXT NOT NULL, method TEXT NOT NULL, at TEXT NOT NULL)",
            "CREATE INDEX IF NOT EXISTS events_worker_at ON events(worker_id, at DESC)",
            "CREATE TABLE IF NOT EXISTS visitors (id TEXT PRIMARY KEY, status TEXT NOT NULL, version INTEGER NOT NULL, created_at TEXT NOT NULL, data TEXT NOT NULL)",
            "CREATE TABLE IF NOT EXISTS audit (id TEXT PRIMARY KEY, action TEXT NOT NULL, entity_id TEXT NOT NULL, actor TEXT NOT NULL, at TEXT NOT NULL, summary TEXT NOT NULL)",
            "CREATE TABLE IF NOT EXISTS outbox (event_id TEXT PRIMARY KEY, entity_id TEXT NOT NULL, person_id TEXT NOT NULL, unit_id TEXT NOT NULL, entity_version INTEGER NOT NULL, event_type TEXT NOT NULL, occurred_at TEXT NOT NULL, status TEXT NOT NULL)",
            "CREATE TABLE IF NOT EXISTS worker_images (worker_id TEXT NOT NULL REFERENCES workers(id) ON DELETE CASCADE, kind TEXT NOT NULL, drive_id TEXT NOT NULL, updated_at TEXT NOT NULL, PRIMARY KEY(worker_id, kind))",
            "CREATE TABLE IF NOT EXISTS legacy_links (legacy_id INTEGER PRIMARY KEY, worker_id TEXT NOT NULL UNIQUE REFERENCES workers(id))",
        )
        with self.transaction() as connection:
            for statement in statements:
                connection.execute(statement)
            version = connection.execute("SELECT value FROM metadata WHERE key = 'schema_version'").fetchone()
            if version:
                if version["value"] not in {"1.0", "1.1", "1.2"}:
                    raise RuntimeError("Unsupported demo database version")
                if version["value"] == "1.0":
                    # Backfill JSON only: identities, versions, history and outbox stay untouched.
                    for row in connection.execute("SELECT id, data FROM workers").fetchall():
                        worker = json.loads(row["data"])
                        for field, default in EXTRA_WORKER_DEFAULTS.items():
                            worker.setdefault(field, default)
                        connection.execute("UPDATE workers SET data = ? WHERE id = ?", (encode(worker), row["id"]))
                    connection.execute("UPDATE metadata SET value = '1.1' WHERE key = 'schema_version'")
                if version["value"] in {"1.0", "1.1"}:
                    connection.execute("UPDATE metadata SET value = '1.2' WHERE key = 'schema_version'")
                return
            connection.execute("INSERT INTO counters(name, value) VALUES ('person', 0)")
            if seed:
                self._seed(connection)
            connection.execute("INSERT INTO metadata(key, value) VALUES ('schema_version', '1.2')")

    def _next_person(self, connection):
        connection.execute("UPDATE counters SET value = value + 1 WHERE name = 'person'")
        number = connection.execute("SELECT value FROM counters WHERE name = 'person'").fetchone()["value"]
        return f"CN-{number:04d}"

    def _record(self, connection, action, entity_id, person_id, unit_id, version, summary, at=None):
        at = at or timestamp()
        connection.execute(
            "INSERT INTO audit(id, action, entity_id, actor, at, summary) VALUES (?, ?, ?, ?, ?, ?)",
            (identifier(), action, entity_id, "Phiên demo cục bộ", at, summary),
        )
        connection.execute(
            "INSERT INTO outbox(event_id, entity_id, person_id, unit_id, entity_version, event_type, occurred_at, status) VALUES (?, ?, ?, ?, ?, ?, ?, 'pending')",
            (identifier(), entity_id, person_id, unit_id, version, action, at),
        )

    def _insert_worker(self, connection, worker):
        connection.execute(
            "INSERT INTO workers(id, person_id, unit_id, cmnd_key, status, version, updated_at, data) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (worker["id"], worker["person_id"], worker["unit_id"], worker["cmnd"].casefold() or None,
             worker["status"], worker["version"], worker["updated_at"], encode(worker)),
        )

    def _update_worker(self, connection, worker, previous_version):
        cursor = connection.execute(
            "UPDATE workers SET unit_id = ?, cmnd_key = ?, status = ?, version = ?, updated_at = ?, data = ? WHERE id = ? AND version = ?",
            (worker["unit_id"], worker["cmnd"].casefold() or None, worker["status"], worker["version"],
             worker["updated_at"], encode(worker), worker["id"], previous_version),
        )
        if cursor.rowcount != 1:
            raise APIError(409, "Phiên bản đã thay đổi. Hãy tải lại dữ liệu.")

    def _seed(self, connection):
        now = datetime.now(timezone.utc)
        seed_time = timestamp(now - timedelta(hours=4))
        for prefix, unit in zip("ABC", UNITS):
            for number in range(1, 5):
                room_id = f"{prefix}{number:02d}"
                connection.execute("INSERT INTO rooms VALUES (?, ?, ?)", (room_id, unit, 3 if room_id == "A01" else 6))
        workers = []
        for index in range(48):
            number = index + 1
            unit_index = index % 3
            kind = "Lao động" if number <= 32 else "Gia thuộc" if number <= 46 else "Khác"
            worker = {
                **EXTRA_WORKER_DEFAULTS,
                "id": identifier(), "person_id": self._next_person(connection), "unit_id": UNITS[unit_index],
                "ten_that": f"Hồ sơ mẫu {number:02d}", "ten_ho_so": f"Hồ sơ mẫu {number:02d}",
                "loai": kind, "to": TEAMS[index % 4], "phong_o": f"{'ABC'[unit_index]}{(index // 3) % 4 + 1:02d}",
                "so_dt": "", "cmnd": "" if number % 7 == 0 else f"DEMO-{number:04d}",
                "ngay_sinh": "" if kind == "Gia thuộc" else "1990-05-12", "gioi_tinh": "M" if number % 2 else "F",
                "quan_he": "Con" if kind == "Gia thuộc" else "Khác" if kind == "Khác" else "Chủ hộ",
                "danh_gia_ky_nang": None if kind == "Gia thuộc" else 3,
                "danh_gia_dao_duc": None if kind == "Gia thuộc" else 3,
                "_manuallyRated": False, "ghi_chu": "Hồ sơ hoàn toàn hư cấu để duyệt demo.",
                "status": "active", "version": 1, "updated_at": seed_time,
            }
            self._insert_worker(connection, worker)
            self._record(connection, "worker.created", worker["id"], worker["person_id"], worker["unit_id"], 1,
                         "Khởi tạo hồ sơ minh họa.", seed_time)
            workers.append(worker)
        for index, worker in enumerate(workers[:12]):
            self._insert_event(connection, worker, "in", GATES[0], timestamp(now - timedelta(hours=3) + timedelta(minutes=index)))
        for index, worker in enumerate(workers[:4]):
            self._insert_event(connection, worker, "out", GATES[0], timestamp(now - timedelta(hours=1) + timedelta(minutes=index)))
        for index in range(2):
            visitor = {
                "id": identifier(), "name": f"Khách mẫu {index + 1:02d}", "company": "Đơn vị minh họa",
                "purpose": "Tham quan demo", "host": "Đầu mối minh họa", "unit_id": UNITS[index],
                "expected": (date.today() + timedelta(days=index)).isoformat(), "status": "registered",
                "version": 1, "created_at": seed_time,
            }
            self._insert_visitor(connection, visitor)
            self._record(connection, "visitor.registered", visitor["id"], "", visitor["unit_id"], 1,
                         "Khởi tạo khách minh họa.", seed_time)

    def bootstrap(self):
        with self.transaction(write=False) as connection:
            dataset = connection.execute("SELECT value FROM metadata WHERE key = 'dataset'").fetchone()
            imported = dataset is not None and dataset["value"] == "dsx02"
            return {
                "ok": True, "mode": "imported" if imported else "demo",
                "directory": {
                    "units": [
                        {"id": "DSX02", "name": "Đội sản xuất 02"},
                        {"id": "DSX03", "name": "Đội sản xuất 03"},
                        {"id": "NMCB", "name": "Nhà máy chế biến"},
                    ],
                    "teams": list(TEAMS),
                },
                "workers": [json.loads(row["data"]) for row in connection.execute("SELECT data FROM workers ORDER BY person_id")],
                "rooms": [dict(row) for row in connection.execute("SELECT * FROM rooms ORDER BY id")],
                "events": [dict(row) for row in connection.execute("SELECT * FROM events ORDER BY at DESC, rowid DESC")],
                "visitors": [json.loads(row["data"]) for row in connection.execute("SELECT data FROM visitors ORDER BY created_at DESC, rowid DESC")],
                "audit": [dict(row) for row in connection.execute("SELECT * FROM audit ORDER BY at DESC, rowid DESC")],
                "outbox": [dict(row) for row in connection.execute("SELECT * FROM outbox ORDER BY occurred_at DESC, rowid DESC")],
                "images": self._image_index(connection),
                "meta": {
                    "source": "Dữ liệu ĐSX02" if imported else "Dữ liệu minh họa",
                    "integration": "disconnected",
                },
            }

    def _image_index(self, connection):
        index = {}
        for row in connection.execute("SELECT worker_id, kind FROM worker_images"):
            index.setdefault(row["worker_id"], {})[row["kind"]] = True
        return index

    def worker_image(self, worker_id, kind):
        if kind not in ("photo", "cmnd"):
            raise APIError(404, "Không tìm thấy ảnh.")
        with self.transaction(write=False) as connection:
            row = connection.execute("SELECT drive_id FROM worker_images WHERE worker_id = ? AND kind = ?",
                                     (worker_id, kind)).fetchone()
            if row is None:
                raise APIError(404, "Hồ sơ chưa có ảnh này.")
            return row["drive_id"]

    def link_legacy(self, connection, legacy_id, worker_id):
        connection.execute("INSERT OR REPLACE INTO legacy_links(legacy_id, worker_id) VALUES (?, ?)",
                           (legacy_id, worker_id))

    def set_worker_image(self, connection, worker_id, kind, drive_id):
        if kind not in ("photo", "cmnd"):
            raise ValueError("Unsupported image kind")
        if not drive_id:
            connection.execute("DELETE FROM worker_images WHERE worker_id = ? AND kind = ?", (worker_id, kind))
            return
        connection.execute(
            "INSERT OR REPLACE INTO worker_images(worker_id, kind, drive_id, updated_at) VALUES (?, ?, ?, ?)",
            (worker_id, kind, drive_id, timestamp()),
        )

    def _worker(self, connection, worker_id):
        row = connection.execute("SELECT data FROM workers WHERE id = ?", (worker_id,)).fetchone()
        if row is None:
            raise APIError(404, "Không tìm thấy hồ sơ công nhân.")
        return json.loads(row["data"])

    def _validate_worker(self, connection, worker):
        for field in ("ten_that", "ten_ho_so", "phong_o", "so_dt", "cmnd", "noi_sinh", "khu_vuc",
                      "phan_cay", "so_bao_hiem", "chi_tiet_noi_o", "dia_chi", "hinh_thuc_ky_luat",
                      "trang_thai_ky_luat", "nguoi_lap_bien_ban"):
            worker[field] = text(worker[field], field, required=field == "ten_that",
                                 maximum=500 if field in LONG_TEXT_FIELDS else 200)
        for field in ("ghi_chu", "ghi_chu_ky_luat"):
            worker[field] = text(worker[field], field, maximum=2000)
        worker["nhom_mau"] = text(worker["nhom_mau"], "nhom_mau").upper()
        if len(worker["nhom_mau"]) > 8:
            raise APIError(400, "nhom_mau vượt quá 8 ký tự.")
        for field, choices in (("unit_id", UNITS), ("loai", KINDS), ("to", TEAMS),
                               ("gioi_tinh", ("M", "F", "")), ("quan_he", RELATIONSHIPS)):
            worker[field] = choice(worker[field], field, choices)
        for field in ("ngay_sinh", "ngay_ky_luat"):
            worker[field] = iso_date(worker[field], field)
        for field in ("_manuallyRated", "chu_phong"):
            if type(worker[field]) is not bool:
                raise APIError(400, f"{field} phải là boolean.")
        for field in ("danh_gia_ky_nang", "danh_gia_dao_duc"):
            value = worker[field]
            if value is not None and (type(value) is not int or not 1 <= value <= 5):
                raise APIError(400, f"{field} chỉ nhận số nguyên từ 1 đến 5 hoặc null.")
            if worker["loai"] == "Gia thuộc":
                worker[field] = None
            elif not worker["_manuallyRated"]:
                worker[field] = 3
        if worker["loai"] == "Gia thuộc":
            worker["_manuallyRated"] = False
            for field in DISCIPLINE_FIELDS:
                worker[field] = ""
        if worker["phong_o"]:
            room = connection.execute("SELECT unit_id FROM rooms WHERE id = ?", (worker["phong_o"],)).fetchone()
            if room is None or room["unit_id"] != worker["unit_id"]:
                raise APIError(400, "Phòng ở không tồn tại hoặc không thuộc đơn vị đã chọn.")
        if worker["cmnd"]:
            duplicate = connection.execute("SELECT id FROM workers WHERE cmnd_key = ? AND id != ?",
                                           (worker["cmnd"].casefold(), worker["id"])).fetchone()
            if duplicate:
                raise APIError(409, "Mã giấy tờ minh họa đã được sử dụng.")

    def _validate_room_leader(self, connection, worker):
        if not worker["chu_phong"]:
            return
        if worker["status"] != "active" or worker["loai"] == "Gia thuộc" or not worker["phong_o"]:
            raise APIError(400, "Chủ phòng phải là hồ sơ đang hoạt động, không phải gia thuộc và có phòng ở.")
        rows = connection.execute("SELECT data FROM workers WHERE unit_id = ? AND status = 'active' AND id != ?",
                                  (worker["unit_id"], worker["id"]))
        for row in rows:
            other = json.loads(row["data"])
            if other["phong_o"] == worker["phong_o"] and other["chu_phong"]:
                raise APIError(409, "Phòng đã có chủ phòng. Cần bỏ chọn chủ phòng hiện tại trước khi chỉ định người mới.")

    def save_worker(self, payload):
        schema(payload, EDITABLE | READ_ONLY)
        with self.transaction() as connection:
            existing = None
            if "id" in payload:
                existing = self._worker(connection, uuid_field(payload["id"]))
                check_version(payload, existing)
                if existing["status"] != "active":
                    raise APIError(409, "Hồ sơ đã lưu trữ, không thể chỉnh sửa.")
                for field in ("person_id", "status", "updated_at"):
                    if field in payload and (type(payload[field]) is not str or payload[field] != existing[field]):
                        raise APIError(400, f"Không được thay đổi {field}.")
                worker = dict(existing)
            else:
                if set(payload) & READ_ONLY:
                    raise APIError(400, "Không được tự cấp trường định danh hoặc phiên bản.")
                worker = {
                    **EXTRA_WORKER_DEFAULTS,
                    "id": identifier(), "person_id": self._next_person(connection), "unit_id": "DSX02",
                    "ten_that": "", "ten_ho_so": payload.get("ten_that", ""), "loai": "Lao động", "to": TEAMS[0],
                    "phong_o": "", "so_dt": "", "cmnd": "", "ngay_sinh": "", "gioi_tinh": "", "quan_he": "Chủ hộ",
                    "danh_gia_ky_nang": 3, "danh_gia_dao_duc": 3, "_manuallyRated": False, "ghi_chu": "",
                    "status": "active", "version": 1, "updated_at": timestamp(),
                }
            for field in EDITABLE & set(payload):
                worker[field] = payload[field]
            self._validate_worker(connection, worker)
            if existing and "chu_phong" not in payload and (
                worker["unit_id"] != existing["unit_id"] or worker["phong_o"] != existing["phong_o"]
                or worker["loai"] == "Gia thuộc"
            ):
                worker["chu_phong"] = False
            if existing and worker["unit_id"] != existing["unit_id"]:
                latest = self._latest_event(connection, worker["id"])
                if latest and latest["direction"] == "in":
                    raise APIError(409, "Cần ghi nhận ra cổng trước khi chuyển đơn vị.")
            self._validate_room_leader(connection, worker)
            worker["updated_at"] = timestamp()
            if existing:
                worker["version"] = existing["version"] + 1
                self._update_worker(connection, worker, existing["version"])
            else:
                self._insert_worker(connection, worker)
            action = "worker.updated" if existing else "worker.created"
            self._record(connection, action, worker["id"], worker["person_id"], worker["unit_id"], worker["version"],
                         "Cập nhật hồ sơ minh họa." if existing else "Tạo hồ sơ minh họa.", worker["updated_at"])
            return {"ok": True, "worker": worker}

    def _latest_event(self, connection, worker_id):
        return connection.execute("SELECT direction FROM events WHERE worker_id = ? ORDER BY at DESC, rowid DESC LIMIT 1",
                                  (worker_id,)).fetchone()

    def archive_worker(self, payload):
        schema(payload, {"id", "version"}, {"id"})
        worker_id = uuid_field(payload["id"])
        with self.transaction() as connection:
            worker = self._worker(connection, worker_id)
            check_version(payload, worker)
            if worker["status"] != "active":
                raise APIError(409, "Hồ sơ đã được lưu trữ.")
            latest = self._latest_event(connection, worker_id)
            if latest and latest["direction"] == "in":
                raise APIError(409, "Cần ghi nhận ra cổng trước khi lưu trữ")
            previous_version = worker["version"]
            worker.update(status="archived", phong_o="", chu_phong=False, version=previous_version + 1, updated_at=timestamp())
            self._update_worker(connection, worker, previous_version)
            self._record(connection, "worker.archived", worker["id"], worker["person_id"], worker["unit_id"], worker["version"],
                         "Lưu trữ hồ sơ và giải phóng phòng ở.", worker["updated_at"])
            return {"ok": True}

    def _insert_event(self, connection, worker, direction, gate, at):
        event = {
            "id": identifier(), "worker_id": worker["id"], "person_id": worker["person_id"], "name": worker["ten_that"],
            "unit_id": worker["unit_id"], "gate": gate, "direction": direction, "method": "manual", "at": at,
        }
        connection.execute(
            "INSERT INTO events(id, worker_id, person_id, name, unit_id, gate, direction, method, at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            tuple(event[key] for key in ("id", "worker_id", "person_id", "name", "unit_id", "gate", "direction", "method", "at")),
        )
        self._record(connection, f"gate.{direction}", event["id"], worker["person_id"], worker["unit_id"], 1,
                     "Ghi nhận vào cổng thủ công." if direction == "in" else "Ghi nhận ra cổng thủ công.", at)
        return event

    def add_event(self, payload):
        schema(payload, {"worker_id", "direction", "gate"}, {"worker_id", "direction", "gate"})
        worker_id = uuid_field(payload["worker_id"], "worker_id")
        direction = choice(payload["direction"], "direction", ("in", "out"))
        gate = choice(payload["gate"], "gate", GATES)
        with self.transaction() as connection:
            worker = self._worker(connection, worker_id)
            if worker["status"] != "active":
                raise APIError(409, "Hồ sơ đã lưu trữ, không thể ghi nhận cổng.")
            latest = self._latest_event(connection, worker_id)
            inside = latest is not None and latest["direction"] == "in"
            if direction == "in" and inside:
                raise APIError(409, "Công nhân đã ở bên trong.")
            if direction == "out" and not inside:
                raise APIError(409, "Cần có lượt vào cổng trước khi ghi nhận ra.")
            event = self._insert_event(connection, worker, direction, gate, timestamp())
            return {"ok": True, "event": event}

    def _insert_visitor(self, connection, visitor):
        connection.execute("INSERT INTO visitors(id, status, version, created_at, data) VALUES (?, ?, ?, ?, ?)",
                           (visitor["id"], visitor["status"], visitor["version"], visitor["created_at"], encode(visitor)))

    def add_visitor(self, payload):
        fields = {"name", "company", "purpose", "host", "unit_id", "expected"}
        schema(payload, fields, fields)
        visitor = {field: text(payload[field], field, required=field in {"name", "purpose", "host"})
                   for field in ("name", "company", "purpose", "host")}
        visitor["unit_id"] = choice(payload["unit_id"], "unit_id", UNITS)
        visitor["expected"] = iso_date(payload["expected"], "expected", required=True)
        visitor.update(id=identifier(), status="registered", version=1, created_at=timestamp())
        with self.transaction() as connection:
            self._insert_visitor(connection, visitor)
            self._record(connection, "visitor.registered", visitor["id"], "", visitor["unit_id"], 1,
                         "Đăng ký khách minh họa.", visitor["created_at"])
            return {"ok": True, "visitor": visitor}

    def transition_visitor(self, payload):
        schema(payload, {"id", "version", "status"}, {"id", "status"})
        visitor_id = uuid_field(payload["id"])
        status = choice(payload["status"], "status", ("inside", "left"))
        with self.transaction() as connection:
            row = connection.execute("SELECT data FROM visitors WHERE id = ?", (visitor_id,)).fetchone()
            if row is None:
                raise APIError(404, "Không tìm thấy khách.")
            visitor = json.loads(row["data"])
            check_version(payload, visitor)
            if {"registered": "inside", "inside": "left"}.get(visitor["status"]) != status:
                raise APIError(409, "Chỉ cho phép chuyển trạng thái đăng ký → đang ở trong → đã rời.")
            old_version = visitor["version"]
            visitor.update(status=status, version=old_version + 1)
            cursor = connection.execute("UPDATE visitors SET status = ?, version = ?, data = ? WHERE id = ? AND version = ?",
                                        (status, visitor["version"], encode(visitor), visitor_id, old_version))
            if cursor.rowcount != 1:
                raise APIError(409, "Phiên bản khách đã thay đổi. Hãy tải lại dữ liệu.")
            self._record(connection, f"visitor.{status}", visitor_id, "", visitor["unit_id"], visitor["version"],
                         "Ghi nhận khách vào." if status == "inside" else "Ghi nhận khách rời.")
            return {"ok": True, "visitor": visitor}

    def contract(self):
        return {
            "schema_version": "1.0", "status": "draft", "source": "cn-workforce", "target": "pm-quan-tri-hop-nhat",
            "transport": "Chưa cấu hình",
            "master_data": {
                "workers": {"entity_id": "UUID ổn định", "person_id": "CN-xxxx, không đổi khi sửa", "version": "Số nguyên tăng dần"},
                "units": list(UNITS), "rooms": "Mã phòng duy nhất, thuộc một đơn vị",
                "gate_events": "Sự kiện bất biến; entity_id là UUID lượt cổng, entity_version = 1",
                "visitors": "UUID riêng; person_id rỗng, phiên bản tăng theo chuyển trạng thái",
                "ownership": "Bản nháp; chưa xác lập nguồn dữ liệu chủ với hệ thống đích",
            },
            "events": list(EVENT_TYPES),
            "sample": {
                "event_id": "11111111-1111-4111-8111-111111111111", "entity_id": "22222222-2222-4222-8222-222222222222",
                "person_id": "CN-0001", "unit_id": "DSX02", "entity_version": 2,
                "event_type": "worker.updated", "occurred_at": timestamp(),
            },
            "notes": [
                "Chỉ là hợp đồng bản nháp; không có kết nối mạng, đồng bộ hay lệnh thiết bị thực.",
                "Không nhập dữ liệu thật, ảnh giấy tờ hoặc secrets; outbox không chứa tên, số điện thoại, CMND hay tài liệu nhạy cảm.",
                "Bên nhận tương lai phải xử lý idempotency bằng event_id và optimistic concurrency bằng entity_version.",
                "Trước tích hợp thật cần SSO, RBAC, webhook HMAC, TLS, consent và retention được phê duyệt.",
                "Phiên demo cục bộ không phải cơ chế xác thực hoặc phân quyền.",
            ],
        }
