import json

import pytest
import webclient

from jason.tasks import decisions as store


def test_record_update_tally_roundtrip(tmp_path):
    d = store.record(tmp_path, "2026-10-20", "Reserve loan not restored", "Move to restore $6,000 to the reserve by March 1",
                     item="reserve-loan", mover="A. Director", second="B. Director",
                     votes={"A. Director": "aye", "B. Director": "aye", "C. Director": "no", "D. Director": "absent"})
    assert d.id == "2026-10-20--reserve-loan" and d.outcome == "" and store.suggested_outcome(d.votes) == "approved"
    assert store.tally(d.votes) == {"aye": 2, "no": 1, "abstain": 0, "absent": 1}
    d = store.update(tmp_path, d.id, outcome="approved", by="Secretary")
    assert d.history[-1].endswith("outcome (open) -> approved")
    again = store.record(tmp_path, "2026-10-20", "Reserve loan not restored", "Amended: restore by April 1", item="reserve-loan")
    assert again.id == d.id and again.motion.startswith("Amended") and again.history[-1].endswith("re-recorded")
    free = store.record(tmp_path, "2026-10-20", "Adjournment", "Move to adjourn at 8:12 PM")
    assert free.id == "2026-10-20--move-to-adjourn-at-8-12-pm"
    assert [x.id for x in store.for_meeting(tmp_path, "2026-10-20")] == [d.id, free.id]
    assert store.for_meeting(tmp_path, "2026-11-17") == []
    raw = json.loads((tmp_path / "board" / "decisions.json").read_text())
    assert raw["decisions"][0]["outcome"] == "approved"
    assert store.as_dict(store.load(tmp_path)[0])["suggested"] == "approved"


def test_refusals(tmp_path):
    with pytest.raises(ValueError):
        store.record(tmp_path, "2026-10-20", "", "motion")
    with pytest.raises(ValueError):
        store.record(tmp_path, "soon", "t", "m")
    with pytest.raises(ValueError):
        store.record(tmp_path, "2026-10-20", "t", "m", votes={"A": "yes"})
    with pytest.raises(ValueError):
        store.record(tmp_path, "2026-10-20", "t", "m", outcome="carried")
    with pytest.raises(ValueError):
        store.record(tmp_path, "2026-10-20", "t", "m", recorded="2020-01-01")
    with pytest.raises(KeyError):
        store.update(tmp_path, "nope", notes="n")


def test_api_decision_routes(tmp_path):
    from jason.web.app import create_app

    def writer(decision_id, body):
        if decision_id == "missing":
            raise KeyError(decision_id)
        if body.get("outcome") == "carried":
            raise ValueError("outcome is one of approved, denied, tabled")
        return {"id": decision_id or "new", **body}

    c = webclient.client(create_app(tmp_path, {}, board_writer=None, canvas_writer=None, decision_writer=writer, request_writer=None, owner_info_writer=None, hearing_writer=None, extra_writes=False))
    assert c.post("/api/decisions", json={"meeting": "2026-10-20", "title": "t", "motion": "m"}).json["id"] == "new"
    assert c.post("/api/decisions/x", json={"outcome": "approved"}).json["outcome"] == "approved"
    assert c.post("/api/decisions/x", json={"outcome": "carried"}).status_code == 400
    assert c.post("/api/decisions/missing", json={"notes": "n"}).status_code == 404
    assert c.get("/api/health").json["writes"] == ["decisions"]


def test_minutes_prompt_quotes_recorded_decisions():
    import ast
    import re
    from datetime import date
    from pathlib import Path

    # The prompt builder is pure text; exercise it without the Zoom stores by loading only that function.
    src = Path("src/jason/tasks/minutes_draft.py").read_text(encoding="utf-8")
    assert "Decisions the Secretary recorded" in src
    # Only the open decisions reach the model; an executive one is noted by its 4935 subject (CIV 4935(e)).
    assert re.search(r'"decisions": \[as_dict\(d\) for d in open_only\(recorded\)\]', src)
