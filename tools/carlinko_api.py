"""CarLinko extended cloud API — the feature surface beyond telemetry + opcodes.

Recovered by static RE of CarLinko v1.14.0 `libapp.so` (see
docs/feature-parity-carlinko-v1.14.0.md). Every call is signed with the same
HMAC-SHA256 scheme as `auth` / `server.send_control`, so nothing here needs new
secrets — only the request *shapes*, which are inferred from the app's
`package:carlinko/**` module + `*Params`/`*Bean` field names.

Two signing variants exist in CarLinko and both are reproduced here:
  * GET / string-param bodies  -> values stringified   (auth.sign)
  * bodies with numeric fields -> values keep their JSON type (jsonEncode)
    e.g. remoteControl's `timeOut`, targetSoc's `targetSoc`. Using the wrong
    one yields a signature the server rejects, so each writer picks explicitly.

SAFETY: the write bodies below are RE-inferred, not yet confirmed against a
captured request. Every writer therefore defaults to `confirm=False`, which
returns the exact `{path, body}` it *would* POST **without sending it**, so you
can eyeball/verify the shape (or diff it against one real capture) before it
ever touches the car. Pass `confirm=True` to actually send. Reads always send.
"""
import json, time, hmac, hashlib, base64
import auth
import requests

# CarLinko error codes that mean "token expired, log in again and retry once".
_RELOGIN_CODES = {"9997", "40001", "40003", "401", "1001", "1002"}


def _token():
    """Current session token: token.txt if present, else a fresh login."""
    try:
        t = open(auth.TOKEN_FILE).read().strip()
        if t:
            return t
    except Exception:
        pass
    return auth.login()


def _ids():
    """(vehicle_id, device_sn) from creds.json / auth, or raise a clear error."""
    c = auth.cfg()
    vid = str(c.get("vehicle_id") or auth.VEHICLE_ID or "")
    dsn = str(c.get("device_sn") or auth.DEVICE_SN or "")
    return vid, dsn


def _sign_typed(body, ts):
    """Signature over jsonEncode(sortByKeyAsc({...body, timestamp})) WITH types
    preserved — the variant remoteControl/targetSoc need for numeric fields."""
    ordered = {k: v for k, v in sorted({**body, "timestamp": ts}.items())}
    msg = json.dumps(ordered, separators=(",", ":"), ensure_ascii=False).encode()
    return base64.b64encode(hmac.new(auth.SIGN_KEY, msg, hashlib.sha256).digest()).decode()


def api_get(path, params=None, timeout=20):
    """Signed GET. `params` are sent as the query string AND fed to the signer
    (stringified, matching auth.sign), exactly as the app signs a GET."""
    params = params or {}

    def _do(tok):
        r = requests.get(auth.api_base() + path, params=params,
                         headers=auth.headers_for(params, token=tok), timeout=timeout)
        return r.json()

    d = _do(_token())
    if str(d.get("code")) in _RELOGIN_CODES:
        d = _do(auth.login())
    return d


def api_body(path, body, method="POST", timeout=20, typed=True):
    """Signed request carrying a JSON body. `method` is POST or PUT -- the
    CarLinko `/user/device/manage/*` settings are **PUT** (POST returns 1003
    "method not supported"), while remoteControl is POST (confirmed live
    2026-10-22). `typed=True` keeps numeric JSON types in the signature
    (remoteControl/targetSoc style); `typed=False` stringifies (login style)."""
    def _do(tok):
        ts = auth.now_ms()
        sig = _sign_typed(body, ts) if typed else auth.sign({**body, "timestamp": ts})
        h = {"timestamp": ts, "signature": sig, "user-agent": "Dart/3.10 (dart:io)",
             "content-type": "application/json", "language": "en", "token": tok}
        r = requests.request(method, auth.api_base() + path,
                             data=json.dumps(body, separators=(",", ":"), ensure_ascii=False),
                             headers=h, timeout=timeout)
        return r.json()

    d = _do(_token())
    if str(d.get("code")) in _RELOGIN_CODES:
        d = _do(auth.login())
    return d


def api_post(path, body, timeout=20, typed=True):
    return api_body(path, body, method="POST", timeout=timeout, typed=typed)


def api_put(path, body, timeout=20, typed=True):
    return api_body(path, body, method="PUT", timeout=timeout, typed=typed)


def _ok(d):
    return {"ok": str(d.get("code")) == "0000", "code": d.get("code"),
            "msg": d.get("msg"), "data": d.get("data")}


def _preview(path, body, typed=True):
    return {"ok": None, "preview": True, "would_send": {"method": "POST", "path": path,
            "body": body, "signing": "typed" if typed else "stringified"},
            "note": "RE-inferred body shape — pass confirm=true to send, or verify "
                    "against a captured request first."}


# ---------------------------------------------------------------- reads (safe)

def notifications(page=1, size=20):
    """Notification / event history — `/user/notice/page`. Paging is `page`+
    `size` (confirmed live 2026-10-22). The response groups notices by category
    (system/control/vehicle/service), per unReadCount's *NoticeVo keys."""
    vid, _ = _ids()
    return _ok(api_get("/user/notice/page",
                       {"page": page, "size": size, "vehicleId": vid}))


def notice_unread():
    vid, _ = _ids()
    return _ok(api_get("/user/notice/unReadCount", {"vehicleId": vid, "clientType": "C"}))


def operation_log(page=1, size=20):
    """Remote-control / operation history — who sent what command, when.
    `/user/operating/page` with `page`+`size` (confirmed live 2026-10-22;
    `/user/vehicle/operatingRecord` returns 1000 and is not used)."""
    vid, _ = _ids()
    return _ok(api_get("/user/operating/page",
                       {"vehicleId": vid, "page": page, "size": size}))


