"""The Rules document and the owner's manual template that refers to it (jason.community.rules_document, doc_output, and
jason.tasks.document_docs), on a made-up manual: the rules are records with stable ids, the manual refers to them instead of
retyping them, the status line is the adoption record's, and the Doc a definition makes has real named styles."""

from __future__ import annotations

import json
import re
from datetime import date

import pytest
from test_manual import NORMS, Source, hits, law, outline, spec

from jason.community import doc_output
from jason.community.document_templates import (BOOK, GUIDE, PLAIN, ComputedBlock, Context, DirectoryEntry, HtmlRenderer,
                                                MarkdownRenderer, assemble, check, manual_context, part_map)
from jason.community.manual import AdoptionAction, AdoptionEvent, Excerpt, classify
from jason.community.permanent_ids import IdTable, Name, SectionId
from jason.community.rules_document import (DRAFT_BANNER, MANUAL_TEMPLATE_KEY, RULES_KEY, ManualDocument, RuleBook,
                                            RuleRecord, RulesContext, RulesDocumentSource, RuleVersion, adoption_status,
                                            derive_book, manual_template_definition, rules_definition,
                                            rules_section_check)

ANSWERS = {"R-3": "rule", "WHAT IS AN ASSOCIATION?": "guidance"}
DAY = date(2026, 3, 1)


def inputs(**kw):
    o = outline()
    s = spec(excerpts=(Excerpt("decl#2.5"),), **kw)
    result = classify(o, s, NORMS, hits(o), law=law, answers=ANSWERS)
    return o, s, result, Source(o)


def book_of(events=(), ids=None):
    o, s, result, source = inputs()
    return derive_book(result, s, source, o.text, ids=ids, events=events), (o, s, result, source)


def values(**extra):
    return {"ASSOCIATION_NAME": "Example Commons", "RULES_TITLE": "Example Rules", "MANUAL_TITLE": "Example Manual",
            "AS_OF": DAY.isoformat(), "ADOPTION_STATUS": DRAFT_BANNER, **extra}


def ctx_for(book, parts, *, mode="full", vals=None, day=DAY, events=()):
    o, s, result, source = parts
    v = values(**(vals or {}))
    v["ADOPTION_STATUS"] = adoption_status(events, day)
    ctx = manual_context(result, s, source, o.text, values=v, as_of=day)
    ctx.rules = RulesContext(book, mode)
    return ctx


def render(definition, ctx, layout=PLAIN):
    assembly = assemble(definition, ctx)
    return assembly, MarkdownRenderer().render(assembly, layout)


# --- A. The Rules document ------------------------------------------------------------------------------------------


def test_the_rules_document_holds_the_rules_and_refers_to_the_policy():
    book, parts = book_of()
    assembly, md = render(rules_definition(book), ctx_for(book, parts))
    assert "### R-1. PETS" in md and "Pets shall be leashed in the common area." in md        # printed number, word for word
    assert "**a.** No pet shall be left alone on a deck." in md                              # a subdivision nested under it
    assert "It is recommended" not in md                                                      # guidance stays in the manual
    assert "The board shall give notice before a hearing." not in md and "First violation $25" not in md   # the policy is not copied
    assert "## Appendix: policies published apart" in md and "(document key `disc`)" in md   # ... it is named by its book key
    assert "Restates decl#4.7 (verbatim)" in md                                               # a copy the board adopted stays, named
    assert [a for a, _ in book.appendix] == ["disc", "coll"]
    assert check(assembly, md).clean


def test_every_rule_is_its_own_block_with_a_stable_id():
    ids = IdTable("rules", "example-manual", ids=[SectionId("rules@base/R-1", None, [Name("R-1")]),
                                                  SectionId("rules@base/R-2", None, [Name("R-2")])])
    book, parts = book_of(ids=ids)
    assert book.get("rules@base/R-1") is not None and book.get("rules@base/R-2") is not None     # the permanent id
    assert len({r.id for r in book.records}) == len(book.records)                                  # unique
    assert book.get("rules@base/R-1").number == "R-1" and book.get("rules@base/R-1").segment == "R-1"
    d = rules_definition(book)
    assembly = assemble(d, ctx_for(book, parts))
    rule_ids = [r.id for r in assembly.results if r.kind == "rule"]
    assert rule_ids == [f"rule:{r.id}" for r in book.records]
    pm = part_map(assembly)
    assert [p["id"] for p in pm["parts"] if p["kind"] == "rule"] == rule_ids
    assert next(p for p in pm["parts"] if p["id"] == "rule:rules@base/R-1")["source"] == "rule:rules@base/R-1"


