"""A request for a proposal to the vendor who services a life safety system, drafted from the record.

``jason inspections`` reads, for each system, which obligations apply and which periods have a report on file. Where
one is overdue, has no record to count from, has a past period with nothing on file, or comes due soon, the next step
is usually the same: ask the system's servicer for a proposal, and for copies of any reports it holds that the
association's files lack. This module drafts that email from the record:

- ``request_for(records, key)`` lists the obligations to ask about (``RequestItem``), each with the reason in the
  record's words, and the last day any report or record is on file for the system.
- ``draft(request, ...)`` composes the email (``drafts.DraftPlan``): a proposal for the items, copies of reports since
  the last on file, and what the proposal should state. The reminders are for the person, not the vendor: that the
  record is jason's reading, the vendor's mail still waiting on the association, and that accepting a proposal is the
  board's decision.
- ``recipients(...)`` suggests addresses: the vendor's contact on file, then the people who write from its domains.
  The person chooses; ``jason draft`` takes the address only from ``--to``.

Nothing is sent. The draft is saved to Gmail only with ``jason draft --proposal-request KEY --to ADDRESS --yes``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Iterable

from jason.community.life_safety import row_name
from jason.google.gmail_drafts import DraftMessage
from jason.tasks.drafts import DraftPlan
from jason.tasks.inspections import Coverage, ObligationRecords, Records, SystemRecords, cadence_of

# How far ahead an obligation coming due is worth putting in the same proposal.
HORIZON_DAYS = 120


class Need(Enum):
    """Why an obligation is in the request, in the order the email lists them."""

    OVERDUE = "overdue"
    NO_RECORD = "no record"             # no first due date and nothing on file to count from
    NOT_ON_FILE = "not on file"         # a past period with no report on file
    DUE_SOON = "due soon"


@dataclass(frozen=True)
class RequestItem:
    obligation: str
    cadence: str
    citation: str                       # the authority as the row cites it, without the row's own summary
    need: Need
    why: str                            # the record's words: "due 2024-03-14; overdue", "no record ..."


@dataclass(frozen=True)
class ProposalRequest:
    system_key: str
    system_name: str
    serves: str
    servicer: str
    items: tuple[RequestItem, ...]
    last_on_file: date | None           # the latest report or record day on file for the system
    as_of: date
    community: str = ""
    not_read: tuple[str, ...] = ()      # reports filed but not read: they may answer an item

    def as_dict(self) -> dict[str, Any]:
        return {"system": self.system_key, "name": self.system_name, "serves": self.serves, "servicer": self.servicer,
                "lastOnFile": self.last_on_file.isoformat() if self.last_on_file else None, "asOf": self.as_of.isoformat(),
                "items": [{"obligation": i.obligation, "cadence": i.cadence, "citation": i.citation, "need": i.need.value,
                           "why": i.why} for i in self.items], "notRead": list(self.not_read)}


def _citation(authority: str) -> str:
    """The row's citation without its summary of scope ("19 CCR 904 (NFPA 25), form AES 2.1: valves, ..." keeps the
    part before the colon): a vendor is given the citation, not jason's paraphrase."""
    return (authority or "").split(":", 1)[0].strip().rstrip(",;")


def _day(value: Any) -> date | None:
    try:
        return date.fromisoformat(str(value)[:10]) if value else None
    except ValueError:
        return None


def _item(o: ObligationRecords, as_of: date, horizon: int) -> RequestItem | None:
    cal = o.calendar or {}
    nxt, standing, last = _day(cal.get("next")), str(cal.get("standing") or ""), _day(cal.get("lastDone"))
    name, cadence, citation = row_name(o.row), cadence_of(o.row), _citation(getattr(o.row, "authority", ""))
    missed = [p for p in o.periods if p.status is Coverage.NOT_ON_FILE and p.end < as_of]
    if standing == "overdue" and nxt:
        why = f"due {nxt.isoformat()}, now overdue" + (f"; last done {last.isoformat()} by our records" if last else "")
        return RequestItem(name, cadence, citation, Need.OVERDUE, why)
    if not o.periods and o.counted_from is None and nxt is None:
        return RequestItem(name, cadence, citation, Need.NO_RECORD, "our records do not show when it was last done")
    if missed:
        spans = ", ".join(p.label for p in missed[-3:])
        return RequestItem(name, cadence, citation, Need.NOT_ON_FILE, f"no record on file for {spans}")
    if nxt and as_of <= nxt <= as_of + timedelta(days=horizon):
        return RequestItem(name, cadence, citation, Need.DUE_SOON, f"due {nxt.isoformat()}")
    return None


