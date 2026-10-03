from jason.community.living import provisions_of
from jason.community.outline_align import align_to_reference, opening_key, similarity
from jason.community.outline_labels import How, NoteKind, outline_from_ocr, token_cost
from jason.community.outlines import DocumentOutline, Section, outline_from_text

# A made-up declaration, as a poor scan's OCR reads it.
OCR = """TABLE OF CONTENTS
1.1 Definitions... 0.0.0... cece 2 1.2 Absolute Majority... 0.0... eee 2
RESTATED DECLARATION
ARTICLE 1 DEFINITIONS
1.1 Absolute Majority. "Absolute Majority" means a majority of the votes.
12 Articles. "Articles" means the articles of incorporation.
1.3 Assessment. "Assessment" means a charge levied by the Association, including:
(a) Regular Assessments, as set forth in Section 6.5;
(b} Special Assessments, as set forth in Section 6.6;
{c) Reimbursement Assessments, as set forth in Section 6.7.
ARTICLE2 SS COMMON AREA
2.1 Ownership. Declarant shall convey the Common Area to the Association.
2.2 Rules. The Board may adopt Rules (i) limiting the number of guests, (ii) limiting the hours of use,
(iii) regulating the use of the pool, and (iv) regulating parking upon the Common Area.
ARTICLES USE RESTRICTIONS
31 Residential Use. Each Unit shall be used as a residence only.
3.2 Leasing. An Owner may lease his or her Unit as set forth below.
(a) Restriction. Not more than ten Units shall be leased at any time.
( Rehearing. If an application is disapproved, the Owner may ask for a rehearing.
() Indemnity. Every Owner of a leased Unit shall indemnify the Association.
Gd) Notices. The Board shall give notice of each decision in writing.
“ (e) Exemptions. The following are exempt from the restriction:
(i) Roof replacement;
(i) Exterior maintenance;
(ili) Insurance for the building.
3.2 Pets. No animals other than household pets may be kept in a Unit.
3.4 Signs. The Board may adopt reasonable limits on signs.
"""


def _numbers(reading):
    return [m.number for m in reading.marks]


def test_token_cost_reads_ocr_confusions_as_near():
    assert token_cost("ii", "ii") == 0
    assert token_cost("it", "ii") < 0.3 and token_cost("11", "ii") < 0.5 and token_cost("ili", "iii") < 0.3
    assert token_cost("0", "o") < 0.3 and token_cost("S", "5") < 0.3
    assert token_cost("i", "ii") < token_cost("i", "h")
    assert token_cost("", "f") < 1 and token_cost("D", "f") == 1


def test_the_grammar_reads_garbled_labels_in_order():
    reading = outline_from_ocr(OCR, key="decl")
    assert _numbers(reading) == [
        "1", "1.1", "1.2", "1.3", "1.3(a)", "1.3(b)", "1.3(c)",
        "2", "2.1", "2.2", "2.2(i)", "2.2(ii)", "2.2(iii)", "2.2(iv)",
        "3", "3.1", "3.2", "3.2(a)", "3.2(b)", "3.2(c)", "3.2(d)", "3.2(e)", "3.2(e)(i)", "3.2(e)(ii)",
        "3.2(e)(iii)", "3.3", "3.4"]
    by = {m.number: m for m in reading.marks}
    assert by["1.2"].how is How.RECOVERED and by["1.2"].raw == "12"
    assert by["3"].how is How.RECOVERED and not by["3"].firm          # "ARTICLES" read as Article 3
    assert by["3.3"].how is How.RECOVERED                             # "3.2" between 3.2 and 3.4
    assert by["2.2(i)"].how is How.INLINE and by["2.2(iv)"].how is How.INLINE
    assert by["3.2(e)(ii)"].raw == "(i)" and by["1.1"].firm
    kinds = {n.kind for n in reading.notes}
    assert NoteKind.RECOVERED in kinds and NoteKind.INLINE in kinds


