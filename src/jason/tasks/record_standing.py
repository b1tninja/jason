"""What reads a slot's pick: the duties, the programs, and the conflicts that rest on the record a slot holds (docs/record-intake.md,
phase 3). Read-only: it calls the community's own catalogs and decides nothing.

A match is made by the **record** a slot stands for (a Civil Code 5200 record or a key document's record) and by the **citations** the
slot names as requiring it, never by reading the picked file's words. So it says which duties and recorded conflicts rest on this
slot's record, so a person who pins a file sees what depends on it. Reading the file's own words for duties is a different tool
(``jason duties --documents KEY``), not wired to a pick here.

- ``duties``: the manager's duties (``jason.community.duties.DUTIES``) whose records include the slot's record, or whose sections
  share a citation with the slot's.
- ``conflicts``: the profile's ``Conflict`` rows (``Community.conflicts()``) whose authority or provision cites a section the slot
  requires. A confidential slot shows the count only.
- ``programs``: the adoption catalog of docs/programs.md is not built, so none is shown and the view says why.
"""

from __future__ import annotations

from typing import Any

from jason.community.record_slots import Slot, citations_in


def _sections(text: str) -> set[str]:
    return set(citations_in(text))


def _shared(wanted: set[str], found: set[str]) -> list[str]:
    """The citations the two sets share, at the more general of the two: "CIV 5200" and "CIV 5200(a)(1)" meet, "CIV 5200(a)(2)" and
    "CIV 5200(a)(1)" do not."""
    return sorted({a for a in wanted for b in found if a == b or a.startswith(b + "(") or b.startswith(a + "(")} |
                  {b for a in wanted for b in found if b.startswith(a + "(")})


def duties_for(slot: Slot) -> list[dict[str, Any]]:
    from jason.community.duties import DUTIES

    wanted = set(slot.requires)
    out = []
    for d in DUTIES:
        by_record = bool(slot.record) and slot.record in {r.value for r in d.records}
        shared = _shared(wanted, _sections(d.sections))
        if not by_record and not shared:
            continue
        out.append({"anchor": d.anchor, "keeps": d.keeps_straight, "cadence": d.cadence.value, "when": d.when, "sections": d.sections,
                    "produce": d.produce, "because": "its record is this slot's record" if by_record else "it cites " + ", ".join(shared),
                    "command": f"jason duties --brief \"{d.anchor}\""})
    return out


def conflicts_for(slot: Slot, community: Any) -> list[dict[str, Any]]:
    from jason.community.authority_order import conflicts

    wanted = set(slot.requires)
    if not wanted or community is None:
        return []
    out = []
    for c in conflicts(community):
        shared = _shared(wanted, _sections(f"{c.authority} {c.provision}"))
        if not shared:
            continue
        out.append({"key": c.key, "provision": c.provision, "authority": c.authority, "status": c.status.value, "clarity": c.clarity.value,
                    "open": c.open, "boardItem": c.board_item, "because": "it cites " + ", ".join(shared),
                    "command": "jason conflicts"})
    return out


def programs_for(slot: Slot) -> dict[str, Any]:
    try:
        import importlib

        importlib.import_module("jason.community.program_catalog")
    except ImportError:
        return {"available": False, "items": [], "why": "the program catalog (docs/programs.md) is not built, so no program is read against a slot"}
    return {"available": False, "items": [], "why": "the program catalog exists but is not read against slots yet"}


def standing(slot: Slot, community: Any, *, pinned: int, read: int, private: bool) -> dict[str, Any]:
    """The read-only block of a slot's page: what rests on this slot's record. ``pinned`` and ``read`` say how much of a pick there
    is: with none, the lists still say what the record would carry."""
    hold = slot.confidential and not private
    duties = duties_for(slot)
    found = conflicts_for(slot, community)
    return {
        "pinned": pinned, "read": read,
        "duties": duties,
        "conflicts": {"count": len(found), "open": sum(1 for c in found if c["open"]), "items": [] if hold else found, "held": hold and bool(found)},
        "programs": programs_for(slot),
        "caveats": ["Matched by the record the slot stands for and the citations it names, not by reading the file's words.",
                    "A duty or a conflict listed here is a lead for the board; jason decides nothing and resolves no conflict."],
    }


__all__ = ["conflicts_for", "duties_for", "programs_for", "standing"]
