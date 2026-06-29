# Contributing

Thanks for taking a look! This started as a personal reverse-engineering project for my own
Jaecoo J5 EV and grew into something other owners can use. Contributions — especially from people
with **other CarLinko cars, regions, or firmware** — are very welcome.

## Good first contributions

- **Confirm compatibility.** Run it on your car and open a
  [compatibility report](https://github.com/GodrezJr2/j5-ev-dashboard/issues/new?template=compatibility.md):
  model, region, what worked, what didn't. This is the single most useful thing right now — it tells
  us which byte offsets and assumptions hold beyond the J5.
- **Fix a telemetry offset** for a different model (battery / range / odometer live at fixed byte
  positions in `tools/server.py` → `decode()`; they may differ on other cars).
- **Improve a translation** (`README.id.md`, or UI strings in `web/index.html`).
- **Docs / setup friction** — anything that tripped you up is probably tripping up others.

## Before you start

- Skim **[README.md](README.md)** (architecture + setup) and **[docs/api-map.md](docs/api-map.md)**
  (the reverse-engineered API).
- Try **demo mode** to explore the UI without an account: `cd tools && python server.py --demo`.

## Pull requests

1. Keep changes focused — one feature/fix per PR.
2. The server is **stdlib-only** (`http.server`, `sqlite3`); please don't add web-framework
   dependencies. The only runtime pip deps are `requests` + `websocket-client` (for the logger).
3. **Never** include `creds.json`, `token.txt`, tokens, API keys, your VIN or plate in a commit,
   screenshot, or log paste. Redact before posting.
4. If you touch telemetry decoding, say which car/region you validated against.

## Ground rules

- Be honest about accuracy. This project's whole point is matching the real car/receipts — don't
  paper over a guess as a fact. Mark assumptions as assumptions.
- This is reverse-engineering for **personal, interoperability** use. Don't add anything that
  attacks CarLinko's infrastructure, scrapes other users' data, or abuses the API at scale.

Questions? Open a [Discussion](https://github.com/GodrezJr2/j5-ev-dashboard/discussions).
