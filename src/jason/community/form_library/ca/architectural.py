"""The architectural application, Civil Code 4765 and 4766: a State form of the California pack.

Built from docs/form-templates/architectural-application.md, which follows the workflow of docs/improvement-requests.md. The
text on disk (``data/authorities/CIV/CIV-4760-4766.md``, the 2025 session publication, exported 2026-10-04):

- 4765(a): the section applies "if the governing documents require association approval before a member may make a physical
  change"; (a)(1) the procedure "shall state the maximum time for response to an application or a request for reconsideration by
  the board"; (a)(4) "A decision on a proposed change shall be in writing", and a disapproval carries an explanation and "a
  description of the procedure for reconsideration"; (a)(5) the applicant "is entitled to reconsideration by the board, at an open
  meeting"; (c) the association "shall annually provide its members with notice of any requirements for association approval";
- 4766: a substantially similar reconstruction after a disaster runs on its own clocks: 30 calendar days to say complete or
  incomplete (b)(1), 45 calendar days to review a complete application (c), 60 calendar days to decide an appeal (e)(2), and no
  appeals or additional hearings once approved (f)(1);
- 4760(a)(2)(D): plans and specifications for a modification for access; the association "shall not deny approval ... without
  good cause".

**What is the profile's.** The maximum times (4765(a)(1) makes the documents state them), the procedure's citation, the
annual-notice link, and the contact are slots: a community that gives none is not offered the form, and the check names each
missing slot. The questions that depend on a community's documents are added through ``Add``: the neighbors' acknowledgment
(only where the documents ask, never a condition; ``NEIGHBOR_ACKNOWLEDGMENT``) and the fee acknowledgment (only where the
documents set a fee; ``FEE_ACKNOWLEDGMENT``).

**Deviations from the page.** (1) The ``change_category`` options are the general ones (a change inside the unit, outside it,
in an exclusive-use area, in the common area, something else, not sure); the page's list from the association's change rows is
the profile's later binding. (2) ``{DECIDER}``, ``{RECEIVED}``, ``{DUE}``, ``{REFERENCE}``, and the like are values of one request,
not slots, so a blank form says "the board decides" (the page's default decider) and the acknowledgment keeps them as tokens for
the handler. (3) A pause and a condition's due day are a person's record and carry no number here; the approval's lifetime
(proposed ``improvement-lifetime``) names no number on the page, so no clock row is made.
"""

from __future__ import annotations

from jason.community.form_library.ca.improvement import (
    ACKNOWLEDGMENT_CLOCK,
    AS_OF,
    CHANNELS,
    HELP_PARAGRAPH,
    INSURANCE_PARAGRAPH,
    MEETING_NOTICE_CLOCK,
    PROCEDURE_NOTE,
    REBUILD_CLOCKS,
    REBUILD_FIELDS,
    REBUILD_PANEL,
    REBUILD_SECTION,
    RETURN_PARAGRAPH,
    STANDARD_SLOTS,
    YES_NO_UNSURE,
    applicant,
    help_question,
    not_only_door,
    policy,
    rebuild_questions,
    statute,
    work_dates,
)
from jason.community.form_library.tiers import (
    ATTESTATION,
    DESCRIPTION,
    PREAMBLE,
    SIGNATURE,
    FormDefinition,
    Required,
    Tier,
    register,
)
from jason.community.forms import FormKey, FormQuestion, FormTemplate, QuestionKind, ReadAs

LAW = "Civil Code 4765"

PREAMBLE_PARAGRAPHS = (
    "This form is for a physical change to your unit or to the common area that your association's governing documents require you "
    "to ask about first (Civil Code 4765). If you are rebuilding after a disaster, Civil Code 4766 applies as well. The "
    "association's copy of those sections is not an official restatement of them.",
    "**We got it.** We will tell you in writing that we have your application within {ACK_DAYS} business days of the day we "
    "receive it (a target the board proposed, not a law).",
    "**Who decides.** The board decides, at a board meeting, on an agenda item, in open session. The agenda names your unit and the "
    "kind of change in general words, and not your name or your plans.",
    "**When.** Your procedure says we answer within **{MAX_DAYS_APPLICATION} days** of the day we receive your application "
    "({PROCEDURE_CITATION}). {WHOSE_APPLICATION_CLOCK}. If your application is missing something we need, we tell you in writing "
    "what it is and how to supply it, and we count again from what you send.",
    "**The decision is in writing.** If we approve it, the letter says so and lists any conditions with the day each is due. If we "
    "disapprove it, the letter says **why**, and it **describes how to ask the board to reconsider**.",
    "**If you disagree.** You may ask the board to reconsider a disapproval at an open board meeting (there is a form for it, or "
    "use your own words). The board answers within **{MAX_DAYS_RECONSIDERATION} days** of your request ({PROCEDURE_CITATION}). "
    "{WHOSE_RECONSIDERATION_CLOCK}.",
    "**If we do not answer in time.** The Civil Code does not say that silence approves a change of this kind. If your procedure "
    "says what follows, we follow it. If it says nothing, write to {BOARD_CONTACT}; the board will put your application on its next "
    "agenda and tell you the date.",
    REBUILD_PANEL,
    INSURANCE_PARAGRAPH,
    not_only_door("what you want to change and where"),
    HELP_PARAGRAPH,
    "Each year the association sends its members the notice of the changes that need approval, with a copy of the procedure: "
    "{ANNUAL_NOTICE_LINK}.",
    RETURN_PARAGRAPH,
)

