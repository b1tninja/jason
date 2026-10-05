"""The board's roster as records kept as it changes: each change of office the board made, and each seat's term.

A change of office is the board's act, recorded in the minutes. A person then answers onboarding's ``board-roster``
question in the form below, a second person confirms it (the question has stakes), and ``jason onboard --apply``
appends it to the profile's officers topic (``data/spec/<profile>/officers.json``, ``jason.community.private``) as a row
with the date the board acted and the minutes that record it. Nothing in the topic is rewritten: ``in_force`` reads it so
that, for each office, the row the board acted on last is the one in force (or the office is vacant, when that row says
so). A term is recorded the same way: the ``election-status`` question's answer is appended to the terms topic
(``data/spec/<profile>/terms.json``), which ``terms_of`` reads into ``Term`` records.

The forms (fields separated by ";", several entries by "|"):

- a change of office (``CHANGE_FORM``): the office; the person who holds it now, or "vacant"; the date the board acted
  (YYYY-MM-DD); the minutes that record it;
- a term (``TERM_FORM``): the seat ("director", or the office); the person; the start (YYYY-MM-DD); the end (YYYY-MM-DD,
  or "at the pleasure of the board"); the election record (the minutes, or the inspector of elections' report); and the
  provision that sets the term.

jason invents no date and no threshold: a term has ended only when its recorded end is past (``Term.ended``). A
malformed answer is refused when it is given (``form_problem``) and again when applied (``rows_for``).
"""

from __future__ import annotations

from datetime import date
from typing import Any, Callable, Iterable

from jason.community.base import OfficerRole, SeatKind, Term

OFFICES = (OfficerRole.PRESIDENT, OfficerRole.VICE_PRESIDENT, OfficerRole.SECRETARY, OfficerRole.TREASURER)
PLEASURE = "at the pleasure of the board"
VACANT = ("vacant", "none", "no one")
CHANGE_FORM = "OFFICE; PERSON (or vacant); YYYY-MM-DD; MINUTES"
TERM_FORM = "SEAT; PERSON; START; END (or at the pleasure of the board); ELECTION RECORD; PROVISION"
OFFICERS_TOPIC = "officers"
TERMS_TOPIC = "terms"


class FormError(ValueError):
    """An answer not in its question's form: nothing is recorded."""


def _date(text: str, what: str) -> date:
    try:
        return date.fromisoformat(text.strip())
    except ValueError:
        raise FormError(f"{what} {text.strip()!r} is not a date (YYYY-MM-DD)") from None


def _office(text: str) -> OfficerRole:
    try:
        role = OfficerRole(text.strip().lower())
    except ValueError:
        role = None
    if role not in OFFICES:
        raise FormError(f"{text.strip()!r} is not an office ({', '.join(o.value for o in OFFICES)})")
    return role


def _entries(text: str, count: tuple[int, ...], form: str) -> list[list[str]]:
    out = []
    for entry in (e for e in str(text or "").split("|") if e.strip()):
        fields = [f.strip() for f in entry.split(";")]
        if len(fields) not in count:
            raise FormError(f"{entry.strip()!r} has {len(fields)} fields; the form is {form}")
        out.append(fields)
    if not out:
        raise FormError(f"no entry; the form is {form}")
    return out


def change_rows(text: str) -> list[dict[str, Any]]:
    """The officers topic rows a ``board-roster`` answer records: one per change of office."""
    rows = []
    for office, person, acted, source in _entries(text, (4,), CHANGE_FORM):
        role = _office(office)
        if not person:
            raise FormError(f"no person for {role.value}: name who holds it now, or say vacant")
        if not source:
            raise FormError(f"no minutes for {role.value}: name the minutes that record the board's act")
        row: dict[str, Any] = {"role": role.value, "name": "" if person.lower() in VACANT else person,
                               "acted": _date(acted, "the date the board acted").isoformat(), "source": source}
        if not row["name"]:
            row["vacant"] = True
        rows.append(row)
    return rows


