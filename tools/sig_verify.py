import sys, os, base64, hashlib, hmac, json, itertools
from urllib.parse import parse_qsl
from mitmproxy import io, http
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Signing key loaded from creds.json (extract from your own app capture — see README). Capture path = argv[1].
_HERE = os.path.dirname(os.path.abspath(__file__))
try: _C = json.load(open(os.path.join(_HERE, "creds.json")))
except Exception: _C = {}
KEY = (_C.get("sign_key") or "").encode()
path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(_HERE, "..", "capture", "flows.mitm")

def sign(params):
    # values -> str, sort by key, jsonEncode (Dart style: no spaces), HMAC-SHA256, base64
    m = {k: ("" if v is None else str(v)) for k, v in params.items()}
    ordered = {k: m[k] for k in sorted(m.keys())}
    msg = json.dumps(ordered, separators=(",", ":"), ensure_ascii=False).encode()
    return base64.b64encode(hmac.new(KEY, msg, hashlib.sha256).digest()).decode()

tuples = []
with open(path, "rb") as f:
    for fl in io.FlowReader(f).stream():
        if not isinstance(fl, http.HTTPFlow):
            continue
        h = {k.lower(): v for k, v in fl.request.headers.items()}
        if "hzhjcl" not in h.get("host", "") or "signature" not in h:
            continue
        q = dict(parse_qsl(fl.request.path.split("?", 1)[1])) if "?" in fl.request.path else {}
        body = fl.request.get_text(strict=False) or ""
        bj = {}
        if body.strip().startswith("{"):
            try: bj = json.loads(body)
            except Exception: pass
        tuples.append({"path": fl.request.path.split("?")[0], "q": q, "body": bj,
                       "ts": h.get("timestamp",""), "token": h.get("token",""),
                       "vdata": h.get("v-data",""), "sig": h["signature"], "method": fl.request.method})

print(f"{len(tuples)} signed requests\n")
# candidate param-set recipes to test against the real signature
def recipes(t):
    base = {}
    base.update(t["q"]); base.update(t["body"])
    yield "params", dict(base)
    yield "params+ts", {**base, "timestamp": t["ts"]}
    yield "params+ts+token", {**base, "timestamp": t["ts"], "token": t["token"]}
    yield "ts", {"timestamp": t["ts"]}
    yield "ts+token", {"timestamp": t["ts"], "token": t["token"]}
    yield "params+token", {**base, "token": t["token"]}

winner = None
for t in tuples:
    for name, params in recipes(t):
        if sign(params) == t["sig"]:
            print(f"*** MATCH on {t['method']} {t['path']}  recipe='{name}'  params={params}")
            winner = name
            break
    else:
        continue
    break

if winner:
    # confirm the winning recipe across ALL captured requests
    ok = 0
    for t in tuples:
        base = {}; base.update(t["q"]); base.update(t["body"])
        if winner == "params": p = dict(base)
        elif winner == "params+ts": p = {**base, "timestamp": t["ts"]}
        elif winner == "params+ts+token": p = {**base, "timestamp": t["ts"], "token": t["token"]}
        elif winner == "ts": p = {"timestamp": t["ts"]}
        elif winner == "ts+token": p = {"timestamp": t["ts"], "token": t["token"]}
        elif winner == "params+token": p = {**base, "token": t["token"]}
        match = sign(p) == t["sig"]
        ok += match
        print(("  OK " if match else "  XX ") + f"{t['method']} {t['path']}")
    print(f"\nrecipe '{winner}' matched {ok}/{len(tuples)}")
else:
    print("no recipe matched - inspect the interceptor for the exact param map")
