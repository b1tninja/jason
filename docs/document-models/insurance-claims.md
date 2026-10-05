# Insurance claim papers

Six kinds, read by `jason.community.models.insurance_claims`. No Davis-Stirling section shapes them; the policy does. The master policy covers the buildings. An owner's HO-6 policy covers the unit's contents and improvements, and the deductible the declaration may shift to the owner. The models feed the incident history (`jason incidents`, [../incidents.md](../incidents.md)): a claim paper's number, date of loss, outcome, and payment go onto its evidence, so a letter written months after a loss joins that loss's event. Whether a peril was covered is the carrier's answer.

Every kind is confidential in the library (`CONFIDENTIAL_KINDS`). A claim paper names owners, policyholders, and adjusters, and a police report names drivers. A record keeps no person's name except the carrier's and the program contractor's.

| Kind | Model | Reads | Checks |
|---|---|---|---|
| `loss_run` | `loss-run` | the carrier's Claim Summary and Claim Detail reports: policy, valuation date, period, and each claim's number, date of loss, status, type, cause, location, losses paid, and expenses | each claim listed; no claims in the period; a run valued more than a year ago (lenders and renewals ask for a current one) |
| `claim_letter` | `claim-letter` | a carrier's letter on one claim: claim and policy numbers, whether the association is the insured, loss date and location, the letter type (acknowledgment, status, settlement, denial or disclaimer, closed for no contact, primacy, reservation of rights), the settlement table, the program contractor, and a disclaimer's cancellation date | a disclaimer because the policy had ended before the loss (the claim belongs with the master carrier in force that day, named from `Mystique.insurance()`); a denial; a claim closed for no contact (the policy's conditions set how long it can be reopened); a reservation of rights (for counsel); an owner's carrier deferring to the master policy; a letter on another's policy (below); a settlement paid to a program contractor |
| `claim_payment` | `claim-payment` | a statement of loss (net loss, deductible, depreciation, net claim at ACV) and a claim check (number, issue date, amount, date of loss) | depreciation held back (recoverable once the repairs are done); the check's deposit in the stored ledger within 60 days, or its absence |
| `claim_authorization` | `claim-authorization` | a program contractor's work authorization, certificate of satisfaction, or project tracker: claim, date of loss, carrier (typed into a blank), address, and signing date | the carrier pays the contractor directly and the deductible stays the insured's; a certificate of satisfaction means the repairs were accepted |
| `claim_estimate` | `claim-estimate` | a carrier's or its vendor's estimate (Xactimate layout): claim, type of loss, date of loss, RCV, depreciation, ACV, deductible, net claim; whether it is a water-mitigation (dry-out) estimate | an estimate within the deductible |
| `police_report` | `police-report` | the report number, the agency, the date, and the development address only | none |

Carrier names come from the letterhead (`carrier_of`): its list of carriers, their underwriting companies, program administrators, and claims administrators, each with the words its letterhead prints. The name rules in `mystique/documents.py` come before the proposal and invoice rules. "ESTIMATE FOR REPAIRS 5021000019-1" is the carrier's estimate, not a vendor's.

## Whose policy a paper is on

A letter, payment, estimate, or authorization carries a `Policyholder`: `ASSOCIATION`, `OTHER` (another's policy: an owner's own homeowner policy), or `UNKNOWN`. `policyholder_of` decides by rule, in this order, and never by a carrier's name alone:

1. **The carrier or program is in the insurance record** (`Community.insurance()`), or a directory row says it writes the association's policies: the association's.
2. **The paper prints a policy number the insurance record lists** (a prior term's too): the association's.
3. **The carrier is in the sender directory with its row's `holder` set to `Policyholder.OTHER`:** another's. The row's `role` says what it is ("an owner's own insurer on homeowner claims").
4. **The paper says it is the owner's carrier writing** (a primacy letter): another's.
5. **A letter names the association as the insured:** the association's.
6. **A letter that does not name the association as the insured prints a policy number the specification does not list:** another's.

Anything else is `UNKNOWN`. A directory row with no `holder` is `UNKNOWN`: a name in the directory does not say whose policy a paper is on, since the association's prior carrier and its claims administrator are listed beside an owner's insurer. A person who knows sets the row's `holder` in the profile (`mystique/senders.py`).

A paper on another's policy carries the finding `owner-carrier-paper` (CHECK): it names the carrier, says the paper is on that policy and not the association's, names the association's carriers from the specification, and says that whether the loss touches the master policy or a common area, how a deductible falls under the governing documents, or whether the insurer may look to the association is for a person to analyze. It is a lead, not a determination. A primacy letter already says it is the owner's carrier; it keeps its one finding, `owner-carrier-defers`, raised from INFO to CHECK with the same lead. Every other finding, and every paper on the association's policy, reads as it did.

The incident history keeps such a paper apart from the association's claim and recovery ([../incidents.md](../incidents.md)).

This association's findings are in its private notes (mystique/notes/document-models/insurance-claims.md).

## Manager case reports

`manager_case_report` (`jason.community.models.manager_reports`, model `manager-case-report`) reads a manager's weekly "Case Performance" report (its `manager` is the sender of kind `MANAGER` the report names): the report's date and its "Cases Currently Open", one row per case with its number, subject, and type. It reads both text layouts, one field per line or one row per line. `jason incidents --link` saves every such report from Gmail (the Case Performance PDFs the specification's `EvidencePlan.case_report_query` finds; with no query, none). The history reads each open case whose subject names a unit, a claim, or work as one piece of evidence per case number, however many weekly reports carry it.

The subjects are sometimes the only record that ties a claim or a repair to a unit. A subject of the form "<unit address> - Claim No. <number>, Claim Outcome Letter" places on one unit a claim the loss run gives only as a range of addresses; "<unit address> - Roof Leak" adds a leak to that unit's building. A subject with no address ("Water Leak from Exterior") is evidence of work, not of a place.

Tests: `tests/test_models_claims.py`, on made-up claims and cases.
