"""The Request for Resolution (alternative dispute resolution), Civil Code 5925 to 5965: a State form of the California pack.

Built from docs/form-templates/adr-request.md. Code ``RV``. This is the most exact form in the Act: Civil Code 5935(a) says
what a Request for Resolution "shall include", and the checklist below follows it item by item.

- 5935(a)(1): "A brief description of the dispute between the parties." (``dispute``)
- 5935(a)(2): "A request for alternative dispute resolution." (``adr-request`` and the heading REQUEST FOR RESOLUTION)
- 5935(a)(3): "A notice that the party receiving the Request for Resolution is required to respond within 30 days of receipt
  or the request will be deemed rejected." (the bold notice at the top of the form, in the statute's words)
- 5935(a)(4): "If the party on whom the request is served is the member, a copy of this article." (not required when the
  request is sent to the association, and the form says so; the association's letter to a member is built from the shelf
  with the article attached, a later step)

**Version notes.** (``VERSION_NOTES`` holds the same words for a program.) **1** (2026-10-05, the law as of that day): the
first version of this form; no earlier form existed, so no question was kept or removed.

**Deviations from the design page.** (1) ``FormQuestion.required`` is a plain flag, so a question the page makes required
only in one case (``email``, ``phone``, ``mailing-address``, ``other-party-names``) is not required, and its help line says
when it is needed; the handler reads the rule (the page's ``required_if``). (2) The response (stage 2: ``response``,
``response-kind``, ``response-neutral``, ``response-by``, ``response-date``) and the association's letter to a member (the
other direction, with the article attached) need a ``stage`` and a ``direction`` on the template and the letter generator;
neither is built, and the response is a deferred required item. (3) The page's proposed procedure key is
``request-for-resolution``; the form names ``respond``, which exists. (4) The statute prescribes no response form and sets
no fee; the statement that the association charges none is its proposed policy, and the form says so.
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

# 5935(a)(3), in the statute's words: a notice to the party receiving the request.
NOTICE_30_DAYS = ("**The party receiving this Request for Resolution is required to respond within 30 days of receipt or the "
                  "request will be deemed rejected.**")

# 5965(a): the sentence the annual summary carries, in the statute's words.
SUMMARY_SENTENCE = ("Failure of a member of the association to comply with the alternative dispute resolution requirements of "
                    "Section 5930 of the Civil Code may result in the loss of the member’s right to sue the association or "
                    "another member of the association regarding enforcement of the governing documents or the applicable law.")

ADR_KINDS = ("Mediation", "Conciliation", "Nonbinding arbitration", "Binding arbitration",
             "Another procedure with a neutral person", "No preference")

MEMBER_CLOCK = ("This is a Request for Resolution under Civil Code 5935. The party who receives it is required to respond "
                "within 30 days of receipt or the request will be deemed rejected. A party that does not accept the request "
                "in 30 days has rejected it. If the request is accepted, the parties are to complete alternative dispute "
                "resolution within 90 days of the day the acceptance is received, unless both sign an extension; the "
                "parties pay the costs of it (Civil Code 5940(c)). The association charges no fee to receive or answer this "
                "request (the association's proposed policy, not a rule of the Act). If it is not accepted, the party who "
                "asked may file an action with a certificate saying so; a court that decides fees may consider whether a "
                "refusal to take part was reasonable (Civil Code 5960). Time limits for starting an action are tolled while "
                "the request is pending (Civil Code 5945). Alternative dispute resolution is required before certain "
                "actions in superior court and is not required for a small claims action or, except as the law provides, "
                "for an assessment dispute (Civil Code 5930). If you do not get an answer, the request is rejected after 30 "
                "days; write to {BOARD_CONTACT} if you want it looked at again.")

TEMPLATE = FormTemplate(
    key=FormKey.ADR_REQUEST,
    title="Request for Resolution",
    authority="Civil Code 5935: a Request for Resolution, serving a request for alternative dispute resolution on the other "
              "parties to a dispute.",
    description=("Use this form to ask the other parties to a dispute to use alternative dispute resolution: mediation, "
                 "arbitration, conciliation, or another nonjudicial procedure with a neutral person. It is the request the "
                 "law requires before certain actions in superior court."),
    preamble=(
        "**REQUEST FOR RESOLUTION** (Civil Code 5935). Any party to a dispute may start this process by serving on all other "
        "parties to the dispute a Request for Resolution (Civil Code 5935(a)).",
        NOTICE_30_DAYS,
        "**A brief description of the dispute, and a request for alternative dispute resolution,** are below (Civil Code "
        "5935(a)(1), (2)). Alternative dispute resolution means mediation, arbitration, conciliation, or another "
        "nonjudicial procedure that involves a neutral party in the decisionmaking process. It may be binding or nonbinding, "
        "with the voluntary consent of the parties (Civil Code 5925(a)).",
        "**Serving this request.** Service is by personal delivery, first-class mail, express mail, facsimile transmission, or "
        "other means reasonably calculated to provide the party on whom the request is served actual notice (Civil Code "
        "5935(b)). Email, the PayHOA form, and the association's portal are other such means. Write the date you sent or "
        "delivered it below. A copy of the article (Civil Code 5925 to 5965) is required when the request is served on a "
        "member (Civil Code 5935(a)(4)); it is not required when the request is sent to the association.",
        "**The response.** A party on whom a Request for Resolution is served has 30 days following service to accept or "
        "reject the request. If a party does not accept the request within that period, the request is deemed rejected by the "
        "party (Civil Code 5935(c)). If the request is accepted, the parties shall complete the alternative dispute "
        "resolution within 90 days after the party who made the request receives the acceptance, unless both parties sign "
        "an extension (Civil Code 5940(a)). The costs shall be borne by the parties (Civil Code 5940(c)).",
        "**Time limits and court.** If the request is served before the end of the time limit for starting an enforcement "
        "action, the time limit is tolled for the 30 days and, if the request is accepted, for the 90 days and any extension "
        "the parties sign (Civil Code 5945). When an enforcement action is started, the party who starts it files a "
        "certificate with the first pleading stating that one of these is true: alternative dispute resolution was completed "
        "in compliance with the article; another party did not accept the terms offered; or preliminary or temporary "
        "injunctive relief is necessary (Civil Code 5950(a)). A court that decides attorney's fees and costs may consider "
        "whether a party's refusal to take part before the action began was reasonable (Civil Code 5960).",
        "**When it is required.** An association or a member may not file an enforcement action in the superior court unless "
        "the parties have endeavored to submit their dispute to alternative dispute resolution under this article. This "
        "applies only to an action solely for declaratory, injunctive, or writ relief, or for that relief with a claim for "
        "money damages within the small claims limits; it does not apply to a small claims action, and, except as otherwise "
        "provided by law, not to an assessment dispute (Civil Code 5930).",
        "**The association's yearly summary says:** " + SUMMARY_SENTENCE + " (Civil Code 5965(a)).",
        "**What it costs the association.** The association charges no fee to receive or answer this request. This is the "
        "association's proposed policy, not a rule of the Act, which sets no fee for making or answering the request.",
        "**What comes next.** " + MEMBER_CLOCK,
        CHANNELS_NOTE,
        PLAIN_WORDS_NOTE,
        HELP_ON_THE_FORM,
    ),
    questions=(
        NAME,
        UNIT_ADDRESS,
        *contact_questions("How should we reach you about this request?", why="The acceptance goes back to the party who "
                                                                              "asked (Civil Code 5940(a))."),
        FormQuestion("Who is the dispute with?", QuestionKind.CHOICE, True,
                     ("The association", "Another member or members (named below)", "The association and another member"),
                     "The request is served on all other parties to the dispute (Civil Code 5935(a)).", "other-parties",
                     section="The dispute"),
        FormQuestion("Names and unit addresses of the other members", QuestionKind.PARAGRAPH, False, key="other-party-names",
                     help="Fill this in only if another member is a party."),
        FormQuestion("A brief description of the dispute", QuestionKind.PARAGRAPH, True, key="dispute",
                     authority="Civil Code 5935(a)(1)"),
        one_box("Request for alternative dispute resolution", "adr-request",
                "I request alternative dispute resolution (mediation, arbitration, conciliation, or another nonjudicial "
                "procedure with a neutral person) of this dispute", required=True, authority="Civil Code 5935(a)(2)"),
        FormQuestion("Which kind do you propose?", QuestionKind.CHOICE, False, ADR_KINDS,
                     "Binding or nonbinding, with the voluntary consent of the parties (Civil Code 5925(a)).", "adr-kind"),
        FormQuestion("The date you sent or delivered this request", QuestionKind.DATE, True, key="date-sent",
                     help="Thirty days run from receipt or service (Civil Code 5935(a)(3), (c))."),
        one_box("An urgent request", "urgent", "I believe I need a court order right away (a preliminary or temporary order)",
                help="The association sends an urgent request to its counsel at once.", authority="Civil Code 5950(a)(3)"),
    ),
    signature="Signature of the party serving",
    code="RV",
)

REQUIRED = (
    Required("A brief description of the dispute between the parties", ("dispute",), "CIV 5935(a)(1)"),
    Required("A request for alternative dispute resolution", ("adr-request", PREAMBLE), "CIV 5935(a)(2)"),
    Required("A notice that the party receiving the Request for Resolution is required to respond within 30 days of receipt or "
             "the request will be deemed rejected", (PREAMBLE,), "CIV 5935(a)(3)"),
    Required("If the party on whom the request is served is the member, a copy of this article", (PREAMBLE,),
             "CIV 5935(a)(4)"),
    Required("The request is served on all other parties to the dispute", ("other-parties", "other-party-names"),
             "CIV 5935(a)"),
    Required("Service by personal delivery, first-class mail, express mail, facsimile transmission, or other means reasonably "
             "calculated to give actual notice", ("date-sent", PREAMBLE), "CIV 5935(b)"),
    Required("The party served has 30 days following service to accept or reject; a failure to accept is a rejection",
             (PREAMBLE,), "CIV 5935(c)"),
    Required("The form of alternative dispute resolution may be binding or nonbinding, with the voluntary consent of the "
             "parties", ("adr-kind", PREAMBLE), "CIV 5925(a)"),
    Required("Completion within 90 days after the acceptance is received, unless extended by written stipulation",
             (PREAMBLE,), "CIV 5940(a)"),
    Required("The costs of alternative dispute resolution are borne by the parties", (PREAMBLE,), "CIV 5940(c); CIV 5955(b)"),
    Required("A time limit for starting an enforcement action is tolled while the request is pending", (PREAMBLE,),
             "CIV 5945"),
    Required("The certificate filed with the first pleading when an action is started", (PREAMBLE, "urgent"), "CIV 5950"),
    Required("The annual summary's sentence, in the statute's words", (PREAMBLE,), "CIV 5965(a)"),
    Required("A signed paper served on the other party", (SIGNATURE,), "CIV 5935(a)"),
    Required("An email address is asked for only if the member picks email", ("contact-method", "email"),
             "CIV 4041(b)(2)(A)"),
    Required("A request in other words is still a request, and where to get help", (PREAMBLE,), "standard 5"),
    # Not carried yet: the response and the association's own letter are other stages and directions of the template.
    Required("The response of the party served: accept or reject, with the date (the response)", authority="CIV 5935(c)",
             deferred="the response (stage 2) and the association's letter to a member need a stage and a direction on the "
                      "template"),
)

CLOCKS = (
    Clock("acknowledge", "receipt", 1, DayKind.BUSINESS, SetBy.PROPOSED_POLICY, "", "nothing in the law"),
    Clock("read", "receipt", 10, DayKind.CALENDAR, SetBy.PROPOSED_POLICY, "CIV 5935(c)",
          "the board has less than 20 days to decide; an urgent request is read the same day"),
    Clock("respond", "receipt or service, whichever is earlier", 30, DayKind.CALENDAR, SetBy.STATUTE, "CIV 5935(a)(3), (c)",
          "the request is deemed rejected by the party; the requester may file an action with the certificate that another "
          "party did not accept (CIV 5950(a)(2)); a court deciding fees may consider whether the refusal was reasonable "
          "(CIV 5960)"),
    Clock("decide", "receipt", 25, DayKind.CALENDAR, SetBy.PROPOSED_POLICY, "CIV 5935(c)",
          "day 30 passes in silence and the request is deemed rejected, unreasonably, if the board never met"),
    Clock("answer", "receipt", 28, DayKind.CALENDAR, SetBy.PROPOSED_POLICY, "CIV 5935(c)",
          "a margin for delivery is lost"),
    Clock("complete", "the acceptance received by the party who asked", 90, DayKind.CALENDAR, SetBy.STATUTE, "CIV 5940(a)",
          "the alternative dispute resolution was not completed in compliance; what the requester may then do is for counsel"),
)

ACKNOWLEDGMENT = ("Reference {REFERENCE}. We received your Request for Resolution on {RECEIVED}. Under Civil Code 5935 the "
                  "association must accept or reject it within 30 days of receipt, which is by {DUE}, or it is deemed "
                  "rejected. {DECIDER} will bring it to the board and will send you the association's written answer. If you "
                  "are the association's member and the association served you with a Request for Resolution, a copy of "
                  "Article 3 (Civil Code 5925 to 5965) is attached. If you want to add to your request, write to "
                  "{RETURN_BY_EMAIL} or {RETURN_BY_MAIL} and quote the reference.")

DEFINITION = register(FormDefinition(
    key="adr-request",
    tier=Tier.STATE,
    jurisdiction="CA",
    template=TEMPLATE,
    version="1",
    as_of=AS_OF,
    authority=("CIV 5935", "CIV 5930"),
    required_content=REQUIRED,
    recitals=("CIV 5925(a)", "CIV 5930", "CIV 5935", "CIV 5940", "CIV 5945", "CIV 5950", "CIV 5960", "CIV 5965(a)"),
    member_clock=MEMBER_CLOCK,
    association_clocks=CLOCKS,
    acknowledgment=ACKNOWLEDGMENT,
    procedure="respond",
    handler="response-clock",
    channels=(Channel.PAPER, Channel.FILLABLE_PDF, Channel.EMAIL, Channel.PAYHOA, Channel.PORTAL),
    slots=("RETURN_BY_MAIL", "RETURN_BY_EMAIL", "BOARD_CONTACT"),
))
