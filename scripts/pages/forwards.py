"""Forwards archetype: forwards-comparison.html — the 13-forward study.

The page renders itself: cards, metric table and radar are all built client-side
from three inline JS datasets, so there is no server-side markup to parse for
them — they are hand-ported literals below (`PLAYERS`, `TABLE_ROWS`,
`RADAR_METRICS`/`RADAR_DATA`), plus the default toggle set and the table
footnote. What *does* live in the markup — the 11 verdict paragraphs and the
header/footer scalars — is parsed from the committed page.
"""

from __future__ import annotations

import json
import sqlite3

from bs4 import BeautifulSoup

from . import read_text, write_page

ORDER = 50

PAGE = "forwards-comparison.html"
PAGE_ID = "forwards"

# ── Hand-ported datasets (inline <script> of the committed page) ────────────
PLAYERS = [
    {
        "id": "ferran", "key": "Ferran Torres", "card_cls": "ferran", "color": "#1f77b4",
        "name": "Ferran Torres", "club_line": "FC Barcelona — La Liga",
        "val": "€38M", "age_line": "26 / 184cm / Right",
        "pos": "ST / RW / LW", "apps": "33 (23) — 1,976 min",
        "stats": [
            ("Goals (G/90)", "16 (0.73)", "good"),
            ("Assists", "2", ""),
            ("G+A per 90", "0.82", "good"),
            ("Shots / On Target", "67 / 37 (55.2%)", ""),
            ("xG", "14.02", ""),
            ("G - xG", "+1.98", "good"),
            ("La Liga Rank", "#5", "good"),
        ],
    },
    {
        "id": "mika", "key": "Mikautadze", "card_cls": "mika", "color": "#ffd700",
        "name": "Georges Mikautadze", "club_line": "Villarreal — La Liga",
        "val": "€25.2M", "age_line": "25 / 176cm / Right",
        "pos": "ST (CF)", "apps": "32 (23) — 2,117 min",
        "stats": [
            ("Goals (G/90)", "13 (0.55)", "ok"),
            ("Assists", "6", "good"),
            ("G+A per 90", "0.81", "ok"),
            ("Shots / On Target", "65 / 32 (49.2%)", ""),
            ("xG", "11.42", ""),
            ("G - xG", "+1.58", "ok"),
            ("La Liga Rank", "#13", "ok"),
        ],
    },
    {
        "id": "undav", "key": "Undav", "card_cls": "undav", "color": "#d62728",
        "name": "Deniz Undav", "club_line": "VfB Stuttgart — Bundesliga",
        "val": "~€20M", "age_line": "28 / 178cm / Right",
        "pos": "ST / SS", "apps": "29 (25) — 2,249 min",
        "stats": [
            ("Goals (G/90)", "19 (0.76)", "good"),
            ("Assists", "7", "good"),
            ("G+A per 90", "1.04", "good"),
            ("Shots / On Target", "122 / 68 (55.7%)", ""),
            ("xG", "15.94", ""),
            ("G - xG", "+3.06", "good"),
            ("Bundesliga Rank", "#3", "good"),
        ],
    },
    {
        "id": "oskarsson", "key": "Óskarsson", "card_cls": "oskarsson", "color": "#2ca02c",
        "name": "Orri Óskarsson", "club_line": "Real Sociedad — La Liga",
        "val": "~€10M", "age_line": "21 / 186cm / Right",
        "pos": "ST (CF)", "apps": "20 (8) — 829 min",
        "stats": [
            ("Goals (G/90)", "9 (0.98)*", "good"),
            ("Assists", "0", "bad"),
            ("G+A per 90", "0.98", "good"),
            ("Shots / On Target", "27 / 19 (70.4%)", ""),
            ("xG", "5.77", ""),
            ("G - xG", "+3.23", "good"),
            ("La Liga Rank", "#20", "ok"),
        ],
    },
    {
        "id": "tresoldi", "key": "Tresoldi", "card_cls": "tresoldi", "color": "#9467bd",
        "name": "Nicolò Tresoldi", "club_line": "Club Brugge — Belgian Pro League",
        "val": "~€12M", "age_line": "21 / 183cm / Right",
        "pos": "ST (CF)", "apps": "40 (30) — 2,500 min",
        "stats": [
            ("Goals (G/90)", "19 (0.68)", "good"),
            ("Assists", "5", "ok"),
            ("G+A per 90", "0.86", "good"),
            ("Shots / On Target", "101 / 42 (41.6%)", ""),
            ("xG", "16.85", ""),
            ("G - xG", "+2.15", "ok"),
            ("Pro League Rank", "#1", "good"),
        ],
    },
    {
        "id": "asllani", "key": "Asllani", "card_cls": "asllani", "color": "#ff7f0e",
        "name": "Fisnik Asllani", "club_line": "Hoffenheim — Bundesliga",
        "val": "€30.7M", "age_line": "23 / 188cm / Both",
        "pos": "ST / AM", "apps": "33 (31) — 2,354 min",
        "stats": [
            ("Goals (G/90)", "10 (0.38)", "bad"),
            ("Assists", "7", "good"),
            ("G+A per 90", "0.65", "ok"),
            ("Shots / On Target", "73 / 28 (38.4%)", ""),
            ("xG", "8.28", ""),
            ("G - xG", "+1.72", "ok"),
            ("Bundesliga Rank", "#16", "ok"),
        ],
    },
    {
        "id": "cdk", "key": "CDK", "card_cls": "cdk", "color": "#8c564b",
        "name": "Charles De Ketelaere", "club_line": "Atalanta — Serie A",
        "val": "€35.7M", "age_line": "25 / 192cm / Left",
        "pos": "AM / LW / RW / ST", "apps": "31 (26) — 2,188 min",
        "stats": [
            ("Goals (G/90)", "3 (0.12)", "bad"),
            ("Assists", "5", "good"),
            ("G+A per 90", "0.33", "bad"),
            ("Rating", "7.12 (FotMob)", "ok"),
            ("xA", "8.75", "ok"),
            ("Pass Success", "78.8%", "ok"),
            ("Serie A Rank", "#60+", "bad"),
        ],
    },
    {
        "id": "jackson", "key": "Jackson", "card_cls": "jackson", "color": "#e377c2",
        "name": "Nicolas Jackson", "club_line": "Bayern Munich (loan from Chelsea) — Bundesliga",
        "val": "Loan (obl. ~€65M)", "age_line": "25 / 187cm / Right",
        "pos": "ST (CF)", "apps": "23 (16) — ~1,000 min",
        "stats": [
            ("Goals (G/90)", "8 (0.72)", "ok"),
            ("Assists", "1", "bad"),
            ("G+A per 90", "0.81", "ok"),
            ("Shots / On Target", "38 / 21 (55.3%)", ""),
            ("xG (non-pen)", "8.23", ""),
            ("G - xG", "-0.23", "bad"),
            ("Role", "Impact sub at Bayern", ""),
        ],
    },
    {
        "id": "gyokeres", "key": "Gyökeres", "card_cls": "gyokeres", "color": "#bcbd22",
        "name": "Viktor Gyökeres", "club_line": "Arsenal (ex-Sporting CP) — Premier League",
        "val": "€63.5M fee", "age_line": "27 / 187cm / Right",
        "pos": "ST (CF)", "apps": "36 (26) — 2,231 min",
        "stats": [
            ("Goals (G/90)", "14 (0.56)", "ok"),
            ("Assists", "1", "bad"),
            ("G+A per 90", "0.61", "ok"),
            ("Shots / On Target", "55 / 23 (41.8%)", ""),
            ("xG", "12.51", ""),
            ("G - xG", "+1.49", "good"),
            ("Premier League Rank", "#7 (top AFC scorer)", "ok"),
        ],
    },
    {
        "id": "suarez", "key": "Suárez", "card_cls": "suarez", "color": "#94a3b8",
        "name": "Luis Suárez", "club_line": "Sporting CP — Primeira Liga",
        "val": "€22M–€25M fee", "age_line": "28 / 185cm / Right",
        "pos": "ST (CF)", "apps": "32 (31) — 2,700 min",
        "stats": [
            ("Goals (G/90)", "28 (0.93)", "good"),
            ("Assists", "6", "good"),
            ("G+A per 90", "1.13", "good"),
            ("Shots / On Target", "136 / 60 (44.1%)", ""),
            ("xG", "27.86", "good"),
            ("G - xG", "+0.14", "ok"),
            ("Primeira Liga Rank", "#1 — Top scorer", "good"),
        ],
    },
    {
        "id": "bro", "key": "Bro Hansen", "card_cls": "bro", "color": "#17becf",
        "name": "Mikkel Bro Hansen", "club_line": "Bodø/Glimt — Eliteserien",
        "val": "~€0.9M", "age_line": "17 / 188cm / Right",
        "pos": "ST (CF)", "apps": "11 (0) — 99 min*",
        "stats": [
            ("Goals (G/90)", "2 (1.82)*", "good"),
            ("Assists", "1", "ok"),
            ("G+A per 90", "2.73*", "good"),
            ("U17 Intl Goals", "13 in 16 caps", "good"),
            ("Senior Career", "15 apps, 8 goals", ""),
            ("2025 Cup Goals", "6 in 3 apps", "good"),
            ("Status", "Youth prospect", "bad"),
        ],
    },
    {
        "id": "ayoze", "key": "Ayoze", "card_cls": "ayoze", "color": "#f59e0b",
        "name": "Ayoze Pérez", "club_line": "Villarreal — La Liga",
        "val": "~€6M", "age_line": "32 / 178cm / Right",
        "pos": "SS / RW / ST", "apps": "25 (10) — 1,122 min",
        "stats": [
            ("Goals (G/90)", "5 (0.40)", "bad"),
            ("Assists", "4", "ok"),
            ("G+A per 90", "0.72", "ok"),
            ("Shots / On Target", "24 / 11 (45.8%)", ""),
            ("xG", "5.38", ""),
            ("G - xG", "-0.38", "bad"),
            ("La Liga Rank", "#37", "bad"),
        ],
    },
    {
        "id": "watkins", "key": "Watkins", "card_cls": "watkins", "color": "#7c3aed",
        "name": "Ollie Watkins", "club_line": "Aston Villa — Premier League",
        "val": "~€35M", "age_line": "30 / 180cm / Right",
        "pos": "ST (CF)", "apps": "37 (28) — 2,852 min",
        "stats": [
            ("Goals (G/90)", "16 (0.50)", "ok"),
            ("Assists", "3", "bad"),
            ("G+A per 90", "0.60", "ok"),
            ("Shots / On Target", "83 / 38 (45.8%)", ""),
            ("xG", "15.14", ""),
            ("G - xG", "+0.86", "good"),
            ("Premier League Rank", "#5", "ok"),
        ],
    },
]

