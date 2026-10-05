"""Which document a citation means (``jason.community.scoping``), on made-up documents: the forms a citation is written
in, the scoping rules and the basis each gives, the ambiguity state that names every document that fits, the section
a document prints twice, and jason's own rule rows cited as a plan item writes them."""

import json

import pytest

from jason.community import scoping as S
from jason.community.books import Book, BookEntry
from jason.community.outlines import CitableDocument, outline_from_doc, outline_from_text
from jason.community.symbols import DocumentKind
from jason.tasks.cite import Shelf, resolve
from tests.test_cite import world  # noqa: F401  (a living declaration the shelf reads as amended)

NAMES = {"covenants": "decl", "declaration": "decl", "cc&r": "decl", "bylaws": "bylaws", "by-laws": "bylaws",
         "handbook": "handbook", "rules": "handbook", "rules and regulations": "handbook", "parking rules": "parking",
         "owner's manual": "manual"}


# --- What is written ----------------------------------------------------------------------------------------------------

def _forms(text, headings=False):
    """What a text cites; a line that is only "Article 4" or "R-3(e)" is a heading in a document, a citation alone."""
    return [(m.form, m.number, m.name.lower(), m.demonstrative)
            for m in S.scan(text, NAMES, lettered=("R",), headings=headings)]


@pytest.mark.parametrize("text, expect", [
    ("Section 7.8 of the Bylaws", (S.Form.SECTION, "7.8", "bylaws", "")),
    ("CC&R 7.8 (a)", (S.Form.SECTION, "7.8(a)", "cc&r", "")),
    ("Covenants, Section 6.2", (S.Form.SECTION, "6.2", "covenants", "")),
    ("Rules R-3(e)", (S.Form.RULE_LETTERED, "R-3(e)", "rules", "")),
    ("Owner's Manual R-3(e)", (S.Form.RULE_LETTERED, "R-3(e)", "owner's manual", "")),
    ("Rule 2.1 of the Parking Rules", (S.Form.RULE_NUMBERED, "2.1", "parking rules", "")),
    ("Article IV of the Bylaws", (S.Form.ARTICLE, "4", "bylaws", "")),
    ("Article 4", (S.Form.ARTICLE, "4", "", "")),
    ("Section 7.8", (S.Form.SECTION, "7.8", "", "")),
    ("R-3(e)", (S.Form.RULE_LETTERED, "R-3(e)", "", "")),
    ("this Declaration", (S.Form.SELF, "", "declaration", "this")),
    ("these Bylaws", (S.Form.SELF, "", "bylaws", "these")),
    ("Section 5 of this Policy", (S.Form.SECTION, "5", "policy", "this")),
    ("the Rules and Regulations", (S.Form.DOCUMENT, "", "rules and regulations", "")),
])
def test_the_forms_a_citation_is_written_in(text, expect):
    found = _forms(text)
    assert found and found[0] == expect, found


def test_a_citation_of_the_law_or_a_heading_or_a_year_is_not_one_of_the_documents():
    assert _forms("Section 5 of the Civil Code and section 602(k) of the Penal Code") == []
    assert _forms("ARTICLE 5 - ASSESSMENTS\nThe Covenants control in 2019.", True) == [
        (S.Form.DOCUMENT, "", "covenants", "")]                       # a heading is not a citation; the name is a mention
    assert _forms("R-3. PARKING\nHO-6 is a form.", True) == []         # a heading, and a form's code, are not rules cited
    assert _forms("see HO-6 and rule R-3", True) == [(S.Form.RULE_LETTERED, "R-3", "", "")]


def test_a_list_after_one_name_covers_each_number_and_a_second_citation_starts_its_own():
    found = S.scan("Section 6.5(d) and Section 6.6(c) of the Covenants; Bylaws 7.8, 7.9, and 7.10.", NAMES)
    assert [(m.number, m.name.lower()) for m in found] == [("6.5(d)", "covenants"), ("6.6(c)", "covenants"), ("7.8", "bylaws")]
    assert found[0].expression == "Section 6.5(d) of the Covenants"
    assert found[2].numbers == ("7.8", "7.9", "7.10")


