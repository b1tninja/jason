"""Discovery for onboarding: the county's associations and the documents located for one, read from disk.

``associations(args)`` searches asspy's association directory for a county (``?county=``, else the active profile's
region; ``?q=`` words, ``?limit=``), the directory's summary beside it; a county not yet surveyed gives the asspy
command that surveys it. ``documents_located(args)`` reads the locator's saved result
(``data/onboarding/<profile>-documents-located.json``) for the active profile, or ``?county=&name=`` for another
association; when none was saved it gives the command, and a queued or running locate job is shown with it. Each
located instrument carries every party: the businesses and the association in ``parties``, and the private persons in
``people`` (name and index side, R or E). Owners' names are P1 (``docs/console/security-and-privacy.md``): shown to
the people who work with them, kept in jason's private data, never committed.

Nothing here reads the county: a fresh locate is a person's action, ``write("locate", {county, name, by})``, which
queues ``jason onboard --locate`` for ``jason worker`` (the county lane) and returns the job. A row, a located
instrument, or a link is a lead, not a pin.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

Args = dict[str, str]


def _root() -> Path:
    from jason.config import Settings

    return Settings.load().payhoa_catalog.parent


def _active() -> tuple[str, str, str]:
    from jason.tasks import document_locator

    return document_locator.active()


def associations(args: Args) -> dict[str, Any]:
    """GET /api/associations?county=&q=&limit=: the county's associations from asspy's directory, searched."""
    from jason.tasks import onboarding_lookup as lookup

    county = (args.get("county") or "").strip()
    if not county:
        try:
            county = _active()[2]
        except Exception:  # noqa: BLE001 - no active profile: the county must be given
            county = ""
    try:
        limit = int(args.get("limit") or lookup.SEARCH_RESULTS)
    except ValueError as exc:
        raise ValueError("limit is a number") from exc
    return lookup.directory_search(county, args.get("q", ""), limit)


def documents_located(args: Args) -> dict[str, Any]:
    """GET /api/documents-located (the active profile) or ?county=&name=: the saved locate, or the command that
    fills it, with the locate job while one is queued or running."""
    from jason.tasks import document_locator

    name = (args.get("name") or "").strip()
    try:
        own = _active()
    except Exception as exc:  # noqa: BLE001 - no active profile: another association can still be read by name
        if not name:
            raise ValueError(f"no active profile ({type(exc).__name__}); give county and name") from exc
        own = ("", "", "")
    return document_locator.view(_root(), county=args.get("county", ""), name=name, own=own)


def write(key: str, body: dict[str, Any]) -> dict[str, Any]:
    """POST /api/write/documents-located/locate {county, name, by}: queue a locate as a job; never run it here."""
    from jason.tasks import document_locator

    if key != "locate":
        raise KeyError(key)
    return document_locator.enqueue(_root(), county=str(body.get("county", "") or ""),
                                    name=str(body.get("name", "") or ""), by=str(body.get("by", "") or ""),
                                    own=_active())
