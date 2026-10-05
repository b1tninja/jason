# Maintenance history and insurance claims by unit and building

`jason incidents` reads the association's repair paperwork and lists what was done where, and which events carried an insurance claim. It groups the paperwork into events and places them on units (street addresses) and buildings. This is historical analysis for the board: which units keep leaking, which buildings need a closer look, what each event cost, and which events went to the insurer. An event is a rule's reading of the paperwork, not a finding. A person reads the documents before an event is cited.

## Two answers, kept apart

- **The work: the maintenance history.** Every event records what the association had done: `repair`, `maintenance`, `improvement`, or `inspection` (a claim letter by itself is no work).
  - The work is read from the paperwork's words. A service contract that lists the perils its scope covers ("storm damaged plants, vandalism") is maintenance.
  - A maintenance vendor's calls are maintenance by rule (`VendorWork` in `mystique/incidents.py`). For example, a roof repair vendor's leak calls on roofs and gutters are roof maintenance.
- **The claim: the insurance angle.**
  - How serious an event was is not guessed from its words, since the line between upkeep and a loss is murky. An event is `claimed` when its paperwork ties it to an insurance claim: a claim number, a claim letter or outcome, an adjuster, a statement or date of loss, or proof of loss. Its claim numbers are listed.
  - An event whose paperwork names a sudden cause (a leak, a burst or broken line, a collision, a fire, a fallen tree) and has no claim on file is marked `sudden, no claim`. That is an event a claim could have been asked about. Whether a peril was covered is the insurer's answer, not the history's.
  - A vendor rule changes the work only. A claim on a maintenance vendor's leak is still a claim.

**The deductible.** The master policy's deductible, $10,000 per occurrence (`deductible_cents` on the master policy in `mystique/insurance.py`), is the least loss worth a claim: below it the carrier pays nothing. Each event carries the cost its paperwork puts on it and a standing against the deductible (`ClaimStanding`):

- **Claimed.**
- **Claim candidate:** a sudden cause, no claim on file, and a cost that reaches the deductible.
- **Under deductible:** a sudden cause, and a known cost below the deductible.
- **Sudden, cost unknown:** a sudden cause, and no amount on the paperwork.
- **None:** upkeep, improvements, and inspections.

An event's cost is its largest single figure (a quote, an invoice, a payment, or a carrier's figure), not a sum, since a month of small repairs is not one loss. For a claimed loss with no carrier settlement on file, the distinct figures of the claim's own estimates add up (the repair and the water mitigation). The cost is the paperwork's, not the loss's: interior damage an owner paid for may not be in it.

The cause (roof leak, plumbing leak or overflow, irrigation break, vehicle collision, ...) and the element (roof, gutters, unit interior, garage door, ...) say what happened and to what. They describe; they do not classify.

## Sources

| Channel | What is read | Where |
|---|---|---|
| PayHOA | each payment's attachments, with the payment's day, amount, payee, category, memo, and the unit PayHOA tagged; a repair-category payment with nothing attached is read by its own words | `data/payhoa/transactions.json` and the invoice review's text cache |
| Email | the attachments `jason gmail --files` saved, with each message's subject | `data/gmail/files` |
| Library | the PayHOA library's proposals, contracts, invoices, inspection reports, and notices | `data/library` |
| Drive | the folders and loose files `mystique/incidents.py` names, fetched by `jason incidents --fetch` | `data/drive/evidence` (index `data/drive/evidence.json`) |

A file held in several channels is read once, by content hash. The PayHOA copy is kept first because it carries the payment. Scans and glyph-coded PDFs are read by OCR (their first six pages), cached by hash under `data/documents/incident-text`.

**Kept out:**
- A legal case's medical and veterinary records are never downloaded or read (the plan's `private_names`). The same names are skipped in email.
- The security patrol's daily reports are left for their own reader.
- A document whose name or first page shows it is not repair paperwork is left out: lender questionnaires, escrow instructions, budgets and disclosures, insurance policies and proposals, violation notices, demand requests, and brochures.
- A counterparty that is not a trade (an insurer, bank, law firm, accountant, title company, or manager, by `mystique/senders.py`) counts only through a claim.

