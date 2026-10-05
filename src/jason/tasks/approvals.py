"""Approvals: the letters jason drafted, each waiting on a person to review, approve, and send.

A letter is kept once, keyed by its path (a Drive path or a store path), so the inbox and the document always
agree. jason writes the draft and records each step a person takes; it never moves a letter on its own. The stages
are ``draft -> saved -> requested -> approved -> sent`` and every transition carries the name of the person who
made it. An approval by "the board" is not a person's act: it is a vote at a meeting (Civil Code 4910) that the
president or the secretary records, with the meeting's date. Sending is a terminal command a person runs
(``sentCommand``); the person then records where the send was logged (``sentRef``). The store is
``data/approvals/letters.json``; it calls no service and reads the profile only for who may approve.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

STORE = "approvals"
FILE = Path(STORE) / "letters.json"

STAGES = ("draft", "saved", "requested", "approved", "sent")
APPROVERS = ("the board", "the president", "the secretary", "the treasurer", "the manager", "a fluent reviewer")
BOARD = "the board"
TEXT_FIELDS = ("kind", "title", "date", "to", "via", "signoff", "approver", "sentCommand")
# The transitions a person may make, and the stages each leaves from and lands on.
TRANSITIONS: dict[str, tuple[tuple[str, ...], str]] = {
    "save": (("draft",), "saved"),
    "request": (("saved",), "requested"),
    "withdraw": (("requested",), "saved"),
    "send_back": (("requested",), "saved"),
    "approve": (("requested",), "approved"),
    "record_sent": (("approved",), "sent"),
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _path(data_dir: Path) -> Path:
    return Path(data_dir) / FILE


def load(data_dir: Path) -> dict[str, dict[str, Any]]:
    """Every letter by key, as stored."""
    path = _path(data_dir)
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8")).get("letters", {})


def _save(data_dir: Path, letters: dict[str, dict[str, Any]]) -> None:
    path = _path(data_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"letters": letters}, indent=1, ensure_ascii=False), encoding="utf-8")


def get(data_dir: Path, key: str) -> dict[str, Any]:
    letter = load(data_dir).get(key)
    if letter is None:
        raise KeyError(key)
    return letter


def all(data_dir: Path) -> list[dict[str, Any]]:  # noqa: A001 - the store's own vocabulary, as the inbox reads it
    """Every letter, most recently changed first."""
    return sorted(load(data_dir).values(), key=lambda l: (l.get("updated", ""), l["key"]), reverse=True)


def pending_count(data_dir: Path) -> int:
    """How many letters wait on an approver: the nav badge."""
    return sum(1 for l in load(data_dir).values() if l.get("stage") == "requested")


def _store_lock(fn):
    import functools

    from jason.locks import Resource, hold

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        with hold(Resource.STORE, STORE, timeout=60, purpose=f"approvals: {fn.__name__}"):
            return fn(*args, **kwargs)
    return wrapper


def _who(by: str) -> str:
    by = (by or "").strip()
    if not by:
        raise ValueError("every step names the person who took it (by)")
    return by


def _log(letter: dict[str, Any], title: str, by: str, tone: str = "neutral") -> None:
    now = _now()
    log = letter.setdefault("log", [])
    log.append({"id": str(len(log) + 1), "date": now[:10], "title": title, "tone": tone, "by": by})
    letter["updated"] = now


def _text(body: dict[str, Any], current: dict[str, Any] | None) -> dict[str, Any]:
    out: dict[str, Any] = dict(current or {})
    for name in TEXT_FIELDS:
        if name in body:
            out[name] = str(body[name] or "").strip()
    if "body" in body:
        paras = body["body"]
        if isinstance(paras, str):
            paras = [p for p in paras.replace("\r\n", "\n").split("\n\n")]
        if not isinstance(paras, list):
            raise ValueError("body is a list of paragraphs")
        out["body"] = [str(p).strip() for p in paras if str(p).strip()]
    out.setdefault("body", [])
    for name in TEXT_FIELDS:
        out.setdefault(name, "")
    if not out["title"]:
        raise ValueError("a letter needs a title")
    if not out["approver"]:
        out["approver"] = BOARD
    if out["approver"] not in APPROVERS:
        raise ValueError(f"approver is one of {', '.join(APPROVERS)}")
    return out


@_store_lock
def draft(data_dir: Path, key: str, body: dict[str, Any], *, by: str, note: str = "") -> dict[str, Any]:
    """Create a letter, or change its text while it is still a draft or a saved draft. ``body`` carries the text
    fields (``kind, title, date, to, via, body, signoff, approver, sentCommand``)."""
    by = _who(by)
    key = (key or "").strip()
    if not key:
        raise ValueError("a letter is keyed by its path")
    letters = load(data_dir)
    current = letters.get(key)
    if current is not None and current["stage"] not in ("draft", "saved"):
        raise ValueError(f"the text of a letter {current['stage']} is fixed; withdraw it or send it back first")
    text = _text(body, {k: v for k, v in (current or {}).items() if k in TEXT_FIELDS or k == "body"})
    now = _now()
    if current is None:
        letter = {"key": key, **text, "stage": "draft", "log": [], "created": now, "updated": now, "sentRef": ""}
        _log(letter, f"Drafted by {by}" + (f": {note}" if note else ""), by)
    else:
        letter = {**current, **text, "stage": "draft"}
        _log(letter, f"Draft changed by {by}" + (f": {note}" if note else ""), by)
    letters[key] = letter
    _save(data_dir, letters)
    return letter


def approver_for(community: Any, kind: Any) -> str:
    """The approver the specification names for a kind of draft (``Community.document_approvers``, a ``DraftKind``),
    or "" when it names none: a miss, never "the board" by default. ValueError for one not in ``APPROVERS``."""
    rows = getattr(community, "document_approvers", lambda: ())() if community is not None else ()
    found = next((r.approver for r in rows if r.kind is kind), "")
    if found and found not in APPROVERS:
        raise ValueError(f"the specification names {found!r} to approve {kind.value}; an approver is one of {', '.join(APPROVERS)}")
    return found


def approvers_named(community: Any, approver: str) -> tuple[str, ...]:
    """The people on the roster who may record ``approver``'s approval (``Officer.can_approve``), in roster order."""
    rows = getattr(community, "officers", lambda: ())() if community is not None else ()
    return tuple(dict.fromkeys(o.name for o in rows if approver and o.can_approve(approver)))


