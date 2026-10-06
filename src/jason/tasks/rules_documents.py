"""The Rules document and the owner's manual template on disk (docs/document-templates.md, section 11).

``prepare`` runs ``jason manual --render``'s own pass (the same classification, passages, and sources), reads the rule
records (stored in ``data/rule-records/<document>.json`` when a person keeps them as data, else derived from the
classification), and the adoption record. ``render`` writes a definition's Markdown, HTML, and part map to ``data/drafts``.
``prove_rules`` compares the Rules document's words with ``jason manual --render``'s ``rules-and-regulations.md``;
``prove_switch`` renders the owner's manual with its rules read from the Rules document and compares it with the manual
read from the classification. Reading and writing under ``data/`` only: nothing is written to Drive, PayHOA, or the mail.
"""

from __future__ import annotations

import difflib
import json
import re
from dataclasses import dataclass, field, replace
from datetime import date
from pathlib import Path
from typing import Any

from jason.community.document_templates import (LAYOUTS, Assembly, DocumentDefinition, HtmlRenderer, MarkdownRenderer, PLAIN,
                                                assemble, check, manual_context, part_map)
from jason.community.manual import AdoptionEvent, ManualError, words
from jason.community.rules_document import (MANUAL_TEMPLATE_KEY, RULES_KEY, ManualDocument, RuleBook, RulesContext,
                                            RulesDocumentSource, adoption_status, derive_book, manual_template_definition,
                                            rules_definition, rules_section_check)

DEFINITIONS = (RULES_KEY, MANUAL_TEMPLATE_KEY)


def records_path(data_dir: Path, document: str) -> Path:
    return Path(data_dir) / "rule-records" / f"{document}.json"


def load_book(path: Path) -> RuleBook | None:
    """The rule records a person keeps as data; None when there is no file."""
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return RuleBook.from_dict(raw, source=f"stored in {path}")


def save_book(book: RuleBook, path: Path, *, overwrite: bool = False) -> Path:
    """Write the records. An existing file is never replaced unless ``overwrite``: it is where a person's edits live."""
    path = Path(path)
    if path.exists() and not overwrite:
        raise ManualError(f"{path} already exists: it holds the rule records as a person keeps them; not overwritten")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(book.to_dict(), indent=1, ensure_ascii=False), encoding="utf-8")
    return path


@dataclass
class Prepared:
    data_dir: Path
    community: Any
    made: dict[str, Any]
    result: Any
    outline: Any
    spec: Any
    source: Any
    values: dict[str, str]
    events: list[AdoptionEvent]
    book: RuleBook
    as_of: date
    drafts: Path
    documents: list[ManualDocument] = field(default_factory=list)


def _ids(data_dir: Path, document: str) -> Any:
    try:
        from jason.tasks.permanent_ids import load

        return load(data_dir, document)
    except Exception:                                               # noqa: BLE001 - a miss stays a miss
        return None


def build_book(data_dir: Path, made: dict[str, Any], result: Any, outline: Any, spec: Any, events: list[AdoptionEvent],
               records: str = "auto") -> RuleBook:
    """The rule records: stored (``data/rule-records``) when a person keeps them and ``records`` allows, else derived from
    the classification with the official rules' own sources (``made`` is ``jason.tasks.manual.render``'s result)."""
    stored = load_book(records_path(data_dir, spec.document)) if records != "derived" else None
    if records == "stored" and stored is None:
        raise ManualError(f"no stored rule records at {records_path(data_dir, spec.document)} "
                          "(jason document-template rules-and-regulations --export-records writes the first ones)")
    return stored or derive_book(result, spec, made["rules_source"], outline.text, passages=made["passages"],
                                 ids=_ids(data_dir, spec.document), events=events)


def prepare(data_dir: Path | None = None, community: Any = None, *, as_of: date | None = None, out_dir: Path | None = None,
            records: str = "auto") -> Prepared:
    """The manual's pass, the adoption record, and the rule records. ``records``: ``auto`` (stored when the file is there,
    else derived), ``stored`` (the file, or an error), or ``derived`` (always from the classification)."""
    from jason.tasks import manual as task

    data_dir = Path(data_dir) if data_dir is not None else task.default_data_dir()
    if community is None:
        from jason.community import community as active

        community = active()
    made = task.render(data_dir, community, out_dir=out_dir)
    result, outline, spec = task.classify(data_dir, community)
    source = task.DiskSource(data_dir, community, spec, outline)
    values = task._values(community, outline, spec, basis=False)
    values.setdefault("RULES_TITLE", spec.rules_title)
    values.setdefault("MANUAL_TITLE", spec.manual_title)
    events = task.adoption_history(data_dir, community, spec)
    book = build_book(data_dir, made, result, outline, spec, events, records)
    documents = list(getattr(community, "manual_documents", lambda: ())())
    return Prepared(data_dir, community, made, result, outline, spec, source, values, events, book, as_of or date.today(),
                    made["paths"]["manual"].parent, documents)


