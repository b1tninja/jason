"""Every delivery of a notice to each member, what became of it, and the delivery the law asks for next.

A notice is sent in batches (``jason.batches``): emailed copies, Mailroom letters. This ledger keeps each attempt to
reach a member (``data/notices/deliveries.db``), and ``sync`` reads what happened to each one from PayHOA:

- **email**: PayHOA's communications log carries each message's status and its events. SendGrid reports
  delivered, opened, and bounced, with the receiving server's reason. PayHOA reports failed: skipped for no email on
  file, no follow-up event after 24 hours, or its own failure. An emailed copy is found by the reference in its
  subject.
- **letter**: the same log carries each letter (one row per member) with Lob's events, among them a return to sender.
  A letter is found by its Mailroom letter's communication.

Each attempt's outcome is weighed by ``FOLLOW_UPS``, rows that say what the law, or the association's policy, asks for
next:
- An email that bounced was not to a valid address, and the notice is resent by mail (Civil Code 4041(e), 4040(a)(2)).
- A letter that never went into the mail was not delivered.
- A letter that came back was delivered on deposit (4050(b)), but its address is not good, so the member is asked.

A member is reached once any attempt delivered. A follow-up is a plan for a person to send, through the commands
that already guard each send (``owner-info --mail-batch``, ``mailroom --send``); its batch is then read in like the
first. jason never sends one on its own.
"""

from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Iterable


class Delivery(Enum):
    PENDING = "pending"          # handed over, no outcome yet (an email submitted; a letter not yet in the mail)
    MAILED = "mailed"            # a letter in the mail: delivered on deposit (CIV 4050(b))
    DELIVERED = "delivered"      # an email the receiving server accepted (CIV 4050(c): complete on transmission)
    OPENED = "opened"            # an email opened or clicked
    BOUNCED = "bounced"          # an email the receiving server refused: not a valid address (CIV 4041(e))
    UNKNOWN = "unknown"          # no follow-up event after 24 hours: not shown delivered
    SKIPPED = "skipped"          # never sent: no email on file
    FAILED = "failed"            # PayHOA or Lob failed to send it
    RETURNED = "returned"        # a letter returned to sender
    REROUTED = "rerouted"        # a letter forwarded to another address: delivered, but the address on file is old

    @property
    def reached(self) -> bool:
        return self in (Delivery.MAILED, Delivery.DELIVERED, Delivery.OPENED, Delivery.RETURNED, Delivery.REROUTED)


# Lob's events as PayHOA's Mailroom names them (``mail_events``), latest first in meaning: what each says of a letter.
LOB_EVENTS = (
    ("return", Delivery.RETURNED), ("re-routed", Delivery.REROUTED), ("rerouted", Delivery.REROUTED),
    ("failed", Delivery.FAILED), ("issue", Delivery.FAILED),
    ("delivered", Delivery.MAILED), ("processed for delivery", Delivery.MAILED), ("in local area", Delivery.MAILED),
    ("in transit", Delivery.MAILED), ("sent", Delivery.MAILED), ("mailed", Delivery.MAILED),
)


def letter_outcome(events: list[dict[str, Any]]) -> tuple[Delivery, str, str]:
    """A letter's delivery from its Lob events: the most telling event wins (a return over a delivery)."""
    names = [(str(e.get("event") or "").lower(), str(e.get("createdAt") or ""), str(e.get("additional") or ""))
             for e in events]
    for word, delivery in LOB_EVENTS:
        hit = next((n for n in names if word in n[0]), None)
        if hit:
            return delivery, hit[1], hit[2] or hit[0]
    return Delivery.PENDING, names[-1][1] if names else "", ""


@dataclass(frozen=True)
class FollowUp:
    key: str
    when: frozenset[Delivery]
    channel: str                 # the channel of the attempt it follows ("email", "letter")
    action: str
    force: str                   # "required" (the statute) or "policy" (the association's practice)
    authority: str
    resend: bool = True          # the notice is to be delivered again (not only an address to ask for)


