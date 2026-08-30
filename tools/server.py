"""CarLinko dashboard server (stdlib only).
Serves the mobile PWA in ./web and a JSON API computed from carlinko.db.
Run: python server.py [port]   (default 8088, binds 0.0.0.0 so Tailscale can reach it)
"""
import os, sys, json, time, sqlite3, threading, math, calendar, urllib.request, urllib.parse
import hmac, hashlib, base64, secrets
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import known_cars          # per-model constants the telemetry never carries (pack size, tyre scale)

_poll_lock = threading.Lock()

def live_poll():
    """On-demand: poll the car's WebSocket right now and store the frame.
    Returns (ok, msg). Single-flight via lock so rapid taps don't stack WS connections."""
    if not _poll_lock.acquire(blocking=False):
        return False, "busy"
    try:
        import logger as L
        conn = sqlite3.connect(DB)
        try:
            st = L.poll_once(conn); conn.commit()
        finally:
            conn.close()
        return (st is not None), ("ok" if st else "car offline")
    except Exception as e:
        return False, repr(e)
    finally:
        _poll_lock.release()

HERE = os.path.dirname(os.path.abspath(__file__))
# Demo mode: serve a baked, realistic sample so anyone can click around the dashboard with no
# account, no car, no DB. Turn on with `python server.py --demo` or CARLINKO_DEMO=1.
DEMO = ("--demo" in sys.argv) or (os.environ.get("CARLINKO_DEMO", "").lower() in ("1", "true", "yes"))
_DATA = os.environ.get("CARLINKO_DATA") or HERE          # Docker data dir; else alongside the code
DB   = os.path.join(_DATA, "carlinko.db") if os.environ.get("CARLINKO_DATA") else os.path.join(HERE, "..", "carlinko.db")
WEB  = os.path.join(HERE, "..", "web")

def _creds():
    try:
        return json.load(open(os.path.join(_DATA, "creds.json")))
    except Exception:
        return {}

def _resync_skip():
    """Late cloud re-sync bursts (the odometer catches up after the car was dark) can't be dated to
    a day. Default "skip": keep them out of daily totals (accurate per-day numbers). "count" = old
    behaviour: add them to the day the car reconnected. Toggled from the dashboard Settings tab."""
    try:
        return str(json.load(open(os.path.join(_DATA, "creds.json"))).get("resync_km", "skip")).lower() != "count"
    except Exception:
        return True

def _ensure_db():
    """Create the telemetry table if missing so summary() never hits a fresh/empty DB."""
    try:
        import logger as L
        conn = sqlite3.connect(DB); conn.executescript(L.SCHEMA); conn.commit(); conn.close()
    except Exception:
        pass
# Vehicle identity (plate/model/VIN) comes from creds.json; the client hides plate+VIN by
# default (eye-toggle reveals). Falls back to generic labels so the app still runs unconfigured.
_V = (_creds().get("vehicle") or {})
VEHICLE = {"plate": _V.get("plate") or "—", "model": _V.get("model") or "EV", "vin": _V.get("vin") or "—"}
# CarLinko hosts a render of the exact car (model + colour) on its own CDN; setup.py saves the URL.
# We proxy it through /car-photo and cache it on disk rather than pointing the browser at the
# vendor's CDN -- keeps the dashboard self-hosted and offline-friendly, and leaks no referer.
VEHICLE_IMG = (_V.get("img") or "").strip() or None
_CAR_PHOTO = os.path.join(_DATA, "car-photo.img")
TPMS_POS = ["FL", "FR", "RL", "RR"]

def _vehicle_img():
    """The car's own CarLinko render URL, read fresh so a web login or photo refresh takes
    effect without a restart."""
    return ((_creds().get("vehicle") or {}).get("img") or "").strip() or None

def _car_image():
    """Hero image for /api/summary: the owner's override wins, then the server-cached proxy of
    CarLinko's own render, else None (client falls back to the bundled J5 render / silhouette)."""
    c = _creds()
    override = (c.get("car_image") or "").strip()
    return override or ("/car-photo" if (c.get("vehicle") or {}).get("img") else None)

def _vehicle_img_url(v):
    """CarLinko hosts a render of the exact car (model + colour): the /user/vehicle object
    carries vehicleImgConfig {Front, Side, Top, ...}. Prefer the front view."""
    try:
        img = json.loads(v.get("vehicleImgConfig") or "{}")
        return img.get("Front") or img.get("Side") or img.get("Top")
    except Exception:
        return None

def is_configured():
    """True once an account is set up — used to decide whether to show the login page."""
    if DEMO:
        return True                                        # demo: skip login, go straight to the dashboard
    c = _creds()
    return bool(c.get("email") and c.get("password") and c.get("vehicle_id"))

def web_login(email, password, region="sea", gmaps_key=None, dashboard_password=None):
    """Run the same flow as setup.py from a browser POST: log in, auto-detect the car, persist."""
    c = _creds()
    c["email"] = email.strip(); c["password"] = password; c["region"] = (region or "sea").strip() or "sea"
    if gmaps_key and gmaps_key.strip():
        c["gmaps_key"] = gmaps_key.strip()
    cpath = os.path.join(_DATA, "creds.json")
    json.dump(c, open(cpath, "w"), indent=2)
    try: os.chmod(cpath, 0o600)
    except Exception: pass
    import auth, requests
    auth._C = auth.cfg()
    token = auth.login()                                   # writes token.txt; raises on bad creds
    data = requests.get(auth.api_base() + "/user/vehicle",
                        headers=auth.headers_for({}, token=token), timeout=20).json().get("data")
    v = data[0] if isinstance(data, list) and data else (data if isinstance(data, dict) else {})
    if v.get("vehicleId"):
        c["vehicle_id"] = str(v["vehicleId"]); c["device_sn"] = str(v.get("deviceId") or "")
        c["vehicle"] = {"plate": v.get("licenseNumber") or "—", "model": v.get("model") or "EV",
                        "vin": v.get("vin") or "—"}
        img = _vehicle_img_url(v)
        if img and img != _vehicle_img():
            c["vehicle"]["img"] = img                     # web login now captures the render too
            try: os.remove(_CAR_PHOTO)                    # (previously only CLI setup.py did)
            except Exception: pass                        # bust the old car's cached photo
        json.dump(c, open(cpath, "w"), indent=2)
        try: os.chmod(cpath, 0o600)
        except Exception: pass
        VEHICLE.update(c["vehicle"])                        # reflect immediately, no restart
    if dashboard_password and dashboard_password.strip():
        set_dashboard_password(dashboard_password.strip())  # gate the dashboard for public hosting
    _ensure_db()                                           # table exists before the dashboard first loads
    # grab a first frame in the background so login returns instantly even if the car is offline
    try: threading.Thread(target=live_poll, daemon=True).start()
    except Exception: pass
    return c.get("vehicle", {})

# ---- remote control: replaces the CarLinko app (AC / windows / sunroof / liftgate / lock / find) ----
# Reads the car's OWN vehicleControlConfig for the button set (generic per-car, not J5-hardcoded),
# and forges the same POST /user/vehicle/remoteControl the app sends. Results arrive over the WS.
_VEH_CACHE = {"t": 0.0, "v": None}

def _read_token():
    import auth
    try:
        t = open(auth.TOKEN_FILE).read().strip()
        if t:
            return t
    except Exception:
        pass
    return auth.login()

def _vehicle_raw(force=False):
    """First vehicle object from /user/vehicle (carries vehicleControlConfig + remoteControls).
    Cached ~1h -- the control-capability set is a per-model constant, not live telemetry."""
    import auth, requests
    if not force and _VEH_CACHE["v"] is not None and (time.time() - _VEH_CACHE["t"]) < 3600:
        return _VEH_CACHE["v"]
    def _fetch(t):
        return requests.get(auth.api_base() + "/user/vehicle",
                            headers=auth.headers_for({}, token=t), timeout=20).json()
    d = _fetch(_read_token())
    if str(d.get("code")) != "0000":
        d = _fetch(auth.login())
    data = d.get("data")
    v = (data[0] if isinstance(data, list) and data else data) if data else {}
    _VEH_CACHE["v"] = v or {}; _VEH_CACHE["t"] = time.time()
    return _VEH_CACHE["v"]

def control_caps():
    """What THIS car can be told to do, straight from CarLinko's vehicleControlConfig -- so the
    Control tab only renders buttons the car actually supports."""
    v = _vehicle_raw()
    cfg = v.get("vehicleControlConfig")
    if isinstance(cfg, str):
        try: cfg = json.loads(cfg)
        except Exception: cfg = {}
    cfg = cfg or {}
    ac = cfg.get("A/C") or {}
    return {
        "lock":     bool(cfg.get("Lock")),
        "windows":  {"open": bool(cfg.get("WindowsOpen")), "close": bool(cfg.get("WindowsClose")),
                     "vent": bool(cfg.get("WindowsVent"))},
        "sunroof":  {"open": bool(cfg.get("Sunroof")), "tilt": bool(cfg.get("SunroofTilting"))},
        "liftgate": bool(cfg.get("PowerLiftgate")),
        "trunk":    bool(cfg.get("Trunk")),
        "find":     bool(cfg.get("Search")),
        "charging": bool(cfg.get("ChargingManagement")),
        "ac": {"switch": bool(ac.get("Switch")), "temp": bool(ac.get("SetTemperature")),
               "min": ac.get("SetTemperatureMin"), "max": ac.get("SetTemperatureMax"),
               "step": ac.get("TemperatureStepValue"), "rapidCool": bool(ac.get("RapidCool")),
               "rapidHeat": bool(ac.get("RapidHeat")), "defog": bool(ac.get("Defogging"))},
        "plate": v.get("licenseNumber") or "",
    }

# opcodes we've actually seen the app POST (real, safe to replay). Labels unknown until the owner
# fires each on an awake car and notes the effect -- the Control tab's tester exists for exactly that.
KNOWN_OPCODES = [
    {"code": "2301", "note": "captured (returned 50043 while the car was asleep)"},
    {"code": "24",   "note": "captured"},
    {"code": "77",   "note": "captured"},
]

def send_control(opcode, timeout=20):
    """Forge the exact POST /user/vehicle/remoteControl the app sends. timeOut is signed as a
    NUMBER (not a string) to match the app's jsonEncode, else the server rejects the signature."""
    import auth, requests
    c = _creds()
    vid = str(c.get("vehicle_id") or getattr(auth, "VEHICLE_ID", "") or "")
    dsn = str(c.get("device_sn") or getattr(auth, "DEVICE_SN", "") or "")
    if not vid or not dsn:
        return {"code": "-1", "msg": "vehicle_id / device_sn missing from creds.json"}
    try: timeout = int(timeout)
    except Exception: timeout = 20
    body = {"vehicleId": vid, "deviceSn": dsn, "data": str(opcode), "timeOut": timeout}
    def _post(tok):
        ts = auth.now_ms()
        ordered = {k: v for k, v in sorted({**body, "timestamp": ts}.items())}
        msg = json.dumps(ordered, separators=(",", ":"), ensure_ascii=False).encode()
        sig = base64.b64encode(hmac.new(auth.SIGN_KEY, msg, hashlib.sha256).digest()).decode()
        h = {"timestamp": ts, "signature": sig, "user-agent": "Dart/3.10 (dart:io)",
             "content-type": "application/json", "language": "en", "token": tok}
        return requests.post(auth.api_base() + "/user/vehicle/remoteControl",
                             data=json.dumps(body, separators=(",", ":"), ensure_ascii=False),
                             headers=h, timeout=timeout + 8).json()
    d = _post(_read_token())
    # stale token -> relogin once. 9997 = 登录失效 (login expired), the one CarLinko actually returns.
    if str(d.get("code")) in ("9997", "40001", "40003", "401", "1001", "1002"):
        try: d = _post(auth.login())
        except Exception as e: d = {"code": "-1", "msg": f"relogin failed: {e}"}
    return d

# ---- optional dashboard auth (off by default; set a dashboard_password to gate public hosting) ----
SESSION_TTL = 30 * 86400

def _gated():
    return (not DEMO) and bool(_creds().get("dash_pw_hash"))   # demo is never gated

def _save_creds(c):
    cpath = os.path.join(_DATA, "creds.json")
    json.dump(c, open(cpath, "w"), indent=2)
    try: os.chmod(cpath, 0o600)
    except Exception: pass

def _session_secret():
    c = _creds()
    if not c.get("session_secret"):
        c["session_secret"] = secrets.token_hex(32); _save_creds(c)
    return c["session_secret"].encode()

def _hash_pw(pw, salt):
    return hashlib.sha256((salt + ":" + pw).encode()).hexdigest()

