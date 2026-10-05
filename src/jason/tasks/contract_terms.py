"""Read a contract's terms and keep them: the store under ``data/contracts/terms``, one JSON per document.

``read`` is the one call every caller uses (``jason contract-terms``, ``jason ingest``): unwrap the text, read the
parties, sections, and terms with the grammar, let a model review them when a person chose a backend, and draw the
deliverables and findings. ``run_library`` reads every contract and proposal the library holds. ``markdown`` is what a
person reads. The store names the association's counterparties and quotes its contracts, so it is private (``data/``).
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable

from jason.community import contract_terms as ct
from jason.community.document_models import Finding

STORE = Path("contracts") / "terms"
KINDS = ("contract", "proposal")                 # the document kinds read for terms


class RemoteRefused(RuntimeError):
    """A confidential document and a backend that sends words off this machine, without a person's leave."""


@dataclass
class TermsReading:
    key: str
    name: str
    text_sha: str
    counterparty: str
    parties: ct.PartyTerms
    terms: list[ct.ContractTerm]
    findings: list[Finding]
    method: str = "grammar"                       # "grammar" or "hybrid:<backend>"
    dropped: list[dict[str, Any]] = field(default_factory=list)
    confidential: bool = False
    read_at: str = ""
    licenses: list[Any] = field(default_factory=list)   # ``licenses.LicenseMention``, one per license
    noise: list[dict[str, Any]] = field(default_factory=list)   # what ``page_noise.strip_noise`` removed
    options: list[Any] = field(default_factory=list)    # ``checked_options.Option``, each offered option and its mark
    excluded: list[str] = field(default_factory=list)   # the items listed under an "Exclusions:" heading

    @property
    def deliverables(self) -> list[ct.ContractTerm]:
        return ct.deliverables(self.terms)

    def counts(self) -> dict[str, Any]:
        return {"terms": len(self.terms), "deliverables": len(self.deliverables),
                "byTopic": dict(Counter(t.topic.value for t in self.terms).most_common()),
                "byParty": dict(Counter(t.party.value for t in self.terms).most_common()),
                "findings": dict(Counter(f.code for f in self.findings).most_common())}

    def as_dict(self) -> dict[str, Any]:
        return {"key": self.key, "name": self.name, "textSha": self.text_sha, "counterparty": self.counterparty,
                "parties": {"association": list(self.parties.association), "counterparty": list(self.parties.counterparty),
                            "names": dict(self.parties.names)},
                "method": self.method, "confidential": self.confidential, "readAt": self.read_at,
                "counts": self.counts(), "terms": [t.to_dict() for t in self.terms],
                "deliverables": [t.id for t in self.deliverables],
                "licenses": [m.to_dict() for m in self.licenses],
                "noise": list(self.noise),
                "options": [{"label": o.label, "checked": o.checked, "marker": o.marker} for o in self.options],
                "excluded": list(self.excluded),
                "findings": [{"code": f.code, "message": f.message, "severity": f.severity.value,
                              "authority": f.authority} for f in self.findings],
                "dropped": self.dropped}


def read(text: str, *, key: str, name: str = "", backend: Any = None, confidential: bool = False,
         allow_remote: bool = False, trust: str = "fill", log: Callable[[str], None] = lambda s: None) -> TermsReading:
    """The contract's terms. With ``backend`` a model reviews the grammar's reading (``trust``: "fill" adds and fills
    only, "full" lets the model's verdicts replace the grammar's; ``term_model.merge``); a ``remote`` backend refuses
    a confidential document unless ``allow_remote``."""
    if backend is not None and getattr(backend, "remote", False) and confidential and not allow_remote:
        raise RemoteRefused(f"{name or key} is confidential and {backend.name} sends its words off this machine; "
                            "a person allows it for this run (--allow-remote-confidential) or uses a local model")
    from jason.community.page_noise import strip_noise

    # The words without an e-signature audit trail, page numbers, or running headers and footers; licenses are still
    # read from the whole text (a letterhead line kept once is enough, but a license printed only in a footer counts).
    clean, noise = strip_noise(text)
    prepared = ct.prepare(clean)
    body, parties = prepared.body, prepared.parties
    terms = ct.read_terms(body, source=key, parties=parties, sections=prepared.sections)
    terms, notices = ct.mark_notices(terms, body)
    method, dropped = "grammar", []
    if backend is not None:
        from jason.community.term_model import review

        sections = [(s.start, s.end, s.number, s.caption) for s in prepared.sections]
        terms, dropped = review(body, terms, backend, source=key, sections=sections, trust=trust, log=log)
        method = f"hybrid:{backend.name}" + ("" if trust == "fill" else f" ({trust})")
    from jason.community.licenses import by_license, find_licenses

    from jason.community.checked_options import find_options
    from jason.community.exemptions import excluded_items

    counterparty = ct.counterparty_name(body, parties)
    licenses = by_license(find_licenses(text))
    # Options and an exclusions list are read from the lines as laid out, before unwrapping joins them.
    # A document that carries the contract twice (a copy and the signed copy) offers each option once.
    options, seen = [], set()
    for o in find_options(clean):
        if (o.label.lower(), o.checked) not in seen:
            seen.add((o.label.lower(), o.checked))
            options.append(o)
    excluded = list(dict.fromkeys(excluded_items(clean)))
    return TermsReading(key=key, name=name or key, text_sha=hashlib.sha256(body.encode("utf-8")).hexdigest()[:16],
                        counterparty=counterparty, parties=parties, terms=terms,
                        findings=ct.findings(terms) + license_findings(licenses, counterparty) + notice_findings(notices)
                        + option_findings(options, excluded),
                        method=method, dropped=dropped, confidential=confidential, licenses=licenses, noise=noise,
                        options=options, excluded=excluded,
                        read_at=datetime.now(timezone.utc).isoformat(timespec="seconds"))


