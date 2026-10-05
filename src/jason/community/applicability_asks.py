"""Undetermined answers as intake questions, and a person's answers as facts.

``jason.community.life_safety.applicable`` leaves a row undetermined when a fact is missing or when two sources
disagree on one. Here each such fact becomes one question for the existing intake queue (``jason.community.intake``;
``data/intake/asks.json``), and each answer there becomes a fact with source ``ANSWER`` for the next evaluation. There
is no second question store.

**One question a fact, a subject.** ``questions(result)`` keys a question by its subject and the fact, so the same
missing fact for the same system is one question however many rows wait on it. The subject is the system
(``applies:system:<key>``), or the association (``applies:association``) for a fact about the development, its place,
or its standing rules. A profile that lists no systems gets one question: which systems it has. Each question names
the fact, the rows its answer would decide, and the kinds of record that would settle it (``SETTLED_BY``).

**The notice catalog's standing facts.** A notice, or one of its elements, may turn on a standing fact about the
association's own documents and practice: whether an election rule allows electronic secret ballots, whether the
documents require a quorum for an election of directors, whether the board keeps seating by acclamation available.
The profile states these (``Community.applicability_facts()``). Where it does not, ``standing_findings`` finds the
rows that wait on one and ``questions(result, also=...)`` asks it once under ``applies:association``. A fact of one
event (what one election decides) is never asked here: the caller that knows the event says it.

**An answer is a fact.** ``answered(asks)`` reads each answered question of this kind: the value in the fact's own
closed set (a choice's words, or its word in the JSON form), and after a semicolon the record that states it
("NFPA 13R; the 2006 permit"). It becomes a ``FactValue`` with source ``ANSWER`` and, as its ``where``, the question's
id, who answered, and when. An answer that cannot be read as the fact is listed with why and is not used; the row
stays undetermined. A person answers again through the same path.

**Three rules decided for now, each a default a person can overturn.**

- *Disagreement.* An answer that disagrees with a document or the profile does not win. The evaluation tests both, the
  row stays undetermined, and the question lists both. jason picks neither: a person corrects the specification, or
  answers again.
- *The record.* A fact in ``NEEDS_RECORD`` (a system's installation standard; the standing facts an election rule, a
  bylaw, or the board's decision settles) is read only with the record named: a standard is entered with the record
  that states it (``jason.community.life_safety``), from a person as from the profile.
- *A second person.* A fact in ``CONFIRMED`` waits for a second person's confirmation, the intake queue's own guard
  for a high-stakes answer. The set is empty: no fact waits unless a person adds it here.

Nothing is asked twice: a question keeps its id from run to run, and the queue keeps an answered question answered.
Filing is a person's command (``jason applies --file-questions``), never a side effect of reading.

Pure: no network, no store. ``jason.tasks.applicability_asks`` reads and files.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from enum import Enum
from typing import Any, Iterable

from jason.community.applicability import ALWAYS, Facet, Fact, Facts, FactValue, Source, evaluate
from jason.community.intake import Ask, AskKind, AskStatus, ask_id, high_stakes
from jason.community.life_safety import SUBJECT_FACTS, Finding, SystemApplicability, row_name

SCOPE = ("applies:",)                        # the subjects these questions use, for ``intake.merge``
ASSOCIATION = "applies:association"
SYSTEMS_KEY = "life_safety_systems"          # the question of which systems the association has: not a fact
_METHOD = "Community.life_safety_systems()"

# A fact on one of these facets is the association's, whichever system's row asked for it.
ASSOCIATION_FACETS: frozenset[Facet] = frozenset({Facet.PROPERTY, Facet.PLACE, Facet.EVENT})

# Facts whose answer is read only with the record that states it named after a semicolon: a system's standard, and
# the standing facts that an election rule, a bylaw, or the board's own decision settles.
NEEDS_RECORD: frozenset[Fact] = frozenset({Fact.INSTALLATION_STANDARD, Fact.ELECTRONIC_VOTING, Fact.ACCLAMATION,
                                           Fact.DIRECTOR_QUORUM})

# Facts whose answer a second person confirms before it is used. Empty by default.
CONFIRMED: frozenset[Fact] = frozenset()

# How a fact is asked for, where "what is <the fact>?" would not read well.
ASKS: dict[Fact, str] = {
    Fact.SYSTEM: "what kind of system is it?",
    Fact.INSTALLATION_STANDARD: "which standard was it installed under?",
    Fact.VENDOR_WORK: "which kinds of work does the vendor do on it (inspection, testing, maintenance, repair, "
                      "installation, design, monitoring)?",
    Fact.LICENSE_CLASS: "which license classes does the vendor hold?",
    Fact.COMMON_INTEREST: "what kind of common interest development is it?",
    Fact.HOME_IMPROVEMENT: "is the work a home improvement (Business and Professions Code 7151 and 7151.2)?",
    Fact.ELECTRONIC_VOTING: "does an election operating rule allow electronic secret ballots, and do members opt "
                            "out or opt in (Civil Code 5105(i))?",
    Fact.ACCLAMATION: "does the board keep seating by acclamation available for an election of directors (Civil Code "
                      "5103)? The statute leaves the choice to the association, whatever its documents say, so this "
                      "is the board's decision to record, not a reading of the documents.",
    Fact.DIRECTOR_QUORUM: "do the governing documents require a quorum for an election of directors, and is it lower "
                          "than 20 percent (Civil Code 5115(b)(6))?",
}

# The kinds of record that would settle each fact. Kinds only: which record an association holds is its own.
SETTLED_BY: dict[Fact, str] = {
    Fact.SYSTEM: "the approved plans, the permit, or a service vendor's report",
    Fact.INSTALLATION_STANDARD: "the approved plans, the building permit, or the installer's record (its material "
                                "and test certificate)",
    Fact.VENDOR_WORK: "the vendor's agreement or proposal (its scope of work)",
    Fact.LICENSE_CLASS: "the licensing board's record of the license",
    Fact.COMMON_INTEREST: "the declaration or the condominium plan",
    Fact.OCCUPANCY_CLASS: "the building permit or the certificate of occupancy",
    Fact.UNIT_COUNT: "the condominium plan or the declaration",
    Fact.STATE: "the recorded map or the declaration",
    Fact.COUNTY: "the recorded map or the declaration",
    Fact.CITY: "the recorded map or a permit",
    Fact.WATER_PURVEYOR: "a water bill",
    Fact.HOME_IMPROVEMENT: "counsel's written reading",
    Fact.ELECTRONIC_VOTING: "the election operating rules",
    Fact.ACCLAMATION: "the election operating rules, or the board's resolution in its minutes",
    Fact.DIRECTOR_QUORUM: "the bylaws' quorum section, or the election operating rules",
}
ANY_RECORD = "a record that states it"


def system_subject(key: str) -> str:
    return f"applies:system:{key}"


@dataclass(frozen=True)
class FactQuestion:
    """One question: a fact one subject is missing, or one its sources disagree on (``stated`` holds each value with
    its source). ``fact`` None is the question of which systems the association has."""

    subject: str                      # the intake subject
    fact: Fact | None
    system: str = ""                  # the system's key; empty for the association
    name: str = "the association"     # the subject in words
    waiting: tuple[str, ...] = ()     # the rows the answer would decide
    rules: tuple[str, ...] = ()       # those rows' conditions, in words
    stated: tuple[str, ...] = ()      # where sources disagree: each value with where it comes from
    known: tuple[str, ...] = ()       # what a partial set already names

    @property
    def key(self) -> str:
        return self.fact.value if self.fact else SYSTEMS_KEY

    @property
    def id(self) -> str:
        """Stable from run to run: the kind, the subject, and the fact."""
        return ask_id(AskKind.APPLICABILITY, self.subject, self.key)

    @property
    def disagreement(self) -> bool:
        return bool(self.stated)

    def settled_by(self) -> str:
        if self.fact is None:
            return "the approved plans, the permits, or the service vendors' reports"
        return SETTLED_BY.get(self.fact, ANY_RECORD)

    def values(self) -> tuple[str, ...]:
        """The fact's closed set in words, for a fact with one value from an enum; none otherwise."""
        if self.fact is None or self.fact.spec.many or not issubclass(self.fact.spec.kind, Enum):
            return ()
        return tuple(self.fact.format(member) for member in self.fact.spec.kind)

    def choices(self) -> tuple[str, ...]:
        """The values as the queue's numbered choices. A fact that is entered with its record has none: a choice's
        number would answer without the record, so its values are in the question's words instead."""
        return () if self.fact in NEEDS_RECORD else self.values()

    def text(self) -> str:
        if self.fact is None:
            return (f"Which life safety systems does the association have? The specification lists none ({_METHOD}). "
                    f"Name each system, what it serves, and the record that shows it.")
        name = self.name[:1].upper() + self.name[1:]
        if self.disagreement:
            return (f"{name}: the sources disagree on {self.fact.noun}: {'; '.join(self.stated)}. Which is right? "
                    f"jason picks neither: the rows stay undetermined until the specification is corrected or the "
                    f"answer is given again.")
        if self.fact in NEEDS_RECORD:
            record = (f" Answer with one of {', '.join(self.values())} and, after a semicolon, the record that "
                      f"states it.")
        else:
            record = " Name the record that states it after a semicolon, if one does."
        return f"{name}: {ASKS.get(self.fact, f'what is {self.fact.noun}?')}{record}"

    def evidence(self) -> tuple[str, ...]:
        lines = [f"decides: {'; '.join(self.waiting)}"]
        lines += [f"rule: {rule}" for rule in self.rules[:3]]
        lines += [f"stated: {value}" for value in self.stated]
        lines += [f"known: {value}" for value in self.known]
        lines.append(f"settled by: {self.settled_by()}")
        return tuple(lines)

    def ask(self) -> Ask:
        """The question as the intake queue holds it."""
        return Ask(self.id, AskKind.APPLICABILITY, self.subject, self.text(), choices=self.choices(),
                   evidence=self.evidence(), stakes=self.fact in CONFIRMED,
                   detail={"fact": self.key, "system": self.system, "subject": self.name,
                           "waiting": list(self.waiting), "disagreement": self.disagreement})

    def as_dict(self) -> dict[str, Any]:
        return {"id": self.id, "subject": self.subject, "fact": self.key, "system": self.system or None,
                "question": self.text(), "decides": list(self.waiting), "rules": list(self.rules),
                "stated": list(self.stated), "known": list(self.known), "settledBy": self.settled_by(),
                "values": list(self.values())}


