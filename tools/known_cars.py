"""Per-car constants the telemetry never carries, keyed by CarLinko's model name.

CarLinko publishes the tyre formula in `vehicleControlConfig`, but *not* the battery capacity. So
`battery_kwh` can only come from the owner, from this table, or be a guess -- and guessing is the
problem: applying the reference car's 58.9 kWh pack to a PHEV's ~18 kWh one makes every kWh, cost,
efficiency and savings figure roughly 3x wrong, silently and without ever looking wrong.

Every row here is a value an owner confirmed against their own car's dashboard. Add yours with a
compatibility report: https://github.com/GodrezJr2/j5-ev-dashboard/issues/new?template=compatibility.md
"""
import re

CARS = {
    # key = the words that identify the model; see match() for how they're matched
    "jaecoo j5 ev": {"battery_kwh": 58.9, "wltp_kwh_100": 14.8, "chemistry": "lfp"},   # reference car (ID)
    "tiggo 8 phev": {"battery_kwh": 18.3, "tpms_scale": 1.779, "powertrain": "phev"},  # issue #1 (ZA)
    "tiggo 7 phev": {"battery_kwh": 18.3, "tpms_scale": 1.779, "powertrain": "phev",
                     "wltp_kwh_100": 19.68},                                           # issue #3 (MY)
    "tiggo 7 csh": {"battery_kwh": 18.3, "tpms_scale": 1.779, "powertrain": "phev",
                    "wltp_kwh_100": 19.68},  # Malaysia badges the same car "TIGGO 7 CSH" (#3)
    "omoda e5": {"battery_kwh": 61, "wltp_kwh_100": 15.5, "chemistry": "lfp"},   # issue #5 (UY)
}


def norm(s):
    """Model name -> lowercase words. CarLinko is inconsistent across regions ("JAECOO 5 EV",
    "Jaecoo J5 EV", "Chery Tiggo 8 PHEV 2025"), so compare on words, not on the whole string."""
    s = re.sub(r"[^a-z0-9]+", " ", (s or "").lower())
    return re.sub(r"\bj(\d)\b", r"\1", s).strip()          # "j5" and "5" are the same car


def match(table, model):
    """Value from `table` whose key words all appear in `model`, most specific key winning.
    Word-wise so "TIGGO 7 PHEV" and "Chery Tiggo 7 PHEV 2025" both hit, and "tiggo 8 phev"
    never matches a 7."""
    name = " " + norm(model) + " "
    if not name.strip():
        return None
    best = None
    for key, val in table.items():
        words = norm(key).split()
        if words and all(f" {w} " in name for w in words) and (best is None or len(words) > best[0]):
            best = (len(words), val)
    return best[1] if best else None
