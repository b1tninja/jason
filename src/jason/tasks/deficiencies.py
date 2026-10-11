"""The deficiency register: each deficiency an inspection or test report found, and what has been done about it.

A report that lists an open deficiency (``jason.community.models.legal_inspections``) is read into the library. This
register turns each one into a row a person confirms, then records, in order and with their name, whether it impairs a
safeguard, what cleared it, and whether the insurer was told (docs/console/screens/life-safety.md, "Data" and "Actions").
It is ``data/life-safety/deficiencies.json``.

- **Proposed, then confirmed.** ``propose`` adds a row for each open deficiency a reading lists, once (the id is a hash of
  the report, the location, the device, and the comment, so a second run adds nothing). A proposed row is not yet a
  finding: ``confirm`` is a person's act. A report that counts open deficiencies but lists none gets one row that says
  so. A confidential reading is not read, and a resolved deficiency is the report's own history, not a row.
- **Append only.** A row is never edited or deleted. Each act is appended to the row's ``acts`` with who and when, and the
  row's state is read from them, the latest word on each question winning. The impairment record and the insurer
  correspondence may bear on a claim, so nothing here can be unsaid: a correction is a later act.
- **A deficiency is cleared only by a linked record.** ``clear`` takes the id of a record in the library (an invoice's
  line items, an AES 10, a later passing report) and a kind. An invoice's subject line is not one, and free text is not
  accepted. A later passing report must read passed with nothing open. A row not yet confirmed cannot be cleared.
- **The insurer.** ``insurer_told`` records the day and the record of what was sent (an email or a letter to the agent) by
  reference. jason contacts no insurer and sends nothing; this records what a person did.
- **Impairment** is a person's reading of whether the deficiency impairs a scheduled safeguard; it is ``None`` until a
  person says, never inferred.

- **Severity and deadline** are a person's words too. ``set_severity`` records urgent, high, or normal (the board items'
  own priorities); ``set_deadline`` records a date with the basis word of who set it (the insurer, an authority, a
  document, a vendor, or a person) and, if there is one, the record. jason never infers a severity and never computes a
  legal deadline. The latest word on each wins.
- **A confirmed deficiency is a board item.** ``sync_board_items`` builds (``board_item_of``) and refreshes a board item
  for each confirmed deficiency, proposed for the next agenda, after every act. The item's priority is a person's
  severity when one is set, else jason's proposal (``proposed_priority``), labeled so in the item's summary. The
  deadline is its due date. The board's own fields (status, owner, meeting, notes) are never overwritten, and a cleared
  deficiency closes nothing: the board closes its items. A failure to write the item never undoes the act: the act's
  result carries ``boardItem: {ok: false, why}``.

Each change holds the store's lock (``jason.locks``), asks for ``by``, and writes only this file; the board item is
written after the lock is let go.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Iterable, Mapping

from jason.community.board_items import PRIORITY_ORDER, BoardItem, ItemCategory, Priority

STORE = Path("life-safety") / "deficiencies.json"
LOCK = "life-safety-deficiencies"
UNPLACED = ""                    # the system key of a deficiency whose report no listed system could be named for
DEADLINE_WINDOW_DAYS = 14        # jason's default window, not the law's: a deadline this near (or past) raises the proposed priority
DEADLINE_PAST_LIMIT_DAYS = 365   # a deadline more than a year past is refused as a likely typo; an overdue one within it is real
ITEM_PREFIX = "life-safety-"     # a board item's id is this and the deficiency's id
ITEM_SOURCE = "life-safety register"
ITEM_ASK = "Decide the repair, the vendor, and the date"


class Act(Enum):
    PROPOSED = "proposed"
    CONFIRMED = "confirmed"
    IMPAIRS = "impairs"
    NOT_IMPAIRS = "does not impair"
    CLEARED = "cleared"
    INSURER_TOLD = "insurer told"
    SEVERITY = "severity"
    DEADLINE = "deadline"


class DeadlineBasis(Enum):
    """Who set a deadline a person recorded. jason sets none."""

    INSURER = "insurer"
    AUTHORITY = "authority"
    DOCUMENTS = "documents"
    VENDOR = "vendor"
    PERSON = "person"


DEADLINE_BASES = tuple(b.value for b in DeadlineBasis)
SEVERITIES = tuple(p.value for p in Priority)


class ClearedBy(Enum):
    """What kind of record clears a deficiency. A subject line is none of them."""

    INVOICE_LINES = "invoice line items"
    AES_10 = "AES 10"
    PASSING_REPORT = "later passing report"
    OTHER = "other record"


CLEARED_BY = tuple(k.value for k in ClearedBy)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _path(data_dir: Path | str) -> Path:
    return Path(data_dir) / STORE


def load(data_dir: Path | str) -> list[dict[str, Any]]:
    path = _path(data_dir)
    if not path.is_file():
        return []
    raw = json.loads(path.read_text(encoding="utf-8")).get("deficiencies", [])
    return [dict(r) for r in raw if isinstance(r, dict)]


def _save(data_dir: Path | str, rows: list[dict[str, Any]]) -> None:
    path = _path(data_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps({"savedAt": _now(), "deficiencies": rows}, indent=1), encoding="utf-8")
    tmp.replace(path)


def _locked(fn):
    import functools

    from jason.locks import Resource, hold

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        with hold(Resource.STORE, LOCK, timeout=60, purpose=f"deficiency register: {fn.__name__}"):
            return fn(*args, **kwargs)
    return wrapper


def _syncs(fn):
    """Outside the register's lock (``_locked`` is inside this), refresh the act's board item. A failure there never
    undoes the act already recorded: the row returned carries ``boardItem``, ``{ok: true, ...}`` or ``{ok: false, why}``."""
    import functools

    @functools.wraps(fn)
    def wrapper(data_dir, ident, *args, **kwargs):
        row = fn(data_dir, ident, *args, **kwargs)
        try:
            row["boardItem"] = sync_board_items(data_dir, ident=ident, today=kwargs.get("today"))
        except Exception as exc:  # noqa: BLE001 - the act stands; the person is told the item was not written
            row["boardItem"] = {"ok": False, "why": f"{type(exc).__name__}: {exc}"}
        return row
    return wrapper


def deficiency_id(report_id: str, location: str, device: str, comment: str) -> str:
    key = "|".join(" ".join(str(p).lower().split()) for p in (report_id, location, device, comment))
    return "def-" + hashlib.sha1(key.encode("utf-8")).hexdigest()[:10]


def _library(data_dir: Path | str) -> tuple[dict[str, Any], ...]:
    from jason.tasks.library import load as library

    try:
        return tuple(library(Path(data_dir)))
    except Exception:  # noqa: BLE001 - an unreadable library is no library
        return ()


def _items(fields: Mapping[str, Any]) -> list[dict[str, str]]:
    """The open deficiencies a reading lists: location, device, comment. A resolved one is the report's history."""
    out = []
    for d in fields.get("deficiencies") or ():
        if isinstance(d, Mapping):
            item = {k: str(d.get(k) or "").strip() for k in ("location", "device", "comment", "status")}
        elif isinstance(d, (list, tuple)) and len(d) >= 4:
            item = dict(zip(("location", "device", "comment", "status"), (str(x or "").strip() for x in d)))
        else:
            item = {"location": "", "device": "", "comment": str(d).strip(), "status": "open"}
        if item["status"].lower() in ("", "open"):
            out.append(item)
    return out


