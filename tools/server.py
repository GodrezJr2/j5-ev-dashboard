"""CarLinko dashboard server (stdlib only).
Serves the mobile PWA in ./web and a JSON API computed from carlinko.db.
Run: python server.py [port]   (default 8088, binds 0.0.0.0 so Tailscale can reach it)
"""
import os, sys, json, time, sqlite3, threading, math, urllib.request, urllib.parse
import hmac, hashlib, base64, secrets
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

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
_DATA = os.environ.get("CARLINKO_DATA") or HERE          # Docker data dir; else alongside the code
DB   = os.path.join(_DATA, "carlinko.db") if os.environ.get("CARLINKO_DATA") else os.path.join(HERE, "..", "carlinko.db")
WEB  = os.path.join(HERE, "..", "web")

def _creds():
    try:
        return json.load(open(os.path.join(_DATA, "creds.json")))
    except Exception:
        return {}

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
TPMS_POS = ["FL", "FR", "RL", "RR"]

def is_configured():
    """True once an account is set up — used to decide whether to show the login page."""
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

# ---- optional dashboard auth (off by default; set a dashboard_password to gate public hosting) ----
SESSION_TTL = 30 * 86400

def _gated():
    return bool(_creds().get("dash_pw_hash"))

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

def psi(x):  return None if x == 0xFF else round(x * 1.373 * 0.145, 1)
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
        d["ignition"] = b[3]                               # 0=off/parked, !=0=on (flipped 00->01 at start)
        d["speed"] = round(int.from_bytes(b[14:16], "big") / 16.0, 1)  # km/h: bytes14-15 BE /16 (calibrated live: raw 320 = 20 km/h)
    if len(b) > 55:
        d["consumption"] = round(b[55] * 0.1, 1)           # car's own avg kWh/100km (byte55 x0.1; matches dash 12.2)
    d["tyre"] = b[44:52] if len(b) >= 52 else None         # 4 psi + 4 temp, FF=parked
    return d

_CC = _creds()          # per-model overrides (default to the J5 EV values this was calibrated on)
CAP_KWH = float(_CC.get("battery_kwh") or 58.9)        # net usable battery (J5: gross 60.9 kWh, LFP)
WLTP_KWH_100 = float(_CC.get("wltp_kwh_100") or 14.8)  # WLTP reference consumption -> "optimal" baseline
TARIFF_IDR_CFG = _CC.get("tariff_idr")                 # local SPKLU all-in Rp/kWh override (optional)
IDLE_GAP = 1800         # parked + no SoC rise for 30 min => charge session ended
CHARGE_PARK_MIN = 600   # a real charge sits odo-flat >=10 min; regen blips (odo coarse=1km) don't
MIN_GAIN_PCT = 2        # net SoC gain floor; drops 1% regen/noise that survives the park gate
TARIFF_IDR = int(TARIFF_IDR_CFG or 2540)  # all-in SPKLU DC Rp/kWh (Rp2.467 base + 3% tax; service Rp0)
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
PETROL_KM_L = 12.0      # comparable ICE fuel economy (km per litre)
PETROL_RP_L = 12500     # Pertamax-class petrol price Rp/litre (for savings-vs-petrol insight)

def build_trips(data):
    """A trip = a run of moving frames (odometer rising). Bridges brief stops; ends
    after TRIP_GAP parked. Returns newest-first with km / time / speed / kWh / efficiency."""
    fr = [(ts, d.get("battery"), d.get("odometer")) for ts, dt, d in data
          if d.get("battery") is not None and d.get("odometer") is not None]
    trips, cur, last_move = [], None, 0
    for i in range(1, len(fr)):
        ts0, b0, o0 = fr[i-1]; ts1, b1, o1 = fr[i]
        if o1 > o0:                                    # moving (odometer rising = reliable)
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
        if eff is not None and not (5 <= eff <= 40):    # implausible (sparse-data merge) -> hide energy
            eff = kwh = None
        out.append({"start_dt": time.strftime("%a %H:%M", time.localtime(t["start"])),
                    "km": dist, "min": round(dur_min), "avg_kmh": avg,
                    "kwh": round(kwh, 1) if kwh else None, "kwh100": eff})
    return out[::-1]                                    # newest first

def build_sessions(fr, now):
    """fr = [(ts, soc, odo)] sorted asc. A charge session = parked (odo flat) frames
    where SoC trends up. Robust to dense frames where most steps show 0% change."""
    raw, cur = [], None
    for i in range(len(fr)):
        ts, soc, odo = fr[i]
        moved = i > 0 and odo > fr[i-1][2]
        if moved:                                      # car drove -> close any session
            if cur:
                if soc > cur["max"]:                   # charge peaked right before unplug/drive-off
                    cur["max"] = soc; cur["last_rise"] = ts; cur["pts"].append((ts, soc))
                raw.append(cur); cur = None
            continue
        if cur is None:                                # open when SoC rises vs prev parked frame
            if i > 0 and odo == fr[i-1][2] and soc > fr[i-1][1]:
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

