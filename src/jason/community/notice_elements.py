"""Whether a notice carries what the law requires of it: each required element, present or missing, and where.

A ``NoticeRequirement`` (``jason.community.notice_catalog``) lists its required elements as ``content``: jason's
reading of the section, one phrase an element. A ``Sign`` row says how an element shows in a notice's words: patterns
any one of which shows it (``any_of``), patterns every one of which must show (``all_of``), and, for an element the
notice may carry as an enclosure ("the insurance summary is enclosed"), the words that say so. Each row names the
statute subdivision the element is read from, so a report recites the law beside jason's reading of it.

``check(requirement, text)`` reads a rendered notice or a base template and returns one ``ElementFinding`` per element:

- ``PRESENT``: the words are in the notice, at the line given;
- ``TOKEN``: a template token stands for it (``{HEARING_DATE}``) and supplies it when the notice is filled;
- ``ENCLOSED``: the notice says the element is enclosed; the enclosure is checked on its own;
- ``MISSING``: no sign of it. A conditional element missing is reported with its condition;
- ``UNCHECKED``: an element words cannot settle ("anything else the law or the documents require"): a person reads it;
- ``NOT_REQUIRED``: a conditional element the event's facts rule out, with the fact that decided it.

**A conditional element.** An element only some notices need carries ``applies``, a condition over the event's facts
(``jason.community.notice_conditions``: how the meeting is held, whether the rule change is an emergency one, whether
an election rule allows electronic secret ballots, whether the documents require a quorum for an election of
directors, whether the election approves an amendment), and ``when``, the same condition in the catalog's words. ``check``
takes the facts the caller has. With none, the condition is undetermined and the finding names the missing fact
(``needs``); the words are still checked, and a missing element is reported with ``when``, as before the condition
was data. With facts, an element that does not apply is ``NOT_REQUIRED``, and one that applies and is missing is a gap
like any other.

The signs are a check of words, not of law: a notice that passes still goes to a person, and a sign that matches may
match the wrong sentence. The ``where`` of each finding is there so the person can look. Pure: no disk, no profile.

``law_statements(text)`` lists each sentence of a template that states the law in its own words, with the statute it
cites and the reference token that would recite or cite it instead (``{CITE:CIV#5855(c)}``; see
``STATUTE_TOKEN_NOTE``).
"""

from __future__ import annotations

import html as html_lib
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable

from jason.community.applicability import (ALWAYS, Answer, Condition, Facet, Fact, Facts, FactValue, Source, Verdict,
                                           evaluate)
from jason.community.notice_conditions import (AMENDMENT_ELECTION, DIRECTOR_QUORUM_STATEMENT, ELECTRONIC_VOTING_USED,
                                               EMERGENCY_RULE_CHANGE, ENTIRELY_BY_TELECONFERENCE)
from jason.community.notices import NoticeRequirement


class Status(Enum):
    PRESENT = "present"
    TOKEN = "supplied by a token when filled"
    ENCLOSED = "said to be enclosed"
    MISSING = "missing"
    UNCHECKED = "not checkable by words: a person reads it"
    NOT_REQUIRED = "does not apply"


@dataclass(frozen=True)
class Sign:
    """How one required element shows in a notice. ``element`` is the catalog's ``content`` phrase, exactly. ``cite``
    is the subdivision the element is read from. ``applies`` is the condition for an element only some notices need,
    over the event's facts, and ``when`` says it in the catalog's words ("a meeting held entirely by
    teleconference"); an element every notice needs has neither. ``checkable`` False: words cannot settle it."""

    element: str
    cite: str
    any_of: tuple[str, ...] = ()
    all_of: tuple[str, ...] = ()
    enclosed: tuple[str, ...] = ()
    applies: Condition = ALWAYS
    when: str = ""
    checkable: bool = True

    def __post_init__(self) -> None:
        if (self.applies is ALWAYS) != (not self.when):
            raise ValueError(f"{self.element!r}: a conditional element has both its condition and its words")


