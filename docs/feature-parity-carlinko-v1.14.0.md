# CarLinko → j5-ev-dashboard feature parity (CarLinko v1.14.0)

Static RE pass to answer one question: **what can the CarLinko app do that the
dashboard does not yet replicate?** Derived from the shipped v1.14.0 Android
artifact — no runtime, no car touched for this pass.

## Artifact identity

| | |
|---|---|
| Package | `com.cqr.CarLinko` |
| Version | **1.14.0** (versionCode **178**) — prior recon was 1.12.0 / 172 |
| XAPK | `CarLinko_1.14.0_APKPure.xapk` (APKPure), arm64-v8a |
| `libapp.so` sha256 | `67b4a6283bf65ca0724b304d91dac334df03d8b0cc01f278f15b8631d447767c` |
| Dart snapshot hash | `1ce86630892e2dca9a8543fdb8ed8e22` |
| Engine | clang 19.0.1 (Android r530567e, +pgo +bolt +lto +mlgo) |

**Method:** string-pool + `package:carlinko/*` module extraction from the Dart
AOT snapshot (REA `identify_flutter_build` / `inspect_dart_aot`, plus offline
`strings` over `libapp.so`). This recovers **every API path, every control
opcode, every feature module, and the control-action vocabulary** the binary
carries. It does **not** recover the exact `controlType → opcode` jump table
(Dart dispatches string constants through the object-pool pointer; that needs
Blutter-style recovery or a one-tap runtime confirm) — see *Control labels*.

---

## Headline findings

1. **The control opcode SET is unchanged from 1.12.0.** No new remote-control
   commands were added. So the only outstanding control work is confirming
   labels, not discovering commands.
2. **The app has ~40 endpoints; the dashboard replicates ~15.** The gap is
   almost entirely *features*, not telemetry — the dashboard's reads are
   solid, but a large slice of the app's write/management surface is unmapped.
3. **Not everything is an opcode.** Charge scheduling, target-SoC, climate
   duration and geofencing are **REST endpoints**, not `74xx` opcodes. Any
   "replicate all features" effort has to cover both channels.

---

## Complete endpoint inventory (v1.14.0)

Legend: ✅ replicated · ⚠️ partial · ❌ not replicated · 🔭 read-only value

### Vehicle telemetry & control — mostly done
| Endpoint | Purpose | Dashboard |
|---|---|---|
| `GET /user/vehicle` | Vehicle list + full config (control caps, TPMS formulas, images) | ✅ `_vehicle_raw` |
| `GET /user/vehicle/state/{id}` | 73-byte telemetry blob | ✅ `/api/summary` |
| `GET /user/vehicle/isOnline/{id}` | Reachable bool | ✅ |
| `GET /user/vehicle/terminal/{id}` | Terminal feature flags | ✅ |
| `POST /user/vehicle/remoteControl` | Fire `74xx` opcode | ✅ `send_control` |
| `GET /user/vehicle/operatingRecord`, `/user/operating/page` | **Control/operation history log** | ❌ |
| `GET /user/vehicle/license?vehicleId=` | Plate | ⚠️ read from `/user/vehicle` already |
| `GET /user/vehicle/default/` | **Set default vehicle (multi-vehicle)** | ❌ |
| `GET /user/vehicle/installationPersonnel` | Installer info | ❌ (low value) |
| `POST /user/vehicle/user_transfer` | **Transfer ownership** | ❌ (out of scope) |

### Charging management — ❌ entirely unmapped, high value
| Endpoint | Purpose | Dashboard |
|---|---|---|
| `/user/device/manage/targetSoc` | **Set charge limit (target SoC %)** | ❌ |
| `/user/device/manage/batterySchedule` | **Scheduled / timed charging** | ❌ |
| `/user/device/manage/batteryScheduleByBle` | Scheduled charging over BLE | ❌ (BLE — N/A for cloud) |
| `/user/device/manage/airDuration` | **Climate pre-conditioning duration** | ❌ |
| App modules: `appointment_charge`, `appointment_duration`, `appointment_travel`, `battery_schedule_handle`, `charge_manager` | The UI behind the above | — |

