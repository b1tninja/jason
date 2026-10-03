"""Mystique's assignments: who does each duty and when (``jason.community.schedule``).

Every row is jason's proposal (October 2, 2026) until the board adopts it; the board's canvas
(``mystique/notes/canvas/governing-document-duties.md``) carries the questions behind them. A role is the office;
who holds it is the board's record. Rows cover the duties by statute, by governing-document section, by the notice
catalog's key, and by the recurring deadlines' names (``obligations.py``).
"""

from __future__ import annotations

from jason.community.schedule import Adoption, Anchor, Assignment, Role, Trigger

ASSIGNMENTS = (
    # Money: the board's monthly review, the annual reports, the reserve plan.
    Assignment("monthly-financial-review", "The board's monthly review of the financial documents", Role.TREASURER,
               ("CIV 5500", "CIV 5501", "bylaws#9.6"), Trigger.ANCHORED, anchor=Anchor.BOARD_MEETING,
               evidence="the minutes: the review, or its 5501 ratification", backup=Role.BOARD,
               jason="jason reconcile --fetch; jason report treasurers-report period=previous-month",
               note="Monthly by statute; bylaws 9.6 says quarterly (conflict bylaws-quarterly-review)."),
    Assignment("annual-budget-report", "The annual budget report and policy statement", Role.TREASURER,
               ("CIV 5300", "CIV 5310", "notice:annual-budget-report", "notice:annual-policy-statement",
                "notice:collection-policy-notice", "notice:penalty-schedule", "notice:dispute-resolution-summary",
                "notice:architectural-requirements", "obligation:Annual budget report and policy statement",
                "collection-policy#3", "bylaws#9.2", "bylaws#9.5", "bylaws#9.7", "bylaws#9.9", "bylaws#9.10",
                "bylaws#9.11", "bylaws#9.12", "bylaws#9.13", "notice:annual-report-8321"),
               Trigger.ANCHORED, anchor=Anchor.FISCAL_YEAR_END, offset_days=-30,
               evidence="the packet as mailed, and its notice proof (jason notices KEY --proof)",
               note="Due 30 to 90 days before the fiscal year ends; the date shown is the last day."),
    Assignment("reserve-investment-review", "The yearly review of the reserve investment plan", Role.TREASURER,
               ("resolution-policy-resolution-fiscal-management-17d3#INVESTMENT OF RESERVE FUNDS",),
               Trigger.ANCHORED, anchor=Anchor.FISCAL_YEAR_END, offset_days=-90,
               evidence="the minutes", note="Proposed alongside the budget, when the reserve plan is reviewed."),
    Assignment("reviewed-financial-statement", "The reviewed financial statement", Role.TREASURER,
               ("CIV 5305", "obligation:Reviewed financial statement", "notice:financial-review"),
               Trigger.ANCHORED, anchor=Anchor.FISCAL_YEAR_END, offset_days=120,
               evidence="the CPA's review, distributed with its notice proof"),
    Assignment("reserve-study", "The reserve study with a visual inspection, at least every three years", Role.BOARD,
               ("CIV 5550", "bylaws#9.3", "resolution-policy-resolution-fiscal-management-17d3#RESERVE STUDY"),
               Trigger.EVENT, handled_by="jason reserve-study: the next site visit falls due three years after the last",
               evidence="the study on disk", note="The resolution's 'may' yields to 5550(a) (conflict "
               "resolution-reserve-study-discretion)."),
    Assignment("reserve-funds", "Reserve funds spent only for their purposes; a transfer repaid within a year",
               Role.BOARD, ("CIV 5510", "CIV 5515", "CIV 5520", "bylaws#9.4", "notice:reserve-transfer-consideration",
                            "resolution-special-resolution-borrowing-reserve-funds-for-n-1nkq",
                            "resolution-special-resolution-borrowing-reserve-funds-for-p-1af1",
                            "notice:litigation-reserve-use"),
               Trigger.EVENT, handled_by="jason reserve-transfers: a transfer's notice before the meeting, and its "
               "repayment within a year", evidence="the minutes and the ledger"),
    Assignment("taxes", "Property and income taxes", Role.TREASURER,
               ("resolution-special-resolution-irs-70-604-resolution-2025-1rpf",
                "obligation:Property tax, first installment (common-area parcels)",
                "obligation:Property tax, second installment (common-area parcels)",
                "obligation:Income tax payments (IRS, FTB)", "obligation:Income tax returns prepared"),
               Trigger.EVENT, handled_by="jason deadlines (the obligation rows' own dates)",
               evidence="the PayHOA payments the obligation rows read"),
    # Meetings and records.
    Assignment("board-meeting-notice", "Notice and agenda of each board meeting", Role.SECRETARY,
               ("CIV 4920", "notice:board-meeting", "notice:board-meeting-executive", "notice:teleconference-meeting",
                "bylaws#7.5", "bylaws#7.6"),
               Trigger.ANCHORED, anchor=Anchor.BOARD_MEETING, offset_days=-4,
               evidence="the posting and the notice proof", jason="jason board --agenda DOC --doc; jason calendar"),
    Assignment("minutes-available", "Minutes available to members within 30 days", Role.SECRETARY,
               ("CIV 4950", "notice:minutes-available", "bylaws#7.11"),
               Trigger.ANCHORED, anchor=Anchor.BOARD_MEETING, offset_days=30, evidence="the minutes posted",
               jason="jason meetings (the 30-day check)"),
    # Corp. Code 8210(a), (c) (read on leginfo October 2, 2026): within 90 days of the original articles, then biennially
    # in the filing period, the month the articles were filed and the five months before it; Civil Code 5405(b): the
    # SI-CID goes in at the same time. The articles were filed May 16, 2007 (the endorsed copy in the library), so the
    # period is December 1 to May 31 of each odd year. The last filing is the SI-CID filed May 5, 2025 (bizfile's
    # approval, document BA20251018479, attached to the PayHOA payment of May 12, 2025); the next is due by May 31, 2027.
    Assignment("statement-of-information", "The Secretary of State's statement of information and SI-CID",
               Role.SECRETARY, ("CIV 5405", "obligation:Statement of information and SI-CID"),
               Trigger.CADENCE, every_months=24, month=5, day=31, from_year=2027,
               evidence="bizfile's approval of the filing", jason="jason deadlines",
               note="Corp. Code 8210(a), (c); Civil Code 5405(b). The filing period opens December 1 of the year before; "
                    "the date shown is its last day."),
    Assignment("records-requests", "Members' records requests, answered on the statute's clocks", Role.SECRETARY,
               ("CIV 5205", "CIV 5210", "bylaws#9.1", "bylaws#12", "notice:records-current-year",
                "notice:records-prior-years", "notice:records-committee-minutes", "notice:records-withheld-explanation",
                "notice:membership-list-alternative", "notice:resale-documents"),
               Trigger.EVENT, handled_by="the response handler (PayHOA requests)", backup=Role.MANAGER,
               evidence="the request, its answer, and the dates"),
    Assignment("rule-changes", "Operating rule changes: notice, adoption, and the reversal vote", Role.SECRETARY,
               ("CIV 4360", "CIV 4365", "bylaws#8.2", "notice:rule-change-proposed", "notice:rule-change-adopted",
                "notice:rule-change-reversal-results"),
               Trigger.EVENT, handled_by="jason rule-change", evidence="the notices' proofs and the minutes"),
    # Elections and the annual meeting.
    Assignment("annual-meeting", "The annual meeting, the election, and the organizational meeting", Role.SECRETARY,
               ("CIV 5100", "bylaws#4", "bylaws#5", "bylaws#7.1", "bylaws#10.3", "election-rules#2.4",
                "notice:member-meeting"),
               Trigger.ANCHORED, anchor=Anchor.ANNUAL_MEETING, evidence="the notice proof and the minutes",
               note="The election's own clocks run backward from the ballots; see election-cycle."),
    Assignment("election-cycle", "The election's timetable: nominations, lists, ballots, results", Role.INSPECTOR,
               ("CIV 5105", "CIV 5115", "CIV 5120", "CIV 5125", "bylaws#3.4", "bylaws#4.7", "bylaws#4.11",
                "bylaws#4.12", "bylaws#6", "election-rules",
                "notice:nomination-procedure", "notice:acclamation-initial", "notice:acclamation-reminder",
                "notice:nomination-acknowledgment", "notice:pre-ballot-notice", "notice:ballots",
                "notice:electronic-ballot-notice", "notice:electronic-opt-out-notice",
                "notice:reconvened-election-meeting", "notice:election-results", "notice:member-vote-result-request"),
               Trigger.EVENT, handled_by="the election calendar, counted back from the ballots", backup=Role.SECRETARY,
               evidence="the election materials, kept a year", note="The board names the Inspector each election."),
    Assignment("owner-information", "The annual owner information request, with the resident registration",
               Role.SECRETARY, ("CIV 4041", "notice:owner-info-solicitation", "owners-manual#B-1(d)"),
               Trigger.CADENCE, every_months=12, month=10, day=1, evidence="PayHOA's records of the answers",
               jason="jason owner-info; jason sop owner-info-cycle",
               note="Folding the resident registration into this request is a proposal (canvas item 7)."),
    # Collections, hearings, insurance, architecture: clocks events start.
    Assignment("collections", "Collections: the pre-lien notice, liens and their release, payment plans",
               Role.TREASURER, ("CIV 5650", "CIV 5660", "CIV 5665", "CIV 5673", "CIV 5675", "CIV 5685", "CIV 5700",
                                "CIV 5705", "CIV 5710", "CIV 5715", "CIV 5720", "ccrs#6", "bylaws#PAYMENTS",
                                "bylaws#MEETINGS AND PAYMENT PLANS",
                                "collection-policy", "owners-manual#B-18(C)(7)(d)", "bylaws#ASSESSMENTS AND FORECLOSURE",
                                "notice:pre-lien-notice", "notice:payment-plan-meeting", "notice:lien-copy",
                                "notice:lien-release", "notice:foreclosure-decision", "notice:notice-of-default",
                                "notice:notice-of-sale", "notice:assessment-increase",
                                "notice:emergency-assessment-resolution"),
               Trigger.EVENT, handled_by="jason association-collections; jason title-watch",
               evidence="each step's notice proof, and the recorded release"),
    Assignment("hearings", "Discipline and variance hearings, and their decisions", Role.BOARD,
               ("CIV 5850", "CIV 5855", "bylaws#8", "ccrs#4.20", "ccrs#10", "enforcement-policy", "owners-manual",
                "parking-rules", "notice:religious-item-removal",
                "notice:discipline-hearing", "notice:discipline-decision", "notice:penalty-schedule-supplement"),
               Trigger.EVENT, handled_by="jason hearing", backup=Role.SECRETARY,
               evidence="the notice proof, the minutes, the decision's proof"),
    Assignment("architecture", "Architectural, solar, and EV decisions on their clocks", Role.BOARD,
               ("CIV 4765", "CIV 4746", "CIV 714", "CIV 4745", "ccrs#5", "notice:architectural-decision",
                "notice:ev-charger-decision", "notice:ev-meter-decision", "notice:solar-decision",
                "notice:solar-building"),
               Trigger.EVENT, handled_by="the response handler (PayHOA architectural requests)", evidence="the decision"),
    Assignment("insurance", "Insurance: renewals, the 5810 notice, and the lender requirements", Role.TREASURER,
               ("CIV 5800", "CIV 5805", "CIV 5806", "CIV 5810", "ccrs#8", "ccrs#11", "ccrs#12", "bylaws#9.8",
                "notice:insurance-change", "notice:disaster-rebuild-completeness"),
               Trigger.EVENT, handled_by="jason policies; jason insurance", evidence="the declarations and notice proof"),
    # Each policy's term end, from the insurance store (insurance.py: the flood policies by building, and the master,
    # umbrella, crime, D&O, and workers' compensation terms ending September 28). People kept these as calendar events
    # ("Insurance Renewal - ..."); the action register's "Confirm the 2026-27 ... renewals" item is the bound step.
    Assignment("insurance-renewal-quotes", "Each policy's renewal: the carrier's terms or quotes, and the board's "
               "decision before the term ends", Role.TREASURER, ("ccrs#8.1", "CIV 5805"),
               Trigger.ANCHORED, anchor=Anchor.POLICY_RENEWAL, offset_days=-45, backup=Role.BOARD,
               evidence="the renewal notice or quote, and the minutes approving it", jason="jason insurance",
               note="Forty-five days ahead leaves a regular meeting before the term ends. CC&Rs 8.1 sets the coverages; "
                    "Civil Code 5805 the general liability and D&O limits that shield the volunteers."),
    Assignment("insurance-renewal-bound", "Each policy's renewal confirmed bound: the new declarations or certificate, "
               "the premium paid or financed, the policy sheet updated", Role.TREASURER, ("CIV 5810", "ccrs#8.1"),
               Trigger.ANCHORED, anchor=Anchor.POLICY_RENEWAL, offset_days=7, backup=Role.SECRETARY,
               evidence="the new declarations or certificate, and the premium's payment in PayHOA",
               jason="jason insurance; jason deadlines",
               note="A week after each term ends. If a policy lapsed or was not renewed and not replaced, Civil Code 5810 "
                    "requires notice to members as soon as reasonably practicable (notice:insurance-change); the new "
                    "number and term go into insurance.py."),
    # The reserve CD: $150,000 of reserves placed in a certificate of deposit under the Fiscal Management resolution,
    # maturing July 3 (the calendar's yearly "Certificate of Deposit Vests" event); people's "Renegotiate C/D" tasks
    # recur around it. The resolution: "All money borrowed will be restored at the end of the investment period, unless
    # the board finds that a temporary delay, and further investment would be in the best interests" of the association,
    # and "All interest accrued will be contributed to the reserve fund". It cites Civil Code 5380 (the board's written
    # approval before a transfer out of the reserve account) and 5510 (two signatures to withdraw reserve funds).
    Assignment("reserve-cd-maturity", "The reserve CD's maturity: renew, move, or redeem it on the board's written "
               "approval, with principal and interest kept in reserves", Role.TREASURER,
               ("resolution-policy-resolution-fiscal-management-17d3#INVESTMENT OF RESERVE FUNDS", "CIV 5380",
                "CIV 5510"),
               Trigger.CADENCE, every_months=12, month=7, day=3, backup=Role.BOARD,
               evidence="the minutes' approval and the bank's renewal or redemption notice", jason="jason reserves",
               note="Decided at the June meeting, before the CD renews on its own terms; the yearly investment plan "
                    "review (reserve-investment-review) can be held at the same time."),
    # IRS Revenue Ruling 70-604 (1970-2 C.B. 9): the members, at a meeting, decide each year whether excess assessments
    # are returned or applied to the next year's; it matters only on Form 1120. The Form 1120-H instructions (irs.gov,
    # read October 2, 2026): "The election is made separately for each tax year", and the estimated tax requirements
    # "do not apply to homeowners associations electing to file Form 1120-H". Which form this association files is
    # not settled on disk: the 2021 and 2023 returns are 1120-H (the CPA's 2021 review; the 2023 return's letter); the
    # 2024 reserve study and annual disclosures assume 1120H; but the members voted under 70-604 on November 18, 2025,
    # the board's 2025 resolution followed, and the September 11, 2026 IRS payment is an estimated tax applied to
    # "Form 1120 Corporation Income Tax" for 2026, which an 1120-H filer need not make.
    Assignment("rev-rul-70-604", "The members' Revenue Ruling 70-604 vote on excess income, and the board's "
               "resolution, before the year ends", Role.TREASURER,
               ("Rev. Rul. 70-604", "resolution-special-resolution-irs-70-604-resolution-2025-1rpf"),
               Trigger.ANCHORED, anchor=Anchor.FISCAL_YEAR_END, offset_days=0, backup=Role.SECRETARY,
               applies_if="the association files Form 1120 for the year (the CPA confirms 1120 or 1120-H)",
               evidence="the annual meeting's minutes (the members' vote) and the signed resolution",
               note="The members vote at the annual meeting; the date shown is the fiscal year's last day. On Form "
                    "1120-H no resolution is needed (the CPA's representation letter says so)."),
    Assignment("disputes", "Internal dispute resolution and ADR", Role.BOARD,
               ("CIV 5900", "CIV 5915", "CIV 5935", "CIV 6000", "CIV 6100", "bylaws#14", "notice:meet-and-confer",
                "notice:request-for-resolution", "notice:defect-action-meeting", "notice:defect-settlement",
                "notice:defect-list-6000"),
               Trigger.EVENT, handled_by="the response handler", evidence="the meeting and its written resolution"),
    Assignment("board-meetings", "The board's meetings: held monthly, open, with executive sessions as the law allows",
               Role.BOARD, ("CIV 4900", "CIV 4910", "CIV 4923", "CIV 4930", "CIV 4935", "bylaws#7",
                            "notice:board-meeting-emergency", "notice:disaster-meeting-first"),
               Trigger.ANCHORED, anchor=Anchor.BOARD_MEETING, evidence="the minutes",
               note="Monthly in practice; Administrative Resolution 20230130-1 sets the schedule."),
    Assignment("officers-committees", "Officers elected, and committees appointed, at the organizational meeting",
               Role.BOARD, ("bylaws#10", "bylaws#11"), Trigger.ANCHORED, anchor=Anchor.ANNUAL_MEETING,
               evidence="the organizational meeting's minutes"),
    Assignment("amendments", "Amendments, restatements, and annexations: adoption, notice, recording",
               Role.SECRETARY, ("CIV 4225", "CIV 4230", "CIV 4235", "CIV 4260", "CIV 4270", "CIV 4275", "ccrs#13",
                                "ccrs#14", "ccrs#15", "bylaws#13", "ccrs-2nd-amendment", "ccrs-3rd-amendment",
                                "notice:rental-amendment-4741", "notice:developer-amendment-4230",
                                "notice:amendment-petition-hearing", "notice:amendment-recorded-4275"),
               Trigger.EVENT, handled_by="jason sop document-intake; jason living", evidence="the recorded instrument"),
    Assignment("rentals", "Rental applications and the rental cap", Role.BOARD, ("CIV 4740", "CIV 4741", "ccrs#4.15"),
               Trigger.EVENT, handled_by="jason rentals", evidence="the board's decision within the documents' days"),
    Assignment("use-restrictions", "The use restrictions and the common area, kept and enforced", Role.BOARD,
               ("ccrs#2", "ccrs#3", "ccrs#4", "ccrs#5", "ccrs#9"), Trigger.STANDING,
               handled_by="the rules and the hearings", evidence="the violation file and the minutes"),
    Assignment("general-provisions", "Definitions, purposes, and general provisions: no schedule needed", Role.BOARD,
               ("bylaws#1", "bylaws#2", "ccrs#1", "ccrs#16", "ccrs#RECITALS", "alpr-policy"), Trigger.STANDING,
               note="Readings here are mostly statements, not acts; the ALPR policy's data rules are the board's."),
    # Maintenance and inspections.
    Assignment("maintenance", "Association maintenance, pest control, and entry to units", Role.BOARD,
               ("ccrs#7", "bylaws#8.9", "notice:pesticide-unit", "notice:pesticide-common-area",
                "notice:termite-relocation", "notice:mechanics-lien-claim"),
               Trigger.EVENT, handled_by="the response handler (maintenance requests); jason pests",
               evidence="the work order, the notice of entry or pesticide application", backup=Role.MANAGER),
    # The grounds' seasonal work people kept in Google Tasks and on the calendar (read October 2, 2026): no law sets
    # these; CC&Rs 7.1(a) and 7.1(b)(v) make the landscaping the association's to maintain. Each month is when people
    # did it (tree maintenance August 11, 2025; citrus harvest by March 15, 2026; rose bushes November 2024; yard
    # waste put out January 8, 2024); the board sets its own.
    Assignment("grounds-trees", "Tree maintenance on the common area", Role.BOARD, ("ccrs#7.1(b)(v)",),
               Trigger.CADENCE, every_months=12, month=8, day=31, evidence="the landscaper's or arborist's invoice",
               note="No legal clock; the month people kept."),
    Assignment("grounds-citrus", "The citrus trees harvested", Role.BOARD, ("ccrs#7.1(b)(v)",),
               Trigger.CADENCE, every_months=12, month=3, day=15, evidence="the landscaper's invoice or a note",
               note="No legal clock; the day people kept."),
    Assignment("grounds-roses", "The rose bushes pruned", Role.BOARD, ("ccrs#7.1(b)(v)",),
               Trigger.CADENCE, every_months=12, month=11, day=30, evidence="the landscaper's invoice or a note",
               note="No legal clock; the month people kept."),
    Assignment("grounds-yard-waste", "Yard waste out after the season's pruning", Role.BOARD, ("ccrs#7.1(a)",),
               Trigger.CADENCE, every_months=12, month=1, day=15, evidence="a note",
               note="No legal clock; the month people kept."),
    Assignment("manager", "The managing agent's disclosures, when one is hired", Role.BOARD, ("CIV 5375", "CIV 5380",
               "CIV 5385", "notice:manager-disclosure"), Trigger.EVENT, handled_by="the management agreement",
               evidence="the disclosure on file"),
    Assignment("inspections", "Fire, backflow, and balcony inspections on their cycles", Role.BOARD,
               ("obligation:Backflow assembly test", "obligation:Fire alarm inspection and test",
                "obligation:Fire sprinkler quarterly inspection", "obligation:Fire sprinkler annual inspection and test",
                "obligation:Fire sprinkler five-year internal inspection",
                "obligation:Exterior elevated elements (balconies) inspection", "CIV 5551"),
               Trigger.EVENT, handled_by="jason deadlines (the obligation rows' own dates)",
               evidence="the vendor's report and its payment", note="The board names who books the vendors."),
    Assignment("owner-maintenance", "Owners' own maintenance duties (filters, inspections)", Role.OWNERS,
               ("ccrs#7.8(b)",), Trigger.STANDING,
               note="The owners' duty; a semiannual reminder by general notice is the board's choice (canvas item 7)."),
    # The declarant's era.
    Assignment("declarant", "The declarant's working capital and completion bonds", Role.BOARD,
               ("ccrs#3.7", "ccrs#6.5(g)"), Trigger.EVENT,
               handled_by="jason developer-securities: a members' petition starts the 35-to-45-day meeting clock",
               note="Proposed not applicable once the board confirms the bonds are released (canvas item 8)."),
)
