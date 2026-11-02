# Unreleased

- Added Malaysia maintenance timetables and nearby service centre lookups through
  `GET /api/maintenance-guide` and `GET /api/service-centres`.
- Added the `maintenance_guide` and `service_centres` capability IDs to public
  `/api/status`. Demo mode advertises these two implemented reads.
- `/api/summary` moves to `api_version: 2`: `history[].kwh` and `.eff` are net of regen; the
  drops-only (head-unit) figures are now `kwh_hu` / `eff_hu`. `energy.week_consumption` (and
  `energy.consumption` when the car reports none) is net of regen too. `/api/history` changed the same way.
  See the version table in `docs/api-map.md`.
- `/api/controls` keeps `seatHeat` / `seatVent` beside the new `seats`, for clients that read them.
- Voltmoss can open the maintenance guide from the Vehicle tab. Older clients
  can ignore the new capability IDs and routes.
