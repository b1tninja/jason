# The annual disclosure packet: a document made of documents

Status: **design** (October 2026). Nothing in this page is built except what section 1 lists. The idea is the board manager's: the annual disclosures are *a collection of other documents embedded in a template*. [document-templates.md](document-templates.md) gives that idea its model (section 6 there names this use case); this page works it through: the definition, the checklist of what the law asks of it, the clock and the delivery, the run that makes one packet each year, the checks on the result, and the console. The screen is [console/handoff-annual-disclosures.md](console/handoff-annual-disclosures.md).

The packet is a **draft for a person to read and send**. jason assembles it, checks what it can, and says what is missing. It does not mail, does not adopt a budget or a policy, and does not say the packet complies. Where the law and the governing documents leave a choice open, the choice is the board's and is shown as one ("Where the law is silent, write it down", [AGENTS.md](../AGENTS.md)).

## 1. What exists

| Piece | Where | What it does today | Used here as |
|---|---|---|---|
| The packet | `jason.community.packets` (`Packet`, `Part`, `PartSource`, `SourceKind`), `jason.tasks.packets`, `jason packet`, [packets.md](packets.md) | An ordered list of parts, each found fresh for the year (a template Doc, the library, Drive, a generator, an addendum); page choice (`pages`, `keep`, `drop`); `own_sheet`; per-building `variants`; four value layers; a merged PDF with a bookmark per part and "Page n of N" on every page; `manifest.json` with each part's source, first page, page count, and SHA-256; a draft build that names each missing part on a page | The splice and the manifest: kept as they are |
| The document-template model | `jason.community.document_templates` (phase 1 built), [document-templates.md](document-templates.md) | A definition of a layout and blocks; an embedded-document block (a nested definition, or a stored file attached as it is) that prints a visible gap line when its part is missing or older than the block's as-of day; `check`, `Requirement`, `part_map` (order and sources, no pages yet) | The definition: the packet becomes one, built from its `Packet` at run time |
| What the law requires of a notice | `jason.community.notices` (`NoticeRequirement`, `Timing`, `Method`, `Recipients`, `Evidence`), `jason.community.notice_catalog.REQUIREMENTS`, `jason notices --catalog` | Each notice's recipients, methods, clock, content, and proof; rows flagged `annual`; `carried_by` links a row to the document that carries it; `applies` is a three-valued condition | The requirements checklist, and the clock |
| The finer checklists | `jason.community.models.financial_annual`: `BUDGET_REPORT_ITEMS`, `POLICY_STATEMENT_ITEMS`, `AnnualReportModel`, `packet_reserve_plan` | The items of the annual budget report and of the policy statement, each with the pattern that finds it in a packet's text; a lens that checks the budget's reserve transfer against the study | The checklist's finer rows, and an independent reading of the output |
| The delivery rules | `jason.community.notices.NoticeRule`, `jason delivery`, `jason notices`, `jason mailroom`, [notices.md](notices.md) | Who receives an individual notice how, from the owners' tags; the ledger of attempts; the proof of notice; the Mailroom's plan and cost | The send plan and the proof |
| The owner information cycle | [owner-information.md](owner-information.md), `jason owner-info`, `OWNER_INFO_CYCLE` in the profile | The yearly request for each owner's delivery choice and occupancy, and the day the answers are entered | The first piece of the annual set, with its own clock |
| Structure of a generated PDF | [structure-recovery.md](structure-recovery.md), [document-segmentation.md](document-segmentation.md), [pdf-preflight.md](pdf-preflight.md), `jason segments`, `jason preflight` | How much of a document's structure a PDF carries; the documents inside a file and their page ranges; a scan's blank pages, orientation, and risks | The checks on the built PDF |
| The review | `jason review annual-disclosures` | The manager's check of the assembled text against the law on hand | The last check, unchanged |

**What is missing**, and what this design adds:
- a **definition** for the packet (it is a splice plan today, with no layout, no as-of day per part, no value layers per nested part);
- a **requirement map**: which part answers which element of the law, checked against the catalog and the models rather than typed in prose;
- a **run**: values collected, a day frozen, every part hashed, the output archived with its proof;
- a **contents page**, nested bookmarks, and a part map with pages;
- a **send plan** a person carries out, with the clock computed from the catalog's rows.

## 2. The annual set

"The annual disclosures" are not one notice. The catalog has rows flagged `annual`; the set and how each rides, from `jason notices --catalog`:

