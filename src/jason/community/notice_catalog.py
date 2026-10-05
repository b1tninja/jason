"""The catalog of notices the law requires of a California common interest development, as ``NoticeRequirement`` rows.

Each row is read from the section's text on disk (``data/authorities``; ``jason export-authorities``): its recipients,
whether it goes by individual delivery (4040) or general delivery (4045) or a method of its own (certified mail,
personal service), its clock (``Timing``), its content, and the evidence that proves it was given. ``words`` is a
phrase the section carries; ``tests/test_notice_catalog.py`` checks it against the exported text, and a row whose
section is not on disk says ``verified=False`` rather than guessing. The periods that ``statutory_terms`` already pins
name their term, and the test checks the two agree.

The keys are stable: the association's ``NoticeRule`` (who receives it, by which tags), a notice's ledger key (its
batches' prefix: "board-meeting-2026-10-20"), the governing documents' ``NoticeProvision`` rows, and the duties read
from the documents all link here by key. A profile adds the notices only its documents require through
``Community.notice_provisions()``; it does not restate these.

A row that is required only for some events carries ``applies`` (``jason.community.notice_conditions``), written from
the section's words. ``applicable(facts)`` sorts the rows by it into three groups: applies (the notice is required, on
its clock), does not apply (with the fact that decided it), and undetermined (with the missing fact; never read as
"not required"). A row with no condition applies whenever its event happens. Where the section's words leave the
condition open, the row keeps its prose ``note`` and no condition.

This is an index of what the statutes say, for drafting and for proving delivery. It is not legal advice; where a row
has a ``caveat``, counsel reads it first.
"""

from __future__ import annotations

from typing import Iterable

from jason.community.applicability import ALWAYS, Fact, Facts, Partition, facts_tested, partition
from jason.community.notice_conditions import (ACCLAMATION_KEPT_AVAILABLE, DIRECTOR_ELECTION,
                                               DIRECTOR_OR_RECALL_ELECTION, ELECTRONIC_SECRET_BALLOT,
                                               ELECTRONIC_VOTING_OPT_OUT, EMERGENCY_BOARD_MEETING,
                                               ENTIRELY_BY_TELECONFERENCE, EXECUTIVE_SESSION_ONLY_MEETING,
                                               LISTED_RULE_CHANGE, LISTED_RULE_CHANGE_NOT_EMERGENCY,
                                               ORDINARY_BOARD_MEETING, same_event)
from jason.community.notices import (Anchor, Comparison, Evidence, Method, NoticeKind, NoticeProvision,
                                     NoticeRequirement, Recipients, Timing, Unit, combined)

I, G = NoticeKind.INDIVIDUAL, NoticeKind.GENERAL
B = Unit.BUSINESS_DAYS


def _before(anchor: Anchor, least: int | None = None, most: int | None = None, *, unit: Unit = Unit.CALENDAR_DAYS,
            words: str = "", delivery: bool = True) -> Timing:
    return Timing(anchor, False, least, most, unit, words, delivery)


def _after(anchor: Anchor, most: int | None = None, least: int | None = None, *, unit: Unit = Unit.CALENDAR_DAYS,
           words: str = "", delivery: bool = True) -> Timing:
    return Timing(anchor, True, least, most, unit, words, delivery)


