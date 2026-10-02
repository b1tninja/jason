"""The board's running list of action items, a draft agenda from it, and its Google Sheet.

The list is ``data/board/items.json``. jason adds and refreshes items from its reviews (``upsert``); an item keeps its id,
so finding the same matter again updates it. The board owns an item's status, owner, meeting, and notes: a refresh
never overwrites them, and ``sync_sheet`` reads them back from the Sheet the board edits before writing jason's columns.

``agenda`` drafts the next meeting's agenda from the items proposed or on the agenda, open session first and executive
session after (CIV 4935), with the date the notice must go out (four days before, two for a meeting solely in executive
session; CIV 4920) and the items that need a notice of their own. The draft is a starting point for the board; the
board sets the agenda.
"""

from __future__ import annotations

import json
from dataclasses import asdict, fields
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from jason.community.board_items import (
    PRIORITY_ORDER,
    BoardItem,
    ItemCategory,
    ItemStatus,
    Priority,
    Session,
    agenda_session,
)

STORE = Path("board") / "items.json"
BOARD_FIELDS = ("status", "owner", "meeting", "notes")
SHEET_TITLE = "Mystique Board Action Items"
TAB = "Items"
COLUMNS = ("id", "priority", "status", "category", "title", "ask", "summary", "authority", "evidence", "session", "special_notice", "due",
           "opened", "owner", "meeting", "notes")


def _encode(item: BoardItem) -> dict[str, Any]:
    raw = asdict(item)
    for key in ("category", "priority", "status", "session"):
        raw[key] = raw[key].value if raw[key] is not None else None
    for key in ("due", "opened"):
        raw[key] = raw[key].isoformat() if raw[key] else None
    raw["evidence"] = list(item.evidence)
    return raw


def _decode(raw: dict[str, Any]) -> BoardItem:
    known = {f.name for f in fields(BoardItem)}
    data = {k: v for k, v in raw.items() if k in known}
    data["category"] = ItemCategory(data["category"])
    data["priority"] = Priority(data.get("priority") or "normal")
    data["status"] = ItemStatus(data.get("status") or "open")
    data["session"] = Session(data["session"]) if data.get("session") else None
    for key in ("due", "opened"):
        data[key] = date.fromisoformat(data[key]) if data.get(key) else None
    data["evidence"] = tuple(data.get("evidence") or ())
    return BoardItem(**data)


def load(data_dir: Path) -> list[BoardItem]:
    path = Path(data_dir) / STORE
    if not path.is_file():
        return []
    return [_decode(raw) for raw in json.loads(path.read_text(encoding="utf-8")).get("items", [])]


def save(data_dir: Path, items: list[BoardItem]) -> Path:
    path = Path(data_dir) / STORE
    path.parent.mkdir(parents=True, exist_ok=True)
    body = {"savedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"), "items": [_encode(i) for i in items]}
    path.write_text(json.dumps(body, indent=1), encoding="utf-8")
    return path


def _store_lock(fn):
    """Hold the board store (jason.locks) while ``fn`` reads, changes, and writes it, so two processes (a sync and an
    agent session) never lose one another's changes."""
    import functools

    from jason.locks import Resource, hold

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        with hold(Resource.STORE, "board-items", timeout=120, purpose=f"board items: {fn.__name__}"):
            return fn(*args, **kwargs)
    return wrapper


@_store_lock
def upsert(data_dir: Path, found: list[BoardItem], *, today: date | None = None) -> dict[str, int]:
    """Add new items and refresh jason's fields on existing ones; the board's fields are never overwritten."""
    day = today or date.today()
    items = {i.id: i for i in load(data_dir)}
    added = updated = 0
    for item in found:
        current = items.get(item.id)
        if current is None:
            item.opened = item.opened or day
            item.history.append(f"{day.isoformat()}: opened by {item.source}")
            items[item.id] = item
            added += 1
            continue
        for f in fields(BoardItem):
            if f.name in BOARD_FIELDS or f.name in ("opened", "history", "source"):
                continue
            new = getattr(item, f.name)
            if new not in (None, "", ()) and new != getattr(current, f.name):
                setattr(current, f.name, new)
                updated += 1
    save(data_dir, sorted(items.values(), key=lambda i: (PRIORITY_ORDER[i.priority], i.opened or day, i.id)))
    return {"added": added, "updated": updated, "items": len(items)}


@_store_lock
def propose(data_dir: Path, found: list[BoardItem], *, today: date | None = None) -> dict[str, Any]:
    """Add or refresh ``found`` and propose each new one for the next agenda. An item the board has already moved on
    (proposed, on the agenda, in progress, deferred, closed) keeps the board's status; only jason's fields refresh."""
    counts = upsert(data_dir, found, today=today)
    proposed = []
    for item in found:
        current = next(i for i in load(data_dir) if i.id == item.id)
        if current.status is ItemStatus.OPEN:
            set_fields(data_dir, item.id, today=today, status=ItemStatus.PROPOSED.value)
            proposed.append(item.id)
    return {**counts, "proposed": proposed}


