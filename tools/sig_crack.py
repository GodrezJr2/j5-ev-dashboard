import sys, base64, hashlib, hmac, itertools
from mitmproxy import io, http
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

path = r"F:\Project\Reverse Carlinko\capture\flows3.mitm"
tuples = []
with open(path, "rb") as f:
    for fl in io.FlowReader(f).stream():
        if not isinstance(fl, http.HTTPFlow):
            continue
        h = {k.lower(): v for k, v in fl.request.headers.items()}
        if "hzhjcl" not in h.get("host", "") or "signature" not in h:
            continue
        tuples.append({
            "method": fl.request.method,
            "path": fl.request.path.split("?")[0],
            "full": fl.request.path,
            "query": fl.request.path.split("?")[1] if "?" in fl.request.path else "",
            "ts": h.get("timestamp", ""),
            "token": h.get("token", ""),
            "vdata": h.get("v-data", ""),
            "sig": h.get("signature", ""),
            "body": fl.request.get_text(strict=False) or "",
            "ctype": h.get("content-type", ""),
        })

print(f"captured {len(tuples)} signed requests")
for t in tuples[:3]:
    print(f"\n{t['method']} {t['full']}")
    print(f"  ts={t['ts']} sig={t['sig']}")
    print(f"  token={t['token']}")
    print(f"  vdata={t['vdata'][:40]}... body={t['body'][:80]}")

# offline brute force: does sig == b64(SHA256(msg)) or b64(HMAC-SHA256(key,msg)) for some recipe?
if not tuples:
    sys.exit()
t = next((x for x in tuples if not x["body"]), tuples[0])  # prefer a no-body GET
target = t["sig"]

parts = {
    "ts": t["ts"], "token": t["token"], "vdata": t["vdata"],
    "path": t["path"], "full": t["full"], "query": t["query"],
    "method": t["method"], "body": t["body"], "": "",
}
seps = ["", "&", "|", "\n", "+", "_"]
keys = {"none": None, "token": t["token"], "vdata": t["vdata"], "ts": t["ts"], "empty": ""}
# try ordered combos of 2-4 components
names = ["ts", "token", "vdata", "path", "full", "body", "query", "method", ""]

def enc(s):
    return s.encode() if isinstance(s, str) else s

def check(msg, label):
    for kname, k in keys.items():
        if k is None:
            digests = {
                "sha256": hashlib.sha256(enc(msg)).digest(),
                "md5": hashlib.md5(enc(msg)).digest(),
                "sha1": hashlib.sha1(enc(msg)).digest(),
            }
        else:
            digests = {
                "hmac-sha256": hmac.new(enc(k), enc(msg), hashlib.sha256).digest(),
                "hmac-md5": hmac.new(enc(k), enc(msg), hashlib.md5).digest(),
            }
        for alg, dg in digests.items():
            for outenc in (base64.b64encode(dg).decode(),
                           base64.urlsafe_b64encode(dg).decode(),
                           dg.hex()):
                if outenc == target:
                    print(f"\n*** MATCH ***  alg={alg} key={kname} recipe={label}")
                    return True
    return False

print(f"\nbrute-forcing against: {target}")
found = False
for r in range(2, 5):
    for combo in itertools.permutations(names, r):
        for sep in seps:
            msg = sep.join(parts[c] for c in combo)
            if check(msg, sep.join(combo)):
                found = True
                break
        if found: break
    if found: break
if not found:
    print("no offline recipe matched (key is likely a hardcoded secret -> need Blutter/Frida)")
