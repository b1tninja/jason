# Onboarding

A band added to `#/onboarding`: the onboarding session · phase 2 · CLI: `jason onboard`, `jason onboard --questions`, `jason intake`

## In the console

**Communities** (`#/communities`) and **Onboarding** (`#/onboarding`) are built from [onboarding-ux.md](../../onboarding-ux.md): the portal of every profile with the active one's progress; and, for the active community, its accounts (set or not, never a value), its facts by duty, the request list a manager sends with the stores' own reading beside each item, its letter, and the gaps. A person records what they did about each item (`POST /api/onboarding/<key>`).

**What this spec adds** is the **onboarding session** (`jason onboard`), as a band of `#/onboarding`: the stage gates in order, the open questions ranked by what each answer unblocks, a signed answer to each, and a second person on a high-stakes answer. The request list says what to ask for; the session says what is still unanswered and what each answer unlocks. The loaders to add are `onboarding-session` (over `jason.api.onboarding_status`) and `next-questions`; the writes are `answer_intake_question` and `onboarding_confirm`, both of which already take `by`. The components are being added: `StageSteps` and `QuestionCard`.

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
