"""Record addresses, the books, and permanent section ids, on made-up documents: keys and aliases, the address round
trip, versions as of a day and made effective on one, stage versions, restricted books, permanent ids through an
amendment that renumbers and a reading that numbers differently, defined terms, and the migration."""

import json
import sqlite3
from datetime import date
from types import SimpleNamespace

import pytest

from jason.community.addresses import Address, AddressError, VersionLabel, parse, pid
from jason.community.books import Book, BookEntry, Books, Role, Shape, book_named, default_book
from jason.community.cite import Kind, Reason, Target, Treatment, Unit
from jason.community.definitions import DefinedTerm, GoverningSet, compare_governing, read, used_in
from jason.community.deontic import Bearer, DocumentDuty, DutyKind
from jason.community.living import LivingDocument, LivingInstrument, SourceKind, SourceRef
from jason.community.outlines import CitableDocument, DocumentOutline, Section
from jason.community.permanent_ids import IdTable, Name, add_reading, carry, from_lineages, from_versions
from jason.community.revisions import RecordVersion, Stage
from jason.community.symbols import DocumentKind
from jason.tasks.cite import Shelf, resolve

OLD = "No more than ten percent (10%) of the Lots shall be let at any one time without the Board's written consent."
NEW = "No more than fifteen percent (15%) of the Lots shall be let at any one time without the Board's written consent."
NOTICE = "An Owner who lets a Lot shall give the Board written notice of the letting within ten days."
DRAFT = "An Owner who lets a Lot shall give the Board written notice of the letting within five days."
BIRDS = "No poultry or livestock shall be kept on any Lot. The Board may adopt Rules for birds kept as pets."
SIGNS = "An Owner shall post no sign larger than one square foot in a window of a Unit."

BASE = f"""ARTICLE 1
1.1 Rules. "Rules" shall mean the regulations the Board adopts for the use of the Common Area.
ARTICLE 6
6.2 Letting of Lots.
(a) Limit. {OLD}
(b) Notice. {NOTICE}
6.3 Animals. {BIRDS}
"""


def _run(text, bold=False, strike=False):
    return {"textRun": {"content": text, "textStyle": {"bold": bold, "strikethrough": strike}}}


def _doc(paragraphs):
    return {"revisionId": "rev-1", "body": {"content": [{"paragraph": {"elements": p}} for p in paragraphs]}}


def _first_amendment():
    return _doc([
        [_run("NOW, THEREFORE, the Association declares:\n")],
        [_run("Article 6, Section 6.2, subsection (a) (\"Limit\") is hereby amended and restated as follows "
              "(stricken out wording will be removed, and bolded wording will be added):\n")],
        [_run("No more than "), _run("ten percent (10%)", strike=True), _run(" "),
         _run("fifteen percent (15%)", bold=True), _run(OLD.split("(10%)", 1)[1] + "\n")],
        [_run("Article 6, Section 6.2 is hereby amended to add the following subsection:\n")],
        [_run(f"(c) Signs. {SIGNS}\n")],
        [_run("IN WITNESS WHEREOF, the Board.\n")],
    ])


def _draft_amendment():
    return _doc([
        [_run("NOW, THEREFORE, the Association declares:\n")],
        [_run("Article 6, Section 6.2, subsection (b) (\"Notice\") is hereby amended and restated as follows "
              "(stricken out wording will be removed, and bolded wording will be added):\n")],
        [_run(NOTICE.split("ten days")[0]), _run("ten", strike=True), _run(" "), _run("five", bold=True),
         _run(" days.\n")],
        [_run("IN WITNESS WHEREOF, the Board.\n")],
    ])


def _outline(key, title, kind, lines):
    """An outline from (number, caption, words) rows, its offsets computed."""
    text, sections = "", []
    for number, caption, words in lines:
        start = len(text)
        text += f"{number} {caption} {words}\n"
        sections.append(Section(number, caption, 1 + number.count(".") + number.count("("), start, len(text)))
    return DocumentOutline(key, title, kind=kind, text=text, sections=sections)