def test_the_outline_writes_the_labels_cleanly():
    outline = outline_from_ocr(OCR, key="decl").outline()
    assert "1.2 Articles." in outline.text and "(b) Special" in outline.text and "(c) Reimbursement" in outline.text
    assert "(d) Notices." in outline.text and "TABLE OF CONTENTS" in outline.text
    assert outline.section("3.2(d)").title.startswith("Notices.")
    assert outline.text_of(outline.section("3.2(b)")).startswith("(b) Rehearing.")
    provisions = {p.number: p for p in provisions_of(outline)}
    assert provisions["3.2(c)"].caption == "Indemnity." and provisions["3.1"].caption == "Residential Use."
    assert provisions["2.2(ii)"].body.startswith("limiting the hours of use")
    assert provisions["2.2(ii)"].caption == ""            # an inline item has no caption
    assert outline.section_at(outline.text.index("pool")).number == "2.2(iii)"


def test_the_grammar_finds_more_than_outline_from_text():
    old = {s.number for s in outline_from_text(OCR, key="decl").sections}
    new = {m.number for m in outline_from_ocr(OCR, key="decl").marks}
    assert {"1.2", "1.3(b)", "1.3(c)", "3", "3.1", "3.2(b)", "3.2(c)", "3.2(d)", "3.3"} <= new - old
    assert "1.1" in old and not any(n.startswith("10.") for n in new)


def test_a_table_of_contents_and_a_clear_label_out_of_order_are_text():
    text = """ARTICLE 4 USE RESTRICTIONS
4.1 Residential Use. Each Unit is a residence.
4.2 Businesses. No business may be run from a Unit, except as allowed under
1.5 above, by the Board.
4.3 Noise. No Resident shall make unreasonable noise.
"""
    reading = outline_from_ocr(text, key="decl")
    assert _numbers(reading) == ["4", "4.1", "4.2", "4.3"]
    assert any(n.kind is NoteKind.OUT_OF_ORDER and n.number == "1.5" for n in reading.notes)


def test_an_excerpt_and_a_gap_keep_their_clear_numbers():
    text = """ARTICLE 4
4.15 Rental of Condominiums.
(a) Restrictions. Not more than twenty percent of the Units shall be leased.
(b) Applications. An Owner shall apply in writing.
(d) Rules. The Board may adopt rules.
4.17 Insurance. Nothing shall be done that raises the premium.
"""
    reading = outline_from_ocr(text, key="decl")
    assert _numbers(reading) == ["4", "4.15", "4.15(a)", "4.15(b)", "4.15(d)", "4.17"]
    gaps = {n.number: n.detail for n in reading.notes if n.kind is NoteKind.GAP}
    assert "4.15(d)" in gaps and "4.16" in gaps["4.17"]
    assert not {m.number: m for m in reading.marks}["4.15(d)"].firm


# The same made-up declaration as another OCR engine reads it: its table of contents in columns (bare article
# headings, rows of numbers), "1.40" for 1.10, a heading run into the next, a number read above its caption, and
# a wrong digit that only a comma-separated next label settles.
CLI_OCR = """TABLE OF CONTENTS
ARTICLE 2
ARTICLE 3
1.9 1.10 1.11
2.1 2.2 2.3
3.1 3.2 3.3 3.4
Total Voting Power... 0... ccc cc cece 5
ARTICLE 4
ARTICLE 5
4.1 4.2
5.1 5.2
EXHIBIT "A"
ARTICLE 1 DEFINITIONS
1.8 Bylaws. "Bylaws" shall mean the bylaws of the Association.
1.9 City. "City" shall mean the city in which the Development lies.
1.40 Common Area. "Common Area" shall mean all of the property except the Units.
1.11 Condominium. "Condominium" shall mean an estate in real property.
ARTICLE 2 COMMON AREA 2.1 Ownership of Common Area. (a) Association Common Area. Declarant shall convey it.
(b) Condominium Common Area. Each Unit owns an undivided interest.
2.2 Assessment Liens.
(a) Collection. The Association may collect a delinquent Assessment:
(i) By a civil action in small claims court.
2.3 (ii) By Recording a lien on the Owner's Unit.
Foreclosure of Liens.
(a) Conditions. The Association may foreclose only as the law allows.
ARTICLE 3 EASEMENTS
3.4 Easements in General. Easements are reserved as shown on the Map.
3,2 Utility Easements. Easements for utilities are reserved.
3,3 Easements Granted by Board. The Board may grant easements.
3.4 Maintenance Easements. The Association has an easement to maintain the Common Area.
"""


