"""Utility bills: SMUD's commercial electric bill and the City of Sacramento's utility bill.

The readers already exist (``jason.community.smud_utility.Smud``, ``jason.community.city_utility.SacramentoUtilities``,
which ``jason utilities`` uses on the portal downloads); this model wraps them so a utility bill in the library or
attached to a PayHOA payment reads the same way. ``identify`` says whose bill a text is and its account; the provider's
parser reads the period, the charges by service, the meter reads, and the amount due.

The checks are the ones the readers support: the charges add to the bill's current charges, the amount due is the
current charges (a larger amount due carries a previous balance; a smaller one a credit), and the account is one the
specification lists (``Community.utility_accounts()``). No statute shapes a utility bill; the City's delinquent
charges can reach the county tax roll (``Community.utility_roll()``), which is why a carried balance is worth a look.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from jason.community.city_utility import SacramentoUtilities
from jason.community.document_models import DocumentModel, Finding, ModelContext, Severity, register
from jason.community.smud_utility import Smud
from jason.community.symbols import DocumentKind, Utility
from jason.community.utility import UtilityBill, UtilityProvider
from jason.community.utility_payments import identify

PROVIDERS: dict[Utility, UtilityProvider] = {Utility.SMUD: Smud(), Utility.CITY_OF_SACRAMENTO: SacramentoUtilities()}


@dataclass
class UtilityBillRecord:
    provider: Utility
    account: str
    account_label: str = ""           # the specification's purpose for the account ("Building 3 house meter")
    bill_date: date | None = None
    period_start: date | None = None
    period_end: date | None = None
    current_charges_cents: int | None = None
    charged_cents: int = 0            # the charge lines added up
    amount_due_cents: int | None = None
    service_address: str = ""
    parcel: str = ""
    rate_schedule: str = ""
    by_service: dict[str, int] = field(default_factory=dict)
    charges: int = 0
    meter_reads: int = 0
    bill: UtilityBill | None = field(default=None, repr=False)

    @property
    def reconciles(self) -> bool:
        return self.bill.reconciles if self.bill is not None else False


def _accounts(context: ModelContext) -> dict[tuple[Utility, str], str]:
    community = context.community
    try:
        rows = community.utility_accounts() if community is not None else ()
    except (AttributeError, TypeError):
        rows = ()
    return {(row.utility, row.account): row.label for row in rows}


class UtilityBillModel(DocumentModel):
    kind = DocumentKind.UTILITY_BILL
    name = "utility-bill"
    required = ("account", "bill_date", "period_start", "period_end", "current_charges_cents", "amount_due_cents")

    def parse(self, text: str, context: ModelContext) -> UtilityBillRecord | None:
        who = identify(text or "")
        if who is None:
            return None
        utility, account = who
        bill = PROVIDERS[utility].parse(text, account=account, source=context.name)
        if not bill.charges and not bill.total_cents and bill.due_cents is None:
            return None
        return UtilityBillRecord(
            provider=utility, account=account, account_label=_accounts(context).get((utility, account), ""),
            bill_date=bill.bill_date, period_start=bill.period_start, period_end=bill.period_end,
            current_charges_cents=bill.total_cents or None, charged_cents=bill.charged_cents, amount_due_cents=bill.due_cents,
            service_address=bill.service_address, parcel=bill.parcel, rate_schedule=bill.rate_schedule,
            by_service={service.value: amount for service, amount in bill.by_service().items()},
            charges=len(bill.charges), meter_reads=len(bill.reads), bill=bill,
        )

    def check(self, r: UtilityBillRecord, context: ModelContext) -> list[Finding]:
        found: list[Finding] = []
        current = r.current_charges_cents
        if r.charges and current is not None and not r.reconciles:
            found.append(Finding("charges-differ", f"the {r.charges} charge lines add to ${r.charged_cents / 100:,.2f}; the bill's current "
                                 f"charges are ${current / 100:,.2f}", Severity.CHECK))
        if r.amount_due_cents is not None and current is not None and r.amount_due_cents != current:
            gap = r.amount_due_cents - current
            if gap > 0:
                found.append(Finding("previous-balance", f"the amount due, ${r.amount_due_cents / 100:,.2f}, is ${gap / 100:,.2f} more than "
                                     "the current charges: a previous balance is carried, so an earlier bill was paid late or not at all",
                                     Severity.CHECK))
            else:
                found.append(Finding("credit-applied", f"the amount due, ${r.amount_due_cents / 100:,.2f}, is ${-gap / 100:,.2f} less than "
                                     "the current charges: a credit is applied", Severity.INFO))
        accounts = _accounts(context)
        if accounts and (r.provider, r.account) not in accounts:
            found.append(Finding("unknown-account", f"{r.provider.value} account {r.account} is not among the specification's utility "
                                 "accounts: name it there if it is the association's, or the bill is another customer's", Severity.CHECK))
        if r.period_start and r.period_end and r.bill_date and r.bill_date < r.period_end:
            found.append(Finding("billed-before-period-end", f"billed {r.bill_date}, before its period ends {r.period_end}", Severity.CHECK))
        return found


register(UtilityBillModel())

__all__ = ["UtilityBillRecord", "UtilityBillModel", "PROVIDERS"]
