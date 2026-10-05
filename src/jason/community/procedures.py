"""Standard operating procedures: a task's steps in order, each with the command that does it, what to check, and where
to read more. A procedure is an index into the reference material (docs, reports, lessons) for one job, so whoever
runs it next year, a person or an agent, starts from the last time's knowledge rather than from memory.

``jason sop`` lists them; ``jason sop KEY`` prints one, its steps, and the lessons still open in its areas
(``jason.community.lessons``); ``{REPORT:sop key=KEY}`` carries one into a document. A step that a lesson changed names
that lesson, so the reason travels with the step. General procedures are here; a community's own (its dates, its
board's habits) are its specification's (``Community.procedures()``).
"""

from __future__ import annotations

from dataclasses import dataclass

from jason.community.lessons import Area


@dataclass(frozen=True)
class Step:
    do: str                              # what to do, in a sentence
    command: str = ""                    # the command that does it, if any
    check: str = ""                      # what to look at before going on
    refs: tuple[str, ...] = ()           # docs, reports ({REPORT:...}), or other procedures to read
    lessons: tuple[str, ...] = ()        # lesson keys that shaped this step
    person: bool = False                 # a person's step: jason does not do it


@dataclass(frozen=True)
class Procedure:
    key: str
    title: str
    when: str                            # when it is run
    areas: tuple[Area, ...]
    purpose: str
    steps: tuple[Step, ...]
    refs: tuple[str, ...] = ()           # the main reading for the whole procedure