def test_a_change_to_one_record_changes_both_documents_and_nothing_else():
    book, parts = book_of()
    ctx = ctx_for(book, parts)
    _, rules_before = render(rules_definition(book), ctx)
    _, manual_before = render(manual_template_definition(), ctx)
    target = next(r for r in book.records if r.number == "R-1")
    word = target.versions[0].text
    edited = replace_record(book, target.id, word.replace("leashed", "kept on a leash"))
    ctx2 = ctx_for(edited, parts)
    _, rules_after = render(rules_definition(edited), ctx2)
    _, manual_after = render(manual_template_definition(), ctx2)

    def changed(a, b):
        return [(x, y) for x, y in zip(a.splitlines(), b.splitlines()) if x != y]

    for before, after in ((rules_before, rules_after), (manual_before, manual_after)):
        assert len(before.splitlines()) == len(after.splitlines())
        diff = changed(before, after)
        assert len(diff) == 1 and "leashed" in diff[0][0] and "kept on a leash" in diff[0][1]
    assert "kept on a leash" in rules_after and "kept on a leash" in manual_after


def replace_record(book, id_, text):
    from dataclasses import replace

    out = RuleBook(list(book.records), list(book.appendix), list(book.loose), book.document, book.source)
    i = next(k for k, r in enumerate(out.records) if r.id == id_)
    r = out.records[i]
    out.records[i] = replace(r, versions=(replace(r.versions[0], text=text, words=text),))
    return out


def test_the_manual_template_refers_to_the_rules_and_never_contains_them():
    book, parts = book_of()
    definition = manual_template_definition()
    from jason.community.document_templates import ManualBlock

    assert not any(b.kind == "rule" or (isinstance(b, ManualBlock) and b.verb == "INCLUDE" and b.arg == "rules")
                   for b in definition.items)                                                  # no rule, no rules book
    ctx = ctx_for(book, parts, mode="index", vals={"RULES_DOC_URL": "https://docs.example.test/rules"})
    assembly, md = render(definition, ctx)
    assert "[Example Rules](https://docs.example.test/rules)" in md                            # the link
    assert "- R-1. PETS" in md and "- R-2. NOISE" in md                                        # numbers and titles only
    assert "Pets shall be leashed" not in md and "No Unit shall be altered" not in md
    full_ctx = ctx_for(book, parts, mode="full")
    _, full = render(definition, full_ctx)
    assert "Pets shall be leashed in the common area." in full                                # rendered from the records
    shifted = [ln for ln in full.splitlines() if ln.startswith("#### R-1")]
    assert shifted == ["#### R-1. PETS"]                                                       # one level under its heading
    rules_block = next(r for r in assembly.results if r.kind == "rules-reference")
    assert rules_block.address == RULES_KEY and rules_block.required


def test_the_manual_template_rules_are_the_rules_documents_words():
    book, parts = book_of()
    _, rules_md = render(rules_definition(book), ctx_for(book, parts))
    _, manual_md = render(manual_template_definition(), ctx_for(book, parts, mode="full"))
    for rec in book.records:
        for line in rec.versions[0].text.splitlines():
            if line.strip():
                assert line in rules_md and line.lstrip("#").strip() in manual_md.replace("#", "")


def test_a_record_with_no_version_in_force_that_day_is_a_visible_gap():
    book, parts = book_of(events=[AdoptionEvent(date(2026, 1, 10), AdoptionAction.ADOPTED, ("R-1",), "minutes")])
    rec = book.get(next(r.id for r in book.records if r.number == "R-1"))
    assert rec.versions[0].adopted == date(2026, 1, 10)                                        # from the adoption record
    early, parts_early = book, parts
    assembly = assemble(rules_definition(book), ctx_for(book, parts, day=date(2025, 12, 1)))
    gaps = [g for g in assembly.gaps if "R-1" in g]
    assert gaps and "no version of this rule on file is in force on 2025-12-01" in gaps[0]
    assert not [g for g in assemble(rules_definition(book), ctx_for(book, parts, day=DAY)).gaps if "R-1" in g]