@dataclass(frozen=True)
class ElementFinding:
    requirement: str
    element: str
    cite: str
    status: Status
    where: str = ""               # "line 14, under 'Your rights': ..."
    applies: str = ""             # a conditional element's condition, in the catalog's words (``Sign.when``)
    verdict: Verdict | None = None  # that condition asked of the caller's facts; None for an element every notice needs

    @property
    def ok(self) -> bool:
        return self.status in (Status.PRESENT, Status.TOKEN, Status.ENCLOSED)

    @property
    def required(self) -> bool | None:
        """Whether this notice needs the element: True, False (its condition does not hold), or None when the facts
        on hand do not say. None is never read as False."""
        if self.verdict is None or self.verdict.answer is Answer.APPLIES:
            return True
        return False if self.verdict.answer is Answer.DOES_NOT_APPLY else None

    def needs(self) -> str:
        """For a conditional element the facts do not settle: the fact that is missing; empty otherwise."""
        return self.verdict.question() if self.verdict is not None else ""

    def condition(self) -> str:
        """How the condition reads beside a finding: "only for ..." while it is undetermined, "required here: ..."
        once the facts say it applies. Empty for an element every notice needs."""
        if not self.applies:
            return ""
        return f"required here: {self.applies}" if self.verdict is not None and self.verdict.applies \
            else f"only for {self.applies}"

    def row(self) -> dict[str, str]:
        out = {"requirement": self.requirement, "element": self.element, "cite": self.cite,
               "status": self.status.value, "where": self.where, "applies": self.applies}
        if self.verdict is not None:
            out["answer"] = self.verdict.answer.value
            out["needs"] = self.needs()
        return out


_TOK = r"\{[A-Z][A-Z0-9_]*\}"

# The conditions the conditional elements turn on are in ``jason.community.notice_conditions``, each beside the
# statute's words it is written from. Each ``when`` here is the catalog's words for its condition.

