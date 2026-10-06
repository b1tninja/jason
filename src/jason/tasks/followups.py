"""Follow-ups: what we do next, and when (docs/followups-design.md, "Follow-ups: what we do next, and when").

A follow-up is a dated action for a person. jason computes it from what it already holds, shows it, and tracks it; it never
carries one out: it sends nothing, resends nothing, and marks nothing done on a person's behalf. Most are **derived**, so there
is no second list to keep:

- a campaign's cycle (``tasks.campaigns``, ``AnswerCycle``): the reminder (a campaign setting, ``remind-days``, else a proposed
  number), the return-by date, the day answers must be entered in the books (4041(b)(1)), the reports' mailing date, and the
  day the watch window closes;
- the notice ledger (``tasks.notice_ledger``): a bounced or undelivered email is resent by first-class mail, a returned letter
  asks for a current address (its ``FOLLOW_UPS``, with their authority);
- the response inbox (``tasks.response_inbox``): an arrival nobody has read, a reading nobody has confirmed, an answer confirmed
  and not recorded;
- a request's association clocks (``form_library``'s ``association_clocks``), counted from the arrival's receipt.

A person's own items (``add_manual``) are kept in ``data/followups/manual.json``. A person's act on any item, derived or
their own (done, deferred to a date, dropped), is kept in the append-only ``data/followups/acts.jsonl`` (who, when, what,
why), keyed by the item's stable id, so the next run shows the item with its state and does not make it again. Both are
written under the store lock ``followups-<profile>``.

**Where the law or the documents are silent, the number is proposed policy and says so.** ``PROPOSED_DAYS`` holds each one;
the board's adoption is a rule row that replaces it (the design's open decisions). An item's ``basis`` is ``law`` (with its
citation), ``documents`` (with the section), ``proposed policy`` (labeled), or ``person``; its ``due_note`` says when the date
is a proposed number counted from a day the law or a record fixes.

An item names units and owners, never an address, an email, or an answer.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Iterable

from jason.community.response_inbox import ResponseRequest, State
from jason.tasks import campaign_funnel, campaigns
from jason.tasks import response_inbox as ri

ROOT = "followups"
ACTS = "acts.jsonl"
MANUAL = "manual.json"
NEXT_DAYS = 14                                   # the default window: overdue, today, and the next two weeks
REMIND_OPTION = "remind-days"                    # a campaign's own setting (``jason campaigns --open --option remind-days=10``)
# Where the law and the documents are silent: the board's numbers are proposed until it adopts them. Each is a number of
# calendar days counted from a day a record fixes.
PROPOSED_DAYS = {"remind": 7,                    # before the return-by date
                 "resend": 3,                    # after a delivery failed, to resend by first-class mail
                 "ask": 7,                       # after a letter came back or an email bounced, to ask the member for an address
                 "read": 3,                      # after an arrival was kept, to read it
                 "confirm": 3,                   # after a reading was made, to confirm it
                 "record": 7,                    # after an answer was confirmed (or came structured), to record it
                 "close": ResponseRequest.AFTER_RETURN_BY}   # after the return-by date, to close the campaign


class FollowUpError(ValueError):
    """A follow-up act refused: ``str(exc)`` is the reason, in plain words."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class FollowUpKind(Enum):
    REMIND = "remind"
    RETURN_BY = "return-by"
    ENTER_BY = "enter-by"
    REPORTS_MAILED = "reports-mailed"
    RESEND = "resend"
    ACKNOWLEDGE = "acknowledge"
    REVIEW = "review"
    DECIDE = "decide"
    ANSWER_DUE = "answer-due"
    CLOSE = "close"
    MANUAL = "manual"


class Basis(Enum):
    LAW = "law"
    DOCUMENTS = "documents"
    PROPOSED_POLICY = "proposed policy"
    PERSON = "person"


class FollowUpState(Enum):
    UPCOMING = "upcoming"
    DUE = "due"                  # due today
    OVERDUE = "overdue"
    DONE = "done"
    DEFERRED = "deferred"        # to a date, with the reason
    DROPPED = "dropped"          # with the reason


def kind_of(text: str) -> FollowUpKind:
    word = (text or "").strip().lower().replace("_", "-")
    for kind in FollowUpKind:
        if word == kind.value:
            return kind
    raise FollowUpError(f"no kind {text!r}; the kinds are " + ", ".join(k.value for k in FollowUpKind))


