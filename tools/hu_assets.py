"""Pull the head unit's own seat-climate art out of com.chery.systemui.apk into web/hu/.

The v2 Climate page draws the cabin seen from above with the head unit's own seat glows when
these files exist, and falls back to plain level buttons when they don't. The art is Chery's,
so it is NOT committed (web/hu/ is gitignored): run this against an APK pulled from your own
car's head unit (adb pull /system/priv-app/.../com.chery.systemui.apk).

    python tools/hu_assets.py path/to/com.chery.systemui.apk

Resource names are obfuscated in the APK's file table, so they are looked up by their real
names in resources.arsc (needs: pip install androguard pillow). Positions in v2 come from the
head unit's own HVAC seat layout: cabin 874 wide, seat glows 264x298 at (148,173) front-left,
(460,173) front-right, (152,517) rear-left, (460,517) rear-right, seat button 88x88 at (88,105)
inside each glow.
"""
import io
import os
import re
import sys

from androguard.core.apk import APK
from PIL import Image

try:
    from loguru import logger
    logger.remove()
except Exception:
    pass

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "web", "hu")

# output name -> drawable name in com.chery.systemui
WANT = {
    "cabin": "hvac_seat_car_model",        # left-hand drive
    "cabin-r": "hvac_seat_car_model_r",    # right-hand drive (J5 in Indonesia)
    **{f"vent-glow{i}": f"front_seat_ventilation_highlight{i}" for i in (1, 2, 3)},
    **{f"heat-glow{i}": f"front_seat_heat_highlight{i}" for i in (1, 2, 3)},
    **{f"vent{i}": f"seat_ventilation{i}" for i in range(4)},
    **{f"vent{i}-r": f"seat_ventilation{i}_r" for i in range(4)},
    **{f"heat{i}": f"seat_heat{i}" for i in range(4)},
    **{f"heat{i}-r": f"seat_heat{i}_r" for i in range(4)},
}


def main(apk_path):
    a = APK(apk_path)
    res = a.get_android_resources()
    pkg = res.get_packages_names()[0]
    pub = res.get_public_resources(pkg)
    pub = pub.decode() if isinstance(pub, bytes) else pub
    ids = {n: int(i, 16) for n, i in
           re.findall(r'<public type="drawable" name="([^"]+)" id="(0x[0-9a-f]+)"', pub)}
    os.makedirs(OUT, exist_ok=True)
    for out, name in WANT.items():
        rid = ids.get(name)
        if rid is None:
            print("missing", name)
            continue
        # one file per density/theme; for the cabin the two are the night and day renders
        files = sorted({str(v) for _c, v in res.get_resolved_res_configs(rid) if str(v).endswith((".png", ".webp"))})
        for i, f in enumerate(files):
            suffix = "" if len(files) == 1 else ("-dark", "-light")[i] if out.startswith("cabin") else ("", f"-{i}")[min(i, 1)]
            im = Image.open(io.BytesIO(a.get_file(f))).convert("RGBA")
            dst = os.path.join(OUT, f"{out}{suffix}.webp")
            im.save(dst, "WEBP", quality=88, method=6)
            print(f"{dst}  {im.size}  <- {name} ({f})")

    airflow(a, ids)


# A/C airflow view, from the head unit's EV climate screen (elac_main): the dashboard seen from
# the back seat on a 1440x1130 canvas, car render at y=163, and looping 20-frame airflow
# animations (100 ms a frame) at fixed spots. Saved at half size; each animation becomes one
# vertical sprite strip that v2 steps through with CSS.
FLOW = {
    "flow-face": "right_fan_{:05d}",          # centre vents, drawn mirrored on the left one
    "flow-door": "right_door_fan_{:05d}",     # door-side vents
    "flow-foot": "foot_right_{:05d}",         # footwell
    "flow-defog": "defog_{:05d}",             # windshield, left-hand drive
    "flow-defog-r": "defog_r_{:05d}",         # windshield, right-hand drive
}


def _imgs(a, res, ids, name):
    rid = ids.get(name)
    if rid is None:
        return []
    files = sorted({str(v) for _c, v in res.get_resolved_res_configs(rid) if str(v).endswith((".png", ".webp"))})
    return [Image.open(io.BytesIO(a.get_file(f))).convert("RGBA") for f in files]


def _half(im):
    return im.resize((im.width // 2, im.height // 2), Image.LANCZOS)


def airflow(a, ids):
    res = a.get_android_resources()
    for out, name in (("dash", "car_model_bev"), ("dash-r", "car_model_bev_r")):
        for im in _imgs(a, res, ids, name)[:1]:
            _half(im).save(os.path.join(OUT, out + ".webp"), "WEBP", quality=86, method=6)
            print(out, im.size)
    for k, im in enumerate(_imgs(a, res, ids, "wheel")[:2]):
        _half(im).save(os.path.join(OUT, ("wheel-dark", "wheel-light")[k] + ".webp"), "WEBP", quality=88, method=6)
    for out, pat in FLOW.items():
        frames = [im for i in range(20) for im in _imgs(a, res, ids, pat.format(i))[:1]]
        if len(frames) != 20:
            print("missing", pat)
            continue
        f0 = _half(frames[0])
        strip = Image.new("RGBA", (f0.width, f0.height * 20))
        for i, im in enumerate(frames):
            strip.paste(_half(im), (0, i * f0.height))
        strip.save(os.path.join(OUT, out + ".webp"), "WEBP", quality=80, method=6)
        print(out, f0.size, "x20")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
