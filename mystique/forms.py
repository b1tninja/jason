"""The association's own forms, and what it gives the form library.

The forms the law requires of every association under it (the request to meet and confer, the records request) are not
here: they are built into the form library (``jason.community.form_library.ca``), and the association gives the library
its slots (``form_slots``) and its own forms (``CUSTOM_FORMS``). ``Community.forms()`` is the resolved set: ask it, never
this module. A response is personal data; it stays in the Forms account and on local disk.
"""

from __future__ import annotations

from datetime import date

from jason.community import form_refs
from jason.community.form_library import Channel, FormDefinition, Slot, Tier
from jason.community.response_inbox import ResponseRequest
from jason.community.forms import CONTACT, AnswerCycle, EarlierElections, FormImport, SuggestedChoices, FormKey, FormQuestion, FormTemplate, ImportRule, QuestionKind, ReadAs, FormStyle, Assurance, EmailCollection, GoogleFormChannel

# The annual owner notice (Civil Code 4041(a)), with what the solicitation must say (4041(b)(2)): an email address is
# optional, and a simple way to change the preferred delivery method. The same rows make the PayHOA form's build sheet,
# the paper form in the annual packet (jason.community.form_render), and a Google Form if one is wanted. Two optional
# preferences ride along: ballot delivery (the Election Rules' paper or electronic choice) and the membership-list
# opt-out (Civil Code 5220). The answers are entered in PayHOA, the association's books (4041(b)(1)); jason stores no
# owner's address.
# The address answers are short text: one line online (PayHOA's textarea is a rich-text box, wrong for an address), two
# lines to write on paper.
OWNER_INFO = FormTemplate(
    key=FormKey.OWNER_INFO,
    title="Owner Information and Notice Delivery Preferences",
    code="NP",                                  # notice preferences: the marker on its copies, NP27E-…
    # 22 pt to write in, pale writing lines, 10 pt typing: the layout lab's results (docs/form-design.md, October 1, 2026)
    style=FormStyle(write_height=22.0, line_gray=0.6, typed_size=10.0),
    authority=("Civil Code 4041: each year, each owner's preferred and secondary delivery method, legal representative, "
               "and whether the unit is owner-occupied or rented, entered at least 30 days before the annual reports."),
    description=("The Association's annual request for each owner's notice delivery preferences and owner information "
                 "under California Civil Code §4041."),
    preamble=(
        "Each year the Association must ask every owner for (1) the owner's preferred method of receiving the "
        "Association's notices, (2) an alternate or secondary method, (3) the name and contact information of any legal "
        "representative, and (4) whether the unit is owner-occupied, rented, or vacant (Civil Code §4041(a)).",
        "**You do not have to provide an email address** to the Association (Civil Code §4041(b)(2)(A)). If you do not "
        "answer, notices will be delivered to the last mailing address you gave the Association in writing or, if none, "
        "to your unit (Civil Code §4041(c)).",
        "**You may change your preferences at any time** by submitting this form again or by writing to the Association "
        "(Civil Code §4041(b)(2)(B)).",
        "Please answer by **{RETURN_BY}**. The Association enters the answers in its records at least 30 days before it "
        "delivers the annual budget report and the annual policy statement (Civil Code §4041(b)(1)). The information is "
        "used to deliver the Association's notices and to keep its records.",
    ),
    attestation=("I certify that I am an owner of record of this unit, or am authorized to answer for the owner, and "
                 "that the information I have given is true and correct."),
    questions=(
        # Each question holds one value (October 1, 2026): a compound answer ("list each owner"; a representative's name,
        # address, and email on one line) is several fields under one heading, each read with its own hint.
        FormQuestion("Your name", key="name", section="Owner", reads=ReadAs.NAME,
                     help="The person filling in this form."),
        FormQuestion("You are answering for", QuestionKind.CHOICE, key="answering-for",
                     options=("Myself only", "All owners of this unit", "An owner, as their legal representative"),
                     help="Co-owners may each answer for themselves, or one owner may answer for all."),
        FormQuestion("Unit address", key="unit-address", prefill="UNIT_ADDRESS", reads=ReadAs.ADDRESS),
        FormQuestion("How should the Association deliver notices to you?", QuestionKind.CHECKBOX, key="delivery",
                     options=("By mail", "By email"), section="Notice delivery (Civil Code §4041(a)(1))",
                     help="Choose one or both. You do not have to provide an email address.",
                     authority="Civil Code §4041(a)(1), (b)(2)(A)"),
        # "Only if it is not your unit address" went unread; the usual answer is a box to check instead, checked on
        # the emailed copy when the owner's mail goes to the unit (October 1, 2026). The address is written in its
        # parts: the street, then City, State, ZIP (form_render.ADDRESS_ROW).
        FormQuestion("Mailing address for notices", QuestionKind.SHORT, lines=2, required=False, key="mailing-address",
                     reads=ReadAs.ADDRESS, same_as="Same as my unit address"),
        FormQuestion("Email address for notices", QuestionKind.EMAIL, required=False, key="email",
                     help="Only if you chose email. Choosing email means you agree to receive notices by email; you can "
                          "change this at any time.", authority="Civil Code §4041(a)(1)(B)"),
        FormQuestion("Second email for notices (optional)", QuestionKind.EMAIL, required=False, key="second-email",
                     section="Second delivery, optional (Civil Code §4041(a)(2))",
                     help="Another place for notices, such as an email you check or a family member's. Copies of the "
                          "annual budget report, policy statement, and collection notices go here too. For a property "
                          "manager, use the manager section.",
                     authority="Civil Code §4041(a)(2), §4040(b)"),
        FormQuestion("Second mailing address for notices (optional)", QuestionKind.SHORT, lines=2, required=False,
                     key="second-mailing-address", reads=ReadAs.ADDRESS),
        FormQuestion("Representative's name (optional)", required=False, key="representative-name", reads=ReadAs.NAME,
                     section="Legal representative, optional (Civil Code §4041(a)(3))",
                     help="Anyone with power of attorney, or another person the Association can contact if you are away "
                          "for an extended time. A representative is a contact, not a recipient of notices.",
                     authority="Civil Code §4041(a)(3)"),
        FormQuestion("Representative's email (optional)", QuestionKind.EMAIL, required=False, key="representative-email"),
        FormQuestion("Representative's phone (optional)", QuestionKind.PHONE, required=False, key="representative-phone"),
        FormQuestion("Representative's mailing address (optional)", QuestionKind.SHORT, lines=2, required=False,
                     key="representative-mailing-address", reads=ReadAs.ADDRESS),
        # The law's own question (4041(a)(4)); "Is your unit" alone didn't say it asked about occupancy (October 1, 2026).
        FormQuestion("Is your unit owner-occupied, rented out, or vacant?", QuestionKind.CHOICE, key="occupancy",
                     options=("Owner-occupied", "Rented out", "Vacant (not occupied)"),
                     section="Occupancy (Civil Code §4041(a)(4))", authority="Civil Code §4041(a)(4)"),
        # The owner's property manager (October 1, 2026): who it is, and what the owner lets the Association do with
        # the contact. Copies of notices make the manager the owner's second delivery (4041(a)(2)); "contact me through
        # them" makes the manager the legal representative (4041(a)(3)); neither keeps the manager on file only, an
        # other contact. Copies go by email, so the section asks no mailing address.
        FormQuestion("Manager or company name (optional)", required=False, key="manager-name",
                     section="Property manager, optional",
                     help="Only if someone manages your unit for you, usually when it is rented out. A manager is not "
                          "an owner and gets nothing from the Association unless you check a box below."),
        FormQuestion("Manager's email (optional)", QuestionKind.EMAIL, required=False, key="manager-email"),
        FormQuestion("Manager's phone (optional)", QuestionKind.PHONE, required=False, key="manager-phone"),
        FormQuestion("What may the Association do with your manager's contact? (optional)", QuestionKind.CHECKBOX,
                     required=False, key="manager-role",
                     options=("Send my manager copies of Association notices",
                              "Contact my manager if I can't be reached"),
                     help="Leave both unchecked to keep it on file only. Copies go to your manager's email.",
                     authority="Civil Code §4041(a)(2), (a)(3)"),
        FormQuestion("How would you like to receive election ballots? (optional)", QuestionKind.CHOICE, required=False,
                     key="ballots", options=("Paper ballot by mail", "Electronic ballot by email"),
                     section="Elections and the membership list",
                     help="Where the Association's Election Rules offer electronic voting.",
                     authority="Election Rules"),
        FormQuestion("Membership list (optional)", QuestionKind.CHOICE, required=False, key="membership-list",
                     options=("Include my name and addresses in the membership list",
                              "Opt me out of sharing my name and addresses (Civil Code §5220)"),
                     help="Members may request the membership list. If you opt out, requests to contact you go through "
                          "the Association instead; the opt-out stays in effect until you change it.",
                     authority="Civil Code §5220"),
    ),
)