REQUIREMENTS: tuple[NoticeRequirement, ...] = (
    # Board meetings (Article 2 of Chapter 6, the Open Meeting Act).
    NoticeRequirement(
        "board-meeting", "Board meeting: notice and agenda", "CIV 4920", Recipients.ALL_MEMBERS, G, (Method.GENERAL,),
        (_before(Anchor.MEETING, 4),),
        ("the time and place of the meeting", "the agenda (4920(d)); the board may act only on items on it (4930)",
         "for a teleconference meeting: technical instructions, a contact for help, and a reminder that a member may "
         "ask for individual delivery (4926(a)(1))"),
        words=r"at least four days before the meeting", individual_on_request=True, term="board meeting notice",
        also=("CIV 4045", "CIV 4926", "CIV 4930"), evidence=(Evidence.AGENDA,),
        note="A governing document that requires a longer period controls (4920(b)(3)); for an emergency meeting or "
             "one held only in executive session only if it says it applies to those.",
        applies=ORDINARY_BOARD_MEETING),
    NoticeRequirement(
        "board-meeting-executive", "Board meeting held only in executive session", "CIV 4920",
        Recipients.ALL_MEMBERS, G, (Method.GENERAL,), (_before(Anchor.MEETING, 2),),
        ("the time and place of the meeting", "the agenda"),
        words=r"at least two days prior to the meeting", individual_on_request=True, term="executive session notice",
        also=("CIV 4935",), evidence=(Evidence.AGENDA,),
        note="Matters discussed in executive session are generally noted in the minutes of the next open meeting "
             "(4935(e)).",
        applies=EXECUTIVE_SESSION_ONLY_MEETING),
    NoticeRequirement(
        "board-meeting-emergency", "Emergency board meeting", "CIV 4920", Recipients.ALL_MEMBERS, None, (),
        words=r"not required to give notice of the time and place", delivers=False, also=("CIV 4923", "CIV 4910"),
        evidence=(Evidence.MINUTES,),
        note="No notice is required. Called by the president or any two other directors for circumstances that could "
             "not reasonably have been foreseen (4923); a meeting by email needs every director's written consent, "
             "filed with the minutes (4910(b)(2)). The minutes are the evidence of the emergency.",
        applies=EMERGENCY_BOARD_MEETING),
    NoticeRequirement(
        "board-meeting-directors", "Special board meeting: notice to the directors", "CORP 7211", Recipients.BOARD,
        None, (Method.FIRST_CLASS_MAIL, Method.PERSONAL_DELIVERY, Method.ELECTRONIC), (_before(Anchor.MEETING, 4),),
        ("the time and place of the meeting (the purpose need not be stated)",),
        words=r"four days. notice by first-class mail or 48 hours. notice delivered personally",
        also=("CIV 4920",),
        note="Four days by first-class mail, or 48 hours delivered personally, by telephone, or by electronic "
             "transmission; the clock here is the four days, which serves every method. A regular meeting whose time "
             "and place the bylaws or the board fix needs no notice to the directors, and the articles or bylaws may "
             "not dispense with notice of a special meeting (7211(a)(2)). A director's written waiver, consent, or "
             "approval of the minutes, or attendance without protest, excuses it, and the waivers are filed with the "
             "minutes (7211(a)(3)). The directors' notice; the members' is 4920. 'Unless otherwise provided in the "
             "articles or in the bylaws' (7211(a)): a document's own rule is its NoticeProvision."),
    NoticeRequirement(
        "teleconference-meeting", "A board or member meeting held entirely by teleconference", "CIV 4926",
        Recipients.ALL_MEMBERS, None, (Method.GENERAL,), (),
        ("clear technical instructions on how to participate", "the telephone number and email of a person who can "
         "help, before and during the meeting", "a reminder that a member may request individual delivery of meeting "
         "notices, with instructions"),
        words=r"Clear technical instructions on how\s+to participate by teleconference", carried_by="board-meeting",
        note="Not for a meeting at which ballots are counted (4926(b)); directors vote by roll call; everyone may "
             "join by telephone.",
        applies=ENTIRELY_BY_TELECONFERENCE),
    NoticeRequirement(
        "disaster-meeting-first", "First teleconference meeting during a declared emergency", "CIV 5450",
        Recipients.ALL_MEMBERS, I, (Method.INDIVIDUAL,), (),
        ("the meeting notice's usual content", "technical instructions, a contact for help, and the reminder about "
         "individual delivery (5450(b)(2))"),
        words=r"Notice of the first meeting that is conducted under this section", also=("CIV 4926",),
        note="Where mail cannot be delivered or retrieved at an onsite address that is the member's address on file, "
             "the notice goes to any email the member gave in writing (5450(c))."),
    NoticeRequirement(
        "reserve-transfer-consideration", "Notice that the board will consider a temporary transfer from reserves",
        "CIV 5515", Recipients.ALL_MEMBERS, G, (Method.GENERAL,), (_before(Anchor.MEETING, 4),),
        ("the reasons the transfer is needed", "some of the options for repayment",
         "whether a special assessment may be considered"),
        words=r"notice of the intent to consider the transfer in a board meeting notice", carried_by="board-meeting",
        evidence=(Evidence.MINUTES,),
        note="The board's written finding goes in the minutes (5515(c)); the funds come back within one year, or the "
             "board gives the same notice again before delaying (5515(d))."),
    NoticeRequirement(
        "litigation-reserve-use", "Decision to use reserve funds for litigation", "CIV 5520", Recipients.ALL_MEMBERS,
        G, (Method.GENERAL,), (_after(Anchor.ACTION, words="when the decision is made"),),
        ("the decision", "that an accounting of the litigation expenses is available"),
        words=r"shall provide general notice pursuant to Section 4045 of that decision",
        note="The accounting is made at least quarterly and available at the association's office (5520(b))."),
    NoticeRequirement(
        "minutes-available", "Board minutes (or a draft or summary) available to members", "CIV 4950",
        Recipients.ALL_MEMBERS, None, (Method.MADE_AVAILABLE,), (_after(Anchor.MEETING, 30),),
        words=r"shall be available to members within 30 days of the meeting", delivers=False, term="minutes available",
        note="Not executive-session minutes. Distributed to a member on request at the association's cost of "
             "distribution. The annual policy statement says how to get them (4950(b))."),
    # Member meetings and elections (Article 4 of Chapter 6).
    NoticeRequirement(
        "member-meeting", "Meeting of the members", "CORP 7511", Recipients.ALL_MEMBERS, None, (), (),
        ("the date, time, and place", "the general nature of the business"),
        verified=False,
        caveat="Corporations Code 7511 (notice of members' meetings) is not exported here; the bylaws' own notice "
               "period governs meanwhile (a NoticeProvision), and the Act's election notices below apply to an "
               "election."),
    NoticeRequirement(
        "nomination-procedure", "Call for candidates: the nomination procedure and deadline", "CIV 5115",
        Recipients.ALL_MEMBERS, G, (Method.GENERAL,), (_before(Anchor.NOMINATION_DEADLINE, 30),),
        ("the procedure for submitting a nomination", "the deadline"),
        words=r"at least 30 days before any deadline for submitting a nomination", individual_on_request=True,
        term="notice of nominations", note="Elections of directors and recall elections only (5115(a)).",
        applies=DIRECTOR_OR_RECALL_ELECTION),
    NoticeRequirement(
        "acclamation-initial", "Initial notice of an election that may end in acclamation", "CIV 5103",
        Recipients.ALL_MEMBERS, I, (Method.INDIVIDUAL,), (_before(Anchor.NOMINATION_DEADLINE, 90),),
        ("the number of board positions to be filled", "the deadline for submitting nominations",
         "the manner in which nominations can be submitted",
         "the statement that the board may seat the qualified candidates by acclamation if there are no more "
         "candidates than positions"),
        words=r"at least 90 days before the deadline for submitting nominations", term="acclamation notice",
        note="Required only if the association may seat candidates by acclamation; also a regular election within the "
             "last three years (5103(a)).",
        applies=ACCLAMATION_KEPT_AVAILABLE),
    NoticeRequirement(
        "acclamation-reminder", "Reminder notice before the nomination deadline", "CIV 5103", Recipients.ALL_MEMBERS,
        I, (Method.INDIVIDUAL,), (_before(Anchor.NOMINATION_DEADLINE, 7, 30),),
        ("the number of positions", "the deadline", "the manner of nominating",
         "the names of the qualified candidates as of the reminder",
         "the acclamation statement, unless the candidates already outnumber the positions"),
        words=r"between 7 and 30 days before the deadline for submitting nominations",
        applies=ACCLAMATION_KEPT_AVAILABLE),
    NoticeRequirement(
        "nomination-acknowledgment", "Acknowledgment of a nomination, and the nominee's qualification", "CIV 5103",
        Recipients.NOMINATOR_AND_NOMINEE, None, (Method.WRITTEN, Method.ELECTRONIC),
        (_after(Anchor.NOMINATION_RECEIVED, 7, unit=B),),
        ("to the nominator: the nomination was received", "to the nominee: qualified, or not qualified with the basis "
         "and the procedure to appeal under 5900 and following"),
        words=r"within seven business days of receiving a nomination",
        note="A condition of seating by acclamation; one communication when nominator and nominee are the same.",
        applies=ACCLAMATION_KEPT_AVAILABLE),
    NoticeRequirement(
        "pre-ballot-notice", "Election notice before ballots go out", "CIV 5115", Recipients.ALL_MEMBERS, G,
        (Method.GENERAL,), (_before(Anchor.BALLOTS_DISTRIBUTED, 30),),
        ("when and where ballots are returned by mail or by hand to the inspector",
         "for electronic voting: when electronic ballots are due and preliminary instructions",
         "the date, time, and location of the meeting at which a quorum is determined and ballots are counted",
         "the list of all candidates' names that will appear on the ballot",
         "if the documents require a quorum: the statement about a reconvened meeting at a 20 percent quorum"),
        words=r"at least 30 days before the ballots are distributed", individual_on_request=True,
        also=("CIV 5105",),
        note="Members may verify their own entries on the voter and candidate lists at least 30 days before ballots "
             "are distributed; the inspector corrects an error within two business days (5105(a)(7)).",
        applies=DIRECTOR_OR_RECALL_ELECTION),
    NoticeRequirement(
        "ballots", "Ballots, return envelopes, and the election rules", "CIV 5115", Recipients.ALL_MEMBERS, None,
        (Method.FIRST_CLASS_MAIL, Method.PERSONAL_DELIVERY), (_before(Anchor.VOTING_DEADLINE, 30),),
        ("the ballot, which does not identify the voter", "two preaddressed envelopes and return instructions",
         "the election operating rules, or their website address with the phrase 5105(h)(4)(B)(i) prescribes",
         "for an amendment: the text of the proposed amendment (5115(g))"),
        words=r"not less than 30 days prior to the deadline for voting", term="ballots delivered ahead of the deadline",
        also=("CIV 5105",), evidence=(Evidence.RECIPIENTS,),
        note="Mailed by first-class mail or delivered by the association; with electronic voting, only to the members "
             "voting on paper. The inspector delivers the ballots and rules at least 30 days before the election "
             "(5105(h)(4))."),
    NoticeRequirement(
        "electronic-ballot-notice", "Notice of an electronic secret ballot", "CIV 5105", Recipients.ALL_MEMBERS, I,
        (Method.INDIVIDUAL, Method.ELECTRONIC), (_before(Anchor.ELECTION, 30),),
        ("how to get access to the internet-based voting system", "how to vote by electronic secret ballot"),
        words=r"individual notice of the electronic secret ballot to each member 30 days before the election",
        applies=ELECTRONIC_SECRET_BALLOT),
    NoticeRequirement(
        "electronic-opt-out-notice", "Notice of the deadline to opt out of electronic voting", "CIV 5105",
        Recipients.ALL_MEMBERS, I, (Method.INDIVIDUAL,), (_before(Anchor.OPT_OUT_DEADLINE, 30),),
        ("the member's current voting method", "the email that will be used, for an electronic voter",
         "that a member who wants a paper ballot must opt out", "how to opt out", "the deadline to opt out"),
        words=r"at least 30 days before the deadline to opt out of voting by electronic secret ballot",
        note="A member may change voting method no later than 90 days before an election (5105(i)(1)(A)).",
        applies=ELECTRONIC_VOTING_OPT_OUT),
    NoticeRequirement(
        "reconvened-election-meeting", "Reconvened meeting after an election without a quorum", "CIV 5115",
        Recipients.ALL_MEMBERS, G, (Method.GENERAL,), (_before(Anchor.RECONVENED_MEETING, 15),),
        ("the date, time, and location", "the list of all candidates",
         "that 20 percent of the members will satisfy the quorum, unless the documents set a lower one"),
        words=r"No less than 15 days prior to the date of the reconvened meeting",
        note="The reconvened meeting is at least 20 days after the adjourned one (5115(d)(2)).",
        applies=DIRECTOR_ELECTION),
    NoticeRequirement(
        "election-results", "Tabulated results of an election", "CIV 5120", Recipients.ALL_MEMBERS, G,
        (Method.GENERAL,), (_after(Anchor.ELECTION, 15),), ("the tabulated results",),
        words=r"Within 15 days of the election, the board shall give general notice", term="election results notice",
        evidence=(Evidence.MINUTES,),
        note="Also recorded in the minutes of the next board meeting (5120(b)); the one-year period to challenge the "
             "election runs from the inspector's notice of the results (5145(a))."),
    NoticeRequirement(
        "member-vote-result-request", "Result of a member vote, on request", "CORP 8325", Recipients.REQUESTER, None,
        (Method.WRITTEN,), (),
        ("the number of memberships voting for, against, and abstaining",),
        words=r"For a period of 60 days following the conclusion of an annual, regular, or special meeting",
        note="For 60 days after a members' meeting, on a member's written request, forthwith."),
    # Operating rules and the governing documents (Chapter 3).
    NoticeRequirement(
        "rule-change-proposed", "Proposed rule change", "CIV 4360", Recipients.ALL_MEMBERS, G, (Method.GENERAL,),
        (_before(Anchor.RULE_CHANGE, 28),),
        ("the text of the proposed rule change", "a description of its purpose and effect"),
        words=r"at least 28 days before making the rule change", individual_on_request=True,
        term="notice of a rule change", also=("CIV 4355", "CIV 4365"),
        note="Only for rules on the subjects in 4355(a). The decision is made at a board meeting after considering "
             "members' comments (4360(b)). No notice for an emergency rule change (4360(d)).",
        applies=LISTED_RULE_CHANGE_NOT_EMERGENCY),
    NoticeRequirement(
        "rule-change-adopted", "Adopted rule change", "CIV 4360", Recipients.ALL_MEMBERS, G, (Method.GENERAL,),
        (_after(Anchor.RULE_CHANGE, 15),),
        ("the rule change", "for an emergency rule change: its text, purpose and effect, and the date it expires "
         "(it lasts at most 120 days)"),
        words=r"not more than 15 days after making the rule change", individual_on_request=True,
        note="Members owning 5 percent of the separate interests may call a vote to reverse it, by a written request "
             "delivered within 30 days after this notice (4365(b)).",
        applies=LISTED_RULE_CHANGE),
    NoticeRequirement(
        "rule-change-reversal-results", "Results of a member vote to reverse a rule change", "CIV 4365",
        Recipients.ALL_MEMBERS, G, (Method.GENERAL,), (_after(Anchor.CLOSE_OF_VOTING, 15),),
        ("the results of the vote",), words=r"not more than 15 days after the close of voting",
        note="The vote is held 35 to 90 days after the association receives a proper request (4365(b)).",
        applies=LISTED_RULE_CHANGE_NOT_EMERGENCY),
    NoticeRequirement(
        "rental-amendment-4741", "Board amendment deleting or restating an unlawful rental restriction", "CIV 4741",
        Recipients.ALL_MEMBERS, G, (Method.GENERAL,), (_before(Anchor.ACTION, 28),),
        ("the text of the amendment", "a description of its purpose and effect"),
        words=r"at least 28 days before approving the amendment",
        note="The board, without member approval, restates the document with no other change; the decision at a "
             "board meeting after considering comments (4741(f))."),
    NoticeRequirement(
        "developer-amendment-4230", "Amendment deleting the developer's construction and marketing provisions",
        "CIV 4230", Recipients.ALL_MEMBERS, I, (Method.INDIVIDUAL,), (_before(Anchor.MEETING, 30),),
        ("a copy of every amendment proposed", "the time, date, and place the board will consider adopting them"),
        words=r"At least 30 days prior to taking action pursuant to subdivision \(a\)",
        note="Considered only at an open meeting; the board cannot adopt it without a majority of a quorum of the "
             "members (4230(d))."),
    NoticeRequirement(
        "amendment-petition-hearing", "Court hearing on a petition to reduce the vote needed for an amendment",
        "CIV 4275", Recipients.ALL_MEMBERS, None, (Method.WRITTEN,), (_before(Anchor.HEARING, 15),),
        words=r"not less than 15 days written notice of the court hearing",
        note="Also to the mortgagees and the city or county the declaration entitles to notice; the court's ex parte "
             "order sets the manner (4275(b))."),
    NoticeRequirement(
        "amendment-recorded-4275", "Amendment recorded under a court order", "CIV 4275", Recipients.ALL_MEMBERS, I,
        (Method.INDIVIDUAL,), (_after(Anchor.RECORDING, words="within a reasonable time"),),
        ("a copy of the amendment", "a statement that it has been recorded"),
        words=r"Within a reasonable time after the amendment is recorded"),
    # Annual disclosures (Article 7 of Chapter 6) and the annual solicitation (4041).
    NoticeRequirement(
        "owner-info-solicitation", "Annual request for each owner's delivery preferences and occupancy", "CIV 4041",
        Recipients.ALL_MEMBERS, None, (Method.WRITTEN,),
        (_before(Anchor.ANNUAL_REPORTS, 30, words="the answers entered in the books at least 30 days before the "
                                                     "5300 and 5310 disclosures", delivery=False),),
        ("the preferred delivery method (mail, email, or both)", "an alternate or secondary delivery method",
         "the legal representative, if any", "whether the unit is owner-occupied, rented, or vacant",
         "that the member does not have to provide an email address",
         "a simple way to change the preferred delivery method in writing"),
        words=r"at least 30 days before making its own required disclosure", annual=True,
        note="The clock is for entering the answers, not for sending the request. Without an answer, the last mailing "
             "address the member gave in writing, else the unit's address, is the address (4041(c))."),
    NoticeRequirement(
        "annual-budget-report", "Annual budget report", "CIV 5300", Recipients.ALL_MEMBERS, I, (Method.INDIVIDUAL,),
        (_before(Anchor.FISCAL_YEAR_END, 30, 90),),
        ("the pro forma operating budget", "the reserve summary (5565) and the reserve funding plan summary",
         "deferred repairs, anticipated special assessments, and how reserves are funded", "outstanding loans",
         "the insurance summary with the 10-point bold statement (5300(b)(9))",
         "the FHA and VA status statements, each on a separate page",
         "the completed Charges For Documents Provided form (4528)",
         "the Assessment and Reserve Funding Disclosure Summary (5570)"),
        words=r"30 to 90 days before the end of its fiscal year", annual=True, secondary_copies=True,
        also=("CIV 5320", "CIV 5570"),
        note="The full report, or a summary whose first page describes it and says in 10-point bold how to get the "
             "full report free; a member who asked for full reports gets them (5320). The window applies "
             "notwithstanding a contrary provision in the documents."),
    NoticeRequirement(
        "annual-policy-statement", "Annual policy statement", "CIV 5310", Recipients.ALL_MEMBERS, I,
        (Method.INDIVIDUAL,), (_before(Anchor.FISCAL_YEAR_END, 30, 90),),
        ("who receives official communications for the association (4035)",
         "that a member may have notices sent to up to two addresses (4040)",
         "the designated posting location for general notices, if any (4045(a))",
         "the option to receive general notices by individual delivery (4045(b))",
         "the right to copies of minutes and how (4950(b))", "the assessment and foreclosure notice (5730)",
         "lien enforcement policies and practices", "the discipline policy and penalty schedule (5850)",
         "the dispute resolution summaries (5920, 5965)", "the architectural approval requirements (4765)",
         "the mailing address for overnight payments (5655)", "electronic voting opt-in or opt-out procedures "
         "(5105(i)(1)(D)), if used", "anything else the law or the documents require"),
        words=r"Within 30 to 90 days before the end of its fiscal year, the board shall distribute an annual policy "
              r"statement", annual=True, secondary_copies=True, also=("CIV 5320",),
        note="The website or posting location named here is what makes posting a valid general notice "
             "(4045(a)(3), (5))."),
    NoticeRequirement(
        "collection-policy-notice", "Notice of assessments and foreclosure", "CIV 5730", Recipients.ALL_MEMBERS, I,
        (Method.INDIVIDUAL,), (), ("the statutory notice, verbatim, in at least 12-point type",),
        words=r"shall include the following notice, in at least 12-point type", annual=True, secondary_copies=True,
        carried_by="annual-policy-statement"),
    NoticeRequirement(
        "penalty-schedule", "Schedule of monetary penalties", "CIV 5850", Recipients.ALL_MEMBERS, I,
        (Method.INDIVIDUAL,), (), ("the penalties that may be assessed for each violation",),
        words=r"a schedule of the monetary penalties that may be assessed", annual=True,
        carried_by="annual-policy-statement",
        note="A new or revised penalty may go out as a supplement by individual delivery (5850(b)); a member may ask "
             "for the latest schedule (5850(f)). A penalty above $100 needs the 5850(d) written finding first."),
    NoticeRequirement(
        "penalty-schedule-supplement", "Supplement to the penalty schedule", "CIV 5850", Recipients.ALL_MEMBERS, I,
        (Method.INDIVIDUAL,), (), ("the new or revised penalty",),
        words=r"may be included in a supplement that is delivered to the members\s+individually",
        also=("CIV 4360",),
        note="A schedule of penalties is an operating rule on member discipline (4355(a)(3)): propose it with 28 "
             "days' general notice first."),
    NoticeRequirement(
        "dispute-resolution-summary", "Summary of alternative dispute resolution (and the internal process)",
        "CIV 5965", Recipients.ALL_MEMBERS, I, (Method.INDIVIDUAL,), (),
        ("a summary that cites the article", "the statutory warning about losing the right to sue",
         "the internal dispute resolution process (5920)"),
        words=r"shall annually provide its members a summary of the provisions of this article", annual=True,
        carried_by="annual-policy-statement", also=("CIV 5920",)),
    NoticeRequirement(
        "architectural-requirements", "Annual notice of the requirements for architectural approval", "CIV 4765",
        Recipients.ALL_MEMBERS, I, (Method.INDIVIDUAL,), (),
        ("the types of changes that need approval", "a copy of the review procedure"),
        words=r"shall annually provide its members with notice of any requirements for association approval",
        annual=True, carried_by="annual-policy-statement"),
    NoticeRequirement(
        "financial-review", "Reviewed financial statement", "CIV 5305", Recipients.ALL_MEMBERS, I,
        (Method.INDIVIDUAL,), (_after(Anchor.FISCAL_YEAR_END, 120),), ("the CPA's review of the financial statement",),
        words=r"within 120 days after the close of each\s+fiscal year, by individual delivery", annual=True,
        secondary_copies=True, term="financial review",
        note="When gross income for the year exceeds $75,000, unless the documents set a stricter standard."),
    NoticeRequirement(
        "annual-report-8321", "Notice of the right to the corporation's annual report", "CORP 8321",
        Recipients.ALL_MEMBERS, None, (Method.WRITTEN,), (), ("the member's right to receive a financial report",),
        words=r"shall notify each member yearly of the member.s right to receive a financial report", annual=True,
        note="The annual report is prepared within 120 days after the fiscal year closes and sent promptly on a "
             "member's written request."),
    # Assessments (Chapter 8).
    NoticeRequirement(
        "assessment-increase", "Increase in regular or special assessments", "CIV 5615", Recipients.ALL_MEMBERS, I,
        (Method.INDIVIDUAL,), (_before(Anchor.DUE_DATE, 30, 60),), ("the increase", "when it becomes due"),
        words=r"not less than 30 nor more than 60 days prior to the increased assessment becoming due",
        also=("CIV 5605", "CIV 5610"),
        note="A regular increase over 20 percent, or special assessments over 5 percent of budgeted gross expenses, "
             "needs a member vote unless it is an emergency under 5610 (5605(b))."),
    NoticeRequirement(
        "emergency-assessment-resolution", "Resolution with findings for an emergency assessment", "CIV 5610",
        Recipients.ALL_MEMBERS, I, (Method.INDIVIDUAL,), (),
        ("the written findings on the necessity of the expense and why it could not have been foreseen",),
        words=r"the resolution shall be distributed to the members with the notice of assessment",
        carried_by="assessment-increase", evidence=(Evidence.MINUTES,),
        note="For an expense under 5610(c); the resolution is passed before the assessment is imposed or collected."),
    NoticeRequirement(
        "pre-lien-notice", "Notice before recording an assessment lien", "CIV 5660", Recipients.OWNER_OF_RECORD, None,
        (Method.CERTIFIED_MAIL,), (_before(Anchor.LIEN_RECORDING, 30),),
        ("the collection and lien enforcement procedures and how the amount is calculated",
         "the right to inspect the records (5205)", "the foreclosure warning in 14-point bold or capitals",
         "an itemized statement of the charges", "that no charges are owed if the assessment was paid on time",
         "the right to request a meeting with the board (5665)",
         "the right to dispute the debt through meet and confer (5900)",
         "the right to request ADR before foreclosure (5925)"),
        words=r"At least 30 days prior to recording a lien upon the separate interest", secondary_copies=True,
        term="pre-lien notice ahead of the lien", also=("CIV 5670", "CIV 5673", "CIV 5690"),
        note="Before recording, offer meet and confer (5670), and the board decides to record by majority vote in an "
             "open meeting, recorded in the minutes (5673). A step done wrong is started over at the association's "
             "cost (5690)."),
    NoticeRequirement(
        "payment-plan-meeting", "Board meeting on a payment plan request", "CIV 5665", Recipients.MEMBER, None, (),
        (_after(Anchor.REQUEST_MAILED, 45, words="within 45 days of the postmark of the request", delivery=False),),
        words=r"within 45 days of the postmark of the request", delivers=False, term="payment plan meeting",
        note="If the owner's request is mailed within 15 days of the postmark of the pre-lien notice; in executive "
             "session (4935(c)); a committee of directors when no regular meeting falls in the period."),
    NoticeRequirement(
        "lien-copy", "Copy of the recorded notice of delinquent assessment", "CIV 5675", Recipients.RECORD_OWNERS,
        None, (Method.CERTIFIED_MAIL,), (_after(Anchor.LIEN_RECORDING, 10),),
        ("the recorded notice of delinquent assessment",),
        words=r"no later than 10 calendar days after recordation", secondary_copies=True,
        term="lien mailed after recording", evidence=(Evidence.RECORDING,)),
    NoticeRequirement(
        "lien-release", "Lien release after payment, or after a lien recorded in error", "CIV 5685",
        Recipients.OWNER_OF_RECORD, None, (Method.RECORDED, Method.WRITTEN), (_after(Anchor.PAYMENT, 21),),
        ("a copy of the lien release or notice that the delinquent assessment is satisfied",
         "for a lien recorded in error: a declaration that it was in error"),
        words=r"Within 21 days of the payment of the sums specified in the notice of delinquent assessment",
        secondary_copies=True, term="lien release after payment",
        note="A lien recorded in error is released within 21 calendar days of that determination (5685(b))."),
    NoticeRequirement(
        "foreclosure-decision", "Notice of the board's decision to foreclose", "CIV 5705", Recipients.OWNER_OR_REPRESENTATIVE,
        None, (Method.PERSONAL_SERVICE, Method.FIRST_CLASS_MAIL), (_after(Anchor.VOTE_TO_FORECLOSE),),
        ("the board's decision to foreclose",),
        words=r"provide notice by personal service in accordance with the manner of service of summons",
        also=("CIV 5720",), evidence=(Evidence.MINUTES,),
        note="Personal service on an owner who occupies the unit or the owner's legal representative; first-class "
             "mail to an owner who does not, at the most current address on the books. The vote is in executive "
             "session at least 30 days before any public sale, recorded by parcel number in the next open minutes "
             "(5705(c)); ADR offered first (5705(b)); no foreclosure under $1,800 unless more than 12 months "
             "delinquent (5720)."),
    NoticeRequirement(
        "notice-of-default", "Service of the notice of default", "CIV 5710", Recipients.OWNER_OR_REPRESENTATIVE,
        None, (Method.PERSONAL_SERVICE,), (), ("the notice of default",),
        words=r"shall serve a notice of default on the person named as the owner", secondary_copies=True,
        also=("CIV 2924b",),
        note="Besides the trustee's mailing by registered or certified mail within 10 business days after the notice "
             "of default is recorded (2924b(b)(1))."),
    NoticeRequirement(
        "notice-of-sale", "Notice of the trustee's sale", "CIV 5715", Recipients.OWNER_OF_RECORD, None,
        (Method.REGISTERED_OR_CERTIFIED,), (_before(Anchor.PUBLIC_SALE, 20),),
        ("the time and place of sale", "that the property is sold subject to the 90-day right of redemption"),
        words=r"subject to the right of redemption created in this section", also=("CIV 2924b", "CIV 2924f"),
        note="The trustee's notice, mailed by registered or certified mail at least 20 days before the sale "
             "(2924b(b)(2)), and also published, posted on the property, and recorded at least 20 days before it "
             "(2924f(b)). The 20 days are read from 2924b on disk; the test checks 5715's words."),
    NoticeRequirement(
        "mechanics-lien-claim", "Claim of lien served for work on the common area", "CIV 4620",
        Recipients.ALL_MEMBERS, I, (Method.INDIVIDUAL,), (_after(Anchor.SERVICE, 60),), ("the claim of lien",),
        words=r"within 60 days of service, give individual notice to the members"),
    # Insurance (Chapter 9).
    NoticeRequirement(
        "insurance-change", "Insurance lapse, cancellation, or significant change", "CIV 5810", Recipients.ALL_MEMBERS,
        I, (Method.INDIVIDUAL,), (_after(Anchor.EVENT, words="as soon as reasonably practicable"),),
        ("which policy", "what happened: lapsed, canceled, not renewed, reduced coverage or limits, or a higher "
         "deductible"),
        words=r"as soon as reasonably practicable, provide individual notice",
        note="A notice of nonrenewal with no replacement in effect by the lapse date: notify the members immediately."),
    # Discipline (Article 1 of Chapter 10).
    NoticeRequirement(
        "discipline-hearing", "Notice of a hearing on discipline or a damage charge", "CIV 5855", Recipients.MEMBER,
        None, (Method.PERSONAL_DELIVERY, Method.INDIVIDUAL), (_before(Anchor.HEARING, 10),),
        ("the date, time, and place of the meeting",
         "the nature of the alleged violation, or of the common-area damage",
         "that the member may attend and address the board", "that the member may ask for executive session",
         "that a cure before the meeting (or a financial commitment to cure) ends it (5855(c))"),
        words=r"at least 10 days prior to the meeting", term="hearing notice", also=("CIV 4935",),
        evidence=(Evidence.MINUTES,),
        note="No discipline is effective without these steps (5855(g))."),
    NoticeRequirement(
        "discipline-decision", "Written decision after a hearing", "CIV 5855", Recipients.MEMBER, None,
        (Method.PERSONAL_DELIVERY, Method.INDIVIDUAL), (_after(Anchor.ACTION, 14),), ("the decision",),
        words=r"within 14 days following the action", term="written decision after a hearing",
        note="15 days before June 30, 2025 (AB 130); statutory_terms.in_force gives the period for a decision's date."),
    NoticeRequirement(
        "religious-item-removal", "Temporary removal of a religious item for door work", "CIV 4706",
        Recipients.MEMBER, I, (Method.INDIVIDUAL,), (), ("that the item must come down while the work is done",),
        words=r"shall provide individual notice to the member regarding the temporary removal"),
    # Dispute resolution (Articles 2 and 3 of Chapter 10).
    NoticeRequirement(
        "meet-and-confer", "Request for internal dispute resolution (meet and confer)", "CIV 5915",
        Recipients.PARTIES, None, (Method.WRITTEN,), (), ("the request to meet and confer",),
        words=r"request the other party to meet and confer in an effort to resolve the dispute",
        also=("CIV 5910",),
        note="The association cannot refuse a member's request; the board designates a director; no fee. The "
             "association's own procedure must state the maximum time to act on a request (5910(b))."),
    NoticeRequirement(
        "request-for-resolution", "Request for Resolution (ADR before an enforcement action)", "CIV 5935",
        Recipients.PARTIES, None,
        (Method.PERSONAL_DELIVERY, Method.FIRST_CLASS_MAIL, Method.WRITTEN),
        (_after(Anchor.SERVICE, 30, words="the other party accepts or rejects within 30 days"),),
        ("a brief description of the dispute", "a request for ADR",
         "that the recipient must respond within 30 days or the request is deemed rejected",
         "to a member: a copy of the article (5925 to 5965)"),
        words=r"required to respond within 30 days of receipt", term="ADR response", also=("CIV 5940", "CIV 5950"),
        note="Served by personal delivery, first-class mail, express mail, fax, or other means reasonably calculated "
             "to give actual notice. Once accepted, ADR is completed within 90 days (5940)."),
    # Records (Article 5 of Chapter 6).
    NoticeRequirement(
        "records-current-year", "Association records of the current fiscal year", "CIV 5210", Recipients.REQUESTER,
        None, (Method.MADE_AVAILABLE, Method.INDIVIDUAL), (_after(Anchor.REQUEST_RECEIVED, 10, unit=B),),
        words=r"within 10 business days following the association.s receipt of the request",
        term="records of the current year", also=("CIV 5205", "CIV 5215"),
        note="Copies of specifically identified records may go by individual delivery (5205(e)); tell the member the "
             "copying and mailing cost, and any redaction charge, before copying (5205(f), (g))."),
    NoticeRequirement(
        "records-prior-years", "Association records of the two prior fiscal years", "CIV 5210", Recipients.REQUESTER,
        None, (Method.MADE_AVAILABLE, Method.INDIVIDUAL), (_after(Anchor.REQUEST_RECEIVED, 30),),
        words=r"within 30 calendar days following the association.s receipt of the request",
        term="records of prior years"),
    NoticeRequirement(
        "records-committee-minutes", "Minutes of a committee with decisionmaking authority", "CIV 5210",
        Recipients.REQUESTER, None, (Method.MADE_AVAILABLE,), (_after(Anchor.ACTION, 15),),
        words=r"within 15 calendar days following approval", delivers=False,
        note="Counted from the minutes' approval."),
    NoticeRequirement(
        "records-withheld-explanation", "Written explanation of records withheld or redacted", "CIV 5215",
        Recipients.REQUESTER, None, (Method.WRITTEN,), (), ("the legal basis for withholding or redacting",),
        words=r"shall provide a written explanation specifying the legal basis",
        note="When the member asks for it."),
    NoticeRequirement(
        "membership-list-alternative", "Offer of an alternative to the membership list", "CORP 8330",
        Recipients.REQUESTER, None, (Method.WRITTEN,), (_after(Anchor.REQUEST_RECEIVED, 10, unit=B),),
        ("a written offer of another way to achieve the stated purpose",),
        words=r"within ten business days after receiving a demand", also=("CIV 5220", "CIV 5225"),
        note="Members who opted out (5220) are reached only this way; the request states a purpose reasonably related "
             "to membership (5225)."),
    # Transfers (Article 2 of Chapter 4).
    NoticeRequirement(
        "resale-documents", "Documents for a sale (4525), on the owner's request", "CIV 4530", Recipients.REQUESTER,
        None, (Method.WRITTEN, Method.ELECTRONIC), (_after(Anchor.REQUEST_MAILED, 10),),
        ("the requested 4525 documents", "the completed 4528 form"),
        words=r"within 10 days of the mailing or delivery of the request", term="resale documents",
        also=("CIV 4525", "CIV 4528"),
        note="The fee estimate on the 4528 form goes out before the request is processed (4530(b)(2)); delivery may "
             "not be withheld except for the fee."),
    # Use and maintenance (Chapter 5).
    NoticeRequirement(
        "architectural-decision", "Decision on a proposed physical change", "CIV 4765", Recipients.APPLICANT, None,
        (Method.WRITTEN,), (_after(Anchor.APPLICATION_RECEIVED, words="within the maximum time the procedure states"),),
        ("the decision", "if disapproved: why, and how to ask the board to reconsider"),
        words=r"A decision on a proposed change shall be in writing",
        note="The statute sets no period; the documents' procedure must (4765(a)(1)). A disapproval is reconsidered at "
             "an open board meeting on request."),
    NoticeRequirement(
        "ev-charger-decision", "Decision on an electric vehicle charging station", "CIV 4745", Recipients.APPLICANT,
        None, (Method.WRITTEN,), (_after(Anchor.APPLICATION_RECEIVED, 60),),
        ("approval or denial in writing",),
        words=r"not denied in writing within 60 days from the date of receipt of the application",
        note="Deemed approved if not denied in writing in time, unless a reasonable request for more information "
             "caused the delay."),
    NoticeRequirement(
        "ev-meter-decision", "Decision on an EV-dedicated time-of-use meter", "CIV 4745.1", Recipients.APPLICANT,
        None, (Method.WRITTEN,), (_after(Anchor.APPLICATION_RECEIVED, 60),), ("approval or denial in writing",),
        words=r"not denied in writing within 60 days from the date of receipt of the application"),
    NoticeRequirement(
        "solar-decision", "Decision on a solar energy system", "CIV 714", Recipients.APPLICANT, None,
        (Method.WRITTEN,), (_after(Anchor.APPLICATION_RECEIVED, 45),), ("approval or denial in writing",),
        words=r"not denied in writing within 45 days from the date of receipt of the application",
        also=("CIV 4746",),
        note="For a shared roof the applicant notifies each owner in the building (4746(a)(1)); see solar-building."),
    NoticeRequirement(
        "solar-building", "Applicant's notice to the building's owners of a roof solar application", "CIV 4746",
        Recipients.BUILDING_OWNERS, None, (Method.WRITTEN,), (), ("the application to install a solar energy system",),
        words=r"notify each owner of a unit in the building on which the installation will be located",
        note="The applicant's duty, which the association requires; the association keeps evidence it was given."),
    NoticeRequirement(
        "disaster-rebuild-completeness", "Whether an application to rebuild after a disaster is complete", "CIV 4766",
        Recipients.APPLICANT, None, (Method.WRITTEN,), (_after(Anchor.APPLICATION_RECEIVED, 30),),
        ("complete or incomplete", "if incomplete: the missing items and how to complete it"),
        words=r"no later than 30 calendar days after the body receives the application",
        note="Deemed complete if not decided in time; the review follows within 45 calendar days (4766(c)), and an "
             "appeal is decided within 60 calendar days (4766(e)(2))."),
    NoticeRequirement(
        "pesticide-unit", "Pesticide applied in a unit without a licensed operator", "CIV 4777",
        Recipients.OWNER_AND_TENANT, I, (Method.INDIVIDUAL,), (_before(Anchor.APPLICATION_OF_PESTICIDE, 48, unit=Unit.HOURS),),
        ("the pests", "the product's name and brand", "the statutory caution, verbatim",
         "the approximate date, time, and frequency", "that the schedule may change"),
        words=r"At least 48 hours prior to application of the pesticide to a separate interest",
        evidence=(Evidence.MINUTES,),
        note="Tenants by first-class mail, personal delivery to an adult, or email they gave (4777(b)(4)); a copy is "
             "attached to the next board minutes (4777(b)(6)). A licensed operator's notices are the operator's."),
    NoticeRequirement(
        "pesticide-common-area", "Pesticide applied in the common area without a licensed operator", "CIV 4777",
        Recipients.OWNER_AND_TENANT, None, (Method.POSTED_AT_SITE, Method.INDIVIDUAL),
        (_before(Anchor.APPLICATION_OF_PESTICIDE, 48, unit=Unit.HOURS),),
        ("the same statements as for a unit",),
        words=r"At least 48 hours prior to application of the pesticide to a common area",
        note="Posted where it is applied if practicable, else individual notice to the adjacent units; for an "
             "immediate threat, posted within one hour after."),
    NoticeRequirement(
        "termite-relocation", "Temporary relocation for wood-destroying pest treatment", "CIV 4785",
        Recipients.OCCUPANTS_AND_OWNER, None, (Method.PERSONAL_DELIVERY, Method.INDIVIDUAL),
        (_before(Anchor.RELOCATION, 15, 30),),
        ("the reason", "when treatment begins and is expected to end",
         "that the occupants arrange their own accommodations"),
        words=r"not less than 15 days nor more than 30 days prior to the date of the temporary relocation",
        note="Complete on personal delivery to the occupants, or individual delivery to the occupant at the unit, and "
             "in either case individual delivery to an owner who is not an occupant (4785(c))."),
    # Construction defects (Chapter 11).
    NoticeRequirement(
        "defect-action-meeting", "Meeting before suing the builder over defects", "CIV 6150",
        Recipients.ALL_MEMBERS, None, (Method.WRITTEN,), (_before(Anchor.FILING, 30),),
        ("that a meeting will discuss problems that may lead to a civil action, and its impacts",
         "the options, including civil actions", "the time and place of the meeting"),
        words=r"Not later than 30 days before filing of any civil action",
        note="If the statute of limitations would run first, within 30 days after filing (6150(b))."),
    NoticeRequirement(
        "defect-settlement", "Disclosure after a defect claim against the builder is resolved", "CIV 6100",
        Recipients.ALL_MEMBERS, None, (Method.WRITTEN,), (_after(Anchor.SETTLEMENT, words="as soon as reasonably practicable"),),
        ("the defects the association expects to be corrected", "a good-faith estimate of when",
         "the status of the other claims"),
        words=r"As soon as is reasonably practicable after the association and the builder have entered into a "
              r"settlement agreement"),
    NoticeRequirement(
        "defect-list-6000", "Preliminary list of defects", "CIV 6000", Recipients.ALL_MEMBERS, None, (), (),
        verified=False,
        caveat="Former Civil Code 6000 became inoperative July 1, 2024 and was repealed January 1, 2025 (jason "
               "law-history); 4525(a)(6) still lists a copy of an initial list provided under it among the resale "
               "documents."),
    # The manager.
    NoticeRequirement(
        "manager-disclosure", "Prospective managing agent's written statement to the board", "CIV 5375",
        Recipients.BOARD, None, (Method.WRITTEN,), (_before(Anchor.CONTRACT, most=90),),
        words=r"as soon as practicable, but in no event more than 90 days, before entering into a management agreement",
        note="To the board, not the members."),
)


