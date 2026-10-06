"""A form, defined once: its questions, and the answers it collects, whichever way they come back.

A ``FormTemplate`` row in the specification (``mystique/forms.py``) is the single definition. The renderers read it:

- the paper form (``form_render.paper_markdown`` for a Doc, ``form_render.paper_html`` for a local PDF);
- the fillable PDF laid over the printed form (``fillable.make_fillable``);
- the PayHOA build sheet (``form_render.payhoa_sheet``);
- a Google Form (``jason.google.forms``).

Each question has a stable ``field`` (its ``key``, or a slug of its title), so a PDF's fields, a response's columns, and
a check's messages name the question the same way however the form is reordered or retitled. A choice question's
options have keys too (``option_key``). ``prefill`` names a value a mailing fills in for each recipient (the unit's
address), and ``check`` reads answers against the definition: required questions, one choice where one is asked,
options the form offers, and the shape of a date, an email address, or a phone number. Answers are personal data;
nothing here stores them.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum, IntEnum
from typing import Any, Iterable


class QuestionKind(Enum):
    SHORT = "short"
    PARAGRAPH = "paragraph"
    CHOICE = "choice"           # one of the options
    CHECKBOX = "checkbox"       # any of the options
    DATE = "date"
    EMAIL = "email"
    PHONE = "phone"


TEXT_KINDS = (QuestionKind.SHORT, QuestionKind.PARAGRAPH, QuestionKind.DATE, QuestionKind.EMAIL, QuestionKind.PHONE)
CHOICE_KINDS = (QuestionKind.CHOICE, QuestionKind.CHECKBOX)


class ReadAs(Enum):
    """What a written answer holds, for reading it back from paper (``form_hints``): the rules that put an OCR misread
    right differ for an email, a phone number, an address, and a name."""
    TEXT = "text"
    NAME = "name"
    ADDRESS = "address"
    CONTACT = "contact"         # a name, an address, an email, or several
    EMAIL = "email"
    PHONE = "phone"


@dataclass(frozen=True)
class FormStyle:
    """How a form's answer spaces are drawn, per medium. The values come from the layout lab (``jason form-lab``,
    docs/form-design.md): spaces tall enough that handwriting stays in them, writing lines pale enough that what a scan
    keeps of them doesn't read as letters, and typed answers large enough to survive a print and a scan.

    **Print** (the mailed letter, filled by hand): each writing line gets ``write_height`` points (the forms standards'
    8 mm; at 14 points a third of the writing left its space in the lab, at 22 none landed on the print), and its line
    is ``line_gray`` (0 black, 1 white). **Screen** (the emailed fillable PDF, typed into): answers print at
    ``typed_size`` points, a multi-line answer too."""

    write_height: float = 22.0
    line_gray: float = 0.6
    typed_size: float = 10.0


class EmailCollection(Enum):
    """What a Google Form asks of its respondent's email (Forms API ``settings.emailCollectionType``)."""
    DO_NOT_COLLECT = "DO_NOT_COLLECT"
    VERIFIED = "VERIFIED"               # the respondent signs in to Google; the address is Google's, not typed
    RESPONDER_INPUT = "RESPONDER_INPUT"  # typed, unverified


class Assurance(IntEnum):
    """How sure the Association is that a returned form came from the owner it speaks for. Every channel has a level;
    a change from below ``MATCHED`` is confirmed to the address on file before it is relied on (``assess``)."""
    LEAD = 0           # nothing ties it to the owner: a lead to confirm
    CLAIMED = 1        # names the unit and an owner, from the Association's own mailing (a signed paper letter)
    TOKEN = 2          # quotes a reference only that owner's copy carried (an emailed copy's, or its personal link's)
    MATCHED = 3        # comes from, or names, the email the Association has for that owner
    SIGNED_IN = 4      # the owner signed in to send it (PayHOA)


@dataclass(frozen=True)
class GoogleFormChannel:
    """A form also offered as a Google Form: no sign-in, so each answer carries its ``Assurance``. ``reference`` is the
    question an owner's personal link fills with their copy's reference; ``email`` how the respondent's email is taken."""
    form_id: str = ""
    responder_uri: str = ""
    email: EmailCollection = EmailCollection.RESPONDER_INPUT
    reference: str = "Reference (filled in by your link; leave it as it is)"


