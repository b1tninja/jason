"""The notice of a board meeting, rendered for the active profile from one base template.

The base is ``src/jason/templates/notices/board-meeting-notice.md``: Markdown in the dialect of
``jason.google.docs_markdown``, with ``{UPPER_SNAKE}`` tokens jason fills and ``<!-- if FORMAT -->`` ... ``<!-- end -->``
blocks for the meeting's format. ``render`` fills it, and the one Markdown source becomes the email (``email_html``, on
the letterhead's email frame) and, through ``jason letter --markdown``, the Doc on the letterhead and its PDF.

What the notice says comes from records, never from a default:

- **time and place** (CIV 4920(a)) by the meeting's ``MeetingFormat``: in person, the place; hybrid, the physical
  location members may attend, with a director or the board's designee there (4090(b)); held entirely by teleconference,
  the join instructions, the telephone option, the person who can help, the reminder about individual delivery, and
  roll-call votes (4926(a)(1), (3), (4)). A meeting at which ballots are counted and tabulated is never noticed as held
  entirely by teleconference (4926(b)): ``render`` refuses it;
- **the agenda** (4920(d)): the board's items for the meeting, an executive matter only by its 4935 subject
  (``meeting_agenda.executive_lines``), and the open forum's time limit only when the board adopted one
  (``Community.open_forum_limit()``); with none, no line;
- **the notice date** against the notice period and its source (``board_items.notice_period``: the statute's four days,
  or the governing documents' longer period, 4920(b)(3)), as a date line, not a number in prose;
- **the law it mentions**, recited from the statutes on disk (``data/authorities``, ``jason export-authorities``): 4930
  whole, 4045(b), and 4041(a)(1). A section not on disk is a highlighted miss that says so; its words are never
  paraphrased in its place;
- **the signer** and the association's name from ``Community.identity()``.

A value the records do not hold is left highlighted (``==[...]==``) for a person, and listed in ``Notice.review``.
Rendering reads disk only. Nothing is sent and nothing is written to Google from here: the Doc is a person's
``jason letter --markdown ... --yes``, and the email a person's send in PayHOA (``jason broadcast FILE.md --notice``).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Iterable

from jason.community.board_items import PRIORITY_ORDER, BoardItem, ItemStatus, Session, agenda_session
from jason.tasks.agenda_plan import MeetingFormat, meeting_format

TEMPLATE = Path(__file__).resolve().parents[1] / "templates" / "notices" / "board-meeting-notice.md"
REQUIREMENT = "board-meeting"          # the notice catalog's key (jason.community.notice_catalog)
TOKEN = re.compile(r"\{([A-Z][A-Z0-9_]*)\}")

# The statutes the base recites, by the token that carries each: read from data/authorities when the notice is drawn.
RECITALS: dict[str, str] = {
    "RECITE_AGENDA_ONLY": "CIV 4930",
    "RECITE_INDIVIDUAL_DELIVERY": "CIV 4045(b)",
    "RECITE_DELIVERY_METHOD": "CIV 4041(a)(1)",
}

# What a person writes in place of a token the records leave empty; the blank stays highlighted in the draft.
BLANKS: dict[str, str] = {
    "ASSOCIATION_NAME": "the association's name",
    "MEETING_TIME": "the time of the meeting",
    "LOCATION": "the place of the meeting",
    "JOIN_INSTRUCTIONS": "how to join by teleconference: the link and the meeting ID",
    "DIAL_IN": "the telephone number to call, and the meeting ID",
    "TECH_CONTACT": "the name, telephone number, and email of the person who can help",
    "GENERAL_DELIVERY": "where general notices are posted, as the annual policy statement names it (Civil Code "
                        "Sections 4045(a), 5310)",
    "DELIVERY_REQUEST": "the association's address or email for notices",
}

FORMAT_BLOCK = {MeetingFormat.IN_PERSON: "in-person", MeetingFormat.HYBRID: "hybrid",
                MeetingFormat.TELECONFERENCE: "teleconference"}
CODES = {"CIV": "Civil Code", "CORP": "Corporations Code", "CCP": "Code of Civil Procedure", "GOV": "Government Code"}


class NoticeRefused(ValueError):
    """A notice jason will not draw: the reason is the message."""


@dataclass(frozen=True)
class Meeting:
    """The facts of one meeting the notice gives. Empty means the record does not hold it: the notice leaves a blank."""

    day: date
    format: MeetingFormat
    time: str = ""
    location: str = ""
    join: str = ""
    dial_in: str = ""
    tech_contact: str = ""
    ballots_counted: bool = False      # ballots are counted and tabulated at it (CIV 5120): never by teleconference only
    notice_date: date | None = None    # the day a person gives the notice; None: the last day the period allows


@dataclass(frozen=True)
class Recital:
    """A statute's words as the notice recites them, or why they could not be read."""

    token: str
    citation: str                      # "CIV 4045(b)"
    found: bool
    paragraphs: tuple[str, ...] = ()   # the words, paragraph by paragraph; "…" marks words left out
    split: bool = False                # a subdivision jason split from the section
    page: str = ""
    session: str = ""
    digest: str = ""
    reason: str = ""

    @property
    def label(self) -> str:
        return statute_label(self.citation)

    def lines(self) -> list[str]:
        if not self.found:
            return [f"=={self.label}: not on disk ({self.reason}). Its words are not paraphrased here: run jason "
                    "export-authorities, then draw the notice again.=="]
        how = "; the subdivision as jason split it from the section" if self.split else ""
        session = f", {self.session} session" if self.session else ""
        return [*(f"> {p}" for p in self.paragraphs), "",
                f"_({self.label}, from jason's copy of the code{session}{how}; the official code controls.)_"]

    def as_dict(self) -> dict[str, Any]:
        return {"token": self.token, "citation": self.citation, "found": self.found, "split": self.split,
                "page": self.page, "session": self.session, "digest": self.digest, "reason": self.reason}


