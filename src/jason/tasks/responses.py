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

import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from jason.community.responses import ClockSource, ResponseKind, ResponseRule, classify, rules_for
from jason.community.topics import Topic

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
    payhoa_due: date | None = None     # a due date a person set in PayHOA, beside jason's clock
    hints: tuple[str, ...] = ()        # what PayHOA's own fields suggest (tags, its AI analysis): leads, not the kind

    @property
    def open(self) -> bool:
        return self.answered is None


# PayHOA's own fields on a request: what a person set there (a due date, tags, an assignee, approvals) and PayHOA's AI
# analysis. Most are usually empty (docs/responses.md); each is read only when it holds something.
PAYHOA_FIELDS = ("dueDate", "tags", "assigneeMembershipId", "assignedVendorId", "approvals", "approvalsGiven", "aiAnalysis")


def payhoa_fields(data_dir: Path) -> dict[int, dict[str, Any]]:
    """Each stored request's PayHOA fields that hold something: the due date, the tags' words, the assignee, the vendor,
    the approvals, and the AI analysis, by request id."""
    import json
    import sqlite3

    path = Path(data_dir) / "payhoa.db"
    if not path.is_file():
        return {}
    conn = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    try:
        rows = conn.execute("SELECT id, raw_json FROM requests").fetchall()
    finally:
        conn.close()
    out: dict[int, dict[str, Any]] = {}
    for rid, raw in rows:
        data = json.loads(raw or "{}")
        held = {k: data.get(k) for k in PAYHOA_FIELDS if data.get(k) not in (None, "", [], {}, 0)}
        if "tags" in held:
            held["tags"] = [str(t.get("tag") or "") for t in held["tags"] if isinstance(t, dict) and t.get("tag")]
        if held:
            out[int(rid)] = held
    return out


def payhoa_hints(fields: dict[str, Any], kind: ResponseKind, kind_rules: tuple) -> tuple[str, ...]:
    """What PayHOA's fields suggest beside jason's kind. A tag or the AI analysis that reads as another kind (by the
    same words rows) is a hint for a person to weigh, never a reclassification."""
    words_only = tuple(k for k in kind_rules if not k.forms)
    out = []
    for tag in fields.get("tags") or []:
        said, _ = classify("", tag, words_only)
        note = "" if said is ResponseKind.OTHER else (" (agrees)" if said is kind else f" (reads as {said.value})")
        out.append(f"PayHOA tag \"{tag}\"{note}")
    ai = fields.get("aiAnalysis")
    if ai:
        text = ai if isinstance(ai, str) else str(ai)
        said, _ = classify("", text, words_only)
        if said not in (ResponseKind.OTHER, kind):
            out.append(f"PayHOA's AI analysis reads as {said.value} (a lead; jason's kind stands)")
    if fields.get("assigneeMembershipId"):
        out.append(f"assigned in PayHOA (membership {fields['assigneeMembershipId']})")
    if fields.get("assignedVendorId"):
        out.append(f"a vendor assigned in PayHOA ({fields['assignedVendorId']})")
    if fields.get("approvals") or fields.get("approvalsGiven"):
        out.append(f"PayHOA approvals: {fields.get('approvalsGiven') or 0} given")
    return tuple(out)


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
    fields = payhoa_fields(Path(data_dir))
    out = []
    for r in load_requests(Path(data_dir), community):
        own = fields.get(int(r["id"]), {})
        if own:
            r = {**r, "payhoa": own}
        kind, why = classify_request(r, kind_rules)
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
                           _standing(due, answered, today), _local_day(own.get("dueDate"), tz) if own else None,
                           payhoa_hints(own, kind, kind_rules) if own else ()))
    return sorted(out, key=lambda h: (h.closed is not None, h.due or date.max, h.received or date.min))


# The topics whose threads are maintenance requests when the subject names no kind. They are the topics' values (a
# bare "maintenance" never matched "maintenance and repairs"); utilities and bins are left out, because an owner's
# thread about the meter reader or the bins is rarely a repair (measured against the gold set, docs/responses.md).
MAINTENANCE_TOPICS = frozenset({Topic.MAINTENANCE.value, Topic.LANDSCAPING.value, Topic.PESTS.value})


