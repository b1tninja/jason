"""Mystique's registers: the Google Sheets jason and the board keep together (docs/registers.md).

The board action items are the first: jason writes what each item is (its ask, authority, evidence, priority) and the
board writes its standing (status, owner, meeting, notes), in the Sheet or by checking off the item's Google Task. The
Sheet is the existing "Mystique Board Action Items" (BOARD_ITEMS_SHEET in banking.py); new registers are created in the
association's Drive folder "Registers", shared with no one until the board decides.
"""

from __future__ import annotations

from jason.community.board_items import ItemCategory, ItemStatus, Priority, Session
from jason.community.registers import Column, Kind, Owner, Register

J, B = Owner.JASON, Owner.BOARD

REGISTERS_FOLDER = "Registers"

BOARD_ITEMS = Register(
    "board-items", "Mystique Board Action Items", "Items",
    (
        Column("id", J, width=200, note="jason's key for the item; never edit"),
        Column("priority", J, Kind.CHOICE, tuple(p.value for p in Priority), 80),
        Column("status", B, Kind.CHOICE, tuple(s.value for s in ItemStatus), 110, "the board's standing for the item"),
        Column("category", J, Kind.CHOICE, tuple(c.value for c in ItemCategory), 110),
        Column("title", J, width=320),
        Column("ask", J, width=420),
        Column("summary", J, width=420),
        Column("authority", J, width=200),
        Column("evidence", J, width=260),
        Column("session", J, Kind.CHOICE, tuple(s.value for s in Session), 130),
        Column("special_notice", J, width=200),
        Column("due", J, Kind.DATE, width=100),
        Column("opened", J, Kind.DATE, width=100),
        Column("owner", B, width=140, note="the director who carries the item"),
        Column("meeting", B, Kind.DATE, width=100, note="the meeting the item is set for"),
        Column("notes", B, width=320),
    ),
    about="The board's running action items: what each matter is (jason) and where the board stands on it (the board).",
)

REGISTERS = (BOARD_ITEMS,)
