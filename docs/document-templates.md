# Document templates: one definition of a document, a layout apart from its blocks

Status: **design, with phase 1 built** (October 2026), and the Rules document, the owner's manual template, and their Docs built after it ([section 11](#11-the-rules-document-the-owners-manual-template-and-the-docs-they-make)). Code: `jason.community.document_templates` (pure) and `jason.tasks.document_templates` (disk); command `jason document-template`.

The owner's manual ([owners-manual.md](owners-manual.md)) is already most of the way to a generated document. Its base template is a list of tokens (`{PART:front}`, `{INCLUDE:rules}`, `{EXCERPTS}`) and each token is read from a source each time the manual is rendered, so the guide never keeps a stale copy. What it lacks is a name for that shape, so the next document (the annual disclosures, the resale package, a welcome guide) can use it without copying it. This design gives it one: a **document definition** with a **layout** (how it looks) and **blocks** (what it says, each rendered from its source). It adapts the form engine's idea, one definition with many renderers ([forms.md](forms.md)), from a form to a whole document.

## 1. What exists, and what is reusable

| Piece | Where | What it does | Reuse |
|---|---|---|---|
| The manual's base template | `src/jason/templates/manual/owners-manual.md` | Ordered tokens: a cover slot, guide slots, the governing documents' excerpts, the rules, three policies, guidance | **Becomes** layout plus a block list (use case 1). The file stays; a loader reads it into a definition. |
| Manual render | `jason.community.manual.render` | Fills `{PART}`, `{INCLUDE}`, `{EXCERPTS}`, `{LAW}`, `{ADOPTION_HISTORY}` and the identity tokens; returns Markdown and one `Chunk` per piece | **Reused unchanged.** The token fill is extracted as `fill_token`, called by `render` and by the new blocks, so the two cannot differ. |
| `Chunk` (markdown, words, source span, label) | `jason.community.manual` | A rendered piece carries the span it stands for, or a label for why it has none | **Reused** as the unit every block returns. Phase 2 moves it to a neutral module. |
| Render check | `manual.check`, `tasks.manual.diff_text` | Every word of the source sits in one chunk, in order; a chunk that differs carries a label; an unlabeled difference is a defect | **Generalized** (section 7): the placement check works for any definition; the word comparison stays with blocks that stand for a source span. |
| The form engine | `jason.community.forms.FormTemplate`, `form_render` | One definition (questions with stable `field` ids), renderers for a paper form (Markdown, HTML), a fillable PDF, a Google Form, a PayHOA build sheet | **Reused:** a form block calls `form_render.paper_markdown`. **Adapted:** the renderer idea and the stable-id idea apply to blocks. |
| Identity, citation values | `jason.community.template_values` (`Layer`, `resolve`, `profile_values`, `lint`) | Layered `{TOKEN}` values: the profile's identity, citations, then a run's own; an empty value never overrides a filled one; a lint sorts a template's tokens by origin | **Reused** as the value layers of every document and of its prose blocks. |
| Letter bodies and the Drive template route | `jason.community.templates` (`BODIES`, `DocumentTemplate`, `body_markdown`), `tasks.template_gen`, `tasks.template_docs` | A body of styled lines becomes a Drive Doc with `{VARIABLE}` tokens, copied and filled | **Reused** for the Doc output (section 4). The `Block` enum there names a line's style (text, heading, bullet); it is a *layout* concern and stays there, under the name "line style". |
| Packets | `jason.community.packets` (`Packet`, `Part`, `PartSource`, `SourceKind`), `tasks.packets`, [packets.md](packets.md) | Several documents as one PDF: a part found fresh for the year from a template Doc, the library, Drive, a generator, or an addendum; variants per building; `required` and `authority` on a part; page choice | **Reused** as the model of an embedded-document block (section 3, 5, and the annual disclosures use case). |
| Notice requirements | `jason.community.notices` (`NoticeRule`, `NoticeRequirement`, `Timing`), `notice_catalog` | What the statute requires of each notice, to whom, by what method, by when, each row tied to the statute's words | **Reused** for the clock of a document that is delivered (section 6.3). |
| Statute and document words | `{QUOTE:key#n}` (`tasks.section_refs`), `{LAW:...}`, `statutory_terms` | A passage read from the stored authority, with its citation | **Reused** as the quote block. |
| Rule classification | `manual.classify`, `Segment`, `Target`, the concordance, `permanent_ids` | Which words are rules, copies, policies, guidance; each piece's book and number; every old address resolved; a section's permanent id through amendments and renumbering | **Reused** as the rule records' base (section 4). |
| Rule changes | `jason.community.rule_changes` (`RuleChange`), `jason rule-change`, `manual_rule_change` | A proposed change as data, noticed under 4360 | **Reused** as the proposal path. |
| Officers and private facts | `Community.officers()`, `jason.community.private.facts` | Roles and names from `data/spec`, never checked in | **Reused** by the directory block. |

