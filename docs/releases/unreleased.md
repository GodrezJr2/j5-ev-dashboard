# Unreleased

- Added Malaysia maintenance timetables and nearby service centre lookups through
  `GET /api/maintenance-guide` and `GET /api/service-centres`.
- Added the `maintenance_guide` and `service_centres` capability IDs to public
  `/api/status`. Demo mode advertises these two implemented reads.
- `/api/summary` remains at `api_version: 1`; its payload contract is unchanged.
- Voltmoss can open the maintenance guide from the Vehicle tab. Older clients
  can ignore the new capability IDs and routes.
