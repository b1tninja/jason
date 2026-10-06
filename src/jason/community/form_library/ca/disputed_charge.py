"""The notice of a disputed charge, paid under protest, Civil Code 5658: a State form of the California pack.

Built from docs/form-templates/disputed-charge.md. Code ``PR``. The statute asks for no notice: Civil Code 5658(a) says what
the owner "may" do (pay under protest the disputed amount and all other amounts levied, and commence an action in small
claims court). The form is the owner's record of the protest and the association's record that it was told. Its checklist
is therefore the elements of 5658(a) that make a payment a payment under protest, plus what the association needs to
record it, and no clock the form runs is the law's except the lien release of 5685(b).

**Version notes.** (``VERSION_NOTES`` holds the same words for a program.) **1** (2026-10-05, the law as of that day): the
first version; no earlier form existed, so no question was kept or removed.

**Deviations from the design page.** (1) ``FormQuestion.required`` is a plain flag, so a question the page makes required
only in one case (``email``, ``phone``, ``mailing-address``) is not required, and its help line says when it is needed; the
handler reads the rule (the page's ``required_if``). (2) ``{PAYMENT_CHANNELS}``, ``{ANSWER_DAYS}``, and
``{SMALL_CLAIMS_LIMIT}`` are not slots of this version: the form says a payment goes through the association's usual
payment channel, states the 30-day answer as the association's proposed policy, and states no dollar limit (the small
claims sections are not on the shelf). (3) The page's proposed procedure key is ``disputed-charge``, and a ``ResponseKind``
and a ``KindRule`` for "under protest" (page section 11); the form names ``respond``, which exists. (4) The lien release
clock is the page's row 6 (5685(b), 21 calendar days).
"""

from __future__ import annotations

from jason.community.form_library.ca.common import (
    AS_OF,
    CHANNELS_NOTE,
    HELP_ON_THE_FORM,
    NAME,
    PLAIN_WORDS_NOTE,
    UNIT_ADDRESS,
    contact_questions,
    one_box,
)
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
from jason.community.forms import FormKey, FormQuestion, FormTemplate, QuestionKind

VERSION_NOTES = {"1": "the first version: no earlier form existed"}

CHARGE_KINDS = ("An assessment", "A fine, penalty, or monetary penalty imposed as discipline", "A late fee",
                "A collection cost or attorney's fee", "Interest", "Another charge")

MEMBER_CLOCK = ("If you dispute a charge the association has billed to you, you may pay it under protest and then bring an "
                "action in small claims court, if the amount in dispute is within that court's limit (Civil Code 5658(a)). "
                "You pay the disputed amount and all the other amounts on your account. You may also ask to meet and confer, "
                "or ask for alternative dispute resolution, in addition to paying under protest. Paying under protest does "
                "not stop the association from collecting delinquent assessments (Civil Code 5658(b)). Your payment is "
                "applied first to assessments, then to fees and costs, attorney's fees, late charges, and interest (Civil "
                "Code 5655(a)); if you ask, we will give you a receipt showing the date and who received the payment (Civil "
                "Code 5655(b)). We will record your protest on your account and tell the board. Proposed until the board "
                "adopts a time: we will write to you within 30 calendar days to say whether the association will correct the "
                "charge, look at it again, or stand by it. The association decides whether to change a charge; the law does "
                "not set a time for it to answer. The courts decide a small claims case; the association does not decide it "
                "for you. If the association has recorded a lien in error, it must promptly reverse the charges and pay the "
                "costs of dispute resolution (Civil Code 5685(c)). If you do not get an answer, write to {BOARD_CONTACT}.")

