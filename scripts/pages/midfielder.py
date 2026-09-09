"""Midfielder archetype: midfielder-comparison.html — 3-player cross-era study.

Owns `mid_players`, `mid_card_stats`, `mid_table_rows`, `mid_radar_axes`,
`mid_radar_values`, plus `page_blocks`/`page_scalars` rows scoped to
`page_id = 'midfielder'`.

Three name variants live on the page and none is derivable from another, so all
three are stored: `mid_players.name` (card + table header), `radar_name.<id>`
(radar series key and legend, e.g. plain "Bellingham") and `best_label.<id>`
(the winner column, e.g. plain "Bernal"). The radar dataset is not parsed out of
the inline JS — it is hand-ported below and the byte-diff loop guards it.
"""

from __future__ import annotations

import re
import sqlite3

from bs4 import BeautifulSoup

from . import read_text, write_page

ORDER = 60

PAGE = "midfielder-comparison.html"
PAGE_ID = "midfielder"

# Hand-ported from the page's inline radar script (AXES / P / CL literals).
RADAR_AXES = ["G/90", "A/90", "Pass%", "Tkl/90", "Duel%", "DefC/90", "Drb%", "Aerial%"]
RADAR = {
    "yaya": ("Yaya Toure", "#6caddf", [0.57, 0.26, 90.8, 2.3, 48.0, 4.5, 55.0, 52.0]),
    "bernal": ("Marc Bernal", "#a50044", [0.23, 0.11, 92.0, 3.0, 55.3, 6.75, 78.6, 48.4]),
    "bellingham": ("Bellingham", "#febe10", [0.28, 0.19, 81.5, 2.1, 53.8, 3.8, 69.2, 11.1]),
}

# `.card.<class>::before { background: var(--<token>); }` — the accent bar token
# is 'bell' for bellingham, so it cannot be derived from the card class.
CSS_TOKEN_RE = re.compile(r"\.card\.(\w+)::before\s+\{ background: var\(--(\w+)\); \}")

CELL_COLUMNS = ("yaya_html", "bernal_html", "bellingham_html")


def _inner(tag) -> str:
    """Inner HTML, undoing bs4's `<br/>` serialisation."""
    return tag.decode_contents().replace("<br/>", "<br>")


def _stat_cls(val_span) -> str:
    """Suffix after `stat-val`, '' when the value carries no modifier."""
    return " ".join(c for c in val_span.get("class", []) if c != "stat-val")


