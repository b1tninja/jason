# Placer County document processes

jason built its document processes on Sacramento County's recorder: the
index, the detail pages, the cache, the walks, and the readings. This page
lists each one with its Placer counterpart. A counterpart is either built
now, or listed as a gap with the reason.

The HTTP and the cache are asspy's (`asspy.placer`). The walks, readings,
reports, and bundles are jason's (`jason.community.placer`,
`jason.tasks.placer_history`). The other pages cover Sacramento:
[recorded-instruments.md](recorded-instruments.md),
[property-histories.md](property-histories.md), and
[document-readings.md](document-readings.md).

## How Placer's index differs, and what each difference changes

| Placer's index | What the Placer code does instead |
| --- | --- |
| A document number is `YYYY-NNNNNNN`. It carries no recording day, and the assessor prints it as `YYYYRNNNNNNN`. | `normalize_document_number` reads every spelling. `dated_numbers` is False, so a date comes from the row and never from the number. Numbers in a year still run in sequence, so a closing's instruments sit side by side, as Sacramento's do. |
| The detail page lists no cited documents (`carries_citations` False). | A prior-deed seat or released-lien seat is filled by party from the instruments in hand (`processes.read`). Each chain step joins the one before it by the grantor's name, never by a citation. |
| The detail page names no parcel (APN). | Only the assessor's current instrument ties a number to a parcel. A builder's lot meets its parcel through that one deed. |
| The type is printed as free text (`DEED`, `NOTICE OF DELINQUENT ASSESSMENT - HOMEOWNERS ASSOCIATION`). Sacramento uses a numeric filing code. | `asspy.placer.filings.FILING_CODES` maps each Placer type to the shared class code (680, 695, 386, 655, 320, …). `classify_filing` takes the walk kind from that class, so `encumbrances`, `title`, `owner_events`, and `beside_step` read Placer instruments the way they read Sacramento's. A name not in the table falls back to the shared readers, which go by the words. |
| A plain name search returns every type. Filtering by type works only on a name search, with catalog ids such as `T1` (`types=`). | `TYPE_IDS` pins the ids from the live catalog. `type_ids(names, catalog)` prefers a live `document_types()` list. A name too common to read whole is narrowed by type, not by filing code. |
| A name matches as a prefix, and `%` is a wildcard anywhere. `"%"` with `types=` returns every instrument of those types. | Builders are searched as `FORM%` together with the fee and completion types, over a date window. The window is halved until each half fits on one page (`PlacerIndex.typed`, at most 1000 rows a page). |
| One number can be listed twice: a substitution and its reconveyance, or a deed of trust and its assignment of rents. | `filed_instruments` makes the two rows one instrument. The kind that moves the most decides it (the reconveyance, the deed of trust), and the class code comes from that row. `PlacerIndex.store` merges a later partial reading of the same number into the cached row. |
| A search sometimes comes back blank, or the session ends (`SearchFailed`). | `PlacerIndex.page` keeps one guest session. On a failure it opens a new session and runs the search again (`retries`). Nothing is stored for a search that never answered. |
| The name index is reliable from about 1997. Names before 2010 are abbreviated (`ASSN`, `HOA`, `EST`). | A chain can stop at a deed from the 1990s. The report shows it as a gap. |

Four type names misread by their words are now read by class:

- A request for notice of a trustee's deed is not a trustee's deed. `conveys_row` took it for one; `asspy.placer.filings.conveys` does not.
- A rescission of a notice of default is not a default.
- A deed in lieu of foreclosure and a tax deed do convey. `conveys_row` missed both.
- A severance of joint tenancy and a declaration of trust are not governing declarations.

## The cache

`County("placer").cache()` is asspy's per-county file,
`$ASSPY_HOME/counties/placer/index.db`. `jason.community.placer.open_cache()`
opens that same file through jason's `IndexCache`, which writes the walk's
notes on each row as the row is stored.

Every search goes through one `asspy.placer.PlacerIndex`:

| Method | Search | Stored under |
| --- | --- | --- |
| `number(n)`, `range(low, high)`, `around(n, before, after)` | Number range | `range\|low\|high` |
| `name(name, after, before, types, limit)` | Party name, `%` wildcards. A count over `limit` is stored wide. | `name\|NAME\|types\|after\|before` |
| `typed(types, after, before, name="%")` | Every instrument of these types in a window, halved until each half fits | `typed\|NAME\|types\|after\|before` |
| `held(low, high)`, `around(..., search=False)` | No search: the cached rows in a number range | — |
| `pages(n)` | The detail page's page count | the row's `pages` |

Each row is a `FiledInstrument` with its `kind`, its shared `filing_code`,
and Placer's own type name. A search that has run before is read from the
cache. A second walk of the same parcel runs no searches at all.

