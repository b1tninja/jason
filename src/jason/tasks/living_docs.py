"""Keep a document as amended: read its sources, apply the instruments in effect, check, and write the current text.

A ``LivingDocument`` row in the specification names the base text, each amendment and where its marked words are read,
the editorial corrections, the rule rows that copy its terms, and the working copy a person keeps by hand. ``build``:

- reads the base and each instrument. A library extract must still have the digest a person reviewed (``SourceRef.
  sha256``); a changed file is held out and reported. A Doc is read at its current revision, through the Docs API
  (read-only) or, with no client, from the copy the last read saved under ``data/living/<key>/sources``;
- consolidates (``living.consolidate``): drafts are listed, not applied, and every surprise is a finding;
- checks the rule rows against the current words (``living.check_text``) and, given the working copy, where it drifts.

``write`` puts the current text in ``data/living/<key>/current.md`` and the findings beside it. Comments on the working
copy are read (Drive's comments list, read-only) into annotations kept in ``data/annotations/<key>.json``; a person may
change an annotation's kind there, and a later import keeps it. jason never edits the working copy or its comments.
"""

from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from jason.community.living import (Annotation, AnnotationKind, AmendmentFinding, CurrentDocument, Instrument,
                                    LivingDocument, Placed, SourceKind, SourceRef, TextCheck, check_text, consolidate,
                                    drift, operations_from_doc, operations_from_text, place, standing_of)
from jason.community.outlines import DocumentOutline, outline_from_doc, outline_from_text

# An OCR extract puts a section's label on its own line ("(a)" then the words): join them so the outline reads them.
_LONE_LABEL = re.compile(r"(?m)^(\(\s*[a-z0-9]{1,4}\s*\)|\d+\.\d+)\s*\n(?=\S)")


def living_dir(data_dir: Path, key: str) -> Path:
    return Path(data_dir) / "living" / key


def prepare_extract(raw: str) -> str:
    return _LONE_LABEL.sub(r"\1 ", raw)


def library_text(data_dir: Path, path: str) -> tuple[str, str] | None:
    """A library file's text extract and its digest, by library path; None when the library has no such file."""
    db = Path(data_dir) / "library" / "library.db"
    if not db.is_file():
        return None
    with sqlite3.connect(f"{db.resolve().as_uri()}?mode=ro", uri=True) as conn:
        row = conn.execute("SELECT id, sha256 FROM documents WHERE path = ?", (path,)).fetchone()
    if row is None:
        return None
    text = Path(data_dir) / "library" / "text" / f"{row[0]}.txt"
    return (text.read_text(encoding="utf-8", errors="replace"), str(row[1] or "")) if text.is_file() else None


def doc_json(ref: str, cache: Path, docs: Any = None) -> dict[str, Any] | None:
    """A Google Doc as the Docs API returns it (read-only), saved to ``cache``; with no client, the saved copy."""
    path = cache / f"{ref}.json"
    if docs is not None:
        doc = docs.get(ref)
        cache.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(doc), encoding="utf-8")
        return doc
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None


@dataclass
class Built:
    living: LivingDocument
    current: CurrentDocument
    held: list[str] = field(default_factory=list)              # sources not read, and why
    revisions: dict[str, str] = field(default_factory=dict)    # a Doc's revision, by instrument key
    checks: list[tuple[TextCheck, bool]] = field(default_factory=list)
    drift: list[AmendmentFinding] = field(default_factory=list)


def _read(ref: SourceRef, data_dir: Path, cache: Path, docs: Any) -> tuple[str, Any, str]:
    """("doc", json, revision) or ("text", text, "") or ("held", reason, "")."""
    if ref.kind is SourceKind.DOC:
        doc = doc_json(ref.ref, cache, docs)
        if doc is None:
            return "held", f"Doc {ref.ref} not read yet (jason living KEY --fetch)", ""
        return "doc", doc, str(doc.get("revisionId") or "")
    found = library_text(data_dir, ref.ref)
    if found is None:
        return "held", f"{ref.ref}: not in the library (jason library)", ""
    text, digest = found
    if ref.sha256 and digest != ref.sha256:
        return "held", f"{ref.ref}: the file changed since it was reviewed (sha256 {digest[:12]}, pinned {ref.sha256[:12]})", ""
    return "text", text, ""


