"""Which statutes a document cites, and whether Jason holds their words.

A document that cites a section hands Jason a question: are that section's words on the authorities shelf, so a
reading of the document can be checked against them? ``survey`` reads each text with the citation grammar
(``jason.community.references.extract``), groups what it finds by section, and gives each one a standing:

- ``ON_SHELF``: a page under ``data/authorities`` holds it (the manifest lists each page's sections).
- ``NOT_EXPORTED``: lawlibrary holds it and the shelf does not. This is the gap: ``proposal`` writes the citations in
  the form a duty's ``sections`` string takes (``GOV 66427, 66428; BPC 11010.4``), for a person to add as a row in
  ``jason.community.authorities``. Nothing is added by this module.
- ``NOT_FOUND``: the current publication has no such section: lawlibrary has none, or a page the shelf holds spans its
  number without it. A section the document got wrong, one since
  repealed, or a reading error; a person looks.
- ``RENUMBERED``: a pre-2014 Davis-Stirling number (1350 to 1378). Its successor is a question for
  ``jason statute-align``, not for this module.
- ``REGULATION``: a Title 10 or other regulation. The shelf holds some sections; the rest are read from the
  Department's PDF.
- ``OTHER_CODE``: a code lawlibrary does not hold (a fire or building code, a city code).
- ``UNCHECKED``: not on the shelf, and lawlibrary was not asked or could not be reached.

A range (``Sections 10000-10580``) is read as its two ends: the grammar finds what is written. The grammar is the
citation grammar's, so a citation it misses stays missed; this reports on what it found and never says a document
cites nothing else. ``external`` is for a guide or manual rather than one of the association's documents (see
``extract``).
"""

from __future__ import annotations

import json
import re
from bisect import bisect_right
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from jason.community.authorities import LAWLIBRARY_CODES, number_key
from jason.community.outlines import outline_from_text
from jason.community.references import TargetKind, extract, statute_key

_PAGE = re.compile(r"<<PAGE (\d+)>>")
_TARGET = re.compile(r"^(?P<code>\d+ CCR|[A-Z]+)\s+(?P<number>\d[\d.]*)")


class Standing(Enum):
    ON_SHELF = "on the authorities shelf"
    NOT_EXPORTED = "in the law, not exported"
    NOT_FOUND = "not in the current publication"
    RENUMBERED = "a pre-2014 Davis-Stirling number"
    REGULATION = "a regulation not on the shelf"
    OTHER_CODE = "a code lawlibrary does not hold"
    UNCHECKED = "not checked against lawlibrary"


@dataclass
class Cited:
    code: str
    section: str
    standing: Standing = Standing.UNCHECKED
    mentions: int = 0
    sources: list[str] = field(default_factory=list)
    subdivisions: set[str] = field(default_factory=set)
    quote: str = ""
    page: str = ""                  # the first page it appears on, when the text carries ``<<PAGE n>>`` markers

    @property
    def citation(self) -> str:
        return f"{self.code} {self.section}"

    def as_dict(self) -> dict[str, Any]:
        return {"citation": self.citation, "standing": self.standing.name, "mentions": self.mentions, "sources": self.sources,
                "subdivisions": sorted(self.subdivisions), "quote": self.quote, "page": self.page}


