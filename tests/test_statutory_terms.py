"""Each statutory term matches the constants that hold it and the words of the statute in force."""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

import pytest

from jason.community.statutory_terms import TERMS, constant, in_force

DATA = Path(__file__).resolve().parents[1] / "data"


@pytest.mark.parametrize("term", TERMS, ids=lambda t: t.name)
def test_every_constant_holds_its_terms_value(term):
    for ref in term.constants:
        assert constant(ref) == term.value, f"{ref} is {constant(ref)}; {term.citation} ({term.name}) is {term.value}"


@pytest.mark.parametrize("term", TERMS, ids=lambda t: t.name)
def test_the_statute_in_force_still_carries_the_value(term):
    from jason.tasks.export_authorities import authority_text

    found = authority_text(DATA, term.citation)
    text = found.get("text") or ""
    if not text:
        pytest.skip(f"{term.citation} is not exported here (jason export-authorities)")
    flat = re.sub(r"\s+", " ", text)
    assert re.search(term.pattern, flat, re.I), (
        f"{term.citation} no longer reads '{term.pattern}' ({term.name}); the law may have changed: "
        "read the section, update the term and its constants, and run jason law-history --sweep")


@pytest.mark.parametrize("term", TERMS, ids=lambda t: t.name)
def test_the_pattern_names_the_one_sentence_that_sets_the_clock(term):
    """A pattern that also fits another clock's sentence (another subdivision's 30 days) would still pass if only that other
    sentence were left: it matches exactly one place in the section, the one that carries this term."""
    from jason.tasks.export_authorities import authority_text

    text = authority_text(DATA, term.citation).get("text") or ""
    if not text:
        pytest.skip(f"{term.citation} is not exported here (jason export-authorities)")
    found = re.findall(term.pattern, re.sub(r"\s+", " ", text), re.I)
    assert len(found) == 1, (f"{term.citation} ({term.name}): '{term.pattern}' matches {len(found)} places; "
                             "make it the words of the one sentence that sets this clock")


def test_a_document_is_read_under_the_law_of_its_own_date():
    assert in_force("written decision after a hearing", date(2024, 11, 1)) == 15
    assert in_force("written decision after a hearing", date(2025, 6, 30)) == 14
    assert in_force("written decision after a hearing", None) == 14
    assert in_force("hearing notice", date(2020, 1, 1)) == 10
