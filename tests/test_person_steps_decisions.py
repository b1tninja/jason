"""The board's decision list for phase 2 of person steps (docs/workflows/person-steps-decisions.md): the page exists and is indexed,
lists all seven decisions with the parts a board member needs to answer each, names no fact of the profile, uses only made-up
dates, and recites a statute only in words the authorities shelf holds."""

from __future__ import annotations

import re

import pytest

from jason.community import community
from jason.community.boundary import instance_terms, repo_root, scan

ROOT = repo_root()
PAGE = "docs/workflows/person-steps-decisions.md"
TEXT = (ROOT / PAGE).read_text(encoding="utf-8") if (ROOT / PAGE).exists() else ""
SHELF = ROOT / "data" / "authorities"

TITLES = (
    "The escalation table",
    "The defaults",
    "Backups and covers",
    "Reminder email drafts",
    "A claim: a note or an assignment",
    "Snooze",
    "Who records an absence, and the command's name",
)
PARTS = ("**The question.**", "**Why it matters.**", "**Options", "**Proposed, not the law's", "**What stays true",
         "**The law and the documents.**", "**How the answer is recorded.**", "**What code changes follow.**")


def _sections() -> dict[int, str]:
    parts = re.split(r"^## (\d)\. ", TEXT, flags=re.M)
    return {int(parts[i]): parts[i + 1] for i in range(1, len(parts) - 1, 2)}


def test_the_page_exists():
    assert TEXT, f"{PAGE} is missing"


def test_the_page_is_indexed():
    for index, needle in (("docs/README.md", "workflows/person-steps-decisions.md"),
                          ("docs/workflows/README.md", "person-steps-decisions.md")):
        assert needle in (ROOT / index).read_text(encoding="utf-8"), f"{index} does not link {needle}"


def test_all_seven_decisions_are_listed_in_the_table_and_as_sections():
    sections = _sections()
    assert sorted(sections) == [1, 2, 3, 4, 5, 6, 7]
    for number, title in enumerate(TITLES, start=1):
        assert sections[number].startswith(title), f"decision {number} is not '{title}'"
    glance = TEXT.split("## The seven, at a glance", 1)[1].split("\n## ", 1)[0]
    rows = re.findall(r"^\| (\d) \|", glance, flags=re.M)
    assert rows == [str(n) for n in range(1, 8)]


def test_the_summary_table_is_near_the_top_and_how_to_answer_is_last():
    assert TEXT.index("## The seven, at a glance") < TEXT.index("## 1. ")
    last = [line for line in TEXT.splitlines() if line.startswith("## ")][-1]
    assert last == "## How to answer"
    assert "secretary" in TEXT.split("## How to answer", 1)[1] and "decides nothing" in TEXT.split("## How to answer", 1)[1]


@pytest.mark.parametrize("number", range(1, 8))
def test_each_decision_has_every_part(number):
    body = _sections()[number]
    for part in PARTS:
        assert part in body, f"decision {number} lacks {part}"
    assert re.search(r"\*\*Proposed, not the law's[^*]*\*\*", body), number


def test_the_standing_lines_are_stated():
    assert "jason sends nothing on its own" in TEXT
    assert "Directors and officers have the same access to information" in TEXT
    assert "A legal clock is never snoozable" in TEXT
    assert "held step shows its general title only" in TEXT
    assert "nothing is sent" in TEXT.lower() or "sends nothing" in TEXT.lower()


def test_the_page_names_no_instance_facts():
    found = scan(ROOT, instance_terms(community()))
    assert PAGE not in found, f"instance facts in {PAGE}: {found.get(PAGE)}"


def test_the_page_uses_only_made_up_dates():
    for real in re.findall(r"\b20\d{2}-\d{2}-\d{2}\b", TEXT):
        assert real.startswith("2099") or real == "2026-10-11", f"{real} is not a made-up 2099 date (or the drafting date)"


def test_the_page_makes_no_claim_that_a_cover_gains_authority():
    assert "gains no authority" in TEXT or "gain no authority" in TEXT
    assert "A cover **sees and asks;** it gains no authority" in TEXT


def _fold(s: str) -> str:
    s = s.replace("“", '"').replace("”", '"').replace("’", "'").replace("‘", "'")
    return re.sub(r"\s+", " ", s).strip().lower()


def test_every_recited_statute_is_in_the_shelf_text():
    """A block quote is a statute's words: each is in a file of the authorities shelf (the check `jason verify-quotes` makes; the shelf is
    on disk only where it was exported, and without it this test is skipped)."""
    if not SHELF.is_dir() or not any(SHELF.rglob("*.md")):
        pytest.skip("the authorities shelf is not exported here")
    shelf = _fold(" ".join(p.read_text(encoding="utf-8", errors="replace") for p in SHELF.rglob("*.md")))
    blocks = [_fold(b) for b in re.findall(r"^> (.+)$", TEXT, flags=re.M)]
    assert len(blocks) >= 5
    for block in blocks:
        for piece in re.split(r"\s*(?:\.\.\.|…)\s*", block):
            assert piece.rstrip(".") in shelf, f"not in the shelf text: {piece[:80]}"
