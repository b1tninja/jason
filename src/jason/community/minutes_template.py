"""The minutes of a board meeting as sections, each with the instructions that say what it must record.

A ``MinutesSection`` is a heading and a ``prompt``: the instructions a person or the local model follows to write that
section from the meeting's record (the transcript up to the executive session, the attendance, the agenda). The prompt
states what the law or the bylaws require the section to hold, and ``answers`` names the minutes questions
(``jason.community.question_sets.MINUTES``) the section answers. The template and the check are one list: minutes
written from these sections are what the questions look for, and a question with no section is a gap in the template.

``render`` writes the template with each prompt in braces, ``{like this}``, for the Secretary or the model to replace.
A section marked ``confidential`` says only the general nature of what it covers (the executive session, CIV 4935(e)).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class MinutesSection:
    key: str
    heading: str
    prompt: str
    authority: str = ""
    answers: tuple[str, ...] = ()        # the minutes questions this section answers
    per_item: bool = False               # written once for each agenda item
    confidential: bool = False           # the general nature only; never names, amounts, or what was said


UNKNOWN = "___ (not in the record)"

SECTIONS: tuple[MinutesSection, ...] = (
    MinutesSection("meeting", "Meeting",
                   "State the meeting's type (regular, special, emergency, annual, or organizational), its date, and that it "
                   "was held by teleconference (Zoom), with the physical location if there was one.",
                   "CIV 4920, 4926", ("meeting_date", "meeting_type", "draft")),
    MinutesSection("call_to_order", "Call to order",
                   "The time the chair called the meeting to order, as the record shows it happening (not the scheduled "
                   "time), and who called it.", "Bylaws", ("called_to_order",)),
    MinutesSection("attendance", "Attendance and quorum",
                   "A roll call: each director by name, present or absent, and when a director joined late or left early. "
                   "Others present by role (manager, counsel), and members by count. The number of directors in office, "
                   "and whether a quorum (a majority of the directors in office, at least two) was present.",
                   "Bylaws 7.10, 10.10", ("quorum", "directors_present")),
    MinutesSection("prior_minutes", "Approval of prior minutes",
                   "Each earlier meeting's minutes the board considered, any corrections, and the motion approving them "
                   "with each director's vote.", "CIV 4950", ("prior_minutes_approved",)),
    MinutesSection("business", "Business",
                   "For each agenda item: one to three sentences on the discussion. Then each motion: its words, who moved "
                   "and who seconded, each director's vote by roll call, and whether it carried or failed. Give every dollar "
                   "amount approved and what it is for. A transfer or loan from the reserves records the board's written "
                   "finding: the reason and how and when it will be repaid. Record no action on a matter that was not on "
                   "the agenda. Never name a member, or give a member's balance, in a delinquency, payment plan, violation, "
                   "discipline, or foreclosure: those are executive session matters, noted only generally.",
                   "CIV 4926(a)(3), 4930, 4935, 5515(c)",
                   ("decision_topics", "vote_recorded", "roll_call", "amounts_approved", "reserve_transfer"), per_item=True),
    MinutesSection("open_forum", "Open forum",
                   "Whether members spoke in the open forum and the general subjects they raised, or that no member came "
                   "forward. No names are needed.", "CIV 4925(b)", ("open_forum",)),
    MinutesSection("executive_session", "Executive session",
                   "Only the general nature of the matters the board took up in executive session since the last open "
                   "meeting: litigation, formation of contracts, member discipline, personnel, a member's assessment payment "
                   "plan, or a foreclosure decision. No names, amounts, or what was said.", "CIV 4935(a)-(e)",
                   ("executive_session", "executive_topics"), confidential=True),
    MinutesSection("next_meeting", "Next meeting", "The date, time, and place (or Zoom) of the next meeting.", "CIV 4920",
                   ("next_meeting",)),
    MinutesSection("adjournment", "Adjournment",
                   "The time the meeting was adjourned, or adjourned to executive session.", "Bylaws", ("adjourned",)),
    MinutesSection("recorder", "Recorded by",
                   "Who took the minutes (the Secretary), and a line for the date the board approved them.", "Bylaws 10.10",
                   ("recorder",)),
)

FOOTER = ("Minutes, draft minutes marked DRAFT, or a summary are available to members within 30 days of the meeting "
          "(CIV 4950(a)) and are kept permanently (CIV 5210(a)(2)).")


def render(meeting: date, sections: tuple[MinutesSection, ...] = SECTIONS, *, items: tuple[str, ...] = ()) -> list[str]:
    """The template as Markdown: each section's heading and its prompt in braces; the business section once per item."""
    out = [f"# DRAFT Minutes of {meeting.month}/{meeting.day}/{meeting.year % 100:02d}", ""]
    for s in sections:
        out += [f"## {s.heading}", ""]
        if s.per_item and items:
            for n, item in enumerate(items, 1):
                out += [f"### {n}. {item}", "", f"{{{s.prompt}}}", ""]
        else:
            out += [f"{{{s.prompt}}}", ""]
        if s.authority:
            out += [f"_({s.authority})_", ""]
    out += [f"_{FOOTER}_"]
    return out


def uncovered(sections: tuple[MinutesSection, ...], question_keys: tuple[str, ...]) -> list[str]:
    """The minutes questions no section answers: gaps in the template itself."""
    answered = {k for s in sections for k in s.answers}
    return [k for k in question_keys if k not in answered]


__all__ = ["FOOTER", "SECTIONS", "UNKNOWN", "MinutesSection", "render", "uncovered"]
