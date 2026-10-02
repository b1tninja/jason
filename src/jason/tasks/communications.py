"""Owner communications for a recipient membership/user id."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


def summarize_communication(item: Mapping[str, Any]) -> dict[str, Any]:
    """Compact summary using only fields that exist on the item."""
    out: dict[str, Any] = {}
    for key, aliases in (
        ("type", ("type", "communicationType", "kind")),
        ("date", ("date", "sentAt", "createdAt", "communicationDate")),
        ("subject", ("subject", "title", "name")),
    ):
        for alias in aliases:
            if alias in item and item[alias] is not None and item[alias] != "":
                out[key] = item[alias]
                break
    if "id" in item:
        out["id"] = item["id"]
    return out


@dataclass
class CommunicationsReport:
    items: list[dict[str, Any]] = field(default_factory=list)
    summaries: list[dict[str, Any]] = field(default_factory=list)
    recipient_id: int | None = None

    def summary(self) -> str:
        return f"communications={len(self.items)} recipient_id={self.recipient_id}"


def list_owner_communications(
    client: Any,
    org_id: int,
    recipient_id: int,
) -> CommunicationsReport:
    """List communications for ``recipient_id`` via ``iter_communications``."""
    items = [
        dict(item)
        for item in client.iter_communications(org_id, recipient_id=recipient_id)
    ]
    summaries = [summarize_communication(item) for item in items]
    return CommunicationsReport(
        items=items,
        summaries=summaries,
        recipient_id=recipient_id,
    )
