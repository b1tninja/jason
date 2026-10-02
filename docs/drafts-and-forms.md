# Gmail drafts and request forms

jason prepares email as Gmail drafts and makes the association's request forms in Google Forms. It never sends email:
`jason.google.gmail_drafts.GmailDrafts` has no send method and calls only `users.drafts.create` and `users.drafts.list`.
Every write is a dry run unless the person passes `--yes`. The token needs `gmail.compose`, `forms.body`, and
`forms.responses.readonly`.

## Drafts

```bash
jason draft --hearing "1234 Example Way" --to member@example.org [--pdf] [--yes]
jason draft --meeting-notice 2026-10-20 --to board@example.org [--yes]
jason draft --list
```

- **Hearing notice.** Read from `data/zoom/hearings.json` (the next hearing for the address, else the latest): date and
  time, the Zoom join link, and the notice Doc link, or with `--pdf` the Doc exported to PDF and attached. The subject
  names no owner or address. The dry run reminds the person that email is individual delivery only if the member
  consented to email (Civil Code 4040(b), 4041), and when the notice is due (5855(a)). The reminder is not in the email.
- **Meeting notice.** The agenda `data/board/agenda-<date>.md` is the body. The dry run flags a heading that still says
  DRAFT and prints the notice deadline the agenda states (Civil Code 4920(a)).

The recipient is always given by the person. The draft waits in Gmail; a person reviews and sends it.

## Forms

```bash
jason forms --create idr|records|owner-info [--yes]          # a Google Form
jason forms --responses FORM_ID [--offline] [--json]         # its responses
jason forms --pdf owner-info [--out FILE] [--prefill unit-address="<the unit's address>"]   # a fillable PDF
jason forms --read returned/*.pdf --form owner-info [--out answers.csv] [--json]            # read and check them
```

Templates are `FORM_TEMPLATES` in `mystique/forms.py`:
- the Request for Internal Dispute Resolution (Civil Code 5910, 5915);
- the Request to Inspect Association Records (Civil Code 5205);
- the Owner Information and Notice Delivery Preferences form (Civil Code 4041).

### One definition, every rendering

A form is defined once, as a `FormTemplate` (`jason.community.forms`), and every version is rendered from that
definition:

| Layer | Module | What it does |
|---|---|---|
| Definition | `jason.community.forms` | Questions and their kinds: short, paragraph, choose one, choose any, date, email, phone. Each question has a stable `field` (its `key`, or a slug of its title) and option keys. `prefill` names a per-recipient value. `check` validates answers. `answer_rows` makes rows for a sheet or CSV. |
| Paper | `jason.community.form_render` | `paper_blocks` lays the form out once. `paper_markdown` (for a Doc on the Letterhead) and `paper_html` (for a local PDF) print the same marks. `payhoa_sheet` is PayHOA's build sheet. |
| PDF fields | `jason.community.pdf_fields` | Works on any PDF: text fields (multi-line, required, maximum length), check boxes, radio groups, `values`, `fill`, `flatten`. Every field has a tooltip, which screen readers announce. |
| Form ↔ PDF | `jason.community.fillable` | `make_fillable` lays fields over a printed form, named by the definition. `read_answers` turns a returned PDF into a `FormAnswers`. |
| Tasks | `jason.tasks.forms` | `form_pdf` goes from definition to a fillable PDF, with no Doc, and can prefill one recipient's values. `read_pdfs` reads returned PDFs into checked rows. `create` and `fetch_responses` handle Google Forms. |
| Google Forms | `jason.google.forms` | `question_item` and `form_requests` render the definition for the Forms API. |

### How fields behave in the PDF

- A "check one" question is one radio group named by the question's field; choosing one option clears the others. PyMuPDF on its own makes each button a separate field that switches with the others, so `radio_group` builds the PDF standard's structure: one parent field, with each button a kid carrying its own "on" name.
- A "check all that apply" question gets a check box per option, named `<field>.<option>`.
- Required questions are marked required.

Because field names come from the definition, a returned form reads back the same way however the form is laid out,
and `forms.check` reports:
- a required question left blank;
- two choices where one was asked;
- an option the form does not offer;
- an answer that is not a date, an email address, or a phone number.

`flatten` bakes a returned form into its page for the record.

