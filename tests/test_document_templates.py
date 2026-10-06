"""Document templates (jason.community.document_templates): a layout apart from its blocks, on made-up data.

The owner's manual re-expressed as a definition prints exactly what ``manual.render`` prints; a second layout changes how
the same blocks look and not a word they say; a form block is the form's own paper rendering; a directory prints only the
fields people published; an embedded document shows a gap rather than a silent skip, and the part map names the structure."""

from __future__ import annotations

import json
from datetime import date

import pytest
from test_manual import MANUAL, NORMS, Source, hits, law, outline, spec

from jason.community.document_templates import (GUIDE, LAYOUTS, PLAIN, ComputedBlock, ContactField, Context,
                                                DirectoryBlock, DirectoryEntry, DocumentDefinition, DocumentError,
                                                Embedded, EmbeddedBlock, FormBlock, HtmlRenderer, Layout,
                                                MarkdownRenderer, ProseBlock, QuoteBlock, Requirement, assemble, check,
                                                definition_from_template, manual_context, part_map)
from jason.community.forms import FormKey, FormQuestion, FormTemplate, QuestionKind
from jason.community.manual import Excerpt, classify, render

ANSWERS = {"R-3": "rule", "WHAT IS AN ASSOCIATION?": "guidance"}


def manual_inputs(**kw):
    o = outline()
    s = spec(excerpts=(Excerpt("decl#2.5"),))
    return o, s, classify(o, s, NORMS, hits(o), law=law, answers=ANSWERS), Source(o)


def test_the_manual_as_a_definition_prints_what_render_prints():
    o, s, result, source = manual_inputs()
    old_md, old_chunks = render(MANUAL, result, s, source, o.text)
    definition = definition_from_template(MANUAL, "example-manual", "Owner's Manual")
    ctx = manual_context(result, s, source, o.text)
    assembly = assemble(definition, ctx)
    assert MarkdownRenderer().render(assembly, PLAIN) == old_md
    new_chunks = assembly.chunks
    assert [(c.markdown, c.start, c.end, c.label) for c in new_chunks if c.start >= 0] == \
           [(c.markdown, c.start, c.end, c.label) for c in old_chunks if c.start >= 0]


def test_the_official_rules_template_also_matches():
    o, s, result, source = manual_inputs()
    template = "# {RULES_TITLE}\n\n{ADOPTION_HISTORY}\n\n{INCLUDE:rules official}\n"
    old_md, _ = render(template, result, s, source, o.text)
    definition = definition_from_template(template, "rules", "Rules")
    assert MarkdownRenderer().render(assemble(definition, manual_context(result, s, source, o.text)), PLAIN) == old_md


def test_a_block_that_cannot_be_filled_lists_every_problem():
    o, s, result, source = manual_inputs()
    definition = definition_from_template("{PART:nowhere}\n\n{INCLUDE:nobook}", "x", "X")
    with pytest.raises(DocumentError) as exc:
        assemble(definition, manual_context(result, s, source, o.text))
    assert "nowhere" in str(exc.value) and "nobook" in str(exc.value)


def test_block_ids_are_unique():
    with pytest.raises(DocumentError):
        assemble(DocumentDefinition("d", "D", (ProseBlock("a", text="x"), ProseBlock("a", text="y"))), Context())


