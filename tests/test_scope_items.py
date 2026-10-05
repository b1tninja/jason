"""Scope items: the fixture rows for scope_items in tests/fixtures/contracts/expected.json, and made-up proposals."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from jason.community.scope_items import (
    INCLUSION_RULES,
    OPTION_HEADINGS,
    OPTION_RULES,
    OTHERS_RULES,
    ScopeKind,
    find_scope_items,
)

FIXTURES = Path(__file__).parent / "fixtures" / "contracts"


def _collapse(text: str) -> str:
    return " ".join(text.split()).lower()


def _rows() -> list[tuple[str, str]]:
    expected = json.loads((FIXTURES / "expected.json").read_text(encoding="utf-8"))
    rows: list[tuple[str, str]] = []
    for name, entry in expected.items():
        if name.startswith("_"):
            continue
        for block in ("expect", "open"):
            for contains in entry.get(block, {}).get("scope_items", []):
                rows.append((name, contains))
    return rows


@pytest.mark.parametrize(("name", "contains"), _rows())
def test_fixture_scope_items(name: str, contains: str) -> None:
    text = (FIXTURES / name).read_text(encoding="utf-8")
    items = find_scope_items(text)
    assert any(_collapse(contains) in _collapse(item.text) for item in items), [i.text for i in items]


@pytest.mark.parametrize("name", sorted(p.name for p in FIXTURES.glob("*.txt")))
def test_offsets_index_the_text(name: str) -> None:
    text = (FIXTURES / name).read_text(encoding="utf-8")
    for item in find_scope_items(text):
        assert " ".join(text[item.start:item.end].split()) == item.text


def test_fixture_kinds() -> None:
    text = (FIXTURES / "07_paving_extra_work.txt").read_text(encoding="utf-8")
    kinds = {item.text: item.kind for item in find_scope_items(text)}
    assert kinds["Crack seal all cracks over 1/4 inch."] is ScopeKind.WORK
    assert kinds["The price includes all labor, materials, and equipment."] is ScopeKind.INCLUSION
    assert kinds["Traffic control is included at no additional cost."] is ScopeKind.INCLUSION
    assert not any("permits, engineering" in t for t in kinds)


def test_fixture_clause_not_whole_sentence() -> None:
    text = (FIXTURES / "05_landscape_signature_block.txt").read_text(encoding="utf-8")
    [item] = find_scope_items(text)
    assert item.text == "repair minor leaks at no additional cost."
    assert item.kind is ScopeKind.INCLUSION


def test_fixtures_without_scope_lists_give_none() -> None:
    for name in ("01_monitoring_second_person.txt", "02_sprinkler_proposal_bullets.txt",
                 "04_management_agreement.txt", "08_association_drafted_we.txt"):
        assert find_scope_items((FIXTURES / name).read_text(encoding="utf-8")) == [], name


PROPOSAL = """EXAMPLE ROOFING, INC.
123 Main St, Exampletown, CA 90000
(555) 555-0100 | office@example.test

Scope of Work:
- Gutter cleaning
* Remove and replace 40 sq ft of damaged decking
  at the north eave.
o
Pressure-wash the walkway and
dispose of all debris.
1. Repair leaks at no additional cost.
2. Total: $1,200
Test results will be sent within ten (10) days.

Exclusions:
- Remove existing trees
- Permits

Install gutter guards on all buildings.
Sales tax is not included.
Exhibit A is included for reference.
This quote includes the following clarifications:
All materials are included free of charge.
Options:
- Annual inspection

CUSTOMER:
Provide access to the roof on the scheduled day.

