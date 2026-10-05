"""Segmentation: a file split into documents, a document into parts. Made-up PDFs built with PyMuPDF and mocked models, so
nothing here needs Ollama, a profile's data, or a real scan."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import pytest

from jason.community import document_segments as ds
from jason.community.document_segments import (
    Line, Part, PartKind, Reader, Segment, Segmentation, Tier, address, build_page, decide, find_parts, page_cues,
    parse_address, part_span, read_date, read_parties, resolve, score_pages, slug)
from jason.tasks import segments as task

pymupdf = pytest.importorskip("pymupdf")

PLUMBING = "pipe valve faucet drain leak copper solder fixture water heater trap flange".split()
GARDEN = "lawn shrub mulch irrigation sprinkler trim prune sod soil planter hedge turf".split()
LEGAL = "grantor grantee parcel easement covenant lien recorded instrument conveys premises".split()
BILLING = "quantity amount rate labor materials subtotal tax remit balance payment net".split()
RULES = "owner resident vehicle parking guest pet noise trash balcony common area board".split()


def _filler(words: list[str], n: int, seed: int = 0, lowercase_start: bool = False) -> list[str]:
    lines = []
    for i in range(n):
        pick = [words[(seed + i * 3 + j * 5) % len(words)] for j in range(9)]
        text = " ".join(pick)
        lines.append(text if (lowercase_start or i) else text.capitalize())
    return lines


def _page(doc, lines, *, footer: str = "", header: str = ""):
    """lines: (text, size, bold, centered, y)."""
    page = doc.new_page(width=612, height=792)
    for text, size, bold, centered, y in lines:
        font = "hebo" if bold else "helv"
        width = pymupdf.get_text_length(text, fontname=font, fontsize=size)
        x = (612 - width) / 2 if centered else 72
        page.insert_text((x, y), text, fontsize=size, fontname=font)
    if footer:
        page.insert_text((250, 770), footer, fontsize=9)
    if header:
        page.insert_text((72, 30), header, fontsize=9)
    return page


def _body(words, y0=200, n=12, seed=0, lowercase_start=False):
    return [(t, 11, False, False, y0 + 15 * i) for i, t in enumerate(_filler(words, n, seed, lowercase_start))]


@pytest.fixture()
def combined(tmp_path) -> Path:
    """A letter (2 pages), an agreement (3 pages, "Page k of 3"), a blank back, an invoice, a recorded deed (2 pages)."""
    doc = pymupdf.open()
    _page(doc, [("Mill Road Landscaping", 14, True, True, 60), ("(555) 010-2000   office@example.test", 9, False, True, 76),
                ("October 4, 2026", 11, False, False, 110), ("Dear Board Members,", 11, False, False, 135)]
          + _body(GARDEN, 170, 12))
    _page(doc, _body(GARDEN, 90, 14, seed=2, lowercase_start=True))
    for k in (1, 2, 3):
        head = [("SERVICE AGREEMENT", 20, True, True, 90)] if k == 1 else []
        _page(doc, head + _body(PLUMBING, 130, 14, seed=k, lowercase_start=(k > 1)), footer=f"Page {k} of 3")
    doc.new_page(width=612, height=792)                                    # a blank back
    _page(doc, [("INVOICE", 22, True, True, 80), ("Bill To:  Example Owners Association", 11, False, False, 130),
                ("Date: 11/02/2026", 11, False, False, 148)] + _body(BILLING, 190, 10))
    _page(doc, [("RECORDING REQUESTED BY", 10, False, False, 50), ("AND WHEN RECORDED MAIL TO", 10, False, False, 64),
                ("GRANT DEED", 20, True, True, 120)] + _body(LEGAL, 170, 12))
    _page(doc, _body(LEGAL, 90, 14, seed=4, lowercase_start=True))
    path = tmp_path / "combined.pdf"
    doc.save(path)
    return path


@pytest.fixture()
def manual(tmp_path) -> Path:
    """A fake owner's manual: cover, contents, a running header on two pages, a rules part, a policy, and a form."""
    doc = pymupdf.open()
    _page(doc, [("OWNER'S MANUAL", 24, True, True, 300), ("Example Owners Association", 14, False, True, 330)])
    _page(doc, [("TABLE OF CONTENTS", 18, True, True, 90)] + [(f"Section number {i} ........ {i + 3}", 11, False, False, 140 + 16 * i) for i in range(10)])
    for k in range(2):
        _page(doc, _body(RULES, 90, 14, seed=k, lowercase_start=True), header="QUESTIONS & ANSWERS")
    _page(doc, [("Rules and Regulations", 20, True, False, 90)] + _body(RULES, 130, 14, seed=7))
    for k in range(2):
        _page(doc, [(f"reference note {6 + k} of the manual, continuing the rules", 11, False, False, 90)]
              + _body(RULES, 110, 14, seed=9 + k, lowercase_start=True))
    _page(doc, [("ASSESSMENT COLLECTION POLICY", 18, True, True, 90)] + _body(BILLING, 130, 12, seed=3))
    _page(doc, [("HOME IMPROVEMENT REQUEST APPLICATION", 16, True, True, 90)] + _body(GARDEN, 130, 12, seed=5))
    doc.set_toc([[1, "Rules and Regulations", 5], [1, "Assessment Collection Policy", 8]])
    path = tmp_path / "manual.pdf"
    doc.save(path)
    return path


