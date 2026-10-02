# Pest management

This page covers what the association owes, what the manager keeps, what the vendor must do, and how jason reads the vendor's record. Citations were checked against the primary text on September 29, 2026.

## Who is responsible

**The declaration decides first.** Civil Code 4775, 4780 and 4785 each start with "unless otherwise provided in the declaration."

- **The CC&Rs** say who pays for the wood-destroying pest inspection and preventive program, who repairs common area and unit interiors damaged by those pests, and how owners and occupants are asked to vacate for an eradication.
- **The rules** say whether exterior pest control is a common service and who handles pests inside a unit.

This association's findings are in its private notes (mystique/notes/pest-management.md).

**The statutes behind those clauses:**

- **Civil Code 4775.** The association maintains the common area and each owner maintains the separate interest. For exclusive-use common area (patios, decks), the owner maintains and the association repairs and replaces. Under 4775(c), the owner bears relocation costs while the association repairs.
- **Civil Code 4780(a).** In a condominium, the association repairs and maintains common area damaged by wood-destroying pests.
- **Civil Code 4785.** The association may temporarily remove occupants for wood-destroying pest treatment. Notice goes out 15 to 30 days ahead, by personal delivery or individual delivery (4040), with individual delivery to the owner as well when the occupant is not the owner. Section 4790 is about telephone wiring, not pests.
- **Civil Code 5200.** The contract, the board's approval of the proposal, the invoices, and the service tickets ("statements for services rendered") are association records. Civil Code 5210 opens them to members for the current year and the two before it.

**Who handles a complaint:**

| Where the pest is | Who handles it |
|---|---|
| Common area, building envelope, wood-destroying damage | The association |
| Confined inside a unit (ants, cockroaches, bed bugs) | The owner |
| Inside a unit, but coming from a common-area source (a wall void, the attic, a roof stack) | The association fixes the source |
| A tenant's bed bugs | The landlord-owner (Civil Code 1954.603 and 1954.604) |

## The vendor's license, insurance, and notices

**License and insurance:**

