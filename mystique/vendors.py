"""Vendor customer portals jason signs in to, non-interactively, with the Keeper record named by each key.

ProActive Pest Control (Pro Active North, Roseville) services the common areas on a bi-weekly plan
sold December 29, 2022. Its portal runs on FieldRoutes' FieldPortals; the association is customer
47362 (commercial, master account). The PayHOA bank line reads "ORIG CO NAME:Pro Active Pest".

Its license is as a board member read it at the Department of Consumer Affairs license search
(Structural Pest Control Board) on September 29, 2026: company registration 6993, CLEAR, Branch 2
(general pest) and Branch 3 (wood-destroying organisms), no Branch 1 (fumigation). The search listed
113 people and branch offices on the registration; the first 10 are recorded here. A technician not
listed may be on the part not read. Check again at each contract renewal.
"""

from datetime import date

from jason.community.base import EmailFiling, LicensedPerson, VendorLicense, VendorPortal
from jason.community.symbols import DocumentKind, PortalPlatform

PROACTIVE_LICENSE = VendorLicense(
    board="Structural Pest Control Board",
    number="6993",
    kind="Company Registration",
    classes=("Branch 2", "Branch 3"),
    status="CLEAR",
    issued=date(2014, 3, 20),
    verified=date(2026, 9, 29),
    people=(
        LicensedPerson("TURNER, KYLE T", "President"),
        LicensedPerson("SINDLE, JESSE L", "Qualified Manager"),
        LicensedPerson("TURNER, KYLE T", "Qualified Manager"),
        LicensedPerson("TURNER, KYLE T", "Operator", "12674", "CLEAR"),
        LicensedPerson("SINDLE, JESSE L", "Operator", "13900", "CLEAR"),
        LicensedPerson("LEIGHTON, STEVEN EDWARD", "Field Representative", "25256", "CLEAR"),
        LicensedPerson("RODRIGUEZ, SAUL E", "Field Representative", "28829", "CLEAR"),
        LicensedPerson("SINDLE, JESSE LEE", "Field Representative", "39192", "CLEAR"),
        LicensedPerson("REBOJA, JASON P", "Field Representative", "49355", "CLEAR"),
        LicensedPerson("CROSBY, GEORGE D JR", "Field Representative", "51660", "CLEAR"),
    ),
    relationships_seen=10,
    relationships_total=113,
    lookup="https://search.dca.ca.gov/ (Structural Pest Control Board, license 6993)",
)

VENDOR_PORTALS: tuple[VendorPortal, ...] = (
    VendorPortal(
        key="proactive",
        vendor="ProActive Pest Control",
        platform=PortalPlatform.FIELDPORTALS,
        account="proactive",
        budget_line="Pest Control",
        payhoa_words=("PRO ACTIVE PEST", "PROACTIVE PEST", "DUE TO PRO ACTIVE"),
        service="Bi-weekly exterior pest control",
        license=PROACTIVE_LICENSE,
    ),
    # Signal Service, Inc (fire alarm monitoring, Angels Camp): its portal is a Django site, account 15520 with a
    # site per building. Quarterly invoices on the 16th-17th, one per building; PayHOA vendor "Signal Service Inc".
    VendorPortal(
        key="signalservice",
        vendor="Signal Service, Inc",
        platform=PortalPlatform.SIGNAL_SERVICE,
        account="portal.signalserviceinc.com",
        budget_line="Fire Alarm Monitoring",
        payhoa_words=("SIGNAL SERVICE",),
        service="Fire alarm monitoring, inspection, and equipment lease",
        reports=PortalPlatform.FIRENSPEC,
    ),
)

# Where vendors' email attachments are filed (jason gmail --file-vendor): a kind with its own shelf in My Drive goes
# there; everything else to My Drive/Vendors/<vendor>/<year>. Folder ids read from the Drive sync of September 30, 2026.
EMAIL_FILING = EmailFiling(
    vendors_folder="1fQRi2-6n2GoeSKs-KV-BcT6t9pou-8XV",                       # My Drive/Vendors
    by_kind=(
        (DocumentKind.INSPECTION_REPORT, "1n3nEuzT3AvbORRR0yMxyKVZcB464rasN"),   # My Drive/Reports
        (DocumentKind.ELEVATED_ELEMENT_INSPECTION, "1n3nEuzT3AvbORRR0yMxyKVZcB464rasN"),
        (DocumentKind.CONTRACT, "1iLK8x2AIJb4ROO6scFuuK-N-AkPpdTsc"),            # My Drive/Contracts
        (DocumentKind.PROPOSAL, "1NG5sYiX1s-rE2OhWKy5eglUGO7irAJb2"),            # My Drive/Proposals / Estimates
        (DocumentKind.EVIDENCE_OF_INSURANCE, "1-YNfQtR9pgPNAreFZ4lIlb3mSzekW9r7"),  # My Drive/Vendors/W9 and Insurance
    ),
)
