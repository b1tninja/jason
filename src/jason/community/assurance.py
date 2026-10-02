"""How sure the Association is that a returned form came from the owner it speaks for (``forms.Assurance``).

No channel but a signed-in one proves who answered. A paper form can be signed by anyone, an emailed PDF can be
forwarded, and a Google Form needs no sign-in. What each return does carry is evidence, and the levels rank it:

- **SIGNED_IN**: the owner signed in to send it (a PayHOA form submission).
- **MATCHED**: it came from the email the Association has for an owner of that unit (an email reply's sender; a Google
  Form's *verified* respondent email), or quotes that owner's own reference and names that same email.
- **TOKEN**: it quotes a reference only that owner's copy carried: an emailed copy's marker, or the personal link that
  copy's email held (``form_refs``; the registry is ``tasks/form_references``).
- **CLAIMED**: it names the unit and an owner and came by the Association's own mailing (a signed letter, its campaign
  marker), or names an email that matches but was only typed.
- **LEAD**: nothing ties it to the owner (an unlinked Google Form answer, a reference for another unit).

``assess`` gives the level and its reasons. A return below ``MATCHED`` is the owner's word only once the Association
has told the address on file what changed and given them the chance to say it wasn't them (``confirm``); what level
a change may be recorded at is the specification's (``mystique/forms.py``). A reference is a hint everywhere else;
here it is evidence of who held the copy, never proof of who wrote on it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable

from jason.community.forms import Assurance


class Channel(Enum):
    PAYHOA = "payhoa"          # a signed-in PayHOA form submission
    EMAIL = "email"            # a reply email (its sender is the From address), a typed PDF attached
    GOOGLE = "google"          # a Google Form response
    PAPER = "paper"            # a mailed or scanned paper form


@dataclass(frozen=True)
class Provenance:
    channel: Channel
    sender: str = ""            # the email it came from (a reply) or the respondent's email (a Google Form)
    sender_verified: bool = False  # a Google sign-in gave the respondent's email (not typed)
    reference: str = ""         # the reference it quoted (a link's prefill, a reply's subject, a scan's marker)


@dataclass
class Assessment:
    level: Assurance
    reasons: list[str] = field(default_factory=list)

    @property
    def confirm(self) -> bool:
        """Whether the address on file is to be told of the change before it is relied on."""
        return self.level < Assurance.MATCHED


def assess(p: Provenance, *, unit_id: int | None, on_file: Iterable[str], sent: dict[str, dict[str, Any]]) -> Assessment:
    """The level of one return: ``unit_id`` the unit it answers for (as it says, or as its reference names), ``on_file``
    the emails PayHOA has for that unit's owners, ``sent`` the registry of references sent (reference to its record:
    ``unitId``, ``membershipId``, ``channel``)."""
    from jason.community.form_refs import parse, repaired

    if p.channel is Channel.PAYHOA:
        return Assessment(Assurance.SIGNED_IN, ["signed in to PayHOA"])
    emails = {e.strip().casefold() for e in on_file if e and e.strip()}
    sender = p.sender.strip().casefold()
    reasons: list[str] = []
    marker = next(iter(parse(p.reference)), None)
    fixed = False
    if marker is None:
        marker, fixed = next(iter(repaired(p.reference)), None), True
    record = sent.get(marker.text) if marker else None
    token = campaign = False
    if marker and record is None:
        reasons.append(f"quotes {marker.text}, which the Association did not send")
    elif marker and record:
        if marker.copy:
            if unit_id is not None and record.get("unitId") not in (None, unit_id):
                return Assessment(Assurance.LEAD, [f"quotes {marker.text}, the reference sent for another unit"])
            token = True
            reasons.append(f"quotes {marker.text}, the reference only that owner's copy carried"
                           + (" (one character put right)" if fixed else ""))
        else:
            campaign = True
            reasons.append(f"answers the mailing {marker.text}")
    matches = bool(sender) and sender in emails
    if matches and (p.channel is Channel.EMAIL or p.sender_verified):
        reasons.append("sent from the email on file" if p.channel is Channel.EMAIL else
                       "a Google sign-in gave the email on file")
        return Assessment(Assurance.MATCHED, reasons)
    if matches and token:
        reasons.append("names the email on file")
        return Assessment(Assurance.MATCHED, reasons)
    if token:
        return Assessment(Assurance.TOKEN, reasons)
    if matches:
        reasons.append("names the email on file, typed (not verified)")
        return Assessment(Assurance.CLAIMED, reasons)
    if campaign or p.channel is Channel.PAPER:
        reasons.append("a signed form by mail" if p.channel is Channel.PAPER else "names the unit")
        return Assessment(Assurance.CLAIMED, reasons)
    if sender:
        reasons.append("from an email the Association does not have for this unit")
    return Assessment(Assurance.LEAD, reasons or ["nothing ties it to an owner of the unit"])


__all__ = ["Assessment", "Channel", "Provenance", "assess"]
