"""Request to receive general notices by individual delivery, Civil Code 4045(b) and 5260(c): a State form of the California pack.

The design is docs/form-templates/individual-delivery-request.md. The text on the shelf (``data/authorities/CIV/``):

- 4045(b): "if a member requests to receive general notices by individual delivery, all general notices to that member, given
  under this section, shall be delivered pursuant to Section 4040", and "The option provided in this subdivision shall be
  described in the annual policy statement prepared pursuant to Section 5310" (5310(a)(4));
- 5260(c): the request, "or a request to cancel a prior request", is effective when "delivered in writing to the association,
  pursuant to Section 4035";
- 4926(a)(1)(C) and 5450(b)(2)(C): a teleconference meeting's notice includes "A reminder that a member may request individual
  delivery of meeting notices, with instructions on how to do so": this form is those instructions.

The Act does not say when the request takes effect, whether it lasts or lapses, whether a fee may be charged, or what becomes
of a notice already begun. Each is the association's proposed policy and is labeled so (the clocks, the member's sentence).

Deviations from the page:

- "What this covers" is a plain list of the sections on the shelf that say "general notice" or "general delivery" (the page's
  section 1), each a recital the check reads, not a list read from the notice catalog at build time; reading the catalog's
  general-delivery rows into the form is a step the notice catalog's recipient rule owes (the page's section 11).
- The member's current method is not printed beside the question (that needs a copy made for one member); the form says where
  a member's method comes from, and the acknowledgment carries ``{CURRENT_METHOD}``.
- The handler is ``response-clock`` (procedure ``respond``): the form's effect is a flag and a register row, not the annual
  cycle's delivery tags. The page proposes a dedicated procedure, ``delivery-requests`` (``NOTES``); it is not written here.
"""

from __future__ import annotations

from datetime import date

