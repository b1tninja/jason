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
    Lesson("fire-reports-filed-loose", date(2026, 10, 3), (Area.DOCUMENTS,),
           "The fire alarm reports were scattered: the September 2025 reports loose in the root of My Drive (and PayHOA's "
           "Email Attachments), the 2024 NFPA 72 report in the False Alarm folder, and the 2023 sprinkler report in "
           "Reports. No report has been filed since September 2025.",
           "Reports arrive only as email attachments (Signal Service's portal keeps no files), and each was saved where "
           "the task of the day needed it. Nothing tied them to the master policy's P-1 sprinkler safeguard, which makes "
           "them insurance evidence.",
           "The board adopts the keeping rule in mystique/notes/fire-protection-records.md; then a Drive folder "
           "(Reports/Fire Protection) and a non-public PayHOA folder synced from it, with a kind rule that files each "
           "vendor report there. Until then the reports stay where they are.",
           Status.DECISION, docs=("mystique/notes/fire-protection-records.md", "board item fire-alarm-deficiencies")),
    Lesson("signed-inspection-never-scheduled", date(2026, 10, 3), (Area.DOCUMENTS,),
           "The board signed The Fire Sprinkler Company's annual and quarterly inspection proposal on April 17, 2024, and no "
           "inspection followed; the company's June 18, 2025 email offering to schedule the annual went unanswered. An "
           "invoice titled a flow switch replacement was an investigation, and the problem was still open.",
           "A signed proposal is not a schedule: nothing turned it into dates, and the vendor's own scheduling email sat in a "
           "mailbox as one more thread awaiting us. Invoice subjects were read as what the work was.",
           "The obligation rows (mystique/obligations.py) now carry the contract and the open waterflow issue, so jason "
           "deadlines shows them overdue; the board sets the inspection dates. Still open: a check that reads each "
           "vendor invoice's line description, not its email subject.",
           Status.OPEN, docs=("mystique/notes/fire-protection-records.md", "board item fire-sprinkler-inspections")),
)