TABLE_ROWS = [
    ("GOALSCORING", [
        ("Goals", dict(ferran="16", mika="13", undav="19", oskarsson="9", tresoldi="19", asllani="10", cdk="3", jackson="8", gyokeres="14", suarez="28", bro="2*", ayoze="5", watkins="16")),
        ("G/90", dict(ferran="0.73", mika="0.55", undav="0.76", oskarsson="0.98", tresoldi="0.68", asllani="0.38", cdk="0.12", jackson="0.72", gyokeres="0.56", suarez="0.93", bro="1.82*", ayoze="0.40", watkins="0.50")),
        ("Shot Accuracy", dict(ferran="55.2%", mika="49.2%", undav="55.7%", oskarsson="70.4%", tresoldi="41.6%", asllani="38.4%", cdk="83%*‡", jackson="55.3%", gyokeres="41.8%", suarez="44.1%", bro="33.3%*", ayoze="45.8%", watkins="45.8%")),
        ("Conversion Rate", dict(ferran="23.9%", mika="20.0%", undav="15.6%", oskarsson="33.3%", tresoldi="19.6%", asllani="13.7%", cdk="6.5%§", jackson="21.1%", gyokeres="25.5%", suarez="20.6%", bro="66.7%*", ayoze="20.8%", watkins="19.3%")),
        ("xG", dict(ferran="14.02", mika="11.42", undav="15.94", oskarsson="5.77", tresoldi="16.85", asllani="8.28", cdk="3.63§", jackson="8.23†", gyokeres="12.51", suarez="27.86", bro="0.4*", ayoze="5.38", watkins="15.14")),
        ("G - xG", dict(ferran="+1.98", mika="+1.58", undav="+3.06", oskarsson="+3.23", tresoldi="+2.15", asllani="+1.72", cdk="-0.63§", jackson="-0.23", gyokeres="+1.49", suarez="+0.14", bro="+1.6*", ayoze="-0.38", watkins="+0.86")),
    ]),
    ("LINK-UP & CREATIVITY", [
        ("Assists", dict(ferran="2", mika="6", undav="7", oskarsson="0", tresoldi="5", asllani="7", cdk="5", jackson="1", gyokeres="1", suarez="6", bro="1*", ayoze="4", watkins="3")),
        ("Key Passes", dict(ferran="23", mika="14*", undav="39", oskarsson="5*", tresoldi="23", asllani="19*", cdk="24", jackson="18", gyokeres="20", suarez="46", bro="2*", ayoze="16", watkins="23")),
        ("Pass Success", dict(ferran="70.4%", mika="75.5%", undav="69.9%", oskarsson="64.0%", tresoldi="74.0%", asllani="68.6%", cdk="78.8%", jackson="81.6%", gyokeres="62.6%", suarez="75.6%", bro="64%*", ayoze="75.8%", watkins="72.7%")),
    ]),
    ("HOLD-UP & PHYSICAL", [
        ("Aerial Duels Won", dict(ferran="25", mika="10", undav="27*", oskarsson="16", tresoldi="63*", asllani="24", cdk="13*‡", jackson="7", gyokeres="30", suarez="32", bro="n/a*", ayoze="15", watkins="36")),
        ("Touches Opp Box", dict(ferran="125", mika="140", undav="174*", oskarsson="44", tresoldi="172", asllani="149", cdk="129", jackson="95", gyokeres="142", suarez="249", bro="n/a*", ayoze="55", watkins="177")),
    ]),
    ("PRESSING", [
        ("Duels Won %", dict(ferran="44.1%", mika="45.4%", undav="44.1%", oskarsson="41.8%", tresoldi="50.7%", asllani="37.0%", cdk="53.1%", jackson="36.7%", gyokeres="31.6%", suarez="45.7%", bro="n/a*", ayoze="40.2%", watkins="41.1%")),
        ("Recoveries", dict(ferran="36", mika="40", undav="135*", oskarsson="12", tresoldi="172*", asllani="76", cdk="9*‡", jackson="25", gyokeres="55", suarez="53", bro="n/a*", ayoze="23", watkins="49")),
    ]),
]

