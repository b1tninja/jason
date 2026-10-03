"""Mystique's written provisions that a higher authority displaces, wholly or in part
(``jason.community.authority_order.Conflict``). Each is followed as written except the part that yields. The rows
paraphrase; the board items they name carry the findings and the sources."""

from datetime import date

from jason.community.authority_order import Clarity, Conflict, ConflictStatus, Tier
from jason.community.lessons import Area

AB_130 = date(2025, 6, 30)          # Stats. 2025, ch. 22: Civil Code 5850 and 5855 as amended, operative

CONFLICTS = (
    Conflict(
        "rental-cap-below-floor", "CC&Rs 4.15(a)", Tier.DECLARATION,
        "As restated in 2007, caps rentals at 20 percent of the units.",
        "CIV 4741(b), (f)", Tier.STATUTE, date(2021, 1, 1),
        "A cap below 25 percent may not be adopted or enforced, and 4741(f) had the board restate it by July 1, 2022.",
        "The cap is 25 percent (leasing.py). The rest of 4.15 still governs, read against 4741(a)'s bar on "
        "unreasonable restrictions.",
        Clarity.PLAIN, ConflictStatus.RESOLVED, (Area.RENTALS, Area.OWNER_INFO, Area.GOVERNING),
        board_item="rental-cap-20-percent",
        resolved_by="the Second Amendment, adopted by the board November 16, 2023 and recorded December 6, 2023 "
                    "(202312060284), which restates 4.15(a) at 25 percent; recorded after the 4741(f) deadline"),
    Conflict(
        "fines-over-the-cap", "the 2022 Enforcement Policy and fine schedule", Tier.OPERATING_RULES,
        "Fines a safety violation up to $300, and lists late fees and interest beside the fines.",
        "CIV 5850(c)-(e)", Tier.STATUTE, AB_130,
        "A penalty is the lesser of the schedule or $100 a violation; more only for a violation that may harm health "
        "or safety, after a written finding at an open board meeting (5850(d)); no late charge or interest on a "
        "penalty (5850(e)).",
        "Fine at most $100 a violation unless the board first makes a 5850(d) finding; charge no late fee or interest "
        "on a penalty. The rest of the schedule stands until the board adopts the new policy.",
        Clarity.PLAIN, ConflictStatus.BOARD, (Area.ENFORCEMENT,), board_item="enforcement-policy-ab130"),
    Conflict(
        "per-day-fines", "the 2022 fine schedule's per-day fines; owner's manual B-18(e)", Tier.OPERATING_RULES,
        "Fines a continuing violation by the day until it is cured; B-18(e) fines an unapproved alteration not restored "
        "on the board's request $10 to $50 a day.",
        "CIV 5850(c), 5865", Tier.STATUTE, AB_130,
        "Whether a fine accruing by the day survives the $100 cap is unsettled; the bylaws allow per-day fines, and "
        "5865 says 5850 neither expands nor reduces the board's authority.",
        "Accrue no per-day fine until counsel advises; a violation that continues after the decision and its cure "
        "period is a new violation, with a new notice and hearing.",
        Clarity.UNCLEAR, ConflictStatus.COUNSEL, (Area.ENFORCEMENT,), board_item="enforcement-policy-ab130"),
    Conflict(
        "hearing-procedure", "the 2022 Enforcement Policy's hearing procedure", Tier.OPERATING_RULES,
        "Notices the hearing by first-class mail, decides within fifteen days, gives no chance to cure, and re-fines a "
        "continuing violation without a further hearing.",
        "CIV 5855(a)-(g)", Tier.STATUTE, AB_130,
        "Notice by personal delivery or the member's 4040 method; no discipline if the member cures before the "
        "hearing (5855(c)); the decision in writing within 14 days (5855(f)); no discipline without these steps "
        "(5855(g)).",
        "Follow the policy's hearing steps with the statute's: 4040 delivery of the notice stating the right to cure, "
        "the member's right to executive session, the decision within 14 days, and a hearing for each penalty.",
        Clarity.PLAIN, ConflictStatus.BOARD, (Area.ENFORCEMENT,), board_item="enforcement-policy-ab130"),
    Conflict(
        "ballot-not-suspended", "CC&Rs 2.3(d) and 10.5(c) (suspension of voting rights)", Tier.DECLARATION,
        "Let the board suspend a member's voting rights as a sanction for a violation or an unpaid assessment.",
        "CIV 5105(h)(1)", Tier.STATUTE, date(2020, 1, 1),
        "Notwithstanding any other law, a member may not be denied a ballot in an election under the Act for any "
        "reason but not being a member when ballots go out (SB 323). A suspension cannot reach those ballots.",
        "Deny no member a ballot in an election the Act governs (Civil Code 5100(a)), whatever their standing. Other "
        "suspensions (use of the recreational facilities) still follow the hearing process (5855).",
        Clarity.PLAIN, ConflictStatus.NOTED, (Area.GOVERNING, Area.ENFORCEMENT)),
    Conflict(
        "bylaws-ballot-good-standing", "Bylaws 3.6(d) (only Members in Good Standing may vote)", Tier.BYLAWS,
        "Limits the vote to members in good standing.",
        "CIV 5105(h)(1)", Tier.STATUTE, date(2020, 1, 1),
        "In an election under the Act, no member may be denied a ballot for any reason but not being a member when "
        "ballots go out; good standing cannot be a condition of that ballot.",
        "Give every member a ballot in an election the Act governs. The rest of 3.6(d) (who receives notice) still "
        "governs, read with the delivery the Act requires.",
        Clarity.PLAIN, ConflictStatus.NOTED, (Area.GOVERNING,)),
    Conflict(
        "bylaws-nomination-timetable", "Bylaws 6.1(a)-(c) (nominations, the nominating committee's report, and notice "
        "of nominees)", Tier.BYLAWS,
        "Nominations close, and the nominating committee reports its nominees, 14 days before ballots are mailed, and "
        "the nominees are noticed 7 days before.",
        "CIV 5115", Tier.STATUTE, date(2020, 1, 1),
        "The Act's election timetable (the nomination procedure, the candidate list at least 30 days before ballots, "
        "ballots at least 30 days before the deadline to vote) cannot be met on the bylaws' days.",
        "Run elections on the Act's timetable as the election rules set it; the bylaws' days yield to it.",
        Clarity.PLAIN, ConflictStatus.NOTED, (Area.GOVERNING,)),
    Conflict(
        "bylaws-action-without-meeting", "Bylaws 7.12 (board action by unanimous written consent)", Tier.BYLAWS,
        "Lets the board act without a meeting if every director consents in writing.",
        "CIV 4910", Tier.STATUTE, date(2014, 1, 1),
        "The board may not act on association business outside a meeting; unanimous written consent by email is "
        "allowed only for an emergency meeting (4910(b)).",
        "Take board action at a noticed meeting; written consent only for an emergency as 4910(b) defines it.",
        Clarity.PLAIN, ConflictStatus.NOTED, (Area.GOVERNING,)),
    Conflict(
        "bylaws-discipline-decision", "Bylaws 8.5(g) (notice of discipline within 15 days)", Tier.BYLAWS,
        "Notifies the member of discipline by personal delivery or first-class mail within 15 days of the action.",
        "CIV 5855(f)", Tier.STATUTE, date(2025, 6, 30),
        "Since AB 130 the decision goes to the member within 14 days, by personal delivery or individual delivery "
        "under 4040 (the member's chosen method).",
        "Deliver the decision within 14 days, personally or by the member's 4040 method.",
        Clarity.PLAIN, ConflictStatus.NOTED, (Area.ENFORCEMENT,), board_item="enforcement-policy-ab130"),
    Conflict(
        "bylaws-quarterly-review", "Bylaws 9.6(a)-(c) (the board's quarterly financial reviews)", Tier.BYLAWS,
        "Has the board review the reconciliations and reserve actuals against budget at least quarterly.",
        "CIV 5500, 5501", Tier.STATUTE, date(2019, 1, 1),
        "Unless the documents are more stringent, the board reviews monthly: both reconciliations, actuals against "
        "budget, the bank statements, the income and expense statement, the check register, general ledger, and "
        "delinquency report. A review outside a meeting is ratified at the next meeting, in the minutes (5501).",
        "Review the 5500 documents monthly, and record the review or its ratification in the minutes.",
        Clarity.PLAIN, ConflictStatus.NOTED, (Area.GOVERNING,)),
    Conflict(
        "resolution-reserve-study-discretion", "the Fiscal Management Resolution's reserve study paragraph",
        Tier.OPERATING_RULES,
        "Lets the board vote whether to have a reserve study and how often, and calls a physical examination preferred.",
        "CIV 5550(a)", Tier.STATUTE, date(2014, 1, 1),
        "Read to give it effect, the paragraph governs what the law leaves open (who prepares the study, studies "
        "beyond the law's). It cannot make the study at least every three years, with a visual inspection of the "
        "major components, a choice; the bylaws (9.3) agree with the statute.",
        "Have the study at least every three years with a visual inspection; the board chooses the preparer.",
        Clarity.PLAIN, ConflictStatus.NOTED, (Area.GOVERNING,)),
    Conflict(
        "collection-interest-start", "the Assessment Collection Policy's interest clause", Tier.OPERATING_RULES,
        "Starts interest on an unpaid assessment 15 days after it becomes due.",
        "CIV 5650(b)(3)", Tier.STATUTE, date(2014, 1, 1),
        "Interest, at no more than 12 percent a year, runs from 30 days after the assessment becomes due.",
        "Charge no interest before the 31st day after an assessment is due.",
        Clarity.PLAIN, ConflictStatus.NOTED, (Area.GOVERNING,)),
    Conflict(
        "disaster-reconstruction-vote", "CC&Rs 11.1(b) (rebuilding when insurance covers less than 80 percent)",
        Tier.DECLARATION,
        "Puts the rebuilding bids to a vote of the impacted members; if they reject every bid and every lesser "
        "alternative, the board, with the mortgagees' approval, may sell the whole development.",
        "CIV 4752(a)", Tier.STATUTE, date(2026, 1, 1),
        "4752 voids a provision of a governing document to the extent it prohibits, or sets conditions that have the "
        "effect of prohibiting, a substantially similar reconstruction of a residential structure destroyed or damaged "
        "in a declared disaster; 4766 sets how a body reviews one. Whether either reaches a condominium building the "
        "association rebuilds (4752 defines the structure as one on a separate interest, measured against lot lines), "
        "and whether a members' vote against the bids, or a sale under 11.1(b)(ii), is such a condition, turns on a "
        "reading.",
        "Follow 11.1 as written. After a casualty in a declared disaster, counsel reads 4752 before the bids go to the "
        "members' vote or the board acts to sell under 11.1(b)(ii); meanwhile keep reconstruction open (seek bids and "
        "the lesser alternatives), which is lawful under either reading.",
        Clarity.UNCLEAR, ConflictStatus.COUNSEL, (Area.GOVERNING,)),
    Conflict(
        "pre-2014-citations", "CC&Rs and Bylaws (their Davis-Stirling citations)", Tier.DECLARATION,
        "Cite about 60 Davis-Stirling sections by their numbers before 2014 (Civil Code 1350 to 1378).",
        "the Davis-Stirling Act as recodified (Stats. 2012, ch. 180)", Tier.STATUTE, date(2014, 1, 1),
        "No conflict of substance: each citation is read as its successor section, as the law now stands.",
        "Read each citation through jason law-history; where the successor or a later amendment changed the rule, "
        "the current text governs.",
        Clarity.RENUMBERED, ConflictStatus.BOARD, (Area.GOVERNING, Area.DOCUMENTS),
        board_item="governing-documents-old-statute-numbers"),
)
