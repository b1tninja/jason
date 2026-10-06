"""The request for reconsideration of a disapproval, Civil Code 4765(a)(5) and 4766(e): a State form of the California pack.

Built from docs/form-templates/reconsideration-request.md, the second half of the architectural application. The text on disk
(``data/authorities/CIV/CIV-4760-4766.md`` and ``CIV-4900-4955.md``, the 2025 session publication):

- 4765(a)(5): "If a proposed change is disapproved, the applicant is entitled to reconsideration by the board, at an open meeting
  of the board." It "does not require reconsideration of a decision that is made by the board or a body that has the same
  membership as the board, at a meeting that satisfies the requirements of Article 2"; the form offers it either way (page,
  section 13, reading (b)), and never makes a reason a condition;
- 4765(a)(1): the procedure states the maximum time for the board's response to a request for reconsideration;
- 4766(e): a rebuild's incomplete or noncompliant finding is appealed, and the final written determination comes within 60
  calendar days of the written appeal; 4766(f)(1): once approved, no appeals or additional hearings;
- 4920(a), (d), 4925(a), (b): the meeting is noticed at least four days before, with its agenda, and a member may attend and
  speak within a reasonable time limit.

The members' slots a profile gives: the procedure's citation, the maximum time for the board's response with whose it is, the time
limit to speak, the days to deliver the answer (a proposed policy), and the standard ones. The meeting, its place, and its agenda
link are of one request and are filled by the handler.
"""

from __future__ import annotations