def seed(conn: sqlite3.Connection) -> None:
    soup = BeautifulSoup(read_text(PAGE), "html.parser")

    tokens = dict(CSS_TOKEN_RE.findall(soup.find("style").get_text()))
    assert len(tokens) == 3, tokens

    cards = soup.select(".cards-section .card")
    assert len(cards) == 3, f"expected 3 player cards, found {len(cards)}"
    ids = []
    n_stats = 0
    for sort, card in enumerate(cards):
        classes = card.get("class", [])
        assert classes[0] == "card" and len(classes) == 2, classes
        pid = classes[1]
        ids.append(pid)
        radar_name, color, _ = RADAR[pid]
        conn.execute(
            "INSERT INTO mid_players (id, card_cls, css_token, name, sub, color, sort)"
            " VALUES (?,?,?,?,?,?,?)",
            (
                pid,
                pid,
                tokens[pid],
                card.select_one(".player-name").get_text(),
                card.select_one(".player-sub").get_text(),
                color,
                sort,
            ),
        )
        conn.execute(
            "INSERT INTO page_scalars (page_id, key, val) VALUES (?,?,?)",
            (PAGE_ID, f"radar_name.{pid}", radar_name),
        )
        for idx, row in enumerate(card.select(".stat-row")):
            val = row.select_one(".stat-val")
            conn.execute(
                "INSERT INTO mid_card_stats (player_id, idx, label, val, cls)"
                " VALUES (?,?,?,?,?)",
                (
                    pid,
                    idx,
                    row.select_one(".stat-label").get_text(),
                    val.get_text(),
                    _stat_cls(val),
                ),
            )
            n_stats += 1
    assert ids == list(RADAR), ids
    # Not uniform: bernal's card carries 11 stat rows, the other two 10.
    assert n_stats == 31, n_stats

    header = soup.select("table.stat-table thead th")
    assert [th.get_text() for th in header[1:4]] == [
        c.select_one(".player-name").get_text() for c in cards
    ], "table header columns must match the card names"

    best_labels: dict[str, str] = {}
    rows = soup.select("table.stat-table tbody > tr")
    assert len(rows) == 20, f"expected 20 table rows, found {len(rows)}"
    for ord_, row in enumerate(rows):
        cells = row.find_all("td", recursive=False)
        if "section-row" in row.get("class", []):
            assert len(cells) == 1 and cells[0]["colspan"] == "5", ord_
            conn.execute(
                "INSERT INTO mid_table_rows (ord, kind, label, yaya_html,"
                " bernal_html, bellingham_html, winner_idx) VALUES (?,?,?,?,?,?,?)",
                (ord_, "section", _inner(cells[0]), "", "", "", 0),
            )
            continue
        assert len(cells) == 5, f"row {ord_}: {len(cells)} cells"
        values = [_inner(c) for c in cells[1:4]]
        winners = [i for i, c in enumerate(cells[1:4], 1) if c.select_one("span.badge.best")]
        assert len(winners) <= 1, f"row {ord_}: {len(winners)} best badges"
        winner_idx = winners[0] if winners else 0
        verdict = cells[4]
        if winner_idx:
            assert verdict.get("class") == ["accent"], verdict.get("class")
            best_labels.setdefault(ids[winner_idx - 1], verdict.get_text())
            assert best_labels[ids[winner_idx - 1]] == verdict.get_text(), verdict
        else:
            assert not verdict.get("class") and verdict.get_text() == "—", verdict
        conn.execute(
            "INSERT INTO mid_table_rows (ord, kind, label, yaya_html,"
            " bernal_html, bellingham_html, winner_idx) VALUES (?,?,?,?,?,?,?)",
            (ord_, "row", _inner(cells[0]), *values, winner_idx),
        )
    assert sorted(best_labels) == sorted(ids), best_labels
    for pid, label in best_labels.items():
        conn.execute(
            "INSERT INTO page_scalars (page_id, key, val) VALUES (?,?,?)",
            (PAGE_ID, f"best_label.{pid}", label),
        )

    for idx, label in enumerate(RADAR_AXES):
        conn.execute(
            "INSERT INTO mid_radar_axes (idx, label) VALUES (?,?)", (idx, label)
        )
    for pid, (_, _, values) in RADAR.items():
        assert len(values) == len(RADAR_AXES), pid
        for idx, val in enumerate(values):
            conn.execute(
                "INSERT INTO mid_radar_values (player_id, idx, val) VALUES (?,?,?)",
                (pid, idx, val),
            )

    blocks = soup.select(".verdict-body > p")
    assert len(blocks) == 4, f"expected 4 verdict paragraphs, found {len(blocks)}"
    for idx, para in enumerate(blocks):
        conn.execute(
            "INSERT INTO page_blocks (page_id, section, idx, html) VALUES (?,?,?,?)",
            (PAGE_ID, "verdict", idx, _inner(para)),
        )

    meta = {
        cell.select_one(".meta-label").get_text(): cell.select_one(".meta-value").get_text()
        for cell in soup.select(".header-meta .meta-cell")
    }
    assert meta["Players"] == str(len(cards)), meta
    assert meta["Dimensions"] == str(len(RADAR_AXES)), meta

    header_th = [th.get_text() for th in header]
    scalars = {
        "title": soup.find("title").get_text(),
        "nav_crumb": soup.select_one(".fi-nav-crumb").get_text(),
        "label_pill": soup.select_one(".label-pill").get_text(),
        "report_title": soup.select_one(".report-title").get_text(),
        "report_sub": soup.select_one(".report-sub").get_text(),
        "eras": meta["Eras"],
        "th_metric": header_th[0],
        "th_best": header_th[4],
        "radar_caption": soup.select_one(".radar-wrap").find_previous("p").get_text(),
        # Multi-line inner HTML, indented to the template's footer body.
        "footer_left": _inner(soup.select_one(".footer-left")).strip(),
        "footer_right": _inner(soup.select_one(".footer-right")).strip(),
    }
    for key, val in scalars.items():
        conn.execute(
            "INSERT INTO page_scalars (page_id, key, val) VALUES (?,?,?)",
            (PAGE_ID, key, val),
        )


def context(conn: sqlite3.Connection) -> dict:
    scalars = {
        r["key"]: r["val"]
        for r in conn.execute(
            "SELECT key, val FROM page_scalars WHERE page_id = ?", (PAGE_ID,)
        )
    }

    players = []
    for row in conn.execute("SELECT * FROM mid_players ORDER BY sort"):
        player = dict(row)
        pid = row["id"]
        player["radar_name"] = scalars[f"radar_name.{pid}"]
        player["best_label"] = scalars[f"best_label.{pid}"]
        player["stats"] = [
            dict(s)
            for s in conn.execute(
                "SELECT label, val, cls FROM mid_card_stats WHERE player_id = ?"
                " ORDER BY idx",
                (pid,),
            )
        ]
        player["radar"] = [
            r["val"]
            for r in conn.execute(
                "SELECT val FROM mid_radar_values WHERE player_id = ? ORDER BY idx",
                (pid,),
            )
        ]
        players.append(player)

    rows = []
    for row in conn.execute("SELECT * FROM mid_table_rows ORDER BY ord"):
        cells = [row[c] for c in CELL_COLUMNS]
        winner = row["winner_idx"]
        rows.append(
            {
                "kind": row["kind"],
                "label": row["label"],
                "cells": cells,
                "winner": players[winner - 1]["best_label"] if winner else "",
            }
        )

    return {
        **{k: v for k, v in scalars.items() if "." not in k},
        "players": players,
        "axes": [
            r["label"]
            for r in conn.execute("SELECT label FROM mid_radar_axes ORDER BY idx")
        ],
        "rows": rows,
        "blocks": [
            r["html"]
            for r in conn.execute(
                "SELECT html FROM page_blocks WHERE page_id = ? AND section = 'verdict'"
                " ORDER BY idx",
                (PAGE_ID,),
            )
        ],
        "n_players": len(players),
    }


def build(conn: sqlite3.Connection, env) -> None:
    ctx = context(conn)
    ctx["n_axes"] = len(ctx["axes"])
    # Alignment column of the `.card.<cls>::before` accent-bar rules.
    ctx["css_sel_width"] = max(
        len(f".card.{p['card_cls']}::before") for p in ctx["players"]
    )
    write_page(PAGE, env.get_template("midfielder.html.j2").render(**ctx))
