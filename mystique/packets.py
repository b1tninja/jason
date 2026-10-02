"""Mystique's packets: what each delivers, in order, and where each year's copy of each part is found.

The annual packet follows the October 1, 2026 research (data/briefs/research/research-finance.md): a first page with
the Civil Code 5320 notice, Part A (the annual budget report, 5300) with its enclosures, then Part B (the annual policy
statement, 5310) with the collection and enforcement policies. The 25-26 packet was one Doc ("Annual Disclosures",
1kovE3GFs3fqS82ZUfv_3S2OFShid6h9UPG3nBL-ylj4) with four "[ INSERT ]" pages spliced in by hand; the assembler does that
now. The templates' text is in packet_templates/, used once to make the Docs on the Letterhead; after that the Docs are
the originals (their ids below). The values here are the standing ones; a year's own (the assessment, the board's
statements on deferral, special assessments, and funding) go in data/packets/<packet>-<year>/values.json.
"""

from __future__ import annotations

from jason.community.packets import Packet, Part, PartSource, SourceKind

from jason.community.symbols import Building

from .help import PORTAL_SIGN_UP
from .insurance import FLOOD_ZONE
from .templates import FOOTER, MAILING_ADDRESS_LINES

# The template Docs (My Drive/Templates), made October 1, 2026 by `jason packet annual-disclosures --make-templates --yes`.
BUDGET_REPORT_DOC = "1SPbdIdfGmYmq6OTsjOJmRpv6JEp9ky43R8bYYoZTRq4"
POLICY_STATEMENT_DOC = "1bj351KwYhSvcEIVRi_QvYEJIF_Ja7i5UbVTt1tmlBbo"
# The owner information form (Civil Code 4041), from forms.OWNER_INFO, made October 1, 2026.
OWNER_FORM_DOC = "1lfmHwJbnWXHd0kSYzOeErwYs1qcV4vOwzw5MFoaNek8"

T, L, D, G = SourceKind.TEMPLATE, SourceKind.LIBRARY, SourceKind.DRIVE, SourceKind.GENERATED

# In the annual packet the form is the solicitation for the next year's cycle; this fall it also goes out on its own,
# early enough for the answers to be entered 30 days before the reports (4041(b)(1)).
OWNER_FORM_PART = Part("Owner Information and Notice Delivery Preferences", PartSource(T, OWNER_FORM_DOC, markdown="form:owner-info"),
                       "CIV 4041")

