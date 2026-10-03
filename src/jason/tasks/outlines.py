"""Outline the association's documents and map the references among them and to the law.

``build`` reads each Google Doc the specification names (``Community.citable_documents()``) and every Doc in the
resolutions folder, plus the library documents of the outlined kinds from their text, and writes one outline per
document to ``data/outlines/<key>.json``. ``references`` reads the references in every outline (``jason.community
.references``), and ``resolve`` checks each against what jason holds: a section against the target's outline, a statute
against the exported law (``data/authorities``), a resolution number against the numbers the resolutions print, a
document by name against the outlines. ``report`` writes ``data/reports/references.md`` (the documents, a diagram of
which cites which, the findings, and the most cited targets) and a page per document under ``data/outlines/``.

A finding is a lead for a person: a dangling section may be a drafting gap (the Phase 6 and 7 annexations cite a
1.3(d)(ii) they do not contain) or an outline that missed a subsection; a resolution number two Docs print may be a
duplicate number or a stale header. Reading only: nothing in Drive changes.
"""

from __future__ import annotations

import json
import re
import sqlite3
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from jason.community.outlines import DocumentOutline, outline_from_doc, outline_from_text, outline_lines
from jason.community.references import Reference, TargetKind, ancestors, extract, section_target, statute_key

RESOLUTION_NUMBER = re.compile(r"RESOLUTION\s+NUMBER\s+([\w-]+)", re.I)
TITLE_NUMBER = re.compile(r"\b(?:Administrative|Special|Policy)\s+Resolution\s+(\d{6,8}-\d+)\b", re.I)


def outline_dir(data_dir: Path) -> Path:
    path = Path(data_dir) / "outlines"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:60]


def _header_text(doc: dict[str, Any]) -> str:
    tab = ((doc.get("tabs") or [{}])[0].get("documentTab")) or doc
    parts = []
    for seg in (tab.get("headers") or {}).values():
        for block in seg.get("content", []):
            for el in (block.get("paragraph") or {}).get("elements", []):
                parts.append(el.get("textRun", {}).get("content", ""))
    return "".join(parts)


def build(docs: Any, drive: Any, community: Any, data_dir: Path, *, log=print) -> list[DocumentOutline]:
    """Read every outlined document and write its outline. Returns the outlines."""
    out: list[DocumentOutline] = []
    for spec in community.citable_documents():
        doc = docs.get(spec.drive_id, without_suggestions=True)
        outline = outline_from_doc(doc, key=spec.key, title=spec.title, kind=spec.kind.value)
        outline.aliases, outline.amends = list(spec.aliases), spec.amends
        out.append(_save(data_dir, outline))
        log(f"{spec.key}: {len(outline.sections)} sections")
    folder = community.resolutions_folder()
    if folder:
        for f in drive.list_folder(folder):
            if not f.get("mimeType", "").endswith("document"):
                continue
            doc = docs.get(f["id"], without_suggestions=True)
            # Several resolutions share a title ("Special Resolution - Investment of Reserve Funds"); the Drive id keeps them apart.
            key = f"resolution-{_slug(f['name'])[:48]}-{f['id'][:4].lower()}"
            # The number the headers print, or the one the Doc's first line (its title) gives.
            numbers = list(dict.fromkeys(RESOLUTION_NUMBER.findall(_header_text(doc)) + TITLE_NUMBER.findall(_body_head(doc, 1))))
            outline = outline_from_doc(doc, key=key, title=f["name"], kind="resolution")
            outline.numbers = numbers
            out.append(_save(data_dir, outline))
            log(f"{key}: {len(outline.sections)} sections; numbers printed: {', '.join(numbers) or 'none'}")
    kinds = {k.value: supplements for k, supplements in community.library_outlined_kinds().items()}
    library = Path(data_dir) / "library"
    if kinds and (library / "library.db").is_file():
        with sqlite3.connect(f"{(library / 'library.db').resolve().as_uri()}?mode=ro", uri=True) as conn:
            rows = conn.execute("SELECT id, path, kind FROM documents").fetchall()
        for doc_id, path, kind in rows:
            text_file = library / "text" / f"{doc_id}.txt"
            if kind not in kinds or not text_file.is_file():
                continue
            key = f"{kind}-{_slug(Path(path).stem)}"
            outline = outline_from_text(text_file.read_text(encoding="utf-8", errors="replace"), key=key, title=Path(path).name, kind=kind)
            outline.library, outline.amends = path, kinds[kind]
            out.append(_save(data_dir, outline))
            log(f"{key}: {len(outline.sections)} sections (from the library's text)")
    return out


