"""The association's recurring deadlines: what is due, under what authority, and what shows it was done.

An ``Obligation`` is one recurring deadline. It is either a fixed date each year (a property tax installment is
delinquent after December 10) or an interval from the last time it was done (a balcony inspection at least every nine
years). What shows it was done is a record jason already keeps: a PayHOA payment booked to one of its categories, or
to a payee whose name carries one of its words. An obligation no store shows (the annual budget report goes out by
mail or email) says so, rather than guessing.

The rows are the association's (``Mystique.obligations()``); insurance renewals and the reserve study's site visit
come from their own models.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum

from jason.community.applicability import ALWAYS, Condition


class Standing(Enum):
    DONE = "done"
    LATE = "done late"
    MISSED = "no evidence"
    UPCOMING = "upcoming"
    DUE_SOON = "due soon"
    OVERDUE = "overdue"
    UNTRACKED = "no store shows it"
    LISTED = "payments listed, not judged"


@dataclass(frozen=True)
class Obligation:
    """One recurring deadline.

    A fixed yearly deadline sets ``month`` and ``day``; evidence dated from ``window_days`` before it through the
    deadline shows it done on time, and evidence up to ``grace_days`` after shows it done late. An interval deadline
    sets ``every_years``, or ``every_months`` for a quarterly or semiannual item: the next is that long after the latest
    evidence, or ``first_due`` when there is none. ``done_on`` is the date the record itself gives (a report's date):
    the interval counts from it, and a payment is evidence of a later round only when it comes at least half an
    interval (at most a year) after it (the invoice for that round is paid months later). One with neither lists its payments without judging them (tax payments mix estimates and balances due, and
    a payment's date alone does not say which deadline it met).

    ``applies`` is what the deadline reaches (``jason.community.applicability``): a standard's own scope, such as a
    kind of system and the installation standards it leaves out. The default is always. A row that names a system is
    asked of each of the profile's systems (``jason.community.life_safety.applicable``), and an answer the facts on
    hand cannot give is a question for a person, never "does not apply".
    """

    name: str
    authority: str
    month: int = 0
    day: int = 0
    every_years: int = 0
    every_months: int = 0
    window_days: int = 90
    grace_days: int = 120
    categories: tuple[str, ...] = ()
    payee_words: tuple[str, ...] = ()
    first_due: date | None = None
    done_on: date | None = None
    note: str = ""
    applies: Condition = ALWAYS

    @property
    def fixed(self) -> bool:
        return bool(self.month and self.day)

    @property
    def months(self) -> int:
        """The interval in months: ``every_months``, else twelve times ``every_years``; 0 for a fixed or listed one."""
        return self.every_months or 12 * self.every_years

    def cadence(self) -> str:
        months = self.months
        if months % 12 == 0:
            years = months // 12
            return f"every {years} year{'s' if years > 1 else ''}"
        return {3: "quarterly", 6: "semiannually"}.get(months, f"every {months} months")

    @property
    def tracked(self) -> bool:
        """Whether a store shows it: payments by category or payee, or the date of the last report on record."""
        return bool(self.categories or self.payee_words or self.done_on)

    def deadline(self, year: int) -> date:
        return date(year, self.month, self.day)


__all__ = ["Obligation", "Standing"]
