# Handoff: a parcel's title history, its document processes, and how an association is found

For the design pass on components that do not exist yet. They draw what jason already reads from a county recorder's public
index: a parcel's deeds, the closings and loans around them, and, for onboarding, the documents that tie a builder's declaration to
the association it created. The readings are built and tested ([../placer.md](../placer.md), [../instrument-graph.md](../instrument-graph.md),
`jason placer-history --processes` and its Markdown report); the console endpoints below are proposed. The first build will use the
sample data here as test fixtures (made-up names and numbers only), and the real payloads will have the same shapes.

## The idea in four sentences

A county index lists every recorded document with its number, date, type, and parties, and almost never says which document
follows which, so jason **reads** the chain: each deed's prior (the deed that put its seller in title), the bundle recorded with
it (the buyer's loan, the old loan's release, the court's letters), and each loan's life from deed of trust to reconveyance. Joined
by party names, a chain is a **braid**: a seller who sold several units, or a co-owner with other title, matches many deeds, so the
parcel's own **strand** is drawn apart from the side strands. Where a reading expects a document the walk did not find (the trustee's
deed before a bank's resale), that **gap** is where a person looks next, never a conclusion. For an association, the same readings
show which founding documents (declarations, annexations, condominium plans) belong to it, through the documents that name both the
builder and the association, such as the builder's deed of the common area.

## Where it lives in the console

| Surface | Route (proposed) | Audience |
|---|---|---|
| Title history of a unit | a tab on the unit's page in Members and units (`#/members?unit=`), opened from its "Title, liens, and taxes" line | manager, board |
| Any parcel by address | `#/title?parcel=` (the Title watch item, Finance), with `ParcelLookup` at the top | manager, board |
| Founding documents and their association | Onboarding → Recorded instruments, beside `InstrumentGraph` | manager, board, onboarding |
| County survey coverage | Onboarding → Find the association, behind "How the directory was built" | admin |

Title history is P1 (owners' names): the people who work with the owners see it; the default view masks owners by role, and names
are shown only by a named person's logged reveal, as `InstrumentGraph` does (`OwnerNames`). Nothing here is owner-facing yet.

## The components

Existing jason-ui parts are reused where named: `InstrumentGraph`, `OwnerNames`, `TieBadge`, `Day`, `Timeline`, `DataTable`, `Pill`,
`Badge`, `Stat`, `Tabs`, `SearchBox`, `Caveats`, `Confirm`, `Command`, `EmptyState`, `Loading`, `ErrorNotice`. New ones:

| Component | Where it renders | Data | States to design |
| --- | --- | --- | --- |
| `ParcelLookup` | Title watch, top; Onboarding | `ParcelHit[]` from the assessor | a combobox over address or APN (twelve digits) or a document number; searching; one match (the parcel card); several; none ("the assessor has no parcel for…"); the assessor unreachable (a retry, not "none"); chosen |
| `ParcelHeader` | top of a title history | `ParcelProcesses.parcel` and counts | APN, address, property type, the assessor's last document; counts as `Stat` (instruments, deeds, closings, lien lifecycles); read on (date); "Read again" behind `Confirm` (a read job); job queued, running, failed; never read ("Read its history") |
| `TitleStrand` | Title history, first section | `ParcelProcesses.chain` | the parcel's strand as a vertical spine of `DeedCard`s, newest first; side strands folded into a chip between cards ("3 earlier deeds share a name"), which opens them; a gap slot (dashed) where a prior was not found; the developer grant at the root; a chain with one deed; a long chain (40+); the Mermaid view on request |
| `DeedCard` | in `TitleStrand`, `TenureSwimlane` focus | `Deed` | number, date, `ReadingBadge`, from → to as `OwnerRole`s; seats summary ("3 of 3 seats" or "missing: trustee's deed"); companions count; expanded: `ClosingSeats`; a side-strand card (muted, with "shares a name with …"); focused |
| `ReadingBadge` | `DeedCard`, lists, the graph's node detail | a reading word | resale, restatement (the same people re-titling: not a sale), REO resale, excluded transfer, re-recording, companion transfer, foreclosure, and any new word the readings add (an open set); the meaning on hover and focus; never a color alone |
| `OwnerRole` | everywhere a private party appears | `OwnerRef` | masked: "Owner C (2 persons)", a prime for the same people re-titling ("Owner C′"); revealed: the names, with the reveal's who and when nearby; a business, lender, or agency always by name; a party the index left blank ("(none indexed)") |
| `ClosingSeats` | `DeedCard` expanded | `Reading.seats` | a checklist of the closing's seats (grant, prior deed, buyer lien, notice of completion, reconveyance, trustee's deed, letters): present (its number, linked), missing (a `GapCallout`), held by other parties (not this closing's), not expected; complete or not, in words |
| `GapCallout` | a missing seat, a gap slot | `Gap` | what is missing and why the reading expects it ("a bank's resale follows a trustee's deed"), whose name the missing document would carry, the cheapest search that finds it; "Look it up" queues a read job behind `Confirm` in the person's name; writes off: the `Command`; searched and still not found ("not under these names: ask the title company") |
| `TenureSwimlane` | Title history, second section | `ParcelProcesses.chain` + `loans` | one lane per tenure (by `OwnerRole`), a bar from the deed in to the deed out; under each, thin bars for that tenure's loans (open to reconveyance) with markers for a notice of default and a rescission; an REO resale marked; restatements as ticks on the same lane; today; a tenure still open; zoom by decade; phone: a list by tenure |
| `LoanTrack` | Title history, Loans; `LoanList` rows | `Lifecycle` | a horizontal step track: opens → advances (assignment, substitution of trustee, subordination, modification) → escalates (notice of default) → closes (reconveyance) or a trustee's sale; the lender at the opening; status word (open, closed, lapsed); during this tenure or outside it; compact (one row) and expanded (each step with its number and date) |
| `LoanList` | Title history, Loans | `Lifecycle[]` | grouped by tenure; filters: during this tenure, open only, defaulted; a count line ("12 loans: 11 closed, 1 open; 1 defaulted and cured"); empty |
| `LifecycleFlow` | Title history, Loans (summary); a subdivision's page | `Transition[]` | every loan's step-to-step transitions with counts (a flow, not a pie): how many deeds of trust were assigned, defaulted, cured, reconveyed, sold at a trustee's sale; a parcel's owners and a whole subdivision; the counts as a table for screen readers |
| `OtherLiens` | Title history, last section | `Lifecycle[]` (not loans) | tax liens, judgments, mechanics liens, assessment liens: against whom (`OwnerRole`), status, during this tenure or not, the steps; an assessment lien by the association marked as the association's own (its release due, `association_collections`) |
| `FoundingShape` | governing-instrument rows (Onboarding) | a shape word | subdivision (a declarant and a tract), condominium (a plan beside it), commercial (an industrial or business park), regulatory (a public agency's restriction: not an association), between neighbors (private persons only: not an association), declarant only (undecided); each with its meaning |
| `FormationTies` | Recorded instruments, a founding document's detail | `FormationTie[]` | the associations the document may belong to, each with its evidence ranked: the builder's deed of the common area to the association, an annexation or amendment naming both, a shared tract word ("X at Y" points to Y), the same day or adjacent numbers; strong or weak in words (`TieBadge`); several candidates (a builder of many communities); none yet ("declared, no association has recorded yet"); confirm one behind `Confirm` (a person's pin); a lead, not a pin |
| `FilingFootprint` | an association's row in the directory, the picker's detail | `Footprint` | what the association has recorded over its life, by family and year: its liens and releases, its deeds and easements, amendments and annexations, the builder's filings that name it; first and last year; an association with only the builder's documents (new); one with only liens (formation before the index) |
| `SurveyCoverage` | Find the association, "How the directory was built" | `SurveyWindow[]` | a grid of searches (rows) by period (columns): read, split (the window held more than a page, so it was halved), refused (a type the index will not list without a name), failed and retried, not read; the query count against a budget; the last read |

### Data shapes (TypeScript)

```ts
// GET /api/parcel-processes?county=&apn=   (proposed; the server builds it from the saved bundle, masked)
interface ParcelProcesses {
  county: string;                         // "placer"
  parcel: { apn: string; address: string; propertyType?: string; newest: string; read?: string };
  counts: { instruments: number; deeds: number; closings: number; lifecycles: number };
  chain: {
    strand: string[];                     // the parcel's own deeds, newest first (OwnershipHistory.line())
    deeds: Deed[];                        // every deed the walk read, the strand and the side strands
    gaps: Gap[];
    reachedDeveloper: boolean;
  };
  loans: Lifecycle[];
  otherLiens: Lifecycle[];
  transitions: Transition[];              // for LifecycleFlow
  names: boolean;                         // true only on a logged reveal
  reveal?: { at: string; by: string; log: string };
  notes: string[]; caveats: string[];
  job?: { id: string | number; status: "queued" | "running" | "failed" } | null;
}

interface OwnerRef { label: string; persons: number; names?: string[]; kind: "private" | "business" | "agency" | "association" }

interface Deed {
  number: string; recorded: string;       // "2015-0000400", ISO date
  reading: string;                        // ReadingBadge word: "resale", "restatement", "reo resale", ...
  complete: boolean;
  from: OwnerRef[]; to: OwnerRef[];
  prior?: string;                         // the strongest hand-off (ChainStep.prior)
  sharesName: string[];                   // other earlier deeds that only share a name (side links)
  onStrand: boolean;
  seats: Seat[]; companions: string[];    // same-day instruments of its closing
}

interface Seat {
  role: string;                           // "grant", "prior deed", "buyer lien", "trustee's deed", "letters administration", ...
  state: "present" | "missing" | "other parties" | "not expected";
  number?: string; filing?: string;       // when present
  gap?: Gap;                              // when missing
}

interface Gap {
  at: string;                             // the deed whose seat or prior is missing
  missing: string;                        // "trustee's deed", "prior deed"
  why: string;                            // "a lender's resale follows a trustee's deed"
  lookUnder: string[];                    // names the missing document would carry (businesses; owners only by role)
  search?: { name: string; types: string[]; after: string; before: string };   // the read job "Look it up" queues
  searched?: { on: string; found: boolean };
}

interface Lifecycle {
  process: string;                        // "loan", "federal tax lien", "judgment lien", "assessment lien", ...
  status: "open" | "closed" | "lapsed";
  duringTenure: boolean; against: OwnerRef[]; claimant?: string;
  steps: { number: string; recorded: string; word: string; effect: "opens" | "advances" | "escalates" | "closes" | "lapses" }[];
}

interface Transition { from: string; to: string; count: number }   // "deed of trust" → "assignment": 7

// GET /api/formation-ties?county=&number=   (proposed)
interface FormationTie {
  association: { key: string; name: string; standing: "confirmed" | "likely" | "named" };
  strength: "strong" | "weak";
  evidence: { kind: "common-area deed" | "names both" | "tract word" | "same day" | "adjacent number" | "master community";
              number?: string; recorded?: string; words: string }[];
  pinned?: { by: string; at: string };
}

interface Footprint {
  key: string; first: string; last: string;
  byYear: { year: number; family: "assessment lien" | "release" | "property" | "governing" | "builder" | "other"; count: number }[];
}

interface SurveyWindow {
  search: string;                         // "assessment liens", "governing documents", "%OWNERS ASS% × deeds"
  start: string; end: string;
  state: "read" | "split" | "refused" | "failed" | "not read";
  rows?: number;
}
```

Endpoints (proposed, none built): `GET /api/parcel-search?county=&q=` (the assessor), `POST /api/write/parcel-history/read`
with `{county, apn, by}` (a read job on the `county` lane, as the document locator queues one), `GET /api/parcel-processes`
(masked), `POST /api/write/parcel-processes/reveal` with `{by, county, apn}` (names, logged to `data/console/reveals.jsonl`, never a
name in a URL), `GET /api/formation-ties`, `GET /api/association-footprint`, `GET /api/survey-coverage`.

### Sample data (made up)

A half-plex in an example subdivision: the strand runs five deeds back to a bank's resale; before it, the trustee's deed is a gap;
two older deeds share a name with the strand (the twin unit the same couple sold); one loan defaulted and was cured; the estate deed
carries the court's letters.

```ts
const strand = ["2023-0000500", "2020-0000470", "2015-0000400", "2014-0000390", "2009-0000300"];
const deeds: Deed[] = [
  { number: "2009-0000300", recorded: "2009-05-06", reading: "reo resale", complete: false, onStrand: true,
    from: [{ label: "US EXAMPLE BANK NA TR", persons: 0, kind: "business" }], to: [{ label: "Owner D", persons: 2, kind: "private" }],
    sharesName: ["1997-0000120"], companions: ["2009-0000301"],
    seats: [{ role: "grant", state: "present", number: "2009-0000300" },
            { role: "trustee's deed", state: "missing", gap: { at: "2009-0000300", missing: "trustee's deed",
              why: "a lender's resale follows the trustee's deed that gave it title",
              lookUnder: ["US EXAMPLE BANK NA TR", "EXAMPLE TRUSTEE SERVICES CORP"],
              search: { name: "US EXAMPLE BANK NA TR", types: ["TRUSTEES DEED"], after: "2008-01-01", before: "2009-05-06" } } },
            { role: "buyer lien", state: "present", number: "2009-0000301" }] },
  { number: "2014-0000390", recorded: "2014-06-16", reading: "resale", complete: true, onStrand: true, prior: "2009-0000300",
    from: [{ label: "Owner D′", persons: 3, kind: "private" }], to: [{ label: "Owner E", persons: 3, kind: "private" }],
    sharesName: ["1988-0000080"], companions: ["2014-0000389"],
    seats: [{ role: "grant", state: "present", number: "2014-0000390" }, { role: "letters administration", state: "present", number: "2014-0000389" },
            { role: "prior deed", state: "present", number: "2009-0000300" }] },
];
const loan: Lifecycle = { process: "loan", status: "closed", duringTenure: true, against: [{ label: "Owner D", persons: 2, kind: "private" }],
  claimant: "EXAMPLE MORTGAGE CORP",
  steps: [{ number: "2009-0000301", recorded: "2009-05-06", word: "deed of trust", effect: "opens" },
          { number: "2011-0000710", recorded: "2011-03-02", word: "assignment", effect: "advances" },
          { number: "2012-0000900", recorded: "2012-01-10", word: "notice of default", effect: "escalates" },
          { number: "2012-0004410", recorded: "2012-06-01", word: "rescission", effect: "advances" },
          { number: "2015-0000401", recorded: "2015-07-24", word: "reconveyance", effect: "closes" }] };
```

A wireframe of the title history, newest first:

```
 PARCEL 000-000-000-001 · 123 Main St · half-plex          Read Oct 3, 2026   [Read again]
 [ 177 instruments ] [ 22 deeds ] [ 17 closings ] [ 75 lien lifecycles ]       Owners by role [Show owners' names]

 THIS PARCEL'S STRAND
 ┃ 2023-0000500  Mar 27, 2023  [restatement]  Owner F′ (2) → Owner F′            all seats ▸
 ┃ 2020-0000470  Aug 14, 2020  [restatement]  Owner F → Owner F′ (2)             reconveyance, deed of trust ▸
 ┃ 2015-0000400  Jul 24, 2015  [resale]       Owner E (3) → Owner F              buyer lien, reconveyance ▸
 ┃ 2014-0000390  Jun 16, 2014  [resale]       Owner D′ (3) → Owner E (3)          letters of administration ▸
 ┆   ⋯ 2 earlier deeds share a name (the twin unit, a co-owner's other title)  [Show]
 ┃ 2009-0000300  May 6, 2009   [REO resale]   US EXAMPLE BANK NA TR → Owner D (2)  missing: trustee's deed ▸
 ╎ ┌ Not found: the trustee's deed before this resale. A lender's resale follows the deed that gave it title. ┐
 ╎ │ It names the foreclosing trustee and the lender, not the owners. [Look it up]  (a read job, as you)      │
 ╎ └──────────────────────────────────────────────────────────────────────────────────────────────────────────┘
 WHO HELD TITLE, WHEN      1990 ─────── 2000 ─────── 2010 ─────── 2020 ──
   Owner D (2)                        ███████████▲(default, cured)
   Owner E (3)                                         ██
   Owner F / F′                                          ████████████▶
```

## What the design must keep

- **A reading is a lead, not a pin.** Every join (a prior, a seat, a tie) is jason's reading of numbers, dates, types, and names. Say
  "read as", "shares a name", "not found under these names"; never "is the prior", "belongs to", or "missing from the record".
- **The strand, then the braid.** The parcel's own strand is the default; side strands are one click away and say why they are there
  ("shares a name"), so a person can see the evidence the walk weighed. Never draw the braid as one line.
- **A gap invites a search.** A missing seat names what would fill it, whose name it would carry, and the search that would find it.
  It never says a foreclosure, a transfer, or a payoff did not happen.
- **Neutral process words about people.** "A lender sold it after a trustee's sale", "the loan was reconveyed", "a notice of default
  was recorded and rescinded": the document's own words, never "lost the house" or "defaulted on". A restatement is not a sale.
- **Owners by role by default.** A screenshot or an export holds no owner's name unless a named person asked; the reveal is logged
  and says who and when. Businesses, lenders, trustees, and agencies are always named.
- **Nothing reaches the county from the page.** "Read again" and "Look it up" queue read jobs a named person asks for, behind
  `Confirm`; the page reads the job's result. With writes off, the `Command` instead.
- **No money is implied.** Placer's index carries no price and Sacramento's transfer tax only sometimes; no figure appears unless a
  document states it, and then as `Money` in cents with its source.
- **A founding document's association is a person's pin.** `FormationTies` ranks evidence and a person confirms one; until then it
  is a lead. A regulatory restriction or one between neighbors says it is not an association's, in words.
- **WCAG 2.2 AA** as in [components.md](components.md#accessibility): the strand is an ordered list with the deed number first; the
  swimlane has a table alternative (tenure, from, to, loans) and the flow a counts table; reading and status words never rely on
  color; every interactive step of a `LoanTrack` is reachable by keyboard; the print layout keeps the strand, the gaps, and the
  caveats on paper.

## Decisions for the design

1. **The braid.** A spine of cards with side strands folded into chips (as sketched), or the full DAG with the strand emphasized?
   The DAG is `InstrumentGraph`'s job; this view should read top to bottom in a minute.
2. **Tenures on a phone.** The swimlane does not fit at 360px: a list by tenure with each loan as a `LoanTrack` row, or a horizontal
   scroll with the lanes pinned?
3. **How many loans.** A parcel's owners can carry 50 lifecycles across their other property. Default to this tenure's loans and
   fold the rest, or show all with a filter?
4. **A gap's search.** Inline in the card (as sketched), or a drawer with the search's terms editable before it is queued?
5. **Formation ties.** A ranked list with evidence chips, or a small graph (declaration, deed, association) per candidate? Several
   candidates must stay readable when a builder built many communities.
6. **The footprint.** Small multiples by family across years, or one dot timeline colored by family with the words beside it?
7. **Survey coverage.** An admin's view only; does it belong in Onboarding or under a settings or data area?
8. **Export.** The Markdown report with Mermaid (`jason placer-history --processes`) exists; should the screen offer it, a PDF, or both?

## Not part of this pass

Owner-facing title views; the subdivision page (a builder's lots, `jason.tasks.placer_history.placer_subdivision_report`), which
will reuse `TitleStrand` and `LifecycleFlow` per lot; the endpoints themselves; the rolling-window survey (asspy), whose coverage the
`SurveyCoverage` grid shows once it is built.
