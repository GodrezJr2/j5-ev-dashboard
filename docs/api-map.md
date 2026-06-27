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
| GET | `/user/vehicle` | **Vehicle list + full config** | VIN, model, deviceSn, control config, TPMS formulas, images |
| GET | `/user/vehicle/terminal/{vehicleId}` | Terminal feature flags | |
| GET | `/user/device/manage/terminalNoticeConfig/{vehicleId}` | Alert toggles | lowVoltage, illegalOpened, forgetToLock, targetSoc=100... |
| PUT | `/user/jPush/{regId}` | Register push id | |
| GET | `/netty/getConnect/2/{deviceSn}` | Get WS URL | returns `ws://wss-cqr-sea.hzhjcl.com:4002` |
| POST | `/system/record/getResearch` | Survey check | body `{vehicleId,userId,clientType}` |
| POST | `/pub/file/appLog` | **Uploads internal debug logs** (multipart) | Leaks Dart logs w/ VIN, email, decoded beans. Useful + a privacy smell. |
| GET | `/user/notice/unReadCount?vehicleId=` | Notification counts | |
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
| `battery_pct` | byte 28 | 49 |
| `range_km` | bytes 29–30 (BE u16) | 248 |
| tyre block (4 PSI + 4 temp) | ~byte 44–51 | always `FF` (indirect TPMS — never populated, see above) |

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