def build(living: LivingDocument, data_dir: Path, *, docs: Any = None, as_of: date | None = None,
          working: bool = False, all_sections: bool = False) -> Built:
    """The current text of ``living`` from its sources. ``docs`` (a Docs client) reads the Docs afresh; without it the
    copies saved by the last read are used. ``working`` also compares the working copy: the sections an amendment set,
    or with ``all_sections`` every section (where a base read by OCR differs mostly by the OCR's slips)."""
    cache = living_dir(data_dir, living.key) / "sources"
    kind, base, _ = _read(living.base, data_dir, cache, docs)
    if kind == "held":
        raise ValueError(f"the base text cannot be read: {base}")
    outline = (outline_from_doc(base, key=living.key, title=living.title, kind=living.kind.value) if kind == "doc"
               else outline_from_text(prepare_extract(base), key=living.key, title=living.title, kind=living.kind.value))
    held, revisions, instruments = [], {}, []
    for li in living.instruments:
        kind, body, revision = _read(li.source, data_dir, cache, docs)
        if kind == "held":
            held.append(f"{li.key}: {body}")
            continue
        if revision:
            revisions[li.key] = revision
        ops = operations_from_doc(body) if kind == "doc" else operations_from_text(body)
        d = li.document
        instruments.append(Instrument(li.key, living.key, standing_of(d), ops, getattr(d, "title", "") or li.key,
                                      adopted=getattr(d, "adopted", None), recorded=getattr(d, "recorded", None),
                                      number=getattr(d, "recorder_number", "") or ""))
    current = consolidate(outline, instruments, as_of=as_of, base_from=living.base_from,
                          corrections=living.corrections)
    out = Built(living, current, held, revisions, check_text(current, living.checks))
    if working and living.working_doc:
        copy = working_copy(living, data_dir, docs=docs)
        if copy is None:
            out.held.append("the working copy: not read yet (jason living KEY --fetch)")
        else:
            out.drift = drift(current, copy, label="the working copy", amended_only=not all_sections)
    return out


def working_copy(living: LivingDocument, data_dir: Path, *, docs: Any = None) -> DocumentOutline | None:
    doc = doc_json(living.working_doc, living_dir(data_dir, living.key) / "sources", docs)
    return outline_from_doc(doc, key=living.key, title=living.title, kind=living.kind.value) if doc else None


