"""The electric vehicle charging station and EV-dedicated meter application, Civil Code 4745 and 4745.1: a State form of the
California pack.

Built from docs/form-templates/ev-charger.md. The text on disk (``data/authorities/CIV/CIV-4700-4753.md``, the 2025 session
publication, exported 2026-10-04; its history keeps the text before 2026):

- 4745(e) and 4745.1(e): approval, where required, is processed "in the same manner as an application for approval of an
  architectural modification", "shall not be willfully avoided or delayed", is in writing, and "If an application is not denied in
  writing within 60 days from the date of receipt of the application, the application shall be deemed approved, unless that delay
  is the result of a reasonable request for additional information." The time runs from receipt; the text does not say
  "complete";
- 4745(f)(1): for a station in a common area or an exclusive-use common area the association "shall approve the installation if
  the owner agrees in writing to do all of the following": (A) to (D), each its own box here; 4745.1(f)(1) has two, (A) and (B);
- 4745(f)(2), (f)(3), (f)(4) and 4745.1(f)(2): what the owner and each successive owner are responsible for, the liability
  coverage policy and its yearly certificate, and the plug exception: each its own acknowledgment;
- 4745(g): a station in a common area that is not exclusive use "only if installation in the owner's designated parking space is
  impossible or unreasonably expensive", by license agreement.

**The 2026 change.** CIV 4745(f)(1)(C) was amended by Stats. 2025, Ch. 525 (SB 770), operative 2026-01-01. Before, the owner
agreed to "provide a certificate of insurance that names the association as an additional insured under the owner's insurance
policy in the amount set forth in paragraph (3)"; now it is "Within 14 days of approval, provide a certificate of insurance as
required by paragraph (3)", and paragraph (3) states no amount. This form asks for neither an additional-insured endorsement nor
a coverage amount (docs/form-templates/ev-charger.md, 13, lead 1), and a profile whose old form does is told which words changed.

**Not asked:** the vehicle, the cost of the station, a neighbor's consent, the owner's reasons for wanting a charger.

**Deviations from the page.** (1) The agreement and acknowledgment boxes are not required on a copy (the placements that need them
are the owner's answer to ``where_placed``, read by a person; a box left unchecked is a question to the owner, not a denial,
page section 3). (2) ``{DECIDER}``, ``{NEXT_MEETING}``, and ``{DUE}`` are of one request and left to the handler. (3) The fee
(``{FEE_SCHEDULE}``) is not asked on the base form: the page carries one only where the documents set it, and a profile adds it.
"""

from __future__ import annotations