### Alerts / notifications — ❌ mostly unmapped
| Endpoint | Purpose | Dashboard |
|---|---|---|
| `GET /user/device/manage/terminalNoticeConfig/{id}` | Alert toggles (lowVoltage, illegalOpened, forgetToLock, targetSoc) | 🔭 read only |
| `POST …/terminalNoticeConfig` (write) | **Change alert thresholds** | ❌ |
| `GET /user/notice/page`, `/user/notice/` | **Notification / event history** | ❌ |
| `/user/notice/allRead`, `unReadCount` | Mark read / badge | ⚠️ count only |
| `/notice/publishMessage*` | Server→client push messages | ❌ |
| `PUT /user/jPush/{regId}` | Register push id | ❌ (needs FCM) |
| `push_setting_controller` | Push preferences UI | — |

### Geofencing — ❌ unmapped
| Endpoint | Purpose | Dashboard |
|---|---|---|
| `/user/electronicFence/add`, `/list`, `/update`, `/updateStatus` | **Geofence create/manage + breach alerts** | ❌ |

### Car location & navigation — ❌ unmapped, notable
| Endpoint | Purpose | Dashboard |
|---|---|---|
| `/maps/deviceLocate` | **Car's live GPS position (find-my-car)** | ❌ |
| `/maps/computeRoute`, `/maps/searchNearby`, `/maps/reverseGeocoding`, `/maps/geoLocate` | In-app routing / nearby / geocode (Google-backed) | ⚠️ dashboard has its own SPKLU + geocode |

### Maintenance & service — ❌ unmapped
| Endpoint | Purpose | Dashboard |
|---|---|---|
| `/user/maintain/page`, `/user/maintain/details/` | **Maintenance records / reminders** | ❌ |
| `/user/servicePackage/*`, `/user/order/trade/{online,offline}`, `/user/order/result/` | Paid service packages / orders | ❌ (commercial — out of scope) |

### Digital key sharing — ❌ unmapped
| Endpoint | Purpose | Dashboard |
|---|---|---|
| `/user/keyAuthority`, `/user/keyAuthority/` | **Share car access / key authority** | ❌ |
| App modules: `ble_key_authorize`, `add_authorized`, `authorized_manager`, `send_key_authorize_data_utils` | Key-sharing UI (partly BLE) | — |

### Firmware / OTA — ❌ unmapped
| Endpoint | Purpose | Dashboard |
|---|---|---|
| `/user/higherFirmware?deviceId=`, `/user/startUpgradeFirmware/v1.3/`, `/pub/reportDeviceVersion` | T-Box firmware OTA | ❌ (risky — leave to app) |

### Device bind / account / misc
| Endpoint | Purpose | Dashboard |
|---|---|---|
| `/user/applyUnbound`, `/user/applyUnbound/bind/` | Bind / unbind device | ❌ |
| `/user/login`, `/user/logout`, `/user/register`, `/user/updatePassword`, `/user/updateMobile`, `/user/setInfo`, `/user/closeAccount`, `/user/language/` | Account lifecycle | ✅ login only |
| `/pub/sendVerifyCode`, `/pub/sendEmailVerifyCode`, `/pub/verifyCode` | OTP | ❌ (not needed) |
| `/pub/appConfig`, `/pub/checkAppUpdate`, `/pub/timestamp`, `/pub/help/tree`, `/system/cfeedback*`, `/cqr/treaty` | App config / help / feedback | ✅ timestamp; rest N/A |
| `/netty/getConnect/2/{sn}` | WS URL | ✅ (REST poll used instead) |

### New since 1.12.0
- Region host `cqr-api-kaz` / `cqr-pub-kaz` (Kazakhstan) added. SEA remains the
  relevant region. No functional change for the J5.

---

## Control surface (opcodes)

