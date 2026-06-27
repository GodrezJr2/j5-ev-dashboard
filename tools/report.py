"""Report from carlinko.db: km driven (daily/weekly/monthly) + charge sessions + latest TPMS.
Odometer + charge detection depend on offsets confirmed from real driving/charging frames;
until then km uses odo_guess deltas and charging detection is a placeholder."""
import sys, os, sqlite3, time
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DB = os.path.join(os.path.dirname(__file__), "..", "carlinko.db")

def main():
    if not os.path.exists(DB):
        print("no db yet"); return
    conn = sqlite3.connect(DB)
    rows = conn.execute(
        "SELECT ts,dt,battery,range_km,odo_guess,tyre_raw,online FROM telemetry "
        "WHERE online=1 ORDER BY ts").fetchall()
    print(f"frames with data: {len(rows)}")
    if not rows:
        print("waiting for first online frame (drive/charge the car so the cloud has fresh data)")
        return

    # latest snapshot + TPMS
    ts, dt, batt, rng, odo, tyre, _ = rows[-1]
    print(f"\nlatest @ {dt}: battery={batt}%  range={rng}km  odo?={odo}")
    if tyre:
        b = bytes.fromhex(tyre)
        psi  = [None if x == 0xFF else round(x*1.373*0.145, 1) for x in b[:4]]
        temp = [None if x == 0xFF else round(x*0.65-40, 1) for x in b[4:8]]
        labels = ["FL", "FR", "RL", "RR"]
        print("  TPMS:", ", ".join(f"{l}={p}psi/{t}C" for l, p, t in zip(labels, psi, temp)))
        if all(p is None for p in psi):
            print("  (tyres FF = parked; drive to get live PSI)")

    # km by day from odo_guess deltas
    def bucket(fmt):
        agg = {}
        for ts, dt, batt, rng, odo, tyre, _ in rows:
            if odo is None: continue
            k = time.strftime(fmt, time.localtime(ts))
            lo, hi = agg.get(k, (odo, odo))
            agg[k] = (min(lo, odo), max(hi, odo))
        return {k: hi-lo for k, (lo, hi) in agg.items()}

    for name, fmt in [("DAILY", "%Y-%m-%d"), ("WEEKLY", "%Y-W%W"), ("MONTHLY", "%Y-%m")]:
        b = bucket(fmt)
        print(f"\n{name} km (odo_guess delta, unvalidated):")
        for k in sorted(b):
            print(f"  {k}: {b[k]} km")

if __name__ == "__main__":
    main()
