"""Find the car's own consumption value (dash shows 12.2 kWh/100km) in the blob.
Scan every byte and 16-bit window for values that map to ~12.2 at common scales."""
import sqlite3, os
DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "carlinko.db")
c = sqlite3.connect(DB)
ts, dt, raw = c.execute("SELECT ts,dt,raw FROM telemetry WHERE online=1 AND raw IS NOT NULL "
                        "ORDER BY ts DESC LIMIT 1").fetchone()
b = bytes.fromhex(raw)
print(f"latest {dt}  len={len(b)}")
print("hex:", raw)
TARGET = 12.2
def near(v, t, tol): return abs(v - t) <= tol
print("\n=== single bytes matching ~12.2 (×1, ×0.1) ===")
for i, x in enumerate(b):
    for sc, lbl in [(1, "x1"), (0.1, "x0.1")]:
        if near(x*sc, TARGET, 1.5):
            print(f"  byte[{i}]={x} (0x{x:02x}) {lbl} -> {x*sc:.1f}")
print("\n=== 16-bit BE windows matching ~12.2 (×0.1, ×0.01) ===")
for i in range(len(b)-1):
    v = int.from_bytes(b[i:i+2], "big")
    for sc, lbl in [(0.1, "x0.1"), (0.01, "x0.01")]:
        if near(v*sc, TARGET, 1.0):
            print(f"  u16[{i}:{i+2}]={v} (0x{v:04x}) {lbl} -> {v*sc:.2f}")
print("\n=== all bytes (idx=hex=dec) for manual scan ===")
print(" ".join(f"{i}:{x}" for i, x in enumerate(b)))
