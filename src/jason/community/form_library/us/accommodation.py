"""Reasonable accommodation or modification request: a State form of the federal pack (jurisdiction ``US``).

The design is docs/form-templates/accommodation-request.md. **The fair-housing statutes are not on the authorities shelf.** The
federal Fair Housing Act and California's Fair Employment and Housing Act (Government Code 12900 and following, with 12927 and
12955) are not held and are not quoted here, so this definition recites only what the shelf holds: the Davis-Stirling Act's own
references to them and its sections on modifying a separate interest for a disability, on pets, and on a grant of exclusive use
"to accommodate a disability":

- 4765(a)(3): a decision on a proposed change "may not violate any governing provision of law, including, but not limited to,
  the Fair Employment and Housing Act", notwithstanding a contrary provision of the governing documents;
- 4700(e): the Act's note of "Section 12927 of the Government Code, relating to the modification of property to accommodate a
  disability";
- 4760(a)(2): a member's right to modify the separate interest to facilitate access, and the association's duty not to deny
  approval "without good cause" (4760(a)(2)(D));
- 4715(a): the pet section, which "may not be construed to affect any other rights provided by law";
- 4600(b)(3)(F): a grant of exclusive use "to accommodate a disability" does not need the member vote of 4600(a).

What the shelf does not say, and so the form does not: who may ask, what a request must contain, what supporting information an
association may ask for, how long it has to respond, whether a request must be in writing, what "reasonable" means, and what
may be charged. For each, the form says "for counsel". **Every clock below is the association's proposed policy**, for the board
to adopt after counsel's advice; none comes from the shelf.

The form never asks for a diagnosis, a condition, a medication, or a provider, and says in words that none is asked. It is a
request, never a refusal: a request in other words, aloud, from someone other than the owner, or on the wrong form is still a
request and is received, dated from the first mention, and answered. The decision is the board's on counsel's reading; jason
never decides, recommends a decision, or reads a request's content into a shared catalog (the page's section 11: the text is a
restricted record, never in a Google Form or a shared register).

Deviations from the page:

- ``{COUNSEL}`` is a slot of this definition (the page lists it among its slots, and its sentence "Our attorney reads every
  request first" needs the name), so the form is not offered to a community until its profile says who reads a request first.
  The page's ``{ACCOMMODATION_CLOCKS}`` and ``{ARCHITECTURAL_PROCEDURE}`` slots are not slots here: a community's clocks are an
  ``Adjust`` row and its architectural procedure is a pointer a community adds.
- The page's sixth clock is the architectural procedure's reconsideration (4765(a)(5)), a statute with no number of days and not
  a clock of this form; it is named in the form's text. The restricted-store flag the page asks of a template (P4) does not
  exist yet: the form is therefore not offered through a Google Form, and nothing keeps its answers out of a shared place beyond
  that until the flag is built (the lesson text in the build report).
- ``required_if`` does not exist on ``FormQuestion``: ``email`` and ``phone`` are ``required=False`` and their help lines say when
  each is needed.
- The page proposes a dedicated procedure, ``accommodation-request`` (``NOTES``); it is not written here. The handler is
  ``response-clock`` with procedure ``respond``.
"""

from __future__ import annotations

from datetime import date

from jason.community.form_library.tiers import (
    PREAMBLE,
    Channel,
    Clock,
    DayKind,
    FormDefinition,
    Required,
    SetBy,
    Tier,
    register,
)
from jason.community.forms import FormKey, FormQuestion, FormTemplate, QuestionKind, ReadAs

CODE = "AM"                                   # accommodation, modification: AM26P-... for the PayHOA form, AM26M-... for the mailed blank