# The signs, by requirement key, in the order of the requirement's ``content``. A test holds the two in step: an
# element added to the catalog without a sign fails the build.
SIGNS: dict[str, tuple[Sign, ...]] = {
    "rule-change-proposed": (
        Sign("the text of the proposed rule change", "CIV 4360(a)",
             any_of=(r"text of the proposed (?:rule )?change",)),
        Sign("a description of its purpose and effect", "CIV 4360(a)",
             all_of=(r"\bpurpose\b", r"\beffect\b")),
    ),
    "rule-change-adopted": (
        Sign("the rule change", "CIV 4360(c)",
             any_of=(r"text of the (?:rule )?change as adopted", r"adopted text", r"text as adopted",
                     r"what changed")),
        Sign("for an emergency rule change: its text, purpose and effect, and the date it expires (it lasts at most "
             "120 days)", "CIV 4360(c), (d)", all_of=(r"\bpurpose\b", r"\bexpires?\b"),
             applies=EMERGENCY_RULE_CHANGE, when="an emergency rule change (4360(d))"),
    ),
    "pre-ballot-notice": (
        Sign("when and where ballots are returned by mail or by hand to the inspector", "CIV 5115(b)(1)",
             all_of=(r"ballots?\b[^.]{0,120}\b(?:returned|received|mailed|delivered|handed)",
                     r"inspectors? of elections?")),
        Sign("for electronic voting: when electronic ballots are due and preliminary instructions", "CIV 5115(b)(2)",
             any_of=(r"electronic (?:secret )?ballots?",), applies=ELECTRONIC_VOTING_USED,
             when="an association that allows voting by electronic secret ballot (5105)"),
        Sign("the date, time, and location of the meeting at which a quorum is determined and ballots are counted",
             "CIV 5115(b)(3)",
             all_of=(r"ballots? (?:will be|are|shall be) (?:counted|tabulated)|count(?:ing)? (?:of )?the ballots",
                     r"\bdate\b|\btime\b|\bp\.?m\.?\b|\ba\.?m\.?\b",
                     r"\bplace\b|\blocation\b|teleconference|video conference")),
        Sign("the list of all candidates' names that will appear on the ballot", "CIV 5115(b)(4)",
             any_of=(r"\bcandidates?\b",)),
        Sign("if the documents require a quorum: the statement about a reconvened meeting at a 20 percent quorum",
             "CIV 5115(b)(6)", all_of=(r"reconvened meeting", r"20 percent|twenty percent|20%"),
             applies=DIRECTOR_QUORUM_STATEMENT,
             when="governing documents that require a quorum for an election of directors, unless one lower than 20 "
                  "percent (5115(b)(6))"),
    ),
    "ballots": (
        Sign("the ballot, which does not identify the voter", "CIV 5115(c)", checkable=False),
        Sign("two preaddressed envelopes and return instructions", "CIV 5115(c)",
             all_of=(r"envelopes?", r"\breturn")),
        Sign("the election operating rules, or their website address with the phrase 5105(h)(4)(B)(i) prescribes",
             "CIV 5105(h)(4)(B)", any_of=(r"rules governing this election may be found here",
                                          r"election (?:operating )?rules (?:are|is) enclosed")),
        Sign("for an amendment: the text of the proposed amendment (5115(g))", "CIV 5115(g)",
             any_of=(r"text of the proposed amendment",), applies=AMENDMENT_ELECTION,
             when="an election to approve an amendment of the governing documents (5115(g))"),
    ),
    "discipline-hearing": (
        Sign("the date, time, and place of the meeting", "CIV 5855(b)",
             all_of=(r"(?:hearing|meeting)[ _]date|\bdate(?:\*\*)?:|date of the (?:hearing|meeting)",
                     r"(?:hearing|meeting)[ _]time|\btime(?:\*\*)?:|time of the (?:hearing|meeting)",
                     r"\bplace(?:\*\*)?:|\blocation\b|video conference|teleconference|place of the (?:hearing|meeting)")),
        Sign("the nature of the alleged violation, or of the common-area damage", "CIV 5855(b)",
             any_of=(r"alleged violation", r"damage to the common area")),
        Sign("that the member may attend and address the board", "CIV 5855(b)",
             any_of=(r"attend[^.]{0,60}address the board",)),
        Sign("that the member may ask for executive session", "CIV 5855(b), 4935(b)",
             any_of=(r"executive session",)),
        Sign("that a cure before the meeting (or a financial commitment to cure) ends it (5855(c))", "CIV 5855(c)",
             all_of=(r"\bcure\b", r"financial commitment")),
    ),
    "board-meeting": (
        Sign("the time and place of the meeting", "CIV 4920(a)",
             all_of=(r"\btime\b|\{MEETING_TIME\}|\bp\.?m\.?\b|\ba\.?m\.?\b",
                     r"\bplace\b|\blocation\b|\{MEETING_PLATFORM\}|\{ZOOM_LINK\}|teleconference|video conference")),
        Sign("the agenda (4920(d)); the board may act only on items on it (4930)", "CIV 4920(d), 4930(a)",
             any_of=(r"\{AGENDA_ITEMS\}", r"\bagenda\b")),
        Sign("for a teleconference meeting: technical instructions, a contact for help, and a reminder that a member "
             "may ask for individual delivery (4926(a)(1))", "CIV 4926(a)(1)",
             all_of=(r"technical|how to (?:join|participate)", r"\bhelp\b", r"individual delivery"),
             applies=ENTIRELY_BY_TELECONFERENCE, when="a meeting held entirely by teleconference (4926)"),
    ),
    "annual-policy-statement": (
        Sign("who receives official communications for the association (4035)", "CIV 5310(a)(1)",
             any_of=(r"designated recipient", r"official communications")),
        Sign("that a member may have notices sent to up to two addresses (4040)", "CIV 5310(a)(2)",
             any_of=(r"(?:up to )?two (?:different )?addresses", r"second address")),
        Sign("the designated posting location for general notices, if any (4045(a))", "CIV 5310(a)(3)",
             any_of=(r"\bposted\b", r"\bposting\b")),
        Sign("the option to receive general notices by individual delivery (4045(b))", "CIV 5310(a)(4)",
             all_of=(r"general notices", r"individual(?:ly| delivery)")),
        Sign("the right to copies of minutes and how (4950(b))", "CIV 5310(a)(5)", any_of=(r"\bminutes\b",)),
        Sign("the assessment and foreclosure notice (5730)", "CIV 5310(a)(6), 5730",
             any_of=(r"foreclosure",)),
        Sign("lien enforcement policies and practices", "CIV 5310(a)(7)",
             any_of=(r"lien (?:enforcement|rights)", r"enforcing lien")),
        Sign("the discipline policy and penalty schedule (5850)", "CIV 5310(a)(8), 5850",
             all_of=(r"discipline", r"penalt|\bfines?\b")),
        Sign("the dispute resolution summaries (5920, 5965)", "CIV 5310(a)(9), 5920, 5965",
             all_of=(r"internal dispute resolution|meet and confer", r"alternative dispute resolution")),
        Sign("the architectural approval requirements (4765)", "CIV 5310(a)(10), 4765",
             any_of=(r"architectural",)),
        Sign("the mailing address for overnight payments (5655)", "CIV 5310(a)(11), 5655",
             any_of=(r"overnight",)),
        Sign("electronic voting opt-in or opt-out procedures (5105(i)(1)(D)), if used", "CIV 5105(i)(1)(D)",
             any_of=(r"electronic (?:secret )?ballot", r"opt (?:in|out)", r"how you vote"),
             applies=ELECTRONIC_VOTING_USED, when="an association that uses electronic voting"),
        Sign("anything else the law or the documents require", "CIV 5310(a)(12)", checkable=False),
    ),
    "annual-budget-report": (
        Sign("the pro forma operating budget", "CIV 5300(b)(1)", any_of=(r"pro forma operating budget",)),
        Sign("the reserve summary (5565) and the reserve funding plan summary", "CIV 5300(b)(2), (3)",
             all_of=(r"reserve summary", r"funding plan")),
        Sign("deferred repairs, anticipated special assessments, and how reserves are funded", "CIV 5300(b)(4)-(7)",
             all_of=(r"defer", r"special assessment", r"reserves? (?:are|is) (?:funded|calculated)|how reserves")),
        Sign("outstanding loans", "CIV 5300(b)(8)", any_of=(r"\bloans?\b",)),
        Sign("the insurance summary with the 10-point bold statement (5300(b)(9))", "CIV 5300(b)(9)",
             all_of=(r"\binsurance\b", r"should not be considered a substitute for the complete policy terms"),
             enclosed=(r"summary of the association's [^.]{0,80}insurance is enclosed", r"insurance summary")),
        Sign("the FHA and VA status statements, each on a separate page", "CIV 5300(b)(10), (11)",
             all_of=(r"Federal Housing Administration|\bFHA\b", r"Veterans Affairs|\bVA\b")),
        Sign("the completed Charges For Documents Provided form (4528)", "CIV 5300(b)(12), 4528",
             any_of=(r"charges for documents provided",)),
        Sign("the Assessment and Reserve Funding Disclosure Summary (5570)", "CIV 5300(e), 5570",
             any_of=(r"assessment and reserve funding disclosure summary",)),
    ),
    "insurance-change": (
        Sign("which policy", "CIV 5810", any_of=(r"\{POLICY_LIST\}", r"\bpolic(?:y|ies)\b")),
        Sign("what happened: lapsed, canceled, not renewed, reduced coverage or limits, or a higher deductible",
             "CIV 5810", any_of=(r"\{CHANGES_LIST\}", r"\blaps", r"cancel", r"not renewed|nonrenew",
                                  r"reduc(?:ed|tion)", r"deductible (?:went|rose|increased)|higher deductible")),
    ),
    "pre-lien-notice": (
        Sign("the collection and lien enforcement procedures and how the amount is calculated", "CIV 5660(a)",
             all_of=(r"collection and lien enforcement", r"calculat")),
        Sign("the right to inspect the records (5205)", "CIV 5660(a), 5205",
             any_of=(r"inspect[^.]{0,60}records",)),
        Sign("the foreclosure warning in 14-point bold or capitals", "CIV 5660(a)",
             any_of=(r"may be sold without court action",)),
        Sign("an itemized statement of the charges", "CIV 5660(b)", any_of=(r"itemiz",)),
        Sign("that no charges are owed if the assessment was paid on time", "CIV 5660(c)",
             any_of=(r"paid on time", r"not (?:required|obligated) to pay")),
        Sign("the right to request a meeting with the board (5665)", "CIV 5660(d), 5665",
             any_of=(r"meeting with the board", r"request a meeting")),
        Sign("the right to dispute the debt through meet and confer (5900)", "CIV 5660(e)",
             any_of=(r"meet and confer", r"internal dispute resolution")),
        Sign("the right to request ADR before foreclosure (5925)", "CIV 5660(f)",
             any_of=(r"alternative dispute resolution",)),
    ),
}


