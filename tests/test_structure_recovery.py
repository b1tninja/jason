"""Structure recovery: the gold of a Doc, the degraded variants, the clue rows that read a PDF's headings, and the score.

Every document is made up here (invented headings and sentences) and drawn with PyMuPDF; no real document is read. The
image-only cases need the Tesseract tool and are skipped without it.
"""

from __future__ import annotations

import pymupdf
import pytest

from jason.community import structure_gold as sg
from jason.community import structure_pdf as sp
from jason.community import structure_score as sc
from jason.community import structure_variants as sv
from jason.community.structure_numbering import NumberKind, SequenceCheck, fold_number, is_contents_page, split_number


def drawn(tmp_path, numbering="dotted", style=None, **kw):
    gold = sg.made_up(numbering=numbering, **{"articles": 4, "sections": 3, **kw})
    pdf = sg.render_pdf(gold, tmp_path / "source.pdf", style or sg.RenderStyle.sized())
    sg.pair_pages(gold, pdf)
    return gold, pdf


def record_of(pdf, name="clean"):
    n = pymupdf.open(pdf).page_count
    return sv.VariantRecord(name, str(pdf), 0, False, [], {p: p for p in range(1, n + 1)}, pages=n)


def recovery(pdf, **kw):
    return sp.outline_from_pdf(pdf, key="x", **kw)


def read(pdf, clues=None, min_score=sp.MIN_SCORE, toc=True):
    with pymupdf.open(pdf) as doc:
        lines, sources = sp.extract_lines(doc)
        return sp.recover(lines, doc.page_count, toc=doc.get_toc(simple=True) if toc else (), clues=clues,
                          min_score=min_score, sources=sources)


# --- the numbering grammar -------------------------------------------------------------------------------------------


@pytest.mark.parametrize("line, kind, printed, rest", [
    ("ARTICLE IV PARKING", NumberKind.WORD, "ARTICLE IV", "PARKING"),
    ("Section 3.2 Noise", NumberKind.WORD, "Section 3.2", "Noise"),
    ("B-12. Gates", NumberKind.DASH, "B-12.", "Gates"),
    ("1.1 Definitions", NumberKind.DOTTED, "1.1", "Definitions"),
    ("12. Fines", NumberKind.DOTTED, "12.", "Fines"),
    ("A. General", NumberKind.CAPITAL, "A.", "General"),
    ("(a) Pets", NumberKind.PAREN, "(a)", "Pets"),
    ("IV. Records", NumberKind.ROMAN, "IV.", "Records"),
])
def test_split_number_reads_each_shape(line, kind, printed, rest):
    n = split_number(line)
    assert (n.kind, n.printed, n.rest) == (kind, printed, rest)


def test_a_line_without_a_number_has_none():
    assert split_number("The gate shall be kept closed") is None
    assert fold_number("8.5.") == fold_number("8.5") and fold_number("(a)") != fold_number("a")


def test_sequence_check_keeps_gaps_repeats_and_disorder_as_findings():
    check = SequenceCheck()
    states = [check.see(split_number(t)) for t in ("1.1 A", "1.2 B", "1.4 C", "1.4 D", "1.3 E", "2.1 F")]
    assert states == ["first", "next", "gap", "repeat", "out of order", "first"]
    assert [f.kind for f in check.findings] == ["gap", "repeat", "out of order"]
    assert check.findings[0].printed == "1.4" and check.findings[0].after == "1.2"


def test_sequence_check_follows_a_lettered_rule_family():
    check = SequenceCheck()
    assert [check.see(split_number(t)) for t in ("B-11. X", "B-12. Y", "B-14. Z")] == ["first", "next", "gap"]


def test_a_contents_page_is_found_by_its_leaders_or_its_title():
    assert is_contents_page(["Contents", "Parking ..... 3", "Noise ..... 4", "Pets ..... 5"])
    assert not is_contents_page(["The gate shall be kept closed.", "Notice is given by mail."])
    assert is_contents_page(["TABLE OF CONTENTS", "1. Parking", "2. Noise", "3. Pets"])    # OCR drops the leaders


# --- the gold of a Doc -----------------------------------------------------------------------------------------------


def _para(text, style="NORMAL_TEXT", bold=False, size=None, bullet=None, page_break=False):
    elements = [{"textRun": {"content": text + "\n", "textStyle": {**({"bold": True} if bold else {}),
                                                                  **({"fontSize": {"magnitude": size}} if size else {})}}}]
    if page_break:
        elements.insert(0, {"pageBreak": {}})
    p = {"paragraphStyle": {"namedStyleType": style}, "elements": elements}
    if bullet:
        p["bullet"] = bullet
    return {"paragraph": p}


