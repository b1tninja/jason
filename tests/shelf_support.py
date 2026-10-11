"""Guards for tests that read the real authorities shelf (``data/authorities``) and skip where it is not here.

A folder named for a code is not a shelf. A reader's miss can bring one page down on demand (jason.tasks.statute_fetch), which
leaves ``authorities/CIV`` holding that page, its manifest, and nothing curated. A test that cites many sections reads the
shelf as complete only when the manifest lists the curated pages (``jason export-authorities``); otherwise it skips, with
the reason below, rather than failing on a section the shelf never held.
"""

from __future__ import annotations

from pathlib import Path

import pytest

NOT_CURATED = "the authorities shelf here is partial or absent (no curated pages; run jason export-authorities)"


def gap(root: Path | str) -> str:
    """Why ``root`` (a data folder) holds no complete shelf, or ``""`` when its manifest lists curated pages."""
    from jason.tasks.export_authorities import authority_pages

    return "" if authority_pages(Path(root)) else NOT_CURATED


def needs_shelf(root: Path | str):
    """``@needs_shelf(DATA)``: skip the test unless the folder holds a curated shelf."""
    return pytest.mark.skipif(bool(gap(root)), reason=NOT_CURATED)


def require(root: Path | str) -> None:
    """Skip the running test unless the folder holds a curated shelf."""
    if reason := gap(root):
        pytest.skip(reason)


def resolver(root: Path | str):
    """``general.shelf_resolver`` for a definition's law clocks, except that a partial shelf cannot tell (``None``) instead of
    answering that a section is missing."""
    from jason.workflows import definitions_general as general

    return None if gap(root) else general.shelf_resolver(root)
