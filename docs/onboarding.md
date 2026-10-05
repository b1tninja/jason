# Onboarding a new association

Bringing an association into jason is the same work a management company does when it takes one over: gather the association's records and information, then set up the systems that use them. jason writes that work down once, as a checklist any California common interest development shares (`jason.community.onboarding`), and checks it against a profile.

## The checklist

Each item is an `OnboardingItem`:

| Field | What it says |
|---|---|
| `title` | what the item is |
| `why` | the statute that requires the association to keep or give it, or what jason uses it for |
| `sources` | where it usually comes from: the prior manager, the board, the county recorder or assessor, the Secretary of State, the developer, the city, the bank, the insurance agent, the accountant, the reserve specialist, a utility, a vendor, counsel, the owners, the management software |
| `fills` | the `Community` method, record, book, or store it fills |
| `checks` | how jason tells it is there (below) |
| `origins` | where the item came from (below) |
| `fetch` | the jason command that reads it once access is set up; with none, a person supplies it |
| `private` | it names people or accounts: it goes in the private facts (`data/spec/<name>.json`) or the profile's notes, never the specification |

The items fall into fifteen groups, in the order a takeover usually needs them: governing documents and amendments; recorded instruments (maps, plans, deeds, the developer's file); corporate and tax filings; the board, officers, committees, and manager; members, units, and occupants; finances; insurance; contracts and vendors; maintenance, utilities, and life safety; meetings; elections; enforcement; architectural review; records, retention, and pending matters; and system access.

An item's `origins`:

- **law**: a statute requires it. The text is on disk (`jason export-authorities`): records (Civil Code 5200), the annual budget report and policy statement (5300, 5310), the buyer's disclosures (4525, 4528), reserve studies (5550, 5565), balcony inspections (5551), owner information (4041), the managing agent (5375, 5380), insurance (5800-5810), and the statement of information (5405).
- **profile**: jason's own design needs it: a `Community` method, a book (`jason.community.books`), or a store.
- **request**: an incoming manager's transition request list asked for it. A typical list has three parts: what is needed at once to set the association up in the manager's systems; what to send after each month's late fees post until the handover (receivables, updates to the collections list and the owner roster); and what comes on the transition date (records, keys, and property; ledgers; the year's 1099s).
- **follow-up**: the incoming manager asked for it during the transition, after the list: bank signers, start-up funds, how utilities are charged, the board's access to the old portal.
- **handoff**: the board's own knowledge-transfer document for a new manager carried it: templates, manuals, the calendar, building plans, the parking and towing record, keys and codes.

A typical takeover list leaves out items the law or jason needs: the reserve study, the balcony inspection report, the statement of information, the loans, the maps and plans, and the policy statement's addresses. The checklist adds them.

## Checking a profile

```bash
jason onboard                             # the session: progress, the stage gates, the next questions (below)
jason onboard --checklist                 # every item: present, partial, or missing, with the evidence
jason onboard --checklist --group finance --status missing
jason onboard --checklist --write         # keep the report in data/onboarding/ (private)
jason onboard --items                     # the checklist itself
jason onboard --request                   # the items to ask the prior manager for, as a list to send
jason onboard --request "county recorder"
```

The command reads only the profile and the data on disk. It writes nothing to PayHOA, Google, or the mail. Each check is one of:

| Check | Passes when |
|---|---|
| `Method` | a `Community` method or property answers with rows (optionally rows naming some words, or one field set) |
| `Kinds` | the classified library (`jason library`) holds files of those document kinds |
| `Record` | the Civil Code 5200 records inventory pins a holder for the record and finds files in it |
| `InBook` | the profile maps a document into the book (`Community.book_entries()`) |
| `Store` | a store under the data folder has rows, files, or entries |
| `Private` | a private fact file has entries |
| `Setting` | a setting is set (a Keeper record UID) |
| `Fact` | a person's answer for the item is in the profile's private facts, or the note that it is kept in Keeper |
| `Settled` | no intake question of some kinds is open (a stage gate's check) |
| `Verified` | each governing instrument's recorded copy is matched in the county index, and none is read without a stamp (a stage gate's check) |

An item is **present** when every check passes, **partial** when some do, and **missing** when none does or nothing in jason holds it yet. The evidence gives counts and keys only, never a private value. A missing item is a place to look, not a finding that the record does not exist: the association may keep it outside jason. Items marked `[person]` have no command that can read them.

