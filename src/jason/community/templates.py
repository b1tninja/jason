"""Letter templates: Google Docs on the association's letterhead with ``{VARIABLE}`` tokens where a letter's facts go.

A template is a Doc in the Templates folder, built from the Letterhead Doc so every letter keeps its logo, header,
footer, and fonts. A token is ``{`` + upper-case letters, digits, or ``_`` + ``}``: ``{OWNER_NAME}``, ``{HEARING_DATE}``.
Filling a letter copies the template into the folder the letter belongs in and replaces each token everywhere (body,
headers, footers). A token with no value stays in the copy, visible, for the person who edits it; an optional token
with no value is removed. A token in ``link_tokens`` becomes a link to its own value.

``DocumentTemplate`` is a specification row (``Community.document_templates()``): which kind of letter, the Drive id,
the tokens it carries, which are optional, the folder filled letters go in, and the authority the letter serves.
``BODIES`` is each template's body as blocks, kept here so the Docs can be rebuilt from the Letterhead
(``jason templates --build``). The wording is the statute's; the facts are the board's.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

TOKEN = re.compile(r"\{([A-Z][A-Z0-9_]*)\}")


class TemplateKind(Enum):
    LETTERHEAD = "letter on letterhead"
    HEARING_NOTICE = "notice of hearing"
    DECISION_NOTICE = "notice of decision"
    AGENDA = "board meeting agenda"

    @property
    def slug(self) -> str:
        return self.name.lower().replace("_", "-")

    @classmethod
    def from_slug(cls, text: str) -> TemplateKind:
        key = text.strip().lower().replace("_", "-")
        for kind in cls:
            if key in (kind.slug, kind.value):
                return kind
        raise ValueError(f"no template {text!r}; choose " + ", ".join(k.slug for k in cls))


class Block(Enum):
    """How a body line is styled."""

    TEXT = "NORMAL_TEXT"
    HEADING = "HEADING_3"
    BULLET = "BULLET"
    BOLD = "BOLD"
    TITLE = "TITLE"      # centered and larger: an agenda's meeting name under the letterhead
    BOX = "BOX"          # centered in a ruled box with the lines around it: the meeting's date and how to join
    NOTE = "NOTE"        # small grey text: a statement the law asks for, set apart from the business


@dataclass(frozen=True)
class DocumentTemplate:
    kind: TemplateKind
    title: str
    drive_id: str = ""                        # empty until the template is built
    folder_id: str = ""                       # where a filled letter goes; empty for the drafts folder of the caller's choosing
    optional: tuple[str, ...] = ()
    link_tokens: tuple[str, ...] = ()
    authority: str = ""

    @property
    def tokens(self) -> tuple[str, ...]:
        return tokens_in("\n".join(text for _, text in BODIES.get(self.kind, ())))


def body_markdown(kind: TemplateKind, values: dict[str, str], optional: tuple[str, ...] = ()) -> str:
    """A template's body as Markdown, its tokens filled; a token with no value is left as ``[token in words]`` for the
    person who finishes the draft, and an ``optional`` one is dropped. The same body the Doc is built from, so the
    notice reads the same everywhere."""

    def fill(text: str) -> str:
        return TOKEN.sub(lambda m: values.get(m.group(1)) or ('' if m.group(1) in optional
                                                             else f"[{m.group(1).lower().replace('_', ' ')}]"), text).rstrip()

    lines: list[str] = []
    for block, text in BODIES[kind]:
        text = fill(text)
        if block is Block.HEADING:
            lines += ["", f"## {text}", ""]
        elif block is Block.BULLET:
            lines.append(f"- {text}")
        elif block is Block.BOLD:
            lines.append(f"**{text}**")
        elif block is Block.TITLE:
            lines.append(f"# {text}")
        else:
            lines.append(text)
    out: list[str] = []
    for line in lines:                       # no run of blank lines
        if line or (out and out[-1]):
            out.append(line)
    return "\n".join(out).strip() + "\n"


def tokens_in(text: str) -> tuple[str, ...]:
    """The distinct tokens in ``text``, in order of first appearance."""
    seen: dict[str, None] = {}
    for name in TOKEN.findall(text):
        seen.setdefault(name, None)
    return tuple(seen)


def _lines(*rows: tuple[Block, str]) -> tuple[tuple[Block, str], ...]:
    return rows


T, H, B, BOLD, TITLE, BOX, NOTE = Block.TEXT, Block.HEADING, Block.BULLET, Block.BOLD, Block.TITLE, Block.BOX, Block.NOTE

_ADDRESSEE = (
    (T, "{DATE}"), (T, ""),
    (T, "{OWNER_NAME}"), (T, "{ADDRESS}"), (T, "{CITY_STATE_ZIP}"), (T, ""),
    (T, "Delivered by {DELIVERY_METHOD}"), (T, ""),
)
# The profile fills the signer, its name, and its citations (template_values.profile_values); a body names no association.
_CLOSING = ((T, ""), (T, "Sincerely,"), (T, ""), (T, ""), (T, "{SIGNER}"), (T, "{ASSOCIATION_NAME}"))

BODIES: dict[TemplateKind, tuple[tuple[Block, str], ...]] = {
    TemplateKind.LETTERHEAD: (
        (T, "{DATE}"), (T, ""),
        (T, "{RECIPIENT_NAME}"), (T, "{RECIPIENT_ADDRESS}"), (T, "{RECIPIENT_CITY_STATE_ZIP}"), (T, ""),
        (BOLD, "Re: {SUBJECT}"), (T, ""),
        (T, "Dear {RECIPIENT_NAME},"), (T, ""),
        (T, "{BODY}"),
        *_CLOSING,
    ),
    TemplateKind.HEARING_NOTICE: (
        *_ADDRESSEE,
        (BOLD, "Re: Notice of Hearing, {ADDRESS}"), (T, ""),
        (T, "Dear {OWNER_NAME},"), (T, ""),
        (T, "The Board of Directors of {ASSOCIATION_NAME} will hold a hearing to consider imposing discipline "
            "for the alleged violation described below. This notice is given under Civil Code Section 5855."),
        (H, "Date, time, and place"),
        (T, "**Date:** {HEARING_DATE}"),
        (T, "**Time:** {HEARING_TIME} {TIME_ZONE}"),
        (T, "**Place:** by {MEETING_PLATFORM} video conference"),
        (T, "**Join:** {ZOOM_LINK}"),
        (T, "**Meeting ID:** {ZOOM_MEETING_ID}    **Passcode:** {ZOOM_PASSCODE}"),
        (T, "**By telephone:** {ZOOM_DIAL_IN}"),
        (H, "The alleged violation"),
        (T, "{VIOLATION}"),
        (H, "Governing documents"),
        (T, "{GOVERNING_SECTIONS}"),
        (H, "Possible discipline"),
        (T, "{POSSIBLE_DISCIPLINE}"),
        (T, ""),
        (T, "A fine may not exceed the lesser of the amount in the association's schedule of monetary penalties in effect "
            "at the time of the violation or $100 per violation, unless the violation may result in an adverse health or "
            "safety impact and the Board makes a written finding of that impact at a meeting open to the members (Civil "
            "Code Section 5850(c), (d)). No late charge or interest is charged on a fine (Section 5850(e)). If the Board "
            "finds a violation that continues after the hearing, it may consider further fines for the continuing "
            "violation ({CITE_CONTINUING_FINES}); you will be notified before any further fine is imposed."),
        (H, "Your rights"),
        (B, "You have the right to attend the hearing and to address the Board."),
        (B, "You may present evidence, including a written statement, photographs, and witnesses, and you may question "
            "any witness who speaks against you ({CITE_HEARING_EVIDENCE}). If you cannot attend, you may send a written "
            "response before the hearing."),
        (B, "The Board will meet in executive session if you ask it to, and you may attend that session (Civil Code "
            "Section 4935(b)). To ask, reply to this notice before the hearing."),
        (B, "You may cure the violation before the hearing. The Board will not impose discipline if you cure it before "
            "the hearing or, if a cure would take longer than the time before the hearing, if you give a financial "
            "commitment to cure it (Civil Code Section 5855(c)). {CURE}"),
        (B, "If you need a reasonable accommodation for a disability, including for an assistance animal, please tell "
            "the Board before the hearing."),
        (B, "For good cause, you may ask in writing, before the hearing, to move it to another date."),
        (B, "If you do not attend, the Board will still consider the evidence and decide whether a violation occurred."),
        (B, "If you and the Board do not agree after the hearing, you may request internal dispute resolution, at no "
            "cost to you (Civil Code Sections 5855(d), 5910)."),
        (B, "The Board will deliver its decision to you in writing within 14 days after it acts (Civil Code Section "
            "5855(f))."),
        (H, "Questions"),
        (T, "{CONTACT}"),
        *_CLOSING,
    ),
    TemplateKind.DECISION_NOTICE: (
        *_ADDRESSEE,
        (BOLD, "Re: Notice of Board Decision, {ADDRESS}"), (T, ""),
        (T, "Dear {OWNER_NAME},"), (T, ""),
        (T, "On {HEARING_DATE}, the Board of Directors held a hearing on the alleged violation described below, of which "
            "you were notified on {NOTICE_DATE}. This is the Board's written decision, delivered within 14 days after "
            "the Board acted, as Civil Code Section 5855(f) requires."),
        (H, "The alleged violation"),
        (T, "{VIOLATION}"),
        (H, "Findings"),
        (T, "The Board considered the evidence presented, including anything you submitted, and finds:"),
        (T, ""),
        (T, "{FINDINGS}"),
        (H, "Decision"),
        (T, "{DECISION}"),
        (H, "Governing documents"),
        (T, "{GOVERNING_SECTIONS}"),
        (H, "Your rights"),
        (B, "If you disagree with this decision, you may request internal dispute resolution, at no cost to you, by "
            "writing to the Board (Civil Code Sections 5855(d), 5910)."),
        (B, "No late charge or interest will be charged on a fine (Civil Code Section 5850(e)). A fine is not an "
            "assessment and cannot become a lien on your unit (Civil Code Section 5725(b); {CITE_FINES_NOT_LIENS})."),
        (B, "{PAYMENT_OR_CURE}"),
        (H, "Questions"),
        (T, "{CONTACT}"),
        *_CLOSING,
    ),
    # The board's agenda on the letterhead. {AGENDA_ITEMS} is one paragraph that filling replaces with the numbered
    # business (jason.tasks.meeting_agenda.agenda_items); the rest is what an all-teleconference meeting's notice must
    # carry (CIV 4926(a)(1), (3)).
    TemplateKind.AGENDA: (
        (TITLE, "{MEETING_KIND}"),
        (T, ""),
        (BOX, "**{MEETING_DATE} at {MEETING_TIME}**"),
        (BOX, "by {MEETING_PLATFORM}: {ZOOM_LINK}"),
        (BOX, "Meeting ID {ZOOM_MEETING_ID} · by telephone {ZOOM_PHONE}"),
        (NOTE, "Technical help before and during the meeting: {TECH_CONTACT}. You may ask to receive meeting notices by "
               "individual delivery by writing to the board. Every vote of the directors at this meeting is taken by roll "
               "call (Civil Code Section 4926(a))."),
        (T, ""),
        (T, "{AGENDA_ITEMS}"),
    ),
}

# The header of the pages after the first (the letterhead's logo is on the first page only).
CONTINUATION: dict[TemplateKind, str] = {
    TemplateKind.LETTERHEAD: "Re: {SUBJECT} · {DATE}",
    TemplateKind.HEARING_NOTICE: "Notice of Hearing · {ADDRESS} · {DATE}",
    TemplateKind.DECISION_NOTICE: "Notice of Board Decision · {ADDRESS} · {DATE}",
    TemplateKind.AGENDA: "{MEETING_KIND} · {MEETING_DATE}",
}


__all__ = ["BODIES", "CONTINUATION", "Block", "DocumentTemplate", "TOKEN", "TemplateKind", "tokens_in"]