def test_a_proposed_version_is_in_force_on_no_day():
    adopted = RuleVersion("Old words.", "Old words.", date(2020, 1, 1))
    proposed = RuleVersion("New words.", "New words.", None, proposed=True)
    rec = RuleRecord("r", "R-9", "R-9. TEST", 3, versions=(adopted, proposed))
    assert rec.version_on(DAY) == adopted and rec.version_on(None) == adopted
    later = RuleVersion("Newer words.", "Newer words.", date(2025, 6, 1))
    rec = RuleRecord("r", versions=(adopted, later, proposed))
    assert rec.version_on(date(2024, 1, 1)) == adopted and rec.version_on(DAY) == later
    assert RuleRecord("r", versions=(proposed,)).version_on(DAY) is None


# --- The status line -----------------------------------------------------------------------------------------------------


def test_the_draft_banner_is_there_until_an_adoption_event_is_on_record():
    book, parts = book_of()
    _, md = render(rules_definition(book), ctx_for(book, parts))
    assert DRAFT_BANNER in md and "not an adopted rule until the board adopts it (Civil Code 4350, 4355, 4360)" in md
    # an adoption of a part is not an adoption of the document
    part = [AdoptionEvent(date(2026, 1, 10), AdoptionAction.ADOPTED, ("R-1",), "minutes")]
    assert adoption_status(part, DAY) == DRAFT_BANNER
    # nor a notice, a delivery, or an adoption dated after the document's day
    other = [AdoptionEvent(date(2026, 1, 10), AdoptionAction.NOTICED, (RULES_KEY,), "notice"),
             AdoptionEvent(date(2026, 6, 1), AdoptionAction.ADOPTED, (RULES_KEY,), "minutes")]
    assert adoption_status(other, DAY) == DRAFT_BANNER
    done = [AdoptionEvent(date(2026, 2, 1), AdoptionAction.ADOPTED, (RULES_KEY,), "minutes of 2026-02-01")]
    _, adopted = render(rules_definition(book), ctx_for(book, parts, events=done))
    assert "DRAFT" not in adopted and "Adopted by the board of directors on 2026-02-01 (minutes of 2026-02-01)" in adopted
    assert "{ADOPTION_STATUS}" not in md and "{ADOPTION_STATUS}" not in adopted


def test_the_status_token_is_open_when_no_value_is_given():
    book, parts = book_of()
    o, s, result, source = parts
    ctx = manual_context(result, s, source, o.text, values={"ASSOCIATION_NAME": "X", "RULES_TITLE": "R"}, as_of=DAY)
    ctx.rules = RulesContext(book)
    assembly = assemble(rules_definition(book), ctx)
    assert "{ADOPTION_STATUS}" in check(assembly, MarkdownRenderer().render(assembly, PLAIN)).open_tokens


# --- Layout apart from blocks --------------------------------------------------------------------------------------------


def test_two_layouts_one_set_of_blocks():
    book, parts = book_of()
    assembly = assemble(rules_definition(book), ctx_for(book, parts))
    before = [(r.id, r.markdown) for r in assembly.results]
    plain = MarkdownRenderer().render(assembly, PLAIN)
    book_md = MarkdownRenderer().render(assembly, BOOK)
    guide = MarkdownRenderer().render(assembly, GUIDE)
    assert [(r.id, r.markdown) for r in assembly.results] == before
    assert "## Contents" in book_md and "## Contents" not in plain and book_md != guide
    # the status line and the title come before the contents, and the rule headings are not numbered again
    assert book_md.index(DRAFT_BANNER) < book_md.index("## Contents") < book_md.index("### R-1. PETS")
    assert "### R-1. PETS" in book_md and "### 1." not in book_md and "## 1." in guide
    for line in plain.split("\n"):
        if line.strip() and not line.startswith("#"):
            assert line in book_md
    html = HtmlRenderer().render(assembly, BOOK)
    assert "--accent:#1f3a5f" in html and "<h3 id=\"r-1-pets\">" in html


def test_the_layout_never_changes_a_rule_block():
    book, parts = book_of()
    one = assemble(rules_definition(book, PLAIN), ctx_for(book, parts))
    two = assemble(rules_definition(book, BOOK), ctx_for(book, parts))
    assert [(r.id, r.markdown) for r in one.results] == [(r.id, r.markdown) for r in two.results]


# --- The manual that reads its rules from the Rules document -------------------------------------------------------------