def _body_head(doc: dict[str, Any], lines: int = 12) -> str:
    """The first ``lines`` paragraphs with text."""
    from jason.community.outlines import _paragraph_text, _paragraphs

    tab = ((doc.get("tabs") or [{}])[0].get("documentTab")) or doc
    texts = [t for t in (_paragraph_text(p).strip() for p in _paragraphs(tab.get("body", {}).get("content", []))) if t]
    return "\n".join(texts[:lines])


def _save(data_dir: Path, outline: DocumentOutline) -> DocumentOutline:
    (outline_dir(data_dir) / f"{outline.key}.json").write_text(json.dumps(outline.to_dict(), indent=1), encoding="utf-8")
    return outline


def load(data_dir: Path) -> list[DocumentOutline]:
    out = []
    for path in sorted(outline_dir(data_dir).glob("*.json")):
        if path.name == "references.json":
            continue
        out.append(DocumentOutline.from_dict(json.loads(path.read_text(encoding="utf-8"))))
    return out


def aliases_of(outlines: list[DocumentOutline]) -> dict[str, str]:
    names: dict[str, str] = {}
    for o in outlines:
        for alias in o.aliases:
            names[alias.lower()] = o.key
    return names


def references(outlines: list[DocumentOutline]) -> list[Reference]:
    names = aliases_of(outlines)
    out: list[Reference] = []
    for o in outlines:
        # A resolution naming its own number ("Administrative Resolution 20261020-1" as its title) is not a reference.
        out += [r for r in extract(o, names) if not (r.kind is TargetKind.RESOLUTION and r.target.split(":", 1)[1] in o.numbers)]
    return out


def resolve(refs: list[Reference], outlines: list[DocumentOutline], data_dir: Path) -> list[dict[str, Any]]:
    """Each reference with a ``status``: found, parent only (the section exists, not the subsection), missing, not
    outlined, statute on disk or not, a resolution number printed by one Doc, several, or none."""
    by_key = {o.key: o for o in outlines}
    claims: dict[str, list[str]] = defaultdict(list)
    for o in outlines:
        for n in o.numbers:
            claims[n].append(o.key)
    law_cache: dict[str, bool] = {}

    def on_disk(citation: str) -> bool:
        if citation not in law_cache:
            try:
                from jason.tasks.export_authorities import authority_text

                law_cache[citation] = bool(authority_text(Path(data_dir), citation).get("found"))
            except Exception:
                law_cache[citation] = False
        return law_cache[citation]

    out = []
    for r in refs:
        row = r.to_dict()
        if r.kind is TargetKind.SECTION:
            key, number = section_target(r.target)
            outline = by_key.get(key)
            if outline is None:
                row["status"] = "document not outlined"
            elif outline.section(number):
                row["status"] = "found"
            elif any(outline.section(a) for a in ancestors(number)):
                row["status"] = "parent only"
                row["nearest"] = next(a for a in ancestors(number) if outline.section(a))
            else:
                row["status"] = "missing"
        elif r.kind is TargetKind.STATUTE:
            base, _ = statute_key(r.target)
            row["status"] = "prior numbering" if r.prior else ("law on disk" if on_disk(base) else "law not on disk")
        elif r.kind is TargetKind.RESOLUTION:
            number = r.target.split(":", 1)[1]
            who = [k for k in claims.get(number, []) if k != r.source]
            row["status"] = "found" if len(who) == 1 else "printed by several" if who else "no resolution prints it"
            row["claimants"] = who
        elif r.kind is TargetKind.DOCUMENT:
            row["status"] = "found" if r.target in by_key else "document not outlined"
        else:
            row["status"] = "not checked"
        out.append(row)
    return out


