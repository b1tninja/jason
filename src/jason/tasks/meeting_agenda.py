"""Draft the next board meeting's agenda from the last one, the way the secretary does, with what the law asks added.

The board's agendas are Google Docs ("My Drive/Meetings/<year>/Agenda for M/D/YY"): a header table with the meeting's date
and Zoom details, numbered headings for the standing items and the month's business, the open forum, the next meeting,
the executive session, and the decorum rules. The secretary copies last month's and updates it. ``read_doc`` reads such
a Doc (read-only, smart chips included: linked files, dates, people) into an ``AgendaDoc``; ``draft`` makes the next
meeting's agenda from it as Markdown:

- the date is the schedule's next meeting (``Community.meeting_schedule()``), with the notice deadline (four days
  before, or the governing documents' longer period; CIV 4920) and the note that an item not on the agenda cannot be
  acted on (4930);
- the header follows the meeting's format (``MeetingFormat``: the agenda plan's for the date, or a person's flag). A
  meeting held entirely by teleconference carries what 4926(a) asks of its notice: technical instructions, the
  telephone and email of a person who can help before and during the meeting, the reminder that a member may request
  individual delivery of meeting notices with 4045(b) and 4041(a)(1) recited from disk by the board meeting notice's
  helpers (``individual_delivery_lines``; a statute not on disk is a visible miss), and that every vote of the
  directors is by roll call (4926(a)(1), (3)). A hybrid
  meeting's names the physical location, with a director or the board's designee there (4090(b)); an in-person
  meeting's names its place. With no format given, the draft assumes the first and says so;
- the standing items carry forward; the business items carry forward marked "carried over" for the board to keep or drop;
- the board's action items proposed for this meeting (``data/board/items.json``) join the business, labeled action or
  report, with their authority and any notice of their own; the litigation and collections items go to executive session;
- a report of the last executive session is added (4935(e)); the annual meeting at which ballots are counted cannot be
  held entirely by teleconference (4926(b)), and a teleconference draft for the annual meeting says so.

``minutes_template`` drafts the minutes' frame: attendance and quorum (the provision ``BoardRule.quorum_source`` cites),
each motion with mover, second, and the vote by director (a roll call for a meeting held entirely by teleconference),
the executive session's general note, and the next steps. Drafts only; the board sets the agenda and approves the
minutes.

``agenda_items`` names an executive-session matter on the open agenda only by its 4935 subject in the statute's words
(``executive_lines``), never by an item's title or a last agenda's heading.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from jason.community.board_items import PRIORITY_ORDER, BoardItem, ItemStatus, Session, agenda_session
from jason.tasks.agenda_plan import MeetingFormat
from jason.tasks.agenda_plan import meeting_format as to_format

STANDING = re.compile(r"call to order|approval of minutes|treasurer|open forum|time and place|adjourn|architectural review|"
                      r"maintenance|election|decorum", re.I)
EXECUTIVE_HEADING = re.compile(r"executive session", re.I)


@dataclass
class AgendaHeading:
    title: str
    level: int                       # 4 for an item, 5 for a sub-item (the Docs' heading styles)
    notes: list[str] = field(default_factory=list)


@dataclass
class AgendaDoc:
    title: str = ""
    header: str = ""                 # the header table's text: date chip, Zoom, phone, meeting id
    links: list[str] = field(default_factory=list)      # the header table's links (the Zoom join link)
    headings: list[AgendaHeading] = field(default_factory=list)
    closing: list[str] = field(default_factory=list)   # the decorum rules and other trailing text


def _chip(run: dict[str, Any]) -> str:
    if "textRun" in run:
        return run["textRun"].get("content", "")
    if "richLink" in run:
        return f"[{run['richLink'].get('richLinkProperties', {}).get('title', 'file')}]"
    if "person" in run:
        props = run["person"].get("personProperties", {})
        return props.get("name") or props.get("email", "")
    if "dateElement" in run:
        props = run["dateElement"].get("dateElementProperties", {})
        return props.get("displayText") or props.get("timestamp", "")
    return ""


def _links(table: dict[str, Any]) -> list[str]:
    urls = []
    for row in table.get("tableRows", []):
        for cell in row.get("tableCells", []):
            for e in cell.get("content", []):
                for run in (e.get("paragraph") or {}).get("elements", []):
                    url = (run.get("textRun", {}).get("textStyle", {}).get("link") or {}).get("url")                         or run.get("richLink", {}).get("richLinkProperties", {}).get("uri")
                    if url:
                        urls.append(url)
    return urls


def _text(paragraph: dict[str, Any]) -> str:
    return "".join(_chip(run) for run in paragraph.get("elements", [])).strip()


def parse_doc(doc: dict[str, Any]) -> AgendaDoc:
    """An agenda Doc (the Docs API's document, tabs included) as its header, headings, and closing text."""
    body = (doc.get("tabs") or [{}])[0].get("documentTab", {}).get("body") or doc.get("body", {})
    out = AgendaDoc(title=doc.get("title", ""))
    in_closing = False
    for block in body.get("content", []):
        if "table" in block and not out.header:
            cells = [_text(e["paragraph"]) for row in block["table"].get("tableRows", []) for cell in row.get("tableCells", [])
                     for e in cell.get("content", []) if "paragraph" in e]
            out.header = " ".join(c for c in cells if c)
            out.links = list(dict.fromkeys(_links(block["table"])))
            continue
        paragraph = block.get("paragraph")
        if not paragraph:
            continue
        text = _text(paragraph)
        if not text:
            continue
        style = paragraph.get("paragraphStyle", {}).get("namedStyleType", "")
        if style.startswith("HEADING_1"):
            break                       # a minutes Doc: the Zoom recap starts here
        if re.match(r"decorum rules", text, re.I):
            in_closing = True
        if in_closing:
            out.closing.append(text)
        elif style in ("HEADING_4", "HEADING_5") and paragraph.get("bullet"):
            out.headings.append(AgendaHeading(text, int(style[-1])))
        elif out.headings:
            out.headings[-1].notes.append(text)
    return out


def read_doc(docs: Any, document_id: str) -> AgendaDoc:
    """Read an agenda Google Doc (read-only)."""
    return parse_doc(docs.get(document_id))


def _meeting_line(header: str, meeting: date, schedule: Any, fmt: MeetingFormat = MeetingFormat.TELECONFERENCE,
                  location: str = "") -> str:
    # "To be held on: Sep 15, 2026 7:00 PM PDT via Zoom (669) ..." keeps "via Zoom (669) ..." for the new date.
    zoom = re.sub(r"^To be held on:?.*?(?=\bvia\b)", "", header).strip()
    when = f"{meeting:%A, %B} {meeting.day}, {meeting.year} at {getattr(schedule, 'time', '7:00 pm')}"
    if fmt is MeetingFormat.IN_PERSON:
        return f"To be held on {when} at {location or '[the place of the meeting]'}"
    if fmt is MeetingFormat.HYBRID:
        return f"To be held on {when} at {location or '[the physical location]'}, and {zoom or 'by teleconference'}"
    return f"To be held on {when}, {zoom or 'on Zoom'}"


# How each format reads in the draft's note on it, with the provision that defines it.
FORMAT_LABEL = {MeetingFormat.TELECONFERENCE: "held entirely by teleconference, with no physical location (CIV 4926(a))",
                MeetingFormat.HYBRID: "hybrid, a teleconference with a physical location members may attend (CIV 4090(b))",
                MeetingFormat.IN_PERSON: "in person (CIV 4090(a))"}


def individual_delivery_lines(data_dir: Path | None, request: str = "") -> list[str]:
    """4926(a)(1)(C)'s reminder that a member may request individual delivery, with how: 4045(b) and 4041(a)(1) recited
    from the statutes on disk by the board meeting notice's own helpers (``meeting_notice.delivery_recitals``,
    ``delivery_lines``), then where to write. A statute not on disk is a highlighted miss, never a paraphrase."""
    from jason.tasks.meeting_notice import delivery_lines, delivery_recitals

    return ["A member may request individual delivery of meeting notices (CIV 4926(a)(1)(C)).", "",
            *delivery_lines(delivery_recitals(data_dir), request)]


def format_lines(fmt: MeetingFormat, *, tech_contact: str = "", location: str = "", data_dir: Path | None = None,
                 delivery_request: str = "") -> list[str]:
    """What the notice says about taking part, by the meeting's format. 4926's lines (technical instructions, a person
    who can help, the individual-delivery reminder, roll-call votes) are for a meeting held entirely by teleconference
    only (4926(a)); a hybrid meeting's notice names a physical location with a director or the board's designee there
    (4090(b)); an in-person meeting's names its place (4920(a)). The individual-delivery reminder recites the statutes
    from ``data_dir`` (``individual_delivery_lines``); ``delivery_request`` is where a member writes."""
    if fmt is MeetingFormat.IN_PERSON:
        return [f"Members may attend the meeting at {location or '[the place of the meeting]'} (CIV 4920(a), 4925(a))."]
    if fmt is MeetingFormat.HYBRID:
        return [f"Members may attend in person at {location or '[the physical location]'}, where at least one director or a "
                "person the board designates is present (CIV 4090(b)).",
                "Members may also join by teleconference from the link, or by telephone at the number above with the meeting ID."]
    return ["To participate: join the Zoom meeting from the link, or by telephone at the number above with the meeting ID. "
            f"Technical help before and during the meeting: {tech_contact or '[name, telephone, and email of the person who can help]'} "
            "(CIV 4926(a)(1)(A), (B)).", "",
            *individual_delivery_lines(data_dir, delivery_request), "",
            "Every vote of the directors at this meeting is taken by roll call (CIV 4926(a)(3))."]


ACTION = re.compile(r"\b(adopt|decide|direct|authorize|approve|fill|correct|refer)\b", re.I)

# An executive session is noticed by the general nature of its business (CIV 4935(a)-(d), (e)): the open agenda names a
# matter only by its subject in the statute's words (``EXECUTIVE_GENERAL_TERMS``), never by an item's title or ask, or a
# last agenda's heading, which can name the member, the party, or the matter. Those stay in the directors' packet.
CONFIRM = "==confirm: the 4935 subject was read from the wording, not recorded=="
UNKNOWN_SUBJECT = "==___ (an executive-session matter; its 4935 subject is not on record)=="


def executive_lines(carried: list[str], items: list[BoardItem], subjects: dict[str, Any]) -> list[str]:
    """The executive session's lines on the open agenda, in general words only. Each item's subject is the agenda plan's
    (``subjects`` by item id, an ``ExecutiveSubject``); with none, jason's reading of the item's words
    (``classify_executive``, which matches words and can misread a name), flagged for the Secretary to confirm; with
    neither, a blank. A heading carried from the last agenda is read the same way and its words are never copied."""
    from jason.community.models.meetings import classify_executive, executive_general_note, executive_subject

    recorded: list[Any] = []
    read: list[Any] = []
    blanks = 0
    for i in items:
        subject = executive_subject(subjects.get(i.id))
        if subject is not None:
            recorded.append(subject)
            continue
        guess = classify_executive(f"{i.title} {i.ask}")
        if guess is None:
            blanks += 1
        else:
            read.append(guess)
    for title in carried:
        guess = classify_executive(title)
        if guess is None:
            blanks += 1
        else:
            read.append(guess)
    read = [s for s in dict.fromkeys(read) if s not in recorded]
    out = [executive_general_note(recorded)] if recorded else []
    if read:
        out.append(f"{executive_general_note(read)} {CONFIRM}")
    out += [UNKNOWN_SUBJECT] * blanks
    return out


def _kind(title: str) -> str:
    if re.search(r"approval|appointment|proposal|adopt", title, re.I):
        return "action"
    if re.search(r"treasurer|report|review", title, re.I):
        return "report"
    return ""


def agenda_items(previous: AgendaDoc, items: list[BoardItem], meeting: date, schedule: Any, *, include_open: bool = False,
                 previous_meeting: date | None = None, subjects: dict[str, Any] | None = None) -> list[str]:
    """The agenda's business as Markdown, for the agenda Doc's ``{AGENDA_ITEMS}`` and the draft file: the last agenda's
    standing items carried forward, what it carried over flagged for the board to keep or drop, the board's action items
    as New Business (each with the action proposed and any notice the law requires; the background is in the packet),
    the executive session by the general nature of its business only (``executive_lines``; ``subjects`` is the agenda
    plan's 4935 subject by board item id), and the decorum rules."""
    wanted = {ItemStatus.PROPOSED, ItemStatus.ON_AGENDA} | ({ItemStatus.OPEN} if include_open else set())
    chosen = sorted((i for i in items if i.status in wanted), key=lambda i: (PRIORITY_ORDER[i.priority], i.id))
    open_items = [i for i in chosen if agenda_session(i) is Session.OPEN]
    executive_items = [i for i in chosen if agenda_session(i) is Session.EXECUTIVE]
    out: list[str] = []
    n = 0

    def item(title: str, kind: str = "", notes: list[str] = (), flag: str = "") -> None:
        nonlocal n
        n += 1
        # The label and flag sit inside the bold: Docs sets a list number in the style the whole line shares.
        out.append(f"{n}. **{title}" + (f" _({kind})_" if kind else "") + (f" =={flag}==" if flag else "") + "**")
        out.extend(f"   {note}" for note in notes)

    headings = previous.headings
    executive_at = next((k for k, h in enumerate(headings) if EXECUTIVE_HEADING.search(h.title)), len(headings))
    before, after = headings[:executive_at], headings[executive_at:]
    carried = False
    for h in before:
        if re.search(r"time and place", h.title, re.I):
            break
        if re.search(r"open forum", h.title, re.I):
            if open_items:
                item("New Business")
                for i in open_items:
                    kind = "action" if ACTION.search(i.ask) else "report"
                    out.append(f"   - **{i.title} _({kind})_**")
                    # The authority, unless the ask already cites it; a notice line only when the item needs one.
                    first_cite = i.authority.split(";")[0].split(",")[0].strip()
                    cited = bool(first_cite) and first_cite in i.ask
                    out.append(f"      {i.ask}" + (f" ({i.authority})" if i.authority and not cited else ""))
                    if i.special_notice and not re.match(r"none\b", i.special_notice, re.I):
                        out.append(f"      Notice: {i.special_notice}")
            item("Report of the last executive session", "report", ["A general note of the matters discussed (Civil Code Section 4935(e))."])
        if h.level == 5:
            out.append(f"   - {h.title}" + ("" if STANDING.search(h.title) or not carried else " ==keep or drop=="))
            continue
        notes = [nt for nt in h.notes if not re.match(r"^\[.*\]$", nt)][:1]
        if re.search(r"approval of minutes", h.title, re.I) and previous_meeting:
            notes = [f"See: ==[Minutes of {previous_meeting.month}/{previous_meeting.day}/{previous_meeting.year % 100:02d}]=="]
        elif re.search(r"treasurer", h.title, re.I):
            month = meeting.month - 1 or 12
            notes = [f"See: ==[Treasurer's Report - {meeting.year if meeting.month > 1 else meeting.year - 1}-{month:02d}_Redacted.pdf]=="]
        carried = not STANDING.search(h.title)
        item(h.title, _kind(h.title), notes, "carried over: keep or drop" if carried else "")
    nxt = schedule.next_meeting(meeting, monthly=True) if schedule else meeting
    item("Time and place of next meeting", "", [f"{nxt:%A, %B} {nxt.day}, {nxt.year} at {getattr(schedule, 'time', '7:00 pm')} "
                                                 f"on {getattr(schedule, 'place', 'Zoom')}"])
    item("Adjourn to Executive Session")
    out.extend(f"   - {e}" for e in executive_lines([h.title for h in after[1:]], executive_items, subjects or {}))
    item("Adjournment")
    if previous.closing:
        out.append("")
        out.append("### " + previous.closing[0])
        out.extend(previous.closing[1:])
    return out


def draft(previous: AgendaDoc, items: list[BoardItem], meeting: date, schedule: Any, *, tech_contact: str = "",
          include_open: bool = False, previous_meeting: date | None = None, meeting_format: MeetingFormat | str | None = None,
          format_source: str = "", location: str = "", subjects: dict[str, Any] | None = None,
          data_dir: Path | None = None, delivery_request: str = "") -> list[str]:
    """The next meeting's draft agenda (Markdown): the header the notice needs for the meeting's format, the
    secretary's notes on the notice, and ``agenda_items``.

    ``meeting_format`` is the meeting's ``MeetingFormat`` (from the agenda plan for the date or a person's flag;
    ``format_source`` says which). With none, the draft assumes a meeting held entirely by teleconference, as it always
    drafted, and says it assumed so. ``subjects`` is the agenda plan's 4935 subject by item id (``executive_lines``).
    ``data_dir`` holds the statutes the individual-delivery reminder recites, and ``delivery_request`` is where a member
    writes (``format_lines``)."""
    annual = schedule is not None and schedule.annual_month == meeting.month and schedule.day_in(meeting.year, meeting.month) == meeting
    from jason.tasks.board_items import notice_period

    fmt = to_format(meeting_format)
    assumed = fmt is None
    fmt = fmt or MeetingFormat.TELECONFERENCE
    days, basis = notice_period()      # the statute's four days, or the governing documents' longer period (4920(b)(3))
    notice_by = meeting - timedelta(days=days)
    out = [f"# DRAFT Agenda for {meeting.month}/{meeting.day}/{meeting.year % 100:02d}", ""]
    out.append(_meeting_line(previous.header, meeting, schedule, fmt, location))
    out.append("")
    out += format_lines(fmt, tech_contact=tech_contact, location=location, data_dir=data_dir,
                        delivery_request=delivery_request)
    out.append("")
    out.append(f"_Notice with this agenda must go out by {notice_by:%A, %B} {notice_by.day} ({basis}); the board may act only on "
               "items on this agenda (CIV 4930)._")
    out.append("")
    if assumed:
        out.append(f"_Format assumed: {FORMAT_LABEL[fmt]}; no format is in the agenda plan for this date or given with --format. "
                   "4926's lines above are for that format only; for a hybrid or in-person meeting, set the format and draft again._")
    else:
        out.append(f"_Format: {FORMAT_LABEL[fmt]}" + (f", from {format_source}" if format_source else "") + "._")
    if annual and fmt is MeetingFormat.TELECONFERENCE:
        out.append("")
        out.append("_This is the annual meeting. If election ballots are counted and tabulated at it, the meeting cannot be held "
                   "entirely by teleconference: a physical location must be open (CIV 4926(b), 5120)._")
    if schedule is not None and schedule.regular_months and meeting.month not in schedule.regular_months:
        out.append("")
        out.append(f"_{schedule.resolution} fixes regular meetings in months {', '.join(map(str, schedule.regular_months))}; "
                   "unless a later resolution makes every month regular, this meeting is a special meeting._")
    out.append("")
    out += agenda_items(previous, items, meeting, schedule, include_open=include_open, previous_meeting=previous_meeting,
                        subjects=subjects)
    out.append("")
    out.append("_Drafted by jason from the last agenda and the board's action items; the board sets the agenda._")
    return out


def agenda_values(previous: AgendaDoc, meeting: date, schedule: Any, *, tech_contact: str = "") -> dict[str, str]:
    """The agenda template's tokens for ``meeting``: the date and time from the schedule, the Zoom details from the last
    agenda's header (a standing meeting keeps its link, ID, and number). A value it cannot find is left out, so the token
    stays visible in the Doc for the secretary."""
    annual = schedule is not None and schedule.annual_month == meeting.month and schedule.day_in(meeting.year, meeting.month) == meeting
    phone = re.search(r"\(\d{3}\)\s*\d{3}-\d{4}", previous.header)
    meeting_id = re.search(r"Meeting ID:?\s*([\d ]{9,})", previous.header)
    link = next((u for u in previous.links if "zoom.us" in u), "")
    values = {"MEETING_KIND": "Annual Meeting of the Members" if annual else "Regular Meeting of the Board of Directors",
              "MEETING_DATE": f"{meeting:%A, %B} {meeting.day}, {meeting.year}",
              "MEETING_TIME": str(getattr(schedule, "time", "7:00 pm")),
              "ZOOM_LINK": link, "ZOOM_PHONE": phone.group(0) if phone else "",
              "ZOOM_MEETING_ID": meeting_id.group(1).strip() if meeting_id else "", "TECH_CONTACT": tech_contact}
    return {k: v for k, v in values.items() if v}


# The heading the agenda template's note points to ("how to ask follows the agenda"; ``templates.BODIES``).
DELIVERY_HEADING = "How notices are delivered"


def delivery_section(data_dir: Path | None, request: str = "") -> list[str]:
    """The agenda Doc's closing section, after ``agenda_items``: the statutes on individual delivery recited from disk
    and where to write (``individual_delivery_lines``), which the template's teleconference note points to."""
    return ["", f"### {DELIVERY_HEADING}", "", *individual_delivery_lines(data_dir, request)]


HIGHLIGHT ={"color": {"rgbColor": {"red": 1.0, "green": 0.95, "blue": 0.6}}}


def insertion_requests(doc: dict[str, Any], items: list[BoardItem], *, before: str = "Open Forum",
                       highlight: bool = False) -> list[dict[str, Any]]:
    """Docs ``batchUpdate`` requests that add each item as an agenda heading, with a short note under it, just before the
    ``before`` heading. Inserted at the start of that heading's paragraph, each title keeps its heading style and list
    numbering; each note becomes plain text. Send them with ``write_mode="SUGGEST"`` so the secretary accepts or rejects
    each; with ``highlight`` (for normal edits) the inserted text is shaded so it stands out."""
    body = (doc.get("tabs") or [{}])[0].get("documentTab", {}).get("body") or doc.get("body", {})
    target = None
    for block in body.get("content", []):
        paragraph = block.get("paragraph")
        if paragraph and re.match(re.escape(before), _text(paragraph), re.I):
            target = block["startIndex"]
            break
    if target is None or not items:
        return []
    text, notes = "", []
    for item in items:
        text += f"{item.title}\n"
        note = f"{item.ask}" + (f" ({item.authority})" if item.authority else "") + (f" Notice: {item.special_notice}." if item.special_notice else "")
        start = target + len(text)
        text += note + "\n"
        notes.append((start, start + len(note) + 1))
    requests: list[dict[str, Any]] = [{"insertText": {"location": {"index": target}, "text": text}}]
    for start, end in notes:
        rng = {"startIndex": start, "endIndex": end}
        requests.append({"deleteParagraphBullets": {"range": rng}})
        requests.append({"updateParagraphStyle": {"range": rng, "paragraphStyle": {"namedStyleType": "NORMAL_TEXT"},
                                                  "fields": "namedStyleType"}})
    if highlight:
        requests.append({"updateTextStyle": {"range": {"startIndex": target, "endIndex": target + len(text)},
                                             "textStyle": {"backgroundColor": HIGHLIGHT}, "fields": "backgroundColor"}})
    return requests


def minutes_template(meeting: date, directors: list[str], agenda_lines: list[str], *, quorum: int | None = None,
                     quorum_source: str = "", roll_call: bool = True) -> list[str]:
    """The minutes' frame for a meeting: each section with its instructions in braces (``jason.community.minutes_template``),
    the business section once per agenda item, and the tables for attendance and motions. ``quorum_source`` is the
    provision that sets the quorum (``BoardRule.quorum_source``); ``roll_call`` says the meeting is held entirely by
    teleconference, where every director vote is by roll call (CIV 4926(a)(3))."""
    from jason.community.minutes_template import render

    items = tuple(re.sub(r"^\d+\.\s*\*\*|\*\*.*$", "", line).strip() for line in agenda_lines if re.match(r"^\d+\. \*\*", line))
    out = render(meeting, items=items)
    at = out.index("## Attendance and quorum") + 1
    cite = f" ({quorum_source})" if quorum_source else ""
    table = ["", "| Director | Present | Absent | Joined / left |", "|---|---|---|---|", *[f"| {d} | | | |" for d in directors], "",
             f"Quorum: {quorum} directors{cite}. Quorum present: yes / no." if quorum else "Quorum present: yes / no."]
    out[at:at] = table
    at = out.index("## Business") + 1
    out[at:at] = ["", "Every motion's vote is by roll call (CIV 4926(a)(3)):" if roll_call else "Each motion's vote, by director:", "",
                  "| # | Item | Motion | Moved | Seconded | " + " | ".join(directors) + " | Result |",
                  "|---|---|---|---|---|" + "---|" * len(directors) + "---|",
                  "| 1 | | | | | " + " | ".join("" for _ in directors) + " | carried / failed |"]
    return out


__all__ = ["AgendaDoc", "AgendaHeading", "parse_doc", "read_doc", "agenda_items", "agenda_values", "delivery_section",
           "draft", "format_lines", "individual_delivery_lines", "executive_lines", "minutes_template"]