def test_the_manual_read_from_the_rules_document_is_the_manual_with_labeled_differences_only():
    from jason.community.document_templates import definition_from_template
    from jason.community.manual import check as manual_check
    from test_manual import MANUAL

    book, (o, s, result, source) = book_of()
    d = definition_from_template(MANUAL, "m", "M")
    base = assemble(d, manual_context(result, s, source, o.text, as_of=DAY))
    wrapped = RulesDocumentSource(source, book, DAY)
    same = assemble(d, manual_context(result, s, wrapped, o.text, as_of=DAY))
    assert MarkdownRenderer().render(same, PLAIN) == MarkdownRenderer().render(base, PLAIN)         # option on, nothing differs
    assert rules_section_check(same.chunks, book, DAY).identical and wrapped.used
    # a record whose words changed: the manual shows the new words, and the difference is labeled
    target = next(r for r in book.records if r.number == "R-1(a)")
    edited = replace_record(book, target.id, "**a.** No pet shall be left alone on a patio.")
    changed = assemble(d, manual_context(result, s, RulesDocumentSource(source, edited, DAY), o.text, as_of=DAY))
    md = MarkdownRenderer().render(changed, PLAIN)
    assert "left alone on a patio" in md and "left alone on a deck" not in md
    found = manual_check(changed.chunks, o.text)
    assert not found.unlabeled and any("read from the Rules document" in d.label for d in found.labeled)
    # with the option off, the words are the classification's, whatever the records say
    off = assemble(d, manual_context(result, s, source, o.text, as_of=DAY))
    assert "left alone on a deck" in MarkdownRenderer().render(off, PLAIN)


def test_a_record_the_manual_does_not_place_is_reported():
    from jason.community.document_templates import definition_from_template
    from test_manual import MANUAL

    book, (o, s, result, source) = book_of()
    extra = RuleRecord("new-rule", "R-9", "R-9. NEW", 3, segment="R-9", versions=(RuleVersion("### R-9. NEW", "R-9 NEW"),))
    more = RuleBook(book.records + [extra], book.appendix, book.loose)
    # the owner's manual places only the rules its own outline has: a new record is the Rules document's alone
    d = assemble(definition_from_template(MANUAL, "m", "M"),
                 manual_context(result, s, RulesDocumentSource(source, more, DAY), o.text, as_of=DAY))
    found = rules_section_check(d.chunks, more, DAY)
    assert found.unplaced == ["new-rule"] and not found.different
    # the manual template places every record, by reference
    full = assemble(manual_template_definition(), ctx_for(more, (o, s, result, source), mode="full"))
    assert rules_section_check(full.chunks, more, DAY).unplaced == [] and any("R-9. NEW" in r.markdown for r in full.results)


# --- Records kept as data ---------------------------------------------------------------------------------------------------


def test_records_round_trip_and_an_existing_file_is_never_overwritten(tmp_path):
    from jason.community.manual import ManualError
    from jason.tasks.rules_documents import load_book, records_path, save_book

    book, _ = book_of()
    path = records_path(tmp_path, "example-manual")
    save_book(book, path)
    again = load_book(path)
    assert [r.to_dict() for r in again.records] == [r.to_dict() for r in book.records] and again.appendix == book.appendix
    path.write_text(json.dumps({**json.loads(path.read_text(encoding="utf-8")), "edited": True}), encoding="utf-8")
    with pytest.raises(ManualError, match="not overwritten"):
        save_book(book, path)
    assert json.loads(path.read_text(encoding="utf-8"))["edited"] is True


def test_the_proof_of_the_rules_document_against_the_official_rules():
    from jason.community.manual import render as manual_render
    from jason.tasks.rules_documents import prove_rules

    book, (o, s, result, source) = book_of()
    official, _ = manual_render("# {ASSOCIATION_NAME}\n\n## {RULES_TITLE}\n\n### Adoption history\n\n{ADOPTION_HISTORY}\n\n"
                                "{INCLUDE:rules official}\n", result, s, source, o.text,
                                values={"ASSOCIATION_NAME": "Example Commons", "RULES_TITLE": "Example Rules"})
    _, doc = render(rules_definition(book), ctx_for(book, (o, s, result, source)))
    proof = prove_rules(official, doc, values())
    assert proof.equal and proof.same > 5, proof.unlabeled
    why = {w for _, w in proof.labeled}
    assert "the appendix of policies published apart" in why and "the status line {ADOPTION_STATUS}" in why
    # a word changed in the document and not in the official rules is not a labeled difference
    bad = doc.replace("Pets shall be leashed", "Pets shall be caged")
    assert not prove_rules(official, bad, values()).equal


# --- C. The Doc ----------------------------------------------------------------------------------------------------------------


def plan_of(definition, ctx, layout=BOOK):
    assembly = assemble(definition, ctx)
    return assembly, doc_output.build(assembly, layout)


