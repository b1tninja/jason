"""Open minutes naming a member in an executive-session matter, and the general note that replaces it."""

from __future__ import annotations

from jason.tasks.minutes_privacy import hits_in

NAMES = ["Morgan Tessaly", "Riley Vantreese", "Pat Lee"]
TEXT = ("The board approved the roof repair. The board also approved offering Morgan Tessaly a payment plan to pay his "
        "outstanding balance of $9,999 over 12 months.\n● Notify Morgan Tessaly about approved payment plan\n"
        "Adjourn to executive session to discuss homeowners discipline: motion was made by Riley Vantreese, Board President.\n"
        "Pat Lee asked about the pool schedule.")


def test_a_named_member_in_a_confidential_matter_is_found_and_a_director_acting_is_not() -> None:
    hits = hits_in(TEXT, NAMES)
    assert [h["member"] for h in hits] == ["Morgan Tessaly", "Morgan Tessaly"]
    assert hits[0]["replacement"].startswith("The board took up a member's request for an assessment payment plan")
    assert hits[1]["replacement"].startswith("Notify the member")