MEMBER_CLOCK = (
    "You may ask us for a change to a rule, a policy, or a practice, or for a change to your home or the common area, because "
    "of a disability. You may ask at any time, in writing or aloud, with this form or without it. You do not need to name a "
    "condition or a diagnosis. **We will not turn your request away because it is on the wrong form, or comes from someone "
    "other than the owner.** We will tell you in writing the day we received your request. Our attorney, {COUNSEL}, reads "
    "every request first; the board decides, and we will give you our answer in writing, with the reasons. We will offer to "
    "talk with you about the request. If the change is to the home or the common area, we will also ask for plans, and the "
    "time our architectural procedure states applies as well. If you disagree with our answer, you may ask the board to "
    "reconsider it at an open meeting, and you may ask to meet and confer (Civil Code 5900 to 5920). The association does not "
    "give legal advice; the law on this subject is mostly outside what we have quoted here, and our attorney reads it. Send "
    "this form to {RETURN_BY_MAIL} or {RETURN_BY_EMAIL}, or answer it online at {PORTAL}, or tell {BOARD_CONTACT}, who will "
    "write it down for you.")

ACKNOWLEDGMENT = (
    "Reference {REFERENCE}. We received your request on {RECEIVED}. {DECIDER} will contact you by {DUE} to talk about it. Our "
    "attorney reads every request first; the board decides, and we will give you our answer in writing, with the reasons, by "
    "{DECISION_BY}. You do not have to name a diagnosis, and we will not turn your request away because of the form it came "
    "on. If you want to change or add to your request, write to {RETURN_BY_EMAIL} or {RETURN_BY_MAIL}, or tell "
    "{BOARD_CONTACT}, and quote the reference.")

SLOTS = ("ASSOCIATION", "RETURN_BY_MAIL", "RETURN_BY_EMAIL", "PORTAL", "BOARD_CONTACT", "COUNSEL")

POINTER = "Pointer: outside the authorities shelf."

