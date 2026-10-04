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

**The basis is observed** (docs/ingestion-and-review.md, the inventory). ``ModelContext`` counts each read of its
specification, data directory, and date. ``DocumentModel.read`` takes what ``parse`` read as the basis of the record's
fields, and what ``check`` read as the basis of that call's findings. The granularity is the call, not the finding: a
``check`` returns its findings together, so each carries everything that call read, which is an upper bound. A
finding stamped ``text`` only needed nothing but the record; one stamped ``today`` came from a call that read the date,
whether or not that finding used it. What a reader reaches without the context (a module's cache filled by an earlier
call, a clock read directly) is not seen.
"""

from __future__ import annotations

import dataclasses
import functools
import hashlib
import inspect
import re
import sys
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


class Basis(Enum):
    """What a finding, or a record's fields, were drawn from. Text alone is ingestion; anything else is a review."""

    TEXT = "text"        # the document's own text
    PROFILE = "profile"  # the specification (``ModelContext.community``)
    STORE = "store"      # another store on disk (``ModelContext.data_dir``)
    TODAY = "today"      # the date of the reading (``ModelContext.today``)
    LAW = "law"          # a statute or standard (the finding's ``authority``)


def basis_values(basis: Any) -> list[str]:
    """A basis as its words, in the enum's order."""
    return [b.value for b in Basis if b in (basis or ())]


@dataclass(frozen=True)
class Finding:
    code: str            # short kebab-case slug, stable across runs ("minutes-draft", "no-licensed-signer")
    message: str         # one sentence a board member can read
    severity: Severity = Severity.CHECK
    authority: str = ""  # the statute or standard, when one applies ("CIV 5551(c)")
    # What the call that produced the finding read, stamped by ``DocumentModel.read``; empty means not observed. It is
    # no part of the finding's identity: two findings equal before are equal now.
    basis: frozenset[Basis] = field(default=frozenset(), compare=False)

    def __post_init__(self) -> None:
        if not isinstance(self.basis, frozenset):
            object.__setattr__(self, "basis", frozenset(self.basis or ()))

    def as_dict(self) -> dict[str, Any]:
        out = {"code": self.code, "message": self.message, "severity": self.severity.value, "authority": self.authority}
        if self.basis:
            out["basis"] = basis_values(self.basis)
        return out


# The parts of a context whose reading is a basis. The file's own name, its library period, and its confidential flag
# are not counted: they describe the file being read.
_PARTS = {"community": Basis.PROFILE, "data_dir": Basis.STORE, "today": Basis.TODAY}


@dataclass
class ModelContext:
    """What a check may consult besides the record: the specification, the data directory (disk only), today, the
    file's own name and library period, and whether the library holds it as confidential.

    The context counts each read of ``community``, ``data_dir``, and ``today``, whatever the value (a ``None``
    specification that a reader asks for is still asked for). ``mark`` takes the counts and ``since`` names the parts
    read after a mark, so a caller can tell what one call read. The attributes return what they always did."""

    community: Any = None
    data_dir: Path | None = None
    today: date = field(default_factory=date.today)
    name: str = ""
    period: str = ""
    confidential: bool = False

    def __getattribute__(self, name: str) -> Any:
        part = _PARTS.get(name)
        if part is not None:
            reads = object.__getattribute__(self, "__dict__").setdefault("_reads", {})
            reads[part] = reads.get(part, 0) + 1
        return object.__getattribute__(self, name)

    def mark(self) -> dict[Basis, int]:
        """The read counts now, to give to ``since`` later."""
        return dict(object.__getattribute__(self, "__dict__").get("_reads") or {})

    def since(self, mark: dict[Basis, int] | None = None) -> frozenset[Basis]:
        """The parts read after ``mark`` (with no mark, since the context was made)."""
        mark = mark or {}
        return frozenset(part for part, n in self.mark().items() if n > mark.get(part, 0))


def _mark(context: Any) -> dict[Basis, int] | None:
    take = getattr(context, "mark", None)
    return take() if callable(take) else None


def _since(context: Any, mark: dict[Basis, int] | None) -> frozenset[Basis] | None:
    """What ``context`` read after ``mark``; None when it does not record (a stand-in that is no ``ModelContext``)."""
    return context.since(mark) if mark is not None and callable(getattr(context, "since", None)) else None