# This year's owner information solicitation (4041(b)(1)): for fiscal year 2027, opened October 1, 2026. An answer
# sent since then is this year's; earlier answers are leads to confirm (jason.community.forms.AnswerCycle). Owners are
# asked to answer by October 23; the annual reports go out by December 1 (the end of the 5300/5310 window for a
# January 1 fiscal year), so the answers must be in PayHOA by November 1.
OWNER_INFO_CYCLE = AnswerCycle(year=2027, opened=date(2026, 10, 1), return_by=date(2026, 10, 23),
                               reports_mailed=date(2026, 12, 1))

# An earlier answer is the owner's written election when its email matches the one PayHOA has for that owner, it
# came after the latest deed, it is no more than two years old, and nothing newer is in PayHOA (the board,
# October 1, 2026). It sets the delivery tags; this cycle still asks the owner to confirm it.
EARLIER_ELECTIONS = EarlierElections(apply=True, max_age_days=730, require_email_match=True)

# On each emailed form, the association's suggestions where the owner has made no choice: "By email" for an owner who
# reads the association's email (signed in to PayHOA or opened its email in the last year; 87 of 105 owner records on
# October 1, 2026), and an electronic ballot unless they chose paper. The owner edits or keeps them; nothing is recorded
# until the form comes back.
SUGGESTED_CHOICES = SuggestedChoices(apply=True, active_days=365, opens_count=True, ballots=True)

