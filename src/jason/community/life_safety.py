"""The association's life safety systems, and which rule rows reach each one.

A ``LifeSafetySystem`` is one system the profile states: its kind, the standard it was installed under (None when no
record on hand says), what it serves, who services and monitors it, and where each fact comes from. The systems are the
profile's (``Community.life_safety_systems()``, empty by default); nothing here names one. Which kind each building
has is a fact from the plans, the permit, or the installer's record, never something to infer
(docs/fire-protection.md).

``system_facts(system)`` turns one system into applicability facts (source PROFILE), so a row's ``applies`` condition
is evaluated once per system. ``applicable(community)`` does that for every obligation: a row whose condition tests a
subject fact (the system, its installation standard) is asked of each system, and a row that tests none is asked of
the association. The answer is three groups, as ``jason.community.applicability`` gives them:

- applies;
- does not apply, with the fact that decided it and where that fact comes from;
- undetermined, with the missing fact, as a question for a person. It is never read as "does not apply".

Two records that state different standards for one system are both kept (``also_stated``). Each is tested: where they
give the same answer it stands, and where they do not the row is undetermined with both named. jason never picks one.

Pure: no network, no store.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Callable, Iterable

from jason.community.applicability import (
    ALWAYS,
    Answer,
    Condition,
    Facet,
    Fact,
    Facts,
    FactValue,
    InstallationStandard,
    Source,
    SystemKind,
    Verdict,
    facts_tested,
    partition,
    profile_facts,
)

# The facts that describe one system. A row whose condition tests any of them is asked of each system.
SUBJECT_FACTS: frozenset[Fact] = frozenset(f for f in Fact if f.facet is Facet.SUBJECT)

_METHOD = "Community.life_safety_systems()"


@dataclass(frozen=True)
class StandardReading:
    """An installation standard a record states for a system, and the record that states it."""

    standard: InstallationStandard
    where: str

    def __post_init__(self) -> None:
        if not isinstance(self.standard, InstallationStandard):
            raise TypeError(f"expected InstallationStandard, got {self.standard!r}")
        if not self.where.strip():
            raise ValueError("a standard is entered with the record that states it")


@dataclass(frozen=True)
class LifeSafetySystem:
    """One life safety system the association has.

    ``standard`` is the standard it was installed under and ``standard_from`` the record that says so; ``standard``
    stays None until a record on hand states it, so a rule that turns on it comes back undetermined with the question.
    ``also_stated`` holds a different standard another record states for the same system. ``serves`` are the profile's
    own building symbols and ``serves_label`` the same in words (or a label where the system serves no building).
    ``servicer`` and ``monitor`` are vendors' names in the profile's sender directory, empty when there is none.
    ``note`` says where the facts come from and what is not known.
    """

    key: str
    name: str
    kind: SystemKind
    standard: InstallationStandard | None = None
    standard_from: str = ""
    also_stated: tuple[StandardReading, ...] = ()
    serves: tuple = ()
    serves_label: str = ""
    servicer: str = ""
    monitor: str = ""
    note: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.kind, SystemKind):
            raise TypeError(f"{self.key}: expected SystemKind, got {self.kind!r}")
        if self.standard is not None:
            StandardReading(self.standard, self.standard_from)      # a symbol, and the record that states it
        elif self.also_stated:
            raise ValueError(f"{self.key}: also_stated is for a second record; enter the first as standard")
        if any(r.standard is self.standard for r in self.also_stated):
            raise ValueError(f"{self.key}: also_stated repeats the standard")

    def readings(self) -> tuple[StandardReading, ...]:
        """Every standard a record states for this system; empty when none does."""
        first = (StandardReading(self.standard, self.standard_from),) if self.standard is not None else ()
        return first + tuple(self.also_stated)

    def served(self) -> str:
        """What it serves, in words."""
        return self.serves_label or ", ".join(str(getattr(s, "value", s)) for s in self.serves)

    def as_dict(self) -> dict[str, Any]:
        return {"key": self.key, "name": self.name, "kind": self.kind.value,
                "standard": self.standard.value if self.standard else None, "standardFrom": self.standard_from,
                "alsoStated": [{"standard": r.standard.value, "where": r.where} for r in self.also_stated],
                "serves": [getattr(s, "value", s) for s in self.serves], "served": self.served(),
                "servicer": self.servicer, "monitor": self.monitor, "note": self.note}


def system_facts(system: LifeSafetySystem) -> Facts:
    """One system as applicability facts, each from the profile: its kind, and each standard a record states for it.
    A system with no standard on record gives no standard fact, so a condition on it is undetermined."""
    values = [FactValue(Fact.SYSTEM, system.kind, Source.PROFILE, f"{_METHOD}: {system.key}")]
    values += [FactValue(Fact.INSTALLATION_STANDARD, r.standard, Source.PROFILE, r.where) for r in system.readings()]
    return Facts(()).merge(values)


def _condition(row: Any) -> Condition:
    return getattr(row, "applies", None) or ALWAYS


def row_name(row: Any) -> str:
    return str(getattr(row, "name", "") or getattr(row, "key", "") or row)


# How a missing fact is asked for, where the plain "what is ..." would not say who can answer it.
_ASK: dict[Fact, str] = {
    Fact.INSTALLATION_STANDARD: "which standard was it installed under? The plans, the permit, or the installer's "
                                "record says.",
}


@dataclass(frozen=True)
class Finding:
    """One row asked of one system (``system`` None: asked of the association), and the answer."""

    row: Any
    system: LifeSafetySystem | None
    verdict: Verdict

    @property
    def subject(self) -> str:
        return self.system.name if self.system else "the association"

    def why(self) -> str:
        """The facts that decided it (or, undetermined, the facts known so far), each with where it comes from."""
        return "; ".join(v.describe() for v in self.verdict.deciding)

    def question(self) -> str:
        """What a person must settle for an undetermined answer; empty otherwise."""
        if not self.verdict.undetermined:
            return ""
        missing = self.verdict.missing
        if self.system is None and SUBJECT_FACTS.intersection(missing):
            return (f"Which life safety systems does the association have? The specification lists none "
                    f"({_METHOD}).")
        parts = [f"{self.subject}: " + _ASK.get(fact, f"what is {fact.noun}?") for fact in missing]
        by_fact: dict[Fact, list[FactValue]] = {}
        for value in self.verdict.conflicting:
            by_fact.setdefault(value.fact, []).append(value)
        for fact, values in by_fact.items():
            stated = "; ".join(f"{fact.format(v.value)} ({v.where or v.source.value})" for v in values)
            parts.append(f"{self.subject}: the records disagree on {fact.noun}: {stated}. Which is right?")
        return " ".join(parts)

    def as_dict(self) -> dict[str, Any]:
        return {"row": row_name(self.row), "authority": getattr(self.row, "authority", ""),
                "system": self.system.key if self.system else None, "subject": self.subject,
                "verdict": self.verdict.as_dict(), "why": self.why(), "question": self.question()}


@dataclass(frozen=True)
class Question:
    """One question for a person, and the rows that wait on its answer."""

    text: str
    system: LifeSafetySystem | None
    waiting: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {"question": self.text, "system": self.system.key if self.system else None, "waiting": list(self.waiting)}


@dataclass(frozen=True)
class SystemApplicability:
    """Every row's answer for every system, in three groups, each in the systems' order and then the rows'."""

    systems: tuple[LifeSafetySystem, ...] = ()
    applies: tuple[Finding, ...] = ()
    does_not_apply: tuple[Finding, ...] = ()
    undetermined: tuple[Finding, ...] = ()
    whole: bool = True                    # False for one system's part, which cannot say what reaches no system

    def of(self, system: LifeSafetySystem | None) -> "SystemApplicability":
        """The same three groups for one system alone (None: the rows asked of the association)."""
        keep = lambda group: tuple(f for f in group if f.system is system)  # noqa: E731
        return SystemApplicability((system,) if system else (), keep(self.applies), keep(self.does_not_apply),
                                   keep(self.undetermined), whole=False)

    def questions(self) -> tuple[Question, ...]:
        """The undetermined answers as questions, one per question however many rows wait on it."""
        found: dict[str, tuple[LifeSafetySystem | None, list[str]]] = {}
        for finding in self.undetermined:
            _, waiting = found.setdefault(finding.question(), (finding.system, []))
            if row_name(finding.row) not in waiting:
                waiting.append(row_name(finding.row))
        return tuple(Question(text, system, tuple(waiting)) for text, (system, waiting) in found.items())

    def unreached(self) -> tuple[Any, ...]:
        """Rows asked of the systems that reach none of them: every answer was "does not apply". Either the
        association has no such system or the specification does not list it, so it is shown, not dropped. One
        system's part (``of``) answers with none: only the whole result can say it."""
        if not self.whole:
            return ()
        reached = {id(f.row) for f in self.applies + self.undetermined}
        out: list[Any] = []
        for finding in self.does_not_apply:
            if finding.system is not None and id(finding.row) not in reached and finding.row not in out:
                out.append(finding.row)
        return tuple(out)

    def as_dict(self) -> dict[str, Any]:
        return {"systems": [s.as_dict() for s in self.systems],
                "applies": [f.as_dict() for f in self.applies],
                "doesNotApply": [f.as_dict() for f in self.does_not_apply],
                "undetermined": [f.as_dict() for f in self.undetermined],
                "questions": [q.as_dict() for q in self.questions()],
                "unreached": [row_name(r) for r in self.unreached()]}


