# -*- coding: utf-8 -*-
import base64
import http.client
import json
import os
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest import mock
from urllib.parse import urlsplit

import ocr
from app import create_server
from store import Store

SECRET = "provider-secret-value"
FIELDS = {
    "ten_that": "BOEURN YON", "cmnd": "150532961", "ngay_sinh": "03/10/1981",
    "gioi_tinh": "ប្រុស", "dia_chi": "ភូមិចក", "noi_sinh": "ឃុំកំពង់ចិនជើង",
}
IMAGE = "data:image/jpeg;base64," + base64.b64encode(b"\xff\xd8\xff" + b"x" * 4000).decode()


class ProviderHandler(BaseHTTPRequestHandler):
    requests = []

    def do_POST(self):
        length = int(self.headers.get("Content-Length") or 0)
        payload = self.rfile.read(length)
        ProviderHandler.requests.append(
            {"path": self.path, "auth": self.headers.get("Authorization", ""), "payload": payload})
        path = urlsplit(self.path).path
        if path == "/limited":
            self.reply(429, {"error": {"status": "RESOURCE_EXHAUSTED"}})
        elif path == "/auth":
            self.reply(401, {"error": {"message": "API key invalid"}})
        elif path == "/echo":
            self.reply(500, {"message": "bad key " + SECRET})
        elif path == "/m1:generateContent":
            self.reply(500, {"error": "model down"})
        elif path == "/m2:generateContent":
            text = "```json\n" + json.dumps(FIELDS, ensure_ascii=False) + "\n```"
            self.reply(200, {"candidates": [{"content": {"parts": [{"text": text}]}}]})
        elif path == "/fields":
            self.reply(200, {"ok": True, "fields": FIELDS})
        elif path == "/top":
            self.reply(200, FIELDS)
        else:
            self.reply(200, {"ok": True, "data": FIELDS})

    def reply(self, code, value):
        body = json.dumps(value, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


class ProviderServer:
    def __enter__(self):
        ProviderHandler.requests = []
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), ProviderHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        return self.server.server_port

    def __exit__(self, *args):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=3)


class OcrServiceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="cn-ocr-test-")
        self.addCleanup(self.temporary.cleanup)
        self.store = Store(self.temporary.name, seed=False)

    def service(self, env):
        values = {"CN_OCR_PROVIDERS": "", "GEMINI_API_KEY": ""}
        values.update(env)
        return ocr.Service(self.store, values)

    def test_config_validation_is_reported_without_exposing_keys(self):
        service = self.service({"CN_OCR_PROVIDERS": json.dumps([
            {"kind": "generic", "endpoint": "http://example.com/ocr"},
            {"id": "dup", "kind": "generic", "endpoint": "https://api.example.com/ocr"},
            {"id": "dup", "kind": "generic", "endpoint": "https://api.example.com/ocr"},
            {"kind": "other", "endpoint": "https://api.example.com/ocr"},
        ]), "K": SECRET})
        status = service.status()
        self.assertTrue(status["configured"])
        errors = " · ".join(status["errors"])
        self.assertIn("localhost", errors)
        self.assertIn("bị trùng", errors)
        self.assertIn("kind", errors)
        self.assertNotIn(SECRET, json.dumps(status, ensure_ascii=False))
        broken = self.service({"CN_OCR_PROVIDERS": "{not json"})
        self.assertFalse(broken.status()["configured"])
        self.assertIn("JSON", broken.status()["errors"][0])

    def test_birth_date_is_normalized_to_iso_for_the_form(self):
        cases = {
            "03/10/1981": "1981-10-03",
            "3.10.1981": "1981-10-03",
            "3-10-1981": "1981-10-03",
            "1981-10-03": "1981-10-03",
            "31/02/1981": "",
            "không rõ": "",
        }
        for raw, expected in cases.items():
            fields = ocr.normalize_fields({"ten_that": "KIỂM THỬ", "ngay_sinh": raw})
            self.assertEqual(expected, fields["ngay_sinh"], raw)

    def test_missing_provider_returns_copyable_request_and_fallback_requirement(self):
        for env in ({}, {"GEMINI_API_KEY": ""}):
            result = self.service(env).recognize(IMAGE)
            self.assertFalse(result["ok"])
            self.assertEqual("no_provider", result["error"])
            self.assertIn("dự phòng", result["request"]["text"])
            self.assertIn("CN_OCR_PROVIDERS", result["request"]["text"])
            self.assertEqual(2, len(result["request"]["sample"]["providers"]))
            self.assertTrue(all(item.get("key_env") for item in result["request"]["sample"]["providers"]))
            self.assertNotIn(SECRET, json.dumps(result, ensure_ascii=False))

    def test_quota_rotates_to_next_provider_and_tracks_usage(self):
        with ProviderServer() as port:
            service = self.service({
                "CN_OCR_PROVIDERS": json.dumps([
                    {"id": "phu", "kind": "generic", "endpoint": f"http://127.0.0.1:{port}/limited", "key_env": "K1"},
                    {"id": "chinh", "kind": "generic", "endpoint": f"http://127.0.0.1:{port}/ok", "key_env": "K2"},
                ]),
                "K1": SECRET, "K2": "second-secret",
            })
            result = service.recognize(IMAGE)
            self.assertTrue(result["ok"])
            self.assertEqual("chinh", result["provider"])
            self.assertEqual("M", result["fields"]["gioi_tinh"])
            self.assertEqual("1981-10-03", result["fields"]["ngay_sinh"])
            self.assertEqual("BOEURN YON", result["fields"]["ten_that"])
            self.assertEqual(2, len(ProviderHandler.requests))
            self.assertEqual("Bearer " + SECRET, ProviderHandler.requests[0]["auth"])
            usage = self.store.ocr_usage()
            self.assertEqual(1, usage["phu"]["quota_hits"])
            self.assertEqual(1, usage["chinh"]["calls"])
            status = service.status()
            by_id = {item["id"]: item for item in status["providers"]}
            self.assertEqual("cooling", by_id["phu"]["state"])
            self.assertEqual("ready", by_id["chinh"]["state"])
            self.assertEqual("127.0.0.1", by_id["chinh"]["target"])
            self.assertNotIn(SECRET, json.dumps(status, ensure_ascii=False))
            self.assertNotIn("second-secret", json.dumps(status, ensure_ascii=False))

    def test_all_quota_providers_cool_down_and_stop_calling(self):
        with ProviderServer() as port:
            service = self.service({"CN_OCR_PROVIDERS": json.dumps([
                {"id": "only", "kind": "generic", "endpoint": f"http://127.0.0.1:{port}/limited", "key_env": "K"},
            ]), "K": SECRET})
            first = service.recognize(IMAGE)
            second = service.recognize(IMAGE)
            self.assertEqual("quota_exhausted", first["error"])
            self.assertEqual("quota_exhausted", second["error"])
            self.assertEqual(1, len(ProviderHandler.requests))
            usage = self.store.ocr_usage()["only"]
            self.assertEqual(1, usage["calls"])
            self.assertEqual(1, usage["quota_hits"])
            provider = service.status()["providers"][0]
            self.assertEqual("cooling", provider["state"])
            self.assertTrue(provider["cooldown_until"].endswith("Z"))

    def test_gemini_models_fall_back_and_parse_code_fence(self):
        with ProviderServer() as port:
            service = self.service({"CN_OCR_PROVIDERS": json.dumps([
                {"id": "g", "kind": "gemini", "endpoint": f"http://127.0.0.1:{port}", "key_env": "K",
                 "models": ["m1", "m2"], "timeout": 5},
            ]), "K": SECRET})
            result = service.recognize(IMAGE)
            self.assertTrue(result["ok"])
            self.assertEqual("g", result["provider"])
            self.assertEqual("150532961", result["fields"]["cmnd"])
            paths = [urlsplit(item["path"]).path for item in ProviderHandler.requests]
            self.assertEqual(["/m1:generateContent", "/m2:generateContent"], paths)
            self.assertTrue(all("key=" + SECRET in item["path"] for item in ProviderHandler.requests))
            status = json.dumps(service.status(), ensure_ascii=False)
            self.assertNotIn(SECRET, status)
            self.assertNotIn(SECRET, json.dumps(result, ensure_ascii=False))

    def test_generic_shapes_auth_failures_and_key_redaction(self):
        for path in ("/fields", "/top", "/ok"):
            with ProviderServer() as port:
                service = self.service({"CN_OCR_PROVIDERS": json.dumps([
                    {"id": "api", "kind": "generic", "endpoint": f"http://127.0.0.1:{port}{path}", "key_env": "K"},
                ]), "K": SECRET})
                result = service.recognize(IMAGE)
                self.assertTrue(result["ok"], path)
                self.assertEqual("M", result["fields"]["gioi_tinh"])
        with ProviderServer() as port:
            denied = self.service({"CN_OCR_PROVIDERS": json.dumps([
                {"id": "api", "kind": "generic", "endpoint": f"http://127.0.0.1:{port}/auth", "key_env": "K"},
            ]), "K": SECRET}).recognize(IMAGE)
            self.assertEqual("failed", denied["error"])
            self.assertIn("401", denied["message"])
            self.assertNotIn(SECRET, json.dumps(denied, ensure_ascii=False))
        with ProviderServer() as port:
            service = self.service({"CN_OCR_PROVIDERS": json.dumps([
                {"id": "api", "kind": "generic", "endpoint": f"http://127.0.0.1:{port}/echo", "key_env": "K"},
            ]), "K": SECRET})
            failed = service.recognize(IMAGE)
            self.assertEqual("failed", failed["error"])
            self.assertIn("***", failed["message"])
            self.assertNotIn(SECRET, failed["message"])
            self.assertIn("***", service.status()["providers"][0]["last_error"])

    def test_image_payload_validation(self):
        service = self.service({})
        invalid = [
            None, "", "not-a-data-url", "http://example.com/card.jpg",
            "data:image/gif;base64,AAAA",
            "data:image/jpeg;base64,%%%%",
            "data:image/jpeg;base64," + base64.b64encode(b"\xff\xd8").decode(),
        ]
        for value in invalid:
            with self.assertRaises(ocr.OcrInputError):
                service.recognize(value)
        encoded = base64.b64encode(b"\xff\xd8\xff" + b"x" * 4000).decode()
        spaced = "data:image/jpeg;base64," + encoded[:24] + "\n" + encoded[24:]
        self.assertEqual("no_provider", service.recognize(spaced)["error"])


class OcrHttpTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="cn-ocr-http-test-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        (self.root / "static").mkdir()
        patcher = mock.patch.dict(os.environ, {
            "CN_OCR_PROVIDERS": "", "GEMINI_API_KEY": "", "CN_ACCESS_CODE": "",
            "CN_BACKUP_FILE_ID": "", "CN_SYNC_TOKEN": "",
        })
        patcher.start()
        self.addCleanup(patcher.stop)
        self.server = create_server(port=0, data_dir=self.root / "data", static_root=self.root / "static")
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

    def call(self, method, path, payload=None, expected=200):
        headers = {"Host": self.host}
        body = None
        if method == "POST":
            headers.update({"Origin": self.origin, "Content-Type": "application/json"})
        if payload is not None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        try:
            connection.request(method, path, body=body, headers=headers)
            response = connection.getresponse()
            content = response.read()
            self.assertEqual(expected, response.status, content.decode("utf-8", errors="replace"))
        finally:
            connection.close()
        return json.loads(content)

    def test_status_is_readable_and_ocr_requires_post(self):
        status = self.call("GET", "/api/v1/ocr/status")
        self.assertTrue(status["ok"])
        self.assertFalse(status["configured"])
        self.assertEqual([], status["providers"])
        self.assertTrue(status["request"]["text"])
        self.assertNotIn(SECRET, json.dumps(status, ensure_ascii=False))
        body = self.call("GET", "/api/v1/ocr", expected=405)
        self.assertFalse(body["ok"])

    def test_ocr_post_validates_image_and_reports_missing_provider(self):
        rejected = self.call("POST", "/api/v1/ocr", {"image": "not-an-image"}, expected=400)
        self.assertFalse(rejected["ok"])
        result = self.call("POST", "/api/v1/ocr", {"image": IMAGE})
        self.assertFalse(result["ok"])
        self.assertEqual("no_provider", result["error"])
        self.assertTrue(result["request"]["sample"]["providers"])


if __name__ == "__main__":
    unittest.main()