PROCEDURES: tuple[Procedure, ...] = (
    Procedure(
        "owner-info-cycle", "The annual owner information request (Civil Code 4041)",
        "Each year: open in mid-September; answers by late October; entered in PayHOA by November 1.",
        (Area.OWNER_INFO, Area.FORMS, Area.EMAIL, Area.MAILROOM),
        "Ask every owner how to deliver notices, a second address, any representative, and occupancy; record the "
        "answers in PayHOA at least 30 days before the annual reports.",
        (
            Step("Set the cycle's dates, leaving room for one correction before the answer-by date.",
                 refs=("OWNER_INFO_CYCLE in the specification's forms.py", "docs/owner-information.md"),
                 lessons=("leave-room-to-correct",)),
            Step("Settle the board's decisions the cycle depends on: rental approvals, what to ask likely "
                 "non-owner-occupied units, co-owner envelopes.", command="jason board --packet",
                 refs=("{REPORT:occupancy-signals}", "jason lessons --open --area owner-info"), person=True),
            Step("Update the PayHOA form in place (never replace a linked form), and confirm it is live and locked.",
                 command="jason forms --payhoa owner-info --update", check="questions kept their ids; help under 255 "
                 "characters", refs=("docs/forms.md",), lessons=("paper-cannot-require",)),
            Step("Round-trip made-up answers as the test owner.", command="jason forms --payhoa-test owner-info --yes",
                 check="every answer reads back"),
            Step("Open the form's link as an owner, in a private window, signed out and signed in.",
                 check="it lands on the form for the unit, not the dashboard", lessons=("form-link-needs-unit",
                 "test-as-an-owner"), person=True),
            Step("Build the letter and the fillable form from the template Docs.",
                 command="jason packet owner-information --year YEAR --make-templates --yes; then --build --yes",
                 check="four pages (a fifth billed page adds $2.25); the form prints the way online, not a link",
                 refs=("docs/packets.md",)),
            Step("Plan who gets what: email, letter, or both; and the occupancy signals.",
                 command="jason owner-info --send-plan", refs=("data/owner-info/send-plan-DATE.md",)),
            Step("Write the email in Markdown and keep its Doc on the letterhead.",
                 command="jason broadcast data/drafts/NAME.md --to-doc --yes",
                 refs=("docs/drafts-and-forms.md (one Markdown source)",), lessons=("one-source-per-document",
                 "name-the-unit")),
            Step("Preview one owner's email, then send yourself a test.",
                 command="jason owner-info --email-batch --message NAME.md --only me --preview OUT.html; then --yes",
                 check="the subject names the unit; every form link carries ;unitId=; the pictures show"),
            Step("Send the email batch.", command="jason owner-info --email-batch --message NAME.md --yes "
                 "--confirmed-by NAME", refs=("docs/batches.md",)),
            Step("Read the emails' delivery: bounced, skipped, or never shown delivered; mail those owners.",
                 command="jason notices owner-info-YEAR --sync", check="the follow-ups owed; again after 24 hours, "
                 "when PayHOA marks a message with no delivery event failed", refs=("procedure notice-delivery",),
                 lessons=("bounces-are-silent",)),
            Step("The next day, test the emailed link as an owner again; only then mail the letters.",
                 command="jason owner-info --mail-batch --yes --confirmed-by NAME",
                 check="the Mailroom preview's recipients and price", refs=("jason mailroom --prices",),
                 lessons=("letters-cannot-be-recalled", "letter-link-per-unit")),
            Step("Check for new responses, read each returned form, and confirm what it says. An owner can answer in "
                 "PayHOA, by a reply email, by a mailed scan, or in a Google Form; the check looks at all four.",
                 command="jason responses --check; jason responses --list --new; jason responses --read ID --by NAME; "
                         "jason responses --confirm ID --by NAME",
                 check="a reading is evidence for a person; nothing is an answer until a person confirms it; nothing is "
                       "written to PayHOA by a check; a channel that failed says why under its last check (the board's "
                       "new_responses tool shows each channel's age)",
                 refs=("docs/responses-design.md",),
                 lessons=("returns-by-the-same-rules", "form-return-found-by-searching-the-mailbox",
                          "payhoa-submission-list-row-shape-unconfirmed"), person=True),
            Step("Triage the answers as they come in: what to record, enter, confirm, or hold for the board.",
                 command="jason owner-info --responses --canvas",
                 check="each finding's outcome; the board's questions in its canvas (mystique/notes/canvas)",
                 lessons=("answers-need-a-policy",)),
            Step("Record the answers as they come in: dry run, then write; or as an approval, decided item by item "
                 "by a named person and applied only if nothing changed since. An answer a person confirmed from an "
                 "email or a scan (keyed) is planned by --apply like a PayHOA answer, and the arrival is marked "
                 "recorded once its writes are made.",
                 command="jason owner-info --apply --payhoa; then --yes --by NAME (or jason approvals plan "
                         "owner-info-tags; show ID; decide ID --items ... --by NAME; submit ID; apply ID; apply ID --yes)",
                 check="each write's reason; a request left open says why; held items are never approved; apply "
                       "refuses when the plan changed since review; each request's evidence opens with its last read "
                       "from PayHOA (a request no plan has read since: jason sync-request-files --requests N)",
                 lessons=("returns-by-the-same-rules", "same-as-unit-needs-no-person", "complete-only-after-writes",
                          "apply-loses-partial-results", "request-read-thrown-away")),
            Step("Remind the owners who have not answered, a week before the answer-by date.",
                 command="jason owner-info --email-batch --follow-up reminder --message REMINDER.md"),
            Step("On the entry date, close the cycle: remove the unconfirmed addresses, and note what is still open.",
                 refs=("docs/owner-information.md",), person=True),
            Step("Write what went wrong or could be better as lessons, and update this procedure.",
                 command="jason lessons --area owner-info", refs=("AGENTS.md (Lessons and procedures)",)),
        ),
        refs=("docs/owner-information.md", "docs/forms.md", "docs/batches.md", "docs/payhoa-reports.md"),
    ),
    Procedure(
        "board-packet", "The board packet for a meeting",
        "Before each board meeting (the third Tuesday): a week ahead, and again the day before.",
        (Area.DOCUMENTS,),
        "Give the directors each open-session item researched, the standing reports, and the evidence, as of the "
        "meeting.",
        (
            Step("Before the notice day, read the meeting's clocks: the last day to give members notice and the "
                 "agenda (Civil Code 4920), and the minutes still owed from the last meeting (4950(a)). Rebuild the "
                 "catalog first so a notice already sent is on record.",
                 command="jason meetings --sync; jason schedule-evidence --watch",
                 check="the notice goes out by its day, at least four days before the meeting (longer if a document "
                       "asks more); the last meeting's minutes, or a draft marked as one, are available to members "
                       "within 30 days; a posting jason cannot see is recorded (jason schedule --done KEY DUE --by "
                       "NAME --evidence TEXT); a notice day already passed means a later meeting day noticed in time",
                 refs=("docs/schedule.md (The watch)", "docs/attention.md"), lessons=("meeting-clocks-read-forward",)),
            Step("Say what kind of meeting it is and how it is held, and list the notices the law requires for that "
                 "meeting: the rows that apply, those that do not with the fact that decided each, and those left "
                 "undetermined with the fact still missing.",
                 command="jason notices --catalog --fact board_meeting=ordinary --fact meeting_format=in_person "
                         "(executive_session_only, emergency; entirely_by_teleconference)",
                 check="the ordinary meeting's row applies and its executive-session and emergency rows do not; a "
                       "meeting held only in executive session takes its own shorter clock; a meeting held entirely "
                       "by teleconference adds the teleconference row's elements; an undetermined row is a fact not "
                       "yet said, never a notice not required",
                 refs=("docs/notices.md (When a row is required)", "docs/applicability.md"),
                 lessons=("a-condition-kept-as-prose-cannot-be-asked", "teleconference-reminder-paraphrased")),
            Step("Within days of a meeting, draft its minutes from the Zoom transcript, and read jason's checks before "
                 "anything else: the quorum counted from the attendance, a motion acted on without one, and lines "
                 "naming a subject the open minutes give only in general terms.",
                 command="jason board --minutes DATE; jason board --minutes DATE --recheck",
                 check="the quorum statement matches the count; members' names and executive matters are out; the "
                       "draft stays DRAFT until the Secretary reads it and the board approves it",
                 refs=("docs/board-agenda.md",), lessons=("model-asserts-quorum",), person=True),
            Step("Read each meeting's minutes history and each open rule change's stages: a copy of the minutes on "
                 "record within 30 days, the next minutes stating the approval in words, and a rule change's 28-day "
                 "notice delivered before its decision and its notice of adoption within 15 days after (Civil Code "
                 "4360).", command="jason record-stages --minutes; jason record-stages --change KEY",
                 check="the approval is written as passed ('approved the minutes of DATE, M/S/P'), not only listed; "
                       "a clock is met by a delivery, not a file; executive-session minutes show only their date",
                 refs=("docs/record-stages.md",),
                 lessons=("approval-item-is-not-approval", "notice-file-is-not-delivery",
                          "executive-minutes-counted-open")),
            Step("Bring the action items up to date: status, owner, meeting, notes.",
                 command="jason board --set ITEM --status 'on agenda' --meeting DATE",
                 refs=("docs/board-agenda.md",)),
            Step("Name reports in an item's notes rather than copying facts into them.",
                 command="jason board --set ITEM --notes \"commentary {REPORT:KEY} commentary\"",
                 refs=("jason report --list",)),
            Step("The day before, refresh the reports the items name, and catalogue PayHOA's packet runs.",
                 command="jason report --all --doc --yes; jason report treasurers-report period=previous-month --doc --yes",
                 check="no report is stale or failed; last month's Treasurer's Report has been run in PayHOA"),
            Step("Build the packet, and its private Doc on the letterhead.", command="jason board --packet --doc --yes",
                 check="executive session items are listed by title only"),
            Step("Draft the agenda from the last agenda Doc.", command="jason board --agenda DOC_ID --doc --yes",
                 check="the draft's format line names the meeting's format (the agenda plan's, or --format), not "
                       "\"Format assumed\"; only a meeting held entirely by teleconference carries 4926's lines, and "
                       "its individual-delivery reminder recites 4045(b) and 4041(a)(1) with no highlighted miss",
                 refs=("docs/board-agenda.md",), lessons=("notice-date-ignored-documents",
                                                          "teleconference-reminder-paraphrased")),
            Step("Share the packet with the directors from Drive.", person=True),
        ),
        refs=("docs/board-agenda.md", "docs/payhoa-reports.md"),
    ),
    Procedure(
        "mailroom-letter", "A letter through PayHOA's Mailroom",
        "Whenever the association mails owners on paper.",
        (Area.MAILROOM,),
        "Print and mail a letter through PayHOA (Lob), charged to the association, without a letter that cannot be "
        "recalled going out wrong.",
        (
            Step("Keep the PDF to four pages (PayHOA's address page is billed; a sixth billed page adds $2.25).",
                 command="jason mailroom --prices", refs=("payhoa.pricing", "AGENTS.md (Boundaries)")),
            Step("Preview the recipients and the cost.", command="jason mailroom --pdf FILE --units UNITS",
                 check="each recipient and the price per letter"),
            Step("Test every link and QR code in the letter as its reader would.", person=True,
                 lessons=("test-as-an-owner", "form-link-needs-unit")),
            Step("Mail it, only on a person's word.", command="jason mailroom --pdf FILE --units UNITS --send --yes",
                 check="the batch's letters read back as processing", lessons=("letters-cannot-be-recalled",)),
            Step("If something is wrong, cancel at once: the window is minutes.",
                 command="jason mailroom --cancel LETTER_ID --yes"),
            Step("A week on, read the letters' tracking: never mailed, returned, or forwarded.",
                 command="jason notices KEY --sync", refs=("procedure notice-delivery",)),
        ),
        refs=("AGENTS.md (Boundaries)",),
    ),
    Procedure(
        "notice-delivery", "A notice's delivery, and the follow-ups the law asks for",
        "After every notice to members: the day after it goes out, again after 24 hours, and a week on for letters.",
        (Area.EMAIL, Area.MAILROOM),
        "Know that each member was reached, and where a message bounced, was skipped, or a letter did not mail, "
        "deliver the notice again the way Civil Code 4040, 4041(e), and 4045 ask.",
        (
            Step("Before it goes out, read the notice's requirement: recipients, method, the clock with the governing "
                 "documents' stricter period, the content, and the evidence it will need. Name its batches with the "
                 "requirement's key and the date (board-meeting-2026-10-20) so the ledger and the proof find it.",
                 command="jason notices REQUIREMENT --catalog",
                 check="the last day to send; the documents' clauses that ask more; the content list",
                 refs=("docs/notices.md",)),
            Step("Read the notice's delivery from PayHOA: a jason batch by its id prefix; a notice sent from PayHOA's "
                 "screens by its subject.",
                 command="jason notices KEY --sync (or --sync --subject \"SUBJECT\" --since DATE)",
                 check="members reached; the follow-ups owed and each one's authority; a notice sent from PayHOA's "
                       "screens is synced under its requirement and date (board-meeting-YYYY-MM-DD), so its proof "
                       "and its stage find it",
                 lessons=("notice-key-names-requirement",)),
            Step("For a general notice (a meeting notice), say whether it was also posted where the annual policy "
                 "statement designates; only then is a failed message information rather than a resend.",
                 command="jason notices KEY --mark-general --posted \"WHERE, YYYY-MM-DD\" --by NAME",
                 check="the posting happened, on the notice's date; a posting with no day meets no clock",
                 refs=("Civil Code 4045",), person=True),
            Step("Send each required follow-up as its own confirmed send: a bounced or skipped email by first-class "
                 "mail; a letter that never mailed, again.",
                 command="jason owner-info --mail-batch --only UNIT --resend --yes --confirmed-by NAME, or jason mailroom",
                 check="the follow-up's batch starts with the notice's KEY (--resend), so the next --sync reads it",
                 refs=("procedure mailroom-letter",), lessons=("bounces-are-silent",), person=True),
            Step("Ask each member whose address failed for a working one, and record the answer in PayHOA.",
                 refs=("procedure owner-info-cycle", "docs/owner-information.md")),
            Step("Sync again until nothing is owed; the ledger is the record of each delivery.",
                 command="jason notices KEY", refs=("data/notices/deliveries.db",)),
            Step("Put together the proof of notice: the evidence the requirement calls for, the window, and who was "
                 "reached only after the last day (a finding for the board: usually a new date and a new notice).",
                 command="jason notices KEY --proof --event DATE [--general --posted DATE] [--have text_as_sent,...]",
                 check="every item on file; nobody late or unreached", refs=("docs/notices.md (Proof of notice)",),
                 person=True),
            Step("Keep the text as sent and the recipients plan with the notice, and read its record.",
                 command="data/notices/KEY/ (text, .refs.json, recipients.json); jason cite jason://notice/KEY",
                 check="its strength is delivered, or sent with what is owed listed; never a file alone",
                 lessons=("notice-evidence-first-attempt", "notice-text-not-kept",
                          "broadcast-kept-is-handed-not-sent")),
        ),
        refs=("docs/batches.md (Delivery and follow-ups)", "docs/notices.md", "Civil Code 4040, 4041(e), 4045, 4050"),
    ),
    Procedure(
        "election", "An election: of directors, a recall, or a member vote",
        "When the board sets an election's date, before its first notice; again before each notice goes out.",
        (Area.GOVERNING, Area.EMAIL, Area.MAILROOM),
        "Know which notices the law requires for this election and which it does not, send each on its clock with "
        "every required element, and record the seats it fills.",
        (
            Step("Say what kind of election it is, and list the notices the law requires for it: the rows that apply, "
                 "those that do not with the fact that decided each, and those left undetermined with the fact still "
                 "missing. A row left undetermined is never read as a notice not required.",
                 command="jason notices --catalog --fact election=directors (recall, assessment, amendment, "
                         "exclusive_use, other)",
                 check="the nomination and pre-ballot rows apply to an election of directors or a recall and to no "
                       "other kind; the acclamation, electronic-ballot, and reconvened-meeting rows wait on the "
                       "association's standing facts where the specification does not state them",
                 refs=("docs/notices.md (When a row is required)", "docs/applicability.md"),
                 lessons=("a-condition-kept-as-prose-cannot-be-asked",)),
            Step("Answer the standing facts those rows wait on, each with the record that settles it: whether an "
                 "election rule allows electronic secret ballots and lets members opt out, whether the governing "
                 "documents require a quorum for an election of directors and how large, and whether the board keeps "
                 "seating by acclamation available (its decision, written down once).",
                 command="jason applies --questions; jason applies --file-questions; jason intake --answer ID TEXT "
                         "--by NAME",
                 check="each answer names its section or minute; the catalog run again leaves no election row "
                       "undetermined", refs=("docs/intake.md",), person=True),
            Step("Read each notice's requirement with the election's facts: its recipients, method, clock with the "
                 "documents' stricter period, and the conditional elements it carries for this kind of election.",
                 command="jason notices REQUIREMENT --catalog --fact election=directors",
                 check="the last day to send each; the elements marked for this election only",
                 refs=("procedure notice-delivery",)),
            Step("Check each notice's text for its required elements before it goes out, with the election's facts.",
                 command="jason notice-check FILE --requirement KEY --event election=directors",
                 check="no required element missing; a conditional element is judged by the facts said, not skipped",
                 refs=("docs/notices.md",)),
            Step("Deliver each notice under its requirement's key and date, and read its delivery and the follow-ups "
                 "owed.", command="jason notices KEY --sync", refs=("procedure notice-delivery",),
                 lessons=("notice-key-names-requirement", "notice-file-is-not-delivery")),
            Step("After the inspector of elections reports, record the seats filled and their terms, with the report or "
                 "the minutes in hand; a second person confirms.",
                 command="jason onboard --questions --group elections; jason onboard --answer ID TEXT --by NAME; "
                         "jason onboard --confirm ID --by NAME; jason onboard --apply",
                 refs=("procedure onboard",), lessons=("board-roster-change-unrecorded",), person=True),
        ),
        refs=("docs/notices.md", "Civil Code 5100 to 5145"),
    ),
    Procedure(
        "rule-change", "A change to an operating rule (Civil Code 4340 to 4365)",
        "When the board proposes to adopt, amend, or repeal an operating rule, before the member notice; again "
        "after the decision.",
        (Area.GOVERNING,),
        "Know whether the change is one the members must be noticed of, give the notice with the text of the change "
        "first, decide only after the notice period, and notice the adoption on its clock.",
        (
            Step("Say the change's facts, and list the notices the law requires for it: whether the rule is on a "
                 "subject Civil Code 4355(a) lists (or the change is a board action 4355(b) lists), and whether it is "
                 "an emergency rule change under 4360(d). The rows that apply, those that do not with the deciding "
                 "fact, and those left undetermined with the fact still missing; an undetermined row is never read as "
                 "a notice not required.",
                 command="jason notices --catalog --fact rule_scope=listed_subject (not_reached) --fact "
                         "rule_change=noticed (emergency)",
                 check="for a listed subject the proposed-change and adoption rows apply, and the proposed-change row "
                       "falls away only for an emergency rule change; whether the subject is one 4355(a) lists is a "
                       "reading, labeled as the board's, and where two readings remain the board asks counsel",
                 refs=("docs/notices.md (When a row is required)", "docs/applicability.md",
                       "AGENTS.md (Where the law is silent, write it down)"),
                 lessons=("a-condition-kept-as-prose-cannot-be-asked",)),
            Step("Draft the course: the member notice of the proposed change, the agenda item for the decision "
                 "meeting, and the notice of adoption, each reciting the sections as they stand and the proposed text "
                 "as its own version.",
                 command="jason rule-change CHANGE --notice-date DATE; jason rule-change --list",
                 check="the notice carries the text of the proposed rule change first, then its purpose and effect "
                       "(4360(a)); the decision meeting is at least 28 days after the notice; a rule change is never "
                       "a vote by the members unless the documents say so",
                 refs=("docs/notices.md", "AGENTS.md (Recite the rule; label the reading)")),
            Step("Preview the member notice as a Gmail draft, and keep its text as sent; a person addresses and "
                 "sends it.", command="jason rule-change CHANGE --draft-email; then --yes --by NAME",
                 check="the draft has no recipients until a person adds them; the text, subject, and the sections "
                       "it recites are kept in data/notices/KEY/", lessons=("notice-text-not-kept",), person=True),
            Step("Check the notice's text for its required elements with the change's facts.",
                 command="jason notice-check FILE --requirement rule-change-proposed --event rule_scope=listed_subject",
                 check="the text, the purpose and effect, and the comment deadline are each present"),
            Step("Deliver each notice under its requirement's key and date, and read its delivery and the follow-ups "
                 "owed.", command="jason notices KEY --sync", refs=("procedure notice-delivery",),
                 lessons=("notice-key-names-requirement", "notice-file-is-not-delivery")),
            Step("Read the change's stages: the 28-day notice delivered before the decision, the decision in the "
                 "minutes, and the notice of adoption delivered within 15 days after.",
                 command="jason record-stages --change KEY",
                 check="a clock is met by a delivery, not a file; the minutes state the decision in words",
                 refs=("docs/record-stages.md",), lessons=("approval-item-is-not-approval",)),
            Step("After adoption, carry the rule into the rules book and the owner's manual, and run their "
                 "procedure.", refs=("procedure owners-manual", "procedure rule-history"), person=True),
        ),
        refs=("docs/notices.md", "Civil Code 4340 to 4365"),
    ),
    Procedure(
        "law-review", "The year's changes in the law against the written provisions",
        "Each January, once the year's new laws are operative; again when a law takes effect mid-year.",
        (Area.GOVERNING, Area.ENFORCEMENT, Area.RENTALS),
        "Find each governing document, rule, policy, and procedure a change in the law now displaces, wholly or in "
        "part, so it is followed only as far as the law allows and the board can amend it.",
        (
            Step("Refresh the law and the change history from lawlibrary.",
                 command="jason export-authorities; jason law-history --export",
                 check="the export's date; the year's chaptered bills are in the change list"),
            Step("Set aside each reading of the law whose words changed.",
                 command="jason readings --stale",
                 check="each stale reading is redone or confirmed by the board or counsel against the words now on "
                       "disk before it is used again",
                 refs=("docs/law-readings.md",), lessons=("reading-untied-from-the-words",)),
            Step("Keep the earlier versions of the sections that changed, each with the range it was in force.",
                 command="jason law-history --versions --since YEAR --shelf",
                 check="0 where the shelf differs from the newest publication; a miss is a citation to correct",
                 refs=("docs/law-readings.md (The words in force on a day)",),
                 lessons=("recital-gave-todays-words-for-an-earlier-day",)),
            Step("Refresh the documents' outlines.", command="jason outlines --fetch",
                 check="a document added or adopted since is a citable document in the specification, with its "
                       "written date"),
            Step("List the leads: each change since a document was written, with the section that cites it or "
                 "speaks to its subject.", command="jason conflicts --leads --since YEAR-01-01",
                 check="a document with no written date counts every change: pin the date when the evidence allows",
                 refs=("docs/law-history.md (Leads for the conflict register)",)),
            Step("Read each lead beside the statute's text; record each real conflict as a Conflict row (the part "
                 "that yields, how it is followed meanwhile, plain or for counsel).",
                 command="jason law-history --section NNNN", refs=("AGENTS.md (Follow what is written)",),
                 lessons=("law-outdates-provisions",)),
            Step("Check jason's own rules and pages for the same changes.",
                 command="jason law-history --sweep --since YEAR", check="data/reports/law-sweep.md"),
            Step("Survey the documents' references and the records that cite them: misses by reason, and citations "
                 "made stale by an amendment or a renumbering.", command="jason outlines; jason cite --survey; "
                                                                          "jason cite --stale",
                 check="a prior-numbering miss is read as its successor; a stale record is re-keyed or re-read; "
                       "jason cite --renumbered lists the records found again by permanent id; jason cite --migrate-ids "
                       "(then --apply) stores the ids; each 'more than one section answers' row is picked by a person",
                 refs=("docs/citations.md", "docs/record-addresses.md"),
                 lessons=("numbers-are-not-identity", "number-alone-is-ambiguous-across-readings", "short-forms-unread")),
            Step("Check each people-task rule that retires a duty against its source (an exemption, a repealed "
                 "filing).", command="jason schedule --people --all", check="each retire reason still true at its source",
                 lessons=("people-keep-clocks-by-hand",)),
            Step("After an amendment is recorded (and each January), find the copies of each changed section: stale "
                 "copies in adopted documents are findings for their next revision and conflict leads; jason's own "
                 "bases are patched to tokens on a person's word.",
                 command="jason section-refs --refresh --scan --guide; jason section-refs --patch",
                 check="no stale copy in a base jason renders; the guide rebuilt",
                 refs=("docs/embedded-references.md",), lessons=("copied-passages-go-stale",)),
            Step("Put each new conflict on the board's action register, and carry them into the next packet.",
                 command="jason board --set ITEM ...", refs=("{REPORT:conflicts}",), person=True),
        ),
        refs=("docs/law-history.md", "AGENTS.md (Follow what is written, as far as a higher authority allows)"),
    ),
    Procedure(
        "document-intake", "Taking a document in: classify, establish its standing, read it, ask, and check",
        "Whenever a governing document, amendment, rule, policy, or recorded instrument arrives, and after each "
        "library or Drive sync.",
        (Area.GOVERNING, Area.DOCUMENTS),
        "Know what each document is, whether it took effect, what its words say where a reader was unsure, and what it "
        "changes: so the current text, the conflicts, and the duties stay true, and every answer a person gives is kept.",
        (
            Step("Bring the document in: the library and the Drive catalog.", command="jason library; jason drive",
                 check="it has a kind; an unclassified file becomes a question"),
            Step("Establish its standing: a draft, adopted (minutes, resolution), or recorded (the county index, the "
                 "recorded copy with its stamp). Read the recorded copy, not a summary of it.",
                 command="jason-mcp recorder_search / recorder_detail; jason records-request",
                 check="an amendment's adopted and recorded dates pinned in the specification",
                 lessons=("amendment-standing-is-a-record",), person=True),
            Step("If it amends a document jason keeps living, add it as an instrument with the source its marks are "
                 "read from (the recorded scan; the draft Doc as a second reading), then build.",
                 command="jason living KEY --fetch --working",
                 check="applied and not-in-effect lists; before-words findings; the rule rows' checks",
                 refs=("docs/living-documents.md",), lessons=("plain-text-loses-the-marks", "amended-by-hand-drifts")),
            Step("Before reading a bulk or scanned PDF, preflight it: blank and near-blank pages, rotation, skew, "
                 "resolution, the text layer's quality, and what the file carries (attachments and photographs are "
                 "saved as their own documents, never opened or run). Keep the original; read the cleaned rendition "
                 "only where a measured defect was found.",
                 command="jason preflight FILE|FOLDER [--render --pdf] [--ocr] [--extract]",
                 check="the original is untouched; no page with a mark is called blank; a clean page is unchanged; "
                       "a text layer over the suspect limit is read again, not trusted",
                 refs=("docs/pdf-preflight.md",),
                 lessons=("cleaning-every-page-adds-errors", "blank-page-test-drops-the-page-number",
                          "english-prior-misjudges-a-text-layer")),
            Step("Segment a file that holds more than one document, or a document with parts (rules inside a manual, an "
                 "exhibit or a report inside a packet): the stack of open documents, each with its parent and pages. "
                 "Segment before blank removal. A boundary the rules and the model agree on is likely; one reader's is "
                 "a suggestion.",
                 command="jason segments FILE [--model] [--write]",
                 check="the file is never split; each segment has a parent and absolute pages; a duplex scan's blanks "
                       "are not separators",
                 refs=("docs/document-segmentation.md",),
                 lessons=("scan-holding-several-documents-read-as-one", "vision-model-leans-to-new-document",
                          "duplex-blank-backs-are-not-separators")),
            Step("Park every uncertainty as a question, and answer them: the kind, OCR readings (the likely ones in a "
                 "batch after a look), drift, an amendment's silent changes, orphaned notes. The text rules read the "
                 "OCR beside the working copy (with a vocabulary search, case from the sentence, and the document's "
                 "terms: --ocr-options); --model adds the local model as a second reader of the doubtful words and "
                 "--vision the page's crop of every word the rules cannot settle (--vision-route suspects). Learn the "
                 "letters this association's scans misread first, once (--learn-channel).",
                 command="jason intake --learn-channel; jason intake --scan [--model] [--vision]; jason intake --likely; "
                         "jason intake --answer ID TEXT --by NAME",
                 check="no answer without a name; a likely reading has two readers that agree and changes no number "
                       "or operative word without the page; a reading the crop alone makes is held, not likely; a "
                       "question for counsel goes to the board's canvas",
                 refs=("docs/ocr-correction.md",),
                 lessons=("model-corrects-the-drafting", "copy-shares-ocr-slips", "real-word-misread-needs-the-page",
                          "one-edit-candidates-miss-two-glyph-misreads", "misread-glyph-sets-the-case"), person=True),
            Step("For a scan with no working copy (most library files), write the OCR suggestions beside its text and "
                 "look first at the worst-read files: a high share of words no English list knows is a file to read "
                 "again (the Tesseract tool, or the vision model).",
                 command="jason intake --library-ocr [--library-kind KIND]",
                 check="the raw text is unchanged; suggestions sit in <id>.ocr-suggestions.json",
                 refs=("docs/ocr-correction.md",), lessons=("ocr-engine-runs-words-together",)),
            Step("Apply the answers, and build again.", command="jason intake --apply; jason living KEY",
                 check="transcriptions applied; the question count falls"),
            Step("When a better reading of a scanned base is available, re-read it as a dry run, and switch only on a "
                 "person's word.", command="jason living KEY --reread cli; jason living KEY --use-reread cli --yes "
                                           "--by NAME",
                 check="the re-read's section count under the builds' numbering is close to the reading in use; no "
                       "transcription unplaced; the WER falls; the re-keyed questions answered after the switch",
                 refs=("docs/living-documents.md (Re-reading a base)",),
                 lessons=("reading-moves-transcriptions", "ocr-labels-garbled"), person=True),
            Step("Check what the document changes against the law and the other documents: conflict leads, duties, "
                 "notice requirements.", command="jason conflicts --leads --document KEY",
                 refs=("procedure law-review",), lessons=("law-outdates-provisions",)),
            Step("Read the citations the document makes, scoped to the documents they mean.",
                 command="jason cite --scan FILE; jason cite EXPR --in KEY --on DAY",
                 check="every ambiguous_document is a question for a person, never a pick; a document's own text is "
                       "read with --in its key and --on its day",
                 refs=("docs/rule-citations.md",), lessons=("citation-needs-its-document",), person=True),
            Step("Find the rule-making power it grants, and the rules on file for each subject.",
                 command="jason rules --find --model; jason rules --subjects",
                 check="each conflict-tier row is read against its words; a subject with rules on file and no named "
                       "grant, or a grant with no rule, is a finding for the board, never an accusation",
                 refs=("docs/rule-authority.md",),
                 lessons=("model-answers-for-its-neighbor", "grant-without-a-rule-noun"), person=True),
            Step("Record what the intake taught as lessons, and update this procedure.",
                 command="jason lessons --area governing", refs=("AGENTS.md (Lessons and procedures)",)),
        ),
        refs=("docs/intake.md", "docs/living-documents.md"),
    ),
    Procedure(
        "respond", "Answering members' requests on their clocks",
        "Each week, and the day before each board meeting.",
        (Area.GOVERNING, Area.EMAIL),
        "Know every open request's kind, its due day, and its owner; answer within the clock; put on the agenda what "
        "the board decides; never approve, deny, or assign on jason's own.",
        (
            Step("Refresh the requests, and read them with their clocks.", command="jason sync-catalog; jason respond",
                 check="anything overdue or due soon; a request classified 'other' is read and its kind decided"),
            Step("Read where each answer is written: the documents' passages, the library's files, and the precedents.",
                 command="jason respond --sources", check="each line is a lead to read, not a ruling"),
            Step("Acknowledge within the policy's days, and send the answer or the plan; a board decision goes on the "
                 "next agenda. An answer that turns on a rule recites the rule's words with its citation before any "
                 "reading of it (AGENTS.md, Recite the rule; label the reading). A PayHOA request gets a comment; an "
                 "email request a Gmail draft in its thread, which a person reads, edits, and sends.",
                 command="jason respond --draft ID; jason request-comment ID ... (or jason respond --draft email:ID "
                         "--gmail, then --yes)", person=True),
            Step("Join emailed requests PayHOA lacks.", command="jason request-links",
                 check="a draft is entered only on a person's word"),
            Step("Close each request when it is done.", person=True),
            Step("Monthly, read how many answers were on time, by kind, for the board.", command="jason respond --all"),
            Step("Label new requests' kinds in the gold set, and measure before changing a kind rule.",
                 command="jason respond --measure", check="no kind's precision or recall falls",
                 lessons=("email-topic-values",)),
        ),
        refs=("docs/responses.md", "procedure duty-schedule"),
    ),
    Procedure(
        "duty-schedule", "Every duty owned, every clock set, and each occurrence done",
        "Each month before the board meeting; and whenever a document, an amendment, or a law adds duties.",
        (Area.GOVERNING,),
        "See that every duty the law and the documents impose has an owner and a schedule, that what fell due was done "
        "with evidence, and that the board has adopted the assignments.",
        (
            Step("Read what falls due, by role.", command="jason schedule --days 45",
                 check="overdue items: done and not recorded, or not done"),
            Step("Read people's own Google Tasks and calendar beside the schedule.",
                 command="jason schedule --read-google --people",
                 check="each untracked recurring item becomes a proposed assignment or a rule row; stale tasks go to "
                       "their owner; a task proposed to close is closed by a person in Google; jason marks nothing",
                 refs=("docs/schedule.md (People's own tasks and events)",),
                 lessons=("people-keep-clocks-by-hand", "reminder-is-not-a-deadline")),
            Step("Find the evidence on disk for what fell due: the minutes, the reports they name, the notices, the "
                 "mailings, and the payments.", command="jason schedule-evidence --since DATE --all",
                 check="a proposal is read in its source before it is recorded; 'contrary' (a late notice, a late "
                       "payment) goes to the board; a miss is not proof the duty was not done",
                 refs=("docs/schedule.md (Evidence)",), lessons=("minutes-say-the-review",)),
            Step("Record each occurrence done, with who did it and the evidence.",
                 command="jason schedule-evidence --record KEY DUE --by NAME (or jason schedule --done KEY DUE --by NAME "
                         "--evidence TEXT)", person=True),
            Step("For a life safety inspection overdue or with no record, ask its servicer for the reports it holds and "
                 "a proposal; read the vendor's waiting mail and the agreement on file first.",
                 command="jason inspections; jason draft --proposal-request SYSTEM [--to ADDRESS --yes]",
                 check="a report the vendor sends may close an item with no proposal; the draft is saved, never sent; "
                       "accepting a proposal is the board's decision",
                 refs=("docs/fire-protection.md (Asking the servicer)",), person=True),
            Step("Put the schedule where people see it: each dated occurrence on the board calendar, each open one on "
                 "its role's Google Tasks list; a task checked off there is recorded done. Read the dry run, then write.",
                 command="jason schedule --tasks --calendar; jason schedule --tasks --calendar --yes",
                 check="the check-offs to record are real; a 'Google Tasks' completion is weaker evidence than the "
                       "minutes, so record the minutes' item too; no person's name in a title",
                 refs=("docs/schedule.md (On Google Calendar and Google Tasks)", "docs/calendar.md"), person=True),
            Step("After a document, amendment, or law changes, read its duties again and check coverage.",
                 command="jason duties --documents KEY; jason schedule --coverage",
                 check="no duty unowned; no duty on a clock with only a standing owner", lessons=("duties-need-owners",)),
            Step("Carry the schedule into the packet; the board adopts, changes, or declines the proposed assignments.",
                 command="{REPORT:schedule}", refs=("docs/schedule.md",), person=True),
        ),
        refs=("docs/schedule.md", "procedure document-duties"),
    ),
    Procedure(
        "document-duties", "The duties a governing document states",
        "When a governing document is outlined, amended, or replaced, and before relying on what it requires.",
        (Area.GOVERNING,),
        "List what each document requires, forbids, and allows, who bears it, and when; review the readings; and see "
        "that every timed duty and duty to give notice is tracked by a person's row.",
        (
            Step("Read the documents with the phrase grammar (reviews are kept).", command="jason duties --documents --read"),
            Step("Fill the bearers the words leave out with the local model, the stack permitting.",
                 command="jason duties --documents --fill-bearers",
                 check="preflight passes; afterwards the model is unloaded (jason local-ai --unload NAME --yes) before pytest",
                 refs=("docs/document-tools.md (model trials)",), lessons=("model-reads-norms-loosely",)),
            Step("Review the readings that matter first: timed duties nothing tracks, duties to give notice, and owners' "
                 "prohibitions; confirm, correct, or reject each against the sentence in the document.",
                 command="jason duties --documents --timed --untracked; jason duties --documents KEY --notices",
                 check="a list item read with its lead-in; a \"may\" is a power, not a duty",
                 refs=("docs/document-duties.md (How a person reviews)",), lessons=("duty-gold-overstates",), person=True),
            Step("Say what tracks each timed duty, or propose the recurring-deadline row it needs; hand duties to give "
                 "notice to the notice catalog.", command="jason duties --documents KEY --review ID --tracked-by WHAT",
                 refs=("docs/notices.md",), person=True),
            Step("After a change to the grammar or the model, score it again and record the trial.",
                 command="python scripts/eval_duties.py --model NAME", lessons=("duty-gold-overstates",)),
        ),
        refs=("docs/document-duties.md",),
    ),
    Procedure(
        "owners-manual", "Keeping the owner's manual and the rules it carries",
        "Whenever the manual's Doc changes, a rule is changed, or a document it copies is amended.",
        (Area.DOCUMENTS, Area.GOVERNING),
        "Keep the official rules word for word, the manual generated from its sources, and every citation resolving.",
        (
            Step("Refresh the outlines (read-only) and the copies scan.", command="jason outlines --fetch; jason section-refs --scan"),
            Step("Classify each section by rule rows and evidence, and answer the questions.",
                 command="jason manual --classify --asks; jason intake",
                 lessons=("guide-states-duties", "askkind-classify-is-the-librarys", "grammar-misses-future-and-passive-duties")),
            Step("Check the concordance.", command="jason manual --concordance", check="zero unresolved citations",
                 lessons=("outline-numbers-are-the-readers", "span-is-not-subject")),
            Step("Render the rules and the manual, and read the labeled differences and the diff.",
                 command="jason manual --render (the last adopted words); jason manual --render --current (the working "
                         "words)",
                 check="zero unlabeled differences; render.json's adoption block: the passages changed with no "
                       "adoption, how many have no adopted version on record, and no pending suggestion left",
                 lessons=("working-doc-is-not-adopted-text", "revision-text-reads-suggestions-accepted")),
            Step("Refetch the Doc's links (chips) before anything is published.", command="jason outlines --fetch"),
            Step("Put the extraction on the board's agenda; a rule change takes the 4360 notice and adoption.",
                 command="jason board --set ITEM ...; jason rule-change", person=True),
            Step("After adoption, add the rules document as a citable document and the source of the rules book, move the "
                 "aliases to it, and run the steps again.", person=True),
        ),
        refs=("docs/owners-manual.md", "docs/record-addresses.md"),
    ),
    Procedure(
        "rule-history", "A rule's history: its versions, its changes, and their adoption",
        "Before relying on a rule's current text, before a rule change, and each January with the law review.",
        (Area.DOCUMENTS, Area.GOVERNING),
        "Know which text is in force, what changed and when, and whether each change was adopted.",
        (
            Step("Fetch the document's versions, read-only: copies sent and uploaded, and the Doc's Drive revisions.",
                 command="jason revisions KEY --fetch",
                 check="'N revisions kept by Drive'; no export errors left (rerun if any show 429)",
                 lessons=("drive-revision-exports-rate-limited",)),
            Step("List the versions.", command="jason revisions KEY --versions",
                 check="every copy sent or uploaded is a copy of a revision or listed as side; files not read get --ocr",
                 lessons=("effective-date-is-a-claim", "library-resolves-by-name-only")),
            Step("Read the report: pending suggestions first, then flagged changes. For each, find the notice and the "
                 "minutes before calling it unadopted; 'in the window, but not naming this section' is only a lead.",
                 command="data/reports/revisions-KEY.md", lessons=("docx-carries-pending-suggestions",)),
            Step("Before quoting a copy someone was sent as 'the rules', compare it with its revision.",
                 command="jason revisions KEY --diff A B"),
            Step("Put findings on the board's action register. Never edit the Doc or accept its suggestions.",
                 command="jason board --set ITEM ...", person=True),
            Step("For the owner's manual, rerun the extraction so the official rules read the detected history.",
                 command="jason revisions owners-manual; jason manual --render"),
        ),
        refs=("docs/revision-detection.md", "procedure owners-manual"),
    ),
    Procedure(
        "onboard", "Taking on an association, or a change of manager",
        "When jason takes on a new association, and before a management company's contract ends.",
        (Area.ONBOARDING,),
        "Gather every record and fact a profile needs, from each source, and keep secrets out of documents.",
        (
            Step("Start the profile: the package from jason's templates and its empty private facts; set JASON_PROFILE; "
                 "with --county and --lookup, the county recorder's finds become questions.",
                 command="jason onboard --new KEY --name NAME --county COUNTY --lookup",
                 check="the package is new (nothing overwritten); jason onboard shows every gate closed; a lead is a "
                       "question, never a row",
                 refs=("docs/onboarding.md (Starting a new association)",),
                 lessons=("second-profile-shared-stores", "recorder-empty-or-unreachable")),
            Step("Confirm the new profile reads only its own private facts; for the default profile, copy its old "
                 "topic files into its own folder once.", command="jason spec; jason spec --migrate (then --yes)",
                 check="the paths are data/spec/<key>.json and data/spec/<key>/ only; a backup before any copy",
                 refs=("docs/profiles.md (Each profile's data)",),
                 lessons=("second-profile-shared-stores", "profile-module-reads-active-facts")),
            Step("Read the checklist.", command="jason onboard --items"),
            Step("Run the session: the stage gates, then the ranked questions. Park the fact and mapping questions, "
                 "answer in the order given, have a second person confirm the high-stakes ones, then apply.",
                 command="jason onboard; jason onboard --scan; jason onboard --answer ID TEXT --by NAME; "
                         "jason onboard --confirm ID --by NAME; jason onboard --apply",
                 check="a secret is never typed (answer with the Keeper record's name); each private-facts diff is "
                       "read; each profile proposal in data/onboarding/proposals/ is reviewed before it is applied",
                 refs=("docs/onboarding.md (The session)",),
                 lessons=("intake-queue-order", "answer-may-hold-a-secret", "profile-proposal-untracked"),
                 person=True),
            Step("Or answer by conversation: register the onboarding tool set and use the onboard prompt; a second "
                 "person runs onboard_review for the high-stakes answers.",
                 command="jason-mcp --profile onboarding",
                 check="every answer's by is a person's name; no secret recorded; the person who confirms is not the "
                       "one who answered",
                 refs=("docs/onboarding.md (Onboarding by conversation)", "docs/mcp.md (Prompts)"),
                 lessons=("listed-question-not-answerable-over-mcp",), person=True),
            Step("After the minutes record a change of office, or an election or appointment fills a seat, answer the "
                 "standing question in its form (board-roster: OFFICE; PERSON or vacant; YYYY-MM-DD; MINUTES. "
                 "election-status: SEAT; PERSON; START; END; RECORD; PROVISION); a second person confirms; then apply.",
                 command="jason onboard --questions --group board (or elections); jason onboard --answer ID TEXT --by NAME; "
                         "jason onboard --confirm ID --by NAME; jason onboard --apply",
                 check="the minutes or the inspector's report are in hand before answering; the diff appends to the "
                       "officers or terms topic and changes no row already there; the People screen shows the result",
                 refs=("docs/onboarding.md (The roster, as it changes)", "docs/console/screens/people.md"),
                 lessons=("board-roster-change-unrecorded",), person=True),
            Step("Send each source its request list, with three dates: at once, monthly after late fees, and at "
                 "transition; paper records come with a contents list for each box.",
                 command="jason onboard --request [SOURCE]", lessons=("outgoing-manager-only-items",), person=True),
            Step("Put people, account numbers, and figures in data/spec/<name>.json or the profile's notes; put codes and "
                 "passwords in Keeper, never in a Doc.", person=True),
            Step("Connect the community's integrations: each credential under its vault path (move the .env records "
                 "with the plan first), then each read checked by a person at a console.",
                 command="jason vault status; jason vault migrate (then --yes); jason integrations list; "
                         "jason integrations check KEY --live --by NAME",
                 check="every credential shows set, never its value; an integration counts as connected only after its "
                       "read succeeds; nothing is checked live by an agent",
                 refs=("docs/integrations-design.md", "docs/setup.md (The vault)"),
                 lessons=("credential-readers-env-only", "nul-is-a-tty"), person=True),
            Step("Adopt the schedules the administrator or the board chose, then run jason as a service.",
                 command="jason cadence; jason cadence --restore SOURCE --by NAME (or --every/--cron); "
                         "jason serve --install-task (then --yes); jason daemon status",
                 check="no source runs until adopted; none faster than its floor; no write is scheduled; the heartbeat "
                       "is fresh and lists the next runs",
                 refs=("docs/scheduler-daemon-design.md", "docs/jobs.md (Scheduling)"),
                 lessons=("scheduled-defaults-need-adoption", "worker-guard-per-machine",
                          "keeper-login-does-not-clear-sign-in-pause"), person=True),
            Step("Write the profile's Community subclass with the facts the board supplies; pin the library folders and "
                 "Drive roots to the 5200 records; map each governing document into its book.",
                 refs=("docs/profiles.md", "docs/record-addresses.md")),
            Step("Fetch what jason can read itself.",
                 command="jason sync-catalog; jason library; jason outlines --fetch"),
            Step("Run the checklist until only the items a person supplies are missing, and give each an owner.",
                 command="jason onboard --checklist --write; jason schedule",
                 lessons=("takeover-list-omits-statutory-items",)),
            Step("For a change of manager, read the outgoing agreement first: its term, its non-renewal and "
                 "termination clauses, and what it owes at transition. Count each notice window back from the term's "
                 "end, both edges, and send by the delivery the clause names.",
                 check="the window's first and last days are written down before the notice is sent; proof of delivery "
                       "is kept with the notice",
                 refs=("docs/contracts.md (Notice)",), lessons=("notice-window-has-two-edges",), person=True),
            Step("For a change of manager, before the termination date: request the records (Civil Code 5205), confirm "
                 "the board's portal access through the handover, and tell each vendor.", person=True),
        ),
        refs=("docs/onboarding.md",),
    ),
    Procedure(
        "ingest", "Taking in a folder of documents",
        "When a person hands over records: a folder, a zip, or a Drive folder (onboarding, a change of manager, a box "
        "of scans).",
        (Area.ONBOARDING, Area.DOCUMENTS),
        "Know every file, take in what is new, and file each where it belongs, with nothing guessed.",
        (
            Step("Read the dry run: duplicates, files already held, versions, copies, questions, and the checklist items "
                 "and gates that would move.", command="jason ingest SOURCE",
                 check="a new version of a living or citable document is read beside the current text, never applied; "
                       "a kind with no files in the library is read against the mail and the Drive before it is called missing",
                 lessons=("packet-read-as-version", "kinds-in-other-stores-were-gaps")),
            Step("Read the report's contract terms: each contract's deliverables (logs, reports, records at the end) and "
                 "findings (notice windows, arbitration, limits on claims, transfers). For a closer reading, have a model "
                 "review them; Bedrock sends the words to AWS, so a person chooses it.",
                 command="jason ingest SOURCE --terms-model ollama; jason contract-terms --list",
                 check="a finding is a lead read beside the contract's words and the statute; a deliverable worth "
                       "tracking becomes a board item or a register row, decided by a person",
                 refs=("docs/contracts.md (Contract terms in the ingestion pipeline)",),
                 lessons=("notice-window-has-two-edges",), person=True),
            Step("If many files have no kind, add the local model.", command="jason ingest SOURCE --model",
                 check="preflight passes; the model is unloaded afterwards (jason local-ai)"),
            Step("Park the questions and answer them in the ranked queue.",
                 command="jason ingest SOURCE --park; jason onboard; jason intake --apply",
                 lessons=("ingest-catch-all-folder",), person=True),
            Step("Run the dry run again, then take the ready files in.", command="jason ingest SOURCE --apply",
                 check="the filed count; jason ingest --gate; a later jason library run keeps the ingested rows",
                 lessons=("library-run-drops-ingested-rows",)),
            Step("For a version of a known document, read its history; ingest changes no document.",
                 command="jason revisions KEY", refs=("procedure rule-history",)),
        ),
        refs=("docs/onboarding.md (Ingest)",),
    ),
    Procedure(
        "owner-document", "An owner-facing document: email, guide, or notice",
        "Whenever the association writes to owners.",
        (Area.DOCUMENTS, Area.EMAIL),
        "Write it once and make the email, the Doc on the letterhead, and the PDF from the same file.",
        (
            Step("Write it in Markdown under data/drafts (pictures as ![alt](file){width=560}).",
                 refs=("docs/drafts-and-forms.md (one Markdown source)",), lessons=("one-source-per-document",)),
            Step("Quote a governing-document section as {QUOTE:key#n} (or cite it as {CITE:key#n}), never a pasted copy, "
                 "and check the references before sending.", command="jason section-refs --check FILE",
                 check="every reference fills; a quote noted 'check before sending' is read against the recorded copy; "
                       "any reading of the provision follows the quote and is labeled as a reading, and whose",
                 refs=("docs/embedded-references.md",), lessons=("copied-passages-go-stale", "quotes-carry-ocr-slips")),
            Step("Where it states what a provision requires, read the provision as cited, with jason's readings beside "
                 "its words.", command="jason cite EXPRESSION --cited-by --md",
                 check="the words in force are quoted; a summary is labeled as a reading",
                 refs=("docs/citations.md",), lessons=("reading-in-place-of-words",)),
            Step("Keep its Doc on the letterhead for review.", command="jason broadcast FILE.md --to-doc --yes"),
            Step("For a page to post or attach, export the PDF.",
                 command="jason letter --markdown FILE.md --pdf OUT.pdf --yes", refs=("docs/letters.md",)),
            Step("Preview it as one recipient receives it before sending.", refs=("docs/batches.md",)),
        ),
    ),
    Procedure(
        "careful-reading", "Reading a set of documents carefully, and answering from them",
        "When a question turns on what a set of documents says: a legal case's file, a vendor's file, a meeting's "
        "packet, a system's inspection records.",
        (Area.DOCUMENTS, Area.GOVERNING),
        "Keep three things apart: what the documents say, what the provisions mean, and whether the facts meet them. "
        "Recite the words, label each reading, and check every quotation before the answer is given.",
        (
            Step("Before a build or a copy of data: check where scratch and the caches will go.",
                 command="jason storage --check",
                 check="temp (JASON_TEMP_DIR) and ASSPY_HOME are on the data drive with room; work on a copy "
                       "(JASON_DATA_DIR) goes under the scratch folder and a confidential copy is removed when the "
                       "check ends",
                 lessons=("temp-and-caches-followed-the-system-drive",),
                 refs=("docs/scratch.md",)),
            Step("See what the index holds and what it holds back or cannot read.",
                 command="jason index --plan; jason cases --extract-text --case KEY; jason index --build",
                 check="the collection's files are in the index; a file listed as unreadable or partly read is opened "
                       "by a person; a held-back record is never extracted",
                 lessons=("case-file-searchable-only-by-transcripts", "index-flag-per-file-not-per-catalog")),
            Step("Search the slice that matters, not everything at once.",
                 command="jason index --search QUESTION --catalog NAME [--kind K] [--standing S]",
                 check="each hit's standing: the law, the record, evidence, a reference, or jason's own page (a "
                       "summary, never the rule)",
                 refs=("docs/mcp.md",)),
            Step("Lay out what the documents say happened, and where they disagree.",
                 command="jason chronology --catalog NAME; jason fact-conflicts --catalog NAME",
                 check="an event states what a document says, never that it happened; where two documents differ both "
                       "are kept and jason picks neither",
                 refs=("docs/collections.md",), lessons=("form-line-is-not-one-fact", "spoken-dates-carry-no-year")),
            Step("See what should be on file and is not.",
                 command="jason inspections; jason applies",
                 check="'not on file' never means 'not done'; an undetermined answer is a question for a person",
                 refs=("docs/fire-protection.md", "docs/applicability.md")),
            Step("Recite each provision's words before any reading of them.",
                 command="jason readings --recite CITATION; jason cite KEY",
                 check="a reading is labeled with whose it is; a stale one is not used; where two readings remain the "
                       "board asks counsel",
                 refs=("docs/law-readings.md", "docs/interpretation.md"), lessons=("reading-untied-from-the-words",)),
            Step("Review under the task's pack, with the collection as its own tier.",
                 command="jason review TASK --collection KEY --ask QUESTION [--run]",
                 check="the collection's sources are labeled evidence; a confidential collection is refused for a "
                       "members' task; the review is kept, not overwritten",
                 refs=("docs/manager-review.md", "docs/ingestion-and-review.md")),
            Step("Judge the date-dependent findings as of the date that matters.",
                 command="jason models --as-of DATE",
                 check="only the lens's findings move with the date; a reading's fields do not",
                 lessons=("reading-mixes-ingestion-and-review",)),
            Step("Check the answer's quotations against the stored words.",
                 command="jason verify-quotes FILE",
                 check="every quotation is found, in the provision the answer names; none is found only in a page or "
                       "a reference",
                 lessons=("answer-quotes-unchecked",)),
            Step("Give the answer as a proposal: the facts with their sources, the provisions recited, the reading "
                 "labeled, and the application. The board or counsel decides.", person=True),
        ),
        refs=("docs/ingestion-and-review.md",),
    ),
    Procedure(
        "check-in", "Checking work into the public repositories",
        "Before any commit to jason or payhoa.",
        (Area.REPOSITORY,),
        "Keep the association's records and people's details out of public history.",
        (
            Step("Keep the community's facts in the private specification (mystique/), never in jason."),
            Step("Before writing a new file, list its exact path and read git status for it: a name that sounds free may "
                 "be taken, and a tracked file the writer replaces is restored from git only if it was tracked.",
                 command="ls PATH; git status --short PATH",
                 check="the path does not exist, or it is a file you mean to change (read it first)",
                 lessons=("new-module-name-already-taken",)),
            Step("Use made-up values in fixtures; the operator's own ids go in .env.",
                 refs=(".env.example",), lessons=("no-real-data-in-fixtures",)),
            Step("Scan what will be committed for names, personal emails, phone numbers, and ids.",
                 check="no owner or deed party, no personal mailbox, no signed link or token"),
            Step("Commit, and push only when the person says so.", person=True),
        ),
    ),
)