## Reading one document

`jason.community.incidents.read_evidence` reads a document's scope and problem lines. Its terms, warranties, disclaimers, lien notices, and exclusions are dropped first, so "not responsible for mold" and "excluding vandalism" are not read as work.

- **Cause and element.** Rule rows. Every matching row counts, but a roof leak or plumbing leak is not also counted as generic water intrusion.
- **Stage.** Claim, report, proposal, contract, change order, invoice, notice, or photos, read from the file name first.
- **Places.**
  - A unit is its street address on the development's five streets. Its building comes from the building table, or, for an end unit addressed on the cross street, from its parcel's assessor block (`Mystique.unit_blocks()`, from the stored tax roll).
  - The association's site address, and the variants the policies and vendors print, mean the whole community.
  - A bill-to or ship-to address never places the work: it is the payer's home or where the parts went.
  - A street number that is no parcel (a typo, or a project number) places nothing.
- **Amount and date.** The largest labeled total, and the invoice date or the first date on the page, else the date in the file name ("<Association> - 230222 - ...", "20220808", "(9.4.26)"), else the copy's date.

## Claim papers and loss runs

A document that reads as a claim paper is read again by its document model ([document-models/insurance-claims.md](document-models/insurance-claims.md)). Its claim number, date of loss, outcome (settlement, denial, closed for no contact, primacy), and payment go onto its evidence. A letter dated months after a loss is placed on the loss's date.

A carrier's loss run becomes one piece of evidence per claim it details: number, date of loss, cause, location, the carrier's status, and what it paid. A location spanning the whole street ("100-198 Main St") places the claim on the community, not on its two end units.

Claim numbers are compared by their base. Some carriers add feature suffixes (5021000019-1, 5021000019-1-1), and others a line number (030200001-002).

### A claim on another's policy

Some claim papers in an association's records are on an owner's own homeowner policy, not the association's: the owner's insurer's estimate, authorization, letter, or payment, or a letter deferring to the master policy. Each claim reading carries a `Policyholder` (`ASSOCIATION`, `OTHER`, or `UNKNOWN`; the rules are in [document-models/insurance-claims.md](document-models/insurance-claims.md)), and a paper on another's policy is marked on its evidence (`claim_of`, `claimOf` in the JSON).

An owner's insurer's claim is not the association's, so the history keeps it apart:

- **Claimed.** The event's `claimed`, `standing`, and `routine` count only the association's papers. An event with only another's claim is not `claimed`: a sudden cause with a cost that reaches the deductible stays a `claim candidate`.
- **Cost.** A paper on another's policy puts none of its figures (its estimate, its paid amount) on the event's `costCents`: they are the other policy's loss, not the association's.
- **Marks.** The event lists the claims with such a paper in `otherInsurerClaims`, and `claimOutcomes` marks each paper's `policyholder`. The text report marks the event `OWNER-INS` and names the claim ("on another's policy"), and the report carries a note. `--claims` and `--link` still take the event: the insurer's involvement in a loss is a lead worth a person's deeper analysis (whether the loss touches the master policy or a common area, how a deductible falls under the governing documents, whether the insurer may look to the association). It is a lead, not a determination.
- **Grouping is unchanged.** The papers still join their loss's event by claim number, unit, and date, so the lead stands beside the association's own paperwork.
- **A shared number.** A claim number two policies' papers print (a program contractor's form beside the association's carrier's letter) is listed once, and each paper stands by what it says: only the paper on another's policy is left out of the claimed and cost figures.

Events with no such paper read exactly as before.

## Grouping into events

Claim papers are grouped first (`claim_seeds`):

1. One group is formed per claim number.
2. Groups for one loss are merged: the same day of loss (within three days), at the same unit or at no unit. This joins the owner's and the association's claims, and a loss run's number with the carrier's letter number for the same claim.
3. Every other document then joins these seeds or other events.

Two different claims never merge otherwise. Routine upkeep joins a claim only through the claim's own unit.