def term_rows(text: str) -> list[dict[str, Any]]:
    """The terms topic rows an ``election-status`` answer records: one per term."""
    rows = []
    for fields in _entries(text, (5, 6), TERM_FORM):
        seat, person, start, end, source = fields[:5]
        provision = fields[5] if len(fields) == 6 else ""
        if seat.strip().lower() == SeatKind.DIRECTOR.value:
            kind, office = SeatKind.DIRECTOR, None
        else:
            kind, office = SeatKind.OFFICER, _office(seat)
        if not person:
            raise FormError("no person: name who holds the seat")
        if not source:
            raise FormError(f"no election record for {person}: name the minutes or the inspector's report")
        began = _date(start, "the start")
        ends = None if end.strip().lower() in (PLEASURE, "none", "") else _date(end, "the end")
        if ends is not None and ends < began:
            raise FormError(f"the end {ends.isoformat()} is before the start {began.isoformat()}")
        rows.append({"person": person, "seat": kind.value, "office": office.value if office else "",
                     "start": began.isoformat(), "end": ends.isoformat() if ends else None, "source": source,
                     "provision": provision})
    return rows


FORMS: dict[str, Callable[[str], list[dict[str, Any]]]] = {OFFICERS_TOPIC: change_rows, TERMS_TOPIC: term_rows}


def rows_for(topic: str, text: str) -> list[dict[str, Any]]:
    """The rows an answer appends to ``topic``; a topic with no form keeps the answer's words as one row."""
    form = FORMS.get(topic)
    return form(text) if form is not None else [{"answer": str(text or "").strip()}]


def form_problem(topic: str, text: str) -> str:
    """Why an answer for ``topic`` is not in its form ("" when it is, or when the topic has no form)."""
    try:
        rows_for(topic, text)
    except FormError as exc:
        return str(exc)
    return ""


def _roles(row: dict[str, Any]) -> list[str]:
    given = row.get("role", "")
    return [str(r).strip().lower() for r in (given if isinstance(given, list) else [given]) if str(r).strip()]


def in_force(rows: Iterable[Any]) -> list[tuple[str, dict[str, Any]]]:
    """Each (role, row) of an officers topic still in force. For an office, once any row records the board's act
    (``acted``), the one acted on last holds it (a later row on the same day wins) and the rest are superseded; a
    ``vacant`` row leaves no one. A role no change names keeps every row, as written."""
    pairs = [(role, n, row) for n, row in enumerate(r for r in rows if isinstance(r, dict)) for role in _roles(row)]
    offices = {o.value for o in OFFICES}
    latest: dict[str, tuple[str, int]] = {}
    for role, n, row in pairs:
        acted = str(row.get("acted") or "")
        if role in offices and acted and (role not in latest or (acted, n) >= latest[role]):
            latest[role] = (acted, n)
    out = []
    for role, n, row in pairs:
        if role in latest and (str(row.get("acted") or ""), n) != latest[role]:
            continue
        if row.get("vacant") or not str(row.get("name", "")).strip():
            continue
        out.append((role, row))
    return out


def terms_of(rows: Any) -> tuple[Term, ...]:
    """The terms topic's rows as ``Term`` records; a row without a person, a seat, or a start date is skipped (a
    malformed row is not a term), and a missing topic is none."""
    out = []
    for row in rows if isinstance(rows, list) else ():
        if not isinstance(row, dict) or not str(row.get("person") or "").strip():
            continue
        try:
            seat = SeatKind(str(row.get("seat") or "").strip().lower())
            office = OfficerRole(str(row["office"]).strip().lower()) if row.get("office") else None
            start = date.fromisoformat(str(row.get("start") or ""))
            end = date.fromisoformat(str(row["end"])) if row.get("end") else None
        except ValueError:
            continue
        out.append(Term(str(row["person"]).strip(), seat, start, end, office, str(row.get("source") or ""),
                        str(row.get("provision") or "")))
    out.sort(key=lambda t: (t.seat.value, t.office.value if t.office else "", t.start, t.person))
    return tuple(out)


__all__ = ["CHANGE_FORM", "FORMS", "FormError", "OFFICERS_TOPIC", "OFFICES", "PLEASURE", "TERMS_TOPIC", "TERM_FORM",
           "change_rows", "form_problem", "in_force", "rows_for", "term_rows", "terms_of"]