def test_the_doc_has_the_real_named_styles_and_a_link_to_the_rules_doc():
    book, parts = book_of(events=[AdoptionEvent(date(2022, 8, 30), AdoptionAction.ADOPTED, ("R-1",), "minutes")])
    url = "https://docs.google.com/document/d/RULES123/edit"
    ctx = ctx_for(book, parts, mode="index", vals={"RULES_DOC_URL": url})
    for drop in ("ASSOCIATION_NAME",):
        ctx.values.pop(drop)                                               # the template form keeps its token
    assembly, plan = plan_of(manual_template_definition(), ctx)
    named = [r["updateParagraphStyle"]["paragraphStyle"].get("namedStyleType") for r in plan.requests
             if "updateParagraphStyle" in r]
    assert "TITLE" in named and "SUBTITLE" in named and "HEADING_1" in named and "HEADING_2" in named
    assert ("TITLE", "Example Manual") in plan.headings and ("SUBTITLE", "{ASSOCIATION_NAME}") in plan.headings
    assert ("HEADING_1", "Example Rules") in plan.headings
    assert plan.tokens == ["{ASSOCIATION_NAME}"]                           # left in place for the copy
    links = {text: u for text, u in plan.links}
    assert links["Example Rules"] == url                                    # the line that links the Rules Doc
    assert any("updateTextStyle" in r and r["updateTextStyle"]["textStyle"].get("link", {}).get("url") == url
               for r in plan.requests)
    assert plan.page_breaks >= 1 and any(r["updateParagraphStyle"]["paragraphStyle"].get("pageBreakBefore") is True
                                         for r in plan.requests if "updateParagraphStyle" in r)
    # the Doc has a marker where the contents go (the Docs API cannot insert the table-of-contents field)
    assert doc_output.CONTENTS_MARKER in plan.paragraphs and plan.contents_depth == 2


def test_the_rules_doc_has_titles_headings_a_table_and_a_named_range_per_rule():
    book, parts = book_of(events=[AdoptionEvent(date(2022, 8, 30), AdoptionAction.ADOPTED, ("R-1",), "minutes")])
    assembly, plan = plan_of(rules_definition(book), ctx_for(book, parts))
    styles = plan.styles()
    assert styles["TITLE"] == 1 and styles["SUBTITLE"] == 1 and styles["HEADING_1"] >= 2 and styles["HEADING_2"] >= 2
    assert ("HEADING_2", "R-1. PETS") in plan.headings and ("HEADING_1", "The rules") in plan.headings
    assert len(plan.tables) == 1 and plan.tables[0][0] == ["Date", "Action", "Parts", "Evidence"]
    kinds = [next(iter(r)) for r in plan.requests]
    assert kinds.count("insertTable") == 1 and "pinTableHeaderRows" in kinds
    assert set(plan.named_ranges) >= {f"rule:{r.id}" for r in book.records}        # a rule is found by its id in the Doc
    boxed = [r for r in plan.requests if "updateParagraphStyle" in r and "borderLeft" in r["updateParagraphStyle"]["paragraphStyle"]]
    assert boxed                                                                   # the draft banner is a ruled box
    assert plan.tokens == []
    assert plan.header == "Rules and Regulations" and plan.footer == f"As of {DAY.isoformat()}"


def test_the_requests_apply_to_a_doc_and_put_each_style_on_its_own_paragraph():
    """A small simulator of the text requests (insert, delete, paragraph style) shows the indices are right."""
    book, parts = book_of()
    d = rules_definition(book)
    d = d.__class__(d.key, d.title, tuple(b for b in d.items if b.kind not in ("history",) and b.id != "adoption-history"),
                    d.layout, d.kind, d.authority)
    assembly, plan = plan_of(d, ctx_for(book, parts))
    sim = Sim()
    sim.apply(plan.requests)
    by_text = {t: s for t, s in sim.paragraphs()}
    assert by_text["Example Rules"] == "TITLE" and by_text["Example Commons"] == "SUBTITLE"
    assert by_text["R-1. PETS"] == "HEADING_2" and by_text["The rules"] == "HEADING_1"
    assert by_text["Pets shall be leashed in the common area."] == "NORMAL_TEXT"
    assert doc_output.verify(sim.doc(), plan) == []
    # the named range of a rule covers that rule's own paragraphs
    name = next(n for n in plan.named_ranges if n.startswith("rule:") and n.endswith("R-1"))
    start, end = sim.ranges[name]
    assert "Pets shall be leashed" in sim.text()[start - 1:end - 1] and "No Unit shall be altered" not in sim.text()[start - 1:end - 1]


