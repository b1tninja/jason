"""A proposed operating rule change, carried through Civil Code 4360: notice, decision, notice of adoption.

Given a ``RuleChange`` (the specification's ``rule_changes()``), the meeting schedule, and the day the member notice
goes out, this builds three things and writes them to ``data/board/rule-change-<slug>.md``:

(a) the **member notice** of the proposed change, by general notice (Civil Code 4045) at least 28 days before the board
    decides: the text of the change, its purpose and effect (4360(a)), how and by when members may comment, and the
    decision meeting (4360(b));
(b) the **agenda item** for the decision meeting (agenda with the meeting notice, 4920);
(c) the **notice of adoption** to deliver within 15 days after the decision (4360(c)), with the members' right to call
    a vote to reverse it (4365).

The decision meeting defaults to the first meeting on the schedule at least 28 days after the notice date.

**The words.** Each section's current words come through the shared reader (``recite_sections``: the ``Shelf`` of
``jason.tasks.cite``, which reads the living document kept as amended, else the outline on disk), with the section's
citation, address (``jason://coll/14``), permanent id, and the version in force; the outline is read directly
(``current_sections``) only when the shelf cannot place a section, and the page says so. The proposed text is a stage
version of its own (``proposed_version``: ``coll@proposed-2026-11-01``, ``Stage.PROPOSED``): cited as itself, never
merged into the text in force.

**The order.** The member notice follows 4360(a), whose words are recited from disk: "the text of the proposed rule
change", then "a description of the purpose and effect of the proposed rule change", labeled as the board's own
description. The adoption notice (4360(c)) recites the text as adopted (the noticed text, for the secretary to correct
if the board changed it). Each notice is also checked against the catalog's required elements
(``jason.community.notice_elements``).

The statutes are quoted from ``data/authorities`` when exported; a citation not found there is marked unverified,
never paraphrased as a quote.

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
from jason.community.revisions import RecordVersion, Stage
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


@dataclass(frozen=True)
class Recital:
    """One section's current words as the shared reader recites them, and where they came from. ``source`` is
    ``shelf`` (the living document or the outline, through ``jason.tasks.cite``) or ``outline`` (read directly when the
    shelf could not place the section; ``reason`` says why)."""

    number: str
    words: str
    citation: str = ""
    address: str = ""
    pid: str = ""
    in_force: str = ""
    source: str = "shelf"
    reason: str = ""


def open_shelf(data_dir: Path | None = None, community: Any = None) -> Any:
    """The shared reader (``jason.tasks.cite.Shelf``): reading only."""
    from jason.tasks.cite import Shelf

    return Shelf(community, data_dir)


def recite_sections(change: RuleChange, *, shelf: Any = None, data_dir: Path | None = None,
                    community: Any = None) -> dict[str, Recital]:
    """Each section's current words, through the shelf by its address, with its citation, permanent id, and the
    version in force. A section the shelf cannot place is read from the outline on disk, marked so; a new section has
    no current words."""
    shelf = shelf if shelf is not None else open_shelf(data_dir, community)
    data_dir = Path(data_dir) if data_dir is not None else Path(shelf.data_dir)
    outline: dict[str, str] | None = None
    out: dict[str, Recital] = {}
    for section in change.sections:
        if section.new:
            continue
        found = None
        try:
            found = shelf.doc(change.document).section(section.number)
            ok = found.found and bool(found.text)
        except Exception:       # a reader that fails is a miss here, read from the outline instead
            ok = False
        if ok:
            out[section.number] = Recital(section.number, found.text, str(found), found.address, found.pid,
                                          found.in_force, "shelf")
            continue
        if outline is None:
            outline = current_sections(data_dir, change.document)
        words = outline.get(section.number, "")
        reason = (found.reason.value if found is not None and found.reason else "") or "not on the shelf"
        if words:
            out[section.number] = Recital(section.number, words, f"{change.document_title} {section.label}", "", "",
                                          f"data/outlines/{change.document}.json, read directly", "outline", reason)
    return out


def words_of(recitals: dict[str, Recital]) -> dict[str, str]:
    """The words alone, by section number (what ``current_sections`` returns)."""
    return {number: r.words for number, r in recitals.items()}


def proposed_version(change: RuleChange, when: Timeline, *, book: str = "", source: str = "") -> RecordVersion:
    """The proposed text as a stage version of the rule (``rules@proposed-2026-11-01``): noticed on the notice date,
    never in force, cited as itself and never merged into the text in force."""
    return RecordVersion(book or change.document, "", Stage.PROPOSED, when.notice_date, None,
                         source or f"specification:rule_changes/{change.key}",
                         "the notice of the proposed rule change (Civil Code 4360(a))",
                         "the text as proposed: not in force; cited as itself, never merged into the text in force")


def version_address(version: RecordVersion, number: str = "") -> str:
    """A stage version's address: ``jason://coll@proposed-2026-11-01/14``."""
    from jason.community.addresses import Address

    return Address(version.book, number, version=version.label().lstrip("@")).format()