@_store_lock
def set_fields(data_dir: Path, item_id: str, *, today: date | None = None, **changes: str) -> BoardItem:
    """Change an item's board-owned fields (status, owner, meeting, notes) and note it in the item's history."""
    items = load(data_dir)
    item = next((i for i in items if i.id == item_id), None)
    if item is None:
        raise KeyError(item_id)
    day = (today or date.today()).isoformat()
    for key, value in changes.items():
        if key not in BOARD_FIELDS:
            raise ValueError(f"{key} is jason's; the board sets {', '.join(BOARD_FIELDS)}")
        new = ItemStatus(value) if key == "status" else value
        if getattr(item, key) != new:
            item.history.append(f"{day}: {key} {getattr(item, key).value if key == 'status' else getattr(item, key)!s} -> {value}")
            setattr(item, key, new)
    save(data_dir, items)
    return item


def notice_date(meeting: date, *, executive_only: bool = False) -> date:
    """The last day to give notice of a board meeting (CIV 4920(a), (b)(2))."""
    return meeting - timedelta(days=2 if executive_only else 4)


def agenda(items: list[BoardItem], meeting: date | None = None, *, include_open: bool = False, community: Any = None) -> list[str]:
    """A draft agenda in Markdown from the items proposed or on the agenda (and, with ``include_open``, every open item).
    The association's name and its bylaws on a quorum come from the profile (the active one unless given)."""
    from jason.community.template_values import profile_values

    if community is None:
        from jason.community import community as active

        community = active()
    values = profile_values(community)
    wanted = {ItemStatus.PROPOSED, ItemStatus.ON_AGENDA} | ({ItemStatus.OPEN} if include_open else set())
    chosen = sorted((i for i in items if i.status in wanted), key=lambda i: (PRIORITY_ORDER[i.priority], i.category.value, i.id))
    open_items = [i for i in chosen if agenda_session(i) is Session.OPEN]
    executive = [i for i in chosen if agenda_session(i) is Session.EXECUTIVE]
    out = [f"# DRAFT agenda: board of directors, {values['ASSOCIATION_NAME']}", ""]
    if meeting:
        out.append(f"Meeting: {meeting:%A, %B %d, %Y}. Notice with this agenda by {notice_date(meeting):%A, %B %d} (CIV 4920(a)); "
                   "an item not on the posted agenda cannot be acted on (CIV 4930).")
        out.append("")
    out += [f"1. Call to order; roll call and quorum ({values['CITE_DIRECTOR_QUORUM']})",
            "2. Approval of the minutes of the last meeting (CIV 4950)", "3. Treasurer's report", ""]
    n = 4
    if open_items:
        out.append("## Open session")
        out.append("")
        for item in open_items:
            out.append(f"{n}. **{item.title}** ({item.priority.value}). {item.ask}")
            if item.special_notice:
                out.append(f"   - Notice: {item.special_notice}")
            if item.authority:
                out.append(f"   - Authority: {item.authority}")
            n += 1
        out.append("")
    out.append(f"{n}. Member comment (CIV 4925)")
    n += 1
    if executive:
        out.append("")
        out.append("## Executive session (CIV 4935); noted generally in the next open minutes (4935(e))")
        out.append("")
        for item in executive:
            out.append(f"{n}. **{item.title}** ({item.priority.value}). {item.ask}")
            n += 1
    out += ["", f"{n}. Adjournment", "", "_Drafted by jason from the board's action items; the board sets the agenda._"]
    return out


def list_lines(items: list[BoardItem], *, every: bool = False) -> list[str]:
    shown = [i for i in items if every or i.status is not ItemStatus.CLOSED]
    out = [f"{len(shown)} board action items" + ("" if every else " not closed"), ""]
    for i in shown:
        out.append(f"[{i.priority.value:<6}] [{i.status.value:<11}] {i.id}: {i.title}")
        out.append(f"      ask: {i.ask}")
        if i.authority:
            out.append(f"      authority: {i.authority}")
        if i.evidence:
            out.append(f"      evidence: {'; '.join(i.evidence)}")
        if i.owner or i.meeting or i.notes:
            out.append(f"      board: owner {i.owner or '-'}, meeting {i.meeting or '-'}, notes {i.notes or '-'}")
    return out


# The Google Sheet: jason writes every column; the board edits status, owner, meeting, and notes there.

