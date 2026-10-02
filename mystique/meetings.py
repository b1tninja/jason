"""What Mystique's meeting files are called, and where the ones that are not meeting records sit.

The rules run in order: an executive session agenda before an agenda, draft minutes before minutes, a Zoom transcript or
chat before a recording. Audio and video count as a meeting recording only when the name or path says so (a Zoom
"GMT..._Recording" file, a Meetings folder); the phone videos in a violation folder are evidence, not meetings. The
bylaws' audio book is the governing documents read aloud.

The Decorum Rules on every agenda say the Secretary's recording "is deleted once the minutes have been prepared".
"""

from __future__ import annotations

from jason.community.agenda_items import ItemRule
from jason.community.agenda_links import LinkKind, LinkRule
from jason.community.meeting_records import EmailRule, RecordKind, RecordRule
from jason.community.symbols import DocumentKind

RECORD_RULES: tuple[RecordRule, ...] = (
    RecordRule(RecordKind.EXECUTIVE_AGENDA, r"executive session agenda"),
    RecordRule(RecordKind.TRANSCRIPT, r"transcript|\.vtt$"),
    RecordRule(RecordKind.CHAT, r"chat\.txt$|newchat"),
    RecordRule(RecordKind.AI_SUMMARY, r"meeting summary|quick recap|ai companion", needs_context=True),
    RecordRule(RecordKind.VIDEO, r"\.(mp4|mov)$", needs_context=True),
    RecordRule(RecordKind.AUDIO, r"\.(m4a|mp3|wav)$", needs_context=True),
    RecordRule(RecordKind.DRAFT_MINUTES, r"draft[^/]*minutes|minutes[^/]*draft"),
    RecordRule(RecordKind.MINUTES, r"minutes"),
    RecordRule(RecordKind.AGENDA, r"agenda"),
    RecordRule(RecordKind.NOTICE, r"meeting notice|notice of (?:the )?(?:annual|special|board|regular)? ?meeting"),
)

# Emails about a meeting, as the association's Gmail holds them (headers only). PayHOA sends the board's notice to every
# member and a copy to the association; Zoom emails the host when the recording, its assets, and the AI summary are
# ready (an emailed summary is a copy of it outside Zoom); members and directors reply on the agenda's thread.
EMAIL_RULES: tuple[EmailRule, ...] = (
    EmailRule(RecordKind.NOTICE, r"meeting of the (?:board|members)|annual (?:membership )?meeting|special meeting", ("payhoa.com",),
              "PayHOA's copy of the notice sent to members"),
    EmailRule(RecordKind.AI_SUMMARY, r"^meeting summary for", ("zoom.us",), "Zoom emailed the AI summary"),
    EmailRule(RecordKind.RECORDING_NOTICE, r"cloud recording .* is now available|meeting assets for .* are ready", ("zoom.us",)),
    EmailRule(RecordKind.CORRESPONDENCE, r"^(?:re|fwd?):.*(?:agenda|minutes|meeting of the board)"),
    EmailRule(RecordKind.CORRESPONDENCE, r"(?:document shared with you|share request for).*(?:agenda|minutes)"),
)

# PayHOA's communications log is searched by these words; each communication is one row per recipient.
COMMUNICATION_SEARCH: tuple[str, ...] = ("Meeting", "Agenda", "Minutes")

# What an agenda's links point at, in order: the board attaches Drive files and folders as smart chips, photo albums of a
# repair as Google Photos links, and cites the statute (leginfo, davis-stirling.com) and the court's case page.
LINK_RULES: tuple[LinkRule, ...] = (
    LinkRule(LinkKind.DRIVE_FOLDER, r"drive\.google\.com/drive/(?:u/\d+/)?folders/"),
    LinkRule(LinkKind.GOOGLE_DOC, r"docs\.google\.com/(?:document|spreadsheets|presentation)"),
    LinkRule(LinkKind.DRIVE_FILE, r"drive\.google\.com/(?:file/d/|open\?id=|uc\?)"),
    LinkRule(LinkKind.PHOTOS, r"photos\.app\.goo\.gl|photos\.google\.com"),
    LinkRule(LinkKind.ZOOM, r"zoom\.us/"),
    # The footer's chip for the meeting's calendar event (September 30, 2026: 80 agendas carry one).
    LinkRule(LinkKind.CALENDAR, r"google\.com/calendar/|calendar\.google\.com/"),
    # A footnote cites the case law on Justia (Nahrstedt, Bernardo Villas).
    LinkRule(LinkKind.LAW, r"leginfo\.legislature\.ca\.gov|davis-stirling\.com|law\.cornell\.edu|law\.justia\.com"),
    LinkRule(LinkKind.COURT, r"journaltech\.com|saccourt\.ca\.gov|courts\.ca\.gov"),
)

