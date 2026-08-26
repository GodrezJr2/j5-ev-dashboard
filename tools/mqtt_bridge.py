"""Home Assistant MQTT bridge: discovery, telemetry publish, named remote-control commands.

Runs inside the dashboard server process. Soft-depends on paho-mqtt — if enabled in creds
but the package is missing, logs a clear error and stays idle.
"""
from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
_DATA = os.environ.get("CARLINKO_DATA") or HERE

# Fallback if tools/control_opcodes.json is missing/corrupt. The shipped file is the source of truth.
DEFAULT_OPCODES = {
    "lock": "741000",
    "unlock": "741001",
    "acOn": "742401",
    "acOff": "742400",
    "winOpen": "741501",
    "winClose": "741500",
    "winVent": "741502",
    "roofOpen": "741A01",
    "roofClose": "741A00",
    "roofTilt": "741A02",
    "liftOpen": "741201",
    "find": "740100",
    "chgStop": "742701",
}

POLL_S = 2.5
HEARTBEAT_S = 60.0
ONLINE_AGE_MIN = 40.0
BATTERY_LOW_PCT = 20

try:
    import paho.mqtt.client as mqtt
    HAS_PAHO = True
except ImportError:
    mqtt = None
    HAS_PAHO = False


def opcodes_path():
    # Static protocol map lives next to the code (tools/), not in the mutable data volume.
    return os.path.join(HERE, "control_opcodes.json")


def load_opcodes():
    """Read tools/control_opcodes.json; fall back to DEFAULT_OPCODES if missing/corrupt."""
    out = dict(DEFAULT_OPCODES)
    path = opcodes_path()
    if not os.path.isfile(path):
        return out
    try:
        raw = json.load(open(path, encoding="utf-8"))
    except Exception:
        return out
    if not isinstance(raw, dict):
        return out
    for k, v in raw.items():
        if k.startswith("_"):
            continue
        if k not in DEFAULT_OPCODES:
            continue
        s = str(v or "").strip()
        if s and all(ch in "0123456789abcdefABCDEF" for ch in s) and len(s) <= 16:
            out[k] = s
    return out


def save_opcodes(mapping):
    """Merge validated remaps into tools/control_opcodes.json. Returns the effective map."""
    path = opcodes_path()
    existing = dict(DEFAULT_OPCODES)
    if os.path.isfile(path):
        try:
            raw = json.load(open(path, encoding="utf-8"))
            if isinstance(raw, dict):
                for k, v in raw.items():
                    if str(k).startswith("_") or k not in DEFAULT_OPCODES:
                        continue
                    s = str(v or "").strip()
                    if s:
                        existing[k] = s
        except Exception:
            pass
    clean = dict(existing)
    for k, v in (mapping or {}).items():
        if k.startswith("_") or k not in DEFAULT_OPCODES:
            continue
        s = str(v or "").strip()
        if not s:
            clean[k] = DEFAULT_OPCODES[k]
            continue
        if not all(ch in "0123456789abcdefABCDEF" for ch in s) or len(s) > 16:
            raise ValueError(f"invalid opcode for {k}")
        clean[k] = s
    with open(path, "w", encoding="utf-8") as f:
        json.dump(clean, f, indent=2, ensure_ascii=False)
        f.write("\n")
    return load_opcodes()


def _mqtt_cfg(raw=None):
    c = raw if isinstance(raw, dict) else {}
    return {
        "enabled": bool(c.get("enabled")),
        "host": (c.get("host") or "").strip(),
        "port": int(c.get("port") or 1883),
        "username": (c.get("username") or "").strip(),
        "password": c.get("password") if c.get("password") is not None else "",
        "tls": bool(c.get("tls")),
        "base_topic": (c.get("base_topic") or "j5").strip().strip("/") or "j5",
        "discovery_prefix": (c.get("discovery_prefix") or "homeassistant").strip().strip("/")
                            or "homeassistant",
    }


