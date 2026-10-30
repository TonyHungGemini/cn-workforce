# -*- coding: utf-8 -*-
"""OCR thẻ CMND/CCCD bằng AI, chạy phía máy chủ (proxy giữ khoá bí mật).

Nhà cung cấp AI được cấu hình bằng biến môi trường CN_OCR_PROVIDERS (JSON) hoặc
GEMINI_API_KEY. Khoá KHÔNG bao giờ nằm trong mã nguồn, không trả về cho trình duyệt.
Khi hết hạn mức, hệ thống tự xoay sang nhà cung cấp kế tiếp và trả về văn bản
yêu cầu lập trình viên cung cấp danh sách API dự phòng.
"""
import base64
import binascii
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

GEMINI_API_ROOT = "https://generativelanguage.googleapis.com/v1beta/models"
DEFAULT_GEMINI_MODELS = ("gemini-flash-latest", "gemini-2.5-flash")
MAX_IMAGE_BYTES = 5 * 1024 * 1024
MIN_IMAGE_BYTES = 2048
COOLDOWN_SECONDS = 600
MAX_ERROR_CHARS = 200
IMAGE_URL = re.compile(r"^data:(image/(?:jpeg|png|webp));base64,([A-Za-z0-9+/=\s]+)$")
PROVIDER_KINDS = ("gemini", "generic")

FIELD_LIMITS = {
    "ten_that": 120, "cmnd": 32, "ngay_sinh": 20, "tuoi": 4, "gioi_tinh": 4,
    "noi_sinh": 200, "dia_chi": 300, "noi_sinh_goc": 300, "dia_chi_goc": 300, "loai_the": 60,
}
FIELDS = tuple(FIELD_LIMITS)

OCR_PROMPT = """Bạn là chuyên gia AI trích xuất thông tin giấy tờ tùy thân đa quốc gia (đặc biệt là Căn cước công dân Campuchia - Cambodian National ID Card, CCCD/CMND Việt Nam, Hộ chiếu).

Nhiệm vụ:
1. Đọc và trích xuất chính xác các thông tin trên thẻ căn cước:
   - Họ và tên (ten_that): Viết hoa chữ La-tinh (ví dụ: BOEURN YON).
   - Số CMND/CCCD (cmnd): Dãy số định danh (thẻ Campuchia 9 số, CCCD VN 12 số hoặc 9 số).
   - Ngày sinh (ngay_sinh): Định dạng dd/mm/yyyy.
   - Tuổi (tuoi): Số tuổi tính đến năm hiện tại.
   - Giới tính (gioi_tinh): "M" (Nam/Male/ប្រុស) hoặc "F" (Nữ/Female/ស្រី).
   - Nơi sinh (noi_sinh): ទីកន្លែងកំណើត / Place of birth.
   - Địa chỉ thường trú (dia_chi): អាសយដ្ឋាន / Nơi thường trú / Residence.
   - Giữ nguyên văn bản gốc của nơi sinh và địa chỉ tại noi_sinh_goc, dia_chi_goc.
   - loai_the: "CCCD", "CMND", "Hộ chiếu" hoặc "Thẻ Campuchia".

2. ĐẶC BIỆT XỬ LÝ & DỊCH ĐỊA CHỈ, NƠI SINH CAMPUCHIA SANG TIẾNG VIỆT CHUẨN:
   * ភូមិ (Phum) -> "Thôn" hoặc "Ấp"; ឃុំ (Khum) -> "Xã"; សង្កាត់ (Sangkat) -> "Phường";
     ស្រុក (Srok) -> "Huyện"; ខណ្ឌ (Khan) -> "Quận"; ក្រុង (Krong) -> "Thị xã";
     ខេត្ត (Khet) -> "Tỉnh"; រាជធានី -> "Thủ đô".
   * Từ chỉ phương hướng: ជើង (Bắc), ត្បូង (Nam), កើត (Đông), លិច (Tây),
     លើ (Thượng), ក្រោម (Hạ), ធំ (Lớn), តូច (Nhỏ), ថ្មី (Mới), ចាស់ (Cũ).
   * Phiên âm La-tinh chuẩn cho tỉnh Campuchia: Kampong Thom, Kampong Cham, Prey Veng,
     Svay Rieng, Kandal, Takeo, Battambang, Siem Reap, Kratie, Stung Treng, Ratanakiri,
     Mondulkiri, Banteay Meanchey, Kampot, Kep, Koh Kong, Pursat, Kampong Chhnang,
     Kampong Speu, Preah Sihanouk, Preah Vihear, Oddar Meanchey, Pailin, Tbong Khmum,
     Phnom Penh.
   * Định dạng mẫu: "Thôn Chork, Xã Kampong Chen Cheung, Huyện Stoung, Tỉnh Kampong Thom".

3. Không bịa dữ liệu: trường không đọc được thì để chuỗi rỗng. Trả về JSON đúng cấu trúc."""

