"""The PDF splitter's apply journal (docs/pdf-splitter-failure-modes.md section 5; docs/pdf-splitter.md section 6.5).

An apply writes to four places (the part files, the slot store, the library, the session). No file system makes that atomic, so the
apply keeps a memory of what it meant to do and what it has done: ``<data>/split/journal/<session>.jsonl``, one JSON object a line,
``{n, prev, at, kind, apply, by, detail}``. ``n`` counts events in the file; ``prev`` is the first 12 hex of the sha256 of the previous
line, so an edited line breaks the chain; each line is flushed and ``fsync``ed (``jason.durable``); a torn last line (a crash) is
dropped on read, never guessed at. The journal holds ids, hashes, counts, and slot keys. It holds **no file name and no page's text**.

Events of one apply, in order:

- ``intent``: first, before anything is written. The plan fingerprint the person reviewed (``fingerprint``) and the fingerprint of the
  choices alone (``inputs``), the draft's version, the source hash, the status the session had (``before``), the person's choices
  (``args``: parts, drop, filing, rotate, keep-copies, ocr, so a finish needs nothing restated), and each part's ordinal, segment,
  planned action, slot, and the **pre-allocated pin id** (so a resume recognises its own pin and never pins twice).
- ``placing``: before a part's file is kept and pinned (a part is then possibly visible).
- ``part``: after it: the part's result as it goes into the session (action, slot, pin, ref, hash, size).
- ``failed``: a part that could not be written (the apply stops at it; a re-run of the same choices resumes).
- ``library``: the parts the library intake took in, or held, as a batch.
- ``commit``: last. The session is written as applied. ``queued``: the read-back and OCR jobs, after the commit.
- ``abort``: a roll back (``reason``), or an apply that never wrote anything.

States (``state``): ``none`` (no journal), ``clean`` (the last apply committed or aborted), ``pending`` (an intent with neither: an
apply that did not finish). A pending apply with no ``placing`` event wrote nothing visible; any other is **partly visible** and is
finished (``split_session.recover(..., "finish")``) or rolled back (``"rollback"``) by a person, never by a background job.

``JASON_FAULT=split.apply:<point>`` raises ``Killed`` (a ``BaseException``, so no ``except Exception`` swallows it, as with a real kill)
at a named point of the apply. It is read only when set, and is for the tests and the doctor's drill.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jason.durable import durable_append

FOLDER = "journal"
_SID = re.compile(r"^[0-9a-f]{8}([0-9a-f]{8})?$")


class Killed(BaseException):
    """A simulated kill at a fault point. Not an ``Exception``: nothing in the apply may catch it and carry on."""


def fault(point: str) -> None:
    """Raise ``Killed`` when ``JASON_FAULT`` names this point of the apply. A no-op unless the variable is set."""
    want = os.environ.get("JASON_FAULT")
    if want and want == f"split.apply:{point}":
        raise Killed(point)


def journal_file(root: Path, sid: str) -> Path:
    if not _SID.match(str(sid or "")):
        raise KeyError(sid)
    return Path(root) / "split" / FOLDER / f"{sid}.jsonl"


def _chain(line: str) -> str:
    return hashlib.sha256(line.encode("utf-8")).hexdigest()[:12]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def read(root: Path, sid: str) -> list[dict[str, Any]]:
    """The events in order. A last line that does not parse is a torn write and is dropped; so is anything after a line whose chain
    is broken (the journal is then read as far as it can be trusted)."""
    try:
        text = journal_file(root, sid).read_text(encoding="utf-8")
    except (OSError, KeyError):
        return []
    out: list[dict[str, Any]] = []
    prev = ""
    for line in text.splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except ValueError:
            break
        if not isinstance(row, dict) or row.get("prev", "") != prev:
            break
        out.append(row)
        prev = _chain(line)
    return out


def append(root: Path, sid: str, kind: str, apply_id: str, by: str, detail: dict[str, Any] | None = None) -> dict[str, Any]:
    """Add one event (flushed to disk before this returns). The caller holds the session's lock, so ``n`` is the last plus one."""
    path = journal_file(root, sid)
    text = ""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        pass
    lines = [ln for ln in text.splitlines() if ln.strip()]
    events = read(root, sid)
    if len(events) != len(lines):                # a torn or broken tail: cut back to what is trusted before adding to it
        from jason.durable import durable_write

        durable_write(path, "".join(json.dumps(e, ensure_ascii=False, separators=(",", ":")) + "\n" for e in events))
        lines = [json.dumps(e, ensure_ascii=False, separators=(",", ":")) for e in events]
    row = {"n": len(events) + 1, "prev": _chain(lines[-1]) if lines else "", "at": _now(), "kind": kind, "apply": apply_id, "by": by,
           "detail": detail or {}}
    durable_append(path, json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
    return row


def _last_apply(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    start = max((i for i, e in enumerate(events) if e.get("kind") == "intent"), default=None)
    return [] if start is None else events[start:]


def state(root: Path, sid: str) -> dict[str, Any]:
    """The journal's last apply: ``{"state": none | clean | pending, "apply", "intent", "visible", "parts", "failed", "events"}``.
    ``visible`` is whether anything outside the splitter's own folders may have been written (a ``placing`` event); ``parts`` are the
    ``part`` results so far."""
    events = _last_apply(read(root, sid))
    if not events:
        return {"state": "none", "apply": "", "intent": {}, "visible": False, "parts": [], "failed": [], "events": 0}
    intent = events[0]
    kinds = [e["kind"] for e in events]
    done = "commit" in kinds or "abort" in kinds
    parts = [e["detail"] for e in events if e["kind"] == "part"]
    for e in events:
        if e["kind"] == "library":
            parts += list(e["detail"].get("parts") or ())
    return {"state": "clean" if done else "pending", "apply": intent.get("apply", ""), "by": intent.get("by", ""), "at": intent.get("at", ""),
            "intent": intent.get("detail") or {}, "visible": "placing" in kinds or "library" in kinds, "parts": parts,
            "failed": [e["detail"] for e in events if e["kind"] == "failed"], "events": len(events),
            "committed": "commit" in kinds, "queued": "queued" in kinds}


def pending(root: Path, sid: str) -> dict[str, Any] | None:
    """The unfinished apply of this session, or None."""
    st = state(root, sid)
    return st if st["state"] == "pending" else None


def describe(st: dict[str, Any]) -> dict[str, Any]:
    """What a screen or a command says of an unfinished apply: who, when, how far, and the two ways out. No file name."""
    intent = st.get("intent") or {}
    planned = [p for p in intent.get("parts") or () if p.get("action") not in ("collision", "duplicate")]
    return {"apply": st["apply"], "by": st.get("by", ""), "at": st.get("at", ""), "written": len(st.get("parts") or ()), "of": len(planned),
            "visible": bool(st.get("visible")), "failed": len(st.get("failed") or ()),
            "choices": ["finish", "rollback"],
            "words": ("An apply started" + (f" by {st['by']}" if st.get("by") else "") + (f" at {st['at']}" if st.get("at") else "")
                      + f" did not finish: {len(st.get('parts') or ())} of {len(planned)} files were written. Finish it with the same choices "
                        "(--finish), or roll it back (--rollback); either is a person's act (--yes --by NAME).")}


def input_hash(session: Any, plan: dict[str, Any], keep_copies: bool, *, full: bool) -> str:
    """The fingerprint of a plan. ``full`` includes what the world answered (each part's action, so a slot taken since the review, a
    duplicate, or a changed hash shows); without it, only the person's inputs and the draft: the source's hash, the draft's version,
    its boundaries and labels, the parts and where each goes, the pages left out, the turns, and the filing asked. A person's review
    and a person's apply must carry the same one, or nothing is written."""
    version = int((session.confirmed or {}).get("draftVersion") or session.version) if session.status == "confirmed" else int(session.version)
    body: dict[str, Any] = {
        "source": session.source.sha256, "version": version, "keepCopies": bool(keep_copies),
        "boundaries": [[b.page, b.level] for b in session.ordered()],
        "labels": {k: dict(sorted(v.items())) for k, v in sorted(session.labels.items())},
        "parts": [[r["segment"], r["start"], r["end"], r["level"], r.get("slot", ""), r.get("period", ""), r.get("entry", ""),
                   r.get("filing", "")] for r in plan["parts"]],
        "dropped": list(plan["dropped"]), "rotated": [[x["page"], x["degrees"]] for x in plan["rotated"]],
        "filing": plan["filing"]["asked"],
    }
    if full:
        body["actions"] = [[r["segment"], r["action"], r.get("sha256", "")] for r in plan["parts"]]
    return hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()[:32]


__all__ = ["Killed", "append", "describe", "fault", "input_hash", "journal_file", "pending", "read", "state"]
