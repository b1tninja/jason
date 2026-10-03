"""The board's officers and the manager by role, their names from the private facts.

Who holds which seat is a private fact in data/spec/officers.json (jason.community.private): a list of
``{"role": "president" | "vice president" | "secretary" | "treasurer" | "director" | "manager", "name": "...",
"approves": [...], "email": "..."}``. ``role`` may be a list when one person holds more than one office, as the
bylaws allow (``["secretary", "treasurer"]``): one row per office, each with its own default ``approves``.
``approves`` names what the person may approve alone and defaults by role: the president approves "the president",
the secretary "the secretary", the treasurer "the treasurer", the manager "the manager"; a vice president or director
approves nothing alone. A row may add "a fluent reviewer" (translations). "The board" is never a person's: it is a vote
at a meeting (CIV 4910) that the president or the secretary records. ``email`` is the Google account the person signs
in to jason-web with; a row without one cannot sign in.

The people who build jason are data/spec/maintainers.json, ``[{"name": "...", "email": "..."}]``: with
``jason-web --dev`` they may view the console as any officer or office (jason.web.signin). It is not an office.
"""

from __future__ import annotations

from jason.community.base import Maintainer, Officer, OfficerRole

DEFAULT_APPROVES: dict[OfficerRole, tuple[str, ...]] = {
    OfficerRole.PRESIDENT: ("the president",),
    OfficerRole.SECRETARY: ("the secretary",),
    OfficerRole.TREASURER: ("the treasurer",),
    OfficerRole.MANAGER: ("the manager",),
    OfficerRole.VICE_PRESIDENT: (),
    OfficerRole.DIRECTOR: (),
}


def officers() -> tuple[Officer, ...]:
    from jason.community.private import facts

    rows = []
    for row in facts("officers", []):
        name = str(row.get("name", "")).strip()
        if not name:
            continue
        given = row.get("role", "")
        roles = []
        for r in given if isinstance(given, list) else [given]:
            try:
                roles.append(OfficerRole(str(r).strip().lower()))
            except ValueError:
                continue
        approves = row.get("approves")
        email = str(row.get("email", "") or "").strip()
        for role in roles:
            rows.append(Officer(role, name, tuple(str(a) for a in approves) if isinstance(approves, list) else DEFAULT_APPROVES[role],
                                email))
    return tuple(rows)


def maintainers() -> tuple[Maintainer, ...]:
    from jason.community.private import facts

    out = []
    for row in facts("maintainers", []):
        name, email = str(row.get("name", "") or "").strip(), str(row.get("email", "") or "").strip()
        if name and email:
            out.append(Maintainer(name, email))
    return tuple(out)


__all__ = ["DEFAULT_APPROVES", "maintainers", "officers"]
