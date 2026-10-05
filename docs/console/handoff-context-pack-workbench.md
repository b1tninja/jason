# Handoff: the context-pack workbench

For the design pass on the components that **search jason's passage index by slice**, **show the context a review reads**, and **run a review under a chosen pack**. The data exists today, with no screen and no loader:

- **The index.** `jason index --plan` (what a build would take, catalog by catalog, with the confidential counts and what is left out), `--status` (files and passages by catalog and standing, the passages with no vector), `--search QUESTION` (scoped by `--catalog`, `--standing`, `--kind`, `--folder`, with held files only on `--confidential`), and `--build`. Behind them: `jason.community.passage_index` (`IndexSource`, `IndexFile`, `Scope`, `Standing`, `CORE_CATALOGS`, `search`, `status`) and `jason.community.retrieval` (BM25, the dense ranking, the exact-token boost, reciprocal rank fusion, near copies folded).
- **The pack.** `jason review TASK` with `--ask`, `--draft`, `--collection KEY` (or an ad hoc one from `--catalog`, `--kind`, `--folder`), `--as-of DAY`, `--mode`, `-k`, `--run`, and `--history`. Behind them: `jason.community.context_pack.assemble` (the tiers S, G, R, C, F, D, the gaps, the law on hand), `jason.tasks.manager_review` (the run, under the GPU lock after `jason.local_ai.preflight`), and `jason.tasks.review_store` (every pack kept by digest, with its runs).
- **The tools.** `document_search`, `passage_search`, `manager_context`, and `verify_quotes` in `jason-mcp` ([mcp.md](../mcp.md)), the same functions `jason.api` exports.

