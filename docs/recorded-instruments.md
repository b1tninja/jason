# Recorded instruments

What each instrument in the county's public index is, which lifecycle it opens or closes, and which official record confirms it. The conveyance processes are in the private notes (mystique/notes/ownership-history.md); this page covers everything else the index returns for the community, its owners, and its developers. The code is `jason.community.filings` (the registry and the lifecycles), `jason.community.governing` (the 2792.23 deliveries), and `jason.community.association_record` (the association's record and each parcel's liens). Survey date: 2026-09-28.

## How to read an index row

The index prints a filing code and name, a date, and two party lists: the "R" side that gives and the "E" side that receives. What the sides mean depends on the filing. `instrument_class` names them.

| Family | Filings | R side | E side | Lifecycle |
| --- | --- | --- | --- | --- |
| Conveyance | 685 grant deed, 689 quitclaim, 680 deed | grantor | grantee | the chain of title |
| Loan | 230 deed of trust, 229 construction, 231 with assignment of rents | trustor (the owner) | beneficiary (the lender) | opens a loan |
| Loan paperwork | 227 assignment, 239 substitution of trustee, 658 release of rents | assignor or owner | assignee or new trustee | advances the loan, moves nothing |
| Release | 238 reconveyance, 613 partial reconveyance | trustee | owner | closes the loan |
| Default | 531 notice of default, 543 notice of trustee's sale | whoever recorded it | | escalates the loan or the lien it cites |
| Sale | 695 or 694 trustee's deed, 801 deed in lieu, 692 tax deed | trustee and trustor, or the tax collector | buyer | closes the loan or the tax default by conveying the fee |
| Rescission | 720 | claimant | debtor | closes a default without a sale |
| Assessment lien | 386 notice of association lien, 655 release, 624 release of lien | owner, then the association | the association, then the owner | opens and closes the association's lien |
| Utility lien | 401 utility billing lien, 644 termination | customer, then the utility | the utility, then the customer | opens and closes |
| Tax default | 802 notice of power to sell tax-defaulted property, 720 rescission, 692 tax deed | owner, then the tax collector | the tax collector, then the owner or buyer | opens, then closes by payment or by sale |
| Judgment and state liens | 376 or 405 abstract of judgment, 717 judgment by default, 400 state tax lien, 623 release of judgment, 624 or 619 release, 576 order of sale | debtor | creditor or the state | opens and closes; an order of sale escalates |
| Support lien | 406 notice of support judgment, 392 order for support payment, 593 registered foreign support order, 623 release | obligor | the county's support agency | opens and closes; a lien on real property under Family Code section 4506 |
| Federal and county tax liens | 379 certificate of federal tax lien, 631 release; 381 certificate of tax collector's lien, 623 or 624 release | taxpayer | the United States or the tax collector | opens and closes |
| Special tax | 407 notice of special tax lien | owner | a community facilities district | opens; the district's standing charge, not a delinquency |
| PACE | 387 notice of assessment | owner | the financing agency | opens; stays until released |
| County reimbursement | 183 agreement to reimburse, 624 release | debtor | the county's Department of Revenue Recovery | opens and closes; a voluntary lien for county costs |
| Code enforcement | 398 notice of substandard building, 619 or 624 release | owner | the city | opens and closes |
| Loan paperwork, more | 208 subordination, 235 modification, 257 assignment of rents, 614 partial release | owner | lender | advances the loan |
| Cure | 720 rescission, 616 cancelled default | claimant | debtor | ends the default and leaves the lien or loan open; on a tax default it closes the process |
| Mechanic's lien | 389 notice of claim or mechanics lien, 232 extension, 635 release, 270 or 269 bond, 385 or 223 notice of action, 651 withdrawal, 291 partial discharge | owner (the debtor), or the plaintiff on a notice of action | claimant (the contractor) | opens; a release or bond closes; a notice of action puts it in suit; ninety days unsued expires it |
| Fixture filing | 368 UCC financing statement, 372 termination | debtor (the owner) | secured party: a solar lessor or lender, the utility, or a bank; `classify_secured_party` says which | opens and closes |
| Notice | 546 request for notice, 549 notice, 306 notice of completion, 305 cessation, 539 non-responsibility, 535 bulk transfer | requester or builder | | none; 542 notice of intended sale is a bulk-sale notice unless the tax collector recorded it, when it escalates a tax default |
| Estate and court | 555 letters of administration, 558 letters testamentary, 559 order | estate or court | administrator, executor, or party | none; an owner event |
| Fixture filing, more | 365 amendment, 366 assignment, 367 continuation, 370 partial release, 371 release | debtor | secured party | advances or closes the fixture filing |
| Map and plan, more | 285 certificate of correction, 460 lot line adjustment, 307 plans and specifications | owner | | none; map or plan family |
| Governing | 162 or 324 declaration, 220 amended restriction, 225 amendment, 320 declaration of annexation, 478 and 499 covenants, 604 cancellation, 446 articles, 494 bylaws, 476 resolution | declarant | | none; a 2792.23 delivery |
| Plan and map | 301 condominium plan, 240 plan amendment, 435 subdivision map, 433 parcel map | owner | | none; a 2792.23 delivery |
| Vital | 153 affidavit of death, 156 terminating joint tenancy | decedent | survivor | none; title passes outside the chain |
| Authority | 466 power of attorney, declaration of homestead | principal or owner | attorney in fact | none |
| Easement | 190, 681, 485 | grantor | grantee | none; a common-area right |