LAW_SENTENCES: tuple[tuple[str, str], ...] = (
    ("CIV 4360(a)", "The notice shall include"),
    ("CIV 4360(c)", "As soon as possible after making a rule change"),
)


def recite_law(shelf: Any = None, *, data_dir: Path | None = None, community: Any = None) -> dict[str, str]:
    """The statute's own words the notices quote, read from ``data/authorities`` through the shelf: for 4360(a) and
    (c), the sentence that says what the notice must carry. A citation not on disk is left out (the notice then states
    the rule in its own words, and the page marks it unverified)."""
    shelf = shelf if shelf is not None else open_shelf(data_dir, community)
    out: dict[str, str] = {}
    for citation, phrase in LAW_SENTENCES:
        try:
            c = shelf(citation)
            words = (c.containing(phrase) if phrase else c.text) if c.found else ""
        except Exception:
            words = ""
        if words:
            out[citation] = _fold(re.sub(r"^\([a-z0-9]+\)\s*", "", words))
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


def _recited_from(r: Recital | None) -> str:
    """Where the current words were read: the citation, the address and permanent id, and the version in force."""
    if r is None:
        return ""
    bits = [r.citation] if r.citation else []
    if r.address:
        bits.append(f"`{r.address}`" + (f", permanent id `{r.pid}`" if r.pid else ""))
    if r.in_force:
        bits.append(r.in_force)
    if r.source == "outline":
        bits.append(f"the shelf could not place it ({r.reason})")
    return "; ".join(bits)


def section_blocks(change: RuleChange, current: dict[str, str], *, recitals: dict[str, Recital] | None = None,
                   version: RecordVersion | None = None) -> list[str]:
    """Markdown blocks, one per section: the instruction, the current words (recited, with where they came from), and
    the proposed words (the stage version's own address when given)."""
    blocks: list[str] = []
    recitals = recitals or {}
    for section in change.sections:
        now = current.get(section.number, "") or (recitals[section.number].words if section.number in recitals else "")
        head = f"### {section.label}: {section.title}"
        source = _recited_from(recitals.get(section.number))
        cur_label = "Current text" + (f" ({source})" if source else "") + ":"
        prop = f" (`{version_address(version, section.number)}`; not in force)" if version is not None else ""
        if section.new:
            lines = [head, "", f"Add a new section{prop}:", "", _quote(section.proposed)]
        elif section.strike:
            lines = [head, "", f"Replace the words \"{section.strike}\" with \"{section.proposed}\"", "",
                     f"As amended{prop}:", "", _quote(proposed_section_text(section, now))]
            if source:
                lines += ["", f"*Read from:* {source}."]
        else:
            lines = [head, "", cur_label, "", _quote(now or "[current text not on disk]"), "",
                     f"Proposed text (replaces the section){prop}:", "", _quote(proposed_section_text(section, now))]
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


TEXT_HEADING = "THE TEXT OF THE PROPOSED RULE CHANGE"
DESCRIPTION_HEADING = "THE BOARD'S DESCRIPTION OF THE PURPOSE AND EFFECT OF THE PROPOSED RULE CHANGE"
DESCRIPTION_LABEL = ("This description is the Board's own explanation; the proposed rule change itself is the text "
                     "above.")


def text_lines(change: RuleChange, current: dict[str, str] | None = None, *, current_label: str = "") -> list[str]:
    """The text of the proposed change, section by section, as the member notice prints it. With ``current_label``
    each replaced section also shows the words it replaces under that label ("Now reads")."""
    parts: list[str] = []
    for section in change.sections:
        parts.append("")
        now = (current or {}).get(section.number, "")
        if section.strike:
            parts.append(f"{section.label} ({section.title}): replace the words \"{section.strike}\" with "
                         f"\"{section.proposed}\".")
        elif section.repeal:
            parts.append(f"{section.label} ({section.title}): repeal.")
            if current_label and now:
                parts += [f"{current_label}:", _plain(now)]
        else:
            verb = "add" if section.new else "replace the section with"
            if current_label and now and not section.new:
                parts += [f"{section.label} ({section.title}).", f"{current_label}:", _plain(now),
                          "Proposed to read:", _plain(section.proposed)]
            else:
                parts.append(f"{section.label} ({section.title}): {verb}:")
                parts.append(_plain(section.proposed))
    return parts


