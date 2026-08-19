# Scout Report — Mobile Design Spec ("The Dossier")

Date: 2026-08-19
Status: Approved
Scope: Visual and structural design for rendering football-scout skill output (Branch A Full Profile and Branch B Rapid Verdict) as a mobile-first, single-column report. This spec defines layout, components, and content mapping. It does not cover data collection (owned by the skill) or any backend.

---

## 1. Concept

A printed scouting dossier rendered for a phone. Warm paper ground, ink typography, hairline rules instead of cards, one pitch-green accent.

**Governing rule:** every closed accordion row already states its conclusion — a rating chip, a gap type, a risk flag. Expanding reveals *evidence*, never the *answer*. Scrolling the fully collapsed report reads the entire verdict chain in ~10 seconds.

**Order principle:** inverted pyramid. The verdict tier renders above the evidence, inverting the skill's report-template order (verdict last). The underlying data keeps template order; only presentation inverts.

---

## 2. Foundations

### 2.1 Palette

| Token | Value | Use |
|---|---|---|
| `--paper` | `#FAF7F2` | Page background |
| `--ink` | `#1C1B18` | Primary text |
| `--hairline` | `#E4DFD5` | 1px rules, borders |
| `--accent` | `#1E5A3C` | Pitch green: open-state rules, active chips, percentile bars |
| `--strong` | `#1E5A3C` | Strong rating (shares accent) |
| `--adequate` | `#8A857B` | Adequate rating, secondary text |
| `--concern` | `#A63D2F` | Concern rating, red flags, injury High |

Tier colors: Pass = `--concern`, Watch = `--adequate`, Shortlist = `--accent`, Recommend = `--ink` (heaviest weight = final word).

No shadows, no card fills, no gradients. Sections separated by 1px hairline rules; the verdict band uses a heavier 2px rule top and bottom.

### 2.2 Typography

| Font | Role | Notes |
|---|---|---|
| **Fraunces** | Display: player name (34px/1.1, weight 560, optical size high), tier word (28px) | Variable font, `SOFT`/`WONK` axes at defaults |
| **Newsreader** | Prose: corner paragraphs, rationale, evidence text (16px/1.55) | Serif body suits dossier reading |
| **IBM Plex Mono** | All numerals, section labels, chips, fact grid, table rows (11–13px, small-caps labels via `text-transform: uppercase; letter-spacing: 0.08em`) | `font-variant-numeric: tabular-nums` mandatory so metric columns align |

### 2.3 Layout constants

- Viewport target: 360–430px. Single column always.
- Side gutters: 24px. Max content width: 480px, centered — on desktop the report reads as a paper column, no reflow to multi-column.
- Vertical rhythm: 16px base; 24px between rule-separated sections.
- Touch targets: ≥48px for all interactive rows.

---

## 3. Full Profile layout (Branch A)

Section order, top to bottom:

```
┌──────────────────────────────────┐
│ SCOUT REPORT · FULL PROFILE      │  1 masthead
│ 19 AUG 2026                      │
│                                  │
│ Viktor Andersson                 │  2 identity
│ ST / LW · Malmö FF · Allsvenskan │
│ ──────────────────────────────── │
│ AGE 21    CONTRACT 06/27  €4.5M  │    fact grid
│ OPTION +1 INJURY LOW             │
│ ================================ │
│ SHORTLIST                        │  3 verdict band
│ Next: live obs vs AIK, 30 Aug    │
│ ▸ Rationale                      │
│ ================================ │
│  0.48      0.61      74%         │  4 signal row
│  xG/90     PrgC/90   pctl bars   │
│ ──────────────────────────────── │
│ DORMANT POTENTIAL  [METRIC GAP] ▸│  5 dormant potential
│ ──────────────────────────────── │
│ FOUR CORNERS   ●●◐○              │  6 four corners
│   Technical      [STRONG]      ▸ │
│   Tactical       [STRONG]      ▸ │
│   Physical       [ADEQUATE]    ▸ │
│   Psychosocial   [CONCERN]     ▸ │
│ ──────────────────────────────── │
│ FULL METRICS                   ▸ │  7 metrics
│ EYE TEST       S S A S C       ▸ │  8 eye test
│ BACKGROUND     [⚑ INJ LOW]     ▸ │  9 background
│ PHILOSOPHY FIT [4/5 FIT]       ▸ │  10 philosophy
│ ──────────────────────────────── │
│ METHODS: ▣data ▣video ▣behav     │  11 methods footer
│          ▣bkgd □live             │
└──────────────────────────────────┘
```