def _messages_by_thread(data_dir: Path) -> dict[str, list[dict[str, Any]]]:
    """The stored messages of each thread, in date order."""
    from jason.tasks.gmail import CORRESPONDENCE, _load

    by_thread: dict[str, list[dict[str, Any]]] = {}
    for m in _load(Path(data_dir), CORRESPONDENCE).get("messages") or []:
        by_thread.setdefault(m["threadId"], []).append(m)
    for items in by_thread.values():
        items.sort(key=lambda m: m["at"])
    return by_thread


def owner_threads(data_dir: Path, community: Any, *, today: date | None = None) -> list[dict[str, Any]]:
    """The threads that can be a member's request: between the association and an owner, with no business on it, not
    the association's own notice or internal mail, and not joined to a PayHOA request (``request_links``)."""
    from jason.tasks.request_links import request_links
    from jason.tasks.threads import threads

    linked = {t["threadId"] for r in request_links(Path(data_dir), community)["rows"] for t in r["ownerThreads"]}
    out = []
    for t in threads(Path(data_dir), community, today=today)["rows"]:
        owners = [p for p in t["parties"] if p.startswith("owner of ")]
        if not owners or t["domains"] or t["threadId"] in linked or t["status"] in ("notice", "internal"):
            continue
        out.append({**t, "owners": owners})
    return out


def classify_request(r: dict[str, Any], kind_rules: tuple) -> tuple[ResponseKind, str]:
    """A PayHOA request's kind from its form and its title and message."""
    return classify(r.get("form") or "", f"{r.get('title', '')} {r.get('message', '')}", kind_rules)


# A subject that reads as the association's own word (a notice, a schedule, a survey, an update, a proposal, a reply
# to a violation) or a vendor's: a repair or a conduct it names is not the owner asking. It never overrides a kind the
# subject names outright (a notice of intent to rent is still a rental application).
ANNOUNCEMENT = re.compile(r"(?i)\bnotice\b|\bscheduled\b|\bsurvey\b|\bproposal\b|\bintro(?:duction)?\b|\bupdate\b|"
                          r"\binspections?\b|\bnew\s+vendor\b|"
                          r"\bmeeting\b|^\s*(?:re:\s*)?your\b|\binsurance\s+claim\b|^\s*re:.*\bviolation\b|"
                          r"\bform\s+submission\b")
# Words that make a maintenance topic business or a question, not a repair: a contract, an expense, a quote, an
# invoice, whose responsibility it is.
NOT_A_REPAIR = re.compile(r"(?i)\bcontracts?\b|\bexpenses?\b|\bquotes?\b|\binvoices?\b|\bresponsib\w*|"
                          r"\bliab(?:le|ility)\b|^\s*\(no subject\)\s*$")
_LOOSE = (ResponseKind.MAINTENANCE, ResponseKind.COMPLAINT)


def classify_email(subject: str, topics: list[str] | tuple[str, ...], kind_rules: tuple) -> tuple[ResponseKind, str]:
    """An email thread's kind from its subject (the words rows only), else maintenance from a maintenance topic. A
    repair or a conduct named in the association's own notice or update is not a request (``ANNOUNCEMENT``)."""
    kind, why = classify("", subject, tuple(k for k in kind_rules if not k.forms))
    if kind in _LOOSE and ANNOUNCEMENT.search(subject):
        return ResponseKind.OTHER, "the association's own notice or update"
    if kind is ResponseKind.OTHER and MAINTENANCE_TOPICS & set(topics or []):
        if ANNOUNCEMENT.search(subject) or NOT_A_REPAIR.search(subject):
            return ResponseKind.OTHER, "a maintenance topic, but a notice or business"
        kind, why = ResponseKind.MAINTENANCE, "its topic"
    return kind, why


def thread_kind(t: dict[str, Any], items: list[dict[str, Any]], kind_rules: tuple) -> tuple[ResponseKind, str]:
    """An owner's thread's kind, as ``email_requests`` reads it (``items``: its messages in date order). Who started
    the thread is not read: the first message in the store is often the association's answer to a call or to mail
    synced earlier, so a thread it started can still be a member's request (measured, docs/responses.md)."""
    return classify_email(t["subject"], t.get("topics") or [], kind_rules)