def signs_for(requirement: NoticeRequirement) -> tuple[Sign, ...]:
    """The signs for a requirement's elements, in its order; an element no row covers is a ``Sign`` that cannot be
    checked, so it is never silently passed."""
    rows = {s.element: s for s in SIGNS.get(requirement.key, ())}
    return tuple(rows.get(e) or Sign(e, requirement.statute, checkable=False) for e in requirement.content)


@dataclass(frozen=True)
class Conditional:
    """One condition the notice catalog carries: a requirement's own (when the notice is required) or one of its
    elements' (when a notice needs the element). ``name`` says which, for a question that waits on it."""

    name: str
    applies: Condition
    authority: str = ""


def conditionals(rows: Iterable[NoticeRequirement] | None = None) -> tuple[Conditional, ...]:
    """Every condition of the catalog's rows (default: the general catalog) and of their elements, in the rows'
    order. A caller asks them of the association's standing facts to find what a person must settle
    (``jason.community.applicability_asks.standing_findings``)."""
    if rows is None:
        from jason.community.notice_catalog import REQUIREMENTS   # the catalog imports no element, so no cycle

        rows = REQUIREMENTS
    out: list[Conditional] = []
    for row in rows:
        if row.applies is not ALWAYS:
            out.append(Conditional(f"notice {row.key}", row.applies, row.statute))
        out += [Conditional(f"notice {row.key}: {sign.element}", sign.applies, sign.cite)
                for sign in signs_for(row) if sign.applies is not ALWAYS]
    return tuple(out)