TEMPLATE = FormTemplate(
    key=FormKey.DISPUTED_CHARGE,
    title="Notice of a Disputed Charge, Paid Under Protest",
    authority="Civil Code 5658: an owner may pay a disputed charge under protest and bring an action in small claims court.",
    description=("Use this form to tell the association that you dispute a charge and are paying it under protest. The "
                 "association records your protest on your account. You pay through the association's usual payment "
                 "channel; this form takes no payment."),
    preamble=(
        "**Do not write a card, bank, or account number on this form.** Payment is made through the association's usual "
        "payment channel, never through this form.",
        "**The right.** If a dispute exists between the owner of a separate interest and the association regarding any "
        "disputed charge or sum levied by the association, including an assessment, fine, penalty, late fee, collection "
        "cost, or monetary penalty imposed as a disciplinary measure, and the amount in dispute does not exceed the "
        "jurisdictional limits of the small claims court, the owner may, in addition to pursuing dispute resolution under "
        "Civil Code 5925 and the following sections, pay under protest the disputed amount and all other amounts levied, "
        "including any fees and reasonable costs of collection, reasonable attorney's fees, late charges, and interest, and "
        "commence an action in small claims court (Civil Code 5658(a)). Nothing in this section shall impede an association’s "
        "ability to collect delinquent assessments as provided in this article or Article 3 (commencing with Section 5700) "
        "(Civil Code 5658(b)). To ask for alternative dispute resolution, use the Request for Resolution form.",
        "**Alternative dispute resolution is not required first.** The prerequisite of Civil Code 5930 does not apply to a "
        "small claims action or, except as otherwise provided by law, to an assessment dispute (Civil Code 5930(c), (d)).",
        "**Your payment.** Payments toward the debt are first applied to the assessments owed, and only after those are paid "
        "in full to the fees and costs of collection, attorney's fees, late charges, or interest (Civil Code 5655(a)). When "
        "you make a payment you may request a receipt, and the association shall provide it, showing the date of payment "
        "and the person who received it (Civil Code 5655(b)). If you pay less than all other amounts levied, the payment is "
        "applied the same way and the association's collection continues on what is unpaid; whether it is a payment under "
        "protest is for counsel.",
        "**What comes next.** " + MEMBER_CLOCK,
        CHANNELS_NOTE,
        PLAIN_WORDS_NOTE,
        HELP_ON_THE_FORM,
    ),
    questions=(
        NAME,
        UNIT_ADDRESS,
        FormQuestion("What kind of charge do you dispute?", QuestionKind.CHOICE, True, CHARGE_KINDS,
                     "Civil Code 5658(a) lists the kinds.", "charge-kind", section="The charge"),
        FormQuestion("Which charge? (the date, the notice or statement it was on, what it says)", QuestionKind.PARAGRAPH, True,
                     key="charge-description", help="So the association can find the charge on your account."),
        FormQuestion("The amount you dispute", required=True, key="charge-amount", authority="Civil Code 5658(a)"),
        FormQuestion("Why do you dispute it?", QuestionKind.PARAGRAPH, True, key="why", authority="Civil Code 5658(a)"),
        FormQuestion("The total you are paying: the disputed amount and all other amounts on your account", required=True,
                     key="paid-amount", authority="Civil Code 5658(a)", section="Your payment"),
        FormQuestion("The date you paid or will pay", QuestionKind.DATE, True, key="paid-date",
                     help="The date of payment is the date of the protest."),
        one_box("Paying under protest", "protest", "I am paying this under protest. I dispute the charge described above",
                required=True, authority="Civil Code 5658(a)"),
        one_box("A receipt", "receipt", "Send me a receipt for this payment", authority="Civil Code 5655(b)"),
        one_box("Meet and confer", "also-meet-confer", "Also: I ask to meet and confer with a director about this charge",
                help="The association shall not refuse a request to meet and confer (Civil Code 5915(b)(2)).",
                authority="Civil Code 5658(a); 5915(b)(1)"),
        *contact_questions("How should we reach you about this?", why="The association's reply."),
    ),
    signature="Signature of owner",
    code="PR",
)

