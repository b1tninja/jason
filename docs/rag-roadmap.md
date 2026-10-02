# jason RAG roadmap: document models, kinds, and retrieval contexts

## What exists now

- **Models on this machine.** The RTX 5090 runs one chat model through Ollama: qwen3.6:27b Q4_K_M with a 65,536-token window. It serves chat, vision OCR (`OllamaVisionOcr`), the classifier and the scan reader. The embedder is qwen3-embedding:8b. Every model request holds the GPU lock (`jason.locks`) and runs `jason.local_ai.preflight` first. Commit charge is tight. `locks.hold` is re-entrant only within one thread and one process.
- **Readers.** The `DocumentModel` registry in `jason.community.document_models` uses rule readers only. They do no model work and run on the CPU. `jason models` writes `data/documents/readings.json`: 610 readings, 557 with fields and 934 findings, of which 629 carry `Finding.authority`. `jason.tasks.drive_minutes` also writes this file and adds 36 `drive-<id>` minutes rows. Each run overwrites the file and keeps no diff. Some rule regexes fail on the vision layer's ` | ` table rows (see "Layout fixtures" under Next).
- **Question sets.** `question_sets.QUESTION_SETS` covers four kinds: minutes, insurance_policy, proposal and invoice. `model_questions` sends `text[:60_000]` and checks the answers with `questions.judge` and `grounded`. Each run overwrites `questions-<kind>.json`.
- **Library.** `data/library/library.db` holds 689 rows, and 687 of them were classified by a name rule. `tasks.library.distinct` folds copies by sha256 first. `text_for` puts the vision layer first. There are 87 `.vision.txt` layers. `invoices.readable()` already flags text with control characters. `data/readings` still holds 4 scan readings from qwen3.5:9b. `read_image_only` does not refresh them unless it gets `refresh=True`.
- **Retrieval.** The pieces are `passages`, `retrieval.keyword_exact`, `hybrid` and `VectorCache` (1,953 vectors cached). `manager_review` defaults to hybrid. `scripts/eval_retrieval.py` scores against `data/retrieval/gold.json`, which has 24 questions. Its `kind` field means exact or paraphrase, not document kind. No dense or hybrid row has been recorded on gold. BM25 is recomputed over the whole corpus on every query, and `dense_rank` loads one `.npy` per passage on every query.
- **Context pack.** `context_pack.assemble` builds the S, G, R, F and D tiers. R takes the latest `RECORD_FILES=3` files per kind, by period. `prompts.verify` checks quotes.
- **AnythingLLM.**
  - Catalogs: authorities, association-records, insurance, mail, jason-pages, and one `case-<key>` per legal case, plus the shared association workspace. The legacy "My Workspace" still holds 115 custom-documents.
  - `anythingllm.Source` keeps only title, text and score. `SHELF_OF_FOLDER` has no `insurance` entry.
  - Only `anythingllm_admin.reembed` takes the GPU lock.
  - jason-pages includes `reports/property-history/*.md` (104 pages) with no filter.
  - The insurance catalog uploads `data/insurance/documents/*.pdf` (50 files) as a whole folder.
  - Sources do not recurse, and they match `*.pdf` or `*.md` only.
- **Law and outlines.** `export_authorities` writes 497 sections across 76 pages, plus a manifest with no per-section digest. `board_packet.statute_excerpt` trims to a subdivision. `tasks.outlines.resolve` and `outlines/references.json` already resolve section references. The reference model has read only 23% of passages; ccrs (394) and bylaws (292) are unread. 13 outlines have zero sections.
- **Scoring against known facts.** `extraction.cases()` and the `extraction_scorecard` tool cover 8 recorded-instrument cases. Some fields are also checked against other stores:
  - bank statements against PayHOA reconciliations (77/77);
  - treasurer reports against `balance-sheets.json`;
  - invoices against payments in `invoice-review`;
  - deed numbers against the `ownership.db` chain.
- **Proposed pieces that do not exist yet.** `KindContext` (P8), `links.json` (P18), `KindIndex` (P13), `FieldStatus` and `probes.json` (P2), gold (P5), `law_for` (P22), `StatuteTerm` (P23) and `GoverningTerm` (P24). Nothing under "Do first" depends on any of them.

## Do first

### 1. Stop the confidential library leak into the shared workspace (P8, the small fix only)

- **Problem.**
  - `anythingllm_sync.library_items` checks each row's `confidential` flag on its own, but `distinct()` treats a file as confidential when any copy of it is.
  - As a result, 8 treasurer reports are in today's association-records upload list, which is shared into the association workspace. Each has one copy under `Confidential/` and a byte-identical copy under Email Attachments.
  - The cause is the folder (`CONFIDENTIAL_FOLDERS`), not the kind.
  - Treasurer reports also carry PayHOA's aging section. Of the 46 distinct treasurer reports in the upload list, 22 contain both a unit street address and aging or past-due words. This was counted with a loose text match, so a person should confirm it.