FOLLOW_UPS: tuple[FollowUp, ...] = (
    FollowUp("email-bounced", frozenset({Delivery.BOUNCED}), "email",
             "Resend the notice by first-class mail to the address on the books (or another address the member "
             "identified), and ask the member for a working email.", "required", "CIV 4041(e), 4040(a)(2)"),
    FollowUp("email-not-shown-delivered", frozenset({Delivery.UNKNOWN, Delivery.FAILED}), "email",
             "Not shown delivered: resend by first-class mail, as for a bounce.", "policy", "CIV 4041(e), 4040(a)(2)"),
    FollowUp("email-skipped", frozenset({Delivery.SKIPPED}), "email",
             "No email on file: first-class mail is the law's delivery; make sure a letter went.", "required",
             "CIV 4040(a)(2), 4041(c)"),
    FollowUp("letter-failed", frozenset({Delivery.FAILED}), "letter",
             "The letter never went into the mail, so it was not delivered: correct the address and send it again.",
             "required", "CIV 4040(a)(2), 4050(b)"),
    FollowUp("letter-rerouted", frozenset({Delivery.REROUTED}), "letter",
             "Delivered, but forwarded: the address on the books is likely old; ask the member to confirm their "
             "mailing address.", "policy", "CIV 4040(a)(2), 4041(a)", resend=False),
    FollowUp("letter-returned", frozenset({Delivery.RETURNED}), "letter",
             "Delivered on deposit, but the address is not good: send to the member's elected email or secondary "
             "address if there is one, and ask the member for a current mailing address.", "policy",
             "CIV 4050(b), 4041(c)"),
)


@dataclass
class Attempt:
    notice: str
    membership_id: int
    unit_id: int
    unit: str
    channel: str                 # "email" or "letter"
    batch: str                   # the jason batch it went out in
    key: str                     # what identifies it in PayHOA: an email's reference, a letter's communication
    sent_at: str = ""
    status: Delivery = Delivery.PENDING
    status_at: str = ""
    reason: str = ""             # the receiving server's or PayHOA's words


def _db(data_dir: Path) -> sqlite3.Connection:
    path = Path(data_dir) / "notices" / "deliveries.db"
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    con.execute("""create table if not exists attempts (
        notice text, membership_id integer, unit_id integer, unit text, channel text, batch text, key text,
        sent_at text, status text, status_at text, reason text, synced_at text,
        primary key (notice, membership_id, channel, key))""")
    con.execute("""create table if not exists notice_kinds (
        notice text primary key, general integer, posted text, set_by text, set_at text)""")
    return con


def set_general(data_dir: Path, notice: str, general: bool, *, posted: str = "", by: str = "") -> None:
    """Record that ``notice`` is a general notice (CIV 4045) that was posted (``posted``: where and when), so every
    reader of the ledger weighs its failed messages as noted, not as resends the law requires."""
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with _db(data_dir) as con:
        con.execute("insert or replace into notice_kinds values (?,?,?,?,?)", (notice, int(general), posted, by, now))


def is_general(data_dir: Path, notice: str) -> bool:
    """Whether the ledger records ``notice`` as a posted general notice (``set_general``); False when nobody said."""
    path = Path(data_dir) / "notices" / "deliveries.db"
    if not path.is_file():
        return False
    with _db(data_dir) as con:
        row = con.execute("select general from notice_kinds where notice = ?", (notice,)).fetchone()
    return bool(row and row[0])


def save(data_dir: Path, attempts: Iterable[Attempt]) -> int:
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    n = 0
    with _db(data_dir) as con:
        for a in attempts:
            con.execute("insert or replace into attempts values (?,?,?,?,?,?,?,?,?,?,?,?)",
                        (a.notice, a.membership_id, a.unit_id, a.unit, a.channel, a.batch, a.key, a.sent_at,
                         a.status.value, a.status_at, a.reason, now))
            n += 1
    return n


