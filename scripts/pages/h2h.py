"""H2H archetype: the four `{id}-comparison.html` head-to-head dossiers.

One rigid skeleton — identity cards, four-corners matrix, mirrored metric bars,
radar, divergence cards, optional acquisition landscape, verdict — shared by
alvarez-lautaro, lautaro-guirassy, balde-cancelo and inacio-lukeba. Per-page
deviations (section renumbering, the missing acquisition section, inacio's
two-line radar axes and methodology paragraph, hand-written LTR/RTL bar
asymmetries) are stored as data, not branched on by page name.

The radar `<script>` payload is not parsed back out of JavaScript: AXES, the two
normalised data arrays, the benchmark comment block, the axis-label radius and
the polygon draw order are hand-ported literals below. A transcription error
surfaces immediately as a byte diff when the page is regenerated.
"""

from __future__ import annotations

import json
import re
import sqlite3

from bs4 import BeautifulSoup

from . import read_text, write_page

ORDER = 40

CORNERS = ("Technical", "Tactical", "Physical", "Psychosocial")

# Section keys in emission order; `acquisition` is absent on two pages.
SECTIONS = (
    ("identity", "IDENTITY CARDS"),
    ("corners", "FOUR CORNERS MATRIX"),
    ("metrics", "KEY METRICS COMPARISON"),
    ("radar", "RADAR"),
    ("divergence", "DIVERGENCE ANALYSIS"),
    ("acquisition", "ACQUISITION LANDSCAPE"),
    ("verdict", "VERDICT"),
)

SUB_OPEN = '<span style="font-size:9px;color:var(--muted)">'
DIVERGE_TAG = '<span class="diverge-tag">≠</span>'

# ── Hand-ported radar payloads ─────────────────────────────────────────────
# axes/p1/p2 are the JS literals; notes is the benchmark comment block emitted
# verbatim between AXES and P1_DATA; radius is the `(R + n)` axis-label offset;
# p1_on_top means the p1 polygon is drawn last (it wins the overlap).

RADAR = {
    "alvarez-lautaro": {
        "axes": ["xG/90", "G/90", "KP/90", "UCL G/90", "Shots/90"],
        "p1": [62, 71, 88, 66, 63],
        "p2": [88, 94, 61, 96, 94],
        "notes": "  // normalized 0-100 against elite CF benchmarks",
        "radius": 22,
        "p1_on_top": 1,
        "multiline": 0,
    },
    "lautaro-guirassy": {
        "axes": ["xG/90", "G/90", "UCL G/90", "Aerial %", "Shots/90"],
        "p1": [78, 89, 61, 58, 94],
        "p2": [94, 80, 95, 100, 77],
        "notes": (
            "  // Normalized against elite CF benchmarks\n"
            "  // xG/90 ref 0.90:   L=0.70→78,  G=0.85→94\n"
            "  // G/90 ref 0.90:    L=0.80→89,  G=0.72→80\n"
            "  // UCL G/90 ref 1.75: L=1.06→61, G=1.66→95\n"
            "  // Aerial % ref 60:  L=~35→58,   G=~60→100\n"
            "  // Shots/90 ref 4.00: L=3.76→94, G=3.07→77"
        ),
        "radius": 22,
        "p1_on_top": 0,
        "multiline": 0,
    },
    "balde-cancelo": {
        "axes": ["xA/90", "Prog Carries", "Dribble %", "Top Speed", "Key Passes/90"],
        "p1": [47, 82, 73, 98, 52],
        "p2": [73, 60, 90, 85, 84],
        "notes": (
            "  // Normalized against elite attacking LB benchmarks\n"
            "  // xA/90 ref 0.30:        B=0.14→47,  C=0.22→73\n"
            "  // Prog Carries ref 10:   B=8.2→82,   C=6.0→60\n"
            "  // Dribble % ref 80:      B=58→73,    C=72→90\n"
            "  // Top Speed ref 37 km/h: B=36.2→98,  C=31.4→85\n"
            "  // Key Passes ref 2.5:    B=1.3→52,   C=2.1→84"
        ),
        "radius": 26,
        "p1_on_top": 0,
        "multiline": 0,
    },
    "inacio-lukeba": {
        "axes": [
            "Ball\nProgression",
            "Anticipation",
            "Distribution",
            "Press Fit",
            "Availability",
        ],
        "p1": [94, 68, 90, 70, 86],
        "p2": [68, 88, 82, 62, 64],
        "notes": """
  /*
   * Normalised against elite LCB benchmarks for high-line possession shapes.
   *
   * Ball Progression (ref: top-99% global CB progressive output — Inácio benchmark):
   *   Inácio  → top 99% prog passes + top 97% carries  = 94
   *   Lukeba  → 74th pct deep progressions              = 68
   *
   * Anticipation (ref: 94th pct ball recoveries — Lukeba benchmark):
   *   Inácio  → press-trigger, ~65th pct interceptions  = 68
   *   Lukeba  → 94th pct recoveries + 65th pct int      = 88
   *
   * Distribution (ref: 90%+ completion under match press):
   *   Inácio  → 90.01%, 88.6 passes/90, UCL-validated   = 90
   *   Lukeba  → 90% (2025-26), 84th pct touches         = 82
   *
   * Press Fit (ref: top speed 36+ km/h + high pressing output + aerial coverage):
   *   Inácio  → 34 km/h, press-trigger profile, aerial 47.7%    = 70
   *   Lukeba  → 34.69 km/h, 30th pct pressures, aerial unknown  = 62
   *
   * Availability (ref: full-season injury-free):
   *   Inácio  → medium risk, 42 apps, all episodes brief  = 86
   *   Lukeba  → HIGH risk, ~32% missed peak, improving    = 64
   */""",
        "radius": 30,
        "p1_on_top": 0,
        "multiline": 1,
    },
}

