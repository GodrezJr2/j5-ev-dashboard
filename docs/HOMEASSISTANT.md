# Home Assistant integration

The dashboard already exposes everything as JSON at `GET /api/summary`, so Home Assistant can
read it with a built-in **REST sensor** — no extra add-on, no code. You get entities for battery,
range, charging, etc., and can fire automations (e.g. *battery low → notify my phone*).

## Before you start
- Home Assistant must be able to reach the dashboard URL (same LAN, or both on Tailscale).
- If you set a **dashboard password** (public hosting), `/api/summary` is locked, so a plain REST
  sensor gets `401`. For Home Assistant, run the instance **un-gated on a private network /
  Tailscale** (recommended) so HA can read it directly. (A read-only API token for gated instances
  isn't built yet — open an issue if you want it.)

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

## Fields you can map
`/api/summary` also carries (handy for more sensors / templates):

| Path | Meaning |
| --- | --- |
| `battery` | state of charge (%) |
| `range_km` | range remaining (km) |
| `odometer` | total km |
| `volt12` | 12 V battery voltage |
| `online` | car reachable (bool) |
| `charging.active` | charging now (bool) |
| `charging.rate_kw` | live charge power (kW) |
| `energy.consumption` | car's avg kWh/100km |
| `energy.today_kwh` | energy used today (kWh) |
| `tyre_status` | `Normal` / `Check tyres` (indirect TPMS, no PSI) |
| `insights.rp_per_km`, `insights.real_range` | running cost / real-world range |

## MQTT (not packaged yet)
A push-based MQTT publisher (HA auto-discovery, instant charge-done events) isn't built into this
repo yet — the REST sensor above covers most needs. If you'd prefer MQTT, open an issue.
