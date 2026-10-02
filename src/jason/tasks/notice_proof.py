"""Proof of notice: for one notice that went out, the evidence its requirement calls for, what is on file, what is
owed, and whether it went out in time.

A notice's ledger (``notice_ledger``: each delivery attempt and its outcome, read from PayHOA) shows who was reached
and what follow-ups are owed. Its requirement (``notice_catalog``: the statute's recipients, methods, clock, content,
and evidence), made stricter by the governing documents (``notice_catalog.effective``), says what has to be shown.
``build`` puts the two together with the dates a person supplies (the event, the day it was mailed or sent, the day
it was posted) and the records a person says are on file (the notice as sent, the declaration of mailing), and gives
one record per notice: each piece of evidence with its standing, the window and whether the send fell in it, and the
members reached only after the deadline. jason does not decide that notice was sufficient: a member reached late, or
a window missed, is a finding for the board or counsel (often the cure is a new date for the meeting or hearing).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Iterable

from jason.community.notices import Evidence, NoticeKind, NoticeRequirement, Timing
from jason.tasks.notice_ledger import Standing


class Status(Enum):
    HAVE = "on file"
    MISSING = "to attach"
    OWED = "owed"


@dataclass(frozen=True)
class ProofItem:
    evidence: Evidence
    status: Status
    detail: str = ""


@dataclass
class ProofOfNotice:
    requirement: NoticeRequirement
    ledger_key: str = ""
    clocks: tuple[Timing, ...] = ()
    event: date | None = None
    delivered: date | None = None          # the day it went out: deposited, transmitted, or posted
    windows: list[tuple[Timing, date | None, date | None]] = field(default_factory=list)
    on_time: bool | None = None            # None: no clock with a number, or no dates to judge by
    items: list[ProofItem] = field(default_factory=list)
    members: int = 0
    reached: int = 0
    late: list[str] = field(default_factory=list)        # reached only after the last day
    unreached: list[str] = field(default_factory=list)   # owed delivery and not reached
    notes: list[str] = field(default_factory=list)

    @property
    def complete(self) -> bool:
        """Every piece of evidence on file, the send in its window, and no member owed or late."""
        return (all(i.status is Status.HAVE for i in self.items) and self.on_time is not False
                and not self.late and not self.unreached)


def _day(text: str) -> date | None:
    try:
        return date.fromisoformat(str(text)[:10])
    except ValueError:
        return None


def build(requirement: NoticeRequirement, *, clocks: Iterable[Timing] | None = None, event: date | None = None,
          sent: date | None = None, posted: date | None = None, standings: list[Standing] | None = None,
          general: bool = False, individual: Iterable[int] = (), have: Iterable[Evidence] = (),
          ledger_key: str = "", notes: Iterable[str] = ()) -> ProofOfNotice:
    """The proof-of-notice record. ``general``: the notice was also posted where the annual policy statement
    designates, so the posting delivered it to everyone but the members in ``individual`` (who asked for individual
    delivery, 4045(b)). ``sent`` defaults to the earliest attempt in the ledger; mail is delivered on deposit (4050(b))
    and email on transmission (4050(c))."""
    clocks = tuple(clocks if clocks is not None else requirement.timing)
    have = set(have)
    individual = set(individual)
    standings = standings or []
    if sent is None:
        days = [d for s in standings for a in s.attempts if (d := _day(a.sent_at))]
        sent = min(days) if days else None
    delivered = posted if general and posted else sent
    out = ProofOfNotice(requirement, ledger_key, clocks, event, delivered, notes=list(notes))
    last_day: date | None = None
    for t in clocks:
        first, last = t.window(event) if event else (None, None)
        out.windows.append((t, first, last))
        if event and t.delivery and (t.least is not None or t.most is not None):
            if last is not None:
                last_day = last if last_day is None else min(last_day, last)
            if delivered is not None:
                ok = (first is None or delivered >= first) and (last is None or delivered <= last)
                out.on_time = ok if out.on_time is None else (out.on_time and ok)
    out.members = len(standings)
    for s in standings:
        if s.reached:
            out.reached += 1
            first_reached = min((d for a in s.attempts if a.status.reached and (d := _day(a.sent_at))), default=None)
            covered = general and posted is not None and s.membership_id not in individual
            if last_day and first_reached and first_reached > last_day and not covered:
                out.late.append(f"{s.unit or 'unit ?'} (member {s.membership_id}): reached {first_reached}, after {last_day}")
        elif not (general and s.membership_id not in individual):
            out.unreached.append(f"{s.unit or 'unit ?'} (member {s.membership_id})")
    owed = sum(1 for s in standings for f, _ in s.follow_ups if f.resend)
    asks = sum(1 for s in standings for f, _ in s.follow_ups if not f.resend)
    for evidence in requirement.proof():
        out.items.append(_item(evidence, requirement, have, standings, event, posted, general, owed, asks, out))
    if requirement.caveat:
        out.notes.append(f"For counsel: {requirement.caveat}")
    if out.late:
        out.notes.append("A member reached only after the last day was not given the notice in time: a finding for the "
                         "board or counsel (a new date for the meeting or hearing, and a new notice, is the usual cure).")
    return out


def _item(evidence: Evidence, requirement: NoticeRequirement, have: set[Evidence], standings: list[Standing],
          event: date | None, posted: date | None, general: bool, owed: int, asks: int, out: ProofOfNotice) -> ProofItem:
    if evidence in have:
        return ProofItem(evidence, Status.HAVE)
    if evidence is Evidence.DELIVERY_LEDGER:
        if standings:
            return ProofItem(evidence, Status.HAVE, f"{out.reached} of {out.members} members reached")
        return ProofItem(evidence, Status.MISSING, "jason notices KEY --sync reads it from PayHOA")
    if evidence is Evidence.RECIPIENTS:
        if standings:
            return ProofItem(evidence, Status.HAVE, f"{out.members} members in the ledger; keep the send plan "
                                                    "(jason delivery --notice RULE --ids FILE) as of the record date")
        return ProofItem(evidence, Status.MISSING, "jason delivery --notice RULE --ids FILE")
    if evidence is Evidence.FOLLOW_UPS:
        if not standings:
            return ProofItem(evidence, Status.MISSING, "no ledger yet")
        if owed:
            return ProofItem(evidence, Status.OWED, f"{owed} resend(s) owed" + (f"; {asks} address request(s)" if asks else ""))
        return ProofItem(evidence, Status.HAVE, "none owed" + (f"; {asks} address request(s) to make" if asks else ""))
    if evidence is Evidence.POSTING:
        if posted:
            return ProofItem(evidence, Status.HAVE, f"posted {posted}; keep the dated photo or capture")
        if requirement.kind is NoticeKind.GENERAL and not general:
            return ProofItem(evidence, Status.MISSING, "not posted: the individual deliveries are the general notice "
                                                       "(4045(a)(1)), so every member must be reached")
        return ProofItem(evidence, Status.MISSING, "where and when it was posted")
    if evidence is Evidence.ANCHOR_DATE:
        return ProofItem(evidence, Status.HAVE, str(event)) if event else ProofItem(evidence, Status.MISSING)
    return ProofItem(evidence, Status.MISSING)


def lines(p: ProofOfNotice) -> list[str]:
    r = p.requirement
    out = [f"Proof of notice: {r.title} [{r.key}; {r.statute}]" + (f" (ledger {p.ledger_key})" if p.ledger_key else "")]
    for t, first, last in p.windows:
        span = (f": from {first}" if first else "") + (f" through {last}" if last else "") if (first or last) else ""
        out.append(f"  clock: {t.describe()}{span}")
    if p.delivered:
        judged = {True: "in time", False: "OUTSIDE the window", None: "not judged"}[p.on_time]
        out.append(f"  went out {p.delivered}: {judged}")
    if p.members:
        out.append(f"  members: {p.reached} of {p.members} reached; {len(p.unreached)} not reached; "
                   f"{len(p.late)} reached late")
    out.append("  evidence:")
    for i in p.items:
        out.append(f"    [{i.status.value}] {i.evidence.value}" + (f" ({i.detail})" if i.detail else ""))
    for who in p.unreached:
        out.append(f"  not reached: {who}")
    for who in p.late:
        out.append(f"  late: {who}")
    out += [f"  note: {n}" for n in p.notes]
    out.append("  complete" if p.complete else "  not yet complete")
    return out


__all__ = ["ProofItem", "ProofOfNotice", "Status", "build", "lines"]