TEMPLATE = FormTemplate(
    key=FormKey.ACCOMMODATION_REQUEST,
    title="Request for a Reasonable Accommodation or Modification",
    code=CODE,
    authority=(f"{POINTER} Federal and California fair-housing law (the Fair Housing Act; the Fair Employment and Housing Act, "
               "Government Code 12900 and following) is not quoted here. This form recites only the Davis-Stirling Act's own "
               "references to it: Civil Code 4765(a)(3), 4700(e), 4760(a)(2), 4715(a), and 4600(b)(3)(F)."),
    description=("Use this form to ask {ASSOCIATION} for a change to a rule, a policy, or the way something is done, or for a "
                 "change to your home or the common area, because of a disability. You may ask at any time, in any words, with "
                 "or without this form."),
    signature="",
    dated=False,
    preamble=(
        MEMBER_CLOCK,
        "**We do not ask for a diagnosis.** This form asks for no diagnosis, no condition, no medication, and no provider's "
        "name. You may tell us why the change would help in your own words, or not at all. A letter from someone who knows "
        "the need is welcome but never required; please do not send medical records.",
        "**A request in other words is still a request.** A request made aloud, in a letter, an email, a complaint, an "
        "architectural application, a pet registration, or a parking request is a request. It may come from the owner, a "
        "resident who is not an owner, or someone asking for them, such as a family member, a caregiver, or an advocate. We "
        "will date it from the first day the need was mentioned to us, in any form or words.",
        "**What the Davis-Stirling Act says, and what it does not.** The Act says a decision on a proposed change \"may not "
        "violate any governing provision of law, including, but not limited to, the Fair Employment and Housing Act\" "
        "(Civil Code 4765(a)(3)). It notes the Government Code's section on modifying property to accommodate a disability "
        "(Civil Code 4700(e)), gives a member a right to modify the separate interest to facilitate access, subject to "
        "conditions and with approval not to be denied without good cause (Civil Code 4760(a)(2)), and says the pet "
        "section does not affect other rights provided by law (Civil Code 4715(a)). The statutes that say who may ask, what "
        "a request must contain, and how long the association has are outside what the Association has quoted here, and "
        "counsel reads them. This form's clocks are the Association's proposed policy.",
        "**Who decides.** The board decides, on counsel's reading. The Association is not giving legal advice. If the "
        "change is to the home or the common area, plans and specifications are part of the request, and a disapproval can be "
        "reconsidered at an open meeting of the board (Civil Code 4765(a)(5)).",
        "For an interpreter, large print, another format, a person to write your request down, or a reasonable accommodation "
        "to take part, tick the help question or tell {BOARD_CONTACT}. A request written down for you is returned for you to "
        "confirm.",
    ),
    questions=(
        FormQuestion("Your name", key="name", reads=ReadAs.NAME),
        FormQuestion("Unit address", key="unit-address", prefill="UNIT_ADDRESS", reads=ReadAs.ADDRESS),
        FormQuestion("You are", QuestionKind.CHOICE, key="capacity",
                     options=("An owner of this unit", "A resident who is not an owner",
                              "Someone asking for the owner or the resident", "Someone else"),
                     help="We read the request whoever you are. Your answer is never a reason to refuse it."),
        FormQuestion("If the change is for someone else, their name", required=False, key="person", reads=ReadAs.NAME,
                     help="So our answer names the right person."),
        FormQuestion("What kind of change are you asking for?", QuestionKind.CHOICE, key="kind",
                     options=("A change to a rule, a policy, or the way something is done",
                              "A change to the home or the common area (a modification)", "Both", "I am not sure"),
                     help="Your answer does not limit your request.", authority="Civil Code 4760(a)(2), 4715(a)"),
        FormQuestion("What change are you asking for?", QuestionKind.PARAGRAPH, key="change"),
        FormQuestion("How would this help?", QuestionKind.PARAGRAPH, required=False, key="why",
                     help="You do not have to name a condition or a diagnosis."),
        FormQuestion("Where does this apply?", required=False, key="where",
                     help="Your unit, a common area, a parking space, a rule or a section."),
        FormQuestion("By what date do you need it?", QuestionKind.DATE, required=False, key="when"),
        FormQuestion("Have you already asked about this, in any form or in any words? If so, the date",
                     QuestionKind.DATE, required=False, key="earlier",
                     help="The clock runs from the first time you mentioned it."),
        FormQuestion("Plans or drawings, if the change is to the home or the common area", QuestionKind.PARAGRAPH,
                     required=False, key="plans", help="Describe them here, or attach them.",
                     authority="Civil Code 4760(a)(2)(D)"),
        FormQuestion("A letter that helps explain the need", QuestionKind.CHECKBOX, required=False, key="support",
                     options=("I am attaching a letter that helps explain the need, from someone who knows it",),
                     help="Please do not attach medical records or a diagnosis."),
        FormQuestion("How may we reach you to talk about this?", QuestionKind.CHOICE, key="contact-how",
                     options=("By mail", "By email", "By phone", "In person")),
        FormQuestion("Email address", QuestionKind.EMAIL, required=False, key="email",
                     help="Needed only if you chose email. Kept on this request only."),
        FormQuestion("Phone number", QuestionKind.PHONE, required=False, key="phone",
                     help="Needed only if you chose phone. Kept on this request only."),
        FormQuestion("Do you need help with this form, or with a meeting?", QuestionKind.CHECKBOX, required=False, key="help",
                     options=("I need help",),
                     help="An interpreter, large print, a person to write it down, or a way to hear."),
        FormQuestion("What help do you need?", required=False, key="help-what"),
    ),
)

REQUIRED = (
    Required("A plain way to ask for a change because of a disability, in the member's own words", ("change", "why"),
             "CIV 4765(a)(3)"),
    Required("No question about a diagnosis, a condition, a medication, or a provider: the form says in words that none is "
             "asked", (PREAMBLE,)),
    Required("That a request in other words, and an oral request, is still a request, and may be made at any time",
             (PREAMBLE,)),
    Required("The kind of change: a rule, a policy, or a practice; or a modification of the home or common area", ("kind",),
             "CIV 4760(a)(2); CIV 4700(e); CIV 4715(a)"),
    Required("The plans and specifications, for a modification", ("plans",), "CIV 4760(a)(2)(D)"),
    Required("The date of an earlier mention, so the clock runs from it", ("earlier",)),
    Required("Who needs the change, if not the person asking", ("person",)),
    Required("Where the change applies, and by when it is needed", ("where", "when")),
    Required("Optional supporting information, never records or a diagnosis", ("support", PREAMBLE)),
    Required("How the association will reach the member to talk about it", ("contact-how", "email", "phone")),
    Required("That the association will not refuse the request for being on the wrong form or from the wrong person",
             (PREAMBLE,)),
    Required("The clocks, who decides, and how the member may ask the board to reconsider", (PREAMBLE,),
             "CIV 4765(a)(5)"),
    Required("The decision is the board's on counsel's reading, and the association is not giving legal advice", (PREAMBLE,)),
)

