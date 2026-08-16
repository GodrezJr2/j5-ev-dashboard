# CarLinko Cloud API — Map (Jaecoo J5 EV)

Captured 2026-06-21 via reFlutter-patched app + emulator `-http-proxy` + mitmproxy.
Raw capture: `capture/flows.mitm`; dumps: `capture/api_dump.txt`, `capture/ws_dump.txt`.

> Contains the owner's live data (token, VIN, vehicle/device ids). Keep local; do not share unsanitised.

## Hosts

- **REST API:** `https://cqr-api-{region}.hzhjcl.com` — this account = **`sea`** (Indonesia).
  Resolved IPs seen: `47.131.252.2`, `54.255.41.185`.
- **Realtime WebSocket:** `ws://wss-cqr-{region}.hzhjcl.com:4002/` (URL handed out by
  `/netty/getConnect/...`). Plain WS over port 4002 (not 443).
- Static assets: `cqr-prod.oss-cn-beijing.aliyuncs.com` (Aliyun OSS, vehicle images).

## Auth / request signing

Vehicle was identified, user logged in. Every authenticated REST request carries headers:

| Header | Example | Meaning |
|---|---|---|
| `token` | `<TOKEN>` | Session token (from login). Constant for session. |
| `timestamp` | `1782017645767` | Epoch ms. Server validates clock skew (app has `VerifyTimestampUtils` correction). |
| `signature` | `sbw3BSLR2fxbUtK4xBXnGesN69AL4TnaD9SUhu5vkf0=` | base64, 32 bytes → **HMAC-SHA256**. Differs per request (depends on path/body/timestamp). |
| `v-data` | `<VDATA>` | base64 device/app blob the app sends. **NOT validated by the server** — login + signed requests succeed with it absent/empty/garbage (tested 2026-06-27), so we omit it entirely. |

Notes:
- **Responses are plaintext JSON** (not encrypted). The request `v-data` blob is ignored by the server (not validated), so the only thing gating signed requests is the HMAC signature (app-global key).
- Envelope: `{"data": ..., "code": "0000", "msg": "请求成功"/"OK"}`. `code != "0000"` = error.
- Crypto lib = pointycastle (AES + HMAC-SHA256). Signing key (appSecret) still to be recovered → see "Remaining".

## Endpoint catalog (observed)

