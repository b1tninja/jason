# Ingestion and review

**Status:** proposed design, October 4, 2026. Nothing here is built except the inventory in step 1, which is in progress. It follows [applicability.md](applicability.md) (the search index, the "applies to" conditions) and the survey in "What jason does today" below.

## The idea

Read a document once. Review it as many times as needed, each time under a different context.

- **Ingestion** turns a file into what it says: its text, its passages, its kind, and the facts on its face (parties, dates, amounts, terms). It needs nothing but the file. The same bytes give the same result on any day, for any association.
- **Review** judges what a document says against something outside it: the law, the governing documents, the association's facts, another record, a date, or the matter it belongs to. A review is one **lens** applied to one document, or to a **collection** of them.

Kept apart, three things become possible:
- **The same document under different lenses.** A contract is read once. It is then reviewed for its duties and deadlines, for the notices a statute requires, and for what it means in a dispute.
- **Lenses that outlive one scenario.** A way of interpreting documents ("who owes what to whom, by when") is written once and applied to a vendor's file, a legal case, or a meeting packet.
- **Review again without reading again.** When the law, the profile, or the lens changes, only the review reruns. A stored reading stops changing because today's date changed.

## Three questions, as the law separates them

The split above is two layers. The law's own practice separates three, and jason should too. Researched October 4, 2026; sources are linked, and the statutes marked "on the shelf" are quoted from `data/authorities`.

| Question | Who decides it at law | What it rests on | How it is reviewed |
|---|---|---|---|
| **Fact:** what happened, and what does the document say? | the finder of fact: a jury, or a judge sitting without one | the evidence in the record, and how far each piece is believed | with deference: it stands unless clearly wrong or unsupported by substantial evidence |
| **Law:** what does the provision mean? | the judge | the provision's words, read by the rules of construction | afresh ("de novo"), with no deference to the earlier reading |
| **Application:** do these facts meet that provision? | either, depending on which predominates (a "mixed question") | the facts as found and the law as read | afresh where the legal part predominates, with deference where the factual part does |

