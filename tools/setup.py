"""Interactive setup - builds creds.json and auto-detects your vehicle.

You only need four things (the rest is fetched from the API for you):
  email, password         your CarLinko login
  sign_key, v_data        extracted once from your own app capture (see README -> First-time capture)

Run:  python setup.py
"""
import os, sys, re, json, getpass

HERE = os.path.dirname(os.path.abspath(__file__))
CREDS = os.path.join(os.environ.get("CARLINKO_DATA") or HERE, "creds.json")


def _safe(s):
    """Windows consoles default to cp1252, which cannot encode a currency symbol like the euro sign.
    Printing one raises UnicodeEncodeError and would kill setup mid-run, so degrade instead."""
    enc = (sys.stdout.encoding or "utf-8")
    try:
        s.encode(enc)
        return s
    except (UnicodeEncodeError, LookupError):
        return s.encode(enc, "replace").decode(enc, "replace")


def say(s=""):
    print(_safe(s))


def ask(label, cur, secret=False, optional=False):
    shown = ("set" if secret else cur) if cur else ""
    suffix = f" [{shown}]" if shown else (" (optional)" if optional else "")
    val = (getpass.getpass if secret else input)(_safe(f"{label}{suffix}: ")).strip()
    return val or cur  # blank keeps the existing value


# Money/unit presets so a non-Indonesian user never has to hand-edit creds.json to get sane costs.
# Prices are a starting point, not gospel -- they move monthly, and setup lets you override each one.
COUNTRIES = {
    "id": {"label": "Indonesia", "tyre_unit": "psi",
           "currency": {"symbol": "Rp", "locale": "id-ID", "code": "IDR"},
           "tariff": 2540, "petrol_price": 16250, "petrol_kml": 12.0,
           "hint": "PLN SPKLU all-in ~Rp2,540/kWh | Pertamax ~Rp16,250/L (Jul 2026)"},
    "za": {"label": "South Africa", "tyre_unit": "bar",
           "currency": {"symbol": "R", "locale": "en-ZA", "code": "ZAR"},
           "tariff": 3.50, "petrol_price": 26.10, "petrol_kml": 12.0,
           "hint": "home charging ~R3.50/kWh (public DC is ~R7.00) | 95 unleaded inland ~R26.10/L, Jul 2026"},
    "gb": {"label": "United Kingdom", "tyre_unit": "psi",
           "currency": {"symbol": "£", "locale": "en-GB", "code": "GBP"},
           "tariff": 0.27, "petrol_price": 1.35, "petrol_kml": 12.0,
           "hint": "home rate ~£0.27/kWh | petrol ~£1.35/L"},
    "eu": {"label": "Eurozone", "tyre_unit": "bar",
           "currency": {"symbol": "€", "locale": "de-DE", "code": "EUR"},
           "tariff": 0.35, "petrol_price": 1.75, "petrol_kml": 12.0,
           "hint": "home rate ~€0.35/kWh | petrol ~€1.75/L"},
}


def ask_region(c):
    """Currency, charging tariff, petrol baseline and tyre unit -- every cost the dashboard shows
    depends on these. Buried in creds.json nobody finds them, so ask up front."""
    say("\n=== Money + units (drives every cost/saving on the dashboard) ===")
    say("  " + " | ".join(f"{k}={v['label']}" for k, v in COUNTRIES.items()) + " | other=enter by hand")
    cur_code = ((c.get("currency") or {}).get("code") or "").lower()
    guess = next((k for k, v in COUNTRIES.items() if v["currency"]["code"].lower() == cur_code), "id")
    pick = (ask("Country", guess) or guess).lower()

    if pick in COUNTRIES:
        p = COUNTRIES[pick]
        say(f"  {p['hint']}")
        c["currency"] = p["currency"]
        defaults = p
    else:                                   # unknown country -> ask for the currency itself
        cc = c.get("currency") or {}
        c["currency"] = {
            "symbol": ask("  Currency symbol (e.g. R, $, €)", cc.get("symbol") or "$"),
            "code":   (ask("  Currency code (e.g. ZAR, USD)", cc.get("code") or "USD") or "USD").upper(),
            "locale": ask("  Number locale (e.g. en-ZA, en-US)", cc.get("locale") or "en-US"),
        }
        defaults = {"tariff": c.get("tariff") or 0.30, "petrol_price": c.get("petrol_price") or 1.50,
                    "petrol_kml": c.get("petrol_kml") or 12.0, "tyre_unit": c.get("tyre_unit") or "psi"}

    sym = c["currency"]["symbol"]

    def num(label, key, dflt):
        raw = ask(label, str(c.get(key) if c.get(key) is not None else dflt))
        try:
            return float(raw)
        except (TypeError, ValueError):
            say(f"    '{raw}' isn't a number - keeping {dflt}")
            return float(dflt)

    c["tariff"] = num(f"  Charging tariff ({sym}/kWh)", "tariff", defaults["tariff"])
    c["petrol_price"] = num(f"  Petrol price ({sym}/litre, for the savings comparison)",
                            "petrol_price", defaults["petrol_price"])
    c["petrol_kml"] = num("  Petrol car economy (km/litre)", "petrol_kml", defaults["petrol_kml"])
    c.pop("tariff_idr", None)               # legacy IDR-only key; "tariff" supersedes it

    unit = (ask("  Tyre unit (psi / bar / kpa)", c.get("tyre_unit") or defaults["tyre_unit"]) or "psi").lower()
    c["tyre_unit"] = unit if unit in ("psi", "bar", "kpa") else "psi"
    return c


