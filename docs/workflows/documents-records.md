# Documents and records: taking a document, a folder, a checklist, or an association in, as durable runs

Status: **design**. This page is one family page of [../workflows-design.md](../workflows-design.md) and follows its section 5 template. Nothing here is built as a run: the store (`jason.workflows`, `data/workflows/`) does not exist yet (checked). What exists is the pieces this page maps onto steps: four standard operating procedures (`jason sop document-intake`, `ingest`, `onboard`, `careful-reading`), the record checklist and the splitter (both built, backend and screens), the key documents, the instrument graph, the onboarding session, and the members' records-request store.

Words used as the law and the documents use them. Statutes are recited from `data/authorities` (jason's copy of the publication, not an official restatement); a reading of them is labeled as a reading. A number that is not the law's or the documents' is **proposed policy** and says so; this page proposes none. Where the law is silent the workflow holds a question for the board. Sample names, dates, and ids are made up.

## 0. How these tasks relate

```text
onboard  (one run per association; five gates: start, ingest, establish, operate, adopt)
 |- ingest               one run per handed-over source (a folder, zip, or Drive folder)     gate: ingest
 |    '- document-intake  one run per document that matters (see 2.1); the rest are only asks
 |- record-slot          the checklist: one run per association, its steps repeat per slot   gates: ingest, establish
 |    '- split-document   one run per draft split of a combined scan
 |- founding-documents   locate, ask, confirm, pin the recorded instruments                  gate: establish
 |    '- key-document     one run per entry (declaration, each amendment, annexation, map ...)
 '- roster, request lists, integrations, schedules, rules and policies                       gates: start, operate, adopt
careful-reading          one run per question that turns on a set of documents (reads what the above filed)
records-production       one run per member's records request; reads the checklist for what is held
```

- **Onboarding hosts ingest, ingest hosts intake, intake feeds the checklist.** A takeover is `onboard`; its INGEST gate is satisfied by `ingest` runs over what the prior manager hands over and by the checklist's slots; its ESTABLISH gate waits on `document-intake` and `key-document` runs for the governing instruments.
- **A child run is a link, not a copy** (design rule 7). The parent's step shows the child's current state and never goes `done` because a child did: a gate is jason's reading of the checklist, and the board decides what is done.
- **One writer per fact.** A recorded instrument's slot is written by the key-documents function from the CLI, the Key documents tab, and the Records screens; the workflow adds no second store (record-intake.md, "Which wins").
- **Only some documents get a run.** `document-intake` is for what the SOP's trigger names: a governing document, amendment, rule, policy, or recorded instrument. A file in a handed-over box that is a bank statement is an `ingest` ask, not a run.

### Conventions for this family

| Term | Meaning on this page |
|---|---|
| **Roles** | M manager; S secretary; P president; T treasurer; B the board, by a vote recorded by S; A administrator; R a second person (any roster person other than the one who answered); any = any signed-in roster person; J jason (checks and jobs). Counsel and owners have no step. |
| **person (signed)** | A `person` step whose act is a signed record in jason's own store (`--by NAME`, a dry run first, `--yes`). Evidence is the store row (`data/intake/asks.json`, `data/spec/<profile>/records.json`, `data/key-documents/<profile>.json`, `data/onboarding/requests.json`, `data/records-requests/requests.json`). The step panel runs the dry run as a `Confirm` where the console has the writer, else shows the `Command`. |
| **plan** | Only where an approvals kind exists or is proposed. **Built kinds** (`registry.py`): `owner-info-tags`, `payhoa-attach-bills`, `gmail-drafts`; none is in this family. **Proposed** (approval-workflow.md section 8): `local.ingest.apply`, `local.living.reread`, `local.spec.migrate`, `local.section-refs.apply`. Intake answers and confirms are explicitly "not engine kinds". |
| **Terminal-only acts** | `jason onboard --apply`, `jason intake --apply`, `jason ingest --apply`, `git apply` of a profile proposal. The run shows the `Command` and the person attests; the console has no writer (checked: `EXTRA_WRITERS`). |
| **Lanes** | `jobs.JobClass`: google, payhoa, county, gpu, local. A model step takes the GPU lane and fails fast on `local_ai.preflight`. A county read takes the county lane. |
| **Never in the log** | A file name or id of a confidential file, a Drive id, a secret, an owner's name. Events carry slot keys, pin ids, counts, and hashes (the records history line already holds no file name). |

## 1. The tasks

| # | Task | Definition key | SOP | Trigger | Subject |
|---|---|---|---|---|---|
| 1 | Take a document in | `document-intake` | `document-intake` (13 steps, 5 `person`) | a governing document, amendment, rule, policy, or recorded instrument arrives; after each library or Drive sync | a document: library id, entry, or instrument number |
| 2 | Take a folder in | `ingest` | `ingest` (7 steps, 2 `person`) | a person hands over a folder, zip, or Drive folder | a source (never its path in a URL) |
| 3a | Fill the record checklist | `record-slot` | `onboard` step 4 and 5; docs/record-intake.md | an association is onboarded; a record is added or reopened | the association; steps repeat per slot, period, entry |
| 3b | Split a combined scan | `split-document` | `onboard` step 5; docs/pdf-splitter.md | a scan holds more than one document | a draft (a split session id) |
| 4 | Take on an association or a change of manager | `onboard` | `onboard` (19 steps, 10 `person`) | jason takes on an association; before a management contract ends | the association (profile key) |
| 5a | Find and pin the founding instruments | `founding-documents` | none (no `jason sop` key; checked in `PROCEDURES`); onboarding.md "Starting a new association" | onboarding; a gap in the key documents | the association |
| 5b | Get one recorded instrument | `key-document` | none; key-documents.md | an entry is expected or located and not held | a key-document entry (`<row>/<number>`) |
| 5c | Read a parcel's title history | `parcel-title` (optional run) | none; handoff-title-processes.md | a resale, a lien, a title-watch item, a formation question | a parcel |
| 6 | Read a set of documents and answer from them | `careful-reading` | `careful-reading` (10 steps, 1 `person`) | a question turns on what a set says | a question and a collection |
| 7 | Produce records to a member (the records side) | `records-production` | none (SOP `respond` covers the clock side); [members-cycles.md](members-cycles.md) | a member's request under Civil Code 5200 to 5240 | a request id (day and unit, never a name) |

## 2. The definitions

Columns: **kind** is one of the seven; **needs** are step ids; **produces / evidence** says what the step makes and what shows it is done; **clock** is its own, with a basis (section 4); **repeat / skip** is how often, and when a step does not apply (a skip by fact is recorded as `skipped` by `jason`; a skip by a person needs a reason).

### 2.1 `document-intake`

| id | Step | Kind | Role | Needs | Produces / evidence | Command | Clock | Repeat / skip |
|---|---|---|---|---|---|---|---|---|
| D1 | Bring the document in | job | J | none | a library row and Drive catalog row; evidence: row exists with a hash | `jason library; jason drive` | none | once; re-evaluated on each sync (hash) |
| D2 | It has a kind | check | J | D1 | the row's method (person, name rule, phrase rule, model) or a parked `classify` ask; a miss stays a miss | `jason intake --scan` | none | never skipped |
| D3 | Say what it is | person (signed) | M or any | D2 failed | a person-chosen kind (outranks every rule) and the ask's answer, by, at | `jason intake --answer ID N --by NAME` | none | per ask; skipped if D2 passes |
| D4 | Read the recorded copy's index row | job | J | D1 | number, date, stamp from the county index; evidence: the read result | MCP `recorder_search`, `recorder_detail` | none | skipped for a draft not meant to record |
| D5 | Establish its standing: draft, adopted, or recorded | person (signed) | S or M | D4 | the `standing` ask answered, naming the minutes or the stamp; an amendment's adopted and recorded dates pinned | `jason intake --answer ID TEXT --by NAME` | law, CIV 4270(a) | per document; a high-stakes answer |
| D6 | A different person confirms | person (signed) | R | D5 | `confirmedBy`; refused for the same name, any case or spacing | `jason intake --confirm ID --by OTHER` | none | per high-stakes ask |
| D7 | Add it to the living document and build | job | J | D5, D6 | built text; applied and not-in-effect lists; before-words findings | `jason living KEY --fetch --working` | none | skipped by fact unless it amends a living document |
| D8 | Preflight a bulk or scanned PDF | job | J | D1 | preflight record keyed by hash; the original untouched | `jason preflight FILE [--render --pdf] [--ocr] [--extract]` | none | skipped by fact unless scanned or bulk |
| D9 | Segment a file that holds more than one document | job (gpu with `--model`) | J | D8 | segments as page ranges with parents; the file is never split | `jason segments FILE [--model] [--write]` | none | skipped by fact unless more than one document or parts |
| D10 | Park every uncertainty | job | J | D2 to D9 | asks in `data/intake/asks.json` (kind, OCR reading, drift, before differs, readings differ, orphaned note) | `jason intake --learn-channel; jason intake --scan [--model] [--vision]` | none | after each change |
| D11 | Answer the questions | person (signed) | M, S, any | D10 | each ask answered with a name; a likely OCR reading accepted only after a look | `jason intake --likely; --answer ID TEXT --by NAME; --accept-likely --by NAME` | none | per ask |
| D12 | Second person on each high-stakes ask | person (signed) | R | D11 | `confirmedBy`; a new answer clears it | `jason intake --confirm ID --by OTHER` | none | per ask of kind standing, readings differ, before differs, drift |
| D13 | OCR suggestions beside scans with no working copy | job (local or gpu) | J | D10 | `<id>.ocr-suggestions.json`; raw text unchanged | `jason intake --library-ocr` | none | skipped by fact if a working copy exists |
| D14 | Apply the answers; build again | person | M | D11, D12 | transcriptions, person-chosen kinds, facts, proposals applied; the question count falls | `jason intake --apply; jason living KEY` | none | after D11 or D12 |
| D15 | Switch to a better reading of a scanned base | plan (proposed `local.living.reread`, two people) | M then R | D14 | dry run first: section count close, no transcription unplaced, WER falls; then the switch | `jason living KEY --reread cli`; `--use-reread cli --yes --by NAME` | none | skipped unless a better reading exists |
| D16 | Check what it changes against the law and the other documents | job | J | D14 | conflict leads, duties, notice requirements | `jason conflicts --leads --document KEY` | person: `jason sop law-review` each January | once per version |
| D17 | Read each lead beside the statute | person | M | D16 | a `Conflict` row proposed as a patch, or a note "no conflict"; never resolved here | `jason conflicts` | none | per lead |
| D18 | Where two readings remain, the board asks counsel | decision | B | D17 | board item, then the decision as recorded by S or P | `jason board` | none | skipped by fact unless D17 marks "for counsel" |
| D19 | Read the citations, scoped to the document they mean | job then person | J, M | D9 | every `ambiguous_document` is a question, never a pick; no citation moves to another document | `jason segments ID --write; jason cite --scan FILE; jason cite EXPR --in KEY --on DAY` | none | per file |
| D20 | Find the rule-making power and the rules on file | job (gpu) then person | J, M | D14 | a subject with rules and no named grant, or a grant with no rule, is a finding for the board, never an accusation | `jason rules --find --model; jason rules --subjects` | none | skipped for a document that grants none |
| D21 | Record the lessons | person | M | D1 to D20 | a lesson row; the SOP step changed | `jason lessons --area governing` | none | once |

### 2.2 `ingest`

Dates: the date the source arrived. A done `ingest` run is read again from the report: `data/onboarding/ingest-<day>.json`.

| id | Step | Kind | Role | Needs | Produces / evidence | Command | Clock | Repeat / skip |
|---|---|---|---|---|---|---|---|---|
| I0 | The source arrives | wait | none (M registers it) | none | the source address and the hash list | none | person (the sender's date) | once per source |
| I1 | Read the dry run | job (google for a Drive source) | J | I0 | the report: files, duplicates, files already held, versions, copies, questions, checklist items and gates that would move | `jason ingest SOURCE` | none | again after I5 |
| I2 | Read the contract terms | person (a model review is a gpu job) | M | I1 | each contract's deliverables and findings as leads beside the words and the statute; a deliverable worth tracking becomes a board item or register row, decided by a person; a remote model (words go to a cloud service) is a person's choice | `jason ingest SOURCE --terms-model ollama; jason contract-terms --list` | none | skipped by fact if the report holds no contract |
| I3 | Follow the report's QR codes | job then person | J, M | I1 | the portal's reports against the library (`reports.missingFromLibrary`); a protected portal is read by a person | `jason vendors --reports; jason ingest data/vendors/KEY/reports` | none | skipped by fact if no code names a portal |
| I4 | Add the local model for files with no kind | job (gpu) | J | I1 | kinds proposed; model unloaded afterward | `jason ingest SOURCE --model` | none | skipped unless many files have no kind |
| I5 | Park the questions and answer them in the ranked queue | job then person (signed) | J, then M or any | I1 | asks parked; then answered and applied (D11 to D14 shapes) | `jason ingest SOURCE --park; jason onboard; jason intake --apply` | none | per ask |
| I6 | Read the dry run again | job | J | I5 | ready, need a kind, need a folder counts | `jason ingest SOURCE` | none | once |
| I7 | File the ready files | plan (proposed `local.ingest.apply`, one person) | M | I6 | files copied into `data/library/files`, `library.db` rows (`ingested`); evidence: the filed count | `jason ingest SOURCE --apply` | none | once; held files stay held |
| I8 | Read a new version of a known document | job then branch | J, M | I1 | history; **reported, never applied**; the new version opens a `document-intake` child | `jason revisions KEY` | none | skipped by fact unless the report finds a version |
| I9 | The ingest gate | check | J | I7 | the last report's files filed and held, versions, open questions, items moved | `jason ingest --gate` | none | on every open |

### 2.3 `record-slot` (the checklist) and `split-document`

Subject of `record-slot`: the association's checklist, about 60 slots in groups (record-intake.md). A slot's identity is its key (`records/5200/minutes`), a period for a series, an entry for a repeating key document. Steps S2 to S9 repeat per slot; the Run page shows them grouped by slot group with the `SlotWord` of each. The slot's state is **computed**, never set by a step: the run reads `record-slots` and folds it.

| id | Step | Kind | Role | Needs | Produces / evidence | Command | Clock | Repeat / skip |
|---|---|---|---|---|---|---|---|---|
| S1 | Read the checklist and its biggest unknowns | check | J | none | counts by state, group, law; the slots a gate waits on | `jason records --list [--group G] [--state S]` | none | on open |
| S2 | How is this slot answered | branch (by person) | any | S1 | one of: pick a file, bind a folder, upload, or answer none, not applicable, waiting | `jason records --slot KEY` | none | per slot |
| S3 | Pick, bind, or upload | person (signed) | any | S2 | a pin (`records.json`; a recorded instrument's pin is a key-documents link); a bound folder's files are candidates, never pins; the file is never touched | `jason records --pick KEY --file ID --by NAME`; `--bind KEY --folder ID`; `--upload KEY --file PATH --yes` | none | per slot, period, entry |
| S4 | Read what was picked | job (google lane; gpu only if a person asked) | J | S3 | the reading at `data/record-intake/<profile>/readings/<pin>.json` once per file hash: kind, tier, preflight, segments, findings | `jason records --read KEY --yes --by NAME` (dry run first) | none | per pin; again if the hash changes |
| S5 | Compare with the slot | check | J | S4 | verdict agrees, differs, or unclassified; differs sets the slot to `problem` | none | none | per pin |
| S6 | Resolve a wrong-slot pick | branch (by person) | any | S5 differs | repin to the slot it fits, keep with a required reason, or unpin; nothing moves until a person confirms | `--repin KEY --to SLOT`; `--keep KEY --reason TEXT`; `--unpin KEY --pin ID` | none | skipped unless S5 differs |
| S7 | Split a combined scan | person (signed) | any | S4 | each confirmed part pinned to its slot as a new file of just those pages; a split nobody confirmed fills nothing | `jason records --split KEY --part SEG=SLOT[@PERIOD][#ENTRY] --yes --by NAME`, or the `split-document` run | none | skipped unless the reading proposes a split |
| S8 | Two holders: which is current | person (signed) | any | S3 | a `currents` row with a required reason; the profile's own pin is changed only by a patch a person applies, so `stillTwo` may remain | `jason records --current KEY --pin ID --reason TEXT` | none | skipped unless two holders |
| S9 | Answer: none exists, not applicable, or waiting | person (signed) | any | S2 | an answer with a name, the words (where looked, or why not applicable), and for waiting who and the day asked | `jason records --answer KEY --none\|--not-applicable\|--waiting WHO --note TEXT --by NAME` | person (the day asked) | per slot; reopen is a later act, the trail stays |
| S10 | Wait for the one who holds it | wait | none | S9 waiting | arrival: a pick for that slot; a date passed opens a follow-up | none | person | until arrival |
| S11 | Is there another? / this is all | person (signed) | any | S3 | a `more` row; a `SEVERAL` slot or a series is answered only when a person says so | `jason records --more KEY --value yes\|no` | none | per slot |
| S12 | Read the gates the slots feed | check | J | S1 | checklist items and gates (start, ingest, establish) computed from the slots; no control passes a gate | `jason onboard` | none | on every open |

`split-document` (the splitter; backend and screens built). A draft is a long-lived session with its own states: draft, confirmed, applied, stale, declined. The only command that writes PDFs is `--apply --yes --by`; no schedule or job applies a split.

| id | Step | Kind | Role | Needs | Produces / evidence | Command | Clock | Repeat / skip |
|---|---|---|---|---|---|---|---|---|
| P1 | Open a draft | person (signed) | any | none | a draft from an upload or a library id (a copy is kept); a Drive file is not taken yet | `jason split FILE\|ID` (dry run) | none | once |
| P2 | Measure the pages and suggest first pages | job (local; gpu with `--model`) | J | P1 | per-page facts; suggestions with tier and reason (High, Medium, Low), never automatic | `jason split ID --suggest [--model]` | none | once; again if new facts are measured |
| P3 | Mark first pages; accept or reject suggestions | person | any | P2 | boundaries saved in order with a version; a 409 shows both copies | `jason split ID --boundaries ...; --accept ...; --mark/--unmark` | none | many |
| P4 | Review: counts, collisions, flags, pages to turn and leave out | check then person | J, any | P3 | flags (blank only, repeats, sideways, may be over the size limit, slot already filled, may hold more than one document) are readings, not decisions | `jason split ID --review --flags` | none | once |
| P5 | Where do the new files go | branch (by person) | any | P4 | held, library, slots, or as each part is labelled | `jason split ID --filing ...` | none | per draft; a part may differ |
| P6 | Write the files | person (signed) | any | P4, P5 | new files (page ranges, `/Rotate` only in the new file); result: filled, taken in, held, skipped, failed; original untouched | `jason split ID --apply --yes --by NAME` | none | once; a failed segment is retried |
| P7 | Read each new part | job (google lane; local for OCR) | J | P6 | read-back job per part (`split.auto_read`), OCR jobs for library parts (`split.ocr_queue_max`); "no OCR engine" means install one, not retry | `jason library --ocr-doc ID --yes --by NAME` | none | per part |
| P8 | Or decline | person (signed) | any | P1 | draft `declined`; the record-intake "combined scan" item leaves | `jason split ID --decline --by NAME` | none | alternative to P6 |

### 2.4 `onboard`

Subject: an association (profile key), with the run's first fork: **new association** or **change of manager** (a branch by person at start; the last block applies only to the second). Dates: the outgoing contract's term end and the transition date (documents or person). Phases are the five gates (`onboarding.Stage`: start, ingest, establish, operate, adopt); each gate row is a `check` whose result is jason's computed reading ("a gate is jason's reading; the board decides what is done").

| id | Step (SOP step) | Kind | Role | Needs | Produces / evidence | Command | Clock | Repeat / skip |
|---|---|---|---|---|---|---|---|---|
| ST-1 | Choose the community (1) | check | J then M | none | the active profile equals the run's subject; the write banner names it; the vault pool shows the sessions this process opened | `jason which; jason use KEY` | none | on every open and before every job (a mismatch blocks) |
| ST-2 | Start the profile package (2) | person | A | ST-1 | a package from jason's templates, empty private facts `data/spec/<key>.json`; it overwrites nothing; source files a person reviews and commits | `jason onboard --new KEY --name NAME --county COUNTY` | none | once; terminal only |
| ST-3 | Look up the county's finds (2) | job (county) | J | ST-2 | leads under `leads` in the private facts; each becomes a question; an empty or unreachable recorder is a note, not a row | `jason onboard --lookup` | none | skipped if no county reader |
| ST-4 | Confirm only its own facts are read (3) | check | J | ST-2 | paths `data/spec/<key>.json` and `data/spec/<key>/` only | `jason spec` | none | a copy of the default profile's topics is plan `local.spec.migrate` (proposed), default profile only |
| ST-5 | Set up the community's Google Workspace (6) | person | A | ST-1 | the client in this community's vault path and one sign-in per needed token; never ask for consent again while a token covers the scopes; never retry `invalid_grant` | `jason google status; jason google setup --from-file F --yes; jason google sign-in --name drive --interactive` | none | interactive only, by a person |
| ST-6 | Connect the integrations (14) | person | A | ST-1 | each credential under its vault path; "connected" only after a read succeeds, checked by a person at a console | `jason vault status; jason vault migrate; jason integrations check KEY --live --by NAME` | none | per integration |
| ST-7 | Gate: start | check | J | ST-4 to ST-6 | open when units, management software, Drive, and vault are present | `jason onboard` | none | on open |
| IN-1 | Read the record checklist (4) | check | J | ST-7 | child run `record-slot` linked; counts by state | `jason records --list` | none | link only |
| IN-2 | Read the picks (5) | person | any | IN-1 | children: `record-slot` S3 to S11, `split-document` for a long combined scan | `jason records --read KEY` | none | per slot |
| IN-3 | Send each source its request list (11) | person | M | ST-7 | `data/onboarding/requests.json` rows: asked (of whom, when); three dates: at once, monthly after late fees, at transition; paper comes with a contents list per box | `jason onboard --request [SOURCE]` | person (the dates), documents where the transition agreement sets them | per source |
| IN-4 | Wait for each source | wait | none | IN-3 | received (when, where filed); a date passed opens a follow-up (gap 7) | none | person | per source and date |
| IN-5 | Take in what arrives | child `ingest` | M | IN-4 | one `ingest` run per source | `jason ingest SOURCE` | none | per source |
| IN-6 | Fetch what jason can read itself (16) | job (payhoa, google) | J | ST-7 | catalog, library, outlines refreshed | `jason sync-catalog; jason library; jason outlines --fetch` | none | repeat |
| IN-7 | Gate: ingest | check | J | IN-1, IN-5, IN-6 | open when records map, minutes, budget reports, financial statements, contracts, and insurance policies are present and no library file waits for a kind | `jason onboard; jason ingest --gate` | none | on open |
| ES-1 | Find and pin the founding instruments | child `founding-documents` | M | IN-7 | the declaration, amendments, annexations, bylaws, articles located, asked, confirmed | see 2.5 | none | link only |
| ES-2 | Take each governing instrument in | child `document-intake`, `key-document` | S, M | ES-1 | one run per instrument | see 2.1, 2.5 | none | per instrument |
| ES-3 | Run the session: answer (8) | person (signed) | M, S, T, any | ST-7 | each question answered; a secret is refused and nothing stored (the Keeper record's name is answered instead); the answer is shown to the one who gave it or is confirming it | `jason onboard --answer ID TEXT --by NAME` | none | per question, ranked by what it unblocks |
| ES-3b | Or answer by conversation (9) | branch (by person) | any, R | ST-7 | same tools: `onboarding_status`, `next_questions`, `answer_intake_question`; the second person runs `onboard_review` | `jason-mcp --profile onboarding` | none | alternative to ES-3 |
| ES-4 | A second person confirms a high-stakes answer | person (signed) | R | ES-3 | which text is in force, whether an instrument was recorded, bank signers; the answerer cannot | `jason onboard --confirm ID --by OTHER` | none | per high-stakes answer |
| ES-5 | Apply the answers | person | M | ES-3, ES-4 | private facts merged with a backup and a diff; Keeper notes; profile proposals written under `data/onboarding/proposals/` | `jason onboard --apply` | none | terminal only; repeat |
| ES-6 | Read and apply each profile proposal | person | M | ES-5 | a patch read, `git apply`, committed; jason never edits the profile | `git apply` | none | per proposal |
| ES-7 | Gate: establish | check | J | ES-2, ES-6 | open when the declaration, amendments, annexations, bylaws, and articles are present, each recorded copy is matched in the county index and read with a stamp (`Verified`), and no question is open about which text is in force (`Settled`) | `jason onboard` | none | on open |
| OP-1 | Put people, accounts, figures in the private facts (12) | person | M | ST-7 | facts in `data/spec/<key>.json` or notes; codes and passwords in Keeper only | none | none | continuous |
| OP-2 | Keep the roster current (10) | person (signed) | S or M, then R | ES-3 | `board-roster` (OFFICE; PERSON or vacant; YYYY-MM-DD; MINUTES) and `election-status` answered after the minutes record the change; appended to the officers or terms topic | `jason onboard --questions --group board` | none | per change; waits on the minutes |
| OP-3 | Adopt the schedules (15) | person | A, or the board's choice | ST-6 | no source runs until adopted; none faster than its floor; no write scheduled; the heartbeat fresh | `jason cadence; jason serve --install-task; jason daemon status` | none | per source |
| OP-4 | Gate: operate | check | J | OP-1 to OP-3 | board rule, roster, signers, accounts, assessments, fiscal year, meeting schedule, notice rules, assignments, utilities present | `jason onboard` | none | on open |
| AD-1 | Write the profile's rows (13) | person | M, with the facts the board supplies | ES-6 | a Community subclass, pinned library folders and Drive roots, books; the SOP does not flag this step `person` (gap 2) | none | none | continuous |
| AD-2 | Take in the rules and policies | child `document-intake` | S, M | AD-1 | one run per operating rule set, election rules, policy, resolution | see 2.1 | none | per document |
| AD-3 | Run the checklist until only what a person supplies is missing; give each an owner (17) | check then person | J, M | all gates | the checklist report; each missing item has an owner in the schedule | `jason onboard --checklist --write; jason schedule` | none | repeat |
| AD-4 | Gate: adopt | check | J | AD-2, AD-3 | operating rules, election rules, policies, collection and enforcement policies, architectural procedure, governing set, conflicts present | `jason onboard` | none | on open |
| AD-5 | Close the onboarding | person | M | all gates | a note that the board saw the gates open; closes the run | none | none | once (design choice, section 8) |
| CM-1 | Read the outgoing agreement (18) | person | M | ST-7 | its term, non-renewal and termination clauses, what it owes at transition; each notice window counted back from the term's end, both edges written down | none | documents (the agreement) | branch: change of manager only |
| CM-2 | Decide whether to give notice | decision | B | CM-1 | the board's decision, meeting, vote as taken. **Added by this design**: the SOP assumes the decision | `jason board` | documents | change of manager only |
| CM-3 | Send the notice by the delivery the clause names; keep proof | person, then wait | M | CM-2 | proof of delivery kept with the notice | none | documents (both edges of the window) | change of manager only |
| CM-4 | Before the termination date: request the records, confirm the board's portal access, tell each vendor (19) | person, then wait | M | CM-2 | asked, received, per source; the board's access confirmed | `jason onboard --request` | person (the three dates); see 4, row 9 | change of manager only |

### 2.5 Title and deed work

There is no `jason sop` key for this work (checked in `PROCEDURES`). The three definitions below are drawn from [../key-documents.md](../key-documents.md), [../instrument-graph.md](../instrument-graph.md), [../console/handoff-title-processes.md](../console/handoff-title-processes.md), and onboarding.md. **A reading is a lead, not a pin**: every join is "read as", never "is".

`founding-documents` (subject: the association; gate ESTABLISH):

| id | Step | Kind | Role | Needs | Produces / evidence | Command | Clock | Repeat / skip |
|---|---|---|---|---|---|---|---|---|
| F1 | Choose the association from the county directory | person | M | ST-3 | the directory row; a row is a lead, not a pin | `jason onboard --associations --county C [--find WORDS]` | none | once; skipped if the profile names it |
| F2 | Locate its recorded documents | job (county) | J | F1 | `data/onboarding/<profile>-documents-located.json` with ties (names the association, recorded with its documents, the builder's filing "may be another community's"); the same job the console queues | `jason onboard --locate` | none | again on demand; a queued locate is returned, not doubled |
| F3 | Ask the board about each | person (signed) | any | F2 | a `FACT` question per item answered; the declaration and amendments are high stakes | `jason onboard --questions` | none | per item |
| F4 | A second person confirms which is the declaration | person (signed) | R | F3 | `confirmedBy` | `jason onboard --confirm ID --by OTHER` | none | per high-stakes item |
| F5 | Pin it in the profile | person | M | F4 | a proposal patch applied by a person; a located number is a lead until the recorded copy is read | `git apply` | none | per pin |
| F6 | Not located: ask for the recording number | wait | none | F2 | "Not located" with the ask; a number arrives from the board or prior manager | none | person | per item |

`key-document` (subject: one entry; the list is data, `KEY_DOCUMENTS`):

| id | Step | Kind | Role | Needs | Produces / evidence | Command | Clock | Repeat / skip |
|---|---|---|---|---|---|---|---|---|
| K1 | Status from the stores: expected, located, held, linked | check | J | none | the entry's status and copies; `missing` is only ever a person's word and needs a note | `jason key-documents` | none | on every open |
| K2 | Order the recorded copy | person | M | K1 located | the copy-order list (instruments the records lack, priced in cents); jason never sends it | `jason records-request`; `jason county-records --request` (in the working tree, not committed: not verified) | none | skipped if held |
| K3 | Wait for the copy | wait | none | K2 | arrival of a scan | none | person | until arrival |
| K4 | Link or upload the copy | person (signed) | any | K3 | a link (file, Drive, or PayHOA document) or an upload kept under `data/key-documents/<profile>/files/`; unlink marks, never deletes | `jason key-documents --link KEY ...; --upload KEY --file PATH --by NAME` | none | per copy |
| K5 | Read the stamp and match the county index | check | J | K4 | the `Verified` check: matched, and none read without a stamp | `jason onboard` | none | on open |
| K6 | Say whether it took effect | person (signed), then R | S or M | K5 | standing (steps D5, D6 of `document-intake`); an amendment with no number is noted as not recorded | `jason intake --answer` | law, CIV 4270(a)(3) | per instrument |
| K7 | Or: none on record, with the note | person (signed) | any | K1 | status `missing` with what was looked for and where | `jason key-documents --status KEY --set missing --note TEXT --by NAME` | none | alternative to K4; reopen by linking |

`parcel-title` is a **read, not a procedure**: a history of a parcel's deeds, the closings and loans around them, and gaps, masked by role until a named person reveals owners' names (logged to `data/console/reveals.jsonl`). It becomes a run only when started from a matter (a lien release, a resale, a formation question): P-1 read (job, county lane), P-2 check strand and gaps (check), P-3 look up a gap (job, a person asks, `Confirm`), P-4 reveal names (person, logged), P-5 export the report (job). The commands are the parcel-history command in [../placer.md](../placer.md) and `jason instrument-graph --parcel APN`; the MCP tools are `recorder_descend`, `ownership_record`, `pinned_chain`, `read_deed`.

### 2.6 `careful-reading`

Subject: a question and the collection it turns on (a case's file, a vendor's file, a meeting's packet). The workflow keeps three things apart as the SOP does: what the documents say, what the provisions mean, whether the facts meet them.

| id | Step | Kind | Role | Needs | Produces / evidence | Command | Clock | Repeat / skip |
|---|---|---|---|---|---|---|---|---|
| C1 | Check where scratch and caches go | check | J | none | temp and `ASSPY_HOME` on the data drive with room | `jason storage --check` | none | before a build or a copy |
| C2 | See what the index holds and cannot read | job (local, gpu to build) | J | C1 | the collection's files indexed; unreadable or partly read files listed for a person; a held-back record is never extracted | `jason index --plan; jason cases --extract-text --case KEY; jason index --build` | none | once; again when files change |
| C3 | Search the slice that matters | person | any | C2 | hits with standing (the law, the record, evidence, a reference, jason's own page: a summary, never the rule) | `jason index --search Q --catalog NAME [--kind K] [--standing S]` | none | many |
| C4 | Lay out what the documents say happened, and where they differ | job | J | C2 | chronology (each event states what a document says); fact conflicts keep both documents | `jason chronology --catalog NAME; jason fact-conflicts --catalog NAME` | none | once |
| C5 | See what should be on file and is not | job | J | C2 | "not on file" never means "not done"; an undetermined answer is a question for a person | `jason inspections; jason applies` | none | skipped if no inspection applies |
| C6 | Recite each provision's words before any reading | job | J | C3 | the provision whole, in force on the day, with its caveat | `jason readings --recite CITATION; jason cite KEY` | none | per provision |
| C7 | Review under the task's pack, the collection its own tier | job (gpu) | J | C4 to C6 | a kept review (pack digest, runs); a confidential collection is refused for a members' task | `jason review TASK --collection KEY --ask Q --run` | none | repeat; kept, not overwritten |
| C8 | Judge date-dependent findings as of the date that matters | job | J | C7 | only the lens's findings move with the date | `jason models --as-of DATE` | person (the date) | skipped if nothing is date-dependent |
| C9 | Check every quotation against the stored words | check | J | C7 | each `FOUND`, in the provision the answer names; `ALTERED`, `MISATTRIBUTED`, `OTHER VERSION`, or `NOT FOUND` blocks C10 | `jason verify-quotes FILE --as-of DAY` | none | every time the answer changes |
| C10 | Give the answer as a proposal | person | M | C9 | facts with sources, provisions recited, reading labeled, application; the board or counsel decides | none | inherited (a parent run) | once per answer |

### 2.7 `records-production` (the records side of a member's request)

The request's receipt, acknowledgment, and answer clocks belong to the members family: [members-cycles.md](members-cycles.md) (written separately; not read). This definition is the part that touches the records: which record answers, what is withheld, what it costs, and the production. It may run as a child of that page's request run.

| id | Step | Kind | Role | Needs | Produces / evidence | Command | Clock | Repeat / skip |
|---|---|---|---|---|---|---|---|---|
| M1 | Open the request | person (signed) | M | none | a row in `data/records-requests/requests.json` keyed by day and unit, with the record kinds asked, the years, the purpose in the member's words | console write `records-requests` (no CLI command exists, checked) | law, CIV 5210(b), see 4 | once; starts the clocks |
| M2 | Designation, if a representative asks | check then person | M | M1 | the member's written designation on file | none | none | skipped by fact if the member asks |
| M3 | Map each kind to its record and its holder | check | J | M1 | each kind to its paragraph of CIV 5200(a) (table below), the slot's state, the inspection period | `jason records --slot KEY` | none | per kind |
| M4 | A record not held: look, ask, or say none exists | person (signed) | any | M3 | `S9` of `record-slot` (none exists, waiting) for that kind; "missing" is not "none" | as S9 | none | skipped if held |
| M5 | Membership list only: weigh the stated purpose | person | M, counsel where needed | M1 | `purposeAdequate` true or false, the member's words quoted, never paraphrased or scored | console write | law, CIV 5225 | skipped unless the list is asked |
| M6 | Decide what to withhold or redact, and on what basis | person (signed) | M, counsel where needed | M3 | `withheld` rows `{record, reason}` as the person gives them; a membership list built with opt-outs removed is handed to no one by jason | console write | law, CIV 5215 | per kind |
| M7 | Tell the member the cost and wait for agreement | wait | none | M6 | the member's agreement (copying and mailing; a redaction estimate), then `feeCents` | none | law, CIV 5205(f), (g) | skipped if inspection only |
| M8 | Produce: make available, deliver copies, or send electronically | person | M | M5, M6, M7 | `producedOn`, `inspectedOrCopies`; nothing is sent by jason; a cover email is a Gmail draft a person sends (needs a new `gmail-drafts` case) | console write | law, CIV 5210(b) | once |
| M9 | If asked, give the written explanation of a denial or redaction | person | M | M6 | the written explanation specifying the legal basis | none | law, CIV 5215(d) | skipped unless the member asked |
| M10 | Wait to the production date; overdue opens a follow-up | wait | none | M1 | `standing` open, produced, or overdue, read on its face | none | law, CIV 5210(b) | until M8 |

Which record answers which request (labels are the code's `AssociationRecord` labels; paragraphs are those of CIV 5200(a), (b), (c) as stored):

| Request kind | 5200 paragraph | Notes the step must show |
|---|---|---|
| Financial disclosures | (a)(1) | within the time stated in the section that requires it (5210(b)(3)) |
| Transfer and escrow financial documents | (a)(2) | same |
| Interim financial statements | (a)(3) | |
| Executed contracts | (a)(4) | "not otherwise privileged under law"; 5215(a)(5)(D) |
| Vendor and contractor approvals | (a)(5) | |
| Tax returns | (a)(6) | |
| Reserve account balances and records | (a)(7) | |
| Minutes (member, board, committee) | (a)(8) | excludes executive sessions; permanent (5210(a)(2)); times per 5210(b)(4), (5) |
| Membership list | (a)(9) | opt-outs (5220), purpose (5225), time per 5210(b)(6); Safe at Home (5216) |
| Check registers | (a)(10) | |
| Governing documents | (a)(11) | the key documents' slots carry this record |
| Accounting of reserve funds used for litigation | (a)(12) | |
| Enhanced records | (a)(13), (b) | redaction cost under 5205(g) |
| Election materials | (a)(14), (c) | "may be inspected but may not be copied" (signed voter envelopes) |
| Exterior elevated element inspection report | (a)(15) | period per 5210(a)(3) |

## 3. Branches and failure paths

**Branches by person:** S2 (how a slot is answered), S6 (a wrong-slot pick), P5 (where new files go), ES-3 versus ES-3b (terminal or conversation), the start fork (new association or change of manager). **By fact:** D7, D8, D9, D13 (document shape), I2, I3, I4, I8 (what the ingest report found), S7 (the reading proposes a split).

| Event | What the run does |
|---|---|
| A `check` fails (D2, S5, ES-7) | the step is `blocked` and says why in the server's words (a kind is missing; the file reads as another kind; a recorded copy has no stamp). A failed check is never turned into a pass; a person records why it does not apply, with a reason. |
| A job fails | `failed` with the message, the lane, and the log link; nothing is retried automatically. "No OCR engine" means install one. A county read that cannot reach the index is `failed`, never "none found". The Drive chooser's "not connected" is `blocked` with the command; the upload path still works. A Google refusal's file id is never put in the log. |
| A model step cannot run | `blocked` with `local_ai.preflight`'s words (short of memory, GPU lock held). The step is not skipped: the person chooses to wait or to run it later; a miss stays a miss. |
| An arrival never comes (IN-4, S10, K3, M7, CM-4) | the wait's date passes: the step stays `waiting`, a follow-up opens for a person, the Run page says "overdue by N days, basis: person" (no law clock exists for a handover, section 4). It never marks anything received. |
| A secret is typed | the server refuses the answer (`intake.secret_reason`); nothing is written; the event is a `note` with no value; the person answers with the Keeper record's name. |
| The second person is the first | refused on the server for any case or spacing; the step stays `needs a person` for R. A new answer after a confirmation clears it and returns the step to R, with the cleared line shown. |
| Rejected or held plan (D15, I7) | the item is recorded as rejected or held with its reason; the step stays open; a held item is never approved. The proposed kinds do not exist yet (gap 5). |
| A wrong-slot pick | S5 differs; S6 offers three acts; nothing moves until a person confirms; the confirmations item leaves when the pick is kept, moved, or unpinned. |
| A collision (two holders, a split part into a held slot) | reported, not written; S8 asks which is current; the profile's own pin is changed only by a patch a person applies, so the run may stay at "two holders remain" and says so. |
| A partial apply | the result is `partial` with the finishing command; the step stays `running` until the finishing act (the replace act's rule) and never reads `done`. |
| Wrong community | ST-1 fails before any job: the active profile must equal the run's subject. |

**Changed since (resume rule 2).** Opening a run compares each done step's evidence with its store:

| Done step | Compared with | Reads "changed since" when |
|---|---|---|
| D1, S3, K4 | the file's hash and Drive modified time | the bytes differ (the reading marks `changed` with a diff of facts: size, kind, tier, text length, pages, documents; `--ack` marks it seen) |
| D5, D11, ES-3 | the ask's `answeredAt` | a different answer was saved after the person saw it (the built route overwrites; gap 6) |
| D9, P4 | the segmentation and flags matched by level and page range | the draft's segments moved |
| I7 | `data/onboarding/ingest-<day>.json` | the report was rewritten, or a later `jason library` run dropped an ingested row (lesson `library-run-drops-ingested-rows`) |
| IN-7, ES-7, OP-4, AD-4 | the gate computed now | a gate that was open is closed again (an item fell out, a question reopened) |
| K5 | the county index row | the number no longer matches or the stamp is gone |
| S9 | the trail | reopened by a later act; the earlier answer stays in the trail |

## 4. The clocks and their basis

Recited from `data/authorities` (jason's copy; not an official restatement). Reading is labeled.

| # | Clock | Basis | The words | Used in |
|---|---|---|---|---|
| 1 | An amendment's effect | law, CIV 4270(a)(3) | "an amendment is effective after all of the following requirements have been met: ... (3) The amendment has been recorded in each county in which a portion of the common interest development is located." | D5, K6 |
| 2 | Law over documents | law, CIV 4205(a) | "To the extent of any conflict between the governing documents and the law, the law shall prevail." | D16, D17 |
| 3 | Inspection periods | law, CIV 5210(a)(1), (2) | "For the current fiscal year and for each of the previous two fiscal years." Minutes "are subject to inspection permanently." | M3 |
| 4 | Current-year records | law, CIV 5210(b)(1) | "within 10 business days following the association's receipt of the request." | M10 |
| 5 | Prior-year records | law, CIV 5210(b)(2) | "within 30 calendar days following the association's receipt of the request." | M10 |
| 6 | Membership list | law, CIV 5210(b)(6) and CORP 8330 | 5210(b)(6): "within the timeframe specified in Section 8330 of the Corporations Code." 8330(a)(1): "upon five business days' prior written demand"; 8330(a)(2): "on or before the later of ten business days after the demand is received or after the date specified therein"; 8330(c): the corporation "may, within ten business days after receiving a demand ... deliver ... a written offer of an alternative method". | M10 |
| 7 | Cost agreed first | law, CIV 5205(f), (g) | (f) "the member shall agree to pay those costs, before copying and sending the requested documents." (g) "an amount not in excess of ten dollars ($10) per hour, and not to exceed two hundred dollars ($200) total per written request" (1000 and 20000 cents) "for the time actually and reasonably involved in redacting an enhanced association record." | M7 |
| 8 | Written explanation | law, CIV 5215(d) | "If requested by the requesting member, an association that denies or redacts records shall provide a written explanation specifying the legal basis for withholding or redacting the requested records." | M9 |
| 9 | Handover dates | person; documents where the transition agreement sets them | at once, monthly after late fees, at transition. The stored statutes name no handover deadline: the law is silent here. | IN-3, IN-4, CM-4 |
| 10 | Notice windows of the outgoing agreement | documents | counted back from the term's end, both edges written down before the notice goes (lesson `notice-window-has-two-edges`) | CM-1, CM-3 |
| 11 | Election materials kept | law, CIV 5200(c) | "An association shall maintain association election materials for one year after the date of the election." | S3, M3 |
| 12 | The January law review | documents (the SOP `law-review`) | each January | D16 |
| 13 | A slot's "waiting" and the onboarding gates | person | a day a person recorded; no due date unless a person sets one. The record-intake narrative (day 1, week 1, day 30) is a typical path, not a clock. | S10, ST-7 to AD-4 |

**Reading, held for the board and counsel (row 6).** The members' request code counts the list stage at five business days and labels it "CIV 5210(b)" (`records_requests.MEMBERSHIP_LIST_BUSINESS_DAYS`, checked). The stored text of 5210(b)(6) points to 8330, which states more than one timeframe (above). Which applies to a given demand is not settled here: the run shows the three recitations beside the computed date and labels the date "jason's computed date, for a person to check", never as the deadline. Business days count Monday to Friday with no holidays, and the fiscal year is read as the calendar year (the code's own caveats).

## 5. The screens

The common screens are those of workflows-design.md section 4 (Work list, Run page, StartRun, dialogs, Today). This family uses the existing screens as the step panels' destinations rather than drawing parallel ones.

| Surface | Route | Shows (from real loader fields) | Built or to add |
|---|---|---|---|
| Work list rows | `#/work` | run label, the gate or phase, current step, its clock and basis, age | to add (`work`) |
| Onboarding run | `#/work/onboard/<profile>` | the rail grouped by gate (`gates[].stage`, `open`, `opensWhen`, `waiting[]`, `checks[]`), `progress` (present, partial, missing), `questions.open`, `.byKind`, `.answeredNotApplied`, the first closed gate; child-run rows | rail to add; `onboarding-session` built; `StageSteps`, `QuestionCard`, `SecondConfirm` built (Setup tab of `#/onboarding`) |
| Questions step | the Setup tab, or inline | `next[]` ranked: `kind`, `subject`, `question`, `choices`, `suggestion` (not pre-selected), `evidence`, `unblocks`, `highStakes`; where the answer goes | built |
| Find the association | `#/onboarding` tab | `associations`, `documents-located` (`items[].located`, `not_located`, `job`), "Locate documents" through `Confirm`, polling the job | built (`AssociationPicker`, `DocumentLocator`) |
| Key documents | `#/onboarding` tab | `key-documents`: each entry's status, copies, `slot`, `slotCounts`; link, upload, unlink, status | built (`KeyDocuments`) |
| Recorded instruments | `#/onboarding` tab | `instrument-graph?scope=association` masked; reveal logged | built (`InstrumentGraph`, `OwnerNames`) |
| Request list | `#/onboarding` tab | `onboarding` items with asked and received days; `POST /api/onboarding/<key>` | built |
| The record checklist | `#/setup/records`, `#/setup/records/<key>` | `record-slots` (`counts.byState`, `groups[]`, `biggestUnknowns`), `record-slot` (`holders`, `collisions`, `acts`, `log`, `standing`), `record-bindings`, `record-readings` | built (`RecordsView`; `DriveChooser`) |
| The splitter | `#/setup/split`, `#/setup/split/<id>` | `split-sessions`, `split-session` (boundaries, suggestions, flags, review) | built (`SplitView`) |
| The 5200 inventory | `#/records` | `association-records`, `records-inventory`, `governing-documents` | built |
| Ingestion | `#/ingestion` | `library-status` (`files`, `distinctFiles`, `unclassified`, `byMethod`, `byKind`, `byRecord`), `document-readings`, `citations?source=ingest` | built; the ingest report band needs a loader `ingest` |
| Leads | `#/leads` | unpinned items | built |
| Records requests | `#/records-requests` | `records-requests`: each request's stages (clock), `standing`, `kinds` with citation and retention | built (`RecordsRequestsView`); owner view sends kinds alone |
| Jobs | `#/jobs` | the job a `job` step links | built |

**The Run page for this family** (workflows-design.md section 4, point 2) adds:
- **Gate grouping.** For `onboard`, the step rail is grouped by the five gates, using `StageSteps` for the stage header ("Gate open", or "Gate closed" with what it waits on, `aria-current="step"` on the stage being worked). Each gate row's text is the gate's own `opensWhen`. The caveat is always shown: "A gate is jason's reading of the checklist; the board decides what is done."
- **Child-run row** (to add: `ChildRunRow`): the child's label, state word, and next step, linking to its Run page; used for `ingest`, `record-slot`, `document-intake`, `key-document`, `founding-documents`.
- **Act in place.** A `person (signed)` step opens the existing screen's act, not a copy: S3 to S11 open `#/setup/records/<key>`; P3 to P8 open `#/setup/split/<id>`; K4, K7 open the Key documents row; ES-3 opens the `QuestionCard`; M1 to M9 open `#/records-requests`. Each is a `Confirm` that names the slot, the file, and the person. The Run page records the result as an `attested` event pointing at the store row.
- **Terminal-only steps** show the `Command` and a "Done in a terminal" attestation (ES-5, ES-6, D14, I7).

**States** (every Run page and step panel):

| State | What it says |
|---|---|
| Loading | a list skeleton announced; a slow loader keeps what it shows |
| Empty | "No run yet. Start one" with `StartRun`; an association with no profile: "jason has no stores for this profile yet. Start with Onboarding." |
| Missing | a store absent (no ingest report: "No ingest has run. Start one with `jason ingest SOURCE`."; no library; Drive not connected: the server's sentence and the command) |
| Stale | a read longer ago than its source allows (the county index row, the Drive listing's counts "as old as the listing"); said in words with the day |
| Blocked | by which step or fact (the active community; a first closed gate; a second person needed) |
| Changed since | the banner of section 3, with the difference in facts, never the text |
| Owner view | none: every route here is board only; the loaders refuse `view=owner` |

**Loaders and writers to add for the family** (all read disk only):

| Name | Function behind it | Why |
|---|---|---|
| `ingest` | `jason.tasks.ingest` report (`data/onboarding/ingest-<day>.json`) | I1, I9 (named "to add" in records-and-library.md; not in `sources.py`, checked) |
| `library-text`, `revisions` | `library_text`, `revision_detection.history` | I8, D5 (same note) |
| `recorder-reading` | `recorder_detail` by number, county lane, cached | D4, K5 (only the MCP tool exists) |
| `conflicts`, `cite` | `document_conflicts`, `cite_document` | D16, D17, C6 (MCP only today) |
| `work`, `work-run` | the run store | common |
| writers | a run's small acts; the `ingest` and `intake` apply as proposed kinds, not new routes | common |

## 6. Privacy and roles

| Steps | Level | Who acts |
|---|---|---|
| Gates, counts, slot states, stage words | P0 to P1 | any signed-in roster person |
| Slot titles, law, pins, readings | P1; a confidential file's name and reading by kind only outside the private view ("a confidential file: kind legal") | any |
| Intake questions and answers | P1; the answer shown to the one who gave it or is confirming it | M, S, any; R confirms |
| Standing, conflict leads, rule-power findings | P1; counsel's letters P3 | M, S; B for D18 |
| Private facts, bank signers, account numbers | P3 (`data/spec`); secrets P4 never typed | M with R; A for ST-5, ST-6, OP-3 |
| Instruments, parties, title history | owners' names P1: masked by role by default; a named person's reveal is logged and says who and when | M, S |
| Ingest report, contract terms | P1 to P3 (names the files); a remote model is a person's choice | M |
| Executive-session records, the membership list, ballots, election materials | P3, listed by kind only; the request's restricted kinds are counted, not named | M, with counsel |
| Records requests | a member's name is never the key; day and unit; P2 contact details not shown | M; B, T read |

Directors and officers have the same access to information (the board's decision of 2026-10-11): a director reads what an officer reads at the same level. By `access.SEE_RULES` the roster opens P0 and P1; the manager, president, vice president, director, secretary, and treasurer open P2 and, in the private view, P3 (the treasurer since 2026-10-11). A director acting as the second person (R) sees the question and the answer to be confirmed.

A run's list never carries an owner's contact details or an answer. A URL carries a slot's key, a draft's id, or a run id, never a file name, a Drive id, or search words (searches are POSTs). The pin store and `data/spec` are never served as files.

## 7. What exists now

Each row was checked against the repo on 2026-10-11 unless it says "not verified".

| Piece | Where | Covers |
|---|---|---|
| SOPs | `jason.community.procedures.PROCEDURES` (`document-intake` 13 steps, `ingest` 7, `onboard` 19, `careful-reading` 10); `jason sop KEY` | definitions' source |
| Intake queue | `jason intake` (`--scan`, `--answer`, `--confirm`, `--apply`, `--likely`, `--accept-likely`, `--library-ocr`), `data/intake/asks.json`; writer `POST /api/write/intake/<id>` (answer, confirm only) | D2 to D14 |
| Onboarding session | `jason onboard` (`--new`, `--lookup`, `--locate`, `--associations`, `--scan`, `--answer`, `--confirm`, `--apply`, `--request`, `--checklist`), `onboarding.GATES` (five), loader `onboarding-session`, MCP `onboarding_status`, `next_questions`, `answer_intake_question`, `intake_questions`, `onboarding_confirm`, `association_directory`, `documents_located` | `onboard` |
| Ingest | `jason ingest` (`--apply`, `--park`, `--model`, `--terms-model`, `--gate`), report `data/onboarding/ingest-<day>.{md,json}`; also `jason contract-terms`, `jason revisions`, `jason preflight`, `jason segments` | `ingest`, D8, D9 |
| Record checklist | `jason records` (`--list --slot --pick --also --bind --upload --replace --answer --unpin --keep --repin --more --reopen --current --bindings --read --split --ack`), `jason.tasks.record_slots`, `record_readback`, `record_acts`, `record_upload`, `record_standing`; loaders `record-slots`, `record-slot`, `record-bindings`, `record-readings`, `drive-list`, `drive-search`, `drive-resolve`; writers `records`, `drive`; MCP `record_slots`, `record_slot` (read only) | `record-slot` |
| Splitter | `jason split`; loaders `split-sessions`, `split-session`; writer `split`; limits `upload.max_bytes`, `split.auto_read`, `split.ocr_queue_max` | `split-document` |
| Key documents | `jason key-documents`; loader `key-documents`; writer `key-documents` | `key-document` |
| Founding documents | `jason onboard --locate`; loaders `associations`, `documents-located`; writer `documents-located` (queues the job) | `founding-documents` |
| Instrument graph | `jason instrument-graph`; loader `instrument-graph`; writer `instrument-graph` (reveal) | title |
| Title tools | the parcel-history command (section 2.5), MCP `recorder_search`, `recorder_descend`, `ownership_record`, `pinned_chain`, `read_deed`, `title_watch`; screen `#/title` | `parcel-title` |
| County records, land check | `jason county-records`, `jason land-check` exist in the working tree, uncommitted by another session | not verified |
| Careful reading | `jason index`, `cases`, `chronology`, `fact-conflicts`, `review`, `verify-quotes`, `readings`, `cite`, `models`; MCP `document_search`, `passage_search`, `manager_context`, `verify_quotes` | `careful-reading` |
| Members' records | `jason.tasks.records_requests`, loader and writer `records-requests`, screen `#/records-requests`, MCP `records_inventory`; no CLI command and no MCP tool reads or writes the request store (checked: `commands/`, `mcp/`); the response rules (`community/responses.py`) route a records request to the `records-requests` assignment | `records-production` |
| Jobs | `jason.jobs.JobClass` (gpu, google, payhoa, county, local); loader `jobs`; `#/jobs` | every `job` step |
| Approvals kinds | `registry.py`: `owner-info-tags`, `payhoa-attach-bills`, `gmail-drafts` only | none in this family |
| Run store | `jason.workflows`, `data/workflows/` | **absent** |

**SOP against the code.** `onboard` step 13 (write the profile's `Community` subclass) is not flagged `person`, though no command does it. `document-intake` step 2 names MCP tools only (no CLI or console loader for a recorder reading by number). `jason records-request` builds the **copy-order list for the county**, not a member's records request (those are `records-requests`); the two names are easy to confuse.

## 8. Gaps and the build order

**Gaps found** (each verified unless noted):

1. **No run store, no step kinds, no event log** for any of this (`jason.workflows` and `data/workflows/` absent).
2. **SOP flaws.** `onboard` step 13 lacks `person`. Step 19 cites Civil Code 5205 for a board's request to its outgoing manager; the stored 5205 speaks of "a member of the association", and no stored provision sets a handover deadline: the cite and the clock need the board's or counsel's reading. The decision to give a notice of termination (CM-2) is not a step in the SOP.
3. **Handoff against build.** The handoff and the information architecture put the records checklist on a Records tab of `#/onboarding`; it is built at `#/setup/records`, and the splitter at `#/setup/split`. The `#/onboarding` tab list (Setup, Find the association, Key documents, Recorded instruments, Accounts, Facts, Request list, The letter, Gaps) has no Records tab. Reconcile the documents.
4. **No loaders or screens** for: the ingest report, a library file's text, a document's revisions, conflicts, a recitation by key, preflight, segments, and OCR review ([../console/handoff-intake-review.md](../console/handoff-intake-review.md)), the confirmations queue (only its `record-readings` loader exists), the context-pack workbench, the collection workspace, quote checking, parcel processes, formation ties, survey coverage. The document-kinds loader `library-kinds` has no view.
5. **No approvals kind for any write in the family.** `local.ingest.apply` and `local.living.reread` are proposed; everything else is a signed record or a terminal act.
6. **Terminal-only applies.** `onboard --apply`, `intake --apply`, `ingest --apply`, and profile patches cannot be done from the console. The built intake route overwrites an earlier answer with no check that the person saw it (journeys, "What the journeys found", (g)).
7. **No follow-ups for this family.** `tasks/followups.py` derives from campaigns, the notice ledger, the response inbox, and request clocks (checked); a slot "waiting on someone else", an onboarding request's asked and chased days, and a member's records-request clock are not derived.
8. **Records-request clock and cost.** The membership-list stage uses five business days labeled 5210(b); the stored 5210(b)(6) and CORP 8330 state more (section 4). `feeCents` is validated only as a non-negative integer: no check against the $10 an hour and $200 caps of 5205(g). Safe at Home (5216) handling in this flow: not verified. A "cover email" has no `gmail-drafts` case.
9. **Child runs.** The workflow model has no child-run link; this page needs a link kind `run` and the rule that a child never completes its parent's gate.
10. **The series' span** (from which period a series expects cells) is an open decision of the record-intake design; until it is decided the run shows only periods that have a pin.
11. **Drive reads as one account.** The chooser lists what jason's Drive account sees, not the signed-in person's.

**Build order for the family**, after the common run store and `jason workflow` (design section 6, steps 1 to 4):
1. `onboard` as a read-only run over `onboarding-session`: gates as `check` steps, questions as `person` steps, no new writes; it is cheapest because the session already computes every state.
2. `record-slot`: fold `record-slots` into slot states; the acts stay on `#/setup/records`.
3. `ingest` with the `ingest` loader.
4. `document-intake`, with the intake queue's writer unchanged.
5. `split-document` (link to the built splitter; the draft's states are the step states).
6. `records-production`, after the clock decision of section 4 row 6, with the cost cap check and a `gmail-drafts` case.
7. `founding-documents` and `key-document`; `parcel-title` last (endpoints not built).
8. `careful-reading` once the workbench and the quote check have screens.

**Decisions for the user.** (a) Signed local records stay `person` steps (recommended) or become `plan` steps under new `local.*` kinds. (b) Whether `onboard` closes on a person's attestation (AD-5) or only when the five gates read open. (c) Whether a child run per instrument is wanted, or one `document-intake` repeat inside `founding-documents`. (d) The membership-list clock, for the board with counsel. (e) Whether the CM-2 decision belongs in the definition.

## 9. A made-up sample run

`onboard`, new association "Example Village HOA" (profile `example-village`), opened 2099-10-01 by Jane Example. Today in the sample is 2099-10-11.

| Step | State | Detail |
|---|---|---|
| ST-1 Choose the community | done | active profile `example-village` matches the run; checked 2099-10-11 |
| ST-2 Start the profile package | done | Jane Example, 2099-10-01 (terminal) |
| ST-3 Look up the county's finds | done | 3 leads parked as questions |
| ST-4 Own facts only | done | `data/spec/example-village.json` |
| ST-5 Google Workspace | needs a person (A) | token missing a scope; run `jason google sign-in --name drive --interactive` |
| ST-6 Integrations | blocked | by ST-5 |
| ST-7 Gate: start | blocked | waits on drive, vault |
| IN-1 Record checklist | done | 61 slots: 34 empty, 6 picked, 5 classified, 8 read, 3 confirmed, 2 not applicable, 1 does not exist, 2 waiting |
| IN-2 Picks | needs a person | 2 picks read as another kind (S6 open on 2 slots) |
| IN-3 Request lists | done | 3 sources asked, 2099-10-02 |
| IN-4 Wait: prior manager, first date | waiting | until 2099-10-15, basis: person |
| IN-5 Ingest: "box 1" | running | child run, I5 needs a person (31 questions) |
| IN-7 Gate: ingest | blocked | 22 library files wait for a kind |
| ES-1 Founding documents | needs a person | F3: "Which is your declaration?" (high stakes), 1 located |
| ES-3 Questions | needs a person | 14 open; 2 answered, waiting on a second person (ES-4) |
| ES-4 Second person | needs a person (R) | Casey Sample may confirm; Jordan Example may not (answered) |
| ES-5 Apply the answers | not started | terminal only |
| ES-7 Gate: establish | blocked | declaration not verified; 1 question about which text is in force |
| OP-2 Roster | waiting | minutes of the 2099-10-20 meeting not yet in hand |
| AD-3 Checklist | ready | 86 items: 51 present, 14 partial, 21 missing |
| CM-1 Read the outgoing agreement | skipped | new association |
| Changed since | banner | the declaration's pinned file changed on 2099-10-09 (size and page count); ES-2 reopened |

Clock strip: "Prior manager's first date: 2099-10-15 (person)"; no legal clock runs on this run. Links: child runs (`ingest` box 1, `record-slot`), 3 jobs (1 running, 1 failed: OCR "no OCR engine"), 14 questions, 2 profile proposals under `data/onboarding/proposals/`. History (newest first): `changed` (pin hash), `attested` (Casey Sample read the question), `job-finished` (lookup), `opened` (Jane Example).

`records-production`, request `2099-10-05--unit-14` (kinds: minutes, interim financial statements; years: this year and one prior):

| Step | State | Detail |
|---|---|---|
| M1 Open | done | received 2099-10-05; clocks start |
| M3 Map kinds | done | minutes held (series, 2 periods read); interim statements held for this year, waiting on the prior manager for last year |
| M4 Not held | waiting | last year's statements: asked 2099-10-06 |
| M6 Withhold or redact | needs a person (M) | one executive-session item excluded as stored text allows; basis to be written by the manager |
| M7 Cost agreed | waiting | the member has the estimate (18000 cents of redaction time, under the 20000 cap) |
| M10 Wait to date | waiting | current-year stage due 2099-10-19 (computed: 10 business days, no holidays subtracted); prior-year stage due 2099-11-04 (30 calendar days) |

## 10. Acceptance criteria

Tests a build can check, on made-up fixtures.

1. A `person (signed)` step with no `by`, or with `jason` as `by`, is refused and writes no event.
2. The second person for ES-4, D12, and F4 is refused when the name equals the answerer's, in any case or spacing; a new answer clears the confirmation and the step returns to `needs a person`.
3. A secret-like answer is refused with `intake.secret_reason`'s reason; the fixture's fake secret never appears in `data/workflows/`, the audit log, or the server log.
4. ST-1 blocks every job step when the active profile differs from the run's subject.
5. A gate step is `done` only when `onboarding.GATES` reads it open now; closing a gate again (an item falls out) reopens the step with a `changed` event; no step marks a gate passed.
6. A child run's `done` does not complete the parent step; the parent shows the child's current state.
7. A file whose hash changed after its reading shows "changed since" with a diff of facts (size, kind, tier, text length, pages), never the text; `ack` clears it once.
8. A wrong-slot pick (S5 differs) leaves the slot at `problem` and S6 open; no act moves a pin until a person confirms; `keep` requires a reason.
9. A split nobody confirmed fills no slot; a part into a full slot is reported as a collision and not written; the original file is unchanged after P6.
10. P6 is the only step that writes PDFs, and no scheduled path or job applies a split.
11. A new version of a known document found by I8 is reported and changes no recited text; D15 needs two different people.
12. I7 refuses to file a file with an open question; a later `jason library` run keeps the ingested rows.
13. The log of any step on a confidential file holds the kind and a masked label, never the name or a Drive id.
14. A director reads what an officer reads at the same level, and the owner view reads none of it.
15. Every route of the family is refused in the owner view (403).
16. A county read that fails leaves the step `failed`, never "none found"; a located number is shown as a lead until the recorded copy is read.
17. `missing` (K7) requires a note naming what was looked for and where; "none exists" and "not applicable" are different answers and neither is ever filled by jason.
18. M3 shows each requested kind with its paragraph of CIV 5200(a); a kind with no holder shows "no holder" and offers S9, never "none exists" inferred.
19. The records-production clock shows the recitations of section 4 rows 4 to 6 beside the computed date, labeled as a computed date; it never reads "satisfied" without the production date a person recorded.
20. `feeCents` above the 5205(g) cap for a redaction estimate shows a warning that the cap is the statute's words, and the manager records the reason; the run never lowers it.
21. A done run's history exports as a `Doc` with evidence addresses and no private value; a re-open shows only steps whose evidence differs.
22. A `wait` step past its date opens a follow-up for a person and does not mark the arrival.
23. Every command a step shows is one that exists in the CLI parser; a terminal-only step shows the `Command` and accepts only a signed attestation.
24. Opening the run page with the server down reads the run from `data/workflows/` without error.
