"""The question sets, per document kind, that a local model answers beside the rule readers (``questions``).

A question set serves the law that shapes the kind (the Open Meeting Act for minutes) and is compared, field by field,
with the kind's document model. Questions with no field are ones only a reader of the words can answer; a gap on one
is a lead that the document may lack what the law or a rule expects.
"""

from __future__ import annotations

from jason.community.questions import AnswerType as A
from jason.community.questions import Question as Q
from jason.community.questions import QuestionSet
from jason.community.symbols import DocumentKind

MINUTES = QuestionSet(
    DocumentKind.MINUTES,
    "This is the minutes (or a draft, or an AI summary) of a meeting of a California homeowners association's board of "
    "directors or its members.",
    (
        Q("meeting_date", "On what date was the meeting held?", A.DATE, "CIV 4950(a)", "meeting_date"),
        Q("meeting_type", "Was it a regular, special, emergency, annual, or organizational meeting? One word.", A.TEXT,
          "CIV 4920", "meeting_type"),
        Q("draft", "Is the document marked as a draft?", A.YES_NO, "CIV 4950(a)", "draft"),
        # The heading's scheduled time, an agenda item's title, and a person who speaks answer none of these: each asks
        # what the minutes record happening.
        Q("called_to_order", "At what time do the minutes say the meeting was actually called to order? Not the "
          "scheduled time in the heading or notice.", A.TEXT, "Bylaws", "called_to_order"),
        Q("quorum", "Do the minutes state that a quorum of directors was present?", A.YES_NO, "Bylaws 7.10", "quorum",
          gap="the minutes do not state that a quorum was present"),
        Q("directors_present", "Which directors do the minutes list as present or attending (a roll call or an "
          "attendance line)? Not people who are only mentioned as speaking. Names only.", A.LIST, "Bylaws 10.10",
          "directors_present", gap="the minutes list no directors present"),
        Q("prior_minutes_approved", "Did the board approve the minutes of a previous meeting?", A.YES_NO, "CIV 4950",
          "prior_minutes_approved"),
        # The distinct matters decided, not how many sentences say so: an AI summary retells one decision several times.
        Q("decision_topics", "List each distinct matter the board decided or approved (one short entry per matter, "
          "with its dollar amount if any; a matter only discussed is not a decision).", A.LIST, "CIV 4950", "actions",
          topics=True),
        Q("vote_recorded", "For the decisions, do the minutes record how directors voted (a count, unanimous, or each "
          "director's vote)?", A.YES_NO, "CIV 4926(a)(3)",
          gap="the minutes record decisions without the vote"),
        Q("roll_call", "Do the minutes record a roll-call vote, naming how each director voted?", A.YES_NO,
          "CIV 4926(a)(3) (teleconference meetings)"),
        Q("amounts_approved", "List each dollar amount the board approved or authorized, with what it was for.", A.LIST,
          "CIV 5500, 5502"),
        Q("executive_session", "Did the board meet, or adjourn to, an executive session?", A.YES_NO, "CIV 4935",
          "executive_session"),
        Q("executive_topics", "What general subjects do the minutes say the executive session took up?", A.LIST,
          "CIV 4935(e)", "executive_topics"),
        Q("reserve_transfer", "Do the minutes record a transfer or borrowing from the reserve funds?", A.YES_NO,
          "CIV 5515", "reserve_transfer"),
        Q("open_forum", "Do the minutes record that the open forum was held: members spoke, or none came forward? An "
          "agenda heading that only names the open forum is not enough.", A.YES_NO, "CIV 4925(b)",
          gap="the minutes do not note the members' open forum"),
        Q("recorder", "Who prepared or recorded the minutes (a name or an office)?", A.TEXT, "Bylaws 10.10",
          gap="the minutes do not say who took them"),
        Q("adjourned", "At what time was the meeting adjourned?", A.TEXT, "Bylaws", "adjourned"),
        Q("next_meeting", "On what date is the next meeting set?", A.DATE, "CIV 4920", "next_meeting"),
    ),
)

