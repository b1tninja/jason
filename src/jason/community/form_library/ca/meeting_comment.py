"""Request to be heard at a board meeting, a written comment, and a request to add an item, Civil Code 4925 and 4930: a State
form of the California pack.

The design is docs/form-templates/meeting-comment-request.md. One form holds three requests, and **only the first is a right the
Act gives.** The text on the shelf (``data/authorities/CIV/CIV-4900-4955.md``):

- 4925(b): "The board shall permit any member to speak at any meeting of the association or the board, except for meetings of
  the board held in executive session. A reasonable time limit for all members ... shall be established by the board." The form
  is never a condition of speaking, and says so first;
- 4930(a): the board may not discuss or act on an item not on the posted agenda of a nonemergency meeting, but that "does not
  prohibit a member or resident who is not a director from speaking on issues not on the agenda";
- 4930(c)(2): the board or a director "may" direct staff "to place a matter of business on a future agenda". That is the only
  thing the article says about placing an item, and it is the board's choice. **The Act gives a member no right to place an item
  on the agenda**, so the form says so in plain words and prints the written-comment and item parts as courtesies, each under a
  heading that says it is not a right the Act gives;
- 4935(a) to (c): executive session, the one place a member has no right to speak; a member's own discipline and payment plan
  have their own routes;
- 4920(a), (c), (d): notice at least four days before, by general delivery, with the agenda; 4950(a): the minutes within 30
  days; 4955(a): a member's action for a violation of the article.

The form asks no signature (``signature=""``): a request to be heard asks nothing that binds the member. It asks no phone
number, no email address (never required, 4041(b)(2)(A)), no reason, and no view on the topic.

Deviations from the page:

- ``required_if`` does not exist on ``FormQuestion``: ``topic``, ``comment``, and ``item-what`` are ``required=False`` and
  their help lines say when each is needed.
- The page's ``{AGENDA_SETTER}`` and ``{PACKET_DAY}`` slots are the handler's and the board packet's, not the member's form, so
  they are not slots of this definition; ``{TIME_LIMIT}`` is: the form never invents a limit, and a profile with none says so
  in the slot's value.
- The page names the ``board-packet`` procedure (it exists) for this form. The handler here is ``response-clock`` with procedure
  ``respond``; the step the page adds to ``board-packet`` (``NOTES``) is not written here.
"""

from __future__ import annotations

from datetime import date

