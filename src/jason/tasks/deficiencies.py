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

Each change holds the store's lock (``jason.locks``), asks for ``by``, and writes only this file.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Iterable, Mapping

STORE = Path("life-safety") / "deficiencies.json"
LOCK = "life-safety-deficiencies"
UNPLACED = ""                    # the system key of a deficiency whose report no listed system could be named for


class Act(Enum):
    PROPOSED = "proposed"
    CONFIRMED = "confirmed"
    IMPAIRS = "impairs"
    NOT_IMPAIRS = "does not impair"
    CLEARED = "cleared"
    INSURER_TOLD = "insurer told"


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
    standing = "cleared" if cleared else "open" if confirmed else "proposed"
    impairing = bool(impairs and impairs["act"] == Act.IMPAIRS.value and not cleared)
    return {"standing": standing, "confirmed": confirmed, "impairs": (None if impairs is None else impairs["act"] == Act.IMPAIRS.value),
            "impairsBy": impairs, "cleared": cleared, "insurerTold": told,
            "impairmentOpen": impairing and bool(confirmed), "insurerNotTold": impairing and bool(confirmed) and told is None}


@_locked
def confirm(data_dir: Path | str, ident: str, *, by: str, now: str | None = None) -> dict[str, Any]:
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


@_locked
def set_impairs(data_dir: Path | str, ident: str, impairs: bool, *, by: str, now: str | None = None) -> dict[str, Any]:
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


# --- reading ----------------------------------------------------------------------------------------------------------

def view(data_dir: Path | str, *, system: str = "", detail: bool = True) -> dict[str, Any]:
    """The register as the Life safety screen reads it. ``detail`` False (a viewer who may not see the impairment and
    insurer record) gives the counts alone."""
    rows = [r for r in load(data_dir) if not system or r["system"] == system]
    states = [(r, state_of(r)) for r in rows]
    counts = {"proposed": sum(1 for _, s in states if s["standing"] == "proposed"),
              "open": sum(1 for _, s in states if s["standing"] == "open"),
              "cleared": sum(1 for _, s in states if s["standing"] == "cleared"),
              "impairments": sum(1 for _, s in states if s["impairmentOpen"]),
              "insurerNotTold": sum(1 for _, s in states if s["insurerNotTold"])}
    out: dict[str, Any] = {"found": True, "counts": counts, "detail": detail,
                           "command": "jason life-safety", "caveats": list(CAVEATS)}
    if detail:
        out["rows"] = [{**r, **s} for r, s in states]
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
)


def lines(result: Iterable[Mapping[str, Any]]) -> list[str]:
    out = []
    for r in result:
        s = state_of(r)
        flag = ("  IMPAIRS, insurer not told" if s["insurerNotTold"] else "  impairs" if s["impairmentOpen"] else "")
        where = f"{r['system'] or 'system not placed'}" + (f" ({', '.join(r['buildings'])})" if r["buildings"] else "")
        found = (r.get("report") or {}).get("day") or "?"
        out.append(f"{r['id']}  {s['standing']:<8} {where}; found {found}{flag}")
        what = " / ".join(p for p in (r["location"], r["device"], r["comment"]) if p)
        if what:
            out.append(f"    {what}")
        if s["cleared"]:
            c = s["cleared"]
            out.append(f"    cleared {c['on']} by {c['kind']} {c['record']} (recorded by {c['by']})")
    return out


__all__ = ["Act", "CAVEATS", "CLEARED_BY", "ClearedBy", "STORE", "clear", "confirm", "deficiency_id", "insurer_told", "lines",
           "load", "propose", "set_impairs", "state_of", "view"]
