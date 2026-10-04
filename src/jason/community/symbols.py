"""Closed sets for the Mystique specification. JSON stores the values; code uses the members."""

from __future__ import annotations

from enum import Enum, IntEnum


class Parity(Enum):
    """Which street numbers a flood building covers."""

    ODD = "odd"
    EVEN = "even"
    ANY = "any"


class Street(Enum):
    MACON_DR = "MACON DR"
    ENCHANTED_WALK = "ENCHANTED WALK"
    MAGICAL_WALK = "MAGICAL WALK"
    MESMERIZING_WALK = "MESMERIZING WALK"
    WHIMSICAL_LN = "WHIMSICAL LN"


class Building(IntEnum):
    """Flood building number. Members compare equal to that integer."""

    BLDG_1 = 1
    BLDG_2 = 2
    BLDG_3 = 3
    BLDG_4 = 4
    BLDG_5 = 5
    BLDG_6 = 6
    BLDG_7 = 7
    BLDG_8 = 8


class DeveloperDelivery(Enum):
    """One document Title 10 section 2792.23(a) requires the subdivider to deliver.

    ``PUBLIC_REPORT`` is the Bureau public report under Business and Professions
    Code section 11018.5. It is not one of those paragraphs.
    """

    SUBDIVISION_MAP = "subdivision_map"
    CONDOMINIUM_PLAN = "condominium_plan"
    COMMON_AREA_DEED = "common_area_deed"
    DECLARATION = "declaration"
    ARTICLES = "articles"
    BYLAWS = "bylaws"
    USE_RULES = "use_rules"
    MAINTENANCE_PLANS = "maintenance_plans"
    NOTICE_OF_COMPLETION = "notice_of_completion"
    BOND = "bond"
    WARRANTY = "warranty"
    INSURANCE = "insurance"
    CONTRACT = "contract"
    MEMBERSHIP_REGISTER = "membership_register"
    BOOKS = "books"
    MINUTES = "minutes"
    RECIPROCAL_INSTRUMENT = "reciprocal_instrument"
    PUBLIC_REPORT = "public_report"


class AssociationRecord(Enum):
    """One kind of association record named in Civil Code 5200.

    The citation for each member lives in ``jason.community.records``.
    """

    FINANCIAL_DISCLOSURE = "financial_disclosure"
    TRANSFER_FINANCIAL = "transfer_financial"
    INTERIM_FINANCIAL = "interim_financial"
    EXECUTED_CONTRACT = "executed_contract"
    VENDOR_APPROVAL = "vendor_approval"
    TAX_RETURN = "tax_return"
    RESERVE_ACCOUNT = "reserve_account"
    MINUTES = "minutes"
    MEMBERSHIP_LIST = "membership_list"
    CHECK_REGISTER = "check_register"
    GOVERNING_DOCUMENTS = "governing_documents"
    RESERVE_LITIGATION_ACCOUNTING = "reserve_litigation_accounting"
    ENHANCED = "enhanced"
    ELECTION_MATERIALS = "election_materials"
    ELEVATED_ELEMENT_REPORT = "elevated_element_report"


class DocumentRule(Enum):
    GOVERNING_ROOT = "governing-root"
    ELECTION_RULES = "election-rules"
    ANNEXATIONS = "annexations"
    POLICIES = "policies"
    RESOLUTIONS = "resolutions"
    DRE_REPORTS = "dre-reports"
    GRANT_DEEDS = "grant-deeds"
    PLANS = "plans"
    MAPS = "maps"
    INSURANCE_CURRENT = "insurance-current"


class PublicDrive(Enum):
    """Public Drive folder ids embedded on the site or named in a sync rule."""

    GOVERNING_DOCUMENTS = "1nPj0V31Ow8cljf5PlMLFU5Ig5M2_CksY"
    POLICIES = "1W4bU8gi-oBsDKzaxZW6tjytnFkWC0XH_"
    RESOLUTIONS = "1DHFt7PHrm3ggCTEntFzxuF3BclAuzDHp"
    ANNEXATIONS = "1kmG5x3tAoOyzsuVVctQr5YTNzx44dksw"
    DRE_REPORTS = "14d8ky7wyxG3H58i_-rnbLNKzYXe4yyee"
    DEEDS = "1PGpjai14WeiqlOIoos09KAqwrjISaO9t"
    PLANS = "1JFIRnLGeiljRPFmoGnYn8tk5jXPpGmKW"
    MAPS = "1JOkXoesEntjLSAlYtjhKzl8yI6PyQ5ni"
    INSURANCE = "19ypA08BtmlSTJWcYlt3o3HLjXzplGoc_"
    AUDIO_BOOK = "1XyvQDfG5UC2dh5fNkC3lqk08nWEOcVfy"
    PROPOSED = "1bwrvs806KLP41uCXq8DTJVBUbYQ80XGI"
    APPLICATIONS = "1sInTlCKG8GVCJ3lRVyvOHHRd6b2Z2exD"
    POLICIES_OLD = "1_1b4zGLdvxIf9ztyzXNV8ujipZRqYeJI"
    JOHN_LAING = "1Ta98-Ekr2-Tf-Cbd1_Y_akgT0CFURUfW"
    WATT = "17ohMjY8-KrTSPbKY4DpJEBOw3pFnguY2"