@dataclass
class Survey:
    rows: list[Cited] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    law_checked: bool = False

    def of(self, standing: Standing) -> list[Cited]:
        return [r for r in self.rows if r.standing is standing]

    def counts(self) -> dict[str, int]:
        found: dict[str, int] = {}
        for row in self.rows:
            found[row.standing.name] = found.get(row.standing.name, 0) + 1
        return found

    def gaps(self) -> list[Cited]:
        return self.of(Standing.NOT_EXPORTED)

    def proposal(self) -> str:
        """The gaps as a duty's ``sections`` string: ``"BPC 11010.4, 11010.35; GOV 66427"``, each code's numbers in order."""
        by_code: dict[str, list[str]] = defaultdict(list)
        for row in self.gaps():
            by_code[row.code].append(row.section)
        return "; ".join(f"{code} " + ", ".join(sorted(set(nums), key=number_key)) for code, nums in sorted(by_code.items()))

    def as_dict(self) -> dict[str, Any]:
        return {"lawChecked": self.law_checked, "counts": self.counts(), "proposal": self.proposal(), "notes": self.notes,
                "cited": [r.as_dict() for r in self.rows]}

    def lines(self, limit: int = 12) -> list[str]:
        if not self.rows:
            return ["no statute cited"]
        counts = self.counts()
        out = [f"{len(self.rows)} sections cited: " + ", ".join(f"{Standing[k].value} {v}" for k, v in counts.items())]
        if not self.law_checked and counts.get(Standing.UNCHECKED.name):
            out.append("lawlibrary was not asked, so what is off the shelf is unchecked")
        for standing in (Standing.NOT_EXPORTED, Standing.NOT_FOUND, Standing.RENUMBERED):
            rows = self.of(standing)
            if rows:
                shown = ", ".join(r.citation for r in rows[:limit]) + (f" and {len(rows) - limit} more" if len(rows) > limit else "")
                out.append(f"{standing.value}: {shown}")
        if self.gaps():
            out.append(f"to add to the shelf: {self.proposal()}")
        return out

    def markdown(self, heading: str = "Statutes cited", level: int = 2) -> str:
        hashes = "#" * level
        out = [f"{hashes} {heading}", ""]
        if not self.rows:
            return "\n".join(out + ["No statute cited.", ""])
        out += ["| Standing | Sections |", "| --- | ---: |"] + [f"| {Standing[k].value} | {v} |" for k, v in self.counts().items()] + [""]
        if not self.law_checked and self.of(Standing.UNCHECKED):
            out += ["lawlibrary was not asked, so what is off the shelf is unchecked.", ""]
        if self.gaps():
            out += ["To add to the shelf (a person adds the row in `jason.community.authorities`; nothing is added here):", "",
                    f"    {self.proposal()}", ""]
        for standing in (Standing.NOT_FOUND, Standing.RENUMBERED, Standing.NOT_EXPORTED, Standing.REGULATION, Standing.OTHER_CODE):
            rows = self.of(standing)
            if not rows:
                continue
            out += [f"{standing.value} ({len(rows)}):", ""]
            for r in rows:
                where = (f", page {r.page}" if r.page else "") + (f", cited {r.mentions} times" if r.mentions > 1 else "")
                out.append(f"- {r.citation}{where}: \"{' '.join(r.quote.split())[:160]}\"")
            out.append("")
        return "\n".join(out)


def shelf_spans(root: Path) -> list[tuple[str, str, str, frozenset[str]]]:
    """(code, first, last, sections) of each page the authorities shelf holds: the curated pages and the ones a reader's miss
    brought down on demand (``statute_fetch``), as the shelf's own reader counts both. The exporter owns the manifest
    (``export_authorities.read_manifest``); this only reads what it wrote. None without one."""
    from jason.tasks.export_authorities import read_manifest

    manifest = read_manifest(Path(root))
    pages = [*(manifest.get("pages") or []), *(manifest.get("on_demand") or [])]
    return [(str(p["code"]), str(p["start"]), str(p["end"]), frozenset(str(n) for n in p.get("sections") or ())) for p in pages if p.get("code")]


# --- Saved surveys ----------------------------------------------------------------------------------------------------
# A survey made with lawlibrary is kept under data/citations so a reader that does not call lawlibrary (jason-mcp) can
# report it. Each file is one source's survey and says when it was made; nothing else reads or writes the folder.

CITATIONS_DIR = "citations"


def _slug(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "-", name).strip("-").lower()[:80] or "survey"


def save(root: Path, name: str, result: Survey, *, kind: str = "reference") -> Path:
    """Keep ``result`` as ``data/citations/<kind>-<name>.json``."""
    from datetime import date

    folder = Path(root) / CITATIONS_DIR
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{kind}-{_slug(name)}.json"
    path.write_text(json.dumps({"name": name, "kind": kind, "made": date.today().isoformat(), **result.as_dict()}, indent=1), encoding="utf-8")
    return path


def from_dict(raw: dict[str, Any], root: Path | None = None) -> Survey:
    """A survey as ``Survey.as_dict`` wrote it. With ``root``, a section that was off the shelf, or not found in a page's
    range, when the survey was made is placed again against the manifest as it is now: the shelf grows and a saved survey
    must not keep calling a section a gap after it has been exported."""
    spans = shelf_spans(root) if root is not None else []
    rows: list[Cited] = []
    for r in raw.get("cited") or []:
        code, _, section = str(r["citation"]).rpartition(" ")
        row = Cited(code, section, Standing[r["standing"]], int(r.get("mentions") or 0), list(r.get("sources") or []),
                    set(r.get("subdivisions") or ()), str(r.get("quote") or ""), str(r.get("page") or ""))
        if spans and row.standing in (Standing.NOT_EXPORTED, Standing.NOT_FOUND, Standing.UNCHECKED):
            if _shelf_standing(spans, code, section) is Standing.ON_SHELF:
                row.standing = Standing.ON_SHELF
        rows.append(row)
    return Survey(rows, list(raw.get("notes") or []), bool(raw.get("lawChecked")))


# The most telling standing wins when surveys of different sources disagree; an unchecked one tells least.
_PRECEDENCE = (Standing.NOT_FOUND, Standing.NOT_EXPORTED, Standing.RENUMBERED, Standing.REGULATION, Standing.OTHER_CODE,
               Standing.ON_SHELF, Standing.UNCHECKED)


