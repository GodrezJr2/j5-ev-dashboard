"""Published, market-specific maintenance catalogue and due-service calculation.

Only schedules backed by a manufacturer document belong here. Never substitute
another market's interval or invent a price for an unsupported model.
"""

import json
from pathlib import Path

SOURCE = "https://omodajaecoo.com.my/themes/demo/assets/pdf/J5EV-Maintenance-Schedule.pdf"
PRICE_DATE = "2 Sep 2026"

# Official Malaysian manufacturer documents. Where a PDF has not yet been
# transcribed and checked, the API returns the source but no invented figures.
_OJ = "https://omodajaecoo.com.my/themes/demo/assets/pdf/"
_CHERY = "https://www.chery.my/wp-content/uploads/"
CATALOGUE = {
    "Jaecoo J5 EV": (SOURCE, "OMODA JAECOO"),
    "Jaecoo J5 2WD": (_OJ + "J5_Maintenance_Schedule.pdf", "OMODA JAECOO"),
    "Jaecoo J7 2WD": (_OJ + "J7-2WD-Maintenance-Schedule.pdf", "OMODA JAECOO"),
    "Jaecoo J7 AWD": (_OJ + "J7-AWD-Maintenance-Schedule.pdf", "OMODA JAECOO"),
    "Jaecoo J7 PHEV": (_OJ + "J7-PHEV-Maintenance-Schedule.pdf", "OMODA JAECOO"),
    "Jaecoo J8 2WD": (_OJ + "Jaecoo-J8-2WD-Maintenance-Schedule.pdf", "OMODA JAECOO"),
    "Jaecoo J8 AWD": (_OJ + "Jaecoo-J8-AWD-Maintenance-Schedule.pdf", "OMODA JAECOO"),
    "Omoda C9 2WD": (_OJ + "C9_2WD_Maintenance%20Schedule.pdf", "OMODA JAECOO"),
    "Omoda C9 AWD": (_OJ + "C9_AWD_Maintenance%20Schedule.pdf", "OMODA JAECOO"),
    "Omoda C9 PHEV": (_OJ + "Omoda_C9_PHEV_Maintenance_Schedule.pdf", "OMODA JAECOO"),
    "Chery Omoda E5": (_CHERY + "2026/05/Chery_Service_Maintenance_Schedule_E5_2026-2.pdf", "Chery"),
    "Chery Omoda 5": (_CHERY + "2025/08/Chery-Service-Maintenance-Schedule_OMODA-5_2025.pdf", "Chery"),
    "Chery O5": (_CHERY + "2025/09/Chery-Service-Maintenance-Schedule_O5_2025_compressed-1.pdf", "Chery"),
    "Chery Tiggo Cross HEV": (_CHERY + "2026/09/3Chery-Service-Maintenance-Schedule_TIGGO-CROSS_2026.pdf", "Chery"),
    "Chery Tiggo Cross 1.5T": (_CHERY + "2026/09/3Chery-Service-Maintenance-Schedule_TIGGO-CROSS_2026.pdf", "Chery"),
    "Chery Tiggo 7 Pro": (_CHERY + "2025/08/Chery-Service-Pricing-Guide_TIGGO-7-PRO_2025.pdf", "Chery"),
    "Chery Tiggo 7 PHEV": (_CHERY + "2026/08/Chery_Service_Maintenance_Schedule_TIGGO_7_PHEV_2026-3.pdf", "Chery"),
    "Chery Tiggo 8": (_CHERY + "2026/04/Chery-Service-Maintenance-Schedule_TIGGO-8-1.6T_2026-Updated-as-of-27-March-2026.pdf", "Chery"),
    "Chery Tiggo 8 Pro": (_CHERY + "2025/08/Chery-Service-Maintenance-Schedule_TIGGO-8-PRO_2025.pdf", "Chery"),
    "Chery Tiggo 8 PHEV": (_CHERY + "2026/08/Chery_Service_Maintenance_Schedule_TIGGO_8_PHEV_2026-3.pdf", "Chery"),
    "Chery Tiggo 9": (_CHERY + "2026/06/Chery-Service-Maintenance-Schedule_TIGGO-9_2026-260626.pdf", "Chery"),
    "iCAUR 03 RWD": ("https://icar-cloudformation-uploads-ap-southeast-1.s3.ap-southeast-1.amazonaws.com/flyers/Oct2026/iCAUR%2003%20RWD.pdf", "iCAUR"),
    "iCAUR 03 iWD": ("https://icar-cloudformation-uploads-ap-southeast-1.s3.ap-southeast-1.amazonaws.com/flyers/Oct2026/iCAUR%2003%20iWD.pdf", "iCAUR"),
    "iCAUR V23 RWD": ("https://icar-cloudformation-uploads-ap-southeast-1.s3.ap-southeast-1.amazonaws.com/flyers/Oct2026/V23%20RWD.pdf", "iCAUR"),
    "iCAUR V23 iWD": ("https://icar-cloudformation-uploads-ap-southeast-1.s3.ap-southeast-1.amazonaws.com/flyers/Oct2026/V23%20iWD.pdf", "iCAUR"),
}