# Declarations pages. Several readers read the kind (the NFIP flood page, the package, crime, D&O, and umbrella
# declarations), so a question names each reader's field (``Question.field``). A policy form's definitions, sample
# wording, and exclusions answer nothing: each question asks what the declarations (or a schedule) state for this policy.
_DECLARATIONS = " Answer from the declarations, a schedule, or an endorsement that states this policy's own figures; " \
    "not from the policy form's definitions, conditions, exclusions, sample wording, or a notice about the program. " \
    "Where the page's labels and figures print in separate runs and which figure goes with which label is unclear, " \
    "answer not stated."

INSURANCE_POLICY = QuestionSet(
    DocumentKind.INSURANCE_POLICY,
    "This is an insurance policy of a California homeowners association (a condominium community): its declarations "
    "page and possibly the policy forms, endorsements, or an evidence of coverage.",
    (
        Q("carrier", "Which insurance company issues the policy (the insurer or underwriting company)? Not the agent, "
          "broker, producer, or program administrator." + _DECLARATIONS, A.TEXT, "CIV 5300(b)(9)", "carrier",
          gap="the document does not name the insurer"),
        Q("policy_number", "What is the policy number (or the evidence of coverage number)? Not a quote, application, "
          "account, NAIC, or form number, and not a label such as \"Policy Number:\" alone.", A.TEXT, "CIV 5300(b)(9)",
          "policy_number|evidence_number", gap="the document states no policy number"),
        Q("named_insured", "Who is the named insured?" + _DECLARATIONS, A.TEXT, "CIV 5800, 5805", "named_insured",
          gap="the declarations name no insured"),
        Q("mailing_address", "What mailing address do the declarations give for the named insured (where the insurer "
          "sends its notices)? Not the insured property's location or the agent's address.", A.TEXT, "CIV 5810",
          "mailing_address"),
        Q("insured_location", "What property address or premises does the policy insure (the property location or "
          "premises schedule)? Give every street address the location lists, joined with \" & \". Not a mailing "
          "address.", A.TEXT, "CIV 5300(b)(9)", "premises|property_location"),
        Q("coverage_type", "What kind of insurance is this: property, general liability, directors and officers, crime "
          "or fidelity, umbrella or excess liability, flood, or earthquake? Name each the declarations schedule, in a "
          "few words.", A.TEXT, "CIV 5300(b)(9)", "coverage"),
        Q("term_start", "On what date does the policy period begin?" + _DECLARATIONS, A.DATE, "CIV 5300(b)(9)",
          "term_start", gap="the document states no policy period"),
        Q("term_end", "On what date does the policy period end?" + _DECLARATIONS, A.DATE, "CIV 5300(b)(9)", "term_end"),
        Q("building_limit", "What is the limit of insurance for the building or buildings (building property coverage)? "
          "Not the replacement cost value, a contents limit, or a liability limit.", A.AMOUNT, "CIV 5300(b)(9)",
          "building_limit|limit:flood_zone"),
        Q("valuation", "On what basis do the declarations value the building: replacement cost, guaranteed "
          "replacement cost (GRC), actual cash value, or agreed value? A few words.", A.TEXT, "CIV 5300(b)(9)",
          "valuation"),
        Q("replacement_cost_value", "What replacement cost value do the declarations state for the building (a "
          "figure labeled replacement cost value)? Not the limit of insurance.", A.AMOUNT, "44 CFR 61.6",
          "replacement_cost:flood_zone"),
        Q("property_deductible", "What is the deductible for a building (property or flood) loss, per occurrence? Not "
          "a crime, liability retention, equipment breakdown, or contents deductible." + _DECLARATIONS, A.AMOUNT,
          "CIV 5300(b)(9)", "property_deductible|deductible:flood_zone"),
        Q("gl_each_occurrence", "What is the general liability each-occurrence limit (bodily injury and property "
          "damage)? Not an aggregate, an umbrella, or a D&O limit.", A.AMOUNT, "CIV 5800(a)(4), 5805(b)",
          "each_occurrence:general_aggregate", minimum=50_000_000),
        Q("gl_aggregate", "What is the general liability general aggregate limit?", A.AMOUNT, "CIV 5805(b)",
          "general_aggregate"),
        Q("umbrella_limit", "What is the umbrella or excess liability limit each occurrence? Not the primary general "
          "liability limit.", A.AMOUNT, "CIV 5805(b)", "each_occurrence:retained_limit"),
        Q("dno_limit", "What is the directors and officers (management liability) limit of liability?", A.AMOUNT,
          "CIV 5800(a)(4)", "limit:claims_made", minimum=50_000_000),
        Q("crime_coverages", "List each crime or fidelity insuring agreement the declarations schedule, with its limit "
          "(one entry each, e.g. \"Employee Theft $400,000\"). Leave it empty when the policy has no crime coverage.",
          A.LIST, "CIV 5806", "agreements", topics=True),
        Q("computer_fraud", "Do the declarations schedule computer fraud or funds transfer fraud coverage with a limit?",
          A.YES_NO, "CIV 5806(b)"),
        Q("premium", "What is the total premium for the policy term (with fees and surcharges if the page totals "
          "them)? Not an installment or a single coverage part." + _DECLARATIONS, A.AMOUNT, "CIV 5300(b)(9)",
          "premium"),
    ),
)