def requirement(key: str) -> NoticeRequirement:
    """One general row by key; KeyError when there is none."""
    for row in REQUIREMENTS:
        if row.key == key:
            return row
    raise KeyError(key)


def conditional(rows: Iterable[NoticeRequirement] | None = None) -> tuple[NoticeRequirement, ...]:
    """The rows that are required only for some events: those that carry a condition."""
    return tuple(r for r in (REQUIREMENTS if rows is None else rows) if r.applies is not ALWAYS)


def applicable(facts: Facts | None = None, rows: Iterable[NoticeRequirement] | None = None) -> Partition:
    """Each row's answer for the facts on hand (the event's, as the caller says them, beside the association's
    standing ones), in the rows' order:

    - ``applies``: the notice is required, on its clock. A row with no condition is here: it is required whenever
      its event happens;
    - ``does_not_apply``: not required, with the fact that decided it (``Verdict.deciding``);
    - ``undetermined``: the facts do not say, with the missing fact (``Verdict.question()``). Never "not required".

    With no facts every conditional row is undetermined."""
    return partition(REQUIREMENTS if rows is None else rows, facts or Facts())


def about(rows: Iterable[NoticeRequirement], said: Iterable[Fact]) -> tuple[tuple[NoticeRequirement, ...],
                                                                             tuple[NoticeRequirement, ...]]:
    """The conditional rows an event's facts are about, and the rest. ``said`` are the facts the caller stated. A row
    is about the event when its condition tests one of them or another fact of the same kind of event
    (``notice_conditions.SAME_EVENT``), or tests no fact of one event at all (its condition is the association's
    standing facts alone). The rest turn on another kind of event, whose facts were not said: they are set aside, not
    answered. With nothing said, every row is kept."""
    said = same_event(frozenset(said))
    kept, aside = [], []
    for row in rows:
        own = frozenset(f for f in facts_tested(row.applies) if f.per_event)
        (kept if not said or not own or own & said else aside).append(row)
    return tuple(kept), tuple(aside)