Signed: ____________________   Date: ______
"""


def _texts(kind: ScopeKind | None = None) -> list[str]:
    return [i.text for i in find_scope_items(PROPOSAL) if kind is None or i.kind is kind]


def test_list_items_under_a_scope_heading() -> None:
    work = _texts(ScopeKind.WORK)
    assert "Gutter cleaning" in work  # a noun phrase, but under the scope heading
    assert "Remove and replace 40 sq ft of damaged decking at the north eave." in work  # wrapped onto two lines
    assert "Pressure-wash the walkway and dispose of all debris." in work  # a bare "o" bullet on its own line


def test_a_work_item_with_an_inclusion_cue_is_read_once() -> None:
    hits = [i for i in find_scope_items(PROPOSAL) if "Repair leaks" in i.text]
    assert len(hits) == 1 and hits[0].kind is ScopeKind.WORK


def test_plain_imperative_line_and_its_heading() -> None:
    items = {i.text: i for i in find_scope_items(PROPOSAL)}
    assert items["Install gutter guards on all buildings."].kind is ScopeKind.WORK
    assert items["Provide access to the roof on the scheduled day."].heading == "CUSTOMER:"
    assert items["Gutter cleaning"].heading == "Scope of Work:"


def test_inclusions() -> None:
    assert _texts(ScopeKind.INCLUSION) == ["All materials are included free of charge."]


@pytest.mark.parametrize("near_miss", [
    "Remove existing trees",  # under Exclusions
    "Permits",
    "Total: $1,200",  # a price line alone
    "Test results will be sent",  # a noun with a subject's verb, not an imperative
    "Sales tax is not included",  # an exclusion
    "Exhibit A is included",  # an attachment, not work
    "This quote includes the following clarifications",  # a heading
    "Annual inspection",  # a list item under a heading that is not the scope
    "Scope of Work",
    "Signed",
    "Main St",
    "EXAMPLE ROOFING",
])
def test_near_misses(near_miss: str) -> None:
    assert not any(near_miss.lower() in t.lower() for t in _texts()), _texts()


def test_offsets_on_the_made_up_proposal() -> None:
    for item in find_scope_items(PROPOSAL):
        assert " ".join(PROPOSAL[item.start:item.end].split()) == item.text


def test_exclusion_heading_with_items_on_its_line() -> None:
    text = "Work Not Included: Paint the trim.\nNot included:\nReplace the fence posts\n\nRepaint the trim on Bldg 2.\n"
    assert [i.text for i in find_scope_items(text)] == ["Repaint the trim on Bldg 2."]


def test_short_plain_lines_and_empty_text() -> None:
    assert find_scope_items("") == []
    assert find_scope_items("Repair\nClean gutters\n") == []  # too short to be a line of work outside a list


def test_inclusion_rules_have_notes() -> None:
    assert all(rule.note for rule in (*INCLUSION_RULES, *OTHERS_RULES, *OPTION_HEADINGS, *OPTION_RULES))


def _read(text: str) -> list[tuple[str, ScopeKind]]:
    return [(i.text, i.kind) for i in find_scope_items(text)]


def test_work_by_others_or_the_owner_is_not_scope() -> None:
    text = ("Scope of Work\n- Permits by others\n- Engineering by others\n- Permits by owner\n"
            "- Owner to supply paint\n- Debris haul-off by the HOA.\n- The association will furnish the gate code\n"
            "- Paint supplied by the customer, installed by contractor\n"
            "- Repaint doors in colors selected by the owner.\n- Contractor to provide all materials\n")
    assert _read(text) == [
        ("Repaint doors in colors selected by the owner.", ScopeKind.WORK),  # near miss: the owner only chooses
        ("Contractor to provide all materials", ScopeKind.WORK),  # near miss: the vendor supplies
    ]


def test_a_list_item_stops_at_a_label_or_a_new_sentence() -> None:
    text = "Scope:\n- Paint all trim\nAlternate: Repaint doors at an additional cost of $500.\n"
    assert _read(text) == [("Paint all trim", ScopeKind.WORK),
                           ("Repaint doors at an additional cost of $500.", ScopeKind.OPTION)]
    text = "Scope:\n- Clean gutters\nInstall gutter guards on all buildings.\n"
    assert _read(text) == [("Clean gutters", ScopeKind.WORK),
                           ("Install gutter guards on all buildings.", ScopeKind.WORK)]


def test_a_list_item_still_carries_on_an_open_sentence() -> None:
    text = "Scope:\n- Install new gutters on\nBuilding 3 and the carports.\n- Seal coat the lot,\n   Area B only.\n"
    assert _read(text) == [("Install new gutters on Building 3 and the carports.", ScopeKind.WORK),
                           ("Seal coat the lot, Area B only.", ScopeKind.WORK)]


def test_optional_and_alternate_items() -> None:
    text = ("Scope of Work\n- Replace the pool pump.\n\nOptional Items\n- Install new irrigation controller $1,200\n"
            "\nAdd Alternates:\n- Repaint the pool fence.\n\nSpecifications\n- Remove the old timer.\n"
            "Option 2: Replace the pool heater.\nOptional: Add a pool cover.\n"
            "Replace pool tile at an additional cost.\nRepair pool lights at no additional cost.\n")
    assert _read(text) == [
        ("Replace the pool pump.", ScopeKind.WORK),
        ("Install new irrigation controller $1,200", ScopeKind.OPTION),
        ("Repaint the pool fence.", ScopeKind.OPTION),
        ("Remove the old timer.", ScopeKind.WORK),  # a scope heading ends the options
        ("Replace the pool heater.", ScopeKind.OPTION),
        ("Add a pool cover.", ScopeKind.OPTION),
        ("Replace pool tile at an additional cost.", ScopeKind.OPTION),
        ("Repair pool lights at no additional cost.", ScopeKind.WORK),  # near miss: included, not extra
    ]
    [item] = [i for i in find_scope_items(text) if i.text.startswith("Install new irrigation")]
    assert item.heading == "Optional Items"


def test_a_plain_line_carries_onto_a_lowercase_line() -> None:
    text = "Remove and replace damaged fascia boards on\nbuildings 3 and 4 as needed.\n"
    assert _read(text) == [("Remove and replace damaged fascia boards on buildings 3 and 4 as needed.",
                            ScopeKind.WORK)]
    near = "Remove and replace damaged fascia boards on all buildings\nInstall new gutters at the carports.\n"
    assert _read(near) == [("Remove and replace damaged fascia boards on all buildings", ScopeKind.WORK),
                           ("Install new gutters at the carports.", ScopeKind.WORK)]


@pytest.mark.parametrize("text", [
    "Scope:\n- Paint all trim\nAlternate: Repaint doors at an additional cost of $500.\n",
    "Remove and replace damaged fascia boards on\nbuildings 3 and 4 as needed.\n",
    "Scope:\n- Seal coat the lot,\n   Area B only.\n",
])
def test_offsets_on_carried_and_labelled_items(text: str) -> None:
    for item in find_scope_items(text):
        assert " ".join(text[item.start:item.end].split()) == item.text