The design is settled in [applicability.md](../applicability.md#6-the-index-one-store-with-columns) (the index and its measured numbers), [ingestion-and-review.md](../ingestion-and-review.md#how-a-context-pack-fits) (the pack under a lens, and facts, law, and application kept apart), [manager-review.md](../manager-review.md#reviews-are-kept) (the kept reviews and the quote check), and [rag-roadmap.md](../rag-roadmap.md) (what was measured and left off).

The format follows [handoff-applicability-questions.md](handoff-applicability-questions.md) and [handoff-confirmations-queue.md](handoff-confirmations-queue.md). The words on screen follow [content/style.md](content/style.md), the patterns [content/patterns.md](content/patterns.md), the components [components.md](components.md). The neighbours this page links to and does not repeat: [screens/records-and-library.md](screens/records-and-library.md) (the library search: files by kind, record, period, and words, and a file's text; this page searches passages), [documents.md](documents.md) and [doc-component.md](doc-component.md) (how a hit's file opens: `Doc` and its viewer), and [handoff-confirmations-queue.md](handoff-confirmations-queue.md) (the gold labels that would decide the records tier). The neighbours written in this wave, named and not linked: `handoff-collection-workspace.md` (one collection read together: this page only picks one for a pack), `handoff-as-of-and-quote-check.md` (the day control, the version in force, and the verdict row of a quotation: this page places them), and `handoff-storage-and-settings.md` (the machine: drives, locks, local models, and the index's health in full: this page shows one line of it).

These components pair with what the console already has: `SearchBox`, `Pill`, `Doc` and `DocList`, `Recitation` and `ReadingLabel`, `Caveats`, `Command`, `Confirm`, `DataTable`, `Card`, `Tabs`, `Stat`, `Findings`, `RemoteView`, and the private view's switch. Build new parts only where the table says so.

## The idea in one line

A search returns **passages to read**, each saying what it is and how far its words can be relied on; a pack is **the passages one review reads**, each with why it is in, beside what was held back and what is missing; a run is **a person's act** that asks a local model to draft an answer from one pack, recited, labeled, and checked word by word. Nothing in the three decides: a hit is evidence, not a pin, and an answer is a draft for the board.

## The components

| Component | Where it renders | Data | States to design |
| --- | --- | --- | --- |
| `IndexLine` | the top of `#/workbench`, one line | `GET /api/index-status` | built (files, passages, catalogs, built when); files changed since the cut ("3 files changed since the index cut them"); passages with no vector; not built (the note and `jason index --build`); unreadable (the reason). The full health view is the storage handoff's |
| `IndexSearchBar` | Search band, first | `POST /api/index-search` | empty (Search is off, "Type a question"); typed (nothing runs until Search: no search on a keystroke); searching (hybrid: "asking the embedder"; waiting for the GPU, with the holder's purpose); done ("8 passages"); fell back to exact, with the tool's note; refused (an unknown standing or mode, in the tool's words); no index |
| `SliceControls` | under the bar | `index-status`'s catalogs and kinds; `review-tasks`'s collections | the core default ("Searched: … · Not searched: …" with why); a catalog named; all catalogs; a case catalog named (P3: in the private view only); a standing chosen; a kind chosen (it narrows, it opens nothing); a collection chosen (its scope); held files included (only while the private view is open, its reason shown); a slice that holds nothing ("0 files and 0 passages in this slice") |
| `SearchScopeLine` | above the results | the search answer's `searched`, `notSearched`, `heldInSlice`, `mode`, `note` | the core catalogs, with the ones left out named; every catalog; held files in the slice, counted and not shown; the mode asked and the mode used; no passage matched (the tool's note and `jason index --status`) |
| `PassageStanding` (a `Pill` preset) | every hit, pack source, and compared source | `standing`, `generated`, `confidential`, `catalog` | the five words below; a page that jason generated; a record from the mail (with its caveat); confidential (the P3 word, beside the standing, never a color) |
| `HitCard` | the results list | one hit | the passage's words as the index holds them; the file as a `Doc` chip; the section heading; rank; `PassageStanding`; catalog; kind, or "no kind" (a miss stays a miss); the file's context line; near copies folded ("also in 2 files", a disclosure of `Doc` chips); a page ("jason's summary, never the rule"); a mail hit; a reference hit; the file changed since the cut; "Evidence, not a pin" always visible |
| `PackBuilder` | Pack band, first | `GET /api/review-tasks` | a task picked (its title, purpose, audience, the count of topics and kinds); a question; text under review pasted; a collection: none, named, or this search's slice as an ad hoc one; the day (the as-of handoff's control: empty is "today, not named"); mode (hybrid, keyword, exact) and k; **Preview** (reads, writes nothing); **Keep** (a `Confirm`); a confidential collection with a task not for the board (refused before building, in the pack's own words) |
| `PackView` | Pack band | `POST /api/context-pack` (a preview) or `GET /api/review` (a kept pack) | tiers in order with their counts; a tier with nothing in it, with why; built as of a day (the header line); a preview, not kept; kept (digest, when, by whom); kept, and a source's words have changed since (the digest differs, said per source); a confidential pack outside the private view (its sources by tier and kind, "held: in the private view") |
| `PackSource` | inside `PackView`, one per source | one source | id; the tier's label, or the collection's label; title and place; `PassageStanding`; why it is in (each reason from the code); its characters, and "trimmed" where cut; a law source's digest; as of a day: what the words are, the words, the section's words given under a passage, and each reading listed under them as a `ReadingLabel` with its state; withheld from this viewer (P3) |
| `HeldBack` | inside `PackView`, before the gaps | `heldBack[]` | held by the index for this audience (a count and a kind); a collection refused for this audience; held by the governing tier or the library reader (counts the loader adds; see "What was held back"); none ("Nothing was held back for this audience") |
| `PackGaps` | inside `PackView` | `gaps[]` | each kind in "The vocabulary", with the command that closes it; none ("No gaps recorded. The pack holds what retrieval found, which is not all there is.") |
| `PackBudget` | the foot of `PackView` | `budget` | characters by tier, each against its cap; the sources trimmed, named; the model's window; after a run, the prompt's tokens as the model counted them; "No cap is tuned: there is no gold set for the pack" |
| `ModelGate` | Run band, first | `GET /api/model-gate` | ready; preflight refused (each of `local_ai.preflight`'s reasons with its command); the GPU lock held (purpose, since); the embedder loaded and to be unloaded first; no worker running (`jason worker`); a review of this pack already queued or running |
| `ReviewRun` (with `JobStatus`) | Run band | the queued job | not started (the `Confirm`); queued (place on the GPU lane); waiting: preflight refused, tried again later; waiting for the GPU; asking the model (time elapsed, the 30-minute limit); checking quotations; kept (run 2 of this pack); failed (exit code, the log's tail, what was kept); cancelled; the pack changed between Keep and Run (decision 3) |
| `ReviewAnswer` | Run band after a run; a kept review's page | one run | each issue in three parts (below); the considerations; conflicts, noted; "For the board to decide", as text on no control; open questions; the draft, when the task asks for one; an answer that could not be read; a source cited that the pack does not have |
| `QuotationCheck` | under each quotation in `ReviewAnswer` | `packCheck`, `verify` | both checks found it; the pack's check found it and `verify_quotes` says another version; a reading quoted as the provision; not found; altered (both texts, differences marked); skipped (too short to check); the place confidential and withheld. The verdict row itself is the as-of handoff's |
| `KeptReviews` | `#/workbench/reviews` | `GET /api/reviews?task=` | none kept ("No review of this task is kept yet"); packs only; packs with runs; confidential ones counted outside the private view, listed inside it; the day named or the day written |
| `PackCompare` | `#/workbench/compare` | `GET /api/review-compare` | one question, two packs; one pack, two runs; two questions (refused: "Compare one question"); what differs in how each was built; sources in both (matched by provision or file and section, never by id), in one only, and changed; gaps in one only; the quotations both cite; neither preferred |

## The vocabulary

Every state is a word from the code, so the console and the terminal agree, and no state is color alone. Keep the words.

**A passage's standing** (`passage_index.Standing`; the coarse shelf, below `authority_order.Tier`):

| Word | Meaning | Beside it |
| --- | --- | --- |
| authority | the law: statutes, regulations, an agency's adopted text | the citation |
| record | the association's governing documents and records, quoted as the record | the kind; a mail hit adds "a letter received: the sender's words as scanned" |
| reference | learned from, never quoted as binding | "reference: explains, never controls" |
| page | a page jason wrote from its stores (`generated`) | "jason's summary, never the rule: quote the record or the law it points to" |
| evidence | gathered for one matter (a case's file) | "neither the record nor the law" |

**Search modes** (`retrieval`): hybrid (keyword and the embedder fused, exact numbers first), keyword, exact (keyword with the exact boost, no model), dense. "Fell back to exact" is a state of its own, said with the tool's note.

**The pack's tiers** (`context_pack`): S the law · G the governing documents · R the records · C a collection's material (labeled with the collection's own words in place of a tier) · F jason's records · D the text under review. Within S and G each source also carries its place in the order of authority (`Tier.label`: "California statute", "declaration (CC&Rs, amendments, annexations)", …).

**Why a source is in** (the source's `note`, in the code's words): found for the task's topics · cited by a governing document · a former section read through the successor table · the version printed under its number · standing and catalog (a C source) · what holds for the whole collection · jason's summary of the collection: a summary, not the record.

**As of a day** (`Recitation.decided`; the as-of handoff designs the words in full): for the law, prior, current, own words, not shown, not found; for a governing passage, as amended, as amended below, not kept, unnamed. A reading listed under the words: current, stale, missing, misquoted, later. Only a current one is a reading on that day.

**What was held back, and the gaps** (each a row with its kind and command; see "The pack"): held by the index for this audience · collection refused for this audience · no law on hand · cited, not on hand · a former number: find the section in force · not shown in force that day · the collection not searched, missing files, no passages, no match · changed since the index cut it · retrieval fell back to keyword · a record of jason's unavailable.

**A run** (`jobs.JobStatus` and the run's stages): queued · waiting: preflight refused · waiting for the GPU · asking the model · checking quotations · kept · failed · cancelled.

**A quotation** (two checks, never merged): the pack's own check (`prompts.verify`): found in the source · not found in the source · a reading attached to the source, not the provision's words · no such source. `verify_quotes` (`quote_check.Verdict`): found (exact, normalized) · altered · misattributed · other version · not found · skipped.

**The answer's own words** (`prompts.ANSWER_SCHEMA`): a rule's force is required, permitted, or best practice; a consideration is met, not met, wrong, not applicable, or unknown.

The console never says "verified", "confirmed", "answer" alone, or "relevance": a found quotation says the words are stored, not that the answer reads them rightly.

## The search and its slices

**The bar.** One question field, a mode, and **Search**. A search runs when a person presses it, never on a keystroke or on load: in hybrid mode the question is embedded by the local embedder under the GPU lock, and a review run can hold that lock for half an hour. When the lock is held the bar says by what ("held: qwen3.6:27b chat, since 14:02") and offers exact mode, which needs no model. The question is sent in a POST body, never in the route: it can name a person ([security-and-privacy.md](security-and-privacy.md#urls)).

**The slice.** Four controls, each a closed set the index gives (`passage_index.catalogs`, the kinds in the index), never typed:

- **Catalog.** With none named, the search ranks the **core catalogs** (`CORE_CATALOGS`: records, insurance, authorities, publications, reference) and `SearchScopeLine` names the ones it left out (library, mail, reports, docs). The reason is a measurement, shown behind "Why only these": ranking the library, the mail, the reports, and jason's documentation together with the core took hybrid recall@5 from 0.86 to 0.83 and MRR@10 from 0.74 to 0.70 on the three gold sets (October 4, 2026; [applicability.md](../applicability.md#5-why-jasons-own-index-measured)), because their many passages crowd the answers out. **All** searches every catalog a person may see. A case catalog (`case-<key>`) is searched only when named, and only in the private view.
- **Standing.** The five words above; more than one may be chosen.
- **Kind.** The profile's document kinds as the index holds them. A kind narrows and opens nothing.
- **Collection.** A collection's scope (`document_collections.collections`) in place of the three above, with its label. The same slice can become a pack's ad hoc collection ("Use this slice in a pack"), which `PackBuilder` takes as `--catalog`, `--kind`, `--folder` take it.

**Held back unless asked.** A confidential file (a library file the library flags or holds, an attorney's letter, a bank statement, a report that names owners) is left out of every search. "Include held files" appears only while the person's private view is open; the view's stated reason stands as the search's reason, and each confidential listing shown is a line in `access/served.jsonl` ([security-and-privacy.md](security-and-privacy.md#built-the-private-view)). Outside it the switch is shown with why it is off ("held files open in the private view"; for the treasurer, the refusal's reason). `SearchScopeLine` says how many held files the slice has, never which: "4 files in this slice are held back: for directors and counsel." A letter that carries a PIN or an access code is in no catalog at all.

**The ranking is a rank.** The fused score is arithmetic over ranks, not a confidence: the card shows the rank. There is no "no good match" banner, because no threshold has been found that separates a question with no answer in the documents (`retrieval.NO_ANSWER_COSINE` is unset; six such questions against 116 answerable ones, October 2, 2026). A search with no hit says so in the tool's words.

## The hit card

`HitCard` shows, in this order:

1. **The passage**, its words as the index cut them, the question's exact tokens marked where the passage carries them (a section number, a recording number).
2. **Where it is**: the file as a `Doc` chip (`library:`, `file:`, or a citation reference, built by `jason.approvals.docref`), the section heading the cut gives, and the passage's number. Opening the file is the `Doc` viewer's logged view, never a raw path.
3. **What it is**: `PassageStanding`, the catalog, the kind (or "no kind"), and the file's context line (for a case file's extract: the source file and how it was read).
4. **Near copies, folded.** One document is often on the shelf two or three times (a Doc's export, a PDF's text, a scan's reading). The search folds a near copy into the best-ranked one (`retrieval.collapse`) and lists the rest: "also in 2 files", opened as `Doc` chips. Folding is measured (held-out recall@5 from 0.86 to 0.91, October 2, 2026); which copy leads is the ranking's, not the order of authority, since no store ranks a governing document's copies yet. The card says so in the disclosure.
5. **The caveats.** "Evidence, not a pin" is on every card, and the tool's caveats (`DOCUMENT_SEARCH_CAVEATS`) sit once above the list through `Caveats`, verbatim.

A card offers **Open the file** and **Copy the passage with its place** (the words with the file and section, never the words alone). It offers nothing that pins a fact, files a document, or answers the question.

## The pack

`PackBuilder` takes what `jason review` takes. The task is a specification row (`Community.task_prompts()`); its **audience** is the task's, not the viewer's, and it decides what may enter: a confidential file or collection enters only a pack for the board. **Preview** assembles the pack and writes nothing (as `manager_context` does; reciting a section of a document kept as amended may refresh the versions cache). **Keep** writes it, below.

`PackView` shows the pack as the model will read it, in order, with each tier's heading and count:

- **S, the law.** The sections on hand that best answer the task's topics, each recited whole, and each section a governing passage cites. Each is a `Recitation` with the version in force, its digest, and, as of a day, whether the words are shown in force that day and how. The sections whole are the default; ranking the index's law passages instead was measured (sections whole 0.98 recall@5 and 0.84 MRR@10; the index's passages 0.96 and 0.87; the two fused 0.96 and 0.88, October 4, 2026) and left off (`LAW_FROM_INDEX`).
- **G, the governing documents.** Passages, narrowed to the kinds the task names, each with its tier; copies in one kind folded. As of a day, the section the passage falls in is recited for that day.
- **R, the records.** The latest files of each record kind the task names, from the library reader. Reading them from the index was measured and left off (`RECORDS_FROM_INDEX`: on the six tasks that name record kinds the index's passages matched the reader's on none; there is no gold set for the pack).
- **C, a collection.** Its passages, labeled with the collection's own words ("evidence gathered for this matter: neither the record nor the law"), capped at 8 and 2 a file.
- **F, jason's records.** The tools the task names, as their records, trimmed; the collection's context lines; its summary page, labeled "jason's summary of the collection: a summary, not the record".
- **D, the text under review**, when there is one.

**What was held back** (`HeldBack`) sits before the gaps, each row with why: "the passage index holds back 2 minutes files as confidential that the library does not flag; this task's audience is all members: nothing from them is in this pack"; "the collection is confidential; this task's audience is all members: nothing from it is in this pack". Today two tiers leave held files out with no line: the governing tier read from the index and the library reader. The loader adds their counts (`heldBack[]` rows the build writes), so the band never reads "nothing held" when something was.

**The gaps** (`PackGaps`) are the pack's own lines, each with its kind and the command that closes it. The one the design must make plain is the former number: "CIV 9902 is a former Davis-Stirling number cited by a source; find the section in force", with **Build it as of the matter's day** (`jason review TASK --as-of DAY` reads the former number through the successor table and brings the section in force in) and the citation's successor line where the citations handoff gives one (`Successor`, proposed in `handoff-citations.md`).

**The size budget** (`PackBudget`). No one number limits a pack; caps do, each per source or per tier: a law section at 9,000 characters, a record of jason's at 6,000, a collection's summary at 16,000, 12 law sections from retrieval, 3 files and 2 passages a record kind, 8 collection passages and 2 a file, k passages a question before copies fold. The band shows each tier's characters beside its cap, names every source that was trimmed, and shows the model's window (65,536 tokens for the default model). Tokens are not estimated before a run: after one, the band shows the prompt's tokens as the model counted them (`prompt_eval_count`, which the run would store). "No cap is tuned: there is no gold set for the pack" is always on the band.

**The day.** A pack built as of a day says so in its header ("As of Mar 1, 2098, named by Jane Example"), and the law's search note stays visible: the law was found by searching it as it stands now, so a section repealed since is not among the sources. Without a day the header reads "today; no day named", and no law source carries an as-of line.

## Running a review under a pack

**Pick the pack and the question.** A run is always of one kept pack: a preview cannot be run. The Run band names the pack (task, question, collection, day, digest) and the model (the default, or another pulled model).

**The gate first** (`ModelGate`), read when the band opens and on **Check again**, never on the workbench's load. It shows, in words: whether the model is pulled; whether Ollama has the GPU; how much Windows commit is free against what the model needs; whether the embedder is loaded (the run unloads it first, and says so); who holds the GPU lock and for what (`locks.holders()`); and whether a worker is running the GPU lane. A refused preflight is shown in `local_ai.preflight`'s own words with its command ("unload a model (`jason local-ai --unload NAME --yes`) or raise the page file"), as a `Command`: the console unloads nothing.

**The act.** **Run the review on qwen3.6:27b as Jane Example**, behind `Confirm`, restating the pack, the model, that the text never leaves the machine, and that the run takes the GPU for up to 30 minutes. It queues a job on the GPU lane in the person's name; it is a heavy action a person starts, never one a page starts on load. While it is queued or running, `ReviewRun` shows the stage and the time elapsed, never a percentage: the model's answer comes back whole. A job waiting on a refused preflight is "waiting: preflight refused", tried again later by the worker, with the reason. A failed run shows the exit code and the log's tail, and says what was kept (the pack stays; no run is added).

**The answer, in three parts kept apart.** For each issue the answer raises, `ReviewAnswer` shows the issue in one sentence, then:

1. **What the documents say.** The answer's `facts`: each a quotation from a record, a collection's document, jason's records, or the text under review, with its source id, title, and `PassageStanding`.
2. **What the law says, recited.** The answer's `rules`, in the order of authority: each a quotation from a law source or a governing document, with its force (required, permitted, best practice) as the model gave it, and the provision's `Recitation` one click away. A rule that cites an R or F source is marked "a record cited as a rule: records are facts, not rules".
3. **How it is applied.** The answer's `application` and `conclusion`, under `ReadingLabel whose="jason"`: "jason's reading, drafted by qwen3.6:27b on Oct 5, 2099: a draft for the board, not adopted. A reading, not legal advice. The words above govern."

The split is the answer's own keys, never inferred by the client. After the issues: the considerations (each with its status and sources), conflicts ("noted": jason notes a conflict and never resolves one), "For the board to decide" as text on no control, the open questions, and the draft when the task asks for one.

**Each quotation's verdict** (`QuotationCheck`) carries both checks. The pack's own check (`prompts.verify`) knows the readings attached to a source and says when a quotation quotes a reading as the provision; it accepts a near match. `verify_quotes` reads the index and the shelf, checks a statute's words against the version in force on the pack's day, and names altered words, a misattribution, or another version; it does not know readings, so it calls a quoted reading "not found" ([manager-review.md](../manager-review.md#the-quote-check-and-readings)). The two are shown side by side and never merged into one verdict. The summary line reads "5 of 6 quotations found in their sources", never "verified".

## Comparing two packs on one question

`PackCompare` takes two kept reviews of one task and one question (the same `ask` and the same draft), or two runs of one pack. It never says which is better.

- **How each was built**, side by side: the collection, the day (named or the day kept), the mode, k, and the model of each run.
- **The sources**, matched by what they are, never by id ("S3" in one pack is not "S3" in the other): a law source by its citation and digest, a passage by its file and section. Three groups: in both (with "the same words" or "different words", and why where the record says, such as "B recites the words in force on Mar 1, 2098"), only in A, only in B. A source whose words changed since its pack was kept says so.
- **The gaps and what was held back**, only in A and only in B.
- **The answers**, side by side, each in its three parts, and the provisions both cite with whether they quote the same words. The issues are not aligned by the client; where the answers raise different issues, both lists stand.

The caveat, always shown: "Two packs, two drafts. Neither is preferred: the differences are what each pack held. Which serves the question is a person's judgment."

## States

| State | What shows | From |
| --- | --- | --- |
| Empty index | `IndexLine`: "No passage index: run `jason index --build`". Search is off, with why; a pack still builds (each tier cut from the folders, said in the gaps) | `index_path` absent; `document_search`'s `available: false` |
| Stale index | "3 files changed since the index cut them (records 2, library 1)". A search answers with the indexed words, and a hit on a changed file says so; a pack's tier that the index does not cover is cut from the folders, and a C source from a changed file carries its gap line | the plan's files against each file's `indexed_at` (`context_pack.index_covers`) |
| Embedding model missing | Search falls back to exact, with the tool's note; a pack falls back to keyword with the gap "retrieval fell back to keyword: …"; passages with no vector are counted ("120 passages have no vector: build again with the embedder") | `EmbeddingUnavailable`; `status().withoutVector` |
| GPU busy | the holder and purpose; exact mode offered for search; a queued run waits its turn | `locks.holders()` |
| Preflight refused | `ModelGate` in the preflight's words with its command; Run stays possible (it queues and waits), said so | `LocalAIUnavailable` |
| Partial | a pack with gaps; a record of jason's unavailable (its tool's error as a gap); a run with some quotations not found; an answer that could not be read ("The model's answer could not be read as JSON. The pack is kept; no answer is shown"); a source the answer cites that the pack lacks | the pack's gaps; `Checked.unknown_sources` |
| No worker | "No worker is running the GPU lane: start `jason worker`. The run stays queued." | the jobs table |
| Confidential pack | outside the private view, its sources by tier and kind with "held: in the private view", its answer withheld; inside it, whole, logged | the record's `confidential` |

## Privacy by level

| What | Level | Shown |
| --- | --- | --- |
| A hit or source of standing authority, reference, or a governing record; jason's documentation | P0 | always |
| A library file not held, a minutes passage, jason's pages, a mail letter not held; the question's words in a kept pack (`ask`), which can name a person | P1 | to roster people |
| A held file (the confidential flag), a case catalog (evidence), another association's mail, a kept review of a confidential collection, an answer that quotes any of them | P3 | in the private view only, each listing logged; outside it, counted, never named |
| A letter that carries a credential | P4 | never: it is in no catalog |

Two gates, both shown and never confused: the **task's audience** decides what enters a pack (`Audience.BOARD` alone takes held files), and the **viewer's level** decides what the console shows of it. A board pack seen outside the private view shows its held sources by kind only. The owner view has no workbench. A route carries a task's slug, a pack's digest, and a run's number, never a question's words.

## Data shapes

Made-up samples only: "Example Village HOA", "Jane Example", "CIV 9901", a case "24CV000123". The words of a passage or a provision are left out on purpose: on screen they come from the index and the shelf. Keys follow the commands' JSON (`jason index --search --json`, `document_search`, the review store's record) where one exists.

`GET /api/index-status` (proposed; `passage_index.status`, `commands.index.plan`, the changed-file count to write):

```json
{
  "found": true, "built": true, "index": "retrieval/index.db", "bytes": 412000000,
  "model": "qwen3-embedding:8b", "vectors": 9120, "withoutVector": 0,
  "core": ["records", "insurance", "authorities", "publications", "reference"],
  "coreWhy": "Ranking the library, mail, reports, and docs with the core took hybrid recall@5 from 0.86 to 0.83 and MRR@10 from 0.74 to 0.70 (October 4, 2026).",
  "catalogs": [
    {"catalog": "authorities", "standing": "authority", "files": 101, "passages": 2310, "core": true},
    {"catalog": "records", "standing": "record", "files": 64, "passages": 1890, "core": true},
    {"catalog": "library", "standing": "record", "files": 689, "passages": 5120, "core": false, "heldFiles": 120},
    {"catalog": "case-24cv000123", "standing": "evidence", "files": 20, "passages": 610, "core": false, "named": true, "confidential": true}
  ],
  "changed": {"files": 3, "byCatalog": {"records": 2, "library": 1}},
  "kinds": ["declaration", "bylaws", "minutes", "insurance_policy"],
  "commands": {"build": "jason index --build", "plan": "jason index --plan", "status": "jason index --status"}
}
```

`POST /api/index-search` (proposed; `document_search` with the held-file count to write). The body: `{"question": "…", "catalogs": [], "standings": ["record"], "kinds": [], "folders": [], "collection": "", "mode": "hybrid", "k": 8, "includeHeld": false}`. The answer:

```json
{
  "available": true, "mode": "hybrid", "count": 1,
  "searched": ["records", "insurance", "authorities", "publications", "reference"],
  "notSearched": ["library", "mail", "reports", "docs"], "heldInSlice": 4,
  "hits": [
    {"rank": 1, "doc": {"address": "file:governing/declaration-example.md", "name": "Declaration (Example Village HOA)", "kind": "text", "level": "P0"},
     "section": "Article 7 > 7.3 Leasing", "passage": 41, "catalog": "records", "standing": "record", "kind": "declaration",
     "generated": false, "confidential": false, "context": "", "text": "(the passage's words, as the index holds them)",
     "exact": ["7.3"], "changedSinceCut": false,
     "alsoIn": [{"address": "library:4001", "name": "Declaration (recorded copy).pdf", "kind": "pdf", "level": "P0"}]}
  ],
  "note": "",
  "caveats": ["A hit is evidence to read, not a pin: quote the passage's own words with its file and section, and decide nothing from a hit alone.", "…"]
}
```

`POST /api/context-pack` (proposed; `context_pack.assemble`, writing nothing). The body: `{"task": "question", "ask": "…", "collection": "case-24cv000123", "asOf": "2098-03-01", "mode": "hybrid", "k": 4}`. The answer (one source a tier shown):

```json
{
  "found": true, "task": "question", "taskTitle": "a question for the manager", "audience": "the board",
  "asOf": "2098-03-01", "asOfNamed": true, "mode": "hybrid", "modeUsed": "hybrid", "k": 4,
  "digest": "3f9a02c1d4e7a8b9", "kept": null,
  "collection": {"key": "case-24cv000123", "kind": "legal case", "title": "Example v. Example Village HOA", "confidential": true,
                 "included": true, "label": "evidence gathered for this matter: neither the record nor the law"},
  "tiers": [
    {"letter": "S", "name": "the law", "count": 5, "sources": [
      {"id": "S1", "tier": 2, "tierLabel": "California statute", "title": "CIV 9901", "place": "CIV 9900-9910: Chapter 99. Example",
       "standing": "authority", "why": ["found for the task's topics", "cited by a governing document"], "chars": 4210, "trimmed": false,
       "provision": {"citation": "CIV 9901", "digest": "0a1b2c3d4e5f", "shown": true, "decided": "prior",
                     "above": ["(what the words are: the version, its range, the act that made it)"],
                     "readings": [{"key": "example-day-means", "standing": "reading", "whose": "board", "dated": "2097-06-10", "state": "current"}]}}]},
    {"letter": "G", "name": "the governing documents", "count": 4, "sources": [
      {"id": "G1", "tier": 5, "tierLabel": "declaration (CC&Rs, amendments, annexations)", "title": "Declaration", "place": "governing/declaration-example.md, passage 41",
       "standing": "record", "why": [], "chars": 1380, "trimmed": false,
       "provision": {"citation": "declaration#7.3", "digest": "1122334455aa", "shown": true, "decided": "as_amended_below", "readings": []}}]},
    {"letter": "C", "name": "the collection", "count": 6, "sources": [
      {"id": "C1", "label": "evidence gathered for this matter: neither the record nor the law", "title": "Complaint.pdf.txt",
       "place": "cases/24cv000123/Complaint.pdf.txt, passage 3", "standing": "evidence", "why": ["standing: evidence; catalog: case-24cv000123; confidential"],
       "chars": 1610, "trimmed": false, "level": "P3"}]},
    {"letter": "F", "name": "jason's records", "count": 2, "sources": [
      {"id": "F1", "title": "board_items", "place": "jason records", "standing": "page", "why": [], "chars": 6000, "trimmed": true}]}
  ],
  "heldBack": [{"tier": "R", "kind": "minutes", "count": 2, "why": "held as confidential by the index; this task's audience may read them", "inPack": true}],
  "gaps": [
    {"kind": "former-number", "text": "CIV 9902 is a former Davis-Stirling number cited by a source; find the section in force", "command": "jason review question --as-of 2098-03-01"},
    {"kind": "not-shown-that-day", "text": "as of 2098-03-01: 1 of the 5 law sources are not shown to be in force that day (S4): …", "command": "jason law-history --versions --citation CIV-9904"}
  ],
  "shelf": {"chapters": 101, "command": "jason export-authorities"},
  "budget": {"chars": 41230, "byTier": {"S": 19800, "G": 6100, "C": 9330, "F": 6000},
             "caps": [{"name": "a law section", "chars": 9000}, {"name": "a record of jason's", "chars": 6000}, {"name": "a collection's passages", "count": 8, "perFile": 2}],
             "trimmed": ["F1"], "window": {"model": "qwen3.6:27b", "tokens": 65536}, "promptTokens": null, "tuned": false},
  "caveats": ["A pack is what retrieval found, numbered in order of authority: each source is a lead to read, not a ruling.", "The law was found by searching it as it stands now: a section repealed since is not among the sources."]
}
```

`GET /api/model-gate?model=qwen3.6:27b` (proposed; `local_ai.preflight` and `status`, `locks.holders`, `jobs.jobs`):

```json
{"model": "qwen3.6:27b", "pulled": true, "gpu": true, "loaded": ["qwen3-embedding:8b"], "unloadFirst": ["qwen3-embedding:8b"],
 "preflight": {"ok": false, "why": "loading qwen3.6:27b needs about 24.0 GB of Windows commit and 9.5 GB is free; unload a model (jason local-ai --unload NAME --yes) or raise the page file"},
 "gpuLock": {"held": true, "purpose": "qwen3-embedding:8b embed", "since": "2099-10-05T14:02:00"},
 "worker": {"running": true}, "queued": [{"job": 41, "command": "review question --run --model qwen3.6:27b", "status": "queued", "by": "Jane Example"}],
 "commands": {"status": "jason local-ai", "worker": "jason worker"}}
```

`POST /api/write/reviews/run` (proposed; behind the write guard): `{"task": "question", "digest": "3f9a02c1d4e7a8b9", "model": "qwen3.6:27b", "by": "Jane Example"}`. The answer: `{"job": 42, "resource": "gpu", "status": "queued", "command": "jason jobs add --resource gpu --confirm \"Jane Example\" -- review question --ask \"…\" --collection case-24cv000123 --as-of 2098-03-01 --run --model qwen3.6:27b"}`.

`GET /api/review?task=question&collection=case-24cv000123&digest=3f9a02c1d4e7a8b9` (proposed; the review store's record, its run split into the three parts, and `verify_quotes` over each run's quotations with the pack's sources and day):

```json
{
  "found": true, "task": "question", "digest": "3f9a02c1d4e7a8b9", "asOf": "2098-03-01", "asOfNamed": true,
  "confidential": true, "confidentialWhy": "a review of a confidential collection is confidential: for directors and counsel, never an owner, the newsletter, or an open meeting",
  "keptBy": "Jane Example", "sources": [{"id": "S1", "standing": "authority", "file": "authorities/CIV/CIV-9900-9910.md", "section": "CIV 9901", "digest": "…", "changedSince": false}],
  "runs": [{
    "n": 1, "at": "2099-10-05T14:31:00Z", "model": "qwen3.6:27b", "by": "Jane Example", "promptTokens": 21340,
    "packCheck": {"found": 5, "notFound": 1, "unknownSources": []},
    "issues": [{
      "issue": "(the issue, in the model's sentence)",
      "documents": [{"source": "C1", "quote": "(words quoted from the complaint)", "packCheck": "found in the source",
                     "verify": {"verdict": "found", "match": "normalized"}}],
      "law": [{"source": "S1", "citation": "CIV 9901", "quote": "(words quoted from the section)", "force": "required",
               "packCheck": "found in the source", "verify": {"verdict": "found", "match": "exact", "inForce": "the version of 2097, in force that day"}},
              {"source": "G1", "citation": "declaration#7.3", "quote": "(words quoted from the reading)", "force": "permitted",
               "packCheck": "a reading attached to the source, not the provision's words", "verify": {"verdict": "not found"}}],
      "application": "(the model's application)", "conclusion": "(the model's conclusion)",
      "whose": "jason's reading, drafted by qwen3.6:27b: a draft for the board, not adopted"}],
    "considerations": [{"consideration": "(from the task row)", "sources": ["S1", "G1"], "status": "unknown", "note": ""}],
    "conflicts": [], "boardDecisions": ["(a question the answer says the board decides)"], "openQuestions": [], "draft": ""}],
  "caveats": ["A review is a draft for the board; it decides nothing.", "This checks words, not meaning: …"]
}
```

`GET /api/review-compare?task=question&a=3f9a02c1d4e7&b=9e8d7c6b5a4f` (proposed; `&runA=` and `&runB=` for two runs of one pack):

```json
{"found": true, "task": "question", "sameQuestion": true,
 "built": [{"what": "collection", "a": "none", "b": "case-24cv000123"}, {"what": "as of", "a": "2099-10-05 (the day kept)", "b": "2098-03-01 (named)"}],
 "sources": {"both": [{"a": "S1", "b": "S2", "match": "CIV 9901", "sameWords": false, "why": "B recites the words in force on 2098-03-01 (an earlier version)"}],
             "onlyA": [{"id": "G3", "match": "rules-example.md, Rule 4"}], "onlyB": [{"id": "C1", "match": "Complaint.pdf.txt, passage 3", "level": "P3"}]},
 "gaps": {"onlyA": [], "onlyB": ["the passage index lacks 2 of the 20 files of the collection …"]},
 "citedByBoth": [{"provision": "CIV 9901", "sameQuote": false}],
 "caveats": ["Two packs, two drafts. Neither is preferred: the differences are what each pack held. Which serves the question is a person's judgment."]}
```

## What the design must keep

- **A hit is evidence, not a pin** (principle 3). No control on a hit pins a fact, files a document, marks it the answer, or scores it. The rank is shown, never the fused score as a confidence, and there is no "nothing relevant" verdict until a measured threshold earns one.
- **The core default says what it left out, and why.** "Searched" and "Not searched" are on the results every time the default applies, with the measured numbers behind "Why only these". **All** is one click; it is never the default.
- **Held back unless asked, with a reason.** Held files open only in the private view (its reason, its time limit, its log), never from a checkbox on the page; the count of what was held in the slice or the pack is shown, never the names. A case catalog opens only when named. The pack's audience is the task's and is not a control.
- **Recite first; label the reading** (principle 2). A law or governing source opens as a `Recitation` with its version and digest; a reading listed under it is a `ReadingLabel` with whose and its state, and only a current one counts on the pack's day. The answer's application is jason's reading, drafted by a named model, labeled, under the recited rules and the documents' words.
- **Facts, law, and application apart** ([ingestion-and-review.md](../ingestion-and-review.md#a-review)). The three parts come from the answer's own keys, in that order, never merged into prose, so the board can accept the facts and reject the reading.
- **Two quote checks, side by side.** The pack's check and `verify_quotes` answer different questions; neither is hidden and neither overrides the other.
- **A run is a person's act.** Nothing loads a model on page load: not the gate's first read, not a preview, not a search typed but not sent. A preview never unloads a model: `manager_review.build` releases the chat model once when the embedder fails; the preview calls `assemble` and takes the keyword fallback with its gap line. The run's `Confirm` names the model, the time it can hold the GPU, and that the text stays on the machine.
- **A miss stays a miss** (principle 8). A tier with nothing says why; a gap is never hidden to make a pack look whole; a kind the profile did not assign is "no kind".
- **The board decides.** "For the board to decide" is text. No control on this screen approves, adopts, sends, or proposes on the answer's say-so.
- **Nothing is worked out on the client.** The gaps' kinds, the held counts, the budget, the three-part split, the source matching in a comparison, and the quotation verdicts all come from the loaders.
- **No color-only meaning.** Each standing, tier, gap kind, verdict, and run stage is a word; a budget bar has its numbers in text beside it.

## Where it goes

Routes are proposed, consistent with [information-architecture.md](information-architecture.md#where-the-proposed-screens-go); none exists yet.

- **Records → Search and review** (proposed): `#/workbench`, board-only (`owner: false`), as `Tabs`: **Search** (`IndexLine`, `IndexSearchBar`, `SliceControls`, `SearchScopeLine`, the hits), **Pack** (`PackBuilder`, `PackView`), **Run** (`ModelGate`, `ReviewRun`, `ReviewAnswer`), and **Kept** (`KeptReviews`). One kept pack: `#/workbench/pack/<task>/<collection>/<digest>`; one run: `…/<digest>/run/<n>`; a comparison: `#/workbench/compare?task=<slug>&a=<digest>&b=<digest>`. A route carries slugs, keys, digests, and run numbers only; the question and the search words travel in POST bodies. The header's `Command` is `jason review --list` on the Pack band and `jason index --status` on Search.
- **The dock's Ask** (`AskPanel`): a question with no library hit offers "Search the passage index", which opens `#/workbench` with the question in the field (not sent; a person presses Search).
- **Document ingestion** (`#/ingestion`, [screens/records-and-library.md](screens/records-and-library.md)): its header shows `IndexLine` beside the library's counts.
- **Legal** (`#/legal`) and the collection workspace: "Review under this collection" opens the Pack band with the collection chosen.
- **Jobs** (`#/jobs`): a review run is a row there like any GPU job.

**Loaders and writes to add** (names only; nothing built; each wraps a function that exists today, except where marked "to write"):

| Name | Route | Wraps | Notes |
| --- | --- | --- | --- |
| `index-status` | `GET /api/index-status` | `passage_index.status`, `catalogs`, `count`; `commands.index.plan`; the changed-file count (to write, from `context_pack.index_covers`'s comparison, made public) | the index path relative to the data folder, never absolute (`tests/test_loader_paths.py`) |
| `index-search` | `POST /api/index-search` | `jason.api.document_search` (`_index_search`'s scope); `passage_index.count` with and without held files for `heldInSlice` (to write); `docref` for each file | `includeHeld` refused (403) outside the private view; each held listing logged as the library's are |
| `review-tasks` | `GET /api/review-tasks` | `Community.task_prompts()`; `document_collections.collections` with `passage_index.count` (as `jason review --collections`) | slugs, titles, audiences, counts; never a task row's guidance text beyond what `jason review --list` prints |
| `context-pack` | `POST /api/context-pack` | `context_pack.assemble` (not `manager_review.build`: no unload); `ContextPack.sources`, `gaps`, `shelf`; the structured gaps and held rows (to write: `assemble` records each as a row with its kind, keeping the text); the budget (to write: each source's characters and trimmed flag) | writes nothing (the versions cache aside) |
| `model-gate` | `GET /api/model-gate?model=` | `local_ai.status`, `preflight` (caught, its message returned), `locks.holders`, `jobs.jobs` | read when the Run band opens, never on load |
| `reviews` | `GET /api/reviews?task=` | `review_store.history` (`include_confidential` only in the private view) | the confidential count outside it |
| `review` | `GET /api/review?task=&collection=&digest=` | the record; `quote_check.check` over each run's quotations with the pack's sources and day (disk only) | the three parts from the answer's keys; a source's `changedSince` by its digest against the store |
| `review-compare` | `GET /api/review-compare?task=&a=&b=` | two records (to write: the matching by citation and digest, or file and section) | refuses two questions |
| write `reviews/keep` | `POST /api/write/reviews/keep` `{task, ask, draft, collection \| adHoc, asOf, mode, k, by}` | `manager_review.save_pack` and `review_store.store` under the store lock; the record gains `keptBy`, `mode`, `modeUsed`, and `k` (to write) | **Keep this pack as Jane Example**; CLI `jason review TASK --ask "…" [--collection KEY] [--as-of DAY] --mode hybrid -k 4`. It also writes `data/briefs/<task>.md`, the latest copy, as the CLI does |
| write `reviews/run` | `POST /api/write/reviews/run` `{task, digest, model, by}` | `jobs.add(argv, confirmed_by=by, job_class_override=JobClass.GPU, max_attempts=1)`; the run's record gains `by` and `promptTokens` (to write) | **Run the review on MODEL as Jane Example**; CLI `jason jobs add --resource gpu --confirm NAME -- review TASK … --run --model MODEL`. Today `jobs.job_class` puts `review … --run` on the local lane unless `--model` is given: the write passes the GPU lane, and the build should add the row |
| write `jobs/<id>/cancel` | `POST /api/write/jobs/<id>/cancel` `{by}` | the jobs table's cancel (as `jason jobs cancel ID`) | a queued run only; a running one finishes or fails |

## Accessibility

As [components.md](components.md#accessibility) and [content/patterns.md](content/patterns.md#accessibility-wcag-22-aa), with these particulars.

- **The search is a form.** The question field has a visible label ("Question"), the mode is a radio group, and **Search** is a submit button; Enter submits. `SliceControls` is a `fieldset` with a legend ("Search in"); each control is a labelled multi-select (a list of checkboxes, not a custom combobox). The result count and the scope line are one polite `role="status"` message ("8 passages from the core catalogs; library, mail, reports, and docs not searched; 4 held files not shown").
- **Hits are a list** of `article`s, each with a heading (the file and section), in rank order; the rank is in text ("1 of 8"). "Also in 2 files" is a `details` whose summary carries the count. The exact tokens marked in a passage use `mark`, and the marking is never the only sign of a match.
- **The pack is headed by tier.** Each tier is a section with an `h2` and its count; each source a `figure` (a `Recitation`) or an `article`; a reading follows its words as an `aside` with its label, so a screen reader meets the words first. `PackBudget` is a table with a caption, never a bar alone.
- **The run.** `ModelGate`'s refusal is text with its `Command`. `ReviewRun`'s stage is a polite `role="status"` line that announces a change of stage, not each second; elapsed time is in text and not announced. A failed run is `role="alert"` with the log's tail in a focusable, labelled region.
- **The answer.** Each issue is a section; its three parts are `h3`s in fixed order ("What the documents say", "What the law says, recited", "How it is applied"). Each quotation is a `blockquote` with its source id and title in a `cite`; `QuotationCheck` is a two-item list, each check naming itself.
- **The comparison** is two columns on a wide screen and one list on a narrow one, each item saying "A only", "B only", or "both" in text.
- **Target size (2.5.8)**: chips, disclosures, and the copy button on a `Command` are 24 by 24 CSS px or spaced to pass. **Redundant entry (3.3.7)**: the name on Keep and Run comes from "Signed in as". **Timing (2.2.1)**: nothing times out on the page; a typed question and a half-built pack stay across a band change. **Focus (2.4.3)**: after Search, focus stays on the button and the status message announces the count; after Keep, focus moves to the kept pack's heading.

### The phone layout (under 720 px)

- The bands' tabs become a `select`. `IndexLine` folds to one sentence with a disclosure.
- The search bar is full width; `SliceControls` sits in a disclosure whose summary names the slice ("Core catalogs · any standing"). Hit cards stack: the section heading, `PassageStanding` and catalog on one line, the passage, then the file chip; "also in" stays a disclosure.
- `PackView` stacks the tiers; each source shows its id, title, standing, and why on two lines, with the words behind "Show the words". `HeldBack` and `PackGaps` stay open above the sources' end, never collapsed: a gap is not optional reading. `PackBudget` becomes a two-column table (tier, characters of cap).
- The Run band stacks `ModelGate`, the `Confirm` (not sticky: one act at the end of a reading), then `ReviewRun`. The answer's three parts stack in order; each `QuotationCheck` sits under its quotation.
- `PackCompare` becomes one list grouped "In both", "Only in A", "Only in B", each row saying which pack in words.
- Nothing scrolls sideways at 320 px; a long passage wraps inside its card.

## Decisions for the design

1. **One screen or bands elsewhere.** `#/workbench` gathers search, packs, runs, and the kept reviews. The alternative is search in `#/ingestion` beside the library search and the packs on each task's own screen (a notice's draft, a case). Decide which serves the manager who asks a question in the morning and reviews a draft at night; the loaders are the same either way.
2. **Search on Enter, or a second step for hybrid.** Exact mode needs no model; hybrid embeds the question under the GPU lock (0.46 s a query measured, longer when the lock is held). Decide whether Search runs hybrid by default, as `document_search` does, or exact by default with hybrid one choice away while a run holds the GPU.
3. **A pack that changed between Keep and Run.** The run builds the pack again from its arguments; when a source changed in between, the run is kept under a new digest. Decide whether the run refuses then (the stale-plan pattern: "The pack changed since you kept it. Keep it again, then run"), which needs the job to carry the expected digest, or runs and says plainly that it ran a newer pack.
4. **The measured-off switches.** `assemble` takes `law_index`, `records_index`, and `records_reach`, each left off by a measurement. Decide whether the Pack band offers them as labeled experiments for a comparison only (with their numbers and "measured no better; off by default"), or leaves them to the terminal and the eval scripts.
5. **The structured gaps.** Today a gap is a sentence. Decide with the build whether `assemble` records each gap and held row as a record (kind, text, command), keeping the sentence for the page it writes, or the loader groups them by the code's own phrases; the second is fragile and is named so.
6. **Choosing files for a pack.** A hit can be one of a few files a person wants a review to read. `Scope.paths` exists, and `document_collections.ad_hoc` takes no paths. Decide whether "Review these files" (an ad hoc collection of named files) belongs here, or a person names a slice only.
7. **How much of a passage the card shows.** The CLI cuts at 300 characters; a section passage can run to a page. Decide the cut, and whether the exact tokens' sentence is shown first when it falls past the cut.
8. **The kept-reviews list.** Decide whether `KeptReviews` is its own band or a column of the Pack band's task picker ("3 kept: 2 with runs"), and how a confidential count reads outside the private view without inviting a guess at its subject.

## Not part of this pass

- Building or rebuilding the index from the console, the index's health in full, the locks, and the local models' state: the storage handoff's (`handoff-storage-and-settings.md`). This page shows `IndexLine` and the commands.
- The day control and the verdict row of a quotation: the as-of handoff's (`handoff-as-of-and-quote-check.md`). This page places them.
- One collection read together (its summary, chronology, conflicts, missing files): the collection workspace's (`handoff-collection-workspace.md`).
- The document reviews' lenses (`jason models --as-of`, `--lens records`, `data/reviews/documents/`): they review stored fields, not a pack, and `assemble` takes no lens yet ([ingestion-and-review.md](../ingestion-and-review.md#how-a-context-pack-fits)).
- Gold labels for the records tier and the choice of `RECORDS_FROM_INDEX`: the confirmations queue's, then a person's decision after the score.
- The reranker (`LlmReranker`, off) and a dense floor (none measured).
- Drafting an email or a board item from an answer: [handoff-draft-from-item.md](handoff-draft-from-item.md) and the board's items.
- Any model off the machine for a review, and any write outside jason.
- The owner view: the workbench is board-only at every phase.
- The previews: the design project's authored preview for each component follows the build; fixtures will be `ui/src/components/hitcard.test.tsx` and its siblings, from the sample data above.