def test_a_name_in_lower_case_prose_is_not_a_mention_but_a_name_with_a_number_is():
    assert [m.form for m in S.scan("the rules require a leash", NAMES)] == []
    assert [m.form for m in S.scan("see rules R-3", NAMES, lettered=("R",))] == [S.Form.RULE_LETTERED]


def test_an_expression_is_read_whole_with_its_roman_article_and_trailing_as_amended():
    assert S.clean_expression("Section 7.8 of the Bylaws, as amended.") == "Section 7.8 of the Bylaws"
    assert S.clean_expression("Article IV of the Bylaws") == "Article 4 of the Bylaws"
    m = S.read_expression("Section 7.8 of the Bylaws as restated", NAMES)
    assert m is not None and m.number == "7.8"
    assert S.rewrite("Section 7.8 of the Bylaws", m, "bylaws") == "Section 7.8 of the bylaws"
    assert S.read_expression("this Declaration", NAMES).form is S.Form.SELF
    assert S.read_expression("Section 7.8 and something else entirely", NAMES) is None
    this = S.read_expression("this Declaration, Section 4.15", NAMES)
    assert S.rewrite("this Declaration, Section 4.15", this, "decl") == "decl, Section 4.15"


# --- Scoping ------------------------------------------------------------------------------------------------------------

SECTIONS = {"decl": {"4.15", "6.2", "6.2(a)", "7.8", "4", "6"}, "bylaws": {"4", "4.1", "7.8", "6"},
            "handbook": {"R-1", "R-3", "R-3(e)"}, "parking": {"R-3", "R-3(e)", "R-4"},
            "amend": {"2"}, "manual": {"R-3", "R-3(e)"}}
WORDS = {("handbook", "R-3(e)"): "Fire lanes are kept clear.", ("parking", "R-3(e)"): "Fire lanes are kept clear.",
         ("manual", "R-3(e)"): "Fire lanes are kept clear.",
         ("handbook", "R-3"): "Parking.", ("parking", "R-3"): "Parking is permitted in garages.",
         ("manual", "R-3"): "Parking is allowed."}


def _index():
    docs = {"decl": S.DocInfo("decl", "Covenants", "declaration", "decl", articles=True),
            "bylaws": S.DocInfo("bylaws", "Bylaws", "bylaws", "bylaws", articles=True),
            "handbook": S.DocInfo("handbook", "Handbook", "operating_rules", "rules", lettered="R"),
            "parking": S.DocInfo("parking", "Parking Rules", "operating_rules", "rules.parking", lettered="R"),
            "amend": S.DocInfo("amend", "First Amendment", "amendment", "decl", amends="decl", pooled=False)}
    names = dict(NAMES, **{"first amendment": "amend"})
    del names["owner's manual"]
    return S.Index(docs, names, {"rules": ("handbook", "parking"), "rules and regulations": ("handbook", "parking")},
                   has=lambda key, number, day: number in SECTIONS.get(key, ()),
                   words=lambda key, number: WORDS.get((key, number), ""), scan_names=names)


def _scope(text, citing=None, index=None):
    index = index or _index()
    m = S.read_expression(text, index.scan_names, lettered=index.lettered_prefixes())
    assert m is not None, text
    return S.scope(m, citing, index)


def test_a_bare_section_inside_a_document_that_has_it_is_that_documents_own():
    s = _scope("Section 7.8", S.Citing("bylaws", "bylaws"))
    assert (s.standing, s.key, s.basis) == (S.Standing.SCOPED, "bylaws", S.Basis.CITING)


def test_a_bare_section_in_an_amendment_is_the_document_it_amends_unless_it_has_the_section_itself():
    amends = S.Citing("amend", "amendment", amends="decl")
    assert (_scope("Section 4.15", amends).key, _scope("Section 4.15", amends).basis) == ("decl", S.Basis.AMENDS)
    assert (_scope("Section 2", amends).key, _scope("Section 2", amends).basis) == ("amend", S.Basis.CITING)


def test_a_bare_section_in_minutes_names_every_document_that_has_it_and_picks_none():
    s = _scope("Section 7.8")
    assert s.standing is S.Standing.AMBIGUOUS and s.key == ""
    assert {c.key for c in s.candidates if c.has} == {"decl", "bylaws"}


