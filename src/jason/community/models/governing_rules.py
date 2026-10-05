"""The board's rules: operating rules, policies, and the election rules.

An operating rule is a regulation the board adopts that applies generally to the management and operation of the
development or the conduct of the association's affairs (CIV 4340(a)); it is valid only in writing, within the board's
authority, consistent with the law and the declaration, articles, and bylaws, adopted in good faith, and reasonable
(4350). A rule on one of the subjects 4355(a) lists (use of the common area or of a separate interest, member discipline
and fines, payment plans, dispute resolution, architectural review, elections) takes 28 days' general notice of the text
and its purpose before the board decides, a decision at a board meeting, and general notice within 15 days after
(4360(a)-(c)); members owning 5 percent may call a vote to reverse it (4365). A schedule of monetary penalties is
distributed with the annual policy statement (5850(a), 5310(a)(8)); a penalty may not exceed the schedule or $100 per
violation unless the violation may harm health or safety and the board makes that finding in an open meeting (5850(c),
(d)). The collection policy is part of the annual policy statement (5310(a)(6), (7); 5730).

Election rules are operating rules the association must adopt, and 5105(a) lists what they do: equal access to
association media and to common-area meeting space during a campaign, candidates' qualifications and the nomination
procedure, the voting power of each membership, proxies, and the voting period, how the inspector or inspectors are
selected, the inspector's power to appoint helpers, and keeping the candidate registration list and the voter list. The
rules also guarantee a ballot to every member and to a holder of a general power of attorney, have the inspector
deliver the ballot and the rules 30 days before the election, and may not be amended within 90 days of an election
(5105(h)). ``ElectionRulesRecord.elements`` records which of those the text addresses; a miss is a lead, since a rule
can say the same thing in other words.

Discipline takes a hearing: written notice at least 10 days before the meeting, with its date, time, and place, the
nature of the violation, and the member's right to attend and address the board, in executive session on request
(5855(a), (b)); the member may cure first (5855(c)); IDR is open after the meeting (5855(d)); and the written decision is
due within 14 days of the board's action (5855(f), 15 days before the 2025 amendment). A policy, a rule book, or the
bylaws that restate those steps are read into ``HearingTerms`` and held to the statute as it now reads.

A collection policy restates Article 2 of Chapter 8: an assessment is delinquent 15 days after it is due, interest runs
from 30 days after (5650(b)), payments go to the assessments first (5655(a)), the pre-lien notice comes at least 30 days
before a lien (5660), the board decides to record a lien by vote in an open meeting (5673), and a paid lien is released
within 21 days (5685(a)). ``CollectionTerms`` records what the policy says on each, and a term that departs from the
statute is a PROBLEM. A fee schedule is held to 5650(b) (late charge, interest), 5205(f) (copies of records at direct
and actual cost), 4530(b) (the resale documents at actual cost), and 5910(g) (no fee for IDR).

A policy's adoption is not in its own text here. When the library holds a compilation that prints the policy's effective
date (the Owner's Manual), or minutes or annual policy statements that carry it, the checks say so; those are leads
from other files, never the policy's own fields.

The texts cannot show that notice was given, that the board voted at a meeting, or that a signature exists when the
signature line is an image; those findings are CHECK.
"""

from __future__ import annotations

import functools
import re
from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from pathlib import Path
from typing import Any

from jason.community.document_models import DocumentModel, Finding, ModelContext, Severity, date_after, dates_in, register, squash
from jason.community.reviews import RECORDS
from jason.community.symbols import DocumentKind

from .governing_shared import READER, ExplainsMissing, cites_repealed, number_word, repealed_sections
from .legal_shared import DELINQUENT_AFTER_DAYS, INTEREST_AFTER_DAYS, INTEREST_CAP_PERCENT, LATE_CHARGE_PERCENT, PRE_LIEN_DAYS, RELEASE_DAYS

PENALTY_CAP_CENTS = 10_000  # CIV 5850(c)(2)
HEARING_NOTICE_DAYS = 10    # CIV 5855(a)
DECISION_NOTICE_DAYS = 14   # CIV 5855(f), as amended by Stats. 2025, Ch. 22 (15 days before)
RULE_NOTICE_DAYS = 28       # CIV 4360(a)


class RuleSubject(Enum):
    """The subjects of CIV 4355(a) that bring a rule change under the notice and reversal procedure of 4360 and 4365."""

    COMMON_AREA_USE = "common-area-use"                  # (a)(1)
    SEPARATE_INTEREST_USE = "separate-interest-use"      # (a)(2)
    MEMBER_DISCIPLINE = "member-discipline"              # (a)(3)
    PAYMENT_PLANS = "payment-plans"                      # (a)(4)
    DISPUTE_RESOLUTION = "dispute-resolution"            # (a)(5)
    PHYSICAL_CHANGE_REVIEW = "physical-change-review"    # (a)(6)
    ELECTIONS = "elections"                              # (a)(7)


_SUBJECT_PATTERNS: tuple[tuple[RuleSubject, str], ...] = (
    (RuleSubject.COMMON_AREA_USE, r"common\s+area[s]?\b[^.]{0,80}\b(?:use|park|permit|guest)|guest\s+parking|parking\s+permit"),
    (RuleSubject.SEPARATE_INTEREST_USE, r"exterior\s+appearance|antenna|satellite\s+dish|household\s+pets|barbe(?:que|cue)|sound\s+transmission"),
    (RuleSubject.MEMBER_DISCIPLINE, r"fine\s+schedule|monetary\s+penalt|disciplinary\s+action|notice\s+of\s+(?:board\s+)?hearing"),
    (RuleSubject.PAYMENT_PLANS, r"payment\s+plans?"),
    (RuleSubject.DISPUTE_RESOLUTION, r"internal\s+dispute\s+resolution|meet\s+and\s+confer|alternative\s+dispute\s+resolution"),
    (RuleSubject.PHYSICAL_CHANGE_REVIEW, r"architectural\s+(?:control|application|review|committee)|non-approved\s+alterations"),
    (RuleSubject.ELECTIONS, r"inspectors?\s+of\s+elections?|secret\s+ballot|candidate\s+registration"),
)


class PolicySubject(Enum):
    COLLECTION = "collection"
    ENFORCEMENT = "enforcement"
    ETHICS = "ethics"
    FINE_SCHEDULE = "fine-schedule"
    LICENSE_PLATE_READERS = "license-plate-readers"
    RECORDS = "records"
    RESERVES = "reserves"
    OTHER = "other"