def made_up_doc():
    levels = [{"glyphType": "DECIMAL", "glyphFormat": "%0."}, {"glyphType": "DECIMAL", "glyphFormat": "%0.%1"},
              {"glyphType": "ALPHA", "glyphFormat": "(%2)"}]
    body = [_para("SAMPLE RULES", "TITLE"),
            _para("Parking", "HEADING_1", bullet={"listId": "L1", "nestingLevel": 0}),
            _para("Cars are kept in the lot."),
            _para("Guests", "HEADING_2", bullet={"listId": "L1", "nestingLevel": 1}),
            _para("Guest cars are kept near the gate.", bullet={"listId": "L1", "nestingLevel": 2}),
            _para("Noise", "HEADING_1", bullet={"listId": "L1", "nestingLevel": 0}, page_break=True),
            {"table": {"tableRows": [{"tableCells": [{"content": [_para("cell one")]}, {"content": [_para("cell two")]}]}]}},
            _para("ARTICLE 3 PETS", "HEADING_1", size=18.0, bold=True)]
    return {"documentId": "doc1", "title": "Sample Rules", "revisionId": "r1",
            "body": {"content": body}, "lists": {"L1": {"listProperties": {"nestingLevels": levels}}},
            "headers": {"h1": {"content": [_para("Running header")]}}}


def test_gold_from_a_doc_keeps_levels_numbers_style_and_breaks():
    gold = sg.gold_from_doc(made_up_doc())
    heads = gold.headings()
    assert [(h.level, h.number, h.title) for h in heads] == [
        (0, "", "SAMPLE RULES"), (1, "1.", "Parking"), (2, "1.1", "Guests"), (1, "2.", "Noise"), (1, "ARTICLE 3", "PETS")]
    assert heads[4].own_number and heads[4].bold and heads[4].size == 18.0 and heads[4].caps
    assert heads[1].list_id == "L1" and heads[2].nesting == 1
    item = next(n for n in gold.nodes if n.kind == "list_item")
    assert item.number == "(a)"
    kinds = [n.kind for n in gold.nodes]
    assert kinds.count("page_break") == 1 and kinds.count("table") == 1 and kinds.count("header") == 1
    assert gold.nodes[heads[2].parent] is heads[1] and gold.nodes[heads[1].parent] is heads[0] and heads[0].parent == -1
    assert gold.parts and gold.parts[0]["title"] == "SAMPLE RULES"
    assert gold.text.startswith("SAMPLE RULES") and heads[1].start == gold.text.index("Parking")


def test_gold_from_an_outline_marks_parenthesized_sections_as_list_items():
    from jason.community.outlines import outline_from_text

    out = outline_from_text("ARTICLE 1 Parking\n1.1 Guests\n(a) Cars are kept near the gate\n", key="k", title="K")
    gold = sg.gold_from_outline(out)
    assert [n.kind for n in gold.nodes] == ["heading", "heading", "list_item"]
    assert gold.nodes[1].parent == 0


def test_pairing_finds_each_heading_on_its_page_and_skips_the_contents_page(tmp_path):
    gold, pdf = drawn(tmp_path, style=sg.RenderStyle.sized(toc=True))
    assert all(h.page for h in gold.headings())
    first = gold.headings()[0]
    assert first.page > 1                       # not the contents page that lists it
    assert sg.pair_pages(gold, pdf) == 0 and gold.pages == pymupdf.open(pdf).page_count


# --- the clue rows ---------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("numbering, style", [("dotted", sg.RenderStyle.sized()), ("article", sg.RenderStyle.sized()),
                                              ("dotted", sg.RenderStyle.flat()), ("rules", sg.RenderStyle.flat())])
def test_headings_are_read_back_in_two_styles(tmp_path, numbering, style):
    gold, pdf = drawn(tmp_path, numbering, style)
    rec = read(pdf)
    s = sc.score(gold, record_of(pdf), rec, samples=50)
    assert s["f1"] == 1.0 and s["level_exact"] == 1.0 and s["number_roundtrip"] == 1.0 and s["parent_correct"] == 1.0
    assert all(n.tier == "likely" for n in rec.nodes)


