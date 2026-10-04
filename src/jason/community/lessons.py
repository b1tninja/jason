"""What a mistake taught: the rule it broke, how it was found, and what now keeps it from coming back.

A lesson names no association. It points at the rule in AGENTS.md, the code that holds the fix, and the
test that guards it, so the next change reads the guard before it repeats the mistake.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class Lesson:
    """One mistake and its guard. ``rule`` is the AGENTS.md rule it broke; ``fix`` says where the fact went;
    ``guard`` is the test that fails if it returns."""

    key: str
    learned: date
    rule: str
    mistake: str
    fix: str
    guard: str


LESSONS: tuple[Lesson, ...] = (
    Lesson(
        key="facts-in-general-patterns",
        learned=date(2026, 10, 4),
        rule="Facts are data; dependencies point one way",
        mistake="General readers matched the association's street names and its name word, with OCR's misreadings of it, "
                "in regular expressions, a stop-word list, and default arguments, and one task imported the profile's "
                "labels module by name. Another profile's letters, bills, and claims were then read as this one's, or "
                "its own name was stripped as if it were this association's.",
        fix="Community.streets() and Community.name_pattern(), empty by default, hold the facts; readers build their "
            "patterns from them at call time (base.street_words, base.alternation, base.name_regex) and take the "
            "active profile through jason.community.community(). With none set, no address or name is read: a miss.",
        guard="tests/test_profile.py: scan_code against tests/fixtures/code_boundary.json (only shrinks), the "
              "cleared modules kept out of it, and profile_imports empty",
    ),
)


def lesson(key: str) -> Lesson | None:
    """The lesson filed under ``key``, or None."""
    return next((row for row in LESSONS if row.key == key), None)