def to_rows(items: list[BoardItem]) -> list[list[str]]:
    rows = [list(COLUMNS)]
    for i in items:
        raw = _encode(i)
        raw["evidence"] = "; ".join(i.evidence)
        raw["session"] = agenda_session(i).value
        rows.append(["" if raw.get(c) is None else str(raw.get(c)) for c in COLUMNS])
    return rows


def sync_sheet(sheets: Any, spreadsheet_id: str, data_dir: Path, *, today: date | None = None, community: Any = None) -> dict[str, Any]:
    """The board action items register (``jason.tasks.registers``): the board's edits to status, owner, meeting, and
    notes are read back into the list and logged; jason then writes only its own columns, by item id, and appends new
    items. The Sheet is adopted into the registers the first time, and shaped (dropdowns, dates, protection) once."""
    from jason.tasks import registers as reg_task

    if community is None:
        from jason.community import mystique

        community = mystique()
    reg = reg_task.register(community, "board-items")
    reg_task.ensure(sheets, None, reg, data_dir, adopt=spreadsheet_id)
    reg_task.shape(sheets, reg, data_dir)

    def records() -> list[dict[str, Any]]:
        rows = to_rows(load(data_dir))
        return [dict(zip(rows[0], r)) for r in rows[1:]]

    def apply(edits: dict[str, dict[str, str]]) -> None:
        for item_id, changes in edits.items():
            if changes.get("status"):
                try:
                    ItemStatus(changes["status"])
                except ValueError:
                    changes.pop("status")
            if changes:
                try:
                    set_fields(data_dir, item_id, today=today, **changes)
                except KeyError:
                    continue

    return reg_task.sync(sheets, reg, data_dir, records, apply)


def task_body(item: BoardItem, sheet_id: str = "") -> dict[str, Any]:
    """The Google Task for one item: its title, the ask and standing in the notes with jason's marker, and its due date."""
    from jason.google.tasks import MARKER

    notes = [f"Ask: {item.ask}", f"Status: {item.status.value}; priority {item.priority.value}; {item.category.value}"]
    if item.owner:
        notes.append(f"Owner: {item.owner}")
    if item.meeting:
        notes.append(f"Meeting: {item.meeting}")
    if sheet_id:
        notes.append(f"Sheet: https://docs.google.com/spreadsheets/d/{sheet_id}")
    notes.append(f"{MARKER}{item.id}")
    body: dict[str, Any] = {"title": item.title, "notes": "\n".join(notes),
                            "status": "completed" if item.status is ItemStatus.CLOSED else "needsAction"}
    if item.due:
        body["due"] = f"{item.due.isoformat()}T00:00:00.000Z"
    return body


def sync_tasks(tasks: Any, data_dir: Path, *, sheet_id: str = "", today: date | None = None) -> dict[str, Any]:
    """Keep the board's items as one Google Tasks list: a task checked off there closes its item (recorded in the item's
    history), then every item is written back (a closed item's task is completed). Tasks jason no longer knows are
    reported, not deleted."""
    from jason.google.tasks import marker_of

    list_id = tasks.task_list(SHEET_TITLE)
    existing = {marker_of(t): t for t in tasks.tasks(list_id) if marker_of(t)}
    items = {i.id: i for i in load(data_dir)}
    closed_there = [k for k, t in existing.items()
                    if t.get("status") == "completed" and k in items and items[k].status is not ItemStatus.CLOSED]
    for k in closed_there:
        set_fields(data_dir, k, today=today, status=ItemStatus.CLOSED.value)
    counts = {"closedFromTasks": closed_there, "created": 0, "updated": 0, "unchanged": 0,
              "unknown": sorted(k for k in existing if k not in items)}
    for item in load(data_dir):
        body = task_body(item, sheet_id)
        task = existing.get(item.id)
        if task is None:
            if item.status is ItemStatus.CLOSED:
                continue
            tasks.insert(list_id, body)
            counts["created"] += 1
            continue
        changed = {k: v for k, v in body.items() if (task.get(k) or "")[:10 if k == "due" else None] != (v[:10] if k == "due" else v)}
        if "due" in task and "due" not in body:
            changed["due"] = None
        if changed:
            tasks.patch(list_id, task["id"], changed)
            counts["updated"] += 1
        else:
            counts["unchanged"] += 1
    return counts


def create_sheet(sheets: Any) -> str:
    """Create the board's action item Sheet (a new, private file in the signed-in Drive) and return its id."""
    created = sheets.create(SHEET_TITLE, sheet_titles=(TAB,))
    return created["spreadsheetId"]


__all__ = ["load", "save", "upsert", "set_fields", "agenda", "list_lines", "notice_date", "to_rows", "sync_sheet", "task_body", "sync_tasks",
           "create_sheet", "SHEET_TITLE"]