## The session

Taking documents in and answering questions are one guided flow. `jason onboard`, with no flags, is that session. It reads the profile and the data on disk, and writes nothing:

```bash
jason onboard                                  # progress, the stage gates, and the next 5 questions
jason onboard --questions --group finance      # more questions (--stage S, --limit N)
jason onboard --scan                           # park the onboarding questions in the intake queue
jason onboard --answer ID "TEXT" --by NAME     # answer one (a choice's number, or words; "dismiss")
jason onboard --confirm ID --by OTHER          # a second person, for a high-stakes answer
jason onboard --apply                          # answers into records (--replace for a changed private fact)
jason onboard --new KEY --name NAME            # a new association's profile package (below)
```

- **Progress:** present, partial, and missing by checklist group.
- **The stage gates** (`Stage`, `GATES` in `jason.community.onboarding`), in the order a takeover opens. Each is open when its items are present and its own checks pass:

  | Stage | Open once |
  |---|---|
  | start | the units, the management software, the Drive, and the vault are present |
  | ingest | the records map, minutes, budget reports, financial statements, contracts, and insurance policies are present, and no library file waits for a kind (`Settled`) |
  | establish | the declaration with its amendments and annexations, the bylaws, and the articles are present; each recorded copy is matched in the county index and none is read without a stamp (`Verified`); and no question is open about which text is in force (`Settled` on the governing documents: standing, readings differ, before differs, drift) |
  | operate | the board rule and roster, the signers, the bank accounts, the assessments, the fiscal year, the meeting schedule, the notice rules, the schedule's assignments, and the utility accounts are present |
  | adopt | the operating rules, election rules, policies and resolutions, collection and enforcement policies, the architectural procedure, the governing set, and the conflicts are present |

