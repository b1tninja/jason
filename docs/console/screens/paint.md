# Paint

A new screen, `#/paint`, a tab under Records · phase 3 · CLI: `jason paint` (built), `jason paint --page`, `jason paint --to-doc` · MCP: `paint_colors`, `paint_check`, `paint_match` (to add)

## In the console

None. `jason paint` prints the schedule, checks it against the maker's catalog, writes a swatch page and a Google Doc. The records and the catalog reader are built ([../../paint.md](../../paint.md)); the screen is the matrix of [../handoff-unit-records.md](../handoff-unit-records.md) over them.

## Purpose and personas

What each color is for (door, trim, field, fascia), what the maker calls it now, and when the paint is next due. The questions owners ask most about paint are "what color is my door," "can I use another color," and "when will it be painted," and the interior question the association usually cannot answer.

- **Manager:** answers an owner, prepares a bid's scope (surfaces, codes), refreshes the catalog and the Doc.
- **Director:** reads next due and cost before a budget or reserve decision.
- **Owner (later):** reads the palette and the interior register; reports an interior color.
- **Treasurer, secretary, counsel:** read-only; no writes.

## Data

| Part | Source | Level |
|---|---|---|
| The schedule: rows by surface as printed, colors by scheme, its source document and preparer | `Community.paint_schedules()` (`jason.community.paint.PaintSchedule`) | P0 |
| Each color's current name, hex, light reflectance, family, status | `jason.sources.sherwin_williams.SherwinWilliams.load()` (the catalog kept on disk for a week); `paint.check(schedule, catalog)` for ok, renamed, discontinued, not found, not checked | P0 |
| Coordinating and similar colors | `SherwinWilliams.related(code)`, from the same catalog, no per-color call; a description only on a person's click (`descriptions=True`) | P0 |
| Closest current colors for a discontinued one | `SherwinWilliams.nearest(color, exterior=True)` | P0 |
| Painting component dates: last painted (implied), next due, cycle, cost | `reserve_study(year)` (`jason.mcp.county`): the painting components' useful life, remaining life, and planned expenditure. Last painted is due minus life, labeled **implied** | P1 |
| Recorded last-painted dates | `incident_history(work="improvement")` events whose element is paint, placed on a building (a person confirms before it is cited); each is a `DocRef` | P1 |
| Built and first conveyance | `unit_characteristics()` (assessor year built, by parcel) rolled to buildings through the parcel-to-building bridge; the first conveyance from the audited chains. Both are **needs input** until those exist | P1 |
| The Doc of the palette | `data/paint/doc.json` (the Doc's id) as a `drive_ref` | P0 |
| Interior colors reported by owners | the interior register (`unit_record.InteriorReport`), by plan | P1; the reporter is never shown to others |

The catalog is fetched only by a person's refresh (`jason paint --refresh`, or the screen's button as a job); nothing on load calls Sherwin-Williams, Google, or PayHOA.

## Layout

```
+---------------------------------------------------------------------------------+
| Paint                                         [Refresh the catalog] [Make the Doc]|
| Exterior palette · prepared for the developer, 2015-06-01 · original [chip]       |
| Catalog copy from Oct 3 · 1 color renamed · 0 discontinued    CLI: jason paint   |
+---------------------------------------------------------------------------------+
| Scheme [1][2][3]                                                                |
|              Scheme 1       Scheme 2       Scheme 3                             |
| FASCIA       [swatch]                                                           |
| STUCCO TRIM  [swatch]                                                           |
| STUCCO FIELD [swatch]       [swatch]       [swatch]                             |
| ENTRY DOORS  [swatch]                                                           |
| GARAGE DOORS [swatch]       [swatch]                                            |
| ROOF         tile, not paint                                                    |
+---------------------------------------------------------------------------------+
| Dates by building group     Last painted   Next due    Cost at today's prices    |
| Buildings 1, 2              2019 implied   2026        $50,000                   |
+---------------------------------------------------------------------------------+
| Interior colors, as owners reported them (not the association's record)         |
| Plan A · Living room · SW 7008 · confirmed by 3 owners          [This matches mine]|
+---------------------------------------------------------------------------------+
| Screens and printers shift color. The number on the schedule governs.            |
+---------------------------------------------------------------------------------+
```

A swatch opens `ColorDetail`. A renamed color shows the printed name beside the current one.

## Components

`PaletteMatrix`, `Swatch`, `ColorDetail`, `SourcedDate`, `InteriorColorRegister`, `DocList` for the palette's documents, `Findings` for the check, `Caveats` for the catalog's copy, `Command` for the CLI, `Confirm` for the two writes.

## Actions

| Action | Effect | How |
|---|---|---|
| Refresh the catalog | fetches the maker's open catalog | a job a person asks for, behind `Confirm`; with writes off, shows `jason paint --refresh` |
| Make or refresh the Doc | `jason paint --to-doc --yes` | behind `Confirm`; says it replaces edits made in the Doc since |
| Open a color | `ColorDetail`, with an optional "fetch the description" | a read of one color's page data |
| Report an interior color (later) | adds an owner-reported row | the owner's act, in their name; never a board write |
| Confirm "this matches mine" (later) | adds one to the confirmation count | the owner's act; one per unit |

jason never changes a schedule row; a renamed or discontinued color is a finding for the board.

## States

Loading (the catalog copy takes under a second); no schedule on file ("The association has no color schedule yet." with the picture reader's command); catalog unavailable (the screen uses the copy on disk and says how old it is, or shows the fetch command if none); renamed, discontinued, or not found (a flag on the swatch and a `Findings` line); a color from another maker (entered, not checked); a row with no paint; interior register empty, with one report, confirmed, or conflicting.

## Privacy

The palette and the catalog are public (P0). Reserve figures are P1. An interior report never shows who reported it; the confirmation count is the only evidence shown. Contractor names from recorded painting events are not shown in this screen.

## Acceptance criteria

1. With the sample schedule, the matrix shows each surface's label as printed, each scheme's swatch with its code and name in text, and flags the one renamed color.
2. No swatch is filled from anything but a catalog or typed hex; a hand-entered color says so.
3. Last painted is labeled implied with its arithmetic unless a recorded event is attached; next due and cost match the reserve study's schedule.
4. With the network off and a catalog copy on disk, the screen renders and states the copy's age; with neither, it shows the fetch command and a stated empty state.
5. The screen makes no network call on load; the refresh and the Doc are behind `Confirm` and named people.
6. Every status is readable without color; the matrix is a table with headers; the scheme toggle is a radio group; the print layout shows the matrix and the caption.
7. A renamed color changes nothing in the schedule.
