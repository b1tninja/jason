"""The request to inspect or copy association records, Civil Code 5200 to 5240: a State form of the California pack.

Built from docs/form-templates/records-request.md. Code ``RR``.

**Version notes.** (``VERSION_NOTES`` holds the same words for a program.)

- **1** (2026-10-05): the generic RECORDS template every association had, moved into the library with its questions, field
  names, and options unchanged (a return, a marker, and a PayHOA form record all know it by ``FormKey.RECORDS`` and these
  fields). Its description cited 5205(e) for the copying charge; in the text on disk 5205(e) is the individual-delivery
  provision, the charge for copying and mailing is 5205(f), and the redaction charge 5205(g) (an enhanced association
  record only). The definition cites the right subdivisions, and its recitals are keys the check reads from the shelf, so a
  subdivision that moves again fails the check instead of drifting.
- **2** (2026-10-05, the law as of that day): the full form. **Kept**, with the same field and the same options: ``name``,
  ``unit-address``, ``records-requested`` (now the exact description of the records; the title is longer, the field is the
  same), ``time-period-the-records-cover`` (now not required, because ``period`` places each record in a clock),
  ``inspect-or-receive-copies`` (options ``Inspect`` and ``Copies``, and ``Inspect, then copies`` added),
  ``how-should-copies-be-delivered`` (options ``Email``, ``Mail``, ``Pick up in person``, and a storage-media option added;
  no longer required, because a member who only inspects takes no copies). **Added**: ``capacity``, ``member-name``,
  ``designation``, ``designation-signature`` (the written designation of a representative, 5205(b)), ``record-sets``,
  ``period``, ``inspect-times``, ``email``, ``mailing-address``, ``cost-ceiling``, ``explanation`` (5215(d)). **Removed**: no
  question. The old form had no email question, so none was required; the new ``email`` is for electronic delivery only and
  is never required. The signature line reads "Signature of the person asking" because a representative may ask. The marker
  code ``RR`` is set. Required items it closes: the representative's designation (5205(b)), the cost estimate (5205(f), (g)),
  the timeframes (5210(b)), what may be withheld and the written explanation (5215(a), (d)); the member's written agreement
  to an estimate stays deferred (it is the estimate copy, a second stage of the template).

**Deviations from the design page.** (1) ``FormQuestion.required`` is a plain flag, so a question the page makes required
only in one case (``member-name`` for a representative, ``email`` for electronic delivery) is not required, and its help
line says when it is needed; the handler reads the rule (the page's ``required_if``). (2) ``period-from`` and ``period-to``
are not asked: the kept ``time-period-the-records-cover`` takes the dates in words. (3) The estimate copy (stage 2,
``agree-copying`` and ``agree-redaction``) is not built; it needs a ``stage`` on the template. (4) ``{RECORDS_CONTACT}``,
``{BUSINESS_OFFICE}``, ``{FEE_SCHEDULE}``, ``{FISCAL_YEAR_START}``, and ``{BUSINESS_DAY_DEFINITION}`` are not slots of this
version: the form states the law's rule for the place, the cost, and the timeframes without them, so the form is offered
by every community that gives its name, return address, and board contact. (5) The page's proposed procedure key is
``records-request``; the form names ``respond``, which exists.

The timeframes come from 5210(b), as the text on disk states them: 10 business days for records of the current fiscal year,
30 calendar days for the two before, and 15 calendar days after approval for a decision-making committee's minutes.
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
from jason.community.forms import FormKey, FormQuestion, FormTemplate, QuestionKind, ReadAs

VERSION_NOTES = {
    "1": "the generic form moved into the library unchanged; its description cites 5205(f) and (g), not 5205(e)",
    "2": "the full form: kept name, unit-address, records-requested, time-period-the-records-cover, inspect-or-receive-copies, "
         "how-should-copies-be-delivered; added capacity, member-name, designation, designation-signature, record-sets, period, "
         "inspect-times, email, mailing-address, cost-ceiling, explanation; removed none; code RR; the member's agreement to "
         "an estimate deferred",
}

# 5200(a) and (b), (c) in plain words: the sets a member may ask for. Each is an AssociationRecord of the profile's.
RECORD_SETS = (
    "Financial documents the Act requires us to give members (Civil Code 5300, 5565, 5810)",
    "Interim financial statements (balance sheet, income and expense statement, budget comparison, general ledger)",
    "Executed contracts",
    "Written board approval of vendor or contractor proposals or invoices",
    "State and federal tax returns",
    "Reserve account balances and records of payments from reserve accounts",
    "Agendas and minutes of meetings of the members, the board, and its committees",
    "Check registers",
    "The governing documents",
    "An accounting under Civil Code 5520(b)",
    "Enhanced association records (invoices, receipts, canceled checks, purchase orders, bank and credit card statements, "
    "statements for services, reimbursement requests)",
    "Association election materials (ballots, voter list, proxies, candidate registration list, tally sheet)",
    "Inspector's reports under Civil Code 5551",
    "The membership list (a separate form asks the purpose the law requires)",
    "Other records (describe them below)",
)

PERIODS = (
    "This fiscal year",
    "Last fiscal year",
    "The fiscal year before last",
    "Minutes of member or board meetings, any date",
    "Minutes of a committee with decisionmaking authority",
    "Inspector's reports",
)

_DELIVERY = ("Email", "Mail", "Pick up in person", "On a USB drive or disc")

MEMBER_CLOCK = ("We will make records of this fiscal year available within 10 business days after we receive your request, "
                "and records of the two years before within 30 calendar days (Civil Code 5210(b)). Minutes, committee minutes, "
                "the membership list, and the documents named in Civil Code 4525 to 4530, 5300, 5565, and 5810 have the times "
                "the law sets for them. Before we copy or send anything, we will tell you the cost and ask you to agree to it "
                "in writing; if you want to see the records instead, there is no copy cost. We may hold back or black out "
                "some information the law lets us protect; if you ask, we will tell you in writing the legal reason. The "
                "association decides what is within your request; if you disagree, write to {BOARD_CONTACT} and ask the board "
                "to reconsider. You may also ask to meet and confer (Civil Code 5900 to 5920), and you may go to court, "
                "including small claims court if the amount is within its limit (Civil Code 5235). If we do not act in time, "
                "you may bring an action, and a court that finds we unreasonably withheld access shall award you your "
                "reasonable costs and attorney's fees and may assess a civil penalty of up to $500 for each separate written "
                "request.")

TEMPLATE = FormTemplate(
    key=FormKey.RECORDS,
    title="Request to Inspect Association Records",
    authority="Civil Code 5205: a member's written request to inspect or copy association records.",
    description=("Use this form to ask to inspect or receive copies of association records. The association may "
                 "charge the direct and actual cost of copying and mailing (Civil Code 5205(f)) and, for an enhanced "
                 "association record, a limited charge for the time spent redacting it (Civil Code 5205(g))."),
    preamble=(
        "**The right.** The association shall make association records available for the time periods and within the "
        "timeframes of Civil Code 5210, for inspection and copying by a member of the association or the member's designated "
        "representative (Civil Code 5205(a)). A member may designate another person to inspect and copy the specified records "
        "on the member's behalf; the member shall make this designation in writing (Civil Code 5205(b)). You do not need to "
        "say why you want the records.",
        "**Where.** Records are inspected and copied in the association's business office within the development. If the "
        "association has no business office there, they are made available at a place you and the association agree on "
        "(Civil Code 5205(c), (d)). If you cannot agree on a place, or you write to ask for copies of specifically identified "
        "records, the association may satisfy the request by delivering copies to you by individual delivery within the same "
        "timeframes (Civil Code 5205(e)).",
        "**What it costs.** If you only inspect, there is no copy cost. The association may bill the direct and actual cost "
        "of copying and mailing; it will tell you the amount, and you agree to pay it, before anything is copied or sent "
        "(Civil Code 5205(f)). For an enhanced association record it may also bill up to $10 an hour, and not more than $200 "
        "for a written request, for the time actually and reasonably spent redacting it; it will tell you the estimate, and "
        "you agree to pay it, before it retrieves the documents (Civil Code 5205(g)).",
        "**Electronic copies.** You may ask to receive specifically identified records by electronic transmission or on "
        "machine-readable storage media, as long as the records can be sent in a redacted format that does not allow them to "
        "be altered. The charge is limited to the direct cost of producing the copy in that format (Civil Code 5205(h)). "
        + CHANNELS_NOTE,
        "**When you will hear from us.** " + MEMBER_CLOCK,
        "**What may be held back.** The association may withhold or redact information if its release is reasonably likely "
        "to lead to identity theft or to fraud in connection with the association; if the information is privileged under "
        "law; if its release is reasonably likely to compromise the privacy of an individual member; or if it is information "
        "of the kinds listed in Civil Code 5215(a)(5) (a la carte services to individual members, other members' discipline, "
        "collection, and payment plans, personal identification numbers, executive session minutes, personnel records, and "
        "interior architectural plans). It may not withhold or redact what it pays an employee, vendor, or contractor "
        "(Civil Code 5215(b)). If you ask, and the association denies or redacts records, it shall give you a written "
        "explanation specifying the legal basis (Civil Code 5215(d)).",
        "**What you may do with what you see.** The records, and any information from them, may not be sold, used for a "
        "commercial purpose, or used for any other purpose not reasonably related to your interest as a member "
        "(Civil Code 5230(a)).",
        PLAIN_WORDS_NOTE,
        HELP_ON_THE_FORM,
    ),
    questions=(
        NAME,
        UNIT_ADDRESS,
        FormQuestion("You are asking as", QuestionKind.CHOICE, True,
                     ("A member (owner) of the association", "A person the member has designated in writing"),
                     "Civil Code 5205(a), (b).", "capacity"),
        FormQuestion("Name of the member you ask for", required=False, key="member-name", reads=ReadAs.NAME,
                     help="Fill this in only if you are asking for a member."),
        one_box("Designation of a representative", "designation",
                "The member designates the person named above to inspect and copy the records described below on the "
                "member's behalf", help="Check this only if you are asking for a member. The member shall make the "
                "designation in writing (Civil Code 5205(b)).", authority="Civil Code 5205(b)"),
        FormQuestion("Member's signature (typed or written) and date", required=False, key="designation-signature",
                     reads=ReadAs.NAME, help="Only if you are asking for a member: the member signs the designation. A power "
                     "of attorney attached in place of this line is a writing, and is accepted."),
        FormQuestion("Which records do you want?", QuestionKind.CHECKBOX, True, RECORD_SETS,
                     "Check any. The sets are those of Civil Code 5200(a).", "record-sets", section="The records"),
        FormQuestion("Describe the records as exactly as you can (what, which dates, which vendor or meeting)",
                     QuestionKind.PARAGRAPH, True, key="records-requested", authority="Civil Code 5205(e)"),
        FormQuestion("What time does it cover?", QuestionKind.CHECKBOX, True, PERIODS, "Check any.", "period",
                     authority="Civil Code 5210(a), (b)"),
        FormQuestion("Time period the records cover", required=False, key="time-period-the-records-cover",
                     help="The dates, if you know them, for example January to June of this year."),
        FormQuestion("What do you want to do?", QuestionKind.CHOICE, True, ("Inspect", "Copies", "Inspect, then copies"),
                     "Civil Code 5205(a), (c), (d), (e).", "inspect-or-receive-copies", section="What you want"),
        FormQuestion("Days and times that suit you to inspect", QuestionKind.PARAGRAPH, False, key="inspect-times",
                     help="Where there is no business office, the place and time are agreed (Civil Code 5205(d))."),
        FormQuestion("If you want copies, how should they reach you?", QuestionKind.CHOICE, False, _DELIVERY,
                     "Email is electronic transmission; the storage media is a USB drive or disc (Civil Code 5205(h)).",
                     "how-should-copies-be-delivered"),
        FormQuestion("Email address for the electronic copies", QuestionKind.EMAIL, False, key="email",
                     help="Fill this in only if you chose email.", authority="Civil Code 4041(b)(2)(A)"),
        mailing_address(help="Fill this in only if you chose mail or storage media.", title="Mailing address for the copies"),
        FormQuestion("Do not copy or send anything that costs more than this without asking me first", required=False,
                     key="cost-ceiling", help="An amount, if you want to set one (Civil Code 5205(f))."),
        one_box("Written reason for anything held back", "explanation",
                "If you keep back or black out anything, send me the legal reason in writing",
                authority="Civil Code 5215(d)"),
    ),
    signature="Signature of the person asking",
    code="RR",
)

REQUIRED = (
    Required("The request is in writing, from a member or the member's designated representative", (SIGNATURE, "capacity"),
             "CIV 5205(a), (b), (e)"),
    Required("The records requested, specifically identified", ("record-sets", "records-requested"), "CIV 5205(a), (e)"),
    Required("The time periods the records cover", ("period", "time-period-the-records-cover"), "CIV 5210(a), (b)"),
    Required("Inspection, copies, or both", ("inspect-or-receive-copies", "inspect-times"), "CIV 5205(a), (c), (d), (e)"),
    Required("A representative's designation is made by the member in writing",
             ("capacity", "member-name", "designation", "designation-signature"), "CIV 5205(b)"),
    Required("The member is told the cost of copying and mailing, and agrees to it, before copying",
             (PREAMBLE, "cost-ceiling"), "CIV 5205(f)"),
    Required("For an enhanced association record, the estimated redaction cost is told and agreed before retrieval, at most "
             "$10 an hour and $200 a request", (PREAMBLE,), "CIV 5205(g)"),
    Required("The option of electronic transmission or machine-readable storage media", ("how-should-copies-be-delivered",),
             "CIV 5205(h)"),
    Required("An email address is asked for only if the member asks for delivery by email",
             ("how-should-copies-be-delivered", "email"), "CIV 4041(b)(2)(A)"),
    Required("The timeframes the association works to", (PREAMBLE,), "CIV 5210(b)"),
    Required("What may be withheld, and the right to a written explanation on request", (PREAMBLE, "explanation"),
             "CIV 5215(a), (d)"),
    Required("Where inspection happens", (PREAMBLE, "inspect-times"), "CIV 5205(c), (d)"),
    Required("The limit on what the records may be used for", (PREAMBLE,), "CIV 5230(a)"),
    Required("The member's remedy if the association does not act", (PREAMBLE,), "CIV 5235(a), (b)"),
    Required("A request in other words is still a request, and where to get help", (PREAMBLE,), "standard 5"),
    # Not carried yet: the estimate copy is a second stage of the template (docs/form-templates/records-request.md, section 11).
    Required("The member's written agreement to the estimate, before copying (the estimate copy)", authority="CIV 5205(f), (g)",
             deferred="the estimate copy (agree-copying, agree-redaction) needs a stage on the template"),
)

CLOCKS = (
    Clock("acknowledge", "receipt", 2, DayKind.BUSINESS, SetBy.PROPOSED_POLICY, "",
          "nothing in the law; the member is left without a date"),
    Clock("current-year", "receipt", 10, DayKind.BUSINESS, SetBy.STATUTE, "CIV 5210(b)(1)",
          "the member may bring an action (CIV 5235(a))"),
    Clock("prior-years", "receipt", 30, DayKind.CALENDAR, SetBy.STATUTE, "CIV 5210(b)(2)",
          "the member may bring an action (CIV 5235(a))"),
    Clock("minutes", "the meeting", 30, DayKind.CALENDAR, SetBy.STATUTE, "CIV 5210(b)(4); CIV 4950(a)",
          "the member may bring an action (CIV 5235(a))"),
    Clock("committee-minutes", "approval of the minutes", 15, DayKind.CALENDAR, SetBy.STATUTE, "CIV 5210(b)(5)",
          "the member may bring an action (CIV 5235(a))"),
    Clock("estimate", "receipt", 3, DayKind.BUSINESS, SetBy.PROPOSED_POLICY, "CIV 5205(f), (g)",
          "copying cannot start; the statutory clock is not paused by the law's text"),
    Clock("agreement", "the estimate", 15, DayKind.CALENDAR, SetBy.PROPOSED_POLICY, "CIV 5205(f), (g)",
          "the request is closed as to copies and stays open for inspection; nothing is billed"),
    Clock("explanation", "the day the records are produced, or the tenth business day after receipt, whichever is first", 0,
          DayKind.CALENDAR, SetBy.PROPOSED_POLICY, "CIV 5215(d)",
          "the member may bring an action; the association has no written basis on the record"),
)

ACKNOWLEDGMENT = ("Reference {REFERENCE}. We received your request to inspect or copy association records on {RECEIVED}. The "
                  "time the law sets for the records you asked for ends on {DUE}. {DECIDER} will tell you the cost of any "
                  "copies before anything is copied or sent, and will ask you to agree to it in writing. If you asked for the "
                  "membership list, a separate letter follows. If you want to change or add to your request, write to "
                  "{RETURN_BY_EMAIL} or {RETURN_BY_MAIL} and quote the reference.")

DEFINITION = register(FormDefinition(
    key="records-request",
    tier=Tier.STATE,
    jurisdiction="CA",
    template=TEMPLATE,
    version="2",
    as_of=AS_OF,
    authority=("CIV 5205", "CIV 5210", "CIV 5215"),
    required_content=REQUIRED,
    recitals=("CIV 5205(a)", "CIV 5205(b)", "CIV 5205(f)", "CIV 5205(g)", "CIV 5205(h)", "CIV 5210(a)", "CIV 5210(b)",
              "CIV 5215(a)", "CIV 5215(d)", "CIV 5230(a)", "CIV 5235(a)"),
    member_clock=MEMBER_CLOCK,
    association_clocks=CLOCKS,
    acknowledgment=ACKNOWLEDGMENT,
    procedure="respond",
    handler="response-clock",
    channels=(Channel.PAPER, Channel.FILLABLE_PDF, Channel.EMAIL, Channel.PAYHOA, Channel.PORTAL),
    slots=("RETURN_BY_MAIL", "RETURN_BY_EMAIL", "BOARD_CONTACT"),
))