def write(built: Built, data_dir: Path) -> Path:
    """The current text as Markdown, and the findings, checks, and drift as JSON beside it."""
    folder = living_dir(data_dir, built.living.key)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "current.md"
    path.write_text(built.current.markdown(), encoding="utf-8")
    report = {
        "key": built.living.key, "built": date.today().isoformat(), "held": built.held, "revisions": built.revisions,
        "applied": [i.describe() for i in built.current.applied],
        "pending": [i.describe() for i in built.current.pending],
        "findings": [f.line() for f in built.current.findings],
        "checks": [{"section": c.section, "expect": c.expect, "rule": c.rule, "found": ok} for c, ok in built.checks],
        "drift": [f.line() for f in built.drift],
    }
    (folder / "report.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    return path


def lines(built: Built) -> list[str]:
    cur = built.current
    out = [f"{built.living.title}: {len(cur.provisions)} provisions; base: {cur.base}."]
    out += [f"  applied: {i.describe()}" for i in cur.applied]
    out += [f"  not in effect: {i.describe()}" for i in cur.pending]
    out += [f"  held: {h}" for h in built.held]
    amended = [p for p in cur.provisions if p.standing is not None]
    if amended:
        out.append("Set by an amendment: " + "; ".join(f"{p.number} ({p.set_by}, {p.dated})" for p in amended))
    if cur.findings:
        out += ["Findings while applying:"] + [f"  - {f.line()}" for f in cur.findings]
    for c, ok in built.checks:
        out.append(f"{'ok' if ok else 'MISMATCH'}: {c.rule} reads \"{c.expect}\" in {c.section}"
                   + ("" if ok else ": the rule row and the document disagree; a person decides which is wrong"))
    if built.drift and len(built.drift) > 40:
        only = sum("only in the copy" in f.detail for f in built.drift)
        missing = sum("missing from the copy" in f.detail for f in built.drift)
        out.append(f"The working copy differs in {len(built.drift)} sections ({only} only in the copy, {missing} only in "
                   f"the base, the rest in their words): mostly the base's OCR. Full list: data/living/"
                   f"{built.living.key}/report.json")
    elif built.drift:
        out += [f"The working copy differs in {len(built.drift)} places:"] + [f"  - {f.line()}" for f in built.drift]
    return out


# Comments on the working copy, read into annotations.

# The kind a comment most likely is, by its words: a person corrects it in data/annotations, and the import keeps it.
_KIND_RULES: tuple[tuple[re.Pattern[str], AnnotationKind], ...] = (
    (re.compile(r"^\s*(first|second|third|fourth|fifth)\s+amendment\s*$", re.I), AnnotationKind.PROVENANCE),
    (re.compile(r"\bold\s+(code|section|statute)\b|\brenumbered\b", re.I), AnnotationKind.OUTDATED_CITATION),
    (re.compile(r"\b(made|make)\s+(it\s+)?a\s+rule\b|\bfee schedule\b|\bpolicy\b", re.I), AnnotationKind.POLICY_CANDIDATE),
    (re.compile(r"\b(update|remove|removal|need to|set a|should be removed|to do)\b", re.I), AnnotationKind.ACTION_ITEM),
    (re.compile(r"\b(allowed|per\s+(sb|ab)\s*\d+|can'?t|cannot|not permitted|we read|interpret)", re.I), AnnotationKind.INTERPRETATION),
    (re.compile(r"\?\s*$"), AnnotationKind.QUESTION),
)


def kind_of(content: str, quote: str) -> AnnotationKind:
    for pattern, kind in _KIND_RULES:
        if pattern.search(content):
            return kind
    # An abbreviation spelled out ("FHA" -> "Federal Housing Administration (FHA)").
    if quote.strip().isupper() and len(quote.strip()) <= 8 and quote.strip() in content:
        return AnnotationKind.DEFINITION
    return AnnotationKind.CONTEXT


def comments_to_annotations(comments: list[dict[str, Any]], copy: DocumentOutline | None) -> list[Annotation]:
    """Drive comments (``comments.list``) as annotations, each placed on the working copy's section that holds its
    quoted words."""
    sections = sorted(copy.sections, key=lambda s: s.start) if copy else []
    squash = lambda text: re.sub(r"\s+", " ", text.replace(" ", " ")).strip()     # noqa: E731
    owns = [(s.number, squash(copy.text[s.start: sections[k + 1].start if k + 1 < len(sections) else len(copy.text)]))
            for k, s in enumerate(sections)] if copy else []

    def section_of(quote: str) -> str:
        """The deepest numbered section whose own words hold the quote's first words, whitespace aside."""
        want = squash(quote)[:80]
        if not want:
            return ""
        return next((number for number, own in owns if number and want in own), "")

    out = []
    for c in comments:
        if c.get("deleted"):
            continue
        quote = str((c.get("quotedFileContent") or {}).get("value") or "")
        replies = "; ".join(str(r.get("content") or "") for r in c.get("replies") or [] if r.get("content"))
        text = str(c.get("content") or "") + (f" (replies: {replies})" if replies else "")
        written = str(c.get("createdTime") or "")[:10]
        out.append(Annotation(section_of(quote), quote, kind_of(str(c.get("content") or ""), quote), text,
                              author=str((c.get("author") or {}).get("displayName") or ""),
                              written=date.fromisoformat(written) if written else None,
                              source=f"comment:{c.get('id')}", resolved=bool(c.get("resolved"))))
    return out


def annotations_path(data_dir: Path, key: str) -> Path:
    return Path(data_dir) / "annotations" / f"{key}.json"


def save_annotations(data_dir: Path, key: str, found: list[Annotation]) -> list[Annotation]:
    """Merge by ``source``: a new comment is added, a known one keeps the kind a person set, and its words update."""
    path = annotations_path(data_dir, key)
    old = {a["source"]: a for a in json.loads(path.read_text(encoding="utf-8"))} if path.is_file() else {}
    merged = []
    for a in found:
        kept = old.get(a.source)
        kind = AnnotationKind(kept["kind"]) if kept and kept.get("kind_set_by_person") else a.kind
        merged.append(Annotation(a.section, a.quote, kind, a.text, a.author, a.written, a.source, a.resolved))
    rows = []
    for a in merged:
        row = {**asdict(a), "kind": a.kind.value, "written": a.written.isoformat() if a.written else None}
        if old.get(a.source, {}).get("kind_set_by_person"):
            row["kind_set_by_person"] = True
        rows.append(row)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows, indent=1), encoding="utf-8")
    return merged


