"""What the five forms for a change to a unit and the protected uses share (docs/form-templates/architectural-application.md and
its siblings): the applicant's questions, the questions about a rebuild after a disaster, the paragraphs every copy carries, and
the clocks the Act sets for a rebuild.

These are the library's words, not an association's: a profile gives each form its slots and its adjustments, and this module
names no association. The five forms are the architectural application, the request for reconsideration, the electric
vehicle charging station, the solar energy system, and the protected use (``architectural``, ``reconsideration``,
``ev_charger``, ``solar``, ``protected_use``).

**The procedure.** Each design page names a dedicated procedure, ``improvement-request``, that does not exist in
``jason.community.procedures`` yet. Until it does, each definition names the ``respond`` procedure and the ``response-clock``
handler, which answer a request on its clock, and says so in its ``notes``.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date

from jason.community.form_library.tiers import Channel, Clock, DayKind, SetBy
from jason.community.forms import FormQuestion, QuestionKind, ReadAs

AS_OF = date(2026, 10, 4)                   # the shelf's export day (data/authorities/manifest.json), the day the recitals are read

CHANNELS = (Channel.PAPER, Channel.FILLABLE_PDF, Channel.EMAIL, Channel.PAYHOA, Channel.PORTAL)

# The slots every one of these forms prints (the standard ones a profile gives for any form).
STANDARD_SLOTS = ("ASSOCIATION", "RETURN_BY_MAIL", "RETURN_BY_EMAIL", "BOARD_CONTACT")

PROCEDURE_NOTE = ("The design page's own procedure, `improvement-request`, does not exist in procedures.py yet; this definition "
                  "names `respond` (answering a request on its clock) until it does, and the handler `response-clock`.")

YES_NO_UNSURE = ("Yes", "No", "Not sure")
DELIVERY = ("By mail to the unit", "By mail to another address", "By email")

# The insurance sentence the association's own summary carries (Civil Code 5300(b)(9)), recited; no coverage advice.
INSURANCE_SENTENCE = "Association members should consult with their individual insurance broker or agent for appropriate additional coverage."


def unit_question(law: str, section: str = "About you") -> FormQuestion:
    return FormQuestion("The address of your unit", key="unit", prefill="UNIT_ADDRESS", reads=ReadAs.ADDRESS, section=section,
                        authority=f"the separate interest it is for ({law})")


def owner_question(law: str) -> FormQuestion:
    return FormQuestion("Owner's name (each owner of record)", key="owner_name", reads=ReadAs.NAME,
                        authority=f"the written decision goes to the owner ({law})")


def submitted_by(other: str = "A contractor, with the owner's signature") -> FormQuestion:
    """Who is sending it; ``other`` is the fourth option (a contractor, an installer), left out when empty."""
    return FormQuestion("Who is sending this?", QuestionKind.CHOICE, key="submitted_by",
                        options=tuple(o for o in ("The owner", "A co-owner", "Someone the owner authorized in writing", other) if o),
                        authority="proof of authority; no clock turns on it")


def representative_question() -> FormQuestion:
    return FormQuestion("Check this if you are not the owner", QuestionKind.CHECKBOX, required=False, key="rep_authorization",
                        options=("I am attaching the owner's written authorization",),
                        authority="a representative acts for the owner (Civil Code 4041(a)(3))")


def phone_question() -> FormQuestion:
    return FormQuestion("A phone number, if you want us to call", QuestionKind.PHONE, required=False, key="contact_phone",
                        authority="convenience only; never required")


def delivery_questions(law: str, decision: str = "the decision") -> tuple[FormQuestion, ...]:
    """How the written answer is sent, and the email address only when email is chosen (Civil Code 4041(b)(2)(A))."""
    return (FormQuestion(f"How should we send you {decision}?", QuestionKind.CHOICE, key="decision_delivery", options=DELIVERY,
                         authority=f"it is in writing ({law}); an email address only if you choose email (Civil Code 4041(b)(2)(A))"),
            FormQuestion("Your email address", QuestionKind.EMAIL, required=False, key="contact_email",
                         help="Only if you chose email.", authority="delivery by email (Civil Code 4041(b)(2)(A))"))


def applicant(law: str, *, decision: str = "the decision", other: str = "A contractor, with the owner's signature",
              section: str = "About you") -> tuple[FormQuestion, ...]:
    """The questions most of these forms ask first: the unit, the owner, who is sending it, a phone, how to answer."""
    return (unit_question(law, section), owner_question(law), submitted_by(other), representative_question(), phone_question(),
            *delivery_questions(law, decision))


def help_question() -> FormQuestion:
    return FormQuestion("Help with this form", QuestionKind.CHECKBOX, required=False, key="help_needed",
                        options=("I need this form in another format, in larger print, in another language, or help filling it in",),
                        authority="help is on the form")


def work_dates(why: str = "an approval's start and finish times are a proposed policy (improvement-lifetime)",
               required: bool = False) -> tuple[FormQuestion, ...]:
    return (FormQuestion("When do you expect to start?", QuestionKind.DATE, required=required, key="start_date", authority=why),
            FormQuestion("When do you expect to finish?", QuestionKind.DATE, required=required, key="finish_date", authority=why))


# A rebuild after a disaster: the facts Civil Code 4752(c) turns on. Optional on every form: the clocks of 4766 run for any
# application the member says is a rebuild, and no rebuild fact is required to start them (architectural-application.md, 4).
REBUILD_SECTION = "Rebuilding after a disaster"
REBUILD_QUESTIONS = (
    FormQuestion("Who declared the disaster?", QuestionKind.CHOICE, required=False, key="disaster_declared_by",
                 options=("The federal government", "The Governor", "A local government", "Not sure"),
                 authority="Civil Code 4752(c)(1)(A) to (C)"),
    FormQuestion("Interior living area before the disaster, in square feet", required=False, key="rebuild_old_sqft",
                 authority="Civil Code 4752(c)(3)(B)"),
    FormQuestion("Interior living area as rebuilt, in square feet", required=False, key="rebuild_new_sqft",
                 authority="Civil Code 4752(c)(3)(B), 110 percent"),
    FormQuestion("Height before and as rebuilt", required=False, key="rebuild_height", authority="Civil Code 4752(c)(3)(D)"),
    FormQuestion("The footprint", QuestionKind.CHOICE, required=False, key="rebuild_footprint",
                 options=("The same place and size", "The setbacks are at least four feet from the side and rear lot lines",
                          "Neither, or not sure"), authority="Civil Code 4752(c)(3)(C)(i), (ii)"),
    FormQuestion("The building permit", QuestionKind.CHOICE, required=False, key="rebuild_permit",
                 options=("Deemed approved", "Applied for", "Not yet applied"), authority="Civil Code 4752(c)(3)(A)(ii)"),
)
REBUILD_FIELDS = tuple(q.key for q in REBUILD_QUESTIONS)


def rebuild_questions(heading: bool = True) -> tuple[FormQuestion, ...]:
    """The six rebuild questions, the first under its section heading unless the form's own question opens the section."""
    first, *rest = REBUILD_QUESTIONS
    return (replace(first, section=REBUILD_SECTION) if heading else first, *rest)


