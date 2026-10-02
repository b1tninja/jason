"""The statutory terms jason's checks rest on, each tied to the statute's words and to the constants that hold it.

A deadline or a cap jason checks (a hearing notice 10 days ahead, a written decision within 14 days, interest from 30
days) is a number in a module. When the Legislature amends the section, the number stays put and the check goes on
applying the old law. Each ``Term`` here names the section, the value, words the section's current text must carry with
that value (``pattern``), and every constant in jason that holds it. ``tests/test_statutory_terms.py`` checks both
against the exported statute (``jason export-authorities``): a constant that differs from its term, or a statute whose
words no longer carry the value, fails the build instead of passing silently. ``jason law-history --sweep`` lists what
else cites a changed section.

A term the law changed keeps its ``prior`` value and the day the new one took effect, so a document is read under the
law of its own date: a hearing decision letter written in 2024 had 15 days, not 14 (``in_force``).
"""

from __future__ import annotations

import importlib
from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class Prior:
    value: int
    until: date                  # the day the current value took effect
    statute: str                 # the act that changed it


@dataclass(frozen=True)
class Term:
    name: str
    code: str
    section: str                 # the section whose text carries the value, e.g. "5855"
    value: int                   # in the constants' units (days, percent, cents)
    pattern: str                 # words the current text carries with the value (regex, case-insensitive)
    constants: tuple[str, ...]   # "module:ATTR" relative to jason.community
    prior: tuple[Prior, ...] = ()

    @property
    def citation(self) -> str:
        return f"{self.code} {self.section}"


_M = "models."
TERMS: tuple[Term, ...] = (
    Term("hearing notice", "CIV", "5855", 10, r"at least 10 days",
         (f"{_M}governing_rules:HEARING_NOTICE_DAYS", f"{_M}correspondence:HEARING_NOTICE_DAYS", f"{_M}meetings_notices:HEARING_NOTICE_DAYS")),
    Term("written decision after a hearing", "CIV", "5855", 14, r"within 14 days",
         (f"{_M}governing_rules:DECISION_NOTICE_DAYS", f"{_M}correspondence:DECISION_NOTICE_DAYS", f"{_M}legal_letters:DECISION_NOTICE_DAYS"),
         prior=(Prior(15, date(2025, 6, 30), "Stats. 2025, Ch. 22 (AB 130)"),)),
    Term("penalty cap per violation", "CIV", "5850", 10_000, r"one hundred dollars \(\$100\)", (f"{_M}governing_rules:PENALTY_CAP_CENTS",)),
    Term("notice of a rule change", "CIV", "4360", 28, r"at least 28 days",
         (f"{_M}governing_rules:RULE_NOTICE_DAYS", f"{_M}meetings:RULE_NOTICE_DAYS")),
    Term("assessment delinquent after", "CIV", "5650", 15, r"delinquent 15 days", (f"{_M}legal_shared:DELINQUENT_AFTER_DAYS",)),
    Term("late charge cap", "CIV", "5650", 10, r"exceeding 10 percent", (f"{_M}legal_shared:LATE_CHARGE_PERCENT",)),
    Term("interest cap", "CIV", "5650", 12, r"exceed 12 percent", (f"{_M}legal_shared:INTEREST_CAP_PERCENT",)),
    Term("interest starts after", "CIV", "5650", 30, r"commencing 30 days", (f"{_M}legal_shared:INTEREST_AFTER_DAYS",)),
    Term("pre-lien notice ahead of the lien", "CIV", "5660", 30, r"at least 30 days", (f"{_M}legal_shared:PRE_LIEN_DAYS",)),
    Term("lien mailed after recording", "CIV", "5675", 10, r"no later than 10 calendar days", (f"{_M}legal_shared:LIEN_MAIL_DAYS",)),
    Term("lien release after payment", "CIV", "5685", 21, r"within 21 calendar days", (f"{_M}legal_shared:RELEASE_DAYS",)),
    Term("payment plan meeting", "CIV", "5665", 45, r"within 45 days", (f"{_M}correspondence:PAYMENT_PLAN_MEETING_DAYS",)),
    Term("board meeting notice", "CIV", "4920", 4, r"at least four days", (f"{_M}meetings:NOTICE_DAYS", "board_calendar:NOTICE_DAYS")),
    Term("executive session notice", "CIV", "4920", 2, r"at least two days", (f"{_M}meetings:EXECUTIVE_NOTICE_DAYS",)),
    Term("minutes available", "CIV", "4950", 30, r"within 30 days", (f"{_M}meetings:MINUTES_DAYS",)),
    Term("election results notice", "CIV", "5120", 15, r"within 15 days of the election", (f"{_M}meetings_elections:RESULTS_NOTICE_DAYS",)),
    Term("ballots delivered ahead of the deadline", "CIV", "5115", 30, r"at least 30 days", (f"{_M}meetings_elections:BALLOT_DAYS",)),
    Term("notice of nominations", "CIV", "5115", 30, r"at least 30 days", (f"{_M}meetings_elections:NOMINATION_NOTICE_DAYS",)),
    Term("acclamation notice", "CIV", "5103", 90, r"at least 90 days", (f"{_M}meetings_elections:ACCLAMATION_NOTICE_DAYS",)),
    Term("records of the current year", "CIV", "5210", 10, r"within 10 business days", (f"{_M}correspondence:RECORDS_CURRENT_BUSINESS_DAYS",)),
    Term("records of prior years", "CIV", "5210", 30, r"within 30 calendar days", (f"{_M}correspondence:RECORDS_PRIOR_DAYS",)),
    Term("resale documents", "CIV", "4530", 10, r"within 10 days",
         (f"{_M}correspondence:RESALE_DOCUMENT_DAYS", f"{_M}legal_records:DOCUMENT_DAYS")),
    Term("financial review", "CIV", "5305", 120, r"within 120 days", (f"{_M}financial_annual:REVIEW_DAYS",)),
    Term("financial review threshold", "CIV", "5305", 7_500_000, r"\$75,000", (f"{_M}financial_annual:REVIEW_THRESHOLD_CENTS",)),
    Term("rental cap floor", "CIV", "4741", 25, r"less than 25 percent", (f"{_M}governing_recorded:RENTAL_FLOOR_PERCENT",)),
    Term("ADR response", "CIV", "5935", 30, r"within 30 days",
         (f"{_M}correspondence:ADR_RESPONSE_DAYS", f"{_M}legal_letters:ADR_RESPONSE_DAYS")),
    Term("mechanic's lien action", "CIV", "8460", 90, r"within 90 days", (f"{_M}legal_liens:MECHANICS_ACTION_DAYS",)),
    Term("lien release bond", "CIV", "8424", 125, r"125 percent", (f"{_M}legal_liens:BOND_PERCENT",)),
)


def constant(ref: str) -> object:
    """The value a "module:ATTR" reference holds in jason.community."""
    module, attr = ref.split(":")
    return getattr(importlib.import_module(f"jason.community.{module}"), attr)


def term(name: str) -> Term:
    return next(t for t in TERMS if t.name == name)


def in_force(name: str, on: date | None) -> int:
    """The term's value in force on a day: the prior value before the change took effect, else the current one."""
    t = term(name)
    if on is not None:
        for p in sorted(t.prior, key=lambda p: p.until):
            if on < p.until:
                return p.value
    return t.value


__all__ = ["Prior", "Term", "TERMS", "constant", "term", "in_force"]