# --- Reading a notice ------------------------------------------------------------------------------------------------

_TAG = re.compile(r"<[^>]+>")
_BLOCK = re.compile(r"</?(?:p|h[1-6]|li|ul|ol|br|div|tr|table|blockquote)\b[^>]*>", re.I)


def plain(text: str) -> str:
    """A notice as lines of plain words: HTML tags dropped (a block tag ends a line) and entities read; Markdown and
    plain text pass through. Tokens stay as written."""
    if re.search(r"<(?:p|h[1-6]|li|ul|div|br)\b", text or "", re.I):
        text = _BLOCK.sub("\n", text)
        text = html_lib.unescape(_TAG.sub("", text))
    return re.sub(r"[ \t]+", " ", (text or "").replace("’", "'").replace("‘", "'"))


def _heading(lines: list[str], at: int) -> str:
    for k in range(at, -1, -1):
        line = lines[k].strip()
        m = re.match(r"^#{1,6}\s+(.*)$", line)
        if m:
            return m.group(1).strip()
        bare = re.sub(_TOK, "", line).strip()
        if bare and len(line) <= 80 and line.upper() == line and re.search(r"[A-Z]{3}", bare):
            return line
    return ""


def _locate(text: str, start: int, end: int) -> str:
    lines = text.splitlines()
    line = text.count("\n", 0, start)
    head = _heading(lines, line)
    snippet = " ".join(text[max(0, start - 30):min(len(text), end + 50)].split())
    return f"line {line + 1}" + (f", under '{head[:60]}'" if head else "") + f": \"{snippet[:110]}\""


def _in_token(text: str, start: int, end: int) -> bool:
    for m in re.finditer(_TOK, text):
        if m.start() <= start and end <= m.end():
            return True
    return False


def _find(pattern: str, text: str) -> re.Match | None:
    return re.search(pattern, text, re.I)