def test_a_name_written_nearby_is_a_lead_and_never_a_pick():
    m = S.scan("The CC&R was read. The board cited Section 7.8 later.", NAMES)[1]
    s = S.scope(m, S.Citing(), _index())
    assert s.standing is S.Standing.AMBIGUOUS and s.leads == ("decl",)


def test_a_bare_number_one_document_has_is_that_document_by_elimination_and_says_so():
    s = _scope("Section 4.15")
    assert (s.standing, s.key, s.basis) == (S.Standing.SCOPED, "decl", S.Basis.ONLY)


def test_the_form_narrows_the_documents_a_lettered_rule_belongs_to_rules_documents():
    s = _scope("R-1")
    assert (s.key, s.basis) == ("handbook", S.Basis.FORM)
    assert _scope("R-9").standing is S.Standing.NO_SECTION
    assert [c.key for c in _scope("Article 4").candidates if c.has] == ["decl", "bylaws"]


def test_the_same_rule_printed_in_a_part_and_in_the_document_adopted_apart_is_the_one_adopted_apart():
    s = _scope("R-3(e)")
    assert (s.standing, s.key, s.basis, s.part) == (S.Standing.SCOPED, "parking", S.Basis.PART, "rules.parking")
    assert s.also == ("handbook",)
    different = _scope("R-3")                                           # printed with other words: two documents fit
    assert different.standing is S.Standing.AMBIGUOUS


def test_a_book_name_covers_its_documents_and_the_document_that_has_the_section_is_the_one():
    assert _scope("Rules R-4").key == "parking"
    whole = _scope("the Rules")
    assert (whole.key, whole.basis) == ("handbook", S.Basis.BOOK) and whole.also == ("parking",)
    assert _scope("Rules R-1", S.Citing("handbook", "operating_rules")).basis is S.Basis.CITING
    assert _scope("these Rules").standing is S.Standing.AMBIGUOUS         # written in text that is not one of them
    assert _scope("these Rules", S.Citing("parking", "operating_rules")).basis is S.Basis.SELF


def test_self_reference_is_the_citing_document_and_otherwise_the_named_one_with_a_note():
    assert _scope("this Declaration", S.Citing("decl", "declaration")).basis is S.Basis.SELF
    other = _scope("this Declaration", S.Citing("bylaws", "bylaws"))
    assert (other.key, other.basis) == ("decl", S.Basis.NAMED) and "the citing document is bylaws" in other.note
    assert _scope("Section 5 of this Policy", S.Citing("bylaws", "bylaws")).basis is S.Basis.SELF


def test_a_name_the_association_does_not_use_is_an_unknown_document_never_a_guess():
    m = S.scan("Section 3 of the Master Plan applies.", NAMES)[0]
    assert S.scope(m, S.Citing("bylaws", "bylaws"), _index()).standing is S.Standing.UNKNOWN_DOCUMENT


# --- The shelf ----------------------------------------------------------------------------------------------------------

def _doc(tmp_path, key, title, kind, text):
    outline = outline_from_text(text, key=key, title=title, kind=kind)
    folder = tmp_path / "outlines"
    folder.mkdir(exist_ok=True)
    (folder / f"{key}.json").write_text(json.dumps(outline.to_dict()), encoding="utf-8")
    return outline


@pytest.fixture
def shelf(tmp_path):
    from types import SimpleNamespace

    _doc(tmp_path, "covenants", "Covenants", "declaration",
         "ARTICLE 4 USE\n4.15 Rental. Units may be let.\n(a) Notice. The owner gives notice.\nARTICLE 6 DUES\n6.2 Dues. Ten.\n"
         "7.8 Fines. The covenants' fine.\n")
    _doc(tmp_path, "bylaws", "Bylaws", "bylaws", "ARTICLE 4 MEETINGS\n4.1 Annual. Once a year.\n7.8 Records. The bylaws' own.\n")
    _doc(tmp_path, "handbook", "Handbook", "operating_rules",
         "R-1. Pets\n(a) Leashed.\nR-3. Parking\n(e) Fire lanes are kept clear.\nR-3. Parking again\n(a) A second R-3.\n")
    _doc(tmp_path, "parking", "Parking Rules", "operating_rules", "R-3. Parking\n(e) Fire lanes are kept clear.\n")
    community = SimpleNamespace(
        living_documents=lambda: (),
        citable_documents=lambda: (
            CitableDocument("covenants", "Covenants", "d1", DocumentKind.DECLARATION, aliases=("Declaration", "CC&R"),
                            cite_as="Covenants"),
            CitableDocument("bylaws", "Bylaws", "d2", DocumentKind.BYLAWS, aliases=("Bylaws",), cite_as="Bylaws"),
            CitableDocument("handbook", "Handbook", "d3", DocumentKind.OPERATING_RULES, aliases=("Handbook",)),
            CitableDocument("parking", "Parking Rules", "d4", DocumentKind.OPERATING_RULES, aliases=("Parking Rules",))),
        book_entries=lambda: (BookEntry("covenants", Book.DECL), BookEntry("bylaws", Book.BYLAWS),
                              BookEntry("handbook", Book.RULES), BookEntry("parking", Book.RULES, part="parking")),
        conflicts=lambda: (), notice_provisions=lambda: ())
    return Shelf(community, tmp_path, repo=tmp_path / "no-repo")