- **The next questions**, ranked by what each answer unblocks ([intake.md](intake.md#the-session)), each with its evidence, its choices, jason's suggestion where it has a lead, and what it unblocks.

### Questions the checklist asks

- **`FACT`:** a fact the checklist needs and no document holds. An item a person supplies carries a `FactAsk`: the question, where the answer goes, whether it is high stakes, the legal clock it sets (the fiscal year's end sets the annual reports' windows), and the library document kinds that may hold a lead. A missing or partial item with a `FactAsk` is asked. A lead pattern (the employer identification number's shape) suggests an answer from those files' text.
  - **The meeting rules.** `board-rule` asks, beside the seats and quorum, what carries a motion and whether a director who discloses an interest and does not vote counts toward the quorum, each with its source: the provision, recited from disk, or counsel's reading, named and labeled (`BoardRule.vote_basis`, `vote_source`, `interested_in_quorum`, `interested_source`). `meeting-schedule` asks the notice of a board meeting the governing documents require and whether it reaches a meeting held solely in executive session (`board_notice_period()`, CIV 4920(b)(3)), and the open-forum time limit the board adopted (`open_forum_limit()`, 4925(b)). Each stays partial until it is on file; none is assumed.
  - **The roster, as it changes.** Two questions are standing (`FactAsk.standing`): asked whatever their item's status, since the roster changes after onboarding. Both are high stakes and append to a private fact topic (`FactAsk.topic`, `jason.community.roster`); an answer not in the form is refused when given.
    - `board-roster` records a change of office, after the minutes record the board's act: `OFFICE; PERSON (or vacant); YYYY-MM-DD; MINUTES`. It is appended to the officers topic. For each office the row the board acted on last is in force (`roster.in_force`).
    - `election-status` records a term: `SEAT; PERSON; START; END (or at the pleasure of the board); ELECTION RECORD; PROVISION`. It is appended to the terms topic, read by `Community.terms()` (`Term`). A term has ended only when its recorded end is past.
- **`MAP`:** which book or Civil Code 5200 record a document fills. jason asks for a book a checklist item looks for that no document fills, where the outlines or the library hold a candidate. It also asks for a 5200 record held in classified files that no folder is pinned to hold, suggesting the folder that holds most of them.

### Where an answer goes

| The answer is | It becomes |
|---|---|
| a private fact (people, account numbers, the tax ID) | an entry under `facts` in `data/spec/<profile>.json`, keyed by the checklist item, with who answered and when. The file is copied to `data/spec/backups/` first, the change is shown as a diff, and a different answer already there is refused unless `--replace` is given. The item's `Fact` check then passes, and only that it is recorded is reported. |
| a roster record (a change of office, a term) | rows appended to its topic, `data/spec/<profile>/officers.json` or `terms.json` (the file `facts(topic)` reads), each signed. A backup and a diff first. A row already there is not added twice, and nothing there is changed. |
| a secret (keys and codes, a portal's sign-in) | a record that it is kept in Keeper, under the record the person named, with no value. An answer that looks like a secret (a password, a PIN or code given with its digits, a key or token with its value, a long token) is refused when it is given and is never stored. |
| a profile fact (a book mapping, a pinned folder, the board's seats) | a proposed change under `data/onboarding/proposals/`. Where jason can write the row (a `BookEntry`, a record pinned on an existing library folder row) it is a `.patch` against the profile's own file, for `git apply`. Otherwise it is a `.md` with the answer and the `Community` method it fills, for a person to write. jason never edits the profile. The row names the question and the day, never the person. |

- **A second person.** A high-stakes answer waits for a second person's `--confirm` before `--apply` takes it: which text is in force, whether an instrument was recorded, or a fact marked high stakes (the bank signers). The one confirming is not the one who answered. A new answer clears the confirmation.
- **Every answer is signed.** Who answered and when, and who confirmed and when.
- **The same queue.** Answering, confirming, and applying use the intake queue's own paths (`jason intake`). `jason intake --scan` also parks these questions. Over MCP, `answer_intake_question` answers one (parking a question `next_questions` listed first, as `--answer` does) and `onboarding_confirm` is the second person. `onboarding_status` and `next_questions` read the session ([mcp.md](mcp.md)).

## Connecting integrations (TODO)

The design is [integrations-design.md](integrations-design.md) (integrations, the vault, defaults from rate limits) and [scheduler-daemon-design.md](scheduler-daemon-design.md); the screens and setup dialogs are [console/handoff-instance-and-integrations.md](console/handoff-instance-and-integrations.md).

Onboarding a real association means an administrator connects its integrations. Today each is set up at a terminal by a person ([setup.md](setup.md)), and the console's setup tab shows the command, never a field:
- **Google Workspace:** the Cloud project and its APIs, an OAuth web-application client (consent screen, scopes, redirect URIs for jason-web's sign-in), the token, the Drive home, the groups, the calendar; later jason's own mailbox.
- **Keeper:** the vault and the records every other credential lives in; `jason login`, with device approval.
- **PayHOA:** the organization id and its Keeper record.
- **Zoom:** the app (`jason zoom --store-app`) and its Keeper record.
- **The others a profile names:** PostScanMail, a vendor's portal, the county's sources.

**To build:** an administrator's flow for connecting each integration. What it must keep:
- the administrator only, signed in, never while viewing as someone else;
- no secret typed into, shown in, logged by, or stored by the console: the secret goes to Keeper, and the console holds the record's name;
- the narrowest scope that does the job, read-only first, with the scopes listed before consent;
- a connection checked by a read before it counts as connected, and who connected it and when recorded;
- revoking and rotating, as visible as connecting;
- a profile's own facts (which services it uses) staying in the profile, and the onboarding checklist computing whether each is connected.

Until it is built, the write route (`POST /api/write/intake/<id>`) still accepts an answer naming a Keeper record, as `jason onboard --answer` and the MCP tool do; `intake.secret_reason` refuses anything that looks like a secret.

## Starting a new association

A new association is a new profile package ([profiles.md](profiles.md)). `jason onboard --new` writes one from jason's general templates (`src/jason/templates/profile/`):

```bash
jason onboard --new oakview --name "Oakview Example Association" --county "Example County"
jason onboard --new oakview --name "Oakview Example Association" --county Sacramento --lookup
jason onboard --new oakview --name "Oakview Example Association" --dir D:\profiles\oakview
jason onboard --lookup                      # the lookup again, for the active profile
```

- **What it writes.** The package goes beside the default profile unless `--dir` says where. It holds:
  - a `Community` subclass with only the identity given: the name, the key, and the region from the county;
  - one empty module per rule-row family (documents, anchors, pins, the declaration, books, outlines, living documents, conflicts, parcels, buildings, developers, the board and banking, obligations, the schedule, notices, transactions, insurance, utilities, vendors, cases, letter templates, response clocks, lessons, forms). Each module's docstring says what goes there, which `Community` method reads it, and which page here describes it;
  - `docs/README.md`, the instance reference;
  - `notes/`, with a `.gitignore` that keeps everything in it out of git.

  It also writes `data/spec/<key>.json` with empty private facts.
- **What it refuses.** It never overwrites a package or a private facts file. It refuses a key that is:
  - a book's record address key (`decl`, `rules`, ...);
  - a document key or alias the active profile's addresses answer to;
  - another profile, or a jason-mcp tool set (`board`, `governance`, `onboarding`, `all`).
- **Where its stores go.** A profile other than the default keeps its stores in `data/<key>/` unless `PAYHOA_CATALOG` names a folder. The command prints the `.env` lines that make it active (`JASON_PROFILE`, and `JASON_PROFILE_DIR` when the package is not where jason looks).
- **The first session.** `JASON_PROFILE=<key> jason onboard` then shows every stage gate closed and nearly every item missing, with the first questions to ask.
- **Leads, with `--lookup`.** jason searches the county recorder's public index for the association's name, read-only, with the county's existing reader (`jason.tasks.onboarding_lookup`). It reads no source that needs a sign-in, and it adds no scraper.
  - **What it finds.** The declaration, amendments, annexations, condominium plans, and bylaws recorded under the name, and the spellings the index uses for the association.
  - **Where finds go.** Each becomes a lead under `leads` in the private facts file, never a row in the profile. The session asks each lead as a `FACT` question with the found value as its suggestion, while its checklist item is missing. Leads about the declaration and its amendments are high stakes.
  - **Who decides.** A person answers each lead question. The answer becomes a proposed change to the profile for a person to apply. A hit is not a pin.
  - **Limits.** jason has no reader for the Secretary of State's business search, so the corporate filings stay questions for a person. A county with no reader is a note, not a failure.
- **Locating its recorded documents, with `--locate`.** `jason onboard --locate` (for the active profile, or with `--new ... --county`) finds the association's recorded documents in the county index, read-only (`jason.tasks.document_locator`), in three searches:
  - **By name.** Every spelling the county's association directory holds: each instrument a party of which is the association (common-area deeds and easements, amendments it recorded, annexations, its statement, judgments). Its own assessment liens are counted, not listed.
  - **Beside.** The six numbers on either side of each governing instrument found, and of the association's earliest named instruments. A community's formation is recorded together, so the declaration, the map, and the condominium plan sit beside the first deed of common area. A same-day neighbor counts when it shares the builder or names the association.
  - **The builder.** The governing filings of the builders on those instruments: the other phases' annexations, but possibly another community's, so they are asked, never suggested.
  - **What it gives.** Each located instrument serves a checklist item by its filing name (rule rows in `jason.community.locator`): declaration, amendments, annexations, condominium plans, maps, bylaws, common-area deeds, litigation, the statement. Each item becomes a lead whose choices are the document numbers, and the instruments tied by name or recorded beside its documents are the suggestion. The declaration and its amendments are high stakes. The board's list is written to `data/onboarding/<profile>-documents-located.md` (private): each document's number, date, filing, why it is thought the association's, its parties and the people on it, and the question, "Do you hold a copy of each?" A located instrument is a lead, not a pin.
  - **What it cannot find.** A declaration that predates the index's names, or one recorded under the builder alone with nothing of the association's beside it, is listed under "Not located" with the ask for its recording number.
  - **The result as data.** Beside the board's list, `data/onboarding/<profile>-documents-located.json` holds the same result (`Location.to_dict`, read back with `Location.from_dict`): the association, county, `located_at`, searches, liens counted, spellings, each item located with its instruments (number, recorded, filing, `tie` and `tie_label`, `strong`, `via`, the business and association `parties`, and the private persons as `people`: each name with its index side, R grantor or E grantee), the core items `not_located` with their ask, the notes, and the caveats. Both files are replaced whole. Every party is kept: owners' names are P1 ([console/security-and-privacy.md](console/security-and-privacy.md)), shown in the board's list, the console, and jason-mcp to the people who work with them; they stay in jason's private data (`data/onboarding/`) and are never committed. The console (`GET /api/documents-located`) and jason-mcp (`documents_located`) read this file and never search the county.
  - **Another association.** `--locate --name "<name>"` for a name that is not the profile's association (by directory key) writes `data/onboarding/<county>-<name key>-documents-located.*` and keeps no lead in the profile's facts. To keep its leads, start it: `--new KEY --name "<name>" --county C --locate`.
  - **From the console, as a job.** The "locate" action (`POST /api/write/documents-located/locate` with `{county, name, by}`) queues `jason onboard --locate --county C [--name N]` on the queue's county lane ([jobs.md](jobs.md)) and returns the job; `jason worker` runs it. Who asked is kept in `data/onboarding/locate-requests.jsonl`. A locate already queued or running for the same files is returned instead of a second. Until the job finishes, `GET /api/documents-located` shows the job (`queued`, `running`, or `failed` since the last result) beside the saved result or the command.
- **Choosing the association, with `--associations`.** For a county asspy has surveyed (`python -m asspy.associations_cli placer --survey 2001-01 YYYY-MM`, then `--link`), `jason onboard --associations --county Placer [--find oaks]` lists the owners', commercial, and maintenance associations its recorder's index shows. Each row gives the kind, the standing (confirmed: it records assessment liens or its declaration), the years it recorded, and the evidence. A person picks the association and starts it with `--new KEY --name "<name>" --county Placer --lookup`. The lookup then searches the index under every spelling the directory holds (an older `... HOA` among them, up to three) and offers those spellings first. A row is a lead, not a pin. How the directory is built is asspy's `API.md` ("Associations in a county"). The console's `GET /api/associations?county=&q=&limit=` and jason-mcp's `association_directory` give the same directory as data (`onboarding_lookup.directory_search`): each row with its key, spellings, evidence, the count of governing instruments that name it or were linked to it, and the search score, the directory's summary beside them, and, for a county not surveyed, the asspy command that surveys it.

## Onboarding by conversation

The questions can be answered in a conversation with an assistant instead of at the command line. The assistant reads the session, asks one question at a time, and records each answer in the person's name. The same tools serve every client:

| Tool | What it does |
|---|---|
| `onboarding_status` | the progress, the gates, and the queue |
| `next_questions` | the next questions, ranked |
| `answer_intake_question` | records one person's answer (**writes**) |
| `intake_questions` | with `awaiting_confirmation`, the answers waiting for a second person |
| `onboarding_confirm` | the second person's confirmation (**writes**) |
| `association_directory` | the county's associations from asspy's directory, searched by words (read only) |
| `documents_located` | the recorded documents `jason onboard --locate` last saved, or the command (read only) |

`jason-mcp --profile onboarding` serves just these seven, with two prompts (`jason.mcp.prompts`): `onboard`, the conversation, and `onboard_review`, a second person confirming the high-stakes answers. The governance set carries the first five and the prompts; the full set carries all seven (`jason.mcp.discovery` holds the last two, which never read the county). The board set (`--profile board`) is unchanged: onboarding happens once, and a client chooses better from fewer tools.

- **A client without MCP prompts.** Register `jason-mcp --profile onboarding` in it and put the text below in its system prompt, which then carries the steps. Register the board set again when onboarding is done.
- **Claude Desktop.** Add jason-mcp to `claude_desktop_config.json`, with `"args": ["--profile", "onboarding"]` and `"env": {"JASON_CWD": "<the jason folder>", "JASON_PROFILE": "<key>"}`. Then choose the `onboard` or `onboard_review` prompt. The text below also serves as a project's instructions.

The system prompt (it is `system_prompt()` in `jason.mcp.prompts`, and a test keeps this copy the same):

```text
You help the people who run a homeowners association bring it into jason, a records and compliance assistant, by answering jason's onboarding questions through its tools. Ask for the person's full name first; it is the by of every answer.

When someone asks to onboard, or to answer jason's questions:

1. Call onboarding_status. Say in two or three sentences where onboarding stands: the stage reached, the first closed stage gate and what it waits on, and how many questions are open. Repeat its caveat.
2. Call next_questions with limit 1. Take one question at a time, in the order given; never batch them.
3. Show the question as jason asked it, then its evidence and what answering it unblocks. Number the choices as given. If there is a suggestion, say it is jason's lead from the evidence (name the source), not an answer.
4. Ask the person for the answer. Do not answer for them, guess, or fill in from your own knowledge or from a file name. If they do not know, ask who would (the evidence says where it usually comes from), and go on to the next question.
5. Record the answer with answer_intake_question: the question's id, the person's answer in their own words (or the number of the choice they picked), and by set to the person's full name. Never use your own name, "assistant", or "jason" as by.
6. Never accept a secret. If the answer would be a password, a PIN, a gate or lock box code, a sign-in, a key or token, or a full account number when the question asks only where it is kept, do not record it: tell the person it belongs in Keeper, the association's password vault, ask them to save it there, and record only the Keeper record's name (its title, never its value or id). If answer_intake_question refuses an answer as a secret, say so and do the same.
7. If the question is high stakes (highStakes is true, or the answer's reply says a second person confirms it), tell the person the answer is recorded but is not applied until a second person confirms it in a review (the onboard_review prompt, or a conversation that asks to review answers) or with jason onboard --confirm. Stop there for that question: never confirm it yourself, and never ask the person who answered to confirm it.
8. Go back to next_questions for as long as the person wants to continue.
9. To finish, call onboarding_status again and show the progress: present, partial, and missing by group, what this session answered, and which answers wait for a second person. Say that answers become records only when someone runs jason onboard --apply, which shows each change before it makes it, and that a change to the profile is a proposal a person applies.

When someone asks to review or confirm answers:

1. Call intake_questions with awaiting_confirmation true. If it lists none, say so and stop.
2. Take one question at a time. Show the question, its evidence, the answer given, and who gave it and when. Do not argue for the answer: let the person check it against the source the evidence names.
3. If the person reviewing is the one who answered, stop: a person cannot confirm their own answer. Another person confirms it.
4. If the person agrees, call onboarding_confirm with the question's id and by set to their full name. If they do not, do not confirm it: record the answer they give with answer_intake_question (by set to their name), which clears any confirmation and waits for another person in turn.
5. Never accept a secret: the same rule as when answering. A secret belongs in Keeper; only the record's name is kept.
6. To finish, say how many answers were confirmed and how many still wait, and that jason onboard --apply makes the confirmed answers records.

Throughout:
- The tools read jason's records on disk. They never reach the management software, Google, or the mail, and they decide nothing: every answer is a person's, signed with their name.
- A missing checklist item is a place to look, not a finding that the record does not exist.
- Quote a document only from what a tool returned, never from its file name.
- Keep private facts (people, account numbers) to the answer itself; never repeat a private value once recorded.
```

## Ingest

Taking the association's documents in is part of onboarding: the prior manager's export, a box of scans, a Drive folder the board shares. `jason ingest` runs the library's whole chain over them as one step (`jason.tasks.ingest`):

```bash
jason ingest "D:\handover\Records"                 # a dry run: inventory, read, classify, version, propose; files nothing
jason ingest handover.zip --park                   # also park the questions in the intake queue
jason ingest "https://drive.google.com/drive/folders/ID"   # a Drive folder, read-only (or drive:ID)
jason ingest a.pdf b.pdf --apply                   # file the ready files in the library
jason ingest SOURCE --model                        # ask the local model about files no rule placed
jason ingest --gate                                # what the last ingest says, for the session's ingest stage
```

1. **Inventory.** Every file, with its sha256, type, size, where it came from, and the dates it carries: the file's own times, a PDF's metadata, a zip entry's time, Drive's last change, a date in its name, and the dates its words print. Files with the same hash are one file; a hash the library already holds is noted and not taken in again. A zip's members and a Drive folder's files are staged under `data/onboarding/ingest/`; a Google Doc comes as a Word file. Drive is only read, and fails fast without a token.
2. **Extract and classify.** The library's readers: the text layer first, then OCR when it is empty (`--no-ocr` reads text layers only). The library's chain: a person's earlier answer, the profile's kind rules, the phrase rules, then the local model, only with `--model` (it runs preflight and holds the GPU lock). A miss, or a model's answer below 0.7, is a `CLASSIFY` question with the file's name, its first words, and the candidate kinds.
3. **Analyse the kind, then read by kind.** The chain stops at its first match, so a name rule decides before the words are read. The kind analysis (`jason.community.kind_analysis`) weighs the alternatives for each new file:
   - **Rules.** Every phrase rule votes, a title phrase more than a body phrase.
   - **Shape.** `SIGNALS` rows read the document's structure: a parties clause, a signature block, an e-signature audit, a recorder's stamp, motions and votes, a letter's salutation, a form's blanks, many amounts, numbered sections.
   - **Readers.** Each leading kind's own reader (`document_models`) says whether it recognizes the text and how many of its fields it finds.
   - **Parties.** For an agreement, it checks whether the association is a party at all.

   It never changes a kind on its own. A person's answer stands. Each verdict:
   - **confirmed:** the evidence agrees with the chain's kind.
   - **disagrees:** another kind reads better, or the file is an agreement between others (a lender's assignment filed under a manager's name). The verdict is a `CLASSIFY` question with the evidence, and the file is held.
   - **weak:** little in the text supports the chain's kind. It is also a question.
   - **proposed:** a file with no kind gets a suggested kind on its question; the miss stays a miss until a person answers.
   - **unknown:** no kind leads.

   Then each kind's readers run (`jason.community.kind_readers`, rows like the rest):
   - the kind's document model, giving its typed record and findings;
   - for an agreement, its terms, deliverables, and findings (docs/contracts.md), with a model's review under `--terms-model ollama|bedrock`;
   - for a governing document, the phrase grammar's norms, counted.

   A questioned file is read both as its chain's kind and as the suggested one, so the person who answers sees both readings. A reader's failure is reported on the file's row and never stops the run.
4. **Version.** A file that holds enough of a known document's current text (the revision detector's test, by shared letter runs) is a version of it: the current text, a version on record, one not on record, or an excerpt, dated by what it carries. A new version of a living or citable document is reported and never applied. A packet that carries a document inside it (an annual disclosure with the collection policy) is a copy, not a version. Files no known document claims are grouped with each other the same way, for the kinds of a living book only (monthly statements share boilerplate, not a text).
5. **File.** Each file's book (`Community.book_entries()` for a known document, else its kind's book), its Civil Code 5200 records, and its library folder (where the library files that kind, preferring a folder pinned to its record). A classified file no folder holds is a `MAP` question; its answer files it on the next run and becomes a proposed profile change. A dry run by default: `--apply` copies the ready files into `data/library/files` and records them in `library.db` with their hash, where each came from, its dates, and its classification (`documents`, and `ingested`, which a `jason library` run keeps). A file with a question open is held. Nothing goes to Drive or PayHOA.
6. **Report.** `data/onboarding/ingest-<day>.md` and `.json`, private because they name the files: counts by kind, book, record, and folder; duplicates; the kind analysis and each file's readings; each contract's terms; versions and copies; the questions; and the checklist items and stage gates that moved, the checklist run before and after (after: as if the ready files were filed and the questions parked). Questions are parked in the intake queue only with `--park`; otherwise they are listed.

The session's **ingest** stage reads the last report (`jason.tasks.ingest.gate`): when it ran and in which mode, the files filed and held, the versions found, the questions still open in the queue, and the items it moved.

## From the checklist to the first profile

1. **Ask.** Send `jason onboard --request` to the prior manager, and the other sources' lists to the board, counsel, and the agent. Paper records come in boxes with a contents list for each.
2. **Keep what is private apart.** People, account numbers, codes, and figures go in `data/spec/<name>.json` or the profile's `notes/`. Passwords and codes go in the vault, never in a document or an email.
3. **Write the profile.** A new `Community` subclass in its own package (profiles.md), started by `jason onboard --new` ([above](#starting-a-new-association)). Start with the facts the checklist marks as the board's: buildings and units, the board rule, the meeting schedule, the fiscal year, bank accounts by purpose and last digits, insurance policies, utility accounts, the obligations, and the schedule's assignments.
4. **Map the documents.** Pin the library folders and Drive roots to the Civil Code 5200 records, add the kind rules, and map each governing document into its book.
5. **Fetch.** Run the commands the checklist names (`jason sync-catalog`, `jason library`, `jason outlines --fetch`, the county and utility syncs), and `jason ingest` for documents that come from outside the management software (above).
6. **Check again.** `jason onboard` until what is missing is only what a person still has to supply, and each of those has an owner in the schedule. Answer the questions in the order the session gives them.

When an item turns out to be needed that the checklist does not have, add a row to `ITEMS`: what it is, why, where it comes from, what it fills, and how to check it.

This association: the request and response from its own takeover are in its private notes (`mystique/notes/onboarding/`).
