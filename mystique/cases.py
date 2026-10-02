"""Mystique's legal matters (``Mystique.legal_cases()``).

Gathered 2026-09-29 from Gmail, the library, Drive, and the ledger, and confirmed as matters to track by the board.
Businesses are named; private persons are described by role. The duties cite the statute pages in data/authorities.
"""

from __future__ import annotations

from datetime import date

from jason.community.legal_cases import CaseDuty, CaseEvent, CaseRole, CaseStatus, Forum, LegalCase, RepairStanding, SettledItem

from .incidents import EVIDENCE

def _with_private(case: LegalCase) -> LegalCase:
    """The case with its private facts from data/spec/cases.json (jason.community.private): settlement money, the
    proceeds account, the cost of repair's items (Evidence Code 1119: for directors and counsel), insurer claim numbers,
    and events whose figures are kept out of the specification."""
    from dataclasses import replace

    from jason.community.private import facts

    private = dict(facts("cases").get(case.key) or {})
    if "settled_items" in private:
        private["settled_items"] = tuple(SettledItem(**{**s, "standing": RepairStanding(s.get("standing", RepairStanding.OPEN.value))})
                                         for s in private["settled_items"])
    if "events" in private:
        private["events"] = tuple(CaseEvent(date.fromisoformat(e["day"]), e["step"], e.get("source", "")) for e in private["events"])
    if "insurer_claims" in private:
        private["insurer_claims"] = tuple(private["insurer_claims"])
    return replace(case, **private) if private else case


