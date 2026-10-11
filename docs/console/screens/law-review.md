# Law review

A new screen, `#/law-review` (`?year=` the review's year, `?lead=` one lead's id, `?view=conflicts` the Conflicts list), in the Governance group beside Decisions and Board action items · phase 3, after the Work screens · CLI: `jason conflicts`, `jason conflicts --leads [--since DATE] [--document KEY]`, `jason law-history --section NNNN`, `jason sop law-review`

## In the console

Almost nothing. The Reference shelf (`#/reference`, `ReferenceShelfView`) shows the citation gaps (step l4) with the `CitationGaps` component; nothing shows a lead or a `Conflict` row, and the `law-review` run's steps l6, l7, and l12 are CLI only ([board-governance.md](../../workflows/board-governance.md) sections 2.5, 8: "No law-review screen").

**This spec is the whole screen, as proposed.** Verified in the repo on 2026-10-11.

| Piece | State |
|---|---|
| `jason conflicts` (`--area`, `--open`, `--json`) over `authority_order.conflicts(community)` | built |
| `jason conflicts --leads` (`--since`, `--document`, `--json`) over `jason.tasks.conflict_leads.leads` | built. The full `Lead` (document, title, written, route, section, quote, score, recorded, and the `Change`: citation, action, statute, bill, when, summary, inserted) is in `--json` only |
| MCP `document_conflicts(area, include_resolved, leads, document, since)` | built. Its leads carry fewer fields (`document`, `section`, `statute`, `bill`, `operative`, `route`, `recorded`, `quote`) and stop at 200 with `leadCount` |
| MCP `law_in_force`, `cite_document`, `section_refs`, `citation_gaps`, `document_citations`; `jason law-history` (`--export`, `--section`, `--versions`, `--sweep`); `jason readings --stale` | built |
| Web loaders `citations`, `citation-gaps`, `reference-works`, `reference-page` (`jason.web.extra.citations`) | built; they answer l4 only |
| Web loaders `conflict-leads`, `conflicts`, `cite`, `record` | **to add**: none is registered in `jason.web.sources` |
| The dispositions store, its writer, `LeadList`, `LeadReader`, `ConflictRows` | **to add** |
| Components `Recitation`, `ReadingLabel`, `Caveats`, `Command`, `Confirm`, `DataTable`, `Pill`, `Evidence`, `RemoteView` | built |

The loaders to add wrap what exists and derive no fact: `conflict-leads` (`?since=`, `?document=`, `?year=`) over `conflict_leads.leads`, with each change's `authority_text` and `law_in_force` fetched on open; `conflicts` (`?area=`, `?resolved=`) over `authority_order.conflicts`. It reads only except the one writer below.

## Purpose and personas

Each January, and again when a law takes effect mid-year, the board's manager asks one question of every written provision: **has a later change in the law displaced any of it?** The screen puts each candidate beside the statute's stored words and the provision's own words, and records what a person decided, once, in their name. A lead is a reason to read two texts side by side, not a finding. jason notes a conflict and never resolves one; only the board, counsel, or an amendment does.

- **Manager:** runs steps l1 to l7, reads each lead, records dispositions, and drafts the proposed `Conflict` row.
- **Secretary:** records the board's decision on a conflict (step l12) and links the board item.
- **President, vice president, treasurer, director:** read everything the secretary and manager read, and may record a disposition. Directors and officers have the same access to information; they differ in duties, not in what they may read.
- **Counsel:** reads the leads and the conflicts marked for counsel, on grant. No act.
- **Administrator:** holds no office; counts only. **Owner, reviewer:** no access.

## Data

