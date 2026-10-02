# Insurance claim papers

Six kinds, read by `jason.community.models.insurance_claims`. No Davis-Stirling section shapes them; the policy does. The master policy covers the buildings. An owner's HO-6 policy covers the unit's contents and improvements, and the deductible the declaration may shift to the owner. The models feed the incident history (`jason incidents`, [../incidents.md](../incidents.md)): a claim paper's number, date of loss, outcome, and payment go onto its evidence, so a letter written months after a loss joins that loss's event. Whether a peril was covered is the carrier's answer.

Every kind is confidential in the library (`CONFIDENTIAL_KINDS`). A claim paper names owners, policyholders, and adjusters, and a police report names drivers. A record keeps no person's name except the carrier's and the program contractor's.

| Kind | Model | Reads | Checks |
|---|---|---|---|
| `loss_run` | `loss-run` | the carrier's Claim Summary and Claim Detail reports: policy, valuation date, period, and each claim's number, date of loss, status, type, cause, location, losses paid, and expenses | each claim listed; no claims in the period; a run valued more than a year ago (lenders and renewals ask for a current one) |
| `claim_letter` | `claim-letter` | a carrier's letter on one claim: claim and policy numbers, whether the association is the insured, loss date and location, the letter type (acknowledgment, status, settlement, denial or disclaimer, closed for no contact, primacy, reservation of rights), the settlement table, the program contractor, and a disclaimer's cancellation date | a disclaimer because the policy had ended before the loss (the claim belongs with the master carrier in force that day, named from `Mystique.insurance()`); a denial; a claim closed for no contact (the policy's conditions set how long it can be reopened); a reservation of rights (for counsel); an owner's carrier deferring to the master policy; a settlement paid to a program contractor |
| `claim_payment` | `claim-payment` | a statement of loss (net loss, deductible, depreciation, net claim at ACV) and a claim check (number, issue date, amount, date of loss) | depreciation held back (recoverable once the repairs are done); the check's deposit in the stored ledger within 60 days, or its absence |
| `claim_authorization` | `claim-authorization` | a program contractor's work authorization, certificate of satisfaction, or project tracker: claim, date of loss, carrier (typed into a blank), address, and signing date | the carrier pays the contractor directly and the deductible stays the insured's; a certificate of satisfaction means the repairs were accepted |
| `claim_estimate` | `claim-estimate` | a carrier's or its vendor's estimate (Xactimate layout): claim, type of loss, date of loss, RCV, depreciation, ACV, deductible, net claim; whether it is a water-mitigation (dry-out) estimate | an estimate within the deductible |
| `police_report` | `police-report` | the report number, the agency, the date, and the development address only | none |

Carrier names come from the letterhead (`carrier_of`): Farmers (including Truck Insurance Exchange and Fire Insurance Exchange), USAA (Garrison Property and Casualty), Accelerant, AAA, Athens, MG Skinner, McGowan, and Philadelphia. The name rules in `mystique/documents.py` come before the proposal and invoice rules. "ESTIMATE FOR REPAIRS 5021000019-1" is the carrier's estimate, not a vendor's.

Mystique's findings are in the private notes (mystique/notes/document-models/insurance-claims.md).

## Manager case reports

`manager_case_report` (`jason.community.models.manager_reports`, model `manager-case-report`) reads the prior manager's weekly "Case Performance" report (The Helsing Group, 2023): the report's date and its "Cases Currently Open", one row per case with its number, subject, and type. It reads both text layouts, one field per line or one row per line. `jason incidents --link` saves every such report from Gmail (subject "Helsing Report", the Case Performance PDF). The history reads each open case whose subject names a unit, a claim, or work as one piece of evidence per case number, however many weekly reports carry it.

The subjects are sometimes the only record that ties a claim or a repair to a unit. A subject of the form "<unit address> - Claim No. <number>, Claim Outcome Letter" places on one unit a claim the loss run gives only as a range of addresses; "<unit address> - Roof Leak" adds a leak to that unit's building. A subject with no address ("Water Leak from Exterior") is evidence of work, not of a place.

Tests: `tests/test_models_claims.py`, on made-up claims and cases.
