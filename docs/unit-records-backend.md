# Paint, community facts, and unit records: the backend

Status: proposal, ready to build when the design returns. The screens are specified in
[console/screens/paint.md](console/screens/paint.md), [console/screens/community-facts.md](console/screens/community-facts.md), and
[console/screens/unit-record.md](console/screens/unit-record.md); the components in
[console/handoff-unit-records.md](console/handoff-unit-records.md); the ideas in [paint-design.md](paint-design.md),
[paint-ui-design.md](paint-ui-design.md), and [unit-records-design.md](unit-records-design.md). This page is how the backend is built
so that the screens have loaders, writes, tests, and tools behind them, within AGENTS.md's rules.

## The rules this build keeps

- **No association in code.** Everything about one association (its plans' specifications, the provisions that draw its insurance
  line, its open questions, its deductible guideline) is a `Community` method with an empty default, implemented by the profile.
- **A fact is data.** A fact never restates a provision's words; it stores the expression and the loader recites it with `cite_document`.
- **A reading is a lead.** Statuses are words; the triage points and asks, and never says covered, not covered, or at fault.
- **Reads touch disk only.** No loader calls the maker's catalog, Google, PayHOA, or Keeper on load.
- **Writes are a person's.** Each write names `by`, runs under the store's lock, and is a `Confirm` in the UI and a `--yes` in the CLI.
- **Nothing is sent.** Exports are files; a question to an agent or counsel is a draft.

## The records (new modules in `src/jason/community/`)

**`facts.py`**

```python
class FactStatus(Enum): DOCUMENTED; REPORTED; ASSUMED
class ScopeKind(Enum): COMMUNITY; PLAN; BUILDING; PHASE

@dataclass(frozen=True)
class FactScope: kind: ScopeKind; name: str = ""
@dataclass(frozen=True)
class Fact:
    key: str; statement: str; topics: tuple[str, ...]; scope: FactScope
    status: FactStatus; sources: tuple[str, ...]      # evidence addresses (docref)
    provisions: tuple[str, ...] = ()                  # cite_document expressions
    answers: tuple[str, ...] = ()                     # the questions it settles
    as_of: str = ""; confirmations: int = 0
```

`Community.facts() -> tuple[Fact, ...]` (empty default). A facts register (`registers.py`, board columns: status, sources, notes) is
merged over the specification's rows by key; jason's columns are never written by the board.

**`unit_record.py`**

```python
class ComponentKind(Enum): FLOORING; CABINETS; BUILT_IN_APPLIANCE; APPLIANCE; PLUMBING_FIXTURE; ELECTRICAL_FIXTURE;
                           HVAC; WATER_HEATER; WALL_FINISH; CEILING_FINISH; DOORS; WINDOWS; OTHER
class ComponentStatus(Enum): ORIGINAL; EQUIVALENT_REPLACEMENT; UPGRADE; BUILDER_OPTION; PERSONAL_PROPERTY; UNKNOWN

@dataclass(frozen=True)
class OriginalSpec: plan: str; component: str; kind: ComponentKind; value: str; source: str   # an evidence address
@dataclass(frozen=True)
class ImprovementEntry: id: str; unit: str; component: str; kind: ComponentKind; what: str; where: str
    replaces: str = ""; date: str = ""; contractor: str = ""; licence: str = ""; permit: str = ""
    approval: str = ""; cost_cents: int | None = None; product: str = ""; model: str = ""; serial: str = ""
    warranty: str = ""; photos: tuple[str, ...] = (); docs: tuple[str, ...] = ()
    status: ComponentStatus = ComponentStatus.UPGRADE; visibility: str = "private"; by: str = ""; at: str = ""
@dataclass(frozen=True)
class EffectiveComponent: component: str; kind: ComponentKind; value: str; status: ComponentStatus
    sources: tuple[str, ...]; entries: tuple[ImprovementEntry, ...]; verified: str = ""
```

Pure functions, no I/O, no profile:

- `effective(plan, specs, entries) -> tuple[EffectiveComponent, ...]`: for each component of the plan's specification, the newest
  entry that replaces it, else the specification row (status ORIGINAL). Entries with no matching component are added as
  UPGRADE or as their own status. A plan with no specification yields no ORIGINAL row: every component is UNKNOWN, never original.