What is **new**: the layout as a separate record; block kinds as classes with a common contract (source, as-of day, chunks, gaps); the Markdown and HTML renderers over one definition; the embedded-document block; the directory block with publish flags; the part map written beside a generated PDF.

## 2. The model

```
DocumentDefinition  (key, title, kind, authority, layout, items)
   Layout           how it looks: page, headings, header, footer, styles by token, contents, cover, page breaks
   items            an ordered list of Prose and Block entries
      Block         what it says, from a SOURCE, as of a DAY, rendered and never copied
```

**Layout owns style, and only style.** A layout says: the heading level of a block's title and whether headings are numbered; the running header and footer (tokens: `{ASSOCIATION_NAME}`, `{DOCUMENT_TITLE}`, `{AS_OF}`); fonts, sizes, and colors as named tokens, not values scattered through a body; whether there is a table of contents and how deep; whether there is a cover and what it carries; where a page breaks (before a block, before a heading level, an own sheet where the law asks for one, as `Part.own_sheet` does); the separator between blocks. A block never carries a style. A second layout changes how the same blocks look, and no block's words change (tested).

**Blocks own content, and only content.** Each block has:

- an `id`: stable, unique in the document, the way a question's `field` is stable in a form, so a check, a part map, and a later reading name the block the same way however the document is reordered;
- a **source**: a named place its words are read from;
- an **as-of day**: the day the source is read as of (the version in force that day), defaulting to the day of the run, recorded in the output;
- `render(context) -> BlockResult`: chunks (Markdown with the span or label each stands for), the gaps it found, and its part-map entry.

The block kinds:

| Kind | Source | Reads |
|---|---|---|
| prose | the definition itself | Text written once, with `{TOKENS}` from the value layers. The only block whose words live in the definition. |
| part | the profile's guidance slot | The guide's own words for a slot (`front`, `welcome`, `contacts`, `guidance`): `{PART:slot}` today. |
| rule book | the classification and the rule records | A whole book (`rules`, `disc`, `coll`, `arch`) or one section, with flags `official` and `optional`: `{INCLUDE:book}` today. By reference: section 4. |
| excerpts, quote, law | the stored governing document, the stored statute | The passages by `{QUOTE:key#n}` and `{LAW:CIV 5730(a) quoted}`, with their citations. |
| form | a `FormTemplate` | The paper form (title, questions with their boxes and lines, certification, signature line), rendered by `form_render.paper_markdown`. The block's `form` is the form's own key, so the form in the document and the live form are one definition: change a question once and both change. |
| directory | `Community` facts and `data/spec` | Roles and the contact fields the board chose to publish: section 5. |
| guide Q&A | the profile's guidance rows | Questions and answers, each a labeled piece of guidance. |
| history | adoption events, rule-change records, a detector's timeline | When each part was adopted or changed: `{ADOPTION_HISTORY}` today. |
| computed | a function of the stores | A table of figures or dates (an assessment schedule, a deadline list), with the inputs it read. |
| embedded document | another document definition, a stored file, or a packet part | Section 6. |

**Rendering is a fold, not a template language.** A definition's items are rendered in order. Prose is filled from the value layers; a block returns its result; the layout wraps the result. No block reads another block's output, and the layout never reads a block's source. That keeps the two halves independent.

## 3. Many outputs from one definition

