#!/usr/bin/env python3
"""
update-stats.py — Football Intelligence · 2026-27 Season Data Fetcher

Fetches current-season stats from FBref and Understat for all tracked players,
upserts them into data/football.db, then rebuilds every generated artifact via
scripts/build.py. Run weekly via GitHub Actions after matchday.

Sources:
  - FBref: goals, assists, apps, minutes, progressive carries/passes (rendered HTML via Playwright)
  - Understat: xG, xA, key passes per 90 (XHR response intercepted via Playwright)

Requires: pip install playwright beautifulsoup4 lxml jinja2 && playwright install chromium
"""

import re
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright, BrowserContext

# ── Constants ─────────────────────────────────────────────────────────────────

CURRENT_SEASON = "2026-27"
FBREF_SEASON   = "2026-2027"   # FBref URL format
UNDERSTAT_YEAR = "2026"        # Understat season key

sys.path.insert(0, str(Path(__file__).resolve().parent))

import build  # noqa: E402
from pages import season  # noqa: E402

# Same path build.py reads (honours the FOOTBALL_DB override).
DB_PATH = build.DB_PATH

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; FootballIntelligence/1.0; "
        "+https://github.com/football-intelligence/scouting)"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

# Polite delay between requests (seconds)
REQUEST_DELAY = 2.5

# ── Player registry ───────────────────────────────────────────────────────────
# Each entry: player-id → config dict
#
# fbref_id:      FBref player page ID (in URL: /players/{id}/)
# understat_id:  Understat player ID (in URL: /player/{id})
# position:      "fw" | "cb" | "fb" | "gk" | "cm" etc.  (drives which metrics to pull)
# signal_labels: list of 3 label strings shown in the .signals row (must match HTML)
# signal_keys:   list of 3 stat keys this script will populate (see _extract_* funcs)
# league:        fbref league short-name for stat table lookup
#
# FBref IDs: visit player page and copy from URL.
# Understat IDs: only covers PL, La Liga, Bundesliga, Serie A, Ligue 1.
#   For other leagues (JPL, HNL, Primeira Liga) understat_id = None.

