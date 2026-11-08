"""Head unit add-ons: find the car's head unit on the local network and install an add-on APK.

Talks the ADB wire protocol directly over TCP, so the laptop needs no adb tools. The Jaecoo J5
head unit runs adbd with ro.adb.secure=0 (no key prompt) once "Enable ADB" is on in its
engineering menu. If an adbd does ask for a key (an emulator, another head unit), the
`cryptography` package and ~/.android/adbkey are used when available.

Only fixed actions are exposed (identify, check, install a bundled add-on, start it). There is
no way to run an arbitrary command from the web page.
"""
import concurrent.futures
import hashlib
import ipaddress
import os
import re
import socket
import struct
import time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DIST = os.path.join(ROOT, "headunit", "dist")
PORT = 5555

CNXN, AUTH, OPEN, OKAY, CLSE, WRTE = 0x4E584E43, 0x48545541, 0x4E45504F, 0x59414B4F, 0x45534C43, 0x45545257
VERSION, MAXDATA = 0x01000001, 256 * 1024

VHAL = "android.hardware.automotive.vehicle@2.0::IVehicle/default"

# Add-ons this dashboard can install. Each APK lives in headunit/dist/.
ADDONS = {
    "climate-gesture": {
        "name": "Climate Gesture",
        "pkg": "id.jaylabb.climategesture",
        "apk": "climate-gesture.apk",
        "service": "id.jaylabb.climategesture/.GestureService",
        "open_action": "id.jaylabb.climategesture.OPEN_ADB",
        "log": "/data/data/id.jaylabb.climategesture/files/log.txt",
        # the A/C properties it writes must read back, or the head unit is not one we know
        "needs_props": [557847208, 557847225],
        "tested": "Jaecoo J5 EV, T13J-INTL 00.04.15",
    },
}


class AdbError(Exception):
    pass


class Adb:
    """Minimal ADB transport: CNXN/AUTH, shell commands, sync push."""

    def __init__(self, host, port=PORT, timeout=6.0):
        self.host = host
        self.s = socket.create_connection((host, port), timeout=timeout)
        self.s.settimeout(timeout)
        self.next_id = 1
        self.banner = ""
        self.maxdata = 4096

    def close(self):
        try:
            self.s.close()
        except OSError:
            pass

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()

    # ---- framing ----
    def _send(self, cmd, a0, a1, data=b""):
        hdr = struct.pack("<6I", cmd, a0, a1, len(data), sum(data) & 0xFFFFFFFF, cmd ^ 0xFFFFFFFF)
        self.s.sendall(hdr + data)

    def _recvn(self, n):
        buf = b""
        while len(buf) < n:
            chunk = self.s.recv(n - len(buf))
            if not chunk:
                raise AdbError("connection closed by the head unit")
            buf += chunk
        return buf

    def _read(self):
        cmd, a0, a1, ln, _sum, magic = struct.unpack("<6I", self._recvn(24))
        if magic != cmd ^ 0xFFFFFFFF:
            raise AdbError("not an ADB reply")
        return cmd, a0, a1, self._recvn(ln) if ln else b""

    # ---- handshake ----
    def connect(self):
        self._send(CNXN, VERSION, MAXDATA, b"host::\0")
        tried_sig = tried_pub = False
        while True:
            cmd, a0, a1, data = self._read()
            if cmd == CNXN:
                self.maxdata = min(a1 or 4096, MAXDATA)
                self.banner = data.rstrip(b"\0").decode(errors="replace")
                return self
            if cmd != AUTH or a0 != 1:
                raise AdbError("unexpected reply during connect")
            key = _load_key()
            if key is None:
                raise AdbError("this adbd asks for a key (ro.adb.secure=1), not a J5 in engineering ADB mode")
            if not tried_sig:
                tried_sig = True
                self._send(AUTH, 2, 0, _sign(key, data))
            elif not tried_pub:
                tried_pub = True
                self._send(AUTH, 3, 0, _pubkey(key) + b" j5-dashboard\0")
                self.s.settimeout(30)          # someone has to tap "Allow" on the screen
            else:
                raise AdbError("key refused")

    def props(self):
        """ro.product.* from the connect banner, e.g. device::ro.product.model=X;..."""
        out = {}
        for part in self.banner.split("::", 1)[-1].split(";"):
            if "=" in part:
                k, v = part.split("=", 1)
                out[k] = v
        return out

    # ---- streams ----
    def _open(self, dest):
        lid = self.next_id
        self.next_id += 1
        self._send(OPEN, lid, 0, dest.encode() + b"\0")
        while True:
            cmd, a0, a1, data = self._read()
            if a1 != lid:
                continue                       # late packet of an earlier stream
            if cmd == OKAY:
                return lid, a0
            if cmd == CLSE:
                raise AdbError("head unit refused " + dest.split(":")[0])

    def shell(self, command, timeout=20):
        lid, rid = self._open("shell:" + command)
        self.s.settimeout(timeout)
        out = b""
        while True:
            cmd, a0, a1, data = self._read()
            if a1 != lid:
                continue
            if cmd == WRTE:
                out += data
                self._send(OKAY, lid, a0)
            elif cmd == CLSE:
                self._send(CLSE, lid, a0)
                return out.decode(errors="replace")

    def push(self, data, remote, mode=0o644):
        lid, rid = self._open("sync:")

        def wrte(payload):
            self._send(WRTE, lid, rid, payload)
            while True:                        # wait for the ack before the next packet
                cmd, a0, a1, d = self._read()
                if a1 != lid:
                    continue
                if cmd == OKAY:
                    return
                if cmd == CLSE:
                    raise AdbError("push aborted by the head unit")

        spec = ("%s,%d" % (remote, mode)).encode()
        wrte(b"SEND" + struct.pack("<I", len(spec)) + spec)
        step = min(self.maxdata, 64 * 1024) - 8
        for i in range(0, len(data), step):
            chunk = data[i:i + step]
            wrte(b"DATA" + struct.pack("<I", len(chunk)) + chunk)
        wrte(b"DONE" + struct.pack("<I", int(time.time())))
        reply = b""
        while len(reply) < 8:
            cmd, a0, a1, d = self._read()
            if a1 != lid:
                continue
            if cmd == WRTE:
                reply += d
                self._send(OKAY, lid, a0)
            elif cmd == CLSE:
                break
        if not reply.startswith(b"OKAY"):
            raise AdbError("push failed: " + reply[8:].decode(errors="replace")[:120])
        try:
            self._send(WRTE, lid, rid, b"QUIT" + struct.pack("<I", 0))
            self._send(CLSE, lid, rid)
        except OSError:
            pass