The form engine writes one `FormTemplate` as paper Markdown, paper HTML for a PDF, a fillable PDF, a Google Form, and a PayHOA sheet. The document engine does the same from one `DocumentDefinition`.

| Output | How | Status |
|---|---|---|
| Markdown | The renderer joins prose and block Markdown and applies the layout's heading and header rules. This is `jason manual --render`'s output today. | phase 1 |
| HTML | The same Markdown through one converter, wrapped in the layout's page, header, footer, and style tokens as CSS variables. | phase 1 |
| PDF | HTML printed by the installed Chrome or Edge, as the packets' generated parts already are (`tasks.packets`). The layout's page breaks and `own_sheet` carry over. | phase 2 (path exists; wiring is not done) |
| Drive Doc | Not rendered from scratch. A **template Doc** (the letterhead, header, footer, and styles set once in Docs) is copied and its `{VARIABLE}` tokens filled with the rendered blocks, as `DocumentTemplate` rows and `tasks.template_gen` do for letters. The Doc is the original once built ([base-templates.md](base-templates.md)); the layout's fonts and colors are then the Doc's styles, not a second set. | phase 2 |

What is shared between the form engine and the document engine:

- **The renderer protocol:** one definition in, one output out, no renderer reading another's output. A renderer is a function of the definition and a context (values, sources, the as-of day).
- **Stable ids:** a form's questions have a `field`, a document's blocks have an `id`, and a block that wraps a form carries the form's key and its fields unchanged.
- **The value layers** of `template_values`, with the same rule: an empty value never overrides a filled one, and the lint sorts tokens by where they come from.
- **The placement check:** the form's `check` asks that every required question is answered; the document's check asks that every block is placed, and that every difference from a source is labeled.

What the document engine adds: the source and as-of day on every block, and the layout split. A form's style is a small record (`FormStyle`); a document's layout is the same idea made larger.

## 4. Rules by reference, maintained as structured data

The aim is the user's: the rules live in one structured place, a document **includes** them by reference, and a change to a rule is one edit that every including document picks up the next time it is rendered.

### 4.1 What exists

The owner's manual's rules today are words in a Google Doc. `jason manual` reads that Doc's outline, classifies each section (rule, copy, policy, guidance, mixed) by rule rows with evidence, gives each piece a book and a number, keeps a concordance from every old address to its new one, and renders the official rules word for word. `permanent_ids` gives a section an id that survives amendments and renumbering. `RuleChange` records a proposed change; `manual_rule_change` separates passages that changed with no adoption found; `adoption_history` lists adoption events. That is most of what a rule record needs, but it is derived from a document, not stored as records.

### 4.2 The rule record

A **rule record** is the structured form of one operating rule (or policy section):

| Field | Meaning | Today |
|---|---|---|
| `id` | A permanent id that does not change when the rule is renumbered or reworded | `permanent_ids` has it for outline sections (`doc@base/4.15(a)`); **not yet** used for the manual's pieces, which are keyed by `Segment.id` (the outline number, so a renumbering breaks it; the concordance aliases it) |
| `number`, `book` | Where it prints now: `rules`, `B-7` | `Segment.address` |
| `title`, `text` | The words, as adopted | the outline's words |
| `subject` | What it is about (parking, pets, architectural) | topic readers; **not stored** per rule |
| `kind` | rule, policy, copy, guidance | `SectionKind` |
| `adopted` | The day and the board item that adopted this version | `AdoptionEvent` (`on`, `record`, `evidence`) |
| `supersedes` | The record this version replaces | the detector's timeline; **not stored** as a link |
| `copies` | What it restates, with its state | `Segment.copies`, `CopyState` |

A record has **versions**: each a body, an adoption day, and the board item. The **version in force on a day** is the newest adopted version on or before that day. The record's text is the version's text.

### 4.3 Where the records live

Do not add a second store. The records are the manual's classification plus the history it already holds, given three additions:

1. **A stable id per piece.** Use `permanent_ids` (the piece's id at its first version) and keep `Segment.id` as an alias, the way the concordance keeps old numbers. Whether the outline's keys are enough: they are enough while the Doc is the source, because the outline is re-read each run and the concordance resolves old numbers. They are not enough once records are the source, because a rule must then keep its id with no outline to read. That is the one open data decision (section 9, item 1).
2. **Versions with the board item.** `AdoptionEvent` already has the day, the action, and the record. Add the board item key and the version's words (a digest today) so "in force on DAY" can print the words.
3. **`supersedes`**, a link from one version to the one it replaced.

Phase 1 does **not** build the store: the rule book block reads the classification as the manual does, so the migration is exact. Phase 2 stores the records and has the classifier write them; the block then reads records instead of the outline. Because the block's contract (source, as-of, chunks) is the same, no definition changes.

### 4.4 A change is a proposal until the board adopts it

jason proposes; the board adopts. A changed record never becomes a rule by being saved:

1. A person (or jason, from a request) edits a **proposed version** of a record. It has no adoption day, so it is not in force on any day.
2. For a subject in Civil Code 4355(a), `jason rule-change` builds the notice with the proposed text first and its purpose and effect (4360(a)). For another subject, a board item carries it.
3. The board adopts at a meeting. A person records the adoption: the version gets its day and board item, and becomes the version in force from that day.
4. Every document that includes the rule regenerates. The rule book block renders the version in force on the document's as-of day, so a document dated before the adoption still shows the earlier words.

A passage whose words changed with no adoption found stays what it is today: a labeled note, never printed as the rule.

### 4.5 "As in force on DAY", and the official document

`as_of` on the rule book block selects versions. The manual and the official rules document render from the same records with different flags: the manual includes the rules, the policies, and the guide's notes beside them; `official` prints only the rule text word for word, with a bracketed note where guidance was left out. The word-for-word official rules document is therefore **derived**, never a second file to keep, and `jason manual --render` keeps writing it.

## 5. The directory and privacy

A directory block lists the board, the manager, and the association's contacts. Its words are people's names, emails, and phone numbers: private facts, kept in `data/spec/<profile>/<topic>.json`, read through `jason.community.private.facts` and `Community.officers()`, never checked in.

Rules for the block:

- **Each field has its own publish flag.** A directory entry carries a role, a name, and contact fields (`email`, `phone`, `address`); each contact field has `publish: true` or false, default **false**. The role and the name publish only when the person has agreed too (the entry's own flag). An unflagged field is a miss, never printed.
- **A person confirms publication.** A flag is set from the person's own confirmation (the answer to a request, recorded with who and when), not by jason. jason proposes the list; the person decides.
- **A document that goes to owners includes only what is published.** The block takes an `audience` (`board` or `owners`); for `owners` it renders only published fields. For `board`, it may render all, and the output is a draft that is not distributed.
- **The rendered directory is never in a tracked file.** Output goes to `data/drafts/`. The definition holds no names. The checked-in examples and tests use made-up people (`tests/fixtures/spec`).
- **A gap is visible.** A role with no one in it renders a line saying so (the vacancy provision, when the profile has one) instead of being dropped.

## 6. The annual disclosures: a document made of documents

The annual disclosures are the second use case, and the one that shapes the model most. The annual packet is a cover and the statutory notices, with the budget report, the policy statement, the insurance summary, the reserve study summary, the collection policy, and forms embedded. Each embedded document has its own source, its own as-of day, and its own standing; the outer document supplies the cover, the order, the statutory headings, and the delivery wording.

### 6.1 What the packet machinery already does

[packets.md](packets.md) and `jason.community.packets` already do the assembly: a `Packet` is an ordered list of `Part`s; each `Part` has a `title`, a `PartSource` (`TEMPLATE`, `LIBRARY`, `DRIVE`, `GENERATED`, `ADDENDUM`) that says where *this year's* copy is found, an `authority`, `required`, an `own_sheet` flag, and page choice (`pages`, `keep`, `drop`); a packet has `variants` (one PDF per building) and standing `values`; `jason packet --year` plans (parts found or missing, tokens open), builds the PDF, and `jason review annual-disclosures` checks the assembled text against the law.

What it does not do: it is a PDF splice plan, not a document. It has no layout (the cover and headings live inside the template Docs), no as-of day per part (a part is "the newest file matching a pattern"), no notion of one part being a template with its own values, no record of the output's structure, and no check of the packet against what the statute requires.

### 6.2 What the document-template model adds or replaces

`Part` becomes an **embedded-document block**; `Packet` becomes a `DocumentDefinition`; the splice stays the PDF output's job. Concretely:

- **Embedded-document block.** A block that includes another document by reference. Its source is one of: a nested **document definition** (the budget report is itself a template, with its own values, and renders recursively); a **stored file** (a PDF or Doc the packet attaches rather than re-renders: an insurer's declarations, the reserve study summary); a **form** (a block of kind form). It carries its own `as_of`, its own source, and its standing: required (with its authority), optional, or addendum for some recipients.
- **Attach, do not re-render.** For a stored file the block is a layout-level instruction: put these pages here, from this stored address, unchanged. It records the file's stable address (library path or Drive id), its page count, the pages chosen (`pages`, `keep`, `drop` carry over), and the `own_sheet` page-break rule. The Markdown and HTML renderers print an attachment line (title, address, pages); the PDF output splices the pages.
- **A required part that is missing or stale is a visible gap.** Never silently skipped. The block prints a line in the document ("Required by Civil Code 5300(b)(5): the pro forma budget, not on file for this year.") and records the gap in the result. Stale means the source's as-of is not the document's year: the insurance summary uses only the terms in force on the first day of the fiscal year, so a term not on file is a gap, never last year's figures ([packets.md](packets.md)). The gap wording is the manager review's wording, so one report speaks one way.
- **The checklist of what is required.** A definition lists the statute's requirements as **required parts** (each with its authority); the check compares them with the blocks the definition includes and reports an item the statute requires that no block covers, and a block no requirement names (a part kept for the board's choice, so labeled). Requirements come from the models' checklists and the notice catalog, not memory. Phase 2 reads the packet requirements; phase 1 carries the `required` and `authority` fields on the block.
- **The clock.** What must reach members by when comes from the `NoticeRequirement` rows (`Timing`, `Anchor`, `Method`, recipients), never from dates in a definition's prose. A definition names the requirement key it satisfies (`delivers: ["annual-budget-report"]`); a computed block renders the deadline from the row and the year's anchor days (`AnswerCycle`), and a delivery wording block recites the method the row allows.
- **A part map beside the output.** A generated packet's PDF has a known structure. The renderer writes, next to the PDF, a **part map**: the document key, and for each block its id, title, kind, as-of, source address, standing, and **pages** (first and last page in the output). A later `jason segments` of that PDF can be checked against the map: the segmenter's findings are expected to match the known part list, and a disagreement is a finding about the segmenter or the splice, not a guess about the packet. Phase 1 writes the map with block order and sources; page numbers need the PDF output (phase 2).
- **Variants.** Per-building variants stay a definition parameter (`variants`, `{building}`), as for `Packet`.

The packet registry in the profile (`Community.packets()`) is unchanged for now: phase 2 adds a function that builds a `DocumentDefinition` from a `Packet`, so existing packets render through the new model without rewriting the profile's rows.

## 7. The check

The manual's check says: the rendering is the source, apart from layout and labeled changes. Generalized:

1. **Every block is placed once**, in the definition's order, and every requirement (6.2) is covered or a gap is shown.
2. **Every chunk carries what it stands for**: the source span it was read from, or a label (editorial, a statute read from disk in place of a copy, a note left for a person).
3. **A difference with no label is a defect.** For a block that stands for a source span (the manual's pieces), the words are compared with the source as `manual.check` does today; for a block that is read from a store (a form, a directory, a figure table), the check is that its inputs are named and its output has no token left open.
4. **A layout never changes a block.** The check renders the same blocks under two layouts and compares the block results.

A result reports: placed, unplaced, gaps, labeled differences, unlabeled differences, open tokens. An unlabeled difference or an unplaced block makes the command exit 1.

## 8. Migration and use cases

### 8.1 Use case 1: the owner's manual (the one to prove)

The base template's tokens map one for one to blocks:

| Token | Block |
|---|---|
| `{PART:front}` ... `{PART:guidance optional}` | part block (slot, optional) |
| `{EXCERPTS}` | excerpts block |
| `{INCLUDE:rules}` | rule book block (book `rules`) |
| `{INCLUDE:disc optional}`, `coll`, `arch` | rule book blocks (policy books) |
| `{LAW:...}`, `{ADOPTION_HISTORY}` | law block, history block |
| text between tokens | prose block (the manual's base has none; the official rules' base has its title) |
| layout | the default Markdown layout adds nothing: no header, no contents, blocks separated by a blank line |

`definition_from_template` reads the existing base into a definition; `render_document` fills it through the same `fill_token` the old `render` calls. The proof is the existing check: the new output is identical to `render`'s for the same inputs (tested on the made-up manual in `tests/test_manual.py`'s fixture, and on the profile's real classification by `jason document-template owners-manual`, which renders both and exits 1 unless the Markdown is identical), and `jason manual --render`'s `owners-manual.diff` and `render.json` still pass. Any difference the migration needs is labeled.

### 8.2 The candidates

| # | Document | Blocks it uses | Effort | Value |
|---|---|---|---|---|
| 1 | Owner's manual | part, rule book, excerpts, quote, history, prose | low (built) | high: the user's case; the rules by reference |
| 2 | **Annual disclosures** | embedded documents, computed tables, forms, statute quotes, delivery wording | medium: needs the packet-to-definition builder, the part map with pages, and the requirements checklist | high: statutory, yearly, many parts, already the model for assembly |
| 3 | Annual policy statement | prose, rule book (policies), quotes, a directory (the designated recipient) | low after 2 | high: it is a part of 2 and a document of its own |
| 4 | Resale package (4525/4530) | embedded documents, forms, computed figures, as-of days | medium | high: a package of documents each with its own date |
| 5 | Welcome / guide for new owners | part, directory, rule book (selected subjects), form (owner information) | low | medium |
| 6 | Notice of a proposed rule change (4360) | prose, quote, rule record (the proposed and current text) | low | medium: removes a hand-built notice |
| 7 | Board meeting notice and agenda | prose, computed (dates by `NoticeRequirement`), quote | low | medium: already generated; moves to the base system |
| 8 | Letters (`DocumentTemplate` rows) | prose only | none | none: they are a one-block document; keep as they are |

## 9. Open decisions for a person

1. **Where the rule records live once the Doc is not the source.** Options: (a) keep the Doc as the original and records derived (today; no change to how the board edits); (b) records in the profile's data as the source, with the Doc generated from them (what the user describes). (b) needs permanent ids for the manual's pieces and a way to enter an adoption. Recommend: (a) now, (b) when the board chooses to edit the rules as data.
2. **Who confirms directory publication**, and how (a form answer, an email reply, a board item).
3. **Doc output:** generate the Drive Doc from a template Doc, or print the HTML to PDF only. The first keeps the letterhead and styles in Docs; the second is simpler.
4. **Whether a document's as-of day is the day of the run or the day it is dated.** A mailed packet is dated its mailing day; a manual is dated the day it was last adopted. Recommend: both recorded, the definition says which governs.
5. **Where the requirement checklists come from** for the annual packet (the models' checklists, the notice catalog, or both) and who reviews them.
6. **Whether `Packet` rows in the profile are rewritten** as definitions, or kept and converted at run time (recommended: converted).

## 10. Phases

- **Phase 1 (built):** the model (`Layout`, block kinds, `DocumentDefinition`, renderers: Markdown, HTML), the manual re-expressed with identical output, the form block, the directory block with publish flags, the embedded-document block with gaps and the part map (block order, no pages), two layouts proven independent of blocks, `jason document-template`.
- **Phase 2:** the PDF output with page numbers in the part map; the Doc output from a template Doc; the packet-to-definition builder; the requirements checklist; the rule records as a store with ids, versions, and adoption; `jason segments` checked against a part map; the profile's annual disclosures and policy statement as definitions.
- **Phase 3:** the resale package, the rule-change notice, and the welcome guide; the board edits rules as data if decision 1 says so.

## 11. The Rules document, the owner's manual template, and the Docs they make

Built after phase 1 (code: `jason.community.rules_document`, `jason.community.doc_output`, `jason.tasks.rules_documents`, `jason.tasks.document_docs`; command: `jason document-template`). It takes the model of section 4 (the rules by reference) from design to a document and puts the rules in one place.

### 11.1 The rule records

A **rule record** (`RuleRecord`) is one operating rule or one of its subdivisions: a stable `id`, the `number` it prints now, its heading (`title`, `level`), its outline address (`segment`, kept as an alias), the editorial `notes` that follow it, and its `versions` (`RuleVersion`: the words, the day the board adopted that version and the board item, or `proposed`).

- **The id is the permanent id** (`permanent_ids`) of the outline section when the document has an id table, else its address in its book. It does not change when the rule is renumbered or reworded; a piece of a section is the id with `/n`.
- **The version in force on a day** (`version_on`) is the newest adopted version on or before that day. A version with no adoption day is the words as the source document has them. A **proposed** version is in force on no day. A rule with no version in force on the document's day prints a visible line saying so and is reported as a gap.
- **Where they come from.** `derive_book` reads the classification: it groups the official rules' own pieces by the section each stands for, so the words are exactly the official rules' words (copies the board adopted as rules keep their note naming the source; a change with no adoption found keeps jason's note). A person may keep the records as data instead: `--export-records` writes them to `data/rule-records/<document>.json` (never over an existing file), and `--records stored|derived|auto` chooses. Where a stored record's words are edited, the owner's manual that reads from the Rules document shows a **labeled** difference from the working Doc.
- **A change is a proposal until the board adopts it.** Saving a record never makes a rule: an added version is `proposed` until a person records the adoption (its day and board item). jason proposes; the board adopts (Civil Code 4350, 4355, 4360; section 4.4).

### 11.2 The Rules document (`rules-and-regulations`)

The rules book only, as one document. In order:

1. **Title** (`{RULES_TITLE}`) and the association's name, from the identity tokens.
2. **The status line**, the token `{ADOPTION_STATUS}`. It is the draft banner, "DRAFT FOR BOARD ADOPTION: not an adopted rule until the board adopts it (Civil Code 4350, 4355, 4360)", until an adoption event for the whole document is on record: an `AdoptionEvent` of action `adopted`, dated on or before the document's day, whose `sections` name `rules-and-regulations`. Then it is replaced by a line giving the day and the evidence. An adoption of one rule does not adopt the document, a notice is not an adoption, and this code never decides: it reads the record, and a person records the event.
3. **The adoption history** (the same table `{ADOPTION_HISTORY}` prints), then the contents (the layout puts them after the title and the status line).
4. **The rules**, each its own block (`rule:<id>`), with the printed numbers as headings and the subdivisions under them.
5. **An appendix naming the policies bound in apart** by their book keys (`PolicyReferencesBlock`). They are separate documents, read from their own sources; nothing of them is copied here.

Rendered, it equals `jason manual --render`'s `rules-and-regulations.md` line for line, apart from labeled differences (the title block, the status line, the heading over the rules, the appendix in place of the "published as its own document" notes, the official rules' introduction, and the notes on guidance left in the manual). `jason document-template rules-and-regulations` proves it and exits 1 on any other difference.

### 11.3 The owner's manual template (`owners-manual-template`)

The guide, the directory, the governing documents' excerpts, **a reference to the Rules document where the rules go**, the policies and statutory notices bound into the manual (the discipline policy and the collection policy with the notice the law requires), the forms, and the rest of the guidance. It contains no rule and no rules book (a test asserts it).

`RulesReferenceBlock` renders the reference in one of two modes from the same records, so the words are never typed twice:

| Mode | Where | What it prints |
|---|---|---|
| `full` | the Markdown and HTML outputs | the rules, rendered from the Rules document's records, one heading level under the reference |
| `index` | the Google Doc template form | a line that links the Rules document (`RULES_DOC_URL`) and an index of the parts' and rules' numbers and titles; `--with-rules` renders the full text in the Doc instead |

The directory is a directory block with publish flags (section 5); an office the profile has but nobody has agreed to publish prints "(not published)", never "(vacant)". A form is a form block: the application is the paper form from its `FormTemplate`, and where the profile has no such form the manual's own words for it (the `arch` book) are included, so the template does not lose it. In the Doc template form the association's name and the date stay `{TOKENS}`, filled when the Doc is copied.

### 11.4 The option: the manual reads its rules from the Rules document

`jason document-template owners-manual --rules-from-document` reads the rule and copy words of the existing `owners-manual` definition from the records instead of the classification. It is off by default and nothing changes without it. With it on:

- **the check:** every rule the manual places has its record's words (`rules_section_check`), a record the manual does not place is reported, and the Markdown equals the manual read from the classification **except** at pieces whose words differ, each labeled "read from the Rules document (rule ID)";
- **the usual cause** of a labeled difference is that the Rules document holds no pending suggestion: the working Doc may carry suggested insertions that are not rules ([owners-manual.md](owners-manual.md), "The last adopted words, not the working ones": a pending suggestion is never printed).

### 11.5 The Doc output (`--doc`)

`jason document-template [rules-and-regulations|owners-manual-template] --doc plan|create`. **A dry run unless `--doc create --yes`.** The plan prints, for each Doc: the action, the name, the folder, the requests, the styles, the tables, the page breaks, the header and footer, the `{TOKENS}` left open, and the link between the two Docs.

`doc_output.build` writes the definition as one list of Docs `batchUpdate` requests with the Doc's **real named styles**: the document title is `TITLE`, the line under it `SUBTITLE`, a part or a section `HEADING_1`, a numbered rule `HEADING_2`, its subdivision `HEADING_3` (the Markdown levels moved up one), everything else `NORMAL_TEXT`. The Doc's outline is therefore the document's own: the heading a block prints is the heading the Doc has. A reader of published Docs, and the structure recovery that reads them, can take that heading structure as known.

- **Tables** (the adoption history, the directory): a marker paragraph is written, then replaced by `insertTable` and the cells filled last to first, the head row bold and pinned.
- **A named range per block**, named by the block's stable id, so a rule is found in the Doc by the id its record has.
- **The status line** is a ruled box; a page starts before each heading level the layout names.
- **The link to the Rules document** is a hyperlink on the words that name it, to `https://docs.google.com/document/d/<id>/edit`. The Rules Doc is created first so its id is known when the manual template is written. (A smart chip is not made: the API has no request for one.)
- **The contents.** The Docs API has no request that inserts a table-of-contents field. The Doc has a marker where the contents go; once the headings have ids a second pass writes the contents as links to the headings (`contents_requests`), and Insert > Table of contents in the Doc editor makes the field from the same headings.
- **The letterhead** is the existing path: the Letterhead Doc is copied, its sample text and banner removed (`letters.banner_requests`), the header set (`letters.format_requests`), and the layout's footer text appended to its footer.
- **Verification.** After writing, the Doc is read back and each planned paragraph and heading style is checked; a difference is printed and recorded, never hidden.

**States** are `template_gen`'s, kept in `data/templates/<profile>.json` under `document:<key>` (the Doc id, a hash of the rendered text, a hash of the Doc's text): no Doc yet, **create**; the document changed and the Doc did not, **update** in place; a person edited the Doc and the document did not, **edited**, left alone; both changed, **conflict**, nothing written; neither, **unchanged**. A Doc the profile names that jason did not generate is not overwritten. Nothing is shared, sent, or deleted.

The Docs are the profile's rows (`Community.manual_documents()`, `ManualDocument`): the definition's key, the name its Drive file bears, and the folder (empty: the Templates folder of `drive_home`). A definition with no row takes its own title. The first `--yes` follows a person's confirming the names, the folder, and who adopts the Rules document.

### 11.6 Not built, and what is untested

- The Doc requests are tested against a simulator of the text requests and a fake Docs service, never a live Doc. The table and list index arithmetic follows the Docs structure as documented; the post-write verification and a first run on a scratch Doc are the check.
- The records as the store (section 4.3): the stored file is the first step; the classifier does not yet write adoption days per rule, and `supersedes` is the order of the versions.
- The Rules document's proposal path (`jason rule-change` text from a proposed record) is not wired.