PLAYERS = {
    "deniz-undav": {
        "name": "Deniz Undav",
        "fbref_id":     "dd549382",
        "understat_id": 10804,        # Bundesliga — covered
        "position": "fw",
        "signal_labels": ["NP-xG / 90", "Goals − xG", "Shots on target / 90"],
        "signal_keys":   ["np_xg90",   "goals_minus_xg", "sot90"],
        "league": "Bundesliga",
    },
    "nicolo-tresoldi": {
        "name": "Nicolò Tresoldi",
        "fbref_id":     "3860ab13",
        "understat_id": None,         # JPL — not covered by Understat
        "position": "fw",
        "signal_labels": ["NP-xG / 90", "Goals − xG", "Shots on target / 90"],
        "signal_keys":   ["np_xg90",   "goals_minus_xg", "sot90"],
        "league": "Belgian Pro League",
    },
    "lautaro-martinez": {
        "name": "Lautaro Martínez",
        "fbref_id":     "f7036e1c",
        "understat_id": 7006,         # Serie A — covered
        "position": "fw",
        "signal_labels": ["G/90", "xG / 90", "Goals − xG"],
        "signal_keys":   ["g90", "xg90", "goals_minus_xg"],
        "league": "Serie A",
    },
    "orri-oskarsson": {
        "name": "Orri Steinn Óskarsson",
        "fbref_id":     "d0b8e745",
        "understat_id": 13048,        # La Liga — covered
        "position": "fw",
        "signal_labels": ["G/90", "Shots on target / 90", "Goals − xG"],
        "signal_keys":   ["g90", "sot90", "goals_minus_xg"],
        "league": "La Liga",
    },
    "julian-alvarez": {
        "name": "Julián Álvarez",
        "fbref_id":     "15ab5a2b",
        "understat_id": 10846,        # La Liga — covered
        "position": "fw",
        "signal_labels": ["xG / 90", "G+A / 90", "Key passes / 90"],
        "signal_keys":   ["xg90", "ga90", "kp90"],
        "league": "La Liga",
    },
    "serhou-guirassy": {
        "name": "Serhou Guirassy",
        "fbref_id":     "923f4dda",
        "understat_id": 3738,         # Bundesliga — covered
        "position": "fw",
        "signal_labels": ["xG / 90", "G+A / 90", "Shot on target %"],
        "signal_keys":   ["xg90", "ga90", "sot_pct"],
        "league": "Bundesliga",
    },
    "dominik-livakovic": {
        "name": "Dominik Livaković",
        "fbref_id":     "58f077c0",
        "understat_id": None,         # HNL — not covered by Understat
        "position": "gk",
        "signal_labels": ["Save %", "PSxG − GA", "Pass completion %"],
        "signal_keys":   ["save_pct", "psxg_minus_ga", "pass_pct"],
        "league": "HNL",
    },
    "chupe": {
        "name": "Carlos Ruiz Rubio",
        "fbref_id":     "4eb8be46",
        "understat_id": None,         # La Liga 2 — not covered by Understat
        "position": "fw",
        "signal_labels": ["G/90", "xG / 90", "Shot on target %"],
        "signal_keys":   ["g90", "xg90", "sot_pct"],
        "league": "La Liga 2",
    },
    "george-salinas": {
        "name": "Jorge Salinas Viadero",
        "fbref_id":     "a44995b7",
        "understat_id": None,         # La Liga 2 — not covered by Understat
        "position": "fb",
        "signal_labels": ["Assists / 90", "Prog. carries / 90", "G+A / 90"],
        "signal_keys":   ["a90", "prog_carries90", "ga90"],
        "league": "La Liga 2",
    },
    "castello-lukeba": {
        "name": "Castello Lukeba",
        "fbref_id":     "5b9512c5",
        "understat_id": 9511,         # Bundesliga — covered
        "position": "cb",
        "signal_labels": ["Prog. passes / 90", "Prog. carries / 90", "xA / 90"],
        "signal_keys":   ["prog_passes90", "prog_carries90", "xa90"],
        "league": "Bundesliga",
    },
    "goncalo-inacio": {
        "name": "Gonçalo Inácio",
        "fbref_id":     "33651873",
        "understat_id": None,         # Primeira Liga — not covered by Understat
        "position": "cb",
        "signal_labels": ["Prog. passes / 90", "Prog. carries / 90", "xA / 90"],
        "signal_keys":   ["prog_passes90", "prog_carries90", "xa90"],
        "league": "Primeira Liga",
    },
    "gabriel-jesus": {
        "name": "Gabriel Jesus",
        "fbref_id":     "b66315ae",
        "understat_id": 5543,         # La Liga (Barcelona) — covered
        "position": "fw",
        "signal_labels": ["xG / 90", "Prog. carries / 90", "G+A / 90"],
        "signal_keys":   ["xg90", "prog_carries90", "ga90"],
        "league": "La Liga",
    },
}

# ── Playwright scrapers ───────────────────────────────────────────────────────

BROWSER_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/127.0.0.0 Safari/537.36"
)


def _fbref_player_url(fbref_id: str) -> str:
    return f"https://fbref.com/en/players/{fbref_id}/all_comps/stats/"


