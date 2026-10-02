"""Every request of the association with its kind, its clock, its owner, and whether the answer is on time.

``handle`` reads the stored PayHOA requests (``request_links.load_requests``), classifies each (``responses.classify``),
and applies its kind's rule: the day it was received (the request's creation, in the association's time zone), the
acknowledgment due (a proposed policy's days, if any), the answer due by the rule's clock, and the response: the first
admin comment the owner can see, or the request's closing (completed, approved) if that came first. Closing is kept
apart: a maintenance request is answered when the owner is told the plan, and closed when the work is done. The
standing is answered on time, answered late,
open and overdue, open and due soon (within five days), or open. A statute's clock is the notice catalog's
(``notice_catalog.requirement(key).timing``); a business-day clock skips weekends but not holidays, so it is the
earliest the deadline can fall (docs/notices.md).

It reads disk only. It never approves, denies, or assigns a request; the owner it names is the schedule's role.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from jason.community.responses import ClockSource, ResponseKind, ResponseRule, classify, rules_for

SOON_DAYS = 5
DONE = ("complete", "approved", "denied", "closed")
REQUEST_ANCHORS = ("REQUEST_RECEIVED", "REQUEST_MAILED", "APPLICATION_RECEIVED", "SERVICE")


def _local_day(value: str | None, tz: str) -> date | None:
    if not value:
        return None
    try:
        when = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if when.tzinfo is not None:
        from zoneinfo import ZoneInfo

        when = when.astimezone(ZoneInfo(tz))
    return when.date()


def _add(day: date, days: int, business: bool) -> date:
    from jason.community.notices import Unit, _shift

    return _shift(day, days, Unit.BUSINESS_DAYS if business else Unit.CALENDAR_DAYS)


def due_day(rule: ResponseRule, received: date) -> tuple[date | None, str]:
    """The last day for the answer, and the clock's words."""
    if rule.source is ClockSource.STATUTE and rule.notice:
        from jason.community.notice_catalog import requirement

        req = requirement(rule.notice)
        for t in req.timing if req else ():
            if t.anchor.name in REQUEST_ANCHORS:
                _, last = t.window(received)
                return last, f"{t.describe()} ({req.statute})"
        return None, f"{rule.notice}: no clock from the request ({rule.authority})"
    if rule.days:
        unit = "business days" if rule.business_days else "days"
        return _add(received, rule.days, rule.business_days), f"within {rule.days} {unit} ({rule.authority})"
    return None, rule.authority or "no clock"


@dataclass(frozen=True)
class Handled:
    request: dict[str, Any]
    kind: ResponseKind
    why: str
    rule: ResponseRule | None
    received: date | None
    due: date | None
    clock: str
    acknowledge_due: date | None
    acknowledged: date | None
    answered: date | None              # the first response: an admin comment, or the closing if earlier
    closed: date | None
    standing: str

    @property
    def open(self) -> bool:
        return self.answered is None


def _standing(due: date | None, answered: date | None, today: date) -> str:
    if answered is not None:
        if due is None:
            return "answered"
        return "answered on time" if answered <= due else f"answered late ({(answered - due).days} days)"
    if due is None:
        return "open, no clock"
    if today > due:
        return f"OVERDUE ({(today - due).days} days)"
    if today >= due - timedelta(days=SOON_DAYS):
        return "due soon"
    return "open"


def handle(community: Any, data_dir: Path, *, today: date | None = None) -> list[Handled]:
    from jason.tasks.request_links import load_requests

    today = today or date.today()
    tz = getattr(community, "timezone", lambda: "America/Los_Angeles")() if callable(getattr(community, "timezone", None)) \
        else "America/Los_Angeles"
    kind_rules, by_kind = rules_for(community)
    out = []
    for r in load_requests(Path(data_dir), community):
        kind, why = classify(r.get("form") or "", f"{r.get('title', '')} {r.get('message', '')}", kind_rules)
        rule = by_kind.get(kind) or by_kind.get(ResponseKind.OTHER)
        received = _local_day(r.get("created"), tz)
        due, clock = due_day(rule, received) if rule and received else (None, "")
        ack_due = _add(received, rule.acknowledge_days, True) if rule and received and rule.acknowledge_days else None
        admin = sorted(d for d in (_local_day(c.get("at"), tz) for c in r.get("comments") or [] if c.get("admin")) if d)
        acknowledged = admin[0] if admin else None
        done = str(r.get("status") or "").lower() in DONE
        closed = (_local_day(r.get("completed"), tz) or _local_day(r.get("updated"), tz)) if done else None
        answered = min((d for d in (acknowledged, closed) if d), default=None)
        out.append(Handled(r, kind, why, rule, received, due, clock, ack_due, acknowledged, answered, closed,
                           _standing(due, answered, today)))
    return sorted(out, key=lambda h: (h.closed is not None, h.due or date.max, h.received or date.min))


def summary(found: list[Handled]) -> dict[str, Any]:
    """Open requests by standing, and the answered ones: on time against late, by kind."""
    from collections import Counter

    opened = Counter(h.standing.split(" (")[0] for h in found if h.open)
    timed = [h for h in found if not h.open and h.due]
    on_time = Counter(h.kind.value for h in timed if h.standing == "answered on time")
    late = Counter(h.kind.value for h in timed if h.standing.startswith("answered late"))
    return {"open": dict(opened), "onTime": dict(on_time), "late": dict(late)}


def lines(found: list[Handled], *, limit: int = 40) -> list[str]:
    out = []
    for h in found[:limit]:
        r, rule = h.request, h.rule
        owner = rule.assignment if rule else "?"
        ack = ""
        if h.closed is None and h.acknowledge_due:
            ack = f"; acknowledged {h.acknowledged}" if h.acknowledged else f"; acknowledgment due {h.acknowledge_due}"
        out.append(f"- #{r['id']} {h.kind.value} [{h.standing}] {r.get('unit') or 'unit ?'}: \"{(r.get('title') or '')[:70]}\""
                   f" received {h.received}; due {h.due or '-'} {h.clock and '(' + h.clock[:90] + ')'}{ack}; owner "
                   f"{owner}; classified by {h.why}")
        if h.open and rule and rule.first_step:
            out.append(f"    next: {rule.first_step}")
    return out


__all__ = ["Handled", "due_day", "handle", "lines", "summary"]
