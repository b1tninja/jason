"""Mystique's own evidence rules: what shows done a duty it covers by its own documents' sections
(``jason.community.schedule_evidence``; jason's general rules serve the statutes and the notice catalog).

Each row names the document sections its assignment covers (``schedule.py``) and the words the association's
minutes use for the item.
"""

from __future__ import annotations

from jason.community.schedule_evidence import EvidenceRule, EvidenceSource, Weight

EVIDENCE_RULES = (
    # The Fiscal Management Resolution's yearly review of the reserve investment plan: the minutes' agenda item on the
    # investment of reserve funds shows the board took up the reserves' investment, not that it reviewed the plan.
    EvidenceRule("reserve-investment-item",
                 ("resolution-policy-resolution-fiscal-management-17d3#INVESTMENT OF RESERVE FUNDS",),
                 EvidenceSource.MINUTES_TEXT, Weight.SUPPORTING, words=(r"invest\w*\s+of\s+reserve\s+funds",),
                 window=(-120, 90),
                 note="the minutes take up the investment of reserve funds; the plan's yearly review is the duty"),
    # Officers elected at the organizational meeting after the annual meeting (bylaws 10, 11).
    EvidenceRule("officers-elected", ("bylaws#10", "bylaws#11"), EvidenceSource.MINUTES_TEXT,
                 words=(r"election\s+of\s+officers", r"organizational\s+meeting"),
                 note="the minutes of the organizational meeting"),
)