| Method | Path | Purpose | Notes |
|---|---|---|---|
| GET | `/pub/timestamp` | Server time | No auth. `data` = epoch ms. |
| GET | `/pub/checkAppUpdate?platform=2&type=1&version=1.12.0` | App update check | |
| GET | `/user/info` | User profile | id 88504, email, nickname Jay, areaCode IDN |
| GET | `/user/vehicle` | **Vehicle list + full config** | VIN, model, deviceSn, control config, TPMS formulas, images. Also `brand` (`OMODA\|JAECOO`), `modelId`, `oldModel` (platform code, e.g. `T13J BEV`), `year`, `areaCode`. `vehicleImgConfig` is a **JSON string** holding `{Front, Side, Top}` CDN URLs for this exact car, and `vehicleImgConfigs` repeats them per `vehicleColor` — so the correct render is available for any CarLinko car, no bundled art needed |
| GET | `/user/vehicle/terminal/{vehicleId}` | Terminal feature flags | |
| GET | `/user/device/manage/terminalNoticeConfig/{vehicleId}` | Alert toggles | lowVoltage, illegalOpened, forgetToLock, targetSoc=100... |
| PUT | `/user/jPush/{regId}` | Register push id | |
| GET | `/netty/getConnect/2/{deviceSn}` | Get WS URL | returns `ws://wss-cqr-sea.hzhjcl.com:4002` |
| POST | `/system/record/getResearch` | Survey check | body `{vehicleId,userId,clientType}` |
| POST | `/pub/file/appLog` | **Uploads internal debug logs** (multipart) | Leaks Dart logs w/ VIN, email, decoded beans. Useful + a privacy smell. |
| GET | `/user/notice/unReadCount?vehicleId=` | Notification counts | |
| GET | **`/user/vehicle/state/{vehicleId}`** | **Telemetry over REST** | Returns the exact same 73-byte hex blob as WS `action:6` — one signed GET per poll is enough for reads, no persistent WS needed. Verified live 2026-08-13 (byte-for-byte match with the WS frame, incl. battery/range). Reported by [@jebentancour](https://github.com/jebentancour) in [#5](https://github.com/GodrezJr2/j5-ev-dashboard/issues/5) |
| GET | **`/user/vehicle/isOnline/{vehicleId}`** | Car reachable (bool) | `{"data":true}` / `false`; same signing. Also [#5](https://github.com/GodrezJr2/j5-ev-dashboard/issues/5) |
| POST | **`/user/vehicle/remoteControl`** | **CONTROL the car** | body `{vehicleId, deviceSn, data:"<hexcmd>", timeOut:20}`. See control. |

## Remote control

`POST /user/vehicle/remoteControl`  body:
```json
{"vehicleId":"<VEHICLE_ID>","deviceSn":"<DEVICE_SN>","data":"2301","timeOut":20}
```
- `data` = hex command code (e.g. `2301`). Observed response when car asleep/unreachable:
  `{"code":"50043","msg":"设备网络不佳，请使用蓝牙控车"}` (“device network poor, use Bluetooth control”).
- Command set comes from `/user/vehicle` → `remoteControls.commandList`
  `[{name:1},{name:2},{name:3},{name:4},{name:5},{name:6}]` and `vehicleControlConfig`
  (Lock, Windows Open/Close/Vent, Sunroof, PowerLiftgate, A/C with temp 15.5–30.5°C,
  ChargingManagement, ScheduledCharging, ScheduledTravel, Search/find-car…).
- Control results / live status come back over the **WebSocket**, not the HTTP response.

## Realtime WebSocket protocol (`:4002`)

```
>> {"action":1,"data":{"token":"<token>","vehicleId":"<VEHICLE_ID>"}}   # login
<< {"action":1,"code":"0000","msg":"登录成功"}                     # ok
>> {"action":6}                                                   # request telemetry
<< {"action":6,"code":"0000","data":"7700....F802","msg":"成功"}  # telemetry hex blob
>> {"action":0,"data":{"sn":"<DEVICE_SN>"}}                  # poll/keepalive
<< {"action":0,"code":"0000","data":0,"msg":"成功"}
```

### Telemetry blob (action 6 `data`, hex)
Example (car parked/asleep):
```
77000000000200000000FF7F056800600000000372000101B80201003100F8B8
000000000000000000000000FFFFFFFFFFFFFFFF00000071000003FF00000000
000000FF00E000F802
```
This is the packed vehicle state (battery, range, lock, windows, **tyres**…). Field byte
offsets are decoded by the Dart parser in `libapp.so` — still to be fully mapped.
The `FFFFFFFFFFFFFFFF` run = invalid markers (`tirePressureInvalid:["FF"]`,
`tireTempInvalid:["FF"]`) because the car is asleep → no live tyre data right now.

## TPMS — ANSWERED ✅ (INDIRECT, no real PSI)

The J5 EV uses **indirect TPMS** (inferred from ABS wheel-speed differences, **no pressure
sensor per wheel**) — so **no real PSI exists** anywhere to read. Proven by driving: the tyre
block (bytes ~44–51) stayed **`FF` through a full road drive** (slow laps *and* road speed),
not just while parked. The official CarLinko app confirms it too — it shows tyres as "-.- bar".

The blob *has* pressure/temp fields and the app's `vehicleControlConfig` even ships conversion
formulas, but the platform **never populates them on this car** — they're permanently `FF`:

```
appPsiFormula : data * 1.373 * 0.145   ->  PSI   (formula exists…)
appKpaFormula : data * 1.373           ->  kPa
appBarFormula : data * 1.373 * 0.01    ->  bar
tireTempFormula: data * 0.65 - 40      ->  °C
invalid: pressure byte == FF, temp byte == FF    (…but the bytes are always FF here)
```

So the dashboard shows tyre **status** (Normal / Check tyres), **not** PSI. The decoder + formula
are kept so that a car which *does* report real values would display them, but on this vehicle
the only honest output is status. An abnormal tyre would surface via CarLinko alerts, not telemetry.

## Standalone access — VALIDATED ✅

`tools/ws_client.py`: a host-side Python client connects to the WS with **only the token**
(WS login takes `{action:1,data:{token,vehicleId}}` — **no signature**), requests
`{action:6}`, and decodes the blob. Confirmed against the app dashboard:

| Field | Blob offset | Value |
|---|---|---|
| `doors` | byte 2 | bitmask: front L/R, rear L/R doors (E5-verified, #5) |
| `ignition` | byte 3 | 0 = off/parked. ⚠️ The E5 owner has this as **lock** (0=locked, !=0=unlocked) from a live lock/unlock test — both correlate with "car in use", so it's used as an awake indicator and needs a dedicated test to disambiguate |
| `trunk_open` | byte 4 | 0 = closed (E5-verified, #5) |
| `windows` | byte 8 | 2 bits per window (E5-verified, #5) |
| `sunroof_open` | byte 9 | 0 = closed (E5-verified, #5) |
| `volt12` | bytes 12–13 (BE u16 ×0.01) | 13.84 V |
| `speed_kmh` | bytes 14–15 (BE u16 ÷16) | raw 320 = 20 km/h |
| `odometer` | bytes 18–20 (BE u24) | 882 |
| `fuel_pct` **(PHEV)** | byte 21 | 58 % — `0` on every BEV frame |
| `ac_on` | byte 23 | `0`=off, `!=0`=on (climate). **Live-verified on the E5**: a manual A/C toggle moved exactly this byte; fan/temp/seat/defrost changes leave it alone |
| `ac_temp_c` | byte 24 | A/C target temp (E5-verified, #5; scale TBD) |
| `battery_pct` | byte 28 | 49 |
| `range_km` (EV) | bytes 29–30 (BE u16) | 248 |
| `seat_heat` | bytes 32–33 | L, R (0 = off) |
| `seat_vent` | bytes 37–38 | L, R (0 = off) |
| `defrost_front` | byte 42 | 0 = off |
| tyre block (4 pressure + 4 temp) | bytes 44–51 | `FF` on indirect TPMS (J5); real values on direct TPMS. temp = `raw × 0.65 − 40` |
| `fuel_l_100` **(PHEV)** | byte 53 (×0.1) | 0.8 L/100 km — `0` on every BEV frame |
| `consumption` | byte 55 (×0.1) | 12.4 kWh/100 km (matches the J5 dash exactly; on the PHEV it reads `dash − 2.4` — see below) |
| `charge_mode` | byte 56 | connector: `0`=none, `1`=AC, `16`=DC fast. [#5](https://github.com/GodrezJr2/j5-ev-dashboard/issues/5) |
| `charge_state` | byte 57 | `0`=idle, `1`=charging, `2`=complete, `3`=canceled, `4`=hot, `5`=stop-charging |
| `charge_remain_min` | bytes 58–59 (BE u16) | minutes to done; `0x3FE`/`0x3FF` = invalid (CarLinko's own `chargingTimeInvalidValue` sentinel) |
| `charge_power_kw` | bytes 62–63 (BE u16 ×0.1) | instant power; 62 is the overflow byte past 25.5 kW. `0` when idle. ⚠️ **Bidirectional**: the same pair carries **regen power while braking** — gate on b57 (`!= idle`) before calling it charge power (E5-verified, #5) |
| `wltc_range_km` | bytes 68–69 (BE u16) | **rated (WLTC) range** — *not* a mirror of EV range. See below |
| headline range | bytes 70–71 (BE u16) | EV range on a BEV (mirrors `range_km`); **fuel range** on a PHEV (652 km) |
| `hv_state` | byte 5 | HV/motor state per [#5](https://github.com/GodrezJr2/j5-ev-dashboard/issues/5) (`>=2` = on). E5 live data: **0=off, 1=low-voltage (15–90 s power on/off transition), 2=high-voltage/ready** — `2` in 100 % of driving samples. On the J5 the byte takes 0–3 with `2` dominant even parked, so treat as model-specific |

### The platform hands you the per-model constants

`/user/vehicle` → `vehicleControlConfig` publishes what this app used to hard-code, so a new car
can configure itself:

| Key | J5 value | Use |
|---|---|---|
| `appKpaFormula` / `webTirePressureFormula` | `data * 1.373` | the tyre raw→kPa scale, per model — this is where `tpms_scale` comes from |
| `appPsiFormula` / `appBarFormula` / `webConversionFormula1/2` | `… * 0.145` / `… * 0.01` | the same scale expressed in other units |
| `tirePressureInvalid` | `["FF"]` | the "sensor asleep" sentinel |
| `powerConsumption` / `fuelConsumption` | `true` / `false` | powertrain: both true = PHEV, power only = BEV |
| `Engine` | `false` | BEV confirmation |
| `chargingTimeInvalidValue` | `["3FE","3FF","7FE","7FF"]` | sentinels for charge-time fields |
| `A/C`, `WindowsOpen`, `Sunroof`, `Lock`, `Search`, … | | remote-control capability flags |

`setup.py` reads the tyre scale and powertrain from here automatically.

PHEV offsets come from three Chery Tiggo 8 PHEV frames contributed by
[@wbrocker](https://github.com/wbrocker) in
[#2](https://github.com/GodrezJr2/j5-ev-dashboard/issues/2), cross-checked against 13,018+ logged
J5 (BEV) frames where bytes 21, 53 and 54 are `0` in every single one.

### Charging block + rated range — VERIFIED ✅ (bytes 5, 23, 56–59, 62–63, 68–69)

Contributed by [@jebentancour](https://github.com/jebentancour) (Omoda E5 BEV, Uruguay) in
[#5](https://github.com/GodrezJr2/j5-ev-dashboard/issues/5) and verified here against three other
cars' data before shipping:

- **J5 EV (ID)** — 72,507 logged frames, including 1,392 DC-charging frames.
- **Tiggo 8 PHEV (ZA)** — three captured frames from #2, one of which turns out to be **AC
  charging**: `b56=1`, `b57=1`, `b58–59=178` min, `b62–63=39` → 3.9 kW — a typical home charge,
  and the AC enum confirmed on a second car without anyone noticing at the time.
- **Tiggo 7 PHEV (MY)** — one idle frame from #3 (`b56=0`, `b57=0`, `b58–59=0x3FF` sentinel).

What held up:

| Byte | Claim | Verified how |
|---|---|---|
| 56 | `16` = DC fast | every J5 DC session reads 16; `0` on all idle frames; `1` (AC) on the Tiggo 8's home charge |
| 57 | `0` idle / `1` charging / `2` complete / `5` stop | exactly the 1,392 charging frames read 1, `2` appears right after each session, `5` seen in a 14-frame burst after a session start (stop/replug); `3`/`4` never seen |
| 58–59 | minutes to done | counts 37 → 10 → 1 min through a real session; idle reads `0x3FF` = CarLinko's own `chargingTimeInvalidValue` sentinel |
| 62–63 | instant power ×0.1 kW | 29.5–63.7 kW on DC, 3.9 kW on the Tiggo 8's AC charge, taper to 6.0 kW at 99 %, `0` when idle; consistent with the SoC-derived rate (51.8 kW avg vs 63.7 kW instant) |
| 68–69 | **WLTC rated range, not an EV-range mirror** | on the J5 it differs from EV range in **72,482 of 72,507 frames** — e.g. EV 334 vs WLTC 302 at 66 %, and 302/0.66 = 457.6 ≈ the car's 461 km NEDC rating. The Omoda owner cross-checked live against the app (304 vs 329, digit-for-digit). The Tiggo 8's 90/81/38 coincidences were exactly that — a PHEV's EV estimate *is* the rated one |
| 5 | HV state `>=2` = on | only provable on the Omoda E5 (live-verified by its owner). On the J5 the byte takes 0–3 without tracking ignition — kept raw, treated as model-specific |
| 23 | A/C `!=0` = on | `{0,1}` on the J5; 1 in 98.8 % of driving frames, toggles while parked. Consistent, not contradicted |

The dashboard now surfaces `charging.mode` (`ac`/`dc`), `charging.state`, `charging.remaining_min`
(the car's own time-to-done — the field the Tiggo 7 owner asked about in #3) and prefers the car's
own `charge_power_kw` for `charging.rate_kw` over the SoC-derived estimate. `wltc_range_km` is
exposed at the API level.

### Fuel range — RESOLVED ✅ (bytes 70–71)

Three captures settle what one couldn't. The pair is **the car's headline range**: a BEV writes its
EV range there, a PHEV writes its *fuel* range.

| | 19 Jul | 20 Jul | 28 Jul | |
|---|---|---|---|---|
| battery | 100 % | 89 % | 44 % | |
| EV range (b29–30) | 90 | 81 | 38 | |
| b68–69 | 90 | 81 | 38 | equal on a PHEV (its EV estimate is the rated one); see above |
| fuel % (b21) | 58 | 58 | 56 | tank dropped |
| **b70–71** | **652** | **652** | **649** | held while EV range fell, then moved with the tank |
| dash fuel range | 652 | — | 649 | ✅ exact match |

The 20 Jul frame is an EV-only drive: EV range fell 9 km and b70–71 did not move, which rules out
"EV range". The 28 Jul frame burnt fuel: the tank went 58 % → 56 % and b70–71 went 652 → 649, which
rules out "a constant". Surfaced as `fuel.range_km`, PHEV only.

**Combined range is not transmitted.** The app's own total is exactly EV + fuel on every capture
(742 = 90 + 652, 687 = 38 + 649), so `fuel.total_range_km` is computed here and labelled as such.

**Still unidentified:**
- **byte 55 on a PHEV.** It reads `dash − 2.4` on both paired samples (98 → dash 12.20;
  145 → dash 16.90 — slope exactly 10.0, offset exactly 2.4). Not fuel-derived: fuel consumption
  went 0.80 → 0.20 L/100 km between them and the offset didn't budge. On the J5 the same byte
  matches its dash with no offset, so the PHEV either averages over a different window or reports a
  different metric. Left as-is rather than shipped as a two-point fit — needs a third paired sample.
- **byte 54** — 20 on the PHEV in all three frames, `0` on every BEV frame. Meaning unknown.

So the whole product can run off the WebSocket + token, no REST signing needed for reads.

**Caveats:**
- Token expires eventually; re-login (REST) needs the `signature` algo (still TODO). MVP
  logger uses the current token; add auto-refresh once signing is cracked.
- Odometer, charge-state flag, and exact tyre offsets need frames captured while
  **driving** / **charging** — log the RAW blob every poll and back-decode later.

## Remaining to finish Sub-project 1

1. **Recover the `signature` algorithm + key** (HMAC-SHA256 input string + appSecret) so we
   can forge fresh requests, not just replay. → Frida-hook pointycastle `HMac`/the dio
   interceptor, or Blutter on `libapp.so`.
2. **Map the telemetry blob byte offsets** (battery%, range, lock, 4× tyre pressure, 4×
   tyre temp). → Blutter on the Dart parser, or empirically diff blob vs app display.
3. **Capture an awake-car telemetry frame** (real tyre bytes) to validate the PSI formula.
4. ~~Confirm whether `v-data` can be replayed~~ — RESOLVED: `v-data` is not validated at all (omitted).
