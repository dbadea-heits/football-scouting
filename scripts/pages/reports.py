"""Report archetype: the 12 `{player}-report.html` player dossiers.

Every dossier is the same 11-section skeleton, delimited by `<!-- N · TITLE -->`
comment markers, so one template renders all 12. Per-page deviations are stored
as data — nullable override columns, `report_notes` rows, the
`sumright_inline` layout flag — rather than branched on by name, which keeps
today's hand-written pages reproducible byte-for-byte.

Two column budgets in the schema are tighter than the markup, and are spent as
follows:

* `report_corners.prose_html` holds the corner body's *verbatim* inner HTML.
  Corners carry 1–2 paragraphs and their `div.sig` rows are sometimes
  interleaved between them (chupe, livakovic), which a separate bullet table
  cannot express — so `report_sig_bullets` is used for the Background section
  only, where the bullets always trail the prose.
* `report_metrics.kind` carries the element's modifier as well as its type
  ('row-diverge', 'group-na', 'note-na'), because a §7 row needs three class
  slots (row, label span, value span) and the table has two. A note has no
  value, so its `val_cls` carries the note's inline `style` instead. The
  stream also carries 'blank' rows: §7's hand-written blank-line separators
  are placed too irregularly to be a rule, so they are stored as nodes.
"""

from __future__ import annotations

import re
import sqlite3

from bs4 import BeautifulSoup, Comment

from . import read_text, write_page

ORDER = 30

BASE_SEASON = "2025-26"

CORNERS = ("Technical", "Tactical", "Physical", "Psychosocial")

# The dot glyph is a pure function of the rating, so it is derived, not stored.
DOTS = {"dot-strong": "\u25cf", "dot-adequate": "\u25d0", "dot-concern": "\u25cb"}

# Annotation comments, by the section whose marker they follow.
NOTE_KEYS = {4: "signalrow", 6: "dots", 8: "eyes", 9: "background"}

MARKER = re.compile(r"^ (\d+) · ")

# The pages escape `>` inconsistently — both `&gt;` and a bare `>` appear in
# prose — and bs4 decodes either to the same character, so the source's choice
# would be lost on the way out. Parking the entities behind private-use code
# points keeps them out of bs4's hands and round-trips each page verbatim.
ENTITIES = {"&amp;": "\ue000", "&lt;": "\ue001", "&gt;": "\ue002"}


def _protect(html: str) -> str:
    for entity, stand_in in ENTITIES.items():
        html = html.replace(entity, stand_in)
    return html


def _restore(html: str) -> str:
    for entity, stand_in in ENTITIES.items():
        html = html.replace(stand_in, entity)
    return html.replace("<br/>", "<br>")


def _inner(tag) -> str:
    """Inner HTML, verbatim but for bs4's `<br/>` serialisation."""
    return _restore(tag.decode_contents(formatter=None))


def _cls(tag, base: str) -> str:
    """The classes of `tag` other than `base`, '' when it carries no modifier."""
    return " ".join(c for c in tag.get("class", []) if c != base)


def _chip(tag) -> tuple[str, str]:
    return _cls(tag, "chip"), _inner(tag)


def _kids(tag) -> list:
    return [c for c in tag.children if getattr(c, "name", None)]


def _body(tag) -> str:
    """Inner HTML of a `div.body`, re-indented as the pages write it.

    bs4 collapses every whitespace-only text node to a bare newline, so the
    layout of a multi-element body has to be rebuilt rather than round-tripped.
    """
    assert not [c for c in tag.children if not c.name and c.strip()], tag.get("class")
    return _restore(
        "".join(f"\n      {c.decode(formatter=None)}" for c in _kids(tag)) + "\n    "
    )


def _override(value: str, inherited: str) -> str | None:
    """Store a per-report string only where it differs from the hub's."""
    return None if value == inherited else value


