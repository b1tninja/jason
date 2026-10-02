"""The owner information cycle (Civil Code 4040, 4041) in one place: where every current owner stands, what to do
next, and the PayHOA writes that would bring the record up to date, never over newer information.

PayHOA is the record (``jason.community.tags``). For each current owner:

- **the election** is their PayHOA delivery tags, and only those decide delivery (``notice_delivery``); without one the
  law sends first-class mail (4040(a)(2)), which the tag "Notices by Mail" makes visible to PayHOA's filters;
- **an answer this cycle** (a signed-in PayHOA form, a returned PDF or paper form typed in, any form sent since the
  solicitation opened and after the unit's latest deed) sets the tags, and the year's "Owner Info" tag;
- **an earlier answer** (last year's or older: the 2024 Resident Registration form) sets the delivery tags only as an
  earlier written election allows (``EarlierElections``); the owner confirms or changes it this cycle.

Answers live in tags, the profile, and additional owner records, never in custom fields (PayHOA's are untyped text).
``ledger`` gives each owner a status and the next action. ``plan_writes`` lists every tag write that would follow, each
with its reason, read against PayHOA as it is now: a delivery tag is only added where the owner has none, and a
this-cycle answer's changes are applied. ``execute`` performs them, on a person's --yes.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Any, Iterable

from jason.community.forms import AnswerCycle, Freshness
from jason.community.tags import PayhoaTag, TagPurpose, TagScope, tagged


class OwnerStatus(Enum):
    ANSWERED = "answered this cycle"
    ELECTED = "election on file in PayHOA"
    EARLIER_ELECTION = "an earlier written election, applied (confirm this cycle)"
    EARLIER_ANSWER = "an earlier answer to confirm"
    NO_ELECTION = "no election: first-class mail (4040(a)(2))"


@dataclass
class OwnerInfo:
    unit_id: int
    unit: str
    membership_id: int
    name: str
    status: OwnerStatus
    delivery: str                       # how notices go now, from the tags: "mail", "email", "email and mail"
    answer: Any = None                  # the member's latest matched answer (member_preferences.Matched), if any
    actions: list[str] = field(default_factory=list)


def _delivery_text(owner: Any) -> str:
    return " and ".join(c.value for c in owner.channels)


def earlier_election(answer: Any, member_tags: set[str], tags: Iterable[PayhoaTag], rule: Any,
                     today: date) -> list[str]:
    """The delivery channels ("email", "mail") an earlier answer elects under ``rule`` (``EarlierElections``), or none:
    it must be from before this cycle, sent after the unit's latest deed, no older than the rule allows, matched to the
    owner by the email PayHOA has for them (when the rule asks), and the owner must have no delivery election in PayHOA."""
    from jason.community.forms import parse_date

    if rule is None or not rule.apply or answer is None or answer.freshness is Freshness.CURRENT:
        return []
    if any("after this answer" in n for n in answer.notes):
        return []
    if rule.require_email_match and answer.how != "email":
        return []
    sent = parse_date(answer.submitted[:10]) if answer.submitted else None
    if sent is None or (today - sent).days > rule.max_age_days:
        return []
    if tagged(tuple(tags), member_tags, TagPurpose.NOTICE_DELIVERY, TagScope.MEMBER):
        return []
    return sorted(set(re.findall(r"email|mail", (answer.record or {}).get("delivery", ""))))


def ledger(found: Any, matched: Iterable[Any], tags: Iterable[PayhoaTag], cycle: AnswerCycle | None, *,
           earlier: Any = None, today: date | None = None) -> list[OwnerInfo]:
    """Each current owner (from ``notice_delivery.plan``) with their latest answer (``member_preferences.match``,
    latest per unit), a status, and the next action. ``earlier`` (``EarlierElections``) lets an earlier written
    election set the delivery tags."""
    today = today or date.today()
    tags = tuple(tags)
    answers = {(m.unit.unit_id, m.owner.membership_id): m for m in matched if m.latest and m.owner and m.unit}
    answered_tag = {t.name.casefold() for t in tags if t.purpose is TagPurpose.ANSWERED
                    and (cycle is None or t.value == str(cycle.year))}
    out = []
    for o in found.owners:
        answer = answers.get((o.unit_id, o.membership_id))
        elected = tagged(tags, o.member_tags, TagPurpose.NOTICE_DELIVERY, TagScope.MEMBER)
        row = OwnerInfo(o.unit_id, o.unit, o.membership_id, o.name, OwnerStatus.NO_ELECTION, _delivery_text(o), answer)
        if (o.member_tags & answered_tag) or (answer and answer.freshness is Freshness.CURRENT and answer.tag_changes):
            row.status = OwnerStatus.ANSWERED
            row.actions = list(answer.tag_changes) if answer else []
            if answer and answer.record.get("secondary delivery"):
                row.actions.append("add the second address as an additional owner record (no invitation), tagged "
                                   "'Additional Deliveries'")
            if answer and answer.choices.get("representative-name"):
                row.actions.append("add the legal representative as a person record on the unit (no invitation), "
                                   "tagged 'Legal Representative'")
        elif elected:
            row.status = OwnerStatus.ELECTED
            if answer and answer.confirm:
                row.actions = ["ask to confirm in this cycle's form: " + "; ".join(answer.confirm)]
        elif earlier_election(answer, o.member_tags, tags, earlier, today):
            channels = earlier_election(answer, o.member_tags, tags, earlier, today)
            row.status = OwnerStatus.EARLIER_ELECTION
            row.actions = [f"tag notices by {' and '.join(channels)} (written election of {answer.submitted[:10]}, "
                           "the owner's own email)", "ask to confirm in this cycle's form"]
        elif answer and (answer.confirm or answer.record):
            row.status = OwnerStatus.EARLIER_ANSWER
            if any("after this answer" in n for n in answer.notes):
                row.actions = ["the earlier answer predates the unit's latest deed: ask afresh in this cycle's form"]
            else:
                row.actions = ["ask to confirm in this cycle's form"]
            row.actions.append("tag 'Notices by Mail' (the law's default) until they answer")
        else:
            row.actions = ["tag 'Notices by Mail' (the law's default) until they answer"]
        out.append(row)
    return out


def summary(rows: list[OwnerInfo], cycle: AnswerCycle | None, today: date) -> dict[str, Any]:
    return {
        "currentOwners": len(rows),
        "byStatus": dict(Counter(r.status.value for r in rows)),
        "delivery": dict(Counter(r.delivery for r in rows)),
        "deadlines": [{"what": name, "date": day.isoformat(), "daysLeft": left}
                      for name, day, left in (cycle.deadlines(today) if cycle else [])],
    }


# -- the writes -------------------------------------------------------------------------------------------------------

@dataclass
class Write:
    kind: str            # "member tag +", "member tag -", "unit tag +", "unit tag -"
    target: int          # a membership or unit id
    label: str           # who or what, for the person reading the plan
    value: str           # the tag, or the field's text
    why: str


def plan_writes(rows: list[OwnerInfo], found: Any, tags: Iterable[PayhoaTag], *, earlier: Any = None,
                today: date | None = None) -> list[Write]:
    """Every PayHOA tag write the ledger calls for: the default delivery tag for owners with no election and no answer
    this cycle; an earlier written election's tags; and a this-cycle answer's tag changes."""
    tags = tuple(tags)
    mail = next((t for t in tags if t.purpose is TagPurpose.NOTICE_DELIVERY and t.value == "mail"), None)
    owners = {(o.unit_id, o.membership_id): o for o in found.owners}
    out: list[Write] = []
    for r in rows:
        who = f"{r.unit}: {r.name}"
        if r.status is OwnerStatus.ANSWERED and r.answer is not None:
            for change in r.answer.tag_changes:
                sign, rest = change[0], change[1:]
                name, scope = re.match(r"(.+?) \((member|unit)\)", rest).groups()
                target = r.membership_id if scope == "member" else r.unit_id
                out.append(Write(f"{scope} tag {sign}", target, who, name, f"this cycle's answer ({r.answer.source})"))
        elif r.status is OwnerStatus.EARLIER_ELECTION:
            o = owners.get((r.unit_id, r.membership_id))
            for channel in earlier_election(r.answer, o.member_tags if o else set(), tags, earlier, today or date.today()):
                tag = next((t for t in tags if t.purpose is TagPurpose.NOTICE_DELIVERY and t.value == channel), None)
                if tag:
                    out.append(Write("member tag +", r.membership_id, who, tag.name,
                                     f"written election of {r.answer.submitted[:10]} from the owner's own email "
                                     f"({r.answer.source})"))
        elif r.status in (OwnerStatus.NO_ELECTION, OwnerStatus.EARLIER_ANSWER) and mail:
            o = owners.get((r.unit_id, r.membership_id))
            if o is not None and not tagged(tags, o.member_tags, TagPurpose.NOTICE_DELIVERY, TagScope.MEMBER):
                out.append(Write("member tag +", r.membership_id, who, mail.name,
                                 "no election on file: the law sends first-class mail (4040(a)(2))"))
    return out


def execute(client: Any, org_id: int, writes: list[Write], *,
            member_tag_rows: dict[int, list[dict[str, Any]]] | None = None, batch: int = 25) -> dict[str, int]:
    """Perform the writes: member tags added in batches by tag, removals by the member's tag row (from
    ``member_tag_rows``, the members' tags as read live), and unit tags. Returns counts by kind."""
    from collections import defaultdict

    done: Counter[str] = Counter()
    adds: dict[str, list[int]] = defaultdict(list)
    for w in writes:
        if w.kind == "member tag +":
            adds[w.value].append(w.target)
    for tag, ids in adds.items():
        for i in range(0, len(ids), batch):
            client.update_member_tags(org_id, ids[i:i + batch], add=[tag])
        done["member tag +"] += len(ids)
    for w in writes:
        if w.kind == "member tag -":
            rows = [t for t in (member_tag_rows or {}).get(w.target, []) if t.get("tag") == w.value]
            if rows:
                client.update_member_tags(org_id, [w.target], remove=[int(rows[0]["id"])])
                done["member tag -"] += 1
        elif w.kind == "unit tag +":
            client.add_unit_tag(org_id, [w.target], w.value)
            done["unit tag +"] += 1
        elif w.kind == "unit tag -":
            client.remove_unit_tag(org_id, [w.target], w.value)
            done["unit tag -"] += 1
    return dict(done)


