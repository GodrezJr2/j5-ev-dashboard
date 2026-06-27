import socket, ssl, json, time, os
import websocket

# token from token.txt, vehicle id from creds.json (both gitignored).
_HERE = os.path.dirname(os.path.abspath(__file__))
try: _C = json.load(open(os.path.join(_HERE, "creds.json")))
except Exception: _C = {}
_TOK = os.path.join(_HERE, "token.txt")
TOKEN   = open(_TOK).read().strip() if os.path.exists(_TOK) else ""
VEHICLE = str(_C.get("vehicle_id") or "")
HOST = f"wss-cqr-{_C.get('region','sea')}.hzhjcl.com"
PORT = 4002

# 1) DNS + TCP reachability
try:
    ip = socket.gethostbyname(HOST)
    print("DNS", HOST, "->", ip)
except Exception as e:
    print("DNS FAIL", e); ip = None

if ip:
    for tgt in [(HOST, PORT), ("cqr-api-sea.hzhjcl.com", 443)]:
        try:
            t0 = time.time()
            s = socket.create_connection(tgt, timeout=8)
            print("TCP OK", tgt, round((time.time()-t0)*1000), "ms")
            s.close()
        except Exception as e:
            print("TCP FAIL", tgt, repr(e))

# 2) direct WS with Origin + trace
def try_ws(use_proxy):
    tag = "PROXY" if use_proxy else "DIRECT"
    try:
        kw = dict(timeout=20, header=["User-Agent: Dart/3.10 (dart:io)"],
                  suppress_origin=True)
        if use_proxy:
            kw.update(http_proxy_host="127.0.0.1", http_proxy_port=8083,
                      proxy_type="http")
        ws = websocket.create_connection("ws://%s:%d/" % (HOST, PORT), **kw)
        print(tag, "HANDSHAKE OK")
        ws.send(json.dumps({"action":1,"data":{"token":TOKEN,"vehicleId":VEHICLE}}))
        print(tag, "login <<", ws.recv())
        ws.send(json.dumps({"action":6}))
        ws.settimeout(8)
        for _ in range(3):
            try: print(tag, "<<", ws.recv())
            except Exception as e: print(tag, "(end)", e); break
        ws.close()
        return True
    except Exception as e:
        print(tag, "FAIL", repr(e))
        return False

if not try_ws(False):
    print("--- retry via mitmproxy ---")
    try_ws(True)
