"""The ``hearings`` loader's rows and the decision writer's answer: a hearing by a general title and an opaque handle,
its address and findings only in the private view.

A hearing is a member's discipline. Its record (``zoom/hearings.json``, ``zoom/hearings/*``) is P3 by ``PATH_RULES``,
so it opens as the executive record does (``jason.web.extra.meeting_room.private_view``): a signed-in person whose
offices open P3 in the private view, which is open for a stated reason, and each opening is logged in
``access/served.jsonl``. Outside it the board still sees that a hearing is on the calendar and against which 5855 clock,
and nothing more: the open record names the matter in the statute's general words (CIV 4935(e)), never the unit, the
owner, the violation, or the findings. The list carries each hearing's ``handle``, the random name ``hearing_decisions``
keeps beside its key, and no key: the day-and-address key is never in a URL or an element id. Redaction is an allowlist,
so a field added to the stored row stays out of the open rows until someone decides it belongs there.

Outside a request (a script, the Python API) the caller is the person at the terminal and sees the whole row. In a
request with no console sign-in, the private view cannot open, so the rows are held (as the executive record is).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

LOG_PATH = "zoom/hearings.json"
HELD = ("This hearing's unit, owner, violation, notice, and findings are a member's discipline (Civil Code 4935(b)). "
        "They open in the private view, for the offices that open restricted material.")


def general_title() -> str:
    """The matter in the statute's words: ``Hearing on member discipline (Civil Code 4935(a), (b))``."""
    from jason.community.models.meetings import ExecutiveSubject, executive_general_note

    return "Hearing on " + executive_general_note([ExecutiveSubject.DISCIPLINE])


def private_open() -> bool:
    """Whether this read may show the whole row: always outside a request; in one, the private view is open and the
    person's offices open P3 in it (logged)."""
    from flask import has_request_context

    if not has_request_context():
        return True
    from jason.web.extra.meeting_room import private_view

    return private_view("", path=LOG_PATH)


def _stages(h: dict[str, Any]) -> list[dict[str, Any]]:
    decision = h.get("decision") or None
    stages = [{"key": "noticeBy", "label": "Notice delivered by", "date": str(h.get("noticeBy", ""))[:10], "authority": "CIV 5855(a)", "done": bool(h.get("noticeOn"))},
              {"key": "hearing", "label": "Hearing", "date": str(h.get("start", ""))[:10], "done": bool(decision)}]
    if decision:
        stages.append({"key": "noticeDueBy", "label": "Written decision to the owner by", "date": decision["noticeDueBy"], "authority": "CIV 5855(f)"})
    elif h.get("decisionByIfHeld"):
        stages.append({"key": "decisionBy", "label": "Written decision by, if the board acts at the hearing", "date": str(h["decisionByIfHeld"])[:10], "authority": "CIV 5855(f)"})
    return [st for st in stages if st["date"]]


def whole(h: dict[str, Any], root: Path) -> dict[str, Any]:
    """The row as the private view shows it: the stored row, its clock, and its notice's references (P3)."""
    from jason.web.extra.meeting_docs import hearing_refs

    return {**h, "title": general_title(), "stages": _stages(h), "decision": h.get("decision") or None,
            "noticeRefs": hearing_refs(h, root), "held": False}


def open_row(h: dict[str, Any]) -> dict[str, Any]:
    """The row outside the private view: the handle, the general title, the days and the clock, whether a meeting is
    scheduled, how many problems the plan found, and when a decision was recorded. Nothing else."""
    d = h.get("decision") or None
    return {"handle": h.get("handle", ""), "title": general_title(), "start": h.get("start", ""), "noticeBy": h.get("noticeBy", ""),
            "noticeOn": h.get("noticeOn", ""), "decisionByIfHeld": h.get("decisionByIfHeld", ""), "standing": h.get("standing", ""),
            "scheduled": bool(h.get("scheduled")), "problemCount": len(h.get("problems") or []), "stages": _stages(h),
            "decision": {"decidedOn": d["decidedOn"], "noticeDueBy": d["noticeDueBy"], "recorded": d["recorded"]} if d else None,
            "held": True, "heldWhy": HELD}


def rows(private: bool) -> dict[str, Any]:
    from jason.mcp.county import _data_dir, hearings as tool

    root = _data_dir(None)
    out = tool(include_confidential=True)                     # this loader does its own allowlisting (open_row)
    allr = out.get("hearings", [])
    listed = [h for h in allr if h.get("handle")]
    shaped = [whole(h, root) if private else open_row(h) for h in listed]
    return {**out, "hearings": shaped, "held": not private, "unmigrated": len(allr) - len(listed)}


def hearings(args: dict[str, str]) -> dict[str, Any]:
    """The hearings as `jason hearing` saved them: each by handle, its 5855 clock as stages, and its decision when there
    is one. The unit, the grounds, the notice (``noticeRefs``), and the findings only in the private view (P3)."""
    return rows(private_open())


def write(handle: str, body: dict[str, Any]) -> dict[str, Any]:
    """The board's decision after a hearing, onto the row ``handle`` names (P3: only in the private view, logged), and
    the row as the private view shows it. ``KeyError`` for a handle that names none; the day-and-address key does not.
    With no console sign-in set up the private view cannot open, so every handle is a ``KeyError`` (the 404 a missing
    hearing gets) and nothing is echoed. Where sign-in is set up, the 401 or 403 comes before the handle is looked up and
    is the same for every handle, and the opening is logged only for a handle that names a row. Recorded by the signed-in
    account, never the ``by`` the body carries (``gates.recorded_by``)."""
    from jason.mcp.county import _data_dir
    from jason.tasks.hearing_decisions import key_for_handle, record
    from jason.web import gates

    if gates.without_sign_in():
        raise KeyError(handle)                                # the private view cannot open: the row is as one that is not there
    gates.check_private(LOG_PATH, log=False)                  # 401, or 403 for every handle alike; the opening is logged below
    root = _data_dir(None)
    key = key_for_handle(root, handle)                        # KeyError for a handle that names none: nothing is logged
    gates.check_private(LOG_PATH)
    record(root, key, findings=str(body.get("findings", "")), decided_on=str(body.get("decidedOn", "")), by=gates.recorded_by(body))
    return next(r for r in rows(True)["hearings"] if r.get("handle") == handle)


__all__ = ["HELD", "LOG_PATH", "general_title", "hearings", "open_row", "private_open", "rows", "whole", "write"]
