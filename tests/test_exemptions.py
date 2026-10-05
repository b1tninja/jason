"""Exemptions: the fixture rows marked open in tests/fixtures/contracts/expected.json, and made-up sentences."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from jason.community.exemptions import (
    EXEMPTION_RULES,
    ExemptionKind,
    clauses,
    excluded_items,
    exemption_of,
    is_exemption,
)

FIXTURES = Path(__file__).parent / "fixtures" / "contracts"


def _collapse(text: str) -> str:
    return " ".join(text.split()).lower()


def _sentences(text: str) -> list[str]:
    out: list[str] = []
    for line in text.splitlines():
        out.extend(s for s in re.split(r"(?<=[.!?])\s+(?=[A-Z0-9])", line.strip()) if s)
    return out


def _sentence_with(name: str, contains: str) -> str:
    text = (FIXTURES / name).read_text(encoding="utf-8")
    hits = [s for s in _sentences(text) if _collapse(contains) in _collapse(s)]
    assert hits, f"{contains!r} not found in {name}"
    return hits[0]


def _open_rows(key: str) -> list[tuple[str, str]]:
    expected = json.loads((FIXTURES / "expected.json").read_text(encoding="utf-8"))
    return [(name, row) for name, case in expected.items() if isinstance(case, dict)
            for part in ("expect", "open") for row in case.get(part, {}).get(key, [])]


SENTENCE_ROWS = [(n, r) for n, r in _open_rows("exemptions") if not n.startswith("02_")]
LIST_ROWS = [(n, r) for n, r in _open_rows("exemptions") if n.startswith("02_")]


def test_fixture_rows_found():
    names = {n for n, _ in _open_rows("exemptions")}
    assert {"01_monitoring_second_person.txt", "02_sprinkler_proposal_bullets.txt", "04_management_agreement.txt",
            "05_landscape_signature_block.txt", "07_paving_extra_work.txt"} <= names
    assert LIST_ROWS and SENTENCE_ROWS


@pytest.mark.parametrize("name,contains", SENTENCE_ROWS)
def test_fixture_sentence_is_exemption(name, contains):
    assert is_exemption(_sentence_with(name, contains))


@pytest.mark.parametrize("name,contains", LIST_ROWS)
def test_fixture_exclusion_list_item(name, contains):
    items = excluded_items((FIXTURES / name).read_text(encoding="utf-8"))
    assert any(_collapse(contains) in _collapse(i) for i in items)


def test_exclusion_list_stops_at_the_paragraph_after_it():
    items = excluded_items((FIXTURES / "02_sprinkler_proposal_bullets.txt").read_text(encoding="utf-8"))
    assert len(items) == 5
    assert not any("valid for ten" in i for i in items)


@pytest.mark.parametrize("name,contains", _open_rows("not_prohibition"))
def test_fixture_not_prohibition(name, contains):
    found = exemption_of(_sentence_with(name, contains))
    assert found is not None and found.kind is ExemptionKind.NOT_OBLIGATED


def test_fixture_kinds_and_holders():
    one = exemption_of(_sentence_with("01_monitoring_second_person.txt", "We are not responsible for any loss"))
    assert (one.kind, one.holder_words) == (ExemptionKind.NOT_RESPONSIBLE, "We")
    two = exemption_of(_sentence_with("01_monitoring_second_person.txt", "We will not be obligated to repair"))
    assert (two.kind, two.cue, two.holder_words) == (ExemptionKind.NOT_OBLIGATED, "will not be obligated to", "We")
    mgr = exemption_of(_sentence_with("04_management_agreement.txt", "Manager is specifically not responsible"))
    assert (mgr.kind, mgr.cue, mgr.holder_words) == (
        ExemptionKind.NOT_RESPONSIBLE, "is specifically not responsible", "Manager")
    weekends = exemption_of(_sentence_with("04_management_agreement.txt", "Manager shall not be obligated"))
    assert weekends.holder_words == "Manager"
    warranty = exemption_of(_sentence_with("05_landscape_signature_block.txt", "we make no representations"))
    assert (warranty.kind, warranty.holder_words) == (ExemptionKind.NO_WARRANTY, "we")
    paving = exemption_of(_sentence_with("07_paving_extra_work.txt", "Exclusions: permits"))
    assert paving.kind is ExemptionKind.EXCLUDED


@pytest.mark.parametrize("sentence,kind,holder", [
    ("Example Alarm, Inc. shall not be required to replace batteries.", ExemptionKind.NOT_OBLIGATED,
     "Example Alarm, Inc."),
    ("The Contractor is not required to obtain permits.", ExemptionKind.NOT_OBLIGATED, "The Contractor"),
    ("Contractor shall have no duty to inspect the roof.", ExemptionKind.NOT_OBLIGATED, "Contractor"),
    ("The price excludes sales tax.", ExemptionKind.EXCLUDED, "The price"),
    ("This proposal does not include painting.", ExemptionKind.EXCLUDED, "This proposal"),
    ("Hauling is not included.", ExemptionKind.EXCLUDED, "Hauling"),
    ("The equipment is sold AS IS.", ExemptionKind.AS_IS, "The equipment is sold"),
    ("There is no warranty on used parts.", ExemptionKind.NO_WARRANTY, "There is"),
    ("Example Pumps LLC makes no express or implied warranty.", ExemptionKind.NO_WARRANTY, "Example Pumps LLC"),
    ("Vendor disclaims all implied warranties.", ExemptionKind.NO_WARRANTY, "Vendor"),
    ("Our liability is limited to the price paid.", ExemptionKind.LIMITED_TO, "Our"),
])
def test_made_up_exemptions(sentence, kind, holder):
    found = exemption_of(sentence)
    assert found is not None
    assert (found.kind, found.holder_words) == (kind, holder)


@pytest.mark.parametrize("sentence", [
    "Manager shall not disclose the Association's records to any third party.",
    "We will not share your information with anyone.",
    "You will not tamper with, alter, or remove any part of the System.",
    "Contractor shall provide such insurance as is customary in the trade.",
    "The work is limited to the area shown on the map at 123 Main St.",
    "Contractor shall keep the site clean.",
    "Clarifications and exclusions of this proposal shall supersede any conflicting contract language.",
])
def test_not_an_exemption(sentence):
    assert exemption_of(sentence) is None
    assert not is_exemption(sentence)


@pytest.mark.parametrize("sentence", [
    "Owner disclaims any interest in the parking easement.",
    "Contractor excludes nothing from this warranty.",
    "Contractor excludes none of the listed items.",
])
def test_reviewed_false_positives(sentence):
    assert exemption_of(sentence) is None


@pytest.mark.parametrize("sentence,kind,holder", [
    ("Vendor disclaims any and all liability for water damage.", ExemptionKind.NO_WARRANTY, "Vendor"),
    ("Vendor disclaims, to the extent allowed, the implied warranties.", ExemptionKind.NO_WARRANTY, "Vendor"),
    ("This warranty excludes normal wear.", ExemptionKind.EXCLUDED, "This warranty"),
    ("Contractor assumes no responsibility for existing cracks.", ExemptionKind.NOT_RESPONSIBLE, "Contractor"),
    ("Example Paving bears no liability for tree roots.", ExemptionKind.NOT_RESPONSIBLE, "Example Paving"),
    ("We accept no responsibility for lost keys.", ExemptionKind.NOT_RESPONSIBLE, "We"),
    ("Damage from acts of God is excluded.", ExemptionKind.EXCLUDED, "Damage from acts of God"),
    ("Permits and fees are excluded from this proposal.", ExemptionKind.EXCLUDED, "Permits and fees"),
    ("Sold in as-is condition.", ExemptionKind.AS_IS, ""),
])
def test_reviewed_near_misses(sentence, kind, holder):
    found = exemption_of(sentence)
    assert found is not None
    assert (found.kind, found.holder_words) == (kind, holder)


def test_disclaimer_does_not_reach_past_a_clause_break():
    assert exemption_of("Owner disclaims any interest in the easement, but the warranty stays in force.") is None


def test_plain_exclusion_lines_until_blank_line():
    text = ("Scope: replace the gate motor at 123 Main St.\n"
            "Exclusions:\n"
            "Permits and fees\n"
            "Electrical work beyond the motor\n"
            "Painting\n"
            "\n"
            "This proposal is valid for thirty days.\n")
    assert excluded_items(text) == ("Permits and fees", "Electrical work beyond the motor", "Painting")


def test_plain_exclusion_lines_stop_at_a_heading():
    text = "Exclusions:\nPermits\nHauling\nPayment Terms:\nNet 30\n"
    assert excluded_items(text) == ("Permits", "Hauling")


def test_clauses_split_exemption_from_duty():
    sentence = "Contractor is not required to obtain permits, but Contractor shall keep the site clean."
    parts = clauses(sentence)
    assert parts == ["Contractor is not required to obtain permits", "Contractor shall keep the site clean."]
    assert exemption_of(parts[0]).kind is ExemptionKind.NOT_OBLIGATED
    assert exemption_of(parts[1]) is None
    assert clauses("We repair leaks; we are not liable for mold, and we test monthly.") == [
        "We repair leaks", "we are not liable for mold", "we test monthly."]
    assert clauses("Contractor shall keep the site clean.") == ["Contractor shall keep the site clean."]


def test_rules_are_rows_with_kinds():
    assert all(isinstance(rule.kind, ExemptionKind) for rule in EXEMPTION_RULES)
    assert {rule.kind for rule in EXEMPTION_RULES} == set(ExemptionKind)