def state_of(text: str) -> FollowUpState:
    word = (text or "").strip().lower()
    for state in FollowUpState:
        if word == state.value:
            return state
    raise FollowUpError(f"no state {text!r}; the states are " + ", ".join(s.value for s in FollowUpState))


@dataclass(frozen=True)
class FollowUp:
    """One dated action for a person. ``outstanding`` is the count it is about (``None``: it cannot be told, and ``reason`` says
    why) and ``names`` its units and owners, never an address. ``due_note`` is non-empty when the date is a proposed number of
    days counted from a recorded day."""

    id: str                                      # stable: a hash of the kind, the subject, and what fixes the day
    kind: FollowUpKind
    due: date
    subject: str                                 # a campaign code, a request key, an arrival id, a notice, or a person's item
    what: str
    basis: Basis
    cite: str = ""                               # the citation, the section, the proposal, or whose item it is
    window_end: date | None = None               # for a window, the last day
    due_note: str = ""
    outstanding: int | None = None
    names: tuple[str, ...] = ()
    reason: str = ""                             # why ``outstanding`` is not known
    state: FollowUpState = FollowUpState.UPCOMING
    by: str = ""                                 # who changed its state
    at: str = ""                                 # and when
    why: str = ""                                # the note, the reason deferred, or the reason dropped
    deferred_to: date | None = None
    command: str = ""                            # what a person runs to do it (a dry run first where there is one)
    campaign: str = ""
    source: str = ""                             # campaign, ledger, inbox, clock, or person

    @property
    def open(self) -> bool:
        return self.state in (FollowUpState.UPCOMING, FollowUpState.DUE, FollowUpState.OVERDUE)

    def to_json(self) -> dict[str, Any]:
        return {"id": self.id, "kind": self.kind.value, "due": self.due.isoformat(),
                "windowEnd": self.window_end.isoformat() if self.window_end else "", "subject": self.subject,
                "what": self.what, "basis": self.basis.value, "cite": self.cite, "dueNote": self.due_note,
                "outstanding": self.outstanding, "names": list(self.names), "reason": self.reason,
                "state": self.state.value, "by": self.by, "at": self.at, "why": self.why,
                "deferredTo": self.deferred_to.isoformat() if self.deferred_to else "", "command": self.command,
                "campaign": self.campaign, "source": self.source}


def ident(kind: FollowUpKind, subject: str, fixes: str) -> str:
    """The stable id of an item: the same kind, subject, and fixing day (or stage) give the same id on every run."""
    return "fu-" + hashlib.sha1(f"{kind.value}|{subject}|{fixes}".encode("utf-8")).hexdigest()[:10]


def standing(due: date, today: date) -> FollowUpState:
    return FollowUpState.OVERDUE if due < today else FollowUpState.DUE if due == today else FollowUpState.UPCOMING


def _day(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value or "").strip()[:10]
    try:
        return date.fromisoformat(text) if text else None
    except ValueError:
        return None


def _plural(n: int | None, word: str, many: str = "") -> str:
    return f"{n} {word if n == 1 else (many or word + 's')}" if n is not None else f"the {many or word + 's'}"


def _has(n: int | None) -> str:
    return "has" if n == 1 else "have"


def _requests(community: Any) -> tuple[Any, ...]:
    try:
        return tuple(community.response_requests() or ()) if community is not None else ()
    except Exception:  # noqa: BLE001 - a profile that cannot say watches nothing
        return ()


def _make(kind: FollowUpKind, subject: str, fixes: str, due: date, what: str, basis: Basis, today: date, **more: Any) -> FollowUp:
    return FollowUp(ident(kind, subject, fixes), kind, due, subject, what, basis, state=standing(due, today), **more)


# -- derived from a campaign's cycle ---------------------------------------------------------------------------------------

