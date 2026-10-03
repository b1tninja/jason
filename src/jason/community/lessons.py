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
    Lesson("notice-labels-match-outline", OCT_2026, (Area.GOVERNING,),
           "Read for notice duties, the documents showed 52 untracked, though several already had a notice-clause row: "
           "the rows named sections the outline does not use ('(b) Due Process', '6.12 (payment plan)').",
           "A notice clause's section label is free text, matched against the outline's numbers and titles.",
           "A test checks each label a clause names by heading against its outline's numbers and titles. A free-text "
           "suffix after a valid number still passes, so that case is open.",
           Status.OPEN, guards=("tests/test_notice_catalog.py (labels are outline numbers or titles)",),
           docs=("docs/notices.md",)),
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
