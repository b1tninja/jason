"""What needs attention across the governance systems, in one place, most urgent first.

``digest`` reads the stores the governance commands keep and gives each system a section:

- **schedule** (``jason schedule``): occurrences overdue or due soon, by role, and the duties nobody owns;
- **requests** (``jason respond``): members' requests past or near their clocks, a statute's clock first;
- **intake** (``jason intake``): open questions by kind, the likely ones apart, and answers not yet applied;
- **conflicts** (``jason conflicts``): open conflicts by status (with counsel, on the board's register, noted);
- **notices** (``jason notices``): every notice in the delivery ledger with follow-ups owed;
- **living** (``jason living``): living documents with failed rule checks, held sources, or drift, from each one's last
  build (``data/living/<key>/report.json``);
- **duties** (``jason duties --documents``): the documents' timed duties that nothing tracks and no assignment owns.

Each line is an ``Item`` with an ``Urgency`` and the command that gives its detail. A clock the law or the governing
documents set, passed, is ``LEGAL``, and so is a resend the statute requires; then what is overdue against a policy,
then what is due soon, then what waits on a person, then what is noted. Within one urgency a statute's clock comes
before the documents', and the documents' before a proposed policy's. A section is capped (``limit``) and says how many
more there are and where to read them.

A section that cannot be read (a store missing or broken) is reported as unavailable with the reason; the rest of the
digest still stands. It reads disk only, writes nothing, and decides nothing: a clock is computed, a conflict is noted,
a follow-up is a plan for a person to send through the command that guards the send.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, timedelta
from enum import IntEnum
from pathlib import Path
from typing import Any, Callable

LIMIT = 8                                  # items shown per section
PAST_DAYS = 30                             # how far back the schedule looks for what is overdue
STALE_BUILD_DAYS = 30                      # a living document built longer ago than this is flagged
LONG_LATE_DAYS = 90                        # requests past a policy's clock by more than this are summed on one line


class Urgency(IntEnum):
    LEGAL = 0           # a clock the statute or the governing documents set has passed, or the law owes a delivery
    OVERDUE = 1         # past a clock a policy (adopted or proposed) sets
    SOON = 2            # due soon, or a check that failed
    OPEN = 3            # waiting on a person, with no clock
    NOTED = 4           # for the record

    @property
    def label(self) -> str:
        return {Urgency.LEGAL: "LEGAL", Urgency.OVERDUE: "OVERDUE", Urgency.SOON: "due soon", Urgency.OPEN: "open",
                Urgency.NOTED: "noted"}[self]


# The authority behind a clock: a lower rank comes first within one urgency.
STATUTE, DOCUMENTS, POLICY, NONE = 0, 1, 2, 3


@dataclass(frozen=True)
class Item:
    urgency: Urgency
    text: str
    command: str                           # what gives the detail
    rank: int = NONE
    due: date | None = None

    def key(self) -> tuple:
        return (self.urgency, self.rank, self.due or date.max, self.text)

    def as_dict(self) -> dict[str, Any]:
        return {"urgency": self.urgency.label, "text": self.text, "due": self.due.isoformat() if self.due else None,
                "command": self.command}


@dataclass
class Section:
    key: str
    title: str
    command: str                           # the command for the whole system
    tool: str                              # the MCP tool for the whole system
    items: list[Item] = field(default_factory=list)
    summary: str = ""
    counts: dict[str, Any] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)
    error: str = ""                        # why the section could not be read ("" when it was)

    @property
    def available(self) -> bool:
        return not self.error

    @property
    def top(self) -> Urgency | None:
        return min((i.urgency for i in self.items), default=None)

    def ordered(self) -> list[Item]:
        return sorted(self.items, key=Item.key)

    def as_dict(self, limit: int = LIMIT) -> dict[str, Any]:
        shown = self.ordered()[: max(0, limit)]
        return {"key": self.key, "title": self.title, "command": self.command, "tool": self.tool,
                "available": self.available, "error": self.error or None, "summary": self.summary,
                "counts": self.counts, "notes": self.notes, "total": len(self.items),
                "items": [i.as_dict() for i in shown], "more": max(0, len(self.items) - len(shown))}


@dataclass
class Digest:
    on: date
    sections: list[Section]
    limit: int = LIMIT

    def ordered(self) -> list[Section]:
        """The sections with something urgent first; then the quiet ones; then any that could not be read."""
        order = {k: n for n, k in enumerate(SECTIONS)}
        return sorted(self.sections, key=lambda s: (not s.available, s.top if s.top is not None else 9,
                                                    order.get(s.key, 99)))

    def totals(self) -> dict[str, int]:
        found = Counter(i.urgency for s in self.sections for i in s.items)
        return {u.label: found.get(u, 0) for u in Urgency}

    def as_dict(self) -> dict[str, Any]:
        return {"asOf": self.on.isoformat(), "totals": self.totals(),
                "unavailable": [s.key for s in self.sections if not s.available],
                "sections": [s.as_dict(self.limit) for s in self.ordered()],
                "caveat": CAVEAT}

    def lines(self) -> list[str]:
        """The digest as Markdown: a line of totals, then each section with its items, capped."""
        t = self.totals()
        head = (f"As of {self.on.isoformat()}: {t['LEGAL']} on a legal clock or duty, {t['OVERDUE']} overdue, "
                f"{t['due soon']} due soon, {t['open']} waiting on a person, {t['noted']} noted.")
        missing = [s.title for s in self.sections if not s.available]
        out = [head] + ([f"Unavailable: {'; '.join(missing)}."] if missing else []) + [""]
        for s in self.ordered():
            out.append(f"## {s.title} (`{s.command}`; {s.tool})")
            if s.error:
                out += [f"_Unavailable: {s.error}_", ""]
                continue
            if s.summary:
                out.append(s.summary)
            items = s.ordered()
            for i in items[: self.limit]:
                when = f" [{i.due.isoformat()}]" if i.due and i.urgency <= Urgency.SOON else ""
                out.append(f"- **{i.urgency.label}**{when} {i.text} (`{i.command}`)")
            if len(items) > self.limit:
                out.append(f"- ... {len(items) - self.limit} more: `{s.command}`")
            if not items:
                out.append("- Nothing needs attention.")
            out += [f"_{n}_" for n in s.notes]
            out.append("")
        out.append(f"_{CAVEAT}_")
        return out


CAVEAT = ("Read from the stores on disk (sync each system for the latest). jason decides nothing: a clock is computed, "
          "a conflict is noted, a follow-up is a person's send, and an assignment is a proposal until the board adopts it.")


def _days(n: int) -> str:
    return f"{n} day" if n == 1 else f"{n} days"


def _q(text: str) -> str:
    """An argument for a command line: quoted when it has a space."""
    return f'"{text}"' if " " in text else text


# --- The schedule -----------------------------------------------------------------------------------------------------

_STATUTE = re.compile(r"^[A-Z]{2,5} \d")


def cover_rank(covers: tuple[str, ...] | list[str]) -> int:
    """What sets an assignment's duty: a statute (``CIV 5500``, a notice requirement, a recurring deadline), the
    governing documents (``bylaws#9.6``), or nothing it names."""
    if any(c.startswith(("notice:", "obligation:")) or _STATUTE.match(c) for c in covers):
        return STATUTE
    if any(c and ":" not in c for c in covers):
        return DOCUMENTS
    return POLICY


def schedule_section(community: Any, root: Path, on: date, *, past: int = PAST_DAYS) -> Section:
    from jason.community.schedule import Adoption
    from jason.tasks import schedule as task

    s = _new("schedule")
    found = task.agenda(community, root, start=on - timedelta(days=past), end=on + timedelta(days=task.SOON_DAYS),
                        today=on)
    by_role: dict[str, Counter] = {}
    for o in found:
        if o.standing not in ("overdue", "due soon"):
            continue
        a = o.assignment
        rank = cover_rank(a.covers)
        urgency = (Urgency.SOON if o.standing == "due soon"
                   else Urgency.LEGAL if rank <= DOCUMENTS else Urgency.OVERDUE)
        by_role.setdefault(a.role.value, Counter())[o.standing] += 1
        late = f", {_days((on - o.due).days)} late" if o.standing == "overdue" else ""
        proposed = "; proposed, not yet adopted" if a.adoption is Adoption.PROPOSED else ""
        s.items.append(Item(urgency, f"{a.role.value}: {a.title}, due {o.due.isoformat()}{late} [{a.key}{proposed}]",
                            f"jason schedule --role {_q(a.role.value)}", rank, o.due))
    s.counts = {"byRole": {r: dict(c) for r, c in sorted(by_role.items())}}
    overdue = sum(c["overdue"] for c in by_role.values())
    soon = sum(c["due soon"] for c in by_role.values())
    s.summary = (f"{overdue} overdue and {soon} due within {task.SOON_DAYS} days"
                 + (": " + "; ".join(f"{r} {c['overdue']} overdue, {c['due soon']} due soon"
                                     for r, c in sorted(by_role.items())) if by_role else "") + ".")
    if (overdue or soon) and not task.completions(root):
        s.notes.append("No completion is recorded yet, so an occurrence done but not recorded shows as overdue: "
                       "record it with jason schedule --done KEY DUE --by NAME --evidence TEXT.")
    try:
        _, uncovered = task.coverage(community, root)
        loose = task.unscheduled(community, root)
    except Exception as exc:  # the coverage check reads the duties store; the agenda stands without it
        s.notes.append(f"The coverage check could not run: {exc}")
    else:
        s.counts.update(unassigned=len(uncovered), assignedNotScheduled=len(loose))
        if uncovered or loose:
            s.items.append(Item(Urgency.NOTED, f"{len(uncovered)} duties nobody owns; {len(loose)} on a clock that only "
                                               "a standing assignment owns", "jason schedule --coverage"))
    return s


# --- Members' requests ------------------------------------------------------------------------------------------------

def request_rank(rule: Any) -> int:
    from jason.community.responses import ClockSource

    source = getattr(rule, "source", None)
    return {ClockSource.STATUTE: STATUTE, ClockSource.DOCUMENTS: DOCUMENTS, ClockSource.POLICY: POLICY}.get(source, NONE)


def requests_section(community: Any, root: Path, on: date, *, private: bool = False) -> Section:
    from jason.tasks import responses as task

    s = _new("requests")
    found = list(task.handle(community, root, today=on))
    try:
        found += task.email_requests(community, root, today=on)
    except Exception as exc:  # the email stores are optional: the PayHOA requests stand without them
        s.notes.append(f"Requests made by email were not read: {exc}")
    unanswered = [h for h in found if h.answered is None and h.closed is None]
    clocks: Counter = Counter()
    long_late = []
    for h in unanswered:
        rank = request_rank(h.rule)
        overdue, soon = h.standing.startswith("OVERDUE"), h.standing == "due soon"
        ack_late = bool(h.acknowledge_due and h.acknowledge_due < on and h.acknowledged is None)
        if not (overdue or soon or ack_late):
            continue
        clocks[("statute", "documents", "policy", "none")[rank]] += 1
        if rank > DOCUMENTS and h.due and (on - h.due).days > LONG_LATE_DAYS:
            long_late.append(h)                   # a policy's clock long passed: one line, not one each
            continue
        urgency = (Urgency.LEGAL if overdue and rank <= DOCUMENTS else Urgency.OVERDUE if overdue or ack_late
                   else Urgency.SOON)
        rule = h.rule
        authority = getattr(rule, "authority", "") or h.clock
        under = (f" under {authority}" if rank <= DOCUMENTS else " under a proposed policy" if rank == POLICY else "")
        unit = "" if private else f" ({h.request.get('unit') or 'unit ?'})"
        ack = f"; acknowledgment was due {h.acknowledge_due.isoformat()}" if ack_late else ""
        due = f"due {h.due.isoformat()}{under}, {h.standing}" if h.due else h.standing
        s.items.append(Item(urgency, f"#{h.request.get('id')} {h.kind.value}{unit}, received {h.received}: {due}{ack}",
                            f"jason respond --kind {_q(h.kind.value)}", rank, h.due))
    if long_late:
        kinds = Counter(h.kind.value for h in long_late)
        s.items.append(Item(Urgency.OVERDUE, f"{len(long_late)} more past a proposed policy's clock by over "
                                             f"{LONG_LATE_DAYS} days, the oldest received {min((h.received for h in long_late if h.received), default='?')} "
                                             f"({', '.join(f'{n} {k}' for k, n in kinds.most_common())}): likely settled "
                                             "outside the record; answer or close each where it was made",
                            "jason respond", NONE + 1))
    s.counts = {"unanswered": len(unanswered), "pastOrNear": dict(clocks), "longLate": len(long_late),
                "byKind": dict(Counter(h.kind.value for h in unanswered).most_common())}
    s.summary = (f"{len(unanswered)} unanswered; {sum(clocks.values())} past or near a clock"
                 + (" (" + ", ".join(f"{n} on a {k} clock" for k, n in clocks.items()) + ")" if clocks else "") + ".")
    return s


# --- Intake questions -------------------------------------------------------------------------------------------------

# Which open questions to look at first: whether an instrument took effect and what it changed, then the rest.
KIND_ORDER = ("standing", "before differs", "readings differ", "drift", "held source", "classify", "orphaned note",
              "ocr reading")


def intake_section(root: Path) -> Section:
    from jason.community import intake

    s = _new("intake")
    asks = intake.load(root)
    open_ = [a for a in asks if a.status is intake.AskStatus.OPEN]
    by_kind = Counter(a.kind.value for a in open_)
    likely = Counter(a.kind.value for a in open_ if a.likely)
    answered = [a for a in asks if a.status is intake.AskStatus.ANSWERED]
    order = {k: n for n, k in enumerate(KIND_ORDER)}
    for kind, n in by_kind.items():
        unsure = n - likely.get(kind, 0)
        if unsure:
            s.items.append(Item(Urgency.OPEN, f"{kind}: {unsure} open", f"jason intake --kind {_q(kind)}",
                                order.get(kind, len(order))))
    if likely:
        n = sum(likely.values())
        s.items.append(Item(Urgency.OPEN, f"{n} likely ({', '.join(f'{k} {v}' for k, v in likely.items())}): two "
                                          "readers agree; look at them, then accept in a batch "
                                          "(--accept-likely --by NAME)", "jason intake --likely", len(order) + 1))
    if answered:
        s.items.append(Item(Urgency.OPEN, f"{len(answered)} answered and not yet applied", "jason intake --apply",
                            len(order) + 2))
    s.counts = {"open": len(open_), "byKind": dict(by_kind), "likely": dict(likely), "answeredNotApplied": len(answered)}
    s.summary = (f"{len(open_)} open questions ({sum(likely.values())} likely)." if asks
                 else "No questions parked (jason intake --scan finds them).")
    return s


# --- Conflicts --------------------------------------------------------------------------------------------------------

STATUS_ORDER = ("counsel", "board", "noted")
STATUS_WORDS = {"counsel": "with counsel", "board": "on the board's register", "noted": "noted; no one is acting on it"}


def conflicts_section(community: Any) -> Section:
    from jason.community.authority_order import Clarity, conflicts

    s = _new("conflicts")
    found = conflicts(community, open_only=True)
    order = {k: n for n, k in enumerate(STATUS_ORDER)}
    for c in found:
        item = f"; board item {c.board_item}" if c.board_item else ""
        how = {Clarity.PLAIN: "plain: the authority applies now", Clarity.UNCLEAR: "unclear: counsel reads it first",
               Clarity.RENUMBERED: "a renumbered citation"}.get(c.clarity, c.clarity.value)
        who = STATUS_WORDS.get(c.status.value, c.status.value)
        s.items.append(Item(Urgency.OPEN if c.status.value != "noted" else Urgency.NOTED,
                            f"{c.provision} yields to {c.authority} [{who}; {how}{item}]",
                            "jason conflicts --open", order.get(c.status.value, len(order))))
    by_status = Counter(c.status.value for c in found)
    s.counts = {"open": len(found), "byStatus": {k: by_status.get(k, 0) for k in STATUS_ORDER}}
    s.summary = (f"{len(found)} open: " + ", ".join(f"{by_status.get(k, 0)} {k}" for k in STATUS_ORDER) + "."
                 if found else "No open conflicts recorded.")
    return s


# --- Notices ----------------------------------------------------------------------------------------------------------

def notices_section(root: Path) -> Section:
    from jason.community.notice_catalog import for_ledger
    from jason.community.notices import NoticeKind
    from jason.tasks import notice_ledger

    s = _new("notices")
    if not (Path(root) / "notices" / "deliveries.db").is_file():
        s.summary = "No notices in the delivery ledger (jason notices KEY --sync reads one)."
        return s
    rows = notice_ledger.notices(root)
    quiet = 0
    owed: dict[str, dict[str, int]] = {}
    for key, _, synced in rows:
        found = notice_ledger.standing(notice_ledger.load(root, key), general=notice_ledger.is_general(root, key))
        required = [m for m in found if any(f.resend and f.force == "required" for f, _ in m.follow_ups)]
        policy = [m for m in found if m not in required and any(f.resend for f, _ in m.follow_ups)]
        ask = [m for m in found if any(not f.resend and f is not notice_ledger.GENERAL_NOTE
                                         for f, _ in m.follow_ups)]
        if not (required or policy or ask):
            quiet += 1
            continue
        owed[key] = {"members": len(found), "reached": sum(1 for x in found if x.reached), "resendRequired":
                     len(required), "resendPolicy": len(policy), "askAddress": len(ask)}
        laws = sorted({f.authority for x in required for f, _ in x.follow_ups if f.resend and f.force == "required"})
        bits = []
        if required:
            bits.append(f"{len(required)} owed a resend by law ({'; '.join(laws)})")
        if policy:
            bits.append(f"{len(policy)} a resend by policy")
        if ask:
            bits.append(f"{len(ask)} to ask for an address")
        req = for_ledger(key)
        general = ""
        if req is None:
            general = (f"; no requirement in the notice catalog fits this key: if it was a general notice and was "
                       f"posted, see `jason notices {key} --general`")
        elif req.kind is NoticeKind.GENERAL:
            general = f"; a general notice: if it was posted, see `jason notices {key} --general`"
        urgency = Urgency.LEGAL if required else Urgency.SOON if policy else Urgency.OPEN
        s.items.append(Item(urgency, f"{key}: " + ", ".join(bits) + f"; {owed[key]['reached']} of {len(found)} reached"
                            f" (synced {str(synced)[:10]}){general}", f"jason notices {key}",
                            STATUTE if required else POLICY))
    s.counts = {"notices": len(rows), "withFollowUps": len(owed), "nothingOwed": quiet, "owed": owed}
    s.summary = f"{len(rows)} notices in the ledger; {len(owed)} with follow-ups owed, {quiet} with none."
    s.notes.append("Each notice is read as individually delivered; a person sends a follow-up through the command that "
                   "guards the send, and jason sends none.")
    return s


# --- Living documents -------------------------------------------------------------------------------------------------

def living_section(community: Any, root: Path, on: date) -> Section:
    s = _new("living")
    docs = list(getattr(community, "living_documents", lambda: ())())
    findings_total = 0
    for ld in docs:
        path = Path(root) / "living" / ld.key / "report.json"
        if not path.is_file():
            s.items.append(Item(Urgency.OPEN, f"{ld.key}: not built yet", f"jason living {ld.key}"))
            continue
        report = json.loads(path.read_text(encoding="utf-8"))
        built = str(report.get("built") or "")
        for c in report.get("checks") or []:
            if not c.get("found"):
                s.items.append(Item(Urgency.SOON, f"{ld.key}: the rule row {c.get('rule')} reads \"{c.get('expect')}\" "
                                                  f"in {c.get('section')}, and the current text does not: a person "
                                                  "decides which is wrong", f"jason living {ld.key}", DOCUMENTS))
        held = report.get("held") or []
        if held:
            s.items.append(Item(Urgency.OPEN, f"{ld.key}: {len(held)} sources held: {str(held[0])[:140]}",
                                f"jason living {ld.key} --fetch", DOCUMENTS))
        drift = report.get("drift") or []
        if drift:
            mostly = " (many: mostly the base's OCR)" if len(drift) > 40 else ""
            s.items.append(Item(Urgency.OPEN, f"{ld.key}: the working copy differs in {len(drift)} places{mostly}",
                                f"jason living {ld.key} --working", POLICY))
        kinds = Counter(str(f).split(":", 1)[0] for f in report.get("findings") or [])
        findings_total += sum(kinds.values())
        if kinds:
            s.items.append(Item(Urgency.NOTED, f"{ld.key}: findings while applying: "
                                + ", ".join(f"{n} {k}" for k, n in kinds.most_common()), f"jason living {ld.key}"))
        try:
            age = (on - date.fromisoformat(built[:10])).days if built else None
        except ValueError:
            age = None
        if age is not None and age > STALE_BUILD_DAYS:
            s.items.append(Item(Urgency.NOTED, f"{ld.key}: last built {built[:10]}, {age} days ago",
                                f"jason living {ld.key}"))
    s.counts = {"documents": len(docs), "failedChecks": sum(1 for i in s.items if i.urgency is Urgency.SOON),
                "findings": findings_total}
    s.summary = (f"{len(docs)} kept as amended; read from each one's last build." if docs
                 else "No document is kept as amended.")
    return s


# --- The documents' timed duties --------------------------------------------------------------------------------------

def duties_section(community: Any, root: Path) -> Section:
    from jason.community.schedule import assignments, covering
    from jason.tasks import document_duties as dd
    from jason.tasks.schedule import ASSOCIATION_BEARERS

    s = _new("duties")
    folder = Path(root) / "duties"
    keys = sorted(p.stem for p in folder.glob("*.json")) if folder.is_dir() else []
    if not keys:
        s.summary = "No documents read for duties (jason duties --documents all)."
        return s
    trackers = (list(getattr(community, "obligations", lambda: ())()),
                list(getattr(community, "notice_rules", lambda: ())()),
                list(getattr(community, "notice_provisions", lambda: ())()))
    rows = assignments(community)
    loose, owned, others = [], 0, 0
    by_doc: Counter = Counter()
    for key in keys:
        for d, by in dd.untracked(dd.stored(root, key), *trackers):
            if by:
                continue
            if covering(f"{d.source}#{d.section}", rows):
                owned += 1
                continue
            if d.bearer.value not in ASSOCIATION_BEARERS:
                others += 1
                continue
            by_doc[d.source] += 1
            loose.append(d)
    for d in loose:
        timing = "; ".join(x for x in (d.deadline.text if d.deadline is not None else "", d.recurrence or "") if x)
        s.items.append(Item(Urgency.OPEN, f"{d.source}#{d.section} [{d.bearer.value}]: "
                                          f"{' '.join(d.quote.split())[:120]}" + (f" | when: {timing}" if timing else ""),
                            f"jason duties --documents {d.source} --timed --untracked",
                            DOCUMENTS if d.notice else POLICY))
    if others:
        s.items.append(Item(Urgency.NOTED, f"{others} timed duties of owners or others nothing tracks (the association "
                                           "may choose to remind)", s.command))
    s.counts = {"documents": len(keys), "association": len(loose), "others": others, "ownedBySchedule": owned,
                "byDocument": dict(by_doc.most_common())}
    s.summary = (f"{len(loose)} of the association's timed duties have no recurring deadline, calendar event, notice "
                 f"rule, or assignment; {owned} more are owned by an assignment. A reading is a lead to review.")
    return s


# --- The digest -------------------------------------------------------------------------------------------------------

SECTIONS = ("requests", "schedule", "notices", "living", "conflicts", "duties", "intake")
TITLES = {"schedule": ("The schedule: overdue and due soon", "jason schedule", "schedule_agenda"),
          "requests": ("Members' requests and their clocks", "jason respond", "member_requests"),
          "intake": ("Intake questions", "jason intake", "intake_questions"),
          "conflicts": ("Provisions that yield to a higher authority", "jason conflicts", "document_conflicts"),
          "notices": ("Notices with follow-ups owed", "jason notices", "notice_delivery"),
          "living": ("Living documents", "jason living", "living_document"),
          "duties": ("The documents' timed duties nothing tracks", "jason duties --documents all --timed --untracked",
                     "document_duties")}


def _new(key: str) -> Section:
    title, command, tool = TITLES[key]
    return Section(key, title, command, tool)


def _guard(key: str, build: Callable[[], Section]) -> Section:
    """One section, or the section marked unavailable with the reason: a missing store never sinks the digest."""
    try:
        return build()
    except Exception as exc:
        s = _new(key)
        s.error = f"{type(exc).__name__}: {str(exc)[:200]}"
        return s


def digest(community: Any, data_dir: Path, *, on: date | None = None, limit: int = LIMIT, past: int = PAST_DAYS,
           sections: tuple[str, ...] = SECTIONS, private: bool = False) -> Digest:
    """Every section in ``sections`` (all by default), each read on its own. ``private`` leaves out units (for an
    open-session packet)."""
    on = on or date.today()
    root = Path(data_dir)
    builders: dict[str, Callable[[], Section]] = {
        "schedule": lambda: schedule_section(community, root, on, past=past),
        "requests": lambda: requests_section(community, root, on, private=private),
        "intake": lambda: intake_section(root),
        "conflicts": lambda: conflicts_section(community),
        "notices": lambda: notices_section(root),
        "living": lambda: living_section(community, root, on),
        "duties": lambda: duties_section(community, root),
    }
    unknown = [k for k in sections if k not in builders]
    if unknown:
        raise ValueError(f"no section {', '.join(unknown)}: the sections are {', '.join(SECTIONS)}")
    return Digest(on, [_guard(k, builders[k]) for k in sections], limit)


__all__ = ["CAVEAT", "Digest", "Item", "LIMIT", "SECTIONS", "Section", "Urgency", "conflicts_section", "cover_rank",
           "digest", "duties_section", "intake_section", "living_section", "notices_section", "request_rank",
           "requests_section", "schedule_section"]