# A proposal, quote, bid, or estimate a vendor gives the association before the work.
PROPOSAL = QuestionSet(
    DocumentKind.PROPOSAL,
    "This is a proposal, quote, bid, or estimate a vendor or contractor gave a California homeowners association. "
    "Marketing pages, company history, and sample process descriptions answer nothing.",
    (
        # A bill filed as a proposal (an invoice that cites its estimate) answers the rest wrongly; this tells it apart.
        Q("is_offer", "Is this document an offer of future work or service (a proposal, quote, bid, estimate, or "
          "engagement letter), rather than an invoice, receipt, or statement for work already done or a policy "
          "notice?", A.YES_NO, "", gap="the document reads as a bill or notice, not an offer; check its kind"),
        Q("vendor", "Which company makes the proposal (the contractor or vendor offering the work)? Not the customer.",
          A.TEXT, "CIV 5200(b)", "vendor"),
        Q("number", "What is the proposal, quote, bid, or estimate number? Not a phone, license, tax id, or account "
          "number.", A.TEXT, "", "number"),
        Q("proposal_date", "On what date was the proposal issued or prepared?", A.DATE, "", "proposal_date"),
        Q("prepared_for", "To whom is the proposal made (the customer)? A name, not an address.", A.TEXT, "",
          "prepared_for"),
        Q("work_items", "List each item of work or service the proposal prices, with its price when it gives one (one "
          "entry per item, e.g. \"Crack seal $2,100.00\"). Not totals, tax, deposits, or payment installments.", A.LIST,
          "CIV 5200(b)", "items|options", topics=True),
        Q("total", "What is the proposal's total price? When it prices only alternatives with no single total, not "
          "stated.", A.AMOUNT, "CIV 5500", "total"),
        Q("valid_until", "Until what date does the proposal say its price or offer holds (an expiration or \"valid "
          "until\" date)? When it gives only a number of days, not stated.", A.DATE, "", "valid_until",
          gap="the proposal states no date the offer expires"),
        Q("exclusions", "List what the proposal expressly excludes or says is not included (one short entry each). "
          "Only an express exclusion; not a general term or condition.", A.LIST, "BPC 7159(d)",
          gap="the proposal states no exclusions"),
        Q("license", "What contractor's state license number does the proposal print (e.g. \"CA State License "
          "#123456\", \"CSLB Lic.\")? Not a business, tax, DIR, or other registration number.", A.TEXT, "BPC 7030.5",
          "license", gap="the proposal prints no contractor's license number (a licensee must print it on every bid)"),
        Q("insurance", "What does the proposal say about the contractor's own insurance (liability or workers' "
          "compensation: a carrier, policy, limit, or that it is insured)? A general promise of quality is not an "
          "answer.", A.TEXT, "BPC 7159(e)(1), (2)", gap="the proposal says nothing of the contractor's insurance"),
        Q("warranty", "What warranty or guarantee does the proposal give on the work (its length and what it covers)? "
          "A stated refusal to guarantee something is an answer.", A.TEXT, "",
          gap="the proposal states no warranty"),
        Q("payment_schedule", "List the payment schedule: each payment with its amount or percent and when it is due "
          "(deposit, progress, final). Not the item prices.", A.LIST, "BPC 7159.5(a)", "payment_schedule",
          topics=True),
        Q("accepted", "Does the document show that the association signed or accepted the proposal (a filled-in "
          "signature, an acceptance date, or an e-signature certificate)? A signature line, an \"x\", or a \"Customer "
          "Acceptance\" heading with no name or date filled in is not acceptance.",
          A.YES_NO, "CIV 5200(a)(5)", "accepted_on", gap="no acceptance shows in the document"),
        Q("signed_by", "Who signed the proposal? Names only, from filled-in signatures (printed or electronic), not "
          "from blank signature lines.", A.LIST, "CIV 5200(a)(5)", "signatures"),
    ),
)

