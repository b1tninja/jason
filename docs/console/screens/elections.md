# Elections

A new screen, `#/elections` (`?id=` for one election), in the Governance group · phase 3, after the Work screens and the run store · CLI: `jason elections` (to add), with `jason notices --catalog --fact election=directors` and `jason sop election` (built)

## In the console

None. Verified against the repo on 2026-10-11, what exists is the pieces around an election, not a record of one:

| Built | Where |
|---|---|
| The election's notices as catalog rows, with their clocks and the election facts that decide when each applies: `nomination-procedure`, `acclamation-initial`, `acclamation-reminder`, `nomination-acknowledgment`, `pre-ballot-notice`, `ballots`, `electronic-ballot-notice`, `electronic-opt-out-notice`, `reconvened-election-meeting`, `election-results` | `src/jason/community/notice_catalog.py`; the kinds are `ElectionKind` (`directors`, `recall`, `assessment`, `amendment`, `exclusive_use`, `other`) in `applicability.py`; the anchors are in `notices.py` (`NOMINATION_DEADLINE`, `BALLOTS_DISTRIBUTED`, `VOTING_DEADLINE`, `ELECTION`, `OPT_OUT_DEADLINE`, `RECONVENED_MEETING`) |
| Standard procedure `election` (six steps), the open legal questions about these notices | `jason sop election` (`procedures.py`); [../../notices.md](../../notices.md) |
| The candidate nomination form, version 1 (handler `response-clock`) | `form_library/ca/candidate_nomination.py`; [../../form-templates/candidate-nomination.md](../../form-templates/candidate-nomination.md) |
| The seats and terms question (`election-status`), the group `elections`, the `election-materials` item | `onboarding.py`; `jason onboard --questions --group elections` |
| "term ended; election due" on `#/people`, from a recorded term end only | `web/extra/people.py` |
| The "Elections" duty ("Jason does not run an election or count ballots.") and the 5200 record `ELECTION_MATERIALS` | `duties.py`, `symbols.py` |
| A reader of an inspector's results document (candidate votes, measures, tie-breaks), as a document model | `models/meetings_elections.py` |
| The board's recorded decisions (motion, mover, second, votes, outcome) | `data/board/decisions.json`, `tasks/decisions.py` |
| The workflow library (types, append-only run store with hash chain and compare-and-swap, fold), no `election` definition | `src/jason/workflows/` |

**Not built:** any election store (`data/elections/` does not exist), any loader, any screen, the `election` workflow definition, a nominee or candidate record, a record of the inspector, of the dates, of the inspector's reports, of the results, of the custody of the materials. The recall's own procedure is not modeled and its Corporations Code section is not on the authorities shelf (only CORP 7151, 7210-7215, 7230-7238, 8310-8340). The workflow family is [../../workflows/board-governance.md](../../workflows/board-governance.md) section 2.3 (steps e1 to e18).

**This spec is the whole screen, as proposed.** The loaders to add are `elections` (the list) and `election` (`?id=`: one election), over the **proposed** store below and over things that exist (the catalog, `notice_ledger`, `decisions.json`, `Community.terms()`). The screen reads. Its writes are small, signed, and record what a person or the inspector reported. It runs nothing.

**What jason never does here.** jason runs no election and counts no ballot. It does not decide who is qualified, whether a quorum was met, who won, or whether a measure carried; the inspector reports, the board decides, and the secretary records the board's decisions. jason shows the evidence and the clocks.

## Purpose and personas

One election in one line of sight: what kind it is and the rules it runs under, the dates and the notice each forces, who the inspector is, the nominations and their acknowledgments, each notice from catalog to delivery, what the inspector reported (and the report itself as evidence), the results, the seats filled, and who holds the materials until when.

- **Secretary:** the recorder. Opens the election, records the dates, nominations, the inspector's reports, the board's acclamation vote, and the seats.
- **Manager:** plans the notices and mailings (they go through `#/approvals`), reads delivery, keeps the clocks.
- **President, vice president, treasurer, director:** read the same page (directors and officers have the same access to information). The board decides what the law leaves to it.
- **Inspector of elections:** an independent third party, **outside the console**. Never signs in. Reports to the board; the secretary or manager records the report.
- **Counsel:** reads the page on grant; the unclear points below go to counsel.
- **Owner, candidate as a member:** never see this screen. Members read the notices and the results notice.

