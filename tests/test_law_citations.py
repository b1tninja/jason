"""A document's statute citations resolved to the law in force on a day: a former number through the successor table,
both recited; one the table does not place left open (``jason.community.law_citations``), in the as-of pack and on a
collection's summary page.

Every section, act, renumbering, document, and case here is made up: a made-up code's sections 9800 to 9810 moved to
9900 to 9910 by "Stats. 2093, Ch. 1", operative 2094-01-01. Nothing is fetched.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from jason.community import law_citations as lc
from jason.community import law_text
from jason.community import passage_index as pi
from jason.community.context_pack import LawSection, assemble
from jason.community.document_collections import Collection, collection, collections
from jason.community.law_citations import Resolution
from jason.community.legal_cases import CaseRole, CaseStatus, Forum, LegalCase
from jason.community.prompts import Audience, FactSource, TaskKind, TaskPrompt
from jason.community.symbols import DocumentKind
from jason.tasks import collection_pages as cp
from jason.tasks.case_files import catalog_name, index_sources

NOTICE = ("9901. (Added by Stats. 2093, Ch. 1, Sec. 2.)\n\n(a) A notice of the hearing shall be given in writing.\n\n"
          "(b) The notice is given fifteen days before the hearing.")
FINE = "9903. (Added by Stats. 2093, Ch. 1, Sec. 4.)\n\n(a) A fine is imposed only after the hearing."
FORMER_NOTICE = ("9803. (Added by Stats. 2080, Ch. 2, Sec. 1.)\n\n(f) A fine is imposed only after a hearing.\n\n"
                 "(g) A notice of the hearing is given fourteen days before it.")
PAGE = "authorities/CIV/CIV-9900-9910.md"
OPERATIVE = "2094-01-01"
KEY = "example-26cv000009"
CASE = LegalCase(KEY, "Example v. Example Commons", Forum.SUPERIOR_COURT, CaseRole.DEFENDANT, CaseStatus.PENDING,
                 case_number="26CV000009", drive_folder="26CV000009 - Example")
OLD_LETTER = ("Date: March 1, 2092\n\nThe board gives notice under Civil Code Section 9803(g) and Section 9805 of the "
              "Civil Code that a hearing will be held.\n")
NEW_LETTER = "Date: March 1, 2096\n\nThe fine was imposed under Civil Code Section 9903(a), as the notice said.\n"
TASK = TaskPrompt(TaskKind.HEARING_NOTICE, "A notice of a hearing.", Audience.BOARD, topics=("the notice of the hearing",),
                  documents=(DocumentKind.DECLARATION,), facts=(FactSource("open_items", why="what is open"),),
                  considerations=("Does it say when?",))


def _row(former: str, part: str, targets: list[str], source: str = "disposition_table", succession: str = "continued") -> dict:
    return {"former": {"citation": f"CIV {former}{part}", "section": former, "part": part},
            "targets": [{"citation": t} for t in targets], "succession": succession, "source": source,
            "act": "davis-stirling", "report": {"title": "A made-up disposition table", "url": "http://example.invalid/x.pdf"}}


def _recodification() -> dict:
    return {"act": "davis-stirling", "title": "A made-up act", "former": ["9800", "9810"], "current": ["9900", "9910"],
            "statute": "Stats. 2093, Ch. 1", "bill": "AB 1", "operative": OPERATIVE, "repeals_former": True,
            "source": "http://example.invalid/"}


@pytest.fixture()
def data(tmp_path: Path) -> Path:
    (tmp_path / "authorities" / "CIV").mkdir(parents=True)
    (tmp_path / PAGE).write_text("# Made-up hearings\n\n- Source: A made-up Legislature, 2097 session publication\n\n"
                                 f"## CIV 9901\n\n{NOTICE}\n\n## CIV 9903\n\n{FINE}\n", encoding="utf-8")
    (tmp_path / "authorities" / "manifest.json").write_text(json.dumps({"exported": "2095-01-01", "pages": [{
        "file": PAGE, "citation": "CIV 9900-9910", "title": "Made-up hearings", "code": "CIV", "start": "9900",
        "end": "9910", "sections": ["9901", "9903"], "basis": "duty", "why": [], "session": "2097"}]}), encoding="utf-8")
    history = tmp_path / "authorities" / "history"
    history.mkdir()
    (history / "former-sections.json").write_text(json.dumps({"exported": "2099-01-02", "act": "davis-stirling", "sections": [
        {"citation": "CIV 9803", "code": "CIV", "section": "9803", "recodifications": [_recodification()],
         "rows": [_row("9803", "(f)", ["CIV 9903(a)"]), _row("9803", "(g)", ["CIV 9901"]),
                  _row("9803", "(g)", ["CIV 9901"], source="commission_comment", succession="continued_with_changes")]},
        {"citation": "CIV 9805", "code": "CIV", "section": "9805", "recodifications": [_recodification()],
         "rows": [_row("9805", "", [], succession="omitted")]}]}), encoding="utf-8")
    return tmp_path


def _former_words(data: Path) -> str:
    """The former section's own words, added by hand with their range, as a person may add them."""
    folder = data / "authorities" / "history" / "CIV-9803"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "from-the-statutes.md").write_text(
        "# CIV 9803: a former section\n\n- Source: Statutes of 2080, chapter 2 (a made-up volume)\n- Act: Stats. 2080, Ch. 2\n"
        f"- From: 2081-01-01\n- Until: {OPERATIVE}\n- Added by hand: A. Person, 2099-02-03\n\n## CIV 9803\n\n{FORMER_NOTICE}\n",
        encoding="utf-8")
    return law_text.words_digest(FORMER_NOTICE)


