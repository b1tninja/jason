"""The notices Mystique sends, with who receives each and how (jason.community.notices), and what its governing
documents say about notice beside the statutes (``NOTICE_PROVISIONS``).

Read from the statutes on file (data/authorities): individual delivery under 4040 for the annual budget report (5300)
and policy statement (5310), an assessment increase (5615), a lapse or cancellation of insurance (5810), and a member's
discipline (5855, one member); general notice under 4045 for a board meeting (4920) and a proposed or adopted rule
change (4360). The secondary copies of 4040(b) go only with the annual reports and the assessment collection notices
(Article 2 of Chapter 8 and 5710). A building's flood policy notice is the association's own practice, sent to that
building's owners.

The provisions are read from the outlines (data/outlines: the bylaws, election rules, enforcement and collection
policies) and the CC&Rs as amended (data/living/ccrs/current.md; its base outline's numbers where the living outline's
are garbled). Each paraphrases; quote a provision only from its text. A clause that asks more than the statute is
followed as well as the statute (``notice_catalog.effective`` takes the stricter clock); one that asks less, or differs,
is a lead for the conflict register (``conflicts.py``), and the statute governs meanwhile (Civil Code 4205).
"""

from __future__ import annotations

from jason.community.notices import (Anchor, Comparison, Method, NoticeKind, NoticeProvision, NoticeRule, Recipients,
                                     Timing)

I, G = NoticeKind.INDIVIDUAL, NoticeKind.GENERAL
MORE, SAME, LESS, DIFFERENT, RENUMBERED, OWN = (Comparison.MORE, Comparison.SAME, Comparison.LESS,
                                                Comparison.DIFFERENT, Comparison.RENUMBERED, Comparison.OWN)

NOTICE_RULES: tuple[NoticeRule, ...] = (
    # The request also goes to each secondary address on file, and (fiscal 2027, the board's call of October 1, 2026)
    # to the addresses the county roll gives for an owner, kept as unconfirmed secondary records until the owner
    # answers: the request is how the owner confirms or drops them.
    NoticeRule("owner-info-solicitation", "Owner information request", "CIV 4041(b)", I, courtesy_email=True,
               secondary_copies=True, unconfirmed_copies=True,
               note="each owner's election governs (mail without one); every owner with an email also gets a courtesy "
                    "copy with the online form's link; a copy by mail to each secondary record, unconfirmed ones too"),
    NoticeRule("annual-budget-report", "Annual budget report", "CIV 5300, 5320, 4040(b)", I, secondary_copies=True),
    NoticeRule("annual-policy-statement", "Annual policy statement", "CIV 5310, 4040(b)", I, secondary_copies=True,
               requirements=("annual-policy-statement", "collection-policy-notice", "penalty-schedule",
                             "dispute-resolution-summary", "architectural-requirements")),
    NoticeRule("assessment-increase", "Notice of an increase in assessments", "CIV 5615", I,
               note="30 to 60 days before the increase is due"),
    NoticeRule("collection-notice", "Assessment collection notice", "CIV 5650-5690, 5710, 4040(b)", I,
               secondary_copies=True, reach="one owner",
               note="the pre-lien notice also goes by certified mail (5660)",
               requirements=("pre-lien-notice", "lien-copy", "lien-release", "notice-of-default")),
    NoticeRule("insurance-change", "Insurance lapse, cancellation, or reduced coverage", "CIV 5810", I,
               note="as soon as reasonably practicable; also by first-class mail (bylaws 9.8)"),
    NoticeRule("flood-policy", "A building's flood policy", "association practice; CIV 5300(b)(9)", I, reach="unit tag",
               note="the building's owners: give its building tag"),
    NoticeRule("discipline", "Notice of hearing or decision", "CIV 5855", I, reach="one owner",
               note="10 days before the hearing; the decision within 14 days",
               requirements=("discipline-hearing", "discipline-decision")),
    NoticeRule("board-meeting", "Board meeting notice and agenda", "CIV 4920, 4045", G,
               note="posted at least 4 days before (2 for executive session only)",
               requirements=("board-meeting", "board-meeting-executive")),
    NoticeRule("rule-change", "Proposed or adopted rule change", "CIV 4360, 4045", G,
               note="30 days before the decision (bylaws 8.2(a); the statute's 28); the adopted rule within 15 days after",
               requirements=("rule-change-proposed", "rule-change-adopted")),
)


