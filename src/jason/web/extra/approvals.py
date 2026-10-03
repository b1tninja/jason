"""The approvals inbox: the letters jason drafted and where each stands, and the one write, a person's step.

Reads disk only (``data/approvals/letters.json``) and the profile's officers for who may approve. The write records a
person's act on a draft (saving it, asking for approval, approving, sending it back, recording that it was sent).
Nothing here sends anything: an approved letter shows the terminal command a person runs.
"""

from __future__ import annotations

from typing import Any

Args = dict[str, str]

CAVEATS = (
    "Nothing is sent, posted, recorded, or filed without approval.",
    "A board approval is a vote at a meeting (CIV 4910) that an officer, the president or the secretary, records here with the meeting's date.",
    "Sending is a terminal command a person runs; the page shows it and never runs it. Recording the send names where it was logged.",
    "jason drafts and records; it decides nothing and moves no letter on its own.",
)
GROUPS = ("requested", "approved", "sent", "drafts")


def _people() -> list[dict[str, Any]]:
    from jason.community import community
    from jason.tasks.approvals import BOARD

    people: dict[str, dict[str, Any]] = {}             # one entry a person: two offices are one person, roles joined
    for o in community().officers():
        p = people.setdefault(o.name, {"name": o.name, "role": "", "approves": [], "canApproveBoard": False})
        p["role"] = ", ".join(r for r in (p["role"], o.role.value) if r)
        p["approves"] += [a for a in o.approves if a not in p["approves"]]
        p["canApproveBoard"] = p["canApproveBoard"] or o.can_approve(BOARD)
    return list(people.values())


def approvals(args: Args) -> dict[str, Any]:
    """Every letter with its stage and trail, grouped; the people who may approve; or, with ``key``, one letter in full."""
    from jason.mcp.county import _data_dir
    from jason.tasks import approvals as store

    root = _data_dir(None)
    key = args.get("key", "").strip()
    if key:
        try:
            letter = store.get(root, key)
        except KeyError:
            return {"found": False, "note": f"no letter at {key}", "key": key}
        return {"found": True, "letter": letter, "people": _people(), "stages": list(store.STAGES), "caveats": list(CAVEATS)}
    letters = store.all(root)
    groups: dict[str, list[str]] = {g: [] for g in GROUPS}
    for letter in letters:
        groups["drafts" if letter["stage"] in ("draft", "saved") else letter["stage"]].append(letter["key"])
    return {"found": True, "count": len(letters), "letters": letters, "groups": groups, "pending": store.pending_count(root),
            "people": _people(), "stages": list(store.STAGES), "approvers": list(store.APPROVERS), "caveats": list(CAVEATS),
            "note": "" if letters else "no letter drafted yet"}


def write(key: str, body: dict[str, Any]) -> dict[str, Any]:
    """``body.action`` is ``draft`` or one of the transitions (``save, request, withdraw, send_back, approve,
    record_sent``), with ``by`` (the person) and ``note``; ``draft`` carries the text in ``body.letter`` (and the key in
    ``body.letter.key`` when the URL's key is empty or ``-``); ``approve`` for the board carries ``meeting``;
    ``record_sent`` carries ``sentRef``. Returns the letter."""
    from jason.mcp.county import _data_dir
    from jason.tasks import approvals as store

    root = _data_dir(None)
    action = str(body.get("action", "")).strip()
    by = str(body.get("by", ""))
    note = str(body.get("note", "") or "")
    if action == "draft":
        text = body.get("letter")
        if not isinstance(text, dict):
            raise ValueError("draft carries the text in letter")
        key = key.strip() if key.strip() not in ("", "-", "new") else str(text.get("key", "")).strip()
        return store.draft(root, key, text, by=by, note=note)
    if action not in store.TRANSITIONS:
        raise ValueError(f"action is draft or one of {', '.join(store.TRANSITIONS)}")
    return store.step(root, key, action, by=by, note=note, meeting=body.get("meeting"), sent_ref=str(body.get("sentRef", "") or ""))


__all__ = ["CAVEATS", "GROUPS", "approvals", "write"]
