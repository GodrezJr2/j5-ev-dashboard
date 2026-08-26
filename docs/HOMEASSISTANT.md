# Home Assistant integration

> **Native integration exists:** [ha-carlinko](https://github.com/jebentancour/ha-carlinko) by
> [@jebentancour](https://github.com/jebentancour) is a read-only Home Assistant integration built
> on the same telemetry (no dashboard needed in the middle). The REST-sensor and MQTT paths below
> are the zero-extra-component alternatives that use this dashboard.

## Before you start
- Home Assistant must be able to reach the dashboard URL (same LAN, or both on Tailscale) **or**
  share an MQTT broker with the dashboard.
- If you set a **dashboard password** (public hosting), `/api/summary` is locked, so a plain REST
  sensor gets `401`. For Home Assistant REST, run the instance **un-gated on a private network /
  Tailscale** (recommended) so HA can read it directly. (A read-only API token for gated instances
  isn't built yet — open an issue if you want it.)
- MQTT works fine with a gated dashboard: the bridge runs server-side and talks to the broker.

## MQTT (recommended for push + controls)

The dashboard can publish telemetry with **MQTT discovery** and accept named remote-control
commands (lock, climate, covers, find, stop charging). Configure it in **Settings → MQTT**, or in
`creds.json`:

```json
"mqtt": {
  "enabled": true,
  "host": "homeassistant.local",
  "port": 1883,
  "username": "",
  "password": "",
  "tls": false,
  "base_topic": "j5",
  "discovery_prefix": "homeassistant"
}
```

Requires `paho-mqtt` (listed in `requirements.txt` — installed by `install.sh` / Docker).

Once connected, Home Assistant should auto-create a device with sensors (battery, range, odometer,
12V, charge power, consumption), binary sensors (charging, online), and — when your car supports
them — lock, climate (on/off), window/sunroof/liftgate covers, and Find / Stop-charging buttons.

### State
| Entity | Source |
| --- | --- |
| Lock | telemetry `unlocked` (verified) |
| Climate on/off | telemetry `ac_on` |
| Windows / sunroof / liftgate | body bytes (E5-verified; treat as best-effort on other models) |
| Sensors | same fields as `/api/summary` |

Availability follows car freshness (~40 min): when the car is dark, entities go unavailable.

### Commands
Commands use **named actions**, not raw hex. Opcodes live in `tools/control_opcodes.json`
(shipped with the repo; only **stop charging** `742701` is confirmed). Long-press a Control-tab
button to remap — that updates the shared file so MQTT and the UI stay in sync.

Events (non-retained): `{base_topic}/event/charge_complete`, `{base_topic}/event/battery_low`.

### Topic sketch
```
{base}/sensor/battery
{base}/lock/state          ← LOCKED / UNLOCKED
{base}/control/lock/set    ← LOCK / UNLOCK
{base}/control/climate/set ← off / cool
{base}/control/windows/set ← OPEN / CLOSE / VENT
{base}/control/result      ← last command ack JSON
{base}/availability
```

## REST sensors
Add to `configuration.yaml` (change the host/port to your instance):

```yaml
rest:
  - resource: "http://YOUR-HOST:8088/api/summary"
    scan_interval: 60
    sensor:
      - name: "J5 Battery"
        unique_id: j5_battery
        value_template: "{{ value_json.battery }}"
        unit_of_measurement: "%"
        device_class: battery
        state_class: measurement
      - name: "J5 Range"
        unique_id: j5_range
        value_template: "{{ value_json.range_km }}"
        unit_of_measurement: "km"
        icon: mdi:map-marker-distance
      - name: "J5 Odometer"
        unique_id: j5_odo
        value_template: "{{ value_json.odometer }}"
        unit_of_measurement: "km"
        state_class: total_increasing
        icon: mdi:counter
      - name: "J5 12V Battery"
        unique_id: j5_12v
        value_template: "{{ value_json.volt12 }}"
        unit_of_measurement: "V"
        device_class: voltage
      - name: "J5 Charge Power"
        unique_id: j5_charge_kw
        value_template: "{{ value_json.charging.rate_kw | default(0) }}"
        unit_of_measurement: "kW"
        device_class: power
      - name: "J5 Consumption"
        unique_id: j5_consumption
        value_template: "{{ value_json.energy.consumption }}"
        unit_of_measurement: "kWh/100km"
      - name: "J5 Tyres"
        unique_id: j5_tyres
        value_template: "{{ value_json.tyre_status }}"
    binary_sensor:
      - name: "J5 Charging"
        unique_id: j5_charging
        value_template: "{{ value_json.charging.active }}"
        device_class: battery_charging
      - name: "J5 Online"
        unique_id: j5_online
        value_template: "{{ value_json.online }}"
        device_class: connectivity
```

Restart Home Assistant (or reload YAML) and the `sensor.j5_*` / `binary_sensor.j5_*` entities appear.

## Automations
```yaml
automation:
  - alias: "J5 battery low"
    trigger:
      - platform: numeric_state
        entity_id: sensor.j5_battery
        below: 20
    action:
      - service: notify.mobile_app_YOURPHONE
        data:
          title: "J5 EV"
          message: "Battery {{ states('sensor.j5_battery') }}% — time to charge."

  - alias: "J5 charge complete"
    trigger:
      - platform: state
        entity_id: binary_sensor.j5_charging
        from: "on"
        to: "off"
    action:
      - service: notify.mobile_app_YOURPHONE
        data:
          title: "J5 EV"
          message: "Charging done — {{ states('sensor.j5_battery') }}%."
```
Replace `YOURPHONE` with your Home Assistant companion-app device (the `notify.mobile_app_*`
service it registers).

With MQTT you can also trigger on `{base_topic}/event/charge_complete` /
`{base_topic}/event/battery_low` for push instead of poll edge-detection.

## Fields you can map
`/api/summary` also carries (handy for more sensors / templates):

| Path | Meaning |
| --- | --- |
| `battery` | state of charge (%) |
| `range_km` | range remaining (km) |
| `odometer` | total km |
| `volt12` | 12 V battery voltage |
| `online` | car reachable (bool) |
| `unlocked` | lock state (bool: unlocked) |
| `ac_on` | climate on (bool) |
| `trunk_open` / `windows` / `sunroof_open` | body state |
| `charging.active` | charging now (bool) |
| `charging.rate_kw` | live charge power (kW) |
| `energy.consumption` | car's avg kWh/100km |
| `energy.today_kwh` | energy used today (kWh) |
| `tyre_status` | `Normal` / `Check tyres` (indirect TPMS, no PSI) |
| `insights.rp_per_km`, `insights.real_range` | running cost / real-world range |