_POLICY_SUBJECTS: tuple[tuple[PolicySubject, str], ...] = (
    (PolicySubject.COLLECTION, r"(?:ASSESSMENT\s+)?COLLECTION\s+POLICY|delinquent\s+assessment"),
    (PolicySubject.ETHICS, r"ETHICS\s+POLICY|conflict\s+of\s+interest"),
    (PolicySubject.LICENSE_PLATE_READERS, r"\bALPR\b|license\s+plate\s+(?:recognition|reader)"),
    (PolicySubject.ENFORCEMENT, r"ENFORCEMENT\s+POLICY|due\s+process"),
    (PolicySubject.FINE_SCHEDULE, r"FINE\s+SCHEDULE"),
    (PolicySubject.RECORDS, r"RECORDS?\s+(?:INSPECTION|RETENTION)\s+POLICY"),
    (PolicySubject.RESERVES, r"RESERVE\s+(?:FUND\s+)?POLICY|investment\s+policy"),
)


@dataclass(frozen=True)
class FineRow:
    """One line of a fine or fee schedule. ``penalty`` is a monetary penalty for a violation (CIV 5850); a fee (a permit,
    a copy, a returned check) is not."""

    label: str
    value: str
    amount_cents: int | None = None      # the first dollar amount in the line
    max_cents: int | None = None         # the largest dollar amount in the line ("up to $300")
    per_day: bool = False
    penalty: bool = False


@dataclass(frozen=True)
class Adoption:
    adopted: date | None = None
    effective: date | None = None
    effective_text: str = ""              # "the date of adoption", when that is all it says
    adoption_blank: bool = False          # "adopted ______", "came into effect on the ____ day of ____"
    signature_blank: bool = False         # a signature line with nothing on it ("____ Secretary")


@dataclass(frozen=True)
class RuleSection:
    code: str                             # "B-12"
    title: str                            # "PARKING"


class ElectionElement(Enum):
    """What CIV 5105 says the election rules do, by subdivision."""

    MEDIA_ACCESS = "5105(a)(1)"
    MEETING_SPACE = "5105(a)(2)"
    CANDIDATE_QUALIFICATIONS = "5105(a)(3) qualifications"
    NOMINATION_PROCEDURE = "5105(a)(3) nominations"
    VOTING_POWER = "5105(a)(4) voting power"
    PROXIES = "5105(a)(4) proxies"
    VOTING_PERIOD = "5105(a)(4) voting period"
    INSPECTOR_SELECTION = "5105(a)(5)"
    INSPECTOR_HELPERS = "5105(a)(6)"
    CANDIDATE_LIST = "5105(a)(7) candidate list"
    VOTER_LIST = "5105(a)(7) voter list"
    BALLOT_NOT_DENIED = "5105(h)(1)"
    POWER_OF_ATTORNEY = "5105(h)(2), (3)"
    BALLOT_AND_RULES_DELIVERY = "5105(h)(4)"
    NO_LATE_AMENDMENT = "5105(h)(4)(B)(iii)"


_ELEMENT_PATTERNS: dict[ElectionElement, str] = {
    ElectionElement.MEDIA_ACCESS: r"(?:association\s+media|newsletter|website)[^.]{0,300}equal\s+access|equal\s+access[^.]{0,200}media",
    ElectionElement.MEETING_SPACE: r"common\s+area\s+meeting\s+space|meeting\s+space[^.]{0,120}no\s+cost",
    ElectionElement.CANDIDATE_QUALIFICATIONS: r"qualifications?\s+(?:of|for)\s+candidates|disqualify\s+(?:a\s+)?nominee",
    ElectionElement.NOMINATION_PROCEDURE: r"nominations?\b[^.]{0,200}(?:procedure|deadline)|(?:procedure|deadline)[^.]{0,120}nominat",
    ElectionElement.VOTING_POWER: r"voting\s+power",
    ElectionElement.PROXIES: r"\bprox(?:y|ies)\b",
    ElectionElement.VOTING_PERIOD: r"\bpolls?\s+(?:will\s+|shall\s+)?(?:open|close)|voting\s+period|polling\s+period|"
                                   r"deadline\s+for\s+(?:voting|the\s+return\s+of\s+ballots)",
    ElectionElement.INSPECTOR_SELECTION: r"(?:appoint|elect|select)\w*\s+(?:one\s+\(1\)\s+or\s+three\s+\(3\)\s+)?inspectors?\s+of\s+elections?|"
                                         r"inspectors?\s+of\s+elections?[^.]{0,80}(?:appointed|elected|selected)\s+by",
    ElectionElement.INSPECTOR_HELPERS: r"inspector[^.]{0,80}may\s+appoint[^.]{0,40}(?:additional\s+)?persons",
    ElectionElement.CANDIDATE_LIST: r"candidate\s+registration\s+list",
    ElectionElement.VOTER_LIST: r"voter\s+list",
    ElectionElement.BALLOT_NOT_DENIED: r"(?:shall\s+not\s+be|no\s+member\s+shall\s+be)\s+denied\s+a\s+ballot|denied\s+a\s+ballot\s+for\s+any\s+reason",
    ElectionElement.POWER_OF_ATTORNEY: r"general\s+power\s+of\s+attorney",
    ElectionElement.BALLOT_AND_RULES_DELIVERY: r"rules\s+governing\s+this\s+election\s+may\s+be\s+found\s+here|"
                                               r"(?:thirty\s+\(30\)|30)\s+days\s+before\s+(?:an|the)\s+election[^.]{0,200}(?:rules|ballot)",
    ElectionElement.NO_LATE_AMENDMENT: r"(?:not|never)\s+be\s+amended\s+less\s+than\s+(?:ninety\s+\(90\)|90)\s+days",
}


@dataclass(frozen=True)
class HearingTerms:
    """The discipline procedure a text restates, as it states it (CIV 5855)."""

    notice_days: int | None = None         # notice of the hearing at least this many days before it
    decision_days: int | None = None       # the written decision within this many days after the hearing or action
    notice_contents: bool = False          # date, time, and place, and the right to attend and address the board
    executive_session: bool = False        # the member may ask for executive session
    cure_before_hearing: bool = False      # the member may cure before the meeting (5855(c), since 2026)
    idr_after_hearing: bool = False        # IDR is offered when the board and the member disagree (5855(d))


@dataclass(frozen=True)
class CollectionTerms:
    """What a collection policy says on the points Article 2 of Chapter 8 fixes (CIV 5650-5685)."""

    delinquent_days: int | None = None     # delinquent this many days after the due date
    interest_starts_days: int | None = None  # interest runs from this many days after the due date
    pre_lien_days: int | None = None       # days the pre-lien notice gives before a lien is recorded
    payments_to_assessments_first: bool | None = None
    lien_decision_open_meeting: bool = False
    release_days: int | None = None        # a paid lien released within this many days
    foreclosure_decision_executive: bool = False
    payment_plan_meeting: bool = False     # an owner may ask to meet the board about a payment plan (5665)


