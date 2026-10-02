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
            Step("Triage the answers as they come in: what to record, enter, confirm, or hold for the board.",
                 command="jason owner-info --responses --canvas",
                 check="each finding's outcome; the board's questions in its canvas (mystique/notes/canvas)",
                 lessons=("answers-need-a-policy",)),
            Step("Record the answers as they come in: dry run, then write.",
                 command="jason owner-info --apply --payhoa; then --yes",
                 check="each write's reason; a request left open says why", lessons=("returns-by-the-same-rules",
                 "same-as-unit-needs-no-person")),
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
                 refs=("docs/board-agenda.md",)),
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
                 check="members reached; the follow-ups owed and each one's authority"),
            Step("For a general notice (a meeting notice), say whether it was also posted where the annual policy "
                 "statement designates; only then is a failed message information rather than a resend.",
                 command="jason notices KEY --general", check="the posting happened, on the notice's date",
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
        ),
        refs=("docs/batches.md (Delivery and follow-ups)", "docs/notices.md", "Civil Code 4040, 4041(e), 4045, 4050"),
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
            Step("Park every uncertainty as a question, and answer them: the kind, OCR readings (the likely ones in a "
                 "batch after a look), drift, an amendment's silent changes, orphaned notes. The text rules read the "
                 "OCR beside the working copy; --model adds the local model as a second reader of the doubtful words "
                 "and --vision the page's crop of a number or operative word in doubt.",
                 command="jason intake --scan [--model] [--vision]; jason intake --likely; "
                         "jason intake --answer ID TEXT --by NAME",
                 check="no answer without a name; a likely reading has two readers that agree and changes no number "
                       "or operative word without the page; a question for counsel goes to the board's canvas",
                 refs=("docs/ocr-correction.md",),
                 lessons=("model-corrects-the-drafting", "copy-shares-ocr-slips"), person=True),
            Step("For a scan with no working copy (most library files), write the OCR suggestions beside its text and "
                 "look first at the worst-read files: a high share of words no English list knows is a file to read "
                 "again (the Tesseract tool, or the vision model).",
                 command="jason intake --library-ocr [--library-kind KIND]",
                 check="the raw text is unchanged; suggestions sit in <id>.ocr-suggestions.json",
                 refs=("docs/ocr-correction.md",), lessons=("ocr-engine-runs-words-together",)),
            Step("Apply the answers, and build again.", command="jason intake --apply; jason living KEY",
                 check="transcriptions applied; the question count falls"),
            Step("Check what the document changes against the law and the other documents: conflict leads, duties, "
                 "notice requirements.", command="jason conflicts --leads --document KEY",
                 refs=("procedure law-review",), lessons=("law-outdates-provisions",)),
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
            Step("Acknowledge within the policy's days, and send the answer or the plan; a board decision goes on the "
                 "next agenda.", command="jason request-comment ID ...", person=True),
            Step("Join emailed requests PayHOA lacks.", command="jason request-links",
                 check="a draft is entered only on a person's word"),
            Step("Close each request when it is done.", person=True),
            Step("Monthly, read how many answers were on time, by kind, for the board.", command="jason respond --all"),
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
            Step("Record each occurrence done, with who did it and the evidence.",
                 command="jason schedule --done KEY DUE --by NAME --evidence TEXT", person=True),
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
        "owner-document", "An owner-facing document: email, guide, or notice",
        "Whenever the association writes to owners.",
        (Area.DOCUMENTS, Area.EMAIL),
        "Write it once and make the email, the Doc on the letterhead, and the PDF from the same file.",
        (
            Step("Write it in Markdown under data/drafts (pictures as ![alt](file){width=560}).",
                 refs=("docs/drafts-and-forms.md (one Markdown source)",), lessons=("one-source-per-document",)),
            Step("Keep its Doc on the letterhead for review.", command="jason broadcast FILE.md --to-doc --yes"),
            Step("For a page to post or attach, export the PDF.",
                 command="jason letter --markdown FILE.md --pdf OUT.pdf --yes", refs=("docs/letters.md",)),
            Step("Preview it as one recipient receives it before sending.", refs=("docs/batches.md",)),
        ),
    ),
    Procedure(
        "check-in", "Checking work into the public repositories",
        "Before any commit to jason or payhoa.",
        (Area.REPOSITORY,),
        "Keep the association's records and people's details out of public history.",
        (
            Step("Keep the community's facts in the private specification (mystique/), never in jason."),
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
