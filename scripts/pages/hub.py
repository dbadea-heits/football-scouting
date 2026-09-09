"""Hub archetype: index.html — player report cards + comparison cards.

Seeds `players`, `card_stats('2025-26')`, `comparisons`, `comparison_chips`
and `site_meta` from the committed index.html, and renders it back from the DB.
"""

from __future__ import annotations

import sqlite3

from bs4 import BeautifulSoup, Comment

from . import read_text, write_page

ORDER = 10

PAGE = "index.html"
BASE_SEASON = "2025-26"

# 12 report players + 5 comparison-only players; not derivable from the tables.
PLAYERS_TRACKED = "17"


def _comment_above(tag) -> str:
    node = tag.find_previous(string=lambda s: isinstance(s, Comment))
    return str(node).strip()


def _inner(tag) -> str:
    """Inner HTML, undoing bs4's `<br/>` serialisation."""
    return tag.decode_contents().replace("<br/>", "<br>")


def _stat_cls(val_div) -> str:
    """Suffix after `card-stat-val`, '' when the value carries no modifier."""
    classes = [c for c in val_div.get("class", []) if c != "card-stat-val"]
    return " ".join(classes)


def seed(conn: sqlite3.Connection) -> None:
    soup = BeautifulSoup(read_text(PAGE), "html.parser")

    cards = soup.select("a.report-card")
    assert len(cards) == 12, f"expected 12 report cards, found {len(cards)}"
    for sort, card in enumerate(cards):
        pid = card["data-player"]
        classes = card.get("class", [])
        assert classes[0] == "report-card" and len(classes) == 3, classes
        verdict_tier, pos_class = classes[1], classes[2]
        assert card["href"] == f"{pid}-report.html", card["href"]
        potential = card.select_one(".potential-chip").get_text()
        assert potential.startswith("Potential: "), potential
        conn.execute(
            "INSERT INTO players (id, name, short_name, club_line, pos_badge,"
            " pos_class, verdict_tier, verdict_label, potential, mins_base, sort)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (
                pid,
                card.select_one(".card-name").get_text(),
                _comment_above(card),
                card.select_one(".card-club").get_text(),
                card.select_one(".pos-badge").get_text(),
                pos_class,
                verdict_tier,
                card.select_one(".verdict-badge").get_text(),
                potential[len("Potential: ") :],
                card.select_one(".card-mins").get_text(),
                sort,
            ),
        )
        stats = card.select(".card-stat")
        assert len(stats) == 3, f"{pid}: {len(stats)} card stats"
        for idx, stat in enumerate(stats):
            val = stat.select_one(".card-stat-val")
            conn.execute(
                "INSERT INTO card_stats (player_id, season, idx, label, val, cls)"
                " VALUES (?,?,?,?,?,?)",
                (
                    pid,
                    BASE_SEASON,
                    idx,
                    stat.select_one(".card-stat-label").get_text(),
                    val.get_text(),
                    _stat_cls(val),
                ),
            )

    comps = soup.select("a.comp-card")
    assert len(comps) == 6, f"expected 6 comparison cards, found {len(comps)}"
    for sort, comp in enumerate(comps):
        href = comp["href"]
        cid = href.removesuffix("-comparison.html")
        classes = comp.get("class", [])
        assert classes[0] == "comp-card" and len(classes) == 2, classes
        type_class = classes[1]
        badge = comp.select_one(".comp-type-badge")
        assert badge.get("class") == ["comp-type-badge", type_class], badge.get("class")
        conn.execute(
            "INSERT INTO comparisons (id, href, type_class, badge, title,"
            " subtitle_html, meta, comment, sort) VALUES (?,?,?,?,?,?,?,?,?)",
            (
                cid,
                href,
                type_class,
                badge.get_text(),
                comp.select_one(".comp-title").get_text(),
                _inner(comp.select_one(".comp-subtitle")),
                comp.select_one(".comp-meta").get_text(),
                _comment_above(comp),
                sort,
            ),
        )
        for idx, chip in enumerate(comp.select(".player-chip")):
            conn.execute(
                "INSERT INTO comparison_chips (comparison_id, idx, label)"
                " VALUES (?,?,?)",
                (cid, idx, chip.get_text()),
            )

    conn.execute(
        "INSERT INTO site_meta (key, val) VALUES (?,?)",
        ("players_tracked", PLAYERS_TRACKED),
    )


def context(conn: sqlite3.Connection) -> dict:
    players = []
    for row in conn.execute("SELECT * FROM players ORDER BY sort"):
        player = dict(row)
        player["stats"] = [
            dict(s)
            for s in conn.execute(
                "SELECT label, val, cls FROM card_stats WHERE player_id = ?"
                " AND season = ? ORDER BY idx",
                (row["id"], BASE_SEASON),
            )
        ]
        players.append(player)

    comparisons = []
    for row in conn.execute("SELECT * FROM comparisons ORDER BY sort"):
        comp = dict(row)
        comp["chips"] = [
            r["label"]
            for r in conn.execute(
                "SELECT label FROM comparison_chips WHERE comparison_id = ?"
                " ORDER BY idx",
                (row["id"],),
            )
        ]
        comparisons.append(comp)

    return {
        "players": players,
        "comparisons": comparisons,
        "n_players": len(players),
        "n_comps": len(comparisons),
        "players_tracked": conn.execute(
            "SELECT val FROM site_meta WHERE key = 'players_tracked'"
        ).fetchone()[0],
    }


def build(conn: sqlite3.Connection, env) -> None:
    write_page(PAGE, env.get_template("index.html.j2").render(**context(conn)))