@dataclass
class OperatingRulesRecord:
    title: str = ""
    adoption: Adoption = field(default_factory=Adoption)
    effective: date | None = None
    authority: str = ""                    # the declaration section that lets the board make rules ("Section 2.5")
    rules: tuple[RuleSection, ...] = ()
    subjects: tuple[RuleSubject, ...] = ()
    fines: tuple[FineRow, ...] = ()
    notice_described: bool = False         # the text itself describes the 28-day notice to members
    reversal_described: bool = False       # and the members' right to reverse a rule change
    includes: tuple[str, ...] = ()         # other documents the compilation carries (the collection policy, the 5730 notice)
    included_effective: tuple[tuple[str, date], ...] = ()  # (included document, the effective date printed beside it)
    hearing: HearingTerms | None = None
    repealed_sections: tuple[str, ...] = ()


@dataclass
class PolicyRecord:
    title: str = ""
    subject: PolicySubject = PolicySubject.OTHER
    adoption: Adoption = field(default_factory=Adoption)
    adopted: date | None = None
    effective: date | None = None
    supersedes_prior: bool = False
    subjects: tuple[RuleSubject, ...] = ()
    fines: tuple[FineRow, ...] = ()
    declaration_sections: tuple[str, ...] = ()  # the CC&R sections it cites ("6.12")
    hearing: HearingTerms | None = None          # an enforcement policy's hearing procedure
    collection: CollectionTerms | None = None    # a collection policy's terms
    repealed_sections: tuple[str, ...] = ()


@dataclass
class ElectionRulesRecord:
    title: str = ""
    adoption: Adoption = field(default_factory=Adoption)
    adopted: date | None = None
    certificate: bool = False              # a secretary's certificate of adoption
    certificate_year: int | None = None    # the year the certificate prints beside its blanks ("____, 2022")
    elements: tuple[ElectionElement, ...] = ()
    missing_elements: tuple[ElectionElement, ...] = ()
    electronic_voting: bool = False        # CIV 5105(i)
    acclamation: bool = False              # CIV 5103
    cumulative_voting: bool = False
    write_ins_allowed: bool | None = None
    floor_nominations_allowed: bool | None = None
    disqualifies_delinquent: bool = False  # CIV 5105(c)(1)
    directors_must_be_current: bool = False
    excludes_fines: bool = False           # CIV 5105(d)
    idr_before_disqualifying: bool = False  # CIV 5105(e)
    one_year_membership: bool = False      # CIV 5105(c)(3)
    retention: str = ""                    # how long the election materials are kept


# Shared readers.

def adoption(text: str) -> Adoption:
    flat = squash(text)
    effective = date_after(r"EFFECTIVE\s*:", text, window=40) or date_after(r"\beffective\s+(?:on|as\s+of)\s+", flat, window=30)
    return Adoption(
        adopted=READER.read_adopted(flat),
        effective=effective,
        effective_text=READER.read_effective(flat),
        adoption_blank=bool(re.search(r"\badopted\s*_{3,}|came\s+into\s+effect\s+on\s+the\s*_{2,}|effective\s*:?\s*_{3,}", flat, re.I))
        or READER.read_unsigned(text),
        signature_blank=bool(re.search(r"_{10,}\s*(?:Secretary|President|Board\s+of\s+Directors|Mystique)", flat)),
    )


def subjects_of(text: str) -> tuple[RuleSubject, ...]:
    flat = squash(text)
    return tuple(s for s, pattern in _SUBJECT_PATTERNS if re.search(pattern, flat, re.I))


_FINE_START = re.compile(r"Fine\s+Schedule\s*\n", re.I)
_FINE_END = re.compile(r"\n\s*(?:b\)\s*Due\s+Process|Due\s+Process\s+Requirements|\d+\.\s+[A-Z][a-z]+ [a-z])", re.I)
_VALUE_START = re.compile(r"\$\s?\d|\bWarning\b|\bNo\s+Cost\b|\d+(?:\.\d+)?\s?%|\bAvailable\b|\bfree\b", re.I)
_PENALTY_LABEL = re.compile(r"violation|fine\b|alteration|littering|registration|continuing", re.I)


def fine_schedule(text: str) -> tuple[FineRow, ...]:
    """The rows under a "Fine Schedule" heading, label and value, with a value on the label's line or the next one."""
    start = _FINE_START.search(text)
    if not start:
        return ()
    block = text[start.end(): start.end() + 4000]
    end = _FINE_END.search(block)
    block = block[: end.start()] if end else block
    lines = [ln.strip() for ln in block.splitlines() if ln.strip()]
    rows: list[FineRow] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if re.match(r"^(?:To\s+insure|following|MYSTIQUE|ENFORCEMENT)", line, re.I) or len(line) > 120:
            i += 1
            continue
        value_at = _VALUE_START.search(line)
        if value_at is None and i + 1 < len(lines) and _VALUE_START.match(lines[i + 1]):
            line, value_at = f"{line} {lines[i + 1]}", _VALUE_START.search(f"{line} {lines[i + 1]}")
            i += 1
        i += 1
        if value_at is None or value_at.start() == 0:
            continue
        label, value = line[: value_at.start()].strip(" :-"), line[value_at.start():].strip()
        amounts = [int(a.replace(",", "")) * 100 + int(c or 0) for a, c in re.findall(r"\$\s?(\d[\d,]*)(?:\.(\d\d))?", value)]
        rows.append(FineRow(label, value, amounts[0] if amounts else None, max(amounts) if amounts else None,
                            bool(re.search(r"per\s+day", value, re.I)), bool(_PENALTY_LABEL.search(label)) and "fee" not in label.lower()))
    return tuple(rows)


def fine_findings(fines: tuple[FineRow, ...]) -> list[Finding]:
    found: list[Finding] = []
    penalties = [f for f in fines if f.penalty]
    if not penalties:
        return found
    found.append(Finding("penalty-schedule-annual", f"a schedule of {len(penalties)} monetary penalties: distribute it with the annual "
                         "policy statement, and provide the current one to a member on request", Severity.INFO, "CIV 5850(a), (f); 5310(a)(8)"))
    for f in penalties:
        if f.max_cents is None or f.max_cents <= PENALTY_CAP_CENTS or f.per_day:
            continue
        if re.search(r"safety|health", f.label, re.I):
            found.append(Finding("penalty-over-cap-safety", f"{f.label!r} allows {f.value!r}, above $100; the board must first make a written "
                                 "finding of the health or safety impact in an open meeting", Severity.INFO, "CIV 5850(d)"))
        else:
            found.append(Finding("penalty-over-cap", f"{f.label!r} allows {f.value!r}, above the $100 per violation the statute permits "
                                 "outside health and safety violations", Severity.CHECK, "CIV 5850(c)"))
    return found


