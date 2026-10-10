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

from jason.community.base import EmailFiling, FilingRule, LicensedPerson, VendorLicense, VendorPortal
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

# Where counterparties' email attachments are filed (jason gmail --file-vendor), by the record's kind first and its
# source second, so each record sits where its retention clock runs (mystique/notes/fire-protection-records.md):
# invoices by fiscal year (Civil Code 5210(a)(1)), contracts by vendor (kept past their term), inspection reports by
# system (kept the life of the system), and a vendor's own paperwork (W-9, certificate) in its vendor folder.
_FIRE = ("Reports", "Fire Protection")
EMAIL_FILING = EmailFiling(
    root="root",                                                                  # My Drive
    rules=(
        FilingRule(DocumentKind.INSPECTION_REPORT, (*_FIRE, "Fire Alarm"), senders=("Signal Service",)),
        FilingRule(DocumentKind.INSPECTION_REPORT, (*_FIRE, "Fire Sprinklers"), senders=("The Fire Sprinkler Company",)),
        FilingRule(DocumentKind.INSPECTION_REPORT, (*_FIRE, "Backflow"), senders=("LeDoux Backflow Testing Services",)),
        FilingRule(DocumentKind.INSPECTION_REPORT, ("Reports", "Roofs"),
                   senders=("North American Home Services", "GoodLife Construction", "Summit Roofing Company")),
        FilingRule(DocumentKind.INSPECTION_REPORT, ("Reports", "Pest Control"), senders=("ProActive Pest Control",)),
        FilingRule(DocumentKind.NOTICE, ("Reports", "Pest Control"), senders=("ProActive Pest Control",)),
        FilingRule(DocumentKind.ELEVATED_ELEMENT_INSPECTION, ("Reports", "Balconies (SB 326)")),
        FilingRule(DocumentKind.INSPECTION_REPORT, ("Reports", "{vendor}")),
        FilingRule(DocumentKind.CONTRACT, ("Contracts", "{vendor}")),
        FilingRule(DocumentKind.PROPOSAL, ("Proposals / Estimates", "{year}")),
        FilingRule(DocumentKind.INVOICE, ("Financials", "{year}", "Invoices", "{vendor}")),
        FilingRule(DocumentKind.RESERVE_STUDY, ("Financials", "{year}")),
        # A utility's bill is paid like an invoice and is filed like one, by fiscal year and vendor (Civil Code 5210(a)(1)
        # makes the current and two previous fiscal years inspectable).
        FilingRule(DocumentKind.UTILITY_BILL, ("Financials", "{year}", "Invoices", "{vendor}")),
        # The preparer's package of a year's returns arrives the year after, so a year folder would file it a year late:
        # one folder, the tax year in each file's name. The returns are CIV 5200(a)(6) records.
        FilingRule(DocumentKind.TAX_RETURN, ("Financials", "Tax Returns")),
        FilingRule(DocumentKind.SECURITY_REPORT, ("Reports", "Security Patrol")),
        FilingRule(DocumentKind.EVIDENCE_OF_INSURANCE, ("Vendors", "{vendor}")),
        FilingRule(DocumentKind.FORM, ("Vendors", "{vendor}")),
        # The inspector of elections' materials are election records (Civil Code 5200(c)), not the vendor's file.
        FilingRule(None, ("Elections", "{year}"), senders=("Pro Elections",)),
    ),
    fallback=("Vendors", "{vendor}", "{year}"),
)
