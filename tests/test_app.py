import hashlib
import http.client
import json
import os
import selectors
import signal
import subprocess
import sys
import tempfile
import threading
import unittest
import uuid
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timezone
from pathlib import Path
from unittest.mock import patch


PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR))

from app import MAX_JSON_BYTES, create_server
from store import APIError, Store, encode


ADDED_TEXT_FIELDS = (
    "noi_sinh", "khu_vuc", "phan_cay", "so_bao_hiem", "chi_tiet_noi_o", "dia_chi", "nhom_mau",
    "ghi_chu_ky_luat", "ngay_ky_luat", "hinh_thuc_ky_luat", "trang_thai_ky_luat", "nguoi_lap_bien_ban",
)
ADDED_DEFAULTS = dict.fromkeys(ADDED_TEXT_FIELDS, "")
ADDED_DEFAULTS["chu_phong"] = False
DISCIPLINE_SAMPLE = {
    "ghi_chu_ky_luat": "Tình huống hư cấu\nDòng ghi chú minh họa\r\n\tKhông phải dữ liệu thật.",
    "ngay_ky_luat": "2024-02-29", "hinh_thuc_ky_luat": "Hình thức minh họa",
    "trang_thai_ky_luat": "Trạng thái minh họa", "nguoi_lap_bien_ban": "Người lập mẫu",
}


def fictional_details(**changes):
    payload = dict.fromkeys(ADDED_TEXT_FIELDS, "Nội dung hoàn toàn hư cấu")
    payload.update(DISCIPLINE_SAMPLE, nhom_mau="CUSTOM", chu_phong=True)
    payload.update(changes)
    return payload


def fictional_worker(**changes):
    payload = {
        "ten_that": "Hồ sơ mẫu bổ sung", "ten_ho_so": "Tên minh họa", "unit_id": "DSX02",
        "loai": "Lao động", "to": "Tổ 2", "phong_o": "A02", "so_dt": "", "cmnd": "",
        "ngay_sinh": "1990-05-12", "gioi_tinh": "F", "quan_he": "Chủ hộ",
        "danh_gia_ky_nang": 3, "danh_gia_dao_duc": 3, "_manuallyRated": False, "ghi_chu": "Dữ liệu hoàn toàn hư cấu.",
    }
    payload.update(changes)
    return payload