`group_events` joins a document to an earlier event in any of these cases:

- **Same file, payment, or claim.** It is the same file, the same PayHOA payment, or the same claim number.
- **Same unit within weeks.** It is the same unit within 45 days of a claimed or sudden event. The police report, the contractor's proposal, and the reimbursement notice share an address and dates, not always a word.
- **Same unit, vendor, and period.** It is the same vendor at the same unit, within 150 days.
- **Shared cause or element.** The place overlaps (unit, else building, else both community-wide), the dates are within 150 days, and the documents share a cause or an element. Without a unit on both sides, they need a shared cause or the same vendor.

Two limits:

- **Anchor places.** A later document is matched against the event's first document's places, so one invoice listing five addresses does not chain five units together.
- **Splitting and span.** A document naming more than three units is split into one row per unit. A community-wide event spans at most 150 days.

An event reports:

- its dates, works, whether it is claimed, sudden, or routine, and its causes, elements, units, buildings, and vendors;
- the largest quoted amount, the invoiced amount not yet matched to a payment, and the PayHOA payments;
- claim numbers;
- each document with a snippet. Email addresses and phone numbers are masked, and a claim file's snippet is held back unless `--private` is given.

## Related documents (`--link`)

`jason incidents --link` (`jason.tasks.incident_links`) searches for each claimed or sudden-cause event, and each unit repair, from what the event knows: its claim numbers, units, buildings, vendors, and dates (30 days before to 150 after).

| Store | Search |
|---|---|
| Drive (read-only API) | full text for each claim number, and each unit's address beside "claim", "leak", "damage", or "repair" |
| Gmail (read-only API) | the message search for each claim number, and each address with a claim or repair word inside the dates; headers and attachment names only, never a body |
| stored email headers and attachments | subjects and file names carrying a key |
| stored PayHOA ledger | entries inside the dates naming the unit or one of the event's vendors |
| library text | minutes, agendas, notices, and resolutions naming the unit or a claim |
| stored mail | letters naming a claim number |

Each hit keeps the reason it matched (`data/reports/incident-links.json`). New results are fetched as linked evidence, and the history is read again:

- a Drive hit is fetched into `data/drive/evidence`, unless it sits in a folder about people (registrations, collections, discipline);
- a Gmail hit's PDF attachments are saved beside the synced email attachments.

Medical and veterinary file names are never fetched. `jason incidents --links` prints the stored links; `--address` narrows them to one event.

## Use

Copy each command on its own:

```bash
jason incidents --fetch
```

```bash
jason incidents --building 8
```

```bash
jason incidents --address "123 Main" --all
```

```bash
jason incidents --claims --private
```

```bash
jason incidents --standing "claim candidate"
```

```bash
jason incidents --work maintenance
```

```bash
jason incidents --cause "roof leak" --since 2024-01-01
```

```bash
jason incidents --stored --json
```

- By default the list leaves out routine events: upkeep and inspections with no claim and no sudden cause. `--all` or `--work` brings them back.
- The MCP tool `incident_history` (board profile) reads the stored report with the same filters (`work`, `claims_only`, `include_routine`).
- Nothing is sent, moved, or changed anywhere.

## Findings

This association's findings are in its private notes (mystique/notes/incidents.md).

## Limits

- **Old payments.** Payments before January 2024 are not in the stored ledger, so the prior manager's work shows its paperwork without its payment.
- **Large files.** A photo set or report over 25 MB is not fetched; its report or invoice usually carries the facts.
- **OCR.** OCR can misread an amount or an address. The snippet and the document are the check.
- **Words only.**
  - An event the paperwork never describes (a leak reported only by phone) is not here.
  - A claim the association's paperwork never mentions is not marked.
  - The minutes and email bodies are not read yet.
- **Duplicate copies.** The same invoice kept twice in Drive can date differently: an archive copy by its name, a loose copy by Drive's modified date. It can show as two events years apart; one unit's 2022 plumbing leak shows again in 2024.
- **Panel addresses.** A fire alarm or backflow test places its work at the panel's address, which is the building's, not that unit's.
