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
