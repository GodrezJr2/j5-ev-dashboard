# DESIGN.md

**Theme**: light, warm. Instrument-panel calm, not techy. (Scene: daylight glance on a phone.)

**Color strategy**: Restrained. Warm-tinted neutrals + one accent (deep automotive green),
plus semantic amber/red for tyre warnings only. Accent carries < 10% of the surface.

OKLCH tokens (never pure #000/#fff; neutrals tinted warm):
- `--canvas`  oklch(0.972 0.006 95)   warm paper background
- `--surface` oklch(0.992 0.004 95)   raised panels
- `--ink`     oklch(0.27 0.012 95)    primary text (warm near-black)
- `--muted`   oklch(0.55 0.012 95)    secondary text
- `--faint`   oklch(0.70 0.010 95)    tertiary / units
- `--line`    oklch(0.90 0.008 95)    hairlines
- `--accent`  oklch(0.52 0.10 158)    deep moss green: battery, positive, current
- `--warn`    oklch(0.74 0.13 70)     amber: tyre slightly out of range
- `--bad`     oklch(0.58 0.16 27)     red: tyre well out of range / alerts

**Typography**: one family, system stack (`-apple-system, "SF Pro Text", Inter, system-ui`).
Fixed rem scale, ratio ~1.2. Strong weight contrast (700 data, 600 labels, 450 body).
Tabular numerals (`font-variant-numeric: tabular-nums`) for all numbers. Overlines in
small caps with letter-spacing.

**Layout**: mobile-first single column, max 460px. Sections separated by whitespace and
hairlines, not nested cards. Vary spacing for rhythm. At most one level of surface. The
battery SoC arc is legitimate data-viz (not decoration) but solid color, thin, no gradient.

**Components**: states for everything interactive; skeleton, not spinner. Empty/idle states
teach ("tyres report only while driving"). Same vocabulary throughout.

**Motion**: 150-250ms, ease-out, state-only. Number/arc transitions on update. No page-load
choreography.

**Bans honored**: no gradient text, no glass, no side-stripe borders, no glossy hero-ring
template, no neon, no em dashes.

---

# V2 surface (`web/v2.html`) — BYD-grammar porcelain, adaptive light and dark

A second front end on the same backend. v1 stays the default at `/`; V2 lives at `/v2.html` and
shares the manifest, auth gate, `/api/summary`, `/api/control`, `/api/history`.

**Register**: the BYD Auto app (Seal 5 / Sealion 7), pinned by the owner. A cool blue-grey
gradient hero owning the top of the screen, the car's own render as the subject, a huge centred
range numeral, white elevated cards on a porcelain ground, round quick actions floating on the
hero seam. Two tabs, right-slide detail pages.

**Theme**: adaptive, in the same grammar both ways. The system preference decides by default;
`Account > Appearance` writes an Auto/Light/Dark override to `localStorage` and
`<meta name="theme-color">` follows. Every colour is defined on bare `:root`, redefined under
`@media (prefers-color-scheme: dark)` guarded as `:root:not([data-theme="light"])`, and again
under `:root[data-theme="dark"]` so the manual toggle wins in both directions.

OKLCH tokens (light / dark): `--bg` 0.963 / 0.175 · `--card` 1.0 / 0.232 · `--ink` 0.25 / 0.960 ·
`--mut` 0.46 / 0.750 · `--fnt` 0.50 / 0.625 · `--line` 0.915 / 0.315 · `--heroA` 0.885 / 0.300.
`--acc` is the product green (battery, charging, good states); `--blue` is reserved for a PHEV's
fuel bar and an active A/C. Contrast: `--mut` ~5.2:1 and `--fnt` ~4.6:1 on porcelain.

**Scales**: radius 10/14/18/24/full; space 4/8/12/16/22/30/44; one ease
`cubic-bezier(.16,1,.3,1)`; durations 140/220/340ms.

**Layout**: hero = model name and a status line (live dot, state, freshness) at the top left, a
74px centred range numeral, a state-of-charge bar, then the car render with four round quick
actions on the seam. Below: a climate tile with an inline stepper, Doors and Tyres stacked
beside it, Battery and Charging as half-width cards, then full-width rows for Consumption,
Distance and Seats.

A second blue fuel bar exists in the code and appears only when the backend reports a tank. The
Seal 5 screen this follows is a PHEV and shows two bars; drawing a second one on a BEV would be
stating a number the car never sent.

**Energy chart**: seven daily bars, not a line. A line is the wrong mark when most weeks have
days with no driving — joining across those gaps invents a trend, and breaking the line leaves
stubs and orphan dots. A faint full-height track keeps a no-driving day visible as an empty slot,
the WLTP rating is a dashed reference whose label sits at the right edge where no bar label can
reach it, and bars are measured from zero because they encode a magnitude.

**Doors**: one shared top-view diagram, used by Doors and Tyres. Every moving panel pivots about
a real hinge — doors swing 34°, and the liftgate and sunroof foreshorten toward their hinge,
which is what a lifting panel looks like from directly above. The page paints shut first and
releases the open panels on the next frame, so entering it plays the movement.

**Tyres**: with indirect TPMS all four wheels render in the same state, because `/api/summary`
returns all four entries as `psi: null` and a single overall status. Colouring them independently
would invent per-wheel knowledge. A caption says so. Cars with real sensors get the other branch.

**Charging view**: the hero swaps to a photo of this car plugged in, because the charge port is on
the front-left corner and is not visible on the three-quarter render. The photo's background was
removed in an image tool by the owner, after removing it in code failed: the studio backdrop
measures 196 mean luminance against the bonnet's 198, so no tone threshold separates them, and
the backdrop carries a gradient, so a local-variance mask marked 67% of the frame as structure.
A green trace runs along the photograph's own cable — located by detecting its dark opaque pixels
— from the nozzle holster, down the slack loop, along the ground and into the port, so the pulse
reads as energy flowing into the car. `?cable=1` previews it without a live session.

**Navigation**: two tabs, right-slide detail pages, deep links at `#doors` `#tyres` `#energy`
`#ac` `#batt` `#chg` `#dist` `#flex`, `history.pushState` so hardware and browser back close a
page, an edge-swipe-back gesture, Escape, and a bottom confirm sheet in place of `window.confirm`
(which blocks the whole PWA).

**Motion**: state-bearing only, transform and opacity, one ease. A first-paint rise with a stagger,
a needle-style count-up on the range numeral, a brief accent warm on any value the poll changed,
bars that grow from the baseline, chart strokes that draw themselves, and an expanding ring on the
live dot — the last only while the car is actually online. `prefers-reduced-motion` flattens the
CSS, and the JS helpers check the same query.

**Honesty rules inherited**: the windows row stays hidden on the J5 (byte 8 quirk, #5); indirect
TPMS reports status only; seats read "Not available" when the car reports none; the A/C
temperature opcode is labelled as pending on-car verification; and the door-corner mapping is
labelled as E5-derived and unverified on this car.

**Bans honored**: no gradient text, no glass, no neon, no decorative shadow, no em dashes.