from jason.community.form_library.ca.improvement import (
    AS_OF,
    CHANNELS,
    MEETING_NOTICE_CLOCK,
    PROCEDURE_NOTE,
    RETURN_PARAGRAPH,
    STANDARD_SLOTS,
    ACKNOWLEDGMENT_CLOCK,
    delivery_questions,
    help_question,
    not_only_door,
    owner_question,
    policy,
    representative_question,
    statute,
    submitted_by,
    unit_question,
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
from jason.community.forms import FormKey, FormQuestion, FormTemplate, QuestionKind

LAW = "Civil Code 4765(a)(5)"

DECISION_KINDS = (
    "My change was disapproved",
    "My change was approved, with conditions I ask the board to look at again",
    "My rebuild application was found incomplete",
    "My rebuild application was found not compliant",
    "I am not sure",
)

QUESTIONS = (
    unit_question(LAW, "The decision"),
    FormQuestion("The reference on your decision letter or on the form you sent", required=False, key="reference",
                 authority="ties this to your application; the unit and the date are enough without it"),
    owner_question(LAW),
    submitted_by(""),
    representative_question(),
    FormQuestion("The date on the letter that disapproved it", QuestionKind.DATE, key="decision_date",
                 authority="which decision this is about (Civil Code 4765(a)(5))"),
    FormQuestion("What did the letter say?", QuestionKind.CHOICE, key="decision_kind", options=DECISION_KINDS,
                 authority="if a change is disapproved (Civil Code 4765(a)(5)); a rebuild appeal (Civil Code 4766(e)(1))"),
    FormQuestion("What do you want?", QuestionKind.CHOICE, key="request_kind", section="Your request",
                 options=("Please reconsider the same application",
                          "I changed my plans; please treat this as a new application"),
                 authority="a new application has its own clock (Civil Code 4766(d)(3), (d)(4)); the documents"),
    FormQuestion("What would you like the board to look at again? (You do not need to give a reason.)", QuestionKind.PARAGRAPH,
                 required=False, key="what_to_look_at",
                 authority="helps the board prepare; reconsideration is an entitlement (Civil Code 4765(a)(5))"),
    FormQuestion("New or changed plans or information", QuestionKind.CHECKBOX, required=False, key="new_material",
                 options=("I am attaching new or changed plans or information",),
                 authority="the board may weigh it; for a rebuild a resubmission has its own clock (Civil Code 4766(d)(3), (d)(4))"),
    FormQuestion("How do you plan to take part in the meeting?", QuestionKind.CHOICE, required=False, key="attend_how",
                 section="The meeting",
                 options=("In person", "By phone or video", "I would rather not attend", "Not sure"),
                 authority="the right to attend and to speak (Civil Code 4925(a), (b))"),
    FormQuestion("Help to take part", QuestionKind.CHECKBOX, required=False, key="meeting_help",
                 options=("I need help to take part (an accessible room, a phone line, an interpreter)",),
                 authority="help is on the form"),
    *delivery_questions(LAW, "the written answer"),
    help_question(),
)

PREAMBLE_PARAGRAPHS = (
    "**What you are asking for.** You are asking the board to look again at its decision on a change you asked for. The Civil Code "
    "says that if a change is disapproved, the applicant is entitled to ask the board to reconsider, at an open meeting. You do not "
    "need a new reason to ask. The association's copy of the section is not an official restatement of it.",
    "**Who decides and where.** The board decides, at a board meeting that is open to members. Our acknowledgment names the meeting: "
    "the next one that can be noticed in time. The notice is given at least four days before the meeting and carries the agenda; the "
    "agenda item names your unit and the kind of change in general words, and not your name.",
    "**You may come and you may speak.** Any member may attend, and the board permits any member to speak, within a reasonable time "
    "limit it sets ({TIME_LIMIT_TO_SPEAK} per speaker). The meeting is open, so what is said about your change is said where other "
    "members can hear it. If you would rather not attend, say so on the form; the board will still decide.",
    "**How long the board has.** Your procedure says the board answers a request for reconsideration within "
    "**{MAX_DAYS_RECONSIDERATION} days** of the day it receives the request ({PROCEDURE_CITATION}). {WHOSE_RECONSIDERATION_CLOCK}.",
    "**The answer.** The board's answer is in writing, and we send it within {ANSWER_DELIVERY_DAYS} days of the vote (a target the "
    "board proposed, not a law). If the board again disapproves, the letter says why. It also says whether any further step is "
    "available under our procedure, and it does not use up your other rights, such as asking to meet and confer about a dispute.",
    "**If we do not act in time.** The Civil Code does not say what follows if the board does not act on a request for "
    "reconsideration in time. If your procedure says what follows, we follow it. If it says nothing, write to {BOARD_CONTACT}; the "
    "item goes on the next agenda.",
    "**If your application to rebuild after a declared disaster was found incomplete or not compliant,** you may appeal. We give you "
    "a final written determination within **60 calendar days** of your written appeal (Civil Code 4766(e)(2)); this form is your "
    "written appeal. Once an application is approved, the board may not subject you to any appeals or additional hearings, except "
    "for not complying with what was approved (4766(f)). A new application that fixes what we found is treated as a new application "
    "with its own timelines, and is made on the architectural application (4766(d)(3), (d)(4)). Your reading of these rules is "
    "yours; a lawyer can help you with it.",
    not_only_door("\"please reconsider the decision on\" your unit"),
    "**Help.** Ask {BOARD_CONTACT} for another format, larger print, another language, help filling this in, or help taking part in "
    "the meeting.",
    RETURN_PARAGRAPH,
)

TEMPLATE = FormTemplate(
    key=FormKey.RECONSIDERATION_REQUEST,
    title="Request for Reconsideration of a Decision on a Change",
    authority="Civil Code 4765(a)(5) and 4766(e): a request that the board reconsider a disapproval at an open meeting.",
    description=("Use this form to ask the board of {ASSOCIATION} to reconsider a decision on a change to your unit or the common "
                 "area. The board hears it at an open meeting."),
    questions=QUESTIONS,
    signature="Signature of owner or agent",
    preamble=PREAMBLE_PARAGRAPHS,
    attestation=("I am the owner of this unit, or I am authorized by the owner to send this. What I have written is true to the best "
                 "of my knowledge. I understand the board will consider this at an open meeting that members may attend."),
    code="RC",
)

REQUIRED = (
    Required("Which decision is to be reconsidered: the unit, the decision's date, and the reference", ("unit", "decision_date", "reference"),
             "CIV 4765(a)(5)"),
    Required("Who is asking, and authority if not the owner", ("owner_name", "submitted_by", "rep_authorization"),
             "CIV 4765(a)(5); CIV 4041(a)(3)"),
    Required("What kind of decision it was", ("decision_kind",), "CIV 4765(a)(5); CIV 4766(e)(1)"),
    Required("That the board will reconsider at an open meeting, and which", (PREAMBLE,), "CIV 4765(a)(5); CIV 4920(a)"),
    Required("The board's maximum response time, from the procedure", (PREAMBLE,), "CIV 4765(a)(1)"),
    Required("What the applicant would like looked at again (optional, never a condition)", ("what_to_look_at",),
             "CIV 4765(a)(5)"),
    Required("New or changed plans, and the choice to make it a new application", ("new_material", "request_kind"),
             "CIV 4766(d)(3); CIV 4766(d)(4)"),
    Required("That the meeting is open, the right to attend and to speak, the time limit, and the agenda",
             (PREAMBLE, "attend_how", "meeting_help"), "CIV 4925(a); CIV 4925(b); CIV 4920(d)"),
    Required("The written answer and how it is delivered", ("decision_delivery", "contact_email"), "CIV 4765(a)(4)"),
    Required("For a rebuild: the written appeal, the 60 calendar days, and no appeals once approved", ("decision_kind", PREAMBLE),
             "CIV 4766(e); CIV 4766(f)"),
    Required("Signature, help, and that a request in other words is still a request", (SIGNATURE, ATTESTATION, "help_needed", PREAMBLE),
             "the standard (docs/form-templates.md)"),
)

CLOCKS = (
    ACKNOWLEDGMENT_CLOCK,
    policy("reconsideration-window", "the date of the written decision", 30, "improvement-reconsideration",
           "a later request is taken at the board's discretion, or as a new application; counsel reads whether a window narrows the "
           "entitlement"),
    policy("reconsideration-response", "the day the request is received", 45, "improvement-reconsideration; CIV 4765(a)(1) requires "
           "the documents to state the maximum",
           "a finding for the board; a special meeting is the board's choice; no statutory consequence is stated for an ordinary "
           "request"),
    MEETING_NOTICE_CLOCK,
    statute("continued-item", "the first meeting", 30, "CIV 4930(d)(3)", "beyond 30 calendar days it needs a new agenda item"),
    statute("rebuild-appeal", "the day the written appeal is received", 60, "CIV 4766(e)(2)",
            "no deemed result is stated; fees under 4766(g); counsel"),
    policy("answer-delivered", "the vote", 7, "improvement-reconsideration", "a finding for the manager"),
    statute("minutes-available", "the meeting", 30, "CIV 4950(a)", "the minutes are late; jason notices shows it"),
)

ACKNOWLEDGMENT = (
    "We received your request to reconsider the decision of {DECISION_DATE} on {UNIT_ADDRESS} on **{RECEIVED}**. Your reference is "
    "**{REFERENCE}**.\n\n"
    "{DECIDER} will consider it at an open board meeting. The next meeting that can be noticed in time is **{NEXT_MEETING}**; the "
    "agenda is posted with the notice of that meeting ({AGENDA_LINK}). You may attend and speak. Under {PROCEDURE_CITATION} the "
    "board answers within {MAX_DAYS_RECONSIDERATION} days, which is **{DUE}**. We will send you the answer in writing.\n\n"
    "If you told us you need help to take part, we will contact you about it before the meeting.\n\n"
    "[Rebuild only] Because this is an appeal of a rebuild determination, the final written determination is due within 60 "
    "calendar days of today, **{DUE}**.\n\n"
    "This says only that we have your request and when. It is not a decision."
)

SLOTS = (*STANDARD_SLOTS, "PROCEDURE_CITATION", "MAX_DAYS_RECONSIDERATION", "WHOSE_RECONSIDERATION_CLOCK",
         "TIME_LIMIT_TO_SPEAK", "ANSWER_DELIVERY_DAYS")

NOTES = (
    PROCEDURE_NOTE,
    "The Act states no time for the applicant to ask and no consequence of the board's silence; the clocks that say so are proposed "
    "policy, labeled, until the board adopts them by a written rule (subject 4355(a)(6); general notice, 4360(a)).",
    "The page's proposed ResponseKind.RECONSIDERATION is in responses.py, and its notice-catalog row (architectural-"
    "reconsideration) in notice_catalog.py.",
)

DEFINITION = register(FormDefinition(
    key="reconsideration-request",
    tier=Tier.STATE,
    jurisdiction="CA",
    template=TEMPLATE,
    version="1",
    as_of=AS_OF,
    authority=("CIV 4765(a)(5)", "CIV 4766(e)"),
    required_content=REQUIRED,
    recitals=("CIV 4765(a)(5)", "CIV 4765(a)(1)", "CIV 4765(a)(4)", "CIV 4925(b)", "CIV 4920(a)", "CIV 4766(e)(1)", "CIV 4766(e)(2)",
              "CIV 4766(f)(1)"),
    member_clock=("The board reconsiders at an open meeting, the next one that can be noticed in time (at least four days' notice, "
                  "with the agenda), and answers in writing within {MAX_DAYS_RECONSIDERATION} days of the day it receives your "
                  "request ({PROCEDURE_CITATION}). You may attend and speak."),
    association_clocks=CLOCKS,
    acknowledgment=ACKNOWLEDGMENT,
    procedure="respond",
    handler="response-clock",
    channels=CHANNELS,
    slots=SLOTS,
    notes=NOTES,
))