def _mask(text: str) -> str:
    from jason.approvals.audit import mask

    return str(mask(text))


@_locked
def propose(data_dir: Path | str, community: Any, *, now: str | None = None) -> list[dict[str, Any]]:
    """Add a proposed row for each open deficiency the library's inspection readings list that the register does not
    hold. Returns the rows added."""
    from jason.tasks.inspections import Report, place

    systems = tuple(community.life_safety_systems())
    rows = load(data_dir)
    have = {r["id"] for r in rows}
    at = now or _now()
    added = []
    for reading in _library(data_dir):
        fields = reading.get("fields") or {}
        if reading.get("confidential") or reading.get("kind") != "inspection_report" or not fields:
            continue
        report = Report.of(reading)
        items = _items(fields)
        if not items and report.open_deficiencies:
            items = [{"location": "", "device": "", "status": "open",
                      "comment": f"the report counts {report.open_deficiencies} open deficiencies; its items were not read"}]
        if not items:
            continue
        system, slots, _ = place(report, systems)
        for item in items:
            ident = deficiency_id(report.id, item["location"], item["device"], item["comment"])
            if ident in have:
                continue
            row = {"id": ident, "system": system.key if system else UNPLACED, "buildings": list(slots or report.buildings),
                   "report": {"id": report.id, "name": report.name, "day": report.day.isoformat() if report.day else None,
                              "where": report.where},
                   "location": _mask(item["location"]), "device": _mask(item["device"]), "comment": _mask(item["comment"]),
                   "source": "proposed from a report's reading",
                   "acts": [{"act": Act.PROPOSED.value, "at": at}]}
            rows.append(row)
            added.append(row)
            have.add(ident)
    if added:
        _save(data_dir, rows)
    return added


