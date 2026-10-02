"""How Mystique's utility agencies collect a delinquent account: a recorded lien, then the tax roll.

The City of Sacramento bills water, sewer, and garbage, and the Sacramento
Area Sewer District (County Sanitation District 1, billed through the
County's Department of Finance) bills sewer service. A delinquent account
becomes a recorded utility lien (filing 401) in the agency's name, and the
agency then places the delinquency on the parcel's next secured tax bill as
a direct charge. Paid with the taxes, the lien is satisfied whether or not
the agency records a termination (filing 644).

The codes are the direct-charge codes printed on Mystique's own bills in
data/tax.db: 0202 "SACTO CITY DELQ UTILITIES" and 0411 "CSD #1 DELINQUENT
SEWER". The claimant words are the index spellings of the two agencies on
the liens joined to Mystique's owners.
"""

from __future__ import annotations

from jason.community.symbols import Building, Utility
from jason.community.tax import RollRule
from jason.community.utility import Service, UtilityAccount

UTILITY_ROLL: tuple[RollRule, ...] = (
    RollRule("0202", ("CITY OF SACRAMENTO", "CITY OF SACTO"), "City of Sacramento utilities (water, sewer, garbage)"),
    RollRule("0411", ("COUNTY OF SACRAMENTO", "COUNTY OF SACTO"), "Sacramento Area Sewer District, County Sanitation District 1, through the County Department of Finance"),
)

# What each account serves, from the board's utility sheet (the "SMUD" and "Water" tabs, read 2026-09-29), with the
# account numbers: private facts in data/spec/utility_accounts.json (jason.community.private), one row per account
# (utility, account, label, building). Only the purpose is pinned: meters, sizes, service addresses, and parcels are read
# from the bills themselves, which are the record where the sheet and a bill differ. An account the sheet does not name
# stays unlabeled until a person names it.
SMUD, CITY = Utility.SMUD, Utility.CITY_OF_SACRAMENTO


def _accounts() -> tuple[UtilityAccount, ...]:
    from jason.community.private import facts

    return tuple(UtilityAccount(Utility(r["utility"]), str(r["account"]), r.get("label", ""),
                                Building(r["building"]) if r.get("building") else None)
                 for r in facts("utility_accounts", []))


UTILITY_ACCOUNTS: tuple[UtilityAccount, ...] = _accounts()

# The PayHOA budget line (expense category) each service is budgeted and split under.
UTILITY_BUDGET_LINES: dict[Service, str] = {
    Service.ELECTRIC: "Electricity (SMUD)",
    Service.WATER_DOMESTIC: "Water - Residential",
    Service.WATER_IRRIGATION: "Water - Irrigation",
    Service.FIRE_SERVICE: "Water - Fire",
    Service.STORM_DRAINAGE: "Storm Drains",
    Service.STREET_SWEEPING: "Street Sweeping",
}
