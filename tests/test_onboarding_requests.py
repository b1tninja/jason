import json

import pytest

from jason.tasks import onboarding_requests as ob


def test_catalog_names_only_real_records_deliveries_and_kinds():
    from jason.community.symbols import AssociationRecord, DeveloperDelivery, DocumentKind

    records = {r.value for r in AssociationRecord}
    deliveries = {d.value for d in DeveloperDelivery}
    kinds = {k.value for k in DocumentKind}
    assert len(ob.CATALOG) == len(ob.CATALOG_KEYS), "keys are unique"
    for c in ob.CATALOG:
        assert c.title and c.group and c.holders
        assert not c.record or c.record in records, (c.key, c.record)
        assert not c.delivery or c.delivery in deliveries, (c.key, c.delivery)
        for k in c.kinds:
            assert k in kinds, (c.key, k)
    covered = {c.record for c in ob.CATALOG if c.record}
    assert {"governing_documents", "financial_disclosure", "minutes", "membership_list", "executed_contract"} <= covered


def test_update_roundtrip_and_refusals(tmp_path):
    r = ob.update(tmp_path, "declaration", status="asked", asked_of="the prior manager", asked_on="2026-10-03")
    assert r.history == ["2026-10-03: not asked -> asked"] or r.history[0].endswith("not asked -> asked")
    r = ob.update(tmp_path, "declaration", status="received", received_on="2026-10-10", filed="Governing Documents/CC&Rs.pdf")
    assert ob.load(tmp_path)["declaration"].filed.endswith("CC&Rs.pdf")
    with pytest.raises(KeyError):
        ob.update(tmp_path, "nope", status="asked")
    with pytest.raises(ValueError):
        ob.update(tmp_path, "bylaws", status="lost")
    with pytest.raises(ValueError):
        ob.update(tmp_path, "bylaws", status="not applicable")
    ok = ob.update(tmp_path, "bylaws", status="not applicable", reason="unincorporated; no bylaws exist")
    assert ok.reason.startswith("unincorporated")
    with pytest.raises(ValueError):
        ob.update(tmp_path, "bylaws", title="x")
    assert json.loads((tmp_path / "onboarding" / "requests.json").read_text())["requests"][0]["key"] == "declaration"


def test_request_letter_groups_and_cites():
    items = [c for c in ob.catalog_dicts() if c["key"] in ("declaration", "budget")]
    text = ob.request_letter(items, association="Example Owners Association", to="the board")
    assert text.startswith("# Records and information requested for Example Owners Association")
    assert "## Governing documents and the developer file" in text and "## Financial" in text
    assert "(CIV 4135, 5200(a)(11))" in text and "Usually held by the board, the prior manager, the county." in text
    assert "demand" in text


def test_api_onboarding_route(tmp_path):
    from jason.web.app import create_app

    def writer(key, body):
        if key == "nope":
            raise KeyError(key)
        if body.get("status") == "lost":
            raise ValueError("status")
        return {"key": key, **body}

    c = create_app(tmp_path, {}, board_writer=None, canvas_writer=None, decision_writer=None, request_writer=writer, owner_info_writer=None, hearing_writer=None, extra_writes=False).test_client()
    assert c.post("/api/onboarding/declaration", json={"status": "asked"}).json == {"key": "declaration", "status": "asked"}
    assert c.post("/api/onboarding/nope", json={"status": "asked"}).status_code == 404
    assert c.post("/api/onboarding/x", json={"status": "lost"}).status_code == 400
    assert c.get("/api/health").json["writes"] == ["onboarding"]
