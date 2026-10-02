"""Mystique's task prompts: for each kind of notice or review, what it turns on, which kinds of documents and records a
manager would read for it, and the questions an experienced manager asks.

A row names no statute section, no document section, and no figure. When the CC&Rs are amended, a policy is replaced,
or the law changes, the same row still leads to the right reading: retrieval finds the words in force
(``jason.community.context_pack``), and the review cites and quotes them. Findings about the current templates (a wrong
figure, a missing element) belong in the review and the research notes (``data/briefs``), never here.

``subjects`` ties the PayHOA broadcast templates and their Docs to a task. ``MANAGEMENT`` is the one fact about the
association the prompts state; the rest of ``Community.prompt_context()`` is read from the specification.
"""

from __future__ import annotations

from jason.community.prompts import Audience, FactSource, TaskKind, TaskPrompt
from jason.community.symbols import DocumentKind as K
from jason.community.templates import TemplateKind

MANAGEMENT = "self-managed by its volunteer board of directors, using PayHOA; there is no management company"

_DELIVERY = "how notices to members must be delivered, and to whom else they are owed"
_MEMBERS = ("Write for members: plain language, and say how to reach the board with questions.",)

TASK_PROMPTS: tuple[TaskPrompt, ...] = (
    TaskPrompt(
        TaskKind.INSURANCE_CHANGE,
        "Tell every member that the association's insurance renewed or changed, what it covers and does not, what owners "
        "must carry themselves, and how to prove coverage to a lender.",
        Audience.MEMBERS,
        topics=(
            "the association's duty to tell members when its insurance lapses, is canceled, or changes",
            "the insurance the association must carry, its limits, and its form",
            "each owner's duty to insure the unit, its improvements, and personal property, and required policy terms",
            "who pays a deductible after a covered loss, and guidelines for charging it",
            "the summary of insurance members receive each year",
            "insurance the association does not carry, such as earthquake",
            _DELIVERY,
            "notices owed to mortgage lenders",
        ),
        documents=(K.DECLARATION, K.AMENDMENT, K.BYLAWS, K.OPERATING_RULES, K.POLICY, K.RESOLUTION,
                   K.INSURANCE_POLICY, K.EVIDENCE_OF_INSURANCE, K.ANNUAL_DISCLOSURE),
        facts=(FactSource("insurance_policies", why="each policy's terms read from its declarations"),
               FactSource("insurance_review", why="renewals, carriers' letters, and premiums")),
        considerations=(
            "Against the prior term, did any coverage, limit, or deductible change, or did a policy lapse or end? Which "
            "change, if any, makes this notice a legal duty rather than a courtesy?",
            "Are each policy's carrier, term, limits, and deductibles stated as its declarations show them?",
            "Does it say what the association's insurance does not cover, including any peril it does not insure?",
            "Does it tell owners what insurance the governing documents require of them, and any terms their policy must carry?",
            "Does it explain who may bear a deductible, and coverage an owner can buy for an assessment?",
            "Does every attachment state the coverage correctly and consistently with the declarations?",
            "Will it reach each member the way the law and the member's choice require, and is anyone else owed notice?",
        ),
        guidance=(*_MEMBERS,
                  "Describe only coverage the declarations or the carrier's documents show; a policy's own words decide coverage.",
                  "Name a renewal as a renewal and a change as a change."),
        subjects=(r"(?i)change in insurance coverage.*master", r"(?i)\binsurance\b.*\bmaster policy\b"),
    ),
    TaskPrompt(
        TaskKind.FLOOD_RENEWAL,
        "Tell the members of a building that its flood policy renewed, what the policy covers, what owners should insure "
        "themselves, and how to give a lender proof.",
        Audience.SOME_MEMBERS,
        topics=(
            "flood insurance the association carries for each building, its policy form, and what it covers in the units",
            "flood coverage owners may need for their belongings and living expenses",
            "what lenders require as proof of flood insurance for a condominium",
            "the association's duty to tell members when a policy changes or lapses",
            _DELIVERY,
        ),
        documents=(K.DECLARATION, K.OPERATING_RULES, K.INSURANCE_POLICY, K.EVIDENCE_OF_INSURANCE, K.CORRESPONDENCE),
        facts=(FactSource("insurance_policies", (("policy", "flood"),), "each building's flood policy as its declarations read"),),
        considerations=(
            "Which building and policy is it, and do the form, term, limit, and deductible match the declarations page?",
            "What does the policy form cover inside the units, and what must owners insure themselves?",
            "Did anything change from the expiring term that all members, not just this building, must be told?",
            "What will a lender accept as proof, and can a lender be named on the association's policy?",
        ),
        guidance=(*_MEMBERS,
                  "A placeholder other than {first name} may not be filled; name the building in the text.",
                  "Do not promise what a lender will accept; lenders decide."),
        subjects=(r"(?i)change in insurance coverage.*flood", r"(?i)\bflood\b"),
    ),
    TaskPrompt(
        TaskKind.MEETING_NOTICE,
        "Notice of a board meeting, with its agenda, how to join, and members' rights to attend and speak.",
        Audience.MEMBERS,
        topics=(
            "notice of board meetings: how far ahead, what it contains, and where it is posted",
            "board meetings held by teleconference or video, and what the notice must tell members to join",
            "members' right to attend open meetings and to speak",
            "the agenda, and acting on matters not on it",
            "executive session",
            "the board's adopted meeting schedule, and regular as against special meetings",
            "minutes and members' access to them",
            "recording meetings",
        ),
        documents=(K.BYLAWS, K.RESOLUTION, K.POLICY, K.OPERATING_RULES, K.AGENDA, K.MINUTES, K.ANNUAL_DISCLOSURE),
        facts=(FactSource("meeting_records", why="the board's meetings, agendas, notices, and minutes"),
               FactSource("board_items", why="matters waiting on a board decision")),
        considerations=(
            "Is the notice given far enough ahead, and posted where the association says general notices are posted?",
            "Does it carry the agenda, or say where the agenda is?",
            "If the meeting has no physical location, does the notice include everything the law requires for that, and "
            "may this kind of meeting be held only remotely?",
            "Is the meeting correctly called regular or special under the adopted schedule?",
            "Does it state members' right to attend and speak, accurately?",
            "Are the date, time, and time zone right for that date?",
        ),
        guidance=(*_MEMBERS, "Do not promise that a recording will be deleted; a legal hold may apply."),
        subjects=(r"(?i)meeting of the board", r"(?i)board meeting"),
        template=TemplateKind.AGENDA,
    ),
    TaskPrompt(
        TaskKind.ANNUAL_DISCLOSURES,
        "The annual budget report and the annual policy statement to members, with every disclosure the law requires.",
        Audience.MEMBERS,
        topics=(
            "the annual budget report: when it is due and what it must contain",
            "the annual policy statement: when it is due and what it must contain",
            "the reserve study, the reserve funding plan, and the reserve disclosure form",
            "notice of an assessment increase",
            "the assessment collection and lien enforcement policy",
            "the discipline policy and the schedule of fines",
            "dispute resolution procedures",
            "architectural approval",
            "owners' addresses and delivery choices for notices",
            "the summary of the association's insurance",
            "fees for copies of records and documents",
        ),
        documents=(K.BYLAWS, K.POLICY, K.RESOLUTION, K.OPERATING_RULES, K.ELECTION_RULES, K.BUDGET, K.RESERVE_STUDY,
                   K.ANNUAL_DISCLOSURE, K.FINANCIAL_REVIEW),
        facts=(FactSource("budget_status", why="this year's budget against actual"),
               FactSource("reserve_study", why="the reserve study's plan and disclosure"),
               FactSource("association_calendar", why="the annual deadlines and when each was done")),
        considerations=(
            "Counting from the end of the fiscal year, when must each report go out, and is the plan on time?",
            "Are the budget report's items and the policy statement's items kept apart and each cited correctly?",
            "Does every item the packet lists have content behind it, and is anything the law requires missing?",
            "Do the figures on every form match the adopted budget and the reserve study?",
            "Are the fees and policies it encloses current and consistent with the law in force?",
            "Were owners asked for their delivery choices in time, and will each member receive it the way they chose?",
        ),
        guidance=(*_MEMBERS,),
        subjects=(r"(?i)annual disclosure", r"(?i)\b5310\b", r"(?i)budget report"),
    ),
    TaskPrompt(
        TaskKind.TREASURER_REPORT,
        "Share with members the monthly financial summary the board reviewed, without disclosing any owner's account.",
        Audience.MEMBERS,
        topics=(
            "the board's regular review of the association's finances",
            "members' rights to the association's financial records, and what may be withheld",
            "privacy of owners' accounts and delinquency information",
            "the annual review of the financial statements",
            "the accounting basis of the association's financial statements",
        ),
        documents=(K.BYLAWS, K.POLICY, K.RESOLUTION, K.TREASURER_REPORT, K.FINANCIAL_STATEMENT, K.BUDGET),
        facts=(FactSource("budget_status", why="budget against actual"), FactSource("bank_accounts", why="balances by account")),
        considerations=(
            "Is it clear what the report is and that it is shared as a courtesy, not as the board's own duty?",
            "Could anything in it identify an owner's account, even without a name?",
            "Does it tell members how to ask for the association's records?",
            "Is there a related duty (an annual review, a disclosure) the board should know is due?",
        ),
        guidance=("Summarize what the board reviewed; do not quote the law at members.",),
        subjects=(r"(?i)treasurer'?s report",),
    ),
    TaskPrompt(
        TaskKind.BALANCE_FORWARD,
        "Explain to one owner a balance carried over from a prior manager, with the account history and how to question it.",
        Audience.OWNER,
        topics=(
            "statements of an owner's account and how payments are applied",
            "late charges, interest, and fees an association may charge",
            "an owner's right to dispute a charge and to meet with the board",
            "the notice an association must give before recording a lien",
            "payment plans",
        ),
        documents=(K.DECLARATION, K.BYLAWS, K.POLICY, K.RESOLUTION),
        facts=(FactSource("association_collections", why="each account beside the association's liens"),),
        considerations=(
            "Does it give the itemized history behind the balance?",
            "Are the charges in it ones the governing documents and the law allow, at the amounts they allow?",
            "Does it tell the owner how to dispute the balance and meet with the board?",
            "Could it be mistaken for a collection or pre-lien notice, and does it need to say it is not one?",
        ),
        guidance=("One owner's account is confidential; write to that owner only.",),
        subjects=(r"(?i)forward balance", r"(?i)balance forward"),
    ),
    TaskPrompt(
        TaskKind.FIRE_SYSTEM_TESTING,
        "Tell the residents of the affected units when a fire alarm or fire sprinkler system will be inspected or tested, "
        "what will happen, and what they need to do.",
        Audience.SOME_MEMBERS,
        topics=(
            "inspection and testing of fire alarm systems, and how often",
            "inspection, testing, and maintenance of fire sprinkler systems, how often, and who may perform it",
            "the association's right to enter a unit and the notice owed before entry",
            "smoke alarm duties of owners and landlords",
            "who maintains fire protection equipment inside and outside the units",
            "keeping sprinkler heads clear and unpainted",
        ),
        documents=(K.DECLARATION, K.BYLAWS, K.OPERATING_RULES, K.CONTRACT, K.INSPECTION_REPORT, K.INVOICE),
        facts=(FactSource("association_calendar", why="the fire system inspections and when each was last done"),),
        considerations=(
            "Which system is being inspected, which standard applies to it, and is the vendor licensed for that work?",
            "Which buildings and units have the system, and is the notice going only to them?",
            "Is entry into units needed, and does the notice meet what the governing documents require before entry?",
            "What did the last inspection leave undone or find deficient that this visit needs access for?",
            "Does it tell residents what will happen and what to do (pets, alarms sounding, access, clearances)?",
        ),
        guidance=("An alarm test and a sprinkler inspection are different inspections; do not describe one as the other.",
                  "Ask residents not to call 911 for test alarms, and give a way to arrange access."),
        subjects=(r"(?i)fire alarm", r"(?i)sprinkler"),
    ),
    TaskPrompt(
        TaskKind.RULE_REMINDER,
        "A friendly reminder of a rule, quoting it correctly, before any enforcement.",
        Audience.OWNER,
        topics=(
            "what the declaration says on the rule's subject",
            "the operating rule itself in its current adopted form",
            "how the association enforces its rules: courtesy notices, hearings, and fines",
            "the schedule of fines and when a fine may be imposed",
            "a local ordinance on the same subject",
        ),
        documents=(K.DECLARATION, K.AMENDMENT, K.OPERATING_RULES, K.POLICY, K.NOTICE),
        considerations=(
            "Is the rule quoted from its current adopted version, with its number, and do two versions disagree?",
            "Does the declaration speak to the subject, and does the reminder rest on it?",
            "Does it threaten anything the enforcement policy and the law do not allow at this stage?",
            "Does it tell the owner how to respond, including that the matter may not be theirs?",
            "Is a local ordinance stricter or looser, and which controls for the association?",
        ),
        guidance=("A courtesy reminder is not a violation notice; keep it friendly and short.", "Never name who reported it."),
        subjects=(r"(?i)trash", r"(?i)reminder"),
    ),
    TaskPrompt(
        TaskKind.HEARING_NOTICE,
        "Notice to an owner of a hearing before the board on an alleged violation.",
        Audience.OWNER,
        topics=("notice of a disciplinary hearing: how far ahead, how delivered, and what it contains",
                "the member's rights at the hearing", "the enforcement policy and the schedule of fines",
                "holding the hearing in executive session"),
        documents=(K.DECLARATION, K.BYLAWS, K.POLICY, K.OPERATING_RULES),
        considerations=("Is the notice delivered far enough ahead, the way the law requires?",
                        "Does it state the alleged violation, the possible penalty, and the owner's right to attend and speak?",
                        "Does the penalty it names exist in the adopted fine schedule?"),
        template=TemplateKind.HEARING_NOTICE,
    ),
    TaskPrompt(
        TaskKind.DECISION_NOTICE,
        "Notice to an owner of the board's decision after a hearing.",
        Audience.OWNER,
        topics=("notice of the board's decision after a disciplinary hearing", "internal dispute resolution",
                "when a penalty takes effect"),
        documents=(K.DECLARATION, K.BYLAWS, K.POLICY),
        considerations=("Is the decision delivered within the time the law allows, the way it requires?",
                        "Does it tell the owner how to request dispute resolution?"),
        template=TemplateKind.DECISION_NOTICE,
    ),
    TaskPrompt(
        TaskKind.QUESTION,
        "Answer a question about the association's obligations or an owner's, from the law and the governing documents.",
        Audience.BOARD,
    ),
)
