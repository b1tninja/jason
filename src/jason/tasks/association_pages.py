"""The records inventory and the duty briefs as pages, from the specification, the catalog, the readings, and the extracts.

``records.md`` is the Civil Code 5200 inventory. ``duties.md`` is one
brief per duty anchor: the statute, the artifact, the records, the cadence,
the Jason command, and the passages the governing documents and the law
notes give for the duty's questions. Both are maps for a person; nothing
here decides a duty is met.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from jason.community.duties import DUTIES, Duty, duty_named
from jason.community.passages import Passage, corpus, passages_of, rank
from jason.community.readings import read_folder
from jason.community.records_inventory import Holding, inventory, inventory_dicts, inventory_markdown

GOVERNING_FOLDERS = (
    "artifacts/site-docs/governing_documents",
    "artifacts/site-docs/governing_documents_Annexations",
    "artifacts/site-docs/governing_documents_Policies",
    "artifacts/site-docs/governing_documents_Resolutions",
)


@dataclass
class AssociationPagesReport:
    written: tuple[Path, ...] = ()
    holdings: tuple[Holding, ...] = ()
    duties: int = 0
    gaps: list[str] = field(default_factory=list)

    def summary(self) -> str:
        return f"association pages records={len(self.holdings)} gaps={len(self.gaps)} duties={self.duties} files={len(self.written)}"


def catalog_paths(root: Path, org_id: int) -> tuple[str, ...]:
    """Every file path the local PayHOA catalog holds (folders left out)."""
    db = root / "payhoa.db"
    if not db.is_file():
        return ()
    with sqlite3.connect(db) as conn:
        rows = conn.execute("SELECT path FROM documents WHERE org_id = ? AND (directory = 0 OR directory IS NULL)", (org_id,)).fetchall()
    return tuple(str(row[0] or "") for row in rows)


def build_inventory(community, root: Path, *, governing=None) -> tuple[Holding, ...]:
    readings = read_folder(*(root / folder for folder in GOVERNING_FOLDERS[:2]), root / "governing")
    from jason.tasks.library import distinct, load as load_library

    return inventory(community, catalog_paths(root, community.org_id), readings=readings, governing=governing, library=tuple(distinct(load_library(root))))


class Shelf(Enum):
    GOVERNING = "governing document"
    STATUTE = "statute"
    LAW_NOTE = "law note"


@dataclass(frozen=True)
class Found:
    """One passage a duty's question found: where it came from, and the words."""

    shelf: Shelf
    label: str
    index: int
    score: float
    text: str


def statute_passages(duty: Duty, root: Path) -> tuple[tuple[Passage, ...], dict[Passage, str]]:
    """Passages of the exported statute sections the duty cites, each tied to its section's citation.

    Only sections inside the duty's own spans are read, so a question about
    assessments searches the assessment article, not all of Davis-Stirling.
    Nothing comes back before ``jason export-authorities`` has run.
    """
    from jason.community.authorities import Basis, number_key, parse_statutes, section_in
    from jason.tasks.export_authorities import authority_pages

    spans = [a for a in parse_statutes(duty.sections, "", Basis.DUTY) if a.exportable]
    items: list[Passage] = []
    cite: dict[Passage, str] = {}
    for page in authority_pages(root):
        if not any(page.code == a.code and number_key(page.start) <= number_key(a.end) and number_key(a.start) <= number_key(page.end) for a in spans):
            continue
        path = root / page.file
        if not path.is_file():
            continue
        for block in path.read_text(encoding="utf-8", errors="ignore").split("\n## ")[1:]:
            head, _, body = block.partition("\n")
            citation = head.strip()
            number = citation.rsplit(" ", 1)[-1]
            if not any(a.code == page.code and section_in(a, number) for a in spans):
                continue
            for piece in passages_of(path, text=body):
                passage = Passage(piece.path, len(items), piece.start_word, piece.text)
                items.append(passage)
                cite[passage] = citation
    return tuple(items), cite


def duty_passages(duty: Duty, root: Path, laws: Path | None = None, *, k: int = 3) -> dict[str, tuple[Found, ...]]:
    """The best passages for each of the duty's questions: the governing documents, then the statute.

    The statute is the exported section text for the duty's own sections. The
    law notes under docs/laws are Jason's summaries and are searched only
    when no statute page has been exported.
    """
    docs = corpus(*(root / folder for folder in GOVERNING_FOLDERS))
    statutes, cite = statute_passages(duty, root)
    law = () if statutes else (corpus(laws) if laws is not None else ())
    found: dict[str, tuple[Found, ...]] = {}
    for query in duty.queries:
        hits = [Found(Shelf.GOVERNING, h.passage.title, h.passage.index, h.score, h.passage.text) for h in rank(query, docs, k=k)]
        if statutes:
            hits += [Found(Shelf.STATUTE, cite[h.passage], h.passage.index, h.score, h.passage.text) for h in rank(query, statutes, k=2)]
        elif law:
            hits += [Found(Shelf.LAW_NOTE, h.passage.title, h.passage.index, h.score, h.passage.text) for h in rank(query, law, k=1)]
        found[query] = tuple(hits)
    return found


