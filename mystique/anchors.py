"""Drive files, PayHOA folders, Drive roots, and public site pages."""

from jason.community.base import DriveRoot, KnownAnchor, LibraryFolder, SitePageRef
from jason.community.symbols import (
    AssociationRecord,
    DocumentKind,
    DocumentRule,
    FileKind,
    KnownFile,
    PayhoaFolder,
    PublicDrive,
    SitePage,
)

FILES: tuple[KnownAnchor, ...] = (
    KnownAnchor(KnownFile.PORTAL, FileKind.GOOGLE_SITE, "Portal", "1nSGJEbLudfpGPK5fjweyd-CNZKXa4a5-"),
    KnownAnchor(
        KnownFile.MINUTES_2026_07_07,
        FileKind.GOOGLE_DOC,
        "Minutes of 7/7/26",
        "1naPLbSTlpz_a9uf2fl2Dta6dC1Nrv0rvqwMUGbRwI7Q",
        PayhoaFolder.MEETINGS_2026,
        "Minutes of 7_7_26.pdf",
        records=(AssociationRecord.MINUTES,),
        document_kind=DocumentKind.MINUTES,
    ),
    KnownAnchor(
        KnownFile.ALPR_POLICY,
        FileKind.GOOGLE_DOC,
        "ALPR Policy",
        "1tRv7GEG9WjJSBd71s1Yu3rgwTYgQWhcRbYZeSdmsiyI",
        PayhoaFolder.POLICIES,
        "ALPR Policy.pdf",
        records=(AssociationRecord.GOVERNING_DOCUMENTS,),
        document_kind=DocumentKind.POLICY,
    ),
    KnownAnchor(
        KnownFile.ALPR_SAFE_LIST,
        FileKind.GOOGLE_DOC,
        "ALPR Safe List",
        "1I8w65IgcqvK6Ii4rtj8hk8GQCoAP6lgIgxDVSJO20xg",
    ),
    KnownAnchor(
        KnownFile.INSURANCE_WORKBOOK,
        FileKind.GOOGLE_SHEET,
        "Vendors, Utilities, Accounts, Taxes, and Insurance",
        "1Z-vOivliQf55_a8zxi4OmX4-7Qaf6amfrPWzDzwq0sA",
        tab="Insurance",
    ),
    KnownAnchor(
        KnownFile.MEMBERSHIP,
        FileKind.GOOGLE_SHEET,
        "Membership",
        "1LFwR2-_RX8h9_o3EwMd_P5R8h3q4Jtl3J12KzoeG_4I",
        records=(AssociationRecord.MEMBERSHIP_LIST,),
        document_kind=DocumentKind.MEMBERSHIP_LIST,
    ),
    KnownAnchor(
        KnownFile.RESERVE_COMPONENTS,
        FileKind.GOOGLE_SHEET,
        "Reserve Components",
        "1olOFGoQL3EAwIlTujWE_arO00tNolsPI_bNw9tAhwok",
        tab="Components",
    ),
)