def _before(anchor: Anchor, least: int | None = None, most: int | None = None) -> Timing:
    return Timing(anchor, False, least, most)


def _after(anchor: Anchor, most: int | None = None, least: int | None = None) -> Timing:
    return Timing(anchor, True, least, most)


NOTICE_PROVISIONS: tuple[NoticeProvision, ...] = (
    # Bylaws.
    NoticeProvision(
        "bylaws-3.6a", "bylaws", "3.6(a)",
        "The board may fix a record date for notice of a members' meeting 10 to 90 days before it; otherwise the close "
        "of business the business day before notice is given.", OWN, "member-meeting",
        title="Record date for notice of a members' meeting", recipients=Recipients.ALL_MEMBERS),
    NoticeProvision(
        "bylaws-3.6cd", "bylaws", "3.6(c), 3.6(d)",
        "Only members in good standing receive written ballots and vote; notice of elections and meetings goes to "
        "members, and to mortgagees who asked.", LESS, "ballots",
        lead="A member may be denied a ballot only for not being a member when ballots go out (5105(h)(1)); the "
             "ballot-not-suspended conflict names the CC&Rs and should name these bylaws too. Read 3.6(d) as giving "
             "notice to every member and to mortgagees who asked; if it is read as limiting member notice to those "
             "who asked, 4920, 5115, and 5105(h)(4) govern."),
    NoticeProvision(
        "bylaws-4.3", "bylaws", "4.3(a), 4.3(b)",
        "Written notice of each members' meeting, mailed first class or otherwise delivered 10 to 90 days before, to "
        "the address on the books or given for notice, stating the date, hour, place, and the general nature of the "
        "business; a special meeting members call is noticed within 20 days of their request and held 35 to 90 days "
        "after it.", OWN, "member-meeting", (_before(Anchor.MEETING, 10, 90),),
        (Method.FIRST_CLASS_MAIL, Method.WRITTEN),
        ("the date, hour, and place", "the general nature of the matters the board intends to present"),
        title="Members' meeting", recipients=Recipients.ALL_MEMBERS),
    NoticeProvision(
        "bylaws-4.11", "bylaws", "4.11(b), 4.11(d)",
        "A written ballot sets out the proposed action, gives a reasonable time to return it, and states the responses "
        "needed for a quorum, the approvals needed, and when the ballot must be received.", MORE, "ballots",
        content=("the number of responses needed for a quorum", "the percentage of approvals needed",
                 "the time by which the ballot must be received")),
    NoticeProvision(
        "bylaws-6.1", "bylaws", "6.1(a), 6.1(c)",
        "Nominations close 14 days before the date set for mailing ballots, and members get notice of the nominees 7 "
        "days before that mailing.", LESS, "pre-ballot-notice",
        lead="5115(b) requires general notice of the candidates' names at least 30 days before ballots are "
             "distributed, so nominations must close more than 30 days before; the election rules (3.2.1, 2.1) follow "
             "the statute and the bylaws' timetable cannot be met as written."),
    NoticeProvision(
        "bylaws-6.7", "bylaws", "6.7", "Ballots and two envelopes mailed first class or delivered at least 30 days "
        "before the voting deadline.", SAME, "ballots", (_before(Anchor.VOTING_DEADLINE, 30),)),
    NoticeProvision(
        "bylaws-6.12", "bylaws", "6.12",
        "Within 15 days of the election the board publicizes the results in a communication directed to all members.",
        MORE, "election-results", (_after(Anchor.ELECTION, 15),), (Method.INDIVIDUAL,),
        lead="Read as a communication to every member, more than a posting: send the results by each member's 4040 "
             "method as well as posting them, which satisfies both."),
    NoticeProvision(
        "bylaws-7.6", "bylaws", "7.6",
        "Members get notice of the day, time, and place of each board meeting at least four days before, by posting in "
        "a prominent place in the common area and by mail to an owner who asked; also, optionally, by delivery to each "
        "residence, newsletter, or other means reasonably designed to give actual notice.", DIFFERENT, "board-meeting",
        (_before(Anchor.MEETING, 4),), (Method.POSTING, Method.FIRST_CLASS_MAIL),
        lead="Posting is general delivery only at a location the annual policy statement designates (4045(a)(3)); a "
             "member who asked gets individual delivery by their 4041 choice, not only mail (4045(b), 4040); 'other "
             "means reasonably designed' is wider than 4045(a); and the notice must carry the agenda (4920(d)), which "
             "7.6 omits."),
    NoticeProvision(
        "bylaws-7.11", "bylaws", "7.11(a), 7.11(c)",
        "Minutes, draft minutes, or a summary available within 30 days; members told annually of their right to "
        "copies, with the pro forma budget under former Civil Code 1365 or another general mailing.", RENUMBERED,
        "minutes-available", (_after(Anchor.MEETING, 30),),
        lead="The annual notice of the right to minutes is now an item of the annual policy statement (5310(a)(5), "
             "4950(b))."),
    NoticeProvision(
        "bylaws-7.12", "bylaws", "7.12",
        "The board may act without a meeting by unanimous written consent, posting an explanation within three days.",
        LESS, "board-meeting-emergency",
        lead="The board may not act outside a board meeting (4910(a)); a meeting by email is allowed only as an "
             "emergency meeting with every director's written consent filed with the minutes (4910(b)(2)). Corporations "
             "Code 7211 is overridden for an association."),
    NoticeProvision(
        "bylaws-8.2a", "bylaws", "8.2(a), 8.2(e), 12.12",
        "Written notice of a proposed rule change to the members at least 30 days before adopting it, with its text "
        "and purpose and effect, delivered by a 12.12 method.", MORE, "rule-change-proposed",
        (_before(Anchor.RULE_CHANGE, 30),), (Method.INDIVIDUAL, Method.FIRST_CLASS_MAIL),
        lead="30 days, not 28; and 12.12's methods are deliveries (mail, email a member agreed to, a newsletter), so a "
             "posting alone would not satisfy the bylaws."),
    NoticeProvision(
        "bylaws-8.2c", "bylaws", "8.2(c), 8.2(f), 8.2(g)",
        "The adopted rule change to all members within 15 days; members are deemed notified on delivery or on "
        "enforcement, whichever is sooner; a reversal request within 30 days after notice; the vote's results to every "
        "member within 15 days after voting closes.", SAME, "rule-change-adopted", (_after(Anchor.RULE_CHANGE, 15),)),
    NoticeProvision(
        "bylaws-8.5d", "bylaws", "8.5(d)",
        "Written notice of a discipline hearing at least ten days before, by personal delivery or first-class mail, "
        "with the date, time, place, nature of the violation, and the right to attend and speak.", DIFFERENT,
        "discipline-hearing", (_before(Anchor.HEARING, 10),), (Method.PERSONAL_DELIVERY, Method.FIRST_CLASS_MAIL),
        lead="5855(a) allows personal delivery or individual delivery under 4040, which follows the member's 4041 "
             "choice; first-class mail alone does not reach a member who elected email. Deliver by both. The notice "
             "also says the member may cure first and may ask for executive session (5855(b), (c)). The "
             "hearing-procedure conflict covers the enforcement policy's same text."),
    NoticeProvision(
        "bylaws-8.5e", "bylaws", "8.5(e)",
        "After emergency corrective action under the declaration, a member may request a hearing within 10 days of the "
        "notice of discipline; it is held within 30 days, and the discipline is held in abeyance until affirmed.",
        DIFFERENT, "discipline-hearing",
        lead="Whether holding discipline in abeyance until a later hearing satisfies 5855(g) (no discipline effective "
             "without the prior notice and hearing) is for counsel; corrective action that is not discipline is "
             "outside 5855."),
    NoticeProvision(
        "bylaws-8.5g", "bylaws", "8.5(g)",
        "Written notice of the discipline imposed within 15 days, by personal delivery or first-class mail.", LESS,
        "discipline-decision", (_after(Anchor.ACTION, 15),), (Method.PERSONAL_DELIVERY, Method.FIRST_CLASS_MAIL),
        lead="Within 14 days since June 30, 2025 (5855(f), AB 130), by personal delivery or the member's 4040 method."),
    NoticeProvision(
        "bylaws-8.9", "bylaws", "8.9",
        "Entry into a unit for repairs on reasonable written notice of at least 24 hours, except in an emergency.", OWN,
        title="Notice of entry for repairs", recipients=Recipients.MEMBER, methods=(Method.WRITTEN,)),
    NoticeProvision(
        "bylaws-9.2", "bylaws", "9.2, 9.2(c)",
        "The pro forma budget 30 to 90 days before the fiscal year begins, or a summary with a 10-point bold notice "
        "that the full budget is available; a copy mailed first class within five days of a member's request, at the "
        "association's expense.", MORE, "annual-budget-report", (_before(Anchor.FISCAL_YEAR_END, 30, 90),),
        lead="The five-day turnaround on a request for the full budget is the bylaws' own."),
    NoticeProvision(
        "bylaws-9.7", "bylaws", "9.7(a), 9.7(b)",
        "The annual report within 120 days after the fiscal year, sent on request; the reviewed financial statement to "
        "all members within 120 days.", SAME, "financial-review", (_after(Anchor.FISCAL_YEAR_END, 120),)),
    NoticeProvision(
        "bylaws-9.8", "bylaws", "9.8",
        "The insurance summary 30 to 90 days before the fiscal year; notice by first-class mail as soon as reasonably "
        "practicable of a lapse, cancellation, or significant change; immediately on a nonrenewal without replacement.",
        MORE, "insurance-change", methods=(Method.FIRST_CLASS_MAIL,),
        lead="5810 sends it by individual delivery (the member's 4041 choice); the bylaws add first-class mail. "
             "Send both. It cites former Civil Code 1365."),
    NoticeProvision(
        "bylaws-9.9", "bylaws", "9.9",
        "Annual notices of lien enforcement, the ADR summary, the fine procedures, insurance, and the assessment and "
        "foreclosure notice, by their former Civil Code numbers.", RENUMBERED, "annual-policy-statement",
        lead="Each is now an item of the annual policy statement (5310(a)(6)-(9), 5730, 5850, 5920, 5965)."),
    NoticeProvision(
        "bylaws-9.9g", "bylaws", "9.9(g)",
        "The assessment and foreclosure notice, in 12-point type, distributed during the 60 days before the fiscal "
        "year begins.", MORE, "collection-policy-notice", (_before(Anchor.FISCAL_YEAR_END, None, 60),),
        lead="With 5310's 30 to 90 days, the annual policy statement that carries it goes out 30 to 60 days before "
             "the fiscal year begins."),
    NoticeProvision(
        "bylaws-9.9h", "bylaws", "9.9(h)",
        "Annually, the requirements for approval of physical changes and the review procedure.", SAME,
        "architectural-requirements"),
    NoticeProvision(
        "bylaws-9.10", "bylaws", "9.10",
        "Written notice to each owner, before each fiscal year, of the regular assessment for the unit.", OWN,
        title="Regular assessment for the year", recipients=Recipients.ALL_MEMBERS, methods=(Method.WRITTEN,)),
    NoticeProvision(
        "bylaws-12.2", "bylaws", "12.2", "Copies of specifically identified records may be mailed by first-class mail.",
        DIFFERENT, "records-current-year",
        lead="5205(e) delivers them by individual delivery under 4040, the member's 4041 choice."),
    NoticeProvision(
        "bylaws-12.7", "bylaws", "12.7(b)",
        "Records produced within 10 business days (current year), 30 calendar days (two prior years), and committee "
        "minutes within 15 calendar days of approval.", SAME, "records-current-year"),
    NoticeProvision(
        "bylaws-12.12", "bylaws", "12.12(a)-(c)",
        "Notices and documents go by personal delivery, first-class mail, email or other electronic means the member "
        "agreed to, a periodical, a recorded method, or another method the member agreed to; an unrecorded provision is "
        "not agreement.", DIFFERENT, "",
        title="How notices are delivered", recipients=Recipients.ALL_MEMBERS,
        lead="This follows 4040 as it read before 2023. Individual delivery now follows the member's 4041 choice of "
             "mail or email, else first-class mail to the address on the books (4040(a)); personal delivery is "
             "individual delivery only where a section names it (5855, 4785). 12.12(c) matches 4040(c)."),
    # Election rules.
    NoticeProvision(
        "election-rules-2", "election-rules", "1.2, 2.1, 2.2, 2.3, 2.7, 3.2.1",
        "The voter list open to verification 30 days before ballots; the pre-ballot notice 30 days before ballots; "
        "ballots 30 days before the voting deadline; the acclamation notices at 90 and 7 to 30 days; nominations "
        "acknowledged within 7 business days; results within 15 days; the call for candidates 30 days before the "
        "nomination deadline.", SAME, "pre-ballot-notice", (_before(Anchor.BALLOTS_DISTRIBUTED, 30),)),
    NoticeProvision(
        "election-rules-8", "election-rules", "8.3, 8.4, 8.12, 8.13",
        "Members are deemed to choose electronic ballots unless they opt for paper at least 90 days before an "
        "election; electronic ballots go out 30 days before; individual notice 30 days before the deadline to change.",
        SAME, "electronic-opt-out-notice", (_before(Anchor.OPT_OUT_DEADLINE, 30),)),
    NoticeProvision(
        "election-rules-8.18", "election-rules", "8.18",
        "Members who vote electronically agree to receive all election notices electronically.", DIFFERENT,
        "pre-ballot-notice",
        lead="An unrecorded rule's method is not a member's agreement (4040(c)); individual delivery follows the "
             "member's 4041 choice. Whether opting into electronic voting is the member's own choice of email for "
             "election notices is for counsel; until then, deliver by the 4041 choice."),
    # The enforcement and collection policies.
    NoticeProvision(
        "enforcement-policy-due-process", "enforcement-policy", "(b) Due Process Requirements",
        "A Notice of Board Hearing mailed at least ten days before, delivered personally or by first-class mail, with "
        "the provision allegedly violated; the decision within fifteen days after the hearing.", LESS,
        "discipline-hearing", (_before(Anchor.HEARING, 10),), (Method.PERSONAL_DELIVERY, Method.FIRST_CLASS_MAIL),
        ("a reference to the provision allegedly violated",),
        lead="Already the hearing-procedure conflict (5855(a)-(g)); the content it adds (the provision's reference) "
             "is followed."),
    NoticeProvision(
        "collection-policy-3", "collection-policy", "3",
        "Notice of the regular assessment 30 to 90 days before the fiscal year begins; an increase or a special "
        "assessment 30 to 60 days before it is due (5615).", SAME, "assessment-increase",
        (_before(Anchor.DUE_DATE, 30, 60),)),
    NoticeProvision(
        "collection-policy-6", "collection-policy", "6",
        "Interest on the unpaid balance begins 15 days after the assessment is due.", LESS, "pre-lien-notice",
        lead="Interest commences 30 days after the assessment becomes due (5650(b)(3)). The CC&Rs 6.11 the policy "
             "cites makes an installment delinquent at 15 days, subject to interest and late charges within what the "
             "law permits; the law starts interest at 30."),
    NoticeProvision(
        "collection-policy-10", "collection-policy", "10",
        "Once 30 days past due, a pre-lien notice by certified mail: a lien will be recorded unless paid within 30 "
        "days; with the policy and an itemized statement.", SAME, "pre-lien-notice",
        (_before(Anchor.LIEN_RECORDING, 30),), (Method.CERTIFIED_MAIL,)),
    NoticeProvision(
        "collection-policy-12", "collection-policy", "12",
        "The lien recorded after the board decides in an open meeting; a copy by certified and first-class mail to all "
        "record owners within 10 calendar days.", MORE, "lien-copy", (_after(Anchor.LIEN_RECORDING, 10),),
        (Method.CERTIFIED_MAIL, Method.FIRST_CLASS_MAIL),
        lead="Adds first-class mail. Before recording, the association still offers meet and confer (5670)."),
    NoticeProvision(
        "collection-policy-5730", "collection-policy", "(5730 notice)",
        "The assessments and foreclosure notice goes to each member during the 60 days before the fiscal year.", MORE,
        "collection-policy-notice", (_before(Anchor.FISCAL_YEAR_END, None, 60),)),
    # The CC&Rs as amended.
    NoticeProvision(
        "ccrs-3.6", "ccrs", "3.6",
        "A mechanic's lien recorded against the common area for an owner's work: written notice to discharge it within "
        "five days, with a hearing before the board in that time.", OWN, "mechanics-lien-claim",
        title="Owner's lien on the common area", recipients=Recipients.MEMBER, methods=(Method.WRITTEN,)),
    NoticeProvision(
        "ccrs-3.7b", "ccrs", "3.7(b)",
        "On a petition of 5 percent of the voting power, a special meeting on enforcing a completion bond, 35 to 45 "
        "days after the petition, noticed as the bylaws provide for special meetings.", OWN, "member-meeting",
        title="Special meeting on a completion bond", recipients=Recipients.ALL_MEMBERS),
    NoticeProvision(
        "ccrs-4.15e", "ccrs", "4.15(e), 4.15(f)",
        "The board decides an application to rent within 30 days of receipt, by written notice with reasons for a "
        "disapproval; after a rehearing, a written determination within 10 days.", OWN, "",
        (_after(Anchor.APPLICATION_RECEIVED, 30),), (Method.WRITTEN,),
        title="Decision on an application to rent", recipients=Recipients.APPLICANT),
    NoticeProvision(
        "ccrs-4.15k", "ccrs", "4.15(k)",
        "Before an eviction action, notice to the owner detailing the tenant's infraction and a chance to correct it "
        "or appear before the board.", OWN, title="Notice before an eviction action", recipients=Recipients.MEMBER,
        methods=(Method.WRITTEN,)),
    NoticeProvision(
        "ccrs-4.20", "ccrs", "4.20(a)-(c)",
        "A variance request: a denial on its face noticed within 30 days of the decision; otherwise a hearing within "
        "45 days of the request, noticed to all members at least 15 days before; the decision noticed within 30 days.",
        OWN, "", (_before(Anchor.HEARING, 15),), (Method.WRITTEN,),
        title="Variance hearing", recipients=Recipients.ALL_MEMBERS,
        lead="The section names no method for the notice to all members; whether general notice satisfies it is a "
             "question for the board (a written policy) or counsel."),
    NoticeProvision(
        "ccrs-6.5", "ccrs", "6.5",
        "The budget estimate for the year distributed to all owners 30 to 90 days before the fiscal year begins.", SAME,
        "annual-budget-report", (_before(Anchor.FISCAL_YEAR_END, 30, 90),)),
    NoticeProvision(
        "ccrs-6.12-payment-plan", "ccrs", "6.12 (payment plan)",
        "The board meets an owner on a payment plan within 45 days of the request's postmark, or a committee of one or "
        "more members when no meeting falls in the period.", DIFFERENT, "payment-plan-meeting",
        (_after(Anchor.REQUEST_MAILED, 45),),
        lead="5665(b) says a committee of one or more directors."),
    NoticeProvision(
        "ccrs-6.12-collection", "ccrs", "6.12 (notices, lien, release, secondary address)",
        "The pre-lien notice's content, the lien copy by certified mail within 10 calendar days, release within 21 "
        "days, and copies of collection notices to a secondary address the owner gives in writing.", SAME,
        "lien-copy", (_after(Anchor.LIEN_RECORDING, 10),), (Method.CERTIFIED_MAIL,),
        lead="It tells owners of the secondary-address right with the budget under former Civil Code 1365; that is "
             "now the policy statement (5310(a)(2))."),
    NoticeProvision(
        "ccrs-6.13", "ccrs", "6.13 (decision to foreclose; notice)",
        "The foreclosure vote at least 30 days before any sale; personal service on a resident owner or the legal "
        "representative, first-class mail to a non-resident owner.", SAME, "foreclosure-decision",
        methods=(Method.PERSONAL_SERVICE, Method.FIRST_CLASS_MAIL)),
    NoticeProvision(
        "ccrs-7.2", "ccrs", "7.2",
        "Entry into a unit or exclusive use common area on reasonable written notice of at least 24 hours, except in "
        "an emergency.", OWN, title="Notice of entry", recipients=Recipients.MEMBER, methods=(Method.WRITTEN,)),
    NoticeProvision(
        "ccrs-7.6", "ccrs", "7.6",
        "Notice to an owner of maintenance the board deems necessary; after 60 days, written notice and a hearing "
        "before the association does the work and charges the owner.", OWN, "discipline-hearing",
        (_before(Anchor.HEARING, 10),), title="Owner maintenance, then a hearing before a reimbursement charge",
        recipients=Recipients.MEMBER,
        lead="A charge to the owner after a hearing: give the hearing the 5855 notice."),
    NoticeProvision(
        "ccrs-7.7", "ccrs", "7.7",
        "Vacating for wood-destroying pest treatment on 15 to 30 days' notice stating the reason, the treatment dates, "
        "and that occupants arrange their own lodging.", SAME, "termite-relocation",
        (_before(Anchor.RELOCATION, 15, 30),)),
    NoticeProvision(
        "ccrs-8.2", "ccrs", "8.2",
        "Before the board materially reduces required coverage, reasonable efforts to notify the members of the "
        "reduction and why at least 30 days before it takes effect.", MORE, "insurance-change",
        (_before(Anchor.EVENT, 30),),
        lead="Ahead of the change, where 5810 notices it after."),
    NoticeProvision(
        "ccrs-10.5c", "ccrs", "10.5(b), 10.5(c), 10.7",
        "Sanctions only after a hearing under former Civil Code 1363; after emergency corrective action, the hearing "
        "follows it.", RENUMBERED, "discipline-hearing",
        lead="Former 1363's hearing is now 5855; whether emergency corrective action is discipline is for counsel."),
    NoticeProvision(
        "ccrs-10.10", "ccrs", "10.10",
        "A hearing notice states the date, time, and place, the alleged violation, the provision violated, and the "
        "sanction contemplated, in writing, by any method reasonably calculated to give actual notice, first-class if "
        "by mail.", MORE, "discipline-hearing", methods=(Method.WRITTEN, Method.FIRST_CLASS_MAIL),
        content=("the provision allegedly violated", "the sanction or action the board contemplates"),
        lead="Its content adds to 5855(b). Its method is wider than 5855(a) (personal delivery or the member's 4040 "
             "method): use the statute's."),
    NoticeProvision(
        "ccrs-12.6", "ccrs", "12.4(c), 12.6, 12.7(c)",
        "A mortgagee who asks gets written notice of meetings, 60-day delinquencies, uncured defaults, insurance lapses, "
        "and proposed actions needing its consent; an eligible mortgagee is deemed to approve an amendment it does not "
        "answer within 30 or 60 days of a proposal sent by certified or registered mail, return receipt requested.",
        OWN, "", methods=(Method.REGISTERED_OR_CERTIFIED,), title="Notices to mortgagees",
        recipients=Recipients.MORTGAGEES),
    NoticeProvision(
        "ccrs-15.5", "ccrs", "15.2 (outline 15.1(a)), 15.5",
        "An amendment is approved by the members' vote or written ballot (the board alone to conform to a change in "
        "law) and takes effect on recording a certificate of amendment signed by the president and secretary.", SAME,
        "",
        title="Amendment of the declaration", recipients=Recipients.ALL_MEMBERS,
        lead="4270(a) also requires recording. Of the sections on disk, only a court-ordered amendment (4275(g)) and "
             "a reinstated declaration (4276(e)) require sending the recorded instrument to the members; sending every "
             "recorded amendment is a practice for the board to adopt."),
)