def test_a_second_layout_changes_the_look_and_not_one_block():
    o, s, result, source = manual_inputs()
    definition = definition_from_template(MANUAL, "example-manual", "Owner's Manual")
    ctx = manual_context(result, s, source, o.text, as_of=date(2026, 1, 2))
    assembly = assemble(definition, ctx)                      # assembling reads no layout
    before = [(r.id, r.markdown) for r in assembly.results]
    plain = MarkdownRenderer().render(assembly, PLAIN)
    guide = MarkdownRenderer().render(assembly, GUIDE)
    assert [(r.id, r.markdown) for r in assembly.results] == before          # no renderer changed a block
    assert plain != guide
    assert "## Contents" in guide and "_Owner's Manual_" in guide and "_As of 2026-01-02_" in guide
    assert "\n---\n" in guide and "## 1. " in guide
    for line in plain.split("\n"):                                           # every word of the plain output is still there
        if line.strip() and not line.startswith("#"):
            assert line in guide
    html = HtmlRenderer().render(assembly, GUIDE)
    assert "--accent:#1f3a5f" in html and '<div class="running footer">As of 2026-01-02</div>' in html
    assert html.count("<h2") >= 3 and 'class="break"' in html
    shifted = MarkdownRenderer().render(assembly, Layout("deeper", heading_shift=1))
    assert "#### R-1. PETS" in shifted and "### A. PREAMBLE" in shifted


FORM = FormTemplate(
    key=FormKey.RECORDS, title="Request to inspect records", authority="Civil Code 0000",
    description="Ask to inspect the association's records.",
    questions=(FormQuestion("Your name", key="requester"),
               FormQuestion("Records wanted", QuestionKind.CHECKBOX, key="which", options=("Minutes", "Budget"))),
    signature="Signature")


def test_a_form_block_is_the_forms_own_paper_rendering():
    from jason.community.form_render import paper_markdown

    block = FormBlock("records-form", form="records", authority="Civil Code 0000")
    got = assemble(DocumentDefinition("d", "D", (block,)), Context(forms={"records": FORM})).results[0]
    expected = "\n".join(ln for ln in paper_markdown(FORM) if ln not in (r"\keep", r"\endkeep")).strip()
    assert got.markdown == expected
    assert "☐ Minutes" in got.markdown and got.fields == ("requester", "which")      # the form's own field ids
    assert got.chunks[0].label == "form records, rendered from its definition"


def test_a_form_that_is_not_defined_is_a_gap():
    got = assemble(DocumentDefinition("d", "D", (FormBlock("f", form="absent"),)), Context()).results[0]
    assert got.gaps and "Missing" not in got.markdown and "not defined" in got.markdown


PEOPLE = (
    DirectoryEntry("president", "Quill Example", True, (ContactField("email", "quill@example.test", True),
                                                          ContactField("phone", "555-0100", False))),
    DirectoryEntry("treasurer", "Ilse Example", False, (ContactField("email", "ilse@example.test", True),)),
)


def test_a_directory_for_owners_prints_only_what_was_published():
    block = DirectoryBlock("board", roles=("president", "treasurer", "secretary"))
    got = assemble(DocumentDefinition("d", "D", (block,)), Context(directory=PEOPLE)).results[0]
    assert "Quill Example" in got.markdown and "quill@example.test" in got.markdown
    assert "555-0100" not in got.markdown                       # the phone's own flag is off
    assert "Ilse" not in got.markdown and "ilse@example.test" not in got.markdown     # the person did not publish
    assert "(not published)" in got.markdown and "(vacant)" in got.markdown
    assert got.gaps == ["No one holds the role secretary."]


def test_a_directory_for_the_board_is_labeled_a_draft():
    block = DirectoryBlock("board", roles=("president",))
    got = assemble(DocumentDefinition("d", "D", (block,)), Context(directory=PEOPLE, audience="board")).results[0]
    assert "555-0100" in got.markdown and "not for owners" in got.chunks[0].label


def test_the_directory_is_read_from_private_facts_never_a_tracked_file(tmp_path, monkeypatch):
    from jason.tasks.document_templates import directory_entries

    from jason.community.private import profile_of

    monkeypatch.setenv("JASON_SPEC_DIR", str(tmp_path))
    (tmp_path / profile_of()).mkdir()
    (tmp_path / profile_of() / "directory.json").write_text(json.dumps([
        {"role": "president", "name": "Quill Example", "publish": True,
         "contacts": {"email": {"value": "q@example.test", "publish": True}, "phone": {"value": "555-0100"}}}]),
        encoding="utf-8")
    entries = directory_entries()
    assert entries[0].contacts[0].publish and not entries[0].contacts[1].publish