def car_location():
    """Live GPS position of the car — `/maps/deviceLocate`. The dashboard has no
    car GPS otherwise. Tries POST then GET (endpoint method unconfirmed)."""
    vid, dsn = _ids()
    # POST (confirmed live 2026-10-22; GET/PUT -> 1003). `50008 车辆不在线` = the
    # car is offline right now, which is a valid answer, not a wiring error.
    return _ok(api_post("/maps/deviceLocate", {"vehicleId": vid, "deviceSn": dsn}, typed=True))


def maintenance(page=1, size=20):
    """Maintenance records / service reminders — `/user/maintain/page`."""
    vid, _ = _ids()
    return _ok(api_get("/user/maintain/page", {"vehicleId": vid, "page": page, "size": size}))


def alert_config():
    """Current alert toggles — `/user/device/manage/terminalNoticeConfig/{id}`.
    Returns the exact object shape; writes below echo it back (read-modify-write)."""
    vid, _ = _ids()
    return _ok(api_get("/user/device/manage/terminalNoticeConfig/" + vid))


def charge_schedule():
    """Current scheduled-charging config — `/user/device/manage/batterySchedule`.
    1003 here is state ('no schedule set' / device state), not a param error."""
    vid, dsn = _ids()
    return _ok(api_get("/user/device/manage/batterySchedule", {"vehicleId": vid, "deviceSn": dsn}))


def geofences(page=1, size=20):
    """Geofence list — `/user/electronicFence/list` with `page`+`size`
    (confirmed live 2026-10-22)."""
    vid, _ = _ids()
    return _ok(api_get("/user/electronicFence/list",
                       {"vehicleId": vid, "page": page, "size": size}))


# ------------------------------------------------------------- writes (gated)

def set_target_soc(target_soc, confirm=False):
    """Set the charge limit (target SoC %). `/user/device/manage/targetSoc`.
    Numeric field -> typed signing."""
    vid, dsn = _ids()
    body = {"vehicleId": vid, "deviceSn": dsn, "targetSoc": int(target_soc)}
    path = "/user/device/manage/targetSoc"
    if not confirm:
        return _preview(path, body)
    # PUT, not POST -- confirmed live 2026-10-22 (POST -> 1003).
    return _ok(api_put(path, body, typed=True))


def set_air_duration(minutes, confirm=False):
    """Set remote-climate run duration (minutes). `/user/device/manage/airDuration`."""
    vid, dsn = _ids()
    body = {"vehicleId": vid, "deviceSn": dsn, "airDuration": int(minutes)}
    path = "/user/device/manage/airDuration"
    if not confirm:
        return _preview(path, body)
    # PUT like the other /device/manage/* settings (see set_target_soc).
    return _ok(api_put(path, body, typed=True))


def set_alert_config(changes, confirm=False):
    """Read-modify-write the alert toggles. `changes` is a dict of the fields to
    override (lowVoltage / illegalOpened / forgetToLock / targetSoc /
    chargeComplete / highTemp / lowSoc / vibration). The full current object is
    fetched first and merged, so we never guess the schema — only the overrides.

    WRITE IS OWNER-ONLY (resolved by capture 2026-10-22): the alert settings
    live under the app's Device screen, which a sub-user cannot open ("Operation
    not supported by sub authorisation Device"). This dashboard authenticates as
    a sub-user, so its terminalNoticeConfig PUT is permission-denied, returned by
    the gateway as `1000 未知异常` -- not a body error. No body makes a sub-user's
    write succeed; editing needs the dashboard logged in as the vehicle OWNER,
    and then this writer works as-is. The READ works for sub-users, so the
    client correctly shows the toggles read-only. (Old note kept below.)
    The method is **PUT** (POST -> 1003 confirmed live
    2026-10-22), but every body shape tried — full object, booleans-only,
    path-param `/{vehicleId}` — returns `1000 未知异常` (a server-side
    exception). The exact PUT body needs one captured request from the app
    (Frida/mitm) to resolve; the READ (`alert_config`) works perfectly, so the
    client can show current state read-only until then."""
    cur = alert_config()
    base = cur.get("data") if isinstance(cur.get("data"), dict) else {}
    if not base:
        return {"ok": False, "code": cur.get("code"),
                "msg": "could not read current terminalNoticeConfig to modify", "data": cur}
    merged = {**base, **(changes or {})}
    path = "/user/device/manage/terminalNoticeConfig"
    if not confirm:
        return _preview(path, merged)
    return _ok(api_put(path, merged, typed=True))


def set_charge_schedule(enabled, hour=0, minute=0, duration=1, week=None,
                        confirm=False):
    """Set scheduled charging — `PUT /user/device/manage/batterySchedule`.

    Body shape captured from the app and verified live 2026-10-22 (the dashboard
    sent this exact shape to revert the account and got `0000`):
      `{vehicleId:int, enabled:bool, hour:0-23, minute:0-59, duration:<hours>,
        week:[7 bools]}`.
    `week` is the Sun..Sat repeat flags; all-false = one-time. There is **no
    working GET** (batterySchedule GET → 1003), so this is write-only — the UI
    sets a schedule rather than reading the current one back."""
    vid, _ = _ids()
    body = {
        "vehicleId": int(vid),
        "enabled": bool(enabled),
        "hour": int(hour),
        "minute": int(minute),
        "duration": int(duration),
        "week": list(week) if week else [False] * 7,
    }
    path = "/user/device/manage/batterySchedule"
    if not confirm:
        return _preview(path, body)
    return _ok(api_put(path, body, typed=True))