# --- a person's acts --------------------------------------------------------------------------------------------------

def _need(by: str) -> str:
    by = (by or "").strip()
    if not by:
        raise ValueError("name who is recording this (--by NAME)")
    return by


def _day(value: str | date | None, label: str, today: date | None = None) -> str:
    try:
        day = value if isinstance(value, date) else date.fromisoformat(str(value or "").strip())
    except ValueError:
        raise ValueError(f"{label}: give a date as YYYY-MM-DD") from None
    if day > (today or date.today()):
        raise ValueError(f"{label}: {day} is in the future")
    return day.isoformat()


def _deadline_day(value: str | date | None, today: date | None = None) -> str:
    """A deadline a person records: a date, in the future or past. A past one within a year is an overdue deadline, which
    is real; one more than a year back is refused as likely a typo."""
    try:
        day = value if isinstance(value, date) else date.fromisoformat(str(value or "").strip())
    except ValueError:
        raise ValueError("date: give the deadline as YYYY-MM-DD") from None
    now = today or date.today()
    if day < now - timedelta(days=DEADLINE_PAST_LIMIT_DAYS):
        raise ValueError(f"date: {day} is more than a year in the past; check it (an overdue deadline within a year is accepted)")
    return day.isoformat()


def _ref(record: str, label: str) -> str:
    record = (record or "").strip()
    if not record or any(ch.isspace() for ch in record):
        raise ValueError(f"{label}: give the record's id (a library id such as drive-… or gmail:ID), not words")
    return record


def _find(rows: list[dict[str, Any]], ident: str) -> dict[str, Any]:
    for r in rows:
        if r["id"] == ident:
            return r
    raise ValueError(f"no deficiency {ident!r} in the register (`jason life-safety --list` lists them)")


def state_of(row: Mapping[str, Any]) -> dict[str, Any]:
    """What the acts say, the latest word on each question winning. ``impairs`` is None until a person says."""
    acts = row.get("acts") or []
    last = lambda *names: next((a for a in reversed(acts) if a["act"] in names), None)  # noqa: E731
    confirmed = last(Act.CONFIRMED.value)
    impairs = last(Act.IMPAIRS.value, Act.NOT_IMPAIRS.value)
    cleared = last(Act.CLEARED.value)
    told = last(Act.INSURER_TOLD.value)
    severity = last(Act.SEVERITY.value)
    deadline = last(Act.DEADLINE.value)
    standing = "cleared" if cleared else "open" if confirmed else "proposed"
    impairing = bool(impairs and impairs["act"] == Act.IMPAIRS.value and not cleared)
    return {"standing": standing, "confirmed": confirmed, "impairs": (None if impairs is None else impairs["act"] == Act.IMPAIRS.value),
            "impairsBy": impairs, "cleared": cleared, "insurerTold": told,
            "severity": severity["value"] if severity else None, "severityBy": severity,
            "deadline": deadline["date"] if deadline else None, "deadlineBy": deadline,
            "impairmentOpen": impairing and bool(confirmed), "insurerNotTold": impairing and bool(confirmed) and told is None}


