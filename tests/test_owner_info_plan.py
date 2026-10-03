from dataclasses import dataclass, field

import pytest

from jason.tasks import owner_info_plan as plan


@dataclass
class W:
    kind: str
    target: int
    label: str
    value: str
    why: str


@dataclass
class T:
    submission_id: int
    unit: str
    name: str
    membership_id: int
    left: list = field(default_factory=list)


def test_save_confirm_status_roundtrip(tmp_path):
    assert plan.status(tmp_path)["found"] is False
    writes = [W("member tag +", 11, "unit 12 owner", "notice: email", "answered this cycle"), W("unit tag -", 5, "unit 5", "paper statements", "election on file")]
    plan.save_plan(tmp_path, summary={"currentOwners": 2}, writes=writes, to_complete=[T(901, "12", "Owner Twelve", 11, ["a tag write not yet made"])], owners=[])
    s = plan.status(tmp_path)
    assert s["found"] and s["pending"] == 2 and s["allConfirmed"] is False and s["command"] == plan.APPLY
    assert s["writes"][0]["key"] == "member tag +|11|notice: email" and s["toComplete"][0]["submissionId"] == 901
    with pytest.raises(ValueError):
        plan.confirm(tmp_path, s["writes"][0]["key"], by="  ")
    with pytest.raises(KeyError):
        plan.confirm(tmp_path, "nope|1|x", by="A")
    plan.confirm(tmp_path, s["writes"][0]["key"], by="Secretary")
    plan.confirm(tmp_path, s["writes"][1]["key"], by="Secretary")
    s = plan.status(tmp_path)
    assert s["allConfirmed"] is True and s["writes"][0]["confirmedBy"] == "Secretary"
    plan.confirm(tmp_path, s["writes"][1]["key"], by="Secretary", confirmed=False)
    assert plan.status(tmp_path)["pending"] == 1
    plan.save_plan(tmp_path, summary={}, writes=[], to_complete=[], owners=[], written=True)
    s = plan.status(tmp_path)
    assert s["written"] is True and s["command"] == "" and s["allConfirmed"] is False


def test_api_owner_info_route(tmp_path):
    from jason.web.app import create_app

    def writer(key, body):
        if key == "nope":
            raise KeyError(key)
        if not body.get("by"):
            raise ValueError("by")
        return {"found": True, "pending": 0, "key": key}

    c = create_app(tmp_path, {}, board_writer=None, canvas_writer=None, decision_writer=None, request_writer=None, owner_info_writer=writer, hearing_writer=None, extra_writes=False).test_client()
    assert c.post("/api/owner-info/member tag +|11|notice: email", json={"by": "S"}).json["key"] == "member tag +|11|notice: email"
    assert c.post("/api/owner-info/nope", json={"by": "S"}).status_code == 404
    assert c.post("/api/owner-info/x", json={}).status_code == 400
    assert c.get("/api/health").json["writes"] == ["owner-info"]