class FormKey(Enum):
    IDR = "idr"
    RECORDS = "records"
    OWNER_INFO = "owner-info"
    # The forms of docs/form-templates/ (each key is its design page's file name), made as the library gains them.
    ADR_REQUEST = "adr-request"
    RESALE_DOCUMENTS = "resale-documents"
    MEMBERSHIP_LIST = "membership-list"
    PAYMENT_PLAN = "payment-plan"
    DISPUTED_CHARGE = "disputed-charge"
    ARCHITECTURAL_APPLICATION = "architectural-application"
    RECONSIDERATION_REQUEST = "reconsideration-request"
    EV_CHARGER = "ev-charger"
    SOLAR = "solar"
    PROTECTED_USE_APPLICATION = "protected-use-application"
    DELIVERY_CHANGE = "delivery-change"
    SECONDARY_ADDRESS = "secondary-address"
    INDIVIDUAL_DELIVERY_REQUEST = "individual-delivery-request"
    CANDIDATE_NOMINATION = "candidate-nomination"
    MEETING_COMMENT_REQUEST = "meeting-comment-request"
    ACCOMMODATION_REQUEST = "accommodation-request"


def slug(text: str, limit: int = 40) -> str:
    """A field name from text: lower case, words joined by hyphens, at most ``limit`` characters."""
    return re.sub(r"[^a-z0-9]+", "-", text.casefold()).strip("-")[:limit].strip("-")


def option_key(option: str) -> str:
    return slug(option)


@dataclass(frozen=True)
class FormQuestion:
    title: str
    kind: QuestionKind = QuestionKind.SHORT
    required: bool = True
    options: tuple[str, ...] = ()
    help: str = ""
    key: str = ""               # the stable field name; a slug of the title when empty
    lines: int = 0              # lines to write on, on paper; 0 is the kind's default
    prefill: str = ""           # the per-recipient value a mailing fills in ("UNIT_ADDRESS")
    authority: str = ""         # the law that asks for it ("Civil Code §4041(a)(1)"), printed with the question
    section: str = ""           # a heading printed before this question
    reads: ReadAs | None = None  # what a written answer holds, for reading it back; None follows the kind
    same_as: str = ""           # a box before the answer for the usual case ("Same as my unit address"): checked, it is
                                # the answer, and its field is ``{field}.{option_key(same_as)}``

    @property
    def reads_as(self) -> ReadAs:
        if self.reads is not None:
            return self.reads
        return {QuestionKind.EMAIL: ReadAs.EMAIL, QuestionKind.PHONE: ReadAs.PHONE}.get(self.kind, ReadAs.TEXT)

    @property
    def field(self) -> str:
        return self.key or slug(self.title.replace("(optional)", ""))

    @property
    def same_as_field(self) -> str:
        return f"{self.field}.{option_key(self.same_as)}" if self.same_as else ""

    @property
    def in_parts(self) -> bool:
        """An address written as its parts on paper: the street on one line, then city, state, and ZIP on the next."""
        return self.reads is ReadAs.ADDRESS and self.paper_lines == 2 and self.kind is QuestionKind.SHORT

    @property
    def paper_lines(self) -> int:
        return self.lines or (2 if self.kind is QuestionKind.PARAGRAPH else 1)

    def option_for(self, key: str) -> str:
        """The option a key names (a printed label can be cut short, so a key may be a prefix of the option's)."""
        for option in self.options:
            full = option_key(option)
            if key and (full == key or full.startswith(key) or key.startswith(full)):
                return option
        return key


@dataclass(frozen=True)
class FormTemplate:
    key: FormKey
    title: str
    authority: str
    description: str
    questions: tuple[FormQuestion, ...]
    signature: str = "Signature of owner"       # the paper form's signature line; empty for none
    dated: bool = True
    preamble: tuple[str, ...] = ()              # paragraphs before the questions ({TOKENS}; **bold**), every channel
    attestation: str = ""                       # what the owner certifies by answering: above the signature on paper,
                                                # a required box online
    code: str = ""                              # two letters naming the form in a marker on its copies (``form_refs``)
    style: FormStyle = FormStyle()              # its answer spaces on paper and on screen

    def question(self, name: str) -> FormQuestion:
        """A question by its field, its title, or its number ("3")."""
        for n, q in enumerate(self.questions, 1):
            if name in (q.field, q.title, str(n)):
                return q
        raise KeyError(name)


