"""Party aliases and role labels: the made-up contract fixtures' open rows, and a few made-up cases."""

from __future__ import annotations

import json
import re
from pathlib import Path

from jason.community.party_aliases import AliasKind, aliases_of, find_aliases, role_sections

FIXTURES = Path(__file__).parent / "fixtures" / "contracts"
EXPECTED = json.loads((FIXTURES / "expected.json").read_text(encoding="utf-8"))


def _text(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def _squash(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().lower()


def _sentence_with(text: str, contains: str) -> str:
    """The line holding ``contains``, up to its end (each duty in the fixture opens its own line)."""
    i = text.lower().index(contains.lower())
    return text[text.rfind("\n", 0, i) + 1:i + len(contains)]


def test_fixture_03_aliases_of_the_counterparty():
    name = "03_roof_repair_letterhead.txt"
    text, open_rows = _text(name), {**EXPECTED[name]["expect"], **EXPECTED[name]["open"]}
    found = find_aliases(text)
    counterparty = EXPECTED[name]["expect"]["counterparty"]
    others = aliases_of(counterparty, found)
    for alias in open_rows["aliases"]:
        assert alias in others, (alias, others)
    dba = [a for a in found if a.kind is AliasKind.DBA]
    assert [(a.alias, a.name) for a in dba] == [("Sample Holdings Inc.", "Example Home Services")]
    ehs = [a for a in found if a.alias == "EHS"]
    assert ehs and ehs[0].kind is AliasKind.PARENTHETICAL and ehs[0].name == "Example Home Services"
    assert text[ehs[0].start:ehs[0].end] == "EHS"


def test_fixture_03_alias_terms_and_deliverables_have_the_counterparty_as_subject():
    name = "03_roof_repair_letterhead.txt"
    text, open_rows = _text(name), {**EXPECTED[name]["expect"], **EXPECTED[name]["open"]}
    counterparty = EXPECTED[name]["expect"]["counterparty"]
    names = [counterparty.lower()] + [n.lower() for n in aliases_of(counterparty, find_aliases(text))]
    for row in open_rows["alias_terms"]:
        assert row["party"] == "counterparty"
        sentence = _squash(_sentence_with(text, row["contains"]))
        # The sentence opens with a name the counterparty goes by, written before the duty's verb.
        assert any(sentence.startswith(n) for n in names), (sentence, names)
    for deliverable in open_rows["alias_deliverables"]:
        sentence = _squash(_sentence_with(text, deliverable))
        assert sentence.startswith("ehs will provide") and "ehs" in names


def test_fixture_06_role_labels_and_the_lines_under_them():
    name = "06_implementation_role_labels.txt"
    text, open_rows = _text(name), {**EXPECTED[name]["expect"], **EXPECTED[name]["open"]}
    labels = [a for a in find_aliases(text) if a.kind is AliasKind.ROLE_LABEL]
    assert {a.alias for a in labels} == {"SAMPLE CAMERAS", "CUSTOMER"}
    by_label = {a.alias: a.name for a in labels}
    assert by_label["SAMPLE CAMERAS"] == EXPECTED[name]["expect"]["counterparty"]
    assert by_label["CUSTOMER"] == "Example Community Association"
    # The reader's party for a label: the counterparty's names, else the association.
    counterparty = EXPECTED[name]["expect"]["counterparty"]
    sections = role_sections(text)
    for row in open_rows["role_labels"]:
        hits = [s for s in sections if row["contains"].lower() in s.text.lower()]
        assert len(hits) == 1, (row, sections)
        party = "counterparty" if hits[0].label.name == counterparty else "association"
        assert party == row["party"], (row, hits[0].label)
    assert not any(s.text.startswith("Step") for s in sections)


def test_form_labels_are_not_parties():
    text = ("Re:\nRoof repair.\nDate:\nMarch 1, 2026.\nPhone:\n(555) 555-0100.\nTotal:\n$1,000.00.\n"
            "SUBJECT:\nGutter cleaning.\n")
    assert find_aliases(text) == []
    assert role_sections(text) == []


def test_d_b_a_and_doing_business_as():
    one = find_aliases("Sample Partners LLC d/b/a Example Alarm, Inc. will monitor the panel.")
    assert [(a.alias, a.name, a.kind) for a in one] == [("Sample Partners LLC", "Example Alarm, Inc.", AliasKind.DBA)]
    two = find_aliases("Contractor: Jane Example doing business as Example Painting.")
    assert [(a.alias, a.name) for a in two if a.kind is AliasKind.DBA] == [("Jane Example", "Example Painting")]


def test_quoted_short_form_and_the_party_before_it():
    found = find_aliases('This agreement is between Example Owners Association and Example Pool Co. (the "Vendor").')
    assert [(a.alias, a.name) for a in found] == [("Vendor", "Example Pool Co.")]


def test_not_short_forms():
    text = ('Work begins at 8:00 (AM) daily. Fees are listed in Schedule B (see attached). Payment is due in '
            'thirty (30) days. Sample Co., hereinafter ("SC"), agrees. THIS SERVICE AGREEMENT ("Agreement") applies.')
    assert find_aliases(text) == []


def test_a_heading_label_that_names_no_party_is_not_a_role():
    text = "WARRANTY:\nAll work is warranted for one year.\nEXCLUSIONS:\nPainting is not included.\n"
    assert find_aliases(text) == []


def test_aliases_of_follows_both_directions():
    text = "Sample Holdings Inc. dba Example Alarm (EA) will install the panel. EA will monitor it."
    found = find_aliases(text)
    assert set(aliases_of("EA", found)) == {"Example Alarm", "Sample Holdings Inc."}
    assert set(aliases_of("Sample Holdings Inc.", found)) == {"Example Alarm", "EA"}
    assert aliases_of("Example Owners Association", found) == []