class Sim:
    """Enough of the Docs body to follow insertText, deleteContentRange, updateParagraphStyle, and createNamedRange."""

    def __init__(self):
        self.body = "\n"
        self.style: dict[int, str] = {}
        self.ranges: dict[str, tuple[int, int]] = {}

    def text(self):
        return self.body

    def apply(self, requests):
        for r in requests:
            if "deleteContentRange" in r:
                rg = r["deleteContentRange"]["range"]
                self.body = self.body[:rg["startIndex"] - 1] + self.body[rg["endIndex"] - 1:]
            elif "insertText" in r:
                at = r["insertText"]["location"]["index"]
                self.body = self.body[:at - 1] + r["insertText"]["text"] + self.body[at - 1:]
            elif "updateParagraphStyle" in r:
                rg = r["updateParagraphStyle"]["range"]
                name = r["updateParagraphStyle"]["paragraphStyle"].get("namedStyleType")
                if name:
                    for start in self._starts():
                        if rg["startIndex"] <= start < rg["endIndex"]:
                            self.style[start] = name
            elif "createNamedRange" in r:
                rg = r["createNamedRange"]["range"]
                self.ranges[r["createNamedRange"]["name"]] = (rg["startIndex"], rg["endIndex"])

    def _starts(self):
        out, pos = [], 1
        for line in self.body.split("\n"):
            out.append(pos)
            pos += len(line) + 1
        return out

    def paragraphs(self):
        out, pos = [], 1
        for line in self.body.split("\n"):
            out.append((line, self.style.get(pos, "NORMAL_TEXT")))
            pos += len(line) + 1
        return out

    def doc(self):
        content, pos = [], 1
        for line, style in self.paragraphs():
            content.append({"startIndex": pos, "endIndex": pos + len(line) + 1,
                            "paragraph": {"paragraphStyle": {"namedStyleType": style},
                                          "elements": [{"textRun": {"content": line + "\n"}}]}})
            pos += len(line) + 1
        return {"body": {"content": content}}


def test_the_contents_are_links_to_the_headings_once_they_have_ids():
    doc = {"body": {"content": [
        {"startIndex": 1, "endIndex": 6, "paragraph": {"paragraphStyle": {"namedStyleType": "TITLE"},
                                                      "elements": [{"textRun": {"content": "Name\n"}}]}},
        {"startIndex": 6, "endIndex": 20, "paragraph": {"paragraphStyle": {"namedStyleType": "NORMAL_TEXT"},
                                                       "elements": [{"textRun": {"content": "[[contents]]\n"}}]}},
        {"startIndex": 20, "endIndex": 30, "paragraph": {"paragraphStyle": {"namedStyleType": "HEADING_1", "headingId": "h.one"},
                                                        "elements": [{"textRun": {"content": "Part one\n"}}]}},
        {"startIndex": 30, "endIndex": 40, "paragraph": {"paragraphStyle": {"namedStyleType": "HEADING_2", "headingId": "h.two"},
                                                        "elements": [{"textRun": {"content": "Rule 1\n"}}]}},
        {"startIndex": 40, "endIndex": 50, "paragraph": {"paragraphStyle": {"namedStyleType": "HEADING_3", "headingId": "h.deep"},
                                                        "elements": [{"textRun": {"content": "Deeper\n"}}]}}]}}
    reqs = doc_output.contents_requests(doc, 2)
    assert reqs[0] == {"deleteContentRange": {"range": {"startIndex": 6, "endIndex": 6 + len("[[contents]]")}}}
    assert reqs[1]["insertText"]["text"] == "Part one\n\tRule 1"
    links = [r["updateTextStyle"]["textStyle"]["link"]["headingId"] for r in reqs if "updateTextStyle" in r]
    assert links == ["h.one", "h.two"]
    assert doc_output.contents_requests({"body": {"content": []}}, 2) == []


def test_a_table_is_a_marker_then_a_real_table_filled_last_cell_first():
    book, parts = book_of(events=[AdoptionEvent(date(2022, 8, 30), AdoptionAction.ADOPTED, ("R-1",), "minutes")])
    _, plan = plan_of(rules_definition(book), ctx_for(book, parts))
    kinds = [next(iter(r)) for r in plan.requests]
    at = kinds.index("insertTable")
    assert "deleteContentRange" in kinds[at - 1]                          # the marker's text is taken out first
    inserts = [r["insertText"]["location"]["index"] for r in plan.requests[at + 1:] if "insertText" in r
               and r["insertText"]["location"]["index"] > plan.requests[at]["insertTable"]["location"]["index"]]
    assert inserts == sorted(inserts, reverse=True)                       # last cell first: no cell moves under the next
    table = plan.requests[at]["insertTable"]
    assert table["rows"] == 2 and table["columns"] == 4