# --- the priority a board item carries --------------------------------------------------------------------------------

def _step_up(priority: Priority) -> Priority:
    return {Priority.NORMAL: Priority.HIGH, Priority.HIGH: Priority.URGENT}.get(priority, priority)


def proposed_priority(state: Mapping[str, Any], today: date | None = None) -> tuple[Priority, str]:
    """jason's PROPOSED priority for a deficiency's board item, and why. It is jason's proposal, not a legal standard, and a
    person's severity replaces it (``priority_of``).

    - urgent: the deficiency impairs a safeguard and no record shows the insurer was told;
    - high: it impairs a safeguard;
    - otherwise normal.

    A deadline a person recorded that is past, or within ``DEADLINE_WINDOW_DAYS`` (jason's default window, not the law's),
    raises it one step (normal to high, high to urgent). A cleared deficiency has no deadline pressing."""
    if state.get("insurerNotTold"):
        base, why = Priority.URGENT, "it impairs a safeguard and no record shows the insurer was told"
    elif state.get("impairmentOpen"):
        base, why = Priority.HIGH, "it impairs a safeguard"
    else:
        base, why = Priority.NORMAL, "no impairment of a safeguard is recorded"
    deadline = state.get("deadline")
    if deadline and not state.get("cleared"):
        left = (date.fromisoformat(deadline) - (today or date.today())).days
        if left <= DEADLINE_WINDOW_DAYS:
            raised = _step_up(base)
            when = f"{-left} days past" if left < 0 else "today" if left == 0 else f"in {left} days"
            return raised, (f"{why}; the deadline {deadline} is {when}, within jason's default window of "
                            f"{DEADLINE_WINDOW_DAYS} days (not the law's), which raises it one step")
    return base, why


def priority_of(state: Mapping[str, Any], today: date | None = None) -> dict[str, Any]:
    """The priority a deficiency's board item carries: a person's severity when one is set, else jason's proposal.
    ``proposed`` says which."""
    if state.get("severity"):
        by = state.get("severityBy") or {}
        return {"value": Priority(state["severity"]), "proposed": False,
                "why": f"set by {by.get('by', 'a person')} on {str(by.get('at', ''))[:10]}".strip()}
    value, why = proposed_priority(state, today)
    return {"value": value, "proposed": True, "why": why}


@_syncs
@_locked
def confirm(data_dir: Path | str, ident: str, *, by: str, now: str | None = None, today: date | None = None) -> dict[str, Any]:
    by = _need(by)
    rows = load(data_dir)
    row = _find(rows, ident)
    if state_of(row)["confirmed"]:
        return row
    row["acts"].append({"act": Act.CONFIRMED.value, "by": by, "at": now or _now()})
    _save(data_dir, rows)
    return row


def _confirmed(row: Mapping[str, Any], what: str) -> None:
    if not state_of(row)["confirmed"]:
        raise ValueError(f"{row['id']} is only proposed: confirm it first (`jason life-safety --confirm {row['id']} --by NAME`) "
                         f"before recording {what}")


@_syncs
@_locked
def set_impairs(data_dir: Path | str, ident: str, impairs: bool, *, by: str, now: str | None = None,
                today: date | None = None) -> dict[str, Any]:
    by = _need(by)
    rows = load(data_dir)
    row = _find(rows, ident)
    _confirmed(row, "whether it impairs a safeguard")
    row["acts"].append({"act": (Act.IMPAIRS if impairs else Act.NOT_IMPAIRS).value, "by": by, "at": now or _now()})
    _save(data_dir, rows)
    return row