# ---- optional key auth (emulators, secure adbd); the J5 does not need it ----
def _load_key():
    path = os.path.join(os.path.expanduser("~"), ".android", "adbkey")
    try:
        from cryptography.hazmat.primitives import serialization
        with open(path, "rb") as f:
            return serialization.load_pem_private_key(f.read(), password=None)
    except Exception:
        return None


def _sign(key, token):
    from cryptography.hazmat.primitives.asymmetric import padding, utils
    from cryptography.hazmat.primitives import hashes
    # adbd checks RSA_verify(NID_sha1, token): the 20-byte token is signed as if it were a SHA-1 digest
    return key.sign(token, padding.PKCS1v15(), utils.Prehashed(hashes.SHA1()))


def _pubkey(key):
    import base64
    n = key.public_key().public_numbers().n
    e = key.public_key().public_numbers().e
    r32 = 1 << 32
    n0inv = (-pow(n % r32, -1, r32)) % r32
    rr = pow(2, 4096, n)
    blob = struct.pack("<II", 64, n0inv) + n.to_bytes(256, "little") + rr.to_bytes(256, "little") + struct.pack("<I", e)
    return base64.b64encode(blob)


# ---- discovery ----
def _local_ipv4():
    ips = set()
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ips.add(info[4][0])
    except OSError:
        pass
    try:                                       # the address the default route would use
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))
        ips.add(s.getsockname()[0])
        s.close()
    except OSError:
        pass
    out = []
    for ip in ips:
        a = ipaddress.ip_address(ip)
        # private LANs and phone hotspots only; skip loopback, link-local and Tailscale's 100.64/10
        if a.is_private and not a.is_loopback and not a.is_link_local and not ip.startswith("100."):
            out.append(ip)
    return sorted(out)


def _port_open(ip, port=PORT, timeout=0.5):
    try:
        with socket.create_connection((ip, port), timeout=timeout):
            return True
    except OSError:
        return False


def networks():
    return list(dict.fromkeys(str(ipaddress.ip_network(ip + "/24", strict=False)) for ip in _local_ipv4()))


def scan(extra_ip=None):
    """Find adbd on this machine's /24 networks. Returns the networks scanned and the devices found."""
    nets, hosts = [], []
    for ip in _local_ipv4():
        net = ipaddress.ip_network(ip + "/24", strict=False)
        if str(net) in nets:
            continue
        nets.append(str(net))
        hosts += [str(h) for h in net.hosts() if str(h) != ip]
    if extra_ip:
        hosts.insert(0, extra_ip)
    with concurrent.futures.ThreadPoolExecutor(64) as ex:
        open_ = [h for h, ok in zip(hosts, ex.map(_port_open, hosts)) if ok]
    found = []
    for ip in dict.fromkeys(open_):
        try:
            with Adb(ip, timeout=4) as a:
                a.connect()
                p = a.props()
                found.append({"ip": ip, "model": p.get("ro.product.model", ""),
                              "device": p.get("ro.product.device", ""), "name": p.get("ro.product.name", "")})
        except Exception as e:
            found.append({"ip": ip, "error": str(e)[:120]})
    return {"networks": nets, "found": found}


