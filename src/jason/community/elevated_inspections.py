"""Each building's inspection of exterior elevated elements under Civil Code 5551: when its elements were last
inspected, by whom as a licensed professional, the report on file, when the next is due under the section's cycle,
and whether subdivisions (k) and (l) reach the building.

The section's duty is the association's, for one sample across the project and one report (5551(b)(1), (j)(1)), so
the obligation row is asked of the association as a whole (``jason.community.life_safety``). Two of its subdivisions
are nevertheless about one building each, which is why this record is per building:

- (k): "The inspection of buildings for which a building permit application has been submitted on or after January
  1, 2020, shall occur no later than six years following the issuance of a certificate of occupancy."
- (l): "This section shall only apply to buildings containing three or more attached multifamily dwelling units."

An ``ElevatedElementsInspection`` is one building's record, stated by the profile
(``Community.elevated_elements_inspections()``, empty by default) from its private facts: the inspector is a person
and the report a file, so the rows live under ``data/spec``, never in the specification. Each fact is entered with
the record that states it, and a fact the profile does not state stays None: the building's answer is then a
question for a person (``questions()``), never a date jason guesses. In particular, a report on file whose date of
inspection has not been read into the record is a question, and the next due day stays unknown.

The cycle, in the section's words (``jason cite "CIV 5551"``):

- (b)(1): "At least once every nine years"; (i): "The first inspection shall be completed by January 1, 2025, and
  then every nine years thereafter". A building inspected on a day is next due nine years after it.
- (k), for a building whose permit application was submitted on or after January 1, 2020: the first inspection "no
  later than six years following the issuance of a certificate of occupancy". The permit application's date says
  whether (k) reaches the building, and the certificate's date counts the six years; either unknown is a question.
- (i), for every other building with no inspection on record: January 1, 2025, already past.

Whether the section reaches a building is ``applicability.ELEVATED_ELEMENTS_INSPECTION`` asked with the building's
own facts (its attached units for (l), and whether the association maintains or repairs elevated elements in it for
(b)(1)) over the profile's. The three answers are the module's: applies, does not apply with the deciding fact, and
undetermined with the fact missing. ``jason applies`` prints each building, and ``jason deadlines`` lists each
building's next due day beside the association's own row. Pure: no network, no store.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum
from typing import Any, Callable, Iterable, Mapping

from jason.community.applicability import (
    ELEVATED_ELEMENTS_INSPECTION,
    Answer,
    AtLeast,
    Condition,
    ElevatedElements,
    Fact,
    Facts,
    FactValue,
    Source,
    Verdict,
    evaluate,
    profile_facts,
)
from jason.community.obligations import Standing

_METHOD = "Community.elevated_elements_inspections()"
AUTHORITY = "Civil Code 5551(b)(1), (i), (k), (l)"

# The section's own numbers, each beside the words it comes from.
FIRST_DUE = date(2025, 1, 1)          # (i): "The first inspection shall be completed by January 1, 2025"
CYCLE_YEARS = 9                       # (b)(1): "At least once every nine years"; (i): "every nine years thereafter"
PERMIT_RULE_FROM = date(2020, 1, 1)   # (k): "a building permit application has been submitted on or after January 1, 2020"
PERMIT_RULE_YEARS = 6                 # (k): "no later than six years following the issuance of a certificate of occupancy"
MIN_ATTACHED_UNITS = 3                # (l): "buildings containing three or more attached multifamily dwelling units"

# (l) alone, so a building's answer names it; the whole section's condition is ELEVATED_ELEMENTS_INSPECTION.
ATTACHED_UNITS_RULE: Condition = AtLeast(Fact.ATTACHED_UNITS, MIN_ATTACHED_UNITS)

# The facts a building states for itself; the profile's own values for them (the most units in any one building)
# are set aside when the building is asked.
_BUILDING_FACTS: frozenset[Fact] = frozenset({Fact.ATTACHED_UNITS, Fact.ELEVATED_ELEMENTS})


class InspectorLicense(Enum):
    """The professional 5551(b)(1) names: "a licensed structural or civil engineer or architect"."""

    STRUCTURAL_ENGINEER = "structural_engineer"
    CIVIL_ENGINEER = "civil_engineer"
    ARCHITECT = "architect"

    @property
    def label(self) -> str:
        return {InspectorLicense.STRUCTURAL_ENGINEER: "licensed structural engineer",
                InspectorLicense.CIVIL_ENGINEER: "licensed civil engineer",
                InspectorLicense.ARCHITECT: "licensed architect"}[self]


def years_after(day: date, years: int) -> date:
    """``day`` moved ``years`` later; February 29 lands on February 28."""
    try:
        return day.replace(year=day.year + years)
    except ValueError:
        return day.replace(year=day.year + years, day=28)


@dataclass(frozen=True)
class Reach:
    """One subdivision's answer for one building, and why."""

    subdivision: str
    answer: Answer
    why: str

    def as_dict(self) -> dict[str, Any]:
        return {"subdivision": self.subdivision, "answer": self.answer.value, "why": self.why}


