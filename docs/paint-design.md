# Paint module: design

Status: proposal. What exists today is in [paint.md](paint.md): the schedule records, the Sherwin-Williams catalog reader, the
picture reader, `jason paint`, and the palette page. This page is how a community enters its own colors and how they become the
paint assistant.

## The problem

A community's colors live in one of three places: a developer's palette (often only an image), the architectural rules ("choose
from the approved list"), or a board member's memory. Today a schedule is Python rows in a profile. That is right for a record the
developer filed once; it is wrong for a community that has to enter its own and change them.

## Records (extend what exists)

- `PaintSchedule` keeps its rows. Add `Scheme` (number, a name if the schedule gives one, the buildings or streets it applies to)
  so "which building takes which scheme" is data, not a gap. A schedule with no scheme map says so.
- `PaintSpec` gains optional `sheen`, `product`, and a `hex` with `source` ("drawdown card", "formula", "catalog") for a color from
  a maker jason has no catalog for. A catalog color never stores a hex: it is looked up, so it cannot drift from the maker.
- `Maker` stays a closed set. Sherwin-Williams has a reader. Another maker (Dunn-Edwards, Behr, Kelly-Moore, Frazee) is `Maker.OTHER`
  with a hand-entered hex until a reader is written; the check reports "not checked", never a guess.
- Every row carries where it came from: `Origin` (filed by the developer, adopted by the board, read from a picture, entered by
  a person) and its date. A picture reading is evidence until a person confirms it.

## How a community enters its colors

Three doors into the same records, in order of trust. Whichever is used, the result is the same `PaintSchedule`, and the profile's
`paint_schedules()` merges them (profile rows, then the register, then confirmed readings), never the other way round.

1. **A register Sheet** (the way for a community that is not a Python profile). A `Register` row ([registers.md](registers.md)) named
   `paint`: the board's columns are surface, scheme, maker, code, printed name, buildings, sheen, note; jason's columns are the
   catalog name, hex, LRV, a swatch cell, and a status (ok, renamed, discontinued, not found). The board types "SW 7029"; jason fills
   in the rest on the next `jason registers --sync paint`, and writes nothing in a board column. A new scheme is a new row.
2. **A picture** (`jason paint --read IMAGE`, the local model). For a scanned palette. The reading is checked against the catalog
   and shown against any schedule already held; a person confirms it, and it then lands in the register as rows of origin
   "read from a picture".
3. **Profile rows** (`mystique/paint.py`'s kind). For a record the developer filed. Kept, and read-only to the register.

Onboarding gets one item, `paint-schedule`: "Does the association have an approved color list or palette?" Its answer is a file
(Drive id) or "none"; "none" is recorded and is a finding for the board, because architectural review has nothing to compare an
owner's color against.

## What the assistant does

Each is a task that reads the records and applies a result; none decides.

1. **Answer "what color is the X?"** Quote the schedule as printed (code and name), then label what jason adds: the catalog's
   current name, hex, LRV, and a swatch. A question the schedule does not answer (a surface, a building, a sheen) is a miss.
2. **Check an owner's proposed color** against the schedule for that surface and building: on the schedule for this surface, on
   it for another surface, near one (closest scheduled color and its color difference, labeled a screen match), or not on it. The
   result goes to architectural review with the governing text recited. jason never approves or denies a request; the committee or
   board does, in writing, under the association's procedure and the architectural-review statute (Civil Code 4765; read it from
   the statute on disk before quoting).
3. **Watch the catalog.** `jason paint --check` on a schedule (quarterly, and with the January law review): a color renamed or
   discontinued is a board item, not an edit. A discontinued color gets its closest current colors (`--match`), as options.
4. **Prepare a painting job.** For a repaint, a per-building sheet for the vendor: surface, code, name, sheen, and the swatch,
   with the schedule's source and date. It sits beside the reserve component for painting and the vendor's contract; the paint
   schedule does not set the cycle or the price.
5. **Palette page for owners.** The page that exists (`jason paint --page`), per scheme, for the website or a notice.

## Where the law is silent, write it down

Questions the schedule cannot answer are policy questions, and the axiom applies: propose a written policy, have the board adopt
it, apply it the same way each time, record each use. Candidates jason lists for the board, never decides:

- a color on the schedule is discontinued or renamed: what substitutes (the same number, a closest match, or the board's choice);
- an owner asks for a color not on the schedule: the standard for "near enough", if any (a color-difference limit is a number the
  board sets, not one jason picks);
- a touch-up or a partial repaint that must match aged paint: who matches, and who pays;
- a scheme per building: who assigns it, and whether a building may change scheme.

A policy on a subject in Civil Code 4355(a) needs the notice to members under 4360 (`jason rule-change`).

## Interface

- `Community.paint_schedules()` exists (default none). Add `paint_policy()` (default none) for the board's adopted rules above.
- MCP: `paint_colors` (the schedule with catalog data), `paint_check` (findings), `paint_match` (nearest colors for a code or hex).
  Each carries its caveats: the catalog is the maker's current one, screens are not paint, a reading is evidence.
- CLI: `jason paint` (exists), plus `--register` to show the register's rows against the catalog, and `--request CODE --surface S
  --building B` for item 2.
- Nothing here names a community. The first profile's rows stay in its own folder.

## Phases

1. **Scheme map and origins** on the records; the `paint` register spec and its sync; the onboarding item.
2. **Request check** (item 2) with the MCP tools; the confirmation step for a picture reading.
3. **Catalog watch** as a scheduled check that opens board items, and the policy list above as intake questions.
4. **Other makers**: one reader each, only when a community uses one; until then a hand-entered hex, marked as such.

## Open decisions (for the person)

- Which door first: the register Sheet, or the onboarding item plus picture reading? (Recommended: the register, because it is the
  one a community can use without a developer.)
- Does any community need a maker other than Sherwin-Williams soon? If so, which, because each is its own reader.
- Should jason's request check also read the architectural-review rules from the governing documents, or only the schedule?