def fetch_fbref(fbref_id: str, league: str, ctx: BrowserContext) -> dict:
    """
    Scrape current-season (2026-27) stats from a player's FBref all-comps page
    using a real Playwright browser page (bypasses IP/UA blocking).
    """
    url = _fbref_player_url(fbref_id)
    print(f"    FBref: {url}", flush=True)

    page = ctx.new_page()
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=30_000)
        try:
            page.wait_for_selector("table[id*='stats_standard']", timeout=15_000)
        except Exception:
            print("    ⚠  stats_standard table not rendered within 15s", flush=True)
        time.sleep(REQUEST_DELAY)
        html = page.content()
    except Exception as exc:
        print(f"    ✗ FBref navigation error: {exc}", flush=True)
        return {}
    finally:
        page.close()

    soup = BeautifulSoup(html, "lxml")
    stats: dict = {}

    table = soup.find("table", {"id": re.compile(r"stats_standard")})
    if not table:
        print("    ⚠  stats_standard table not found", flush=True)
        return stats

    for row in table.select("tbody tr"):
        season_cell = row.find("th", {"data-stat": "year_id"})
        if not season_cell:
            continue
        season_link = season_cell.find("a")
        season_text = season_link.text.strip() if season_link else season_cell.text.strip()
        if season_text != FBREF_SEASON:
            continue

        def cell(stat: str) -> str:
            td = row.find("td", {"data-stat": stat})
            return td.text.strip() if td else ""

        def num(stat: str) -> float | None:
            v = cell(stat)
            if not v or v in ("—", ""):
                return None
            try:
                return float(v.replace(",", ""))
            except ValueError:
                return None

        mp      = num("games")
        mins    = num("minutes")
        mins_90 = (mins / 90.0) if mins else None
        goals   = num("goals")
        assists = num("assists")
        xg      = num("xg")
        xga     = num("xa")
        shots   = num("shots")
        sot     = num("shots_on_target")
        prog_c  = num("progressive_carries")
        prog_p  = num("progressive_passes")

        if goals is not None and mins_90:
            stats["g90"] = round(goals / mins_90, 2)
        if assists is not None and mins_90:
            stats["a90"] = round(assists / mins_90, 2)
        if goals is not None and assists is not None and mins_90:
            stats["ga90"] = round((goals + assists) / mins_90, 2)
        if xg is not None and mins_90:
            stats["xg90"] = round(xg / mins_90, 2)
        if xga is not None and mins_90:
            stats["xa90"] = round(xga / mins_90, 2)
        if prog_c is not None and mins_90:
            stats["prog_carries90"] = round(prog_c / mins_90, 2)
        if prog_p is not None and mins_90:
            stats["prog_passes90"] = round(prog_p / mins_90, 2)
        if shots and sot is not None:
            stats["sot_pct"] = round((sot / shots) * 100, 1)
        if goals is not None and xg is not None:
            diff = goals - xg
            stats["goals_minus_xg"] = f"{'+' if diff >= 0 else ''}{diff:.1f}"
            if mins_90:
                stats["goals_minus_xg90"] = round((goals - xg) / mins_90, 2)
                stats["np_xg90"] = stats.get("xg90")  # simplified

        stats["_apps"]    = int(mp) if mp else 0
        stats["_mins"]    = int(mins) if mins else 0
        stats["_goals"]   = int(goals) if goals else 0
        stats["_assists"] = int(assists) if assists else 0
        break

    return stats


def fetch_understat(understat_id: str, ctx: BrowserContext) -> dict:
    """
    Fetch xG/xA/KP data from Understat by intercepting the /getPlayerData/{id}
    XHR response that fires during page load. Aggregates match-level data for
    the current season (UNDERSTAT_YEAR).
    """
    url = f"https://understat.com/player/{understat_id}"
    data_prefix = f"https://understat.com/getPlayerData/{understat_id}"
    print(f"    Understat: {url}", flush=True)

    captured: list[dict] = []

    page = ctx.new_page()
    try:
        def on_response(response):
            if data_prefix in response.url and response.status == 200:
                try:
                    captured.append(response.json())
                except Exception:
                    pass

        page.on("response", on_response)
        page.goto(url, wait_until="domcontentloaded", timeout=30_000)
        page.wait_for_timeout(2_000)   # allow XHR to complete
    except Exception as exc:
        print(f"    ✗ Understat navigation error: {exc}", flush=True)
        return {}
    finally:
        page.close()

    if not captured:
        print("    ⚠  No getPlayerData XHR captured", flush=True)
        return {}

    matches = captured[0].get("matches", [])
    season_matches = [m for m in matches if m.get("season") == UNDERSTAT_YEAR]

    if not season_matches:
        print(f"    ⚠  No {CURRENT_SEASON} matches (total: {len(matches)})", flush=True)
        return {}

    def fsum(key: str) -> float:
        return sum(float(m.get(key) or 0) for m in season_matches)

    total_mins    = fsum("time")
    total_goals   = fsum("goals")
    total_xg      = fsum("xG")
    total_npxg    = fsum("npxG")
    total_assists  = fsum("assists")
    total_xa      = fsum("xA")
    total_kp      = fsum("key_passes")

    if total_mins < 45:
        print(f"    ⚠  Only {int(total_mins)} mins played — skipping", flush=True)
        return {}

    n90    = total_mins / 90.0
    result: dict = {}

    result["g90"]        = round(total_goals / n90, 2)
    result["xg90"]       = round(total_xg / n90, 2)
    result["np_xg90"]    = round(total_npxg / n90, 2)
    result["a90"]        = round(total_assists / n90, 2)
    result["xa90"]       = round(total_xa / n90, 2)
    result["kp90"]       = round(total_kp / n90, 2)
    result["ga90"]       = round((total_goals + total_assists) / n90, 2)

    diff = total_goals - total_xg
    result["goals_minus_xg"] = f"{'+' if diff >= 0 else ''}{diff:.1f}"

    result["_apps"]    = len(season_matches)
    result["_mins"]    = int(total_mins)
    result["_goals"]   = int(total_goals)
    result["_assists"] = int(total_assists)

    return result