ATTESTATION_TEXT = ("I am the owner of this unit, or I am authorized by the owner to send this. What I have written is true to the "
                    "best of my knowledge. I understand that an approval by the association is an approval under its procedure, and "
                    "does not say that the change is safe, meets the building code, is insured, or is worth what it costs.")

QUESTIONS = (
    *applicant(LAW, decision="the written decision", other="A contractor, with the owner's signature"),
    FormQuestion("What kind of change is it?", QuestionKind.CHOICE, key="change_category", section="The change",
                 options=("A change inside my unit", "A change outside my unit (a wall, roof, door, window, yard)",
                          "A change in my exclusive-use area", "A change in the common area", "Something else", "Not sure"),
                 authority="the annual notice names the types of change that need approval (Civil Code 4765(c))"),
    FormQuestion("What do you want to do? Describe it in your own words", QuestionKind.PARAGRAPH, key="change_what",
                 authority="a decision needs something to decide (Civil Code 4765(a)(2))"),
    FormQuestion("Where?", QuestionKind.CHOICE, key="change_where",
                 options=("Inside my unit", "Outside my unit (a wall, roof, door, window, yard)", "In my exclusive-use area",
                          "In the common area", "Not sure"),
                 authority="the separate interest or the common area (Civil Code 4765(a))"),
    FormQuestion("Which part? (for example, rear patio, east wall)", required=False, key="change_location_detail",
                 authority="helps find the part; the plan shows it exactly"),
    FormQuestion("What does it replace, if anything?", required=False, key="replaces",
                 authority="a unit's record links an approval to what it changes"),
    FormQuestion("In your words, is it", QuestionKind.CHOICE, required=False, key="like_for_like",
                 options=("The same as what is there", "Different from what is there", "New"),
                 authority="your own word, kept as yours and never as the association's finding"),
    FormQuestion("I am attaching", QuestionKind.CHECKBOX, required=False, key="plans_attached", section="Plans and the work",
                 options=("Drawings to scale", "A description of materials and colors", "Photos of the area", "Product sheets"),
                 help="Your association's checklist for this kind of change says which you need. Plans and specifications are what "
                      "a modification for access is reviewed on.",
                 authority="plans and specifications (Civil Code 4760(a)(2)(D)); the documents' checklist"),
    FormQuestion("Who will do the work?", QuestionKind.CHECKBOX, required=False, key="owner_doing_work",
                 options=("I am doing the work myself",), authority="tells us there is no contractor to ask about"),
    FormQuestion("Contractor's name", required=False, key="contractor_name", reads=ReadAs.NAME,
                 authority="the documents; proposed policy improvement-application-contents"),
    FormQuestion("The contractor's licence number", required=False, key="contractor_license",
                 authority="the documents; proposed policy improvement-application-contents"),
    FormQuestion("The contractor's insurance", QuestionKind.CHECKBOX, required=False, key="contractor_insurance",
                 options=("I am attaching the contractor's certificate of insurance",),
                 authority="the documents; proposed policy improvement-application-contents"),
    FormQuestion("Does the work need a city or county permit?", QuestionKind.CHOICE, key="permit_needed", options=YES_NO_UNSURE,
                 authority="a decision may not violate a building code or other law of land use or public safety (Civil Code 4765(a)(3))"),
    FormQuestion("The permit number, if you have it", required=False, key="permit_number",
                 authority="evidence you give us; the association holds no owner's permit"),
    *work_dates("an approval's start and finish times are a proposed policy (improvement-lifetime)", required=True),
    FormQuestion("This change is to make my home easier or safer for a person who is blind, visually handicapped, deaf, or "
                 "physically disabled", QuestionKind.CHECKBOX, required=False, key="accessibility",
                 options=("Check this if it is",), help="We do not ask who the person is or what the condition is.",
                 authority="a member's modification for access (Civil Code 4760(a)(2))"),
    FormQuestion("Is this to rebuild a home that was destroyed or damaged in a disaster?", QuestionKind.CHOICE,
                 key="disaster_rebuild", options=YES_NO_UNSURE, section=REBUILD_SECTION,
                 authority="a substantially similar reconstruction runs on its own clocks (Civil Code 4766(a))"),
    *rebuild_questions(heading=False),
    help_question(),
)