@dataclass(frozen=True)
class Due:
    """When a building's next inspection is due: the day, the subdivision and count it comes from, and, when the day
    cannot be given, what a person must settle."""

    day: date | None
    under: str
    question: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {"day": self.day.isoformat() if self.day else None, "under": self.under, "question": self.question}


@dataclass(frozen=True)
class ElevatedElementsInspection:
    """One building's record under Civil Code 5551.

    ``building`` is the profile's own building symbol and ``label`` the same in words. ``attached_units`` is what (l)
    counts; ``responsibility`` says whether the association maintains or repairs exterior elevated elements in this
    building (5551(b)(1)), and ``elements`` how many the inspector's list ((c)) places in it. ``inspected_on`` is the
    date of inspection the report's first page gives ((e)(5)(A)), entered only with ``report``, the report on file;
    ``inspector``, ``license``, and ``license_number`` say who inspected it and under which license (b)(1) names.
    ``permit_application_on`` and ``occupancy_certificate_on`` are the two dates (k) turns on. Each stays None until a
    record states it, and ``note`` says where the facts come from and what is not known.
    """

    building: Any
    label: str
    attached_units: int | None = None
    responsibility: ElevatedElements | None = None
    elements: int | None = None
    inspected_on: date | None = None
    inspector: str = ""
    license: InspectorLicense | None = None
    license_number: str = ""
    report: str = ""
    permit_application_on: date | None = None
    occupancy_certificate_on: date | None = None
    note: str = ""

    def __post_init__(self) -> None:
        if not self.label.strip():
            raise ValueError("a building's record is entered with its label")
        for name in ("attached_units", "elements"):
            value = getattr(self, name)
            if value is not None and (isinstance(value, bool) or not isinstance(value, int) or value < 0):
                raise TypeError(f"{self.label}: {name} is a count or None, got {value!r}")
        if self.responsibility is not None and not isinstance(self.responsibility, ElevatedElements):
            raise TypeError(f"{self.label}: expected ElevatedElements, got {self.responsibility!r}")
        if self.license is not None and not isinstance(self.license, InspectorLicense):
            raise TypeError(f"{self.label}: expected InspectorLicense, got {self.license!r}")
        for name in ("inspected_on", "permit_application_on", "occupancy_certificate_on"):
            value = getattr(self, name)
            if value is not None and not isinstance(value, date):
                raise TypeError(f"{self.label}: {name} is a date or None, got {value!r}")
        if self.inspected_on is not None and not self.report.strip():
            raise ValueError(f"{self.label}: an inspection date is entered with the report that states it")

    # --- facts and reach ---------------------------------------------------------------------------------------

    def facts(self) -> tuple[FactValue, ...]:
        """The building's own applicability facts, each from the profile."""
        where = f"{_METHOD}: {self.label}"
        out: list[FactValue] = []
        if self.attached_units is not None:
            out.append(FactValue(Fact.ATTACHED_UNITS, self.attached_units, Source.PROFILE, where))
        if self.responsibility is not None:
            out.append(FactValue(Fact.ELEVATED_ELEMENTS, self.responsibility, Source.PROFILE, where))
        return tuple(out)

    def reaches(self, base: Facts | None = None) -> Verdict:
        """Whether the section reaches this building (``ELEVATED_ELEMENTS_INSPECTION``): the building's facts over
        the association's (``base``, the profile's facts without its own values for the building's facts)."""
        kept = tuple(v for v in (base.values if base else ()) if v.fact not in _BUILDING_FACTS)
        return evaluate(ELEVATED_ELEMENTS_INSPECTION, Facts(kept).merge(self.facts()))

    def units_rule(self) -> Reach:
        """(l): three or more attached multifamily dwelling units."""
        verdict = evaluate(ATTACHED_UNITS_RULE, Facts(self.facts()))
        if verdict.undetermined:
            return Reach("(l)", Answer.UNDETERMINED, "the number of attached multifamily dwelling units is not on record")
        return Reach("(l)", verdict.answer, "; ".join(v.describe() for v in verdict.deciding))

    def permit_rule(self) -> Reach:
        """(k): a building permit application submitted on or after January 1, 2020."""
        day = self.permit_application_on
        if day is None:
            return Reach("(k)", Answer.UNDETERMINED, "the building permit application's date is not on record")
        if day >= PERMIT_RULE_FROM:
            return Reach("(k)", Answer.APPLIES, f"the permit application of {day.isoformat()} is on or after "
                                                f"{PERMIT_RULE_FROM.isoformat()}")
        return Reach("(k)", Answer.DOES_NOT_APPLY, f"the permit application of {day.isoformat()} is before "
                                                   f"{PERMIT_RULE_FROM.isoformat()}")

    # --- the cycle -----------------------------------------------------------------------------------------------

    def due(self) -> Due:
        """The next inspection's day under the section's cycle, or the question that stands in its place."""
        if self.inspected_on is not None:
            return Due(years_after(self.inspected_on, CYCLE_YEARS),
                       f"(b)(1), (i): {CYCLE_YEARS} years from the inspection of {self.inspected_on.isoformat()}")
        permit = self.permit_rule()
        if permit.answer is Answer.APPLIES:
            if self.occupancy_certificate_on is not None:
                return Due(years_after(self.occupancy_certificate_on, PERMIT_RULE_YEARS),
                           f"(k): {PERMIT_RULE_YEARS} years from the certificate of occupancy of "
                           f"{self.occupancy_certificate_on.isoformat()}")
            return Due(None, "(k)", "no inspection is on record, and (k) counts six years from the certificate of "
                                    "occupancy, whose date is not on record: enter it from the certificate")
        if permit.answer is Answer.DOES_NOT_APPLY:
            return Due(FIRST_DUE, f"(i): the first inspection by {FIRST_DUE.isoformat()}")
        return Due(None, "(i) or (k)", "no inspection is on record, and the building permit application's date is "
                                       f"not: under (i) the first inspection was due {FIRST_DUE.isoformat()}, under "
                                       "(k) six years from the certificate of occupancy. Enter the permit "
                                       "application's date, or the date of inspection from the report on file")

    def standing(self, today: date, *, soon_days: int = 60) -> Standing:
        """Where the next due day stands on ``today``; ``UNKNOWN`` when no day can be given."""
        due = self.due()
        if due.day is None:
            return Standing.UNKNOWN
        left = (due.day - today).days
        return Standing.OVERDUE if left < 0 else Standing.DUE_SOON if left <= soon_days else Standing.UPCOMING

    # --- what a person settles -----------------------------------------------------------------------------------

    def questions(self, base: Facts | None = None) -> tuple[str, ...]:
        """What a person must settle for this building, each a finding and none a guess. With ``base`` (the
        association's facts), a building the section does not reach raises none: nothing is due of it."""
        if base is not None and self.reaches(base).answer is Answer.DOES_NOT_APPLY:
            return ()
        out: list[str] = []
        if self.inspected_on is None and self.report.strip():
            out.append(f"the report on file ({self.report}) has not been read into the record: enter the date of "
                       "inspection from its first page (5551(e)(5)(A))")
        if self.inspected_on is not None and self.license is None:
            out.append("the inspection is on record with no licensed professional: 5551(b)(1) requires a licensed "
                       "structural or civil engineer or architect; enter who inspected it and under which license")
        due = self.due()
        if due.question:
            out.append(due.question)
        units = self.units_rule()
        if units.answer is Answer.UNDETERMINED:
            out.append(f"(l): {units.why}")
        # (k) undetermined is asked only where it changes the due day (``due`` asks it); once a building is
        # inspected the next is nine years on under either subdivision.
        if self.responsibility is None:
            out.append("whether the association maintains or repairs exterior elevated elements in this building "
                       "(5551(b)(1)) is not on record")
        return tuple(dict.fromkeys(out))

    def last(self) -> str:
        """The last inspection in words, or that none is on record."""
        if self.inspected_on is None:
            return "no inspection on record"
        who = self.inspector or "an inspector not on record"
        kind = f", {self.license.label}" if self.license else ", license not on record"
        number = f" {self.license_number}" if self.license_number else ""
        return f"{self.inspected_on.isoformat()} by {who}{kind}{number}; report: {self.report}"

    def as_dict(self, base: Facts | None = None) -> dict[str, Any]:
        due = self.due()
        return {"building": getattr(self.building, "value", self.building), "label": self.label,
                "attachedUnits": self.attached_units,
                "responsibility": self.responsibility.value if self.responsibility else None,
                "elements": self.elements, "inspectedOn": self.inspected_on.isoformat() if self.inspected_on else None,
                "inspector": self.inspector, "license": self.license.value if self.license else None,
                "licenseNumber": self.license_number, "report": self.report,
                "permitApplicationOn": self.permit_application_on.isoformat() if self.permit_application_on else None,
                "occupancyCertificateOn": (self.occupancy_certificate_on.isoformat()
                                           if self.occupancy_certificate_on else None),
                "reaches": self.reaches(base).as_dict(), "unitsRule": self.units_rule().as_dict(),
                "permitRule": self.permit_rule().as_dict(), "due": due.as_dict(),
                "questions": list(self.questions(base)), "note": self.note}