# ── Build player output ────────────────────────────────────────────────────────

def format_val(v) -> str:
    """Format a numeric or string value for display."""
    if v is None:
        return "—"
    if isinstance(v, float):
        return f"{v:.2f}"
    return str(v)


def build_player_entry(player_id: str, cfg: dict, ctx: BrowserContext) -> dict:
    """Fetch data and build the player's 2026-27 overlay entry."""
    print(f"\n  [{player_id}]", flush=True)

    fbref_stats: dict = {}
    understat_stats: dict = {}

    if cfg.get("fbref_id"):
        try:
            fbref_stats = fetch_fbref(cfg["fbref_id"], cfg["league"], ctx)
        except Exception as exc:
            print(f"    ✗ FBref error: {exc}", flush=True)

    if cfg.get("understat_id"):
        try:
            understat_stats = fetch_understat(cfg["understat_id"], ctx)
        except Exception as exc:
            print(f"    ✗ Understat error: {exc}", flush=True)

    # Merge: Understat xG/xA preferred over FBref (more precise)
    merged = {**fbref_stats, **understat_stats}

    # Build signals (3 entries matching HTML signal row)
    signals = []
    for key in cfg["signal_keys"]:
        val = merged.get(key)
        num_str = format_val(val) if val is not None else "—"
        signals.append({
            "num":  num_str,
            "bar":  0,   # percentile bars need cohort data — set manually or extend script
            "pctl": f"{CURRENT_SEASON} · In progress" if val is None else f"{CURRENT_SEASON} · {cfg['league']}",
        })

    # Build current season metrics block
    apps  = merged.get("_apps", 0)
    mins  = merged.get("_mins", 0)
    goals = merged.get("_goals", 0)
    assts = merged.get("_assists", 0)
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
        ("xa90",           "xA / 90"),
        ("g90",            "Goals / 90"),
        ("a90",            "Assists / 90"),
        ("ga90",           "G+A / 90"),
        ("prog_carries90", "Prog. carries / 90"),
        ("prog_passes90",  "Prog. passes / 90"),
        ("goals_minus_xg", "Goals vs xG"),
        ("save_pct",       "Save %"),
    ]:
        v = merged.get(key)
        if v is not None:
            current_block.append({"label": label, "val": format_val(v)})

    # Build card stats (3 entries matching index.html card)
    # Default: all "—" — the signal_keys guide which go to card
    card = [{"val": "—", "cls": ""} for _ in range(3)]
    for i, key in enumerate(cfg["signal_keys"][:3]):
        v = merged.get(key)
        if v is not None:
            card[i] = {"val": format_val(v), "cls": "good" if _is_positive(v) else ""}

    raw_mins = merged.get("_mins", 0)
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
        return float(str(v).replace("+", "")) > 0
    except (ValueError, TypeError):
        return False


# ── Database round-trip ───────────────────────────────────────────────────────
# data/football.db is the single source of truth; the shape of an overlay entry
# (and the SQL that reads/writes it) lives in scripts/pages/season.py so the
# scraper and the site build can never disagree about it.

def _db_entry(conn: sqlite3.Connection, player_id: str) -> dict | None:
    """The player's stored 2026-27 entry, in `build_player_entry()`'s shape."""
    return season.entry(conn, player_id)


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
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            ctx = browser.new_context(user_agent=BROWSER_UA)

            for player_id in targets:
                cfg = PLAYERS[player_id]
                entry = build_player_entry(player_id, cfg, ctx)
                if _db_entry(conn, player_id) != entry:
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


if __name__ == "__main__":
    main()