# --- D. Plan and create ----------------------------------------------------------------------------------------------------------


class Profile:
    """The few facts a Docs job reads from the profile."""

    def __init__(self, documents=()):
        self._documents = documents

    def drive_home(self):
        from jason.community.identity import DriveHome

        return DriveHome(my_drive="my-drive", templates="templates-folder")

    def letterhead(self):
        from jason.community.identity import LetterheadSpec

        return LetterheadSpec("EXAMPLE", footer="1 Main St", doc_id="letterhead-doc")

    def manual_documents(self):
        return self._documents


def prepared_for(tmp_path, documents=()):
    from jason.tasks.rules_documents import Prepared

    book, (o, s, result, source) = book_of()
    made = {"passages": [], "paths": {"manual": tmp_path / "owners-manual.md"}}
    return Prepared(tmp_path, Profile(documents), made, result, o, s, source, values(), [], book, DAY, tmp_path,
                    list(documents))


class FakeDocs:
    """Records what is written; ``get`` answers an empty Doc (the Letterhead's copy)."""

    def __init__(self):
        self.writes: list[tuple[str, int]] = []

    def get(self, doc_id):
        body = [{"startIndex": 1, "endIndex": 3, "paragraph": {"paragraphStyle": {"namedStyleType": "NORMAL_TEXT"},
                                                              "elements": [{"textRun": {"content": "\n"}}]}}]
        return {"body": {"content": body}, "documentStyle": {}}

    def batch_update(self, doc_id, requests):
        self.writes.append((doc_id, len(requests)))
        return {"replies": []}


class FakeDrive:
    def __init__(self):
        self.copies: list[tuple[str, str, str]] = []

    def copy(self, file_id, name, parent_id=None):
        self.copies.append((file_id, name, parent_id))
        return f"doc-{len(self.copies)}"


def test_the_plan_is_a_dry_run_that_writes_nothing(tmp_path):
    from jason.tasks import document_docs as dd

    rows = (ManualDocument(RULES_KEY, "Rules (draft)", "rules-folder"), ManualDocument(MANUAL_TEMPLATE_KEY, "Template - Manual"))
    prepared = prepared_for(tmp_path, rows)
    state: dict = {}
    jobs = dd.jobs_for(prepared, (RULES_KEY, MANUAL_TEMPLATE_KEY), state)
    steps = dd.plan_docs(prepared, jobs, state, {})
    assert [(s.key, s.action.value, s.folder) for s in steps] == [(RULES_KEY, "create", "rules-folder"),
                                                                   (MANUAL_TEMPLATE_KEY, "create", "templates-folder")]
    text = "\n".join(line for s in steps for line in dd.describe(s, state))
    assert "Rules (draft)" in text and "Template - Manual" in text and "requests:" in text
    assert "tokens left open: {ASSOCIATION_NAME}" in text or "tokens left open: none" in text
    assert "link: 'Example Rules' -> https://docs.google.com/document/d/<the Rules Doc's id" in text
    assert state == {} and list(tmp_path.iterdir()) == []                           # nothing was recorded or written


def test_the_manual_template_links_the_rules_doc_by_its_id_once_it_is_known(tmp_path):
    from jason.tasks import document_docs as dd

    prepared = prepared_for(tmp_path)
    state = {"document:" + RULES_KEY: {"docId": "RULESID", "baseSha": "x", "docSha": "y"}}
    job = dd.make_job(prepared, MANUAL_TEMPLATE_KEY, state)
    assert ("Example Rules", "https://docs.google.com/document/d/RULESID/edit") in job.plan.links
    unnamed = dd.make_job(prepared, MANUAL_TEMPLATE_KEY, {})
    assert "RULES_DOC_ID" in unnamed.rules_url and unnamed.base != job.base


