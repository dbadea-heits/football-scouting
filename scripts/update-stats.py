#!/usr/bin/env python3
"""
update-stats.py — Football Intelligence · 2026-27 Season Data Fetcher

Fetches current-season stats for every tracked player, upserts them into
data/football.db, then rebuilds every generated artifact via scripts/build.py.
Run weekly via GitHub Actions after matchday.

Source: FotMob (Opta-derived). One browser context is kept on fotmob.com and
the JSON endpoints are called same-origin from the page:

  /api/data/playerData?id={id}                      → season / tournament index
  /api/data/playerStats?playerId={id}&seasonId={e}  → per-tournament deep stats

Club competitions of the current season are aggregated into one "all comps"
line; national-team tournaments are excluded (see NATIONAL_COMP_RE).

FBref was the previous source and is no longer usable: every request — headless
Chromium, headed Chrome, plain HTTP, third-party readers — is answered with a
Cloudflare 403 interstitial. Understat was the xG/xA source and only ever
covered the big five leagues; FotMob supersedes both.

Every slot is filled only with the metric its stored caption names; a caption
with no 2026-27 equivalent (progressive passes and carries, deep progressions,
GK top speed, or any caption pinned to a past season or single competition)
stays "—". check_labels() aborts the run if the registry and the captions in
the database ever disagree, and a fetch that returns nothing never overwrites
values already stored.

Requires: pip install playwright jinja2 && playwright install chromium
"""

import json
import re
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright, Page

# ── Constants ─────────────────────────────────────────────────────────────────

CURRENT_SEASON = "2026-27"
FOTMOB_SEASON  = "2026/2027"   # FotMob statSeasons key

sys.path.insert(0, str(Path(__file__).resolve().parent))

import build  # noqa: E402
from pages import season  # noqa: E402

# Same path build.py reads (honours the FOOTBALL_DB override).
DB_PATH = build.DB_PATH

FOTMOB_HOME = "https://www.fotmob.com/"

BROWSER_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/127.0.0.0 Safari/537.36"
)

# One full match of football is the floor for publishing any per-90 rate.
MIN_RATE_MINUTES = 90

# National-team competitions are dropped from the club "all comps" aggregate.
# "FIFA Club World Cup" is a club tournament and must survive the World Cup rule.
NATIONAL_COMP_RE = re.compile(
    r"(?<!club )world cup|nations league|^euro\b|european championship"
    r"|copa am[eé]rica|africa cup|asian cup|gold cup|olympic|friendl",
    re.IGNORECASE,
)

# ── Player registry ───────────────────────────────────────────────────────────
# Each entry: player-id → config dict
#
# fotmob_id:     FotMob player page ID (in URL: /players/{id})
# position:      "fw" | "cb" | "fb" | "gk" | "cm"  (drives which metrics are read)
# signals:       one (label, key) pair per slot of the report's .signals row.
# card:          one (label, key) pair per slot of the index hub's stat card.
#
# Each label is the caption stored in the DB (signal_defs / card_stats) for that
# slot — the season toggle swaps only the number, never the caption, so a slot
# may only be filled with the very metric its caption names. A `None` key means
# the caption is tied to a past season ("xG / 90 (BL 24-25)"), to one specific
# competition ("UCL goals"), to a career total, or to a metric FotMob does not
# carry (progressive passes and carries, deep progressions, GK top speed).
# Those slots stay "—" for 2026-27 rather than borrowing a foreign number.
#
# The competition shown beside each number is derived from the player's
# current-season domestic tournament on FotMob, so it can never go stale.

