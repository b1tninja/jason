# Handoff: the documents studio

For the design pass on the screen of the **document template system**: each document jason can generate, defined once as a **layout** (how it looks) and **blocks** (what it says, each read from a named source), and the Google Doc that definition makes. The system is built and has no screen: `jason document-template` lists, renders, checks, plans (`--doc plan`) and writes (`--doc create --yes`) the Rules document and the owner's manual template, and `jason templates --generate` does the same for the letter templates ([document-templates.md](../document-templates.md), [owners-manual.md](../owners-manual.md), [base-templates.md](../base-templates.md)). Code: `jason.community.document_templates` (the model, the check, the part map), `jason.community.doc_output` (the Doc's requests and its read-back check), `jason.tasks.rules_documents` (the definitions on disk and their proofs), `jason.tasks.document_docs` (the plan and the write, with the states create, update, edited, conflict, unchanged), and `jason.tasks.template_gen` (the same states for letters). Behavior and words are settled by this page, [README.md](README.md) (principles 1 to 9), [components.md](components.md), [content/style.md](content/style.md), [content/patterns.md](content/patterns.md), and [approval-workflow.md](approval-workflow.md).

The console already has `#/templates` ([screens/requests-and-links.md](screens/requests-and-links.md)): fill one letter template, see it as it would read, copy the `jason letter` command. The studio is the other half, the **definitions**: what a document is made of, what its Doc is, and whether the Doc still agrees with it.