def directory(prepared: Prepared) -> list[Any]:
    """The directory's people: those the private facts list, then each office holder the profile has who is not listed, as
    an entry nobody has agreed to publish, so an owners' document says "(not published)" and never "(vacant)" for a seat
    that is held."""
    from jason.community.document_templates import DirectoryEntry
    from jason.tasks.document_templates import directory_entries

    try:
        entries = list(directory_entries())
    except Exception:                                               # noqa: BLE001 - the private facts are not there
        entries = []
    have = {e.role for e in entries}
    try:
        officers = prepared.community.officers()
    except Exception:                                               # noqa: BLE001
        officers = ()
    for o in officers:
        role = getattr(o.role, "value", str(o.role))
        if role not in have and o.name:
            entries.append(DirectoryEntry(role, o.name, False))
            have.add(role)
    return entries


def forms_of(prepared: Prepared) -> dict[str, Any]:
    try:
        return {getattr(t.key, "value", str(t.key)): t for t in prepared.community.forms()}
    except Exception:                                               # noqa: BLE001 - a form with no slot is not here
        return {}


def identity_keys(prepared: Prepared) -> set[str]:
    try:
        return set(prepared.community.identity().values())
    except Exception:                                               # noqa: BLE001
        return set()


def context(prepared: Prepared, *, mode: str = "full", notes: bool = True, rules_url: str = "", template_form: bool = False,
            source: Any = None) -> Any:
    """The context a definition renders in. In the template form the association's own values (its name) are left as
    ``{TOKENS}`` to be filled when the Doc is copied; every other value is the profile's."""
    values = dict(prepared.values)
    values["ADOPTION_STATUS"] = adoption_status(prepared.events, prepared.as_of)
    if rules_url:
        values["RULES_DOC_URL"] = rules_url
    if template_form:
        for key in identity_keys(prepared):
            values.pop(key, None)
    else:
        values["AS_OF"] = prepared.as_of.isoformat()
    ctx = manual_context(prepared.result, prepared.spec, source or prepared.source, prepared.outline.text, values=values,
                         passages=prepared.made["passages"], as_of=prepared.as_of)
    ctx.rules = RulesContext(prepared.book, mode, notes)
    ctx.forms = forms_of(prepared)
    ctx.directory = directory(prepared)
    return ctx


def definition(prepared: Prepared, key: str, layout: str = "book") -> DocumentDefinition:
    if layout not in LAYOUTS:
        raise ValueError(f"no layout {layout!r}; choose " + ", ".join(LAYOUTS))
    chosen = LAYOUTS[layout]
    if key == RULES_KEY:
        return rules_definition(prepared.book, chosen)
    if key == MANUAL_TEMPLATE_KEY:
        form = "architectural-application"
        return manual_template_definition(chosen, form=form if form in forms_of(prepared) else "")
    raise ValueError(f"no document {key!r}; choose " + ", ".join(DEFINITIONS))


def roles_of(prepared: Prepared) -> tuple[str, ...]:
    """The roles the directory lists: the offices the profile has, in order, so a vacant one shows."""
    try:
        return tuple(dict.fromkeys(o.role.value for o in prepared.community.officers()))
    except Exception:                                               # noqa: BLE001
        return ()


def render(prepared: Prepared, key: str, *, layout: str = "book", mode: str = "full", notes: bool = True,
           rules_url: str = "") -> dict[str, Any]:
    """A definition's Markdown, HTML, and part map, written beside ``jason manual --render``'s drafts."""
    from jason.community.document_templates import DirectoryBlock

    d = definition(prepared, key, layout)
    roles = roles_of(prepared)
    if roles:
        d = replace(d, items=tuple(replace(b, roles=roles) if isinstance(b, DirectoryBlock) else b for b in d.items))
    ctx = context(prepared, mode=mode, notes=notes, rules_url=rules_url, template_form=False)
    assembly = assemble(d, ctx)
    chosen = LAYOUTS[layout]
    md = MarkdownRenderer().render(assembly, chosen)
    found = check(assembly, md)
    paths = {"markdown": prepared.drafts / f"{key}.document.md", "html": prepared.drafts / f"{key}.document.html",
             "parts": prepared.drafts / f"{key}.parts.json"}
    paths["markdown"].write_text(md, encoding="utf-8")
    paths["html"].write_text(HtmlRenderer().render(assembly, chosen), encoding="utf-8")
    paths["parts"].write_text(json.dumps(part_map(assembly), indent=1), encoding="utf-8")
    return {"paths": paths, "check": found, "assembly": assembly, "markdown": md}


# ---------------------------------------------------------------------------------------------------------------------
# The proofs


