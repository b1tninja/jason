# Handoff: the paint palette, community facts, the unit manual, and the loss packet

For the design pass on a set of components that do not exist yet. The behavior, the words, and the data are settled in
[../paint-ui-design.md](../paint-ui-design.md), [../paint-design.md](../paint-design.md), and
[../unit-records-design.md](../unit-records-design.md); this page is what the design needs to draw them: the components, their
states, sample data, what the design must keep, and the decisions it is asked to make. Nothing here is built. The first build will
use the sample data below as test fixtures (made-up names and colors only), and the real payloads will have the same shapes.

## The idea in four sentences

An association keeps a **palette** (which color goes on which surface) and a set of **community facts** (what was originally
installed, who maintains what, and the answers owners keep asking), and treats those facts as **assumed defaults**. An owner can keep
a **unit manual** that overrides the defaults with what they actually changed, with receipts, approvals, and photos. When a loss
happens, the unit's **effective record** tells a person in minutes which layer of insurance an item sits in, and the **loss packet**
puts the governing words, the policy, and the history in front of the person who decides. jason informs and never decides coverage,
fault, or approval.

## Where it lives in the console

| Surface | Route (proposed) | Audience today | Audience later |
|---|---|---|---|
| Paint | `#/paint` (a tab under Records) | manager, board | owners (read-only palette and interior register) |
| Community facts | `#/facts` (Records) | manager, board | every owner (the FAQ view) |
| Unit record | a tab on the unit's page in Members and units | manager, board | the owner, signed in as that unit |
| Loss packet | opened from a unit or an incident | manager, board | the owner, for their own unit |

The console is loopback and manager-only today ([security-and-privacy.md](security-and-privacy.md)). Design each component so it
also works **without `ConsoleShell`**, in a plain owner-facing page at phone width, since owners will use it on their phones and the
platform may host several communities later.

## The components

Existing jason-ui parts are reused where named (`Doc`/`DocList`, `Recitation`, `ReadingLabel`, `Pill`, `Badge`, `Timeline`,
`DataTable`, `Findings`, `Caveats`, `HeldNote`, `Confirm`, `Command`, `Money`, `DueDate`, `Stat`, `SearchBox`, `Tabs`, `Checklist`,
`StageSteps`, `EmptyState`). New ones:

