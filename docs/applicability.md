# Applicability, ingestion, and the search index

**Status:** proposed design, October 4, 2026. Built so far: the measurement in "Why jason's own index", the index and its sources (step 4), the applicability module (step 2), the systems fact and the first converted rows (step 3), the context-header measurement (step 5), and AnythingLLM's retirement (step 8). The contract-terms reader is another session's code, so the parts that touch it (the gate, the scope of a term) are proposals to that session until it agrees.

## The problem

A provision applies only to some things. A statute applies to some systems and not others. A contract term binds one party, on one site, for one kind of work. A rule applies to rentals and not to owners in residence. A version of a statute is in force only between two dates.

jason handles one of these well, which is time: `in_force`, `statutory_terms.Prior`, and supersession. The others are scattered:
- a gate inside the contract reader decides when the fire-protection deliverable rules apply;
- `FilingRule` has its senders and source kinds;
- the profile's kind rules;
- prose in the notice catalog ("applies to ...");
- obligation rows that simply leave out what they do not cover.

Retrieval does not know any of it. A question about one kind of system retrieves a standard's text just as readily when the standard excludes that system.

## 1. One record: what a row applies to

Add a module, `jason.community.applicability`. A rule-like row (an obligation, a deliverable rule, a statutory notice, a filing rule, a catalog rule, a term's scope) carries an `applies` condition built from closed sets.

| Facet | What it names | Where the fact comes from |
|---|---|---|
| Document | the document kind: contract, home improvement contract, proposal, inspection report | the classifier (`DocumentKind`) |
| Subject | the system or topic: a fire sprinkler by its installation standard, a fire alarm, backflow, a roof, a balcony | the document's words; the profile's systems |
| Party | the vendor's role, its license classes, the association, an owner, a tenant | the vendor directory; the license reader |
| Property | condominium or planned development; the occupancy class; the number of units | the profile |
| Place | state, county, city, water purveyor | the profile's region |
| Transaction | the amount; where it was signed; who the buyer is | the contract's own figures and dates |
| Time | in force between two dates; the edition adopted; within N years of an event | the existing `in_force` and `Prior`, folded in |

- **Combining conditions.** A condition is all-of, any-of, or not, over facet tests, with exclusions spelled out. Example: a standard applies to water-based systems, except those installed under the one- and two-family standard.
- **Facets are enums.** A JSON row stores the word, and the loader turns it into a symbol (AGENTS.md). A profile's own members (its systems and buildings) stay in the profile.
- **Shape of a row.** A condition is a frozen dataclass beside the row it governs. It is never a function with one association's id inside it, so a new decision is a new row.

## 2. Three answers, never two

`evaluate(condition, facts)` returns one of three answers:
- **Applies.**
- **Does not apply**, with the fact that decided it.
- **Undetermined**, with the missing fact named.

Undetermined is never read as "does not apply". It becomes a question for a person: an intake question, or a canvas item when the answer is a reading for counsel. This is the "a miss stays a miss" rule. Example: whether common-area work for an association is "home improvement" for a home improvement contract's notices is a reading for counsel, so it stays undetermined until then.

Every output records:
- the rule row that applied;
- the facts that decided it, and where each fact came from;
- the facts that were missing.

## 3. Facts in ingestion

```
classify  ->  document facts      ->  join profile facts      ->  apply only the rows that apply
              (kind, vendor,          (the system at that
              license classes,        address and its
              systems named,          standard, the units,
              amounts, dates,         the region, the date)
              sites)
```

- **Document facts** come from what jason already reads: the classifier, the vendor directory, the license reader, the contract-terms reader, the dates.
- **Profile facts** come from `Community` methods with empty defaults. A profile that lacks a fact gets "undetermined", never a crash. Systems are the first new fact needed: the `LifeSafetySystem` record proposed in [console/screens/life-safety.md](console/screens/life-safety.md).
- **The contract reader's fire gate becomes one row.** The fire-protection deliverable rules apply when the subject is a fire protection system and the vendor inspects, tests, or maintains it. The decision moves out of the reader's code and into data. This is for the contracts session to agree to.

## 4. Scope stated inside a document

Governing documents and contracts state their own scope:
- "this Section applies only to ...";
- "with respect to the Phase 1 Property";
- "shall not apply to ...";
- an exclusions list in a proposal.

The term readers should read this into each term as its scope, using the same facets. Then:
- a cost-center component in an annexation scopes its maintenance terms;
- a proposal's exclusions become the exemption kind already proposed to the contracts session;
- a split between in-unit parts and common parts is two scopes, not one term.

A scope read from the text is evidence, not a pin, like any other reading: it is recited with its words, and the reading is labeled ("Recite the rule; label the reading").

## 5. Why jason's own index, measured

The plan for retrieval rests on one measurement, taken October 4, 2026 on the 140 gold questions. The tables are in [document-tools.md](document-tools.md) (model trials) and the per-question results in `data/retrieval/runs/2026-10-04-anythingllm.json`.

| | recall@5 | MRR@10 | a query |
|---|---|---|---|
| jason's hybrid (BM25 + `qwen3-embedding:8b` + the exact-token boost, near copies folded) | 0.89 | 0.76 | 0.46 s |
| AnythingLLM, the shared workspace (the same embedder, its own chunks) | 0.47 | 0.32 | 2.2 s |
| AnythingLLM, on the 110 questions whose answer it holds | 0.60 | — | — |
| jason's hybrid, on the same 110 | 0.91 | — | — |

- **Why AnythingLLM misses.** It answers 4 questions the hybrid misses, and misses 62 that the hybrid answers.
  - 25 of the 62 have no answer anywhere in its stored text. Some are thin parses of a scanned PDF; others are documents never uploaded, such as Google Doc exports.
  - The other 37 are ranking misses. Its losses concentrate on exact tokens (recording, rule, and resolution numbers, statute citations), where it has only the dense ranking and no keyword ranking.
- **It cannot be scoped.** AnythingLLM has no metadata filtering. The request for it ([#1858](https://github.com/Mintplex-Labs/anything-llm/issues/1858)) was closed as not planned, so a workspace is its only boundary.
- **Merging catalogs does not help.** Merging the record, insurance, and page catalogs by score was no better than the shared workspace. Separate workspaces add nothing without a filter.

## 6. The index: one store with columns

jason's vectors move from one `.npy` file per passage (`data/retrieval/vectors`) into an embedded store with columns. A filter is then a column condition, not a second workspace.

**Engine.** [LanceDB](https://docs.lancedb.com/core/filtering) is the proposal: a pip package with no server, vector and full-text indexes, and filters. It is the engine AnythingLLM itself runs on. sqlite-vec is the plainer fallback, since SQLite already ships with Python. The choice is measured on the gold set, under these conditions:
- it must at least match today's hybrid;
- it must keep the exact-token boost and the near-copy fold;
- the query time must not grow.

**One row per passage:**

| Column | From |
|---|---|
| text, vector, section heading, position | `passages`, `retrieval` |
| source file, sha256, library id | the library and the catalogs' `Source` rows |
| standing: authority, record, reference, jason's page, evidence | `authority_order.Tier` and the catalog. Mail is indexed as `record` with a caveat; it has no standing of its own yet. |
| kind and shelf | `DocumentKind`, `DocumentCategory` |
| period, in force from and to | the reading's dates; the statute's history |
| subject, party, place | the applicability facts (sections 1 and 3) |
| confidential, and who may see it | each source's rule rows, by file. The library's flag is OR-ed across copies, and `index_sources.library_holds` carries it to the same bytes in any other catalog. |
| generated | a jason page, never quoted as authority |

**At question time:**
- **Scope.** A caller passes facets (`passage_search(..., standing=, kind=, subject=, as_of=)`).
- **Self-query.** jason may draw the facets out of the question itself ("the 2023 sprinkler reports"), shown to the person as the filter it used.
- **Applicability.** A passage whose applicability is "does not apply" for the facts in hand is dropped. An "undetermined" one is kept and flagged with the missing fact.
- **Confidentiality.** A confidential row is filtered by the caller's role, the way the MCP tools hold confidential files back now.
- **Collections.** A named scope with a context (`document_collections`): the pack ranks it as its own tier, and a confidential one only for a board audience.

**Context headers.** Before a passage is embedded and indexed, jason prepends a short header of where it sits: the document, section, standing, date, and what it applies to. This follows Anthropic's [contextual retrieval](https://anthropic.com/news/contextual-retrieval): contextual embeddings cut retrieval failures by 35%, 49% with keyword search, and 67% with reranking. The header is built from jason's own records, not written by a model. That makes it cheap, repeatable, and the same on every run. It is measured on the gold set before it is kept.

## 7. Companion pages

jason writes pages for what the documents do not say themselves, and indexes them beside the documents with `generated` set:

| Page | Built from |
|---|---|
| One page a subject: what governs it, who does the work, how often, where the records are | obligations, the deliverable rules, the filing map, the subject's reference page |
| What applies: for a subject, the provisions that apply to the association's facts, those that do not and why, and those undetermined with the question that settles each | the evaluator (section 2) |
| One page a vendor or system: the contract, its duties and deliverables, licenses, invoices, open deficiencies, board items | contract terms, obligations, vendor files, board items |

The rules for these pages:
- **A page is a summary and says so.** It carries a header saying it is generated, and an answer that uses it points to the record it summarizes. A page is never quoted as the rule ("Only stored words").
- **Pages are rebuilt, never edited.** Each is regenerated from the stores when they change.
- **Private facts stay private.** A page that names owners or parties gets the confidential flag.

## 8. The stack

Today, two programs drive the one GPU: jason and AnythingLLM Desktop. jason's calls hold the GPU lock and run `preflight`. AnythingLLM's calls do neither: it loads its chat model whenever someone chats, at a window it keeps in its own settings file. `jason local-ai` can only warn when the two swap each other out.

**The proposal: jason makes every model call.** One lock then covers them all, and loading and unloading become jason's decision through Ollama's `keep_alive` and `/api/ps`:
- load the reader for a batch;
- free it before an embedding run;
- keep the chat model warm only while a person is asking.

**No model router.** Tools such as llama-swap add a process that Ollama's own controls already make unnecessary.

**What AnythingLLM still does, and where each job goes:**

| Job | Goes to |
|---|---|
| Retrieval | jason's index (section 6) |
| Catalogs | the `Catalog` and `Source` rows in `anythingllm_sync` stay as the definition of what is indexed and at what standing. Only the destination changes: rows in the index instead of uploads. |
| A chat window | the console's Ask, or any MCP client with `jason-mcp` |
| Hosting `jason-mcp`'s tools for a local model | any MCP client |
| OCR | already jason's; the `anythingllm-collector` engine goes when the app does |
| A one-step install | `pip install -e .` and Ollama. This is the real cost of leaving. |

**Not a swap for another app.** Open WebUI and LibreChat bring their own vector store, model settings, and server, which are the same costs as AnythingLLM.

## 9. Order of work

1. **Done:** the measurement (section 5) and `scripts/eval_anythingllm.py`.
2. **The applicability module.** Done October 4, 2026: `jason.community.applicability`.
   - Facets as closed sets, reusing `DocumentKind`.
   - The condition language (`Is`, `In`, `AtLeast`, `Below`, `InForce`, `AllOf`, `AnyOf`, `Not`, `Except`), with `describe()` and a JSON form.
   - `evaluate` in three answers by Kleene logic. Each verdict names its deciding facts and their sources, the facts missing, and the sources that disagree; a disagreement is undetermined, never a pick.
   - `Community.applicability_facts()` is empty by default. No row is converted yet.
3. **The first profile fact: systems.** Done October 4, 2026: `jason.community.life_safety`.
   - `LifeSafetySystem` and `Community.life_safety_systems()`, empty by default. A standard is entered only with the record that states it. Two records that differ are both tested, and jason picks neither.
   - `Obligation.applies` (default: always). `life_safety.applicable(community)` asks each obligation of each system and returns the three groups. An undetermined answer is a question, and `jason applies` prints them.
   - The fire-protection deliverable rules each carry `applies`: a water-based system, and the vendor's kinds of work as each provision says. The contract reader still decides in its own code (step 7).
   - `jason inspections` (`jason.tasks.inspections`) uses the three groups for completeness. For each system, the obligations that apply get periods and the records on file in each. Those that do not apply are listed with the deciding fact, so nothing is expected. The record-keeping provisions are `RecordRule` rows, recited from the shelf, and a provision the shelf does not print is said to be missing.
   - Still to do: file the questions as intake questions; convert the other rows (elevated elements, the notice catalog, filing rules).
4. **The index.** First part built October 4, 2026: `jason.community.passage_index`, `jason index`. Its engine is SQLite with the vectors as blobs (no new dependency), ranked by `retrieval`'s own functions.
   - Built:
     - the records, insurance, authorities, and reference sources, 6,770 passages;
     - the catalog, standing, kind, confidential, and generated columns;
     - `passage_search` reads from it.
   - The gold set holds: 0.89 recall@5 scoped to the gold folders, the same as cutting them, and 0.88 over the whole index.
   - `context_pack`: the governing-documents tier reads the index (same sources as before, about 10 times faster). The law tier waits for a comparison on the law's gold set; the records tier waits for the library source.
   - Sources added October 4, 2026:
     - the agency publications by what each is (`PublicationText`): a regulation's adopted text as authority, guidance as reference, a compilation not at all. The Title 19 fire regulations and forms are now searchable.
     - the `library`, `mail`, `reports`, and `docs` catalogs (`jason.tasks.index_sources`), each file with its own confidential flag from rule rows. `jason index --plan` lists the counts before a build.
   - The law pages' description passage is left out (the law questions' MRR@10 0.71 to 0.75).
   - The law tier of `context_pack` was compared on the law's gold set: sections whole 0.98 recall@5, the index's passages 0.96. It stays on sections whole.
   - Still to do:
     - the records tier of `context_pack` reading the `library` catalog;
     - the applicability columns;
   - Gold questions for the law: done (`data/retrieval/gold-law.json`, 50 questions, every phrase checked against the file).
     - Scoped to the authorities, hybrid 0.96 recall@5.
     - Over the whole index, 0.86. The paraphrase questions lose most, probably to governing-document passages on the same subjects; that is unchecked.
     - Each statute file's first passage is metadata only (title, source, why jason holds it) and competes with the operative text. It is the next thing to fix and measure.
5. **Context headers.** Measured October 4, 2026, and not kept for the law's pages. A line of the chapter path, why the page is held, and the standing and kind moved one question either way on each gold set (`data/retrieval/runs/2026-10-04-context-headers.json`). The index can carry a context line per file, and the publications use one for their title, since their text has no headings.
6. **Companion pages,** starting with the fire and life safety subject, whose sources are gathered.
7. **The contract reader's gate and term scopes.** In the contracts session's code, once it agrees to the interface.
8. **Retiring AnythingLLM.** Done October 4, 2026.
   - **Snapshot first:** every workspace's document list was saved (`data/anythingllm/snapshots/20261004-125545.json`).
   - **`document_search`** replaces `passage_search` in the board profile, which still has thirty-eight tools. It searches the passage index and returns passages with their standing and caveats, with no chat model.
   - **Case files:** each legal case's fetched file is a confidential `case-<key>` catalog (standing `evidence`) in `jason index --build`: its transcripts, and the text extract beside each PDF (`jason cases --extract-text`). An extract's context line names the source file and how it was read (text layer, OCR, or a vision reading). Held-back records are never extracted.
   - **Removed:** `jason anythingllm`, `anythingllm_query`, `anythingllm_status`, the catalog sync, the collector OCR engine, the app checks in `jason local-ai`, and the `anythingllm_*` settings.

## Open questions

- **Who asks, and where.** Settled: no person uses AnythingLLM. The board's questions reach jason through MCP clients and, later, the console's Ask.
- **Engine and footprint.** LanceDB or sqlite-vec, settled by the gold set and by the index's size on disk.
- **The gold set's reach.** Questions for the mail and vendor-records catalogs, which it does not cover today. The law has its set (step 4).
- **Undetermined answers.** Where they go: the intake questions, the canvas, or both, by facet.