OCR_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "ten_that": {"type": "STRING"},
        "cmnd": {"type": "STRING"},
        "ngay_sinh": {"type": "STRING"},
        "tuoi": {"type": "STRING"},
        "gioi_tinh": {"type": "STRING"},
        "noi_sinh": {"type": "STRING"},
        "dia_chi": {"type": "STRING"},
        "noi_sinh_goc": {"type": "STRING"},
        "dia_chi_goc": {"type": "STRING"},
        "loai_the": {"type": "STRING"},
    },
    "required": ["ten_that"],
}

REQUEST_TEXT = (
    "App Quản lý Công nhân cần API AI để đọc thẻ CMND/CCCD (OCR) khi nối vào App mẹ.\n"
    "Vui lòng cung cấp: (1) API hiện có để kích hoạt ngay; (2) danh sách API dự phòng khi hết hạn mức.\n"
    "Mỗi API cần: endpoint HTTPS nhận POST JSON, cách xác thực (Bearer token hoặc header riêng), "
    "hạn mức mỗi ngày, thời gian chờ tối đa.\n"
    "Dữ liệu App gửi: {\"image\": \"data URL JPEG/PNG/WebP <= 5 MB\", \"mime\": \"image/jpeg\", "
    "\"fields\": [\"ten_that\", \"cmnd\", \"ngay_sinh\", \"tuoi\", \"gioi_tinh\", \"noi_sinh\", "
    "\"dia_chi\", \"noi_sinh_goc\", \"dia_chi_goc\", \"loai_the\"]}.\n"
    "Dữ liệu App nhận: {\"ok\": true, \"data\": {\"ten_that\": \"...\", \"cmnd\": \"...\"}} "
    "hoặc {\"ok\": false, \"error\": \"...\"}.\n"
    "Với API Gemini, cung cấp khoá qua biến môi trường GEMINI_API_KEY. Với API riêng, "
    "khai báo danh sách trong CN_OCR_PROVIDERS trên máy chủ. Không gửi khoá qua chat."
)

PROVIDER_SAMPLE = {
    "providers": [
        {"id": "gemini-chinh", "kind": "gemini", "key_env": "GEMINI_API_KEY",
         "models": ["gemini-flash-latest", "gemini-2.5-flash"], "quota_per_day": 200, "timeout": 12},
        {"id": "api-phu-1", "kind": "generic", "endpoint": "https://api.example.com/ocr",
         "key_env": "OCR_FALLBACK_1_KEY", "quota_per_day": 500, "timeout": 15},
    ],
    "note": "Dán JSON này vào biến môi trường CN_OCR_PROVIDERS; thay endpoint và tên biến khoá thật.",
}


class OcrInputError(Exception):
    """Ảnh gửi lên không hợp lệ (lỗi phía người dùng)."""


class ProviderFailure(Exception):
    def __init__(self, message, quota=False):
        super().__init__(message)
        self.message = message
        self.quota = quota


def _is_quota(code, detail):
    if code in (402, 429):
        return True
    text_value = (detail or "").upper()
    markers = ("RESOURCE_EXHAUSTED", "QUOTA", "RATE_LIMIT", "RATE LIMIT",
               "TOO MANY REQUESTS", "EXCEEDED YOUR CURRENT")
    return any(marker in text_value for marker in markers)


def _failure_text(code, detail):
    if code == 402:
        return "Nhà cung cấp báo hết hạn mức (402)."
    if code == 429:
        return "Nhà cung cấp báo hết hạn mức (429)."
    if code in (401, 403):
        return "Khoá API bị từ chối (HTTP %d)." % code
    if code == 404:
        return "Endpoint AI không tồn tại (404)."
    detail = re.sub(r"\s+", " ", (detail or "")).strip()[:160]
    if detail:
        return "Nhà cung cấp AI trả lỗi HTTP %d: %s" % (code, detail)
    return "Nhà cung cấp AI trả lỗi HTTP %d." % code


