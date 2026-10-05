"""Which readers run on a document of each kind, once ingest knows (or has proposed) what the document is.

A kind's readers are rows: ``KindReader(key, kinds, about, run)``. Ingest's kind stage (``jason.tasks.ingest.read_by_kind``)
analyses the kind first (``jason.community.kind_analysis``), then runs every reader whose kinds include it:

- **document-model** (every modeled kind): the kind's typed record and findings (``document_models``): a policy's limits
  and term, minutes' motions, an invoice's total, a contract's term and signatures.
- **contract-terms** (contracts, proposals, settlements, and the developer's security and subsidy agreements): each
  term with its party, deadline, and topic, the deliverables, and the findings (``contract_terms``), with a model's review
  when a person chose a backend.
- **norms** (the governing documents): the phrase grammar's duties, prohibitions, permissions, and rights, counted by
  who bears them and how many have a clock. The full reading (outlined, reviewed, tracked) is ``jason duties`` once the
  file is filed.

A new kind of reading is a new row. A reader returns a short summary for the ingest row (counts, codes, sections) and
keeps its full reading in its own store. A reader that fails says so in its summary and never stops the run.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Callable

from jason.community.symbols import DocumentKind as K


@dataclass
class ReaderContext:
    key: str                          # the file's key in the run ("ingest-<sha16>")
    name: str                         # its path or name, for a person
    kind: str
    community: Any = None
    data_dir: Path | None = None
    today: date | None = None
    confidential: bool = False
    backend: Any = None               # a model backend a person chose (``term_model``), or None
    allow_remote: bool = False
    notes: list[str] = field(default_factory=list)
    log: Callable[[str], None] = lambda s: None


@dataclass(frozen=True)
class KindReader:
    key: str
    about: str
    kinds: frozenset[str] | None      # None: every kind a document model handles
    run: Callable[[str, ReaderContext], dict[str, Any]]
    uses_model: bool = False          # takes the person's backend

    def handles(self, kind: str) -> bool:
        if not kind:
            return False
        if self.kinds is None:
            from jason.community.document_models import modeled_kinds

            return kind in {k.value for k in modeled_kinds()}
        return kind in self.kinds


def _document_model(text: str, ctx: ReaderContext) -> dict[str, Any]:
    from jason.community import document_models as dm

    context = dm.ModelContext(community=ctx.community, data_dir=ctx.data_dir, name=ctx.name,
                              confidential=ctx.confidential, **({"today": ctx.today} if ctx.today else {}))
    reading = dm.read(K(ctx.kind), text, context)
    if reading is None:
        return {"read": False, "why": f"no {ctx.kind} reader recognized the text"}
    return {"read": True, "model": reading.model, "complete": reading.complete, "missing": list(reading.missing),
            "findings": [{"code": f.code, "severity": f.severity.value, "authority": f.authority}
                         for f in reading.findings]}


def _contract_terms(text: str, ctx: ReaderContext) -> dict[str, Any]:
    from jason.tasks import contract_terms as task

    try:
        reading = task.read(text, key=ctx.key, name=ctx.name, backend=ctx.backend, confidential=ctx.confidential,
                            allow_remote=ctx.allow_remote, log=ctx.log)
    except task.RemoteRefused as exc:
        ctx.notes.append(str(exc))
        reading = task.read(text, key=ctx.key, name=ctx.name, confidential=ctx.confidential)
    if ctx.data_dir is not None:
        task.save(ctx.data_dir, reading)
    return task.summary(reading)


def _norms(text: str, ctx: ReaderContext) -> dict[str, Any]:
    from jason.community.contract_terms import prepare
    from jason.community.deontic import NORMS, read_passage

    prepared = prepare(text)
    body = prepared.body
    found = []
    for sec in prepared.sections:
        norms, _ = read_passage(body[sec.start:sec.end], source=ctx.key, section=sec.number, base=sec.start)
        found += [n for n in norms if n.kind in NORMS]
    return {"norms": len(found), "byKind": dict(Counter(n.kind.value for n in found).most_common()),
            "byBearer": dict(Counter(n.bearer.value for n in found).most_common(6)),
            "timed": sum(1 for n in found if n.timed), "notices": sum(1 for n in found if n.notice),
            "next": "file it, then jason outlines and jason duties for the full reading"}


def _licenses(text: str, ctx: ReaderContext) -> dict[str, Any]:
    from jason.community.licenses import by_license, find_licenses

    found = by_license(find_licenses(text))
    return {"licenses": [{"board": m.board.name, "kind": m.kind, "number": m.number, "class": m.classification,
                          "jurisdiction": m.jurisdiction, "holder": m.holder, "verify": m.verify} for m in found]}


_TERMS_KINDS = frozenset(k.value for k in (K.CONTRACT, K.PROPOSAL, K.SETTLEMENT, K.SECURITY_AGREEMENT,
                                           K.SUBSIDY_AGREEMENT))
_GOVERNING_KINDS = frozenset(k.value for k in (K.DECLARATION, K.AMENDMENT, K.ANNEXATION, K.BYLAWS, K.ARTICLES, K.POLICY,
                                               K.OPERATING_RULES, K.ELECTION_RULES, K.RESOLUTION))

READERS: tuple[KindReader, ...] = (
    KindReader("document-model", "the kind's typed record and findings", None, _document_model),
    KindReader("contract-terms", "each term, the deliverables, and the findings beside the statutes", _TERMS_KINDS,
               _contract_terms, uses_model=True),
    KindReader("norms", "the duties, prohibitions, permissions, and rights the phrase grammar reads", _GOVERNING_KINDS,
               _norms),
    KindReader("licenses", "the license numbers it prints, each with its board and holder (jason.community.licenses)",
               None, _licenses),
)


def readers_for(kind: str, readers: tuple[KindReader, ...] = READERS) -> list[KindReader]:
    return [r for r in readers if r.handles(kind)]


def run_readers(text: str, ctx: ReaderContext, readers: tuple[KindReader, ...] = READERS) -> dict[str, dict[str, Any]]:
    """Every reader for ``ctx.kind``, each summary under its key. A reader that raises reports the error; a model the
    person chose that becomes unavailable stops the run (``term_model.ModelUnavailable``), as a dry run should."""
    from jason.community.term_model import ModelUnavailable

    out: dict[str, dict[str, Any]] = {}
    for reader in readers_for(ctx.kind, readers):
        try:
            out[reader.key] = reader.run(text, ctx)
        except ModelUnavailable:
            raise
        except Exception as exc:  # noqa: BLE001 - one reader's failure is reported, never fatal
            out[reader.key] = {"error": f"{type(exc).__name__}: {exc}"[:300]}
    return out


__all__ = ["ReaderContext", "KindReader", "READERS", "readers_for", "run_readers"]