| Part | Source |
|---|---|
| The leads | `conflict_leads.leads(data_dir, community, document=, since=)` → `Lead`: `document` (outline key), `title`, `written` (the date the text was written, or "" = every change since 2014 counts), `route` (`cites` or `subject`), `section` (the document's section name), `quote` (first 240 characters, a locator and not a recitation), `score`, `recorded` (the `Conflict` key already covering the change); `change`: `citation`, `action`, `statute`, `bill`, `when` (operative date), `summary`, `inserted` |
| The statute's words | `jason.tasks.export_authorities.authority_text(data_dir, citation)` (stored, whole); `law_in_force(citation, as_of)` for the words on the day before and the day of `change.when`, from the versions `jason law-history --versions` kept. When a version is not on disk: `found: false` and its `reason`; nothing is picked |
| The provision's words | `cite_document("KEY#SECTION")` (to add as the `cite` loader), whole, with `inForce` and `caveat`. Whether `Lead.section` names resolve as `KEY#SECTION` is not verified |
| jason's reading | none stored for a lead. Where the profile holds a reading of the same provision (`jason readings --citation`), its status (current or stale) and whose it is; otherwise the lead shows "No reading on file" |
| The Conflicts list | `authority_order.conflicts(community, area, open_only=)` → `Conflict`: `key`, `provision`, `says`, `authority`, `since`, `extent`, `apply`, `clarity` (`plain`, `unclear`, `renumbered`), `status` (`noted`, `counsel`, `board`, `resolved`), `board_item`, `resolved_by`. Caveat: "jason notes a conflict; only the board, counsel, or an amendment resolves one." |
| Dispositions (a **proposal**) | `data/law-review/dispositions.json`, one row per lead, append only, in the shape of `jason.tasks.deficiencies` (below) |
| The board item | `board_items.propose` (`ItemCategory`, `due`, `authority`, `evidence`), as `deficiencies.sync_board_items` builds one |
| Freshness | the export's date (`jason law-history --export`), the outlines' fetch date, and `written_from` for each document |

**The disposition store (proposal).** Each row: `id` (a hash of document, change citation, and operative date, so a second run adds nothing), the lead as read (document, section, change citation, bill, operative date, route), the **digests** of the statute words and the provision words the person read, and `acts[]`. Each act is appended with `by` and `at` and the row's state is read from them, the latest word on the disposition winning (the deficiency register's `state_of`). Acts: `proposed` (jason lists the lead), `read` (a person opened both texts), `no-conflict` (reason required), `renumbered` ("read as its successor"; no conflict of substance), `conflict-proposed` (the drafted `Conflict` fields: provision, authority, since, extent that yields, how applied meanwhile, clarity), `for-counsel` (the question, the course lawful under either reading meanwhile), `board-item` (the item id), `note`, `withdrawn` (a reason). A correction is a later act; nothing is edited or deleted. Each write holds the store lock (`jason.locks`), requires `by`, and writes only this file; the board item is written after the lock is let go, and a failure there never undoes the act.

## Layout: the leads

```
+------------------------------------------------------------------------------------------+
| Law review 2099        Leads since [ 2099-01-01 ]  Document [ all v ]  View [Leads|Conflicts]|
| Law refreshed Jan 4 (export) · outlines Jan 4 · 41 leads · 6 read · 2 conflicts proposed   |
| Command: jason conflicts --leads --since 2099-01-01 [copy]                                 |
+------------------------------------------------------------------------------------------+
| Document / section      Change in the Act (operative)          Route   Disposition         |
|------------------------------------------------------------------------------------------|
| Example Declaration     CIV 9999.1 amended, AB 9999 (fake)     subject Not yet read        |
|  Section 7.3 (fake)     operative Jan 1, 2099 · 38 words added                              |
| Example Declaration     CIV 9999.2 added, SB 8888 (fake)       cites   No conflict (Jan 9) |
|  Section 4.2 (fake)     operative Jul 1, 2099                                               |
| Example Policy          CIV 9999.1 amended, AB 9999 (fake)     subject Conflict proposed   |
|  Section 2 (fake)       already recorded as C-3                        [Put on agenda]     |
| Example Rules (no date) CIV 9999.3 amended ...                 subject For counsel         |
|  every change since 2014 is counted: no written date                                       |
+------------------------------------------------------------------------------------------+
```

A document whose `written` date is unknown carries the line "date unknown: every change since 2014 is counted" and a link to pin it (`jason outlines`); its leads are many and loose, and say so. Sort: document order, then operative date. Filters: document, route, disposition, "recorded already". A lead already on a `Conflict` row shows "recorded as KEY" and still opens.

## Layout: one lead

Four bands in a fixed order, so the words come before any reading: the statute, the provision, jason's reading, the disposition.