def _item(name, price, required=True):
    return {"name": name, "price": price, "required": required}


def _stop(km, months, items, required_price=None):
    compulsory = round(sum(i["price"] for i in items if i["required"]), 2)
    return {"km": km, "months": months, "items": items,
            "required_price": compulsory if required_price is None else required_price,
            "with_recommended_price": round(sum(i["price"] for i in items), 2)}


def _j5_ev_stops():
    stops = []
    for index, km in enumerate((1000, 20000, 40000, 60000, 80000, 100000,
                                120000, 140000, 160000, 180000, 200000)):
        months = 1 if index == 0 else index * 12
        major = index > 0 and index % 2 == 0
        items = []
        if index:
            if major:
                items.extend((
                    {"name": "Drive motor oil (1 L)", "price": 200.0, "required": True},
                    {"name": "Brake fluid (1 L)", "price": 78.0, "required": True},
                    {"name": "Coolant (10.7 L)", "price": 425.4, "required": True},
                ))
            items.extend((
                {"name": "A/C filter", "price": 135.3, "required": True},
                {"name": "Labour", "price": 100.0 if major else 10.0,
                 "required": True},
                {"name": "Wiper blades (R & L)", "price": 196.4,
                 "required": False},
            ))
        stops.append(_stop(km, months, items))
    return stops


def _j5_2wd_stops():
    """Official June 2026 J5 2WD table, through 150,000 km."""
    stops = []
    labour = (100, 100, 150, 150, 100, 200, 100, 150, 150, 100, 100, 250, 100, 100, 150)
    for index in range(16):
        km = 1000 if index == 0 else index * 10000
        months = 1 if index == 0 else index * 6
        items = []
        if index:
            items.extend((_item("Engine oil SP 5W-30 (4.2 L)", 270),
                          _item("Engine oil filter", 34),
                          _item("Engine oil washer", 1.5)))
            if index % 3 == 0:
                items.append(_item("Spark plug", 167.4))
            if index % 4 == 0:
                items.append(_item("Brake fluid (1 L)", 78))
            if index % 6 == 0:
                items.extend((_item("Transmission oil (4 L)", 320),
                              _item("Oil drain plug washer", 3)))
            items.append(_item("Labour", labour[index - 1]))
            if index % 2 == 0:
                items.extend((_item("A/C filter", 135.3, False),
                              _item("Engine air filter", 98, False),
                              _item("Wiper blades (R & L)", 196.4, False)))
            if index % 4 == 0:
                items.append(_item("Coolant (3.2 L)", 141.8, False))
        stops.append(_stop(km, months, items))
    return stops


def _omoda_e5_stops():
    """Chery's May 2026 Omoda E5 table, through 200,000 km."""
    stops = []
    for index in range(11):
        km = 1000 if index == 0 else index * 20000
        months = 1 if index == 0 else index * 12
        items = []
        if index:
            if index % 3 == 0:
                items.extend((_item("Drive motor antifreeze (6 L)", 283.6),
                              _item("Brake fluid", 50),
                              _item("Transmission oil", 200)))
            items.extend((_item("A/C filter", 135.3),
                          _item("Labour", 200 if index % 3 == 0 else 100)))
            if index % 2 == 0:
                items.append(_item("Wiper blades (R & L)", 175.7, False))
            if index % 5 == 0:
                items.extend((_item("Front brake pads (R & L)", 593.3, False),
                              _item("Rear brake pads (R & L)", 542.2, False)))
        stops.append(_stop(km, months, items))
    return stops