def load(data_dir: Path, notice: str) -> list[Attempt]:
    with _db(data_dir) as con:
        rows = con.execute("select * from attempts where notice = ? order by unit, membership_id, sent_at",
                           (notice,)).fetchall()
    return [Attempt(r["notice"], r["membership_id"], r["unit_id"], r["unit"], r["channel"], r["batch"], r["key"],
                    r["sent_at"], Delivery(r["status"]), r["status_at"], r["reason"]) for r in rows]


def notices(data_dir: Path) -> list[tuple[str, int, str]]:
    with _db(data_dir) as con:
        return [(r[0], r[1], r[2]) for r in con.execute(
            "select notice, count(*), max(synced_at) from attempts group by notice order by notice").fetchall()]


def outcome(row: dict[str, Any]) -> tuple[Delivery, str, str]:
    """A communications-log row's delivery, when it happened, and the reason given."""
    events = (row.get("statusData") or {}).get("events") or []
    last = events[-1] if events else {}
    details = last.get("details") or {}
    reason = str(details.get("reason") or details.get("response") or "")
    when = str(last.get("occurredAt") or row.get("updatedAt") or "")
    status = str(row.get("status") or "")
    if row.get("type") == "letter":
        kinds = " ".join(str(e.get("type") or "") + " " + str((e.get("details") or {}).get("event") or "")
                         for e in events).lower()
        if "return" in kinds:
            return Delivery.RETURNED, when, reason
        if status == "failed":
            return Delivery.FAILED, when, reason
        if status in ("delivered", "mailed", "in_transit") or any(w in kinds for w in ("mailed", "in_transit",
                                                                                         "in transit", "delivered")):
            return Delivery.MAILED, when, reason
        return Delivery.PENDING, when, reason
    if status in ("opened", "clicked"):
        return Delivery.OPENED, when, reason
    if status == "delivered":
        return Delivery.DELIVERED, when, reason
    if status == "bounced":
        return Delivery.BOUNCED, when, reason
    if status == "failed":
        if last.get("source") == "email-skip" and "no email" in reason.lower():
            return Delivery.SKIPPED, when, reason
        if "no follow-up" in reason.lower():
            return Delivery.UNKNOWN, when, reason
        return Delivery.FAILED, when, reason or str(last.get("source") or "")
    return Delivery.PENDING, when, reason


def subject_of(row: dict[str, Any]) -> str:
    """A log row's subject: an email's own, or the subject its first event recorded."""
    events = (row.get("statusData") or {}).get("events") or []
    return str(row.get("subject") or (events[0].get("details") or {}).get("subject") if events else row.get("subject") or "")


def _members(row: dict[str, Any]) -> list[int]:
    return [int(m["id"]) for m in row.get("recipientMemberships") or [] if m.get("id") is not None]


