import sys
from mitmproxy import io, http
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

path = r"F:\Project\Reverse Carlinko\capture\flows3.mitm"
tokens = []
login = []
with open(path, "rb") as f:
    for fl in io.FlowReader(f).stream():
        if not isinstance(fl, http.HTTPFlow):
            continue
        host = fl.request.headers.get("host", fl.request.host)
        if "hzhjcl" not in host:
            continue
        tk = fl.request.headers.get("token")
        if tk:
            tokens.append(tk)
        p = fl.request.path.lower()
        if "login" in p or "auth" in p or "/pub/" in p and fl.request.method == "POST":
            body = fl.request.get_text(strict=False) or ""
            resp = fl.response.get_text(strict=False) if fl.response else ""
            login.append((fl.request.method, fl.request.path, dict(fl.request.headers), body, resp))

print("=== distinct tokens seen ===")
for t in sorted(set(tokens)):
    print(" ", t)
print("\n=== login/auth-ish requests ===")
for m, p, h, b, r in login:
    print(f"\n#### {m} {p}")
    for k in ("token","signature","timestamp","v-data","content-type"):
        if k in {kk.lower():kk for kk in h}:
            real = {kk.lower():kk for kk in h}[k]
            print(f"  {real}: {h[real]}")
    if b: print("  REQ>", b[:600])
    if r: print("  RESP>", r[:600])