**A question never splits across pages.** Each question stays on one page with its help, choices, and lines, and so does the certification with the signature line:
- the HTML rendering puts each in a block that a page break can't split;
- the Markdown for a template Doc wraps each in `\keep`…`\endkeep`, which the Doc gets as "keep with next" and "keep lines together";
- a filled copy of a template made before that gets the same paragraph settings when the packet is built (`packets.keep_together_requests`). Its text is unchanged.

A section heading always stays with its first question.

**Links.** Statute citations, web addresses, and email addresses become links (`links.linkify` in HTML, and `links.link_pdf` over a Doc's PDF), so the PDF can be clicked while the printed page reads the same.

### To add a form

Add a `FormTemplate` row to `mystique/forms.py`, giving each question a short `key`. Every rendering then follows:
- the Google Form;
- the paper form;
- the fillable PDF;
- the PayHOA build sheet;
- the reader.

A packet takes a form as a `form:<key>` template part, so it can be enclosed in a mailing.

### Where the answers live: PayHOA

PayHOA is the record of each owner's contact details and notice preferences. Civil Code 4041(b)(1) requires the
Association to enter the answers "into its books and records", and PayHOA is the books. Owners sign in and change
their own details there, which is the "simple way to change" that 4041(b)(2)(B) asks for, and the Association's mail
and email go out from it.

The other channels are conveniences. A person enters their answers in PayHOA:
- the paper form;
- the emailed fillable PDF;
- a Google Form.

Where each answer lives in PayHOA:

| What | Where in PayHOA | Who changes it |
|---|---|---|
| Email, phone, mailing address | the member profile | the owner, signed in |
| Notice delivery: email, mail, or both (4041(a)(1)) | member tags "Notices by Email", "Notices by Mail" | the board, from the owner's answer |
| A secondary address on file (4041(a)(2), 4040(b)) | an additional owner record tagged "Additional Deliveries" | the board |
| A legal representative on file (4041(a)(3)) | member tag "Legal Representative" | the board |
| Occupancy (4041(a)(4)) | unit tags "Rental", "Vacant"; untagged is owner-occupied | the board |
| Answered this year's solicitation | member tag "Owner Info 2027" | the board |
| A second address; a legal representative | an additional owner record tagged "Additional Deliveries"; the representative's own person record tagged "Legal Representative" (no custom fields: PayHOA's are untyped text) | the board, from the answer |

- **Tags fit the work.** A broadcast and the Mailroom both select by tag. A delivery election is per owner, so it is a member tag, and co-owners may choose differently.
- **The vocabulary** is `PayhoaTag` rows in `mystique/tags.py`. "Rental", "Paper Statements", "Paper Ballot", the building tags, and PayHOA's own tags are already in use. A proposed tag stays `exists=False` until the board creates it.
- **Paper Statements is billing.** It covers billing statements, not a 4041 notice election.
- **The year in "Owner Info" changes.** Each year has its own "Owner Info" tag, so a reminder can go to whoever has not answered.

```bash
jason delivery                 # each current owner: email, mail, or both, and why; the broadcast and Mailroom counts
jason delivery --out plan.csv  # the plan per owner (names; no addresses)
jason delivery --tags          # the vocabulary beside PayHOA's tags: to create, carried, and unnamed
```

`delivery` applies Civil Code 4040(a) to each owner:
- an email election gets email, as long as PayHOA has a deliverable address;
- a mail election gets mail;
- both tags get both;
- no valid election gets first-class mail to the address on the books: the profile's mailing address, else the unit.

`jason forms --match` proposes the tag changes for each current owner's latest answer, for a person to confirm and
apply. Writing tags from jason needs a captured PayHOA tag request first.

### Sending the notices the law requires

```bash
jason delivery --notice list                                  # the notice rules (mystique/notices.py)
jason delivery --notice annual-budget-report [--ids ids.json] # exact recipients, and the PayHOA filters to use
jason delivery --notice flood-policy --unit-tag "Building 3"  # a building's owners only
jason delivery --audit [--out changes.csv]                    # tag changes so PayHOA's own filters find everyone
```