def findings(rows: list[dict[str, Any]], outlines: list[DocumentOutline]) -> list[str]:
    out = []
    seen: set[tuple[str, str]] = set()
    for r in [r for r in rows if r["kind"] == "section" and r["status"] == "missing"]:
        if (r["source"], r["target"]) in seen:
            continue
        seen.add((r["source"], r["target"]))
        where = f" (in its section {r['source_section']})" if r["source_section"] else ""
        out.append(f"{r['source']}{where} cites {r['target']}, which that outline does not have: a drafting gap, or a section the "
                   f"outline missed. \"{r['quote'][:140]}\"")
    for r in [r for r in rows if r["kind"] == "section" and r["status"] == "parent only"]:
        if (r["source"], r["target"]) in seen:
            continue
        seen.add((r["source"], r["target"]))
        out.append(f"{r['source']} cites {r['target']}; the outline has {r['nearest']} but not the subsection")
    for number, count in Counter(n for o in outlines for n in o.numbers).items():
        if count > 1:
            docs = [o.key.removeprefix("resolution-") for o in outlines if number in o.numbers]
            listed = ", ".join(docs) if len(docs) <= 4 else f"{', '.join(docs[:3])}, and {len(docs) - 3} more"
            out.append(f"resolution number {number} is printed by {count} Docs ({listed}): a duplicate number or a header copied "
                       "from another resolution")
    prior = sorted({r["target"] for r in rows if r["status"] == "prior numbering"})
    if prior:
        out.append(f"statutes cited by their pre-2014 Davis-Stirling numbers: {', '.join(prior)} (renumbered January 1, 2014)")
    unclaimed = sorted({r["target"] for r in rows if r["kind"] == "resolution" and r["status"] == "no resolution prints it"})
    if unclaimed:
        out.append(f"resolutions cited that no resolution Doc prints: {', '.join(unclaimed)}")
    return out


def model_references(data_dir: Path, grammar: list[Reference]) -> list[Reference]:
    """The local model's verified references (``jason outlines --model``) that the grammar does not also have in the same
    section. A target the model could only name in words (``named:...``) stays in the model's own file: nothing here can
    check it."""
    from dataclasses import fields

    from jason.tasks.reference_review import load_store

    have = {(r.source, r.source_section, r.target) for r in grammar}
    # A section number the grammar already read in the same place, whichever document it gave it to ("§ 4.15(o)" under
    # "WHAT ARE THE CC&Rs?" is the CC&Rs', which the grammar takes from the title).
    numbers = {(r.source, r.source_section, r.target.split("#", 1)[1]) for r in grammar if r.kind is TargetKind.SECTION}
    known = {f.name for f in fields(Reference)}
    out = []
    for raw in load_store(Path(data_dir)).get("references", []):
        if str(raw.get("target", "")).startswith("named:"):
            continue
        ref = Reference.from_dict({k: v for k, v in raw.items() if k in known})
        if ref.kind is TargetKind.SECTION:
            # Stored before a rule changed: take it as verification takes it now.
            from dataclasses import replace

            from jason.community.reference_model import section_rule

            checked = section_rule(ref.target)
            if checked is None:
                continue
            ref = replace(ref, kind=checked[0], target=checked[1], prior=checked[2])
        if (ref.source, ref.source_section, ref.target) in have:
            continue
        if ref.kind is TargetKind.SECTION and (ref.source, ref.source_section, ref.target.split("#", 1)[1]) in numbers:
            continue
        out.append(ref)
    return out