def set_dashboard_password(pw):
    c = _creds(); c["dash_salt"] = secrets.token_hex(8)
    c["dash_pw_hash"] = _hash_pw(pw, c["dash_salt"])
    c.setdefault("session_secret", secrets.token_hex(32)); _save_creds(c)

def check_dashboard_password(pw):
    c = _creds(); h, salt = c.get("dash_pw_hash"), c.get("dash_salt")
    return bool(h and salt) and hmac.compare_digest(h, _hash_pw(pw, salt))

def make_session():
    exp = str(int(time.time()) + SESSION_TTL)
    sig = hmac.new(_session_secret(), exp.encode(), hashlib.sha256).hexdigest()
    return base64.urlsafe_b64encode(f"{exp}.{sig}".encode()).decode()

def valid_session(tok):
    try:
        exp, sig = base64.urlsafe_b64decode((tok or "").encode()).decode().split(".", 1)
        if int(exp) < time.time(): return False
        good = hmac.new(_session_secret(), exp.encode(), hashlib.sha256).hexdigest()
        return hmac.compare_digest(sig, good)
    except Exception:
        return False

def _cookie_sid(cookie_header):
    for part in (cookie_header or "").split(";"):
        if part.strip().startswith("sid="):
            return part.strip()[4:]
    return ""

def _psi_raw(x):
    # raw tyre byte -> PSI, always (used for internal soft/hard thresholds regardless of display unit)
    return None if x == 0xFF else x * TPMS_SCALE * 0.145038
def pressure(x):
    # raw tyre byte -> value in the configured display unit (psi | bar | kpa)
    if x == 0xFF: return None
    kpa = x * TPMS_SCALE
    if TYRE_UNIT == "bar": return round(kpa / 100.0, 2)
    if TYRE_UNIT == "kpa": return round(kpa)
    return round(kpa * 0.145038, 1)
def temp(x): return None if x == 0xFF else round(x * 0.65 - 40, 1)

def decode(hexstr):
    """Decode the action:6 status blob. Validated offsets: battery, range, odometer."""
    b = bytes.fromhex(hexstr)
    d = {}
    if len(b) > 30:
        d["battery"]  = b[28]                              # validated =49
        d["range_km"] = int.from_bytes(b[29:31], "big")    # validated =248
        d["odometer"] = int.from_bytes(b[18:21], "big")    # validated =882 (0x0372)
        d["volt12"]   = round(int.from_bytes(b[12:14], "big") * 0.01, 2)  # 12V aux ~13.84 (validate on drive)
        d["unlocked"] = b[3] != 0                          # 0=locked, !=0=unlocked. VERIFIED: live lock/unlock
        # test on the Omoda E5 (#5) + J5 data (217 park 0->1 flips; b3=1 lingers a median 105 s
        # after driving stops -- the walk-away-and-lock delay). NOT ignition, despite the old name;
        # it doubles as a "car is in use / awake" hint, which is all the logger needs it for.
        d["speed"] = round(int.from_bytes(b[14:16], "big") / 16.0, 1)  # km/h: bytes14-15 BE /16 (calibrated live: raw 320 = 20 km/h)
    if len(b) > 55:
        d["consumption"] = round(b[55] * 0.1, 1)           # car's own avg kWh/100km (byte55 x0.1; matches dash 12.2)
        # PHEV-only fields. Both bytes are 0 in all 13,018 logged J5 (BEV) frames, and on a Chery
        # Tiggo 8 PHEV they read exactly what its dash showed (58% tank, 0.80 L/100km) -- see #2.
        # Kept raw here; summary() decides whether this car has a fuel tank at all.
        d["fuel_pct"]   = b[21]                            # fuel tank %
        d["fuel_l_100"] = round(b[53] * 0.1, 1)            # fuel consumption L/100km
        # Charging block, decoded from issue #5 (Omoda E5, Uruguay) and verified against 72,507
        # logged J5 frames + Tiggo 8 / Tiggo 7 PHEV frames from #2/#3 -- see docs/api-map.md.
        d["charge_mode"] = b[56]                           # connector: 0=none, 1=AC, 16=DC fast
        d["charge_state"] = b[57]                          # 0=idle 1=charging 2=complete 3=canceled 4=hot 5=stop
        d["charge_remain"] = int.from_bytes(b[58:60], "big")  # minutes to done; CarLinko sentinels >= 0x3FE = invalid
        if d["charge_remain"] >= 0x3FE: d["charge_remain"] = None
        d["charge_power"] = round(int.from_bytes(b[62:64], "big") * 0.1, 1)  # instant power (x0.1 kW; 0 when idle)
        # NOTE: b62-63 is bidirectional -- the same pair carries regen power while braking
        # (issue #5, E5 owner). summary() only surfaces it as charge power when b57 == 1.
        # AC flag: 0 = off, !=0 = on. Live-verified by the E5 owner (#5): a manual A/C toggle moved
        # exactly this byte and nothing else (fan/temp/seat/defrost changes left it alone).
        d["ac_on"] = b[23] != 0
        # Body-state bytes decoded by the Omoda E5 owner in #5 (live-verified on his car; not yet
        # cross-checked on the J5, so they are surfaced raw and labelled as such where shown).
        d["doors"] = b[2]                                   # door bitmask (E5, #5): 1=driver,
                                                            # 2=passenger, 4=rear-driver, 8=rear-passenger
        d["trunk_open"] = bool(b[4])                        # 0 = closed
        d["windows"] = b[8]                                 # 2 bits per window: closed/open bits,
                                                            # both clear = partial (E5, #5)
        d["sunroof_open"] = bool(b[9])                      # 0 = fully closed (E5, #5)
        d["ac_temp_c"] = b[24] if b[24] else None           # A/C target temp, raw degC (E5, #5);
                                                            # the J5 reads 159-169 here -> model-specific
        d["seat_heat"] = [b[32], b[33]]                     # L, R (0 = off)
        d["seat_vent"] = [b[37], b[38]]                     # L, R (0 = off)
        d["defrost_front"] = bool(b[42])
        # Rated (WLTC) range, NOT a mirror of EV range (b29-30). On the J5 they differ in 72,482 of
        # 72,507 frames (334 vs 302 at 66% -- 302/0.66 = 457.6, the car's 461 km NEDC rating).
        # The Omoda E5 owner in #5 cross-checked it live against the app: 304 vs 329, digit-for-digit.
        # On the Tiggo 8 PHEV they happen to coincide (its EV range IS the rated estimate).
        d["wltc_range_km"] = int.from_bytes(b[68:70], "big")
        # HV/motor state per #5 (>=2 = on). The E5 owner's live data: 0=off while parked, 2=ready
        # in 100% of driving samples, 1 as a 15-90s transition at power on/off -- i.e.
        # 0=off, 1=low-voltage active, 2=high-voltage/ready. On the J5 the byte also takes 0-3
        # without tracking ignition (2 dominates even parked), so it stays raw + model-specific.
        d["hv_state"] = b[5]
    if len(b) > 71:
        # The car's own headline range: EV range on a BEV, *fuel* range on a PHEV. Proven on the
        # Tiggo 8 PHEV over three frames (#2): it held 652 while EV range fell 90 -> 81 (so it is
        # not EV range), then dropped to 649 as the tank went 58% -> 56% (so it does track fuel).
        # On the J5 it mirrors range_km in every logged frame, so summary() only surfaces it as a
        # fuel range once the car is known to have a tank.
        d["headline_range_km"] = int.from_bytes(b[70:72], "big")
    d["tyre"] = b[44:52] if len(b) >= 52 else None         # 4 psi + 4 temp, FF=parked
    return d

_CC = _creds()          # per-model overrides; anything not set falls back to known_cars.CARS

def match_model(table, model=None):
    """Value from `table` for this car. `model` is passed explicitly by demo mode, which has its
    own car rather than the one in creds.json."""
    return known_cars.match(table, model if model is not None else VEHICLE.get("model"))

KNOWN = match_model(known_cars.CARS) or {}

# creds.json  >  a car we know  >  the J5's number, which on any other car is a guess and is
# labelled as one all the way out to the UI (battery_kwh_source) rather than stated as fact.
CAP_KWH = float(_CC.get("battery_kwh") or KNOWN.get("battery_kwh") or 58.9)
CAP_SOURCE = ("creds" if _CC.get("battery_kwh") else
              "known" if KNOWN.get("battery_kwh") else "guess")
WLTP_KWH_100 = float(_CC.get("wltp_kwh_100") or KNOWN.get("wltp_kwh_100") or 14.8)  # "optimal" baseline
WLTP_KNOWN = bool(_CC.get("wltp_kwh_100") or KNOWN.get("wltp_kwh_100"))
TARIFF_IDR_CFG = _CC.get("tariff_idr") or _CC.get("tariff")   # local all-in tariff/kWh override (optional)
# --- currency + tyre-unit (open to non-Indonesia cars; default to the J5/IDR values this was calibrated on) ---
_CUR       = _CC.get("currency") or {}
CUR_SYMBOL = _CUR.get("symbol") or "Rp"                # display symbol, e.g. "R" (ZAR), "$", "€"
CUR_LOCALE = _CUR.get("locale") or "id-ID"             # thousands grouping locale, e.g. "en-ZA"
CUR_CODE   = (_CUR.get("code") or "IDR").upper()
TYRE_UNIT  = (_CC.get("tyre_unit") or "psi").lower()   # tyre display unit: psi | bar | kpa
# raw tyre byte -> kPa. setup.py writes CarLinko's own appKpaFormula here; the table covers cars
# whose config doesn't publish one. 1.373 is the J5's, and needs recalibrating on any other car.
TPMS_SCALE = float(_CC.get("tpms_scale") or KNOWN.get("tpms_scale") or 1.373)
# --- pack chemistry: decides the 100%-charge advice (LFP wants one regularly, NMC does not) ---
CHEMISTRY = (_CC.get("chemistry") or KNOWN.get("chemistry") or "lfp").lower()   # lfp | nmc — J5 is LFP
CHEMISTRY_KNOWN = bool(_CC.get("chemistry") or KNOWN.get("chemistry"))
# Optional path/URL to a picture of YOUR car for the dashboard hero. The bundled render is a
# Jaecoo J5; showing it to an Omoda/Chery/Tiggo owner is just wrong, so anything we don't have
# a render for falls back to a neutral silhouette (see web/car-generic.svg) instead.
#   your own picture  >  CarLinko's render of your actual car  >  (client picks J5 or silhouette)
CAR_IMAGE = (_CC.get("car_image") or "").strip() or ("/car-photo" if VEHICLE_IMG else None)

# Brochure specs. These are per-model facts nothing in the telemetry can tell us, so they can only
# come from a table or from you. Showing the J5's numbers to a Tiggo owner is stating a falsehood,
# so an unknown model gets no spec card at all -- see issue #3.
MODEL_SPECS = {
    "jaecoo j5 ev": {
        "label": "Jaecoo J5 EV", "source": "Andalan Motors",
        "performance": [["Power", 210, "PS"], ["Torque", 288, "Nm"], ["0-100 km/h", 7.3, "s"],
                        ["DC 10-80%", 28, "min"], ["Battery", 60.9, "kWh"],
                        ["Range NEDC", 461, "km"], ["Drivetrain", "FWD", ""]],
        "dimensions": [["Length", 4380, "mm"], ["Width", 1860, "mm"], ["Height", 1650, "mm"],
                       ["Wheelbase", 2620, "mm"], ["Ground clearance", 200, "mm"]],
        "notes": ["gross_vs_usable", "nedc_optimistic"],
    },
}
_TIGGO7 = {
    "label": "Chery Tiggo 7 PHEV", "source": "owner-reported, issue #3",
    "performance": [["Power", 279, "PS"], ["Torque", 365, "Nm"], ["Battery", 18.3, "kWh"]],
    "dimensions": [["Length", 4553, "mm"]],
    "notes": ["owner_reported"],
}
# Malaysia badges the same car "TIGGO 7 CSH", so both keys share the entry.
MODEL_SPECS["tiggo 7 phev"] = _TIGGO7
MODEL_SPECS["tiggo 7 csh"] = _TIGGO7

def model_specs(model=None):
    """Specs for this car, or None. creds.json `specs` wins, so an owner can fill in a model we
    don't ship -- and nothing is shown if neither we nor they know."""
    if isinstance(_CC.get("specs"), dict):
        return _CC["specs"]
    return match_model(MODEL_SPECS, model)