A `NoticeRule` names a notice and its authority. It says whether the notice goes by individual delivery (4040) or as a
general notice (4045), whether secondary addresses get a copy (4040(b): the annual reports and the collection notices
only), and its reach: all owners, one owner, or the owners of a unit tag.

PayHOA's filters select anyone carrying any chosen tag. They cannot select "owners with no election", who are exactly
the owners the law sends first-class mail. So jason works the notice out three ways:
- **`--ids`** gives the exact recipients for the sending tools.
- **The PayHOA filters** to use are printed, for a person working in PayHOA.
- **`--audit`** lists the tag changes that make those filters complete: every owner carries a delivery tag ("Notices by Mail" until they elect otherwise), and an owner who elected email with no deliverable address also gets mail.

How the tags combine was checked in PayHOA on October 1, 2026. A unit tag and a member tag together select what
carries both, an intersection, on both screens tried: the people list, and the Mailroom's unit picker. This association's
findings are in its private notes (mystique/notes/drafts-and-forms.md).

So "Building 3" with "Notices by Mail" picks the Building 3 units that have a mail-electing owner. The Mailroom then
lists every owner of each unit it picked. Uncheck a co-owner who elected email only, or send to jason's list (`--ids`).
Two tags of one kind (two buildings) were not captured.

**Secondary addresses (4040(b)).** As demonstrated on October 1, 2026:
- PayHOA's Mailroom mails a unit's owners only, at their profiles' mailing addresses.
- A broadcast can also email a unit's other contacts (the composer's "other contacts").

