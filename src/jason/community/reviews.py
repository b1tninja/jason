"""Reviews: a lens applied to what a reader found (docs/ingestion-and-review.md, step 2).

A reading says what a document says. A **review** judges that against something outside the document: a date, the
specification, another record, the law. A ``Lens`` is one reusable way to judge; a ``Review`` is one lens applied to one
document's stored fields. The first lens is ``AS_OF``, "as of a date": which terms have ended, which deadlines have
passed, what is due next.

**A lens check is a row.** ``@AS_OF.check(key, Record, fields=(...))`` registers a function
``(fields, as_of, facts) -> findings``. It is given only the record's fields it names, rebuilt from their stored
(JSON) form by the record's own type hints, and the date. A check that needs the specification names a ``facts``
function ``(fields, community) -> facts``; it gets those facts and never the specification itself. So a review is a
function of three things, each with a digest: the fields it read, the facts it read, and the date. It never reads a
store, and it can be made again from a stored reading without reading the document again.

**A reader says where a lens's findings go.** A reader lists its checks in ``lens_checks`` and may return a check
from ``check`` among its findings, as a slot: ``DocumentModel.read`` puts that check's findings there. A check with no
slot goes last. A reading's findings therefore keep the order they always had, and each finding from a lens carries the
lens's key.

**The key.** A review is keyed by its document, the digest of the text read, the lens, the lens's version, and the
as-of date. With the same key, the same fields, and the same facts, the stored review stands and is not made again
(``Lens.review`` with ``known``). The lens's version is a hash of its source: this module and every module that
registers one of its checks.

Nothing here reads a file. ``jason.tasks.document_reviews`` keeps the store.
"""

from __future__ import annotations

import dataclasses
import hashlib
import inspect
import json
import sys
import types
import typing
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Any, Callable, Iterable, Mapping, Sequence

from jason.community.document_models import Basis, Finding, Severity, to_plain
from jason.community.symbols import DocumentKind

RULE = "rule"   # who made a review: a rule (a check function); a grammar or a model later


# ---------------------------------------------------------------------------------------------------------------
# The stored form of a record, and the way back


def stored(record: Any) -> dict[str, Any]:
    """A record's fields exactly as a stored row holds them: ``to_plain``, then through JSON."""
    plain = record if isinstance(record, dict) else to_plain(record)
    return json.loads(json.dumps(plain, default=str))


def digest(value: Any) -> str:
    """A short digest of a JSON-ready value (sixteen hex digits of its SHA-256, keys sorted)."""
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str, separators=(",", ":")).encode("utf-8")).hexdigest()[:16]


_HINTS: dict[type, dict[str, Any]] = {}


def hints(cls: type) -> dict[str, Any]:
    """A record class's field types; empty when they cannot be resolved (the values then stay as stored)."""
    if cls not in _HINTS:
        try:
            _HINTS[cls] = typing.get_type_hints(cls)
        except Exception:  # a name only imported for type checking
            _HINTS[cls] = {}
    return _HINTS[cls]


def hydrate(value: Any, hint: Any) -> Any:
    """A stored (JSON) value as the type its field declares: an ISO string as a date, a value as its enum member, a dict
    as its dataclass, a list as a tuple of the same. A value that does not fit the type is returned as stored."""
    if value is None or hint is None or hint is Any:
        return value
    origin = typing.get_origin(hint)
    if origin is typing.Union or origin is types.UnionType:
        for arm in typing.get_args(hint):
            if arm is type(None):
                continue
            out = hydrate(value, arm)
            if out is not value:
                return out
        return value
    if origin in (tuple, list, set, frozenset):
        if not isinstance(value, (list, tuple)):
            return value
        args = typing.get_args(hint)
        if origin is tuple and args and not (len(args) == 2 and args[1] is Ellipsis):
            return tuple(hydrate(v, args[i] if i < len(args) else Any) for i, v in enumerate(value))
        inner = args[0] if args else Any
        return origin(hydrate(v, inner) for v in value)
    if origin is dict:
        args = typing.get_args(hint)
        return {k: hydrate(v, args[1] if len(args) == 2 else Any) for k, v in value.items()} if isinstance(value, dict) else value
    if not isinstance(hint, type):
        return value
    if issubclass(hint, Enum):
        try:
            return hint(value)
        except ValueError:
            return value
    if hint is datetime:
        try:
            return datetime.fromisoformat(value) if isinstance(value, str) else value
        except ValueError:
            return value
    if hint is date:
        try:
            return date.fromisoformat(value) if isinstance(value, str) else value
        except ValueError:
            return value
    if dataclasses.is_dataclass(hint) and isinstance(value, dict):
        return _record(hint, value)
    if hint is tuple and isinstance(value, list):
        return tuple(value)
    return value