RADAR_METRICS = ["G/90", "A/90", "Shot%", "Conv%", "G-xG"]

# Decimal places per metric: the hand-written literal writes A/90 0.00 and
# G-xG 1.60, which a bare float repr would collapse to 0.0 / 1.6.
RADAR_DECIMALS = [2, 2, 1, 1, 2]

RADAR_DATA = {
    "ferran": [0.73, 0.09, 55.2, 23.9, 1.98],
    "mika": [0.55, 0.26, 49.2, 20.0, 1.58],
    "undav": [0.76, 0.28, 55.7, 15.6, 3.06],
    "oskarsson": [0.98, 0.00, 70.4, 33.3, 3.23],
    "tresoldi": [0.68, 0.18, 41.6, 19.6, 2.15],
    "asllani": [0.38, 0.27, 38.4, 13.7, 1.72],
    "cdk": [0.12, 0.21, 83.0, 6.5, -0.63],
    "jackson": [0.72, 0.09, 55.3, 21.1, -0.23],
    "gyokeres": [0.56, 0.04, 41.8, 25.5, 1.49],
    "suarez": [0.93, 0.20, 44.1, 20.6, 0.14],
    "bro": [1.82, 0.91, 33.3, 66.7, 1.60],
    "ayoze": [0.40, 0.32, 45.8, 20.8, -0.38],
    "watkins": [0.50, 0.09, 45.8, 19.3, 0.86],
}