So a secondary address goes to an additional owner record on the unit, added without an invitation to sign in
(`add_owner`, `invite=False`) and tagged "Additional Deliveries". The record holds only what the owner gave, and its
fields are its channel: an email gets copies by email, a mailing address copies by mail, both get both. A broadcast to
"Additional Deliveries" emails the records that have an email; the Mailroom to "Additional Deliveries" must leave out the records with no mailing address, which PayHOA would mail at the unit (or send to
jason's `--ids`). jason keeps the records out of owner counts, elections, and matching, and lists them as `secondary`.
A copy record never carries an owners' delivery tag, so the owners' filters never select it; an "all owners" broadcast
would, so a courtesy email to every owner goes as two sends, "Notices by Email" then "Notices by Mail". Unit contacts are
not used for copies: a broadcast that includes "other contacts" reaches every contact on the units it picks, and the
audit flags any with an email.

Before adding a secondary owner record, check how PayHOA treats a second owner on a unit for ballots and the balance
statement. Remove one with `move_out_owners` when the owner withdraws the request.

**Applying the audit.** `jason delivery --audit --apply` reads the units and people from PayHOA live and lists the
delivery tags it would add; `--yes` writes them, 25 members a request. It only adds the tags the audit names and never
removes one.

### Forms in PayHOA

```bash
jason forms --payhoa owner-info [--yes] [--enable]   # make it in PayHOA's form builder (dry run without --yes)
jason forms --payhoa-submissions owner-info          # read the submissions by field, check them, and match them
```

The definition becomes builder questions (`form_render.payhoa_questions`):
- "choose one" becomes a single `select`, since the builder has no radio type;
- "choose any" becomes one `checkbox` per option;
- a date, an email, or a phone becomes short text with a hint.

A form that requires a unit does not ask for the unit's address. The new form is switched off until a person turns it
on (`--enable` leaves it on), and its question ids are recorded against the fields in `data/payhoa/forms.json`.

A PayHOA submission is signed in: it names its member and unit. Its answers read back into `FormAnswers`, and
`member_preferences.match` takes the member and unit directly, with no matching by address or name. The age rules
still apply: an answer only proposes changes in this year's cycle and after the latest deed.

### Answers from another form

```bash
jason forms --match FORM_ID [--offline] [--out review.csv]
```

A hand-made Google Form is read into a definition by a `FormImport` row in `mystique/forms.py` (`FORM_IMPORTS`).
Each `ImportRule` maps one question, matched by its title (and its section, where titles repeat), either:
- to a field of the definition, with its options mapped; or
- to a contact slot (`contact.name`, `contact.email`, `contact.phone`) with a role. Each occurrence of a repeated
  section is one more person.

File uploads are never read. `tasks/member_preferences.py` then sets each response beside PayHOA's current owners in
the stored catalog:
- **the unit:** read from the address as typed, typos allowed;
- **the current owner it names:** matched by email, then by name, allowing a shortened given name;
- **the latest response** for the unit.

Three dates decide whether an answer may still change anything, so older information never overwrites newer:

| Date | From | Effect |
|---|---|---|
| The unit's latest recorded deed | the county index (`PartyResolver.latest_deed`); PayHOA's occupancy date only when there is no deed and it is not PayHOA's setup date | An answer sent before it was the prior owner's, or the same owner's before re-titling (a trust). It changes nothing. |
| The owner's last profile update | PayHOA's `profile.updatedAt` | If the owner updated their profile after answering, PayHOA's email and mailing address stand. |
| The answer's cycle | `OWNER_INFO_CYCLE` in `mystique/forms.py` (`AnswerCycle`: the fiscal year, and the day the solicitation opened) | Only this year's answer proposes tag changes and a new email. Last year's and older answers become questions to confirm with the owner, each showing its date and age. |

Without a cycle, nothing is treated as this year's. The review CSV shows each response's date, age, cycle, deed date,
profile date, the tag changes it proposes, what to confirm, and why. It stays in `data/forms/<id>/` and holds names
and emails, but no addresses. Nothing is written to PayHOA.

A Google Form that does not collect a verified email cannot show who answered, so its response is a lead to confirm
with the owner. It is not the owner's 4041 election.

A created Google Form is recorded in `data/forms/forms.json`. Its responses are saved to
`data/forms/<formId>/responses.json` and read into one row per response, keyed by question title. A response is a
member's personal data: it stays in the Forms account and on local disk, and is never written to a shared store.

## Editing a draft

`jason draft --show ID` prints a saved draft. `jason draft --edit ID` refines it in place (`users.drafts.update`):
- `--replace OLD NEW`, repeatable; each OLD must be found, or nothing changes;
- `--subject`, `--body-file`, `--to`.

Without `--yes` the command prints a diff and changes nothing. An edit keeps:
- the draft's id and thread;
- any recipients a person typed in Gmail (an edit that names none keeps the draft's own).

It refuses a draft that has attachments rather than drop them. The client still has no send or delete method. `jason hold --notices --yes` updates the hold's saved drafts instead of adding new ones.

## PayHOA broadcasts

A member broadcast is drafted on disk as the HTML PayHOA's composer writes (`<p>` paragraphs, `<span class="placeholder">{first name}</span>`), checked, and previewed through PayHOA's own renderer. jason never sends a broadcast; a person pastes the body into PayHOA's composer and sends it there.

```bash
jason broadcast --templates                                  # PayHOA's saved templates and their attachments
jason broadcast --template 13417 --save data/drafts/notice.html   # start from a template's body
jason broadcast data/drafts/notice.html --subject "..." --attach "Email Attachments/Assessors Parcel Map.pdf"
jason broadcast data/drafts/notice.html --subject "..." --preview
jason broadcast data/drafts/notice.html --subject "..." --upload "coi.pdf=Certificate of Insurance 2026-2027.pdf" --yes
jason broadcast data/drafts/notice.html --subject "..." --send-sample --yes
```

- The bare command checks the body (subject, placeholders the capture showed, placeholders not wrapped as the composer wraps them, links) and resolves each `--attach` (library id, library path, or a file name that names one file) against the catalog on disk. A miss stays a miss.
- `--preview` posts the body to `email/sample/{membership}` for the signed-in admin's own membership, so no other member's name is read, and writes `FILE.preview.html` with the subject, sender, attachments, and checks. Nothing is sent.
- `--upload PDF[=Name.pdf] --yes` puts a file in the library's private `Email Attachments/` folder (`PayhoaFolder.EMAIL_ATTACHMENTS`), where the templates' attachments live, and attaches it.
- `--send-sample --yes` emails a `(Preview)` copy to the signed-in admin only, and only when the checks pass.

### Recipients by tag

```bash
jason broadcast --tags                                   # the unit and member tags in the catalog, with counts
jason broadcast FILE --subject "..." --tag "Building 3"  # who it reaches, checked with the draft
jason broadcast --tag "Building 3" --tag "Building 6" --member-tag "Board Member" --recipients-out data/drafts/to.json
```

A unit tag (Building 1 to 8, Rental, Paper Statements) resolves to its units and their current owners' memberships.
A member tag (Board Member) resolves to the tagged members. Both are read from the catalog `jason sync-catalog`
stores, and its date is printed. The output counts the members PayHOA marks as having no deliverable email, who must get
the notice by mail, and the other tags on the recipients' units. A tag nothing carries is refused. jason resolves
recipients but does not send: the send call was not in the capture, so the person picks the same tags in PayHOA's composer.

### Templates as Google Docs

```bash
jason broadcast --sync-docs                    # what would change
jason broadcast --sync-docs --yes              # create or update the Docs
jason broadcast --format-docs --yes            # header and highlights on every template Doc
jason broadcast --from-doc DOC_ID [--preview]  # the Doc as a body to check or preview
jason broadcast --from-doc DOC_ID --save-template 9087 --upload "PDF=Name.pdf" --yes
```

Each PayHOA template is a Doc named "PayHOA - <subject>" in My Drive/Templates/PayHOA Broadcasts
(`BROADCASTS_FOLDER` in `mystique/templates.py`), marked with the private appProperty `jason_payhoa_template`. Its
header (not part of the body, so never part of the email) names the template, the subject, and the attachments, and
explains the highlights: PayHOA's placeholders (`{first name}`, `{unit address}`) in light blue, and fields a person
fills for each use (`[BUILDING]`) in yellow. `data/payhoa/template-docs.json` keeps a hash of each template and of each
Doc as jason last wrote it, so a run says, per template:

| Status | Meaning | What jason does |
|---|---|---|
| create | no Doc yet, or its Doc is in the trash | creates the Doc (`--yes`) |
| update | PayHOA changed, the Doc did not | writes PayHOA's version into the Doc (`--yes`) |
| unchanged | neither changed | nothing |
| doc ahead | a person edited the Doc | nothing; `--from-doc ... --save-template ID --yes` puts it in PayHOA |
| conflict | both changed | nothing; a person merges them |
| deleted in PayHOA | the template is gone | keeps the Doc |

**One HTML form.** `jason.community.email_html.normalize` puts any body (PayHOA's, a Doc's, a draft) into one email-safe
form. It allows paragraphs, `h2`-`h4`, bold, italic, underline, strikethrough, links, line breaks, nested lists,
tables, rules, images, and the composer's placeholder span. It removes what a paste from a Doc leaves in PayHOA:
`dir`, `role`, `aria-*`, a `<p>` in every list item, and empty paragraph runs. Both directions use it.
`email_tables` adds the inline table borders mail clients keep.

**Doc to PayHOA.** `--from-doc` reads the Doc through the Docs API (`jason.google.docs_html`). A title or heading
becomes `h2`/`h3`/`h4`, and a table stays a table (a row whose every cell is bold is a header row). Horizontal rules,
strikethrough, and centered or right-aligned paragraphs come through, and each known placeholder is wrapped again. The
stored hashes from before this richer reading were of the first form (`rich=False`). The sync carries an unchanged
Doc's hash forward, so a change of form is not taken for an edit.

**Owner-facing documents: one Markdown source.** An email draft, a guide for the website, or a notice is written once
in Markdown (`data/drafts/NAME.md`, the dialect of `jason.google.docs_markdown`) and every form of it is made from that
file, so the email, its Doc, and its PDF cannot say different things:

| Output | Made by | From the Markdown |
|---|---|---|
| Email body | `jason owner-info --email-batch --message NAME.md`, `jason broadcast NAME.md` | `markdown_html.render`: placeholders wrapped for PayHOA, `{HELP:...}` filled, citations and addresses linked, pictures uploaded at send |
| Doc on the letterhead | `jason broadcast NAME.md --to-doc --yes` (PayHOA Broadcasts), `jason letter --markdown NAME.md --yes` (Templates) | `letters.markdown_doc`: a copy of the Letterhead, the house style, pictures put in, `{placeholders}` highlighted, help filled and citations linked as in the email |
| PDF to attach or post | `jason letter --markdown NAME.md --pdf OUT --yes` | the Doc's export, links kept |
| Preview of one owner's email | `jason owner-info --email-batch --message NAME.md --only UNIT --preview OUT.html` | the dry run's first copy as it is received: subject, unit links, reference, pictures; nothing sent |

What the Markdown holds: `#`/`##` headings (an email's `##` is its `h3`), paragraphs, `1.` and `-` lists nested by
indent, `**bold**`, `_italic_`, `[text](url)` (a `mailto:` link keeps its `?subject=`), a bare email address or web
address (linked), `![alt](file){width=560}` on its own line (a centred picture; the file sits beside the Markdown),
a line ending in `\` (the next line follows after a line break: an address, a signature), `{first name}`,
`{unit address}`, `{HELP:key}`, and `==a note==` for whoever reads the Doc (dropped from the email).

The Markdown is the source: a rewrite replaces the Doc's text, so edits belong in the file, and a Markdown draft is not
pulled back. The Doc ids are in `docs.json` beside the drafts.

**An HTML draft as a Doc.** An HTML draft that is not a PayHOA template is kept as a Doc through Drive's import,
pictures and all (`jason.tasks.draft_docs`), and can be pulled back:

```bash
jason broadcast data/drafts/DRAFT.html --to-doc --subject "SUBJECT" --yes   # make or refresh "Draft - SUBJECT"
jason broadcast data/drafts/DRAFT.html --pull-doc --yes                     # a person's edits back over the draft
```

- Drive's import drops pictures, so each `<img src="local.png">` is imported as a marker and inserted with the Docs
  API from a short-lived PayHOA upload link (Docs keeps its own copy). `data/drafts/docs.json` records which Doc
  picture is which file, and its alt text.
- The import also forgets which lists were numbered; the push numbers them again.
- A pull writes the Doc over the draft (the old one kept as `.bak`): each picture back as its file at the Doc's width,
  and a picture a person added in the Doc saved under `doc-pictures/`. A push replaces edits made in the Doc since,
  so pull first.
- Styles a Doc cannot hold (a button's colours, indents) do not come back; the email's letterhead tidy drops them
  anyway. Lines joined by `<br>` come back as paragraphs.

**Saving a template.** `--save-template ID --yes` replaces a PayHOA template's subject and body
(`PUT /email-templates/{id}`) and sends nothing.

- A save keeps only the files uploaded with it. On October 1, 2026 a template lost its attachment when one was not
  uploaded again. So each attachment is given again with `--upload`.
- A template that has attachments is refused without them, unless `--drop-attachments`.
- Saved from a Doc, the Doc and the template are recorded as in step.

**Placeholders.** `{first name}` and `{unit address}` are filled by PayHOA. The preview call fills `{unit address}`
from the member's unit (the full street address, city, state, and ZIP). A send fills it from the units the member was
chosen through. The check refuses `[FIELDS]` left unfilled in a body or subject. A template may keep them.

**The letterhead.** `--letterhead` frames the body as the Letterhead Doc frames a letter: the logo centered over
the association's name (Century Gothic, with fallbacks), and a rule over the mailing address. It applies to
`--preview`, `--send-sample`, and `--save-template`. The frame is not template text. The sync strips it when it copies
a PayHOA template into a Doc, and a save keeps it when the PayHOA template already had it. The logo needs a public image
address any mail client loads without signing in (`EMAIL_LOGO_URL` in `mystique/templates.py`). Until one is set, the
frame has the name and no logo. The website's Google Sites image links refuse other sizes (403), and PayHOA's logo
address needs a login.

**How it looks.** `--critique` renders the body through PayHOA (nothing is sent) and lays it out as a mail client
would, with the subject over a white column. It screenshots the page with the installed Chrome or Edge at desktop
(640 px) and phone (390 px) widths, set by the column because a headless window will not go that narrow. The local
vision model (`jason.tasks.email_review`) gets the screenshots and the letterhead logo (`data/brand/letterhead-logo.png`)
and answers what works and what to change, using only what the template HTML can carry. It writes
`FILE.desktop.png`, `FILE.phone.png`, and `FILE.critique.md`. It judges the look; `jason review` judges the words.

The calls are the ones `app.payhoa.com - broadcast.har` and `broadcast2.har` captured (see the payhoa package's
API.md). The broadcast send was captured too. jason does not send broadcasts: `--send-sample --yes` sends a test copy to
the signed-in admin only.