def test_the_rule_pass_finds_each_document_in_a_combined_file(combined):
    pages, toc = task.read_pages(combined)
    assert [p.blank for p in pages] == [False, False, False, False, False, True, False, False, False]
    seg = task.segment_pages(pages, toc=toc)
    assert [s.start for s in seg.segments] == [1, 3, 7, 8]
    assert [s.end for s in seg.segments] == [2, 6, 7, 9]
    agreement = seg.segments[1]
    assert agreement.blank_after == 1 and agreement.title == "SERVICE AGREEMENT"
    assert agreement.tier is Tier.SUGGESTED and agreement.readers == (Reader.RULES,)
    assert seg.segments[0].tier is Tier.LIKELY                    # the first page is a start by definition
    assert any("page-one" in c for c in seg.segments[1].basis.split()) or "page-one" in " ".join(seg.candidates[1].cues)
    assert seg.segments[2].date == "2026-11-02" and any("Example Owners Association" in p for p in seg.segments[2].parties)


def test_a_continuation_page_is_not_a_boundary(combined):
    pages, _ = task.read_pages(combined)
    scores = score_pages(pages)
    for n in (2, 4, 5, 9):
        assert scores[n][0] < ds.THRESHOLD, (n, scores[n])
    keys = {k for k, _, _ in scores[4][1]}
    assert "number-continues" in keys and "mid-sentence" in keys


def test_the_source_file_is_never_changed_and_the_reading_is_stored(combined, tmp_path):
    before = hashlib.sha256(combined.read_bytes()).hexdigest()
    data = tmp_path / "data"
    seg = task.segment_file(combined, data_dir=data, write=True)
    assert hashlib.sha256(combined.read_bytes()).hexdigest() == before
    assert seg.id == "sha-" + before[:16] and seg.sha256 == before
    path = task.store_path(data, seg.id)
    assert path == data / "library" / "segments" / f"{seg.id}.json" and path.is_file()
    loaded = task.load(data, seg.id)
    assert [s.pages for s in loaded.segments] == [s.pages for s in seg.segments] and len(loaded.pages) == 9
    assert not task.stale(loaded, combined)
    combined.write_bytes(combined.read_bytes() + b"\n%edited")
    assert task.stale(loaded, combined)
    assert not (data / "library" / "segments" / f"{seg.id}.pdf").exists()


def test_a_stored_reading_is_reused_for_the_same_bytes(combined, tmp_path, monkeypatch):
    data = tmp_path / "data"
    task.segment_file(combined, data_dir=data, write=True)
    monkeypatch.setattr(task, "read_pages", lambda *a, **k: pytest.fail("the pages were read again"))
    again = task.segment_file(combined, data_dir=data, write=False)
    assert len(again.segments) == 4