def _stamp(finding: Finding, read: frozenset[Basis] | None) -> Finding:
    """``finding`` with the text, what its call read, and the law when it cites one added to its basis."""
    if read is None:
        return finding
    basis = finding.basis | {Basis.TEXT} | read | ({Basis.LAW} if finding.authority else frozenset())
    return finding if basis == finding.basis else dataclasses.replace(finding, basis=basis)


@dataclass
class ModelReading:
    kind: DocumentKind
    model: str
    record: Any
    missing: tuple[str, ...]
    findings: tuple[Finding, ...]
    fields_basis: frozenset[Basis] = frozenset()  # what ``parse`` read to fill the record; empty means not observed
    version: str = ""                             # ``reader_version`` of the model that read it
    mark: dict[Basis, int] | None = field(default=None, repr=False, compare=False)  # the context's counts when the read ended

    @property
    def complete(self) -> bool:
        return not self.missing

    def as_dict(self) -> dict[str, Any]:
        out = {"kind": self.kind.value, "model": self.model, "complete": self.complete, "missing": list(self.missing),
               "fields": to_plain(self.record), "findings": [f.as_dict() for f in self.findings]}
        if self.version:
            out["version"] = self.version
        if self.fields_basis:
            out["fieldsBasis"] = basis_values(self.fields_basis)
        return out


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
        start = _mark(context)
        record = self.parse(text, context)
        if record is None:
            return None
        parsed = _since(context, start)
        missing = tuple(f for f in self.required if _empty(getattr(record, f, None)))
        # A missing field's finding comes from the record alone, so its basis is the fields' own.
        findings = [_stamp(Finding("missing-" + f.replace("_", "-"), f"the text gives no {f.replace('_', ' ')}", Severity.CHECK), parsed)
                    for f in missing]
        before = _mark(context)
        checked = self.check(record, context)
        # One basis for the whole call: ``check`` returns its findings together, so which read served which finding
        # is not observable. Each finding carries everything the call read.
        read = _since(context, before)
        findings += [_stamp(f, read) for f in checked]
        fields = frozenset() if parsed is None else frozenset({Basis.TEXT}) | parsed
        return ModelReading(kind or self.handles()[0], self.name or type(self).__name__, record, missing, tuple(findings),
                            fields, reader_version(self), _mark(context))


def reader_version(model: DocumentModel | type) -> str:
    """A reader's version: the first twelve hex digits of the SHA-256 of its source, taken over every module in its
    class's line of descent (the reader's own module, its base readers' and mixins', and this one, which holds ``read``
    and the shared text helpers). It changes when any of those files changes, with no constant to remember. It does not
    see a helper module the reader only calls into; "" means the source could not be read."""
    return _class_version(model if isinstance(model, type) else type(model))


@functools.lru_cache(maxsize=None)
def _class_version(cls: type) -> str:
    digest = hashlib.sha256()
    for name in sorted({c.__module__ for c in cls.__mro__ if c is not object}):
        try:
            source = inspect.getsource(sys.modules[name])
        except (KeyError, OSError, TypeError):
            return ""
        digest.update(name.encode("utf-8") + b"\0" + source.replace("\r\n", "\n").encode("utf-8") + b"\0")
    return digest.hexdigest()[:12]


def settle(reading: ModelReading, context: Any, start: dict[Basis, int] | None) -> ModelReading:
    """Finish a reading's basis after a model's own ``read`` returned; ``start`` is the context's mark before it.

    A reader that overrides ``read`` may consult the context, rewrite findings, or add some after the base ``read``
    stamped them. What it read then is added to every finding, since it could have rewritten any of them. A finding it
    built itself carries everything the whole read touched, and so do the fields of a reading the base ``read`` never
    stamped."""
    whole = _since(context, start)
    if whole is None:
        return reading
    late = _since(context, reading.mark) if reading.mark is not None else whole
    reading.findings = tuple(_stamp(f, late if f.basis else whole) for f in reading.findings)
    if not reading.fields_basis:
        reading.fields_basis = frozenset({Basis.TEXT}) | whole
    reading.mark = _mark(context)
    return reading


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
        start = _mark(context)
        reading = model.read(text, context, kind)
        if reading is not None:
            return settle(reading, context, start)
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


__all__ = ["Severity", "Basis", "basis_values", "Finding", "ModelContext", "ModelReading", "DocumentModel", "reader_version", "settle",
           "REGISTRY", "register", "models_for", "read", "modeled_kinds", "to_plain", "squash", "first", "cents", "amount_after",
           "dates_in", "date_after"]