- `coverage(kind, status, unit_coverage) -> (declaration_reading, policy_reading)`: the mapping table below.

| Status | Declaration column | Policy column |
|---|---|---|
| ORIGINAL, EQUIVALENT_REPLACEMENT | points to the master policy if the kind is in the declaration's list, else "not stated" | the same against the policy's list |
| UPGRADE | points to the owner's policy | points to the owner's policy |
| PERSONAL_PROPERTY | points to the owner's policy | points to the owner's policy |
| BUILDER_OPTION | ask a person | ask a person (the open question on whether an option counts as original) |
| UNKNOWN | ask a person | ask a person |

When the two columns differ for a kind, `differs` carries the open question's key. A column is never "covered" or "not covered."

**`Community` additions** (each with an empty default, then implemented by a profile):

| Method | Returns | Empty default |
|---|---|---|
| `facts()` | `tuple[Fact, ...]` | `()` |
| `original_specs()` | `tuple[OriginalSpec, ...]` | `()` |
| `unit_coverage()` | `UnitCoverage(declaration_kinds, policy_kinds, declaration_cite, policy_cite)` | `None` |
| `loss_ladder()` | `tuple[LadderStep, ...]` (step 1 to 5, its question, its citations) | `()` |
| `open_questions()` | `tuple[OpenQuestion, ...]` (key, title, with whom, status, asked, answered, source) | `()` |
| `deductible_policy()` | the board's adopted guideline as a rule row, or `None` | `None` |
| `interior_reports()` | owner-reported interior colors by plan (merged from the register) | `()` |

A profile that returns the empty defaults gets screens that say so and no crash.

**`loss_packet.py`**: `assemble(unit, incident, record, ladder, policy, history, guideline) -> LossPacket`. Each step carries its
recited provisions (from `cite_document`, never retyped), what the record shows, `confirmed_by`, `confirmed_at`, and a `held` note
when the step's provisions or guideline are missing. A pure function over inputs the loader gathers.

## Storage

| What | Where | Lock | Level |
|---|---|---|---|
| Facts | `Community.facts()` plus the facts register (a Sheet) | the register's sync | P0 |
| Original specifications | the profile (`Community.original_specs()`) | none | P0 |
| A unit's entries | `<data root>/<profile>/units/<unit>/entries.json` | the store lock (`jason.locks`) | P2 |
| A unit's documents | the unit's Drive folder, referenced by `drive:` address, never copied | n/a | the file's own |
| Packet confirmations | `<data root>/<profile>/units/<unit>/packets/<id>.json` | the store lock | P2 |
| Interior reports | the interior register, one row per report, the reporter's unit as a private column | the register's sync | P1, the reporter hidden |

`access.PATH_RULES` gets a row placing `units/` at P2 so an unplaced file fails closed. Entries carry their own `visibility`
(private, shared, association): a loader for anyone but the unit's owner returns only `shared` and `association` entries.

## Loaders and endpoints (`jason.web.extra`, lazy imports)

| Endpoint | Loader | Tools it wraps |
|---|---|---|
| `GET /api/paint` | `paint_view` | `paint_schedules()`, the catalog copy, `paint.check`, `related`, `reserve_study`, `incident_history`, `unit_characteristics` |
| `GET /api/paint/color?code=` | `paint_color` | `SherwinWilliams.related`, optional description |
| `POST /api/write/paint/refresh` | job | `jason paint --refresh`, a person's act |
| `POST /api/write/paint/doc` | job | `jason paint --to-doc --yes` |
| `GET /api/facts?topic=&q=&scope=&status=` | `facts_view` | `Community.facts`, `cite_document`, `thread_topics`, `Community.open_questions` |
| `POST /api/write/facts/<key>` | `facts_write` | the facts register's board columns only |
| `GET /api/unit-record?unit=` | `unit_record_view` | `unit_characteristics`, `original_specs`, `effective`, `unit_coverage`, entries, `open_questions` |
| `POST /api/write/unit-record/entry` | `entry_write` | the unit's entries store, with `by` |
| `POST /api/write/unit-record/visibility` | `entry_visibility` | the same store |
| `GET /api/loss-packet?unit=&incident=` | `loss_packet_view` | `assemble` with `loss_ladder`, `cite_document`, `insurance_policies`, `incident_history`, `deductible_policy` |
| `POST /api/write/loss-packet/confirm` | `packet_confirm` | the packet store, with `by`, `step`, `note` |
| `GET /api/loss-packet/export?unit=&incident=` | `packet_export` | a PDF built from the same payload, a read |

