# Run links

A cross-cutting spec, no screen of its own: addresses for one item on the screens that own it (`#/approvals?id=`, `#/decisions?id=`, `#/notices?key=`, `#/controls?key=`, and more), and a one-line banner on those screens that points back to the run · phase 2, after Work · CLI: none for the banner (a read); `jason workflow --attest RUN STEP` is the CLI for a decision step today · parent: [work.md](work.md), "Where a step's work happens"

## In the console

**Built.**
- The run page (`WorkRunView`, `RunStepPanel`) lists a run's links and links out, but only to the screen, never to the item. A link row is `{kind, id, step, label, state, read, screen?, problem?}` (`_link_state` in `src/jason/web/extra/work.py`). `screen` is set for two kinds only: `approvals` and `work`. The page builds `#/${screen}` from it. A `plan` step's link is `#/approvals` and a `decision` step's is `#/decisions`, both bare.
- The router (`App.tsx`) splits the hash at `?`. Only `view=owner` is read there. Each screen reads its own parameter: `#/actions?item=ID` (`focusedItem`) and `#/controls?key=KEY` (`focusedControl`, built) work. Nothing else does.
- `#/approvals` keeps the open plan in `useState` (`ApprovalsView`, `PlanApprovals`); it reads no hash. `#/decisions` (`DecisionsView`) lists the next meeting's candidates from `/api/agenda-plan` and cannot show an earlier decision by id. `#/hearings` and `#/rules` open a row from local state. `#/meetings` reads `GET /api/meetings?date=`, but the view takes no hash. `#/notices` is a proposed screen ([notices.md](notices.md)).
- A run link row carries only the run id, no definition. `WorkRunView` finds the child's definition by fetching `/api/work?state=all` (`useRunDefinitions`). `store.locate(data_dir, rid)` already does it for one id.
- `LinkKind` (`src/jason/workflows/types.py`) has eight members. The event's `links[]` takes any kind string; `_link_state` reads the state of three (approval, job, run) and shows the rest as "state not read here".
- `GET /api/decisions?meeting=` (P2) lists decisions; it takes no `id`. `POST /api/decisions` records one; `by` is typed text, not the signed-in name.
- No owning screen shows that its subject belongs to a run. `PartOfRunBanner` is named in [design-brief-property-and-units.md](../design-brief-property-and-units.md) and not built.

**This spec adds** the addresses, a banner loader, the `definition` field on link rows, and a proposal so a decision step can finish from the web. Everything below is read-only except section 4, which is marked a proposal.

## Purpose and personas

A run and the screen that owns a step's work should be one click apart in both directions, at the item and not just the screen. The run reads; the owning screen writes; neither copies the other.

- **Secretary:** records the board's decisions and postings; wants to see which step a decision answers.
- **Treasurer, president, vice president, director:** open an approval or a control from a run, and see on it that a run is waiting. Directors and officers have the same access to information.
- **Manager:** works the run; follows a link to the item and back.
- **Administrator:** repairs; sees the same banner, acts as no one else.
- **Counsel, owner:** no banner. Counsel reads a run's evidence on grant, not its list; the owner view reads neither `work` nor `run-banner`.

## Data

### 1. Every link kind, its address, its state

`LinkKind` is the first eight rows. The last six are subjects the owning screens hold that a link cannot name today (proposed members; decision 2).