def analyze(data):
    """Energy/efficiency from SoC%+odometer; charging sessions from parked SoC-rise."""
    out = {
        "battery_kwh": CAP_KWH, "top_speed_today": 0,
        "energy": {"today_kwh": 0.0, "consumption": None, "rating": None, "week_consumption": None},
        "charging": {"active": False, "session_kwh": 0.0, "rate_kw": None, "soc": None,
                     "week": 0, "month": 0, "week_kwh": 0.0, "month_kwh": 0.0, "session": None},
    }
    today = time.strftime("%Y-%m-%d"); week = time.strftime("%Y-W%W"); month = time.strftime("%Y-%m")
    fr = [(ts, d.get("battery"), d.get("odometer")) for ts, dt, d in data
          if d.get("battery") is not None and d.get("odometer") is not None]
    used_today = km_today = used_week = km_week = 0.0
    for i in range(1, len(fr)):
        ts0, b0, o0 = fr[i-1]; ts1, b1, o1 = fr[i]
        if o1 > o0:                                    # moving
            dkwh = (b1 - b0) / 100.0 * CAP_KWH
            if dkwh < 0:
                if time.strftime("%Y-%m-%d", time.localtime(ts1)) == today:
                    used_today += -dkwh; km_today += (o1 - o0)
                if time.strftime("%Y-W%W", time.localtime(ts1)) == week:
                    used_week += -dkwh; km_week += (o1 - o0)
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
    full = [s for s in sess if s["soc1"] >= 100]       # LFP wants a periodic 100% for balancing
    out["battery_care"] = {
        "last_full_dt": time.strftime("%d %b", time.localtime(full[-1]["start"])) if full else None,
        "days_since_full": round((now - full[-1]["start"]) / 86400) if full else None,
        "balance_due": (not full) or ((now - full[-1]["start"]) / 86400 >= 14)}
    ongoing = [s for s in sess if s["ongoing"]]
    if ongoing:
        s = ongoing[-1]; lr = live_rate(s["pts"])
        out["charging"].update(active=True, session_kwh=round(s["kwh"], 2), soc=s["soc1"],
                               rate_kw=round(lr if lr is not None else s["avg"], 1))
    detail = ongoing[-1] if ongoing else (sess[-1] if sess else None)
    if detail:
        out["charging"]["session"] = session_detail(detail)
    trips_all = build_trips(data)
    out["trips"] = trips_all[:8]
    avgs = [t["avg_kmh"] for t in trips_all if t.get("avg_kmh")]
    out["avg_speed"] = round(sum(avgs) / len(avgs)) if avgs else None   # odo-based, reliable
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
    rpkm = cons * TARIFF_IDR / 100.0 / CHG_EFF_AVG      # Rp/km incl charging loss (you pay delivered)
    ins["rp_per_km"] = round(rpkm)
    hist = out.get("history") or []
    avg_daily = (sum(h["km"] for h in hist) / len(hist)) if hist else 0.0
    ins["avg_daily_km"] = round(avg_daily)
    ins["month_cost_est"] = round(avg_daily * 30 * rpkm)
    petrol_rpkm = PETROL_RP_L / PETROL_KM_L            # comparable ICE Rp/km
    ins["save_per_km"] = round(petrol_rpkm - rpkm)
    ins["month_save_est"] = round(avg_daily * 30 * (petrol_rpkm - rpkm))
    rng, batt = out.get("range_km"), out.get("battery")
    ins["days_to_charge"] = round(rng / avg_daily, 1) if (rng and avg_daily > 0.5) else None
    ins["rated_range"] = round(rng / batt * 100) if (rng and batt) else None   # car's full-charge estimate
    ins["real_range"] = round(CAP_KWH / cons * 100) if cons else None          # from your real consumption
    if ins["rated_range"] and ins["real_range"]:
        r = ins["real_range"] / ins["rated_range"]
        ins["range_verdict"] = "accurate" if 0.95 <= r <= 1.06 else ("optimistic" if r < 0.95 else "conservative")
    return ins

