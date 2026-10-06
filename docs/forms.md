# Paper forms: the reference for agents

This page maps the forms jason makes, sends, and reads back. The first form is the owner information form, the Civil Code 4041 annual request. Each part has its own page; this one says where everything is, what must never happen, how to extend it, what has been measured, and what is still open. It was written October 1, 2026. This association's findings are in its private notes (mystique/notes/forms.md).

## The life of a form

| Stage | What happens | Code | Detail |
|---|---|---|---|
| 1. Define | The questions, their kinds, what each answer holds (`ReadAs`), the two-letter marker code, and which tag each answer sets | `mystique/forms.py` (`OWNER_INFO`, `OWNER_INFO_CYCLE`, `SUGGESTED_CHOICES`), `mystique/tags.py`, `mystique/help.py`; types in `jason.community.forms`. The forms the law requires of every association under it (the records request, the request to meet and confer) are built into the form library, `src/jason/community/form_library/` (`jason form-library`); the association's slots and own forms are `Community.form_slots()` and `Community.custom_forms()`, and everything that makes or reads a form asks `Community.forms()` | [owner-information.md](owner-information.md), [form-library-design.md](form-library-design.md) |
| 2. Render | The cover letter and form as a Google Doc (refreshed in place), its PDF, and the fillable form; labels kept with their answers across a page break; links on every page | `jason packet owner-information --build --yes`; `tasks/packets.py`, `community/fillable.py`, `community/form_render.py`, `community/links.py` | [drafts-and-forms.md](drafts-and-forms.md), [letters.md](letters.md) |
| 3. Plan | Who gets what: the emailed pre-filled copy, the mailed blank letter, suggested choices, occupancy signals, the county roll as a hint | `jason owner-info --send-plan`; `tasks/owner_send.py`, `tasks/owner_prefill.py`, `tasks/owner_county.py` | [owner-information.md](owner-information.md) |
| 4. Mark | A printed marker at each page's top right and the same marker as a gray bar mark at the top left; a campaign for the mailed letter, a copy for each emailed one. A marker is made only for a form with an open campaign (`jason campaigns --open`): the person who opens it chooses the handler, and each sent copy's entry points at its campaign | `community/form_refs.py`, `community/form_marks.py`, `fillable.stamp_reference`, `tasks/campaigns.py` | [form-identifiers.md](form-identifiers.md) |
| 5. Send | One engine per channel, run slowly from a resumable ledger | `tasks/delivery_engines.py`, `jason.batches`; `jason owner-info --email-batch` / `--mail-batch`, `jason batches` | [batches.md](batches.md) |
| 6. Return | A PayHOA form submission, a Google Form response, a typed PDF or a paper scan in a reply email, or a mailed return scanned by the mail service. **The inbox** finds each (`jason responses`), keeps it under `data/responses/`, reads its attachments, and makes a person's confirmed reading the same `FormAnswers` a submission becomes | `tasks/response_inbox.py` (`check`, `read`, `confirm`, `keyed_answers`), `tasks/member_preferences.py`, `fillable.read_answers`, `form_reader.read_scan`, `tasks/form_references.lookup` | [responses-design.md](responses-design.md), [form-reader.md](form-reader.md) |
| 7. Read | Align the scan to the form, drop the form out, read boxes and writing; the reading hints; the vision model | `community/form_layout.py`, `community/form_reader.py`, `community/form_hints.py`, `form_reader.VisionReader` | [form-reader.md](form-reader.md) |
| 8. Compare and record | Each answer against what was on file (unchanged, changed, added, cleared), then tag writes in PayHOA | `owner_prefill.compare`; `tasks/owner_info.py` (`plan_writes`, `execute`); `jason owner-info ... --yes` | [owner-information.md](owner-information.md) |
| 9. Test | Made-up returns of the real form, scanned badly and scored; layouts and readers compared | `jason form-fuzz` (`tasks/form_fuzz.py`), `jason form-lab` (`tasks/form_lab.py`), `tasks/form_scans.simulate` | [form-fuzzer.md](form-fuzzer.md), [form-design.md](form-design.md) |

## Formats: print and screen

One definition, three media. The layout rules for each are `FormStyle` on the form (`mystique/forms.py`; the type in `jason.community.forms`), set from the layout lab's results ([form-design.md](form-design.md)).