def sync(client: Any, org_id: int, data_dir: Path, notice: str, batch_ids: Iterable[str], *,
         since: str = "", subject: str = "") -> dict[str, int]:
    """Read every attempt of ``notice`` from its batches, and its outcome from PayHOA's communications log (and the
    Mailroom's letter list), into the ledger. ``subject`` also takes every email in the log whose subject contains it:
    a notice sent from PayHOA's own screens (a meeting notice, a broadcast), with no jason batch. Read-only in
    PayHOA."""
    from jason import batches

    email_refs: dict[str, tuple[int, int, str]] = {}      # reference -> (membership, unit, batch)
    mail_batches: dict[int, str] = {}                     # Mailroom batch -> jason batch
    for bid in batch_ids:
        for item in batches.items(Path(data_dir), bid):
            if item.status is not batches.ItemStatus.SENT:
                continue
            if item.result.get("reference"):
                email_refs[str(item.result["reference"])] = (int(item.payload["membershipId"]),
                                                             int(item.payload["unitId"]), bid)
            for mb in item.result.get("mailBatches") or []:
                mail_batches[int(mb)] = bid
    letter_comm: dict[int, str] = {}                      # communication -> jason batch
    if mail_batches:
        wanted = {int(l["id"]): mail_batches[mb] for mb in mail_batches for l in client.mail_batch(org_id, mb)}
        for l in client.mail_letters(org_id, "pdf"):
            if int(l.get("id") or 0) in wanted and l.get("commActivityId"):
                letter_comm[int(l["commActivityId"])] = wanted[int(l["id"])]
    found: list[Attempt] = []
    floor = since or "0000"
    for row in client.iter_communications(org_id):
        created = str(row.get("createdAt") or "")
        if created and created < floor:
            break
        title = str(row.get("subject") or "")
        ref = next((r for r in email_refs if r in title), None) if row.get("type") == "email" else None
        comm = int(row.get("activityId") or 0)
        if ref is not None:
            member, unit_id, bid = email_refs[ref]
            key, channel = ref, "email"
        elif row.get("type") == "letter" and comm in letter_comm:
            bid, channel, key = letter_comm[comm], "letter", str(comm)
            unit_id = 0
            members = _members(row)
            member = members[0] if members else 0
        elif subject and row.get("type") in ("email", "letter", "paper") and subject.lower() in subject_of(row).lower():
            bid, channel, key = "payhoa", "letter" if row.get("type") != "email" else "email", str(comm)
            unit_id = 0
            members = _members(row)
            member = members[0] if members else 0
        else:
            continue
        status, when, reason = outcome(row)
        if channel == "letter" and status is Delivery.PENDING:
            # the log's summary lags Lob's own tracking: read the letter's events
            status, when, reason = letter_outcome(client.mail_events(org_id, comm)) if comm else (status, when, reason)
        found.append(Attempt(notice, member, unit_id, str(row.get("recipientUnitTitle") or ""), channel, bid, key,
                             created, status, when, reason))
    save(data_dir, found)
    counts: dict[str, int] = {}
    for a in found:
        counts[f"{a.channel} {a.status.value}"] = counts.get(f"{a.channel} {a.status.value}", 0) + 1
    return counts


@dataclass
class Standing:
    membership_id: int
    unit: str
    attempts: list[Attempt]
    follow_ups: list[tuple[FollowUp, Attempt]]

    @property
    def reached(self) -> bool:
        return any(a.status.reached for a in self.attempts)


GENERAL_NOTE = FollowUp(
    "general-notice", frozenset(), "",
    "Delivered by its posting where the annual policy statement designates (or another 4045(a) method); this message "
    "failing is noted, and owed again only if the member asked for individual delivery.", "policy", "CIV 4045(a), (b)",
    resend=False)

ASK_EMAIL = FollowUp(
    "ask-email", frozenset({Delivery.BOUNCED}), "email",
    "The email bounced, so the address is not valid; the notice reached the member another way (or by its posting): "
    "ask the member for a working email.", "policy", "CIV 4041(e)", resend=False)

ASK_ADDRESS = FollowUp(
    "ask-address", frozenset({Delivery.RETURNED}), "letter",
    "The letter came back; the notice reached the member another way: ask the member for a current mailing address.",
    "policy", "CIV 4041(a), (c)", resend=False)

# What a follow-up becomes once another delivery (or a general notice's posting) has reached the member.
ONCE_REACHED = {"email-bounced": ASK_EMAIL, "letter-returned": ASK_ADDRESS, "letter-rerouted": None}

# Attempts that got the notice to the member: a returned letter was delivered on deposit (4050(b)) but did not.
ARRIVED = frozenset({Delivery.MAILED, Delivery.DELIVERED, Delivery.OPENED, Delivery.REROUTED})


def temporary(a: Attempt) -> bool:
    """A bounce the receiving server called temporary (an SMTP 4xx: a full mailbox). Still a bounce under 4041(e),
    which counts any "bounce or other error notification indicating failure of the message"; the address may work
    again."""
    return a.status is Delivery.BOUNCED and bool(re.match(r"\s*4\d\d\b", a.reason))