| Deliverable | Catalog key | Recipients, method | Clock | Rides in |
|---|---|---|---|---|
| The request for each owner's delivery choice and occupancy (CIV 4041) | `owner-info-solicitation` | every member, written | the answers entered at least a stated number of days before the reports go out (a clock on entering, not on sending: `delivery=False`) | its own mailing; its paper form is also bound at the end of the packet as next year's request |
| The annual budget report (CIV 5300, with 5320 and 5570) | `annual-budget-report` | every member, individual delivery, secondary copies | a window before the fiscal year ends | the packet |
| The annual policy statement (CIV 5310, with 5320) | `annual-policy-statement` | every member, individual delivery, secondary copies | the same window | the packet |
| What the policy statement carries: the assessment and foreclosure notice (5730), the schedule of penalties (5850), the dispute resolution summary (5965), the architectural approval notice (4765) | `collection-policy-notice`, `penalty-schedule`, `dispute-resolution-summary`, `architectural-requirements` | as the statement | `carried_by: annual-policy-statement` | the policy statement, or a policy bound behind it |
| The reviewed financial statement (CIV 5305), when it applies | `financial-review` | every member, individual delivery, secondary copies | a stated number of days after the fiscal year closes | **its own delivery**, a second definition with one attached file |
| The notice of the right to the corporation's annual report (CORP 8321) | `annual-report-8321` | every member, written | yearly | **not settled**: the catalog names the notice and no method that fixes where it rides; whether it is a part of the packet is a question for the board (section 9) |

The numbers of days are the catalog rows' (`Timing`); no definition and no page of prose types them. The packet is the **budget report and policy statement** together, as [packets.md](packets.md) has it, with the owner-information form bound at its end. The 4041 request is its own earlier mailing. The 5305 statement follows the year's close and is its own run. The same machinery serves all three; section 5 gives each its clock.

## 3. The packet as a definition

A document definition has a **layout** (how it looks) and **blocks** (what it says), and the annual packet is one whose body is mostly embedded documents ([document-templates.md](document-templates.md), sections 2 and 6).

### 3.1 The outer template

The outer template is the part of the packet that is written once for any association and rendered with the profile's identity:

