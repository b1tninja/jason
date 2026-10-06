"""The request to meet and confer (internal dispute resolution), Civil Code 5900 to 5920: a State form of the California pack.

Built from the generic IDR template every association had, with its questions, field names, and options unchanged (a
return, a marker, and a PayHOA form record all know it by ``FormKey.IDR`` and these fields). What the library adds is
what makes it a form the law reaches: its recitals as statute keys, the content the law requires of the request with the
question that carries each item (and the items it does not yet carry, named as deferred), its handler, and its
as-of day.

The text on disk (``data/authorities/CIV/CIV-5900-5920.md``, the 2025 session publication; none of 5900 to 5920 was amended
in 2025):

- 5910(a): a request invoking the procedure "shall be in writing";
- 5915(b)(1): the party "may request the other party to meet and confer in an effort to resolve the dispute. The request
  shall be in writing";
- 5915(b)(2): "The association shall not refuse a request to meet and confer";
- 5915(b)(4): the parties "shall meet promptly at a mutually convenient time and place, explain their positions to each
  other" and may be assisted "at their own cost";
- 5910(g) and 5915(d): no fee.

The full form (docs/form-templates/idr-request.md) closes the deferred items.
"""

from __future__ import annotations

from datetime import date

from jason.community.form_library.tiers import (
    DESCRIPTION,
    SIGNATURE,
    Channel,
    FormDefinition,
    Required,
    Tier,
    register,
)
from jason.community.forms import FormKey, FormQuestion, FormTemplate, QuestionKind, ReadAs

TEMPLATE = FormTemplate(
    key=FormKey.IDR,
    title="Request for Internal Dispute Resolution",
    authority="Civil Code 5910 and 5915: a written request to meet and confer with the board.",
    description=("Use this form to ask the association to meet and confer about a dispute. A board member will "
                 "contact you to set a meeting."),
    questions=(
        FormQuestion("Your name", key="name"),
        FormQuestion("Unit address", key="unit-address", prefill="UNIT_ADDRESS", reads=ReadAs.ADDRESS),
        FormQuestion("Email address", QuestionKind.EMAIL, key="email"),
        FormQuestion("What is the dispute about?", QuestionKind.PARAGRAPH),
        FormQuestion("What outcome are you asking for?", QuestionKind.PARAGRAPH),
        FormQuestion("Preferred meeting days and times", QuestionKind.PARAGRAPH, required=False),
    ),
)

REQUIRED = (
    Required("The request is in writing", (SIGNATURE,), "CIV 5910(a); CIV 5915(b)(1)"),
    Required("A request that the association meet and confer to resolve the dispute", (DESCRIPTION, "what-is-the-dispute-about"),
             "CIV 5915(b)(1)"),
    Required("The member's position, for the parties to explain to each other",
             ("what-is-the-dispute-about", "what-outcome-are-you-asking-for"), "CIV 5915(b)(4); CIV 5910(f)"),
    Required("A time that suits both, to meet promptly", ("preferred-meeting-days-and-times",), "CIV 5915(b)(4)"),
    Required("A way to reach the member to set the meeting", ("email",), "CIV 5915(b)(4)"),
    # Required by the law and not carried by this form yet: the full form's fixed text and questions (docs/form-templates/idr-request.md).
    Required("The association shall not refuse a request to meet and confer", authority="CIV 5915(b)(2)",
             deferred="the full request-to-meet-and-confer form recites it"),
    Required("No fee to take part", authority="CIV 5910(g); CIV 5915(d)", deferred="the full form states it"),
    Required("Either side may be assisted by an attorney or another person, at its own cost", authority="CIV 5910(f); CIV 5915(b)(4)",
             deferred="the full form asks who will assist"),
    Required("The maximum time for the association to act on the request", authority="CIV 5910(b)",
             deferred="the full form states it from the association's procedure"),
    Required("A resolution is written and signed by the parties, including the board's designee", authority="CIV 5915(b)(5), (c)",
             deferred="the full form states it"),
)

DEFINITION = register(FormDefinition(
    key="idr-request",
    tier=Tier.STATE,
    jurisdiction="CA",
    template=TEMPLATE,
    version="1",
    as_of=date(2026, 10, 5),
    authority=("CIV 5910", "CIV 5915"),
    required_content=REQUIRED,
    recitals=("CIV 5910(a)", "CIV 5915(b)"),
    procedure="respond",
    handler="response-clock",
    channels=(Channel.PAPER, Channel.FILLABLE_PDF, Channel.EMAIL, Channel.PAYHOA, Channel.GOOGLE_FORM),
))