def notice_finding(subjects: tuple[RuleSubject, ...]) -> list[Finding]:
    if not subjects:
        return []
    names = ", ".join(s.value for s in subjects)
    return [Finding("rule-change-procedure", f"covers {names}: adopting or changing it takes 28 days' general notice of the text and its "
                    "purpose, a decision at a board meeting, and general notice within 15 days after; the text cannot show that",
                    Severity.CHECK, "CIV 4355(a), 4360(a)-(c)")]


_NUM = r"([\w-]+(?:\s*\(\d{1,3}\))?)"
_HEARING_NOTICE = re.compile(rf"(?:at\s+least|not\s+less\s+than|no\s+(?:less|fewer)\s+than)\s+{_NUM}\s+(?:calendar\s+)?days\s+"
                             r"(?:before|prior\s+to)\s+(?:the\s*|any\s+)?(?:Board\s+meeting|hearing|meeting)", re.I)
_DECISION_NOTICE = re.compile(rf"(?:within|not\s+more\s+than|no\s+later\s+than)\s+{_NUM}\s+(?:calendar\s+)?days\s+(?:after|following)\s+"
                              r"(?:the\s*)?(?:hearing|action|meeting)", re.I)
_HEARING_START = re.compile(r"Due\s+Process|Notice\s+of\s+(?:Board\s+)?Hearing|Sanctions;\s+Hearings|\bHearings?\.", re.I)


def _near(flat: str, m: re.Match, pattern: str, reach: int = 250) -> bool:
    return bool(re.search(pattern, flat[max(0, m.start() - reach): m.end() + reach], re.I))


def hearing_terms(text: str) -> HearingTerms | None:
    """The discipline procedure the text restates, or None when it restates none. The procedure's own words are read in
    its section (from the first due-process or hearing heading to 1,500 characters past the last deadline), so a rule
    book that mentions IDR for assessments elsewhere does not credit its hearings with it."""
    flat = squash(text)
    notice = next((m for m in _HEARING_NOTICE.finditer(flat) if _near(flat, m, r"hearing|disciplin")), None)
    decision = next((m for m in _DECISION_NOTICE.finditer(flat) if _near(flat, m, r"decision|disciplin", 200)), None)
    start = _HEARING_START.search(flat)
    if notice is None and decision is None and start is None:
        return None
    anchors = [m.start() for m in (notice, decision, start) if m is not None]
    ends = [m.end() for m in (notice, decision, start) if m is not None]
    section = flat[max(0, min(anchors) - 1500): max(ends) + 1500]
    return HearingTerms(
        notice_days=number_word(notice.group(1)) if notice else None,
        decision_days=number_word(decision.group(1)) if decision else None,
        notice_contents=bool(re.search(r"(?:time,?\s+date,?\s+and\s+place|date,?\s+time,?\s+and\s+place)", section, re.I)
                             and re.search(r"right\s+to\s+attend", section, re.I)),
        executive_session=bool(re.search(r"executive\s+session[^.]{0,120}(?:request|hearing)|(?:request|hearing)[^.]{0,120}executive\s+session",
                                         flat, re.I)),
        cure_before_hearing=_said(section, r"opportunity\s+to\s+cure|cures?\s+the\s+violation\s+(?:before|prior\s+to)"),
        idr_after_hearing=_said(section, r"internal\s+dispute\s+resolution|meet\s+and\s+confer|\bIDR\b"),
    )


def _said(section: str, pattern: str) -> bool:
    """The pattern in the hearing section, within 300 characters of a hearing or discipline."""
    return any(_near(section, m, r"hearing|disciplin", 300) for m in re.finditer(pattern, section, re.I))


def hearing_findings(h: HearingTerms | None) -> list[Finding]:
    if h is None:
        return []
    found: list[Finding] = []
    if h.notice_days is not None and h.notice_days < HEARING_NOTICE_DAYS:
        found.append(Finding("hearing-notice-short", f"the text gives {h.notice_days} days' notice of a disciplinary hearing; the member is "
                             f"owed at least {HEARING_NOTICE_DAYS}", Severity.PROBLEM, "CIV 5855(a)"))
    if h.decision_days is not None and h.decision_days > DECISION_NOTICE_DAYS:
        found.append(Finding("decision-notice-days", f"the text gives the member written notice of the decision within {h.decision_days} days; "
                             f"since the 2025 amendment the statute allows {DECISION_NOTICE_DAYS}", Severity.PROBLEM, "CIV 5855(f)"))
    if not h.cure_before_hearing:
        found.append(Finding("no-cure-before-hearing", "the text does not say the member may cure the violation before the hearing, or that "
                             "the board may not then impose discipline; the statute now says so regardless", Severity.CHECK, "CIV 5855(c)"))
    if not h.idr_after_hearing:
        found.append(Finding("no-idr-after-hearing", "the text does not offer internal dispute resolution when the board and the member do "
                             "not agree after the hearing", Severity.CHECK, "CIV 5855(d)"))
    if not h.executive_session:
        found.append(Finding("no-executive-session-on-request", "the text does not say the hearing is held in executive session if the "
                             "member asks; the statute provides it regardless", Severity.INFO, "CIV 5855(b)"))
    return found


def _days(pattern: str, flat: str) -> int | None:
    hit = re.search(pattern, flat, re.I)
    return number_word(hit.group(1)) if hit else None


def collection_terms(text: str) -> CollectionTerms:
    flat = squash(text)
    applied = re.search(r"Payments?\s+(?:shall|will)\s+be\s+applied\s+first\s+to\s+([^,.;]{3,60})", flat, re.I)
    first_to = applied.group(1).lower() if applied else ""
    lien = re.search(r"[^.]{0,200}\blien\s+shall\s+be\s+recorded[^.]{0,200}|[^.]{0,200}decision\s+to\s+record\s+a\s+lien[^.]{0,200}", flat, re.I)
    return CollectionTerms(
        delinquent_days=_days(rf"delinquent\s+if\s+not\s+(?:received|paid)[^.]{{0,80}}?\b{_NUM}\s+days\s+after", flat),
        interest_starts_days=_days(rf"Beginning\s+{_NUM}\s+days\s+after\s+the\s+assessment\s+becomes\s+due[^.]{{0,160}}\binterest", flat)
        or _days(rf"interest[^.]{{0,100}}(?:commenc|begin)\w*\s+{_NUM}\s+days\s+after", flat),
        pre_lien_days=_days(rf"paid\s+within\s+{_NUM}\s+days\s+after\s+the\s+date\s+of\s+(?:such|the)\s+notice", flat)
        or _days(rf"(?:at\s+least|not\s+less\s+than)\s+{_NUM}\s+days\s+(?:before|prior\s+to)\s+recording\s+a\s+lien", flat),
        payments_to_assessments_first=None if not applied else bool(re.search(r"principal|assessment", first_to))
        and not re.search(r"late|interest|fee|cost", first_to),
        lien_decision_open_meeting=bool(lien and re.search(r"open\s+(?:Board\s+)?meeting", lien.group(0), re.I)),
        release_days=_days(rf"Release\s+of\s+Lien\s+within\s+{_NUM}\s+(?:calendar\s+)?days", flat)
        or _days(rf"release[^.]{{0,80}}within\s+{_NUM}\s+(?:calendar\s+)?days", flat),
        foreclosure_decision_executive=bool(re.search(r"foreclos\w*[^.]{0,120}executive\s+session", flat, re.I)),
        payment_plan_meeting=bool(re.search(r"request\s+to\s+meet\s+with\s+the\s+Board\s+to\s+discuss\s+a\s+payment\s+plan", flat, re.I)),
    )