PAGE_IDS = tuple(RADAR)

# Hand-written, not uniform: alvarez-lautaro stops at 5, the rest run to 6.
DIVERGENCES = {
    "alvarez-lautaro": 5,
    "lautaro-guirassy": 6,
    "balde-cancelo": 6,
    "inacio-lukeba": 6,
}


class _Source:
    """A committed page, located with bs4 but read back verbatim.

    bs4 collapses a whitespace-only text node containing a newline to a bare
    `\\n`, which destroys the hand-written indentation of every block whose
    body opens with a tag, and `decode_contents()` re-encodes `&nbsp;` and
    `<br>`. Elements are therefore *found* with bs4 and *read* by slicing the
    original bytes at the element's recorded source position.
    """

    def __init__(self, raw: str):
        self.raw = raw
        self.soup = BeautifulSoup(raw, "html.parser")
        self.line_starts = [0] + [
            i + 1 for i, ch in enumerate(raw) if ch == "\n"
        ]

    def one(self, selector: str):
        tag = self.soup.select_one(selector)
        assert tag is not None, selector
        return tag

    def _span(self, tag) -> tuple[int, int]:
        """(end of the opening tag, start of the closing tag)."""
        start = self.line_starts[tag.sourceline - 1] + tag.sourcepos
        assert self.raw[start] == "<", self.raw[start : start + 20]
        i, quote = start, ""
        while self.raw[i] != ">" or quote:
            if quote:
                quote = "" if self.raw[i] == quote else quote
            elif self.raw[i] in "\"'":
                quote = self.raw[i]
            i += 1
        open_end = i + 1
        pattern = re.compile(rf"</?{tag.name}\b")
        depth, pos = 1, open_end
        while True:
            m = pattern.search(self.raw, pos)
            assert m, tag.name
            depth += -1 if m.group(0).startswith("</") else 1
            if depth == 0:
                return open_end, m.start()
            pos = m.end()

    def inner(self, tag) -> str:
        open_end, close_start = self._span(tag)
        return self.raw[open_end:close_start]

    def outer(self, tag) -> str:
        start = self.line_starts[tag.sourceline - 1] + tag.sourcepos
        _, close_start = self._span(tag)
        return self.raw[start : self.raw.index(">", close_start) + 1]

    def text(self, tag) -> str:
        """Inner HTML of an element written on a single line."""
        inner = self.inner(tag)
        assert "\n" not in inner, repr(inner)
        return inner

    def block(self, tag) -> str:
        """Inner HTML of an element written across its own lines, indent kept.

        `<div>\\n          body\\n        </div>` → `          body`, so the
        template re-emits the body on its own line without re-deriving the
        indentation.
        """
        inner = self.inner(tag)
        assert inner.startswith("\n") and inner.rstrip(" ").endswith("\n"), repr(inner)
        return inner[1:].rstrip(" ")[:-1]

    def line(self, tag) -> str:
        block = self.block(tag)
        assert "\n" not in block, repr(block)
        return block