def member_notice(change: RuleChange, when: Timeline, current: dict[str, str], association: str,
                  schedule: MeetingSchedule | None = None, *, law: dict[str, str] | None = None,
                  text_part: list[str] | None = None, current_label: str = "") -> Notice:
    """The general notice of the proposed rule change (Civil Code 4360(a)), as plain text for mail or email.

    It follows the subdivision's order: the text of the proposed rule change, then the board's description of its
    purpose and effect, labeled as the board's. ``law`` holds the statute's words (``recite_law``); with 4360(a)'s
    sentence on disk the notice quotes it, otherwise it states the rule in its own words. ``text_part`` replaces the
    section-by-section text (a whole document proposed as the change)."""
    place = f" at {schedule.time} on {schedule.place}" if schedule else ""
    law = law or {}
    rule = law.get("CIV 4360(a)", "")
    if rule:
        said = f"Civil Code section 4360(a) provides: \"{rule}\" The notice is given at least 28 days before the " \
               f"Board decides."
    else:
        said = ("Civil Code section 4360(a) requires the Board to give members notice of a proposed rule change at "
                "least 28 days before making it, with the text of the change and a description of its purpose and "
                "effect.")
    parts = [
        f"{association.upper()}",
        "NOTICE OF PROPOSED RULE CHANGE",
        f"Date of this notice: {_day(when.notice_date)}",
        "",
        _plain(f"The Board of Directors proposes to amend the {change.document_title}. {said} The Board will consider "
               f"members' comments and decide on the change at its open meeting on {_day(when.decision)}{place}."),
        "",
        TEXT_HEADING,
    ]
    parts += text_part if text_part is not None else text_lines(change, current, current_label=current_label)
    parts += [
        "",
        DESCRIPTION_HEADING,
        _plain(DESCRIPTION_LABEL),
        "",
        "PURPOSE OF THE PROPOSED CHANGE",
        _plain(change.purpose),
        "",
        "EFFECT OF THE PROPOSED CHANGE",
        _plain(change.effect),
    ]
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


ADOPTED_TEXT_HEADING = "THE TEXT OF THE RULE CHANGE AS ADOPTED"


def adopted_lines(change: RuleChange) -> list[str]:
    """The adopted text, recited section by section: the words as noticed, which the secretary replaces where the
    board adopted other words."""
    parts: list[str] = []
    for section in change.sections:
        parts.append("")
        if section.repeal:
            parts.append(f"{section.label} ({section.title}): repealed.")
        elif section.strike:
            parts.append(f"{section.label} ({section.title}): the words \"{section.strike}\" are replaced with "
                         f"\"{section.proposed}\".")
        else:
            parts.append(f"{section.label} ({section.title})" + (", a new section" if section.new else "") + ", now reads:")
            parts.append(_plain(section.proposed))
    return parts