def applicable(community: Any, rows: Iterable[Any] | None = None, *, as_of: date | None = None,
               condition_of: Callable[[Any], Condition] = _condition) -> SystemApplicability:
    """Each row's answer for each of the community's systems; ``rows`` default to its obligations.

    A row whose condition tests a subject fact is asked of each system, with the system's facts beside the profile's
    own (``profile_facts``) and the date. A row that tests none is asked of the association once. A community that
    lists no systems leaves every system row undetermined, with the question of which systems it has.
    """
    rows = tuple(community.obligations() or ()) if rows is None else tuple(rows)
    systems = tuple(community.life_safety_systems() or ())
    base = Facts.build(profile=profile_facts(community), as_of=as_of)
    of_systems = tuple(r for r in rows if facts_tested(condition_of(r)) & SUBJECT_FACTS)
    of_association = tuple(r for r in rows if not facts_tested(condition_of(r)) & SUBJECT_FACTS)
    groups: dict[Answer, list[Finding]] = {answer: [] for answer in Answer}

    def add(facts: Facts, asked: tuple[Any, ...], system: LifeSafetySystem | None) -> None:
        parts = partition(asked, facts, condition_of)
        for answer, pairs in ((Answer.APPLIES, parts.applies), (Answer.DOES_NOT_APPLY, parts.does_not_apply),
                              (Answer.UNDETERMINED, parts.undetermined)):
            groups[answer].extend(Finding(row, system, verdict) for row, verdict in pairs)

    for system in systems:
        add(base.merge(system_facts(system)), of_systems, system)
    if not systems:
        add(base, of_systems, None)
    add(base, of_association, None)
    return SystemApplicability(systems, tuple(groups[Answer.APPLIES]), tuple(groups[Answer.DOES_NOT_APPLY]),
                               tuple(groups[Answer.UNDETERMINED]))