| Kind | Address (`#/…`) | State read from | Status |
|---|---|---|---|
| `approval` | `approvals?id=apr-31` | `approvals.load(id).status` | State read: built. Screen link: built, without `id`. **Add:** `PlanApprovals` opens `?id=`, scrolls and focuses it; a superseded id opens its successor (the 409 path exists) |
| `job` | `jobs?id=N` (administrator only) | `jobs.db`, newest 500 | State read: built. **Add:** a link for an administrator; other viewers see the state as text |
| `followup` | none: the Tasks drawer of the dock | follow-ups store | Not read, no screen. **Add:** read the state; address per decision 7 |
| `board-item` | `actions?item=ID` | `board/items.json` | Address: built. **Add:** read the state (a held executive item as `executive-<n>`, general words only) |
| `task` | none: the Tasks drawer | action register | As `followup` |
| `doc` | not a route: a `Doc` chip on `drive:`, `file:`, or `library:` (one logged view) | the document store | `Doc` built. **Add:** a `doc` link row draws as a `Doc` chip, not as text |
| `campaign` | `owner-info?campaign=ID` | `forms/campaigns.json` | **Add:** the state read and the parameter |
| `run` | `work/<definition>/<id>` | the run store | Built, but the row lacks `definition` (section 3) |
| `decision` | `decisions?id=2099-03-10--item-7` | `board/decisions.json` | **Add:** the parameter, and `GET /api/decisions?id=` (derives the meeting from the id). An executive decision only in the private view |
| `notice` | `notices?key=owner-info-2099` | `notice_ledger`, `notice_record.build` | Screen proposed; its `?key=` is in notices.md |
| `control` | `controls?key=KEY` | the control store | Built (`focusedControl`) |
| `hearing` | `hearings?run=ID` (opaque) | `zoom.hearings` | **Add** the parameter. Today's key is the day and an address slug: never in a link, a banner, or a URL ([hearing-process.md](hearing-process.md)); the opaque run id first |
| `rule-change` | `rules?key=KEY` | `/api/rule-changes?key=` | Loader built; **add** the view's read of the hash |
| `meeting` | `meetings?date=2099-03-10` | `GET /api/meetings?date=` | Loader built; **add** the view's read of the hash |

The server sends `screen` for every kind that has one. The UI owns the parameter name and builds the address in one table (`ui/src/lib/runLinks.ts`, `runHref(kind, id, definition?)`, `null` when there is no route). The run page, the step panel, the banner, and the Decisions picker use it and nothing else.

### 2. The banner loader (to add)

`GET /api/run-banner?subjects=approval:apr-31,board-item:bi-12` (batched, up to 50; one `kind=&id=` pair also works). Gate: as `work-run`: signed out 401; a viewer whose offices do not open P2, or the owner view, 403 with `access.may_see`'s sentence; counsel 403. Reads disk; writes nothing.

```
{ found, asOf, caveats,
  banners: [ { subject: "approval:apr-31",
    runs: [ { definition: "bill-attach", id: "run-3f9a01c2d4", label: "Bill attach: Example Electric, Oct",
              runState: "active", held: false,
              step: { id: "bill-attach.4", n: 4, of: 7, title: "Approve the attachments", state: "needs a person", role: "treasurer" },
              via: "link" } ],
    answers: [ ... ] } ] }
```

- Offices and labels only: `label` is the list's own (`_mask`ed, as in `GET /api/work`); `role` is an office word; no `by`, no person, no subject.
- **How it finds runs:** the run index row (`store.index_put`) gains `holds`, the `kind:address` of every link and of the board item a `decision` step names. `_index` runs after every write, so it stays current, and `reindex` rebuilds it. The loader reads the index for open runs, then folds only the matching ones (a dry read) so the step and its state are what the run page would show. The index is a hint; the run page is the truth.
- `answers[]` (only for `board-item:` and `decision:` subjects): the open `decision` steps the subject may answer, `{definition, id, label, step{id,n,title}, role, canRecord}`; `canRecord` is true only for the viewer who holds the step's role. Section 4 uses it.
- A held matter (CIV 4935(e)) outside the private view: `held: true`, `label` is the general words, `step` is absent.

### 3. `definition` on link rows (to add)

`_link_state` adds `definition` to every row: the run's definition for kind `run` (`store.locate`), `null` for the others. `RunLink` gains `definition?: string`. `useRunDefinitions` and its `/api/work?state=all` fetch go away. A parent run's link (`run.parent`) gets it too.

### 4. A decision step finishing from the web (a proposal)

Today `attest` on a `decision` step is refused on the web (`DECISION_ELSEWHERE`), and the run keeps only the secretary's `record` text and outcome ("the decisions store is not linked by id"). The secretary has to attest at a terminal. Proposed:

- **The reference.** The Decisions screen records a decision with an optional `run` and `step`. In `DecisionCard`: "This decision answers: [none | Rule change: quiet hours, step 13: The board decides]", listing `answers[]` where `canRecord`. Default none. When the candidate's board item is held by exactly one open decision step, it is offered first, never chosen for the secretary.
- **What changes in `jason.tasks.decisions`.** `Decision` gains `run: str = ""` and `step: str = ""`. `EDITABLE` gains both. `_validate` requires `step` to come with `run` and both to be strings in a run id's shape (`run-` and ten hex). The store stays a store: it checks the shape and imports nothing from `jason.workflows`. A `for_run(data_dir, run, step="")` finder and a history line ("linked to run R, step S") are added. The id (`<meeting>--<item>`) does not change; a re-record keeps the reference unless the body clears it. Old rows read `""`.
- **The writer** (`POST /api/decisions`) validates a given reference before writing anything: the run is open, the step is a `decision` step in `needs a person`, the signed-in person holds its role (the secretary), and `by` is the signed-in person's name (a `by` naming someone else is a 403, as in `POST /api/write/work`). A refusal says why, in the engine's sentences, and nothing is recorded. No reference always works.
- **The run's next open reads it.** A `decision` reader (like the `plan` step's approval reader) finds a decision with `run` and `step` and a final outcome (`FINAL_OUTCOMES`) and appends one `decided` event: `by` the decision's recorder, `record` = `decision:<id>`, `outcome` as recorded, once (idempotent by the id). "Tabled" or "pending" is recorded and the step stays open. A later edit of the decision shows as "changed since" (the step's evidence gains `file:board/decisions.json#<id>`), never a silent repeat.
- **The run page** then reads the mover, second, and votes by id (`GET /api/decisions?id=`), which removes the first "not composed" note, and links `#/decisions?id=…`. It still offers no approve, vote, or adopt control.
- jason does not decide, vote, or choose the step. It carries a reference the secretary chose.

## Layout

The banner (`PartOfRunBanner`): one line in flow above the thing it describes. It pushes content down; it never covers a control.

```
+------------------------------------------------------------------------------------------+
| Plans of writes > apr-31                                                                 |
| [list-checks] Part of run Bill attach: Example Electric, Oct, step 4: Approve the        |
|   attachments · needs a person (treasurer) · Open the run                                |
+------------------------------------------------------------------------------------------+
| PlanReview: ... every check, decision, second signature, and apply, as always ...        |
```

Decisions: the banner heads the matter's section, and the picker sits inside `DecisionCard`.

```
| Quiet hours for the pool, Board meeting 2099-03-10                                       |
| [list-checks] Part of run Rule change: quiet hours, step 13: The board decides · Open    |
| [DecisionBrief ...]                                                                      |
| DecisionCard: motion, mover, second, votes, outcome                                      |
|   This decision answers: ( ) none  (o) Rule change: quiet hours, step 13                  |
|   The secretary records it; the step reads done when the run is next opened.   [Record]  |
```

Two runs: the first line in full, then "and 1 more run" as a disclosure listing the other. The run page's link row becomes `approval apr-31 [approved]` as a link to the item, `child run Notice delivery [done]` as a link with `definition`, and a `doc` as a `Doc` chip.

## Components

Built: `Pill`, `Glyph`, `Doc`, `Command`, `Confirm`, `RemoteView`, `ControlStepNotice` (the model: a one-line aid, silent on failure). To add:

- `PartOfRunBanner` (props `runs[]`; states: none (draws nothing), one, several, held, loading (draws nothing), failed (draws nothing)).
- `useRunBanners(subjects)` (batches one request per screen render, silent on any error, like `useControlNotice`).
- `runHref` and the kind table (`ui/src/lib/runLinks.ts`).
- `AnswersStep` (the picker in `DecisionCard`; section 4).
- An opener for each owning screen that reads `?id=`, `?key=`, `?run=`, `?date=`, or `?campaign=`: scroll into view and focus the item, like `focusedItem`.

## Actions

| Control | Does | Approval? | CLI |
|---|---|---|---|
| "Open the run" in the banner | Goes to `#/work/<definition>/<id>`; reads | No | `jason workflow --show RUN` |
| A link row on a run | Goes to the owning screen at the item; reads | No | none |
| "This decision answers" (section 4) | Adds `run` and `step` to the decision the secretary records | No: the decision is the secretary's record, not an approval | `jason workflow --attest RUN STEP --by NAME --outcome WORD --record REF` (built engine act) |

The banner has no act of its own, and a run link never decides, approves, or applies. The two-person rule, fingerprints, and logs of the owning screen apply as if the person had arrived by hand.

## States