# Every number is the association's proposed policy: the statute that sets any time for an accommodation is outside the
# shelf. Counted from the first day the need is mentioned to the association, in any form or words.
_FIRST = "the first day the need is mentioned to the association"
CLOCKS = (
    Clock("acknowledge", _FIRST, 2, DayKind.BUSINESS, SetBy.PROPOSED_POLICY, "",
          "the member is left without a date; the association's good-faith record is weaker"),
    Clock("counsel-reads", _FIRST, 5, DayKind.BUSINESS, SetBy.PROPOSED_POLICY, "", "the request waits; the member is told"),
    Clock("offer-to-talk", _FIRST, 5, DayKind.BUSINESS, SetBy.PROPOSED_POLICY, "",
          "the association has not engaged with the request"),
    Clock("first-answer", _FIRST, 14, DayKind.CALENDAR, SetBy.PROPOSED_POLICY, "",
          "the member is told why and when the answer will come (a written decision, or a written request for the specific "
          "information needed)"),
    Clock("decision", "a complete request", 30, DayKind.CALENDAR, SetBy.PROPOSED_POLICY, "CIV 4765(a)(1)",
          "nothing on the shelf is deemed approved if the association is late; whether law outside the shelf is, is for "
          "counsel (for a physical change the architectural procedure's maximum response time also applies: the shorter)"),
)

RECITALS = ("CIV 4765(a)(3)", "CIV 4700", "CIV 4760(a)(2)", "CIV 4715(a)", "CIV 4600(b)(3)(F)")

NOTES = (
    "The fair-housing statutes are not on the authorities shelf: the federal Fair Housing Act and California's Fair Employment "
    "and Housing Act (Government Code 12900 and following, 12927, 12955). This definition recites only what the shelf holds, "
    "and the build fails if a recital for a fair-housing statute is added without its text on the shelf. Everything that turns "
    "on those statutes is for counsel.",
    "Every clock is PROPOSED POLICY, for counsel and the board; none comes from the shelf.",
    "The text of a request is a restricted record (level P4): never in a shared catalog, the board or governance tools' open "
    "views, a Google Form, or a register a wider group can read. The line for counsel's list names no person and no health fact.",
    "Proposed dedicated procedure: accommodation-request: (1) stamp the first mention, whatever form it came on; (2) "
    "acknowledge; (3) keep the text in the restricted store and list only the reference for counsel; (4) counsel reads first; "
    "(5) offer to talk and record the date and who took part, not the content; (6) for a modification start the architectural "
    "application in the same record and run its clock beside this one; (7) the board decides on counsel's reading, in "
    "writing, with reasons; (8) record the decision and the date; (9) write each failure as a lesson. Until then: respond.",
    "jason never decides, or recommends a decision on, a request; reads a request's health content into any catalog or tool; or "
    "tells a member what the law requires.",
)

DEFINITION = register(FormDefinition(
    key="accommodation-request",
    tier=Tier.STATE,
    jurisdiction="US",
    template=TEMPLATE,
    version="1",
    as_of=date(2026, 10, 5),
    authority=("CIV 4760", "CIV 4765"),
    required_content=REQUIRED,
    recitals=RECITALS,
    member_clock=MEMBER_CLOCK,
    association_clocks=CLOCKS,
    acknowledgment=ACKNOWLEDGMENT,
    procedure="respond",
    handler="response-clock",
    channels=(Channel.PAPER, Channel.FILLABLE_PDF, Channel.EMAIL, Channel.PAYHOA, Channel.PORTAL),
    slots=SLOTS,
    notes=NOTES,
))
