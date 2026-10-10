# Life safety

A new screen, `#/life-safety`, under Records beside Insurance · phase 3 · CLI: `jason deadlines`, `jason applies`, `jason inspections`, `jason gmail --file-vendor`, `jason sync-report-portals` · MCP: `life_safety` (to add), with `vendor_portal`, `document_models`, `insurance_review`, `email_threads`, `board_items` behind it

## In the console

None. Its parts are scattered:
- The dock's Deadlines lists the fire obligations among every other date.
- `#/actions` holds the board items a deficiency becomes.
- `#/insurance` holds the policy that makes the sprinklers a condition of coverage.
- The reports themselves are in Drive, the library, and a vendor's report portal.

This screen puts one association's fire protection systems on one page: each system with its standard, its schedule, its vendor, its reports, its open deficiencies, and what the insurer requires. It renders what the loader returns and never works out a status itself. The reference it rests on is [../../fire-protection.md](../../fire-protection.md).

## Purpose and personas

The question it answers is "are our fire protection systems inspected, tested, and in working order, and can we prove it?" It also answers the questions behind that one: what is overdue, what is broken and since when, which vendor owes what, and what the insurer and the fire authority have been told.

- **Manager:** books inspections, chases reports, opens the entry notices, records what cleared each deficiency.
- **Director:** reads the summary before a meeting; sees what the board must decide (a contract, a repair over the manager's limit).
- **Secretary:** files the reports and keeps the records (five years past the next inspection, 19 CCR 904.1(b)).
- **Treasurer:** reads what each vendor is paid for against what it delivered.
- **Counsel (on grant):** reads the impairment record for an insurance question.
- **Owner:** not at first; an owner version (what is inspected in my unit, and when) is its own decision.

## Data

| Part | Source | Level |
|---|---|---|
| The systems: name, standard (13R, 13D, NFPA 72, backflow), buildings, the vendor for each kind of work, the obligations that keep it, the insurer's safeguard symbol | `Community.life_safety_systems()`: a `LifeSafetySystem` record per system (`jason.community.life_safety`), empty by default. Every fact is the profile's, and a standard is entered only with the record that states it. The obligations that keep a system are those whose `applies` condition holds for it (`life_safety.applicable`, `jason applies`); an undetermined one is shown with its question. The insurer's safeguard symbol is still **to add** | P0 |
| The schedule: each obligation's last record, next due, status (overdue, due, current, none on record) | `jason.tasks.deadlines.calendar` (behind `/api/calendar` and the dock's Deadlines), filtered to the systems' obligations | P0 |
| The rule each obligation rests on | the obligation's `authority`, recited from the authorities shelf (HSC 13195-13199; the State Fire Marshal's Title 19 text) by `cite_document` | P0 |
| Which periods have a report on file | `jason.tasks.inspections.review` (`jason inspections --json`): for each system and each obligation that applies, each period's standing (covered, partly on file, not on file, not yet due) with the document's name, date, and id; the reports it could not place and the field each lacks; the reports filed but not read; and the record-keeping provisions recited from the shelf, or said to be missing from it | P1 (reports name units) |
| Reports: each inspection or test report, its date, system, buildings, vendor, result (passed, failed, incomplete), and where it is filed | the library's inspection reports (`library_search(kind="inspection_report")`); `document_models` (`jason.community.models.legal_inspections`: result, deficiencies, devices); the vendor's report portal (`jason.tasks.report_portals`, `data/vendors/<key>/reports.json`); the filing log (`data/drive/vendor-files.jsonl`) | P1 (reports name units) |
| Deficiencies: each one found, the report it came from, its system and building, whether it impairs a scheduled safeguard, the record that cleared it, and whether the insurer was told | a deficiency register, **to add**: `data/life-safety/deficiencies.json`. Rows are proposed from the report models and confirmed by a person (`by`). The clearing record (an invoice's line items, an AES 10, a later passing report) is a `DocRef` | P1 |
| Vendors: who does what, their licenses (number, class, as read and when), what they owe (the AES report, the report to the fire authority, the itemized invoice), and what is on file | the sender directory and `VendorPortal` rows (`license`); `vendor_portal` for a vendor with a portal; payments by vendor from the books; `email_threads(sender=...)` for what is awaiting whom | P0, P1 for amounts |
| The insurer's condition: the policy, the endorsement, the symbol, the buildings scheduled | `insurance_review` (the policy pages' protective-safeguards finding) | P1 |
| Board items about these systems | `/api/board-items`, those whose evidence or category is safety | P0 |

A new loader, `life-safety` in `jason.web.extra.life_safety`, composes these by system. Nothing on load calls Gmail, Drive, PayHOA, or a vendor's portal. A sync is a person's job: `jason gmail --file-vendor`, `jason sync-report-portals`, or `jason vendors --sync`.