def line(row: NoticeRequirement) -> str:
    """One row as the catalog lists it: its key, statute, kind of delivery, and clock."""
    clock = "; ".join(t.describe() for t in row.timing) or (f"with {row.carried_by}" if row.carried_by else "")
    kind = row.kind.value if row.kind else ", ".join(m.name.lower() for m in row.methods) or "no delivery"
    return f"  {row.key:32} {row.statute:10} {kind:28} {clock}" + ("" if row.verified else "  [unverified]")


def _to_say(fact: Fact) -> str:
    """How a missing fact is settled: an event's fact is said by the caller, a standing one by the profile or a person."""
    if fact.per_event:
        return f"say it with --fact {fact.value}=WORD ({', '.join(str(m.value) for m in fact.spec.kind)})"
    return "a standing fact: the profile states it, or jason applies --questions asks a person"


def applicable_lines(facts: Facts | None = None, said: Iterable[Fact] = (),
                     rows: Iterable[NoticeRequirement] | None = None) -> list[str]:
    """The conditional rows in their three groups, as plain lines. ``said`` are the facts the caller stated for the
    event; rows about another kind of event are set aside and named, not answered."""
    facts = facts or Facts()
    every = tuple(REQUIREMENTS if rows is None else rows)
    shown, aside = about(conditional(every), said)
    parts = applicable(facts, shown)
    lines = [f"{len(conditional(every))} of {len(every)} notice requirements are required only for some events. Each is "
             f"answered from the facts on hand.",
             "The others carry no condition: each is required whenever its event happens (jason notices --catalog)."]
    if facts.values:
        lines += ["", "Facts on hand"] + [f"  {v.describe()}" for v in facts.values]
    lines += ["", f"Applies: required when its event happens, on its clock ({len(parts.applies)})"]
    for row, verdict in parts.applies:
        lines += [line(row), f"      rule: {verdict.condition.describe()}"]
    lines += ["", f"Does not apply: not required ({len(parts.does_not_apply)})"]
    for row, verdict in parts.does_not_apply:
        lines += [line(row), "      decided by " + "; ".join(v.describe() for v in verdict.deciding)]
    lines += ["", f"Undetermined: the facts do not say, which is never \"not required\" ({len(parts.undetermined)})"]
    for row, verdict in parts.undetermined:
        lines += [line(row), f"      rule: {verdict.condition.describe()}"]
        lines += [f"      unknown: {fact.topic}: {_to_say(fact)}" for fact in verdict.missing]
        if verdict.conflicting:
            lines.append("      sources disagree: " + "; ".join(v.describe() for v in verdict.conflicting))
    if aside:
        lines += ["", f"Set aside ({len(aside)}): each turns on another kind of event, whose facts were not said"]
        for row in aside:
            own = sorted(f.value for f in facts_tested(row.applies) if f.per_event)
            lines.append(f"  {row.key:32} {row.statute:10} turns on: {', '.join(own)}")
    return lines