def _cycle_items(data_dir: Path, community: Any, today: date, moment: datetime) -> list[FollowUp]:
    rows = campaigns.view(data_dir, community)
    requests = _requests(community)
    out: list[FollowUp] = []
    for row in sorted(rows.values(), key=lambda c: (-c.year, c.code)):
        if not row.is_open:
            continue
        request = next((r for r in requests if r.names_campaign(row.code)), None)
        cycle = request.cycle if request is not None else None
        return_by = _day(row.return_by) or (cycle.return_by if cycle else None)
        shown = campaign_funnel.funnel(data_dir, community, row.code, now=moment)
        known = shown.get("found") and shown["outstanding"]["count"] is not None
        count = shown["outstanding"]["count"] if known else None
        names = tuple(f"{o['unit']} ({o['name']})" if o["name"] else o["unit"] for o in shown["outstanding"]["owners"]) if known else ()
        reason = "" if known else (shown.get("outstanding", {}).get("reason") or "the funnel could not be read")
        who = f"set by {row.by} when the campaign was opened" if row.by else "set when the campaign was opened"
        watch = request.key if request is not None else ""
        if return_by is not None:
            raw = row.options.get(REMIND_OPTION)
            days = int(raw) if str(raw or "").strip().isdigit() else PROPOSED_DAYS["remind"]
            chosen = str(raw or "").strip().isdigit()
            if count == 0:
                remind = "Nobody is outstanding: there is no one to remind (mark this done, or drop it)"
            else:
                remind = f"Remind {_plural(count, 'owner')} who {_has(count)} not answered the {row.code} request"
            by_email = row.channel == "email"
            out.append(_make(
                FollowUpKind.REMIND, row.code, return_by.isoformat(), return_by - timedelta(days=days), remind,
                Basis.PERSON if chosen else Basis.PROPOSED_POLICY, today, window_end=return_by,
                cite=(f"remind {days} days before the return-by date, {who}" if chosen else
                      f"proposed: remind {days} days before the return-by date (the board has not adopted a number)"),
                due_note="" if chosen else f"proposed: {days} days before {return_by.isoformat()}",
                outstanding=count, names=names, reason=reason, campaign=row.code, source="campaign",
                command=("jason owner-info --email-batch --follow-up reminder --message FILE.md (a dry run; --yes sends)"
                         if by_email else f"jason responses --outstanding --request {watch}" if watch else
                         f"jason campaigns --show {row.code}")))
            out.append(_make(
                FollowUpKind.RETURN_BY, row.code, return_by.isoformat(), return_by,
                f"Answers to the {row.code} request are due: {_plural(count, 'owner')} {_has(count)} not answered; decide who is "
                "followed up and how", Basis.PERSON, today, cite=f"the return-by date, {who}", outstanding=count, names=names,
                reason=reason, campaign=row.code, source="campaign",
                command=f"jason responses --outstanding --request {watch}" if watch else f"jason campaigns --show {row.code}"))
            closing = return_by + timedelta(days=PROPOSED_DAYS["close"])
            out.append(_make(
                FollowUpKind.CLOSE, row.code, return_by.isoformat(), closing,
                f"The watch window of the {row.code} campaign ends: close it, or let a person's --since read on",
                Basis.PROPOSED_POLICY, today, cite=f"proposed: close {PROPOSED_DAYS['close']} days after the return-by date "
                "(the window a response check watches)", due_note=f"proposed: {PROPOSED_DAYS['close']} days after "
                f"{return_by.isoformat()}", campaign=row.code, source="campaign",
                command=f"jason campaigns --close {row.code} --by NAME"))
        if cycle is not None and request is not None:
            waiting = _to_record(data_dir, request)
            if cycle.entry_deadline is not None:
                out.append(_make(
                    FollowUpKind.ENTER_BY, request.key, cycle.entry_deadline.isoformat(), cycle.entry_deadline,
                    f"Enter the answers to the {request.key} request in PayHOA: {_plural(len(waiting), 'answer')} "
                    "waiting to be recorded", Basis.LAW, today, cite="CIV 4041(b)(1): at least 30 days before the annual reports",
                    outstanding=len(waiting), names=tuple(waiting), campaign=row.code, source="inbox",
                    command="jason owner-info --apply --payhoa (a dry run; --yes writes)"))
            if cycle.reports_mailed is not None:
                out.append(_make(
                    FollowUpKind.REPORTS_MAILED, request.key, cycle.reports_mailed.isoformat(), cycle.reports_mailed,
                    "The annual budget report and policy statement go out", Basis.LAW, today, cite="CIV 5300, 5310",
                    campaign=row.code, source="campaign"))
    seen: set[str] = set()
    return [i for i in out if not (i.id in seen or seen.add(i.id))]