DEFAULT_VISIBLE = ["Undav", "Óskarsson", "Tresoldi", "Suárez", "Mikautadze"]

TABLE_FOOTNOTE = (
    "* Extremely small sample. Bro Hansen: 99 Eliteserien min across 2 seasons. "
    "Óskarsson: 829 min. ‡ CDK from WC 2026 (353 min). † Jackson xG is non-penalty. "
    "§ CDK conversion/xG/G−xG are FotMob Serie A 25/26 (FBref Opta blocked). "
    "Bro Hansen aerial/physical/pressing metrics unavailable (no tracking data at 99 min). "
    "All new cells sourced from FotMob 2025/26 domestic league."
)

# Verdict prose is keyed off the leading name of each paragraph's <strong>.
VERDICT_SPLIT = " — "

SCALAR_KEYS = (
    "default_visible",
    "footer_left",
    "footer_right",
    "label_pill",
    "meta_leagues",
    "meta_players",
    "meta_view",
    "nav_brand",
    "table_footnote",
    "title",
)


def _inner(tag) -> str:
    """Inner HTML, undoing bs4's `<br/>` serialisation."""
    return tag.decode_contents().replace("<br/>", "<br>")


def _verdicts(soup, by_name: dict[str, str]) -> dict[str, tuple[str, int]]:
    """player id -> (verdict inner HTML, display order) from the verdict box.

    Each paragraph opens `<strong>{name} — {angle}.</strong>`, which is the only
    link back to the player; ferran and asllani have no paragraph.
    """
    paras = soup.select("#verdict .verdict-box p")
    assert len(paras) == 11, f"expected 11 verdict paragraphs, found {len(paras)}"
    verdicts = {}
    for order, para in enumerate(paras):
        lead = para.strong.get_text()
        name = lead.split(VERDICT_SPLIT)[0]
        assert name in by_name, f"unknown verdict subject: {lead}"
        verdicts[by_name[name]] = (_inner(para), order)
    return verdicts