# --- the resolver -------------------------------------------------------------------------------------------------------

def test_the_renumbering_is_read_from_the_table_on_disk(data):
    (act,) = lc.recodifications(data)
    assert (act.act, act.code, act.former, act.current, act.operative, act.repeals_former) == (
        "davis-stirling", "CIV", ("9800", "9810"), ("9900", "9910"), OPERATIVE, True)
    assert act.describe() == "renumbered to CIV 9900 to 9910 by Stats. 2093, Ch. 1 (AB 1), operative 2094-01-01"
    assert lc.renumbered(data, "CIV", "9803") == act and lc.renumbered(data, "CIV", "9901") is None
    assert lc.renumbered(data, "CCP", "9803") is None and lc.recodifications(data / "nowhere") == ()
    cited = lc.cited_in(OLD_LETTER + NEW_LETTER)
    assert [(c.citation, c.base, c.subdivisions, c.prior) for c in cited] == [
        ("CIV 9803(g)", "CIV 9803", "(g)", False), ("CIV 9805", "CIV 9805", "", False), ("CIV 9903(a)", "CIV 9903", "(a)", False)]
    assert cited[0].quote.startswith("The board gives notice under Civil Code Section 9803(g)")
    assert [c.citation for c in lc.former_in([OLD_LETTER, NEW_LETTER], data)] == ["CIV 9803(g)", "CIV 9805"]


def test_a_former_number_is_read_through_the_table_and_both_are_recited_where_held(data):
    day = date(2096, 1, 1)
    found = lc.resolve(data, "Civil Code Section 9803(g)", day)
    assert found.resolution is Resolution.FORMER and not found.open and found.cited == "CIV 9803(g)"
    assert found.successors == ("CIV 9901",) and found.successor_bases == ("CIV 9901",)
    assert found.source == "commission comment and disposition table" and found.succession == "continued, continued with changes"
    assert found.note == ("cites former CIV 9803(g), now CIV 9901 (commission comment and disposition table: continued, continued "
                          "with changes; renumbered to CIV 9900 to 9910 by Stats. 2093, Ch. 1 (AB 1), operative 2094-01-01); "
                          "its own words not held; CIV 9901 recited")
    (now,) = found.words
    assert now.found and now.citation == "CIV 9901" and "fifteen days" in now.words and now.decided == "current"
    assert found.former is not None and not found.former.found
    lines = found.lines()
    assert lines[0] == f"- {found.note}"
    assert any(line.startswith("- Former CIV 9803, its own words as last in force (to 2093-12-31): not held (") for line in lines)
    assert any(line.startswith("- Now CIV 9901: digest ") and "in force on 2096-01-01" in line for line in lines)
    assert "  > (b) The notice is given fifteen days before the hearing." in lines
    # With the former section's own words in the history, both are recited.
    digest = _former_words(data)
    both = lc.resolve(data, "CIV 9803(g)", day)
    assert both.former.found and both.former.digest == digest and both.former.decided == "prior"
    assert both.former_day == date(2093, 12, 31) and lc.last_day(both.renumbered) == date(2093, 12, 31)
    assert both.note.endswith("its own words recited from the history as last in force (to 2093-12-31); CIV 9901 recited")
    assert "  > (g) A notice of the hearing is given fourteen days before it." in both.lines()
    assert any("in force on 2093-12-31: from 2081-01-01 until 2094-01-01" in line for line in both.lines())
    told = both.as_dict()
    assert told["resolution"] == "former" and told["former"]["digest"] == digest and told["words"][0]["citation"] == "CIV 9901"
    assert told["formerAsOf"] == "2093-12-31"
    # A subdivision the table maps to a subdivision of the successor keeps the table's own target.
    fine = lc.resolve(data, "CIV 9803(f)", day)
    assert fine.successors == ("CIV 9903(a)",) and fine.successor_bases == ("CIV 9903",) and fine.words[0].citation == "CIV 9903"
    # The whole former section: every row's target.
    whole = lc.resolve(data, "CIV 9803", day)
    assert whole.successors == ("CIV 9903(a)", "CIV 9901") and whole.successor_bases == ("CIV 9903", "CIV 9901")


