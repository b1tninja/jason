"""Discretion and effort standards, read from the made-up contract fixtures and a few made-up sentences."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from jason.community.discretion import DISCRETION_RULES, Degree, Discretion, discretion_of, flag, holds

FIXTURES = Path(__file__).parent / "fixtures" / "contracts"


def _sentence(fixture: str, contains: str) -> str:
    text = " ".join((FIXTURES / fixture).read_text(encoding="utf-8").split())
    for sentence in re.split(r"(?<=[.!?])\s+(?=[A-Z0-9])", text):
        if contains.lower() in sentence.lower():
            return sentence
    raise AssertionError(f"{contains!r} not in {fixture}")


def _open_rows(key: str) -> list[tuple[str, dict]]:
    expected = json.loads((FIXTURES / "expected.json").read_text(encoding="utf-8"))
    return [
        (fixture, row)
        for fixture, entry in expected.items()
        if isinstance(entry, dict)
        for part in ("expect", "open")
        for row in entry.get(part, {}).get(key, [])
    ]


# Who each fixture's counterparty is, as its sentences name it; the association's own words are left out.
COUNTERPARTY = {
    "01_monitoring_second_person.txt": ("we", "Example"),
    "04_management_agreement.txt": ("Manager",),
    "06_implementation_role_labels.txt": ("Sample Cameras Group Inc.", "the technician"),
    "08_association_drafted_we.txt": ("you", "Contractor"),
}

HOLDER_WORDS = {
    "We may increase the monthly service charge at any time": "We",
    "Manager may adjust the fees in its sole discretion": "Manager",
    "Either party may terminate this Agreement for any reason": "Either party",
    "may update these terms at any time": "Sample Cameras Group Inc.",
    "When the technician deems the locations suitable": "the technician",
    "We may, but are not obligated to, inspect the work": "We",
}


def _holder_label(fixture: str, d: Discretion) -> str:
    holder = d.holder_words.lower()
    if holder.startswith(("either", "each")):
        return "either"
    counterparty = COUNTERPARTY[fixture]
    return "counterparty" if holds(d.holder_words, counterparty) else "association"


@pytest.mark.parametrize(("fixture", "row"), _open_rows("discretion"), ids=lambda v: v if isinstance(v, str) else v["contains"])
def test_fixture_discretion_rows(fixture, row):
    d = discretion_of(_sentence(fixture, row["contains"]))
    assert d is not None
    expected = row["degree"]
    if row["holder"] == "either" and expected == Degree.ONE_SIDE_CHANGE.value:
        expected = Degree.MUTUAL_CHANGE.value  # the fixture's change either party may make reads as mutual
    assert d.degree.value == expected
    assert d.holder_words == HOLDER_WORDS[row["contains"]]
    assert _holder_label(fixture, d) == row["holder"]


@pytest.mark.parametrize(("fixture", "row"), _open_rows("effort_standard"), ids=lambda v: v if isinstance(v, str) else v["contains"])
def test_fixture_effort_rows(fixture, row):
    d = discretion_of(_sentence(fixture, row["contains"]))
    assert d is not None and d.degree is Degree.EFFORT
    assert d.cue.lower() == "endeavor"
    assert _holder_label(fixture, d) == row["holder"]
    assert flag(d, COUNTERPARTY[fixture]) == "effort-standard"


def test_fixture_rows_are_covered():
    assert len(_open_rows("discretion")) == 6
    assert len(_open_rows("effort_standard")) == 1


def test_fixture_over_and_flags():
    fees = discretion_of(_sentence("04_management_agreement.txt", "Manager may adjust the fees in its sole discretion"))
    assert fees.over == "fees"
    assert flag(fees, ("Manager",)) == "vendor-unfettered-over-price"

    charge = discretion_of(_sentence("01_monitoring_second_person.txt", "We may increase the monthly service charge"))
    assert charge.over == "price"
    assert flag(charge, ("we",)) == "vendor-one-side-change"

    terms = discretion_of(_sentence("06_implementation_role_labels.txt", "may update these terms at any time"))
    assert terms.over == "terms"
    assert flag(terms, ("Sample Cameras Group Inc.",)) == "vendor-one-side-change"

    mutual = discretion_of(_sentence("04_management_agreement.txt", "Either party may terminate this Agreement"))
    assert mutual.degree is Degree.MUTUAL_CHANGE
    assert mutual.over == "termination"
    assert flag(mutual, ("Manager",)) is None  # a right either party holds is mutual

    inspect = discretion_of(_sentence("08_association_drafted_we.txt", "We may, but are not obligated to"))
    assert flag(inspect, ("you",)) is None  # the association's own permission is a power


def test_fixture_sentences_that_must_not_match():
    assert discretion_of(_sentence("04_management_agreement.txt", "will deliver services reasonably necessary")) is None


def test_fixture_prior_written_consent_is_approval_gated():
    d = discretion_of(_sentence("08_association_drafted_we.txt", "without our prior written consent"))
    assert d.degree is Degree.APPROVAL_GATED
    assert d.holder_words == "our"


@pytest.mark.parametrize(
    ("sentence", "degree", "holder", "over"),
    [
        ("Example Alarm, Inc. reserves the right to change its rates.", Degree.UNFETTERED, "Example Alarm, Inc.", "price"),
        ("At its option, Contractor may replace the panel.", Degree.UNFETTERED, "Contractor", ""),
        ("Consent shall not be unreasonably withheld, conditioned or delayed.", Degree.BOUNDED, "Consent", ""),
        ("Any change order is subject to the Board's prior written approval.", Degree.APPROVAL_GATED, "the Board's", ""),
        ("Extra work is subject to the written approval of the Association.", Degree.APPROVAL_GATED, "the Association", ""),
        ("Vendor may suspend service without notice for nonpayment.", Degree.ONE_SIDE_CHANGE, "Vendor", "termination"),
        ("Repairs will be scheduled as determined by the Manager.", Degree.JUDGMENT, "the Manager", ""),
        ("Contractor shall perform all work in a good and workmanlike manner.", Degree.QUALITY, "Contractor", ""),
        ("Contractor shall perform the work to industry standards.", Degree.QUALITY, "Contractor", ""),
        ("Contractor may, at any time and without notice, change the price.", Degree.ONE_SIDE_CHANGE, "Contractor", "price"),
        ("Prices are subject to change without notice.", Degree.ONE_SIDE_CHANGE, "Prices", "price"),
        ("All terms are subject to change at any time.", Degree.ONE_SIDE_CHANGE, "All terms", "terms"),
        ("The monthly fee may be adjusted annually.", Degree.ONE_SIDE_CHANGE, "The monthly fee", "fees"),
        ("Vendor may set the route at the Vendor's sole discretion.", Degree.UNFETTERED, "the Vendor's", ""),
        ("Vendor may change the rates at its sole discretion.", Degree.UNFETTERED, "Vendor", "price"),
        ("Visits are added at the Manager's reasonable discretion.", Degree.BOUNDED, "the Manager's", ""),
        ("Extra visits are added at the Manager's discretion.", Degree.JUDGMENT, "the Manager's", ""),
        ("Contractor will try to finish by June 1.", Degree.EFFORT, "Contractor", ""),
        ("Either party may terminate this Agreement for any reason.", Degree.MUTUAL_CHANGE, "Either party", "termination"),
        ("Example Paving Co. will use commercially reasonable efforts to finish by June 1.", Degree.EFFORT, "Example Paving Co.", ""),
    ],
)
def test_made_up_sentences(sentence, degree, holder, over):
    d = discretion_of(sentence)
    assert d is not None
    assert (d.degree, d.holder_words, d.over) == (degree, holder, over)


@pytest.mark.parametrize(
    "sentence",
    [
        "Contractor shall complete the work at 123 Main St by June 1.",
        "The Association may terminate this Agreement upon thirty (30) days written notice.",
        "Any notice shall be deemed received three days after mailing.",
        "Payment is due within thirty days of the invoice date.",
        "Contractor may terminate the hose at the valve at any time.",
        "This Agreement may be modified only by a writing signed by both parties.",
        "Prices are subject to change after the first year by written amendment.",
    ],
)
def test_made_up_sentences_that_must_not_match(sentence):
    assert discretion_of(sentence) is None


def test_comma_clause_change_is_flagged():
    d = discretion_of("Contractor may, at any time and without notice, change the price.")
    assert flag(d, ("Contractor",)) == "vendor-one-side-change"


def test_over_comes_from_the_object_not_the_verb():
    d = discretion_of("Vendor may terminate the services at any time.")
    assert (d.degree, d.over) == (Degree.ONE_SIDE_CHANGE, "termination")
    raise_rate = discretion_of("Vendor may raise the hourly rate without notice.")
    assert raise_rate.over == "price"


def test_quality_and_mutual_are_not_flagged():
    quality = discretion_of("Vendor shall perform the work in a workmanlike manner.")
    assert quality.degree is Degree.QUALITY and flag(quality, ("Vendor",)) is None
    mutual = discretion_of("Each party may terminate this Agreement without cause.")
    assert mutual.degree is Degree.MUTUAL_CHANGE and flag(mutual, ("Vendor",)) is None


def test_holds_is_public_and_the_private_alias_remains():
    from jason.community import discretion

    assert discretion._holds is holds
    assert holds("Vendor", ("Vendor",)) and holds("our", ("we",))
    assert not holds("Either party", ("Vendor",))


def test_association_discretion_is_not_flagged():
    d = discretion_of("The Association may adjust the fees in its sole discretion.")
    assert d.degree is Degree.UNFETTERED
    assert flag(d, ("Example Alarm, Inc.",)) is None


def test_unfettered_over_schedule_is_not_flagged():
    d = discretion_of("Vendor may set the visit schedule in its sole discretion.")
    assert d.over == "schedule"
    assert flag(d, ("Vendor",)) is None


def test_rules_are_rows():
    assert all(isinstance(degree, Degree) and isinstance(pattern, str) for degree, pattern in DISCRETION_RULES)
    # A mutual change is a one-side change row read with a mutual holder, so no row names it.
    assert {degree for degree, _ in DISCRETION_RULES} == set(Degree) - {Degree.MUTUAL_CHANGE}