def _approval_check(letter: dict[str, Any], by: str, meeting: str | None) -> str:
    """Who may record the approval, and the log line. Raises ValueError when ``by`` may not."""
    from jason.community import community

    from jason.access import officers_with_managers
    from jason.community.profile import profile_name

    approver = letter.get("approver") or BOARD
    officers = officers_with_managers(community().officers(), profile_name())   # and the portfolio's manager
    if not officers:
        raise ValueError("the profile names no officers (officers.json), so no approval can be recorded")
    from jason.community.base import offices_of

    held = offices_of(officers, by)                    # a person may hold two offices: one row each
    if not held:
        raise ValueError(f"{by} is not one of the association's officers")
    person = next((o for o in held if o.can_approve(approver)), held[0])
    if approver == BOARD:
        if not person.can_approve(BOARD):
            raise ValueError("the board's approval is a vote at a meeting (CIV 4910); the president or the secretary records it")
        if not (meeting or "").strip():
            raise ValueError("a board approval needs the date of the meeting at which it voted (meeting, ISO date)")
        day = date.fromisoformat(str(meeting).strip())
        return f"The board approved it by vote at its meeting of {day.isoformat()} (CIV 4910); recorded by {by}, {person.role.value}"
    if not person.can_approve(approver):
        raise ValueError(f"{by} ({', '.join(o.role.value for o in held)}) is not {approver} and cannot approve for them")
    return f"Approved by {by} ({person.role.value}) as {approver}"


@_store_lock
def step(data_dir: Path, key: str, action: str, *, by: str, note: str = "", meeting: str | None = None, sent_ref: str = "") -> dict[str, Any]:
    """One transition of ``TRANSITIONS``, made by ``by``. Refused (ValueError) when the letter is not at the stage the
    transition leaves from, or when ``by`` may not approve for the letter's approver."""
    by = _who(by)
    if action not in TRANSITIONS:
        raise ValueError(f"no transition {action!r}; one of {', '.join(TRANSITIONS)}")
    letters = load(data_dir)
    letter = letters.get(key)
    if letter is None:
        raise KeyError(key)
    frm, to = TRANSITIONS[action]
    if letter["stage"] not in frm:
        raise ValueError(f"{action} applies to a letter {' or '.join(frm)}, not one {letter['stage']}")
    approver = letter.get("approver") or BOARD
    tail = f": {note}" if note.strip() else ""
    if action == "save":
        title, tone = f"Draft saved to {key} by {by}", "neutral"
    elif action == "request":
        title, tone = f"Approval requested from {approver} by {by}", "neutral"
    elif action == "withdraw":
        title, tone = f"Approval request withdrawn by {by}", "neutral"
    elif action == "send_back":
        title, tone = f"Sent back to the drafter by {by}", "warn"
    elif action == "approve":
        title, tone = _approval_check(letter, by, meeting), "good"
        if meeting:
            letter["meeting"] = date.fromisoformat(str(meeting).strip()).isoformat()
    else:  # record_sent
        ref = (sent_ref or "").strip()
        if not ref:
            raise ValueError("recording a send needs where it was logged (sentRef: a mailroom communication id or log line)")
        letter["sentRef"] = ref
        letter["sentOn"] = _now()[:10]
        title, tone = f"Recorded as sent by {by}; logged: {ref}", "good"
    letter["stage"] = to
    _log(letter, title + tail, by, tone)
    letters[key] = letter
    _save(data_dir, letters)
    return letter


__all__ = ["APPROVERS", "BOARD", "STAGES", "TRANSITIONS", "all", "approver_for", "approvers_named", "draft", "get", "load",
           "pending_count", "step"]