def test_create_writes_the_rules_doc_first_and_records_both(tmp_path):
    from jason.tasks import document_docs as dd

    prepared = prepared_for(tmp_path, (ManualDocument(RULES_KEY, "Rules (draft)", "rf"),
                                       ManualDocument(MANUAL_TEMPLATE_KEY, "Template - Manual", "mf")))
    state: dict = {}
    steps = dd.plan_docs(prepared, dd.jobs_for(prepared, (MANUAL_TEMPLATE_KEY, RULES_KEY), state), state, {})
    drive, docs = FakeDrive(), FakeDocs()
    done = dd.generate(drive, docs, prepared, steps, state, letterhead_id="letterhead-doc", footer="1 Main St")
    assert [d["key"] for d in done] == [RULES_KEY, MANUAL_TEMPLATE_KEY]                  # the rules first
    assert drive.copies == [("letterhead-doc", "Rules (draft)", "rf"), ("letterhead-doc", "Template - Manual", "mf")]
    assert state["document:" + RULES_KEY]["docId"] == "doc-1" and state["document:" + MANUAL_TEMPLATE_KEY]["docId"] == "doc-2"
    assert "doc-1" in state["document:" + MANUAL_TEMPLATE_KEY]["rulesUrl"]                 # the link between the two
    assert all(w[1] > 0 for w in docs.writes)


def test_the_states_of_a_doc_are_the_template_generators(tmp_path):
    from jason.tasks import document_docs as dd
    from jason.tasks.template_gen import Action, sha

    prepared = prepared_for(tmp_path)
    state: dict = {}
    job = dd.make_job(prepared, RULES_KEY, state)
    entry = {"docId": "d", "baseSha": job.base, "docSha": sha("as written")}
    state = {"document:" + RULES_KEY: entry}

    def action(texts, st=state, job=job):
        return dd.plan_docs(prepared, [job], st, texts)[0].action

    assert action({"d": "as written"}) is Action.UNCHANGED
    assert action({"d": "a person edited it"}) is Action.EDITED                       # left alone
    assert action({"d": None}) is Action.CREATE                                       # trashed
    changed = {"document:" + RULES_KEY: {**entry, "baseSha": "old"}}
    assert action({"d": "as written"}, changed) is Action.UPDATE
    assert action({"d": "a person edited it"}, changed) is Action.CONFLICT
    assert action({}, changed) is Action.UPDATE and "not read" in dd.plan_docs(prepared, [job], changed, {})[0].reason
    assert not Action.EDITED.writes and not Action.CONFLICT.writes and Action.UPDATE.writes
    # a Doc the profile names that jason did not generate is not overwritten
    named = prepared_for(tmp_path, (ManualDocument(RULES_KEY, "Rules", drive_id="theirs"),))
    step = dd.plan_docs(named, [dd.make_job(named, RULES_KEY, {})], {}, {})[0]
    assert step.action is Action.EDITED and step.doc_id == "theirs"


def test_an_edited_doc_is_left_alone_by_generate(tmp_path):
    from jason.tasks import document_docs as dd

    prepared = prepared_for(tmp_path)
    from jason.tasks.template_gen import Action

    steps = [dd.Step(RULES_KEY, "Rules", Action.EDITED, "d"), dd.Step(MANUAL_TEMPLATE_KEY, "Manual", Action.CONFLICT, "e")]
    docs, drive = FakeDocs(), FakeDrive()
    assert dd.generate(drive, docs, prepared, steps, {}, letterhead_id="l", footer="f") == [] and not docs.writes and not drive.copies


def test_the_profile_supplies_the_docs_and_the_base_has_none():
    from jason.community import community
    from jason.community.base import Community

    assert Community.manual_documents(community()) == ()
    rows = {r.key: r for r in community().manual_documents()}
    assert set(rows) == {RULES_KEY, MANUAL_TEMPLATE_KEY} and all(r.name for r in rows.values())


def test_the_directory_block_in_the_template_prints_only_what_is_published():
    book, parts = book_of()
    ctx = ctx_for(book, parts, mode="index")
    ctx.directory = (DirectoryEntry("president", "Quill Example", False), DirectoryEntry("secretary", "Ilse Example", True))
    _, md = render(manual_template_definition(), ctx)
    assert "Ilse Example" in md and "Quill Example" not in md and "(not published)" in md
    assert ComputedBlock and Context


def test_the_command_lists_the_documents_and_a_dry_run_never_asks_for_google(capsys):
    from argparse import Namespace

    from jason.commands.document_template import cmd_document_template

    args = Namespace(list=True, document=None, doc=None, export_records=False)
    assert cmd_document_template(args) == 0
    out = capsys.readouterr().out
    assert "rules-and-regulations" in out and "owners-manual-template" in out and "book" in out
    assert "rules-reference" in out and "policy-references" in out