def load_annotations(data_dir: Path, key: str) -> list[Annotation]:
    path = annotations_path(data_dir, key)
    if not path.is_file():
        return []
    return [Annotation(r["section"], r["quote"], AnnotationKind(r["kind"]), r["text"], r.get("author", ""),
                       date.fromisoformat(r["written"]) if r.get("written") else None, r.get("source", ""),
                       bool(r.get("resolved"))) for r in json.loads(path.read_text(encoding="utf-8"))]


def annotation_lines(placed: list[Placed] | list[tuple[Placed, str]]) -> list[str]:
    """Orphans first: a note whose words are gone is a finding for a person."""
    pairs = [x if isinstance(x, tuple) else (x, "current") for x in placed]
    labels = {id(p): label for p, label in pairs}
    out = []
    for p in sorted((p for p, _ in pairs), key=lambda x: (x.placement.value != "orphaned", x.annotation.kind.value)):
        a = p.annotation
        where = p.section or a.section or "?"
        quote = f' on "{a.quote[:60]}"' if a.quote else ""
        on = f" in the {labels.get(id(p))}" if labels.get(id(p)) == "working copy" else ""
        out.append(f"- [{a.kind.value}; {p.placement.value} {where}{on}]{quote}: {a.text[:160]}"
                   + (f" ({a.written})" if a.written else ""))
    return out


def place_annotations(current: CurrentDocument, copy: DocumentOutline | None, found: list[Annotation]
                      ) -> list[tuple[Placed, str]]:
    """Each annotation placed on the current text, else on the working copy (where a base read by OCR garbles the
    quoted words). Returns (placement, where): "current", "working copy", or "" for an orphan on both."""
    from jason.community.living import CurrentDocument as _Current, Placement, provisions_of

    first = place(current, found)
    copy_doc = _Current(copy.key, copy.title, "the working copy", provisions_of(copy)) if copy else None
    out = []
    for p in first:
        if p.placement is not Placement.ORPHANED or copy_doc is None:
            out.append((p, "current" if p.placement is not Placement.ORPHANED else ""))
            continue
        again = place(copy_doc, [p.annotation])[0]
        out.append((again, "working copy") if again.placement is not Placement.ORPHANED else (p, ""))
    return out


__all__ = ["Built", "annotation_lines", "build", "place_annotations", "comments_to_annotations", "doc_json", "kind_of", "library_text",
           "lines", "load_annotations", "place", "prepare_extract", "save_annotations", "working_copy", "write"]