def collection_findings(c: CollectionTerms | None) -> list[Finding]:
    if c is None:
        return []
    found: list[Finding] = []
    if c.delinquent_days is not None and c.delinquent_days < DELINQUENT_AFTER_DAYS:
        found.append(Finding("delinquent-too-soon", f"an assessment is delinquent {c.delinquent_days} days after it is due; the statute "
                             f"allows {DELINQUENT_AFTER_DAYS} or the declaration's longer period", Severity.PROBLEM, "CIV 5650(b)"))
    if c.interest_starts_days is not None and c.interest_starts_days < INTEREST_AFTER_DAYS:
        found.append(Finding("interest-starts-early", f"interest runs from {c.interest_starts_days} days after the assessment is due; the "
                             f"statute lets it commence {INTEREST_AFTER_DAYS} days after", Severity.PROBLEM, "CIV 5650(b)(3)"))
    if c.pre_lien_days is not None and c.pre_lien_days < PRE_LIEN_DAYS:
        found.append(Finding("pre-lien-notice-short", f"the pre-lien notice gives {c.pre_lien_days} days; it must come at least "
                             f"{PRE_LIEN_DAYS} days before a lien is recorded", Severity.PROBLEM, "CIV 5660"))
    if c.payments_to_assessments_first is False:
        found.append(Finding("payments-not-to-assessments-first", "payments go first to something other than the assessments owed",
                             Severity.PROBLEM, "CIV 5655(a)"))
    if c.release_days is not None and c.release_days > RELEASE_DAYS:
        found.append(Finding("lien-release-late", f"a paid lien is released within {c.release_days} days; the statute allows {RELEASE_DAYS}",
                             Severity.PROBLEM, "CIV 5685(a)"))
    if not c.lien_decision_open_meeting:
        found.append(Finding("lien-decision-not-stated", "the text does not say the board decides to record a lien by a vote in an open "
                             "meeting, recorded in the minutes", Severity.CHECK, "CIV 5673"))
    return found


_PERCENT = re.compile(r"(\d{1,2}(?:\.\d+)?)\s?%")


def fee_findings(fines: tuple[FineRow, ...]) -> list[Finding]:
    """A fee schedule's lines the statute limits: the late charge and interest (5650(b)), copies of records (5205(f)), the
    resale documents (4530(b)), and IDR (5910(g))."""
    found: list[Finding] = []
    for f in fines:
        pct = _PERCENT.search(f.value)
        if re.search(r"late\s+(?:fee|charge)", f.label, re.I) and pct and float(pct.group(1)) > LATE_CHARGE_PERCENT:
            found.append(Finding("late-charge-over-cap", f"{f.label!r} is {f.value!r}; a late charge may not exceed {LATE_CHARGE_PERCENT} "
                                 "percent of the delinquent assessment or $10, whichever is greater", Severity.PROBLEM, "CIV 5650(b)(2)"))
        elif re.search(r"\binterest\b", f.label, re.I) and pct and float(pct.group(1)) > INTEREST_CAP_PERCENT:
            found.append(Finding("interest-over-cap", f"{f.label!r} is {f.value!r}; interest may not exceed {INTEREST_CAP_PERCENT} percent a year",
                                 Severity.PROBLEM, "CIV 5650(b)(3)"))
        elif re.search(r"cop(?:y|ies)\s+of\s+records|5205", f.label, re.I) and f.amount_cents:
            found.append(Finding("records-copy-fee", f"{f.label!r} is {f.value!r}: a flat charge; the association may bill only the direct "
                                 "and actual cost of copying and mailing, told to the member and agreed before copying", Severity.CHECK,
                                 "CIV 5205(f)"))
        elif re.search(r"transfer|demand|resale|4525", f.label, re.I) and f.amount_cents:
            found.append(Finding("resale-document-fee", f"{f.label!r} is {f.value!r}; the resale documents may be charged only at the "
                                 "association's actual cost, estimated first on the 4528 form, stated separately, and with no extra "
                                 "charge for electronic delivery", Severity.CHECK, "CIV 4530(b)"))
        elif re.search(r"dispute\s+resolution|\bIDR\b|meet\s+and\s+confer", f.label, re.I) and f.amount_cents:
            found.append(Finding("idr-fee", f"{f.label!r} is {f.value!r}; a member may not be charged to take part in IDR", Severity.PROBLEM,
                                 "CIV 5910(g)"))
    return found


# The library, for leads from other files (disk only; each index and text read once per data directory).

@functools.lru_cache(maxsize=4)
def _library(data_dir: str) -> tuple[tuple[str, str, str], ...]:
    try:
        from jason.tasks.library import distinct, load
        return tuple((str(r["id"]), str(r.get("name") or ""), str(r.get("kind") or "")) for r in distinct(load(Path(data_dir))))
    except Exception:  # no index on disk: the leads stay silent
        return ()


@functools.lru_cache(maxsize=512)
def _library_text(data_dir: str, doc_id: str) -> str:
    try:
        from jason.tasks.library import text_for
        return text_for(Path(data_dir), doc_id)
    except Exception:
        return ""


def _files(context: ModelContext, *kinds: DocumentKind) -> list[tuple[str, str]]:
    """(name, text) of the library's files of ``kinds``, other than the file being read."""
    if context.data_dir is None:
        return []
    values = {k.value for k in kinds}
    return [(name, _library_text(str(context.data_dir), doc_id)) for doc_id, name, kind in _library(str(context.data_dir))
            if kind in values and name != context.name]


