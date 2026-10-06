"""The request for the membership list, and the opt-out of sharing it: a State form of the California pack.

Built from docs/form-templates/membership-list.md. Code ``MN``. One template, one question first (``action``): ask for the
list, opt out, or end an opt-out. The three share the member's identity and the signature, so one form serves them.

- Civil Code 5220: a member may opt out of the sharing of the member's name, property address, email address, and mailing
  address "by notifying the association in writing that the member prefers to be contacted via the alternative process
  described in subdivision (c) of Section 8330 of the Corporations Code". "This opt-out shall remain in effect until
  changed by the member."
- Civil Code 5225: a member requesting the list "shall state the purpose for which the list is requested which purpose
  shall be reasonably related to the requester's interest as a member".
- Corporations Code 8330(a)(1), (a)(2), (c): the demand is in writing and states the purpose; five business days' prior
  demand to inspect; the list on or before the later of ten business days after the demand is received or the date the
  member names; and a written offer of an alternative method within ten business days.

**Version notes.** (``VERSION_NOTES`` holds the same words for a program.) **1** (2026-10-05, the law as of that day): the
first version of this form. The owner-information form carries the same opt-out as a choice (``membership-list`` in the
profile's form); both set the same tag and the later date stands, so no question of that form was changed.

**Deviations from the design page.** (1) ``FormQuestion.required`` is a plain flag, so a question the page makes required
for one ``action`` only (``how``, ``purpose``, ``delivery`` for a request for the list; ``for-whom`` and
``optout-statement`` for an opt-out) is not required, and its help line says when it is needed; the handler reads the rule
(the page's ``required_if``). (2) The reply (stage 2: ``alternative-answer``, ``alternative-reasons``, ``agree-cost``) needs
a ``stage`` on the template and is a deferred required item. (3) ``{ALTERNATIVE_METHOD}``, ``{LIST_RECORD_DATE}``, and
``{FEE_SCHEDULE}`` are not slots of this version: the form states the law's rule (an alternative method may be offered; a
reasonable charge is told and agreed first) without them. (4) The page's proposed procedure key is ``membership-list``; the
form names ``respond``, which exists.
"""

from __future__ import annotations