def test_the_grammar_reads_another_engines_failure_patterns():
    reading = outline_from_ocr(CLI_OCR, key="decl")
    numbers = _numbers(reading)
    assert numbers == ["1", "1.8", "1.9", "1.10", "1.11", "2", "2.1", "2.1(a)", "2.1(b)", "2.2", "2.2(a)",
                       "2.2(a)(i)", "2.2(a)(ii)", "2.3", "2.3(a)", "3", "3.1", "3.2", "3.3", "3.4"]
    by = {m.number: m for m in reading.marks}
    assert by["1.10"].raw == "1.40" and by["3.1"].raw == "3.4"
    assert by["2.1"].how is How.INLINE and by["2.1(a)"].how is How.INLINE
    notes = {(n.kind, n.number) for n in reading.notes}
    assert (NoteKind.RECOVERED, "2.3") in notes                 # its number read above its caption
    assert any(n.kind is NoteKind.OUT_OF_ORDER and "table of contents" in n.detail for n in reading.notes)
    outline = reading.outline()
    assert outline.text_of(outline.section("2.3")).startswith("2.3 Foreclosure of Liens.")
    assert outline.text_of(outline.section("2.2(a)(ii)")).startswith("(ii) By Recording a lien")
    assert not any(n.startswith(("4", "5")) for n in numbers)      # the table of contents is not the body


def test_a_bare_article_heading_still_starts_an_excerpt():
    reading = outline_from_ocr("ARTICLE 4\n4.15 Rental. An Owner may rent.\n(a) Cap. Ten Units.\n", key="d")
    assert _numbers(reading) == ["4", "4.15", "4.15(a)"]


def test_a_hanging_caption_is_read_with_its_label():
    text = """5.1 Leasing.
(a) Restriction. Not more than ten Units shall be leased.
Rehearing.
(b) If an application is disapproved, the Owner may ask for a rehearing.
"""
    outline = outline_from_ocr(text, key="decl").outline()
    assert [s.number for s in outline.sections] == ["5.1", "5.1(a)", "5.1(b)"]
    assert outline.text_of(outline.section("5.1(b)")).startswith("(b) Rehearing. If an application")
    assert {p.number: p for p in provisions_of(outline)}["5.1(b)"].caption == "Rehearing."


# The reference: a copy kept by hand, its numbers from list formatting (here, written out).
REF_PARTS = [
    ("6.12", "Assessment Liens.\n"),
    ("6.12(a)", "Notice. At least 30 days before Recording a lien, the Association shall notify the Owner of:\n"),
    ("6.12(a)(i)", "a general description of the collection procedures;\n"),
    ("6.12(a)(ii)", "an itemized statement of the charges owed;\n"),
    ("6.12(b)", "Payments Made by Owner. Any payments made by the Owner shall be applied first to the principal.\n"),
    ("6.12(c)", "Meet and Confer. Before Recording a lien, the Association shall offer to meet and confer.\n"),
    ("6.12(d)", "Any proposed action which requires the consent of a specified percentage of Mortgagees.\n"),
    ("6.12(e)", "Lien Recorded in Error. A lien recorded in error shall be released.\n"),
    ("6.12(f)", "Use of Funds. The Board may use the funds of the Association for\n"),
    ("6.12(f)(i)", "managing and operating the Development, and\n"),
    ("6.12(f)(ii)", "conducting the business of the Association.\n"),
    ("6.13", "Priority. The lien is prior to\n"),
    ("6.13(a)", "all liens recorded after this Declaration, and\n"),
    ("6.13(b)", "all liens not recorded.\n"),
    ("6.14", "Association Funds. The accounts of the Association shall be kept at a bank.\n"),
    ("6.15", "Waiver of Exemptions. Each Owner waives the benefit of any homestead exemption.\n"),
]
READING = """6.12 Assessment Liens.
(a) Notice. At least 30 days before Recording a lien, the Association shall notify the Owner of:
(i) a general description of the collection procedures;
(ii) an itemized statement of the charges owed;
(1) Payments Made by Owner. Any payments made by the Owner shall be applied first to the principal.
(c) Meet and Confer. Before Recording a lien, the Association shall offer to meet and confer.
63) Anyproposed action which requires the consent of a specified percentage of Mortgagees.
(e) Lien Recorded in Error. A lien recorded in error shall be released.
(f) Use of Funds. The Board may use the funds of the Association for (i) managing and operating the
Development, and (ii) conducting the business of the Association.
6.13 Priority. The lien is prior to (i) all liens recorded after this Declaration, and (ii) all liens not recorded.
6.14 Waiver of Exemptions. Each Owner waives the benefit of any homestead exemption.
"""


