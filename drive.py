import base64
import json
import os
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

FILE_ID = re.compile(r"[A-Za-z0-9_-]{10,100}")
TOKEN_URL = "https://oauth2.googleapis.com/token"
DRIVE_URL = "https://www.googleapis.com/drive/v3/files/{file_id}?alt=media&supportsAllDrives=true"
SCOPE = "https://www.googleapis.com/auth/drive.readonly"
MAX_BYTES = 10 * 1024 * 1024
CACHE_TTL = 7 * 24 * 3600


class DriveError(Exception):
    pass


def _credentials():
    inline = os.environ.get("CN_DRIVE_CREDENTIALS_JSON", "")
    source = inline or os.environ.get("CN_DRIVE_CREDENTIALS", "")
    if not source:
        return None
    if source.lstrip().startswith("{"):
        return json.loads(source)
    path = Path(source).expanduser()
    if not path.is_file():
        raise DriveError(f"Không tìm thấy tệp khoá Drive: {path.name}")
    return json.loads(path.read_text(encoding="utf-8"))


class Drive:
    def __init__(self, credentials, cache_dir, timeout=20):
        self.credentials = credentials
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.timeout = timeout
        self._lock = threading.Lock()
        self._token = None
        self._token_expiry = 0
        self._private_key = None

    @classmethod
    def from_env(cls, cache_dir):
        try:
            credentials = _credentials()
        except (ValueError, OSError) as error:
            raise DriveError("Tệp khoá Drive không hợp lệ.") from error
        return cls(credentials, cache_dir) if credentials else None

    @property
    def configured(self):
        return self.credentials is not None

    def _key(self):
        if self._private_key is None:
            try:
                from cryptography.hazmat.primitives import serialization
                self._private_key = serialization.load_pem_private_key(
                    self.credentials["private_key"].encode("utf-8"), password=None)
            except Exception as error:
                raise DriveError("Không nạp được khoá Drive; kiểm tra service account.") from error
        return self._private_key

    def _access_token(self):
        with self._lock:
            if self._token and time.time() < self._token_expiry - 60:
                return self._token
            from cryptography.hazmat.primitives import hashes
            from cryptography.hazmat.primitives.asymmetric import padding

            now = int(time.time())
            claims = {
                "iss": self.credentials["client_email"],
                "scope": SCOPE,
                "aud": self.credentials.get("token_uri", TOKEN_URL),
                "iat": now,
                "exp": now + 3600,
            }
            header = {"alg": "RS256", "typ": "JWT"}
            segments = []
            for part in (header, claims):
                raw = json.dumps(part, separators=(",", ":")).encode("utf-8")
                segments.append(base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii"))
            signing_input = ".".join(segments).encode("ascii")
            signature = self._key().sign(signing_input, padding.PKCS1v15(), hashes.SHA256())
            segments.append(base64.urlsafe_b64encode(signature).rstrip(b"=").decode("ascii"))
            assertion = ".".join(segments)
            body = urllib.parse.urlencode({
                "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                "assertion": assertion,
            }).encode("ascii")
            request = urllib.request.Request(
                self.credentials.get("token_uri", TOKEN_URL), data=body, method="POST",
                headers={"Content-Type": "application/x-www-form-urlencoded"})
            try:
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    payload = json.loads(response.read().decode("utf-8"))
                self._token = payload["access_token"]
                self._token_expiry = now + int(payload.get("expires_in", 3600))
            except (urllib.error.URLError, ValueError, TypeError, KeyError, OSError) as error:
                raise DriveError("Không lấy được quyền đọc Google Drive.") from error
            return self._token

    def _download(self, file_id):
        self._access_token()
        request = urllib.request.Request(
            DRIVE_URL.format(file_id=urllib.parse.quote(file_id)), method="GET",
            headers={"Authorization": f"Bearer {self._token}"})
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            length = response.headers.get("Content-Length")
            try:
                oversized = bool(length) and int(length) > MAX_BYTES
            except ValueError:
                oversized = False
            if oversized:
                raise DriveError("Ảnh vượt quá 10 MB.")
            body = response.read(MAX_BYTES + 1)
            if len(body) > MAX_BYTES:
                raise DriveError("Ảnh vượt quá 10 MB.")
            content_type = (response.headers.get("Content-Type") or "application/octet-stream").split(";")[0]
            return body, content_type

    def fetch(self, file_id):
        if not FILE_ID.fullmatch(file_id or ""):
            raise DriveError("Mã tệp Drive không hợp lệ.")
        image = self.cache_dir / file_id
        meta = self.cache_dir / f"{file_id}.json"
        if image.is_file() and meta.is_file() and time.time() - image.stat().st_mtime < CACHE_TTL:
            try:
                return image.read_bytes(), json.loads(meta.read_text(encoding="utf-8"))["type"]
            except (OSError, ValueError, KeyError):
                pass
        try:
            body, content_type = self._download(file_id)
        except (urllib.error.HTTPError, urllib.error.URLError, OSError) as error:
            if image.is_file() and meta.is_file():
                try:
                    return image.read_bytes(), json.loads(meta.read_text(encoding="utf-8"))["type"]
                except (OSError, ValueError, KeyError):
                    pass
            raise DriveError("Không tải được ảnh từ Google Drive.") from error
        try:
            temporary = image.with_suffix(".part")
            temporary.write_bytes(body)
            temporary.replace(image)
            meta.write_text(json.dumps({"type": content_type}), encoding="utf-8")
        except OSError:
            pass  # A read-only or full disk must not stop image delivery.
        return body, content_type