def _icaur_stops(model):
    is_03 = "03" in model
    is_iwd = "iWD" in model
    labour = ([110, 80, 110, 120, 110, 80, 110, 120, 110, 80] if is_iwd else
              [70, 80, 70, 120, 70, 80, 70, 120, 70, 80]) if is_03 else (
              [140, 110, 140, 150, 140, 110, 140, 150, 140, 110] if is_iwd else
              [100, 110, 100, 150, 100, 110, 100, 150, 100, 110])
    stops = [_stop(5000, 3, [])]
    for index in range(1, 11):
        items = [_item("A/C filter", 101.5 if is_03 else 95.9)]
        if index % 2:
            items.append(_item(
                "Rear reducer oil (750 ml)" if is_03 and not is_iwd else
                "Front and rear reducer oil (1.5 L)" if not is_03 and is_iwd else
                "Rear reducer oil (800 ml)" if not is_03 else
                "Front and rear reducer oil",
                (400 if is_iwd else 200) if is_03 else (300 if is_iwd else 150)))
        else:
            items.append(_item("Brake fluid (850 ml)", 100))
        if index in (4, 8):
            items.append(_item("Coolant (2.5 L)" if is_03 else "Coolant (4 L)", 141.8))
        items.append(_item("Labour", labour[index - 1]))
        items.append(_item("Wiper blades (R & L)", 213.4 if is_03 else 203.2, False))
        if is_03:
            items.append(_item("Rear wiper blade", 114.2, False))
        stops.append(_stop(5000 + index * 20000, 3 + index * 12, items))
    return stops


def _oj_petrol_stops(model):
    """Official 22 June 2026 J7, J8 and C9 petrol tables, to 150,000 km."""
    j7 = "J7" in model
    j8 = "J8" in model
    awd = "AWD" in model
    labour = [100, 100, 150, 150, 100, 200 if not j8 else 150,
              100, 150, 150, 100, 100, 250 if not j8 else 200,
              100, 100, 150]
    if awd:
        labour[5] += 150 if not j8 else 50
        labour[11] += 150 if not j8 else 50
        if j8:
            labour[14] += 50
    stops = [_stop(1000, 1, [])]
    for index in range(1, 16):
        items = [_item("Engine oil 5W-30 (4.3 L)" if j7 else
                       "Engine oil 0W-20 (4 L)", 270 if j7 else 250),
                 _item("Engine oil filter", 34),
                 _item("Engine oil washer", 1.5)]
        if index % 3 == 0:
            items.append(_item("Spark plugs", 167.4 if j7 else 233.6))
        if index % 4 == 0:
            items.append(_item("Brake fluid (1 L)", 78))
        if index % 6 == 0:
            items.append(_item("Transmission oil", 580 if j7 else 812 if j8 else 696))
            items.append(_item("Oil drain plug", 38 if j7 else 120.1))
            if awd:
                items.extend((_item("Transfer fluid", 150),
                              _item("Rear final drive fluid", 100)))
        items.append(_item("Labour", labour[index - 1]))
        if index % 2 == 0:
            items.extend((_item("A/C filter", 135.3, False),
                          _item("Engine air filter", 101, False),
                          _item("Wiper blades (R & L)",
                                223.3 if j7 else 209.1 if j8 else 224.3,
                                False)))
        if index % 5 == 0:
            items.append(_item("Coolant (7.5 L)", 283.6, False))
        stops.append(_stop(index * 10000, index * 6, items))
    return stops


def _oj_phev_stops(model):
    """Official 22 June 2026 J7 and C9 PHEV tables."""
    j7 = "J7" in model
    stops = [_stop(1000, 1, [])]
    for index in range(1, 16 if not j7 else 11):
        km = index * 10000
        items = [_item("Engine oil (4.7 L)", 270),
                 _item("Engine oil filter", 34),
                 _item("Engine oil washer", 2.2)]
        spark = index % 3 == 0
        if spark:
            items.append(_item("Spark plugs", 308.4))
        major = index % 4 == 0
        if major:
            items.extend((_item("Brake fluid (1 L)", 78),
                          _item("Transmission oil", 399.2 if j7 else 499),
                          _item("Transmission washer / gasket", 4.4)))
            if not j7:
                items.append(_item("Rear drive motor fluid (1.5 L)", 400))
        labour = (200 if major else 150 if spark else 100) if j7 else (
            [90, 90, 130, 240, 90, 130, 90, 240, 130, 90,
             90, 280, 90, 90, 170][index - 1])
        items.append(_item("Labour", labour))
        if index % 2 == 0:
            items.extend((_item("A/C filter", 135.3, False),
                          _item("Engine air filter", 137.1, False),
                          _item("Wiper blades (R & L)", 223.3 if j7 else 224.3, False)))
        if major:
            items.extend((_item("Coolant", 567.2 if j7 else 283.6, False),
                          _item("Transmission filter", 68.6, False)))
        if spark:
            items.append(_item("Fuel filter", 29.5, False))
        stops.append(_stop(km, index * 6 if not j7 else index * 12, items))
    return stops


