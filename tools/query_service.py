"""Query the cloud for the telematics SERVICE / subscription expiry on this vehicle."""
import sys, json, os
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import auth, requests

def get(path, params=None):
    token = open(auth.TOKEN_FILE).read().strip()
    h = auth.headers_for(params or {}, token=token)
    r = requests.get(auth.api_base() + path, headers=h, timeout=20)
    try:
        return r.json()
    except Exception:
        return {"_raw": r.text[:400], "_status": r.status_code}

veh = get("/user/vehicle")
data = (veh.get("data") or [{}])
v = data[0] if data else {}
print("=== /user/vehicle : time/service/expiry fields ===")
KEYS = ("time", "date", "expire", "expiry", "begin", "end", "valid", "service", "activ", "deadline", "due")
for k, val in v.items():
    if any(t in k.lower() for t in KEYS):
        print(f"  {k} = {val}")
print("  vehicleId =", v.get("vehicleId"), "deviceSn =", v.get("deviceSn") or v.get("deviceId"))

vid = v.get("vehicleId")
print("\n=== terminal config ===")
print(json.dumps(get(f"/user/vehicle/terminal/{vid}"), ensure_ascii=False)[:500])

# service package endpoints seen in the decompiled app (service_package_controller)
for p in [f"/user/service/package/{vid}", f"/user/servicePackage/{vid}",
          f"/user/vehicle/service/{vid}", f"/service/package/list",
          f"/user/device/manage/{vid}"]:
    print(f"\n=== try {p} ===")
    print(json.dumps(get(p), ensure_ascii=False)[:400])
