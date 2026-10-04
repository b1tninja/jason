# The instrument graph

The recorded instruments of a community, the parties on them, and the parcels they touch, as one graph of typed edges. The declaration and what amends, annexes, and supersedes it; the land chain and the common-area deeds; each unit's chain of title with the notice of completion, the buyer's lien, and the reconveyances recorded at each closing; and the lien lifecycles that opened while an owner held it. Every edge says which rule made it and from which store, and whether it is firm or a lead.

Code: `jason.community.instrument_graph` (the model and the builders; county-neutral and pure), `jason.tasks.instrument_graph` (reading Sacramento's stores), `jason.web.extra.key_documents:instrument_graph` (the console's source), `jason.commands.instrument_graph` (the CLI). The console component is `InstrumentGraph`.

## Nodes

| Type | Id | What it carries |
|---|---|---|
| instrument | `inst:<county>:<number>` | number, recorded, county, filing, kind (asspy's: fee, lien, release, foreclosure, ...), role (declaration, annexation, amendment, condominium plan, common area deed, ...), phase, delivery, status and `supersededBy`, `loaded` (false for a number only seen cited), the checklist `item` and `tie` for a locator find, and `parties`: business and association names only |
| party | `party:association`, `party:<name>`, or `person:<hash>` | `partyKind`: association, business, or private |
| parcel | `parcel:<apn digits>` | apn, unit, building, phase |

A party is the association when its name starts with one of the association's index spellings, a business when it carries a company, lender, or public-body word (or is a pinned developer), and otherwise a private person. A family trust is private. When unclear, private.

## Edges

Each edge runs from the later or dependent node to the one it acts on. Each kind belongs to a family, and **each family is kept a DAG**: an edge that would close a cycle in its family is not added; it is reported in `cycles` with the path it would have closed (a buy-back, two instruments citing each other, a misread number).

| Kind | Source → target | Family | Made by |
|---|---|---|---|
| `prior_of` | a chain step → its earlier deed | chain | the stored chain (`chain.cites` when the deed cites it, `chain.prior` otherwise), a process seat |
| `re_records` | a re-recording → the first recording | chain | a process seat, `beside_step` |
| `cites` | an instrument → one it cross-references | citation | the index's cross-references, a reading's plain reference |
| `completes` | a notice of completion → the developer's grant | closing | the developer-closing reading |
| `beside` | a same-day instrument → the deed it was recorded with | closing | a process seat (buyer lien, companion), a locator tie |
| `amends` | an amendment → the declaration | governing | the specification's amendment (firm), the index's citation (firm), the role (lead), a reading (lead) |
| `annexes` | an annexation → the declaration | governing | the same |
| `supersedes` | the later instrument → the one it rescinded | governing | the specification's `Supersession` (firm), a reading's "rescinds and supersedes" (lead) |
| `covers` | the annexation in force for a phase → a parcel of that phase | governing | the phase the public report gives the parcel's building (lead) |
| `releases` | a reconveyance or release → the lien | loan | a cross-reference, a blanket-release reading, a lifecycle's closing step |
| `forecloses` | a trustee's deed → the deed of trust | loan | a cross-reference, the foreclosure reading |
| `advances` | a later lifecycle step → its opener | loan | the lien lifecycle |
| `encumbers` | a deed of trust or lien → the parcel | parcel | the buyer-lien seat, a lifecycle joined by the owner's name (lead: a lien indexes a person) |
| `carries` | a deed → the parcel it conveys | parcel | the chain |
| `conveys` | grantor → grantee, `via` the deed | party | the chain, the index row |
| `vests` | a deed → its grantee | party | the chain, the index row |
| `names` | an instrument → a party it names (a private person only in the private view) | party | the index, the governing record, the lifecycle's claimant, the locator (`locator.party`; `locator.person` for a private person, with its index side) |

**Provenance.** Each edge carries `provenance: {rule, store, lead, note}`, and `also` for each further rule that made the same edge. An edge is a lead only when every rule behind it is: the role's guess that an amendment amends the declaration in force becomes firm once the specification pins it.

## Privacy

Owners' names are P1 ([console/security-and-privacy.md](console/security-and-privacy.md)): shown to the people who work with them, kept in jason's private stores and caches (`data/`, `$ASSPY_HOME`), and never written to anything committed (source, docs, tests, and fixtures use made-up names). Masking is the default, and every mask can be lifted by a person:

- The **shared view** (the default) holds no private person: their nodes, every edge touching one, and every cycle through one are left out, and a note counts them. Instrument nodes never carry a person's name in any view.
- The **private view** adds private persons labeled by their role and parcel ("owner, unit 12", "grantor, parcel ...", "named party"); their names are masked.
- **Names** ride in `names` in the private view only when a person asks: `--private --names` on the command line, or **Show owners' names** in the console (`names=1&by=NAME`). The console's reveal needs a person's name (never "jason"; while someone is signed in, theirs) and appends a record to `data/console/reveals.jsonl`: when, who, the scope, the parcel, unit, or instrument it was around, and how many persons were named (never the names). **Hide names** returns to the masked view. The Mermaid diagram stays labeled by role.

## Feeding it from another county

The builders take plain inputs; a county's walk calls them with its own `Context(county, association spellings, developers)`:

| Builder | Takes |
|---|---|
| `add_filed` | asspy `FiledInstrument` rows (number, recorded, kind, grantors, grantees, cross_references, filing_code, filing_name); with `apn`, deeds carry and liens encumber the parcel |
| `add_ownership_history` | an `OwnershipHistory` of `ChainStep`s (from `succession` or a county walk) |
| `add_reading` / `add_seats` | a process `Reading` around a chain deed (its filled slots), or `Seat` rows |
| `add_process_steps` | Placer's `ProcessStep` rows (number, recorded, kind, filing_name, grantors, grantees, process, companions, reading) |
| `add_encumbrance` | an asspy `Encumbrance` lifecycle |
| `add_governing` | `GoverningRecord` rows (from `locate_governing` or `recorded_association`) |
| `add_supersessions`, `add_governing_document` | the specification's facts |
| `add_readings` | `DocumentReading` rows from `read_folder` |
| `add_located`, `add_location` | the document locator's `Located` rows, its saved JSON rows, or a `Location` |

For Placer, a parcel's graph is `add_ownership_history(graph, walk.history, ctx)` then `add_process_steps(graph, walk.processes, ctx, apn=...)`, and the association's is `add_location` with the locator's result and `add_governing` once Placer's governing filings are classified. A county whose index lists no citations (Placer) gets its `prior_of` edges from the chain's party handoffs (`chain.prior`), not from cross-references. Two counties' graphs merge (`merge`), each edge checked again.

## Exports

- `to_dict(view)`: nodes, edges with provenance, cycles, counts, the kinds and their meanings, notes, and caveats.
- `mermaid(view, kinds=..., direction=...)`: a flowchart in the property-history pages' manner: instruments as `d<number>` boxes with the number, the date, and the role; parties as rounded boxes; parcels as hexagons; a firm edge solid, a lead dotted; a superseded instrument dashed and faded; a number only seen cited dotted.
- `neighborhood(node, depth)`: the part within `depth` edges of one node.

## Commands

```bash
jason instrument-graph                                   # the association: Mermaid, shared view
jason instrument-graph --kinds amends,annexes,supersedes # the declaration's family only
jason instrument-graph --parcel 201-1170-022-0013 --json # one parcel's chain, closings, liens
jason instrument-graph --unit 12 --private               # every parcel unit 12 names, owners by role
jason instrument-graph --around 200709200938 --depth 1   # what touches the declaration
jason instrument-graph --all --markdown --out data/reports/instrument-graph.md
```

`GET /api/instrument-graph?scope=association|parcel|unit|all&parcel=APN&unit=N&around=NUMBER&depth=2&view=shared|private` returns the JSON with its `mermaid`. `all` builds every parcel and takes a while. `&names=1&by=NAME` returns the private view with the names, `names: true`, and `reveal: {at, by, scope, named, log, parcel?, unit?, around?}`; a missing `by`, "jason", or a name other than the signed-in person's is refused (400), and so is a reveal while an admin views the console as someone else.

`InstrumentGraph` (`ui/src/components/InstrumentGraph.tsx`) takes `data` (the payload) and `initial` (a node to select). It draws a layered timeline in SVG: parcels in the first column, instruments one column per recording year, parties last; a dashed line is a lead. Beside it a list of every node is the keyboard path: choosing a node lists its edges, and focusing an edge shows its rules, stores, and notes in a status region. Families can be hidden; the cycles left out are listed; the Mermaid source renders on request through `Markdown`. A private person shows by name when the payload carries `names`, with its role beside it. `OwnerNames` (same file) is the **Show owners' names** action: it asks for the person's name (filled from the console's person), and once the names are shown it says who asked, when, that the reveal was logged, and offers **Hide names**. The onboarding view's "Recorded instruments" tab (`InstrumentGraphTab`) opens masked and refetches with `names=1&by=` on a reveal; a refused reveal stays masked and says why.

## Caveats

- A graph of what the records on disk say. A dotted edge is a lead: something to read, not a finding.
- A lien indexes a person, not a parcel: a lien edge joins a parcel through its owner's name and tenure.
- An instrument seen only cited is a node marked not loaded; its filing and parties are unknown.
- The shared view leaves out every private person; the private view masks their names until a person asks, and each console reveal is logged.