def _passing(reading: Mapping[str, Any]) -> bool:
    from jason.tasks.inspections import Report

    report = Report.of(reading)
    return report.result == "passed" and not report.reports_deficiencies


@_syncs
@_locked
def clear(data_dir: Path | str, ident: str, *, record: str, kind: str, on: str, by: str, now: str | None = None,
          today: date | None = None) -> dict[str, Any]:
    """Link the record that cleared a deficiency. ``record`` must be a record in the library; a later passing report must
    read passed with nothing open and be dated after the report that found the deficiency."""
    by = _need(by)
    if kind not in CLEARED_BY:
        raise ValueError(f"kind is one of: {'; '.join(CLEARED_BY)} (an invoice's subject line is not a record that clears)")
    ref = _ref(record, "record")
    day = _day(on, "on", today)
    rows = load(data_dir)
    row = _find(rows, ident)
    _confirmed(row, "what cleared it")
    reading = next((r for r in _library(data_dir) if str(r.get("id")) == ref), None)
    if reading is None:
        raise ValueError(f"record {ref!r} is not in the library: file it first, then link it")
    if kind == ClearedBy.PASSING_REPORT.value:
        if not _passing(reading):
            raise ValueError(f"{ref} does not read as a passing report with no open deficiency")
        found = (row.get("report") or {}).get("day")
        later = (reading.get("fields") or {}).get("inspection_date")
        if found and later and str(later) <= found:
            raise ValueError(f"{ref} is dated {later}, not after the report that found it ({found})")
    row["acts"].append({"act": Act.CLEARED.value, "by": by, "at": now or _now(), "record": ref, "kind": kind, "on": day})
    _save(data_dir, rows)
    return row


@_syncs
@_locked
def insurer_told(data_dir: Path | str, ident: str, *, record: str, on: str, by: str, now: str | None = None,
                 today: date | None = None) -> dict[str, Any]:
    """Record that a person told the insurer: the day, and the record of what was sent, by reference. The reference is
    kept as given (a message or letter is not always in the library); ``inLibrary`` says whether it is."""
    by = _need(by)
    ref = _ref(record, "record")
    day = _day(on, "on", today)
    rows = load(data_dir)
    row = _find(rows, ident)
    _confirmed(row, "that the insurer was told")
    known = any(str(r.get("id")) == ref for r in _library(data_dir))
    row["acts"].append({"act": Act.INSURER_TOLD.value, "by": by, "at": now or _now(), "record": ref, "on": day,
                        "inLibrary": known})
    _save(data_dir, rows)
    return row


@_syncs
@_locked
def set_severity(data_dir: Path | str, ident: str, value: str, *, by: str, now: str | None = None,
                 today: date | None = None) -> dict[str, Any]:
    """Record a person's severity: urgent, high, or normal (the board items' own priorities). It is the person's reading,
    never inferred; it replaces jason's proposed priority, and the latest word wins."""
    by = _need(by)
    if value not in SEVERITIES:
        raise ValueError(f"value is one of: {', '.join(SEVERITIES)}")
    rows = load(data_dir)
    row = _find(rows, ident)
    _confirmed(row, "a severity")
    row["acts"].append({"act": Act.SEVERITY.value, "by": by, "at": now or _now(), "value": value})
    _save(data_dir, rows)
    return row