# What an answer can ask that jason does not write: a person enters it (the merge plan's rule), so the request stays open.
FOR_A_PERSON = ("email", "mailing address", "secondary delivery", "property manager")
PERSON_FIELDS = ("representative-name", "representative-email", "representative-phone", "representative-mailing-address")


@dataclass
class ToComplete:
    """An owner's PayHOA request and whether jason has recorded all of it: ``left`` is what is still to do (a tag
    write not yet made, or something a person enters); empty, the request can be marked complete."""

    submission_id: int
    unit: str
    name: str
    membership_id: int
    left: list[str] = field(default_factory=list)


def to_complete(rows: list[OwnerInfo], writes: list[Write]) -> list[ToComplete]:
    """Each owner's latest answer that came through the PayHOA form, with what is left before it is fully recorded."""
    out = []
    for r in rows:
        a = r.answer
        if a is None or not str(a.source).startswith("payhoa:") or not a.latest:
            continue
        item = ToComplete(int(str(a.source).split(":", 1)[1]), r.unit, r.name, r.membership_id)
        pending = [w for w in writes if (w.kind.startswith("member") and w.target == r.membership_id)
                   or (w.kind.startswith("unit") and w.target == r.unit_id)]
        item.left += [f"{w.kind} {w.value}" for w in pending]
        item.left += [f"a person enters the {k}" for k in FOR_A_PERSON if a.record.get(k)]
        item.left += ["a person enters the legal representative"] if any(a.choices.get(f) for f in PERSON_FIELDS) else []
        out.append(item)
    return out


def complete(client: Any, org_id: int, item: ToComplete, comment: str) -> None:
    """Mark the request complete and leave the owner the comment, emailed to them (``recipientMemberIds``)."""
    client.set_submission_complete(org_id, item.submission_id)
    if comment:
        client.add_submission_comment(item.submission_id, comment, notify_admins=False,
                                      recipient_member_ids=[item.membership_id])


__all__ = ["FOR_A_PERSON", "OwnerInfo", "OwnerStatus", "ToComplete", "Write", "complete", "earlier_election", "execute",
           "ledger", "plan_writes", "summary", "to_complete"]
