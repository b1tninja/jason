"""Views across the stores: topics, a party's brief, new owners, and what is waiting."""

from __future__ import annotations

from jason.community import mystique
from jason.community.topics import Topic, TopicRule, topics_of
from jason.tasks.party import _unit_of


def test_topics_match_at_the_start_of_a_word_and_a_subject_can_carry_two() -> None:
    rules = (TopicRule(Topic.BINS, ("bin", "garbage")), TopicRule(Topic.INSURANCE, ("insurance", "flood")))
    assert topics_of("Garbage bins", rules) == (Topic.BINS,)
    assert topics_of("Cabinet repair", rules) == ()
    assert topics_of("Bins and flood insurance", rules) == (Topic.BINS, Topic.INSURANCE)


def test_the_specification_names_the_new_owners_questions() -> None:
    rules = mystique().topic_rules()
    assert Topic.PARKING in topics_of("Need Guest Parking Permit", rules)
    assert Topic.SOLAR in topics_of("Solar Ownership Transfer with Sale", rules)
    assert Topic.INSURANCE in topics_of("Request for Current Condo Master Flood Policy", rules)
    assert topics_of("Couple of questions", rules) == ()


def test_a_party_label_names_its_units_whatever_the_owners_standing() -> None:
    assert _unit_of(["owner of 3024 MACON DR"]) == ["3024 MACON DR"]
    assert _unit_of(["former owner of 3048 ENCHANTED WALK (conveyed 2026-08-12)", "hoa-insurance.com"]) == ["3048 ENCHANTED WALK"]
    assert _unit_of(["buyer of 3024 MACON DR, 3026 MACON DR"]) == ["3024 MACON DR", "3026 MACON DR"]
    assert _unit_of(["board member", "personal"]) == []