- **The division of labor.** California's Evidence Code gives questions of law, "including ... the construction of statutes and other writings", to the court (section 310), and questions of fact, with "the credibility of witnesses", to the jury (section 312) ([text](https://california.public.law/codes/evidence_code_section_312); not on the shelf).
- **The mixed question.** The facts are established, the rule is undisputed, and the issue is whether the facts satisfy the rule ([Ninth Circuit, standards of review](https://cdn.ca9.uscourts.gov/datastore/uploads/guides/stand_of_review/I.%20Definitions%202022.pdf); [Cornell, standard of review](https://www.law.cornell.edu/wex/standard_of_review)).
- **Why the standards differ.** The finder of fact saw the evidence, so its findings are hard to disturb. A reading of the law is the same for every case, so each court reads it for itself. After *Loper Bright* (2024) that holds for agencies too: a court decides what a statute means by its own judgment, while an agency's findings of fact still get deferential review ([King & Spalding](https://www.kslaw.com/insights/articles/loper-bright-v-raimondo)).

### The administrative law judge

An administrative law judge hears a matter for an agency, finds the facts, and proposes a decision. The agency decides.

- **The decision shows its work.** It is in writing, with "a statement of the factual and legal basis for the decision" (Government Code 11425.50(a); [text](https://california.public.law/codes/ca_gov't_code_section_11425.50); not on the shelf). A trial court's statement of decision does the same, for "each of the principal controverted issues" (Code of Civil Procedure 632).
- **Facts come only from the record.** The factual basis is "based exclusively on the evidence of record in the proceeding" and on matters officially noticed (11425.50(c)). Repeating the statute's words is not a finding: the decision states the underlying facts that support it (11425.50(b)).
- **Credibility is explained.** A finding that rests on believing a witness names the specific evidence for it (11425.50(b)).
- **The judge proposes; the agency adopts.** The proposed decision is written "in a form that may be adopted by the agency as the final decision". The agency may adopt it, reduce the penalty, make clarifying changes, send it back, or reject it and decide on the record itself (Government Code 11517(c)).

This is jason's position, already in AGENTS.md: jason proposes, and the board adopts. What it adds is the form of the proposal:
- findings of fact, each tied to the record;
- the provisions recited, and any reading of them labeled;
- the application, as a proposed determination;
- all three kept apart, so the board can accept the facts and reject the reading, or the reverse.

### The plain text

The words come first, and a reading of them is a separate thing.

- **The text governs where it is plain.** "The language of a contract is to govern its interpretation, if the language is clear and explicit, and does not involve an absurdity" (Civil Code 1638, on the shelf). For a writing, the intention is found "from the writing alone, if possible" (1639). Words are read "in their ordinary and popular sense", unless used in a technical one (1644).
- **The reader's office is narrow.** It is "simply to ascertain and declare what is in terms or in substance contained therein, not to insert what has been omitted, or to omit what has been inserted" (Code of Civil Procedure 1858, on the shelf).
- **Plain is judged in context.** The words are read with the rest of the provision and its purpose, never one sentence alone ([interpretation.md](interpretation.md) has the canons and their order).

For jason this gives a rule for storage. The **body of authorities** is the text itself: each provision, the version in force on a date, and a digest of its words. A **reading** is a derived record, kept apart and keyed to the digest of every provision it reads. A stored reading:
- is never shown in place of the words: an answer recites the provision first, then the reading, labeled as one and whose;
- is not needed where the words are plain: the record then says "plain", and quotes them;
- is void when any provision it reads changes: the digest no longer matches, and the reading is redone before it is used;
- gets no deference for being stored: like a question of law on appeal, it is checked against the text each time the text or the method changes.

### What this means for the records

The three questions become three stores, each rerun on its own trigger.

| Store | Holds | Rerun when | Deference |
|---|---|---|---|
| **Findings of fact** | what a document says and what the records show, each with its source and how far it is believed (a text layer over an OCR reading; a recorded instrument over a draft; two records that disagree are both kept) | the evidence changes: a new file, a better text, a person's answer | stands until the evidence changes; never re-found because the law changed |
| **Readings of the law** | what a provision means: plain, a labeled reading (whose, by which canon), or two readings that remain (the board asks counsel) | the provision's text changes, or a person or counsel replaces the reading | none; tied to the text's digest |
| **Applications** | whether the facts meet the provision: applies, does not apply, or undetermined ([applicability.md](applicability.md)), with the proposed determination | either side changes, or the as-of date does | none; recomputed from the other two |

- **Ingestion is fact-finding.** A reader's fields are findings of fact about a document. They rest only on the document.
- **A lens holds questions of law and of application.** Its authority scope names the provisions, and its readings are the stored ones. Its checks are applications.
- **A review is a proposed decision.** It states its factual basis, its legal basis, and its determination apart, for a person or the board to adopt, change, or reject.

## What jason does today

Almost every reader mixes the two (surveyed October 4, 2026).

- **One call does both.** `DocumentModel.read` runs `parse` and then `check`. `check` receives the profile, the data folder, and today's date. The fields and the findings are saved together as one row in `data/documents/readings.json`.
- **Context reaches some fields, not only the findings.** Examples:
  - an agenda's "notice sent" date is read from another store during `parse`;
  - a contract's "current term end" is rolled forward to today;
  - a contract's client is filled from the profile's name.
- **Findings that are really reviews sit inside readers.** Examples:
  - an invoice's "due date passed" (today);
  - a policy's "term ended" against the policy sheet (the profile, today, a statute);
  - a required insurance limit computed from the ledger (another store, a statute);
  - a lien's deadline (today, a statute);
  - a declaration's number against the pinned one (the profile).
- **A stale reading cannot be detected.** A reading records no digest of its input text, no reader version, and no as-of date. The text under an id can change (a vision reading is added) with the reading unchanged.
- **Reviews are stored apart in only a few places:** the manager-review briefs, the question-set answers, the invoice review, and the incident reports. Only the statute alignment records a fingerprint of its inputs.

What already points the right way:
- **Lenses exist under other names:** `TaskPrompt` rows, `QuestionSet`, the notice elements, the deontic grammar, the deliverable rules, and the applicability conditions.
- **Collections exist under other names:** an index catalog and `Scope`, a legal case's file, a meeting packet, an incident's evidence, a vendor's file.
- **Sources of a fact are already named:** `applicability.Source` separates the document, the profile, the date, and a person's answer.

## The records

### An ingested document

Keyed by the file's SHA-256, so two copies are one document.

| Part | What it holds |
|---|---|
| Aliases | the ids other stores use for it: library, Drive, mail, ingest |
| Text | the text's own digest, and where it came from: the text layer, an OCR engine, a vision reading |
| Kind | the `DocumentKind`, with the rule or model that gave it |
| Passages | its rows in the passage index |
| Readings | one per reader, keyed by (reader, reader version, text digest): the fields, what is missing, and only the findings that need nothing but the text ("no signature block", "two different totals") |

A reading is rerun only when its text digest or its reader's version changes.

### A lens

A lens is a reusable way to interpret documents. It is a row of data, like a `TaskPrompt` or a rule row, never a function with one association's facts inside it.

| Part | What it holds |
|---|---|
| Key and version | the version is a hash of its rows, so a changed lens is a new version |
| Applies to | document kinds, plus an applicability condition ([applicability.md](applicability.md)) |
| Questions and checks | what to ask of the document's fields or text; each check is `(reading, context) -> findings` |
| Authority scope | which law and which governing documents it reads: an index `Scope` by standing, chapter, or kind |
| Reference material | the companion pages and reference works that go into its context pack |
| Facts it needs | the profile methods and stores it reads, and whether it needs an as-of date |

General lenses worth writing first, each useful for any collection:

| Lens | The question it asks |
|---|---|
| Duties and deadlines | Who must do what, for whom, by when? Which terms are promises, permissions, conditions, or exemptions? |
| Parties and roles | Who is named, in what role, with what authority or license? |
| Chronology | What happened, in what order, according to which document? |
| Money | What amounts are stated, and do they agree with the ledger or with each other? |
| As of a date | Which deadlines have passed, which terms have ended, what is due next? |
| Against the law | Which provisions does the law require, forbid, or override, as of the document's date? |
| Against the governing documents | Does it follow the declaration, bylaws, rules, and policies, in their order of authority? |
| Consistency | Across the collection, what contradicts, repeats, or supersedes what? |
| Completeness | Which documents should the collection hold that it does not? |

A profile adds its own lenses the way it adds task prompts.

### A collection

A set of documents reviewed together, with the larger context that applies to all of them.

| Part | What it holds |
|---|---|
| Key | a legal case, a vendor, a meeting, an incident, a project |
| Members | an index `Scope` (a catalog, a folder, kinds), or a list of document digests |
| Context | what holds for the whole collection: the matter in a sentence, the parties, a chronology, the questions at issue, and facts for applicability |
| Companion material | a generated summary page and the reference works that bear on it |
| Confidentiality | the strictest of its members', and of the matter's |

For a legal case, the context is the case's record in the specification (its events and duties) plus a summary page built from the case file. A document in two collections is ingested once and reviewed in each.

### A review

Keyed by (document digest, text digest, lens, lens version, collection, as-of date, context digest). The context digest is a hash of what the lens read: the law's text, the profile's facts, the other stores' rows.

A review holds:
- its findings, each with its authority and the sources it quotes;
- its verdicts on the lens's questions: met, not met, not applicable, or unknown;
- who produced it: a grammar, a rule, or a model, and which one.

A review is rerun when any part of its key changes, and only then. The earlier result is kept, so a change is visible as a difference between two reviews.

Every finding names its **basis**: the text, the profile, another store, today's date, or the law. A finding whose basis is only the text belongs to ingestion. Any other belongs to a review.

A review is written as a proposed decision, in three parts kept apart:
1. **Findings of fact:** each with the document and passage it rests on, and what was missing or in conflict.
2. **The law:** each provision recited from the authorities, by its version in force on the as-of date. A reading is attached only where the words are not plain, labeled with whose it is and the digest of the text it reads.
3. **The application:** applies, does not apply, or undetermined, with the proposed determination.

### A reading of the law

Keyed by (provision, text digest, question).

| Part | What it holds |
|---|---|
| Provisions | each provision it reads, with the digest of its words and the version's dates |
| Question | what was asked of the words ("does 'day' mean calendar day?") |
| Standing | plain (the words answer it; they are quoted), a reading, or two readings remain |
| The reading | in a sentence, with the canon or authority relied on |
| Whose | jason's (a lead), the board's, or counsel's, with the date |

A reading whose digest no longer matches the provision's text is stale and is not used. A profile's readings (the board's, counsel's) are profile data; a reading of a statute's plain words is general.

## How a context pack fits

A context pack is what a lens gives a model or a person to review with. `context_pack.assemble` already builds one for a task. It generalizes to `assemble(lens, document, collection, as_of)`:

| Tier today | Under a lens |
|---|---|
| S: the law | the lens's authority scope, searched in the index |
| G: governing documents | the same, by standing and kind |
| R: records | the collection's members, searched in the index by the collection's `Scope` |
| F: facts | the profile's facts and the collection's context |
| D: the draft | the document under review, by its digest |

The same document can then be reviewed under two packs, and the two results are stored side by side.

## Order of work

1. **Inventory, with no change in behavior.**
   - Each reading records its text digest, its reader's version, and its as-of date.
   - `Finding` gets an optional `basis`. `ModelContext` records which of its parts a check touched (the profile, the data folder, today), so the basis is observed, not declared by hand.
   - The result is a table of which findings are reviews today.
2. **The review store and the first lens.**
   - `data/reviews/<document>/<lens>@<version>.json`, written under the store lock.
   - An "as of a date" lens takes over the checks that need only the stored fields and a date or the profile: an invoice's due date, a policy's term, a contract's current term end, a lien's deadline, minutes due.
   - Readers stop reading other stores during `parse`.
   - Commands and tools that read `readings.json` get a joined view in today's shape, so nothing downstream changes at once.
3. **Collections.**
   - `Collection` as a record. A legal case is the first: its index catalog and its record in the specification.
   - `assemble` takes a lens, a document digest, and a collection.
   - A manager review is keyed by its lens, the draft's digest, and the pack's digest, and no longer overwritten by slug.
4. **Readings of the law as records.**
   - A reading store keyed to each provision's text digest, filled first from what exists: the `Conflict` rows, the statutory terms, and the readings the docs already label.
   - The authorities' manifest gets a digest per section (docs/rag-roadmap.md, item 3), so a changed provision marks its readings stale.
   - A review recites the provision and attaches a reading only where one is stored.
5. **The general lenses,** one at a time, each measured on a small set of documents with known answers before it is relied on.

## Limits and risks

- **Other sessions' code.** The contract-terms reader, the license reader, and the kind readers are other sessions' work in progress. Their findings stay where they are until those sessions agree to the split.
- **Fields that are not context-free.** A field filled from the profile or another store during `parse` is wrong to treat as ingestion until it moves.
- **Findings that depend on today** change daily. They are keyed by as-of date or computed when read, never stored as if fixed.
- **Checks across documents** are reviews of a collection, and need the collection in their key.
- **Lens rows that hold an association's facts** belong in the profile.
- **Confidentiality carries over.** A review is as confidential as its document and its collection.
- **A review decides nothing.** It is a reading, labeled as one, with the words it relies on recited ([AGENTS.md](../AGENTS.md), "Recite the rule; label the reading").
