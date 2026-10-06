"""The solar energy system application, Civil Code 714, 714.1, and 4746: a State form of the California pack.

Built from docs/form-templates/solar.md. The text on disk (``data/authorities/CIV/CIV-714-714.1.md`` and
``CIV-4700-4753.md``, the 2025 session publication, exported 2026-10-04):

- 714(e)(1), (e)(2): approval is processed "in the same manner as an application for approval of an architectural modification";
  an association that is not a public entity gives its approval or denial in writing, and "If an application is not denied in
  writing within 45 days from the date of receipt of the application, the application shall be deemed approved, unless that delay
  is the result of a reasonable request for additional information." The time runs from receipt: the text does not say
  "complete";
- 714(b), (d)(1): only "reasonable restrictions", and how much "significantly" is; 714.1(a): what an association may impose;
  714.1(b): what it shall not do (a general policy against a rooftop system for household purposes on the owner's building, or a
  vote of the members);
- 4746(a): on "a multifamily common area roof shared by more than one homeowner" the association "shall require" the applicant to
  notify each owner of a unit in the building, and the owner and each successive owner to keep a homeowner liability coverage
  policy, with the certificate within 14 days of approval and annually after. 4746(b): what it may also require.

**What is the profile's.** The questions for what 714.1(a)(3), (a)(4) and 4746(b) let an association require are asked only where
the profile has adopted them: ``ADOPTABLE`` holds each, in the statute's words, for a profile's ``Add`` row (the page: a provision
the profile has not adopted is not asked). The base form carries the "shall" items of 4746(a) as questions.

**Deviations from the page.** (1) The "when adopted" items (survey, the owner's responsibilities, the installer's indemnity, the
roof provision) are not in ``required_content`` (a form for a community that has not adopted them is complete without them); they
are the ``ADOPTABLE`` questions. (2) ``{SURVEY_PANEL}`` is ``SURVEY_PARAGRAPH``, a paragraph a profile adds with the survey question.
(3) ``{DECIDER}``, ``{NEXT_MEETING}``, and ``{DUE}`` are of one request and left to the handler.

**The shelf's 714(d)(1)(B).** Its words, "not to exceed one thousand dollars ($1,000) over the system cost as originally specified
and proposed", read opposite to (A)'s "exceeding": the form recites them exactly and states neither reading as law (page, 13, lead 2).
"""

from __future__ import annotations

from jason.community.form_library.ca.improvement import (
    ACKNOWLEDGMENT_CLOCK,
    AS_OF,
    CHANNELS,
    HELP_PARAGRAPH,
    MEETING_NOTICE_CLOCK,
    PROCEDURE_NOTE,
    RETURN_PARAGRAPH,
    STANDARD_SLOTS,
    applicant,
    help_question,
    not_only_door,
    policy,
    statute,
    work_dates,
)
from jason.community.form_library.tiers import (
    ATTESTATION,
    PREAMBLE,
    SIGNATURE,
    FormDefinition,
    Required,
    Tier,
    register,
)
from jason.community.forms import FormKey, FormQuestion, FormTemplate, QuestionKind, ReadAs

LAW = "Civil Code 714(e)(2)"
ROOF_NOTE = "Answer this section if it is on a roof that more than one homeowner shares, or you are not sure."

