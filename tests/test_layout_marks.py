"""Layout marks: options and their marks read from where the words sit on the page (made-up layouts)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from jason.community.layout_marks import (
    MarkMiss,
    OptionMarker,
    marks_from_pdf,
    marks_from_words,
)

FIXTURES = Path(__file__).parent / "fixtures" / "contracts"
H = 10.0  # line height of the synthetic pages


def _row(name: str) -> dict:
    """The fixture's checked-options row, expect and open merged (the lead moves rows from open to expect)."""
    data = json.loads((FIXTURES / "expected.json").read_text(encoding="utf-8"))[name]
    merged: dict = {}
    for part in ("expect", "open"):
        merged.update(data.get(part, {}).get("checked_options", {}) or {})
    return merged


def _words(y: float, x: float, text: str, block: int, line: int = 0, width: float = 6.0) -> list[tuple]:
    """Word tuples for ``text`` laid left to right from ``x`` on the line whose top is ``y``."""
    out = []
    for n, word in enumerate(text.split()):
        w = width * len(word)
        out.append((x, y, x + w, y + H, word, block, line, n))
        x += w + 4
    return out


def _page_02() -> list[tuple]:
    """The 02 signature page: three blank-line options, then the signer's X marks in a later text layer."""
    words: list[tuple] = []
    words += _words(470, 50, "Please indicate type of inspections requested:", 1, 0)
    words += _words(485, 50, "______ Five Year Inspection", 1, 1)
    words += _words(500, 50, "______ Annual Inspection", 1, 2)
    words += _words(515, 50, "______ Quarterly Inspection", 1, 3)
    words += _words(530, 50, "ACCEPTED BY:________________", 1, 4)
    words += _words(545, 50, "Date: _________", 1, 5)
    words += _words(560, 50, "Name & Title: ______________", 1, 6)
    # The marks: drawn later, in their own block, on the Annual and Quarterly blanks.
    words += [(60, 500.5, 66, 510.5, "X", 9, 0, 0), (61, 515.5, 67, 525.5, "X", 9, 1, 0)]
    return words


def test_02_with_layout_row():
    row = _row("02_sprinkler_proposal_bullets.txt")["with_layout"]
    reading = marks_from_words(_page_02())
    assert set(reading.selected()) == set(row["selected"])
    assert set(reading.not_selected()) == set(row["not_selected"])
    assert reading.unread() == ()
    assert reading.unassigned == ()
    labels = [o.label for o in reading.options]
    assert labels == ["Five Year Inspection", "Annual Inspection", "Quarterly Inspection"]
    annual = reading.options[1]
    assert annual.mark_box is not None and annual.marker is OptionMarker.BLANK
    assert reading.options[0].mark_box is None


def test_signature_and_date_blanks_are_not_options():
    labels = [o.label for o in marks_from_words(_page_02()).options]
    assert not any("Date" in label or "ACCEPTED" in label or "Title" in label for label in labels)


def test_mark_left_of_the_blank_on_the_baseline():
    words = _words(100, 50, "______ Monthly service", 1, 0) + _words(115, 50, "______ Weekly service", 1, 1)
    words.append((40, 115.5, 46, 125.5, "X", 5, 0, 0))  # just left of the Weekly blank
    reading = marks_from_words(words)
    assert reading.selected() == ("Weekly service",)
    assert reading.not_selected() == ("Monthly service",)


def test_mark_on_the_label_text():
    words = _words(100, 50, "______ Monthly service", 1, 0)
    words.append((120, 100, 126, 110, "x", 5, 0, 0))
    assert marks_from_words(words).selected() == ("Monthly service",)


