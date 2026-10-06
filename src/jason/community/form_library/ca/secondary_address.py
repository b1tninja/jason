"""Secondary address for notices and collection notices, Civil Code 4040(b) and 5260(b): a State form of the California pack.

The design is docs/form-templates/secondary-address.md. A member who asks "to add or remove a second email or mailing address
for delivery of individual notices" (5260(b)) is owed, from the day the association receives the request, "an additional copy"
of two groups of documents (4040(b)): the annual reports of Article 7 of Chapter 6 (5300 to 5320), and the collection documents of
Article 2 of Chapter 8 and Section 5710. The form says so, lists the sections that plainly deliver or serve a document on the
member, and says plainly that collection notices can show what is owed. It never asks the member to name a legal
representative (that is 4041(a)(3) on the annual form, and 5710(b) is another act), a phone number, a relationship, or a reason.

The text on the shelf (``data/authorities/CIV/``) has no section in 5650 to 5690 that names a secondary address: the tie is
4040(b)(2). Whether the payment-plan standards of 5665(a) are "documents to be delivered" is for counsel (the page's lead 1),
so the list stops at the four the text plainly delivers.

Deviations from the page:

- The page's ``other-notices`` box (copies of the other individual notices, beyond the two groups 4040(b) names) is printed only
  if the board adopts the policy of the page's lead 2. A form cannot print a question on a profile's setting, so the base form
  has no such question: a community whose board adopts the policy adds it with
  ``Add("secondary-address", FormQuestion("Also send the second address copies of the other notices ...", key="other-notices"))``.
- ``required_if`` does not exist on ``FormQuestion``: ``remove-which`` and the two address questions are ``required=False`` and
  their help lines say when one is needed.
- The handler is the owner-information return (``owner-information``, procedure ``owner-info-cycle``), because the form's effect
  is the cycle's: an additional owner record, added without an invitation, named exactly as the owner wrote it, and tagged for
  additional deliveries. The page proposes a dedicated procedure, ``delivery-requests`` (``NOTES``); it is not written here.
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

CODE = "NA"                                   # notice, additional: NA26P-... for the PayHOA form, NA26M-... for the mailed blank

MEMBER_CLOCK = (
    "You may ask us in writing to send a second copy of some notices to another email address or mailing address. The law "
    "names which: the annual budget report, the annual policy statement, and the other annual reports; and the notices we "
    "send about assessments that are past due (the notice before a lien, the copy of the recorded notice, the lien release, "
    "and a notice of default). We will start sending the second copies from the day we receive your request. We will not "
    "send copies of a notice we had already sent. You can remove a second address the same way, and we stop on the day we "
    "receive that request. These notices can show what you owe, so give an address you trust. We will tell you in writing "
    "the day we received your request. Send it to {DESIGNATED_PERSON} at {RETURN_BY_MAIL} or {RETURN_BY_EMAIL}, or answer "
    "it online at {PORTAL}.")

ACKNOWLEDGMENT = (
    "Reference {REFERENCE}. We received your request about your second address for notices on {RECEIVED}. From that day we "
    "will send an additional copy of the notices the law names to the address you gave. {DECIDER} records it; no one has to "
    "approve it. If you asked us to remove an address, we stopped using it on {RECEIVED}. We will enter your request in our "
    "records by {DUE}. We will write to your address on file to say we received it, so you can tell us if it was not you. To "
    "change or cancel this request, use the same form or write to {RETURN_BY_EMAIL} or {RETURN_BY_MAIL} and quote the "
    "reference.")

SLOTS = ("ASSOCIATION", "DESIGNATED_PERSON", "RETURN_BY_MAIL", "RETURN_BY_EMAIL", "PORTAL", "BOARD_CONTACT")

TEMPLATE = FormTemplate(
    key=FormKey.SECONDARY_ADDRESS,
    title="Second Address for Notices",
    code=CODE,
    authority=("Civil Code 4040(b) and 5260(b): a member's written request to add or remove a second email or mailing address "
               "for delivery of notices."),
    description=("Use this form to ask {ASSOCIATION} to send an additional copy of some notices to a second email address or "
                 "mailing address, or to stop using one. You may use it any day of the year."),
    preamble=(
        "**Who gets copies.** When we receive your request, we send an additional copy of two groups of documents to the "
        "second address (Civil Code 4040(b)): (1) the annual reports: the annual budget report, the annual policy statement, "
        "the review of the financial statement, and the other documents of Civil Code 5300 to 5320; and (2) the notices about "
        "assessments past due: the notice before a lien is recorded (Civil Code 5660), the copy of the recorded notice of "
        "delinquent assessment (Civil Code 5675(e)), the lien release or the notice that a lien was recorded in error (Civil "
        "Code 5685), and a notice of default (Civil Code 5710(b)).",
        MEMBER_CLOCK,
        "**Who sees these.** Collection notices can show what is owed and to whom. Give only an address you trust. You may "
        "choose a second email address, a second mailing address, or both; you do not have to give an email address (Civil "
        "Code 4041(a)(2), (b)(2)(A)).",
        "**Where your request goes.** A request is effective when it is delivered to the Association in writing, to the person "
        "designated to receive documents or, if none, to the president or secretary (Civil Code 5260; Civil Code 4035(a)). "
        "Send it to {DESIGNATED_PERSON} at {RETURN_BY_MAIL} or {RETURN_BY_EMAIL}.",
        "A second address is also where we send a notice again if an email address you gave us stops working (Civil Code "
        "4041(e)). The Association must tell members every year that they may ask to have notices sent to up to two "
        "different specified addresses (Civil Code 5310(a)(2)).",
        "This form does not name a legal representative. That is a separate question on the annual owner information form "
        "(Civil Code 4041(a)(3)).",
        "**A request in other words is still a request.** A letter or an email that says \"also send my notices to ...\" "
        "is a request. For large print, another format, someone to read this form to you or write it down, or a reasonable "
        "accommodation, write to {BOARD_CONTACT}. You may also ask to meet and confer (Civil Code 5900 to 5920).",
        "The Association's plain-words notes above state its proposed policy and are not the statute; the words of the "
        "sections cited control. The Association's copy of the law is not an official restatement.",
    ),
    attestation=("I certify that I am an owner of this unit, or am authorized to answer for the owner, and that what I have "
                 "written is true."),
    questions=(
        FormQuestion("Your name", key="name", reads=ReadAs.NAME, authority="Civil Code 5260"),
        FormQuestion("Unit address", key="unit-address", prefill="UNIT_ADDRESS", reads=ReadAs.ADDRESS),
        FormQuestion("You are answering as", QuestionKind.CHOICE, key="capacity",
                     options=("An owner of this unit", "Someone the owner has authorized to answer"),
                     help="If you answer for the owner, attach the written authority."),
        FormQuestion("What do you want to do?", QuestionKind.CHOICE, key="action",
                     options=("Add or change a second address", "Remove a second address"),
                     authority="Civil Code 5260(b)"),
        FormQuestion("Second email address", QuestionKind.EMAIL, required=False, key="second-email",
                     section="The second address (Civil Code 4041(a)(2))",
                     help="For an add or a change, give an email address, a mailing address, or both. You do not have to "
                          "give an email address.", authority="Civil Code 4040(b), 4041(a)(2)(B)"),
        FormQuestion("Second mailing address", QuestionKind.SHORT, lines=2, required=False, key="second-mailing-address",
                     reads=ReadAs.ADDRESS, authority="Civil Code 4040(b), 4041(a)(2)(A)"),
        FormQuestion("Name the mail should be addressed to at the second address (a person or a company)", required=False,
                     key="second-name", reads=ReadAs.NAME,
                     help="So a copy reaches the right hands. For a company, you may write \"in care of\"."),
        FormQuestion("Which one should we stop using?", QuestionKind.CHECKBOX, required=False, key="remove-which",
                     options=("My second email", "My second mailing address"),
                     help="Only if you chose to remove a second address. Tick any.", authority="Civil Code 5260(b)"),
    ),
)

REQUIRED = (
    Required("A request that identifies a secondary email or mailing address", ("second-email", "second-mailing-address"),
             "CIV 4040(b)"),
    Required("A request to add or to remove one, in writing", ("action", "remove-which", SIGNATURE), "CIV 5260(b)"),
    Required("Delivered to the association pursuant to Section 4035 (the person designated to receive documents, and where)",
             (PREAMBLE,), "CIV 5260; CIV 4035(a)"),
    Required("What the second address receives copies of", (PREAMBLE,), "CIV 4040(b)(1), (2)"),
    Required("When it takes effect: upon receipt", (PREAMBLE,), "CIV 4040(b)"),
    Required("The option of a mailing address, an email address, or both; an email address not required",
             ("second-email", "second-mailing-address", PREAMBLE), "CIV 4041(a)(2); CIV 4041(b)(2)(A)"),
    Required("A warning that collection notices contain financial detail", (PREAMBLE,)),
    Required("Who is asking, and for which unit", ("name", "unit-address", "capacity"), "CIV 4160; CIV 4041"),
    Required("That a request in other words is still a request, and where to get help", (PREAMBLE,)),
)

CLOCKS = (
    Clock("acknowledge", "receipt", 2, DayKind.BUSINESS, SetBy.PROPOSED_POLICY, "", "the member is left without a date"),
    Clock("effective", "receipt", 0, DayKind.CALENDAR, SetBy.STATUTE, "CIV 4040(b)",
          "the association has not delivered an additional copy: its delivery record is weaker"),
    Clock("removal-effective", "receipt of a removal", 0, DayKind.CALENDAR, SetBy.STATUTE, "CIV 5260(b)",
          "a copy goes to an address the owner removed: a delivery the owner did not want"),
    Clock("enter-in-books", "receipt", 5, DayKind.BUSINESS, SetBy.PROPOSED_POLICY, "",
          "a batch goes without the copy unless the handler reads the unrecorded requests"),
    Clock("missed-copy", "the day the association finds a copy missed the second address", 3, DayKind.BUSINESS,
          SetBy.PROPOSED_POLICY, "", "the delivery record is weaker"),
    Clock("confirm-to-address-on-file", "receipt from a channel below MATCHED", 2, DayKind.BUSINESS, SetBy.PROPOSED_POLICY, "",
          "a stranger's address could receive an owner's financial notices"),
    Clock("bounce-resend", "the day the preferred email bounces", 3, DayKind.BUSINESS, SetBy.PROPOSED_POLICY, "CIV 4041(e)",
          "the notice has not reached the member"),
)

# Each section the form's list names, so a section that moved or was amended fails the check (the list is read from the shelf).
RECITALS = ("CIV 4040(b)", "CIV 5260", "CIV 4041(a)(2)", "CIV 4035(a)", "CIV 5310(a)(2)", "CIV 4041(e)",
            "CIV 5300", "CIV 5305", "CIV 5320(a)", "CIV 5660", "CIV 5675(e)", "CIV 5685(a)", "CIV 5685(b)", "CIV 5710(b)")

NOTES = (
    "Proposed dedicated procedure: delivery-requests, shared with delivery-change and individual-delivery-request: before each "
    "5300, 5305, 5310, or 5320 document and before each 5660, 5675(e), 5685, or 5710 notice, list the additional deliveries on "
    "the units in the batch, and send each additional copy as its own confirmed batch.",
    "Whether an additional copy of a notice of default goes to a secondary address, and how, is for counsel (the page's lead 1).",
    "A second address belongs to the member who asked: a deed after the request's date ends it (the prior title's).",
    "The 'other-notices' box is a community's Add when its board adopts the policy of the page's lead 2.",
)

DEFINITION = register(FormDefinition(
    key="secondary-address",
    tier=Tier.STATE,
    jurisdiction="CA",
    template=TEMPLATE,
    version="1",
    as_of=date(2026, 10, 5),
    authority=("CIV 4040", "CIV 5260"),
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