- **Branches.** Structural pest control is licensed by the Structural Pest Control Board in three branches (B&P 8560): fumigation (Branch 1), general pest (Branch 2), and wood-destroying organisms (Branch 3).
- **Insurance.** A registered company files liability insurance of at least $500,000 bodily injury and $500,000 property damage (B&P 8690, 8692).
- **Live removal.** Removing bees, wasps, or other vertebrates alive without pesticide needs no board license, only that insurance (B&P 8555(g)). Rats, mice, and pigeons are not covered by that exemption.
- **Landscapers.** Landscape applicators are licensed by the Department of Pesticide Regulation (FAC 11701, 11704).
- **Verifying.** Check the license at [search.dca.ca.gov](https://search.dca.ca.gov/) under "Structural Pest Control Board" before each contract and renewal. Record the registration, its status, and its branches in `mystique/vendors.py`. A company without Branch 1 cannot do a fumigation. The registration lists its operators and field representatives; check that the technicians who apply are among them.

**Before an application (B&P 8538):**

- **Who gets it.** The vendor gives the owner or owner's agent, and the tenant, a notice.
- **What it says.**
  - the pest;
  - the pesticides and active ingredients;
  - the statutory caution statement;
  - the flu-like-symptoms warning;
  - Poison Control's number (1-800-222-1222);
  - the numbers of the company, the county health department, the agricultural commissioner, and the board;
  - the frequency, under a periodic contract.
- **When.** Under a periodic contract, the notice comes at the first treatment and again whenever a pesticide changes.
- **Where it's posted.** For exterior service at a multi-unit property, a posted notice goes in heavily frequented common areas, including all multi-unit mailboxes (16 CCR 1970.41, operative 2025).

**After an application (16 CCR 1970.42, operative 2025):**

- **Content.** Every visit gets a written notice of each pesticide, the date, and the company. A door hanger or invoice counts.
- **Right to ask.** For three years, anyone may ask the company which pesticides it applied and get an answer within 24 hours.
- **SDS.** No statute found gives a right to the safety data sheet itself. Ask for the sheets in the contract; UC IPM tells managers to keep them.

**Other vendor duties:**

- **Use reports.** The company files a monthly report of every pesticide it uses in the county with the agricultural commissioner (B&P 8505.17(c)). The association can ask for copies.
- **Inspection reports.** Only a Branch 3 inspector reports on wood-destroying organisms (B&P 8516). The report goes to the owner within 10 business days, separated into Section I (active infestation or damage) and Section II (conditions likely to lead to it) on request.
  - A control service agreement is in writing. It lists the pests and buildings covered, frequency, fees, and whether repairs are included, with a full re-inspection at least every three years.
  - On a unit sale, the seller hands over the report only when the contract or loan requires one (Civil Code 1099).
- **Fumigation.**
  - It needs a Branch 1 operator, a signed occupant disclosure form (16 CCR 1970.4), vacancy until declared safe (B&P 8505.7), and "DANGER—FUMIGATION" signs.
  - The association's own 15-to-30-day notice under Civil Code 4785 and the declaration still applies.
- **A death or serious injury.** The vendor must report it immediately to the board and the agricultural commissioner (16 CCR 1970.43).

## California rules on the products

- **Pyrethroids outdoors (3 CCR 6970).** The rule covers bifenthrin, lambda-cyhalothrin, deltamethrin, alpha-cypermethrin, and others, applied for hire at residences.
  - **Pavement, walks, windows and doors:** only spot, crack-and-crevice, or a pin stream of an inch or less.
  - **Walls:** a perimeter band up to 2 feet high.
  - **Soil, turf and mulch:** a band up to 3 feet.
  - **Prohibited:** application during rain (except under eaves), and application to standing water, storm drains, gutters, or drain grates.
  - **Exempt (3 CCR 6972):** baits in weatherproof stations and the undersides of eaves.
- **Neonicotinoids (FAC 12838(c)(2), from AB 363, since January 1, 2025).** Dinotefuran and imidacloprid may be used on non-production outdoor ornamental plants, trees, and turf only by state-certified applicators. The text does not plainly reach a structural perimeter treatment. Whether a Structural Pest Control Board licensee counts as a certified applicator is unsettled. DPR's reevaluation is due by July 1, 2027.
- **Rodenticides (FAC 12978.7, as amended by AB 2552).**
  - Banned at residences: second-generation anticoagulants, diphacinone, chlorophacinone, and warfarin.
  - Cholecalciferol (Selontra) is not an anticoagulant, so the statute does not reach it. That reading comes from the statute's definitions; DPR does not address it directly. Its label still governs.
- **The label is the law (7 U.S.C. 136j(a)(2)(G)).**

## Integrated pest management

The state's own definition of structural integrated pest management is long-term prevention with the least harm (16 CCR 1984). It rests on correct identification, monitoring, and physical and cultural controls ahead of chemical ones.

UC IPM's [Guide for Property Managers](https://ipm.ucanr.edu/home-and-landscape/guide-for-property-managers/) asks the manager to:

- choose a vendor by request for proposal, not lowest bid, and prefer one that does not spray on a calendar;
- have the vendor report conditions that invite pests;
- keep a logbook of every service, complaint, inspection, and safety data sheet;
- inspect the whole property at the start, and each unit yearly.

An integrated contract would:

1. Keep monitoring stations on a site map, with written action thresholds.
2. Treat on documented activity rather than by the calendar.
3. Put exclusion and sanitation first.
4. Keep baits in tamper-resistant stations.
5. Stay within the pyrethroid and neonicotinoid limits.
6. Send a conditions report after each visit.
7. Give the notices and safety data sheets to the manager.
8. Keep the license and insurance current.

## Sacramento services and emergencies

- **Sacramento-Yolo Mosquito & Vector Control District** ([fightthebite.net](https://www.fightthebite.net/services/request-service/), 800-429-1022).
  - It treats yellowjacket and paper-wasp nests in the ground or trees at no charge. It does not treat nests inside a structure or high on a multi-story building.
  - It also handles standing water and mosquitofish.
  - For dead birds, call 1-877-968-2473.
- **Honey bees.** Use a live-removal vendor.
- **Suspected pesticide exposure.**
  - Call 911 in an emergency.
  - Otherwise call Poison Control at 1-800-222-1222.
  - Report it to the agricultural commissioner at 1-87-PESTLINE (1-877-378-5463). The Sacramento County Agricultural Commissioner's pesticide use enforcement office is at 916-875-6603.

## Each product by its registration number

```bash
jason pests --fetch     # registrations, labels, and safety data sheets for every product the vendor applied
```

**Registration numbers.** EPA's number is `firm-product`. A distributor's label adds a numeric suffix. California adds a two-letter revision code for each brand it registers: `499-561-ZA` is Alpine WSG in California, and `-AA` is the first brand registered. `EpaNumber` keeps EPA's key and California's number apart. A FIFRA 25(b) minimum-risk product, recorded as "EPA EXEMPT", has no EPA record.

**Sources.** Each is public and needs no key.

- **EPA's registration.** [PPLS](https://ordspub.epa.gov/ords/pesticides/cswu/ppls/499-561) gives the registrant, status, signal word, restricted-use flag, and active ingredients. It also gives the newest label EPA stamped as accepted. Sort the labels by accepted date, not file name, because a transferred product keeps the old number in its file names.
- **California's registration.** CalPEST shows whether the registration the vendor recorded is active in California.
- **Safety data sheet and specimen label.**
  - For BASF, Syngenta, Envu, and MGK products, they come from CDMS's library. One EPA number can list two products there, such as Termidor SC and Termidor NY, so the sheet is kept only when it names the vendor's product.
  - Control Solutions (Bifen, Dominion) and Zoecon (Essentria) post their own sheets.

**Where the files go.** They land under `data/pesticides/<EPA key>/`. `product.json` holds both registrations, the document sources, and the SDS reading.

**What the label and the SDS are for.**
- **The label governs use:** directions, restrictions, re-entry, and water.
- **The SDS carries what a label cannot:**
  - Section 2: the GHS signal word and hazard statements;
  - Section 4: first aid;
  - Section 11: toxicology;
  - Section 12: ecology;
  - Section 15: Proposition 65.
- **The two signal words can differ.** Suspend PolyZone's label says Caution and its SDS says Warning.
- **GHS classification covers the workplace.** Selontra's SDS is "not classified" under GHS. Its label still warns that a pet can be poisoned, and requires tamper-resistant stations where children or pets can reach.

## What jason checks against the labels

`pesticide_facts.py` holds each ingredient's class, hazards, bee and aquatic concern, and California rule, each with its source. It also holds the limits jason can test against the vendor's application record:

- **Termidor SC in California.** Only the 0.03% dilution (0.4 fl oz per gallon), 4 applications a calendar year, at least 60 days apart, and none from November 1 to February 28. Source: the EPA-stamped label of August 15, 2023, "Additional California Specific Use Restrictions."
  - The interval and yearly count are tested per building when the visit note names the buildings.
  - A short gap with no buildings recorded is a question, not a finding, since it may be two halves of the property.
  - A row with no volume applied is ignored.
  - A lower strength than the label's is not flagged, since a label rate is a maximum.
- **Neonicotinoids on landscape areas since 2025.** An application of dinotefuran or imidacloprid that lists landscape or yard areas since January 1, 2025 raises a question. Were ornamental plants, trees, or turf treated, and by a technician with an Operator or Field Representative license (FAC 12838(c)(2))?

What the record cannot show stays with the vendor:

- the band width and whether it rained (3 CCR 6970);
- where the bait stations are and whether they are anchored;
- the notices under B&P 8538 and 16 CCR 1970.41 and 1970.42.

Questions worth putting to the vendor:

1. Please send the application records and the monthly use reports filed with the county.
2. How is Termidor scheduled to keep 60 days between treatments of the same building?
3. How do technicians meet the pyrethroid band and rain limits? Does 6970 apply to Fendona CS?
4. Are Alpine or Dominion applied to plants, trees, or turf, and by whom?
5. Could treatment be triggered by inspection rather than the calendar, with exclusion first, using the entry points the last rodent-proofing report found?
6. Where are the Selontra stations, and how are dead rodents collected?
7. Which notices are posted at the mailboxes, and which are left after each visit?

## How jason reads the vendor

`jason vendors --sync` saves ProActive's portal record (see [vendor-portals.md](vendor-portals.md)). `jason pests` reads it:

- **Products.** Each product applied, by EPA registration number, with its active ingredient, amounts, methods, areas, targets, and years.
- **Visits.** Each technician's note, read into the buildings serviced, whether the bait stations were checked and refilled, the rodent activity rating, and the pests named.
- **Inspection reports.** The vendor's inspection reports and their quotes.

The `pest_program` tool serves the same brief. The duty is in the registry as "Pest control" (`duty_brief`).
