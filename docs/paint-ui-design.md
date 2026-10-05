# Paint screen: what a community needs to see

Status: proposal. The records and checks are in [paint.md](paint.md); entry is in [paint-design.md](paint-design.md). This page is
the screen a board member or manager opens when someone asks about paint, and the facts it needs. A mock (buildings in rows, true
swatches, painted and due dates) is the target. It replaces reading a scanned palette: the matrix is built from data, and the scan
is only where the data first came from.

## Scope (October 3, 2026)

The screen is about **the selection of colors and what each one is for** (door, trim, field, fascia), plus an honest answer about
interior colors. It does not need to say which building or unit wears which scheme; that is optional and later (see "The scheme is
per unit or bay" below). Residents mostly ask about interior colors, which an association usually does not set or keep, so the
screen says what the governing documents say and where an answer might be found.

## The matrix

One row per building (or per group the reserve study treats together). One column per surface the schedule names, in the
schedule's own words, each cell a swatch in the maker's catalog color with its code and current name. A scheme toggle switches the
columns that vary. Beside the swatches, the facts that decide *when* and *whether*:

| Column | Question it answers | Source | If missing |
|---|---|---|---|
| Built | How old is the paint's surface? | assessor year built, by parcel, rolled up to the building | "needs input" |
| First conveyance | When did the developer's duties and the association's start? | the recorded first sale of any unit in the building | "needs input" |
| Last painted | When was it done? | a contract or invoice for the work; else the reserve study's implied date | "implied" or "needs input" |
| Cycle | How often? | the reserve study's useful life for the painting component | "needs input" |
| Next due, cost | When, and what will it cost? | the reserve study's remaining life and the plan's expenditure | "needs input" |
| Scheme | Which column of the schedule does this building wear? | the architectural record | "needs input" |
| Colors | What goes on each surface? | the schedule, checked against the maker's catalog | row flagged |

Every date is labeled by where it came from: **recorded** (a contract, invoice, or notice), **implied** (arithmetic from the reserve
study: next due minus useful life), or **needs input**. An implied date is never shown as fact. The reserve study's remaining life
is the preparer's estimate and moves with each update, so the screen shows the study's date beside it.

Not every painted thing is a building. Gates, rails, hydrants, light poles, and kiosks are separate reserve components with their
own cycle. They get their own short list below the matrix.

### The scheme is per unit or bay, not per building (optional, later)

A photo of one entry (a light stucco field, white trim, a dark door) beside a neighbor's entry in the same building run (a green
stucco field) shows that schemes alternate along a building. So the **scheme belongs to a unit or bay**, and the matrix needs a
second level: building rows that expand to their units, each with its own scheme. The building row shows the schemes in use
("scheme 1 on 6 units, 2 on 4, 3 on 2") and the dates, which are per building.

A photo is also the cheapest way to fill the scheme in. The screen shows a unit's photo beside the schedule's candidate swatches
for that surface and asks a person to pick. A pixel match from the photo alone is not reliable: lighting, shade, the camera's white
balance, and stucco texture shift every color (one sampled copy of a photo came out strongly blue, with its white trim reading as
blue). A person choosing among three candidates, or a white-balance card in the frame, is. A photo records what is on the wall and
may differ from the schedule, because a repaint or a fade is possible; the screen keeps "scheduled" and "observed" as separate columns.

Things in a photo that the schedule has no row for (here, the black wrought-iron patio fence and gate, light fixtures, and mechanical
screens) are listed as "not on the schedule" so the board can decide whether the schedule needs a row.

## Interior colors

Residents ask about these most, and the association usually does not know them, because it does not set them. What the screen does:

1. **Say what the documents say.** Recite the operative words with their citation, then label any reading (the "Recite the rule" rule).
   The declaration's interior-decoration section gives each owner discretion over interior decorating and the exclusive right to
   paint the interior surfaces bounding the unit, with its own limits. Where the documents are silent (no interior color list), say so;
   do not infer one.
2. **Say what is not on file.** A search of the library for finish and interior documents found none, so the developer's interior
   color selections are not in the association's records.
3. **Say where an answer might be**, as leads and not facts: the developer or builder (color selection sheets, standard-features
   lists, or sales and closing packets), the original owner's papers, and a paint store, which can color-match a chip taken from a wall.
4. **Offer an owner-reported register.** Builders usually fit out a plan with one interior package, so a few owners' confirmations
   generalize. A register row is: plan (from the assessor's characteristics, already matched to the developer's plans), surface or
   room, maker and code, who reported it and when, and how many others confirmed. Every row is labeled **owner-reported**, never the
   association's record, and the screen shows the count of confirmations. It costs one small form and nothing else.
5. **Point to the exterior palette** for what the association does set (touch-up on doors and trim).

Nothing here makes the association responsible for an interior color, and nothing is approved: the screen gives information and
leaves decisions to owners and the board.

## The questions people actually ask

Read from the association's email and requests (subjects and attachment names only; bodies were not read) and from the reserve
study. Each theme names the fact that answers it:

1. **"What color is my door, garage door, trim?"** The schedule row for that surface and the building's scheme. Needs the scheme per building.
2. **"Can I paint it a different color?"** Whether the color is on the schedule for that surface (the request check in [paint-design.md](paint-design.md)), the architectural rule, and the review procedure. jason does not approve.
3. **"When will my building be painted?"** Next due and the reserve plan's year. A board that has not scheduled the work says "planned, not scheduled."
4. **"When was it last painted?"** Last painted, with its source. Today this is the weakest field.
5. **"What do I buy for a touch-up?"** The code and name, the maker, the sheen if the schedule gives one, and the vendor on the current contract. Say that a touch-up on aged paint may not match the code.
6. **Bids and vendors** ask for the scope: surfaces, codes, and the building list. The screen exports exactly that per building (the swatch Doc and PDF already do).
7. **Related exterior work** that gets mistaken for painting: stucco repair, caulking, garage door service, curb striping. They share a building and a vendor list, so the screen links to them but keeps them separate.

## Data jason needs and does not have yet

- **Scheme per unit or bay.** The schedule shows schemes; nothing says who wears which, and a photo shows they alternate along a building. Ask the board, read the architectural record, or pick from photos (above).
- **Parcel to building.** Year built is stored by parcel, and the parcel-to-address bridge is not in the local stores (the secured-roll table is empty; PayHOA units carry addresses, not parcel numbers). Fill it from the secured-roll sync.
- **First conveyance per building.** The ownership chains hold each parcel's first deed. The building's first conveyance is the earliest across its units. The existing report is a superseded candidate list, so compute it from the audited chains instead.
- **Last painted, recorded.** Read the painting contracts and invoices in the library and email (dates and buildings) as incident events of work type improvement or maintenance. Until then, show implied dates.
- **Sheen and product.** Not on a developer's palette; the board may adopt them.

## Using the email and request history

A scan of subjects and attachment names for paint, color, stucco, trim, and door words found the themes above and no standing FAQ.
Two follow-ups would give the real questions. First, read the bodies of those threads: a deliberate step, since bodies hold owners'
private facts, and the answers belong in a register, not on this page. Second, count how often a surface or building is named. The
topic report's rule for an FAQ candidate is three or more units asking in a year.

## Build order

1. The matrix over what exists: schedule, catalog, reserve study. Gaps shown as "needs input" cells a person can fill.
2. Inputs for the gaps: scheme per building, parcel to building, recorded last-painted with a source document.
3. The request check and the export per building.
4. Draft answers to the common questions from the facts, for a person to send. jason sends nothing.
