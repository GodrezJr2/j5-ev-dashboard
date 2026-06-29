# J5 EV Dashboard — a self-hosted telematics dashboard for the Jaecoo J5 EV

**English** · [Bahasa Indonesia](README.id.md)

A clean, mobile-first PWA that shows the **real** numbers your car already reports —
battery, range, odometer, charging sessions, efficiency, tyre status, 12 V health, trip
log, lifetime cost, a long-trip charge planner, and an interactive SPKLU (EV charger) map.

It exists because the stock CarLinko app hides most of this (tyres only show
"normal/abnormal", there are no trip totals, no charge-cost history, no road-trip planner).
Everything here is derived from data the car **already** sends to its own cloud — this
project just reads your own account and presents it properly.

> Built and validated against a single real car. Charge-cost output matches the owner's
> PLN Mobile receipts to **99.6–99.9 %** (see [Accuracy](#accuracy)).

## Screenshots

| Dashboard | Charging |
| :---: | :---: |
| ![Home dashboard — battery, range, tyres, efficiency, insights](docs/screenshots/home.png) | ![Charge tab — battery care, charge stats, charge-to planner](docs/screenshots/charge.png) |
| **Trip planner** | **SPKLU map** |
| ![Long-trip planner — route, on-route charge stops with connectors and arrival %](docs/screenshots/trip-planner.png) | ![Interactive SPKLU map — pins, live availability, directions](docs/screenshots/spklu-map.png) |

*Plate and VIN are masked by default (privacy eye-toggle). Light theme shown — a dark theme and EN/ID language toggle are built in.*

---

## ⚠️ Legal & ethics — read this first

This is a **personal interoperability / reverse-engineering** project for accessing **your
own vehicle and your own account**. It is provided for educational and personal use.

- **Use it only with an account and a car you own.** Do not access anyone else's data.
- This talks to a **private, undocumented vendor API**. There is **no warranty** and it can
  break at any time if the vendor changes their backend. It is **not affiliated with,
  endorsed by, or supported by** Jaecoo, Chery, or CarLinko.
- **No personal data is shipped.** Your account, token, VIN, plate, vehicle id and device
  serial live only in a gitignored `creds.json` (see [Setup](#setup)). The request-signing key
  is an **app-global constant** (the same string baked into every CarLinko install, trivially
  readable from the APK) — it's bundled so setup is just email + password; it is not a secret
  tied to you.
- **Do not run this as a public/hosted multi-user service.** Doing so means storing other
  people's credentials (which can unlock/control their car) and almost certainly violates the
  vendor's terms. The intended deployment is **one instance per owner**, self-hosted, private
  (e.g. behind Tailscale). See [Going multi-user](#going-multi-user).
- Read-only by design. Remote control of the vehicle is **not** implemented.

If you don't accept the above, don't use this.

---

## Features

- **Live status** — battery %, range, odometer, 12 V, online/parked/charging/driving state,
  pulled from the realtime WebSocket and cached in SQLite.
- **Charging** — auto-detected charge sessions (kWh into pack, kWh billed at the meter, cost),
  a charge-curve chart, weekly/monthly counts, and a "charge to X %" planner with real SPKLU
  tariffs. Regen blips are filtered out so they don't pollute charge history.
- **Efficiency & trips** — per-trip and rolling kWh/100 km with honest guards, lifetime kWh /
  cost / km, and savings vs petrol at real Indonesian fuel prices.
- **Long-trip planner** — set start/finish, get on-route charge stops sized to arrive with a
  safety margin (ABRP-style), with real connector type / kW / live availability from Google.
- **SPKLU map** — pan an interactive map, tap a charger for connectors, live availability and
  directions (PLN-Mobile-style), data from Google Places.
- **Battery care, service countdown, tyre view, privacy toggles, dark mode, EN/ID i18n.**
- **Home Assistant** — read it all over a REST sensor and get battery-low / charge-done notifications. See [docs/HOMEASSISTANT.md](docs/HOMEASSISTANT.md).

See [PRODUCT.md](PRODUCT.md) for the product rationale and [DESIGN.md](DESIGN.md) for the
visual system.

## Architecture

```
  Car TCU ──(cellular)──> CarLinko cloud  ──┐
                                            │  WebSocket (token auth, no signing) — telemetry blob
   tools/logger.py  ◀───────────────────────┘  decodes + stores every frame to carlinko.db
        │                                       (auth.py auto-refreshes the token on expiry)
        ▼
   carlinko.db (SQLite)
        │
        ▼
   tools/server.py  ── /api/summary, /api/trip, /api/spklu ──▶  web/ PWA (vanilla JS, Leaflet)
   (stdlib http.server)        + Google Places (optional)        served over Tailscale
```

- **No framework, no build step.** Backend is Python standard library; frontend is hand-written
  HTML/CSS/JS with two vendored libs (Leaflet, slot-text). Self-hosted and offline-friendly.
- **The telemetry is a 73-byte blob.** Field offsets were recovered by driving the car and
  watching which bytes moved (battery = byte 28, range = 29–30 BE, odometer = 18–20 BE, …).
  See [docs/api-map.md](docs/api-map.md).

## Accuracy

The charge analytics are calibrated against the owner's real PLN Mobile receipts:

| Session            | Dashboard            | Receipt              | Match   |
| ------------------ | -------------------- | -------------------- | ------- |
| 58 → 100 %         | 28.9 kWh / Rp 73,491 | 28.94 kWh / Rp 73,521 | 99.9 % |
| 35 → 80 %          | 29.1 kWh / Rp 73,981 | 29.23 kWh / Rp 74,273 | 99.6 % |

DC charge efficiency is modelled as SoC-dependent (charging to 100 % loses more than to 80 %),
calibrated to two receipts. Usable pack ≈ 58.9 kWh.

The charge planner predicts what you'll actually pay at the meter, checked against a real
PLN Mobile SPKLU receipt:

| The app's charge planner | The real PLN Mobile receipt |
| :---: | :---: |
| ![Charge planner estimate](docs/screenshots/accuracy-app.png) | ![PLN Mobile SPKLU receipt](docs/screenshots/accuracy-receipt.png) |

The app estimates **58.2 kWh** to buy at the meter at **Rp 2,540/kWh**; the receipt shows
**57.34 kWh** actually delivered at the same **Rp 2,540/kWh** all-in tariff — the per-kWh
price is exact and the volume lands within ~1.5 % (the receipt session stopped a little short
of a full charge). The refund maths line up too: bought Rp 152,448, used Rp 145,694.

## Try it first (demo, no account)
Want to see the UI before setting anything up? Run it in **demo mode** — fake but realistic data,
no CarLinko account, no car, no database:
```bash
cd tools && python server.py --demo      # then open http://localhost:8088
# or with Docker:  docker compose run --rm -p 8088:8088 web python server.py --demo 8088
```
A 🧪 *Demo mode* banner makes clear nothing is real. Nice for a quick look or a screenshot.

## Privacy & security
This runs **entirely on your machine** — there is no backend operated by me, and your data is
never sent to any server I control. See **[SECURITY.md](SECURITY.md)** for the full picture; in short:
- Your CarLinko **email/password** are stored locally in `tools/creds.json` (gitignored) and used
  only to log in to **CarLinko's own** cloud (`*.hzhjcl.com`) over TLS — same place the app talks to.
- The only other outbound calls are to **Google Maps** (if you add a key) and free map/route
  services (OpenStreetMap / OSRM) for the trip planner. Nothing else leaves your device.
- Keep the dashboard private (LAN / Tailscale). If it must face the internet, set a
  `dashboard_password` so `/api/summary` isn't open to the world.
- Found a security issue? See [SECURITY.md](SECURITY.md) — please report privately, don't open a public issue.

## Setup

### Prerequisites
- Python 3.10+, `pip install requests websocket-client`
- A CarLinko account with your car on it
- (optional) a Google Maps API key for the trip planner / SPKLU map

No app capture, no MITM, no decompiling needed — you just log in with your account. (The
signing key is bundled, and the `v-data` blob the app sends turned out to be ignored by the
server, so it's dropped entirely.)

### Use a second account (recommended)
CarLinko keeps **one active session per account**, so logging the dashboard in can sign you out
of the official app. Avoid the clash by giving the dashboard its **own** CarLinko account:

1. Make a second CarLinko account (different email).
2. From your main account, **Me → Authorisation → +** and authorise the second account's email
   to your car.
3. Log the dashboard into the second account; keep the app on your main account.

> Heads-up: the in-app *Authorisation* screen describes Bluetooth control sharing — confirm the
> authorised account can also pull the car over the **cloud** (run `python setup.py` on it; if
> auto-detect finds the vehicle, you're good). If it can't, the alternative is to just use one
> account and accept the occasional re-login.

### Quick start — Docker (recommended)
```bash
docker compose up -d        # then open http://localhost:8088
```
On first open the dashboard shows a **login page** — enter your CarLinko **email + password** and
it logs in and **auto-detects your car** (vehicle id, device SN, VIN, plate, model). That's it.
Prefer the terminal? `docker compose run --rm web python setup.py` does the same interactively.
Everything that persists (creds, token, database) lives in `./data`.

### Quick start — Python (no Docker)
```bash
pip install requests websocket-client
cd tools
python setup.py                # interactive config + login + auto-detect car
python logger.py --adaptive    # record telemetry (fast when awake, slow when parked)
python server.py 8088          # dashboard at http://<host>:8088
```
Prefer not to use the helper? `cp creds.example.json tools/creds.json && chmod 600 tools/creds.json`
and fill it in by hand. `creds.json` and `token.txt` are gitignored — never commit them.

For always-on use, install the provided systemd units
([carlinko-logger.service](tools/carlinko-logger.service),
[carlinko-web.service](tools/carlinko-web.service)) and reach the dashboard over Tailscale so it
stays private without exposing anything to the internet.

### `creds.json` reference
| key | required | what |
| --- | --- | --- |
| `email`, `password` | ✅ | your CarLinko login (plaintext over TLS; stored locally only) |
| `region` | | API region, default `sea` |
| `vehicle_id`, `device_sn` | auto | your vehicle id + device serial — **`setup.py` fills these for you** |
| `vehicle` | auto | `{plate, model, vin}` — auto-detected; UI hides plate+VIN by default |
| `battery_kwh`, `wltp_kwh_100`, `tariff_idr` | | per-model / local overrides (default to J5 values) |
| `gmaps_key` | | Google Maps key — enables trip planner + SPKLU map (else OSM fallback) |
| `dashboard_password` | | set it (login page → Advanced) to lock the dashboard behind a password — **do this if the URL is reachable from the internet** |

## Where to run it

It needs a host that's on **24/7** (the logger polls continuously to build trends and charge
history). **A phone alone won't do it** — iOS can't run a background server at all, and Android
(Termux) gets killed by battery management. So the host runs elsewhere and your phone is just the
browser (add it to your home screen as a PWA).

| Host | Cost | Notes |
| --- | --- | --- |
| A spare PC / old laptop / **Raspberry Pi** at home | free | best privacy; reach it over [Tailscale](https://tailscale.com) |
| A small **VPS** (Hetzner, Contabo, DigitalOcean…) | ~$4/mo | easiest always-on; keep it private with Tailscale, or set a `dashboard_password` |
| **Fly.io / Railway / Render** free tier | free | deploy the Docker image; set a `dashboard_password` |
| **Oracle Cloud Free / Google e2-micro** | free | always-on free VM |

> **Public hosting = set a dashboard password.** On a private/home/Tailscale host you can leave it
> open. The moment the URL is reachable from the internet, set a `dashboard_password` (login page →
> Advanced) so only you can open the dashboard.

### Per-OS setup
The Docker path is identical on every OS — install Docker, then `docker compose up -d` and open
`http://localhost:8088`:
- **macOS / Windows**: install [Docker Desktop](https://www.docker.com/products/docker-desktop/), open it, then run the two commands in Terminal / PowerShell from the cloned repo folder.
- **Linux**: `sudo apt install docker.io docker-compose-plugin` (or your distro's equivalent), then the same two commands.

No Docker? Install **Python 3.10+** ([python.org](https://www.python.org/downloads/) on macOS/Windows, `sudo apt install python3 python3-pip` on Linux) and use the *Quick start — Python* steps above.

### Set it up with an AI coding agent
If the terminal isn't your thing, paste this into an AI coding agent (Claude Code, Cursor, etc.)
running on the machine that will host it:

```text
Set up the open-source project https://github.com/GodrezJr2/j5-ev-dashboard on this machine.
Clone it, then bring it up with Docker (docker compose up -d). It serves a login page on
http://localhost:8088 — tell me the URL when it's running. I'll enter my CarLinko email and
password there myself; do not ask me for them. If Docker isn't available, fall back to the
Python quick-start in the README (pip install requests websocket-client, then run
tools/server.py and tools/logger.py). If the host is reachable from the internet, remind me to
set a dashboard password on the login page's Advanced section.
```

## Going multi-user

This is intentionally **single-tenant per instance**. The clean way to let other owners use
it is to have **each of them run their own instance** with their own `creds.json` — not to
host one service holding everyone's credentials. Different models can override
`battery_kwh` / `wltp_kwh_100` / `tariff_idr`, and the vehicle name/VIN/plate come from
`creds.json`, so the app already adapts per car.

## Project layout
- `tools/` — Python backend (`server.py`, `logger.py`, `auth.py`) + reverse-engineering utilities
- `web/` — the PWA (single `index.html` + vendored `leaflet.*`, `slot-text.js`)
- `docs/` — API map and decompiled signing notes (secrets redacted)
- `PRODUCT.md`, `DESIGN.md` — product + visual design notes

## Contributing
Other Jaecoo / CarLinko owners welcome — a [compatibility report](https://github.com/GodrezJr2/j5-ev-dashboard/issues/new?template=compatibility.md)
(does it work on your car/region?) is the most useful thing right now. See
[CONTRIBUTING.md](CONTRIBUTING.md), and [SECURITY.md](SECURITY.md) for privacy/security.
Questions → [Discussions](https://github.com/GodrezJr2/j5-ev-dashboard/discussions).

## License
[MIT](LICENSE). Not affiliated with Jaecoo, Chery, or CarLinko. Trademarks belong to their owners.
