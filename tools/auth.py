"""CarLinko auth: request signing + self-login (token auto-refresh).
Signing recovered from libapp.so (Blutter): see docs/decompiled/secure_*_utils.dart.
  signature = base64(HMAC-SHA256("<SIGN_KEY>",
              jsonEncode(sortByKeyAsc({...params, timestamp}))))   # Dart jsonEncode = no spaces
Login = POST /user/login with a plaintext password body.

Credentials come from creds.json next to this file (NOT committed):
  {"email": "...", "password": "...", "region": "sea"}
"""
import os, json, time, hmac, hashlib, base64, socket

# Force IPv4 (same reason as logger: some hosts resolve AAAA and hang).
_orig_gai = socket.getaddrinfo
def _gai_v4(host, port, family=0, *a, **k):
    return _orig_gai(host, port, socket.AF_INET, *a, **k) or _orig_gai(host, port, family, *a, **k)
socket.getaddrinfo = _gai_v4

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
_DATA = os.environ.get("CARLINKO_DATA") or HERE   # Docker mounts a data dir here; else alongside the code
CREDS = os.path.join(_DATA, "creds.json")
TOKEN_FILE = os.path.join(_DATA, "token.txt")

def cfg():
    """All instance-specific values live in creds.json (gitignored). See creds.example.json."""
    try:
        return json.load(open(CREDS))
    except Exception:
        return {}

_C = cfg()
# App request-signing key + device blob — extract these once from your own app capture
# (see README "First-time capture"); they are NOT shipped with the source.
SIGN_KEY = (_C.get("sign_key") or "").encode()
VDATA = _C.get("v_data") or ""
VEHICLE_ID = str(_C.get("vehicle_id") or "")
DEVICE_SN = _C.get("device_sn") or ""

def _require(val, name):
    if not val:
        raise RuntimeError(f"{name} missing from creds.json — see creds.example.json / README")
    return val

def _region():
    try:
        return json.load(open(CREDS)).get("region", "sea")
    except Exception:
        return "sea"

def api_base():
    return f"https://cqr-api-{_region()}.hzhjcl.com"

def now_ms():
    return str(int(time.time() * 1000))

def sign(params):
    _require(SIGN_KEY, "sign_key")
    m = {k: ("" if v is None else str(v)) for k, v in params.items()}
    ordered = {k: m[k] for k in sorted(m.keys())}
    msg = json.dumps(ordered, separators=(",", ":"), ensure_ascii=False).encode()
    return base64.b64encode(hmac.new(SIGN_KEY, msg, hashlib.sha256).digest()).decode()

def headers_for(params, token=None):
    ts = now_ms()
    h = {
        "timestamp": ts,
        "signature": sign({**params, "timestamp": ts}),
        "v-data": VDATA,
        "user-agent": "Dart/3.10 (dart:io)",
        "language": "en",
    }
    if token:
        h["token"] = token
    return h

def login():
    """Log in with stored creds, return the new token (and save it to token.txt)."""
    c = json.load(open(CREDS))
    body = {
        "account": c["email"],
        "password": c["password"],
        "method": "PASSWORD",
        "appType": "APP",
        "osType": "ANDROID",
        "appName": "CarLinko",
        "appVersion": "1.12.0",
        "osVersion": "13",
        "language": "en",
        "timeZone": "Asia/Jakarta",
        "phoneBrand": "Google",
        "phoneModel": "Pixel 7 Pro",
        "md5": "",
        "verifyCode": "",
        "dateTime": now_ms(),
    }
    ts = now_ms()
    h = {
        "timestamp": ts,
        "signature": sign({**body, "timestamp": ts}),
        "v-data": VDATA,
        "user-agent": "Dart/3.10 (dart:io)",
        "content-type": "application/json",
        "language": "en",
    }
    r = requests.post(api_base() + "/user/login", json=body, headers=h, timeout=20)
    d = r.json()
    if str(d.get("code")) != "0000":
        raise RuntimeError(f"login failed: {d}")
    # token location confirmed from a real login response (adjust if needed)
    data = d.get("data") or {}
    token = data.get("token") if isinstance(data, dict) else data
    if not token:
        raise RuntimeError(f"login ok but no token in response: {d}")
    with open(TOKEN_FILE, "w") as f:
        f.write(token)
    return token

if __name__ == "__main__":
    print("logging in...")
    print("new token:", login())