## Lifecycles

`encumbrances` pairs the lien-family instruments naming a party into lifecycles. A closing or escalating instrument joins the newest open lifecycle it cites, else the newest open one of its process that names the same debtor, else, for a notice of default or a rescission that names only the claimant, that claimant's newest open lien. A release with no lien in hand still shows, so nothing is hidden. Each lifecycle reports open, in default, noticed for sale, or closed, and the date it closed.

An assessment lien follows Civil Code sections 5650 to 5720: the association records the notice of delinquent assessment (386), and either releases it (655 or 624) when paid or records a notice of default (531) and a notice of sale (543) toward a trustee's deed (695), unless a rescission (720) ends the default. The association's own filings of 531 and 720 name only the association, so they join by citation or by the claimant rule.

A utility lien is the city's: a customer account in arrears becomes a lien (401) and a termination (644) releases it. The association's own common-area accounts can carry them.

A tax default is the tax collector's: five years after the first unpaid bill the notice of power to sell (802) records against the owner, and a rescission (720) follows payment. The association's own common-area parcels can go through this. The bills themselves, in `data/tax.db`, show the delinquency before any of that records, and the Taxes due tab is the earlier warning.

## The survey of the cache, and what it left unmodeled

The `index_survey` tool counts every cached document by family, process, and filing and lists the filings no class reads. Reading the `other` family against the community's parties produced the models above: the judgment, support, federal, and county tax liens; the special tax notice; the county reimbursement agreement; code enforcement; the loan paperwork that advances rather than opens a loan; the cure that a rescission or a cancelled default is; the probate letters and court orders as owner events; the map corrections; and the rest of the UCC family. An order of sale beside a same-day deed from a developer reads as a court-ordered (bankruptcy) sale on the land chain, not a resale, and a notice of intended sale the tax collector recorded is the notice of a tax sale, which a rescission or a tax deed should follow.

Rows the early walks stored with no filing at all (labeled only fee, lien, release, or foreclosure) are read by that label: a lien row is a deed of trust, a release a reconveyance, so they form loans instead of falling out. What stays unmodeled is noise around an owner's name rather than a process: notary bonds, business agreements, partnership statements, and a 1984 CalVet agreement to sell. Each has a class and a name now, so a report can say what it is, and none opens a lifecycle.

This association's findings are in its private notes (mystique/notes/recorded-instruments.md).

### Coverage: what each process explains, and what is left

The `index_coverage` tool (`jason index-coverage`) goes the other way round: it reads every cached document against the parcel histories, the association's record, and the land chain, and says which process holds each one. A document is explained when it is a chain step or an instrument beside one, a step of a lien lifecycle, an owner event, a candidate a pass placed, a solar contract notice, a governing record, the association's own filing, or the community's land chain. What is left is sorted by the party it names and the pattern it fits, and each pattern is a bucket, not yet a process:

| Bucket | What it is |
| --- | --- |
| re-recording of a chain step | a conveyance that cites a chain step, or vests the same parties within the twin window |
| companion transfer at a closing | a family transfer within three days of a chain step, sharing a party with it |
| an owner's other property | a filing on an owner's name outside the tenure, or a conveyance during it that the parcel does not hold |
| the developer's other project | a governing instrument or deed the developer recorded elsewhere |
| the developer's insolvency | a notice of action, withdrawal, or lis pendens naming the developer in its insolvency |
| no process yet | a filing naming a community party that no pattern places |
| names no community party | noise a wide-name search swept in; counted, not sorted |

A document naming an owner during the tenure that lands in "no process yet" is the one to look at: it names the unit's owner while they held it, and no parcel process picked it up. The rest of that bucket is the owner's life elsewhere. Buckets become processes when one recurs on a parcel; the re-recordings and companions are the first candidates, as related instruments beside the chain step.

## Mechanic's liens

