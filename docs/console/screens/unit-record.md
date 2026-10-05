# Unit record and loss packet

A tab on a unit's page in Members and units (`#/members?unit=`, a PayHOA unit id only), and `#/loss-packet?unit=&incident=` · phase 4, after P2 masking and the owner sign-in · CLI: `jason unit-record` and `jason loss-packet` (to add) · MCP: `unit_record`, `loss_packet` (to add)

## In the console

No screen, though the loaders and writers are built: `GET /api/unit-record?unit=&plan=`, `GET /api/loss-packet?unit=&incident=&address=`, `POST /api/write/unit-record/<key>` (an owner's entry and its visibility), and `POST /api/write/loss-packet/<key>` (a person's confirmation of one step), all in `jason.web.extra.unit_records` over `jason.tasks.unit_records_view` and `unit_records_write`, with the `Community` methods named below. No view or component draws them. Today a loss is reconstructed by hand from listings, invoices, the declaration, and the policy. [../../unit-records-design.md](../../unit-records-design.md) proposes the record and the packet; this spec is the screen for both. The unit's page ([members-and-units.md](members-and-units.md)) is where the tab sits.

## Purpose and personas

What is in this unit, which items are original and which were changed, and, when something is damaged, which provisions and which policy a person must read to decide who answers for what.

- **Manager:** opens a unit's record before answering an owner; opens the packet when an incident is reported.
- **Director:** reads the packet before a decision on an incident; does not edit.
- **Owner (later):** keeps their own manual; opens their own packet.
- **Treasurer:** reads the deductible step and the figures only.
- **Secretary, counsel:** the packet, as the board's record, with its open questions; counsel for a matter.

## Data

**The unit record**

| Part | Source | Level |
|---|---|---|
| The unit's plan | `unit_characteristics(apn)`: the plan the assessor's measures match (or empty) | P1 |
| The original specification by plan | `Community.original_specs()` (built, empty by default): rows `(plan, component, value, source address, status)`; empty until the developer's papers are read | P0 |
| The effective record | `unit_record.effective(plan, specs, entries)` (pure): the unit's entry if any, else the plan's default, else unknown; each row with status, sources, and verification date | P1 |
| The owner's entries | `data/<profile>/units/<unit>/entries.json` (built: `jason.tasks.unit_records_write`), under a store lock; each entry carries its own visibility | P2; never listed across units |
| An entry's approval | the architectural review record for the unit (the association's own), attached as a `DocRef` when found | P1 |
| The coverage columns | `Community.unit_coverage()` (built, None by default): what the declaration's insurance section lists and what the policy's unit endorsement lists, by component kind, each with its citation; `unit_record.coverage(kind, status)` (pure) gives where the record points | P1 |
| Open questions | `Community.open_questions()` | P1 |

**The loss packet**