TEMPLATE = FormTemplate(
    key=FormKey.ARCHITECTURAL_APPLICATION,
    title="Application to Change a Unit or the Common Area",
    authority="Civil Code 4765 and 4766: an application for a physical change the governing documents require approval for.",
    description=("Use this form to ask the association to approve a physical change to your unit or to the common area, where the "
                 "governing documents require approval first. {ASSOCIATION} decides it by the procedure in the documents."),
    questions=QUESTIONS,
    preamble=PREAMBLE_PARAGRAPHS,
    attestation=ATTESTATION_TEXT,
    code="AP",
)

REQUIRED = (
    Required("The change, said so it can be decided: what, where, and whether it is the separate interest or the common area",
             ("change_category", "change_what", "change_where", "change_location_detail"), "CIV 4765(a); CIV 4765(a)(2)"),
    Required("The owner and the unit, and who is submitting", ("unit", "owner_name", "submitted_by", "rep_authorization"),
             "CIV 4765(a)(4); CIV 4041(a)(3)"),
    Required("Plans and specifications", ("plans_attached",), "CIV 4760(a)(2)(D)"),
    Required("Contractor, licence, and insurance", ("owner_doing_work", "contractor_name", "contractor_license", "contractor_insurance"),
             "the documents; proposed policy improvement-application-contents"),
    Required("The permit, where the change needs one", ("permit_needed", "permit_number"), "CIV 4765(a)(3)"),
    Required("Start and finish dates", ("start_date", "finish_date"), "proposed policy improvement-lifetime"),
    Required("The maximum time for response to an application", (PREAMBLE,), "CIV 4765(a)(1)"),
    Required("The maximum time for response to a request for reconsideration", (PREAMBLE,), "CIV 4765(a)(1)"),
    Required("That the decision will be in writing, with reasons if disapproved and a description of the reconsideration procedure",
             (PREAMBLE,), "CIV 4765(a)(4)"),
    Required("That a disapproved applicant may ask the board to reconsider at an open meeting, and how", (PREAMBLE,), "CIV 4765(a)(5)"),
    Required("The rebuild section: its clocks, the list of incomplete items, the appeal, and the end of appeals once approved",
             ("disaster_rebuild", *REBUILD_FIELDS, PREAMBLE), "CIV 4766(b); CIV 4766(c); CIV 4766(d); CIV 4766(e); CIV 4766(f)"),
    Required("The accessibility track", ("accessibility",), "CIV 4760(a)(2)(D)"),
    Required("The owner's signature, a representative's authorization, and the date", (SIGNATURE, ATTESTATION, "rep_authorization"),
             "the documents; proof of who applied"),
    Required("Help, another format, and that a request in other words is still a request", ("help_needed", PREAMBLE),
             "the standard (docs/form-templates.md)"),
    Required("A pointer to the annual notice and its copy of the procedure", (PREAMBLE,), "CIV 4765(c)"),
    Required("What the form is for, in words a member can read", (DESCRIPTION,), "docs/form-templates.md"),
)

# Fields a profile may add when its documents ask (never a condition of the application; docs/form-templates/architectural-
# application.md, 13): the neighbors' acknowledgment, and the review fee the documents set.
NEIGHBOR_ACKNOWLEDGMENT = FormQuestion(
    "Neighbors who may be affected have been told", QuestionKind.CHOICE, required=False, key="neighbor_ack",
    options=("Attached", "Not attached", "Does not apply"),
    help="This is a courtesy so your neighbors know. It is not their consent, and no one's signature decides your application.",
    authority="the documents ask for it (proposed policy improvement-neighbors); never a condition")
FEE_ACKNOWLEDGMENT = FormQuestion(
    "The review fee", QuestionKind.CHECKBOX, required=False, key="fee_ack",
    options=("I have paid, or will pay, the review fee the documents set",),
    authority="the documents set a fee for this kind of change; none is invented")