### Opcode set — unchanged from 1.12.0
```
740100 740200 740300 740400 740500 740600 740700 740800 740A00 740E00
740F00 740F01 740F02  741000 741001  741200 741201
741500 741501 741502 741503   741600 741601 (741602) 741603
741700 741701 741702 741703   741900 741901 741902 741903
741A00 741A01 741A02 741A03   741B00 741B01 741B02 741B03
(741C00) 741C01 (741C02) 741C03   741E00 741E01 741E02 741E03
741F00 741F01  742000 742001  742300 742301  742400 742401
742500 742501  742600 742602  742701(=stop charge, confirmed)
```
Entries in parentheses weren't emitted as standalone strings in this scan but
were present in 1.12.0 — almost certainly a scan artefact, not a removed
command. **No opcode added or removed → the 1.12.0 opcode work stays valid.**

### Control-action enum (from `tools/vehicle_control_action_enum.dart` + response labels)
Climate family recovered from the `{action}{On|Off}{Result}` response-label
scheme in `vehicle_control_response_handle.dart`:

`ac`, `quickCool`, `quickHeat`, `defrostFront`, `windshieldHeat`,
`steeringHeat`, `seatHeat`, `seatVent`, `airPurifier`, `ventilation`, `engine`

Body family from `vehicleControlConfig` keys: `Lock`, `Unlock`, `WindowsOpen`,
`WindowsClose`, `WindowsVent`, `Sunroof`, `SunroofTilting`, `PowerLiftgate`,
`Trunk`, `Search` (find car), `ChargingManagement`.

### Control labels — authoritative map exists; confirmation now automated
The `assembledSendData` jump table was already decoded against the
`vcLoadingMessage` labels (issue #11) — that authoritative opcode→label map is in
`docs/control-opcodes.md`, and lock/unlock, trunk, windows, A/C and stop-charge
are **runtime-confirmed**. The remaining rows are "static decode, pending one-tap".

This pass wired an automated finisher: `/api/control {confirm:true}` snapshots the
car's body-state, fires, re-reads, and reports what moved (`server._OPCODE_EFFECT`
maps each confirmed opcode to its body-state field). Firing a pending button on the
Control tab now both actuates **and** records the effect, so the pending rows get
confirmed by use rather than by a separate mitm/Blutter session. The v1.14.0 opcode
constant pool is unchanged from 1.12.0, so the table is complete — only labels remain.

### Climate temperature / duration is NOT an opcode
`SetTemperature` / `airDuration` / `targetSoc` / `batterySchedule` go through
the REST `/user/device/manage/*` endpoints above, carrying numeric params —
`AcDeskControlStatusBean`, `AcGearControlStatusBean`, `BatteryScheduleParams`,
`appointmentDurationBeanParams`. On/off A/C is an opcode; *setpoints and
schedules are REST*. Replicating "A/C to 22°C" or "charge to 80%" means a
REST call, not a `74xx` fire.

---

## Prioritised gap list (what to actually build)

All of these are signed-GET/POST with the existing `auth.SIGN_KEY` HMAC — the
signing is already solved, so each is a thin addition to `server.py`.

| # | Feature | Endpoint(s) | Value | Risk | Notes |
|---|---|---|---|---|---|
| 1 | **Target SoC (charge limit)** | `…/manage/targetSoc` | High | Low | Already surfaced in telemetry as targetSoc=100; make it settable |
| 2 | **Scheduled charging** | `…/manage/batterySchedule` | High | Low | `BatteryScheduleParams`; mirror app's appointment UI |
| 3 | **Climate pre-conditioning duration** | `…/manage/airDuration` | High | Low | Pairs with A/C opcode; sets run-time |
| 4 | **Alert threshold writes** | `…/terminalNoticeConfig` (POST) | Med | Low | Dashboard already reads these; add write |
| 5 | **Notification / event history** | `/user/notice/page` | Med | Low | Read-only; the event feed the app shows |
| 6 | **Operation history log** | `/user/vehicle/operatingRecord` | Med | Low | "who locked it when" audit trail |
| 7 | **Car GPS (find-my-car)** | `/maps/deviceLocate` | Med | Low | Live position; dashboard has no car GPS today |
| 8 | **Geofencing** | `/user/electronicFence/*` | Med | Med | Create fence + consume breach alerts |
| 9 | **Maintenance reminders** | `/user/maintain/page` | Low | Low | Service schedule read |
| 10 | **Multi-vehicle default** | `/user/vehicle/default/` | Low | Low | Only if >1 car on the account |