## As built (2026-10-10)

`GET /api/life-safety[?system=KEY]` (`jason.web.extra.life_safety`) is built, read only, for a signed-in roster person. It composes `jason.tasks.inspections.review` (each system's obligations with their periods and the deadlines calendar's row), the backflow program and the watchlist (`jason.tasks.backflow`), and the report portal with the last filing plan (`jason.tasks.report_portals`). Every standing is a word the loader says (`current`, `done late`, `upcoming`, `due soon`, `overdue`, `needs input`, `none on record`, `no evidence`), and the counts are made there: `summary` has `systems`, `obligations`, `overdue`, `dueSoon`, `needsInput`, `noneOnRecord`, `unplaced`, `questions`. A part that cannot be read is `{found: false, note}` and the rest stands.

**The deficiency register is built** (`jason.tasks.deficiencies`, `data/life-safety/deficiencies.json`, `jason life-safety`). A row is proposed once from a report's reading (`--propose`), then a person confirms it, says whether it impairs a scheduled safeguard, links the library record that cleared it (an invoice's line items, an AES 10, or a later passing report that reads passed with nothing open; free text and a subject line are refused), and records that the insurer was told (the day and the record of what was sent; jason contacts no insurer). It is append only: each act carries who and when, the latest word on a question wins, and a correction is a later act. `POST /api/write/life-safety/<id>` takes `{act: confirm | impairs | cleared | insurer-told}` (and `propose` for key `propose`) in the signer's own name, for an office that opens P2, never while an admin views as someone else.

The loader reads it. The proposed, open, and cleared counts show to every signed-in person; which deficiencies impair a safeguard, what cleared each, and whether the insurer was told are P2 (they may bear on a claim), so for a viewer whose office does not open P2 `impairments` and `insurerNotTold` are `null` and `deficiencies.rows` is empty with `held`. The banner ("A person recorded an impairment on a scheduled safeguard, and no record shows the insurer was told") is raised only from what a person recorded, never inferred.

**Not composed yet,** each listed under `notComposed` with its command: the insurer's condition, the vendors' licences and payments (P1), and the board items.

## Layout

```
+----------------------------------------------------------------------------------------+
| Life safety                                                   [Refresh] (job) [Ask]   |
| 4 systems · 3 overdue · 2 open deficiencies (1 impairs a safeguard) · insurer: P-1     |
| Last read: deadlines Oct 4 · reports Oct 4 · portal Oct 3        CLI: jason deadlines  |
+----------------------------------------------------------------------------------------+
| ! An impairment is open on a scheduled safeguard, and no record shows the insurer was  |
|   told. [Recite the condition]  [Open the board item]                                   |
+----------------------------------------------------------------------------------------+
| Sprinklers, buildings with risers (NFPA 13R)                  vendor: <sprinkler co.>  |
|   Schedule                     last        next        status                           |
|   Quarterly inspection         —           —           none on record                  |
|   Annual inspection and test   2023-03-14  2024-03-14  overdue 934 days                 |
|   Five-year internal           —           —           none on record                  |
|   Gauges (5 years)             2006?       —           overdue (needs input)            |
|   Sample test (20 years)       —           2027-11     due in 13 months                 |
|   Deficiencies   2 open · 14 cleared        [Show]                                      |
|   Reports        AES 2.1 2023-03-14 [chip]  · 9 of 24 units not entered                 |
|   Owes us        the annual (signed 2024-04-17) · reports to the fire authority         |
+----------------------------------------------------------------------------------------+
| Fire alarm and monitoring (NFPA 72)                           vendor: <alarm co.>      |
|   Semiannual test              2025-09-19  2026-03-19  overdue 199 days                 |
|   Reports        2025-09-19 ×2 [chips] · portal: 3 more not filed  [File them]          |
|   Deficiencies   waterflow (bldg) failed 2025-09-19 · open · insurer told: no record    |
+----------------------------------------------------------------------------------------+
| Backflow on the fire service                                  vendor: <tester>         |
|   Purveyor's annual test       2026-05-01  2027-05-01  current                          |
|   Forward-flow (NFPA 25 13.6)  —           —           in the sprinkler annual: overdue |
+----------------------------------------------------------------------------------------+
| Sprinklers, townhouse buildings (NFPA 13D)                    vendor: none             |
|   NFPA 25 does not apply (its scope) · the insurer's P-1 still does · none on record    |
+----------------------------------------------------------------------------------------+
| Vendors   [table: vendor · work · license (as read, when) · owes · last report · paid]  |
+----------------------------------------------------------------------------------------+
```