| Component | Where it renders | Data | States to design |
| --- | --- | --- | --- |
| `Swatch` | everywhere a color appears | `PaintColor` | catalog color (fill, code, name); renamed (shows the printed name beside the current one); discontinued; not in catalog or entered by hand (flagged "entered, not checked"); unknown; sizes: chip 24px, tile 96px, card 120 by 84 |
| `PaletteMatrix` | Paint, top | `PaintSchedule` | surfaces down the left as the schedule prints them, schemes across; the scheme toggle; a row with no paint (a roof tile); drift flags; no schedule on file; catalog unavailable (the copy's age); print layout; phone layout |
| `ColorDetail` | a drawer from any `Swatch` | `PaintColorDetail` | description, light reflectance, family, "used on", three coordinating and six similar colors as chips; for a discontinued color, its closest current colors; the touch-up caveat |
| `SourcedDate` | Paint dates, unit record, packet | `SourcedDate` | recorded (a source document), implied (shows its arithmetic), reported (by an owner, with a count), needs input (an invitation to enter it) |
| `FactList` and `FactCard` | Community facts | `Fact` | grouped by topic with search; documented, reported (n confirmations), assumed; its scope (community, plan, building, phase); its sources as `Doc` chips; the questions it answers; a rule's words in `Recitation` then a `ReadingLabel`; open question attached |
| `FactStatus` | on a `FactCard`, `EffectiveRecord` | a status word | documented, reported, assumed, with the meaning on focus and hover; never a color alone |
| `EffectiveRecord` | Unit record | `EffectiveComponent[]` | a table of the unit's components with status, source, and both coverage columns; a row opens its history of entries; no plan matched to the unit; all unknown |
| `CoverageCell` | inside `EffectiveRecord`, the packet | `CoverageReading` | "points to the master policy", "points to the owner's policy", "differs: the declaration says X and the policy says Y", "ask a person"; it never says covered or not covered |
| `OpenQuestion` | `CoverageCell`, the packet, a fact | `OpenQuestionRef` | with the agent, with counsel, with the board; asked, answered, closed; the answer's source |
| `ImprovementForm` | Unit manual, "Add an improvement" | `ImprovementEntry` | blank; saving; saved; approval found and attached; approval not found (a gap shown to the owner only); upload failed; validation; draft kept |
| `UnitManual` | Unit record | `UnitManualView` | the entries as a timeline plus the unit's documents; visibility chip (private to the owner, shared with the association, made by the association); empty (an invitation); export |
| `LossPacket` | opened from a unit or incident | `LossPacket` | a five-step ladder (item, origin of cause, insured casualty, negligence, deductible) each with the words recited, what the record says, and a person's confirmation; a step with no guideline on file; an open question pending; export |
| `InteriorColorRegister` | Paint, below the palette | `InteriorReport[]` | none reported; one report; confirmed by n; two reports that disagree shown side by side; "this matches my unit" (owner) |
| `DocRepository` | Community facts, Unit manual | `DocRef[]` | grouped by kind and scope; stale; upload behind `Confirm`; empty |

### Data shapes (TypeScript)

```ts
interface PaintColor {
  code: string;                 // "SW 7008", or another maker's code
  maker: "sherwin-williams" | "other";
  name: string;                 // the current name
  printedName?: string;         // as the schedule printed it, when it differs
  hex: string;                  // catalog color, "#EDEAE0"; never sampled from a scan
  lrv?: number;                 // light reflectance value
  status: "ok" | "renamed" | "discontinued" | "not found" | "not checked";
  entered?: boolean;            // hex typed by a person, not looked up
}

interface PaintSchedule {
  title: string; source: Doc; prepared: string;        // "Prepared for the developer, 2017-11-17"
  schemes: number[];
  rows: { label: string; surface: string; note?: string;
          colors: Record<number, PaintColor> }[];       // label as printed: "ENTRY DOORS"
  catalogFetched: string; unavailable?: boolean;
}

interface SourcedDate {
  date?: string;                                        // ISO date or year
  source: "recorded" | "implied" | "reported" | "needs input";
  docs?: DocRef[]; arithmetic?: string;                 // "due 2027 minus a 7-year life"
}

interface Fact {
  id: string; statement: string; topics: string[];
  scope: { kind: "community" | "plan" | "building" | "phase"; name?: string };
  status: "documented" | "reported" | "assumed"; confirmations?: number;
  sources: DocRef[]; asOf?: string; answers: string[];
  recitation?: Recitation; reading?: ReadingLabelProps; open?: OpenQuestionRef;
}

interface EffectiveComponent {
  component: string;                                    // "Kitchen flooring"
  value: string;                                        // "Vinyl plank, model X (per the plan's finish schedule)"
  status: "original" | "equivalent replacement" | "upgrade" | "builder option" | "personal property" | "unknown";
  sources: DocRef[]; verified?: SourcedDate;
  declaration: CoverageReading; policy: CoverageReading;
  history: ImprovementEntry[];
}

interface CoverageReading {
  points: "master policy" | "owner's policy" | "ask a person" | "not stated";
  words: Recitation;                                    // the operative words, whole, with citation
  differs?: OpenQuestionRef;                            // set when the declaration and the policy disagree
}

interface ImprovementEntry {
  id: string; what: string; where: string; replaces?: string;   // an EffectiveComponent.component
  date: string; contractor?: { name: string; licence?: string };
  permit?: string; approval?: DocRef;                    // the association's own record, attached
  costCents?: number; paidByOwner: true;                 // "owner's figure; not certified"
  product?: string; model?: string; serial?: string; warranty?: DocRef;
  photos: DocRef[]; docs: DocRef[]; visibility: "private" | "shared" | "association";
}

interface LossPacket {
  unit: string; plan?: string; incident?: { id: string; day: string; cause: string };
  steps: { n: 1|2|3|4|5; question: string; recited: Recitation[]; record: string;
           confirmedBy?: string; confirmedAt?: string; held?: string; open?: OpenQuestionRef }[];
  policy: { deductibleCents: number; valuation: string; reading: ReadingLabelProps };
  effective: EffectiveComponent[]; priorIncidents: number;
}
```

### Sample data (made up)

- A palette of five rows (FASCIA, TRIM, FIELD, ENTRY DOORS, GARAGE DOORS) and a roof-tile row, three schemes, one renamed color, one
  discontinued color, one color from another maker.
- Plan A, unit 14 Example Lane: kitchen flooring (original, vinyl plank), bath flooring (upgrade to tile, with an approval and a
  permit, owner's figure $4,180), water heater (equivalent replacement), refrigerator (builder option), a rug (personal property),
  and a ceiling fan with no record (unknown). One row where the declaration and the policy differ (finished flooring).
- Three facts, one each documented, reported (3 confirmations), and assumed; an interior paint color reported two ways for one plan.

## What the design must keep

- **A lead is not a pin, and a triage is not a decision.** No word on a coverage cell, a status, or the packet says "covered," "not
  covered," "your responsibility," or "at fault." They say where the record **points** and what is **asked**. The carrier decides
  coverage, and the board and counsel decide responsibility.
- **Recite, then label.** A rule or a policy term is shown in its own words with its citation (`Recitation`), then any reading is
  labeled with whose it is (`ReadingLabel`). Where the declaration and the policy differ, both are shown, side by side, and the
  difference is an open question with an owner.
- **The word for each status is the status.** Color and icon never carry it alone; swatches always carry their code and name in text.
- **Color is the catalog's, not a photo's.** A swatch fill is the maker's catalog color. Show the caption that screens and printers
  shift color and that the number governs. Never fill a swatch from a scan or a photo.
- **Owner-reported is never the association's record.** Anything owners supplied (an interior color, an unconfirmed fact) is labeled
  as owner-reported with the number who confirmed it, and shown apart from documented facts.
- **The owner's manual is the owner's.** Show who can see each entry, and tell the owner when sharing an entry with the association
  may make it an association record. Contractor names and costs never appear in a list across units.
- **A cost is the owner's figure.** `Money` in integer cents, labeled as paid by the owner and not certified or appraised.
- **Nothing is sent.** Exports are files. A question to an agent or counsel is a draft a person sends. Writes go through `Confirm`
  in a named person's name.
- **Words on screen** follow [content/style.md](content/style.md): sentence case, verbs first, no "successfully," no "please," an
  empty state that invites ("Start your unit's manual").
- **WCAG 2.2 AA** as in [components.md](components.md#accessibility): the matrix is a real table with row and column headers; the
  scheme toggle is a radio group; ink on a swatch meets contrast at every color (choose black or white by luminance, and check mid
  tones); every status has a text name; focus order follows the ladder; the stepper announces each step's confirmation; a packet and
  a matrix have print layouts; motion respects the reduced-motion setting; touch targets are at least 24 CSS pixels and a photo upload works
  from a phone camera.

## Decisions for the design

1. **Where the screens live.** The routes above are a proposal. Is Paint a tab under Records, or its own item? Does Community facts
   belong beside the governing documents, since many facts recite them?
2. **Owner-facing chrome.** Design the standalone page (no `ConsoleShell`): brand, header, language, and a phone-first layout, since
   the same components appear for owners and may serve several communities with their own names and colors.
3. **The matrix on a phone.** A table of swatches does not fit at 360px. Choose between a card per surface with a scheme chooser, a
   horizontal scroll with a pinned label column, or one scheme at a time.
4. **How to show "differs."** The declaration and the policy sometimes disagree. Design the cell so it neither alarms an owner nor
   suggests coverage, and so it leads to the open question and its owner.
5. **Dates with a source.** One glyph set or words only for recorded, implied, reported, and needs input; where the arithmetic for an
   implied date appears.
6. **Adding an improvement from a phone.** Photo first, then the form? How the approval is found and attached, and how the owner sees
   the gap when none is found.
7. **The loss packet as paper.** A one-to-three page print layout a person can hand to an adjuster or a board, with the recited words
   whole.
8. **The photo-first scheme pick (optional, later).** A unit's photo beside the three candidate swatches for a surface, a person
   choosing, with "scheduled" and "observed" kept apart. Not required for the first pass.
9. **Empty and unknown.** Most units start with no entries and many facts start as assumptions. Design these as the common case, not
   an error.

## Not part of this pass

- The backend. The loaders and endpoints (`GET /api/paint`, `/api/facts`, `/api/unit-record?unit=`, `/api/loss-packet?unit=&incident=`
  and the writes behind `Confirm`) are proposed, not built; the first build uses the sample data above.
- The register Sheet for community facts and the per-unit folders ([../registers.md](../registers.md)).
- Entering which building or unit wears which scheme.
- Any statement of what a policy covers beyond what is recited from it, and the questions open with the carrier's agent and counsel.
