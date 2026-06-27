import sqlite3, time, os
DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "carlinko.db")
c = sqlite3.connect(DB)
rows = c.execute("SELECT ts,dt,raw FROM telemetry WHERE online=1 AND raw IS NOT NULL "
                 "ORDER BY ts DESC LIMIT 8").fetchall()
rows = rows[::-1]
prev = None
for ts, dt, raw in rows:
    b = bytes.fromhex(raw)
    batt = b[28]; rng = int.from_bytes(b[29:31], "big")
    odo = int.from_bytes(b[18:21], "big"); volt = int.from_bytes(b[12:14], "big")*0.01
    tyre = b[44:52].hex()
    diff = ""
    if prev is not None:
        ch = [i for i in range(min(len(b), len(prev))) if b[i] != prev[i]]
        diff = "changed bytes: " + (",".join(map(str, ch)) if ch else "(none)")
    print(f"{dt}  batt={batt}% rng={rng} odo={odo} volt={volt:.2f} tyre={tyre}")
    if diff: print("   ", diff)
    prev = b
print("\nfull last blob:", rows[-1][2] if rows else "none")
