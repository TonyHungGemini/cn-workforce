import base64
import hashlib
import hmac
import json
import os
import time

SESSION_COOKIE = "cn_session"
SESSION_TTL = 12 * 3600


def _b64(value):
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _unb64(value):
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def access_code():
    return os.environ.get("CN_ACCESS_CODE", "")


def auth_required():
    return bool(access_code())


def _secret():
    secret = os.environ.get("CN_SECRET_KEY", "")
    if secret:
        return secret.encode("utf-8")
    # A single shared deployment without CN_SECRET_KEY still gets signed sessions,
    # but rotating the access code invalidates every open session.
    return hashlib.sha256(("cn-workforce:" + access_code()).encode("utf-8")).digest()


def verify_code(candidate):
    expected = access_code()
    if not expected or not isinstance(candidate, str):
        return False
    return hmac.compare_digest(hashlib.sha256(candidate.encode("utf-8")).digest(),
                                hashlib.sha256(expected.encode("utf-8")).digest())


def issue_session(now=None):
    now = int(now if now is not None else time.time())
    payload = _b64(json.dumps({"iat": now, "exp": now + SESSION_TTL}, separators=(",", ":")).encode("utf-8"))
    signature = _b64(hmac.new(_secret(), payload.encode("ascii"), hashlib.sha256).digest())
    return f"{payload}.{signature}"


def valid_session(token, now=None):
    if not token or token.count(".") != 1:
        return False
    payload, signature = token.split(".")
    try:
        expected = _b64(hmac.new(_secret(), payload.encode("ascii"), hashlib.sha256).digest())
        if not hmac.compare_digest(signature, expected):
            return False
        data = json.loads(_unb64(payload))
    except (ValueError, UnicodeDecodeError, UnicodeEncodeError):
        return False
    now = int(now if now is not None else time.time())
    return isinstance(data, dict) and type(data.get("exp")) is int and data["exp"] > now


def parse_cookies(header):
    cookies = {}
    for part in (header or "").split(";"):
        name, sep, value = part.strip().partition("=")
        if sep and name not in cookies:
            cookies[name] = value
    return cookies
