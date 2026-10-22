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

SAFETY: every write body below was captured from the app (tools/capture/,
2026-10-22) and verified live. Writers still default to `confirm=False`, which
returns the exact `{method, path, body}` it *would* send **without sending it**, so a
client can show what is about to change before it touches the car or account.
Pass `confirm=True` to actually send. Reads always send.
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


def _preview(method, path, body, typed=True):
    return {"ok": None, "preview": True, "would_send": {"method": method, "path": path,
            "body": body, "signing": "typed" if typed else "stringified"},
            "note": "preview only, nothing sent -- pass confirm=true to send."}


def _put_setting(path, body, confirm):
    """Preview or send one `/user/device/manage/*` setting. The preview and the real
    request take their method from here, so a preview always shows what would really
    go out. PUT, not POST -- confirmed live 2026-10-22 (POST -> 1003)."""
    if not confirm:
        return _preview("PUT", path, body)
    return _ok(api_put(path, body, typed=True))


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
    """The vehicle's notice config — `/user/device/manage/terminalNoticeConfig/{id}`.
    One object per vehicle (owner and sub-users see the same `id`): the alert switches
    (ALERT_SWITCHES) and scheduled travel (`startupAppointment` + `extra`). The writers
    below change one item each."""
    vid, _ = _ids()
    return _ok(api_get("/user/device/manage/terminalNoticeConfig/" + vid))


def _json_field(v):
    """CarLinko nests some settings as JSON *strings* inside the notice config."""
    if isinstance(v, dict):
        return v
    try:
        return json.loads(v) if isinstance(v, str) and v else {}
    except ValueError:
        return {}


def device_settings():
    """The vehicle's settings, parsed from ONE notice-config read so clients don't unpack
    CarLinko's JSON-in-a-string fields: charge limit (`targetSoc`), charge schedule
    (`batterySchedule`), scheduled travel (`startupAppointment` + `extra`, hour/minute
    sent as zero-padded strings) and the alert switches. A missing part is None."""
    cur = alert_config()
    if not cur.get("ok") or not isinstance(cur.get("data"), dict):
        return cur
    a = cur["data"]
    cs, tr = _json_field(a.get("batterySchedule")), _json_field(a.get("extra"))
    num = lambda v: int(v) if str(v).isdigit() else None
    return {**cur, "data": {
        "targetSoc": a.get("targetSoc"),
        "chargeSchedule": {"enabled": bool(cs.get("enabled")), "hour": num(cs.get("hour")),
                           "minute": num(cs.get("minute")), "duration": num(cs.get("duration")),
                           "week": cs.get("week")} if cs else None,
        "scheduledTravel": {"enabled": bool(a.get("startupAppointment")), "hour": num(tr.get("hour")),
                            "minute": num(tr.get("minute")), "week": tr.get("week")} if tr else None,
        "alerts": {name: a.get(field) for name, field in ALERT_SWITCHES.items()},
    }}


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
    return _put_setting("/user/device/manage/targetSoc", body, confirm)


AIR_DURATIONS = (5, 10, 15)    # the only choices the app's picker offers (capture 2026-10-22)


def set_air_duration(minutes, confirm=False):
    """Set the Smart A/C run time (the app's "Reservation Duration"), in minutes.
    Body captured from the app 2026-10-22: `PUT /user/device/manage/airDuration`
    `{"duration": 15, "vehicleId": "<vehicle id>"}` -- field is `duration`, vehicleId a string,
    no deviceSn. The current value comes back as `airDuration` on `GET /user/vehicle`
    (surfaced by server.control_caps)."""
    minutes = int(minutes)
    if minutes not in AIR_DURATIONS:
        return {"ok": False, "error": "duration must be one of %s minutes" % (AIR_DURATIONS,)}
    vid, _ = _ids()
    return _put_setting("/user/device/manage/airDuration",
                        {"duration": minutes, "vehicleId": vid}, confirm)


def _set_notice_item(config_name, enabled, extra, confirm):
    """Write ONE item of the vehicle's notice config -- `PUT .../terminalNoticeConfig`.
    The app writes one item per call (captured 2026-10-22); the old whole-object body
    got `1000 未知异常`. Works for sub-users even though the app hides the screen from
    them. `extra` is a JSON *string* ("" when the item has no settings)."""
    vid, _ = _ids()
    return _put_setting("/user/device/manage/terminalNoticeConfig",
                        {"configExtra": extra, "configName": config_name,
                         "configStatus": bool(enabled), "vehicleId": vid}, confirm)


# The app's only two alert switches (owner's Device -> Push setting), each covering several
# reminders. configName -> the field that reads it back on GET terminalNoticeConfig/{id}.
ALERT_SWITCHES = {
    "VEHICLE_ANOMALY": "enableVehicleAnomalyWarning",   # anti-theft, tyre, door open, lights, unlocked
    "BATTERY_ANOMALY": "enableBatteryAnomalyWarning",   # low battery, low battery voltage
}


def set_alert(config_name, enabled, confirm=False):
    """Turn one alert switch on/off. `config_name` is a key of ALERT_SWITCHES."""
    if config_name not in ALERT_SWITCHES:
        return {"ok": False, "error": "configName must be one of %s" % sorted(ALERT_SWITCHES)}
    return _set_notice_item(config_name, enabled, "", confirm)


def set_scheduled_travel(enabled, hour, minute, week=None, confirm=False):
    """Have the cabin ready by a departure time (the app's "Advance travel").
    It is the `STARTUP_APPOINTMENT` notice item, not its own endpoint. `week` is the
    repeat days as 7 bools (all false = one-time); hour and minute go out zero-padded
    as strings, exactly as the app sends them. Reads back as `startupAppointment` +
    `extra` on GET terminalNoticeConfig/{id}."""
    hour, minute = int(hour), int(minute)
    week = list(week) if week else [False] * 7
    if not (0 <= hour <= 23 and 0 <= minute <= 59) or len(week) != 7:
        return {"ok": False, "error": "need hour 0-23, minute 0-59 and 7 week flags"}
    extra = json.dumps({"hour": "%02d" % hour, "minute": "%02d" % minute,
                        "week": [bool(d) for d in week]}, separators=(",", ":"))
    return _set_notice_item("STARTUP_APPOINTMENT", enabled, extra, confirm)


def set_charge_schedule(enabled, hour=0, minute=0, duration=1, week=None,
                        confirm=False):
    """Set scheduled charging — `PUT /user/device/manage/batterySchedule`.

    Body shape captured from the app and verified live 2026-10-22 (the dashboard
    sent this exact shape to revert the account and got `0000`):
      `{vehicleId:int, enabled:bool, hour:0-23, minute:0-59, duration:<hours>,
        week:[7 bools]}`.
    `week` is the Sun..Sat repeat flags; all-false = one-time. `GET batterySchedule`
    answers 1003, but the current schedule reads back as the `batterySchedule` JSON
    string on the notice config -- see device_settings()."""
    vid, _ = _ids()
    body = {
        "vehicleId": int(vid),
        "enabled": bool(enabled),
        "hour": int(hour),
        "minute": int(minute),
        "duration": int(duration),
        "week": list(week) if week else [False] * 7,
    }
    return _put_setting("/user/device/manage/batterySchedule", body, confirm)