def fictional_visitor(**changes):
    payload = {
        "name": "Khách mẫu thử nghiệm", "company": "Đơn vị minh họa", "purpose": "Duyệt demo",
        "host": "Đầu mối mẫu", "unit_id": "DSX02", "expected": date.today().isoformat(),
    }
    payload.update(changes)
    return payload


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="cn-workforce-store-test-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.store = Store(self.root / "data")

    def assert_api_error(self, status, operation, *args):
        with self.assertRaises(APIError) as caught:
            operation(*args)
        self.assertEqual(status, caught.exception.status)
        return caught.exception.message

    def counts(self):
        result = self.store.bootstrap()
        return {key: len(result[key]) for key in ("workers", "events", "visitors", "audit", "outbox")}

    def database_snapshot(self):
        with self.store.transaction(write=False) as connection:
            return {
                table: [dict(row) for row in connection.execute(f"SELECT * FROM {table} ORDER BY rowid")]
                for table in ("metadata", "counters", "rooms", "workers", "events", "visitors", "audit", "outbox")
            }

    def make_legacy_database(self):
        # Downgrade only this test's synthetic database; never import original data.
        worker = self.store.save_worker(fictional_worker(**fictional_details(), _manuallyRated=True,
                                                        danh_gia_ky_nang=2, danh_gia_dao_duc=None))["worker"]
        worker = self.store.save_worker({"id": worker["id"], "version": 1, "ghi_chu": "Giữ phiên bản mẫu"})["worker"]
        self.store.add_event({"worker_id": worker["id"], "direction": "in", "gate": "Cổng chính"})
        archived = self.store.save_worker(fictional_worker(phong_o=""))["worker"]
        self.store.archive_worker({"id": archived["id"], "version": 1})
        visitor = self.store.bootstrap()["visitors"][0]
        self.store.transition_visitor({"id": visitor["id"], "version": 1, "status": "inside"})
        with self.store.transaction() as connection:
            for row in connection.execute("SELECT id, data FROM workers").fetchall():
                data = json.loads(row["data"])
                if row["id"] == worker["id"]:
                    # Existing legacy values must not be revalidated or normalized by migration.
                    data["nhom_mau"] = " custom "
                    data["noi_sinh"] = "  Nơi sinh mẫu  "
                else:
                    for field in ADDED_DEFAULTS:
                        data.pop(field)
                    if data["person_id"] == "CN-0001":
                        data["dia_chi"] = "Địa chỉ mẫu giữ lại khi backfill một phần"
                connection.execute("UPDATE workers SET data = ? WHERE id = ?", (json.dumps(data, ensure_ascii=False), row["id"]))
            connection.execute("UPDATE metadata SET value = '1.0' WHERE key = 'schema_version'")
        return self.database_snapshot()

    def test_seed_is_fictional_complete_and_initialized_once(self):
        data = self.store.bootstrap()
        self.assertEqual({"Lao động": 32, "Gia thuộc": 14, "Khác": 2}, Counter(w["loai"] for w in data["workers"]))
        self.assertEqual({"DSX02": 16, "DSX03": 16, "NMCB": 16}, Counter(w["unit_id"] for w in data["workers"]))
        self.assertEqual({f"Tổ {i}" for i in range(1, 5)}, {w["to"] for w in data["workers"]})
        self.assertEqual(48, len({w["id"] for w in data["workers"]}))
        self.assertEqual(48, len({w["person_id"] for w in data["workers"]}))
        self.assertEqual({"source": "Dữ liệu minh họa", "integration": "disconnected",
                          "transfer_approval": "external",
                          "card_scope": ["DSX01", "DSX02", "DSX03", "DSX06"]}, data["meta"])
        self.assertEqual([], data["transfers"])
        self.assertEqual({
            "units": [{"id": f"DSX{number:02d}", "name": f"Đội sản xuất {number:02d}"} for number in range(1, 9)]
                     + [{"id": "NMCB", "name": "Nhà máy chế biến"}],
            "teams": [f"Tổ {i}" for i in range(1, 9)],
        }, data["directory"])
        self.assertEqual([{"key": "schema_version", "value": "1.2"}], self.database_snapshot()["metadata"])
        self.assertTrue(data["ok"])
        self.assertEqual("demo", data["mode"])
        self.assertEqual(12, len(data["rooms"]))
        rooms = {r["id"]: r for r in data["rooms"]}
        self.assertEqual({"id": "A01", "unit_id": "DSX02", "capacity": 3}, rooms["A01"])
        self.assertEqual(4, sum(w["phong_o"] == "A01" for w in data["workers"]))
        self.assertTrue(all(r["capacity"] == 6 for r in data["rooms"] if r["id"] != "A01"))
        self.assertTrue(any(not w["cmnd"] for w in data["workers"]))
        for index, worker in enumerate(data["workers"], start=1):
            self.assertEqual(f"Hồ sơ mẫu {index:02d}", worker["ten_that"])
            self.assertEqual(worker["ten_that"], worker["ten_ho_so"])
            self.assertEqual(f"CN-{index:04d}", worker["person_id"])
            self.assertEqual(worker["id"], str(uuid.UUID(worker["id"])))
            self.assertEqual("", worker["so_dt"])
            self.assertTrue(not worker["cmnd"] or worker["cmnd"].startswith("DEMO-"))
            self.assertEqual(worker["unit_id"], rooms[worker["phong_o"]]["unit_id"])
            self.assertEqual("active", worker["status"])
            self.assertEqual(1, worker["version"])
            self.assertIsNotNone(datetime.fromisoformat(worker["updated_at"].replace("Z", "+00:00")).tzinfo)
            self.assertEqual(ADDED_DEFAULTS, {field: worker[field] for field in ADDED_DEFAULTS})
            self.assertIs(worker["chu_phong"], False)
            self.assertNotIn("tuoi", worker)
            self.assertNotIn("age", worker)
            self.assertIs(worker["_manuallyRated"], False)
            if worker["loai"] == "Gia thuộc":
                self.assertIsNone(worker["danh_gia_ky_nang"])
                self.assertIsNone(worker["danh_gia_dao_duc"])
            else:
                self.assertEqual((3, 3), (worker["danh_gia_ky_nang"], worker["danh_gia_dao_duc"]))
        self.assertEqual(data, Store(self.root / "data").bootstrap())

    def test_seed_events_have_eight_inside_four_outside_and_runtime_dates(self):
        data = self.store.bootstrap()
        self.assertEqual(16, len(data["events"]))
        self.assertEqual(sorted((e["at"] for e in data["events"]), reverse=True), [e["at"] for e in data["events"]])
        latest = {}
        for event in data["events"]:
            latest.setdefault(event["worker_id"], event["direction"])
            self.assertEqual("manual", event["method"])
            at = datetime.fromisoformat(event["at"].replace("Z", "+00:00"))
            self.assertLess(abs((datetime.now(timezone.utc) - at).total_seconds()), 5 * 3600)
        self.assertEqual({"in": 8, "out": 4}, Counter(latest.values()))
        self.assertEqual({w["id"] for w in data["workers"][:12]}, set(latest))
        self.assertEqual(sorted((a["at"] for a in data["audit"]), reverse=True), [a["at"] for a in data["audit"]])

    def test_concurrent_initialization_seeds_once(self):
        barrier = threading.Barrier(6)
        data_dir = self.root / "concurrent"

        def initialize(_):
            barrier.wait()
            return Store(data_dir).bootstrap()

        with ThreadPoolExecutor(max_workers=6) as executor:
            snapshots = list(executor.map(initialize, range(6)))
        for snapshot in snapshots:
            self.assertEqual(snapshots[0], snapshot)
        self.assertEqual(48, len(snapshots[0]["workers"]))
        self.assertEqual(66, len(snapshots[0]["outbox"]))

    def test_seed_failure_rolls_back_and_can_retry(self):
        seed = Store._seed

        def fail_after_seed(store, connection):
            seed(store, connection)
            raise RuntimeError("Simulated seed failure")

        with patch.object(Store, "_seed", fail_after_seed):
            with self.assertRaises(RuntimeError):
                Store(self.root / "failed-seed")
        result = Store(self.root / "failed-seed").bootstrap()
        self.assertEqual(48, len(result["workers"]))
        self.assertEqual(66, len(result["audit"]))
        self.assertEqual(66, len(result["outbox"]))

    def test_schema_1_0_backfill_preserves_all_records_values_and_versions(self):
        before = self.make_legacy_database()
        with patch.object(Store, "_seed", side_effect=AssertionError("Must not reseed")), \
                patch.object(Store, "_record", side_effect=AssertionError("Must not create history")):
            self.store = Store(self.root / "data")
        after = self.database_snapshot()
        self.assertEqual([{"key": "schema_version", "value": "1.2"}], after["metadata"])
        for table in before:
            if table not in {"workers", "metadata"}:
                self.assertEqual(before[table], after[table], table)
        self.assertEqual(len(before["workers"]), len(after["workers"]))
        for old, new in zip(before["workers"], after["workers"]):
            self.assertEqual({k: v for k, v in old.items() if k != "data"},
                             {k: v for k, v in new.items() if k != "data"})
            expected = dict(ADDED_DEFAULTS, **json.loads(old["data"]))
            self.assertEqual(expected, json.loads(new["data"]))
        # Reopening 1.2 must not even rewrite the serialized JSON or bump versions.
        with patch("store.encode", side_effect=AssertionError("Migration must be idempotent")):
            reopened = Store(self.root / "data")
        self.assertEqual(after, self.database_snapshot())
        self.assertEqual(self.store.bootstrap(), reopened.bootstrap())
        self.assertEqual("CN-0051", reopened.save_worker(fictional_worker())["worker"]["person_id"])

    def test_schema_backfill_is_atomic_and_can_retry(self):
        before = self.make_legacy_database()
        calls = []

        def fail_during_backfill(value):
            calls.append(value["id"])
            if len(calls) == 2:
                raise RuntimeError("Simulated failure after first worker backfill")
            return encode(value)

        with patch("store.encode", side_effect=fail_during_backfill):
            with self.assertRaisesRegex(RuntimeError, "Simulated failure"):
                Store(self.root / "data")
        self.assertEqual(2, len(calls))
        self.assertEqual(before, self.database_snapshot())
        self.store = Store(self.root / "data")
        self.assertEqual([{"key": "schema_version", "value": "1.2"}], self.database_snapshot()["metadata"])
        self.assertTrue(all(set(ADDED_DEFAULTS) <= set(w) for w in self.store.bootstrap()["workers"]))
        self.assertEqual(before["audit"], self.database_snapshot()["audit"])
        self.assertEqual(before["outbox"], self.database_snapshot()["outbox"])

    def test_concurrent_schema_migration_backfills_once(self):
        before = self.make_legacy_database()
        barrier = threading.Barrier(4)

        def reopen(_):
            barrier.wait()
            return Store(self.root / "data").bootstrap()

        with patch("store.encode", wraps=encode) as encoder:
            with ThreadPoolExecutor(max_workers=4) as executor:
                snapshots = list(executor.map(reopen, range(4)))
        self.assertEqual(len(before["workers"]), encoder.call_count)
        self.assertTrue(all(snapshot == snapshots[0] for snapshot in snapshots))
        self.assertEqual(before["audit"], self.database_snapshot()["audit"])
        self.assertEqual(before["outbox"], self.database_snapshot()["outbox"])

    def test_unknown_schema_version_is_rejected_without_changes(self):
        with self.store.transaction() as connection:
            connection.execute("UPDATE metadata SET value = '99.0' WHERE key = 'schema_version'")
        before = self.database_snapshot()
        with self.assertRaisesRegex(RuntimeError, "Unsupported demo database version"):
            Store(self.root / "data")
        self.assertEqual(before, self.database_snapshot())

    def test_worker_create_update_archive_persists_unicode(self):
        worker = self.store.save_worker(fictional_worker(ten_that="Hồ sơ mẫu Ánh Đào", ghi_chu="Minh họa\nTiếng Việt"))["worker"]
        self.assertEqual("CN-0049", worker["person_id"])
        updated = self.store.save_worker({"id": worker["id"], "version": 1, "ten_ho_so": "Mẫu đã cập nhật"})["worker"]
        self.assertEqual(2, updated["version"])
        self.assertEqual(worker["person_id"], updated["person_id"])
        self.assertEqual(worker["ten_that"], updated["ten_that"])
        self.assertEqual("Minh họa\nTiếng Việt", updated["ghi_chu"])
        self.store.archive_worker({"id": worker["id"], "version": 2})
        persisted = next(w for w in Store(self.root / "data").bootstrap()["workers"] if w["id"] == worker["id"])
        self.assertEqual("archived", persisted["status"])
        self.assertEqual("", persisted["phong_o"])
        self.assertEqual(3, persisted["version"])
        self.assertEqual(49, len(self.store.bootstrap()["workers"]))
        self.assert_api_error(409, self.store.save_worker, {"id": worker["id"], "version": 3, "ten_that": "Mẫu đổi"})

    def test_same_name_does_not_merge_and_identifiers_are_immutable(self):
        first = self.store.save_worker(fictional_worker())["worker"]
        second = self.store.save_worker(fictional_worker())["worker"]
        self.assertNotEqual(first["id"], second["id"])
        self.assertNotEqual(first["person_id"], second["person_id"])
        self.assert_api_error(400, self.store.save_worker, {"id": first["id"], "version": 1, "person_id": second["person_id"]})
        self.assert_api_error(400, self.store.save_worker, fictional_worker(person_id="CN-9000"))
        self.assert_api_error(404, self.store.save_worker, fictional_worker(id=str(uuid.uuid4()), version=1))
        self.assert_api_error(409, self.store.save_worker, fictional_worker(id=first["id"]))
        roundtrip = self.store.save_worker(first)["worker"]
        self.assertEqual(2, roundtrip["version"])
        self.assertEqual(50, len(self.store.bootstrap()["workers"]))

    def test_document_uniqueness_is_case_insensitive_including_archived(self):
        worker = self.store.save_worker(fictional_worker(cmnd=" DEMO-UNIQUE-ALPHA "))["worker"]
        before = self.counts()
        self.assert_api_error(409, self.store.save_worker, fictional_worker(cmnd="demo-unique-alpha"))
        self.assertEqual(before, self.counts())
        self.store.archive_worker({"id": worker["id"], "version": 1})
        self.assert_api_error(409, self.store.save_worker, fictional_worker(cmnd="Demo-Unique-Alpha"))
        for _ in range(2):
            self.store.save_worker(fictional_worker(cmnd=""))
        edited = self.store.save_worker(fictional_worker(cmnd="DEMO-UNIQUE-BETA"))["worker"]
        self.assert_api_error(409, self.store.save_worker, {"id": edited["id"], "version": 1, "cmnd": "demo-unique-alpha"})
        self.assertEqual(1, next(w["version"] for w in self.store.bootstrap()["workers"] if w["id"] == edited["id"]))

    def test_room_unit_relationship_and_unit_changes(self):
        worker = self.store.save_worker(fictional_worker())["worker"]
        self.assert_api_error(400, self.store.save_worker, {"id": worker["id"], "version": 1, "unit_id": "DSX03"})
        self.assert_api_error(400, self.store.save_worker, fictional_worker(phong_o="MISSING"))
        updated = self.store.save_worker({"id": worker["id"], "version": 1, "unit_id": "DSX03", "phong_o": "B01"})["worker"]
        self.assertEqual("DSX03", updated["unit_id"])
        self.assertEqual("B01", updated["phong_o"])
        self.assertEqual(worker["person_id"], updated["person_id"])
        updated = self.store.save_worker({"id": worker["id"], "version": 2, "unit_id": "NMCB", "phong_o": ""})["worker"]
        self.assertEqual("NMCB", updated["unit_id"])

    def test_transfer_requires_closed_gate_visit(self):
        worker = self.store.save_worker(fictional_worker())["worker"]
        event = {"worker_id": worker["id"], "direction": "in", "gate": "Cổng chính"}
        self.store.add_event(event)
        change = {"id": worker["id"], "version": 1, "unit_id": "DSX03", "phong_o": "B01"}
        before = self.counts()
        self.assert_api_error(409, self.store.save_worker, change)
        self.assertEqual(before, self.counts())
        self.store.add_event(dict(event, direction="out"))
        moved = self.store.save_worker(change)["worker"]
        self.assertEqual("DSX03", moved["unit_id"])
        self.assertEqual(worker["person_id"], moved["person_id"])

    def test_room_transfer_request_frees_room_until_approval(self):
        worker = self.store.save_worker(fictional_worker(phong_o="A02", chu_phong=True))["worker"]
        result = self.store.request_transfer({"worker_id": worker["id"], "version": 1, "to_room": "A03",
                                              "note": "Lý do hoàn toàn hư cấu"})
        transfer, moved = result["transfer"], result["worker"]
        self.assertEqual("pending", transfer["status"])
        self.assertEqual(("DSX02", "A02", "DSX02", "A03"), (transfer["from_unit"], transfer["from_room"],
                                                            transfer["to_unit"], transfer["to_room"]))
        self.assertEqual(("", False, 2), (moved["phong_o"], moved["chu_phong"], moved["version"]))
        self.assertEqual([transfer], self.store.bootstrap()["transfers"])
        self.assert_api_error(409, self.store.request_transfer,
                              {"worker_id": worker["id"], "version": 2, "to_room": "A04"})
        self.assert_api_error(409, self.store.save_worker,
                              {"id": worker["id"], "version": 2, "phong_o": "A04"})
        self.assertEqual([transfer], self.store.bootstrap()["transfers"])

    def test_room_transfer_validation_errors_leave_data_untouched(self):
        worker = self.store.save_worker(fictional_worker(phong_o="A02"))["worker"]
        before = self.store.bootstrap()
        self.assert_api_error(400, self.store.request_transfer,
                              {"worker_id": worker["id"], "version": 1, "to_room": "A02"})
        self.assert_api_error(400, self.store.request_transfer,
                              {"worker_id": worker["id"], "version": 1, "to_room": "MISSING"})
        self.assert_api_error(409, self.store.request_transfer,
                              {"worker_id": worker["id"], "version": 2, "to_room": "A03"})
        self.assert_api_error(404, self.store.request_transfer,
                              {"worker_id": str(uuid.uuid4()), "version": 1, "to_room": "A03"})
        self.assert_api_error(400, self.store.request_transfer,
                              {"worker_id": worker["id"], "version": 1, "to_room": "A03", "extra": 1})
        self.assertEqual(before, self.store.bootstrap())
        no_room = self.store.save_worker(fictional_worker(phong_o=""))["worker"]
        self.assert_api_error(400, self.store.request_transfer,
                              {"worker_id": no_room["id"], "version": 1, "to_room": "A03"})
        archived = self.store.save_worker(fictional_worker(phong_o=""))["worker"]
        self.store.archive_worker({"id": archived["id"], "version": 1})
        self.assert_api_error(409, self.store.request_transfer,
                              {"worker_id": archived["id"], "version": 2, "to_room": "A03"})

    def test_room_transfer_across_units_requires_closed_gate_visit(self):
        worker = self.store.save_worker(fictional_worker(phong_o="A02"))["worker"]
        event = {"worker_id": worker["id"], "direction": "in", "gate": "Cổng chính"}
        self.store.add_event(event)
        cross = {"worker_id": worker["id"], "version": 1, "to_room": "B02"}
        before = self.counts()
        self.assert_api_error(409, self.store.request_transfer, cross)
        self.assertEqual(before, self.counts())
        self.store.add_event(dict(event, direction="out"))
        transfer = self.store.request_transfer(cross)["transfer"]
        self.assertEqual(("DSX02", "DSX03"), (transfer["from_unit"], transfer["to_unit"]))

    def test_transfer_approval_moves_worker_and_rejection_keeps_room_empty(self):
        first = self.store.save_worker(fictional_worker(phong_o="A02"))["worker"]
        second = self.store.save_worker(fictional_worker(phong_o="A02"))["worker"]
        approved = self.store.request_transfer({"worker_id": first["id"], "version": 1, "to_room": "A03"})["transfer"]
        rejected = self.store.request_transfer({"worker_id": second["id"], "version": 1, "to_room": "A04"})["transfer"]
        result = self.store.decide_transfer({"id": approved["id"], "decision": "approve", "note": "Duyệt minh họa"})
        self.assertEqual(("approved", "Duyệt minh họa"), (result["transfer"]["status"], result["transfer"]["decision_note"]))
        self.assertEqual(("A03", 3), (result["worker"]["phong_o"], result["worker"]["version"]))
        result = self.store.decide_transfer({"id": rejected["id"], "decision": "reject"})
        self.assertEqual("rejected", result["transfer"]["status"])
        self.assertIsNone(result["worker"])
        workers = {w["id"]: w for w in self.store.bootstrap()["workers"]}
        self.assertEqual("A03", workers[first["id"]]["phong_o"])
        self.assertEqual("", workers[second["id"]]["phong_o"])
        self.assert_api_error(409, self.store.decide_transfer, {"id": approved["id"], "decision": "approve"})
        self.assert_api_error(404, self.store.decide_transfer, {"id": str(uuid.uuid4()), "decision": "approve"})
        self.assert_api_error(400, self.store.decide_transfer, {"id": rejected["id"], "decision": "maybe"})
        events = {item["event_type"] for item in self.store.bootstrap()["outbox"]}
        self.assertLessEqual({"transfer.requested", "transfer.approved", "transfer.rejected"}, events)

    def test_archiving_worker_cancels_pending_transfer(self):
        worker = self.store.save_worker(fictional_worker(phong_o="A02"))["worker"]
        transfer = self.store.request_transfer({"worker_id": worker["id"], "version": 1, "to_room": "A03"})["transfer"]
        self.store.archive_worker({"id": worker["id"], "version": 2})
        pending = self.store.bootstrap()["transfers"]
        self.assertEqual(1, len(pending))
        self.assertEqual("rejected", pending[0]["status"])
        self.assert_api_error(409, self.store.decide_transfer, {"id": transfer["id"], "decision": "approve"})

    def test_concurrent_transfer_decisions_have_one_winner(self):
        worker = self.store.save_worker(fictional_worker(phong_o="A02"))["worker"]
        transfer = self.store.request_transfer({"worker_id": worker["id"], "version": 1, "to_room": "A03"})["transfer"]
        def decide(decision):
            try:
                self.store.decide_transfer({"id": transfer["id"], "decision": decision})
                return "ok"
            except APIError as error:
                return error.status
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = Counter(pool.map(decide, ("approve", "reject")))
        self.assertEqual(1, results["ok"])
        self.assertEqual(1, results[409])
        self.assertEqual(1, sum(item["event_type"] in {"transfer.approved", "transfer.rejected"}
                                for item in self.store.bootstrap()["outbox"]))

    def test_room_leader_requires_active_nondependent_and_room(self):
        worker = self.store.save_worker(fictional_worker(chu_phong=True))["worker"]
        before = self.database_snapshot()
        for changes in ({"phong_o": ""}, {"loai": "Gia thuộc"}):
            with self.subTest(changes=changes):
                self.assert_api_error(400, self.store.save_worker, fictional_worker(chu_phong=True, **changes))
                self.assert_api_error(400, self.store.save_worker,
                                      dict(changes, id=worker["id"], version=1, chu_phong=True))
        self.assertEqual(before, self.database_snapshot())
        other = self.store.save_worker(fictional_worker(loai="Khác", phong_o="A03", chu_phong=True))["worker"]
        self.assertIs(other["chu_phong"], True)
        self.store.archive_worker({"id": worker["id"], "version": 1})
        archived = next(w for w in self.store.bootstrap()["workers"] if w["id"] == worker["id"])
        self.assertIs(archived["chu_phong"], False)
        before = self.database_snapshot()
        self.assert_api_error(409, self.store.save_worker, {"id": worker["id"], "version": 2, "chu_phong": True})
        self.assertEqual(before, self.database_snapshot())
        self.assertIs(self.store.save_worker(fictional_worker(chu_phong=True))["worker"]["chu_phong"], True)

    def test_room_leader_conflicts_are_scoped_and_require_explicit_resolution(self):
        first = self.store.save_worker(fictional_worker(chu_phong=True))["worker"]
        contender = self.store.save_worker(fictional_worker())["worker"]
        other_room = self.store.save_worker(fictional_worker(phong_o="A03", chu_phong=True))["worker"]
        other_unit = self.store.save_worker(fictional_worker(unit_id="DSX03", phong_o="B02", chu_phong=True))["worker"]
        factory = self.store.save_worker(fictional_worker(unit_id="NMCB", phong_o="C02", chu_phong=True))["worker"]
        first = self.store.save_worker({"id": first["id"], "version": 1, "ghi_chu": "Chủ phòng mẫu giữ nguyên"})["worker"]
        self.assertIs(first["chu_phong"], True)
        before = self.database_snapshot()
        message = self.assert_api_error(409, self.store.save_worker,
                                        {"id": contender["id"], "version": 1, "chu_phong": True})
        self.assertIn("chủ phòng hiện tại trước", message)
        self.assert_api_error(409, self.store.save_worker, fictional_worker(chu_phong=True))
        for target in (other_room, other_unit, factory):
            self.assert_api_error(409, self.store.save_worker, {
                "id": first["id"], "version": 2, "unit_id": target["unit_id"],
                "phong_o": target["phong_o"], "chu_phong": True,
            })
        self.assert_api_error(400, self.store.save_worker, {
            "id": first["id"], "version": 2, "unit_id": "DSX03", "phong_o": "A02", "chu_phong": True,
        })
        self.assertEqual(before, self.database_snapshot())
        self.store.save_worker({"id": first["id"], "version": 2, "chu_phong": False})
        promoted = self.store.save_worker({"id": contender["id"], "version": 1, "chu_phong": True})["worker"]
        self.assertIs(promoted["chu_phong"], True)
        current = {w["id"]: w for w in self.store.bootstrap()["workers"]}
        self.assertIs(current[first["id"]]["chu_phong"], False)
        for unaffected in (other_room, other_unit, factory):
            self.assertEqual(unaffected, current[unaffected["id"]])

    def test_room_leader_transfer_clears_unless_explicitly_reassigned(self):
        worker = self.store.save_worker(fictional_worker(chu_phong=True))["worker"]
        worker = self.store.save_worker({"id": worker["id"], "version": 1, "unit_id": " DSX02 ", "phong_o": " A02 "})["worker"]
        self.assertIs(worker["chu_phong"], True)
        cases = (
            ({"phong_o": "A03"}, False),
            ({"phong_o": "A04", "chu_phong": True}, True),
            ({"unit_id": "DSX03", "phong_o": "B02"}, False),
            ({"unit_id": "NMCB", "phong_o": "C02", "chu_phong": True}, True),
            ({"phong_o": ""}, False),
            ({"phong_o": "C01", "chu_phong": True}, True),
            ({"unit_id": "DSX02", "phong_o": "A01", "chu_phong": False}, False),
        )
        for changes, expected in cases:
            with self.subTest(changes=changes):
                previous = worker
                worker = self.store.save_worker(dict(changes, id=worker["id"], version=worker["version"]))["worker"]
                self.assertIs(worker["chu_phong"], expected)
                self.assertEqual(previous["person_id"], worker["person_id"])
                self.assertEqual(previous["version"] + 1, worker["version"])
        # Moving into an occupied leader's room as an ordinary resident is allowed.
        owner = self.store.save_worker(fictional_worker(unit_id="DSX03", phong_o="B02", chu_phong=True))["worker"]
        worker = self.store.save_worker({"id": worker["id"], "version": worker["version"], "chu_phong": True})["worker"]
        worker = self.store.save_worker({"id": worker["id"], "version": worker["version"], "unit_id": "DSX03", "phong_o": "B02"})["worker"]
        self.assertIs(worker["chu_phong"], False)
        self.assertEqual(owner, next(w for w in self.store.bootstrap()["workers"] if w["id"] == owner["id"]))
        self.assertIs(self.store.save_worker(fictional_worker(phong_o="A01", chu_phong=True))["worker"]["chu_phong"], True)

    def test_room_leader_inside_gate_guards_roll_back_transfers_and_archive(self):
        worker = self.store.save_worker(fictional_worker(chu_phong=True))["worker"]
        event = {"worker_id": worker["id"], "direction": "in", "gate": "Cổng chính"}
        self.store.add_event(event)
        change = {"id": worker["id"], "version": 1, "unit_id": "DSX03", "phong_o": "B02"}
        before = self.database_snapshot()
        for payload in (change, dict(change, chu_phong=True), dict(change, chu_phong=False)):
            self.assertIn("ra cổng", self.assert_api_error(409, self.store.save_worker, payload))
        self.assert_api_error(409, self.store.archive_worker, {"id": worker["id"], "version": 1})
        self.assertEqual(before, self.database_snapshot())
        self.store.add_event(dict(event, direction="out"))
        worker = self.store.save_worker(dict(change, chu_phong=True))["worker"]
        self.assertIs(worker["chu_phong"], True)
        self.store.archive_worker({"id": worker["id"], "version": 2})
        archived = next(w for w in Store(self.root / "data").bootstrap()["workers"] if w["id"] == worker["id"])
        self.assertEqual(("archived", "", False, 3), (archived["status"], archived["phong_o"], archived["chu_phong"], archived["version"]))

    def test_concurrent_room_leader_claims_have_one_winner_and_one_audit(self):
        workers = [self.store.save_worker(fictional_worker())["worker"] for _ in range(6)]
        before = self.database_snapshot()
        barrier = threading.Barrier(len(workers))

        def promote(worker):
            barrier.wait()
            try:
                self.store.save_worker({"id": worker["id"], "version": 1, "chu_phong": True})
                return 200
            except APIError as error:
                return error.status

        with ThreadPoolExecutor(max_workers=6) as executor:
            self.assertEqual({200: 1, 409: 5}, Counter(executor.map(promote, workers)))
        after = self.database_snapshot()
        self.assertEqual(before["counters"], after["counters"])
        self.assertEqual(before["audit"], after["audit"][:-1])
        self.assertEqual(before["outbox"], after["outbox"][:-1])
        current = {w["id"]: w for w in self.store.bootstrap()["workers"]}
        self.assertEqual(1, sum(current[w["id"]]["chu_phong"] for w in workers))
        for worker in workers:
            if current[worker["id"]]["chu_phong"]:
                self.assertEqual(2, current[worker["id"]]["version"])
            else:
                self.assertEqual(worker, current[worker["id"]])

    def test_added_fields_default_roundtrip_partial_update_and_clear(self):
        default = self.store.save_worker({"ten_that": "Hồ sơ mẫu mặc định"})["worker"]
        self.assertEqual(ADDED_DEFAULTS, {field: default[field] for field in ADDED_DEFAULTS})
        self.assertIs(default["chu_phong"], False)
        details = fictional_details()
        payload = {field: f"  {value}  " if isinstance(value, str) else value for field, value in details.items()}
        payload["nhom_mau"] = "  custom  "
        worker = self.store.save_worker(fictional_worker(**payload))["worker"]
        self.assertEqual(details, {field: worker[field] for field in details})
        changed = dict.fromkeys(ADDED_TEXT_FIELDS, "Nội dung mẫu đã sửa")
        changed.update(chu_phong=False, nhom_mau="AB-", ngay_ky_luat="2025-01-02")
        worker = self.store.save_worker(dict(changed, id=worker["id"], version=1))["worker"]
        self.assertEqual(changed, {field: worker[field] for field in changed})
        worker = self.store.save_worker({"id": worker["id"], "version": 2, "ten_that": "Mẫu giữ trường mở rộng"})["worker"]
        self.assertEqual(changed, {field: worker[field] for field in changed})
        persisted = next(w for w in Store(self.root / "data").bootstrap()["workers"] if w["id"] == worker["id"])
        self.assertEqual(worker, persisted)
        worker = self.store.save_worker(dict(ADDED_DEFAULTS, id=worker["id"], version=3))["worker"]
        self.assertEqual(ADDED_DEFAULTS, {field: worker[field] for field in ADDED_DEFAULTS})
        self.assertEqual(4, worker["version"])

    def test_all_directory_units_and_eight_teams_are_accepted(self):
        for unit in self.store.bootstrap()["directory"]["units"]:
            for team in (f"Tổ {i}" for i in range(1, 9)):
                with self.subTest(unit=unit["id"], team=team):
                    worker = self.store.save_worker(fictional_worker(unit_id=unit["id"], to=team, phong_o=""))["worker"]
                    self.assertEqual((unit["id"], team), (worker["unit_id"], worker["to"]))

    def test_added_field_invalid_types_limits_and_controls_are_atomic(self):
        worker = self.store.save_worker(fictional_worker())["worker"]
        before = self.database_snapshot()
        for field in ADDED_TEXT_FIELDS:
            maximum = 2000 if field == "ghi_chu_ky_luat" else 8 if field == "nhom_mau" else 500 if field in {"noi_sinh", "dia_chi", "chi_tiet_noi_o"} else 200
            for value in (None, True, 1, 1.5, [], {}, "x" * (maximum + 1), "Mẫu\x00", "\ud800"):
                for base in (fictional_worker(), {"id": worker["id"], "version": 1}):
                    with self.subTest(field=field, value=repr(value)[:40], update="id" in base):
                        self.assert_api_error(400, self.store.save_worker, dict(base, **{field: value}))
            if field != "ghi_chu_ky_luat":
                self.assert_api_error(400, self.store.save_worker, fictional_worker(**{field: "Mẫu\nMẫu"}))
        for field in ("chu_phong", "_manuallyRated"):
            for value in (None, 0, 1, -1, 1.0, "true", "false", [], {}):
                for base in (fictional_worker(), {"id": worker["id"], "version": 1, "phong_o": "A03"}):
                    with self.subTest(field=field, value=value, update="id" in base):
                        self.assert_api_error(400, self.store.save_worker, dict(base, **{field: value}))
        for field in ("ngay_sinh", "ngay_ky_luat"):
            for value in ("2023-02-29", "2024-13-01", "2024-2-29", "20240229", "2024-02-29T00:00:00Z"):
                with self.subTest(field=field, value=value):
                    self.assert_api_error(400, self.store.save_worker, fictional_worker(**{field: value}))
        for field in ("age", "tuoi"):
            self.assert_api_error(400, self.store.save_worker, fictional_worker(**{field: 34}))
        self.assertEqual(before, self.database_snapshot())

    def test_added_text_boundaries_blood_normalization_and_multiline_notes(self):
        bounded = set(ADDED_TEXT_FIELDS) - {"nhom_mau", "ghi_chu_ky_luat", "ngay_ky_luat"}
        fields = dict.fromkeys(bounded, "x" * 200)
        fields.update(nhom_mau="  custom12  ", ghi_chu_ky_luat="Mẫu\n\r\t" + "x" * 1994, ngay_ky_luat="2024-02-29")
        worker = self.store.save_worker(fictional_worker(**fields))["worker"]
        self.assertEqual("CUSTOM12", worker["nhom_mau"])
        self.assertEqual(fields["ghi_chu_ky_luat"], worker["ghi_chu_ky_luat"])
        self.assertEqual(2000, len(worker["ghi_chu_ky_luat"]))
        for field in bounded:
            self.assertEqual(fields[field], worker[field])
        for blood in ("ab+", "o-", "rh null", "", "  "):
            with self.subTest(blood=blood):
                saved = self.store.save_worker(fictional_worker(nhom_mau=blood))["worker"]
                self.assertEqual(blood.strip().upper(), saved["nhom_mau"])
        long_fields = dict.fromkeys(("noi_sinh", "dia_chi", "chi_tiet_noi_o"), "x" * 500)
        long_worker = self.store.save_worker(fictional_worker(**long_fields))["worker"]
        self.assertEqual(long_fields, {field: long_worker[field] for field in long_fields})
        before = self.database_snapshot()
        # Uppercasing can expand Unicode characters; the stored value must still fit.
        self.assert_api_error(400, self.store.save_worker, fictional_worker(nhom_mau="ß" * 5))
        self.assert_api_error(400, self.store.save_worker, fictional_worker(ghi_chu_ky_luat="x" * 2001))
        self.assert_api_error(400, self.store.save_worker, fictional_worker(dia_chi="x" * 501))
        self.assertEqual(before, self.database_snapshot())

    def test_ratings_accept_one_through_five_and_null_for_both_fields(self):
        for value in (1, 2, 3, 4, 5, None):
            with self.subTest(value=value):
                worker = self.store.save_worker(fictional_worker(_manuallyRated=True, danh_gia_ky_nang=value,
                                                                danh_gia_dao_duc=value))["worker"]
                self.assertEqual((value, value), (worker["danh_gia_ky_nang"], worker["danh_gia_dao_duc"]))
                self.assertIs(worker["_manuallyRated"], True)
                worker = self.store.save_worker({"id": worker["id"], "version": 1, "ghi_chu": "Giữ đánh giá mẫu"})["worker"]
                self.assertEqual((value, value), (worker["danh_gia_ky_nang"], worker["danh_gia_dao_duc"]))
                worker = self.store.save_worker({"id": worker["id"], "version": 2, "_manuallyRated": False})["worker"]
                self.assertEqual((3, 3), (worker["danh_gia_ky_nang"], worker["danh_gia_dao_duc"]))
                self.assertIs(worker["_manuallyRated"], False)

    def test_invalid_ratings_for_both_fields_never_write_or_increment_counters(self):
        worker = self.store.save_worker(fictional_worker())["worker"]
        before = self.database_snapshot()
        for field in ("danh_gia_ky_nang", "danh_gia_dao_duc"):
            for value in (True, False, -1, 0, 6, 5.0, "5", [], {}):
                for kind in ("Lao động", "Gia thuộc", "Khác"):
                    for manual in (True, False):
                        with self.subTest(field=field, value=value, kind=kind, manual=manual):
                            changes = {field: value, "loai": kind, "_manuallyRated": manual}
                            self.assert_api_error(400, self.store.save_worker, fictional_worker(**changes))
                            self.assert_api_error(400, self.store.save_worker, dict(changes, id=worker["id"], version=1))
        self.assertEqual(before, self.database_snapshot())

    def test_dependents_clear_all_discipline_and_ratings_on_create_and_update(self):
        details = fictional_details(chu_phong=False)
        worker = self.store.save_worker(fictional_worker(**details, loai="Gia thuộc", _manuallyRated=True,
                                                        danh_gia_ky_nang=5, danh_gia_dao_duc=5))["worker"]
        for changes in ({}, dict(DISCIPLINE_SAMPLE, _manuallyRated=True, danh_gia_ky_nang=5, danh_gia_dao_duc=None)):
            worker = self.store.save_worker(dict(changes, id=worker["id"], version=worker["version"]))["worker"]
            self.assertIsNone(worker["danh_gia_ky_nang"])
            self.assertIsNone(worker["danh_gia_dao_duc"])
            self.assertIs(worker["_manuallyRated"], False)
            self.assertTrue(all(worker[field] == "" for field in DISCIPLINE_SAMPLE))
            self.assertEqual(details["dia_chi"], worker["dia_chi"])
        worker = self.store.save_worker({"id": worker["id"], "version": worker["version"], "loai": "Lao động"})["worker"]
        self.assertEqual((3, 3), (worker["danh_gia_ky_nang"], worker["danh_gia_dao_duc"]))
        self.assertTrue(all(worker[field] == "" for field in DISCIPLINE_SAMPLE))
        adult = self.store.save_worker(fictional_worker(**fictional_details(), _manuallyRated=True,
                                                       danh_gia_ky_nang=5, danh_gia_dao_duc=5))["worker"]
        dependent = self.store.save_worker({"id": adult["id"], "version": 1, "loai": "Gia thuộc"})["worker"]
        self.assertTrue(all(dependent[field] == "" for field in DISCIPLINE_SAMPLE))
        self.assertIsNone(dependent["danh_gia_ky_nang"])
        self.assertIsNone(dependent["danh_gia_dao_duc"])
        self.assertIs(dependent["_manuallyRated"], False)
        self.assertIs(dependent["chu_phong"], False)
        self.assertEqual(dependent, next(w for w in Store(self.root / "data").bootstrap()["workers"] if w["id"] == adult["id"]))

    def test_ratings_rules_and_explicit_null(self):
        worker = self.store.save_worker(fictional_worker(danh_gia_ky_nang=1, danh_gia_dao_duc=None))["worker"]
        self.assertEqual((3, 3), (worker["danh_gia_ky_nang"], worker["danh_gia_dao_duc"]))
        worker = self.store.save_worker({"id": worker["id"], "version": 1, "_manuallyRated": True,
                                         "danh_gia_ky_nang": 1, "danh_gia_dao_duc": None})["worker"]
        worker = self.store.save_worker({"id": worker["id"], "version": 2, "ghi_chu": "Mẫu giữ đánh giá"})["worker"]
        self.assertEqual(1, worker["danh_gia_ky_nang"])
        self.assertIsNone(worker["danh_gia_dao_duc"])
        dependent = self.store.save_worker(fictional_worker(loai="Gia thuộc", _manuallyRated=True, danh_gia_ky_nang=1))["worker"]
        self.assertIsNone(dependent["danh_gia_ky_nang"])
        self.assertIsNone(dependent["danh_gia_dao_duc"])
        self.assertIs(dependent["_manuallyRated"], False)
        dependent = self.store.save_worker({"id": dependent["id"], "version": 1, "loai": "Lao động"})["worker"]
        self.assertEqual((3, 3), (dependent["danh_gia_ky_nang"], dependent["danh_gia_dao_duc"]))

    def test_invalid_worker_schema_types_enums_lengths_and_dates(self):
        bad = [
            [], None, "text", {}, {"unknown": 1}, fictional_worker(ten_that=" "), fictional_worker(ten_that=12),
            fictional_worker(ten_ho_so=[]), fictional_worker(cmnd=True), fictional_worker(so_dt=None),
            fictional_worker(loai="Other"), fictional_worker(unit_id="OTHER"), fictional_worker(to="Tổ 9"),
            fictional_worker(gioi_tinh="X"), fictional_worker(quan_he="Người lạ"), fictional_worker(phong_o=4),
            fictional_worker(danh_gia_ky_nang=True), fictional_worker(danh_gia_ky_nang=0),
            fictional_worker(danh_gia_dao_duc=6), fictional_worker(danh_gia_dao_duc=1.0),
            fictional_worker(danh_gia_dao_duc="3"), fictional_worker(_manuallyRated=1),
            fictional_worker(ngay_sinh="2023-02-29"), fictional_worker(ngay_sinh="19900512"),
            fictional_worker(ngay_sinh="1990-05-12T00:00:00Z"), fictional_worker(ten_that="x" * 201),
            fictional_worker(ghi_chu="x" * 2001), fictional_worker(ten_that="Mẫu\x00"),
            fictional_worker(ten_that="\ud800"), fictional_worker(id=[]), fictional_worker(id="bad-id"),
            fictional_worker(status="archived"), fictional_worker(version=1),
        ]
        before = self.counts()
        for payload in bad:
            with self.subTest(payload=repr(payload)[:150]):
                self.assert_api_error(400, self.store.save_worker, payload)
        self.assertEqual(before, self.counts())
        worker = self.store.save_worker(fictional_worker(ten_that="x" * 200, ghi_chu="x" * 2000, ngay_sinh="2024-02-29"))["worker"]
        self.assertEqual("CN-0049", worker["person_id"])

    def test_missing_stale_and_non_integer_versions_conflict(self):
        worker = self.store.bootstrap()["workers"][0]
        for version in (None, 0, 2, "1", True, 1.0, [], {}):
            for operation in (self.store.save_worker, self.store.archive_worker):
                with self.subTest(version=version, operation=operation.__name__):
                    self.assert_api_error(409, operation, {"id": worker["id"], "version": version})
        self.assert_api_error(409, self.store.save_worker, {"id": worker["id"]})
        self.assert_api_error(409, self.store.archive_worker, {"id": worker["id"]})

    def test_concurrent_edits_allow_exactly_one_writer(self):
        worker = self.store.save_worker(fictional_worker())["worker"]
        before = self.counts()
        barrier = threading.Barrier(8)

        def update(index):
            barrier.wait()
            try:
                self.store.save_worker({"id": worker["id"], "version": 1, "ghi_chu": f"Mẫu cập nhật {index}"})
                return 200
            except APIError as error:
                return error.status

        with ThreadPoolExecutor(max_workers=8) as executor:
            statuses = list(executor.map(update, range(8)))
        self.assertEqual({200: 1, 409: 7}, Counter(statuses))
        after = self.counts()
        self.assertEqual(before["audit"] + 1, after["audit"])
        self.assertEqual(before["outbox"] + 1, after["outbox"])
        current = next(w for w in self.store.bootstrap()["workers"] if w["id"] == worker["id"])
        self.assertEqual(2, current["version"])

    def test_gate_duplicate_checks_archive_guard_and_event_immutability(self):
        worker = self.store.save_worker(fictional_worker())["worker"]
        payload = {"worker_id": worker["id"], "direction": "out", "gate": "Cổng chính"}
        self.assert_api_error(409, self.store.add_event, payload)
        payload["direction"] = "in"
        incoming = self.store.add_event(payload)["event"]
        self.assertEqual("manual", incoming["method"])
        self.assert_api_error(409, self.store.add_event, payload)
        self.assertEqual("Cần ghi nhận ra cổng trước khi lưu trữ",
                         self.assert_api_error(409, self.store.archive_worker, {"id": worker["id"], "version": 1}))
        self.store.save_worker({"id": worker["id"], "version": 1, "ten_that": "Hồ sơ mẫu đổi tên"})
        payload.update(direction="out", gate="Cổng khu ở")
        outgoing = self.store.add_event(payload)["event"]
        self.assertEqual("Cổng khu ở", outgoing["gate"])
        self.assert_api_error(409, self.store.add_event, payload)
        self.store.archive_worker({"id": worker["id"], "version": 2})
        self.assert_api_error(409, self.store.add_event, dict(payload, direction="in"))
        events = self.store.bootstrap()["events"]
        self.assertEqual(incoming, next(e for e in events if e["id"] == incoming["id"]))
        self.assertEqual(outgoing, next(e for e in events if e["id"] == outgoing["id"]))

    def test_concurrent_gate_and_archive_operations_are_serialized(self):
        worker = self.store.save_worker(fictional_worker())["worker"]
        barrier = threading.Barrier(6)

        def enter(_):
            barrier.wait()
            try:
                self.store.add_event({"worker_id": worker["id"], "direction": "in", "gate": "Cổng chính"})
                return 200
            except APIError as error:
                return error.status

        with ThreadPoolExecutor(max_workers=6) as executor:
            self.assertEqual({200: 1, 409: 5}, Counter(executor.map(enter, range(6))))
        another = self.store.save_worker(fictional_worker())["worker"]
        barrier = threading.Barrier(2)

        def race(operation):
            barrier.wait()
            try:
                if operation == "archive":
                    self.store.archive_worker({"id": another["id"], "version": 1})
                else:
                    self.store.add_event({"worker_id": another["id"], "direction": "in", "gate": "Cổng chính"})
                return 200
            except APIError as error:
                return error.status

        with ThreadPoolExecutor(max_workers=2) as executor:
            self.assertEqual({200: 1, 409: 1}, Counter(executor.map(race, ("archive", "enter"))))

    def test_invalid_gate_payloads(self):
        worker = self.store.bootstrap()["workers"][0]
        valid = {"worker_id": worker["id"], "direction": "in", "gate": "Cổng chính"}
        for payload in ({}, [], dict(valid, direction="both"), dict(valid, gate="Unknown"),
                        dict(valid, worker_id=1), dict(valid, method="qr"), dict(valid, at="2020-01-01")):
            with self.subTest(payload=payload):
                self.assert_api_error(400, self.store.add_event, payload)
        self.assert_api_error(404, self.store.add_event, dict(valid, worker_id=str(uuid.uuid4())))

    def test_visitors_enforce_transitions_and_versioning(self):
        visitor = self.store.add_visitor(fictional_visitor(expected="2000-01-01"))["visitor"]
        self.assertEqual("registered", visitor["status"])
        self.assert_api_error(409, self.store.transition_visitor, {"id": visitor["id"], "version": 1, "status": "left"})
        self.assert_api_error(409, self.store.transition_visitor, {"id": visitor["id"], "status": "inside"})
        inside = self.store.transition_visitor({"id": visitor["id"], "version": 1, "status": "inside"})["visitor"]
        self.assertEqual(2, inside["version"])
        self.assert_api_error(409, self.store.transition_visitor, {"id": visitor["id"], "version": 1, "status": "left"})
        self.assert_api_error(409, self.store.transition_visitor, {"id": visitor["id"], "version": 2, "status": "inside"})
        left = self.store.transition_visitor({"id": visitor["id"], "version": 2, "status": "left"})["visitor"]
        self.assertEqual(3, left["version"])
        self.assertEqual(visitor["created_at"], left["created_at"])
        self.assert_api_error(409, self.store.transition_visitor, {"id": visitor["id"], "version": 3, "status": "inside"})
        persisted = next(v for v in Store(self.root / "data").bootstrap()["visitors"] if v["id"] == visitor["id"])
        self.assertEqual(left, persisted)

    def test_invalid_visitors_and_unknown_visitors(self):
        for changes in ({"expected": "2024-13-01"}, {"expected": ""}, {"expected": "20240101"},
                        {"expected": None}, {"name": ""}, {"name": 3}, {"company": False},
                        {"purpose": []}, {"host": ""}, {"unit_id": "OTHER"}, {"company": "x" * 201},
                        {"extra": "not allowed"}):
            with self.subTest(changes=changes):
                self.assert_api_error(400, self.store.add_visitor, fictional_visitor(**changes))
        self.assert_api_error(400, self.store.add_visitor, {"name": "Mẫu"})
        self.assert_api_error(404, self.store.transition_visitor, {"id": str(uuid.uuid4()), "version": 1, "status": "inside"})
        self.assert_api_error(400, self.store.transition_visitor, {"id": str(uuid.uuid4()), "version": 1, "status": "registered"})

    def test_concurrent_visitor_transitions_have_one_winner(self):
        visitor = self.store.add_visitor(fictional_visitor())["visitor"]
        barrier = threading.Barrier(4)

        def transition(_):
            barrier.wait()
            try:
                self.store.transition_visitor({"id": visitor["id"], "version": 1, "status": "inside"})
                return 200
            except APIError as error:
                return error.status

        with ThreadPoolExecutor(max_workers=4) as executor:
            self.assertEqual({200: 1, 409: 3}, Counter(executor.map(transition, range(4))))

    def test_mutation_audit_outbox_roll_back_together(self):
        worker = self.store.save_worker(fictional_worker(**fictional_details()))["worker"]
        visitor = self.store.add_visitor(fictional_visitor())["visitor"]
        operations = (
            (self.store.save_worker, fictional_worker()),
            (self.store.save_worker, {"id": worker["id"], "version": 1, "ghi_chu": "Mẫu không được lưu"}),
            (self.store.save_worker, {"id": worker["id"], "version": 1, "loai": "Gia thuộc"}),
            (self.store.save_worker, {"id": worker["id"], "version": 1, "unit_id": "DSX03", "phong_o": "B02"}),
            (self.store.save_worker, {"id": worker["id"], "version": 1, "phong_o": "A03", "chu_phong": True}),
            (self.store.archive_worker, {"id": worker["id"], "version": 1}),
            (self.store.add_event, {"worker_id": worker["id"], "direction": "in", "gate": "Cổng chính"}),
            (self.store.add_visitor, fictional_visitor()),
            (self.store.transition_visitor, {"id": visitor["id"], "version": 1, "status": "inside"}),
        )
        original_record = self.store._record

        def fail_after_record(*args, **kwargs):
            original_record(*args, **kwargs)
            raise RuntimeError("Simulated failure after audit and outbox")

        for operation, payload in operations:
            with self.subTest(operation=operation.__name__):
                before = self.store.bootstrap()
                with patch.object(self.store, "_record", side_effect=fail_after_record):
                    with self.assertRaises(RuntimeError):
                        operation(payload)
                self.assertEqual(before, self.store.bootstrap())

    def test_outbox_has_only_identifiers_and_draft_contract(self):
        worker = self.store.save_worker(fictional_worker(**fictional_details(), cmnd="DEMO-OUTBOX-EXCLUSION",
                                                        ten_that="Hồ sơ mẫu bí danh kiểm thử"))["worker"]
        data = self.store.bootstrap()
        keys = {"event_id", "entity_id", "person_id", "unit_id", "entity_version", "event_type", "occurred_at", "status"}
        self.assertEqual(len(data["outbox"]), len({e["event_id"] for e in data["outbox"]}))
        for item in data["outbox"]:
            self.assertEqual(keys, set(item))
            self.assertEqual("pending", item["status"])
            self.assertIs(type(item["entity_version"]), int)
        serialized = json.dumps(data["outbox"], ensure_ascii=False)
        for sensitive in (worker["cmnd"], worker["ten_that"], "cmnd", "ten_that", "company", "name", "so_dt"):
            self.assertNotIn(sensitive, serialized)
        for field in ADDED_TEXT_FIELDS:
            self.assertNotIn(field, serialized)
            self.assertNotIn(json.dumps(worker[field], ensure_ascii=False), serialized)
        self.assertTrue(all(a["actor"] == "Phiên demo cục bộ" for a in data["audit"]))
        contract = self.store.contract()
        self.assertEqual("1.0", contract["schema_version"])
        self.assertEqual("draft", contract["status"])
        self.assertEqual("Chưa cấu hình", contract["transport"])
        self.assertEqual("cn-workforce", contract["source"])
        self.assertEqual("pm-quan-tri-hop-nhat", contract["target"])
        for required in ("SSO", "RBAC", "HMAC", "TLS", "consent", "retention", "event_id", "optimistic"):
            self.assertIn(required, " ".join(contract["notes"]))
        self.assertIn("C2-xxxx", contract["master_data"]["id_cards"])
        self.assertIn("KH-ddmmyy", contract["master_data"]["visitor_passes"])

    def test_existing_synthetic_json_and_backend_source_are_unchanged(self):
        legacy_fixture = self.root / "unrelated-fixture.json"
        original = b'{"source":"fictional-test-only","workers":[]}'
        legacy_fixture.write_bytes(original)
        before = {name: hashlib.sha256((PROJECT_DIR / name).read_bytes()).hexdigest() for name in ("app.py", "store.py")}
        store = Store(self.root)
        store.save_worker(fictional_worker())
        store.bootstrap()
        self.assertEqual(original, legacy_fixture.read_bytes())
        after = {name: hashlib.sha256((PROJECT_DIR / name).read_bytes()).hexdigest() for name in ("app.py", "store.py")}
        self.assertEqual(before, after)


class HTTPTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="cn-workforce-http-test-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.static = self.root / "static"
        self.static.mkdir()
        (self.static / "assets" / "icons").mkdir(parents=True)
        (self.static / "index.html").write_bytes(b"<!doctype html><title>Fictional test fixture</title>")
        (self.static / "app.js").write_bytes(b"'use strict';")
        (self.static / "qr.js").write_bytes(b"'use strict';")
        (self.static / "styles.css").write_bytes(b"body { color: #123; }")
        (self.static / "assets" / "icons" / "marker.svg").write_bytes(b'<svg xmlns="http://www.w3.org/2000/svg"/>')
        for filename in ("app.py", "store.py", ".env"):
            (self.static / filename).write_bytes(b"FICTIONAL_NONPUBLIC_FIXTURE")
        (self.static / ".local").mkdir()
        (self.static / ".local" / "demo.sqlite3").write_bytes(b"FICTIONAL_NONPUBLIC_FIXTURE")
        self.server = create_server(port=0, data_dir=self.root / "data", static_root=self.static)
        self.thread = threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True)
        self.thread.start()
        self.addCleanup(self.stop_server)
        self.port = self.server.server_port
        self.host = f"127.0.0.1:{self.port}"
        self.origin = f"http://{self.host}"

    def stop_server(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=3)

    def request(self, method, path, payload=None, headers=None, body=None):
        values = {"Host": self.host}
        if method == "POST":
            values.update({"Origin": self.origin, "Content-Type": "application/json"})
        for key, value in (headers or {}).items():
            if value is None:
                values.pop(key, None)
            else:
                values[key] = value
        if payload is not None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        try:
            connection.request(method, path, body=body, headers=values)
            response = connection.getresponse()
            return response.status, dict(response.getheaders()), response.read()
        finally:
            connection.close()

    def api(self, method, path, payload=None, expected=200, headers=None, body=None):
        status, response_headers, content = self.request(method, path, payload=payload, headers=headers, body=body)
        self.assertEqual(expected, status, content.decode("utf-8", errors="replace"))
        self.assertEqual("no-store", response_headers["Cache-Control"])
        self.assertEqual("nosniff", response_headers["X-Content-Type-Options"])
        self.assertEqual("DENY", response_headers["X-Frame-Options"])
        self.assertNotIn("Access-Control-Allow-Origin", response_headers)
        self.assertNotIn("Access-Control-Allow-Credentials", response_headers)
        return json.loads(content)

    def raw_request(self, headers, method="POST", path="/api/v1/workers", body=b"{}"):
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        try:
            connection.putrequest(method, path, skip_host=True, skip_accept_encoding=True)
            for key, value in headers:
                connection.putheader(key, value)
            connection.endheaders(body)
            response = connection.getresponse()
            return response.status, response.read()
        finally:
            connection.close()

    def test_bootstrap_contract_security_headers_and_loopback_binding(self):
        self.assertEqual("127.0.0.1", self.server.server_address[0])
        self.assertGreater(self.port, 0)
        data = self.api("GET", "/api/v1/bootstrap")
        self.assertEqual(48, len(data["workers"]))
        self.assertEqual([f"DSX{number:02d}" for number in range(1, 9)] + ["NMCB"],
                         [u["id"] for u in data["directory"]["units"]])
        self.assertEqual([f"Tổ {i}" for i in range(1, 9)], data["directory"]["teams"])
        self.assertEqual(ADDED_DEFAULTS, {field: data["workers"][0][field] for field in ADDED_DEFAULTS})
        contract = self.api("GET", "/api/v1/contract")
        self.assertEqual("draft", contract["status"])
        status, headers, content = self.request("GET", "/api/v1/bootstrap")
        self.assertEqual(200, status)
        self.assertEqual(len(content), int(headers["Content-Length"]))
        self.assertIn("script-src 'self'", headers["Content-Security-Policy"])
        self.assertIn("style-src 'self' 'unsafe-inline'", headers["Content-Security-Policy"])
        self.assertIn("frame-ancestors 'none'", headers["Content-Security-Policy"])
        self.assertNotIn("Python", headers["Server"])
        self.assertEqual("no-referrer", headers["Referrer-Policy"])

    def test_all_mutating_endpoints_and_persistence(self):
        worker = self.api("POST", "/api/v1/workers", fictional_worker())["worker"]
        worker = self.api("POST", "/api/v1/workers", {"id": worker["id"], "version": 1, "ten_that": "Hồ sơ mẫu qua HTTP"})["worker"]
        self.assertEqual(2, worker["version"])
        self.api("POST", "/api/v1/workers", {"id": worker["id"], "version": 1}, expected=409)
        event = self.api("POST", "/api/v1/events", {"worker_id": worker["id"], "direction": "in", "gate": "Cổng chính"})["event"]
        self.assertEqual("manual", event["method"])
        self.api("POST", "/api/v1/workers/archive", {"id": worker["id"], "version": 2}, expected=409)
        self.api("POST", "/api/v1/events", {"worker_id": worker["id"], "direction": "out", "gate": "Cổng khu ở"})
        self.assertEqual({"ok": True}, self.api("POST", "/api/v1/workers/archive", {"id": worker["id"], "version": 2}))
        visitor = self.api("POST", "/api/v1/visitors", fictional_visitor())["visitor"]
        visitor = self.api("POST", "/api/v1/visitors/transition", {"id": visitor["id"], "version": 1, "status": "inside"})["visitor"]
        self.assertEqual(2, visitor["version"])
        visitor = self.api("POST", "/api/v1/visitors/transition", {"id": visitor["id"], "version": 2, "status": "left"})["visitor"]
        persisted = Store(self.root / "data").bootstrap()
        self.assertEqual("archived", next(w for w in persisted["workers"] if w["id"] == worker["id"])["status"])
        self.assertEqual(visitor, next(v for v in persisted["visitors"] if v["id"] == visitor["id"]))

    def test_room_transfer_endpoint_and_external_decision(self):
        worker = self.api("POST", "/api/v1/workers", fictional_worker(phong_o="A02"))["worker"]
        transfer = self.api("POST", "/api/v1/transfers", {
            "worker_id": worker["id"], "version": 1, "to_room": "A03", "note": "Mẫu hư cấu",
        })["transfer"]
        self.assertEqual("pending", transfer["status"])
        self.api("GET", "/api/v1/transfers", expected=405)
        self.api("POST", "/api/v1/transfers", {"worker_id": worker["id"], "version": 2, "to_room": "A04"}, expected=409)
        data = self.api("GET", "/api/v1/bootstrap")
        self.assertEqual([transfer["id"]], [item["id"] for item in data["transfers"]])
        self.assertEqual("", next(w for w in data["workers"] if w["id"] == worker["id"])["phong_o"])
        payload = {"id": transfer["id"], "decision": "approve"}
        self.api("POST", "/api/v1/transfers/decision", payload, expected=404)
        with patch.dict(os.environ, {"CN_SYNC_TOKEN": "t" * 32}):
            self.api("POST", "/api/v1/transfers/decision", payload, expected=401)
            self.api("POST", "/api/v1/transfers/decision", payload, expected=401,
                     headers={"Authorization": "Bearer " + "u" * 32, "Origin": None})
            decided = self.api("POST", "/api/v1/transfers/decision", payload,
                               headers={"Authorization": "Bearer " + "t" * 32, "Origin": None})
        self.assertEqual("approved", decided["transfer"]["status"])
        self.assertEqual("A03", decided["worker"]["phong_o"])
        persisted = Store(self.root / "data").bootstrap()
        self.assertEqual("A03", next(w for w in persisted["workers"] if w["id"] == worker["id"])["phong_o"])

    def test_extended_worker_fields_ratings_and_leader_conflicts_over_http(self):
        details = fictional_details()
        worker = self.api("POST", "/api/v1/workers", fictional_worker(
            **details, to="Tổ 8", _manuallyRated=True, danh_gia_ky_nang=5, danh_gia_dao_duc=5,
        ))["worker"]
        self.assertEqual(details, {field: worker[field] for field in details})
        self.assertEqual((5, 5), (worker["danh_gia_ky_nang"], worker["danh_gia_dao_duc"]))
        before = self.api("GET", "/api/v1/bootstrap")
        conflict = self.api("POST", "/api/v1/workers", fictional_worker(chu_phong=True), expected=409)
        self.assertFalse(conflict["ok"])
        for changes in ({"chu_phong": 1}, {"danh_gia_ky_nang": 6}, {"danh_gia_dao_duc": -1},
                        {"ghi_chu_ky_luat": "x" * 2001}):
            self.api("POST", "/api/v1/workers", dict(changes, id=worker["id"], version=1), expected=400)
        self.assertEqual(before, self.api("GET", "/api/v1/bootstrap"))
        worker = self.api("POST", "/api/v1/workers", {
            "id": worker["id"], "version": 1, "danh_gia_ky_nang": None, "danh_gia_dao_duc": None,
        })["worker"]
        self.assertIsNone(worker["danh_gia_ky_nang"])
        self.assertIsNone(worker["danh_gia_dao_duc"])
        worker = self.api("POST", "/api/v1/workers", {"id": worker["id"], "version": 2, "loai": "Gia thuộc"})["worker"]
        self.assertTrue(all(worker[field] == "" for field in DISCIPLINE_SAMPLE))
        self.assertIs(worker["_manuallyRated"], False)
        self.assertIs(worker["chu_phong"], False)

    def test_host_allowlist_rejects_rebinding_and_duplicate_hosts(self):
        for host in ("evil.example", "127.0.0.1", "localhost", "0.0.0.0:" + str(self.port),
                     "localhost:0", "[::1]:" + str(self.port), self.host + ".evil.example"):
            with self.subTest(host=host):
                self.api("GET", "/api/v1/bootstrap", headers={"Host": host}, expected=403)
        self.api("GET", "/api/v1/bootstrap", headers={"Host": f"localhost:{self.port}"})
        for headers in ([], [("Host", self.host), ("Host", self.host)]):
            status, _ = self.raw_request(headers, method="GET", path="/api/v1/bootstrap", body=None)
            self.assertEqual(403, status)

    def test_origin_required_and_strict_for_mutations(self):
        before = self.server.store.bootstrap()
        for origin in (None, "null", "https://evil.example", f"http://localhost:{self.port + 1}",
                       f"https://{self.host}", self.origin + "/", self.origin + ".evil.example", self.origin + "@evil.example"):
            with self.subTest(origin=origin):
                self.api("POST", "/api/v1/workers", fictional_worker(), headers={"Origin": origin}, expected=403)
        self.assertEqual(before, self.server.store.bootstrap())
        self.api("POST", "/api/v1/workers", fictional_worker(), headers={"Host": f"localhost:{self.port}", "Origin": f"http://localhost:{self.port}"})
        headers = [("Host", self.host), ("Origin", self.origin), ("Origin", self.origin),
                   ("Content-Type", "application/json"), ("Content-Length", "2")]
        status, _ = self.raw_request(headers)
        self.assertEqual(403, status)

    def test_cross_site_rejected_even_with_valid_origin_and_no_cors(self):
        self.api("GET", "/api/v1/bootstrap", headers={"Sec-Fetch-Site": "cross-site"}, expected=403)
        self.api("POST", "/api/v1/workers", fictional_worker(), headers={"Sec-Fetch-Site": "cross-site"}, expected=403)
        self.api("POST", "/api/v1/workers", fictional_worker(), headers={"Sec-Fetch-Site": "same-origin"})
        self.api("OPTIONS", "/api/v1/workers", headers={"Origin": "https://evil.example"}, expected=405)
        status, _, _ = self.request("GET", "/", headers={"Sec-Fetch-Site": "cross-site"})
        self.assertEqual(403, status)

    def test_json_body_limit_is_in_bytes_and_exact_boundary_allowed(self):
        self.api("POST", "/api/v1/workers", body=b" " * (MAX_JSON_BYTES + 1), expected=413)
        body = json.dumps({"ten_that": "Hồ sơ mẫu ranh giới"}, ensure_ascii=False).encode("utf-8")
        body += b" " * (MAX_JSON_BYTES - len(body))
        self.api("POST", "/api/v1/workers", body=body)
        self.api("POST", "/api/v1/workers", body="ư".encode("utf-8") * 40000, expected=413)
        self.api("POST", "/api/v1/workers", body=b"{}", headers={"Content-Length": str(MAX_JSON_BYTES + 1)}, expected=413)

    def test_malformed_json_types_duplicate_keys_and_encoding(self):
        for body in (b"", b"not-json", b"[]", b"null", b"true", b"12", b'"text"', b"\xff",
                     b'{"ten_that":"first","ten_that":"second"}', b'{"ten_that":NaN}',
                     b'{"ten_that":Infinity}', b'{"ten_that":"\\ud800"}', b"[" * 1500 + b"]" * 1500):
            with self.subTest(body=body[:100]):
                self.api("POST", "/api/v1/workers", body=body, expected=400)
        for payload in ({"ten_that": 1}, {"ten_that": "Mẫu", "unknown": True}):
            self.api("POST", "/api/v1/workers", payload, expected=400)
        self.api("POST", "/api/v1/workers", fictional_worker(), headers={"Content-Type": "text/plain"}, expected=400)
        self.api("POST", "/api/v1/workers", fictional_worker(), headers={"Content-Encoding": "gzip"}, expected=400)
        self.api("POST", "/api/v1/workers", fictional_worker(), headers={"Content-Type": "application/json; charset=utf-8"})

    def test_invalid_content_lengths_and_transfer_encoding(self):
        headers = [("Host", self.host), ("Origin", self.origin), ("Content-Type", "application/json")]
        for extra in ([], [("Content-Length", "-1")], [("Content-Length", "bad")],
                      [("Content-Length", "2"), ("Content-Length", "2")],
                      [("Transfer-Encoding", "chunked"), ("Content-Length", "2")],
                      [("Content-Length", "2"), ("Content-Type", "application/json")]):
            with self.subTest(extra=extra):
                status, _ = self.raw_request(headers + extra)
                self.assertEqual(400, status)

    def test_allowed_static_files_and_head(self):
        for path, content_type in (("/", "text/html"), ("/index.html", "text/html"), ("/app.js?v=1", "text/javascript"),
                                   ("/qr.js", "text/javascript"), ("/styles.css", "text/css"),
                                   ("/assets/icons/marker.svg", "image/svg+xml")):
            with self.subTest(path=path):
                status, headers, body = self.request("GET", path)
                self.assertEqual(200, status)
                self.assertIn(content_type, headers["Content-Type"])
                self.assertEqual("nosniff", headers["X-Content-Type-Options"])
                self.assertEqual("DENY", headers["X-Frame-Options"])
                self.assertTrue(body)
        status, headers, body = self.request("HEAD", "/")
        self.assertEqual(200, status)
        self.assertGreater(int(headers["Content-Length"]), 0)
        self.assertEqual(b"", body)
        status, headers, body = self.request("HEAD", "/api/v1/bootstrap")
        self.assertEqual(200, status)
        self.assertEqual("no-store", headers["Cache-Control"])
        self.assertEqual(b"", body)

    def test_source_database_env_tests_and_traversal_paths_are_blocked(self):
        paths = (
            "/app.py", "/store.py", "/tests/test_app.py", "/source/app.py", "/.env", "/.local/demo.sqlite3",
            "/static/index.html", "/assets", "/assets/", "/assets/fake.py", "/assets/fake.json", "/assets/fake.html",
            "/../app.py", "/assets/../../app.py", "/%2e%2e/app.py", "/assets/%2e%2e/%2e%2e/app.py",
            "/assets/%252e%252e/app.py", "/assets/%2f..%2fapp.py", "/assets/%5c..%5capp.py",
            "/assets/..\\app.py", "/assets/.local/image.png", "/assets/tests/image.png", "/assets/source/image.png",
            "/assets/%00.png", "/assets/%ZZ.png", "/index.html/", "/assets//icons/marker.svg",
        )
        for path in paths:
            with self.subTest(path=path):
                status, _, body = self.request("GET", path)
                self.assertEqual(404, status, body)
                self.assertNotIn(b"FICTIONAL_NONPUBLIC_FIXTURE", body)
        self.assertEqual(b"FICTIONAL_NONPUBLIC_FIXTURE", (self.static / ".env").read_bytes())

    def test_symlink_files_directories_and_root_are_blocked(self):
        outside = self.root / "outside.svg"
        outside.write_bytes(b"FICTIONAL_NONPUBLIC_FIXTURE")
        (self.static / "assets" / "outside.svg").symlink_to(outside)
        (self.static / "assets" / "internal.svg").symlink_to(self.static / "assets" / "icons" / "marker.svg")
        (self.static / "assets" / "linked").symlink_to(self.static / "assets" / "icons", target_is_directory=True)
        (self.static / "assets" / "escape").symlink_to(self.root, target_is_directory=True)
        for path in ("/assets/outside.svg", "/assets/internal.svg", "/assets/linked/marker.svg", "/assets/escape/outside.svg"):
            with self.subTest(path=path):
                status, _, body = self.request("GET", path)
                self.assertEqual(404, status)
                self.assertNotIn(b"FICTIONAL_NONPUBLIC_FIXTURE", body)
        linked_root = self.root / "linked-static"
        linked_root.symlink_to(self.static, target_is_directory=True)
        self.server.static_root = linked_root
        status, _, _ = self.request("GET", "/")
        self.assertEqual(404, status)

    def test_unknown_routes_wrong_methods_and_generic_internal_error(self):
        self.api("GET", "/api/v1/unknown", expected=404)
        self.api("POST", "/api/v1/unknown", {}, expected=404)
        self.api("GET", "/api/v1/workers", expected=405)
        self.api("POST", "/api/v1/bootstrap", {}, expected=405)
        for method in ("PUT", "DELETE", "PATCH", "TRACE"):
            self.api(method, "/api/v1/workers", expected=405)
        with patch.object(self.server.store, "bootstrap", side_effect=RuntimeError("PRIVATE_SQL_TRACE_SENTINEL")):
            data = self.api("GET", "/api/v1/bootstrap", expected=500)
            self.assertFalse(data["ok"])
            self.assertNotIn("PRIVATE_SQL_TRACE_SENTINEL", json.dumps(data))
            self.assertNotIn("Traceback", json.dumps(data))
        self.api("GET", "/api/v1/bootstrap")

    def test_worker_image_proxy_serves_only_linked_images(self):
        worker = self.server.store.bootstrap()["workers"][0]
        with self.server.store.transaction() as connection:
            self.server.store.set_worker_image(connection, worker["id"], "photo", "A" * 33)
        self.assertTrue(self.api("GET", "/api/v1/bootstrap")["images"][worker["id"]]["photo"])

        class FakeDrive:
            def fetch(self, drive_id):
                self.asserted = drive_id
                return b"\x89PNG\r\n\x1a\nfiction", "image/png"

        drive = FakeDrive()
        self.server.drive = drive
        self.server.drive_ready = True
        status, headers, body = self.request("GET", f"/api/v1/workers/{worker['id']}/photo")
        self.assertEqual(200, status)
        self.assertEqual("A" * 33, drive.asserted)
        self.assertEqual("image/png", headers["Content-Type"])
        self.assertEqual("private, max-age=3600", headers["Cache-Control"])
        self.assertEqual(b"\x89PNG\r\n\x1a\nfiction", body)
        self.assertEqual(404, self.request("GET", f"/api/v1/workers/{worker['id']}/cmnd")[0])
        self.assertEqual(404, self.request("GET", f"/api/v1/workers/{uuid.uuid4()}/photo")[0])

    def test_company_access_code_login_session_and_logout(self):
        code = "ma-cong-ty-kiem-thu-2026"
        environment = patch.dict(os.environ, {"CN_ACCESS_CODE": code, "CN_SECRET_KEY": "k" * 64}, clear=False)
        environment.start()
        self.addCleanup(environment.stop)
        server = create_server(port=0, data_dir=self.root / "auth-data", static_root=self.static)
        thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True)
        thread.start()
        self.addCleanup(lambda: (server.shutdown(), server.server_close(), thread.join(timeout=3)))
        port = server.server_port
        origin = f"http://127.0.0.1:{port}"

        def call(method, path, payload=None, headers=None):
            values = {"Host": f"127.0.0.1:{port}"}
            if payload is not None:
                values.update({"Origin": origin, "Content-Type": "application/json"})
            values.update(headers or {})
            connection = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
            try:
                body = json.dumps(payload).encode("utf-8") if payload is not None else None
                connection.request(method, path, body=body, headers=values)
                response = connection.getresponse()
                return response.status, response.getheaders(), response.read()
            finally:
                connection.close()

        self.assertEqual(401, call("GET", "/api/v1/bootstrap")[0])
        status, headers, _ = call("GET", "/")
        self.assertEqual(302, status)
        self.assertEqual("/login.html", dict(headers)["Location"])
        self.assertEqual(401, call("POST", "/api/v1/session", {"code": "sai-ma"})[0])
        status, headers, content = call("POST", "/api/v1/session", {"code": code})
        self.assertEqual(200, status)
        cookie = dict(headers)["Set-Cookie"]
        self.assertIn("HttpOnly", cookie)
        self.assertIn("SameSite=Strict", cookie)
        session = cookie.split(";", 1)[0]
        self.assertEqual(200, call("GET", "/api/v1/bootstrap", headers={"Cookie": session})[0])
        self.assertEqual(200, call("DELETE", "/api/v1/session", headers={"Cookie": session})[0])
        status, headers, _ = call("DELETE", "/api/v1/session", headers={"Cookie": session})
        self.assertIn("Max-Age=0", dict(headers)["Set-Cookie"])

    def test_env_port_data_dir_and_invalid_ports(self):
        with patch.dict(os.environ, {"PORT": "0", "CN_DATA_DIR": str(self.root / "env-data"), "HOST": "0.0.0.0"}):
            server = create_server(static_root=self.static)
            try:
                self.assertEqual("127.0.0.1", server.server_address[0])
                self.assertEqual((self.root / "env-data" / "demo.sqlite3").resolve(), server.store.db_path)
            finally:
                server.server_close()
        for port in (True, -1, 65536, "8787", 1.5):
            with self.subTest(port=port), self.assertRaises(ValueError):
                create_server(port=port, data_dir=self.root / "invalid-port", static_root=self.static)
        for port in ("bad", "-1", "65536", "1.0", "127.0.0.1:8787"):
            with patch.dict(os.environ, {"PORT": port}), self.assertRaises(ValueError):
                create_server(data_dir=self.root / "invalid-port", static_root=self.static)
        self.assertFalse((self.root / "invalid-port").exists())

    def test_main_subprocess_starts_loopback_and_reuses_isolated_database(self):
        data_dir = self.root / "subprocess-data"
        env = dict(os.environ, PORT="0", CN_DATA_DIR=str(data_dir), PYTHONDONTWRITEBYTECODE="1")
        process = subprocess.Popen([sys.executable, "-B", str(PROJECT_DIR / "app.py")], env=env,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        selector = selectors.DefaultSelector()
        try:
            selector.register(process.stdout, selectors.EVENT_READ)
            self.assertTrue(selector.select(timeout=10), "Server did not announce startup")
            announcement = process.stdout.readline()
            self.assertIn("http://127.0.0.1:", announcement)
            port = int(announcement.split("http://127.0.0.1:", 1)[1].split()[0])
            connection = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
            try:
                connection.request("GET", "/api/v1/bootstrap")
                response = connection.getresponse()
                self.assertEqual(200, response.status)
                self.assertEqual(48, len(json.loads(response.read())["workers"]))
            finally:
                connection.close()
        finally:
            selector.close()
            if process.poll() is None:
                process.send_signal(signal.SIGINT)
            try:
                _, stderr = process.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                _, stderr = process.communicate(timeout=5)
        self.assertEqual(0, process.returncode, stderr)
        self.assertEqual(48, len(Store(data_dir).bootstrap()["workers"]))


if __name__ == "__main__":
    unittest.main()