def test_a_citation_the_table_does_not_place_stays_open_and_a_day_before_the_renumbering_reads_the_number_then_in_force(data):
    day = date(2096, 1, 1)
    omitted = lc.resolve(data, "CIV 9805", day)
    assert omitted.resolution is Resolution.UNRESOLVED and omitted.open and omitted.successors == ()
    assert omitted.note == "cites former CIV 9805; the table says omitted: an open finding, and no successor is guessed"
    assert omitted.lines() == [f"- {omitted.note}"] and omitted.as_dict()["open"]
    nowhere = lc.resolve(data, "CIV 9807", day)
    assert nowhere.open and "places nothing under that number" in nowhere.note
    # The grammar's own reading of a former number, with no table on disk: open, with the command that exports one.
    bare = lc.resolve(data / "nowhere", "CIV 1363(g)", day, prior=True)
    assert bare.open and "jason law-history --export" in bare.note
    # Before the renumbering the cited number was the section in force; its words of that day are held or not.
    then = lc.resolve(data, "CIV 9803(g)", date(2092, 3, 1))
    assert then.resolution is Resolution.THEN_CURRENT and not then.open and then.successors == ()
    assert then.note.startswith("cites CIV 9803(g), the number in force on 2092-03-01 (renumbered to CIV 9900 to 9910")
    assert then.note.endswith("its words of that day are not held: a person adds them from an official source (jason law-history --add-version)")
    _former_words(data)
    held = lc.resolve(data, "CIV 9803(g)", date(2092, 3, 1))
    assert held.words[0].found and held.words[0].decided == "prior" and "not held" not in held.note
    assert any(line.startswith("- CIV 9803, the words then in force: digest ") for line in held.lines())
    # A current number is the section as of the day, or not on the shelf; without a day, the shelf now.
    current = lc.resolve(data, "CIV 9903(a)", day)
    assert current.resolution is Resolution.CURRENT and current.note == f"cites CIV 9903(a): on the shelf (digest {current.words[0].digest[:12]}), in force on 2096-01-01"
    assert current.lines() == [f"- {current.note}", f"- CIV 9903: digest {current.words[0].digest[:12]}; source: A made-up Legislature, 2097 session publication; in force on 2096-01-01: {current.words[0].basis}"]
    assert lc.resolve(data, "CIV 9903", None).note.endswith(")") and lc.resolve(data, "CIV 9909", day).resolution is Resolution.NOT_HELD
    assert lc.resolve(data, "the hearing rule", day).open


def test_the_records_lens_finding_says_now_y_or_open_never_a_missing_section():
    from jason.community.models.legal_shared import former_sections_finding

    (found,) = former_sections_finding(("1363(g)", "1350.7", "1370"),
                                       ["1363(g) is now CIV 5855 (disposition table)", "1350.7 was not continued (omitted)"])
    assert found.code == "cites-former-sections"
    assert found.message == ("cites former Civil Code 1363(g), now CIV 5855 (disposition table); former Civil Code 1350.7, was "
                             "not continued (omitted): open; former Civil Code 1370, not placed by the law history on disk "
                             "(jason law-history --export): open (the Davis-Stirling Act was renumbered to Civil Code 4000 to "
                             "6150 by Stats. 2012, Ch. 180, operative January 1, 2014)")
    assert "missing" not in found.message and former_sections_finding(()) == []


