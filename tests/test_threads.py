"""Email threads: who a sender was on the day they wrote, and whose move it is."""

from __future__ import annotations

import json
import sqlite3
from datetime import date

from jason.tasks.parties import PartyResolver
from jason.tasks.threads import status_of


def _stores(tmp_path) -> None:
    tax = sqlite3.connect(tmp_path / "tax.db")
    tax.execute("CREATE TABLE accounts (apn TEXT, address TEXT)")
    tax.executemany("INSERT INTO accounts VALUES (?, ?)", [("201-1170-024-0004", "3048 ENCHANTED WALK SACRAMENTO, CA 95835"),
                                                         ("201-1170-027-0016", "5651 WHIMSICAL LN SACRAMENTO, CA 95835")])
    tax.commit()
    tax.close()
    payhoa = sqlite3.connect(tmp_path / "payhoa.db")
    payhoa.execute("CREATE TABLE units (id INTEGER, label TEXT)")
    payhoa.execute("CREATE TABLE people (email TEXT, is_admin INTEGER, raw_json TEXT)")
    payhoa.executemany("INSERT INTO units VALUES (?, ?)", [(1, "3048 ENCHANTED WALK"), (2, "5651 WHIMSICAL LN")])
    payhoa.executemany("INSERT INTO people VALUES (?, ?, ?)", [
        ("gina@example.org", 0, json.dumps({"owners": [{"unitId": 1, "deletedAt": None}]})),
        ("board@example.org", 1, json.dumps({"owners": [{"unitId": 2, "deletedAt": None}]})),
    ])
    payhoa.commit()
    payhoa.close()
    chain = sqlite3.connect(tmp_path / "ownership.db")
    chain.execute("CREATE TABLE chain (apn TEXT, recorded TEXT, grantees TEXT)")
    chain.executemany("INSERT INTO chain VALUES (?, ?, ?)", [
        ("20111700240004", "2019-05-01", "ROE KAREN"),
        ("20111700240004", "2026-08-12", "FERN GINA"),
    ])
    chain.commit()
    chain.close()


def test_a_sender_is_who_the_records_knew_on_the_day(tmp_path) -> None:
    _stores(tmp_path)
    r = PartyResolver(tmp_path)
    assert r.resolve("gina@example.org", "Gina Fern", date(2026, 9, 1)) == "owner of 3048 ENCHANTED WALK"
    # A current member writing before the deed recorded was the buyer.
    assert r.resolve("gina@example.org", "Gina Fern", date(2026, 7, 20)) == "buyer of 3048 ENCHANTED WALK"
    assert r.resolve("board@example.org", "", date(2026, 9, 1)) == "board member"
    # PayHOA no longer knows the prior owner; the deed chain does, by name.
    assert r.resolve("karen@example.org", "Karen Roe", date(2026, 3, 1)) == "owner of 3048 ENCHANTED WALK"
    assert r.resolve("karen@example.org", "Karen Roe", date(2026, 9, 1)) == "former owner of 3048 ENCHANTED WALK (conveyed 2026-08-12)"
    assert r.resolve("x@example.org", "Somebody Else", date(2026, 9, 1)) == "personal"


def _m(direction: str, at: str, parties=("title.com",), people=(), subject="Re: request") -> dict:
    return {"direction": direction, "at": at, "parties": list(parties), "people": [list(p) for p in people], "subject": subject}


def test_the_last_message_decides_whose_move_it_is() -> None:
    today = date(2026, 9, 29)
    assert status_of([_m("in", "2026-09-20T00:00:00+00:00")], today) == ("awaiting us", 9)
    assert status_of([_m("in", "2026-09-01T00:00:00+00:00"), _m("out", "2026-09-02T00:00:00+00:00")], today)[0] == "awaiting them"
    assert status_of([_m("in", "2026-09-01T00:00:00+00:00", parties=("association",))], today)[0] == "internal"
    notice = _m("in", "2026-09-01T00:00:00+00:00", people=(("", "noreply@vitesse.io", "from"),), subject="Your payment")
    assert status_of([notice], today)[0] == "notice"
    asks = _m("in", "2026-09-01T00:00:00+00:00", people=(("", "noreply@vitesse.io", "from"),), subject="Action Required: eCheck")
    assert status_of([asks], today)[0] == "awaiting us"
