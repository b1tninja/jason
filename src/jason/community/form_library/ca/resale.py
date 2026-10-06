"""The request for the documents for the sale of a unit, Civil Code 4525 to 4530: a State form of the California pack.

Built from docs/form-templates/resale-documents.md. Code ``RT``. Two documents are designed there; this module is the
first, the **request** an owner (or the owner's authorized agent) makes. The second is the **billing disclosure** the
association gives back, whose layout Civil Code 4528 prescribes. It is not a form a member fills, so it is the
association's output, built by the handler (a later step); this module holds what that output needs and the library can
check: the 22 document rows in the statute's order (``DOCUMENTS``), the title and the two fixed sentences word for word
(``BILLING_TITLE``, ``BILLING_NO_COST``, ``BILLING_NOT_ALL``, ``BILLING_ASTERISK``).

**The 10-point type rule (4528: "in at least 10-point type").** ``FormStyle`` carries a ``typed_size`` for answers typed on
screen and writing-line spacing for paper, and no smallest size for a whole document, so the rule is **a rendering
requirement**, recorded here as ``BILLING_MIN_POINT_SIZE`` and as a deferred required item: every run of text of the
billing disclosure is at least 10 points in every medium, and the test of that output reads every run.

**Version notes.** (``VERSION_NOTES`` holds the same words for a program.) **1** (2026-10-05, the law as of that day,
including the 2025 amendments of 4525 and 4528, operative 2026-01-01): the first version; no earlier form existed, so no
question was kept or removed.

**Deviations from the design page.** (1) ``FormQuestion.required`` is a plain flag, so a question the page makes required
only in one case (``authorization`` and ``authorization-signature`` for an authorized person, ``email`` for electronic
delivery, ``mailing-address`` for mail, ``cancel-reference`` for a cancellation) is not required, and its help line says
when it is needed; the handler reads the rule (the page's ``required_if``). (2) The billing disclosure is not built here
(see above); its rows B1, B2, B3, B5, B6, B8, B9, B10, and B11 are deferred required items, and B4 and B7 are carried by
the questions that gather them. (3) The page's proposed procedure key is ``resale-documents``; the form names ``respond``,
which exists. (4) ``{FEE_SCHEDULE}`` is a slot: the association's actual-cost fee for each document is a fact the law
makes the form state (4528's "Fee for Document" column; 4530(b)(1)), so a community that has not given a fee schedule is
not offered this form, and ``jason form-library`` names the slot.
"""

from __future__ import annotations