def email_requests(community: Any, data_dir: Path, *, today: date | None = None) -> list[Handled]:
    """Members' requests made by email: a thread between the association and an owner (no business on it), not joined
    to a PayHOA request (``request_links``), whose subject names a kind (the words rules) or a maintenance topic. Its
    clock runs from the first message in; its response is the first message out after it. Email is read by its headers,
    so a kind comes from the subject alone; a request whose subject says nothing is left to ``jason replies``."""
    today = today or date.today()
    tz = "America/Los_Angeles"
    kind_rules, by_kind = rules_for(community)
    by_thread = _messages_by_thread(Path(data_dir))
    out = []
    for t in owner_threads(Path(data_dir), community, today=today):
        items = by_thread.get(t["threadId"], [])
        kind, why = thread_kind(t, items, kind_rules)
        if kind in (ResponseKind.OTHER, ResponseKind.QUESTION):
            continue
        first_in = next((m for m in items if m.get("direction") == "in"), None)
        if first_in is None:
            continue
        reply = next((m for m in items if m.get("direction") == "out" and m["at"] > first_in["at"]), None)
        rule = by_kind.get(kind) or by_kind.get(ResponseKind.OTHER)
        received = _local_day(first_in["at"], tz)
        due, clock = due_day(rule, received) if rule and received else (None, "")
        answered = _local_day(reply["at"], tz) if reply else None
        request = {"id": f"email:{t['threadId'][:10]}", "form": "email", "unit": t["owners"][0][len("owner of "):],
                   "title": t["subject"], "status": t["status"], "link": t["link"], "threadId": t["threadId"],
                   "topics": list(t.get("topics") or [])}
        out.append(Handled(request, kind, f"{why} (email subject)", rule, received, due, clock, None, answered, answered,
                           answered, _standing(due, answered, today)))
    return out


def acknowledgment(h: Handled, community: Any) -> str:
    """A first comment to the owner, for a person to read and send (``jason request-comment``). It names what was
    received and when, and a date only where the law or the documents set one: a proposed policy's day is the board's
    target, not a promise the association has made."""
    name = getattr(community, "name", "") or "the Association"
    kind = h.kind.value
    when = f"{h.received:%B} {h.received.day}, {h.received.year}" if h.received else "recently"
    lines = [f"Thank you. The Association received your {kind} on {when}, and it is being reviewed."]
    rule = h.rule
    if rule and h.due and rule.source is not ClockSource.POLICY:
        lines.append(f"Under {rule.authority}, the Association will respond by {h.due:%B} {h.due.day}, {h.due.year}.")
    else:
        lines.append("We will follow up with next steps.")
    if h.kind in (ResponseKind.ARCHITECTURAL, ResponseKind.SOLAR, ResponseKind.EV_CHARGER, ResponseKind.RENTAL,
                  ResponseKind.VARIANCE):
        lines.append("The Board decides applications at its meetings; we will let you know the meeting it is on.")
    lines.append(f"- {name}")
    return " ".join(lines[:-1]) + "\n\n" + lines[-1]


def summary(found: list[Handled]) -> dict[str, Any]:
    """Open requests by standing, and the answered ones: on time against late, by kind."""
    from collections import Counter

    opened = Counter(h.standing.split(" (")[0] for h in found if h.open)
    timed = [h for h in found if not h.open and h.due]
    on_time = Counter(h.kind.value for h in timed if h.standing == "answered on time")
    late = Counter(h.kind.value for h in timed if h.standing.startswith("answered late"))
    return {"open": dict(opened), "onTime": dict(on_time), "late": dict(late)}


def lines(found: list[Handled], *, limit: int = 40, sources: dict[str, dict[str, Any]] | None = None) -> list[str]:
    """A request a line, with its next step, what PayHOA's own fields hold, and (``sources``, by request id) the leads
    to where its answer is written."""
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
        if h.payhoa_due or h.hints:
            due = [f"due {h.payhoa_due} as set in PayHOA" + (" (earlier than jason's clock)" if h.due and h.payhoa_due < h.due
                                                              else "")] if h.payhoa_due else []
            out.append("    PayHOA: " + "; ".join(due + list(h.hints)))
        if h.open and rule and rule.first_step:
            out.append(f"    next: {rule.first_step}")
        if sources is not None and str(r["id"]) in sources:
            from jason.tasks.response_sources import source_lines

            out.extend(source_lines(sources[str(r["id"])]))
    return out