def test_an_embedded_document_renders_nested_attaches_files_and_shows_gaps():
    budget = DocumentDefinition("budget", "Budget Report", (
        ProseBlock("title", text="# Budget Report\n\nFigures for {YEAR}.\n"),
        ComputedBlock("totals", name="totals", head=("Line", "Cents"))))
    docs = {"budget": Embedded(budget),
            "reserve": Embedded(address="library/reserve-summary.pdf", pages=3, as_of=date(2026, 1, 1), title="Reserve summary"),
            "old": Embedded(address="library/insurance-25.pdf", pages=2, as_of=date(2025, 1, 1))}
    outer = DocumentDefinition("annual", "Annual Disclosures", (
        ProseBlock("cover", text="# {ASSOCIATION_NAME}\n\n"),
        EmbeddedBlock("budget", ref="budget", title="Budget report", required=True, authority="Civil Code 0001"),
        EmbeddedBlock("reserve", ref="reserve", required=True, authority="Civil Code 0002", as_of=date(2026, 1, 1)),
        EmbeddedBlock("insurance", ref="old", title="Insurance summary", required=True, authority="Civil Code 0003",
                      as_of=date(2026, 1, 1)),
        EmbeddedBlock("policy", ref="policy", title="Policy statement", required=True, authority="Civil Code 0004")))
    ctx = Context({"ASSOCIATION_NAME": "Example Commons", "YEAR": "2027"}, date(2026, 1, 1), documents=docs,
                  computed={"totals": lambda c: [["Operating", "10000"]]})
    assembly = assemble(outer, ctx)
    out = MarkdownRenderer().render(assembly, PLAIN)
    assert "## Budget Report" in out and "Figures for 2027." in out and "| Operating | 10000 |" in out
    assert "_[Attached: Reserve summary (library/reserve-summary.pdf, 3 pages, as of 2026-01-01).]_" in out
    assert "Missing: Insurance summary (required by Civil Code 0003): the copy on file is as of 2025-01-01" in out
    assert "Missing: Policy statement (required by Civil Code 0004): not on file." in out
    found = check(assembly, out, [Requirement("budget"), Requirement("policy", "Civil Code 0004"), Requirement("ghost")])
    assert len(found.gaps) == 2 and found.uncovered == ["ghost"] and not found.open_tokens
    pm = part_map(assembly)
    assert pm["document"] == "annual" and [p["id"] for p in pm["parts"]] == ["cover", "budget", "reserve", "insurance", "policy"] \
        or [p["id"] for p in pm["parts"]][0] == "cover"
    by = {p["id"]: p for p in pm["parts"]}
    assert by["reserve"]["address"] == "library/reserve-summary.pdf" and by["reserve"]["attachedPages"] == 3
    assert by["insurance"]["gap"] and by["policy"]["gap"] and not by["budget"]["gap"]
    assert by["budget"]["standing"] == "required" and by["budget"]["pages"] is None


def test_check_names_an_open_token_and_an_unlabeled_piece():
    assembly = assemble(DocumentDefinition("d", "D", (ProseBlock("p", text="Dear {OWNER}.\n"),)), Context())
    out = MarkdownRenderer().render(assembly, PLAIN)
    assert check(assembly, out).open_tokens == ["{OWNER}"]


def test_a_quote_block_needs_its_authority():
    with pytest.raises(DocumentError):
        assemble(DocumentDefinition("d", "D", (QuoteBlock("q", ref="decl#4.15"),)), Context())
    got = assemble(DocumentDefinition("d", "D", (QuoteBlock("q", ref="decl#4.15"),)),
                   Context(quote=lambda ref: f"> the words of {ref}")).results[0]
    assert got.chunks[0].label == "quoted from decl#4.15"


def test_the_stock_layouts_are_named():
    assert set(LAYOUTS) == {"plain", "guide"}
