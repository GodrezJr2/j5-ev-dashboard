"""Find a power/current byte: which blob bytes vary during the drive window,
and how they track range/odo changes (power should swing while moving)."""
import sqlite3, os
DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "carlinko.db")
c = sqlite3.connect(DB)
# drive window today with dense frames
rows = c.execute("SELECT ts,dt,raw FROM telemetry WHERE online=1 AND raw IS NOT NULL "
                 "AND dt >= '2026-06-21 16:20:00' ORDER BY ts").fetchall()
blobs = [(dt, bytes.fromhex(r)) for ts, dt, r in rows]
print(f"{len(blobs)} frames in window")
if len(blobs) < 2:
    raise SystemExit
n = min(len(b) for _, b in blobs)
# variance per byte index
print("\nidx : distinct values across frames (only changing bytes)")
known = {3:"state",12:"v12hi",13:"v12lo",14:"?",15:"?",18:"odo0",19:"odo1",20:"odo2",
         28:"batt",29:"rng_hi",30:"rng_lo",31:"?",69:"?",71:"?"}
for i in range(n):
    vals = [b[i] for _, b in blobs]
    uniq = sorted(set(vals))
    if len(uniq) > 1:
        tag = known.get(i, "")
        print(f"  {i:3d} {tag:7s}: {[hex(v) for v in uniq]}")
print("\n=== per-frame: range, byte14,15,23,24,26,31,69,71 ===")
for dt, b in blobs:
    rng = int.from_bytes(b[29:31], "big")
    cells = " ".join(f"{i}={b[i]:02x}" for i in (14,15,23,24,26,31,69,71) if i < len(b))
    print(f"  {dt[11:]} rng={rng} batt={b[28]} {cells}")
