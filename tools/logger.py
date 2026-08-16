"""CarLinko telemetry logger.
Polls the realtime WebSocket (token auth, no signing) and records each frame to SQLite.
Stores the RAW blob every poll so fields decoded later (odometer, charge flag, tyres) can
be back-filled from history.

Usage:
  python logger.py            # single poll (good for Windows Task Scheduler)
  python logger.py --loop 600 # poll every 600s forever (Ctrl-C to stop)
"""
import sys, json, time, sqlite3, argparse, os, socket
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import websocket  # websocket-client

# Force IPv4: some hosts resolve an AAAA record and hang on the WS handshake.
_orig_gai = socket.getaddrinfo
def _gai_v4(host, port, family=0, *a, **k):
    res = _orig_gai(host, port, socket.AF_INET, *a, **k)
    return res or _orig_gai(host, port, family, *a, **k)
socket.getaddrinfo = _gai_v4

_HERE = os.path.dirname(os.path.abspath(__file__))
_DATA = os.environ.get("CARLINKO_DATA") or _HERE   # Docker data dir; else alongside the code
def _cfg():
    try:
        return json.load(open(os.path.join(_DATA, "creds.json")))
    except Exception:
        return {}
_C = _cfg()
WS_URL  = f"ws://wss-cqr-{_C.get('region','sea')}.hzhjcl.com:4002/"
# Token comes from token.txt (auto-refreshed by auth.login() on expiry); vehicle id + device SN from creds.json.
_TOKEN_FILE = os.path.join(_DATA, "token.txt")
TOKEN   = open(_TOKEN_FILE).read().strip() if os.path.exists(_TOKEN_FILE) else ""
VEHICLE = str(_C.get("vehicle_id") or "")
SN      = _C.get("device_sn") or ""
DB      = os.path.join(_DATA, "carlinko.db") if os.environ.get("CARLINKO_DATA") else os.path.join(_HERE, "..", "carlinko.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS telemetry (
  ts        INTEGER PRIMARY KEY,   -- unix seconds
  dt        TEXT,                  -- local ISO time
  battery   INTEGER,
  range_km  INTEGER,
  odo_guess INTEGER,               -- candidate odometer (bytes 12-13), validate by driving
  tyre_raw  TEXT,                  -- 8 bytes hex (4 psi + 4 temp), FF=invalid
  online    INTEGER,               -- 1 if a fresh blob arrived
  raw       TEXT                   -- full blob hex (for back-decoding)
);
"""

def decode(hexstr):
    b = bytes.fromhex(hexstr)
    d = {"raw": hexstr}
    if len(b) > 30:
        d["battery"]  = b[28]
        d["range_km"] = int.from_bytes(b[29:31], "big")
        d["odo_guess"] = int.from_bytes(b[18:21], "big")  # validated =882 (0x0372)
        d["unlocked"] = b[3] != 0                         # 0=locked (see docs/api-map.md -- verified #5)
        d["speed"]    = int.from_bytes(b[14:16], "big") / 16.0
    if len(b) >= 52:
        d["tyre_raw"] = b[44:52].hex()
    return d

def connect(attempts=3):
    last = None
    for i in range(attempts):
        try:
            return websocket.create_connection(
                WS_URL, timeout=20, suppress_origin=True,
                header=["User-Agent: Dart/3.10 (dart:io)"])
        except Exception as e:
            last = e
            time.sleep(2 + i * 2)
    raise last

def reload_config():
    """Re-read creds.json + token.txt so a fresh login (e.g. via the web login page) is picked
    up without restarting the process."""
    global TOKEN, VEHICLE, SN, WS_URL, _C
    _C = _cfg()
    VEHICLE = str(_C.get("vehicle_id") or "") or VEHICLE
    SN = _C.get("device_sn") or SN
    WS_URL = f"ws://wss-cqr-{_C.get('region','sea')}.hzhjcl.com:4002/"
    if os.path.exists(_TOKEN_FILE):
        TOKEN = open(_TOKEN_FILE).read().strip() or TOKEN

def poll_once(conn, _retried=False):
    global TOKEN
    if not _retried:
        reload_config()
        conn.executescript(SCHEMA)          # idempotent: ensure the table exists for any caller
    ws = connect()
    try:
        ws.send(json.dumps({"action": 1, "data": {"token": TOKEN, "vehicleId": VEHICLE}}))
        login = json.loads(ws.recv())
        if login.get("code") != "0000":
            try: ws.close()
            except Exception: pass
            if not _retried:
                print(f"token invalid ({login.get('code')}); self-logging in...")
                try:
                    import auth
                    TOKEN = auth.login()
                    print("got fresh token, retrying poll")
                    return poll_once(conn, _retried=True)
                except Exception as e:
                    print("self-login FAILED:", e)
                    return None
            print("LOGIN FAILED after refresh:", login)
            return None
        ws.send(json.dumps({"action": 6}))
        ws.send(json.dumps({"action": 0, "data": {"sn": SN}}))
        blob = None
        ws.settimeout(8)
        t_end = time.time() + 10
        while time.time() < t_end:
            try:
                j = json.loads(ws.recv())
            except Exception:
                break
            if j.get("action") == 6 and isinstance(j.get("data"), str):
                blob = j["data"]; break
    finally:
        ws.close()

    ts = int(time.time())
    dt = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts))
    if blob:
        d = decode(blob)
        conn.execute(
            "INSERT OR REPLACE INTO telemetry VALUES (?,?,?,?,?,?,?,?)",
            (ts, dt, d.get("battery"), d.get("range_km"), d.get("odo_guess"),
             d.get("tyre_raw"), 1, blob))
        print(f"{dt}  battery={d.get('battery')}%  range={d.get('range_km')}km  "
              f"odo?={d.get('odo_guess')}  spd={d.get('speed')}  unl={d.get('unlocked')}")
        return d
    conn.execute("INSERT OR REPLACE INTO telemetry VALUES (?,?,?,?,?,?,?,?)",
                 (ts, dt, None, None, None, None, 0, None))
    print(f"{dt}  (no blob — car offline/basement)")
    return None

# adaptive cadence (seconds). Near-real-time while the car is doing anything -- on the road,
# charging, or the car unlocked/in use -- and ease off only when it's parked+idle or genuinely
# dark. All three
# tiers are overridable from creds.json so you can tune without editing code.
ACTIVE = int(_C.get("poll_active")  or 5)   # driving / charging / unlocked -> near real-time.
                                            # The cloud has its own push lag, so below ~5 s just
                                            # re-fetches the same frame and hammers CarLinko.
PARK   = int(_C.get("poll_parked")  or 30)  # parked, engine off, not charging: cloud just replays
                                            # the last frame, so 5 s would spam identical bytes. 30 s
                                            # still catches a wake (ignition/plug-in) within 30 s,
                                            # then it jumps to ACTIVE. Set to 5 for always-real-time.
OFFLINE_SLOW = int(_C.get("poll_offline") or 900)  # genuinely dark (basement, no signal) -> back off
HOLD = 600         # keep ACTIVE this long after the last sign of activity (bridges a brief stop)
OFFLINE_AFTER = 3  # consecutive empty polls before the car counts as dark
CHG_LOOKBACK = 900 # window (s) to spot an ongoing charge from a SoC rise. SoC is 1%-coarse, so a
                   # slow AC charge won't tick a whole percent between two polls -- comparing the
                   # latest reading to the *prior* one reads "flat" and drops us out of real-time
                   # mid-charge. Compare to the window's low instead, which still sees the gain.

def adaptive_loop(conn):
    print(f"adaptive logging to {os.path.abspath(DB)}  (active={ACTIVE}s / parked={PARK}s / dark={OFFLINE_SLOW}s)")
    active_until = 0.0
    last_odo = None
    soc_hist = []      # (ts, soc) within CHG_LOOKBACK, to spot a slow charge the prior frame can't
    miss = 0
    while True:
        try:
            st = poll_once(conn)
            conn.commit()
        except Exception as e:
            print("poll error:", repr(e)); st = None
        now = time.time()
        if st:
            miss = 0
            soc = st.get("battery"); odo = st.get("odo_guess")
            # on the road = odometer advancing, or the car unlocked (b3 -- the "in use" hint; the
            # lock/unlock byte verified in #5, previously mistaken for ignition). Charging is
            # handled separately below (b3 is 0 on some cars while charging).
            driving = bool(st.get("unlocked")) or (last_odo is not None and odo is not None and odo > last_odo)
            if soc is not None:
                soc_hist.append((now, soc))
            if driving:
                active_until = now + HOLD
            if odo is not None: last_odo = odo
        else:
            miss += 1
        # charge detector: SoC now above the window's low => still gaining => plugged in. Survives
        # the 1%-coarse SoC that looks flat frame-to-frame, so a slow charge stays real-time. When
        # the charge ends (or the car unplugs) the low catches up within CHG_LOOKBACK and releases.
        soc_hist = [(t, s) for (t, s) in soc_hist if now - t <= CHG_LOOKBACK]
        charging = bool(soc_hist) and soc_hist[-1][1] > min(s for _t, s in soc_hist)
        awake = charging or time.time() < active_until
        if awake:                                      # on the road or plugged in -> near real-time.
            delay = ACTIVE                             # a momentary empty frame here is a transient WS
        elif miss >= OFFLINE_AFTER:                    # hiccup (car still awake), so we stay fast.
            delay = OFFLINE_SLOW                       # genuinely dark for a while -> back off
        else:
            delay = PARK                               # parked + idle + online
        time.sleep(delay)

# ---- persistent stream (recommended): hold ONE socket, like the CarLinko app does ----
# The probe proved the cloud PUSHES an action:6 frame whenever the car reports a change, as long as
# the socket is kept warm with an action:0 heartbeat. So instead of reconnecting + logging in every
# few seconds (the source of the WebSocketTimeouts and the stale gaps), open once and receive. New
# data lands the instant the car reports -- bounded only by the car's own report cadence, which no
# amount of polling can beat.
HEARTBEAT       = 5   # action:0 keepalive cadence -- matches the app; keeps the push subscription alive
STREAM_BACKSTOP = int(_C.get("stream_backstop") or 20)  # re-request action:6 this often, purely as a
                                                        # safety net for a missed push (pushes do the work)
TOUCH           = 30  # re-store the last frame at least this often so a parked car still reads
                      # "live · <30s ago" even when nothing changes and nothing is pushed
RECONNECT_WAIT  = 3   # backoff before reopening a dropped socket

def _store_blob(conn, blob):
    ts = int(time.time()); dt = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts))
    d = decode(blob)
    conn.execute("INSERT OR REPLACE INTO telemetry VALUES (?,?,?,?,?,?,?,?)",
                 (ts, dt, d.get("battery"), d.get("range_km"), d.get("odo_guess"),
                  d.get("tyre_raw"), 1, blob))
    conn.commit()
    return d

def _stream_session(conn):
    """One connection's lifetime: login, prime a frame, then heartbeat + receive pushes until the
    socket drops or errors (which bubbles up to stream_loop, which reconnects)."""
    global TOKEN
    reload_config()
    ws = connect()
    try:
        ws.send(json.dumps({"action": 1, "data": {"token": TOKEN, "vehicleId": VEHICLE}}))
        login = json.loads(ws.recv())
        if login.get("code") != "0000":                    # token expired -> self-login, as poll_once does
            print(f"token invalid ({login.get('code')}); self-logging in...")
            import auth
            TOKEN = auth.login()
            ws.send(json.dumps({"action": 1, "data": {"token": TOKEN, "vehicleId": VEHICLE}}))
            login = json.loads(ws.recv())
            if login.get("code") != "0000":
                print("LOGIN FAILED after refresh:", login); return
        ws.send(json.dumps({"action": 6}))                 # prime: pull the current frame immediately
        ws.send(json.dumps({"action": 0, "data": {"sn": SN}}))
        ws.settimeout(2)
        last_hb = last_req = last_store = time.time()
        last_blob = None
        while True:
            now = time.time()
            if now - last_hb >= HEARTBEAT:
                ws.send(json.dumps({"action": 0, "data": {"sn": SN}})); last_hb = now
            if now - last_req >= STREAM_BACKSTOP:
                ws.send(json.dumps({"action": 6})); last_req = now
            try:
                msg = ws.recv()
            except websocket.WebSocketTimeoutException:
                if last_blob and time.time() - last_store >= TOUCH:   # keep the freshness stamp live
                    _store_blob(conn, last_blob); last_store = time.time()
                continue
            try:
                j = json.loads(msg)
            except Exception:
                continue
            if j.get("action") == 6 and isinstance(j.get("data"), str):
                blob = j["data"]
                changed = blob != last_blob
                if changed or time.time() - last_store >= TOUCH:
                    d = _store_blob(conn, blob); last_store = time.time()
                    print(f"{time.strftime('%H:%M:%S')}  batt={d.get('battery')}%  "
                          f"range={d.get('range_km')}km  odo?={d.get('odo_guess')}  "
                          f"{'push' if changed else 'touch'}")
                last_blob = blob
    finally:
        try: ws.close()
        except Exception: pass

def stream_loop(conn):
    """Persistent-socket ingest: one WS, action:0 heartbeat, receive pushed frames. Reconnects on any
    drop. Low-latency and low-load -- no per-cycle handshake, so no reconnect-induced timeouts."""
    reload_config()
    conn.executescript(SCHEMA)
    print(f"streaming to {os.path.abspath(DB)}  (push + {HEARTBEAT}s heartbeat, auto-reconnect)")
    while True:
        try:
            _stream_session(conn)
        except Exception as e:
            print("stream error, reconnecting:", repr(e))
        time.sleep(RECONNECT_WAIT)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--loop", type=int, default=0, help="fixed seconds between polls; 0 = single")
    ap.add_argument("--adaptive", action="store_true", help="fast when awake, slow when parked")
    ap.add_argument("--stream", action="store_true", help="persistent WS socket, push-driven (recommended)")
    args = ap.parse_args()
    conn = sqlite3.connect(DB)
    conn.executescript(SCHEMA)
    if args.stream:
        stream_loop(conn)
    elif args.adaptive:
        adaptive_loop(conn)
    elif args.loop <= 0:
        poll_once(conn); conn.commit()
    else:
        print(f"logging every {args.loop}s to {os.path.abspath(DB)}  (Ctrl-C to stop)")
        while True:
            try:
                poll_once(conn); conn.commit()
            except Exception as e:
                print("poll error:", repr(e))
            time.sleep(args.loop)

if __name__ == "__main__":
    main()