def test_parts_of_a_manual_are_found_with_anchors_and_books(manual):
    pages, toc = task.read_pages(manual)
    whole = [Segment("s1", 1, 9)]
    parts = find_parts(pages, whole, toc=toc)
    by_kind = {p.kind: p for p in parts}
    assert by_kind[PartKind.COVER].pages == (1, 1)
    assert by_kind[PartKind.CONTENTS].pages == (2, 2)
    rules = by_kind[PartKind.RULES]
    assert rules.pages == (5, 7) and rules.book == "rules" and rules.title.lower().startswith("rules")
    assert rules.end_anchor.lower().startswith("assessment collection policy")
    assert by_kind[PartKind.POLICY].pages == (8, 8) and by_kind[PartKind.FORM].pages == (9, 9)
    guidance = by_kind[PartKind.GUIDANCE]
    assert guidance.title == "QUESTIONS & ANSWERS" and guidance.pages == (3, 4)
    keys = [p.key for p in parts]
    assert len(set(keys)) == len(keys)


def test_a_part_is_found_again_in_any_text_of_the_document(manual):
    pages, toc = task.read_pages(manual)
    parts = find_parts(pages, [Segment("s1", 1, 9)], toc=toc)
    rules = next(p for p in parts if p.kind is PartKind.RULES)
    text = "\n".join(task.page_texts(manual))
    start, end = part_span(rules, text)
    inside = text[start:end]
    assert inside.lower().startswith("rules and regulations") and "ASSESSMENT COLLECTION" not in inside.upper()
    reflowed = " ".join(text.split()).replace("Rules and Regulations", "RULES  AND  REGULATIONS")
    assert part_span(rules, reflowed) is not None               # spacing, punctuation, and case do not matter
    assert part_span(rules, "an unrelated text with no such heading at all") is None    # a miss stays a miss
    assert ds.in_part(rules, 6) and not ds.in_part(rules, 8) and not ds.in_part(rules, None)


def test_a_whole_segment_part_says_nothing_and_a_contents_part_ends_with_its_leaders():
    def page(n, lines, lead=None):
        return build_page(n, 612, 792, [Line(t, 0.2 + 0.03 * i, 0.22 + 0.03 * i, 0.1, 0.9, size, bold) for i, (t, size, bold) in enumerate(lines)])

    leaders = [(f"Article {i} . . . . . . . . . . . {i}", 11, False) for i in range(8)]
    pages = [page(1, [("BYLAWS", 22, True), ("of the Example Owners Association", 12, False)]), page(2, [("TABLE OF CONTENTS", 16, True), *leaders]), page(3, leaders)]
    pages += [page(n, [("Plain words of the document here and there.", 11, False)] * 6) for n in range(4, 12)]
    parts = find_parts(pages, [Segment("s1", 1, 11)])
    kinds = [(p.kind, p.pages) for p in parts]
    assert (PartKind.CONTENTS, (2, 3)) in kinds
    assert any(p.basis == "after contents" and p.pages == (4, 11) for p in parts)
    assert find_parts(pages[:1], [Segment("s1", 1, 1)]) == []


def test_two_readers_agreeing_make_a_boundary_likely(combined):
    pages, _ = task.read_pages(combined)
    scores = score_pages(pages)
    model = {n: 0.1 for n in range(2, 10)} | {3: 0.9, 5: 0.8, 8: 0.95}
    found = {b.page: b for b in decide(pages, rule_scores=scores, model=model)}
    assert found[3].tier is Tier.LIKELY and found[3].readers == (Reader.RULES, Reader.MODEL)
    assert found[5].tier is Tier.SUGGESTED and found[5].readers == (Reader.MODEL,)       # the model alone: a suggestion
    assert found[7].tier is Tier.SUGGESTED and found[7].readers == (Reader.RULES,)       # the rules alone
    agree = {b.page for b in decide(pages, rule_scores=scores, model=model, accept="agree")}
    assert agree == {1, 3, 8}
    only_rules = {b.page for b in decide(pages, rule_scores=scores, model=model, accept="rules")}
    assert only_rules == {1, 3, 7, 8}


