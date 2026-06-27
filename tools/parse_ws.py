from mitmproxy import io, http

path = r"F:\Project\Reverse Carlinko\capture\flows.mitm"
out = r"F:\Project\Reverse Carlinko\capture\ws_dump.txt"
lines = []
with open(path, "rb") as f:
    reader = io.FlowReader(f)
    try:
        for fl in reader.stream():
            if not isinstance(fl, http.HTTPFlow):
                continue
            ws = getattr(fl, "websocket", None)
            if not ws:
                continue
            lines.append("\n#### WS {} ({} messages)".format(fl.request.pretty_url, len(ws.messages)))
            for m in ws.messages:
                arrow = ">>" if m.from_client else "<<"
                try:
                    txt = m.content.decode("utf-8", "replace")
                except Exception:
                    txt = repr(m.content)
                lines.append("  {} [{}] {}".format(arrow, len(m.content), txt[:1500]))
    except Exception as e:
        lines.append("parse-stop: " + repr(e))

with open(out, "w", encoding="utf-8") as o:
    o.write("\n".join(lines) if lines else "(no websocket messages captured)")
print("wrote", out, "lines:", len(lines))