def provisions(community: object | None = None, key: str | None = None) -> tuple[NoticeProvision, ...]:
    """The profile's governing-document notice clauses (``Community.notice_provisions()``), for one requirement when
    ``key`` is given."""
    found = tuple(getattr(community, "notice_provisions", lambda: ())()) if community is not None else ()
    return tuple(p for p in found if key is None or p.requirement == key)


def for_ledger(key: str) -> NoticeRequirement | None:
    """The requirement a notice's ledger key belongs to: the longest requirement key it starts with
    ("board-meeting-2026-10-20" is a board-meeting notice). None when no key fits; then say which."""
    fits = [r for r in REQUIREMENTS if key == r.key or key.startswith(r.key + "-")]
    return max(fits, key=lambda r: len(r.key)) if fits else None


def rule_requirements(rule: object) -> tuple[NoticeRequirement, ...]:
    """The requirements a ``NoticeRule`` delivers: those it names, else the one with its own key."""
    keys = tuple(getattr(rule, "requirements", ()) or ()) or (str(getattr(rule, "key", "")),)
    return tuple(r for r in REQUIREMENTS if r.key in keys)


def effective(key: str, community: object | None = None):
    """The requirement, its clocks made stricter by the documents that ask more, the notes on what changed, and the
    provisions that touch it (the ones that ask less or differ are leads, not applied)."""
    row = requirement(key)
    found = provisions(community, key)
    base = row.timing or (requirement(row.carried_by).timing if row.carried_by else ())
    clocks, notes = combined(base, found)
    for p in found:
        if p.comparison in (Comparison.LESS, Comparison.DIFFERENT):
            notes.append(f"{p.citation} {p.comparison.value}: {p.lead or p.says} The statute governs (CIV 4205).")
    return row, clocks, notes, found


__all__ = ["REQUIREMENTS", "about", "applicable", "applicable_lines", "conditional", "effective", "for_ledger", "line",
           "provisions", "requirement", "rule_requirements"]