def _to_record(data_dir: Path, request: Any) -> list[str]:
    """The units whose answers to a request are in (confirmed, or structured) and not yet recorded in PayHOA."""
    out = []
    for a in ri.load_inbox(data_dir).arrivals.values():
        if a.request != request.key or a.superseded_by or a.state in (State.DISMISSED, State.RECORDED):
            continue
        if a.state is State.KEYED or (a.structured and a.state in (State.NEW, State.SEEN)):
            out.append(ri.scrub(a.unit or a.who or a.id, 80))
    return sorted(out)


# -- derived from the notice ledger ----------------------------------------------------------------------------------------

def _ledger_items(data_dir: Path, today: date, moment: datetime) -> list[FollowUp]:
    from jason.tasks import notice_ledger as nl

    ledger = campaign_funnel.read_ledger(data_dir, moment)
    if not ledger["exists"]:
        return []
    by_notice: dict[str, list[Any]] = {}
    for a in ledger["attempts"]:
        by_notice.setdefault(a.notice, []).append(a)
    groups: dict[tuple[str, str, str], list[tuple[Any, Any, Any]]] = {}
    for notice, attempts in sorted(by_notice.items()):
        for member in nl.standing(attempts, general=nl.is_general(data_dir, notice)):
            for owed, attempt in member.follow_ups:
                if owed is nl.GENERAL_NOTE:
                    continue                             # noted, nothing to do
                day = _day(attempt.status_at) or _day(attempt.sent_at)
                if day is not None:
                    groups.setdefault((notice, owed.key, day.isoformat()), []).append((member, attempt, owed))
    out = []
    for (notice, key, read), found in sorted(groups.items()):
        owed = found[0][2]
        days = PROPOSED_DAYS["resend" if owed.resend else "ask"]
        units = sorted({ri.scrub(m.unit or f"member {m.membership_id}", 80) for m, _, _ in found})
        out.append(_make(
            FollowUpKind.RESEND, notice, f"{key}@{read}", date.fromisoformat(read) + timedelta(days=days),
            f"{_plural(len(units), 'member')} ({owed.channel} outcome read {read}): {owed.action}",
            Basis.LAW if owed.force == "required" else Basis.PROPOSED_POLICY, today, cite=owed.authority,
            due_note=f"proposed: {days} days after the outcome was read ({read}); the law sets no day",
            outstanding=len(units), names=tuple(units), source="ledger",
            command=(("jason owner-info --mail-batch " + " ".join(f'--only "{u}"' for u in units) + " --resend "
                      "(a dry run; --yes with --confirmed-by NAME sends)") if owed.resend else "")))
    return out


# -- derived from the response inbox ---------------------------------------------------------------------------------------

def _inbox_items(data_dir: Path, today: date) -> list[FollowUp]:
    acts: dict[str, list[dict[str, Any]]] = {}
    for act in ri.acts_for(data_dir):
        acts.setdefault(str(act.get("id")), []).append(act)

    def acted(arrival: Any, what: str) -> date | None:
        rows = [a for a in acts.get(arrival.id, []) if a.get("act") == what]
        return _day(rows[-1].get("at")) if rows else None

    out = []
    for a in sorted(ri.load_inbox(data_dir).arrivals.values(), key=lambda a: a.id):
        if a.superseded_by or a.state in (State.DISMISSED, State.RECORDED):
            continue
        who = ri.scrub(f"{a.who} ({a.unit})" if a.unit else a.who, 100) or a.id
        arrived = _day(a.kept_at) or _day(a.at)
        if a.structured and a.state in (State.NEW, State.SEEN):
            if "status: complete" in a.note:
                continue                                   # PayHOA marks it complete: nothing waits on it
            stage, start, text = "record", arrived, f"Record the {a.channel.value} answer from {who} in PayHOA"
            command = "jason owner-info --apply --payhoa (a dry run; --yes writes)"
        elif a.state in (State.NEW, State.SEEN):
            stage, start, text = "read", arrived, f"Read the returned form that came by {a.channel.value} from {who}"
            command = f"jason responses --read {a.id} --by NAME"
        elif a.state is State.READ:
            stage, start, text = "confirm", acted(a, "read") or arrived, f"Confirm the reading of the form from {who}"
            command = f"jason responses --confirm {a.id} --by NAME"
        else:
            stage, start, text = "record", acted(a, "confirm") or arrived, f"Record the confirmed answer from {who} in PayHOA"
            command = "jason owner-info --apply --payhoa (a dry run; --yes writes)"
        if start is None:
            continue
        days = PROPOSED_DAYS[stage]
        out.append(_make(
            FollowUpKind.REVIEW, a.id, f"{stage}@{start.isoformat()}", start + timedelta(days=days), text,
            Basis.PROPOSED_POLICY, today, cite="no number is adopted: the board decides how soon an arrival is read, confirmed, "
            "and recorded", due_note=f"proposed: {days} days after {start.isoformat()}", outstanding=1, names=(who,), command=command,
            campaign="", source="inbox"))
    return out