- **Mechanism.**
  - `library_items` iterates `distinct(load(root))`. A sha group whose copies disagree on confidentiality goes into a new `SyncReport` list and is not uploaded.
  - Add a stale-removal step for library items, modeled on the mail catalog's `_mail_id` pruning, so that copies already uploaded leave association-records and the association workspace.
  - Add `insurance` to `SHELF_OF_FOLDER`.
  - Keep the exclusion of unclassified (`""`) rows explicit.
- **First step.** Replay `library_items` offline. Then diff the list by kind, before and after the change.
- **Measure.**
  - Confidential distinct copies in the upload list go from 8 to 0.
  - The list diff shows only those 8.
  - Insurance sources labelled `unfiled` go to 0.
- **Conditions.**
  - A person decides which classification of the 8 is correct before anything is removed or re-uploaded.
  - Stale removal deletes documents from a workspace. AGENTS.md and the docs say jason deletes no workspace or document and never replaces association records. This step therefore needs an explicit exception that a person approves. Take a snapshot of the workspace's document list before any removal, and add a check that the removal never touches a `case-<key>` catalog.
  - Update `tests/test_library.py`.
  - Decide treasurer_report sharing explicitly: BOARD, or shared once the aging section is stripped. Decide the same for legal_correspondence (3 in the list) and settlement (1). A person sets these rows; the code does not infer them.
  - Update the stale docs in the same change:
    - `document-tools.md` still says MiniLM/LanceDB, three catalogs and nineteen tools.
    - `SKILLS.md:150` says three catalogs.
    - The classifier `keep_alive` is documented as 1 minute, but the code uses 5m.
    - The `anythingllm_query` docstring and AGENTS.md omit the insurance catalog.
  - Longer term, move `CONFIDENTIAL_FOLDERS` into the profile (`mystique/`) as a confidential flag on `LibraryFolder` rows.

### 2. Owner data and claim papers in shared catalogs (no P number; needs a person's decision)

- **Problem.**
  - jason-pages includes `Source(Root.DATA, "reports/property-history", "*.md")` (`anythingllm_sync.py:130`). Its 104 pages carry who held each unit, PayHOA members, liens and notices, and taxes. They go into the shared association workspace with no filter. The library treats owner_history and membership_list as confidential kinds, so this exposure is larger than item 1's.
  - The insurance catalog uploads `data/insurance/documents/*.pdf` with no confidentiality filter. No file name among the 50 looks like a claim paper, but nobody has checked the contents against `CONFIDENTIAL_KINDS`.
- **Mechanism.** A person decides one of two things:
  - property-history stays out of the shared workspace, which means a BOARD-only catalog or no catalog;
  - or it is shared only after the owner, member and lien sections are stripped.

  For insurance, join each PDF to its library row by sha256 and exclude any confidential kind. The same stale-removal exception, snapshot and case-catalog check from item 1 apply.
- **First step.** Run an offline list of jason-pages and insurance uploads, with counts by source and by matched library kind.
- **Measure.**
  - property-history pages in the association workspace: 0, or exactly the stripped pages the person approved.
  - Insurance PDFs that match a confidential kind: 0 uploaded.
- **Conditions.** The code infers nothing here. This item does not depend on P8.

### 3. Keep history before it is overwritten (P6 step 1, P4 steps 1, 2 and 4, P25 steps 1 and 2)

- **Problem.** Three stores lose their prior state on every run:
  - `readings.json` is overwritten, and `data/` is not in git.
  - `questions-<kind>.json` is overwritten. The attachment runs the docs cite (27 proposals, 40 invoices) can no longer be reproduced.
  - `export_authorities` overwrites the statute pages. The 2025 text disappears at the next export, and the 2026 session's changes arrive with the next re-export.
- **Mechanism.**
  - **Readings.**
    - Add a reusable `compare(old, new)` keyed by `(id, field)`. It reports what was lost, changed and gained, and what became complete or incomplete.
    - Call it from every writer: `document_models.run`, `drive_minutes.read` and `drive_minutes.reread`.
    - Hold `Resource.STORE` around each read-modify-write.
    - Keep `readings.prev.json` and write `runs/<readAt with colons replaced>.json`.
    - On each reading, store a digest of the input text and the layer used (old, vision partial or vision full). A change can then be traced to a rule edit or to new text.
    - Make this report-only. Do not add an `--accept` gate.
  - **Questions.**
    - Store the raw answer beside each verdict: stated, value, and the full quote. Today the quote is cut at 200 characters.
    - Keep every run under `questions/<kind>/<askedAt>.json`.
    - Add `model_questions.rejudge`, which runs offline and needs no model.
    - Leave `questions-<kind>.json` in its current shape, because `paid_vs_approved`, `cross_checks` and `minutes_draft` read it.
  - **Authorities.**
    - Add a per-section sha256, a history line and subdivision markers to the manifest.
    - Hash the body as `context_pack.law_corpus` splits it, not the rendered page, so the session header does not cause diffs.
    - Copy replaced text to `data/authorities/history/<citation>/<digest>.md` and write `changes.json`.
    - The 10 CCR pages carry `session: "DRE publication"`, so they need the digest, not the session label.
