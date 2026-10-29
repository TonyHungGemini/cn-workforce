import json
import os
import re
import socket
import stat
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

from store import APIError, Store


BASE_DIR = Path(__file__).resolve().parent
MAX_JSON_BYTES = 64 * 1024
CSP = (
    "default-src 'self'; script-src 'self' 'wasm-unsafe-eval'; style-src 'self' 'unsafe-inline'; "
    "img-src 'self' blob:; font-src 'self'; connect-src 'self'; worker-src 'self'; object-src 'none'; "
    "base-uri 'none'; frame-ancestors 'none'; form-action 'self'"
)
STATIC_FILES = {"index.html": "text/html; charset=utf-8", "app.js": "text/javascript; charset=utf-8",
                "ocr.js": "text/javascript; charset=utf-8", "styles.css": "text/css; charset=utf-8"}
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

    def __init__(self, port, store, static_root):
        self.store = store
        self.static_root = Path(static_root).absolute()
        super().__init__(("127.0.0.1", port), Handler)

    def get_request(self):
        connection, address = super().get_request()
        connection.settimeout(10)
        return connection, address


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "CNWorkforceDemo"
    sys_version = ""

    def log_message(self, format, *args):
        pass

    def _send(self, status, body, content_type="application/json; charset=utf-8", api=True):
        self.close_connection = True
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Connection", "close")
        self.send_header("Cache-Control", "no-store" if api else "no-cache")
        self.send_header("Content-Security-Policy", CSP)
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _json(self, status, value):
        body = json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode("utf-8")
        self._send(status, body)

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
        port = self.server.server_port
        hosts = self.headers.get_all("Host", [])
        if len(hosts) != 1 or hosts[0] not in (f"127.0.0.1:{port}", f"localhost:{port}"):
            raise APIError(403, "Host không được phép cho demo loopback.")
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

    def _body(self):
        port = self.server.server_port
        origins = self.headers.get_all("Origin", [])
        if len(origins) != 1 or origins[0] not in (f"http://127.0.0.1:{port}", f"http://localhost:{port}"):
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
        if length > MAX_JSON_BYTES:
            raise APIError(413, "JSON vượt giới hạn 64 KB.")
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
        self._send(200, body, content_type, api=False)

    def _dispatch(self):
        try:
            self._check_request()
            path = self._path()
            reads = {"/api/v1/bootstrap": self.server.store.bootstrap, "/api/v1/contract": self.server.store.contract}
            writes = {
                "/api/v1/workers": self.server.store.save_worker,
                "/api/v1/workers/archive": self.server.store.archive_worker,
                "/api/v1/events": self.server.store.add_event,
                "/api/v1/visitors": self.server.store.add_visitor,
                "/api/v1/visitors/transition": self.server.store.transition_visitor,
            }
            if self.command in ("GET", "HEAD"):
                if path in reads:
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


def create_server(port=None, data_dir=None, static_root=None):
    if port is None:
        value = os.environ.get("PORT", "8787")
        if not re.fullmatch(r"[0-9]{1,5}", value):
            raise ValueError("PORT must be an integer between 0 and 65535")
        port = int(value)
    if type(port) is not int or not 0 <= port <= 65535:
        raise ValueError("PORT must be an integer between 0 and 65535")
    data_dir = data_dir if data_dir is not None else os.environ.get("CN_DATA_DIR", str(BASE_DIR / ".local"))
    static_root = static_root if static_root is not None else BASE_DIR / "static"
    return DemoServer(port, Store(data_dir), static_root)


def main():
    server = create_server()
    print(f"Demo minh họa: http://127.0.0.1:{server.server_port} (không có xác thực hoặc tích hợp thật)", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