from jason.community.form_library.ca.common import (
    AS_OF,
    CHANNELS_NOTE,
    HELP_ON_THE_FORM,
    NAME,
    PLAIN_WORDS_NOTE,
    UNIT_ADDRESS,
    mailing_address,
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

# 5220's words: the statement the opt-out is made by.
OPT_OUT_STATEMENT = ("I prefer to be contacted via the alternative process described in subdivision (c) of Section 8330 of the "
                     "Corporations Code")

ACTIONS = ("Ask for the membership list", "Opt out: do not share my information", "End my opt-out: share my information again")
HOW = ("Inspect and copy the record of members' names and addresses",
       "Receive a list of the names and addresses of the members entitled to vote")

MEMBER_CLOCK = ("If you ask for the membership list, tell us what it is for. The reason must be related to your interest as a "
                "member of the association. We will make the list available no later than ten business days after we "
                "receive your request (or after the date you name for the list, if later). We may, within ten business "
                "days, offer you another way to reach the members without giving you the list; you may accept it, or reject "
                "it in writing and tell us why. We may refuse to give you the list if we reasonably believe the information "
                "will be used for another purpose; if we do, we will say so in writing, and in a later court case the "
                "association carries the burden of proving that you would have used it for a purpose unrelated to being a "
                "member. The list leaves out members who have opted out. If you opt out, your name, property address, email "
                "address, and mailing address are not shared, and members who want to contact you are offered the "
                "alternative process; your choice stays in effect until you change it. If you disagree with a decision, "
                "write to {BOARD_CONTACT} and ask the board to reconsider; you may also go to court, including small claims "
                "court (Civil Code 5235).")

TEMPLATE = FormTemplate(
    key=FormKey.MEMBERSHIP_LIST,
    title="Request for the Membership List, or Opt-Out of Sharing It",
    authority="Civil Code 5220 and 5225; Corporations Code 8330: a member's written demand for the membership list, and a "
              "member's opt-out of its being shared.",
    description=("Use this form to ask for the membership list, to opt out of having your name and addresses shared in it, or "
                 "to end an opt-out. Choose one at the first question and answer only what belongs to it."),
    preamble=(
        "**The opt-out.** A member may opt out of the sharing of the member's name, property address, email address, and "
        "mailing address by notifying the association in writing that the member prefers to be contacted via the "
        "alternative process described in subdivision (c) of Section 8330 of the Corporations Code. This opt-out remains in "
        "effect until changed by the member (Civil Code 5220). The membership list leaves out the members who have opted "
        "out (Civil Code 5200(a)(9)).",
        "**The request.** A member requesting the membership list shall state the purpose for which the list is requested, "
        "which purpose shall be reasonably related to the requester's interest as a member. If the association reasonably "
        "believes that the information in the list will be used for another purpose, it may deny the member access to the "
        "list (Civil Code 5225). The demand is in writing and states the purpose (Corporations Code 8330(a)).",
        "**The time.** The list is made available on or before the later of ten business days after the demand is received or "
        "the date you name as the date the list is to be compiled (Corporations Code 8330(a)(2); Civil Code 5210(b)(6)). To "
        "inspect and copy the record of members' names and addresses at reasonable times, the demand is made five business "
        "days before (Corporations Code 8330(a)(1)). Within ten business days after receiving a demand, the association may "
        "give you a written offer of an alternative method of achieving your purpose without access to or a copy of the "
        "list; you may reject it, in writing, with the reasons the alternative does not meet your purpose (Corporations "
        "Code 8330(c)).",
        "**What it costs.** The association may bill a reasonable charge for a list (Corporations Code 8330(a)(2)). It will "
        "tell you the amount, and you agree to pay it, before anything is copied. The association's plain-words reading: "
        "the charge is the direct and actual cost, as for other records (Civil Code 5205(f)); counsel confirms.",
        "**What the list may be used for.** The records, and any information from them, may not be sold, used for a "
        "commercial purpose, or used for any other purpose not reasonably related to a member's interest as a member (Civil "
        "Code 5230(a)). A membership list is a corporate asset: without the board's consent it may not be used to solicit "
        "money or property, for a purpose the user does not reasonably and in good faith believe will benefit the "
        "association, or for a commercial purpose, and it may not be sold or bought (Corporations Code 8338(a)).",
        "**What comes next.** " + MEMBER_CLOCK,
        CHANNELS_NOTE,
        PLAIN_WORDS_NOTE,
        HELP_ON_THE_FORM,
    ),
    questions=(
        FormQuestion("What do you want to do?", QuestionKind.CHOICE, True, ACTIONS, "Civil Code 5220, 5225; Corporations Code "
                     "8330(a).", "action"),
        NAME,
        UNIT_ADDRESS,
        FormQuestion("This choice is for", QuestionKind.CHOICE, False,
                     ("Me only", "Me and the other owners of this unit, who have each agreed"),
                     "Answer this only to opt out or to end an opt-out. Each owner is a member (Civil Code 5220).", "for-whom",
                     section="To opt out, or to end an opt-out"),
        one_box("The opt-out statement", "optout-statement", OPT_OUT_STATEMENT, help="Check this only to opt out "
                "(Civil Code 5220).", authority="Civil Code 5220"),
        FormQuestion("You want to", QuestionKind.CHOICE, False, HOW, "Answer this only to ask for the list "
                     "(Corporations Code 8330(a)(1), (2)).", "how", section="To ask for the membership list"),
        FormQuestion("What is the list for?", QuestionKind.PARAGRAPH, False, key="purpose",
                     help="Answer this only to ask for the list. The purpose must be reasonably related to your interest as a "
                     "member of the association.", authority="Civil Code 5225"),
        FormQuestion("List as of this date, if you want a later date than the association's latest", QuestionKind.DATE, False,
                     key="as-of", authority="Corporations Code 8330(a)(2)"),
        FormQuestion("How should the list reach you?", QuestionKind.CHOICE, False,
                     ("By electronic transmission", "On paper, by mail", "I will collect it", "I will inspect it"),
                     "Answer this only to ask for the list (Civil Code 5205(h)).", "delivery"),
        FormQuestion("Email address", QuestionKind.EMAIL, False, key="email",
                     help="Fill this in only if you chose electronic transmission.", authority="Civil Code 4041(b)(2)(A)"),
        mailing_address(help="Fill this in only if you chose paper, by mail."),
    ),
    signature="Signature of the member",
    code="MN",
)

REQUIRED = (
    Required("A written request or demand", (SIGNATURE, "name", "unit-address", "action"), "CORP 8330(a)(1), (2)"),
    Required("A statement of the purpose", ("purpose",), "CIV 5225; CORP 8330(a)"),
    Required("The purpose is reasonably related to the member's interest as a member", ("purpose", PREAMBLE), "CIV 5225"),
    Required("Inspect, or receive a list", ("how",), "CORP 8330(a)(1), (2)"),
    Required("The date the list is compiled as of, if the member names one", ("as-of",), "CORP 8330(a)(2)"),
    Required("The list is without members who opted out", (PREAMBLE,), "CIV 5200(a)(9)"),
    Required("A charge: reasonable, told before copying", (PREAMBLE,), "CORP 8330(a)(2); CIV 5205(f)"),
    Required("The opt-out is in writing and names the preference for the alternative process", ("optout-statement", "for-whom"),
             "CIV 5220"),
    Required("The opt-out stays in effect until the member changes it", (PREAMBLE, "action"), "CIV 5220"),
    Required("The use limits", (PREAMBLE,), "CIV 5230(a); CORP 8338(a)"),
    Required("An email address is asked for only if electronic delivery is asked", ("delivery", "email"), "CIV 4041(b)(2)(A)"),
    Required("A request in other words is still a request, and where to get help", (PREAMBLE,), "standard 5"),
    # Not carried yet: the member's answer to an offered alternative, and to a charge, is a second stage of the template.
    Required("The member's answer to an alternative the association offers, in writing, with reasons if rejected, and the "
             "member's agreement to a charge (the reply)", authority="CORP 8330(c); CIV 5205(f)",
             deferred="the reply (alternative-answer, alternative-reasons, agree-cost) needs a stage on the template"),
)

CLOCKS = (
    Clock("acknowledge", "receipt", 2, DayKind.BUSINESS, SetBy.PROPOSED_POLICY, "", "no statutory consequence"),
    Clock("inspect", "the written demand", 5, DayKind.BUSINESS, SetBy.STATUTE, "CORP 8330(a)(1)",
          "the member may sue (CIV 5235; CORP 8336)"),
    Clock("list", "receipt of the demand, or the date the member names for the list if later", 10, DayKind.BUSINESS,
          SetBy.STATUTE, "CIV 5210(b)(6); CORP 8330(a)(2)",
          "the member may sue; a court that finds the association unreasonably withheld access shall award costs and fees and "
          "may assess up to $500 for each separate written request (CIV 5235(a))"),
    Clock("alternative", "receipt of the demand", 10, DayKind.BUSINESS, SetBy.STATUTE, "CORP 8330(c)",
          "the offer is no longer timely; the list is due"),
    Clock("alternative-answer", "the offer", 10, DayKind.BUSINESS, SetBy.PROPOSED_POLICY, "CORP 8330(c)",
          "the offer stands as accepted for what the association must then do (counsel reads it)"),
    Clock("denial", "receipt", 10, DayKind.BUSINESS, SetBy.PROPOSED_POLICY, "CIV 5225",
          "the association's burden in the member's action is harder to carry without a written reason"),
    Clock("opt-out", "receipt of the opt-out or its end", 2, DayKind.BUSINESS, SetBy.PROPOSED_POLICY, "CIV 5220",
          "a list made after the day, still carrying the member's information, is a breach of the member's choice "
          "(CIV 5230(c)(1)(B))"),
)

ACKNOWLEDGMENT = ("Reference {REFERENCE}. We received your {REQUEST_KIND} on {RECEIVED}. If you asked for the membership list, we "
                  "will make it available, or offer you another way to reach the members, by {DUE}. {DECIDER} handles your "
                  "request. The membership list leaves out members who have opted out. If you opted out, we recorded your "
                  "choice on {RECORDED}; it stays in effect until you change it. If you want to change your request, write to "
                  "{RETURN_BY_EMAIL} or {RETURN_BY_MAIL} and quote the reference.")

DEFINITION = register(FormDefinition(
    key="membership-list",
    tier=Tier.STATE,
    jurisdiction="CA",
    template=TEMPLATE,
    version="1",
    as_of=AS_OF,
    authority=("CIV 5220", "CIV 5225", "CORP 8330"),
    required_content=REQUIRED,
    recitals=("CIV 5200(a)", "CIV 5210(b)", "CIV 5220", "CIV 5225", "CIV 5230(a)", "CORP 8330", "CORP 8338(a)"),
    member_clock=MEMBER_CLOCK,
    association_clocks=CLOCKS,
    acknowledgment=ACKNOWLEDGMENT,
    procedure="respond",
    handler="response-clock",
    channels=(Channel.PAPER, Channel.FILLABLE_PDF, Channel.EMAIL, Channel.PAYHOA, Channel.PORTAL),
    slots=("RETURN_BY_MAIL", "RETURN_BY_EMAIL", "BOARD_CONTACT"),
))
