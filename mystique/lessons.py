"""Mystique's own lessons, beside jason's general ones (``jason.community.lessons``): what this association's cycles
taught that names its units, its counts, or its board's decisions."""

from datetime import date

from jason.community.lessons import Area, Lesson, Status

LESSONS = (
    Lesson("co-owners-share-an-envelope", date(2026, 10, 2), (Area.MAILROOM, Area.OWNER_INFO),
           "The 2027 letters reached all 76 mailed units, but 24 of the 107 owners planned a letter shared an envelope "
           "addressed to a co-owner at the same address (17 at the unit, 7 at a shared mailing address).",
           "PayHOA's Mailroom sends co-owners at one address one letter.",
           "The board decides whether each owner gets an envelope by name next cycle (one send per owner, at the "
           "letter price each).",
           Status.DECISION, docs=("data/owner-info/send-plan-2026-10-02.md",)),
    Lesson("occupancy-waits-for-the-board", date(2026, 10, 2), (Area.OWNER_INFO,),
           "Returns came back with occupancy blank, and some units the records read as not owner-occupied are not "
           "tagged Rental (which ones: jason report occupancy-signals).",
           "Asking owners about occupancy touches the rental approvals the board has not decided.",
           "Follow-ups to owners about occupancy are held until the board decides rental-approvals-4-15; the "
           "occupancy-signals report carries the evidence to the meeting.",
           Status.DECISION, docs=("board item rental-approvals-4-15", "jason report occupancy-signals")),
    Lesson("tax-form-unsettled", date(2026, 10, 2), (Area.GOVERNING,),
           "The association's filed returns are Form 1120-H, but the members voted a Revenue Ruling 70-604 resolution "
           "and a 2026 estimated payment was applied to Form 1120, which an 1120-H filer does not make.",
           "Which return the association files was never recorded where jason reads it.",
           "The CPA confirms the form the 2025 return used; then the rev-rul-70-604 assignment drops its condition or "
           "is marked not applicable.",
           Status.DECISION, docs=("mystique/schedule.py (rev-rul-70-604)",)),
)
