"""The notices Mystique sends, with who receives each and how (jason.community.notices).

Read from the statutes on file (data/authorities): individual delivery under 4040 for the annual budget report (5300)
and policy statement (5310), an assessment increase (5615), a lapse or cancellation of insurance (5810), and a member's
discipline (5855, one member); general notice under 4045 for a board meeting (4920) and a proposed or adopted rule
change (4360). The secondary copies of 4040(b) go only with the annual reports and the assessment collection notices
(Article 2 of Chapter 8 and 5710). A building's flood policy notice is the association's own practice, sent to that
building's owners.
"""

from __future__ import annotations

from jason.community.notices import NoticeKind, NoticeRule

I, G = NoticeKind.INDIVIDUAL, NoticeKind.GENERAL

NOTICE_RULES: tuple[NoticeRule, ...] = (
    # The request also goes to each secondary address on file, and (fiscal 2027, the board's call of October 1, 2026)
    # to the addresses the county roll gives for an owner, kept as unconfirmed secondary records until the owner
    # answers: the request is how the owner confirms or drops them.
    NoticeRule("owner-info-solicitation", "Owner information request", "CIV 4041(b)", I, courtesy_email=True,
               secondary_copies=True, unconfirmed_copies=True,
               note="each owner's election governs (mail without one); every owner with an email also gets a courtesy "
                    "copy with the online form's link; a copy by mail to each secondary record, unconfirmed ones too"),
    NoticeRule("annual-budget-report", "Annual budget report", "CIV 5300, 5320, 4040(b)", I, secondary_copies=True),
    NoticeRule("annual-policy-statement", "Annual policy statement", "CIV 5310, 4040(b)", I, secondary_copies=True),
    NoticeRule("assessment-increase", "Notice of an increase in assessments", "CIV 5615", I,
               note="30 to 60 days before the increase is due"),
    NoticeRule("collection-notice", "Assessment collection notice", "CIV 5650-5690, 5710, 4040(b)", I,
               secondary_copies=True, reach="one owner",
               note="the pre-lien notice also goes by certified mail (5660)"),
    NoticeRule("insurance-change", "Insurance lapse, cancellation, or reduced coverage", "CIV 5810", I,
               note="as soon as reasonably practicable"),
    NoticeRule("flood-policy", "A building's flood policy", "association practice; CIV 5300(b)(9)", I, reach="unit tag",
               note="the building's owners: give its building tag"),
    NoticeRule("discipline", "Notice of hearing or decision", "CIV 5855", I, reach="one owner",
               note="10 days before the hearing; the decision within 14 days"),
    NoticeRule("board-meeting", "Board meeting notice and agenda", "CIV 4920, 4045", G,
               note="posted at least 4 days before (2 for executive session only)"),
    NoticeRule("rule-change", "Proposed or adopted rule change", "CIV 4360, 4045", G,
               note="28 days before the decision; the adopted rule within 15 days after"),
)