def standing(attempts: list[Attempt], *, general: bool = False,
             individual: set[int] | frozenset[int] = frozenset()) -> list[Standing]:
    """Each member's attempts and the follow-ups still owed, each once. A member another attempt has reached owes no
    resend; an email that bounced or a letter that came back still asks for the member's address, and a forwarded
    letter asks the member to confirm it.

    ``general``: a general notice (CIV 4045) also posted where the annual policy statement designates, so the posting
    is its delivery. A resend is owed only to a member in ``individual`` (who asked for general notices by individual
    delivery, 4045(b)); for the rest a failure is noted, and a bounce still asks for a working email. A general notice
    that was not posted was delivered by these messages (4045(a)(1)): leave ``general`` off."""
    by_member: dict[int, list[Attempt]] = {}
    for a in attempts:
        by_member.setdefault(a.membership_id, []).append(a)
    out = []
    for member, mine in by_member.items():
        posted = general and member not in individual
        arrived = any(a.status in ARRIVED for a in mine)
        owed: list[tuple[FollowUp, Attempt]] = []
        seen: set[str] = set()
        for a in mine:
            for f in FOLLOW_UPS:
                if a.channel != f.channel or a.status not in f.when:
                    continue
                if arrived or posted:
                    if f.key in ONCE_REACHED:
                        f = ONCE_REACHED[f.key] or f
                    elif posted:
                        f = GENERAL_NOTE
                    else:
                        continue                     # another delivery reached the member: no resend
                if f.key not in seen:
                    seen.add(f.key)
                    owed.append((f, a))
        out.append(Standing(member, next((a.unit for a in mine if a.unit), ""), mine, owed))
    return sorted(out, key=lambda s: (not s.follow_ups, s.unit))


def lines(found: list[Standing]) -> list[str]:
    total = len(found)
    reached = sum(1 for s in found if s.reached)
    resend = [s for s in found if any(f.resend for f, _ in s.follow_ups)]
    ask = [s for s in found if any(not f.resend and f is not GENERAL_NOTE for f, _ in s.follow_ups)]
    noted = [s for s in found if any(f is GENERAL_NOTE for f, _ in s.follow_ups)]
    out = [f"{total} members; {reached} reached; {len(resend)} owed a resend; {len(ask)} to ask for an address"
           + (f"; {len(noted)} not reached by this message, noted" if noted else "") + "."]
    if noted:
        out.append(f"General notice: {GENERAL_NOTE.action} [{GENERAL_NOTE.authority}]")
    for s in found:
        for f, a in s.follow_ups:
            action = "noted (general notice)" if f is GENERAL_NOTE else f"{f.action} [{f.force}; {f.authority}]"
            out.append(f"- {s.unit or 'unit ?'} (member {s.membership_id}): {a.channel} {a.status.value}"
                       + (" temporary" if temporary(a) else "")
                       + (f" ({a.reason[:120]})" if a.reason else "") + f" -> {action}")
    units = sorted({s.unit for s in resend if s.unit})
    if units:
        out += ["", "To send the follow-ups (a person's step; each is its own confirmed send):",
                "  a notice jason batched:  jason owner-info --mail-batch --only \"UNIT\" --resend --yes --confirmed-by NAME",
                "  any other letter:        jason mailroom --pdf LETTER.pdf --units \"UNIT\" --send --yes",
                "  units: " + "; ".join(units)]
    return out


def as_json(found: list[Standing]) -> str:
    return json.dumps([{"membershipId": s.membership_id, "unit": s.unit, "reached": s.reached,
                        "attempts": [{"channel": a.channel, "status": a.status.value, "reason": a.reason,
                                      "batch": a.batch, "at": a.status_at} for a in s.attempts],
                        "followUps": [{"key": f.key, "action": f.action, "force": f.force, "authority": f.authority}
                                      for f, _ in s.follow_ups]} for s in found], indent=1)


__all__ = ["Attempt", "Delivery", "FOLLOW_UPS", "FollowUp", "ASK_ADDRESS", "ASK_EMAIL", "GENERAL_NOTE", "temporary", "Standing", "as_json", "lines", "load", "notices",
           "letter_outcome", "outcome", "save", "standing", "sync"]