# -- derived from a request's association clocks ----------------------------------------------------------------------------

CLOCK_KINDS = {"acknowledge": FollowUpKind.ACKNOWLEDGE, "read": FollowUpKind.REVIEW, "decide": FollowUpKind.DECIDE,
               "answer": FollowUpKind.ANSWER_DUE, "respond": FollowUpKind.ANSWER_DUE}


def _clock_items(data_dir: Path, community: Any, today: date) -> list[FollowUp]:
    """Each open arrival whose request's form has association clocks (``FormDefinition.association_clocks``), counted from
    the day the arrival came in. A clock counted from another event, or one this module has no kind for, is skipped."""
    from jason.community.form_library.tiers import DayKind, SetBy

    open_arrivals = [a for a in ri.load_inbox(data_dir).arrivals.values()
                     if not a.superseded_by and a.state not in (State.DISMISSED, State.RECORDED)]
    if not open_arrivals:
        return []
    rows = campaigns.view(data_dir, community)
    clocks: dict[str, tuple[Any, ...]] = {}
    resolved = None
    out = []
    for a in sorted(open_arrivals, key=lambda a: a.id):
        if a.request not in clocks:
            clocks[a.request] = ()
            request = next((r for r in _requests(community) if r.key == a.request), None)
            named = campaigns.for_request(rows, request) if request is not None else []
            if named:
                try:
                    if resolved is None:
                        from jason.community.form_library.resolve import resolve

                        resolved = resolve(community)
                    form = resolved.get(named[0].form)
                    clocks[a.request] = tuple(form.definition.association_clocks) if form is not None else ()
                except Exception:  # noqa: BLE001 - a library that cannot resolve gives no clocks, not a traceback
                    clocks[a.request] = ()
        received = _day(a.at)
        for clock in clocks[a.request]:
            kind = CLOCK_KINDS.get(clock.name)
            if kind is None or received is None or not clock.counted_from.lower().startswith("receipt"):
                continue
            due = _business(received, clock.number) if clock.kind is DayKind.BUSINESS else received + timedelta(days=clock.number)
            basis = {SetBy.STATUTE: Basis.LAW, SetBy.DOCUMENTS: Basis.DOCUMENTS}.get(clock.set_by, Basis.PROPOSED_POLICY)
            out.append(_make(
                kind, a.id, f"{clock.name}@{received.isoformat()}", due,
                f"{clock.name.capitalize()}: {ri.scrub(a.who, 60) or a.id}'s request, {clock.number} "
                f"{'business' if clock.kind is DayKind.BUSINESS else 'calendar'} days from {clock.counted_from}",
                basis, today, cite=clock.section or ("proposed policy" if basis is Basis.PROPOSED_POLICY else ""),
                due_note="proposed: " + clock.words() if basis is Basis.PROPOSED_POLICY else "", outstanding=1,
                names=(ri.scrub(f"{a.who} ({a.unit})" if a.unit else a.who, 100),),
                command=f"jason responses --show {a.id}", source="clock"))
    return out


def _business(start: date, days: int) -> date:
    """``days`` weekdays after ``start`` (holidays are not known, so this is the earliest the clock can run out)."""
    from jason.community.models.correspondence import add_business_days

    return add_business_days(start, days)


# -- a person's items and acts ---------------------------------------------------------------------------------------------

def _root(data_dir: Path) -> Path:
    return Path(data_dir) / ROOT


def _locked(purpose: str) -> Any:
    from jason.locks import Resource, account, hold

    return hold(Resource.STORE, f"followups-{account()}", purpose=purpose)


