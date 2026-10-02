"""A PayHOA request form as the association's specification names it, and the form a set of topics belongs on."""

from __future__ import annotations

from dataclasses import dataclass

from jason.community.topics import Topic


@dataclass(frozen=True)
class RequestForm:
    """One request form: its PayHOA id, the ids of its title, message, and attachment questions, and the topics it takes.

    A form with no topics is the catch-all.
    """

    name: str
    form_id: int
    title_question: int
    message_question: int
    attachment_question: int
    topics: tuple[Topic, ...] = ()


def form_for(topics: tuple[Topic, ...] | list[Topic], forms: tuple[RequestForm, ...]) -> RequestForm | None:
    """The first form that takes one of ``topics``, else the catch-all (a form with no topics), else None."""
    for form in forms:
        if form.topics and any(t in form.topics for t in topics):
            return form
    return next((f for f in forms if not f.topics), None)


__all__ = ["RequestForm", "form_for"]