def _key(title: str) -> str:
    """The words that name a policy wherever it is copied ("ETHICS POLICY FOR DIRECTORS" -> ETHICS POLICY), as a pattern."""
    words = re.sub(r"\s+FOR\s+.*$", "", title.upper()).split()[-3:]
    return r"\s*".join(re.escape(w) for w in words) if words else ""


def compiled_effective(context: ModelContext, title: str) -> list[tuple[str, date]]:
    """The compilations (the Owner's Manual) that print this document's title with an effective date beside it."""
    key = _key(title)
    out = []
    for name, text in _files(context, DocumentKind.OPERATING_RULES) if key else ():
        hit = re.search(rf"{key}\s*EFFECTIVE\s*:?\s*([A-Za-z]+\s+\d{{1,2}},?\s+\d{{4}})", squash(text), re.I)
        found = dates_in(hit.group(1)) if hit else []
        if found:
            out.append((name, found[0]))
    return out


def adopting_minutes(context: ModelContext, title: str) -> tuple[int, list[str]]:
    """(minutes on file, the minutes that mention adopting or approving this document)."""
    key = _key(title)
    files = _files(context, DocumentKind.MINUTES)
    hits = [name for name, text in files if key and re.search(rf"(?:adopt|approv)\w*[^.]{{0,160}}{key}|{key}[^.]{{0,160}}(?:adopt|approv)",
                                                              squash(text), re.I)]
    return len(files), hits


def statements_carrying(context: ModelContext, title: str) -> list[str]:
    """The annual policy statements (annual disclosures) on file that carry this document."""
    key = _key(title)
    return [name for name, text in _files(context, DocumentKind.ANNUAL_DISCLOSURE) if key and re.search(key, squash(text), re.I)]


def _day(d: date) -> str:
    return f"{d:%B} {d.day}, {d.year}"


def leads_clause(total: int, hits: list[str]) -> str:
    """What the library's minutes say about adopting a document (``adopting_minutes``), as a clause to append to a
    finding; empty with no minutes on file."""
    if not total:
        return ""
    if hits:
        return f"; minutes that mention adopting it: {', '.join(hits[:3])}"
    return f"; none of the library's {total} minutes mentions adopting it"


def adoption_leads(context: ModelContext, title: str) -> str:
    """What the library's minutes say about adopting this document, as a clause to append to a finding (empty without a
    library)."""
    return leads_clause(*adopting_minutes(context, title))


def _title(text: str, pattern: str) -> str:
    for line in text.splitlines()[:40]:
        clean = line.strip()
        if clean.startswith(("#", "-")) or not clean:
            continue
        if re.search(pattern, clean, re.I):
            return " ".join(clean.split())[:120]
    return ""


# Operating rules.

def minutes_adopting(r, records) -> dict[str, Any] | None:
    """From the library's minutes: how many are on file, and the names of those that mention adopting or approving the
    document. None for a document that prints its adoption date."""
    if r.adoption.adopted is not None:
        return None
    total, hits = adopting_minutes(records, r.title)
    return {"minutes": total, "mention": hits}


@RECORDS.check("rules-adoption", OperatingRulesRecord, fields=("title", "adoption", "effective"), facts=minutes_adopting, dated=False)
def rules_adoption(r, _as_of, minutes: dict[str, Any] | None) -> list[Finding]:
    """Rules that print no adoption date, with what the minutes on file say about adopting them."""
    if minutes is None:
        return []
    printed = f" (it prints only an effective date, {_day(r.effective)})" if r.effective else ""
    return [Finding("no-adoption-date", f"no adoption date is printed in the text{printed}; the minutes of the meeting that "
                    f"adopted the rules are the record{leads_clause(minutes['minutes'], minutes['mention'])}", Severity.CHECK, "CIV 4360(b)")]


rules_repealed = cites_repealed("rules-repealed-sections", OperatingRulesRecord)


class OperatingRulesModel(DocumentModel):
    kind = DocumentKind.OPERATING_RULES
    name = "operating-rules"
    required = ("title", "effective", "rules")
    lens_checks = (rules_adoption, rules_repealed)

    def parse(self, text: str, context: ModelContext) -> OperatingRulesRecord | None:
        codes = re.findall(r"^\s*([A-Z]-\d{1,2})\.\s+([A-Z][A-Z/&,' -]{2,60}?)\s*$", text, re.M)
        if len({c for c, _ in codes}) < 3 or not re.search(r"\bRULES\b", text[:5000], re.I):
            return None
        flat = squash(text)
        r = OperatingRulesRecord()
        head = " ".join(" ".join(ln for ln in text[:1500].splitlines() if not ln.startswith(("#", "- "))).split())
        hit = re.search(r"([A-Z][A-Z' ]{3,60}(?:OWNER.S\s+MANUAL\s*&?\s*RULES|RULES\s+AND\s+REGULATIONS|RULES))", head)
        r.title = hit.group(1).strip() if hit else "Rules"
        r.adoption = adoption(text)
        r.effective = r.adoption.effective
        hit = re.search(r"(?:provided|authoriz\w*)\s+by\s*the\s*Declaration[^.]{0,120}?\bSection\s+(\d+(?:\.\d+)+)", flat, re.I)
        r.authority = f"Section {hit.group(1)}" if hit else ""
        r.rules = tuple(dict((c, RuleSection(c, t.strip())) for c, t in codes).values())
        r.subjects = subjects_of(text)
        r.fines = fine_schedule(text)
        r.notice_described = bool(re.search(r"28[\s-]*day\s+notice|twenty-eight\s+\(28\)\s+days", flat, re.I))
        r.reversal_described = bool(re.search(r"petition\s+to\s+reverse|reverse\s+a\s+rule\s+change", flat, re.I))
        includes, dated = [], []
        hit = re.search(r"ASSESSMENT\s+COLLECTION\s+POLICY\s+EFFECTIVE\s*:?\s*([A-Za-z]+\s+\d{1,2},?\s+\d{4})?", flat, re.I)
        if hit:
            includes.append("assessment collection policy")
            when = dates_in(hit.group(1) or "")
            if when:
                dated.append(("assessment collection policy", when[0]))
        if re.search(r"Civil\s+Code\s+section\s+5730\s+requires", flat, re.I):
            includes.append("annual notice of assessments and foreclosure (CIV 5730)")
        r.includes, r.included_effective = tuple(includes), tuple(dated)
        r.hearing = hearing_terms(text)
        r.repealed_sections = repealed_sections(flat)
        return r

    def check(self, r: OperatingRulesRecord, context: ModelContext) -> list[Finding]:
        found = notice_finding(r.subjects)
        found += fine_findings(r.fines)
        found += fee_findings(r.fines)
        found += hearing_findings(r.hearing)
        found.append(rules_adoption)   # the records lens's place: no adoption date printed, and what the minutes on file say
        if not r.authority:
            found.append(Finding("no-authority-cited", "the rules do not cite the declaration or bylaw section that lets the board make "
                                 "them", Severity.INFO, "CIV 4350(b)"))
        found.append(rules_repealed)   # the records lens's place: the former sections cited, and where the law history puts each
        return found


