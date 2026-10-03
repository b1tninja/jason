# Notices

A new screen, `#/notices` (`?key=` for one notice, `?catalog=` for a requirement), in the Governance group · phase 2 · CLI: `jason notices`, `jason notices KEY`, `jason notices --catalog`

## In the console

None. The closest are `#/disclosures` (the calendar's recurring deadlines, some of them notices), `#/meeting` (a meeting's notice deadline), and `#/rules` (a rule change's 4360 notice). None follows a notice from its requirement to its proof.

**This spec is the whole screen, as proposed.** The loaders to add are `notices` (the ledger and the catalog) and `notice` (`?key=`: one notice as the record `jason://notice/KEY`), over `notice_ledger.notices`, `notice_record.build`, `jason.api.notice_requirements`, and `notice_delivery`. It reads only. Member rows wait on the private view ([security-and-privacy.md](../security-and-privacy.md#data-levels)); until then every band is counts only.

## Purpose and personas

Each notice from its requirement to its proof, in one line of sight: what the law requires, the text kept as sent, whom it was planned for, what became of each delivery, the follow-ups owed, and the proof of notice. One notice's page is the record `jason://notice/KEY`.

- **Manager:** syncs a notice's outcomes, reads the follow-ups owed, and plans a resend.
- **Secretary:** follows meeting notices and the minutes' availability, and records a posting.
- **Director:** reads whether a notice reached members before a meeting relies on it.
- **Counsel:** reads the requirement and the proof, on grant.
- **Treasurer, reviewer:** no access, except a reviewer opening a resend approval's evidence.

## Data

| Part | Source |
|---|---|
| The notice catalog | `jason.api.notice_requirements()`: each `key`, `title`, `statute`, `verified`, `clock`. One: `notice_requirements(key)`: `recipients`, `methods`, `clock[]`, `content[]`, `proof[]`, `note`, `caveat`, and `documents[]` (each clause's `document`, `section`, `comparison`, `says`) |
| The notices in the ledger | `jason.tasks.notice_ledger.notices(data_dir)`: `(key, attempts, synced)`; each one's `standing(...)` summary; the digest's `notices` section for the follow-ups owed |
| One notice, as a record | `jason.tasks.notice_record.build(key, private=private_view)`; the same record `jason.api.read_record("jason://notice/KEY")` renders as Markdown |
| Its parts, in order | `requirement` (recited: `words`, `passage`, `source`, `clocks`, `clauses[]` each with `words` and jason's `reading`) → `text` (`words`, `source`, `digest`, `edited`, `subjects`, `kept[]`, `files[]`, `fills[]`) → `recipients` (`plan`, `batches[]`) → `standing` (`describe`, `byOutcome`, `followUps[]`, `asks`, `general`, `posted`, `synced`) → `proof` (`windows`, `wentOut`, `onTime`, `members`, `reached`, `unreached`, `late`, `items[]`, `complete`) → `stage` |
| Delivery by member | `jason.api.notice_delivery(key)`: `standing` and `summary`. Member rows (`memberRows`) only in the private view |
| The proof page | `jason://notice/KEY/proof` (`notice_record.proof`, `notice_proof.build`) |
| The caveat | `notice_record.CAVEAT`, verbatim |

## Layout: the list

```
+------------------------------------------------------------------------------------------+
| Notices                                                       [The catalog]              |
| 12 notices in the ledger · 2 with follow-ups owed · 10 with none                         |
+------------------------------------------------------------------------------------------+
| Key                             Reached     Follow-ups owed                  Synced       |
|------------------------------------------------------------------------------------------|
| owner-info-2099                 46 of 48    2 resend by law (CIV 4041(e))    Oct 3 08:40  |
|                                             [LEGAL]                                      |
| board-meeting-2099-10-07        posted      general notice, posted Oct 2     -            |
| rule-change-proposed-pets       48 of 48    none                             Sep 20       |
+------------------------------------------------------------------------------------------+
```

## Layout: one notice

Six bands, always in this order, so the record reads from requirement to proof.

```
+------------------------------------------------------------------------------------------+
| Notices > owner-info-2099                       jason://notice/owner-info-2099 [copy]     |
| Proof: jason://notice/owner-info-2099/proof · CLI: jason notices owner-info-2099 [copy]   |
+------------------------------------------------------------------------------------------+
| 1 THE REQUIREMENT                                                                        |
| Owner information solicitation [owner-info-solicitation; CIV 4041]                        |
| Found by: the key starts with the form's key, whose request this is.                      |
| To: (the catalog's recipients) · by (its methods) · Clock: (its timing, in words)         |
| [Recitation] the statute's words, as exported, with the passage marked; caveat           |
| The governing documents' clauses:                                                        |
|   [Recitation] Bylaws 5.4 ... words ...                                                  |
|   [ReadingLabel: jason's reading, not the clause] Asks no more than the statute.         |
+------------------------------------------------------------------------------------------+
| 2 THE TEXT AS SENT                                                                       |
| Subject: Owner information request                                                       |
| [recitation-style block of the kept text]  sha256 9e2f4b7c1d0a5e33: unchanged since kept |
| Kept Oct 1 08:10: email; sent; batch owner-info-2099-email; by Jane Example              |
| Fill records: {QUOTE:decl#7.3} -> Declaration 7.3, digest a1b2...; the words now differ   |
+------------------------------------------------------------------------------------------+
| 3 RECIPIENTS                                                                             |
| Plan (data/notices/owner-info-2099/recipients.json): 30 emails, 18 letters, 2 secondary  |
| Batch owner-info-2099-email (email): 30 items, 30 sent; done                             |
| Batch owner-info-2099-mail (letter): 18 items, 18 sent; done                             |
+------------------------------------------------------------------------------------------+
| 4 DELIVERY                                            synced Oct 3, 08:40 [Sync now]      |
| 46 of 48 reached. By outcome: email delivered 26; email bounced 2; letter mailed 18 ...  |
| Owed: 2 members, resend by first-class mail [required; CIV 4041(e), 4040(a)(2)] [Plan]   |
| Counts only: a member's unit is shown only in the private view.                          |
+------------------------------------------------------------------------------------------+
| 5 PROOF OF NOTICE                                                                        |
| Window: from Sep 2 through Oct 1 · went out Oct 1: in time                               |
| [on file] text as sent · [owed] declaration of mailing · [to attach] ...                 |
| Not yet complete.                                                                        |
+------------------------------------------------------------------------------------------+
| 6 THE STAGE IT SERVED                                                                    |
| (a meeting's notice, a rule change's stage, or the minutes' availability, with links)    |
+------------------------------------------------------------------------------------------+
| A notice record is read from jason's stores: ... (notice_record.CAVEAT, verbatim)        |
+------------------------------------------------------------------------------------------+
```

## Components

`ScreenHeader`, `DataTable`, `Card`, `Recitation` (the statute's words and each clause), `ReadingLabel` (each clause's `reading`, labeled "jason's reading, not the clause"), `Clock` (the notice's windows), `Pill`, `DueDate`, `Evidence`, `Caveats` (verbatim), `Command`, `RemoteView`. The kept text against the file now waits on `DiffTable` ([components.md](../components.md#still-proposed)).

**The kept text is quoted, not recited as law.** It sits in a quoted block with its source and sha256, styled apart from a rule's recitation so a reader never takes a notice's words for the governing words.

## Actions

| Control | Does | Approval? | CLI |
|---|---|---|---|
| Sync | shown as a command: reads the notice's batches and each attempt's outcome from PayHOA | No | `jason notices KEY --sync` |
| Plan a resend (follow-ups owed by law or policy) | shown as the dry-run command; later the `payhoa.owner-info.mail-batch` or `payhoa.mailroom.send` kind | Later: an approval (phase 4, R3, two people, cost shown) | `jason owner-info --mail-batch --only "UNIT" --resend` (dry run) |
| Record a posting (a general notice) | `notice_ledger.set_general(key, posted=WHERE_AND_WHEN, by=NAME)` behind `Confirm`: a `data/` record signed by name | No: a signed record | `jason notices KEY --mark-general --posted "..." --by NAME` |
| Proof for a date | Re-renders the proof with an event day (and, for a general notice, the day posted) given by the person. Not stored | No | `jason notices KEY --proof --event DATE` |
| Open the catalog row | `#/notices?catalog=KEY` | No | `jason notices KEY --catalog` |
| Open the stage's records | The meeting's agenda and minutes (`jason://agenda/DAY`, `jason://min/DAY`), or the rule change's history | No | `jason record-stages --change KEY` |

**Ask for an address** (a returned letter, a bounce with no other delivery) is a message to a member. It is not a console action until a message kind exists; the follow-up line names it as a task for a person.

**What the proof never says.** Whether notice was sufficient is for the board or counsel. The proof shows the evidence, the window, and who was reached late. A window missed reads "OUTSIDE the window", with: "Whether notice was sufficient is for the board or counsel; often the cure is a new date."

## States

- **No ledger:** "No notices in the delivery ledger. `jason notices KEY --sync` reads one."
- **A key jason holds nothing under:** 404 with "jason holds nothing under this key: no ledger attempts, no batch, no folder."
- **No requirement fits the key:** band 1 says so, with the fix from `notice_record.sections`: name the batches with the requirement's key, or give the proof one.
- **Text not kept:** "jason does not have the text as sent. jason keeps it in `data/notices/KEY/` when it sends or saves a notice for sending."
- **Text edited since kept:** "EDITED since it was kept: the words above are not the words sent." The proof then counts the text as not on file as evidence.
- **Not synced:** band 4: "Nothing in the delivery ledger under KEY. Sync now reads it from PayHOA."
- **Not synced lately:** the last synced standing shows, with its time and the sync command.

## Privacy

- Every band is counts only by default. No member's name, unit, or ledger id appears unless the private view is on, and then only as unit and membership id (`memberRows`), never a name or an address.
- The kept text is the text as sent to all. A member's own fills are not in it.
- The catalog and the requirement are P0. Counsel sees bands 1, 5, and 6, and the counts in band 4.

## Acceptance criteria

1. One notice's page renders its six bands in order, matching `notice_record.sections` for the fixture.
2. The requirement's statute words and each clause render in `Recitation` blocks before any `ReadingLabel`, and each clause's reading is labeled "jason's reading, not the clause".
3. An edited kept text shows the EDITED line, and the proof lists text as sent as not on file.
4. With the private view off, no unit or membership id appears in the HTML.
5. "Plan a resend" creates a two-person approval with the cost shown, and nothing is sent until it is applied.
6. Recording a posting refuses an empty "where and when" or name, with "Say where and when it was posted, and who records it."
7. The page shows `notice_record.CAVEAT` verbatim.
8. `#/notices?key=KEY` and `read_record("jason://notice/KEY")` show the same facts.