@dataclass
class Notice:
    """A drawn notice: its Markdown, and what a person checks before it goes out."""

    markdown: str
    meeting: Meeting
    notice_by: date
    period_source: str
    recitals: list[Recital] = field(default_factory=list)
    blanks: list[str] = field(default_factory=list)       # tokens left highlighted for a person
    review: list[str] = field(default_factory=list)

    @property
    def misses(self) -> list[Recital]:
        return [r for r in self.recitals if not r.found]

    @property
    def key(self) -> str:
        """The notice's ledger key (``jason notices KEY``, ``jason broadcast --notice KEY``)."""
        return f"{REQUIREMENT}-{self.meeting.day.isoformat()}"


def statute_label(citation: str) -> str:
    """"CIV 4045(b)" as "Civil Code Section 4045(b)"."""
    code, _, rest = citation.partition(" ")
    return f"{CODES.get(code, code)} Section {rest}" if rest else citation


def _long_date(day: date) -> str:
    return f"{day:%A, %B} {day.day}, {day.year}"


def _clock(start: str) -> str:
    """The plan's "19:00" as "7:00 pm"; any other wording as written."""
    m = re.fullmatch(r"(\d{1,2}):(\d{2})", start.strip())
    if not m:
        return start.strip()
    hour, minute = int(m.group(1)), m.group(2)
    return f"{hour % 12 or 12}:{minute} {'am' if hour < 12 else 'pm'}"


# --- The statutes ----------------------------------------------------------------------------------------------------

# A section as exported opens with jason's history note and the section's own amendment line; neither is its words.
_NOT_WORDS = re.compile(r"^(?:- History:|\d{3,5}(?:\.\d+)?\.\s*\((?:Added|Amended|Enacted|Repealed)\b)", re.I)


