import json

import pytest

from jason.tasks import hearing_decisions as hd


def _seed(tmp_path):
    (tmp_path / "zoom").mkdir()
    (tmp_path / "zoom" / "hearings.json").write_text(json.dumps({"hearings": [
        {"address": "123 Main St #12", "start": "2026-10-20T18:00:00-07:00", "noticeBy": "2026-10-10", "decisionByIfHeld": "2026-11-03"},
    ]}))


def test_record_decision_onto_the_row(tmp_path):
    _seed(tmp_path)
    key = hd.key_of(hd.load(tmp_path)[0])
    assert key == "2026-10-20|123-main-st-12"
    row = hd.record(tmp_path, key, findings="The enclosure is a violation of section 4.2; a $50 fine, waived if removed by December 1.", decided_on="2026-10-20", by="Secretary")
    assert row["decision"]["noticeDueBy"] == "2026-11-03" and row["decision"]["history"][0].endswith("recorded by Secretary")
    again = hd.record(tmp_path, key, findings="Amended: no fine.", decided_on="2026-10-21", by="Secretary")
    assert again["decision"]["noticeDueBy"] == "2026-11-04" and "re-recorded" in again["decision"]["history"][-1]
    assert json.loads((tmp_path / "zoom" / "hearings.json").read_text())["hearings"][0]["decision"]["findings"] == "Amended: no fine."
    with pytest.raises(ValueError):
        hd.record(tmp_path, key, findings="  ", decided_on="2026-10-20", by="S")
    with pytest.raises(ValueError):
        hd.record(tmp_path, key, findings="x", decided_on="2026-10-20", by="")
    with pytest.raises(ValueError):
        hd.record(tmp_path, key, findings="x", decided_on="2026-10-01", by="S")
    with pytest.raises(KeyError):
        hd.record(tmp_path, "2026-01-01|nope", findings="x", decided_on="2026-10-20", by="S")


def test_api_hearing_route(tmp_path):
    from jason.web.app import create_app

    def writer(key, body):
        if key == "nope":
            raise KeyError(key)
        if not body.get("by"):
            raise ValueError("by")
        return {"key": key, "decision": body}

    c = create_app(tmp_path, {}, board_writer=None, canvas_writer=None, decision_writer=None, request_writer=None, owner_info_writer=None, hearing_writer=writer, extra_writes=False).test_client()
    assert c.post("/api/hearings/2026-10-20|123-main-st-12", json={"findings": "f", "decidedOn": "2026-10-20", "by": "S"}).json["key"] == "2026-10-20|123-main-st-12"
    assert c.post("/api/hearings/nope", json={"by": "S"}).status_code == 404
    assert c.post("/api/hearings/x", json={}).status_code == 400
    assert c.get("/api/health").json["writes"] == ["hearings"]