def _width(tag) -> int:
    m = re.fullmatch(r"width:(\d+)%", tag["style"])
    assert m, tag["style"]
    return int(m.group(1))


def _bar(src: "_Source", line) -> dict:
    """One `.bar-line`: which side, how wide, the value and its emphasis."""
    fill = line.select_one(".bar-fill")
    classes = fill.get("class")
    assert classes[0] == "bar-fill" and len(classes) == 2, classes
    val = line.select_one(".bar-val")
    val_classes = [c for c in val.get("class") if c != "bar-val"]
    assert val_classes in ([], ["best-p1"], ["best-p2"]), val_classes
    return {
        "name": src.text(line.select_one(".bar-name")),
        "side": classes[1],
        "width": _width(fill),
        "best": 1 if val_classes else 0,
        "val": src.text(val),
        "style": val.get("style"),
    }


def _style_tokens(raw: str) -> dict:
    """`--p1: #e8a020;  /* Álvarez */` pairs, plus any trailing block comment."""
    head = raw[raw.index("<style>") + len("<style>") : raw.index("</style>")]
    tokens = {
        m.group(1): (m.group(2), m.group(3))
        for m in re.finditer(
            r"^  --(p[12](?:-dim|-glow)?): +([^;]+);(?: +/\* (.*) \*/)?$", head, re.M
        )
    }
    assert len(tokens) == 6, sorted(tokens)
    note = re.search(r"^(/\* .* \*/)$", head, re.M)
    return {"tokens": tokens, "note": note.group(1) if note else None}


def _section_numbers(raw: str) -> dict:
    return {
        title: int(num)
        for num, title in re.findall(r"<!-- (\d+) · (.+?) -->", raw)
    }


