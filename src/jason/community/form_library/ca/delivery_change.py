"""Change my notice delivery, Civil Code 4041(b)(2)(B): a State form of the California pack.

The design is docs/form-templates/delivery-change.md. The form is the "simple method for the member to inform the
association in writing that the member wishes to change their preferred delivery method" that the annual solicitation must
carry. It sits beside the annual owner information form and sets the same delivery tags by the same rules: its ``delivery``,
``mailing-address``, and ``email`` questions have the annual form's own fields and options (``delivery`` is "By mail" and
"By email"; ``mailing-address`` has the box "Same as my unit address"), so ``member_preferences.propose_tags`` reads an answer
to either form the same way (tests/test_form_library_notices.py compares them).

What the form states, from the text on the shelf (``data/authorities/CIV/CIV-4000-4070.md``, the 2025 session publication):

- 4041(b)(2)(A): "Notification that the member does not have to provide an email address to the association." So the
  ``email`` question is never required unless the member chose email;
- 4041(a)(1): the preferred method "shall include the option of receiving notices at one or both" of a mailing address and a
  valid email address; 4041(c): with no mailing address given, the last one given in writing or, if none, the property address;
- 4041(e): an email address that bounces is not valid, and the notice is resent to a mailing or email address the member gave;
- 4040(a): individual notices go by the member's preferred method, else first-class mail to the address on the books.

What the Act does not say (the form does not say it either): the day a change takes effect, the time to record it, or how
often a member may change. Those are the association's proposed policy, labeled so in the clocks.

Deviations from the page, each for a reason the code states:

- ``required_if`` does not exist on ``FormQuestion``: ``email`` and ``mailing-address`` are ``required=False`` and their help
  line says when they are needed (the handler reads a choice of email with no address as incomplete).
- ``mailing-same`` is the ``same_as`` box of ``mailing-address``, as on the annual form, so the record rules read it unchanged.
- The page's sixth clock (a bounced email, 4041(e)) names a duty and no number of days, so it is not a ``Clock``; the notice
  goes by first-class mail to the address on the books until the member gives a working one (4040(a)(2)).
- The handler is the owner-information return (``owner-information``, procedure ``owner-info-cycle``): the form's effect is
  the cycle's delivery tags. The page proposes a dedicated procedure, ``delivery-requests`` (see ``NOTES``); it is not written
  here. The cycle reads only the annual form's PayHOA submissions today, so reading this form's returns into the same plan is a
  step the wiring still owes (lesson text in the build report).
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

CODE = "NC"                                   # notice change: NC26P-... for the PayHOA form, NC26M-... for the mailed blank

# What the member reads (docs/form-templates/delivery-change.md, section 6); the plain-words note of the association's proposed
# policy, not the statute.
MEMBER_CLOCK = (
    "Use this form any day of the year to change how we deliver your notices. You do not have to give us an email address. "
    "We will follow your change for every notice we begin to deliver on or after the day we receive it, which we will tell "
    "you in writing. A notice we had already begun to deliver stays as it was delivered. No one has to approve your change. "
    "If you chose email and a message to that address fails, we will send the notice again by mail to the address we have for "
    "you. If you do not tell us a mailing address, we use your unit address (Civil Code 4041(c)). Send this form to "
    "{DESIGNATED_PERSON} at {RETURN_BY_MAIL} or {RETURN_BY_EMAIL}, or answer it online at {PORTAL}.")

ACKNOWLEDGMENT = (
    "Reference {REFERENCE}. We received your request to change how we deliver your notices on {RECEIVED}. We will follow it "
    "for every notice we begin to deliver on or after {EFFECTIVE}. We will enter it in our records by {DUE}. {DECIDER} "
    "records it; no one has to approve it. If you gave an email address and we cannot deliver to it, we will write to you by "
    "mail. To change or cancel this request, use the same form or write to {RETURN_BY_EMAIL} or {RETURN_BY_MAIL} and quote "
    "the reference.")

SLOTS = ("ASSOCIATION", "DESIGNATED_PERSON", "RETURN_BY_MAIL", "RETURN_BY_EMAIL", "PORTAL", "BOARD_CONTACT")

TEMPLATE = FormTemplate(
    key=FormKey.DELIVERY_CHANGE,
    title="Change My Notice Delivery",
    code=CODE,
    authority=("Civil Code 4041(b)(2)(B): a simple method for a member to tell the association in writing that the member "
               "wishes to change their preferred delivery method for receiving notices."),
    description=("Use this form to change how {ASSOCIATION} delivers notices to you: by mail, by email, or both. No one has "
                 "to approve your change."),
    preamble=(
        "**Use this form any day of the year.** It is the simple method for telling the Association in writing that you "
        "want to change your preferred delivery method (Civil Code 4041(b)(2)(B)). It has no return-by date.",
        "**You do not have to give us an email address** (Civil Code 4041(b)(2)(A)). You may choose a mailing address, an "
        "email address, or both (Civil Code 4041(a)(1)). If you do not tell us a mailing address, we use the last mailing "
        "address you gave us in writing or, if none, your unit address (Civil Code 4041(c)).",
        MEMBER_CLOCK,
        "If an email address you gave us stops working (a message to it fails), it is no longer a valid delivery method "
        "(Civil Code 4041(e)). We then send the notice again to a mailing or email address you gave us, and until you give "
        "us a working address we use first-class mail to the address on our books (Civil Code 4040(a)(2)).",
        "Your second address, your representative, and your occupancy answers stay as they are unless you use another form. "
        "Choosing mail only takes the email tag off your delivery record; it does not delete the email on your PayHOA "
        "profile, which is your own login.",
        "**A request in other words is still a request.** You do not have to use this form: a letter or an email that says "
        "how you want your notices delivered is a change in writing. For large print, another format, someone to read this "
        "form to you or write it down, or a reasonable accommodation, write to {BOARD_CONTACT}. If you disagree with how a "
        "notice was delivered, write to {BOARD_CONTACT}; you may also ask to meet and confer (Civil Code 5900 to 5920).",
        "The Association's plain-words notes above state its proposed policy and are not the statute; the words of the "
        "sections cited control. The Association's copy of the law is not an official restatement.",
    ),
    attestation=("I certify that I am an owner of this unit, or am authorized to answer for the owner, and that what I have "
                 "written is true."),
    questions=(
        FormQuestion("Your name", key="name", reads=ReadAs.NAME, authority="Civil Code 4041(a)"),
        FormQuestion("Unit address", key="unit-address", prefill="UNIT_ADDRESS", reads=ReadAs.ADDRESS),
        FormQuestion("You are answering as", QuestionKind.CHOICE, key="capacity",
                     options=("An owner of this unit", "Someone the owner has authorized to answer"),
                     help="If you answer for the owner, attach the written authority."),
        FormQuestion("How should the Association deliver notices to you from now on?", QuestionKind.CHECKBOX, key="delivery",
                     options=("By mail", "By email"), section="How we deliver your notices (Civil Code 4041(a)(1))",
                     help="Choose one or both. You do not have to give us an email address. If you choose email, write the "
                          "address below: a choice of email with no address is one we cannot use, so your earlier method "
                          "continues until you give one.",
                     authority="Civil Code 4041(a)(1), (b)(2)(A)"),
        FormQuestion("Mailing address for notices", QuestionKind.SHORT, lines=2, required=False, key="mailing-address",
                     reads=ReadAs.ADDRESS, same_as="Same as my unit address",
                     help="Only if you chose mail. If you do not tell us one, we use your unit address.",
                     authority="Civil Code 4041(a)(1)(A), (c)"),
        FormQuestion("Email address for notices", QuestionKind.EMAIL, required=False, key="email",
                     help="Needed only if you chose email. Choosing email means you agree to receive notices by email; you "
                          "can change this at any time.", authority="Civil Code 4041(a)(1)(B), (b)(2)(A)"),
    ),
)

REQUIRED = (
    Required("A simple method to tell the association in writing of a change of the preferred method, usable any day of the "
             "year", (PREAMBLE, "delivery"), "CIV 4041(b)(2)(B)"),
    Required("The member may choose a mailing address, a valid email address, or both", ("delivery",), "CIV 4041(a)(1)"),
    Required("Notice that the member does not have to provide an email address, and no email address required unless the "
             "member chose email", (PREAMBLE, "email"), "CIV 4041(b)(2)(A)"),
    Required("A way to give the mailing address, and what happens with none", ("mailing-address", PREAMBLE),
             "CIV 4041(a)(1)(A), (c)"),
    Required("Who is asking, and for which unit", ("name", "unit-address", "capacity"), "CIV 4041(a); CIV 4160"),
    Required("The request is in writing and says where it goes (the person designated to receive documents, and a mailing and "
             "an email address)", (SIGNATURE, PREAMBLE), "CIV 4041(b)(2)(B); CIV 4035(a), (b)"),
    Required("What a bounced email means and what the association does", (PREAMBLE,), "CIV 4041(e)"),
    Required("The day a change takes effect, and what is not changed (the association's proposed policy: the law is silent)",
             (PREAMBLE,)),
    Required("That a request in other words is still a request, and where to get help", (PREAMBLE,)),
)

CLOCKS = (
    Clock("acknowledge", "receipt", 2, DayKind.BUSINESS, SetBy.PROPOSED_POLICY, "", "the member is left without a date"),
    Clock("effective", "receipt", 0, DayKind.CALENDAR, SetBy.PROPOSED_POLICY, "CIV 4040(a)(1)",
          "a notice sent the old way after this day is sent again the new way (the resend clock)"),
    Clock("enter-in-books", "receipt", 5, DayKind.BUSINESS, SetBy.PROPOSED_POLICY, "",
          "the change is already effective, but a batch may go the old way unless the handler reads the unrecorded changes"),
    Clock("resend", "the day the association finds a notice went the old way", 3, DayKind.BUSINESS, SetBy.PROPOSED_POLICY, "",
          "the association's delivery record is weaker"),
)

RECITALS = ("CIV 4041(b)(2)(B)", "CIV 4041(b)(2)(A)", "CIV 4041(a)(1)", "CIV 4041(c)", "CIV 4041(e)", "CIV 4040(a)")

# What the definition proposes and does not build (the dedicated procedure the page names is not written here).
NOTES = (
    "A change in the 30 days before the annual reports is still effective, and the annual solicitation's entry date is not "
    "moved (proposed policy, the page's row 4).",
    "Proposed dedicated procedure: delivery-requests, shared with secondary-address and individual-delivery-request; until it "
    "exists the handler's procedure is owner-info-cycle, and notice-delivery covers a resend.",
    "A change from a channel below MATCHED to a new email address is confirmed first to the address on file.",
)

DEFINITION = register(FormDefinition(
    key="delivery-change",
    tier=Tier.STATE,
    jurisdiction="CA",
    template=TEMPLATE,
    version="1",
    as_of=date(2026, 10, 5),
    authority=("CIV 4041", "CIV 4040"),
    required_content=REQUIRED,
    recitals=RECITALS,
    member_clock=MEMBER_CLOCK,
    association_clocks=CLOCKS,
    acknowledgment=ACKNOWLEDGMENT,
    procedure="owner-info-cycle",
    handler="owner-information",
    channels=(Channel.PAPER, Channel.FILLABLE_PDF, Channel.EMAIL, Channel.PAYHOA, Channel.PORTAL),
    slots=SLOTS,
    notes=NOTES,
))
