"""The console dock's own store: the action register, scratchpad notes, the questions asked, and translation drafts.

Everything here is a person's working material or jason's record of what a person did, kept in
``data/dock/dock.json``. A task is something a person said needs doing; completing it stamps who and when. A note is a
working note, never an association record (``NOTE_CAVEAT``). An ask is a question with the answer jason found in the
stores and where it came from, or no answer and the task it became: owned by the office the caller found owns the
duty, else unassigned and waiting for a person to take it (``UNASSIGNED``). A translation is an English
record beside a draft a person entered, which a fluent reviewer checks; the English notice controls. The store reads
no profile fact, calls no service, and decides nothing.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

STORE = "dock"
FILE = Path(STORE) / "dock.json"

NOTE_CAVEAT = "Working notes, not association records."
TRANSLATION_CAVEAT = "A translation is a draft for a fluent reviewer. The English notice controls."
ROUTED_ANSWER = "jason has no sourced answer; on the action register"
UNASSIGNED = "unassigned: waiting for a person to take it"
NO_DUE = "no due date: the board has set no lead time for answering a question"

NOTE_STATUSES = ("researching", "question", "draft", "parked", "done")
TRANSLATION_STATES = ("needs review", "sent for review", "approved")
TASK_SOURCES_FIXED = ("scratchpad", "ask", "manual")   # any other source is a screen id

TASK_EDITABLE = ("text", "owner", "due", "source", "screen")
NOTE_EDITABLE = ("title", "status", "body", "sources")

_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _today() -> str:
    return _now()[:10]


def _empty() -> dict[str, Any]:
    return {"tasks": [], "notes": [], "asks": [], "translations": []}


def load(data_dir: Path) -> dict[str, Any]:
    path = Path(data_dir) / FILE
    if not path.is_file():
        return _empty()
    raw = json.loads(path.read_text(encoding="utf-8"))
    return {**_empty(), **{k: list(v) for k, v in raw.items() if isinstance(v, list)}}


def save(data_dir: Path, data: dict[str, Any]) -> Path:
    path = Path(data_dir) / FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")
    return path


def _store_lock(fn):
    import functools

    from jason.locks import Resource, hold

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        with hold(Resource.STORE, STORE, timeout=60, purpose=f"dock: {fn.__name__}"):
            return fn(*args, **kwargs)
    return wrapper


def _next_id(rows: list[dict[str, Any]], prefix: str) -> str:
    taken = {str(r.get("id")) for r in rows}
    n = len(rows) + 1
    while f"{prefix}{n}" in taken:
        n += 1
    return f"{prefix}{n}"


def _find(rows: list[dict[str, Any]], row_id: str) -> dict[str, Any]:
    row = next((r for r in rows if str(r.get("id")) == row_id), None)
    if row is None:
        raise KeyError(row_id)
    return row


def _date_or_blank(value: Any, what: str) -> str:
    text = str(value or "").strip()
    if text and not _DATE.match(text):
        raise ValueError(f"{what} is YYYY-MM-DD")
    return text


def _who(by: Any) -> str:
    who = str(by or "").strip()
    if not who:
        raise ValueError("a write names who made it (by)")
    return who


def _strings(value: Any, what: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list) or not all(isinstance(x, str) for x in value):
        raise ValueError(f"{what} is a list of strings")
    return [x.strip() for x in value if x.strip()]


# -- tasks -----------------------------------------------------------------------------------------------------------


@_store_lock
def add_task(data_dir: Path, text: str, *, by: str, owner: str = "", due: str = "", source: str = "manual", screen: str = "") -> dict[str, Any]:
    """A task a person (or the scratchpad or Ask, on a person's click) puts on the register."""
    text = str(text or "").strip()
    if not text:
        raise ValueError("a task says what needs doing")
    by = _who(by)
    source = str(source or "manual").strip() or "manual"
    data = load(data_dir)
    now = _now()
    row = {"id": _next_id(data["tasks"], "t"), "text": text, "source": source, "screen": str(screen or "").strip(), "owner": str(owner or "").strip(),
           "due": _date_or_blank(due, "due"), "done": False, "doneBy": "", "doneAt": "", "created": now, "by": by,
           "history": [f"{now[:10]}: added by {by} from {source}"]}
    data["tasks"].append(row)
    save(data_dir, data)
    return row


@_store_lock
def update_task(data_dir: Path, task_id: str, *, by: str, **changes: Any) -> dict[str, Any]:
    """Change what a task says, who owns it, when it is due, or where it came from. Done is set by complete_task."""
    by = _who(by)
    unknown = sorted(set(changes) - set(TASK_EDITABLE))
    if unknown:
        raise ValueError(f"{', '.join(unknown)}: not a field a person edits; done goes through complete_task")
    if not changes:
        raise ValueError("nothing to change")
    data = load(data_dir)
    row = _find(data["tasks"], task_id)
    now = _now()
    for k, v in changes.items():
        v = _date_or_blank(v, "due") if k == "due" else str(v or "").strip()
        if k == "text" and not v:
            raise ValueError("a task says what needs doing")
        if row.get(k) != v:
            row.setdefault("history", []).append(f"{now[:10]}: {k} changed by {by}")
            row[k] = v
    save(data_dir, data)
    return row


@_store_lock
def complete_task(data_dir: Path, task_id: str, *, by: str, done: bool = True) -> dict[str, Any]:
    """Mark a task done, stamping who and when; ``done=False`` reopens it and clears the stamp."""
    by = _who(by)
    data = load(data_dir)
    row = _find(data["tasks"], task_id)
    now = _now()
    if done:
        row.update({"done": True, "doneBy": by, "doneAt": now})
        row.setdefault("history", []).append(f"{now[:10]}: done by {by}")
    else:
        row.update({"done": False, "doneBy": "", "doneAt": ""})
        row.setdefault("history", []).append(f"{now[:10]}: reopened by {by}")
    save(data_dir, data)
    return row


# -- notes -----------------------------------------------------------------------------------------------------------


@_store_lock
def add_note(data_dir: Path, title: str, *, by: str, body: str = "", status: str = "researching", sources: list[str] | None = None) -> dict[str, Any]:
    by = _who(by)
    title = str(title or "").strip() or "Untitled"
    if status not in NOTE_STATUSES:
        raise ValueError(f"status is one of {', '.join(NOTE_STATUSES)}")
    data = load(data_dir)
    now = _now()
    row = {"id": _next_id(data["notes"], "n"), "title": title, "status": status, "body": str(body or ""), "sources": _strings(sources, "sources"),
           "created": now, "updated": now, "by": by, "history": [f"{now[:10]}: opened by {by}"]}
    data["notes"].append(row)
    save(data_dir, data)
    return row


@_store_lock
def update_note(data_dir: Path, note_id: str, *, by: str, **changes: Any) -> dict[str, Any]:
    by = _who(by)
    unknown = sorted(set(changes) - set(NOTE_EDITABLE))
    if unknown:
        raise ValueError(f"{', '.join(unknown)}: not a field a person edits")
    if not changes:
        raise ValueError("nothing to change")
    data = load(data_dir)
    row = _find(data["notes"], note_id)
    now = _now()
    for k, v in changes.items():
        if k == "status":
            if v not in NOTE_STATUSES:
                raise ValueError(f"status is one of {', '.join(NOTE_STATUSES)}")
            if row.get("status") != v:
                row.setdefault("history", []).append(f"{now[:10]}: status {row.get('status')} -> {v} by {by}")
        elif k == "sources":
            v = _strings(v, "sources")
        else:
            v = str(v or "")
            if k == "title":
                v = v.strip() or "Untitled"
        row[k] = v
    row["updated"] = now
    row["by"] = by
    save(data_dir, data)
    return row


# -- asks -------------------------------------------------------------------------------------------------------------


@_store_lock
def record_ask(data_dir: Path, question: str, *, by: str, answer: str = "", sources: list[str] | None = None, screen: str = "",
               owner: str = "", routing: str = "") -> dict[str, Any]:
    """Record a question and what jason found. With no sources there is no answer: the question becomes a task
    (source ``ask``) owned by ``owner``, the office the caller found owns the duty (``routing`` says how), or, with no
    owner, plainly unassigned and waiting for a person to take it. The task has no due date until the board sets a
    lead time (``NO_DUE``). jason never guesses and picks no one."""
    by = _who(by)
    question = str(question or "").strip()
    if not question:
        raise ValueError("a question has words")
    cites = _strings(sources, "sources")
    owner = str(owner or "").strip()
    routing = str(routing or "").strip() or (UNASSIGNED if not owner else f"routed to {owner}")
    data = load(data_dir)
    now = _now()
    routed = not cites
    row = {"id": _next_id(data["asks"], "q"), "question": question, "answer": answer if not routed else ROUTED_ANSWER, "sources": cites,
           "screen": str(screen or "").strip(), "routed": routed, "at": now, "by": by, "task": ""}
    if routed:
        row.update({"routedTo": owner, "routing": routing})
        task = {"id": _next_id(data["tasks"], "t"), "text": f"Answer a question: {question}", "source": "ask", "screen": "", "owner": owner,
                "due": "", "done": False, "doneBy": "", "doneAt": "", "created": now, "by": by,
                "history": [f"{now[:10]}: routed from Ask by {by}; no sourced answer; {routing}", f"{now[:10]}: {NO_DUE}"]}
        data["tasks"].append(task)
        row["task"] = task["id"]
    data["asks"].append(row)
    save(data_dir, data)
    return row


# -- translations ----------------------------------------------------------------------------------------------------


@_store_lock
def add_translation(data_dir: Path, *, english_key: str, english: str, language: str, draft: str, by: str) -> dict[str, Any]:
    """An English record beside a person-entered draft in ``language``. The draft starts as ``needs review``."""
    by = _who(by)
    english, draft, language = str(english or "").strip(), str(draft or "").strip(), str(language or "").strip()
    if not english:
        raise ValueError("a translation starts from the English record")
    if not language:
        raise ValueError("a translation names its language")
    if not draft:
        raise ValueError("the draft is a person's text; jason has no translator here")
    data = load(data_dir)
    now = _now()
    row = {"id": _next_id(data["translations"], "x"), "englishKey": str(english_key or "").strip(), "english": english, "language": language,
           "draft": draft, "state": TRANSLATION_STATES[0], "by": by, "at": now, "history": [f"{now[:10]}: draft entered by {by}; needs review"]}
    data["translations"].append(row)
    save(data_dir, data)
    return row


@_store_lock
def translation_state(data_dir: Path, translation_id: str, state: str, *, by: str, note: str = "") -> dict[str, Any]:
    """Move a translation between ``needs review``, ``sent for review``, and ``approved``. Approval is a fluent
    reviewer's act, recorded here with their name."""
    by = _who(by)
    if state not in TRANSLATION_STATES:
        raise ValueError(f"state is one of {', '.join(TRANSLATION_STATES)}")
    data = load(data_dir)
    row = _find(data["translations"], translation_id)
    now = _now()
    if row.get("state") != state:
        row.setdefault("history", []).append(f"{now[:10]}: {row.get('state')} -> {state} by {by}" + (f": {note}" if note else ""))
    row["state"] = state
    row["by"] = by
    row["at"] = now
    save(data_dir, data)
    return row


__all__ = ["FILE", "NOTE_CAVEAT", "NOTE_EDITABLE", "NOTE_STATUSES", "NO_DUE", "ROUTED_ANSWER", "STORE", "TASK_EDITABLE", "TRANSLATION_CAVEAT", "TRANSLATION_STATES", "UNASSIGNED",
           "add_note", "add_task", "add_translation", "complete_task", "load", "record_ask", "save", "translation_state", "update_note", "update_task"]
