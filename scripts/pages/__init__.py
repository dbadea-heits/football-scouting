"""Page archetype registry.

Every module in this package owns one archetype end-to-end:

    ORDER            int, seed/build execution order (low first)
    seed(conn)       parse the current committed artifacts into the DB
    build(conn, env) render the archetype's page(s) from the DB

`init_db.py` creates the schema and calls `seed()`; `build.py` calls `build()`.
Modules are discovered, not registered, so archetypes stay independent.
"""

from __future__ import annotations

import importlib
import pkgutil
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parent.parent.parent


def modules(only: list[str] | None = None) -> list[ModuleType]:
    """Import archetype modules, ordered by ORDER.

    `only` restricts discovery to the named modules, which lets one archetype
    be seeded/built in isolation while the others are still being written.
    """
    names = sorted(info.name for info in pkgutil.iter_modules(__path__))
    if only is not None:
        unknown = [n for n in only if n not in names]
        if unknown:
            raise SystemExit(
                f"unknown archetype(s): {', '.join(unknown)}; have: {', '.join(names)}"
            )
        names = [n for n in names if n in only]
    found = []
    for name in names:
        mod = importlib.import_module(f"{__name__}.{name}")
        missing = [a for a in ("ORDER", "seed", "build") if not hasattr(mod, a)]
        if missing:
            raise AttributeError(f"pages.{name} is missing {', '.join(missing)}")
        found.append(mod)
    found.sort(key=lambda m: m.ORDER)
    return found


def read_text(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def write_page(rel: str, text: str) -> None:
    """Write a generated artifact, reporting whether its bytes changed."""
    path = ROOT / rel
    old = path.read_bytes() if path.exists() else None
    new = text.encode("utf-8")
    path.write_bytes(new)
    mark = "=" if old == new else ("+" if old is None else "~")
    print(f"  {mark} {rel}")