# bev | phev | auto. "auto" calls it a PHEV once a frame reports a non-zero fuel tank or fuel
# consumption -- both are hard 0 on every BEV frame we've seen, so a BEV never trips it.
POWERTRAIN = (_CC.get("powertrain") or KNOWN.get("powertrain") or "auto").lower()
# LFP's discharge curve is nearly flat, so the BMS loses its SoC reference without a periodic
# 100% charge (it re-anchors + balances cells there). ~weekly is the common OEM line; NMC has no
# such need and prefers not to sit full, so don't nag those owners.
BALANCE_DAYS = float(_CC.get("full_charge_days") or (7 if CHEMISTRY == "lfp" else 90))
IDLE_GAP = 1800         # parked + no SoC rise for 30 min => charge session ended
CHARGE_PARK_MIN = 600   # a real charge sits odo-flat >=10 min; regen blips (odo coarse=1km) don't
MIN_GAIN_PCT = 2        # net SoC gain floor; drops 1% regen/noise that survives the park gate
_TARIFF = float(TARIFF_IDR_CFG or 2540)   # all-in DC tariff/kWh, in CUR_CODE (IDR default: Rp2.467 + 3% tax; service Rp0)
TARIFF_IDR = int(_TARIFF) if _TARIFF == int(_TARIFF) else _TARIFF  # keep cents for decimal currencies (e.g. ZAR 3.10)
CHG_EFF_AVG = 0.89      # blended DC charge efficiency for the per-km cost insight

def chg_eff(soc_end):
    """DC charge efficiency = stored SoC kWh / delivered (metered) kWh. Drops when topping to
    100% (current taper + cell balancing). Calibrated to receipts: end 80% -> 0.906,
    end 100% -> 0.855; linear between 85-95%."""
    if soc_end is None: return CHG_EFF_AVG
    if soc_end >= 95: return 0.855
    if soc_end <= 85: return 0.91
    return 0.91 + (0.855 - 0.91) * (soc_end - 85) / 10.0
TRIP_GAP = 180          # parked >3 min => a trip ends (merges short red-light stops)
MAX_PAIR_GAP = 1800     # >30 min between two logged frames = a hole in the log (service down, car
                        # offline, TBox asleep). The odo/SoC delta across a hole covers driving we
                        # never saw, so it can't be attributed to a day/week/trip -- skip the pair.
                        # Slow poll is 300 s, so this only ever trips on a genuine outage.
ODO_MAX_KMH = 160       # top speed a Jaecoo J5 can plausibly do (~150 km/h); anything faster is batching
ODO_RESYNC_KM = 12      # a frame pair advancing more than this is a late cloud re-sync, not live
                        # driving: the car went dark (basement, no signal) and the odometer syncs all
                        # the accumulated km in one burst when it reconnects. Those km were driven at
                        # some unknown earlier time, so they can't be dated to a day/trip -- skip the
                        # pair (the lifetime odo span still includes them). Real driving is ticked in
                        # ~1 km steps, so the largest genuine batch seen is ~11 km.
PETROL_KM_L = float(_CC.get("petrol_kml") or 12.0)        # comparable ICE fuel economy (km per litre)
PETROL_RP_L = float(_CC.get("petrol_price") or 16250)     # petrol price /litre in CUR_CODE
                                                          # (IDR default: Pertamax, Jawa/Bali, 1 Jul 2026)

def _m(x):
    # round money: whole units at IDR scale (>=100), keep 2 dp for sub-unit currencies (e.g. ZAR /km)
    return round(x) if abs(x) >= 100 else round(x, 2)

def build_trips(data, resync_skip=True):
    """A trip = a run of moving frames (odometer rising). Bridges brief stops; ends
    after TRIP_GAP parked. Returns newest-first with km / time / speed / kWh / efficiency.
    resync_skip=True skips implausible odo bursts as late cloud re-syncs (see ODO_RESYNC_KM);
    resync_skip=False counts them (old behaviour)."""
    fr = [(ts, d.get("battery"), d.get("odometer")) for ts, dt, d in data
          if d.get("battery") is not None and d.get("odometer") is not None]
    trips, cur, last_move = [], None, 0
    for i in range(1, len(fr)):
        ts0, b0, o0 = fr[i-1]; ts1, b1, o1 = fr[i]
        if ts1 - ts0 > MAX_PAIR_GAP:                   # hole in the log: the odo jump across it is
            if cur:                                    # days of unseen driving, not one long trip
                trips.append(cur); cur = None
            continue
        if o1 < o0:                                    # odometer went backwards = byte glitch ->
            if cur:                                    # trust break, close the trip
                trips.append(cur); cur = None
            continue
        if o1 > o0:                                    # moving (odometer rising = reliable)
            if resync_skip and (o1 - o0) > max(ODO_RESYNC_KM,  # a delta no real drive can cover
                    (ts1 - ts0) / 3600.0 * ODO_MAX_KMH):   # between two frames is a cloud catch-up
                if cur:                                # burst (car was dark; km belong to an earlier
                    trips.append(cur); cur = None      # unknown day) -> skip unless counting
                continue
            if cur is None:
                cur = {"start": ts0, "odo0": o0, "soc0": b0}
            cur.update(end=ts1, odo1=o1, soc1=b1); last_move = ts1
        elif cur and ts1 - last_move > TRIP_GAP:       # parked long enough -> close
            trips.append(cur); cur = None
    if cur: trips.append(cur)
    out = []
    for t in trips:
        dist = t["odo1"] - t["odo0"]
        if dist <= 0: continue
        dur_min = max((t["end"] - t["start"]) / 60.0, 0.1)
        avg = round(dist / (dur_min / 60.0)) if dur_min else None   # odo/time, reliable
        kwh = max(0.0, (t["soc0"] - t["soc1"]) / 100.0 * CAP_KWH)
        eff = round(kwh / dist * 100, 1) if kwh and dist >= 1 else None
        if eff is not None and not (5 <= eff <= 40):    # implausible (sparse-data merge, or a SoC drop
            eff = kwh = None                            # that resyncs with the odo) -> hide energy
        out.append({"start_ts": t["start"], "end_ts": t["end"],
                    "start_dt": time.strftime("%a %H:%M", time.localtime(t["start"])),
                    "km": dist, "min": round(dur_min), "avg_kmh": avg,
                    "kwh": round(kwh, 1) if kwh else None, "kwh100": eff})
    return out[::-1]                                    # newest first

def day_energy(data, resync_skip):
    """kWh used per day from EVERY SoC drop observed between consecutive frames, not just drops
    inside trips -- a drop often lands while parked (e.g. the BMS settles a minute after you
    arrive, like 43%->42% right after parking at the destination), and summing trip energy alone
    loses it. A drop counts when the car was moving on the pair or stopped within 15 min; drops
    that sync with a late re-sync burst, sit across a log hole, or happen long after the car last
    moved (parked drain) are excluded -- that energy isn't attributable to driving on that day.
    Returns {YYYY-MM-DD: kwh}."""
    frS = [(ts, d2.get("battery"), d2.get("odometer")) for ts, dt2, d2 in data
           if d2.get("battery") is not None]
    out = {}
    last_move = 0
    for i in range(1, len(frS)):
        t0, b0, o0 = frS[i-1]; t1, b1, o1 = frS[i]
        if t1 - t0 > MAX_PAIR_GAP:                     # hole in the log: what happened inside it
            last_move = 0                              # is unknown -> don't bridge drops across it
            continue
        if o0 is not None and o1 is not None and o1 > o0:
            if resync_skip and (o1 - o0) > max(ODO_RESYNC_KM, (t1 - t0) / 3600.0 * ODO_MAX_KMH):
                continue                               # re-sync burst: the SoC drop that synced with
            last_move = t1                             # it is earlier driving, not this day's
        if b0 is not None and b1 is not None and b0 > b1 and last_move and t1 - last_move <= 900:
            k = time.strftime("%Y-%m-%d", time.localtime(t1))
            out[k] = out.get(k, 0.0) + (b0 - b1) / 100.0 * CAP_KWH
    return out

def build_sessions(fr, now):
    """fr = [(ts, soc, odo)] sorted asc. A charge session = parked (odo flat) frames
    where SoC trends up. Robust to dense frames where most steps show 0% change."""
    raw, cur = [], None
    for i in range(len(fr)):
        ts, soc, odo = fr[i]
        gap = i > 0 and ts - fr[i-1][0] > MAX_PAIR_GAP  # hole in the log: kWh/rate/duration measured
        if gap and cur:                                # across it would be fiction -> close, don't span
            raw.append(cur); cur = None
        moved = i > 0 and odo > fr[i-1][2]
        if moved:                                      # car drove -> close any session
            if cur:
                if soc > cur["max"]:                   # charge peaked right before unplug/drive-off
                    cur["max"] = soc; cur["last_rise"] = ts; cur["pts"].append((ts, soc))
                raw.append(cur); cur = None
            continue
        if cur is None:                                # open when SoC rises vs prev parked frame
            if i > 0 and not gap and odo == fr[i-1][2] and soc > fr[i-1][1]:
                cur = {"start": fr[i-1][0], "soc0": fr[i-1][1], "last_rise": ts,
                       "max": soc, "pts": [(fr[i-1][0], fr[i-1][1]), (ts, soc)]}
        else:
            cur["pts"].append((ts, soc))
            if soc > cur["max"]:
                cur["max"] = soc; cur["last_rise"] = ts
            elif soc < cur["max"] - 1:                 # clear drop -> session ended earlier
                raw.append(cur); cur = None; continue
            if ts - cur["last_rise"] > IDLE_GAP:       # long flat -> unplugged/done
                raw.append(cur); cur = None
    if cur: raw.append(cur)
    moves = [fr[k][0] for k in range(1, len(fr)) if fr[k][2] > fr[k-1][2]]  # ts where odo ticked
    out = []
    for s in raw:
        soc0, soc1, pts = s["soc0"], s["max"], s["pts"]
        # Reject regen "charges": SoC can rise 1-2% on a descent while the (1 km-coarse)
        # odometer looks flat. A genuine charge keeps the car odo-flat for many minutes;
        # a regen blip sits inside a sub-km flat run bracketed by odo ticks. Gate on how
        # long the car was actually stationary around the rise.
        nxt = next((m for m in moves if m > s["last_rise"]), None)
        right = nxt if nxt is not None else now                      # ongoing -> up to now
        prev = [m for m in moves if m <= s["start"]]
        left = prev[-1] if prev else fr[0][0]
        if (right - left) < CHARGE_PARK_MIN or (soc1 - soc0) < MIN_GAIN_PCT:
            continue                                                 # regen / noise, not a charge
        kwh = max(0.0, (soc1 - soc0) / 100.0 * CAP_KWH)
        dur_h = max((s["last_rise"] - s["start"]) / 3600.0, 1e-6)
        peak, j = 0.0, 0                               # peak kW over >=3 min windows (1% steps are coarse)
        for k in range(1, len(pts)):
            dtp, dsc = pts[k][0] - pts[j][0], pts[k][1] - pts[j][1]
            if dtp >= 180 and dsc > 0:
                r = dsc / 100.0 * CAP_KWH / (dtp / 3600.0)
                if peak < r < 200: peak = r
                j = k
            elif pts[k][1] < pts[j][1]:
                j = k
        ongoing = (now - s["last_rise"] < IDLE_GAP) and pts[-1][0] == fr[-1][0]
        out.append({"start": s["start"], "end": s["last_rise"], "soc0": soc0, "soc1": soc1,
                    "kwh": kwh, "dur_h": dur_h, "avg": kwh / dur_h, "peak": peak,
                    "pts": pts, "ongoing": ongoing})
    return out

def live_rate(pts):
    """Charging speed over the last 15 min of the session (kW)."""
    ref = pts[-1][0]; w = [p for p in pts if p[0] >= ref - 900]
    if len(w) >= 2 and w[-1][0] > w[0][0] and w[-1][1] > w[0][1]:
        return (w[-1][1] - w[0][1]) / 100.0 * CAP_KWH / ((w[-1][0] - w[0][0]) / 3600.0)
    return None