# --- the profile's rows --------------------------------------------------------------------------------------------


def _date(value: Any, label: str, name: str) -> date | None:
    if value in (None, ""):
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError as exc:
        raise ValueError(f"{label}: {name} is not a date: {value!r}") from exc


def _count(value: Any) -> int | None:
    return None if value in (None, "") else int(value)


def from_rows(rows: Iterable[Mapping[str, Any]], building_of: Callable[[Any], Any] = str) -> tuple[ElevatedElementsInspection, ...]:
    """The records from the profile's private rows, each word turned into its symbol (AGENTS.md: JSON may store the
    word; the loader turns it into a symbol). ``building_of`` makes the profile's building symbol from the row's
    ``building``; ``label`` defaults to "building N". A row with no building is skipped."""
    out: list[ElevatedElementsInspection] = []
    for row in rows:
        if row.get("building") in (None, ""):
            continue
        label = str(row.get("label") or f"building {row['building']}")
        responsibility = row.get("responsibility")
        license_ = row.get("license")
        out.append(ElevatedElementsInspection(
            building=building_of(row["building"]), label=label,
            attached_units=_count(row.get("attached_units")),
            responsibility=ElevatedElements(responsibility) if responsibility else None,
            elements=_count(row.get("elements")),
            inspected_on=_date(row.get("inspected_on"), label, "inspected_on"),
            inspector=str(row.get("inspector") or ""),
            license=InspectorLicense(license_) if license_ else None,
            license_number=str(row.get("license_number") or ""),
            report=str(row.get("report") or ""),
            permit_application_on=_date(row.get("permit_application_on"), label, "permit_application_on"),
            occupancy_certificate_on=_date(row.get("occupancy_certificate_on"), label, "occupancy_certificate_on"),
            note=str(row.get("note") or "")))
    return tuple(out)


