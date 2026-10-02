"""A utility bill paid twice: the credit on the account's next bill, including when a month's bill is not on disk."""

from __future__ import annotations

from datetime import date

from jason.community.symbols import Utility
from jason.community.utility import UtilityBill
from jason.community.utility_payments import Payment, credit_evidence


def _bill(day: date, total: int, due: int) -> UtilityBill:
    return UtilityBill(Utility.SMUD, "3547597", f"b{day}", day, total, due_cents=due)


def test_the_credit_paid_a_missing_months_bill_and_its_remainder_shows_on_the_next_on_file() -> None:
    march = _bill(date(2024, 3, 28), 25011, 25011)
    may = _bill(date(2024, 5, 28), 25939, 25347)            # April's bill is not on disk; May shows $5.92 of credit left
    repeat = Payment(2, Utility.SMUD, date(2024, 4, 25), 25011, "SMUD")
    confirmed, notes = credit_evidence(repeat, [march], [march, may])
    assert confirmed and "no 3547597 bill on disk between 2024-03-28 and 2024-05-28" in notes[0]


def test_no_credit_on_the_very_next_bill_is_not_confirmed() -> None:
    march = _bill(date(2024, 3, 28), 25011, 25011)
    april = _bill(date(2024, 4, 26), 24419, 24419)
    repeat = Payment(2, Utility.SMUD, date(2024, 4, 25), 25011, "SMUD")
    confirmed, notes = credit_evidence(repeat, [march], [march, april])
    assert not confirmed and "that is not the second payment's credit" in notes[0]
