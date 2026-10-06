"""Citation scoping and rule authority read a stored segmentation's parts and exhibits (made-up files and readings): a name
a part or an exhibit goes by, the way down through the nesting, ambiguity when two documents hold the same label, a stale
reading left out with its reason, and the manual classification as the fallback."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from types import SimpleNamespace

import pytest

from jason.community import scoping as S
from jason.community.books import Book, BookEntry
from jason.community.document_segments import Part as SegPart
from jason.community.document_segments import PartKind, Segment, Segmentation
from jason.community.outlines import CitableDocument, outline_from_text
from jason.community.symbols import DocumentKind
from jason.tasks import cite_scope
from jason.tasks import segments as task
from jason.tasks.cite import Shelf, resolve

INSTRUMENT = ("ARTICLE 1 GENERAL\n1.1 Scope. The association engages the vendor.\n1.2 Term. One year.\nCommunity Regulations\n"
              "7.3 Noise. Owners shall keep quiet after ten.\n7.4 Pets. Pets are leashed.\nEXHIBIT A MAP\n"
              "3.1 Boundary. The boundary is marked.\nEXHIBIT B SCHEDULES\nSchedule 1 Hours\n8.1 Hours. Work is by day.\n")
AGREEMENT = ("ARTICLE 1 GENERAL\n1.1 Scope. The parties agree.\nEXHIBIT A PRICES\n2.1 Price. The price is stated.\n")


def _library(tmp_path, name, rows):
    """A library of made-up files: data/library/library.db, files/<path> (their bytes), and text/<id>.txt."""
    folder = tmp_path / "library"
    (folder / "files").mkdir(parents=True, exist_ok=True)
    (folder / "text").mkdir(exist_ok=True)
    conn = sqlite3.connect(folder / "library.db")
    conn.execute("CREATE TABLE IF NOT EXISTS documents (id TEXT, path TEXT, name TEXT, kind TEXT, category TEXT, period TEXT, "
                 "confidential INTEGER)")
    for doc_id, path, body in rows:
        (folder / "files" / path).write_bytes(body)
        conn.execute("INSERT INTO documents VALUES (?, ?, ?, '', '', '', 0)", (doc_id, path, path))
    conn.commit()
    conn.close()


def _outline(tmp_path, key, title, kind, text, library=""):
    outline = outline_from_text(text, key=key, title=title, kind=kind)
    outline.library = library
    folder = tmp_path / "outlines"
    folder.mkdir(exist_ok=True)
    (folder / f"{key}.json").write_text(json.dumps(outline.to_dict()), encoding="utf-8")
    return outline


def _reading(tmp_path, doc_id, body, segments, parts, *, sha=None):
    seg = Segmentation(doc_id, sha or hashlib.sha256(body).hexdigest(), f"{doc_id}.pdf", 14, segments=segments, parts=parts)
    task.save(tmp_path, seg)
    return seg


def _instrument_reading(tmp_path, doc_id="9001", body=b"%PDF instrument", **kw):
    segments = [Segment("s1", 1, 14, "Agreement", "declaration"),
                Segment("s1.1", 10, 11, "Map", role="exhibit", label="Exhibit A", aliases=("Ex. A",), parent="s1"),
                Segment("s1.2", 12, 14, "Schedules", role="exhibit", label="Exhibit B", aliases=("Ex. B",), parent="s1")]
    parts = [SegPart("community-regulations", "Community Regulations", PartKind.RULES, 4, 9, "Community Regulations", segment="s1"),
             SegPart("schedule-1", "Schedule 1", PartKind.OTHER, 12, 14, "Schedule 1 Hours", segment="s1.2")]
    return _reading(tmp_path, doc_id, body, segments, parts, **kw)


@pytest.fixture
def world(tmp_path):
    """Two documents, each with a stored reading: the first has a rules part, an exhibit A, and an exhibit B holding a
    part; the second has an exhibit A of its own."""
    body1, body2 = b"%PDF instrument", b"%PDF agreement"
    _library(tmp_path, "lib", [("9001", "instrument.pdf", body1), ("9002", "agreement.pdf", body2)])
    _outline(tmp_path, "instrument", "Instrument", "declaration", INSTRUMENT, library="instrument.pdf")
    _outline(tmp_path, "agreement", "Agreement", "bylaws", AGREEMENT, library="agreement.pdf")
    _instrument_reading(tmp_path, body=body1)
    _reading(tmp_path, "9002", body2, [Segment("s1", 1, 6, "Agreement", "bylaws"),
                                       Segment("s1.1", 5, 6, "Prices", role="exhibit", label="Exhibit A", parent="s1")], [])
    community = SimpleNamespace(
        living_documents=lambda: (),
        citable_documents=lambda: (
            CitableDocument("instrument", "Instrument", "d1", DocumentKind.DECLARATION, aliases=("Instrument",), cite_as="Instrument"),
            CitableDocument("agreement", "Agreement", "d2", DocumentKind.BYLAWS, aliases=("Agreement",), cite_as="Agreement")),
        book_entries=lambda: (BookEntry("instrument", Book.DECL), BookEntry("agreement", Book.BYLAWS)),
        conflicts=lambda: (), notice_provisions=lambda: ())
    return tmp_path, community


def _shelf(world, **kw):
    path, community = world
    return Shelf(community, path, repo=path / "no-repo", **kw)


# --- A name a part or an exhibit goes by ----------------------------------------------------------------------------------------


def test_an_exhibit_written_in_the_document_that_holds_it_is_that_documents_own_and_the_path_says_so(world):
    got = resolve("Exhibit A", shelf=_shelf(world), citing="instrument")
    assert got["found"] and got["scope"]["document"] == "instrument" and got["scope"]["basis"] == "segment"
    assert got["scope"]["path"] == ["instrument", "Exhibit A"] and got["scope"]["partSource"] == "segments"
    assert resolve("Ex. B", shelf=_shelf(world), citing="instrument")["scope"]["path"] == ["instrument", "Exhibit B"]


def test_the_same_label_in_two_documents_is_ambiguous_and_names_both(world):
    got = resolve("Exhibit A", shelf=_shelf(world))
    assert not got["found"] and got["reason"] == "ambiguous_document"
    assert {c["document"] for c in got["scope"]["candidates"]} == {"instrument", "agreement"}
    assert "documents that could be meant" in got["detail"]
    other = resolve("Exhibit A", shelf=_shelf(world), citing="agreement")
    assert other["found"] and other["scope"]["document"] == "agreement"


def test_a_label_only_one_document_holds_is_that_document_even_when_written_elsewhere(world):
    got = resolve("Exhibit B", shelf=_shelf(world), citing="agreement")
    assert got["found"] and got["scope"]["document"] == "instrument" and got["scope"]["path"] == ["instrument", "Exhibit B"]


def test_a_part_inside_an_exhibit_resolves_through_the_nesting(world):
    got = resolve("Schedule 1", shelf=_shelf(world))
    assert got["found"] and got["scope"]["path"] == ["instrument", "Exhibit B", "Schedule 1"]
    assert got["scope"]["document"] == "instrument"


def test_a_section_number_is_the_parts_only_where_the_part_has_the_section(world):
    shelf = _shelf(world)
    ok = resolve("Section 7.3 of the Community Regulations", shelf=shelf)
    assert ok["found"] and ok["scope"]["document"] == "instrument" and ok["scope"]["basis"] == "segment"
    assert ok["scope"]["path"] == ["instrument", "Community Regulations"]
    outside = resolve("Section 1.1 of the Community Regulations", shelf=shelf)
    assert not outside["found"] and outside["reason"] == "not_in_document"      # the document has a 1.1; the part does not
    index = shelf.index()
    assert index.part_of("instrument", "7.4").source == "segments" and index.part_of("instrument", "1.1") is None


def test_the_part_stops_where_an_exhibit_begins(world):
    parts = [p for p in _shelf(world).index().parts if p.source == "segments" and p.kind == "rules"]
    assert [p.numbers for p in parts] == [("7.3", "7.4")]                         # 3.1 and the schedule's 8.1 are the exhibits'


def test_a_section_in_an_exhibit_is_a_miss_never_the_documents_section_of_that_number(world):
    got = resolve("Section 3.1 of Exhibit A", shelf=_shelf(world))
    assert not got["found"] and got["reason"] == "not_in_document"
    assert "not an outline on the shelf" in got["detail"]
    assert not resolve("Section 8.1 of Exhibit B", shelf=_shelf(world))["found"]


def test_without_the_stored_readings_the_names_are_unknown_documents(world):
    got = resolve("Exhibit A", shelf=_shelf(world, segments=False), citing="instrument")
    assert not got["found"] and got["reason"] in ("unknown_document", "unparsed")


# --- A reading that cannot be used, and why -------------------------------------------------------------------------------------


def test_a_stale_reading_is_left_out_with_the_reason(world):
    path, _ = world
    (path / "library" / "files" / "instrument.pdf").write_bytes(b"%PDF instrument, edited")
    shelf = _shelf(world)
    notes = shelf.index().segment_notes
    assert any("9001" in n and "stale" in n for n in notes)
    assert not resolve("Exhibit B", shelf=shelf, citing="instrument")["found"]
    assert not any(p.source == "segments" and p.document == "instrument" for p in shelf.index().parts)


def test_a_file_that_holds_several_documents_is_not_taken_for_one(world):
    path, _ = world
    body = b"%PDF agreement"
    _reading(path, "9002", body, [Segment("s1", 1, 3, "Agreement"), Segment("s2", 4, 6, "Other")], [])
    shelf = _shelf(world)
    assert any("9002" in n and "2 documents" in n for n in shelf.index().segment_notes)


def test_a_file_of_several_documents_is_one_outlines_when_the_outline_holds_every_one(world):
    path, community = world
    bound = AGREEMENT + "COLLECTION POLICY\n1. Notices. Notices are sent.\n"
    _outline(path, "agreement", "Agreement", "bylaws", bound, library="agreement.pdf")
    _reading(path, "9002", b"%PDF agreement", [Segment("s1", 1, 3, "Article 1 General", "bylaws"),
                                                Segment("s2", 4, 6, "Collection Policy", "policy")], [])
    notes = _shelf(world).index().segment_notes
    assert any("9002" in n and "2 documents are bound into it" in n for n in notes), notes
    assert not any("9002" in n and "not used" in n for n in notes)


def test_a_cover_or_contents_title_names_nothing_a_citation_could_mean(world):
    path, _ = world
    parts = [SegPart("example-community-association", "Example Community Association", PartKind.COVER, 1, 1,
                     "Example Community Association", segment="s1"),
             SegPart("table-of-contents", "Table of Contents", PartKind.CONTENTS, 2, 2, "Table of Contents", segment="s1"),
             SegPart("questions-answers", "Questions and Answers", PartKind.GUIDANCE, 3, 6, "Questions and Answers", segment="s1")]
    _reading(path, "9002", b"%PDF agreement", [Segment("s1", 1, 6, "Agreement", "bylaws")], parts)
    shelf = _shelf(world)
    assert not resolve("Example Community Association", shelf=shelf)["found"]
    assert not resolve("Table of Contents", shelf=shelf)["found"]
    assert resolve("Questions and Answers", shelf=shelf)["found"]


def test_a_file_not_in_the_library_is_left_out(world):
    path, _ = world
    _reading(path, "sha-0123", b"anything", [Segment("s1", 1, 2, "X")], [])
    assert any("sha-0123" in n and "not in the library" in n for n in _shelf(world).index().segment_notes)


def test_a_file_is_bound_to_the_outline_whose_words_it_is_never_to_the_nearest(tmp_path):
    words = " ".join(f"{a}{i} {b}{i}" for i, (a, b) in enumerate(zip("alpha beta gamma delta".split() * 40, "north south east west".split() * 40)))
    other = " ".join(f"{b}{i} {a}{i}" for i, (a, b) in enumerate(zip("kappa sigma omega theta".split() * 40, "red green blue pink".split() * 40)))
    outlines = {"one": outline_from_text("1. Words. " + words, key="one"), "two": outline_from_text("1. Words. " + other, key="two")}
    assert cite_scope.bind_outline(words, outlines)[0] == "one"
    assert cite_scope.bind_outline("totally different words " * 80, outlines)[0] == ""
    twin = {"one": outlines["one"], "twin": outline_from_text("1. Words. " + words, key="twin")}
    key, why = cite_scope.bind_outline(words, twin)
    assert key == "" and "more than one outline" in why


def test_a_file_with_no_outline_of_its_own_is_bound_by_its_text_on_disk(world):
    path, _ = world
    words = " ".join(f"{a}{i} {b}{i}" for i, (a, b) in enumerate(zip("alpha beta gamma delta".split() * 40, "north south east west".split() * 40)))
    text = INSTRUMENT.replace("1.1 Scope.", "1.1 Scope. " + words)
    _outline(path, "instrument", "Instrument", "declaration", text)           # no library path: bound by words
    (path / "library" / "text" / "9001.txt").write_text(text, encoding="utf-8")
    shelf = _shelf(world)
    assert resolve("Exhibit B", shelf=shelf, citing="instrument")["found"]
    assert any("9001" in n and "is the document instrument" in n for n in shelf.index().segment_notes)
    (path / "library" / "text" / "9001.txt").write_text("a few words", encoding="utf-8")
    assert any("9001" in n and "too short" in n for n in _shelf(world).index().segment_notes)


# --- The manual classification stays the fallback ----------------------------------------------------------------------------------


def test_the_manual_classification_is_the_fallback_and_a_reading_with_sections_replaces_it(world, monkeypatch):
    classified = S.Part("instrument", "7.3", "rules", "Community Regulations")
    monkeypatch.setattr(cite_scope, "manual_parts", lambda community: (classified,))
    shelf = _shelf(world)
    assert classified not in shelf.index().parts and shelf.index().part_of("instrument", "7.3").source == "segments"
    bare = _shelf(world, segments=False)
    assert bare.index().parts == (classified,) and bare.index().part_of("instrument", "7.3") is classified
    path, _ = world
    (path / "library" / "files" / "instrument.pdf").write_bytes(b"changed")
    assert [p for p in _shelf(world).index().parts if p.document == "instrument"] == [classified]       # a stale reading leaves the classification alone


def test_a_citation_that_resolved_before_resolves_to_the_same_document_after(world):
    for text in ("Section 1.1", "Section 2.1", "Instrument 1.2", "Agreement 1.1", "Section 7.3"):
        before = resolve(text, shelf=_shelf(world, segments=False))
        after = resolve(text, shelf=_shelf(world))
        if before["found"]:
            assert after["found"] and after["citation"] == before["citation"], text


def test_a_scan_lists_the_nesting_and_counts_the_new_names(world):
    from jason.tasks.cite_scope import read_text

    rows = read_text(_shelf(world), "See Exhibit B and Schedule 1; Exhibit A is in both.", citing="instrument")
    by = {r["text"]: r for r in rows}
    assert by["Exhibit B"]["path"] == ["instrument", "Exhibit B"] and by["Exhibit B"]["status"] == "resolved"
    assert by["Schedule 1"]["path"] == ["instrument", "Exhibit B", "Schedule 1"]
    assert by["Exhibit A"]["document"] == "instrument"
    again = read_text(_shelf(world), "See Exhibit A.", citing="")
    assert again[0]["status"] == "ambiguous document" and sorted(again[0]["candidates"]) == ["agreement", "instrument"]


# --- Rule authority reads the parts, too ------------------------------------------------------------------------------------------

from jason.community import rule_authority as ra  # noqa: E402
from jason.tasks import rule_authority as ra_task  # noqa: E402

GUIDE = ("1.1 Guide\nThe Board may adopt rules for the Common Area.\n1.2 Rules\nNo vehicle shall be parked on the lawn.\n"
         "EXHIBIT A FORMS\n1.3 Forms. The Board may adopt rules for the forms.\n")


def _classified(text, source="manual"):
    cut = text.index("1.2 Rules")
    return [ra.RulePart(source, 0, cut, "guidance", "manual", "", "classification"),
            ra.RulePart(source, cut, len(text), "rule", "rules", "", "classification")]


def _segment_parts():
    return [SegPart("guide", "Guide", PartKind.GUIDANCE, 1, 2, "1.1 Guide", "1.2 Rules", segment="s1"),
            SegPart("rules", "Rules", PartKind.RULES, 3, 4, "1.2 Rules", segment="s1")]


def test_segment_parts_give_the_same_standing_where_the_classification_already_covers_the_document():
    text = GUIDE.split("EXHIBIT A")[0]
    o = outline_from_text(text, key="manual", kind="operating_rules")
    old = _classified(text)
    new = ra.merge_parts(ra.parts_from_segments("manual", _segment_parts(), text), old, text)
    assert [(p.kind, p.origin) for p in new] == [("guidance", "segments"), ("rule", "segments")]
    before = [(c.section, c.part) for c in ra.candidates(o, parts=old)]
    after = [(c.section, c.part) for c in ra.candidates(o, parts=new)]
    assert before == after and before                                   # the same grants, in the same parts
    assert [r.words for r in ra.rules_on_file([o], parts=old)] == [r.words for r in ra.rules_on_file([o], parts=new)]
    assert {c.part_source for c in ra.candidates(o, parts=new)} == {"segments"}
    assert {c.part_source for c in ra.candidates(o, parts=old)} == {"classification"}
    rows_old, rows_new = ra.find([o], parts=old)["authorities"], ra.find([o], parts=new)["authorities"]
    assert [(r.id, r.answer, r.part) for r in rows_old] == [(r.id, r.answer, r.part) for r in rows_new]


def test_the_classification_fills_the_text_no_segment_part_covers():
    text = GUIDE.split("EXHIBIT A")[0]
    only_rules = [SegPart("rules", "Rules", PartKind.RULES, 3, 4, "1.2 Rules", segment="s1")]
    new = ra.merge_parts(ra.parts_from_segments("manual", only_rules, text), _classified(text), text)
    assert [(p.kind, p.origin) for p in new] == [("guidance", "classification"), ("rule", "segments")]
    assert new[0].end == new[1].start and new[-1].end == len(text)
    left_out = ra.parts_from_segments("manual", [SegPart("x", "Nowhere", PartKind.RULES, 1, 2, "No such heading")], text)
    assert left_out == []                                               # a heading not in the text is not placed by guess
    assert ra.merge_parts([], _classified(text), text) == _classified(text)


def test_where_the_readings_disagree_whether_a_stretch_is_a_rule_the_classification_stays_and_says_so():
    text = GUIDE.split("EXHIBIT A")[0]
    o = outline_from_text(text, key="manual", kind="operating_rules")
    wide = [SegPart("rules", "Rules", PartKind.RULES, 1, 4, "1.1 Guide", segment="s1")]          # the guide read as rules
    old = _classified(text)
    new = ra.merge_parts(ra.parts_from_segments("manual", wide, text), old, text)
    assert [(p.kind, p.origin, p.contested) for p in new] == [("guidance", "classification", "rule"), ("rule", "segments", "")]
    assert [r.words for r in ra.rules_on_file([o], parts=new)] == [r.words for r in ra.rules_on_file([o], parts=old)]
    guide = [c for c in ra.candidates(o, parts=new) if c.section == "1.1"][0]
    assert (guide.part, guide.part_source, guide.part_contested) == ("guidance", "classification", "rule")
    rows = ra.find([o], parts=new)["authorities"]
    lines = ra_task.authority_lines(rows, answers=tuple(ra.Answer))
    assert any("the stored segmentation takes it to be rule; the classification is kept" in line for line in lines), lines


def test_a_grant_in_an_exhibit_is_the_exhibits_and_a_rule_there_is_not_a_rule_on_file():
    o = outline_from_text(GUIDE, key="manual", kind="operating_rules")
    exhibit = Segment("s1.1", 5, 6, "Forms", role="exhibit", label="Exhibit A", parent="s1")
    parts = ra.parts_from_segments("manual", _segment_parts(), GUIDE, exhibits=[exhibit])
    assert [p.kind for p in parts] == ["guidance", "rule", "exhibit"] and parts[1].end == parts[2].start
    kinds = {c.section: c.part for c in ra.candidates(o, parts=parts)}
    assert kinds["1.3"] == "exhibit" and kinds["1.1"] == "guidance"
    assert all("forms" not in r.words for r in ra.rules_on_file([o], parts=parts))


def test_the_recital_says_where_each_part_came_from():
    o = outline_from_text(GUIDE.split("EXHIBIT A")[0], key="manual", kind="operating_rules")
    parts = ra.parts_from_segments("manual", _segment_parts(), o.text)
    rows = ra.find([o], parts=parts)["authorities"]
    lines = ra_task.authority_lines(rows, answers=tuple(ra.Answer))
    assert any(line == "  part: guidance (from the stored segmentation)" for line in lines), lines
    assert all(r.part_source == "segments" for r in rows if r.part)
    again = ra.RuleAuthority.from_dict(rows[0].to_dict())
    assert again.part_source == rows[0].part_source


def test_stored_readings_become_rule_parts_and_a_stale_one_leaves_the_classification(world):
    path, _ = world
    notes: list[str] = []
    parts = ra_task.rule_parts(path, None, notes=notes)
    mine = [p for p in parts if p.source == "instrument"]
    assert {p.kind for p in mine} >= {"rule", "exhibit"} and {p.origin for p in mine} == {"segments"}
    assert any("9001" in n and "instrument" in n for n in notes)
    (path / "library" / "files" / "instrument.pdf").write_bytes(b"edited")
    stale: list[str] = []
    assert [p for p in ra_task.rule_parts(path, None, notes=stale) if p.source == "instrument"] == []
    assert any("stale" in n for n in stale)
    assert ra_task.rule_parts(path, None, segments=False) == []


# --- Parts are placed in page order, never by every occurrence of a heading -----------------------------------------------------

from jason.community.document_segments import locate_heading, place_parts  # noqa: E402

GUIDE_TEXT = ("ACME COMMUNITY\nTABLE OF CONTENTS\nRules ........ 4\nPolicy ........ 9\n"
              + "".join(f"A line of the guide, number {i}, says nothing about parts.\n" for i in range(40))
              + "Rules\n1.1 Parking. No vehicle shall be parked on the lawn.\nACME COMMUNITY\n1.2 Noise. Quiet after ten.\n"
              "ACME COMMUNITY\n1.3 Pets. Pets are leashed.\nPolicy\n2.1 Dues. Dues are due monthly.\nACME COMMUNITY\n")


def _guide_parts():
    return [SegPart("acme", "ACME COMMUNITY", PartKind.COVER, 1, 1, "ACME COMMUNITY", segment="s1"),
            SegPart("toc", "TABLE OF CONTENTS", PartKind.CONTENTS, 2, 3, "TABLE OF CONTENTS", segment="s1"),
            SegPart("rules", "Rules", PartKind.RULES, 4, 7, "Rules", segment="s1"),
            SegPart("policy", "Policy", PartKind.POLICY, 8, 9, "Policy", segment="s1")]


def test_a_heading_is_a_line_not_a_word_in_a_contents_entry_and_is_found_after_the_part_before_it():
    assert locate_heading("Rules ........ 4\nRules\n", "Rules") == len("Rules ........ 4\n")
    assert locate_heading("see the Rules here\n", "Rules") is None
    assert locate_heading("Rules\nRules\n", "Rules", after=1) == 6


def test_a_running_header_printed_again_is_inside_the_part_and_is_not_another_part():
    spans = place_parts(_guide_parts(), GUIDE_TEXT, (), 9)
    assert set(spans) == {"acme", "toc", "rules", "policy"}
    starts = [spans[k][0] for k in ("acme", "toc", "rules", "policy")]
    assert starts == sorted(starts) and spans["acme"][0] == 0
    assert GUIDE_TEXT[spans["rules"][0]:spans["rules"][0] + 5] == "Rules" and spans["rules"][0] > spans["toc"][0] + 300
    assert spans["rules"][1] == spans["policy"][0]                     # each part ends where the next begins
    assert GUIDE_TEXT[spans["rules"][0]:spans["rules"][1]].count("ACME COMMUNITY") == 2    # its running headers are its own


def test_a_contents_part_is_a_few_pages_of_text_not_the_guide_that_follows_it():
    text = "TABLE OF CONTENTS\n" + "".join(f"Guide line {i} with some words in it.\n" for i in range(400))
    toc = SegPart("toc", "TABLE OF CONTENTS", PartKind.CONTENTS, 2, 3, "TABLE OF CONTENTS", segment="s1")
    (start, end), = place_parts([toc], text, (), 30).values()
    assert end - start <= 1.5 * 2 / 30 * len(text) + 1 and end - start < len(text) / 8
    assert place_parts([toc], text, (), 0)["toc"][1] == len(text)      # no page count, no cap: the next part's start is all there is


def test_a_cover_or_contents_part_never_overrides_a_finer_reading_and_makes_no_new_parts():
    text = GUIDE_TEXT
    old = [ra.RulePart("m", 0, text.index("Rules\n1.1"), "guidance", "manual", "g", "classification"),
           ra.RulePart("m", text.index("Rules\n1.1"), text.index("Policy\n2.1"), "rule", "rules", "r", "classification"),
           ra.RulePart("m", text.index("Policy\n2.1"), len(text), "policy", "disc", "p", "classification")]
    new = ra.parts_from_segments("m", _guide_parts(), text, page_count=9)
    assert [p.kind for p in new][:2] == ["cover", "contents"]
    merged = ra.merge_parts(new, old, text)
    assert [(p.kind, p.origin) for p in merged] == [("guidance", "classification"), ("rule", "segments"), ("policy", "segments")]
    assert all(not p.contested for p in merged)
    assert len(ra.merge_parts([p for p in new if p.kind in ("cover", "contents")], old, text)) == 3
    again = ra.merge_parts([p for p in new if p.kind in ("cover", "contents")], old, text)
    assert [(p.kind, p.origin) for p in again] == [("guidance", "classification"), ("rule", "classification"), ("policy", "classification")]


def test_a_file_of_several_documents_is_used_where_the_outline_holds_every_one(world):
    path, _ = world
    body = b"%PDF instrument"
    segments = [Segment("s1", 1, 8, "Community Regulations", "declaration"), Segment("s2", 9, 14, "Schedules", "policy")]
    _reading(path, "9001", body, segments, [])
    notes = _shelf(world).index().segment_notes
    assert any("9001" in n and "2 documents are bound into it" in n for n in notes)
    _reading(path, "9001", body, [Segment("s1", 1, 8, "Community Regulations", "declaration"), Segment("s2", 9, 14, "Unrelated Matter", "policy")], [])
    assert any("9001" in n and "does not hold 1 of them" in n for n in _shelf(world).index().segment_notes)