- **First step.** Ship the authorities digest and history before the next `jason export-authorities` run. That is the only part whose loss cannot be undone.
- **Measure.**
  - Fields lost, changed and gained per kind on each run.
  - Rejudge flips against the stored answers. The count today is 23 to 25, depending on method. One reconstruction gives 25: 21 insurance `mailing_address`, 1 proposal license, 2 minutes `decision_topics` and 1 minutes quorum. The map gives 23, with 1 `decision_topics` and no quorum. Pin the method in the first `rejudge` run and report that run's number.
  - Changed sections per export, with a fixture that compares the CIV 5855 page at Stats. 2024 against Stats. 2025, Ch. 22.
- **Conditions.**
  - Re-ask the four question kinds once on the GPU (about 45 minutes), so that history starts from exact raw answers instead of reconstructed ones. Run it as a queued `jobs` job, not ad hoc, so it does not collide with OCR or AnythingLLM on the one resident model.
  - Add a unit test proving that rejudge never converts cents twice and never re-counts lists.
  - Leave out of the regression counts any finding that depends on today's date or on another store, such as `contracts_insurance_package`, which reads `readings.json` itself.
  - Hold back confidential rows' values in `runs/*.json`; record field names and value hashes only. Apply the same rule to the stored raw answers and quotes in `questions/<kind>/*.json`, and keep the MCP `document_models` tool from serving them.
  - Set a retention rule for `runs/` and `questions/` (for example, keep the last N runs plus one per month). Back them up together with `data/authorities/history`, because `data/` is not in git.
  - Every diff is a lead. Nothing is re-run and nothing is pinned.
  - Run the diff outside the GPU lane. `jobs` currently classes every `models` command as GPU (`jobs.py:70`).

### 4. Count documents, not files: identity fields per model (P16)

- **Problem.** 21 of the 77 bank statements are second copies of a statement already read: same account, period end and ending balance, but different bytes. They carry 28 duplicated findings into the coverage and finding tallies. In 19 of the 21 groups both copies have the same file name, so `distinct()` misses them only because sha256 takes precedence.
- **Mechanism.**
  - Add `identity: ClassVar[tuple[str, ...]]` beside `DocumentModel.required`. Start with:
    - `BankStatement`: account_last4, period_end and ending_cents.
    - The NFIP flood declarations reader: policy number and term start, plus the building limit or premium.
    - Minutes: meeting date and type, plus draft or approved, so that a draft and its approved minutes stay separate.
    - Treasurer report: period and generated.
  - Join readings in `community/copies.py` through `group()`, with a new `JoinRule.SAME_IDENTITY`. Map readings into the existing join instead of writing a second union-find.
  - `document_models.run` writes `copyOf` on secondary readings and keeps every row.
  - Choose the primary by completeness (complete first, then fewest missing fields), then by library path joined through `id`. Do not use `COPY_PRIORITY`, because nearly every reading comes from one channel. Drive minutes need their own tie-break rule.
- **First step.** Bank statements only. `coverage()` and the MCP `document_models` tool report logical documents next to file counts and count each finding once.
- **Measure.** 77 readings become 56 logical documents, and the 28 duplicated findings are removed.
- **Conditions.**
  - Fold only when every identity field is filled and equal. The fields must include an amount, and an OCR'd number alone is never enough: a misread policy or account number can match falsely.
  - When copies match on identity but disagree on a non-identity amount, report the pair and do not fold it.
  - Add tests that two months of one account never join, and that two buildings' flood declarations never join.
  - Show the secondary reading, with its own findings, under the primary.
  - OR confidentiality across the group. List every reading whose effective confidentiality changes, so a person sees what `context_pack` stops showing to member tasks.
  - Do not depend on P8.
  - Defer the embedder-based "possible copy" leads.
  - Measure the retrieval and AnythingLLM effects separately, by extending the existing `SAME_TEXT` and title-dedup helpers. Do this only if a gold run shows copies crowding the top results.

### 5. Show the law beside each finding (P22)

- **Problem.** 629 findings cite an authority as free text, in 132 distinct strings. No output shows the words of the law. Citations to the Bylaws and the Declaration of Annexation never reach the outline section that holds their text.
- **Mechanism.**
  - Put one citation parser, `CITATION_ALIASES` (R&T to RTC, Corp. Code to CORP, CC&R to ccrs) and a `LawCite` record in `jason.community` (references or authorities).
  - Build them on `references.extract` and `statute_key`, which already cover EVID and VEH and mark prior Davis-Stirling numbering.
  - Retire `board_packet._CITE` and `export_authorities._CITE` in the same change.
  - Move `statute_excerpt` into community as well.
  - Write `law_for(authority, reading)`.
    - It resolves statutes through `authority_text`, and Bylaws and annexation sections through `tasks.outlines.resolve` and `aliases_of`.
    - It returns one of: resolved, parent only, pointer, or unresolved. It never returns a nearest match.
    - It compares the excerpt's session and operative date with the document's date. When the text on disk postdates the document, or the history shows an amendment between the two dates, it shows "text on disk may differ from the law at the document's date." It never presents current text as the text then in force.
  - `summary()` and the MCP tool add a law list, deduplicated per response, with each excerpt capped at 1,800 characters.
  - `follow_citations` also scans F-tier facts.
