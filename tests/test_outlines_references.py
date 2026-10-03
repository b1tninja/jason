from jason.community.outlines import DocumentOutline, Section, normalize_number, outline_from_doc, outline_from_text
from jason.community.references import RefRelation, TargetKind, ancestors, extract
from jason.tasks import outlines as task


def _para(text, style="NORMAL_TEXT", list_id="", level=0):
    p = {"paragraphStyle": {"namedStyleType": style}, "elements": [{"textRun": {"content": text + "\n"}}]}
    if list_id:
        p["bullet"] = {"listId": list_id, "nestingLevel": level}
    return {"paragraph": p}


LISTS = {"L": {"listProperties": {"nestingLevels": [
    {"glyphType": "DECIMAL", "glyphFormat": "%0."},
    {"glyphType": "DECIMAL", "glyphFormat": "%0.%1."},
    {"glyphType": "ALPHA", "glyphFormat": "%2."},
    {"glyphType": "ROMAN", "glyphFormat": "%3."},
]}}, "B": {"listProperties": {"nestingLevels": [{"glyphSymbol": "●", "glyphFormat": "%0"}]}}}


def _doc(paragraphs):
    return {"title": "Bylaws", "documentId": "D", "revisionId": "R",
            "tabs": [{"documentTab": {"lists": LISTS, "body": {"content": paragraphs}}}]}


def test_a_docs_outline_renders_its_list_numbers_as_documents_cite_them():
    doc = _doc([
        _para("ARTICLE 1", "HEADING_1"), _para("DEFINITIONS", "HEADING_2", "L", 0),
        _para("Absolute Majority.", "HEADING_3", "L", 1),
        _para("ARTICLE 2", "HEADING_1"), _para("COMMON AREA", "HEADING_2", "L", 0),
        _para("Ownership of Common Area.", "HEADING_3", "L", 1),
        _para("Owners Non-Exclusive Easements.", "HEADING_3", "L", 1),
        _para("Rules.", "HEADING_4", "L", 2), _para("limiting guests;", "NORMAL_TEXT", "L", 3),
        _para("a bullet, not a section", "NORMAL_TEXT", "B", 0),
    ])
    outline = outline_from_doc(doc, key="ccrs")
    assert [(s.number, s.title) for s in outline.sections] == [
        ("1", "DEFINITIONS"), ("1.1", "Absolute Majority."), ("2", "COMMON AREA"), ("2.1", "Ownership of Common Area."),
        ("2.2", "Owners Non-Exclusive Easements."), ("2.2(a)", "Rules."), ("2.2(a)(i)", "limiting guests;")]
    rules = outline.section("2.2(a)")
    assert outline.section_at(outline.text.index("limiting")).number == "2.2(a)(i)" and rules.parent == "2.2"
    assert outline.section("2") .end == len(outline.text) and outline.section("1").end == outline.section("2").start


def test_a_text_outline_closes_ocr_gaps_and_tells_a_letter_i_from_roman_i():
    text = ("1.3 Assessments.\n(d) Cost Center Allocation.\n(i) Segregation of Expenses.\n(iii) Annexed Property.\n"
            "(e) Other.\n(h) Eighth.\n(i) Ninth, the letter.\nSection 13 .1 of the Declaration and 1.3( d)(i).\n")
    outline = outline_from_text(text, key="annexation")
    numbers = [s.number for s in outline.sections]
    assert numbers == ["1.3", "1.3(d)", "1.3(d)(i)", "1.3(d)(iii)", "1.3(e)", "1.3(h)", "1.3(i)"]
    assert "13.1" in outline.text and "1.3(d)(i)" in outline.text
    assert normalize_number("8.5.c") == "8.5(c)" and list(ancestors("3.3(a)(i)")) == ["3.3(a)", "3.3", "3"]


def _outline(key, text, sections=(), amends=""):
    o = DocumentOutline(key=key, title=key, text=text, amends=amends)
    o.sections = list(sections) or [Section("1", "All", 1, 0, len(text))]
    return o


ALIASES = {"bylaws": "bylaws", "declaration": "ccrs", "declaration of covenants, conditions and restrictions": "ccrs",
           "enforcement policy": "enforcement-policy"}


def test_the_grammar_reads_statutes_sections_and_documents():
    text = ("Pursuant to Civil Code Sections 5855(d), 5910 and CIV 5850(c), (d); see Sections 1366, 1367.1, and 1367.4 of the "
            "Civil Code. The quorum for assessment increases described in Section 6.5(d) and Section 6.6(c) of the Declaration. "
            "Bylaws Section 8.5(f) applies, subject to the Enforcement Policy. Former Civil Code Section 1363. "
            "California Corporation Code, Section 7110. Posted under section 602(k) Penal Code. As defined in subdivision (p) "
            "of Section 12955 of the Government Code. The Declaration of Covenants, Conditions and Restrictions under Section 2.5. "
            "(See Declaration §§ 10.6, 11.2).")
    refs = extract(_outline("bylaws", text), ALIASES)
    got = {(r.kind, r.target) for r in refs}
    for statute in ("CIV 5855(d)", "CIV 5910", "CIV 5850(c)", "CIV 5850(d)", "CIV 1366", "CIV 1367.1", "CIV 1367.4", "CIV 1363",
                    "CORP 7110", "PEN 602(k)", "GOV 12955"):
        assert (TargetKind.STATUTE, statute) in got, statute
    for section in ("ccrs#6.5(d)", "ccrs#6.6(c)", "bylaws#8.5(f)", "ccrs#2.5", "ccrs#10.6", "ccrs#11.2"):
        assert (TargetKind.SECTION, section) in got, section
    assert (TargetKind.DOCUMENT, "enforcement-policy") in got
    assert not any(t.startswith("bylaws#1") or t.startswith("bylaws#7110") for _, t in got)
    assert next(r for r in refs if r.target == "CIV 1363").prior
    assert next(r for r in refs if r.target == "enforcement-policy").relation is RefRelation.SUBJECT_TO


