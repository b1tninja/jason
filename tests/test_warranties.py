"""Warranties, read from the made-up contract fixtures and a few made-up sentences."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from jason.community.warranties import (
    Cover,
    Period,
    Start,
    Unit,
    WarrantyForm,
    find_warranties,
    sentences,
    warranties_of,
    warranty_of,
)

FIXTURES = Path(__file__).parent / "fixtures" / "contracts"


def _rows(key: str) -> list[tuple[str, object]]:
    """Each fixture's rows under ``key``, from 'expect' and 'open' both (a row moves from open to expect when it lands)."""
    expected = json.loads((FIXTURES / "expected.json").read_text(encoding="utf-8"))
    rows: list[tuple[str, object]] = []
    for fixture, entry in expected.items():
        if not isinstance(entry, dict):
            continue
        for part in ("expect", "open"):
            for row in (entry.get(part) or {}).get(key, []) or []:
                rows.append((fixture, row))
    return rows


def _text(fixture: str) -> str:
    return (FIXTURES / fixture).read_text(encoding="utf-8")


def _norm(words: str) -> str:
    return " ".join(words.lower().split())


WARRANTY_ROWS = _rows("warranty")
DELIVERABLE_ROWS = [(f, row) for f, row in _rows("alias_deliverables") if "warrant" in str(row).lower()]


def test_the_fixture_rows_are_found():
    assert WARRANTY_ROWS and DELIVERABLE_ROWS


@pytest.mark.parametrize(("fixture", "row"), WARRANTY_ROWS, ids=[f for f, _ in WARRANTY_ROWS])
def test_fixture_warranty(fixture, row):
    found = [w for w in find_warranties(_text(fixture)) if _norm(row["contains"]) in _norm(w.sentence)]
    assert len(found) == 1
    warranty = found[0]
    assert warranty.period_months == row["period_months"]
    # The holder is the counterparty's name as written; the reader maps it to the party.
    if row.get("party") == "counterparty":
        assert warranty.holder_words and warranty.holder_words.lower() in _text(fixture).splitlines()[0].lower()


@pytest.mark.parametrize(("fixture", "row"), DELIVERABLE_ROWS, ids=[f for f, _ in DELIVERABLE_ROWS])
def test_fixture_deliverable_warranty(fixture, row):
    found = [w for w in find_warranties(_text(fixture)) if w.deliverable]
    assert [_norm(w.deliverable_words) for w in found] == [_norm(row)]


def test_paving_warranty_in_full():
    (warranty,) = find_warranties(_text("07_paving_extra_work.txt"))
    assert warranty.form is WarrantyForm.WARRANTS
    assert warranty.holder_words == "Example Paving Company"
    assert warranty.covered_words == "its workmanship"
    assert warranty.covers == (Cover.WORKMANSHIP,)
    assert warranty.period == Period(1, Unit.YEAR, "one (1) year")
    assert warranty.start is Start.COMPLETION
    assert not warranty.deliverable and not warranty.written


def test_roof_warranty_in_full():
    (warranty,) = find_warranties(_text("03_roof_repair_letterhead.txt"))
    assert warranty.form is WarrantyForm.PROVIDES
    assert warranty.holder_words == "EHS"
    assert warranty.covers == (Cover.WORKMANSHIP,)
    assert warranty.period_months == 60
    assert warranty.start is Start.COMPLETION
    assert warranty.written and warranty.deliverable


def test_disclaimer_fixture_gives_no_warranty():
    assert find_warranties(_text("05_landscape_signature_block.txt")) == ()


@pytest.mark.parametrize("fixture", sorted(p.name for p in FIXTURES.glob("*.txt")))
def test_fixtures_give_only_their_warranties(fixture):
    expected = {"03_roof_repair_letterhead.txt": 1, "07_paving_extra_work.txt": 1}
    assert len(find_warranties(_text(fixture))) == expected.get(fixture, 0)


@pytest.mark.parametrize(("sentence", "holder", "months", "covers", "start", "deliverable"), [
    ("Example Roofing, Inc. warrants the roof against leaks for ten (10) years from installation.",
     "Example Roofing, Inc.", 120, (), Start.INSTALLATION, False),
    ("Contractor shall warrant all labor and materials for a period of two (2) years from substantial completion.",
     "Contractor", 24, (Cover.LABOR, Cover.MATERIALS), Start.SUBSTANTIAL_COMPLETION, False),
    ("All work is guaranteed for one year from the date of completion.",
     "", 12, (Cover.WORK,), Start.COMPLETION, False),
    ("Installed equipment is warranted by Example Gates LLC for 90 days.",
     "Example Gates LLC", 3, (Cover.EQUIPMENT, Cover.INSTALLATION), None, False),
    ("We will furnish a warranty certificate for a 12-month period after final acceptance.",
     "We", 12, (), Start.ACCEPTANCE, True),
    ("Warranty: two (2) years on labor.", "", 24, (Cover.LABOR,), None, False),
    ("Contractor offers a 5-year warranty on the installation.", "Contractor", 60, (Cover.INSTALLATION,), None,
     False),
    ("1.4 Vendor hereby guarantees its workmanship.", "Vendor", None, (Cover.WORKMANSHIP,), None, False),
])
def test_made_up_warranties(sentence, holder, months, covers, start, deliverable):
    warranty = warranty_of(sentence)
    assert warranty is not None
    assert warranty.holder_words == holder
    assert warranty.period_months == months
    assert warranty.covers == covers
    assert warranty.start is start
    assert warranty.deliverable is deliverable


def test_roof_is_in_the_covered_words():
    warranty = warranty_of("Example Roofing, Inc. warrants the roof against leaks for ten (10) years.")
    assert warranty is not None and "the roof" in warranty.covered_words