- **First step.** Two deliverables:
  - `coverage()` columns for resolved, pointer and unresolved, reported separately for compound strings such as "Bylaws 10.10, CIV 4926(a)(3)".
  - An AST test that walks every `Finding` authority literal in the model sources and lists the unparsed ones, without loosening any match.
- **Measure.**
  - 566 of 629 resolve to statute text today. That count includes 15 compound Bylaws strings whose Bylaws half does not resolve.
  - Bylaws-cited findings: 40 (20 cite Bylaws 10.10 alone, 15 cite it with a statute, 5 cite Bylaws 7.10). Annexation-cited findings: 9. Today none of these 49 shows section text.
  - Target: every authority resolves to text or to a named pointer.
- **Conditions.**
  - Add `Authority` or pointer rows for 44 CFR 61.6, Cal. Fire Code 907.8, CORP 7341, 7511 and 8210, and RTC 11911, each with a fitting `Basis`, after a person reviews them.
  - Fetch the CORP and RTC sections in a separate, explicit `export-authorities` run. `law_for` reads only what is on disk.
  - Label outline text "Docs export, not the recorded copy." Show the session and history line beside every statute excerpt. This depends on item 3's authorities history for the date check.
  - Show nothing for outlines with zero sections. There are 13, including the 2nd and 3rd amendments and annexation phase 8.
  - Bylaws and annexation pointers resolve only through the outlines, and the reference model has not read the bylaws or ccrs passages. "Resolved" for these means only that the outline has the section, not that its text was checked against the recorded copy.
  - Keep a confidential file's finding message held back. Show only the public statute text.

### 6. Keep AnythingLLM's chunk metadata, and run it under a scoped lock (P11 step 1)

- **Problem.**
  - In the vector-cache JSON, all 11,578 cached chunks store `description` in their metadata, and 5,460 of them carry the library kind, period and Civil Code 5200 record.
  - `buildHeaderMeta` never embeds the description. It is metadata only, so surfacing it helps labelling, not retrieval or the chat model's context.
  - `Source` drops this metadata.
  - `ask()`'s fallback search uses `top_n=4` against a workspace `topN` of 12.
  - `sync_catalogs`, `ask()` and `anythingllm_query` embed and chat outside `hold(Resource.GPU)`.
- **Mechanism.**
  - Add `Source.description` and `Source.published`. `AnythingLLM.search` reads only the metadata title today (`community/anythingllm.py:185`), and `query` reads only title and text (line 176), so both readers change.
  - `ask()` returns kind, period and records parsed from the description.
  - Pass the `WORKSPACE_SETTINGS` `topN` to the fallback.
  - Locking:
    - Use a lock key for AnythingLLM that is separate from `Resource.GPU`, or hold `Resource.GPU` per request (one upload batch, one chat) with a timeout, never across a whole sync.
    - The jason-mcp server does not take the GPU lock while it serves an AnythingLLM agent call. Otherwise a chat that holds the lock and calls the board profile's `passage_search(mode='hybrid')` waits on itself until the 600 s `ResourceBusy` timeout.
    - Run `preflight` once per sync, naming the embedder. `reembed` does not call it today.
- **First step.** Under the lock, confirm on one live chat response and one live `vector-search` response that sources carry `description`. So far it has been seen only in the vector-cache files, never in an API response.
- **Measure.**
  - Share of `ask()` sources with a kind or shelf label. This is a labelling measure, not a retrieval one.
  - AnythingLLM calls made outside the lock: should reach 0.
  - Lock waits and `ResourceBusy` raised by jason-mcp during AnythingLLM chats: should be 0.