def session_detail(s):
    pts = s["pts"]; t0 = pts[0][0]; n = len(pts); step = max(1, n // 48)
    series = [{"m": round((t - t0) / 60, 1), "soc": soc}
              for idx, (t, soc) in enumerate(pts) if idx % step == 0 or idx == n - 1]
    return {"ongoing": s["ongoing"],
            "start_dt": time.strftime("%H:%M", time.localtime(s["start"])),
            "dur_min": round((s["end"] - s["start"]) / 60), "kwh": round(s["kwh"], 2),
            "soc0": s["soc0"], "soc1": s["soc1"], "avg_kw": round(s["avg"], 1),
            "peak_kw": round(s["peak"], 1) if s["peak"] else None,
            "kwh_billed": round(s["kwh"] / chg_eff(s["soc1"]), 1),  # metered (what you pay for)
            "cost": round(s["kwh"] / chg_eff(s["soc1"]) * TARIFF_IDR), "series": series}

def analyze(data, trips, kwh_day):
    """Energy/efficiency from SoC%+odometer; charging sessions from parked SoC-rise.
    Today/this-week km come from build_trips(), each trip bucketed by the day it STARTED -- a
    drive that crosses midnight stays one trip on the day it began. Energy comes from
    day_energy() (every observed SoC drop, parked drops included), so "used today" matches the
    battery you actually consumed rather than only the drops that landed inside trip frames."""
    out = {
        "battery_kwh": CAP_KWH, "top_speed_today": 0,
        "energy": {"today_kwh": 0.0, "consumption": None, "rating": None, "week_consumption": None},
        "charging": {"active": False, "session_kwh": 0.0, "rate_kw": None, "soc": None,
                     "week": 0, "month": 0, "week_kwh": 0.0, "month_kwh": 0.0, "session": None},
    }
    today = time.strftime("%Y-%m-%d"); week = time.strftime("%Y-W%W"); month = time.strftime("%Y-%m")
    fr = [(ts, d.get("battery"), d.get("odometer")) for ts, dt, d in data
          if d.get("battery") is not None and d.get("odometer") is not None]
    km_today = km_week = 0.0
    for t in trips:                                    # trip-start bucketing (see build_trips)
        if time.strftime("%Y-%m-%d", time.localtime(t["start_ts"])) == today:
            km_today += t["km"]
        if time.strftime("%Y-W%W", time.localtime(t["start_ts"])) == week:
            km_week += t["km"]
    used_today = kwh_day.get(today, 0.0)
    used_week = sum(v for k, v in kwh_day.items()
                    if time.strftime("%Y-W%W", time.strptime(k, "%Y-%m-%d")) == week)
    now = time.time()
    sess = build_sessions(fr, now)
    for s in sess:
        if time.strftime("%Y-W%W", time.localtime(s["start"])) == week:
            out["charging"]["week"] += 1; out["charging"]["week_kwh"] += s["kwh"]
        if time.strftime("%Y-%m", time.localtime(s["start"])) == month:
            out["charging"]["month"] += 1; out["charging"]["month_kwh"] += s["kwh"]
    out["charging"]["week_kwh"] = round(out["charging"]["week_kwh"], 1)
    out["charging"]["month_kwh"] = round(out["charging"]["month_kwh"], 1)
    out["charging"]["month_cost"] = round(sum(
        s["kwh"] / chg_eff(s["soc1"]) * TARIFF_IDR for s in sess
        if time.strftime("%Y-%m", time.localtime(s["start"])) == month))
    out["charging"]["history"] = [                     # recent finished/ongoing sessions, newest first
        {"dt": time.strftime("%d %b %H:%M", time.localtime(s["start"])),
         "kwh": round(s["kwh"], 1), "kwh_billed": round(s["kwh"] / chg_eff(s["soc1"]), 1),
         "dur_min": round((s["end"] - s["start"]) / 60),
         "avg_kw": round(s["avg"], 1), "soc0": s["soc0"], "soc1": s["soc1"],
         "cost": round(s["kwh"] / chg_eff(s["soc1"]) * TARIFF_IDR)}
        for s in sess[::-1][:6] if s["kwh"] > 0.3]
    total_dsoc = sum(max(0, s["soc1"] - s["soc0"]) for s in sess)
    out["health"] = {
        "usable_kwh": CAP_KWH,                          # design usable; verified vs receipts (no SoH byte exists)
        "cycles": round(total_dsoc / 100.0, 1),         # equivalent full cycles seen since logging
        "charged_kwh": round(sum(s["kwh"] / chg_eff(s["soc1"]) for s in sess), 1),  # delivered, lifetime-logged
        "avg_eff": round(sum(chg_eff(s["soc1"]) for s in sess) / len(sess) * 100) if sess else None,
        "sessions": len(sess)}
    out["lifetime"] = {                                # running totals since logging began
        "kwh_in": round(sum(s["kwh"] for s in sess), 1),                          # into the pack
        "kwh_billed": round(sum(s["kwh"] / chg_eff(s["soc1"]) for s in sess), 1), # metered (paid for)
        "cost": round(sum(s["kwh"] / chg_eff(s["soc1"]) * TARIFF_IDR for s in sess)),
        "km": (fr[-1][2] - fr[0][2]) if len(fr) >= 2 else 0,                      # odometer span
        "since": time.strftime("%d %b", time.localtime(fr[0][0])) if fr else None}
    # A 100% charge is what re-anchors an LFP BMS: the discharge curve is so flat that the gauge
    # drifts without one. Track the interval so the dashboard can say *when*, not just "overdue".
    full = [s for s in sess if s["soc1"] >= 100]
    since = (now - full[-1]["start"]) / 86400 if full else None
    due_in = round(BALANCE_DAYS - since, 1) if since is not None else None
    out["battery_care"] = {
        "chemistry": CHEMISTRY,
        "interval_days": BALANCE_DAYS,
        "last_full_dt": time.strftime("%d %b", time.localtime(full[-1]["start"])) if full else None,
        "days_since_full": round(since) if since is not None else None,
        "days_to_due": due_in,                          # negative = overdue by that many days
        "next_due_dt": (time.strftime("%d %b", time.localtime(full[-1]["start"] + BALANCE_DAYS * 86400))
                        if full else None),
        # three states, so "do it this week" reads differently from "you're well past due"
        "state": ("unknown" if not full else
                  "overdue" if since >= BALANCE_DAYS * 2 else
                  "due" if since >= BALANCE_DAYS else "ok"),
        "balance_due": (not full) or (since >= BALANCE_DAYS)}   # kept for older clients
    ongoing = [s for s in sess if s["ongoing"]]
    if ongoing:
        s = ongoing[-1]; lr = live_rate(s["pts"])
        out["charging"].update(active=True, session_kwh=round(s["kwh"], 2), soc=s["soc1"],
                               rate_kw=round(lr if lr is not None else s["avg"], 1))
    detail = ongoing[-1] if ongoing else (sess[-1] if sess else None)
    if detail:
        out["charging"]["session"] = session_detail(detail)
    trips_all = trips
    out["trips"] = trips_all[:8]
    # Overall average speed = total distance / total time, not the mean of per-trip averages
    # (one short burst trip would dominate -- a cloud catch-up of a few km in ~10 s reads as
    # 700+ km/h). Only trips that actually lasted a minute count; sub-minute "trips" are
    # batch catch-ups, not drives.
    long = [(t["km"], t["end_ts"] - t["start_ts"]) for t in trips_all
            if t["end_ts"] - t["start_ts"] >= 60]
    tot_km = sum(x[0] for x in long); tot_s = sum(x[1] for x in long)
    out["avg_speed"] = round(tot_km / (tot_s / 3600.0)) if (long and tot_s > 0) else None
    out["energy"]["today_kwh"] = round(used_today, 2)
    def rate(cons):
        if cons is None: return None
        return "optimal" if cons < WLTP_KWH_100 else ("normal" if cons < 18 else "boros")
    if km_today >= 2:
        c = used_today / km_today * 100; out["energy"]["consumption"] = round(c, 1)
        out["energy"]["rating"] = rate(c)
    if km_week >= 5:
        out["energy"]["week_consumption"] = round(used_week / km_week * 100, 1)
        if out["energy"]["rating"] is None:
            out["energy"]["rating"] = rate(out["energy"]["week_consumption"])
    return out

def parked_drain(data):
    """Detect SoC lost across an offline/parked gap (car dark in a basement). Needs only the
    before/after readings, so it works without signal while parked. Returns the most recent
    gap that was parked (odometer unchanged), >=2 h, with a SoC drop."""
    best = None
    for i in range(1, len(data)):
        ts0, _, d0 = data[i-1]; ts1, _, d1 = data[i]
        gap = ts1 - ts0
        if gap < 7200:                                 # only long gaps (>=2h) -> stable %/day
            continue
        o0, o1 = d0.get("odometer"), d1.get("odometer")
        s0, s1 = d0.get("battery"), d1.get("battery")
        if None in (o0, o1, s0, s1) or o1 != o0:       # moved during the gap = driving, not drain
            continue
        if s0 - s1 <= 0:
            continue
        hrs = gap / 3600.0
        best = {"pct": s0 - s1, "hours": round(hrs, 1), "per_day": round((s0 - s1) / hrs * 24, 1),
                "dt": time.strftime("%d %b", time.localtime(ts1))}   # loop ascending -> ends newest
    return best

def insights(out):
    """Actionable read-only insights from the data: running cost, charge forecast, real range."""
    ins = {}
    cons = (out["energy"].get("consumption") or out["energy"].get("week_consumption") or WLTP_KWH_100)
    ins["consumption"] = cons
    rpkm = cons * TARIFF_IDR / 100.0 / CHG_EFF_AVG      # cost/km incl charging loss (you pay delivered)
    ins["rp_per_km"] = _m(rpkm)
    hist = out.get("history") or []
    avg_daily = (sum(h["km"] for h in hist) / len(hist)) if hist else 0.0
    ins["avg_daily_km"] = round(avg_daily)
    ins["month_cost_est"] = round(avg_daily * 30 * rpkm)
    petrol_rpkm = PETROL_RP_L / PETROL_KM_L            # comparable ICE cost/km
    ins["save_per_km"] = _m(petrol_rpkm - rpkm)
    ins["month_save_est"] = round(avg_daily * 30 * (petrol_rpkm - rpkm))
    rng, batt = out.get("range_km"), out.get("battery")
    ins["days_to_charge"] = round(rng / avg_daily, 1) if (rng and avg_daily > 0.5) else None
    ins["rated_range"] = round(rng / batt * 100) if (rng and batt) else None   # car's full-charge estimate
    ins["real_range"] = round(CAP_KWH / cons * 100) if cons else None          # from your real consumption
    if ins["rated_range"] and ins["real_range"]:
        r = ins["real_range"] / ins["rated_range"]
        ins["range_verdict"] = "accurate" if 0.95 <= r <= 1.06 else ("optimistic" if r < 0.95 else "conservative")
    return ins

def demo_summary():
    """A self-consistent, fictional J5 payload for demo mode. No real account, car or DB —
    every number here is made up but plausible, so people can explore the UI before setting up.
    Timestamps are anchored to 'now' so today/this-week views look alive."""
    now = time.time()
    def cd(off): return time.strftime("%d %b %H:%M", time.localtime(now - off))
    def hm(off): return time.strftime("%a %H:%M", time.localtime(now - off))
    def day(i):  return time.strftime("%m-%d", time.localtime(now - i * 86400))
    cap = 58.9
    # 7-day km + efficiency trend (newest last, matching the real series shape)
    km7  = [0, 41, 18, 63, 0, 27, 52]
    eff7 = [None, 12.6, 13.4, 12.1, None, 14.0, 12.9]
    kwh7 = [0, 5.2, 2.4, 7.6, 0, 3.8, 6.7]
    history = [{"day": day(6 - i), "km": km7[i], "kwh": kwh7[i], "eff": eff7[i]} for i in range(7)]
    # charge-curve series (minutes, SoC) for the last session detail chart
    series = [{"m": round(i * 47 / 24, 1), "soc": round(18 + (88 - 18) * (i / 24))} for i in range(25)]
    chist = [
        {"dt": cd(7 * 3600),  "kwh": 41.2, "kwh_billed": 45.6, "dur_min": 47, "avg_kw": 52.6, "soc0": 18, "soc1": 88, "cost": 115800},
        {"dt": cd(2 * 86400), "kwh": 24.7, "kwh_billed": 27.1, "dur_min": 33, "avg_kw": 44.9, "soc0": 46, "soc1": 88, "cost": 68800},
        {"dt": cd(4 * 86400), "kwh": 49.4, "kwh_billed": 57.8, "dur_min": 58, "avg_kw": 51.1, "soc0": 16, "soc1": 100, "cost": 146800},
        {"dt": cd(6 * 86400), "kwh": 18.9, "kwh_billed": 20.7, "dur_min": 22, "avg_kw": 51.5, "soc0": 56, "soc1": 88, "cost": 52600},
    ]
    trips = [
        {"start_dt": hm(5 * 3600),  "km": 52, "min": 71, "avg_kmh": 44, "kwh": 6.7, "kwh100": 12.9},
        {"start_dt": hm(29 * 3600), "km": 27, "min": 41, "avg_kmh": 39, "kwh": 3.8, "kwh100": 14.0},
        {"start_dt": hm(54 * 3600), "km": 63, "min": 78, "avg_kmh": 48, "kwh": 7.6, "kwh100": 12.1},
        {"start_dt": hm(78 * 3600), "km": 18, "min": 33, "avg_kmh": 33, "kwh": 2.4, "kwh100": 13.4},
    ]
    out = {
        "demo": True,
        "vehicle": {"plate": "B 1234 DEMO", "model": "Jaecoo J5 EV", "vin": "DEMOVIN00000J5EV"},
        "online": True, "battery": 72, "range_km": 318, "odometer": 8421, "volt12": 13.6,
        "unlocked": False, "speed": None, "moving": False, "avg_speed": 41,
        "doors": 0, "trunk_open": False, "windows": 0, "sunroof_open": False,
        "ac_on": False, "ac_temp_c": None, "seat_heat": [0, 0], "seat_vent": [0, 0],
        "updated": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(now - 180)), "age_min": 3.0,
        "battery_kwh": cap, "battery_kwh_source": "known", "wltp_kwh_100": 14.8,
        "chemistry_known": True, "powertrain": "bev", "fuel": None,
            "currency": {"symbol": CUR_SYMBOL, "locale": CUR_LOCALE, "code": CUR_CODE},
            "tyre_unit": TYRE_UNIT, "tariff": TARIFF_IDR, "car_image": _car_image(),
        "specs": model_specs("Jaecoo J5 EV"),   # demo car, not whatever creds.json says
        "energy": {"today_kwh": 6.7, "consumption": 12.9, "rating": "normal",
                   "week_consumption": 13.0, "source": "car"},
        "charging": {"active": False, "session_kwh": 0.0, "rate_kw": None, "soc": None,
                     "week": 2, "month": 9, "week_kwh": 65.9, "month_kwh": 312.4, "month_cost": 921000,
                     "history": chist,
                     "session": {"ongoing": False, "start_dt": time.strftime("%H:%M", time.localtime(now - 7 * 3600)),
                                 "dur_min": 47, "kwh": 41.2, "soc0": 18, "soc1": 88, "avg_kw": 52.6,
                                 "peak_kw": 61.3, "kwh_billed": 45.6, "cost": 115800, "series": series}},
        "trips": trips,
        "tpms": [{"pos": p, "psi": None, "temp": None, "valid": False} for p in TPMS_POS],
        "tpms_updated": None, "tpms_age_min": None, "tpms_live": False, "tpms_raw": None,
        "tyre_status": "Normal", "tyre_indirect": True,
        "km": {"today": 52, "week": 201, "month": 1043},
        "charges": {"week": 2, "month": 9},
        "history": history, "resync_km": "skip",
        "health": {"usable_kwh": cap, "cycles": 31.4, "charged_kwh": 1612.0, "avg_eff": 89, "sessions": 38},
        "lifetime": {"kwh_in": 1448.0, "kwh_billed": 1612.0, "cost": 4090000, "km": 8127,
                     "since": time.strftime("%d %b", time.localtime(now - 96 * 86400)),
                     "saved": 7240000, "liters_saved": 677.3, "co2_saved": 1564},
        "battery_care": {"chemistry": CHEMISTRY, "interval_days": BALANCE_DAYS,
                         "last_full_dt": time.strftime("%d %b", time.localtime(now - 4 * 86400)),
                         "days_since_full": 4, "days_to_due": round(BALANCE_DAYS - 4, 1),
                         "next_due_dt": time.strftime("%d %b", time.localtime(now + (BALANCE_DAYS - 4) * 86400)),
                         "state": "ok", "balance_due": False},
        "drain": None, "volt12_min7d": 12.7, "volt12_status": "ok",
        "insights": {}, "moving": False,
    }
    out["insights"] = insights(out)
    lf = out["lifetime"]
    lf["saved"] = max(0, round(lf["km"] * (PETROL_RP_L / PETROL_KM_L - out["insights"].get("rp_per_km", 0))))
    return out

