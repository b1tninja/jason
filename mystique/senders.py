"""Mystique's counterparties: who writes to the association, who it pays, and what kind of source each is.

Built from the senders and letterheads of the PostScanMail mail (read September 29, 2026) and PayHOA's
vendor directory. ``payhoa_vendor`` is the name in that directory, so a sender's letters and its
payments can be read together. A role is written only where the documents show it; "prior manager"
for the four management companies is from a board member (September 29, 2026), and the flood carriers are the ones the
renewal letters name.

San Jose Water Company is not Mystique's utility: its letter in the box is BellaTerra Owners
Association's backflow notice, addressed in care of Mystique.
"""

from __future__ import annotations

from jason.community.sources import Level, Policyholder, Sender, SourceKind

G, U, I, B, V = SourceKind.GOVERNMENT, SourceKind.UTILITY, SourceKind.INSURER, SourceKind.BANK, SourceKind.VENDOR

_SENDERS: tuple[Sender, ...] = (
    # Government
    Sender("Internal Revenue Service", G, ("INTERNAL REVENUE SERVICE", "DEPARTMENT OF THE TREASURY"), Level.FEDERAL),
    Sender("Franchise Tax Board", G, ("FRANCHISE TAX BOARD",), Level.STATE),
    Sender("California Secretary of State", G, ("SECRETARY OF STATE",), Level.STATE, role="statement of information"),
    Sender("Sacramento County Department of Finance, Tax Collector", G, ("DEPARTMENT OF FINANCE", "TAX COLLECTOR", "CHAD RINDE", "TAX AND LICENSING DIVISION"),
           Level.COUNTY, payhoa_vendor="SACRAMENTO COUNTY TAX COLLECTOR", role="secured property taxes on the common-area parcels"),
    Sender("Sacramento Fire Department", G, ("SACRAMENTO FIRE DEPARTMENT", "FIRE DEPARTMENT"), Level.CITY, role="alarm and fire code notices"),
    # Utilities
    Sender("City of Sacramento Department of Utilities", U, ("DEPARTMENT OF UTILITIES", "CITY OF SACRAMENTO"), Level.CITY,
           payhoa_vendor="City of Sacramento", role="water, storm drainage, street sweeping, backflow testing", domains=('cityofsacramento.org',)),
    Sender("SMUD", U, ("SMUD", "SACRAMENTO MUNICIPAL UTILITY"), Level.DISTRICT, role="electricity", domains=('smud.org',)),
    Sender("San Jose Water Company", U, ("SAN JOSE WATER", "SOUTH BASCOM"), role="not Mystique's utility; its letter is for BellaTerra Owners Association"),
    # Insurance
    Sender("Philadelphia Insurance Companies", I, ("PHILADELPHIA INDEMNITY", "PHILADELPHIA INSURANCE", "TOKIO MARINE"),
           role="flood policies, one per building, since 2025", domains=('torrentcorp.com',)),
    Sender("Fire Insurance Exchange (Farmers, NFIP flood)", I, ("FIRE INSURANCE EXCHANGE", "FLOOD INSURANCE PROCESSING", "FARMERS"),
           payhoa_vendor="Fire Insurance Exchange", role="flood policies through 2024"),
    # Its account managers write from hoa-insurance.com (agency license 0C84283 in their signatures).
    Sender("LaBarre/Oksnee Insurance Agency", I, ("LABARRE", "OKSNEE"), payhoa_vendor="LaBarre/Oksnee Insurance Agency, LLC",
           role="insurance agency", domains=("hoa-insurance.com",)),
    Sender("Castle Rock Insurance Agency", I, ("CASTLE ROCK INSURANCE",), role="insurance agency on the Philadelphia flood policies"),
    Sender("Arden Insurance Services", I, ("ARDEN INSURANCE",)),
    Sender("McGowan Program Administrators", I, ("MCGOWAN",)),
    # Its claim letters print "Athens Administrators" (privilege.py lists it by that name and this domain).
    Sender("Athens Program Insurance Services", I, ("ATHENS PROGRAM", "ATHENS ADMINISTRATORS"), domains=('athensadmin.com',)),
    # CAIS bills both PMA-group policies on one account; its ACH debit ("CAIS Insurance") names neither.
    Sender("Manufacturers Alliance Insurance Company", I, ("MANUFACTURERS ALLIANCE", "CAIS INSURANCE"),
           role="crime (fidelity) policy, billed by CAIS through LaBarre/Oksnee; CAIS's debit also pays the workers' comp"),
    Sender("Pennsylvania Manufacturers' Association Insurance Company", I, ("PENNSYLVANIA MANUFACTURERS", "WORKCOMP INVOICE", "CAIS, LLC"),
           role="workers' compensation policy since September 28, 2026, billed by CAIS through LaBarre/Oksnee"),
    Sender("Vitesse PSP", I, ("VITESSE",), role="insurance claim payments", domains=("vitesse.io",)),
    # An owner's own homeowner insurers, from claim papers in the records (letters, estimates, authorizations, payments).
    # The policies are the owners', not the association's: `holder` says so, and the history shows these claims apart.
    Sender("AAA Insurance", I, ("AAA INSURANCE", "CSAA"), role="an owner's own insurer on homeowner claims", domains=("csaa.com",),
           holder=Policyholder.OTHER),
    Sender("USAA (Garrison Property and Casualty)", I, ("USAA", "GARRISON PROPERTY AND CASUALTY"),
           role="an owner's own insurer on homeowner claims", holder=Policyholder.OTHER),
    # Banks
    Sender("First Citizens Bank", B, ("FIRST CITIZENS", "FIRST-CITIZENS", "PRIMARY ACCOUNT NUMBER ENDING IN"), role="reserve certificate of deposit <reserve cd (first citizens)>"),
    Sender("JPMorgan Chase", B, ("JPMORGAN", "CHASE BANK", "INDIANAPOLIS IN 46244", "CHASE FOR BUSINESS", "CHASE COM"), role="the association's bank: the operating, reserve, and reserve CD accounts"),
    # Title and escrow
    Sender("Fidelity National Title Company", SourceKind.TITLE_ESCROW, ("FIDELITY NATIONAL TITLE",)),
    Sender("First American Title Company", SourceKind.TITLE_ESCROW, ("FIRST AMERICAN TITLE",), domains=('firstam.com',)),
    Sender("Priority Title", SourceKind.TITLE_ESCROW, ("PRIORITY TITLE",)),
    Sender("Placer Title Company", SourceKind.TITLE_ESCROW, ("PLACER TITLE",)),
    Sender("Chicago Title", SourceKind.TITLE_ESCROW, ("CHICAGO TITLE",)),
    # Law firms
    Sender("Berding & Weil LLP", SourceKind.LAW_FIRM, ("BERDING",), payhoa_vendor="Berding & Weil LLP", domains=('berdingweil.com',)),
    Sender("Severaid and Glahn", SourceKind.LAW_FIRM, ("SEVERAID",), payhoa_vendor="Severaid and Glahn", role="assessment collections"),
    Sender("Absolute Law Group", SourceKind.LAW_FIRM, ("ABSOLUTE LAW GROUP",)),
    Sender("Morgan and Buzzard", SourceKind.LAW_FIRM, ("BUZZARD", "729 FIRST STREET", "729 FIRSTSTREET"), role="personal injury attorneys"),
    # Management, accountants, platforms
    # The association's prior managers, as a board member listed them on September 29, 2026: RealManage, The Helsing
    # Group, Vierra Moore, and Network Community Management (the order and dates are not recorded here). Owner
    # statements of other associations came to the box from RealManage's lockbox (P.O. Box 803555, Dallas; they print
    # ciranet.com, RealManage's owner portal) and Vierra Moore's (P.O. Box 348600, Sacramento).
    Sender("The Helsing Group", SourceKind.MANAGER, ("HELSING",), role="prior manager", domains=('helsing.com',)),
    Sender("RealManage", SourceKind.MANAGER, ("REALMANAGE", "REAL MANAGE", "CIRANET", "CIRACONNECT", "BOX 803555"),
           role="prior manager; other associations' owner statements from its lockbox"),
    Sender("Network Community Management", SourceKind.MANAGER, ("NETWORK COMMUNITY MANAGEMENT",), role="prior manager"),
    Sender("Newman Certified Public Accountant", SourceKind.ACCOUNTANT, ("NEWMAN CERTIFIED", "NEWMAN CPA"),
           payhoa_vendor="Newman Certified Public Accountant, PC", role="tax preparation", domains=('hoacpa.com',)),
    # The IRS still has the association in Vierra Moore's care.
    Sender("Vierra Moore", SourceKind.MANAGER, ("VIERRA MOORE", "VIERRAMOORE", "BOX 348600"),
           role="prior manager; named in care of on an IRS notice; other associations' owner statements"),
    # Owners' property managers: each named as manager or agent on a lease the Association holds, and writing from its
    # domain (October 1, 2026). An owner's manager is the unit's other contact, and a Property Manager record only when the owner asks;
    # the manager gets notices only if the owner names them. A domain that only looks like a manager's (a realty, a
    # "properties") is a candidate until a lease or the owner says so (`jason rentals --register`).
    Sender("Belong", SourceKind.PROPERTY_MANAGER, ("BELONG INC", "BELONG HOME"), role="an owner's property manager (lease)",
           domains=("belonghome.com",)),
    Sender("Tiner Properties", SourceKind.PROPERTY_MANAGER, ("TINER PROPERTIES",), role="an owner's property manager (lease)",
           domains=("tiner.com",)),
    Sender("TMT Property Services", SourceKind.PROPERTY_MANAGER, ("TMT PROPERTY",),
           role="an owner's property manager (lease)", domains=("tmtpropertyservices.com",)),
    Sender("Sac Placer Properties", SourceKind.PROPERTY_MANAGER, ("SAC PLACER", "SACPLACER"),
           role="an owner's property manager (lease)"),
    Sender("Allegiance Property Management", SourceKind.PROPERTY_MANAGER, ("ALLEGIANCE PROPERTY",),
           role="an owner's property manager (lease)"),
    # The association's own assessment statement, mailed back to the box by an owner with a payment.
    Sender("An owner (the association's own statement)", SourceKind.OWNER, ("REGULAR ASSESSMENT MONTHLY MEMBER DUES",),
           role="an owner's account; Civil Code 5215 keeps an individual owner's records from other members"),
    Sender("PayHOA", SourceKind.PLATFORM, ("PAYHOA",), payhoa_vendor="PayHOA", role="association management platform",
           domains=("payhoa.com",)),
    Sender("PostScanMail", SourceKind.PLATFORM, ("POSTSCANMAIL", "POST SCAN MAIL"), payhoa_vendor="Post Scan Mail", role="mailbox",
           domains=("postscanmail.com",)),
    # Vendors the association pays
    Sender("California Builder Services", V, ("CALIFORNIA BUILDER SERVICES",), role="reserve study preparer",
           domains=("cabuilderservices.com",)),
    Sender("All Year Pressure Washing", V, ("ALL YEAR PRESSURE",), payhoa_vendor="All Year Pressure Washing"),
    Sender("California Deck Inspection", V, ("CALIFORNIA DECK INSPECTION",), payhoa_vendor="California Deck Inspection, LLC",
           role="balcony inspection"),
    Sender("E&R Landscaping", V, ("E R LANDSCAPING",), payhoa_vendor="E&R Landscaping", role="landscaping"),
    # Added by the board 2026-09-29 from the contracts and proposals in the library. None is in PayHOA's vendor directory yet.
    Sender("Bravo Security Services", V, ("BRAVO SECURITY",), role="security patrol (daily reports, 2023)"),
    # Bark and mulch installation, 2025: its quotes come from acceleratedwaste.com under the letterhead
    # "RCS TC", in a file named "1JR Landscaping Quote"; the bank pays "RCS TC LLC", with no PayHOA vendor set.
    Sender("RCS TC", V, ("RCS TC", "1JR LANDSCAPING"), role="bark and mulch installation", domains=("acceleratedwaste.com",)),
    # Doors: the mailbox room and storage closet doors, 2026 (a deposit before materials are ordered, then the balance).
    Sender("Industrial Door Company", V, ("INDUSTRIAL DOOR",), role="doors", domains=("idc-sac.com",)),
    Sender("Flock Safety", V, ("FLOCK GROUP", "FLOCK SAFETY"), role="license plate reader cameras (ALPR)", domains=("flocksafety.com",)),
    Sender("CalPro Construction & Painting", V, ("CALPRO", "THINKCALPRO"), role="balcony deck resealing proposal",
           domains=("thinkcalpro.com",)),
    Sender("Top Garden Landscaping", V, ("TOP GARDEN",), role="landscaping proposal and agreement"),
    Sender("Excel Painting and Striping", V, ("EXCEL PAINTING",), payhoa_vendor="Excel Painting and Striping"),
    Sender("GoodLife Construction", V, ("GOODLIFE", "GOOD LIFE CONSTR"), payhoa_vendor="GoodLife Construction Inc.", domains=('goodlifeconstruction.com',)),
    Sender("HighClass Window and Gutter", V, ("HIGHCLASS",), payhoa_vendor="HighClass Window and Gutter", role="gutter cleaning"),
    Sender("JB Bostick Company", V, ("BOSTICK",), payhoa_vendor="JB BOSTICK COMPANY", role="paving"),
    Sender("Jensen Landscape", V, ("JENSEN LANDSCAPE",), payhoa_vendor="Jensen Landscape", role="landscaping", domains=('jensencorp.com',)),
    Sender("LeDoux Backflow Testing Services", V, ("LEDOUX",), payhoa_vendor="LeDoux Backflow Testing Services", role="backflow testing", domains=('ledouxbackflow.com',)),
    Sender("Mirowski Electric", V, ("MIROWSKI",), payhoa_vendor="Mirowski Electric", role="electrical"),
    Sender("Monarch Landscape", V, ("MONARCH LANDSCAPE",), payhoa_vendor="Monarch Landscape", role="landscaping", domains=('monarchlandscape.com',)),
    Sender("North American Home Services", V, ("NORTH AMERICAN HOME",), payhoa_vendor="North American Home Services", domains=('nahspro.com',)),
    Sender("ProActive Pest Control", V, ("PRO ACTIVE PEST", "PROACTIVE PEST"), payhoa_vendor="Pro Active Pest Control", role="pest control", domains=('beproactivepestcontrol.com',)),
    Sender("Pro Elections", V, ("PRO ELECTIONS",), payhoa_vendor="Pro Elections LLC", role="inspector of elections", domains=('pro-ei.com',)),
    Sender("Summit Roofing Company", V, ("SUMMIT ROOFING",), payhoa_vendor="SUMMIT ROOFING COMPANY, INC.", role="roofing"),
    Sender("Sac Val Plumbing", V, ("SAC VAL PLUMBING",), payhoa_vendor="Sac Val Plumbing", role="plumbing"),
    Sender("Signal Service", V, ("SIGNAL SERVICE", "ANGELS CAMP"), payhoa_vendor="Signal Service Inc", role="fire alarm monitoring", domains=('signalserviceinc.net', 'signalserviceinc.com')),
    Sender("TaskForge", V, ("TASKFORGE",), payhoa_vendor="TaskForge"),
    Sender("The Fire Sprinkler Company", V, ("FIRE SPRINKLER COMPANY",), payhoa_vendor="The Fire Sprinkler Company", role="fire sprinklers", domains=('thefiresprinklercompany.com',)),
    Sender("The Sign Factory", V, ("SIGN FACTORY",), payhoa_vendor="The Sign Factory", role="signs"),
)


def _with_private(sender: Sender) -> Sender:
    """A sender with its private facts (data/spec/mystique/senders.json): which unit an owner's property manager serves, and
    match words that are a person's name."""
    from dataclasses import replace

    from jason.community.private import facts

    private = facts("senders", profile="mystique")
    role = (private.get("roles") or {}).get(sender.name)
    extra = tuple((private.get("words") or {}).get(sender.name, ()))
    if not role and not extra:
        return sender
    return replace(sender, role=role or sender.role, words=sender.words + extra)


SENDERS: tuple[Sender, ...] = tuple(_with_private(s) for s in _SENDERS)
