"""Interactive setup — builds creds.json and auto-detects your vehicle.

You only need four things (the rest is fetched from the API for you):
  email, password         your CarLinko login
  sign_key, v_data        extracted once from your own app capture (see README → First-time capture)

Run:  python setup.py
"""
import os, json, getpass

HERE = os.path.dirname(os.path.abspath(__file__))
CREDS = os.path.join(os.environ.get("CARLINKO_DATA") or HERE, "creds.json")


def ask(label, cur, secret=False, optional=False):
    shown = ("set" if secret else cur) if cur else ""
    suffix = f" [{shown}]" if shown else (" (optional)" if optional else "")
    val = (getpass.getpass if secret else input)(f"{label}{suffix}: ").strip()
    return val or cur  # blank keeps the existing value


def main():
    c = {}
    if os.path.exists(CREDS):
        try:
            c = json.load(open(CREDS))
            print(f"Editing existing {CREDS} (press Enter to keep a value).\n")
        except Exception:
            pass

    print("=== CarLinko login (use a SECOND account linked to your car, not your daily one) ===")
    c["email"] = ask("Email", c.get("email"))
    c["password"] = ask("Password", c.get("password"), secret=True)
    c["region"] = ask("Region", c.get("region") or "sea") or "sea"

    print("\n=== Optional ===")
    c["gmaps_key"] = ask("Google Maps key (enables trip planner + SPKLU map)",
                         c.get("gmaps_key"), secret=True, optional=True)

    # write what we have first, so a later failure still saves progress
    json.dump(c, open(CREDS, "w"), indent=2)
    try:
        os.chmod(CREDS, 0o600)
    except Exception:
        pass

    if not (c.get("email") and c.get("password")):
        print("\nSaved creds.json, but email/password are incomplete — fill them, then re-run.")
        return

    print("\nLogging in…")
    import auth  # the signing key is bundled; reads creds.json for the account
    auth._C = auth.cfg()
    try:
        token = auth.login()
    except Exception as e:
        print(f"  login failed: {e}\n  Double-check email/password, then re-run.")
        return
    print(f"  ok — token saved to token.txt")

    print("Detecting your vehicle…")
    import requests
    h = auth.headers_for({}, token=token)
    try:
        data = requests.get(auth.api_base() + "/user/vehicle", headers=h, timeout=20).json().get("data")
        v = data[0] if isinstance(data, list) and data else (data if isinstance(data, dict) else {})
    except Exception as e:
        print(f"  couldn't read /user/vehicle ({e}) — fill vehicle_id/device_sn by hand if needed.")
        v = {}

    if v.get("vehicleId"):
        c["vehicle_id"] = str(v["vehicleId"])
        c["device_sn"] = str(v.get("deviceId") or c.get("device_sn") or "")
        c["vehicle"] = {
            "plate": v.get("licenseNumber") or "—",
            "model": v.get("model") or "EV",
            "vin": v.get("vin") or "—",
        }
        json.dump(c, open(CREDS, "w"), indent=2)
        try:
            os.chmod(CREDS, 0o600)
        except Exception:
            pass
        print(f"  found: {c['vehicle']['model']}  (plate hidden in the UI by default)")

    print("\nDone. Now run:")
    print("  python logger.py --loop 600    # record telemetry")
    print("  python server.py 8088          # dashboard on http://<host>:8088")


if __name__ == "__main__":
    main()