# -- answers ----------------------------------------------------------------------------------------------------------

EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$")
DATE_FORMATS = ("%m/%d/%Y", "%m/%d/%y", "%Y-%m-%d", "%B %d, %Y", "%b %d, %Y")


def parse_date(text: str) -> date | None:
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(text.strip(), fmt).date()
        except ValueError:
            continue
    return None


@dataclass
class FormAnswers:
    """One response: each question's field to its answer (text, or the options chosen), where it came from (a PDF, a
    Google Form, PayHOA, or a person's typing from paper), and the signature line's text when the form has one."""

    form: FormKey
    answers: dict[str, Any] = field(default_factory=dict)
    source: str = ""
    signature: str = ""
    signed: str = ""
    submitted: str = ""                                          # when it was sent (ISO), when the source says
    contacts: list[dict[str, str]] = field(default_factory=list)  # people it names: role, name, email, phone
    membership_id: int | None = None      # who sent it, when the source signs them in (a PayHOA submission)
    unit_id: int | None = None            # the unit it is for, when the source says (a PayHOA submission)
    reference: str = ""                   # the copy it answers (``references``), when the copy printed one

    def by_title(self, form: FormTemplate) -> dict[str, Any]:
        return {q.title: self.answers[q.field] for q in form.questions if q.field in self.answers}


# -- how old an answer is ---------------------------------------------------------------------------------------------

class Freshness(Enum):
    CURRENT = "this year's answer"
    PRIOR = "last year's answer"
    STALE = "older than last year"


@dataclass(frozen=True)
class AnswerCycle:
    """A yearly solicitation (Civil Code 4041 asks for the answers each year): the fiscal ``year`` it is for and the day
    it ``opened``. An answer sent since then is this year's; one from the year before is last year's, a lead to confirm;
    anything older is stale."""

    year: int
    opened: date
    return_by: date | None = None          # the date the solicitation asks owners to answer by
    reports_mailed: date | None = None     # when the annual budget report and policy statement go out (5300, 5310)

    ENTRY_LEAD_DAYS = 30                   # 4041(b)(1): answers entered at least 30 days before those reports

    @property
    def entry_deadline(self) -> date | None:
        """The last day to enter the answers in the books (4041(b)(1))."""
        from datetime import timedelta

        return self.reports_mailed - timedelta(days=self.ENTRY_LEAD_DAYS) if self.reports_mailed else None

    def deadlines(self, today: date) -> list[tuple[str, date, int]]:
        """The cycle's dates with the days left: opened, return by, enter by, reports mailed."""
        rows = [("solicitation opened", self.opened), ("owners asked to answer by", self.return_by),
                ("answers entered in PayHOA by (4041(b)(1))", self.entry_deadline),
                ("annual reports mailed (5300, 5310)", self.reports_mailed)]
        return [(name, day, (day - today).days) for name, day in rows if day]

    def freshness(self, submitted: str) -> Freshness:
        day = (parse_date(submitted[:10]) if submitted else None) or date.min
        if day >= self.opened:
            return Freshness.CURRENT
        if day >= self.opened.replace(year=self.opened.year - 1):
            return Freshness.PRIOR
        return Freshness.STALE


@dataclass(frozen=True)
class EarlierElections:
    """When an answer from before this cycle counts as the owner's written election of a delivery method (4040(a)(1),
    4041(a)(1)): the form's email matches the email PayHOA has for that owner (it was the owner, at a working address),
    it was sent after the unit's latest deed, it is no older than ``max_age_days``, and the owner has no delivery
    election in PayHOA (nothing newer). Such an answer sets the delivery tags; the owner is still asked to confirm it
    this cycle, and is not marked as having answered until they do."""

    apply: bool = True
    max_age_days: int = 730
    require_email_match: bool = True


@dataclass(frozen=True)
class SuggestedChoices:
    """The association's suggested answers, pre-filled on an owner's emailed form only (never on the page of what is on
    file, and never recorded until the owner returns the form). An owner's own choice always stands; where they have
    none, an owner who reads the association's email gets "By email" checked, and, with ``ballots``, an electronic
    ballot, unless they chose paper (a paper ballot, or paper statements they asked for). Reading email means a working
    email on file, nothing bounced or unsubscribed, and within ``active_days`` a PayHOA sign-in or an opened
    association email (``opens_count``: opens alone are weaker, since some mail apps open every message)."""

    apply: bool = True
    active_days: int = 365
    opens_count: bool = True
    ballots: bool = True


