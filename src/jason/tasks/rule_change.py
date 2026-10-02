"""A proposed operating rule change, carried through Civil Code 4360: notice, decision, notice of adoption.

Given a ``RuleChange`` (the specification's ``rule_changes()``), the meeting schedule, and the day the member notice
goes out, this builds three things and writes them to ``data/board/rule-change-<slug>.md``:

(a) the **member notice** of the proposed change, by general notice (Civil Code 4045) at least 28 days before the board
    decides: the text of the change, its purpose and effect (4360(a)), how and by when members may comment, and the
    decision meeting (4360(b));
(b) the **agenda item** for the decision meeting (agenda with the meeting notice, 4920);
(c) the **notice of adoption** to deliver within 15 days after the decision (4360(c)), with the members' right to call
    a vote to reverse it (4365).

The decision meeting defaults to the first meeting on the schedule at least 28 days after the notice date. The current
words of each section come from the rule's outline on disk (``data/outlines/<document>.json``). The statutes are quoted
from ``data/authorities`` when exported; a citation not found there is marked unverified, never paraphrased as a quote.

jason sends nothing. ``email_draft`` builds a Gmail draft with no recipients, which a person addresses and sends from
Gmail; ``save_draft`` only creates it. Fees and dates the board must decide stay as ``[bracketed]`` placeholders.
"""

from __future__ import annotations

import json
import re
import textwrap
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from jason.community.base import MeetingSchedule
from jason.community.rule_changes import RuleChange, SectionChange

NOTICE_DAYS = 28            # Civil Code 4360(a)
ADOPTION_NOTICE_DAYS = 15   # Civil Code 4360(c)
REVERSAL_REQUEST_DAYS = 30  # Civil Code 4365(b)
AGENDA_NOTICE_DAYS = 4      # Civil Code 4920(a)
BOARD_DIR = "board"


@dataclass(frozen=True)
class Timeline:
    """The dates a rule change runs on. ``notice_by`` is the last day the member notice may go out for ``decision``."""

    notice_date: date
    decision: date
    comment_deadline: date
    agenda_notice_by: date
    adoption_notice_by: date
    reversal_request_by: date
    notice_by: date
    policy_statement: tuple[date, date] | None = None

    @property
    def lead_days(self) -> int:
        return (self.decision - self.notice_date).days


def first_decision_date(schedule: MeetingSchedule, notice_date: date, *, monthly: bool = True,
                        lead_days: int = NOTICE_DAYS) -> date:
    """The first scheduled meeting at least ``lead_days`` after ``notice_date``. ``monthly`` follows the board's practice
    (every month); without it only the resolution's regular months count."""
    return schedule.next_meeting(notice_date + timedelta(days=lead_days - 1), monthly=monthly)


def timeline(schedule: MeetingSchedule | None, *, notice_date: date, decision: date | None = None, monthly: bool = True,
             comment_deadline: date | None = None, fiscal_year_end: date | None = None) -> Timeline:
    """The rule change's dates. A ``decision`` fewer than 28 days after ``notice_date`` is refused (4360(a))."""
    if decision is None:
        if schedule is None:
            raise ValueError("no meeting schedule in the specification; give the decision date")
        decision = first_decision_date(schedule, notice_date, monthly=monthly)
    if (decision - notice_date).days < NOTICE_DAYS:
        raise ValueError(f"{decision} is {(decision - notice_date).days} days after the notice on {notice_date}; "
                         f"Civil Code 4360(a) needs at least {NOTICE_DAYS}")
    comment = comment_deadline or decision - timedelta(days=1)
    if not notice_date <= comment <= decision:
        raise ValueError("the comment deadline must fall between the notice and the decision meeting")
    adoption_by = decision + timedelta(days=ADOPTION_NOTICE_DAYS)
    window = None
    if fiscal_year_end is not None:   # the annual policy statement goes out 30 to 90 days before the fiscal year ends (5310(a))
        window = (fiscal_year_end - timedelta(days=90), fiscal_year_end - timedelta(days=30))
    return Timeline(notice_date=notice_date, decision=decision, comment_deadline=comment,
                    agenda_notice_by=decision - timedelta(days=AGENDA_NOTICE_DAYS), adoption_notice_by=adoption_by,
                    reversal_request_by=adoption_by + timedelta(days=REVERSAL_REQUEST_DAYS),
                    notice_by=decision - timedelta(days=NOTICE_DAYS), policy_statement=window)