def valid_ip(ip):
    try:
        a = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return a.version == 4 and a.is_private and not a.is_loopback


# ---- identify + install ----
_PROP_RE = re.compile(r"\.prop = (\d+).*?int32Values = \[1\]\{(-?\d+)\}")


def _root_prefix(a):
    uid = a.shell("id -u").strip()
    if uid == "0":
        return ""
    if "uid=0" in a.shell("su 0 id 2>&1"):
        return "su 0 "
    return None


def probe(ip, addon="climate-gesture"):
    """What the head unit is, whether we have root, and whether this add-on fits it."""
    spec = ADDONS[addon]
    with Adb(ip) as a:
        a.connect()
        p = a.props()
        info = {"ip": ip, "model": p.get("ro.product.model", ""), "device": p.get("ro.product.device", "")}
        info["build"] = a.shell("getprop ro.build.display.id").strip()
        info["android"] = a.shell("getprop ro.build.version.release").strip()
        info["fingerprint"] = a.shell("getprop ro.build.fingerprint").strip()
        pre = _root_prefix(a)
        info["root"] = pre is not None
        props = {}
        if pre is not None:
            out = a.shell(pre + "sh -c 'for p in %s; do lshal debug %s --get $p 2>&1; done'"
                          % (" ".join(map(str, spec["needs_props"])), VHAL))
            props = {int(k): int(v) for k, v in _PROP_RE.findall(out)}
        info["compatible"] = info["root"] and all(pid in props for pid in spec["needs_props"])
        ver = a.shell("dumpsys package %s 2>/dev/null | grep versionName | head -1" % spec["pkg"]).strip()
        info["installed"] = ver.split("=", 1)[1] if "=" in ver else None
        info["running"] = bool(a.shell("pidof %s" % spec["pkg"]).strip())
        return info


def apk_info(addon="climate-gesture"):
    path = os.path.join(DIST, ADDONS[addon]["apk"])
    if not os.path.exists(path):
        return None
    data = open(path, "rb").read()
    return {"path": path, "size": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def install(ip, addon="climate-gesture", force=False):
    """Push, install and start an add-on. Returns a list of (step, ok, detail)."""
    spec = ADDONS[addon]
    steps = []
    path = os.path.join(DIST, spec["apk"])
    if not os.path.exists(path):
        return [("apk", False, "headunit/dist/%s is missing on this server" % spec["apk"])]
    data = open(path, "rb").read()
    with Adb(ip, timeout=15) as a:
        a.connect()
        pre = _root_prefix(a)
        if pre is None:
            return [("root", False, "no root shell on this head unit")]
        if not force:
            out = a.shell(pre + "sh -c 'for p in %s; do lshal debug %s --get $p 2>&1; done'"
                          % (" ".join(map(str, spec["needs_props"])), VHAL))
            got = {int(k) for k, _ in _PROP_RE.findall(out)}
            if not all(pid in got for pid in spec["needs_props"]):
                return [("check", False, "the A/C properties this add-on uses do not read on this head unit")]
            steps.append(("check", True, "A/C properties read back, this is a head unit we know"))
        else:
            steps.append(("check", True, "skipped (forced)"))
        # an installed copy may have closed port 5555 to the network: ask it to keep it open while we work
        a.shell(pre + "am start-foreground-service -a %s -n %s >/dev/null 2>&1" % (spec["open_action"], spec["service"]))
        remote = "/data/local/tmp/%s" % spec["apk"]
        a.push(data, remote)
        steps.append(("upload", True, "%d KB" % (len(data) // 1024)))
        out = a.shell("pm install -r %s 2>&1; rm -f %s" % (remote, remote), timeout=90).strip()
        ok = "Success" in out
        steps.append(("install", ok, out.splitlines()[-1][:160] if out else ""))
        if not ok:
            return steps
        a.shell(pre + "appops set %s SYSTEM_ALERT_WINDOW allow" % spec["pkg"])
        out = a.shell(pre + "am start-foreground-service -a %s -n %s 2>&1" % (spec["open_action"], spec["service"])).strip()
        steps.append(("start", "Error" not in out, out[:160]))
        time.sleep(4)
        log = a.shell(pre + "tail -5 %s 2>/dev/null" % spec["log"]).strip()
        linked = "car link ok" in log and "not supported" not in log
        steps.append(("verify", linked, log[-400:] if log else "no log yet"))
    return steps