# An invoice, bill, or receipt a vendor sends the association.
INVOICE = QuestionSet(
    DocumentKind.INVOICE,
    "This is an invoice, bill, statement, or receipt a vendor sent a California homeowners association.",
    (
        Q("vendor", "Which company issued the invoice? Not the customer or bill-to party; on an insurance premium notice, the "
          "insurer, not the agency.", A.TEXT, "CIV 5200(b)",
          "vendor"),
        Q("number", "What is the invoice, bill, or receipt number? Not an account, customer, policy, purchase order, "
          "or phone number, and not a label alone.", A.TEXT, "CIV 5200(b)", "number",
          gap="the document prints no invoice number"),
        Q("invoice_date", "On what date was the invoice issued (the invoice or bill date)? Not a service or due date.",
          A.DATE, "CIV 5200(b)", "invoice_date"),
        Q("due_date", "On what date is payment due? When it states only terms (e.g. \"Net 30\"), not stated.", A.DATE,
          "", "due_date"),
        Q("total", "What total does the invoice charge (the invoice total)? Not a line item, a prior balance, or a "
          "payment.", A.AMOUNT, "CIV 5500(a)", "total_cents"),
        Q("amount_due", "What balance does the invoice say is still due now? When it says paid in full or a balance "
          "of $0.00, \"$0.00\".", A.AMOUNT, "CIV 5500(a)", "amount_due_cents"),
        Q("paid", "Does the document itself show the amount was paid (a receipt, \"paid\", a payment applied, or a "
          "zero balance)?", A.YES_NO, "CIV 5500(a)", "paid"),
        Q("bill_to", "To whom is the invoice billed (the bill-to or customer name)? A name, not an address.", A.TEXT,
          "CIV 5200(b)", "bill_to"),
        Q("service_location", "At what address, unit, or building was the work done or the service given (a job, "
          "project, service, or property address)? Not the vendor's address or the bill-to mailing address.", A.TEXT,
          "Declaration (who maintains what)", "property_location",
          gap="the invoice does not say where the work was done"),
        Q("line_items", "List each charge the invoice itemizes with its amount (one entry per line, e.g. \"Drywall "
          "$2,418.00\"). Not headings, tax, subtotals, totals, or payments.", A.LIST, "CIV 5500(a)", "line_items",
          topics=True),
        Q("reference", "What proposal, estimate, contract, purchase order, work order, or change order number does the "
          "invoice cite? A blank label such as \"P.O. No.\" is not an answer.", A.TEXT, "CIV 5200(a)(5)",
          gap="the invoice cites no proposal, contract, or work order"),
        Q("license", "What contractor's state license number does the invoice print? Not a business, tax, or other "
          "registration number.", A.TEXT, "BPC 7030.5"),
    ),
)

QUESTION_SETS: dict[DocumentKind, QuestionSet] = {qs.kind: qs for qs in (MINUTES, INSURANCE_POLICY, PROPOSAL, INVOICE)}

__all__ = ["INSURANCE_POLICY", "INVOICE", "MINUTES", "PROPOSAL", "QUESTION_SETS"]
