"""Who an email is from, as the association's records knew them on the day it was sent.

An owner writes from a personal address, and a unit changes hands: the owner who wrote in 2024 may have conveyed the
unit in 2025, and the buyer may write before the deed records. So a person is resolved at the message's date:

1. **PayHOA members** (``data/payhoa.db``): the address of a current member gives the units PayHOA links to it, and
   "board member" for an administrator. If the unit's latest deed recorded after the message, the member wrote before
   they owned it: a buyer.
2. **The deed chain** (``data/ownership.db``): a sender PayHOA does not know is matched by display name (first and last
   name, in any order) to the grantees and grantors of each unit's deeds. A grantee owns from the deed's recording to
   the next deed on the parcel. The message then reads as from the owner then, a former owner (after the conveyance),
   or a buyer (before the deed recorded).

A unit is joined to its parcel by address (the tax store's situs address is PayHOA's unit label). The name is used for
matching only and is never stored; a sender neither source knows stays "personal".
"""

from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass
from datetime import date
from pathlib import Path

_STOP = {"TRUST", "TRUSTEE", "TRUSTEES", "FAMILY", "LIVING", "REVOCABLE", "THE", "OF", "AND", "LLC", "INC", "ETAL", "ET", "AL",
         "JR", "SR", "II", "III", "HUSBAND", "WIFE", "A", "AN"}


def _tokens(name: str) -> set[str]:
    return {t for t in re.findall(r"[A-Z]{2,}", name.upper()) if t not in _STOP}


@dataclass(frozen=True)
class Holding:
    unit: str
    names: tuple[frozenset[str], ...]
    start: date | None
    end: date | None


class PartyResolver:
    def __init__(self, data_dir: Path) -> None:
        data_dir = Path(data_dir)
        self.members: dict[str, tuple[str, list[str]]] = {}
        self.latest_deed: dict[str, date] = {}
        self.holdings: list[Holding] = []
        apn_unit = self._parcels(data_dir)
        self._load_members(data_dir)
        self._load_chain(data_dir, apn_unit)

    @staticmethod
    def _parcels(data_dir: Path) -> dict[str, str]:
        path = data_dir / "tax.db"
        if not path.is_file():
            return {}
        conn = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
        try:
            return {re.sub(r"\D", "", apn): address.split(" SACRAMENTO")[0].strip().upper()
                    for apn, address in conn.execute("SELECT apn, address FROM accounts")}
        finally:
            conn.close()

    def _load_members(self, data_dir: Path) -> None:
        path = data_dir / "payhoa.db"
        if not path.is_file():
            return
        conn = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
        try:
            units = {int(i): label.upper() for i, label in conn.execute("SELECT id, label FROM units")}
            for email, is_admin, raw in conn.execute("SELECT email, is_admin, raw_json FROM people WHERE email <> ''"):
                try:
                    owners = json.loads(raw or "{}").get("owners") or []
                except json.JSONDecodeError:
                    owners = []
                labels = sorted({units.get(int(o.get("unitId") or 0), "") for o in owners if not o.get("deletedAt")} - {""})
                self.members[email.strip().lower()] = ("board member" if is_admin else "member", labels)
        finally:
            conn.close()

    def _load_chain(self, data_dir: Path, apn_unit: dict[str, str]) -> None:
        path = data_dir / "ownership.db"
        if not path.is_file():
            return
        conn = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
        try:
            rows = conn.execute("SELECT apn, recorded, grantees FROM chain WHERE recorded <> '' ORDER BY apn, recorded").fetchall()
        finally:
            conn.close()
        by_apn: dict[str, list[tuple[date, str]]] = {}
        for apn, recorded, grantees in rows:
            try:
                by_apn.setdefault(re.sub(r"\D", "", apn), []).append((date.fromisoformat(recorded[:10]), grantees or ""))
            except ValueError:
                continue
        for apn, deeds in by_apn.items():
            unit = apn_unit.get(apn)
            if not unit:
                continue
            self.latest_deed[unit] = deeds[-1][0]
            for n, (recorded, grantees) in enumerate(deeds):
                end = deeds[n + 1][0] if n + 1 < len(deeds) else None
                names = tuple(frozenset(_tokens(line)) for line in grantees.splitlines() if len(_tokens(line)) >= 2)
                if names:
                    self.holdings.append(Holding(unit, names, recorded, end))

    def resolve(self, address: str, display_name: str, at: date | None) -> str:
        """The sender as the records knew them on ``at``: an owner, a former owner, a buyer, a board member, or "personal"."""
        member = self.members.get(address.strip().lower())
        if member is not None:
            role, units = member
            if role == "board member":
                return role
            labels = []
            for unit in units:
                recorded = self.latest_deed.get(unit)
                labels.append(f"buyer of {unit}" if at and recorded and at < recorded else f"owner of {unit}")
            return ", ".join(labels) if labels else "member"
        tokens = _tokens(display_name)
        if len(tokens) < 2 or at is None:
            return "personal"
        found = []
        for h in self.holdings:
            if not any(len(name & tokens) >= 2 for name in h.names):
                continue
            if h.start and at < h.start:
                found.append((2, f"buyer of {h.unit}"))
            elif h.end and at >= h.end:
                found.append((1, f"former owner of {h.unit} (conveyed {h.end.isoformat()})"))
            else:
                found.append((0, f"owner of {h.unit}"))
        if not found:
            return "personal"
        best = min(r for r, _ in found)
        return ", ".join(sorted({label for r, label in found if r == best}))


__all__ = ["PartyResolver"]