### 3.1 Masthead
Mono small-caps: `SCOUT REPORT · FULL PROFILE` + report date. No logo, no imagery.

### 3.2 Identity block
- Player name in Fraunces 34px.
- One line: `Primary / Secondary position · Club · League` (mono, 12px).
- Fact grid below a hairline: 2 rows × 3 cells, mono. Cells: AGE (years, DOB in expanded metrics), CONTRACT (expiry MM/YY), MARKET VALUE (€), OPTION (+1 / —), INJURY (LOW/MED/HIGH colored by risk), REPORT DATE. Labels 10px above values 14px.

### 3.3 Verdict band
The primary glance element. 2px rules top and bottom.
- Tier word in Fraunces 28px, colored per tier, with a 3px underline in the same color.
- **Next step** line always visible (mono, 13px): the specific action, never "monitor".
- **Rationale** accordion beneath: closed = `▸ Rationale`; open = 2–3 sentences in Newsreader, including the primary risk.
- Recommend tier only: a mono footnote line `LIVE OBS: [completed date / scheduled fixture]` — enforces the framework rule that Recommend requires live observation.

### 3.4 Signal row
Three most diagnostic metrics for the player's position, per SOURCES.md Positional Metric Priority. Each cell: value in mono 24px, label 10px beneath, and a 3px-tall percentile bar (accent fill on hairline track) with the percentile number at the bar's end. Not an accordion.

### 3.5 Dormant potential
Closed: `DORMANT POTENTIAL` label + chip `[METRIC GAP | SYSTEM GAP | AGE GAP | NONE]`. Gap chips render in accent; `NONE` in `--adequate`.
Open: evidence paragraph (≥2 data points cited). For `NONE`: the rule-out reasoning for each gap type checked. For age gap on 16–22 players: one line noting the Relative Age Effect adjustment (birth month).

### 3.6 Four Corners
- Header row: `FOUR CORNERS` + 4-dot glance strip (● Strong filled green, ◐ Adequate half grey, ○ Concern outlined red — order: Tech, Tact, Phys, Psych).
- Four accordion rows. Closed: corner name (mono) + rating chip. Open: ≥2 sentences Newsreader prose citing specific metrics and video observations, indented 12px behind a 1px accent rule.
- Psychosocial open state additionally lists its ≥2 sourced signals as bulleted mono lines with source attribution; a thin-data caveat renders in `--concern` if applicable.

### 3.7 Full metrics
Closed: `FULL METRICS` label only.
Open: rows grouped by source (FBREF, UNDERSTAT, SOFASCORE, SCOUTINGSTATS.AI, TRANSFERMARKT), each row: metric name · value (tabular mono) · percentile bar where available · sample size note where relevant (matches, minutes).
**Divergence rows:** any ScoutingStats↔FBref (or other source-to-source) contradiction is marked with a `≠` prefix in `--concern` and a one-line interpretation beneath. Divergence is the finding — disagreeing rows get *more* visual weight, never suppression.
Understat unavailable for the league → explicit `UNDERSTAT: N/A (league not covered)` row.

### 3.8 Eye test
Closed: `EYE TEST` + five score letters `S S A S C` colored per score (Strong/Adequate/Concern), fixed order: Movement off ball, Body shape, First touch, Pressing, Communication.
Open: five rows — criterion name, score chip, one-sentence observation, and a small `→ CORNER` mapping tag. Footer line: minutes watched + footage type (highlights/full match).