# The owner information form also as a Google Form, for owners who won't sign in to PayHOA (the PayHOA form stays the
# official one: a signed-in answer is the owner's own). No sign-in, so each answer carries its Assurance
# (jason.community.assurance): an owner's personal link fills in their copy's reference, which only their email held.
# The email is typed, not verified: a Google sign-in would cost the convenience the form is for. form_id and
# responder_uri are set after `jason forms --create owner-info`; the form stays unpublished until the board decides.
GOOGLE_FORMS = {
    FormKey.OWNER_INFO: GoogleFormChannel(  # made October 1, 2026; unpublished
        form_id="1UCnK7G61HBoPC8Qhq_cOV5q_TEOM8Vv1TghcLi9Mhf0",
        responder_uri="https://docs.google.com/forms/d/e/1FAIpQLScNMEqzW8uq0Aj6RzedQKDjF0sBjmucx5mKqgj7cdFWYjBnqQ/viewform",
        email=EmailCollection.RESPONDER_INPUT),
}

# When jason has recorded an owner's PayHOA answer in full (tags written; nothing left for a person to enter), it marks
# the request complete with this comment, emailed to the owner who sent it (the board, October 1, 2026). An answer that
# still needs a person (an email or mailing address, a second delivery, a representative, a manager) stays pending.
OWNER_INFO_COMPLETED_COMMENT = ("<p>Thank you. Your notice preferences are recorded. You can change them at any time by "
                                "answering this form again.</p>")

# PayHOA accounts made to test the owner forms from an owner's side: their submissions are never an owner's answer.
# They are kept in .env (payhoa_test_membership_ids), not here: an account id is the operator's, not a community fact.
TEST_MEMBERSHIPS: dict[int, str] = {}

# A change is recorded from a return at TOKEN or above (it quotes the reference only that owner's copy carried);
# below MATCHED (from or naming the email on file) the address on file is told of it first. A lower return is a lead.
RECORD_AT = Assurance.TOKEN

_OWNER_SECTIONS = ("Owner and Property Information", "Additional Owner Information")

