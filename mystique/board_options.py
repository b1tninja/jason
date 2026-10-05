"""The options and draft motions written for particular board items (``Community.board_item_options()``).

Each row is the directors' packet's **Options** and **Draft motion** for one item, by the item's id in the board's
action items. An item with no row gets the packet's generic frame (act, refer, or defer, and a motion built from the
item's ask). The options are the board's to weigh and a motion is a starting point; jason decides nothing.
"""

from __future__ import annotations

from jason.community.board_items import ItemOptions

BOARD_ITEM_OPTIONS: tuple[ItemOptions, ...] = (
    ItemOptions("reserve-loan-march-2024",
                ("Adopt a repayment plan restoring the $16,000 to reserves by a set date",
                 "Find, with documentation, that a temporary delay is in the association's best interest (5515(d))",
                 "Levy a special assessment to recover the funds (5515(e); limits in 5605)",
                 "Establish first whether the loan was repaid in a way the records do not show"),
                "Move that the board direct the treasurer to account for the $16,000 transferred from reserves on March 14, "
                "2024, and adopt the following plan to restore it to the reserve fund by ______: ______."),
    ItemOptions("cost-centers-not-kept",
                ("Refer to counsel for an opinion on the annexations' cost center requirement and past allocations",
                 "Direct the budget committee to present the 2027 budget with the General, Phases 1 and 2, and Annexed "
                 "Property components",
                 "Direct the reserve preparer to separate the cost centers' components and funding"),
                "Move that the board refer the cost center requirement of the declarations of annexation (section 1.3) to "
                "counsel and direct that the 2027 budget and reserve funding plan be prepared with the cost centers kept apart."),
    ItemOptions("settlement-disclosure-6100",
                ("Direct counsel to prepare a supplemental 6100(a) disclosure to members (amendments are allowed and "
                 "keep their privilege, 6100(b), (c))",
                 "Direct the manager or secretary to add the latest 6100 information to every resale packet (4525(a)(7))",
                 "Direct the reserve preparer to itemize the unspent settlement funds separately (4177(b), 5565(b)(3))",
                 "Ask counsel first whether any defects were corrected, which would narrow the disclosure"),
                "Move that the board direct counsel to prepare, for the board's review, a supplemental disclosure to "
                "the members under Civil Code 6100 of the October 2023 settlement with the builder; that the latest "
                "6100 information be included in every resale disclosure packet under Civil Code 4525(a)(7); and that "
                "the reserve study preparer itemize the unspent settlement funds separately under Civil Code 4177(b) "
                "and 5565(b)(3)."),
    ItemOptions("defect-repairs-and-941-review",
                ("Adopt a repair plan by priority within the settlement funds (the settled items were "
                 "priced well above the net received), starting with site drainage and the garage entry "
                 "aprons",
                 "Decide whether the 2023-2024 JB Bostick concrete and seal coat work counts against the "
                 "settlement funds, and have the treasurer track the remaining funds as their own fund",
                 "Ask counsel in writing to prepare or review the repair contracts under the fee "
                 "agreement's post-recovery scope, and for the signed fee agreement",
                 "Calendar a building-condition review with counsel before the first 10-year date",
                 "Discuss the scope and the cost of repair in executive session: the pricing is marked "
                 "for mediation only (Evidence Code 1119)"),
                "Move that the board ask Berding & Weil to confirm in writing that drafting, review, and "
                "negotiation of contracts to repair the items released in the October 2023 settlement fall "
                "within its contingency fee agreement, and to provide the signed agreement; direct [a "
                "director] to obtain proposals for the site drainage and garage entry repairs for the "
                "board's review; and schedule a review of building conditions with counsel before "
                "February 2029."),
    ItemOptions("minutes-ai-recap-executive",
                ("Direct the Secretary to replace the posted minutes (PayHOA Meetings and Resale Documents) with "
                 "versions that note executive session matters only generally, keeping the originals preserved "
                 "under the litigation hold",
                 "Stop appending Zoom's AI recap to the minutes; prepare minutes from the template (motions, "
                 "roll-call votes, a general note of the executive session)",
                 "Ask counsel whether members or buyers who received the resale packets need a notice"),
                "Move that the board direct the Secretary to (1) prepare corrected minutes for each meeting whose "
                "posted minutes carry Zoom's AI recap, noting executive session matters only generally (Civil Code "
                "4935(e)), for approval at the next meeting; (2) replace the posted copies once approved, keeping "
                "the originals preserved; and (3) no longer append AI summaries to minutes."),
    ItemOptions("meeting-recordings-retention",
                ("Adopt a meeting records policy: approved minutes are the only record of proceedings; the "
                 "Secretary records open sessions only, announced, solely to prepare minutes; the recording, "
                 "transcript, and any AI summary are deleted within 30 days after the minutes are approved, "
                 "except anything under a litigation hold",
                 "Keep transcripts and AI summaries of open sessions as working papers, access limited to "
                 "directors, deleted on a fixed schedule; recordings deleted after the minutes",
                 "Turn off Zoom AI Companion and stop cloud recording before adjourning to executive session, "
                 "or hold executive session as a separate unrecorded meeting; never record hearings or counsel",
                 "Before deleting anything, ask defense counsel to confirm a litigation hold for the "
                 "26CV016125 matter and release what is not needed"),
                "Move that the board (1) direct that no meeting recording, transcript, AI summary, or chat be "
                "deleted until defense counsel for 26CV016125 confirms in writing what must be preserved; (2) "
                "direct the Secretary to turn off Zoom AI Companion and to stop recording before any executive "
                "session; and (3) direct the Secretary to present a meeting records policy for adoption at the "
                "next meeting."),
    ItemOptions("meeting-schedule-resolution",
                ("Adopt a resolution fixing regular meetings on the third Tuesday of every month at 7:00 pm on Zoom",
                 "Keep the quarterly schedule and notice the other months as special meetings"),
                "Move that the board adopt an administrative resolution fixing regular board meetings on the third "
                "Tuesday of each month at 7:00 pm by teleconference, superseding Resolution 20230130-1 as to regular meetings."),
    ItemOptions("fire-sprinkler-inspections",
                ("Engage a State Fire Marshal licensed (A or C-16) firm for the annual inspection and test now",
                 "Contract the quarterly inspections, or train a person to do them (19 CCR 904.1)",
                 "Schedule the five-year internal inspection"),
                "Move that the board authorize the treasurer to engage ______ for the annual fire sprinkler inspection and "
                "test of buildings 3 and 8, not to exceed $______, and to arrange the quarterly inspections."),
)
