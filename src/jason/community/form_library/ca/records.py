"""The request to inspect or copy association records, Civil Code 5200 to 5240: a State form of the California pack.

Built from the generic RECORDS template every association had, with its questions, field names, and options unchanged (a
return, a marker, and a PayHOA form record all know it by ``FormKey.RECORDS`` and these fields).

**A correction to the old text.** The generic form's description said the association "may charge the direct cost of
copying and redaction (Civil Code 5205(e))". In the text on disk (``data/authorities/CIV/CIV-5200-5240.md``, the 2025
session publication) 5205(e) is the provision for delivering copies of specifically identified records by individual
delivery; the charge for copying and mailing is 5205(f) ("the direct and actual cost of copying and mailing"), and the
redaction charge is 5205(g) (not more than $10 an hour and $200 a written request, for an enhanced association record
only). This definition cites the right subdivisions, and its recitals are keys the check reads from the shelf, so a
subdivision that moves again fails the check instead of drifting. The description is the one line that differs from the
old form's.

The timeframes come from 5210(b), as the text on disk states them: 10 business days for records of the current fiscal year,
30 calendar days for the two years before, and 15 calendar days after approval for a decision-making committee's minutes.
"""

from __future__ import annotations

from datetime import date

from jason.community.form_library.tiers import (
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

_DELIVERY = ("Email", "Mail", "Pick up in person")

TEMPLATE = FormTemplate(
    key=FormKey.RECORDS,
    title="Request to Inspect Association Records",
    authority="Civil Code 5205: a member's written request to inspect or copy association records.",
    description=("Use this form to ask to inspect or receive copies of association records. The association may "
                 "charge the direct and actual cost of copying and mailing (Civil Code 5205(f)) and, for an enhanced "
                 "association record, a limited charge for the time spent redacting it (Civil Code 5205(g))."),
    questions=(
        FormQuestion("Your name", key="name"),
        FormQuestion("Unit address", key="unit-address", prefill="UNIT_ADDRESS", reads=ReadAs.ADDRESS),
        FormQuestion("Records requested", QuestionKind.PARAGRAPH),
        FormQuestion("Time period the records cover"),
        FormQuestion("Inspect or receive copies?", QuestionKind.CHOICE, options=("Inspect", "Copies")),
        FormQuestion("How should copies be delivered?", QuestionKind.CHOICE, options=_DELIVERY),
    ),
)

REQUIRED = (
    Required("The request is in writing, from a member or the member's designated representative", (SIGNATURE,),
             "CIV 5205(a), (b), (e)"),
    Required("The records requested, specifically identified", ("records-requested",), "CIV 5205(a), (e)"),
    Required("The time periods the records cover", ("time-period-the-records-cover",), "CIV 5210(a), (b)"),
    Required("Inspection, copies, or both", ("inspect-or-receive-copies",), "CIV 5205(a), (c), (d), (e)"),
    Required("The option of electronic transmission or machine-readable storage media", ("how-should-copies-be-delivered",),
             "CIV 5205(h)"),
    # Required by the law and not carried by this form yet: the full form's text and questions (docs/form-templates/records-request.md).
    Required("A representative's designation is made by the member in writing", authority="CIV 5205(b)",
             deferred="the full records form asks for it"),
    Required("The member is told the cost of copying and mailing, and agrees to it, before copying", authority="CIV 5205(f)",
             deferred="the full form's cost estimate and agreement"),
    Required("For an enhanced association record, the estimated redaction cost is told and agreed before retrieval, at most "
             "$10 an hour and $200 a request", authority="CIV 5205(g)", deferred="the full form's cost estimate and agreement"),
    Required("The timeframes the association works to", authority="CIV 5210(b)", deferred="the full form states them"),
    Required("What may be withheld, and the right to a written explanation on request", authority="CIV 5215(a), (d)",
             deferred="the full form states it and asks for the explanation"),
)

CLOCKS = (
    Clock("current-year", "receipt", 10, DayKind.BUSINESS, SetBy.STATUTE, "CIV 5210(b)(1)",
          "the member may bring an action (CIV 5235(a))"),
    Clock("prior-years", "receipt", 30, DayKind.CALENDAR, SetBy.STATUTE, "CIV 5210(b)(2)",
          "the member may bring an action (CIV 5235(a))"),
    Clock("committee-minutes", "approval of the minutes", 15, DayKind.CALENDAR, SetBy.STATUTE, "CIV 5210(b)(5)",
          "the member may bring an action (CIV 5235(a))"),
)

DEFINITION = register(FormDefinition(
    key="records-request",
    tier=Tier.STATE,
    jurisdiction="CA",
    template=TEMPLATE,
    version="1",
    as_of=date(2026, 10, 5),
    authority=("CIV 5205", "CIV 5210"),
    required_content=REQUIRED,
    recitals=("CIV 5205(a)", "CIV 5205(f)", "CIV 5205(g)", "CIV 5210(b)"),
    association_clocks=CLOCKS,
    procedure="respond",
    handler="response-clock",
    channels=(Channel.PAPER, Channel.FILLABLE_PDF, Channel.EMAIL, Channel.PAYHOA, Channel.GOOGLE_FORM),
))