def records(community: Any) -> tuple[ElevatedElementsInspection, ...]:
    """The community's per-building records; empty for a profile that states none."""
    return tuple(getattr(community, "elevated_elements_inspections", lambda: ())() or ())


def base_facts(community: Any) -> Facts:
    return Facts(profile_facts(community))


# --- for jason deadlines ---------------------------------------------------------------------------------------------


def calendar_rows(community: Any, today: date, *, soon_days: int = 60) -> list[dict[str, Any]]:
    """One calendar row a building, in the shape ``jason.tasks.deadlines.calendar`` gives its obligations: the next
    due day under the cycle, its standing, the last inspection, and the note with the building's questions. A
    building the section does not reach is left out: ``jason applies`` lists it with the deciding fact. An unknown
    day is a row with standing ``date not on record`` and the question in its note, never a guessed date."""
    found = records(community)
    if not found:
        return []
    base = base_facts(community)
    rows: list[dict[str, Any]] = []
    for record in found:
        reach = record.reaches(base)
        if reach.answer is Answer.DOES_NOT_APPLY:
            continue
        due = record.due()
        standing = record.standing(today, soon_days=soon_days)
        parts = [f"last: {record.last()}", f"next under {due.under}" if due.day else f"next: not on record ({due.under})"]
        if reach.undetermined:
            parts.append(f"whether 5551 reaches it is undetermined: {reach.question()}")
        parts += [f"question: {q}" for q in record.questions(base)]
        if record.note:
            parts.append(record.note)
        rows.append({"name": f"Exterior elevated elements inspection, {record.label}", "authority": AUTHORITY,
                     "rule": f"every {CYCLE_YEARS} years", "note": "; ".join(parts),
                     "next": due.day.isoformat() if due.day else None,
                     "daysLeft": (due.day - today).days if due.day else None, "standing": standing.value,
                     "lastDone": record.inspected_on.isoformat() if record.inspected_on else None, "history": []})
    return rows