def recite(data_dir: Path, citation: str, token: str = "") -> Recital:
    """The words of ``citation`` ("CIV 4930", "CIV 4041(a)(1)") from the statutes on disk, read without fetching.

    A subdivision is recited with the lead-in of each subdivision above it, and "…" where words of the section are left
    out, so the omission changes no meaning. A section not on disk, or a subdivision jason cannot find in its words, is
    a miss with the reason."""
    from jason.community.cite import label_text, paragraphs
    from jason.community.law_text import words_digest
    from jason.tasks.export_authorities import authority_text

    m = re.fullmatch(r"([A-Z]+)\s+(\d+(?:\.\d+)?)((?:\([A-Za-z0-9]+\))*)", citation.strip())
    if not m:
        return Recital(token, citation, False, reason="not a statute citation")
    code, number, labels = m.group(1), m.group(2), re.findall(r"\(([A-Za-z0-9]+)\)", m.group(3))
    got = authority_text(Path(data_dir), f"{code} {number}", fetch=False)
    if not got.get("found"):
        return Recital(token, citation, False, reason=str(got.get("reason") or "not in the exported authorities"))
    text = str(got.get("text") or "")
    base = dict(page=str(got.get("page") or ""), session=str(got.get("session") or ""), digest=words_digest(text))
    words = [p for p in paragraphs(text) if not _NOT_WORDS.match(p)]
    if not labels:
        return Recital(token, citation, True, tuple(words), **base)
    joined = "\n\n".join(words)
    target = paragraphs(label_text(joined, labels))
    if not target:
        return Recital(token, citation, False, reason=f"{code} {number} is on disk; jason could not find "
                       f"{''.join(f'({x})' for x in labels)} in its words", **base)
    picked: list[str] = []
    for k in range(1, len(labels)):           # each subdivision above the one recited: its lead-in
        above = paragraphs(label_text(joined, labels[:k]))
        if above and above[0] not in picked:
            picked.append(above[0])
    picked += [p for p in target if p not in picked]
    out: list[str] = []
    last = -1
    for p in picked:
        at = words.index(p) if p in words else last + 1
        if at > last + 1 and (last >= 0 or any(re.match(r"^\(", w) for w in words[:at])):
            out.append("…")
        out.append(p)
        last = at
    if last < len(words) - 1:
        out.append("…")
    return Recital(token, citation, True, tuple(out), split=True, **base)


# --- The agenda ------------------------------------------------------------------------------------------------------

def choose_items(items: Iterable[BoardItem], plan_items: dict[str, Any] | None = None) -> tuple[list[BoardItem], list[BoardItem]]:
    """The board items on this meeting's agenda, open and executive. The agenda plan's choice governs when it includes
    any item; otherwise the items proposed or on the agenda, less any the plan leaves out. An item is executive when
    its session is (``agenda_session``) or the plan marks it so: either one keeps it off the open agenda."""
    planned = {str(k): v for k, v in (plan_items or {}).items() if isinstance(v, dict)}
    items = list(items)
    if any(v.get("include") is True for v in planned.values()):
        chosen = [i for i in items if planned.get(i.id, {}).get("include") is True]
    else:
        chosen = [i for i in items if i.status in (ItemStatus.PROPOSED, ItemStatus.ON_AGENDA)
                  and planned.get(i.id, {}).get("include") is not False]

    def order(i: BoardItem) -> tuple[Any, ...]:
        place = planned.get(i.id, {}).get("order")
        return (place if isinstance(place, int) else 10 ** 6, PRIORITY_ORDER[i.priority], i.id)

    chosen.sort(key=order)
    executive = [i for i in chosen if agenda_session(i) is Session.EXECUTIVE or planned.get(i.id, {}).get("kind") == "executive"]
    return [i for i in chosen if i not in executive], executive


