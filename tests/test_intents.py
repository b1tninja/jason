"""What an email asks, from its subject, and where the answer is likely written."""

from __future__ import annotations

from jason.community import mystique
from jason.community.topics import Intent, intents_of


def _intents(subject: str) -> list[Intent]:
    return list(intents_of(subject, mystique().intent_rules()))


def test_complaints_name_the_conduct() -> None:
    assert Intent.COMPLAINT in _intents("Noise complaint")
    assert Intent.COMPLAINT in _intents("Cars parked in front of my garage again")
    assert Intent.COMPLAINT in _intents("Trash cans left out")
    assert Intent.COMPLAINT in _intents("Unauthorized parking")


def test_the_associations_own_notices_are_enforcement() -> None:
    assert _intents("Notice of Violation and Disciplinary Hearing")[0] is Intent.ENFORCEMENT
    assert _intents("Courtesy Notice - Garbage Cans Left Outside")[0] is Intent.ENFORCEMENT


def test_requests_for_records_questions_and_billing() -> None:
    assert _intents("Request for Current Condo Master Flood Policy") == [Intent.INFORMATION]
    assert Intent.INFORMATION in _intents("HOA Demand and Docs Request - Order #FSSE-0100000033")
    assert Intent.INFORMATION not in _intents("Demand: MARLO ZENTHAM- DOL: 06/05/2025")
    assert _intents("Parking rules") == [Intent.QUESTION]
    assert _intents("Double Charge on HOA Fees for April") == [Intent.BILLING]


def test_every_topic_with_a_source_names_a_query() -> None:
    sources = mystique().topic_sources()
    assert all(s.query for s in sources)
    trash = next(s for s in sources if s.topic.value == "trash and bins")
    assert "trash" in trash.violation_words and "declaration" in trash.kinds
