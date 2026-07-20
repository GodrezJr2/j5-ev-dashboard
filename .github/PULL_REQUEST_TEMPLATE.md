<!-- Thanks for contributing. Delete any section that doesn't apply. -->

## What this changes

<!-- One or two sentences. What does it do, and why? -->

Fixes #

## How it was tested

<!-- Be specific. "Ran it" is fine if you say on what. -->

- [ ] Ran against my own car — model / year / region:
- [ ] Ran in demo mode (`python server.py --demo`)
- [ ] Checked the dashboard in a browser
- [ ] Not applicable (docs / tooling only)

## If you touched telemetry decoding

The whole point of this project is that the numbers are true, so decoding changes need evidence.

- **Which car and region did you validate against?**
- **What did the car's own dashboard say, versus what the app now shows?**
- **Is this confirmed, or inferred from a single sample?** Say so plainly — an inferred offset is
  still welcome, it just needs to be labelled as inferred rather than shipped as fact.

## Checklist

- [ ] No `creds.json`, `token.txt`, tokens, API keys, VIN, plate or location data in the diff,
      screenshots, or logs
- [ ] Anything uncertain is described as uncertain, in the code comment and the UI
- [ ] Existing cars still work — this doesn't assume everyone drives what I drive
      (defaults still sane for a BEV, for Indonesia, for indirect TPMS, etc.)
- [ ] Docs updated if behaviour or config changed (`README.md`, `README.id.md`,
      `creds.example.json`, `docs/api-map.md`)

## Screenshots

<!-- For UI changes. Redact your plate and VIN — the app's eye-toggle hides both. -->
