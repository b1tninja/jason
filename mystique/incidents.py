"""Where Mystique's repair paperwork is in Drive, for the incident history (``jason incidents``).

Each folder is a path under My Drive. The claims and losses folders are confidential: they hold adjusters' letters, a
police report, and payment stubs, so the history keeps their facts (date, place, cause, amounts, claim number) and holds
their snippets back unless asked. The root of My Drive holds loose files; only names that read as repair paperwork are
fetched. The dog-attack lawsuit's medical and veterinary records sit at the root too, and are never downloaded.

The Security Patrol reports (``Reports/Security Patrol``, 88 daily reports from 2023) are left for their own reader.
"""

from jason.community.incidents import Element, EvidenceFolder, EvidencePlan, VendorWork, Work

EVIDENCE = EvidencePlan(
    folders=(
        EvidenceFolder("Proposals / Estimates", "proposals, estimates, and bids since 2024"),
        EvidenceFolder("The Helsing Group/Archives from Prior Management/Vendor Invoices", "the prior manager's vendor invoices, 2021 to 2023"),
        EvidenceFolder("The Helsing Group/Archives from Prior Management/Vendor Contracts", "the prior manager's vendor contracts"),
        EvidenceFolder("The Helsing Group/Property", "the prior manager's property files: roofs, pest, exterior, utilities"),
        EvidenceFolder("The Helsing Group/Insurance/Claims", "insurance claims under the prior manager", confidential=True),
        EvidenceFolder("Claims", "insurance claims: adjusters' reports, estimates, mitigation, outcome letters", confidential=True),
        EvidenceFolder("Losses", "losses: statements of loss, police reports, estimates, claim payments", confidential=True),
        EvidenceFolder("Inspections", "inspection and repair records: roof repairs, the storm drain"),
        EvidenceFolder("Reports", "inspection reports: roofs, fire sprinklers, backflow, SB 326, the defect report",
                       skip=("Security Patrol/*",)),
        EvidenceFolder("Roof Inspection - 2026", "the 2026 roof inspection report and photos"),
        EvidenceFolder("archive", "archive boxes of older paperwork"),
        # Found by searching Drive for claim language (September 29, 2026).
        EvidenceFolder("The Helsing Group/Archives from Prior Management/Insurance", "the prior manager's insurance files: loss runs",
                       confidential=True),
        EvidenceFolder("The Helsing Group/Insurance", "insurance under the prior manager", confidential=True),
        EvidenceFolder("The Helsing Group/Homeowner Files, by Address", "the prior manager's unit files: a claim's tracker and "
                       "certificate of satisfaction, leak records", confidential=True),
        EvidenceFolder("The Helsing Group/Inspection Reports and Pictures", "the prior manager's inspection reports"),
        EvidenceFolder("The Helsing Group/Archives from Prior Management/Minutes", "special and executive minutes (the 2022 "
                       "water leak repair)", confidential=True),
        EvidenceFolder("Insurance/2026", "the insurers' 2026 letters: claim status", confidential=True),
        # The dog-attack liability claim: the tender, the carrier's acknowledgment, and its status letters only. The demand,
        # the preservation letter, the court filings, and the transcripts describe the injuries and are not read.
        EvidenceFolder("26CV016125 - Dog Attack", "the liability claim's correspondence with the carriers", confidential=True,
                       skip=("*Demand*", "*preservation*", "ROA *", "*Case Summary*", "*transcript*", "Dog Attack/*",
                             "*Disciplinary*", "*Violation*", "*Complaints*")),
        EvidenceFolder("Meetings", "board packets' attachments: proposals, invoices, leak repairs, water tests"),
        EvidenceFolder("Financials/2022/Invoices", "2022 invoices"),
        EvidenceFolder("Financials/2023/Invoices", "2023 invoices"),
        EvidenceFolder("Financials/Invoices", "invoices kept outside PayHOA"),
        EvidenceFolder("Reserve Expenses", "reserve-funded repairs"),
        EvidenceFolder("Defects", "construction defect records"),
        EvidenceFolder("Construction Defect", "notices to the builder"),
        EvidenceFolder("Warranty", "the builder's homeowner warranty"),
        EvidenceFolder("Historical", "older reports: a 2021 police report"),
        EvidenceFolder("False Alarm", "false fire alarms and the city's determination"),
        EvidenceFolder("Notices", "notices: backflow repair, fire sprinkler inspection"),
        EvidenceFolder("Legal", "counsel's letters: builder settlement, window warranty and efflorescence claims", confidential=True),
        EvidenceFolder("Governing Documents/Resolutions", "resolutions: the 2022 freshwater leak, reserve borrowing for repairs"),
    ),
    root_names=("*estimate*", "*Estimate*", "*ESTIMATE*", "*Proposal*", "*proposal*", "*Repair*", "*repair*", "*Mitigation*",
                "*inspection report*", "*Inspection Report*", "*Emergency*", "*Claim*", "*claim*", "*Service Agreement*",
                "*Invoice*", "*invoice*", "*Damage*", "*damage*", "*Leak*", "*leak*", "*Loss Run*", "*Status letter*",
                "*Police Report*"),
    private_names=("*MEDICAL*", "*Medical*", "*medical*", "*Urgent Care*", "*VCA *", "*VCA_*", "*PEDIATRIC*", "*Pediatric*",
                   "*Health*", "*RECORD*", "*Records*"),
    # The insurance policies, escrow instructions, and the landscaper's service location print 3048 Macon Dr for the
    # association's premises; no parcel has that address (the site's own is 3000 Macon Dr, in mail.py).
    site_words=("3048 MACON",),
    vendor_work=(
        # Summit is the association's roof repair vendor, called to each leak since at least 2017; its calls are the
        # roofs' upkeep. The work is maintenance; a claim on the same leak is still a claim.
        VendorWork("Summit Roofing Company", Work.MAINTENANCE, (Element.ROOF, Element.GUTTER),
                    "the association's roof repair vendor; its leak calls are roof maintenance"),
    ),
)