PLAYERS = {
    "deniz-undav": {
        "name": "Deniz Undav",
        "fotmob_id": 661519,
        "position": "fw",
        "signals": [
            ("NP-xG/90",    "np_xg90"),
            ("Goals − xG",  "goals_minus_xg"),
            ("Shots/90",    "shots90"),
        ],
        "card": [
            ("G/90",     "g90"),
            ("G+A/90",   "ga90"),
            ("NP-xG/90", "np_xg90"),
        ],
    },
    "nicolo-tresoldi": {
        "name": "Nicolò Tresoldi",
        "fotmob_id": 1334552,
        "position": "fw",
        "signals": [
            ("npxG/90",     "np_xg90"),
            ("Goals − xG",  "goals_minus_xg"),
            ("Shots/90",    "shots90"),
        ],
        "card": [
            ("G/90",     "g90"),
            ("G+A/90",   "ga90"),
            ("NP-xG/90", "np_xg90"),
        ],
    },
    "lautaro-martinez": {
        "name": "Lautaro Martínez",
        "fotmob_id": 690230,
        "position": "fw",
        "signals": [
            ("xG / 90 (career Serie A)",     None),
            ("xG / 90 (2025/26 Serie A)",    None),
            ("UCL Goals vs xG Δ 2024/25",    None),
        ],
        "card": [
            ("G/90",   "g90"),
            ("G+A/90", "ga90"),
            ("xG/90",  "xg90"),
        ],
    },
    "orri-oskarsson": {
        "name": "Orri Steinn Óskarsson",
        "fotmob_id": 1097229,
        "position": "fw",
        "signals": [
            ("Goals / 90",           "g90"),
            ("npxG (season total)",  "npxg_total"),
            ("Goals vs npxG Δ",      "goals_minus_npxg"),
        ],
        "card": [
            ("G/90",     "g90"),
            ("G+A/90",   "ga90"),
            ("NP-xG/90", "np_xg90"),
        ],
    },
    "julian-alvarez": {
        "name": "Julián Álvarez",
        "fotmob_id": 974753,
        "position": "fw",
        "signals": [
            ("xG/90 · 24-25 La Liga",      None),
            ("Goals/90 · UCL 25-26",       None),
            ("Prog Passes/90 · 25-26",     None),
        ],
        "card": [
            ("G/90",   "g90"),
            ("G+A/90", "ga90"),
            ("xG/90",  "xg90"),
        ],
    },
    "serhou-guirassy": {
        "name": "Serhou Guirassy",
        "fotmob_id": 448540,
        "position": "fw",
        "signals": [
            ("xG / 90 (BL 24-25)",     None),
            ("Goals / 90 (BL 24-25)",  None),
            ("Aerial duel won",        "aerial_pct"),
        ],
        "card": [
            ("G/90",      "g90"),
            ("xG/90",     "xg90"),
            ("UCL goals", None),
        ],
    },
    "dominik-livakovic": {
        "name": "Dominik Livaković",
        "fotmob_id": 383971,
        "position": "gk",
        "signals": [
            ("Save % (all comps)",     "save_pct"),
            ("Top speed km/h (EL)",    None),
            ("Pass accuracy (EL)",     None),
        ],
        "card": [
            ("Sv %",     "save_pct"),
            ("km/h top", None),
            ("Pass %",   "pass_pct"),
        ],
    },
    "chupe": {
        "name": "Carlos Ruiz Rubio",
        "fotmob_id": 1669622,
        "position": "fw",
        "signals": [
            ("Goals / 90",  "g90"),
            ("xG / 90",     "xg90"),
            ("SoT conv.",   "sot_conv"),
        ],
        "card": [
            ("G/90",   "g90"),
            ("G+A/90", "ga90"),
            ("xG/90",  "xg90"),
        ],
    },
    "george-salinas": {
        "name": "Jorge Salinas Viadero",
        "fotmob_id": 1670161,
        "position": "fb",
        "signals": [
            ("Assists (25/26)",     None),
            ("FotMob Avg Rating",   "rating"),
            ("Assists / 90",        "a90"),
        ],
        "card": [
            ("Assists", "assists_total"),
            ("A/90",    "a90"),
            ("FotMob",  "rating"),
        ],
    },
    "castello-lukeba": {
        "name": "Castello Lukeba",
        "fotmob_id": 1253852,
        "position": "cb",
        "signals": [
            ("Recoveries / 90",         "recoveries90"),
            ("Touches / 90",            "touches90"),
            ("Deep Progressions / 90",  None),
        ],
        "card": [
            ("Rec/90",  "recoveries90"),
            ("Prog/90", None),
            ("FotMob",  "rating"),
        ],
    },
    "goncalo-inacio": {
        "name": "Gonçalo Inácio",
        "fotmob_id": 1165710,
        "position": "cb",
        "signals": [
            ("Prog. Passes / 90",   None),
            ("Prog. Carries / 90",  None),
            ("xA / 90",             "xa90"),
        ],
        "card": [
            ("Prog Pass/90", None),
            ("Prog Car/90",  None),
            ("UCL Rating",   None),
        ],
    },
    "gabriel-jesus": {
        "name": "Gabriel Jesus",
        "fotmob_id": 576165,
        "position": "fw",
        "signals": [
            ("xG / 90",             "xg90"),
            ("Prog. carries / 90",  None),
            ("Career xG − goals",   None),
        ],
        "card": [
            ("xG/90",           "xg90"),
            ("Prog car/90",     None),
            ("xG − G (career)", None),
        ],
    },
    "jj-gabriel": {
        "name": "JJ Gabriel",
        "fotmob_id": 1737914,
        "position": "fw",
        "signals": [
            ("Goals / 90",  "g90"),
            ("G+A / 90",    "ga90"),
            ("Shots / 90",  "shots90"),
        ],
        "card": [
            ("G/90",     "g90"),
            ("G+A/90",   "ga90"),
            ("Shots/90", "shots90"),
        ],
    },
    "jesse-bisiwu": {
        "name": "Jesse Bisiwu",
        "fotmob_id": 1656591,
        "position": "fw",
        "signals": [
            ("Succ. dribbles / 90", None),
            ("xA / 90",             "xa90"),
            ("Def. actions / 90",   None),
        ],
        "card": [
            ("Drb/90", None),
            ("xA/90",  "xa90"),
            ("Def/90", None),
        ],
    },
}

