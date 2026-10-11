"""The exceptions log: ``exceptions.jsonl`` in the approvals store, append only (docs/held-items.md).

An item **flagged for review** (held for the board by jason's policy finding: no rule the board has adopted answers it)
may be decided by a director, an officer, or the manager as a **one-off exception**: approved, rejected, or kept
flagged, each with a reason. A one-off decision needs no rule (Civil Code 4355(b)(2)) and is not one; jason adopts none.
This log is how the board sees what was decided, case by case, under each finding, so it can write the rule.

One JSON object a line, never edited. A later fact about an earlier decision (the second person signed; the write was
applied) is a **later line**, not a change to the first. A line is::

    {at, event, approval, item, finding, boardItem, by, secondBy, decision, reason, applied, kind}

``event`` is ``decided`` (the person's decision), ``second`` (the second, distinct person signed the plan it is in), or
``applied`` (the apply ran: ``applied`` says whether this item's write was made). ``finding`` is the item's rule, the
row of the response policy that raised the flag. ``rows`` folds the lines into one record a decision; ``for_finding``
is a finding's history, ``counts`` the number of exceptions approved under each finding, and ``nudge`` whether a finding
has reached ``EXCEPTION_NUDGE``, where the plan suggests the board write a rule.

The reason is a person's words and is masked like the audit log's: no email address, phone number, or street address.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jason.approvals.model import Decision, PlanItem

FILE = "exceptions.jsonl"
LOCK_KEY = "approvals-exceptions"
# How many times a finding is decided by exception before the plan suggests that the board write a rule. The board's
# to change (docs/held-items.md, section 3); jason proposes a policy and never makes one.
EXCEPTION_NUDGE = 2
# A reason for approving an exception is words, not a token ("ok" is not a reason).
REASON_WORDS = 2
EVENTS = ("decided", "second", "applied")
FIELDS = ("at", "event", "approval", "item", "finding", "boardItem", "by", "secondBy", "decision", "reason", "applied",
          "kind")


def path(data_dir: Path | None = None) -> Path:
    from jason.approvals.store import store_dir

    return store_dir(data_dir) / FILE


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _line(event: str, approval: str, item: PlanItem, *, by: str, decision: str, reason: str, second_by: str = "",
          applied: bool = False, kind: str = "", at: str = "") -> dict[str, Any]:
    from jason.approvals.audit import mask

    if event not in EVENTS:
        raise ValueError(f"unknown exceptions-log event {event}")
    return {"at": at or _now(), "event": event, "approval": approval, "item": item.id, "finding": item.rule,
            "boardItem": item.board_item, "by": by, "secondBy": second_by, "decision": decision,
            "reason": mask(reason or ""), "applied": bool(applied), "kind": kind}


def _append(data_dir: Path | None, row: dict[str, Any]) -> dict[str, Any]:
    from jason.locks import Resource, hold

    file = path(data_dir)
    file.parent.mkdir(parents=True, exist_ok=True)
    with hold(Resource.STORE, LOCK_KEY, timeout=60, purpose=f"exceptions log {row['event']}"):
        with file.open("a", encoding="utf-8", newline="\n") as fh:
            fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    return row


def record(approval: str, item: PlanItem, *, by: str, decision: Decision, reason: str, kind: str = "",
           at: str = "", data_dir: Path | None = None) -> dict[str, Any]:
    """Append a person's decision on a flagged item (approved, rejected, or kept flagged), with their reason."""
    return _append(data_dir, _line("decided", approval, item, by=by, decision=decision.value, reason=reason, kind=kind,
                                   at=at))


def follow_up(approval: str, item: PlanItem, event: str, *, second_by: str = "", applied: bool = False,
              kind: str = "", data_dir: Path | None = None) -> dict[str, Any]:
    """Append a later fact about an earlier decision: the second person signed (``second``), or the apply ran
    (``applied``, with whether this item's write was made). The decision's own line is never changed."""
    if event == "decided":
        raise ValueError("a decision is recorded with record()")
    return _append(data_dir, _line(event, approval, item, by=item.decided_by, decision=item.decision.value,
                                   reason=item.reason, second_by=second_by, applied=applied, kind=kind))


def lines(data_dir: Path | None = None) -> list[dict[str, Any]]:
    """Every line as written, oldest first."""
    file = path(data_dir)
    if not file.is_file():
        return []
    out = []
    for text in file.read_text(encoding="utf-8").splitlines():
        if text.strip():
            try:
                out.append(json.loads(text))
            except ValueError:
                continue
    return out


def rows(data_dir: Path | None = None) -> list[dict[str, Any]]:
    """One record a decision, oldest first: each ``decided`` line with the ``secondBy`` and ``applied`` that later
    lines gave it (a later line for the same approval and item that follows its decision, until the next decision)."""
    out: list[dict[str, Any]] = []
    latest: dict[tuple[str, str], dict[str, Any]] = {}
    for line in lines(data_dir):
        key = (str(line.get("approval", "")), str(line.get("item", "")))
        if line.get("event", "decided") == "decided":
            row = {k: line.get(k, "" if k not in ("applied",) else False) for k in FIELDS if k != "event"}
            row["secondBy"], row["applied"] = line.get("secondBy", "") or "", bool(line.get("applied"))
            out.append(row)
            latest[key] = row
            continue
        row = latest.get(key)
        if row is None:
            continue
        if line.get("secondBy"):
            row["secondBy"] = line["secondBy"]
        if line.get("event") == "applied":
            row["applied"] = bool(line.get("applied"))
    return out


def for_finding(finding: str, data_dir: Path | None = None) -> list[dict[str, Any]]:
    """The decisions made under one finding (an item's rule), oldest first, across every plan."""
    return [r for r in rows(data_dir) if r["finding"] == finding]


def counts(data_dir: Path | None = None) -> dict[str, int]:
    """Exceptions approved under each finding. A decision counts once for its approval and item: the latest decision
    on it, and only if it approved the change (a rejection or a flag kept is in the history, not in the count)."""
    latest: dict[tuple[str, str], dict[str, Any]] = {}
    for r in rows(data_dir):
        latest[(r["approval"], r["item"])] = r
    out: dict[str, int] = {}
    for r in latest.values():
        if r["decision"] == Decision.APPROVED.value and r["finding"]:
            out[r["finding"]] = out.get(r["finding"], 0) + 1
    return out


def count(finding: str, data_dir: Path | None = None) -> int:
    return counts(data_dir).get(finding, 0)


def nudge(finding: str, data_dir: Path | None = None) -> bool:
    """Whether the finding has been decided by exception ``EXCEPTION_NUDGE`` times or more."""
    return count(finding, data_dir) >= EXCEPTION_NUDGE


__all__ = ["EVENTS", "EXCEPTION_NUDGE", "FILE", "FIELDS", "REASON_WORDS", "count", "counts", "follow_up", "for_finding", "lines",
           "nudge", "path", "record", "rows"]