# The rebuild's own paragraph: the statute's numbers (Civil Code 4766(b), (c), (e), (f)), the same for every association.
REBUILD_PANEL = (
    "**If you are rebuilding after a declared disaster.** Within **30 calendar days** of the day we receive your application we tell "
    "you in writing whether it is complete or incomplete. If it is incomplete, the same letter lists the incomplete items and says how "
    "to make it complete, and you may resubmit it. If we do not tell you in time, your application is treated as complete (Civil "
    "Code 4766(b)(3)). Once it is complete we have **45 calendar days** to approve it or to send you, in writing, a full set of "
    "comments with a comprehensive request for revisions and a list of what is not compliant and how to fix it (4766(c), (d)). If we "
    "find the application incomplete or not compliant you may appeal, and we give you a final written determination within **60 "
    "calendar days** of your written appeal (4766(e)). Once we approve it, we may not subject you to any appeals or additional "
    "hearings, except for not complying with what was approved (4766(f)). This is the law's rule for a rebuild; your reading of it is "
    "yours, and a lawyer can help you with it."
)


def not_only_door(what: str) -> str:
    return (f"**Not the only door.** You do not have to use this form. A letter or an email that says {what} is a request, and our "
            "time starts the day we get it.")


HELP_PARAGRAPH = ("**Help.** Ask {BOARD_CONTACT} for this form in another format, in large print, or in another language, or for help "
                  "filling it in. A request for a reasonable accommodation is welcome with it or on its own; it has its own form.")