def option_findings(options: list[Any], excluded: list[str]) -> list[Finding]:
    """Which offered options the text says were chosen, and those it cannot read (a mark that sits elsewhere in the
    text layer belongs to an option only by its place on the page: a person or a layout reader settles it)."""
    from jason.community.document_models import Severity

    out = []
    chosen = [o.label for o in options if o.checked is True]
    if chosen:
        out.append(Finding("options-chosen", f"marked: {'; '.join(chosen)}" + (
            f"; not marked: {'; '.join(o.label for o in options if o.checked is False)}"
            if any(o.checked is False for o in options) else ""), Severity.INFO))
    unread = [o.label for o in options if o.checked is None]
    if unread:
        out.append(Finding("options-not-read", f"options not read from the text: {'; '.join(unread)}; which were "
                           "chosen is read from the signed page, never guessed", Severity.CHECK))
    if excluded:
        out.append(Finding("excluded-items", f"excluded from the work: {'; '.join(excluded)}", Severity.INFO))
    return out


def notice_findings(notices: list[Any]) -> list[Finding]:
    """One finding per statutory notice the contract prints: the law's words, read as such, with their authority."""
    from jason.community.document_models import Severity

    seen, out = set(), []
    for notice, _s, _e in notices:
        if notice.key in seen:
            continue
        seen.add(notice.key)
        out.append(Finding("statutory-notice", f"prints the {notice.title}: the Legislature's words, not a promise of "
                           "either party", Severity.INFO, notice.authority))
    return out


def license_findings(licenses: list[Any], counterparty: str) -> list[Finding]:
    """Each license the document prints, with where to check it; and a license whose holder is not the counterparty (a
    subcontractor, a surety, or a misread holder)."""
    from jason.community.document_models import Severity
    from jason.community.licenses import Board

    out = []
    for m in licenses:
        if m.board in (Board.NOTARY, Board.CERTIFICATION):
            continue
        where = f"{m.label} {m.number}" + (f" ({m.classification})" if m.classification else "") + \
                (f", {m.jurisdiction}" if m.jurisdiction and m.jurisdiction != "CA" else "")
        out.append(Finding("license-printed", f"{where}" + (f", held by {m.holder}" if m.holder else "") +
                           (f"; check it at {m.verify}" if m.verify else ""), Severity.INFO,
                           "BPC 7030.5" if m.board is Board.CSLB else ""))
        if m.holder and counterparty and not _same_party(m.holder, counterparty):
            out.append(Finding("license-holder-differs", f"{where} is printed beside {m.holder}, not {counterparty}: a "
                               "subcontractor, an affiliate, or a misread holder", Severity.CHECK))
    return out


def _same_party(a: str, b: str) -> bool:
    words = lambda s: {w for w in "".join(c.lower() if c.isalnum() else " " for c in s).split()  # noqa: E731
                       if w not in ("inc", "llc", "corp", "co", "company", "the", "ltd", "llp", "services", "group")}
    x, y = words(a), words(b)
    return bool(x and y and (x <= y or y <= x or len(x & y) >= 2))


def save(root: Path, reading: TermsReading) -> Path:
    folder = Path(root) / STORE
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{_safe(reading.key)}.json"
    path.write_text(json.dumps(reading.as_dict(), indent=1, ensure_ascii=False), encoding="utf-8")
    return path


def load(root: Path) -> list[dict[str, Any]]:
    folder = Path(root) / STORE
    if not folder.is_dir():
        return []
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(folder.glob("*.json"))]


def _safe(key: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "-_." else "-" for ch in key)[:120]


