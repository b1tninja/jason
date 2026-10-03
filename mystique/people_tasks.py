"""Mystique's rules for people's own Google Tasks and calendar events (``jason.community.people_tasks``).

Written from the read of October 2, 2026 (``data/schedule/google-read.json``): the association account's "My Tasks"
list and its primary calendar. Each rule names what jason tracks the item by; the first that fits wins, so a narrow
rule comes before a broad one (an appeal of a false-alarm fee before the fire alarm, a violation notice about insurance
before insurance). A label is what a shared output prints for the title, which can name an owner or a unit. A miss
stays a miss: a title no rule fits is matched by the general rules (an action register item, an assignment's or a
recurring deadline's own title, the board meeting's words) or left untracked.
"""

from __future__ import annotations

from jason.community.people_tasks import PeopleTaskRule as R
from jason.community.people_tasks import Tracker

A, O, Q = Tracker.ASSIGNMENT, Tracker.OBLIGATION, Tracker.REQUEST

# FinCEN's beneficial ownership page (fincen.gov/boi, read October 2, 2026): the interim final rule of March 26, 2025
# exempted "All entities created in the United States", and the final rule published August 11, 2026 (effective
# August 14, 2026; Federal Register document 2026-16576) made it permanent: "U.S. companies are exempt from the
# Beneficial Ownership Information (BOI) reporting requirements". The association is a California corporation.
BOIR = ("FinCEN's rule exempts every entity created in the United States from beneficial ownership reporting (interim "
        "final rule of March 26, 2025; final rule of August 11, 2026, effective August 14, 2026; fincen.gov/boi): no "
        "report is owed")

PEOPLE_TASK_RULES: tuple[R, ...] = (
    R("boir", r"\bboir\b|beneficial ownership", "a FinCEN beneficial ownership report", retire=BOIR,
      source="fincen.gov/boi; 31 CFR 1010.380 as revised"),
    # Narrow ones first.
    R("fire-fee-appeal", r"false (fire )?alarm|appeal|fire prevention", "a fire department fee or its appeal"),
    R("violation", r"violation|notice to repair|waiver request", "an enforcement or waiver matter", A, "hearings"),
    R("hearing", r"\bhearing\b", "a board hearing", A, "hearings"),
    R("seventy-604", r"70-604", "the Revenue Ruling 70-604 resolution", A, "rev-rul-70-604", recurring=True),
    # Insurance: each renewal is a clock from the insurance store.
    R("insurance-renewal", r"insurance renewal|flood insurance|renew policy|loss run|\bfarmers\b|policy number",
      "an insurance renewal", A, "insurance-renewal-bound", recurring=True),
    # Money.
    R("reserve-cd", r"certificate of deposit|\bc/d\b|\bcd\d|reno?g[eo]?tiate c", "the reserve CD's maturity", A,
      "reserve-cd-maturity", recurring=True),
    R("reserve-study", r"reserve study", "the reserve study", A, "reserve-study", recurring=True),
    R("budget", r"^budget$|annual disclosures|budget report", "the annual budget report and disclosures", A,
      "annual-budget-report", recurring=True),
    R("property-tax", r"property tax|tax defaulted", "a property tax installment", A, "taxes", recurring=True),
    R("income-tax", r"tax return|cpa\s*/\s*taxes|review\s*(&|and)\s*tax", "the income tax return and the CPA's review",
      A, "taxes", recurring=True),
    R("collections", r"^collections$", "collections", A, "collections"),
    R("invoices", r"invoices,? and mail|mail invoices|generate invoices", "the yearly assessment invoices mailed",
      recurring=True, note="No assignment yet: the assessments' yearly billing (in September, with the resident "
                           "registration form) is a clock for the board to adopt."),
    # Filings and notices.
    R("statement-of-information", r"statement of information", "the Secretary of State's statement of information",
      A, "statement-of-information", recurring=True),
    R("agenda", r"send out agenda|\bagenda\b", "a board meeting's notice and agenda", A, "board-meeting-notice",
      recurring=True),
    R("annual-meeting", r"annual (membership )?meeting", "the annual meeting", A, "annual-meeting", recurring=True),
    R("election", r"election|ballot", "the election", A, "election-cycle", recurring=True),
    R("owner-information", r"resident registration|delivery preference|owner information", "the owner information "
      "request", A, "owner-information", recurring=True),
    R("rule-change", r"proposed rule change|draft policies", "an operating rule change", A, "rule-changes"),
    R("resale", r"demand request|questionnaire|initial request|hoa document", "an escrow's resale or demand request",
      Q, "resale documents"),
    R("declarant", r"bond release", "the declarant's bonds", A, "declarant"),
    # Life safety and maintenance.
    R("fire-alarm", r"fire alarm|supervisory alarm|alarm system|monitoring company", "the fire alarm system", A,
      "inspections", recurring=True),
    R("backflow", r"backflow", "the backflow assemblies", A, "inspections", recurring=True),
    R("sprinkler", r"sprinkler", "the fire sprinklers", A, "inspections", recurring=True),
    R("pest", r"\bpest\b|rodent|termite", "pest control", A, "maintenance"),
    R("trees", r"tree maintenance|tree trim", "tree maintenance", A, "grounds-trees", recurring=True),
    R("citrus", r"citrus", "the citrus harvest", A, "grounds-citrus", recurring=True),
    R("roses", r"\broses?\b|rose bushes", "rose pruning", A, "grounds-roses", recurring=True),
    R("yard-waste", r"yard waste|green waste", "yard waste", A, "grounds-yard-waste", recurring=True),
    R("permit", r"\bpermits?\b", "a parking or city permit"),
)

__all__ = ["PEOPLE_TASK_RULES"]