- **Conditions.**
  - Take the shelf from `authority_order.Tier` rather than adding a free-string `Catalog.shelf`.
  - No re-embedding in this step.
  - A queued GPU job (such as item 3's re-ask) serializes interactive AnythingLLM chat behind it. Say so in the job's notice.
  - Do not gate this on P8, P12 or P25.

## Next

**Layout fixtures for rule readers (no P number).**
- Several rule patterns fail on the vision layer's ` | ` rows:
  - `_CLAIM_NO`;
  - Chase's `_SUMMARY_ROW`;
  - `'Beginning Balance\s*\n'`.
- `amount_after` and `date_after` pick the wrong column in tables with a header row.
- `incidents.enrich_claim` uses parse acceptance as its classifier, so a parse failure becomes a classification miss.
- Item 3's diff catches a regression only after a run has overwritten the readings.

Add vision-layout fixtures (pipe tables and header-row tables) to the 214 model tests for each affected reader. Then add one pipe-table adapter in community that the readers share. Run the fixtures before any vision re-read. This does not depend on P15.

**Thin-parse repair for AnythingLLM (P11 step 2, narrowed).**
- **The gap.** 25 association-records documents in AnythingLLM's store have fewer than 50 words, while jason holds between 0.5k and 56k characters for each. They include the operating rules (21 words stored), a CC&R amendment (1 word) and 8 DRE public reports.
- **The fix.** For these documents only, upload a jason text page titled `<kind> <period> — <name> [library <id>]`.
  - The page names the PDF as the record and states its text source (vision or Tesseract; OCR can misread).
  - Put these pages on their own shelf, "jason's reading of a record", not the record shelf. Keep the record PDF beside the page, so an answer can point to the record and is not quoting OCR text as if it were the record.
  - Keep the PDF everywhere jason's text is shorter: for 48 documents, AnythingLLM's own parse holds more.
- **Dedup.** The DRE reports, operating rules and amendment arrive from the site-docs Drive mirror, which wins today's title dedup. A sha256 rule must therefore add jason's page next to the mirror PDF when the stored parse is thin.
- **Absent documents.** Also cover the 12 governing documents that exist only as Google Doc exports and never reach association-records: the 3rd amendment, the ALPR policy, the fiscal-management resolution and 9 special resolutions. The Sources match `*.pdf`, and `mirror_index` skips `.md`.
- **Safeguards.**
  - Take a snapshot first and upload before removing. The item 1 exception applies to any removal.
  - Leave case catalogs untouched.
  - Approve this as an explicit catalog flag, not `generated=True`.
- **Scorer first.** Write a small `vector-search` scorer over gold before retitling all of the ~214 library documents or splitting the 497 statute sections into separate pages.

**Retrieval baseline on gold (no P number).** Record keyword, dense and hybrid rows from `eval_retrieval.py` on the 24 gold questions, run as a queued GPU job. `manager_review` defaults to hybrid, which is unmeasured. Record the per-query time of BM25 and `dense_rank` as well. This is the baseline for the R-tier change, for P12 and for the thin-parse scorer.

**Cross-catalog duplicates (no P number).**
- In the association workspace, duplicates use up slots in the topN of 12:
  - `re25.pdf` is in both authorities and association-records;
  - 23 PDFs are in both association-records and insurance;
  - insurance also holds duplicates within itself.
- Pick one catalog per sha256 by rule: authorities for law, insurance for policies.
- Retire the legacy "My Workspace" (115 custom-documents) once a person confirms that nothing reads it.
- The item 1 snapshot and exception apply.

**Agenda fallback for minutes (P20, the minutes part only).**
- **The gap.** `MinutesModel._against_agenda` reads only the library. 26 minutes readings and 2 resolution readings carry `no-agenda-on-file`. Yet the meeting catalog has agendas for about 21 of those dates, and 17 of them have text on disk (`agenda-files`, `agenda-docs`).
- **The fix.** Fall back through the loaders that `cross_checks.py` already uses.
  - Prefer the posted copy over a draft, and name the source in the finding.
  - Report "agenda unread" when `AgendaModel` cannot parse the agenda.
- **Check.** Pin the before and after counts in a fixture; about 11 are expected to remain.
- **Scope.**
  - Do not wait for P18.
  - Drop the parent-parcel placement row.
  - Ship `policy-number-unknown` (17 of 72 mail items) as a separate small lead row that reuses the `number-not-on-sheet` logic.

**Statutory terms table (P23).**
- **The gap.** About 48 to 52 constants with statute comments hold real deadlines. Examples:
  - CIV 5855(a)=10 and 5855(f)=14, in four modules each;
  - CIV 4920(a)=4, in four places;
  - a literal `timedelta(days=4)` in `meeting_agenda.py:223`.
- **The table.** Add `TERMS` in `jason.community`, beside `authorities.py`, with aliases for the old names.
  - Keep the two different `NOTICE_DAYS` (5855(a) and 4920(a)) apart.
  - Keep the two 30-day ADR terms (5935(a)(3) and 5935(c)) as separate keys.
  - Model compound terms such as 5650(b)(2) ("greater of") as a small rule shape.
- **Checks.** Add an offline pytest that checks each value against `data/authorities`.
- **Dated terms.** Add `prior=` only to 5855(f), with the operative date pinned by a person from the chaptered act. Pass the document date in `legal_letters` and `correspondence`. Today a decision letter written under the old 15-day rule is flagged as a problem.
- **Mismatches.** A "value differs" verdict must make `zoom.plan_hearing` and `board_calendar` refuse or warn loudly, never switch a deadline silently.
- **Scope.**
  - CORP 7341 and 7511 stay "not on shelf" until they are exported.
  - Item 5's date check uses the same operative dates.
  - Do this alongside the next statute-year update.

**Field accuracy without person time first (P5, cross-record half).** Generalize `extraction.Scorecard` and `FieldScore`, without adding a third scorecard, to score readings against records jason already holds:
- grant_deed number, recorded date and APN against the `ownership.db` chain (recorded date agrees 119/119; APN agrees 87 and differs 12);
- bank_statement against `reconciliations.json`;
- treasurer_report against `balance-sheets.json`;
- invoices against `invoice-review` payments;
- policy numbers against `mystique/insurance.py`.

Report these as "agrees with the record", never as gold.

Spend person-checked gold only on fields with no second record. Keep it in `data/`, under the STORE lock, never served by the MCP tools. The fields are:
- minutes and agenda meeting type, roll call, quorum and executive session;
- notice dates;
- policy and election-rule adoption;
- deed consideration and transfer tax.

Aim for 10 to 15 files per kind. Seed the review from disagreements, leaving out the YES_NO answers where both sides are silent. Key rows by a content hash that also covers Drive minutes. Define the status enum here rather than waiting for P2.

**Identifier checks against pinned values (replaces the dropped Tesseract cross-check from P7).**
- Check OCR'd identifiers against pinned values and the public index:
  - recording numbers and APNs against `ownership.db` and the recorder index cache;
  - policy numbers against `mystique/insurance.py`.
- Report a mismatch as a lead.
- Use the Tesseract versus vision comparison that `document-tools.md` names only where no pinned value exists, and treat Tesseract as the weaker witness.

**Applicability and agreement reporting (P4 steps 3 and 5).**
- **The gap.** 151 insurance gaps exist. 126 of them come from general liability, umbrella, D&O, crime and computer-fraud questions (six questions) asked of the 21 flood declarations. One more is the master package's umbrella gap. Whether that one is not-applicable is a person's call, because the umbrella is a separate policy.
- **The fix.**
  - Express applicability as a field predicate in the existing `Question.field` style, not as reader-name strings.
  - `NOT_APPLICABLE` replaces only `GAP`.
  - A reading with no reader counts as applicable to every question.
- **Agreement figures.** Insurance agreement excluding not-applicable answers:
  - 72.6% (212/292) with 126 not-applicable, or 72.9% (212/291) with 127;
  - after the `mailing_address` rejudge, 79.8% or 80.1%.
- **What the figure rests on.** Say plainly that it rests on flood pages. The master package has 17 ungrounded answers, and 5 of them fall on the GL, D&O, crime and computer-fraud questions. Those 5 are applicable to the package and stay in the denominator.
- **Where it goes.** Put agreement in the MCP `document_models` tool, not on the jason-pages shelf.
- **Checks.** Make sure `paid_vs_approved` and `cross_checks` treat the new verdict the way they treat a gap.
- **Deferred.** The lead queue, the regex miner and `FieldFormat`.

**Governing-document terms (P24, after P23).**
- A person pins about six to ten values as `GoverningTerm` rows in the profile (`mystique/`): delinquency period, late charge, interest, review requirement, insurance minimums and meeting notice.
- Sources: the CC&Rs (6.11, 6.12, 8.1, 8.2), the bylaws (7.6, 8.5, 9.7) and the collection policy outline (section 6, Late Charges/Interest).
- Take the values for amended sections from the recorded amendments, since those outlines are empty.
- The existing "Cites:" lines in the outlines are a cheaper lead than a BM25 ranker.
- Checks use `effective_term`, and findings stay at CHECK until a value is pinned.
- State the filter that yields the "42 deferring findings."

**Findings in the pack (P9, pack side only).**
- Inside `context_pack.assemble`, render each R file's current findings and a few key fields at pack time, from `readings.json`. Write no `cards/` directory and add no catalog. Date-relative findings then stay current.
- `verify` counts a quote grounded only in a reading as `readings`, not `grounded`.
- The base prompt must say that C is jason's reading, not the record.
- Place each block next to its R file; `_ordered` sorts by tier first.
- Use a per-kind field allowlist. It drops minutes `executive_*`, `others_present` and AI summaries, and the legal_correspondence and settlement fields.
- Measure on the six record-reading tasks (not trash-cans, which has no R sources): recall of named findings over several runs, counting any lead stated as a conclusion.

**R-tier baseline (P10, the part with no dependencies).**
- For small kinds, rank passages across all of a kind's files instead of the latest 3, and fuse that ranking with recency.
- Cap passages per file, and set a relevance floor for dense hits.
- Take the library period from the reading's date fields: all 22 insurance_policy rows and 9 of the 13 contracts have no period.
- Store the person-labelled expected-file lists beside `gold.json`.
- The test case is recall of the fire-testing contract.
- Measure per-query time and memory against the retrieval baseline. Ranking across a whole kind increases both BM25 recomputation and `.npy` loads. Cache the corpus index and the stacked vectors if the time grows.

**Cheap trust fixes for long files (P1, first stage).**
- Record `fullChars`, `prompt_eval_count`, `truncated` and the text's sha256 per file.
- When a file was cut, mark its gaps "not read" and emit no statutory lead for them.
- Skip files that fail `invoices.readable()` and list them for `vision_read`.
- Cache `embed_query`.
- Replace both 60k cut sites: `model_questions.ask_file` and `cross_checks.py:861`.
- Add excerpt selection only for a question set on a long kind. Start with reserve_study, for the 5570 disclosure, and annual_disclosure. Do this only after measuring a token-based cap and pinning gold by hand beyond character 60,000.

**Refresh stale model outputs (no P number).**
- Re-read the 4 qwen3.5:9b scan readings with `refresh=True` as one queued GPU job, with item 3's diff.
- Queue the reference model over the bylaws (292) and ccrs (394) passages before item 5 treats outline resolution as text that was read.
- List the outputs of each model by model name in `jason local-ai`, so stale ones show up.

**Classification diagnostics, CPU only (P13 and P17, first steps).**
- First rank the 312 `unruledFolders` in `holdings.json` by unclassified file count, and draft `KindRule paths=` rows.
- Run a phrase miner on the labelled members of the 20 kinds that have no content rule. A phrase qualifies when it appears in at least 80% of members and at most 2% of outsiders.
- Add the 7 missing `KIND_HINTS` lines by hand: loss_run, claim_letter, claim_payment, claim_authorization, claim_estimate, police_report and manager_case_report.
- Then add a TF-IDF leave-one-out vote to `jason library --score --neighbors` as a diagnostic, using numpy only.
  - scikit-learn is not installed.
  - The vote should not become a new `Method`.
  - Exclude identity copies once item 4 lands.
  - Keep the vote from gating incident evidence until its precision on incident text is measured.

**Lexical no-cue mark (P2, CPU part only).**
- Beside each gap verdict or `missing-<field>` finding, record "no cue in text" together with the text layer used. Name the status `NO_CUE`, not `ABSENT_IN_TEXT`.
- Fill grant-deed APNs from the `ownership.db` chain by recording number (all 9 are there).
- Run the existing minutes set over the 36 Drive minutes to cover the 8 `meeting_type` misses.

**Law-change impact (P25 step 4).**
- After item 3, add `law_impact(citation)` over what already exists:
  - `DUTIES.sections`;
  - `mystique/obligations`;
  - the `board_items` authority;
  - `Question.why` (`Question` has no `requires`);
  - the `references.json` rows with status "law on disk" (131);
  - the finding citations.
- Add the `StatuteTerm` and `GoverningTerm` joins when P23 and P24 land.
- Settle the method for counting citations first: 151 claimed, against a regex count of 78.
- Separate a history change that only renumbers from a change to the text.

## Not now

- **Stores with no RAG path, kept out on purpose for now.** These are outside retrieval and AnythingLLM. Each needs its own confidentiality rule before it joins:
  - incident text (2,367 `.txt` plus 290 `.ocr.txt`). The text carries no confidentiality marker; confidentiality lives only in `drive/evidence.json`, and medical records are never read.
  - PayHOA attachment text (965 files);
  - the 36 Drive minutes and 63 agenda files;
  - Zoom transcripts (executive session and hearing text is held back);
  - developer-security text;
  - the outlines;
  - `docs/document-models/*.md`, which is missed because the jason-pages Source does not recurse.
- **P3, companion sources in the prompt.** Most minutes gaps are real absences: no adjournment times, and no "roll call" in any file. A statute block would mostly risk answers taken from the statute. Reprint detection and `COMPANION_ONLY` can ship alone later.
- **P7, OCR digit cross-check between engines.** None of the counted slips has the shape of a recorder or APN number, about 80% keep their length, and Tesseract is the weaker witness. Replaced by "Identifier checks against pinned values" under Next.
- **P15, layout families.** Its motivating scorecard predates the current format rows (21 of 26 rows now match 287 of 1,063 texts). Re-run `jason invoices` first. Its gate overlaps `invoices.readable()`. Vision-layout fixtures are covered under Next.
- **P18, entity link index.** It is measured by link rate, not precision. Ship the deed-to-building and mail-to-policy joins as rules in the existing tasks.
- **P19, entity cards.** Policy pages already exist (`data/insurance/pages`), and `meetings.md` has one section per meeting. The rest depends on P18.
- **P21, entity-scoped insurance questions.** `policies.json` already holds the non-flood limits from the rule readers, and `adoption_leads` already searches minutes for adoptions.
- **P12, kind workspaces.** Unproven until a `vector-search` baseline exists. Only its scorer, a prerequisite listed under Next, is worth building now.
- **P14, neighbor audit.** It found 6 leads in 397 files, 1 of them strong. Store verdicts on the existing `score()` misses list instead.
- **P8, the full 67-row `KindContext` table.** Items 1 and 2 cover the leaks. Build the table only with law-shaped defaults that a person reviews, and either fold in or drop the `KIND_TIERS` claim (`KIND_TIERS` maps 12 kinds).
- **P9, AnythingLLM readings catalog.** Defer until gold and an A/B test show that file chunks keep their recall@12. It also repeats the insurance pages.
- **P10, subjects and entity binding.** It depends on P8, P9 and P18. `--subject` and `TaskPrompt.subjects` already exist with another meaning.
- **P1, dense two-phase embedding and excerpt switching.** No gold exists for long kinds. The memory obstacle is unsettled (see Corrections). Measure it with the retrieval baseline before deciding.
- **P2, model probes.** There are about 15 fields with a cue present in all; cheaper fixes cover them.
- **P4, lead queue, regex miner and `FieldFormat`.** 2 invoices and 4 proposals are too few to mine rules from. Moving `INVOICE_FORMATS` into the profile (`mystique/`) is a separate cleanup.

## Corrections

**Pieces that do not exist**
- None of these exist: `KindContext`, `links.json`, `KindIndex`/`TfidfVectors`, `FieldStatus`/`probes.json`, gold for document fields, `law_for`, `StatuteTerm`, `GoverningTerm`, `mystique/entities.py`.
- Neither `Community` nor `Mystique` defines `question_sets()`. `model_questions` only probes for it with `getattr`, and a non-empty result replaces `QUESTION_SETS` entirely.
- No question set exists for contract, grant_deed, policy, bylaws or the financial kinds.

**Readings store**
- Rows are keyed by `id`: a library id, or `drive-<id>` for the 36 Drive minutes. They carry no sha256 and no library path.
- `drive_minutes` also writes `readings.json`.
- The stored layers have no page delimiters, so comparing page by page means re-extracting the PDF.
- `readAt` contains colons, which Windows does not allow in file names.

**Counts**
- grant_deed readings: 126, not 124.
- insurance_policy: 22, of which 21 are flood declarations.
- Not-applicable insurance gaps: 126 on flood declarations (21 files × 6 questions). The 127th gap is the master package's umbrella gap and is a person's call.
- Insurance agreement excluding not-applicable answers: 72.6% at 126, or 72.9% at 127. It is not 78%.
- Rejudge flips: 23 to 25 depending on the method, to be settled by the first `rejudge` run.
- Bylaws-cited findings: 40, not 25.
- `no-agenda-on-file`: 26 minutes plus 2 resolutions. Of the minutes dates, about 21 have a catalog agenda, and 17 have agenda text on disk.
- Statute constants: about 48 to 52.
- Library chunks in AnythingLLM: 5,460 carry the library description, not 3,300. This is cache metadata only, and it is never embedded.
- Treasurer reports in the upload list: 46 distinct. 22 contain a unit street address and aging or past-due words (a loose match).
- property-history pages in jason-pages: 104.

**Copies and sharing**
- `distinct()` already folds byte-identical copies. The bank-statement copies therefore differ in bytes, and most share a file name.
- `library_items` already dedupes by title. The Drive mirror wins that dedup, which is why the DRE reports arrive through site-docs.
- The library leak is 8 treasurer reports, not 9. It is caused by the folder, not the kind.
- The larger exposure is the 104 property-history pages in jason-pages (item 2).

**Law**
- `statute_excerpt` lives in `tasks.board_packet`.
- `board_packet._CITE` covers six codes. `references.extract` is the better base, and `tasks.outlines.resolve` already resolves section references.
- `pointers()` returns four authorities and has no rows for 44 CFR 61.6 or the fire code.
- 13 outlines have zero sections, including annexation phase 8 and both amendment outlines.
- `CitableDocument` rows are in `mystique/outlines.py`, not `mystique/community.py`.
- `Question` has no `requires`. Outline revision ids exist only in the stored JSON.

**Layer replay**
- Measured against what production actually reads (`text_for`), no fields are lost. condominium_plan stays at 3 complete, and complete grant_deed readings rise from 38 to 48.
- The reported "losses" came from reading the vision layer alone.

**Machine**
- The chat model and the embedder are meant to be resident together: about 27 GB of VRAM, with about 6 GB of commit left.
- `document-tools.md` records that the dense eval needed 9.7 GB, with only about 4.3 to 6 GB free while both were loaded. Whether the blocker was co-residence or preflight's cold-load margin is unmeasured; the retrieval baseline settles it.
- `reembed` takes the GPU lock but does not call `preflight`.
- `locks.hold` is re-entrant only within one thread and one process.
- scikit-learn is not installed.

**AnythingLLM API**
- `description` has been seen only in the vector-cache files. `search` reads only the metadata title, and `query` reads only title and text. No live response has yet been checked for it.

**Evaluation**
- In `gold.json`, `kind` means exact or paraphrase.
- `invoice-review.json` predates the current format rows.
- The trash-cans pack has no R sources.
- `ContextPack._ordered` sorts by tier first, so a GUIDANCE-tier source prints after all R and F sources.
- There is no AGENDA TaskPrompt row.
- Every called_to_order and adjourned time in the gap files is a heading time. Agenda headings contain those words, so word cues alone do not settle them.
- No dense or hybrid retrieval row has been recorded on gold.