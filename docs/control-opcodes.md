# CarLinko remote-control opcodes — decoded (static, Blutter)

Recovered 2026-07-28 from the Dart AOT disassembly of `libapp.so`
(`asm/carlinko/tools/send_vehicle_control_data_utils.dart::assembledSendData`). These are the
`data` values for `POST /user/vehicle/remoteControl` — the actual actuation commands, distinct
from the init handshake.

## Format
```
74 <CMD> <STATE>        (6 hex chars, ASCII string in the app)
  74      = control-command prefix
  <CMD>   = command id (0x01..0x27)
  <STATE> = 00 off/close · 01 on/open · 02/03 extra mode/position
```
`assembledSendData(int controlType)` is a jump-table switch: `controlType` (an int enum) indexes
to the opcode. The CMD byte is NOT the controlType — the mapping is via the jump table, so the exact
CMD↔button label still needs a 1-tap runtime confirm (fire it, watch the car).

## Init (sent first — the app's "initializing car")
Raw (not 74-prefixed): `2301` (0x23), `24` (0x24), `77` (0x77) — recovered from symbols
`_sendInitCmd0x23Data / 0x24 / 0x77`. Send before an actuation command.

## Confirmed
- **`742701` = STOP CHARGING** — app log string `当前执行停止充电操作---->742701`.

## Full opcode set (from the constant pool)
```
740100 740200 740300 740400 740500 740600 740700 740800 740A00 740E00
740F00 740F01 740F02
741000 741001
741200 741201
741500 741501 741502 741503     \
741600 741601 741602 741603      |
741700 741701 741702 741703      |  4-state groups (00/01/02/03) =
741900 741901 741902 741903      |  windows (close/open/vent/…) + sunroof
741A00 741A01 741A02 741A03      |
741B00 741B01 741B02 741B03      |
741C00 741C01 741C02 741C03      |
741E00 741E01 741E02 741E03     /
741F00 741F01
742000 742001
742300 742301
742400 742401
742500 742501
742600 742602
742701   (stop charge)
```
Control set (from `vehicle_control_response_handle.dart` result labels): Lock, Unlock, TrunkOpen,
Window open/close/vent, Sunroof, FindCar, A/C on/off + cool/heat + temperature, AirPurifier,
DefrostFront, SeatHeat, SteeringHeat, EngineStart, QuickCool/QuickHeat, Charge start/stop.

## Best-effort label map (wired into the Control tab — VERIFY & report mismatches)
Only `742701` is confirmed; the rest are educated from opcode structure + the car's capabilities.
Long-press a Control-tab button to correct its opcode in-place.

| Button | Opcode | Confidence |
|---|---|---|
| Stop charging | `742701` | **confirmed** (app log) |
| Lock | `741000` | guess (0x10 off) |
| Unlock | `741001` | guess (0x10 on) |
| A/C on | `742401` | guess (0x24 on) |
| A/C off | `742400` | guess (0x24 off) |
| Windows open | `741501` | guess (0x15 state1) |
| Windows close | `741500` | guess (0x15 state0) |
| Windows vent | `741502` | guess (0x15 state2) |
| Sunroof open | `741A01` | guess (0x1A on) |
| Sunroof close | `741A00` | guess (0x1A off) |
| Sunroof tilt | `741A02` | guess (0x1A state2) |
| Tailgate (bagasi) | `741201` | guess (0x12 on) |
| Find car | `740100` | guess (0x01) |

## To finish the map
Fire each `74xx01` (on/open variant) at an **awake** car via the dashboard Control tab (it inits
`77` first, then fires), watch which control moves, and label it. `742701` is already known.
Full runtime capture (all labels at once) = mitm the app tapping each control — see
`D:\android-mitm\README.md` (emulator + mitmproxy stack is built; the last mile is a TUN redirect
because Flutter ignores the system proxy).