from jason.community.form_library.ca.common import (
    AS_OF,
    CHANNELS_NOTE,
    HELP_ON_THE_FORM,
    PLAIN_WORDS_NOTE,
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
from jason.community.forms import FormKey, FormQuestion, FormTemplate, QuestionKind, ReadAs

VERSION_NOTES = {"1": "the first version: no earlier form existed"}

# CIV 4528: the rows of the billing disclosure, each with the Civil Code section the statute gives it, in the order it
# states them. The request's ``documents`` and ``seller-provides`` questions offer exactly these names, and no other.
DOCUMENTS: tuple[tuple[str, str], ...] = (
    ("Articles of Incorporation or statement that not incorporated", "Section 4525(a)(1)"),
    ("CC&Rs", "Section 4525(a)(1)"),
    ("Bylaws", "Section 4525(a)(1)"),
    ("Operating Rules", "Section 4525(a)(1)"),
    ("Age restrictions, if any", "Section 4525(a)(2)"),
    ("Rental restrictions, if any", "Section 4525(a)(9)"),
    ("Annual budget report or summary, including reserve study", "Sections 5300 and 4525(a)(3)"),
    ("Assessment and reserve funding disclosure summary", "Sections 5300 and 4525(a)(4)"),
    ("Financial statement review", "Sections 5305 and 4525(a)(3)"),
    ("Assessment enforcement policy", "Sections 5310 and 4525(a)(4)"),
    ("Insurance summary", "Sections 5300 and 4525(a)(3)"),
    ("Regular assessment", "Section 4525(a)(4)"),
    ("Special assessment", "Section 4525(a)(4)"),
    ("Emergency assessment", "Section 4525(a)(4)"),
    ("Other unpaid obligations of seller", "Sections 5675 and 4525(a)(4)"),
    ("Approved changes to assessments", "Sections 5300 and 4525(a)(4), (8)"),
    ("Settlement notice regarding common area defects", "Sections 4525(a)(6), (7), and 6100"),
    ("Preliminary list of defects", "Sections 4525(a)(6), 6000, and 6100"),
    ("Notice(s) of violation", "Sections 5855 and 4525(a)(5)"),
    ("Required statement of fees", "Section 4525"),
    ("Minutes of regular board meetings conducted over the previous 12 months, if requested", "Section 4525(a)(10)"),
    ("Copy of the report issued pursuant to the most recent inspection of exterior elevated elements",
     "Sections 4525(a)(11) and 5551"),
)

BILLING_MIN_POINT_SIZE = 10
BILLING_TITLE = "CHARGES FOR DOCUMENTS PROVIDED AS REQUIRED BY SECTION 4525*"
BILLING_NO_COST = ("The seller may, in accordance with Section 4530 of the Civil Code, provide to the prospective purchaser, at "
                   "no cost, current copies of any documents specified by Section 4525 that are in the possession of the seller.")
BILLING_NOT_ALL = ("A seller may request to purchase some or all of these documents, but shall not be required to purchase ALL "
                   "of the documents listed on this form.")
BILLING_ASTERISK = ("The information provided by this form may not include all fees that may be imposed before the close of "
                    "escrow. Additional fees that are not related to the requirements of Section 4525 shall be charged "
                    "separately.")

NAMES = tuple(name for name, _ in DOCUMENTS)

MEMBER_CLOCK = ("We will send you a written estimate of the fees for the documents you ask for, on the form set by Civil Code "
                "4528, before we start the work. We will give the owner, or the person the owner authorizes, the documents "
                "you ask for within 10 days of the day the request was mailed or delivered (Civil Code 4530(a)(1)). We may "
                "not hold the documents back for any reason or condition except the fee (Civil Code 4530(a)(3)). The seller "
                "is billed the association's actual cost for getting, preparing, copying, and sending the documents; there "
                "is no extra fee for receiving them electronically (Civil Code 4530(b)(1)). Any other charge for the "
                "transfer is limited by Civil Code 4575 and is billed separately (Civil Code 4530(b)(4)). You may ask for "
                "some of the documents and not all (Civil Code 4530(d)). You may cancel in writing: if no work has been "
                "done there is no fee and any fee paid is refunded; if work was done, you pay for what was done (Civil Code "
                "4530(b)(3)). If you disagree with a fee, ask {BOARD_CONTACT} in writing; you may also ask to meet and "
                "confer (Civil Code 5900 to 5920).")

TEMPLATE = FormTemplate(
    key=FormKey.RESALE_DOCUMENTS,
    title="Request for the Documents for the Sale of a Unit",
    authority="Civil Code 4525 to 4530: the documents an owner gives a prospective purchaser, and the association's estimate "
              "and billing form.",
    description=("Use this form to ask the association for the documents an owner must give a prospective purchaser of a unit "
                 "(Civil Code 4525), or to cancel a request you made. Ask early: the association has 10 days from the day "
                 "your request is mailed or delivered."),
    preamble=(
        "**What the owner gives the buyer.** The owner of a separate interest shall give a prospective purchaser the "
        "documents listed in Civil Code 4525(a), as soon as practicable before the transfer of title or the signing of a real "
        "property sales contract. The owner gives, at no cost, current copies of any of these documents the owner already has "
        "(Civil Code 4530(b)(6)).",
        "**The request and the time.** Upon written request, the association shall, within 10 days of the mailing or delivery "
        "of the request, give the owner of the unit, or any other recipient the owner authorizes, a copy of all the requested "
        "documents specified in Civil Code 4525 (Civil Code 4530(a)(1)). The association's plain-words reading: the 10 days "
        "are counted as calendar days from the mailing or delivery date you write below. Documents the association keeps in "
        "electronic form may be received electronically (Civil Code 4530(a)(2)). Delivery of the documents shall not be "
        "withheld for any reason, or subject to any condition, except payment of the fee (Civil Code 4530(a)(3)).",
        "**The estimate.** Upon receipt of a written request, the association shall give you a written or electronic "
        "estimate of the fees, on the form described in Civil Code 4528, before it processes the request (Civil Code "
        "4530(b)(2)). You may ask for some or all of the documents on that form; you are not required to buy all of them "
        "(Civil Code 4530(d)).",
        "**What it costs.** The association may collect a reasonable fee from the seller based on its actual cost for getting, "
        "preparing, copying, and delivering the documents. No additional fee may be charged for electronic delivery instead "
        "of paper (Civil Code 4530(b)(1)). The association's fees for each document are on its fee schedule: "
        "{FEE_SCHEDULE}. The fee for each document is itemized, and billed separately from all other fees, fines, or "
        "assessments of the sale (Civil Code 4530(b)(4), (7)). The seller pays the association (Civil Code 4530(b)(8)). "
        "Any other charge for the transfer is limited to the association's actual costs to change its records and the amount "
        "of Civil Code 4530 (Civil Code 4575).",
        "**Only what Civil Code 4525 names.** Documents the law does not require the seller to give a buyer are not part of "
        "this request, and may not be bundled with it (Civil Code 4530(b)(5)). To ask for other records, use the form to "
        "inspect or copy association records.",
        "**Cancelling.** A cancellation fee is not collected if the request was canceled in writing by the party that placed "
        "it and no work had been done, or the request was canceled in writing and any work done was paid for. If you cancel "
        "in writing before any work is done, the association refunds every fee collected; if you cancel after some work, it "
        "refunds the share for the work not done (Civil Code 4530(b)(3)).",
        "**What comes next.** " + MEMBER_CLOCK,
        CHANNELS_NOTE,
        PLAIN_WORDS_NOTE,
        HELP_ON_THE_FORM,
    ),
    questions=(
        FormQuestion("What do you want to do?", QuestionKind.CHOICE, True, ("Ask for the documents", "Cancel a request I made"),
                     "Civil Code 4530(a)(1); 4530(b)(3).", "action"),
        FormQuestion("Your name", key="requester-name", reads=ReadAs.NAME),
        FormQuestion("You are", QuestionKind.CHOICE, True,
                     ("The owner of the unit", "A person the owner has authorized (agent, escrow, title, attorney)"),
                     "The documents go to the owner or to a recipient the owner authorizes (Civil Code 4530(a)(1)).",
                     "requester-role"),
        FormQuestion("Owner of the property", key="owner-name", reads=ReadAs.NAME, authority="Civil Code 4528"),
        FormQuestion("Property address (the unit)", key="property-address", reads=ReadAs.ADDRESS, lines=2,
                     authority="Civil Code 4528"),
        FormQuestion("Owner's mailing address, if different from the property", required=False, key="owner-mailing",
                     reads=ReadAs.ADDRESS, lines=2, authority="Civil Code 4528"),
        one_box("The owner's authorization", "authorization",
                "The owner authorizes the person named above to receive the estimate and the documents",
                help="Check this only if you are not the owner (Civil Code 4530(a)(1)).", authority="Civil Code 4530(a)(1), (d)"),
        FormQuestion("Owner's name, typed or signed, and date", required=False, key="authorization-signature",
                     reads=ReadAs.NAME, help="Only if you are not the owner: the owner's writing authorizes you. A signed "
                     "listing or escrow instructions are accepted in its place."),
        FormQuestion("Which documents do you ask for?", QuestionKind.CHECKBOX, True, NAMES,
                     "Check any. These are the documents Civil Code 4528 lists; you need not ask for all of them.",
                     "documents", authority="Civil Code 4528; 4530(d)", section="The documents"),
        FormQuestion("Which of these do you already have as current copies and will provide directly?", QuestionKind.CHECKBOX,
                     False, NAMES, "Check any (Civil Code 4530(b)(6)).", "seller-provides"),
        FormQuestion("The date you mailed or delivered this request", QuestionKind.DATE, True, key="date-sent",
                     help="The 10 days run from it (Civil Code 4530(a)(1))."),
        FormQuestion("Send the estimate and the documents to (name)", key="recipient-name", reads=ReadAs.NAME,
                     authority="Civil Code 4530(a)(1), (b)(2)", section="Where they go"),
        FormQuestion("How should they reach that person?", QuestionKind.CHOICE, True,
                     ("By electronic transmission", "By mail", "I will collect them"),
                     "You may receive them electronically if the association keeps them in electronic form "
                     "(Civil Code 4530(a)(2)).", "delivery"),
        FormQuestion("Email address", QuestionKind.EMAIL, False, key="email", help="Fill this in only if you chose electronic "
                     "transmission.", authority="Civil Code 4041(b)(2)(A)"),
        mailing_address(help="Fill this in only if you chose mail."),
        FormQuestion("The reference printed on the request you want to cancel", required=False, key="cancel-reference",
                     help="Fill this in only if you chose to cancel a request (Civil Code 4530(b)(3))."),
    ),
    signature="Signature of the person asking",
    code="RT",
)

REQUIRED = (
    Required("A written request", (SIGNATURE, "action"), "CIV 4530(a)(1)"),
    Required("Which separate interest, and who the owner is", ("property-address", "owner-name", "owner-mailing"), "CIV 4528"),
    Required("Who is asking, and whether the owner authorized them",
             ("requester-name", "requester-role", "authorization", "authorization-signature"), "CIV 4530(a)(1)"),
    Required("The documents asked for: some or all, never forced to take all", ("documents", PREAMBLE), "CIV 4528; CIV 4530(d)"),
    Required("The documents the seller already has and will provide directly", ("seller-provides",),
             "CIV 4528; CIV 4530(b)(6)"),
    Required("The date the request was mailed or delivered", ("date-sent",), "CIV 4530(a)(1)"),
    Required("Where the estimate and the documents go; electronic is an option",
             ("recipient-name", "delivery", "email", "mailing-address"), "CIV 4530(a)(2), (b)(2)"),
    Required("Nothing outside Civil Code 4525 is asked for or bundled", (PREAMBLE, "documents"), "CIV 4530(b)(5)"),
    Required("The seller is the one billed, and pays", (PREAMBLE,), "CIV 4530(b)(1), (8)"),
    Required("Cancellation in writing", ("action", "cancel-reference"), "CIV 4530(b)(3)"),
    Required("An email address is asked for only if the member picks electronic delivery", ("delivery", "email"),
             "CIV 4530(a)(2); CIV 4041(b)(2)(A)"),
    Required("The estimate comes on the 4528 form before the request is processed, and the completed form goes with the "
             "documents", (PREAMBLE,), "CIV 4530(b)(2), (d)"),
    Required("A request in other words is still a request, and where to get help", (PREAMBLE,), "standard 5"),
    # The billing disclosure (CIV 4528) is the association's output. B4 and B7 are gathered by the questions above; the rest
    # is the document the handler builds, with its 10-point type, in every medium.
    Required("B1: the billing disclosure is in at least 10-point type, every run of text, in every output",
             authority="CIV 4528", deferred="a rendering requirement of the billing disclosure document (FormStyle has no "
                                            "smallest point size); the handler's output step"),
    Required("B2, B3, B9: the title line, the two sentences about the seller's copies and not having to buy all, and the "
             "asterisk note, word for word", authority="CIV 4528",
             deferred="the billing disclosure document carries them (BILLING_TITLE, BILLING_NO_COST, BILLING_NOT_ALL, "
                      "BILLING_ASTERISK); the handler's output step"),
    Required("B5, B6, B8, B10, B11: the provider, the date completed, the total, one fee on each row, and the two stages "
             "(estimate, completed)", authority="CIV 4528; CIV 4530(b)(4), (7), (b)(2), (d)",
             deferred="the billing disclosure document; the handler's output step"),
)

CLOCKS = (
    Clock("acknowledge", "receipt", 2, DayKind.BUSINESS, SetBy.PROPOSED_POLICY, "", "none in the law; the owner has no date"),
    Clock("estimate", "receipt of the written request", 2, DayKind.BUSINESS, SetBy.PROPOSED_POLICY, "CIV 4530(b)(2)",
          "processing may not start without it; the 10-day clock keeps running"),
    Clock("documents", "the mailing or delivery of the request", 10, DayKind.CALENDAR, SetBy.STATUTE, "CIV 4530(a)(1)",
          "the owner may bring an action; a person who willfully violates the article is liable for actual damages and a civil "
          "penalty up to $500, and the prevailing party recovers fees (CIV 4540)",
          "the statute says 10 days; calendar days is the association's reading (counsel confirms)"),
    Clock("completed-form", "delivery of the documents", 0, DayKind.CALENDAR, SetBy.STATUTE, "CIV 4530(d)",
          "as for the documents"),
    Clock("refund", "a written cancellation", 10, DayKind.BUSINESS, SetBy.PROPOSED_POLICY, "CIV 4530(b)(3)(B), (C)",
          "the association keeps money the law says it refunds"),
)

ACKNOWLEDGMENT = ("Reference {REFERENCE}. We received your request for the documents for the sale of {PROPERTY} on {RECEIVED}. "
                  "We will send the estimate of fees on the form set by Civil Code 4528 first. The documents are due within "
                  "10 days of {SENT}, by {DUE}. {DECIDER} will deliver them to the owner or to the person the owner "
                  "authorizes. If you want to cancel, write to {RETURN_BY_EMAIL} or {RETURN_BY_MAIL} and quote the reference.")

DEFINITION = register(FormDefinition(
    key="resale-documents",
    tier=Tier.STATE,
    jurisdiction="CA",
    template=TEMPLATE,
    version="1",
    as_of=AS_OF,
    authority=("CIV 4530", "CIV 4525", "CIV 4528"),
    required_content=REQUIRED,
    recitals=("CIV 4525(a)", "CIV 4528", "CIV 4530(a)", "CIV 4530(b)", "CIV 4530(d)", "CIV 4575"),
    member_clock=MEMBER_CLOCK,
    association_clocks=CLOCKS,
    acknowledgment=ACKNOWLEDGMENT,
    procedure="respond",
    handler="response-clock",
    channels=(Channel.PAPER, Channel.FILLABLE_PDF, Channel.EMAIL, Channel.PAYHOA, Channel.PORTAL),
    slots=("RETURN_BY_MAIL", "RETURN_BY_EMAIL", "BOARD_CONTACT", "FEE_SCHEDULE"),
))