# Policies.

def adoption_note(adoption_: Adoption, *, certificate: bool = False, year: int | None = None) -> str:
    """What the text prints where an adoption date would be, as a finding's message."""
    if certificate and adoption_.adoption_blank:
        why = "the secretary's certificate of adoption is blank" + (f" (\"____ day of ____, {year}\")" if year else "")
    elif adoption_.adoption_blank:
        why = "the adoption line is blank (\"adopted ____\")"
    elif adoption_.effective_text.lower() == "the date of adoption":
        why = "it takes effect \"on the date of adoption\" and names no date"
    else:
        why = "it carries no adoption line, date, or certificate"
    return f"no adoption date is printed in the text: {why}"


def compilations_dating(r, records) -> list[list[Any]] | None:
    """From the library's compilations (the operating rules on file): each one that prints this policy's title with an
    effective date beside it, as its name and that date. None for a policy that prints a date of its own."""
    if r.adopted is not None or r.effective is not None:
        return None
    return [[name, when] for name, when in compiled_effective(records, r.title)]


@RECORDS.check("policy-compiled-date", PolicyRecord, fields=("title", "adopted", "effective"), facts=compilations_dating, dated=False)
def policy_compiled_date(r, _as_of, compilations: list[list[Any]] | None) -> list[Finding]:
    """A policy that prints no date, against the compilations on file that print one for it."""
    return [Finding("effective-date-in-compilation", f"{name} prints this policy as effective {_day(when)}; this copy "
                    "prints no date", Severity.INFO) for name, when in compilations or ()]


def statements_with_policy(r, records) -> list[str] | None:
    """From the library's annual policy statements (annual disclosures): the names of those that carry this policy. None
    for a policy that is neither the collection policy nor the discipline policy."""
    if r.subject not in (PolicySubject.COLLECTION, PolicySubject.ENFORCEMENT):
        return None
    return statements_carrying(records, r.title)


@RECORDS.check("policy-statements", PolicyRecord, fields=("title", "subject", "fines"), facts=statements_with_policy, dated=False)
def policy_statements(r, _as_of, statements: list[str] | None) -> list[Finding]:
    """The collection policy and the discipline policy against the annual policy statements on file: which carry it."""
    statements = statements or []
    if r.subject is PolicySubject.COLLECTION:
        where = f"; the annual policy statements on file carry it ({', '.join(statements[:3])})" if statements else ""
        return [Finding("annual-policy-statement", "the collection policy belongs in the annual policy statement with the "
                        f"statutory notice of assessments and foreclosure{where}", Severity.INFO, "CIV 5310(a)(6), (7); 5730")]
    if r.subject is PolicySubject.ENFORCEMENT and r.fines and statements:
        return [Finding("in-annual-policy-statement", f"the annual policy statements on file carry this policy "
                        f"({', '.join(statements[:3])})", Severity.INFO, "CIV 5310(a)(8)")]
    return []


policy_repealed = cites_repealed("policy-repealed-sections", PolicyRecord)


class PolicyModel(ExplainsMissing, DocumentModel):
    kinds = (DocumentKind.POLICY, DocumentKind.OPERATING_RULES)
    name = "board-policy"
    required = ("title", "adopted")
    lens_checks = (policy_compiled_date, policy_statements, policy_repealed)

    def missing_notes(self, r: PolicyRecord, context: ModelContext) -> dict[str, tuple[str, str]]:
        note = f"{adoption_note(r.adoption)}{adoption_leads(context, r.title)}"
        return {"adopted": (note, "CIV 4360(b)" if r.subjects else "")}

    def parse(self, text: str, context: ModelContext) -> PolicyRecord | None:
        title = _title(text, r"\bPOLICY\b|\bPOLICIES\b|FINE\s+SCHEDULE|RESOLUTION|RULES?\b|PROCEDURES?\b")
        if not title:
            return None
        flat = squash(text)
        r = PolicyRecord(title=title)
        head = " ".join(text[:2500].split())
        r.subject = next((s for s, p in _POLICY_SUBJECTS if re.search(p, head, re.I)), PolicySubject.OTHER)
        r.adoption = adoption(text)
        r.adopted, r.effective = r.adoption.adopted, r.adoption.effective
        r.supersedes_prior = bool(re.search(r"shall\s+supersede\s+any\s+(?:other|prior)", flat, re.I))
        # An ethics policy governs directors and committee members; its "disciplinary action" is theirs, not a member's,
        # and none of the 4355(a) subjects is in it.
        r.subjects = () if r.subject is PolicySubject.ETHICS else subjects_of(text)
        r.fines = fine_schedule(text)
        r.declaration_sections = tuple(dict.fromkeys(re.findall(r"CC&Rs\s*§\s*(\d+(?:\.\d+)*)", flat)))
        if r.subject in (PolicySubject.ENFORCEMENT, PolicySubject.FINE_SCHEDULE):
            r.hearing = hearing_terms(text)
        if r.subject is PolicySubject.COLLECTION:
            r.collection = collection_terms(text)
        r.repealed_sections = repealed_sections(flat)
        return r

    def check(self, r: PolicyRecord, context: ModelContext) -> list[Finding]:
        found: list[Finding] = []
        if r.adoption.adoption_blank:
            found.append(Finding("adoption-date-blank", "the adoption date is a blank line: an unadopted draft or an unsigned copy",
                                 Severity.CHECK))
        elif r.adopted is None and r.adoption.effective_text.lower() == "the date of adoption":
            found.append(Finding("effective-on-adoption-undated", "effective \"on the date of adoption\", but the text does not give that "
                                 "date; the minutes of the meeting that adopted it are the record", Severity.CHECK, "CIV 4360(b)"))
        found.append(policy_compiled_date)   # the records lens's place: a compilation on file that dates this policy
        found += notice_finding(r.subjects)
        found += fine_findings(r.fines)
        found += fee_findings(r.fines)
        found += hearing_findings(r.hearing)
        found += collection_findings(r.collection)
        found.append(policy_statements)   # the records lens's place: the annual policy statements on file that carry it
        if r.subject is PolicySubject.ENFORCEMENT and not r.fines:
            found.append(Finding("discipline-policy-statement", "the discipline policy belongs in the annual policy statement",
                                 Severity.INFO, "CIV 5310(a)(8)"))
        found.append(policy_repealed)   # the records lens's place: the former sections cited, and where the law history puts each
        return found