## Inventory: each Sacramento process and its Placer counterpart

Status: **built** (works on Placer now), **shared** (the Sacramento code
already works on Placer records), **gap** (not built; the reason is given).

### Index search and cache

| Sacramento process | Placer counterpart | Status |
| --- | --- | --- |
| Search by number or party, narrowing a wide name by filing (`mcp/index.recorder_search`) | `PlacerIndex.name` / `range`. A wide name is narrowed by `types=`. | built. The MCP tool is still Sacramento-only. |
| Read one instrument: APN, parties, citations (`recorder_detail`) | `PlacerCountyRecorder.row_detail` (parties, pages) and `PlacerIndex.pages` | built. The page has no APN and no citations. |
| Earlier grant deeds into a grantee (`recorder_priors`) | `placer.parcel.prior_deeds`: fee types, the grantor named as grantee | built |
| Same-day neighbors and cited numbers (`recorder_around`) | `PlacerIndex.around`, `processes.neighbors(index=)` | built. No citations to follow. |
| Party search and trace (`OwnershipWalks.for_parties`, `trace`) | `PlacerCountyRecorder.for_parties`. Fee rows are found by class (`conveys`); a wide name is narrowed to `FEE_TYPES`. `trace` is inherited. | built |
| Link numbers into a chain (`OwnershipWalks.history`, `succession`) | Live: `history`. Cached: `succession` over the cached instruments (`placer.parcel`). | built |
| A developer's sales (`forward_sales`) | `placer.descent.developer_seed`: one type search per name form and window | built |
| Index cache with walk notes (`index_cache.IndexCache`) | `placer.index.open_cache` over `County("placer")` | built |
| Cache one name; narrow when wide (`cache_party_search`) | `PlacerIndex.name`. The wide flag is stored, and a wide name is narrowed by type. | built |
| Cache the community's names and known parties (`cache_community_names`, `cache_known_parties`) | `bundle.governing_instruments` (governing types by name) and `parcel.cache_owner_filings` | built |
| Cache cited numbers (`cache_cited_numbers`) | — | not needed. Placer lists no citations. |
| Backfill blank kinds (`backfill_empty_kinds`) | The kind is set when the row is stored, from the type name (`FILING_CODES`) | built. An unmapped Placer type keeps the kind the shared readers give it, which can be blank. |
| Parse numbers in text (`recorder.document_numbers`) | `asspy.placer.normalize_document_number` | gap for scans. jason's text regexes look for 12 digits. |
| Sync solar filings by lessor (`tasks/sync_solar`) | The classes line up: `UCC FIXTURE FILING` is 368, and the solar contract notice is 549, so `solar_notices` and `solar_record` read them. Search a lessor with `PlacerIndex.name(lessor, types=type_ids(("UCC FIXTURE FILING", "NOTICE OF INDEPENDENT SOLAR ENERGY PRODUCER CONTRACT")))`. | gap for the task. Its search filters by Sacramento `Filing`. |
| Sync liens for owners, developers, and the association (`tasks/sync_liens`) | `parcel.cache_owner_filings`: every owner on a chain, every type, narrowed to `LIEN_TYPES` when wide. Association liens: `PlacerIndex.typed(type_ids(("NOTICE OF DELINQUENT ASSESSMENT - HOMEOWNERS ASSOCIATION",)), name="ASSN NAME%", …)` | built per parcel and lot |
| Onboarding lookup and document locator | Already county-neutral (`READERS` has Placer) | shared |

### Chain walks

| Sacramento process | Placer counterpart | Status |
| --- | --- | --- |
| One leaf out from the builder (`builder_leaf`) | `placer.descent.descend(depth=1)`: grants, notices of completion, and each grant's neighbors | built |
| Descend until the current deed meets the builder side (`descend`, `find_meets`) | `descend(depth=n, currents={apn: number})` with the shared `find_meets` (document or handoff) | built. The MCP `recorder_descend` is still Sacramento-only. |
| Place deeds out from anchors (`expand_anchors`) | Same function; it works on `Conveyance` | shared |
| Chain tests (`OwnershipHistory`, `chain_ready`) | Same | shared |
| Walk one parcel live (`placer.history.walk_ownership`) | Kept. `parcel.parcel_record` is the cached counterpart. | built |

### Process readings

| Sacramento process | Placer counterpart | Status |
| --- | --- | --- |
| Name an anchor's process (`processes.read`) | `placer.processes.read_chain(index=, search=)`: Placer numbering, priors matched by party | built |
| Load the numbers a reading needs (`processes.gather`) | `build_parcel_history(recorder=)` passes Placer's numbering to `gather` and `read` | built. The optional `recorder=` leaves Sacramento unchanged. |
| Next party searches (`follow_on`) | `descent.later_deeds` (`FEE_TYPES` by type id) | built |
| Twins, re-recordings, family transfers (`beside_step`) | Same function. Placer's class codes line up with it. | shared |