def _both_stated(verdict: Verdict) -> str:
    """Where the deciding facts hold two values for one fact (two records, one answer), the values in words."""
    seen: dict[Fact, list[str]] = {}
    for value in verdict.deciding:
        words = value.fact.format(value.value) if not value.fact.spec.many else ""
        if words and words not in seen.setdefault(value.fact, []):
            seen[value.fact].append(words)
    return "; ".join(f"the records state {' and '.join(words)} for {fact.noun}; the answer is the same under either"
                     for fact, words in seen.items() if len(words) > 1)


def _grouped(findings: Iterable[Finding], key: Callable[[Finding], str]) -> list[tuple[str, list[Finding]]]:
    """Findings that share a reason, kept together in first-seen order, so the reason is printed once."""
    groups: dict[str, list[Finding]] = {}
    for finding in findings:
        groups.setdefault(key(finding), []).append(finding)
    return list(groups.items())


def _system_lines(system: LifeSafetySystem) -> list[str]:
    lines = [f"{system.name} ({system.kind.label})"]
    if system.served():
        lines.append(f"  serves: {system.served()}")
    for reading in system.readings():
        lines.append(f"  standard: {reading.standard.label}, from {reading.where}")
    if not system.readings():
        lines.append("  standard: not on record")
    if system.servicer:
        lines.append(f"  services it: {system.servicer}")
    if system.monitor:
        lines.append(f"  monitors it: {system.monitor}")
    if system.note:
        lines.append(f"  note: {system.note}")
    return lines