# ── FotMob client ─────────────────────────────────────────────────────────────

# Counting stats that may be summed across a season's tournaments. Percentages
# are never summed — they are recomputed from their components.
ADDITIVE_STATS = frozenset({
    "minutes_played", "matches_uppercase", "goals", "assists",
    "expected_goals", "non_penalty_xg", "expected_assists",
    "shots", "ShotsOnTarget", "chances_created",
    "saves", "goals_conceded", "goals_prevented", "successful_passes",
    "recoveries", "touches", "aerials_won",
    "_pass_attempts", "_aerial_duels", "_rating_minutes",
})

# Percentages arrive per competition and cannot be summed; each is paired with
# the counter it is a share of, so the aggregate is rebuilt from the components.
SHARE_OF = {
    "successful_passes_accuracy": ("successful_passes", "_pass_attempts"),
    "aerials_won_percent":        ("aerials_won",       "_aerial_duels"),
}

# Counting stats whose per-90 rate can recover minutes when FotMob omits
# `minutes_played` from the card (goalkeeper cards do).
MINUTES_PROXIES = ("saves", "goals_conceded", "successful_passes")

_FETCH_JS = """async (path) => {
    const res = await fetch(path, { headers: { accept: 'application/json' } });
    return { status: res.status, body: await res.text() };
}"""


def api(page: Page, path: str):
    """Call a fotmob.com JSON endpoint from inside the loaded page."""
    res = page.evaluate(_FETCH_JS, path)
    if res["status"] != 200:
        raise RuntimeError(f"{path} → HTTP {res['status']}")
    body = res["body"].strip()
    return json.loads(body) if body else None


def _num(value) -> float | None:
    try:
        return float(str(value).replace(",", "").replace("%", ""))
    except (TypeError, ValueError):
        return None


def current_tournaments(player_data: dict) -> list[dict]:
    """Club tournaments the player has current-season stats for, league first."""
    seasons = player_data.get("statSeasons") or []
    current = next(
        (s for s in seasons if s.get("seasonName") == FOTMOB_SEASON), None
    )
    if not current:
        return []
    return [
        t for t in current.get("tournaments", [])
        if not NATIONAL_COMP_RE.search(t.get("name", ""))
    ]