from jason.community.form_library.ca.improvement import (
    ACKNOWLEDGMENT_CLOCK,
    AS_OF,
    CHANNELS,
    HELP_PARAGRAPH,
    MEETING_NOTICE_CLOCK,
    PROCEDURE_NOTE,
    RETURN_PARAGRAPH,
    STANDARD_SLOTS,
    applicant,
    help_question,
    not_only_door,
    policy,
    statute,
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
from jason.community.forms import FormKey, FormQuestion, FormTemplate, QuestionKind, ReadAs

LAW = "Civil Code 4745(e)"


def agreement(key: str, title: str, sentence: str, authority: str, *, required: bool = False) -> FormQuestion:
    """One agreement or acknowledgment of the statute: its own box, in its own words."""
    return FormQuestion(title, QuestionKind.CHECKBOX, required=required, key=key, options=(sentence,), authority=authority)


QUESTIONS = (
    *applicant(LAW, decision="the written decision"),
    FormQuestion("What do you want to install?", QuestionKind.CHOICE, key="what_installing", section="What and where",
                 options=("A charging station", "An EV-dedicated time-of-use meter", "Both", "Not sure"),
                 authority="Civil Code 4745(a); 4745.1(a)"),
    FormQuestion("Where will it go?", QuestionKind.CHOICE, key="where_placed",
                 options=("Inside my unit", "In my deeded parking space", "In a parking space designated for my use",
                          "In my exclusive-use common area", "In a common area that is not exclusive use",
                          "A station for all members", "Not sure"),
                 authority="Civil Code 4745(a), (f), (g), (h)"),
    FormQuestion("Which space, or which part of the unit? (a space number or a short description)", required=False,
                 key="space_description", authority="identifies the location"),
    FormQuestion("Installing at your own parking space is", QuestionKind.CHOICE, required=False, key="why_not_own_space",
                 options=("Impossible", "Unreasonably expensive", "Neither", "Not sure"),
                 help="Answer this only if it will go in a common area that is not exclusive use.",
                 authority="authorized \"only if installation in the owner’s designated parking space is impossible or "
                           "unreasonably expensive\" (Civil Code 4745(g))"),
    FormQuestion("Please tell us why (a quote or a note is welcome, never required)", QuestionKind.PARAGRAPH, required=False,
                 key="why_not_own_space_detail", authority="helps the board; the statute states no proof"),
    FormQuestion("Describe what you will install (make and model, how many charge points, the wiring route)",
                 QuestionKind.PARAGRAPH, required=False, key="station_description", section="The station or the meter",
                 help="Needed for a station.",
                 authority="the standards the owner agrees to comply with (Civil Code 4745(c), (d))"),
    FormQuestion("I am attaching", QuestionKind.CHECKBOX, required=False, key="plans_attached",
                 options=("A sketch of where it goes", "The product sheet", "The wiring or conduit route"),
                 help="Your association's checklist says which it needs. Nothing here is a reason the 60 days do not run.",
                 authority="applying Civil Code 4745(c); the documents' checklist"),
    FormQuestion("Where will the electricity come from?", QuestionKind.CHOICE, required=False, key="power_source",
                 options=("My unit's panel", "My own meter", "A common-area meter", "A new EV-dedicated meter", "Not sure"),
                 authority="who pays for the electricity (Civil Code 4745(f)(1)(D), (f)(2)(C))"),
    FormQuestion("Which electric utility will install the meter?", required=False, key="utility_name",
                 help="Needed for a meter.", authority="Civil Code 4745.1(f)(1)(B)"),
    FormQuestion("The licensed contractor's name, if you know it now", required=False, key="contractor_name", reads=ReadAs.NAME,
                 authority="due before the work starts, as a condition of the approval (Civil Code 4745(f)(1)(B))"),
    FormQuestion("The contractor's licence number, if you know it now", required=False, key="contractor_license",
                 authority="the same (Civil Code 4745(f)(1)(B))"),
    agreement("agree_standards", "Agreement 1 of 4: the association's standards",
              "I agree to comply with the association's architectural standards for the installation of the charging station.",
              "Civil Code 4745(f)(1)(A)"),
    agreement("agree_licensed_contractor", "Agreement 2 of 4: a licensed contractor",
              "I agree to engage a licensed contractor to install the charging station.", "Civil Code 4745(f)(1)(B)"),
    agreement("agree_certificate_14_days", "Agreement 3 of 4: the certificate of insurance",
              "I agree that, within 14 days of approval, I will give the association a certificate of insurance as required by "
              "paragraph (3) of Civil Code 4745(f).", "Civil Code 4745(f)(1)(C), (f)(3)"),
    agreement("agree_pay_costs", "Agreement 4 of 4: the costs",
              "I agree to pay for both the costs associated with the installation of, and the electricity usage associated with, the "
              "charging station.", "Civil Code 4745(f)(1)(D)"),
    FormQuestion("This is only an existing standard (NEMA) alternating-current power plug", QuestionKind.CHOICE, required=False,
                 key="plug_only", options=("Yes", "No"),
                 help="A homeowner liability policy is not required for it.", authority="Civil Code 4745(f)(4)"),
    agreement("ack_damage_costs", "What you are responsible for: damage",
              "I understand that I, and each later owner of the station, are responsible for costs for damage to the station, the "
              "common area, an exclusive-use common area, or separate interests resulting from its installation, maintenance, "
              "repair, removal, or replacement.", "Civil Code 4745(f)(2)(A): the statute's own responsibility, not an extra condition"),
    agreement("ack_maintenance_restoration", "What you are responsible for: maintenance and restoration",
              "I understand that I, and each later owner, are responsible for the maintenance, repair, and replacement of the station "
              "until it is removed and for restoring the common area afterwards.", "Civil Code 4745(f)(2)(B)"),
    agreement("ack_electricity", "What you are responsible for: the electricity",
              "I understand that I, and each later owner, are responsible for the cost of the electricity.",
              "Civil Code 4745(f)(2)(C)"),
    agreement("ack_disclose_buyers", "What you are responsible for: telling a buyer",
              "I understand that I must tell a buyer that there is a charging station and what the owner's responsibilities under "
              "this section are.", "Civil Code 4745(f)(2)(D): the owner's duty, not the association's"),
    agreement("meter_agree_standards", "Meter agreement 1 of 2: the association's standards",
              "I agree to comply with the association's architectural standards for the installation of the meter.",
              "Civil Code 4745.1(f)(1)(A)"),
    agreement("meter_agree_utility_contractor", "Meter agreement 2 of 2: the utility and a contractor",
              "I agree to engage the relevant electric utility to install the meter and, if necessary, a licensed contractor to "
              "install wiring or conduit to connect it to a charging station.", "Civil Code 4745.1(f)(1)(B)"),
    agreement("meter_ack_damage", "For a meter, what you are responsible for: damage",
              "I understand that I, and each later owner of the meter, are responsible for costs for damage to the meter, the "
              "common area, an exclusive-use common area, or separate interests.", "Civil Code 4745.1(f)(2)(A)"),
    agreement("meter_ack_maintenance", "For a meter, what you are responsible for: maintenance and restoration",
              "I understand that I, and each later owner, are responsible for the maintenance, repair, and replacement of the meter "
              "until it is removed and for restoring the common area afterwards.", "Civil Code 4745.1(f)(2)(B)"),
    agreement("meter_ack_disclose", "For a meter, what you are responsible for: telling a buyer",
              "I understand that I must tell a buyer that there is an EV-dedicated meter and what the owner's responsibilities are.",
              "Civil Code 4745.1(f)(2)(C)"),
    *work_dates("an approval's start time is a proposed policy (improvement-lifetime)", required=False),
    help_question(),
)

PREAMBLE_PARAGRAPHS = (
    "This form is for an electric vehicle charging station, an EV-dedicated time-of-use meter, or both, where the governing "
    "documents require approval first (Civil Code 4745 and 4745.1). The association's copy of those sections is not an official "
    "restatement of them.",
    "**We got it.** We will tell you in writing that we have your application within {ACK_DAYS} business days of the day we "
    "receive it (a target the board proposed, not a law).",
    "**The sixty days.** The Civil Code says: \"If an application is not denied in writing within 60 days from the date of receipt of "
    "the application, the application shall be deemed approved, unless that delay is the result of a reasonable request for "
    "additional information.\" (Civil Code 4745(e); the same words are in 4745.1(e) for a meter.) We count from the day we "
    "**receive** your application. The approval or the denial will be in writing.",
    "**If we need more information.** If we ask you for more information, we will do it in writing, say exactly what we need and why, "
    "and keep a copy. The law lets the delay that comes from a reasonable request count against the 60 days; it does not say how "
    "much. We aim to decide inside 60 days of the day we received your application either way.",
    "**Who decides.** The board decides, in the same way it decides any request to change a unit: at a board meeting, on an agenda "
    "item.",
    "**What the law says we must approve.** If your station is to go in a common area or an exclusive-use common area, the "
    "association \"shall approve the installation if the owner agrees in writing to do all of the following\": the four things "
    "listed on this form, each with its own box. If you check them all and sign, you have given the written agreement the statute "
    "asks for. You may agree in other words, too. For a meter there are two (Civil Code 4745.1(f)(1)).",
    "**What the law says you are responsible for.** You, and each later owner of the station, are responsible for the costs and the "
    "duties listed on this form (Civil Code 4745(f)(2)), and you must keep a liability coverage policy at all times and give us the "
    "certificate within 14 days of approval and every year after (4745(f)(3)). A buyer must be told that the station is there. "
    "These are the law's, not ours.",
    "**What we may and may not require.** We may impose \"reasonable restrictions\": for a station, restrictions \"that do not "
    "significantly increase the cost of the station or significantly decrease its efficiency or specified performance\" (Civil Code "
    "4745(b)(2)); for a meter, restrictions \"based upon space, aesthetics, structural integrity, and equal access to these services "
    "for all homeowners\", and we must attempt to find a reasonable way to accommodate the request, unless we would need to incur an "
    "expense (4745.1(b)(2)). The station must meet the health and safety standards and the permits the law requires (4745(c)); you "
    "are responsible for the permit.",
    "**If your station goes in a common area that is not your exclusive-use area.** The law lets us authorize that \"only if "
    "installation in the owner’s designated parking space is impossible or unreasonably expensive\" (Civil Code 4745(g)), and then "
    "we sign a license agreement with you for the space. Tell us on the form why your own space will not do.",
    "**If we deny it.** The denial is in writing and says why. You may ask the board to reconsider at an open meeting (there is a "
    "form for it, or use your own words); the board answers within {MAX_DAYS_RECONSIDERATION} days of your request "
    "({PROCEDURE_CITATION}). A denial does not end your rights under the section.",
    not_only_door("what you want to install, where, and that you agree to the four things"),
    HELP_PARAGRAPH,
    RETURN_PARAGRAPH,
)

TEMPLATE = FormTemplate(
    key=FormKey.EV_CHARGER,
    title="Application for an Electric Vehicle Charging Station or EV Meter",
    authority="Civil Code 4745 and 4745.1: an application to install an electric vehicle charging station or an EV-dedicated meter.",
    description=("Use this form to ask {ASSOCIATION} to approve an electric vehicle charging station, an EV-dedicated time-of-use "
                 "meter, or both. The association must decide it in writing within 60 days of the day it receives it."),
    questions=QUESTIONS,
    preamble=PREAMBLE_PARAGRAPHS,
    attestation=("I am the owner of this unit, or authorized by the owner to send this. What I have written is true to the best of my "
                 "knowledge. Where I have checked a box above, I agree to it in writing."),
    code="EV",
)

REQUIRED = (
    Required("What is to be installed: a station, a meter, or both", ("what_installing",), "CIV 4745(a); CIV 4745.1(a)"),
    Required("Where: in the unit, in a deeded or designated space, in an exclusive-use common area, in a common area that is not "
             "exclusive use, or a station for all members", ("where_placed", "space_description"),
             "CIV 4745(a); CIV 4745(f); CIV 4745(g); CIV 4745(h)"),
    Required("If a common area that is not exclusive use: why the owner's own space will not do",
             ("why_not_own_space", "why_not_own_space_detail"), "CIV 4745(g)"),
    Required("The station or meter described, so the standards can be applied",
             ("station_description", "plans_attached", "power_source", "utility_name"), "CIV 4745(c); CIV 4745.1(c)"),
    Required("Agreement 1: comply with the association's architectural standards for the installation", ("agree_standards",),
             "CIV 4745(f)(1)(A)"),
    Required("Agreement 2: engage a licensed contractor", ("agree_licensed_contractor", "contractor_name", "contractor_license"),
             "CIV 4745(f)(1)(B)"),
    Required("Agreement 3: within 14 days of approval, provide a certificate of insurance as required by paragraph (3)",
             ("agree_certificate_14_days",), "CIV 4745(f)(1)(C); CIV 4745(f)(3)"),
    Required("Agreement 4: pay for the costs of the installation and the electricity usage", ("agree_pay_costs",), "CIV 4745(f)(1)(D)"),
    Required("The owner's responsibilities: (A) damage costs; (B) maintenance, repair, replacement, and restoration; (C) the cost of "
             "electricity; (D) disclosure to prospective buyers",
             ("ack_damage_costs", "ack_maintenance_restoration", "ack_electricity", "ack_disclose_buyers"), "CIV 4745(f)(2)"),
    Required("The liability coverage policy kept at all times, the certificate yearly, and that an existing standard plug needs no "
             "homeowner policy", ("plug_only", PREAMBLE), "CIV 4745(f)(3); CIV 4745(f)(4)"),
    Required("Meter agreement 1: comply with the association's architectural standards for the meter", ("meter_agree_standards",),
             "CIV 4745.1(f)(1)(A)"),
    Required("Meter agreement 2: engage the relevant electric utility, and if necessary a licensed contractor for wiring or conduit",
             ("meter_agree_utility_contractor",), "CIV 4745.1(f)(1)(B)"),
    Required("The meter owner's responsibilities: (A) damage costs; (B) maintenance and restoration; (C) disclosure to buyers",
             ("meter_ack_damage", "meter_ack_maintenance", "meter_ack_disclose"), "CIV 4745.1(f)(2)"),
    Required("The 60-day rule: a decision in writing, deemed approved if not denied in writing, the exception for a reasonable "
             "request for additional information", (PREAMBLE,), "CIV 4745(e); CIV 4745.1(e)"),
    Required("The reasonable-restriction standard, so the owner sees what the association may and may not require", (PREAMBLE,),
             "CIV 4745(b); CIV 4745.1(b)"),
    Required("The license agreement, where the space is in a common area that is not exclusive use", ("why_not_own_space", PREAMBLE),
             "CIV 4745(g)"),
    Required("Start and finish dates, the signature and date, and help", ("start_date", "finish_date", SIGNATURE, ATTESTATION,
                                                                          "help_needed"), "the documents; the standard"),
    Required("The owner, the unit, and who is sending it", ("unit", "owner_name", "submitted_by", "rep_authorization"),
             "CIV 4745(e); CIV 4041(a)(3)"),
)

CLOCKS = (
    statute("decision-station", "the date of receipt of the application", 60, "CIV 4745(e)",
            "deemed approved, unless the delay is the result of a reasonable request for additional information"),
    statute("decision-meter", "the date of receipt of the application", 60, "CIV 4745.1(e)",
            "deemed approved, unless the delay is the result of a reasonable request for additional information"),
    policy("information-request", "the day the application is received", 15, "an addition to improvement-review-time",
           "the statute's exception may apply; a person records the request, who sent it, the day, and the day it was answered; the "
           "handler still aims to decide inside 60 days of receipt (a reading)"),
    ACKNOWLEDGMENT_CLOCK,
    statute("certificate-of-insurance", "the day of approval", 14, "CIV 4745(f)(1)(C); CIV 4745(f)(3)",
            "a finding for the manager; the statute states no remedy, counsel reads it"),
    statute("certificate-yearly", "the anniversary of the approval", 365, "CIV 4745(f)(3)",
            "a finding for the manager; a recurring duty (duty-schedule)"),
    policy("license-agreement", "the approval", 30, "proposed: for a common area that is not exclusive use (CIV 4745(g))",
           "the approval's conditions are not met; the work does not start"),
    policy("reconsideration-response", "the day the request for reconsideration is received", 45, "improvement-reconsideration; "
           "CIV 4765(a)(1) requires the documents to state the maximum", "as the reconsideration request"),
    MEETING_NOTICE_CLOCK,
)

ACKNOWLEDGMENT = (
    "We received your application to install {WHAT_INSTALLING} at {UNIT_ADDRESS} on **{RECEIVED}**. Your reference is "
    "**{REFERENCE}**.\n\n"
    "The Civil Code says an application not denied in writing within 60 days from the day it is received is deemed approved, unless "
    "the delay is the result of a reasonable request for additional information. We received it on {RECEIVED}, so the sixtieth day is "
    "**{DUE}**. {DECIDER} decides it, at an open meeting of the board; the next meeting that can be noticed in time is "
    "{NEXT_MEETING}. We will tell you in writing.\n\n"
    "[If more information is needed] To decide, we need: {ITEMS_AND_WHY}. Please send it by {ASK_BY}. We are asking because "
    "{REASON}.\n\n"
    "If the board denies it, the letter will say why and how to ask the board to reconsider.\n\n"
    "This says only that we have your request and when. It is not an approval and not a denial."
)

SLOTS = (*STANDARD_SLOTS, "PROCEDURE_CITATION", "MAX_DAYS_RECONSIDERATION", "ACK_DAYS")

NOTES = (
    PROCEDURE_NOTE,
    "CIV 4745(f)(1)(C) changed on 2026-01-01 (SB 770): the certificate is 'as required by paragraph (3)'; no additional-insured "
    "endorsement and no coverage amount is asked, and a profile whose older form asks for either is told which words changed.",
    "The 60 days run from the date of receipt, not from a complete application; a request for additional information is a person's "
    "record and the form never pauses the clock on its own.",
    "A fee, where the documents set one and the profile says it may be charged, is added by a profile; counsel reads it.",
)

DEFINITION = register(FormDefinition(
    key="ev-charger",
    tier=Tier.STATE,
    jurisdiction="CA",
    template=TEMPLATE,
    version="1",
    as_of=AS_OF,
    authority=("CIV 4745", "CIV 4745.1"),
    required_content=REQUIRED,
    recitals=("CIV 4745(e)", "CIV 4745(f)(1)", "CIV 4745(f)(1)(A)", "CIV 4745(f)(1)(B)", "CIV 4745(f)(1)(C)", "CIV 4745(f)(1)(D)",
              "CIV 4745(f)(2)", "CIV 4745(f)(3)", "CIV 4745(f)(4)", "CIV 4745(b)(2)", "CIV 4745(g)", "CIV 4745.1(e)",
              "CIV 4745.1(f)(1)", "CIV 4745.1(f)(1)(A)", "CIV 4745.1(f)(1)(B)", "CIV 4745.1(f)(2)", "CIV 4745.1(b)(2)"),
    member_clock=("We tell you in writing that we have your application. An application not denied in writing within 60 days from "
                  "the day we receive it is deemed approved, unless the delay is the result of a reasonable request for additional "
                  "information. If it is denied, the board answers a request to reconsider within {MAX_DAYS_RECONSIDERATION} days "
                  "({PROCEDURE_CITATION})."),
    association_clocks=CLOCKS,
    acknowledgment=ACKNOWLEDGMENT,
    procedure="respond",
    handler="response-clock",
    channels=CHANNELS,
    slots=SLOTS,
    notes=NOTES,
))