def _record(cls: type, plain: Mapping[str, Any]) -> Any:
    """A dataclass rebuilt from its stored dict, field by field (no ``__init__``, so a frozen record works too)."""
    out = object.__new__(cls)
    types_ = hints(cls)
    for f in dataclasses.fields(cls):
        if f.name in plain:
            value = hydrate(plain[f.name], types_.get(f.name))
        elif f.default is not dataclasses.MISSING:
            value = f.default
        elif f.default_factory is not dataclasses.MISSING:
            value = f.default_factory()
        else:
            value = None
        object.__setattr__(out, f.name, value)
    return out


def view(record: type, names: Sequence[str], plain: Mapping[str, Any]) -> types.SimpleNamespace:
    """The named fields of a stored record, each as its declared type: all a lens check sees of a reading."""
    types_ = hints(record)
    return types.SimpleNamespace(**{name: hydrate(plain.get(name), types_.get(name)) for name in names})


# ---------------------------------------------------------------------------------------------------------------
# A lens and its checks


@dataclass(frozen=True)
class Reviewed:
    """What a check returns when it also derives fields as of the date (a contract's current term end)."""

    findings: tuple[Finding, ...] = ()
    fields: Mapping[str, Any] = field(default_factory=dict)


@dataclass(eq=False)
class LensCheck:
    """One check of a lens: a function of a record's named fields, the as-of date, and the facts it names."""

    lens: "Lens"
    key: str
    record: type
    fields: tuple[str, ...]
    fn: Callable[..., Any]
    facts: Callable[[Any, Any], Any] | None = None

    @property
    def reads(self) -> frozenset[Basis]:
        """What the check reads: the reading's fields, and the specification when it names facts."""
        return frozenset({Basis.TEXT}) | (frozenset({Basis.PROFILE}) if self.facts else frozenset())

    def basis(self, finding: Finding) -> frozenset[Basis]:
        return (self.reads | (frozenset({Basis.TODAY}) if self.lens.needs_as_of else frozenset())
                | (frozenset({Basis.LAW}) if finding.authority else frozenset()))

    def __call__(self, fields: Any, as_of: date | None, facts: Any = None) -> Reviewed:
        """The check on fields already rebuilt: its findings, each marked with the lens and its basis, and its fields."""
        out = self.fn(fields, as_of, facts)
        made = out if isinstance(out, Reviewed) else Reviewed(tuple(out or ()))
        return Reviewed(tuple(dataclasses.replace(f, lens=self.lens.key, basis=self.basis(f)) for f in made.findings), dict(made.fields))

    def __repr__(self) -> str:
        return f"<{self.lens.key}:{self.key}>"