class DocumentCategory(Enum):
    """The shelf a document belongs on. The kind says which document it is."""

    GOVERNING = "governing"
    MEETING = "meeting"
    MEMBERSHIP = "membership"
    INSURANCE = "insurance"
    CONTRACT = "contract"
    FINANCIAL = "financial"
    PROPERTY = "property"
    ELECTION = "election"
    LEGAL = "legal"
    REFERENCE = "reference"


class DocumentKind(Enum):
    """What the document is. ``FileKind`` is only the Drive format."""

    DECLARATION = "declaration"
    AMENDMENT = "amendment"
    BYLAWS = "bylaws"
    ARTICLES = "articles"
    POLICY = "policy"
    ELECTION_RULES = "election_rules"
    ANNEXATION = "annexation"
    RESOLUTION = "resolution"
    MINUTES = "minutes"
    TREASURER_REPORT = "treasurer_report"
    MEMBERSHIP_LIST = "membership_list"
    INSURANCE_POLICY = "insurance_policy"
    CONTRACT = "contract"
    LEASE = "lease"
    CONDOMINIUM_PLAN = "condominium_plan"
    MAP = "map"
    GRANT_DEED = "grant_deed"
    DRE_REPORT = "dre_report"
    PLAN_SET = "plan_set"
    # Governing, beyond the recorded instruments.
    OPERATING_RULES = "operating_rules"
    # Meetings: Civil Code 5200(a)(8) counts agendas with minutes; executive sessions are outside it.
    AGENDA = "agenda"
    EXECUTIVE_SESSION = "executive_session"
    NOTICE = "notice"
    COMMITTEE_REPORT = "committee_report"
    # Elections: 5200(c).
    BALLOT = "ballot"
    ELECTION_RESULTS = "election_results"
    # Money: interim statements (a)(3), the Article 7 disclosures (a)(1), tax returns (a)(6), enhanced records (b).
    FINANCIAL_STATEMENT = "financial_statement"
    BANK_STATEMENT = "bank_statement"
    BUDGET = "budget"
    RESERVE_STUDY = "reserve_study"
    FINANCIAL_REVIEW = "financial_review"
    TAX_RETURN = "tax_return"
    ANNUAL_DISCLOSURE = "annual_disclosure"
    INVOICE = "invoice"
    # A utility's bill on a published tariff (SMUD, the City): parsed and checked by jason.community.utility, not a vendor invoice.
    UTILITY_BILL = "utility_bill"
    TAX_BILL = "tax_bill"
    # Vendors and property.
    PROPOSAL = "proposal"
    INSPECTION_REPORT = "inspection_report"
    # The Civil Code 5551 (SB 326) inspection of exterior elevated elements: its report is a 5200(a)(15) record.
    ELEVATED_ELEMENT_INSPECTION = "elevated_element_inspection"
    EVIDENCE_OF_INSURANCE = "evidence_of_insurance"
    # Insurance claims: the carrier's claims history on a policy, its letters on one claim, what it paid, the claim's
    # repair paperwork, its estimate of the loss, and the police report a loss can rest on.
    LOSS_RUN = "loss_run"
    CLAIM_LETTER = "claim_letter"
    CLAIM_PAYMENT = "claim_payment"
    CLAIM_AUTHORIZATION = "claim_authorization"
    CLAIM_ESTIMATE = "claim_estimate"
    POLICE_REPORT = "police_report"
    # A manager's periodic report of its open cases (the prior manager's weekly "Case Performance" report).
    MANAGER_CASE_REPORT = "manager_case_report"
    IMAGE = "image"
    # Legal and collections.
    SETTLEMENT = "settlement"
    LEGAL_CORRESPONDENCE = "legal_correspondence"
    LEGAL_BRIEF = "legal_brief"
    RECORDED_LIEN = "recorded_lien"
    DELINQUENCY_NOTICE = "delinquency_notice"
    # Members.
    OWNER_HISTORY = "owner_history"
    OWNER_STATEMENT = "owner_statement"
    ESCROW_REQUEST = "escrow_request"
    FORM = "form"
    # Reference: a blank template the platform ships, or a third party's letter, is not an association record.
    TEMPLATE = "template"
    CORRESPONDENCE = "correspondence"
    VIOLATION_NOTICE = "violation_notice"
    RESALE_DISCLOSURE = "resale_disclosure"
    SECURITY_REPORT = "security_report"
    AUDIO = "audio"
    # The subdivider's securities to the association under the Real Estate Commissioner's regulations (10 CCR 2792.4,
    # 2792.9, 2792.10; B&P 11018.5) and what releases them.
    SECURITY_AGREEMENT = "security_agreement"
    SUBSIDY_AGREEMENT = "subsidy_agreement"
    SURETY_BOND = "surety_bond"
    BOND_RELEASE = "bond_release"