CLOCKS = (
    ACKNOWLEDGMENT_CLOCK,
    policy("completeness", "the day received", 15, "improvement-review-time",
           "proposed: the application stands as complete on the next day (a policy the board may or may not adopt; the Act states it "
           "only for a rebuild)"),
    policy("decision", "the day the application is complete", 45, "improvement-review-time; CIV 4765(a)(1) requires the documents to "
           "state the maximum",
           "a finding for the board; 4765 states no deemed approval; the member is told what the procedure says"),
    MEETING_NOTICE_CLOCK,
    policy("reconsideration-window", "the date of the written decision", 30, "improvement-reconsideration",
           "a later request is taken at the board's discretion or as a new application; counsel reads whether a window narrows the "
           "entitlement"),
    policy("reconsideration-response", "the day the request for reconsideration is received", 45, "improvement-reconsideration; "
           "CIV 4765(a)(1) requires the documents to state the maximum",
           "a finding for the board; a special meeting is the board's choice"),
    *REBUILD_CLOCKS,
    statute("annual-notice", "the previous annual notice", 365, "CIV 4765(c)",
            "the notice catalog's architectural-requirements row shows it open (jason notices)"),
)

ACKNOWLEDGMENT = (
    "We received your request to change {UNIT_ADDRESS} on **{RECEIVED}**. Your reference is **{REFERENCE}**; please write it on "
    "anything you send us about this request.\n\n"
    "Under {PROCEDURE_CITATION}, we answer within {MAX_DAYS_APPLICATION} days of the day we received it, which is **{DUE}**. "
    "{DECIDER} decides it, at an open meeting of the board; the next meeting that can be noticed in time is {NEXT_MEETING}. We will "
    "tell you in writing what the decision is. If it is a disapproval, the letter will say why and how to ask the board to "
    "reconsider (the board answers a request within {MAX_DAYS_RECONSIDERATION} days).\n\n"
    "If we need anything else from you, we will write to say exactly what it is and how to send it. Nothing here is a decision.\n\n"
    "[Rebuild only] Because you told us this is a rebuild after a disaster, we will tell you whether your application is complete or "
    "incomplete by **{COMPLETE_DUE}**, 30 calendar days after we received it.\n\n"
    "This acknowledgment says only that we have your request and when. It is not an approval."
)

SLOTS = (*STANDARD_SLOTS, "PROCEDURE_CITATION", "MAX_DAYS_APPLICATION", "MAX_DAYS_RECONSIDERATION", "ACK_DAYS",
         "WHOSE_APPLICATION_CLOCK", "WHOSE_RECONSIDERATION_CLOCK", "ANNUAL_NOTICE_LINK")

NOTES = (
    PROCEDURE_NOTE,
    "4765 states no deemed approval for an ordinary application; the proposed clocks are labeled proposed policy until the board "
    "adopts them by a written rule on subject 4355(a)(6) (general notice, 4360(a)).",
    "The neighbors' acknowledgment and the fee acknowledgment are asked only where the documents do; a profile adds "
    "NEIGHBOR_ACKNOWLEDGMENT or FEE_ACKNOWLEDGMENT with an Add row.",
    "A rebuild runs on the 4766 clocks for any application the member says is a rebuild; no rebuild fact is required to start them.",
)

DEFINITION = register(FormDefinition(
    key="architectural-application",
    tier=Tier.STATE,
    jurisdiction="CA",
    template=TEMPLATE,
    version="1",
    as_of=AS_OF,
    authority=("CIV 4765", "CIV 4766"),
    required_content=REQUIRED,
    recitals=("CIV 4765(a)(1)", "CIV 4765(a)(4)", "CIV 4765(a)(5)", "CIV 4765(c)", "CIV 4766(b)(1)", "CIV 4766(b)(2)",
              "CIV 4766(b)(3)", "CIV 4766(c)", "CIV 4766(e)(2)", "CIV 4766(f)(1)", "CIV 4760(a)(2)(D)"),
    member_clock=("We tell you in writing that we have your application. The board decides at an open meeting within "
                  "{MAX_DAYS_APPLICATION} days of the day we receive it ({PROCEDURE_CITATION}). The decision is in writing; a "
                  "disapproval says why and how to ask the board to reconsider, and the board answers within "
                  "{MAX_DAYS_RECONSIDERATION} days of your request."),
    association_clocks=CLOCKS,
    acknowledgment=ACKNOWLEDGMENT,
    procedure="respond",
    handler="response-clock",
    channels=CHANNELS,
    slots=SLOTS,
    notes=NOTES,
))