## Proposal: the election store

**Labeled a proposal.** A new store, `data/elections/<id>.jsonl`, in the conventions of `jason.workflows.store`: one append-only file per election, one JSON object a line, `{n, kind, by, at, detail, prev}`; `n` is the compare-and-swap, `prev` the first 12 hex of the sha256 of the previous line; every append holds `locks.hold(Resource.STORE, "elections-<id>")` and is flushed and fsynced; a partial last line is dropped and reported; `data/elections/index.json` is a cache that can be deleted. A correction is a later event, never an edit. The id is opaque (`elec-` and ten hex); a URL carries it, never a name. (Reading `workflows/store.py` shows `ROOT` and the `Event` types are the workflows' own, so reuse needs a small generalization: a build note, not a second implementation.)

| Event `kind` | `detail` (what is stored) | Evidence required |
|---|---|---|
| `opened` | `electionKind` (an `ElectionKind` word), `label` ("Directors 2099"), `seats`, `trigger` (a term end, the four-year rule, a petition, a board decision, a reversal request with its received day) | the record that triggered it, or the board decision id |
| `rules-recorded` | the election rules' version in force, and the answers to the standing facts (electronic ballots and opt-out, quorum, acclamation availability), each with its record | the rules' record; `jason://` address of each answer |
| `inspector-selected` | `method` (board, members, other, per the rules), `count` (one or three), the inspector's firm or name, the independence statement as received | the appointing decision or the members' record; the statement (a library document) |
| `dates-set` | nomination deadline, ballots out, voting deadline, count meeting, opt-out deadline; each with the notice day it forces and its basis | none; `check` refuses an inside-90-days rules change (below) |
| `nomination-received` | nominee, nominator (names as the form gives them), `received`, the form answer id | the candidate-nomination response |
| `nomination-acknowledged` | to nominator and to nominee, each `on` and the notice key | the notice or message record |
| `qualified` / `disqualified` | `basis` (an election-rule row or a 5105(b) ground), `appeal`, who decided (an office) | the rule row; for a disqualification, the appeal route as sent |
| `lists-made-available` | counts only (candidate list, voter list), the dates members may verify, `corrections` reported and made | the inspector's statement |
| `notice-linked` | a notice key (`jason://notice/KEY`); nothing copied | the ledger |
| `ballots-delivered` | as the inspector reported: date, counts by channel (paper, electronic), who delivered | the inspector's report |
| `count-held` | the meeting (a date; its agenda/minutes addresses), whether it was properly noticed, the quorum as the inspector determined it (counts only) | the inspector's report or the minutes |
| `report-filed` | the report's library id and sha256, the day received, the tabulated results: for each candidate or measure the counts the report gives, turnout, the outcome as the report states it | the report itself |
| `results-confirmed` | the second person's name and day | none |
| `acclaimed` | the decision id (`decisions.json`), the candidates named on that agenda item | the decision, outcome `approved` |
| `results-noticed` | the notice key and the day | the ledger |
| `seats-recorded` | the onboarding answer id that recorded the terms | the answer |
| `materials-transferred` | day, from the inspector, the receipt | the receipt |
| `reconvened`, `moved`, `cancelled`, `note` | the new date and the reason; a note | a reason |

**What the store never holds:** a ballot, a signed envelope, an electronic receipt, a tally sheet, the voter list or candidate registration list themselves (counts and dates only), how any member voted, whether any one member has voted, or a running count before the count meeting. These stay with the inspector (CIV 5125). The store holds the inspector's **report**, as a document, and the counts the report states.

## Data

| Part | Source |
|---|---|
| The list | `jason.elections.runs(data_dir)` (to add): `id`, `label`, `kind`, `state`, `next` (date, what, basis), `inspector` (set or not), `seats` |
| One election | `jason.elections.show(data_dir, id)` (to add): the events folded to `rules`, `dates[]`, `inspector`, `nominations[]`, `notices[]`, `reports[]`, `results`, `seats`, `custody`, `events[]` |
| The notices an election of this kind needs | `jason.community.notice_catalog.applicable(...)` with `election=KIND` and the answered standing facts (built); each row's last day computed from the dates |
| Each notice's delivery | `notice_ledger`, `notice_delivery` (built): counts only |
| The acclamation vote | `jason.tasks.decisions` (built): motion, mover, second, outcome |
| Terms and "term ended" | `Community.terms()` (built); the last election on record |
| The statute's words | the authorities shelf, `data/authorities/CIV/CIV-5100-5145.md` (present here, ignored by git): recited at render time, never copied into the store. **If a build finds the shelf absent, every recital reads "recited from the shelf" with the section and a note to export it; no quote is written from memory.** |
| The caveat | a constant to add, beside `notice_record.CAVEAT`: "jason records what the inspector reports. It runs no election, counts no ballot, and decides nothing; the board decides." |

## Layout: the list

```
+------------------------------------------------------------------------------------------+
| Elections                                                          [Open an election]   |
| 2 elections on record · 1 in progress · 1 closed, materials kept until Oct 5, 2099       |
+------------------------------------------------------------------------------------------+
| Directors 2099 (2 seats)   Nominations closed Feb 27   Next: pre-ballot notice by Mar 2  |
|                            [LEGAL] CIV 5115(b)         Inspector: set                   |
| Member vote: amendment     Report filed Oct 5, 2098     Materials: with the inspector    |
+------------------------------------------------------------------------------------------+
```

## Layout: one election

Seven bands, in the order the work runs. Every date is `DueDate` with a basis word; none is typed except the five the secretary sets.

```
+------------------------------------------------------------------------------------------+
| Elections > Directors 2099             jason://election/elec-3f9a1c07d2 [copy]           |
| Kind: directors · 2 seats · opened Nov 3, 2098 by the secretary · CLI: jason elections ID |
+------------------------------------------------------------------------------------------+
| 1 RULES AND STANDING FACTS            [Recitation: CIV 5100(a)(2), the four-year rule]    |
| Election rules in force: version of 2097-06-01 · last amended 2097-06-01                 |
| Electronic ballots: opt-out (rules s.4)  Quorum: required (bylaws s.7)  Acclamation: not  |
| available (board decision 2098-09-15)    "undetermined" shows as undetermined, never "no" |
| Check: no rules change falls after Feb 4, 2099 (90 days before the count).  [passes]     |
+------------------------------------------------------------------------------------------+
| 2 DATES (ElectionTimeline)                                                               |
| Call for candidates by Jan 28 [LEGAL 5115(a)] · Nominations close Feb 27 [PERSON]        |
| Pre-ballot notice by Mar 2 [LEGAL 5115(b)] · Ballots out Apr 1 [PERSON]                  |
| Ballots delivered by Apr 4 [LEGAL 5115(c)] · Voting deadline May 4 · Count May 5          |
| Results notice by May 20 [LEGAL 5120(b)] · Change of voting method by Feb 4 [LEGAL]      |
| Each is computed from the catalog's anchor. A day already past moves the election.       |
+------------------------------------------------------------------------------------------+
| 3 THE INSPECTOR (outside the console)                                                    |
| Selected Dec 1 by the board (method: the rules' appointment by the board) · one inspector |
| Independent Inspector Co. · statement of independence on file (Doc) · [Recitation 5110(b)]|
| jason records the statement; whether the inspector is independent is not jason's call.   |
+------------------------------------------------------------------------------------------+
| 4 NOMINATIONS                                                                            |
| Candidates so far: 3 for 2 seats (A. Candidate, B. Candidate, C. Candidate) · all qualified|
| A. Candidate: received Feb 3, acknowledged Feb 5 (to the nominator and the nominee)      |
| Lists: made available Jan 28 to Mar 2 · 1 correction reported, made Feb 12 (2 business days)|
| More candidates than seats: acclamation does not arise.   [Qualify] [Disqualify] by form |
+------------------------------------------------------------------------------------------+
| 5 NOTICES (each from catalog to delivery)                                                |
| nomination-procedure   by Jan 28   delivered Jan 20, in time   jason://notice/...        |
| pre-ballot-notice      by Mar 2    delivered Mar 1, in time    48 of 48 reached          |
| ballots                by Apr 4    owed                         [Plan in Approvals]       |
+------------------------------------------------------------------------------------------+
| 6 VOTING AND THE COUNT                                                                   |
| Ballots go out Apr 1. Voting closes May 4. Nothing is shown before the count: no ballot, |
| no running tally, no list of who has returned one.                                       |
| (after the report) Count May 5, properly noticed: yes · quorum, as the inspector reports: |
| met · [Report: inspector-report-2099.pdf, sha256 4b1c...9e0a, received May 5]            |
| Results as reported: A. Candidate 21 · B. Candidate 17 · C. Candidate 9 · Ballots 48     |
| [ReadingLabel] Typed from the inspector's report; jason has not counted or checked it.   |
+------------------------------------------------------------------------------------------+
| 7 SEATS AND THE MATERIALS                                                                |
| Results confirmed by a second person May 6 · noticed May 12 (in time) · minutes: next    |
| meeting · seats recorded: onboarding answer 31 · Materials: with the inspector until the |
| challenge window ends · Kept until at least May 5, 2100 [LEGAL 5200(c)] [counsel: below] |
+------------------------------------------------------------------------------------------+
| (caveat, verbatim)                                                                       |
+------------------------------------------------------------------------------------------+
```

A **member vote** (assessment, amendment, exclusive use, reversal under CIV 4365) shows no nominations band; band 4 becomes **The measure**: its text as sent with the ballot (5115(g)), the threshold the documents and the law set (shown as their words), and, after the report, the counts the inspector reports. A reversal request shows its received day and the 35-to-90-day window from 4365(b), and its results notice within 15 days of the close of voting (4365(g)).

## Components

Built: `ScreenHeader`, `DataTable`, `Card`, `Recitation`, `ReadingLabel`, `Clock`, `Pill`, `DueDate`, `Evidence`, `Doc`, `Caveats`, `Command`, `Confirm`, `RemoteView`. To add: `ElectionTimeline` (dates, each with the notice day it forces and its basis word, built from `Clock` stages; named in board-governance.md), `InspectorCard` (the inspector and the independence statement; no controls for the inspector's work), `NominationRow`, `ReportEvidence` (the report as a `Doc` with sha256 and the day received, the counts beside it), `CustodyLine` (who holds the materials and until when). Any proposed number (a correction room, a retention rule) is a `BasisPill` PROPOSED, never a stamp.

## Actions

Every write is signed with the signer's name (a `by` naming someone else is a 403), behind `Confirm`, appends one event, and needs the evidence in the store's table. None sends, mails, counts, or decides.

| Control | Does | Approval? | CLI (to add) |
|---|---|---|---|
| Open an election | `opened`: kind, seats, trigger. Starts the `election` run (e1) | No | `jason elections --open KIND --seats N --by NAME` |
| Record the rules and standing facts | `rules-recorded`, each answer with its record; an unanswered fact stays undetermined | No (the answers go through `jason intake`) | `jason elections ID --rules --by NAME` |
| Record the inspector | `inspector-selected` with the independence statement | No | `jason elections ID --inspector ... --by NAME` |
| Set the dates | `dates-set`; refuses a rules change inside 90 days of the count (5105(h)(4)(B)(iii)) and a date plan whose notice day has passed | No | `jason elections ID --dates ... --by NAME` |
| Record a nomination, its acknowledgment, its qualification | `nomination-received`, `nomination-acknowledged`, `qualified` / `disqualified` (refused on a ground 5105(d) or (e) rules out; the appeal route is required) | No: a signed record. The message to the nominee is a draft in `#/approvals` | `jason elections ID --nomination ... --by NAME` |
| Link a notice | `notice-linked`; shows delivery, counts only | No | `jason elections ID --notice KEY` |
| Plan a notice or mailing | Opens the existing plan (Gmail draft, PayHOA broadcast, Mailroom letter) in `#/approvals`; letters cannot be recalled | Yes: the approvals engine (R3 for mail) | `jason notice-check`; `jason mailroom --pdf` |
| Record the inspector's report | `ballots-delivered`, `count-held`, `report-filed`: the report attached as evidence, the counts the report states, typed from it | No; `results-confirmed` needs a second person | `jason elections ID --report FILE --by NAME` |
| Record the acclamation | `acclaimed`, only when `decisions.json` holds an approved decision whose item names each qualified candidate. No vote control | No | `jason elections ID --acclaim DECISION_ID` |
| Record the seats | Hands to the existing `election-status` question | The existing two-person confirm | `jason onboard --questions --group elections` |
| Record the materials transferred | `materials-transferred` with the receipt | No | `jason elections ID --transfer ...` |
| Move, reconvene, cancel, note | The new date with a reason | No | `jason elections ID --move ...` |

**There is no** control to count, tabulate, open, declare a winner, certify, approve, or adopt; the words are on no button. jason deletes nothing at the end of retention: the end is a date and a signed note by a person.

## States

- **No store:** "No elections on record. The inspector's reports of past elections are in the library; open one to record the next." The page never says "no election was held".
- **No inspector yet:** band 3: "No inspector on record." Bands 4 to 7 can show nominations but record no ballot event; the dates band says the pre-ballot notice needs a candidate list.
- **Rules silent on selecting the inspector:** a question for the board (a board item), not a default (board-governance.md).
- **A notice day passed:** the date reads "PASSED" with the law's words and opens a follow-up; the election moves, no clock is shortened.
- **A rules change inside the 90 days:** the dates band is blocked: "the election rules may not be amended less than 90 days before an election".
- **Report not in hand:** bands 6 and 7 read "waiting on the inspector's report"; no seat is recorded from a name alone.
- **No quorum reported:** `reconvened` opens the reconvened-meeting notice row (15 days before; at least 20 days after) and keeps the materials with the inspector.
- **Acclamation:** only when seats are not fewer than qualified candidates and the standing fact says available; the band shows the board's decision as recorded.
- **Edited or missing report file:** "EDITED since filed" (sha256 differs) or "report not on file"; the results read as unconfirmed.
- **Past a term end with no election on record:** "term ended; election due" links here (from People); the four-year rule is shown beside the last election on record.

## Privacy

- **Shown (P0 once noticed):** kind, dates, the notices, the candidates' names as the notices give them, the tabulated results the inspector reports and the general notice gives (5120(b): "available for review by members").
- **P2 (the offices that open it; a director reads what an officer reads):** nominees and their status before a notice names them; the inspector; the report. **P1:** counts only (of the lists, of ballots delivered, of ballots counted), with no name.
- **Never shown, never stored:** how any member voted; any individual ballot, envelope, or electronic receipt; a tally before the count; whether one named member has returned a ballot. The secret ballot is the law's (5100(a)(1)); the signed envelope may be inspected but not copied (5200(c)); no one but the inspector may review a ballot before the count (5120(a)).
- **P2/P3:** a nominee's address, the voter list, the candidate registration list, and the materials are P3 election materials (security-and-privacy.md) held by the inspector. The page links no `/api/file`, shows no absolute path, and logs each report opening (`access/served.jsonl`).
- A director reads what an officer reads. An election's executive-session discussion (e.g. a challenge) appears by its 4935 general words only.

## A made-up sample

As of 2099-03-10, `directors`, two seats; every day computed. Call for candidates by 2099-01-28; nominations close 2099-02-27; pre-ballot notice by 2099-03-02; ballots out 2099-04-01; delivered by 2099-04-04; voting deadline 2099-05-04; count and election day 2099-05-05; results notice by 2099-05-20; change of voting method and rules amendments close 2099-02-04; reconvened meeting at least 2099-05-25 (notice 2099-05-10). Acclamation notice would have been due 2098-11-29 (90 days before the deadline), not applicable here. Challenge window and one year of retention both run to at least 2100-05-05.

| Step | State on 2099-03-10 |
|---|---|
| e1-e3 kind, facts, rules | done (rules of 2097-06-01 in force) |
| e4 inspector | done: Independent Inspector Co., statement on file |
| e5 dates | done |
| e6 lists | done: 1 correction made |
| e7 call for candidates | done in time |
| e9 nominations | 3 received, all acknowledged and qualified |
| e10 acclaim or ballot | ballot (3 for 2) |
| e11 pre-ballot notice | done Mar 1 |
| e12 ballots | waiting (Apr 1) |
| e13 to e18 | not started |

## Acceptance criteria

1. `GET /api/elections` signed out is a 401; the owner view and an office that does not open P2 are refused (counts alone, no name, open at P1) with `access.may_see`'s sentence; `elections` is not in `OWNER_SOURCES`.
2. The store appends under `locks.hold(Resource.STORE, ...)`; a stale `n` is refused with a changed-since message; an edited line fails `verify`; a torn last line is dropped and reported.
3. Nothing the page loads, and nothing in the store, holds a ballot, an envelope, a voter or candidate list, how a member voted, or a count before `count-held`. A test greps the store and the API for these.
4. Every statute quote renders from the shelf in `Recitation` before its `ReadingLabel`, and reads "recited from the shelf" when the shelf is absent.
5. Every date shows a basis word; a past notice day reads PASSED, opens a follow-up, and never moves a clock earlier.
6. `dates-set` is refused when a rules change falls within 90 days of the count day.
7. `disqualified` is refused without a basis and the appeal route, and on a ground 5105(d) or (e) excludes.
8. `acclaimed` is refused unless `decisions.json` holds an approved decision whose item names each qualified candidate; the page has no vote control.
9. `report-filed` is refused without a file; an edited file shows EDITED; results are "unconfirmed" until a second, different person confirms.
10. No control or label reads count, tabulate, declare, certify, approve, adopt, or vote.
11. A candidate cannot record or confirm their own qualification or results (proposed policy, below).
12. A member vote shows no nominations band, and its measure text is the text sent with the ballot.
13. Retention shows a date and custody (inspector or association); the page deletes nothing.
14. `#/elections?id=ID`, `jason elections ID`, and `read_record("jason://election/ID")` show the same facts; the page shows the caveat verbatim.

## Decisions for the user

1. **One log or two.** Recommended: the election store holds the facts; the `election` run holds steps and links to it (links, not copies). A second event log for the same facts is not recommended.
2. **Who records and confirms.** Recommended: the secretary records; a second person confirms the results and the seats.
3. **A candidate does not record their own election** (proposed policy, for the board): the screen refuses a recorder or confirmer who is on the candidate list. Needs the board's adoption.
4. **Who qualifies a nominee** (the board, the inspector, or the rules' own test) and who hears the appeal. Recommended: the election rules name it; if silent, a question for the board. jason records the basis; it does not judge.
5. **Who selects the inspector when the rules are silent.** A board question, not a default.
6. **No interim count.** Recommended: no returned-ballot figure before the count, because CIV 5120(a) bars review before it. The cost: no early warning of a missed quorum. Confirm.
7. **A measure's pass or fail.** Recommended: show the inspector's reported outcome and the threshold in the documents' and the law's words; jason does not compute "carried".
8. **The day the 15-day results notice runs from.** 5120(b): "Within 15 days of the election". Recommended: show both the voting deadline and the count day and use the earlier as the working date (lawful under either reading); counsel to read.
9. **Retention.** 5200(c): "maintain association election materials for one year after the date of the election"; 5125 keeps them with the inspector "until the time allowed by Section 5145 for challenging the election has expired", a year from the inspector's notice or the cause, "whichever is later". These can end on different days. Recommended: show both; keep to the later (proposed policy); counsel to read. Which "date of the election" 5200(c) means is also counsel's.
10. **Who delivers the ballots.** 5115(c) says "mailed by first-class mail or delivered by the association"; 5105(h)(4) says the inspector shall "deliver, or cause to be delivered". jason records who did, as reported, and settles neither; counsel to read.
11. **Counsel (unclear in the law, already open in notices.md):** whether the "recall elections" of 5115 are the "removal of directors" of 5100(a)(1); whether 5103 reaches seats filled after a recall; whether 5103(a)'s three-year condition leaves the acclamation notices owed when it is not met; how 5115(d)(3)(C) reads. The recall's own procedure (Corporations Code) must be exported to the shelf before the recall kind is built.
12. **Phase.** Recommended: after the Work screens, with the `election` definition (board-governance.md build step 8). Until then the CLI, the catalog, and the nomination form carry it.