def learn_from_config(c, v):
    """CarLinko publishes the per-model constants this app used to hard-code. Read them off
    `vehicleControlConfig` so a new car configures itself instead of needing hand-calibration."""
    cfg = v.get("vehicleControlConfig")
    if isinstance(cfg, str):
        try:
            cfg = json.loads(cfg or "{}")
        except Exception:
            return
    if not isinstance(cfg, dict):
        return

    # Tyre scale. The platform states it outright, e.g. appKpaFormula = "data * 1.373" -- exactly
    # the number owners of direct-TPMS cars previously had to derive against their own dashboard.
    formula = str(cfg.get("appKpaFormula") or cfg.get("webTirePressureFormula") or "")
    m = re.search(r"data\s*\*\s*([0-9]*\.?[0-9]+)", formula)
    if m:
        scale = float(m.group(1))
        have = c.get("tpms_scale")
        if have is None:
            c["tpms_scale"] = scale
            say(f"  tyre scale from CarLinko: {scale} kPa per raw unit")
        elif abs(float(have) - scale) > 1e-9:
            say(f"  note: CarLinko says tyre scale is {scale}, your creds.json has {have} "
                f"- keeping yours (delete tpms_scale to use theirs)")

    # Powertrain. A BEV reports powerConsumption only; a plug-in hybrid reports both.
    fuel, power = bool(cfg.get("fuelConsumption")), bool(cfg.get("powerConsumption"))
    if fuel and power and not c.get("powertrain"):
        c["powertrain"] = "phev"
        say("  detected a plug-in hybrid - fuel readouts enabled")


def ask_battery(c, model):
    """Usable pack size. CarLinko never sends it, and it scales every kWh, cost, efficiency and
    savings figure on the dashboard -- so a car we don't recognise gets asked rather than quietly
    inheriting the reference car's 58.9 kWh, which on a PHEV is about 3x too big."""
    import known_cars
    known = known_cars.match(known_cars.CARS, model) or {}
    if c.get("battery_kwh"):
        return
    if known.get("battery_kwh"):
        c["battery_kwh"] = known["battery_kwh"]
        say(f"  usable battery {known['battery_kwh']} kWh (confirmed by another {model} owner)")
        return
    say("\n=== Battery ===")
    say("  Your car doesn't report its pack size, and we have no figure for this model. It scales")
    say("  every kWh, cost and efficiency number, so a wrong one is worse than none.")
    say("  Usable (net) capacity, not the gross brochure figure - a PHEV is typically 12-20 kWh.")
    raw = ask("  Usable battery (kWh, blank = skip)", "", optional=True)
    try:
        if raw:
            c["battery_kwh"] = float(raw)
    except ValueError:
        say(f"    '{raw}' isn't a number - skipping, set battery_kwh in creds.json later")


def main():
    c = {}
    if os.path.exists(CREDS):
        try:
            c = json.load(open(CREDS, encoding="utf-8"))
            print(f"Editing existing {CREDS} (press Enter to keep a value).\n")
        except Exception:
            pass

    print("=== CarLinko login (use a SECOND account linked to your car, not your daily one) ===")
    c["email"] = ask("Email", c.get("email"))
    c["password"] = ask("Password", c.get("password"), secret=True)
    c["region"] = ask("Region", c.get("region") or "sea") or "sea"

    ask_region(c)

    print("\n=== Optional ===")
    c["gmaps_key"] = ask("Google Maps key (enables trip planner + SPKLU map)",
                         c.get("gmaps_key"), secret=True, optional=True)

    # write what we have first, so a later failure still saves progress
    json.dump(c, open(CREDS, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    try:
        os.chmod(CREDS, 0o600)
    except Exception:
        pass

    if not (c.get("email") and c.get("password")):
        print("\nSaved creds.json, but email/password are incomplete - fill them, then re-run.")
        return

    print("\nLogging in...")
    import auth  # the signing key is bundled; reads creds.json for the account
    auth._C = auth.cfg()
    try:
        token = auth.login()
    except Exception as e:
        print(f"  login failed: {e}\n  Double-check email/password, then re-run.")
        return
    print(f"  ok - token saved to token.txt")

    print("Detecting your vehicle...")
    import requests
    h = auth.headers_for({}, token=token)
    try:
        data = requests.get(auth.api_base() + "/user/vehicle", headers=h, timeout=20).json().get("data")
        v = data[0] if isinstance(data, list) and data else (data if isinstance(data, dict) else {})
    except Exception as e:
        print(f"  couldn't read /user/vehicle ({e}) - fill vehicle_id/device_sn by hand if needed.")
        v = {}

    if v.get("vehicleId"):
        c["vehicle_id"] = str(v["vehicleId"])
        c["device_sn"] = str(v.get("deviceId") or c.get("device_sn") or "")
        c["vehicle"] = {
            "plate": v.get("licenseNumber") or "—",
            "model": v.get("model") or "EV",
            "vin": v.get("vin") or "—",
        }
        # CarLinko hosts a render of YOUR car (right model, right colour). Keep the front view so
        # the dashboard shows your actual car instead of the bundled J5. Server caches it locally.
        try:
            img = json.loads(v.get("vehicleImgConfig") or "{}")
            front = img.get("Front") or img.get("Side") or img.get("Top")
            if front:
                c["vehicle"]["img"] = front
                say("  found your car's own image from CarLinko")
        except Exception:
            pass
        learn_from_config(c, v)
        ask_battery(c, c["vehicle"]["model"])
        json.dump(c, open(CREDS, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
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