def test_ambiguous_mark_between_two_lines_is_not_guessed():
    words = _words(100, 50, "______ Monthly service", 1, 0) + _words(110, 50, "______ Weekly service", 1, 1)
    # Halfway between the two lines and overlapping both blanks.
    words.append((55, 104, 61, 116, "X", 5, 0, 0))
    reading = marks_from_words(words)
    assert reading.selected() == ()
    assert set(reading.unread()) == {"Monthly service", "Weekly service"}
    [miss] = reading.unassigned
    assert miss.miss is MarkMiss.AMBIGUOUS
    assert set(miss.candidates) == {"Monthly service", "Weekly service"}


def test_ambiguous_mark_leaves_the_other_option_read():
    words = (_words(100, 50, "______ Monthly service", 1, 0) + _words(110, 50, "______ Weekly service", 1, 1)
             + _words(140, 50, "______ Yearly service", 1, 2))
    words.append((55, 104, 61, 116, "X", 5, 0, 0))
    reading = marks_from_words(words)
    assert reading.not_selected() == ("Yearly service",)


def test_stray_mark_is_reported_and_given_to_no_option():
    words = _page_02() + [(300, 700, 306, 710, "X", 10, 0, 0)]  # a signature-line X far from the list
    reading = marks_from_words(words)
    assert set(reading.selected()) == {"Annual Inspection", "Quarterly Inspection"}
    [miss] = reading.unassigned
    assert miss.miss is MarkMiss.NO_OPTION and miss.candidates == ()


def test_mark_far_right_on_the_baseline_is_stray():
    words = _words(100, 50, "______ Monthly service", 1, 0)
    words.append((400, 100, 406, 110, "X", 5, 0, 0))  # same y, but far past the label's end: outside its column
    reading = marks_from_words(words)
    assert reading.selected() == ()
    assert reading.unassigned[0].miss is MarkMiss.NO_OPTION
    assert not reading.has_marks_layer
    assert reading.unread() == ("Monthly service",)


def _three_options() -> list[tuple]:
    return (_words(100, 50, "______ Monthly service", 1, 0) + _words(115, 50, "______ Weekly service", 1, 1)
            + _words(130, 50, "______ Yearly service", 1, 2))


def _table_row() -> list[tuple]:
    """A table row "10 | x | 12" below the list, each cell its own block."""
    return [(300, 300, 312, 310, "10", 7, 0, 0), (340, 300, 346, 310, "x", 8, 0, 0), (380, 300, 392, 310, "12", 9, 0, 0)]


def test_table_cell_x_is_no_marks_layer():
    reading = marks_from_words(_three_options() + _table_row())
    assert not reading.has_marks_layer
    assert set(reading.unread()) == {"Monthly service", "Weekly service", "Yearly service"}
    [miss] = reading.unassigned
    assert miss.miss is MarkMiss.NO_OPTION


def test_signature_x_at_the_foot_is_no_marks_layer():
    words = _three_options() + _words(700, 50, "______________", 6, 0)
    words.append((40, 700, 46, 710, "X", 6, 0, 1))  # the signer's "X" beside the signature blank
    reading = marks_from_words(words)
    assert [o.label for o in reading.options] == ["Monthly service", "Weekly service", "Yearly service"]
    assert not reading.has_marks_layer
    assert reading.not_selected() == ()
    assert len(reading.unread()) == 3


def test_table_cell_beside_a_real_mark_still_reads():
    words = _three_options() + _table_row()
    words.append((55, 115.5, 61, 125.5, "X", 5, 0, 0))  # on the Weekly blank
    reading = marks_from_words(words)
    assert reading.has_marks_layer
    assert reading.selected() == ("Weekly service",)
    assert set(reading.not_selected()) == {"Monthly service", "Yearly service"}


def test_mark_beside_two_lines_is_evidence_and_leaves_them_unread():
    words = _three_options()
    # Left of the blanks, between the Monthly and Weekly lines: on neither blank nor baseline, but beside both.
    words.append((40, 107, 46, 117, "X", 5, 0, 0))
    reading = marks_from_words(words)
    assert reading.has_marks_layer
    assert reading.selected() == ()
    assert set(reading.unread()) == {"Monthly service", "Weekly service"}
    assert reading.not_selected() == ("Yearly service",)
    assert reading.unassigned[0].miss is MarkMiss.NO_OPTION


