"""Candidate nomination and candidate statement, Civil Code 5100 to 5145: a State form of the California pack.

The design is docs/form-templates/candidate-nomination.md. The text on the shelf (``data/authorities/CIV/CIV-5100-5145.md``,
the 2025 session publication):

- 5105(a)(3): the election rules "Specify the qualifications for candidates ... and procedures for the nomination of
  candidates"; "A nomination or election procedure shall not be deemed reasonable if it disallows any member from nominating
  themself", so the form offers a self-nomination;
- 5105(b): the association "shall disqualify a person from a nomination as a candidate for not being a member of the
  association at the time of the nomination" (and one who has served the most terms). That is the only ground the form states
  itself; every other ground is the election rules' own, each printed with its section by the profile (``Add`` rows);
- 5105(d), (e): no disqualification for fines, late charges, collection costs, or for an assessment paid under protest or
  under a payment plan, and none for want of the opportunity for internal dispute resolution. So the form asks nothing about
  money owed, a conviction (5105(c)(4) is optional and speaks of disclosure, not of asking), age, a photograph, or terms
  served: the association reads those from its own records;
- 5105(a)(1), (a)(2): equal access to association media and to the common-area meeting space, with no editing or redaction of
  what a candidate writes;
- 5103(c): within seven business days of receiving a nomination, acknowledge it to the member who submitted it and tell the
  nominee whether the nominee is a qualified candidate (if not, the basis and the Article 2 appeal);
- 5115(a): general notice of the procedure and deadline at least 30 days before any deadline for submitting a nomination.

The Act sets no nomination deadline, no form for a candidate statement, no rule on a nominee's consent, and names no one to
decide qualification outside 5103 (the page's section 6 and leads 1, 2, 4, and 6). Each is the election rules' or the board's
proposed policy, labeled so.

Deviations from the page:

- ``required_if`` does not exist on ``FormQuestion``: the nominator's, the entity appointee's, and the acceptance questions are
  ``required=False`` and their help lines say when they are needed.
- The page's ``seat`` question ("only if the election rules name seats"), the profile's qualification questions, and the
  statement limit are a community's ``Add`` rows and slots, not part of the base form; ``NOMINATION_DEADLINE`` is a slot the
  board fills for each election, so the form is not offered until it is given.
- The page names the ``election`` procedure (it exists) for this form. The handler here is ``response-clock`` with procedure
  ``respond``; the step the page adds to ``election`` (``NOTES``) is not written here.
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

CODE = "CN"                                   # candidate nomination: CN26P-... for the PayHOA form; a campaign is the election's year

MEMBER_CLOCK = (
    "You may nominate yourself, or another member, for the board. Nominations are open until {NOMINATION_DEADLINE}; the "
    "election rules set that date, and the election rules and this notice are the whole procedure. Within seven business "
    "days after we receive a nomination we will tell the member who sent it that we have it, and we will tell the nominee "
    "whether the nominee is a qualified candidate; if not, we will say why, and how to appeal. The election's inspector, an "
    "independent person who is not a director or a candidate, handles the lists and counts the votes. Every member may check "
    "the list of voters at least 30 days before ballots go out. Every member who is a member on the day ballots are sent may "
    "vote. A candidate may give a short statement; we will print it as written and will not edit it, and we may add a note "
    "that the candidate, not the association, is responsible for it. Send this form to {NOMINATION_RETURN}, or answer it "
    "online at {PORTAL}.")

ACKNOWLEDGMENT = (
    "To the member who submitted the nomination: Reference {REFERENCE}. We received a nomination of {NOMINEE} for {SEAT} on "
    "{RECEIVED}. We will tell the nominee by {DUE} whether the nominee is a qualified candidate. {DECIDER} reads each "
    "nomination against the election rules. Nominations are open until {NOMINATION_DEADLINE}. To add to or withdraw this "
    "nomination, use the same form or write to {RETURN_BY_EMAIL} or {RETURN_BY_MAIL} and quote the reference.\n\n"
    "To the nominee: Reference {REFERENCE}. {QUALIFIED_OR_NOT}. If you are a qualified candidate, your name will be on the list "
    "of candidates in the general notice we give at least 30 days before ballots are distributed, and you may give a "
    "candidate statement by {STATEMENT_DUE}. If you are not, the reason is stated above and you may ask to meet and confer "
    "under Civil Code 5900 to 5920 by {APPEAL_BY}. The inspector of elections is {INSPECTOR}.")

SLOTS = ("ASSOCIATION", "NOMINATION_DEADLINE", "NOMINATION_RETURN", "PORTAL", "INSPECTOR", "BOARD_CONTACT",
         "RETURN_BY_MAIL", "RETURN_BY_EMAIL")

TEMPLATE = FormTemplate(
    key=FormKey.CANDIDATE_NOMINATION,
    title="Candidate Nomination and Candidate Statement",
    code=CODE,
    authority=("Civil Code 5105(a)(3), 5103(c), and 5115(a): a member's nomination of a candidate for the board, or of "
               "themself, and the candidate's statement."),
    description=("Use this form to nominate yourself, or another member, as a candidate for the board of {ASSOCIATION}, and "
                 "to give a candidate statement if you wish. Nominations close on {NOMINATION_DEADLINE}."),
    preamble=(
        MEMBER_CLOCK,
        "**A member may nominate themself.** No nomination procedure is reasonable if it disallows any member from nominating "
        "themself (Civil Code 5105(a)(3)).",
        "**Who may be a candidate.** The Association must disqualify a person who is not a member of the Association at the "
        "time of the nomination (Civil Code 5105(b)); a legal entity that holds title may appoint a natural person to be the "
        "member (Civil Code 5105(b)(2)). That is the only ground this form states itself. Every other qualification is in "
        "the election rules, and the rules may not disqualify a nominee for fines, late charges, or collection costs, or for "
        "an assessment paid under protest or under a payment plan, or when the person has not had the opportunity for "
        "internal dispute resolution (Civil Code 5105(c) to (e)). This form asks nothing about money owed.",
        "**Your candidate statement.** The Association will not edit or redact it, and may state that the candidate, and not "
        "the Association, is responsible for its content. Every candidate has equal access to association media and to the "
        "common-area meeting space, at no cost, for purposes reasonably related to the election (Civil Code 5105(a)(1), "
        "(a)(2)).",
        "**The lists.** Your name and address are kept as election material on the candidate registration list, and each "
        "member may check the lists at least 30 days before ballots are distributed; an error reported to the inspector is "
        "corrected within two business days (Civil Code 5105(a)(7)). The Association gives the list of candidates in a "
        "general notice at least 30 days before ballots are distributed (Civil Code 5115(b)(4)).",
        "**Who may vote.** A ballot is denied to a member only for not being a member when ballots are distributed (Civil "
        "Code 5105(h)(1)).",
        "**The inspector of elections** is {INSPECTOR}: an independent third party who may not be a director or a candidate "
        "or related to one (Civil Code 5110(a), (b)).",
        "**A request in other words is still a request.** A letter or an email that names a nominee, sent to the person the "
        "election rules name before the deadline, is a nomination. For large print, another format, someone to read this form "
        "to you or write it down, or a reasonable accommodation, write to {BOARD_CONTACT}. You may also ask to meet and "
        "confer (Civil Code 5900 to 5920).",
        "The Association's plain-words notes above state its proposed policy and are not the statute; the words of the "
        "sections cited control. The Association's copy of the law is not an official restatement.",
    ),
    attestation=("I certify that I am the member named above, or am authorized to answer for the member, and that what I have "
                 "written is true."),
    questions=(
        FormQuestion("Who is being nominated?", QuestionKind.CHOICE, key="self",
                     options=("I am nominating myself", "I am nominating another member"),
                     authority="Civil Code 5105(a)(3), 5103(c)(3)"),
        FormQuestion("Name of the member being nominated", key="nominee-name", reads=ReadAs.NAME,
                     authority="Civil Code 5105(a)(7)"),
        FormQuestion("Unit address of the member being nominated", key="nominee-unit", reads=ReadAs.ADDRESS,
                     authority="Civil Code 5105(a)(7), (b)"),
        FormQuestion("Mailing address for election notices to the nominee", QuestionKind.SHORT, lines=2, required=False,
                     key="nominee-mailing", reads=ReadAs.ADDRESS, same_as="Same as the unit address",
                     help="Only if it is not the unit address.", authority="Civil Code 5105(a)(7), 5103(c)(2)"),
        FormQuestion("Email address of the nominee", QuestionKind.EMAIL, required=False, key="nominee-email",
                     help="Only if the nominee wants election notices by email. An email address is never required (Civil "
                          "Code 4041(b)(2)(A))."),
        FormQuestion("Confirm the nominee's membership", QuestionKind.CHECKBOX, key="member-statement",
                     options=("The nominee owns the unit named above, and was an owner on the day of this nomination",),
                     authority="Civil Code 5105(b)", help="The Association checks its records."),
        FormQuestion("If an entity or trust holds title, the natural person it has appointed to be the member",
                     required=False, key="entity-appointee", reads=ReadAs.NAME,
                     help="Only if a legal entity holds title. Attach the appointment.", authority="Civil Code 5105(b)(2)"),
        FormQuestion("Does the nominee agree to stand?", QuestionKind.CHECKBOX, required=False, key="accepts",
                     options=("The nominee accepts this nomination and agrees to stand",),
                     help="Needed when you are nominating another member. A nominee who signs this form accepts."),
        FormQuestion("Name of the member submitting this nomination", required=False, key="nominator-name",
                     reads=ReadAs.NAME, section="The member submitting the nomination",
                     help="Only if you are nominating another member. We write to this member too.",
                     authority="Civil Code 5103(c)(1)"),
        FormQuestion("Unit address of the member submitting this nomination", required=False, key="nominator-unit",
                     reads=ReadAs.ADDRESS, help="Only if you are nominating another member."),
        FormQuestion("Candidate statement (optional)", QuestionKind.PARAGRAPH, required=False, key="statement",
                     section="Candidate statement, optional",
                     help="Printed as written, without editing. Nothing here is required.", authority="Civil Code 5105(a)(1)"),
        FormQuestion("Candidate statement: the Association's note", QuestionKind.CHECKBOX, required=False,
                     key="statement-ack",
                     options=("I understand the Association will not edit or redact my statement, and may add a note that I, "
                              "and not the Association, am responsible for it",),
                     help="Needed if you wrote a statement.", authority="Civil Code 5105(a)(1)"),
    ),
)

REQUIRED = (
    Required("A member may nominate themself", ("self",), "CIV 5105(a)(3)"),
    Required("The nominee's name and address, for the candidate registration list",
             ("nominee-name", "nominee-unit", "nominee-mailing"), "CIV 5105(a)(7)"),
    Required("The nominee is a member at the time of the nomination", ("member-statement",), "CIV 5105(b)"),
    Required("A unit held by a legal entity: the natural person appointed", ("entity-appointee",), "CIV 5105(b)(2)"),
    Required("The qualifications of the election rules, and nothing more (the only ground the form states is membership; the "
             "rest are the rules', each with its section)", (PREAMBLE,), "CIV 5105(a)(3), (c), (d), (e)"),
    Required("Who submitted the nomination, so the association can acknowledge it", ("nominator-name", "nominator-unit"),
             "CIV 5103(c)(1)"),
    Required("The nominee is told whether qualified and, if not, why and how to appeal", (PREAMBLE,), "CIV 5103(c)(2)"),
    Required("The nomination period, where nominations go, and the manner", (PREAMBLE, SIGNATURE), "CIV 5115(a); CIV 5105(a)(3)"),
    Required("The candidate statement is published without editing", ("statement", "statement-ack"), "CIV 5105(a)(1)"),
    Required("Equal access for all candidates to association media and the meeting space", (PREAMBLE,),
             "CIV 5105(a)(1), (a)(2)"),
    Required("Who may vote, and that the voter list may be checked", (PREAMBLE,), "CIV 5105(h)(1); CIV 5105(a)(7)"),
    Required("The inspector's role", (PREAMBLE,), "CIV 5110(c)"),
    Required("That a request in other words is still a request, and where to get help", (PREAMBLE,)),
)

CLOCKS = (
    # 5103(c) is a condition of acclamation; the proposal applies it to every election, so the member has one clock.
    Clock("acknowledge-nomination", "receipt of a nomination", 7, DayKind.BUSINESS, SetBy.STATUTE, "CIV 5103(c)(1)",
          "the board may not seat the qualified candidates by acclamation (5103(c)); otherwise the member is left without "
          "a date", "statute where acclamation is to be available; applied to every election as proposed policy"),
    Clock("tell-nominee", "receipt of a nomination", 7, DayKind.BUSINESS, SetBy.STATUTE, "CIV 5103(c)(2)",
          "the board may not seat the qualified candidates by acclamation (5103(c))",
          "statute where acclamation is to be available; applied to every election as proposed policy"),
    Clock("nomination-notice", "the nomination deadline (the general notice is due at least this many days before it)", 30,
          DayKind.CALENDAR, SetBy.STATUTE, "CIV 5115(a)", "the deadline is not valid until noticed"),
    Clock("initial-notice", "the nomination deadline (the individual initial notice is due at least this many days before it)",
          90, DayKind.CALENDAR, SetBy.STATUTE, "CIV 5103(b)(1)", "acclamation is not available (where the association wants it)"),
    Clock("candidate-list", "the day ballots are distributed (the list of candidates is due at least this many days before it)",
          30, DayKind.CALENDAR, SetBy.STATUTE, "CIV 5115(b)(4)", "the notice lists an incomplete slate"),
    Clock("list-correction", "an error reported to the inspector", 2, DayKind.BUSINESS, SetBy.STATUTE, "CIV 5105(a)(7)",
          "the election is open to challenge"),
    Clock("statement-due", "the nomination deadline", 0, DayKind.CALENDAR, SetBy.PROPOSED_POLICY, "",
          "a late statement is still published, in the media that remain open, and the candidate is told"),
    Clock("appeal-request", "the day a disqualification notice is sent", 5, DayKind.BUSINESS, SetBy.PROPOSED_POLICY,
          "CIV 5103(c)(2)(B)", "the disqualification is not final until the opportunity of 5105(e) is given"),
)

RECITALS = ("CIV 5105(a)(3)", "CIV 5105(b)", "CIV 5105(c)", "CIV 5105(d)", "CIV 5105(e)", "CIV 5105(a)(1)", "CIV 5105(a)(2)",
            "CIV 5105(a)(7)", "CIV 5115(a)", "CIV 5103(c)", "CIV 5110(a)", "CIV 5110(b)", "CIV 5105(h)")

NOTES = (
    "The page names the election procedure for this form (it exists): add a step after 'Read each notice's requirement': receive "
    "each nomination, stamp the day, acknowledge the submitter and tell the nominee within seven business days, hand it to the "
    "inspector for the qualification reading, enter the candidate registration list, and list the qualified candidates for the "
    "5115(b)(4) notice. The handler here is response-clock with respond until that step is written.",
    "jason never decides whether a nominee is qualified, disqualifies anyone, seats anyone, edits a candidate statement, or "
    "opens a ballot (5105(a)(1), 5120).",
    "A community adds the election rules' qualification questions, and a seat question where the rules name seats, with Add rows.",
    "A nomination from the floor, or a write-in, only where the rules allow it (5105(g)); not with electronic secret ballots "
    "(5105(i)(1)(F)). The secretary or inspector writes it on this form and the clocks run from that day.",
)

DEFINITION = register(FormDefinition(
    key="candidate-nomination",
    tier=Tier.STATE,
    jurisdiction="CA",
    template=TEMPLATE,
    version="1",
    as_of=date(2026, 10, 5),
    authority=("CIV 5105", "CIV 5103", "CIV 5115", "CIV 5110"),
    required_content=REQUIRED,
    recitals=RECITALS,
    member_clock=MEMBER_CLOCK,
    association_clocks=CLOCKS,
    acknowledgment=ACKNOWLEDGMENT,
    procedure="respond",
    handler="response-clock",
    channels=(Channel.PAPER, Channel.FILLABLE_PDF, Channel.EMAIL, Channel.PAYHOA, Channel.PORTAL),
    slots=SLOTS,
    notes=NOTES,
))
