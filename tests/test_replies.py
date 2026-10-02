"""Which email the association answers, learned from its own replies."""

from __future__ import annotations

from jason.tasks.replies import _answered, party_class


def test_the_kind_of_party_prefers_the_owners_standing() -> None:
    assert party_class({"parties": ["former owner of 3048 ENCHANTED WALK (conveyed 2026-08-12)"]}) == "former owner"
    assert party_class({"parties": ["buyer of 3024 MACON DR", "owner of 3026 MACON DR"]}) == "buyer"
    assert party_class({"parties": ["owner of 3024 MACON DR", "hoa-insurance.com"], "senderKind": "insurer or insurance agency"}) == "owner"
    assert party_class({"parties": ["board member"]}) == "board member"
    assert party_class({"parties": ["hoa-insurance.com"], "senderKind": "insurer or insurance agency"}) == "insurer or insurance agency"
    assert party_class({"parties": ["somevendor.com"], "domains": ["somevendor.com"]}) == "business"
    assert party_class({"parties": ["personal"]}) == "personal"


def test_a_thread_is_answered_by_a_message_out_after_the_first_in() -> None:
    inbound = {"direction": "in", "at": "2026-09-01T10:00:00+00:00"}
    reply = {"direction": "out", "at": "2026-09-02T10:00:00+00:00"}
    earlier_out = {"direction": "out", "at": "2026-08-31T10:00:00+00:00"}
    assert _answered([inbound, reply]) == (True, 1.0)
    assert _answered([earlier_out, inbound]) == (False, None)
    assert _answered([reply]) == (False, None)