QUESTIONS = (
    *applicant(LAW, decision="the written decision", other="The installer, with the owner's signature"),
    FormQuestion("What kind of system?", QuestionKind.CHOICE, key="system_kind", section="The system",
                 options=("Electricity (photovoltaic)", "Water heating for the home", "Swimming pool heating", "Another kind",
                          "Not sure"),
                 authority="Civil Code 714(c), (d)(1): different standards and different limits"),
    FormQuestion("Where will it go?", QuestionKind.CHOICE, key="where_installed",
                 options=("On the roof of the building I live in",
                          "On a garage or carport next to my building that is assigned to me",
                          "Elsewhere on my own property (my yard, a patio)", "In the common area",
                          "On another owner's property", "Not sure"),
                 authority="Civil Code 714.1(a)(1), (a)(2), (b)(1)"),
    FormQuestion("Is it on a roof that more than one homeowner shares?", QuestionKind.CHOICE, key="roof_shared",
                 options=("Yes", "No", "Not sure"),
                 authority="\"a multifamily common area roof shared by more than one homeowner\" (Civil Code 4746(a))"),
    FormQuestion("Describe the system (what it is, its size, and where on the roof or lot)", QuestionKind.PARAGRAPH,
                 key="system_description", authority="applies Civil Code 714(b) and (c)"),
    FormQuestion("Who owns the system?", QuestionKind.CHOICE, required=False, key="system_ownership",
                 options=("I do", "It is leased to me", "I buy power from the owner of the system", "Not sure"),
                 authority="names who is responsible (Civil Code 4746(a)(2), (b)(2) speak of the owner)"),
    FormQuestion("I am attaching", QuestionKind.CHECKBOX, required=False, key="plans_attached",
                 options=("A layout showing placement", "The equipment sheets and listings or certifications",
                          "The wiring diagram", "Roof attachment details"),
                 help="Your association's checklist says which it needs. Nothing here is a reason the 45 days do not run.",
                 authority="Civil Code 714(c); the documents' checklist"),
    FormQuestion("The cost of the system as you originally specified and proposed it (an estimate is fine)", required=False,
                 key="system_cost",
                 authority="so the limits of Civil Code 714(d)(1) can be applied if the association proposes a change that adds "
                           "cost; never used to approve or deny"),
    FormQuestion("The permit", QuestionKind.CHOICE, key="permit_status",
                 options=("I have it", "I applied", "I will apply", "None needed"), authority="Civil Code 714(c)(1)"),
    FormQuestion("The permit number, if you have it", required=False, key="permit_number", authority="evidence you give us"),
    FormQuestion("The installer's name", required=False, key="installer_name", reads=ReadAs.NAME,
                 authority="Civil Code 714.1(a)(4); 4746(b)(1)(A)"),
    FormQuestion("The installer's licence number", required=False, key="installer_license",
                 authority="a licensed contractor prepares a survey (Civil Code 4746(b)(1)(A))"),
    FormQuestion("I have notified the owner of each unit in the building of this application", QuestionKind.CHECKBOX,
                 required=False, key="owners_notified", section="If the roof is shared with other homeowners",
                 options=("I have notified the owner of each unit in the building of this application.",),
                 help=ROOF_NOTE + " Your notice is notice, not a request for permission.",
                 authority="Civil Code 4746(a)(1)"),
    FormQuestion("On what date did you notify them?", QuestionKind.DATE, required=False, key="owners_notified_on",
                 authority="the evidence the association keeps (Civil Code 4746(a)(1))"),
    FormQuestion("How?", QuestionKind.CHOICE, required=False, key="owners_notified_how",
                 options=("Hand delivery", "Mail", "Email", "Posted at the building", "Other"),
                 authority="the statute names no method; the evidence says which"),
    FormQuestion("A copy of the notice", QuestionKind.CHECKBOX, required=False, key="notice_copy_attached",
                 options=("I am attaching a copy of the notice and the list of units notified.",),
                 authority="evidence; the owners' names stay in the request's file"),
    FormQuestion("Your homeowner liability coverage policy", QuestionKind.CHECKBOX, required=False, key="agree_liability_policy",
                 options=("I agree that I, and each later owner, will keep a homeowner liability coverage policy at all times and "
                          "give the association the certificate of insurance within 14 days of approval and every year after.",),
                 help=ROOF_NOTE, authority="Civil Code 4746(a)(2)"),
    *work_dates("an approval's start time is a proposed policy (improvement-lifetime)", required=False),
    help_question(),
)