@pytest.fixture
def world(tmp_path):
    lib = tmp_path / "library"
    (lib / "text").mkdir(parents=True)
    with sqlite3.connect(lib / "library.db") as conn:
        conn.execute("CREATE TABLE documents (id TEXT, path TEXT, kind TEXT, confidential INTEGER, sha256 TEXT)")
        conn.execute("INSERT INTO documents VALUES ('1', 'Governing/Covenants.pdf', 'declaration', 0, 'abc')")
    (lib / "text" / "1.txt").write_text(BASE, encoding="utf-8")
    sources = tmp_path / "living" / "cov" / "sources"
    sources.mkdir(parents=True)
    (sources / "doc-2.json").write_text(json.dumps(_first_amendment()), encoding="utf-8")
    (sources / "doc-3.json").write_text(json.dumps(_draft_amendment()), encoding="utf-8")
    first = SimpleNamespace(title="First Amendment", recorded=date(2099, 3, 1), adopted=None,
                            recorder_number="209903010001")
    draft = SimpleNamespace(title="Second Amendment", recorded=None, adopted=None, recorder_number="")
    living = LivingDocument("cov", "Covenants", DocumentKind.DECLARATION,
                            base=SourceRef(SourceKind.LIBRARY_TEXT, "Governing/Covenants.pdf", sha256="abc"),
                            base_from="the recorded copy",
                            instruments=(LivingInstrument("cov-1st", first, SourceRef(SourceKind.DOC, "doc-2")),
                                         LivingInstrument("cov-2nd", draft, SourceRef(SourceKind.DOC, "doc-3"))))
    outlines = tmp_path / "outlines"
    outlines.mkdir()
    # The working copy as outlined numbers the animals section 6.4 and runs 6.2(b) under (ii).
    copy = _outline("cov", "Covenants", "declaration", [
        ("1.1", "Rules.", '"Rules" shall mean the regulations the Board adopts for the use of the Common Area.'),
        ("6.2", "Letting of Lots.", ""), ("6.2(a)", "Limit.", NEW), ("6.2(ii)", "Notice.", NOTICE),
        ("6.2(c)", "Signs.", SIGNS), ("6.4", "Animals.", BIRDS)])
    (outlines / "cov.json").write_text(json.dumps(copy.to_dict()), encoding="utf-8")
    rules = _outline("rules", "Handbook", "operating_rules", [
        ("B-1", "Letting.", "Owners who let a Lot follow the Covenants."),
        ("B-2", "Pets.", "Birds are pets under the Covenants."),
        ("B-2", "Parking.", "Residents park only in their own garage.")])
    (outlines / "rules.json").write_text(json.dumps(rules.to_dict()), encoding="utf-8")
    (outlines / "references.json").write_text("[]", encoding="utf-8")
    duties = tmp_path / "duties"
    duties.mkdir()
    duty = DocumentDuty("cov", "6.4", 0, 10, "No poultry or livestock shall be kept on any Lot.", DutyKind.PROHIBITION,
                        Bearer.OWNER, "No ... shall")
    parking = DocumentDuty("rules", "B-2", 0, 10, "Residents park only in their own garage.", DutyKind.DUTY,
                           Bearer.OWNER, "only")
    for key, items in (("cov", [duty]), ("rules", [parking])):
        (duties / f"{key}.json").write_text(json.dumps({"source": key, "reader": "grammar", "read": "2099-04-01",
                                                        "duties": [d.to_dict() for d in items], "reviews": {}}),
                                            encoding="utf-8")
    community = SimpleNamespace(
        living_documents=lambda: (living,),
        citable_documents=lambda: (CitableDocument("cov", "Covenants", "doc-1", DocumentKind.DECLARATION,
                                                   aliases=("Covenants",), cite_as="Covenants"),
                                   CitableDocument("rules", "Handbook", "doc-4", DocumentKind.OPERATING_RULES,
                                                   aliases=("Handbook",))),
        book_entries=lambda: (BookEntry("cov", Book.DECL), BookEntry("rules", Book.RULES, part="handbook"),
                              BookEntry("rules", Book.MANUAL)),
        defined_terms=lambda: (DefinedTerm("Rules", "cov", "1.1"), DefinedTerm("Common Area", "cov", "1.9")),
        governing_set=lambda: GoverningSet("decl#1.1", (Book.DECL, Book.RULES, Book.RES),
                                           also=("the policies the Board adopts",)),
        conflicts=lambda: (), notice_provisions=lambda: ())
    return Shelf(community, tmp_path, repo=tmp_path / "no-repo"), tmp_path