def _seed_page(conn: sqlite3.Connection, pid: str) -> None:
    src = _Source(read_text(f"{pid}-comparison.html"))
    soup, raw = src.soup, src.raw
    radar = RADAR[pid]

    style = _style_tokens(raw)
    tokens = style["tokens"]

    # ── header ────────────────────────────────────────────────────────────
    shorts = {s: src.text(src.one(f".{s}-name")) for s in ("p1", "p2")}
    chips = soup.select(".header-chips .chip")
    assert len(chips) == 3, len(chips)
    chip_cols = []
    for chip in chips:
        classes = chip.get("class")
        assert classes[0] == "chip" and len(classes) == 2, classes
        chip_cols += [classes[1], src.text(chip)]

    # ── identity + verdict, per side ──────────────────────────────────────
    sides = {}
    for side in ("p1", "p2"):
        card = src.one(f".id-card.{side}-card")
        tier = card.select_one(".id-verdict .verdict-tier")
        tier_classes = tier.get("class")
        assert tier_classes[0] == "verdict-tier" and len(tier_classes) == 2, tier_classes
        assert src.text(card.select_one(".verdict-label")) == "Scout Verdict"
        box = src.one(f".verdict-box.{side}-box")
        big = box.select_one(".verdict-tier-big")
        assert big.get("class") == ["verdict-tier-big", side], big.get("class")
        name = src.text(card.select_one(".id-name"))
        assert src.text(box.select_one(".verdict-player")) == name
        sides[side] = {
            "name": name,
            "club_line": src.text(card.select_one(".id-club")),
            "tier_cls": tier_classes[1],
            "tier": src.text(tier),
            "tier_big": src.text(big),
            "verdict_html": src.block(box.select_one(".verdict-text")),
        }

        facts = card.select(".id-fact")
        assert len(facts) == 8, f"{pid}/{side}: {len(facts)} identity facts"
        for idx, fact in enumerate(facts):
            val = fact.select_one(".id-fact-val")
            val_classes = [c for c in val.get("class") if c != "id-fact-val"]
            assert len(val_classes) <= 1, val_classes
            conn.execute(
                "INSERT INTO h2h_id_facts (page_id, side, idx, label, val,"
                " val_cls, val_style) VALUES (?,?,?,?,?,?,?)",
                (
                    pid,
                    side,
                    idx,
                    src.text(fact.select_one(".id-fact-label")),
                    src.text(val),
                    " ".join(val_classes),
                    val.get("style"),
                ),
            )

    # ── four corners ──────────────────────────────────────────────────────
    cells = soup.select(".fc-grid > .fc-cell")
    assert len(cells) == 2 + 2 * len(CORNERS), len(cells)
    for i, corner in enumerate(CORNERS):
        for j, side in enumerate(("p1", "p2")):
            cell = cells[2 + 2 * i + j]
            assert src.text(cell.select_one(".fc-corner-name")) == corner
            dot, badge = cell.select_one(".fc-dot"), cell.select_one(".fc-badge")
            dot_cls = dot.get("class")[1]
            assert src.text(dot) == ("◐" if dot_cls == "adequate" else "●")
            conn.execute(
                "INSERT INTO h2h_corners (page_id, side, corner, dot_cls,"
                " badge_cls, badge_label, evidence_html) VALUES (?,?,?,?,?,?,?)",
                (
                    pid,
                    side,
                    corner,
                    dot_cls,
                    badge.get("class")[1],
                    src.text(badge),
                    src.block(cell.select_one(".fc-evidence")),
                ),
            )
    header_comment = cells[0].find_previous(string=lambda s: "header row" in s)

    # ── metric stream ─────────────────────────────────────────────────────
    section = src.one(".metric-section")
    initials = set()
    for idx, node in enumerate(section.find_all(recursive=False)):
        classes = node.get("class")
        if classes == ["metric-group-header"]:
            conn.execute(
                "INSERT INTO h2h_metrics (page_id, idx, kind, group_label)"
                " VALUES (?,?,'group',?)",
                (pid, idx, src.text(node)),
            )
            continue
        assert classes[0] == "metric-row", classes

        note = node.select_one(".metric-note")
        if note is not None:
            assert node["style"] == "padding-top:4px;padding-bottom:10px"
            conn.execute(
                "INSERT INTO h2h_metrics (page_id, idx, kind, note_html, note_style)"
                " VALUES (?,?,'note',?,?)",
                (pid, idx, src.block(note), note["style"]),
            )
            continue

        assert classes[1:] in ([], ["diverge"]), classes
        diverge = 1 if classes[1:] == ["diverge"] else 0

        label_html = src.text(node.select_one(".metric-label"))
        if diverge:
            assert DIVERGE_TAG in label_html, label_html
            label_html = label_html.replace(DIVERGE_TAG, "", 1)
        label, _, rest = label_html.partition("<br>")
        assert rest.startswith(SUB_OPEN) and rest.endswith("</span>"), rest
        sub_html = rest[len(SUB_OPEN) : -len("</span>")]

        wraps = node.select(".metric-bar-wrap")
        assert len(wraps) == 2 and wraps[1]["style"] == "direction:rtl", len(wraps)
        left = [_bar(src, b) for b in wraps[0].select(".bar-line")]
        right = [_bar(src, b) for b in wraps[1].select(".bar-line")]
        assert len(left) == len(right) == 2
        override = {}
        for pos, (side, lo, ro) in enumerate(zip(("p1", "p2"), left, right)):
            assert lo["side"] == ro["side"] == side, (lo["side"], ro["side"])
            assert lo["name"] == ro["name"] and lo["best"] == ro["best"]
            assert lo["style"] in (None, "color:var(--muted)"), lo["style"]
            assert ro["style"] in (
                "text-align:right",
                "text-align:right;color:var(--muted)",
            ), ro["style"]
            lo["muted"] = 1 if lo["style"] else 0
            ro["muted"] = 1 if "muted" in ro["style"] else 0
            initials.add((pos, lo["name"]))
            # The RTL block is a hand-copied mirror of the LTR one; two cells
            # drifted on alvarez-lautaro. Record only the drift.
            drift = {k: ro[k] for k in ("width", "val", "muted") if ro[k] != lo[k]}
            if drift:
                override[side] = drift

        conn.execute(
            "INSERT INTO h2h_metrics (page_id, idx, kind, label, diverge, sub_html,"
            " p1_width, p1_val, p1_best, p2_width, p2_val, p2_best,"
            " p1_val_style, p2_val_style, right_override)"
            " VALUES (?,?,'row',?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                pid,
                idx,
                label,
                diverge,
                sub_html,
                left[0]["width"],
                left[0]["val"],
                left[0]["best"],
                left[1]["width"],
                left[1]["val"],
                left[1]["best"],
                left[0]["style"],
                left[1]["style"],
                json.dumps(override, ensure_ascii=False) if override else None,
            ),
        )
    initials = dict(sorted(initials))
    assert set(initials) == {0, 1}, initials

    # ── divergence cards ──────────────────────────────────────────────────
    cards = soup.select(".divg-grid > .divg-card")
    assert len(cards) == DIVERGENCES[pid], f"{pid}: {len(cards)} divergence cards"
    for idx, card in enumerate(cards):
        assert card.get("class") == ["divg-card", "key"], card.get("class")
        conn.execute(
            "INSERT INTO h2h_divg (page_id, idx, title, body_html) VALUES (?,?,?,?)",
            (
                pid,
                idx,
                src.text(card.select_one(".divg-title")),
                src.block(card.select_one(".divg-body")),
            ),
        )

    # ── acquisition landscape (two pages) ─────────────────────────────────
    has_acquisition = 1 if soup.select_one(".acq-grid") else 0
    if has_acquisition:
        for side in ("p1", "p2"):
            card = src.one(f".acq-card.{side}-card")
            assert src.text(card.select_one(".acq-player")) == sides[side]["name"]
            rows = card.select(".acq-row")
            assert len(rows) == 8, f"{pid}/{side}: {len(rows)} acquisition rows"
            for idx, row in enumerate(rows):
                val = row.select_one(".acq-val")
                conn.execute(
                    "INSERT INTO h2h_acq (page_id, side, idx, key, val, val_cls)"
                    " VALUES (?,?,?,?,?,?)",
                    (
                        pid,
                        side,
                        idx,
                        src.text(row.select_one(".acq-key")),
                        src.text(val),
                        " ".join(c for c in val.get("class") if c != "acq-val"),
                    ),
                )

    # ── section numbering + labels ────────────────────────────────────────
    numbers = _section_numbers(raw)
    labels = [src.text(el) for el in soup.select(".section-label")]
    keys = [k for k, _ in SECTIONS if k != "acquisition" or has_acquisition]
    assert len(labels) == len(keys), (len(labels), len(keys))
    for key, label in zip(keys, labels):
        conn.execute(
            "INSERT INTO h2h_sections (page_id, section, num, label) VALUES (?,?,?,?)",
            (pid, key, numbers[dict(SECTIONS)[key]], label),
        )

    # ── page row ──────────────────────────────────────────────────────────
    intro = src.one(".fc-grid").find_previous("p")
    methodology = section.find_previous_sibling("p")
    values = (
        pid,
        src.text(soup.title),
        src.text(src.one(".label-pill")),
        src.line(src.one("p.header-sub")),
        *chip_cols,
        sides["p1"]["name"],
        shorts["p1"],
        initials[0],
        sides["p1"]["club_line"],
        tokens["p1"][0],
        tokens["p1-dim"][0],
        tokens["p1-glow"][0],
        tokens["p1"][1],
        sides["p1"]["tier_cls"],
        sides["p1"]["tier"],
        sides["p1"]["tier_big"],
        sides["p1"]["verdict_html"],
        sides["p2"]["name"],
        shorts["p2"],
        initials[1],
        sides["p2"]["club_line"],
        tokens["p2"][0],
        tokens["p2-dim"][0],
        tokens["p2-glow"][0],
        tokens["p2"][1],
        sides["p2"]["tier_cls"],
        sides["p2"]["tier"],
        sides["p2"]["tier_big"],
        sides["p2"]["verdict_html"],
        style["note"],
        src.block(intro),
        f"<!--{header_comment}-->" if header_comment else None,
        json.dumps(radar["axes"], ensure_ascii=False),
        json.dumps(radar["p1"]),
        json.dumps(radar["p2"]),
        radar["notes"],
        src.outer(src.one(".radar-wrap > p")),
        radar["multiline"],
        radar["radius"],
        radar["p1_on_top"],
        src.outer(methodology) if methodology else None,
        has_acquisition,
        src.text(src.one(".rec-label")),
        src.block(src.one(".rec-text")),
        src.text(src.one(".footer-left")),
        src.text(src.one(".footer-right")),
    )
    conn.execute(
        "INSERT INTO h2h_pages VALUES (" + ",".join("?" * len(values)) + ")", values
    )


