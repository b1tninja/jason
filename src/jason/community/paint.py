"""A paint schedule: which color goes on which surface, and how it is checked against the maker's catalog.

A community's exterior color palette (the developer's "Exterior Color and Materials Palette", an architectural review
committee's approved list) is a table of surfaces against schemes. The profile holds the rows
(``Community.paint_schedules()``); this module holds the records and the checks. It makes no HTTP call: the catalog
comes from a reader (``jason.sources.sherwin_williams``) and is handed in.

A schedule row is the association's record of what it approved. The maker's catalog can move under it (a color renamed
or discontinued), so the check reports the drift and never edits the row: the number governs, and the board decides.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable, Protocol


class Maker(Enum):
    SHERWIN_WILLIAMS = "sherwin-williams"
    OTHER = "other"


class Surface(Enum):
    FASCIA = "fascia"
    TRIM = "trim"
    FIELD = "field"
    ENTRY_DOORS = "entry doors"
    GARAGE_DOORS = "garage doors"
    WINDOWS = "windows"
    RAILINGS = "railings"
    ROOF = "roof"
    OTHER = "other"


@dataclass(frozen=True)
class PaintSpec:
    """One color in one scheme, as the schedule printed it. ``name`` is the printed name, which may no longer be the
    maker's."""

    scheme: int
    code: str
    name: str
    maker: Maker = Maker.SHERWIN_WILLIAMS


@dataclass(frozen=True)
class PaintRow:
    """A surface and the color it takes in each scheme. ``label`` is the schedule's own wording ("STUCCO TRIM")."""

    surface: Surface
    label: str
    specs: tuple[PaintSpec, ...]
    note: str = ""

    def spec(self, scheme: int) -> PaintSpec | None:
        return next((s for s in self.specs if s.scheme == scheme), None)


@dataclass(frozen=True)
class PaintSchedule:
    """One schedule: its title, where the original is, and its rows. ``source`` names the document (a Drive id or a
    path in the library), ``prepared`` who made it and when, as the document says."""

    title: str
    rows: tuple[PaintRow, ...]
    source: str = ""
    prepared: str = ""
    buildings: tuple[str, ...] = ()
    schemes: tuple[int, ...] = field(default=())

    def scheme_numbers(self) -> tuple[int, ...]:
        return self.schemes or tuple(sorted({s.scheme for r in self.rows for s in r.specs}))

    def specs(self) -> tuple[tuple[PaintRow, PaintSpec], ...]:
        return tuple((r, s) for r in self.rows for s in r.specs)

    def surface(self, surface: Surface | str) -> tuple[PaintRow, ...]:
        key = surface.value if isinstance(surface, Surface) else surface.lower()
        return tuple(r for r in self.rows if r.surface.value == key or r.label.lower() == key)


class FindingKind(Enum):
    OK = "ok"
    RENAMED = "renamed"
    ARCHIVED = "archived"
    NOT_FOUND = "not found"
    NOT_CHECKED = "not checked"


@dataclass(frozen=True)
class PaintFinding:
    surface: str
    scheme: int
    code: str
    printed_name: str
    kind: FindingKind
    catalog_name: str = ""
    hex: str = ""
    lrv: float | None = None
    exterior: bool | None = None

    @property
    def needs_a_person(self) -> bool:
        return self.kind not in (FindingKind.OK, FindingKind.NOT_CHECKED)


class Catalog(Protocol):
    def color(self, number: str): ...


_SPELLING = (("grey", "gray"),)


def name_key(name: str) -> str:
    """A color name for comparison: case, spacing, and punctuation do not distinguish it, and "grey" is "gray"."""
    text = name.lower()
    for old, new in _SPELLING:
        text = text.replace(old, new)
    return re.sub(r"[^a-z0-9]", "", text)


def check(schedule: PaintSchedule, catalog: Catalog) -> tuple[PaintFinding, ...]:
    """Each color on the schedule against the catalog: found under the same name, renamed, discontinued, or not there.
    A color from another maker is not checked."""
    found: list[PaintFinding] = []
    for row, spec in schedule.specs():
        base = dict(surface=row.label, scheme=spec.scheme, code=spec.code, printed_name=spec.name)
        if spec.maker is not Maker.SHERWIN_WILLIAMS:
            found.append(PaintFinding(**base, kind=FindingKind.NOT_CHECKED))
            continue
        color = catalog.color(spec.code)
        if color is None:
            found.append(PaintFinding(**base, kind=FindingKind.NOT_FOUND))
            continue
        kind = FindingKind.OK
        if color.archived:
            kind = FindingKind.ARCHIVED
        elif name_key(color.name) != name_key(spec.name):
            kind = FindingKind.RENAMED
        found.append(
            PaintFinding(**base, kind=kind, catalog_name=color.name, hex=color.hex, lrv=color.lrv, exterior=color.exterior)
        )
    return tuple(found)


def distinct_codes(schedules: Iterable[PaintSchedule]) -> tuple[str, ...]:
    """Every Sherwin-Williams number across the schedules, once each, in the order first printed."""
    seen: dict[str, None] = {}
    for schedule in schedules:
        for _, spec in schedule.specs():
            if spec.maker is Maker.SHERWIN_WILLIAMS:
                seen.setdefault(spec.code)
    return tuple(seen)
