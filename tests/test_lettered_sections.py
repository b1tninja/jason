"""A section whose number ends in a letter, and a section printed in two versions under one number, through every
reader that quotes the law: the one citation grammar, the order the codes print sections in, ``authority_text``,
``jason cite``, the board packet, the context pack's law, and the MCP tools.

Every section and act here is made up ("CIV 9924f", "Stats. 2001, Ch. 1"): nothing is a real provision.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest

from jason.community import cite as grammar
from jason.community import law_text
from jason.community.authorities import LAWLIBRARY_CODES, Authority, Basis, number_key, parse_statutes, section_in
from jason.community.cite import Kind, Reason
from jason.community.context_pack import LawSection, assemble, cited_statutes, index_law_ranking, law_corpus
from jason.community.law_readings import recite
from jason.community.outlines import outline_from_text
from jason.community.passages import Passage
from jason.community.prompts import Audience, TaskKind, TaskPrompt
from jason.community.references import (ABBREVIATIONS, StatuteCitation, TargetKind, extract, statute_citation, statute_key,
                                        subdivision_reading)
from jason.tasks import board_packet
from jason.tasks.cite import Shelf, markdown, resolve
from jason.tasks.export_authorities import authority_text

UNTIL = "This section shall remain in effect only until January 1, 2099, and as of that date is repealed."
FROM = "This section shall be operative January 1, 2099."
PAGE = "authorities/CIV/CIV-9924-9924.26.md"
OTHER = "authorities/CIV/CIV-9950-9960.md"

# The publication's order: the bare number, the lettered ones, then the dotted ones. 9924f is printed twice, the
# version not yet operative first; 9924g is printed twice and its words name no day.
SECTIONS = (
    ("9924", "9924. (Added by Stats. 2001, Ch. 1, Sec. 1.)\n\n(a) The base section's first rule.\n\n(b) The base section's second rule."),
    ("9924a", "9924a. (Added by Stats. 2001, Ch. 1, Sec. 2.)\n\nThe lettered section's own words."),
    ("9924b", "9924b. (Added by Stats. 2001, Ch. 1, Sec. 3.)\n\nAnother lettered section."),
    ("9924f", f"9924f. (Amended by Stats. 2001, Ch. 2, Sec. 9.)\n\n(a) The sale is noticed thirty days ahead.\n\n(b) {FROM}"),
    ("9924f", f"9924f. (Amended by Stats. 2001, Ch. 2, Sec. 8.)\n\n(a) The sale is noticed twenty days ahead.\n\n(b) {UNTIL}"),
    ("9924g", "9924g. (Amended by Stats. 2001, Ch. 3, Sec. 1.)\n\n(a) A postponement is announced one way."),
    ("9924g", "9924g. (Amended by Stats. 2001, Ch. 3, Sec. 2.)\n\n(a) A postponement is announced another way."),
    ("9924.1", "9924.1. (Added by Stats. 2001, Ch. 1, Sec. 4.)\n\nThe first dotted section."),
    ("9924.12", "9924.12. (Added by Stats. 2001, Ch. 1, Sec. 5.)\n\nThe twelfth dotted section, which is not a lettered one."),
)
HEARING = "9955. (Added by Stats. 2001, Ch. 4, Sec. 1.)\n\n(a) The member is heard first.\n\n(b) The board decides after."


def _write(tmp_path: Path, file: str, citation: str, sections) -> dict:
    path = tmp_path / file
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"# {citation}: A made-up article\n\n- Source: California Legislature, 2025 session publication, read "
                    "with lawlibrary\n\n" + "".join(f"## CIV {n}\n\n{words}\n\n" for n, words in sections), encoding="utf-8")
    code, _, span = citation.partition(" ")
    start, _, end = span.partition("-")
    return {"file": file, "citation": citation, "title": "A made-up article", "code": code, "start": start,
            "end": end or start, "sections": [n for n, _ in sections], "basis": "duty", "why": ["made up"], "session": "2025"}


@pytest.fixture
def shelf(tmp_path: Path) -> Path:
    pages = [_write(tmp_path, PAGE, "CIV 9924-9924.26", SECTIONS), _write(tmp_path, OTHER, "CIV 9950-9960", (("9955", HEARING),))]
    (tmp_path / "authorities" / "manifest.json").write_text(json.dumps({"exported": "2026-01-02", "session": "2025",
                                                                       "pages": pages}), encoding="utf-8")
    return tmp_path


def _citing(tmp_path: Path) -> Shelf:
    community = SimpleNamespace(living_documents=lambda: (), citable_documents=lambda: (), conflicts=lambda: (),
                                notice_provisions=lambda: ())
    return Shelf(community, tmp_path, repo=tmp_path / "no-repo")


def _digest(n: int) -> str:
    return law_text.words_digest(SECTIONS[n][1])


# --- The grammar ---------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("written, base, subdivisions", [
    ("CIV 9924a", "CIV 9924a", ""),                          # a lettered section: the letter is part of the number
    ("civ-9924f", "CIV 9924f", ""),
    ("CIV 9924F", "CIV 9924f", ""),
    ("Civil Code section 9924f", "CIV 9924f", ""),
    ("Civ. Code, § 9924.12", "CIV 9924.12", ""),             # a dotted section is not a lettered one
    ("CIV 9955(a)", "CIV 9955", "(a)"),                      # a letter in parentheses is a subdivision
    ("CIV 9955 (a)(1)", "CIV 9955", "(a)(1)"),
    ("CIV 9924f(a)", "CIV 9924f", "(a)"),                    # both: section 9924f, subdivision (a)
    ("SHC 9898.16", "SHC 9898.16", ""),
    ("10 CCR 9792.23", "10 CCR 9792.23", ""),
    ("10-CCR-9792.23", "10 CCR 9792.23", ""),
])
def test_one_grammar_reads_a_lettered_section_and_a_subdivision_apart(written, base, subdivisions):
    found = statute_citation(written)
    assert (found.base, found.subdivisions) == (base, subdivisions)
    assert law_text.normal_citation(written) == (base, subdivisions)             # the shelf's reader is the same grammar
    assert statute_key(base + subdivisions) == (base, subdivisions)


def test_what_is_not_a_citation_is_a_miss_and_the_codes_are_the_librarys():
    assert all(statute_citation(text) is None for text in ("", "9955", "Section 9955", "bylaws#7.2", "CIV 9955 and more"))
    assert ABBREVIATIONS == LAWLIBRARY_CODES and grammar.ABBREVIATIONS is ABBREVIATIONS
    assert statute_citation("CIV 9924f").letter == "f" and statute_citation("CIV 9924.12").letter == ""


def test_free_text_keeps_the_letter_and_never_reads_a_lettered_section_as_its_base():
    text = ("The trustee acts under Civil Code section 9924f and Civ. Code, § 9924.12. See Civil Code sections 9924a, 9924b, "
            "and Section 9955(a) of the Civil Code. Section 9924g of the Civil Code applies, as do CIV 9924f(a) and "
            "SHC 9898.16. Civil Code section 9955 and the rest follow.")
    found = [r.target for r in extract(outline_from_text(text, key="made-up"), {}) if r.kind is TargetKind.STATUTE]
    assert found == ["CIV 9924f", "CIV 9924.12", "CIV 9924a", "CIV 9924b", "CIV 9955(a)", "CIV 9924g", "CIV 9924f(a)",
                     "SHC 9898.16", "CIV 9955"]
    assert "CIV 9924" not in found                                  # 9924f is not section 9924
    assert cited_statutes([text])[0][:4] == ["CIV 9924f", "CIV 9924.12", "CIV 9924a", "CIV 9924b"]
    # A document's own short section number reads as it always has.
    own = [r.target for r in extract(outline_from_text("See Section 3a and Section 4.15(a) of these Rules.", key="rules"), {})]
    assert "rules#3a" not in own


def test_a_letters_link_goes_to_the_lettered_section():
    from jason.community.links import link_citations

    linked = link_citations("See Civil Code 9924f(a) and Civil Code 9955(a).")
    assert 'sectionNum=9924f."' in linked and ">Civil Code 9924f(a)</a>" in linked
    assert 'sectionNum=9955."' in linked and ">Civil Code 9955(a)</a>" in linked


@pytest.mark.parametrize("expression, target, base, labels", [
    ("CIV 9924f", "CIV 9924f", "CIV 9924f", ()),
    ("Civil Code section 9924f", "CIV 9924f", "CIV 9924f", ()),
    ("Section 9924f of the Civil Code", "CIV 9924f", "CIV 9924f", ()),
    ("CIV 9924F", "CIV 9924f", "CIV 9924f", ()),
    ("CIV 9924f(a)(1)", "CIV 9924f(a)(1)", "CIV 9924f", ("a", "1")),
    ("CIV 9955(a)", "CIV 9955(a)", "CIV 9955", ("a",)),          # section 9955, subdivision (a): not a lettered section
    ("CIV 9955(A)", "CIV 9955(A)", "CIV 9955", ("A",)),          # a subdivision's label keeps its case
    ("CIV 9924f@2101-06-01", "CIV 9924f@2101-06-01", "CIV 9924f", ()),
    ("CIV 9924-9924.26", "CIV 9924-9924.26", "CIV 9924", ()),
    ("CIV 9924a-9924p", "CIV 9924a-9924p", "CIV 9924a", ()),
    ("CIV 9924a, 9924b", "CIV 9924a,9924b", "CIV 9924a", ()),
    ("SHC 9898.16", "SHC 9898.16", "SHC 9898.16", ()),           # every code the library holds, not a chosen few
])
def test_jason_cite_parses_a_lettered_section(expression, target, base, labels):
    found = grammar.parse(expression, {})
    assert (found.id, found.base, found.labels) == (target, base, labels)


# --- The order, and a page's span -------------------------------------------------------------------------------------------

def test_number_key_sorts_as_the_publication_prints():
    printed = ["9924", "9924a", "9924b", "9924f", "9924g", "9924p", "9924.1", "9924.9", "9924.10", "9924.12", "9925"]
    assert sorted(reversed(printed), key=number_key) == printed
    assert number_key("9924a") < number_key("9924.1") and number_key("9924") < number_key("9924a")
    assert number_key("9102.6") < number_key("9102.6a") < number_key("9102.7")
    assert number_key("not a number") == (-1.0,) and number_key("9924.") == (-1.0,)
    page = Authority("CIV", "9924", "9924.26", "", Basis.PROCESS)
    assert all(section_in(page, n) for n in ("9924", "9924a", "9924p", "9924.12")) and not section_in(page, "9925")
    assert not section_in(Authority("CIV", "9955", "9955", "", Basis.DUTY), "9955a")     # one section is not its lettered neighbor
    # A duty's citation string keeps a lettered section and a lettered span.
    assert [(a.start, a.end) for a in parse_statutes("CIV 9924, 9924a to 9924p, 9924.1", "made up", Basis.DUTY)] == [
        ("9924", "9924"), ("9924a", "9924p"), ("9924.1", "9924.1")]


def test_a_span_of_the_law_covers_its_lettered_sections(shelf: Path):
    citing = _citing(shelf)
    for span in ("CIV 9924-9924.26", "CIV 9924a-9924p", "CIV 9924f-9924.1"):
        got = citing(span)
        assert got.kind is Kind.OUTLINE and [n["file"] for n in got.outline] == [PAGE]
    assert law_text.shelf_numbers(shelf)["CIV"] >= {"9924", "9924a", "9924f", "9924.12", "9955"}


# --- Reading a lettered section; the shelf's own list decides ---------------------------------------------------------------

def test_authority_text_quotes_a_lettered_section(shelf: Path):
    hit = authority_text(shelf, "CIV 9924a")
    assert hit["found"] and hit["citation"] == "CIV 9924a" and hit["page"] == PAGE
    assert hit["text"].endswith("The lettered section's own words.") and "version" not in hit
    assert authority_text(shelf, "Civil Code section 9924a")["text"] == hit["text"]
    assert "base section's first rule" in authority_text(shelf, "CIV 9924")["text"]              # nothing else moved
    assert "twelfth dotted section" in authority_text(shelf, "Civ. Code, § 9924.12")["text"]
    assert authority_text(shelf, "CIV 9924(a)") == {"found": False, "citation": "CIV 9924(a)",
                                                    "reason": "say a code and a section, such as CIV 5200"}


def test_the_shelfs_section_list_says_whether_a_lettered_number_is_a_section(shelf: Path):
    listed = law_text.shelf_numbers(shelf)["CIV"]
    # "9924a" is listed: it is that section, and nothing else is offered.
    assert subdivision_reading(statute_citation("CIV 9924a"), listed) is None
    # "9955a" is not listed and 9955 is: the text is ambiguous, and the subdivision it may mean is offered, not quoted.
    assert subdivision_reading(statute_citation("CIV 9955a"), listed) == StatuteCitation("CIV", "9955", "(a)")
    assert subdivision_reading(statute_citation("CIV 9000a"), listed) is None
    miss = authority_text(shelf, "CIV 9955a")
    assert not miss["found"] and miss["suggest"] == "CIV 9955(a)" and "text" not in miss
    assert "CIV 9955a is not a section on the shelf" in miss["reason"] and "write CIV 9955(a)" in miss["reason"]
    citing = _citing(shelf)
    asked = resolve("CIV 9955a", shelf=citing)
    assert not asked["found"] and asked["reason"] == Reason.STATUTE_NOT_ON_DISK.value and asked["suggest"] == "CIV 9955(a)"
    assert "text" not in asked                                      # one section's words are never quoted under another's number
    # Written with the parentheses, each is what it says: a subdivision of 9955, a subdivision of 9924, the section 9924a.
    assert citing("CIV 9955(a)").text == "(a) The member is heard first."
    assert citing("CIV 9924(a)").text == "(a) The base section's first rule."
    assert citing("CIV 9924a").text.endswith("The lettered section's own words.")
    assert citing("Section 9924a of the Civil Code").version["official"]


# --- Two versions under one number --------------------------------------------------------------------------------------------

def test_every_reader_says_which_version_it_quotes_and_why(shelf: Path):
    today = date.today().isoformat()
    first, second = law_text.versions("CIV 9924f", shelf)
    assert (first.digest, second.digest) == (_digest(3), _digest(4))
    which = law_text.quoted("CIV 9924f", shelf)
    assert which.text.digest == second.digest and which.decided is law_text.Decided.OWN_WORDS and not which.undecided
    assert which.quotes == (UNTIL, FROM)
    assert which.note.startswith(f"CIV 9924f is printed in 2 versions under the one number. Version 2 in the publication's "
                                 f"order (digest {second.digest[:12]}) is the one in force on {today}")
    assert f"its own words: \"{UNTIL}\"" in which.note
    assert f"Version 1 (digest {first.digest[:12]}): it came into force on 2099-01-01, after {today}: \"{FROM}\"" in which.note
    assert which.label(first.digest).startswith(f"version 1 of 2 the publication prints under CIV 9924f (digest "
                                                f"{first.digest[:12]}); not in force on {today}: it came into force on 2099-01-01")
    assert f"; the one in force on {today}: " in which.label(second.digest)

    hit = authority_text(shelf, "CIV 9924f")
    assert "twenty days" in hit["text"] and "thirty days" not in hit["text"]         # the one in force, not the first printed
    assert hit["version"] == which.note and hit["digest"] == second.digest and hit["decided"] == "own_words"
    assert hit["quotes"] == [UNTIL, FROM] and "undecided" not in hit
    assert [(v["digest"], v["quoted"]) for v in hit["versions"]] == [(first.digest, False), (second.digest, True)]

    citing = _citing(shelf)
    cited = citing("CIV 9924f")
    assert "twenty days" in cited.text and cited.version["note"] == which.note and cited.version["decidingWords"] == [UNTIL, FROM]
    assert cited.version["digest"] == second.digest and which.note in markdown(cited)
    part = citing("CIV 9924f(a)")
    assert part.text == "(a) The sale is noticed twenty days ahead." and which.note in part.version["note"]
    assert "split by jason" in part.version["note"]

    # The as-of form goes through law_text.in_force: after the day the versions' own words name, the other version.
    later = citing("CIV 9924f@2101-06-01")
    assert later.found and "thirty days" in later.text and later.version["decided"] == "own_words"
    assert later.version["digest"] == first.digest and later.version["decidingWords"] == [FROM, UNTIL]
    assert f"own words that decide it: \"{FROM}\"" in later.version["note"]
    assert f"(digest {second.digest[:12]}) ceased on 2099-01-01" in later.version["note"]
    assert resolve("CIV 9924f", as_of="2101-06-01", shelf=citing)["version"]["digest"] == first.digest

    excerpt = board_packet.statute_excerpt(shelf, "CIV 9924f", "(a)")
    assert excerpt.startswith("(a) The sale is noticed twenty days ahead.") and excerpt.endswith(f"[jason: {which.note}]")
    assert board_packet.citations("CIV 9924f(a), (b); 9924g; SHC 9898.16; 10 CCR 9792.23") == [
        ("CIV 9924f", "(a)(b)"), ("CIV 9924g", ""), ("SHC 9898.16", ""), ("10 CCR 9792.23", "")]

    from jason.mcp.county import authorities
    from jason.mcp.governance import cite_document

    assert authorities("CIV 9924f", data_dir=shelf)["version"] == which.note
    assert cite_document("CIV 9924f", data_dir=shelf)["version"]["note"] == which.note
    assert cite_document("CIV 9924a", data_dir=shelf)["found"]

    # A recital with no day still gives both, and now says which is in force today.
    assert which.note in recite("CIV 9924f", shelf, ()).caveats


def test_where_the_words_do_not_decide_every_version_is_shown(shelf: Path):
    first, second = law_text.versions("CIV 9924g", shelf)
    which = law_text.quoted("CIV 9924g", shelf)
    assert which.undecided and which.text is None and which.decided is law_text.Decided.NOT_SHOWN
    assert "the disk does not show which is in force on" in which.note and "Every version is quoted" in which.note

    hit = authority_text(shelf, "CIV 9924g")
    assert hit["found"] and hit["undecided"] and "digest" not in hit and hit["version"] == which.note
    assert "announced one way" in hit["text"] and "announced another way" in hit["text"]            # never the first alone
    assert hit["text"].startswith(f"[jason: version 1 of 2 the publication prints under CIV 9924g (digest {first.digest[:12]}); "
                                  "the disk does not show which version is in force on")
    assert f"[jason: version 2 of 2 the publication prints under CIV 9924g (digest {second.digest[:12]})" in hit["text"]
    assert [(v["digest"], v["quoted"]) for v in hit["versions"]] == [(first.digest, True), (second.digest, True)]

    citing = _citing(shelf)
    whole = citing("CIV 9924g")
    assert whole.text == hit["text"] and whole.version["undecided"] and whole.version["note"] == which.note
    part = citing("CIV 9924g(a)")
    assert part.text.count("[jason: version") == 2
    assert "(a) A postponement is announced one way." in part.text and "(a) A postponement is announced another way." in part.text
    excerpt = board_packet.statute_excerpt(shelf, "CIV 9924g", "(a)")
    assert "announced one way" in excerpt and "announced another way" in excerpt and excerpt.count("[jason: version") == 2
    # A section printed once carries no note at all.
    assert board_packet.statute_excerpt(shelf, "CIV 9955", "(b)") == "(b) The board decides after."


# --- The context pack's law --------------------------------------------------------------------------------------------------

class _Community:
    def prompt_context(self):
        return ["Example Commons, 12 units"]

    def classify_document(self, name, folder=None):
        return None


def test_the_packs_law_keeps_each_lettered_section_and_each_version(shelf: Path, monkeypatch):
    today = date.today().isoformat()
    corpus = law_corpus(shelf)
    assert [s.citation for s in corpus] == [f"CIV {n}" for n, _ in SECTIONS] + ["CIV 9955"]      # none dropped, none merged
    by = {(s.citation, law_text.words_digest(s.text)): s for s in corpus}
    assert len(by) == len(corpus)
    lettered, once = by[("CIV 9924a", _digest(1))], by[("CIV 9955", law_text.words_digest(HEARING))]
    assert lettered.text.endswith("The lettered section's own words.") and lettered.version == "" and once.version == ""
    later, sooner = by[("CIV 9924f", _digest(3))], by[("CIV 9924f", _digest(4))]
    assert f"not in force on {today}" in later.version and FROM in later.version
    assert f"the one in force on {today}" in sooner.version and UNTIL in sooner.version
    assert all("the disk does not show which version is in force" in by[("CIV 9924g", _digest(n))].version for n in (5, 6))

    # A page a reader's miss brought down is the law on hand too.
    manifest = shelf / "authorities" / "manifest.json"
    data = json.loads(manifest.read_text(encoding="utf-8"))
    data["on_demand"] = [_write(shelf, "authorities/CIV/CIV-9970.md", "CIV 9970", (("9970", "9970. A section fetched on demand."),))]
    manifest.write_text(json.dumps(data), encoding="utf-8")
    assert law_corpus(shelf)[-1].citation == "CIV 9970"

    # A source that cites the section brings both versions, each saying which it is; one version alone never stands in.
    task = TaskPrompt(TaskKind.RULE_REMINDER, "A reminder of a rule.", Audience.OWNER, topics=("the first dotted section",))
    pack = assemble(_Community(), task, shelf, draft="The sale is noticed under Civil Code section 9924f.", law=corpus,
                    search=lambda *a, **k: (), files=lambda kind: [], fact_runner=lambda tool, args: {}, use_index=False)
    versions = [s for s in pack.sources if s.id.startswith("S") and s.title == "CIV 9924f"]
    assert sorted(("thirty days" in s.text, "twenty days" in s.text) for s in versions) == [(False, True), (True, False)]
    assert all("the publication prints under CIV 9924f" in s.note for s in versions)
    assert not any("CIV 9924f" in gap for gap in pack.gaps)

    # A passage the index returns under the shared heading is read as the version it starts in, not the first.
    from jason.community import passage_index

    path = shelf / PAGE
    hits = [SimpleNamespace(hit=SimpleNamespace(passage=Passage(path, n, s.start_word + 2, s.text, heading="A made-up article > CIV 9924f")))
            for n, s in enumerate((sooner, later))]
    monkeypatch.setattr(passage_index, "search", lambda *a, **k: hits)
    ranked = index_law_ranking(corpus, shelf, mode="keyword")("the sale", 4)
    assert [corpus[i] for i in ranked] == [sooner, later]


def test_a_made_up_law_list_with_two_versions_is_not_merged(tmp_path: Path):
    chapter = "CIV 9924-9924.26: A made-up article"
    law = [LawSection("CIV 9924f", chapter, "(a) Thirty days.", version="version 1 of 2; not in force today"),
           LawSection("CIV 9924f", chapter, "(a) Twenty days.", version="version 2 of 2; the one in force today")]
    task = TaskPrompt(TaskKind.RULE_REMINDER, "A reminder of a rule.", Audience.OWNER, topics=("notice of the sale",))
    pack = assemble(_Community(), task, tmp_path, draft="See CIV 9924f.", law=law, search=lambda *a, **k: (),
                    files=lambda kind: [], fact_runner=lambda tool, args: {}, use_index=False)
    assert sorted(s.text for s in pack.sources if s.title == "CIV 9924f") == ["(a) Thirty days.", "(a) Twenty days."]