def summary():
    if DEMO:
        return demo_summary()
    out = {"vehicle": VEHICLE, "online": False, "battery": None, "range_km": None,
           "odometer": None, "volt12": None, "unlocked": None, "speed": None,
           "moving": False, "avg_speed": None, "insights": {}, "health": {}, "drain": None,
           "volt12_min7d": None, "volt12_status": None,
           "updated": None, "age_min": None,
           "battery_kwh": CAP_KWH, "battery_kwh_source": CAP_SOURCE,
           "wltp_kwh_100": WLTP_KWH_100 if WLTP_KNOWN else None,
           "chemistry_known": CHEMISTRY_KNOWN, "powertrain": "bev", "fuel": None,
           "currency": {"symbol": CUR_SYMBOL, "locale": CUR_LOCALE, "code": CUR_CODE},
           "tyre_unit": TYRE_UNIT, "tariff": TARIFF_IDR, "car_image": CAR_IMAGE,
           "specs": model_specs(),
           "energy": {"today_kwh": 0.0, "consumption": None, "rating": None,
                      "week_consumption": None},
           "charging": {"active": False, "session_kwh": 0.0, "rate_kw": None, "soc": None,
                        "week": 0, "month": 0, "week_kwh": 0.0, "month_kwh": 0.0,
                        "month_cost": 0, "history": [], "session": None},
           "trips": [],
           "tpms": [{"pos": p, "psi": None, "temp": None, "valid": False} for p in TPMS_POS],
           "tpms_updated": None, "tpms_age_min": None, "tpms_live": False, "tpms_raw": None,
           "tyre_status": "Normal", "tyre_indirect": True,
            "km": {"today": None, "week": None, "month": None},
            "charges": {"week": None, "month": None},
            "history": [], "resync_km": "skip"}
    if not os.path.exists(DB):
        return out
    conn = sqlite3.connect(DB)
    rows = conn.execute(
        "SELECT ts,dt,online,raw FROM telemetry ORDER BY ts").fetchall()
    # decode authoritatively from the stored raw blob (offset fixes apply to all history)
    data = []
    for ts, dt, online, raw in rows:
        if online != 1 or not raw:
            continue
        data.append((ts, dt, decode(raw)))
    if not data:
        return out
    ts, dt, dec = data[-1]
    out.update(battery=dec.get("battery"), range_km=dec.get("range_km"),
               odometer=dec.get("odometer"), volt12=dec.get("volt12"),
               unlocked=dec.get("unlocked"), speed=None, updated=dt,
               # body-state bytes, decoded since #5 — pass-through for the V  2 status surfaces
               doors=dec.get("doors"), trunk_open=dec.get("trunk_open"),
               windows=dec.get("windows"), sunroof_open=dec.get("sunroof_open"),
               ac_on=dec.get("ac_on"), ac_temp_c=dec.get("ac_temp_c"),
               seat_heat=dec.get("seat_heat"), seat_vent=dec.get("seat_vent"))
    out["age_min"] = round((time.time() - ts) / 60, 1)
    out["online"] = out["age_min"] is not None and out["age_min"] < 40
    # Fuel side of a PHEV. Decided over the whole window, not the latest frame, so a car sitting at
    # an empty tank still counts as a PHEV. A BEV reports 0 for both bytes forever and stays "bev",
    # which keeps the fuel UI off every existing install.
    phev = POWERTRAIN == "phev" or (POWERTRAIN == "auto" and
           any(d2.get("fuel_pct") or d2.get("fuel_l_100") for _t, _d, d2 in data))
    out["powertrain"] = "phev" if phev else "bev"
    if phev:
        fr, ev = dec.get("headline_range_km"), out.get("range_km")
        out["fuel"] = {"pct": dec.get("fuel_pct"), "l_100": dec.get("fuel_l_100"), "range_km": fr,
                       # The combined figure is not transmitted: the app's own total is exactly
                       # EV + fuel on every capture (742 = 90 + 652, 687 = 38 + 649), so we compute
                       # it and the UI labels it as computed rather than read from the car.
                       "total_range_km": (ev + fr) if (ev is not None and fr is not None) else None}
    # reliable "moving now": latest odometer rose vs the prior fresh frame (speed byte is garbage)
    if len(data) >= 2:
        (tsa, _, da), (tsb, _, db) = data[-2], data[-1]
        oa, ob = da.get("odometer"), db.get("odometer")
        if oa is not None and ob is not None and (time.time() - tsb) < 120 and (tsb - tsa) < 120:
            out["moving"] = ob > oa
    # tyres: hold the last frame that carried a real (non-FF) reading ("last known good").
    # Sensors sleep when parked -> FF; keep showing the last live values + an as-of stamp.
    for ts2, dt2, dec2 in reversed(data):
        tb = dec2.get("tyre")
        if tb and any(x != 0xFF for x in tb):
            # "psi" holds the value in the configured display unit; status logic below normalises to PSI
            out["tpms"] = [{"pos": TPMS_POS[i], "psi": pressure(tb[i]), "temp": temp(tb[4 + i]),
                            "valid": tb[i] != 0xFF} for i in range(4)]
            out["tpms_updated"] = dt2
            out["tpms_age_min"] = round((time.time() - ts2) / 60, 1)
            out["tpms_live"] = (ts2 == ts)  # newest frame still has live tyres
            # the undecoded bytes, so you can calibrate tpms_scale on a car that has real (direct)
            # TPMS: read one wheel off the car's own screen, then tpms_scale = your_kPa / raw_byte.
            out["tpms_raw"] = [tb[i] for i in range(4)]
            raw_psi = [p for p in (_psi_raw(tb[i]) for i in range(4)) if p is not None]
            if raw_psi:  # real per-wheel pressure present (J5: indirect TPMS, bytes stay FF; some cars send it)
                out["tyre_indirect"] = False
                out["tyre_status"] = "Check tyres" if any(p < 28 or p > 40 for p in raw_psi) else "Normal"
            break

    # Daily distance comes from trips, each bucketed by the day it STARTED: a drive that crosses
    # midnight (23:45 -> 00:30) stays one trip on the day it began, so "today" only ever shows
    # trips that began today -- last night's drive reads under yesterday, not split across two.
    # Daily energy comes from day_energy(): every observed SoC drop, not just in-trip drops.
    resync_skip = _resync_skip()
    out["resync_km"] = "skip" if resync_skip else "count"
    trips_all = build_trips(data, resync_skip)
    kwh_day = day_energy(data, resync_skip)
    km_day = {}
    for t in trips_all:
        k = time.strftime("%Y-%m-%d", time.localtime(t["start_ts"]))
        km_day[k] = km_day.get(k, 0) + t["km"]
    today = time.strftime("%Y-%m-%d")
    week  = time.strftime("%Y-W%W")
    month = time.strftime("%Y-%m")
    out["km"]["today"] = km_day.get(today, 0)
    out["km"]["week"]  = sum(t["km"] for t in trips_all
                             if time.strftime("%Y-W%W", time.localtime(t["start_ts"])) == week)
    out["km"]["month"] = sum(t["km"] for t in trips_all
                             if time.strftime("%Y-%m", time.localtime(t["start_ts"])) == month)
    # last 7 days km + efficiency series (same trip-start buckets as km.today)
    series = []
    for i in range(6, -1, -1):
        day = time.strftime("%Y-%m-%d", time.localtime(time.time() - i * 86400))
        km = km_day.get(day, 0)
        u = kwh_day.get(day, 0.0)
        eff = round(u / km * 100, 1) if (km >= 1 and u > 0) else None
        if eff is not None and not (9 <= eff <= 30):   # 1%-coarse SoC over short trips lies; hide it
            eff = None
        series.append({"day": day[5:], "km": km, "kwh": round(u, 1), "eff": eff})
    out["history"] = series
    res = analyze(data, trips_all, kwh_day)
    out["battery_kwh"] = res["battery_kwh"]
    out["energy"] = res["energy"]
    # prefer the car's own BMS consumption (byte55) over the coarse SoC-derived estimate.
    # byte55 only reports while driving; when parked it reads 0, so reuse the last driving value
    # rather than flip to the noisy 1%-SoC estimate (which lags mid-drive, e.g. shows 10 vs 12).
    rc = dec.get("consumption")
    if not rc:
        for _t, _d, _dc in reversed(data):
            if _dc.get("consumption"):
                rc = _dc.get("consumption"); break
    if rc:
        out["energy"]["consumption"] = rc
        out["energy"]["rating"] = ("optimal" if rc < WLTP_KWH_100 else "normal" if rc < 18 else "boros")
        out["energy"]["source"] = "car"
    out["charging"] = res["charging"]
    # Prefer the car's own charging flags over the SoC-derived session detector: b56/b57/b62-63
    # report connector, state and instant power directly (verified on J5 DC + Tiggo 8 AC frames,
    # issue #5). The car flips to "active" the moment the charger starts, before any SoC tick.
    cmode = dec.get("charge_mode"); cstate = dec.get("charge_state")
    out["charging"]["mode"] = {16: "dc", 1: "ac"}.get(cmode)
    out["charging"]["state"] = cstate
    out["charging"]["remaining_min"] = dec.get("charge_remain")
    if cstate == 1 and dec.get("charge_power") is not None:
        out["charging"]["active"] = True
        out["charging"]["rate_kw"] = dec["charge_power"]
        out["charging"]["rate_source"] = "car"
    elif out["charging"]["active"]:
        out["charging"]["rate_source"] = "soc-estimate"
    out["wltc_range_km"] = dec.get("wltc_range_km")
    out["trips"] = res.get("trips", [])
    out["avg_speed"] = res.get("avg_speed")
    out["health"] = res.get("health", {})
    out["lifetime"] = res.get("lifetime", {})
    out["battery_care"] = res.get("battery_care", {})
    out["drain"] = parked_drain(data)                  # SoC lost across offline/parked gaps
    # 12V battery watch (directly measured): 7-day min + status (readings are DC-DC-supported while awake)
    v7 = [d2.get("volt12") for ts2, dt2, d2 in data if d2.get("volt12") and time.time() - ts2 <= 7 * 86400]
    if v7:
        mn = min(v7)
        out["volt12_min7d"] = round(mn, 2)
        out["volt12_status"] = "critical" if mn < 12.0 else ("low" if mn < 12.5 else "ok")
    out["insights"] = insights(out)
    lf = out.get("lifetime") or {}                     # saved-vs-petrol over distance actually driven
    rpkm_l = out["insights"].get("rp_per_km")
    if lf.get("km"):
        if rpkm_l is not None:
            lf["saved"] = max(0, round(lf["km"] * (PETROL_RP_L / PETROL_KM_L - rpkm_l)))
        lf["liters_saved"] = round(lf["km"] / PETROL_KM_L, 1)        # petrol you didn't burn
        lf["co2_saved"] = round(lf["km"] / PETROL_KM_L * 2.31)       # ~2.31 kg CO2 per litre petrol
    out["charges"] = {"week": res["charging"]["week"], "month": res["charging"]["month"]}
    return out