# --- The books -----------------------------------------------------------------------------------------------------------

def test_the_keys_are_a_closed_set_with_their_statutes():
    assert Book("decl").info.statute == "CIV 4135" and Book.RULES.info.statute == "CIV 4340(a)"
    assert Book.RES.info.shape is Shape.SERIES and Book.DECL.living and Book.GOV.info.shape is Shape.GROUP
    assert {b.value for b in Book if b.restricted} == {"exec", "members", "ballots"}
    assert Book.DECL.governing and not Book.MANUAL.governing
    assert default_book(DocumentKind.BYLAWS) is Book.BYLAWS and default_book(DocumentKind.POLICY) is None
    assert default_book(DocumentKind.ANNEXATION) is Book.DECL


def test_common_names_are_the_canon_without_case_or_punctuation():
    for name in ("CC&R's", "CC & Rs", "ccrs", "Covenants, Conditions and Restrictions", "Master Declaration"):
        assert book_named(name) is Book.DECL, name
    assert book_named("BY-LAWS") is Book.BYLAWS and book_named("House Rules") is Book.RULES
    assert book_named("decl") is Book.DECL and book_named("Owner Handbook") is None


def test_the_profile_maps_documents_onto_keys_both_ways():
    books = Books([BookEntry("cov", Book.DECL), BookEntry("cov-1st", Book.DECL, role=Role.AMENDMENT),
                  BookEntry("parking", Book.RULES, part="parking")])
    assert books.document("decl") == "cov" and books.key("cov") == "decl" and books.key("cov-1st") == "decl"
    assert books.document("rules.parking") == "parking" and books.key("parking") == "rules.parking"
    assert books.document("cov") == "cov"                          # a document's own key is an alias
    assert books.named("CC & R's") == "cov" and books.named("Bylaws") == ""
    assert books.restricted("exec") == "CIV 5215(a)(5)(D)"


# --- Addresses -----------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("text", [
    "jason://decl/4.15(a)", "jason://decl@2099-01-01/4.15(a)", "jason://decl:2099-06-01/4.15(a)",
    "jason://decl/history/4.15(a)", "jason://rules@proposed-2099-11-01", "jason://res/20990101-1",
    "jason://min/2099-01-01#item-4", "jason://inst/209901010001", "jason://rules.parking/B-1",
    "jason://decl@base/4.15(a)", "jason://min/2099-01-01@draft-2099-01-20", "jason://decl/6.2..6.4",
    "jason://rules/B-2~2", "jason://gov",
])
def test_an_address_round_trips(text):
    assert parse(text).format() == text


def test_an_address_names_its_parts():
    a = parse("jason://decl@2099-01-01/4.15(a)")
    assert a.book is Book.DECL and a.section == "4.15(a)" and a.label.effective == date(2099, 1, 1)
    assert parse("jason://decl:2099-06-01/4.15(a)").in_force == date(2099, 6, 1)
    stage = parse("jason://rules@proposed-2099-11-01").label
    assert stage.stage is Stage.PROPOSED and stage.day == date(2099, 11, 1) and stage.effective is None
    assert parse("jason://min/2099-01-01#item-4").item == "2099-01-01" and parse("jason://rules.parking/B-1").part == \
        "parking"
    assert pid("decl", "base", "4.15(a)") == "decl@base/4.15(a)" and parse("decl@base/4.15(a)").section == "4.15(a)"


def test_a_stage_version_label_is_the_revision_models():
    proposed = RecordVersion("rules", "", Stage.PROPOSED, date(2099, 11, 1), None)
    adopted = RecordVersion("rules", "", Stage.ADOPTED, date(2099, 12, 1), date(2099, 12, 1))
    assert parse("jason://rules" + proposed.label()).label.stage is Stage.PROPOSED
    assert parse("jason://rules" + adopted.label()).label.effective == date(2099, 12, 1)


@pytest.mark.parametrize("text", ["jason://res@2099-01-01/1", "jason://decl@2099-01-01:2099-01-01/1",
                                  "jason://Decl/1", "jason://decl/4.15 (a)", "jason://"])
