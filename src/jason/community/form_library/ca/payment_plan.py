"""The request to meet with the board about a payment plan, Civil Code 5665: a State form of the California pack.

Built from docs/form-templates/payment-plan.md. Code ``PP``. The form is sent with the pre-lien notice (Civil Code 5660(d)),
which tells the owner of the right, so the owner has it in hand within the 15 days Civil Code 5665(b) allows.

**Version notes.** (``VERSION_NOTES`` holds the same words for a program.) **1** (2026-10-05, the law as of that day): the
first version; no earlier form existed, so no question was kept or removed.

**Deviations from the design page.** (1) ``FormQuestion.required`` is a plain flag, so a question the page makes required
only in one case (``email``, ``phone``, ``mailing-address``) is not required, and its help line says when it is needed; the
handler reads the rule (the page's ``required_if``). (2) ``{PAYMENT_PLAN_STANDARDS}`` is a slot, as the page says: Civil Code
5665(a) says the association "shall provide the owners the standards for payment plans, if any exists", so the form cannot
be generated until the association gives its standards or the statement that it has none; a community that has not is not
offered this form, and ``jason form-library`` names the slot. (3) The committee rule (``{COMMITTEE_RULE}``) and the board's
meeting calendar (``{BOARD_MEETING_CALENDAR}``) are the handler's inputs, not the form's, and are not slots of this version.
(4) The page's clocks 6 to 9 (no additional late fees during a plan, the right to resume on a default, the matter noted in
the next open minutes, the lien hold) are statements and holds, not clocks the form runs a number on; the form states
the first three in its text, and the lien hold is the handler's proposed policy (page lead 2). (5) The page's proposed
procedure key is ``payment-plan``; the form names ``respond``, which exists.
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

MEMBER_CLOCK = ("If you want to talk about a payment plan for the debt in the notice we sent you, ask the board in writing. For "
                "the board to meet you within the time the law sets, your request must be mailed within 15 days of the date "
                "the notice was postmarked. The board will meet with you in executive session within 45 days of the postmark "
                "of your request (Civil Code 5665(b)). If no regular board meeting falls in that time, the board may name "
                "one or more directors to meet with you instead. The meeting is private; the board notes only generally in "
                "its next open minutes that it was held (Civil Code 4935(e)). Here are the association's standards for "
                "payment plans: {PAYMENT_PLAN_STANDARDS}. A payment plan may include assessments that come due while it "
                "runs, and late fees do not add up during the plan if you keep to its terms (Civil Code 5665(c)). A plan "
                "does not stop the association from recording a lien (Civil Code 5665(d)). If you do not keep to the plan, "
                "the association may go back to collecting from where it left off (Civil Code 5665(e)). Your payments are "
                "applied first to assessments (Civil Code 5655(a)); you may ask for a receipt for any payment (Civil Code "
                "5655(b)). The meeting is a conversation about a plan; the law does not oblige the board to agree to the "
                "plan you propose. If you do not agree with a charge, you may ask to meet and confer, or pay it under "
                "protest. If the association does not meet with you in time, tell {BOARD_CONTACT}; before it records a lien "
                "the association must follow the article's procedures, and if it has not it must start the notice process "
                "again at its own cost (Civil Code 5690).")

TEMPLATE = FormTemplate(
    key=FormKey.PAYMENT_PLAN,
    title="Request to Meet With the Board About a Payment Plan",
    authority="Civil Code 5665: an owner's written request to meet with the board to discuss a payment plan for the debt "
              "noticed under Civil Code 5660.",
    description=("Use this form to ask the board, in writing, to meet with you about a payment plan for the debt in the "
                 "notice the association sent you before it records a lien."),
    preamble=(
        "**The right.** An owner may submit a written request to meet with the board to discuss a payment plan for the debt "
        "noticed under Civil Code 5660. The association shall provide the owners the standards for payment plans, if any "
        "exists (Civil Code 5665(a)).",
        "**The times.** The board shall meet with the owner in executive session within 45 days of the postmark of the "
        "request, if the request is mailed within 15 days of the date of the postmark of the notice, unless there is no "
        "regularly scheduled board meeting within that period, in which case the board may designate a committee of one or "
        "more directors to meet with the owner (Civil Code 5665(b)). The board shall adjourn to, or meet solely in, "
        "executive session to discuss a payment plan (Civil Code 4935(c)). The association's plain-words note: a request "
        "sent later is still read, and the board meets within the same time where it can (the association's proposed "
        "policy, until the board adopts it).",
        "**What a plan may hold.** Payment plans may incorporate any assessments that accrue during the payment plan period. "
        "Additional late fees shall not accrue during the payment plan period if the owner is in compliance with the terms of "
        "the payment plan (Civil Code 5665(c)). Payment plans shall not impede an association's ability to record a lien on "
        "the owner's separate interest to secure payment of delinquent assessments (Civil Code 5665(d)). In the event of a "
        "default on any payment plan, the association may resume its efforts to collect the delinquent assessments from the "
        "time before the payment plan (Civil Code 5665(e)).",
        "**Your payments.** Payments toward the debt are first applied to the assessments owed, and only after those are paid "
        "in full to the fees and costs of collection, attorney's fees, late charges, or interest (Civil Code 5655(a)). When "
        "you make a payment you may request a receipt, and the association shall provide it, showing the date of payment "
        "and the person who received it (Civil Code 5655(b)).",
        "**What comes next.** " + MEMBER_CLOCK,
        CHANNELS_NOTE,
        PLAIN_WORDS_NOTE,
        HELP_ON_THE_FORM,
    ),
    questions=(
        NAME,
        UNIT_ADDRESS,
        one_box("Request to meet with the board", "request",
                "I ask to meet with the board to discuss a payment plan for the debt in the notice the association sent me",
                required=True, authority="Civil Code 5665(a)"),
        FormQuestion("The date on the notice about unpaid assessments, if you have it", QuestionKind.DATE, False,
                     key="notice-date", help="The association knows its own date; this only helps match the notice "
                     "(Civil Code 5665(b))."),
        FormQuestion("The date you mailed or delivered this request", QuestionKind.DATE, True, key="date-sent",
                     help="The 45 days run from the postmark of your request; where there is none, the date you sent it "
                     "(Civil Code 5665(b))."),
        *contact_questions("How should we reach you to set the meeting?", why="Civil Code 5665(b): the board shall meet with "
                                                                              "the owner."),
        FormQuestion("What payment plan would you like to discuss? (optional)", QuestionKind.PARAGRAPH, False, key="proposal",
                     help="Civil Code 5665(a): the request is to discuss a payment plan. We do not ask your income or why the "
                     "debt arose."),
        one_box("Assessments that come due during the plan", "include-accruing",
                "I ask that the plan include the assessments that come due while it runs", authority="Civil Code 5665(c)"),
        FormQuestion("Days and times that suit you for the meeting", QuestionKind.PARAGRAPH, False, key="availability",
                     help="The meeting is within 45 days (Civil Code 5665(b))."),
    ),
    signature="Signature of owner",
    code="PP",
)

REQUIRED = (
    Required("A written request to meet with the board to discuss a payment plan", ("request", SIGNATURE), "CIV 5665(a)"),
    Required("For the debt noticed under 5660", ("notice-date", PREAMBLE), "CIV 5665(a)"),
    Required("The date the request is mailed, for the 15-day window and the 45-day meeting", ("date-sent",), "CIV 5665(b)"),
    Required("The association provides the standards for payment plans, if any exist, or says none exist", (PREAMBLE,),
             "CIV 5665(a)"),
    Required("The meeting is in executive session; a committee of directors may stand in if no regular meeting is scheduled",
             (PREAMBLE,), "CIV 5665(b); CIV 4935(c)"),
    Required("What a plan may hold: accruing assessments; no new late fees while the owner complies",
             (PREAMBLE, "include-accruing"), "CIV 5665(c)"),
    Required("A plan does not stop the association from recording a lien", (PREAMBLE,), "CIV 5665(d)"),
    Required("On a default, the association may resume collection from before the plan", (PREAMBLE,), "CIV 5665(e)"),
    Required("A receipt on request for each payment, and the order a payment is applied", (PREAMBLE,), "CIV 5655(a), (b)"),
    Required("An email address is asked for only if the owner picks email", ("contact-method", "email"),
             "CIV 4041(b)(2)(A)"),
    Required("A request in other words is still a request, and where to get help", (PREAMBLE,), "standard 5"),
)

CLOCKS = (
    Clock("acknowledge", "receipt", 2, DayKind.BUSINESS, SetBy.PROPOSED_POLICY, "", "none in the law"),
    Clock("window", "the postmark of the notice", 15, DayKind.CALENDAR, SetBy.STATUTE, "CIV 5665(b)",
          "the 45-day duty is not triggered by the section's words; the board may still meet (the association's proposed "
          "policy)"),
    Clock("meeting", "the postmark of the request", 45, DayKind.CALENDAR, SetBy.STATUTE, "CIV 5665(b); CIV 4935(c)",
          "the association has not followed a procedure of the article; before recording a lien it shall recommence the "
          "required notice process at its own cost (CIV 5690; a reading for counsel)"),
    Clock("plan", "the meeting", 5, DayKind.BUSINESS, SetBy.PROPOSED_POLICY, "CIV 5665(a)",
          "the owner has no record of the terms; a default cannot be shown on a plan never written"),
)

ACKNOWLEDGMENT = ("Reference {REFERENCE}. We received your written request to meet with the board about a payment plan on "
                  "{RECEIVED}. The request was dated {SENT}. The board will meet with you in executive session by {DUE}, which "
                  "is 45 days from the postmark of your request. {DECIDER} will contact you to set a time. Our standards for "
                  "payment plans are enclosed, or: the association has no written standards for payment plans. If you want "
                  "to change your request, write to {RETURN_BY_EMAIL} or {RETURN_BY_MAIL} and quote the reference.")

DEFINITION = register(FormDefinition(
    key="payment-plan",
    tier=Tier.STATE,
    jurisdiction="CA",
    template=TEMPLATE,
    version="1",
    as_of=AS_OF,
    authority=("CIV 5665", "CIV 5660"),
    required_content=REQUIRED,
    recitals=("CIV 4935(c)", "CIV 5655(a)", "CIV 5655(b)", "CIV 5665(a)", "CIV 5665(b)", "CIV 5665(c)", "CIV 5665(d)",
              "CIV 5665(e)"),
    member_clock=MEMBER_CLOCK,
    association_clocks=CLOCKS,
    acknowledgment=ACKNOWLEDGMENT,
    procedure="respond",
    handler="response-clock",
    channels=(Channel.PAPER, Channel.FILLABLE_PDF, Channel.EMAIL, Channel.PAYHOA, Channel.PORTAL),
    slots=("RETURN_BY_MAIL", "RETURN_BY_EMAIL", "BOARD_CONTACT", "PAYMENT_PLAN_STANDARDS"),
))