@_syncs
@_locked
def set_deadline(data_dir: Path | str, ident: str, *, day: str, basis: str, record: str = "", by: str,
                 now: str | None = None, today: date | None = None) -> dict[str, Any]:
    """Record a deadline a person knows, with who set it (``basis``: the insurer, an authority, the documents, a vendor, or
    the person) and, if there is one, the record it comes from. jason computes or invents none. A past date within a year is
    an overdue deadline and is accepted. The latest word wins; it becomes the board item's due date."""
    by = _need(by)
    if basis not in DEADLINE_BASES:
        raise ValueError(f"basis is one of: {', '.join(DEADLINE_BASES)} (who set the deadline)")
    ref = _ref(record, "record") if (record or "").strip() else ""
    on = _deadline_day(day, today)
    rows = load(data_dir)
    row = _find(rows, ident)
    _confirmed(row, "a deadline")
    act = {"act": Act.DEADLINE.value, "by": by, "at": now or _now(), "date": on, "basis": basis}
    if ref:
        act["record"] = ref
    row["acts"].append(act)
    _save(data_dir, rows)
    return row


# --- the board item ---------------------------------------------------------------------------------------------------

def item_id(ident: str) -> str:
    return ITEM_PREFIX + ident


def _system_name(community: Any, key: str) -> str:
    for s in tuple(getattr(community, "life_safety_systems", lambda: ())() or ()):
        if s.key == key:
            return s.name
    return key or "a system not placed"


def _on(act: Mapping[str, Any] | None) -> str:
    return str((act or {}).get("at") or "")[:10]


def board_item_of(row: Mapping[str, Any], state: Mapping[str, Any], community: Any = None, *,
                  today: date | None = None) -> BoardItem:
    """The board item for a confirmed deficiency, from the register alone (no reading or writing). ``community`` only
    names the system in words. The summary is what the report and the people who recorded say, with a priority line that
    says whether the priority is jason's proposal or a person's word; ``authority`` and ``evidence`` cite only what the
    register holds (the report); the deadline a person recorded is ``due``. The category is SAFETY (fire, life safety,
    inspections)."""
    report = row.get("report") or {}
    system = _system_name(community, row.get("system", ""))
    device = (row.get("device") or "").strip()
    title = f"Life safety deficiency: {device or 'a device not named in the report'} ({system})"
    what = " / ".join(p for p in (row.get("location"), row.get("device"), row.get("comment")) if p)
    found = report.get("day") or "a date not read"
    lines = [f"The inspection report {report.get('name') or 'on file'} ({found}) lists an open deficiency: {what or 'no detail was read'}.",
             f"Confirmed by {(state['confirmed'] or {}).get('by', 'a person')} on {_on(state['confirmed'])}."]
    if state["impairs"] is True:
        lines.append(f"Recorded as impairing a scheduled safeguard ({state['impairsBy'].get('by')}, {_on(state['impairsBy'])}).")
    elif state["impairs"] is False:
        lines.append(f"Recorded as not impairing a scheduled safeguard ({state['impairsBy'].get('by')}, {_on(state['impairsBy'])}).")
    else:
        lines.append("Whether it impairs a scheduled safeguard is not yet recorded.")
    told = state["insurerTold"]
    if told:
        lines.append(f"The insurer was told on {told['on']} ({told['by']}; record {told['record']}).")
    elif state["impairs"] is True:
        lines.append("No record shows the insurer was told.")
    dl = state["deadlineBy"]
    if dl:
        lines.append(f"Deadline {dl['date']}, set by {dl['basis']} (recorded by {dl['by']}"
                     + (f"; record {dl['record']}" if dl.get("record") else "") + ").")
    p = priority_of(state, today)
    if p["proposed"]:
        lines.append(f"priority proposed: {p['value'].value} ({p['why']}). This is jason's proposal, not a legal standard; "
                     "a severity a person records replaces it.")
    else:
        lines.append(f"priority: {p['value'].value}, {p['why']} (a person's word, not jason's proposal).")
    if state["cleared"]:
        c = state["cleared"]
        lines.append(f"cleared by {c['record']} on {c['on']} ({c['kind']}; recorded by {c['by']}). jason closes nothing: "
                     "the board closes this item.")
    where = report.get("where") or "library"
    evidence = [f"{where}: {report['name']}"] if report.get("name") else []
    evidence.append("jason life-safety --list")
    authority = f"Inspection report: {report.get('name') or report.get('id') or 'on file'}" + (f", {report['day']}" if report.get("day") else "")
    if dl and dl.get("record"):
        authority += f"; deadline per {dl['basis']}, record {dl['record']}"
    return BoardItem(item_id(row["id"]), title=title, summary=" ".join(lines), ask=ITEM_ASK, category=ItemCategory.SAFETY,
                     priority=p["value"], authority=authority, evidence=tuple(evidence),
                     due=date.fromisoformat(dl["date"]) if dl else None, source=ITEM_SOURCE)


