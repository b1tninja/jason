"""jason fetch-bills lists the bills a parse added from a portal's folder, not a PayHOA attachment's copy."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from jason.cli import _new_bills, _store_sources


def test_only_portal_bills_the_parse_added_are_new(tmp_path: Path) -> None:
    store = tmp_path / "utilities.db"
    with sqlite3.connect(store) as db:
        db.execute("create table bills (source text, provider text, account text, bill_date text, total_cents int)")
        db.execute("insert into bills values ('smud/bills/3547597/2026-08-26.pdf', 'smud', '3547597', '2026-08-26', 30000)")
    before = _store_sources(store)
    with sqlite3.connect(store) as db:
        db.executemany("insert into bills values (?, ?, ?, ?, ?)", [
            ("smud/bills/3547597/2026-09-25.pdf", "smud", "3547597", "2026-09-25", 34898),
            ("jason/data/payhoa/attachments/1/DistributionView2.pdf", "smud", "3547597", "2026-09-25", 34898)])
    assert _new_bills(store, before) == [("smud", "3547597", "2026-09-25", 34898)]
    assert _store_sources(tmp_path / "missing.db") == set()