### Parcel history and reports

| Sacramento process | Placer counterpart | Status |
| --- | --- | --- |
| Build a unit's `ParcelHistory` (`build_parcel_history`) | `parcel.placer_parcel_history`, `parcel.parcel_record`, `tasks.placer_history.lot_histories` | built. There are no tax bills, deed scans, public reports, or member rolls for Placer, so the history has no price, no bill calendar, and no member check. |
| Markdown and sheet tabs (`write_markdown`, `property_tabs`) | `parcel.parcel_markdown`, `tasks.placer_history` (`<apn>.md`, `subdivision.md`, `liens.md`). `property_tabs` reads Placer histories as they are. | built. `write_markdown`'s market pages read the instance's own community. |
| Pinned chain report and Mermaid (`history_report`) | Same functions | shared |
| County tabs (`county_report`) | `deed_history_values(history)` works as is | gap for taxes. asspy has no Placer tax adapter. |
| Current owner per parcel (`ownership_sheet`, `ParcelOwnership`) | `PlacerCountyAssessor.ownership` (the Placer recorder) | built (existing) |
| Audit chains against bills (`audit_chain`) | Runs inside `build_parcel_history` | partial. Without bills, the 2% checks are empty. |
| What the processes explain in the cache (`coverage`) | The class codes line up, so it can read a Placer `IndexCache` | gap in wiring. The CLI and MCP open the Sacramento cache. |
| Count the cache by filing (`index_survey`) | `cache.kind_counts()`, plus `instrument_class` over a Placer cache | gap in wiring (MCP) |

### Liens, title, solar, mechanics, briefs

| Sacramento process | Placer counterpart | Status |
| --- | --- | --- |
| Liens on a parcel's owners by tenure (`parcel_liens` over `encumbrances`) | The same, through `build_parcel_history`'s `load_naming=cache.naming_party` | built. Association liens are 386 and 655. Loans are 230, 238, 239, and 613. Mechanics are 389, 635, and 270. Lis pendens are 385 and 651. |
| Lien standing (`title.lien_standing`, `title_watch`) | The same, over Placer `ParcelHistory` | built. The utility-roll standings need tax bills, so a utility lien reads as standing. |
| Solar lease standing (`solar_record`) | Pass a `SolarProgram` to `placer_parcel_history` | shared once lessor filings are cached |
| Mechanic's liens | `Process.MECHANICS_LIEN` through `encumbrances` | built |
| Owner events (`standing.owner_events`) | 466 power of attorney, 697 transfer-on-death deed, 555/558 letters, 559 decree of distribution, 153 death affidavits | built |
| Unit and escrow briefs, recent filings, digest (`briefs`) | Read `ParcelHistory` | gap in wiring. They load the instance's own histories. |
| Explain a filing (`explain_filing`) | `asspy.placer.classify_filing(name)` | built (library) |

### Governing instruments and formation

| Sacramento process | Placer counterpart | Status |
| --- | --- | --- |
| The association's recorded record and 2792.23 deliveries (`recorded_association`, `governing.locate_governing`) | `bundle.governing_instruments` and `community_formations`: declaration (324/162), annexation (320), amendment (220/225/499), condominium plan (301/240), bylaws (494), articles (446), map (435/433), and the common-area deed into the association, read from same-day neighbors | built as formation bundles. The record itself (`lar`) reads the instance's own association. |
| Community search plan (`index_queries`) | `developer_seed` and `governing_instruments` type searches | built |
| Copy-order list (`records_request`) | Page counts via `PlacerIndex.pages` | gap. Placer's copy fees and order form are not modeled. |

### Document text and tax

| Sacramento process | Placer counterpart | Status |
| --- | --- | --- |
| Read a recorded copy's stamp and citations (`readings`) | — | gap. The stamp regexes are Sacramento's, and no Placer copies are on disk. |
| Deed scans: price and placement (`scans`, `consideration`) | — | gap. No Placer copies; the city transfer-tax rates differ. |
| Property tax, secured roll | — | gap. No Placer adapter in asspy. |
| Assessor characteristics | `PlacerCountyAssessor.characteristics` | built (existing) |

## The bundle the instrument graph reads

`jason.community.placer.parcel_bundle(record, index, developers=)` and
`subdivision_bundle(descent, index)` each return an `InstrumentBundle` built
from shared shapes only:

| Field | Type | What |
| --- | --- | --- |
| `county` | `str` | `"placer"` |
| `scope` | `str` | `"parcel"` or `"subdivision"` |
| `label` | `str` | The APN, or the developers' names |
| `instruments` | `tuple[asspy.core.FiledInstrument, ...]` | Every instrument touched, in number order. `kind` is the walk kind; `filing_code` is the shared class code; `filing_name` is Placer's type name (`"; "`-joined for a two-row number). |
| `histories` | `tuple[OwnershipHistory, ...]` | One per parcel or lot. Steps are `ChainStep(Conveyance, priors, cited)`. In Placer, `cited` is always empty. |
| `readings` | `tuple[placer.processes.ProcessStep, ...]` | `number, recorded, kind, filing_name, grantors, grantees, process, complete, reassesses, companions, reading`. `reading` is `processes.Reading` with its `slots` (`Finding`: role, required, reason, number, date window). |
| `formations` | `tuple[Formation, ...]` | `Formation(kind, anchor: FiledInstrument, members: tuple[Member(role, instrument, why)])`. Kind `closing`: notice of completion, buyer lien, companion vesting, partial reconveyance. Kind `community`: declaration, annexation, condominium plan, bylaws, map, common-area deed. |
| `liens` | `tuple[association_record.ParcelLien, ...]` | Parcel scope: owner, `asspy.filings.Encumbrance` (process, debtor, claimant, steps), `during_tenure`, `community` |
| `parcels` | `tuple[(apn, newest number), ...]` | The lots placed on a parcel |
| `notes` | `tuple[str, ...]` | What the bundle could not settle: buyer names too common to follow, and deeds reached from two lots |

`bundle.as_dict()` is the JSON form:

```json
{
  "county": "placer", "scope": "parcel", "label": "000000000001",
  "instruments": [{"number": "2019-0000201", "recorded": "2019-06-03", "kind": "fee",
                   "filingCode": "680", "filingName": "DEED", "family": "conveyance",
                   "grantors": ["..."], "grantees": ["..."], "crossReferences": []}],
  "histories": [{"apn": "000000000001", "developers": ["..."], "reachedDeveloper": true, "gaps": [],
                 "steps": [{"number": "...", "recorded": "...", "grantors": [], "grantees": [], "priors": [], "cited": []}]}],
  "readings": [{"number": "...", "process": "developer closing", "complete": true, "reassesses": true,
                "slots": [{"role": "notice of completion", "required": true, "reason": "present", "number": "...",
                           "after": "", "before": ""}], "companions": ["..."]}],
  "formations": [{"kind": "community", "anchor": "...", "recorded": "...",
                  "members": [{"role": "common-area deed", "number": "...", "why": "deed into an association the same day"}]}],
  "liens": [{"owner": "...", "process": "assessment lien", "status": "open", "duringTenure": true, "community": true,
             "debtor": [], "claimant": [], "steps": [{"number": "...", "recorded": "...", "filing": "386 NOTICE OF ASSOCIATION LIEN", "effect": "opens"}]}],
  "parcels": [{"apn": "000000000001", "newest": "..."}],
  "notes": ["..."]
}
```

Each formation, chain step, and lien here is a reading of numbers and names.
Treat it as a lead, not a pin. A handoff by name can join a namesake's deed,
and a person confirms a step from the deed's copy.

## Running it

```python
from datetime import date
from jason.community.base import Developer
from jason.community.placer import placer_index, parcel_record, parcel_bundle, descend, subdivision_bundle

index = placer_index(pause=1.0)                       # asspy's Placer cache, one held session
record = parcel_record("123 EXAMPLE LN", index=index, developers=(Developer("Example", ("EXAMPLE BUILDER LLC",)),))
print(record.markdown)
bundle = parcel_bundle(record, index, developers=record.history.developers)

found = descend(index, developers=(Developer("Example", ("EXAMPLE BUILDER LLC",)),),
                after=date(2017, 1, 1), before=date(2018, 12, 31), depth=2, neighbors=False)
whole = subdivision_bundle(found, index)
```

`jason.tasks.placer_history.placer_parcel_report(query, out_dir)` and
`placer_subdivision_report(developers, out_dir, after=…)` write the pages
and the bundle JSON. Their rows name owners, so write them under `data/`.

`descend(neighbors=True)` runs one range search for each run of nearby
grant numbers. That is complete, but a builder's grants are rarely
consecutive, so it costs about one search per lot. `neighbors=False` relies
on the builder's search, which also finds partial reconveyances, and on each
buyer's search across every type. Those two searches already hold every
seat that names the closing's parties.

The live index is read-only. Each search takes several seconds, so
`pause=1.0` keeps a walk polite. At that pace a 100-lot subdivision two
leaves deep is about a hundred searches, roughly fifteen minutes the first
time and none after that.