def _active_community() -> Any:
    try:
        from jason.community import community

        return community()
    except Exception:  # noqa: BLE001 - no profile: the system is named by its key
        return None


def sync_board_items(data_dir: Path | str, *, ident: str | None = None, community: Any = None,
                     today: date | None = None) -> dict[str, Any]:
    """Build and refresh the board item of each confirmed deficiency (of ``ident`` only, when given). A new item is
    proposed for the next agenda; an existing one has jason's fields refreshed and the board's kept. A cleared deficiency
    with no item yet gets none, and one with an item is only refreshed: nothing is closed here. Call it without the
    register's lock held. Returns ``{ok: True, items: [...], added: [...]}``; a failure raises, for the caller to report."""
    from jason.tasks import board_items

    day = today or date.today()
    comm = community if community is not None else _active_community()
    have = {i.id for i in board_items.load(Path(data_dir))}
    new: list[BoardItem] = []
    old: list[BoardItem] = []
    for row in load(data_dir):
        if ident and row["id"] != ident:
            continue
        state = state_of(row)
        if not state["confirmed"]:
            continue
        item = board_item_of(row, state, comm, today=day)
        if item.id in have:
            old.append(item)
        elif not state["cleared"]:
            new.append(item)
    if new:
        board_items.propose(Path(data_dir), new, today=day)
    if old:
        board_items.upsert(Path(data_dir), old, today=day)
    return {"ok": True, "items": [i.id for i in new + old], "added": [i.id for i in new]}


# --- reading ----------------------------------------------------------------------------------------------------------

def _standing_rank(s: Mapping[str, Any]) -> int:
    return {"open": 0, "proposed": 1, "cleared": 2}[s["standing"]]


def view(data_dir: Path | str, *, system: str = "", detail: bool = True, today: date | None = None) -> dict[str, Any]:
    """The register as the Life safety screen reads it. ``detail`` False (a viewer who may not see the impairment and
    insurer record) gives the counts alone, with the counts that reveal an impairment (``impairments``,
    ``insurerNotTold``, ``urgent``) null, never a bare zero.

    Each detail row also carries ``severity`` (a person's word, or None), ``deadline`` (a day a person recorded, or None),
    ``priority`` (``value``, ``proposed``, ``why``), and ``boardItem`` (its id and status, or None). Rows are sorted open
    first, then by priority, deadline ascending (none last), and the date found."""
    day = today or date.today()
    rows = [r for r in load(data_dir) if not system or r["system"] == system]
    states = [(r, state_of(r), priority_of(state_of(r), day)) for r in rows]
    open_ = [(r, s, p) for r, s, p in states if s["standing"] == "open"]
    full = {"proposed": sum(1 for _, s, _ in states if s["standing"] == "proposed"),
            "open": len(open_),
            "cleared": sum(1 for _, s, _ in states if s["standing"] == "cleared"),
            "impairments": sum(1 for _, s, _ in states if s["impairmentOpen"]),
            "insurerNotTold": sum(1 for _, s, _ in states if s["insurerNotTold"]),
            "urgent": sum(1 for _, _, p in open_ if p["value"] is Priority.URGENT),
            "overdueDeadlines": sum(1 for _, s, _ in open_ if s["deadline"] and s["deadline"] < day.isoformat())}
    counts = full if detail else {**full, "impairments": None, "insurerNotTold": None, "urgent": None}
    out: dict[str, Any] = {"found": True, "counts": counts, "detail": detail,
                           "command": "jason life-safety", "caveats": list(CAVEATS)}
    if detail:
        try:
            from jason.tasks import board_items

            items = {i.id: i for i in board_items.load(Path(data_dir))}
        except Exception:  # noqa: BLE001 - an unreadable board list leaves the item column empty
            items = {}

        def shown(r, s, p):
            item = items.get(item_id(r["id"]))
            return {**r, **s, "priority": {"value": p["value"].value, "proposed": p["proposed"], "why": p["why"]},
                    "boardItem": {"id": item.id, "status": item.status.value} if item else None}

        ordered = sorted(states, key=lambda t: (_standing_rank(t[1]), PRIORITY_ORDER[t[2]["value"]], t[1]["deadline"] is None,
                                                t[1]["deadline"] or "", (t[0].get("report") or {}).get("day") or "9999", t[0]["id"]))
        out["rows"] = [shown(*t) for t in ordered]
    else:
        out["rows"] = []
        out["held"] = ("Which deficiencies impair a safeguard, what cleared each, and whether the insurer was told may bear on "
                       "a claim: they open for the offices that open members' submissions (P2).")
    return out


