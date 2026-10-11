"""The investigation's outcome and its routes (``jason.tasks.bill_outcomes``, ``jason.web.extra.bill_investigation``): a person's
word, append only, in the signer's name; the card's read held back from an office that does not open P2. Made-up data in
tmp_path; nothing is reached.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
import webclient

from jason.tasks import bill_outcomes as out


def test_an_outcome_names_who_and_a_receipt_or_bill_names_its_record(tmp_path):
    with pytest.raises(ValueError, match="name who"):
        out.record(tmp_path, 1, "escalated", by=" ")
    with pytest.raises(ValueError, match="outcome is one of"):
        out.record(tmp_path, 1, "paid", by="Pat Example")
    with pytest.raises(ValueError, match="names the record"):
        out.record(tmp_path, 1, "attached-receipt-only", by="Pat Example")
    with pytest.raises(ValueError, match="not words"):
        out.record(tmp_path, 1, "attached-bill", by="Pat Example", doc="the tax bill")


def test_outcomes_are_append_only_and_the_last_one_stands(tmp_path):
    out.record(tmp_path, 7, "waiting-for-mail", by="Pat Example", now="2026-10-08T10:00:00+00:00")
    out.record(tmp_path, 7, "attached-receipt-only", by="Lee President", doc="gmail:t1", note="x" * 400,
               now="2026-10-10T10:00:00+00:00")
    out.record(tmp_path, 8, "not-our-bill", by="Pat Example")
    mine = out.history(tmp_path, 7)
    assert [r["outcome"] for r in mine] == ["waiting-for-mail", "attached-receipt-only"]
    assert mine[1]["by"] == "Lee President" and mine[1]["on"] == "2026-10-10" and len(mine[1]["note"]) == 300
    assert len(out.load(tmp_path)) == 3


@pytest.fixture
def app(tmp_path, monkeypatch):
    from jason.web.app import create_app
    from jason.web.extra import bill_investigation as route

    p = tmp_path / "payhoa" / "transactions.json"
    p.parent.mkdir(parents=True)
    p.write_text(json.dumps({"syncedAt": "2026-10-09T00:00:00+00:00", "transactions": [
        {"id": 1, "amount": 36357, "description": "ACH EXAMPLE COUNTY TAX", "transactionDate": "2026-10-07",
         "approved": False, "attachments": []}]}), encoding="utf-8")
    g = tmp_path / "gmail" / "correspondence.json"
    g.parent.mkdir()
    g.write_text(json.dumps({"syncedAt": "x", "messages": [{"subject": "You sent $363.57", "at": "2026-10-07", "threadId": "t1"}]}),
                 encoding="utf-8")
    monkeypatch.setattr("jason.mcp.county._data_dir", lambda d: tmp_path)
    monkeypatch.setattr("jason.tasks.library.load", lambda d: [])
    monkeypatch.setattr("jason.tasks.mail.load_items", lambda d: {})
    monkeypatch.setattr("jason.tasks.invoice_review.vendor_ledgers", lambda d, c: {})
    monkeypatch.setattr("jason.community.community", lambda: SimpleNamespace(
        payee_rules=lambda: (), vendor_portals=lambda: (), transaction_rules=lambda: ()))
    dist = tmp_path / "dist"
    dist.mkdir()
    return create_app(dist, {"bill-investigation": route.bill_investigation}, approvals_live=None, extra_writes=True,
                      sign_in=webclient.roster_sign_in(dev=True))


def as_(app, name):
    return webclient.sign_in(webclient.client(app), name)


def test_the_card_needs_a_sign_in_and_is_no_owner_view_and_a_bad_tx_is_a_400(app):
    assert webclient.client(app).get("/api/bill-investigation?tx=1").status_code == 401
    assert as_(app, "Pat Example").get("/api/bill-investigation?tx=1&view=owner").status_code == 403
    assert as_(app, "Pat Example").get("/api/bill-investigation?tx=abc").status_code == 400


def test_an_office_that_opens_p2_sees_the_subject_and_the_read_is_logged(app, monkeypatch):
    served = []
    from jason.web import access

    monkeypatch.setattr(access, "served", lambda viewer, level, **k: served.append((viewer.name, level.value, k)))
    card = as_(app, "Pat Example").get("/api/bill-investigation?tx=1").json
    assert card["found"] is True and card["routing"]["payeeClass"] == "unknown"
    assert [c["label"] for c in card["candidates"]] == ["You sent $363.57"]
    assert served == [("Pat Example", "P2", {"address": "api/bill-investigation"})]


def test_an_office_that_does_not_open_p2_sees_no_subject(app):
    card = as_(app, "Ada Admin").get("/api/bill-investigation?tx=1")
    assert card.status_code == 200
    assert [c["label"] for c in card.json["candidates"]] == ["a message whose subject names this amount"]


def test_the_outcome_is_the_signers_and_a_body_naming_someone_else_is_refused(app, tmp_path):
    c = as_(app, "Pat Example")
    assert c.post("/api/write/bill-investigation/1", json={"outcome": "escalated", "by": "Somebody Else"}).status_code == 403
    row = c.post("/api/write/bill-investigation/1", json={"outcome": "waiting-for-mail", "note": "asked the county"})
    assert row.status_code == 200 and row.json["by"] == "Pat Example"
    assert c.post("/api/write/bill-investigation/1", json={"outcome": "paid"}).status_code == 400
    assert c.post("/api/write/bill-investigation/x", json={"outcome": "escalated"}).status_code == 400
    card = c.get("/api/bill-investigation?tx=1").json
    assert [h["outcome"] for h in card["history"]] == ["waiting-for-mail"] and card["outcome"]["note"] == "asked the county"
    assert webclient.client(app).post("/api/write/bill-investigation/1", json={"outcome": "escalated"}).status_code == 401


def test_nobody_records_while_viewing_as_someone_else(app):
    c = as_(app, "Ada Admin")
    with c.session_transaction() as s:
        s["acting"] = {"name": "Pat Example", "role": "treasurer"}
    assert c.post("/api/write/bill-investigation/1", json={"outcome": "escalated"}).status_code in (403, 405)


def test_registered_and_no_owner_source():
    from jason.web.extra.owner_view import OWNER_SOURCES
    from jason.web.sources import EXTRA_LOADERS, EXTRA_WRITERS

    assert "bill-investigation" not in OWNER_SOURCES
    assert EXTRA_LOADERS["bill-investigation"].endswith(":bill_investigation")
    assert EXTRA_WRITERS["bill-investigation"].endswith(":write")
