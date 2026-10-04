"""Lessons: what went wrong, why, what changed, and what still has to, kept as records a command can read.

A lesson is not a paragraph someone has to remember. Each one names the area it applies to (``Area``), so the command
that works in that area shows it before it acts (a dry run of a Mailroom send lists the Mailroom's lessons), the board
packet can carry them (``{REPORT:lessons area=owner-info}``), and ``jason lessons`` lists what is still open. A fixed
lesson names its guard: the code or check that now stops the mistake, so a reader can see it is enforced, not hoped for.

The lessons here are general: true of any association running jason on PayHOA. A community's own (its units, its
board's decisions) are its specification's (``Community.lessons()``), kept private with the rest of its facts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum


class Area(Enum):
    OWNER_INFO = "owner-info"            # the annual Civil Code 4041 request and its answers
    MAILROOM = "mailroom"                # letters through PayHOA's Mailroom (Lob)
    EMAIL = "email"                      # email batches through PayHOA
    FORMS = "forms"                      # the PayHOA form, the fillable PDF, the paper form
    DOCUMENTS = "documents"              # drafts, Docs, the letterhead, the packet
    REPOSITORY = "repository"            # what is kept in git and what is not
    ENFORCEMENT = "enforcement"          # violations, hearings, fines, and their notices
    RENTALS = "rentals"                  # leasing approvals and limits
    GOVERNING = "governing"              # the governing documents themselves: amendments, citations, meetings
    ONBOARDING = "onboarding"            # taking on an association, or a change of manager: its records and access


class Status(Enum):
    FIXED = "fixed"                      # the change is made and a guard enforces it
    OPEN = "open"                        # a change still to make in jason
    DECISION = "decision"                # a person's or the board's call before anything can change


@dataclass(frozen=True)
class Lesson:
    key: str
    learned: date
    areas: tuple[Area, ...]
    what: str                            # what happened
    why: str                             # why it happened
    change: str                          # what changed, or what has to
    status: Status
    guards: tuple[str, ...] = ()         # the code, check, or command that now enforces it
    docs: tuple[str, ...] = ()           # where it is written up
    notes: tuple[str, ...] = field(default_factory=tuple)

    def applies_to(self, area: Area) -> bool:
        return area in self.areas


OCT_2026 = date(2026, 10, 2)
RUNBOOK = "docs/owner-information.md (What the 2027 cycle taught)"

LESSONS: tuple[Lesson, ...] = (
    Lesson("form-link-needs-unit", OCT_2026, (Area.FORMS, Area.EMAIL, Area.MAILROOM, Area.OWNER_INFO),
           "Every letter, QR code, and email linked to the PayHOA form without the unit; owners saw \"You do not have "
           "permission to access this form\" and only an administrator could open it.",
           "PayHOA's owner app opens a form only with the unit (;unitId=). The test round trip submitted through the "
           "API, which names the unit itself, so it passed.",
           "Every form link carries the unit; the printed form gives the way in words instead of a link.",
           Status.FIXED,
           guards=("payhoa_forms.owner_link / with_unit", "payhoa_forms.live_problem refuses a bare link",
                   "fillable.link_phrase links each emailed copy's words to its unit"),
           docs=(RUNBOOK, "docs/forms.md (Channels and assurance)")),
    Lesson("letters-cannot-be-recalled", OCT_2026, (Area.MAILROOM, Area.OWNER_INFO),
           "The letters were mailed first; when the link problem surfaced about 70 minutes later, every cancel failed.",
           "Lob's cancel window closes within minutes of a send; PayHOA still shows the letters as processing.",
           "Send the emails first, test the link as an owner the next day, then mail.",
           Status.OPEN, docs=(RUNBOOK,),
           notes=("To build: the mail batch refuses until the email batch went out a day earlier and a person "
                  "recorded the owner-side test (--link-tested-by NAME).",)),
    Lesson("test-as-an-owner", OCT_2026, (Area.FORMS, Area.EMAIL, Area.MAILROOM),
           "The API round trip passed while every owner's link failed.",
           "A test that skips the owner's own path (open the link, sign in, land on the form) tests something else.",
           "Before any send, open the exact link and QR target in a private window as the test account, signed out "
           "and signed in; jason never signs in, so a person does it and records it.",
           Status.OPEN, docs=(RUNBOOK,)),
    Lesson("letter-link-per-unit", OCT_2026, (Area.MAILROOM, Area.FORMS),
           "One letter for every owner cannot carry a link to each owner's unit.",
           "The Mailroom batch sends the same PDF to a building's owners.",
           "Either one Mailroom send per unit (each letter with its unit's link and QR code; same price per letter), "
           "or the written route only with a QR code to the sign-in page.",
           Status.DECISION, docs=(RUNBOOK,),
           notes=("First test whether ;unitId= survives PayHOA's sign-in page.",)),
    Lesson("paper-cannot-require", OCT_2026, (Area.FORMS, Area.OWNER_INFO),
           "A returned PDF left the occupancy question, required by law, blank.",
           "No PDF or paper form can refuse to be sent; the question sat at number 12, after the optional sections.",
           "Move occupancy and \"you are answering for\" up beside delivery, name the unit, say they are required by "
           "law, and print what is on file beside them; never pre-check (a default is confirmed unread). Follow a "
           "blank with one reply link per choice.",
           Status.OPEN, docs=(RUNBOOK,)),
    Lesson("same-as-unit-needs-no-person", OCT_2026, (Area.OWNER_INFO,),
           "\"Same as my unit address\" was sent to a person to enter.",
           "Any mailing-address answer was treated as an entry to make.",
           "It needs a person only when PayHOA's profile mails somewhere else.",
           Status.FIXED, guards=("member_preferences._to_record compares the profile's mailing street",)),
    Lesson("name-the-unit", OCT_2026, (Area.EMAIL, Area.OWNER_INFO),
           "Property managers with several units could not tell the emails apart.",
           "The unit was named only inside a sentence.",
           "Each email opens \"Regarding: {unit address}\", and the subject can carry {unit address}.",
           Status.FIXED, guards=("owner_send.EmailHandler.subject_for / message_for",)),
    Lesson("answers-need-a-policy", OCT_2026, (Area.OWNER_INFO,),
           "Complete answers still could not simply be written: one owner answered for co-owners with records of their "
           "own, a \"second\" email was a co-owner's, a rented unit's mail went to the tenant, and occupancy answers "
           "contradicted the unit's tags.",
           "The cycle had rules for recording an answer, not for an answer that raises a question.",
           "A response policy of rule rows: each finding is recorded, entered by a person, confirmed with the owner, "
           "held for the board, or ignored; a request with anything but \"record\" stays open, and writes held for the "
           "board are not made. The board's questions go to its canvas.",
           Status.FIXED, guards=("owner_responses.RULES", "owner-info --responses --canvas",
                                 "owner-info --apply holds the board's writes and keeps such requests open")),
    Lesson("law-outdates-provisions", OCT_2026, (Area.GOVERNING, Area.ENFORCEMENT, Area.RENTALS),
           "Governing documents and rules written before a change in the law stayed in use as written: a fine schedule "
           "above a new statutory cap, a rental cap below a statutory floor the law said the board must amend by a "
           "deadline.",
           "Where a provision no longer held was known only from board items and drafts, not to the procedure or "
           "command about to apply it.",
           "Each such provision is a Conflict row: what still governs, the part that yields, since when, and how it is "
           "applied meanwhile; procedures in its area show it.",
           Status.FIXED, guards=("authority_order.Conflict", "Community.conflicts()", "jason conflicts",
                                 "jason sop KEY (conflicts in its areas)"),
           docs=("AGENTS.md (Follow what is written, as far as a higher authority allows)",)),
    Lesson("amendment-standing-is-a-record", OCT_2026, (Area.GOVERNING,),
           "An amendment was reported as never recorded, from a board item's summary, while a leasing rule said it was "
           "recorded; the county index showed an amended restriction recorded by the association.",
           "Whether an amendment took effect was prose in several places, and no record held its standing.",
           "Check the public index before repeating whether an instrument was recorded. Each amendment should carry "
           "its standing (draft, adopted, recorded with number and date) as data, and the current text of the "
           "document it amends should be built from the amendments that took effect, not copied by hand.",
           Status.FIXED, guards=("living.standing_of (from the amendment's adopted and recorded dates)",
                                 "living.Effect: a declaration's amendment takes effect on recording",
                                 "jason living KEY lists what is applied and what is not in effect"),
           docs=("docs/living-documents.md",)),
    Lesson("returns-by-the-same-rules", OCT_2026, (Area.OWNER_INFO, Area.FORMS),
           "An emailed-back form had to be read and judged by hand.",
           "Only PayHOA submissions run through --apply.",
           "owner-info --returns DIR: returned PDFs and scans through the same rules, trust levels, and dry run.",
           Status.OPEN, docs=(RUNBOOK,)),
    Lesson("bounces-are-silent", OCT_2026, (Area.EMAIL,),
           "A bounced email never reached jason.",
           "PayHOA's mailer receives the bounce after the send succeeded.",
           "After a batch, read PayHOA's communications log for failed and bounced deliveries, and resend those owners' "
           "notices by mail: a bounced address is not valid, and the association shall resend (Civil Code 4041(e)).",
           Status.FIXED, guards=("notice_ledger.FOLLOW_UPS", "jason notices KEY --sync", "procedure notice-delivery"),
           docs=("docs/batches.md (Delivery and follow-ups)",),
           notes=("SendGrid reports a full mailbox (SMTP 452) as a bounce; 4041(e) counts it, and jason marks it "
                  "temporary.",)),
    Lesson("one-source-per-document", OCT_2026, (Area.DOCUMENTS, Area.EMAIL),
           "The email, its Doc, and the website guide were separate HTML, and drifted.",
           "Each was edited where it lived.",
           "Owner-facing documents are written once in Markdown; the email body, the letterhead Doc, and the PDF are "
           "made from that file.",
           Status.FIXED, guards=("markdown_html.render", "draft_docs.push_markdown", "jason letter --markdown"),
           docs=("docs/drafts-and-forms.md (Owner-facing documents: one Markdown source)",)),
    Lesson("leave-room-to-correct", OCT_2026, (Area.OWNER_INFO,),
           "The request opened October 1 with three weeks to answer and no room to resend.",
           "The cycle's dates were set late.",
           "Open in mid-September, so a correction can go out before the answer-by date and November 1.",
           Status.DECISION, docs=(RUNBOOK,)),
    Lesson("no-real-data-in-fixtures", OCT_2026, (Area.REPOSITORY,),
           "Tests carried owners' names, personal emails, phone numbers, and PayHOA ids into a public repository.",
           "Fixtures were copied from real records.",
           "Fixtures use made-up values; the operator's own ids are in .env; the community's facts are a private "
           "repository.",
           Status.FIXED, guards=("payhoa_test_membership_ids, payhoa_my_membership_id, payhoa_my_unit_id in .env",
                                 "mystique/ is its own repository, ignored by jason")),
    Lesson("plain-text-loses-the-marks", OCT_2026, (Area.GOVERNING,),
           "A plain-text copy of an amendment read the struck and the added words run together, both versions at once.",
           "The amendment carries its change in type (struck through, bold), and text extraction drops type styles.",
           "Operations are read from a source that keeps the marks (a Doc's runs, a text PDF's spans and rules, a "
           "scan's measured rules); a plain copy of an instrument whose legend promises marks is held out, not applied.",
           Status.FIXED, guards=("living.read_operations (marks_lost)", "tests/test_living.py"),
           docs=("docs/living-documents.md",),
           notes=("Text copies kept for search and quoting still read run together; quote an amended passage from "
                  "the consolidated text or the instrument, not the plain copy.",)),
    Lesson("amended-by-hand-drifts", OCT_2026, (Area.GOVERNING, Area.RENTALS),
           "The working text of the declaration, amended by hand, disagreed with the recorded amendment: a numeral "
           "changed without its words, words the amendment dropped kept, an article dropped; a hand copy of the "
           "amended terms in a rule row could drift the same way.",
           "Each amendment was applied by reading it and editing the copy, with nothing to check the result.",
           "Compute the current text from the base and the operations of each instrument in effect, with each "
           "section's provenance, and compare the working copy and the rule rows against it.",
           Status.FIXED, guards=("jason living KEY --working (the working copy against the current text)",
                                 "LivingDocument.checks (TextCheck: the rule rows' terms in the current words)"),
           docs=("docs/living-documents.md",),
           notes=("The full comparison (--all-sections) is mostly the base's OCR slips until the base is reconciled.",)),
    Lesson("ocr-engine-runs-words-together", OCT_2026, (Area.DOCUMENTS, Area.GOVERNING),
           "The recorded declaration's OCR ran about one word in thirty into the next (\"ofthe\", \"Notmore\"): a word "
           "error rate of 8.6% against the working copy, two thirds of it run-together words.",
           "PyMuPDF's page OCR takes Tesseract's characters and builds words itself, losing the narrow spaces of "
           "justified type. Tesseract's own tool, with the same model at the same resolution, read 2.2%.",
           "A Tesseract command-line engine reads scans with the tool's own word spacing and boxes; the text rules "
           "split what is left run together, as suggestions.",
           Status.FIXED, guards=("ocr.TesseractCli (before PyMuPdfTesseract in ocr.engines)",
                                 "scan_marks.scan_text(engine=\"auto\")", "tests/test_ocr_correct.py"),
           docs=("docs/ocr-correction.md",),
           notes=("A base text already cached was read the old way and keeps its transcriptions; reading it again is a "
                  "person's decision, since the transcriptions name the old text's words.",)),
    Lesson("model-corrects-the-drafting", OCT_2026, (Area.DOCUMENTS, Area.GOVERNING),
           "Told what OCR errors look like and asked to correct a passage, the local model also changed the drafter's "
           "grammar, turned an article's numeral into a roman one, invented a notary's commission number, replaced a "
           "sentence with another, and quoted words not in the passage; on the cleanest passages it changed right "
           "words nine times as often as the text rules.",
           "A writer model makes text read well; faithfulness to the page is not what it optimizes.",
           "The model reads only the tokens the lexicon doubts, or chooses among readings it is given; its edit must "
           "be minimal and pass the guard; a suggestion is likely only when two independent readers agree.",
           Status.FIXED, guards=("ocr_models.minimal", "ocr_correct.guard", "ocr_correct.tier",
                                 "tests/test_ocr_correct.py"),
           docs=("docs/ocr-correction.md",)),
    Lesson("copy-shares-ocr-slips", OCT_2026, (Area.DOCUMENTS, Area.GOVERNING),
           "The hand-kept working copy kept some of the OCR's run-together words (\"ofRecord\") and made its own "
           "(\"ofCalifornia\", a misread letter), so its agreement with the OCR was taken as proof the OCR was right.",
           "The copy was made from the same OCR text, so the two readers were not independent there.",
           "Where the copy keeps the OCR's reading against a confident text rule, the rule's reading is asked; an "
           "OCR reading is likely only when two independent readers agree.",
           Status.FIXED, guards=("tasks.intake.ocr_reading_asks (copy slips asked; agreement tiers)",),
           docs=("docs/ocr-correction.md",)),
    Lesson("duty-gold-overstates", OCT_2026, (Area.GOVERNING,),
           "The phrase grammar for duties scored precision 1.00 on its gold sets, while random samples of its readings "
           "across all the governing documents had about four in five of the right kind.",
           "The gold passages were chosen for the traps the grammar was then written around; list items under a lead-in "
           "that states a purpose, a scope, or a set of methods, and consequences stated with \"shall\", are rare in them.",
           "Each measurement reports a blind set drawn after the grammar is frozen and a random sample of readings across "
           "the corpus beside the gold set; every reading stays a lead with a review status until a person confirms it.",
           Status.OPEN, guards=("scripts/eval_duties.py (gold.json dev and test halves, gold-fresh.json)",
                                "DocumentDuty.review (ReviewStatus)"),
           docs=("docs/document-duties.md (The gold sets and the measurements)",),
           notes=("To build: a gold set of list items under lead-ins, and a check that a lead-in stating a purpose or "
                  "scope passes no kind to its items.",)),
    Lesson("task-notes-marker", OCT_2026, (Area.GOVERNING,),
           "A synced Google Task's notes carried the assignment's command as a line starting 'jason:', which the sync "
           "reads as the task's marker, so every run would have made a duplicate task.",
           "The marker is the first notes line that starts with 'jason:', and free text could start the same way.",
           "Notes write the command as 'Command: ...' and escape any other line starting 'jason:'.",
           Status.FIXED, guards=("schedule_sync._about", "tests/test_schedule_sync.py (a check-off recorded back)"),
           docs=("docs/schedule.md (On Google Calendar and Google Tasks)",)),
    Lesson("duties-need-owners", OCT_2026, (Area.GOVERNING,),
           "Read across the documents, 47 duties with a deadline or a recurrence had nothing tracking them, among them "
           "the board's financial reviews, which the law makes monthly.",
           "Duties were read and listed, but no record said who does each one, or when.",
           "Each duty is covered by an assignment (a role, a cadence, an anchored clock, or an event's module) that the "
           "board adopts; a coverage check lists any duty no one owns or no clock sets.",
           Status.FIXED, guards=("jason.community.schedule.Assignment", "jason schedule --coverage",
                                 "procedure duty-schedule"),
           docs=("docs/schedule.md",)),
    Lesson("model-reads-norms-loosely", OCT_2026, (Area.GOVERNING,),
           "Asked to list a section's duties, the local model reported statuses, definitions, and a prohibition's "
           "descriptive clauses as norms, and missed list items under a lead-in (precision 0.78, recall 0.80).",
           "Deciding what is a norm turns on drafting forms the grammar reads exactly; the model is good at the part the "
           "words leave out, who bears a passive duty.",
           "The model fills only the bearers the grammar leaves unstated; the grammar's kinds and timing stay.",
           Status.FIXED, guards=("duty_model.merge_review(fill_only=True)", "jason duties --documents --fill-bearers",
                                 "tests/test_deontic.py"),
           docs=("docs/document-duties.md (What the numbers say)", "docs/document-tools.md (model trials)")),
    Lesson("cli-parser-built-not-imported", OCT_2026, (Area.REPOSITORY,),
           "A new option on jason notices reused --posted, which the command already had, and every jason command "
           "stopped working until it was found.",
           "The check after an edit imported jason.cli, and argparse refuses a duplicate option only when the parser is "
           "built, so the import passed.",
           "A test builds the whole parser and renders each command's help, so a clash fails the suite.",
           Status.FIXED, guards=("tests/test_cli_parser.py",)),
    Lesson("minutes-say-the-review", OCT_2026, (Area.GOVERNING,),
           "Searched for evidence of the board's monthly financial review (Civil Code 5500) and its ratification under "
           "5501, the minutes named the treasurer's report but never said the board reviewed the reconciliations.",
           "Minutes record the report as received; the statute asks for a review of named documents, and the words that "
           "would show it were never written down.",
           "The evidence finder proposes what the minutes show and marks a named report as supporting only. The minutes "
           "template should carry a line that says the review was done, which is a decision for the secretary and the "
           "board.",
           Status.DECISION, guards=("jason schedule-evidence", "procedure duty-schedule"),
           docs=("docs/schedule.md (Evidence: What the minutes show)",)),
    Lesson("meeting-clocks-read-forward", OCT_2026, (Area.GOVERNING, Area.DOCUMENTS),
           "Reading the record backward for evidence that duties were done showed board meeting notices given to "
           "members fewer than the four days Civil Code 4920(a) requires, some on the day of the meeting, and minutes "
           "first dated weeks past the 30 days of 4950(a).",
           "Nothing read the meetings' clocks ahead of time. The calendar carried the notice day, but no check set "
           "the record against it, so a late notice or late minutes was found only after the fact.",
           "The watch reads the same records forward: for each board meeting, the notice day and the minutes day "
           "from the notice catalog's clocks, and what is on record for each. A day passed with none on record ranks "
           "first in jason attention; a day within two weeks is due soon. The board packet procedure reads it before "
           "the notice day. Whether the minutes reach members by being posted, not only dated, is still not kept.",
           Status.FIXED, guards=("jason schedule-evidence --watch", "jason attention (meetings section)",
                                 "tests/test_meeting_watch.py", "procedure board-packet"),
           docs=("docs/schedule.md (The watch)", "docs/attention.md")),
    Lesson("email-topic-values", OCT_2026, (Area.EMAIL,),
           "Measured against hand-labelled requests, owners' emailed repair requests were found less than half the "
           "time, and the email topic fallback never fired.",
           "The fallback compared bare words such as 'maintenance' to topic values such as 'maintenance and repairs', "
           "so nothing matched; and the kind rules had never been measured.",
           "The fallback uses the Topic members themselves; kinds are scored against a private gold set before a rule "
           "changes.",
           Status.FIXED, guards=("tests/test_responses.py (test_classify_email)", "jason respond --measure",
                                 "procedure respond"),
           docs=("docs/responses.md (How well the kinds are read)",)),
    Lesson("ocr-labels-garbled", OCT_2026, (Area.GOVERNING, Area.DOCUMENTS),
           "Building a living document from a scan's OCR, the outline reader missed garbled section labels ('41' for "
           "4.1, 'Gj)' for (j)) and read a broken-up table of contents as sections, so corrections keyed to those "
           "sections went stale and structural drift against the working copy was overstated.",
           "outline_from_text expects a typed document's clean labels; OCR drops dots, confuses letters and digits, and "
           "breaks dot leaders.",
           "A label grammar reads the label the order expects and skips the table of contents; the working copy may "
           "place what the grammar cannot read, and a clear in-order label is never renumbered.",
           Status.FIXED, guards=("outline_labels.outline_from_ocr", "outline_align", "tests/test_outline_labels.py"),
           docs=("docs/document-readings.md (Section numbers from a scan's OCR)",)),
    Lesson("reading-moves-transcriptions", OCT_2026, (Area.GOVERNING, Area.DOCUMENTS),
           "A better OCR reading of the recorded base was ready, but the person's transcriptions and open questions "
           "were keyed by section, and the new engine misreads different labels, so switching would have dropped or "
           "misplaced them.",
           "Transcriptions are keyed by section number, and a change of reading or of numbering moves the sections.",
           "A re-read is a dry run that migrates each transcription by its words and re-keys the questions; the switch "
           "needs a person's name and refuses a dry run numbered otherwise than the builds. The label grammar, tuned on "
           "one engine, first collapsed the other's columned table of contents into the last article; it now skips "
           "number-only rows and drops word-poor front matter, and every transcription is placed.",
           Status.FIXED, guards=("ocr_reread.migrate", "jason living KEY --use-reread (numbering check)",
                                 "tests/test_ocr_reread.py",
                                 "tests/test_outline_labels.py (another engine's failure patterns)",
                                 "procedure document-intake (re-read step)"),
           docs=("docs/living-documents.md (Re-reading a base)",)),
    Lesson("copied-passages-go-stale", OCT_2026, (Area.GOVERNING, Area.DOCUMENTS),
           "Notices, templates, rules, and vendor forms carry copies of governing-document sections, and a copy keeps "
           "the words of the day it was made after an amendment changes the section.",
           "A pasted passage has no link back to the section it copies.",
           "jason's own documents quote by reference ({QUOTE:key#n}, {CITE:key#n}), filled from the living document "
           "when rendered and refusing to render on a miss; a scan finds copies elsewhere and marks each current, stale, "
           "or draft. Adopted documents are not edited: a stale copy is a finding for their next revision.",
           Status.OPEN, guards=("jason.community.section_refs (fail-loud rendering)", "jason section-refs --scan",
                                "tests/test_section_refs.py", "procedure owner-document", "procedure law-review"),
           docs=("docs/embedded-references.md",),
           notes=("Fixed for jason's sources; open for adopted documents until their next revision.",)),
    Lesson("quotes-carry-ocr-slips", OCT_2026, (Area.DOCUMENTS,),
           "A section quoted from a base read by OCR prints the OCR's run-together words to owners.",
           "The living text is built from the recorded scan; transcriptions do not yet cover every section.",
           "A quote takes the working copy's spacing only where its letters are identical, and otherwise carries a "
           "note to check it before sending.",
           Status.OPEN, guards=("section_refs DiskResolver typesetting note",),
           docs=("docs/embedded-references.md",)),
    Lesson("base-swallows-notary-page", OCT_2026, (Area.DOCUMENTS,),
           "The last section of a base read by OCR ran into the signature page and notary acknowledgment, so the copy "
           "detector matched unrelated deeds by their notary text.",
           "The outline reader ends a section only at the next label, and the execution block has none.",
           "The detector drops runs common to many documents and requires an excerpt to cover part of its section; "
           "the base reading still needs the execution block split off.",
           Status.OPEN, guards=("embedded_copies boilerplate filter and EXCERPT_COVERAGE",),
           docs=("docs/embedded-references.md",)),
    Lesson("people-keep-clocks-by-hand", OCT_2026, (Area.GOVERNING,),
           "People kept clocks in Google Tasks and the calendar that jason had no assignment for (policy renewals, a "
           "reserve CD, seasonal grounds work, a tax resolution), and open tasks past their due day showed in no digest.",
           "jason read only its own keyed tasks and events.",
           "jason reads the people's tasks and events (read-only), matches each to what it tracks, proposes a clock "
           "for each untracked recurring item, and lists stale tasks in jason attention. It marks nothing in Google.",
           Status.FIXED, guards=("jason schedule --read-google --people", "people_tasks.classify",
                                 "attention people section", "tests/test_people_tasks.py", "procedure duty-schedule"),
           docs=("docs/schedule.md (People's own tasks and events)",)),
    Lesson("reminder-is-not-a-deadline", OCT_2026, (Area.GOVERNING,),
           "A person's 'Property Taxes Due' calendar event fell on a day that is no statutory tax date of any kind.",
           "The event mirrored a real delinquency date by six months; a reminder was kept as if it were the deadline.",
           "The tax dates are tabled from the statutes; a check that a covered event falls on one of its obligation's "
           "dates is still to build.",
           Status.OPEN, docs=("docs/insurance-and-deadlines.md",)),
    Lesson("task-due-day-is-not-a-filing", OCT_2026, (Area.GOVERNING,),
           "A filing task's due day was read as the day the last filing was made, a year off from the filing's own "
           "record.",
           "A task's due day is a person's plan, not evidence of the act.",
           "An obligation counts from the filing's own record (done_on), and a biennial filing is a cadence from its "
           "year.",
           Status.FIXED, guards=("Obligation done_on", "Assignment.from_year", "tests/test_schedule.py")),
    Lesson("stored-read-keeps-the-key", OCT_2026, (Area.GOVERNING,),
           "The first stored read of the calendar kept no event ids or private keys, so jason's own events could be "
           "told from people's only by their titles.",
           "The read copied a few display fields.",
           "The read keeps each event's id and extendedProperties.",
           Status.FIXED, guards=("people_tasks EVENT_FIELDS", "tests/test_people_tasks.py")),
    Lesson("duty-readings-keyed-to-copy-numbers", OCT_2026, (Area.GOVERNING,),
           "Read for stale citations, dozens of document-duty readings named sections the living text does not have "
           "(numbered as the working copy numbers them), and others named sections missing from their outline.",
           "Records cite a section by its number alone, and the number depends on which copy and which reading "
           "numbered it.",
           "Superseded by numbers-are-not-identity: records now carry a permanent id beside the number.",
           Status.FIXED, guards=("jason cite --stale", "jason cite --migrate-ids", "procedure law-review"),
           docs=("docs/record-addresses.md",)),
    Lesson("numbers-are-not-identity", OCT_2026, (Area.GOVERNING,),
           "Of 99 stale citations, 58 named sections by the working copy's numbers and 22 named numbers an outline "
           "prints twice; only 21 were truly gone or changed.",
           "Records cited a section by its number alone, and the number depends on which copy and which reading "
           "numbered it.",
           "Each section has a permanent id, its address at the version where it first appeared; a renumbering or "
           "another reading is a name in its history. Records store the number as written, the id, and the version.",
           Status.FIXED, guards=("jason.community.permanent_ids", "jason cite --migrate-ids", "Treatment.RELOCATED",
                                 "tests/test_record_addresses.py"),
           docs=("docs/record-addresses.md",)),
    Lesson("number-alone-is-ambiguous-across-readings", OCT_2026, (Area.GOVERNING,),
           "A notice provision citing two subsections could not say whether it used the working copy's numbers or the "
           "living text's, which give those numbers to different sections.",
           "The provision was written against one copy and records only the number.",
           "The migration stores no id where more than one section answers and lists the candidates for a person.",
           Status.DECISION, guards=("jason cite --migrate-ids (more than one section answers)",)),
    Lesson("short-forms-unread", OCT_2026, (Area.GOVERNING,),
           "'Section 4.15 (...), subsection (a)' was read as a citation of 4.15, not 4.15(a), and a bare 'subsection "
           "(b)' inside a section went unplaced.",
           "The reference grammar read only full citations.",
           "A short form in the same sentence narrows its antecedent, and a bare subsection reads as the enclosing "
           "section's child or sibling where the outline has one.",
           Status.FIXED, guards=("references short-form pass", "tests/test_outlines_references.py")),
    Lesson("reading-in-place-of-words", OCT_2026, (Area.GOVERNING,),
           "Listing what cites a section, a conflict row's summary of the provision would have stood as the "
           "provision itself.",
           "jason's records keep a summary ('says') beside the citation, and nothing kept the two apart.",
           "A citation leads with the recited words and the version in force; a record's summary is shown only as "
           "jason's reading, beside the words.",
           Status.FIXED, guards=("cite Citing.reading / recitedWords", "tests/test_cite.py")),
    Lesson("roman-under-letter-split", OCT_2026, (Area.GOVERNING,),
           "Splitting a statute's words to a subdivision, a deeper '(i)' ended the subdivision '(a)' early.",
           "A roman numeral and a letter share the glyph 'i'.",
           "The splitter reads the label that succeeds the one asked for, not any label at the same glyph.",
           Status.FIXED, guards=("cite.label_text", "tests/test_cite.py")),
    Lesson("executive-minutes-counted-open", OCT_2026, (Area.GOVERNING,),
           "An executive session's minutes, dated earlier, could have met the 30-day clock for the open meeting's "
           "minutes.",
           "The minutes reader took any minutes copy in the meeting catalog, confidential ones included.",
           "The reader skips confidential copies; executive-session minutes show only that they exist and their date.",
           Status.FIXED, guards=("schedule_evidence.minutes_on_record", "tests/test_record_stages.py")),
    Lesson("approval-item-is-not-approval", OCT_2026, (Area.GOVERNING,),
           "Most minutes name the earlier meeting under 'Approval of minutes' without saying the motion passed.",
           "Minutes are written on the agenda's outline.",
           "jason reports an approval as stated (the words say it passed) or only listed. Writing 'The board approved "
           "the minutes of DATE (M/S/P)' is a practice for the secretary and the board to adopt.",
           Status.DECISION, guards=("jason record-stages --minutes",), docs=("docs/record-stages.md",)),
    Lesson("notice-file-is-not-delivery", OCT_2026, (Area.GOVERNING,),
           "For rule changes made before the delivery log began, only the 4360 notices' files are on disk.",
           "A file shows the notice was written, not that members received it.",
           "jason reports 'a file in time; its delivery is not on record' and never counts it as met; a person confirms "
           "each delivery and records it in the notice ledger.",
           Status.OPEN, guards=("record_stages evidence strength",), docs=("docs/record-stages.md",)),
    Lesson("model-asserts-quorum", OCT_2026, (Area.GOVERNING, Area.DOCUMENTS),
           "Two minutes drafts from Zoom transcripts each said 'a quorum was present' while listing two of four "
           "directors on the call, below the bylaws' majority of those in office; one recorded a motion as carried, "
           "and the other set out a lawsuit and a member's assessment hearing in the open business.",
           "The model wrote the quorum sentence from the template's prompt instead of counting, and a meeting with no "
           "executive break gave it every subject discussed.",
           "The drafter counts the directors on the call against the board's quorum, flags a quorum claim the count "
           "does not support and any motion acted on without one, and lists lines naming a subject the open minutes "
           "give only in general terms. Whether to ratify actions taken without a quorum is the board's decision.",
           Status.FIXED, guards=("minutes_draft.checks", "jason board --minutes DATE --recheck",
                                 "tests/test_minutes_draft_checks.py", "procedure board-packet"),
           docs=("docs/board-agenda.md (Drafting the minutes from the Zoom record)",)),
    Lesson("outline-numbers-are-the-readers", OCT_2026, (Area.DOCUMENTS, Area.GOVERNING),
           "An owner's manual's part letters were hung under the section before them ('4(A)', 'B-18(C)'), and a list "
           "under an unnumbered heading was read as a second 'B-12(i)'; records already cited those made-up numbers.",
           "The Docs outline reader numbers by nesting, and a part letter or an unnumbered list has no number of its own.",
           "Extraction keeps every printed number and maps each made-up one to where it now lives (a concordance), so old "
           "citations still resolve. The outline reader itself still does this.",
           Status.OPEN, guards=("jason manual --concordance", "manual.resolve_old", "tests/test_manual.py"),
           docs=("docs/owners-manual.md",)),
    Lesson("span-is-not-subject", OCT_2026, (Area.DOCUMENTS,),
           "One rule section's span in the outline ran on over a bound-in collection policy, its statutory notice, and "
           "an application form, so duties and an assignment cited the rule for the notice.",
           "A section's span ends only at the next label, and bound-in documents carry none.",
           "Sections are split into pieces by kind; the notice now has its own address in the collection policy's book. "
           "Open until the assignment that cites the old span is re-pointed.",
           Status.OPEN, guards=("manual classification pieces",), docs=("docs/owners-manual.md",)),
    Lesson("guide-states-duties", OCT_2026, (Area.DOCUMENTS,),
           "Guidance in an owner's manual said what owners 'shall' maintain without citing any source.",
           "A guide written for owners restates duties in its own words.",
           "Classification asks a person when guidance states an owner's duty with no source; it is never taken as a rule "
           "on its own.", Status.FIXED, guards=("manual evidence check", "AskKind.SECTION_KIND")),
    Lesson("askkind-classify-is-the-librarys", OCT_2026, (Area.DOCUMENTS,),
           "A section-kind question filed under the library's classify kind would have been applied as a library file's "
           "kind and failed.",
           "One question kind was reused for a different subject.",
           "Section kinds have their own question kind, applied by the next classification run.",
           Status.FIXED, guards=("AskKind.SECTION_KIND", "tests/test_manual.py")),
    Lesson("grammar-misses-future-and-passive-duties", OCT_2026, (Area.GOVERNING,),
           "Rule sections phrased 'are to be', 'requires', or 'will be' showed no norm to the duty grammar.",
           "The deontic grammar reads shall, must, may, and their negatives.",
           "Listed as grammar leads; the grammar needs these forms.", Status.OPEN, guards=("jason manual --classify (grammar leads)",)),
    Lesson("fusion-gave-up-dense", OCT_2026, (Area.DOCUMENTS,),
           "The hybrid search, jason's default retriever, was never measured; on the gold questions it found fewer "
           "paraphrased answers than the dense ranking alone (0.67 against 0.78).",
           "Equal-weight fusion with a large k let the keyword ranking's misses dilute the dense ranking's first places.",
           "The fusion weighs the dense ranking 1.5 with k 10 (recall@5 0.75 to 0.88), measured on the gold set; a change "
           "to retrieval is measured with scripts/eval_retrieval.py before and after, and recorded in the model trials.",
           Status.FIXED, guards=("retrieval.HYBRID_RRF_K and DENSE_WEIGHT", "scripts/eval_retrieval.py",
                                 "tests/test_retrieval.py"),
           docs=("docs/document-tools.md (model trials)", "docs/rag-roadmap.md")),
    Lesson("resource-template-reserved-section", OCT_2026, (Area.GOVERNING,),
           "An MCP resource template for a section would not match sibling sections ('6.2(a),6.2(b)'), and a broad "
           "template caught versioned addresses with the version glued to the book.",
           "URI template simple expansion stops at a comma, and a bounded variable accepts '@' and ':'.",
           "Sections use reserved expansion ({+section}), templates are ordered most specific first, and every handler "
           "rebuilds the address from its parameters.",
           Status.FIXED, guards=("jason.mcp.resources", "tests/test_record_resources.py")),
    Lesson("document-in-two-books-lists-twice", OCT_2026, (Area.GOVERNING,),
           "A document mapped to two books had its sections listed twice as resources.",
           "A document's address key is its first book entry, so both books produced the same addresses.",
           "The resource listing skips a document already listed.",
           Status.FIXED, guards=("tests/test_record_resources.py (no address listed twice)",)),
    Lesson("docx-carries-pending-suggestions", OCT_2026, (Area.DOCUMENTS,),
           "A Doc's Word and Markdown exports carried its unaccepted suggestions as if they were the text, so a rules "
           "Doc's local export, and a dozen apparent rule changes, came from suggestions no one had accepted.",
           "Suggestions arrive as tracked changes; a reader that keeps every run reads them as text, and the Markdown "
           "export applies them.",
           "The revision reader reads the text as it stands (insertions out, deletions kept) and lists the suggestions "
           "apart. Other readers of a Markdown export still get the suggested text.",
           Status.OPEN, guards=("revision_detection.docx_text", "revision_detection.docx_suggestions",
                                "tests/test_revision_detection.py"), docs=("docs/revision-detection.md",)),
    Lesson("drive-revision-exports-rate-limited", OCT_2026, (Area.DOCUMENTS,),
           "Exporting a Doc's revision history failed with HTTP 429 after a few revisions.",
           "Drive throttles revision exports tightly.",
           "The export retries on Retry-After or backoff, and the fetch paces itself.",
           Status.FIXED, guards=("GoogleDrive.export_revision", "revision_detection EXPORT_PAUSE")),
    Lesson("library-resolves-by-name-only", OCT_2026, (Area.DOCUMENTS,),
           "Uploads of different sizes under one name all carried one file's hash in the library index, so a different "
           "version was attributed to the wrong copy.",
           "The library resolves a PayHOA file to its local mirror by name alone.",
           "Revision detection counts a mirror only when its size agrees; the library index itself still resolves by name.",
           Status.OPEN, guards=("revision_detection mirror size check",)),
    Lesson("effective-date-is-a-claim", OCT_2026, (Area.DOCUMENTS,),
           "Later copies of a manual kept printing an old 'EFFECTIVE' date, and ordering versions by it put recent "
           "copies before old ones.",
           "A date the text prints is what the text claims, not when the copy existed.",
           "A version keeps its existed-by dates (email, upload, Drive, PDF metadata) apart from the dates it claims, and is "
           "ordered by the former.", Status.FIXED, guards=("revision_detection Version.existed / claims",)),
    Lesson("page-numbers-survived-furniture", OCT_2026, (Area.DOCUMENTS, Area.GOVERNING),
           "Page numbers and a footer just above the margin band survived the furniture pass and split a recited "
           "section's sentence.",
           "The pass dropped only margin lines whose letters recurred on another page; a page number differs on every "
           "page and is too short for a likeness, and a footer on a page scanned askew sat just inside the band.",
           "Page numbers are matched by shape and height; footers just outside the band by likeness at the same height; "
           "OCR lines are kept so the pass can improve without new OCR (jason living KEY --page-lines, kept only when the "
           "words match).",
           Status.FIXED, guards=("scan_marks.drop_furniture", "tests/test_scan_marks.py"),
           docs=("docs/living-documents.md (Page furniture)",)),
    Lesson("instruction-lead-in-joined-the-words", OCT_2026, (Area.GOVERNING,),
           "An amendment's instruction ('Section X (“Caption”), subsection (m) (‘Caption’)') became a "
           "subpart's caption and was recited inside the section.",
           "The caption was the last quoted run anywhere after the section number, and OCR mixed curly and single quotes.",
           "A caption belongs only to the label it follows, any quote style is read, an instruction ends at its colon, and "
           "the operation's words end at the next instruction or the signature block.",
           Status.FIXED, guards=("living.read_instruction", "living.read_operations", "tests/test_living.py"),
           docs=("docs/living-documents.md (An instruction's lead-in)",)),
    Lesson("history-and-provenance-disagreed", OCT_2026, (Area.GOVERNING,),
           "A section's history listed an amendment while its provenance said it was written in the original.",
           "The provenance described only the section's own words; the recitation and the history include its "
           "subsections.",
           "The provenance names each subsection another instrument set, and the version fields describe the words "
           "recited.", Status.FIXED, guards=("SectionText.parts", "tests/test_cite.py (history and provenance agree)")),
    Lesson("doc-smart-chips-dropped", OCT_2026, (Area.DOCUMENTS,),
           "A checklist Doc read as questions with no answers: its answers were smart chips (linked files, people).",
           "The Docs reader kept text runs only.",
           "Rich links render as [title] and person chips by name.", Status.FIXED,
           guards=("google.docs.document_markdown", "tests/test_onboarding.py (smart chips kept)")),
    Lesson("takeover-list-omits-statutory-items", OCT_2026, (Area.ONBOARDING,),
           "A management company's takeover request list left out what the law requires the association to keep or "
           "give: the reserve study, the elevated-element inspection, the Secretary of State statements, loans, and the "
           "policy statement's addresses.",
           "Takeover lists are written for running the books, not for the statutes' records.",
           "The onboarding checklist marks each statutory item by its law and checks it against the profile and disk.",
           Status.FIXED, guards=("jason.community.onboarding.ITEMS (Origin.LAW)", "jason onboard --checklist",
                                 "tests/test_onboarding.py"), docs=("docs/onboarding.md",)),
    Lesson("outgoing-manager-only-items", OCT_2026, (Area.ONBOARDING,),
           "At a change of manager, the ledgers, receivables, owner account numbers, and start-up funds never reached "
           "the board's own record, and the board's access to the old portal ended before the records were delivered.",
           "Only the outgoing manager held them, and nothing named them or a date in the termination.",
           "Name these items, with dates, in the termination notice; keep the board's portal access through the "
           "handover; have the outgoing manager copy the board.", Status.DECISION, docs=("docs/onboarding.md",)),
    Lesson("gmail-store-window", OCT_2026, (Area.EMAIL,),
           "A history search found nothing in the stored Gmail because the store keeps a limited window.",
           "The Gmail sync stores a rolling window of messages.",
           "The window is written down (730 days from the last sync, kept with the store); an older search is a live "
           "read-only search, and an answer says which it came from.",
           Status.FIXED, guards=("docs/gmail.md (The window)", "the store's recorded days"), docs=("docs/gmail.md",)),
    Lesson("tuned-on-the-test", OCT_2026, (Area.DOCUMENTS,),
           "The hybrid search's fusion settings were tuned on the same 24 questions that reported their gain.",
           "One gold set served both to choose the settings and to score them.",
           "A held-out set written after the tuning and never used for it checks a change (recall@5 0.71 to 0.80 on 116 "
           "new questions, 12 won and 1 lost); before changing the fusion, both gold files run with the old settings "
           "passed as --fusion, and wins and losses are read question by question.",
           Status.FIXED, guards=("data/retrieval/gold-heldout.json", "scripts/eval_retrieval.py --gold ... --fusion K:W",
                                 "tests/test_eval_retrieval.py"), docs=("docs/document-tools.md (model trials)",)),
    Lesson("chunks-ignore-section-breaks", OCT_2026, (Area.DOCUMENTS,),
           "Questions on definitions, fee tables, form pages, and exported lists that lost their numbers were missed by "
           "every retrieval method.",
           "Passages were fixed 220-word windows that split sections and put unrelated subsections together.",
           "Passages are cut on the outline, the OCR labels, and the headings, with the section's path carried for "
           "ranking and the words kept exact for recitation (held-out hybrid recall@5 0.80 to 0.86; on the 24 tuning "
           "questions it fell 0.88 to 0.83, so both sets are read before a change is kept).",
           Status.FIXED, guards=("passage_sections.section_passages", "tests/test_passage_sections.py",
                                 "scripts/eval_retrieval.py --chunking"), docs=("docs/document-tools.md",)),
    Lesson("copies-crowd-the-top", OCT_2026, (Area.DOCUMENTS,),
           "A document kept as a Doc, a PDF's text, and a recorded scan filled four or five of every top ten with near "
           "copies of one passage.",
           "Retrieval ranked every copy on its own.",
           "Near copies fold under the best-ranked one, listed as also-in (held-out hybrid recall@5 0.86 to 0.91, no "
           "question lost); short boilerplate and two instruments written from one form never fold.",
           Status.FIXED, guards=("retrieval.collapse", "retrieval.near_copies", "tests/test_passage_sections.py")),
    Lesson("numbered-paragraph-title-doubled", OCT_2026, (Area.DOCUMENTS,),
           "Putting a numbered paragraph's opening words in its ranking prefix doubled them, and a neighbouring list "
           "item outranked the answer.",
           "A numbered paragraph's 'title' is its own first words.",
           "The prefix keeps only a short first sentence, or the number alone.", Status.FIXED,
           guards=("passage_sections._caption(numbered=True)",)),
    Lesson("copies-have-no-authority-order", OCT_2026, (Area.DOCUMENTS, Area.GOVERNING),
           "When near copies of a governing document fold, nothing says the recorded or adopted copy should be the one "
           "shown over a working copy.",
           "Neither the library nor the profile ranks a document's copies by authority.",
           "Add a Community method giving the order of authority for a document's copies, and pass it to collapse.",
           Status.DECISION, guards=("retrieval.collapse(prefer=...)",)),
    Lesson("no-nothing-relevant-signal", OCT_2026, (Area.DOCUMENTS,),
           "Questions whose answer is in no document still returned confident passages from the governing documents.",
           "Retrieval always returns its top k; no score says nothing answers.",
           "A search tool's results must not imply a passage answers the question. No dense or keyword score "
           "threshold separated the questions answered nowhere (best precision 0.33), so no advisory is shown; grow "
           "the absent list and measure again with eval_retrieval --no-answer.", Status.OPEN,
           guards=("retrieval.NO_ANSWER_COSINE (unset)", "retrieval.no_answer_advisory")),
    Lesson("notice-evidence-first-attempt", OCT_2026, (Area.EMAIL, Area.GOVERNING),
           "Record stages, the meeting watch, and the evidence finder counted any send as delivered: a notice owing "
           "resends to a fifth of the members looked the same as one every member received.",
           "Only the notices command and attention read the delivery ledger's standing; the others kept a first attempt.",
           "One reader weighs a notice as delivered, sent with follow-ups owed, sent, or a file; a file never meets a "
           "clock, and a send meets one only with what is owed listed.",
           Status.FIXED, guards=("notice_evidence.weigh", "notice_evidence.judge", "tests/test_notice_evidence.py",
                                 "procedure notice-delivery"), docs=("docs/notices.md",)),
    Lesson("notice-key-names-requirement", OCT_2026, (Area.EMAIL,),
           "Real notice keys did not start with their requirement's key, so a meeting notice got no proof of notice.",
           "Notices sent from PayHOA's screens were synced under ad hoc keys.",
           "Form keys are mapped and a meeting's day in a key is read as that meeting's notice (labeled as a reading); "
           "sync such notices as REQUIREMENT-DATE.", Status.OPEN, guards=("notice_record requirement matching",),
           docs=("docs/notices.md",)),
    Lesson("notice-text-not-kept", OCT_2026, (Area.EMAIL,),
           "A notice's record could not show the words members received: the email's text was not kept with its batch.",
           "Batches kept recipients and outcomes, not the message.",
           "Each sender keeps the text as rendered, subject, fill records, and recipients plan in data/notices/KEY/ with "
           "sha256 digests once sent or saved for sending; the record shows whether the text was edited since.",
           Status.FIXED, guards=("notice_text.keep", "notice_record.text_sent", "tests/test_notice_text.py"),
           docs=("docs/notices.md",)),
    Lesson("notice-quoting-the-law", OCT_2026, (Area.GOVERNING,),
           "A member notice put the board's purpose and effect before the rule's text, and a notice that only quoted "
           "the statute's requirement was counted as carrying it.",
           "Notices were drafted from the content list, not the statute's order, and the check matched words.",
           "Rule-change notices give the text first, then the board's description, labeled (4360(a)); the "
           "required-elements check masks recited statutes before it looks.",
           Status.FIXED, guards=("rule_change.member_notice", "notice_elements.mask_recitals",
                                 "tests/test_rule_change.py", "tests/test_notice_elements.py"),
           docs=("docs/notices.md (What a notice must say, checked)",)),
    Lesson("working-doc-is-not-adopted-text", OCT_2026, (Area.GOVERNING, Area.DOCUMENTS),
           "Publishing the working rules Doc whole would have presented dozens of passages changed with no adoption, "
           "and pending suggestions, as the adopted rules.",
           "The Doc is edited between adoptions, and its exports carried suggestions inline.",
           "jason manual --render prints each such passage's last adopted words where an adoption on record covers "
           "them, with jason's labeled note reciting the working words; where none is on record, a note only; "
           "--current prints the working words with the same notes; pending suggestions never appear.",
           Status.FIXED, guards=("manual.render", "manual_rule_change.separate (Unadopted.basis)",
                                 "tests/test_manual.py", "tests/test_manual_rule_change.py"),
           docs=("docs/owners-manual.md",)),
    Lesson("intake-queue-order", OCT_2026, (Area.ONBOARDING,),
           "The intake queue listed questions in the order scans found them: library classifications first, the "
           "questions deciding which text is in force behind them, and mostly OCR respacings.",
           "Nothing measured what an answer unblocks.",
           "intake_rank.priority ranks a legal clock, then a missing checklist item, then a stage gate, then a cited "
           "section, then quality; jason onboard shows the ranked queue.",
           Status.FIXED, guards=("intake_rank.priority", "tests/test_onboarding_session.py")),
    Lesson("answer-may-hold-a-secret", OCT_2026, (Area.ONBOARDING,),
           "A person asked where keys, codes, or a sign-in are kept may type the secret itself.",
           "Answers are stored as given.",
           "intake.answer refuses an answer that looks like a secret before anything is written, for the command line "
           "and MCP alike; a Keeper answer stores only the record's name.",
           Status.FIXED, guards=("intake.secret_reason", "tests/test_onboarding_session.py")),
    Lesson("profile-proposal-untracked", OCT_2026, (Area.ONBOARDING,),
           "A mapping or profile-fact answer is marked applied once its proposal is written, whether or not a person "
           "ever applies the patch.",
           "The applier's job ends at writing the proposal.",
           "Track a proposal's state, or ask again when its checklist item is still not present.", Status.OPEN),
    Lesson("packet-read-as-version", OCT_2026, (Area.DOCUMENTS, Area.ONBOARDING),
           "Taking in a folder, annual disclosure packets that carry a policy whole were reported as new versions of the "
           "policy.",
           "The version test measured how much of the document a file holds; with no name to narrow the candidates, a "
           "packet holding the whole policy passed.",
           "A version must also be mostly the document's own words; otherwise it is a copy carried inside another file "
           "and gets no book from the document.",
           Status.FIXED, guards=("ingest.find_versions / is_version", "tests/test_ingest.py")),
    Lesson("library-run-drops-ingested-rows", OCT_2026, (Area.DOCUMENTS,),
           "A library run rebuilds its documents table from the PayHOA catalog, so files taken in by hand would have "
           "vanished from it.",
           "save() drops and rebuilds the table.",
           "Files taken in are also kept in an ingested table, and save() copies them back.",
           Status.FIXED, guards=("library.keep_ingested", "tests/test_ingest.py")),
    Lesson("ingest-catch-all-folder", OCT_2026, (Area.ONBOARDING,),
           "Taking in a folder as new, most files would be proposed for a catch-all correspondence folder, because "
           "that is where the library files most statements and letters today.",
           "A file's folder is proposed from where the library already files its kind.",
           "Whether new files go to a catch-all folder is the board's or manager's call; a rule could prefer a folder "
           "pinned to the file's record.", Status.DECISION),
    Lesson("second-profile-shared-stores", OCT_2026, (Area.ONBOARDING,),
           "A second association's onboarding session read the first association's library, intake queue, stores, "
           "and private fact files.",
           "Every store was found from one shared data folder, some callers named it directly, and the private fact "
           "topics were one file each for every profile.",
           "The data root is named once (config.data_root, JASON_DATA_DIR); callers ask config.data_dir() or the "
           "settings when they need it; private fact topics are each profile's own (data/spec/<profile>/<topic>.json), "
           "the default profile's old files read for it alone until jason spec --migrate --yes copies them.",
           Status.FIXED, guards=("config.data_root", "community.private.path_of", "tests/test_profile_data.py",
                                 "jason spec --migrate"), docs=("docs/profiles.md (Each profile's data)",)),
    Lesson("profile-module-reads-active-facts", OCT_2026, (Area.ONBOARDING,),
           "A profile computes its private-fact rows at import; first imported while another profile was active, it "
           "cached that profile's facts, or none, for the whole process.",
           "The facts reader keyed on the active profile, not the profile asking.",
           "private.facts(topic, profile=...): each profile module passes its own key, and the onboarding and ingest "
           "contexts pass the profile whose checklist they build.",
           Status.FIXED, guards=("community.private.facts(profile=)", "tests/test_profile_data.py")),
    Lesson("empty-default-counted-present", OCT_2026, (Area.ONBOARDING,),
           "A new profile's checklist showed items present that held nothing: a map of empty groups and an all-empty "
           "record counted as rows.",
           "The size check counted entries, not content.",
           "A map counts only non-empty groups and an all-empty record counts nothing.",
           Status.FIXED, guards=("onboarding._size", "tests/test_onboarding_new.py")),
    Lesson("read-only-session-made-a-folder", OCT_2026, (Area.ONBOARDING,),
           "A read-only onboarding session created a data folder for a new profile.",
           "A loader called a folder helper that makes the folder.",
           "Loading references creates nothing; a test asserts the session leaves no folder.",
           Status.FIXED, guards=("outlines.load_rows", "tests/test_onboarding_new.py")),
    Lesson("listed-question-not-answerable-over-mcp", OCT_2026, (Area.ONBOARDING,),
           "A question listed over MCP could not be answered there until someone parked it from the command line.",
           "Listing computed the questions; answering read only the parked queue.",
           "Answering a listed question parks it first.",
           Status.FIXED, guards=("governance._with_onboarding_questions", "tests/test_onboarding_new.py")),
    Lesson("profile-root-finds-jason-subpackages", OCT_2026, (Area.ONBOARDING,),
           "A profile key such as 'tasks' would resolve to jason's own subpackage.",
           "The profile loader walks every parent of jason's community package.",
           "The scaffold refuses such keys, and the loader skips jason's own tree.",
           Status.FIXED, guards=("profile_scaffold key refusal", "profile.profile_root",
                                 "tests/test_profile.py (jason's subpackages are never a profile)")),
    Lesson("recorder-empty-or-unreachable", OCT_2026, (Area.ONBOARDING,),
           "A county recorder search returns no rows when its session fails to open, so 'nothing recorded' and "
           "'index unreachable' look the same.",
           "The reader swallows the session failure.",
           "The reader should raise, or the lookup check the session first.", Status.OPEN),
    Lesson("revision-text-reads-suggestions-accepted", OCT_2026, (Area.DOCUMENTS, Area.GOVERNING),
           "The revision history's copy of a Doc's current words read it as if every suggestion were accepted.",
           "Its text comes from the Word export, which applies insertions and drops pending deletions.",
           "A passage's note recites the rendered words with insertions taken out, so pending deletions still stand.",
           Status.FIXED, guards=("manual.render (working_of)",)),
    Lesson("insertions-hide-each-others-context", OCT_2026, (Area.DOCUMENTS,),
           "Taking one suggested insertion out broke the context that locates the next.",
           "Insertions were removed one at a time.",
           "All are found first, then removed together.",
           Status.FIXED, guards=("manual.strip_inserts", "tests/test_manual.py")),
    Lesson("adoption-between-versions-is-no-basis", OCT_2026, (Area.GOVERNING,),
           "An adoption dated between an earlier version and a change was about to vouch for words no version shows "
           "it adopted.",
           "Any adoption before the change was taken as covering the earlier words.",
           "The basis must be no later than the version the earlier words come from.",
           Status.FIXED, guards=("manual_rule_change.separate", "tests/test_manual_rule_change.py")),
    Lesson("broadcast-kept-is-handed-not-sent", OCT_2026, (Area.EMAIL,),
           "A broadcast's kept text is what jason handed PayHOA's composer; a person may edit it there before sending.",
           "jason cannot see the body PayHOA sent.",
           "Compare with the communication's body when the notice is synced, if PayHOA returns it.", Status.OPEN,
           guards=("notice_text.keep (state: handed)",)),
    Lesson("google-writes-without-yes", OCT_2026, (Area.GOVERNING, Area.DOCUMENTS),
           "Surveying every write jason makes outside itself for the console's approvals, five commands were found "
           "writing with no --yes step: the board items' sheet (create and update), the board items' Google Tasks "
           "sync, the property-history sheet, and a PayHOA request comment that is emailed to the owner.",
           "They were built as syncs of jason's own registers, so writing seemed routine. jason request-comment, "
           "which posts a PayHOA comment emailed to the owner, has no dry run or --yes either.",
           "Each gets a dry run by default and --yes (and later an approval kind), like every other outside write.",
           Status.OPEN, docs=("docs/console/approval-workflow.md (the survey)",)),
    Lesson("apply-loses-partial-results", OCT_2026, (Area.OWNER_INFO,),
           "The owner-information apply returned only counts, so a failure part-way left no record of which writes "
           "were made.",
           "The apply was written for all-or-nothing runs from the command line.",
           "Each write has its own result and audit line; a failure stops the run with what was written recorded.",
           Status.FIXED, guards=("owner_info_apply.execute_each", "tests/test_approvals.py")),
    Lesson("complete-only-after-writes", OCT_2026, (Area.OWNER_INFO,),
           "After writing, the apply treated every planned write as made, which would complete a request whose write "
           "was never approved or failed.",
           "The pending list was cleared after the run, not after each write.",
           "A write not actually made stays pending, so its request stays open (blocked, in an approval).",
           Status.FIXED, guards=("owner_info_apply", "tests/test_approvals.py")),
    Lesson("plan-reads-once", OCT_2026, (Area.OWNER_INFO,),
           "One owner-information plan read PayHOA three times, and a task imported from a command module.",
           "The response triage and the plan each read live on their own.",
           "The plan reads once through a wrapper that also refuses any write while planning, and the triage reuses it.",
           Status.FIXED, guards=("owner_info_apply.ReadOnce", "owner_responses.contexts(live=...)",
                                 "tests/test_approvals.py")),
    Lesson("plan-evidence-kept-no-copy", OCT_2026, (Area.OWNER_INFO, Area.GOVERNING),
           "An approval's evidence named a PayHOA request by its address only. The plan read the request live and kept "
           "no copy, so the console could print the address but never show what the plan had read.",
           "Evidence was designed as a pointer to a source jason holds on disk, and the owner-information plan's "
           "source (the form's submissions) is read live with no store behind it. A sidecar beside each approval "
           "would also have been listed as an approval: the store's glob took any apr-*.json.",
           "The plan keeps what it read beside the approval (<id>.evidence.json, written with the plan under the store "
           "lock), each request's evidence carries its read time and digest, and the evidence resolver opens every "
           "address from disk with the commands that read it again. The store lists only ids with no dot.",
           Status.FIXED, guards=("jason.approvals.evidence", "store.ids", "tests/test_evidence.py"),
           docs=("docs/console/approval-workflow.md (Evidence you can open)",),
           notes=("A plan made before snapshots still had no copy of its requests: see "
                  "request-read-thrown-away for the last full read that now fills the gap.",)),
    Lesson("request-read-thrown-away", OCT_2026, (Area.OWNER_INFO, Area.FORMS, Area.GOVERNING),
           "The evidence panel showed \"No copy on disk\" for every owner-information request. Only plans made after "
           "snapshots keep one; the PayHOA catalog lists requests (status only, never answers) and was last synced "
           "before the answers came in; the request files held comments, notes, and attachments but never the "
           "submission. Meanwhile every owner-information plan read each submission in full and threw it away.",
           "Each reader of a submission kept only what its own task needed (answers by field, a status, a file "
           "list), so no store held the request as PayHOA answered it.",
           "Whatever reads a submission in full keeps it as the request's last read "
           "(payhoa-files/requests/N/submission.json, written whole): fetch_submissions hands each raw read to a keep "
           "callback that gather_answers sets, sync-request-files saves it with one read a request, and a person can "
           "refresh one request from the console (POST /api/evidence/refresh, logged in evidence/refreshes.jsonl, "
           "never a write to PayHOA). The evidence resolver shows it as \"Last read from PayHOA\", masked by the "
           "snapshot's P2 rule, and compares it with the plan's read.",
           Status.FIXED, guards=("jason.tasks.submission_cache", "payhoa_forms.fetch_submissions(keep=...)",
                                 "jason.approvals.evidence.refresh", "tests/test_evidence.py",
                                 "tests/test_sync_request_files.py"),
           docs=("docs/console/approval-workflow.md (Evidence you can open)",)),
    Lesson("approvals-store-location", OCT_2026, (Area.GOVERNING,),
           "The console spec puts approvals in a SQLite store under the console's folder; the engine as built keeps one "
           "JSON file per approval and an append-only audit log in the profile's data folder.",
           "The engine was built before the console's storage was decided.",
           "A person picks one before the console is built.", Status.DECISION,
           docs=("docs/console/approval-workflow.md", "docs/console/architecture.md")),
    Lesson("web-writes-unguarded", OCT_2026, (Area.GOVERNING,),
           "jason-web's writes (board items, canvases, decisions, onboarding, owner-information confirmations, "
           "hearings) accepted any POST: any page in the person's browser could write jason's stores through loopback, "
           "and a DNS-rebinding page could read the API under its own name.",
           "The web app was built read-only first, and its writes were added without a guard.",
           "jason.web.guard checks Host on every /api request and Origin plus a per-process token on every write; a route "
           "that writes outside jason also needs the token in a header. The token is not a sign-in.",
           Status.FIXED, guards=("jason.web.guard", "tests/test_web_approvals.py"),
           docs=("docs/web-ui.md (The write guard)",)),
    Lesson("web-route-name-reused", OCT_2026, (Area.GOVERNING,),
           "The approvals engine's list reused the URL of the letters inbox, which the inbox, the nav badge, and the "
           "officer picker already read.",
           "Two approval stores grew in parallel under one name.",
           "One loader answers both shapes; whether to split them (letters under their own path) is a decision once "
           "the UI moves.", Status.DECISION, guards=("tests/test_web_approvals.py (the letters inbox keeps its shape)",)),
    Lesson("apply-signs-in-before-refusing", OCT_2026, (Area.GOVERNING,),
           "A web apply or check signed in to PayHOA before the engine refused it for its status, a missing second "
           "person, or its age.",
           "The live context was built before the engine's checks ran.",
           "The engine's problems are checked, and the refusal audited, before any live context is built.",
           Status.FIXED, guards=("approvals.engine.problems", "tests/test_web_approvals.py")),
    Lesson("console-sticky-offsets", OCT_2026, (Area.GOVERNING,),
           "Scrolling the console was strange once sign-in was added: the page kept scrolling into blank space past "
           "short screens, and jumped-to headings and a docked drawer landed under the header.",
           "The left nav (38 screens) was never sticky, so it set the page's height; the sticky header grew to two "
           "rows with the sign-in and admin-view controls, while the drawer's offset and the page's scroll padding "
           "assumed a fixed, short header.",
           "ConsoleShell measures the header (ResizeObserver) into --console-bar-h; the nav sticks below it and "
           "scrolls on its own, a pinned drawer sticks below it, and html scroll-padding-top reserves it. Check a "
           "header change by scrolling a short and a long screen.",
           Status.FIXED, guards=("ui/src/components/consoleshell.test.tsx (the header's height is published)",)),
    Lesson("shadowed-community-method", OCT_2026, (Area.GOVERNING,),
           "A new Community.developers (the people who maintain jason, for the console's view-as) replaced the "
           "existing Community.developers (the subdividers) in the same class, and 78 tests in the recorder, history, "
           "and filings modules failed with no error near the change.",
           "Python lets a second definition of a name in one class silently replace the first, and \"developer\" "
           "already meant the subdivider in jason's vocabulary.",
           "The grant is now Maintainer / Community.maintainers / maintainers.json. A test refuses any name defined "
           "twice in one class or module across src/jason and the profile. Before adding a Community method, grep "
           "for the name.",
           Status.FIXED, guards=("tests/test_no_shadowed_names.py",)),
    Lesson("file-route-ungated", date(2026, 10, 3), (Area.DOCUMENTS,),
           "The console's GET /api/file served any whitelisted file under data/ to anyone on the loopback, with no "
           "level check, no name, and no log; /api/library?confidential=1 listed confidential rows to anyone; and the "
           "evidence views took the name in the body, a pick from a list, as who opened a document unmasked.",
           "The routes were built for a canvas's photos before sign-in existed, and the data levels were written down "
           "(security-and-privacy.md) but not enforced: a level in a doc is not a check.",
           "Files and documents open only for a signed-in roster person whose offices open the level, by rule rows "
           "(SEE_RULES, PATH_RULES; a path no row places is P2); P3 only in the private view with a reason; each serve "
           "is logged in access/served.jsonl; a view's name is the sign-in's and its link is bound to that sign-in.",
           Status.FIXED, guards=("jason.web.access (require, level_of_path, SEE_RULES, PATH_RULES)",
                                 "tests/test_web_access.py"),
           docs=("docs/console/security-and-privacy.md (Roles)", "docs/console/documents.md (Gaps to close)")),
    Lesson("ui-tests-on-the-wrong-shape", OCT_2026, (Area.GOVERNING,),
           "The Approvals screen failed on the first real plan (\"items.filter is not a function\"): its tests fed the "
           "list the full approval, while GET /api/approvals sends a summary row whose items is a count.",
           "The UI fixture was the engine's record, not what the route answers; the Python and UI tests each passed "
           "against their own idea of the contract.",
           "The list reads either shape, and a UI test feeds it the summary row as the route builds it "
           "(engine.counts: items, byClass). A screen is opened on real data before it is called done.",
           Status.FIXED, guards=("ui/src/views/planapprovals.test.tsx (the server's summary rows)",)),
    Lesson("notice-labels-match-outline", OCT_2026, (Area.GOVERNING,),
           "Read for notice duties, the documents showed 52 untracked, though several already had a notice-clause row: "
           "the rows named sections the outline does not use ('(b) Due Process', '6.12 (payment plan)').",
           "A notice clause's section label is free text, matched against the outline's numbers and titles.",
           "A test checks each label a clause names by heading against its outline's numbers and titles. A free-text "
           "suffix after a valid number still passes, so that case is open.",
           Status.OPEN, guards=("tests/test_notice_catalog.py (labels are outline numbers or titles)",),
           docs=("docs/notices.md",)),
    Lesson("a-name-joined-chain-is-a-braid", date(2026, 10, 3), (Area.ONBOARDING,),
           "A Placer half-plex's chain of title came back with 22 deeds, one estate deed with three candidate priors and "
           "a 2009 deed with seven; drawn as a DAG it was a braid, and the 'line' through every prior took in the twin "
           "unit and the neighbors. Partner suffixes (PRTN) in the 1980s index also made private persons read as "
           "businesses, so a report would have printed them by name.",
           "Placer's index cites no prior deed, so each step is joined by party name, and a seller who sold several "
           "units, or a co-owner with other title, matches many earlier deeds. Every candidate stayed on the step "
           "unranked, and the graph drew each name hand-off as firm. PRTN was read as a business word, though it is "
           "a role a person carries as readily as a company.",
           "succession ranks priors by hand-off strength (each earlier grantee counted once, then exact spellings, then "
           "the newest): ChainStep.prior is the step's own predecessor and OwnershipHistory.line() the parcel's strand; "
           "the instrument graph draws the other candidates as leads ('shares a name'). party_kind strips a partner "
           "suffix before reading the name. `jason placer-history --processes` draws the strand thick and the side "
           "strands dotted, owners by role unless --names.",
           Status.FIXED,
           guards=("tests/test_history.py (the strongest hand-off is the prior; two spellings of one seller count once)",
                   "tests/test_instrument_graph.py (a second candidate is a lead; a PRTN person stays private)",
                   "tests/test_process_report.py (owners by role, the strand by prior)"),
           docs=("docs/placer.md", "docs/instrument-graph.md")),
    Lesson("utility-screen-wrong-shape", date(2026, 10, 3), (Area.DOCUMENTS,),
           "The utility payments screen read fields its loader never had, so its bills showed no document when it moved "
           "to Doc.",
           "The screen's test fed it a fixture written from the screen's idea of a row, not from what "
           "GET /api/utility-payments answers (each payment's rows and its attachments with their doc).",
           "The screen reads the loader's own shape, and the money tests render it from that shape: a payment's rows, "
           "and its attachments each with the DocRef the loader builds (utility_payments.attachment_refs).",
           Status.FIXED, guards=("ui/src/views/money.test.tsx (the loader's real shape: rows, attachments with doc)",
                                 "tests/test_money_docrefs.py"),
           docs=("docs/console/doc-component.md (Adopting it on a screen)",)),
    Lesson("docref-collapsed-spaces", date(2026, 10, 3), (Area.DOCUMENTS,),
           "A file named with two spaces in a row got no document reference: doc_ref folded the address's whitespace, "
           "so file:<path> named another file (or none), and the money loader dropped such a file rather than open the "
           "wrong one.",
           "Every evidence address went through one whitespace fold, written for free-text addresses (a citation, a "
           "board item); a path is not free text.",
           "evidence.clean_address keeps a file: address exactly and folds every other; doc_ref, resolve, view, the "
           "view route's level, and its log use it. The money loader's round-trip guard is gone.",
           Status.FIXED, guards=("jason.approvals.evidence.clean_address",
                                 "tests/test_docref.py (a two-space name keeps its spaces and opens its own file)",
                                 "tests/test_money_docrefs.py (a two-space attachment is its own reference)"),
           docs=("docs/console/doc-component.md (The reference)",)),
    Lesson("hearing-doc-level-by-folder", date(2026, 10, 3), (Area.DOCUMENTS, Area.ENFORCEMENT),
           "A hearing's notice Doc in Drive was held at P3 by the Hearings screen's loader, but the server judged the "
           "same Drive id by its folder: P0 under a Drive root's path rule, else P2. A view, the copy, or the thumbnail "
           "would have opened a member's discipline outside the private view.",
           "The level was set on the reference, which the client shows, not where the server decides it; "
           "drive_copies.level_of read only the holdings and the templates.",
           "drive_copies.level_of holds every Drive id a saved hearing names (zoom/hearings.json, noticeDoc) at P3, "
           "read once a version of the file; while the hearings cannot be read, no Drive file is P0. The evidence's "
           "level, the copy's path rule, the thumbnail, and the view all ask it, and the copy's documents are held back "
           "outside the private view.",
           Status.FIXED, guards=("jason.tasks.drive_copies.hearing_ids / level_of",
                                 "tests/test_drive_copies.py (a hearing's Doc refused outside the private view, opened in it)"),
           docs=("docs/console/security-and-privacy.md (Built: levels a store's own flag decides)",)),
    Lesson("executive-break-transcript-p1", date(2026, 10, 3), (Area.DOCUMENTS, Area.GOVERNING),
           "A board call that went on into executive session after a break kept its transcript and audio at P1, and "
           "Minutes review shows the transcript inline on mount beside the draft.",
           "access._zoom_meeting judged a meeting folder by the Zoom index's kind and confidential flag only; the "
           "catalog's own signal (the words that say so, the adjournment its transcript shows) was not asked.",
           "A listed meeting's transcript, audio, video, chat, and summary are P3 when access.executive_signal finds "
           "the catalog's signal (confidential_mentions or executive_break), P2 when it cannot be read (never P1), "
           "else P1; its attendance stays P1. The signal is read once a version of its files.",
           Status.FIXED, guards=("jason.web.access.executive_signal / _zoom_meeting",
                                 "tests/test_web_access.py (a flagged call P3, an open one P1, an unreadable signal P2)"),
           docs=("docs/console/security-and-privacy.md (Built: levels a store's own flag decides)",)),
    Lesson("credential-mail-served", date(2026, 10, 3), (Area.DOCUMENTS,),
           "A scanned letter the mail sort flags as carrying a credential (a PIN mailer) was P2 like any other letter: "
           "its scan, envelope, and text opened for any office that opens P2, and the mail screens linked it.",
           "mail/* was one path rule; the sort's credential flag kept the letter out of the shared catalogs "
           "(mail.shareable) but nothing told the console.",
           "A per-letter hook on mail/* reads mail/items.json (once a version): a letter carrying a credential is P4, "
           "never served; another association's mail is P3; an unreadable sort is P3. The mail loaders emit no "
           "reference for a P4 letter and say \"Held: this letter holds a credential; it opens in no screen\".",
           Status.FIXED, guards=("jason.web.access._mail_letter", "jason.tasks.mail.scan_ref / scan_fields",
                                 "tests/test_web_access.py (P4 and P3 letters; /api/file refuses P4)",
                                 "tests/test_mail_docrefs.py (no reference, Held)"),
           docs=("docs/console/security-and-privacy.md (Built: levels a store's own flag decides)",)),
    Lesson("executive-session-in-open-log", date(2026, 10, 4), (Area.GOVERNING, Area.DOCUMENTS),
           "In the meeting room, entries, motions, and roll calls made during executive session went into the "
           "room's open log; the draft minutes letter copied that log, decide recorded the decision as \"open "
           "session\", and the general note fell back to the item's title.",
           "The room kept one record with an executive flag on its entries. Nothing tied the record to Civil Code "
           "4935(e) (\"shall be generally noted in the minutes of the immediately following meeting that is open "
           "to the entire membership\") or to the open minutes of 4950(a).",
           "Executive session now writes a separate record, meetings/room-<date>-executive.json, at P3 and shown "
           "only in the private view. The open log gets only the general note, from the item's ExecutiveSubject, "
           "never its title; an item with no subject cannot go into executive session. Decisions made there are "
           "marked executive and kept out of the open views, the dock, and the minutes draft. "
           "`python -m jason.tasks.meeting_room --check-executive all` counts executive entries in open logs.",
           Status.FIXED, guards=("tests/test_meeting_room_executive.py",
                                 "ui/src/components/meetingstage.test.tsx (HostPanel executive tests)",
                                 "ui/src/views/meetingroom.test.tsx (the hold card)"),
           docs=("docs/console/screens/meetings-and-minutes.md", "docs/console/security-and-privacy.md"),
           notes=("Still open: the agenda Doc's executive subitems reach the minutes model as headings.",)),
    Lesson("owner-view-showed-delinquency", date(2026, 10, 4), (Area.DOCUMENTS, Area.GOVERNING),
           "The owner view's Overview rendered the board's digest, with owners in default and liens on current "
           "owners, and its nav included Records (CIV 5200), which listed the liens the association placed. Other "
           "owner screens got the board's loaders and hid rows only in the browser: other members' records "
           "requests, policy numbers and claims, the reserve ledger, call titles and checks, and the meeting "
           "room's owner roster and executive matters. The live meeting screen never got its audience, so owners "
           "saw the host panel, and the Ask drawer offered owners the board's questions and the library.",
           "The owner view was a filter on which screens show, plus client-side hiding. Nothing on the server "
           "knew a read came from the owner view, and each owner screen reused a board loader.",
           "Every read in the owner view carries view=owner, and the server answers it only from OWNER_SOURCES "
           "(jason.web.extra.owner_view): each copies an allowlist of what a member is entitled to under CIV 4925, "
           "4950, 5300, 5565/5570, 5200-5215, and 4041. Any other read is refused with 403. The owner Overview is "
           "the member digest (/api/owner-digest); Records (CIV 5200) and the dock are board-only; an owner's "
           "records screen is the request form; liens the association placed are held back on the server outside "
           "the private view.",
           Status.FIXED, guards=("ui/src/ownerScreens.json (each owner screen's sources)",
                                 "tests/test_web_owner_view.py (no delinquent owner, lien, hearing, or executive "
                                 "item in any owner source; OWNER_SOURCES equals the JSON)",
                                 "ui/src/views/ownerview.test.tsx (each owner screen reads only its sources with "
                                 "view=owner and renders no board-only section)"),
           docs=("docs/console/security-and-privacy.md (Built: the server answers the owner view)",),
           notes=("Still open: the standalone #/meeting-room?audience=owner link does not carry view=owner.",)),
)


def lessons(community: object | None = None) -> tuple[Lesson, ...]:
    """The general lessons, then the community's own (``Community.lessons()``), if it keeps any."""
    own = getattr(community, "lessons", lambda: ())() if community is not None else ()
    return LESSONS + tuple(own)


def for_area(area: Area, community: object | None = None, *, open_only: bool = False) -> list[Lesson]:
    return [l for l in lessons(community) if l.applies_to(area) and (not open_only or l.status is not Status.FIXED)]


def lines(found: list[Lesson]) -> list[str]:
    """Lessons as Markdown list items: what happened, what changed, its status and guard."""
    out = []
    for l in found:
        guard = f" Guarded by: {'; '.join(l.guards)}." if l.guards else ""
        out.append(f"- **{l.key}** ({l.status.value}, {l.learned.isoformat()}): {l.what} {l.change}{guard}")
    return out


__all__ = ["Area", "LESSONS", "Lesson", "Status", "for_area", "lessons", "lines"]