@dataclass(eq=False)
class Lens:
    """A reusable way to judge readings: its key, the question it asks, whether it needs an as-of date, and its checks."""

    key: str
    question: str
    needs_as_of: bool = False
    checks: dict[str, LensCheck] = field(default_factory=dict)

    def check(self, key: str, record: type, *, fields: Sequence[str], facts: Callable[[Any, Any], Any] | None = None) -> Callable[[Callable[..., Any]], LensCheck]:
        """Register ``fn(fields, as_of, facts)`` as this lens's check ``key`` on ``record``'s named fields."""
        def register(fn: Callable[..., Any]) -> LensCheck:
            if key in self.checks:
                raise ValueError(f"the {self.key} lens already has a check {key!r}")
            made = LensCheck(self, key, record, tuple(fields), fn, facts)
            self.checks[key] = made
            return made
        return register

    @property
    def reads(self) -> frozenset[Basis]:
        """What the lens reads beyond the as-of date: the fields only (text), or the specification too. Never a store."""
        out: frozenset[Basis] = frozenset({Basis.TEXT})
        for c in self.checks.values():
            out |= c.reads
        return out

    @property
    def version(self) -> str:
        """The first twelve hex digits of a SHA-256 over this module's source and every module that registers one of the
        lens's checks, so a changed check is a new version; "" when a source cannot be read."""
        _load()
        names = sorted({__name__} | {c.fn.__module__ for c in self.checks.values()})
        key = (self.key, tuple(names), len(self.checks))
        if key not in _VERSIONS:
            h = hashlib.sha256()
            try:
                for name in names:
                    h.update(name.encode("utf-8") + b"\0" + inspect.getsource(sys.modules[name]).replace("\r\n", "\n").encode("utf-8") + b"\0")
                _VERSIONS[key] = h.hexdigest()[:12]
            except (KeyError, OSError, TypeError):
                _VERSIONS[key] = ""
        return _VERSIONS[key]

    def readers(self) -> tuple[tuple[DocumentKind, str], ...]:
        """Each (kind, reader) whose readings the lens reviews, from the registered readers' ``lens_checks``."""
        from jason.community.document_models import REGISTRY

        _load()
        return tuple((kind, model.name or type(model).__name__) for kind in DocumentKind for model in REGISTRY.get(kind, ())
                     if any(getattr(c, "lens", None) is self for c in model.lens_checks))

    @property
    def kinds(self) -> tuple[DocumentKind, ...]:
        """The document kinds the lens applies to."""
        return tuple(dict.fromkeys(kind for kind, _reader in self.readers()))

    def review(self, plain: Mapping[str, Any], checks: Sequence[LensCheck], as_of: date | None, community: Any = None, *,
               reading_version: str = "", known: "Review | None" = None) -> "Review":
        """This lens's review of one stored record, by ``checks`` (the ones its reader names).

        ``known`` is the review already stored for the same document and text. It stands, and no check runs, when the
        lens's version, the date, the fields the checks read, and the facts they read are all the same."""
        when = as_of if self.needs_as_of else None
        names = sorted({name for c in checks for name in c.fields})
        fields_sha = digest({name: plain.get(name) for name in names})
        views = {c.key: view(c.record, c.fields, plain) for c in checks}
        facts = {c.key: c.facts(views[c.key], community) for c in checks if c.facts is not None}
        facts_sha = digest(to_plain(facts)) if facts else ""
        version = self.version
        if known is not None and (known.lens, known.lens_version, known.as_of, known.fields_sha, known.facts_sha, tuple(known.checks)) == \
                (self.key, version, when, fields_sha, facts_sha, tuple(c.key for c in checks)):
            return dataclasses.replace(known, reused=True)
        found: dict[str, tuple[Finding, ...]] = {}
        derived: dict[str, Any] = {}
        for c in checks:
            made = c(views[c.key], when, facts.get(c.key))
            found[c.key] = made.findings
            derived.update(to_plain(dict(made.fields)))
        return Review(lens=self.key, lens_version=version, as_of=when, checks=found, fields=derived, reading_version=reading_version,
                      fields_sha=fields_sha, facts_sha=facts_sha)


_VERSIONS: dict[tuple[Any, ...], str] = {}


def _load() -> None:
    """Import the reader modules, which register the lenses' checks."""
    from jason.community import document_models

    document_models._load()


@dataclass(frozen=True)
class Review:
    """One lens applied to one document's stored fields.

    Its key is ``(document, text_sha, lens, lens_version, as_of)``. ``fields_sha`` and ``facts_sha`` are the digests of
    what it read; ``reading_version`` is the reader's version the fields came from. ``checks`` holds each check's
    findings, and ``fields`` the fields the lens derived as of the date, in their stored form."""

    lens: str
    lens_version: str
    as_of: date | None
    checks: Mapping[str, tuple[Finding, ...]] = field(default_factory=dict)
    fields: Mapping[str, Any] = field(default_factory=dict)
    document: str = ""
    text_sha: str = ""
    reading_version: str = ""
    reader: str = ""
    kind: str = ""
    fields_sha: str = ""
    facts_sha: str = ""
    produced_by: str = RULE
    reused: bool = field(default=False, compare=False)   # it was taken from the store, not made again

    @property
    def key(self) -> tuple[str, str, str, str, date | None]:
        return (self.document, self.text_sha, self.lens, self.lens_version, self.as_of)

    @property
    def findings(self) -> tuple[Finding, ...]:
        return tuple(f for found in self.checks.values() for f in found)

    def as_dict(self) -> dict[str, Any]:
        return {"document": self.document, "textSha": self.text_sha, "lens": self.lens, "lensVersion": self.lens_version,
                "asOf": self.as_of.isoformat() if self.as_of else None, "reader": self.reader, "kind": self.kind,
                "readingVersion": self.reading_version, "fieldsSha": self.fields_sha, "factsSha": self.facts_sha,
                "producedBy": self.produced_by, "checks": {key: [f.as_dict() for f in found] for key, found in self.checks.items()},
                "fields": dict(self.fields)}

    @classmethod
    def from_dict(cls, row: Mapping[str, Any]) -> "Review":
        return cls(lens=str(row.get("lens") or ""), lens_version=str(row.get("lensVersion") or ""),
                   as_of=date.fromisoformat(row["asOf"]) if row.get("asOf") else None,
                   checks={key: tuple(finding_from(f) for f in found) for key, found in (row.get("checks") or {}).items()},
                   fields=dict(row.get("fields") or {}), document=str(row.get("document") or ""), text_sha=str(row.get("textSha") or ""),
                   reading_version=str(row.get("readingVersion") or ""), reader=str(row.get("reader") or ""), kind=str(row.get("kind") or ""),
                   fields_sha=str(row.get("fieldsSha") or ""), facts_sha=str(row.get("factsSha") or ""),
                   produced_by=str(row.get("producedBy") or RULE))