- **Not in any run:** nothing is drawn. No empty banner.
- **Loader fails, or the viewer is refused:** nothing is drawn, and the page works as before. The banner is an aid and never the gate.
- **A run past a legal date:** the banner adds "past a legal date" in the word, not colour alone.
- **Paused, failed, draft:** the run's state word is shown as the engine gives it.
- **A step done:** no banner (the run no longer waits on this item). The run page still links the item.
- **A link whose item is gone:** "state not read here" on the run, and the owning screen says "no approval apr-31" with its own 404 sentence.
- **Held:** "Part of a run on a matter held under Civil Code 4935(e)" with no step; opening the run is logged (`access/served.jsonl`).
- **Stale index:** the loader folds the run it found, so a step that moved reads as it is. A run the index misses shows no banner until the next write or `reindex`.

## Privacy

- **No person's name** in a banner, a link, or a URL: not the mover, the secretary, the treasurer, nor a unit. Offices and labels only. A URL carries an id or a key, never a name, an email, or an address (so no hearing key with an address slug).
- A banner appears only to a viewer who may see the run: the same gate as `GET /api/work-run`, checked on the server. The page hides nothing it is not entitled to show, and shows nothing the server refused.
- The same banner for every board member and the manager: directors and officers have the same access to information. Only the `answers[]` picker depends on the office, because recording is the secretary's duty, not a matter of access.
- The banner never hides, disables, or reorders a control, and relaxes no check. It adds no skip and no shortcut past a second signature.
- An executive-session matter goes by its general words (section 2).

## Acceptance criteria

1. `GET /api/run-banner` signed out is 401; for a viewer whose offices do not open P2, for counsel, and in the owner view it is 403; it writes nothing.
2. A subject held by an open run's step returns that run with `definition`, `id`, `label`, the step's `id`, `n`, `of`, `title`, and `state`; a subject held by none returns an empty `runs`.
3. No response, banner, or URL contains a person's name, an email, a unit, or an address.
4. Every `RunLink` row has `definition` for a run link; the run page makes no `/api/work?state=all` request to find it.
5. `#/approvals?id=apr-31` opens that plan, scrolls to it, and focuses it; an unknown id says so and opens the list.
6. `#/decisions?id=2099-03-10--item-7` shows that decision's matter, including a past meeting's; `?id=` for an executive decision outside the private view shows the held line.
7. `#/controls?key=` and `#/actions?item=` still work as built.
8. The banner shows "Part of run NAME, step N: TITLE", its state word, and a link, on an Approvals plan, a Decisions matter, a notice, a control card, and a hearing; it draws nothing when there is no run, an error, or a refusal.
9. Every control on the owning screen is present and behaves the same with and without the banner.
10. (Proposal) A decision recorded with `run` and `step` by the secretary completes the step at the run's next open with one `decided` event, once; a second open adds none; "tabled" leaves the step open.
11. (Proposal) A reference to a step that is not open, or a recorder who does not hold its role, or a `by` that is not the signed-in person, is refused with a sentence, and no decision is recorded.
12. (Proposal) The decision step still shows no approve, vote, or adopt control.
13. The tests use "Oakview" and 2099 dates and read no real record.

## Decisions for the user

1. **Parameter names.** `?id=` for approvals and decisions, `?key=` for controls, notices, and rules, `?run=` for a hearing, `?date=` for a meeting, `?campaign=` for owner information, as each screen's own loader names it (recommended). The alternative is one `?item=` everywhere.
2. **Widen `LinkKind`?** Add `decision`, `notice`, `control`, `hearing`, `rule-change`, `meeting` (recommended: a step then links the exact item), or keep eight and carry the rest as `board-item` and `doc`.
3. **How the banner finds runs.** A `holds` column in the run index (recommended: cheap, kept by every write) or a fold of every open run per request (no new data, slower as runs grow).
4. **Section 4.** Adopt the reference (recommended, it matches how a `plan` step reads its approval), or keep the secretary's terminal attest and add only the read of the decisions store by id. Also: who is `by` of the `decided` event (recommended: the secretary who recorded the decision), and whether a lone matching step is preselected in the picker.
5. **Banner text for member families.** The run's own label (as the list shows it) or, for hearing, delinquency, and enforcement runs, the definition's title and the opaque id (recommended where a label could name a unit).
6. **Held matters.** A banner by general words with no step (recommended) or none at all.
7. **Follow-up and task links.** They have no screen. Build `#/followups?id=`, open the Tasks drawer at the item, or leave them as text with their state.
8. **Several runs on one item.** The first in full and "and N more" (recommended), or all, one line each.
9. **Treasurer and manager.** They see the banner like every board member and the manager, since they read `work` (assumed).
