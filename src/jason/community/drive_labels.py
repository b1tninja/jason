"""jason's labels on Drive files, stored as Drive appProperties.

A Drive file carries up to 30 private properties per application, each key and value together at most 124 bytes of
UTF-8. Only the OAuth application that set a property can read it; the Drive UI does not show it. A property can be
searched with ``appProperties has { key='k' and value='v' }``, an exact match on the whole value.

The schema is data: one ``LabelProperty`` row per key, in ``mystique/labels.py``. A row says what the key holds, where
the value comes from, who writes it, and how an overlong value is trimmed. ``fit`` applies the trim. A label is a lead
for a person to follow, not a classification of the file.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

PROPERTY_BYTES = 124        # key and value together, UTF-8
PROPERTIES_PER_APP = 30     # private properties per file from one application
PREFIX = "jason_"
ELLIPSIS = "…"
LIST_SEPARATOR = ","


class Label(Enum):
    """Each appProperties key jason owns. The value is the key as Drive stores it."""

    KIND = "jason_kind"
    RECORDS = "jason_records"
    MEETINGS = "jason_meetings"
    ITEM = "jason_item"
    TOPICS = "jason_topics"
    INCIDENT = "jason_incident"
    CLAIMS = "jason_claims"
    CONFIDENTIAL = "jason_confidential"
    LABELED_AT = "jason_labeled_at"
    HOLD = "jason_hold"
    PRIVILEGE = "jason_privilege"


class LabelSource(Enum):
    """Where a label's value is read from."""

    DRIVE_HOLDINGS = "jason drive (data/drive/holdings.json)"
    AGENDA_LINKS = "agenda links (data/meetings/agenda-links.json)"
    MEETING_CATALOG = "meeting catalog (data/meetings/catalog.json)"
    APPLY = "the apply run itself"
    LEGAL_HOLD = "a legal hold"


class LabelWriter(Enum):
    """Which command writes the key. ``jason drive-labels`` writes and removes only its own keys."""

    DRIVE_LABELS = "jason drive-labels"
    LEGAL_HOLD = "jason legal-hold"


class Fit(Enum):
    """How a value longer than its budget is trimmed. Every trim is deterministic."""

    LIST = "drop whole list items from the end"
    TEXT = "cut at a character boundary and end with an ellipsis"
    EXACT = "never trimmed; an overlong value is not written"


@dataclass(frozen=True)
class LabelProperty:
    """One appProperties key: what it holds, how it is derived, its writer, and its trim."""

    label: Label
    holds: str
    derived: str
    source: LabelSource
    writer: LabelWriter = LabelWriter.DRIVE_LABELS
    fit: Fit = Fit.EXACT

    @property
    def key(self) -> str:
        return self.label.value

    @property
    def max_value_bytes(self) -> int:
        """Bytes left for the value once the key is counted."""
        return PROPERTY_BYTES - len(self.key.encode("utf-8"))


def fits(key: str, value: str) -> bool:
    return len(key.encode("utf-8")) + len(value.encode("utf-8")) <= PROPERTY_BYTES


def fit(prop: LabelProperty, value: str) -> str | None:
    """The value trimmed to the key's budget by the row's rule, or None when an exact value is too long."""
    budget = prop.max_value_bytes
    if len(value.encode("utf-8")) <= budget:
        return value
    if prop.fit is Fit.EXACT:
        return None
    if prop.fit is Fit.LIST:
        kept: list[str] = []
        for item in value.split(LIST_SEPARATOR):
            candidate = LIST_SEPARATOR.join([*kept, item])
            if len(candidate.encode("utf-8")) > budget:
                break
            kept.append(item)
        if kept:
            return LIST_SEPARATOR.join(kept)
        # A single item longer than the budget is cut as text.
    room = budget - len(ELLIPSIS.encode("utf-8"))
    cut = value.encode("utf-8")[:room].decode("utf-8", errors="ignore").rstrip(" ,;/-")
    return cut + ELLIPSIS


__all__ = [
    "ELLIPSIS",
    "Fit",
    "LIST_SEPARATOR",
    "Label",
    "LabelProperty",
    "LabelSource",
    "LabelWriter",
    "PREFIX",
    "PROPERTIES_PER_APP",
    "PROPERTY_BYTES",
    "fit",
    "fits",
]
