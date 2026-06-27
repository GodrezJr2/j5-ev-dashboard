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
        d["ignition"] = b[3]                               # 0=parked
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
              f"odo?={d.get('odo_guess')}  spd={d.get('speed')}  ign={d.get('ignition')}")
        return d
    conn.execute("INSERT OR REPLACE INTO telemetry VALUES (?,?,?,?,?,?,?,?)",
                 (ts, dt, None, None, None, None, 0, None))
    print(f"{dt}  (no blob — car offline/basement)")
    return None

# adaptive cadence: poll fast while the car is awake (driving/charging), slow when asleep
FAST = 15          # seconds between polls when active
SLOW = 300         # seconds when parked + idle (online)
HOLD = 600         # stay in FAST this long after the last sign of activity
OFFLINE_SLOW = 900 # back off when persistently dark (basement = no signal), reconnect fast on return
OFFLINE_AFTER = 3  # consecutive empty polls before backing off

def adaptive_loop(conn):
    print(f"adaptive logging to {os.path.abspath(DB)}  (fast={FAST}s active / slow={SLOW}s idle)")
    active_until = 0.0
    last_soc = last_odo = None
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
            # awake = driving (odometer rising, reliable) or charging (SoC rising) or ignition flag.
            # speed/ignition bytes are unreliable at a standstill, so odometer is the primary signal.
            driving = last_odo is not None and odo is not None and odo > last_odo
            rising = last_soc is not None and soc is not None and soc > last_soc
            if driving or rising or st.get("ignition"):
                active_until = now + HOLD
            if soc is not None: last_soc = soc
            if odo is not None: last_odo = odo
        else:
            miss += 1
        if time.time() < active_until:
            delay = FAST
        elif miss >= OFFLINE_AFTER:                    # dark for a while (basement) -> back off
            delay = OFFLINE_SLOW
        else:
            delay = SLOW
        time.sleep(delay)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--loop", type=int, default=0, help="fixed seconds between polls; 0 = single")
    ap.add_argument("--adaptive", action="store_true", help="fast when awake, slow when parked")
    args = ap.parse_args()
    conn = sqlite3.connect(DB)
    conn.executescript(SCHEMA)
    if args.adaptive:
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