RETURN_PARAGRAPH = "Return this form to {ASSOCIATION}: by mail to {RETURN_BY_MAIL}, or by email to {RETURN_BY_EMAIL}."

INSURANCE_PARAGRAPH = (f"**Approval is not the whole story.** An approval says the change was allowed under the association's procedure. "
                       f"It does not say the change is safe, meets the building code, is insured, or is worth what it costs. The "
                       f"association's insurance summary says: \"{INSURANCE_SENTENCE}\" (Civil Code 5300(b)(9)).")


# -- the clocks the Act sets for a rebuild, and the ones every form meets -----------------------------------------------

def statute(name: str, counted_from: str, number: int, section: str, if_passes: str = "", kind: DayKind = DayKind.CALENDAR) -> Clock:
    return Clock(name, counted_from, number, kind, SetBy.STATUTE, section, if_passes)


def policy(name: str, counted_from: str, number: int, section: str, if_passes: str = "", kind: DayKind = DayKind.CALENDAR) -> Clock:
    """A clock for the board to adopt: the law and the documents are silent, so it is a proposed policy (labelled as one)."""
    return Clock(name, counted_from, number, kind, SetBy.PROPOSED_POLICY, section, if_passes)


ACKNOWLEDGMENT_CLOCK = policy("acknowledgment", "the day received", 3, "improvement-review-time",
                              "a finding for the manager; no legal effect", DayKind.BUSINESS)
MEETING_NOTICE_CLOCK = statute("meeting-notice", "the meeting (given at least this many days before it)", 4, "CIV 4920(a)",
                               "the board may not discuss or act on an item not on the agenda, except as 4930(b) to (e) allow (4930(a))")
REBUILD_CLOCKS = (
    statute("rebuild-completeness", "the day the application is received", 30, "CIV 4766(b)(1)", "deemed complete (4766(b)(3))"),
    statute("rebuild-resubmission", "the day the resubmission is received", 30, "CIV 4766(b)(2)(C)(ii)", "deemed complete (4766(b)(3))"),
    statute("rebuild-review", "the day the application is complete (determined or deemed)", 45, "CIV 4766(c)",
            "no deemed approval is stated; a court shall award reasonable attorney's fees to the applicant who prevails (4766(g)); counsel"),
    statute("rebuild-appeal", "the day the written appeal is received", 60, "CIV 4766(e)(2)",
            "no deemed result is stated; fees under 4766(g); counsel"),
)

__all__ = ["ACKNOWLEDGMENT_CLOCK", "AS_OF", "CHANNELS", "DELIVERY", "HELP_PARAGRAPH", "INSURANCE_PARAGRAPH", "INSURANCE_SENTENCE",
           "MEETING_NOTICE_CLOCK", "PROCEDURE_NOTE", "REBUILD_CLOCKS", "REBUILD_FIELDS", "REBUILD_PANEL", "REBUILD_QUESTIONS",
           "REBUILD_SECTION", "RETURN_PARAGRAPH", "STANDARD_SLOTS", "YES_NO_UNSURE", "applicant", "delivery_questions",
           "help_question", "not_only_door", "owner_question", "phone_question", "policy", "rebuild_questions",
           "representative_question", "statute", "submitted_by", "unit_question", "work_dates"]