def acts(data_dir: Path) -> list[dict[str, Any]]:
    """Every act on a follow-up, oldest first (``data/followups/acts.jsonl``)."""
    path = _root(data_dir) / ACTS
    if not path.is_file():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            row = json.loads(line) if line.strip() else None
        except ValueError:
            continue
        if isinstance(row, dict) and row.get("id"):
            out.append(row)
    return out


def _log(data_dir: Path, act: str, item_id: str, by: str, why: str = "", **detail: Any) -> dict[str, Any]:
    row = {"at": ri.iso(ri.now_utc()), "by": by, "act": act, "id": item_id, "why": why, **detail}
    path = _root(data_dir) / ACTS
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    return row


def _manual_rows(data_dir: Path) -> dict[str, dict[str, Any]]:
    path = _root(data_dir) / MANUAL
    try:
        raw = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    except (OSError, ValueError):
        return {}
    return {str(k): v for k, v in (raw.get("items") or {}).items() if isinstance(v, dict)} if isinstance(raw, dict) else {}


def manual_items(data_dir: Path, *, today: date | None = None) -> list[FollowUp]:
    """A person's own items (``add_manual``), as follow-ups of kind manual and basis person."""
    today = today or date.today()
    out = []
    for item_id, row in sorted(_manual_rows(data_dir).items()):
        due = _day(row.get("date"))
        if due is None:
            continue
        out.append(FollowUp(item_id, FollowUpKind.MANUAL, due, str(row.get("campaign") or "a person's item"), str(row.get("text") or ""),
                            Basis.PERSON, cite=f"added by {row.get('by', '?')} on {str(row.get('at', ''))[:10]}",
                            state=standing(due, today), campaign=str(row.get("campaign") or ""), source="person"))
    return out


def _need(value: str, what: str) -> str:
    if not str(value or "").strip():
        raise FollowUpError(f"{what} is required: an act names who did it")
    return value.strip()


def add_manual(data_dir: Path, *, due: date, text: str, by: str, campaign: str = "", today: date | None = None) -> FollowUp:
    """A person's own follow-up ("call the printer on Thursday") due on ``due``. ``by`` and ``text`` are required."""
    _need(by, "--by")
    if not str(text or "").strip():
        raise FollowUpError("--text is required: what is to be done")
    if not isinstance(due, date) or isinstance(due, datetime):
        raise FollowUpError("--date is required: the day it is due, YYYY-MM-DD")
    clean = ri.scrub(text, 300)
    code = (campaign or "").strip().upper()
    item_id = ident(FollowUpKind.MANUAL, code or "a person's item", f"{due.isoformat()}|{clean}")
    with _locked("add a follow-up"):
        rows = _manual_rows(data_dir)
        if item_id in rows:
            raise FollowUpError(f"that follow-up is already kept ({item_id})")
        rows[item_id] = {"id": item_id, "date": due.isoformat(), "text": clean, "by": by.strip(), "campaign": code,
                         "at": ri.iso(ri.now_utc())}
        path = _root(data_dir) / MANUAL
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"version": 1, "items": rows}, indent=1, sort_keys=True), encoding="utf-8")
        tmp.replace(path)
        _log(data_dir, "add", item_id, by.strip(), clean, date=due.isoformat())
    return next(i for i in manual_items(data_dir, today=today) if i.id == item_id)


def apply_acts(items: Iterable[FollowUp], logged: Iterable[dict[str, Any]], *, today: date | None = None) -> list[FollowUp]:
    """The items with each person's latest act folded in: done (who, when, the note), deferred to a date (the reason; it is
    ``deferred`` until that day and then due or overdue from it), dropped (the reason). An act on an item no longer derived is
    left in the log, not shown."""
    today = today or date.today()
    latest: dict[str, dict[str, Any]] = {}
    for row in logged:
        if row.get("act") in ("done", "defer", "drop"):
            latest[str(row["id"])] = row
    out = []
    for item in items:
        act = latest.get(item.id)
        if act is None:
            out.append(item)
        elif act["act"] == "done":
            out.append(replace(item, state=FollowUpState.DONE, by=str(act.get("by") or ""), at=str(act.get("at") or ""),
                               why=str(act.get("why") or "")))
        elif act["act"] == "drop":
            out.append(replace(item, state=FollowUpState.DROPPED, by=str(act.get("by") or ""), at=str(act.get("at") or ""),
                               why=str(act.get("why") or "")))
        else:
            to = _day(act.get("to"))
            state = FollowUpState.DEFERRED if to is not None and to > today else standing(to or item.due, today)
            out.append(replace(item, state=state, by=str(act.get("by") or ""), at=str(act.get("at") or ""),
                               why=str(act.get("why") or ""), deferred_to=to))
    return out


