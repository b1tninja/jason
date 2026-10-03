"""Records requests: a member's request for association records under Civil Code 5200-5240, and what a person decided.

One request is one member's ask, received on one day: which kinds of record (``AssociationRecord``), the purpose
the member stated, in the member's words, and the decisions a person then makes. jason computes the clock from the
statute's structure (section 5210: current-fiscal-year records in business days, prior-year records in calendar days,
the membership list sooner), keeps the record, and stops there. It does not judge whether a purpose is reasonably
related to the member's interest as a member (section 5225), does not choose what to withhold or redact or the legal
basis stated for it (section 5215), and does not hand the membership list to anyone. A person records each of those,
with counsel where needed, and jason keeps the history.

The store is jason's own, ``data/records-requests/requests.json``. A request is keyed by its day and unit, never by
the member's name.

Business days here are Monday through Friday. Court and state holidays are not subtracted, so a computed business-day
deadline can fall a day or two earlier than the statute would allow; a person checks the calendar before relying on it.
The fiscal year is taken as the calendar year of the day the request was received: a ``years`` entry equal to that
year is a current-year record, an earlier one a prior-year record. An association with another fiscal year reads the
two classes with that in mind.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from jason.community.records import CITATION
from jason.community.symbols import AssociationRecord

STORE = Path("records-requests") / "requests.json"

VIAS = ("email", "mail", "form")
HOW = ("inspection", "copies", "")
RECORD_VALUES = tuple(r.value for r in AssociationRecord)
DECISION_FIELDS = ("purposeAdequate", "withheld", "producedOn", "inspectedOrCopies", "feeCents", "note")

CURRENT_YEAR_BUSINESS_DAYS = 10     # section 5210(b)(1)
PRIOR_YEAR_CALENDAR_DAYS = 30       # section 5210(b)(2)
MEMBERSHIP_LIST_BUSINESS_DAYS = 5   # section 5210(b)


@dataclass
class Decisions:
    purposeAdequate: bool | None = None            # section 5225; only when the membership list is asked
    withheld: list[dict[str, str]] = field(default_factory=list)   # [{record, reason}], section 5215 grounds as given
    producedOn: str = ""                           # ISO date the records were made available or sent
    inspectedOrCopies: str = ""                    # "inspection" | "copies" | ""
    feeCents: int = 0                              # the copying, mailing, or redaction cost the member agreed to
    note: str = ""


@dataclass
class Request:
    id: str                                        # "<receivedOn>--<slug of the unit>"
    receivedOn: str                                # ISO date
    unit: str
    via: str                                       # one of VIAS
    records: list[str] = field(default_factory=list)   # AssociationRecord values
    purpose: str = ""                              # the member's stated purpose, as given
    membershipList: bool = False
    years: list[int] = field(default_factory=list)     # fiscal years asked for; empty means the current one
    decisions: Decisions = field(default_factory=Decisions)
    by: str = ""
    recorded: str = ""
    updated: str = ""
    history: list[str] = field(default_factory=list)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:40] or "unit"


def add_business_days(start: date, days: int) -> date:
    """``days`` business days after ``start``, Monday through Friday, holidays not subtracted (see the module docstring)."""
    out = start
    left = days
    while left > 0:
        out += timedelta(days=1)
        if out.weekday() < 5:
            left -= 1
    return out


def deadlines(received_on: date | str, records: list[str] | tuple[str, ...], years: list[int] | None = None) -> list[dict[str, Any]]:
    """The section 5210 clock for a request, as stages for a Clock.

    Current-fiscal-year records are due within ten business days, prior-year records within thirty calendar days, and
    the membership list within five business days. Business days are Monday through Friday with no holidays
    subtracted, and the fiscal year is the calendar year of ``received_on`` (module docstring). ``years`` empty means
    only the current year was asked for. A request for the membership list alone carries only that stage.
    """
    day = received_on if isinstance(received_on, date) else date.fromisoformat(str(received_on))
    kinds = [str(r) for r in records]
    other = [k for k in kinds if k != AssociationRecord.MEMBERSHIP_LIST.value]
    current_year = day.year
    asked_years = list(years or [])
    stages: list[dict[str, Any]] = [{"key": "received", "label": "Request received", "date": day.isoformat(), "done": True}]
    if AssociationRecord.MEMBERSHIP_LIST.value in kinds:
        stages.append({"key": "membershipList", "label": "Membership list produced by", "authority": "CIV 5210(b)",
                       "date": add_business_days(day, MEMBERSHIP_LIST_BUSINESS_DAYS).isoformat()})
    if other:
        if not asked_years or any(y >= current_year for y in asked_years):
            stages.append({"key": "currentYear", "label": "Current fiscal year records produced by", "authority": "CIV 5210(b)(1)",
                           "date": add_business_days(day, CURRENT_YEAR_BUSINESS_DAYS).isoformat()})
        if any(y < current_year for y in asked_years):
            stages.append({"key": "priorYears", "label": "Prior fiscal year records produced by", "authority": "CIV 5210(b)(2)",
                           "date": (day + timedelta(days=PRIOR_YEAR_CALENDAR_DAYS)).isoformat()})
    return stages


def due_by(req: Request) -> str:
    """The earliest production deadline, or "" when none applies."""
    dates = [s["date"] for s in deadlines(req.receivedOn, req.records, req.years) if s["key"] != "received"]
    return min(dates) if dates else ""


def standing(req: Request, today: date | None = None) -> str:
    """open, produced, or overdue: where the request stands on its face. A person decides what was actually produced."""
    if req.decisions.producedOn:
        return "produced"
    now = today or date.today()
    due = due_by(req)
    return "overdue" if due and now.isoformat() > due else "open"


def _validate_records(records: Any) -> list[str]:
    if not isinstance(records, (list, tuple)) or not records:
        raise ValueError("records is a non-empty list of record kinds")
    bad = sorted({str(r) for r in records} - set(RECORD_VALUES))
    if bad:
        raise ValueError(f"{', '.join(bad)}: not a record kind (CIV 5200)")
    return [str(r) for r in records]


def _validate_decisions(changes: dict[str, Any], req: Request) -> None:
    if "purposeAdequate" in changes:
        v = changes["purposeAdequate"]
        if v not in (True, False, None):
            raise ValueError("purposeAdequate is true, false, or null")
        if v is not None and not req.membershipList:
            raise ValueError("purposeAdequate applies only when the membership list is asked (CIV 5225)")
    if "withheld" in changes:
        rows = changes["withheld"]
        if not isinstance(rows, list):
            raise ValueError("withheld is a list of {record, reason}")
        for row in rows:
            if not isinstance(row, dict) or str(row.get("record", "")) not in RECORD_VALUES:
                raise ValueError("each withheld row names a record kind")
            if not str(row.get("reason", "")).strip():
                raise ValueError("each withheld row states the basis for withholding, as the person gives it (CIV 5215)")
    if "producedOn" in changes and changes["producedOn"]:
        date.fromisoformat(str(changes["producedOn"]))
    if "inspectedOrCopies" in changes and changes["inspectedOrCopies"] not in HOW:
        raise ValueError("inspectedOrCopies is inspection, copies, or empty")
    if "feeCents" in changes:
        fee = changes["feeCents"]
        if isinstance(fee, bool) or not isinstance(fee, int) or fee < 0:
            raise ValueError("feeCents is a whole number of cents, zero or more")
    if "note" in changes and not isinstance(changes["note"], str):
        raise ValueError("note is text")


def _from_raw(raw: dict[str, Any]) -> Request:
    known = set(Request.__dataclass_fields__)
    data = {k: v for k, v in raw.items() if k in known}
    dec = data.get("decisions") or {}
    data["decisions"] = Decisions(**{k: v for k, v in dec.items() if k in Decisions.__dataclass_fields__})
    return Request(**data)


def load(data_dir: Path) -> list[Request]:
    path = Path(data_dir) / STORE
    if not path.is_file():
        return []
    return [_from_raw(raw) for raw in json.loads(path.read_text(encoding="utf-8")).get("requests", [])]


def save(data_dir: Path, items: list[Request]) -> Path:
    path = Path(data_dir) / STORE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"savedAt": _now(), "requests": [asdict(r) for r in items]}, indent=1), encoding="utf-8")
    return path


def get(data_dir: Path, request_id: str) -> Request:
    found = next((r for r in load(data_dir) if r.id == request_id), None)
    if found is None:
        raise KeyError(request_id)
    return found


def _store_lock(fn):
    import functools

    from jason.locks import Resource, hold

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        with hold(Resource.STORE, "records-requests", timeout=60, purpose=f"records requests: {fn.__name__}"):
            return fn(*args, **kwargs)
    return wrapper


@_store_lock
def open_request(data_dir: Path, received_on: str, unit: str, via: str, records: list[str], purpose: str = "",
                 years: list[int] | None = None, by: str = "") -> Request:
    """Record a member's request as received. The purpose is kept in the member's words."""
    received_on = str(received_on).strip()
    date.fromisoformat(received_on)
    unit = str(unit).strip()
    if not unit:
        raise ValueError("a request names the unit it came from")
    if via not in VIAS:
        raise ValueError(f"via is one of {', '.join(VIAS)}")
    kinds = _validate_records(records)
    ys = [int(y) for y in (years or [])]
    items = load(data_dir)
    base = f"{received_on}--{slug(unit)}"
    key, n = base, 1
    while any(r.id == key for r in items):
        n += 1
        key = f"{base}-{n}"
    now = _now()
    req = Request(id=key, receivedOn=received_on, unit=unit, via=via, records=kinds, purpose=str(purpose or ""),
                  membershipList=AssociationRecord.MEMBERSHIP_LIST.value in kinds, years=ys, by=str(by or ""),
                  recorded=now, updated=now, history=[f"{now[:10]}: received via {via}"])
    items.append(req)
    save(data_dir, items)
    return req


@_store_lock
def decide(data_dir: Path, request_id: str, **changes: Any) -> Request:
    """Record what a person decided on a request: adequacy of the purpose, what is withheld and why, when and how it
    was produced, the fee. ``by`` names the person. jason validates the shape and keeps the history; it decides nothing."""
    by = changes.pop("by", None)
    unknown = sorted(set(changes) - set(DECISION_FIELDS))
    if unknown:
        raise ValueError(f"{', '.join(unknown)}: not a decision field")
    items = load(data_dir)
    found = next((r for r in items if r.id == request_id), None)
    if found is None:
        raise KeyError(request_id)
    _validate_decisions(changes, found)
    now = _now()
    for k, v in changes.items():
        before = getattr(found.decisions, k)
        if before != v:
            if k == "purposeAdequate":
                word = {True: "adequate", False: "not adequate", None: "(undecided)"}
                found.history.append(f"{now[:10]}: purpose {word[before]} -> {word[v]} (CIV 5225)")
            elif k == "withheld":
                found.history.append(f"{now[:10]}: withheld {len(v)} record kind(s) (CIV 5215)")
            elif k == "producedOn":
                found.history.append(f"{now[:10]}: produced {before or '(not yet)'} -> {v or '(not yet)'}")
            setattr(found.decisions, k, v)
    if by is not None:
        found.by = str(by)
    found.updated = now
    save(data_dir, items)
    return found


def as_dict(req: Request, today: date | None = None) -> dict[str, Any]:
    return {**asdict(req), "stages": deadlines(req.receivedOn, req.records, req.years), "dueBy": due_by(req),
            "standing": standing(req, today), "citations": {k: CITATION[AssociationRecord(k)] for k in req.records}}
