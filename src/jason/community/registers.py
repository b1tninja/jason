"""A register: a Google Sheet that jason and the board keep together, one row per record, found by its key.

A ``Register`` is a specification row: its title, the tab that holds the records, its columns, and whether it is
confidential (shared with directors only). Each ``Column`` belongs to jason or to the board (``Owner``): jason writes only
its own columns and reads the board's back, so neither overwrites the other. A column's ``kind`` gives the Sheet its
data validation (a dropdown of ``choices``, a date, a checkbox). The first column is the key; it never changes once a row
is written, and rows are found by it, never by their position.

Every change the board makes in a board column is also kept as a row in the register's log tab (``LOG_TAB``): the key,
the column, the value before and after, and when jason saw it. The log is append-only; the Sheet's version history is
the second record.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Owner(Enum):
    JASON = "jason"
    BOARD = "board"


class Kind(Enum):
    TEXT = "text"
    DATE = "date"
    NUMBER = "number"
    MONEY = "money"           # dollars and cents in the Sheet; integer cents in jason
    CHOICE = "choice"         # a dropdown of the column's choices
    CHECKBOX = "checkbox"
    LINK = "link"


@dataclass(frozen=True)
class Column:
    name: str
    owner: Owner = Owner.JASON
    kind: Kind = Kind.TEXT
    choices: tuple[str, ...] = ()
    width: int = 140          # pixels
    note: str = ""            # the header's note: what the column holds


@dataclass(frozen=True)
class Register:
    key: str                  # "board-items"
    title: str                # the spreadsheet's title
    tab: str                  # the records' tab
    columns: tuple[Column, ...]
    confidential: bool = False
    about: str = ""           # a sentence for the spreadsheet's About tab
    book: str = ""            # registers with the same book share one spreadsheet, each on its own tab

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(c.name for c in self.columns)

    def owned(self, owner: Owner) -> tuple[Column, ...]:
        return tuple(c for c in self.columns if c.owner is owner)


LOG_TAB = "Log"
LOG_COLUMNS = ("seen", "key", "column", "before", "after", "by")


__all__ = ["Column", "Kind", "LOG_COLUMNS", "LOG_TAB", "Owner", "Register"]