_STRUCTURED = {"Jaecoo J5 EV": (_j5_ev_stops, PRICE_DATE),
               "Jaecoo J5 2WD": (_j5_2wd_stops, "2026-06-22")}
_CHERY_DATA = json.loads((Path(__file__).with_name("maintenance_chery_my.json")).read_text())
for _name, _data in _CHERY_DATA.items():
    _STRUCTURED[_name] = (lambda data=_data: data["stops"], _data["price_date_label"])
for _name in CATALOGUE:
    if _name.startswith("iCAUR"):
        _STRUCTURED[_name] = (lambda name=_name: _icaur_stops(name), "23 Sep 2026")
    elif _name.startswith(("Jaecoo J7", "Jaecoo J8", "Omoda C9")):
        factory = _oj_phev_stops if "PHEV" in _name else _oj_petrol_stops
        _STRUCTURED[_name] = (lambda name=_name, build=factory: build(name), "22 Jun 2026")


def _match_model(model):
    name = model.lower().replace("-", " ").strip()
    if "icar" in name or "icaur" in name:
        variant = "iWD" if "iwd" in name else "RWD" if "rwd" in name else None
        series = "V23" if "v23" in name else "03" if "03" in name else None
        return f"iCAUR {series} {variant}" if series and variant else None
    if "j5" in name and ("ev" in name or "electric" in name):
        return "Jaecoo J5 EV"
    if "j5" in name:
        return "Jaecoo J5 2WD"
    for series in ("j7", "j8", "c9"):
        if series in name:
            prefix = "Omoda C9" if series == "c9" else f"Jaecoo {series.upper()}"
            variant = "PHEV" if "phev" in name else "AWD" if "awd" in name else (
                "2WD" if "2wd" in name or "rwd" in name else None)
            selected = f"{prefix} {variant}" if variant else None
            return selected if selected in CATALOGUE else None
    if "e5" in name:
        return "Chery Omoda E5"
    if "tiggo cross" in name:
        if "hev" in name or "hybrid" in name:
            return "Chery Tiggo Cross HEV"
        if "1.5" in name or "petrol" in name:
            return "Chery Tiggo Cross 1.5T"
        return None
    for key in CATALOGUE:
        if key.startswith("Chery ") and key[6:].lower() in name:
            return key
    candidates = [key for key in CATALOGUE if key.lower() in name]
    return max(candidates, key=len) if candidates else None


def brand_for(model):
    selected = model if model in CATALOGUE else _match_model(model)
    if selected:
        return CATALOGUE[selected][1]
    name = model.lower()
    if "icaur" in name or "icar" in name:
        return "iCAUR"
    if "jaecoo" in name or name.startswith("j5") or name.startswith("j7") or name.startswith("j8"):
        return "OMODA JAECOO"
    if "chery" in name or "tiggo" in name or "omoda" in name:
        return "Chery" if "chery" in name or "tiggo" in name else "OMODA JAECOO"
    return None


def timetable(country, model, odometer, completed_km=None):
    """The next upcoming milestone and any unconfirmed past milestones.

    A missed service remains visible as unconfirmed. Last-service odometer
    alone does not prove which manufacturer milestone was completed.
    """
    selected = model if model in CATALOGUE else _match_model(model)
    result = {"country": country, "model": model, "selected_model": selected,
              "available_models": list(CATALOGUE), "supported": False,
              "stops": [], "next": None}
    if brand_for(model):
        result["brand"] = brand_for(model)
    if country != "MY" or selected is None:
        return result
    source, brand = CATALOGUE[selected]
    result.update({"model": selected, "brand": brand, "currency": "MYR",
                   "source": source, "published": True,
                   "source_only": selected not in _STRUCTURED,
                   "rule": "whichever comes first: months or kilometres"})
    if selected not in _STRUCTURED:
        return result
    factory, price_date = _STRUCTURED[selected]
    stops = factory()
    completed = set(completed_km or [])
    next_stop = next((s for s in stops if s["km"] > odometer and
                      s["km"] not in completed), None)
    result.update({"supported": True, "price_date": price_date,
                   "stops": stops, "next": next_stop,
                   "past_unconfirmed": [s["km"] for s in stops if
                        s["km"] <= odometer and s["km"] not in completed],
                   "km_remaining": next_stop["km"] - odometer if next_stop else None})
    return result