def procedures(community: object | None = None) -> tuple[Procedure, ...]:
    own = getattr(community, "procedures", lambda: ())() if community is not None else ()
    return PROCEDURES + tuple(own)


def find(key: str, community: object | None = None) -> Procedure | None:
    return next((p for p in procedures(community) if p.key == key), None)


def lines(proc: Procedure, community: object | None = None) -> list[str]:
    """A procedure as Markdown: its purpose, its steps with their commands, checks, and references, then the lessons
    still open in its areas."""
    from jason.community.lessons import Status, lessons

    out = [f"**{proc.title}.** {proc.purpose} _When:_ {proc.when}", ""]
    for n, s in enumerate(proc.steps, 1):
        text = f"{n}. {s.do}" + (" _(a person's step)_" if s.person else "")
        extra = []
        if s.command:
            extra.append(f"`{s.command}`")
        if s.check:
            extra.append(f"check: {s.check}")
        if s.refs:
            extra.append("see: " + "; ".join(s.refs))
        if s.lessons:
            extra.append("lessons: " + ", ".join(s.lessons))
        out.append(text + (" " + ". ".join(x[0].upper() + x[1:] if not x.startswith("`") else x for x in extra) + "."
                           if extra else ""))
    if proc.refs:
        out += ["", "Reading: " + "; ".join(proc.refs) + "."]
    open_ = [l for l in lessons(community) if l.status is not Status.FIXED and any(l.applies_to(a) for a in proc.areas)]
    if open_:
        out += ["", "Open lessons in its areas:"] + [f"- **{l.key}** ({l.status.value}): {l.change}" for l in open_]
    from jason.community.authority_order import conflict_lines, conflicts

    held = [c for c in conflicts(community, open_only=True) if set(c.areas) & set(proc.areas)]
    if held:
        out += ["", "Where a written provision yields to a higher authority (follow it only that far):"]
        out += conflict_lines(held)
    return out


__all__ = ["PROCEDURES", "Procedure", "Step", "find", "lines", "procedures"]