def _subject(finding: Finding, fact: Fact) -> tuple[str, str, str]:
    """(intake subject, system key, name) for a fact a finding needs."""
    if finding.system is not None and fact.facet not in ASSOCIATION_FACETS:
        return system_subject(finding.system.key), finding.system.key, finding.system.name
    return ASSOCIATION, "", "the association"


def standing_findings(rows: Iterable[Any], facts: Facts) -> tuple[Finding, ...]:
    """Rows asked of the association that wait on one of its standing facts (``Fact.standing``): each row whose
    condition the facts leave undetermined with a standing fact missing, or with two sources disagreeing on one. A
    row that waits only on one event's facts is not here: its caller says those, and nobody is asked them in
    advance. ``rows`` are anything with ``applies`` and a name (``notice_elements.conditionals()``)."""
    out: list[Finding] = []
    for row in rows:
        verdict = evaluate(getattr(row, "applies", None) or ALWAYS, facts)
        if verdict.undetermined and (any(f.standing for f in verdict.missing)
                                     or any(v.fact.standing for v in verdict.conflicting)):
            out.append(Finding(row, None, verdict))
    return tuple(out)


def questions(result: SystemApplicability, also: Iterable[Finding] = ()) -> tuple[FactQuestion, ...]:
    """The undetermined answers as questions, one a subject and fact, in first-seen order. ``also`` are findings from
    other rows asked of the association (``standing_findings``: the notice catalog's), which join the same
    questions. A fact of the time facet is not asked: the caller gives the date. Nor is a fact of one event (how one
    meeting is held, what one election decides): the caller that knows the event says it."""
    found: dict[tuple[str, str], dict[str, Any]] = {}

    def slot(subject: str, system: str, name: str, fact: Fact | None, finding: Finding) -> dict[str, Any]:
        key = (subject, fact.value if fact else SYSTEMS_KEY)
        entry = found.setdefault(key, {"subject": subject, "fact": fact, "system": system, "name": name,
                                       "waiting": [], "rules": [], "stated": [], "known": []})
        for held, value in (("waiting", row_name(finding.row)), ("rules", finding.verdict.condition.describe())):
            if value not in entry[held]:
                entry[held].append(value)
        return entry

    for finding in (*result.undetermined, *also):
        verdict = finding.verdict
        for fact in verdict.missing:
            if fact.facet is Facet.TIME or fact.per_event:
                continue
            if finding.system is None and fact in SUBJECT_FACTS:
                slot(ASSOCIATION, "", "the association", None, finding)
                continue
            entry = slot(*_subject(finding, fact), fact, finding)
            for value in verdict.deciding:               # what a partial set already names
                if value.fact is fact and value.describe() not in entry["known"]:
                    entry["known"].append(value.describe())
        for value in verdict.conflicting:
            entry = slot(*_subject(finding, value.fact), value.fact, finding)
            words = (f"{', '.join(sorted(value.fact.format(v) for v in value.value))}" if value.fact.spec.many
                     else value.fact.format(value.value))
            stated = f"{words} ({value.source.value}{', ' + value.where if value.where else ''})"
            if stated not in entry["stated"]:
                entry["stated"].append(stated)
    return tuple(FactQuestion(e["subject"], e["fact"], e["system"], e["name"], tuple(e["waiting"]), tuple(e["rules"]),
                              tuple(e["stated"]), tuple(e["known"])) for e in found.values())