# -- the whole list --------------------------------------------------------------------------------------------------------

def derive(data_dir: Path, community: Any, *, today: date | None = None) -> list[FollowUp]:
    """The follow-ups jason derives from what it holds (a campaign's cycle, the notice ledger, the response inbox, a request's
    clocks), in date order, with no person's act folded in. Reads disk only, and a source that is missing yields none."""
    data_dir = Path(data_dir)
    today = today or date.today()
    moment = campaign_funnel.moment_of(None, today)
    found: list[FollowUp] = []
    for part in (lambda: _cycle_items(data_dir, community, today, moment), lambda: _ledger_items(data_dir, today, moment),
                 lambda: _inbox_items(data_dir, today), lambda: _clock_items(data_dir, community, today)):
        try:
            found += part()
        except Exception:  # noqa: BLE001 - one unreadable source never hides the others (ages() says which is missing)
            continue
    seen: set[str] = set()
    return sorted((i for i in found if not (i.id in seen or seen.add(i.id))), key=lambda i: (i.due, i.kind.value, i.id))


def items(data_dir: Path, community: Any, *, today: date | None = None) -> list[FollowUp]:
    """Every follow-up: the derived ones and a person's own, with each person's acts folded in, in date order."""
    today = today or date.today()
    both = derive(data_dir, community, today=today) + manual_items(data_dir, today=today)
    return sorted(apply_acts(both, acts(data_dir), today=today), key=lambda i: (i.due, i.kind.value, i.id))


def select(found: Iterable[FollowUp], *, today: date | None = None, within: int = NEXT_DAYS, campaign: str = "", kind: str = "",
           state: str = "", overdue: bool = False, everything: bool = False) -> list[FollowUp]:
    """The items a view shows: by default what is overdue, due today, and due in the next ``within`` days (not done, dropped,
    or deferred); ``overdue`` only the overdue; ``everything`` every state and date. ``campaign``, ``kind``, ``state`` narrow."""
    today = today or date.today()
    want_kind = kind_of(kind) if kind else None
    want_state = state_of(state) if state else None
    code = (campaign or "").strip().upper()
    out = []
    for i in found:
        if code and code not in (i.campaign.upper(), i.subject.upper()):
            continue
        if want_kind is not None and i.kind is not want_kind:
            continue
        if want_state is not None and i.state is not want_state:
            continue
        if not (everything or want_state is not None):
            if not i.open:
                continue
            if overdue and i.state is not FollowUpState.OVERDUE:
                continue
            if not overdue and i.due > today + timedelta(days=within):
                continue
        out.append(i)
    return out


def _find(data_dir: Path, community: Any, item_id: str, today: date) -> FollowUp:
    wanted = (item_id or "").strip()
    for i in items(data_dir, community, today=today):
        if i.id == wanted:
            return i
    raise FollowUpError(f"no follow-up {item_id!r} (jason followups --all lists them with their ids)")


def _act(data_dir: Path, community: Any, act: str, item_id: str, by: str, why: str = "", today: date | None = None,
         **detail: Any) -> FollowUp:
    today = today or date.today()
    _need(by, "--by")
    with _locked(f"follow-up {act}"):
        _find(data_dir, community, item_id, today)
        _log(data_dir, act, item_id.strip(), by.strip(), why.strip(), **detail)
    return _find(data_dir, community, item_id, today)


def done(data_dir: Path, community: Any, item_id: str, *, by: str, note: str = "", today: date | None = None) -> FollowUp:
    """A person says the follow-up was done. Needs ``by``; ``note`` says what was done."""
    return _act(data_dir, community, "done", item_id, by, note, today)


def defer(data_dir: Path, community: Any, item_id: str, *, to: date, by: str, why: str, today: date | None = None) -> FollowUp:
    """A person puts a follow-up off to a later day. Needs ``by``, a day after today, and the reason."""
    today = today or date.today()
    if not isinstance(to, date) or isinstance(to, datetime):
        raise FollowUpError("--to is required with --defer: the day it comes back, YYYY-MM-DD")
    if to <= today:
        raise FollowUpError(f"--to must be a day after today ({today.isoformat()}): a deferral says when it comes back")
    if not str(why or "").strip():
        raise FollowUpError("--why is required with --defer: the reason it is put off")
    return _act(data_dir, community, "defer", item_id, by, why, today, to=to.isoformat())


