# Handoff: finding the association, its documents, and its instruments

For the design pass on four components built in October 2026. They render today, in the Onboarding screen's first three tabs, with working data; what they need is the design system's look and a few decisions below. The behavior and the words are settled by [screens/onboarding.md](screens/onboarding.md#finding-the-association-and-its-documents), [components.md](components.md), [key-documents.md](../key-documents.md), and [instrument-graph.md](../instrument-graph.md).

## The components

| Component | Where it renders | Data | States to design |
| --- | --- | --- | --- |
| `AssociationPicker` | Onboarding → Find the association, card 1 | `GET /api/associations?county=&q=` | not surveyed (a command to run), searching, matches (a combobox listbox), no match, chosen (spellings behind a disclosure) |
| `DocumentLocator` (and its parts `LocatedDocuments`, `BoardList`, `TieBadge`) | Find the association, card 2 | `GET /api/documents-located`; `POST /api/write/documents-located/locate` | missing (note, command, "Locate documents"), confirming, job queued or running (polls), job failed, writes off (the command instead of the button), located (grouped by checklist item), the board's printable list |
| `KeyDocuments` | Onboarding → Key documents | `GET /api/key-documents`; `POST /api/write/key-documents/<key>` | each status word (expected, located, held, linked, missing), copies and links, link / upload / unlink / status behind `Confirm`, a refused write |
| `InstrumentGraph` (and `OwnerNames`) | Onboarding → Recorded instruments | `GET /api/instrument-graph?scope=association`; `POST /api/write/instrument-graph/reveal` with `{by, scope}` to show owners' names (logged; a URL never carries a name) | the timeline with its node list, a focused edge's provenance, family filters, cycles left out, the Mermaid view, masked, asking for a name, names shown (with who asked and that it was logged), a refused reveal |

Sample data, with made-up names only, is each component's test fixture: `ui/src/components/associationpicker.test.tsx`, `documentlocator.test.tsx`, `keydocuments.test.tsx`, `instrumentgraph.test.tsx`, and `ui/src/views/onboarding.test.tsx`. The real payloads have the same shape.

## What the design must keep

- **A lead is not a pin.** A directory row, a located document, and a graph edge marked a lead are readings to confirm, never findings. The tie words carry this: "names the association" and "recorded with the association's documents" are strong; "the builder's filing" is weak and "may be another community's". Keep the words, not only a color.
- **Nothing reaches the county from the page.** "Locate documents" queues a read job a named person asks for; the page reads the job's result. Writes off shows the command.
- **Every write names a person**, through `Confirm`; jason never writes as itself. Unlink never deletes a file.
- **Owners are masked by default, and the mask can be lifted.** Owners' names are P1 ([security-and-privacy.md](security-and-privacy.md)): shown to the people who work with them, kept in jason's private data, never committed (fixtures use made-up names). The documents located list each instrument's private persons by name with their index side (`people`). The graph opens in the shared view (no private person); **Show owners' names** asks for the person's name, shows the names, says the reveal was logged (`data/console/reveals.jsonl`), and **Hide names** returns to the masked view, so a screenshot or an export holds no name unless someone asked.
- **A second person confirms** the declaration and its amendments: the high-stakes mark stays visible.
- WCAG 2.2 AA as in [components.md](components.md#accessibility): the combobox pattern, named regions per checklist item, status and alert regions, the graph's node list as the keyboard path.

## Decisions for the design

1. **Styles.** The finder's rules are a section of `ui/src/styles.css` (they were `views/discovery.css`, which the design library never shipped), so all four components render styled in the design project. They use the shared tokens; how far to restyle them is the design's.
2. **The first tab.** "Find the association" is listed first, but Onboarding opens on "Request list". A community with no profile facts yet may want to open on Find.
3. **Answering a question.** Each located item names its onboarding question (`fact:lookup:located-<item>`); "Answer it" shows only when a `questionHref` is passed, and the console has no route for the onboarding questions yet. Design the route, or the link to it.
4. **Slow loads.** Key documents and Recorded instruments each take about ten seconds to load on real data. Design a loading state worth that wait, or ask for a server cache first.
5. **A large graph.** The timeline is a column per recording year; a subdivision with hundreds of instruments crowds it. Choose a layout (grouping by parcel or by formation bundle, a zoom, or the list first).
6. **The board's list.** The printable checklist (hold a copy, order a copy) is a first pass at paper.

## Not part of this pass

The four components, their parts (`LocatedDocuments`, `BoardList`, `TieBadge`, `OwnerNames`, `Day`), and their previews are in the Jason UI design project as of the October 3, 2026 sync; `ui/src/components/index.ts` exports them all with their types.
