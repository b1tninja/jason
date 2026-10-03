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
    Lesson("rules-changed-without-adoption", date(2026, 10, 2), (Area.GOVERNING,),
           "Revision detection found rule text in circulation with no adoption on record: the election rules' electronic "
           "voting provisions in copies emailed from May 2025; the fine schedule's 2024 changes (the resident permit fee "
           "and struck fee lines); the license plate data opt-out removed in September 2024.",
           "The working Docs were edited and their copies sent as the rules, with no rule-change notice or minutes found.",
           "A decision for the board, with counsel: which text is in force, and whether to notice and adopt the changes "
           "(Civil Code 4360) or restore the adopted text.", Status.DECISION,
           docs=("data/reports/revisions-owners-manual.md", "data/reports/revisions-election-rules.md")),
    Lesson("secrets-in-handoff-doc", date(2026, 10, 2), (Area.ONBOARDING,),
           "The knowledge-transfer Doc holds a portal password and lock and fire panel codes in plain text.",
           "It was written as a working handoff list, with access details beside the records.",
           "The board moves them to Keeper, changes them, and removes them from the Doc; a scan of Docs for credential "
           "words could guard it.", Status.DECISION, docs=("mystique/notes/onboarding/README.md",)),
    Lesson("rules-without-adopted-words", date(2026, 10, 3), (Area.GOVERNING,),
           "Most of the rules' passages changed with no adoption on record (20 of 24) have no adopted version on "
           "record either, so the official rules print jason's note alone for them.",
           "The working Doc was edited over years without rule-change notices, and earlier adopted texts were not kept.",
           "The board adopts the working words through 4360 (jason rule-change --from-manual) or records the adoptions "
           "that cover them; the parking demarcation passages may be covered by the 2022 parking adoption.",
           Status.DECISION, docs=("data/manual/owners-manual/render.json",)),
)