# --- the as-of pack -----------------------------------------------------------------------------------------------------

class Community:
    def __init__(self, cases=()):
        self.cases = cases

    def prompt_context(self):
        return ["Example Commons, 12 units"]

    def classify_document(self, name, folder=None):
        return DocumentKind.DECLARATION if name.startswith("Covenants") else None

    def living_documents(self):
        return ()

    def citable_documents(self):
        return ()

    def law_readings(self):
        return ()

    def legal_cases(self):
        return self.cases


COVENANTS = ("ARTICLE 6\n6.2 Hearings.\n(a) Notice. The Board gives notice of the hearing as Civil Code Section 9803(g) "
             "provides, and a fine follows Section 9805 of the Civil Code.\n")


def _law() -> list[LawSection]:
    return [LawSection("CIV 9901", "CIV 9900-9910: Made-up hearings", NOTICE, PAGE),
            LawSection("CIV 9903", "CIV 9900-9910: Made-up hearings", FINE, PAGE)]


def _search(query, *folders, k, data_dir, mode):
    from jason.community.passages import Passage

    class Hit:
        def __init__(self, passage):
            self.score, self.passage = 1.0, passage

    return [Hit(Passage(Path(data_dir) / "governing" / "Covenants.md", 0, 0, COVENANTS, heading="Covenants > 6.2 Hearings."))]


def _pack(data: Path, community=None, **kw):
    (data / "governing").mkdir(exist_ok=True)
    (data / "governing" / "Covenants.md").write_text(COVENANTS, encoding="utf-8")
    kw.setdefault("use_index", False)
    return assemble(community or Community(), TASK, data, mode="keyword", law=_law(), search=_search,
                    files=lambda kind: [], fact_runner=lambda tool, args: {"tool": tool, "open": 2}, **kw)


def test_without_a_day_the_pack_is_what_it_was_and_with_one_a_former_number_brings_its_successor_in(data):
    plain = _pack(data)
    assert {s.title for s in plain.sources if s.id.startswith("S")} <= {"CIV 9901", "CIV 9903"}
    assert not any(s.title == "CIV 9803" for s in plain.sources)
    # Without a day the pack reads citations as it did: by the grammar alone, which knows the Act's own former range
    # and not a made-up table, so a made-up former number is a section not on hand. The table is read as of a day.
    assert "CIV 9803 is cited by a source but is not in the law on hand" in plain.gaps
    assert "CIV 9805 is cited by a source but is not in the law on hand" in plain.gaps
    day = date(2096, 1, 1)
    pack = _pack(data, as_of=day)
    law = {s.title: s for s in pack.sources if s.id.startswith("S")}
    assert "CIV 9803" not in law and law["CIV 9901"].provision.shown and law["CIV 9901"].provision.decided == "current"
    assert "cites former CIV 9803(g), now CIV 9901 (commission comment and disposition table" in law["CIV 9901"].note
    assert "in force on 2096-01-01" in law["CIV 9901"].note
    assert not any("former Davis-Stirling number" in g for g in pack.gaps)
    assert any(g.startswith("CIV 9803(g) is cited; the former section's own words are not held") for g in pack.gaps)
    assert "cites former CIV 9805; the table says omitted: an open finding, and no successor is guessed" in pack.gaps
    # With the former words held, both are recited: the successor in force that day, and the former section from the history.
    _former_words(data)
    both = _pack(data, as_of=day)
    law = {s.title: s for s in both.sources if s.id.startswith("S")}
    assert {"CIV 9901", "CIV 9803"} <= set(law) and [s.id for s in both.sources if s.id.startswith("S")] == [f"S{n}" for n in range(1, len(law) + 1)]
    former = law["CIV 9803"]
    assert "fourteen days" in former.text and former.provision.decided == "prior" and former.provision.shown
    assert "cited as CIV 9803(g): the former section's own words as last in force (to 2093-12-31); now CIV 9901" in former.note
    assert any(a.startswith("In force on 2093-12-31: from 2081-01-01 until 2094-01-01") for a in former.provision.above)
    assert former.provision.as_of == date(2093, 12, 31) and law["CIV 9901"].provision.as_of == day
    page = both.markdown()
    assert page.index("fourteen days before it") > page.index("fifteen days before the hearing")
    # Before the renumbering the cited number is the one in force: its words come in under their own number.
    then = _pack(data, as_of=date(2092, 3, 1))
    law = {s.title: s for s in then.sources if s.id.startswith("S")}
    assert "CIV 9803" in law and "cites CIV 9803(g), the number in force on 2092-03-01" in law["CIV 9803"].note
    assert any(g.startswith("cites CIV 9805, the number in force on 2092-03-01") and "not held" in g for g in then.gaps)