A system's card opens to a full page (`#/life-safety?system=<key>`) with three tabs:
- **Schedule:** each obligation with its rule recited, its evidence, and its history.
- **Deficiencies:** the register for that system, each row with its report and its clearing record.
- **Reports:** every report, newest first, with the `Doc` preview.

Under 720 px, the cards stack, the schedule becomes a list of name, status, and next, and the vendors table becomes cards.

## Components

- **Layout:** `ConsoleShell`, `PageHeader`, `RemoteView`, `Section` per system.
- **Status and time:** `StatusPill` (overdue, due, current, none on record, needs input), `Freshness` with `Command`.
- **Recital:** `Recitation` for the rule (HSC, 19 CCR) and for the policy's condition, each followed by a `ReadingLabel` for jason's reading. One example is "the monitoring of the waterflow switch is a related supervisory service".
- **Records and tables:** `DocRef` and `Doc` for reports and clearing records. `DataTable` for the schedule and the vendors.
- **Proposed:** `DeficiencyRow` (still to build): the finding, its report, impairs-a-safeguard, cleared-by, insurer-told, each a field with its source.

## Actions

| Control | What it does | Writes | CLI |
|---|---|---|---|
| Refresh | Reads the stores again: deadlines, the library, the filing log, the portal's last sync | nothing | `jason deadlines` |
| File them (reports on the portal not in Drive) | Queues the report-portal sync and the filing job | a job; Drive writes as an approval | `jason sync-report-portals`; `jason gmail --file-vendor <vendor> --yes` |
| Confirm a deficiency | Accepts a row proposed from a report into the register | jason's store, with `by`, behind `Confirm` | `jason life-safety --confirm <id> --by <name>` (to add) |
| Record what cleared it | Links a clearing record (a `DocRef` the person picks) and the date | jason's store, with `by` | `jason life-safety --cleared <id> --record <ref> --by <name>` |
| Record that the insurer was told | Records the date and the record (the email or letter to the agent) | jason's store, with `by` | `jason life-safety --insurer-told <id> --record <ref> --by <name>` |
| Draft the entry notice | Opens a notice of entry for the units an inspection needs, from the notice template | a draft only; a person sends it | `jason notices` (the template) |
| Draft a request to the vendor | Offered on a system card with an obligation overdue, with no record, or with a period not on file. It drafts an email asking the servicer for the reports it holds after the last on file, and a proposal for the items. Before the person picks the recipient from the suggested addresses, the action shows the vendor's waiting mail and the agreement on file | a Gmail draft only; a person sends it | `jason draft --proposal-request <system> --to <address> --yes` |
| Open the board item | Goes to `#/actions` for the item | nothing | `jason board` |

No control books a vendor, accepts a proposal, pays an invoice, tells the insurer, or sends anything. Each is a person's act, recorded here after it happens.

## States

- **Empty:** "The specification lists no life safety systems." Then point to `Community.life_safety_systems()`.
- **Unavailable:** a store that could not be read is named with its command. Examples: "Reports are unavailable: no library on disk. Run `jason library`." "The vendor's portal has not been synced. Run `jason sync-report-portals`."
- **None on record:** "No quarterly inspection on record. A record kept outside jason's stores is not seen." It never reads as "not done".
- **Needs input:** a fact the profile lacks, such as a system's install date for the 20-year test or a gauge's date. The command or question that supplies it follows.
- **A report jason could not read:** listed by name with "not read", never with a guessed result.
- **A report jason could not place:** listed as unplaced with the field its reading lacks (the system, the building, or the inspection date), never put in a period by its file name.

## Privacy

- **Reports** name units (no-access lists, in-unit heads), so they are P1. Lists show building and date. A unit number shows only to a role that may see it, and the owner view never shows another unit.
- **Payments** are P1, shown to treasurer and director roles.
- **Lock box and panel codes** that appear in emails or reports are never shown. They are listed as "a code appears in this record; change it", with the record by name only.
- **The impairment record and the insurer correspondence** may bear on a claim, so they are P2 under a legal hold.

## Acceptance criteria

1. Each system the profile lists appears as a card with its standard, buildings, vendor, schedule, reports, and deficiencies. A system with no records still appears, with "none on record".
2. Every status comes from the loader. No date arithmetic happens in the view.
3. Every rule shown is recited from the authorities shelf with its citation and version before any reading. The policy's condition is recited from the policy pages.
4. An open deficiency on a system the insurer schedules is flagged until the register records the insurer was told or the deficiency cleared. The flag names the condition.
5. A deficiency is cleared only by a linked record. An invoice's subject line is not one; its line items or a passing report is.
6. Nothing on load calls an outside service. Syncs and filing are jobs a person starts.
7. Codes and unit numbers follow the privacy rules above. The 720 px layout keeps every status readable without color.