# What 714.1(a) and 4746(b) let an association require: asked only where the profile has adopted it, each in the statute's words.
# A profile adds the ones its documents or an adopted rule impose (an ``Add`` row), never one it has not adopted.
ADOPTABLE = {
    "site_survey_attached": FormQuestion(
        "A solar site survey", QuestionKind.CHECKBOX, required=False, key="site_survey_attached",
        options=("I am attaching a solar site survey, prepared by a licensed contractor or the contractor's registered salesperson, "
                 "showing the placement, with a fair allocation of usable roof area among the owners who share the roof.",),
        authority="Civil Code 4746(b)(1)(A), (B)"),
    "ack_damage_costs": FormQuestion(
        "What you are responsible for: damage", QuestionKind.CHECKBOX, required=False, key="ack_damage_costs",
        options=("I understand that I, and each later owner of the system, are responsible for costs for damage to the common area, "
                 "an exclusive-use common area, or separate interests resulting from its installation, maintenance, repair, "
                 "removal, or replacement.",), authority="Civil Code 4746(b)(2)(A)"),
    "ack_maintenance_costs": FormQuestion(
        "What you are responsible for: maintenance and restoration", QuestionKind.CHECKBOX, required=False,
        key="ack_maintenance_costs",
        options=("I understand that I, and each later owner, are responsible for the maintenance, repair, and replacement of the "
                 "system until it is removed and for restoring the common area, exclusive-use common area, or separate interests "
                 "after removal.",), authority="Civil Code 4746(b)(2)(B)"),
    "ack_disclose_buyers": FormQuestion(
        "What you are responsible for: telling a buyer", QuestionKind.CHECKBOX, required=False, key="ack_disclose_buyers",
        options=("I understand that I must tell a buyer that there is a solar energy system and what the owner's responsibilities "
                 "are.",), authority="Civil Code 4746(b)(2)(C): the owner's duty, not the association's"),
    "agree_indemnity": FormQuestion(
        "The installer's indemnity", QuestionKind.CHECKBOX, required=False, key="agree_indemnity",
        options=("I agree that the installer will indemnify or reimburse the association or its members for loss or damage caused "
                 "by the installation, maintenance, or use of the system.",), authority="Civil Code 714.1(a)(4)"),
    "ack_roof_maintenance": FormQuestion(
        "The roof", QuestionKind.CHECKBOX, required=False, key="ack_roof_maintenance",
        options=("I understand the association's provision for the maintenance, repair, or replacement of the roof ({ROOF_PROVISION}).",),
        authority="Civil Code 714.1(a)(3)"),
}

SURVEY_PARAGRAPH = ("Your documents also ask for a solar site survey from a licensed contractor, with a fair allocation of the "
                    "usable roof among the owners who share it. The cost of the survey does not count as part of the cost of your "
                    "system.")

PREAMBLE_PARAGRAPHS = (
    "This form is for a solar energy system, where the governing documents require approval first (Civil Code 714, 714.1, and, on a "
    "roof shared by more than one homeowner, 4746). The association's copy of those sections is not an official restatement of them.",
    "**We got it.** We will tell you in writing that we have your application within {ACK_DAYS} business days of the day we "
    "receive it (a target the board proposed, not a law).",
    "**The 45 days.** The Civil Code says: \"If an application is not denied in writing within 45 days from the date of receipt of "
    "the application, the application shall be deemed approved, unless that delay is the result of a reasonable request for "
    "additional information.\" (Civil Code 714(e)(2)(B).) We count from the day we **receive** your application. The approval or the "
    "denial will be in writing.",
    "**If we need more information.** We will ask in writing, say what we need and why, and keep a copy. The law lets the delay that "
    "comes from a reasonable request count against the 45 days; it does not say how much. We aim to decide inside 45 days of the day "
    "we received your application either way.",
    "**Who decides.** The board decides, in the same way it decides any request to change a unit: at a board meeting, on an agenda "
    "item. You do not need a vote of the members for a system on the roof of the building you live in, or on a garage or carport "
    "next to it that is assigned to you.",
    "**What we may and may not require.** We may impose only reasonable restrictions: \"restrictions that do not significantly "
    "increase the cost of the system or significantly decrease its efficiency or specified performance, or that allow for an "
    "alternative system of comparable cost, efficiency, and energy conservation benefits\" (Civil Code 714(b)). The law says how much "
    "is \"significantly\" (Civil Code 714(d)(1)). We may not set a general policy against rooftop solar for household purposes on your "
    "own building's roof or your assigned garage or carport (714.1(b)). The system must meet the health and safety standards and the "
    "certifications the law lists, and you are responsible for the permit.",
    "**If your roof is shared with other homeowners.** The law says we \"shall require\" you to notify each owner of a unit in the "
    "building of your application, and to keep a homeowner liability coverage policy, and that you and each later owner give us the "
    "certificate within 14 days of approval and every year after (Civil Code 4746(a)). Please notify every owner in the building and "
    "tell us the date and how. Your notice is notice, not a request for permission; no neighbor's signature decides your application.",
    "**If we deny it.** The denial is in writing and says why. You may ask the board to reconsider at an open meeting (there is a "
    "form for it, or use your own words); the board answers within {MAX_DAYS_RECONSIDERATION} days of your request "
    "({PROCEDURE_CITATION}).",
    not_only_door("what you want to install and where"),
    "An installer may send this form for you if you sign it or authorize it.",
    HELP_PARAGRAPH,
    RETURN_PARAGRAPH,
)

