import io as _io
from mitmproxy import io, http

path = r"F:\Project\Reverse Carlinko\capture\flows.mitm"
out_path = r"F:\Project\Reverse Carlinko\capture\api_dump.txt"
SKIP = ("gstatic.com", "google.com", "googleapis.com", "googleapis", "gvt1", "gvt2")
flows = []
with open(path, "rb") as f:
    reader = io.FlowReader(f)
    try:
        for fl in reader.stream():
            if isinstance(fl, http.HTTPFlow):
                flows.append(fl)
    except Exception as e:
        flows_err = repr(e)

lines = []
def w(s=""):
    lines.append(s)

for fl in flows:
    req = fl.request
    if any(s in req.host for s in SKIP):
        continue
    host_hdr = req.headers.get("host", req.host)
    w("\n#### {} https://{}{}".format(req.method, host_hdr, req.path))
    w("  ip: {}".format(req.host))
    for k, v in req.headers.items():
        w("  H> {}: {}".format(k, v))
    body = req.get_text(strict=False) or ""
    if body:
        w("  REQ[{}]> {}".format(len(body), body[:3000]))
    if fl.response:
        w("  << {} {}".format(fl.response.status_code,
                              fl.response.headers.get("content-type", "")))
        rb = fl.response.get_text(strict=False) or ""
        if rb:
            w("  RESP[{}]> {}".format(len(rb), rb[:3000]))
    else:
        w("  << (no response / tunnel only)")

with open(out_path, "w", encoding="utf-8") as o:
    o.write("\n".join(lines))
print("wrote", out_path, "flows:", len(flows))
