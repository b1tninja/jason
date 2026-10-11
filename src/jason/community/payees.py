"""What kind of payee a PayHOA transaction is paid to, when no bill source owns it.

A bill source (``jason.sources``) owns a transaction when the profile's utility rules or a vendor portal's words select
it. Many payments have no source: a county tax collector's ACH, an insurer, a platform fee, an unknown company. Left
unclassified they were dropped from the attach engine's lists, so a payment with no bill could not become a work item
(docs/console/handoff-mail-and-payment-attachments.md, "Checked against the code").

A ``PayeeRule`` is one row of the profile (``Community.payee_rules()``, empty by default) that says *what description text
or PayHOA rule or category is which class of payee*. The first row that matches decides; **a miss stays a miss**, and the
engine calls it ``UNKNOWN`` and opens an investigation, never guesses. The rows are the profile's: the county tax
collector's ACH text is a row in the profile, never a pattern here.

Matching is ``TransactionRule.matches`` (the same fields, in the same way), so a row reads as the utility rules do.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Iterable

from jason.community.base import TransactionRule


class PayeeClass(Enum):
    """A closed set: what a payee is, for deciding where its bill or proof of payment is found."""

    ELECTRIC_UTILITY = "electric-utility"
    CITY_UTILITY = "city-utility"
    FIELD_VENDOR = "field-vendor"          # pest, alarms, landscaping: a vendor with a portal or emailed invoices
    INSURANCE = "insurance"
    COUNTY_TAX = "county-tax"              # property tax: the tax collector, not a utility
    GOVERNMENT = "government"              # another agency: a state tax board, a permit office
    PLATFORM_FEE = "platform-fee"          # fees with often no document to expect
    TRANSFER = "transfer"                  # between the association's own accounts: no bill exists
    BANK_ITEM = "bank-item"                # interest and bank charges: the statement is the record
    UNKNOWN = "unknown"                    # no row selected it

    @property
    def expects_bill(self) -> bool:
        """Whether a bill or invoice is the document to look for. A transfer, a bank item, and a platform fee have none
        (the statement or the ledger is the record), so they are not work items."""
        return self not in (PayeeClass.TRANSFER, PayeeClass.BANK_ITEM, PayeeClass.PLATFORM_FEE)


@dataclass(frozen=True)
class PayeeRule:
    """One class of payee and the PayHOA text that selects it. The fields are ``TransactionRule``'s."""

    payee: PayeeClass
    category_id: int | None = None
    rule_names: tuple[str, ...] = ()
    description_contains: tuple[str, ...] = ()
    description_contains_all: tuple[str, ...] = ()
    description_requires: str = ""
    description_any: tuple[str, ...] = ()
    note: str = ""                         # where the row's text comes from (a bank line, a PayHOA rule name)

    def __post_init__(self) -> None:
        if not isinstance(self.payee, PayeeClass):
            raise TypeError(f"expected PayeeClass, got {self.payee!r}")
        if self.payee is PayeeClass.UNKNOWN:
            raise ValueError("UNKNOWN is what no row selects; a row names a real class")
        if not (self.category_id is not None or self.rule_names or self.description_contains
                or self.description_contains_all or (self.description_requires and self.description_any)):
            raise ValueError("a payee row needs something to match: a category, a rule name, or description text")

    def matches(self, tx: dict[str, Any]) -> bool:
        # The same test the utility rules use: it reads only these fields, so the row is a rule.
        return TransactionRule.matches(self, tx)       # type: ignore[arg-type]


def payee_of(tx: dict[str, Any], rules: Iterable[PayeeRule]) -> PayeeClass:
    """The class of the first row that matches ``tx``; ``UNKNOWN`` when none does."""
    for rule in rules:
        if rule.matches(tx):
            return rule.payee
    return PayeeClass.UNKNOWN


__all__ = ["PayeeClass", "PayeeRule", "payee_of"]
