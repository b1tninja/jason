# Community manager reference

Jason is a virtual agent for a community manager of a California common interest development. This page is the index of duties and the statutes those duties sit on. It is not legal advice, and it is not a substitute for the current code or for the association's governing documents.

The obligation index is [docs/laws/README.md](laws/README.md). Official section text comes from lawlibrary over `US-CA`. Sacramento ordinances are not in that index. Read the live section on [leginfo](https://leginfo.legislature.ca.gov/) only when the publication has no row. Section numbers below were checked against the 2025 session. On 2026-09-27, lawlibrary returned Civil Code §§ 4145, 4600–4620, and 5380, and Business and Professions Code §§ 10131, 10131.01, 10145, 11004.5, 11010.2, 11018.5, 11018.6, and 11500–11506, from that session. The Commissioner’s regulations are not in that index. The regulation numbers below are from the Bureau of Real Estate Law compilation at `dre.ca.gov/files/pdf/relaw/regs.pdf`. Do not quote a section from this page. Quote the official text, or the governing-document body when the file is in hand.

## What a manager does

A manager acts in an advisory capacity, at the direction of the board. Corporations Code § 7210 lets a board delegate management to a person or management company. The board keeps ultimate direction of the corporation’s activities and powers.

Business and Professions Code § 11500(d) names the management services that definition covers:

- Collect, report, and archive the association’s financial and common-area assets, at the board’s direction.
- Carry out board resolutions and directives.
- Carry out the governing documents.
- Administer association contracts, including insurance contracts, and the association’s vendors.

Business and Professions Code § 11501 says an individual may not be required to hold a real estate license in order to perform those services for an association. That sentence does not cancel a license some other statute requires. Selling, leasing, or collecting rents for compensation is still a broker act under § 10131. The narrow exceptions in § 10131.01 cover a resident manager, transient occupancy, and specified unlicensed employees of an apartment property-management firm working under a broker. They are not a general exemption for an association manager who leases units or collects rent.

Using the title “certified common interest development manager” requires the education and exam in §§ 11502 and 11502.5. Certification is of a person, not of a management firm (§ 11503). It is an unfair business practice to use that title without meeting § 11502, to claim a government agency licensed the person as a certified manager, or to skip a disclosure § 11504 or Civil Code § 5375 requires (§ 11505).

Jason prepares, compares, and drafts. Jason does not approve or deny architectural requests, does not record a lien or start a foreclosure, and does not send an account to a collection agency.

## Definitions

These words are Davis-Stirling definitions (Civil Code §§ 4075–4190) unless noted. Use the statute’s word in models.

| Term | Section | Meaning for a model |
| --- | --- | --- |
| Common interest development | § 4100 | The statutory umbrella. A condominium project is one form (§ 4125). A planned development is another (§ 4175). |
| Association | § 4080 | The nonprofit entity that manages the development. |
| Board | § 4085 | The body that directs the association. |
| Member | § 4160 | An owner of a separate interest. |
| Separate interest | § 4185 | The unit or lot the member owns. In a condominium, the unit. |
| Common area | § 4095 | Property owned or maintained in common. |
| Exclusive use common area | § 4145 | Common area the declaration designates for one or more, but fewer than all, of the owners, appurtenant to those separate interests. Unless the declaration says otherwise, fixtures that serve a single separate interest and sit outside its boundaries are exclusive use allocated to that interest, including balconies, patios, and exterior doors. Telephone wiring that serves one separate interest is exclusive use even if the declaration says otherwise. A grant of exclusive use that the declaration does not already make is § 4600, not this definition. |
| Declaration | § 4135 | The recorded CC&Rs. |
| Governing documents | § 4150 | The declaration, bylaws, operating rules, and articles. |
| Operating rule | § 4340 | A board-adopted rule that applies to members. Rule changes that § 4355 covers follow §§ 4360–4365. |
| Managing agent | § 4158 | A person or firm that manages the association for compensation. A full-time employee of the association is not a managing agent for Article 9 (§ 5385). |
| Annual budget report | § 4076 | The yearly financial package in § 5300. |
| Annual policy statement | § 4078 | The yearly policy package in § 5310. |
| Reserve accounts | § 4177 | Funds set aside for major components. |
| Individual notice | § 4040 | Delivery to one member (mail or the electronic method § 4040 allows). |
| General notice | § 4045 | Delivery to the membership by a method in that section, such as posting or a website. |

Document authority when they conflict, Civil Code § 4205:

1. The law controls over the governing documents.
2. The declaration controls over the articles.
3. The declaration and the articles control over the bylaws.
4. The declaration, articles, and bylaws control over operating rules.

## Duty anchors

These are the concepts worth a model. Each row is a manager duty, the statute that frames it, and the artifact Jason would keep.

| Anchor | What the manager keeps straight | Primary sections | Artifact |
| --- | --- | --- | --- |
| Governing documents | Which instrument controls, and which sections an amendment changes | §§ 4150, 4205, 4250–4275, 4340–4370 | `GoverningDocument` and `Amendment` |
| Developer file | Whether the association has the maps, plans, deeds, instruments, maintenance plans, bonds, warranties, policies, contracts, and records the subdivider was required to provide | BPC §§ 11018.5, 11018.6; Title 10 §§ 2792.1, 2792.15, 2792.23 | `developer_file()`. An empty delivery is a missing basis for the duty that document supports |
| Notice | Whether a notice is individual or general, and whether delivery can be proved | §§ 4035–4055, 4041 | Notice record: who, which section, which method, when |
| Meetings | Open board meetings, agenda, executive session, minutes, member meetings | §§ 4900–4955, 5000, 5450 | Agenda, minutes, executive-session log |
| Elections | Election rules, inspector, ballots, retention | §§ 5100–5145 | Election file; do not run the election |
| Records | What a member may copy, how long it is kept, what is withheld, including the membership list | §§ 5200–5240, 5260 | Records request and the redaction reason. The list and a mailing are separate jobs |
| Annual disclosures | Budget report, policy statement, and the notice that they are available | §§ 5300, 5305, 5310, 5320 | Disclosure packet and the date it went out |
| Money | Monthly board review of finances, reserve use, reserve study | §§ 5500–5520, 5550–5580 | Review checklist; reserve study is a vendor product |
| Assessments | Levy, increase notice, delinquency, pre-lien notice, lien, foreclosure limits | §§ 5600–5740 | Ledger and the statutory notice. Handoff only; do not lien or foreclose |
| Insurance | Liability thresholds, fidelity amount, notice when coverage changes | §§ 5800–5810 | Policy register: kind, number, limit, renewal, building |
| Maintenance | Who repairs the unit, exclusive use, and common area | §§ 4775–4785 | Maintenance matrix from the declaration, not from a file name |
| Exclusive use | Whether the board may grant a member exclusive use of common area, and on what vote or exception | §§ 4145, 4600, 4605 | Grant file: the portion, the vote or the § 4600(b) exception, any consideration, and who insures it. Do not grant it |
| Architecture | Application, decision, and the timeline in the statute and the documents | §§ 4760, 4765 | Request file. Do not approve or deny. An approval is not a § 4600 grant |
| Protected uses | Flags, signs, rentals, EV charging, solar, ADUs, drought landscaping | §§ 4700–4753 | A flag on the request when a protected-use section may apply |
| Transfers | Escrow document list, fees, the form in § 4528 | §§ 4525–4545, 4575 | Resale packet. § 5376 if the contract assigns delivery |
| Discipline | Fine schedule, hearing, IDR before a lawsuit, ADR notice | §§ 5850–5965, 5975 | Hearing record and the IDR offer. Do not impose the penalty |
| Manager’s own duties | Pre-contract disclosure, certification status, real-estate license, referral fees, trust account, escrow delivery | CIV §§ 5375, 5375.5, 5376, 5380; BPC §§ 11504, 11505 | Disclosure file and the trust-account rule. Association funds the manager holds follow § 5380. Broker trust-fund rules apply only when the person is acting as a broker |

## Davis-Stirling index

The Davis-Stirling Common Interest Development Act is Part 5 of Division 4 of the Civil Code, §§ 4000–6150 (§ 4000). Chapters:

| Chapter | Sections | Subject |
| --- | --- | --- |
| 1. General provisions | 4000–4190 | Short title, notice, definitions |
| 2. Application | 4200–4202 | Which developments the Act covers |
| 3. Governing documents | 4205–4370 | Hierarchy, declaration, articles, condominium plan, operating rules |
| 4. Ownership and transfer | 4500–4650 | Ownership, transfer disclosures, transfer fees, exclusive-use grants, partition, mechanic’s liens |
| 5. Property use and maintenance | 4700–4790 | Protected uses, architectural review, maintenance |
| 6. Association governance | 4800–5450 | Powers, meetings, elections, records, annual reports, managing agent |
| 7. Finances | 5500–5580 | Review, reserves, reserve study |
| 8. Assessments | 5600–5740 | Levies, delinquency, liens, foreclosure limits |
| 9. Insurance and liability | 5800–5810 | Director liability, member liability, fidelity, coverage-change notice |
| 10. Dispute resolution | 5850–5986 | Hearings, IDR, ADR, enforcement |
| 11. Construction defects | 6100–6150 | Notices. Former § 6000 was repealed as of 2025-01-01 |

Official text: [Civil Code, Part 5](https://leginfo.legislature.ca.gov/faces/codes_displayexpandedbranch.xhtml?tocCode=CIV&division=4.&title=&part=5.&chapter=&article=).

### Exclusive use, which is not an architectural approval

Article 4 of Chapter 4 is Restrictions on Transfer, §§ 4600–4620. The words below are the 2025 session. § 4145 defines exclusive use common area the declaration has already allocated. § 4600 is the member vote required before the board grants exclusive use of common area that allocation does not already cover.

| Section | What it requires |
| --- | --- |
| § 4600 | Unless the governing documents set a different percentage, members owning at least 67 percent of the separate interests must approve before the board grants a member exclusive use of any portion of the common area. Subdivision (b) is the list that does not need that vote: reconveyance to the subdivider to continue a phased development already submitted to the Real Estate Commissioner; a grant in substantial conformance with that plan, or with governing documents the commissioner approved; correction of an engineering error in a recorded or filed document, or of a construction encroachment; a change in the development plan for topography, obstruction, hardship, aesthetics, or environmental conditions; a public-agency requirement; common area that is generally inaccessible and not of general use to the membership; a disability accommodation; assignment of a parking space, storage unit, or other amenity the declaration designates for assignment but does not assign to a specific separate interest; electric-vehicle charging access across the common area, or a license, that meets § 4745; a solar energy system on the common-area roof of a residence that meets §§ 714 and 714.1 and, if it applies, § 4746; and compliance with governing law. A measure asking the members for the grant states whether the association will be paid and whether the association or the transferee insures that exclusive use. |
| § 4605 | A member may sue the association for a violation of § 4600 within one year of accrual. A prevailing member recovers reasonable attorney’s fees and costs. The court may impose a civil penalty of up to $500 for each violation. An identical violation that affects each member equally is one penalty. A prevailing association does not recover costs unless the court finds the action frivolous, unreasonable, or without foundation. |
| § 4610 | Condominium common area stays undivided. Partition of the whole project is by sale of the entire project, and only in a circumstance that section lists. |
| § 4615 | Labor or materials an owner authorizes are not a basis for a lien on another owner’s property unless that owner consented. Emergency repairs to a separate interest are treated as consent. Common-area work the association duly authorizes is treated as the consent of each owner. An owner may clear that owner’s separate interest by paying the fraction of the lien attributable to it, or by recording a lien release bond under § 8424 for 125 percent of that sum. |
| § 4620 | When the association is served with a claim of lien under the works-of-improvement law, Part 6 commencing with § 8000, for work on a common area, it gives the members individual notice under § 4040 within 60 days of service. |

An architectural approval under § 4765 does not grant exclusive use. An electric-vehicle or roof-solar request that needs exclusive use of common area still has to fit an exception in § 4600(b), or go to the members.

### Insurance, which is not the Insurance Code

Chapter 9 is the association insurance statute. The California Insurance Code regulates insurers and policy forms. It does not set the association’s fidelity floor. That floor is Civil Code § 5806.

| Section | What it requires |
| --- | --- |
| § 5800 | Volunteer directors and officers have a liability cap only if the association carries general liability and directors-and-officers coverage of at least $500,000 (100 or fewer separate interests) or $1,000,000 (more than 100), and the other conditions in that section are met. |
| § 5805 | Tort claims that exist only because an owner is a tenant in common of the common area go against the association, not the owner, if general liability is at least $2,000,000 (100 or fewer) or $3,000,000 (more than 100). |
| § 5806 | Crime, employee-dishonesty, or fidelity coverage at least equal to reserves plus three months of assessments, including computer fraud and funds-transfer fraud in that amount. If a managing agent handles funds, the coverage includes that agent and its employees. Self-insurance does not qualify. The governing documents may require more. |
| § 5810 | Notice to members when coverage changes. |

Master property, flood, umbrella, and workers’ compensation are contract and risk-management duties (Business and Professions Code § 11502(b)(1)(C)), not a Civil Code schedule of limits. Flood placement for a building in a flood zone follows the National Flood Insurance Program and the lender’s project rules. The policy number, the renewal date, and which building the declaration describes are facts on the policy, stored on the insurance catalog.

Workers’ compensation applies when the association has employees. Track the policy with the others. Do not treat a blank workers’ compensation row as proof the association has no employees.

## What a certified manager is expected to know

Business and Professions Code § 11502(b) is the curriculum. On or after July 1, 2003, the title requires at least 30 hours and an examination covering the law courses in paragraph (1) and the management skills in paragraph (2). Paragraph (2) is skill, not a code: budgets, contracts, staff, maintenance programs, rules and parliamentary procedure, architectural standards, recreation facilities, owner communications, board training, policy implementation, ethics, and dispute avoidance. Paragraph (1) is the law list:

| Course | What § 11502(b)(1) names | Where this index already points |
| --- | --- | --- |
| (A) Davis-Stirling | Types of developments, disclosures, meetings, financial reporting, member access to records | Civil Code §§ 4000–6150, and the chapter table above |
| (B) Personnel | Employee or independent contractor, harassment, the Unruh Civil Rights Act, FEHA, the ADA | Civil Code § 51; Government Code § 12955 |
| (C) Risk management | Insurance, maintenance, operations, emergency preparedness | §§ 4775–4785, 5800–5810 |
| (D) Property protection | Asbestos, radon, lead-based paint, the Vehicle Code, local regulations, family day care, energy conservation, FCC rules, solar energy systems | §§ 4745–4746, and the hazard topics named in this row. Open the specific statute when a task needs it |
| (E) Business affairs | Compliance with federal, state, and local law | The row is the instruction to look the requirement up. It is not itself a citation |
| (F) Governing documents | The documents, codes, and regulations that govern the association | §§ 4150, 4205, and the Real Estate Commissioner regulations below |

§ 11502.5 says the examination and the course must meet published testing standards, Unruh, FEHA, and the ADA, or be a course the Real Estate Commissioner has approved as continuing education. Commissioner approval of a course is not a license to manage an association.

### Annual disclosure to the board

§ 11504 is an annual disclosure, and some of its items are also required before a contract or renewal. The 2025 text requires:

| Item | When |
| --- | --- |
| Whether the manager meets § 11502, the certifying association, the date and status of certification, and the primary office | Annually |
| Whether the manager’s or employer’s fidelity insurance covers that year’s operating and reserve funds. The association is not required to demand that insurance | Before a contract or renewal |
| Whether the manager holds an active real estate license | With the disclosure |
| The written statement Civil Code § 5375 requires | With the disclosure |
| Any referral fee or other monetary benefit from a third party who distributes documents under § 5300 | With the disclosure |
| A written acknowledgment that the disclosures and documents under §§ 4528 and 5300 are the association’s property, not the managing agent’s or the firm’s | With the disclosure |

### Two different trust-fund rules

Association money a managing agent accepts follows Civil Code § 5380. Funds that are not in escrow or in an account the association controls go into a trust account in a federally insured institution in this state, stay separate from the manager’s money, earn interest that does not go to the manager, and move only on the association’s written instructions. A transfer out of reserves or operations above the smaller of $5,000 or 5 percent of estimated annual income (50 or fewer interests) or $10,000 or 5 percent (51 or more) needs prior written board approval. The manager keeps a separate receipt-and-disposition record.

Business and Professions Code § 10145 and Title 10, Article 15, of the Commissioner’s regulations (sections 2830 through 2836 in the Bureau compilation) are the broker rules. They apply when a licensed broker accepts funds belonging to others in a transaction subject to the Real Estate Law. Section 2832 requires deposit into the broker’s trust account, a neutral escrow, or the owner’s hands within three business days, or the next business day when the broker is holding escrow. Sections 2831.1 and 2831.2 require a record per beneficiary and a monthly reconciliation. Section 2834 limits who may sign a withdrawal. Section 2835 defines commingling and allows up to $200 of the broker’s money to cover bank charges. Do not apply those broker rules to assessment funds a managing agent holds under § 5380. Do not apply § 5380 to a broker’s client trust account in a sale or lease.

### Documents the developer is required to provide

The Commissioner’s regulations explain the documents a subdivider must file to obtain a public report, and the documents the subdivider must deliver to the association. Those documents are how the association knows what it owns, what it must maintain, whom it may assess, and which contracts, warranties, and records it already has. A gap in that file is a gap in the association’s ability to understand and perform the duty the missing document supports.

Business and Professions Code § 11004.5 is the Subdivided Lands definition that covers a planned development, community apartment, condominium, or stock cooperative of five or more, and the accompanying interests in the owners’ association. Section 11010.2 says an application is substantially complete when it contains the documents the Commissioner’s regulations list. Section 11018.5 is the finding required before a public report: completion of the subdivision and offsite improvements is assured; the deeds and leases adequately transfer the interests represented; after the first transfer, the declaration, articles, bylaws, management contracts, and other plan documents last submitted bind later purchasers and occupants; and the plan has reasonable arrangements for delivering control to the purchasers and for management, maintenance, preservation, operation, use, resale, and control. Section 11018.6 requires the offeror to make the declaration, articles, bylaws, and any other instrument establishing the owners’ common rights and responsibilities available before an offer is signed, and to give each purchaser a copy before transfer, together with the financial information in Civil Code §§ 5300 and 5565 to the extent it is available and a statement of delinquent assessments against that interest.

Title 10, sections 2792 and 2792.1, are the application lists those statutes point at. For a condominium, planned development, or community apartment, a substantially complete application includes the proposed or existing governing instruments, the condominium plan or a plot plan of the improvements, the overall plan if the project is phased, evidence that common-area completion is financed, every contract that obligates the association, any agreement by the subdivider to subsidize maintenance and operations, a pro forma budget of ownership, operation, maintenance, and reserves, the association’s latest balance sheet and operating statement if one exists, an exemplar deed conveying the common area to the association, and exemplar escrow instructions. The base list in section 2792 also includes the preliminary title report, the proposed or existing CC&Rs, hazard information, and the arrangements for offsite improvements and for any warranty in the offering. Section 2792.8 is what the CC&Rs, articles, and bylaws ordinarily contain so the Commissioner treats them as the reasonable arrangements § 11018.5 requires. Section 2792.15 requires common areas and facilities that are to become the association’s to be transferred to the association, or to a trustee under an agreement the Commissioner accepts, before or together with the subdivider’s first conveyance.

Section 2792.23(a) is the delivery to the governing body. It starts no later than 90 days after the first close of escrow. Copies go over as soon as they are readily obtainable, including a document the subdivider obtains later. The duty ends at the earlier of the last conveyance covered by a public report and three years after the most recent public report expires. An annexed phase carries the same duty for the documents that apply to that phase, starting no later than 90 days after the annexation. The documents, and the duty each one supports:

| Document the subdivider delivers | Duty it lets the association perform |
| --- | --- |
| Recorded subdivision map or maps | Know the project boundaries |
| Recorded condominium plan and amendments | Tell a separate interest from common area |
| Deeds and easements conveying the common area or another interest to the association | Know what the association owns |
| Recorded CC&Rs, including amendments and annexations | Carry out the declaration |
| Filed articles of incorporation and amendments | Know the corporation |
| Bylaws and amendments | Know meetings, voting, and officers |
| Architectural guidelines and other rules the association has adopted for an owner’s interest or the common area | Apply the use rules already in force |
| Local-agency plans for facilities the association must maintain or repair | Maintain and repair those facilities. The regulation accepts plans that are not as-built |
| Notices of completion for common-area improvements other than residences | Know which common-area work was completed |
| Any bond or other security in which the association is the beneficiary | Look to the security given for the association |
| Written warranties transferred for common-area equipment, fixtures, or improvements | Make the warranty claim |
| Insurance policies procured for the association, its governing body, or the common area | Know the coverage already in force |
| Any lease or contract to which the association is a party | Administer that contract |
| Membership register, including mailing addresses and telephone numbers; books of account; minutes of the members, the governing body, and its committees | Give notice, account for the money, and continue the record |
| Any other instrument under § 11018.6(d) | Know a common, mutual, or reciprocal right or responsibility the list above does not already name |

Section 2792.21 is the set of powers those instruments ordinarily give the board: enforce the instruments, pay taxes that could lien the common area, contract for insurance and for common-area goods and services, prepare budgets and statements, adopt operating rules, discipline under the procedure in the instruments, and enter a separate interest for construction, maintenance, or emergency repair of the common area. Performing those powers depends on the instruments, plans, contracts, and records in the table.

Member inspection, minutes, and the annual budget follow Civil Code §§ 4950, 5200 and following, and 5300. Sections 2792.8 and 2792.32 still cite Civil Code sections the 2014 renumber repealed, including former §§ 1354 and 1359. The current partition section is § 4610. A public-report grant of exclusive use is an exception already listed in § 4600(b). Section 2836(a)(2) is the subdivider’s record of association operating funds during sales, kept three years. The manager’s ledger for assessment funds the manager holds is Civil Code § 5380.

## Other laws a manager is expected to know

Business and Professions Code § 11502(b)(1) is the curriculum for a certified manager. These are the neighboring bodies of law it names. Learn the topic. Open the statute when a task needs the rule. California text still comes from `cite_law` / `get_section` over `US-CA`. When that call misses with reason `outside_us_ca`, the `statute` or `regulations` field names the next corpus: the United States Code in `data/codes/US.sqlite`, or one CFR title in `data/codes/US/cfr/{title}.sqlite` (Fair Housing is 24 CFR, not California Title 24; ADA is 28 CFR; NFIP is 44 CFR). The Commissioner’s Title 10 regulations are not in the lawlibrary index. Those files may be absent until loaded; absence is still a miss. Do not scrape HUD, DOJ, FEMA, leginfo, Westlaw, or ICC, and do not quote this page.

| Body | Where | Why it comes up |
| --- | --- | --- |
| Nonprofit Mutual Benefit Corporation Law | Corporations Code §§ 7110–8910 | Incorporated associations. § 7210 is the board’s duty to direct. Civil Code § 4805 lets an association exercise the powers in Corporations Code § 7140. |
| Certified CID manager | Business and Professions Code §§ 11500–11506 | The job definition, the “certified” title, the annual board disclosure, and the unfair-practice limits. § 11501: no real estate license is required for those management services. |
| Fair housing | Government Code § 12955 (FEHA); Civil Code § 51 (Unruh); federal Fair Housing Act | Occupancy, accommodations, and unlawful restrictive covenants. § 4225 requires the board to delete a covenant that violates § 12955. |
| Employment | FEHA, harassment law, independent-contractor versus employee | Staff and vendors. |
| Disability access | Americans with Disabilities Act; FEHA | Common-area facilities and reasonable accommodation. |
| Vehicles and local rules | Vehicle Code; city and county ordinances | Parking, streets, and use restrictions the declaration does not cover. |
| Solar, radio, environment | Civil Code §§ 4745–4746; FCC rules; hazard rules named in § 11502 | EV charging, solar, antennas, asbestos, lead, radon. |
| Civil rights in covenants | Civil Code § 4225; Government Code § 12955 | Delete the unlawful restriction. Do not rewrite the rest of the document. |
| Real estate license | Business and Professions Code §§ 10131, 10131.01, 10145 | A license is required to sell, lease, or collect rents for compensation, unless § 10131.01 applies. Broker trust accounts follow § 10145 and Title 10, sections 2830–2836. |
| Public report and the developer’s documents | Business and Professions Code §§ 11004.5, 11010.2, 11018.5, 11018.6; Title 10, sections 2792, 2792.1, 2792.8, 2792.15, 2792.23 | The regulations explain the documents the developer must file for a public report and must deliver to the association. Those documents are what the association uses to know its property, maintenance, contracts, members, and money. Citations in the regulations to repealed Civil Code §§ 1354 and 1359 are former section numbers; the current partition section is § 4610. |

## How Jason should use this

- Identify the duty anchor first, then the section, then the association's document or catalog row. What Jason prepares, and what stays with the board, is [docs/laws/assist.md](laws/assist.md).
- Prefer the governing document when the statute defers to it (maintenance, assessment formula, insurance limits above the statutory floor).
- Prefer the statute when § 4205 says the law wins.
- Leave a section citation off a draft until the official text has been read for that task.
- A miss stays a miss. Do not fill an insurance limit, a fine amount, or a CC&R section from this index.
