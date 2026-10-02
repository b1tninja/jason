"""The association's own collections: the PayHOA ledger read beside the liens it recorded.

The index says whether a notice of delinquent assessment stands; the
ledger says whether the owner still owes. Read together they name the
cases a board acts on: a paid account whose lien was never released
(Civil Code 5685 gives the association 21 days from payment to record the
release), a lien that still secures a debt, and a past-due account with no
lien. The ledger's past-due figure can include late charges, interest, and
fees, which the foreclosure floor in section 5720 leaves out, so the floor
is reported as a question for the board, never as a finding. Jason does not
send an account to a collection agency and does not start a foreclosure.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date
from enum import Enum
from pathlib import Path
from typing import Any

from jason.community.filings import Process

# Civil Code 5720(b): below this, not counting accelerated assessments, late charges, fees, costs, or interest,
# an assessment debt cannot be collected by foreclosure; (c)(1) lifts the floor after 12 months of delinquency.
FORECLOSURE_FLOOR_CENTS = 180_000
TWELVE_MONTHS_DAYS = 365


@dataclass(frozen=True)
class LedgerBalance:
    address: str
    balance_cents: int
    past_due_cents: int
    synced: str


def load_ledger(path: Path) -> dict[str, LedgerBalance]:
    """The PayHOA catalog's balance per unit, keyed by the upper-cased street address. Read-only."""
    if not Path(path).is_file():
        return {}
    conn = sqlite3.connect(f"file:{Path(path).as_posix()}?mode=ro", uri=True)
    try:
        rows = conn.execute("SELECT address_line1, label, balance, past_due_balance, synced_at FROM units").fetchall()
    finally:
        conn.close()
    found: dict[str, LedgerBalance] = {}
    for address, label, balance, past_due, synced in rows:
        key = " ".join(str(address or label or "").upper().split())
        if key:
            found[key] = LedgerBalance(key, int(balance or 0), int(past_due or 0), str(synced or ""))
    return found


class CollectionStanding(Enum):
    RELEASE_DUE = "the ledger shows the account paid, and the association's lien is still of record; record the release within 21 days of payment (Civil Code 5685)"
    LIEN_SECURES_DEBT = "the association's lien stands and the ledger shows a past-due balance"
    OWED_NO_LIEN = "the ledger shows a past-due balance and no lien of the association's stands"
    CREDIT = "the ledger shows a credit"


@dataclass(frozen=True)
class CollectionRow:
    apn: str
    address: str
    owners: tuple[str, ...]
    standing: CollectionStanding
    balance_cents: int
    past_due_cents: int
    lien_number: str = ""
    lien_recorded: date | None = None
    lien_status: str = ""
    lien_days: int | None = None

    @property
    def next_step(self) -> str:
        """What the statute requires before the board's next move; the move itself is the board's."""
        if self.standing is CollectionStanding.RELEASE_DUE:
            return "record the release, or a notice of rescission, and send the owner a copy (Civil Code 5685(a))"
        if self.standing is CollectionStanding.OWED_NO_LIEN:
            return (
                "a lien needs the pre-lien notice by certified mail at least 30 days before recording (Civil Code 5660) and the "
                "board's majority vote in an open meeting, recorded in the minutes (Civil Code 5673); whether to proceed is the board's"
            )
        return ""

    @property
    def floor_question(self) -> str:
        """What section 5720 lets the board ask about foreclosure; the ledger cannot answer it alone."""
        if self.standing is not CollectionStanding.LIEN_SECURES_DEBT:
            return ""
        if self.lien_days is not None and self.lien_days > TWELVE_MONTHS_DAYS:
            return "the lien is over a year old, so the assessments it secures are likely more than 12 months delinquent and the $1,800 floor may not apply (Civil Code 5720(c)(1)); confirm on the ledger"
        if self.past_due_cents >= FORECLOSURE_FLOOR_CENTS:
            return "the past-due balance is at least $1,800, but it may include late charges, interest, and fees the floor excludes (Civil Code 5720(b)); confirm the assessments alone"
        return "under $1,800 past due and under a year: foreclosure is barred (Civil Code 5720(b)); small claims or a civil action remain"

    def as_dict(self) -> dict[str, Any]:
        return {
            "apn": self.apn, "address": self.address, "owners": list(self.owners), "standing": self.standing.name, "meaning": self.standing.value,
            "balanceCents": self.balance_cents, "pastDueCents": self.past_due_cents, "lien": self.lien_number,
            "lienRecorded": self.lien_recorded.isoformat() if self.lien_recorded else "", "lienStatus": self.lien_status,
            "lienDays": self.lien_days, "floorQuestion": self.floor_question, "nextStep": self.next_step,
        }


def collections(histories, ledger: dict[str, LedgerBalance], *, today: date | None = None) -> tuple[CollectionRow, ...]:
    """One row per unit with an open lien of the association's on its current owner, a past-due balance, or a credit."""
    day = today or date.today()
    rows: list[CollectionRow] = []
    for item in histories:
        if item.association:
            continue
        balance = ledger.get(" ".join(item.address.upper().split()))
        ours = [
            lien for lien in item.liens
            if lien.community and lien.encumbrance.process is Process.ASSESSMENT_LIEN and lien.encumbrance.status != "closed"
            and any(_same(lien.owner, name) for name in item.owners)
        ]
        lien = ours[-1] if ours else None
        e = lien.encumbrance if lien else None
        owed = balance.past_due_cents if balance else 0
        common = dict(
            apn=item.apn, address=item.address, owners=tuple(item.owners),
            balance_cents=balance.balance_cents if balance else 0, past_due_cents=owed,
            lien_number=e.opened.number if e else "", lien_recorded=e.opened.recorded if e else None,
            lien_status=e.status if e else "", lien_days=(day - e.opened.recorded).days if e and e.opened.recorded else None,
        )
        if e is not None and balance is not None and balance.balance_cents <= 0:
            rows.append(CollectionRow(standing=CollectionStanding.RELEASE_DUE, **common))
        elif e is not None and owed > 0:
            rows.append(CollectionRow(standing=CollectionStanding.LIEN_SECURES_DEBT, **common))
        elif e is None and owed > 0:
            rows.append(CollectionRow(standing=CollectionStanding.OWED_NO_LIEN, **common))
        elif balance is not None and balance.balance_cents < 0:
            rows.append(CollectionRow(standing=CollectionStanding.CREDIT, **common))
    order = {standing: index for index, standing in enumerate(CollectionStanding)}
    rows.sort(key=lambda row: (order[row.standing], -row.past_due_cents, row.address))
    return tuple(rows)


def _same(left: str, right: str) -> bool:
    from jason.community.filings import same_party

    return same_party(left, right)