```
+------------------------------------------------------------------------------------------+
| Law review > Example Declaration, Section 7.3 (fake)  ·  CIV 9999.1, operative Jan 1, 2099 |
| Basis: subject match (score 4.1): the section is among the passages closest to the change |
+------------------------------------------------------------------------------------------+
| 1 THE LAW                       Before (in force Dec 31, 2098)  |  Now (from Jan 1, 2099)  |
| [Recitation] Civil Code 9999.1 (fake), as exported Jan 4. Inserted words marked.          |
|   "... A lease of not less than thirty days shall be permitted ..." (fake text)           |
| History: amended by Stats. 2099, Ch. 1 (AB 9999, fake). Not an official restatement.       |
+------------------------------------------------------------------------------------------+
| 2 THE PROVISION                                                                          |
| [Recitation] Example Declaration, Section 7.3 (fake), as written Mar 12, 2090, whole.      |
|   "An Owner may lease the Owner's Unit for a term of not less than ninety (90) days."      |
+------------------------------------------------------------------------------------------+
| 3 READING                                                                                |
| [ReadingLabel: jason's reading] No reading on file for either text.                        |
| [ReadingLabel: Two readings remain] 1. 7.3 asks more than the minimum: no conflict.        |
|   2. 7.3 sets a floor the statute forbids. The board asks counsel.                         |
+------------------------------------------------------------------------------------------+
| 4 DISPOSITION                                  recorded in the person's own name          |
| ( ) Not a conflict      ( ) A renumbering, read as its successor                          |
| ( ) A Conflict row proposed      ( ) A question for counsel                               |
| Reason (required): [______________________________________________] [Record as NAME]      |
| History (newest first): Jan 9 A. Manager: read · Jan 4 jason: listed                      |
| Board item: none [Put on the board's agenda]                                              |
+------------------------------------------------------------------------------------------+
```