def test_an_amendment_and_an_annexation_cite_the_declaration_unless_the_section_is_their_own():
    amendment = _outline("ccrs-2nd", "Article 4, Section 4.15 (Rental), subsection (a), is hereby amended and restated.", amends="ccrs")
    refs = extract(amendment, ALIASES)
    # "subsection (a)" after "Section 4.15 (Rental)" in the same sentence is 4.15(a): the short form hangs from it.
    assert {r.target for r in refs} == {"ccrs#4", "ccrs#4.15", "ccrs#4.15(a)"}
    assert all(r.relation is RefRelation.AMENDS for r in refs)
    text = "1.3 Assessments.\n(d) Allocation. See subsection 1.3(d)(ii), below, and Section 6.5(b) of the Declaration and Section 13.1.\n"
    annexation = outline_from_text(text, key="phase-7")
    annexation.amends = "ccrs"
    targets = {r.target for r in extract(annexation, ALIASES)}
    assert targets == {"phase-7#1.3(d)(ii)", "ccrs#6.5(b)", "ccrs#13.1"}


def test_a_short_form_names_a_part_or_a_sibling_of_the_section_around_it():
    text = ("6.2 Letting.\n(a) Limit. Except as subsection (b) provides, no more than a tenth of the Lots are let.\n"
            "(b) Notice. Notice is given as paragraph (a) of Section 4920 of the Civil Code requires, and as "
            "subsection (z) says.\n")
    decl = outline_from_text(text, key="decl")
    targets = {r.target for r in extract(decl, ALIASES)}
    assert "decl#6.2(b)" in targets                              # the sibling of the subsection it sits in
    assert not any(t.endswith("(z)") or t == "decl#6.2(a)" for t in targets)   # nothing named; another provision


def test_an_unqualified_section_takes_its_document_from_the_section_title():
    text = "WHAT ARE THE CC&Rs?\n- § 4.15 (o) Department of Veterans Affairs\nPer California Fire Codes § 308.1.4 grills may not be used.\n"
    manual = _outline("owners-manual", text, [Section("", "WHAT ARE THE CC&Rs?", 2, 0, len(text)), Section("4", "Rules", 1, 0, 0)])
    targets = {r.target for r in extract(manual, {**ALIASES, "cc&rs": "ccrs"})}
    assert targets == {"ccrs", "ccrs#4.15(o)", "CFC 308.1.4"}      # the title also names the CC&Rs as a whole


def test_the_models_references_join_the_map_unless_the_grammar_has_them(tmp_path):
    import json

    from jason.tasks.reference_review import store_path

    grammar = extract(_outline("owners-manual", "See Bylaws Section 8.5(f)."), ALIASES)
    path = store_path(tmp_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    base = {"source": "owners-manual", "source_section": "1", "kind": "section", "relation": "cites", "quote": "q", "offset": 0,
            "prior": False, "method": "model", "said": "s", "passage": "p"}
    path.write_text(json.dumps({"references": [
        {**base, "target": "bylaws#8.5(f)"},                      # the grammar has it
        {**base, "target": "ccrs#2.5"},                           # new
        {**base, "kind": "document", "target": "named:city's conditions of approval"},
        {**base, "target": "owners-manual#8.5(f)"},               # the same number the grammar read here, filed elsewhere
    ]}), encoding="utf-8")
    added = task.model_references(tmp_path, grammar)
    assert [(r.target, r.method) for r in added] == [("ccrs#2.5", "model")]


def test_resolve_and_findings(tmp_path):
    bylaws = _outline("bylaws", "Section 7.2 of the Bylaws and Section 3.8 of the Declaration; Resolution 20230130-1.",
                      [Section("7", "Meetings", 1, 0, 90), Section("7.2", "Regular", 2, 0, 90, parent="7")])
    bylaws.aliases = ["Bylaws"]
    ccrs = _outline("ccrs", "Common area.", [Section("3", "Common Area", 1, 0, 12), Section("3.7", "Bonds", 2, 0, 12, parent="3")])
    ccrs.aliases = ["Declaration"]
    a = _outline("res-a", "A.")
    a.numbers = ["20230130-1"]
    b = _outline("res-b", "B.")
    b.numbers = ["20230130-1"]
    outlines = [bylaws, ccrs, a, b]
    rows = task.resolve(task.references(outlines), outlines, tmp_path)
    status = {r["target"]: r["status"] for r in rows}
    assert status["bylaws#7.2"] == "found" and status["ccrs#3.8"] == "parent only"
    assert status["resolution:20230130-1"] == "printed by several"
    found = "\n".join(task.findings(rows, outlines))
    assert "ccrs#3.8; the outline has 3" in found and "20230130-1 is printed by 2 Docs" in found
    assert [r["source"] for r in task.cited_by(rows, "bylaws#7")] == ["bylaws"]
