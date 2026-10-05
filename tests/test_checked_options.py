"""Checked options read from text alone: the fixtures' open rows and made-up cases."""

from __future__ import annotations

import json
from pathlib import Path

from jason.community.checked_options import LABEL_CAP, Option, find_options

FIXTURES = Path(__file__).parent / "fixtures" / "contracts"


def _open_row(name: str) -> dict:
    expected = json.loads((FIXTURES / "expected.json").read_text(encoding="utf-8"))
    rows = {**expected[name]["expect"], **expected[name]["open"]}  # a row moves to expect once the reader gives it
    return rows["checked_options"]


def _read(name: str) -> list[Option]:
    return find_options((FIXTURES / name).read_text(encoding="utf-8"))


def test_fixture_01_header_boxes():
    name = "01_monitoring_second_person.txt"
    row = _open_row(name)
    options = _read(name)
    selected = {o.label for o in options if o.checked is True}
    not_selected = {o.label for o in options if o.checked is False}
    assert selected == set(row["selected"])
    assert not_selected == set(row["not_selected"])
    assert all(o.checked is not None for o in options)


def test_fixture_01_spans_point_at_the_option():
    text = (FIXTURES / "01_monitoring_second_person.txt").read_text(encoding="utf-8")
    for option in find_options(text):
        span = text[option.start : option.end]
        assert span.startswith(option.marker)
        assert span.endswith(option.label)


def test_fixture_02_blank_lines_are_not_read_from_text():
    name = "02_sprinkler_proposal_bullets.txt"
    row = _open_row(name)
    assert row["from_text"] == "not read"
    options = _read(name)
    labels = [o.label for o in options]
    layout = row["with_layout"]
    # Every option the layout row names is found, and none is guessed: the lone X lines belong elsewhere.
    assert set(labels) == set(layout["selected"]) | set(layout["not_selected"])
    assert all(o.checked is None for o in options)


def test_fixture_02_signature_and_address_blanks_are_not_options():
    labels = [o.label for o in _read("02_sprinkler_proposal_bullets.txt")]
    assert not any(word in label for label in labels for word in ("ACCEPTED", "Date", "Billing"))


def test_brackets_and_parentheses():
    text = "Choose one:\n[X] Monthly service\n[ ] Quarterly service\n(x) Paper invoices\n( ) Email invoices\n"
    options = find_options(text)
    assert [(o.label, o.checked) for o in options] == [
        ("Monthly service", True),
        ("Quarterly service", False),
        ("Paper invoices", True),
        ("Email invoices", False),
    ]


def test_blank_carrying_its_own_mark():
    text = "X ____ Quarterly Inspection\n__X__ Annual Inspection\n______ Five Year Inspection\n"
    options = find_options(text)
    assert [(o.label, o.checked) for o in options] == [
        ("Quarterly Inspection", True),
        ("Annual Inspection", True),
        ("Five Year Inspection", None),
    ]


def test_check_glyphs_and_bullets():
    text = "- ☑ Gate repair\n- ☐ Pool heater\n✔ Lighting\n"
    assert [(o.label, o.checked) for o in find_options(text)] == [
        ("Gate repair", True),
        ("Pool heater", False),
        ("Lighting", True),
    ]


def test_prose_brackets_and_counts_do_not_match():
    text = (
        "Example Alarm, Inc. will inspect each riser (x2) per subsection (x) of the agreement.\n"
        "See note [ ] below.\n"
        "Customer signature ____________________ Date __________\n"
        "ACCEPTED BY:________________\n"
    )
    assert find_options(text) == []


def test_a_lone_x_is_never_moved_onto_an_option():
    text = "______ Annual Inspection\n______ Quarterly Inspection\nX\nX\n"
    assert [o.checked for o in find_options(text)] == [None, None]


def test_label_is_capped():
    text = "☒ " + "word " * 60 + "\n"
    (option,) = find_options(text)
    assert len(option.label) <= LABEL_CAP
    assert option.checked is True