def test_the_vision_model_is_scored_from_its_logprobs():
    sent = []

    def fetch(url, body):
        sent.append(body)
        yes = math.log(0.75)
        return {"logprobs": [{"top_logprobs": [{"token": "Y", "logprob": yes}, {"token": " N", "logprob": math.log(0.2)},
                                                {"token": "The", "logprob": math.log(0.05)}]}]}

    reader = task.OllamaPageReader(fetch=fetch)
    assert reader.p_new("AAAA") == pytest.approx(0.75 / 0.95)
    body = sent[0]
    assert body["logprobs"] and body["top_logprobs"] == 10 and body["think"] is False
    assert body["messages"][0]["images"] == ["AAAA"] and body["options"]["num_predict"] == 1
    pair = task.OllamaPageReader(fetch=fetch, pair=True)
    pair.p_new("CURRENT", "BEFORE")
    assert sent[1]["messages"][0]["images"] == ["BEFORE", "CURRENT"]
    silent = task.OllamaPageReader(fetch=lambda url, body: {"logprobs": [{"top_logprobs": [{"token": "x", "logprob": -1}]}]})
    assert silent.p_new("A") is None                           # no Y or N: no reading, not a guess


def test_read_model_asks_every_page_with_words_but_the_first(combined):
    asked = []

    class Fake:
        dpi, pair = 40, False

        def p_new(self, png, before=""):
            asked.append(png)
            return 0.5

    pages, _ = task.read_pages(combined)
    got = task.read_model(combined, pages, Fake())
    assert sorted(got) == [2, 3, 4, 5, 7, 8, 9] and len(asked) == 7      # the blank back and the first page are not asked


def test_an_embedding_change_is_a_cue_and_not_a_boundary_alone(combined):
    class Embedder:
        model = "fake"

        def embed_passages(self, texts):
            vocab = sorted({w for t in texts for w in t.lower().split()})
            out = []
            for t in texts:
                v = [t.lower().split().count(w) for w in vocab]
                norm = math.sqrt(sum(x * x for x in v)) or 1.0
                out.append([x / norm for x in v])
            return out

    pages, _ = task.read_pages(combined)
    cosines = task.read_embeddings(pages, Embedder())
    assert cosines[3] < ds.EMBED_BREAK < cosines[4]
    assert cosines[4] > 0.5 and 6 not in cosines                         # the blank page is not embedded
    with_embedding = score_pages(pages, embeddings=cosines)
    assert any(k == "embedding-change" for k, _, _ in with_embedding[3][1])
    assert not any(k == "embedding-change" for k, _, _ in with_embedding[4][1])


def test_cues_are_a_table_of_rows_and_a_weight_can_be_changed(combined):
    pages, _ = task.read_pages(combined)
    assert {"page-one", "recording-stamp", "mid-sentence", "number-continues", "same-header"} <= set(ds.CUES)
    plain = score_pages(pages)
    quiet = score_pages(pages, weights={"title-block": 0.0, "page-one": 0.0})
    assert quiet[3][0] < plain[3][0] and quiet[3][0] < ds.THRESHOLD


def test_numbering_that_restarts_and_a_changed_total_are_boundaries():
    def page(n, footer):
        return build_page(n, 612, 792, [Line("Some words of a page here that run on.", 0.2, 0.22, 0.1, 0.9, 11),
                                         Line(footer, 0.95, 0.97, 0.4, 0.6, 9)])

    a, b, c, d = page(1, "Page 3 of 9"), page(2, "Page 4 of 9"), page(3, "Page 5 of 12"), page(4, "Page 1 of 2")
    assert [k for k, _, _ in page_cues(a, b)] == ["number-continues", "lexical-flow"]
    assert "numbering-reset" in [k for k, _, _ in page_cues(b, c)]
    assert "page-one" in [k for k, _, _ in page_cues(c, d)]
    assert "one-page-document" in [k for k, _, _ in page_cues(c, page(5, "Page 1 of 1"))]