def _split(col) -> tuple[dict[int, list], dict[int, list[str]], dict[int, str]]:
    """Split `div.col` into its numbered sections.

    The sections are spread over two rails — identity (1-4) and detail (5-11) —
    so both are walked in document order, and the section numbering stays
    global across them.

    Returns the element children of each section, the hand-written annotation
    comments inside it, and the verbatim text of each section marker.
    """
    elements: dict[int, list] = {}
    notes: dict[int, list[str]] = {}
    markers: dict[int, str] = {}
    section = 0
    for rail in col.select("div.col > .rail"):
        for node in rail.children:
            if isinstance(node, Comment):
                found = MARKER.match(str(node))
                if found:
                    section = int(found.group(1))
                    markers[section] = _restore(str(node))
                else:
                    notes.setdefault(section, []).append(_restore(str(node)))
            elif node.name:
                elements.setdefault(section, []).append(node)
    return elements, notes, markers


def _seed_page(conn: sqlite3.Connection, pid: str) -> None:
    text = _protect(read_text(f"{pid}-report.html"))
    lines = text.splitlines()
    soup = BeautifulSoup(text, "html.parser")
    body = soup.body
    assert body["data-player"] == pid, body["data-player"]
    pos_class = " ".join(body.get("class", [])) or None
    hub = dict(
        conn.execute(
            "SELECT pos_class, name, short_name, verdict_tier, verdict_label"
            " FROM players WHERE id = ?",
            (pid,),
        ).fetchone()
    )
    assert pos_class in (None, hub["pos_class"]), f"{pid}: {pos_class}"

    elements, notes, markers = _split(soup.select_one("div.col"))
    assert sorted(markers) == list(range(1, 12)), sorted(markers)
    assert not notes.keys() - NOTE_KEYS.keys(), sorted(notes)

    # ── 1 · masthead, 2 · identity ──────────────────────────────────────────
    date_line = _inner(elements[1][0])
    heading, posline, facts_div, *rest = elements[2]
    facts_footnote = _inner(rest[0]) if rest else None
    facts = facts_div.select("span.fact")
    assert len(facts) == 5, f"{pid}: {len(facts)} facts"
    for idx, fact in enumerate(facts):
        val = fact.select_one("span.val")
        conn.execute(
            "INSERT INTO report_facts (player_id, idx, label, val, risk_cls)"
            " VALUES (?,?,?,?,?)",
            (pid, idx, _inner(fact.select_one("span.label")), _inner(val),
             _cls(val, "val")),
        )

    # ── 3 · verdict band ────────────────────────────────────────────────────
    verdict = elements[3][0]
    tier_span = verdict.select_one("span.tier")
    assert tier_span.get("class") == ["tier", f"tier-{hub['verdict_tier']}"], pid
    for idx, para in enumerate(verdict.select("details .body > p")):
        conn.execute(
            "INSERT INTO report_prose (player_id, section, idx, html) VALUES (?,?,?,?)",
            (pid, "verdict", idx, _inner(para)),
        )

    # ── 4 · signal row ──────────────────────────────────────────────────────
    signals = elements[4][0].select("div")
    assert len(signals) == 3, f"{pid}: {len(signals)} signals"
    for idx, sig in enumerate(signals):
        conn.execute(
            "INSERT INTO signal_defs (player_id, idx, label) VALUES (?,?,?)",
            (pid, idx, _inner(sig.select_one("span.label"))),
        )
        conn.execute(
            "INSERT INTO season_signals (player_id, season, idx, num, pctl)"
            " VALUES (?,?,?,?,?)",
            (pid, BASE_SEASON, idx, _inner(sig.select_one("span.num")),
             _inner(sig.select_one("span.pctl"))),
        )
    signals_footnote = _inner(elements[4][1]) if len(elements[4]) > 1 else None

    # ── 5 · dormant potential ───────────────────────────────────────────────
    dormant = elements[5][0]
    dormant_chip = _chip(dormant.select_one("summary .chip"))
    for idx, para in enumerate(dormant.select(".body > p")):
        conn.execute(
            "INSERT INTO report_prose (player_id, section, idx, html) VALUES (?,?,?,?)",
            (pid, "dormant", idx, _inner(para)),
        )

    # ── 6 · four corners ────────────────────────────────────────────────────
    head, *details_list = elements[6]
    dots = head.select("span.dots > span")
    assert len(details_list) == 4 and len(dots) == 4, pid
    comments = [n for n in notes.get(6, []) if n.strip() in CORNERS]
    assert len(comments) in (0, 4), f"{pid}: {len(comments)} corner comments"
    for pos, (corner, dot, details) in enumerate(zip(CORNERS, dots, details_list)):
        dot_cls = " ".join(dot["class"])
        assert _inner(dot) == DOTS[dot_cls], f"{pid}: {dot_cls} glyph"
        assert _inner(details.select_one("summary .label")) == corner, pid
        chips = [_chip(c) for c in details.select("summary .chip")]
        assert 1 <= len(chips) <= 2, f"{pid}/{corner}: {len(chips)} chips"
        chip2 = chips[1] if len(chips) > 1 else (None, None)
        conn.execute(
            "INSERT INTO report_corners (player_id, corner, dot_cls, dot_title,"
            " chip_cls, chip_label, chip2_cls, chip2_label, comment, prose_html)"
            " VALUES (?,?,?,?,?,?,?,?,?,?)",
            (pid, corner, dot_cls, dot.get("title"), *chips[0], *chip2,
             comments[pos] if comments else None,
             _body(details.select_one("div.body"))),
        )

    # ── 7 · full metrics ────────────────────────────────────────────────────
    # The stream carries the body's hand-written blank-line separators as
    # nodes of their own; their placement is irregular enough per page that it
    # is data, not a rule (bs4 has already collapsed them, hence `lines`).
    nodes = _kids(elements[7][0].select_one("div.body"))
    stream = []
    for node in nodes:
        if not lines[node.sourceline - 2].strip():
            stream.append(("blank", "", "", "", ""))
        classes = node.get("class", [])
        if "mrow" in classes:
            label, val = _kids(node)
            stream.append(("row-diverge" if "diverge" in classes else "row",
                           _inner(label), " ".join(label.get("class", [])),
                           _inner(val), _cls(val, "mv")))
        elif "mgroup" in classes:
            stream.append(("group-na" if "na" in classes else "group",
                           _inner(node), "", "", ""))
        else:
            stream.append(("note" if "diverge-note" in classes else "note-na",
                           _inner(node), " ".join(classes), "",
                           node.get("style", "")))
    last = nodes[-1]
    if not lines[last.sourceline + str(last).count("\n")].strip():
        stream.append(("blank", "", "", "", ""))
    conn.executemany(
        "INSERT INTO report_metrics (player_id, idx, kind, label, label_cls,"
        " val, val_cls) VALUES (?,?,?,?,?,?,?)",
        [(pid, idx, *row) for idx, row in enumerate(stream)],
    )

    # ── 8 · eye test ────────────────────────────────────────────────────────
    eye = elements[8][0]
    letters = eye.select("summary .eyes > span")
    eyerows = eye.select(".body > div.eyerow")
    assert len(letters) == 5 and len(eyerows) == 5, f"{pid}: {len(eyerows)} eye rows"
    for idx, (letter, row) in enumerate(zip(letters, eyerows)):
        criterion, chip = _kids(row.select_one("div.top"))
        conn.execute(
            "INSERT INTO report_eye_rows (player_id, idx, criterion, chip_cls,"
            " chip_label, letter, letter_cls, obs_html, cornertag, title)"
            " VALUES (?,?,?,?,?,?,?,?,?,?)",
            (pid, idx, _inner(criterion), *_chip(chip), _inner(letter),
             " ".join(letter.get("class", [])) or None,
             _inner(row.select_one("p.obs")),
             _inner(row.select_one("span.cornertag")), letter.get("title")),
        )
    for idx, note in enumerate(eye.select(".body > p.diverge-note")):
        conn.execute(
            "INSERT INTO report_eye_notes (player_id, idx, text) VALUES (?,?,?)",
            (pid, idx, _inner(note)),
        )

    # ── 9 · background ──────────────────────────────────────────────────────
    background = elements[9][0]
    bg_chips = [_chip(c) for c in background.select("summary .chip")]
    assert len(bg_chips) == 2, f"{pid}: {len(bg_chips)} background chips"
    for idx, para in enumerate(background.select(".body > p")):
        conn.execute(
            "INSERT INTO report_prose (player_id, section, idx, html) VALUES (?,?,?,?)",
            (pid, "background", idx, _inner(para)),
        )
    for idx, sig in enumerate(background.select(".body > div.sig")):
        src, text = _kids(sig)
        conn.execute(
            "INSERT INTO report_sig_bullets (player_id, section, idx, src, src_cls,"
            " text, text_cls) VALUES (?,?,?,?,?,?,?)",
            (pid, "background", idx, _inner(src), _cls(src, "src"), _inner(text),
             " ".join(text.get("class", []))),
        )

    # ── 10 · philosophy fit ─────────────────────────────────────────────────
    philosophy = elements[10][0]
    tally_cls, tally = _chip(philosophy.select_one("summary .chip"))
    for idx, check in enumerate(philosophy.select("div.check")):
        mark, text = _kids(check)
        conn.execute(
            "INSERT INTO report_checks (player_id, idx, mark_cls, mark, text)"
            " VALUES (?,?,?,?,?)",
            (pid, idx, _cls(mark, "mark"), _inner(mark), _inner(text)),
        )

    # ── 11 · methods footer ─────────────────────────────────────────────────
    footer, closing = elements[11]
    methods = footer.select("span")
    assert len(methods) == 5, f"{pid}: {len(methods)} methods"
    for idx, method in enumerate(methods):
        on = method["class"] == ["m-on"]
        label = _inner(method)
        assert label.startswith("\u25a3 " if on else "\u25a1 "), label
        conn.execute(
            'INSERT INTO report_methods (player_id, idx, label, "on") VALUES (?,?,?,?)',
            (pid, idx, label[2:], int(on)),
        )

    # ── the report row itself ───────────────────────────────────────────────
    mini = soup.find(id="mini")
    mini_chip = mini.select_one("span.chip")
    mini_label = _inner(mini_chip)
    tier_label = _inner(tier_span)
    crumb = _inner(soup.select_one("span.topnav-crumb")).removesuffix(" · Full Profile")
    # Casing is hand-chosen per page, but the wording must still be the verdict.
    assert mini_label.casefold() == hub["verdict_label"].casefold(), pid
    assert tier_label.casefold() == hub["verdict_label"].casefold(), pid
    conn.execute(
        "INSERT INTO reports (player_id, pos_class, date_line, posline,"
        " heading_name, crumb_name, tier_label, mini_name, mini_chip_cls,"
        " mini_chip_label, dormant_chip_cls, dormant_chip_label, philosophy_tally,"
        " philosophy_chip_cls, sumright_inline, srcline, facts_footnote,"
        " signals_footnote, closing_footnote, liveobs_html, nextstep_html,"
        " philosophy_html, bg_chip1_cls, bg_chip1_label, bg_chip2_cls, bg_chip2_label)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (pid, pos_class, date_line, _inner(posline),
         _override(_inner(heading), hub["name"]),
         _override(crumb, hub["name"]),
         _override(tier_label, hub["verdict_label"]),
         _override(_inner(mini.select_one("span.name")), hub["short_name"]),
         _cls(mini_chip, "chip"),
         _override(mini_label, hub["verdict_label"]),
         *dormant_chip, tally, tally_cls,
         int("\n" not in head.select_one("span.dots").decode_contents()),
         _inner(eye.select_one("p.srcline")), facts_footnote, signals_footnote,
         _inner(closing), _inner(verdict.select_one("p.liveobs")),
         _inner(verdict.select_one("p.nextstep")),
         _inner(philosophy.select_one("p.philosophy")),
         *bg_chips[0], *bg_chips[1]),
    )

    # ── hand-written annotation comments ────────────────────────────────────
    page_notes = {"signalrow": markers[4]}
    mini_note = mini.find(string=lambda s: isinstance(s, Comment))
    if mini_note is not None:
        page_notes["mini"] = _restore(str(mini_note))
    for section, key in NOTE_KEYS.items():
        extra = [n for n in notes.get(section, []) if n.strip() not in CORNERS]
        assert len(extra) <= 1, f"{pid}: {len(extra)} notes in section {section}"
        if extra:
            page_notes[key] = extra[0]
    conn.executemany(
        "INSERT INTO report_notes (player_id, key, text) VALUES (?,?,?)",
        [(pid, key, text) for key, text in page_notes.items()],
    )