ANNUAL_DISCLOSURES = Packet(
    key="annual-disclosures",
    title="Annual Budget Report and Annual Policy Statement",
    task="annual-disclosures",
    parts=(
        Part("Cover and Annual Budget Report", PartSource(T, BUDGET_REPORT_DOC, markdown="annual-budget-report.md"), "CIV 5300, 5320"),
        Part("Pro forma operating budget", PartSource(L, pattern=r"^Financials/{year}/Pro Forma Budget"), "CIV 5300(b)(1)"),
        Part("Reserve summary and funding plan", PartSource(L, pattern=r"^Financials/{year}/Reserve Study"), "CIV 5300(b)(2)-(7), 5565",
             note="the study's summary pages; set the pages once the study is in"),
        Part("Assessment and Reserve Funding Disclosure Summary", PartSource(L, pattern=r"(?i)(5570|Reserve Funding Disclosure).*{year}"),
             "CIV 5300(e), 5570", note="often inside the reserve study; its assessment must equal the budget's"),
        Part("Insurance summary", PartSource(G, "insurance-summary"), "CIV 5300(b)(9)"),
        # The insurance section goes to every owner in full, each building with its own flood policy (the board's
        # choice of October 1, 2026, for thoroughness): the 5300(b)(9) summary may enclose the declarations pages.
        Part("Notice of the Association's insurance", PartSource(G, "letter:master-insurance-notice.html"), "CIV 5300(b)(9), 5810",
             note="the board's notice for the term; replace the letter when the master policy renews"),
        # The master package runs to 150 pages; only its declarations go out (the period, the property, and the
        # liability limits: pages 13-15 of the 25-26 package). The schedule of forms names the declarations too, so
        # the rule keys on the policy period and the limits headings, not the word.
        Part("Master policy declarations", PartSource(D, pattern=r"^My Drive/Insurance/\d{4}/Policy\s+ARD\s+PKG\s+{term}\.pdf$",
                                                      keep=r"POLICY PERIOD:|COVERAGES? AND LIMITS"), "CIV 5300(b)(9)"),
        Part("Certificate of Insurance", PartSource(L, pattern=r"^Insurance/Certificate of Insurance {prior}-{year}"), "CIV 5300(b)(9)"),
        Part("Assessor's Parcel Map", PartSource(L, pattern=r"^Insurance/Assessors Parcel Map"), required=False,
             note="shows each address is in the subdivision the certificate names"),
        Part("Flood insurance notice, Building {building}", PartSource(G, "letter:flood-notice.html"), "CIV 5300(b)(9)"),
        # The insurer's packet is a cover letter, a claims page, the declarations, and a privacy notice; only the
        # declarations page goes out (the notice covers what to do after a flood).
        Part("Flood policy declarations, Building {building}",
             PartSource(L, pattern=r"^Insurance/FLOOD POLICY \d\d-\d\d BLDG {building}\.pdf$", keep=r"INSURED NAME\(S\) AND MAILING ADDRESS"),
             "CIV 5300(b)(9)", note="the newest declarations on file; a renewal not yet issued is named in the notice"),
        # Each "in at least 10-point font on a separate piece of paper" (5300(b)(10), (11)).
        Part("FHA statement", PartSource(G, "fha-statement"), "CIV 5300(b)(10)", own_sheet=True),
        Part("VA statement", PartSource(G, "va-statement"), "CIV 5300(b)(11)", own_sheet=True),
        Part("Charges for Documents Provided", PartSource(L, pattern=r"(?i)Charges for Documents"), "CIV 5300(b)(12), 4528"),
        Part("Annual Policy Statement", PartSource(T, POLICY_STATEMENT_DOC, markdown="annual-policy-statement.md"), "CIV 5310, 5730, 5920, 5965"),
        Part("Assessment Collection Policy", PartSource(L, pattern=r"^Governing Documents/Policies/Assessment Collection Policy"),
             "CIV 5310(a)(6), (7)"),
        Part("Enforcement Policy and schedule of fines", PartSource(L, pattern=r"^Governing Documents/Policies/(Enforcement Policy|Fine Schedule)"),
             "CIV 5310(a)(8), 5850"),
        Part("Home Improvement Request Form", PartSource(L, pattern=r"Governing Documents/Forms/Home Improvement Request Form"),
             "CIV 5310(a)(10), 4765", required=False),
        Part("Disclosure regarding pending litigation", PartSource(L, pattern=r"^Disclosure Regarding Pending Litigation"), required=False),
        OWNER_FORM_PART,
    ),
    values=(
        ("DESIGNATED_RECIPIENT", "Secretary, Board of Directors, Mystique Community Association"),
        ("OFFICIAL_ADDRESS", FOOTER),
        # hoa@ (the general inbox) rather than board@, so official mail does not land in every director's inbox.
        ("OFFICIAL_EMAIL", "hoa@mystiquecommunity.com"),
        ("OVERNIGHT_ADDRESS", FOOTER + ". Couriers cannot deliver to the payment lockbox's P.O. Box; use this address for overnight payments."),
        ("POSTING_LOCATION", "The bulletin boards by the community mailboxes, and the Association's website, www.mystiquecommunity.com."),
        ("MINUTES_ACCESS", "Members may have copies of the minutes of any board meeting, approved or in draft, at no cost. Draft "
                           "minutes are available within 30 days of the meeting in PayHOA Documents, or from the designated recipient."),
        ("LOANS_STATEMENT", "The Association has no loans with an original term of more than one year."),
        ("FLOOD_ZONE", FLOOD_ZONE),
    ),
    variants=tuple(str(b.value) for b in Building),
)

# Four pages. The Mailroom adds its own address page and bills it, so they are five, and a sixth billed page adds
# $2.25 of postage a letter (PayHOA's pricing guide, October 1, 2026): how to sign in to PayHOA for the first time is
# on the cover, not a page of its own, and the last sheet's blank back costs nothing.
OWNER_INFORMATION = Packet(
    key="owner-information",
    title="Owner Information and Notice Delivery Preferences",
    task="",
    parts=(
        Part("How would you like to receive Association notices?", PartSource(G, "letter:owner-information-cover.html"), "CIV 4041"),
        OWNER_FORM_PART,
    ),
    values=ANNUAL_DISCLOSURES.values + (("PAYHOA_SIGN_UP", PORTAL_SIGN_UP),
                                        ("MAILING_ADDRESS", "\n".join(MAILING_ADDRESS_LINES)),
                                        ("MAILING_ADDRESS_INLINE", ", ".join(MAILING_ADDRESS_LINES))),
)

PACKETS: tuple[Packet, ...] = (ANNUAL_DISCLOSURES, OWNER_INFORMATION)