# --- for jason applies -----------------------------------------------------------------------------------------------


def building_lines(community: Any, today: date | None = None) -> list[str]:
    """Each building's record as plain lines: what the section's subdivisions say of it, the last inspection, the
    next due day or the question in its place, and what a person must settle."""
    found = records(community)
    lines = ["Exterior elevated elements (Civil Code 5551), by building"]
    if not found:
        lines += [f"  The specification lists no buildings' inspections ({_METHOD}); the obligation row is asked of "
                  "the association as a whole.", ""]
        return lines
    base = base_facts(community)
    questions: list[tuple[str, str]] = []
    for record in found:
        counts = []
        if record.attached_units is not None:
            counts.append(f"{record.attached_units} attached units")
        if record.elements is not None:
            counts.append(f"{record.elements} elevated elements")
        lines.append(f"  {record.label}" + (f" ({', '.join(counts)})" if counts else ""))
        reach = record.reaches(base)
        shown = reach.question() if reach.undetermined else "; ".join(v.describe() for v in reach.deciding)
        lines.append(f"    5551 reaches it: {reach.answer.value}" + (f" ({shown})" if shown else ""))
        for part in (record.units_rule(), record.permit_rule()):
            lines.append(f"    {part.subdivision}: {part.answer.value} ({part.why})")
        lines.append(f"    last inspected: {record.last()}")
        due = record.due()
        if reach.answer is Answer.DOES_NOT_APPLY:
            lines.append("    next due: none asked; the section does not reach it")
        elif due.day is not None:
            standing = record.standing(today) if today else None
            lines.append(f"    next due: {due.day.isoformat()} under {due.under}"
                         + (f" [{standing.value}]" if standing else ""))
        else:
            lines.append(f"    next due: not on record ({due.under})")
        if record.note:
            lines.append(f"    note: {record.note}")
        questions += [(record.label, q) for q in record.questions(base)]
    lines.append("")
    lines.append(f"Questions for a person, by building ({len(questions)})")
    for label, question in questions:
        lines.append(f"  {label}: {question}")
    if not questions:
        lines.append("  none")
    lines.append("")
    return lines


__all__ = [
    "AUTHORITY", "FIRST_DUE", "CYCLE_YEARS", "PERMIT_RULE_FROM", "PERMIT_RULE_YEARS", "MIN_ATTACHED_UNITS",
    "ATTACHED_UNITS_RULE", "InspectorLicense", "Reach", "Due", "ElevatedElementsInspection", "years_after",
    "from_rows", "records", "base_facts", "calendar_rows", "building_lines",
]