def month_history(month):
    """Per-day km / kWh / charging for one calendar month -- the dashboard's calendar view.
    month = 'YYYY-MM' (defaults to the current month). Same buckets as summary(): km by trip
    start, energy from day_energy(), charging from build_sessions()."""
    try:
        y, m = (int(x) for x in (month or "").split("-")[:2])
        if not (1 <= m <= 12):
            raise ValueError
    except Exception:
        now = time.localtime(); y, m = now.tm_year, now.tm_mon
    t0 = int(time.mktime(time.struct_time((y, m, 1, 0, 0, 0, 0, 0, -1))))
    ny, nm = (y, m + 1) if m < 12 else (y + 1, 1)
    t1 = int(time.mktime(time.struct_time((ny, nm, 1, 0, 0, 0, 0, 0, -1))))
    ndays = calendar.monthrange(y, m)[1]
    empty = {"month": f"{y:04d}-{m:02d}", "days": [],
             "totals": {"km": 0, "kwh": 0.0, "chg_kwh": 0.0, "chg_cost": 0},
             "resync_km": "skip"}
    if not os.path.exists(DB):
        return empty
    conn = sqlite3.connect(DB)
    rows = conn.execute(
        "SELECT ts,dt,online,raw FROM telemetry WHERE ts >= ? AND ts < ? ORDER BY ts",
        (t0, t1)).fetchall()
    data = []
    for ts, dt, online, raw in rows:
        if online != 1 or not raw:
            continue
        data.append((ts, dt, decode(raw)))
    if not data:
        return empty
    resync_skip = _resync_skip()
    trips = build_trips(data, resync_skip)
    kwh_day = day_energy(data, resync_skip)
    km_day = {}
    for t in trips:
        k = time.strftime("%Y-%m-%d", time.localtime(t["start_ts"]))
        km_day[k] = km_day.get(k, 0) + t["km"]
    fr = [(ts, d2.get("battery"), d2.get("odometer")) for ts, dt2, d2 in data
          if d2.get("battery") is not None and d2.get("odometer") is not None]
    sess = build_sessions(fr, t1)
    chg = {}                                            # day -> aggregated charging (in + metered cost)
    for s in sess:
        k = time.strftime("%Y-%m-%d", time.localtime(s["start"]))
        d = chg.setdefault(k, {"kwh": 0.0, "cost": 0, "n": 0})
        d["kwh"] += s["kwh"]
        d["cost"] += s["kwh"] / chg_eff(s["soc1"]) * TARIFF_IDR
        d["n"] += 1
    days = []
    for day in range(1, ndays + 1):
        k = f"{y:04d}-{m:02d}-{day:02d}"
        km = km_day.get(k, 0); u = kwh_day.get(k, 0.0)
        eff = round(u / km * 100, 1) if (km >= 1 and u > 0) else None
        if eff is not None and not (9 <= eff <= 30):    # same gate as the 7-day history
            eff = None
        c = chg.get(k)
        days.append({"d": day, "km": km, "kwh": round(u, 1), "eff": eff,
                     "chg_kwh": round(c["kwh"], 1) if c else 0,
                     "chg_cost": round(c["cost"]) if c else 0})
    return {"month": f"{y:04d}-{m:02d}", "days": days,
            "totals": {"km": sum(x["km"] for x in days),
                       "kwh": round(sum(x["kwh"] for x in days), 1),
                       "chg_kwh": round(sum(x["chg_kwh"] for x in days), 1),
                       "chg_cost": round(sum(x["chg_cost"] for x in days))},
            "resync_km": "skip" if resync_skip else "count"}

# ---- long-trip planner: geocode (Nominatim) + route (OSRM) + SPKLU (Overpass/OSM), all keyless ----
_UA_TRIP = "carlinko-trip/1.0 (personal EV dashboard)"
CHG_KW_AVG = 55           # fallback DC power when a station's kW is unknown (incl taper)
CAR_DC_CAP = 68           # J5 real-world DC ceiling: 49.5 kWh in 43.5 min ≈ 68 kW avg (CCS2)
_trip_cache = {}          # tiny cache so we're polite to the free public services
_CONN_LABEL = {"EV_CONNECTOR_TYPE_CCS_COMBO_2": "CCS2", "EV_CONNECTOR_TYPE_CCS_COMBO_1": "CCS1",
               "EV_CONNECTOR_TYPE_CHADEMO": "CHAdeMO", "EV_CONNECTOR_TYPE_TYPE_2": "Type2",
               "EV_CONNECTOR_TYPE_TESLA": "Tesla", "EV_CONNECTOR_TYPE_J1772": "J1772",
               "EV_CONNECTOR_TYPE_OTHER": "DC", "EV_CONNECTOR_TYPE_UNSPECIFIED_GB_T": "GB/T"}

def _ev_info(pl):
    """Pull Google evChargeOptions -> the J5-usable DC speed + live availability + a short connector blurb."""
    ev = pl.get("evChargeOptions") or {}
    dc_kw = 0; dc_total = 0; dc_avail = None; updated = None; parts = []
    for a in (ev.get("connectorAggregation") or []):
        t = a.get("type", ""); kw = round(a.get("maxChargeRateKw") or 0); n = a.get("count") or 0
        lbl = _CONN_LABEL.get(t, "AC")
        parts.append((kw, f"{lbl} {kw}kW" + (f"×{n}" if n > 1 else "")))
        is_dc = t == "EV_CONNECTOR_TYPE_CCS_COMBO_2" or (t == "EV_CONNECTOR_TYPE_OTHER" and kw >= 50)
        if is_dc:                                          # only count what a J5 can actually fast-charge on
            dc_kw = max(dc_kw, kw); dc_total += n
            av = a.get("availableCount")
            if av is not None: dc_avail = (dc_avail or 0) + av
            if a.get("availabilityLastUpdateTime"): updated = a["availabilityLastUpdateTime"]
    parts.sort(key=lambda x: -x[0])
    blurb = " · ".join(p[1] for p in parts[:2]) if parts else None
    avail = (f"{dc_avail}/{dc_total}" if dc_avail is not None and dc_total else None)
    return {"dc_kw": dc_kw, "conns": blurb, "avail": avail, "updated": updated}

def _gkey():
    try: return json.load(open(os.path.join(_DATA, "creds.json"))).get("gmaps_key")
    except Exception: return None

def _g_post(url, body, fieldmask, timeout=9):
    req = urllib.request.Request(url, data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "X-Goog-Api-Key": _gkey(), "X-Goog-FieldMask": fieldmask})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())

def _g_suggest(q, limit=6):                            # Google Places (New) text search — has coords inline
    d = _g_post("https://places.googleapis.com/v1/places:searchText",
                {"textQuery": q, "regionCode": "ID", "maxResultCount": limit},
                "places.displayName,places.formattedAddress,places.location")
    out = []
    for pl in d.get("places", []):
        loc = pl.get("location"); nm = pl.get("displayName", {}).get("text", "")
        addr = pl.get("formattedAddress", "")
        name = (nm + (", " + addr if addr and not addr.startswith(nm) else "")) if nm else addr
        if loc and name:
            out.append({"name": name, "lat": loc["latitude"], "lon": loc["longitude"]})
    return out

def _g_geocode(q):
    s = _g_suggest(q, 1)
    return (s[0]["lat"], s[0]["lon"], s[0]["name"]) if s else None

def _g_spklu(lat, lon, r=30000):                       # Google EV-charging nearby (covers SPKLU OSM misses)
    d = _g_post("https://places.googleapis.com/v1/places:searchNearby",
                {"includedTypes": ["electric_vehicle_charging_station"], "maxResultCount": 8,
                 "locationRestriction": {"circle": {"center": {"latitude": lat, "longitude": lon}, "radius": float(r)}}},
                "places.displayName,places.location")
    best = None
    for pl in d.get("places", []):
        loc = pl["location"]; dkm = _haversine(lat, lon, loc["latitude"], loc["longitude"])
        nm = pl.get("displayName", {}).get("text", "SPKLU")
        if best is None or dkm < best[0]: best = (dkm, nm, loc["latitude"], loc["longitude"])
    return best

def _http_get(url, params=None, timeout=25):
    if params: url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": _UA_TRIP})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())

def _http_post(url, data, timeout=40):
    req = urllib.request.Request(url, data=urllib.parse.urlencode(data).encode(),
                                 headers={"User-Agent": _UA_TRIP})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())

def _haversine(la1, lo1, la2, lo2):
    la1, lo1, la2, lo2 = map(math.radians, (la1, lo1, la2, lo2))
    h = math.sin((la2-la1)/2)**2 + math.cos(la1)*math.cos(la2)*math.sin((lo2-lo1)/2)**2
    return 2 * 6371 * math.asin(math.sqrt(h))

def _geocode(q):
    key = "g:" + q.lower()
    if key in _trip_cache: return _trip_cache[key]
    r = None
    if _gkey():
        try: r = _g_geocode(q)
        except Exception: r = None
    if not r:                                          # OSM fallback (no key / Google miss)
        d = _http_get("https://nominatim.openstreetmap.org/search",
                      {"q": q, "format": "json", "countrycodes": "id", "limit": 1})
        r = (float(d[0]["lat"]), float(d[0]["lon"]), d[0]["display_name"]) if d else None
        if not r:
            try:
                s = _suggest(q, 1)
                if s: r = (s[0]["lat"], s[0]["lon"], s[0]["name"])
            except Exception: pass
    _trip_cache[key] = r
    return r

def _osrm(a, b):
    url = f"https://router.project-osrm.org/route/v1/driving/{a[1]},{a[0]};{b[1]},{b[0]}"
    rt = _http_get(url, {"overview": "simplified", "geometries": "geojson"}, timeout=15)["routes"][0]
    return rt["distance"]/1000.0, rt["duration"]/3600.0, rt["geometry"]["coordinates"]  # [[lon,lat],..]

def _seg_dist_km(plat, plon, alat, alon, blat, blon):
    R = 6371.0; clat = math.cos(math.radians(plat))
    def xy(la, lo): return (math.radians(lo) * clat * R, math.radians(la) * R)
    px, py = xy(plat, plon); ax, ay = xy(alat, alon); bx, by = xy(blat, blon)
    dx, dy = bx - ax, by - ay
    t = 0.0 if (dx == 0 and dy == 0) else max(0.0, min(1.0, ((px-ax)*dx + (py-ay)*dy) / (dx*dx + dy*dy)))
    return math.hypot(px - (ax + t*dx), py - (ay + t*dy))