def _reference() -> DocumentOutline:
    text, sections = "", []
    for number, words in REF_PARTS:
        depth = 1 + number.count(".") + number.count("(")
        sections.append(Section(number, words.split(".")[0], depth, len(text)))
        text += words
    out = DocumentOutline(key="decl", title="Declaration", text=text, sections=sections)
    for k, s in enumerate(sections):
        s.end = next((t.start for t in sections[k + 1:] if t.depth <= s.depth), len(text))
    return out


def test_alignment_renumbers_the_unclear_places_the_missing_and_keeps_the_firm():
    reading = outline_from_ocr(READING, key="decl")
    before = _numbers(reading)
    assert "6.12(a)(ii)(1)" in before and "6.12(b)" not in before     # "(1)": an unusual series, not firm
    assert "6.12(d)" not in before and "6.12(e)" in before            # "63)" is no label the order allows
    aligned = align_to_reference(reading, _reference(), label="the copy")
    numbers = _numbers(aligned)
    assert numbers == ["6.12", "6.12(a)", "6.12(a)(i)", "6.12(a)(ii)", "6.12(b)", "6.12(c)", "6.12(d)", "6.12(e)",
                       "6.12(f)", "6.12(f)(i)", "6.12(f)(ii)", "6.13", "6.14"]
    by = {m.number: m for m in aligned.marks}
    assert by["6.12(b)"].how is How.RENUMBERED and by["6.12(d)"].how is How.ALIGNED and by["6.12(d)"].raw == "63)"
    assert by["6.12(f)(i)"].how is How.ALIGNED and by["6.12(f)(ii)"].how is How.ALIGNED
    notes = {(n.kind, n.number): n.detail for n in aligned.notes}
    # A clear label in order is kept where the copy numbers its words otherwise, and the difference is said.
    assert "6.15" in notes[(NoteKind.DISAGREES, "6.14")]
    # The copy enumerates words the reading labels "(i)" and "(ii)": the reading's labels stand, unsplit.
    assert (NoteKind.DISAGREES, "6.13(a)") in notes and (NoteKind.DISAGREES, "6.13(b)") in notes
    assert (NoteKind.ONLY_IN_REFERENCE, "6.14") not in notes or "6.14" in numbers
    outline = aligned.outline()
    assert "(d) Anyproposed action" in outline.text and "(b) Payments" in outline.text
    assert outline.text_of(outline.section("6.12(f)(ii)")).startswith("(ii) conducting the business")
    payments = {p.number: p for p in provisions_of(outline)}["6.12(b)"]
    assert payments.caption == "Payments Made by Owner." and payments.body.startswith("Any payments")


