"""The manager's duties under the Davis-Stirling Act, each tied to its records, its cadence, and where the governing documents speak to it.

The duty anchors in docs/community-manager.md are data here, so a brief
can be built for one: the statute sections, the artifact the duty leaves
behind, the association records it rests on, when it recurs, the Jason
command or tool that produces the artifact, and the questions to put to the
governing documents and the law notes. The passages those questions find
are the documents' own words, for the person to read; a duty brief is a
map, and it decides nothing.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from jason.community.symbols import AssociationRecord


class Cadence(Enum):
    CONTINUOUS = "continuous"
    MONTHLY = "monthly"
    ANNUAL = "annual"
    EVERY_THREE_YEARS = "every three years"
    ON_EVENT = "on the event"


@dataclass(frozen=True)
class Duty:
    anchor: str
    keeps_straight: str
    sections: str
    artifact: str
    cadence: Cadence
    when: str
    records: tuple[AssociationRecord, ...]
    queries: tuple[str, ...]
    produce: str
    limit: str = ""


DUTIES: tuple[Duty, ...] = (
    Duty(
        "Governing documents", "Which instrument controls, and which sections an amendment changes",
        "CIV 4150, 4205, 4250 to 4275, 4340 to 4370",
        "GoverningDocument and Amendment records; the recorded copies; the association's record in the index",
        Cadence.CONTINUOUS, "whenever an instrument is recorded or a rule adopted",
        (AssociationRecord.GOVERNING_DOCUMENTS,),
        ("amendment of the declaration vote of the members", "operating rules adoption notice to members", "conflict between the declaration and the bylaws"),
        "jason property-history (association.md), document_readings, records_request",
    ),
    Duty(
        "Developer file", "Whether the association holds what the subdivider had to deliver",
        "BPC 11018.5, 11018.6; Title 10 sections 2792.1, 2792.15, 2792.23",
        "developer_file(): each delivery with its pins, an empty delivery a missing basis",
        Cadence.CONTINUOUS, "once, then whenever a delivery turns up",
        (AssociationRecord.GOVERNING_DOCUMENTS,),
        ("condominium plan", "common area conveyed to the association", "maintenance manual warranties delivered by declarant"),
        "association_records, records_request",
    ),
    Duty(
        "Notice", "Whether a notice is individual or general, and whether delivery can be proved",
        "CIV 4035 to 4055, 4041",
        "A notice record: who, which section, which method, when",
        Cadence.ON_EVENT, "each notice",
        (AssociationRecord.MINUTES,),
        ("notice to owners delivery by mail or electronic", "address for official communications"),
        "the annual policy statement carries the address (CIV 4035); the communications task drafts and logs",
    ),
    Duty(
        "Meetings", "Open board meetings, agenda, executive session, minutes, member meetings",
        "CIV 4900 to 4955, 5000, 5450",
        "Agenda, minutes, executive-session log",
        Cadence.MONTHLY, "notice at least four days before a board meeting (two for executive session only); minutes available within thirty days",
        (AssociationRecord.MINUTES,),
        ("board meetings notice agenda open to members", "annual meeting of the members quorum", "executive session"),
        "the Meetings folder in PayHOA; minutes are a 5200 record",
    ),
    Duty(
        "Elections", "Election rules, inspector, ballots, retention",
        "CIV 5100 to 5145",
        "Election file; do not run the election",
        Cadence.ANNUAL, "at the end of a director's term and at least every four years; materials kept one year",
        (AssociationRecord.ELECTION_MATERIALS, AssociationRecord.GOVERNING_DOCUMENTS),
        ("election of directors secret ballot inspector of elections", "term of office of directors", "nomination procedure candidates"),
        "the Elections folder; the Election Rules policy",
        "Jason does not run an election or count ballots.",
    ),
    Duty(
        "Records", "What a member may copy, how long it is kept, what is withheld, including the membership list",
        "CIV 5200 to 5240, 5260",
        "The records request and the redaction reason; the membership list and a mailing are separate jobs",
        Cadence.ON_EVENT, "current fiscal year within ten business days, the two prior within thirty days; minutes within thirty days of the meeting",
        tuple(AssociationRecord),
        ("inspection of books and records by members", "membership list purpose reasonably related"),
        "records_inventory; jason ownership-sheet; the Membership workbook is the list",
        "Jason does not decide that a member's purpose is good enough, and does not write the Membership workbook.",
    ),
    Duty(
        "Annual disclosures", "Budget report, policy statement, and the notice that they are available",
        "CIV 5300, 5305, 5310, 5320",
        "The disclosure packet and the date it went out",
        Cadence.ANNUAL, "thirty to ninety days before the fiscal year ends; the reviewed financial statement within 120 days after it closes when gross income exceeds $75,000",
        (AssociationRecord.FINANCIAL_DISCLOSURE, AssociationRecord.RESERVE_ACCOUNT, AssociationRecord.INTERIM_FINANCIAL),
        ("annual budget report reserve summary distributed to members", "fiscal year of the association", "assessment collection policy annual notice"),
        "the Financials folder; the reserve components sheet; jason reserve-study",
    ),
    Duty(
        "Money", "Monthly board review of finances, reserve use, reserve study",
        "CIV 5500 to 5520, 5550 to 5580",
        "The review checklist; the reserve study is a vendor product",
        Cadence.EVERY_THREE_YEARS, "the board reviews finances monthly (CIV 5500); a visual inspection and study at least every three years, reviewed each year (CIV 5550); reserves borrowed for operating needs are repaid within a year (CIV 5515)",
        (AssociationRecord.RESERVE_ACCOUNT, AssociationRecord.INTERIM_FINANCIAL, AssociationRecord.CHECK_REGISTER),
        ("reserve fund investment withdrawal of reserve funds", "reserve study major components", "signatures required for withdrawal from reserve account"),
        "jason reserve-study and jason review-transactions; the Financials folder",
    ),
    Duty(
        "Assessments", "Levy, increase notice, delinquency, pre-lien notice, lien, foreclosure limits",
        "CIV 5600 to 5740",
        "The ledger and the statutory notice; handoff only",
        Cadence.MONTHLY, "an increase needs thirty to sixty days' notice (CIV 5615); the pre-lien notice thirty days before a lien (CIV 5660); foreclosure only over the CIV 5720 threshold",
        (AssociationRecord.FINANCIAL_DISCLOSURE, AssociationRecord.CHECK_REGISTER),
        ("regular assessments special assessments increase limit", "delinquent assessments late charges interest lien", "notice of delinquent assessment foreclosure"),
        "jason who-owes and who-owes-sheet; assessment_liens; the Assessment Collection Policy",
        "Jason does not lien, foreclose, or submit an account to a collection agency.",
    ),
    Duty(
        "Insurance", "Liability thresholds, fidelity amount, notice when coverage changes",
        "CIV 5800 to 5810",
        "The policy register: kind, number, limit, renewal, building",
        Cadence.ANNUAL, "at each renewal, and immediately on a nonrenewal without replacement (CIV 5810)",
        (AssociationRecord.EXECUTED_CONTRACT,),
        ("insurance the association shall maintain liability fidelity", "flood insurance policy buildings", "insurance summary annual budget report"),
        "the insurance workbook tab and the Insurance folder; jason insurance-sheet",
    ),
    Duty(
        "Maintenance", "Who repairs the unit, exclusive use, and common area",
        "CIV 4775 to 4785",
        "The maintenance matrix from the declaration, not from a file name",
        Cadence.CONTINUOUS, "each request",
        (AssociationRecord.EXECUTED_CONTRACT,),
        ("maintenance responsibility of the association common area", "owner responsible for maintenance of the unit exclusive use common area", "repair of damage caused by an owner"),
        "jason review-requests; the maintenance matrix",
    ),
    Duty(
        "Exclusive use", "Whether the board may grant a member exclusive use of common area, and on what vote or exception",
        "CIV 4145, 4600, 4605",
        "The grant file: the portion, the vote or the 4600(b) exception, consideration, who insures",
        Cadence.ON_EVENT, "each request",
        (AssociationRecord.MINUTES, AssociationRecord.GOVERNING_DOCUMENTS),
        ("exclusive use common area designated patio balcony garage", "grant of exclusive use of common area vote"),
        "jason review-requests flags a 4600 question",
        "Jason does not grant exclusive use; an architectural approval is not a grant.",
    ),
    Duty(
        "Architecture", "Application, decision, and the timeline in the statute and the documents",
        "CIV 4760, 4765",
        "The request file",
        Cadence.ON_EVENT, "each application, decided within the time the documents set",
        (AssociationRecord.MINUTES,),
        ("architectural review committee approval of improvements", "application for architectural approval decision in writing", "reasonable modification accommodation disability"),
        "jason review-requests",
        "Jason does not approve or deny.",
    ),
    Duty(
        "Protected uses", "Flags, signs, rentals, EV charging, solar, ADUs, drought landscaping",
        "CIV 4700 to 4753",
        "A flag on the request when a protected-use section may apply",
        Cadence.ON_EVENT, "each request",
        (AssociationRecord.GOVERNING_DOCUMENTS,),
        ("leasing rental of units restrictions", "solar energy system installation roof", "electric vehicle charging station", "signs flags display"),
        "jason review-requests",
    ),
    Duty(
        "Transfers", "Escrow document list, fees, the form in CIV 4528",
        "CIV 4525 to 4545, 4575",
        "The resale packet",
        Cadence.ON_EVENT, "each sale, within ten days of the request (CIV 4530)",
        (AssociationRecord.TRANSFER_FINANCIAL, AssociationRecord.GOVERNING_DOCUMENTS),
        ("sale of a unit notice to the association escrow documents", "transfer fee"),
        "escrow_brief; solar_status; the Resale Documents folder",
    ),
    Duty(
        "Discipline", "Fine schedule, hearing, IDR before a lawsuit, ADR notice",
        "CIV 5850 to 5965, 5975",
        "The hearing record and the IDR offer",
        Cadence.ON_EVENT, "notice of the hearing at least ten days before (CIV 5855)",
        (AssociationRecord.MINUTES, AssociationRecord.GOVERNING_DOCUMENTS),
        ("fines hearing notice opportunity to be heard", "enforcement of the declaration remedies", "dispute resolution internal alternative"),
        "the Fine Schedule and Enforcement Policy; jason violations",
        "Jason does not impose a penalty.",
    ),
    Duty(
        "Pest control", "Who controls which pests, what the vendor must be licensed and insured for, how residents are told, "
        "and which pesticides California restricts",
        "CIV 4775, 4780, 4785, 5200; BPC 8505, 8516, 8538, 8555, 8560, 8692, 8505.17; FAC 12838, 12978.7",
        "The pest program brief: each product by EPA number with its label and safety data sheet, the rodent monitoring "
        "record, the vendor's inspection reports and open recommendations, and the license and insurance on file",
        Cadence.CONTINUOUS, "every service visit; the license and insurance at each renewal; a new notice when a pesticide changes (BPC 8538)",
        (AssociationRecord.EXECUTED_CONTRACT, AssociationRecord.VENDOR_APPROVAL, AssociationRecord.ENHANCED),
        ("wood destroying pests and organisms inspection and preventive program", "pest control within your unit",
         "temporary relocation notice treatment occupants accommodations"),
        "jason pests, pest_program, vendor_portal",
        "The declaration decides who pays (CC&Rs Article 7, Section 7; the Owner's Manual leaves in-unit pest control to the owner). "
        "The posting and post-application notices are the vendor's duty under 16 CCR 1970.41 and 1970.42; the pyrethroid "
        "surface-water limits are 3 CCR 6970. Jason reads the vendor's record; it does not direct an application.",
    ),
    Duty(
        "Manager's own duties", "Pre-contract disclosure, certification, license, referral fees, trust account, escrow delivery",
        "CIV 5375, 5375.5, 5376, 5380; BPC 11504, 11505",
        "The disclosure file and the trust-account rule",
        Cadence.ANNUAL, "the disclosure before the contract and on change",
        (AssociationRecord.EXECUTED_CONTRACT,),
        ("management agreement managing agent", "funds held by the managing agent trust account"),
        "the Contracts folder",
    ),
)


def duty_named(anchor: str) -> Duty | None:
    wanted = " ".join(anchor.lower().split())
    for duty in DUTIES:
        if duty.anchor.lower() == wanted or duty.anchor.lower().startswith(wanted):
            return duty
    return None
