"""Nested documents: a stack of open documents, so an exhibit sits inside an instrument, a report inside a packet, and the
outer document resumes. Made-up PDFs and pages built by hand, so nothing here needs Ollama or a real scan."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from jason.community import document_segments as ds
from jason.community.document_segments import (
    Line, PartKind, Segmentation, address, build_page, decide, parse_address, resolve, score_pages)
from jason.tasks import segments as task

pymupdf = pytest.importorskip("pymupdf")

PLUMBING = "pipe valve faucet drain leak copper solder fixture water heater trap flange".split()
GARDEN = "lawn shrub mulch irrigation sprinkler trim prune sod soil planter hedge turf".split()
LEGAL = "grantor grantee parcel easement covenant lien recorded instrument conveys premises".split()
BILLING = "quantity amount rate labor materials subtotal tax remit balance payment net".split()
RULES = "owner resident vehicle parking guest pet noise trash balcony common area board".split()


def _filler(words, n, seed=0, lowercase_start=False):
    lines = []
    for i in range(n):
        text = " ".join(words[(seed + i * 3 + j * 5) % len(words)] for j in range(9))
        lines.append(text if (lowercase_start or i) else text.capitalize())
    return lines


def _body(words, y0=200, n=12, seed=0, lowercase_start=False):
    return [(t, 11, False, False, y0 + 15 * i) for i, t in enumerate(_filler(words, n, seed, lowercase_start))]


def _page(doc, lines, *, footer="", header=""):
    page = doc.new_page(width=612, height=792)
    for text, size, bold, centered, y in lines:
        font = "hebo" if bold else "helv"
        width = pymupdf.get_text_length(text, fontname=font, fontsize=size)
        page.insert_text(((612 - width) / 2 if centered else 72, y), text, fontsize=size, fontname=font)
    if footer:
        page.insert_text((250, 770), footer, fontsize=9)
    if header:
        page.insert_text((72, 30), header, fontsize=9)


@pytest.fixture()
def nested(tmp_path) -> Path:
    """An agreement of eight numbered pages with a report inside it (three pages, its own numbering and header) and an
    exhibit inside the report; the agreement resumes at its page 4, closing the exhibit and the report at once."""
    doc = pymupdf.open()
    for k in (1, 2, 3):
        head = [("SERVICE AGREEMENT", 20, True, True, 90)] if k == 1 else []
        _page(doc, head + _body(PLUMBING, 130, 14, seed=k, lowercase_start=(k > 1)), footer=f"Page {k} of 8",
              header="Service Agreement with Example Owners Association")
    for k in (1, 2, 3):                                                              # the report inside
        head = [("ANNUAL REPORT", 20, True, True, 90), ("To: the Board", 11, False, False, 120)] if k == 1 else []
        _page(doc, head + _body(GARDEN, 150, 13, seed=k, lowercase_start=(k > 1)), footer=f"Page {k} of 3",
              header="Annual Report of the Grounds Committee")
    _page(doc, [("EXHIBIT A", 18, True, True, 90), ("Schedule of covered items", 12, False, True, 118)]
          + _body(BILLING, 160, 10, seed=2))                                           # the exhibit inside the report
    for k in (4, 5, 6, 7, 8):                                                        # the agreement resumes
        _page(doc, _body(PLUMBING, 130, 14, seed=k, lowercase_start=True), footer=f"Page {k} of 8",
              header="Service Agreement with Example Owners Association")
    _page(doc, [("INVOICE", 22, True, True, 80), ("Bill To:  Example Owners Association", 11, False, False, 130)]
          + _body(BILLING, 190, 10, seed=5))                                           # a new top-level document
    path = tmp_path / "nested.pdf"
    doc.save(path)
    return path


def test_a_document_inside_a_document_is_a_child_and_the_outer_resumes_after_it(nested):
    pages, toc = task.read_pages(nested)
    seg = task.segment_pages(pages, toc=toc)
    keys = {s.key: s for s in seg.segments}
    assert list(keys) == ["s1", "s1.1", "s1.1.1", "s2"]
    outer, report, exhibit, invoice = keys["s1"], keys["s1.1"], keys["s1.1.1"], keys["s2"]
    assert outer.pages == (1, 12) and outer.runs == ((1, 3), (8, 12)) and outer.parent == ""
    assert report.pages == (4, 7) and report.parent == "s1" and report.runs == ((4, 6),)
    assert exhibit.pages == (7, 7) and exhibit.parent == "s1.1" and exhibit.role == "exhibit" and exhibit.label == "Exhibit A"
    assert exhibit.title == "Schedule of covered items" and "Ex. A" in exhibit.aliases and exhibit.names[0] == "Exhibit A"
    assert invoice.pages == (13, 13) and invoice.parent == ""
    assert seg.segment_at(5).key == "s1.1" and seg.segment_at(9).key == "s1" and seg.segment_at(7).key == "s1.1.1"
    assert [s.key for s in seg.chain_at(7)] == ["s1", "s1.1", "s1.1.1"]
    assert [s.key for s in seg.children_of("s1")] == ["s1.1"] and [s.key for s in seg.ancestors_of("s1.1.1")] == ["s1.1", "s1"]
    assert seg.path("s1.1.1") == ["s1", "s1.1", "s1.1.1"]


def test_a_page_can_close_two_levels_at_once_and_the_move_says_what_decided_it(nested):
    pages, toc = task.read_pages(nested)
    seg = task.segment_pages(pages, toc=toc)
    kinds = [(m.page, m.kind.value, m.segment) for m in seg.moves]
    assert kinds == [(1, "first", "s1"), (4, "push", "s1.1"), (7, "push", "s1.1.1"), (8, "pop", "s1"), (13, "new", "s2")]
    pop = next(m for m in seg.moves if m.kind is ds.MoveKind.POP)
    assert pop.closed == ("s1.1.1", "s1.1")                                  # the exhibit and the report, both
    assert any("page 4 follows 3" in s for s in pop.signals) and any("header returns" in s for s in pop.signals)
    push = next(m for m in seg.moves if m.page == 4)
    assert any("still at page 3 of 8" in s for s in push.signals) and any("page-one" in s for s in push.signals)
    assert next(m for m in seg.moves if m.page == 7).signals[0] == "exhibit label Exhibit A"


def test_the_vision_model_is_asked_each_move_as_a_closed_choice_against_the_stack(nested):
    import math

    pages, toc = task.read_pages(nested)
    seg = task.segment_pages(pages, toc=toc)
    chain = ds.open_chain(seg.segments, 7)                                     # the exhibit inside the report inside the agreement
    assert [s.key for s in chain] == ["s1", "s1.1", "s1.1.1"]
    choices = ds.move_choices(chain)
    assert list(choices) == ["A", "B", "C", "D", "E"]
    assert "innermost open document" in choices["A"] and "inside" in choices["B"] and "top-level" in choices["C"]
    assert "Annual Report" in choices["D"] and "Service Agreement" in choices["E"].title() or "SERVICE AGREEMENT" in choices["E"]
    letters = {m.page: ds.move_letter(m, ds.open_chain(seg.segments, p)) for m, p in
               ((m, {4: 3, 7: 6, 8: 7, 13: 12}.get(m.page)) for m in seg.moves if m.page != 1)}
    assert letters == {4: "B", 7: "B", 8: "E", 13: "C"}               # the pop at page 8 goes back to the OUTER-most open document

    sent = []

    def fetch(url, body):
        sent.append(body)
        return {"logprobs": [{"top_logprobs": [{"token": "E", "logprob": math.log(0.7)}, {"token": " D", "logprob": math.log(0.2)},
                                                {"token": "Z", "logprob": math.log(0.1)}]}]}

    reader = task.OllamaPageReader(fetch=fetch)
    got = reader.move_probs("CUR", "PREV", choices)
    assert got["E"] == pytest.approx(0.7 / 0.9) and got["D"] == pytest.approx(0.2 / 0.9) and got["A"] == 0.0
    assert sent[0]["messages"][0]["images"] == ["PREV", "CUR"] and "E) it goes back to the outer document" in sent[0]["messages"][0]["content"]
    assert task.OllamaPageReader(fetch=lambda u, b: {"logprobs": [{"top_logprobs": []}]}).move_probs("a", "b", choices) is None


def test_the_models_reading_of_each_move_makes_it_likely_where_it_agrees(nested):
    pages, toc = task.read_pages(nested)
    seg = task.segment_pages(pages, toc=toc)

    # the model agrees with the rules everywhere but the exhibit's push, where it says "continue"
    probs = {4: {"A": 0.05, "B": 0.9, "C": 0.03, "D": 0.02}, 7: {"A": 0.8, "B": 0.1, "C": 0.05, "D": 0.03, "E": 0.02},
             8: {"A": 0.1, "B": 0.0, "C": 0.1, "D": 0.1, "E": 0.7}, 13: {"A": 0.0, "B": 0.0, "C": 0.9, "D": 0.1, "E": 0.0}}
    task.attach_moves(seg, probs)
    by_page = {m.page: m for m in seg.moves}
    assert by_page[4].tier is ds.Tier.LIKELY and by_page[8].tier is ds.Tier.LIKELY and by_page[13].tier is ds.Tier.LIKELY
    assert by_page[7].tier is ds.Tier.SUGGESTED and by_page[7].model["A"] == 0.8      # the readers disagree: a person looks
    assert ds.Reader.MODEL in by_page[8].readers and by_page[1].model is None


def test_read_moves_asks_every_move_but_the_first_page(nested):
    pages, toc = task.read_pages(nested)
    seg = task.segment_pages(pages, toc=toc)
    asked = []

    class Fake:
        dpi = 40

        def move_probs(self, png, before, choices):
            asked.append(list(choices))
            return {k: 1.0 / len(choices) for k in choices}

    got = task.read_moves(nested, pages, seg.segments, seg.moves, Fake())
    assert sorted(got) == [4, 7, 8, 13] and len(asked) == 4
    assert asked[0] == ["A", "B", "C"] and asked[2] == ["A", "B", "C", "D", "E"]         # page 8 has two outer documents to go back to


def _hand(n, lines, footer="", header=""):
    out = [Line(t, y, y + 0.02, 0.1, 0.9, size, bold) for t, size, bold, y in lines]
    if footer:
        out.append(Line(footer, 0.95, 0.97, 0.45, 0.55, 9))
    if header:
        out.insert(0, Line(header, 0.04, 0.06, 0.1, 0.9, 9))
    return build_page(n, 612, 792, out)


def _words(ws, k):
    return [(" ".join(ws[(k + j) % len(ws)] for j in range(8)), 11, False, 0.2 + 0.03 * i) for i in range(10)]


def test_a_document_closed_between_the_pages_of_another_is_inside_it_even_when_read_as_a_sibling():
    head = "Operating Agreement of the Association"
    pages = [_hand(1, [("OPERATING AGREEMENT", 20, True, 0.12), *_words(PLUMBING, 1)], "- 1 -", head),
             _hand(2, _words(PLUMBING, 2), "- 2 -", head),
             _hand(3, [("INVOICE", 22, True, 0.1), ("Bill To:  Example Owners Association", 11, False, 0.15), *_words(BILLING, 3)]),
             _hand(4, _words(PLUMBING, 4), "- 3 -", head),
             _hand(5, _words(PLUMBING, 5), "- 4 -", head)]
    boundaries = decide(pages, rule_scores=score_pages(pages))
    segs, moves = ds.walk_segments(pages, boundaries)
    assert [(s.key, s.pages, s.parent) for s in segs] == [("s1", (1, 5), ""), ("s1.1", (3, 3), "s1")]
    assert segs[0].runs == ((1, 2), (4, 5))
    assert [(m.page, m.kind.value) for m in moves] == [(1, "first"), (3, "new"), (4, "pop")]


def test_a_document_that_does_not_come_back_stays_a_sibling():
    head = "Operating Agreement of the Association"
    pages = [_hand(1, [("OPERATING AGREEMENT", 20, True, 0.12), *_words(PLUMBING, 1)], "- 1 -", head),
             _hand(2, _words(PLUMBING, 2), "- 2 -", head),
             _hand(3, [("INVOICE", 22, True, 0.1), ("Bill To:  Example Owners Association", 11, False, 0.15), *_words(BILLING, 3)])]
    segs, _ = ds.walk_segments(pages, decide(pages, rule_scores=score_pages(pages)))
    assert [(s.key, s.pages, s.parent) for s in segs] == [("s1", (1, 2), ""), ("s2", (3, 3), "")]


def test_an_exhibit_is_a_child_of_the_document_it_follows_and_the_next_document_is_a_sibling(tmp_path):
    doc = pymupdf.open()
    for k in (1, 2):
        head = [("BYLAWS OF THE ASSOCIATION", 20, True, True, 90)] if k == 1 else []
        _page(doc, head + _body(RULES, 130, 14, seed=k, lowercase_start=(k > 1)), footer=f"Page {k} of 2")
    for letter in "AB":
        _page(doc, [(f"EXHIBIT {letter}", 18, True, True, 90), (f"Notice number {letter} to owners", 12, False, True, 118)]
              + _body(BILLING, 160, 8, seed=ord(letter)))
    _page(doc, [("GRANT DEED", 22, True, True, 90), ("RECORDING REQUESTED BY", 10, False, False, 40)] + _body(LEGAL, 150, 12))
    path = tmp_path / "exhibits.pdf"
    doc.save(path)
    pages, toc = task.read_pages(path)
    seg = task.segment_pages(pages, toc=toc)
    assert [(s.key, s.pages, s.parent, s.label) for s in seg.segments] == [
        ("s1", (1, 4), "", ""), ("s1.1", (3, 3), "s1", "Exhibit A"), ("s1.2", (4, 4), "s1", "Exhibit B"), ("s2", (5, 5), "", "")]
    assert [s.role for s in seg.segments] == ["document", "exhibit", "exhibit", "document"]


def test_a_nested_segment_is_addressed_by_its_path_and_its_pages_stay_absolute(nested):
    assert address("x1", segment="s1.1.1") == "library:x1#seg=s1/s1.1/s1.1.1" and address("x1", segment="s2") == "library:x1#seg=s2"
    parsed = parse_address("library:x1#seg=s1/s1.1")
    assert parsed.segment == "s1.1" and str(parsed) == "library:x1#seg=s1/s1.1"
    assert parse_address("library:x1#seg=s1.1").segment == "s1.1"
    pages, toc = task.read_pages(nested)
    seg = task.segment_pages(pages, toc=toc, doc_id="x1")
    assert resolve(seg, "library:x1#seg=s1/s1.1") == (4, 7) and resolve(seg, "library:x1#seg=s1") == (1, 12)
    again = Segmentation.from_dict(json.loads(json.dumps(seg.to_dict())))
    assert [(s.key, s.parent, s.runs) for s in again.segments] == [(s.key, s.parent, s.runs) for s in seg.segments]
    assert [(m.page, m.kind, m.closed) for m in again.moves] == [(m.page, m.kind, m.closed) for m in seg.moves]


def test_a_part_belongs_to_the_innermost_document_and_a_nested_exhibit_is_a_child(tmp_path):
    doc = pymupdf.open()
    _page(doc, [("OWNER'S MANUAL", 24, True, True, 300), ("Example Owners Association", 14, False, True, 330)],
          footer="Page 1 of 5")
    _page(doc, [("Rules and Regulations", 20, True, False, 90)] + _body(RULES, 130, 14, seed=7), footer="Page 2 of 5")
    _page(doc, _body(RULES, 90, 14, seed=8, lowercase_start=True), footer="Page 3 of 5")
    _page(doc, [("EXHIBIT A", 18, True, True, 90), ("Parking permit application", 12, False, True, 118),
                ("HOME IMPROVEMENT REQUEST APPLICATION", 14, True, True, 150)] + _body(GARDEN, 180, 8, seed=1))
    _page(doc, _body(RULES, 90, 14, seed=9, lowercase_start=True), footer="Page 4 of 5")
    path = tmp_path / "manual-with-exhibit.pdf"
    doc.save(path)
    pages, toc = task.read_pages(path)
    seg = task.segment_pages(pages, toc=toc, doc_id="x1")
    exhibit = next(s for s in seg.segments if s.role == "exhibit")
    assert exhibit.parent == "s1" and exhibit.pages == (4, 4)
    rules = next(p for p in seg.parts if p.kind is PartKind.RULES)
    assert rules.document == "s1" and rules.book == "rules" and rules.label.lower().startswith("rules") and rules.through == ""
    inner = [p for p in seg.parts if p.segment == exhibit.key]
    assert all(exhibit.start <= p.start <= exhibit.end for p in inner)         # a part inside the exhibit is the exhibit's
    assert not any(p.segment == "s1" and p.start == exhibit.start for p in seg.parts)

    # What citation scoping reads: a part's document is its innermost document; a labeled exhibit is a child of its own.
    from jason.community.scoping import Part as ScopingPart

    parts = ds.scoping_parts(seg, document=lambda key: f"x1:{key}")
    assert all(isinstance(p, ScopingPart) for p in parts)
    rules_row = next(p for p in parts if p.book == "rules")
    assert rules_row.document == "x1:s1" and rules_row.label.lower().startswith("rules") and rules_row.through == ""
    exhibit_row = next(p for p in parts if p.document == f"x1:{exhibit.key}")
    assert exhibit_row.label == "Exhibit A" and "Ex. A" in exhibit_row.aliases and exhibit_row.names[0] == "Exhibit A"