def test_pleading_line_numbers_are_not_page_numbers():
    margin = [Line(str(i), 0.05 + 0.03 * i, 0.07 + 0.03 * i, 0.03, 0.06, 10) for i in range(1, 29)]
    page = build_page(2, 612, 792, margin + [Line("The words of the filing begin here.", 0.2, 0.22, 0.15, 0.9, 11)])
    assert page.numbered == 28 and ds.label_of(page) is None
    assert all(not ln.text.isdigit() for ln in page.head)


def test_addresses_name_a_page_range_a_segment_or_a_part(combined):
    assert address("1018711") == "library:1018711"
    assert address("1018711", pages=(3, 7)) == "library:1018711#p3-7" and address("1018711", pages=(4, 4)) == "library:1018711#p4"
    assert address("x1", segment="s2") == "library:x1#seg=s2" and address("x1", part="rules") == "library:x1#part=rules"
    for text in ("library:1018711", "library:1018711#p3-7", "library:x1#seg=s2", "library:x1#part=rules-and-regulations"):
        assert str(parse_address(text)) == text
    assert parse_address("library:1018711#p3-7").end == 7 and parse_address("library:1018711#p3").end == 3
    assert parse_address("drive:abc") is None and parse_address("library:x#bogus") is None
    seg = Segmentation("x1", page_count=20, segments=[Segment("s1", 1, 9), Segment("s2", 10, 20)],
                       parts=[Part("rules", "Rules", PartKind.RULES, 12, 18, "Rules")])
    assert resolve(seg, "library:x1#seg=s2") == (10, 20) and resolve(seg, "library:x1#part=rules") == (12, 18)
    assert resolve(seg, "library:x1#p3-7") == (3, 7) and resolve(seg, "library:x1") == (1, 20)
    assert resolve(seg, "library:x1#part=missing") is None and resolve(seg, "library:other#p3") is None
    assert seg.part_at(14).key == "rules" and seg.segment_at(14).key == "s2" and seg.parts_of(kind="rules")[0].key == "rules"
    assert slug("Rules and Regulations", ["rules-and-regulations"]) == "rules-and-regulations-2"


def test_a_segmentation_round_trips_through_json(combined):
    pages, toc = task.read_pages(combined)
    seg = task.segment_pages(pages, toc=toc, model={3: 0.9}, doc_id="x1", sha="abc", name="combined.pdf")
    again = Segmentation.from_dict(json.loads(json.dumps(seg.to_dict())))
    assert [s.to_dict() for s in again.segments] == [s.to_dict() for s in seg.segments]
    assert [b.to_dict() for b in again.candidates] == [b.to_dict() for b in seg.candidates]
    assert again.pages[0].to_dict() == seg.pages[0].to_dict() and again.options["accept"] == "any"


def test_dates_and_parties_are_read_from_the_opening_words():
    assert read_date("Dated this 4th day of October, 2026, at Sacramento") == "2026-10-04"
    assert read_date("Statement date 11/02/2026") == "2026-11-02" and read_date("on 2026-03-09") == "2026-03-09"
    assert read_date("no date here") == "" and read_date("February 31, 2026") == ""
    assert read_parties("This Agreement is made by and between Alpha Services LLC and Example Owners Association, a nonprofit") \
        == ("Alpha Services LLC", "Example Owners Association")
    assert read_parties("nothing to see") == ()


def test_the_kind_chain_tries_the_name_rules_and_then_the_phrase_rules():
    class Community:
        def classify_document(self, name):
            from jason.community.symbols import DocumentKind

            return DocumentKind.INVOICE if "invoice" in name.lower() else None

    classify = task.kind_chain(Community())
    assert classify("Invoice 123", "")[0] == "invoice" and classify("Invoice 123", "")[1].startswith("name rule")
    kind, basis = classify("Untitled", "TREASURER'S REPORT for the month of March")
    assert kind == "treasurer_report" and basis.startswith("phrase rule")
    assert classify("Untitled", "words that say nothing in particular") == ("", "")        # a miss stays a miss