def test_a_bare_section_is_scoped_by_where_it_is_written_and_ambiguous_where_that_does_not_say(shelf):
    here = resolve("Section 7.8", shelf=shelf, citing="bylaws")
    assert here["found"] and here["citation"] == "Bylaws Section 7.8" and here["scope"]["basis"] == "citing"
    lost = resolve("Section 7.8", shelf=shelf)
    assert not lost["found"] and lost["reason"] == "ambiguous_document"
    assert "Covenants Section 7.8 (covenants)" in lost["detail"] and "Bylaws Section 7.8 (bylaws)" in lost["detail"]
    assert {c["document"] for c in lost["scope"]["candidates"] if c["has"]} == {"covenants", "bylaws"}


def test_an_article_a_self_reference_and_a_trailing_as_amended_resolve(shelf):
    assert resolve("Article IV", shelf=shelf, citing="bylaws", text=False)["citation"] == "Bylaws Article 4"
    own = resolve("these Bylaws", shelf=shelf, citing="bylaws", text=False)
    assert own["found"] and own["scope"]["basis"] == "self"
    assert resolve("Section 4.15 of the CC&R as amended", shelf=shelf)["citation"] == "Covenants Section 4.15"
    assert resolve("CC&R 4.15 (a)", shelf=shelf)["found"]


def test_a_rule_written_without_its_document_is_the_one_adopted_apart_when_both_print_the_same_words(shelf):
    both = resolve("R-3(e)", shelf=shelf)
    assert both["found"] and both["scope"]["basis"] == "part" and both["scope"]["document"] == "parking"
    assert both["scope"]["alsoPrintedIn"] == ["handbook"]
    assert resolve("Rules R-3(e)", shelf=shelf)["scope"]["document"] == "parking"
    miss = resolve("Rules R-9", shelf=shelf)
    assert not miss["found"] and "R-n" in miss["detail"]


def test_the_rule_numbered_in_the_wrong_style_says_how_the_document_does_number_its_rules(shelf):
    miss = resolve("Rule 2.1 of the Parking Rules", shelf=shelf)
    assert not miss["found"] and miss["reason"] == "not_in_document" and "numbers its sections R-n" in miss["detail"]


def test_a_section_a_document_prints_twice_is_cited_by_its_place(shelf):
    both = resolve("handbook#R-3", shelf=shelf)
    assert both["reason"] == "ambiguous" and "R-3~2" in both["detail"]
    second = resolve("handbook#R-3~2", shelf=shelf)
    assert second["found"] and "A second R-3" in second["text"]
    assert not resolve("handbook#R-3~3", shelf=shelf)["found"]


def test_a_bare_section_in_a_living_document_is_read_in_the_version_in_force_on_the_citing_day(world):
    shelf, _ = world
    then = resolve("Section 6.2(a)", shelf=shelf, citing_day="2020-01-01")
    now = resolve("Section 6.2(a)", shelf=shelf, citing_day="2026-01-01")
    assert then["found"] and "ten percent (10%)" in then["text"] and then["target"].endswith("@2020-01-01")
    assert "fifteen percent (15%)" in now["text"]
    assert then["scope"]["basis"] == "only"


# --- Rule rows ----------------------------------------------------------------------------------------------------------