def agenda_lines(open_items: list[BoardItem], executive_items: list[BoardItem], *, plan_items: dict[str, Any] | None = None,
                 subjects: dict[str, Any] | None = None, forum: Any = None) -> list[str]:
    """The agenda the notice contains (CIV 4920(d)), as a numbered Markdown list. An open item shows its title, its
    kind, the action proposed (the plan's motion, else the item's ask) with its authority, and any notice of its own;
    an executive matter shows only its 4935 subject (``executive_lines``). ``forum`` is the board's adopted
    ``SpeakingLimit``: its line appears only when there is one."""
    from jason.tasks.meeting_agenda import ACTION, executive_lines

    planned = {str(k): v for k, v in (plan_items or {}).items() if isinstance(v, dict)}
    out: list[str] = []
    count = 0

    def item(title: str, notes: Iterable[str] = ()) -> None:
        nonlocal count
        count += 1
        out.append(f"{count}. {title}")
        out.extend(notes)

    item("Call to order")
    item("Approval of the minutes of the last meeting")
    item("Treasurer's report")
    if open_items:
        item("New business")
        for i in open_items:
            plan = planned.get(i.id, {})
            kind = plan.get("kind") if plan.get("kind") in ("consent", "discussion", "action") else (
                "action" if ACTION.search(i.ask) else "report")
            out.append(f"   - **{i.title}** _({kind})_")
            proposed = str(plan.get("motion") or "").strip()
            first_cite = i.authority.split(";")[0].split(",")[0].strip()
            cited = bool(first_cite) and first_cite in (proposed or i.ask)
            out.append(f"      {'Proposed motion: ' + proposed if proposed else i.ask}"
                       + (f" ({i.authority})" if i.authority and not cited else ""))
            if i.special_notice and not re.match(r"none\b", i.special_notice, re.I):
                out.append(f"      Notice: {i.special_notice}")
    limit = []
    if forum is not None and getattr(forum, "minutes", None):
        limit = [f"   Each member may speak for up to {forum.minutes} minutes ({forum.source})."]
    item("Open forum (Civil Code Section 4925(b))", limit)
    item("Time and place of the next meeting")
    if executive_items:
        item("Adjourn to executive session (Civil Code Section 4935)")
        out.extend(f"   - {line}" for line in executive_lines([], executive_items, subjects or {}))
    item("Adjournment")
    return out


# --- The template ----------------------------------------------------------------------------------------------------

_IF = re.compile(r"^<!--\s*if\s+([a-z-]+)\s*-->\s*$")
_END = re.compile(r"^<!--\s*end\s*-->\s*$")


def base_text(template: Path = TEMPLATE) -> str:
    """The base's body: its front matter left off, every format's block kept (what ``jason notice-check`` reads)."""
    text = Path(template).read_text(encoding="utf-8")
    if text.startswith("---\n"):
        end = text.find("\n---\n", 4)
        if end >= 0:
            text = text[end + 5:]
    return text


def select_blocks(text: str, on: set[str]) -> str:
    """The text with each ``<!-- if NAME -->`` block kept when NAME is in ``on`` and dropped otherwise."""
    out: list[str] = []
    keep: list[bool] = []
    for line in text.splitlines():
        m = _IF.match(line)
        if m:
            keep.append(m.group(1) in on)
            continue
        if _END.match(line) and keep:
            keep.pop()
            continue
        if all(keep):
            out.append(line)
    return "\n".join(out)


def fill(text: str, values: dict[str, str]) -> tuple[str, list[str]]:
    """Each token replaced by its value; one with no value is left highlighted for a person (``BLANKS``) and named. A
    line that is only the signer's token, with no signer, is dropped."""
    blanks: list[str] = []
    out: list[str] = []
    for line in text.splitlines():
        if line.strip() == "{SIGNER}" and not values.get("SIGNER"):
            continue

        def one(m: re.Match[str]) -> str:
            name = m.group(1)
            if values.get(name):
                return values[name]
            if name not in blanks:
                blanks.append(name)
            return f"==[{BLANKS.get(name, name.lower().replace('_', ' '))}]=="
        out.append(TOKEN.sub(one, line))
    return re.sub(r"\n{3,}", "\n\n", "\n".join(out)).strip() + "\n", blanks


