"""Document models: one reader per document kind that turns a file's text into a typed record and the findings on it.

A ``DocumentKind`` says what a file is; a ``DocumentModel`` says what is in it. A model reads the text jason already
keeps for a file (the library's text cache, OCR included) into a dataclass record of the facts that kind carries: a
meeting's date and motions, a policy's term and limits, an SB 326 report's inspection date and licensed signer. Its
``check`` then turns the record into ``Finding`` rows: a fact missing that the kind always carries, and, for a record
the law shapes, what the statute asks of it (minutes within thirty days, CIV 4950; a balcony report stamped by a
licensed architect or engineer, CIV 5551). A finding is a lead for a person, never a determination.

Models register by kind (``register``). A kind may have several, most specific first: a vendor's invoice layout before
the general invoice. ``read`` tries them in order and returns the first reading that recognizes the text. A model that
does not recognize a text returns ``None`` from ``parse``; a miss stays a miss.

Nothing here reads a file, calls a service, or pins a fact: the runner (``jason.tasks.document_models``) supplies the
text and stores the readings, and a reading is evidence, not a pin.
"""

from __future__ import annotations

import dataclasses
import re
from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from pathlib import Path
from typing import Any, ClassVar

from jason.community.symbols import DocumentKind


class Severity(Enum):
    INFO = "info"        # worth knowing (a term ends next month)
    CHECK = "check"      # a person should look (a signature line is blank in the text)
    PROBLEM = "problem"  # the document falls short of what the kind or the statute requires


@dataclass(frozen=True)
class Finding:
    code: str            # short kebab-case slug, stable across runs ("minutes-draft", "no-licensed-signer")
    message: str         # one sentence a board member can read
    severity: Severity = Severity.CHECK
    authority: str = ""  # the statute or standard, when one applies ("CIV 5551(c)")

    def as_dict(self) -> dict[str, Any]:
        return {"code": self.code, "message": self.message, "severity": self.severity.value, "authority": self.authority}


@dataclass
class ModelContext:
    """What a check may consult besides the record: the specification, the data directory (disk only), today, the
    file's own name and library period, and whether the library holds it as confidential."""

    community: Any = None
    data_dir: Path | None = None
    today: date = field(default_factory=date.today)
    name: str = ""
    period: str = ""
    confidential: bool = False


@dataclass
class ModelReading:
    kind: DocumentKind
    model: str
    record: Any
    missing: tuple[str, ...]
    findings: tuple[Finding, ...]

    @property
    def complete(self) -> bool:
        return not self.missing

    def as_dict(self) -> dict[str, Any]:
        return {"kind": self.kind.value, "model": self.model, "complete": self.complete, "missing": list(self.missing),
                "fields": to_plain(self.record), "findings": [f.as_dict() for f in self.findings]}


class DocumentModel:
    """One kind's reader. Subclasses set ``kind`` (or ``kinds``), ``name``, and ``required`` (the record's fields the
    kind always carries), and implement ``parse``; ``check`` is optional."""

    kind: ClassVar[DocumentKind | None] = None
    kinds: ClassVar[tuple[DocumentKind, ...]] = ()
    name: ClassVar[str] = ""
    required: ClassVar[tuple[str, ...]] = ()

    def handles(self) -> tuple[DocumentKind, ...]:
        return self.kinds or ((self.kind,) if self.kind else ())

    def parse(self, text: str, context: ModelContext) -> Any | None:
        """The record, or None when the text is not this model's."""
        raise NotImplementedError

    def check(self, record: Any, context: ModelContext) -> list[Finding]:
        return []

    def read(self, text: str, context: ModelContext, kind: DocumentKind | None = None) -> ModelReading | None:
        record = self.parse(text, context)
        if record is None:
            return None
        missing = tuple(f for f in self.required if _empty(getattr(record, f, None)))
        findings = [Finding("missing-" + f.replace("_", "-"), f"the text gives no {f.replace('_', ' ')}", Severity.CHECK) for f in missing]
        findings += self.check(record, context)
        return ModelReading(kind or self.handles()[0], self.name or type(self).__name__, record, missing, tuple(findings))


REGISTRY: dict[DocumentKind, list[DocumentModel]] = {}