def check_element(sign: Sign, text: str, requirement: str = "", facts: Facts | None = None) -> ElementFinding:
    """One element against a notice's plain words. ``facts`` are what the caller knows of the event; a conditional
    element they rule out is ``NOT_REQUIRED`` with the fact that decided it, and one they do not settle is checked as
    before, with the missing fact named (``ElementFinding.needs``)."""
    verdict = evaluate(sign.applies, facts or Facts()) if sign.applies is not ALWAYS else None
    base = dict(requirement=requirement, element=sign.element, cite=sign.cite, applies=sign.when, verdict=verdict)
    if verdict is not None and verdict.answer is Answer.DOES_NOT_APPLY:
        return ElementFinding(status=Status.NOT_REQUIRED,
                              where="decided by " + "; ".join(v.describe() for v in verdict.deciding), **base)
    if not sign.checkable:
        return ElementFinding(status=Status.UNCHECKED, **base)
    hits: list[re.Match] = []
    if sign.all_of:
        found = [_find(p, text) for p in sign.all_of]
        if all(found):
            hits = [m for m in found if m]
    if not hits and sign.any_of:
        m = next((x for x in (_find(p, text) for p in sign.any_of) if x), None)
        if m:
            hits = [m]
    if hits:
        first = min(hits, key=lambda m: m.start())
        tokens = all(_in_token(text, m.start(), m.end()) for m in hits)
        return ElementFinding(status=Status.TOKEN if tokens else Status.PRESENT,
                              where=_locate(text, first.start(), first.end()), **base)
    for p in sign.enclosed:
        m = _find(p, text)
        if m:
            return ElementFinding(status=Status.ENCLOSED, where=_locate(text, m.start(), m.end()), **base)
    return ElementFinding(status=Status.MISSING, **base)


_RECITED = re.compile(r"(?:provides|states|reads|requires|says)\s*:\s*(?:\"[^\"]*\"|“[^”]*”)", re.I)


def mask_recitals(text: str) -> str:
    """The text with each recital of the law ("Civil Code section 4360(a) provides: "...""), blanked to spaces: a
    notice that quotes what the statute requires does not by that carry it. Lengths and lines are kept."""
    return _RECITED.sub(lambda m: re.sub(r"[^\n]", " ", m.group(0)), text)


def check(requirement: NoticeRequirement, text: str, facts: Facts | None = None) -> list[ElementFinding]:
    """Each required element of ``requirement`` (its ``content``), present or missing in ``text``, with where. The
    statute's words the notice recites are not counted as the element. ``facts`` are the event's facts as the caller
    has them (``event_facts``, the profile's); without them a conditional element stays undetermined."""
    words = mask_recitals(plain(text))
    return [check_element(s, words, requirement.key, facts) for s in signs_for(requirement)]


EVENT_FACTS: tuple[Fact, ...] = tuple(f for f in Fact if f.facet is Facet.EVENT)


def event_facts(pairs: Iterable[str], *, where: str = "") -> Facts:
    """The event's facts from a person's words, each ``FACT=WORD`` (``meeting_format=entirely_by_teleconference``):
    the fact one of ``EVENT_FACTS`` and the word one of its closed set. Source ``ANSWER``: a person says them.
    ValueError names what may be said."""
    said = []
    for pair in pairs:
        name, _, word = pair.partition("=")
        fact = next((f for f in EVENT_FACTS if f.value == name.strip()), None)
        if fact is None:
            raise ValueError(f"{name.strip()!r} is not a fact about the event; one of: "
                             + ", ".join(f.value for f in EVENT_FACTS))
        try:
            value = fact.parse(word.strip())
        except ValueError:
            raise ValueError(f"{fact.value}: {word.strip()!r} is not one of: "
                             + ", ".join(str(m.value) for m in fact.spec.kind)) from None
        said.append(FactValue(fact, value, Source.ANSWER, where))
    return Facts(tuple(said))


def missing(findings: Iterable[ElementFinding]) -> list[ElementFinding]:
    return [f for f in findings if f.status is Status.MISSING]


# --- Where a template states the law in its own words ----------------------------------------------------------------

