"""Phrase rules over a document's own words, for the wording the agenda files taught (September 30, 2026)."""

from __future__ import annotations

import pytest

from jason.community.content import classify_text
from jason.community.symbols import DocumentKind as K


@pytest.mark.parametrize("text,kind", [
    ("January 12, 2023 Client Privileged Communication Via email only Re: Disclosure of Litigation", K.LEGAL_CORRESPONDENCE),
    ("October 10, 2024 To the Board of Directors. We are pleased to confirm our acceptance and understanding of the services",
     K.CONTRACT),
    ("Parking Permit Application Variance Needed Owner Name Resident Name", K.FORM),
    ("Home Improvement Request - Removal of plants from patio area", K.FORM),
    ("SACRAMENTO Fire Department PUBLIC NUISANCE ALARM NOTICE FIRE PREVENTION DIVISION", K.NOTICE),
    ("MYSTIQUE COMMUNITY ASSOCIATION NO VEHICLE ACCESS MAINTENANCE SCHEDULED through Apr 26", K.NOTICE),
    ("CAIS This is your Crime Invoice MAKE CHECKS PAYABLE TO: CAIS, LLC Invoice Date 09/28/2025", K.INVOICE),
])
def test_the_documents_own_words_name_its_kind(text, kind) -> None:
    assert classify_text(text)[0] is kind