def seed(conn: sqlite3.Connection) -> None:
    players = [r[0] for r in conn.execute("SELECT id FROM players ORDER BY sort")]
    assert len(players) == 12, f"expected 12 report players, found {len(players)}"
    for pid in players:
        _seed_page(conn, pid)


def _rows(conn: sqlite3.Connection, sql: str, *args) -> list[dict]:
    return [dict(r) for r in conn.execute(sql, args)]


def context(conn: sqlite3.Connection, pid: str) -> dict:
    report = dict(
        conn.execute(
            "SELECT r.*, p.verdict_tier,"
            " COALESCE(r.heading_name, p.name) AS heading,"
            " COALESCE(r.crumb_name, p.name) AS crumb,"
            " COALESCE(r.tier_label, p.verdict_label) AS tier,"
            " COALESCE(r.mini_name, p.short_name) AS mini,"
            " COALESCE(r.mini_chip_label, p.verdict_label) AS mini_chip"
            " FROM reports r JOIN players p ON p.id = r.player_id"
            " WHERE r.player_id = ?",
            (pid,),
        ).fetchone()
    )
    corners = {
        row["corner"]: row
        for row in _rows(conn, "SELECT * FROM report_corners WHERE player_id = ?", pid)
    }
    notes = {key: None for key in ("mini", "signalrow", "dots", "eyes", "background")}
    notes.update(
        (r["key"], r["text"])
        for r in conn.execute(
            "SELECT key, text FROM report_notes WHERE player_id = ?", (pid,)
        )
    )
    prose = {"verdict": [], "dormant": [], "background": []}
    for row in conn.execute(
        "SELECT section, html FROM report_prose WHERE player_id = ?"
        " ORDER BY section, idx",
        (pid,),
    ):
        prose[row["section"]].append(row["html"])

    return {
        **report,
        "notes": notes,
        "inline": bool(report["sumright_inline"]),
        "glyphs": DOTS,
        "facts": _rows(
            conn, "SELECT * FROM report_facts WHERE player_id = ? ORDER BY idx", pid
        ),
        "signals": _rows(
            conn,
            "SELECT d.label, s.num, s.pctl FROM signal_defs d"
            " JOIN season_signals s ON s.player_id = d.player_id AND s.idx = d.idx"
            " WHERE d.player_id = ? AND s.season = ? ORDER BY d.idx",
            pid,
            BASE_SEASON,
        ),
        "corners": [corners[corner] for corner in CORNERS],
        "metrics": _rows(
            conn, "SELECT * FROM report_metrics WHERE player_id = ? ORDER BY idx", pid
        ),
        "eye_rows": _rows(
            conn, "SELECT * FROM report_eye_rows WHERE player_id = ? ORDER BY idx", pid
        ),
        "eye_notes": [
            r["text"]
            for r in conn.execute(
                "SELECT text FROM report_eye_notes WHERE player_id = ? ORDER BY idx",
                (pid,),
            )
        ],
        "verdict_prose": prose["verdict"],
        "dormant_prose": prose["dormant"],
        "bg_prose": prose["background"],
        "bg_sigs": _rows(
            conn,
            "SELECT * FROM report_sig_bullets WHERE player_id = ? AND section = ?"
            " ORDER BY idx",
            pid,
            "background",
        ),
        "checks": _rows(
            conn, "SELECT * FROM report_checks WHERE player_id = ? ORDER BY idx", pid
        ),
        "methods": _rows(
            conn,
            'SELECT label, "on" FROM report_methods WHERE player_id = ? ORDER BY idx',
            pid,
        ),
    }


def build(conn: sqlite3.Connection, env) -> None:
    template = env.get_template("report.html.j2")
    for row in conn.execute("SELECT player_id FROM reports ORDER BY player_id"):
        pid = row["player_id"]
        write_page(f"{pid}-report.html", template.render(**context(conn, pid)))