def test_a_rule_row_is_recited_as_data_and_labeled_as_jasons_own(shelf):
    r = resolve("owner_responses.RULES: delivery", shelf=shelf)
    assert r["found"] and r["kind"] == "row" and r["citation"] == "owner_responses.RULES: delivery"
    assert "key: delivery" in r["text"] and "A signed-in delivery choice sets the delivery tags." in r["text"]
    assert "not a rule of the association" in r["caveat"]
    assert r["row"]["outcome"] == "record" and r["row"]["condition"]["function"] == "_delivery"
    assert r["row"]["condition"]["where"].startswith("src/jason/tasks/owner_responses.py:")
    assert "def _delivery" in r["row"]["condition"]["source"]


def test_a_row_that_rests_on_a_board_item_names_it(shelf):
    r = resolve("the response policy's required-blank row (owner_responses.RULES: required-blank)", shelf=shelf)
    assert r["found"] and r["adoption"]["address"] == "board-item:rental-approvals-4-15"
    assert resolve("owner_responses.RULES: delivery", shelf=shelf).get("adoption") is None


def test_a_table_a_module_keeps_is_recited_row_by_row_and_a_missing_row_lists_the_rows(shelf):
    r = resolve("owner_info.FOR_A_PERSON", shelf=shelf)
    assert r["found"] and {row["key"] for row in r["rows"]} == {"email", "mailing address", "secondary delivery",
                                                                "property manager"}
    assert "a person enters the email" in r["text"]
    miss = resolve("owner_responses.RULES: no-such-row", shelf=shelf)
    assert not miss["found"] and miss["reason"] == "not_in_document" and "delivery" in miss["detail"]


def test_one_attribute_of_the_specification_is_recited_through_a_community_method(tmp_path):
    from types import SimpleNamespace

    held = SimpleNamespace(EARLIER_ELECTIONS={"email": "a made-up rule"})
    shelf = Shelf(SimpleNamespace(living_documents=lambda: (), citable_documents=lambda: (), owner_information=lambda: held),
                  tmp_path, repo=tmp_path / "no-repo")
    r = resolve("Community.owner_information: EARLIER_ELECTIONS", shelf=shelf)
    assert r["found"] and "a made-up rule" in r["text"] and r["kind"] == "row"
    assert not resolve("Community.owner_information: NO_SUCH", shelf=shelf)["found"]
    assert not resolve("Community.__init__: X", shelf=shelf)["found"]


def test_a_module_attribute_is_recited_with_the_decision_written_above_it(tmp_path):
    import importlib.util
    from types import SimpleNamespace

    source = tmp_path / "made_up_forms.py"
    source.write_text("# The board, January 2, 2000: a made-up decision.\n# Its second line.\nDONE_COMMENT = 'thanks'\n",
                      encoding="utf-8")
    spec = importlib.util.spec_from_file_location("made_up_forms", source)
    held = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(held)
    shelf = Shelf(SimpleNamespace(living_documents=lambda: (), citable_documents=lambda: (), owner_information=lambda: held),
                  tmp_path, repo=tmp_path / "no-repo")
    r = resolve("the board's rule (Community.owner_information: DONE_COMMENT)", shelf=shelf)
    assert r["found"] and r["row"]["comment"] == "The board, January 2, 2000: a made-up decision. Its second line."
    assert "made-up decision" in r["text"] and r["row"]["where"].endswith("made_up_forms.py:3")


def test_every_plan_kinds_rule_is_an_address_the_approvals_screen_recites():
    from jason.approvals import registry
    from jason.web import approvals

    for kind in registry.kinds():
        r = approvals.recite(kind.rule)
        assert r["found"], (kind.key, kind.rule, r.get("reason"))


def test_the_approvals_screen_recites_a_row_as_it_recites_a_section():
    from jason.web import approvals

    r = approvals.recite("owner_responses.RULES: delivery")
    assert r["found"] and r["kind"] == "row" and "delivery" in r["text"]


# --- Rule documents as outlines -----------------------------------------------------------------------------------------

def test_a_rules_text_with_lettered_rules_is_outlined_into_addresses_like_r_3_e():
    o = outline_from_text("R-1. Pets\n(a) Leashed.\nR-3. Parking\n(e) Fire lanes.\nRule 4.1 Noise. Quiet hours.\n",
                          key="rules")
    assert [s.number for s in o.sections] == ["R-1", "R-1(a)", "R-3", "R-3(e)", "4.1"]
    assert o.section("R-3(e)").parent == "R-3"