REQUIRED = (
    Required("A dispute exists between the owner and the association about a charge or sum levied",
             ("charge-kind", "charge-description", "why"), "CIV 5658(a)"),
    Required("The amount in dispute, so it can be read against the small-claims limit", ("charge-amount",), "CIV 5658(a)"),
    Required("The owner pays the disputed amount and all other amounts levied", ("paid-amount", "paid-date"), "CIV 5658(a)"),
    Required("The payment is under protest", ("protest",), "CIV 5658(a)"),
    Required("The owner may also pursue dispute resolution, and may commence a small claims action", (PREAMBLE,),
             "CIV 5658(a)"),
    Required("The association's ability to collect delinquent assessments is not impeded", (PREAMBLE,), "CIV 5658(b)"),
    Required("A receipt on request, showing the date and who received the payment", ("receipt", PREAMBLE), "CIV 5655(b)"),
    Required("A request to meet and confer, in writing, if the owner wants one", ("also-meet-confer",), "CIV 5915(b)(1)"),
    Required("An email address is asked for only if the owner picks email", ("contact-method", "email"),
             "CIV 4041(b)(2)(A)"),
    Required("The owner's own statement of the protest, signed", (SIGNATURE,), "CIV 5658(a)"),
    Required("A request in other words is still a request, and where to get help", (PREAMBLE,), "standard 5"),
)

CLOCKS = (
    Clock("acknowledge", "receipt", 2, DayKind.BUSINESS, SetBy.PROPOSED_POLICY, "", "none in the law"),
    Clock("record", "receipt", 2, DayKind.BUSINESS, SetBy.PROPOSED_POLICY, "CIV 5658(a)",
          "the association cannot show it was told; the owner's evidence is the form"),
    Clock("receipt", "the payment", 5, DayKind.BUSINESS, SetBy.PROPOSED_POLICY, "CIV 5655(b)",
          "the association has not done what 5655(b) says (shall provide it); what follows is for counsel"),
    Clock("answer", "receipt", 30, DayKind.CALENDAR, SetBy.PROPOSED_POLICY, "CIV 5658(a)",
          "the owner has no answer; the association's record of good faith is weaker"),
    Clock("lien-release", "a determination that a lien was recorded in error", 21, DayKind.CALENDAR, SetBy.STATUTE,
          "CIV 5685(b)", "the association is liable for the costs 5685(c) names"),
)

ACKNOWLEDGMENT = ("Reference {REFERENCE}. We received your notice that you dispute the charge described and have paid under "
                  "protest, on {RECEIVED}. We recorded the protest on your account on {RECORDED}. {DECIDER} will write to "
                  "you by {DUE} to say what the association will do. Your payment is applied as Civil Code 5655(a) requires, "
                  "and you will receive a receipt if you asked for one. If you also asked to meet and confer, a director "
                  "will be designated and will contact you; the association does not refuse that request and there is no "
                  "fee. If you want to add to your notice, write to {RETURN_BY_EMAIL} or {RETURN_BY_MAIL} and quote the "
                  "reference.")

DEFINITION = register(FormDefinition(
    key="disputed-charge",
    tier=Tier.STATE,
    jurisdiction="CA",
    template=TEMPLATE,
    version="1",
    as_of=AS_OF,
    authority=("CIV 5658", "CIV 5655"),
    required_content=REQUIRED,
    recitals=("CIV 5655(a)", "CIV 5655(b)", "CIV 5658(a)", "CIV 5658(b)", "CIV 5930"),
    member_clock=MEMBER_CLOCK,
    association_clocks=CLOCKS,
    acknowledgment=ACKNOWLEDGMENT,
    procedure="respond",
    handler="response-clock",
    channels=(Channel.PAPER, Channel.FILLABLE_PDF, Channel.EMAIL, Channel.PAYHOA, Channel.PORTAL),
    slots=("RETURN_BY_MAIL", "RETURN_BY_EMAIL", "BOARD_CONTACT"),
))
