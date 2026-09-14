#!/usr/bin/env python3
"""Create data/football.db and seed it from the committed site artifacts.

Rerunnable: every run drops and recreates every table, then reseeds from the
HTML/JSON currently in the repo. This is the permanent bootstrap for a fresh
database, not a throwaway migration.

    python scripts/init_db.py

Seeding is delegated to the archetype modules in `scripts/pages/`.
"""

from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = Path(os.environ.get("FOOTBALL_DB") or ROOT / "data" / "football.db")

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pages  # noqa: E402

SCHEMA = """
-- ── Hub + shared player identity ────────────────────────────────────────────
-- One row per tracked player; hub card order = sort.
-- verdict_tier doubles as the hub card class ('shortlist'|'watch') and the
-- report tier suffix ('tier-watch'…). potential stores 'None'|'Age Gap'|
-- 'System Gap' (templates prefix 'Potential: '). The hub href is DERIVED as
-- {id}-report.html (verified: all 12 match), never stored.
CREATE TABLE players (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    short_name  TEXT NOT NULL,
    club_line   TEXT NOT NULL,
    pos_badge   TEXT NOT NULL,
    pos_class   TEXT NOT NULL,
    verdict_tier  TEXT NOT NULL,
    verdict_label TEXT NOT NULL,
    potential   TEXT NOT NULL,
    mins_base   TEXT NOT NULL,
    sort        INTEGER NOT NULL
);

CREATE TABLE card_stats (
    player_id TEXT NOT NULL,
    season    TEXT NOT NULL,
    idx       INTEGER NOT NULL,
    label     TEXT NOT NULL,
    val       TEXT NOT NULL,
    cls       TEXT NOT NULL,
    PRIMARY KEY (player_id, season, idx)
);

CREATE TABLE player_season (
    player_id TEXT NOT NULL,
    season    TEXT NOT NULL,
    mins      TEXT NOT NULL,
    PRIMARY KEY (player_id, season)
);

-- ── Season overlay → data/season-2627.{json,js} ─────────────────────────────
CREATE TABLE seasons (
    season    TEXT PRIMARY KEY,
    updated   TEXT NOT NULL,
    matchweek INTEGER NOT NULL
);

-- Three static signal labels per player, shared by every season.
CREATE TABLE signal_defs (
    player_id TEXT NOT NULL,
    idx       INTEGER NOT NULL,
    label     TEXT NOT NULL,
    PRIMARY KEY (player_id, idx)
);

CREATE TABLE season_signals (
    player_id TEXT NOT NULL,
    season    TEXT NOT NULL,
    idx       INTEGER NOT NULL,
    num       TEXT NOT NULL,
    pctl      TEXT NOT NULL,
    PRIMARY KEY (player_id, season, idx)
);

CREATE TABLE season_metrics (
    player_id TEXT NOT NULL,
    season    TEXT NOT NULL,
    idx       INTEGER NOT NULL,
    label     TEXT NOT NULL,
    val       TEXT NOT NULL,
    PRIMARY KEY (player_id, season, idx)
);

-- ── Hub comparison cards ────────────────────────────────────────────────────
-- `comment` is the hand-written '<!-- … -->' label above each card; it is not
-- derivable from the title, so it is stored to keep the hub byte-faithful.
CREATE TABLE comparisons (
    id            TEXT PRIMARY KEY,
    href          TEXT NOT NULL,
    type_class    TEXT NOT NULL,
    badge         TEXT NOT NULL,
    title         TEXT NOT NULL,
    subtitle_html TEXT NOT NULL,
    meta          TEXT NOT NULL,
    comment       TEXT NOT NULL,
    sort          INTEGER NOT NULL
);

CREATE TABLE comparison_chips (
    comparison_id TEXT NOT NULL,
    idx           INTEGER NOT NULL,
    label         TEXT NOT NULL,
    PRIMARY KEY (comparison_id, idx)
);

CREATE TABLE site_meta (
    key TEXT PRIMARY KEY,
    val TEXT NOT NULL
);

-- ── Report pages (1:1 with players) ─────────────────────────────────────────
-- A NULL column means "omit that element" or "inherit from players", which
-- preserves today's per-page deviations instead of normalising them away.
-- The hand-written casing/labelling of a report's verdict does NOT reliably
-- match its hub card badge, and the #mini chip class is not a function of
-- verdict_tier, so those are per-report overrides rather than derived values.
CREATE TABLE reports (
    player_id         TEXT PRIMARY KEY,
    pos_class         TEXT,
    date_line         TEXT NOT NULL,
    posline           TEXT NOT NULL,
    heading_name      TEXT,             -- <h1>/<title>; NULL ⇒ players.name
    crumb_name        TEXT,             -- NULL ⇒ players.name
    tier_label        TEXT,             -- §1 .tier text; NULL ⇒ players.verdict_label
    mini_name         TEXT,             -- NULL ⇒ players.short_name
    mini_chip_cls     TEXT,             -- independent of verdict_tier
    mini_chip_label   TEXT,             -- NULL ⇒ players.verdict_label
    dormant_chip_cls   TEXT NOT NULL,
    dormant_chip_label TEXT NOT NULL,
    philosophy_tally  TEXT NOT NULL,
    philosophy_chip_cls TEXT NOT NULL,
    sumright_inline   INTEGER NOT NULL, -- 1 ⇒ .dots/.eyes/background sumright on one line
    srcline           TEXT NOT NULL,
    facts_footnote    TEXT,
    signals_footnote  TEXT,
    closing_footnote  TEXT,
    liveobs_html      TEXT NOT NULL,
    nextstep_html     TEXT NOT NULL,
    philosophy_html   TEXT NOT NULL,
    bg_chip1_cls      TEXT NOT NULL,
    bg_chip1_label    TEXT NOT NULL,
    bg_chip2_cls      TEXT,
    bg_chip2_label    TEXT
);

-- Hand-written '<!-- … -->' annotation comments that vary per page, keyed by
-- the element they annotate ('signalrow', 'dots', 'eyes', 'background', …).
CREATE TABLE report_notes (
    player_id TEXT NOT NULL,
    key       TEXT NOT NULL,
    text      TEXT NOT NULL,
    PRIMARY KEY (player_id, key)
);

-- 6 per player.
CREATE TABLE report_facts (
    player_id TEXT NOT NULL,
    idx       INTEGER NOT NULL,
    label     TEXT NOT NULL,
    val       TEXT NOT NULL,
    risk_cls  TEXT NOT NULL,
    PRIMARY KEY (player_id, idx)
);

-- section ∈ 'verdict' (1–2 <p>), 'dormant' (1–3), 'background' (1).
-- One row per <p>, inner HTML only.
CREATE TABLE report_prose (
    player_id TEXT NOT NULL,
    section   TEXT NOT NULL,
    idx       INTEGER NOT NULL,
    html      TEXT NOT NULL,
    PRIMARY KEY (player_id, section, idx)
);

-- corner ∈ Technical|Tactical|Physical|Psychosocial.
CREATE TABLE report_corners (
    player_id  TEXT NOT NULL,
    corner     TEXT NOT NULL,
    dot_cls    TEXT NOT NULL,
    dot_title  TEXT,
    chip_cls   TEXT NOT NULL,
    chip_label TEXT NOT NULL,
    chip2_cls   TEXT,
    chip2_label TEXT,
    comment     TEXT,                -- hand-written annotation comment (lautaro, orri)
    prose_html TEXT NOT NULL,
    PRIMARY KEY (player_id, corner)
);

-- div.sig rows inside the Psychosocial corner and the Background section.
CREATE TABLE report_sig_bullets (
    player_id TEXT NOT NULL,
    section   TEXT NOT NULL,
    idx       INTEGER NOT NULL,
    src       TEXT NOT NULL,
    src_cls   TEXT NOT NULL,
    text      TEXT NOT NULL,
    text_cls  TEXT NOT NULL,
    PRIMARY KEY (player_id, section, idx)
);

-- Flat §7 stream. kind ∈ 'group' (label=header) | 'row' (label+val+classes)
-- | 'note' (label=note html).
CREATE TABLE report_metrics (
    player_id TEXT NOT NULL,
    idx       INTEGER NOT NULL,
    kind      TEXT NOT NULL,
    label     TEXT NOT NULL,
    label_cls TEXT NOT NULL,
    val       TEXT NOT NULL,
    val_cls   TEXT NOT NULL,
    PRIMARY KEY (player_id, idx)
);

-- 5 per player. letter_cls NULL ⇒ render the muted '?' span (today's tresoldi
-- 'Inconclusive' hack, preserved). title emitted only when non-NULL.
CREATE TABLE report_eye_rows (
    player_id  TEXT NOT NULL,
    idx        INTEGER NOT NULL,
    criterion  TEXT NOT NULL,
    chip_cls   TEXT NOT NULL,
    chip_label TEXT NOT NULL,
    letter     TEXT NOT NULL,
    letter_cls TEXT,
    obs_html   TEXT NOT NULL,
    cornertag  TEXT NOT NULL,
    title      TEXT,
    PRIMARY KEY (player_id, idx)
);

CREATE TABLE report_eye_notes (
    player_id TEXT NOT NULL,
    idx       INTEGER NOT NULL,
    text      TEXT NOT NULL,
    PRIMARY KEY (player_id, idx)
);

CREATE TABLE report_checks (
    player_id TEXT NOT NULL,
    idx       INTEGER NOT NULL,
    mark_cls  TEXT NOT NULL,
    mark      TEXT NOT NULL,
    text      TEXT NOT NULL,
    PRIMARY KEY (player_id, idx)
);

-- 5 per player. "on" is a SQLite keyword: always quote it in SQL.
CREATE TABLE report_methods (
    player_id TEXT NOT NULL,
    idx       INTEGER NOT NULL,
    label     TEXT NOT NULL,
    "on"      INTEGER NOT NULL,
    PRIMARY KEY (player_id, idx)
);

-- ── H2H comparison archetype (4 pages) ─────────────────────────────────────
CREATE TABLE h2h_pages (
    id            TEXT PRIMARY KEY,      -- 'alvarez-lautaro' → {id}-comparison.html
    title         TEXT NOT NULL,
    label_pill    TEXT NOT NULL,
    header_sub    TEXT NOT NULL,
    chip1_cls   TEXT NOT NULL,
    chip1_label TEXT NOT NULL,
    chip2_cls   TEXT NOT NULL,
    chip2_label TEXT NOT NULL,
    chip3_cls   TEXT NOT NULL,
    chip3_label TEXT NOT NULL,
    p1_name TEXT NOT NULL,
    p1_short TEXT NOT NULL,
    p1_initial TEXT NOT NULL,       -- one-letter bar-name in metric rows ('A')
    p1_club_line TEXT NOT NULL,
    p1_color TEXT NOT NULL,
    p1_color_dim TEXT NOT NULL,
    p1_color_glow TEXT NOT NULL,
    p1_style_label TEXT NOT NULL,   -- '/* … */' comment beside --p1 in :root
    p1_tier_cls TEXT NOT NULL,
    p1_tier TEXT NOT NULL,
    p1_tier_big TEXT NOT NULL,      -- §verdict .verdict-tier-big text
    p1_verdict_html TEXT NOT NULL,
    p2_name TEXT NOT NULL,
    p2_short TEXT NOT NULL,
    p2_initial TEXT NOT NULL,
    p2_club_line TEXT NOT NULL,
    p2_color TEXT NOT NULL,
    p2_color_dim TEXT NOT NULL,
    p2_color_glow TEXT NOT NULL,
    p2_style_label TEXT NOT NULL,
    p2_tier_cls TEXT NOT NULL,
    p2_tier TEXT NOT NULL,
    p2_tier_big TEXT NOT NULL,
    p2_verdict_html TEXT NOT NULL,
    style_note TEXT,                -- trailing '/* … */' line inside <style>
    corners_intro_html TEXT NOT NULL,
    corners_header_comment TEXT,   -- §2 fc-grid header comment (alvarez-lautaro only)
    radar_axes    TEXT NOT NULL,   -- JSON array, labels may contain '\\n' (inacio)
    radar_p1      TEXT NOT NULL,   -- JSON array of ints (0–100)
    radar_p2      TEXT NOT NULL,
    radar_notes   TEXT,            -- normalisation comment block, verbatim in the JS
    radar_caption_html TEXT NOT NULL,
    radar_multiline INTEGER NOT NULL,  -- 1 ⇒ two-line axis renderer (inacio)
    radar_label_radius INTEGER NOT NULL,  -- axis-label offset (R + 22|26|30)
    radar_p1_on_top INTEGER NOT NULL,     -- 1 ⇒ p1 polygon drawn last (alvarez)
    methodology_html TEXT,             -- §3 context paragraph (inacio only)
    has_acquisition  INTEGER NOT NULL, -- 0 for balde-cancelo + inacio-lukeba
    rec_label    TEXT NOT NULL,
    rec_html     TEXT NOT NULL,
    footer_left  TEXT NOT NULL,
    footer_right TEXT NOT NULL
);

-- section ∈ identity|corners|metrics|radar|divergence|acquisition|verdict.
-- Stores the hand-written '<!-- N · TITLE -->' number and the role-qualified
-- label text per page (balde jumps 5→7, inacio renumbers to 6 sections —
-- preserved as data, not normalised).
CREATE TABLE h2h_sections (
    page_id TEXT NOT NULL,
    section TEXT NOT NULL,
    num     INTEGER NOT NULL,
    label   TEXT NOT NULL,
    PRIMARY KEY (page_id, section)
);

-- 8 per side; val_cls is the ''|'p1'|'p2' class on .id-fact-val and val_style
-- preserves any inline style="" verbatim (they never co-occur but are
-- different attributes).
CREATE TABLE h2h_id_facts (
    page_id   TEXT NOT NULL,
    side      TEXT NOT NULL,
    idx       INTEGER NOT NULL,
    label     TEXT NOT NULL,
    val       TEXT NOT NULL,
    val_cls   TEXT NOT NULL,
    val_style TEXT,
    PRIMARY KEY (page_id, side, idx)
);

CREATE TABLE h2h_corners (
    page_id       TEXT NOT NULL,
    side          TEXT NOT NULL,
    corner        TEXT NOT NULL,
    dot_cls       TEXT NOT NULL,
    badge_cls     TEXT NOT NULL,
    badge_label   TEXT NOT NULL,
    evidence_html TEXT NOT NULL,
    PRIMARY KEY (page_id, side, corner)
);

-- Flat stream, row-major emission.
CREATE TABLE h2h_metrics (
    page_id     TEXT NOT NULL,
    idx         INTEGER NOT NULL,
    kind        TEXT NOT NULL,
    group_label TEXT,               -- kind='group'
    label       TEXT,               -- kind='row'
    diverge     INTEGER,
    sub_html    TEXT,
    p1_width INTEGER,
    p1_val   TEXT,
    p1_best  INTEGER,
    p2_width INTEGER,
    p2_val   TEXT,
    p2_best  INTEGER,
    p1_val_style TEXT,              -- e.g. 'color:var(--muted)' (inacio 'n/a ‡')
    p2_val_style TEXT,
    right_override TEXT,            -- nullable JSON: hand-written LTR/RTL asymmetries
    note_html  TEXT,                -- kind='note'
    note_style TEXT,
    PRIMARY KEY (page_id, idx)
);

-- 5 per page.
CREATE TABLE h2h_divg (
    page_id   TEXT NOT NULL,
    idx       INTEGER NOT NULL,
    title     TEXT NOT NULL,
    body_html TEXT NOT NULL,
    PRIMARY KEY (page_id, idx)
);

-- 8 per side; only pages with has_acquisition = 1.
CREATE TABLE h2h_acq (
    page_id TEXT NOT NULL,
    side    TEXT NOT NULL,
    idx     INTEGER NOT NULL,
    key     TEXT NOT NULL,
    val     TEXT NOT NULL,
    val_cls TEXT NOT NULL,
    PRIMARY KEY (page_id, side, idx)
);

-- ── One-off comparison pages ────────────────────────────────────────────────
-- Scalars as KV, repeating groups typed.
CREATE TABLE page_scalars (
    page_id TEXT NOT NULL,
    key     TEXT NOT NULL,
    val     TEXT NOT NULL,
    PRIMARY KEY (page_id, key)
);

-- 13 forwards; 2 have no verdict paragraph.
CREATE TABLE fwd_players (
    id           TEXT PRIMARY KEY,
    key          TEXT NOT NULL,   -- short display label ('CDK'); join key in the page JS
    card_cls     TEXT NOT NULL,
    color        TEXT NOT NULL,
    name         TEXT NOT NULL,
    club_line    TEXT NOT NULL,
    val          TEXT NOT NULL,
    age_line     TEXT NOT NULL,
    pos          TEXT NOT NULL,
    apps         TEXT NOT NULL,
    verdict_html TEXT,
    verdict_ord  INTEGER,
    sort         INTEGER NOT NULL
);

-- 7 × 13.
CREATE TABLE fwd_card_stats (
    player_id TEXT NOT NULL,
    idx       INTEGER NOT NULL,
    label     TEXT NOT NULL,
    val       TEXT NOT NULL,
    cls       TEXT NOT NULL,
    PRIMARY KEY (player_id, idx)
);

-- 4 sections, 13 metrics.
CREATE TABLE fwd_table_metrics (
    section TEXT NOT NULL,
    ord     INTEGER NOT NULL,
    metric  TEXT NOT NULL,
    PRIMARY KEY (section, ord)
);

-- 169 cells, verbatim strings including '*‡†§' / 'n/a*'.
CREATE TABLE fwd_table_cells (
    section   TEXT NOT NULL,
    ord       INTEGER NOT NULL,
    player_id TEXT NOT NULL,
    val       TEXT NOT NULL,
    PRIMARY KEY (section, ord, player_id)
);

CREATE TABLE fwd_radar_metrics (
    idx   INTEGER PRIMARY KEY,
    label TEXT NOT NULL
);

-- 5 × 13.
CREATE TABLE fwd_radar_values (
    player_id TEXT NOT NULL,
    idx       INTEGER NOT NULL,
    val       REAL NOT NULL,
    PRIMARY KEY (player_id, idx)
);

CREATE TABLE mid_players (
    id        TEXT PRIMARY KEY,
    card_cls  TEXT NOT NULL,
    css_token TEXT NOT NULL,
    name      TEXT NOT NULL,
    sub       TEXT NOT NULL,
    color     TEXT NOT NULL,
    sort      INTEGER NOT NULL
);

-- 10 × 3.
CREATE TABLE mid_card_stats (
    player_id TEXT NOT NULL,
    idx       INTEGER NOT NULL,
    label     TEXT NOT NULL,
    val       TEXT NOT NULL,
    cls       TEXT NOT NULL,
    PRIMARY KEY (player_id, idx)
);

-- kind ∈ 'section' (colspan header) | 'row'. Value cells hold verbatim inner
-- HTML INCLUDING any <span class="badge best"> markup; winner_idx
-- (0 = none/'—', 1, 2, 3) only drives td.accent.
CREATE TABLE mid_table_rows (
    ord             INTEGER PRIMARY KEY,
    kind            TEXT NOT NULL,
    label           TEXT NOT NULL,
    yaya_html       TEXT NOT NULL,
    bernal_html     TEXT NOT NULL,
    bellingham_html TEXT NOT NULL,
    winner_idx      INTEGER NOT NULL
);

CREATE TABLE mid_radar_axes (
    idx   INTEGER PRIMARY KEY,
    label TEXT NOT NULL
);

-- 8 × 3.
CREATE TABLE mid_radar_values (
    player_id TEXT NOT NULL,
    idx       INTEGER NOT NULL,
    val       REAL NOT NULL,
    PRIMARY KEY (player_id, idx)
);

-- Midfielder verdict paragraphs (4, '<p><strong>heading</strong><br>prose</p>'
-- inner HTML).
CREATE TABLE page_blocks (
    page_id TEXT NOT NULL,
    section TEXT NOT NULL,
    idx     INTEGER NOT NULL,
    html    TEXT NOT NULL,
    PRIMARY KEY (page_id, section, idx)
);
"""


def table_names(conn: sqlite3.Connection) -> list[str]:
    return [
        r[0]
        for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )
    ]


def create_schema(conn: sqlite3.Connection) -> None:
    for name in table_names(conn):
        conn.execute(f'DROP TABLE IF EXISTS "{name}"')
    conn.executescript(SCHEMA)


def main(only: list[str] | None = None) -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        create_schema(conn)
        for mod in pages.modules(only):
            mod.seed(conn)
        conn.commit()
        print(f"\nSeeded {DB_PATH}")
        for name in table_names(conn):
            count = conn.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0]
            print(f"  {name:24s} {count:5d}")
    finally:
        conn.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--only", help="comma-separated archetype module names")
    args = ap.parse_args()
    main(args.only.split(",") if args.only else None)
