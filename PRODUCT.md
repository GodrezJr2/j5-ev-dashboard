# PRODUCT.md

**Product purpose**
A self-hosted dashboard for one car: a Jaecoo J5 EV, fed by the reverse-engineered
CarLinko telematics API. It shows battery, range, tyre status (indirect TPMS — status only,
no PSI), and how far the owner drove (day/week/month) plus charge counts. It exists because
CarLinko's own app hides the real numbers (tyres only show "normal/abnormal"; no trip totals).

**Register**: product. The design serves a quick glance-and-go task, not a brand statement.

**Users**
One owner ("Jay"), Jakarta. Opens it from the iPhone home screen (installed as a PWA over
Tailscale), usually in daylight, for a few seconds at a time: "battery ok? tyres ok? how
far today?" Occasionally sits longer to look at weekly/monthly trends.

**Tone**
Calm, precise, trustworthy, like a well-made instrument. Honest about data it doesn't have
yet (parked tyres, no drive today) instead of faking it. Quietly premium, never flashy.

**Anti-references** (do not look like these)
- Tesla-app dark mode with neon-green accents.
- Generic EV/IoT app: cyan-on-black, glowing rings, glass cards.
- Crypto/trading dashboards.
- SaaS hero-metric template (giant gradient number + supporting stat row).
- Clinical "white + mint/teal" health-app cleanliness.

**Strategic principles**
- Glanceable first: the three things that matter (battery, tyres, distance) read in one second.
- Data honesty: show "—" / "parked" / "drive to see live PSI" rather than guess.
- Light, warm, restrained. One accent. Whitespace and rhythm over boxes.