Below 768 px the Before and Now columns stack, the statute first. Where the earlier version is not on disk, "Before" reads "The earlier words are not on disk. `jason law-history --versions --since 2099`" and nothing is shown in its place. Where the change inserted words, they are marked in "Now"; a side-by-side `DiffTable` waits ([components.md](../components.md#still-proposed)).

## Layout: the Conflicts list

```
| Provision (fake)        Yields to (since)          Part that yields        Meanwhile        Clarity      Status   Item |
| Example Policy 2        CIV 9999.1 (Jan 1, 2099)   the 90-day minimum      Followed as ...  plain        board    BI-7 |
| Example Declaration 4.2 CIV 9999.2 (Jul 1, 2099)   whether it applies      Lawful under ... for counsel  counsel  BI-8 |
```

Each row opens its provision and authority recited (bands 1 and 2), then `says`, `extent`, and `apply` under the label "jason's note, not the provision". A resolved row shows `resolved_by`. "Plain" and "for counsel" are words and a `Pill`, never color alone; a `renumbered` row reads "no conflict of substance". The list is read only: a `Conflict` row is a profile edit a person commits.

## Components

`ScreenHeader`, `DataTable` (leads, conflicts), `LeadList` (to add, from [board-governance.md](../../workflows/board-governance.md) section 5), `LeadReader` (to add: bands 1 to 4), `Recitation` (the statute, then the provision, each with its citation, version, and caveat), `ReadingLabel` (jason's, the board's, counsel's, or "Two readings remain"), `Clock` (the effective date and the days since), `Pill`, `Confirm`, `Evidence`, `Caveats` (verbatim), `Command`, `RemoteView`. The proposed `Conflict` fields are a form of ordinary inputs that produces text a person copies; it is not a component of its own.

**Words before readings.** Band 3 follows bands 1 and 2 always, and a reading is never inline in the recited words, in a heading, or in a tooltip. The `quote` on a list row is the locator the loader returned, marked "excerpt"; the whole provision is recited only in band 2.

## Actions

| Control | Does | Approval? | CLI |
|---|---|---|---|
| Open a lead | `#/law-review?lead=ID` (the id is a hash; no name, no address) | No | `jason conflicts --leads --document KEY --since DATE` |
| Open the statute's history | the change by edition, and the former section's successor | No | `jason law-history --section NNNN` |
| Record a disposition | appends `no-conflict`, `renumbered`, `conflict-proposed`, or `for-counsel` with a required reason, behind `Confirm` ("Record that NAME read both texts and decided: not a conflict") | No: a signed record | `jason law-review --record ID --as no-conflict --reason TEXT --by NAME` (to add) |
| Draft the Conflict row | fills `provision`, `authority`, `since`, `extent`, `apply`, `clarity` as text for a person to paste into the profile; writes no profile | No | `jason law-review --row ID` (to add) |
| Put on the board's agenda | proposes a board item (authority and evidence cite the two texts) and appends `board-item` | No: a proposal | `jason board --set ITEM ...` |
| Record the board's decision | appends the outcome (amend, ask counsel, leave) with the decision id; the secretary only | No: the vote is on `#/decisions` | `jason law-review --decision ID --by NAME` (to add) |
| Withdraw | a later act with a reason; the row stays | No | `--withdraw ID` (to add) |
| Refresh the law | shown as the command | No | `jason export-authorities; jason law-history --export` |

There is no control labeled "resolve", "approve", or "adopt". Whether a conflict exists is a person's reading, a conflict row is committed in the profile by a person, and an amendment is a `rule-change` run.

**Rules the screen honors.** It is a conflict only if both cannot be obeyed; a provision that asks more than the minimum is followed as written. A renumbered citation is read as its successor and is not a conflict. Where two readings remain, the disposition is **for counsel**, the course lawful under either reading is recorded as "meanwhile", and the board asks counsel. jason applies neither reading and the screen offers no third. An unclear extent is never recorded as plain.

## States

- **No outlines or no export:** "No leads: `jason outlines` and `jason law-history --export` write what this reads." (the CLI's own words).
- **No leads since the date:** "No change in the Act since DATE may postdate a document." with the date and the filter.
- **A document with no written date:** the line above; its count is shown apart.
- **A lead's earlier statute words missing:** shown as a miss with its `reason`, never filled with today's words.
- **Changed since read:** a disposition whose recorded digest no longer matches the statute or provision words reads "The words changed since NAME read them on Jan 9." and the lead returns to "Not yet read"; the old act stays in the history.
- **A stale reading** (`jason readings --stale`): listed, with "redone or confirmed by the board or counsel before it is used".
- **A change already on a Conflict row:** "recorded as C-3". Reading it again is allowed.
- **More than 200 leads:** the MCP stops at 200; the loader reads the task and pages. It never says "no more" from a capped list.
- **Store unreadable:** "could not read dispositions.json" with the reason; the leads still show.

## Privacy

- Statutes, leads, and the governing documents' words are P0. Conflict flags the board has put to counsel, counsel's letters, and the reasons in dispositions are board-confidential (P1 board view; counsel's letters P3, not shown here, linked by library address only).
- A disposition names its recorder (an office holder). It names no owner, unit, or resident. The URL carries a hash id.
- Counsel reads the leads and conflicts on grant. Administrator: counts. Owner, reviewer: refused.
- A restricted book's words appear only in the private view ([governing-documents.md](governing-documents.md#privacy)).

## Acceptance criteria

1. Each lead's page renders the statute `Recitation`, then the provision `Recitation`, then `ReadingLabel`, then the disposition, in that order; nothing sits between a recited text and its citation.
2. The statute's words are the stored text; no band paraphrases them. A missing earlier version shows a miss and its reason.
3. The list matches `jason conflicts --leads --json` for the fixture: same leads, order, `route`, and `recorded` marks, and the loader is not capped at 200.
4. Recording a disposition refuses an empty reason or name, with "Say what you read and why, and who is recording it." Nothing is written on a refusal. A body `by` naming someone else is a 403.
5. A disposition is appended, never edited: a second disposition for a lead keeps the first in the history; withdrawal keeps the row.
6. A changed digest returns the lead to "Not yet read" and keeps the earlier act.
7. "A Conflict row proposed" writes no profile and no `Conflict` row; it produces text and a board item only. The page has no resolve control.
8. "A renumbering" and "Not a conflict" never create a board item unless a person asks.
9. A conflict marked for counsel shows its meanwhile course and the board item; two readings are both shown, neither applied.
10. A director sees what an officer sees; the secretary alone records the board's decision.
11. The page shows the Conflict caveat and the consolidated-text caveat verbatim.

## Decisions for the user

1. **Who records a disposition.** Any office that opens P1 (recommended: directors and officers read the same), or the manager and secretary only. The decision step stays the secretary's.
2. **A second reader.** Whether a "not a conflict" disposition needs a second person before the lead leaves the list (recommended: no for a `renumbered` or a plain no-conflict; yes for a `for-counsel` closed without counsel).
3. **The store.** Confirm `data/law-review/dispositions.json` as an append-only register (the deficiencies shape), or fold dispositions into the intake queue.
4. **Lead ids.** Hash of document, citation, and operative date (recommended), or add a stable id to `Lead`.
5. **Pin the written date.** Whether a document with no `written` date blocks the review (recommended: no, but its leads are shown apart and marked loose).
6. **Cadence.** Each January and when a law takes effect mid-year is jason's procedure, not a statute (proposed policy); the board adopts it as a duty assignment.
7. **Statute scope.** The leads read the Davis-Stirling Act only; other codes are not read. Whether to widen them is a separate build.
