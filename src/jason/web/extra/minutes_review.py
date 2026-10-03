"""The minutes review page: the drafts ``jason board --minutes`` wrote, one as a form the Secretary fills, and the save.

Reads disk only (``data/board``). The one write is the Secretary's answers to the draft's blanks
(``jason.tasks.minutes_review.save_review``): the answers go to ``minutes-draft-<date>.review.json`` and the filled copy
to ``minutes-<date>.md``; the draft is never edited. Nothing is posted: the board adopts the minutes at its next meeting.
"""

from __future__ import annotations

from typing import Any

Args = dict[str, str]

CAVEATS = (
    "The draft is jason's reading of the Zoom record; every line is for the Secretary to check against memory or the video.",
    "The Secretary approves the text; the board adopts the minutes at its next meeting (CIV 4950). Nothing here posts them.",
    "jason never edits the draft in place: the answers are kept beside it and filled into a copy. A redraft replaces the draft, and the answers are filled into the new one.",
    "A privacy flag is a lead, not a finding: a member's name beside a delinquency, fine, hearing, lien, or collections word belongs in the executive session minutes, and the open minutes note the matter only generally (CIV 4935(e)).",
)


def minutes_review(args: Args) -> dict[str, Any]:
    """Without ``date``: the drafts list. With it: the draft filled with the saved answers, its blanks (with their saved
    values and the line each sits in), the privacy flags by line, the sections, who reviewed it, and the commands."""
    from jason.mcp.county import _data_dir
    from jason.tasks import minutes_review as task

    root = _data_dir(None)
    day = args.get("date", "").strip()
    if not day:
        drafts = task.list_drafts(root)
        return {"found": bool(drafts), "count": len(drafts), "drafts": drafts, "caveats": list(CAVEATS),
                "note": "" if drafts else "no minutes draft under data/board; run jason board --minutes DATE"}
    src = task.draft_path(root, day)
    if not src.is_file():
        return {"found": False, "note": f"no minutes draft for {day}; run jason board --minutes {day}", "date": day,
                "command": f"jason board --minutes {day}"}
    text = src.read_text(encoding="utf-8", errors="replace")
    review = task.load_review(root, day)
    values = {k: str(v) for k, v in (review.get("values") or {}).items()}
    parsed = task.parse(text)
    blanks = [{**task.encode_blank(b), "value": values.get(b.id, "")} for b in parsed["blanks"]]
    names = task._names(root)
    privacy = task.privacy_flags(text, names=names)
    commands = {"redraft": f"jason board --minutes {day}"}
    if privacy:
        commands["privacy"] = "jason minutes-privacy --correct"
    return {"found": True, "date": day, "draft": text, "markdown": task.fill(text, values), "blanks": blanks,
            "open": sum(1 for b in blanks if not b["value"].strip()), "privacy": privacy, "namesFrom": "PayHOA" if names else "a conservative reading",
            "sections": [task.encode_section(s) for s in parsed["sections"]],
            "reviewedBy": review.get("by", ""), "savedAt": review.get("savedAt", ""), "history": review.get("history", []),
            "minutesFile": str(task.minutes_path(root, day)) if task.minutes_path(root, day).is_file() else "",
            "command": commands["redraft"], "commands": commands, "caveats": list(CAVEATS)}


def write(key: str, body: dict[str, Any]) -> dict[str, Any]:
    """``key`` is the date; ``body`` is {values: {blank id: text}, by}. Saves the answers and the filled copy."""
    from jason.mcp.county import _data_dir
    from jason.tasks import minutes_review as task

    values = body.get("values")
    if not isinstance(values, dict):
        raise ValueError("values is {blank id: text}")
    saved = task.save_review(_data_dir(None), key, {str(k): str(v) for k, v in values.items() if v is not None}, by=str(body.get("by", "")))
    return {**saved, **minutes_review({"date": key})}


__all__ = ["CAVEATS", "minutes_review", "write"]