def find_change(changes: tuple[RuleChange, ...], key: str) -> RuleChange:
    for change in changes:
        if key in (change.key, change.slug):
            return change
    known = ", ".join(c.key for c in changes) or "none"
    raise LookupError(f"no proposed rule change {key!r} (known: {known})")


# --- the current words, from the outline ----------------------------------------------------------------------------


def current_sections(data_dir: Path, document: str) -> dict[str, str]:
    """Each section's current words from ``data/outlines/<document>.json``, by outline number. Empty when not on disk."""
    path = data_dir / "outlines" / f"{document}.json"
    if not path.is_file():
        return {}
    outline = json.loads(path.read_text(encoding="utf-8"))
    text = outline.get("text") or ""
    out: dict[str, str] = {}
    for section in outline.get("sections") or []:
        body = text[section["start"]:section["end"]].strip()
        out[section["number"]] = re.sub(r"\n{3,}", "\n\n", body)
    return out


def _fold(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def proposed_section_text(section: SectionChange, current: str) -> str:
    """The section as it would read. A ``strike`` amendment replaces its words inside the current text."""
    if section.repeal:
        return "[Section repealed.]"
    if section.strike:
        folded = _fold(current)
        if section.strike not in folded:
            return f"[Replace \"{section.strike}\" with \"{section.proposed}\"; the current text was not found on disk.]"
        return folded.replace(section.strike, section.proposed, 1)
    return section.proposed


def section_blocks(change: RuleChange, current: dict[str, str]) -> list[str]:
    """Markdown blocks, one per section: the instruction, the current words, and the proposed words."""
    blocks: list[str] = []
    for section in change.sections:
        now = current.get(section.number, "")
        head = f"### {section.label}: {section.title}"
        if section.new:
            lines = [head, "", "Add a new section:", "", _quote(section.proposed)]
        elif section.strike:
            lines = [head, "", f"Replace the words \"{section.strike}\" with \"{section.proposed}\"", "", "As amended:", "",
                     _quote(proposed_section_text(section, now))]
        else:
            lines = [head, "", "Current text:", "", _quote(now or "[current text not on disk]"), "",
                     "Proposed text (replaces the section):", "", _quote(proposed_section_text(section, now))]
        if section.note:
            lines += ["", f"*Note:* {section.note}"]
        blocks.append("\n".join(lines))
    return blocks


def _quote(text: str) -> str:
    return "\n".join("> " + line if line else ">" for line in text.strip().splitlines())


def _plain(text: str, width: int = 100) -> str:
    return "\n\n".join(textwrap.fill(_fold(p), width) for p in re.split(r"\n\s*\n", text.strip()) if p.strip())


# --- the three documents -------------------------------------------------------------------------------------------


def _day(d: date) -> str:
    return f"{d:%A}, {d:%B} {d.day}, {d.year}"


@dataclass(frozen=True)
class Notice:
    subject: str
    text: str


def member_notice(change: RuleChange, when: Timeline, current: dict[str, str], association: str,
                  schedule: MeetingSchedule | None = None) -> Notice:
    """The general notice of the proposed rule change (Civil Code 4360(a)), as plain text for mail or email."""
    place = f" at {schedule.time} on {schedule.place}" if schedule else ""
    parts = [
        f"{association.upper()}",
        "NOTICE OF PROPOSED RULE CHANGE",
        f"Date of this notice: {_day(when.notice_date)}",
        "",
        _plain(f"The Board of Directors proposes to amend the {change.document_title}. Civil Code section 4360(a) "
               f"requires the Board to give members notice of a proposed rule change at least 28 days before making "
               f"it, with the text of the change and a description of its purpose and effect. The Board will consider "
               f"members' comments and decide on the change at its open meeting on {_day(when.decision)}{place}."),
        "",
        "PURPOSE OF THE PROPOSED CHANGE",
        _plain(change.purpose),
        "",
        "EFFECT OF THE PROPOSED CHANGE",
        _plain(change.effect),
        "",
        "TEXT OF THE PROPOSED CHANGE",
    ]
    for section in change.sections:
        parts.append("")
        if section.strike:
            parts.append(f"{section.label} ({section.title}): replace the words \"{section.strike}\" with "
                         f"\"{section.proposed}\".")
        elif section.repeal:
            parts.append(f"{section.label} ({section.title}): repeal.")
        else:
            verb = "add" if section.new else "replace the section with"
            parts.append(f"{section.label} ({section.title}): {verb}:")
            parts.append(_plain(section.proposed))
    parts += [
        "",
        "HOW TO COMMENT",
        _plain(f"Members may send written comments by {_day(when.comment_deadline)} to [comment address or email], "
               f"or speak during the member comment period of the {_day(when.decision)} meeting. The Board will "
               f"consider the comments before it decides (Civil Code 4360(b)). The full current "
               f"{change.document_title} is available on request [or at the Association's website]."),
        "",
        _plain(f"If the Board adopts a change, members will receive notice of it within 15 days (Civil Code "
               f"4360(c)). Members owning 5 percent or more of the separate interests may call a special vote of the "
               f"members to reverse a rule change by a written request delivered within 30 days after that notice "
               f"(Civil Code 4365)."),
        "",
        "Board of Directors",
        association,
    ]
    return Notice(subject=f"Notice of proposed rule change: {change.document_title} (comments by "
                          f"{when.comment_deadline:%B} {when.comment_deadline.day})", text="\n".join(parts))


REQUIRED_ELEMENTS: tuple[tuple[str, str], ...] = (
    ("Delivered by general notice (Civil Code 4045)", "CIV 4360(a)"),
    ("At least 28 days before the board decides", "CIV 4360(a)"),
    ("The text of the proposed rule change", "CIV 4360(a)"),
    ("A description of the purpose of the proposed rule change", "CIV 4360(a)"),
    ("A description of the effect of the proposed rule change", "CIV 4360(a)"),
    ("The decision at a board meeting, after considering members' comments (deadline and means to comment)", "CIV 4360(b)"),
)


def required_elements(notice: Notice, change: RuleChange, when: Timeline) -> list[tuple[str, str, bool]]:
    """Each element 4360 asks of the notice and the process, and whether this notice carries it."""
    text = notice.text
    has_text = all((s.strike and s.proposed in text) or (not s.strike and _fold(s.proposed)[:60] in _fold(text))
                   for s in change.sections if not s.repeal)
    checks = (
        True,   # the method is the sender's: the notice says nothing about it; see the delivery note
        when.lead_days >= NOTICE_DAYS,
        has_text,
        "PURPOSE OF THE PROPOSED CHANGE" in text and _fold(change.purpose)[:60] in _fold(text),
        "EFFECT OF THE PROPOSED CHANGE" in text and _fold(change.effect)[:60] in _fold(text),
        "HOW TO COMMENT" in text and f"{when.comment_deadline:%B}" in text and _day(when.decision) in text,
    )
    return [(name, cite, ok) for (name, cite), ok in zip(REQUIRED_ELEMENTS, checks)]


def agenda_item(change: RuleChange, when: Timeline) -> str:
    """The open-session agenda item for the decision meeting."""
    sections = ", ".join(s.label.replace("Section ", "") for s in change.sections)
    return "\n".join([
        f"**Consider adoption of the proposed amendment to the {change.document_title}** ({change.title}).",
        "",
        f"- Notice of the proposed change was given on {_day(when.notice_date)}, {when.lead_days} days before this "
        f"meeting (Civil Code 4360(a): at least 28).",
        f"- Sections affected: {sections}.",
        f"- Members' written comments received by {_day(when.comment_deadline)}: [summary of comments]. Member comment "
        f"period at this meeting (Civil Code 4925).",
        "- Board to resolve the bracketed choices: " + "; ".join(change.placeholders()) + ".",
        f"- Proposed motion: \"To adopt the amendment to the {change.document_title} as noticed to members on "
        f"{_day(when.notice_date)} [with the following changes: ...], effective [effective date], and to direct that "
        f"notice of the adopted change be delivered to members by general notice no later than "
        f"{_day(when.adoption_notice_by)}.\"",
        f"- The agenda goes out with the meeting notice by {_day(when.agenda_notice_by)} (Civil Code 4920). A change "
        f"to the noticed text that is more than a refinement may need a new 28-day notice (counsel).",
    ])


def adoption_notice(change: RuleChange, when: Timeline, association: str) -> Notice:
    """The general notice of the adopted rule change (Civil Code 4360(c)), a template the secretary completes."""
    parts = [
        association.upper(),
        "NOTICE OF ADOPTED RULE CHANGE",
        "Date of this notice: [date, no later than " + _day(when.adoption_notice_by) + "]",
        "",
        _plain(f"At its open meeting on {_day(when.decision)}, the Board of Directors adopted an amendment to the "
               f"{change.document_title}, after considering the comments members made on the proposed change noticed "
               f"on {_day(when.notice_date)}. The amendment takes effect on [effective date]."),
        "",
        "WHAT CHANGED",
        _plain(change.effect),
        "",
        "[Attach or quote the text as adopted. If the Board changed the noticed text, quote the adopted words.]",
        "",
        "YOUR RIGHT TO CALL A VOTE TO REVERSE THE CHANGE",
        _plain("Under Civil Code section 4365, members owning 5 percent or more of the separate interests may call a "
               "special vote of the members to reverse this rule change by delivering a written request to the "
               "Association no more than 30 days after the date of this notice. The vote is then held not less than "
               "35 nor more than 90 days after the Association receives a proper request."),
        "",
        "Board of Directors",
        association,
    ]
    return Notice(subject=f"Notice of adopted rule change: {change.document_title}", text="\n".join(parts))


# --- the statutes --------------------------------------------------------------------------------------------------


def authority_status(data_dir: Path, change: RuleChange) -> list[dict[str, Any]]:
    """Each citation the change names, read from ``data/authorities``: found with its page, or not found."""
    from jason.tasks.export_authorities import authority_text

    rows = []
    for citation in change.authorities:
        hit = authority_text(data_dir, citation)
        rows.append({"citation": citation, "found": bool(hit.get("found")), "page": hit.get("page", ""),
                     "session": hit.get("session", ""), "text": hit.get("text", ""), "reason": hit.get("reason", "")})
    return rows


# --- the page and the draft ----------------------------------------------------------------------------------------


def render_markdown(change: RuleChange, when: Timeline, current: dict[str, str], association: str,
                    schedule: MeetingSchedule | None, authorities: list[dict[str, Any]]) -> str:
    notice = member_notice(change, when, current, association, schedule)
    elements = required_elements(notice, change, when)
    adopted = adoption_notice(change, when, association)
    lines = [
        f"# Rule change: {change.title}",
        "",
        "**" + " ".join(change.caveats) + "**",
        "",
        "## Timeline (Civil Code 4360)",
        "",
        "| Step | Date | Rule |",
        "|---|---|---|",
        f"| Member notice goes out (general notice, 4045) | {when.notice_date} | assumed send date |",
        f"| Last day to send the notice for this meeting | {when.notice_by} | 4360(a): 28 days before |",
        f"| Members' written comments due | {when.comment_deadline} | the board's choice; 4360(b) |",
        f"| Agenda and meeting notice out | {when.agenda_notice_by} | 4920(a): 4 days before |",
        f"| **Board decides at its meeting** | **{when.decision}** | 4360(b); {when.lead_days} days after notice |",
        f"| Notice of the adopted change, at the latest | {when.adoption_notice_by} | 4360(c): 15 days after |",
        f"| Members' request for a reversal vote, at the latest | {when.reversal_request_by} | 4365(b): 30 days after the adoption notice (counted from the latest day it may go out) |",
    ]
    if when.policy_statement:
        start, end = when.policy_statement
        lines.append(f"| Annual policy statement window | {start} to {end} | 5310(a): 30 to 90 days before the fiscal year ends |")
    if schedule and schedule.annual_month == when.decision.month:
        lines += ["", f"{when.decision:%B} is the annual meeting month on the schedule: confirm the board meets that "
                      f"day in open session (the decision may follow the annual meeting of members)."]
    if schedule:
        lines += ["", f"Meetings: {schedule.practice or 'the schedule'} at {schedule.time} on {schedule.place} "
                      f"({schedule.resolution}; regular months in the resolution: "
                      f"{', '.join(str(m) for m in schedule.regular_months) or 'every month'})."]
    lines += ["", "## What the board and counsel must decide", ""]
    lines += [f"{i}. {d}" for i, d in enumerate(change.decisions, 1)]
    lines += ["", "Placeholders in the proposed text: " + ", ".join(f"`{p}`" for p in change.placeholders()) + ".",
              "", "## The proposed amendment, section by section", ""]
    lines += ["\n\n".join(section_blocks(change, current)), ""]
    lines += ["## (a) Member notice of the proposed rule change (4360(a))", "",
              f"Subject: {notice.subject}", "", "```text", notice.text, "```", "",
              "Required elements:", ""]
    lines += [f"- [{'x' if ok else ' '}] {name} ({cite})" for name, cite, ok in elements]
    lines += ["", "Delivery: by general notice under Civil Code 4045 (individual delivery to members who asked for it, "
              "4045(b), by each member's preferred delivery method under 4040 and 4041). Email only the members whose "
              "preferred method is email; mail the rest.", "",
              "## (b) Agenda item for the decision meeting", "", agenda_item(change, when), "",
              "## (c) Notice of the adopted rule change (4360(c)), template", "",
              f"Subject: {adopted.subject}", "", "```text", adopted.text, "```", "",
              "## The law, as exported to data/authorities", ""]
    for row in authorities:
        if row["found"]:
            lines += [f"### {row['citation']} ({row['page']}{', ' + str(row['session']) + ' session' if row['session'] else ''})",
                      "", _quote(row["text"]), ""]
        else:
            lines += [f"### {row['citation']}: not verified", "", f"{row['reason']}", ""]
    return "\n".join(lines).rstrip() + "\n"


def write(data_dir: Path, change: RuleChange, markdown: str) -> Path:
    path = data_dir / BOARD_DIR / f"rule-change-{change.slug}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(markdown, encoding="utf-8")
    return path


def email_draft(notice: Notice):
    """The member notice as a Gmail draft with no recipients: a person addresses it (Bcc the members whose preferred
    delivery method is email, Civil Code 4041) and sends it from Gmail."""
    from jason.google.gmail_drafts import DraftMessage

    return DraftMessage(to=(), subject=notice.subject, text=notice.text)


def save_draft(gmail: Any, draft: Any) -> dict[str, Any]:
    """Create the draft. ``GmailDrafts`` has no send method; this calls ``create`` and nothing else."""
    if draft.to or draft.cc or draft.bcc:
        raise ValueError("a rule change notice draft leaves the recipients to the person")
    return gmail.create(draft)


__all__ = ["Notice", "Timeline", "adoption_notice", "agenda_item", "authority_status", "current_sections", "email_draft",
           "find_change", "first_decision_date", "member_notice", "render_markdown", "required_elements", "save_draft",
           "timeline", "write"]
