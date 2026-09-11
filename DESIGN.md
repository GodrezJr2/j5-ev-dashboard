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

# V2 surface (`web/v2.html`) — "Instrument", adaptive light and dark

A second front end on the same backend. v1 stays the default at `/`; V2 lives at `/v2.html`
and shares the manifest, auth gate, `/api/summary`, `/api/control`, `/api/history`.

**Register**: a well-made gauge, not an app screen. The range numeral *is* the first viewport;
everything else is a hairline list beneath it. Refuses both the stat-tile dashboard and the
card-grid car app. (The previous v2 was a pinned BYD Auto clone; it is kept at
`web/v2.byd.bak.html` for reference and is not deployed.)

**Theme**: adaptive. Light is cool paper, dark is graphite. The system preference decides by
default; `Account > Appearance` writes an Auto/Light/Dark override to `localStorage`, and
`<meta name="theme-color">` follows. Every colour is defined on bare `:root` first, redefined
under `@media (prefers-color-scheme: dark)` guarded as `:root:not([data-theme="light"])`, and
again under `:root[data-theme="dark"]` so the manual toggle wins in both directions.

OKLCH tokens (light / dark):
- `--bg` 0.975 / 0.165 · `--bg-2` 1.0 / 0.205 · `--bg-3` 0.955 / 0.235
- `--ink` 0.22 / 0.955 · `--mut` 0.44 / 0.745 · `--fnt` 0.48 / 0.615
- `--line` 0.895 / 0.305 · `--hair` 0.93 / 0.255
- `--acc` 0.53 0.13 162 / 0.755 0.145 162 — product green, state only
- `--acc-ink` accent as text (darker in light mode so body-size accent text still passes)
- `--warn`, `--bad` for tyre and 12V alerts only

Contrast: `--mut` ~5.6:1 and `--fnt` ~4.8:1 on light; both comfortably above 4.5:1 on dark.
The previous v2's `--fnt` sat at ~3.2:1 and was used for every card subtitle.

**Scales** (all tokens, no ad-hoc values): radius 6/10/14/20/full; space 4/8/12/16/24/32/48;
one ease `cubic-bezier(.2,.8,.25,1)`; durations 140/220/320ms.

**Typography**: one system family. Weights are **400 / 500 / 600 only** — the 800-everywhere
wall of the previous v2 is gone. Display numerals at 72px / -0.04em with tabular figures;
labels are 10px uppercase at 0.18em tracking. Numbers are the loudest thing on every screen.

**Structure**: hairlines and whitespace, not cards. `.rows` groups of full-width `.row`
(icon, label, value, chevron) replace the 2-column tile grid. `.panel` exists only where a
chart or figure needs containment. No shadow is used as decoration; the only drop-shadows are
on the two car renders.

**Layout**: hero = model overline, 72px range, "estimated range", a rule, then a status strip
(live dot, SoC, state, freshness). The car's own render sits below it, then four hairline
quick-action circles with labels. A live charging strip appears only while charging. Below:
two groups — Vehicle (Climate with an inline stepper, Doors and windows, Tyres, Seats) and
Energy (Battery, Charging, Consumption, Distance).

**Navigation** (unchanged from the previous v2, by request): two tabs, right-slide detail
pages, deep links at `#doors` `#tyres` `#energy` `#ac` `#batt` `#chg` `#dist` `#flex`.
Added: `history.pushState` so hardware and browser back close a page, an edge-swipe-back
gesture from the left 30px, Escape, and a bottom confirm sheet in place of `window.confirm`
(which blocks the whole PWA).

**Motion**: state-bearing only, transform and opacity, one ease. A first-paint rise with a
26-40ms stagger; a needle-style count-up on the range numeral when a new reading arrives; a
brief accent warm on any row value the poll actually changed; chart strokes that draw
themselves with `stroke-dasharray`; a single expanding ring on the live dot and a breathing
charging bolt, both of which only run while the car is actually online or charging.
`prefers-reduced-motion` flattens the CSS animations, and the JS count-up and stagger check
the same query before running.

**Honesty rules inherited**: windows row hidden on the J5 (byte 8 quirk, #5) rather than
guessed; indirect-TPMS cars get status only; seats show "Not available" when the car reports
none; the A/C temperature opcode is labelled as pending on-car verification.

**Bans honored**: no gradient text, no glass, no glossy hero ring, no neon, no gradient
backgrounds, no decorative shadow, no em dashes.
