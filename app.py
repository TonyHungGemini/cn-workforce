import hmac
import json
import os
import re
import signal
import socket
import stat
import sys
import tempfile
import threading
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

import backup
from auth import (SESSION_COOKIE, SESSION_TTL, auth_required, issue_session, parse_cookies,
                  valid_session, verify_code)
from drive import Drive, DriveError
from store import APIError, Store


BASE_DIR = Path(__file__).resolve().parent
MAX_JSON_BYTES = 64 * 1024
MAX_SYNC_BYTES = 32 * 1024 * 1024
LOGIN_WINDOW = 600
LOGIN_ATTEMPTS = 8
IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
CSP = (
    "default-src 'self'; script-src 'self' 'wasm-unsafe-eval'; style-src 'self' 'unsafe-inline'; "
    "img-src 'self' blob:; font-src 'self'; connect-src 'self'; worker-src 'self'; object-src 'none'; "
    "base-uri 'none'; frame-ancestors 'none'; form-action 'self'"
)
STATIC_FILES = {
    "index.html": "text/html; charset=utf-8", "app.js": "text/javascript; charset=utf-8",
    "ocr.js": "text/javascript; charset=utf-8", "styles.css": "text/css; charset=utf-8",
    "qr.js": "text/javascript; charset=utf-8",
    "login.html": "text/html; charset=utf-8", "login.js": "text/javascript; charset=utf-8",
    "manifest.webmanifest": "application/manifest+json; charset=utf-8",
    "sw.js": "text/javascript; charset=utf-8",
}
PUBLIC_PATHS = {
    "/login.html", "/login.js", "/manifest.webmanifest", "/sw.js", "/healthz", "/assets/mark.svg",
    "/assets/icon-192.png", "/assets/icon-512.png", "/assets/icon-maskable-512.png", "/assets/apple-touch-icon.png",
}
IMAGE_PATH = re.compile(r"^/api/v1/workers/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})/(photo|cmnd)$")
# Explicit paths only: other JS/WASM/gzip files and node_modules remain private.
OCR_FILES = {
    "assets/ocr/tesseract.min.js": "text/javascript; charset=utf-8",
    "assets/ocr/worker.min.js": "text/javascript; charset=utf-8",
    **{f"assets/ocr/tesseract-core-{variant}.wasm.js": "text/javascript; charset=utf-8"
       for variant in ("lstm", "simd-lstm", "relaxedsimd-lstm")},
    **{f"assets/ocr/tesseract-core-{variant}.wasm": "application/wasm"
       for variant in ("lstm", "simd-lstm", "relaxedsimd-lstm")},
    **{f"assets/ocr/{language}.traineddata.gz": "application/gzip"
       for language in ("eng", "vie", "khm")},
}
ASSET_TYPES = {
    ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp",
    ".gif": "image/gif", ".svg": "image/svg+xml", ".ico": "image/x-icon", ".avif": "image/avif",
    ".woff": "font/woff", ".woff2": "font/woff2", ".ttf": "font/ttf", ".otf": "font/otf",
}


def json_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key")
        result[key] = value
    return result


def invalid_constant(value):
    raise ValueError("Non-finite JSON number")


class DemoServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, port, store, static_root, host="127.0.0.1"):
        self.store = store
        self.static_root = Path(static_root).absolute()
        self.drive = None
        self.drive_ready = False
        self.backup = None
        self.remote = host not in ("127.0.0.1", "localhost", "::1")
        self.auth_required = auth_required()
        self.public_url = os.environ.get("CN_PUBLIC_URL", "").rstrip("/")
        self.cloud = self.remote or self.public_url.startswith("https://")
        self.secure_cookie = self.public_url.startswith("https://") or os.environ.get("CN_COOKIE_SECURE") == "1"
        self.login_failures = {}
        super().__init__((host, port), Handler)
        # Port 0 only resolves after bind, so host/origin allowlists use the real port.
        port = self.server_port
        self.allowed_hosts = {f"127.0.0.1:{port}", f"localhost:{port}"}
        self.allowed_origins = {
            f"http://127.0.0.1:{port}", f"http://localhost:{port}",
        }
        for value in os.environ.get("CN_ALLOWED_HOSTS", "").split(","):
            value = value.strip().lower()
            if value:
                self.allowed_hosts.add(value)
                if ":" not in value:
                    self.allowed_hosts.add(f"{value}:{port}")
        render_host = os.environ.get("RENDER_EXTERNAL_HOSTNAME", "").strip().lower()
        if render_host:
            self.allowed_hosts.add(render_host)
            self.allowed_origins.add(f"https://{render_host}")
        if self.public_url:
            parsed = urlsplit(self.public_url)
            if parsed.netloc:
                self.allowed_hosts.add(parsed.netloc.lower())
                self.allowed_origins.add(f"{parsed.scheme}://{parsed.netloc}")
        for value in os.environ.get("CN_ALLOWED_ORIGINS", "").split(","):
            value = value.strip().rstrip("/")
            if value:
                self.allowed_origins.add(value)

    def get_request(self):
        connection, address = super().get_request()
        connection.settimeout(30)
        return connection, address

    def drive_client(self):
        if not self.drive_ready:
            self.drive = Drive.from_env(self.store.data_dir / "image-cache")
            self.drive_ready = True
        return self.drive


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "CNWorkforceDemo"
    sys_version = ""

    def log_message(self, format, *args):
        pass

    def _send(self, status, body, content_type="application/json; charset=utf-8", api=True, headers=None, cache=None):
        self.close_connection = True
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Connection", "close")
        self.send_header("Cache-Control", cache or ("no-store" if api else "no-cache"))
        self.send_header("Content-Security-Policy", CSP)
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        self.send_header("X-Robots-Tag", "noindex, nofollow, noarchive")
        if self._https():
            self.send_header("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        for name, value in (headers or {}).items():
            self.send_header(name, value)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _https(self):
        if self.server.secure_cookie:
            return True
        forwarded = self.headers.get("X-Forwarded-Proto", "") if self.server.public_url else ""
        return forwarded.split(",", 1)[0].strip().lower() == "https"

    def _redirect(self, location):
        self._send(302, b"", "text/plain; charset=utf-8", api=False, headers={"Location": location})

    def _authenticated(self):
        if not self.server.auth_required:
            return True
        return valid_session(parse_cookies(self.headers.get("Cookie")).get(SESSION_COOKIE))

    def _session_cookie(self, token=None):
        parts = [f"{SESSION_COOKIE}={token or ''}", "Path=/", "HttpOnly", "SameSite=Strict"]
        if token:
            parts.append(f"Max-Age={SESSION_TTL}")
        else:
            parts.extend(["Max-Age=0", "Expires=Thu, 01 Jan 1970 00:00:00 GMT"])
        if self._https():
            parts.append("Secure")
        return "; ".join(parts)

    def _client_key(self):
        if self.server.cloud:
            forwarded = self.headers.get("X-Forwarded-For", "").split(",", 1)[0].strip()
            if forwarded and len(forwarded) <= 64 and not any(char.isspace() for char in forwarded):
                return forwarded
        return self.client_address[0]

    def _login_blocked(self):
        key = self._client_key()
        now = time.monotonic()
        attempts = [value for value in self.server.login_failures.get(key, []) if now - value < LOGIN_WINDOW]
        self.server.login_failures[key] = attempts
        return len(attempts) >= LOGIN_ATTEMPTS

    def _login_failed(self):
        key = self._client_key()
        self.server.login_failures.setdefault(key, []).append(time.monotonic())

    def _json(self, status, value, headers=None):
        body = json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode("utf-8")
        self._send(status, body, headers=headers)

    def _error(self, status, message):
        self._json(status, {"ok": False, "error": message})

    def send_error(self, code, message=None, explain=None):
        try:
            phrase = HTTPStatus(code).phrase
        except ValueError:
            phrase = "Request rejected"
        self._error(code, phrase)

    def handle_expect_100(self):
        self._error(417, "Không hỗ trợ Expect: 100-continue.")
        return False

    def _check_request(self):
        hosts = self.headers.get_all("Host", [])
        if len(hosts) != 1 or hosts[0].strip().lower() not in self.server.allowed_hosts:
            raise APIError(403, "Host không được phép.")
        sites = self.headers.get_all("Sec-Fetch-Site", [])
        if len(sites) > 1 or any(site.strip().lower() == "cross-site" for site in sites):
            raise APIError(403, "Không chấp nhận yêu cầu cross-site.")
        if self.headers.get_all("Transfer-Encoding"):
            raise APIError(400, "Không hỗ trợ Transfer-Encoding.")

    def _path(self):
        if not self.path.startswith("/") or self.path.startswith("//"):
            raise APIError(400, "Đường dẫn yêu cầu không hợp lệ.")
        try:
            parsed = urlsplit(self.path)
            path = unquote(parsed.path, encoding="utf-8", errors="strict")
        except (ValueError, UnicodeDecodeError):
            raise APIError(400, "Đường dẫn yêu cầu không hợp lệ.") from None
        if parsed.scheme or parsed.netloc or parsed.fragment:
            raise APIError(400, "Đường dẫn yêu cầu không hợp lệ.")
        parts = path.split("/")[1:]
        if ("\\" in path or "%" in path or any(ord(char) < 32 for char in path)
                or any(part.startswith(".") or part in ("source", "tests", "__pycache__") for part in parts)):
            raise APIError(404, "Không tìm thấy tài nguyên.")
        if path != "/" and any(not part for part in parts):
            raise APIError(404, "Không tìm thấy tài nguyên.")
        return path

    def _body(self, limit=MAX_JSON_BYTES, require_origin=True):
        if require_origin:
            origins = self.headers.get_all("Origin", [])
            if len(origins) != 1 or origins[0] not in self.server.allowed_origins:
                raise APIError(403, "Origin không được phép hoặc bị thiếu.")
        types = self.headers.get_all("Content-Type", [])
        if len(types) != 1 or types[0].split(";", 1)[0].strip().lower() != "application/json":
            raise APIError(400, "Content-Type phải là application/json.")
        if self.headers.get_all("Content-Encoding"):
            raise APIError(400, "Không hỗ trợ Content-Encoding.")
        lengths = self.headers.get_all("Content-Length", [])
        if len(lengths) != 1 or not re.fullmatch(r"[0-9]{1,10}", lengths[0]):
            raise APIError(400, "Content-Length không hợp lệ hoặc bị thiếu.")
        length = int(lengths[0])
        if length > limit:
            raise APIError(413, f"JSON vượt giới hạn {limit // 1024} KB.")
        if length == 0:
            raise APIError(400, "Nội dung JSON không được để trống.")
        try:
            body = self.rfile.read(length)
            if len(body) != length:
                raise ValueError("Incomplete body")
            value = json.loads(body.decode("utf-8"), object_pairs_hook=json_pairs, parse_constant=invalid_constant)
        except (ValueError, UnicodeDecodeError, RecursionError, socket.timeout):
            raise APIError(400, "Nội dung JSON không hợp lệ.") from None
        if not isinstance(value, dict):
            raise APIError(400, "Nội dung JSON phải là một đối tượng.")
        return value

    def _static(self, path):
        relative = "index.html" if path == "/" else path[1:]
        parts = relative.split("/")
        if relative in STATIC_FILES:
            content_type = STATIC_FILES[relative]
        elif relative in OCR_FILES:
            content_type = OCR_FILES[relative]
        elif (len(parts) >= 2 and parts[0] == "assets" and parts[1] != "ocr"
              and Path(relative).suffix.lower() in ASSET_TYPES):
            content_type = ASSET_TYPES[Path(relative).suffix.lower()]
        else:
            raise APIError(404, "Không tìm thấy tài nguyên.")
        root = self.server.static_root
        candidate = root.joinpath(*parts)
        directory_fd = None
        file_fd = None
        try:
            resolved_root = root.resolve(strict=True)
            candidate.resolve(strict=True).relative_to(resolved_root)
            if root.is_symlink() or any(root.joinpath(*parts[:i]).is_symlink() for i in range(1, len(parts) + 1)):
                raise ValueError("Symlink not allowed")
            directory_fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            for part in parts[:-1]:
                next_fd = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory_fd)
                os.close(directory_fd)
                directory_fd = next_fd
            file_fd = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory_fd)
            if not stat.S_ISREG(os.fstat(file_fd).st_mode):
                raise ValueError("Not a regular file")
            with os.fdopen(file_fd, "rb") as stream:
                file_fd = None
                body = stream.read()
        except (OSError, ValueError, RuntimeError):
            raise APIError(404, "Không tìm thấy tài nguyên.") from None
        finally:
            if file_fd is not None:
                os.close(file_fd)
            if directory_fd is not None:
                os.close(directory_fd)
        self._send(200, body, content_type, api=False,
                   cache="private, max-age=604800" if relative.startswith("assets/ocr/") else None)

    def _session(self):
        if self.command == "GET":
            return self._json(200, {
                "ok": True, "authenticated": self._authenticated(),
                "required": self.server.auth_required, "cloud": self.server.cloud,
            })
        if self.command == "POST":
            if self._login_blocked():
                raise APIError(429, "Quá nhiều lần thử. Vui lòng chờ vài phút.")
            payload = self._body()
            if set(payload) != {"code"} or not isinstance(payload["code"], str):
                raise APIError(400, "Cần nhập mã truy cập công ty.")
            if not verify_code(payload["code"]):
                self._login_failed()
                raise APIError(401, "Mã truy cập không đúng.")
            self.server.login_failures.pop(self._client_key(), None)
            return self._json(200, {"ok": True, "authenticated": True},
                              headers={"Set-Cookie": self._session_cookie(issue_session())})
        if self.command == "DELETE":
            return self._json(200, {"ok": True, "authenticated": False},
                              headers={"Set-Cookie": self._session_cookie()})
        raise APIError(405, "Phương thức không được hỗ trợ.")

    def _image(self, worker_id, kind):
        drive_id = self.server.store.worker_image(worker_id, kind)
        try:
            drive = self.server.drive_client()
        except DriveError as error:
            raise APIError(503, str(error)) from error
        if drive is None:
            raise APIError(503, "Chưa cấu hình kho ảnh Google Drive.")
        try:
            body, content_type = drive.fetch(drive_id)
        except DriveError as error:
            raise APIError(502, str(error)) from error
        if content_type not in IMAGE_TYPES:
            raise APIError(502, "Tệp Drive không phải ảnh.")
        self._send(200, body, content_type, headers={"Content-Disposition": "inline"},
                   cache="private, max-age=3600")

    def _require_sync_token(self):
        expected = os.environ.get("CN_SYNC_TOKEN", "")
        if not expected:
            raise APIError(404, "Không tìm thấy API.")
        if self.command != "POST":
            raise APIError(405, "Phương thức không được hỗ trợ.")
        supplied = self.headers.get("Authorization", "")
        if not supplied.startswith("Bearer ") or not hmac.compare_digest(
                supplied[7:].encode("utf-8"), expected.encode("utf-8")):
            raise APIError(401, "Token đồng bộ không đúng.")
        return expected

    def _admin_sync(self):
        self._require_sync_token()
        payload = self._body(limit=MAX_SYNC_BYTES, require_origin=False)
        records = payload.get("records", payload.get("data"))
        images = payload.get("images", {})
        if not isinstance(records, list) or not records or len(records) > 20000:
            raise APIError(400, "Danh sách hồ sơ không hợp lệ hoặc quá lớn.")
        if not all(isinstance(record, dict) for record in records):
            raise APIError(400, "Danh sách hồ sơ không hợp lệ.")
        if not isinstance(images, dict):
            raise APIError(400, "Danh sách ảnh không hợp lệ.")
        sys.path.insert(0, str(BASE_DIR / "scripts"))
        from sync_master import sync  # lazy: only sync endpoints need the importer
        handle = tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", suffix=".json", prefix="sync-", dir=self.server.store.data_dir, delete=False)
        try:
            with handle:
                json.dump({"data": records, "images": images}, handle, ensure_ascii=False)
            report = sync(handle.name, self.server.store.data_dir, images_source=None)
        finally:
            Path(handle.name).unlink(missing_ok=True)
        return self._json(200, self._sync_summary(report))

    def _admin_pull(self):
        self._require_sync_token()
        master = os.environ.get("CN_MASTER_URL", "").strip()
        if not master:
            raise APIError(400, "Chưa cấu hình CN_MASTER_URL.")
        images = os.environ.get("CN_MASTER_IMAGES_URL", "").strip() or None
        sys.path.insert(0, str(BASE_DIR / "scripts"))
        from sync_master import sync
        try:
            report = sync(master, self.server.store.data_dir, images_source=images,
                          token=os.environ.get("CN_MASTER_TOKEN", ""))
        except SystemExit as error:
            raise APIError(502, str(error)) from error
        return self._json(200, self._sync_summary(report))

    def _admin_transfer_decision(self):
        self._require_sync_token()
        return self._json(200, self.server.store.decide_transfer(self._body(require_origin=False)))

    @staticmethod
    def _sync_summary(report):
        return {
            "ok": True, "records": report["records"], "created": report.get("created", 0),
            "updated": report.get("updated", 0), "unchanged": report.get("unchanged", 0),
            "with_images": report.get("with_images", 0),
        }

    def _dispatch(self):
        try:
            self._check_request()
            path = self._path()
            if path == "/healthz":
                if self.command not in ("GET", "HEAD"):
                    raise APIError(405, "Phương thức không được hỗ trợ.")
                return self._json(200, {"ok": True, "service": "cn-workforce"})
            if path == "/api/v1/admin/sync":
                return self._admin_sync()
            if path == "/api/v1/admin/pull":
                return self._admin_pull()
            if path == "/api/v1/transfers/decision":
                return self._admin_transfer_decision()
            if path == "/api/v1/session":
                return self._session()
            authenticated = self._authenticated()
            if not authenticated:
                if path in PUBLIC_PATHS:
                    if self.command in ("GET", "HEAD"):
                        return self._static(path)
                    raise APIError(405, "Phương thức không được hỗ trợ.")
                if path.startswith("/api/"):
                    raise APIError(401, "Cần đăng nhập bằng mã truy cập công ty.")
                return self._redirect("/login.html")
            if path == "/login.html" and self.server.auth_required:
                return self._redirect("/")
            reads = {"/api/v1/bootstrap": self.server.store.bootstrap, "/api/v1/contract": self.server.store.contract}
            writes = {
                "/api/v1/workers": self.server.store.save_worker,
                "/api/v1/workers/archive": self.server.store.archive_worker,
                "/api/v1/transfers": self.server.store.request_transfer,
                "/api/v1/events": self.server.store.add_event,
                "/api/v1/visitors": self.server.store.add_visitor,
                "/api/v1/visitors/transition": self.server.store.transition_visitor,
                "/api/v1/checks": self.server.store.add_check,
            }
            image = IMAGE_PATH.match(path)
            if self.command in ("GET", "HEAD"):
                if image:
                    self._image(image.group(1), image.group(2))
                elif path in reads:
                    self._json(200, reads[path]())
                elif path in writes:
                    raise APIError(405, "Phương thức không được hỗ trợ.")
                elif path.startswith("/api/"):
                    raise APIError(404, "Không tìm thấy API.")
                else:
                    self._static(path)
            elif self.command == "POST":
                if path in writes:
                    self._json(200, writes[path](self._body()))
                elif path in reads:
                    raise APIError(405, "Phương thức không được hỗ trợ.")
                else:
                    raise APIError(404, "Không tìm thấy API.")
            else:
                raise APIError(405, "Phương thức không được hỗ trợ.")
        except APIError as error:
            self._error(error.status, error.message)
        except (BrokenPipeError, ConnectionResetError):
            self.close_connection = True
        except Exception:
            self._error(500, "Lỗi nội bộ của demo. Vui lòng thử lại.")

    do_GET = _dispatch
    do_HEAD = _dispatch
    do_POST = _dispatch
    do_OPTIONS = _dispatch
    do_PUT = _dispatch
    do_PATCH = _dispatch
    do_DELETE = _dispatch
    do_TRACE = _dispatch
    do_CONNECT = _dispatch


