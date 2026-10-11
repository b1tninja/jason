"""Who may read each source the web app serves, in one table.

``jason.web.app.source`` calls a loader and nothing else, so a read is gated only if its loader is. A loader that gates
itself (``life_safety``, ``request_views``, ``unit_records``, ``status``) says so in its own module; every other loader
in ``jason.web.sources.default_loaders()`` is wrapped here by ``GATES``. ``tests/test_loaders_are_gated.py`` calls every
loader as four different viewers and compares what it saw to ``tests/fixtures/loader_gates.json``, so a loader that is
in neither place (a new one) fails until someone classifies it.

The gates, by the data levels of ``jason.web.access``:

- ``p2``: the offices that open contact details and members' submissions (``SEE_RULES``: the manager, the president,
  the vice president, the directors, the secretary, the treasurer). Member data: an owner's unit, balance, address,
  request, mail, hearing, lien, or a board matter that may name one.
- ``p0``: any signed-in person on the roster. The association's own records and operations, nothing about a member.
- ``admin``: one of jason's administrators, signed in as themselves (jobs, and the commands and logs they carry).

Where console sign-in is not set up (the loopback default, with no Google client), a gated loader answers as it did
before: the console is then open to whoever is at the machine, and the write guard (``jason.web.guard``) is its only
protection. This is the rule ``drive_choose`` has always had. Once sign-in is set up, no gated loader answers a person
who is not signed in (401), and none answers a signed-in person whose offices do not open its level (403).

Outside a request (a script, the Python API, a test that calls the function) nothing is checked: the caller is the
person at the terminal. In the owner view (``?view=owner``) the owner hook answers from ``OWNER_SOURCES`` and calls a
board loader only to filter it, so a read it makes passes; a read that carries ``view=owner`` never reaches ``source``.
"""

from __future__ import annotations

import functools
from typing import Any, Callable

Loader = Callable[..., dict[str, Any]]

P0, P2, ADMIN = "p0", "p2", "admin"

GATES: dict[str, str] = {
    # Member data: an owner's unit, balance, address, request, mail, hearing, lien.
    "delinquency": P2,
    "collections": P2,
    "title-watch": P2,
    "audit-chains": P2,
    "hearings": P2,
    "request-links": P2,
    "records-requests": P2,
    "mail-triage": P2,
    "minutes-review": P2,
    "owner-info": P2,
    "legal-cases": P2,
    "approvals": P2,
    "meetings": P2,
    # The board's working set: items, decisions, scratchpads, and the meeting room can name an owner or a unit.
    "board-items": P2,
    "board-digest": P2,
    "open-items": P2,
    "meeting": P2,
    "meeting-room": P2,
    "agenda-plan": P2,
    "decisions": P2,
    "canvases": P2,
    "dock": P2,
    "registers": P2,
    "insurance": P2,
    "insurance-renewals": P2,
    # jason's own operation: job commands and logs may name people.
    "jobs": ADMIN,
    # The association's own records and operations, nothing about a member. (``facts`` is not here: community facts are
    # not about a member and stay open as they were, ``jason.web.extra.unit_records``.)
    "budget": P0,
    "reconciliations": P0,
    "invoices": P0,
    "utility-payments": P0,
    "ledger-validation": P0,
    "reserves": P0,
    "reserve-findings": P0,
    "calendar": P0,
    "duties": P0,
    "leads": P0,
    "association-records": P0,
    "records-inventory": P0,
    "library-status": P0,
    "document-readings": P0,
    "library": P0,
    "library-kinds": P0,
    "drive-files": P0,
    "photos": P0,
    "embeds": P0,
    "templates": P0,
    "request-letter": P0,
    "onboarding": P0,
    "onboarding-session": P0,
    "communities": P0,
    "rule-changes": P0,
    "rule-records": P0,
    "rule-record": P0,
    "rule-record-history": P0,
    "rule-record-compare": P0,
    "rule-uses": P0,
    "rule-events": P0,
    "record-slots": P0,
    "record-slot": P0,
    "record-bindings": P0,
    "record-readings": P0,
    "key-documents": P0,
    "instrument-graph": P0,
    "governing-documents": P0,
    "documents-located": P0,
    "associations": P0,
    "filing-plan": P0,
    "document-codes": P0,
    "report-portal": P0,
    "backflow": P0,
    "watchlist": P0,
}


def _configured() -> bool:
    from flask import current_app

    sign_in = current_app.extensions.get("jason_sign_in")
    return bool(sign_in is not None and getattr(sign_in, "configured", False))


def check(gate: str) -> None:
    """In a request where console sign-in is set up: abort 401 (not signed in) or 403 (the offices do not open the level,
    or not an administrator for ``admin``). Otherwise nothing."""
    from flask import abort, has_request_context

    if not has_request_context() or not _configured():
        return
    from jason.web import access

    viewer = access.signed_in()
    if gate == ADMIN:
        from jason.web.extra.status import require_admin

        require_admin()
        return
    access.allow(viewer, access.Level[gate.upper()])


def gated(name: str, load: Loader, gate: str) -> Loader:
    """``load`` behind ``gate``; it keeps its name, and a read in the owner view (see the module) passes."""
    @functools.wraps(load)
    def read(*args: Any, **kw: Any) -> dict[str, Any]:
        from flask import has_request_context, request

        if not (has_request_context() and request.args.get("view") == "owner"):
            check(gate)
        return load(*args, **kw)

    read.gate = gate  # type: ignore[attr-defined]
    return read


def apply(loaders: dict[str, Loader]) -> dict[str, Loader]:
    """``loaders`` with every one that ``GATES`` names wrapped; the rest as they are (they gate themselves, or are open by
    design, each recorded with its reason in ``tests/fixtures/loader_gates.json``)."""
    return {name: gated(name, load, GATES[name]) if name in GATES else load for name, load in loaders.items()}


__all__ = ["ADMIN", "GATES", "P0", "P2", "apply", "check", "gated"]
