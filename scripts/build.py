#!/usr/bin/env python3
"""Render every page of the site from data/football.db.

    python scripts/build.py                # all 19 pages + data/season-2627.*
    python scripts/build.py --only reports # one archetype (iteration aid)

The database is the single source of truth; every *.html at the repo root and
data/season-2627.{json,js} are generated artifacts. Build-time dependency:
Jinja2. The deployed site itself stays static with zero runtime dependencies.
"""

from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = Path(os.environ.get("FOOTBALL_DB") or ROOT / "data" / "football.db")
TEMPLATE_DIR = ROOT / "templates"

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pages  # noqa: E402


def environment() -> Environment:
    # autoescape MUST stay off: stored fields contain trusted markup
    # (<strong>, <br>, flag emoji) and escaping would break byte-fidelity.
    return Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)),
        autoescape=False,
        undefined=StrictUndefined,
        keep_trailing_newline=True,
    )


def main(only: list[str] | None = None) -> None:
    if not DB_PATH.exists():
        raise SystemExit(
            f"{DB_PATH} not found — run: python scripts/init_db.py"
        )
    env = environment()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        for mod in pages.modules(only):
            mod.build(conn, env)
    finally:
        conn.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--only", help="comma-separated archetype module names")
    args = ap.parse_args()
    main(args.only.split(",") if args.only else None)
