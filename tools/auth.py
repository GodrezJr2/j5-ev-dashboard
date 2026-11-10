"""CarLinko auth: request signing + self-login (token auto-refresh).
Signing recovered from libapp.so (Blutter): see docs/decompiled/secure_*_utils.dart.
  signature = base64(HMAC-SHA256(SIGN_KEY,
              jsonEncode(sortByKeyAsc({...params, timestamp}))))   # Dart jsonEncode = no spaces
Login = POST /user/login with a plaintext password body. The `v-data` header the app sends is
NOT validated by the server (tested: login succeeds with it absent/empty/garbage), so we omit it.

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
# App-global request-signing key: the same string in every CarLinko install (recovered from the
# app binary). Override via creds.json "sign_key" only if the vendor ever rotates it.
SIGN_KEY = (_C.get("sign_key") or "mYj3fzMpn77bir66").encode()
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
        "user-agent": "Dart/3.10 (dart:io)",
        "language": "en",
    }
    if token:
        h["token"] = token
    return h

# ---- login guard ----
# Every automatic re-login (logger on a 9997, the server on a stale token) goes through here. Without
# it a rejected login was retried every ~3 s forever: ~28k POST /user/login a day against the account,
# exactly the kind of pattern that gets an account disabled. State lives in a file next to token.txt
# so the logger and the web server (separate processes) and restarts all share one budget.
LOGIN_STATE = os.path.join(_DATA, "login_state.json")
MAX_PER_HOUR = 6            # hard cap on automatic logins in any rolling hour
BACKOFF_BASE = 60           # first wait after a failed login; doubles per consecutive failure
BACKOFF_MAX = 30 * 60
REJECTS_TO_BLOCK = 3        # explicit server rejections in a row -> stop until a manual login
# Rejections that will never fix themselves by retrying. 10012 = 用户不存在 (no such user).
_FATAL_CODES = {"10012"}
_FATAL_WORDS = ("disabled", "disable", "禁用", "冻结", "locked", "password")

class LoginWait(RuntimeError):
    """Automatic login refused by the guard. `wait` = seconds until it may be tried again,
    or None when blocked until the owner logs in by hand (web login page / setup.py)."""
    def __init__(self, msg, wait=None):
        super().__init__(msg)
        self.wait = wait

def _state():
    try:
        s = json.load(open(LOGIN_STATE))
        return s if isinstance(s, dict) else {}
    except Exception:
        return {}

def _save_state(s):
    tmp = LOGIN_STATE + ".tmp"
    try:
        with open(tmp, "w") as f:
            json.dump(s, f)
        os.replace(tmp, LOGIN_STATE)
    except Exception:
        pass

def login_status():
    """None when automatic login is allowed right now, else {"blocked": bool, "wait": s, "reason"}.
    Read by the dashboard to show why the car stopped updating."""
    s = _state()
    if s.get("blocked"):
        return {"blocked": True, "wait": None, "reason": s["blocked"].get("reason", "")}
    now = time.time()
    if s.get("next_ok", 0) > now:
        return {"blocked": False, "wait": int(s["next_ok"] - now), "reason": s.get("last_error", "")}
    recent = [t for t in s.get("attempts", []) if now - t < 3600]
    if len(recent) >= MAX_PER_HOUR:
        return {"blocked": False, "wait": int(3600 - (now - min(recent))) + 1,
                "reason": f"{MAX_PER_HOUR} logins in the last hour"}
    return None

def _hour_cap_wait():
    now = time.time()
    recent = [t for t in _state().get("attempts", []) if now - t < 3600]
    return int(3600 - (now - min(recent))) + 1 if len(recent) >= MAX_PER_HOUR else 0

def _check_guard(retry=False):
    if retry:                       # a person pressed "try now": skip the backoff/block, keep the cap
        w = _hour_cap_wait()
        if w:
            raise LoginWait(f"{MAX_PER_HOUR} logins in the last hour, try again in {w // 60 + 1} min", w)
        return
    st = login_status()
    if st:
        if st["blocked"]:
            raise LoginWait("login blocked until a manual login: " + st["reason"], None)
        raise LoginWait(f"login backoff {st['wait']}s: {st['reason']}", st["wait"])

def _record(ok, reason="", fatal=False, rejected=False):
    s = _state()
    now = time.time()
    s["attempts"] = [t for t in s.get("attempts", []) if now - t < 3600] + [now]
    if ok:
        for k in ("fails", "rejects", "next_ok", "last_error", "blocked"):
            s.pop(k, None)
    else:
        s["fails"] = s.get("fails", 0) + 1
        s["rejects"] = s.get("rejects", 0) + 1 if rejected else 0
        s["last_error"] = reason[:200]
        s["next_ok"] = now + min(BACKOFF_BASE * 2 ** (s["fails"] - 1), BACKOFF_MAX)
        if fatal or s["rejects"] >= REJECTS_TO_BLOCK:
            s["blocked"] = {"reason": reason[:200], "t": int(now)}
    _save_state(s)

def login(manual=False, retry=False):
    """Log in with stored creds, return the new token (and save it to token.txt).

    manual=True is a person logging in on purpose (web login page, setup.py): it skips the guard
    and clears a block. retry=True is a person pressing "try now" on the dashboard banner: it skips
    the backoff and the block but still counts against the hourly cap. Everything else is automatic
    and is rate-limited / backed off."""
    if not manual:
        _check_guard(retry)
    try:
        token = _do_login()
    except _Rejected as e:
        fatal = e.code in _FATAL_CODES or any(w in e.msg.lower() for w in _FATAL_WORDS)
        _record(False, f"code {e.code}: {e.msg}", fatal=fatal, rejected=True)
        raise RuntimeError(f"login failed: {e.raw}")
    except Exception as e:
        _record(False, f"network: {e!r}")
        raise
    _record(True)
    return token

class _Rejected(Exception):
    def __init__(self, d):
        self.raw = d
        self.code = str(d.get("code")) if isinstance(d, dict) else "?"
        self.msg = str(d.get("msg") or d.get("message") or "") if isinstance(d, dict) else str(d)

def _do_login():
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
        "user-agent": "Dart/3.10 (dart:io)",
        "content-type": "application/json",
        "language": "en",
    }
    r = requests.post(api_base() + "/user/login", json=body, headers=h, timeout=20)
    d = r.json()
    if str(d.get("code")) != "0000":
        raise _Rejected(d)
    # token location confirmed from a real login response (adjust if needed)
    data = d.get("data") or {}
    token = data.get("token") if isinstance(data, dict) else data
    if not token:
        raise _Rejected({"code": "notoken", "msg": f"login ok but no token in response: {d}"})
    with open(TOKEN_FILE, "w") as f:
        f.write(token)
    return token

if __name__ == "__main__":
    print("logging in...")
    print("new token:", login(manual=True))