def run(data_dir: Path, outlines: list[DocumentOutline] | None = None) -> dict[str, Any]:
    outlines = outlines if outlines is not None else load(data_dir)
    grammar = references(outlines)
    rows = resolve(grammar + model_references(data_dir, grammar), outlines, data_dir)
    (outline_dir(data_dir) / "references.json").write_text(json.dumps(rows, indent=1), encoding="utf-8")
    found = findings(rows, outlines)
    report(data_dir, outlines, rows, found)
    from jason.tasks.outline_viewer import write_viewer

    viewer = write_viewer(data_dir, outlines, rows, found)
    return {"documents": len(outlines), "sections": sum(len(o.sections) for o in outlines), "references": len(rows),
            "byKind": dict(Counter(r["kind"] for r in rows)), "byStatus": dict(Counter(r["status"] for r in rows)),
            "byMethod": dict(Counter(r.get("method", "grammar") for r in rows)), "findings": found,
            "viewer": str(viewer)}


def load_rows(data_dir: Path) -> list[dict[str, Any]]:
    path = outline_dir(data_dir) / "references.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else []


def cited_by(rows: list[dict[str, Any]], target: str) -> list[dict[str, Any]]:
    """References whose target is ``target`` or inside it ("CIV 4926" takes "CIV 4926(a)(3)"; "bylaws#7" takes "7.2")."""
    t = target.strip()
    return [r for r in rows if r["target"] == t or r["target"].startswith(t + "(") or r["target"].startswith(t + ".")]


def _mermaid(outlines: list[DocumentOutline], rows: list[dict[str, Any]]) -> list[str]:
    keys = {o.key for o in outlines}
    edges: Counter = Counter()
    statutes: Counter = Counter()
    for r in rows:
        if r["kind"] in ("section", "document"):
            target = r["target"].split("#")[0]
            if target in keys and target != r["source"]:
                edges[(r["source"], target)] += 1
        elif r["kind"] == "resolution":
            for k in r.get("claimants", []):
                edges[(r["source"], k)] += 1
        elif r["kind"] == "statute":
            statutes[(r["source"], r["target"].split()[0] if " CCR " not in r["target"] else "CCR")] += 1
    ident = {k: re.sub(r"[^A-Za-z0-9_]", "_", k) for k in keys}
    lines = ["```mermaid", "flowchart LR"]
    used = {k for e in edges for k in e} | {s for s, _ in statutes}
    titles = {o.key: o.title.replace('"', "'") for o in outlines}
    for k in sorted(used):
        lines.append(f'  {ident[k]}["{titles.get(k, k)[:40]}"]')
    for code in sorted({c for _, c in statutes}):
        lines.append(f'  law_{code}(("{code}"))')
    for (a, b), n in sorted(edges.items()):
        lines.append(f"  {ident[a]} -->|{n}| {ident[b]}")
    for (a, code), n in sorted(statutes.items()):
        if n >= 3:
            lines.append(f"  {ident[a]} -.->|{n}| law_{code}")
    lines.append("```")
    return lines


