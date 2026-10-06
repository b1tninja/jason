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
    CONTRACTS = "contracts"              # vendor and manager agreements: their terms, notices, and readings


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
           Status.FIXED,
           guards=("tests/test_response_inbox.py::test_confirm_makes_the_answers_a_submission_becomes_with_a_persons_corrections",
                   "tests/test_response_inbox.py::test_keyed_answers_make_the_same_writes_as_a_payhoa_submission_with_the_same_answers",
                   "tests/test_response_inbox.py::test_an_arrival_is_recorded_when_the_writes_it_calls_for_are_made",
                   "tests/test_responses_command.py::test_a_confirmed_answer_plans_the_same_writes_as_a_payhoa_answer_with_the_same_answers",
                   "tests/test_mcp_response_inbox.py (the board's new_responses and response tools read the inbox from disk)"),
           docs=(RUNBOOK, "docs/responses-design.md"),
           notes=("The path is not owner-info --returns DIR. `jason responses --check` keeps each arrival (PayHOA, Gmail, "
                  "the mail service, a Google Form) in data/responses; --read reads its attachments; a person's --confirm "
                  "makes the same FormAnswers a PayHOA submission becomes, which `jason owner-info --apply` plans under the "
                  "same rules and trust levels, dry run first. A reading is evidence; only the confirmation is an answer.",)),
    Lesson("form-return-found-by-searching-the-mailbox", date(2026, 10, 5), (Area.OWNER_INFO, Area.FORMS, Area.EMAIL),
           "An owner's filled form reached the association's shared mailbox as a reply, and a scanned return came through "
           "PostScanMail, and nothing told jason. A person found the reply by searching Gmail for the sender's address, read "
           "the scan by eye, and keyed the answers by hand.",
           "jason asked one place, PayHOA's submissions, whether anyone had answered, and the request can be answered four "
           "ways. Nothing looked at the others, so an answer outside PayHOA was found only when a person went looking.",
           "One inbox over every way an owner can answer: a check reads Gmail headers and attachment names, the mail "
           "service's scans on disk, the Google Form's saved responses, and PayHOA's submissions, keeps what is new, and "
           "stores no personal address. The board's tools say what the last check kept and how old it is; the scheduler "
           "runs the check by the registry's cadences once a person adopts them.",
           Status.FIXED,
           guards=("jason responses --check (jason.tasks.response_inbox.check)",
                   "tests/test_response_inbox.py::test_gmail_candidates_follow_the_design_and_keep_no_address",
                   "tests/test_response_inbox.py::test_a_check_keeps_only_new_arrivals_dedupes_and_overlaps_a_day",
                   "tests/test_mcp_response_inbox.py::test_new_responses_lists_each_state_with_the_channels_last_check_and_its_age",
                   "tests/test_integrations.py::test_the_response_checks_are_proposed_cadences_in_the_right_lanes"),
           docs=("docs/responses-design.md",)),
    Lesson("payhoa-submission-list-row-shape-unconfirmed", date(2026, 10, 5), (Area.OWNER_INFO, Area.FORMS),
           "The PayHOA channel of the responses check reads a submission's time and member from the list row and the "
           "detail, and no live look at the shape of either has been made for this form.",
           "PayhoaChannel was written from the client's method names and the stored submissions, and reads `createdAt`, "
           "`membershipId`, and the member's name tolerantly (several places, a missing one is a name 'an owner signed in "
           "to PayHOA' and no time). A row whose time sits under another key would be kept with no date, and the window "
           "would not apply to it.",
           "A person runs `jason responses --check --channel payhoa` against the live form once and compares what it kept "
           "(date, name, unit) with the submissions in PayHOA; then pin the shape in a test with the keys PayHOA really "
           "uses and drop the keys it does not.",
           Status.OPEN, docs=("docs/responses-design.md",)),
    Lesson("new-module-name-already-taken", date(2026, 10, 5), (Area.REPOSITORY,),
           "A new module was written to a path a tracked file already held, and the Write tool replaced that file without "
           "a word; git restored it. Two modules for members' requests (`jason.tasks.responses`, "
           "`jason.community.responses`) already own the name `responses`.",
           "Write silently replaces an existing file, and much of src/ is untracked, so a replaced file may not be "
           "recoverable. The name `responses` sounded free because a different feature uses it.",
           "Before writing a new file, list its exact path and read git status for it; a taken name gets another "
           "(`response_inbox`). A file that is untracked has no copy in git: read it first.",
           Status.FIXED,
           guards=("procedure check-in: list and git status the exact path before writing a new file",
                   "jason.tasks.response_inbox and jason.community.response_inbox are the names; the members' clocks keep "
                   "`responses`"),
           docs=("docs/responses-design.md (Step 1, as built: module names)",)),
    Lesson("a-hook-on-results-is-silent-when-the-step-is-skipped", date(2026, 10, 5), (Area.OWNER_INFO,),
           "An answer a person confirmed from an email stayed `keyed` after `owner-info --apply` found PayHOA already "
           "showed everything it calls for: with no writes, nothing ran the observer that marks an arrival recorded.",
           "The observer listened to each write's result, and a plan with no writes calls no result.",
           "The apply command tells the observer when the plan is empty (`plan.observer.heard([])`), and names the "
           "person with --by.",
           Status.FIXED,
           guards=("tests/test_responses_command.py::test_a_plan_with_no_writes_marks_the_arrival_recorded",),
           docs=("docs/responses-design.md (Step 2, as built)",)),
    Lesson("reading-keeps-no-membership-id", date(2026, 10, 5), (Area.OWNER_INFO,),
           "A returned form's reading named the owner and unit the sender matched but kept no membership id, so "
           "`jason responses --read` and the `response` tool compared a printed reference's copy with the owner by name "
           "and unit only.",
           "The reading was built before the sent-copy catalog was used to identify an arrival.",
           "The reading keeps the owner's membership id and unit id, and `read` now looks the copy up in the sent-copy "
           "catalog through `tasks.recognize` and keeps it (owner and unit as sent, membership id, channel, the rung that "
           "found it), compared by id with the owner the sender matched and with the unit written on the form; a "
           "disagreement is a plain note. The command and the tool read those fields.",
           Status.FIXED,
           guards=("tests/test_response_recognition.py::test_a_reading_records_the_copy_as_sent_and_compares_it_with_the_sender_and_the_page",
                   "tests/test_response_recognition.py::test_a_copy_sent_to_another_unit_and_owner_is_noted_plainly",
                   "tasks.recognize.compare: ids first, a name only for an older reading (response_inbox.copy_of)"),
           docs=("docs/arrivals-design.md", "docs/responses-design.md (Step 1b, as built)")),
    Lesson("cli-doc-behind-the-parser", date(2026, 10, 5), (Area.REPOSITORY,),
           "docs/cli.md lists fewer commands than the parser has, because sessions add their command's section by "
           "hand while others' commands are not yet in the file.",
           "The generated file is edited in many hands and regenerated by no one.",
           "Run scripts/gen_cli_docs.py once the shared files settle, and make the commit hook or a test compare the "
           "documented count with the parser's.",
           Status.OPEN, docs=("docs/cli.md",)),
    Lesson("recognition-covers-only-the-marker-and-the-layout", date(2026, 10, 5), (Area.FORMS, Area.OWNER_INFO),
           "A returned scan that lost its printed reference is only a Candidate by layout, at low sureness, and a copy "
           "sent by mail is known only by its campaign, so the unit and owner then come only from the address written "
           "on the page.",
           "The reference is the only thing that names one copy, and a poor scan can lose it (2 of 20 simulated scans "
           "did).",
           "A rung that matches a sent copy's filled-in fingerprints (owner_prefill.fingerprints, already in the "
           "catalog) would name the copy when the marker is lost.",
           Status.OPEN, docs=("docs/arrivals-design.md (Recognition is the crux)",)),
    Lesson("catalog-has-no-mailing-recipients", date(2026, 10, 5), (Area.FORMS, Area.MAILROOM),
           "The sent-copy catalog records a mailing's campaign marker but not whom it reached, so `jason responses "
           "--outstanding` cannot say which mailed owners are outstanding.",
           "A mailed letter's marker is the same on every copy, and the recipients live in the batch store.",
           "Record the recipients' membership ids at send time and read them for the outstanding list.",
           Status.OPEN, docs=("docs/responses-design.md",)),
    Lesson("answered-is-matched-by-unit-label", date(2026, 10, 5), (Area.FORMS, Area.OWNER_INFO),
           "A PayHOA submission or a Google Form response carries only a unit title, so \"answered\" falls back to a "
           "label comparison (house number and the first street word); a renamed or oddly formatted label can leave a "
           "copy outstanding that was answered.",
           "Those channels do not carry the unit id the way a sent copy does.",
           "tasks.recognize.same_place compares conservatively; a unit id on the submission would end the fallback.",
           Status.OPEN, guards=("tests/test_response_outstanding.py",)),
    Lesson("request-seeds-miss-a-request-stated-by-who-acts", date(2026, 10, 5), (Area.DOCUMENTS, Area.GOVERNING),
           "A list of the phrases a statute is expected to use to create a request missed one stated by who acts rather "
           "than by what is asked: CIV 5210 (records) was missed until a pattern for a member who properly requests "
           "was added, and sections for a hearing, alternative dispute resolution, the delivery preferences, resale "
           "documents, elections, and a member's right to speak still produce no span.",
           "Statutes state a right in many forms, and a pattern list is built from the forms already seen.",
           "A person reads the sections the standard-forms inventory names that the seed did not find; the "
           "rediscovery check in docs/standard-forms.md lists them.",
           Status.OPEN, docs=("docs/standard-forms.md (Running it)",)),
    Lesson("records-form-recites-a-moved-subdivision", date(2026, 10, 5), (Area.FORMS, Area.DOCUMENTS),
           "The request to inspect records recites Civil Code 5205(e) for the charge for copying and redaction; in the "
           "text on disk (e) is individual delivery, the copying and mailing cost is (f), and the hourly redaction "
           "charge for enhanced records is (g). The form also lacks the written designation of a representative "
           "(5205(b)), the member's agreement to the cost before copying, and the request for a withheld record.",
           "The form paraphrased a subdivision, and the section was amended and its subdivisions moved.",
           "Forms recite statutes by key and the form library's check reads each recital from the shelf: a subdivision "
           "that is missing, or a section whose words changed after the form's as-of day, fails the check and names the "
           "form. The records definition cites 5205(f) and (g). Still open: the form lacks the designation, the agreement "
           "to the cost, and the withheld-record request (jason form-library --check lists them as deferred).",
           Status.FIXED,
           guards=("form_library.check.check_recitals",
                   "tests/test_form_library.py::test_the_shipped_forms_and_the_profile_pass_every_check_on_a_shelf_that_holds_"
                   "their_recitals", "jason form-library --check"),
           docs=("docs/form-templates/records-request.md", "docs/form-library-design.md")),
    Lesson("moved-forms-still-miss-required-content", date(2026, 10, 5), (Area.FORMS,),
           "The request to inspect records and the request to meet and confer, moved into the form library, still do not "
           "carry ten items the sections require (the representative's designation, the agreement to the cost, the "
           "redaction estimate, the withholding explanation; that the association shall not refuse, no fee, assistance at "
           "the member's cost, the maximum time, the signed and ratified agreement).",
           "The first step moved the forms unchanged so that existing returns and markers keep working.",
           "Build step 2 of the form library closes them; `jason form-library --check` lists each as deferred until then.",
           Status.OPEN, docs=("docs/form-library-design.md", "docs/form-templates/records-request.md",
                              "docs/form-templates/idr-request.md")),
    Lesson("packet-builds-left-iterations-in-drive", date(2026, 10, 5), (Area.DOCUMENTS, Area.OWNER_INFO),
           "Building the owner information packet while it was being developed left fifteen earlier copies of its form "
           "in Drive, named alike; only the template and the one filled copy the sent packet came from match what was "
           "mailed.",
           "Each build made a new copy until the build learned to refresh its filled copy in place.",
           "The build finds its filled copy by name and refreshes it in place (tasks/packets), and on October 5, 2026 the "
           "fifteen earlier copies, the unused Google Form, and an older duplicate email draft were moved to Drive's "
           "trash on the administrator's word (listed in data/drive/trashed-2026-10-05.jsonl); the template and the "
           "mailed filled copy were kept. The annual disclosures' earlier copies are still there.",
           Status.FIXED, guards=("tasks/packets: the filled copy is found by name and refreshed in place",
                                 "GoogleDrive.trash (tests/test_google_drive.py)"),
           docs=("docs/packets.md",)),
    Lesson("idr-form-requires-an-email", date(2026, 10, 5), (Area.FORMS,),
           "The request to meet and confer requires an email address, which the association's form standard allows "
           "only when the request is for delivery by email, and it lacks what the section says the process carries "
           "(that the association shall not refuse, that no fee is charged, the written agreement and its ratification, "
           "assistance by another person).",
           "The form was written for convenience before the standard stated what a form may require.",
           "The library's definition drops the required email and carries the section's items.",
           Status.OPEN, docs=("docs/form-templates/idr-request.md",)),
    Lesson("no-request-kind-for-a-protest", date(2026, 10, 5), (Area.FORMS, Area.ENFORCEMENT),
           "A member's payment under protest of a disputed charge (Civil Code 5658) is not a request kind, and the "
           "response rules have no row for an internal dispute resolution request, so neither gets a clock or a handler.",
           "The kinds were taken from the requests seen, and the Act gives no association duty for a protest.",
           "Add the kind with its proposed-policy clocks once the board adopts them; until then the form is designed, "
           "not offered.",
           Status.DECISION, docs=("docs/form-templates/disputed-charge.md",)),
    Lesson("ev-insurance-text-changed-on-2026-01-01", date(2026, 10, 5), (Area.FORMS, Area.GOVERNING),
           "Civil Code 4745(f)(1)(C) was amended (SB 770, operative 2026-01-01): the owner's certificate of insurance "
           "no longer must name the association as an additional insured \"in the amount set forth in paragraph (3)\"; "
           "it is now \"as required by paragraph (3)\", which names no amount. A form or a profile that still asks for an "
           "additional-insured endorsement or a coverage amount rests on the old text.",
           "The shelf keeps the earlier text in its history, and a form written before the amendment recited it.",
           "The electric vehicle form does not ask for either; the library's recital check and the law-review procedure "
           "find an amended citation. A profile's own EV rules are read against the new text.",
           Status.FIXED,
           guards=("tests/test_form_library_changes.py::test_the_charger_form_asks_for_no_additional_insured_endorsement_"
                   "and_no_coverage_amount",),
           docs=("docs/form-templates/ev-charger.md",)),
    Lesson("response-first-steps-misstate-two-clocks", date(2026, 10, 5), (Area.FORMS, Area.GOVERNING),
           "The response rules' first step for a solar application says a complete application not denied in writing "
           "within 45 days; Civil Code 714(e)(2)(B) counts from the date of receipt and does not say complete. The "
           "electric vehicle first step omits the exception for a reasonable request for more information.",
           "A first step was worded from a summary of the section, not from its words.",
           "Both first steps are reworded from the section's words (from the date of receipt; the reasonable-request "
           "exception), and the notice catalog gained the reconsideration answer and the disaster rebuild review and "
           "appeal rows.",
           Status.FIXED, guards=("tests/test_form_library_changes.py::test_the_reworded_first_steps_count_from_receipt_and_say_nothing_of_a_"
                   "complete_application",),
           docs=("docs/form-templates/solar.md", "docs/form-templates/ev-charger.md")),
    Lesson("a-long-signature-label-loses-the-date-field", date(2026, 10, 5), (Area.FORMS,),
           "A signature label longer than about one line wraps and pushes the date onto the next line, so the fillable "
           "PDF is made with no date field.",
           "The fillable layout places one field a writing line, and a wrapped label takes two.",
           "The labels on the reconsideration, protected-use, and request-for-resolution forms are short; the render "
           "test asserts the last two fields are the signature and the date.",
           Status.FIXED, guards=("tests/test_form_library_records_money.py", "tests/test_form_library_changes.py")),
    Lesson("a-flat-required-flag-cannot-say-required-only-if", date(2026, 10, 5), (Area.FORMS,),
           "A question's `required` is one flag, so an email that is needed only when the member chooses email delivery "
           "is either required (which the standard forbids) or invisible.",
           "The form model has no condition on a requirement.",
           "The conditional questions are optional and say \"only if ...\" in their help, and a test checks that no email or "
           "phone is ever required. A template-level `required_if` is the board's and the administrator's decision.",
           Status.DECISION, guards=("tests/test_form_library_records_money.py::"
                                    "test_no_email_or_phone_is_ever_required_and_the_question_says_when_it_is_needed",)),
    Lesson("statutory-sentences-are-checked-by-a-script-nobody-keeps", date(2026, 10, 5), (Area.FORMS, Area.DOCUMENTS),
           "The sentences a form must print word for word (the notice in the alternative dispute resolution request, the "
           "charges form's sentences, the membership list statement) are compared with the shelf only by a script that "
           "is not in the repository; the recital check proves only that a subdivision exists. Statutes print curly "
           "apostrophes.",
           "The check was written for citations, and the exact words were verified once by hand.",
           "A check that compares each printed statutory sentence with the shelf's words, whitespace-normalized, belongs "
           "in the form library's checks.",
           Status.OPEN, docs=("docs/form-library-design.md (What the library checks)",)),
    Lesson("forms-not-offered-until-the-board-adopts-its-times", date(2026, 10, 5), (Area.FORMS, Area.GOVERNING),
           "The architectural application, the reconsideration request, the electric vehicle and solar applications, and "
           "the protected-use application are not offered by the real profile until it gives the procedure's maximum "
           "times to answer (Civil Code 4765(a)(1)), and the resale documents and payment plan forms wait for a fee "
           "schedule and the payment plan standards.",
           "The law makes the association state the times and standards, and the board has not adopted them here.",
           "The board adopts the times (a rule on subject 4355(a)(6), 28 days' notice under 4360(a)) and the standards; "
           "the profile then fills the slots and the forms are offered (`jason form-library --check` names each slot).",
           Status.DECISION, docs=("docs/form-templates/architectural-application.md", "docs/form-templates/payment-plan.md")),
    Lesson("overstated-the-law-in-an-inventory-row", date(2026, 10, 5), (Area.FORMS, Area.GOVERNING),
           "The standard-forms inventory said a document's approval requirement is void where it bars a protected use; "
           "the sections void a provision or condition that prohibits or unreasonably restricts the use, and expressly "
           "allow reasonable application requirements.",
           "A table row compressed several sections into one clause, and nobody read the sections it summarized.",
           "The rows now say what the sections say; each form's design page recites the sections and labels a reading. "
           "No check reads a table row against the sections it cites, so a person does.",
           Status.OPEN, docs=("docs/standard-forms.md", "docs/form-templates.md")),
    Lesson("owner-form-short-of-the-forms-standard", date(2026, 10, 5), (Area.FORMS, Area.OWNER_INFO),
           "The built owner information form has no recitals by token, no statement of the clocks to the member, no "
           "acknowledgment at receipt, and no required-content checklist; it omits the statute's fourth occupancy state "
           "(undeveloped land), has no way to remove a second address, and asks a representative's and a manager's phone "
           "numbers where docs/forms.md says no phones are asked.",
           "It was built before the standard in docs/form-templates.md stated what a form carries.",
           "The next cycle's definition moves into the form library against the checklist "
           "(docs/form-templates/owner-information.md lists each item).",
           Status.OPEN, docs=("docs/form-templates/owner-information.md",)),
    Lesson("reference-made-before-a-handler-was-chosen", date(2026, 10, 5), (Area.FORMS, Area.OWNER_INFO),
           "The owner information cycle sent emailed and mailed copies, each with a reference, before anything recorded "
           "which handler would process the answers, so a reference could exist for a form nobody could process.",
           "The reference was made at send time, and a form's handler was a fact of the code, not a choice made when "
           "the form was made.",
           "A person opens a campaign (`jason campaigns --open`) and chooses the handler when the form is made; every "
           "generator calls `campaigns.gate` first and refuses with the reason; each sent copy's entry points at its "
           "campaign and the form version used.",
           Status.FIXED, guards=("tests/test_campaigns.py",), docs=("docs/arrivals-design.md",)),
    Lesson("the-gate-needs-the-unfiltered-form-list", date(2026, 10, 5), (Area.FORMS,),
           "`Community.forms()` leaves out a form with no handler, so a gate built on it could never let a person choose "
           "a general form's handler when opening its campaign.",
           "forms() answers \"what may be made now\", and the gate must ask \"what could be made once a handler is "
           "chosen\".",
           "The gate resolves through `form_library.resolve`, not `forms()`; a refusal names the missing handler or slot.",
           Status.FIXED, guards=("tests/test_campaigns.py",)),
    Lesson("campaign-gate-leaves-forms-pdf-and-payhoa-open", date(2026, 10, 5), (Area.FORMS,),
           "The campaign gate covers the three places a marker is stamped today (the emailed and mailed owner "
           "information copies and the emailed pre-fill); `jason forms --pdf` and `--payhoa` are not gated, and the two "
           "general handlers (collect-only, sheet-register) are named but have no code.",
           "Those commands and handlers belong to the forms being added to the library.",
           "Gate `drafts_forms.py` once the library's forms are in, and build the two general handlers; until then a "
           "campaign can name an unbuilt handler.",
           Status.OPEN, docs=("docs/arrivals-design.md (the handler is chosen when the form is made)",)),
    Lesson("a-delivery-change-would-add-the-years-answered-tag", date(2026, 10, 5), (Area.OWNER_INFO, Area.FORMS),
           "The delivery-change and secondary-address forms use the owner information handler, but the cycle reads only "
           "the annual form's PayHOA submissions, and `member_preferences.match` treats any answer sent during the cycle "
           "as the annual answer, so a delivery-change return would add the year's \"answered\" tag.",
           "The handler and the matcher were written when the annual form was the only form that set delivery.",
           "Read those forms' returns into the plan and keep the year's \"answered\" tag off them; until then the test "
           "compares the delivery tags only.",
           Status.OPEN, docs=("docs/form-templates/delivery-change.md",)),
    Lesson("an-accommodation-request-needs-a-restricted-store", date(2026, 10, 5), (Area.FORMS, Area.DOCUMENTS),
           "An accommodation request's text must be kept where only the people who decide it can read it (level P4), and "
           "a form template has no restricted-store flag, so the form is not offered by Google Form and waits on a "
           "counsel slot.",
           "No form so far held what could disclose a disability.",
           "Add the flag to the template and keep the returns in the restricted store; until then the form is not "
           "offered.",
           Status.OPEN, docs=("docs/form-templates/accommodation-request.md",)),
    Lesson("forms-wait-for-the-profile-to-name-its-people-and-dates", date(2026, 10, 5), (Area.FORMS, Area.GOVERNING),
           "The delivery, nomination, meeting-comment, and accommodation forms are not offered until the profile gives "
           "the designated person (Civil Code 4035(a)), the election's nomination deadline and inspector, the time limit "
           "to speak and where the agenda is posted, and who reads an accommodation request first.",
           "A form with an unfilled slot is not made, so a form never goes out with a blank where the law needs a name or "
           "a date.",
           "The board supplies each, and the profile fills the slot; `jason form-library --check` names each slot.",
           Status.DECISION, docs=("docs/form-templates/README.md",)),
    Lesson("a-joined-group-is-a-lead", date(2026, 10, 5), (Area.DOCUMENTS, Area.GOVERNING),
           "A document span joined to a statute by shared subject words can be about something else.",
           "Shared terms are weaker evidence than a shared citation.",
           "Each join keeps its reason, and only a citation, a shared request kind, or three shared top terms joins.",
           Status.FIXED, guards=("tests/test_form_discovery.py::test_a_pair_with_nothing_in_common_is_not_grouped",)),
    Lesson("a-reseed-must-not-overwrite-a-persons-act", date(2026, 10, 5), (Area.DOCUMENTS,),
           "Running the discovery seeds again could replace a candidate a person had confirmed, held, or dropped.",
           "The seeds write the whole candidate list.",
           "A re-seed keeps a person's status and note, and drops only an unread candidate no longer found.",
           Status.FIXED,
           guards=("tests/test_form_discovery.py::test_a_reseed_keeps_a_persons_status_and_note_and_drops_a_stale_unread_candidate",)),
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
    Lesson("real-word-misread-needs-the-page", date(2026, 10, 5), (Area.DOCUMENTS, Area.GOVERNING),
           "A word misread as another real word (\"ot\" for \"of\") passed every word list. A bigram channel flagged it "
           "but could not choose between the twins, and the local model with no image chose right 11 times in 63.",
           "A word list sees only non-words, and a language model with no image judges how a sentence reads, not "
           "what the page printed.",
           "The noisy channel only flags a real word (Options.real_words, at a posterior of 0.95); the word is sent "
           "to the page's crop (route_real), and the crop reading is taken only when it is one a crop can give. "
           "Measured: the crop fixed 47 of 63 on the certified copy and 161 of 218 at 85 dpi, with no right word "
           "changed.",
           Status.FIXED, guards=("ocr_correct.Options.real_words", "tasks.ocr_correct.routed",
                                 "tasks.ocr_correct.usable_reading", "tests/test_ocr_routing.py"),
           docs=("docs/ocr-correction.md",),
           notes=("real-words stays an option off by default: below 0.95 it changes words the copy kept.",)),
    Lesson("one-edit-candidates-miss-two-glyph-misreads", date(2026, 10, 5), (Area.DOCUMENTS,),
           "The candidate rules asked for one edit, so a word read two or three letters wrong (\"tJnit\") had no right "
           "candidate: 69% of non-words and 44% of two-glyph misreads on the certified copy had theirs listed. A "
           "model shown the crop with candidates did worse than the crop read freely.",
           "Any chooser is bounded by its candidates; a list cut too short makes a confident wrong pick.",
           "A vocabulary search within three edits, scored by a confusion channel learned from aligned readings and "
           "rendered statutes, lifts the listed share to 94% and 80%. The page's crop is read without candidates, and "
           "the vision chooser is kept out of the default route.",
           Status.FIXED, guards=("ocr_vocab.search", "ocr_channel.learn", "jason intake --scan --vision-route suspects",
                                 "tests/test_ocr_channel.py"),
           docs=("docs/ocr-correction.md",)),
    Lesson("misread-glyph-sets-the-case", date(2026, 10, 5), (Area.DOCUMENTS,),
           "A correction copied the misread glyph's capital onto the word (\"Lhe\" in mid-sentence became \"The\"), and "
           "a defined term such as \"Unit\" was never a term, because the term list left out every word the general "
           "list knows.",
           "The case of a misread letter says nothing about the printed word's case.",
           "case_for keeps the token's case when its first letter was read right, and otherwise takes it from the "
           "sentence and the document's own terms (document_term_forms: a word capitalized mid-sentence often enough). "
           "Recomputing the case every time lost 17 right words to fix 4.",
           Status.FIXED, guards=("ocr_correct.case_for", "lexicon.document_term_forms", "tests/test_ocr_channel.py"),
           docs=("docs/ocr-correction.md",)),
    Lesson("cleaning-every-page-adds-errors", date(2026, 10, 5), (Area.DOCUMENTS,),
           "Binarizing a scan before Tesseract (Otsu, Sauvola, Niblack) read worse than the gray page on every clean set "
           "measured (0.3 to 1.5 points of word error), and so did tilting and smoothing every page.",
           "The recognizer reads gray; \"clean it up first\" changes pages that had nothing wrong.",
           "pdf_preflight cleans a page only for a measured defect (the auto variant: shading, dust, tilt of a degree "
           "or more), and a page with none comes back as the same array. Where a defect is present it takes the page "
           "from 25.79% to 2.02%, 7.33% to 1.88%, and 2.63% to 2.09%.",
           Status.FIXED, guards=("page_prep.auto_clean", "tests/test_pdf_preflight.py"),
           docs=("docs/pdf-preflight.md",)),
    Lesson("blank-page-test-drops-the-page-number", date(2026, 10, 5), (Area.DOCUMENTS,),
           "A blank-page test on ink alone would drop a page number or a stamp (an 8-point number is as faint as dust at "
           "100 dpi), and the orientation detector called upright forms and tables upside down at low confidence.",
           "Faintness and confidence are not evidence of emptiness or of rotation.",
           "A page is blank only with no ink worth a mark, no character-like piece, and no text; analysis runs at "
           "150 dpi; a rotation is believed only at confidence 5 or more. On the archive's labeled pages no page "
           "with anything on it was called blank.",
           Status.FIXED, guards=("pdf_preflight.OSD_MINIMUM", "tests/test_pdf_preflight.py"),
           docs=("docs/pdf-preflight.md",)),
    Lesson("english-prior-misjudges-a-text-layer", date(2026, 10, 5), (Area.DOCUMENTS,),
           "The share of words an English list does not know was taken as how badly a scanner's text layer was read, "
           "but tables, names and addresses inflate it: its correlation with the real error rate was 0.28.",
           "A word list measures strangeness, not error.",
           "The 3% re-read limit is only a place to start. A better predictor is Tesseract's word confidence (kept "
           "beside the reading by jason preflight --ocr) or agreement of two readings.",
           Status.OPEN, guards=(), docs=("docs/pdf-preflight.md",)),
    Lesson("scan-holding-several-documents-read-as-one", date(2026, 10, 5), (Area.DOCUMENTS, Area.GOVERNING),
           "A scan that holds several documents (or rules inside an owner's manual) was classified, dated and read as "
           "one, so its kind, date and parties were wrong for most pages.",
           "Ingestion treated a file as a document.",
           "jason segments reads the stack of open documents: continue, push an inner one (an exhibit, a report "
           "inside a packet), pop back to the outer one, or start a new one; a part belongs to the innermost segment "
           "and scoping_parts gives the scoping index its Part rows. It never splits the file. Measured on a labeled "
           "gold set: first pages precision 0.92 and recall 0.84 on the rules alone; 31 of 33 held-out nested "
           "documents found, but only 13 with the right parent, and the pop (an outer document resuming) was "
           "found on 0 of 2 real resume pages.",
           Status.OPEN, guards=("document_segments", "tests/test_document_segments.py", "tests/test_document_nesting.py"),
           docs=("docs/document-segmentation.md",),
           notes=("Open: resumes on real scans, over-nesting in long packets, passage-index segment columns, and a "
                  "segmentation call from jason ingest.",)),
    Lesson("vision-model-leans-to-new-document", date(2026, 10, 5), (Area.DOCUMENTS,),
           "The local vision model's yes or no on \"first page of a new document\" leaned to yes (held-out precision "
           "0.35), and its closed choice on the stack answered one letter for every move; shown the page before as "
           "well it was worse.",
           "A small model asked a closed question without the document's structure has a prior of its own.",
           "The rule pass decides; the model alone is a suggestion, and agreement with the rules is the likely tier "
           "(held-out precision 0.89, recall 0.67).",
           Status.FIXED, guards=("tests/test_document_segments.py", "docs/document-segmentation.md (measurements)"),
           docs=("docs/document-segmentation.md",)),
    Lesson("duplex-blank-backs-are-not-separators", date(2026, 10, 5), (Area.DOCUMENTS,),
           "A duplex scan has a blank back after every page, and pleading paper's margin numbers read as page numbers; "
           "both broke the separator and numbering cues.",
           "The cues assumed a blank page is a break and a number in the margin is a page.",
           "When more than a quarter of the pages are blank the blanks are backs, not separators, and margin line "
           "numbers are dropped from the page lines.",
           Status.FIXED, guards=("document_segments.DUPLEX", "PageInfo.numbered",
                                 "test_pleading_line_numbers_are_not_page_numbers"),
           docs=("docs/document-segmentation.md",)),
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
    Lesson("notice-window-has-two-edges", OCT_2026, (Area.CONTRACTS, Area.ONBOARDING),
           "A board's notice not to renew a management agreement went out by email two days after the window closed: "
           "the agreement asked for written notice at least 60 and no more than 120 days before the term's end.",
           "Nothing counted the window back from the term's end, or listed its opening and closing dates and the "
           "delivery each notice clause names.",
           "Before a term ends, read every notice clause (non-renewal, termination without cause, breach and cure), and "
           "write down its window, both edges, and the delivery it names; send inside the window by that delivery, "
           "and keep proof of delivery. Where a late notice may have renewed the term, the board asks counsel.",
           Status.OPEN, docs=("docs/contracts.md (Notice)",),
           notes=("To build: the contract model's auto-renewal finding also gives the window's first day when the "
                  "clause sets a longest notice, and the delivery the clause names.",)),
    Lesson("name-rule-files-others-agreements", OCT_2026, (Area.CONTRACTS, Area.DOCUMENTS, Area.ONBOARDING),
           "A lender's assignment of an investor-owner's property-management agreement, named \"... Assignment of "
           "Management Agreement\", sat among the association's management contracts; the name rule made it a contract.",
           "The library's chain stops at its first match, so a file's name decided its kind before its words were "
           "read, and nothing asked whether the association was a party.",
           "Ingest weighs each new file's kind before reading it: every phrase rule, the document's shape, the kind's "
           "own reader, and for an agreement whether the association is a party. A disagreement, or an agreement "
           "between others, is a CLASSIFY question that names what the paper reads as (a lease, an owner's rental "
           "papers, a lender's papers), and the file is held until a person answers.",
           Status.FIXED, guards=("jason.community.kind_analysis.analyze (association_is_party, THIRD_PARTY)",
                                 "jason.tasks.ingest.needs_kind (disagrees, weak)", "tests/test_kind_analysis.py"),
           docs=("docs/onboarding.md (Ingest, step 3)",)),
    Lesson("model-invents-contract-clauses", OCT_2026, (Area.CONTRACTS, Area.DOCUMENTS),
           "Asked to review a management agreement's terms, a 9B local model listed 20 clauses that are not in the "
           "contract, among them binding arbitration, a two-year claims limit, and a manager's indemnity, and flipped the "
           "grammar's deliverable and topic calls about as often wrongly as rightly.",
           "A small model completes a contract from what contracts usually say; asked for what was missed, it supplies "
           "the usual clauses.",
           "A model's term is kept only when its quote is in the text, and by default (--model-trust fill) the model "
           "only adds grounded terms and fills unstated parties; the grammar's fields stand. The trial is a row in "
           "docs/document-tools.md.",
           Status.FIXED, guards=("term_model._missed (find_quote)", "term_model.merge(trust='fill')",
                                 "tests/test_contract_terms.py::test_merge_keeps_only_grounded_terms",
                                 "tests/test_contract_terms.py::test_fill_keeps_the_grammars_reading_and_only_fills_and_adds"),
           docs=("docs/contracts.md (How far the model is trusted)", "docs/document-tools.md (Model trials)")),
    Lesson("gpu-lane-checked-the-default-model", OCT_2026, (Area.DOCUMENTS,),
           "The job queue's GPU lane checked whether jason's 27B model could load before every model job, so a job for "
           "a 9B model waited on the 27B's memory; it took jobs in order, so it could load one model, then another, then "
           "the first again; and it put a Bedrock job (off this machine) on the GPU lane.",
           "The lane knew a job was a GPU job, not which model it loads.",
           "Each GPU job's model is read from its flags (jobs.job_model); preflight checks that model; the lane takes a "
           "job whose model is loaded first; after a job the worker unloads models no queued job needs, keeping the "
           "shared model AnythingLLM also uses; a remote backend is not a GPU job.",
           Status.FIXED, guards=("jason.jobs.job_model / job_class (_remote)", "jason.jobs._claim(loaded=...)",
                                 "jason.jobs.release_idle", "tests/test_jobs.py"),
           docs=("docs/jobs.md (Running the queue)",)),
    Lesson("contract-role-labels-joined", OCT_2026, (Area.CONTRACTS, Area.DOCUMENTS),
           "An order form's role labels (\"CUSTOMER:\" above the customer's steps, the vendor's name above its own) were "
           "joined to the line above by unwrapping, so the customer's steps were read as no one's and its orders "
           "(\"Provide access ...\") not at all; and \"Example Holdings Inc. dba ... will complete the work\" lost its "
           "subject at \"Inc.\".",
           "Unwrapping kept a break only after a colon, not before a label; the \"will\" reader stopped its subject at any "
           "period.",
           "A role label keeps its own line; the lines under it take the label's party (contract_terms._role_terms); a "
           "dba, a parenthetical short form, and a label are the party's words (party_aliases); a company suffix's "
           "period does not end a subject.",
           Status.FIXED, guards=("jason.community.contract_terms.unwrap (label)", "contract_terms._role_terms",
                                 "contract_terms._alias_words", "tests/test_contract_fixtures.py::"
                                 "test_aliases_roles_and_topics"),
           docs=("docs/contracts.md (Parties and licenses)",)),
    Lesson("exemption-read-as-prohibition", OCT_2026, (Area.CONTRACTS,),
           "\"Manager shall not be obligated to attend meetings on weekends\" was read as a prohibition on the manager, "
           "and \"We are not responsible for any loss\" was not read at all, so a review missed what the vendor had "
           "released itself from.",
           "The grammar reads \"shall not\" as a prohibition and has no reading for a release from a duty.",
           "Exemptions are their own kind, read by the exemptions rows; a sentence that also binds stays a duty; a "
           "counterparty's release is a finding. Discretion and incorporated standards are read on every term too.",
           Status.FIXED, guards=("jason.community.contract_terms._qualify", "jason.community.exemptions",
                                 "tests/test_contract_fixtures.py::test_exemptions_discretion_standards_and_options"),
           docs=("docs/contracts.md (Parties and licenses)",)),
    Lesson("warranty-holder-unattributed", OCT_2026, (Area.CONTRACTS,),
           "On the library's contracts, every warranty read came back with no party: \"Example Co. warranties all work "
           "for one year\" (the noun used as the verb), \"All work performed is guaranteed for 7 years\" in the vendor's "
           "own form, and a holder named by the company's full name; and \"guarantees the pricing ... one year\" was read "
           "as a warranty.",
           "The warranty rows knew the verb and the noun but not the vendor's own usage; the party map knew the defined "
           "words but not the counterparty's name; a price lock shares the warranty's words.",
           "A row reads \"warranties all work\"; a holder matching the counterparty's name is the counterparty's; a "
           "passive warranty in the counterparty's own form is its, labeled as a reading; a price lock is refused. A "
           "noun warranty with no holder stays unattributed, since a manufacturer's warranty is not the vendor's.",
           Status.FIXED, guards=("jason.community.warranties (_PRICE_LOCK, the 'warranties' row)",
                                 "jason.tasks.contract_terms.warranties_in", "tests/test_warranties.py"),
           docs=("docs/contracts.md (Parties and licenses)",)),
    Lesson("contract-terms-console-encoding", OCT_2026, (Area.CONTRACTS,),
           "jason contract-terms --library stopped after reading every file because the Windows console could not print "
           "a contract's bullet (\"▪\"); the readings were saved, but the run reported an error.",
           "The report quotes the contract's own characters, and the console's code page has none for some of them.",
           "The command prints with errors replaced, so a character the console lacks shows as \"?\".",
           Status.FIXED, guards=("jason.commands.contract_terms.run (reconfigure)",)),
    Lesson("contract-fill-in-date-misread", OCT_2026, (Area.CONTRACTS, Area.DOCUMENTS),
           "The contract model read a management agreement's typed start date as blank, counted its term from the "
           "signing date, and gave it a 30-day notice; the agreement runs from the typed date and ends at the close "
           "of the calendar month after the month of notice.",
           "The PDF's text layer prints a typed fill-in on its own line, away from the blank it fills; the notice rules "
           "have no row for a notice that takes effect at the end of the following month.",
           "Read a lone date line near a blank as that blank's fill-in; add a notice row for end-of-following-month "
           "terminations; until then a person checks commencement-blank and term-end findings against the page.",
           Status.OPEN, docs=("docs/document-models/contracts.md", "docs/contracts.md (How jason reads a contract)")),
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
           notes=("The agenda Doc's executive subitems reaching the minutes model: lesson "
                  "agenda-executive-words-to-minutes-model.",)),
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
    Lesson("dock-counts-everyones", date(2026, 10, 4), (Area.DOCUMENTS, Area.GOVERNING),
           "The dock's red counts totaled every overdue deadline and task whoever was signed in, and the Approvals "
           "badge counted every requested letter. A free Ask question with no library hit became a task with no "
           "owner, while the screen said it went \"to the manager\".",
           "The dock predates the roster and sign-in, so its counts read the stores without a viewer. \"The "
           "manager\" was prose, never a routing rule, and calendar rows carried no owner though the profile's "
           "assignments cover them as obligation:<name>.",
           "Counts narrow to the viewer (the acting identity when an admin views as an office): deadlines by the "
           "duty owner's office, tasks by owner, letters by Officer.can_approve; with nobody signed in, or an admin "
           "with no office, they are labeled everyone's. Deadline rows carry their owners. Ask takes an optional "
           "duty and route() finds its owner from the profile's assignments; otherwise the task is unassigned, "
           "waiting for a person to take it, and it has no due date until the board sets a lead time.",
           Status.FIXED, guards=("tests/test_dock.py (counts by viewer; admin with no office; routing to the duty "
                                 "owner or unassigned; deadline owners)",
                                 "ui/src/components/dock.test.tsx (whose counts; routed question never the "
                                 "manager's)"),
           docs=("docs/web-ui.md (dock)", "docs/console/screens/today.md"),
           notes=("Still open: engine approvals are not counted; the Tasks \"Mine\" filter matches the name only; "
                  "generated calendar rows (insurance renewal, reserve-study visit) have no covering assignment.",)),
    Lesson("profile-old-name", date(2026, 10, 4), (Area.REPOSITORY,),
           "General code (about 300 references in 30 files, some 70 functions in mcp/county.py) still reached the "
           "profile through mystique(), the name from before profiles.",
           "The alias returns the same object, so nothing failed, and new code copied the old pattern.",
           "Callers use `from jason.community import community as active` and `active()`; the alias stays for "
           "callers outside src/jason. The last file, tasks/board_items.py, was converted the same day and the "
           "ratchet is empty.",
           Status.FIXED, guards=("tests/test_profile_access.py (an AST scan of src/jason; any new use fails)",)),
    Lesson("audit-log-masks-email-only", date(2026, 10, 4), (Area.DOCUMENTS, Area.REPOSITORY),
           "approvals.audit.mask replaced email addresses only, so a phone number or mailing address in a detail "
           "was written to the hash-chained audit.jsonl, masked only on the way out; a chained line cannot be "
           "cleaned later. The private view's stated reason had no address masking, and a sign-in refusal's why "
           "had none at all.",
           "The console's outbound mask added phones on top of the audit's email mask, and the write-time mask "
           "was never widened to match.",
           "audit.mask masks emails, phones, and street or PO-box addresses when a line is written; "
           "access.clean_reason and signin._log's why go through it; the console's outbound mask calls it with "
           "addresses=False, so what it shows is unchanged. Lines already written are left: rewriting them breaks "
           "the chain, a person's decision.",
           Status.FIXED, guards=("tests/test_audit_mask.py (contacts masked; ids, dates, cents, and paths survive; "
                                 "the chain verifies)",),
           docs=("docs/console/security-and-privacy.md (audit.jsonl)",)),
    Lesson("recusal-quorum-hardcoded", date(2026, 10, 4), (Area.GOVERNING,),
           "The meeting room and RollCall said a recused director \"counts toward the quorum and not toward the "
           "vote (Corp. Code 7233; CIV 5350)\" as if it were statute, fixed the vote at a majority of those present, "
           "and counted a recused director silently with no rule on file. The Decisions caveat said \"marked "
           "absent\", and DecisionCard dropped the recusal.",
           "A reading was written into general code under a statute that is not on disk (7233), and the bylaws are "
           "silent on the question.",
           "BoardRule carries vote_basis and interested_in_quorum, each with a RuleSource (a cited provision, "
           "recited from disk, or counsel's reading, labeled). board_rules() says \"not on file; ask counsel\" for "
           "what is missing. With no recusal rule, tally() works the vote both ways and holds a vote the two "
           "readings decide differently. A recusal is recorded as one (Decision.recused), never as absent.",
           Status.FIXED, guards=("tests/test_meeting_room.py (two readings held; rules not on file; rule on file "
                                 "decides)", "tests/test_decisions.py (a recusal is never absent)",
                                 "ui/src/components/meetingstage.test.tsx, decision.test.tsx"),
           docs=("docs/console/screens/meetings-and-minutes.md (The meeting room's rules)",),
           notes=("The recusal rule itself is the board's, on counsel's reading.",
                  "Corporations Code 7230-7238 is on the shelf since 2026-10-04 (lesson statute-miss-not-looked-up); "
                  "how 7234 applies through CIV 5350(a) is counsel's reading.")),
    Lesson("notice-date-ignored-documents", date(2026, 10, 4), (Area.GOVERNING,),
           "notice_date and several other modules always used four days, and a hybrid meeting's notice checklist "
           "and fields were cited to 4926.",
           "The statute's floor was taken for the whole rule (4920(b)(3): a longer period in the governing "
           "documents governs), and 4926's lines, for a meeting held entirely by teleconference, were applied to "
           "any remote format.",
           "board_items.notice_period() and Community.board_notice_period() (NoticePeriod, with executive_days only "
           "where the provision says so) feed every caller. A hybrid meeting gets 4090(b)'s lines; only a meeting "
           "held entirely by teleconference gets 4926's.",
           Status.FIXED, guards=("tests/test_board_items.py (a longer period in the documents)",
                                 "tests/test_agenda_plan.py (hybrid is 4090(b), not 4926; the notice line's source)",
                                 "ui agenda.test.tsx (the wizard's fields by format)",
                                 "tests/test_board_items.py::test_the_draft_follows_the_meeting_format",
                                 "tests/test_models_meetings.py::test_agenda_notice_follows_a_longer_period_in_the_documents"),
           notes=("Followed through 2026-10-04: jason board --agenda writes 4926's lines only for a meeting held "
                  "entirely by teleconference (--format, else the agenda plan's), and the models' notice checks use "
                  "notice_period().",)),
    Lesson("open-forum-default-limit", date(2026, 10, 4), (Area.GOVERNING,),
           "The meeting room defaulted open forum to 3 minutes a speaker, in the room record, the agenda row, the "
           "stage, and the script.",
           "A placeholder number stood in for a limit only the board establishes (CIV 4925(b)).",
           "The limit comes from Community.open_forum_limit() (SpeakingLimit) or one a person enters, recorded with "
           "who entered it. Otherwise the room says \"No limit on record; the board sets it (CIV 4925(b))\", with "
           "no clock, and a stored limit with no person behind it reads as none.",
           Status.FIXED, guards=("tests/test_meeting_room.py (no limit until the board sets one; the policy on "
                                 "file)", "ui/src/views/meetingroom.test.tsx (no \"3 minutes\")"),
           notes=("Adopting a limit is the board's decision.",)),
    Lesson("commit-swept-another-sessions-hunk", date(2026, 10, 4), (Area.REPOSITORY,),
           "A commit of a profile file took the whole working copy, with one line another session had not "
           "committed. That line named an enum member and a field that existed only in that session's uncommitted "
           "files, so a clean checkout of master could not import the profile. It was found only when a handoff "
           "was tested in a separate worktree.",
           "Several sessions share one working tree, and `git commit -- PATH` commits the working copy of PATH, "
           "every session's hunks in it. The tests ran in the shared tree, where the other session's files made "
           "the line work.",
           "The line was taken out of the committed copy (f6b719f) and left in the working tree. A commit of a "
           "file another session also edits stages only its own hunks (a temporary index from HEAD plus those "
           "hunks). Work brought in from elsewhere is tested in a worktree at HEAD, where only committed code "
           "runs, before it reaches the shared tree.",
           Status.OPEN,
           notes=("No check yet runs the tests on a clean checkout of each commit; until one does, this stays open.",)),
    Lesson("retrieval-tier-moved-unmeasured", date(2026, 10, 4), (Area.DOCUMENTS,),
           "Moving the context pack's law tier to the passage index changed what it chose: ranked by the index's "
           "passages, the law replaced a quarter of each task's sections at the median, and up to two thirds.",
           "A new store can rank the same text differently (passages against whole sections), and agreement with the "
           "old ranking says nothing about which is better without gold questions.",
           "Only the governing-documents tier moved, after a comparison of all eleven tasks showed the same sources "
           "in the same order. The law tier stays on its old ranking (context_pack.LAW_FROM_INDEX off) until the two "
           "are compared on data/retrieval/gold-law.json.",
           Status.FIXED, guards=("context_pack.LAW_FROM_INDEX = False", "tests/test_context_pack_index.py"),
           docs=("docs/applicability.md", "docs/rag-roadmap.md")),
    Lesson("stand-in-shape-hid-a-crash", date(2026, 10, 4), (Area.REPOSITORY,),
           "applicability.profile_facts called Community.region(), but region is a property on Community, so the "
           "function raised TypeError for every real profile. Its tests passed.",
           "The tests gave it a stand-in class whose region was a method. No test passed it a real Community.",
           "profile_facts reads the property. A function that takes a community is tested with a loaded profile as "
           "well as a stand-in, and a stand-in copies the member's shape (property or method) from Community.",
           Status.FIXED,
           guards=("tests/test_applicability.py: test_profile_facts_read_region_as_the_property_it_is_on_a_profile",
                   "tests/test_life_safety.py: test_the_active_profiles_systems_and_rows_hold_together"),
           docs=("docs/applicability.md",)),
    Lesson("reading-mixes-ingestion-and-review", date(2026, 10, 4), (Area.DOCUMENTS,),
           "A stored reading changed with the date, the profile, or another store, and nothing on the row said so: 943 "
           "of 980 findings came from a check that read more than the record, and three readers' fields were filled "
           "from a store or today during parse.",
           "One call parsed and checked, and a row recorded no digest of its text, no reader version, and no as-of date.",
           "Each row now records textSha, version, asOf, fieldsBasis, and each finding's basis (jason models --basis). "
           "The checks that need only the stored fields and a date are the as-of lens's, and the checks that read "
           "another document or store are the records lens's (jason.community.reviews), each made from the stored "
           "fields and kept in data/reviews/documents (jason models --as-of, --lens records); a records check's facts "
           "are gathered by a named function whose digest is in the review's key. No reader's own check reads a store "
           "or the date, a contract's parse reads no date, and an agenda's reads no store. Still to do: the fields a "
           "parse fills from the profile, and two checks no library file exercises.",
           Status.OPEN,
           guards=("tests/test_reviews.py", "tests/test_records_lens.py: a review is made again when its facts change, "
                   "and a row changes only with one"),
           docs=("docs/ingestion-and-review.md", "docs/document-models/README.md (What a reading records about its own making)")),
    Lesson("index-flag-per-file-not-per-catalog", date(2026, 10, 4), (Area.DOCUMENTS,),
           "The retired catalog sync decided confidentiality a catalog or a row at a time: a library file with one copy "
           "under a confidential folder was shared through its other copy, the property-history pages went to the "
           "shared workspace with owners' names, and a named case catalog would have opened every other catalog's held "
           "files.",
           "The flag was read from the copy in hand, not from the document, and a folder of pages was one source with "
           "one flag. Nothing asked what a file was when no rule placed it.",
           "The index sources (jason.tasks.index_sources) decide each file by rule rows and hold what no row answers "
           "for: the library by document with every copy's flag, the mail by MAIL_RULES (a credential is read from the "
           "text and never indexed), the reports by REPORT_RULES. Every build asks whether the library holds a file's "
           "bytes as confidential (library_holds). jason index --plan lists the counts before a build.",
           Status.FIXED, guards=("tests/test_index_sources.py", "jason index --plan", "passage_index.Scope.confidential_in"),
           docs=("docs/mcp.md (Confidential files in the index)", "docs/rag-roadmap.md (items 1 and 2)"),
           notes=("Open for a person: the held library kinds, the mail's never tier, and which report pages are open.",)),
    Lesson("manager-named-in-general-readers", date(2026, 10, 4), (Area.REPOSITORY,),
           "Six general readers recognized one association's former management companies by name in their patterns "
           "(an agenda's layout and preparer, an owner ledger's manager, a case report's, a statement's and a budget "
           "packet's preparer, a letterhead's office address), and one task searched Gmail for the manager's report by "
           "its subject line. The boundary check did not see them.",
           "The boundary's terms took vendors from the portals, developers, and banks, but not the sender directory, "
           "where the managers are listed.",
           "sources.manager_in and manager_name find a manager through the profile's senders of kind MANAGER, and a "
           "header's office address through its former managers' mail addresses; with none listed, no manager is "
           "named: a miss. The Gmail search is EvidencePlan.case_report_query. boundary.instance_terms now takes each "
           "manager's name and words, so a general pattern or document that names one fails the check; a reader "
           "named after the vendor whose layout it reads may be pointed to in a code span.",
           Status.FIXED, guards=("tests/test_profile.py: a manager is an instance term; a manager named in a general "
                                 "pattern is found", "python -m jason.community.boundary"),
           notes=("The directory's other counterparties joined the terms, and the law firm left "
                  "models/legal_collections.py: lesson counterparty-named-in-general-readers.",)),
    Lesson("reading-untied-from-the-words", date(2026, 10, 4), (Area.GOVERNING,),
           "A reading of a provision was kept as a sentence in a rule row or a doc, with nothing tying it to the words "
           "it read. When the statute was amended the sentence stayed, and nothing marked it for review.",
           "The body of authorities and the readings of it were one text: no digest of a section's words existed, and "
           "an export overwrote the words it replaced.",
           "A reading is a LawReading that names the digest of each provision's words; law_readings.status sets it "
           "aside as stale when the words change, and recite gives the words first, then each current reading labeled "
           "with whose it is. An export keeps the words it replaces (data/authorities/history). The store starts "
           "empty: a person confirms each reading before it becomes a row.",
           Status.FIXED, guards=("tests/test_law_readings.py", "law_readings.status", "jason readings --stale"),
           docs=("docs/law-readings.md", "docs/ingestion-and-review.md")),
    Lesson("lettered-and-doubled-sections-misread", date(2026, 10, 4), (Area.GOVERNING,),
           "authority_text could not read a section whose number ends in a letter (sixteen on the shelf), free text "
           "\"Civil Code section 2924f\" was read as section 2924, and where the publication prints two versions of a "
           "section under one number every reader quoted the first, and the pack kept one of the two, with nothing "
           "saying which.",
           "Several modules each had a citation pattern that took digits only, and a page was assumed to hold one text "
           "a section.",
           "One citation grammar (references.statute_citation, SECTION_NUMBER) reads a number that ends in a letter for "
           "every reader: authority_text, jason cite, the board packet, the context pack, the MCP tools, and the "
           "statute links. number_key sorts as the publication prints, so a page's span covers its lettered sections. "
           "The shelf's own section list says whether a lettered number is a section; one it does not list is a miss "
           "that offers the subdivision it may mean, never another section's words. A section printed in two versions "
           "is quoted as the version in force today with a note that quotes the deciding words (law_text.quoted), or "
           "every version is shown, each labeled, where the disk does not decide. Never the first by position.",
           Status.FIXED, guards=("tests/test_lettered_sections.py", "tests/test_law_versions.py: a reader quotes the "
                                 "version in force today, not the one printed first", "references.statute_citation",
                                 "law_text.quoted", "authorities.number_key"),
           docs=("docs/law-readings.md", "docs/citations.md")),
    Lesson("case-file-searchable-only-by-transcripts", date(2026, 10, 4), (Area.DOCUMENTS,),
           "A legal case's fetched file was searchable only through its transcripts: the PDFs had no text beside them, "
           "so a review of the case could not cite a filing. The first extraction also showed that OCR makes thousands "
           "of tokens of a photograph exhibit, which would have been indexed as the filing's words.",
           "The index takes text files, and the fetch kept PDFs as they came. Nothing counted the files it could not "
           "read.",
           "case_files.extract_text writes <name>.pdf.txt from the text layer and sends only scanned pages to OCR; "
           "ocr.reads_as_words leaves a page of noise unread and listed; the index context line says how each file "
           "was read; held-back files are never extracted or indexed. The context pack says how many of a "
           "collection's files the index lacks.",
           Status.FIXED, guards=("tests/test_case_files.py", "ocr.reads_as_words", "jason index --plan (leftOut)",
                                 "tests/test_document_collections.py (the pack's gap line)"),
           docs=("docs/manager-review.md", "docs/mcp.md")),
    Lesson("quoted-as-from-the-shelf-when-it-was-not", date(2026, 10, 4), (Area.DOCUMENTS,),
           "A reference doc quoted a regulation's subsection under \"from the adopted text\" when the adopted text on "
           "the shelf does not print that subsection; the words came from another print.",
           "The quotation was written into the doc by hand, and nothing checked it against the file.",
           "Record-keeping provisions are RecordRule rows recited from disk by their locator, and a miss says the "
           "words are not on the shelf and quotes nothing. The doc now names the print the words came from.",
           Status.FIXED, guards=("jason.tasks.inspections.recite",
                                 "tests/test_inspections.py: a provision the shelf does not print is said to be missing"),
           docs=("docs/fire-protection.md",)),
    Lesson("wrapped-date-not-read", date(2026, 10, 4), (Area.DOCUMENTS,),
           "A reader returned no inspection date where the PDF wrapped the date across a line, so the report could "
           "not be placed in a period and the period showed as not on file.",
           "dates_in wanted one space before the year; a PDF's text layer breaks \"Thursday, September 05,\" from "
           "\"2024\".",
           "dates_in reads a month and day that end their line with the comma, followed by a line that is only the "
           "year, as one date. A day with no comma, or a year with more on its line, stays unread, so two unrelated "
           "lines are never joined. date_after reads its window against the whole text, so a date the window cuts "
           "short is passed over. On the library that day (615 rows) no stored reading changed.",
           Status.FIXED, guards=("jason.community.document_models.dates_in", "tests/test_document_models.py (the date tests)",
                                 "tests/test_models_legal.py: a completed date the text layer wraps before the year"),
           docs=("docs/fire-protection.md",)),
    Lesson("filed-reports-never-read", date(2026, 10, 4), (Area.DOCUMENTS,),
           "Reports filed to Drive from email were logged and never read: the completeness check listed a backflow "
           "test report as filed, not read, and the period as not on file.",
           "jason models read only the library; a filed attachment had no reading.",
           "jason models --filed reads the filing log's inspection reports from their local copies (text layer, then "
           "local OCR; a vision model only when asked) into readings with id drive-<file id>, by the same code path as "
           "a library row. A row says how its words were read, and takes nothing from the email's date or the file's "
           "name.",
           Status.FIXED, guards=("jason models --filed", "tests/test_filed_readings.py"),
           docs=("docs/document-models/README.md", "docs/gmail.md")),
    Lesson("form-legend-read-as-result", date(2026, 10, 4), (Area.DOCUMENTS,),
           "The general inspection reader counts the words pass and fail, so a form that prints them as a legend or as "
           "box labels on every copy reads as failed.",
           "A printed form's own words were taken for the inspector's marks.",
           "The State Fire Marshal's forms and the backflow field test form have their own readers, which leave the "
           "result empty and say so where the marks are not read. Still open for any other form the general reader "
           "takes; its fallback (the first date in the head) can also take a test-due date.",
           Status.OPEN, docs=("docs/document-models/legal.md",)),
    Lesson("report-does-not-say-which-inspection", date(2026, 10, 4), (Area.DOCUMENTS,),
           "Several obligations apply to one sprinkler system, and a report on the State's quarterly-and-annual form "
           "does not say which it is; the five-year form covers two obligations and includes the quarterly and annual "
           "items, but the completeness check gives a report to one obligation.",
           "The check assumed one report is the record of one obligation.",
           "Reports now carry interval_months and buildings from their own words, and a report that does not say stays "
           "unassigned. Still to do: a decision on whether one report may be the record of several obligations.",
           Status.DECISION, docs=("docs/fire-protection.md",)),
    Lesson("portal-reports-not-readings", date(2026, 10, 4), (Area.DOCUMENTS,),
           "A vendor portal's inspection reports are on disk and no pass reads them into the readings, so the "
           "completeness check cannot see them and shows their periods as not on file.",
           "The portal sync saves files; the readers run over the library and the filing log only.",
           "Still to do: a pass over a portal's saved reports (or filing them to the library), then jason models and "
           "jason inspections.",
           Status.OPEN, docs=("docs/vendor-portals.md", "docs/fire-protection.md")),
    Lesson("form-line-is-not-one-fact", date(2026, 10, 4), (Area.DOCUMENTS,),
           "A rule that took the same dated words with different amounts for one fact reported a conflict that was ten "
           "copies of one bill's stub, each for a different parcel.",
           "A form's line or a table's row is the same words in every copy of the form. Sameness of words was read as "
           "sameness of subject.",
           "The rule takes only a sentence (fact_conflicts.is_prose), leaves out a sentence addressed to \"you\", and "
           "leaves out one a single document repeats with different amounts. The stored-field rule says what a document "
           "is about by FieldRule.same (the thing and its period), never by its words.",
           Status.FIXED, guards=("tests/test_chronology.py: the text rules are narrow and name themselves",),
           docs=("docs/collections.md",),
           notes=("The text rules have no true positive on real documents yet: measure each on documents with known "
                  "answers before it is relied on.",)),
    Lesson("subject-is-the-thing-not-its-number", date(2026, 10, 4), (Area.DOCUMENTS,),
           "Comparing policies that share a policy number and a term found nothing; the real difference was two policy "
           "numbers for one building and one term.",
           "The identifier was used to say two documents are about the same thing, so a difference in the identifier "
           "itself could never be seen.",
           "A kind has a row by what the document covers and its period, with the identifier among the compared fields, "
           "beside the row by identifier (fact_conflicts.FIELD_RULES).",
           Status.FIXED, guards=("tests/test_chronology.py: a kind can have several rows and one difference is listed once",),
           docs=("docs/collections.md",)),
    Lesson("spoken-dates-carry-no-year", date(2026, 10, 4), (Area.DOCUMENTS,),
           "The chronology of a case file of caption transcripts was nearly empty: speech names a month and a day, "
           "never a year, and a recording's date is only in its file name.",
           "A transcript is cut from speech; the index held no other file of the case then.",
           "A date a file's name prints is its own kind of event (DateRole.NAME), never the document's words, and the "
           "page counts the month-and-day mentions it could not place. The case's PDFs now have text extracts, so its "
           "chronology reads the filings. Still to do: a decision on placing a date with no year by its document's date.",
           Status.OPEN, docs=("docs/collections.md",)),
    Lesson("records-tier-index-cut-differs", date(2026, 10, 4), (Area.DOCUMENTS,),
           "Read from the passage index with the same latest files, the context pack's records tier gave the library "
           "reader's sources on none of the six tasks that name record kinds.",
           "The index cuts a file on its sections and ranks each passage with the file's context line; the library "
           "reader cuts 220-word windows. There is no gold set for the pack. The section cut also leaves heading-only "
           "passages under 20 words that rank well and say nothing.",
           "The index reader is built and off (context_pack.RECORDS_FROM_INDEX = False), in both reaches; "
           "tests/test_context_pack_records.py holds the fallback and the confidentiality. Still to do: a gold set "
           "(gold-records.json), both reaches scored on it, and the stub passages merged into their neighbours.",
           Status.OPEN, docs=("docs/rag-roadmap.md", "docs/applicability.md")),
    Lesson("two-stores-two-confidentiality-answers", date(2026, 10, 4), (Area.DOCUMENTS,),
           "The library reader shows a members' task treasurer's reports that the passage index holds back: the "
           "redacted copies, which the library does not flag and the index's held kinds include.",
           "Two stores answer the same confidentiality question by different rules; the stricter is applied only when "
           "the index is read.",
           "A person decides which is right: the redacted copies are for members (then the index's rule is too strict "
           "for them), or they are not (then the library reader holds them back too). One rule then serves both.",
           Status.DECISION, docs=("docs/mcp.md (Confidential files in the index)",)),
    Lesson("a-documents-list-is-not-the-whole-list", date(2026, 10, 4), (Area.DOCUMENTS,),
           "A vendor's kinds of work read from a proposal were tested as complete, so a kind the proposal did not "
           "mention read as \"does not apply\".",
           "A many-valued fact was treated the same whatever stated it.",
           "A set a document gives is partial: a value it leaves out is undetermined. A set the profile or a person "
           "states is complete, and a reader that read the whole list says so (FactValue.complete).",
           Status.FIXED, guards=("tests/test_applicability.py: a set read from a document is partial",),
           docs=("docs/applicability.md",)),
    Lesson("a-condition-kept-as-prose-cannot-be-asked", date(2026, 10, 4), (Area.GOVERNING,),
           "Three notice elements carried \"only for ...\" as words, and fifteen catalog rows said when a notice is "
           "required only in a note, so no caller could state the event's facts and every check left the condition to "
           "the reader.",
           "The applicability module had no facet for a meeting or an event.",
           "The event facet (how a meeting is held, the kind of board meeting, the kind of election, an emergency rule "
           "change, electronic voting, acclamation, a quorum for electing directors) and a condition on each "
           "conditional element and row, each written from the section's own words and checked against the shelf; with "
           "no facts the row or element is undetermined and names the fact (jason notice-check --event, jason notices "
           "--catalog --fact). The rows whose conditions need more than the language holds keep their prose "
           "(docs/notices.md).",
           Status.FIXED, guards=("tests/test_notice_conditions.py", "tests/test_notice_applies.py",
                                 "tests/test_association_asks.py", "notice_elements.Sign: a conditional element has "
                                 "both its condition and its words"),
           docs=("docs/notices.md", "docs/applicability.md")),
    Lesson("answer-quotes-unchecked", date(2026, 10, 4), (Area.GOVERNING, Area.DOCUMENTS),
           "Once the search tools returned passages and the client wrote the answer, nothing checked that the answer's "
           "quotations were in the sources: an altered or invented quotation could reach a member as the rule's words.",
           "prompts.verify checks only a manager review's quotes against its own pack; a free answer had no check.",
           "quote_check.check gives each quotation a verdict (found, altered, misattributed, not found) with where it "
           "is stored and its standing; verify_quotes and jason verify-quotes run it, and document_search's caveats "
           "tell the client to.",
           Status.FIXED, guards=("tests/test_quote_check.py", "jason verify-quotes FILE"),
           docs=("docs/law-readings.md (Checking an answer's quotations)",),
           notes=("The board profile does not serve verify_quotes: a person decides whether it joins that set.",)),
    Lesson("cli-docs-drift-from-the-parser", date(2026, 10, 4), (Area.REPOSITORY,),
           "docs/cli.md lists fewer commands than the parser has, and several new commands were added to it by hand.",
           "The page is generated, but nothing checks it against the parser, and sessions working at once each hold "
           "uncommitted command changes, so a regeneration by one would publish another's.",
           "Still to do: regenerate with scripts/gen_cli_docs.py once the sessions' command changes are committed, and "
           "a test that compares the page's commands with the parser's.",
           Status.OPEN, docs=("docs/cli.md",)),
    Lesson("counterparty-named-in-general-readers", date(2026, 10, 4), (Area.REPOSITORY,),
           "Three general readers recognized the association's law firms by name (a pre-lien notice's sender and who "
           "printed its ledger, a lien's requester, a legal letter's and a brief's firm), and the reserve study reader "
           "named its balcony inspector. The boundary did not see them. Where a module does read one vendor's own layout "
           "(a bank's statement), the only way to pass the check was a baseline entry.",
           "The boundary took managers from the sender directory and no other counterparty, and it had no way to tell a "
           "reader of one vendor's layout from a general reader that names a counterparty.",
           "sources.sender_in and sender_name find a counterparty of a given kind through the profile's senders; one the "
           "directory does not list is a miss. boundary.sender_terms takes every counterparty's name and words (no "
           "government agency, public utility, platform, or owner; no word with a digit, under five characters, or in "
           "KIND_WORDS; a one-word name only when it is among the sender's words). A reader of one vendor's layout is "
           "declared as an Adapter row (jason.community.adapters, or its InvoiceFormat row) and listed in "
           "docs/adapters.md: the vendor's name is then allowed in that module and in a document's code span, nowhere "
           "else, and a stale or unlisted declaration fails the check.",
           Status.FIXED,
           guards=("tests/test_profile.py: a counterparty is an instance term; a counterparty in a general pattern is "
                   "found unless the module is its declared adapter; every adapter is listed and borne out; no general "
                   "reader names a law firm", "python -m jason.community.boundary"),
           docs=("docs/adapters.md",),
           notes=("The readers the boundary could not see are fixed (lesson pattern-given-to-a-helper-unseen). Still in "
                  "general code: tasks/board_packet.py OPTIONS and tasks/request_sheet.py GROUPS, two tables of one "
                  "association's facts.",)),
    Lesson("recital-gave-todays-words-for-an-earlier-day", date(2026, 10, 4), (Area.GOVERNING,),
           "A recital for an earlier day gave today's words: jason held one edition of each statute, so a review of an "
           "older letter recited words not then in force, with only a caveat.",
           "The export kept the current publication only; the law library's session publications from 2011 hold the "
           "earlier words with the Legislature's notes, and nothing read them.",
           "jason law-history --versions keeps each earlier version with the range it was in force (from, until, the "
           "act that made it and the one that ended it), and recite(as_of=) recites the words of that day or says they "
           "are not shown to be in force. A day that is not recorded stays not recorded. Before the 2011 publication "
           "the shelf holds no code text (docs/law-readings.md, The gap).",
           Status.FIXED, guards=("law_text.in_force", "law_readings.Recital.in_force", "tests/test_law_versions.py"),
           docs=("docs/law-readings.md (The words in force on a day)",)),
    Lesson("first-printed-is-not-in-force", date(2026, 10, 4), (Area.GOVERNING,),
           "Where the publication prints a section twice under one number, readers quoted the first; for one section "
           "on the shelf the first printed is the version that becomes operative in 2031.",
           "Position on the page was taken for the order the versions operate in.",
           "in_force picks by the versions' own operative words (\"shall remain in effect only until ...\", \"shall "
           "be operative ...\") and quotes them; where the words state nothing, both are shown.",
           Status.FIXED, guards=("law_text.in_force (Decided.OWN_WORDS)", "tests/test_law_versions.py",
                                 "tests/test_quote_check.py: a section held in two versions says so"),
           docs=("docs/law-readings.md",)),
    Lesson("statute-text-readers-drop-the-version-note", date(2026, 10, 4), (Area.GOVERNING,),
           "Five callers take a statute's words from authority_text without its note: for a section printed twice they "
           "show the version in force and do not say that there is another, or why this one.",
           "The note that names the version is a separate key the callers never read.",
           "Still to do: rule_change.authority_status, manual.statute_words, the meeting notice's recital, "
           "conflict_leads, and statute_passages print the note beside the words.",
           Status.OPEN, docs=("docs/law-readings.md (Limits)",)),
    Lesson("a-statutory-option-is-not-a-document-fact", date(2026, 10, 4), (Area.GOVERNING,),
           "The acclamation notices were described as required \"only if the association may seat candidates by "
           "acclamation\", which reads as a fact about the governing documents.",
           "The section applies notwithstanding the documents and leaves the choice to the association; the row's "
           "prose inserted a condition the words do not state.",
           "The fact is the board's standing choice, asked as a question that says so and answered with the record of "
           "the decision.",
           Status.FIXED, guards=("tests/test_notice_applies.py", "applicability_asks.ASKS (acclamation)"),
           docs=("docs/notices.md",)),
    Lesson("generated-page-read-back-as-a-source", date(2026, 10, 4), (Area.DOCUMENTS,),
           "A collection's generated summary, indexed in the collection's own catalog, would have been quoted by the "
           "chronology as a document and ranked by a review as evidence.",
           "A catalog was one scope for both the documents and what jason wrote about them.",
           "A collection's scope leaves its pages out (Scope.not_folders), on every collection and on the lens "
           "commands; a review carries the summary as one labeled source, without its chronology.",
           Status.FIXED, guards=("tests/test_collection_pages.py: the page is indexed as a confidential generated page; "
                                 "a lens named for the catalog does not read the page back; the pack carries the "
                                 "summary once, labeled"),
           docs=("docs/collections.md", "docs/applicability.md")),
    Lesson("held-files-counted-by-local-name", date(2026, 10, 4), (Area.DOCUMENTS,),
           "A count of a case's held-back files came out two short: two held files that share one local name were "
           "counted once.",
           "The count keyed on the name a file would have on disk, not on the listing's rows.",
           "case_files.inventory counts each flagged listing row, plus each held file on disk the listing does not flag.",
           Status.FIXED, guards=("tests/test_collection_pages.py: the inventory gives each file's state and counts the "
                                 "held ones",)),
    Lesson("near-match-quote-check-passes-another-version", date(2026, 10, 4), (Area.GOVERNING, Area.DOCUMENTS),
           "The review's quote check accepts a quotation 0.9 alike, so \"fourteen days\" checks against a source that "
           "says \"fifteen days\": an as-of review can cite today's words against an earlier version unnoticed.",
           "The tolerance was set for OCR's misreadings and applies to the law's words too.",
           "Still to do: check a law source's quotations with quote_check's exact matcher, and teach quote_check to "
           "read the history for a dated citation and to say when the words are a stored reading.",
           Status.OPEN, docs=("docs/manager-review.md (The quote check and readings)",)),
    Lesson("reciting-writes-the-versions-cache", date(2026, 10, 4), (Area.DOCUMENTS,),
           "A read-only check that recited a section of a document kept as amended rebuilt and wrote that document's "
           "versions cache under data/section-refs.",
           "The reader builds the cache when its fingerprint differs, and the fingerprint includes the code's hash, "
           "which differs between a worktree and the main checkout.",
           "Still to do: a read-only resolver (build_versions(write=False)) for read-only callers such as the MCP tools "
           "and checks.",
           Status.OPEN, docs=("docs/manager-review.md",)),
    Lesson("store-read-outside-check-hid-from-the-inventory", date(2026, 10, 4), (Area.DOCUMENTS,),
           "Two readers reworded a finding in their own read with a clause from the library's minutes. The basis "
           "inventory watched check, so it reported no store read; removing one set of minutes changed four rows with "
           "no review made again.",
           "The inventory observed one call, and a reader's read can run after it.",
           "The finding is the records lens's, and a row records what its check read. A move is proven by changing the "
           "other record and showing that exactly the reviews resting on it are made again, not only by comparing the "
           "same inputs.",
           Status.FIXED, guards=("tests/test_records_lens.py: a review is made again when its facts change, and a row "
                                 "changes only with one",),
           docs=("docs/document-models/README.md",)),
    Lesson("lens-checks-read-before-readers-loaded", date(2026, 10, 4), (Area.DOCUMENTS,),
           "In a fresh process jason models --as-of reviewed its first row with no checks and reported that row's lens "
           "findings as gone.",
           "A lens's checks register when the reader modules import, and nothing imported them before the first row.",
           "document_reviews loads the readers first. Still to do: a test, which needs a fresh process.",
           Status.OPEN),
    Lesson("pattern-given-to-a-helper-unseen", date(2026, 10, 4), (Area.REPOSITORY,),
           "The boundary read a pattern only where it was given to re. Ten term-and-module pairs sat in patterns given "
           "to a reader helper, and a table of carriers and three senders' words in the mail rules sat in module-level "
           "tuples.",
           "The scan listed the places a fact hides by how the code was written, not by what the string is used for.",
           "pattern_parameters finds every function that hands a parameter to re as the pattern, or to another such "
           "function; a module knows its own functions and the ones it imports by name. The wide reading (boundary "
           "--wide) reports a module's own tables; it is not part of the check while two tables of one association's "
           "facts remain. A reader takes a carrier from the insurance record and then the sender directory, a "
           "subdivider from developers(), an opposing party from legal_cases(); one the profile lacks is a miss, listed "
           "for a person.",
           Status.FIXED, guards=("tests/test_profile.py: a fact in a pattern given to a helper is found; a fact in a "
                                 "module's own collection is found by the wide reading; no general table names a "
                                 "counterparty but the two that wait", "python -m jason.community.boundary"),
           docs=("docs/adapters.md",),
           notes=("Matching helper functions by name alone flags unrelated calls (a .get with a default); resolve by "
                  "the module's own and imported names.",)),
    Lesson("owners-insurers-claim-counted-as-the-associations", date(2026, 10, 5), (Area.DOCUMENTS,),
           "A claim paper from an owner's own homeowner insurer was read as the association's claim: it made the loss "
           "\"claimed\", hiding a claim candidate, and put the owner's insurer's estimate and payment into the event's "
           "cost.",
           "The readers named a carrier but not whose policy the paper was on, and the history counted any claim paper. "
           "The old name patterns that happened to name those carriers had been removed in the boundary work, which "
           "turned the papers into carrier-less readings and showed the gap.",
           "Each claim reading carries a Policyholder (the association's, another's, or unknown) decided by rule from the "
           "insurance record, the policy number, the letter's insured line, and the sender directory's holder for a "
           "carrier; a paper on another's policy gets a finding that is a lead for a person, and the incident history "
           "counts only the association's papers and lists the others apart (OWNER-INS, otherInsurerClaims). Whether the "
           "loss touches the master policy, a common area, or the deductible's allocation is for a person to analyze.",
           Status.FIXED, guards=("insurance_claims.policyholder_of",
                                 "tests/test_models_claims.py: a carrier the directory says writes an owner's policies is "
                                 "other and the paper carries the lead",
                                 "tests/test_incidents.py: an event with only another insurer's claim is not claimed and "
                                 "keeps its candidate standing"),
           docs=("docs/incidents.md", "docs/document-models/insurance-claims.md")),
    Lesson("a-directory-entry-does-not-say-whose-policy", date(2026, 10, 5), (Area.DOCUMENTS,),
           "The association's prior carrier and its claims administrator are listed in the sender directory beside "
           "owners' insurers. A rule that read \"in the directory only\" as another's policy would have flipped about "
           "twenty-four of the association's own papers.",
           "A directory row names a counterparty, not whose policies it writes.",
           "Sender.holder states whose policies a row writes; unset is unknown. A person sets it per row. The "
           "certificate of satisfaction on one claim prints another carrier's group name under a claim that also has the "
           "association's carrier's papers: whether it is on an owner's policy is for a person.",
           Status.DECISION, docs=("docs/incidents.md",)),
    Lesson("stub-passages-cost-first-places", date(2026, 10, 5), (Area.DOCUMENTS,),
           "Joining passages under 20 words into their neighbours removed every stub from the gold sets' top five and "
           "kept recall@5, but MRR@10 fell 0.008: competitors a stub had sat above rose past answers already first.",
           "A stub ranks well on few words, and removing it lifts whichever passage sat below it, which cannot be an "
           "answer already in first place.",
           "The join is built and off (passage_sections.MIN_PASSAGE_WORDS = 0); eval_retrieval.py --min-words and "
           "FIRST_STATS measure it. The stubs the context pack showed were library sources, which no gold set measures: "
           "decide after gold-records.json exists.",
           Status.DECISION, docs=("docs/document-tools.md (model trials)", "docs/rag-roadmap.md")),
    Lesson("model-answers-for-its-neighbor", date(2026, 10, 5), (Area.DOCUMENTS, Area.GOVERNING),
           "Asked about one marked sentence of a section, the local model quoted a neighboring sentence's power; the "
           "quote was in the section, so the verbatim check passed, and asked what a general power covers it listed "
           "every subject.",
           "The check asked only whether the quoted words were somewhere in the section, and the subjects were not "
           "tied to words.",
           "rule_authority.model_reading requires the operative words in the marked sentence, else the answer is no, "
           "and drops a subject no word of the section reaches.",
           Status.FIXED, guards=("tests/test_rule_authority.py",), docs=("docs/rule-authority.md",)),
    Lesson("rule-reader-tuned-on-its-gold", date(2026, 10, 5), (Area.DOCUMENTS,),
           "The rule-only reader of rule-making grants scored precision 1.00 on the gold set, but its patterns were tuned "
           "while reading those same candidates; only the model's first run was blind.",
           "One association's documents served as both the tuning set and the test.",
           "Still to do: a held-out half, and a second association's gold set, before the figures are relied on.",
           Status.OPEN, docs=("docs/rule-authority.md",)),
    Lesson("grant-without-a-rule-noun", date(2026, 10, 5), (Area.DOCUMENTS, Area.GOVERNING),
           "A delegation with no rule noun (\"shall be established by the Board\" for a time limit, \"may designate quiet "
           "hours\", a power to establish fines) was read as a reference or not collected, so five of nineteen grants "
           "were missed by the rules.",
           "The collector looked for an adoption verb with a rule noun.",
           "A delegation pattern collects the first kind, and the model's reading shows the disagreement as a conflict "
           "row for a person. Still open for wording the patterns do not look for.",
           Status.OPEN, docs=("docs/rule-authority.md",)),
    Lesson("guide-describes-power-not-power", date(2026, 10, 5), (Area.GOVERNING,),
           "A guide's sentence describing the board's power to make rules read like a grant of it.",
           "Every part of a manual was read the same way.",
           "Parts: a grant stated only in a guidance part is listed apart (\"stated in guidance only\") and never counted "
           "as authority.",
           Status.FIXED, guards=("rule_authority.parts_from_manual", "tests/test_rule_authority.py"),
           docs=("docs/rule-authority.md",)),
    Lesson("citation-needs-its-document", date(2026, 10, 5), (Area.GOVERNING, Area.DOCUMENTS),
           "Of the bare citations in the association's own documents, 348 of 493 were unresolved (every one in letters, "
           "notices, and minutes), and a book's common name silently meant its first document.",
           "A number counted as a section only when a name came with it, and the grammar scoped a bare number only "
           "inside an outline.",
           "jason.community.scoping scopes a citation by the citing document, its day, and the citation's form, with the "
           "basis recorded; two documents that fit are ambiguous_document naming both, never a pick; a nearby name is a "
           "lead; jason cite --in KEY --on DAY and --scan FILE.",
           Status.FIXED, guards=("jason.community.scoping", "tests/test_scoping.py", "jason cite --scan"),
           docs=("docs/rule-citations.md",)),
    Lesson("rule-row-cited-as-a-document", date(2026, 10, 5), (Area.GOVERNING, Area.OWNER_INFO),
           "Plan items that cite jason's own rule rows (owner_responses.RULES: delivery) showed as unknown_document on "
           "the approvals screen.",
           "The resolver knew documents and statutes, not jason's own tables of decisions kept as data.",
           "rule_rows.TABLES recites a row as data, labeled jason's own row and never the association's rule, with the "
           "board decision it rests on when the row names one. A prose rule stays a miss until it cites a row or a "
           "document. The last one, the owner-information completion rule, now cites the specification "
           "(Community.owner_information: OWNER_INFO_COMPLETED_COMMENT), recited with the board's decision written "
           "above it; every plan kind's rule must recite.",
           Status.FIXED, guards=("rule_rows.TABLES", "tests/test_scoping.py",
                                 "test_every_plan_kinds_rule_is_an_address_the_approvals_screen_recites"),
           docs=("docs/rule-citations.md",)),
    Lesson("coarse-segment-part-swallows-finer-classification", date(2026, 10, 5), (Area.GOVERNING, Area.DOCUMENTS),
           "Wiring segmentation into rule authority, a coarse segment \"rules\" part swallowed the manual "
           "classification's finer bound-in policy parts and moved 12 rules from policy to rule, though the total "
           "stayed the same.",
           "The merge let the segmentation win wherever both readings covered a stretch.",
           "rule_authority.merge_parts keeps a segmentation part only where the two readings agree on the kind; "
           "where they disagree the classification's part stays and the segmentation's kind is written on it "
           "(contested), so a segmentation never enlarges the rules on file for a document the classification covers.",
           Status.FIXED, guards=("rule_authority.merge_parts", "tests/test_segment_scoping.py"),
           docs=("docs/rule-authority.md",)),
    Lesson("exhibit-name-must-not-read-the-documents-section", date(2026, 10, 5), (Area.GOVERNING,),
           "\"Section 3 of Exhibit A\" could have resolved to the containing document's own section 3, because an "
           "exhibit has no outline of its own.",
           "A part's name found the document, and the number was then read in the document.",
           "A section number in a part is checked against the part's own sections; an exhibit with none is a miss "
           "that says why, never the document's section of that number.",
           Status.FIXED, guards=("scoping._scope_part",
                                 "test_a_section_in_an_exhibit_is_a_miss_never_the_documents_section_of_that_number"),
           docs=("docs/rule-citations.md",)),
    Lesson("a-reading-is-used-only-for-the-file-it-can-be-checked-against", date(2026, 10, 5),
           (Area.GOVERNING, Area.DOCUMENTS),
           "A stored segmentation could be applied to a file whose bytes had changed, to a file holding several "
           "documents, or to an outline it did not belong to.",
           "A reading is keyed by the file, and nothing checked the file was still the one read.",
           "cite_scope.segment_readings uses a reading only when the file is in the library and on disk, its bytes "
           "are unchanged, and it holds one top-level document that is one outline's document (bound by library path, "
           "else by text, with a miss if two outlines fit); each reading left out says why in the scan's notes.",
           Status.FIXED, guards=("cite_scope.segment_readings", "cite_scope.bind_outline", "tests/test_segment_scoping.py"),
           docs=("docs/rule-citations.md",),
           notes=("Open: the benefit is unmeasured on real documents until each rule document's PDF is read once "
                  "(jason segments ID); only citations that already resolved were checked, with none changed.",)),
    Lesson("parts-placed-by-heading-text-swallow-the-classification", date(2026, 10, 5), (Area.GOVERNING, Area.DOCUMENTS),
           "On the real manual a part was placed by its heading text wherever it occurred: a running page header (and "
           "the association's name) became 16 cover parts that overrode the classification, and a contents part spanned "
           "the whole guide; guidance parts fell from 31 to 2, copy from 18 to 0, and a rule part was lost.",
           "A heading found anywhere is not a heading, and a reading that wins wherever two overlap can erase the finer one.",
           "document_segments.place_parts takes only a line that is the heading, in page order, at or after the previous "
           "part; a repeated heading is a running header inside its part; each part ends where the next starts; a cover "
           "or contents part is capped at its own pages' share and never overrides a part of another kind "
           "(rule_authority.merge_parts, FRAME_KINDS).",
           Status.FIXED, guards=("document_segments.place_parts", "document_segments.locate_heading",
                                 "rule_authority.merge_parts", "tests/test_segment_scoping.py"),
           docs=("docs/rule-authority.md", "docs/document-segmentation.md")),
    Lesson("a-new-reading-must-not-change-a-covered-document", date(2026, 10, 5), (Area.GOVERNING,),
           "A new reading (the stored segmentation) changed the parts of a document the older reading already covered, "
           "and nothing failed: the totals still looked right.",
           "The tests used made-up documents, where the two readings agreed.",
           "Before a new reading is trusted on real data, compare the older reading's counts by kind with the new one "
           "switched off (rule_parts with segments=False), the subjects report, and jason cite --scan with and without "
           "--no-segments, offset by offset: no citation may change document.",
           Status.FIXED, guards=("tests/test_segment_scoping.py (same-standing tests)",),
           docs=("docs/rule-citations.md",)),
    Lesson("a-new-document-definition-calls-the-existing-fill", date(2026, 10, 5), (Area.DOCUMENTS,),
           "A second document system risks a second copy of the token fill, so the manual could print one thing from "
           "jason manual --render and another from its definition.",
           "Two paths over the same tokens drift.",
           "The definition's manual block calls manual.fill_token, the same function render uses; a migration is proved by "
           "rendering both paths from the same inputs and comparing the output exactly; a layout never reads a block's "
           "source (assemble once, render under two layouts, compare the blocks); a directory prints only the fields "
           "with their own publish flag.",
           Status.FIXED, guards=("manual.fill_token", "tests/test_document_templates.py"),
           docs=("docs/document-templates.md",)),
    Lesson("a-docs-missing-styles-read-as-false-positives", date(2026, 10, 5), (Area.DOCUMENTS,),
           "Scoring a PDF's recovered headings against a Google Doc's styles counted about nine numbered capital lines "
           "the Doc leaves as plain paragraphs as the reader's false positives.",
           "A gold made of paragraph styles is only as complete as the Doc.",
           "structure_score reports likely and suggested precision and the findings apart; the closed contents row "
           "demotes headings a complete contents page does not list to suggested; the benchmark counts such lines for "
           "the Doc's keeper to style (or to say they are not headings).",
           Status.OPEN, guards=("tests/test_structure_recovery.py::test_a_contents_page_the_body_bears_out_closes_the_list",),
           docs=("docs/structure-recovery.md",),
           notes=("Open until a person styles the lines or says they are not headings; before a template is built from a "
                  "Doc, run scripts/structure_fuzz.py gold and report on it and its PDF, and carry bookmarks and a contents "
                  "page into the generated PDF (the two cheapest large gains).",)),
    Lesson("section-printed-twice", date(2026, 10, 5), (Area.GOVERNING, Area.DOCUMENTS),
           "A section number a document prints twice was ambiguous with no way to say which, and a list that numbers "
           "its own sections hung its sublist twice (\"18(18)(a)\").",
           "The outline readers assumed one place per number.",
           "A repeated number is cited by place (R-3(i)~2); the sublist hangs once; text outlines read lettered rules. "
           "Outlines already on disk keep the old numbering until jason outlines is re-run.",
           Status.FIXED, guards=("DiskResolver.provision", "outline_from_doc", "outline_from_text",
                                 "tests/test_scoping.py"),
           docs=("docs/rule-citations.md",)),
    Lesson("plan-screen-defaults-stood-in-for-the-kind", date(2026, 10, 5), (Area.REPOSITORY,),
           "The plan review read a two-person flag the server never sent and used its own 24-hour default for a "
           "plan's age, so a two-person kind would have shown no second signer; its old-plan banner promised that apply "
           "would re-read when the engine refuses; an item's rule showed as a citation with no words; the nav count "
           "left out the plans; and a held item's board item was not a link.",
           "The screen was built against the components' props before the plan's answer carried the kind, and the "
           "banner's words were written before the engine's refusal of an old plan.",
           "GET /api/approvals/<id> now carries the kind's facts, whether a second person must sign, and each rule "
           "recited; GET /api/approvals counts the plans waiting on a person; the banner says apply refuses an old plan "
           "and the apply step is not offered; a held item links to #/actions?item=ID; and a test walks every GET the "
           "approvals routes answer to show none changes the store.",
           Status.FIXED, guards=("tests/test_web_approvals.py: kindFacts, needsSecond, recitations, approvalsWaiting, "
                                 "and no GET changes data/approvals/",
                                 "ui/src/views/planapprovals.test.tsx: the kind's line, a recited rule, the board link, "
                                 "and an old plan not offered to apply"),
           docs=("docs/console/screens/approvals.md", "docs/console/mvp.md")),
    Lesson("boundary-misses-plain-strings", date(2026, 10, 5), (Area.REPOSITORY,),
           "With its baseline empty, the code boundary check still passed general modules whose tables and string "
           "constants held one association's facts: board-item options, request groups, stop-word sets, user agents, "
           "a vendor layout row, a parcel-number prefix.",
           "The check read regular expressions, word lists, and default arguments, not a module's own tables or lone "
           "string constants.",
           "The check now reads module- and class-level tuples, lists, sets, dicts, and string constants (the literal "
           "parts of an f-string too); Community gained eight methods with empty defaults (board_item_options, "
           "request_groups, name_words, user_agent, developer_security_notes, program_contractors, parcel_prefix, "
           "recordings_note); the baseline stays empty. Still unseen: strings inside function bodies, a class's lone "
           "enum members in symbols.py (phase 3), docstrings, and comments.",
           Status.FIXED, guards=("tests/test_profile.py: a made-up term in a table or constant is found; a second "
                                 "profile gets the empty answer from each new method",
                                 "boundary.scan_code"),
           docs=("docs/adapters.md", "docs/profiles.md")),
    Lesson("a-move-that-rewrites-changes-behavior", date(2026, 10, 5), (Area.REPOSITORY,),
           "Moving a board-packet sentence into the profile, an agent rewrote it from a different source, and two "
           "other moves reordered a scan and a caveat; only a before-and-after run on real data caught them, and a "
           "first harness had failed the same way on both sides, proving nothing.",
           "A move was treated as a chance to tidy the words; the harness raised on a read-only write instead of "
           "swallowing it.",
           "The rule: move the exact words into the profile as data; prove it by diffing the old code against a "
           "base-commit export (not a checkout with other sessions' edits), with a harness that swallows writes. "
           "Still to decide: where the proof harness lives as a guard (today it is scratch).",
           Status.OPEN),
    Lesson("intake-answer-overwrites-unseen", date(2026, 10, 5), (Area.ONBOARDING,),
           "intake.answer replaces an earlier answer and clears its confirmation without checking that the person "
           "saw the answer they replace, so two people answering one question can silently undo each other.",
           "The write takes the new value only; it carries no echo of the answer it replaces.",
           "Designed (docs/console/handoff-applicability-questions.md): a seen echo of answeredAt and a refusal when "
           "it differs, with the line \"This replaces the answer of NAME\". Still to build in the writer.",
           Status.OPEN, docs=("docs/console/handoff-applicability-questions.md",)),
    Lesson("computed-answer-labeled-decided", date(2026, 10, 5), (Area.GOVERNING,),
           "The terminal prints \"decided by\" before the facts a computed applies/does-not-apply answer turns on, "
           "though nothing jason computes is labeled as decided (docs/console/content/style.md).",
           "The word came from the evaluator's field name (deciding) and spread to eight modules' output.",
           "The console says \"Turns on\" (the applicability handoff). Still open: the same word in the terminal "
           "output of applicability, notice_catalog, notice_elements, commands/notices, life_safety, and "
           "inspections, with their tests, changed together once the life-safety work is committed.",
           Status.OPEN, docs=("docs/console/content/style.md",)),
    Lesson("program-adoption-needs-the-act", date(2026, 10, 5), (Area.GOVERNING, Area.DOCUMENTS),
           "A required program existed and had been adopted, but looked unadopted: the minutes that adopted it were in "
           "no index catalog, so no search or quote check could find the act. Elsewhere a revision report printed "
           "\"adoption on record\" for minutes that only quoted the section.",
           "Minutes were indexed only from a later year, and the report treated a minute that names a section as one "
           "that adopts it. Minute verbs (delegated, directed, \"we would like to\", listed in a packet, approved, "
           "adopted) were not told apart.",
           "Designed (docs/programs.md): the adopting act is its own evidence, named in the catalog row; minutes are "
           "read for references like \"CC&R 7.8 (a)\" and for their verbs. Still to build: index the older minutes, the "
           "lens check program-not-adopted, and a test that a quotation never prints as an adoption.",
           Status.OPEN, docs=("docs/programs.md",)),
    Lesson("inspection-record-needs-a-date", date(2026, 10, 5), (Area.DOCUMENTS,),
           "A required quarterly inspection was kept on a reused worksheet with no date, inspector, or signature: each "
           "walk cleared the last one's answers, a copy looked like a new inspection, and the only dates were the "
           "file's revision times, which jason keeps no store of.",
           "The record was a form to fill, not a log to append, and jason had no kind for an inspection log.",
           "Designed (docs/programs.md): an inspection-log kind that is dated and appended, with inspector and photos; "
           "a payment is not an inspection and a last-modified date is not an inspection date. Still to build: the "
           "kind, its reader, and the lens check inspection-quarter-missing.",
           Status.OPEN, docs=("docs/programs.md",)),
    Lesson("silent-cadence-is-the-boards", date(2026, 10, 5), (Area.GOVERNING,),
           "The duty reader gave \"periodically\", \"immediately\", and \"at all times\" no interval and no deadline, so "
           "the program's steps that used them had no clock and no question.",
           "Only a stated number of days or months became a recurrence; a silent or event cadence was dropped.",
           "Designed (docs/programs.md): the catalog row says which cadences the document fixes and which the board "
           "must set; a silent one is a question and a written policy proposed for the board, never a default "
           "interval jason picks. Still to build in the duty reader.",
           Status.OPEN, docs=("docs/programs.md",)),
    Lesson("outside-mandates-are-duties", date(2026, 10, 5), (Area.GOVERNING,),
           "A city's conditions of approval for the development required a monthly exterior inspection, a maintenance "
           "program the planning director approves, and a repaint interval; none sat in a duty list, an obligation "
           "row, or a reserve assumption, and a reserve study set a longer repaint cycle than the condition.",
           "jason read duties from the governing documents and the statutes only; the conditions were running text "
           "in a plan set.",
           "Designed (docs/programs.md): a source tier below statute for conditions of approval, with a duty reader "
           "for them; whether they bind, and which buildings, is for the city or counsel. Still to build.",
           Status.OPEN, docs=("docs/programs.md",)),
    Lesson("reserve-study-assumes-maintenance", date(2026, 10, 5), (Area.GOVERNING,),
           "A reserve study's useful lives assume maintenance, but the studies stated few of those assumptions, left "
           "out components the declaration names, and one update shortened a life by three years with no maintenance "
           "consequence recorded; the same interval appeared in four conflicting forms across the association's "
           "papers.",
           "Nothing tied the study's components and lives to a maintenance schedule, and the readers took the "
           "funding table, not the component narratives.",
           "Designed (docs/programs.md): a component register at the core of a maintenance program, aligned with the "
           "study, the conditions, the board's sheet, and the owner-facing manual as a first-class check. Still to "
           "build: the register and the study-narrative reader.",
           Status.OPEN, docs=("docs/programs.md",)),
    Lesson("drive-ingestion-needs-screening", date(2026, 10, 5), (Area.DOCUMENTS,),
           "Reading Drive Docs for a review found a counsel letter with no kind and not marked confidential, and a "
           "Doc holding access codes in plain text.",
           "Drive ingestion classified by name and folder and ran no screen for privileged advice or secrets.",
           "Designed (docs/programs.md, the ingestion section): privileged material held back by default and a "
           "secret scan of Doc text, both before any reader or index sees the file. Still to build; the secrets "
           "themselves belong in the credential vault, not a Doc.",
           Status.OPEN, docs=("docs/programs.md",)),
    Lesson("a-requirement-is-not-a-document", date(2026, 10, 5), (Area.GOVERNING,),
           "A provision that obliges the association to adopt a program (an inspection program, a maintenance manual) "
           "was tracked as deadlines and notices, with no record of the instrument itself: whether it exists, whether "
           "the board adopted it, whether it is carried out, whether a newer statute makes it stale. A deadline row "
           "could show \"no store shows it\" for a program nobody had written.",
           "jason modeled obligations and notices, not the instruments an association must adopt; the declaration's "
           "duties were read, but an adoption duty was one more duty row.",
           "Designed (docs/programs.md): an adoption catalog of statute, conditional, and declaration rows; the three "
           "evidences (document, adoption act, implementation) as separate states, \"no act on record\" never read as "
           "\"not adopted\" and \"not on file\" never as \"not done\"; review under a programs lens; drafts from base "
           "templates for the board to adopt. Still to build: program_catalog with its test against the shelf, and the "
           "law-review and document-intake procedure steps.",
           Status.OPEN, docs=("docs/programs.md", "docs/console/handoff-programs.md")),
    Lesson("a-detection-is-a-lead", date(2026, 10, 5), (Area.DOCUMENTS, Area.GOVERNING),
           "A loose rule (an adopt or maintain verb plus a program or policy noun) scored 5 true of 15 on a real "
           "corpus; the false hits were an insurance policy, a parliamentary procedure, and a document speaking of "
           "itself.",
           "The words \"policy\", \"procedure\", and \"adopted\" have several senses, and a rule that matched them anywhere "
           "in a duty could not tell them apart.",
           "The rule designed in docs/programs.md takes the head verb, a program noun, and stops for the known homonyms; a "
           "detection enters the catalog only on a person's confirmation, and a gold set is labeled before tuning. Still "
           "to build: program_detect, its gold set, and scripts/eval_programs.py.",
           Status.OPEN, docs=("docs/programs.md",)),
    Lesson("review-as-of-and-quote-check-ignored-the-versions", date(2026, 10, 5), (Area.GOVERNING, Area.DOCUMENTS),
           "A review as of an earlier day treated a document's citation of a renumbered section (a former Davis-Stirling "
           "number) as a missing section, and verify_quotes confirmed a quotation against whichever edition the shelf "
           "held, so a quote of an earlier or later version of a statute passed or was called NOT FOUND without saying "
           "which version it was.",
           "The pack followed citations by number against the law as it stands now, and the quote check read one edition "
           "and never the history; the successor table and the earlier versions were on disk but no reader joined them "
           "to a day.",
           "law_text.version_on gives the version in force on a day with every version held and where each stands; "
           "quote_check checks a statute's quotation against that version (--as-of) and names a quotation of another "
           "version (OTHER VERSION, never clean); law_citations.resolve reads a former number through the exported "
           "successor table as of a day, recites the successor as of the day and the former section's own words as they "
           "last stood, and leaves a number the table does not place open. Still open: the no-day pack reads former "
           "numbers by the grammar's fixed range, not the table, and prompts.verify (the pack's own near-match check) "
           "still accepts a quote of another version that differs by a word.",
           Status.FIXED, guards=("tests/test_law_in_force.py",
                                 "tests/test_quote_check.py::test_a_quotation_of_another_version_of_the_statute_is_named_not_confirmed",
                                 "tests/test_law_citations.py: an unresolved number stays open; the no-day pack is unchanged"),
           docs=("docs/law-readings.md", "docs/collections.md")),
    Lesson("procedures-left-the-events-facts-unsaid", date(2026, 10, 5), (Area.GOVERNING,),
           "The catalog could sort the conditional notice rows by an event's facts (jason notices --catalog --fact), but "
           "no procedure for an election, a rule change, or a board meeting told the person to say them, so each run "
           "left the conditional rows to the reader again.",
           "The event facet and the --fact flag were built after the procedures were written, and there was no election "
           "or rule-change procedure at all.",
           "The election and rule-change procedures exist, and they and board-packet open with the step that says the "
           "event's facts and reads the three groups, naming the lesson that put the conditions into data; a test holds "
           "that each has it, that every jason command a step names is a subcommand, and that every procedure and docs "
           "reference exists.",
           Status.FIXED, guards=("tests/test_lessons_procedures.py: the election, rule-change, and board-packet "
                                 "procedures say the event's facts; every jason command a step names is a command the "
                                 "parser has",),
           docs=("docs/notices.md",)),
    Lesson("building-clocks-asked-of-the-association", date(2026, 10, 5), (Area.GOVERNING, Area.DOCUMENTS),
           "Civil Code 5551(k) (a building permitted from 2020 is inspected within six years of its certificate of "
           "occupancy) and (l) (three or more attached units) are about one building each, but the only record was the "
           "association's obligation row counted from one report's date, so a newer building's shorter clock and a "
           "building the section does not reach had no place, and a missing date read as the row's own.",
           "No per-building record existed; the applicability condition was asked of the association once.",
           "ElevatedElementsInspection (jason.community.elevated_inspections) is one building's record from the "
           "profile's private facts (Community.elevated_elements_inspections(), empty by default): its last inspection "
           "with the licensed professional and report, the (k) and (l) answers in three values, and the next due day "
           "under (b)(1)/(i) or (k). A date not on record is a question in jason applies and a \"date not on record\" "
           "row in jason deadlines, never a guess. Still to do: the per-building questions are printed, not filed in "
           "the intake queue; the association's own rows are not yet entered (a person enters them).",
           Status.FIXED, guards=("tests/test_elevated_inspections.py: an unknown date is a question, not a guess",),
           docs=("docs/applicability.md",)),
    Lesson("term-pattern-matches-another-clock", date(2026, 10, 5), (Area.GOVERNING,),
           "Four statutory terms (the penalty cap, the lien release after payment, the ballots' mailing, and the "
           "nominations notice) and the mechanic's lien action carried a pattern that also fits another clause of the "
           "section: 5685(b), 5115(a) and (b), 5850(d), and later subdivisions of 8460. The check passed whichever "
           "sentence was left, so a change to the clause that sets the clock would not have been noticed.",
           "The test asked only whether the pattern occurs somewhere in the section's text, and a short pattern such as "
           "'at least 30 days' occurs in several subdivisions that set different clocks.",
           "Each pattern is now the words of the one sentence that sets its clock, and a test requires that it match "
           "exactly one place in the section (it runs where the statute is exported, and skips elsewhere).",
           Status.FIXED, guards=("tests/test_statutory_terms.py::test_the_pattern_names_the_one_sentence_that_sets_the_clock",),
           docs=("src/jason/community/statutory_terms.py",)),
    Lesson("temp-and-caches-followed-the-system-drive", date(2026, 10, 5), (Area.REPOSITORY,),
           "The system drive filled while the data sat on a drive with more than 500 GB free. Two index experiments "
           "left 6.2 GB and 4.2 GB copies of the project and its data (confidential) in the user's Temp, tests failed "
           "with OSError when Temp was nearly full, and the county index cache (4 GB) sat on the system drive.",
           "Python's tempfile, SQLite's sort spill (on Windows it follows TEMP and TMP, and ignores SQLITE_TMPDIR), "
           "OCR page images, pytest's tmp_path, and child processes all follow the OS temp folder, and nothing named "
           "where scratch goes. asspy reads only the process environment, so ASSPY_HOME written in .env moved nothing. "
           "A plain index build does not spill (measured: 0 bytes), so the large copies were made by hand. Settings "
           "by environment variable or a relative path also differ by launcher and working directory, and a program "
           "started from an application sees its own AppData: asspy's default home, resolved from an agent's shell, "
           "was a different folder from the one a terminal sees.",
           "JASON_TEMP_DIR (environment or .env) is applied when a command, jason-mcp, jason-web, the worker, a script, "
           "or pytest starts, and fails fast on a missing drive; jason.asspy_home.apply reads ASSPY_HOME from .env before "
           "asspy is asked for a county's file; jason storage lists each place with its drive, free space, and size, and "
           "--check flags a low drive and scratch on it; docs/scratch.md says where scratch goes and that a confidential "
           "copy stays on the data drive and is removed when the check ends. Each of jason, asspy, and lawlibrary now "
           "reads its own user config from the home folder (~/.jason/.env, ~/.asspy/.env, ~/.lawlibrary/.env), outside "
           "AppData and the same from any working directory; the environment wins, then a project's .env, then the "
           "user config; jason's relative path settings are taken from the checkout, not the working directory; and "
           "jason storage lists the files and where lawlibrary's archive resolves. No default is under AppData now "
           "(asspy ~/.asspy, lawlibrary ~/.lawlibrary/data on Windows, jason's locks ~/.jason/locks), and jason storage "
           "flags data left in an old default folder. Still a person's: TEMP and TMP at user level and PIP_CACHE_DIR.",
           Status.FIXED, guards=("config.apply_temp_dir",
                                 "asspy_home.apply",
                                 "config.user_config_path and config.env_file_values (tests/test_user_config.py: the "
                                 "user config is found from any working directory and under the project's .env)",
                                 "asspy.paths.configured and lawlibrary core.config_path (their tests)",
                                 "tests/test_storage.py: the lock folder defaults to the home folder; data left in an "
                                 "old default folder is a problem",
                                 "tests/test_storage.py: the setting moves tempfile, the environment, a child "
                                 "process, and pytest's tmp_path; a low drive and scratch on it are flagged",
                                 "tests/test_asspy_home.py: .env names the home and the environment wins"),
           docs=("docs/scratch.md", "docs/setup.md")),
    Lesson("anythingllm-retrieval-unmeasured", date(2026, 10, 4), (Area.DOCUMENTS,),
           "The board asked AnythingLLM's workspaces for weeks while jason's own hybrid search was being measured "
           "on the gold questions. Measured on the same 140 questions, the shared workspace found the answer in its "
           "top five 47% of the time; the hybrid, 89%.",
           "Each retriever was judged on its own terms: the hybrid had a gold set, and the catalogs had none. 25 of "
           "AnythingLLM's misses are text it never held (thin parses, documents never uploaded); the rest are "
           "exact numbers and citations it ranks by embedding alone, and it cannot be filtered by kind or scope.",
           "AnythingLLM was retired on October 4, 2026, after a snapshot of every workspace's document list "
           "(data/anythingllm/snapshots). The board's document_search searches the passage index (jason index "
           "--build), scoped by catalog and standing, and returns passages with their caveats for the client to "
           "answer from; a legal case's file is a confidential case-<key> catalog. scripts/eval_anythingllm.py still "
           "scores a workspace on the gold set. The mail, the reports, the docs, and the classified library joined the "
           "index on October 4, 2026 (jason.tasks.index_sources), and the case files' PDFs have text extracts beside them "
           "(jason cases --extract-text), each indexed with how it was read.",
           Status.FIXED, guards=("scripts/eval_retrieval.py --index", "tests/test_passage_index.py (document_search)",
                                 "tests/test_local_tools.py (board profile)"),
           docs=("docs/applicability.md", "docs/document-tools.md (model trials)", "docs/mcp.md")),
    Lesson("facts-in-general-patterns", date(2026, 10, 4), (Area.REPOSITORY,),
           "General readers matched the association's street names and its name word, with OCR's misreadings of it, "
           "in regular expressions, a stop-word list, and default arguments, and one task imported the profile's "
           "labels module by name. Another profile's letters, bills, and claims were then read as this one's, or its "
           "own name was stripped as if it were this association's.",
           "The rules \"Facts are data\" and \"Dependencies point one way\" were checked in the docs but not in code.",
           "Community.streets() and Community.name_pattern(), empty by default, hold the facts; readers build their "
           "patterns from them at call time (base.street_words, base.alternation, base.name_regex) and take the "
           "active profile through jason.community.community(). With none set, no address or name is read: a miss.",
           Status.FIXED, guards=("tests/test_profile.py: scan_code against tests/fixtures/code_boundary.json (only "
                                 "shrinks), the cleared modules kept out of it, and profile_imports empty",),
           notes=("Cleared 2026-10-05: the eleven modules the ratchet still tolerated (the name in model regexes and "
                  "defaults, the streets in community/scans.py, the index words in index_cache, the Workspace's name "
                  "on printed emails, the Drive names jason policies passes over) read Community.short_name, name, "
                  "name_pattern(), streets(), index_project(), gmail_print_names(), and not_policy_names(); the code "
                  "baseline is empty and tests/test_profile.py keeps it so. Still outside the check's reading "
                  "(docs/adapters.md, 'What the check does not see'): OPTIONS in tasks/board_packet.py and GROUPS in "
                  "tasks/request_sheet.py, the name word in four stop-word sets, the user agents, the parcel-number "
                  "prefix, and the escrow note in tasks/developer_security.py.",)),
    Lesson("wrapped-name-on-declarations", date(2026, 10, 5), (Area.DOCUMENTS,),
           "A reader that matched a crime declarations page by the association's full name read no named insured: the "
           "page wraps the name over two lines and the text layer gives the second line first.",
           "A literal that happened to match the page's order was replaced by the full name from the specification, "
           "which does not match the page's wrapped order.",
           "A general name match uses the name's leading words (contracts_ins_package._named_insured), and a reader moved "
           "from a literal to Community.name is reread on the real documents before the move is called done: dump the old "
           "and new readings read-only and diff them.",
           Status.FIXED, guards=("tests/test_profile.py: the reader test over a profile with no short name, index words, "
                                 "print names, or file exclusions; the real-data diff recorded in the commit that cleared "
                                 "the baseline",)),
    Lesson("agenda-executive-words-to-minutes-model", date(2026, 10, 4), (Area.GOVERNING, Area.DOCUMENTS),
           "jason board --minutes DATE gave the local model the agenda Doc's executive-session subitems word for word "
           "as headings, so an agenda that named a member, a party, or a matter under an executive item passed those "
           "words into the draft of the open minutes. The checks skipped the Executive session section, so --recheck "
           "could not catch it. Separately, draft() shadowed its own checks function with a local variable and would "
           "have raised UnboundLocalError on every run.",
           "The record treated the agenda's own wording as general words; nothing tied a subitem to an "
           "ExecutiveSubject, though CIV 4935(e) has a matter \"generally noted in the minutes\".",
           "Each agenda executive item reaches the model only by its 4935 subject in the statute's words: the agenda "
           "plan's subject when its board item matches, else classify_executive (labeled as jason's reading for the "
           "Secretary to confirm), else a blank for the Secretary. The checks and --recheck count lines about the "
           "executive session that use an item's own words (executiveParticulars), never quoting them.",
           Status.FIXED, guards=("tests/test_minutes_draft_executive.py (no executive item's words in the prompt "
                                 "from meeting_record or draft(); plan, then wording, then blank; recheck counts "
                                 "without quoting)",),
           docs=("docs/board-agenda.md (The executive session note)",),
           notes=("The agenda's carry-forward of executive headings: lesson executive-headings-copied.",)),
    Lesson("statute-miss-not-looked-up", date(2026, 10, 4), (Area.GOVERNING, Area.DOCUMENTS),
           "CIV 5350(a) applies Corporations Code 7233 and 7234, and code and caveats cited 7233, but neither was on "
           "the curated shelf, so jason cite answered statute_not_on_disk: an invitation to quote from memory.",
           "The shelf held only what the curated list named; a reader's miss stopped there, and lawlibrary, which "
           "holds the words locally, was never asked.",
           "CORP 7230-7238 is on the list. A reader's miss reads through statute_fetch.ensure: the local lawlibrary "
           "checkout is asked, the page written in the export's format with a Fetched line, listed under on_demand in "
           "the manifest, and logged in data/authorities/on-demand.jsonl. jason export-authorities lists on-demand "
           "sections no curated row holds, for a person to promote with a Basis. A miss names its reason (not in the "
           "library, library unavailable, worker failed); none is filled from memory.",
           Status.FIXED, guards=("tests/test_statute_fetch.py (fake worker: hit, miss, unavailable, failed, off, "
                                 "promotions)", "jason.community.cite.Reason (the distinct miss reasons)"),
           docs=("docs/citations.md (Misses; Caveats)",),
           notes=("Open for counsel: how CORP 7234 applies under CIV 5350(a), for BoardRule.interested_in_quorum.",)),
    Lesson("executive-headings-copied", date(2026, 10, 4), (Area.GOVERNING,),
           "meeting_agenda.agenda_items copied the last agenda's executive-session headings word for word into the "
           "next public agenda, with the notes under \"Adjourn to Executive Session\", so a heading that named a "
           "member, a party, or a matter was noticed again.",
           "The headings were treated as standing items, and nothing asked what the open agenda may say of an "
           "executive matter (CIV 4935(e)).",
           "executive_lines() names each matter only by its 4935 subject in the statute's words: the agenda plan's "
           "subject, else classify_executive flagged for the Secretary to confirm, else a blank. Old headings, item "
           "titles, and the notes under the adjourn heading are never copied.",
           Status.FIXED, guards=("tests/test_board_items.py::test_the_open_agenda_names_an_executive_matter_by_its_"
                                 "subject_only",),
           docs=("docs/board-agenda.md",)),
    Lesson("board-items-title-in-code", date(2026, 10, 4), (Area.REPOSITORY,),
           "tasks/board_items.SHEET_TITLE held the association's name, the title of the board's Sheet and Tasks list.",
           "A title made by hand for one association was written as a constant in general code.",
           "Community.board_items_title(), empty by default, with a fallback from the association's name; the "
           "profile keeps its exact old title, so the existing Tasks list is still found.",
           Status.FIXED, guards=("tests/test_board_items.py::test_the_board_items_title_comes_from_the_profile",)),
    Lesson("quorum-cite-hardcoded", date(2026, 10, 4), (Area.GOVERNING, Area.REPOSITORY),
           "The minutes template cited one association's bylaws section for the quorum, for every association.",
           "The profile's section number was written into a general string.",
           "BoardRule.quorum_source, passed to meeting_agenda.minutes_template from the profile.",
           Status.OPEN, guards=("tests/test_board_items.py (quorum_source in the minutes template)",),
           notes=("Still in general code: bylaws section numbers in community/minutes_template.py (SECTIONS), "
                  "models/meetings.py's minutes checks, and question_sets.py; the meeting schedule in "
                  "tasks/board_packet.py and the --date help (\"the next third Tuesday\").",)),
    Lesson("shared-tree-overwrite", date(2026, 10, 4), (Area.REPOSITORY,),
           "While an agent worked, another session's commit flow left src/jason/cli.py without the agent's "
           "uncommitted hunks, which it re-applied; and running scripts/gen_cli_docs.py --help regenerated "
           "docs/cli.md from the shared tree's parser, taking in every session's uncommitted commands.",
           "Several sessions share one working tree; a flow that rewrites a file from the index or HEAD drops "
           "others' uncommitted hunks, and the doc generator ignores its arguments and has no dry run.",
           "Nothing in code yet. Edits are re-checked before testing, commits stage only their own hunks, and a "
           "commit is tested in a worktree at HEAD (lesson commit-swept-another-sessions-hunk).",
           Status.OPEN,
           notes=("Wanted: gen_cli_docs.py honoring --help and a --check mode; each session in its own worktree.",
                  "The index is shared too: on 2026-10-04 another session's commit (ad36baa, paint and glyphs) took "
                  "this session's staged board-items fix with it. Stage and commit in one command, or commit from a "
                  "temporary index (GIT_INDEX_FILE) so another session's commit cannot sweep staged hunks.",
                  "A hunk is not a session's: a one-line change beside another session's uncommitted block shares its "
                  "diff hunk, and staging the hunk takes both (2026-10-04, styles.css, undone before any push). For a "
                  "small change in a file others are editing, stage HEAD's copy with only that change applied, and "
                  "check the staged diff's line count before committing.")),
    Lesson("marks-mixed-who-acted", date(2026, 10, 4), (Area.DOCUMENTS,),
           "The Decisions screen showed every recorded outcome as a green badge, denied included, and the design's "
           "glyph sheet mapped filed, a word for what jason did, to the stamp that marks a person's decision, with "
           "recorded, draft, and confidential among the stamps.",
           "There was no vocabulary for who acted: a person's decision and jason's act were drawn with the same marks.",
           "Stamp (a person's decision, in the motion's own word) and Seal (what jason did) have disjoint vocabularies; "
           "a county filing is the read seal with its instrument number; draft is the drafted seal; confidential is "
           "the P3 chip, a level. Routing tags take the owner the server resolved, never keywords. The Decisions "
           "screen stamps the outcome in its own word and tone.",
           Status.FIXED, guards=("ui/src/components/marks.test.tsx (disjoint words; filed is a seal; recorded, draft, "
                                 "confidential in neither; sent needs sentRef; unassigned routing)",),
           docs=("docs/console/components.md (Marks)",)),
    Lesson("packet-executive-titles", date(2026, 10, 4), (Area.GOVERNING, Area.DOCUMENTS),
           "jason board --packet, and the console's meeting page that renders it, listed each executive-session item "
           "by its title in the packet's contents, where a title can name a member, a party, or the matter.",
           "The packet predates the 4935 subjects; its executive line was written before the agenda and the minutes "
           "draft were fixed the same way (executive-headings-copied, agenda-executive-words-to-minutes-model).",
           "The packet names each executive matter by its 4935 subject through meeting_agenda.executive_lines: the "
           "agenda plan's subject, else jason's reading flagged to confirm, else a blank. Its research still goes to "
           "the directors separately.",
           Status.FIXED, guards=("tests/test_board_items.py::test_the_packet_names_an_executive_matter_by_its_subject_"
                                 "only",),
           docs=("docs/board-agenda.md", "docs/console/handoff-reconciliation-3.md (The board packet)")),
    Lesson("loader-refusal-became-500", date(2026, 10, 4), (Area.DOCUMENTS,),
           "A loader that refused a request (no sign-in, the owner view) through access.require or signed_in came "
           "back from the /api/<name> route as a 500, not its 401 or 403.",
           "The route caught every exception from a loader to report it, its own refusals included.",
           "The route lets a werkzeug HTTPException through; other errors are still reported.",
           Status.FIXED, guards=("tests/test_web_people.py::test_the_route_needs_a_sign_in",)),
    Lesson("board-roster-change-unrecorded", date(2026, 10, 4), (Area.ONBOARDING, Area.GOVERNING),
           "The People and offices screen says a change of office is the board's act, recorded in the minutes and "
           "then by the board-roster question with a second person's confirmation, but the board-roster onboarding "
           "item has no question to answer, and no term (director or officer) is kept.",
           "The roster was written as private facts by hand; the onboarding item only checks PayHOA's board tag.",
           "board-roster now asks a standing, high-stakes question (OFFICE; PERSON or vacant; the date the board "
           "acted; the minutes). Applied by a person after a second person confirms, it is appended to the officers "
           "topic, and roster.in_force makes the last act per office the holder. election-status asks each term "
           "(seat, person, start, end or at the pleasure of the board, the election record, the provision), appended "
           "to the terms topic and read by Community.terms() (Term, empty default). The People screen shows each term "
           "with its source, 'term ended; election due' only from a recorded end, and the change section names the "
           "question and its commands.",
           Status.FIXED, guards=("tests/test_roster.py (stakes and topic; standing while present; form refused; the "
                                 "route queues and waits on a second person; apply appends, never rewrites)",
                                 "tests/test_web_people.py (terms with sources; the change section's question)",
                                 "ui/src/views/people.test.tsx (terms, an ended term, the questions' commands)"),
           docs=("docs/console/screens/people.md", "docs/onboarding.md (The roster, as it changes)")),
    Lesson("setup-questions-buried", date(2026, 10, 4), (Area.ONBOARDING,),
           "The ranked onboarding questions put hundreds of OCR and drift questions above every fact question, so the "
           "first page of the console's setup had no question a person could answer about the association.",
           "rank scores legal clocks first, and the OCR readings of cited sections carry clocks.",
           "The setup read (GET /api/onboarding-session) defaults to fact and map questions and counts the rest, "
           "with jason intake to see them.",
           Status.FIXED, guards=("tests/test_web_intake.py::test_the_session_gives_five_gates_and_computed_statuses_"
                                 "and_no_answer",)),
    Lesson("keeper-answer-outside-access", date(2026, 10, 4), (Area.ONBOARDING,),
           "An item whose answer is a Keeper record's name (keys and codes) sits outside the access group, so treating "
           "only access items as connections would have offered a text field beside codes. The write route still "
           "accepts a Keeper record's title from any client, as the CLI and MCP do; only the view withholds the field.",
           "Connections were defined by group, not by what the answer is.",
           "A connect item is any item checked by a credential setting or answered by a Keeper record's name, "
           "whatever its group; it shows the terminal command only. intake.secret_reason still guards every value.",
           Status.OPEN, guards=("tests/test_web_intake.py (keys and codes is command-only)",),
           notes=("Decided 2026-10-04: onboarding credentials and integrations (Google Workspace's OAuth web "
                  "application, Keeper, PayHOA, Zoom) is an administrator's flow still to be built; until then the "
                  "console shows the terminal command and the route accepts a Keeper record's name as the CLI does "
                  "(docs/onboarding.md, Connecting integrations).",)),
    Lesson("signer-default-looks-chosen", date(2026, 10, 4), (Area.DOCUMENTS, Area.ONBOARDING),
           "Identity.signer defaults to \"Board of Directors\", so a profile that never named a signer reads the same as "
           "one that chose that wording.", "The default was written into the record instead of the templates.",
           "GET /api/community flags the signer default: true. Still to do: an empty default on Identity.signer, with "
           "the templates falling back to the general wording.",
           Status.OPEN, guards=("tests/test_web_community.py (the signer default is flagged)",)),
    Lesson("board-packet-p1-path", date(2026, 10, 4), (Area.GOVERNING, Area.DOCUMENTS),
           "jason.web.access.PATH_RULES places board/packet* at P1, so the directors' confidential packet "
           "(packet-<date>.md, privileged and mediation material) has the same file level as the members' copy "
           "(packet-<date>-members.md).",
           "The path rule was written before a members' copy existed; P1 is anyone on the roster.",
           "Nothing is exposed yet (the roster is officers and managers). Still to do before owner sign-in: the "
           "directors' packet at the level its header claims (for the directors and counsel), and the members' copy "
           "its own path rule. Which level reaches every director, and only them, is a decision for a person.",
           Status.OPEN),
    Lesson("subsidiary-motions-recorded-approved", date(2026, 10, 4), (Area.GOVERNING,),
           "The meeting room's \"Table the item\", \"Continue to a later meeting\", and \"Direct the manager to report "
           "back\" templates were main motions: a carried motion to table was recorded as approved, stamped carried, "
           "and the item never moved. Decisions were keyed <date>--<item>, so a second motion on the same item "
           "silently replaced the first decision.",
           "The room had no notion of a motion's kind, so every motion carried as approved.",
           "motion_draft takes a kind (table, continue with a meeting date, refer with whom); each is moved, seconded, "
           "and voted by roll call under the board's rules, applies to the pending motion, and when carried records "
           "its own word and moves the item (continued: its meeting; referred: the owner the board named). Withdraw "
           "is the mover's logged act before any vote. Subsidiary decisions are keyed --<kind>.",
           Status.FIXED, guards=("tests/test_meeting_room_subsidiary.py", "ui/src/components/subsidiary.test.tsx"),
           docs=("docs/console/screens/meetings-and-minutes.md (Table, continue, refer, and withdraw)",),
           notes=("Still open: two main motions on the same item at one meeting still replace each other's decision.",)),
    Lesson("credential-repr-showed-secrets", date(2026, 10, 5), (Area.ONBOARDING, Area.REPOSITORY),
           "The credential dataclasses (LoginCredentials, PayhoaCredentials, IdoxsCredentials, ZoomCredentials) showed "
           "passwords, one-time codes, and client secrets in their default repr, so a traceback or a debug log could "
           "carry them.", "Dataclasses print every field unless told not to, and no check looked for secret fields.",
           "The secret fields have repr=False, and the vault's Secret shows only its field names and cannot be pickled. "
           "A scan of every dataclass then found four more (Settings.keeper_password, the sign-in Client's secret, and "
           "two bill-view tokens), now hidden too.",
           Status.FIXED, guards=("tests/test_vault.py::test_credential_records_hide_their_secrets_in_repr",
                                 "tests/test_secret_fields.py"),
           docs=("docs/integrations-design.md (The vault)",)),
    Lesson("registry-reads-had-no-lane", date(2026, 10, 5), (Area.ONBOARDING,),
           "The integrations' refresh commands sync-catalog, meetings --sync, utilities --payments, schedule "
           "--read-google, and sync-tax fell to the local job lane, so scheduled reads were not kept on their "
           "account's lane.", "jobs.job_class knew only the commands people had queued by hand.",
           "Those commands are classed in their account's lane (PayHOA, Google, county).",
           Status.FIXED, guards=("tests/test_scheduler.py::test_each_registry_read_takes_its_accounts_lane",),
           docs=("docs/jobs.md",)),
    Lesson("scheduled-defaults-need-adoption", date(2026, 10, 5), (Area.ONBOARDING,),
           "The registry's cadences are proposed defaults, but a scheduler that ran them at once would start reading "
           "Gmail every ten minutes and PayHOA nightly the first time jason serve booted.",
           "Which cadences a community runs is the administrator's or the board's choice (open decision 2).",
           "The scheduler runs a source only after a person adopts it: jason cadence --restore SOURCE|--restore-all, or "
           "--every/--cron, recorded with who and when.",
           Status.DECISION, guards=("tests/test_scheduler.py",), docs=("docs/scheduler-daemon-design.md",)),
    Lesson("retry-after-not-printed", date(2026, 10, 5), (Area.ONBOARDING,),
           "The scheduler honours a Retry-After line in a job's output, but no client prints one.",
           "The shared backoff helper the design names is not built.",
           "The backoff helper prints Retry-After when it gives up.", Status.OPEN,
           docs=("docs/scheduler-daemon-design.md",)),
    Lesson("keeper-login-does-not-clear-sign-in-pause", date(2026, 10, 5), (Area.ONBOARDING,),
           "A sign-in pause clears only on a later successful jason integrations check --live or jason cadence "
           "--resume; a bare jason login leaves the Keeper-based sources paused.",
           "jason login records no check.", "Decide whether jason login records a check that clears the pause.",
           Status.OPEN, docs=("docs/scheduler-daemon-design.md",)),
    Lesson("calendar-and-tasks-share-a-command", date(2026, 10, 5), (Area.ONBOARDING,),
           "The calendar and tasks sources both run schedule --read-google, so they share one job and Tasks runs at "
           "Calendar's cadence, not its own.", "One command reads both.",
           "Give each its own command or flag.", Status.OPEN, docs=("docs/integrations-design.md",)),
    Lesson("scheduler-log-unrotated", date(2026, 10, 5), (Area.ONBOARDING,),
           "<data>/jobs/scheduler.jsonl grows without bound.", "The rotating serve log is not built yet "
           "(serve-logs-nowhere-under-task-scheduler).", "Rotate it with the serve log.", Status.OPEN,
           docs=("docs/scheduler-daemon-design.md",)),
    Lesson("a-test-could-sign-in-to-keeper", date(2026, 10, 5), (Area.REPOSITORY,),
           "Any test that reached VaultSession.open on a machine with a real Keeper config could try a network login.",
           "Nothing stopped a test from using the person's own Keeper device token.",
           "An autouse fixture makes login_to_vault raise KeeperAuthRequired; a test that fakes Keeper sets its own.",
           Status.FIXED, guards=("tests/conftest.py (_no_keeper_login)",)),
    Lesson("credential-readers-env-only", date(2026, 10, 5), (Area.ONBOARDING,),
           "Every credential reader (PayHOA, the utilities, Accela, the vendor portals, Zoom, PostScanMail, the Google "
           "client, console sign-in) read a Keeper record UID from .env, one set per installation.",
           "Credentials were wired for one association before communities had vault paths.",
           "Each reads the community's vault path first and falls back to the .env record with a deprecation note; "
           "jason sign-in --import-client and jason zoom --store-app write the vault path, create-only; integrations "
           "and onboarding count a vault-only credential as set.",
           Status.FIXED, guards=("tests/test_vault.py (each caller: vault, then .env, then the old error)",
                                 "tests/test_web_signin.py"),
           docs=("docs/integrations-design.md (build step 2)",),
           notes=("Still open: Google tokens per community and account (build step 3); the .env sign-in fallback is "
                  "offered only while its .env key is set; jason onboard's session view and the onboarding MCP tools "
                  "still test .env alone.",)),
    Lesson("worker-guard-per-machine", date(2026, 10, 5), (Area.ONBOARDING,),
           "The job worker's single-instance guard carried no community, so a second community could not run a worker; "
           "and once guards were per community, two communities' model jobs could load on the card at once.",
           "The worker was written for one association on one machine.",
           "The guard is jobs-worker-<profile>; a machine-wide jobs-gpu-lane lock covers the GPU lane, and a model job "
           "that finds it taken waits without spending an attempt. PayHOA writes hold the community's account lock "
           "(locks.account), so two batches for one community no longer run at once.",
           Status.FIXED, guards=("tests/test_serve.py",), docs=("docs/jobs.md", "docs/scheduler-daemon-design.md")),
    Lesson("serve-logs-nowhere-under-task-scheduler", date(2026, 10, 5), (Area.ONBOARDING,),
           "Under Task Scheduler, jason serve's printed lines go nowhere; only the heartbeat's refused and failed fields "
           "and each job's own log remain.", "The service was built before its log.",
           "The design's rotating data/<profile>/serve.log is still to build.",
           Status.OPEN, docs=("docs/scheduler-daemon-design.md",)),
    Lesson("task-restart-on-failure-limits", date(2026, 10, 5), (Area.ONBOARDING,),
           "Task Scheduler restarts a jason serve that exits with a failure, but not one that hangs; a hung serve shows "
           "only as stale in jason daemon status.", "Restart-on-failure watches the exit, not the heartbeat.",
           "A watchdog that acts on a stale heartbeat (or a service wrapper that does) is still to choose.",
           Status.OPEN, docs=("docs/scheduler-daemon-design.md",)),
    Lesson("sources-declare-no-freshness", date(2026, 10, 4), (Area.ONBOARDING, Area.REPOSITORY),
           "The administrator's Status screen can say a data source is current or stale only by a threshold the source "
           "declares, and none does, so every source shows its age with no standing word.",
           "How often each source should be read was never written down; jobs refresh them on a person's command.",
           "Status reads Source.stale_after_days with stale_source naming where the threshold is written, and shows "
           "the age alone until one is. A Keeper sign-in cannot be checked from disk, so a Keeper source reads "
           "\"not signed in\" only after a failed job or refresh. Since 2026-10-05 each source takes its threshold from "
           "its integration's cadence (jason.integrations.registry), the defaults from rate limits.",
           Status.FIXED, guards=("tests/test_web_status.py::test_each_source_takes_its_integrations_threshold",
                                 "tests/test_integrations.py::test_floors_and_thresholds_hold_against_each_cadence",
                                 "tests/test_web_status.py (no invented standing)"),
           docs=("docs/console/screens/status.md", "docs/integrations-design.md (Defaults from rate limits)"),
           notes=("The figures are defaults until the administrator or the board adopts them "
                  "(docs/integrations-design.md, open decisions).",)),
    Lesson("nul-is-a-tty", date(2026, 10, 5), (Area.ONBOARDING, Area.REPOSITORY),
           "An agent ran jason integrations check zoom --live with stdin redirected from NUL; on Windows NUL answers "
           "isatty() True, so the guard meant for a person at a terminal let one read-only Zoom call through and "
           "recorded it as a check (the record was removed).",
           "The guard asked isatty(), which a character device answers yes to, not whether stdin is a console.",
           "jason.commands.integrations.at_terminal asks Windows for the console's mode (GetConsoleMode); "
           "jason integrations check --live and jason vault migrate --yes use it.",
           Status.FIXED, guards=("tests/test_integrations.py (at_terminal gates --live)",),
           notes=("Prompts that rely on input() rather than isatty() are not covered; an agent's --yes is still "
                  "refused only by the agent's own rules.",)),
    Lesson("cadence-without-status-row", date(2026, 10, 5), (Area.ONBOARDING,),
           "Calendar, Tasks, i-doxs, and the vendor portals have cadences but no Status row, so their integrations read "
           "\"never read\".", "Their stores keep no last-read stamp Status reads: the vendor portals' account.json has "
           "none, and Calendar and Tasks share one stamp (schedule/google-read.json) and one command.",
           "Status rows for i-doxs (its sync runs) and Calendar and Tasks, and a syncedAt in the vendor portals' sync.",
           Status.OPEN, docs=("docs/integrations-design.md",)),
    Lesson("executive-title-in-console-agenda", date(2026, 10, 4), (Area.GOVERNING,),
           "board_items.agenda(), which the console's meeting page renders, prints executive items by their title and "
           "ask; the meeting and plan loaders also listed every executive item's title, ask, and id to anyone.",
           "It predates meeting_agenda.executive_lines and the private view.",
           "agenda() names the executive session by executive_lines with the agenda plan's subjects, so the draft and "
           "the minutes frame carry no title. GET /api/meeting and /api/agenda-plan answer an executive item whole "
           "only in the private view (logged); otherwise a held row with its 4935 subject. The meeting room and the "
           "plan call them whole (private=True) and hold back themselves; the UI records no decision on a held row.",
           Status.FIXED,
           guards=("tests/test_board_items.py::test_the_console_agenda_names_an_executive_matter_by_its_subject_only",
                   "tests/test_meeting_room_executive.py::test_the_meeting_loader_lists_executive_titles_only_in_the_"
                   "private_view",
                   "tests/test_agenda_plan.py::test_outside_the_private_view_an_executive_candidate_is_held_by_its_4935_"
                   "subject"),
           docs=("docs/console/screens/meetings-and-minutes.md",)),
    Lesson("teleconference-reminder-paraphrased", date(2026, 10, 4), (Area.GOVERNING, Area.DOCUMENTS),
           "meeting_agenda.format_lines and the agenda template word the 4926(a)(1)(C) individual-delivery reminder in "
           "jason's own phrasing.", "They were written before the rule to recite, not paraphrase.",
           "The agenda's reminder now says a member may request individual delivery of meeting notices (4926(a)(1)(C)) "
           "and recites 4045(b) and 4041(a)(1) from the statutes on disk through the board meeting notice's own helpers "
           "(meeting_notice.delivery_recitals, delivery_lines), with where to write; a statute not on disk is a "
           "highlighted miss, and jason board --agenda says so. The agenda template's note points to that section "
           "(\"How notices are delivered\", meeting_agenda.delivery_section) instead of wording the law.",
           Status.FIXED, guards=("tests/test_meeting_notice.py::test_the_teleconference_agenda_recites_the_notices_"
                                 "delivery_statutes", "tests/test_meeting_notice.py::test_the_agendas_reminder_shows_a_"
                                 "missing_statute_as_a_miss", "tests/test_meeting_notice.py::test_the_agenda_template_"
                                 "points_to_the_recited_section"),
           docs=("docs/board-agenda.md", "docs/base-templates.md")),
    Lesson("board-items-list-executive-titles", date(2026, 10, 4), (Area.GOVERNING,),
           "GET /api/board-items, behind the console's Board items screen, listed every executive-session item whole "
           "to anyone who could load the page (title, summary, ask, authority, notes, evidence, id); its card offered "
           "the board-fields form, and a write to an executive item answered the whole item.",
           "The fix for the meeting page and the agenda plan (executive-title-in-console-agenda) held back those two "
           "loaders only; the board items loader and its write were another path to the same items.",
           "sources.board_items answers an executive item whole only in the private view, logged; otherwise a held "
           "row (executive-<n>, its 4935 subject's general words from the agenda plan, else \"An executive-session "
           "matter\", and its status, priority, meeting, and due date). set_board_item answers an executive item as "
           "missing (404) outside the private view. The screen shows a held row with no details and no board fields. "
           "The held row is one helper for every path (jason.tasks.board_items.hold_executive): the stdio MCP tool "
           "board_items holds executive items back unless include_confidential; the evidence for board-item:<id> is "
           "labeled by its 4935 subject and held outside the private view, whole inside it with level P3 and a line in "
           "access/served.jsonl; a DocRef to one is P3 and named by its subject.",
           Status.FIXED, guards=("tests/test_meeting_room_executive.py::test_the_board_items_listing_holds_an_executive_"
                                 "item_back_outside_the_private_view",
                                 "tests/test_meeting_room_executive.py::test_a_held_board_item_with_no_planned_subject_"
                                 "says_only_executive_session", "ui/src/views/views.test.tsx (the held executive item)",
                                 "tests/test_meeting_room_executive.py::test_the_mcp_board_items_tool_holds_an_executive_"
                                 "item_back_unless_asked",
                                 "tests/test_meeting_room_executive.py::test_the_evidence_labels_an_executive_item_by_its_"
                                 "subject_outside_the_private_view",
                                 "tests/test_private_view.py::test_an_executive_items_summary_and_notes_come_back_in_the_"
                                 "window"),
           docs=("docs/console/screens/board-items.md", "docs/web-ui.md", "docs/mcp.md",
                 "docs/console/security-and-privacy.md"),
           notes=("Still outside this fix: the board-item:<id> address carries the id the caller gave, and an "
                  "approval's own stored evidence label for an executive item may name its title (approval_show).",)),
    Lesson("backflow-letter-goes-whole-to-the-tester", date(2026, 10, 4), (Area.DOCUMENTS, Area.ONBOARDING),
           "A water supplier's annual backflow letter lists each assembly with its ID and due date, and the supplier mails one "
           "letter an assembly; the association forwarded one of them to its tester. A county notice of non-compliance "
           "followed a test that the county had no report of; a failed assembly was repaired 44 days after its test, past the "
           "15 the notice gives, and the repair notice was postmarked nine days after its date.",
           "The tester needs the IDs to file in the program's portal, nothing confirms the filing, and the notice's clock runs "
           "from a date the mail may not match.",
           "Forward every page of every letter the day it arrives; ask for the portal's receipt and each tag number after the "
           "test; read a repair notice's date against its postmark; check the tester against the program's lists each year "
           "(docs/cross-connection-control.md). A person does these: jason files no report and calls no tester.",
           Status.OPEN,
           docs=("docs/cross-connection-control.md",)),
    Lesson("kinds-in-other-stores-were-gaps", date(2026, 10, 4), (Area.DOCUMENTS, Area.ONBOARDING),
           "The shelf of document kinds showed seventeen kinds with no files, among them tax returns, utility bills, a "
           "title company's resale demand, and security reports, although a search of Gmail and the Drive found all four: "
           "the library holds only what PayHOA's document library holds. Ingesting the finds then classified five by "
           "rule and left a preparer's tax-return package (a cover letter that lists the forms) and the demand "
           "unplaced; the package was called a form.",
           "The phrase rules named a tax return only by a form's title in the opening words, and a resale demand only by "
           "the words escrow, resale, or demand, which a title company's request may not use. A kind with no files in the "
           "library is not proof the association has none.",
           "A package's cover letter and a title company's request each have a phrase rule (ContentRule, tax return and "
           "escrow request). The kinds' shelf says where a missing kind would come from, and a gap is read against the "
           "mail and the Drive before it is called missing. A library folder for utility bills and security reports is "
           "the specification's, for a person to name.",
           Status.FIXED,
           guards=("tests/test_content_rules.py (a preparer's cover letter is a tax return; a title company's request is "
                   "an escrow request)",),
           docs=("docs/console/screens/document-kinds.md",),
           notes=("Not yet: the library ingests nothing from Gmail or the Drive until a person answers the folder "
                  "questions an ingest asks.",)),
    Lesson("ladder-named-an-article-not-words", date(2026, 10, 4), (Area.DOCUMENTS, Area.GOVERNING),
           "The loss packet's first run held step three: \"Provision not found on file\" for the declaration's article on "
           "damage and casualty, a provision the documents do hold.",
           "The ladder row named the article by its title (\"decl#Article 11\"), which the shelf does not know; and an article "
           "number alone resolves to an outline of its sections, never to words, so even \"decl#11\" would have recited nothing.",
           "The row names the operative sections (\"decl#11.1\", \"decl#11.2\"). A test resolves every provision of the "
           "profile's ladder against the shelf and fails on any that comes back without words.",
           Status.FIXED,
           guards=("tests/test_unit_records_view.py::test_every_provision_of_the_profiles_ladder_recites_words_from_the_shelf",),
           docs=("docs/unit-records-backend.md",)),
)


def lessons(community: object | None = None) -> tuple[Lesson, ...]:
    """The general lessons, then the community's own (``Community.lessons()``), if it keeps any."""
    own = getattr(community, "lessons", lambda: ())() if community is not None else ()
    return LESSONS + tuple(own)


def lesson(key: str) -> Lesson | None:
    """The general lesson filed under ``key``, or None."""
    return next((row for row in LESSONS if row.key == key), None)


def for_area(area: Area, community: object | None = None, *, open_only: bool = False) -> list[Lesson]:
    return [l for l in lessons(community) if l.applies_to(area) and (not open_only or l.status is not Status.FIXED)]


def lines(found: list[Lesson]) -> list[str]:
    """Lessons as Markdown list items: what happened, what changed, its status and guard."""
    out = []
    for l in found:
        guard = f" Guarded by: {'; '.join(l.guards)}." if l.guards else ""
        out.append(f"- **{l.key}** ({l.status.value}, {l.learned.isoformat()}): {l.what} {l.change}{guard}")
    return out


__all__ = ["Area", "LESSONS", "Lesson", "Status", "for_area", "lesson", "lessons", "lines"]