# --- Email acknowledgments as Gmail drafts -----------------------------------------------------------------------------

REPLY_DRAFTS = Path("responses") / "gmail-drafts.json"
_REPLY_HEADERS = ("From", "Reply-To", "X-Original-From", "Message-ID", "References", "Subject")


def reply_subject(subject: str) -> str:
    """The thread's subject as a reply: one "Re:", whatever prefixes it carried."""
    bare = re.sub(r"(?i)^(?:\s*(?:re|fwd?|fw)\s*:\s*)+", "", subject or "").strip()
    return f"Re: {bare}" if bare else "Re: your message"


def reply_plan(h: Handled, community: Any) -> dict[str, Any]:
    """The Gmail draft that answers an email request in its thread: the thread, the subject, and the acknowledgment.
    The recipient is read from the thread when the draft is made, unless a person names one; it is never stored."""
    thread = h.request.get("threadId") or ""
    if not thread:
        raise ValueError(f"request {h.request['id']} is not an email request; answer it with jason request-comment")
    return {"requestId": h.request["id"], "threadId": thread, "subject": reply_subject(h.request.get("title") or ""),
            "text": acknowledgment(h, community), "link": h.request.get("link", "")}


def drafted(data_dir: Path) -> dict[str, Any]:
    """The acknowledgment drafts made so far, by request id: the draft's id, its thread, and when."""
    import json

    path = Path(data_dir) / REPLY_DRAFTS
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}


def _address(value: str) -> str:
    from email.utils import getaddresses

    found = [a for _, a in getaddresses([value or ""]) if "@" in a]
    return found[0] if found else ""


def make_reply(plan: dict[str, Any], gmail: Any, drafts: Any, data_dir: Path, *, to: tuple[str, ...] = (),
               messages: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Save the acknowledgment as a Gmail draft in its thread (``drafts``: ``GmailDrafts``, which cannot send). The
    draft answers the thread's last message in: its Message-ID threads the reply, and the writer a Google Group
    rewrote (X-Original-From), else its Reply-To, else its From is the recipient, unless ``to`` names one. The draft's
    id is recorded in ``data/responses/gmail-drafts.json``; the address is not."""
    import json
    from datetime import datetime, timezone

    from jason.google.gmail_drafts import DraftMessage

    items = messages if messages is not None else _messages_by_thread(Path(data_dir)).get(plan["threadId"], [])
    last_in = next((m for m in reversed(items) if m.get("direction") == "in"), None)
    if last_in is None:
        raise ValueError(f"thread {plan['threadId']} has no message in to answer")
    head = gmail.get_metadata(last_in["messageId"], headers=_REPLY_HEADERS)["headers"]
    head = {k.lower(): v for k, v in head.items()}
    recipient = to or tuple(a for a in [_address(head.get("x-original-from", "")) or _address(head.get("reply-to", ""))
                                        or _address(head.get("from", ""))] if a)
    message_id = head.get("message-id", "")
    references = " ".join(x for x in (head.get("references", ""), message_id) if x)
    draft = DraftMessage(to=recipient, subject=plan["subject"], text=plan["text"], thread_id=plan["threadId"],
                         in_reply_to=message_id, references=references)
    created = drafts.create(draft)
    record = drafted(data_dir)
    record[str(plan["requestId"])] = {"draftId": created.get("id", ""), "threadId": plan["threadId"],
                                      "at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    path = Path(data_dir) / REPLY_DRAFTS
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, indent=1), encoding="utf-8")
    return {"draftId": created.get("id", ""), "threadId": plan["threadId"], "to": bool(recipient),
            "threaded": bool(message_id)}


__all__ = ["Handled", "PAYHOA_FIELDS", "REPLY_DRAFTS", "classify_email", "classify_request", "drafted", "due_day",
           "email_requests", "handle", "lines", "make_reply", "owner_threads", "payhoa_fields", "payhoa_hints",
           "reply_plan", "reply_subject", "summary", "thread_kind"]
