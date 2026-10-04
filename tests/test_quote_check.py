"""An answer's quotations and citations checked against stored words (``jason.community.quote_check``).

Every statute ("CIV 9901"), document, page, and letter here is made up.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from jason.community import law_text
from jason.community import passage_index as pi
from jason.community import quote_check as qc
from jason.community.cite import Unit, located_targets, targets_in
from jason.community.outlines import outline_from_text
from jason.community.quote_check import Match, Verdict

NOTICE = ("(a) A notice shall be given in writing to each member of the made-up association.\n\n"
          "(b) The notice is given ten days before the hearing, and it names the day and the place.")
OTHER = "The board keeps a register of every made-up kite flown over the common area."
EARLY = "A member may fly one kite until the first day of the made-up year."
LATE = "A member may fly two kites on and after the first day of the made-up year."
RULES = ("# Kite Rules\n\n## 1.1 Pets\n\nEach unit may keep two pets, and a fish is not counted as a pet.\n\n"
         "## 1.2 Parking\n\nEach unit has one space, and a guest parks on the street for the dura-\ntion of a visit.\n")
SUMMARY = "# Hearing summary\n\nIn short, the board warns a member a good fortnight before any hearing is held.\n"
GUIDE = "# A guide\n\nA careful manager sends the hearing letter by two methods whenever the budget allows.\n"
LETTER = "# Counsel's letter\n\nOur office advises the board to settle the made-up kite matter before the spring.\n"
DECLARATION = "# A witness's declaration\n\nI saw the made-up kite strike the lamp post on the evening in question.\n"

SOURCES = (
    pi.IndexSource("records", "governing", pi.Standing.RECORD),
    pi.IndexSource("authorities", "authorities", pi.Standing.AUTHORITY, front_matter=True),
    pi.IndexSource("reports", "pages", pi.Standing.PAGE, generated=True),
    pi.IndexSource("reference", "reference", pi.Standing.REFERENCE),
    pi.IndexSource("library", "private", pi.Standing.RECORD, confidential=True),
    pi.IndexSource("case-example", "case", pi.Standing.EVIDENCE, confidential=True),
)
PAGE = "authorities/CIV/CIV-9900-9910.md"
PROFILE = SimpleNamespace(living_documents=lambda: (), citable_documents=lambda: ())


@pytest.fixture()
def data(tmp_path: Path) -> Path:
    law = tmp_path / "authorities" / "CIV"
    law.mkdir(parents=True)
    (tmp_path / PAGE).write_text(
        "# Made-up hearings\n\n- Source: A made-up Legislature, 2099 session publication\n\n"
        f"## CIV 9901\n\n- History: made up\n\n9901. (Made up for a test.)\n\n{NOTICE}\n\n"
        f"## CIV 9902\n\n9902. (Made up for a test.)\n\n{OTHER}\n\n"
        f"## CIV 9905\n\n9905. (Made up; operative until the made-up year.)\n\n{EARLY}\n\n"
        f"## CIV 9905\n\n9905. (Made up; operative on the made-up year.)\n\n{LATE}\n", encoding="utf-8")
    (tmp_path / "authorities" / "manifest.json").write_text(json.dumps({"pages": [{
        "file": PAGE, "citation": "CIV 9900-9910", "title": "Made-up hearings", "code": "CIV", "start": "9900",
        "end": "9910", "sections": ["9901", "9902", "9905"], "basis": "duty", "why": [], "session": "2099"}]}),
        encoding="utf-8")
    for folder, name, text in (("governing", "rules.md", RULES), ("pages", "summary.md", SUMMARY),
                               ("reference", "guide.md", GUIDE), ("private", "letter.md", LETTER),
                               ("case", "declaration.md", DECLARATION)):
        (tmp_path / folder).mkdir()
        (tmp_path / folder / name).write_text(text, encoding="utf-8")
    outline = outline_from_text("1.1 Pets\nEach unit may keep two pets, and a fish is not counted as a pet.\n"
                                "1.2 Parking\nEach unit has one space, and a guest parks on the street for the "
                                "duration of a visit.\n", key="rules", title="Kite Rules", kind="operating_rules")
    outline.aliases = ["Kite Rules"]
    (tmp_path / "outlines").mkdir()
    (tmp_path / "outlines" / "rules.json").write_text(json.dumps(outline.to_dict()), encoding="utf-8")
    pi.build(tmp_path, sources=SOURCES, kind_of=lambda name: "")
    return tmp_path


def check(data: Path, answer: str, **more) -> qc.Report:
    return qc.check(answer, data, community=PROFILE, **more)


def test_an_exact_quotation_is_found_with_its_source(data):
    report = check(data, 'Civil Code 9901(a) says "A notice shall be given in writing to each member" of it.')
    (quote,) = report.quotes
    assert quote.verdict is Verdict.FOUND and quote.match is Match.EXACT and quote.attributed == ["CIV 9901(a)"]
    shelf, passage = quote.places[0], quote.places[1]
    assert shelf.citation == "CIV 9901(a)" and shelf.digest == law_text.section_digest("CIV 9901", data)
    assert shelf.standing == "authority" and shelf.path == PAGE
    assert passage.path == PAGE and passage.catalog == "authorities" and passage.standing == "authority"
    assert "CIV 9901" in passage.section and passage.passages and "to each member of the made-up" in passage.context
    (cited,) = report.citations
    assert cited.as_dict()["onShelf"] and cited.digest == shelf.digest and cited.quotes == [{"quote": 1, "inItsWords": True}]
    assert report.clean and report.counts["found"] == 1 and report.as_dict()["minimumWords"] == qc.MIN_WORDS
    assert not quote.warnings


def test_folding_finds_a_quotation_across_a_line_break_a_hyphen_and_curly_marks(data):
    # The stored rule breaks "dura-\ntion" at a line's end; the answer writes the word whole, in curly marks.
    report = check(data, "The handbook says \u201ca guest parks on the street for the duration of a visit\u201d.")
    (quote,) = report.quotes
    assert quote.verdict is Verdict.FOUND and quote.match is Match.NORMALIZED and quote.quote.style == "curly"
    assert quote.places[0].path == "governing/rules.md" and quote.places[0].standing == "record"
    assert "dura-" in quote.places[0].context                       # shown as stored, not as folded
    spread = check(data, 'It says "A notice shall be given in writing to each member of the made-up association. '
                         '(b) The notice is given ten days before the hearing".')
    assert spread.quotes[0].verdict is Verdict.FOUND and spread.quotes[0].match is Match.NORMALIZED


def test_one_changed_word_is_altered_with_the_difference_shown(data):
    report = check(data, 'Civil Code 9901 says "The notice is given fifteen days before the hearing".')
    (quote,) = report.quotes
    assert quote.verdict is Verdict.ALTERED and quote.differences == [{"quoted": "fifteen", "stored": "ten"}]
    assert "given [[ten]] days before" in quote.stored and "given [[fifteen]] days before" in quote.quoted
    assert quote.compared_with.citation == "CIV 9901" and not report.clean
    assert report.citations[0].quotes == [{"quote": 1, "inItsWords": "altered"}]
    # With no citation beside it, the nearest stored words are found through the index.
    bare = check(data, 'Somewhere it says "The notice is given fifteen days before the hearing".').quotes[0]
    assert bare.verdict is Verdict.ALTERED and bare.compared_with.path == PAGE and "[[ten]]" in bare.stored
    lines = "\n".join(report.lines())
    assert "ALTERED" in lines and "stored: " in lines and "[[ten]]" in lines


def test_an_invented_quotation_is_not_found(data):
    report = check(data, 'The rules say "Every owner repaints the mailbox each third summer without fail".')
    assert report.quotes[0].verdict is Verdict.NOT_FOUND and not report.quotes[0].places and not report.clean
    assert report.counts["not found"] == 1


def test_a_quotation_from_a_generated_page_or_a_reference_is_flagged(data):
    page = check(data, 'jason says "the board warns a member a good fortnight before any hearing is held".').quotes[0]
    assert page.verdict is Verdict.FOUND and page.places[0].standing == "page" and page.places[0].generated
    assert any("summary" in w and "not the record or the law" in w for w in page.warnings)
    guide = check(data, 'A guide says "sends the hearing letter by two methods whenever the budget allows".').quotes[0]
    assert guide.verdict is Verdict.FOUND and any("reference shelf" in w for w in guide.warnings)


def test_a_quotation_attributed_to_the_wrong_section_is_misattributed(data):
    report = check(data, 'Civil Code 9902 says "A notice shall be given in writing to each member".')
    (quote,) = report.quotes
    assert quote.verdict is Verdict.MISATTRIBUTED and quote.attributed == ["CIV 9902"]
    assert quote.places[0].path == PAGE and "CIV 9901" in quote.places[0].section
    assert report.citations[0].citation == "CIV 9902" and report.citations[0].quotes == [{"quote": 1, "inItsWords": False}]
    # The citation that follows the quotation directly attributes it too; one in another clause does not.
    after = check(data, '"A notice shall be given in writing to each member" (Civil Code 9902).').quotes[0]
    assert after.verdict is Verdict.MISATTRIBUTED
    apart = check(data, 'Civil Code 9902 is about kites; the other section says "A notice shall be given in writing".')
    assert apart.quotes[0].verdict is Verdict.FOUND and apart.quotes[0].attributed == []
    # 'X says "A" and "B"' attributes both to X; a citation that closes one quotation does not introduce the next.
    both = check(data, 'Civil Code 9902 says "A notice shall be given in writing" and "The board keeps a register of every '
                       'made-up kite".').quotes
    assert [q.verdict for q in both] == [Verdict.MISATTRIBUTED, Verdict.FOUND] and both[1].attributed == ["CIV 9902"]
    each = check(data, '"A notice shall be given in writing" (Civil Code 9901(a)), and "The board keeps a register of '
                       'every made-up kite" (Civil Code 9902).').quotes
    assert [q.attributed for q in each] == [["CIV 9901(a)"], ["CIV 9902"]] and all(q.verdict is Verdict.FOUND for q in each)
    # A lead-in sentence that ends with a colon introduces the quotation on the next line.
    lead = check(data, 'Civil Code 9902 provides:\n"A notice shall be given in writing to each member"').quotes[0]
    assert lead.verdict is Verdict.MISATTRIBUTED
    # The words are in the section, outside the subdivision the answer names.
    outside = check(data, 'Civil Code 9901(b) says "A notice shall be given in writing to each member".').quotes[0]
    assert outside.verdict is Verdict.FOUND and any("outside (b)" in w for w in outside.warnings)
    # A section that is not on the shelf cannot confirm or refute: the words are found, the attribution unchecked.
    missing = check(data, 'Civil Code 9999 says "A notice shall be given in writing to each member".')
    assert missing.quotes[0].verdict is Verdict.FOUND and "could not open" in missing.quotes[0].warnings[0]
    assert missing.citations[0].as_dict()["onShelf"] is False


def test_a_governing_section_is_read_through_the_citation_resolver(data):
    right = check(data, 'Section 1.1 of the Kite Rules says "a fish is not counted as a pet".')
    assert right.quotes[0].verdict is Verdict.FOUND and right.quotes[0].places[0].citation == "rules#1.1"
    assert right.citations[0].kind == "section" and right.citations[0].found and len(right.citations[0].digest) == 16
    wrong = check(data, 'Section 1.2 of the Kite Rules says "a fish is not counted as a pet".')
    assert wrong.quotes[0].verdict is Verdict.MISATTRIBUTED and wrong.quotes[0].places[0].path == "governing/rules.md"
    # A whole document named beside a quotation confirms it, and never accuses.
    whole = check(data, 'The Kite Rules say "a fish is not counted as a pet".').quotes[0]
    assert whole.verdict is Verdict.FOUND and whole.places[0].citation == "rules" and not whole.warnings
    other = check(data, 'The Kite Rules say "A notice shall be given in writing to each member".').quotes[0]
    assert other.verdict is Verdict.FOUND and other.places[0].path == PAGE and "as a whole" in other.warnings[0]


def test_a_confidential_source_is_not_disclosed_unless_asked(data):
    answer = 'Counsel wrote "advises the board to settle the made-up kite matter before the spring".'
    held = check(data, answer).quotes[0]
    assert held.verdict is Verdict.FOUND and held.places[0].withheld
    told = json.dumps(held.as_dict())
    assert "letter.md" not in told and "Our office" not in told and "private" not in told and qc.WITHHELD in told
    asked = check(data, answer, include_confidential=True).quotes[0]
    assert asked.places[0].path == "private/letter.md" and "Our office advises" in asked.places[0].context
    assert any("directors and counsel" in w for w in asked.warnings)
    # A case's file opens only when the sources name its catalog or a file in it, as document_search opens it.
    witness = 'The witness wrote "I saw the made-up kite strike the lamp post on the evening in question".'
    assert check(data, witness, include_confidential=True).quotes[0].places[0].withheld
    named = check(data, witness, include_confidential=True, sources="case-example").quotes[0]
    assert named.places[0].path == "case/declaration.md" and any("neither the record nor the law" in w for w in named.warnings)
    assert check(data, witness, sources="case-example").quotes[0].places[0].withheld      # naming it is not asking
    by_file = check(data, witness, include_confidential=True, sources="case/declaration.md#0").quotes[0]
    assert not by_file.places[0].withheld and by_file.places[0].in_sources
    # A near match in a confidential file is said to exist, and its words stay back.
    near = check(data, 'Counsel wrote "advises the board to fight the made-up kite matter before the spring".').quotes[0]
    assert near.verdict is Verdict.ALTERED and near.stored == "" and "letter.md" not in json.dumps(near.as_dict())
    shown = check(data, 'Counsel wrote "advises the board to fight the made-up kite matter before the spring".',
                  include_confidential=True).quotes[0]
    assert "[[settle]]" in shown.stored and shown.differences == [{"quoted": "fight", "stored": "settle"}]


def test_an_ellipsis_is_allowed_when_its_parts_are_in_order_in_one_place(data):
    joined = check(data, 'Civil Code 9901 says "A notice shall be given ... ten days before the hearing".').quotes[0]
    assert joined.verdict is Verdict.FOUND and joined.quote.parts == ("A notice shall be given", "ten days before the hearing")
    backwards = check(data, 'It says "ten days before the hearing [...] A notice shall be given in writing".').quotes[0]
    assert backwards.verdict is Verdict.ALTERED and "order" in backwards.note
    spliced = check(data, 'It says "A notice shall be given in writing \u2026 a fish is not counted as a pet".').quotes[0]
    assert spliced.verdict is Verdict.ALTERED and "joins separate places" in spliced.note
    assert {p.path for p in spliced.places} == {PAGE, "governing/rules.md"}
    half = check(data, 'It says "A notice shall be given in writing ... and the moon is made of cheese".').quotes[0]
    assert half.verdict is Verdict.NOT_FOUND and "1 of its 2 parts" in half.note


def test_a_section_held_in_two_versions_says_so(data):
    report = check(data, 'Civil Code 9905 says "A member may fly two kites on and after the first day".')
    quote, cited = report.quotes[0], report.citations[0]
    assert quote.verdict is Verdict.FOUND and any("2 versions of CIV 9905" in w for w in quote.warnings)
    assert len(cited.versions) == 2 and cited.as_dict()["versions"][0]["digest"] == law_text.section_digest("CIV 9905", data)
    assert any("under the one number" in c and "--as-of" in c for c in cited.caveats)   # which operates is asked by day
    assert quote.places[0].digest == cited.versions[1]["digest"]        # the second version holds these words


def test_short_quotations_block_quotes_and_bylines(data):
    answer = ('The "Made-Up Rules" call it a "pet".\n\nThe statute provides:\n\n'
              "> (b) The notice is given ten days before the hearing,\n> and it names the day and the place.\n"
              "> \u2014 Civil Code 9902\n")
    report = check(data, answer)
    assert report.skipped == ["Made-Up Rules", "pet"]
    (block,) = report.quotes
    assert block.quote.style == "block" and "Civil Code" not in block.quote.text
    assert block.verdict is Verdict.MISATTRIBUTED and block.attributed == ["CIV 9902"]       # the byline names 9902
    styles = [q.style for q in qc.quotations('He said "one two three four" and \u201cfive six seven eight\u201d.\n> nine ten')]
    assert styles == ["straight", "curly", "block"]
    assert qc.quotations('An open "mark that never\n\ncloses" here') == []                    # not across a blank line


def test_sources_flag_a_quotation_from_outside_them(data):
    answer = 'The handbook says "Each unit may keep two pets" and the law says "A notice shall be given in writing".'
    report = check(data, answer, sources="governing/rules.md#0")
    pets, notice = report.quotes
    assert pets.places[0].in_sources and not pets.warnings
    assert any("not in the sources given" in w for w in notice.warnings)
    assert report.sources == {"resolved": ["governing/rules.md#0"], "unresolved": []}
    # A citation, a hit as document_search returns it, and a name jason cannot place.
    hits = json.dumps([{"path": str(data / "governing" / "rules.md"), "passage": 0}])
    assert check(data, answer, sources=hits).quotes[0].places[0].in_sources
    mixed = check(data, answer, sources="CIV 9901; nowhere.md")
    assert mixed.sources == {"resolved": ["CIV 9901"], "unresolved": ["nowhere.md"]}
    assert mixed.quotes[1].places[0].citation == "CIV 9901" and not mixed.quotes[1].warnings


def test_the_folded_text_maps_back_to_the_stored_words():
    for text in ("Each Owner\u2019s  Unit,\nassess-\n  ment \u201cdue\u201d", "  \u2022 one\u200btwo  ", "a - b, non-refundable 10-15",
                 "", "co\u00adoperate", "\u0130stanbul"):
        folded, starts = qc.fold_map(text)
        assert folded == qc.fold(text)
        assert starts is None or len(starts) == len(folded)
    assert qc.fold("assess-\n  ment \u201cDue\u201d") == 'assessment "due"' and qc.fold("10-15 days") == "10-15 days"
    # Markdown's emphasis marks are typography: dropped on both sides, and the words shown as stored.
    marked = "The **Board** `shall` act, re-\nsign, and *co*-sign."
    folded, starts = qc.fold_map(marked)
    assert folded == qc.fold(marked) == "the board shall act, resign, and cosign." and marked[starts[4]] == "B"
    assert qc.fold("the Board shall act") in folded
    found = qc.align("within fifteen days of the made-up notice", "It is paid within thirty days of the made-up notice, in full.")
    assert found.differences == (("fifteen", "thirty"),) and found.stored == "within [[thirty]] days of the made-up notice"
    assert qc.align("entirely different words here", "nothing shared at all") is None


def test_citations_are_located_by_the_grammar_already_in_use():
    text = "Under Civil Code 9901(a) and rules#1.1, see CIV 1365."
    names = {"rules": "rules"}
    found = located_targets(text, names)
    assert [(f.target.id, text[f.offset:f.offset + 5]) for f in found] == [
        ("CIV 9901(a)", "Civil"), ("rules", "rules"), ("CIV 1365", "CIV 1"), ("rules#1.1", "rules")]
    assert found[2].prior and not found[0].prior and found[0].target.unit is Unit.STATUTE
    assert targets_in(text, names) == [f.target for f in found]


def test_the_mcp_tool_and_the_command(data, monkeypatch, capsys):
    import argparse

    from jason.commands import verify_quotes as command
    from jason.mcp import county
    from jason.mcp.server import ALL_TOOLS, PROFILES

    monkeypatch.setattr("jason.community.community", lambda: PROFILE)
    answer = 'Civil Code 9901 says "The notice is given fifteen days before the hearing".'
    told = county.verify_quotes(answer, data_dir=data)
    assert told["available"] and told["counts"]["altered"] == 1 and told["quotes"][0]["differences"]
    assert told["citations"][0]["onShelf"] and told["caveats"] == list(qc.CAVEATS)
    assert county.verify_quotes(answer, data_dir=data / "nowhere") == {
        "available": False, "note": told_note(data / "nowhere")}
    assert "verify_quotes" in {t.__name__ for t in ALL_TOOLS} and "verify_quotes" not in PROFILES["board"]
    assert any("verify_quotes" in c for c in county.DOCUMENT_SEARCH_CAVEATS)
    file = data / "answer.txt"
    file.write_text(answer, encoding="utf-8")
    monkeypatch.setattr("jason.commands._shared.data_dir", lambda args=None: data)
    args = argparse.Namespace(file=str(file), sources="", confidential=False, json=True, env=None)
    assert command.cmd_verify_quotes(args) == 1
    assert json.loads(capsys.readouterr().out)["counts"]["altered"] == 1
    file.write_text('It says "A notice shall be given in writing to each member".', encoding="utf-8")
    args.json = False
    assert command.cmd_verify_quotes(args) == 0 and "FOUND (exact)" in capsys.readouterr().out


def told_note(root: Path) -> str:
    return f"no passage index at {pi.index_path(root)}: build it with jason index --build"