A contractor, subcontractor, or supplier unpaid for work on a property records a claim of lien (389) against the owner. The Civil Code sets its life (sections 8412 to 8494). The claim must be recorded within ninety days of completion, or thirty or sixty days after a notice of completion (306) or cessation (305). Once recorded, the claimant has ninety days to file suit and record a notice of action (385, amended by 223); otherwise the lien expires by section 8460 and is unenforceable, though it stays of record until the claimant releases it (635, or a plain 624 release of lien), the owner bonds it off (270, 269), or a court orders it released on the owner's petition (section 8480). A recorded extension of credit (232) can hold the deadline open up to a year. A withdrawal of lis pendens (651) ends the notice of action, not the lien; a partial discharge (291) narrows the notice to less of the property.

`encumbrances` pairs these into lifecycles under `Process.MECHANICS_LIEN`, and the status reads open, in suit, action withdrawn, expired, or closed, with `unenforceable_after` the ninety-day (or one-year) mark. A notice of action names the parties to a suit and no filing code for the claim, so it joins the newest open lifecycle naming either party, a mechanic's lien before a loan.

Three places to look. Against a developer during construction: those liens attached to the land before the units were conveyed, and one that survived a conveyance would follow the unit; the association's record lists them under "Mechanic's liens from construction". Against the association: a lien on the common area, listed with the other liens against the association. Against an owner: work on a unit, listed on the parcel page with the owner's other lifecycles. `jason sync-liens` fetches the filings: a name the passes searched narrowly already has every filing under it, a wide name is narrowed under the mechanic's lien filings, and a name never searched is searched now. The `mechanics_liens` tool lists every lifecycle with its standing.

## Solar leases and the fixture filings

A developer can sell each unit with a share of the building's rooftop solar system, the buyer choosing at closing to purchase the share or lease it. A leased share carries a UCC financing statement (368) the lease fund records against the buyer, naming itself secured party; a termination (372) ends it. When the association keeps no roster of who chose which, the index is the record. The specification names the program in `mystique/solar.py`: the buildings, the lease funds the index prints, and who services the leases now, which is where a lease question goes.

This association's findings are in its private notes (mystique/notes/recorded-instruments.md).