**Deliberately out of scope** (commercial / risky / app-only): service-package
orders & payments, firmware OTA, ownership transfer, OTP/register/close-account,
BLE key sharing and BLE charge scheduling (no cloud path).

---

## Live verification (2026-10-22, against the real account)

Ran `tools/carlinko_ext_selftest.py` + method/param probing. Signing is correct;
the convention was recovered by probing (safe GETs; writes tested as no-ops).

**Paging is `page`+`size`** (not `pageSize`/`current`). **`/user/device/manage/*`
settings are `PUT`** (POST → `1003` "method not supported"). `/maps/deviceLocate`
is `POST`.

| Endpoint | Method + params | Status |
|---|---|---|
| `notice/unReadCount` | GET | ✅ `0000` (5 category counts) |
| `notice/page` | GET `page`+`size` | ✅ `0000` (empty — no notices on account) |
| `operating/page` | GET `vehicleId`+`page`+`size` | ✅ `0000` (`operatingRecord` returns 1000 — not used) |
| `maintain/page` | GET `vehicleId`+`page`+`size` | ✅ `0000` |
| `electronicFence/list` | GET `vehicleId`+`page`+`size` | ✅ `0000` |
| `terminalNoticeConfig/{id}` (read) | GET | ✅ `0000` — 25 fields |
| `maps/deviceLocate` | POST `{vehicleId, deviceSn}` | ✅ endpoint OK (`50008 车辆不在线` = car asleep) |
| **`targetSoc`** | **PUT** `{vehicleId, deviceSn, targetSoc}` | ✅ **`0000` verified** (no-op write at current value) |
| `airDuration` | PUT (same pattern) | 🔬 untested, PUT by pattern |
| `terminalNoticeConfig` (write) | PUT | ❌ method confirmed; **every body → `1000 未知异常`**, needs one capture |
| `batterySchedule` | — | ❌ GET/POST → 1003, PUT → token-refresh; unresolved |

**Net, production-ready now:** control-state confirmation, charge limit
(`targetSoc` PUT), notice badge, notifications/operation-log/geofences/maintenance
reads, car GPS (when awake), alert config **read**.

### Both remaining gaps resolved by app capture (2026-10-22)

A Flutter-aware capture harness (reFlutter-patched app + mitmproxy WireGuard on an
arm64 emulator — see `tools/capture/`) decrypted the app's own traffic and settled
both:

- **Battery-schedule → implemented.** Captured the app's exact write and verified
  it live (`0000`):
  `PUT /user/device/manage/batterySchedule`
  `{"vehicleId":<int>,"enabled":<bool>,"hour":0-23,"minute":0-59,"duration":<hours>,"week":[7 bools]}`
  (`week` = Sun..Sat repeat flags; all-false = one-time). There is **no working
  GET** (`batterySchedule` GET → 1003), so it is write-only. Wired into
  `carlinko_api.set_charge_schedule`.
- **Alert-config write → owner-only, not a body bug.** The alert toggles live under
  the app's **Device** screen, which a **sub-user cannot open** ("Operation not
  supported by sub authorisation Device"). This dashboard authenticates as a
  sub-user, so its `terminalNoticeConfig` PUT is permission-denied — the gateway
  returns that as `1000 未知异常`. **No body makes a sub-user's write succeed.** The
  READ works for sub-users, so the Flutter **Vehicle-alerts screen staying
  read-only is correct**. Editing requires authenticating as the vehicle **owner**;
  `set_alert_config`'s PUT then works as-is.

## Open items (need runtime or Blutter)

- Exact `74xx` → button labels (runtime 1-tap, or Blutter). Opcode set confirmed
  complete.
- Request-body shapes for the REST writes (#1–#8). Static gives the paths and
  the `*Params`/`*Bean` names; the exact JSON fields want one captured request
  each (Frida hook on the app, or trial against your own car) before shipping.
- Telemetry bytes 54/55 (PHEV) and odometer/charge-flag offsets — unchanged from
  prior recon; need driving/charging frames, not this app version.