def test_a_bad_address_says_why(text):
    with pytest.raises(AddressError):
        parse(text)


# --- Resolving addresses ---------------------------------------------------------------------------------------------------

def test_an_address_resolves_through_the_books_and_every_citation_carries_one(world):
    shelf, _ = world
    got = resolve("jason://decl/6.2(a)", shelf=shelf)
    assert got["found"] and "fifteen percent (15%)" in got["text"] and got["address"] == "jason://decl/6.2(a)"
    assert got["pid"] == "decl@base/6.2(a)"
    assert list(got).index("caveat") < list(got).index("address")       # the recitation leads
    assert resolve("jason://cov/6.2(a)", shelf=shelf)["text"] == got["text"]           # the document key: an alias
    assert resolve("Covenants 6.2(a)", shelf=shelf)["address"] == "jason://decl/6.2(a)"
    assert resolve("decl#6.2(a)", shelf=shelf)["found"]
    assert resolve("CC & R's 6.2(a)", shelf=shelf)["found"]                            # the canon, any punctuation
    assert resolve("jason://rules.handbook/B-1", shelf=shelf)["found"]
    assert resolve("jason://arts/1.1", shelf=shelf)["reason"] == Reason.NO_BOOK_DOCUMENT.value


def test_versions_by_the_day_in_force_and_the_day_made_effective(world):
    shelf, _ = world
    assert "ten percent (10%)" in resolve("jason://decl:2099-02-01/6.2(a)", shelf=shelf)["text"]
    assert "ten percent (10%)" in resolve("jason://decl@base/6.2(a)", shelf=shelf)["text"]
    assert "fifteen percent" in resolve("jason://decl@2099-03-01/6.2(a)", shelf=shelf)["text"]
    miss = resolve("jason://decl@2099-03-02/6.2(a)", shelf=shelf)
    assert miss["reason"] == Reason.NO_VERSION.value and "2099-03-01" in miss["detail"]
    assert resolve("jason://rules.handbook@2099-01-01/B-1", shelf=shelf)["reason"] == Reason.NOT_KEPT_AS_AMENDED.value


def test_a_stage_version_is_cited_as_itself_and_never_in_force(world):
    shelf, _ = world
    draft = resolve("jason://decl@draft/6.2(b)", shelf=shelf)
    assert draft["found"] and "five days" in draft["text"] and draft["version"]["inForce"] is False
    assert "ten days" in resolve("jason://decl/6.2(b)", shelf=shelf)["text"]
    assert resolve("jason://decl@proposed-2099-11-01/6.2(b)", shelf=shelf)["reason"] == Reason.NO_VERSION.value


def test_a_restricted_book_is_refused_unless_asked_privately(world):
    shelf, root = world
    refused = resolve("jason://exec/2099-01-01", shelf=shelf)
    assert refused["reason"] == Reason.RESTRICTED.value and "5215" in refused["detail"]
    assert resolve("jason://members", shelf=shelf)["reason"] == Reason.RESTRICTED.value
    private = Shelf(shelf.community, root, repo=root / "no-repo", private=True)
    assert resolve("jason://exec/2099-01-01", shelf=private)["found"]
    assert resolve("jason://budget/2099", shelf=shelf)["found"]


def test_a_sections_history_follows_its_permanent_id(world):
    shelf, _ = world
    got = resolve("jason://decl/history/6.2(c)", shelf=shelf)
    assert got["kind"] == Kind.HISTORY.value and got["version"]["pid"] == "decl@2099-03-01/6.2(c)"
    rows = {r["version"]: r for r in got["outline"]}
    assert rows["@base"]["number"] is None and rows["@2099-03-01"]["present"]
    history = resolve("jason://decl/history/6.2(b)", shelf=shelf)["outline"]
    assert history[-1]["inForce"] is False and history[-1]["version"].startswith("@draft")


def test_defined_terms_are_recited_beside_the_words(world):
    shelf, _ = world
    got = resolve("jason://decl/6.3", shelf=shelf)
    term = next(t for t in got["terms"] if t["term"] == "Rules")
    assert term["address"] == "jason://decl/1.1" and "regulations the Board adopts" in term["definition"]
    assert all(t["term"] != "Rules" for t in resolve("jason://decl/1.1", shelf=shelf).get("terms", []))


