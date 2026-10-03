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

How people sign in to the console for this community is data/spec/<profile>/sign_in.json (``jason sign-in
--import-client`` writes it): ``[{"key": "...", "record_uid": "...", "provider": "google", "domains": [...],
"label": "..."}]``, each a Google client in Keeper. Empty, the installation's sign-in applies (jason.access).
jason's admins and the managers of a portfolio are the installation's, not the community's (data/access).
"""

from __future__ import annotations

from jason.community.base import IdentityProvider, Officer, OfficerRole, SignInProvider

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


def sign_in() -> tuple[SignInProvider, ...]:
    from jason.community.private import facts

    from jason.access import providers_from

    return providers_from(facts("sign_in", []))


__all__ = ["DEFAULT_APPROVES", "officers", "sign_in"]