@dataclass
class RulesProof:
    same: int = 0
    labeled: list[tuple[str, str]] = field(default_factory=list)       # (line, why it differs)
    unlabeled: list[str] = field(default_factory=list)

    @property
    def equal(self) -> bool:
        return not self.unlabeled


def _norm(line: str) -> str:
    line = re.sub(r"^#+\s+", "", line.strip())
    return " ".join(words(line))


LABELS_OFFICIAL = (
    (re.compile(r"^_\[(?:Guidance|A policy|[A-Z][a-z]+) left in the"), "guidance left in the manual: not a rule"),
    (re.compile(r"published as its own document"), "listed in the appendix of policies published apart instead"),
    (re.compile(r"^_The operating rules adopted by the board"), "the official rules' introduction: jason's note on the extraction"),
)
LABELS_DOCUMENT = (
    (re.compile(r"^\*\*DRAFT FOR BOARD ADOPTION"), "the status line {ADOPTION_STATUS}"),
    (re.compile(r"^_Adopted by the board"), "the status line {ADOPTION_STATUS}"),
    (re.compile(r"^The rules$"), "the heading over the rules"),
    (re.compile(r"^Appendix: policies published apart"), "the appendix of policies published apart"),
    (re.compile(r"^These policies are separate documents"), "the appendix of policies published apart"),
    (re.compile(r"^- .* \(document key `[^`]+`\)$"), "the appendix of policies published apart"),
)


def prove_rules(official: str, document_markdown: str, values: dict[str, str]) -> RulesProof:
    """The Rules document's lines beside ``jason manual --render``'s ``rules-and-regulations.md``. A line only one has must
    be one of the labeled differences (the title block, the status line, the appendix, the manual's introduction and its
    notes on guidance left in the manual); anything else is unlabeled and the proof fails."""
    a = [_norm(ln) for ln in official.splitlines() if ln.strip()]
    b = [_norm(ln) for ln in document_markdown.splitlines() if ln.strip()]
    titles = {_norm(values.get(k, "")) for k in ("ASSOCIATION_NAME", "RULES_TITLE") if values.get(k)}
    out = RulesProof()
    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            out.same += i2 - i1
            continue
        for line, raw in [(x, "official") for x in a[i1:i2]] + [(x, "document") for x in b[j1:j2]]:
            if line in titles:
                out.labeled.append((line, "the title block"))
                continue
            table = LABELS_OFFICIAL if raw == "official" else LABELS_DOCUMENT
            why = next((w for rx, w in table if rx.search(line)), "")
            if why:
                out.labeled.append((line[:90], why))
            else:
                out.unlabeled.append(f"{raw}: {line[:120]}")
    return out


@dataclass
class SwitchProof:
    """The manual with its rules read from the Rules document. ``section`` says every rule it places has its record's words;
    ``identical`` says the Markdown equals the manual read from the classification; where it does not, each piece that differs
    from the working Doc is in ``labeled`` (the Rules document holds no pending suggestion, so a suggestion in the Doc is the
    usual cause) and ``unlabeled`` is a defect."""

    identical: bool
    section: Any                             # RulesSectionCheck
    labeled: list[str] = field(default_factory=list)
    unlabeled: list[str] = field(default_factory=list)

    @property
    def clean(self) -> bool:
        return self.section.identical and not self.unlabeled


def prove_switch(prepared: Prepared) -> SwitchProof:
    """The owner's manual rendered twice from the same classification: its rules read from the classification (what
    ``jason manual --render`` does) and read from the Rules document's records. The words of every rule the manual places must
    equal its record's, and the Markdown must be identical unless a record's words were changed (a labeled difference)."""
    from jason.tasks.document_templates import manual_definition

    base = assemble(manual_definition(PLAIN), manual_context(prepared.result, prepared.spec, prepared.source,
                                                           prepared.outline.text, values=prepared.values,
                                                           passages=prepared.made["passages"], as_of=prepared.as_of))
    switched_source = RulesDocumentSource(prepared.source, prepared.book, prepared.as_of)
    switched = assemble(manual_definition(PLAIN), manual_context(prepared.result, prepared.spec, switched_source,
                                                               prepared.outline.text, values=prepared.values,
                                                               passages=prepared.made["passages"], as_of=prepared.as_of))
    same = MarkdownRenderer().render(base, PLAIN) == MarkdownRenderer().render(switched, PLAIN)
    section = rules_section_check(switched.chunks, prepared.book, prepared.as_of)
    from jason.community.manual import check as manual_check

    found = manual_check(switched.chunks, prepared.outline.text)
    return SwitchProof(same, section, [f"{d.segment}: {d.label}" for d in found.labeled],
                       [f"{d.segment}: {d.detail}" for d in found.unlabeled])


__all__ = ["DEFINITIONS", "Prepared", "RulesProof", "SwitchProof", "context", "definition", "directory", "load_book",
           "prepare", "prove_rules", "prove_switch", "records_path", "render", "roles_of", "save_book"]