def _dist_to_route(plat, plon, geom):                  # min perpendicular distance (km) from a point to the route line
    best = 1e9
    for i in range(1, len(geom)):
        d = _seg_dist_km(plat, plon, geom[i-1][1], geom[i-1][0], geom[i][1], geom[i][0])
        if d < best: best = d
    return best

def _project_km(plat, plon, geom):                     # -> (offset_km, along-route_km, side) of nearest point
    R = 6371.0; clat = math.cos(math.radians(plat))    # side: +1 = left of travel (your carriageway in ID), -1 = right (seberang)
    def xy(la, lo): return (math.radians(lo) * clat * R, math.radians(la) * R)
    px, py = xy(plat, plon)
    best_off, best_cum, best_side, cum = 1e9, 0.0, 0, 0.0
    for i in range(1, len(geom)):
        alat, alon = geom[i-1][1], geom[i-1][0]; blat, blon = geom[i][1], geom[i][0]
        seg = _haversine(alat, alon, blat, blon)
        ax, ay = xy(alat, alon); bx, by = xy(blat, blon)
        dx, dy = bx - ax, by - ay
        t = 0.0 if (dx == 0 and dy == 0) else max(0.0, min(1.0, ((px-ax)*dx + (py-ay)*dy) / (dx*dx + dy*dy)))
        cx, cy = ax + t*dx, ay + t*dy
        off = math.hypot(px - cx, py - cy)
        if off < best_off:
            cross = dx * (py - cy) - dy * (px - cx)     # >0 => station left of travel direction
            best_off, best_cum, best_side = off, cum + t * seg, (1 if cross >= 0 else -1)
        cum += seg
    return best_off, best_cum, best_side

def _spklu_list(lat, lon, r=35000):                    # all candidate charging stations near a point (dicts)
    if _gkey():
        try:
            d = _g_post("https://places.googleapis.com/v1/places:searchNearby",
                        {"includedTypes": ["electric_vehicle_charging_station"], "maxResultCount": 15,
                         "locationRestriction": {"circle": {"center": {"latitude": lat, "longitude": lon}, "radius": float(r)}}},
                        "places.displayName,places.location,places.evChargeOptions")
            out = [{"name": pl.get("displayName", {}).get("text", "SPKLU"),
                    "lat": pl["location"]["latitude"], "lon": pl["location"]["longitude"], **_ev_info(pl)}
                   for pl in d.get("places", []) if pl.get("location")]
            if out: return out
        except Exception: pass
    q = f'[out:json][timeout:25];node["amenity"="charging_station"](around:{r},{lat},{lon});out;'
    try:
        els = _http_post("https://overpass-api.de/api/interpreter", {"data": q}).get("elements", [])
    except Exception:
        return []
    return [{"name": (e.get("tags", {}).get("name") or e.get("tags", {}).get("operator") or "SPKLU"),
             "lat": e["lat"], "lon": e["lon"], "dc_kw": 0, "conns": None, "avail": None, "updated": None}
            for e in els]


def _nearest_spklu(lat, lon, r=25000):
    if _gkey():                                        # Google has SPKLU coverage OSM lacks
        try:
            b = _g_spklu(lat, lon, max(r, 30000))
            if b: return b
        except Exception: pass
    q = f'[out:json][timeout:25];node["amenity"="charging_station"](around:{r},{lat},{lon});out;'
    try:
        els = _http_post("https://overpass-api.de/api/interpreter", {"data": q}).get("elements", [])
    except Exception:
        return None
    best = None
    for e in els:
        d = _haversine(lat, lon, e["lat"], e["lon"])
        t = e.get("tags", {})
        nm = t.get("name") or t.get("operator") or "SPKLU"
        if best is None or d < best[0]:
            best = (d, nm, e["lat"], e["lon"])
    return best

def _coord_at_km(geom, target_km):
    cum = 0.0
    for i in range(1, len(geom)):
        lo1, la1 = geom[i-1]; lo2, la2 = geom[i]
        seg = _haversine(la1, lo1, la2, lo2)
        if cum + seg >= target_km:
            return (la2, lo2)
        cum += seg
    return (geom[-1][1], geom[-1][0])

def _photon(q, limit=6):
    d = _http_get("https://photon.komoot.io/api/",
                  {"q": q, "limit": limit, "bbox": "95,-11,141,6", "lang": "en"})  # Indonesia bbox
    out = []
    for f in d.get("features", []):
        p = f.get("properties", {}); c = f["geometry"]["coordinates"]
        if p.get("countrycode") and p["countrycode"] != "ID":
            continue
        nm = p.get("name") or ""
        parts = [p.get(k) for k in ("street", "district", "city", "county", "state") if p.get(k)]
        name = ", ".join([x for x in [nm] + parts if x])
        if name:
            out.append({"name": name, "lat": float(c[1]), "lon": float(c[0])})
    return out

def _suggest(q, limit=6):
    if not q or len(q) < 3: return []
    if _gkey():
        try:
            g = _g_suggest(q, limit)
            if g: return g
        except Exception: pass
    res = []
    try: res += _photon(q, limit)            # POI-friendly typeahead first
    except Exception: pass
    try:
        d = _http_get("https://nominatim.openstreetmap.org/search",
                      {"q": q, "format": "json", "countrycodes": "id", "limit": limit, "addressdetails": 0})
        res += [{"name": x["display_name"], "lat": float(x["lat"]), "lon": float(x["lon"])} for x in d]
    except Exception: pass
    seen, out = set(), []
    for r in res:
        k = (round(r["lat"], 3), round(r["lon"], 3))
        if k in seen: continue
        seen.add(k); out.append(r)
        if len(out) >= limit: break
    return out

