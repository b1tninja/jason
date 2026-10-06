"""The protected-use application or notice, Civil Code 4700 to 4753: a State form of the California pack.

Built from docs/form-templates/protected-use-application.md. **One generic template, three modes.** A single form has a "which
protected use" choice. For each use the form shows the section it rests on, what the section says the association may not do, and
the limit the section allows (the statute keys the check reads from the shelf, in ``ProtectedUse.recitals``, and the table's own
words in the form's preamble). Then it is one of three things, and says which:

- **an application**, where the governing documents may still require approval and the section limits what the association may
  refuse (4720, 4725, 4735(a) and (b), 4750, 4751, 4752 with 4766, and 4753 for something that has to be installed): the same
  maximum times, written decision, and reconsideration as the architectural application;
- **a notice**, where the section gives the owner a right that needs no approval (4705, 4706, 4710, 4715 for a listed animal,
  4735(c) and (e), 4736, and 4753 for a portable rack). **The form is the owner's way to tell the association; it is never a
  condition of the right and nothing is decided.** Its acknowledgment is dated and quotes the section; no clock runs;
- **a request for an agreement**, the one case in which the section itself leaves the decision to the association and the
  owner ("other animal as agreed to between the association and the homeowner", 4715(b)).

The sections with their own pages are 4745 and 4745.1 (``ev-charger``) and 714, 714.1, and 4746 (``solar``).

**Deviations from the page.** (1) Every question of every use is on the one form, with its use named in its help; the page's "shown
when" is the form's layout on a screen, and a paper copy shows them all. (2) A profile's ``{PROTECTED_USES_OFFERED}`` and
``{DEVELOPMENT_TYPE}`` (4751 speaks of "a planned development") are not built here: the choice lists all the uses, and a profile
that does not offer one is a later binding. (3) The per-use tokens (``{QUOTE:CIV#4705(a)}`` ...) are the statute keys of
``ProtectedUse.recitals``: the check reads them from the shelf and ``jason form-library --show`` prints their words; the preamble
carries the page's own table of what each section leaves the association. (4) ``{SILENCE_RULE}``, ``{PET_DAYS}``, ``{LIMIT_PLAIN}``,
and the per-use rule sources are left out of the blank form (optional or of one request).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from jason.community.form_library.ca.improvement import (
    ACKNOWLEDGMENT_CLOCK,
    AS_OF,
    CHANNELS,
    HELP_PARAGRAPH,
    MEETING_NOTICE_CLOCK,
    PROCEDURE_NOTE,
    REBUILD_CLOCKS,
    REBUILD_FIELDS,
    REBUILD_PANEL,
    RETURN_PARAGRAPH,
    STANDARD_SLOTS,
    YES_NO_UNSURE,
    applicant,
    help_question,
    not_only_door,
    policy,
    rebuild_questions,
    work_dates,
)
from jason.community.form_library.tiers import (
    ATTESTATION,
    PREAMBLE,
    SIGNATURE,
    FormDefinition,
    Required,
    Tier,
    register,
)
from jason.community.forms import FormKey, FormQuestion, FormTemplate, QuestionKind


class Mode(Enum):
    """What the owner's form is for the use: the section gives a right (a notice), the documents may still ask for approval (an
    application), or the section leaves the decision to the association and the owner (an agreement)."""
    NOTICE = "notice"
    APPLICATION = "application"
    AGREEMENT = "request for an agreement"


@dataclass(frozen=True)
class ProtectedUse:
    """One use the form offers: the choice the member makes, the sections it rests on, its mode, the statute keys it recites
    (the operative words, then the limit), what the section leaves no discretion over (a reading of the quoted words, labeled),
    and what the association still may do."""

    key: str
    option: str
    sections: tuple[str, ...]
    mode: Mode
    recitals: tuple[str, ...] = ()
    reading: str = ""
    may: str = ""
    also: Mode | None = None                 # a use that is a notice for one thing and an application for another

    def cites(self) -> str:
        """``Civil Code 4705`` or ``Civil Code 4735 and 4736``."""
        numbers = [s.removeprefix("CIV ") for s in self.sections]
        return "Civil Code " + " and ".join(numbers)


USES = (
    ProtectedUse("flag", "A flag of the United States", ("CIV 4705",), Mode.NOTICE, ("CIV 4705(a)", "CIV 4705(b)"),
                 "no governing document may \"limit or prohibit\" the display; the only exception is \"as required for the "
                 "protection of the public health or safety\"", "apply that exception"),
    ProtectedUse("religious-item", "A religious item on my entry door", ("CIV 4706",), Mode.NOTICE, ("CIV 4706(a)", "CIV 4706(b)"),
                 "no governing document may \"limit or prohibit\" the display, \"Except as restricted in Section 1940.5\"",
                 "require temporary removal while the association works on the door, with individual notice"),
    ProtectedUse("sign", "A sign, poster, flag, or banner (not commercial)", ("CIV 4710",), Mode.NOTICE,
                 ("CIV 4710(a)", "CIV 4710(b)", "CIV 4710(c)"),
                 "the governing documents \"may not prohibit\" them, except for public health or safety or a violation of law",
                 "prohibit signs and posters over nine square feet and flags or banners over 15 square feet; the materials in "
                 "subdivision (b)"),
    ProtectedUse("pet", "Keeping a pet", ("CIV 4715",), Mode.NOTICE, ("CIV 4715(a)", "CIV 4715(b)", "CIV 4715(c)"),
                 "no governing documents shall prohibit keeping \"at least one pet\", subject to reasonable rules",
                 "reasonable rules and regulations; an animal outside the definition is a matter of agreement"),
    ProtectedUse("pet-other", "A pet that is not a dog, cat, bird, or aquarium animal", ("CIV 4715",), Mode.AGREEMENT,
                 ("CIV 4715(a)", "CIV 4715(b)"), "none: it is the association's agreement to give", "agree or not"),
    ProtectedUse("roof", "A roof", ("CIV 4720",), Mode.APPLICATION, ("CIV 4720(a)", "CIV 4720(b)"),
                 "no association \"may require a homeowner to install or repair a roof in a manner that is in violation of Section "
                 "13132.7 of the Health and Safety Code\"; in a very high fire severity zone the documents \"shall allow for at "
                 "least one type of fire retardant roof covering material\"", "approve among the compliant materials"),
    ProtectedUse("antenna", "A television antenna or satellite dish (36 inches or less)", ("CIV 4725",), Mode.APPLICATION,
                 ("CIV 4725(a)", "CIV 4725(b)", "CIV 4725(c)"),
                 "a covenant that \"effectively prohibits or restricts\" the installation or use is void and unenforceable",
                 "\"reasonable restrictions\", including \"requirements for application and notice\"; the decision \"shall not be "
                 "willfully delayed\""),
    ProtectedUse("landscape", "Plants that use little water, or artificial turf, in place of a lawn", ("CIV 4735",), Mode.APPLICATION,
                 ("CIV 4735(a)", "CIV 4735(b)"),
                 "a provision that \"Prohibits, or includes conditions that have the effect of prohibiting\" them is void and "
                 "unenforceable", "apply landscaping rules \"to the extent the rules fully conform with subdivision (a)\""),
    ProtectedUse("drought", "My rights in a drought (watering, landscaping, pressure washing)", ("CIV 4735", "CIV 4736"), Mode.NOTICE,
                 ("CIV 4735(c)", "CIV 4735(d)", "CIV 4735(e)", "CIV 4736(a)"),
                 "an association \"shall not impose a fine or assessment\" for reducing or eliminating watering in a declared "
                 "drought emergency; the owner \"shall not be required to reverse or remove\" water-efficient measures; a document "
                 "provision that \"requires pressure washing\" during a declared drought emergency \"shall be void and "
                 "unenforceable\"", "the recycled-water exception in 4735(d)"),
    ProtectedUse("agriculture", "Growing food in my own yard", ("CIV 4750",), Mode.APPLICATION,
                 ("CIV 4750(b)", "CIV 4750(c)", "CIV 4750(d)", "CIV 4750(e)"),
                 "a provision that \"effectively prohibits or unreasonably restricts\" it is void and unenforceable",
                 "\"reasonable restrictions\"; rules clearing dead plant material and weeds"),
    ProtectedUse("adu", "An accessory dwelling unit", ("CIV 4751",), Mode.APPLICATION, ("CIV 4751(a)", "CIV 4751(b)"),
                 "a restriction that \"either effectively prohibits or unreasonably restricts\" the construction or use is void and "
                 "unenforceable", "\"reasonable restrictions\""),
    ProtectedUse("rebuild", "Rebuilding after a disaster", ("CIV 4752", "CIV 4766"), Mode.APPLICATION,
                 ("CIV 4752(a)", "CIV 4766(b)(1)", "CIV 4766(c)", "CIV 4766(e)(2)", "CIV 4766(f)(1)"),
                 "a provision is void \"to the extent that it prohibits, or includes conditions that have the effect of prohibiting, a "
                 "substantially similar reconstruction\"", "review on the 4766 clocks"),
    ProtectedUse("clothesline", "A clothesline or drying rack", ("CIV 4753",), Mode.NOTICE,
                 ("CIV 4753(c)", "CIV 4753(d)", "CIV 4753(e)"),
                 "a provision that \"effectively prohibits or unreasonably restricts\" it is void and unenforceable",
                 "\"reasonable restrictions\"; \"reasonable rules\"", also=Mode.APPLICATION),
    ProtectedUse("other", "Something else", (), Mode.APPLICATION, (), "", "the architectural application decides it"),
)

# Which of the above a notice or an application is, for the one form: a use with no sections is read by a person.
NOTICE_USES = tuple(u for u in USES if u.mode is Mode.NOTICE)
APPLICATION_USES = tuple(u for u in USES if u.mode is Mode.APPLICATION)
AGREEMENT_USES = tuple(u for u in USES if u.mode is Mode.AGREEMENT)

MODE_LINES = {
    Mode.NOTICE: ("This is a notice, not a request. You do not need our permission: you do not have to tell us, and telling us does "
                  "not make it a request. Nothing here asks for approval, no clock runs, and no one will decide it."),
    Mode.APPLICATION: ("This is an application: the governing documents may still require approval, and the section limits what the "
                       "association may refuse. The maximum time, the written decision, and reconsideration below apply."),
    Mode.AGREEMENT: ("This is a request for an agreement: the section leaves the decision to the association and you, so the "
                     "association decides whether to agree."),
}
ALSO_LINE = ("A portable rack, or a line that needs nothing built, is a notice; something you install that the documents require "
             "approval for is an application.")


def use_paragraph(use: ProtectedUse) -> str:
    """One use as the form prints it: the choice, the section, the mode, the reading of the section's words (labeled as one), and
    what the association still may do."""
    head = f"**{use.option}**" + (f" ({use.cites()})" if use.sections else "")
    parts = [MODE_LINES[use.mode] + (" " + ALSO_LINE if use.also else "")]
    if use.reading:
        parts.append(f"How the section's words read (the board applies the section as written, and this is a reading): {use.reading}.")
    if use.may:
        parts.append(f"What the association still may do: {use.may}.")
    return f"{head}. " + " ".join(parts)


NOTICE_PANEL = (
    "**If it is a notice, you do not need our permission.** The law quoted above gives you this right. You do not have to tell us, "
    "and telling us does not make it a request; nothing here asks for approval and no one will decide it. We ask so that our records "
    "are right, and so you have our written acknowledgment, dated, in case it is ever asked. A notice needs no signature; sign "
    "only an application or a request for an agreement. If something here is outside the "
    "section's words (a flag made of lights, a sign larger than the section lets us allow), we will say so in writing and say which "
    "words, and we will not treat the form as a violation."
)
APPLICATION_PANEL = (
    "**If it is an application.** We will tell you in writing that we have it within {ACK_DAYS} business days of the day we receive "
    "it (a target the board proposed, not a law). The board decides, at a board meeting, on an agenda item. Your procedure says we "
    "answer within **{MAX_DAYS_APPLICATION} days** of the day we receive your application ({PROCEDURE_CITATION}). "
    "{WHOSE_APPLICATION_CLOCK}. The decision is in writing; if it is a disapproval, it says why and how to ask the board to "
    "reconsider at an open meeting, and the board answers within **{MAX_DAYS_RECONSIDERATION} days** of your request. We may impose "
    "reasonable restrictions where the section allows them, in the section's own words above; we may not prohibit the use, or impose "
    "conditions that have that effect, where the section says so. The Civil Code does not say that silence approves this kind of "
    "change (4725(c) says only that the decision \"shall not be willfully delayed\"). If your procedure says what follows, we "
    "follow it. If it says nothing, write to {BOARD_CONTACT}; the board will put your application on its next agenda and tell you "
    "the date."
)
AGREEMENT_PANEL = (
    "**If you ask to keep another animal.** The law says a pet is \"any domesticated bird, cat, dog, aquatic animal kept within an "
    "aquarium, or other animal as agreed to between the association and the homeowner.\" For another animal the association and you "
    "agree. The board considers it; the Civil Code states no time, so any target is a proposed policy until the board adopts it. The "
    "answer is in writing. A request for an animal that helps with a disability is a different request with its own form; you do not "
    "need to use this one."
)

PREAMBLE_PARAGRAPHS = (
    "Civil Code 4700 to 4753 limit what an association or its governing documents may do about some uses of your own home. Choose "
    "the use below. For each, this form shows the section, whether it is a notice or an application, and what the section leaves the "
    "association. The association's copy of the sections is not an official restatement of them.",
    *(use_paragraph(use) for use in USES if use.sections),
    NOTICE_PANEL,
    APPLICATION_PANEL,
    REBUILD_PANEL,
    AGREEMENT_PANEL,
    not_only_door("what you are doing, or what you are telling us about"),
    HELP_PARAGRAPH,
    RETURN_PARAGRAPH,
)

SPECIFIC = "Questions for a particular use"

QUESTIONS = (
    FormQuestion("Which of these is it about?", QuestionKind.CHOICE, key="protected_use", section="The use",
                 options=tuple(u.option for u in USES), authority="Civil Code 4700 to 4753"),
    *applicant("Civil Code 4765(a)(4)", decision="our answer", section="About you"),
    FormQuestion("Tell us what you want to do, or what you are telling us about", QuestionKind.PARAGRAPH, key="use_details",
                 section="What and where", authority="the application's or the notice's text"),
    FormQuestion("Where?", QuestionKind.CHOICE, key="where_is_it",
                 options=("Inside my unit", "On the outside of my unit (a wall, roof, door, window, balcony)",
                          "In my yard or patio that is for my exclusive use", "In the common area", "Not sure"),
                 authority="Civil Code 4705(a); 4750(d); 4753(d)(3)"),
    FormQuestion("Is the yard or patio designated for your exclusive use?", QuestionKind.CHOICE, required=False, key="yard_exclusive",
                 options=YES_NO_UNSURE, help="Answer this for growing food in your yard, or a clothesline or drying rack.",
                 authority="Civil Code 4750(d); 4753(d)(3)"),
    FormQuestion("Will you build, install, or plant something that changes the property?", QuestionKind.CHOICE, required=False,
                 key="physical_change", options=YES_NO_UNSURE, help="This decides whether it is a notice or an application.",
                 authority="Civil Code 4735(a); 4750; 4753; decides application or notice"),
    FormQuestion("Where will it be displayed?", QuestionKind.CHOICE, required=False, key="display_where", section=SPECIFIC,
                 options=("Yard", "Window", "Door or door frame", "Balcony", "Outside wall", "On a staff or pole"),
                 help="For a flag, a religious item, or a sign.", authority="Civil Code 4705(b); 4710(b)"),
    FormQuestion("About how big is it?", QuestionKind.CHOICE, required=False, key="display_size",
                 options=("Nine square feet or less (a sign or poster)", "15 square feet or less (a flag or banner)", "Bigger",
                          "Not sure"), help="For a sign, poster, flag, or banner.", authority="Civil Code 4710(c)"),
    FormQuestion("What kind of animal?", QuestionKind.CHOICE, required=False, key="pet_kind",
                 options=("A dog", "A cat", "A domesticated bird", "An aquarium animal", "Another animal"),
                 help="For a pet.", authority="Civil Code 4715(b)"),
    FormQuestion("How many of that kind do you keep?", required=False, key="pet_count",
                 authority="a rule on number does not apply to a pet you already keep (Civil Code 4715(c))"),
    FormQuestion("Tell us about the other animal", QuestionKind.PARAGRAPH, required=False, key="pet_other_description",
                 help="For an animal that is not a dog, cat, bird, or aquarium animal.",
                 authority="\"other animal as agreed to between the association and the homeowner\" (Civil Code 4715(b))"),
    FormQuestion("Install, repair, or replace the roof?", QuestionKind.CHOICE, required=False, key="roof_work",
                 options=("Install", "Repair", "Replace"), help="For a roof.", authority="Civil Code 4720(a)"),
    FormQuestion("The roof covering you plan to use (product and fire rating, if known)", required=False, key="roof_material",
                 authority="Civil Code 4720(a), (b)"),
    FormQuestion("The antenna or dish is", QuestionKind.CHOICE, required=False, key="antenna_size",
                 options=("36 inches or less across or on the diagonal", "More than 36 inches", "Not sure"),
                 help="For an antenna or satellite dish.", authority="Civil Code 4725(a), (b)"),
    FormQuestion("It will go on", QuestionKind.CHOICE, required=False, key="antenna_property",
                 options=("My own unit", "Another owner's unit", "The common area"),
                 authority="Civil Code 4725(b)(2)"),
    FormQuestion("Can it be seen from a street or the common area?", QuestionKind.CHOICE, required=False, key="antenna_visible",
                 options=YES_NO_UNSURE, authority="Civil Code 4725(a)"),
    FormQuestion("What are you doing?", QuestionKind.CHOICE, required=False, key="landscape_change",
                 options=("Planting low water-using plants (as a group or in place of a lawn)",
                          "Using artificial turf or another synthetic surface that looks like grass",
                          "Complying with a water-efficient landscape ordinance or a water-use restriction", "Something else"),
                 help="For plants that use little water, or artificial turf.", authority="Civil Code 4735(a)(1) to (3)"),
    FormQuestion("What are you telling us about?", QuestionKind.CHOICE, required=False, key="drought_matter",
                 options=("I reduced or stopped watering during a declared drought emergency",
                          "I put in water-efficient landscaping during a declared drought emergency",
                          "I am not washing with a pressure sprayer during a declared drought emergency", "Something else"),
                 help="For your rights in a drought.", authority="Civil Code 4735(c), (e); 4736"),
    FormQuestion("What kind of unit?", QuestionKind.CHOICE, required=False, key="adu_kind",
                 options=("An accessory dwelling unit", "A junior accessory dwelling unit", "Not sure"),
                 help="For an accessory dwelling unit.", authority="Civil Code 4751(a)"),
    FormQuestion("Is your lot zoned for single-family residential use?", QuestionKind.CHOICE, required=False,
                 key="lot_single_family", options=YES_NO_UNSURE, authority="Civil Code 4751(a)"),
    FormQuestion("Your city or county permit", QuestionKind.CHOICE, required=False, key="adu_local_status",
                 options=("Not yet applied", "Applied", "Approved"),
                 authority="Civil Code 4751(a), (b); the standards are the local agency's"),
    FormQuestion("A rack or a line?", QuestionKind.CHOICE, required=False, key="rack_or_line",
                 options=("A portable drying rack", "A clothesline that needs a post or fixture attached", "Not sure"),
                 help="For a clothesline or drying rack.", authority="Civil Code 4753(a), (b); decides notice or application"),
    *rebuild_questions(),
    FormQuestion("I am attaching", QuestionKind.CHECKBOX, required=False, key="plans_attached", section="Plans and the work",
                 options=("A sketch or plan", "Photos of the area", "A product sheet"),
                 help="For an application. Your association's checklist says which it needs.",
                 authority="the documents' checklist; Civil Code 4765"),
    *work_dates("an approval's start and finish times are a proposed policy (improvement-lifetime)", required=False),
    help_question(),
)

TEMPLATE = FormTemplate(
    key=FormKey.PROTECTED_USE_APPLICATION,
    title="Protected Use: Notice, Application, or Request",
    authority="Civil Code 4700 to 4753: a use of your own home the law protects, told to or asked of the association.",
    description=("Use this form to tell {ASSOCIATION} about a use of your own home that the Civil Code protects, or to ask for "
                 "approval where the documents still require it. For each use the form says whether it is a notice (you do not "
                 "need permission) or an application."),
    questions=QUESTIONS,
    preamble=PREAMBLE_PARAGRAPHS,
    attestation=("I am the owner of this unit, or authorized by the owner to send this. What I have written is true to the best of my "
                 "knowledge. A notice has no attestation."),
    code="PX",
)

PER_USE = ("display_where", "display_size", "pet_kind", "pet_count", "pet_other_description", "roof_work", "roof_material",
           "antenna_size", "antenna_property", "antenna_visible", "landscape_change", "drought_matter", "adu_kind",
           "lot_single_family", "adu_local_status", "rack_or_line")

REQUIRED = (
    Required("The use, chosen from the list", ("protected_use",), "CIV 4700 to 4753"),
    Required("The section's operative words for that use", (PREAMBLE, "protected_use"), "each section of CIV 4700 to 4753"),
    Required("The limit the section allows (reasonable restrictions, reasonable rules, the size limits, the public-health-or-safety "
             "exception)", (PREAMBLE,), "CIV 4705(a); CIV 4710(a); CIV 4710(c); CIV 4715(a); CIV 4725(b); CIV 4735(b); CIV 4750(c); "
                                        "CIV 4751(b); CIV 4753(d); CIV 4753(e)"),
    Required("Which mode it is: application, notice, or request for an agreement, and that a notice is not a condition",
             ("protected_use", "physical_change", PREAMBLE), "the form's summary of each section; docs/form-templates.md"),
    Required("For a notice: nothing asks permission, no clock runs, and an acknowledgment is the only answer", (PREAMBLE,),
             "CIV 4705; CIV 4706; CIV 4710; CIV 4715; CIV 4735(c); CIV 4735(e); CIV 4736"),
    Required("For an application: the stated maximum time, the written decision with reasons, reconsideration at an open meeting",
             (PREAMBLE,), "CIV 4765(a)(1); CIV 4765(a)(4); CIV 4765(a)(5); CIV 4725(c)"),
    Required("What is to be done, where, and whether something is built", ("use_details", "where_is_it", "physical_change"),
             "CIV 4765(a)"),
    Required("Whether the area is exclusive-use", ("yard_exclusive",), "CIV 4750(d); CIV 4753(d)(3)"),
    Required("The per-use facts the section turns on", PER_USE, "each section"),
    Required("Plans, where something is installed", ("plans_attached", "start_date", "finish_date"), "the documents; CIV 4765"),
    Required("The rebuild facts, shared with the architectural application", REBUILD_FIELDS, "CIV 4752(c)(3); CIV 4766"),
    Required("The signature (for an application), help, and that a request in other words is still a request",
             (SIGNATURE, ATTESTATION, "help_needed", PREAMBLE), "the standard (docs/form-templates.md)"),
    Required("The owner, the unit, and who is sending it", ("unit", "owner_name", "submitted_by", "rep_authorization",
                                                            "decision_delivery", "contact_email"),
             "CIV 4765(a)(4); CIV 4041(a)(3)"),
)

CLOCKS = (
    ACKNOWLEDGMENT_CLOCK,
    policy("decision", "the day received (complete, where the documents define it)", 45, "improvement-review-time; CIV 4765(a)(1) "
           "requires the documents to state the maximum",
           "a finding for the board; 4765 states no deemed approval; for an antenna the decision \"shall not be willfully delayed\" "
           "(4725(c))"),
    policy("agreement-answer", "the day received", 30, "improvement-review-time (a request for an agreement, CIV 4715(b))",
           "a finding for the board"),
    policy("reconsideration-response", "the day the request for reconsideration is received", 45, "improvement-reconsideration; "
           "CIV 4765(a)(1) requires the documents to state the maximum", "as the reconsideration request"),
    *REBUILD_CLOCKS,
    MEETING_NOTICE_CLOCK,
)

ACKNOWLEDGMENT_NOTICE = (
    "We received your notice about {PROTECTED_USE_PLAIN} at {UNIT_ADDRESS} on **{RECEIVED}**. Your reference is **{REFERENCE}**.\n\n"
    "The section says: {QUOTE_OPERATIVE}. You do not need our permission, so there is nothing for us to decide, and no time is "
    "running. We have noted what you told us.\n\n"
    "{LIMIT_PLAIN}\n\n"
    "This is an acknowledgment only. It is not an approval, because none is needed."
)
ACKNOWLEDGMENT_APPLICATION = (
    "We received your request about {PROTECTED_USE_PLAIN} at {UNIT_ADDRESS} on **{RECEIVED}**. Your reference is **{REFERENCE}**.\n\n"
    "Under {PROCEDURE_CITATION}, we answer within {MAX_DAYS_APPLICATION} days of the day we received it, which is **{DUE}**. "
    "{DECIDER} decides it, at an open meeting of the board; the next meeting that can be noticed in time is {NEXT_MEETING}. We will "
    "tell you in writing what the decision is; if it is a disapproval, the letter will say why and how to ask the board to "
    "reconsider.\n\n"
    "[Rebuild only] We will tell you whether your application is complete or incomplete by **{COMPLETE_DUE}**, 30 calendar days "
    "after we received it.\n\n"
    "This says only that we have your request and when. It is not a decision."
)
# One acknowledgment for a notice, another for an application or a request for an agreement (page, section 8).
ACKNOWLEDGMENT = ("For a notice:\n\n" + ACKNOWLEDGMENT_NOTICE + "\n\nFor an application or a request for an agreement:\n\n"
                  + ACKNOWLEDGMENT_APPLICATION)

SLOTS = (*STANDARD_SLOTS, "PROCEDURE_CITATION", "MAX_DAYS_APPLICATION", "MAX_DAYS_RECONSIDERATION", "ACK_DAYS",
         "WHOSE_APPLICATION_CLOCK")

NOTES = (
    "kind: one form, three modes. A use that is a right (a notice) is the owner's way to tell the association, never a condition "
    "of the right; nothing is decided, no clock runs, and its acknowledgment (ACKNOWLEDGMENT_NOTICE) is dated and quotes the "
    "section. A use the documents may still ask approval for is an application on the architectural application's clocks. The "
    "one use the section leaves to the association and the owner (a pet that is not a dog, cat, bird, or aquarium animal) is a "
    "request for an agreement.",
    PROCEDURE_NOTE,
    "A notice that the documents appear to bar is a lead for the board and counsel (jason conflicts --leads), never a violation "
    "notice; jason sends no enforcement notice on a protected use.",
    "The page's ResponseKind.PROTECTED_USE is in responses.py; a notice opens no clock (its rule carries the note).",
)

DEFINITION = register(FormDefinition(
    key="protected-use-application",
    tier=Tier.STATE,
    jurisdiction="CA",
    template=TEMPLATE,
    version="1",
    as_of=AS_OF,
    authority=tuple(sorted({s for u in USES for s in u.sections})),
    required_content=REQUIRED,
    recitals=("CIV 4765(a)(1)", "CIV 4765(a)(4)", "CIV 4765(a)(5)", *dict.fromkeys(r for u in USES for r in u.recitals)),
    member_clock=("A notice opens no clock: we acknowledge it with a date, and nothing is decided. An application is answered in "
                  "writing within {MAX_DAYS_APPLICATION} days of the day we receive it ({PROCEDURE_CITATION}); a disapproval says why "
                  "and how to ask the board to reconsider, and the board answers within {MAX_DAYS_RECONSIDERATION} days of your "
                  "request."),
    association_clocks=CLOCKS,
    acknowledgment=ACKNOWLEDGMENT,
    procedure="respond",
    handler="response-clock",
    channels=CHANNELS,
    slots=SLOTS,
    notes=NOTES,
))