def test_form_field_pattern_is_shared():
    from jason.community import checked_options, layout_marks

    assert layout_marks._FORM_FIELD is checked_options._FORM_FIELD


def test_form_field_with_a_colon_is_not_an_option():
    words = _words(100, 50, "______ Name:", 1, 0) + _words(115, 50, "______ Weekly service", 1, 1)
    assert [o.label for o in marks_from_words(words).options] == ["Weekly service"]


def test_no_marks_layer_reads_none():
    words = _words(100, 50, "______ Monthly service", 1, 0) + _words(115, 50, "______ Weekly service", 1, 1)
    reading = marks_from_words(words)
    assert not reading.has_marks_layer
    assert set(reading.unread()) == {"Monthly service", "Weekly service"}


def test_x_inside_a_label_line_is_text_not_a_mark():
    words = _words(100, 50, "______ Replace 2 x 4 framing", 1, 0)
    reading = marks_from_words(words)
    [opt] = reading.options
    assert opt.label == "Replace 2 x 4 framing"
    assert opt.checked is None  # no marks layer
    assert reading.unassigned == ()


def test_marked_blank_and_boxes():
    words = (_words(100, 50, "__X__ Monthly service", 1, 0) + _words(115, 50, "☐ Weekly service", 1, 1)
             + _words(130, 50, "☒ Yearly service", 1, 2) + _words(145, 50, "☐ Daily service", 1, 3))
    words.append((51, 145.5, 57, 155.5, "✓", 5, 0, 0))  # a check over the Daily box
    reading = marks_from_words(words)
    assert set(reading.selected()) == {"Monthly service", "Yearly service", "Daily service"}
    assert reading.not_selected() == ("Weekly service",)
    assert reading.options[0].marker is OptionMarker.MARKED_BLANK


def test_blank_after_text_is_not_an_option():
    words = _words(100, 50, "Billing Address: ______ Example Street", 1, 0)
    words.append((150, 100, 156, 110, "X", 5, 0, 0))
    reading = marks_from_words(words)
    assert reading.options == ()
    assert reading.unassigned[0].miss is MarkMiss.NO_OPTION


def test_two_columns_on_one_line():
    words = _words(100, 50, "______ Monthly service", 1, 0) + _words(100, 300, "______ Weekly service", 2, 0)
    words.append((310, 100.5, 316, 110.5, "X", 5, 0, 0))
    reading = marks_from_words(words)
    assert [o.label for o in reading.options] == ["Monthly service", "Weekly service"]
    assert reading.selected() == ("Weekly service",)
    assert reading.not_selected() == ("Monthly service",)


def test_empty_page():
    reading = marks_from_words([])
    assert reading.options == () and reading.unassigned == ()


def test_marks_from_pdf(tmp_path):
    pymupdf = pytest.importorskip("pymupdf")
    path = tmp_path / "form.pdf"
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((50, 100), "______ Five Year Inspection", fontsize=11)
    page.insert_text((50, 120), "______ Annual Inspection", fontsize=11)
    page.insert_text((50, 140), "______ Quarterly Inspection", fontsize=11)
    page.insert_text((50, 160), "Date: _________", fontsize=11)
    # The signer's marks, written after the list as their own text.
    page.insert_text((300, 400), "Example Director", fontsize=11)
    page.insert_text((62, 119), "X", fontsize=11)
    page.insert_text((62, 139), "X", fontsize=11)
    doc.save(str(path))
    doc.close()
    reading = marks_from_pdf(path, 0)
    assert reading.selected() == ("Annual Inspection", "Quarterly Inspection")
    assert reading.not_selected() == ("Five Year Inspection",)
    assert reading.unassigned == ()