TEMPLATE = FormTemplate(
    key=FormKey.SOLAR,
    title="Application for a Solar Energy System",
    authority="Civil Code 714, 714.1, and 4746: an application to install a solar energy system.",
    description=("Use this form to ask {ASSOCIATION} to approve a solar energy system. The association must decide it in writing "
                 "within 45 days of the day it receives it."),
    questions=QUESTIONS,
    preamble=PREAMBLE_PARAGRAPHS,
    attestation=("I am the owner of this unit, or authorized by the owner to send this. What I have written is true to the best of my "
                 "knowledge. Where I have checked a box above, I agree to it in writing."),
    code="PV",
)

REQUIRED = (
    Required("The kind of system: electricity, domestic water heating, swimming pool heating, other", ("system_kind",),
             "CIV 714(c)(2); CIV 714(c)(3); CIV 714(d)(1)(A); CIV 714(d)(1)(B)"),
    Required("Where it goes: the roof of the owner's building, an assigned adjacent garage or carport, elsewhere on the owner's "
             "separate interest, the common area, another owner's separate interest", ("where_installed",),
             "CIV 714.1(a)(1); CIV 714.1(a)(2); CIV 714.1(b)(1)"),
    Required("Whether the roof is shared by more than one homeowner", ("roof_shared",), "CIV 4746(a); CIV 4746(b)"),
    Required("The system described, so the standards can be applied", ("system_description", "plans_attached", "system_ownership"),
             "CIV 714(b); CIV 714(c)"),
    Required("The system's cost as originally specified and proposed", ("system_cost",), "CIV 714(d)(1)(A); CIV 714(d)(1)(B); "
                                                                                         "CIV 4746(b)(1)(A)"),
    Required("Permit and certification", ("permit_status", "permit_number", "plans_attached"), "CIV 714(c)(1); CIV 714(c)(2); CIV 714(c)(3)"),
    Required("Shared roof: the notice to each owner of a unit in the building",
             ("owners_notified", "owners_notified_on", "owners_notified_how", "notice_copy_attached"), "CIV 4746(a)(1)"),
    Required("Shared roof: the owner and each successive owner maintain a homeowner liability coverage policy and give the "
             "certificate within 14 days of approval and annually", ("agree_liability_policy",), "CIV 4746(a)(2)"),
    Required("The 45 days and the exception: a decision in writing, deemed approved if not denied in writing within 45 days from the "
             "date of receipt, unless the delay is the result of a reasonable request for additional information", (PREAMBLE,),
             "CIV 714(e)(2)"),
    Required("The reasonable-restriction limits, and what the association may not do (no general prohibition, no member vote)",
             (PREAMBLE,), "CIV 714(b); CIV 714(d)(1); CIV 714.1(b)"),
    Required("Start and finish dates, the signature, and help", ("start_date", "finish_date", SIGNATURE, ATTESTATION, "help_needed"),
             "the documents; the standard"),
    Required("The owner, the unit, and who is sending it (an installer may, with the owner's signature)",
             ("unit", "owner_name", "submitted_by", "rep_authorization", "installer_name", "installer_license"),
             "CIV 714(e)(2)(A); CIV 4041(a)(3)"),
)