def _entry_totals(stats: dict) -> dict:
    """Flatten one tournament's stat payload into a {key: number} dict."""
    if not stats:
        return {}
    groups = [stats.get("topStatCard") or {}]
    groups += (stats.get("statsSection") or {}).get("items", [])

    totals: dict = {}
    shares: dict = {}
    rating = None

    for group in groups:
        for item in group.get("items", []):
            key = item.get("localizedTitleId")
            value = _num(item.get("statValue"))
            if value is None:
                continue
            if key in ADDITIVE_STATS:
                # topStatCard repeats stats-section entries: assign, never add.
                totals[key] = value
            elif key in SHARE_OF:
                shares[key] = value
            elif key == "rating":
                rating = value

    for share_key, (counter, attempts_key) in SHARE_OF.items():
        share = shares.get(share_key)
        counted = totals.get(counter)
        if share and counted is not None:
            totals[attempts_key] = counted * 100.0 / share

    if "minutes_played" not in totals:
        for group in groups:
            for item in group.get("items", []):
                if item.get("localizedTitleId") not in MINUTES_PROXIES:
                    continue
                per90 = item.get("per90")
                value = _num(item.get("statValue"))
                if per90 and value:
                    totals["minutes_played"] = round(value * 90.0 / per90)
                    break
            if "minutes_played" in totals:
                break

    # A rating is an average, not a total: carry it as rating·minutes so several
    # competitions aggregate into a minutes-weighted season rating.
    if rating is not None and totals.get("minutes_played"):
        totals["_rating_minutes"] = rating * totals["minutes_played"]

    return totals


def fetch_fotmob(page: Page, cfg: dict) -> tuple[dict, str | None]:
    """Season totals across the player's club competitions, plus the league label."""
    fotmob_id = cfg["fotmob_id"]
    print(f"    FotMob: https://www.fotmob.com/players/{fotmob_id}", flush=True)

    player_data = api(page, f"/api/data/playerData?id={fotmob_id}")
    if not player_data:
        print("    ✗ no playerData payload", flush=True)
        return {}, None

    tournaments = current_tournaments(player_data)
    if not tournaments:
        print(f"    ⚠  no {CURRENT_SEASON} club competitions", flush=True)
        return {}, None

    league_label = tournaments[0]["name"]
    totals: dict = {}
    for tournament in tournaments:
        entry = _entry_totals(
            api(
                page,
                f"/api/data/playerStats?playerId={fotmob_id}"
                f"&seasonId={tournament['entryId']}",
            )
        )
        if not entry:
            continue
        for key, value in entry.items():
            totals[key] = totals.get(key, 0.0) + value
        print(
            f"      {tournament['name']}: "
            f"{int(entry.get('matches_uppercase', 0))} apps · "
            f"{int(entry.get('minutes_played', 0))} min",
            flush=True,
        )

    return totals, league_label


# ── Metrics ───────────────────────────────────────────────────────────────────

def _signed(value: float, places: int = 1) -> str:
    """A delta reads as a delta: always carries its sign."""
    return f"{'+' if value >= 0 else ''}{value:.{places}f}"


def metrics(totals: dict, position: str) -> dict:
    """Derive every metric a registry signal key or the metrics block names.

    Per-90 rates need a defensible denominator: below MIN_RATE_MINUTES only the
    appearance line is returned, so a cameo can't publish a 5.62 goals/90 signal.
    Percentages carry their sign so they read the same as the baseline season.
    """
    minutes = totals.get("minutes_played", 0.0)
    if minutes < 1:
        return {}

    goals   = totals.get("goals", 0.0)
    assists = totals.get("assists", 0.0)

    out: dict = {
        "_apps":    int(totals.get("matches_uppercase", 0)),
        "_mins":    int(minutes),
        "_goals":   int(goals),
        "_assists": int(assists),
        "assists_total": int(assists),
    }
    if minutes < MIN_RATE_MINUTES:
        return out

    n90   = minutes / 90.0
    xg    = totals.get("expected_goals", 0.0)
    npxg  = totals.get("non_penalty_xg", 0.0)
    shots = totals.get("shots", 0.0)
    sot   = totals.get("ShotsOnTarget", 0.0)

    if position != "gk":
        out["g90"]        = round(goals / n90, 2)
        out["a90"]        = round(assists / n90, 2)
        out["ga90"]       = round((goals + assists) / n90, 2)
        out["xg90"]       = round(xg / n90, 2)
        out["np_xg90"]    = round(npxg / n90, 2)
        out["npxg_total"] = round(npxg, 2)
        out["xa90"]       = round(totals.get("expected_assists", 0.0) / n90, 2)
        out["kp90"]       = round(totals.get("chances_created", 0.0) / n90, 2)
        out["shots90"]    = round(shots / n90, 2)
        out["sot90"]      = round(sot / n90, 2)
        if sot:
            out["sot_conv"] = f"{goals / sot * 100:.0f}%"
        out["goals_minus_xg"]   = _signed(goals - xg)
        out["goals_minus_npxg"] = _signed(goals - npxg, places=2)
    else:
        saves    = totals.get("saves", 0.0)
        conceded = totals.get("goals_conceded", 0.0)
        if saves + conceded:
            out["save_pct"] = f"{saves / (saves + conceded) * 100:.1f}%"
        prevented = totals.get("goals_prevented")
        if prevented is not None:
            out["psxg_minus_ga"] = _signed(prevented)

    out["recoveries90"] = round(totals.get("recoveries", 0.0) / n90, 2)
    out["touches90"]    = round(totals.get("touches", 0.0) / n90, 2)

    rating_minutes = totals.get("_rating_minutes", 0.0)
    if rating_minutes:
        out["rating"] = round(rating_minutes / minutes, 2)

    attempts = totals.get("_pass_attempts", 0.0)
    if attempts:
        out["pass_pct"] = f"{totals.get('successful_passes', 0.0) / attempts * 100:.1f}"

    duels = totals.get("_aerial_duels", 0.0)
    if duels:
        out["aerial_pct"] = f"{totals.get('aerials_won', 0.0) / duels * 100:.0f}%"

    return out