def seed(conn: sqlite3.Connection) -> None:
    for pid in PAGE_IDS:
        _seed_page(conn, pid)


def _js_axes(axes: list[str]) -> str:
    quoted = [
        "'" + a.replace("\\", "\\\\").replace("'", "\\'").replace("\n", "\\n") + "'"
        for a in axes
    ]
    return "[" + ", ".join(quoted) + "]"


# `  const P1_DATA = [...];` is padded out to this column before its `// name`.
DATA_COMMENT_COL = 42


def context(conn: sqlite3.Connection, pid: str) -> dict:
    page = dict(conn.execute("SELECT * FROM h2h_pages WHERE id = ?", (pid,)).fetchone())

    page["sections"] = {
        r["section"]: dict(r)
        for r in conn.execute(
            "SELECT section, num, label FROM h2h_sections WHERE page_id = ?", (pid,)
        )
    }

    facts = {"p1": [], "p2": []}
    for r in conn.execute(
        "SELECT * FROM h2h_id_facts WHERE page_id = ? ORDER BY side, idx", (pid,)
    ):
        facts[r["side"]].append(dict(r))
    page["id_facts"] = facts

    corners = {}
    for r in conn.execute("SELECT * FROM h2h_corners WHERE page_id = ?", (pid,)):
        cell = dict(r)
        cell["dot"] = "◐" if cell["dot_cls"] == "adequate" else "●"
        corners[r["corner"] + r["side"]] = cell
    page["corners"] = [
        {"tag": c.upper(), "name": c, "p1": corners[c + "p1"], "p2": corners[c + "p2"]}
        for c in CORNERS
    ]

    metrics = []
    for r in conn.execute(
        "SELECT * FROM h2h_metrics WHERE page_id = ? ORDER BY idx", (pid,)
    ):
        m = dict(r)
        if m["kind"] == "row":
            override = json.loads(m["right_override"]) if m["right_override"] else {}
            m["left"], m["right"] = [], []
            for side, initial in (("p1", page["p1_initial"]), ("p2", page["p2_initial"])):
                base = {
                    "name": initial,
                    "side": side,
                    "width": m[f"{side}_width"],
                    "val": m[f"{side}_val"],
                    "cls": f" best-{side}" if m[f"{side}_best"] else "",
                    "muted": 1 if m[f"{side}_val_style"] else 0,
                }
                m["left"].append(base)
                m["right"].append({**base, **override.get(side, {})})
        metrics.append(m)
    page["metrics"] = metrics

    page["divg"] = [
        dict(r)
        for r in conn.execute(
            "SELECT * FROM h2h_divg WHERE page_id = ? ORDER BY idx", (pid,)
        )
    ]

    acq = {"p1": [], "p2": []}
    for r in conn.execute(
        "SELECT * FROM h2h_acq WHERE page_id = ? ORDER BY side, idx", (pid,)
    ):
        acq[r["side"]].append(dict(r))
    page["acq"] = acq

    page["radar_axes_js"] = _js_axes(json.loads(page["radar_axes"]))
    for side in ("p1", "p2"):
        arr = "[" + ", ".join(str(v) for v in json.loads(page[f"radar_{side}"])) + "]"
        page[f"radar_{side}_js"] = arr
        line = f"  const {side.upper()}_DATA = {arr};"
        page[f"radar_{side}_pad"] = " " * max(DATA_COMMENT_COL - len(line), 1)
    return page


def build(conn: sqlite3.Connection, env) -> None:
    template = env.get_template("h2h.html.j2")
    for pid in PAGE_IDS:
        write_page(f"{pid}-comparison.html", template.render(**context(conn, pid)))