def _scalars(soup) -> dict[str, str]:
    title = soup.title.get_text()
    assert soup.select_one("h1.report-title").get_text() == title
    cells = soup.select(".header-meta .meta-cell")
    labels = [c.select_one(".meta-label").get_text() for c in cells]
    assert labels == ["Players", "Leagues", "View"], labels
    values = [c.select_one(".meta-value").get_text() for c in cells]
    scalars = {
        "title": title,
        "nav_brand": soup.select_one(".fi-nav-brand").get_text(),
        "label_pill": soup.select_one(".label-pill").get_text(),
        "meta_players": values[0],
        "meta_leagues": values[1],
        "meta_view": values[2],
        "footer_left": soup.select_one(".footer-left").get_text(),
        "footer_right": soup.select_one(".footer-right").get_text(),
        "table_footnote": TABLE_FOOTNOTE,
        "default_visible": json.dumps(DEFAULT_VISIBLE, ensure_ascii=False),
    }
    assert set(scalars) == set(SCALAR_KEYS), sorted(scalars)
    return scalars


def seed(conn: sqlite3.Connection) -> None:
    soup = BeautifulSoup(read_text(PAGE), "html.parser")

    assert len(PLAYERS) == 13, f"expected 13 forwards, found {len(PLAYERS)}"
    verdicts = _verdicts(soup, {p["name"]: p["id"] for p in PLAYERS})
    for sort, player in enumerate(PLAYERS):
        verdict_html, verdict_order = verdicts.get(player["id"], (None, None))
        conn.execute(
            "INSERT INTO fwd_players (id, key, card_cls, color, name, club_line,"
            " val, age_line, pos, apps, verdict_html, verdict_ord, sort)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                player["id"],
                player["key"],
                player["card_cls"],
                player["color"],
                player["name"],
                player["club_line"],
                player["val"],
                player["age_line"],
                player["pos"],
                player["apps"],
                verdict_html,
                verdict_order,
                sort,
            ),
        )
        stats = player["stats"]
        assert len(stats) == 7, f"{player['id']}: {len(stats)} card stats"
        for idx, (label, val, cls) in enumerate(stats):
            conn.execute(
                "INSERT INTO fwd_card_stats (player_id, idx, label, val, cls)"
                " VALUES (?,?,?,?,?)",
                (player["id"], idx, label, val, cls),
            )

    # `ord` runs across the whole table, so section order needs no extra column.
    ids = [p["id"] for p in PLAYERS]
    ord_ = 0
    for section, rows in TABLE_ROWS:
        for metric, cells in rows:
            conn.execute(
                "INSERT INTO fwd_table_metrics (section, ord, metric) VALUES (?,?,?)",
                (section, ord_, metric),
            )
            assert list(cells) == ids, f"{section}/{metric}: {list(cells)}"
            for player_id, val in cells.items():
                conn.execute(
                    "INSERT INTO fwd_table_cells (section, ord, player_id, val)"
                    " VALUES (?,?,?,?)",
                    (section, ord_, player_id, val),
                )
            ord_ += 1
    assert ord_ == 13, f"expected 13 table metrics, found {ord_}"

    assert len(RADAR_METRICS) == len(RADAR_DECIMALS)
    for idx, label in enumerate(RADAR_METRICS):
        conn.execute(
            "INSERT INTO fwd_radar_metrics (idx, label) VALUES (?,?)", (idx, label)
        )
    for player_id in ids:
        values = RADAR_DATA[player_id]
        assert len(values) == len(RADAR_METRICS), player_id
        for idx, val in enumerate(values):
            conn.execute(
                "INSERT INTO fwd_radar_values (player_id, idx, val) VALUES (?,?,?)",
                (player_id, idx, val),
            )

    for key, val in _scalars(soup).items():
        conn.execute(
            "INSERT INTO page_scalars (page_id, key, val) VALUES (?,?,?)",
            (PAGE_ID, key, val),
        )


