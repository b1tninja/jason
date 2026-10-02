"""Unit and member context notes (not request/submission notes)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ContextNotes:
    unit_notes: list[dict[str, Any]] = field(default_factory=list)
    member_notes: list[dict[str, Any]] = field(default_factory=list)
    unit_id: int | None = None
    membership_id: int | None = None

    def summary(self) -> str:
        parts = [
            f"unit_notes={len(self.unit_notes)}",
            f"member_notes={len(self.member_notes)}",
        ]
        if self.unit_id is not None:
            parts.append(f"unit_id={self.unit_id}")
        if self.membership_id is not None:
            parts.append(f"membership_id={self.membership_id}")
        return " ".join(parts)


def fetch_context_notes(
    client: Any,
    org_id: int,
    *,
    unit_id: int | None = None,
    membership_id: int | None = None,
) -> ContextNotes:
    """Fetch unit notes and/or member notes for the given ids.

    Calls ``client.list_unit_notes(org_id, unit_id)`` and
    ``client.list_member_notes(org_id, membership_id)`` when the respective
    id is provided. These are separate from submission/request notes.
    """
    if unit_id is None and membership_id is None:
        raise ValueError("unit_id and/or membership_id required")

    unit_notes: list[dict[str, Any]] = []
    member_notes: list[dict[str, Any]] = []
    if unit_id is not None:
        unit_notes = list(client.list_unit_notes(org_id, unit_id))
    if membership_id is not None:
        member_notes = list(client.list_member_notes(org_id, membership_id))
    return ContextNotes(
        unit_notes=unit_notes,
        member_notes=member_notes,
        unit_id=unit_id,
        membership_id=membership_id,
    )
