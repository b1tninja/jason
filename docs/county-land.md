# The county's land: every association's footprint, and watching it

jason reads a county three ways, and ties them together:

| Source | What it gives | Owners named? |
|---|---|---|
| The county's map (ArcGIS layers; `asspy.sacramento.gis`) | every parcel's subdivision, lot, unit, land use, and the number of its last transfer; every recorded condominium plan and final map as a polygon, under the recorder's number | no ("OWNER OF RECORD") |
| The parcel viewer's API (same module) | what a land-use code means, the assessor's map book page (PDF), a map's legal lots, a parcel's maps | no |
| The recorder's index (`asspy.sacramento.recorder`) | each recorded document's filing and both sides | yes |

The assessor's secured roll names owners too. jason uses it to check a strategy (how often the deeds and the roll
agree), not as a source the strategies depend on.

## The stores

- `$ASSPY_HOME/counties/<county>/land.db` (`asspy.land.LandStore`, `County(...).land()`): the map's parcels, plans,
  and maps; land-use meanings; the recorder rows read by number (`deeds`); and `events`, every change a sync found.
- `$ASSPY_HOME/counties/<county>/associations.db`: the association directory (`docs/onboarding.md`).
- `$ASSPY_HOME/counties/<county>/map-books/`: the assessor's map pages, downloaded once.

All of it is cache: owners' names in `deeds` stay there. Pages name an owner only when a person asks (`--names`, P1).

## Finding an association's land

The records tie each piece by a number, not by a guess:

1. **Common areas lead to the association.** The assessor codes common land (`AQ000A` "Residential / Common Area";
   `MPARKA` park or greenbelt, `MAWAYA` walkway, `MROADA` private road). A common parcel's last transfer number is a
   recorder document. Its grantee is the association that took it (`asspy.land.common_area_owners`). In a sample of 40,
   35 went to an association; the others went to a city, a district, or a builder.
2. **The parcel's map holds the community.** A parcel's `SUBDIVISION` is its final map's id (`S`, then the map book's
   book and page). Every active parcel on that map is in the footprint (`asspy.land.footprint`).
3. **A condominium plan holds its units.** The map draws each plan under its recorder number, with the name the
   project goes by. The directory ties a plan to its association by that name (`asspy.associations.tie_names`,
   `--tie-plans`). The plan's polygon then holds the units' parcels (`SacramentoGis.parcels_in`).
4. **A map's number is the recorder's.** The map's book and page for a plan or final map is the recording day and its
   page (`document_number`). The recorder's row for a final map names the builder and the map's full title, and the
   title often cites the deed, parent map, or certificate it subdivides.

Pages 7000 to 7999 and 9000 to 9999 of a day's book are the assessor's own unrecorded documents ("scratch"), and a
page of 0 is unknown. Neither is a recorder number (`asspy.land.recorded_number`).

What does not tie:

- The recorder's detail fields (APN, legal description, cross-references) are empty, so a lien never names its parcel.
- A builder's subdivision map does not tie its declaration to one community: a builder maps several projects at
  once. Measured against plans already tied, it agreed only half the time.

## Watching

`jason land-sync` keeps the store current and logs what changed. Each sync only reads.

| Sync | Reads | Events |
|---|---|---|
| plans and maps | every condominium plan and final map (two layers, seconds) | `condominium plan`, `final map`: a community recorded |
| parcels | transfers since the last read (one query; `--full` reads all half million in about a minute) | `transfer` (a new last-transfer number), `new parcel`, `land use`; `--full` adds `retired parcel` |
| common deeds | the recorder rows for common parcels not yet read | (feeds the footprints) |
| recorder watch | the watched filings since the last read (`asspy.land.WATCHED`) | `association lien`, `association lien released`, `utility lien`, `utility lien released`, `tax lien`, `tax default`, `default`, `mechanics lien`, `governing` (annexations, declarations, plans), `map` |

`asspy.land.events_for` gives one community its events: changes to its parcels, filings that name its association,
and filings against its parcels' owners. The owners come from each parcel's last deed, and the match is by name: a
lead, read before acting. Reading every unit's deed takes one recorder search per day's run of numbers
(`read_deeds`), so county-wide reports read common parcels only. `--deeds` reads a community's units.

The integration registry declares two cadences under County sources: `county-land` (daily `land-sync`) and
`county-land-full` (weekly `land-sync --full --no-watch`). Like every cadence, they run only once a person adopts them
(`jason cadence --restore county-land --by NAME`).

## The pages

`jason hoa-reports` writes a page for each association the land ties to it (`data/reports/hoa/<county>/`):

- formation: maps, plans, governing instruments, first recording;
- parcels by land use, with the common parcels its deeds took;
- turnover: each parcel's last transfer, by year and type;
- the recordings under its name, by year;
- what changed;
- maps: `map.svg`, `footprint.kml` (Google Earth), `footprint.geojson`, and, with `--map-books`, the assessor's pages.

`--only WORDS` narrows to associations whose names hold the words.