**Print** (the mailed letter, filled by hand and scanned):
- **What it controls:** `FormStyle.write_height` (22 pt; the forms standards' 8 mm) and `line_gray` (0.6).
- **Where it's drawn:**
  - The Doc renderer gives each writing line, a paragraph of underscores, that much room above it in pale ink (`DocStyle.write_above`, `write_ink`, set by `tasks/packets.template_style`). A signature line gets the room too, and only its blanks are pale.
  - The HTML version (`form_render.paper_html`) does the same in CSS.
- **Why:** at 22 pt the lab's writers kept their writing off the print and in its space, and a black line hurts even a vision model (0.88 against 0.97 for a 60% gray line).
- **Keep:** the labels in a proportional face (Arial or Helvetica, 11 pt). Monospaced type breaks alignment.
- **Avoid:** combs and character boxes, which hurt every reader.

**Screen, the emailed fillable PDF** (typed into, then emailed back or printed):
- **One single-line field a writing line** (October 1, 2026).
  - A multi-line field over two rules put its second line on the first rule. Viewers also set a multi-line field's line spacing differently (1.12 to 1.35 times the type size), and one showed it as a single scrolled line.
  - So each blank is its own field. The first keeps the question's field name; further lines are `name#2`. Filling splits a value across them (`pdf_fields.split_lines`), and reading joins them back (`join_lines`, `form_reader._join_lines`).
- **Field placement** (`fillable.field_geometry`):
  - Every viewer centres a single-line field's text vertically: MuPDF, pdf.js, PDFBox, Acrobat, and PDFium. Apple's PDFKit draws its own.
  - So each field is about 18 points tall, placed so the baseline sits about 4.5 points above the rule, and runs about 1.5 points below it.
  - The rule is a row of pale underscores, about a point above the bottom of its text line.
  - On 30 typed, printed, and scanned cases this read as well as the old full-height fields (75% against 74%). A 2.5-point gap looked nicer but let blurred scans merge the letters' feet into the rule.
- **The scan reader's box is the writing room, not the field** (`form_layout.read_layout`). It runs from the rule up the form's writing height, stops at the printed line above, and ends a point below the rule so it never reaches the next label.
- **Addresses are written in their parts** (`FormQuestion.in_parts`, `form_render.ADDRESS_ROW`).
  - The street line, then "City ___ State ___ ZIP ___" on one row. Each blank is a field: the street keeps the question's name; the rest are `#city`, `#state`, `#zip`.
  - State takes at most 2 characters and ZIP at most 10. A filled value is parsed into its parts; one that doesn't parse stays whole on the street line for a person.
  - Online, PayHOA has one box, with the help "Street, city, state, and ZIP."
- **The usual answer is a box** (`FormQuestion.same_as`). "Same as my unit address" sits before the mailing address, and the emailed copy arrives with it checked when the owner's mail goes to the unit. "Only if it is not your unit address" went unread. Checked with nothing written, the answer is the unit; an address written out stands.
- **Reading addresses forgivingly** (`postal.read_mailing_address`, `form_hints`):
  - A street line at one of the community's units (the number and street, in any case, with a short suffix) is completed with the community's city, state, and ZIP (`Community.unit_city_state_zip`).
  - A misread or missing state is put right from the ZIP (`postal.state_for_zip`, USPS ZIP prefix ranges), marked as a hint.
  - Suffix spellings (DRIVE, DR; WALK, WLK, WK) were already read alike (`normalize_address`).
- **Spellcheck off** on names, addresses, emails, and phone numbers (`DoNotSpellCheck`). Each blank's tooltip says what it holds ("street address", "city", "ZIP").
- **Typed size:** answers print at `FormStyle.typed_size` (10 pt). It was 8 pt, which a home scan misreads.
- **No input checks in the PDF** (research of October 1, 2026).
  - Format and validation scripts (AFSpecial_Format and the like) run in Acrobat, in Firefox's pdf.js, and probably in Chrome. They don't run in Edge, Apple Preview or iOS, or Android viewers.
  - Mail filters treat any `/JS` or `/AA` in a PDF as a red flag, and some strip or quarantine it. No script is "safe".
  - The no-script tools are used instead: boxes and choices, MaxLen on State and ZIP, no spellcheck on exact answers, and tooltips. Required is shown only by pdf.js (a red outline), and enforced by no viewer when a PDF is emailed back.
- **Screen and print.** A widget's Print and NoView flags, and optional content (layers), can keep content to the screen or to paper. Chrome, pdf.js, and Acrobat honour them; Preview may show both. Every field keeps its Print flag, so typed answers print. Nothing is screen-only yet: a page has to read correctly in a viewer that shows everything.
- **Where checks happen instead:** at reading time (`form_hints`, marked) and in the online form.
- **No submit button.** A PDF can carry a SubmitForm action that posts its fields (FDF, XFDF, HTML, or the PDF) to a web address or a `mailto:`, but only Adobe Acrobat and Reader carry it out. Chrome's and Edge's viewers, Safari and Preview, and Firefox's pdf.js ignore it (October 2026). An owner whose button did nothing would think the form was sent.
- **The return path is the email link.** Every viewer follows a `mailto:` link. `stamp_reference` puts the copy's reference in each link's subject (`fillable.with_reference`: "Owner Information Form 2027 [Ref NP27E-…]"), so a reply from any mail program comes back already matched to its copy. The owner attaches the saved PDF; `read_answers` reads its fields, and its hidden reference field confirms the copy.
- **The online form is the submit button.** For a submit that works everywhere, the PDF links to the PayHOA form (and the letter prints its QR code).

**Screen, the PayHOA online form:**
- PayHOA's builder checks what it can (`form_render.payhoa_questions`, `payhoa_sheet`).
- It is the channel to send owners to: answers arrive typed and need no reading.

`jason form-fuzz --lint` checks a built form against its style:
- writing space under `write_height`;
- writing lines darker than `line_gray`;
- typed answers under `typed_size`;
- monospaced type.

## Changing the PayHOA form

**Never delete a live form.** Edit it in place. Deleting a form deletes its link, and the letter, its QR code, and the emails all point to it.
- **Locked:** once something sent links to a form, it is locked (`payhoa_forms.lock`, the `locked` reason in `data/payhoa/forms.json`). `--replace` refuses it, and `jason forms` offers only `--update`.
- **Checked before a send:** each owner-information mailing or email batch first checks that the form is still in PayHOA, switched on, and the one the link names (`payhoa_forms.live_problem`). A batch stops otherwise, because a person can still delete it in PayHOA's own screens.
- `jason forms --payhoa owner-info --update` shows the edit as a dry run. With `--yes` it saves it (`payhoa_forms.update`).
- The save is PayHOA's editor's own call: `PATCH /organizations/{org}/form-builder/{id}` with the whole form (`client.update_form`, from "payhoa form edit.har").
- **Ids are kept.** Each live question is matched to the definition by type and label. A kept question and its options keep their ids, so the answers already submitted stay readable. A new one goes as id 0, and PayHOA numbers it.
- **Read it back.** PayHOA's save answers with the form as it was, so the form is read again and the field-to-question record (`data/payhoa/forms.json`) is rebuilt from that.
- **Removing a question wasn't captured.** An edit that would drop one is refused; remove it in PayHOA's editor.
- **A "plaintext" question** is a block of text with no answer, for instructions within the form.
- **Submission notices:** who is emailed on each submission is the whole list of memberships (`client.set_form_recipients`).
- **Help text is cut at 255 characters.** PayHOA keeps that much of a question's help; `payhoa_forms.request_body` refuses longer help.

## A submission's life in PayHOA

Each call is in the PayHOA client, from the captures named. Each answers with nothing useful, so read the submission again (`get_form_submission`) to see the change.

| Step | Call | Client |
|---|---|---|
| An owner submits | `POST /organizations/{org}/unit-form-submissions`: `formId`, `unitId`, `answers` (only those answered; a dropdown by its option's value, a checkbox "true"/"false"), `sendNotificationToOwner` | `submit_unit_form` |
| An admin submits for a unit | `POST /organizations/{org}/form-submissions` (an owner's login gets 403) | `create_form_submission` |
| Mark complete / re-open | `POST .../form-submissions/{id}/complete` with `isToggleOn` true or false; complete sets `status` "complete" and `completionDate` | `set_submission_complete` |
| Comment (the owner sees it) | `POST /form-submissions/{id}/comments`: `message` (HTML), `notifyAdmins`, `recipientMemberIds` | `add_submission_comment` |
| Internal note | `POST /organizations/{org}/submissions/{id}/notes`: `note` (HTML), `private`, `recipientMemberIds` | `add_submission_note` |
| Notify (sends email) | `POST .../form-submissions/{id}/notification`: `emailOwners`, `emailAdmins`, `memberIds` | `notify_submission` |
| Edit the answers | `PATCH /organizations/{org}/form-submissions/{id}`: `unitId`, `answers` (each with its `answerId`) | `update_form_submission` |
| Delete | `DELETE /organizations/{org}/form-submissions/{id}` | `delete_form_submission` |

**Reading answers:** PayHOA stores a dropdown answer as the option's label, and a checkbox as an icon: `fa-check-square-o` checked, `fa-times` not (`payhoa_forms._truthy`).

**Testing from an owner's side:** `jason forms --payhoa-test owner-info --yes` submits made-up answers to every question as the test owner (`payhoa_test_record_uid`, a membership named in `payhoa_test_membership_ids`), reads them back as the admin, and compares. The test accounts and the operator's own membership and unit (`payhoa_my_membership_id`, `payhoa_my_unit_id`) live in `.env`, never in code, fixtures, or the specification; `--only me` sends a test to the operator's own unit.

**Completing an owner's request** (`owner_info.to_complete`, `complete`):
- `jason owner-info --apply --payhoa --yes` marks an owner's PayHOA owner-information request complete once it has recorded all of it. That means the request is the owner's latest answer, its tag writes are made, and it names nothing a person enters (an email or mailing address, a second delivery, a legal representative, a manager).
- It leaves the comment `OWNER_INFO_COMPLETED_COMMENT` (`mystique/forms.py`), emailed to that owner only.
- A request that still needs a person stays open, and the run lists what is left.
- A test account's request is never completed this way.

**What jason never does:**
- Delete an owner's submission. It is the record of their election. The client's delete is for a test jason made.
- Edit an owner's answers.
- Approve, deny, or assign a request (AGENTS.md). Completing a fully recorded owner-information request is the one exception.

## Channels and assurance

Only a signed-in answer proves who sent it.
- **Every other channel** carries evidence, ranked by `forms.Assurance` and judged by `community/assurance.assess`.
- **Recording:** a change is recorded at `RECORD_AT` (`mystique/forms.py`, `TOKEN`) or above.
- **Confirmation:** a return below `MATCHED` is first told to the address on file ("we received this change; tell us if it wasn't you").

| Channel | Usual level | Why |
|---|---|---|
| PayHOA form (`app.payhoa.com/app/forms/FORM_ID;unitId=UNIT`) | SIGNED_IN | The owner signed in. **The official channel.** The link must name the owner's unit: without `;unitId=` the form opens only for an administrator. `payhoa_forms.owner_link` makes it, the email batch adds each copy's unit, and `live_problem` refuses a bare link, so a letter that is the same for every owner cannot carry one. The printed form gives the way instead ("online in PayHOA: sign in, choose Requests, then Owner Information and Notice Delivery Preferences"), and each emailed copy makes those words its unit's link (`fillable.link_phrase`). |
| Reply email with the emailed copy's reference | MATCHED | From the address on file, quoting that owner's own reference |
| Google Form opened from the owner's personal link | TOKEN, or MATCHED if the typed email is the one on file | The link pre-fills the reference only that owner's email held |
| Signed paper letter | CLAIMED | Names the unit and comes by the Association's mailing; anyone can sign |
| Google Form opened without a personal link | CLAIMED with the email on file typed, otherwise LEAD | No sign-in, no reference |

**The Google Form** is `GOOGLE_FORMS[FormKey.OWNER_INFO]` in `mystique/forms.py`, made by `jason forms --create owner-info --yes`.
- **What it carries:** the preamble with the answer-by date, the section headings, the questions, a required certification box, and an optional reference question.
- **Respondent email:** typed (`RESPONDER_INPUT`). A Google sign-in (`VERIFIED`) would raise the level but cost the convenience the form exists for.
- **Publishing:** it's unpublished until a person runs `jason forms --publish ID --yes`. Unpublish with `--unpublish`.
- **Personal links:** `{GOOGLE_FORM_LINK}` in the email message gives each owner a link with only their copy's reference pre-filled (`google.forms.prefill_url`). Never put a name, an address, or an email in a link.
- **Pre-filled link numbering:** `entry.<n>` in a link is the API's hexadecimal question id read as a decimal. Confirm it the first time a form is published: open one personal link, submit a test answer, and check the response carries the reference.

## Modules

| Module | Layer | What it is |
|---|---|---|
| `community/forms.py` | types | `FormTemplate`, `FormQuestion` (`reads`, `reads_as`), `QuestionKind`, `ReadAs`, `FormKey`, `FormAnswers`, `SuggestedChoices` |
| `community/form_refs.py` | implementation | The marker: 23-character alphabet, two check characters (mod 23) that catch and repair one misread, `make`, `parse`, `repaired`, `closest`, `Channel` |
| `community/form_marks.py` | implementation | The 4-state bar mark: `bars`, `draw`, `read` (no OCR, no alignment, reads upside down) |
| `community/form_layout.py` | implementation | `FormLayout` read from a fillable PDF: fields, printed lines (anchors) and words, and for character boxes their `pitches` and `cells` |
| `community/form_reader.py` | implementation | `read_scan`, `read_page`, `read_area`, `read_cells`, `mark_level`, `identify_form`, `find_marker`, `VisionReader`; constants `DPI`, `GROW`, `MAX_RESIDUAL`, `MARKED` |
| `community/form_hints.py` | implementation | Reading hints: what was sent (fold-equal only), what the answer holds (email, phone, address, contact), the street names |
| `community/fillable.py` | implementation | The fillable PDF, `read_answers`, `stamp_reference` |
| `community/postal.py` | implementation | `normalize_address`, `parse_mailing_address` |
| `tasks/owner_prefill.py` | task | `Prefill`, `prefill`, `suggested`, `fill_pdf`, `normalize`, `fingerprints`, `compare` |
| `tasks/owner_send.py` | task | `send_plan`, occupancy signals, `EmailHandler`, `MailHandler` |
| `tasks/delivery_engines.py` | task | `Engine`, `EmailEngine` (copy identity), `MailroomEngine` (campaign identity), `ENGINES` |
| `tasks/form_references.py` | task | `data/forms/references.json`: sent markers to ids and hashes; `lookup` |
| `community/response_inbox.py` | types | `Arrival`, `Channel`, `State`, `ResponseRequest` (a request that expects answers: form, cycle, PayHOA form, outside forms, marker campaigns, blank form), `Window`; the profile gives them through `Community.response_requests()` |
| `tasks/response_inbox.py` | task | The inbox of returns: the four channels' candidate rules, `check`, `read`, `confirm`, `keyed_answers` (read by `owner_info_apply.gather_answers`), `mark_recorded`, `observe_plan` |
| `tasks/form_scans.py` | task | `simulate` (a scan: dpi, turn, scale, shift, blur, speckle, gamma, JPEG) and `score` |
| `tasks/form_fuzz.py` | task | The owner-form fuzzer: answers, fills (typed, hand, cursive, pre-filled, edited), profiles, `run_case`, `lint`, `report`, the corpus |
| `tasks/form_lab.py` | task | The layout lab: `Layout`, `SPACE`, `render`, the responder model (`Writer`, `AFFORDANCE`, `salience`), `battery`, `evaluate`, `search`, `benchmark`, `sample` |

## Commands

| Command | Writes to PayHOA? | What it does |
|---|---|---|
| `jason owner-info --send-plan` | no | The send plan, names and units only |
| `jason owner-info --prefill UNIT --out F [--emailed]` | no | One unit's letter or emailed copy, for a look |
| `jason owner-info --email-batch` / `--mail-batch` | only with `--yes --confirmed-by NAME` | The batches; a dry run without them. The Mailroom charges the association |
| `jason batches [--show ID]` | no | Batch progress and failures |
| `jason form-fuzz [--lint] [--cases N] [--replay] [--model M]` | no | The owner-form fuzzer; report and corpus in `data/forms/fuzz/<form>/` |
| `jason form-lab [--sample] [--evaluate] [--search] [--benchmark M ... [--styles]]` | no | The layout lab; results in `data/forms/lab/` |
| `jason local-ai` | no | The Ollama stack, Windows commit, and what is loaded |

## Data on disk

`data/` is gitignored. Nothing below is committed.

| Path | Holds | Privacy |
|---|---|---|
| `data/forms/references.json` | Each sent marker: form, cycle, ids, send dates, field hashes | Ids and hashes only |
| `data/responses/` | The inbox of returns: `inbox.json`, `acts.jsonl`, the emailed attachments in `files/<id>/`, `readings/`, and the confirmed answers in `keyed/` | **Owners' answers: P3** (`jason.web.access`); no personal email address is stored on an arrival |
| `data/batches.db` | Batch items, statuses, events | Ids and errors, never an address |
| `data/owner-info/send-plan-<date>.md` | The send plan | Names and units |
| `data/owner-info/preview/` | Sample letters and emailed copies made for review | **Owner information; delete once reviewed** |
| `data/packets/owner-information-2027/` | The built packet, the fillable form, `packet-mailed.pdf` (the stamped letter) | The blank form |
| `data/forms/fuzz/<form>/` | `report-<date>.md`, `corpus.json` (failing cases by seed) | Made-up answers only |
| `data/forms/lab/` | `search-<date>.jsonl`, `best.json`, `benchmark-<date>.json`, logs, `samples/` | Made-up answers only |
| `data/mailroom/sent.jsonl` | Each Mailroom sending | Ids |

## Rules

**The marker is a hint.**
- Never make a reading depend on it. A page is known by its printed lines (`identify_form`), and every answer is read from the page.
- A marker that fails its check is used only when repaired (`repaired`) or matched to exactly one sent marker (`closest`), and says so.
- If the printed marker and the bar mark disagree, neither is used.

**No QR codes for the marker.** A QR code invites the owner to scan it. The bar mark is jason's own code and imitates no postal barcode.

**A QR code for a link: one per page, beside the step it serves.**
- Each is labelled with its action (`QR_LABELS` in `tasks/packets.py`) and has its web address printed beside it.
- The letter's cover has the form's code ("Scan to answer online in PayHOA"). Its "Never signed in to PayHOA?" section prints the sign-up address (`PORTAL_SIGN_UP` in `mystique/help.py`) without a second code, which would make the reader choose.
- Two codes on one page make the reader choose, so don't put two there. Help articles get printed steps (`{HELP_STEPS:key}`), not codes.

**Count the address page, and keep a letter to 4 pages.**
- The Mailroom prints the address on a page of its own ahead of the letter. PayHOA's preview leaves it out, but billing counts it.
- **PayHOA's pricing guide** (`payhoa.pricing`, read October 1, 2026):
  - $1.05 for the first page (first class $1.25), $0.20 for each page after.
  - **$2.25 more postage from 6 billed pages.**
  - Two-sided printing saves paper, not money.
  - So a 4-page PDF costs $1.85 a letter, and a 5-page one $4.30.
- **The owner-information packet is 4 pages.** Double-sided, the last sheet's back is blank, and that costs nothing. A fifth page, "Signing in to PayHOA", was tried and dropped; its steps are a short section on the cover.
- `jason mailroom --pdf` prints the billed pages, sheets, and the guide's cost, and warns at 6 billed pages (`mailroom.printed`). `jason mailroom --prices` checks every charged letter against the guide.

**Name the unit by its street line in an email.** PayHOA's `{unit address}` adds the city, state, and ZIP, and a mail reader turns a full address into a map search. `EmailHandler.message_for` fills the street line instead.

**Tests use made-up answers.** The fuzzer and the lab invent names and use the `example` domains. Never run them on owner records.

**Owner addresses stay in memory.** Real pre-filled values are made from PayHOA when a copy is sent or read, and only their hashes are kept.

**The hints never swallow a change.**
- "What was sent" replaces a reading only when the two are equal once OCR's look-alikes are folded together.
- A near miss stays as read.
- The fuzzer's report counts swallowed changes, and the count must stay zero.

**`normalize` is part of the stored fingerprints.**
- Changing it changes what a sent copy's hashes mean.
- Before any copy is sent this is harmless. After, it needs a migration, or comparisons of earlier copies are wrong.

**Sending is a person's decision.**
- PayHOA writes need `--yes`, and batches need `--confirmed-by`.
- The Mailroom prints, mails, and charges.
- jason never sends or mails on its own initiative.

**Never tell a reader what a copy was sent with.**
- Giving a vision model the pre-filled answers made glm-ocr report the old value for 13 of 24 changed answers, and "correct" 17 of 19 answers the owner wrote wrongly.
- The comparison with what was sent happens after the reading, in code (`form_hints`, `owner_prefill.compare`), where every repair is marked.
- Format rules in the prompt didn't help either. Keep the prompt plain ([form-design.md](form-design.md)).

**Keep three roles apart: owners, an owner's additional deliveries, and other contacts.**
- **Owners of record** are PayHOA's owner rows, checked against the deeds.
- **An additional delivery** is a separate owner record tagged Additional Deliveries, holding a second email or address the owner asked for.
- **Other contacts** are PayHOA's unit "other contacts" (`catalog.unit_contacts`, synced by `jason sync-catalog --only contacts`): tenants, past and present, and property managers.
- **What never happens:** an email that belongs to an other contact, or that a past answer gave for a resident, is never proposed as an owner's additional delivery. A resident named in an old answer isn't assumed to live there still.
- **Earlier answers** (the 2024 Resident Registration) listed residents beside owners. Match an answer's people to the unit's other contacts before treating any of them as an owner.
- **Property managers** are other contacts ("Name (Company), property manager") until the owner says otherwise.
  - The form's property manager section (questions 14–17) asks who the manager is and what the Association may do with the contact: send copies of notices, contact the manager if the owner can't be reached, or neither.
  - Either box makes the manager a person record on the unit, added without an invitation and tagged **Property Manager**. It also gets the role the owner chose: **Additional Deliveries** (4041(a)(2)), **Legal Representative** (4041(a)(3)), or both. Neither box keeps the manager an other contact (`member_preferences._manager`).
  - The record exists only at the owner's ask, because PayHOA treats every person on a unit as an owner: its broadcasts, charge reminders, Mailroom owner mailing, and membership list would reach the manager.
  - jason keeps the record out of owner counts, answer matching, and its own sends (`tags.NOT_OWNERS`). It has no vote and no membership-list entry.
  - An email signature that reads as a property manager (`jason signatures`, [gmail.md](gmail.md#signatures)) is a candidate only, never an other contact or a tag, until a lease or the owner says so.
- **Leases** (`jason leases --fetch --read`, `tasks/leases.py`) are read on this machine by the local model, for the unit, the term, the landlord, the manager, and the tenants' names only. Rental applications and screening reports are never opened.
- **What a lease supports** (`jason leases`):
  - **A current lease** (its end date today or later, no sale since) supports listing its tenants and manager, and tagging the owner.
  - **An ended lease, or one before a sale**, only raises a question to ask the owner. Whether a tenant stayed isn't in the lease.
- **Writes:** none here. Adding or removing an other contact, and tagging, are a person's confirmed writes.

**A reading is evidence for a person.** A scan's answers are never recorded without a person confirming them.

**Model jobs:**
- Run `local_ai.preflight` first, and hold `Resource.GPU`.
- Unload the model when done (`local_ai.unload`). A model left loaded holds Windows commit, stops the next model from loading, and can crash numpy in a test run.

## How to extend

**A new form**
1. Add a `FormTemplate` in `mystique/forms.py`.
   - Its `code` is two letters from the marker alphabet (A C E F H K M N P R T V X).
   - Set `reads` on each written question.
2. Build its fillable PDF.
3. Run `jason form-fuzz --form KEY --lint`, then a run of cases.

**A new kind of answer**
1. Add a `ReadAs` member.
2. Add its repairs to `form_hints.put_right`.
3. Add a generator in `form_fuzz.answers` and `form_lab.lab_answers`.
4. Add a test in `tests/test_form_marks.py`.

**A new channel**
1. Add an `Engine` subclass in `delivery_engines`.
2. Add a `Channel` in `form_refs`, its value one letter of the alphabet.
3. Decide whether it is a campaign or a copy.

**A new layout setting**
1. Add a field on `form_lab.Layout`.
2. Add its values in `SPACE`.
3. Draw it in `render`.
4. If it changes how people write, add that to the responder model and say so in [form-design.md](form-design.md).

**A new reader or model**
1. Run `jason form-lab --benchmark MODEL --styles`.
2. Add a row to the model trials in [document-tools.md](document-tools.md).

**A change to the reader**
1. Run `jason form-fuzz --replay` (the failing corpus) and a fresh run with the same seed. Compare with the last report.
2. Run `pytest tests/test_form_reader.py tests/test_form_marks.py tests/test_form_lab.py`.

## What has been measured

October 1, 2026, on simulated scans. All are made-up answers; real handwriting is still to be tried.

| What | Result | Where |
|---|---|---|
| Printed marker, 9 pt | 10/10 at 150 dpi and above; 0/10 at 120 dpi | [form-identifiers.md](form-identifiers.md) |
| Bar mark, gray | 10/10 at 120 dpi; 9/10 at 100 dpi; upside down 10/10; never a wrong marker | [form-identifiers.md](form-identifiers.md) |
| Owner-form fuzzer, typed answers after the reader fixes, Tesseract and hints | Clean 91%, office 91–100%, home 77%, upside down 100%; every box 100% | [form-fuzzer.md](form-fuzzer.md) |
| False changes on untouched pre-filled copies | 22 raw, 13 with hints; none swallowed | [form-fuzzer.md](form-fuzzer.md) |
| Faint 100 dpi fax | Never aligns (OCR reads 0–2 printed lines) | [form-fuzzer.md](form-fuzzer.md) |
| Lab, current layout, written answers (credit 0–1): Tesseract | 0.38 | [form-design.md](form-design.md) |
| Same, Tesseract and hints | 0.41 | [form-design.md](form-design.md) |
| Same, qwen3.5:9b (4 s a page) | 0.95 | [form-design.md](form-design.md) |
| Same, glm-ocr | 0.97 | [form-design.md](form-design.md) |
| Same, deepseek-ocr:3b | 0.35 | [form-design.md](form-design.md) |
| Same, qwen3.6:27b | Not run: needs about 25 GB of commit, 12–14 GB free | [form-design.md](form-design.md) |
| The form's rules in the vision prompt | No change in accuracy. Adding what was sent: glm-ocr reported the old value for 13 of 24 changed answers; qwen3.5:9b for 0 | [form-design.md](form-design.md) |
| The new print style on the real owner form (22 pt, 60% gray lines), built locally, 30 fuzz cases | Typed answers 90% to 91–94%, handwritten 35% to 42% right (likeness 0.66 to 0.72) against the old style (17 pt, black) | [form-design.md](form-design.md) |
| Line at 22 pt, Tesseract+hints / qwen3.5:9b | Black 0.37 / 0.88; 35% gray 0.42 / 0.96; 60% gray 0.50 / 0.97; none 0.50 / 0.97 | [form-design.md](form-design.md) |
| Layout search (Tesseract), 44 layouts | Converged in two passes on no printed line (0.563 against 0.520 for the current form); 22 pt spaces kept every word off the print (5% outside against 33% at 14 pt); Courier labels broke alignment (0.408); character boxes and combs scored worst | [form-design.md](form-design.md) |
| Vision models by layout | Plain layouts alike: qwen3.5:9b 0.947–0.966 and glm-ocr 0.957–0.978 (no line best); combs and character boxes 0.70–0.83 | [form-design.md](form-design.md) |

**What the numbers say:**
- The reader matters more than the layout. A vision model reads handwriting about as well as Tesseract reads typing, on any plain layout (0.95 to 0.98). Combs and character boxes hurt every reader. Beyond that, layout choices matter for the Tesseract path and for keeping writing off the printed text.
- A vision model needs no alignment, so it also reads the phone scans the Tesseract path can't align.
- The marker and the box answers are already robust. Handwritten text and faint faxes are the weak points.

## Open decisions and next steps

- **Registration marks.**
  - **Proposal:** solid squares in the page corners, as OMR forms and NIST's tax forms use.
  - **Benefit:** a page could be aligned without OCR, so a faint fax's boxes would read.
  - **Waiting on:** a decision, since it's a visible change to the owner letter.
- **The vision model as the handwriting reader.**
  - `read_scan` already prefers the model's words for text fields when given a model.
  - **The problem:** `VisionReader` defaults to qwen3.6:27b, which usually can't load beside everything else.
  - **Candidates:** qwen3.5:9b (6.6 GB, 0.95–0.97 and faithful) or glm-ocr (2.2 GB, 0.96–0.98).
  - **Recommendation:** qwen3.5:9b. glm-ocr "corrects" answers people wrote wrongly (6 of 19 with no hint), and loops on some pages.
  - **Waiting on:** a decision, and a check of both on real scans.
- **Real handwriting.** Print a few copies, fill them by hand, and scan them at home and by phone. Run them through `read_scan` with and without a model, and tune the responder model in `form_lab` to what people actually do.
- **The layout search.** Its result goes in [form-design.md](form-design.md). Vision-model scores of the leading layouts decide whether the layout should serve Tesseract or the model.
- **The membership-list choice** is missed on some pages. Its second button is at the far right, where the alignment is weakest.
- **Phone numbers** are not asked on the owner form (4041 doesn't require one). They exist in the lab and the hints only.
- **`src/jason/community/references.py`** (the citation module: `Reference`, `TargetKind`, `RefRelation`) was overwritten on October 1, 2026 and is still unrestored. Until it's restored, `test_manager_review` and the outline tests fail. Claude Code's file history holds the last good copy: `cp "C:/Users/jcapella/.claude/file-history/b4b63914-bc5e-4453-a9c5-79429b68c561/26bf95a996dd7a71@v1" src/jason/community/references.py`. A person runs it.

## Pitfalls

**Files and editing**
- **The Write tool silently replaces an existing file, and much of `src/` is untracked.** Check that a path is free before creating a module. `references.py` was lost this way.
- **Write Python with Write or Edit, not shell heredocs.** Backslashes get mangled. Import-check `jason.cli` after edits.

**Windows and the toolchain**
- **The Windows console is cp1252.** Printing an accented made-up name raises `UnicodeEncodeError`, so the commands print ASCII.
- **Tesseract writes "Image too small to scale!!" and "Line cannot be recognized!!" to stderr** on tiny crops. They're harmless; filter them from logs.
- **Temporary PDFs can stay locked on Windows.** Use `TemporaryDirectory(ignore_cleanup_errors=True)`.
- **PyMuPDF's `insert_textbox` draws nothing when the box is too small.** It returns a negative number instead of failing. Use `insert_text` for one line.
- **There is no Tesseract executable or `pytesseract`.** Tesseract runs inside PyMuPDF (`get_textpage_ocr`), so a page-segmentation mode can't be set. `read_cells` works around that for character boxes.

**The PDFs**
- **The packet's writing lines are underscore characters (text), not drawn rules.** They appear in `get_text("words")`, so filter out words with no letters or digits.
- **A filled PDF redraws its empty radio buttons.** The outline's difference survives the drop-out, so boxes are measured in their middle.
- **`read_layout` uses the form only for its key.** The lab's form reuses `FormKey.OWNER_INFO` for that reason, and is never sent.

**Background runs and models**
- **A background run loads the modules when it starts.** Editing code doesn't change a search already running; stop it and run again.
- **A Google Form the API creates came out published and open to responses on October 1, 2026,** despite Google's note that forms made after June 30, 2026 start unpublished. `tasks/forms.create` now unpublishes explicitly.
- **A page with few printed lines (the signature page) can fail the line fit.** OCR reads a line short when it ends in underscores or wraps differently. `fit_transform` retries leaving each line out, and `read_page` falls back to matching single words (`fit_words`).
- **Ollama keeps a model loaded after a request.** Call `local_ai.unload` before the next model, or its preflight fails for lack of commit.
