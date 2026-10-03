"""Run the onboarding checklist (``jason.community.onboarding``) against the active profile and the data on disk.

``load_context`` reads, read-only: the classified library (``data/library``), the Civil Code 5200 records inventory,
file and row counts under the data folder, the private facts (``data/spec``), and the settings. Nothing is written to
PayHOA, Google, or the mail. ``write_report`` keeps the report under ``data/onboarding/``, which is never checked in:
its evidence names the association's stores and counts.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import date
from pathlib import Path
from typing import Any

from jason.community.onboarding import Context, ItemResult, check, report_dicts, report_markdown

FOLDER = "onboarding"
_FILE_CAP = 100_000


def counter(root: Path):
    """``count(path, table)``: rows in a database table, files in a folder, entries in a JSON file, 1 for a non-empty
    file, 0 for anything missing or unreadable."""

    def count(path: str, table: str = "") -> int:
        target = root / path
        try:
            if table:
                if not target.is_file():
                    return 0
                conn = sqlite3.connect(f"file:{target.as_posix()}?mode=ro", uri=True)
                try:
                    return int(conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0])
                finally:
                    conn.close()
            if target.is_dir():
                found = 0
                for item in target.rglob("*"):
                    if item.is_file():
                        found += 1
                        if found >= _FILE_CAP:
                            break
                return found
            if not target.is_file() or target.stat().st_size == 0:
                return 0
            if target.suffix.lower() == ".json":
                value = json.loads(target.read_text(encoding="utf-8"))
                if isinstance(value, dict):
                    rows = next((v for v in value.values() if isinstance(v, list)), None)
                    return len(rows) if rows is not None else len(value)
                return len(value) if isinstance(value, list) else 1
            return 1
        except (OSError, ValueError, sqlite3.Error):
            return 0

    return count


def load_context(community: Any, data_dir: Path, *, settings: Any = None, asks: tuple = (),
                 profile: str = "") -> Context:
    """The checks' context. The records inventory is read with the county index's governing instruments where the index
    cache is on disk, so ``Verified`` can match each recorded copy; ``asks`` are the intake questions ``Settled``
    reads; ``profile`` names the private facts file ``Fact`` reads (the active profile by default)."""
    from jason.community.private import facts

    library: tuple[dict[str, Any], ...] = ()
    try:
        from jason.tasks.library import distinct, load as load_library

        library = tuple(distinct(load_library(data_dir)))
    except Exception:  # noqa: BLE001 - no library yet is a miss for the items that need it
        library = ()
    holdings: tuple = ()
    try:
        from jason.tasks.association_pages import build_inventory

        governing = None
        if (Path(data_dir) / "index-cache.db").is_file():
            try:
                from jason.tasks.property_history import load_association_record

                governing = load_association_record(community, Path(data_dir)).governing
            except Exception:  # noqa: BLE001 - an index that cannot be read leaves the copies unmatched
                governing = None
        holdings = tuple(build_inventory(community, data_dir, governing=governing))
    except Exception:  # noqa: BLE001
        holdings = ()
    if not profile:
        try:
            from jason.community.profile import profile_name

            profile = profile_name()
        except Exception:  # noqa: BLE001
            profile = ""
    return Context(community=community, library=library, holdings=holdings, count=counter(data_dir),
                   private=lambda name: facts(name), settings=settings, profile=profile, asks=tuple(asks))


def run(community: Any, data_dir: Path, *, settings: Any = None) -> tuple[ItemResult, ...]:
    from jason.community import intake

    return check(load_context(community, data_dir, settings=settings, asks=tuple(intake.load(data_dir))))


def write_report(results: tuple[ItemResult, ...], data_dir: Path, *, title: str, today: date | None = None) -> Path:
    """``data/onboarding/checklist-<day>.md`` and its ``.json`` beside it; returns the Markdown path."""
    day = (today or date.today()).isoformat()
    folder = data_dir / FOLDER
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"checklist-{day}.md"
    path.write_text(report_markdown(results, title=title), encoding="utf-8")
    path.with_suffix(".json").write_text(json.dumps(report_dicts(results), indent=1), encoding="utf-8")
    return path
