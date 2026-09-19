#!/usr/bin/env python3
"""Watch the door bitmask change in real time, to pin down which bit is which corner.

Byte 2 of the telemetry blob is a per-door bitmask. That much is certain: all four bits fire
independently on the J5 and all fifteen combinations appear in the logs. What is NOT certain is
which bit means which physical corner -- the labels in docs/api-map.md were live-tested on an
Omoda E5 (issue #5) and inherited here without being cross-checked on this car.

This script closes that gap. Run it, walk to the car, and open one door at a time. It prints every
change to the mask with a timestamp, so the corner you just opened can be matched to the bit that
just flipped.

    python tools/door_probe.py                        # uses the Tailscale address
    python tools/door_probe.py http://127.0.0.1:8088  # or run it on the server itself

Polling /api/summary is a pure DB read -- it does not open a second CarLinko socket, so it will
not fight the streaming logger. Do not point this at /api/refresh.
"""
import json
import sys
import time
import urllib.request

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://100.112.64.99:8088").rstrip("/")
INTERVAL = 2.0

BITS = [
    (1, "bit0  value 1", "labelled driver"),
    (2, "bit1  value 2", "labelled passenger"),
    (4, "bit2  value 4", "labelled rear-driver"),
    (8, "bit3  value 8", "labelled rear-passenger"),
]


def decode(mask):
    if mask is None:
        return "unknown"
    on = [name for bit, name, _ in BITS if mask & bit]
    return ", ".join(on) if on else "all closed"


def main():
    print("Watching %s/api/summary every %.0fs" % (BASE, INTERVAL))
    print("Open ONE door at a time and note the order. Ctrl+C to stop.\n")
    print("%-21s %-6s %-6s %s" % ("time", "mask", "bits", "doors reported open"))
    print("-" * 78)

    last = object()          # sentinel so the first reading always prints
    t0 = time.time()
    while True:
        try:
            with urllib.request.urlopen(BASE + "/api/summary", timeout=10) as r:
                d = json.load(r)
        except Exception as e:
            print("%-21s  poll failed: %s" % (time.strftime("%H:%M:%S"), e))
            time.sleep(INTERVAL)
            continue

        mask = d.get("doors")
        if mask != last:
            stamp = time.strftime("%Y-%m-%d %H:%M:%S")
            bits = "----" if mask is None else format(mask & 15, "04b")
            marker = "" if last is object() else "   <-- CHANGED"
            print("%-21s %-6s %-6s %s%s" % (stamp, mask, bits, decode(mask), marker))
            last = mask

        # A heartbeat every 30s, so a quiet console is visibly "still watching" rather than hung.
        if int(time.time() - t0) % 30 == 0:
            print("%-21s (watching, mask still %s)" % (time.strftime("%H:%M:%S"), mask))
            time.sleep(1)

        time.sleep(INTERVAL)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nstopped")
