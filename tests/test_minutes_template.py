"""The minutes template: sections with their instructions, one list with the minutes questions, and the drafted text."""

from __future__ import annotations

from datetime import date

from jason.community.minutes_template import SECTIONS, UNKNOWN, render, uncovered
from jason.community.question_sets import MINUTES
from jason.community.questions import compare_topics, distinct_topics
from jason.tasks.meeting_agenda import minutes_template
from jason.tasks.minutes_draft import render as render_draft


def test_every_minutes_question_has_a_section_that_answers_it() -> None:
    assert uncovered(SECTIONS, tuple(q.key for q in MINUTES.questions)) == []


def test_the_template_carries_each_sections_instructions_in_braces_and_one_business_block_per_item() -> None:
    lines = render(date(2026, 10, 20), items=("Treasurer's Report", "Proposals"))
    text = "\n".join(lines)
    assert text.startswith("# DRAFT Minutes of 10/20/26")
    assert "### 1. Treasurer's Report" in text and "### 2. Proposals" in text
    assert "{A roll call: each director by name" in text and "(CIV 4935(a)-(e))" in text


def test_the_secretarys_template_adds_the_roll_call_tables() -> None:
    lines = minutes_template(date(2026, 10, 20), ["Director 1", "Director 2"], ["1. **Treasurer's Report**"], quorum=2)
    text = "\n".join(lines)
    assert "| Director 1 | | | |" in text and "Quorum: 2 directors" in text and "| Director 1 | Director 2 | Result |" in text


def test_a_decision_told_twice_is_one_topic() -> None:
    told = ["The board approved a $1,850 engagement letter for tax preparation",
            "They approved a $1,850 engagement letter for annual tax prep", "They agreed to replace the street light bulb"]
    assert len(distinct_topics(told)) == 2
    found = compare_topics(["CPA engagement letter, $1,850"], told)
    assert found["both"] == ["CPA engagement letter, $1,850"] and len(found["onlyRules"]) == 1


def test_a_drafted_section_the_record_lacks_is_a_blank_and_an_unsupported_quote_is_flagged() -> None:
    answer = {"call_to_order": {"text": "Called to order at 7:05 PM.", "quotes": ["let's call the meeting to order"]},
              "attendance": {"text": "Quorum present.", "quotes": ["we have three directors, a quorum"]},
              "business": [{"item": "Proposals", "discussion": "Discussed the roof.", "motions": []}]}
    lines, unsupported = render_draft(date(2026, 8, 18), answer, "[7:05 PM] Chair: OK, let's call the meeting to order.")
    text = "\n".join(lines)
    assert "Called to order at 7:05 PM." in text and f"## Recorded by\n\n{UNKNOWN}" in text
    assert unsupported == ["attendance"]