def test_days_are_kept():
    warranty = warranty_of("Contractor warrants its workmanship for forty-five (45) days.")
    assert warranty is not None
    assert warranty.period.days == 45 and warranty.period.months is None
    weeks = warranty_of("Contractor warrants the repair for six (6) weeks.")
    assert weeks is not None and weeks.period.days == 42 and weeks.period.months is None


def test_a_disclaimer_beside_a_warranty_keeps_the_warranty():
    warranty = warranty_of("Contractor warrants its workmanship for one (1) year, but makes no warranty as to "
                           "materials supplied by Owner.")
    assert warranty is not None and warranty.covers == (Cover.WORKMANSHIP,)


@pytest.mark.parametrize("sentence", [
    "Contractor makes no warranties, express or implied.",
    "We make no representations or warranties as to the installed materials.",
    "Example Roofing, Inc. does not warrant the existing roof.",
    "Vendor does not guarantee results.",
    "The equipment is sold without any warranty.",
    "There is no guarantee of uninterrupted service.",
    "Any alteration by Owner voids the warranty.",
    "The roof is not warranted against wind damage.",
    "Contractor represents and warrants that it holds all licenses required by law.",
    "Warranty claims must be made in writing within thirty (30) days.",
    "Payment is guaranteed by the Association.",
    "Contractor will guarantee to complete the work within ten (10) days.",
    "Contractor shall pay all warranty claims.",
    "Example Paving Company will notify the Customer at least forty-eight (48) hours before the work begins.",
    "The warranty period begins on completion.",
])
def test_near_misses_give_no_warranty(sentence):
    assert warranty_of(sentence) is None


def test_sentences_keep_business_suffixes_and_split_headings():
    assert sentences("Example Roofing, Inc. warrants the roof. Owner shall pay.\n\nWarranty. Example warrants it.") == [
        "Example Roofing, Inc. warrants the roof.", "Owner shall pay.", "Warranty.", "Example warrants it."]


def test_a_wrapped_paragraph_keeps_its_period():
    text = ("11. WARRANTY. Contractor warrants its workmanship\nfor a period of two (2) years from the date of\n"
            "completion of the work.\n")
    (warranty,) = find_warranties(text)
    assert warranty.period_months == 24
    assert warranty.start is Start.COMPLETION
    assert warranty.holder_words == "Contractor"


def test_lines_that_end_a_sentence_or_open_a_list_stay_apart():
    text = "Scope of Work\n- Replace the flashing.\nWarranty: two (2) years on labor.\nOwner shall pay\nPage 2 of 4\n"
    assert sentences(text) == ["Scope of Work", "- Replace the flashing.", "Warranty: two (2) years on labor.",
                               "Owner shall pay", "Page 2 of 4"]


def test_warrants_that_with_a_period_or_cover_is_a_warranty():
    warranty = warranty_of("Contractor warrants that all work will be free of defects for one year.")
    assert warranty is not None
    assert warranty.form is WarrantyForm.WARRANTS
    assert warranty.holder_words == "Contractor"
    assert warranty.period_months == 12
    assert warranty.covers == (Cover.WORK,)


def test_represents_and_warrants_that_without_period_or_cover_is_not():
    assert warranty_of("Vendor represents and warrants that it is duly organized under the laws of the state.") is None


def test_each_clause_gives_its_own_noun_warranty_with_its_holder():
    sentence = "Manufacturer's warranty on materials is 25 years; Contractor's labor warranty is 2 years."
    first, second = warranties_of(sentence)
    assert (first.form, first.holder_words, first.covered_words, first.period_months) == (
        WarrantyForm.NOUN, "Manufacturer's", "materials", 300)
    assert first.covers == (Cover.MATERIALS,)
    assert (second.holder_words, second.covered_words, second.period_months) == ("Contractor's", "labor", 24)
    assert second.covers == (Cover.LABOR,)
    assert warranty_of(sentence) == first
    assert len(find_warranties(sentence)) == 2


def test_a_noun_warranty_without_a_possessive_has_no_holder():
    warranty = warranty_of("The roof's warranty is ten (10) years.")
    assert warranty is not None and warranty.holder_words == "" and warranty.period_months == 120


def test_an_exclusion_is_not_what_is_covered():
    warranty = warranty_of("Our 5-year warranty does not cover damage from acts of God.")
    assert warranty is not None
    assert warranty.holder_words == "Our"
    assert warranty.covered_words == ""
    assert warranty.covers == ()
    assert warranty.period_months == 60


def test_an_exclusion_names_no_cover():
    warranty = warranty_of("Our 2-year warranty does not cover labor.")
    assert warranty is not None and warranty.covers == () and warranty.period_months == 24


def test_a_contract_printed_twice_gives_each_warranty_once():
    text = "Contractor warrants its workmanship for one (1) year.\n" * 2
    assert len(find_warranties(text)) == 1


@pytest.mark.parametrize("sentence", [
    "Example Pest Control guarantees the pricing in this agreement one year from start date.",
    "Prices are guaranteed for ninety (90) days.",
    "We lock in the rate for two (2) years.",
])
def test_a_price_lock_is_not_a_warranty(sentence):
    assert warranties_of(sentence) == ()


def test_a_warranty_beside_a_price_lock_still_reads():
    found = warranties_of("Prices are guaranteed for 90 days; all work is guaranteed for one (1) year.")
    assert [w.period_months for w in found] == [12]


def test_the_noun_used_as_the_verb_keeps_its_holder():
    w = warranty_of("Example Paving Company warranties all work for a period of one year with the following exceptions.")
    assert w is not None and w.holder_words == "Example Paving Company" and w.period_months == 12


def test_warranties_as_a_noun_is_not_the_verb():
    w = warranty_of("All warranties are void if the system is altered.")
    assert w is None or w.holder_words == ""