from jason.community.form_library.tiers import (
    PREAMBLE,
    SIGNATURE,
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

CODE = "NV"                                   # notice, individual deliVery: NV26P-... for the PayHOA form

MEMBER_CLOCK = (
    "Most notices to all members, such as notices of board meetings with their agendas, proposed rule changes, and election "
    "notices, may be posted or put on our website. If you ask, we will also deliver every one of them to you the way you "
    "chose to receive notices: by mail, by email, or both. If you have not chosen, we use first-class mail to the address on "
    "our books. We will start with every general notice we begin to deliver on or after the day we receive your request, and "
    "we will tell you in writing the day we received it. A notice we had already begun to deliver is not sent again. Your "
    "request stays until you cancel it with this form or you no longer own your unit. We charge nothing for it. Send it to "
    "{DESIGNATED_PERSON} at {RETURN_BY_MAIL} or {RETURN_BY_EMAIL}, or answer it online at {PORTAL}.")

ACKNOWLEDGMENT = (
    "Reference {REFERENCE}. We received your request about general notices on {RECEIVED}. {DECIDER} records it; no one has to "
    "approve it. From {RECEIVED}, every general notice we begin to deliver will also be delivered to you by the way you chose "
    "to receive notices (shown on your record as: {CURRENT_METHOD}). To cancel this request, use the same form or write to "
    "{RETURN_BY_EMAIL} or {RETURN_BY_MAIL} and quote the reference. We will enter your request in our records by {DUE}.")

# For a cancellation, the second and third sentences are replaced by this one.
ACKNOWLEDGMENT_CANCELLED = "We stopped sending you general notices individually on {RECEIVED}."

SLOTS = ("ASSOCIATION", "DESIGNATED_PERSON", "RETURN_BY_MAIL", "RETURN_BY_EMAIL", "PORTAL", "BOARD_CONTACT",
         "GENERAL_NOTICE_LOCATION")

TEMPLATE = FormTemplate(
    key=FormKey.INDIVIDUAL_DELIVERY_REQUEST,
    title="Request to Receive General Notices by Individual Delivery",
    code=CODE,
    authority=("Civil Code 4045(b) and 5260(c): a member's written request to receive general notices by individual delivery, "
               "or to cancel an earlier request."),
    description=("Use this form to ask {ASSOCIATION} to deliver every general notice to you, the way you chose to receive "
                 "notices, or to cancel an earlier request. You may use it any day of the year."),
    preamble=(
        MEMBER_CLOCK,
        "**What this covers: all general notices.** A general notice is the delivery of a document under Civil Code 4045. "
        "The sections that call for one include a proposed rule change and a rule change made (Civil Code 4360(a), (c)), the "
        "result of a member vote to reverse a rule change (Civil Code 4365(g)), an amendment that removes a restricted rental "
        "covenant (Civil Code 4741(f)), a board meeting, with its agenda (Civil Code 4920(c), (d)), election notices (Civil "
        "Code 5115), and the tabulated results of an election (Civil Code 5120(b)). The Association posts general notices at "
        "{GENERAL_NOTICE_LOCATION}.",
        "**How they reach you.** They are delivered by the delivery method you chose for individual notices; if you chose "
        "none, by first-class mail to the address last shown on our books (Civil Code 4040(a)). To choose or change your "
        "method, use the Change My Notice Delivery form.",
        "**Where we tell you about this.** The Association's annual policy statement describes this option (Civil Code "
        "4045(b), 5310(a)(4)). The notice of a meeting held entirely by teleconference reminds members that they may ask "
        "for individual delivery of meeting notices, and this is the form that gives the instructions (Civil Code "
        "4926(a)(1)(C), 5450(b)(2)(C)).",
        "**This is not** a request for a copy of the minutes (that is a different request: Civil Code 4950(a)), a request to "
        "change your delivery method, or a request to add a second address.",
        "**A request in other words is still a request.** A letter or an email that says \"send me all board notices\" is a "
        "request. For large print, another format, someone to read this form to you or write it down, or a reasonable "
        "accommodation, write to {BOARD_CONTACT}. You may also ask to meet and confer (Civil Code 5900 to 5920).",
        "The Association's plain-words notes above state its proposed policy and are not the statute; the words of the "
        "sections cited control. The Association's copy of the law is not an official restatement.",
    ),
    attestation=("I certify that I am an owner of this unit, or am authorized to answer for the owner, and that what I have "
                 "written is true."),
    questions=(
        FormQuestion("Your name", key="name", reads=ReadAs.NAME, authority="Civil Code 5260(c)"),
        FormQuestion("Unit address", key="unit-address", prefill="UNIT_ADDRESS", reads=ReadAs.ADDRESS),
        FormQuestion("You are answering as", QuestionKind.CHOICE, key="capacity",
                     options=("An owner of this unit", "Someone the owner has authorized to answer"),
                     help="If you answer for the owner, attach the written authority."),
        FormQuestion("What do you want?", QuestionKind.CHOICE, key="request",
                     options=("Deliver every general notice to me by the delivery method I chose", "Cancel my earlier request"),
                     authority="Civil Code 4045(b), 5260(c)"),
    ),
)

REQUIRED = (
    Required("A request to receive general notices by individual delivery", ("request",), "CIV 4045(b)"),
    Required("In writing, to the association pursuant to Section 4035 (the person designated to receive documents, and where)",
             (SIGNATURE, PREAMBLE), "CIV 5260(c); CIV 4035"),
    Required("The request covers all general notices to the member", (PREAMBLE,), "CIV 4045(b)"),
    Required("They are delivered by the member's preferred method, else first-class mail to the address on the books",
             (PREAMBLE,), "CIV 4040(a)(1), (2)"),
    Required("A request to cancel a prior request", ("request",), "CIV 5260(c)"),
    Required("The annual policy statement describes the option", (PREAMBLE,), "CIV 4045(b); CIV 5310(a)(4)"),
    Required("The instructions a teleconference meeting's notice promises", (PREAMBLE,), "CIV 4926(a)(1)(C); CIV 5450(b)(2)(C)"),
    Required("Who is asking, and for which unit", ("name", "unit-address", "capacity"), "CIV 4160"),
    Required("That a request in other words is still a request, and where to get help", (PREAMBLE,)),
)

CLOCKS = (
    Clock("acknowledge", "receipt", 2, DayKind.BUSINESS, SetBy.PROPOSED_POLICY, "", "the member is left without a date"),
    Clock("effective", "receipt", 0, DayKind.CALENDAR, SetBy.PROPOSED_POLICY, "CIV 4045(b)",
          "a notice goes by posting only to a member who asked (4045(b) does not say when the request takes effect)"),
    Clock("enter-in-books", "receipt", 5, DayKind.BUSINESS, SetBy.PROPOSED_POLICY, "",
          "a batch goes without the member unless the handler reads the unrecorded requests"),
    Clock("cancellation-effective", "receipt of a cancellation", 0, DayKind.CALENDAR, SetBy.PROPOSED_POLICY, "CIV 5260(c)",
          "a member who cancelled keeps receiving individual copies (the right to cancel is 5260(c); the day is the policy's)"),
    # A notice period is counted back from the meeting: a request received late does not shorten it, and does not extend it.
    Clock("meeting-notice", "the board meeting (the notice is due at least this many days before it)", 4, DayKind.CALENDAR,
          SetBy.STATUTE, "CIV 4920(a)", "the Act's notice periods are the association's, whatever the request"),
)

RECITALS = ("CIV 4045(b)", "CIV 4045(a)", "CIV 4040(a)", "CIV 5260(c)", "CIV 5310(a)(4)", "CIV 4920(c)", "CIV 4920(d)",
            "CIV 4926(a)(1)(C)", "CIV 5450(b)(2)(C)", "CIV 4360(a)", "CIV 4365(g)", "CIV 4741(f)", "CIV 5115(a)",
            "CIV 5120(b)")

NOTES = (
    "Proposed dedicated procedure: delivery-requests, shared with delivery-change and secondary-address: before each general "
    "notice, list the members with the flag on and deliver the notice to each by their method.",
    "The notice catalog needs a recipient rule for members who asked for individual delivery of general notices (shared by the "
    "rows for 4920, 4360, 4365, 4741(f), 5115, and 5120); the form's list of notices is the page's, not read from the catalog.",
    "A cancellation's acknowledgment replaces its second and third sentences with ACKNOWLEDGMENT_CANCELLED.",
    "The request ends with the member's ownership: a transfer of title ends the flag (proposed policy; the Act is silent).",
    "Whether a late request, an emergency meeting (4920(b)(1)), or a meeting held solely in executive session (4920(b)(2)) owes "
    "an individual copy is for counsel (the page's lead 7).",
)

DEFINITION = register(FormDefinition(
    key="individual-delivery-request",
    tier=Tier.STATE,
    jurisdiction="CA",
    template=TEMPLATE,
    version="1",
    as_of=date(2026, 10, 5),
    authority=("CIV 4045", "CIV 5260"),
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
