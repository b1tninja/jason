# The developer's securities to the association

When a phase is sold under a Department of Real Estate (DRE) public report, the subdivider secures its obligations to the association. It uses the Real Estate Commissioner's forms, and an escrow holder keeps the security. Each is also a delivery the subdivider owed the association: "any bond or other security device" naming it as beneficiary (10 CCR 2792.23(a)(10)).

## The three securities

| Security | What it secures | Law | Forms | How it ends |
|---|---|---|---|---|
| **Assessment** | The subdivider's regular and special assessments on its unsold units, which assessments start at a phase's first conveyance (10 CCR 2792.16) | 10 CCR 2792.9; ordinarily six months of assessments | RE 643 agreement and escrow instructions; RE 643J bond | Held until 80% of the phase's interests are conveyed. The subdivider demands release and certifies it has paid and that 80% has closed; the association has 40 days to object in writing (2792.9(b)(4)(A)). If the subdivider is delinquent, an association officer certifies it and the subdivider has 40 days to object ((b)(4)(B)). |
| **Subsidy** | The subdivider's promise to pay part of the owners' share of costs: the gap between the budgeted assessment and the one it wants buyers to pay | 10 CCR 2792.10 | The subsidy agreement; RE 643E agreement; RE 643K bond | The term the subsidy agreement sets. The subdivider delivers a monthly accounting, and release follows its statement of full performance with the same 40-day objection window. |
| **Completion** | Lien-free completion of the common-area improvements in the planned construction statement, when they are not complete at the first sale | B&P 11018.5(a)(2); 10 CCR 2792.4 | RE 611A planned construction statement; RE 613 agreement; RE 611 bond | If no notice of completion is recorded within 60 days of the completion date (or 30 days after an extension), the board must consider enforcement. 5% of the non-declarant voting power may petition for a special meeting 35 to 45 days out (10 CCR 2792.4; CC&R 3.7). A suit on the bond is due within two years of the completion date (RE 611). |

Research found no Civil Code section of its own on releasing a bond. A release is a board action at a noticed open meeting (CIV 4930), recorded in the minutes (5200(a)(8)), and joined in writing with the escrow holder. The DRE has no part in it.

**Records to keep for each phase and security:**
- the agreement and escrow instructions;
- the bond with its riders;
- any extensions, with the surety's consent;
- notices of completion;
- every demand, objection, and joint instruction, with its delivery date, since that date starts the 40-day clock;
- the resolution and minutes;
- the subsidy accountings;
- the ledger of the developer's assessments;
- proof that 80% of the phase closed.

## What jason reads

**The documents:** the developer-security documents saved from Drive, in `data/developer-security`, each with its text beside it. They include:
- each subdivider's security and subsidy agreements and bonds;
- the escrow holders' and title companies' release letters;
- the board's release resolutions;
- a developer's response to a 2792.23 demand, which can be one long production that `split_instruments` cuts into its instruments.

**The kinds and models:** there are four new document kinds (`security_agreement`, `subsidy_agreement`, `surety_bond`, `bond_release`), with their models in `jason.community.models.developer_security`.

**The register:** `jason securities` and the `developer_securities` MCP tool join everything by phase: the DRE file number, the building, the agreements by type, the bonds, and the releases that name each bond.
- A bond's phase comes from its heading. When the heading has none, it comes from the one security agreement that states the bond's exact sum, marked `*`.
- Copies that read differently are flagged rather than reconciled.

Mystique's findings are in the private notes (mystique/notes/developer-securities.md).
