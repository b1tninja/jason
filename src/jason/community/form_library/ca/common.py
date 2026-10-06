"""What the California forms of requests and money share, written once (docs/form-templates.md, "The standard every form follows").

A form of this pack opens with the law's words and the member's clock, asks only what the law needs and says why, and
puts help on the form. The pieces every one of them repeats are here, so a change to one (the help line, the way an
email address is asked for) reaches every form and no copy drifts. This module registers nothing: it holds paragraphs
and question builders, and the definitions in the other modules of the pack use them.

``{RETURN_BY_MAIL}``, ``{RETURN_BY_EMAIL}``, and ``{BOARD_CONTACT}`` are slots: the community gives them, and a form
that uses one is not offered until it is given (docs/form-library-design.md, check 3).
"""

from __future__ import annotations

from datetime import date

from jason.community.forms import FormQuestion, QuestionKind, ReadAs

# The day of the law the forms of the pack were last read against the shelf (2025 session publication of the code).
AS_OF = date(2026, 10, 5)

PLAIN_WORDS_NOTE = ("These are the association's plain-words notes on the sections named; the words of each section control. "
                    "The text of each section is on the association's records shelf, and jason's copy is not an official "
                    "restatement of the law.")

# Standard 5 (docs/form-templates.md): help is on the form, and a request in other words is still a request.
HELP_ON_THE_FORM = ("**This form is the usual way to ask, never the only way.** A request in other words is still a "
                    "request. To ask for another format, large print, or translation, for help filling in this form, or "
                    "for a reasonable accommodation, write to {RETURN_BY_EMAIL} or {RETURN_BY_MAIL}.")

CHANNELS_NOTE = ("An email address is asked for only if you choose email, and a phone number only if you choose the phone "
                 "(Civil Code 4041(b)(2)(A)).")

SAME_AS_UNIT = "Same as my unit address"

# The two questions every request opens with: who asks, and for which unit.
NAME = FormQuestion("Your name", key="name", reads=ReadAs.NAME)
UNIT_ADDRESS = FormQuestion("Unit address", key="unit-address", prefill="UNIT_ADDRESS", reads=ReadAs.ADDRESS)


def one_box(title: str, key: str, statement: str, *, required: bool = False, help: str = "", authority: str = "") -> FormQuestion:
    """A single box to check: the statement is the box's own words, so the checked box is the member's statement."""
    return FormQuestion(title, QuestionKind.CHECKBOX, required, (statement,), help, key, authority=authority)


def mailing_address(*, help: str = "", title: str = "Mailing address") -> FormQuestion:
    """An address written in its parts, with the usual answer as one box."""
    return FormQuestion(title, required=False, key="mailing-address", lines=2, reads=ReadAs.ADDRESS, same_as=SAME_AS_UNIT,
                        help=help, authority="Civil Code 4040(a)")


def contact_questions(prompt: str, *, why: str) -> tuple[FormQuestion, ...]:
    """How the association reaches the member: one required choice, then the one detail the choice needs, each of them
    not required on its own because the form's questions are a plain flag (``FormQuestion.required``): the help line says
    when each is needed, and the handler reads it (an email address is never required unless the member picks email)."""
    return (
        FormQuestion(prompt, QuestionKind.CHOICE, True, ("By email", "By phone", "By mail"), why, "contact-method"),
        FormQuestion("Email address", QuestionKind.EMAIL, False, help="Fill this in only if you chose email.", key="email",
                     authority="Civil Code 4041(b)(2)(A)"),
        FormQuestion("Phone number", QuestionKind.PHONE, False, help="Fill this in only if you chose the phone.", key="phone"),
        mailing_address(help="Fill this in only if you chose mail."),
    )


__all__ = ["AS_OF", "CHANNELS_NOTE", "HELP_ON_THE_FORM", "NAME", "PLAIN_WORDS_NOTE", "SAME_AS_UNIT", "UNIT_ADDRESS",
           "contact_questions", "mailing_address", "one_box"]