# --- Drawing the notice ----------------------------------------------------------------------------------------------

def from_plan(day: date, plan: dict[str, Any] | None, schedule: Any = None, *, fmt: MeetingFormat | str | None = None,
              location: str = "", tech_contact: str = "", ballots_counted: bool = False,
              notice_date: date | None = None) -> Meeting:
    """The meeting's facts from a person's flags, else the agenda plan saved for the date (``agenda_plan``), else the
    schedule's time. The format has no default: with none, the notice is refused, since its lines depend on it."""
    plan = plan or {}
    basics, zoom = plan.get("basics") or {}, plan.get("zoom") or {}
    chosen = meeting_format(fmt) if fmt else meeting_format(basics.get("format"))
    if chosen is None:
        raise NoticeRefused("the meeting's format is not set: give --format (in person, hybrid, teleconference) or set it "
                            "in the agenda plan for the date; the notice's lines depend on it (CIV 4090, 4926)")
    time = _clock(str(basics.get("start") or "")) or str(getattr(schedule, "time", "") or "")
    join = str(basics.get("join") or zoom.get("joinUrl") or "")
    return Meeting(day, chosen, time=time, location=location or str(basics.get("location") or ""), join=join,
                   dial_in=str(basics.get("dialIn") or zoom.get("dialIn") or ""),
                   tech_contact=tech_contact or str(basics.get("help") or ""), ballots_counted=ballots_counted,
                   notice_date=notice_date)


def _delivery(identity: Any) -> tuple[str, str]:
    """Where general notices are posted, and where a member writes to ask for individual delivery."""
    posted = getattr(identity, "posting_location", "") or ""
    mail = ", ".join(x for x in (getattr(identity, "designated_recipient", ""), getattr(identity, "official_address", "")) if x)
    email = getattr(identity, "official_email", "") or ""
    request = f"{mail}, or by email to {email}" if mail and email else (mail or email)
    return (f"posted at {posted}" if posted else ""), request