| It holds | Notes |
|---|---|
| **The cover**: the association's name and letterhead, the title, the fiscal year, the **dated day** (the day the packet is dated for delivery), the designated recipient, how to reach the association | Identity and the recipient come from the value layers; the dated day comes from the run |
| **The member-facing summary**: one page that says what the packet contains, in order, and where each part begins, and how a member gets the full report free where the packet carries a summary of it | Written from the part map, never typed; the statute's own words in it are `{QUOTE:...}` passages with their citations, and nothing in it paraphrases the law |
| **The order and the statutory headings**: a heading for each statutory part, in the order the definition lists | The heading is the part's `heading`, a named style in the Doc form so the outline is the document's own |
| **The delivery wording**: the notice on how the packet is delivered (by the member's election, or first-class mail), and the line that tells a member where general notices are posted | The delivery method words are recited from the catalog row's methods; the posting location is a profile value |
| **The contents page**: part titles with their pages | Made from the part map after the pages are known; section 6.1 |
| **The layout's tokens**: type sizes the statute names (a minimum point size for one notice, a minimum for the insurance and agency statements, and a separate sheet for two of them), the header and footer, the page breaks | A statutory size is a layout token with a lower bound (`MIN_POINTS` in `tasks/packets.py` is the first such table); a part's block carries which token it takes, never a size |

The outer template holds no budget, no policy, no insurance fact, no rule. Those are parts.

### 3.2 A part

A part is an embedded document by reference. Its record, in addition to what `Part` has today (`title`, `source`, `authority`, `required`, `own_sheet`, `note`, and the source's `pages`, `keep`, `drop`):

| Field | Meaning |
|---|---|
| `id` | Stable, unique in the packet, and the same however the order changes. A nested part's id is its path (`budget-report/insurance-summary`). The part map, the checklist, a check, and a later reading name the part by it |
| `kind` | `definition` (a nested generated document: the budget report, the policy statement, the insurance summary), `stored` (a file attached as it is), `form` (a `FormTemplate` rendered as paper), `passage` (a statute's words), `computed` (a table of figures) |
| `source` | Where the words are read from: the base template (`src/jason/templates/packets/`), the library or Drive address, the generator, the statute's stored text |
| `as_of_rule` | What makes this part current. Section 3.4 |
| `standing` | What the source says it is: **adopted** (a rule, a policy, a budget, with the day of the adoption event and where), **draft**, **recorded** (a recorded instrument), **issued** (an insurer's or a preparer's document, with its period), **computed** (jason's own table from stored records, with the inputs it read), **statute** (a passage from the law on disk). A source that cannot say is **unknown**, shown as such |
| `freshness` | **current** or **stale**, derived from `as_of_rule`. Never entered |
| `answers` | The checklist elements this part answers (section 4): catalog requirement keys, with a content line, or the model's item citations. Declared once, in the base template's front matter or in the profile's part row |
| `basis` | **statute** (the law requires it), **governing document** (the declaration or bylaws ask it), **board's choice** (the board includes it), **convenience** (a map, a form for owners). A part that answers no element is labeled by its basis, never hidden |
| `variants` | The per-building (or other) variants it differs by, as `Packet.variants` does today |
| `address`, `sha256`, `pageCount` | For a stored part: its stable address, its digest, its pages (section 3.5) |

### 3.3 Value layers

Every block that carries a `{TOKEN}` resolves it through the layers of `jason.community.template_values`, later layers winning and an empty value never overriding a filled one:

1. **The profile's standing values**: identity, the designated recipient, the posting location, the website; and the packet's standing values (`Packet.values`). A standing value is as true as the last time a person confirmed it (section 5.2).
2. **Computed values**: the fiscal year, the unit count, the dated day, the window's first and last day, each building's flood-policy values: each is a function of stored records and says which.
3. **Statute passages**: the words of a provision, read from the law on disk (`jason.community.statute_passages`, `jason export-authorities`), with the citation and the digest read. When the law changes, the next run prints the new words and the checklist marks the part's old words stale.
4. **Per-run values**: what only a person can say for this year (the board's statements on deferred repairs, special assessments, and funding; the assessment; the mailing day), entered in the run with who and when, and frozen with it.

A token left empty after all four is a **decision still open**. The checklist lists each one by name against the element it belongs to, and the output prints it as a visible marker in a draft. A final build refuses.

### 3.4 As-of rules

Each part is current under a rule that names the day it is read as of. There are three days in a run, and they are kept apart:

| Day | What it is | Who sets it |
|---|---|---|
| The **as-of day** (`frozen`) | The day the run reads the law, the policies, and the stores as of. The version in force that day is the version printed | The run, at the freeze (section 5.3) |
| The **dated day** | The day printed on the cover, the day the packet is to go out; it must fall in the window the catalog row gives | A person, inside the window |
| The **sent day** | The day the ledger shows it went out | The delivery ledger, never typed |

A freeze after the dated day, or a dated day outside the window, is a finding. The rules:

| Rule | Current when | Example kinds |
|---|---|---|
| `fiscal-year` | the source is the year's own (its stated fiscal year equals the run's) | the budget, the reserve summary's figures, the disclosure summary |
| `term-in-force` | the source's term covers the first day of the fiscal year; a term not on file is a gap, never last year's figures | each insurance summary line, a policy's declarations, a flood policy's |
| `in-force-on` | the version of the rule or policy in force on the as-of day is the version in the packet | the collection policy, the fine schedule, the operating rules a part cites |
| `statute-digest` | the passage's digest equals the digest of the words on disk | a statute's notice or form carried word for word |
| `confirmed-this-run` | a person confirmed the standing value for this run | a standing value such as a statement that holds true until it does not |
| `fixed` | none; the source is as stored | a parcel map, a form that does not change |

### 3.5 Stored files: attached pages, never re-rendered

A stored part is a PDF or a Doc exported as it stands. The definition records its **stable address** (a library path with its id, a Drive id), its **SHA-256**, its **page count**, and the pages chosen. The pages in the packet are the file's own pages: not re-drawn, not recompressed except by the merge's own save, not corrected. A person decides what is left out (`pages`, `keep`, `drop`; a rule that matches no page keeps every page and says so). The output of the Markdown and HTML renderers is an **attachment line** (title, address, pages, as-of); the PDF output splices the pages.

A stored file is read, never written, in three ways: its text may be read to check what it holds (section 6); its pages may be previewed; its preflight (blank pages, orientation, a scan with no text layer) is reported. Nothing is rotated, deskewed, or removed in the packet; a person decides, and the decision is a page choice recorded on the part.

### 3.6 Nested generated parts

The budget report and the policy statement are themselves definitions: a base template with its own tokens and its own embedded parts (the insurance summary is a generated table; each building's flood notice is a letter with that building's values). A nested part renders in place with its headings one level down, its gaps lifted to the outer packet, its own as-of day if it has one, and its part-map entries as children. The part map is a **tree**; the PDF's bookmarks follow it (section 6.1).

### 3.7 Statutory and the association's own

The definition marks each part's basis. The checklist reports, apart, **the parts no element names**, labeled by basis: the board's choice or a convenience. A part kept for the board's own reasons is not a gap and not a requirement; it is a labeled inclusion the board can drop.

## 4. The requirements checklist

### 4.1 Where the rows come from

The checklist is **read, not typed**. Its rows come from three places, and the build keeps the join between them in one small table a person reviews:

1. **The catalog.** Every `NoticeRequirement` with `annual=True`, and the rows `carried_by` it: its `statute`, its `content` lines (the elements), its `applies` condition, its `timing`.
2. **The models' item tables.** `BUDGET_REPORT_ITEMS` (the items of the annual budget report) and `POLICY_STATEMENT_ITEMS` (the items of the policy statement), each citing its subdivision. They are finer than the catalog's content lines: one catalog line holds several items (a reserve summary and a reserve funding plan summary are two items under one line). The join records, for each item, the catalog key and the content line it falls under; the unit of the checklist is the finest the sources give, and the catalog line is its group.
3. **The profile's conditions.** An element the association answers by a fact (an `applies` condition over the profile's standing facts and the answered questions) takes its answer from `notice_catalog.required`; a person's recorded answer, not jason's inference, makes an element not apply.

Two differences between the sources are findings the first run reports, and a person resolves, never the code:
- the policy statement's item table holds eleven entries while the module's own docstring says items (1) through (12), and the catalog's content list names an item the table has no key for (an electronic voting procedure, *if used*);
- the budget report's catalog lines (eight) are coarser than the model's thirteen items ((b)(1) through (b)(12) and (e)).

### 4.2 A row

```
requirement: annual-budget-report   (catalog group)
element:     CIV 9901(b)(2)         (the model's item; the finest unit)
citation:    the statute's section, and its words by {QUOTE:...} when shown
applies:     applies | does not apply | undetermined      (jason's reading of the row's condition)
parts:       the parts that declare they answer it
read:        what the output's own text shows, by the model's pattern (section 4.4)
state:       one of the five words
why:         one line, with the part's as-of and standing
gap:         the sentence that prints in the output when the state is missing or waiting
question:    where the answer is asked, when a person must settle it
```

### 4.3 The five states

| State | Means | What settles it |
|---|---|---|
| **present** | A part answers the element, its source is on file, it is current under its as-of rule, it has the standing the element needs (an adopted policy for a policy element), and no token in it is open | nothing |
| **present but stale** | A part answers it and its source is on file, but it fails its as-of rule: the term in force on the first day of the fiscal year is not the term on file, the policy's version in force today is not the version in the part, the statute's words on disk changed since the part's passage was cut, or a standing value was not confirmed this run | the part is refreshed: a newer file is confirmed, the passage is re-cut, the value is reconfirmed |
| **missing** | No part declares it, or the part's source is not on file for this year. "Not on file is not not done": the row says what was searched | a person supplies the source, or declares which part answers it |
| **does not apply** | The row's condition is answered **does not apply** by a recorded fact, with who and when. The row stays on the list, with the fact it turns on, and is never hidden | the fact changes |
| **waiting** | A value or a decision only a person can give has not arrived (the board's statements, the adopted budget, a figure the treasurer owes, the mailing day), or the part waits on an event not yet happened (the adoption of the budget, the renewal of a policy). The row names who and what | the person gives it; section 5.2 |

An **undetermined** `applies` answer is not a state of the row: it is a question in the intake queue ([console/handoff-applicability-questions.md](console/handoff-applicability-questions.md)), and the row reads **waiting** on that answer until it is given. A requirement is **never** "compliant" in jason's words, and a clean checklist says only: *each element has a part, current, or a visible gap*.

### 4.4 Declared and read

Two independent evidences sit on each row:
- **Declared**: the definition says the part answers the element (the base template's front matter, or the profile's part row).
- **Read**: the built output's own text is read by `AnnualReportModel` (its patterns find which items the text carries), and the reading is compared with the declaration.

Agreement is **present**. A part declared but not found in the output's text (an element the part's words do not carry), or an item found that no part declares (an element covered by a part nobody mapped), is a **finding** with both shown side by side, never resolved by the code. A part with no text layer (a scan) is **declared, not read**; the row says so, and a person reads the page. The model's patterns are jason's readings of how an item is worded, so a pattern that finds nothing in a differently worded part is a miss on the pattern: it is reported as "not found by the reader", not as an absent element.

### 4.5 Cross-part checks

Some things the law asks are relations between parts, not presence. They are checks beside the rows, each a finding with the two values side by side and the source of each:
- the assessment in the budget equals the assessment in the disclosure summary;
- the reserve transfer in the budget against the reserve study's plan for the year (`packet_reserve_plan`);
- the insurance summary's lines against the declarations enclosed, and each building's flood notice against its policy;
- the unit count in the packet against the recipients the delivery plan resolves;
- a statement carried word for word against the statute's words on disk (the digest);
- a statutory type size or a separate sheet against the layout token that sets it.

### 4.6 The gap line in the output

A missing or waiting element is **visible in the document**, in the place its part would be, in the contents, and in the part map (`gap: true`). Its wording is the manager review's, from one function, so one report speaks one way:

> *[Missing: Example item. Required by CIV 9901(b)(2): not on file for fiscal year 2099. Searched: library path "Example Folder/2099/…", index read 2099-03-02.]*

> *[Waiting: Example statement. Required by CIV 9901(b)(4): the board's statement for fiscal year 2099 has not been entered. Asked of the board's secretary on 2099-03-01.]*

A **draft** build prints each gap on its own page and says "DRAFT" with the count of gaps in the footer. A **final** build refuses while any required element is missing, waiting, or stale, or any token is open; the refusal lists them. "Final" means only that the checks passed: it is not a finding that the packet satisfies the law.

### 4.7 The gaps as questions

A gap is a question for someone, and where it goes depends on what settles it:

| What settles it | Goes to |
|---|---|
| A fact (does the association have outstanding loans; does it use electronic voting) | the intake queue, `#/applies` ([handoff-applicability-questions.md](console/handoff-applicability-questions.md)), as a signed answer |
| A value or a file a person has: the adopted budget, the reserve study's pages, a figure | the run's **collection list** (section 5.2), assigned to a role by the schedule's assignments, due on the day computed from the clock |
| Which of two files, or which pages, or whether this file is this year's | the **confirmations queue** as a *packet part to confirm* (a person confirms jason's proposed source and pages; it adopts nothing) |
| What the words mean (whether a notice rides in the packet, whether an item is required) | the confirmations queue as a candidate reading; two readings remain goes to the board, and the board asks counsel |
| A board decision (adopt the budget; adopt a policy; make a statement) | a board item for the agenda; the vote is the board's, recorded on the Decisions tab, never an approve control |

The confirmations queue already holds three kinds of item; adding a fourth, the *packet part to confirm*, is a decision (section 9, decision 1), and until it is made the queue is unchanged and the console shows these on the packet's own page.

## 5. The clock, the delivery, and the run

### 5.1 The clock

Every date in the packet's schedule is computed from catalog rows, never typed:

- **The window.** `Timing.window(anchor_day)` for the budget report and the policy statement, with the anchor the fiscal year's end (`Anchor.FISCAL_YEAR_END`, from the schedule's fiscal year), returns the first and last day the notice may go out ("deposited in the mail, or transmitted, or posted"). How a court counts a period ending on a weekend or holiday is for counsel.
- **The owner-information answers.** The 4041 row's clock is anchored on the day the annual reports go out (`Anchor.ANNUAL_REPORTS`) and governs the **entering of the answers** (`delivery=False`). The date the answers must be entered is therefore the dated day less the row's days; the request's own sending day must leave time to answer and for a correction. The loader computes it from the dated day, and shows the whole chain as one strip.
- **The financial statement.** The 5305 row is anchored on the year's close and runs after it.
- **Stricter clocks.** A governing document that asks more than the statute narrows a clock (`combined`); a document that asks less does not (the statute governs, CIV 4205). The loader shows the statute's window, and beside it the stricter window with the clause that makes it, labeled.
- **A date not on record** (the fiscal year end not set, the dated day not chosen) is a state of its own: a question, never a guess.

A sample (made-up; the days are those of the catalog rows):

```
fiscal year end  2099-06-30
window           2099-04-01 through 2099-05-31      annual-budget-report, annual-policy-statement
dated day        2099-05-15                         a person chose it
answers entered  by 2099-04-15                      owner-info-solicitation (dated day less the row's days)
```

### 5.2 Who sends what; individual and general delivery

The packet is an **individual** notice: each owner receives it by the delivery method that owner elected (CIV 4041), or first-class mail to the address on the books where there is no valid election (4040), and a copy goes to each secondary address on file (4040(b); `secondary_copies`). A **general** notice (4045) is not how the packet goes; but the policy statement is where the association designates the place for posting general notices and the option to receive them individually, and the catalog's note says the posting a later general notice relies on depends on that designation. So the packet's delivery has an effect on later notices, and the checklist shows the designation as an element with a link to the general notices it makes valid.

`tasks.notice_delivery` resolves the rule to the exact recipients from the owners' tags, and the send plan groups them: email, mail, and both, the secondary copies, each building's variant. A reach narrower than "every member" (an owner who asked for the full report, a building's flood notice) is shown as such.

| Act | Who | Notes |
|---|---|---|
| Assemble: start the run, collect, generate drafts, read the checks | the manager, or whoever the schedule's assignment names | `schedule_assignments` are proposed until the board adopts them; the page labels a proposed assignment so |
| Give a figure or a file | the officer or person who holds it (the treasurer for the figures; the manager for insurance) | each a signed record in the run's collection list, with the source |
| Adopt the budget, the policies, a statement the board must make | the board, by vote at a meeting; the president or the secretary records it | The packet reads the adoption from the minutes and the decision record; it never records one |
| Read the packet and say it was read | a named person (section 6.5) | a record of reading, not an approval |
| Send | a person, who runs the send command with `--yes` from the terminal | jason never mails (AGENTS.md, Boundaries); the engine's tier for the send kind applies |
| Record the delivery proof | the manager, from the ledger and the mailing declaration | section 5.5 |

### 5.3 The send plan

The run ends in **files and a plan a person carries out**:

- one PDF per variant, with its SHA-256 and page count;
- the **send plan**: for each variant and each channel, the recipients resolved by the delivery rules (counts, and the ids the sending tool takes; no names or addresses in the plan), what each copy carries, the Mailroom's billed pages per letter and the estimate from `payhoa.pricing` (never typed), and the window's last day;
- the order: **email first, mail after**, with the owner-information cycle's lesson as the reason (a letter cannot be recalled after minutes; an email can be corrected);
- the commands, as text to copy: the mailroom's dry run, the batches, the sync that reads the ledger afterward. None runs from the page.

A packet of many pages is not a Mailroom letter of four pages; where the packet exceeds what a letter carries, the plan says what the cost per owner is and names the board's choice (the summary route of CIV 5320, the full packet to each owner, or a link with a printed notice where the method allows it). That is the board's decision, not the plan's.

### 5.4 The run

A **run** is one year's packet, from the first plan to the proof. It has stages, each with its state, and each a record on disk (`data/packets/<packet>-<year>/`):

| Stage | What happens | Record |
|---|---|---|
| **Plan** | The definition is built from the packet; the checklist is read; each element shows its state; the collection list is made from the rows that are waiting | `plan.json` |
| **Collect** | Values and files arrive, each signed and sourced; a standing value is asked "still true this year?" | `values.json`, `collect.json` |
| **Draft** | A draft PDF, with gap pages | `draft/` |
| **Freeze** | The as-of day is fixed; the part map, the values, and every part's source and hash are written; the definition, the base templates' versions, the statute passages' digests, the layout | `run.json` |
| **Generate** | The final PDF per variant, with contents, bookmarks, and the part map with pages | `building-<n>.pdf`, `part-map.json`, `manifest.json` |
| **Check** | The checklist, the cross-part checks, the segment check, the preflight of attached scans, the review | `checks.json` |
| **Read** | The read-through list (section 6.5) and the person's record | `read-through.json` |
| **Send plan** | The plan above | `send-plan.json` |
| **Sent** (a person's act, from outside) | The Mailroom's log and the batches' ids are read into the run | `sent.json` |
| **Archive and prove** | The sent packet, its map and hashes, the plan, and the ledger's proof are kept together; the packet is filed as an association record | the notice's folder, `jason://notice/KEY/proof` |

### 5.5 What is collected, what is frozen, what is archived

**Collected** (the campaign): what the manager gathers is a **collection item** for each waiting element:

```
id, what it is, which elements it answers, from whom (a role, as the schedule assigns it),
asked on, due by (the latest day it can arrive and still leave the days the next stage needs),
state (asked, received, confirmed, waived by a person), the value or the file and its address,
who entered it, when, and from what source
```

What a typical year's list holds (as kinds, not facts): the adopted budget and the day it was adopted; the reserve study's summary pages and the figures of the disclosure form; the insurance terms in force on the first day of the year, from the policy records; the board's statements; the mailing day; the confirmation of each standing value. A value entered for a board-only statement is labeled "entered by NAME; the board's statement as adopted at its meeting of DAY" where there is an adoption, and "entered by NAME, not yet adopted" where there is not. jason never writes a board's statement; it prints the words a person entered and marks where they came from.

**Frozen at generation**: `run.json` holds:
- the as-of day, the dated day, the fiscal year, the run's key and revision;
- the final merged values, each with its layer;
- for each part: its id, its source address, the SHA-256 of what was read (for a nested definition, of its rendered text), the base template's version and hash, the statute passage's digest, the pages chosen, the pages in the output;
- the part map: the tree of parts with their first and last pages in each variant;
- the checklist as it stood: every row, its state, its parts;
- the tool's version, so the output can be explained later.

A frozen run is not edited. A change is a new revision (`-r2`), with the reason, and the first revision stays. The merged PDF's SHA-256 is the packet's identity.

**Archived**: the sent packet is an **association record**. The profile pins it on the library folder or the known file that holds it, which of the CIV 5200 record kinds it counts as is the pin's decision, and `jason` files it with the run's hashes. **The delivery proof** is the notice's own: the text as sent (the PDF and its map), the recipient list as of the record date with each method and why, each attempt's outcome, each follow-up owed and done, the mailing declaration, and the date of the anchor: `NoticeRequirement.proof()` lists them for each of the two rows (`annual-budget-report-2099` and `annual-policy-statement-2099`), one packet and the same text for both, so the batches are named by those keys and the ledger finds them by prefix.

## 6. Quality checks

### 6.1 The PDF's structure

[structure-recovery.md](structure-recovery.md) finds that bookmarks and a contents page are the cheapest gains in what a PDF carries of its structure. `merge` writes a flat bookmark per part today. The generated packet gets:
- a **contents page** of part titles and page numbers, from the part map;
- **nested bookmarks** from the part tree (a part under the report it belongs to);
- **headings in the template Docs as real named styles** (as the Docs output does), so the outline is the Doc's own;
- the **part map with pages** beside the PDF.

Two expectations to test, not assume, because they bear on the segment check below: a packet-wide "Page n of N" on every page may read as continuous numbering to the segmenter and suppress its breaks; and a contents page that lists the parts is the shape the segmenter reads as a parent cover (a short document that lists three or more of the documents that follow).

### 6.2 The part map

`part_map` is written beside every generated PDF. For the annual packet it gains `pages` (first and last, in each variant), `address`, `sha256`, `standing`, `freshness`, `basis`, `answers`, and `gap`, as a tree.

### 6.3 The segment check

`jason segments --file packet.pdf` reads the PDF as an unknown file. The check compares what it finds with the part map:

| Result | Reading |
|---|---|
| **agree**: a segment starts at a part's first page | nothing to say |
| **inside**: the segmenter finds documents inside an attached file (an exhibit, a declarations page within a longer insurer's file) | expected; reported as nested, not a finding |
| **missed**: no break at a part's first page | expected for a part with no cue; reported with the cues the page has |
| **contradiction**: the segmenter reads continuation across a part boundary the map is sure of, or a break inside a part generated page by page | a finding about the segmenter, the footer, or the splice, never a guess about the packet; the part map is the known structure |

The segmenter's measured recall is below one (dev 0.84, held-out 0.78, [document-segmentation.md](document-segmentation.md)), so a miss is not a defect; only a contradiction is shown first. The check is read-only and holds the GPU lock only if a model reader is asked for; the default is the rules.

### 6.4 Preflight of attached scans

`jason preflight` on each stored part before it is spliced: blank pages (a person decides which stay; a blank back on an `own_sheet` part is the splice's own), orientation (a page the reader finds sideways is reported, and a person decides on a page choice), resolution, symbol-coded images (a digit may have been swapped for a look-alike: digits on a budget scan are checked against the paper), and the text-layer's quality. A part with no text layer is declared, not read (section 4.4). The merge's footer is drawn on every page; a page with ink in the footer band is reported so the footer does not land on an attached page's own words.

### 6.5 The read-through list

A person reads the packet before it goes. jason makes the list, in the order the reader needs it:
1. **Every gap** and every stale part, with why.
2. **The board's statements**, each as entered, who entered it, and whether an adoption is on record.
3. **Each standing value**, with when it was last confirmed.
4. **The cross-part checks**, each with its two values.
5. **The findings** of the segment check, the preflight, and the review.
6. **Each statutory part** by page, in the order of the contents, with the element it answers.
7. **The clock**: the window, the dated day, the last day, the owner-information date.

The reader records **read by NAME on DAY**, with the revision read. That record is evidence that a person read this revision; it is not the board's approval of anything and it adopts nothing. A change after it makes it stale.

`jason review annual-disclosures` runs on the final text as the last check; its findings are shown with the others.

## 7. The console

A band of the Annual disclosures screen (`#/disclosures`), because that is where the disclosures members receive already sit, with the checklist as its first view; the notice's own record stays on the Notices screen and the packet links to it. The design is [console/handoff-annual-disclosures.md](console/handoff-annual-disclosures.md).

## 8. Where the code goes

Nothing here names an association. Facts are the profile's (`Community.packets()`, standing values, its assignments); the requirement map is general.

| New | Where | Does |
|---|---|---|
| `AnnualRequirement`, `ElementState`, `checklist`, `gap_line` | `jason.community.annual_packet` (pure) | Reads the catalog and the models into rows, joins them, computes the five states from parts and their as-of rules, writes the gap sentences |
| `Definition from a Packet` | `jason.community.document_templates` (phase 2 of that design) | The packet becomes a `DocumentDefinition` at run time, so existing profile rows render through the new model unchanged |
| The run store, collection list, freeze, send plan | `jason.tasks.annual_packet` (disk, under the store lock) | Reads and writes `data/packets/<packet>-<year>/` |
| Flags on `jason packet` | `jason.commands.packet` | `--check`, `--collect`, `--freeze`, `--qa`, `--send-plan`, `--archive` (the flag names are free at `src/jason/commands/packet.py` today); the build stays `--build` |
| Part map with pages, contents page, nested bookmarks | `jason.tasks.packets.merge` | The merge already returns each part's first page and count; the tree and contents are new |

## 9. Open decisions for a person

1. **Where a packet's questions go** (section 4.7). The confirmations queue has three kinds; a fourth, the packet part to confirm, is the design's working assumption. The alternative is a list on the packet's own page only.
2. **Does CORP 8321's yearly notice ride in the packet.** The catalog names the notice and no method that fixes it. A reading, then the board.
3. **The summary route or the full report to each member** (CIV 5320). The packet's size, the cost, and the variant a member who asked for full reports gets turn on it.
4. **Which of the three days governs** when the run's as-of day, the dated day, and the sent day differ. The design records all three and says the freeze day governs the content, the dated day the clock, and the sent day the proof; the board may choose otherwise.
5. **The reconciliation of the checklist's sources** (section 4.1): the join table, the policy statement's missing item, the budget's finer items. A person reviews it once.
6. **What counts as an element that does not apply.** The catalog has conditions on notices, not on elements. A person's recorded answer is the only way an element does not apply until the code encodes conditions per element.
7. **Whether the packet is one run or two.** The 4041 request goes out earlier and its form is bound again at the end; the design keeps one packet and one earlier mailing, each its own notice and proof.
8. **The board's own record of distributing.** Whether the minutes record the distribution of the packet, and where.

## 10. Phases

Smallest first; each is a reviewable change that stops.

1. **The checklist and the gap view (read-only).** `annual_packet.checklist` over the existing `Packet`, the catalog, and the model tables; the five states; the declared/read comparison on a built PDF's text; `jason packet annual-disclosures --check`; the screen's first view. No change to generation.
2. **Generation.** The definition built from a `Packet`; the part map with pages; contents and nested bookmarks; the freeze and `run.json`; draft and final with the gap pages and the refusal.
3. **Collection.** The collection list, the standing values' reconfirmation, the confirmed part sources, the writes.
4. **Quality.** The segment check, the preflight of attached scans, the footer-band check, the read-through list and its record.
5. **Delivery.** The clock strip, the send plan, the sent record read from the Mailroom's log and the batches, the archive, and the link to the notice's proof.

## 11. What this does not do

- It never mails, schedules a mailing, or posts a notice.
- It never adopts a budget, a policy, or a statement, and never records a vote.
- It never says the packet complies; it says each element has a part or a visible gap.
- It never writes the law's words from memory: a statute's words come from `jason cite` and the stored text, a governing document's from the stored file.
- It never edits an attached file or an owner's record.