A unit's URL carries its PayHOA unit id only; a search by owner or address is a POST. A payload carries `DocRef`s, never a path
or contents. A loader returns `{found: false, note}` when a store is missing.

## Tools and commands

- MCP (read-only, with their caveats repeated): `paint_colors`, `paint_check`, `paint_match`, `community_facts`, `unit_record`,
  `loss_packet`, in the `governance` profile (the packet in `board`). Each carries: "A reading is evidence, not a pin; the carrier
  decides coverage and the board and counsel decide responsibility."
- CLI: `jason paint` (built), `jason facts` (list, `--topic`, `--coverage`), `jason unit-record --unit ID` (`--add` and
  `--visibility` need `--yes` and `--by`), `jason loss-packet --unit ID [--incident ID] [--pdf]`.
- Lessons and procedure: a procedure `loss-packet` for `jason sop`, and lessons for the cases the packet surfaces (a plan with no
  specification; a policy narrower than the declaration).

## Tests and fixtures

- `tests/fixtures/spec` gets made-up facts, specifications for two plans, a coverage record in which one kind differs, a ladder, and
  an open question. No profile name appears in a general test.
- Pure tests: `effective` (default, replacement, upgrade, builder option, unknown, no specification, newest entry wins),
  `coverage` (every status against both lists, and the differ case), `assemble` (a missing provision becomes a held note, an
  unconfirmed step is stated), and the wording guard: no payload string contains "covered," "not covered," "at fault," or
  "your responsibility" outside a `Recitation`.
- Loader tests: a missing store gives `found: false`; a unit that is not the owner's gets only shared entries; contractor and cost are
  absent from every cross-unit payload; no loader makes a network call (a socket guard in the test).
- Boundary: `tests/test_profile.py` keeps passing, and the new general docs name no profile fact.
- UI: each component gets a `*.test.tsx` beside it in `ui/src/components/`, following the existing fixtures, with the accessibility
  checks the console's other components carry.

## Build order and acceptance

1. **Paint over what exists** (`/api/paint`, `PaletteMatrix`, `Swatch`, `ColorDetail`, `SourcedDate`): needs only the built records and
   the catalog copy. Accepts when the paint screen's criteria pass against the sample palette.
2. **Facts** (`facts.py`, the register, `/api/facts`, `FactList`): accepts when a fact with a provision recites it and the coverage
   counts agree with the register.
3. **The effective record and coverage columns** (`unit_record.py`, `unit_coverage`, `/api/unit-record`, `EffectiveRecord`,
   `CoverageCell`): accepts when the mapping table's cases and the wording guard pass.
4. **The unit manual** (entries store, `ImprovementForm`, `UnitManual`, visibility): accepts when private entries never leave the unit.
5. **The loss packet** (`loss_packet.py`, `/api/loss-packet`, `LossPacket`, export): accepts when every step recites its provisions and
   an unconfirmed packet says so.
6. **Owner-facing** surfaces, after the console has owner sign-in: the same loaders with the owner's level.

## When the design agent hands off

1. Sync the design project into `ui/` (the console's existing design sync), keeping `ui/src/components/index.ts` exporting each new
   component with its types.
2. Reconcile each design component with the data shape in the handoff page; where the design needs a field the shape lacks, change
   the shape and the screen spec together.
3. Run the component tests against the sample data, then wire each to its loader; a screen ships only when its acceptance criteria pass.
4. Record the decisions the design made (the handoff's nine) in [web-ui-decisions.md](web-ui-decisions.md) and close the matching
   items on the handoff page.
