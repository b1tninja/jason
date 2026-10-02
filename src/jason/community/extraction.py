"""Scoring any reader of recorded documents against what the specification pins.

The concept records in ``readings`` are the schema; an ``Extractor`` is
anything that produces a ``DocumentReading`` from a file on disk. The
regex reader is the first one. The pinned facts are the ground truth: the
in-force annexation of each phase and the units its building holds, the
supersessions, and the stamp numbers of the copies whose names carry
them. ``cases`` builds that set from the specification and the record;
``evaluate`` scores an extractor field by field, so a model-backed reader
can be trusted on what it gets right before it is asked about the files
nothing else can read.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from jason.community.readings import DocumentReading, Reader

_PHASE_FILE = re.compile(r"Annexation - Phase (\d+)(?: AMENDED)?\.pdf", re.I)
_NUMBER = re.compile(r"\b((?:19|20)\d{10})\b")


class Extractor(Protocol):
    name: str

    def extract(self, path: Path) -> DocumentReading: ...


class RegexExtractor:
    """The simple parsers over the text extract beside a PDF."""

    name = "regex"

    def extract(self, path: Path) -> DocumentReading:
        text_path = _text_beside(path)
        if text_path is None:
            return Reader().read("", path)
        return Reader().read(text_path.read_text(encoding="utf-8", errors="ignore"), text_path)


def _text_beside(path: Path) -> Path | None:
    """The ``.pdf.md`` or ``.md`` extract for a PDF, or the file itself when it is text."""
    if path.suffix.lower() in (".md", ".txt"):
        return path if path.is_file() else None
    for candidate in (path.with_name(path.name + ".md"), path.with_suffix(".md"), path.with_suffix(".pdf.md")):
        if candidate.is_file():
            return candidate
    return None


@dataclass(frozen=True)
class Case:
    """One file and what the specification says its text must state."""

    path: Path
    number: str = ""
    phase: int | None = None
    first_unit: int | None = None
    last_unit: int | None = None
    association_common_area: int | None = None
    supersedes: tuple[str, ...] = ()
    label: str = ""


@dataclass
class FieldScore:
    hits: int = 0
    misses: int = 0
    wrong: int = 0

    @property
    def total(self) -> int:
        return self.hits + self.misses + self.wrong


@dataclass
class Scorecard:
    extractor: str
    fields: dict[str, FieldScore] = field(default_factory=dict)
    failures: list[dict[str, Any]] = field(default_factory=list)
    cases: int = 0

    def record(self, name: str, expected: Any, actual: Any, case: Case) -> None:
        score = self.fields.setdefault(name, FieldScore())
        if actual in (None, "", (), []):
            score.misses += 1
            self.failures.append({"case": case.path.name, "field": name, "expected": expected, "actual": None})
        elif actual == expected:
            score.hits += 1
        else:
            score.wrong += 1
            self.failures.append({"case": case.path.name, "field": name, "expected": expected, "actual": actual})

    def as_dict(self) -> dict[str, Any]:
        return {
            "extractor": self.extractor,
            "cases": self.cases,
            "fields": {name: {"hits": s.hits, "misses": s.misses, "wrong": s.wrong, "total": s.total} for name, s in self.fields.items()},
            "failures": self.failures,
        }


def cases(community, record, root: Path) -> tuple[Case, ...]:
    """The ground truth from the specification: each pinned annexation file, and each file whose name carries a number.

    An annexation file for phase N must read the in-force annexation's
    number, the phase, the building's unit range under its numbering, the
    A.C.A. number (the building number), and the supersession pinned on it.
    """
    from jason.community.reports import unit_parcels

    folders = (root / "artifacts" / "site-docs" / "governing_documents_Annexations", root / "artifacts" / "site-docs" / "governing_documents", root / "governing")
    reports = {report.phase: report for report in community.public_reports()}
    in_force = {g.phase: g.number for g in record.governing if g.role == "annexation" and g.phase is not None and not g.superseded_by}
    supersessions = {fact.superseded_by: fact.number for fact in community.supersessions()}
    blocks = community.unit_blocks()
    found: list[Case] = []
    for folder in folders:
        if not folder.is_dir():
            continue
        for path in sorted(folder.glob("*.pdf")):
            hit = _PHASE_FILE.match(path.name)
            if hit:
                phase = int(hit.group(1))
                report = reports.get(phase)
                if report is None or "AMENDED" in path.name.upper():
                    continue  # the amended files are the image-only copies; nothing to score yet
                building = int(report.building)
                units = sorted(int(u) for block in blocks if int(block.building) == building for u in range(block.first_unit, block.last_unit + 1))
                number = in_force.get(phase, "")
                found.append(Case(
                    path, number, phase, units[0] if units else None, units[-1] if units else None, building,
                    (supersessions[number],) if number in supersessions else (), f"phase {phase} annexation",
                ))
                continue
            numbers = _NUMBER.findall(path.name)
            if numbers:
                found.append(Case(path, numbers[0], label="numbered file"))
    return tuple(found)


def evaluate(extractor: Extractor, items: tuple[Case, ...]) -> Scorecard:
    card = Scorecard(getattr(extractor, "name", type(extractor).__name__))
    for case in items:
        card.cases += 1
        try:
            reading = extractor.extract(case.path)
        except Exception as exc:  # a reader that cannot open the file scores a miss on every field
            card.failures.append({"case": case.path.name, "field": "extract", "expected": "a reading", "actual": f"{type(exc).__name__}: {exc}"})
            for name in ("number", "phase", "first_unit", "last_unit", "association_common_area", "supersedes"):
                if getattr(case, name) not in (None, "", ()):
                    card.fields.setdefault(name, FieldScore()).misses += 1
            continue
        if case.number:
            card.record("number", case.number, reading.number, case)
        if case.phase is not None:
            card.record("phase", case.phase, reading.phase, case)
        if case.first_unit is not None:
            card.record("first_unit", case.first_unit, reading.annexed.first_unit, case)
        if case.last_unit is not None:
            card.record("last_unit", case.last_unit, reading.annexed.last_unit, case)
        if case.association_common_area is not None:
            aca = reading.annexed.association_common_areas[0] if reading.annexed.association_common_areas else None
            card.record("association_common_area", case.association_common_area, aca, case)
        if case.supersedes:
            card.record("supersedes", list(case.supersedes), sorted(c.number for c in reading.supersedes), case)
    return card