def test_boundary_figures_count_exact_and_near_matches_and_skip_maybe_pages():
    assert task.prf([3, 7, 9], [3, 7, 10])["f1"] == pytest.approx(2 / 3)
    assert task.prf([3, 7, 9], [3, 7, 10], within=1)["f1"] == 1.0
    maybe = task.prf([3, 7, 9, 12], [3, 7], maybe=[12])
    assert maybe["predicted"] == 3 and maybe["precision"] == pytest.approx(2 / 3)       # the maybe page counts neither way
    rank = {n: i for i, n in enumerate([1, 3, 5, 7])}                                    # blank backs between are no distance
    assert task.prf([5], [7], within=1, rank=rank)["tp"] == 1 and task.prf([3], [7], within=1, rank=rank)["tp"] == 0
    parts = [Part("a", "A", PartKind.RULES, 5, 9, "A"), Part("b", "B", PartKind.FORM, 10, 12, "B"), Part("c", "C", PartKind.OTHER, 20, 21, "C")]
    got = task.part_accuracy(parts, [{"title": "a", "start": 5, "end": 9}, {"title": "b", "start": 11, "end": 12}], within=1)
    assert got["found"] == 2 and got["exact"] == 2 and got["extra"] == 1


def test_evaluate_scores_the_rules_the_model_and_both(combined):
    pages, toc = task.read_pages(combined)
    gold = [{"path": str(combined), "split": "dev", "boundaries": [1, 3, 7, 8], "maybe": [], "window": None, "parts": []}]
    out = task.evaluate(gold, lambda f: (pages, toc), variants=("rules", "model", "agree", "union"),
                        model_for=lambda f: {2: 0.2, 3: 0.9, 4: 0.1, 5: 0.1, 7: 0.9, 8: 0.2, 9: 0.1})
    rules = out["variants"]["rules"]["exact"]
    assert rules["precision"] == 1.0 and rules["recall"] == 1.0 and rules["gold"] == 3         # the first page is left out
    assert out["variants"]["model"]["exact"]["recall"] == pytest.approx(2 / 3)
    assert out["variants"]["agree"]["exact"]["precision"] == 1.0
    assert out["variants"]["union"]["exact"]["recall"] == 1.0


def test_the_command_prints_each_segment_with_its_address(combined, tmp_path, monkeypatch, capsys):
    import argparse

    from jason.commands import segments as command

    monkeypatch.setattr(command, "_data_dir", lambda args: tmp_path / "data")
    args = argparse.Namespace(file=str(combined), id="", list=False, show="", write=True, again=False, model="", pair=False,
                              dpi=72, embed=False, ocr=False, accept="any", json=False, env=None)
    assert command.cmd_segments(args) == 0
    out = capsys.readouterr().out
    assert "4 documents" in out and "#seg=s2" in out and "#p3-6" in out and "stored at" in out
    ident = task.file_id(combined)
    args2 = argparse.Namespace(file="", id="", list=False, show=ident, write=False)
    assert command.cmd_segments(args2) == 0 and ident in capsys.readouterr().out
    assert command.cmd_segments(argparse.Namespace(file="", id="", list=True, show="")) == 0
    assert command.cmd_segments(argparse.Namespace(file="", id="", list=False, show="nothing")) == 1


def test_the_command_is_registered():
    from jason.commands import MODULES

    assert "segments" in MODULES


def test_parts_are_found_across_the_store_by_book_and_a_passage_is_tagged_with_its_part(manual, tmp_path):
    data = tmp_path / "data"
    seg = task.segment_file(manual, doc_id="1018711", data_dir=data, write=True)
    found = task.parts_in_store(data, book="rules")
    assert found and all(p.book == "rules" and s.id == "1018711" for s, p in found)
    rules = found[0][1]
    texts = task.page_texts(manual)
    assert task.text_of_pages(manual, rules.start, rules.start).lower().startswith("rules and regulations")
    words = " ".join(texts[5].split()[:14])                         # the second page of the rules, as another reading's passage
    assert words.startswith("reference note 6")
    page, segment_key, part_key = ds.locate(seg, words, texts)
    assert page == 6 and part_key == rules.key
    assert ds.locate(seg, "words that no page of this file holds at all anywhere", texts) == (None, "", "")
    assert task.parts_in_store(data, book="coll") == []