def create_server(port=None, data_dir=None, static_root=None, host=None):
    if port is None:
        value = os.environ.get("PORT", "8787")
        if not re.fullmatch(r"[0-9]{1,5}", value):
            raise ValueError("PORT must be an integer between 0 and 65535")
        port = int(value)
    if type(port) is not int or not 0 <= port <= 65535:
        raise ValueError("PORT must be an integer between 0 and 65535")
    host = host or os.environ.get("CN_HOST", "127.0.0.1")
    if not re.fullmatch(r"[A-Za-z0-9.:\[\]-]{1,100}", host):
        raise ValueError("CN_HOST must be a valid listen address")
    if host not in ("127.0.0.1", "localhost", "::1") and not auth_required():
        raise ValueError("CN_ACCESS_CODE is required when CN_HOST binds beyond loopback")
    data_dir = data_dir if data_dir is not None else os.environ.get("CN_DATA_DIR", str(BASE_DIR / ".local"))
    data_path = Path(data_dir).expanduser().resolve()
    data_path.mkdir(parents=True, exist_ok=True)
    static_root = static_root if static_root is not None else BASE_DIR / "static"
    seed_setting = os.environ.get("CN_SEED_DEMO")
    if seed_setting is None:
        # A sync token marks a real-data server: never mix synthetic records into it.
        seed = not os.environ.get("CN_SYNC_TOKEN", "").strip()
    else:
        seed = seed_setting.strip().lower() not in ("0", "false", "no")
    backup_id = backup.backup_file_id()
    drive = Drive.from_env(data_path / "image-cache") if backup_id else None
    if drive is not None:
        # Free hosting wipes the disk on restart: reload the last copy before opening the store.
        try:
            if backup.restore(data_path, drive, backup_id):
                print("[backup] đã khôi phục cơ sở dữ liệu từ Google Drive", flush=True)
        except DriveError as error:
            print(f"[backup] chưa khôi phục được: {error}", flush=True)
    server = DemoServer(port, Store(data_path, seed=seed), static_root, host=host)
    if drive is not None:
        server.drive = drive
        server.drive_ready = True
        server.backup = backup.DriveBackup(
            server.store.db_path, drive, backup_id, interval=backup.backup_interval())
    return server


def main():
    server = create_server()
    scheme = "https" if server.secure_cookie else "http"
    address = server.public_url or f"{scheme}://127.0.0.1:{server.server_port}"
    print(f"CN Workforce: {address} ({'có' if server.auth_required else 'không'} mã truy cập công ty)", flush=True)
    if server.backup is not None:
        server.backup.start()

    def request_shutdown(*_):
        threading.Thread(target=server.shutdown, daemon=True).start()

    signal.signal(signal.SIGTERM, request_shutdown)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        if server.backup is not None:
            server.backup.stop()
        server.server_close()


if __name__ == "__main__":
    main()