LIBRARY: tuple[LibraryFolder, ...] = (
    LibraryFolder(PayhoaFolder.GOVERNING_DOCUMENTS, 1018654, "Governing Documents/", None, PublicDrive.GOVERNING_DOCUMENTS, (AssociationRecord.GOVERNING_DOCUMENTS,)),
    LibraryFolder(PayhoaFolder.ANNEXATIONS, 1018678, "Governing Documents/Annexations/", DocumentRule.ANNEXATIONS, PublicDrive.ANNEXATIONS, (AssociationRecord.GOVERNING_DOCUMENTS,)),
    LibraryFolder(PayhoaFolder.POLICIES, 1018661, "Governing Documents/Policies/", DocumentRule.POLICIES, PublicDrive.POLICIES, (AssociationRecord.GOVERNING_DOCUMENTS,)),
    LibraryFolder(PayhoaFolder.RESOLUTIONS, 1018688, "Governing Documents/Resolutions/", DocumentRule.RESOLUTIONS, PublicDrive.RESOLUTIONS),
    LibraryFolder(PayhoaFolder.ELECTIONS, 1079397, "Elections/", DocumentRule.ELECTION_RULES),
    LibraryFolder(PayhoaFolder.DRE_PUBLIC_REPORTS, 1018715, "DRE Public Reports/", DocumentRule.DRE_REPORTS, PublicDrive.DRE_REPORTS),
    LibraryFolder(PayhoaFolder.GRANT_DEEDS, 1018695, "Grant Deeds/", DocumentRule.GRANT_DEEDS, PublicDrive.DEEDS),
    LibraryFolder(PayhoaFolder.GRANT_DEEDS_COMMON_AREAS, 1222512, "Grant Deeds/Common Areas/", DocumentRule.GRANT_DEEDS),
    LibraryFolder(PayhoaFolder.PLANS, 1018665, "Plans/", DocumentRule.PLANS, PublicDrive.PLANS),
    LibraryFolder(PayhoaFolder.MAPS, 1018731, "Maps/", DocumentRule.MAPS, PublicDrive.MAPS),
    LibraryFolder(PayhoaFolder.INSURANCE, 1019643, "Insurance/", DocumentRule.INSURANCE_CURRENT, PublicDrive.INSURANCE, (AssociationRecord.EXECUTED_CONTRACT,)),
    LibraryFolder(PayhoaFolder.FINANCIALS, 1076770, "Financials/", records=(AssociationRecord.FINANCIAL_DISCLOSURE, AssociationRecord.INTERIM_FINANCIAL, AssociationRecord.RESERVE_ACCOUNT)),
    LibraryFolder(PayhoaFolder.MEETINGS, 1076728, "Meetings/", records=(AssociationRecord.MINUTES,)),
    LibraryFolder(PayhoaFolder.MEETINGS_2026, 2643621, "Meetings/2026/", records=(AssociationRecord.MINUTES,)),
    LibraryFolder(PayhoaFolder.CONTRACTS, 1079359, "Contracts/", records=(AssociationRecord.EXECUTED_CONTRACT,)),
    LibraryFolder(PayhoaFolder.LEGAL, 1018727, "Legal/"),
    LibraryFolder(PayhoaFolder.LEASE_AGREEMENTS, 2225382, "Lease Agreements/", records=(AssociationRecord.EXECUTED_CONTRACT,)),
    LibraryFolder(PayhoaFolder.RESALE_DOCUMENTS, 2643517, "Resale Documents/"),
    # Private: the files PayHOA broadcasts and templates attach (the insurance notice's four are here).
    LibraryFolder(PayhoaFolder.EMAIL_ATTACHMENTS, 1101044, "Email Attachments/"),
)

ROOTS: tuple[DriveRoot, ...] = (
    DriveRoot("Governing Documents", PayhoaFolder.GOVERNING_DOCUMENTS, PublicDrive.GOVERNING_DOCUMENTS, DocumentRule.GOVERNING_ROOT),
    DriveRoot("Financials", PayhoaFolder.FINANCIALS),
    DriveRoot("Meetings", PayhoaFolder.MEETINGS),
    DriveRoot("Insurance", PayhoaFolder.INSURANCE, PublicDrive.INSURANCE),
    DriveRoot("Contracts", PayhoaFolder.CONTRACTS),
    DriveRoot("Elections", PayhoaFolder.ELECTIONS),
    DriveRoot("Plans", PayhoaFolder.PLANS, PublicDrive.PLANS),
    DriveRoot("Maps", PayhoaFolder.MAPS, PublicDrive.MAPS),
    DriveRoot("Legal", PayhoaFolder.LEGAL),
    DriveRoot("Deeds", PayhoaFolder.GRANT_DEEDS, PublicDrive.DEEDS),
    DriveRoot("California BRE", PayhoaFolder.DRE_PUBLIC_REPORTS, PublicDrive.DRE_REPORTS),
    DriveRoot("Leases", PayhoaFolder.LEASE_AGREEMENTS),
    DriveRoot("Escrow", PayhoaFolder.RESALE_DOCUMENTS),
)

PAGES: tuple[SitePageRef, ...] = (
    SitePageRef(SitePage.HOME, "/"),
    SitePageRef(SitePage.RECORDS, "/records", (PayhoaFolder.GOVERNING_DOCUMENTS, PayhoaFolder.ANNEXATIONS, PayhoaFolder.DRE_PUBLIC_REPORTS, PayhoaFolder.GRANT_DEEDS)),
    SitePageRef(SitePage.PLANS, "/plans", (PayhoaFolder.PLANS, PayhoaFolder.MAPS)),
    SitePageRef(SitePage.REPORTS, "/reports"),
    SitePageRef(SitePage.INSURANCE, "/insurance", (PayhoaFolder.INSURANCE,)),
    SitePageRef(SitePage.FINANCIALS, "/financials", (PayhoaFolder.FINANCIALS,)),
    SitePageRef(SitePage.ESCROW, "/escrow", (PayhoaFolder.RESALE_DOCUMENTS,)),
)