# ── Build player output ────────────────────────────────────────────────────────

def format_val(v) -> str:
    """Format a numeric or string value for display."""
    if v is None:
        return "—"
    if isinstance(v, float):
        return f"{v:.2f}"
    return str(v)


def build_player_entry(player_id: str, cfg: dict, page: Page) -> dict:
    """Fetch data and build the player's 2026-27 overlay entry."""
    print(f"\n  [{player_id}]", flush=True)

    try:
        totals, league_label = fetch_fotmob(page, cfg)
    except Exception as exc:
        print(f"    ✗ FotMob error: {exc}", flush=True)
        totals, league_label = {}, None

    stats = metrics(totals, cfg["position"])

    # Signal row: one entry per slot, in the order the report renders them. A
    # slot with no 2026-27 equivalent stays "—" rather than borrowing a number
    # from a metric its caption does not name.
    signals = []
    for _label, key in cfg["signals"]:
        val = stats.get(key) if key else None
        signals.append({
            "num":  format_val(val) if val is not None else "—",
            "pctl": f"{CURRENT_SEASON} · In progress" if val is None or not league_label
                    else f"{CURRENT_SEASON} · {league_label}",
        })

    # Build current season metrics block
    apps  = stats.get("_apps", 0)
    mins  = stats.get("_mins", 0)
    goals = stats.get("_goals", 0)
    assts = stats.get("_assists", 0)
    current_block = []

    if apps:
        line_parts = [f"{apps} apps", f"{mins} min"]
        if cfg["position"] != "gk":
            line_parts += [f"{goals}G", f"{assts}A"]
        current_block.append({
            "label": f"All comps {CURRENT_SEASON}",
            "val": " · ".join(line_parts),
        })

    for key, label in [
        ("xg90",           "xG / 90"),
        ("np_xg90",        "NP-xG / 90"),
        ("xa90",           "xA / 90"),
        ("g90",            "Goals / 90"),
        ("a90",            "Assists / 90"),
        ("ga90",           "G+A / 90"),
        ("sot90",          "Shots on target / 90"),
        ("kp90",           "Key passes / 90"),
        ("goals_minus_xg", "Goals vs xG"),
        ("save_pct",       "Save %"),
        ("psxg_minus_ga",  "PSxG − GA"),
        ("pass_pct",       "Pass completion %"),
    ]:
        v = stats.get(key)
        if v is not None:
            current_block.append({"label": label, "val": format_val(v)})

    # Hub card: same rule as the signal row, against the card's own captions.
    card = []
    for _label, key in cfg["card"]:
        v = stats.get(key) if key else None
        card.append(
            {"val": "—", "cls": ""} if v is None
            else {"val": format_val(v), "cls": "good" if _is_positive(v) else ""}
        )

    raw_mins = stats.get("_mins", 0)
    entry_mins = f"{raw_mins:,} min" if raw_mins and raw_mins > 0 else "—"

    return {
        "signals": signals,
        "current_block": current_block,
        "card": card,
        "mins": entry_mins,
    }