def test_alignment_never_splits_words_without_a_label():
    reading = outline_from_ocr("7.1 Easements. Easements for (a) water, (b) power, and drainage facilities.\n", key="d")
    ref_text = "Easements.\nwater,\npower, and\ndrainage facilities.\n"
    starts = [0, ref_text.index("water"), ref_text.index("power"), ref_text.index("drainage")]
    ref = DocumentOutline(key="d", title="", text=ref_text, sections=[
        Section("7.1", "Easements.", 2, starts[0]), Section("7.1(a)", "water", 3, starts[1]),
        Section("7.1(b)", "power", 3, starts[2]), Section("7.1(c)", "drainage", 3, starts[3])])
    aligned = align_to_reference(reading, ref)
    assert _numbers(aligned) == ["7.1", "7.1(a)", "7.1(b)"]
    assert any(n.kind is NoteKind.ONLY_IN_REFERENCE and n.number == "7.1(c)" for n in aligned.notes)


def _heading(text, style="HEADING_2"):
    return {"paragraph": {"elements": [{"textRun": {"content": text + "\n"}}],
                          "paragraphStyle": {"namedStyleType": style}}}


def _plain(text):
    return {"paragraph": {"elements": [{"textRun": {"content": text + "\n"}}]}}


def test_build_numbers_a_text_base_by_the_option(tmp_path):
    import json
    import sqlite3

    from jason.community.living import LivingDocument, SourceKind, SourceRef
    from jason.community.symbols import DocumentKind
    from jason.tasks import living_docs as ld

    base = ("ARTICLE 4 USE RESTRICTIONS\n4.15 Rental of Condominiums. An Owner may rent a Unit.\n"
            "#.16 Pets. No animals other than household pets may be kept in a Unit.\n"
            "4.17 Signs. The Board may adopt reasonable limits on signs.\n")
    lib = tmp_path / "library"
    (lib / "text").mkdir(parents=True)
    with sqlite3.connect(lib / "library.db") as conn:
        conn.execute("CREATE TABLE documents (id TEXT, path TEXT, sha256 TEXT)")
        conn.execute("INSERT INTO documents VALUES ('1', 'Governing/Declaration.pdf', 'abc')")
    (lib / "text" / "1.txt").write_text(base, encoding="utf-8")
    copy = {"documentId": "copy-1", "body": {"content": [
        _heading("ARTICLE 4 - USE RESTRICTIONS", "HEADING_1"), _heading("4.15 Rental of Condominiums."),
        _plain("An Owner may rent a Unit."), _heading("4.16 Pets."),
        _plain("No animals other than household pets may be kept in a Unit."), _heading("4.17 Signs."),
        _plain("The Board may adopt reasonable limits on signs.")]}}
    cache = ld.living_dir(tmp_path, "decl") / "sources"
    cache.mkdir(parents=True)
    (cache / "copy-1.json").write_text(json.dumps(copy), encoding="utf-8")
    living = LivingDocument("decl", "Declaration", DocumentKind.DECLARATION,
                            base=SourceRef(SourceKind.LIBRARY_TEXT, "Governing/Declaration.pdf", sha256="abc"),
                            base_from="the recorded copy", working_doc="copy-1")
    assert ld.build(living, tmp_path, numbering="text").current.provision("4.16") is None
    labels = ld.build(living, tmp_path, numbering="labels")
    assert labels.current.provision("4.16") is None and any(n.kind is NoteKind.GAP for n in labels.numbering)
    built = ld.build(living, tmp_path, numbering="aligned", working=True, all_sections=True)
    assert built.current.provision("4.16").body.startswith("No animals")
    assert any(n.kind is NoteKind.ALIGNED and n.number == "4.16" for n in built.numbering)
    assert not [f for f in built.drift if "only in" in f.detail or "missing" in f.detail]
    report = json.loads((ld.write(built, tmp_path).parent / "report.json").read_text(encoding="utf-8"))
    assert any(line.startswith("aligned: 4.16") for line in report["numbering"])


def test_openings_compare_across_ocr_spacing():
    assert opening_key("1.4 Articles ofIncorporation ofthe Association") == opening_key(
        "Articles of Incorporation of the Association")
    assert similarity(opening_key("Theright ofthe Board"), opening_key("The right of the Board")) == 1.0