def finding_from(row: Mapping[str, Any]) -> Finding:
    """A finding from its stored dict."""
    return Finding(str(row.get("code") or ""), str(row.get("message") or ""), Severity(row.get("severity") or Severity.CHECK.value),
                   str(row.get("authority") or ""), frozenset(Basis(b) for b in row.get("basis") or ()), str(row.get("lens") or ""))


# ---------------------------------------------------------------------------------------------------------------
# A reading and its reviews, joined


def compose(record: Any, checks: Sequence[LensCheck], context: Any, *, reading_version: str = "") -> tuple[Review, ...]:
    """The reviews of a record just read, one per lens among ``checks``, as of the context's date. The fields a lens
    derives are set on the record, so the reading shows them as it always did.

    Each lens is given the record in its stored form, never the live one: what a review finds at the reading is what it
    would find from the stored row."""
    plain = stored(record)
    known = getattr(context, "known", None) or {}
    types_ = hints(type(record))
    out = []
    for lens in dict.fromkeys(c.lens for c in checks):
        review = lens.review(plain, [c for c in checks if c.lens is lens], context.today, context.community,
                             reading_version=reading_version, known=known.get(lens.key))
        for name, value in review.fields.items():
            setattr(record, name, hydrate(value, types_.get(name)))
        out.append(review)
    return tuple(out)


def position(before: Iterable[Finding], others: Iterable[Finding]) -> int:
    """Where a slot stands among ``others`` (a reading's findings from outside the lens, as they stand now): after as
    many of them as stood before it when the reading was made. A reader's own ``read`` may drop, reword, or add findings
    after the slots were filled, so the place is counted by code, not remembered."""
    left = [f.code for f in before]
    n = 0
    for f in others:
        if f.code in left:
            left.remove(f.code)
            n += 1
    return n


def join(row: Mapping[str, Any], review: Review) -> dict[str, Any]:
    """A stored row with ``review`` in place of the review of the same lens it was stored with: the other findings where
    they were, the review's findings at the row's slots, and its derived fields in ``fields``. A row that records no
    slots for the lens is returned as it is."""
    stamp = (row.get("lenses") or {}).get(review.lens)
    if not stamp:
        return dict(row)
    others = [f for f in row.get("findings") or [] if f.get("lens") != review.lens]
    slots = sorted(((int(at), n, key) for n, (key, at) in enumerate((stamp.get("slots") or {}).items())))
    findings: list[dict[str, Any]] = []
    taken = 0
    for at, _n, key in slots:
        findings += others[taken:at]
        taken = max(taken, at)
        findings += [f.as_dict() for f in review.checks.get(key, ())]
    findings += others[taken:]
    out = dict(row)
    out["findings"] = findings
    if review.fields and isinstance(row.get("fields"), dict):
        out["fields"] = {**row["fields"], **review.fields}
    out["lenses"] = {**row["lenses"], review.lens: {**stamp, "version": review.lens_version,
                                                    "asOf": review.as_of.isoformat() if review.as_of else None}}
    return out


def lens_findings(row: Mapping[str, Any], lens: str) -> list[dict[str, Any]]:
    """The findings a stored row carries from ``lens``."""
    return [f for f in row.get("findings") or [] if f.get("lens") == lens]


# ---------------------------------------------------------------------------------------------------------------
# The lenses

AS_OF = Lens("as-of", "As of a date: which terms have ended, which deadlines have passed, and what is due next?", needs_as_of=True)

LENSES: dict[str, Lens] = {AS_OF.key: AS_OF}

__all__ = ["RULE", "Lens", "LensCheck", "Review", "Reviewed", "AS_OF", "LENSES", "stored", "digest", "hints", "hydrate", "view",
           "finding_from", "compose", "position", "join", "lens_findings"]
