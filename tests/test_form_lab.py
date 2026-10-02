"""The form layout lab: layouts drawn as readable forms, the responder model, the battery, and the search's bookkeeping."""

import pytest

from jason.tasks import form_lab as fl


@pytest.mark.parametrize("style", list(fl.FieldStyle))
def test_every_style_draws_a_form_the_reader_can_lay_out(tmp_path, style):
    from jason.community.form_layout import read_layout

    pdf, drawn = fl.render(fl.Layout(style=style, phone_style=fl.FieldStyle.CHAR_BOXES), tmp_path / "f.pdf")
    layout = read_layout(pdf, fl.LAB_FORM)
    names = {f.name for f in layout.fields}
    assert {"owner-names", "unit-address", "mailing-address", "email", "phone"} <= names
    assert {"delivery.by-mail", "delivery.by-email", "occupancy"} <= names
    assert "phone" in drawn.pitches                                   # its own style: a box for each character
    assert len(layout.anchors) >= 6 and drawn.used > 200
    if style is fl.FieldStyle.CHAR_BOXES:
        rows = {c[1] for c in drawn.cells["mailing-address"]}
        assert len(rows) == 2                                         # a row of square boxes for each line
        assert all(abs((c[2] - c[0]) - (c[3] - c[1])) < 0.01 for c in drawn.cells["owner-names"])


def test_a_heavier_darker_edge_is_noticed_more():
    light = fl.Layout(style=fl.FieldStyle.BOX, weight=0.5, tone=0.6)
    heavy = fl.Layout(style=fl.FieldStyle.BOX, weight=2.5, tone=0.0)
    assert fl.salience(heavy) > fl.salience(light)
    assert fl.AFFORDANCE[fl.FieldStyle.CHAR_BOXES] > fl.AFFORDANCE[fl.FieldStyle.RULE] > fl.AFFORDANCE[fl.FieldStyle.OPEN]


def test_a_layout_round_trips_and_names_only_what_differs():
    lay = fl.Layout(style=fl.FieldStyle.SHADED, height=22.0, email_style=fl.FieldStyle.BOX)
    assert fl.Layout.from_json(lay.as_json()) == lay
    assert fl._short(lay) == "style shaded, height 22.0, email_style box" and fl._short(fl.CURRENT) == "the current form"
    assert lay.style_for("email") is fl.FieldStyle.BOX and lay.style_for("phone") is fl.FieldStyle.SHADED


def test_the_battery_is_repeatable_and_covers_every_responder():
    trials = fl.battery(12, 3)
    assert trials == fl.battery(12, 3)
    assert {t.responder for t in trials} == {w.name for w in fl.WRITERS} | {fl.TYPED}


def test_a_writer_spills_more_outside_an_open_space_than_a_box(tmp_path):
    import random

    from jason.tasks.form_fuzz import Style

    def outside(layout):
        pdf, drawn = fl.render(layout, tmp_path / f"{layout.style.value}.pdf")
        total = fl.Spill()
        for seed in range(12):
            rng = random.Random(seed)
            s = fl.write(pdf, drawn, layout, fl.lab_answers(rng, Style.PLAIN), fl.WRITERS[1], rng,
                         tmp_path / f"w{seed}.pdf")
            total.words, total.outside = total.words + s.words, total.outside + s.outside
        return total.outside / total.words

    assert outside(fl.Layout(style=fl.FieldStyle.OPEN)) > outside(fl.Layout(style=fl.FieldStyle.BOX, weight=1.5))


def test_letters_read_along_their_boxes():
    import numpy as np
    import pymupdf

    from jason.community.form_reader import DPI, read_cells
    from jason.community.ocr import PyMuPdfTesseract

    if not PyMuPdfTesseract.available():
        pytest.skip("needs Tesseract's language data")
    doc = pymupdf.open()
    page = doc.new_page(width=400, height=60)
    side, pitch, x = 18.0, 22.5, 20.0
    cells = []
    for ch in "JO NES     ":
        cells.append((x, 20, x + side, 20 + side))
        if ch != " ":
            page.insert_text((x + 4 + (len(cells) % 2), 34 + (len(cells) % 3) * 0.7), ch, fontsize=13)
        x += pitch
    pix = page.get_pixmap(dpi=DPI, colorspace=pymupdf.csGRAY)
    gray = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width).copy()
    assert read_cells(gray < 128, gray, cells) == "JO NES"          # a box left empty is a space; trailing ones none


def test_letters_one_a_box_are_joined_and_an_empty_box_is_a_space():
    import numpy as np
    import pymupdf

    from jason.community.form_reader import DPI, read_area
    from jason.community.ocr import PyMuPdfTesseract

    if not PyMuPdfTesseract.available():
        pytest.skip("needs Tesseract's language data")
    doc = pymupdf.open()
    page = doc.new_page(width=300, height=60)
    pitch, x = 18.0, 20.0
    for ch in "AB CD":
        if ch != " ":
            page.insert_text((x + 3, 38), ch, fontsize=14)
        x += pitch
    pix = page.get_pixmap(dpi=DPI, colorspace=pymupdf.csGRAY)
    gray = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width).copy()
    assert read_area(gray < 128, (18, 22, 120, 42), pitch=pitch, gray=gray) == "AB CD"


def test_a_priced_layout_trades_paper_against_misreads_in_cents():
    from jason.tasks.form_lab import CURRENT, Costs, Evaluation

    costs = Costs(page_cents=20, misread_cents=150, returned=0.5)
    tall = Evaluation(CURRENT, readable=0.95, used=1368.0, costs=costs, answers=10)         # two pages of height
    short = Evaluation(CURRENT, readable=0.90, used=684.0, costs=costs, answers=10)
    assert round(tall.costs.paper(tall.used)) == 40
    assert round(tall.cents) == 78 and round(short.cents) == 95                     # 40 + 37.5 against 20 + 75
    assert tall.objective > short.objective                                         # the same order, in one unit
    unpriced = Evaluation(CURRENT, readable=0.95, used=600.0)
    assert unpriced.cents is None and round(unpriced.objective, 3) == 0.85


def test_every_pair_puts_two_answers_on_a_line_and_keeps_the_address_whole(tmp_path):
    from dataclasses import replace

    from jason.tasks.form_lab import CURRENT, render

    _, stacked = render(CURRENT, tmp_path / "a.pdf")
    _, paired = render(replace(CURRENT, columns=2, pairs="every"), tmp_path / "b.pdf")
    rect = {k: v for k, v in paired.fields.items()}
    assert rect["owner-names"][1] == rect["unit-address"][1] and rect["owner-names"][2] < rect["unit-address"][0]
    assert rect["email"][1] == rect["phone"][1]
    assert rect["mailing-address"][2] - rect["mailing-address"][0] > 400                 # the whole line
    assert paired.used < stacked.used
