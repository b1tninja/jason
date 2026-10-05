# Members & units

A new screen, `#/members` (`?unit=` a PayHOA unit id only), in the Governance group · phase 4, after P2 masking · CLI: `jason owner-info`, `jason party`, `jason delivery`

## In the console

None. **Owner information** (`#/owner-info`) shows the cycle's planned writes as a `ConfirmList` and the owners by standing, and the engine's plan for the same cycle is reviewed in `#/approvals`. Nothing lists the owners with how notices reach each, or brings one unit together.

**This spec is the whole screen, as proposed.** The loaders to add are `members` (`owner_info.ledger` and `summary` from the stored catalog, and `notice_delivery.plan`) and `unit` (`party_brief`, `unit_brief`, `parcel_liens`, `association_collections`' row, `new_owners`). Because a unit's page shows contact details and occupancy (P2), it waits on server-side masking with a logged reveal (`MaskedField`); the owners table alone (names, units, statuses, delivery channel: P1) could come first.

## Purpose and personas

Who owns each unit, how notices reach each owner, and where each owner stands in the owner-information cycle. One unit's page brings together what jason knows about it: owners, delivery elections, occupancy, requests, violations, and balance.

- **Manager:** works the cycle from the owners table. Plans the cycle's writes, which makes an approval. Reads one unit before answering an owner.
- **Director:** reads a unit before a decision that concerns it.
- **Treasurer:** reads balances and delinquency by unit. No contact details.
- **Secretary, reviewer, counsel:** no access. The secretary's need for an owner's delivery standing is met on the Notices screen, in counts.

## Data

**The owners table**

| Part | Source |
|---|---|
| Each current owner: unit, name, `OwnerStatus`, how notices go now (`delivery`), the latest answer's date and source, and the next action (`actions`) | `jason.tasks.owner_info.ledger(found, matched, tags, cycle, earlier=..., today=...)`, from the stored catalog. The rows are built today in `commands.owner_info._rows`; moving that into `jason.tasks.owner_info` is a prerequisite ([mvp.md](../mvp.md)) |
| Totals by status and by delivery, and the cycle's deadlines | `owner_info.summary(rows, cycle, today)`: `currentOwners`, `byStatus`, `delivery`, `deadlines[]` (`what`, `date`, `daysLeft`) |
| Delivery totals: by broadcast, by Mailroom, and what is left | `jason.tasks.notice_delivery.plan(units, people, tags)` (`jason delivery`) |
| New owners | `new_owners(days=365)` |

**One unit**

| Part | Source | Level |
|---|---|---|
| Owners by deed, and the PayHOA members on the unit | `party_brief(query)` (`jason.mcp.county`): owners by deed, PayHOA standing and members; `ownership_record(apn)` for the chain | P1 |
| Title, liens, taxes, solar | `unit_brief(apn)`, `parcel_liens(apn)` | P1 |
| Delivery election, by owner | The owner's `OwnerInfo` row: `status` (`OwnerStatus`), `delivery` ("mail", "email", "email and mail"), and the answer it came from (`answer.source`, `answer.submitted`). The election is the owner's PayHOA delivery tags; only those decide delivery | P1 |
| The owner's answer this cycle | `member_preferences.Matched` on the row: `record`, `choices`, `tag_changes`, `confirm`, `notes` | P2 for addresses and emails |
| Occupancy: as the owner stated it | The answer's `occupancy` choice (`owner_responses.Context.answers`) | P2 |
| Occupancy: as the records show it | The unit's occupancy tags (`community.tags`), and the rental register's row: lease on file, whether it runs, tenants, property manager (`jason.tasks.rental_register`) | P1 for the tags and lease standing; P2 for tenants and the manager's contact |
| Where the two differ | The response policy's findings for the unit's latest answer: `owner_responses.triage(context)`, rule `occupancy-vs-tag`, `Outcome.BOARD`, with its `board_item`. Read live, as a job | P1 |
| Requests | `api.member_requests(open_only=False)` filtered to the unit: `kind`, `received`, `due`, `standing`, `next` | P1 |
| Violations | `party_brief(query)`'s violations, from `data/payhoa.db` as last synced | P1; the detail of a disciplinary matter is P3 |
| Balance | `association_collections()`'s row for the unit (`standing`: `RELEASE_DUE`, `LIEN_SECURES_DEBT`, `OWED_NO_LIEN`, `CREDIT`; `pastDueCents` and `balanceCents`), and `party_brief`'s PayHOA balance | See [privacy](#privacy) |

A unit's URL carries its PayHOA unit id only. Finding a unit by owner name or address is a POST search, and its results page has no query string.

## Layout: the owners table

```
+------------------------------------------------------------------------------------------+
| Members & units                                         [Plan the cycle's writes]        |
| Owner information 2099 · answers in PayHOA by Nov 1 [29 days left] · annual reports Nov 30 |
| 48 current owners: 21 answered · 12 election on file · 3 earlier election · 12 no election |
| Notices go: 30 by mail · 14 by email · 4 by email and mail                                |
| Synced Oct 3, 06:00 · jason sync-catalog                  CLI: jason owner-info [copy]    |
+------------------------------------------------------------------------------------------+
| Status [All v]  Delivery [All v]  [Filter]          Find a unit or owner [_______] [Find] |
+------------------------------------------------------------------------------------------+
| Unit   Owner      Status                         Notices go   Latest answer   Next        |
|------------------------------------------------------------------------------------------|
| 12     Owner A    Answered this cycle            mail         Oct 2 (form)    2 writes    |
| 14     Owner B    No election: first-class mail  mail         -               tag mail   |
| 15     Owner C    Answered this cycle            email        Oct 1 (form)    held       |
| 21     Owner D    test                           -            -               -          |
+------------------------------------------------------------------------------------------+
```

## Layout: one unit

```
+------------------------------------------------------------------------------------------+
| Members & units > Unit 12 · 123 Main St                                                  |
+------------------------------------------------------------------------------------------+
| OWNERS                                      | DELIVERY OF NOTICES                         |
| Owner A (by deed Mar 4, 2097; PayHOA member)| Owner A: answered this cycle                |
| Owner E (by deed; no PayHOA member)         |   Notices go by mail                        |
|                                             |   From: the PayHOA form, Oct 2 [Form]       |
|                                             |   Mailing address: 1•• M••• St [Show]       |
+---------------------------------------------+---------------------------------------------+
| OCCUPANCY                                                                                 |
| As the owner stated it:  [Show]  (Owner A's answer, Oct 2)                                |
| As the records show it:  no rental tag · no lease on file                                 |
| [HeldNote inline] The two differ. Held for the board: BI-2099-04. No owner contact.      |
+------------------------------------------------------------------------------------------+
| REQUESTS (2)                               | VIOLATIONS (1)                              |
| 1042 architectural · OVERDUE 6 days >      | Sep 2099 · landscaping · open               |
| 0987 maintenance · answered on time        | Synced Oct 3, 06:00                          |
+--------------------------------------------+---------------------------------------------+
| BALANCE                                                                                  |
| Past due: $412.00 · owed, no lien · ledger synced Oct 3, 06:00                          |
| jason does not send an account to a collection agency, record a lien, or foreclose.      |
+------------------------------------------------------------------------------------------+
| TITLE, LIENS, AND TAXES                                                                  |
| Title: 2 conveyances on record · no lien of record · taxes current                       |
+------------------------------------------------------------------------------------------+
```

Below 768 px the two-column bands stack, in the order shown.

## Components

`ScreenHeader`, `DataTable`, `SearchBox`, `Card`, `Pill` (`OwnerStatus`'s words), `DueDate` (the cycle's deadlines), `MaskedField` (proposed), `Evidence`, `HeldNote` (inline, on an `occupancy-vs-tag` finding), `Money`, `Command`, `RemoteView`.

The owner statuses are `OwnerStatus`'s own words: "answered this cycle", "election on file in PayHOA", "an earlier written election, applied (confirm this cycle)", "an earlier answer to confirm", "no election: first-class mail (4040(a)(2))". The table may shorten them with the full words in the cell's accessible name.

## Actions

| Control | Does | Approval? | CLI |
|---|---|---|---|
| Plan the cycle's writes | shown as the command; the plan then appears in `#/approvals` | Makes an `owner-info-tags` approval: the tags, and the request completions that follow them | `jason approvals plan owner-info-tags --by NAME` |
| Plan the delivery tags | The `payhoa.delivery.tags` planner (phase 3) | Creates an approval | `jason delivery --audit --apply` |
| Filter | GET with `status`, `delivery` | No | `jason owner-info` |
| Find a unit or owner | POST search; results without a query string | No | `jason party "123 MAIN"` |
| Show (a P2 field) | The reveal endpoint for one field of one row | No; logged as `reveal` by kind | — |
| Read the response policy for this unit | shown as a command (a live read) | No | `jason owner-info --responses` |
| Open a request | `#/requests?id=<id>` | No | — |

**There is no control** to message an owner about occupancy, change an occupancy tag, or decide a rental question. A finding of `occupancy-vs-tag` is held for the board, and any owner contact about occupancy waits until the board takes up the board item. There is no control to send an account to collection, record a lien, or start a foreclosure: `association_collections` says these are the board's decisions, and the screen recites that note.

## States

- **No catalog:** "Members are unavailable: no PayHOA catalog on disk. Run `jason sync-catalog`."
- **No cycle set:** the cycle line reads "No owner-information cycle is set in the profile." The table still shows each owner's election from the tags.
- **Test accounts:** labeled "test" and left out of every count (`config.test_memberships`).
- **A unit with no deed on record:** "No deed on record for this unit in the ownership store. This is not proof of ownership either way." With the command that shows what the stores hold: `jason party "123 MAIN"`.
- **No answer this cycle:** "No answer this cycle." Never "did not answer", which would claim more than the record shows.
- **Occupancy with no answer:** "As the owner stated it: no answer on record."
- **Violations unavailable:** the section says so with `jason sync-catalog`; the rest of the unit stands.
- **Triage not on disk:** the policy findings are replaced by the command that reads them. The rest of the unit stands.

## Privacy

| Field | M | D | T | S, R, C |
|---|---|---|---|---|
| Owner names, units, statuses, delivery channel | Shown | Shown | Shown | No access |
| Emails, mailing addresses, phone numbers | Masked; Show, logged | Masked; Show only on an item the director is deciding | Not shown | — |
| Occupancy as the owner stated it | Masked; Show, logged | Masked; Show on an item the director is deciding | Not shown | — |
| Tenants and a property manager's contact | Masked; Show, logged | Masked | Not shown | — |
| Balance: the standing word | Shown | Shown | Shown | — |
| Balance: the amount | Shown | In the private view only | Shown | — |
| Delinquency detail beyond the unit (payment plans, notes) | Private view | Private view | Private view | — |
| A disciplinary matter's detail | Private view | Private view | Not shown | — |

The reasoning: a balance discussed as a member's delinquency belongs to executive session (Civil Code 4935(a)), so a director sees the amount in the private view, which records why it was opened. The manager and treasurer work the ledger daily and see the amount. This split is proposed, with the roles ([security-and-privacy.md](../security-and-privacy.md#roles)).

## Acceptance criteria

1. The owners table's counts match `owner_info.summary` for the fixture, with test accounts labeled and not counted.
2. The plan command, run, makes exactly one `owner-info-tags` approval and supersedes an open one of the same scope; the screen links it in `#/approvals`.
3. The unit page renders with the unit id in the URL and no name or address in any query string.
4. For a treasurer, no email, address, phone, or occupancy statement appears in the HTML, masked or not.
5. With the private view off, a director's unit page shows the balance's standing word and no amount.
6. An `occupancy-vs-tag` finding renders as held for the board with its board item, and the page has no control that contacts the owner or changes the tag.
7. "No answer this cycle" is the only wording for a missing answer.
8. The cycle's deadlines show as deadline badges with days left, from `AnswerCycle.deadlines`.