def report(data_dir: Path, outlines: list[DocumentOutline], rows: list[dict[str, Any]], found: list[str]) -> Path:
    by_source: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_doc_target: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        by_source[r["source"]].append(r)
        if r["kind"] in ("section", "document"):
            by_doc_target[r["target"].split("#")[0]].append(r)
    out = ["# Document references", "",
           "_Each outlined document's sections, the references its text makes, and what cites it. Read from the Google Docs and "
           "the library's text by `jason outlines --fetch`; a finding is a lead for a person, and nothing in Drive changes._", "",
           "| Document | Sections | Statutes | Sections cited | Resolutions | Cited by (other documents) |", "|---|---:|---:|---:|---:|---:|"]
    for o in sorted(outlines, key=lambda o: -len(by_source[o.key])):
        mine = by_source[o.key]
        cited = len({r["source"] for r in by_doc_target[o.key] if r["source"] != o.key})
        out.append(f"| [{o.title}]({o.key}.md) | {len(o.sections)} | {sum(r['kind'] == 'statute' for r in mine)} | "
                   f"{sum(r['kind'] == 'section' for r in mine)} | {sum(r['kind'] == 'resolution' for r in mine)} | {cited} |")
    out += ["", "## Which documents cite which", "", "Arrows are references from one document to another (sections, the document by name, "
            "or a resolution by number), labeled with the count; dotted arrows go to a code the document cites three or more times.", ""]
    out += _mermaid(outlines, rows)
    out += ["", "## Findings", ""] + ([f"- {f}" for f in found] or ["- none"])
    top = Counter(r["target"] for r in rows if r["kind"] in ("statute", "section", "resolution"))
    out += ["", "## Most cited", "", "| Target | References | From |", "|---|---:|---|"]
    for target, n in top.most_common(30):
        sources = sorted({r["source"] for r in rows if r["target"] == target})
        out.append(f"| {target} | {n} | {', '.join(sources)[:120]} |")
    path = Path(data_dir) / "reports" / "references.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(out) + "\n", encoding="utf-8")
    for o in outlines:
        _document_page(data_dir, o, by_source[o.key], [r for r in rows if r["target"].split("#")[0] == o.key and r["source"] != o.key])
    return path


def _document_page(data_dir: Path, outline: DocumentOutline, mine: list[dict[str, Any]], incoming: list[dict[str, Any]]) -> None:
    by_section: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in mine:
        by_section[r["source_section"]].append(r)
    into: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in incoming:
        into[r["target"].split("#")[1] if "#" in r["target"] else ""].append(r)
    out = [f"# {outline.title}", "", f"_{len(outline.sections)} sections; {len(mine)} references out; {len(incoming)} references in "
           f"from other documents. [All documents](../reports/references.md)_", ""]
    if into.get(""):
        out.append("**Cited by name:** " + ", ".join(sorted({r["source"] for r in into[""]})))
        out.append("")
    for s in outline.sections:
        head = "#" * min(s.depth + 1, 6)
        out.append(f"{head} {s.number + ' ' if s.number else ''}{s.title[:100]}")
        refs = by_section.get(s.name, [])
        if refs:
            out.append("")
            out.append("Cites: " + "; ".join(f"{r['target']}" + (f" ({r['relation']})" if r["relation"] != "cites" else "")
                                          + ("" if r["status"] in ("found", "law on disk") else f" [{r['status']}]") for r in refs))
        if s.number and into.get(s.number):
            out.append("")
            out.append("Cited by: " + "; ".join(sorted({f"{r['source']} {r['source_section']}".strip() for r in into[s.number]})))
        out.append("")
    (outline_dir(data_dir) / f"{outline.key}.md").write_text("\n".join(out), encoding="utf-8")


def section_lines(outlines: list[DocumentOutline], rows: list[dict[str, Any]], target: str) -> list[str]:
    key, number = section_target(target)
    outline = next((o for o in outlines if o.key == key), None)
    if outline is None:
        return [f"no outline for {key}"]
    section = outline.section(number)
    if section is None:
        return [f"{outline.title} has no section {number}"]
    out = [f"{outline.title} {section.number} {section.title}", "", " ".join(outline.text_of(section).split())[:2500], ""]
    out.append("Cites:")
    out += [f"  - {r['target']} ({r['relation']}; {r['status']})" for r in rows
            if r["source"] == key and r["source_section"] == section.name] or ["  - nothing"]
    out.append("Cited by:")
    out += [f"  - {r['source']} {r['source_section']}: \"{r['quote'][:200]}\"" for r in cited_by(rows, target) if r["source"] != key
            or r["source_section"] != section.name] or ["  - nothing"]
    return out


__all__ = ["build", "load", "references", "resolve", "findings", "run", "report", "cited_by", "load_rows", "section_lines",
           "outline_lines"]