def duty_brief(duty: Duty, root: Path, laws: Path | None = None) -> dict[str, Any]:
    passages = duty_passages(duty, root, laws)
    return {
        "anchor": duty.anchor, "keepsStraight": duty.keeps_straight, "sections": duty.sections, "artifact": duty.artifact,
        "cadence": duty.cadence.value, "when": duty.when, "records": [r.value for r in duty.records], "produce": duty.produce, "limit": duty.limit,
        "passages": {
            query: [{"shelf": f.shelf.value, "file": f.label, "passage": f.index, "score": f.score, "text": f.text} for f in hits]
            for query, hits in passages.items()
        },
        "note": "a statute passage is the section's words from the current session publication; a law note is Jason's summary and is not quoted as the law",
    }


def duties_markdown(root: Path, laws: Path | None, *, title: str) -> str:
    lines = [f"# {title}", ""]
    lines.append("One brief per duty: the statute, the artifact the duty leaves, the records it rests on, when it recurs, what Jason produces, and the passages the governing documents and the statute give for its questions. The passages are the documents' and the sections' own words, found by search, for the person to read; the brief decides nothing.")
    lines.append("")
    lines.append("| Duty | Sections | Cadence | Records | Jason |")
    lines.append("| --- | --- | --- | --- | --- |")
    for duty in DUTIES:
        lines.append(f"| [{duty.anchor}](#{_slug(duty.anchor)}) | {duty.sections} | {duty.cadence.value} | {', '.join(r.value.replace('_', ' ') for r in duty.records[:4])}{', and more' if len(duty.records) > 4 else ''} | {duty.produce} |")
    lines.append("")
    for duty in DUTIES:
        lines.append(f"## {duty.anchor}")
        lines.append("")
        lines.append(f"- **Keeps straight** {duty.keeps_straight}")
        lines.append(f"- **Sections** {duty.sections}")
        # The cited sections whose law changed since the 2014 recodification (renumbered with the same effect is not).
        from jason.community.succession import changed_in

        for section, note in changed_in(root, duty.sections):
            lines.append(f"- **Law changes** CIV {section}: {note}")
        lines.append(f"- **Artifact** {duty.artifact}")
        lines.append(f"- **When** {duty.when}")
        lines.append(f"- **Records** {', '.join(r.value.replace('_', ' ') for r in duty.records)}")
        lines.append(f"- **Jason produces** {duty.produce}")
        if duty.limit:
            lines.append(f"- **Limit** {duty.limit}")
        lines.append("")
        for query, hits in duty_passages(duty, root, laws).items():
            lines.append(f"**{query}**")
            lines.append("")
            if not hits:
                lines.append("- nothing found in the extracts")
            for hit in hits:
                snippet = " ".join(hit.text.split())[:420]
                where = f"*{hit.label}*" if hit.shelf is Shelf.STATUTE else f"*{hit.label}*, passage {hit.index}"
                lines.append(f"- {where}: {snippet}" if hit.shelf is not Shelf.LAW_NOTE else f"- {where} (Jason's note): {snippet}")
            lines.append("")
    return "\n".join(lines)


def _slug(text: str) -> str:
    return "".join(ch if ch.isalnum() else "-" for ch in text.lower()).strip("-").replace("--", "-")


def write_association_pages(community, root: Path, out_dir: Path, *, laws: Path | None = None, governing=None, title: str) -> AssociationPagesReport:
    out_dir.mkdir(parents=True, exist_ok=True)
    holdings = build_inventory(community, root, governing=governing)
    records = out_dir / "records.md"
    records.write_text(inventory_markdown(holdings, title=f"{title}: the records under Civil Code 5200"), encoding="utf-8")
    duties = out_dir / "duties.md"
    duties.write_text(duties_markdown(root, laws, title=f"{title}: the manager's duties and where the documents speak to them"), encoding="utf-8")
    return AssociationPagesReport((records, duties), holdings, len(DUTIES), [f"{h.kind.value}: {h.gap}" for h in holdings if h.gap])


def brief_for(anchor: str, root: Path, laws: Path | None = None) -> dict[str, Any]:
    duty = duty_named(anchor)
    if duty is None:
        return {"found": False, "anchor": anchor, "duties": [d.anchor for d in DUTIES]}
    return {"found": True, **duty_brief(duty, root, laws)}


def _unused(_: Any) -> None:
    return None


__all__ = ["write_association_pages", "brief_for", "build_inventory", "inventory_dicts", "duty_brief", "AssociationPagesReport"]