def test_running_headers_and_page_numbers_are_taken_out_and_kept(tmp_path):
    gold, pdf = drawn(tmp_path)
    rec = read(pdf)
    assert "Sample Association Rules" not in " ".join(n.text for n in rec.nodes)
    assert rec.labels and all(v.isdigit() for v in rec.labels.values())
    assert any("Sample Association Rules" in t for ts in rec.running.values() for t in ts)
    s = sc.score(gold, record_of(pdf), rec, labels=rec.labels, samples=20)
    assert s["page_numbers"] == 1.0


def test_one_family_of_clues_is_suggested_and_two_are_likely(tmp_path):
    gold, pdf = drawn(tmp_path, style=sg.RenderStyle.sized())
    typography = read(pdf, clues=["size", "weight", "caps"], toc=False)
    assert typography.nodes and {n.tier for n in typography.nodes} == {"suggested"}
    assert all(set(n.families) == {"typography"} for n in typography.nodes)
    both = read(pdf, clues=["size", "numbering", "sequence"], toc=False)
    assert any(n.tier == "likely" for n in both.nodes)


def test_a_clue_left_out_changes_the_score_by_what_it_was_worth(tmp_path):
    gold, pdf = drawn(tmp_path, "dotted", sg.RenderStyle.flat())
    record = record_of(pdf)
    f = {}
    for cfg in sc.ablation_configs():
        rec = read(pdf, clues=cfg["clues"], min_score=cfg["min_score"], toc=False)
        f[cfg["name"]] = sc.score(gold, record, rec, samples=20)["f1"]
    assert f["all"] == 1.0
    assert f["only weight"] < f["all"]                    # a weak clue alone misses headings
    worth = sc.worth(f)
    assert worth["numbering"]["loss"] == pytest.approx(f["all"] - f["without numbering"])
    assert worth["numbering"]["alone"] == f["only numbering"]


def test_the_contents_page_is_a_clue_and_a_check(tmp_path):
    gold, pdf = drawn(tmp_path, style=sg.RenderStyle.sized(toc=True))
    rec = read(pdf, toc=False)
    assert rec.toc["entries"] > 0 and rec.toc["verified"] == rec.toc["entries"]
    assert all("toc" in n.clues for n in rec.nodes if n.level in (1, 2))
    # An entry no heading answers is a finding, not a heading.
    doc = pymupdf.open(pdf)
    doc[0].insert_text((72, 640), "Gutters and Fascia ........ 4", fontsize=10, fontname="tiro")
    doc.save(str(tmp_path / "extra.pdf"))
    rec2 = read(tmp_path / "extra.pdf", toc=False)
    assert rec2.toc["unverified"] == 1
    assert [f["kind"] for f in rec2.findings].count("contents entry with no heading") == 1
    assert "Gutters" not in " ".join(n.text for n in rec2.nodes)


def test_bookmarks_give_levels(tmp_path):
    gold, pdf = drawn(tmp_path, style=sg.RenderStyle.sized(bookmarks=True))
    rec = read(pdf)
    marked = [n for n in rec.nodes if "bookmark" in n.clues]
    assert marked and all(n.level in (1, 2) and n.level_from == "bookmark" for n in marked)


def test_a_gap_in_the_numbers_is_a_finding_and_the_number_stays_as_printed(tmp_path):
    doc = pymupdf.open()
    page = doc.new_page()
    y = 90
    for text, size, font in [("1.1 Parking", 14, "tibo"), ("Cars are kept in the lot by the gate each night.", 11, "tiro"),
                             ("1.2 Noise", 14, "tibo"), ("Music is kept low after the hour posted on the gate.", 11, "tiro"),
                             ("1.4 Pets", 14, "tibo"), ("Dogs are kept on a lead in the common area at all times.", 11, "tiro")]:
        page.insert_text((72, y), text, fontsize=size, fontname=font)
        y += 40
    doc.save(str(tmp_path / "gap.pdf"))
    rec = read(tmp_path / "gap.pdf", toc=False)
    assert [n.number for n in rec.nodes] == ["1.1", "1.2", "1.4"]
    gaps = [f for f in rec.findings if f["kind"] == "numbering gap"]
    assert len(gaps) == 1 and gaps[0]["printed"] == "1.4" and gaps[0]["after"] == "1.2"