# What an agenda item brings to the table, by its title: the treasurer's report brings the reports and statements, a
# claim brings the adjuster's letters, the estimates, the police report, and photos. Every rule that matches adds its
# kinds, in order. A kind here is what the board used a file as, a lead for classifying it, never the classification.
K = DocumentKind
AGENDA_ITEM_RULES: tuple[ItemRule, ...] = (
    ItemRule(r"minutes", (K.MINUTES,)),
    ItemRule(r"treasurer|financial|bank|reconcil", (K.TREASURER_REPORT, K.FINANCIAL_STATEMENT, K.BANK_STATEMENT)),
    ItemRule(r"reserve|investment|\bcd\b|certificate of deposit", (K.BANK_STATEMENT, K.RESERVE_STUDY, K.FINANCIAL_STATEMENT,
                                                                   K.PROPOSAL, K.RESOLUTION)),
    ItemRule(r"budget", (K.BUDGET, K.FINANCIAL_STATEMENT)),
    ItemRule(r"tax|cpa|audit|review of financial", (K.TAX_RETURN, K.FINANCIAL_REVIEW, K.CONTRACT, K.TAX_BILL)),
    ItemRule(r"insurance claim|claim\(s\)|\bclaim\b|loss|collision|leak|damage", (K.CLAIM_LETTER, K.CLAIM_ESTIMATE, K.CLAIM_PAYMENT,
                                                                                   K.POLICE_REPORT, K.IMAGE, K.PROPOSAL)),
    ItemRule(r"insurance|renewal|policy period", (K.INSURANCE_POLICY, K.EVIDENCE_OF_INSURANCE, K.LOSS_RUN,
                                                  K.PROPOSAL, K.ANNUAL_DISCLOSURE)),
    ItemRule(r"proposal|maintenance|repair|garage door|roof|landscap|mulch|paint|striping|pump|tree", (K.PROPOSAL, K.INVOICE,
                                                                                                       K.INSPECTION_REPORT, K.IMAGE)),
    ItemRule(r"pest|rodent|termite", (K.INSPECTION_REPORT, K.PROPOSAL, K.INVOICE)),
    ItemRule(r"fire|sprinkler|alarm|inspection|sb ?326|balcon", (K.INSPECTION_REPORT, K.ELEVATED_ELEMENT_INSPECTION, K.PROPOSAL)),
    ItemRule(r"contract|management|agreement|lock ?box|vendor", (K.CONTRACT, K.PROPOSAL)),
    ItemRule(r"collection|delinquen|lien|foreclos", (K.DELINQUENCY_NOTICE, K.RECORDED_LIEN, K.CONTRACT, K.OWNER_STATEMENT,
                                                            K.RESOLUTION)),
    ItemRule(r"legal|lawsuit|litigation|counsel|attorney|settlement|defect", (K.LEGAL_CORRESPONDENCE, K.LEGAL_BRIEF, K.SETTLEMENT)),
    ItemRule(r"hearing|disciplin|violation|conduct|fine", (K.VIOLATION_NOTICE, K.NOTICE, K.IMAGE)),
    ItemRule(r"architectural|arc\b|home improvement|alteration", (K.FORM, K.PLAN_SET)),
    ItemRule(r"election|candidate|ballot|annual meeting|inspector of election", (K.NOTICE, K.BALLOT, K.ELECTION_RESULTS, K.ELECTION_RULES)),
    ItemRule(r"rule|policy|resolution|decorum|bylaw|cc&r|ccr", (K.POLICY, K.OPERATING_RULES, K.RESOLUTION, K.AMENDMENT)),
    ItemRule(r"committee|report", (K.COMMITTEE_REPORT,)),
    ItemRule(r"security|camera|flock|patrol", (K.SECURITY_REPORT, K.CONTRACT, K.PROPOSAL)),
    ItemRule(r"utilit|smud|water|sewer", (K.UTILITY_BILL,)),
)

NOT_MEETING_RECORDS: tuple[str, ...] = (
    "My Drive/Governing Documents/Audio Book/",
)

RECORDING_RULE = "Decorum Rules (on every agenda): the Secretary's recording is deleted once the minutes have been prepared"