def test_the_governing_documents_compare_the_documents_term_with_the_statutes(world):
    shelf, _ = world
    got = resolve("jason://gov", shelf=shelf)
    assert got["found"] and got["differences"]["onlyInTheDocuments"] == ["res"]
    assert set(got["differences"]["onlyInTheStatute"]) == {"arts", "bylaws"}
    assert got["definedAt"]["address"] == "jason://decl/1.1"


# --- Permanent ids ------------------------------------------------------------------------------------------------------

def _p(number, words, dated=None, removed=False):
    return SimpleNamespace(number=number, caption="", body=words, dated=dated, removed=removed)


BASE_V = [_p("4.15", "Leasing of units by owners is limited as this section says."),
          _p("4.16", "Signs may not be posted in any window facing a street."),
          _p("4.17", "Animals are limited to two household pets in each unit.")]
DAY = date(2099, 6, 1)
AMENDED_V = [_p("4.15", "Leasing of units by owners is limited as this section says."),
             _p("4.16", "Solar panels may be installed on a roof with the board's approval of the plan.", DAY),
             _p("4.17", "Signs may not be posted in any window facing a street."),
             _p("4.18", "Animals are limited to two household pets in each unit.")]


def test_an_amendment_that_renumbers_keeps_each_sections_id():
    table = from_versions("decl", [(None, BASE_V), (DAY, AMENDED_V)])
    signs = table.permanent_id("4.16", date(2099, 1, 1))
    assert signs == "decl@base/4.16" and table.permanent_id("4.17") == signs
    assert table.number_of(signs) == "4.17" and table.number_of(signs, date(2099, 1, 1)) == "4.16"
    solar = table.permanent_id("4.16")
    assert solar == "decl@2099-06-01/4.16" and table.number_of(solar, date(2099, 1, 1)) is None
    assert table.number_of(table.permanent_id("4.18")) == "4.18" and table.permanent_id("4.18") == "decl@base/4.17"
    assert {s.pid for s in table.renamed()} == {"decl@base/4.16", "decl@base/4.17"}


def test_a_reading_that_numbers_differently_names_an_id_and_never_makes_one():
    table = from_versions("decl", [(None, BASE_V)])
    reading = [_p("4.15", BASE_V[0].body), _p("4.15(a)", "Signs may not be posted in any window facing a street."),
               _p("4.19", "Nothing here is in the text as amended at all, word for word.")]
    unmatched = add_reading(table, "outline", reading, BASE_V)
    assert table.permanent_id("4.15(a)", reading="outline") == "decl@base/4.16"
    assert table.number_of("decl@base/4.16", reading="outline") == "4.15(a)"
    assert unmatched == ["4.19"] and table.permanent_id("4.19", reading="outline") is None
    assert len(table.ids) == 3
    inline = from_versions("decl", [(None, [_p("9.3", "The Board may grant easements (a) for utilities serving the "
                                                     "development and its owners, and (b) for any other purpose.")])])
    add_reading(inline, "outline", [_p("9.3", "The Board may grant easements"),
                                    _p("9.3(a)", "for utilities serving the development and its owners, and")],
                [_p("9.3", "The Board may grant easements (a) for utilities serving the development and its owners, "
                           "and (b) for any other purpose.")])
    assert inline.permanent_id("9.3(a)", reading="outline") == "decl@base/9.3"
    assert any(n.within for n in inline.get("decl@base/9.3").names)


def test_a_new_reading_of_the_base_carries_the_ids_and_keeps_the_old_numbers_as_names():
    before = from_versions("decl", [(None, BASE_V)], basis="original")
    reread = [_p("4.15", BASE_V[0].body), _p("4.15(a)", BASE_V[1].body), _p("4.17", BASE_V[2].body)]
    after = carry(before, from_versions("decl", [(None, reread)], basis="cli"), reading_was="original")
    signs = after.permanent_id("4.15(a)")
    assert signs == "decl@base/4.16"                                 # the id is the old one, never a new one
    assert after.number_of(signs, reading="original") == "4.16" and after.number_of(signs) == "4.15(a)"
    restored = IdTable.from_dict(json.loads(json.dumps(after.to_dict())))
    assert restored.permanent_id("4.15(a)") == signs and restored.basis == "cli"