def context(conn: sqlite3.Connection) -> dict:
    players = []
    for row in conn.execute("SELECT * FROM fwd_players ORDER BY sort"):
        player = dict(row)
        player["stats"] = [
            dict(s)
            for s in conn.execute(
                "SELECT label, val, cls FROM fwd_card_stats WHERE player_id = ?"
                " ORDER BY idx",
                (row["id"],),
            )
        ]
        player["radar"] = [
            f"{r['val']:.{RADAR_DECIMALS[r['idx']]}f}"
            for r in conn.execute(
                "SELECT idx, val FROM fwd_radar_values WHERE player_id = ? ORDER BY idx",
                (row["id"],),
            )
        ]
        players.append(player)

    table: list[dict] = []
    for metric in conn.execute(
        "SELECT section, ord, metric FROM fwd_table_metrics ORDER BY ord"
    ):
        if not table or table[-1]["name"] != metric["section"]:
            table.append({"name": metric["section"], "rows": []})
        table[-1]["rows"].append(
            {
                "metric": metric["metric"],
                "cells": [
                    dict(c)
                    for c in conn.execute(
                        "SELECT c.player_id, c.val FROM fwd_table_cells c"
                        " JOIN fwd_players p ON p.id = c.player_id"
                        " WHERE c.section = ? AND c.ord = ? ORDER BY p.sort",
                        (metric["section"], metric["ord"]),
                    )
                ],
            }
        )

    scalars = {
        r["key"]: r["val"]
        for r in conn.execute(
            "SELECT key, val FROM page_scalars WHERE page_id = ?", (PAGE_ID,)
        )
    }
    assert set(scalars) == set(SCALAR_KEYS), sorted(scalars)
    scalars["default_visible"] = json.loads(scalars["default_visible"])

    return {
        "players": players,
        "table": table,
        "radar_metrics": [
            r["label"]
            for r in conn.execute("SELECT label FROM fwd_radar_metrics ORDER BY idx")
        ],
        "verdicts": [
            r["verdict_html"]
            for r in conn.execute(
                "SELECT verdict_html FROM fwd_players WHERE verdict_html IS NOT NULL"
                " ORDER BY verdict_ord"
            )
        ],
        **scalars,
    }


def build(conn: sqlite3.Connection, env) -> None:
    write_page(PAGE, env.get_template("forwards.html.j2").render(**context(conn)))