# Election rules.

class ElectionRulesModel(ExplainsMissing, DocumentModel):
    kinds = (DocumentKind.ELECTION_RULES, DocumentKind.OPERATING_RULES, DocumentKind.POLICY)
    name = "election-rules"
    required = ("title", "adopted")

    def missing_notes(self, r: ElectionRulesRecord, context: ModelContext) -> dict[str, tuple[str, str]]:
        note = adoption_note(r.adoption, certificate=r.certificate, year=r.certificate_year)
        return {"adopted": (f"{note}{adoption_leads(context, r.title)}", "CIV 5105(a), 4360(b)")}

    def parse(self, text: str, context: ModelContext) -> ElectionRulesRecord | None:
        title = _title(text, r"ELECTION\s+(?:RULES|PROCEDURES|POLICY)|VOTING\s+RULES")
        if not title:
            return None
        flat = squash(text)
        r = ElectionRulesRecord(title=title)
        r.adoption = adoption(text)
        cert = re.search(r"certify\s+that\s+these\s+Election\s+Rules\s+were\s+duly\s+adopted[^.]{0,200}", flat, re.I)
        r.certificate = bool(cert)
        if cert:
            dated = dates_in(cert.group(0))
            r.adopted = dated[0] if dated else None
            year = re.search(r"_{2,}\s*,?\s*((?:19|20)\d\d)\b", cert.group(0))
            r.certificate_year = int(year.group(1)) if year else None
        r.adopted = r.adopted or r.adoption.adopted
        r.elements = tuple(e for e, p in _ELEMENT_PATTERNS.items() if re.search(p, flat, re.I))
        r.missing_elements = tuple(e for e in ElectionElement if e not in r.elements)
        r.electronic_voting = bool(re.search(r"electronic\s+secret\s+ballot|electronic\s+voting\s+system", flat, re.I)) and \
            not re.search(r"including\s+electronic\s+voting\)", flat, re.I)
        r.acclamation = bool(re.search(r"by\s+acclamation", flat, re.I))
        r.cumulative_voting = bool(re.search(r"cumulative\s+voting\s+is\s+permitted", flat, re.I))
        if re.search(r"No\s+.?write-in.?\s+candidates\s+shall\s+be\s+permitted", flat, re.I):
            r.write_ins_allowed = False
        elif re.search(r"write-in\s+candidates\s+(?:are|shall\s+be|may\s+be)\s+permitted", flat, re.I):
            r.write_ins_allowed = True
        if re.search(r"Nominations\s+may\s+not\s+be\s+made\s+from\s+the\s+floor", flat, re.I):
            r.floor_nominations_allowed = False
        elif re.search(r"nominations?\s+(?:may\s+be\s+made\s+)?from\s+the\s+floor", flat, re.I):
            r.floor_nominations_allowed = True
        r.disqualifies_delinquent = bool(re.search(r"disqualify\s+(?:a\s+)?nominee.{0,900}?delinquent\s+in\s+the\s+payment", flat, re.I))
        r.directors_must_be_current = bool(re.search(r"serving\s+on\s+the\s+Board\s+shall\s+be\s+current|director[s]?\s+(?:shall|must)\s+"
                                                     r"(?:also\s+)?be\s+current", flat, re.I))
        r.excludes_fines = bool(re.search(r"delinquen\w+\s+relates\s+to\s+the\s+payment\s+of\s+fines|not\s+(?:be\s+)?disqualif\w+[^.]{0,80}fines",
                                          flat, re.I))
        r.idr_before_disqualifying = bool(re.search(r"internal\s+dispute\s+resolution", flat, re.I))
        r.one_year_membership = bool(re.search(r"member\s+of\s+the\s+Association\s+for\s+less\s+than\s+one\s+year", flat, re.I))
        hit = re.search(r"retain\s+the\s+association\s+election\s+materials\s+(for\s+[^.]{5,80})", flat, re.I)
        r.retention = hit.group(1).strip() if hit else ""
        return r

    def check(self, r: ElectionRulesRecord, context: ModelContext) -> list[Finding]:
        found: list[Finding] = []
        for element in r.missing_elements:
            found.append(Finding("election-rule-element-not-found", f"the text does not address {element.value} in the usual words",
                                 Severity.CHECK, f"CIV {element.value.split(' ')[0]}"))
        if r.adoption.adoption_blank or (r.certificate and r.adopted is None):
            found.append(Finding("adoption-certificate-blank", "the secretary's certificate of adoption is blank: the text does not show "
                                 "when, or that, the board adopted these rules", Severity.CHECK, "CIV 5105(a), 4360(b)"))
        found += notice_finding((RuleSubject.ELECTIONS,))
        if r.disqualifies_delinquent and not r.directors_must_be_current:
            found.append(Finding("directors-not-held-to-nominee-rule", "the rules disqualify a delinquent nominee but do not require a "
                                 "director to stay current", Severity.PROBLEM, "CIV 5105(c)(1), (f)"))
        if r.disqualifies_delinquent and not r.excludes_fines:
            found.append(Finding("fines-not-excluded", "the rules disqualify a delinquent nominee without excluding fines, late charges, "
                                 "and collection costs", Severity.CHECK, "CIV 5105(d)"))
        if r.disqualifies_delinquent and not r.idr_before_disqualifying:
            found.append(Finding("no-idr-before-disqualifying", "the rules do not offer internal dispute resolution before disqualifying a "
                                 "nominee", Severity.CHECK, "CIV 5105(e)"))
        if r.electronic_voting and r.floor_nominations_allowed:
            found.append(Finding("floor-nominations-with-electronic-ballot", "an electronic-ballot rule must prohibit nominations from the "
                                 "floor", Severity.PROBLEM, "CIV 5105(i)(1)(F)"))
        found.append(Finding("deliver-rules-with-ballot", "the inspector delivers the ballot and these rules (or the website line) at "
                             "least 30 days before each election; the rules may not change within 90 days of one", Severity.INFO,
                             "CIV 5105(h)(4)"))
        return found


register(ElectionRulesModel())
register(OperatingRulesModel())
register(PolicyModel())

__all__ = ["RuleSubject", "PolicySubject", "FineRow", "Adoption", "RuleSection", "ElectionElement", "HearingTerms", "CollectionTerms",
           "OperatingRulesRecord", "PolicyRecord", "ElectionRulesRecord", "OperatingRulesModel", "PolicyModel", "ElectionRulesModel",
           "adoption", "fine_schedule", "subjects_of", "hearing_terms", "hearing_findings", "collection_terms", "collection_findings",
           "fee_findings", "RULE_NOTICE_DAYS"]