def test_a_collection_s_documents_bring_their_cited_sections_into_the_as_of_pack(data):
    files = data / "cases" / KEY / "files"
    files.mkdir(parents=True)
    (files / "Old letter.txt").write_text(OLD_LETTER, encoding="utf-8")
    (files / "New letter.txt").write_text(NEW_LETTER, encoding="utf-8")
    (data / "cases" / KEY / "manifest.json").write_text(json.dumps({"case": KEY, "files": [
        {"id": "1", "name": "Old letter.txt", "path": "Old letter.txt", "mimeType": "text/plain", "md5": "", "modified": "",
         "heldBack": False, "action": "download", "local": "Old letter.txt"},
        {"id": "2", "name": "New letter.txt", "path": "New letter.txt", "mimeType": "text/plain", "md5": "", "modified": "",
         "heldBack": False, "action": "download", "local": "New letter.txt"}], "extracts": {}}), encoding="utf-8")
    community = Community((CASE,))
    pi.build(data, sources=index_sources((CASE,)), kind_of=lambda name: "")
    found = collection(community, KEY)
    _former_words(data)
    pack = _pack(data, community, as_of=date(2096, 1, 1), collection=found, use_index=True)
    assert pack.collection_included and [s.id for s in pack.sources if s.id.startswith("C")]
    law = [s for s in pack.sources if s.id.startswith("S")]
    assert {s.title for s in law} == {"CIV 9901", "CIV 9803", "CIV 9903"} and [s.id for s in law] == ["S1", "S2", "S3"]
    assert law[-1].title in ("CIV 9803", "CIV 9903")
    fine = next(s for s in law if s.title == "CIV 9903")
    assert "in force on 2096-01-01" in fine.note and fine.provision.shown
    # The law sources sit together, before the governing and collection sources, whatever the order they came in.
    ids = [s.id[0] for s in pack.sources]
    assert ids.index("S") < ids.index("G") and ids[:3] == ["S", "S", "S"]
    assert "cites former CIV 9805; the table says omitted: an open finding, and no successor is guessed" in pack.gaps


# --- the summary page --------------------------------------------------------------------------------------------------

