"""Placer's index cache: asspy's ``PlacerIndex`` over jason's annotated ``IndexCache``.

The cache is asspy's per-county file (``County("placer").db_path``, under
``ASSPY_HOME``), so Placer instruments sit beside nothing of Sacramento's.
jason's ``IndexCache`` subclass writes the walk's notes (a restatement, an
other community's instrument) on each row as it is stored. Every walk,
reading, and report in this package reads the cache through ``PlacerIndex``
and searches only for what the cache has not seen.
"""

from __future__ import annotations

from pathlib import Path

from asspy.county import County
from asspy.placer.index import PlacerIndex, Searched
from jason.community.index_cache import IndexCache
from jason.community.placer.recorder import PlacerCountyRecorder

__all__ = ("PlacerIndex", "Searched", "open_cache", "placer_index")


def open_cache(path: str | Path | None = None) -> IndexCache:
    """Placer's index cache: ``path``, else asspy's ``counties/placer/index.db``."""
    if path is None:
        from jason.asspy_home import apply

        apply()                                   # ASSPY_HOME from the environment or jason's .env, before asspy reads it
    return IndexCache(Path(path) if path is not None else County("placer").db_path, county="placer")


def placer_index(
    cache: IndexCache | None = None,
    recorder: PlacerCountyRecorder | None = None,
    *,
    session=None,
    fetch=None,
    pause: float = 0.0,
    note=None,
) -> PlacerIndex:
    """One held Placer session over the cache; ``pause`` seconds between live searches."""
    return PlacerIndex(
        cache if cache is not None else open_cache(),
        recorder or PlacerCountyRecorder(),
        session=session,
        fetch=fetch,
        pause=pause,
        note=note,
    )