def test_outline_from_pdf_returns_the_outline_shape_with_tiers(tmp_path):
    gold, pdf = drawn(tmp_path, "article", sg.RenderStyle.sized(bookmarks=True))
    out = recovery(pdf, title="Sample")
    assert out.sections and len(out.tiers) == len(out.sections) == len(out.pages_of)
    arts = [s for s in out.sections if s.label.startswith("ARTICLE")]
    assert [s.number for s in arts] == ["1", "2", "3", "4"]
    assert out.section("1.2") is not None and out.section_at(out.section("1.2").start).number == "1.2"
    assert out.to_dict()["sections"][0]["title"]


def test_pages_out_of_order_are_read_in_the_order_of_their_printed_numbers(tmp_path):
    gold, pdf = drawn(tmp_path)
    src = pymupdf.open(pdf)
    n = src.page_count
    order = list(range(n))
    order[1], order[2] = order[2], order[1]
    src.select(order)
    src.save(str(tmp_path / "swapped.pdf"))
    with_order = read(tmp_path / "swapped.pdf", toc=False)
    without = read(tmp_path / "swapped.pdf", clues=[c.name for c in sp.CLUES if c.name != "page_order"], toc=False)
    assert any(f["kind"].startswith("pages out of order") for f in with_order.findings)
    assert not any(f["kind"].startswith("pages out of order") for f in without.findings)
    record = sv.VariantRecord("swapped", "x", 0, False, [], {1: 1, 2: 3, 3: 2, **{p: p for p in range(4, n + 1)}}, pages=n)
    a = sc.score(gold, record, with_order, samples=10)
    b = sc.score(gold, record, without, samples=10)
    assert a["parent_correct"] >= b["parent_correct"] and a["f1"] == 1.0


# --- the variants -----------------------------------------------------------------------------------------------------