def drop(data_dir: Path, community: Any, item_id: str, *, by: str, why: str, today: date | None = None) -> FollowUp:
    """A person says the follow-up is not to be done. Needs ``by`` and the reason; the item stays on file, shown dropped."""
    if not str(why or "").strip():
        raise FollowUpError("--why is required with --drop: the reason it is not to be done")
    return _act(data_dir, community, "drop", item_id, by, why, today)


# -- how old what it reads is ----------------------------------------------------------------------------------------------

def ages(data_dir: Path, community: Any = None, *, today: date | None = None, now: datetime | None = None) -> dict[str, Any]:
    """Each source the items are read from: whether it is on disk, when it was last written (or checked, or synced), how old
    that is, and, for one that is missing, why that matters."""
    data_dir = Path(data_dir)
    moment = campaign_funnel.moment_of(now, today)

    def file(name: str, path: Path, why: str) -> dict[str, Any]:
        stamp = campaign_funnel.mtime(path)
        return {"source": name, "exists": path.is_file(), "at": stamp, "ageHours": campaign_funnel.age_hours(moment, stamp),
                "reason": "" if path.is_file() else why}

    checks = ri.channel_status(data_dir, now=moment)
    last_ok = max((c["lastOk"] for c in checks if c["lastOk"]), default="")
    ledger = campaign_funnel.read_ledger(data_dir, moment)
    return {
        "at": ri.iso(moment),
        "campaign": file("the campaign record", data_dir / campaigns.STORE,
                         "no campaign is recorded, so no cycle's dates are derived (jason campaigns)"),
        "catalog": file("the sent-copy catalog", data_dir / "forms" / "references.json",
                        "no copy has been recorded as sent, so who is outstanding cannot be counted"),
        "inbox": {**file("the response inbox", ri.responses_dir(data_dir) / ri.INBOX,
                         "no check has been run, so no answer is counted (jason responses --check)"),
                  "lastCheck": last_ok, "lastCheckAgeHours": campaign_funnel.age_hours(moment, last_ok)},
        "ledger": {"source": "the notice ledger", "exists": ledger["exists"], "at": ledger["syncedAt"],
                   "ageHours": ledger["ageHours"], "reason": ledger["reason"]},
        "person": file("a person's own items", _root(data_dir) / MANUAL, "no item has been added by a person"),
    }


def source_age(item: FollowUp, known: dict[str, Any]) -> dict[str, Any]:
    """What an item was read from and how old that is, in a line of words and numbers."""
    def hours(row: dict[str, Any], key: str = "ageHours") -> float | None:
        return row.get(key)

    if item.source == "ledger":
        row = known["ledger"]
        return {"source": row["source"], "ageHours": hours(row), "says": (f"the notice ledger was synced {row['at'] or 'never'}"
                                                                         if row["exists"] else row["reason"])}
    if item.source == "campaign":
        row, cat = known["campaign"], known["catalog"]
        return {"source": row["source"], "ageHours": hours(row), "catalogAgeHours": hours(cat),
                "says": (f"the campaign record written {row['at'] or 'never'}; the sent-copy catalog "
                         + (f"written {cat['at']}" if cat["exists"] else "is not on disk"))}
    if item.source in ("inbox", "clock"):
        row = known["inbox"]
        return {"source": row["source"], "ageHours": hours(row, "lastCheckAgeHours"),
                "says": (f"the inbox was last checked {row['lastCheck']}" if row["lastCheck"] else
                         "no check has succeeded, so an answer that arrived is not counted")}
    row = known["person"]
    return {"source": row["source"], "ageHours": hours(row), "says": "a person's own item"}


__all__ = ["ACTS", "Basis", "CLOCK_KINDS", "FollowUp", "FollowUpError", "FollowUpKind", "FollowUpState", "MANUAL", "NEXT_DAYS",
           "PROPOSED_DAYS", "REMIND_OPTION", "acts", "add_manual", "ages", "apply_acts", "defer", "derive", "done", "drop",
           "ident", "items", "kind_of", "manual_items", "select", "source_age", "standing", "state_of"]