def _http_post_json(url, payload, headers, timeout):
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(url, data=data, method="POST", headers=dict(
        headers, **{"Content-Type": "application/json", "User-Agent": "cn-workforce-ocr"}))
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read()
    except urllib.error.HTTPError as exc:
        try:
            detail = exc.read(4096).decode("utf-8", "replace")
        except Exception:
            detail = ""
        raise ProviderFailure(_failure_text(exc.code, detail), quota=_is_quota(exc.code, detail)) from None
    except (urllib.error.URLError, TimeoutError, OSError):
        raise ProviderFailure("Không kết nối được nhà cung cấp AI.") from None
    try:
        parsed = json.loads(body.decode("utf-8"))
    except ValueError:
        raise ProviderFailure("Phản hồi AI không phải JSON.") from None
    if not isinstance(parsed, dict):
        raise ProviderFailure("Phản hồi AI không đúng cấu trúc.")
    return parsed


def _strip_fence(text):
    text = (text or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```[A-Za-z]*\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return text


def _birth_date(value):
    """Thẻ Việt Nam in ngày dạng dd/mm/yyyy; ô ngày sinh của hồ sơ cần ISO."""
    value = re.sub(r"\s+", " ", value or "").strip()
    for pattern, order in ((r"^(\d{4})-(\d{1,2})-(\d{1,2})$", "ymd"),
                           (r"^(\d{1,2})([/.\-])(\d{1,2})\2(\d{4})$", "dmy")):
        match = re.match(pattern, value)
        if not match:
            continue
        if order == "ymd":
            year, month, day = (int(part) for part in match.groups())
        else:
            day, month, year = int(match.group(1)), int(match.group(3)), int(match.group(4))
        if 1900 <= year <= 2100:
            try:
                return datetime(year, month, day).strftime("%Y-%m-%d")
            except ValueError:
                return ""
        return ""
    return ""


def normalize_fields(data):
    if not isinstance(data, dict):
        raise ProviderFailure("AI trả về dữ liệu không hợp lệ.")
    fields = {}
    for name, limit in FIELD_LIMITS.items():
        value = data.get(name, "")
        value = "" if value is None else re.sub(r"\s+", " ", str(value)).strip()
        fields[name] = value[:limit]
    fields["ngay_sinh"] = _birth_date(fields["ngay_sinh"])
    gender = str(data.get("gioi_tinh") or "").strip().casefold()
    fields["gioi_tinh"] = ("M" if gender in {"m", "male", "nam", "ប្រុស"}
                           else "F" if gender in {"f", "female", "nữ", "nu", "ស្រី"} else "")
    if not fields["ten_that"] and not fields["cmnd"]:
        raise ProviderFailure("AI không đọc được họ tên hay số giấy tờ trên thẻ.")
    return fields


def split_image(image):
    if not isinstance(image, str) or not image.strip():
        raise ValueError("Thiếu ảnh để đọc.")
    match = IMAGE_URL.match(image.strip())
    if not match:
        raise ValueError("Ảnh phải là data URL JPEG, PNG hoặc WebP dạng base64.")
    mime = match.group(1).lower()
    payload = re.sub(r"\s+", "", match.group(2))
    try:
        raw = base64.b64decode(payload, validate=True)
    except (ValueError, binascii.Error):
        raise ValueError("Dữ liệu ảnh base64 không hợp lệ.") from None
    if len(raw) > MAX_IMAGE_BYTES:
        raise ValueError("Ảnh vượt quá 5 MB. Hãy chụp lại ở độ phân giải thấp hơn.")
    if len(raw) < MIN_IMAGE_BYTES:
        raise ValueError("Ảnh quá nhỏ hoặc rỗng.")
    return mime, payload


def _endpoint(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError("thiếu endpoint")
    parts = urllib.parse.urlsplit(value.strip())
    if parts.scheme not in ("https", "http") or not parts.hostname:
        raise ValueError("endpoint phải là URL https hợp lệ")
    if parts.username or parts.password:
        raise ValueError("endpoint không được chứa thông tin đăng nhập")
    if parts.scheme == "http" and parts.hostname not in ("localhost", "127.0.0.1", "::1"):
        raise ValueError("http chỉ cho phép với localhost")
    return value.strip()


def _load_provider(item, index):
    if not isinstance(item, dict):
        raise ValueError("phải là một đối tượng JSON")
    kind = item.get("kind", "gemini")
    if kind not in PROVIDER_KINDS:
        raise ValueError("kind phải là gemini hoặc generic")
    provider_id = str(item.get("id") or "provider-%d" % (index + 1)).strip()
    if not re.fullmatch(r"[A-Za-z0-9._-]{1,40}", provider_id):
        raise ValueError("id chỉ gồm chữ, số, dấu chấm, gạch dưới, gạch nối")
    key_env = str(item.get("key_env") or "").strip()
    if kind == "gemini":
        key_env = key_env or "GEMINI_API_KEY"
        endpoint = _endpoint(item.get("endpoint") or GEMINI_API_ROOT).rstrip("/")
        models = item.get("models") or list(DEFAULT_GEMINI_MODELS)
        if not isinstance(models, list) or not models or not all(
                isinstance(model, str) and model.strip() for model in models):
            raise ValueError("models phải là danh sách tên model")
        models = [model.strip() for model in models]
    else:
        endpoint = _endpoint(item.get("endpoint"))
        models = []
    quota = item.get("quota_per_day")
    if quota is not None and (isinstance(quota, bool) or not isinstance(quota, int) or quota < 1):
        raise ValueError("quota_per_day phải là số nguyên dương")
    timeout = item.get("timeout", 12)
    if isinstance(timeout, bool) or not isinstance(timeout, int) or not 1 <= timeout <= 30:
        raise ValueError("timeout phải là số nguyên từ 1 đến 30 giây")
    return {"id": provider_id, "kind": kind, "endpoint": endpoint, "key_env": key_env,
            "models": models, "quota_per_day": quota, "timeout": timeout}


def load_providers(env):
    providers = []
    errors = []
    seen = set()
    raw = (env.get("CN_OCR_PROVIDERS") or "").strip()
    items = []
    if raw:
        try:
            items = json.loads(raw)
        except ValueError as exc:
            errors.append("CN_OCR_PROVIDERS không phải JSON hợp lệ: %s" % exc)
            items = []
        if not isinstance(items, list):
            errors.append("CN_OCR_PROVIDERS phải là một mảng JSON.")
            items = []
    for index, item in enumerate(items):
        try:
            provider = _load_provider(item, index)
        except ValueError as exc:
            errors.append("Nhà cung cấp #%d: %s." % (index + 1, exc))
            continue
        if provider["id"] in seen:
            errors.append("Nhà cung cấp #%d: id %s bị trùng." % (index + 1, provider["id"]))
            continue
        seen.add(provider["id"])
        providers.append(provider)
    if (env.get("GEMINI_API_KEY") or "").strip() and "gemini" not in seen:
        providers.append({"id": "gemini", "kind": "gemini", "endpoint": GEMINI_API_ROOT,
                          "key_env": "GEMINI_API_KEY", "models": list(DEFAULT_GEMINI_MODELS),
                          "quota_per_day": None, "timeout": 12})
    return providers, errors


class Service:
    def __init__(self, store, env=None):
        self.store = store
        self.env = dict(os.environ if env is None else env)
        self.providers, self.config_errors = load_providers(self.env)
        self._errors = {}

    def request(self):
        return {"text": REQUEST_TEXT, "sample": PROVIDER_SAMPLE,
                "fields": list(FIELDS), "max_image_bytes": MAX_IMAGE_BYTES}

    def _redact(self, message):
        text_value = str(message)[:MAX_ERROR_CHARS]
        for provider in self.providers:
            secret = (self.env.get(provider["key_env"]) or "").strip()
            if secret:
                text_value = text_value.replace(secret, "***")
        return text_value

    def _cooling(self, provider, used):
        quota = provider["quota_per_day"]
        if quota is not None and used.get("calls", 0) >= quota:
            return True
        stamp = used.get("exhausted_at") or ""
        if not stamp:
            return False
        try:
            exhausted = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
        except ValueError:
            return False
        return (datetime.now(timezone.utc) - exhausted).total_seconds() < COOLDOWN_SECONDS

    def _cooldown_until(self, provider, used):
        if not self._cooling(provider, used):
            return ""
        quota = provider["quota_per_day"]
        if quota is not None and used.get("calls", 0) >= quota:
            return ""
        try:
            exhausted = datetime.fromisoformat((used.get("exhausted_at") or "").replace("Z", "+00:00"))
        except ValueError:
            return ""
        return (exhausted + timedelta(seconds=COOLDOWN_SECONDS)).isoformat(timespec="seconds").replace("+00:00", "Z")

    def status(self):
        usage = self.store.ocr_usage()
        providers = []
        for provider in self.providers:
            used = usage.get(provider["id"], {})
            key_present = not provider["key_env"] or bool((self.env.get(provider["key_env"]) or "").strip())
            cooling = key_present and self._cooling(provider, used)
            providers.append({
                "id": provider["id"], "kind": provider["kind"], "key_env": provider["key_env"],
                "models": list(provider["models"]), "quota_per_day": provider["quota_per_day"],
                "calls": used.get("calls", 0), "errors": used.get("errors", 0),
                "quota_hits": used.get("quota_hits", 0), "exhausted_at": used.get("exhausted_at", ""),
                "state": "missing_key" if not key_present else ("cooling" if cooling else "ready"),
                "cooldown_until": self._cooldown_until(provider, used),
                "last_error": self._errors.get(provider["id"], ""),
                "target": urllib.parse.urlsplit(provider["endpoint"]).hostname or "",
            })
        return {"ok": True, "configured": bool(self.providers), "providers": providers,
                "errors": list(self.config_errors), "request": self.request(),
                "limits": {"max_image_bytes": MAX_IMAGE_BYTES, "cooldown_seconds": COOLDOWN_SECONDS}}

    def _unavailable(self, code, message):
        return {"ok": False, "error": code, "message": message, "request": self.request()}

    def _mark(self, provider, outcome):
        try:
            self.store.record_ocr(provider["id"], outcome)
        except Exception:
            pass

    def recognize(self, image):
        try:
            mime, b64 = split_image(image)
        except ValueError as exc:
            raise OcrInputError(str(exc)) from None
        if not self.providers:
            return self._unavailable("no_provider", "Chưa cấu hình API AI nào trên máy chủ.")
        usage = self.store.ocr_usage()
        attempted = False
        quota_blocked = False
        failures = []
        for provider in self.providers:
            used = usage.get(provider["id"], {})
            if provider["key_env"] and not (self.env.get(provider["key_env"]) or "").strip():
                continue
            if self._cooling(provider, used):
                quota_blocked = True
                continue
            attempted = True
            try:
                if provider["kind"] == "gemini":
                    fields = self._call_gemini(provider, mime, b64)
                else:
                    fields = self._call_generic(provider, mime, b64)
            except ProviderFailure as exc:
                message = self._redact(exc.message)
                self._errors[provider["id"]] = message
                self._mark(provider, "quota" if exc.quota else "error")
                failures.append(message)
                if exc.quota:
                    quota_blocked = True
                continue
            self._errors.pop(provider["id"], None)
            self._mark(provider, "ok")
            return {"ok": True, "source": "ai", "provider": provider["id"], "fields": fields}
        if quota_blocked:
            return self._unavailable(
                "quota_exhausted",
                "Đã hết hạn mức AI của tất cả API đang cấu hình. Hãy bổ sung API dự phòng.")
        if not attempted:
            return self._unavailable("no_provider", "Chưa có khoá API hợp lệ trên máy chủ.")
        return self._unavailable("failed", failures[-1] if failures else "AI chưa đọc được ảnh này.")

    def _call_gemini(self, provider, mime, b64):
        key = (self.env.get(provider["key_env"]) or "").strip()
        payload = {
            "contents": [{"parts": [{"inlineData": {"mimeType": mime, "data": b64}},
                                    {"text": OCR_PROMPT}]}],
            "generationConfig": {"responseMimeType": "application/json",
                                 "responseSchema": OCR_SCHEMA,
                                 "thinkingConfig": {"thinkingBudget": 0}},
        }
        last = None
        for model in provider["models"]:
            url = "%s/%s:generateContent?key=%s" % (
                provider["endpoint"], urllib.parse.quote(model, safe=""),
                urllib.parse.quote(key, safe=""))
            try:
                body = _http_post_json(url, payload, {}, provider["timeout"])
            except ProviderFailure as exc:
                if exc.quota:
                    raise
                last = exc
                continue
            candidates = body.get("candidates") or []
            text_value = ""
            if candidates:
                parts = (candidates[0].get("content") or {}).get("parts") or []
                text_value = "".join(part.get("text") or "" for part in parts).strip()
            if not text_value:
                last = ProviderFailure("AI không trả về nội dung.")
                continue
            try:
                data = json.loads(_strip_fence(text_value))
            except ValueError:
                last = ProviderFailure("Phản hồi AI không đúng định dạng JSON.")
                continue
            return normalize_fields(data)
        raise last or ProviderFailure("AI không trả về kết quả.")

    def _call_generic(self, provider, mime, b64):
        key = (self.env.get(provider["key_env"]) or "").strip() if provider["key_env"] else ""
        headers = {"Authorization": "Bearer " + key} if key else {}
        payload = {"image": "data:%s;base64,%s" % (mime, b64), "mime": mime, "fields": list(FIELDS)}
        body = _http_post_json(provider["endpoint"], payload, headers, provider["timeout"])
        if body.get("ok") is False:
            raise ProviderFailure(str(body.get("error") or body.get("message") or "API OCR báo lỗi."))
        if isinstance(body.get("data"), dict):
            data = body["data"]
        elif isinstance(body.get("fields"), dict):
            data = body["fields"]
        else:
            data = body
        return normalize_fields(data)