def test_a_number_printed_twice_gets_two_ids_and_another_source_can_supply_lineages():
    table = from_versions("rules", [(None, [_p("B-2", "Birds are pets."), _p("B-2", "Residents park in garages.")])])
    assert [s.pid for s in table.ids] == ["rules@base/B-2", "rules@base/B-2~2"]
    assert table.candidates("B-2") == ["rules@base/B-2", "rules@base/B-2~2"]
    other = from_lineages("rules", [("rules@2099-01-01/B-9", date(2099, 1, 1), [Name("B-9", since=date(2099, 1, 1))])],
                          source="revision detector")
    assert other.permanent_id("B-9") == "rules@2099-01-01/B-9" and other.source == "revision detector"


def test_stale_finds_a_renumbered_section_by_its_permanent_id(world):
    shelf, _ = world
    stale = {(r.key.split(":")[0], r.target) for r in shelf.stale()}
    assert ("duty", "cov#6.4") not in stale and ("duty", "rules#B-2") not in stale
    moved = {r.target: r for r in shelf.relocated()}
    assert moved["cov#6.4"].treatment is Treatment.RELOCATED and "decl@base/6.3" in moved["cov#6.4"].note
    assert "rules.handbook@base/B-2~2" in moved["rules#B-2"].note
    treatment, note = shelf.treat(Target(Unit.SECTION, "cov", "6.4"), quote="the Board may adopt Rules for birds")
    assert treatment is Treatment.RELOCATED and "6.3" in note
    treatment, _ = shelf.treat(Target(Unit.SECTION, "cov", "6.4"), quote="cats are not allowed at all")
    assert treatment is Treatment.WORDS_CHANGED


def test_the_migration_keeps_the_number_adds_the_id_and_backs_up_first(world):
    from jason.tasks.permanent_ids import load_register, migrate

    shelf, root = world
    dry = migrate(shelf)
    assert dry["kinds"]["duty"] == {"placed": 2, "unplaced": 0} and not dry["written"]
    assert not json.loads((root / "duties" / "cov.json").read_text(encoding="utf-8"))["duties"][0].get("pid")
    done = migrate(shelf, apply=True)
    item = json.loads((root / "duties" / "cov.json").read_text(encoding="utf-8"))["duties"][0]
    assert item["section"] == "6.4" and item["pid"] == "decl@base/6.3" and item["reading"] == "outline"
    assert item["version"] == "@2099-03-01"
    assert (root / "duties" / "cov.json.pre-ids.bak").is_file() and done["written"]
    assert load_register(root) == {}                                     # the fixture has no specification rows
    fresh = Shelf(shelf.community, root, repo=root / "no-repo")
    mention = next(m for m in fresh.mentions() if m.key.startswith("duty:cov"))
    assert mention.pid == "decl@base/6.3"


def test_defined_terms_are_read_and_found_in_words():
    found = read([_p("1.7", '"Board of Directors" or "Board" shall mean the governing body of the Association.'),
                  _p("1.29", '"Record," "Recordation", and "Filed" shall mean, with respect to any document, its '
                             'recordation.'),
                  _p("1.30", "Generally, words have their ordinary meaning.")])
    assert [d.terms for d in found] == [("Board of Directors", "Board"), ("Record", "Recordation", "Filed")]
    rows = [DefinedTerm("Member", "cov", "1.2"), DefinedTerm("Member in Good Standing", "cov", "1.3")]
    assert [t.term for t in used_in("Each Member in Good Standing may vote.", rows)] == ["Member in Good Standing"]
    diff = compare_governing(GoverningSet("decl#1.1", (Book.DECL, Book.RES)), (Book.DECL, Book.BYLAWS))
    assert diff.only_profile == (Book.RES,) and diff.only_statute == (Book.BYLAWS,)


def test_an_address_and_a_version_label_agree():
    assert Address("res", item="20990101-1").format() == "jason://res/20990101-1"
    assert VersionLabel("base").base and VersionLabel("draft-undated").stage is Stage.DRAFT
