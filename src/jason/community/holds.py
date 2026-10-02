"""A legal hold: what the association must keep for a matter, from when, whose, and how it is kept.

The duty to preserve arises when litigation is pending or reasonably anticipated (Cedars-Sinai Medical Center v. Superior
Court (1998) 18 Cal.4th 1; Evid. Code 413; Code Civ. Proc. 2031.060(i)(2)), not when a hold is written down: ``duty_from``
is that day, and the hold reaches everything from ``relevant_from`` on. No rule names a tool; the standard is reasonable,
good-faith, proportionate steps, documented (The Sedona Conference, Commentary on Legal Holds, 2d ed. 2019).

A ``LegalHoldSpec`` is a specification row: the matter (``case`` names a ``LegalCase``), the Workspace accounts Vault can
hold (``custodians``), the people whose own accounts Vault cannot reach and who get a written notice
(``notice_to``), the words that put a mail, file, or meeting in scope, the Drive folders held whole, the rules suspended
while the hold stands, counsel, and who keeps the register. Release is counsel's, in writing.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class LegalHoldSpec:
    key: str
    case: str                                   # the LegalCase key (mystique/cases.py)
    title: str                                  # the Vault matter's name; no private person's name
    duty_from: date                             # when preservation became a duty (a preservation letter, a claim)
    relevant_from: date                         # the earliest date whose records are in scope
    custodians: tuple[str, ...]                 # Workspace accounts: Vault holds their Drive and Mail
    terms: tuple[str, ...]                      # words that put a mail subject, file name, or meeting transcript in scope
    drive_folders: tuple[str, ...] = ()         # Drive folder ids held whole
    notice_to: tuple[str, ...] = ()             # roles whose own accounts and devices Vault cannot reach
    outside_vault: tuple[str, ...] = ()         # sources to export and keep by hand
    suspends: tuple[str, ...] = ()              # deletion rules and settings suspended while the hold stands
    counsel: str = ""
    counsel_attention: str = ""                 # the lawyer the note to counsel is addressed to
    counsel_email: str = ""                     # where the note to counsel is addressed (a draft, never sent)
    board_discussed: str = ""                   # where the board took up the matter ("executive session"), and when if known
    custodian_of_record: str = ""               # the person who keeps the register (the board names one)
    released: date | None = None                # counsel's written release

    def mail_query(self) -> str:
        """The Vault mail query: any of the terms, quoted when they hold a space."""
        return " OR ".join(f'"{t}"' if " " in t else t for t in self.terms)


__all__ = ["LegalHoldSpec"]