from jason.community.form_library.tiers import (
    PREAMBLE,
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

CODE = "HM"                                   # heard at a meeting: HM26P-... for the PayHOA form, HM26M-... for the mailed blank

MEMBER_CLOCK = (
    "**You may speak at any open board meeting, without this form.** Nothing in the law lets the board refuse a member who "
    "wants to speak at an open meeting; the board sets a reasonable time limit for everyone, which is {TIME_LIMIT}. You may "
    "speak on any topic, even one that is not on the agenda. You may not speak in an executive session, which is closed to "
    "members. The board may not discuss or act on a topic that is not on the agenda, except as the law allows; a director or "
    "the manager may answer briefly or ask the manager to report back. **Asking the board to put an item on a future agenda, "
    "and sending a written comment, are courtesies, not rights the law gives:** the law does not require the board to place "
    "an item on an agenda, to answer, or to read a written comment aloud. We will tell you in writing the day we received "
    "your request and, for an item, whether the board will consider it and when. The notice of each board meeting, with its "
    "agenda, goes out at least four days before; you may read it at {AGENDA_NOTICE_PLACE}. The minutes of an open meeting "
    "are available within 30 days. If your matter is your own discipline, payment plan, or dispute, there is another route, "
    "and {BOARD_CONTACT} will help you take it.")

ACKNOWLEDGMENT = (
    "Reference {REFERENCE}. We received your request on {RECEIVED}. {ASKED_FOR}. You may speak at the open forum of any board "
    "meeting whether or not you use this form; the board's time limit for each speaker is {TIME_LIMIT}. {DECIDER} will tell "
    "you by {DUE} whether the board will consider your item and for which meeting; this is a courtesy, and the law does not "
    "require the board to place an item on its agenda. The notice and agenda of the next meeting go out at least four days "
    "before it, at {AGENDA_NOTICE_PLACE}. To change or withdraw your request, use the same form or write to "
    "{RETURN_BY_EMAIL} or {RETURN_BY_MAIL} and quote the reference.")

SLOTS = ("ASSOCIATION", "RETURN_BY_MAIL", "RETURN_BY_EMAIL", "PORTAL", "BOARD_CONTACT", "TIME_LIMIT", "AGENDA_NOTICE_PLACE")

COURTESY_COMMENT = "Courtesy: a written comment (not a right the Act gives)"
COURTESY_ITEM = "Courtesy: ask the board to consider an item (not a right the Act gives)"

TEMPLATE = FormTemplate(
    key=FormKey.MEETING_COMMENT_REQUEST,
    title="Request to Be Heard at a Board Meeting",
    code=CODE,
    authority=("Civil Code 4925(b) and 4930: a member's right to speak at a meeting of the board (the form is a convenience, "
               "never a condition), and two courtesy requests the Act does not require the board to grant: a written comment "
               "and an item for a future agenda."),
    description=("Use this form to tell {ASSOCIATION} you would like to speak at a board meeting, to send the board a written "
                 "comment, or to ask the board to consider an item at a future meeting. You do not need this form to speak."),
    signature="",
    dated=False,
    preamble=(
        MEMBER_CLOCK,
        "**The Act gives a member no right to have an item placed on the agenda.** The board may not discuss or take action "
        "on an item at a nonemergency meeting unless the item is on the agenda in the notice, and a member or resident who "
        "is not a director may still speak on issues not on the agenda (Civil Code 4930(a)). The board or a director \"may\" "
        "direct that a matter be placed on a future agenda (Civil Code 4930(c)(2)). A request to add an item is therefore a "
        "request to the board's discretion: a courtesy.",
        "**What the Act does not give a member:** a right to speak in executive session (Civil Code 4925(b)); a right to a "
        "decision, an answer, or action on what the member says (the board may briefly respond, Civil Code 4930(b)(1)); a "
        "right to speak for any particular length (the board sets a reasonable time limit for everyone, Civil Code 4925(b)); "
        "a right to have a written comment read aloud or to use it in place of speaking; and a right to insist that the "
        "board discuss an item that is not on the agenda.",
        "**What the Act does give:** the right to attend open meetings (Civil Code 4925(a)); to speak at any meeting of the "
        "association or the board except in executive session (Civil Code 4925(b)); to speak on issues not on the agenda "
        "(Civil Code 4930(a)); to notice of the time, place, and agenda at least four days ahead (Civil Code 4920); to the "
        "minutes within 30 days (Civil Code 4950(a)); and to bring an action for a violation of the article within one year "
        "(Civil Code 4955(a)).",
        "**Executive session.** The board may meet in executive session to consider litigation, contracts, member "
        "discipline, personnel, or a member's payment plan (Civil Code 4935). A member's own discipline and payment plan "
        "have their own routes: if your matter is one of them, tick the last question and we will point you to the right "
        "form the same day.",
        "**A request in other words is still a request.** A letter or an email that says \"I want to speak at the next "
        "meeting\" is a request, and you may also stand and speak at the open forum. For an interpreter, large print, "
        "another format, a way to hear, a seat you can reach, someone to write your request down, or a reasonable "
        "accommodation, tick the help question or write to {BOARD_CONTACT}. Send this form to {RETURN_BY_MAIL} or "
        "{RETURN_BY_EMAIL}, or answer it online at {PORTAL}.",
        "The Association's plain-words notes above state its proposed policy and are not the statute; the words of the "
        "sections cited control. The Association's copy of the law is not an official restatement.",
    ),
    questions=(
        FormQuestion("Your name", key="name", reads=ReadAs.NAME, authority="Civil Code 4925(b)"),
        FormQuestion("Unit address", key="unit-address", prefill="UNIT_ADDRESS", reads=ReadAs.ADDRESS),
        FormQuestion("You are", QuestionKind.CHOICE, key="capacity",
                     options=("An owner of this unit", "A resident who is not an owner", "Someone else"),
                     help="We accept a request from a resident who is not an owner as a courtesy.",
                     authority="Civil Code 4925(b), 4930(a)"),
        FormQuestion("What do you want to do?", QuestionKind.CHECKBOX, key="purpose",
                     options=("Speak at the open forum", "Give the board a written comment",
                              "Ask the board to consider an item at a future meeting"),
                     help="Tick any. You may speak whether or not you use this form.",
                     authority="Civil Code 4925(b), 4930(c)(2)"),
        FormQuestion("Which meeting?", QuestionKind.CHOICE, required=False, key="meeting",
                     options=("The next board meeting", "A meeting on this date"),
                     help="Leave blank for the next meeting.", authority="Civil Code 4920"),
        FormQuestion("If a meeting on a date, which date?", QuestionKind.DATE, required=False, key="meeting-date"),
        FormQuestion("What is your topic, in a few words?", required=False, key="topic",
                     help="Needed if you want to speak or to ask the board to consider an item. You may speak on any issue, "
                          "even one not on the agenda."),
        FormQuestion("About how many minutes would you like?", required=False, key="time-needed",
                     help="For planning only. The board's time limit applies to every speaker."),
        FormQuestion("How will you attend?", QuestionKind.CHOICE, required=False, key="attend-how",
                     options=("In person", "By phone or video, if the meeting offers it"),
                     authority="Civil Code 4090(b), 4926(a)(4)"),
        FormQuestion("Do you need help to take part?", QuestionKind.CHECKBOX, required=False, key="help",
                     options=("I need help to take part",),
                     help="An interpreter, large print, a way to hear, a seat you can reach, or someone to write this down."),
        FormQuestion("What help do you need?", required=False, key="help-what"),
        FormQuestion("Your written comment for the board", QuestionKind.PARAGRAPH, required=False, key="comment",
                     section=COURTESY_COMMENT,
                     help="Needed if you ticked a written comment. The Act says nothing of written comments: the board "
                          "receives it as a courtesy, and it becomes part of the meeting's record."),
        FormQuestion("What do you ask the board to consider?", QuestionKind.PARAGRAPH, required=False, key="item-what",
                     section=COURTESY_ITEM,
                     help="Needed if you ticked an item. The board may place it on a future agenda, but the Act does not "
                          "require it to.", authority="Civil Code 4930(c)(2)"),
        FormQuestion("What would you like the board to do about it?", QuestionKind.PARAGRAPH, required=False, key="item-ask"),
        FormQuestion("Is this about your own account, a violation notice, a payment plan, or a dispute with the "
                     "Association?", QuestionKind.CHOICE, required=False, key="item-personal", options=("No", "Yes"),
                     section="Your own matter",
                     help="These have their own routes; we will tell you which the same day.",
                     authority="Civil Code 4935(a) to (c), 5665, 5900 to 5920"),
    ),
)

REQUIRED = (
    Required("A member may speak at a board or association meeting, except in executive session", (PREAMBLE, "purpose"),
             "CIV 4925(b)"),
    Required("The board's reasonable time limit applies to every member", (PREAMBLE,), "CIV 4925(b)"),
    Required("A member may speak on an issue not on the agenda", (PREAMBLE,), "CIV 4930(a)"),
    Required("The board may not discuss or act on an item not on the agenda, with the exceptions", (PREAMBLE,),
             "CIV 4930(a) to (e)"),
    Required("A request to add an item is a courtesy, not a right; the board may direct that a matter be placed on a future "
             "agenda", (PREAMBLE, "item-what"), "CIV 4930(c)(2)"),
    Required("Executive session: a member has no right to speak; the member's own discipline and payment plan have their own "
             "routes", (PREAMBLE, "item-personal"), "CIV 4925(b); CIV 4935"),
    Required("The notice and the agenda come at least four days before", (PREAMBLE,), "CIV 4920(a), (d)"),
    Required("A member joining by teleconference may be heard", ("attend-how",), "CIV 4090(b); CIV 4926"),
    Required("Who is asking, and in what capacity", ("name", "unit-address", "capacity"), "CIV 4160"),
    Required("The minutes are available within 30 days", (PREAMBLE,), "CIV 4950(a)"),
    Required("The member's remedy for a violation of the article", (PREAMBLE,), "CIV 4955(a)"),
    Required("That a request in other words is still a request, and where to get help", (PREAMBLE, "help")),
)

CLOCKS = (
    Clock("acknowledge", "receipt", 2, DayKind.BUSINESS, SetBy.PROPOSED_POLICY, "", "the member is left without a date"),
    Clock("meeting-notice", "the board meeting (the notice and agenda are due at least this many days before it)", 4,
          DayKind.CALENDAR, SetBy.STATUTE, "CIV 4920(a)", "the board may not act on an item (4930(a)); the member may sue (4955)"),
    Clock("executive-session-notice", "a nonemergency board meeting held solely in executive session (notice is due at least "
          "this many days before it)", 2, DayKind.CALENDAR, SetBy.STATUTE, "CIV 4920(b)(2)", "see 4955"),
    Clock("minutes", "the meeting", 30, DayKind.CALENDAR, SetBy.STATUTE, "CIV 4950(a)", "see 4955"),
)

RECITALS = ("CIV 4925(b)", "CIV 4925(a)", "CIV 4930(a)", "CIV 4930(c)(2)", "CIV 4935(a)", "CIV 4935(b)", "CIV 4935(c)",
            "CIV 4920(a)", "CIV 4920(c)", "CIV 4920(d)", "CIV 4950(a)", "CIV 4955(a)", "CIV 4090(b)")

NOTES = (
    "The Act gives no right to place an item on the agenda: the form says so, and its comment and item parts are labeled "
    "courtesies. Whether the bylaws or another statute (the Corporations Code on a special meeting called by members) gives one "
    "is for counsel; that code is not on the shelf and is not quoted.",
    "Proposed policy for the board's adoption where it has set no time limit (4925(b)): a stated number of minutes for each "
    "speaker, the same for every member, printed on the notice of every meeting. The number is the board's.",
    "Proposed dedicated step: board-packet (it exists) gains a step: read the meeting-comment requests received since the last "
    "packet; list each speaker, put each written comment in the packet, list each item request as a candidate for the agenda for "
    "the person who sets it, and prepare the answers for a person to send. The handler here is response-clock with respond.",
    "jason never decides whether an item is placed on an agenda, sets the order of speakers, limits anyone's time, or answers "
    "for the board.",
)

DEFINITION = register(FormDefinition(
    key="meeting-comment-request",
    tier=Tier.STATE,
    jurisdiction="CA",
    template=TEMPLATE,
    version="1",
    as_of=date(2026, 10, 5),
    authority=("CIV 4925", "CIV 4930", "CIV 4920", "CIV 4935"),
    required_content=REQUIRED,
    recitals=RECITALS,
    member_clock=MEMBER_CLOCK,
    association_clocks=CLOCKS,
    acknowledgment=ACKNOWLEDGMENT,
    procedure="respond",
    handler="response-clock",
    channels=(Channel.PAPER, Channel.FILLABLE_PDF, Channel.EMAIL, Channel.PAYHOA, Channel.PORTAL, Channel.GOOGLE_FORM),
    slots=SLOTS,
    notes=NOTES,
))