# --- A person's answer as a fact --------------------------------------------------------------------------------


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.casefold()).strip()


def _member(fact: Fact, words: str) -> Any:
    """The member of the fact's closed set a person's words name: its word, its name, or its label (with or without
    the label's parenthetical)."""
    kind = fact.spec.kind
    wanted = _norm(words)
    for member in kind:
        label = fact.format(member)
        names = {_norm(str(member.value)), _norm(member.name), _norm(label), _norm(re.sub(r"\([^)]*\)", " ", label))}
        if wanted and wanted in names:
            return member
    raise ValueError(f"not one of: {', '.join(fact.format(m) for m in kind)}")


def _value(fact: Fact, words: str) -> Any:
    kind = fact.spec.kind
    if not words:
        raise ValueError("the answer is empty")
    if issubclass(kind, Enum):
        return _member(fact, words)
    if kind is int:
        digits = re.sub(r"[,\s]", "", words)
        if not re.fullmatch(r"\d+", digits):
            raise ValueError("not a whole number")
        return int(digits)
    if kind is date:
        try:
            return date.fromisoformat(words)
        except ValueError:
            raise ValueError("not a date as YYYY-MM-DD") from None
    return words


def read_answer(fact: Fact, text: str) -> tuple[Any, str]:
    """A person's answer as the fact's value, and the record named after a semicolon ("NFPA 13R; the 2006 permit").
    A many-valued fact takes its values separated by commas. ValueError says why an answer is not the fact."""
    words, _, record = (text or "").partition(";")
    words, record = words.strip(), " ".join(record.split())
    if fact.spec.many:
        parts = [p.strip() for p in re.split(r",|\band\b", words) if p.strip()]
        if not parts:
            raise ValueError("the answer is empty")
        value: Any = frozenset(_value(fact, p) for p in parts)
    else:
        value = _value(fact, words)
    if fact in NEEDS_RECORD and not record:
        raise ValueError("no record named: it is entered with the record that states it, after a semicolon "
                         "(\"NFPA 13R; the 2006 permit\")")
    return value, record