def _is_positive(v) -> bool:
    """Loose heuristic: non-negative numeric is 'good' for display."""
    try:
        return float(str(v).replace("+", "").replace("%", "")) > 0
    except (ValueError, TypeError):
        return False


def _has_data(entry: dict | None) -> bool:
    """An entry carries data once the fetch produced a current-season line."""
    return bool(entry and entry.get("current_block"))


# ── Database round-trip ───────────────────────────────────────────────────────
# data/football.db is the single source of truth; the shape of an overlay entry
# (and the SQL that reads/writes it) lives in scripts/pages/season.py so the
# scraper and the site build can never disagree about it.

def _db_entry(conn: sqlite3.Connection, player_id: str) -> dict | None:
    """The player's stored 2026-27 entry, in `build_player_entry()`'s shape."""
    return season.entry(conn, player_id)


def check_labels(conn: sqlite3.Connection, targets: list[str]) -> list[str]:
    """Registry captions must still be the ones the pages render.

    The stored caption is what the reader sees in both seasons; if it is edited
    in the DB and the registry is not re-pointed, this run would publish a
    number under a caption that no longer describes it.
    """
    problems = []
    for player_id in targets:
        cfg = PLAYERS[player_id]
        for slot, table, column in (
            ("signals", "signal_defs", "label"),
            ("card",    "card_stats",  "label"),
        ):
            stored = [
                row[column] for row in conn.execute(
                    f"SELECT {column} FROM {table} WHERE player_id = ?"
                    + (" AND season = ?" if table == "card_stats" else "")
                    + " ORDER BY idx",
                    (player_id, season.SEASON) if table == "card_stats" else (player_id,),
                )
            ]
            expected = [label for label, _key in cfg[slot]]
            if stored != expected:
                problems.append(
                    f"{player_id}.{slot}: registry {expected} ≠ stored {stored}"
                )
    return problems


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    # Optional: only update specific players
    targets = sys.argv[1:] if len(sys.argv) > 1 else list(PLAYERS.keys())
    unknown = [t for t in targets if t not in PLAYERS]
    if unknown:
        print(f"Unknown player(s): {unknown}. Valid IDs: {list(PLAYERS.keys())}")
        sys.exit(1)

    print(f"Updating {len(targets)} player(s) for {CURRENT_SEASON} …\n")

    if not DB_PATH.exists():
        print(f"{DB_PATH} not found — run: python scripts/init_db.py")
        sys.exit(1)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    changed = False
    empty: list[str] = []

    drift = check_labels(conn, targets)
    if drift:
        conn.close()
        print("Registry no longer matches the captions in the database:")
        for problem in drift:
            print(f"  {problem}")
        sys.exit(1)

    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            ctx = browser.new_context(user_agent=BROWSER_UA, locale="en-US")
            page = ctx.new_page()
            page.goto(FOTMOB_HOME, wait_until="domcontentloaded", timeout=45_000)

            for player_id in targets:
                cfg = PLAYERS[player_id]
                entry = build_player_entry(player_id, cfg, page)
                stored = _db_entry(conn, player_id)

                # A failed fetch must never blank a populated row: an outage at
                # the source would otherwise silently erase real stats.
                if not _has_data(entry):
                    empty.append(player_id)
                    if _has_data(stored):
                        print(f"  ! {player_id} no data — keeping stored values")
                        continue

                if stored != entry:
                    season.upsert_entry(conn, player_id, entry)
                    changed = True
                    print(f"  ✓ {player_id} updated")
                else:
                    print(f"  = {player_id} unchanged")

            browser.close()

        if changed:
            stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            matchweek = season.bump(conn, stamp)
            conn.commit()
            print(f"\nStored in {DB_PATH} · matchweek {matchweek} · {stamp}")
        else:
            print("\nNo changes — database unchanged")
    finally:
        conn.close()

    if changed:
        # build.py owns artifact emission: every page plus data/season-2627.{json,js}
        print("\nRebuilding site from the database …")
        build.main()

    if len(empty) == len(targets):
        print(
            f"\n✗ No data for any of the {len(targets)} player(s) — "
            "the source is unreachable or its payload shape changed.",
            file=sys.stderr,
        )
        sys.exit(1)
    if empty:
        print(f"\nNo current-season club data: {', '.join(empty)}")


if __name__ == "__main__":
    main()
