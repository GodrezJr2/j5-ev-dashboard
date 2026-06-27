"""Speed calibration: show raw bytes 14-15 for recent frames so we can match
them against the real speedometer reading the user calls out."""
import sqlite3, os, time
DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "carlinko.db")
c = sqlite3.connect(DB)
rows = c.execute("SELECT ts,dt,raw FROM telemetry WHERE online=1 AND raw IS NOT NULL "
                 "ORDER BY ts DESC LIMIT 24").fetchall()[::-1]
print(f"now {time.strftime('%H:%M:%S')}")
print("time      raw(14:15)  b14 b15   /10    /20   *0.1kW   odo  range")
prev = None
for ts, dt, r in rows:
    b = bytes.fromhex(r)
    raw = int.from_bytes(b[14:16], "big")
    odo = int.from_bytes(b[18:21], "big"); rng = int.from_bytes(b[29:31], "big")
    spd = "moving" if raw else "PARK"
    print(f"{dt[11:]}  {raw:5d}      {b[14]:3d} {b[15]:3d}   {raw/10:5.1f}  {raw/20:5.1f}  {raw*0.1:5.1f}   {odo}  {rng}")