def trip_plan(frm, to, soc, cons, reserve=10.0, target=80.0, derate=1.0, a=None, b=None):
    a = a or (_geocode(frm) if frm else None)
    b = b or (_geocode(to) if to else None)
    if not a: return {"error": f"can't find '{frm}'"}
    if not b: return {"error": f"can't find '{to}'"}
    dist, dur, geom = _osrm(a, b)
    cons = cons or WLTP_KWH_100
    rpp = CAP_KWH / cons / max(0.5, derate)             # km gained per 1% SoC (derated for conditions)
    full_range = 100 * rpp
    buffer = reserve                                    # min SoC to arrive at any stop / finish with (safety margin)
    stops, pos, cur = [], 0.0, float(soc if soc is not None else 100)
    guard = 0
    while guard < 12:
        guard += 1
        max_reach = (cur - buffer) * rpp                # furthest we can go and still arrive at buffer%
        if pos + max_reach >= dist - 0.1:
            break                                       # can finish from here
        sp = _coord_at_km(geom, pos + max_reach * 0.85)
        scored = []
        for c in _spklu_list(sp[0], sp[1], 55000):
            slat, slon, nm = c["lat"], c["lon"], c["name"]
            off, cum, side = _project_km(slat, slon, geom)
            if cum <= pos + 2 or cum > pos + max_reach:
                continue                                # behind us, or can't reach while keeping buffer
            if off <= 0.8 and side < 0:
                continue                                # hugging the route on the far carriageway = seberang
            rest = 1 if any(k in nm.lower() for k in ("rest area", "travoy", "km ")) else 0
            scored.append({"cum": cum, "off": off, "rest": rest, "name": nm, "lat": slat, "lon": slon,
                           "dc_kw": c.get("dc_kw", 0), "conns": c.get("conns"),
                           "avail": c.get("avail"), "updated": c.get("updated")})
        if scored:
            rests = [c for c in scored if c["rest"] and c["off"] <= 5]
            pool = rests or scored                      # prefer rest areas
            fast = [c for c in pool if c["dc_kw"] >= 50]
            pool = fast or pool                         # then real DC fast-charging over AC/slow points
            bst = max(pool, key=lambda c: c["cum"] - c["off"] * 12 + min(c["dc_kw"], 120) * 0.03)
            new_pos, off, nm, slat, slon = bst["cum"], bst["off"], bst["name"], bst["lat"], bst["lon"]
            skw, sconns, savail, supd = bst["dc_kw"], bst["conns"], bst["avail"], bst["updated"]
        else:                                           # nothing reachable in range -> stop at range edge, nearest
            new_pos = pos + max_reach
            la0, lo0 = _coord_at_km(geom, new_pos)
            cl = _spklu_list(la0, lo0)
            if cl:
                bb = min(cl, key=lambda c: _dist_to_route(c["lat"], c["lon"], geom))
                nm, slat, slon, off = bb["name"], bb["lat"], bb["lon"], _dist_to_route(bb["lat"], bb["lon"], geom)
                skw, sconns, savail, supd = bb.get("dc_kw", 0), bb.get("conns"), bb.get("avail"), bb.get("updated")
            else:
                nm = slat = slon = off = None; skw, sconns, savail, supd = 0, None, None, None
        new_pos = round(new_pos, 1)
        la, lo = _coord_at_km(geom, new_pos)
        arrive_at = max(int(buffer), round(cur - (new_pos - pos) / rpp))   # SoC% on arrival at this stop
        need_to_finish = (dist - new_pos) / rpp + buffer
        ch_to = int(target) if need_to_finish > target else min(100, int(math.ceil(need_to_finish)) + 1)
        ch_to = max(ch_to, arrive_at + 5)
        into = (ch_to - arrive_at) / 100.0 * CAP_KWH    # kWh added here, from the real arrival SoC
        bill = into / chg_eff(ch_to)
        eff_kw = min(skw * 0.9, CAR_DC_CAP) if skw else CHG_KW_AVG   # real station kW, capped by the car
        stops.append({"at_km": new_pos, "lat": round(la, 4), "lon": round(lo, 4), "arrive": arrive_at,
                      "station": nm, "station_km": round(off, 1) if off is not None else None,
                      "station_lat": round(slat, 5) if slat is not None else None,
                      "station_lon": round(slon, 5) if slon is not None else None,
                      "charge_from": arrive_at, "charge_to": ch_to,
                      "kwh": round(bill, 1), "cost": round(bill * TARIFF_IDR),
                      "kw": skw or None, "conns": sconns, "avail": savail, "avail_updated": supd,
                      "min": max(5, round(into / eff_kw * 60))})
        cur = ch_to; pos = new_pos
    arrive = round(cur - (dist - pos) / rpp)
    step = max(1, len(geom) // 70)
    g = [[round(c[0], 4), round(c[1], 4)] for i, c in enumerate(geom) if i % step == 0 or i == len(geom)-1]
    drive_h = dur
    charge_h = sum(s["min"] for s in stops) / 60.0
    return {"from": a[2].split(",")[0], "to": b[2].split(",")[0],
            "distance": round(dist, 1), "drive_h": round(drive_h, 1),
            "total_h": round(drive_h + charge_h, 1),
            "feasible": guard < 12, "stops": stops, "arrive_soc": arrive,
            "reserve": int(reserve), "full_range": round(full_range), "rpp": round(rpp, 1),
            "geom": g, "start": [round(a[0], 4), round(a[1], 4)], "end": [round(b[0], 4), round(b[1], 4)],
            "total_kwh": round(sum(s["kwh"] for s in stops), 1),
            "total_cost": round(sum(s["cost"] for s in stops)),
            "src": "google" if _gkey() else "osm"}

class H(BaseHTTPRequestHandler):
    def log_message(self, *a):  # quiet
        pass
    def _send(self, code, body, ctype, extra=None):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _authed(self):
        return (not _gated()) or valid_session(_cookie_sid(self.headers.get("Cookie")))

    def _set_cookie(self):
        return {"Set-Cookie": f"sid={make_session()}; HttpOnly; SameSite=Lax; Path=/; Max-Age={SESSION_TTL}"}

    # paths reachable without a session (so the login/unlock page can load + submit)
    _PUBLIC = {"/login.html", "/icon.svg", "/manifest.webmanifest", "/api/status", "/api/login", "/api/unlock"}

    def do_GET(self):
        path = self.path.split("?")[0]
        if path == "/api/status":
            self._send(200, json.dumps({"configured": is_configured(), "gated": _gated(),
                                        "authed": self._authed()}).encode(), "application/json")
            return
        if _gated() and not self._authed() and path not in self._PUBLIC:
            if path in ("/", "/index.html", "/v2.html"):  # gated + locked -> show the unlock page
                with open(os.path.join(WEB, "login.html"), "rb") as f:
                    self._send(200, f.read(), "text/html; charset=utf-8")
                return
            self._send(401, b'{"error":"locked"}', "application/json")
            return
        if path == "/api/summary":
            self._send(200, json.dumps(summary()).encode(), "application/json")
            return
        if path == "/api/controls":                    # what this car supports + opcodes to test
            if not self._authed():
                self._send(401, b'{"error":"auth"}', "application/json"); return
            try:
                self._send(200, json.dumps({"caps": control_caps(), "known": KNOWN_OPCODES}).encode(),
                           "application/json")
            except Exception as e:
                self._send(200, json.dumps({"error": str(e)[:180]}).encode(), "application/json")
            return
        if path == "/car-photo":     # cached proxy for CarLinko's own render of this exact car.
            try:                     # Behind the gate: the render gives away model + colour.
                img = _vehicle_img()
                if not os.path.exists(_CAR_PHOTO):
                    if not img:
                        self._send(404, b"no vehicle image", "text/plain"); return
                    req = urllib.request.Request(img, headers={"User-Agent": "carlinko-dash"})
                    with urllib.request.urlopen(req, timeout=20) as r:
                        blob = r.read(8 * 1024 * 1024)    # cap: it's a car render, not a payload
                    tmp = _CAR_PHOTO + ".part"            # write-then-rename, so an interrupted
                    with open(tmp, "wb") as f: f.write(blob)   # fetch can't leave a truncated cache
                    os.replace(tmp, _CAR_PHOTO)
                with open(_CAR_PHOTO, "rb") as f: blob = f.read()
                kind = "image/png" if blob[:8] == b"\x89PNG\r\n\x1a\n" else "image/jpeg"
                self._send(200, blob, kind)
            except Exception as e:
                self._send(502, ("car image fetch failed: %r" % (e,)).encode(), "text/plain")
            return
        if path == "/api/refresh":                     # manual button: poll the car live, then return
            (ok, msg) = (True, "demo") if DEMO else live_poll()
            body = summary(); body["refreshed"] = ok; body["refresh_msg"] = msg
            self._send(200, json.dumps(body).encode(), "application/json")
            return
        if path == "/api/geocode":                      # autocomplete suggestions for the trip planner
            q = urllib.parse.parse_qs(self.path.split("?", 1)[1] if "?" in self.path else "")
            try:
                res = _suggest((q.get("q") or [""])[0])
            except Exception:
                res = []
            self._send(200, json.dumps(res).encode(), "application/json")
            return
        if path == "/api/spklu":                        # browse SPKLU near a map centre (PLN-Mobile-style)
            q = urllib.parse.parse_qs(self.path.split("?", 1)[1] if "?" in self.path else "")
            g1 = lambda k, d=None: (q.get(k) or [d])[0]
            try:
                lat = float(g1("lat")); lon = float(g1("lon")); r = min(40000.0, float(g1("r", "12000")))
                key = "spklu:%.3f,%.3f,%d" % (lat, lon, int(r))
                hit = _trip_cache.get(key)
                if hit and time.time() - hit[0] < 300:
                    res = hit[1]
                else:
                    res = []
                    for c in _spklu_list(lat, lon, r):
                        res.append({"name": c["name"], "lat": round(c["lat"], 5), "lon": round(c["lon"], 5),
                                    "dist": round(_haversine(lat, lon, c["lat"], c["lon"]), 1),
                                    "dc_kw": c.get("dc_kw", 0), "conns": c.get("conns"),
                                    "avail": c.get("avail"), "updated": c.get("updated")})
                    res.sort(key=lambda x: x["dist"])
                    _trip_cache[key] = (time.time(), res)
            except Exception as e:
                res = {"error": repr(e)[:160]}
            self._send(200, json.dumps(res).encode(), "application/json")
            return
        if path == "/api/trip":                         # long-trip charge planner
            qs = self.path.split("?", 1)[1] if "?" in self.path else ""
            hit = _trip_cache.get("trip:" + qs)         # cache identical plans for 10 min (instant re-plan)
            if hit and time.time() - hit[0] < 600:
                self._send(200, json.dumps(hit[1]).encode(), "application/json"); return
            q = urllib.parse.parse_qs(qs)
            g1 = lambda k, d=None: (q.get(k) or [d])[0]
            try:
                s = summary()
                soc_q = g1("soc")
                soc = float(soc_q) if soc_q else s.get("battery")
                cons = (s.get("insights") or {}).get("consumption") or WLTP_KWH_100
                flat, flon = g1("fromlat"), g1("fromlon")
                tlat, tlon = g1("tolat"), g1("tolon")
                a = (float(flat), float(flon), g1("from", "start")) if flat and flon else None
                b = (float(tlat), float(tlon), g1("to", "finish")) if tlat and tlon else None
                plan = trip_plan(g1("from", ""), g1("to", ""), soc, cons,
                                 float(g1("reserve", "15")), 80.0, float(g1("derate", "1.0")), a, b)
            except Exception as e:
                plan = {"error": repr(e)[:200]}
            if "error" not in plan:
                _trip_cache["trip:" + qs] = (time.time(), plan)
            self._send(200, json.dumps(plan).encode(), "application/json")
            return
        if path == "/api/history":                     # monthly calendar view: per-day km/kWh/charging
            qs = self.path.split("?", 1)[1] if "?" in self.path else ""
            q = urllib.parse.parse_qs(qs)
            try:
                self._send(200, json.dumps(month_history((q.get("month") or [""])[0])).encode(),
                           "application/json")
            except Exception as e:
                self._send(200, json.dumps({"ok": False, "error": str(e)[:160]}).encode(),
                           "application/json")
            return
        if path == "/":
            if not is_configured():
                path = "/login.html"                          # first run -> login page
            else:
                # default UI choice lives in a plain cookie set from either front end's settings
                ui = ""
                for part in (self.headers.get("Cookie") or "").split(";"):
                    part = part.strip()
                    if part.startswith("ui="):
                        ui = part[3:]
                path = "/v2.html" if ui == "v2" else "/index.html"
        fp = os.path.normpath(os.path.join(WEB, path.lstrip("/")))
        if not fp.startswith(os.path.abspath(WEB)) or not os.path.isfile(fp):
            self._send(404, b"not found", "text/plain")
            return
        ctype = {"html": "text/html", "js": "text/javascript", "css": "text/css",
                 "webmanifest": "application/manifest+json", "json": "application/json",
                 "svg": "image/svg+xml", "png": "image/png"}.get(fp.rsplit(".", 1)[-1], "text/plain")
        with open(fp, "rb") as f:
            self._send(200, f.read(), ctype + ("; charset=utf-8" if ctype.startswith("text") or "manifest" in ctype or ctype.endswith("svg+xml") else ""))

    def do_POST(self):
        path = self.path.split("?")[0]
        if path == "/api/login":
            try:
                n = int(self.headers.get("Content-Length") or 0)
                body = json.loads(self.rfile.read(n).decode() or "{}")
                email = (body.get("email") or "").strip()
                password = body.get("password") or ""
                if not email or not password:
                    self._send(400, json.dumps({"ok": False, "error": "email and password required"}).encode(), "application/json")
                    return
                veh = web_login(email, password, body.get("region") or "sea",
                                body.get("gmaps_key"), body.get("dashboard_password"))
                self._send(200, json.dumps({"ok": True, "vehicle": veh}).encode(),
                           "application/json", self._set_cookie())   # log them straight in
            except Exception as e:
                msg = str(e)
                if "login failed" in msg.lower() or "code" in msg.lower():
                    msg = "Login failed — check your email and password."
                self._send(200, json.dumps({"ok": False, "error": msg[:160]}).encode(), "application/json")
            return
        if path == "/api/unlock":                          # re-enter the dashboard password to get a session
            try:
                n = int(self.headers.get("Content-Length") or 0)
                body = json.loads(self.rfile.read(n).decode() or "{}")
                if check_dashboard_password(body.get("password") or ""):
                    self._send(200, b'{"ok":true}', "application/json", self._set_cookie())
                else:
                    self._send(200, json.dumps({"ok": False, "error": "Wrong password."}).encode(), "application/json")
            except Exception as e:
                self._send(200, json.dumps({"ok": False, "error": str(e)[:120]}).encode(), "application/json")
            return
        if path == "/api/forcerefresh":                # poke the car with the benign init (0x77) so it
            if not self._authed():                     # reports now; the client then re-reads the DB.
                self._send(401, b'{"ok":false,"error":"auth"}', "application/json"); return
            try:
                op = str(_creds().get("refresh_opcode") or "77")   # 0x77 = CarLinko's own "initializing car"
                d = send_control(op, 15)
                self._send(200, json.dumps({"ok": str(d.get("code")) == "0000",
                                            "code": d.get("code"), "msg": d.get("msg")}).encode(),
                           "application/json")
            except Exception as e:
                self._send(200, json.dumps({"ok": False, "error": str(e)[:160]}).encode(), "application/json")
            return
        if path == "/api/control":                     # fire a remote-control opcode at the car
            if not self._authed():
                self._send(401, b'{"ok":false,"error":"auth"}', "application/json"); return
            try:
                n = int(self.headers.get("Content-Length") or 0)
                body = json.loads(self.rfile.read(n).decode() or "{}")
                op = str(body.get("data") or "").strip()
                if not op or not all(ch in "0123456789abcdefABCDEF" for ch in op) or len(op) > 16:
                    self._send(200, json.dumps({"ok": False, "error": "opcode must be short hex"}).encode(),
                               "application/json"); return
                d = send_control(op, body.get("timeOut") or 20)
                self._send(200, json.dumps({"ok": str(d.get("code")) == "0000",
                                            "code": d.get("code"), "msg": d.get("msg")}).encode(),
                           "application/json")
            except Exception as e:
                self._send(200, json.dumps({"ok": False, "error": str(e)[:180]}).encode(), "application/json")
            return
        if path == "/api/photorefresh":                # re-grab this car's render from CarLinko
            if not self._authed():
                self._send(401, b'{"ok":false,"error":"auth"}', "application/json"); return
            try:
                import auth, requests
                token = _read_token()
                data = requests.get(auth.api_base() + "/user/vehicle",
                                    headers=auth.headers_for({}, token=token), timeout=20).json().get("data")
                v = data[0] if isinstance(data, list) and data else (data if isinstance(data, dict) else {})
                img = _vehicle_img_url(v)
                if not img:
                    self._send(200, json.dumps({"ok": False,
                                                "error": "no vehicleImgConfig from CarLinko"}).encode(),
                               "application/json"); return
                c = _creds(); c.setdefault("vehicle", {})["img"] = img
                cpath = os.path.join(_DATA, "creds.json")
                json.dump(c, open(cpath, "w"), indent=2)
                try: os.chmod(cpath, 0o600)
                except Exception: pass
                try: os.remove(_CAR_PHOTO)              # force a fresh cache pull
                except Exception: pass
                self._send(200, json.dumps({"ok": True}).encode(), "application/json")
            except Exception as e:
                self._send(200, json.dumps({"ok": False, "error": str(e)[:160]}).encode(),
                           "application/json")
            return
        if path == "/api/config":                      # dashboard settings persisted in creds.json
            if not self._authed():
                self._send(401, b'{"ok":false,"error":"auth"}', "application/json"); return
            try:
                n = int(self.headers.get("Content-Length") or 0)
                body = json.loads(self.rfile.read(n).decode() or "{}")
                if body.get("resync_km") not in ("skip", "count"):
                    self._send(200, json.dumps({"ok": False,
                                                "error": "resync_km must be skip or count"}).encode(),
                               "application/json"); return
                cpath = os.path.join(_DATA, "creds.json")
                try:
                    c = json.load(open(cpath))
                except Exception:
                    c = {}
                c["resync_km"] = body["resync_km"]
                json.dump(c, open(cpath, "w"), indent=2)
                try: os.chmod(cpath, 0o600)
                except Exception: pass
                self._send(200, json.dumps({"ok": True, "resync_km": c["resync_km"]}).encode(),
                           "application/json")
            except Exception as e:
                self._send(200, json.dumps({"ok": False, "error": str(e)[:120]}).encode(),
                           "application/json")
            return
        self._send(404, b"not found", "text/plain")

def main():
    ports = [a for a in sys.argv[1:] if a.isdigit()]       # ignore flags like --demo
    port = int(ports[0]) if ports else 8088
    if DEMO:
        print(f"CarLinko dashboard (DEMO — fake data) on http://0.0.0.0:{port}")
    else:
        _ensure_db()                                       # so a brand-new install serves without crashing
        print(f"CarLinko dashboard on http://0.0.0.0:{port}  (db={os.path.abspath(DB)})")
    ThreadingHTTPServer(("0.0.0.0", port), H).serve_forever()

if __name__ == "__main__":
    main()