def age(submitted: str, today: date) -> str:
    """How long ago an answer was sent, in words: "3 weeks", "7 months", "2 years"."""
    day = parse_date(submitted[:10]) if submitted else None
    if day is None:
        return "unknown age"
    days = max((today - day).days, 0)
    if days < 60:
        return f"{max(days // 7, 0)} weeks" if days >= 14 else f"{days} days"
    if days < 730:
        return f"{days // 30} months"
    return f"{days // 365} years"


# -- another form's answers, read into a definition -------------------------------------------------------------------

CONTACT = "contact."             # an ImportRule field that names a person: contact.name, contact.email, contact.phone


@dataclass(frozen=True)
class ImportRule:
    """One question of an outside form (a Google Form made by hand, say) read into a definition: its ``title`` (and
    ``section``, where the form repeats a title in several sections), the definition's ``field`` it fills, and how its
    options map to the definition's (outside option, definition option). A ``contact.*`` field records a person
    instead, with ``role``; every occurrence of a repeated section is one more person."""

    title: str
    field: str
    section: str = ""
    options: tuple[tuple[str, str], ...] = ()
    role: str = ""


@dataclass(frozen=True)
class FormImport:
    """How an outside form's responses read into one of the association's form definitions. ``source`` is the outside
    form's id; questions no rule names (file uploads, navigation choices) are not read."""

    key: str
    source: str
    form: FormKey
    title: str
    rules: tuple[ImportRule, ...]
    note: str = ""

    def rule(self, section: str, title: str) -> ImportRule | None:
        for r in self.rules:
            if r.title.casefold() == title.strip().casefold() and (not r.section or r.section.casefold() == section.casefold()):
                return r
        return None


def check(form: FormTemplate, answers: dict[str, Any]) -> list[str]:
    """What is wrong with ``answers`` (field to value) against the form: a required question left blank, more than one
    choice where one is asked, an option the form does not offer, and a date, email, or phone that does not read as
    one. An empty list is a complete, well-formed response; it is not a judgment that the answers are true."""
    problems: list[str] = []
    for q in form.questions:
        value = answers.get(q.field)
        values = value if isinstance(value, list) else ([value] if value not in (None, "") else [])
        if not values:
            if q.required:
                problems.append(f"{q.title}: required, left blank")
            continue
        if q.kind in CHOICE_KINDS:
            unknown = [v for v in values if v not in q.options]
            if unknown:
                problems.append(f"{q.title}: not an option on the form: {', '.join(map(str, unknown))}")
            if q.kind is QuestionKind.CHOICE and len(values) > 1:
                problems.append(f"{q.title}: one choice asked, {len(values)} given")
            continue
        text = str(values[0]).strip()
        if q.kind is QuestionKind.EMAIL and not EMAIL.match(text):
            problems.append(f"{q.title}: not an email address: {text}")
        elif q.kind is QuestionKind.DATE and parse_date(text) is None:
            problems.append(f"{q.title}: not a date: {text}")
        elif q.kind is QuestionKind.PHONE and len(re.sub(r"\D", "", text)) not in (10, 11):
            problems.append(f"{q.title}: not a phone number: {text}")
    return problems


def answer_rows(form: FormTemplate, responses: Iterable[FormAnswers]) -> tuple[list[str], list[list[str]]]:
    """A header and one row a response, in the form's question order, for a sheet or a CSV a person enters from:
    the source, each question (choices joined with "; "), the signature, and the problems ``check`` finds."""
    header = ["source", *(q.title for q in form.questions), "signature", "date signed", "problems"]
    rows = []
    for r in responses:
        cells = [r.source]
        for q in form.questions:
            value = r.answers.get(q.field, "")
            cells.append("; ".join(value) if isinstance(value, list) else str(value or ""))
        rows.append([*cells, r.signature, r.signed, "; ".join(check(form, r.answers))])
    return header, rows


__all__ = ["AnswerCycle", "CHOICE_KINDS", "EarlierElections", "SuggestedChoices", "CONTACT", "Freshness", "FormAnswers", "FormImport", "FormKey", "age", "FormQuestion", "FormTemplate", "ImportRule",
           "QuestionKind", "TEXT_KINDS", "answer_rows", "check", "option_key", "parse_date", "slug"]