def run_library(root: Path, *, backend: Any = None, kinds: Iterable[str] = KINDS, allow_remote: bool = False,
                log: Callable[[str], None] = lambda s: None) -> list[TermsReading]:
    """Every contract and proposal in the library, read and saved. A confidential file is skipped by a remote backend
    unless ``allow_remote``; the skip is logged."""
    from jason.tasks.library import distinct, load as load_library, text_for

    out = []
    for row in distinct(load_library(root)):
        if row.get("kind") not in set(kinds):
            continue
        text = text_for(root, str(row["id"]))
        if not text.strip():
            log(f"{row['path']}: no text")
            continue
        try:
            reading = read(text, key=f"library-{row['id']}", name=str(row["path"]), backend=backend,
                           confidential=bool(row.get("confidential")), allow_remote=allow_remote, log=log)
        except RemoteRefused as exc:
            log(str(exc))
            continue
        save(root, reading)
        out.append(reading)
        log(f"{row['path']}: {len(reading.terms)} terms, {len(reading.deliverables)} deliverables")
    return out


# --- What a person reads ----------------------------------------------------------------------------------------------

def _cell(text: Any) -> str:
    return " ".join(str(text if text is not None else "").split()).replace("|", "/")


def _when(t: ct.ContractTerm) -> str:
    bits = []
    if t.deadline is not None:
        bits.append(t.deadline.text)
    if t.recurrence:
        bits.append(t.recurrence)
    if t.window_days:
        bits.append(f"window {t.window_days[0]} to {t.window_days[1]}")
    return "; ".join(bits)


def markdown(reading: TermsReading, *, quote_chars: int = 220) -> str:
    """The reading as a person reviews it: the findings, the deliverables, then the terms by topic. Every row is the
    contract's own words; a finding is a lead, not a determination."""
    c = reading.counts()
    out = [f"# Contract terms: {reading.name}", "",
           f"Counterparty: {(reading.counterparty or 'not named in the opening').rstrip('.')}. Read by {reading.method}; "
           f"{c['terms']} terms, {c['deliverables']} deliverables. Each row quotes the contract; a finding is a lead for "
           "a person, and a question of meaning goes to counsel (docs/contracts.md).", ""]
    out += ["## Parties", ""]
    shorts = [w for w in reading.parties.counterparty if w not in ct._COUNTERPARTY_WORDS]
    out.append(f"- Counterparty: {reading.counterparty or 'not named'}"
               + (f"; it goes by {', '.join(shorts)}" if shorts else ""))
    for term, who in reading.parties.names.items():
        out.append(f"- \"{term}\": {who}")
    for m in reading.licenses:
        out.append(f"- License: {m.label} {m.number}" + (f" ({m.classification})" if m.classification else "")
                   + (f", {m.jurisdiction}" if m.jurisdiction and m.jurisdiction != "CA" else "")
                   + (f", beside {m.holder}" if m.holder else "") + (f"; check {m.verify}" if m.verify else ""))
    out += ["", "## Findings", ""]
    out += [f"- **{f.code}** ({f.severity.value}{', ' + f.authority if f.authority else ''}): {_cell(f.message)}"
            for f in reading.findings] or ["None."]
    out += ["", "## What the counterparty must produce", "",
            "Each one is a duty the association can hold the counterparty to: a log, a report, a notice, records, or an "
            "act with a clock.", "", "| Section | Topic | When | Words |", "| --- | --- | --- | --- |"]
    rows = [f"| {t.section} | {t.topic.value} | {_cell(_when(t))} | {_cell(t.quote[:quote_chars])} |"
            for t in reading.deliverables]
    out += rows or ["| | | | none read |"]
    by_topic: dict[ct.Topic, list[ct.ContractTerm]] = {}
    for t in reading.terms:
        by_topic.setdefault(t.topic, []).append(t)
    out += ["", "## Terms by topic", ""]
    for topic in ct.Topic:
        items = by_topic.get(topic)
        if not items:
            continue
        out += [f"### {topic.value[0].upper()}{topic.value[1:]}", "", "| Section | Kind | Party | When | Words |",
                "| --- | --- | --- | --- | --- |"]
        out += [f"| {t.section} | {t.kind.value} | {t.party.value} | {_cell(_when(t))} | {_cell(t.quote[:quote_chars])} |"
                for t in items]
        out.append("")
    if reading.dropped:
        out += [f"## Dropped by the model ({len(reading.dropped)})", ""]
        out += [f"- {_cell(d.get('why'))}: {_cell(d.get('candidate') or (d.get('item') or {}).get('quote', ''))[:160]}"
                for d in reading.dropped[:40]]
    return "\n".join(out).rstrip() + "\n"


def summary(reading: TermsReading) -> dict[str, Any]:
    """What an ingest row carries: counts, the deliverables' sections, and the findings' codes."""
    return {"key": reading.key, "method": reading.method, "counterparty": reading.counterparty,
            "terms": len(reading.terms), "deliverables": [f"{t.section} {t.topic.value}" for t in reading.deliverables],
            "licenses": [f"{m.board.name} {m.number}" for m in reading.licenses],
            "findings": [f.code for f in reading.findings]}


__all__ = ["STORE", "KINDS", "RemoteRefused", "TermsReading", "read", "save", "load", "run_library", "markdown",
           "summary"]