STATUTE_TOKEN_NOTE = (
    "A statute target ({CITE:CIV#5855(c)}, {QUOTE:CIV#4360(a)}) is not yet a reference token: "
    "jason.community.section_refs.TOKEN takes a lower-case document key only. The extension: let the key be an "
    "upper-case code (CIV, CORP, CCP, GOV, ...), resolve such a key through the exported statutes "
    "(jason.tasks.export_authorities.authority_text, then jason.community.cite.label_text for a subdivision), cite it "
    "as \"Civil Code Section 5855(c)\", record the session it was read from in the Embedded record, and refuse as-of "
    "(jason holds one edition of the law).")

_CODES = {"civil code": "CIV", "corporations code": "CORP", "code of civil procedure": "CCP",
          "government code": "GOV", "civ": "CIV", "corp": "CORP", "ccp": "CCP", "gov": "GOV"}
_CITE = re.compile(
    r"(?P<code>Civil Code|Corporations Code|Code of Civil Procedure|Government Code|CIV|CORP|CCP|GOV)?"
    r"\s*(?:sections?|§§?|secs?\.)?\s*"
    r"(?P<number>(?<![\d$,.])\d{3,4}(?:\.\d{1,2})?)(?P<labels>(?:\([a-z0-9]{1,4}\))*)"
    r"(?P<more>(?:\s*(?:,|and|or)\s*\([a-z0-9]{1,4}\)(?:\([a-z0-9]{1,4}\))*)*)", re.I)


@dataclass(frozen=True)
class LawStatement:
    """A sentence that states the law in a template's own words, and the statute it cites."""

    line: int
    sentence: str
    citations: tuple[str, ...]                 # "CIV 5850(c)", "CIV 5850(d)"
    tokens: tuple[str, ...] = field(default=())  # the reference each would become: "{CITE:CIV#5850(c)}"
    heading: bool = False                      # a heading or a bare citation that names the law, not a statement of it


def _citations(sentence: str) -> list[str]:
    out: list[str] = []
    for m in _CITE.finditer(sentence):
        before = sentence[max(0, m.start() - 40):m.start() + len(m.group(0))]
        named = m.group("code") or ""
        if not named and not re.search(r"(?:civil code|section|§)", before, re.I):
            continue
        number = m.group("number")
        if not (1000 <= float(number) < 10000):
            continue
        code = _CODES.get(named.lower(), "CIV")
        head = f"{code} {number}"
        labels = re.findall(r"\([a-z0-9]{1,4}\)", m.group("labels") or "")
        out.append(head + "".join(labels))
        # "5850(c), (d)": a further label is a sibling of the last one named.
        for extra in re.findall(r"\s*(?:,|and|or)\s*((?:\([a-z0-9]{1,4}\))+)", m.group("more") or ""):
            if labels:
                out.append(head + "".join(labels[:-1]) + extra)
    return list(dict.fromkeys(out))


def law_statements(text: str) -> list[LawStatement]:
    """Each sentence of a template that cites a statute: the template's own words for what the law says. A
    ``{QUOTE:}`` beside it would recite the statute's words; a ``{CITE:}`` names it. Tokens are proposals only."""
    words = plain(text)
    out: list[LawStatement] = []
    for k, line in enumerate(words.splitlines()):
        for sentence in re.split(r"(?<=[.;])\s+(?=[A-Z(])", line):
            cites = _citations(sentence)
            if not cites:
                continue
            tokens = tuple("{CITE:" + c.replace(" ", "#", 1) + "}" for c in cites)
            rest = re.findall(r"[A-Za-z]{2,}", _CITE.sub(" ", re.sub(r"\([^)]*\)", " ", sentence)))
            heading = line.lstrip().startswith("#") or len(rest) < 8
            out.append(LawStatement(k + 1, " ".join(sentence.split())[:300], tuple(cites), tokens, heading))
    return out


__all__ = ["Conditional", "conditionals", "ElementFinding", "LawStatement", "SIGNS", "STATUTE_TOKEN_NOTE", "Sign", "Status", "check",
           "check_element", "law_statements", "mask_recitals", "missing", "plain", "signs_for", "EVENT_FACTS",
           "event_facts", "EMERGENCY_RULE_CHANGE", "ENTIRELY_BY_TELECONFERENCE", "ELECTRONIC_VOTING_USED"]
