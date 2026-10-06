"""Document templates on disk: the directory's private facts, the owner's manual as a definition, and its renderings.

- ``directory_entries`` reads the people a directory block prints from the profile's private facts (``data/spec``, topic
  ``directory``, through ``jason.community.private``), never from a tracked file. Each entry is
  ``{"role", "name", "publish", "contacts": {"email": {"value", "publish"}}}``; a field with no flag is not published.
- ``manual_definition`` is the owner's manual base template (``src/jason/templates/manual/owners-manual.md``) as a
  ``DocumentDefinition``.
- ``render_manual`` writes the manual from that definition beside ``jason manual --render``'s own output, compares the two
  word for word, and writes the part map. Reading only: nothing is written to Drive, PayHOA, or the mail, and the Doc is
  never edited. Phase 1 writes under ``data/drafts``.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

from jason.community.document_templates import (LAYOUTS, Assembly, ContactField, DirectoryEntry, DocumentCheck,
                                                DocumentDefinition, HtmlRenderer, Layout, MarkdownRenderer, PLAIN,
                                                assemble, check, definition_from_template, manual_context, part_map)


def directory_entries(profile: str = "") -> list[DirectoryEntry]:
    """The directory's people from the profile's private facts; none when the topic is not there (a miss stays a miss)."""
    from jason.community.private import facts

    out = []
    for raw in facts("directory", [], profile=profile) or []:
        contacts = []
        for kind, value in (raw.get("contacts") or {}).items():
            if isinstance(value, dict):
                contacts.append(ContactField(kind, str(value.get("value", "")), bool(value.get("publish"))))
            else:
                contacts.append(ContactField(kind, str(value), False))
        out.append(DirectoryEntry(str(raw.get("role", "")), str(raw.get("name", "")), bool(raw.get("publish")),
                                  tuple(contacts)))
    return out


def manual_definition(layout: Layout = PLAIN) -> DocumentDefinition:
    from jason.tasks.manual import template

    return definition_from_template(template("owners-manual.md"), "owners-manual", "Owner's Manual", layout,
                                    kind="guide")


def render_manual(data_dir: Path | None = None, community: Any = None, *, layout: str = "plain",
                  out_dir: Path | None = None, as_of: date | None = None) -> dict[str, Any]:
    """The owner's manual from its definition. Runs ``jason manual --render`` first (the same classification, passages,
    and sources), renders the definition from them, and reports whether the Markdown equals the manual that render wrote;
    then writes ``owners-manual.document.md``, ``.html``, and ``owners-manual.parts.json`` beside it."""
    from jason.tasks import manual as task

    data_dir = Path(data_dir) if data_dir is not None else task.default_data_dir()
    if community is None:
        from jason.community import community as active

        community = active()
    if layout not in LAYOUTS:
        raise ValueError(f"no layout {layout!r}; choose " + ", ".join(LAYOUTS))
    made = task.render(data_dir, community, out_dir=out_dir)
    result, outline, spec = task.classify(data_dir, community)
    source = task.DiskSource(data_dir, community, spec, outline)
    plain = task._values(community, outline, spec, basis=False)
    ctx = manual_context(result, spec, source, outline.text, values=plain, passages=made["passages"],
                         as_of=as_of or date.today())
    assembly = assemble(manual_definition(LAYOUTS[layout]), ctx)
    chosen = LAYOUTS[layout]
    md = MarkdownRenderer().render(assembly, chosen)
    old = made["paths"]["manual"].read_text(encoding="utf-8")
    same = MarkdownRenderer().render(assembly, PLAIN) == old
    found = check(assembly, md)
    drafts = made["paths"]["manual"].parent
    paths = {"markdown": drafts / "owners-manual.document.md", "html": drafts / "owners-manual.document.html",
             "parts": drafts / "owners-manual.parts.json"}
    paths["markdown"].write_text(md, encoding="utf-8")
    paths["html"].write_text(HtmlRenderer().render(assembly, chosen), encoding="utf-8")
    paths["parts"].write_text(json.dumps(part_map(assembly), indent=1), encoding="utf-8")
    return {"paths": paths, "identical": same, "check": found, "assembly": assembly}


def summary(found: DocumentCheck) -> list[str]:
    return [f"blocks placed: {len(found.placed)}", f"gaps: {len(found.gaps)}", f"unlabeled pieces: {len(found.unlabeled)}",
            f"open tokens: {len(found.open_tokens)}"]


__all__ = ["Assembly", "directory_entries", "manual_definition", "render_manual", "summary"]