**What the studio is not.**
- It is not an editor. No control anywhere on it types a document's words. Generated text is never edited in place: every sentence has a way back to the source that holds it, and the change is made there.
- It does not adopt anything. A draft rules document is a draft until the board adopts it; the studio reads that record and never writes it ([approval-workflow.md](approval-workflow.md#12-the-board-decides-by-vote)).
- It does not publish, share, send, mail, or delete. A write is a Doc created or its body replaced in the association's Drive, privately, through an approval a named person signs ([approval-workflow.md](approval-workflow.md#8-the-action-kind-registry): the kind `google.doc`, proposed). Filing a document on the public list is `jason publish-document`, a different act this screen never does.
- It does not work anything out. Every standing, difference, count, and check below is returned by a loader that wraps the function that computes it.

**Its neighbours** (linked, not repeated). [handoff-confirmations-queue.md](handoff-confirmations-queue.md) (a person's signed act that adopts nothing; the same stale-then-reread discipline), [handoff-rules-and-authority.md](handoff-rules-and-authority.md) (the rules a Rules document includes, and the rule-change hand-off), [handoff-draft-from-item.md](handoff-draft-from-item.md) ("a person's words are theirs": regenerating never overwrites an edit without showing it), [handoff-form-library.md](handoff-form-library.md) (a form block's form is the library's form), [handoff-record-intake.md](handoff-record-intake.md) (where a missing embedded document is supplied), [handoff-programs.md](handoff-programs.md) (a program's document and its adoption), [handoff-as-of-and-quote-check.md](handoff-as-of-and-quote-check.md) (`AsOfControl`, the day every recitation obeys), [handoff-intake-review.md](handoff-intake-review.md) (reading a scan back into structure: the opposite direction, which this page only borders in "The Doc's structure"), [doc-component.md](doc-component.md) and [documents.md](documents.md) (`Doc`, `DocumentViewer`), and [screens/records-and-library.md](screens/records-and-library.md) (a document's revisions). A separate **directory-consent** spec is being written; it owns who may publish whose contact details. The studio only reads its answer (see "The directory block").

These components pair with what the console already has: `Recitation`, `Confirm`, `Findings`, `Command`, `Doc` and `DocumentViewer`, `Pill`, `Stat`, `DataTable`, `Card`, `Tabs`, `Markdown`, `Caveats`, `Checklist`, `Timeline`, `DueDate`, `AuditLog`, `EmptyState`, and `RemoteView`; from the approvals engine `PlanReview`, `WriteRow`, `ApproveBar`, `ApplyResult`, and `ChangedBanner`; and, once built, `AsOfControl` and `DiffTable`. Build new parts only where the table says so.

## The idea in one line

A document is **a definition**: a layout and an ordered list of blocks, each block read from a named source as of a day and never copied. The studio shows the definition, shows the Doc it made, says in words whether the two still agree, and, when a person decides to write, shows exactly what would be written before a named person signs. A Doc a person edited is theirs: the studio shows their changes against the base and offers three honest choices, one of them a named loss, and writes nothing until one is chosen.

## How a document gets from its sources to a Doc

```
sources (rule records, forms, the directory, quoted words, embedded files)
   -> blocks (id, source, as-of day)  -- rendered, never copied
   -> layout (heading levels, numbering, header and footer, contents, page breaks)
   -> Markdown, HTML, (PDF later)       read-only, on disk
   -> a plan: what a Doc would be       a dry run; reads Drive to see whether a person edited the Doc
   -> an approval a person signs        engine kind google.doc (proposed)
   -> a Doc in the Drive folder         created, or its body replaced in place; read back and checked
```

The first three rows exist on disk and cost nothing outside jason. The last three are the part of the screen that touches Drive, and each is a person's act (principle 4).

## The components

| Component | Built from | Where it renders | Data | States to design |
| --- | --- | --- | --- | --- |
| `DocumentsStudio` | `ScreenHeader`, `Tabs` (the groups), `RemoteView` | Governance → Documents studio (`#/studio`) | `GET /api/studio` | loading; listed, grouped by kind; one loader failed (the rest listed, the failed one's note and command in its place: no outline on disk, no classification, Google not connected); filtered to none; no profile rows (letters: "The profile has no letter templates"); not authorized (the server's reason); Google not connected ("Standing shown as last read; the Docs were not read", with the sign-in command: the page never prompts) |
| `StandingCounts` (a `Stat` strip) | `Stat`, `Pill` | above the list | `counts` | by standing word; "needs a person" as the sum of edited, conflict, and Doc gone; its table twin |
| `DefinitionRow` | `DataTable` row; a card under 720 px | the list | one `items[]` entry | the columns below; a row whose Doc was never read ("not read"); a row with no Doc output ("Markdown and HTML only") |
| `OutputStanding` (a `Pill` preset) | `Pill` | the list, the page header, the plan, an approval's item | `standing` | the words in "The words": in sync, base changed, edited, conflict, never generated, Doc gone, not made by jason, to adopt, not read, own |
| `OutputLine` | `Doc` (a `DocRef` for `drive:ID`), `DueDate`, `Pill` | a row's Doc column; the page header; the Doc tab | `output` | no Doc yet; a Doc (the `Doc` chip, folder name, last written, last edited by and when); the folder's sync flag as a word; Doc gone; read at a time ("as read Oct 5, 2099, 09:12") or not read |
| `DefinitionPage` | `Card`, `Tabs`, `ScreenHeader`, `OutputLine`, `AdoptionLine`, `AsOfControl` | `#/studio/<key>` | `GET /api/studio/definition?key=&layout=&as_of=` | loading; unknown key (`found: false`, the note and `jason document-template --list`); one of six tabs (Blocks, Layout, Check, Part map, Preview, Doc); the as-of day not today (the banner `AsOfControl` gives) |
| `BlockOutline`, `BlockRow` | nested list, `Pill`, `Findings` | the Blocks tab | `blocks[]` | ordered; an embedded block nests its own (collapsed, with its count); each row: number, `id`, kind word, title, source named, as-of day (shown in full only when it differs from the document's), standing, gap line; prose rows grouped ("12 prose blocks": a person opens them); a row's source opens `SourcePanel`; a block with a gap is first in a "Gaps" filter |
| `BlockKindWord` (a `Pill` preset) | `Pill` | `BlockRow`, the part map | `kind` | the fourteen kinds `jason document-template --list` prints; an unknown kind keeps its word in the neutral tone |
| `SourcePanel` | `Card`, `Recitation`, `Doc`, `Findings`, `Command` | beside the outline; a drawer under 720 px | `GET /api/studio/source?key=&block=` | one preset per kind below: `RuleSource`, `QuoteSource`, `PartSource`, `FormSource`, `DirectorySource`, `EmbeddedSource`, `HistorySource`, `ComputedSource`, `ProseSource`; each ends in `WhereToChange`; loading; the source not on disk (a miss with its command); held (a P3 source outside the private view: by kind only) |
| `WhereToChange` | `Command`, a link | the foot of every `SourcePanel` | `change` | names the one place the change is made (a record file, the manual's Doc, the profile's row, the governing document, a form in the library, the consent record) as a link or a `Command`; says what the change is: a proposal, a person's commit, or a board act; never a text field |
| `AdoptionLine` | `Pill`, `Seal`, `Stamp` (as built in marks), `Doc` | the page header; the Check tab | `adoption` | draft (no adoption event for the whole document on record: the draft banner as the Doc prints it, and what would end it, in words); adopted (the day and the evidence the record gives); an adoption of one rule only ("does not adopt the document"); read-only at every state |
| `LayoutPicker`, `LayoutFacts` | radio group, `DataTable` | the Layout tab | `layouts[]` | the three layouts and the definition's own marked; each layout's fields as a table, a row marked "Doc" when the Doc carries it and "HTML and PDF only" when it does not |
| `LayoutCompare` | two `Markdown` or `Doc` `inline` regions, `Findings` | the Layout tab | `GET /api/studio/render?key=&layout=&format=` twice, and `compare` | two layouts side by side over the same blocks; "Blocks identical under both: 14 of 14" (the server rendered both and compared the block results); a difference in a block's words between layouts is a defect, shown as one; stacked under 720 px |
| `CheckReadout`, `ProofCard` | `Stat`, `Findings`, `DataTable` | the Check tab | `check`, `proofs[]` | clean; placed, unplaced, uncovered requirements, gaps, labeled differences, unlabeled differences (a defect), open tokens (on purpose in the template form, a defect in a filled document); a proof against the official rules (same lines, labeled lines with their reasons, unlabeled lines); the proof not computed yet ("Check again": a read job) |
| `PartMapTable` | `DataTable` | the Part map tab | `partMap` | each block's id, kind, title, source, as-of day, standing, authority, gap; pages "none yet" until the PDF output exists, with that said in words |
| `RenderPreview` | `Markdown`, `Doc` (`inline`, `kind: html`), `Command` | the Preview tab | `GET /api/studio/render` | Markdown; HTML (served by jason, sanitized, never a frame of an outside host); PDF "not built yet" with the command that will make it; the audience (owners or board) named for a directory |
| `OutputPlan`, `OutputPlanStep` | `Card`, `DataTable`, `Findings`, `Command` | the Plan view (`#/studio/<key>/plan`, and a plan of several) | `GET /api/studio/plan?keys=` | per step: action word and reason; the Doc's name; the folder with `FolderLine`; request counts; styles; tables; page breaks; header and footer; tokens left open; links; named ranges; what the step will not do; a step that writes nothing (edited, conflict, unchanged) shown and marked "writes nothing"; blocked (a draft in a public-sync folder; no letterhead Doc; the folder not found); the links' target not known until the first Doc exists |
| `FolderLine`, `PublicSyncNotice` | `Pill`, `Findings` | `OutputPlanStep`; `OutputLine` | `folder` | the folder named, never a path or an id as text; where it comes from (the profile's row, the Drive home's Templates folder, or "a folder named Templates will be made under My Drive" as a write of its own); syncs to the public list or not, by the profile's sync rule, and whether this Doc's name matches that rule's pattern; not found |
| `OutputRead` | `Confirm`-free button, `Timeline` | the list header and the Doc tab | `POST /api/write/studio/read` | not read; reading (progress, `role="status"`); read at a time by a named person; Google not connected (the command); a Doc that cannot be opened (deleted, no access) per Doc |
| `OutputDiff` (a `DiffTable` preset) | `DiffTable` once built, `DataTable` until | the Doc tab in the edited, conflict, and update states | `GET /api/studio/diff?key=` | rows by block (found by the Doc's named range, which the block's id names): same, edited in the Doc, only in the Doc, missing from the Doc, base changed, both changed; each differing row's change marked as inserted and removed words by text cue as well as mark; same rows collapsed with their count; text outside any block; the text as last written not kept (the third column is a stated miss) |
| `EditChoices` | radio group, `Confirm` presets: `FoldProposal`, `KeepOwn`, `RegenerateLoss`, and `AcceptRecord` | the Doc tab, edited and conflict states | `choices` | three choices of equal weight, none chosen at first; each says what it records, what it writes, and what it never does; a choice not offered while the Doc has not been read, or Google is not connected, with the reason in words; the loss line first on `RegenerateLoss` |
| `OutputStructure` | `Stat`, `DataTable`, `Findings` | the Doc tab, after a read | `GET /api/studio/structure?key=` | not read; headings by named style (planned and in the Doc); level checks (a skipped level, an empty heading, a heading style on a body paragraph); one named range per block (planned and found); contents (links written; the field a person inserts, noted); verified at a time, with the read-back's problems as `Findings` |

### The columns of the list

Document (title, key in a chip) · Kind (the definition's own word: a rules document, a manual, a letter) · Layout (`plain`, `guide`, `book`; "Letterhead" for a letter) · Blocks (the count, and the gaps among them as "2 gaps") · Doc (an `OutputLine`) · Folder (name, and "syncs to the public list" as a word when it does) · Last written (a day, or "never") · Edited last (a name and a day from the Drive catalog on disk, or "not read") · Standing (`OutputStanding`) · What a person does next, in words ("Read the Doc", "Look at the plan", "Choose what to do with the edits").

Groups, in order: **Needs a person** (edited, conflict, Doc gone, not made by jason), **Documents** (the definitions), **Letters** (the letter templates: one-block documents on the Letterhead, through `template_gen`), each with its count. Within a group, by title. The row is a link to its page, in DOM order.

### The words

Every state is a word the code already uses, or a phrase in [content/style.md](content/style.md), and the color only repeats it.

| Word | Where from | Meaning |
| --- | --- | --- |
| in sync | `Action.UNCHANGED` | the Doc is as jason last wrote it, and the base has not changed |
| base changed | `Action.UPDATE` | the definition or what it reads changed; the Doc was not edited; an update would replace the body in place, keeping its id, header, and footer |
| edited | `Action.EDITED` | a person edited the Doc and the base did not change; left alone |
| conflict | `Action.CONFLICT` | both changed; nothing is written |
| never generated | `Action.CREATE`, "no Doc yet" | no Doc has been made |
| Doc gone | `Action.CREATE`, "its Doc is gone or in the trash" | the Doc jason made is not there; a new one would be created, and the old one is not restored |
| not made by jason | `Action.EDITED`, "the profile names a Doc that jason did not generate" | a Doc the profile points at; left alone |
| to adopt | `Action.ADOPT` | a letter template's Doc built before the bases; its body would be rewritten from the base |
| not read | `NOT_READ` | the Doc was not read, so whether a person edited it is not known; the standing is "base changed" or "in sync" only as far as the disk can say |
| own | proposed | a person kept the Doc as this association's own, with a reason |
| draft, adopted | `adoption_status` | the status line the document carries, from the adoption record |
| same, edited in the Doc, only in the Doc, missing from the Doc, base changed, both changed | the diff | a block's state against the Doc |
| blocked | the plan | something stops the write, and the plan says what |

The base is what jason would write now from the definition and what it reads (the hash `base_sha` or `Job.base` stands for it). "Approve" appears on no control of the studio; the approval is in `#/approvals`. "Publish" and "sync" appear only as the words a folder's flag uses.

## The list

`#/studio` answers three questions at a glance: which documents jason can make, which have a Doc, and which Docs need a person.

- **What standing means without reading Drive.** The disk alone says "never generated" (no state entry) and "base changed" (the rendered base differs from the hash stored when the Doc was written). It cannot say "edited": that needs the Doc's text, and nothing on load calls Google (principle 1). So the list shows each row's **recorded standing** and says when the Doc was last read. **Read the Docs** is a person's click, signed in and logged, that reads each known Doc and stores its text (`OutputRead`); after it, the standing is complete and says when it was read. A Doc not yet read shows "not read", never a guess.
- **The next step is a link.** A row's last column opens its page at the tab the next step is on (the Doc tab for edited and conflict, the plan for base changed).
- **Letters are rows too.** A letter template is a one-block document whose layout is the Letterhead Doc's own. Its page has no Layout or Part map tab; its tokens are sorted by who fills them (the profile, general wording, the letter's own: `jason templates --lint`), and its plan is `jason templates --generate`.

## The definition page

One page per definition, with the header (title, key, kind, standing, `OutputLine`, `AdoptionLine`, `AsOfControl`) and six tabs. `?tab=` and `?block=` make a link land on a block.

### Blocks

The blocks as an outline, in the document's order. Each row says what the block is and where its words come from:

| Column | From | Notes |
| --- | --- | --- |
| number | order | a nested block is "7.2" |
| `id` | `Block.id` | stable in the document; the Doc's named range for the block bears it; the diff names a block by it |
| kind | `Block.kind` | `BlockKindWord` |
| title | `BlockResult.title` | the heading the block prints, or its id |
| source | `Block.source` | named, never a path: "the Rules document's records", "the guide's front slot", "the form `<key>`", "the directory" |
| as-of day | `Block.as_of` | the document's day unless the block's own differs, then both: "as of Mar 1, 2099 (the document: Oct 5, 2099)" |
| standing | `part_map` | placed, gap, required (with its authority), included (the board's choice, so labeled) |
| gap | `BlockResult.gaps` | the line the document prints in its place, in words ("Required: not on file for this year") with where to supply it (a link into record intake or the library) |

A block whose source is not on disk, a rule with no version in force on the day, a vacant office, a required part not on file, and a stale part (not this year's terms) are **gaps**: visible in the document and here. They are counted, never dropped, and never filled by a guess (principle 8).

### Click through to a source

A row opens its `SourcePanel`. The panel recites or shows what the block read, and ends with where the change is made. **No panel has a field that edits the words.**

| Block kind | The panel shows | Where to change it (`WhereToChange`) |
| --- | --- | --- |
| `rule`, `rule-book`, `rules-reference` | the rule record: its permanent id, the number it prints now, its versions each with the day adopted and the board item, or "proposed"; the version in force on the document's day, recited (`Recitation`: the words whole, the version in force, the caveat); the editorial notes after it; whether the records are stored or derived | stored records: the file the person keeps (`data/rule-records/<document>.json`), where an edit adds a **proposed** version that is in force on no day; derived records: the owner's manual Doc, the source, opened with `Doc`'s Original. Then the board adopts at a meeting: `jason rule-change` for a subject that needs notice, and the adoption is recorded by a person, never here ([handoff-rules-and-authority.md](handoff-rules-and-authority.md)) |
| `quote`, `law`, `excerpts` | the stored words by `{QUOTE:key#n}` or `{LAW:...}`, as a `Recitation` from the `cite` loader, with the as-of day, the version in force, and the caveat; a quote not found says so and recites nothing | the governing document or the statute on disk; a stale or missing copy is read again by `jason export-authorities` or the document's own refresh, never edited here |
| `part` | the guide's own words for a slot (front, welcome, contacts, guidance), with its source Doc as a `Doc` card | the guide's Doc, in Docs |
| `form` | the form's key and its fields; the paper rendering; the live form it is the same definition as, if there is one | the form library ([handoff-form-library.md](handoff-form-library.md)); a live PayHOA form is changed in place with `jason forms --payhoa KEY --update`, never deleted |
| `directory` | the roles and published fields: next section | the directory-consent record, and the profile's officers |
| `embedded` | the nested definition, or the stored file's stable address, its pages and as-of day, `required` and its authority, or the gap | a nested definition: its own page; a stored file: the record's slot in record intake ([handoff-record-intake.md](handoff-record-intake.md)) or the library |
| `history` | the adoption events the table reads, each with its day, action, sections, and evidence | the minutes and the rule-change record; adding an event is a person's record, not the studio's |
| `computed` | the inputs it read, named, and the table it made | the stores it read |
| `prose` | the words written once in the definition, with its `{TOKENS}` and where each token's value comes from (the profile, general wording, the run) | the definition, a change a person commits; a token's value is the profile's |
| `status` | the adoption line | the adoption record |

### The directory block

The directory prints roles and the contact fields the board chose to publish ([document-templates.md](../document-templates.md), section 5). The studio reads it and decides nothing:

- Each role shows the name as owners see it ("(not published)" when nobody has agreed, never "(vacant)" for a held seat) and each contact field with its own **published** word. Nothing is published by default.
- Beside each flag, who confirmed it, when, and how, read from the directory-consent record; a flag no one confirmed says "not published: no one has confirmed". The studio has no control that sets a flag. The consent spec owns the record, who may record it, and its shape, and this page renders whatever it serves under `consent` (`confirmedBy`, `confirmedAt`, `how`, `record`).
- An **audience** picker (owners, board). A directory for the board prints every field and is marked "draft, not distributed"; a Doc is only ever planned for the owners' audience.
- Contact values are masked by the server until a person asks, and that is logged ([security-and-privacy.md](security-and-privacy.md#data-levels)); the plan and the list carry counts ("3 roles printed, 1 '(not published)'; email on 2, phone on 1"), never values.

### The adoption line (read-only)

`AdoptionLine` shows the status line the document carries. **Draft:** no adoption event for the whole document is on record on or before the document's day; the line says so in the words the Doc prints, and says what an adoption event would be (an event of the action `adopted`, dated on or before the day, whose sections name the document), as words and a link to `#/decisions`, never a control. **Adopted:** the day and the evidence. **One rule adopted:** "An adoption of one rule does not adopt the document; a notice is not an adoption." The adoption is the board's vote, recorded by the president or the secretary where every vote is recorded.

### Layout

The layout is how the document looks and nothing it says ([document-templates.md](../document-templates.md), section 2). The tab proves it:

- `LayoutPicker` lists `plain`, `guide`, and `book`, with the definition's own marked. `LayoutFacts` is each layout's fields as a table (heading shift, numbered headings, header, footer, contents and its depth, title heading, cover, separator, page breaks before heading levels, style tokens), each row marked **Doc** when the Doc output carries it (heading levels, numbering, header and footer, contents, page breaks) or **HTML and PDF only** (fonts, sizes, colors: in the Doc they are the Letterhead's styles, not a second set).
- `LayoutCompare` shows two layouts over the **same blocks**, side by side: left the definition's own, right another, both chosen from the picker. Above them, in words, the server's answer to the fourth check: "Blocks identical under both: 14 of 14", or a defect line naming the block whose words differ. A layout that changes a block's words is a bug in the layout and shown as one.
- **Choosing is a preview.** The picker changes what the preview shows (`?layout=`). The Doc output today uses the definition's own layout; there is no per-association setting. Making another layout the Doc's is a profile change, offered as a proposal a person applies (decision 3), and the studio never applies it.

### Check

`CheckReadout` is `DocumentCheck` and the proofs, in words:

| Line | Meaning | A defect when |
| --- | --- | --- |
| placed | every block is rendered once, in order | a block is unplaced |
| covered | each requirement the definition lists has a block, or a visible gap | a requirement has none |
| gaps | parts missing, stale, or vacant, shown in the document | never a defect: it is the document saying so |
| labeled differences | a piece that differs from its source carries a label (a statute read from disk, a note left for a person) | — |
| unlabeled differences | a piece with neither a source span nor a label | **0 is the only clean count** |
| open tokens | `{TOKENS}` left in the output | in a filled document. In the **template form** the association's name and the date stay open on purpose, to be filled when the Doc is copied; the plan lists them as "to be filled when the Doc is copied" |
| layout independence | the same blocks under two layouts | the words differ |

Proof cards read `jason document-template KEY` as it prints it: the Rules document against the official rules (lines the same, lines labeled with their reasons, lines unlabeled, which is a failure), and the owner's manual read from its rules records against the manual read from the classification. A proof not computed shows "Check again", a read job (it runs the manual's own pass, which takes seconds and writes the manual's drafts under `data/`).

### Part map

The part map is the document's known structure, as `part_map` writes it: block id, kind, title, source, as-of day, standing (required or included), authority, gap, form fields, an attached file's address and pages. **Pages are "none yet"**: they need the PDF output, which is not built. The table says so, and never prints a page number it does not have.

### Preview

The rendering as Markdown, HTML, and PDF, for the chosen layout and day. Markdown is `Markdown`. HTML is the file jason wrote, shown by `Doc` `inline` (a sanitized document served by jason). PDF is not built: the tab shows "PDF: not built yet" and the planned command. A preview of a document for owners shows what owners would see (the directory's unpublished roles as "(not published)").

## The plan and the write

There are two plans, and the page keeps them apart.

1. **The dry run** (`jason document-template --doc plan`, `jason templates --generate`): what each Doc would be, printed for a person to read. It reads Drive only to see whether a person edited a Doc, and writes nothing. It is not an approval and carries no signature.
2. **The approval** (engine kind `google.doc`, proposed): the same plan as an `Approval` whose items a named person decides and signs, read again before apply, applied only when the server was started with `--allow-apply` ([approval-workflow.md](approval-workflow.md)). The studio does not duplicate `PlanReview`: it links to the approval in `#/approvals`, and `WriteRow` shows each Doc as an item.

### What the plan says

`OutputPlanStep` prints, for each Doc, exactly what `document_docs.describe` prints, as a table a person can read:

| Line | From | Notes |
| --- | --- | --- |
| action and reason | `Step.action`, `Step.reason` | create, update, adopt (a letter), or one of the three that write nothing |
| name | `ManualDocument.name` | the name the Drive file will bear; in the plan, a place to see a name a person has not confirmed (the first `--yes` follows a person's confirming the names, the folder, and who adopts) |
| folder | `FolderLine` | the folder's name; where the choice came from; **whether it syncs to the public list** (below); whether a folder will be made |
| requests | `DocPlan.count`, "+1 clears the Letterhead's sample text", and the contents pass | the body written as one ordered list, sent in batches |
| styles | `DocPlan.styles()` | the named styles the Doc will carry: TITLE, SUBTITLE, HEADING_1 to HEADING_3, NORMAL_TEXT, each with its count |
| tables and page breaks | `DocPlan.tables`, `page_breaks` | the adoption history, the directory |
| header, footer | `DocPlan.header`, `footer` | or "(the Letterhead's own)" |
| tokens left open | `DocPlan.tokens` | on purpose in a template form; a list a person reads |
| links | `DocPlan.links` | the words and their target; the manual template's link to the Rules Doc names "the Rules Doc's id, known once it is created" until the first Doc exists |
| named ranges | `DocPlan.named_ranges` | one per block, by its id |
| order | the plan | the Rules document first, so the manual template can link it |
| will not do | fixed words | share, send, export, or delete; trash; touch another Doc; write over a person's edit |

An **update** also shows `OutputDiff`: for an unedited Doc, what the base changes, block by block. A step that writes nothing is shown with the word and its reason and the line "writes nothing".

### The folder, and the public list

`FolderLine` is shown on every step and in the approval's item. The server resolves it (the client never matches a name to a rule):

- **Where the folder comes from:** the profile's row for the document, else the Drive home's Templates folder, else "a folder named Templates will be made under My Drive". A folder that will be made is its own line of the plan, never folded into the Doc's.
- **Does it sync to the public list?** The profile's sync rules map a Drive folder to a folder on the owners' site by a name pattern. `FolderLine` says "This folder syncs to the public list" when a rule names it, and says whether **this Doc's name matches the rule's pattern** ("a Doc with this name would be published at the next sync" or "its name does not match; it would stay in Drive"). Nothing here runs a sync.
- **A draft is never filed in such a folder.** A document whose status is draft (no adoption on record) planned into a folder that syncs to the public list is **blocked**: the step is shown with the reason, has no approve control, and the approval cannot include it. The way out is the profile's folder for the document, a change a person commits; the studio names it and links nothing to apply. An adopted document in such a folder shows a warning, not a block: publishing is the person's act and the board's.
- **Who else can see it.** The Doc is private to the Google account jason is connected as. Whether the folder is shared with others is Drive's, and a plan that did not read it says "sharing not read" (decision 9).

### The signed act

- A Doc is **written under an approval a named person signed**: the plan lists each Doc as an item, the person decides each (never "approve all" for an item that writes over an edit), signs with the tally and their name, and applies, or the page shows `jason approvals apply ID --yes --by NAME`. The first approval of a profile's Docs follows a person's confirming the Doc names, the folder, and who adopts the Rules document.
- **Whose name.** The person who signed is the name on the plan, the audit log, and the studio's own record of what was written. The Doc's owner in Drive is the Google account behind jason's stored token, and the page says so by that account's display name; a signer's name is not Drive's creator. Whether a Doc also carries a line saying which approval made it is decision 8.
- **Verify.** After the write, jason reads the Doc back and checks each planned paragraph and heading style (`doc_output.verify`). The result is on the approval's `ApplyResult` and on the Doc tab. A Doc that does not read back as planned is "uncertain", not "applied", and its problems are listed.
- **Reversibility.** A Doc created is not deleted by jason, ever. An update replaces the body, and Drive's version history keeps what it said; the page links the history (the `Doc` card's Original), and `jason revisions` reads it.
- **Fail fast.** A stale approval is read again; a changed Doc since the plan (a person edited it in between) turns the item into `CHANGED` and nothing is written, as for every kind ([approval-workflow.md](approval-workflow.md)). The browser never opens a Google sign-in.

## A Doc a person edited, and a conflict

The Doc is jason's output and the person's document at once. Once a person has edited it, jason's rule is the one this repo keeps for every generated file: **a person's words are theirs**. Regenerating never overwrites an edit without showing it.

### What the page shows

**Edited** (a person edited the Doc, the base did not change): the Doc's text now, against what jason would write now, which is also what jason last wrote, so the difference is exactly the person's edit. `OutputDiff` lists the blocks that differ:

| Block | State | In the Doc | The base says |
| --- | --- | --- | --- |
| `rule:4.2` (rule 4.2) | edited in the Doc | (the Doc's words, with inserted and removed words marked as such) | (the base's words) |
| `contents` | edited in the Doc | the table of contents a person inserted with Insert > Table of contents | links to the headings |
| (outside any block) | only in the Doc | a paragraph a person added after the last block | — |

Each differing row ends in "Where this would be changed": the block's source (`WhereToChange`). The 27 blocks that match are collapsed with their count. A person who inserted the contents field has changed the Doc's text; the row is labeled "the contents field the Doc editor makes" and is **not** counted as an edit of a block's words (decision 4).

**Conflict** (both changed): nothing is written. The page shows the Doc now and the base now side by side and, where the text jason last wrote is kept, a third column. Without it the page says: "The text as jason last wrote it is not kept (only its hash), so the page cannot say which side changed each block." That is a stated miss. It names the two ways the text could be kept (decision 5).

**Base changed, Doc not edited** (an update): the same table, read the other way: what the update changes, and the line "No person has edited this Doc since jason wrote it."

### The three choices

`EditChoices` lists three choices of equal weight, none chosen at first and none worded as the recommended one. Each says what it records, what it writes, and what it never does.

| Choice | What it does | What it writes | What it never does |
| --- | --- | --- | --- |
| **Fold the edit into the base** | For each differing block, names the source the words belong to and prepares the change as a **proposal**: a rule record's edit is a *proposed version*, in force on no day until the board adopts it (Civil Code 4350, 4355, 4360; `jason rule-change` for a subject that needs notice); a prose block's words are a change in the definition, a person's commit; a profile fact is the profile's. A proposal file is written for a person to apply, as onboarding's proposals are. After it is applied and the base regenerated, the blocks should agree; a second step, **Record that the Doc matches the base**, writes the two hashes so the standing becomes in sync | jason's own store (a signed proposal; later the signed accept); nothing in Drive; nothing in code | Apply the change, adopt a rule, or edit a record. Saving a proposal makes no rule |
| **Keep it as this association's own** | Records that this Doc is this association's own, by a named person, with a reason. From then on generation leaves it alone and a later change in the base is shown as "the base moved on: N blocks differ", not a conflict. A matching row for the profile's overrides, with its reason, is offered as a proposal (the base-templates design lists overrides in the profile's docs) | jason's own store (the standing `own`); a proposal patch for the profile, if the person asks | Change the Doc, or stop showing the difference |
| **Regenerate and lose the edit** | Writes the base over the Doc's body. **This is a loss and the page says so first:** "N paragraphs in M blocks, now in the Doc, will be replaced by the base's words. Drive's version history keeps the Doc as it is now; jason also keeps the text it read." It is an item of its own in an approval, decided alone, behind a real checkbox "I read the changes that will be replaced" that is on only after the diff has been opened | the Doc's body, by the signed approval | Run without the diff read; share, send, or delete anything; trash the Doc; or touch another Doc |

Each is a `Confirm` that spells out the record in the signed-in person's name ("Keep this Doc as this association's own, as Jane Example, because: …"), behind the write guard. A conflict offers the same three. **Regenerate and lose** is not the quiet default of `--doc create --yes`: the command writes only create and update steps, and leaves edited and conflict alone ([document-templates.md](../document-templates.md), section 11.5). The overwrite is a new, named act.

## The Doc's structure

After a Doc is read, `OutputStructure` shows the one thing the studio can say about a Doc's structure without reading a PDF: that it has the structure the plan wrote. It reuses the structure work's reader of a Doc (`jason.community.structure_gold`, which reads a Doc's headings, levels, tables, and page breaks and is read-only) ([structure-recovery.md](../structure-recovery.md)). It reports counts and checks only:

- **Headings by named style**: TITLE, SUBTITLE, HEADING_1 to HEADING_3, planned and in the Doc, each pair as numbers ("HEADING_2: 31 in the Doc, 31 planned") from `doc_output.verify` and the reader.
- **Level checks**: a skipped level (a HEADING_3 with no HEADING_2 above it), an empty heading, a heading style on a body paragraph, a numbered rule whose heading style is not the planned one. Each is a line in `Findings`, with the paragraph's text.
- **One named range per block**, planned and found. A Doc whose named ranges were lost cannot be compared block by block, and `OutputDiff` says so.
- **Contents**: the contents pass wrote links to the headings (planned depth, links written). The Docs API cannot insert a contents field; the page says "Insert > Table of contents makes the field from the same headings" as a note.
- **The PDF export would carry one outline entry per heading** ("31 headings"): a count, not a reading of a PDF.

Out of scope here, and said in "Not part of this pass": how well a PDF of the document would be recovered by its text layer.

## Data shapes

Made-up keys, folders, Doc ids, people, and dates. A rule's words are left out of the samples on purpose: on the screen they come from the record and the shelf (`jason cite`), never from a sample.

`GET /api/studio` (proposed): the list, from disk and the last read of the Docs.

```json
{
  "found": true, "asOf": "2099-10-05",
  "counts": {"documents": 3, "letters": 2, "inSync": 1, "baseChanged": 1, "edited": 1, "conflict": 0,
             "neverGenerated": 1, "docGone": 0, "notMadeByJason": 0, "toAdopt": 0, "notRead": 0, "needsAPerson": 1},
  "docsRead": {"at": "2099-10-05T09:12:00", "by": "Jane Example", "docs": 3},
  "items": [
    {"key": "rules-and-regulations", "title": "Rules of Example Village HOA", "kind": "rules", "group": "documents",
     "layout": "book", "blocks": 31, "gaps": 0, "draft": true, "adoption": null,
     "output": {"doc": {"address": "drive:1AbCdEfGhIjK-example", "name": "Rules of Example Village HOA", "kind": "pdf", "level": "P1"},
                "folder": {"name": "Templates", "syncsToPublic": false}, "writtenAt": "2099-10-02T14:00:00",
                "writtenBy": "Jane Example", "lastEditedBy": "Sam Placeholder", "lastEditedAt": "2099-10-04T16:30:00"},
     "standing": "edited", "reason": "a person edited the Doc; left alone", "next": "diff", "route": "#/studio/rules-and-regulations?tab=doc"},
    {"key": "owners-manual-template", "title": "Owner's manual (template)", "kind": "manual", "group": "documents",
     "layout": "book", "blocks": 14, "gaps": 1, "draft": false, "adoption": null,
     "output": null, "standing": "never generated", "reason": "no Doc yet", "next": "plan", "route": "#/studio/owners-manual-template/plan"},
    {"key": "owners-manual", "title": "Owner's manual", "kind": "manual", "group": "documents", "layout": "plain", "blocks": 12, "gaps": 0,
     "output": null, "outputNote": "Markdown and HTML only; its original is the manual Doc a person keeps", "standing": "no Doc output"},
    {"key": "hearing-notice", "title": "Notice of hearing", "kind": "letter", "group": "letters", "layout": "Letterhead", "blocks": 1, "gaps": 0,
     "output": {"doc": {"address": "drive:1ZyXwVuTsRqP-example", "name": "Notice of hearing", "kind": "pdf", "level": "P1"},
                "folder": {"name": "Templates", "syncsToPublic": false}, "writtenAt": "2099-09-20T10:00:00"},
     "standing": "base changed", "reason": "the base changed", "next": "plan"}
  ],
  "unavailable": [],
  "caveats": ["A standing is jason's reading of the disk and, where the Docs were read, of the Docs at that time. A person who edits a Doc after the read changes it."]
}
```

`GET /api/studio/definition?key=rules-and-regulations&layout=book&as_of=2099-10-05` (proposed): the header and the blocks.

```json
{
  "found": true, "key": "rules-and-regulations", "title": "Rules of Example Village HOA", "kind": "rules",
  "layout": "book", "layouts": ["plain", "guide", "book"], "asOf": "2099-10-05", "asOfKind": "run",
  "adoption": {"state": "draft", "line": "(the draft banner, as the Doc prints it)", "forDocument": false, "oneRule": [], "evidence": ""},
  "records": {"from": "derived", "path": null},
  "blocks": [
    {"id": "title", "kind": "prose", "title": "Rules of Example Village HOA", "source": "the definition", "asOf": null, "standing": "included"},
    {"id": "status", "kind": "status", "title": "", "source": "the adoption record", "asOf": null, "standing": "included"},
    {"id": "rule:4.2", "kind": "rule", "title": "4.2 Example rule", "source": "the Rules document's records", "asOf": null,
     "standing": "included", "record": "example-rule-4-2", "versionInForce": {"adopted": null, "boardItem": "", "proposed": false}, "gap": ""},
    {"id": "appendix", "kind": "policy-references", "title": "Policies published apart", "source": "the policies' own documents", "asOf": null, "standing": "included"}
  ],
  "commands": {"render": "jason document-template rules-and-regulations", "list": "jason document-template --list"}
}
```

`GET /api/studio/source?key=rules-and-regulations&block=rule:4.2` (proposed): one panel.

```json
{
  "found": true, "block": "rule:4.2", "kind": "rule",
  "record": {"id": "example-rule-4-2", "number": "4.2", "title": "Example rule", "level": 2, "segment": "rules/4.2",
             "versions": [{"adopted": null, "boardItem": "", "proposed": false, "inForce": true, "note": "the words as the source document has them"}]},
  "recital": {"found": true, "citation": "Rules 4.2", "text": "(the rule's words, as stored in the record)",
              "inForce": "the version in force on Oct 5, 2099", "caveat": "jason's copy of the rule as the manual holds it; the adopted copy controls."},
  "notes": [],
  "change": {"kind": "records-or-source", "from": "derived",
             "words": "The source is the owner's manual Doc. Edit it there; the next render reads it.",
             "doc": {"address": "drive:1MnOpQrStUvW-example", "name": "Owner's manual", "kind": "pdf", "level": "P1"},
             "command": "jason document-template rules-and-regulations --export-records",
             "afterwards": "A changed rule is a proposal until the board adopts it (jason rule-change)."}
}
```

A directory panel, `kind: "directory"` (proposed; `consent` is the directory-consent spec's shape, rendered as served):

```json
{
  "found": true, "block": "directory", "kind": "directory", "audience": "owners",
  "counts": {"roles": 4, "printed": 3, "notPublished": 1, "email": 2, "phone": 1, "address": 0},
  "roles": [
    {"role": "president", "name": "Jordan Example", "published": true,
     "fields": [{"kind": "email", "published": true, "masked": true,
                 "consent": {"confirmedBy": "Jordan Example", "confirmedAt": "2099-09-30", "how": "reply to a request", "record": "consent-0001"}},
                {"kind": "phone", "published": false, "consent": null, "why": "not published: no one has confirmed"}]},
    {"role": "treasurer", "name": "(not published)", "published": false, "fields": []}
  ],
  "change": {"words": "Publication is confirmed in the directory-consent record, by the person.", "route": "(the consent record)"}
}
```

`GET /api/studio/render?key=&layout=&format=md|html` (proposed): `{"found": true, "key": "...", "layout": "guide", "format": "html", "doc": {"address": "file:drafts/rules-and-regulations.document.html", "name": "...", "kind": "html", "level": "P1"}, "markdown": "(the Markdown)", "audience": "owners"}`. `GET /api/studio/definition` carries `compare` when `?compare=plain` is passed: `{"layouts": ["book", "plain"], "blocksIdentical": {"same": 31, "of": 31, "different": []}}`.

`GET /api/studio/check?key=` (proposed):

```json
{
  "found": true, "key": "rules-and-regulations", "computedAt": "2099-10-05T09:10:00", "clean": true,
  "check": {"placed": 31, "unplaced": [], "uncovered": [], "gaps": [], "unlabeled": [], "openTokens": [], "templateForm": false},
  "layoutIndependence": {"layouts": ["plain", "guide", "book"], "same": 31, "of": 31, "different": []},
  "proofs": [{"kind": "rules-vs-official", "same": 214, "labeled": [{"line": "(the line)", "why": "the status line {ADOPTION_STATUS}"}], "unlabeled": [], "equal": true}],
  "partMap": {"document": "rules-and-regulations", "asOf": "2099-10-05", "parts": [
    {"id": "rule:4.2", "kind": "rule", "title": "4.2 Example rule", "source": "the Rules document's records", "asOf": "2099-10-05",
     "standing": "included", "authority": "", "gap": false, "fields": [], "address": "", "attachedPages": null, "pages": null}]}
}
```

`GET /api/studio/plan?keys=rules-and-regulations,owners-manual-template` (proposed): the dry run, as `describe` prints it.

```json
{
  "found": true, "read": {"at": "2099-10-05T09:12:00", "by": "Jane Example"},
  "steps": [
    {"key": "rules-and-regulations", "action": "edited", "writes": false, "reason": "a person edited the Doc; left alone",
     "name": "Rules of Example Village HOA", "doc": {"address": "drive:1AbCdEfGhIjK-example", "name": "Rules of Example Village HOA", "kind": "pdf", "level": "P1"}},
    {"key": "owners-manual-template", "action": "create", "writes": true, "reason": "no Doc yet",
     "name": "Owner's manual (template)", "status": "draft",
     "folder": {"name": "Templates", "source": "the Drive home's Templates folder", "found": true, "willBeMade": false,
                "syncsToPublic": false, "matchesPattern": false, "sharedWith": "not read"},
     "requests": {"body": 412, "clearsSample": 1, "contentsPass": true}, "styles": {"HEADING_1": 6, "HEADING_2": 31, "NORMAL_TEXT": 240, "TITLE": 1},
     "tables": 2, "pageBreaks": 6, "header": "(the Letterhead's own)", "footer": "As of {AS_OF}",
     "tokensLeftOpen": ["ASSOCIATION_NAME", "AS_OF"], "tokensNote": "to be filled when the Doc is copied (template form)",
     "links": [{"words": "the Rules document", "target": "(the Rules Doc's id, known once it is created)"}], "namedRanges": 14,
     "blocked": [], "willNot": ["share", "send", "export", "delete", "trash", "touch another Doc", "write over a person's edit"]}
  ],
  "order": ["rules-and-regulations", "owners-manual-template"],
  "approval": {"kind": "google.doc", "risk": "R1", "approver": "one person", "reversible": "through Drive's version history",
               "plan": "jason approvals plan google.doc --scope document=owners-manual-template --by NAME", "id": null},
  "caveats": ["A dry run. Nothing here is written, shared, sent, or deleted."]
}
```

A blocked step carries `"blocked": [{"reason": "public-sync", "words": "A draft is never filed in a folder that syncs to the public list.", "folder": "(the folder's name)", "pattern": "(the rule's pattern)"}]`, and its `writes` is false.

`GET /api/studio/diff?key=rules-and-regulations` (proposed): the Doc against the base, by block, computed on the server.

```json
{
  "found": true, "key": "rules-and-regulations", "state": "edited", "readAt": "2099-10-05T09:12:00",
  "lastWritten": {"kept": false, "note": "only the hash of the text as last written is kept"},
  "counts": {"blocks": 31, "same": 30, "differ": 1, "outsideBlocks": 0},
  "rows": [
    {"block": "rule:4.2", "title": "4.2 Example rule", "state": "edited in the Doc",
     "doc": [{"op": "eq", "text": "(unchanged words) "}, {"op": "del", "text": "(removed words)"}, {"op": "ins", "text": "(inserted words)"}],
     "base": "(the base's words)", "asWritten": null,
     "source": {"block": "rule:4.2", "route": "#/studio/rules-and-regulations?tab=blocks&block=rule:4.2"}}
  ],
  "choices": {"fold": true, "own": true, "regenerate": true, "why": ""}
}
```

`GET /api/studio/structure?key=` (proposed): `{"found": true, "readAt": "…", "headings": {"TITLE": {"planned": 1, "inDoc": 1}, "HEADING_1": {"planned": 6, "inDoc": 6}, "HEADING_2": {"planned": 31, "inDoc": 31}}, "levelChecks": [], "namedRanges": {"planned": 14, "inDoc": 14}, "contents": {"depth": 3, "links": 37}, "pdfOutlineEntries": 37, "verify": {"problems": [], "at": "2099-10-02T14:00:00"}}`.

**Writes** (proposed; each behind the write guard, `X-Jason-Token`, with `by` from "Signed in as"; a write with no `by` is 400):

- `POST /api/write/studio/read` `{"keys": ["rules-and-regulations"], "by": "Jane Example"}`: reads each known Doc and its Drive metadata, stores the text read under `data/studio/reads/` with the day and the name, and answers per Doc `{key, ok, readAt}` or the reason (`gone`, `no access`, `Google not connected`). It writes nothing to Drive.
- `POST /api/write/studio/fold` `{"key": "...", "blocks": ["rule:4.2"], "by": "..."}`: writes the proposal files, one per differing block, and the signed record; answers the files.
- `POST /api/write/studio/own` `{"key": "...", "reason": "…", "by": "..."}`: records the standing `own` with the reason; refuses an empty reason (400) and a Doc not read (409).
- `POST /api/write/studio/accept` `{"key": "...", "by": "..."}`: after the person has applied the change, reads the Doc again, and only if every block is `same` records the two hashes; otherwise 409 and the diff.
- **A Doc written or overwritten is not a studio write.** It is the engine kind `google.doc`: `jason approvals plan google.doc --scope document=KEY --by NAME`, then decide and sign in `#/approvals`, then apply (`jason approvals apply ID --yes --by NAME`, or from the browser with `--allow-apply`).

## What the design must keep

- **Recite first; label the reading** (principle 2). A quote or rule block shows its `Recitation` (the words whole, the version in force, the caveat) before anything jason says about it. A rule's words are the association's, stored in the record; the page never rephrases them.
- **Nothing is edited in place.** The studio has no field for a block's words, a rule's words, or a Doc's text. Each block has a way back to its source and the page says what kind of change the source takes (a proposal, a person's commit, the board).
- **A rule changes only by the board.** A proposed version is in force on no day. Folding a Doc's edit into the base makes a proposal and adopts nothing ([approval-workflow.md](approval-workflow.md#12-the-board-decides-by-vote)). The adoption line is read-only at every state, and no control says "Approve" for a board matter.
- **A draft is never filed where the public list reads.** The server blocks it and the plan says why; the page does not offer to override.
- **jason proposes; a person writes.** A Doc is created or replaced only by a signed approval, shown first as a plan of exactly what would be written (name, folder, requests, styles, tables, links, tokens), and read back after. There is no bare "Generate" button.
- **A person's edit is theirs.** The studio shows the difference first and never writes over it without the named loss, a diff read, and its own approval item. Drive's version history is named as where the edit remains.
- **A miss stays a miss** (principle 8). A Doc not read is "not read", not "in sync". The text last written, a directory consent never confirmed, pages of a PDF not yet made, and a folder's sharing not read are each said in words. A part not on file is a visible gap, never last year's words.
- **Nothing on load calls Google.** The list and the pages read disk. A Doc is read by a person's click, signed in and logged, and the read is stored with its time. A missing Google token shows the command; the page never prompts.
- **The word is the state.** Every standing, difference, and check is a word, and the color only repeats it.
- **Privacy by level** (principle 6):

  | What | Level | Shown |
  | --- | --- | --- |
  | a definition's blocks, their sources named, the plan, the check | P1 | roster people |
  | a rule's words, a draft rules document, a Doc's text read | P1 | roster people; a draft marked draft |
  | a statute or a public governing document's words | P0 | always, in `Recitation` |
  | a directory's roles and published names | P1 | roster people, as owners would see them |
  | a contact value (email, phone, address) | P2 | masked by the server until asked, logged; the plan and list carry counts only |
  | an embedded file (a stored attachment) | the file's own level | a P3 file by kind only outside the private view ("opens in the private view") |
  | a Doc's folder id, a Doc id | not secret, and not text | shown as a name or a `Doc` chip, never in a URL |

  The screen is board-only, never in the owner view, and nothing here is P4.

## Where it goes

- **Governance → Documents studio** (proposed): `#/studio`, with `?group=` and `?state=` filters and a count in the nav ("needs a person"). One document: `#/studio/<key>` (`?tab=blocks|layout|check|map|preview|doc`, `?layout=`, `?compare=`, `?as_of=`, `?block=<id>`); its plan: `#/studio/<key>/plan`. A URL carries a key, a layout name, a block id, and a day, never a document's words or a name ([security-and-privacy.md](security-and-privacy.md#urls)).
- **Roles.** Officers, managers, and administrators see it; the owner view does not. Signing is the approval's: any person on the roster named on it, for this kind.
- **`#/templates`** stays the place a letter is filled; a letter's row here links to it ("Fill a letter").
- **`#/approvals`**: an approval of kind `google.doc` is reviewed there with `PlanReview`; the studio links to it and to the studio's own plan.
- **`#/rules`** (Rule changes, built), **`#/decisions`**: where a rule's adoption goes; the studio's rule panel links to them and records nothing.
- **Records** (`#/records`, [screens/records-and-library.md](screens/records-and-library.md)): a Doc's revisions beside the studio's Doc tab.

**Loaders and writes to add** (all proposed; a loader wraps a function that exists, except where marked "to write"):

| Name | Function behind it | Reads | Writes |
| --- | --- | --- | --- |
| `studio` | `jason.web.extra.studio:studio` (to write) over `rules_documents.prepare` and `definition`, `document_docs.jobs_for`, `template_gen.load_state`, `Community.manual_documents()` and `document_templates()`, the last read store, and the Drive catalog's modified time and last editor | disk only | — |
| `studio-definition` | `rules_documents.definition`, `document_templates.assemble`, `part_map`, `rules_document.adoption_status`, the records' `version_on` | disk only | — |
| `studio-source` | per kind: `RuleBook` and `version_on`, the `cite` loader, `form_render`, `rules_documents.directory` and the consent record, `Embedded`, the adoption events | disk only | — |
| `studio-render` | `MarkdownRenderer`, `HtmlRenderer`, and the layout independence comparison (to write: wraps what the tests assert) | disk only | `data/drafts/` (its own renders) |
| `studio-check` | `document_templates.check`, `rules_documents.prove_rules`, `prove_switch`, `part_map` | disk only; the manual's own pass | `data/drafts/` (the manual's own outputs) |
| `studio-plan` | `document_docs.plan_docs` over the stored reads, `describe` as data (`Step.as_dict`, to write), the folder's sync check (`Community.sync_rules`, to write) | disk only; the stored read | — |
| `studio-diff` | the stored read of the Doc split by its named ranges, compared by block with the rendered block text (to write), over `doc_output` | disk only | — |
| `studio-structure` | `doc_output.verify`, `structure_gold`'s Doc reader (read-only), the stored read | disk only | — |
| write `studio/read` | `GoogleDocs.get`, the Drive metadata read (read-only calls), stored under the store lock | Google | `data/studio/reads/` |
| write `studio/fold`, `studio/own`, `studio/accept` | to write: signed records and proposal files in jason's own store; `accept` writes the two hashes into `data/templates/<profile>.json` through `template_gen.save_state` | — | jason's own stores; the profile and code only by a person |
| engine kind `google.doc` | the planner (`document_docs.plan_docs`) and the applier (`document_docs.generate`, `template_gen.generate`), each item decided and signed; `risk` R1, one person, reversible through revisions | Google (the plan) | Google (the apply, behind `--allow-apply`) |

**CLI equivalents that exist today:** `jason document-template --list`, `jason document-template KEY [--layout L] [--as-of DAY] [--records MODE] [--rules-from-document]`, `jason document-template KEY --export-records`, `jason document-template [KEY] --doc plan`, `jason document-template [KEY] --doc create --yes`, `jason templates --lint`, `jason templates --generate [--yes]`. **Proposed, not built:** `jason document-template KEY --own --reason TEXT --by NAME`, `jason document-template KEY --accept-doc --by NAME`, `jason document-template KEY --fold --by NAME`, and the overwrite as an approval item. `jason-mcp` stays read-only; a read tool that lists the definitions and their standing may follow, and no tool writes a Doc.

## Accessibility

As [components.md](components.md#accessibility), with these particulars.

- **The list is a real table** (`DataTable`) with a caption ("Documents, grouped by kind"), the sort announced, a polite live region for the filtered count, and a row that is a link to its page. A group is a heading above its table.
- **The outline is nested lists** with headings, not an ARIA tree. Each row is a labelled group; "gap" is a word on its first line; opening a `SourcePanel` moves focus to its heading and Escape returns it to the row.
- **`LayoutCompare` is two labelled sections** ("Layout: book", "Layout: plain") with a line between them that says whether the blocks are identical; nothing depends on seeing both at once.
- **`OutputDiff` is a table with row headers** (the block). Each cell says "In the Doc:" or "The base says:" in visually hidden text, and an inserted or removed word is announced by a hidden "inserted:" or "removed:" and drawn with an underline or strike as well as color (1.4.1).
- **`EditChoices` is a `<fieldset>`** with a legend ("What to do with the Doc's edits, as Jane Example"), a radio group none of whose options is checked at first, the field a choice needs opening in place with a visible label, and an error that names it ("Keeping a Doc as this association's own needs a reason."). The checkbox for the loss is a real checkbox with a label and `aria-describedby` naming the loss line.
- **Every write is a `Confirm`** (two clicks, the record spelled out). After it, the result is in `role="status"` in place and focus stays on the row. A refusal that stops the work is `role="alert"`.
- **A live read** announces its progress politely ("Reading 2 of 3 Docs") and never moves focus.
- **The plan is a definition list** per step, in the order the lines above are listed; a blocked step's reason is the first line and `aria-describedby` of its disabled control.
- **Shortcuts** as [patterns.md](content/patterns.md#keyboard-use): `j` and `k` between rows, `?` lists them. Nothing needs a drag; every target is 24 by 24 CSS pixels or spaced to pass.
- **Nothing times out.** A reason typed for keeping a Doc stays in the form until the person leaves.

### The phone layout (under 720 px)

- The list becomes cards: title first, then the standing word and the next step on one line, then the Doc and when it was written. Filters collapse into a disclosure with the active count.
- The definition page's tabs become stacked sections under a "Go to section" select; one section is open at a time.
- The outline's rows are cards: the title, then kind and standing as words, then the source; the source panel is a drawer from the foot that returns focus to its row.
- `LayoutCompare` stacks: the first layout, a line saying whether the blocks are identical, then the second, each under its own heading; never side by side.
- `OutputDiff` stacks per block: the block's title, "In the Doc", "The base says", each its own paragraph, with the change marks as words.
- The plan's lines stack as a definition list; `Confirm` is full width and not sticky; `FolderLine`'s sync notice stays above the control it concerns.
- "Go to" replaces the nav as `ConsoleShell` does; the dock's drawers float below 1200 px.

## States

| State | Shown |
| --- | --- |
| Empty | a profile with no letter templates: "The profile has no letter templates." The definitions are general, so the Documents group is never empty |
| Loading | the frame with "Opening…" (`aria-busy`), and for a read of Docs the count read so far |
| Error | the tool's own note and the command that fills it (no outline on disk: `jason outlines --fetch`; no classification: `jason manual --classify`); the other rows still list |
| Not authorized | the server's reason in words; the Doc's own `Doc` state "Not allowed" when a view answers 403; the owner view has no route |
| Google not connected | "The Docs were not read. Sign in from a terminal to read them." with the command; standing shown as recorded |
| Folder not found | the plan step is blocked: "The folder the profile names was not found in Drive. Nothing is created." The way is the profile's row, a person's commit |
| No letterhead Doc | blocked: "The profile's letterhead names no Doc to build from." |
| Doc deleted or in the trash | the word "Doc gone"; the plan would create a new Doc and says the old one is not restored; the stored read is kept as the last text known |
| Doc not accessible | per Doc, "No access", with the account jason is connected as; no other state is guessed |
| Stale read | the read is older than the last change to the Doc's definition: "read Oct 5, 09:12; the definition changed since", with Read the Docs |
| Approval changed since the plan | `ChangedBanner`: the Doc was edited between plan and apply; nothing was written; the new plan |

## Decisions for the design

Settled by the axioms in this pass, and why:

- **No in-place editing of generated text.** "Templates are written once": a generated copy is generated, not edited by hand; the way back is the source.
- **Plan, then a person signs, then write, then read back.** Principle 4 and the approvals engine; there is no bare button.
- **A draft is never filed where the public list reads.** The plan blocks it; publishing is a different act.
- **The adoption is not recorded here.** Principle 5: a vote at a meeting, recorded by an officer.
- **A person's edit is shown first and lost only by name.** "A person's words are theirs" (the draft-from-item rule) and the version history named as where the edit remains.
- **The page works nothing out.** Standing, diff, counts, folder sync, and checks are the server's.
- **Template-form open tokens are not defects.** A filled document's are.

Still open, for a person:

1. **One screen for letters and definitions, or two.** The list shows both; the letter template's fill screen is `#/templates`. Decide whether the studio absorbs `#/templates` or stays beside it.
2. **Placement and roles.** Governance beside Canvases and Templates, or Records; and whether a manager sees the plan and signs or only an officer.
3. **Where a chosen layout lives.** A preview only (the Doc uses the definition's own layout today), or a field on the profile's document row (`ManualDocument`), as a proposal a person applies.
4. **What counts as an edit.** The hash folds whitespace. Decide how an inserted contents field, a comment, and a suggested edit are told from an edit of a block's words, and whether a pending suggestion counts.
5. **The text as last written.** Only its hash is kept, so a conflict cannot be told which side changed which block. Decide whether to keep the written text beside the hashes (a store of its own, P1) or read Drive's revision at the written time.
6. **"Keep as own".** The standing in jason's state, a checked-in override row with its reason in the profile, or both; and whether an own Doc still shows "the base moved on".
7. **The overwrite.** One person or two, and whether reading the diff is a gate (as drafted) or a notice.
8. **The Doc's owner and a stamp.** The Doc's creator in Drive is the connected Google account. Decide whether a Doc also carries which approval made it (a Drive description or a property), and what it says.
9. **A folder's sharing.** Whether the plan reads who the folder is shared with (a Drive call) or says "not read".
10. **Reading the Docs.** A person's click each time, or a stored read counted fresh for a time; and whether many Docs are a job.
11. **The check's cost.** The proofs run the manual's own pass. Decide whether the check is cached with its time or run on request as a job.
12. **The consent shape.** `consent` is drawn as served by the separate directory-consent spec; the two shapes are reconciled when it lands.
13. **The day.** A document is read as of the day of the run or the day it is dated ([document-templates.md](../document-templates.md), decision 4). Decide whether `AsOfControl` shows both and which governs by default.
14. **HTML preview.** Served by jason and sanitized (`Doc` `inline`, kind `html`), pending the sanitizer the documents page proposes; until then, Markdown only.
15. **Contract of `DiffTable`.** Four handoffs need it (a section's versions, a quote, a scan's two readings, this one). Decide one contract (`rows` of `{id, label, state, left, right, marks}`, labeled sides) that `QuoteDiff` and `OutputDiff` share.

## Not part of this pass

- Building anything: no loader, route, component, or write above exists, and `jason document-template` and `jason templates` are unchanged.
- The PDF output and the page numbers of the part map, and checking a generated PDF against its part map with `jason segments`.
- How well a PDF of a document would be recovered from its text layer: the structure-recovery scores (F1 by degradation) are another page's. This page counts headings and checks levels in a Doc only.
- Editing a rule record, a form, a guide, or a directory entry: each is its own screen's. Recording the board's adoption of a rules document, or of a rule: `#/decisions`. Recording a person's consent to publish a contact: the directory-consent spec.
- Annual disclosures and the other packets as definitions (the packet-to-definition builder is phase 2 of the model): their rows join the list when they are definitions.
- Publishing or sharing a Doc, filing it on the public list, sending or mailing it, and trashing or deleting one: never from this screen.
- A write tool in `jason-mcp`.
- The previews: the design project's authored preview for each component follows the build, as for the earlier handoffs; fixtures will be `ui/src/components/documentsstudio.test.tsx` and its siblings, from the sample data above.
