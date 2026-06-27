"""Standalone CarLinko telemetry client.
Connects to the realtime WebSocket using only the session token (no request signing),
pulls the vehicle status blob, decodes known fields, saves raw frames."""
import sys, os, json, time
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import websocket  # websocket-client

# Instance values from creds.json; token from token.txt (both gitignored). See creds.example.json.
_HERE = os.path.dirname(os.path.abspath(__file__))
try: _C = json.load(open(os.path.join(_HERE, "creds.json")))
except Exception: _C = {}
_TOK = os.path.join(_HERE, "token.txt")
WS_URL  = f"ws://wss-cqr-{_C.get('region','sea')}.hzhjcl.com:4002/"
TOKEN   = open(_TOK).read().strip() if os.path.exists(_TOK) else ""
VEHICLE = str(_C.get("vehicle_id") or "")
SN      = _C.get("device_sn") or ""
OUT     = os.path.join(_HERE, "..", "capture", "telemetry.json")

def decode_blob(hexstr):
    """Decode known offsets of the action:6 status blob. Validated: battery, range.
    Tyre/odometer offsets still tentative (need an awake+driving frame)."""
    b = bytes.fromhex(hexstr)
    d = {"raw": hexstr, "len": len(b)}
    def psi(x):   return None if x == 0xFF else round(x * 1.373 * 0.145, 1)
    def temp(x):  return None if x == 0xFF else round(x * 0.65 - 40, 1)
    if len(b) > 30:
        d["battery_pct"] = b[28]                      # confirmed (=49)
        d["range_km"]    = int.from_bytes(b[29:31], "big")  # confirmed (=248)
    # tentative tyre block (the 0xFF run while parked) — 4 pressure + 4 temp
    if len(b) >= 53:
        tp = b[45:49]; tt = b[49:53]
        d["tyre_psi"]  = [psi(x) for x in tp]
        d["tyre_temp"] = [temp(x) for x in tt]
        d["tyre_raw"]  = (tp + tt).hex()
    return d

def main():
    ws = websocket.create_connection(
        WS_URL, timeout=20, suppress_origin=True,
        header=["User-Agent: Dart/3.10 (dart:io)"])
    ws.send(json.dumps({"action": 1, "data": {"token": TOKEN, "vehicleId": VEHICLE}}))
    print("login   <<", ws.recv())
    ws.send(json.dumps({"action": 6}))
    ws.send(json.dumps({"action": 0, "data": {"sn": SN}}))

    frames, blob = [], None
    ws.settimeout(8)
    t_end = time.time() + 10
    while time.time() < t_end:
        try:
            msg = ws.recv()
        except Exception:
            break
        frames.append(msg)
        try:
            j = json.loads(msg)
        except Exception:
            continue
        if j.get("action") == 6 and isinstance(j.get("data"), str):
            blob = j["data"]
    ws.close()

    print("\n=== raw frames ===")
    for f in frames:
        print("  ", f)
    if blob:
        dec = decode_blob(blob)
        print("\n=== decoded telemetry ===")
        print(json.dumps(dec, indent=2, ensure_ascii=False))
        with open(OUT, "w", encoding="utf-8") as o:
            json.dump({"ts": int(time.time()), "decoded": dec, "frames": frames}, o,
                      ensure_ascii=False, indent=2)
        print("\nsaved", OUT)
    else:
        print("\n(no action:6 blob this round — car may be offline/basement; cloud cache empty)")

if __name__ == "__main__":
    main()
