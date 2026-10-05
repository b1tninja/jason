# Onboarding

A tab of `#/onboarding`: the onboarding session (built) · phase 2 · CLI: `jason onboard`, `jason onboard --questions`, `jason intake`

## In the console

**Communities** (`#/communities`) and **Onboarding** (`#/onboarding`) are built from [onboarding-ux.md](../../onboarding-ux.md): the portal of every profile with the active one's progress; and, for the active community, its accounts (set or not, never a value), its facts by duty, the request list a manager sends with the stores' own reading beside each item, its letter, and the gaps. A person records what they did about each item (`POST /api/onboarding/<key>`).

**What this spec adds** is the **onboarding session** (`jason onboard`), as a tab of `#/onboarding` (this spec's "band"): the stage gates in order, the open questions ranked by what each answer unblocks, a signed answer to each, and a second person on a high-stakes answer. The request list says what to ask for; the session says what is still unanswered and what each answer unlocks. **It is built**, as the **Setup** tab of `#/onboarding` (`ui/src/views/OnboardingSetup.tsx`): the loader is `GET /api/onboarding-session` (over `jason.api.onboarding_status`; `?limit=`, `?group=`, `?stage=`, `?kinds=`), whose `next` field is the ranked questions, so there is no separate `next-questions` loader. The write is `POST /api/write/intake/<id>` with `{answer, by}`, or `{confirm: true, by}` for the second person, which queues `answer_intake_question` and `onboarding_confirm` for a signed-in roster person (both take `by`); it writes only `data/intake/asks.json`. The components are `StageSteps`, `QuestionCard`, and `SecondConfirm`, built. The tab does not show the proposals band (the patch files under `data/onboarding/proposals/`); the layouts below show the whole design.

## Finding the association and its documents

A tab of `#/onboarding`, **Find the association** (after **Setup**), comes before the document questions. Onboarding a community starts with choosing the association from the county's directory, then locating its recorded documents (declaration, amendments, annexations, condominium plans, maps, bylaws, common-area deeds, litigation, the statement) and asking the board about each: "Which is your declaration? Do you hold a copy of each?" It is built from `AssociationPicker` and `DocumentLocator` (`ui/src/components`), composed by `FindAssociation` in `OnboardingView.tsx`.

### Data

| Part | Source |
|---|---|
| The county's directory | `GET /api/associations?county=placer&q=oaks&limit=25`: `{county, surveyed, summary: {byStanding, byKind, ...}, results: [{key, name, kind, standing, first, last, spellings, evidence, governing, links, score}], caveats, command}`. Built from the county recorder's public index by asspy's survey. A row is an association-named party, never an owner |
| The documents located | `GET /api/documents-located` (the active profile) or `?county=&name=` (the association chosen): `{association, county, located_at, searches, liens, spellings, items: [{item, title, question, stakes, located: [{number, recorded, filing, tie, tie_label, strong, via, parties, people: [{name, side}]}]}], not_located: [{item, title, ask}], notes, caveats, job?}`, or `{missing: true, command, note, job?}` (`jason.tasks.document_locator`) |
| Locating | `POST /api/write/documents-located/locate` with `{county, name, by}` → `{job: {id, status}, command}`. It queues a read job; the console never calls the county. Empty `county` and `name` mean the active profile |

### Layout

```
+-------------------------------------------------------------------------------------------+
| 1. CHOOSE THE ASSOCIATION                                                                 |
| County [Placer v]   Association's name [oaks____________________]                         |
| 25 associations match "oaks". Arrow keys move; Enter chooses.             (role=status)   |
| The Placer directory holds 412 associations: 230 confirmed · 120 likely · 62 named.       |
| +---------------------------------------------------------------------------------------+ |
| | EXAMPLE OAKS OWNERS ASSN                                                   (listbox)  | |
| | [homeowners] [confirmed] recorded from 2001 through 2024                              | |
| | 386 assessment liens · 15 declaration filings · 3 spellings                           | |
| +---------------------------------------------------------------------------------------+ |
| A directory row is a lead, not a pin.                                                     |
+-------------------------------------------------------------------------------------------+
| 2. LOCATE THE RECORDED DOCUMENTS OF EXAMPLE OAKS OWNERS ASSN                              |
| [Command] jason onboard --new example-oaks --name "..." --county placer --locate          |
| [By checklist item] [The board's list]                                                    |
| Recorded documents located for Example Village HOA                                        |
| Placer recorder's public index, Oct 2, 2026 · 42 searches · 3 documents in 2 checklist    |
|   items · 386 of the association's own assessment liens and releases, counted, not listed |
| > Searched under 2 spellings                                                              |
| THE DECLARATION (CC&RS)    1 located: 1 strong tie    [a second person confirms]          |
| Which is the association's declaration? Do you hold a copy of each?                       |
| Document      Recorded     Filing       Why it is thought the association's  Found by  Parties |
| 2004-0012345  Mar 1, 2004  DECLARATION  [names the association]             its name  EXAMPLE HOMES INC |
| Answered in the onboarding questions as fact:lookup:located-declaration.                  |
| ANNEXATIONS ... [the builder's filing] may be another community's                         |
| NOT LOCATED: The subdivision maps. Ask the board or the prior manager for the number.     |
| NOTES · CAVEATS                                                                           |
+-------------------------------------------------------------------------------------------+
| 3. ASK THE BOARD ABOUT EACH                                                               |
| Each item located becomes a FACT question ...  [Command] jason onboard --questions        |
+-------------------------------------------------------------------------------------------+
```

### States

- **Directory not built for the county** (`surveyed: false`): "The Sacramento directory is not built yet." and the `Command` that builds it (the response's `command`). No list.
- **No match:** "No association in the Placer directory matches "oaks"." Never an empty table.
- **Chosen:** the search gives way to the chosen row: its facts, its governing instruments, its spellings behind "3 spellings in the index", and **Choose another**. Choosing writes nothing. The next card names the association and shows the terminal command that starts its profile (`jason onboard --new KEY --name NAME --county COUNTY --locate`); the console never writes a profile.
- **Nothing located yet** (`missing: true`): the tool's note, its command, and **Locate documents** with "Queued by" pre-filled from the console's person. It goes through `Confirm`: "Queue a read of the Placer recorder's public index for NAME, as Jane Example. ... nothing is written to the county, PayHOA, or the profile."
- **Queued or running:** "Queued: job 7. jason reads the county's public index in the background; this page checks again every 4 seconds." with a link to the job queue, in `role="status"`. The page reads the result again while the job is queued or running, keeping what it already shows.
- **Failed or cancelled job:** "Job 9 failed. Nothing was located." in `role="alert"`, a link to its log, and the action again.
- **Writes off** (405): "Writes are off in this console, so it cannot queue the job. Nothing was queued." and the command to run in a terminal.
- **Located** (cached): grouped by checklist item, with **Read the index again** behind a disclosure, and the board's list.

### Words

- A directory row is "a lead, not a pin". A located document is "a lead, not a pin: the recorded copy is read before it is pinned." Both are always visible, with the tool's own caveats (`Caveats`).
- Standing is asspy's word (confirmed, likely, named), with its meaning on hover: "records assessment liens or a declaration", "records other association business", "the name alone".
- Evidence in words, largest first: "386 assessment liens · 15 declaration filings · 1 property filing".
- Years: "recorded from 2004 through 2025", never a dash range.
- Ties are the locator's words. "Names the association" and "recorded with the association's documents" are strong. "The builder's filing" is shown with "may be another community's", and is asked about, never suggested.
- An item whose answer decides which words are in force (the declaration, the amendments) carries "a second person confirms".
- The association's own liens are "counted, not listed". `parties` are the business and association parties; `people` are the private persons on the instrument as indexed, by name with their side (R grantor, E grantee). Owners' names are P1 ([security-and-privacy.md](../security-and-privacy.md)): shown here to the people who work with them, kept in jason's private data, never committed.
- The recorded instruments' graph opens masked (the shared view). **Show owners' names** asks for the person's name, reads the graph again with the names, and says the reveal was logged; **Hide names** masks them again ([instrument-graph.md](../../instrument-graph.md#privacy)).

### The answers

The located items are not answered here. Each becomes a FACT question in the onboarding session (subject `fact:lookup:located-ITEM`, from `onboarding_session.lead_asks`), answered with `QuestionCard` and a name, and confirmed by a second person when it has stakes. Each group names its question's subject, and links to it when the view passes `questionHref`. The session is built (the Setup tab), but `FindAssociation` passes no `questionHref` yet, so the third card still shows `jason onboard --questions`.

**The board's list** is the same data as a printable checklist: for each document, "We hold a copy" and "Order a copy" boxes to mark on paper. **Print the board's list** prints only the list. The page records no mark.

### Accessibility

- The search is a WAI-ARIA combobox (`role="combobox"`, `aria-expanded`, `aria-controls`, `aria-activedescendant`, `aria-autocomplete="list"`) over a `role="listbox"`. Down and Up move the active option, Enter chooses it, and Escape closes the list, then clears the words. Focus stays in the box; a click on an option does not take it. **Choose another** returns focus to the box.
- The result count and "Searching the directory…" are a `role="status"` region, announced without moving focus. So are the job line and the name check. A failed job is `role="alert"`.
- Every control has a visible label (County, Association's name, Queued by). The located tables have captions ("Annexations: documents located, oldest first"), header cells, and sortable headers. Each item is a region named by its heading.
- Every tie, standing, and stake is a word; the badge's tone only repeats it. Colors are the tokens (`--accent`, `--warn`, `--muted`, `--line`), in both schemes.
- The print boxes are hidden from a screen reader and labeled "to mark on paper". There are no on-screen checkboxes that would look like a record.

## Purpose and personas

Taking an association on: the checklist read against the profile and the data on disk, the stage gates in order, and the open questions ranked by what each answer unblocks. A person answers, a second person confirms the high-stakes answers, and the answers become records.

- **Manager:** answers questions, signed with their name. Applies answers through the CLI.
- **Director, Treasurer, Secretary:** answer the questions in their area, and act as the second person on a high-stakes answer they did not give.
- **Reviewer:** confirms high-stakes answers.
- **Counsel:** no access.

The band shows while any stage gate is closed (`onboarding.GATES`: its checks have not all passed). Once every gate is open, it shrinks to one line.

## Data

| Part | Source |
|---|---|
| Status | `jason.api.onboarding_status()` → `onboarding_session.status_dict`: `title`, `progress` (present, partial, missing), `groups[]`, `stage` (the first closed gate, or "operating"), `gates[]` (`stage`, `title`, `open`, `opensWhen`, `waiting[]`, `checks[]`, and the ingest report for the ingest stage), `questions` (`open`, `byKind`, `answeredNotApplied`, `notYetInQueue`). The caveat: "A gate is jason's reading of the checklist; the board decides what is done." |
| The next questions | `jason.api.next_questions(limit, group, stage)`: each `id`, `kind` (FACT, MAP, and the intake kinds), `subject`, `question`, `choices`, `suggestion`, `likely`, `evidence`, `priority`, `unblocks` (items, gates, records, clocks, sections), `serves`, `highStakes`, `inQueue`. The caveat: "A suggestion is jason's lead, not an answer…" |
| Answered, waiting on a second person | `jason.api.intake_questions(awaiting_confirmation=True)`: `answer`, `answeredBy`, `answeredAt`, `highStakes`, `confirmedBy` |
| Answered, not yet applied | `status_dict(...)["questions"]["answeredNotApplied"]`, and `intake_questions(status="answered")` |
| Proposals | The patch files under `data/onboarding/proposals/` |

**Where an answer goes** is part of the question (`onboarding_session._RECORD_ANSWER`), and the screen shows it under the question:
- "The answer goes in the private facts (data/spec), never the specification."
- "The answer becomes a proposed change to the profile, for a person to review and apply."
- "Only the Keeper record's name is kept, never a password or code."

## Layout

```
+------------------------------------------------------------------------------------------+
| Onboarding: Example Village HOA                                                          |
| [start: gate open] > [ingest: gate open] > [establish: working now] > [operate] > [adopt]  |
| Establish's gate is closed. It waits on: insurance policies (partial), bank signers       |
| (missing), 2 questions                                                                     |
| A gate is jason's reading of the checklist; the board decides what is done.              |
+------------------------------------------------------------------------------------------+
| PROGRESS  86 items: 51 present · 14 partial · 21 missing                                 |
| governing 18/20 · finance 9/16 · insurance 3/8 · records 12/14 · ... [by group]          |
+------------------------------------------------------------------------------------------+
| WAITING ON A SECOND PERSON (1)                                                           |
| [SecondConfirm] Which version of the declaration is in force?                            |
|   Answer: the restated declaration of 2090, with Amendment 2                             |
|   Answered by Jordan Example, Oct 2, 14:10                                               |
|   Your full name [________________]  Someone other than Jordan Example.                  |
|                                                         [Confirm the answer]              |
+------------------------------------------------------------------------------------------+
| NEXT QUESTIONS                         Group [All v] Stage [establish v]                  |
| [QuestionCard]                                                                           |
| FACT · high stakes · priority 9                                                          |
| Who are the signers on the association's bank accounts? The answer goes in the private   |
| facts (data/spec), never the specification.                                              |
| Unblocks: checklist "bank signers" (missing) · gate establish · 1 clock                  |
| Evidence: checklist bank-signers is missing: no signer on record · lead: the library     |
|   holds 2 bank statement files                                                           |
| Answer  ( ) 1. Director A and Director B   <- suggested                                  |
|         ( ) 2. ...                                                                       |
|         ( ) In my own words [__________________________]                                 |
| Answered by [Jane Example]                                    [Save the answer]           |
| A high-stakes answer is applied only after a second person confirms it.                  |
+------------------------------------------------------------------------------------------+
| ANSWERED, NOT YET APPLIED (4)                                                            |
| Apply them in a terminal: jason onboard --apply [copy]. A high-stakes answer waits for a |
| second person first.                                                                     |
+------------------------------------------------------------------------------------------+
| PROPOSALS (2 patches in data/onboarding/proposals/)  [read]                              |
| A person applies a patch with git apply. jason never changes the profile.                |
+------------------------------------------------------------------------------------------+
```

## Components

`StageSteps` (each stage's gate in words: "Gate open" once its checks pass, or "Gate closed" with what it waits on; `aria-current="step"` on the stage being worked), `Card`, `QuestionCard` (what it unblocks, the question, jason's suggestion labeled and never pre-selected, the evidence, and the answer behind `Confirm` as a named person), `SecondConfirm` (the second person on a high-stakes answer; the same component as an approval's), `Evidence`, `Pill`, `Command`, `RemoteView`, `ReadingLabel` (a suggestion is "jason's suggestion").

## Actions

| Control | Does | Approval? | CLI |
|---|---|---|---|
| Save the answer | `api.answer_intake_question(id, answer, by)`: writes only `data/intake/asks.json`. An onboarding question not yet in the queue is parked first | No approval: a signed `data/` record, not an engine kind | `jason onboard --answer ID TEXT --by NAME` |
| Dismiss a question | The same, with the answer "dismiss" | Signed | `jason onboard --answer ID dismiss --by NAME` |
| Confirm the answer (second person) | `api.onboarding_confirm(id, by)`. Refused for the name that answered | Signed by a second, distinct person (`intake.confirm`) | `jason onboard --confirm ID --by NAME` |
| Park the onboarding questions | shown as a command | No | `jason onboard --scan` |
| Look up public records | shown as a command: a read-only search of the county recorder's public index; each find becomes a FACT question with the found value as its suggestion | No | `jason onboard --lookup` |
| Filter by group, stage | the loader's `group`, `stage` | No | `jason onboard --questions --group G --stage S` |
| Read a proposal | Shows the patch file, read-only | No | — |

**Applying answers stays in the terminal in phase 2.** `jason onboard --apply` merges private facts (with a backup and a diff), writes Keeper notes, and writes profile proposals. The console shows the count and the command. Whether the console should offer it, as a signed job with the diff shown first, is open.

**A secret is refused, and nothing is kept.** When `intake.secret_reason` flags the answer, the form shows: "This looks like a secret: it gives a password. jason keeps no secrets. Put it in Keeper, and answer with the Keeper record's name." The typed value is cleared from the field and never stored or logged.

**The suggestion is not pre-selected.** It is marked "suggested" beside its choice. The person picks a choice or writes their own.

## States

- **All gates open:** "Every stage gate is open. The association is operating." The band shrinks to that line.
- **No questions:** "No open questions." With the count answered and applied.
- **A question not in the queue yet:** marked "new". Saving an answer parks it first, as `answer_intake_question` does.
- **The session cannot be built:** `onboarding_status`'s error, and "Check the profile with `jason spec`."
- **Confirm refused (same name):** `SecondConfirm` refuses it: "Jordan Example gave this answer, so Jordan Example cannot confirm it. A second person confirms." The server refuses it whatever the browser does.
- **A new answer after a confirmation:** the confirmation is cleared, and the question returns to "waiting on a second person", with "The answer changed, so the earlier confirmation no longer applies."

## Privacy

- Status and gates are counts and keys only, never a private value (`onboarding_status`'s rule).
- Once recorded, a private fact's value is never shown here. The question shows "Answered by Jane Example, Oct 2" and not the answer, unless the person opening it gave it or is confirming it.
- Evidence lines can name files; they are P1.
- Every stored text passes `intake.secret_reason`.

## Acceptance criteria

1. `StageSteps` shows the five stages in order, each gate open, or closed with what it waits on, in words.
2. Questions render in `next_questions` order, each with what it unblocks and where its answer goes.
3. No choice is pre-selected.
4. Saving an answer without a name is refused with "An answer names who gave it."
5. A secret-like answer is refused with `secret_reason`'s reason, and the fixture's fake secret never appears in `data/`, the audit log, or the server log.
6. Confirming with the answerer's name, in any case or spacing, is refused on the server.
7. After a new answer, an earlier confirmation is shown as cleared.
8. No control applies a proposal to the profile.
