#!/usr/bin/env python3
"""Verify the extended CarLinko endpoints against the live account.

Safe by default: exercises only the READ endpoints and prints the WRITE
previews (the exact body each writer would send, without sending). It never
fires a control opcode and never performs a write unless you ask.

    python3 tools/carlinko_ext_selftest.py            # reads + write previews
    python3 tools/carlinko_ext_selftest.py --raw      # also dump each response's data

Writes and control actuation are deliberately NOT exposed here — do those from
the dashboard once a read confirms the signing/param convention is right for
your region, so a bad guess can't POST to the car.
"""
import sys, json
sys.path.insert(0, __import__("os").path.dirname(__file__))
import carlinko_api as clx

RAW = "--raw" in sys.argv


def show(name, fn):
    try:
        r = fn()
    except Exception as e:
        print(f"  {name:16} ERROR  {e!r}")
        return
    ok = r.get("ok")
    code = r.get("code")
    mark = "ok " if ok else ("?? " if ok is None else "FAIL")
    note = ""
    if isinstance(r.get("data"), list):
        note = f"{len(r['data'])} rows"
    elif isinstance(r.get("data"), dict):
        note = f"{len(r['data'])} fields"
    print(f"  {name:16} [{mark}] code={code} {note}")
    if RAW and r.get("data") is not None:
        print("    data:", json.dumps(r["data"], ensure_ascii=False)[:400])


def main():
    vid, dsn = clx._ids()
    print(f"vehicle_id={vid or '(missing)'}  device_sn={dsn or '(missing)'}")
    if not vid:
        print("No vehicle_id in creds.json — run auth/login first."); return

    print("\nREADS (live):")
    for name, fn in [
        ("notice_unread",  clx.notice_unread),
        ("notifications",  lambda: clx.notifications(1, 5)),
        ("operation_log",  lambda: clx.operation_log(1, 5)),
        ("maintenance",    lambda: clx.maintenance(1, 5)),
        ("alert_config",   clx.alert_config),
        ("geofences",      lambda: clx.geofences(1, 5)),
        ("car_location",   clx.car_location),
    ]:
        show(name, fn)

    print("\nWRITE PREVIEWS (nothing sent):")
    print("  targetSoc   ->", json.dumps(clx.set_target_soc(80)["would_send"], ensure_ascii=False))
    print("  airDuration ->", json.dumps(clx.set_air_duration(15)["would_send"], ensure_ascii=False))
    print("  alert       ->", json.dumps(clx.set_alert("VEHICLE_ANOMALY", True)["would_send"], ensure_ascii=False))
    print("  travel      ->", json.dumps(clx.set_scheduled_travel(False, 7, 30)["would_send"], ensure_ascii=False))
    print("\nA read that returns code=0000 confirms the signing/param convention for your region.")
    print("A read with a non-0000 code = that endpoint's param/sign shape needs a tweak — "
          "capture one real request and compare.")


if __name__ == "__main__":
    main()