def test_a_list_that_numbers_the_sections_itself_does_not_hang_its_sublist_from_them_twice():
    lists = {"L": {"listProperties": {"nestingLevels": [{"glyphType": "DECIMAL", "glyphFormat": "%0."},
                                                        {"glyphType": "ALPHA", "glyphFormat": "%1."}]}}}

    def para(text, style, level):
        return {"paragraph": {"paragraphStyle": {"namedStyleType": style}, "bullet": {"listId": "L", "nestingLevel": level},
                              "elements": [{"textRun": {"content": text + "\n"}}]}}

    doc = {"title": "Policy", "tabs": [{"documentTab": {"lists": lists, "body": {"content": [
        para("Assessments.", "HEADING_2", 0), para("Dispute of Charges.", "HEADING_2", 0),
        para("The owner's name.", "NORMAL_TEXT", 1), para("The amount in dispute.", "NORMAL_TEXT", 1)]}}}]}
    assert [s.number for s in outline_from_doc(doc, key="policy").sections] == ["1", "2", "2(a)", "2(b)"]


# --- Sections named by their heading, by a former number, and a text read whole ----------------------------------------------

def test_a_section_named_by_its_heading_is_the_one_section_whose_title_starts_so(shelf):
    use = resolve("covenants#USE", shelf=shelf)
    assert use["found"] and use["citation"] == "Covenants Article 4" and use["version"]["titled"]["to"] == "4"
    assert not resolve("covenants#NOTHING", shelf=shelf)["found"]


def test_a_number_the_document_had_is_read_as_the_number_a_permanent_id_places_it_at_and_says_so(world):
    from types import SimpleNamespace

    shelf, _ = world
    shelf._locator = SimpleNamespace(errors=[], table=lambda document: None, locate=lambda *a, **k: SimpleNamespace(
        number="6.2(a)", ambiguous=False, removed=False, pid="decl@base/6.2(a)"))
    moved = resolve("Covenants 6.2(c)", shelf=shelf)
    assert moved["found"] and moved["version"]["renumbered"] == {
        "from": "6.2(c)", "to": "6.2(a)", "pid": "decl@base/6.2(a)",
        "note": "6.2(c) is a number this document had; a permanent id places it at 6.2(a) now"}
    shelf._locator = SimpleNamespace(errors=[], table=lambda document: None, locate=lambda *a, **k: SimpleNamespace(
        number="6.2(a)", ambiguous=True, removed=False, pid="x"))
    assert not resolve("Covenants 6.2(c)", shelf=shelf)["found"]               # more than one: a miss stays a miss


def test_a_text_is_read_whole_each_citation_resolved_and_counted_by_form(shelf):
    from jason.tasks.cite_scope import read_text, tally

    text = ("The Board cited Section 7.8 and R-1(a). Under Section 4.15 of the CC&R and covenants#7.8, see "
            "owner_responses.RULES: delivery. Section 3 of the Master Plan is not ours; neither is Section 5 of the Civil Code.")
    rows = read_text(shelf, text, citing="")
    by = {r["text"]: r for r in rows}
    assert by["Section 7.8"]["status"] == "ambiguous document" and sorted(by["Section 7.8"]["candidates"]) == ["bylaws", "covenants"]
    assert by["R-1(a)"]["status"] == "resolved" and by["R-1(a)"]["document"] == "handbook" and by["R-1(a)"]["basis"] == "form"
    assert by["Section 4.15 of the CC&R"]["basis"] == "named"
    assert by["covenants#7.8"]["form"] == "address" and by["covenants#7.8"]["status"] == "resolved"
    assert by["owner_responses.RULES: delivery"]["form"] == "jason's rule row"
    assert by["Section 3 of the Master Plan"]["status"] == "unknown document"
    assert not any("Civil Code" in r["text"] for r in rows)
    assert tally(rows)["section (bare)"] == {"ambiguous document": 1}
    here = read_text(shelf, "Section 7.8 is the bylaws' own.", citing="bylaws")
    assert here[0]["document"] == "bylaws" and here[0]["basis"] == "citing"
