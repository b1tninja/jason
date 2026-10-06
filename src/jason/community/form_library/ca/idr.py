"""The request to meet and confer (internal dispute resolution), Civil Code 5900 to 5920: a State form of the California pack.

Built from docs/form-templates/idr-request.md. Code ``MC``.

The text on disk (``data/authorities/CIV/CIV-5900-5920.md``, the 2025 session publication; none of 5900 to 5920 was amended
in 2025):

- 5910(a): a request invoking the procedure "shall be in writing";
- 5910(b): the procedure "shall state the maximum time for the association to act on a request invoking the procedure";
- 5915(b)(1): the party "may request the other party to meet and confer in an effort to resolve the dispute. The request
  shall be in writing";
- 5915(b)(2): "The association shall not refuse a request to meet and confer";
- 5915(b)(3): "The board shall designate a director to meet and confer";
- 5915(b)(4): the parties "shall meet promptly at a mutually convenient time and place, explain their positions to each
  other" and may be assisted "at their own cost";
- 5915(b)(5) and (c): a resolution is written and signed, including by the board's designee, and binds the parties when it
  is lawful and within the designee's authority or ratified;
- 5910(g) and 5915(d): no fee.

**Version notes.** (``VERSION_NOTES`` holds the same words for a program.)

- **1** (2026-10-05): the generic IDR template every association had, moved into the library unchanged (a return, a marker,
  and a PayHOA form record all know it by ``FormKey.IDR`` and its fields).
- **2** (2026-10-05, the law as of that day): the full form. **Kept**, with the same field: ``name``, ``unit-address``,
  ``email`` (now not required: it is asked for only if the member picks email, Civil Code 4041(b)(2)(A)),
  ``what-is-the-dispute-about``, ``what-outcome-are-you-asking-for`` (now not required: the law asks the member to explain
  a position, and a member may only name the dispute), ``preferred-meeting-days-and-times``. **Added**: ``contact-method``
  (required: the way to reach the member), ``phone``, ``mailing-address``, ``related-notice`` (5670), ``meeting-place``,
  ``assisted-by`` (5910(f)). **Removed**: no question. The description no longer promises that "a board member will
  contact you": 5915(b)(3) says the board shall designate a director. The marker code ``MC`` is set. Required items it
  closes: no refusal (5915(b)(2)), no fee (5910(g), 5915(d)), assistance (5910(f)), the maximum time (5910(b)), the written
  signed agreement and its ratification (5915(b)(5), (c)).

**Deviations from the design page.** (1) ``FormQuestion.required`` is a plain flag, so a question the page makes required
only in one case (``email``, ``phone``, ``mailing-address``) is not required, and its help line says when it is needed; the
handler reads the rule (the page's ``required_if``). (2) The page's ``{IDR_MAX_DAYS}`` slot is not a slot of this version:
the form states the maximum time the page proposes, 30 calendar days from receipt to the meeting, **labeled as the
association's proposed policy** until the board adopts one, so a community that has not adopted one still offers the form
(an unadopted number is never printed as the law's). (3) The reply the association's own letter asks for (stage 2,
``participate``) is not built; it needs a ``stage`` and a ``direction`` on the template. (4) The page's proposed procedure
key is ``meet-and-confer``; the form names ``respond``, which exists.
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
from jason.community.forms import FormKey, FormQuestion, FormTemplate, QuestionKind, ReadAs

VERSION_NOTES = {
    "1": "the generic form moved into the library unchanged",
    "2": "the full form: kept name, unit-address, email, what-is-the-dispute-about, what-outcome-are-you-asking-for, "
         "preferred-meeting-days-and-times; added contact-method, phone, mailing-address, related-notice, meeting-place, "
         "assisted-by; removed none; email no longer required; code MC",
}

MEMBER_CLOCK = ("The association cannot refuse your request to meet and confer. It will not charge you a fee. The board will "
                "designate a director to meet with you promptly, at a time and place that suits you both, to hear your side "
                "and explain the association's. Either of you may bring a lawyer or another person to help, at your own "
                "cost. If you reach an agreement, it will be written down and signed by you and the director; it binds you "
                "both if it is lawful and within the authority the board gave the director, or the board ratifies it. "
                "Proposed until the board adopts a time: we will meet within 30 calendar days of receiving your request, "
                "unless you and the association agree in writing to a later date. If the meeting does not resolve the "
                "dispute, you may ask the board to look at it again, ask to use alternative dispute resolution (Civil Code "
                "5925 to 5965), or go to court, including small claims court when the amount is within its limit. If the "
                "association starts the process with you, you may choose not to take part; if you do take part and the "
                "dispute is not settled by your agreement, you may appeal to the board (Civil Code 5910(d)).")

TEMPLATE = FormTemplate(
    key=FormKey.IDR,
    title="Request for Internal Dispute Resolution",
    authority="Civil Code 5910 and 5915: a written request to meet and confer with the board.",
    description=("Use this form to ask the association to meet and confer about a dispute. The board will designate a "
                 "director to meet with you."),
    preamble=(
        "**The association shall not refuse a request to meet and confer** (Civil Code 5915(b)(2)). **You are not charged a "
        "fee to take part** (Civil Code 5910(g), 5915(d)). The dispute may be about your rights, duties, or liabilities "
        "under the Davis-Stirling Act, the law of nonprofit mutual benefit corporations, or the governing documents "
        "(Civil Code 5900(a)).",
        "**Your request is in writing.** This form, signed, is your written request (Civil Code 5910(a), 5915(b)(1)). "
        "The board shall designate a director to meet and confer (Civil Code 5915(b)(3)). You and the director shall meet "
        "promptly at a mutually convenient time and place, explain your positions to each other, and confer in good faith "
        "in an effort to resolve the dispute (Civil Code 5915(b)(4)).",
        "**You may bring help.** Either of you may be assisted by an attorney or another person in explaining your positions, "
        "at your own cost (Civil Code 5910(f), 5915(b)(4)).",
        "**An agreement is written and signed.** A resolution you and the association agree to shall be written down and "
        "signed by you and the board's designee for the association (Civil Code 5915(b)(5)). It binds you both, and can "
        "be enforced in court, if you both sign it, it does not conflict with the law or the governing documents, and it "
        "is either consistent with the authority the board gave its designee or ratified by the board (Civil Code "
        "5915(c)).",
        "**How long we take.** The association's procedure shall state the maximum time for the association to act on a "
        "request like this (Civil Code 5910(b)). Proposed until the board adopts a time: the meeting is held within 30 "
        "calendar days of the day we receive your request, unless you and the association agree in writing to a later date.",
        "**If the association asks you.** When the association starts this process with you, you may choose not to take "
        "part. If you take part and the dispute is resolved other than by your agreement, you have a right of appeal to the "
        "board (Civil Code 5910(d)).",
        "**What comes next.** " + MEMBER_CLOCK,
        CHANNELS_NOTE,
        PLAIN_WORDS_NOTE,
        HELP_ON_THE_FORM,
    ),
    questions=(
        NAME,
        UNIT_ADDRESS,
        *contact_questions("How should we reach you to set the meeting?", why="Civil Code 5915(b)(4): a mutually convenient "
                                                                              "time and place needs a way to ask."),
        FormQuestion("What is the dispute about?", QuestionKind.PARAGRAPH, key="what-is-the-dispute-about",
                     help="A few sentences. The director needs to know the dispute (Civil Code 5915(b)(1)).",
                     section="The dispute"),
        FormQuestion("What outcome are you asking for?", QuestionKind.PARAGRAPH, False, key="what-outcome-are-you-asking-for",
                     help="What would resolve it for you (Civil Code 5915(b)(4)).",),
        FormQuestion("Is this about something the association sent you?", QuestionKind.CHOICE, False,
                     ("A notice about unpaid assessments", "A notice of a violation or a hearing", "A decision on an application",
                      "Something else, or nothing"), "The association offers to meet and confer before a lien (Civil Code 5670).",
                     "related-notice"),
        FormQuestion("Preferred meeting days and times", QuestionKind.PARAGRAPH, False,
                     key="preferred-meeting-days-and-times", help="Civil Code 5915(b)(4).", section="The meeting"),
        FormQuestion("Where would you like to meet?", QuestionKind.CHOICE, False, ("In person", "By phone", "By video"),
                     "In person at the association's office, by phone, or by video (Civil Code 5915(b)(4)).", "meeting-place"),
        FormQuestion("A person who will help you at the meeting (a lawyer or another person, at your cost), if any",
                     required=False, key="assisted-by", reads=ReadAs.NAME, authority="Civil Code 5910(f)"),
    ),
    signature="Signature of owner",
    code="MC",
)

REQUIRED = (
    Required("The request is in writing", (SIGNATURE,), "CIV 5910(a); CIV 5915(b)(1)"),
    Required("A request that the association meet and confer to resolve the dispute", (PREAMBLE, "what-is-the-dispute-about"),
             "CIV 5915(b)(1)"),
    Required("The association shall not refuse a request to meet and confer", (PREAMBLE,), "CIV 5915(b)(2)"),
    Required("The board designates a director to meet and confer", (PREAMBLE,), "CIV 5915(b)(3)"),
    Required("The member's position, for the parties to explain to each other",
             ("what-is-the-dispute-about", "what-outcome-are-you-asking-for"), "CIV 5915(b)(4); CIV 5910(f)"),
    Required("A time and place that suit both, to meet promptly",
             ("preferred-meeting-days-and-times", "meeting-place"), "CIV 5915(b)(4)"),
    Required("A way to reach the member to set the meeting", ("contact-method", "email", "phone", "mailing-address"),
             "CIV 5915(b)(4)"),
    Required("An email address is asked for only if the member picks email", ("contact-method", "email"),
             "CIV 4041(b)(2)(A)"),
    Required("No fee to take part", (PREAMBLE,), "CIV 5910(g); CIV 5915(d)"),
    Required("Either side may be assisted by an attorney or another person, at its own cost", (PREAMBLE, "assisted-by"),
             "CIV 5910(f); CIV 5915(b)(4)"),
    Required("The maximum time for the association to act on the request (proposed until the board adopts one)", (PREAMBLE,),
             "CIV 5910(b)"),
    Required("A resolution is written and signed by the parties, including the board's designee, and binds if lawful and "
             "within the designee's authority or ratified", (PREAMBLE,), "CIV 5915(b)(5), (c)"),
    Required("When the association invokes the procedure: the member may choose not to take part, and has a right of appeal "
             "to the board if the member takes part", (PREAMBLE,), "CIV 5910(d)"),
    Required("A request in other words is still a request, and where to get help", (PREAMBLE,), "standard 5"),
    # Not carried yet: the member's reply to the association's own letter is a second stage of the template.
    Required("The member's election to take part or not, when the association invokes the procedure (the reply)",
             authority="CIV 5910(d)", deferred="the member's reply (participate) needs a stage and a direction on the template"),
)

CLOCKS = (
    Clock("acknowledge", "receipt", 2, DayKind.BUSINESS, SetBy.PROPOSED_POLICY, "",
          "nothing in the law"),
    Clock("meeting", "receipt", 30, DayKind.CALENDAR, SetBy.PROPOSED_POLICY, "CIV 5910(b); CIV 5915(b)(4)",
          "if the association has no procedure that meets 5910, 5915 applies (CIV 5905(c)); the association may not file a "
          "civil action about the dispute unless it engaged in good faith (CIV 5910.1)"),
    Clock("designate", "receipt", 5, DayKind.BUSINESS, SetBy.PROPOSED_POLICY, "CIV 5915(b)(3)",
          "the meeting cannot be set; the meeting clock keeps running"),
    Clock("contact", "the designation", 3, DayKind.BUSINESS, SetBy.PROPOSED_POLICY, "CIV 5915(b)(4)",
          "the meeting cannot be set; the meeting clock keeps running"),
    Clock("summary", "the meeting", 5, DayKind.BUSINESS, SetBy.PROPOSED_POLICY, "CIV 5915(b)(5)",
          "no written agreement for the parties to sign; the duty to write it down is the statute's"),
)

ACKNOWLEDGMENT = ("Reference {REFERENCE}. We received your written request to meet and confer about a dispute on {RECEIVED}. "
                  "The association does not refuse a request to meet and confer, and there is no fee. The board will "
                  "designate a director, {DECIDER}, to meet you. The meeting is to be held by {DUE}, unless you and the "
                  "association agree in writing to a later date. {DECIDER} will contact you at the way you chose to set a "
                  "time and place. If you want to change your request, write to {RETURN_BY_EMAIL} or {RETURN_BY_MAIL} and "
                  "quote the reference.")

DEFINITION = register(FormDefinition(
    key="idr-request",
    tier=Tier.STATE,
    jurisdiction="CA",
    template=TEMPLATE,
    version="2",
    as_of=AS_OF,
    authority=("CIV 5910", "CIV 5915"),
    required_content=REQUIRED,
    recitals=("CIV 5900(a)", "CIV 5910", "CIV 5910.1", "CIV 5915(b)", "CIV 5915(c)", "CIV 5915(d)", "CIV 5920"),
    member_clock=MEMBER_CLOCK,
    association_clocks=CLOCKS,
    acknowledgment=ACKNOWLEDGMENT,
    procedure="respond",
    handler="response-clock",
    channels=(Channel.PAPER, Channel.FILLABLE_PDF, Channel.EMAIL, Channel.PAYHOA, Channel.PORTAL),
    slots=("RETURN_BY_MAIL", "RETURN_BY_EMAIL"),
))