_CASES: tuple[LegalCase, ...] = (
    LegalCase(
        "watt-construction-defects-2022", "Construction defect claim against the builder of buildings 1, 2, and 4-7",
        Forum.SB800, CaseRole.CLAIMANT, CaseStatus.SETTLED,
        opposing=("Watt Communities at Mystique, LLC", "WC Development Services, Inc."),
        counsel=("Berding & Weil LLP (28% contingency)", "Burke ADR (mediator)"),
        buildings=(1, 2, 4, 5, 6, 7),
        events=(
            CaseEvent(date(2022, 7, 5), "counsel's evaluation: twelve defect issues, five non-defect issues, and an action plan "
                      "(tolling agreement, limited testing with costs advanced by the firm, owner questionnaire)", "Gmail, Berding & Weil"),
            CaseEvent(date(2022, 7, 5), "draft tolling agreement", "Gmail, Berding & Weil"),
            CaseEvent(date(2022, 7, 27), "owner questionnaire", "Drive: Legal/Berding Weil - Survey.pdf"),
            CaseEvent(date(2022, 10, 24), "notice of claim to the builder (Civil Code 910)", "Gmail, Berding & Weil"),
            CaseEvent(date(2023, 1, 18), "defect report", "Gmail, Berding & Weil"),
            CaseEvent(date(2023, 1, 19), "repair cost estimate", "Gmail, Berding & Weil"),
            CaseEvent(date(2023, 5, 9), "builder's cash offer against the association's repair number without windows; counsel recommends mediation", "Gmail, Berding & Weil"),
            CaseEvent(date(2023, 7, 7), "mediation", "library: Mediation Brief 07.2023"),
            CaseEvent(date(2023, 7, 10), "settlement terms agreed", "Gmail, Berding & Weil"),
            CaseEvent(date(2023, 10, 26), "settlement agreement fully executed", "library: settlement agreement"),
            CaseEvent(date(2023, 11, 7), "net proceeds deposited to the reserve account", "prior manager's November 2023 statement"),
            CaseEvent(date(2023, 11, 15), "letter to members on the settlement", "library: settlement disclosure letter"),
            CaseEvent(date(2023, 11, 27), "counsel closes the defect file; recommends 6100 disclosure of the repairs and a review "
                      "of building conditions before the 10-year limit", "Drive: The Helsing Group/Legal/Mystique - 231127 - "
                      "Mystique Community Vs Watt Properties Closing Letter.pdf"),
        ),
        duties=(
            CaseDuty("CIV 6150", "30 days' notice to members and a meeting before filing a civil action against the builder",
                     None, "applies only before a civil action is filed; none was, because the claim settled in the builder's "
                     "prelitigation process with mediation", applies=False),
            CaseDuty("CIV 6100(a)", "inform the members in writing of the settlement with a general description of the defects to be "
                     "corrected, a good faith estimate of when, and the status of the other claimed defects", False,
                     "applies to a settlement without a lawsuit: its trigger is a settlement agreement \"or the matter has otherwise "
                     "been resolved\", on the condition that the defects \"have not been corrected\"; the chapter's heading does not narrow "
                     "it (CIV 4005). Counsel treated it as applying: the November 15, 2023 letter was sent under it. That letter gives no "
                     "description of repairs or timing and promised details later; no follow-up is on file"),
            CaseDuty("CIV 4525(a)(7)", "give buyers a copy of the latest 6100 information", False,
                     "follows from 6100: the latest 6100 information goes to buyers; not among the resale packets' attachments found"),
            CaseDuty("CIV 4177(b), 5565(b)(3)", "itemize the unspent settlement funds separately within the reserves and report them in the "
                     "reserve summary", False, "applies to settlement funds as much as to a damage award: 4177(b) reaches funds received "
                     "\"from either a compensatory damage award or settlement\" for construction or design defects, and 5565(b)(3) the same; "
                     "the 2024-2026 reserve studies and summaries do not show them"),
            CaseDuty("CIV 941(a)", "bring any remaining defect claim within 10 years after substantial completion; counsel's "
                     "closing letter recommends a review of building conditions before then", None,
                     "the claims released in the settlement stay released. The builder's six new-building permits were finaled "
                     "2020-02-24 through 2022-03-04 (Accela COM-1810922, COM-1811434, COM-1811429, COM-1811426, COM-1811415, "
                     "COM-1811385), so the earliest 10-year date is about February 2030; the prelitigation process (CIV 910) "
                     "has to start well before it, and some components have shorter periods (CIV 896). The review date is a "
                     "year ahead of the earliest limit; counsel fixes the real dates", due=date(2029, 2, 24)),
        ),
        board_item="settlement-disclosure-6100",
    ),
    LegalCase(
        "sacramento-26cv016125", "Personal injury suit after a dog attack on the property",
        Forum.SUPERIOR_COURT, CaseRole.DEFENDANT, CaseStatus.PENDING,
        court="Superior Court of California, County of Sacramento", case_number="26CV016125",
        opposing=("a resident (plaintiff), represented by Ayala, Morgan & Buzzard",),
        counsel=("Freeman Mathis & Gary (defense, through the general liability carrier)", "Berding & Weil LLP (tender advice)"),
        events=(
            CaseEvent(date(2025, 6, 5), "incident", "Drive: 26CV016125 - Dog Attack"),
            CaseEvent(date(2025, 6, 24), "evidence preservation letter", "Drive: 26CV016125 - Dog Attack"),
            CaseEvent(date(2026, 7, 6), "complaint filed; jury demanded", "Drive: 26CV016125 - Dog Attack"),
            CaseEvent(date(2026, 7, 18), "directors and officers claim tendered", "Gmail"),
            CaseEvent(date(2026, 7, 23), "demand", "Drive: 26CV016125 - Dog Attack"),
            CaseEvent(date(2026, 8, 29), "defense counsel's initial case analysis", "Gmail"),
        ),
        duties=(
            CaseDuty("the summons", "respond to the complaint within the time the summons states (30 days after service); defense "
                     "counsel files the response", None, "the date the association was served is not recorded"),
        ),
        board_item="lawsuit-26cv016125",
        drive_folder="26CV016125 - Dog Attack",
        held_back=EVIDENCE.private_names,
    ),
    LegalCase(
        "idaho-pacific-mechanics-liens-2022", "Supplier's mechanics liens against the builder's unsold units",
        Forum.RECORDED_LIEN, CaseRole.NOT_A_PARTY, CaseStatus.RESOLVED,
        opposing=("Idaho Pacific Lumber", "Watt Communities at Mystique, LLC"),
        events=(
            CaseEvent(date(2022, 3, 1), "mechanics lien recorded ($199,528.21)", "library: MECHANICS LIEN"),
            CaseEvent(date(2022, 3, 30), "second mechanics lien recorded", "library: MECHANICS LIEN"),
            CaseEvent(date(2022, 5, 3), "bond for release of lien recorded (Hanover)", "library: BOND FOR RELEASE OF LIEN 202205031077"),
        ),
        duties=(),
    ),
)

__all__ = ["LEGAL_CASES"]

LEGAL_CASES: tuple[LegalCase, ...] = tuple(_with_private(c) for c in _CASES)