def _last_on_file(s: SystemRecords) -> date | None:
    days: list[date] = []
    for o in s.obligations:
        last = _day((o.calendar or {}).get("lastDone"))
        if last:
            days.append(last)
        for p in list(o.earlier) + [r for period in o.periods for r in period.reports]:
            if p.report.day:
                days.append(p.report.day)
    return max(days) if days else None


def request_for(records: Records, key: str, *, horizon: int = HORIZON_DAYS) -> ProposalRequest | None:
    """The request for system ``key``: None when no system has the key; ``items`` empty when nothing is due."""
    one = next((s for s in records.systems if s.system.key == key), None)
    if one is None:
        return None
    items = [i for o in one.obligations if (i := _item(o, records.as_of, horizon)) is not None]
    items.sort(key=lambda i: list(Need).index(i.need))
    return ProposalRequest(
        system_key=one.system.key, system_name=one.system.name, serves=one.system.serves_label,
        servicer=one.system.servicer, items=tuple(items), last_on_file=_last_on_file(one), as_of=records.as_of,
        community=records.community, not_read=tuple(getattr(f, "name", str(f)) for f in one.not_read))


def offers(records: Records) -> list[tuple[str, int]]:
    """Each system with something to ask its servicer about, and how many items: what ``jason inspections`` offers."""
    out = []
    for s in records.systems:
        req = request_for(records, s.system.key)
        if req is not None and req.items and any(i.need is not Need.DUE_SOON for i in req.items):
            out.append((s.system.key, len(req.items)))
    return out


# ---------------------------------------------------------------------------------------------------------------
# Who to send it to.


@dataclass(frozen=True)
class Recipient:
    address: str
    name: str = ""
    why: str = ""


def recipients(directory: dict[str, Any], servicer: str) -> list[Recipient]:
    """The servicer's contact on file, then each person who writes from its domains, most recent first
    (``tasks.contacts.directory``). A suggestion for the person; ``--to`` decides."""
    row = next((v for v in directory.get("vendors", []) if servicer and servicer.lower() in
                (str(v.get("vendor", "")) + " " + str(v.get("sender", ""))).lower()), None)
    if row is None:
        return []
    out: list[Recipient] = []
    on_file = (row.get("onFile") or {}).get("email") or ""
    if on_file:
        out.append(Recipient(on_file, (row.get("onFile") or {}).get("contactName") or "", "the contact on file in PayHOA"))
    people = sorted(row.get("people") or [], key=lambda p: str(p.get("last") or ""), reverse=True)
    for p in people:
        if p.get("address") and p["address"] != on_file:
            names = ", ".join(p.get("names") or [])
            out.append(Recipient(p["address"], names, f"wrote us {p.get('wroteUs', 0)} times, last {str(p.get('last'))[:10]}"))
    return out


# ---------------------------------------------------------------------------------------------------------------
# The email.


def agreements_on_file(data_dir: Path, servicer: str) -> list[dict[str, Any]]:
    """The servicer's agreements and proposals jason has read (``jason contract-terms``), newest reading first: one
    already signed may cover the items, and its prices are the last ones offered."""
    from jason.tasks.contract_terms import load

    if not servicer:
        return []
    rows = [r for r in load(Path(data_dir)) if servicer.lower() in str(r.get("counterparty") or "").lower()]
    return sorted(rows, key=lambda r: str(r.get("readAt") or ""), reverse=True)