CAVEATS = (
    "A proposed row is a report's reading, not a finding, until a person confirms it.",
    "Whether a deficiency impairs a safeguard is a person's reading; jason never infers it.",
    "A deficiency is cleared only by a linked record, never by a subject line. jason contacts no insurer: \"insurer told\" "
    "records what a person did.",
    "The register is append only: a correction is a later act, with who and when.",
    "A severity and a deadline are a person's words. Until a person sets a severity, the priority is jason's proposal "
    "(urgent if it impairs a safeguard and the insurer is not shown told; high if it impairs one; a near or past "
    "deadline raises it a step), not a legal standard. jason computes no legal deadline.",
    "Each confirmed deficiency is a board item proposed for the next agenda; the board's status, owner, meeting, and "
    "notes on it are never overwritten, and a cleared deficiency closes nothing.",
)


def lines(result: Iterable[Mapping[str, Any]], today: date | None = None) -> list[str]:
    out = []
    for r in result:
        s = state_of(r)
        flag = ("  IMPAIRS, insurer not told" if s["insurerNotTold"] else "  impairs" if s["impairmentOpen"] else "")
        if s["confirmed"] and not s["cleared"]:
            p = priority_of(s, today)
            flag += f"  {p['value'].value}{' (proposed)' if p['proposed'] else ''}"
        if s["deadline"]:
            flag += f"  deadline {s['deadline']} ({s['deadlineBy']['basis']})"
        where = f"{r['system'] or 'system not placed'}" + (f" ({', '.join(r['buildings'])})" if r["buildings"] else "")
        found = (r.get("report") or {}).get("day") or "?"
        out.append(f"{r['id']}  {s['standing']:<8} {where}; found {found}{flag}")
        what = " / ".join(p for p in (r["location"], r["device"], r["comment"]) if p)
        if what:
            out.append(f"    {what}")
        if s["cleared"]:
            c = s["cleared"]
            out.append(f"    cleared {c['on']} by {c['kind']} {c['record']} (recorded by {c['by']})")
        note = r.get("boardItem")
        if note is not None:
            out.append("    board item: " + (", ".join(note.get("items") or ["none"]) if note.get("ok")
                                              else f"NOT written ({note.get('why')}); the act is recorded"))
    return out


__all__ = ["Act", "CAVEATS", "CLEARED_BY", "ClearedBy", "DEADLINE_BASES", "DEADLINE_WINDOW_DAYS", "DeadlineBasis", "SEVERITIES",
           "STORE", "board_item_of", "clear", "confirm", "deficiency_id", "insurer_told", "item_id", "lines", "load",
           "priority_of", "propose", "proposed_priority", "set_deadline", "set_impairs", "set_severity", "state_of",
           "sync_board_items", "view"]
