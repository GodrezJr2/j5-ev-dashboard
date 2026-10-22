# Malaysia maintenance and service directory

The `GET /api/maintenance-guide` response is a market-specific catalogue. It
contains all 25 variants found in the published Malaysian Chery, OMODA JAECOO,
and iCAUR schedules checked on 22 October 2026. Each stop retains the
manufacturer's kilometre and month milestone, required replacement items,
recommended items, and published prices in MYR. The month or kilometre limit
applies, whichever comes first. Prices are estimates and can change at a
service centre.

| Group | Variants | Published source |
| --- | ---: | --- |
| Chery (Omoda E5, Omoda 5, O5, Tiggo Cross HEV/1.5T, Tiggo 7 Pro/PHEV, Tiggo 8/Pro/PHEV, Tiggo 9) | 11 | [Chery maintenance library](https://www.chery.my/after-sales/maintenance/) |
| OMODA JAECOO (J5 EV/2WD, J7 2WD/AWD/PHEV, J8 2WD/AWD, C9 2WD/AWD/PHEV) | 10 | [OMODA JAECOO service schedules](https://omodajaecoo.com.my/services) |
| iCAUR (03 RWD/iWD, V23 RWD/iWD) | 4 | [iCAUR 03](https://www.icaur.com.my/models/icaur-03) and [V23](https://www.icaur.com.my/models/icaur-v23) model pages |

Each model's `source` field links directly to its official PDF. The exact
price date is returned as `price_date`. Chery's machine-readable transcription
is stored in `tools/maintenance_chery_my.json`. Other schedules are encoded in
`tools/maintenance.py`. New models must have an official Malaysian source
before being added. Ambiguous drive variants require explicit selection in
the app.

`GET /api/service-centres` ranks the manufacturer's published service
directory by distance from the user's coordinates. The captured directory
contains 63 Chery, 50 OMODA JAECOO, and 18 iCAUR service locations from
their [Chery](https://www.chery.my/dealer-locator/),
[OMODA JAECOO](https://omodajaecoo.com.my/dealer-locator), and
[iCAUR](https://www.icaur.com.my/dealers) locators. The API reports
`verified_for_model: false` because a brand directory alone does not verify
that a particular centre can service every model; users should confirm before
booking. The original locator and directions are linked in the app.

Run `python3 tools/maintenance_selftest.py` after changing the schedule data.
