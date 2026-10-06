"""The records for checking an association's request for responses (docs/responses-design.md).

An owner can answer a request several ways: a signed-in PayHOA form, a Google Form, a reply email carrying the filled
form, a mailed return that was scanned. Each thing that comes in is an ``Arrival``: a stable id, the channel it came by,
when, from whom (a display name, never a stored personal address), the unit when the channel says, and a ``State``.
A profile says which requests expect answers (``Community.response_requests``, default none): one ``ResponseRequest``
each, with the form, the cycle, the PayHOA form's key, the outside forms read into it, and the form-marker campaigns
that tie a scan to the request by its printed reference.

This module is records only. ``jason.tasks.response_inbox`` finds arrivals, keeps them, reads them, and makes a
person's confirmed reading into answers. (``jason.community.responses`` is a different thing: the clocks that start
when a member writes to the association.)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from enum import Enum
from typing import Any, ClassVar, NamedTuple

from jason.community.forms import AnswerCycle, FormImport, FormTemplate


class Channel(Enum):
    PAYHOA = "payhoa"       # the form's submissions, signed in
    GMAIL = "gmail"         # a reply email, with its attachments
    MAIL = "mail"           # a mailed return, scanned by the mail service
    FORMS = "forms"         # the saved responses of a Google Form
    MANUAL = "manual"       # a return a person keyed from paper handed in, or taken by phone (nothing is checked for it)


class State(Enum):
    NEW = "new"                 # kept by a check; nobody has looked
    SEEN = "seen"               # a person looked and left it
    READ = "read"               # its attachments were read; a reading is kept, unconfirmed
    KEYED = "keyed"             # a person confirmed the reading (with corrections); answers kept
    RECORDED = "recorded"       # the writes it calls for were made in PayHOA
    DISMISSED = "dismissed"     # not an answer (a question, a duplicate, not the form)


# A PayHOA submission or a form response is already structured: its source is its confirmation, so it needs no reading.
STRUCTURED = (Channel.PAYHOA, Channel.FORMS)


@dataclass(frozen=True)
class Arrival:
    """One thing that came in answer to a request. ``who`` is the sender or owner as the channel names them (a display
    name); a personal email address is never stored on an arrival: the sender's address is matched to an owner when the
    message is read, and only the owner's unit and name are kept."""

    id: str                         # "<channel>:<native id>", e.g. "gmail:abc123", "payhoa:1001"
    request: str                    # ResponseRequest.key
    channel: Channel
    at: str                         # when it arrived (UTC ISO)
    who: str
    unit: str = ""                  # the unit it is for, when the channel says
    summary: str = ""               # a subject line, or the form's title
    attachments: tuple[str, ...] = ()
    state: State = State.NEW
    kept_at: str = ""               # the check that kept it
    superseded_by: str = ""
    note: str = ""

    @property
    def native(self) -> str:
        return self.id.split(":", 1)[1] if ":" in self.id else self.id

    @property
    def stem(self) -> str:
        """The id as a file name (a colon is not allowed in one on Windows): ``gmail-abc123``."""
        return self.id.replace(":", "-")

    @property
    def structured(self) -> bool:
        return self.channel in STRUCTURED

    def to_json(self) -> dict[str, Any]:
        return {"id": self.id, "request": self.request, "channel": self.channel.value, "at": self.at, "who": self.who,
                "unit": self.unit, "summary": self.summary, "attachments": list(self.attachments),
                "state": self.state.value, "kept_at": self.kept_at, "superseded_by": self.superseded_by,
                "note": self.note}

    @classmethod
    def from_json(cls, raw: dict[str, Any]) -> Arrival:
        return cls(raw["id"], raw.get("request", ""), Channel(raw["channel"]), raw.get("at", ""), raw.get("who", ""),
                   raw.get("unit", ""), raw.get("summary", ""), tuple(raw.get("attachments") or ()),
                   State(raw.get("state", "new")), raw.get("kept_at", ""), raw.get("superseded_by", ""),
                   raw.get("note", ""))


class Window(NamedTuple):
    """The days a request is watched: from ``start`` to ``end`` (None: no end, a person's ``--since``)."""
    start: date
    end: date | None

    def closed(self, today: date) -> bool:
        return self.end is not None and today > self.end

    def contains(self, day: date) -> bool:
        return day >= self.start and (self.end is None or day <= self.end)


@dataclass(frozen=True)
class ResponseRequest:
    """One request that expects answers. ``form`` is the ``FormTemplate`` (the reader and the question keys); ``cycle``
    the ``AnswerCycle`` (opened, return-by); ``payhoa_form`` the key ``payhoa_forms.record_for`` looks up, or empty;
    ``imports`` the ``FormImport`` rules of any Google Form read into the form; ``marker_campaigns`` the campaigns of the
    markers its copies carry (``form_refs.campaign``), so a scan is tied to the request by its printed reference;
    ``blank`` the request's fillable PDF, relative to the data folder, which a scan is read against."""

    key: str
    title: str
    form: FormTemplate
    cycle: AnswerCycle
    payhoa_form: str = ""
    imports: tuple[FormImport, ...] = ()
    marker_campaigns: tuple[str, ...] = ()
    blank: str = ""

    AFTER_RETURN_BY: ClassVar[int] = 7          # days a request is still watched past its return-by date

    def window(self, since: date | None = None) -> Window:
        """From the day the request opened to a week past its return-by date; with ``since``, from that day on and
        with no end (a person asked)."""
        if since is not None:
            return Window(since, None)
        end = self.cycle.return_by + timedelta(days=self.AFTER_RETURN_BY) if self.cycle.return_by else None
        return Window(self.cycle.opened, end)

    def names_campaign(self, campaign: str) -> bool:
        return campaign.upper() in {c.upper() for c in self.marker_campaigns}


__all__ = ["Arrival", "Channel", "ResponseRequest", "STRUCTURED", "State", "Window"]