def test_the_summary_page_says_cites_former_x_now_y_with_both_recited_and_leaves_the_rest_open(data):
    files = data / "cases" / KEY / "files"
    files.mkdir(parents=True)
    (files / "Old letter.txt").write_text(OLD_LETTER, encoding="utf-8")
    (files / "New letter.txt").write_text(NEW_LETTER, encoding="utf-8")
    (data / "cases" / KEY / "manifest.json").write_text(json.dumps({"case": KEY, "files": [
        {"id": "1", "name": "Old letter.txt", "path": "Old letter.txt", "mimeType": "text/plain", "md5": "", "modified": "",
         "heldBack": False, "action": "download", "local": "Old letter.txt"},
        {"id": "2", "name": "New letter.txt", "path": "New letter.txt", "mimeType": "text/plain", "md5": "", "modified": "",
         "heldBack": False, "action": "download", "local": "New letter.txt"}], "extracts": {}}), encoding="utf-8")
    community = Community((CASE,))
    pi.build(data, sources=(*index_sources((CASE,)), *cp.index_sources(collections(community))), kind_of=lambda name: "")
    _former_words(data)
    today, day = date(2099, 3, 1), date(2096, 1, 1)
    summary = cp.summarize(community, data, collection(community, KEY), today=today, as_of=day)
    assert [u.cited for u in summary.citations] == ["CIV 9805", "CIV 9803(g)", "CIV 9903(a)"]
    assert summary.counts()["citations"] == 3 and summary.counts()["citationsByResolution"] == {"former": 1, "unresolved": 1, "current": 1}
    page = summary.markdown(today)
    section = page[page.index(f"## {cp.CITATIONS}"):page.index(f"## {cp.QUESTIONS}")]
    assert "resolved to the law in force on 2096-01-01, where the disk shows it" in section
    assert "### CIV 9803(g) (former number)" in section and "### CIV 9805 (OPEN)" in section and "### CIV 9903(a) (on the shelf)" in section
    assert "- Cited by: Old letter.txt (passage 0)" in section
    assert "  > Date: March 1, 2092 The board gives notice under Civil Code Section 9803(g)" in section
    assert "- cites former CIV 9803(g), now CIV 9901 (commission comment and disposition table" in section
    assert "- Former CIV 9803, its own words as last in force (to 2093-12-31): digest " in section
    assert "  > (g) A notice of the hearing is given fourteen days before it." in section
    assert "- Now CIV 9901: digest " in section and "  > (b) The notice is given fifteen days before the hearing." in section
    assert "- cites former CIV 9805; the table says omitted: an open finding, and no successor is guessed" in section
    assert "- CIV 9903: digest " in section and "(a) A fine is imposed only after the hearing." not in section   # a current section is not recited whole
    questions = page[page.index(f"## {cp.QUESTIONS}"):page.index(f"## {cp.CONFLICTS}")]
    assert ("- What section, if any, now holds what CIV 9805 held? the table says omitted: an open finding, and no successor "
            "is guessed. Cited by Old letter.txt (passage 0).") in questions
    told = summary.as_dict()
    assert told["asOf"] == "2096-01-01" and [c["resolution"] for c in told["citations"]] == ["unresolved", "former", "current"]
    assert told["citations"][1]["citedBy"] == [{"document": "Old letter.txt", "passage": 0}]
    assert "CIV 9803(g) is cited" not in "\n".join(g.text for g in summary.gaps())
    # Without the former words: the gap says only the successor is recited; without a day: the shelf now.
    for path in (data / "authorities" / "history" / "CIV-9803").iterdir():
        path.unlink()
    bare = cp.summarize(community, data, collection(community, KEY), today=today)
    assert bare.as_of is None and any(g.key == "former-words-not-held" and "CIV 9803(g)" in g.text for g in bare.gaps())
    assert "resolved to the words on the shelf now (no day was asked" in bare.markdown(today)
    assert cp.summarize(community, data, collection(community, KEY), today=today).markdown(today) == bare.markdown(today)


def test_the_command_takes_a_day(data, monkeypatch, capsys):
    from jason.cli import build_parser

    files = data / "cases" / KEY / "files"
    files.mkdir(parents=True)
    (files / "Old letter.txt").write_text(OLD_LETTER, encoding="utf-8")
    (data / "cases" / KEY / "manifest.json").write_text(json.dumps({"case": KEY, "files": [
        {"id": "1", "name": "Old letter.txt", "path": "Old letter.txt", "mimeType": "text/plain", "md5": "", "modified": "",
         "heldBack": False, "action": "download", "local": "Old letter.txt"}], "extracts": {}}), encoding="utf-8")
    community = Community((CASE,))
    pi.build(data, sources=index_sources((CASE,)), kind_of=lambda name: "")
    parser = build_parser()
    monkeypatch.setattr("jason.community.community", lambda: community)
    monkeypatch.setattr("jason.config.data_dir", lambda env_file=None: data)
    args = parser.parse_args(["collection", KEY, "--as-of", "2096-01-01", "--json"])
    assert args.func(args) == 0
    told = json.loads(capsys.readouterr().out)
    assert told["asOf"] == "2096-01-01" and [c["cited"] for c in told["citations"]] == ["CIV 9805", "CIV 9803(g)"]
    assert told["citations"][1]["note"].startswith("cites former CIV 9803(g), now CIV 9901")
    args = parser.parse_args(["collection", KEY, "--as-of", "March 1"])
    assert args.func(args) == 2 and "YYYY-MM-DD" in capsys.readouterr().err
    assert not (data / "collections").exists()