def draft(request: ProposalRequest, to: str, *, signer: str = "", waiting: Iterable[dict[str, Any]] = (),
          agreements: Iterable[dict[str, Any]] = ()) -> DraftPlan:
    """The proposal request: what the record shows is due, the reports to send, and what the proposal should state.
    ``waiting`` are the servicer's threads still waiting on the association (``tasks.threads``), and ``agreements`` its
    agreements on file (``agreements_on_file``), both for the reminders."""
    association = request.community or "the association"
    name = request.system_name[:1].lower() + request.system_name[1:]
    serves = f" serving {request.serves}" if request.serves and request.serves.lower() not in name.lower() else ""
    lines = ["Hello,", "",
             f"{association} asks for a proposal for the {name}{serves}, and for copies of any reports of it that you "
             "hold.", ""]
    if request.items:
        lines.append("What our records show:")
        for i in request.items:
            cite = f" ({i.citation})" if i.citation else ""
            lines.append(f"- {i.obligation}, {i.cadence}{cite}: {i.why}.")
        lines.append("")
    since = request.last_on_file.isoformat() if request.last_on_file else ""
    lines += [("Our files hold no report for this system after " + since + ". " if since else
               "Our files hold no report for this system. ") +
              "If you inspected, tested, or repaired it since, please send a copy of each report, with the date it was "
              "filed with the fire authority where that applies. Where a report answers an item above, it may need "
              "no proposal.", "",
              "For the proposal, please state:",
              "- each inspection or test, its price (per riser or per building), and when it would be done;",
              "- the forms you will complete, and to whom you will send them;",
              "- your contractor's license number and classification;",
              "- anything excluded, and how repairs found during an inspection would be quoted.", "",
              "Thank you,", signer or f"Board of Directors, {association}"]
    reminders = [
        "The items come from jason's reading of the records on file (jason inspections); a report filed elsewhere, or "
        "work done without a report sent, would not show. The vendor's answer may close an item without a proposal.",
        "Accepting a proposal is the board's decision; this email only asks for one.",
    ]
    for t in waiting:
        reminders.append(f"The vendor wrote on {t.get('last')} (\"{t.get('subject')}\") and nothing went out after it: "
                         f"read it before sending ({t.get('link', '')}).")
    for a in agreements:
        signed = "signed" in str(a.get("name", "")).lower() or any(s.get("signed") for s in a.get("signatures") or [])
        reminders.append(f"{'A signed' if signed else 'An'} agreement or proposal from this vendor is on file "
                         f"(\"{a.get('name')}\"): read it first, since it may already cover these items "
                         f"(jason contract-terms --list; key {a.get('key')}).")
    if request.not_read:
        reminders.append(f"Filed but not read ({len(request.not_read)}): {'; '.join(request.not_read[:3])}; "
                         "jason models --filed reads them.")
    if not request.items:
        reminders.append("Nothing is overdue, unrecorded, or due within the horizon: the email asks only for reports.")
    subject = f"Request for proposal and reports: {request.system_name}, {association}"
    return DraftPlan(DraftMessage(to=(to,), subject=subject, text="\n".join(lines)),
                     f"jason inspections, system {request.system_key}, as of {request.as_of.isoformat()}", reminders)


def waiting_threads(data_dir: Path, community: Any, servicer: str, *, words: tuple[str, ...] = ("inspect", "test",
                    "report", "proposal")) -> list[dict[str, Any]]:
    """The servicer's threads waiting on the association whose subject names an inspection, a test, a report, or a
    proposal. Empty when the mail store is not on disk."""
    try:
        from jason.tasks.threads import threads

        rows = threads(Path(data_dir), community).get("rows") or []
    except Exception:  # noqa: BLE001 - no mail store: the reminder is simply absent
        return []
    return [r for r in rows if r.get("status") == "awaiting us" and servicer
            and servicer.lower() in str(r.get("sender", "")).lower()
            and any(w in str(r.get("subject", "")).lower() for w in words)]


__all__ = ["HORIZON_DAYS", "Need", "RequestItem", "ProposalRequest", "Recipient", "request_for", "offers", "recipients",
           "draft", "waiting_threads", "agreements_on_file"]