@dataclass(frozen=True)
class Answered:
    """People's answers, sorted: the facts in use by subject (a system's key; None for the association), each with
    its question; the answers that could not be read, with why; those waiting for a second person; and those that
    are not facts (which systems there are), noted for the specification."""

    facts: dict[str | None, tuple[FactValue, ...]]
    used: tuple[tuple[Ask, FactValue], ...] = ()
    unread: tuple[tuple[Ask, str], ...] = ()
    waiting: tuple[Ask, ...] = ()
    noted: tuple[Ask, ...] = ()
    dismissed: tuple[Ask, ...] = ()

    def of(self, ident: str) -> FactValue | None:
        return next((value for ask, value in self.used if ask.id == ident), None)


def fact_of(ask: Ask) -> Fact | None:
    """The fact a stored question asks for; None for the question of which systems there are."""
    key = str(ask.detail.get("fact") or "")
    return None if key == SYSTEMS_KEY else Fact(key)


def answer_value(ask: Ask) -> FactValue:
    """An answered question as a fact with source ``ANSWER``. ValueError when the answer is not the fact."""
    fact = fact_of(ask)
    if fact is None:
        raise ValueError("which systems there are is not one fact: it becomes rows in the specification")
    value, record = read_answer(fact, ask.answer)
    where = f"intake question {ask.id}: {ask.answered_by}, {ask.answered_at[:10]}"
    return FactValue(fact, value, Source.ANSWER, where + (f"; {record}" if record else "; no record named"))