The county indexes a fixture filing by the debtor's name, so `jason sync-solar` searches the funds' names instead and caches every filing they recorded in the county (about four thousand rows), and `solar_record` matches the debtors to each unit's owners. A UCC filing is not only solar: `classify_secured_party` reads the secured party as the program's lessor, another solar lessor (Tesla, SolarCity, Sunnova, Sunrun), a solar lender (Loanpal, GoodLeap, Mosaic), the utility (SMUD's own financing filings), or a bank, in that order. Only the program's lessors decide a unit's standing:

| Standing | Meaning | What escrow does |
| --- | --- | --- |
| lease on current owner | an open filing by a program lessor names the current owner | carry the lease to the buyer with its payments |
| lease on prior owner | an open filing names an earlier owner and none names the current one | ask the lessor whether it transferred or was bought out |
| lease terminated | the filing was terminated, often on the day of a sale | a buyout or transfer at that escrow; the current owner has no filing |
| no filing | no program lessor filing names any owner | purchase is likely, but a filing can be missed or never recorded |
| outside program | a building the program does not cover | nothing to transfer; a solar filing there is the owner's own |

Two bounds. No filing is not proof of purchase. And an owner of several units shows the same filing on each, since the index names the debtor and not the unit; the report says so and cannot pick the unit. The escrow list is `solar.md` in the property history folder, the Solar tab in the spreadsheet, and the `solar_status` tool.

## Governing instruments and 2792.23

`locate_governing` classifies the governing, plan, and map filings and ties each to the delivery it satisfies. A phase is read from a party name such as "<ASSOCIATION> PHASE 3", or from the recording date matching a phase's annexation date on the public reports, since Watt's later annexations name only the developer. `delivery_status` lists, per delivery, what the index holds and what is missing, phase by phase for annexations. Articles are a Secretary of State filing and bylaws are the association's own; neither is expected in the index. The final map is in the map books, not the document index. Plans, bonds, warranties, policies, and contracts are never recorded and stay with the Drive pins.

An instrument the index places by party name or by date is listed under its delivery, with every grant into the association under the common-area deeds. When an instrument's own recital says it rescinded and superseded an earlier one and the index cites nothing for it, the fact is pinned in `mystique/annexations.py` as a `Supersession`, and the record shows the earlier instrument placed with that status.

This association's findings are in its private notes (mystique/notes/recorded-instruments.md).

## What the other official records add

- The assessor's parcel record gives the current instrument and its type; a death record there is not in the recorder's index.
- The tax bills give the reassessment calendar and the delinquency before a tax default records.
- The secured roll gives the mailing address and the owner the county billed, a year behind a sale.
- The Bureau public reports give each phase's issue date, first conveyance, and annexation date, which is what places a developer's annexation.
- The Secretary of State's business search gives an entity's managers and agent, which is how an affiliate transfer is confirmed; its site blocks automated search, so that is a manual check.

## Names, namesakes, and tenure

The index names a person, not a parcel, so a lien joins a unit by its owner's name. Three rules keep that join honest.

- **An initial matches the full name in either direction.** "DOE JOHN Q" on a fixture filing is "DOE JOHN QUINCY" on the deed, whichever of the two was searched. Before this, a filing was missed when the deed's longer form was the one looked up.
- **Tenure is every step the owner holds.** An owner who re-vests the unit, or adds a co-owner, holds two chain steps. A lien recorded during the second is during their ownership, not "another time or property".
- **A dropped middle name is a namesake risk.** When the deed carries a middle name or initial and the filing gives only surname and given name, the lien row's `nameMatch` says so and `namesakeRisk` is set, unless a claimant ties the filing to the unit on its own: the association, the solar program's lessor, or a loan recorded at a closing. A lien on "DOE JOHN" can match an owner John Q. Doe while the release that follows names John Robert Doe. A deed that itself gives only two words cannot be matched more closely, and is not flagged.

A lien with a statutory life reads **lapsed** once that life has run from its newest recording with no renewal in the index: an abstract of judgment after ten years (Code of Civil Procedure 697.310), a state tax lien after ten years (Government Code 7172), a notice of federal tax lien after ten years and thirty days (26 U.S.C. 6323(g)). The statutes count from the judgment's entry or the tax's assessment, which come on or before the recording, so the date Jason gives is the latest the lien could last. A lapsed lien is unenforceable and still of record until released, like an expired mechanic's lien; escrow's line says both. A support judgment has no such life (Family Code 4502) and stays open until the agency releases it.

## Where a lien stands against the title

`jason.community.title` reads each lien joined to a unit as one `LienStanding`, in this order:

| Standing | When |
| --- | --- |
| elsewhere | it names an owner at another time or on another property; another association's assessment lien is always here |
| released | the index holds its release |
| awaiting roll | a utility lien too recent for the stored tax bills; the next bill says whether it moved onto the roll |
| roll paid, on roll | a utility lien whose delinquency the agency moved onto this parcel's secured tax bill (code 0202 for the city, 0411 for the sewer district), within a year of the lien; a paid bill settles it with no termination recorded, an unpaid one is collected with the taxes |
| runs with the land | a special tax or PACE assessment, which passes to each buyer |
| lapsed, expired | past its statutory life, or a mechanic's lien never sued on |
| in default | a default or sale notice on the current owner, the newest step within a year |
| quiet default | the same, with no step for over a year and the owner still on title: cured, reinstated, or abandoned off the index |
| current loan, solar lease | the current owner's loan, or a solar lessor's or lender's fixture filing |
| stands | anything else open on the current owner |
| fixture prior | a prior owner's fixture filing; the solar standing says whether the lease moved |
| stands on prior | a prior owner's lien with no sale since, so it still follows the property |
| release due | the association's own lien on a prior owner, with a sale since and no release: Civil Code 5685(a) gives the association 21 days from payment to record one |
| presumed paid | any other prior owner's lien with a sale since; escrow pays the seller's liens |

A filing on an owner of several units joins each of them; the row names the other units, and only one is charged. The page is `liens.md` among the property-history pages, the tool is `title_watch`, and the command is `jason title-watch`. It is what the index shows, not a title report.

## Standing beyond title

`jason.community.standing` reads two more things per parcel. `tax_standing` reads the bills: the newest year with a balance is due, an older one is delinquent, and the notice of power to sell can follow on the July 1 five years after the first delinquent year (Revenue and Taxation Code section 3691). A year between the first and last bill with no total is a gap, which can be a stretch the county carried the parcel as tax-defaulted before the notice; a later rescission is the redemption. `owner_events` lists the death affidavits, powers of attorney, and homesteads naming an owner, marks whether each fell during that owner's tenure, and flags a decedent who is still a grantee on the newest deed, which is the membership record's cue.

Utility easements on the common areas are often shown on the final map and the condominium plans rather than recorded as separate instruments, so a search of the index under the developers' and the association's names can find none.

This association's findings are in its private notes (mystique/notes/recorded-instruments.md).

## Where it shows

Each parcel's report and the Liens and notices tab list every lifecycle naming one of its owners, marked "this community" for the association's own lien, "while owning here" when it opened during that owner's tenure, or "another time or property" otherwise, since a lien indexes a person and not a parcel. `data/reports/property-history/association.md` and the Governing records tab hold the association's record. Each parcel's report also has a Taxes section and an Owner events section, with the Tax standing and Owner events tabs beside them. The MCP tools are `association_records` and `parcel_liens`.