def merge(surveys: list[Survey]) -> Survey:
    """One survey over several: a section once, its mentions added and every source that cites it named."""
    rows: dict[str, Cited] = {}
    for one in surveys:
        for row in one.rows:
            held = rows.get(row.citation)
            if held is None:
                rows[row.citation] = Cited(row.code, row.section, row.standing, row.mentions, list(row.sources),
                                           set(row.subdivisions), row.quote, row.page)
                continue
            held.mentions += row.mentions
            held.sources += [s for s in row.sources if s not in held.sources]
            held.subdivisions |= row.subdivisions
            if _PRECEDENCE.index(row.standing) < _PRECEDENCE.index(held.standing):
                held.standing = row.standing
    ordered = sorted(rows.values(), key=lambda r: (r.code, number_key(r.section)))
    return Survey(ordered, [n for one in surveys for n in one.notes], any(one.law_checked for one in surveys))


def saved(root: Path) -> list[dict[str, Any]]:
    """Every saved survey, newest first; one that cannot be read is left out."""
    found: list[dict[str, Any]] = []
    for path in sorted((Path(root) / CITATIONS_DIR).glob("*.json")):
        try:
            found.append(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            continue
    return sorted(found, key=lambda s: str(s.get("made") or ""), reverse=True)


def _shelf_standing(spans: list[tuple[str, str, str, frozenset[str]]], code: str, number: str) -> Standing | None:
    """ON_SHELF when a page holds the section, NOT_FOUND when a page's range takes in its number and the page lacks it
    (so the shelf's own text shows there is no such section), else None: the shelf says nothing."""
    key = number_key(number)
    inside = [(sections, a) for c, a, b, sections in spans if c == code and number_key(a) <= key <= number_key(b)]
    if not inside:
        return None
    return Standing.ON_SHELF if any(number in sections or not sections for sections, _ in inside) else Standing.NOT_FOUND


def _section_of(target: str) -> tuple[str, str] | None:
    base, _ = statute_key(target)
    found = _TARGET.match(base)
    return (found.group("code"), found.group("number")) if found else None


def cited(sources: dict[str, str], *, external: bool = False) -> tuple[list[Cited], list[str]]:
    """The sections each text cites, one row per section, with how often and where. A text the grammar cannot read is noted."""
    rows: dict[tuple[str, str], Cited] = {}
    notes: list[str] = []
    for key, text in sources.items():
        if not text:
            continue
        try:
            outline = outline_from_text(text, key=key, title=key)
            refs = [r for r in extract(outline, {}, external=external) if r.kind is TargetKind.STATUTE]
        except Exception as exc:  # noqa: BLE001 - one unreadable text must not stop the survey of the rest
            notes.append(f"{key}: citations not read ({exc})")
            continue
        marks = [(m.start(), m.group(1)) for m in _PAGE.finditer(outline.text)]
        starts = [s for s, _ in marks]
        for ref in refs:
            split = _section_of(ref.target)
            if split is None:
                continue
            code, number = split
            row = rows.setdefault((code, number), Cited(code, number))
            row.mentions += 1
            if key not in row.sources:
                row.sources.append(key)
            subs = statute_key(ref.target)[1]
            if subs:
                row.subdivisions.add(subs)
            if ref.prior:
                row.standing = Standing.RENUMBERED
            if not row.quote:
                row.quote = ref.quote
                row.page = marks[bisect_right(starts, ref.offset) - 1][1] if marks and starts[0] <= ref.offset else ""
    return sorted(rows.values(), key=lambda r: (r.code, number_key(r.section))), notes


def survey(sources: dict[str, str], root: Path, *, library: Any = None, external: bool = False) -> Survey:
    """Read ``sources`` (key to text), and place each cited section against the shelf under ``root`` and, when ``library``
    is a lawlibrary, against the current publication. Without one, a section off the shelf is ``UNCHECKED``."""
    rows, notes = cited(sources, external=external)
    result = Survey(rows, notes)
    spans = shelf_spans(root)
    ask: list[Cited] = []
    for row in rows:
        if row.standing is Standing.RENUMBERED:
            continue
        if row.code.endswith("CCR"):
            row.standing = _shelf_standing(spans, row.code, row.section) or Standing.REGULATION
        elif row.code not in LAWLIBRARY_CODES:
            row.standing = Standing.OTHER_CODE
        elif (held := _shelf_standing(spans, row.code, row.section)) is not None:
            row.standing = held
        else:
            ask.append(row)
    if ask and library is not None:
        try:
            texts = library.spans([(r.code, r.section, r.section) for r in ask])
            for row, span in zip(ask, texts):
                row.standing = Standing.NOT_EXPORTED if span.found else Standing.NOT_FOUND
            result.law_checked = True
        except Exception as exc:  # noqa: BLE001 - lawlibrary missing or its worker failed: leave them unchecked, and say so
            result.notes.append(f"lawlibrary was not reached ({exc})")
    return result


__all__ = ["Standing", "Cited", "Survey", "survey", "cited", "shelf_spans", "save", "saved", "from_dict", "merge"]