def adoption_notice(change: RuleChange, when: Timeline, association: str, *, law: dict[str, str] | None = None,
                    text_part: list[str] | None = None) -> Notice:
    """The general notice of the adopted rule change (Civil Code 4360(c)), a template the secretary completes. It
    recites the text as adopted (the noticed words; the secretary replaces any the board changed), then the board's
    description, labeled as such."""
    rule = (law or {}).get("CIV 4360(c)", "")
    said = f" Civil Code section 4360(c) provides: \"{rule}\"" if rule else ""
    parts = [
        association.upper(),
        "NOTICE OF ADOPTED RULE CHANGE",
        "Date of this notice: [date, no later than " + _day(when.adoption_notice_by) + "]",
        "",
        _plain(f"At its open meeting on {_day(when.decision)}, the Board of Directors adopted an amendment to the "
               f"{change.document_title}, after considering the comments members made on the proposed change noticed "
               f"on {_day(when.notice_date)}. The amendment takes effect on [effective date].{said}"),
        "",
        ADOPTED_TEXT_HEADING,
    ]
    parts += text_part if text_part is not None else adopted_lines(change)
    parts += [
        "",
        "[If the Board adopted words other than those noticed, replace the text above with the words adopted, from the "
        "minutes.]",
        "",
        "WHAT CHANGED (the Board's description)",
        _plain(change.effect),
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


def element_lines(key: str, text: str) -> list[str]:
    """The catalog's required elements for one notice (``jason notice-check``'s check), as Markdown lines."""
    from jason.community.notice_catalog import requirement
    from jason.community.notice_elements import Status, check

    out = [f"Required elements of `{key}` (the catalog's reading; the statute's words are on disk):", ""]
    for f in check(requirement(key), text):
        mark = "x" if f.ok else (" " if f.status is not Status.UNCHECKED else "?")
        tail = f": {f.where}" if f.where else ""
        cond = f" (only for {f.applies})" if f.applies and not f.ok else ""
        out.append(f"- [{mark}] {f.element} ({f.cite}) {f.status.value}{cond}{tail}")
    return out


def versions_lines(change: RuleChange, recitals: dict[str, Recital], version: RecordVersion | None) -> list[str]:
    """The versions the page cites: each section's current words (the version in force, its address and permanent
    id), and the proposed stage version."""
    lines = ["## The versions cited", "",
             "| Section | Current words | Address | Permanent id | Version in force | Proposed (not in force) |",
             "|---|---|---|---|---|---|"]
    for section in change.sections:
        r = recitals.get(section.number)
        prop = f"`{version_address(version, section.number)}`" if version is not None else ""
        if r is None:
            lines.append(f"| {section.label} | {'a new section' if section.new else 'not on disk'} | | | | {prop} |")
            continue
        read = "the shelf" if r.source == "shelf" else f"the outline, read directly ({r.reason})"
        lines.append(f"| {section.label} | {read} | `{r.address}` | `{r.pid}` | {r.in_force} | {prop} |"
                     .replace("``", ""))
    if version is not None:
        lines += ["", f"The proposed text is the stage version `{version.book}{version.label()}` "
                      f"({version.stage.value}, noticed {version.on}): {version.note}. Its source: {version.source}."]
    return lines


def render_markdown(change: RuleChange, when: Timeline, current: dict[str, str], association: str,
                    schedule: MeetingSchedule | None, authorities: list[dict[str, Any]], *,
                    recitals: dict[str, Recital] | None = None, version: RecordVersion | None = None,
                    law: dict[str, str] | None = None) -> str:
    notice = member_notice(change, when, current, association, schedule, law=law)
    elements = required_elements(notice, change, when)
    adopted = adoption_notice(change, when, association, law=law)
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
    lines += ["\n\n".join(section_blocks(change, current, recitals=recitals, version=version)), ""]
    if recitals is not None or version is not None:
        lines += versions_lines(change, recitals or {}, version) + [""]
    lines += ["## (a) Member notice of the proposed rule change (4360(a))", "",
              f"Subject: {notice.subject}", "", "```text", notice.text, "```", "",
              "Required elements:", ""]
    lines += [f"- [{'x' if ok else ' '}] {name} ({cite})" for name, cite, ok in elements]
    lines += [""] + element_lines("rule-change-proposed", notice.text)
    if "CIV 4360(a)" not in (law or {}):
        lines += ["", "The notice states 4360(a) in its own words: the statute was not read from data/authorities "
                      "(jason export-authorities)."]
    lines += ["", "Delivery: by general notice under Civil Code 4045 (individual delivery to members who asked for it, "
              "4045(b), by each member's preferred delivery method under 4040 and 4041). Email only the members whose "
              "preferred method is email; mail the rest.", "",
              "## (b) Agenda item for the decision meeting", "", agenda_item(change, when), "",
              "## (c) Notice of the adopted rule change (4360(c)), template", "",
              f"Subject: {adopted.subject}", "", "```text", adopted.text, "```", ""]
    lines += element_lines("rule-change-adopted", adopted.text) + [""]
    lines += ["## The law, as exported to data/authorities", ""]
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


__all__ = ["ADOPTED_TEXT_HEADING", "DESCRIPTION_HEADING", "Notice", "Recital", "TEXT_HEADING", "Timeline",
           "adopted_lines", "adoption_notice", "agenda_item", "authority_status", "current_sections", "element_lines",
           "email_draft", "find_change", "first_decision_date", "member_notice", "open_shelf", "proposed_version",
           "recite_law", "recite_sections", "render_markdown", "required_elements", "save_draft", "text_lines",
           "timeline", "version_address", "versions_lines", "words_of", "write"]
