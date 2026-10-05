"""Topic phrases: the open topic rows in tests/fixtures/contracts/expected.json, read from the fixture text, and made-up
cases of each phrase and look-alike."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from jason.community.topic_phrases import NOT_RULES, PHRASE_RULES, PhraseRule, topic_by_phrase, vetoed

FIXTURES = Path(__file__).parent / "fixtures" / "contracts"

TOPICS = {"parties and authority", "term", "renewal", "termination", "breach and cure", "notice", "payment",
          "fees and price", "price changes", "spending authority", "funds and accounts", "indemnity",
          "limits of liability", "insurance", "dispute resolution", "governing law and venue", "time to bring a claim",
          "attorney fees", "assignment", "exclusivity and no-hire", "confidentiality", "logs and rosters",
          "reports and statements", "meetings", "records", "transition at the end", "disclosures and conflicts",
          "amendment and entire agreement", "survival", "statutory notice", "scope of work"}


def _flat(s: str) -> str:
    return " ".join(s.split()).lower()


def _line(name: str, contains: str) -> str:
    """The fixture line that holds ``contains``, matched as expected.json says: case-insensitive, whitespace collapsed."""
    for line in (FIXTURES / name).read_text(encoding="utf-8").splitlines():
        if _flat(contains) in _flat(line):
            return line
    raise AssertionError(f"{contains!r} not in {name}")


def _open_topic_rows():
    expected = json.loads((FIXTURES / "expected.json").read_text(encoding="utf-8"))
    for name, entry in expected.items():
        if name.startswith("_"):
            continue
        for row in [*entry.get("expect", {}).get("topic", ()), *entry.get("open", {}).get("topic", ())]:
            yield pytest.param(name, row, id=f"{name[:2]}-{row['contains'][:30]}")


ROWS = list(_open_topic_rows())


def test_fixture_rows_found():
    names = {p.values[0][:2] for p in ROWS}
    assert {"03", "05", "06"} <= names
    assert len(ROWS) == 5


@pytest.mark.parametrize("name,row", ROWS)
def test_fixture_topic_rows(name, row):
    quote = _line(name, row["contains"])
    got = topic_by_phrase("", quote)
    if "topic" in row:
        # The fixture writes "parties" for the reader's "parties and authority".
        assert got is not None and got.startswith(row["topic"])
    if "not_topic" in row:
        assert got != row["not_topic"]
        if "topic" not in row:
            assert got is None
        # Where the reader's single words would say the wrong topic, the look-alike row says no.
        if row["not_topic"] == "breach and cure":
            assert vetoed(row["not_topic"], quote)


def test_fixture_exact_topics():
    assert topic_by_phrase("Scope of Work", _line("03_roof_repair_letterhead.txt", "Reset and secure")) == "scope of work"
    assert topic_by_phrase("", _line("05_landscape_signature_block.txt", "is made this")) == "parties and authority"
    assert topic_by_phrase("", _line("05_landscape_signature_block.txt", "materially breaches")) == "breach and cure"
    assert topic_by_phrase("", _line("06_implementation_role_labels.txt", "Standard Implementation Fee")) == \
        "fees and price"


def test_rules_name_known_topics():
    assert all(isinstance(r, PhraseRule) and r.topic in TOPICS and r.why for r in PHRASE_RULES)
    assert all(t in TOPICS for t, _ in NOT_RULES)


@pytest.mark.parametrize("quote,topic", [
    ("Either party in breach of this Agreement shall pay the other's costs.", "breach and cure"),
    ("If the Contractor breaches this Contract, the Association may withhold payment.", "breach and cure"),
    ("Vendor shall cure such default within ten (10) days.", "breach and cure"),
    ("Either party may terminate this Agreement on sixty (60) days' notice.", "termination"),
    ("Upon termination of this Agreement, Vendor shall return all keys.", "termination"),
    ("All notices shall be sent to 123 Main St, Exampletown.", "notice"),
    ("Vendor shall give written notice of any delay.", "notice"),
    ("The price includes all labor and materials.", "fees and price"),
    ("Annual Monitoring Fee: $480.00", "fees and price"),
    ("This Agreement is made and entered into this 1st day of May, 2026.", "parties and authority"),
    ("- Remove and replace 4 cracked tiles at the entry.", "scope of work"),
    ("2) Install new flashing at the north wall.", "scope of work"),
    ("This Agreement will automatically renew for successive one-year terms.", "renewal"),
    ("Example Alarm, Inc. may increase the monthly service charge once a year.", "price changes"),
    ("Unpaid balances will be charged at a rate of 1.5% per month.", "payment"),
])
def test_made_up_phrases(quote, topic):
    assert topic_by_phrase("", quote) == topic


def test_order_breach_before_termination_and_notice():
    quote = ("If either party materially breaches this Agreement and fails to cure within thirty (30) days after "
             "written notice, the other party may terminate this Agreement.")
    assert topic_by_phrase("Termination", quote) == "breach and cure"


def test_caption_used_when_words_miss():
    assert topic_by_phrase("Termination of this Agreement", "Either party may end it on thirty days.") == "termination"


@pytest.mark.parametrize("quote", [
    "The water level must not breach the top of the wall.",
    "Technician will terminate the wires at the junction box.",
    "If you notice any leaks, call the office.",
    "Vendor will secure the gate each evening.",
    "Clean up daily and keep the site tidy.",   # a work verb with no item after it is not a work-list line
    "Payment is due on receipt.",
    "",
])
def test_no_phrase(quote):
    assert topic_by_phrase("", quote) is None


@pytest.mark.parametrize("topic,quote", [
    ("breach and cure", "Vendor will secure the gate each evening."),
    ("breach and cure", "Roots may breach the sidewalk edge."),
    ("termination", "Technician will terminate the wires at the junction box."),
    ("notice", "If you notice any leaks, call the office."),
    ("assignment", "Vendor will assign a technician to the property."),
    ("meetings", "All work will be performed meeting the minimum requirements of the code."),
    ("funds and accounts", "Vendor reserves the right to substitute materials of equal quality."),
])
def test_vetoed(topic, quote):
    assert vetoed(topic, quote)


@pytest.mark.parametrize("topic,quote", [
    # A look-alike word beside a real phrase is not a veto.
    ("breach and cure", "If Vendor is in breach, the Association may secure another vendor."),
    ("breach and cure", "Contractor breaches this Agreement if it fails to secure the site."),
    ("termination", "Either party may terminate this Agreement on notice."),
    ("breach and cure", "Vendor will repair the gate."),
])
def test_not_vetoed(topic, quote):
    assert not vetoed(topic, quote)