class FileKind(Enum):
    GOOGLE_SITE = "google_site"
    GOOGLE_DOC = "google_doc"
    GOOGLE_SHEET = "google_sheet"
    DRIVE_FOLDER = "drive_folder"


class KnownFile(Enum):
    """Well-known Drive files. The id lives on `KnownAnchor` in `mystique`."""

    PORTAL = "portal"
    MINUTES_2026_07_07 = "minutes_2026_07_07"
    ALPR_POLICY = "alpr_policy"
    ALPR_SAFE_LIST = "alpr_safe_list"
    INSURANCE_WORKBOOK = "insurance_workbook"
    MEMBERSHIP = "membership"
    RESERVE_COMPONENTS = "reserve_components"


class CostCenter(Enum):
    """Where a reserve component's cost is carried."""

    COMMON = "common"
    PHASE_1_AND_2 = "p1_p2"
    PHASE_3_TO_8 = "p3_p8"


class ComponentMajor(Enum):
    """The reserve study's component classification."""

    CONCRETE = "concrete"
    DECKING = "decking"
    FENCING = "fencing"
    LANDSCAPING = "landscaping"
    PLUMBING = "plumbing"
    BACKFLOW = "backflow"
    LIGHTING = "lighting"
    MISCELLANEOUS = "miscellaneous"
    PAINTING = "painting"
    PAVING = "paving"
    ROOFING = "roofing"
    SAFETY = "safety"
    ELEVATED_ELEMENTS = "elevated_elements"
    SIGNAGE = "signage"
    STRUCTURAL = "structural"


class MembershipTab(Enum):
    """Tabs on the membership workbook worth keeping beside PayHOA."""

    PROPERTIES = "Properties"
    ROSTER = "Roster"
    BUILDINGS = "Buildings"


class PayhoaFolder(Enum):
    """PayHOA library folders that Drive sync and publish target."""

    GOVERNING_DOCUMENTS = "governing_documents"
    ANNEXATIONS = "annexations"
    POLICIES = "policies"
    RESOLUTIONS = "resolutions"
    ELECTIONS = "elections"
    DRE_PUBLIC_REPORTS = "dre_public_reports"
    GRANT_DEEDS = "grant_deeds"
    GRANT_DEEDS_COMMON_AREAS = "grant_deeds_common_areas"
    PLANS = "plans"
    MAPS = "maps"
    INSURANCE = "insurance"
    FINANCIALS = "financials"
    MEETINGS = "meetings"
    MEETINGS_2026 = "meetings_2026"
    CONTRACTS = "contracts"
    LEGAL = "legal"
    LEASE_AGREEMENTS = "lease_agreements"
    RESALE_DOCUMENTS = "resale_documents"
    EMAIL_ATTACHMENTS = "email_attachments"


class SitePage(Enum):
    HOME = "home"
    RECORDS = "records"
    PLANS = "plans"
    REPORTS = "reports"
    INSURANCE = "insurance"
    FINANCIALS = "financials"
    ESCROW = "escrow"


class InsuranceVisit(Enum):
    """What a walk of the Insurance folder does with one path."""

    YEAR_FOLDER = "year_folder"
    ROOT_FILE = "root_file"
    SKIP = "skip"


class PolicyKind(Enum):
    """A line on the Insurance sheet. Flood is one policy per building."""

    MASTER = "master"
    UMBRELLA = "umbrella"
    FIDELITY = "fidelity"
    DIRECTORS_AND_OFFICERS = "directors_and_officers"
    WORKERS_COMP = "workers_comp"
    FLOOD = "flood"


class PortalPlatform(Enum):
    """The software a vendor's customer portal runs on; one client per platform, one spec row per vendor."""

    FIELDPORTALS = "fieldportals"
    SIGNAL_SERVICE = "signal_service"


class Utility(Enum):
    """Which bill portal owns a PayHOA transaction. Order in the spec is the match order."""

    SMUD = "smud"
    CITY_OF_SACRAMENTO = "city_sac"