# The board's first Resident Registration Form (Google Forms, used September 2024 to June 2026). It asked for the
# 4041 delivery preference, a secondary address, and occupancy, plus owner and resident contacts, lease terms, and
# uploads (leases, background and credit checks) that are not read here. It did not collect a verified email, so a
# response is a lead to confirm with the owner, not the owner's 4041 election; PayHOA is where the election is kept.
RESIDENT_REGISTRATION = FormImport(
    key="resident-registration-2024",
    source="17Z695vpkP2ZkPiTvgg_BbBDGINLNQARk3u29CBN7kOE",
    form=FormKey.OWNER_INFO,
    title="Resident Registration Form (2024)",
    rules=(
        ImportRule("Property / Unit Address", "unit-address"),
        ImportRule("Mailing Address (if different)", "mailing-address"),
        *(ImportRule(title, f"{CONTACT}{slot}", section=section, role="owner")
          for section in _OWNER_SECTIONS for title, slot in (("Owner Name", "name"), ("Email", "email"), ("Phone", "phone"))),
        ImportRule("The member's preferred delivery method for receiving notices from the association, which shall "
                   "include the option of receiving notices at one or both of the following:", "delivery",
                   options=(("Mail", "By mail"), ("E-Mail", "By email"))),
        ImportRule("Alternative Mailing Address", "second-mailing-address"),
        ImportRule("Alternative Email Address", "second-email"),
        ImportRule("Is the unit owner occupied, or being leased?", "occupancy",
                   options=(("Rental", "Rented out"), ("Owner Occupied", "Owner-occupied"))),
        *(ImportRule(title, f"{CONTACT}{slot}", section="Resident Information", role="resident")
          for title, slot in (("Name", "name"), ("Email", "email"), ("Phone", "phone"))),
    ),
    note="unverified respondents; uploads and lease terms not read",
)

FORM_IMPORTS: tuple[FormImport, ...] = (RESIDENT_REGISTRATION,)

# The association's own forms, returned by ``Community.custom_forms()``. Owner information is built (Civil Code 4041); its
# handler and procedure are the owner-information cycle's. The request to meet and confer and the records request were
# here until October 5, 2026; they are the library's now (``jason.community.form_library.ca``), with the same questions,
# fields, and options, so the returns, markers, and PayHOA records made from them keep working.
CUSTOM_FORMS: tuple[FormDefinition, ...] = (
    FormDefinition(
        template=OWNER_INFO, tier=Tier.CUSTOM, key="owner-info", version="1", as_of=OWNER_INFO_CYCLE.opened,
        authority=("CIV 4041",), procedure="owner-info-cycle", handler="owner-information",
        channels=(Channel.PAPER, Channel.FILLABLE_PDF, Channel.EMAIL, Channel.PAYHOA, Channel.GOOGLE_FORM)),
)


def form_slots(community) -> tuple[Slot, ...]:
    """What this association gives the form library's ``{SLOT}``s, read from where its notices already get them: its
    name, the official address and email answers come back to, the PayHOA portal, and the board's group address. No fee
    schedule or records contact is on record, so a form that uses those slots is not offered until one is."""
    from jason.community.groups import GroupPurpose

    from .help import PORTAL_SIGN_UP
    from .templates import IDENTITY

    board = next((g.address for g in community.google_groups() if g.purpose is GroupPurpose.BOARD), "")
    return (Slot("ASSOCIATION", IDENTITY.name), Slot("RETURN_BY_MAIL", IDENTITY.official_address),
            Slot("RETURN_BY_EMAIL", IDENTITY.official_email), Slot("PORTAL", PORTAL_SIGN_UP), Slot("BOARD_CONTACT", board))

# The requests that expect answers, watched by `jason responses` (docs/responses-design.md). The owner information
# request is answered four ways: the PayHOA form, a Google Form (FORM_IMPORTS), a reply email carrying the filled form,
# and the mailed letter's return, scanned. A scan is tied to the request by the marker its copy printed: the campaign
# of the emailed copy (NP27E), of the mailed letter (NP27M), and of the PayHOA form (NP27P). Its fillable form is the
# one `jason packet owner-information --build` makes, which a scanned return is read against.
RESPONSE_REQUESTS = (
    ResponseRequest(
        key="owner-information-2027", title="Owner information request", form=OWNER_INFO, cycle=OWNER_INFO_CYCLE,
        payhoa_form=OWNER_INFO.key.value, imports=FORM_IMPORTS,
        marker_campaigns=tuple(form_refs.campaign(OWNER_INFO.code, OWNER_INFO_CYCLE.year, c)
                               for c in (form_refs.Channel.EMAIL, form_refs.Channel.MAIL, form_refs.Channel.PAYHOA)),
        blank="packets/owner-information-2027/owner-info-fillable.pdf"),
)
