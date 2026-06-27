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
