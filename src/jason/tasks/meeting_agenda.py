"""Draft the next board meeting's agenda from the last one, the way the secretary does, with what the law asks added.

The board's agendas are Google Docs ("My Drive/Meetings/<year>/Agenda for M/D/YY"): a header table with the meeting's date
and Zoom details, numbered headings for the standing items and the month's business, the open forum, the next meeting,
the executive session, and the decorum rules. The secretary copies last month's and updates it. ``read_doc`` reads such
a Doc (read-only, smart chips included: linked files, dates, people) into an ``AgendaDoc``; ``draft`` makes the next
meeting's agenda from it as Markdown:

- the date is the schedule's next meeting (``Mystique.meeting_schedule()``: third Tuesdays), with the notice deadline
  (four days before; CIV 4920) and the note that an item not on the agenda cannot be acted on (4930);
- the header carries what an all-teleconference meeting's notice must: technical instructions, the telephone and email
  of a person who can help before and during the meeting, and the reminder that members may ask for individual delivery
  of notices (CIV 4926(a)(1)); and states that every vote of the directors is by roll call (4926(a)(3));
- the standing items carry forward; the business items carry forward marked "carried over" for the board to keep or drop;
- the board's action items proposed for this meeting (``data/board/items.json``) join the business, labeled action or
  report, with their authority and any notice of their own; the litigation and collections items go to executive session;
- a report of the last executive session is added (4935(e)); the annual meeting at which ballots are counted cannot be
  held entirely by teleconference (4926(b)), and the draft says so in November.

``minutes_template`` drafts the minutes' frame: attendance and quorum (Bylaws 7.10), each motion with mover, second, and
the roll call by director, the executive session's general note, and the next steps. Drafts only; the board sets the
agenda and approves the minutes.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from jason.community.board_items import PRIORITY_ORDER, BoardItem, ItemCategory, ItemStatus, Session, agenda_session

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


def _meeting_line(header: str, meeting: date, schedule: Any) -> str:
    # "To be held on: Sep 15, 2026 7:00 PM PDT via Zoom (669) ..." keeps "via Zoom (669) ..." for the new date.
    zoom = re.sub(r"^To be held on:?.*?(?=\bvia\b)", "", header).strip()
    when = f"{meeting:%A, %B} {meeting.day}, {meeting.year} at {getattr(schedule, 'time', '7:00 pm')}"
    return f"To be held on {when}, {zoom or 'on Zoom'}"


ACTION = re.compile(r"\b(adopt|decide|direct|authorize|approve|fill|correct|refer)\b", re.I)

# An executive session is noticed by the general nature of its business (CIV 4935(a)-(d)); an item's own title and ask
# stay in the directors' packet. Each category's general heading, and the words that show the last agenda already has it.
GENERAL_NATURE: dict[ItemCategory, tuple[str, str]] = {
    ItemCategory.LEGAL: ("Legal Matters", r"legal|litigation"),
    ItemCategory.COLLECTIONS: ("Delinquencies", r"delinquen|collection|payment plan"),
}
OTHER_EXECUTIVE = ("Other matters Civil Code Section 4935(a) permits in executive session", r"4935\(a\) permits")


def _kind(title: str) -> str:
    if re.search(r"approval|appointment|proposal|adopt", title, re.I):
        return "action"
    if re.search(r"treasurer|report|review", title, re.I):
        return "report"
    return ""


def agenda_items(previous: AgendaDoc, items: list[BoardItem], meeting: date, schedule: Any, *, include_open: bool = False,
                 previous_meeting: date | None = None) -> list[str]:
    """The agenda's business as Markdown, for the agenda Doc's ``{AGENDA_ITEMS}`` and the draft file: the last agenda's
    standing items carried forward, what it carried over flagged for the board to keep or drop, the board's action items
    as New Business (each with the action proposed and any notice the law requires; the background is in the packet),
    the executive session by the general nature of its business, and the decorum rules."""
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
    executive = [h.title for h in after[1:]]
    for i in executive_items:
        heading, present = GENERAL_NATURE.get(i.category, OTHER_EXECUTIVE)
        if not any(re.search(present, e, re.I) for e in executive):
            executive.append(heading)
    item("Adjourn to Executive Session", "", [e for e in (after[0].notes[:1] if after else [])])
    out.extend(f"   - {e}" for e in executive)
    item("Adjournment")
    if previous.closing:
        out.append("")
        out.append("### " + previous.closing[0])
        out.extend(previous.closing[1:])
    return out


def draft(previous: AgendaDoc, items: list[BoardItem], meeting: date, schedule: Any, *, tech_contact: str = "",
          include_open: bool = False, previous_meeting: date | None = None) -> list[str]:
    """The next meeting's draft agenda (Markdown): the header the notice needs, the secretary's notes on the notice, and
    ``agenda_items``."""
    annual = schedule is not None and schedule.annual_month == meeting.month and schedule.day_in(meeting.year, meeting.month) == meeting
    notice_by = meeting - timedelta(days=4)
    out = [f"# DRAFT Agenda for {meeting.month}/{meeting.day}/{meeting.year % 100:02d}", ""]
    out.append(_meeting_line(previous.header, meeting, schedule))
    out.append("")
    out.append("To participate: join the Zoom meeting from the link, or by telephone at the number above with the meeting ID. "
               f"Technical help before and during the meeting: {tech_contact or '[name, telephone, and email of the person who can help]'} "
               "(CIV 4926(a)(1)(A), (B)).")
    out.append("You may ask to receive meeting notices by individual delivery; write to the board at the association's address "
               "or email (CIV 4926(a)(1)(C), 4040).")
    out.append("Every vote of the directors at this meeting is taken by roll call (CIV 4926(a)(3)).")
    out.append("")
    out.append(f"_Notice with this agenda must go out by {notice_by:%A, %B} {notice_by.day} (CIV 4920(a)); the board may act only on "
               "items on this agenda (CIV 4930)._")
    if annual:
        out.append("")
        out.append("_This is the annual meeting. If election ballots are counted and tabulated at it, the meeting cannot be held "
                   "entirely by teleconference: a physical location must be open (CIV 4926(b), 5120)._")
    if schedule is not None and schedule.regular_months and meeting.month not in schedule.regular_months:
        out.append("")
        out.append(f"_{schedule.resolution} fixes regular meetings in months {', '.join(map(str, schedule.regular_months))}; "
                   "unless a later resolution makes every month regular, this meeting is a special meeting._")
    out.append("")
    out += agenda_items(previous, items, meeting, schedule, include_open=include_open, previous_meeting=previous_meeting)
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


HIGHLIGHT = {"color": {"rgbColor": {"red": 1.0, "green": 0.95, "blue": 0.6}}}


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


def minutes_template(meeting: date, directors: list[str], agenda_lines: list[str], *, quorum: int | None = None) -> list[str]:
    """The minutes' frame for a meeting: each section with its instructions in braces (``jason.community.minutes_template``),
    the business section once per agenda item, and the roll-call tables for attendance and motions."""
    from jason.community.minutes_template import render

    items = tuple(re.sub(r"^\d+\.\s*\*\*|\*\*.*$", "", line).strip() for line in agenda_lines if re.match(r"^\d+\. \*\*", line))
    out = render(meeting, items=items)
    at = out.index("## Attendance and quorum") + 1
    table = ["", "| Director | Present | Absent | Joined / left |", "|---|---|---|---|", *[f"| {d} | | | |" for d in directors], "",
             f"Quorum: {quorum} directors (Bylaws 7.10). Quorum present: yes / no." if quorum else "Quorum present: yes / no."]
    out[at:at] = table
    at = out.index("## Business") + 1
    out[at:at] = ["", "Every motion's vote is by roll call (CIV 4926(a)(3)):", "",
                  "| # | Item | Motion | Moved | Seconded | " + " | ".join(directors) + " | Result |",
                  "|---|---|---|---|---|" + "---|" * len(directors) + "---|",
                  "| 1 | | | | | " + " | ".join("" for _ in directors) + " | carried / failed |"]
    return out


__all__ = ["AgendaDoc", "AgendaHeading", "parse_doc", "read_doc", "agenda_items", "agenda_values", "draft", "minutes_template"]
