"""The ways jason delivers a form to owners, behind one shape: the Mailroom (paper, USPS through PayHOA and Lob) and
email (PayHOA's per-member send). PayHOA's own form and a broadcast are the next to join.

An engine says:

- its **channel** (``form_refs.Channel``), which is also the marker's channel letter;
- its **identity**: ``CAMPAIGN`` when every copy is the same (the mailed letter: its marker names the campaign,
  ``NP27M-…``), or ``COPY`` when each copy is its owner's own (the pre-filled email: its marker names the copy,
  ``NP27E-4RK9T-…``). A campaign is enough to know a return came from this mailing; a copy names who it went to and what
  it said;
- its **pace** (``batches.Pace``) and how its plan becomes batch items (``items``) and the handler that sends one
  (``handler``), so ``jason.batches`` runs every engine the same way: slowly, from a ledger, resumable.

The marker is a hint on what goes out (``form_refs``); reading what comes back never depends on it.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from jason.community.form_refs import Channel, Marker, make


class Identity(Enum):
    CAMPAIGN = "campaign"     # every copy the same; the marker names the campaign
    COPY = "copy"             # each copy its owner's own; the marker names the copy


@dataclass(frozen=True)
class Engine:
    name: str
    channel: Channel
    identity: Identity
    interval: float = 8.0
    jitter: float = 4.0

    def batch_id(self, form: Any, year: int) -> str:
        return f"{form.key.value}-{year}-{self.channel.name.lower()}"

    def marker(self, form: Any, year: int, *, membership_id: int | None = None, unit_id: int | None = None) -> Marker:
        """The marker on what this engine sends: the campaign's, or, for a COPY engine given an owner and unit, the
        copy's."""
        if self.identity is Identity.COPY and membership_id is not None and unit_id is not None:
            return make(form.code, year, self.channel, membership_id=membership_id, unit_id=unit_id)
        return make(form.code, year, self.channel)

    def pace(self) -> Any:
        from jason.batches import Pace

        return Pace(interval=self.interval, jitter=self.jitter)


class EmailEngine(Engine):
    """Each owner with a working email gets their own filled copy (``owner_send.EmailHandler``), marked as theirs."""

    def items(self, rows: list[Any], units: list[dict[str, Any]], tags: Any) -> list[tuple[str, str, dict[str, Any]]]:
        from jason.tasks.owner_send import batch_items

        return batch_items(rows)

    def handler(self, client: Any, org_id: int, rows: list[Any], **context: Any) -> Any:
        from jason.tasks.owner_send import EmailHandler

        return EmailHandler(client, org_id, rows, **context)


class MailroomEngine(Engine):
    """The same letter to every owner the law sends mail, one Mailroom send per building
    (``owner_send.MailHandler``), marked with the campaign."""

    def items(self, rows: list[Any], units: list[dict[str, Any]], tags: Any) -> list[tuple[str, str, dict[str, Any]]]:
        from jason.tasks.owner_send import mail_items

        return mail_items(rows, units, tags)

    def letter(self, packet: Path, form: Any, year: int, out: Path) -> Path:
        """The letter as it is mailed: the packet with the campaign's marker on every page."""
        import shutil

        from jason.community.fillable import stamp_reference

        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(packet, out)
        return stamp_reference(out, self.marker(form, year).text)

    def handler(self, client: Any, org_id: int, data_dir: Any, *, pdf: Path, double_sided: bool = False) -> Any:
        from jason.tasks.owner_send import MailHandler

        return MailHandler(client, org_id, data_dir, pdf=pdf, double_sided=double_sided)


ENGINES: dict[Channel, Engine] = {
    Channel.EMAIL: EmailEngine("email", Channel.EMAIL, Identity.COPY),
    Channel.MAIL: MailroomEngine("mailroom", Channel.MAIL, Identity.CAMPAIGN, interval=20.0, jitter=10.0),
}


__all__ = ["ENGINES", "EmailEngine", "Engine", "Identity", "MailroomEngine"]
