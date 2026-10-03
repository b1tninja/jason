"""The board's officers and the manager by role, their names from the private facts.

Who holds which seat is a private fact in data/spec/officers.json (jason.community.private): a list of
``{"role": "president" | "vice president" | "secretary" | "treasurer" | "director" | "manager", "name": "...",
"approves": [...], "email": "..."}``. ``email`` is the Google account the person signs in to jason-web with; a row
without one cannot sign in. ``approves`` names what the person may approve alone and defaults by role: the president
approves "the president", the secretary "the secretary", the treasurer "the treasurer", the manager "the manager";
a vice president or director approves nothing alone. A row may add "a fluent reviewer" (translations). "The board"
is never a person's: it is a vote at a meeting (CIV 4910) that the president or the secretary records.
"""

from __future__ import annotations

from jason.community.base import Officer, OfficerRole

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
        try:
            role = OfficerRole(str(row.get("role", "")).strip().lower())
        except ValueError:
            continue
        if not name:
            continue
        approves = row.get("approves")
        rows.append(Officer(role, name, tuple(str(a) for a in approves) if isinstance(approves, list) else DEFAULT_APPROVES[role],
                            str(row.get("email", "") or "").strip()))
    return tuple(rows)


__all__ = ["DEFAULT_APPROVES", "officers"]