class MqttBridge:
    def __init__(self):
        self._lock = threading.RLock()
        self._cfg = _mqtt_cfg()
        self._client = None
        self._thread = None
        self._stop = threading.Event()
        self._connected = False
        self._last_error = None
        self._last_publish_ts = None
        self._discovery_sent = False
        self._last_payload = None
        self._last_pub_mono = 0.0
        self._prev_charge_state = None
        self._prev_battery = None
        self._battery_low_latched = False
        # Injected by server.py after import (avoids circular imports at module load).
        self.get_db_path = lambda: None
        self.decode = None
        self.control_caps = lambda: {}
        self.send_control = None
        self.get_vehicle = lambda: {}
        self.get_vehicle_id = lambda: ""

    def status(self):
        with self._lock:
            return {
                "enabled": self._cfg["enabled"],
                "connected": self._connected,
                "last_error": self._last_error,
                "last_publish_ts": self._last_publish_ts,
                "has_paho": HAS_PAHO,
            }

    def start(self, mqtt_creds=None):
        self.reload(mqtt_creds)

    def stop(self):
        self._stop.set()
        with self._lock:
            self._teardown_client()
        t = self._thread
        if t and t.is_alive() and t is not threading.current_thread():
            t.join(timeout=5)
        self._thread = None

    def reload(self, mqtt_creds=None):
        """Apply new config; restart client/loop if needed."""
        cfg = _mqtt_cfg(mqtt_creds)
        self._stop.set()
        with self._lock:
            self._teardown_client()
            self._cfg = cfg
            self._discovery_sent = False
            self._last_payload = None
        t = self._thread
        if t and t.is_alive() and t is not threading.current_thread():
            t.join(timeout=5)
        self._stop = threading.Event()
        self._thread = None
        if not cfg["enabled"]:
            self._connected = False
            self._last_error = None
            return
        if not HAS_PAHO:
            self._last_error = "paho-mqtt not installed (pip install paho-mqtt)"
            print("mqtt_bridge:", self._last_error, flush=True)
            return
        if not cfg["host"]:
            self._last_error = "mqtt.host is empty"
            print("mqtt_bridge:", self._last_error, flush=True)
            return
        self._thread = threading.Thread(target=self._run, name="mqtt-bridge", daemon=True)
        self._thread.start()

    def _teardown_client(self):
        c = self._client
        self._client = None
        self._connected = False
        if not c:
            return
        try:
            base = self._cfg.get("base_topic") or "j5"
            c.publish(f"{base}/availability", "offline", qos=0, retain=True)
        except Exception:
            pass
        try:
            c.loop_stop()
        except Exception:
            pass
        try:
            c.disconnect()
        except Exception:
            pass

    def _run(self):
        cfg = self._cfg
        try:
            client = self._make_client(cfg)
        except Exception as e:
            self._last_error = str(e)[:200]
            print("mqtt_bridge: connect setup failed:", self._last_error, flush=True)
            return
        with self._lock:
            self._client = client
        try:
            client.connect(cfg["host"], cfg["port"], keepalive=60)
            client.loop_start()
        except Exception as e:
            self._last_error = str(e)[:200]
            print("mqtt_bridge: connect failed:", self._last_error, flush=True)
            self._teardown_client()
            return

        while not self._stop.wait(POLL_S):
            try:
                self._tick()
            except Exception as e:
                self._last_error = str(e)[:200]
                print("mqtt_bridge: tick error:", self._last_error, flush=True)
                traceback.print_exc()
        self._teardown_client()

    def _make_client(self, cfg):
        # paho v1 vs v2 callback API
        try:
            client = mqtt.Client(
                mqtt.CallbackAPIVersion.VERSION1,
                client_id=f"carlinko-{cfg['base_topic']}",
                clean_session=True,
            )
        except Exception:
            client = mqtt.Client(client_id=f"carlinko-{cfg['base_topic']}", clean_session=True)
        if cfg["username"]:
            client.username_pw_set(cfg["username"], cfg["password"] or None)
        if cfg["tls"]:
            client.tls_set()
        base = cfg["base_topic"]
        client.will_set(f"{base}/availability", "offline", qos=0, retain=True)
        client.on_connect = self._on_connect
        client.on_disconnect = self._on_disconnect
        client.on_message = self._on_message
        return client

    def _on_connect(self, client, userdata, flags, rc, *args):
        ok = (rc == 0)
        self._connected = ok
        if not ok:
            self._last_error = f"MQTT connect rc={rc}"
            print("mqtt_bridge:", self._last_error, flush=True)
            return
        self._last_error = None
        base = self._cfg["base_topic"]
        # Subscribe all command topics under base/control/+/set and nested climate/covers.
        client.subscribe(f"{base}/control/#")
        client.publish(f"{base}/availability", "online", qos=0, retain=True)
        self._discovery_sent = False
        print("mqtt_bridge: connected to", self._cfg["host"], flush=True)

    def _on_disconnect(self, client, userdata, rc, *args):
        self._connected = False
        if rc != 0:
            self._last_error = f"MQTT disconnected rc={rc}"

    def _on_message(self, client, userdata, msg):
        try:
            topic = msg.topic or ""
            payload = (msg.payload or b"").decode("utf-8", "replace").strip()
            self._handle_command(topic, payload)
        except Exception as e:
            self._last_error = str(e)[:200]
            print("mqtt_bridge: command error:", self._last_error, flush=True)

    def _pub(self, topic, payload, retain=True):
        c = self._client
        if not c or not self._connected:
            return
        if not isinstance(payload, str):
            payload = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
        c.publish(topic, payload, qos=0, retain=retain)

    def _device_info(self):
        v = self.get_vehicle() or {}
        vid = str(self.get_vehicle_id() or v.get("plate") or "car")
        name = v.get("model") or v.get("plate") or "CarLinko EV"
        return {
            "identifiers": [f"carlinko_{vid}"],
            "name": name,
            "manufacturer": "CarLinko",
            "model": v.get("model") or "EV",
            "suggested_area": "Garage",
        }

    def _publish_discovery(self, caps):
        cfg = self._cfg
        pref = cfg["discovery_prefix"]
        base = cfg["base_topic"]
        avail = {"topic": f"{base}/availability"}
        device = self._device_info()
        uniq = device["identifiers"][0]

        def disc(component, object_id, body):
            body = dict(body)
            body["availability"] = [avail]
            body["device"] = device
            body.setdefault("unique_id", f"{uniq}_{object_id}")
            body.setdefault("object_id", object_id)
            self._pub(f"{pref}/{component}/{uniq}/{object_id}/config", body, retain=True)

        # Sensors
        disc("sensor", "battery", {
            "name": "Battery", "state_topic": f"{base}/sensor/battery",
            "unit_of_measurement": "%", "device_class": "battery", "state_class": "measurement",
        })
        disc("sensor", "range", {
            "name": "Range", "state_topic": f"{base}/sensor/range",
            "unit_of_measurement": "km", "icon": "mdi:map-marker-distance",
            "state_class": "measurement",
        })
        disc("sensor", "odometer", {
            "name": "Odometer", "state_topic": f"{base}/sensor/odometer",
            "unit_of_measurement": "km", "icon": "mdi:counter",
            "state_class": "total_increasing",
        })
        disc("sensor", "volt12", {
            "name": "12V Battery", "state_topic": f"{base}/sensor/volt12",
            "unit_of_measurement": "V", "device_class": "voltage", "state_class": "measurement",
        })
        disc("sensor", "charge_power", {
            "name": "Charge Power", "state_topic": f"{base}/sensor/charge_power",
            "unit_of_measurement": "kW", "device_class": "power", "state_class": "measurement",
        })
        disc("sensor", "consumption", {
            "name": "Consumption", "state_topic": f"{base}/sensor/consumption",
            "unit_of_measurement": "kWh/100km", "icon": "mdi:lightning-bolt",
            "state_class": "measurement",
        })
        disc("binary_sensor", "charging", {
            "name": "Charging", "state_topic": f"{base}/binary_sensor/charging",
            "payload_on": "ON", "payload_off": "OFF", "device_class": "battery_charging",
        })
        disc("binary_sensor", "online", {
            "name": "Online", "state_topic": f"{base}/binary_sensor/online",
            "payload_on": "ON", "payload_off": "OFF", "device_class": "connectivity",
        })

        caps = caps or {}
        if caps.get("lock"):
            disc("lock", "lock", {
                "name": "Lock",
                "state_topic": f"{base}/lock/state",
                "command_topic": f"{base}/control/lock/set",
                "payload_lock": "LOCK", "payload_unlock": "UNLOCK",
                "state_locked": "LOCKED", "state_unlocked": "UNLOCKED",
            })
        ac = caps.get("ac") or {}
        if ac.get("switch"):
            disc("climate", "climate", {
                "name": "Climate",
                "mode_command_topic": f"{base}/control/climate/set",
                "mode_state_topic": f"{base}/climate/mode",
                "modes": ["off", "cool"],
                "current_temperature_topic": f"{base}/climate/temperature",
                "temperature_unit": "C",
                "action_topic": f"{base}/climate/action",
            })
        win = caps.get("windows") or {}
        if win.get("open") or win.get("close") or win.get("vent"):
            disc("cover", "windows", {
                "name": "Windows",
                "state_topic": f"{base}/cover/windows/state",
                "command_topic": f"{base}/control/windows/set",
                "payload_open": "OPEN", "payload_close": "CLOSE", "payload_stop": "VENT",
                "state_open": "open", "state_closed": "closed",
                "device_class": "awning",
            })
        roof = caps.get("sunroof") or {}
        if roof.get("open") or roof.get("tilt"):
            disc("cover", "sunroof", {
                "name": "Sunroof",
                "state_topic": f"{base}/cover/sunroof/state",
                "command_topic": f"{base}/control/sunroof/set",
                "payload_open": "OPEN", "payload_close": "CLOSE", "payload_stop": "TILT",
                "state_open": "open", "state_closed": "closed",
                "device_class": "window",
            })
        if caps.get("liftgate") or caps.get("trunk"):
            disc("cover", "liftgate", {
                "name": "Liftgate",
                "state_topic": f"{base}/cover/liftgate/state",
                "command_topic": f"{base}/control/liftgate/set",
                "payload_open": "OPEN", "payload_close": "CLOSE",
                "state_open": "open", "state_closed": "closed",
                "device_class": "garage",
            })
        if caps.get("find"):
            disc("button", "find", {
                "name": "Find car",
                "command_topic": f"{base}/control/find/set",
                "payload_press": "PRESS",
            })
        if caps.get("charging"):
            disc("button", "charge_stop", {
                "name": "Stop charging",
                "command_topic": f"{base}/control/charge_stop/set",
                "payload_press": "PRESS",
            })
        self._discovery_sent = True

    def _read_latest(self):
        db = self.get_db_path()
        if not db or not os.path.exists(db) or not self.decode:
            return None
        conn = sqlite3.connect(db)
        try:
            row = conn.execute(
                "SELECT ts, raw FROM telemetry WHERE online=1 AND raw IS NOT NULL "
                "ORDER BY ts DESC LIMIT 1"
            ).fetchone()
        finally:
            conn.close()
        if not row:
            return None
        ts, raw = row
        return ts, self.decode(raw)

    def _tick(self):
        if not self._connected:
            return
        try:
            caps = self.control_caps() or {}
        except Exception:
            caps = {}
        if not self._discovery_sent:
            self._publish_discovery(caps)

        latest = self._read_latest()
        if not latest:
            base = self._cfg["base_topic"]
            self._pub(f"{base}/binary_sensor/online", "OFF")
            return
        ts, dec = latest
        age_min = (time.time() - ts) / 60.0
        online = age_min < ONLINE_AGE_MIN
        battery = dec.get("battery")
        cstate = dec.get("charge_state")
        charging = cstate == 1
        rate = dec.get("charge_power") if charging else 0
        if rate is None:
            rate = 0
        unlocked = bool(dec.get("unlocked"))
        ac_on = bool(dec.get("ac_on"))
        ac_temp = dec.get("ac_temp_c")
        temp_ok = isinstance(ac_temp, int) and 16 <= ac_temp <= 30
        windows_open = bool(dec.get("windows"))
        sunroof_open = bool(dec.get("sunroof_open"))
        trunk_open = bool(dec.get("trunk_open"))
        consumption = dec.get("consumption") or ""

        snap = {
            "battery": battery, "range": dec.get("range_km"), "odo": dec.get("odometer"),
            "volt12": dec.get("volt12"), "rate": rate, "consumption": consumption,
            "charging": charging, "online": online, "unlocked": unlocked, "ac_on": ac_on,
            "ac_temp": ac_temp if temp_ok else None, "windows": windows_open,
            "sunroof": sunroof_open, "trunk": trunk_open, "cstate": cstate,
        }
        now = time.monotonic()
        changed = snap != self._last_payload
        due = (now - self._last_pub_mono) >= HEARTBEAT_S
        if not changed and not due:
            return

        base = self._cfg["base_topic"]
        def n(v):
            return "" if v is None else str(v)

        self._pub(f"{base}/sensor/battery", n(battery))
        self._pub(f"{base}/sensor/range", n(dec.get("range_km")))
        self._pub(f"{base}/sensor/odometer", n(dec.get("odometer")))
        self._pub(f"{base}/sensor/volt12", n(dec.get("volt12")))
        self._pub(f"{base}/sensor/charge_power", n(rate))
        self._pub(f"{base}/sensor/consumption", n(consumption) if consumption else "")
        self._pub(f"{base}/binary_sensor/charging", "ON" if charging else "OFF")
        self._pub(f"{base}/binary_sensor/online", "ON" if online else "OFF")
        self._pub(f"{base}/lock/state", "UNLOCKED" if unlocked else "LOCKED")
        self._pub(f"{base}/climate/mode", "cool" if ac_on else "off")
        self._pub(f"{base}/climate/action", "cooling" if ac_on else "off")
        self._pub(f"{base}/climate/temperature", n(ac_temp) if temp_ok else "")
        self._pub(f"{base}/cover/windows/state", "open" if windows_open else "closed")
        self._pub(f"{base}/cover/sunroof/state", "open" if sunroof_open else "closed")
        self._pub(f"{base}/cover/liftgate/state", "open" if trunk_open else "closed")
        self._pub(f"{base}/availability", "online" if online else "offline", retain=True)

        # Edge events (not retained)
        if self._prev_charge_state == 1 and cstate == 2:
            self._pub(f"{base}/event/charge_complete",
                      {"battery": battery, "ts": int(time.time())}, retain=False)
        if battery is not None:
            if battery < BATTERY_LOW_PCT and not self._battery_low_latched:
                self._pub(f"{base}/event/battery_low",
                          {"battery": battery, "ts": int(time.time())}, retain=False)
                self._battery_low_latched = True
            elif battery >= BATTERY_LOW_PCT + 5:
                self._battery_low_latched = False

        self._prev_charge_state = cstate
        self._prev_battery = battery
        self._last_payload = snap
        self._last_pub_mono = now
        self._last_publish_ts = int(time.time())

    def _fire_action(self, action_key):
        """Init 77 then fire mapped opcode. Returns result dict."""
        if not self.send_control:
            return {"ok": False, "error": "send_control not wired"}
        ops = load_opcodes()
        code = ops.get(action_key)
        if not code:
            return {"ok": False, "error": f"no opcode for {action_key}"}
        init = self.send_control("77", 20)
        time.sleep(0.6)
        d = self.send_control(code, 20)
        ok = str(d.get("code")) == "0000"
        return {"ok": ok, "action": action_key, "opcode": code,
                "code": d.get("code"), "msg": d.get("msg"), "init": init.get("code"),
                "ts": int(time.time())}

    def _ack(self, result):
        base = self._cfg["base_topic"]
        self._pub(f"{base}/control/result", result, retain=False)

    def _handle_command(self, topic, payload):
        base = self._cfg["base_topic"]
        prefix = f"{base}/control/"
        if not topic.startswith(prefix) or not topic.endswith("/set"):
            return
        mid = topic[len(prefix):-len("/set")]  # e.g. lock, climate, windows, charge_stop
        pl = payload.upper()
        action = None

        if mid == "lock":
            if pl == "LOCK":
                action = "lock"
            elif pl == "UNLOCK":
                action = "unlock"
        elif mid == "climate":
            # HA may send mode string or JSON {"mode":"cool"|"off",...}
            mode = pl
            if payload.startswith("{"):
                try:
                    mode = str(json.loads(payload).get("mode") or "").upper()
                except Exception:
                    mode = pl
            if mode in ("OFF", "0"):
                action = "acOff"
            elif mode in ("COOL", "HEAT", "AUTO", "ON"):
                action = "acOn"
        elif mid == "windows":
            if pl == "OPEN":
                action = "winOpen"
            elif pl == "CLOSE":
                action = "winClose"
            elif pl in ("VENT", "STOP"):
                action = "winVent"
        elif mid == "sunroof":
            if pl == "OPEN":
                action = "roofOpen"
            elif pl == "CLOSE":
                action = "roofClose"
            elif pl in ("TILT", "STOP"):
                action = "roofTilt"
        elif mid == "liftgate":
            if pl == "OPEN":
                action = "liftOpen"
            # CLOSE not mapped distinctly in CTRL_ACTIONS; ignore
        elif mid == "find":
            if pl in ("PRESS", "ON", "1"):
                action = "find"
        elif mid == "charge_stop":
            if pl in ("PRESS", "ON", "1"):
                action = "chgStop"

        if not action:
            self._ack({"ok": False, "error": "unknown command", "topic": topic, "payload": payload})
            return

        # Capability gate
        try:
            caps = self.control_caps() or {}
        except Exception:
            caps = {}
        if not self._action_allowed(action, caps):
            self._ack({"ok": False, "error": "not supported by this car", "action": action})
            return

        result = self._fire_action(action)
        self._ack(result)

    @staticmethod
    def _action_allowed(action, caps):
        if action in ("lock", "unlock"):
            return bool(caps.get("lock"))
        if action in ("acOn", "acOff"):
            return bool((caps.get("ac") or {}).get("switch"))
        if action == "winOpen":
            return bool((caps.get("windows") or {}).get("open"))
        if action == "winClose":
            return bool((caps.get("windows") or {}).get("close"))
        if action == "winVent":
            return bool((caps.get("windows") or {}).get("vent"))
        if action == "roofOpen":
            return bool((caps.get("sunroof") or {}).get("open"))
        if action == "roofClose":
            return bool((caps.get("sunroof") or {}).get("open"))
        if action == "roofTilt":
            return bool((caps.get("sunroof") or {}).get("tilt"))
        if action == "liftOpen":
            return bool(caps.get("liftgate") or caps.get("trunk"))
        if action == "find":
            return bool(caps.get("find"))
        if action == "chgStop":
            return bool(caps.get("charging"))
        return False


# Singleton used by server.py
bridge = MqttBridge()