| Part | Source | Level |
|---|---|---|
| The ladder: five steps (the item, the origin of the cause, an insured casualty, negligence, the deductible), each with its provisions | `Community.loss_ladder()` (built, empty by default): step number, question, citations; `cite_document` recites each provision whole | P1 |
| The policy: deductible, valuation, forms, the unit endorsement's words | `insurance_policies("master")` and the declarations text (a `Recitation` from the library file) | P1 |
| The incident, if one: its cause, elements, building, dates | `incident_history(address=…)` for the unit and its building; the claim files only as counts (a claim's letters are confidential and stay held back) | P2 |
| Prior incidents at the unit and building | `incident_history`, counts | P2 |
| The deductible guidelines | `Community.deductible_policy()` (built, None by default): a rule row adopted by the board, else None, which shows the gap | P1 |
| A person's confirmation of each step | `data/<profile>/units/<unit>/packets/<id>.json` (built: `jason.tasks.unit_records_write`): per step `shows` (what the person says the record shows), `confirmed_by`, `confirmed_at`, and a note | P2 |

The packet reads; it decides nothing. A step's answer is a person's, written down with their name.

## Layout: the unit record

```
+---------------------------------------------------------------------------------+
| Unit 14 Example Lane · Plan A · building 3                  [Open the loss packet]|
+---------------------------------------------------------------------------------+
| Tabs: Overview · Record · Manual · Documents                                     |
| Component         Status          Source            Declaration says  Policy says |
| Kitchen flooring  original        [plan sheet]      points: master    points: master |
| Bath flooring     upgrade         [approval][invoice] points: owner's  points: owner's|
| Water heater      equiv. replace  [invoice]         points: master    ask the agent  |
| Refrigerator      builder option  [closing sheet]   ask a person      ask a person   |
| Ceiling fan       unknown         —                 ask a person      ask a person   |
+---------------------------------------------------------------------------------+
| Differences are questions, not findings. 1 open with the agent.                  |
+---------------------------------------------------------------------------------+
```

## Layout: the loss packet

```
+---------------------------------------------------------------------------------+
| Loss packet · Unit 14 · water damage · Jun 4                  [Export] [Print]   |
| Policy: $10,000 deductible · replacement cost · reading by jason                  |
+---------------------------------------------------------------------------------+
| 1 The item        ● confirmed by A. Smith, Oct 3    [recited provisions] [record]|
| 2 Origin of cause ○ not yet confirmed               [recited provisions] [record]|
| 3 Insured casualty ○                                                           |
| 4 Negligence      ○                                                           |
| 5 The deductible  ◌ no board guideline on file      [Held: gap]                  |
+---------------------------------------------------------------------------------+
| Open: whether unit finishes are covered by the master policy (with the agent).   |
+---------------------------------------------------------------------------------+
```

The packet never states a conclusion about coverage, fault, or who pays. Each step shows the provisions' words, what the record shows, and a person's confirmation.

## Components

`EffectiveRecord`, `CoverageCell`, `OpenQuestion`, `ImprovementForm`, `UnitManual`, and `LossPacket` are proposed, not in jason-ui or [components.md](../components.md#still-proposed): they are specified in [../handoff-unit-records.md](../handoff-unit-records.md). Built, and used here: `SourcedDate`, `Doc`/`DocList`, `Recitation`, `ReadingLabel`, `HeldNote`, `Timeline`, `StageSteps`, `Confirm`, `Command`, `Money`.

## Actions

| Action | Effect | How |
|---|---|---|
| Add an improvement | a new entry in the unit's manual | the owner or the manager for the unit, behind `Confirm`, with `by`; the approval is looked up, never typed |
| Change an entry's visibility | private, shared, or association | the owner's act; sharing says it may become an association record |
| Confirm a step in the packet | records who confirmed what and when | `Confirm`, in the person's name; a second person is not required |
| Export the packet | a file (PDF) | a read; nothing is sent |
| Draft a question to the agent or counsel | a draft in `data/drafts` | a draft only; a person sends it |

jason never marks a component covered or not covered, and never assigns fault.

## States

No plan matched (every default is unknown, stated once at the top, not per row); no specification on file for the plan; no entries; an entry without an approval where one was required (shown to the owner only); an approval with no entry; the declaration and policy differ (an open question, never an error); a claim file exists (its letters held back; the packet says "a claim file exists," not what it says); the deductible guideline missing (held note); an incident with no unit match; the owner's manual shared in part.

## Privacy

Owner names appear only where the console already shows them to that role, masked by default. An entry's contractor and cost are P2 and never appear in a list across units or in the facts screen. A claim's confidential letters are never quoted or summarized. The packet is P2 and is logged when opened for a unit. The owner sees only their own unit.

## Acceptance criteria

1. With the sample unit, the effective record shows each status, its sources, and both coverage columns, and the row where they differ links to its open question.
2. No cell, heading, or export says "covered," "not covered," "at fault," or "your responsibility."
3. Each ladder step recites its provisions whole with their citation, then labels any reading; a step with no provision on file says so.
4. A confirmation records a name and a time; a packet exported before a step is confirmed says the step is unconfirmed.
5. The deductible step shows the board's guideline when one exists, else a held note that the guideline is missing.
6. An entry's cost is `Money` in integer cents, labeled the owner's figure and not certified.
7. A claim file's contents are never shown; only that one exists.
8. Contractor and cost never appear outside the unit's own record.
9. A plan with no specification makes statuses unknown, not original.