def answered(asks: Iterable[Ask]) -> Answered:
    """The answered questions of this kind as facts for ``life_safety.applicable(..., answers=found.facts)``."""
    facts: dict[str | None, list[FactValue]] = {}
    used, unread, waiting, noted, dismissed = [], [], [], [], []
    for ask in asks:
        if ask.kind is not AskKind.APPLICABILITY:
            continue
        if ask.status is AskStatus.DISMISSED:
            dismissed.append(ask)
            continue
        if ask.status not in (AskStatus.ANSWERED, AskStatus.APPLIED):
            continue
        try:
            fact = fact_of(ask)
        except ValueError:
            unread.append((ask, f"the question names a fact jason no longer has: {ask.detail.get('fact')!r}"))
            continue
        if fact is None:
            noted.append(ask)
            continue
        if high_stakes(ask) and not ask.confirmed_by:
            waiting.append(ask)
            continue
        try:
            value = answer_value(ask)
        except (ValueError, TypeError) as exc:
            unread.append((ask, str(exc)))
            continue
        facts.setdefault(str(ask.detail.get("system") or "") or None, []).append(value)
        used.append((ask, value))
    return Answered({k: tuple(v) for k, v in facts.items()}, tuple(used), tuple(unread), tuple(waiting),
                    tuple(noted), tuple(dismissed))


def applied_note(ask: Ask) -> tuple[bool, str]:
    """What ``jason intake --apply`` records for an answered question of this kind: (True, what the answer became),
    or (False, why it is not applied). The answer itself is the record; nothing else is written."""
    try:
        fact = fact_of(ask)
    except ValueError:
        return False, f"the question names a fact jason no longer has: {ask.detail.get('fact')!r}"
    if fact is None:
        return True, f"noted for the specification: a person writes the systems as rows ({_METHOD})"
    try:
        value = answer_value(ask)
    except (ValueError, TypeError) as exc:
        return False, f"not read as {fact.noun}: {exc}"
    return True, f"a fact for jason applies: {value.describe()}"


# --- The page ---------------------------------------------------------------------------------------------------


def _state(question: FactQuestion, ask: Ask | None, found: Answered) -> str:
    if ask is None:
        return "not filed"
    who = f"{ask.answered_by}, {ask.answered_at[:10]}"
    if ask.status is AskStatus.DISMISSED:
        return f"dismissed by {who}: the rows stay undetermined"
    if ask.status in (AskStatus.ANSWERED, AskStatus.APPLIED):
        if any(a.id == ask.id for a, _ in found.unread):
            return f"answered by {who}, not read"
        if any(a.id == ask.id for a in found.waiting):
            return f"answered by {who}; a second person confirms it (jason intake --confirm {ask.id} --by NAME)"
        if question.fact is None:
            return f"answered by {who}; noted for the specification"
        if question.disagreement:
            return f"answered by {who}; the sources disagree, so it is not settled"
        return f"answered by {who}"
    return "stale: filed, and asked again" if ask.status is AskStatus.STALE else "open"


def question_lines(found_questions: Iterable[FactQuestion], stored: Iterable[Ask], found: Answered) -> list[str]:
    """The questions with each one's state in the queue, then the answers in use and the answers not read."""
    by_id = {a.id: a for a in stored}
    asked = tuple(found_questions)
    lines = [f"Questions for a person ({len(asked)})"]
    for q in asked:
        ask = by_id.get(q.id)
        lines += [f"  [{q.id}] {q.subject} {q.key} ({_state(q, ask, found)})", f"    {q.text()}"]
        lines += [f"    {line}" for line in q.evidence()]
        if q.choices():
            lines.append("    choices: " + " | ".join(f"{n}. {c}" for n, c in enumerate(q.choices(), 1)))
        if ask is not None and ask.answer and ask.status is not AskStatus.OPEN:
            lines.append(f"    answer: {ask.answer!r}")
    if not asked:
        lines.append("  none")
    if found.used:
        lines += ["", f"Answers in use ({len(found.used)})"]
        lines += [f"  [{ask.id}] {ask.detail.get('subject') or ask.subject}: {value.describe()}"
                  for ask, value in found.used]
    if found.unread:
        lines += ["", f"Answers not read ({len(found.unread)}): answer again with jason intake --answer ID TEXT --by NAME"]
        lines += [f"  [{ask.id}] {ask.answer!r}: {why}" for ask, why in found.unread]
    return lines


__all__ = [
    "SCOPE", "ASSOCIATION", "SYSTEMS_KEY", "ASSOCIATION_FACETS", "NEEDS_RECORD", "CONFIRMED", "ASKS", "SETTLED_BY",
    "system_subject", "FactQuestion", "standing_findings", "questions", "read_answer", "Answered", "fact_of", "answer_value", "answered",
    "applied_note", "question_lines",
]
