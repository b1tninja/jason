"""What kind of payee a bank line is, for the payments no bill source owns (jason.community.payees).

First match wins; a line no row selects is "unknown" and opens an investigation. The text is the PayHOA description the
bank prints (upper-cased by the matcher). A row says only what the payee is: it never says a bill exists.
"""

from __future__ import annotations

from jason.community.payees import PayeeClass, PayeeRule

PAYEE_RULES: tuple[PayeeRule, ...] = (
    PayeeRule(PayeeClass.TRANSFER, description_contains=("ONLINE TRANSFER",),
              note="the bank's own transfer between the association's accounts"),
    PayeeRule(PayeeClass.BANK_ITEM, description_contains=("INTEREST ADDED",), note="interest the bank adds"),
    PayeeRule(PayeeClass.PLATFORM_FEE, description_contains=("ORIG CO NAME:PAYHOA", "PMNTUS SVC FEE"),
              note="PayHOA's platform and payment-service fees"),
    PayeeRule(PayeeClass.INSURANCE, description_contains=("FEMA NFIP", "ORIG CO NAME:ARDEN INSURANCE", "ORIG CO NAME:CAIS INSURANCE"),
              note="flood program and the agency's premium drafts"),
    PayeeRule(PayeeClass.GOVERNMENT, description_contains=("FRANCHISE TAX BO",), note="the state's tax board"),
    PayeeRule(PayeeClass.FIELD_VENDOR, description_contains=("SIGNAL SERVICE",), note="the fire alarm servicer's card charges"),
)