CLOCKS = (
    statute("decision", "the date of receipt of the application", 45, "CIV 714(e)(2)(B)",
            "deemed approved, unless the delay is the result of a reasonable request for additional information"),
    policy("information-request", "the day the application is received", 15, "an addition to improvement-review-time",
           "the statute's exception may apply; a person records the request, the day, and the day it was answered; the handler still "
           "aims to decide inside 45 days of receipt (a reading)"),
    ACKNOWLEDGMENT_CLOCK,
    statute("certificate-of-insurance", "the day of approval", 14, "CIV 4746(a)(2)",
            "a finding for the manager; no remedy is stated, counsel reads it"),
    statute("certificate-yearly", "the anniversary of the approval", 365, "CIV 4746(a)(2)",
            "a finding for the manager; a recurring duty (duty-schedule)"),
    policy("reconsideration-response", "the day the request for reconsideration is received", 45, "improvement-reconsideration; "
           "CIV 4765(a)(1) requires the documents to state the maximum", "as the reconsideration request"),
    MEETING_NOTICE_CLOCK,
)

ACKNOWLEDGMENT = (
    "We received your application to install a solar energy system at {UNIT_ADDRESS} on **{RECEIVED}**. Your reference is "
    "**{REFERENCE}**.\n\n"
    "The Civil Code says an application not denied in writing within 45 days from the day it is received is deemed approved, unless "
    "the delay is the result of a reasonable request for additional information. We received it on {RECEIVED}, so the forty-fifth "
    "day is **{DUE}**. {DECIDER} decides it, at an open meeting of the board; the next meeting that can be noticed in time is "
    "{NEXT_MEETING}. We will tell you in writing.\n\n"
    "[Shared roof] Please send us the date and how you notified each owner of a unit in the building, and a copy of your notice. The "
    "law says the association shall require this notice.\n\n"
    "[If more information is needed] To decide, we need: {ITEMS_AND_WHY}. Please send it by {ASK_BY}. We are asking because "
    "{REASON}.\n\n"
    "If the board denies it, the letter will say why and how to ask the board to reconsider.\n\n"
    "This says only that we have your request and when. It is not an approval and not a denial."
)

SLOTS = (*STANDARD_SLOTS, "PROCEDURE_CITATION", "MAX_DAYS_RECONSIDERATION", "ACK_DAYS")

NOTES = (
    PROCEDURE_NOTE,
    "The 45 days run from the date of receipt, not from a complete application (714(e)(2)(B)); a request for additional "
    "information is a person's record and the form never pauses the clock on its own.",
    "ADOPTABLE holds the questions for what 714.1(a)(3), (a)(4) and 4746(b) allow, for a profile to Add where it has adopted them; "
    "a provision the profile has not adopted is never asked.",
    "714(d)(1)(B) and (A) read in opposite directions ('not to exceed' and 'exceeding'): the form recites them and states neither "
    "reading as law; counsel reads them before the association relies on a dollar figure.",
)

DEFINITION = register(FormDefinition(
    key="solar",
    tier=Tier.STATE,
    jurisdiction="CA",
    template=TEMPLATE,
    version="1",
    as_of=AS_OF,
    authority=("CIV 714", "CIV 714.1", "CIV 4746"),
    required_content=REQUIRED,
    recitals=("CIV 714(e)(2)", "CIV 714(e)(2)(A)", "CIV 714(e)(2)(B)", "CIV 714(b)", "CIV 714(d)(1)", "CIV 714(d)(1)(A)",
              "CIV 714(d)(1)(B)", "CIV 714.1(a)", "CIV 714.1(b)", "CIV 4746(a)", "CIV 4746(a)(1)", "CIV 4746(a)(2)", "CIV 4746(b)",
              "CIV 4746(b)(1)(A)", "CIV 4746(b)(1)(B)", "CIV 4746(b)(2)(A)", "CIV 4746(b)(2)(B)", "CIV 4746(b)(2)(C)"),
    member_clock=("We tell you in writing that we have your application. An application not denied in writing within 45 days from "
                  "the day we receive it is deemed approved, unless the delay is the result of a reasonable request for additional "
                  "information. If it is denied, the board answers a request to reconsider within {MAX_DAYS_RECONSIDERATION} days "
                  "({PROCEDURE_CITATION})."),
    association_clocks=CLOCKS,
    acknowledgment=ACKNOWLEDGMENT,
    procedure="respond",
    handler="response-clock",
    channels=CHANNELS,
    slots=SLOTS,
    notes=NOTES,
))