def register(model: DocumentModel, *, first: bool = False) -> DocumentModel:
    """Add a model for its kinds; a model registered earlier is tried first, unless ``first`` puts this one ahead of all
    (a reader for one carrier's layout ahead of the general reader another module registered sooner)."""
    for kind in model.handles():
        models = REGISTRY.setdefault(kind, [])
        models.insert(0, model) if first else models.append(model)
    return model


def models_for(kind: DocumentKind) -> list[DocumentModel]:
    _load()
    return list(REGISTRY.get(kind, ()))


def read(kind: DocumentKind, text: str, context: ModelContext | None = None) -> ModelReading | None:
    """The first registered model for ``kind`` that recognizes the text."""
    context = context or ModelContext()
    for model in models_for(kind):
        reading = model.read(text, context, kind)
        if reading is not None:
            return reading
    return None


def modeled_kinds() -> tuple[DocumentKind, ...]:
    _load()
    return tuple(k for k in DocumentKind if REGISTRY.get(k))


_LOADED = False


def _load() -> None:
    """Import the model modules once, so each registers itself."""
    global _LOADED
    if not _LOADED:
        _LOADED = True
        import jason.community.models  # noqa: F401


def _empty(value: Any) -> bool:
    return value is None or value == "" or value == () or value == [] or value == {}


def to_plain(value: Any) -> Any:
    """A record as JSON-ready values: dates as ISO strings, enums as their values, dataclasses as dicts."""
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {f.name: to_plain(getattr(value, f.name)) for f in dataclasses.fields(value)}
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, (list, tuple)):
        return [to_plain(v) for v in value]
    if isinstance(value, dict):
        return {str(k): to_plain(v) for k, v in value.items()}
    return value


# Shared text helpers. Amounts are integer cents.

_WS = re.compile(r"\s+")


def squash(text: str) -> str:
    """The text on one line with single spaces, for patterns that cross the extract's line breaks."""
    return _WS.sub(" ", text or "").strip()


def first(pattern: str | re.Pattern, text: str, group: int = 1, flags: int = re.I) -> str:
    m = (pattern if isinstance(pattern, re.Pattern) else re.compile(pattern, flags)).search(text or "")
    return squash(m.group(group)) if m else ""


def cents(text: str) -> int | None:
    """The first amount in ``text`` ("$1,234.56", "1,234.56", "(12.00)") as cents, or None."""
    m = re.search(r"(\()?-?\$?\s?(\d{1,3}(?:,\d{3})+|\d+)(?:\.(\d\d))?(\))?", text or "")
    if not m:
        return None
    value = int(m.group(2).replace(",", "")) * 100 + int(m.group(3) or 0)
    return -value if m.group(1) and m.group(4) else value


def amount_after(label: str, text: str, *, window: int = 80) -> int | None:
    """The first dollar amount within ``window`` characters after ``label`` (a regex), as cents."""
    m = re.search(label, text or "", re.I)
    if not m:
        return None
    tail = (text or "")[m.end(): m.end() + window]
    money = re.search(r"\(?-?\$?\s?(?:\d{1,3}(?:,\d{3})+|\d+)\.\d\d\)?", tail)
    return cents(money.group(0)) if money else None


def dates_in(text: str) -> list[date]:
    """Every date the text writes as 11/17/2023, 2023-11-17, 11-17-2023, or November 17, 2023, in order."""
    from jason.community.invoices import parse_date

    found = []
    pattern = re.compile(r"\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}-\d{2}-\d{2}|(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)"
                         r"[a-z]*\.? \d{1,2},? \d{4})\b", re.I)
    for m in pattern.finditer(text or ""):
        d = parse_date(m.group(1))
        if d:
            found.append(d)
    return found


def date_after(label: str, text: str, *, window: int = 60) -> date | None:
    m = re.search(label, text or "", re.I)
    if not m:
        return None
    found = dates_in((text or "")[m.end(): m.end() + window])
    return found[0] if found else None


__all__ = ["Severity", "Finding", "ModelContext", "ModelReading", "DocumentModel", "REGISTRY", "register", "models_for", "read",
           "modeled_kinds", "to_plain", "squash", "first", "cents", "amount_after", "dates_in", "date_after"]