def render(community: Any, meeting: Meeting, items: Iterable[BoardItem], data_dir: Path, *,
           plan_items: dict[str, Any] | None = None, template: Path = TEMPLATE) -> Notice:
    """The notice for ``meeting`` (see the module docstring). Refuses a meeting at which ballots are counted when it is
    held entirely by teleconference (CIV 4926(b)), and a notice date later than the notice period allows."""
    from jason.community.template_values import Layer, citation_values, resolve
    from jason.tasks.board_items import notice_period

    if meeting.format is MeetingFormat.TELECONFERENCE and meeting.ballots_counted:
        raise NoticeRefused("ballots are counted and tabulated at this meeting, so it cannot be held entirely by "
                            "teleconference (CIV 4926(b)); notice it in person or hybrid, with a physical location")
    days, source = notice_period(community=community)
    notice_by = meeting.day - timedelta(days=days)
    if meeting.notice_date is not None and meeting.notice_date > notice_by:
        raise NoticeRefused(f"a notice given {_long_date(meeting.notice_date)} is late: notice of this meeting is due by "
                            f"{_long_date(notice_by)} ({source}); choose a later meeting date")
    identity = community.identity()
    plan_items = plan_items or {}
    subjects = {str(k): v.get("subject") for k, v in plan_items.items() if isinstance(v, dict) and v.get("subject")}
    open_items, executive_items = choose_items(items, plan_items)
    forum = getattr(community, "open_forum_limit", lambda: None)()
    agenda = agenda_lines(open_items, executive_items, plan_items=plan_items, subjects=subjects, forum=forum)
    recitals = [recite(data_dir, citation, token) for token, citation in RECITALS.items()]
    general, request = _delivery(identity)
    given = meeting.notice_date or notice_by
    own = {"MEETING_DATE": _long_date(meeting.day), "MEETING_TIME": meeting.time,
           "NOTICE_DATE": _long_date(given), "NOTICE_PERIOD_SOURCE": source,
           "LOCATION": meeting.location if meeting.format is not MeetingFormat.TELECONFERENCE else "",
           "JOIN_INSTRUCTIONS": meeting.join, "DIAL_IN": meeting.dial_in, "TECH_CONTACT": meeting.tech_contact,
           "AGENDA": "\n".join(agenda), "GENERAL_DELIVERY": general, "DELIVERY_REQUEST": request,
           **{r.token: "\n".join(r.lines()) for r in recitals}}
    values = resolve(Layer("profile", identity.values()), Layer("cite", citation_values(community)),
                     Layer("meeting", own)).values
    text = select_blocks(base_text(template), {FORMAT_BLOCK[meeting.format]})
    markdown, blanks = fill(text, values)
    review: list[str] = []
    if meeting.notice_date is None:
        review.append(f"The date of this notice is the last day the notice period allows ({_long_date(notice_by)}, "
                      f"{source}); give --notice-date for the day it is posted.")
    review += [f"Blank for a person: {BLANKS.get(b, b)} ({b})." for b in blanks]
    review += [f"{r.label} is not on disk ({r.reason}): run jason export-authorities." for r in recitals if not r.found]
    flagged = [x for x in agenda if "==" in x]
    if flagged:
        review.append(f"{len(flagged)} executive-session line(s) for the Secretary: a 4935 subject read from the "
                      "item's words, or none on record. Set the subject in the agenda plan.")
    schedule = getattr(community, "meeting_schedule", lambda: None)()
    annual = (schedule is not None and getattr(schedule, "annual_month", None) == meeting.day.month
              and schedule.day_in(meeting.day.year, meeting.day.month) == meeting.day)
    if annual and meeting.format is MeetingFormat.TELECONFERENCE:
        review.append("This is the annual meeting's date. If ballots are counted and tabulated at it, it cannot be held "
                      "entirely by teleconference (CIV 4926(b)); draw it again with --ballots-counted and another format.")
    return Notice(markdown, meeting, notice_by, source, recitals, blanks, review)


def email_html(markdown: str, letterhead: Any = None) -> str:
    """The email body from the notice's Markdown (``markdown_html``), in the letterhead's email frame when given."""
    from jason.community.markdown_html import message_html

    body = message_html(markdown, ".md")
    if letterhead is None:
        return body
    from jason.community.email_html import with_letterhead

    return with_letterhead(body, letterhead)


def write(data_dir: Path, notice: Notice, letterhead: Any = None) -> dict[str, Path]:
    """``data/board/notices/notice-<date>.md`` (the source), ``.html`` (the email body on the letterhead's frame), and
    ``.refs.json`` (each statute recited: its page, session, and the digest of the words read). A folder of their own:
    ``jason letter --markdown`` keeps its Doc ids in the source's folder (``docs.json``), apart from the agenda's and the
    packet's in ``data/board/docs.json``."""
    folder = Path(data_dir) / "board" / "notices"
    folder.mkdir(parents=True, exist_ok=True)
    stem = f"notice-{notice.meeting.day.isoformat()}"
    paths = {"markdown": folder / f"{stem}.md", "html": folder / f"{stem}.html", "refs": folder / f"{stem}.refs.json"}
    paths["markdown"].write_text(notice.markdown, encoding="utf-8")
    paths["html"].write_text(email_html(notice.markdown, letterhead), encoding="utf-8")
    paths["refs"].write_text(json.dumps({"key": notice.key, "drawn": datetime.now().isoformat(timespec="seconds"),
                                         "recitals": [r.as_dict() for r in notice.recitals]}, indent=1), encoding="utf-8")
    return paths


__all__ = ["BLANKS", "Meeting", "Notice", "NoticeRefused", "RECITALS", "Recital", "TEMPLATE", "agenda_lines",
           "base_text", "choose_items", "email_html", "fill", "from_plan", "recite", "render", "select_blocks",
           "statute_label", "write"]