def summary():
    out = {"vehicle": VEHICLE, "online": False, "battery": None, "range_km": None,
           "odometer": None, "volt12": None, "ignition": None, "speed": None,
           "moving": False, "avg_speed": None, "insights": {}, "health": {}, "drain": None,
           "volt12_min7d": None, "volt12_status": None,
           "updated": None, "age_min": None,
           "battery_kwh": CAP_KWH,
           "energy": {"today_kwh": 0.0, "consumption": None, "rating": None,
                      "week_consumption": None},
           "charging": {"active": False, "session_kwh": 0.0, "rate_kw": None, "soc": None,
                        "week": 0, "month": 0, "week_kwh": 0.0, "month_kwh": 0.0,
                        "month_cost": 0, "history": [], "session": None},
           "trips": [],
           "tpms": [{"pos": p, "psi": None, "temp": None, "valid": False} for p in TPMS_POS],
           "tpms_updated": None, "tpms_age_min": None, "tpms_live": False,
           "tyre_status": "Normal", "tyre_indirect": True,
           "km": {"today": None, "week": None, "month": None},
           "charges": {"week": None, "month": None},
           "history": []}
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
               ignition=dec.get("ignition"), speed=None, updated=dt)
    out["age_min"] = round((time.time() - ts) / 60, 1)
    out["online"] = out["age_min"] is not None and out["age_min"] < 40
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
            out["tpms"] = [{"pos": TPMS_POS[i], "psi": psi(tb[i]), "temp": temp(tb[4 + i]),
                            "valid": tb[i] != 0xFF} for i in range(4)]
            out["tpms_updated"] = dt2
            out["tpms_age_min"] = round((time.time() - ts2) / 60, 1)
            out["tpms_live"] = (ts2 == ts)  # newest frame still has live tyres
            break
    valid_psi = [t["psi"] for t in out["tpms"] if t["psi"] is not None]
    if valid_psi:  # real per-wheel PSI present (never on this car — indirect TPMS, bytes stay FF)
        out["tyre_indirect"] = False
        out["tyre_status"] = "Check tyres" if any(p < 28 or p > 40 for p in valid_psi) else "Normal"

    def km_between(fmt):
        agg = {}
        for ts, dt, dec in data:
            odo = dec.get("odometer")
            if odo is None:
                continue
            k = time.strftime(fmt, time.localtime(ts))
            lo, hi = agg.get(k, (odo, odo))
            agg[k] = (min(lo, odo), max(hi, odo))
        return agg
    today = time.strftime("%Y-%m-%d")
    week  = time.strftime("%Y-W%W")
    month = time.strftime("%Y-%m")
    d = km_between("%Y-%m-%d")
    w = km_between("%Y-W%W")
    m = km_between("%Y-%m")
    out["km"]["today"] = (d[today][1] - d[today][0]) if today in d else 0
    out["km"]["week"]  = (w[week][1] - w[week][0]) if week in w else 0
    out["km"]["month"] = (m[month][1] - m[month][0]) if month in m else 0
    # per-day energy used (SoC drop while moving) -> daily efficiency for the trend
    frS = [(ts, dec2.get("battery"), dec2.get("odometer")) for ts, dt2, dec2 in data
           if dec2.get("battery") is not None and dec2.get("odometer") is not None]
    day_used = {}
    for i in range(1, len(frS)):
        t0, b0, o0 = frS[i-1]; t1, b1, o1 = frS[i]
        if o1 > o0 and b0 > b1:                        # moving + SoC fell = energy spent
            k = time.strftime("%Y-%m-%d", time.localtime(t1))
            day_used[k] = day_used.get(k, 0.0) + (b0 - b1) / 100.0 * CAP_KWH
    # last 7 days km + efficiency series
    series = []
    for i in range(6, -1, -1):
        day = time.strftime("%Y-%m-%d", time.localtime(time.time() - i * 86400))
        km = (d[day][1] - d[day][0]) if day in d else 0
        u = day_used.get(day, 0.0)
        eff = round(u / km * 100, 1) if (km >= 1 and u > 0) else None
        if eff is not None and not (9 <= eff <= 30):   # 1%-coarse SoC over short trips lies; hide it
            eff = None
        series.append({"day": day[5:], "km": km, "kwh": round(u, 1), "eff": eff})
    out["history"] = series
    res = analyze(data)
    out["battery_kwh"] = res["battery_kwh"]
    out["energy"] = res["energy"]
    # prefer the car's own BMS consumption (byte55) over the coarse SoC-derived estimate
    rc = dec.get("consumption")
    if rc:
        out["energy"]["consumption"] = rc
        out["energy"]["rating"] = ("optimal" if rc < WLTP_KWH_100 else "normal" if rc < 18 else "boros")
        out["energy"]["source"] = "car"
    out["charging"] = res["charging"]
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
    # if actively charging, reflect it in the headline state
    if res["charging"]["active"]:
        out["ignition"] = out.get("ignition")
    return out

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
            if path == "/" or path == "/index.html":       # gated + locked -> show the unlock page
                with open(os.path.join(WEB, "login.html"), "rb") as f:
                    self._send(200, f.read(), "text/html; charset=utf-8")
                return
            self._send(401, b'{"error":"locked"}', "application/json")
            return
        if path == "/api/summary":
            self._send(200, json.dumps(summary()).encode(), "application/json")
            return
        if path == "/api/refresh":                     # manual button: poll the car live, then return
            ok, msg = live_poll()
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
        if path == "/":
            path = "/index.html" if is_configured() else "/login.html"   # first run -> login page
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
        self._send(404, b"not found", "text/plain")

def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8088
    _ensure_db()                                           # so a brand-new install serves without crashing
    print(f"CarLinko dashboard on http://0.0.0.0:{port}  (db={os.path.abspath(DB)})")
    ThreadingHTTPServer(("0.0.0.0", port), H).serve_forever()

if __name__ == "__main__":
    main()