### 3.9 Background
Closed: `BACKGROUND` + flag chips: injury risk `[⚑ INJ LOW/MED/HIGH]`, and when applicable `[CONTRACT <6MO]` acquisition-window chip, `[INTEREST: n CLUBS]`.
Open: injury detail (type, matches missed %, dates), contract expiry + option year confirmation, transfer interest summary, behavioral search results (the five search strings' outcomes; "no red flags found" stated as neutral, red flags in `--concern` and bolded).

### 3.10 Philosophy fit
Closed: `PHILOSOPHY FIT` + score chip `[n/m FIT]` (m = number of Philosophy dimensions: role, system function, age bracket, each hard constraint).
Open: the Philosophy statement (Newsreader, italic) followed by a per-dimension checklist — `✓ FIT` (accent) / `✗ MISFIT` (concern) with one line of reasoning each. Any hard-constraint misfit also forces a note in the verdict rationale.

### 3.11 Methods footer
Five chips: `▣ DATA ▣ VIDEO ▣ BEHAVIORAL ▣ BACKGROUND □ LIVE`. Unused methods render outlined + `--adequate`. If live not conducted but required, footnote: `LIVE OBSERVATION REQUIRED BEFORE RECOMMEND`.

---

## 4. Rapid Verdict layout (Branch B)

Same masthead (chip reads `· RAPID`), same identity block condensed (name 28px, fact grid single row: AGE / CONTRACT / VALUE). Then the six B3 fields as one rule-separated column, **no accordions** — fits one screen by construction:

1. **Tier band** — identical component to §3.3, without the rationale accordion.
2. **Signal row** — identical component to §3.4 (three metrics with percentile context).
3. **Gap signal** — one line: gap chip + one-sentence evidence.
4. **Constraint check** — one line: `FITS` / `FAILS` chip + which dimension.
5. **Rationale** — 2–3 sentences, Newsreader, always visible.
6. **Escalate** — mono line: `ESCALATE TO FULL PROFILE: YES/NO — reason`.

Triage across multiple players = a vertical stack of Rapid cards separated by 2px rules.

---

## 5. Accordion component

- **Semantics:** native `<details>`/`<summary>`. Zero-JS functional baseline; keyboard and screen-reader behavior for free.
- **Closed row:** 48px min height. Left: mono small-caps label. Right: conclusion chip(s) + thin chevron (`›` rotated 90° when open, CSS transition 150ms — the only animation in the design).
- **Open state:** content indented 12px behind a 1px `--accent` vertical rule. Prose in Newsreader; data rows in mono.
- **Multi-open:** sections stay open independently (no auto-collapse) — scouts compare corners side by side.
- **Chips:** mono 10px uppercase, 1px border in their semantic color, transparent fill, 2px 6px padding. No filled backgrounds except the tier underline.

## 6. Sticky mini-header

On scroll past the verdict band, a 40px bar pins to top: `Surname · [TIER]` on paper background with bottom hairline. Implementation: CSS scroll-driven animation where supported; small IntersectionObserver fallback. This is the only JS in the design.

---

## 7. Content mapping — template field → slot

Every A6 template field has a named slot; none may render blank.

| Template field | Slot |
|---|---|
| Player / Position / Age / Club / League | §3.2 identity |
| Contract until / Option year | §3.2 fact grid + §3.9 open |
| Market value + date | §3.2 fact grid |
| Report date / Branch | §3.1 masthead |
| Observation methods checklist | §3.11 footer |
| Philosophy fit prose | §3.10 open |
| Four corners prose + ratings | §3.6 |
| Dormant potential type + evidence | §3.5 |
| Verdict tier / rationale / next step | §3.3 |
| Raw metrics + percentiles + divergences | §3.4 signal row + §3.7 |
| Eye test scores + observations | §3.8 |
| Behavioral signals / injury / interest | §3.9 |

Missing data renders as an explicit `N/A — reason` row in mono `--adequate`, never as an absent row.

---

## 8. Deliberate exclusions

- No radar charts — percentile bars carry the same data legibly at 380px.
- No club crests, kit colors, or player photos.
- No tabs, bottom nav, or horizontal scrolling.
- No animation beyond chevron rotation and the sticky-header pin.
- No dark mode in v1 (the light dossier *is* the identity; existing desktop reports remain dark).

## 9. Error / edge handling

- Understat league gap, sub-500-minute sample, or any skipped source → explicit flagged row (§3.7), never silent omission.
- Recommend tier without live observation data → the report must not render Recommend; falls back to Shortlist with footnote (mirrors framework rule).
- Long names / double-barreled clubs: name wraps to two lines before shrinking; fact grid cells truncate values with full text on the expanded rows.

## 10. Future implementation notes (non-binding)

Single-file HTML per report, matching the repo's existing convention (`index.html`, `midfielder-comparison.html`): inline CSS, fonts via Google Fonts with `font-display: swap`, populated by the skill at report-composition time (Step A6 / B3).