def _group_lines(part: SystemApplicability) -> list[str]:
    lines: list[str] = []
    if part.applies:
        lines.append(f"  applies ({len(part.applies)})")
        for note, findings in _grouped(part.applies, lambda f: _both_stated(f.verdict)):
            lines += [f"    {row_name(f.row)}" for f in findings]
            if note:
                lines.append(f"      ({note})")
    if part.undetermined:
        lines.append(f"  undetermined ({len(part.undetermined)})")
        for f in part.undetermined:
            lines.append(f"    {row_name(f.row)}")
            lines.append(f"      rule: {f.verdict.condition.describe()}")
            lines.append(f"      question: {f.question()}")
    if part.does_not_apply:
        lines.append(f"  does not apply ({len(part.does_not_apply)})")
        for why, findings in _grouped(part.does_not_apply, Finding.why):
            lines.append(f"    decided by {why}:")
            lines += [f"      {row_name(f.row)}" for f in findings]
    if not lines:
        lines.append("  no row is asked of it")
    return lines


def applicability_lines(result: SystemApplicability, *, association: bool = False) -> list[str]:
    """The result as plain lines, a system at a time: what applies, what is undetermined with its question, and what
    does not apply with the fact that decided it. ``association`` adds the rows asked of the association as a whole;
    an undetermined one is shown either way."""
    lines: list[str] = []
    for system in result.systems:
        lines += [*_system_lines(system), *_group_lines(result.of(system)), ""]
    if not result.systems and result.whole:
        lines += [f"The specification lists no life safety systems ({_METHOD}).", ""]
    rest = result.of(None)
    if not association:
        rest = SystemApplicability((), (), (), rest.undetermined, whole=False)
    if rest.applies or rest.does_not_apply or rest.undetermined:
        lines += ["The association", *_group_lines(rest), ""]
    unreached = result.unreached()
    if unreached:
        lines.append(f"Rows that reach no listed system ({len(unreached)})")
        for row in unreached:
            lines.append(f"  {row_name(row)}: {_condition(row).describe()}")
        lines += ["  Either the association has no such system or the specification does not list it.", ""]
    questions = result.questions()
    lines.append(f"Questions for a person ({len(questions)})")
    for q in questions:
        lines.append(f"  {q.text}")
        lines.append(f"    waiting on it: {'; '.join(q.waiting)}")
    if not questions:
        lines.append("  none")
    return lines


__all__ = [
    "SUBJECT_FACTS", "StandardReading", "LifeSafetySystem", "system_facts", "row_name", "Finding", "Question",
    "SystemApplicability", "applicable", "applicability_lines",
]
