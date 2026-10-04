"""Onboarding discovery, read only: the county's associations (asspy's directory) and the documents the locator
saved for one. Neither tool reads the county: a fresh locate is ``jason onboard --locate`` run by a person, or a job
the console queues for ``jason worker``."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def _root(data_dir: Path | None) -> Path:
    from jason.config import Settings

    return Path(data_dir) if data_dir is not None else Settings.load().payhoa_catalog.parent


def association_directory(county: str = "", query: str = "", limit: int = 25) -> dict[str, Any]:
    """The owners', commercial, and maintenance associations a county recorder's public index shows, from asspy's
    surveyed directory on disk: ``query`` narrows by words (ranked), each row with its kind, standing (confirmed: it
    records assessment liens or its declaration), years recorded, spellings, evidence counts, and how many governing
    instruments name it or were linked to it. ``county`` defaults to the active profile's region. A county not
    surveyed gives the asspy command that surveys it. A row is a lead, not a pin. Reads disk only."""
    from jason.tasks import document_locator, onboarding_lookup as lookup

    if not county.strip():
        try:
            county = document_locator.active()[2]
        except Exception:  # noqa: BLE001 - no active profile: the county must be given
            county = ""
    try:
        return lookup.directory_search(county, query, limit)
    except Exception as exc:  # a reader that fails is an answer, not a traceback
        return {"error": f"{type(exc).__name__}: {exc}"}


def documents_located(county: str = "", name: str = "", data_dir: Path | None = None) -> dict[str, Any]:
    """The association's recorded documents as ``jason onboard --locate`` last saved them (the active profile's, or
    ``name`` in ``county``): each checklist item located (declaration, amendments, annexations, condominium plans,
    maps, common-area deeds, ...) with its document numbers, dates, filings, and how each was tied (names the
    association, recorded beside its documents, or the builder's filing, which may be another community's), the core
    items not located with the ask, and the notes. When nothing was saved: ``missing`` with the command. A located
    instrument is a lead, not a pin: say so, and read the recorded copy before pinning. Reads disk only."""
    from jason.tasks import document_locator

    try:
        try:
            own = document_locator.active()
        except Exception:  # noqa: BLE001 - no active profile: another association can still be read by name
            if not name.strip():
                raise
            own = ("", "", "")
        return document_locator.view(_root(data_dir), county=county, name=name, own=own)
    except Exception as exc:  # a reader that fails is an answer, not a traceback
        return {"error": f"{type(exc).__name__}: {exc}"}


TOOLS = (association_directory, documents_located)