def test_variants_record_the_page_map(tmp_path):
    gold, pdf = drawn(tmp_path)
    n = pymupdf.open(pdf).page_count
    duplex = sv.make_variant(pdf, "duplex", tmp_path / "v")
    assert duplex.pages == 2 * n and duplex.page_map[2] == 3 and duplex.added[0] == 2 and duplex.image_only
    missing = sv.make_variant(pdf, "missing", tmp_path / "v")
    assert missing.pages == n - 1 and missing.lost == [n // 2 + 1] and missing.page_map[n // 2 + 1] == 0
    shuffle = sv.make_variant(pdf, "shuffle", tmp_path / "v")
    assert shuffle.page_map[1] == 2 and shuffle.page_map[2] == 1
    combined = sv.make_variant(pdf, "combined", tmp_path / "v")
    assert combined.page_map[1] == 3 and combined.extra["host_last"] == n + 2 and combined.pages == n + 3
    assert not combined.image_only and pymupdf.open(tmp_path / "v" / "combined.pdf").page_count == combined.pages
    assert sv.VariantRecord.from_dict(combined.to_dict()).page_map == combined.page_map


def test_a_changed_running_header_is_not_a_heading_and_the_document_inside_a_larger_file_is_scored_in_scope(tmp_path):
    gold, pdf = drawn(tmp_path)
    header = sv.make_variant(pdf, "header", tmp_path / "v")
    rec = read(tmp_path / "v" / "header.pdf", toc=False)
    texts = " ".join(n.text for n in rec.nodes)
    assert "Revised Edition" not in texts and "Sample Association Rules" not in texts and header.extra["header_was"]
    assert sc.score(gold, header, rec, samples=10)["f1"] == 1.0
    combined = sv.make_variant(pdf, "combined", tmp_path / "v")
    rec = read(tmp_path / "v" / "combined.pdf", toc=False)
    s = sc.score(gold, combined, rec, samples=10)
    assert s["recall"] == 1.0 and s["bleed"] >= 1               # the filler agreement's own clauses are outside the scope
    assert s["precision"] == 1.0


def test_stencil_substitutes_characters_and_the_image_stays_bilevel(tmp_path):
    import numpy as np

    gold, pdf = drawn(tmp_path, articles=1, sections=1)
    gray = sv.draw(pymupdf.open(pdf)[0], 150)
    out = sv.stencil(gray)
    assert set(np.unique(out)) <= {0, 255} and out.shape == gray.shape
    assert (out == 0).sum() > 0.5 * (prep_ink(gray))


def prep_ink(gray):
    from jason.community import page_prep as prep

    return int((prep.binarize_global(gray) == 0).sum())


# --- the score --------------------------------------------------------------------------------------------------------


def test_scoring_arithmetic_on_a_recovery_made_by_hand():
    gold = sg.Gold("g", nodes=[sg.GoldNode("heading", text="Parking", title="Parking", level=1, number="1.", page=1),
                               sg.GoldNode("heading", text="Noise", title="Noise", level=2, number="1.1", page=1, parent=0),
                               sg.GoldNode("heading", text="Pets", title="Pets", level=1, number="2.", page=2)])
    record = sv.VariantRecord("v", "x", 0, False, [], {1: 1, 2: 2}, pages=2)

    def node(text, level, page, number="", parent=-1, tier="likely"):
        return sp.PNode(text, number, text, level, page, 0, [], [], tier, 1.0, parent=parent)

    rec = sp.Recovery(nodes=[node("1. Parking", 1, 1, "1."), node("1.1 Noise", 1, 1, "1.1", -1),
                             node("Fences", 1, 2, tier="suggested")], pages=2)
    s = sc.score(gold, record, rec, samples=50)
    assert (s["matched"], s["findable"], s["recovered"]) == (2, 3, 3)
    assert s["precision"] == pytest.approx(2 / 3) and s["recall"] == pytest.approx(2 / 3)
    assert s["f1"] == pytest.approx(2 / 3) and s["f1_lo"] <= s["f1"] <= s["f1_hi"]
    assert s["level_exact"] == 0.5 and s["level_within1"] == 1.0
    assert s["number_roundtrip"] == 1.0 and s["numbered"] == 2
    assert s["parent_correct"] == 0.5                         # Noise hangs from nothing, not from Parking
    assert s["likely_precision"] == 1.0 and s["suggested_precision"] == 0.0


def test_a_heading_on_a_lost_page_cannot_be_found_and_does_not_count_against_recall():
    gold = sg.Gold("g", nodes=[sg.GoldNode("heading", text="Parking", title="Parking", level=1, page=1),
                               sg.GoldNode("heading", text="Pets", title="Pets", level=1, page=2)])
    record = sv.VariantRecord("v", "x", 0, False, [], {1: 1, 2: 0}, pages=1, lost=[2])
    rec = sp.Recovery(nodes=[sp.PNode("Parking", "", "Parking", 1, 1, 0, [], [], "likely", 1.0)], pages=1)
    s = sc.score(gold, record, rec, samples=10)
    assert s["findable"] == 1 and s["recall"] == 1.0 and s["recall_all"] == 0.5


def test_ablation_configs_leave_each_clue_out_and_alone_and_add_by_cost():
    configs = sc.ablation_configs()
    names = [c["name"] for c in configs]
    assert names[0] == "all" and "without size" in names and "only numbering" in names
    assert "only page_order" not in names
    assert configs[names.index("only weight")]["min_score"] == sp.BY_NAME["weight"].weight
    cost = [c for c in configs if c["name"].startswith("cost order")]
    assert cost[0]["clues"] == ["bookmark"] and len(cost[-1]["clues"]) == sum(1 for c in sp.CLUES if c.votes)
    assert sc.bootstrap_f1([1, 1, 1], [1, 1, 1]) == (1.0, 1.0)
    assert sc.f1(0.5, 1.0) == pytest.approx(2 / 3)


# --- an image-only variant --------------------------------------------------------------------------------------------


tesseract = pytest.mark.skipif(not __import__("jason.community.ocr", fromlist=["TesseractCli"]).TesseractCli.available(),
                               reason="the Tesseract tool is not installed")


@tesseract
def test_the_headings_of_an_image_only_page_come_from_the_height_of_the_ocr_words(tmp_path):
    gold, pdf = drawn(tmp_path, "dotted", sg.RenderStyle.sized(), articles=2, sections=2)
    image = sv.make_variant(pdf, "image300", tmp_path / "v")
    with pymupdf.open(tmp_path / "v" / image.file) as doc:
        assert not doc[0].get_text().strip()                 # no text layer is left
        lines, sources = sp.extract_lines(doc, words_of=sp.ocr_words_of(300))
        rec = sp.recover(lines, doc.page_count, sources=sources)
    assert set(sources) == {"ocr"} and all(n.source == "ocr" for n in rec.nodes)
    s = sc.score(gold, image, rec, samples=20)
    assert s["f1"] >= 0.9 and s["number_roundtrip"] >= 0.9
    assert not any("weight" in n.clues for n in rec.nodes)    # no weight is known from an image


# --- a Word file -------------------------------------------------------------------------------------------------------


def _docx(tmp_path):
    import zipfile

    w = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
    styles = (f'<w:styles {w}><w:style w:styleId="Heading1"><w:name w:val="heading 1"/><w:pPr><w:numPr><w:ilvl w:val="0"/>'
              f'<w:numId w:val="1"/></w:numPr></w:pPr><w:rPr><w:sz w:val="40"/></w:rPr></w:style>'
              f'<w:style w:styleId="Heading2"><w:name w:val="heading 2"/><w:rPr><w:b/><w:sz w:val="28"/></w:rPr></w:style>'
              f'<w:style w:styleId="Title"><w:name w:val="Title"/></w:style></w:styles>')
    numbering = (f'<w:numbering {w}><w:abstractNum w:abstractNumId="7"><w:lvl w:ilvl="0"><w:numFmt w:val="decimal"/>'
                 f'<w:lvlText w:val="%1."/></w:lvl><w:lvl w:ilvl="1"><w:numFmt w:val="lowerLetter"/><w:lvlText w:val="(%2)"/></w:lvl>'
                 f'</w:abstractNum><w:num w:numId="1"><w:abstractNumId w:val="7"/></w:num></w:numbering>')

    def p(text, style="", num=None, extra=""):
        ppr = (f'<w:pStyle w:val="{style}"/>' if style else "") + (
            f'<w:numPr><w:ilvl w:val="{num[1]}"/><w:numId w:val="{num[0]}"/></w:numPr>' if num else "") + extra
        return f"<w:p><w:pPr>{ppr}</w:pPr><w:r><w:t>{text}</w:t></w:r></w:p>"

    body = (p("SAMPLE RULES", "Title") + p("Parking", "Heading1") + p("Cars are kept in the lot.")
            + p("Guests", "Heading2", num=(1, 1)) + p("Noise", "Heading1", extra="<w:pageBreakBefore/>")
            + "<w:tbl><w:tr><w:tc><w:p><w:r><w:t>cell</w:t></w:r></w:p></w:tc></w:tr></w:tbl>")
    path = tmp_path / "sample.docx"
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("word/document.xml", f'<w:document {w}><w:body>{body}</w:body></w:document>')
        z.writestr("word/styles.xml", styles)
        z.writestr("word/numbering.xml", numbering)
        z.writestr("word/header1.xml", f'<w:hdr {w}><w:p><w:r><w:t>Running header</w:t></w:r></w:p></w:hdr>')
    return path


def test_a_word_file_gives_the_same_gold_as_a_doc(tmp_path):
    gold = sg.gold_from_docx(_docx(tmp_path), doc_id="w")
    heads = gold.headings()
    assert [(h.level, h.number, h.title) for h in heads] == [(0, "", "SAMPLE RULES"), (1, "1.", "Parking"),
                                                             (2, "(a)", "Guests"), (1, "2.", "Noise")]
    assert heads[1].size == 20.0 and heads[2].bold and heads[2].size == 14.0
    kinds = [n.kind for n in gold.nodes]
    assert kinds.count("page_break") == 1 and kinds.count("table") == 1 and kinds.count("header") == 1
    assert gold.source == "docx" and [p["title"] for p in gold.parts] == ["SAMPLE RULES"]


def test_a_contents_page_the_body_bears_out_closes_the_list(tmp_path):
    gold, pdf = drawn(tmp_path, style=sg.RenderStyle.sized(toc=True))
    doc = pymupdf.open(pdf)
    doc[2].insert_text((72, 700), "UNLISTED NOTICE", fontsize=16, fontname="tibo")
    doc.save(str(tmp_path / "unlisted.pdf"))
    closed = read(tmp_path / "unlisted.pdf", toc=False)
    assert closed.closed
    extra = [n for n in closed.nodes if n.text == "UNLISTED NOTICE"]
    assert extra and extra[0].tier == "suggested"                 # by typography alone, and the contents does not list it
    assert all(n.tier == "likely" for n in closed.nodes if "toc" in n.clues)
    assert any(f["kind"] == "headings the contents does not list" for f in closed.findings)
    names = [c.name for c in sp.CLUES if c.name != "closed"]
    open_ = read(tmp_path / "unlisted.pdf", clues=names, toc=False)
    assert not open_.closed and [n for n in open_.nodes if n.text == "UNLISTED NOTICE"][0].tier == "likely"     # without the closed list, two families agree
    s = sc.score(gold, record_of(pdf), closed, samples=10)
    assert s["likely_precision"] == 1.0 and s["likely_f1"] == pytest.approx(s["likely_precision"] * 2 * s["likely_recall"]
                                                                              / (s["likely_precision"] + s["likely_recall"]))
