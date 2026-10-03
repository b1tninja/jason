"""Mystique's bank accounts, by the last four digits the bank's file names carry.

A reserve account's statements and letters are records of reserve balances and payments under Civil Code 5200(a)(7)
as well as enhanced records under 5200(b); the operating account's statements are enhanced records only. The library
marks a file by the suffix in its name ("<date>-statements-<last four>-.pdf").

The accounts themselves (suffix, purpose, bank, label) are private facts in data/spec/mystique/bank_accounts.json
(jason.community.private), confirmed by the board on 2026-09-29: one operating account and the reserve accounts,
including two reserve certificates of deposit.
"""

from __future__ import annotations

from jason.community.base import AccountPurpose, BankAccount, BoardRule, MeetingSchedule, ReserveLine

def _accounts() -> tuple[BankAccount, ...]:
    from jason.community.private import facts

    return tuple(BankAccount(str(r["suffix"]), AccountPurpose(r["purpose"]), r.get("bank", ""), r.get("label", ""))
                 for r in facts("bank_accounts", [], profile="mystique"))


BANK_ACCOUNTS: tuple[BankAccount, ...] = _accounts()

# PayHOA's budget lines for money moved into the reserve. "Repayment" is a child of "Transfer to Reserves"; the 2025
# budget carried the repayment of the December 2024 borrowing (Special Resolution 12-17-24) there. "Reserve Analyst",
# the other child, is the study's fee and is not a transfer.
RESERVE_BUDGET_LINES: dict[ReserveLine, str] = {
    ReserveLine.CONTRIBUTION: "Transfer to Reserves",
    ReserveLine.REPAYMENT: "Repayment",
}

# The board: Bylaws 5.1 allows three to five directors, the number fixed by the board; it is five (confirmed by the board
# 2026-09-29, with four seats filled). Bylaws 7.10: "A majority of the number of Directors then in office, but not less
# than two Directors, shall constitute a quorum for the transaction of business."
BOARD = BoardRule(seats=5, minimum=3, maximum=5, quorum_floor=2, source="Bylaws 5.1, 7.10")

# Administrative Resolution 20230130-1 (adopted January 30, 2023; Bylaws 4.1, 7.2): all meetings at 7:00 pm on Zoom;
# regular board meetings the third Tuesday of January, April, July, and October; the annual meeting of members the third
# Tuesday of November. The board meets the third Tuesday of every month in practice (told by the treasurer 2026-09-29); a
# later resolution adopting that is not in the library.
MEETING_SCHEDULE = MeetingSchedule(weekday=1, nth=3, time="7:00 pm", place="Zoom", regular_months=(1, 4, 7, 10), annual_month=11,
                                   resolution="Administrative Resolution 20230130-1",
                                   practice="the third Tuesday of every month")

# The board's running action items as a Google Sheet ("Mystique Board Action Items", created by jason 2026-09-29 at the
# treasurer's request, private to the association's Drive). `jason board --sheet` reads the board's edits and writes the list.
BOARD_ITEMS_SHEET = "1SPxkJkB6hNtMw1pwfwvhNpp1QKw9gS_OOH9oeMWK1cM"

__all__ = ["BANK_ACCOUNTS", "BOARD", "BOARD_ITEMS_SHEET", "MEETING_SCHEDULE", "RESERVE_BUDGET_LINES", "AccountPurpose", "BankAccount",
           "ReserveLine"]
