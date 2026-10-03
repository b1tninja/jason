import json
from datetime import date

import pytest

from jason.tasks import records_requests as store


def test_deadlines_each_class():
    # Friday 2026-10-02: five business days is the next Friday, ten the one after; thirty calendar days is November 1.
    stages = {s["key"]: s for s in store.deadlines("2026-10-02", ["membership_list", "minutes", "tax_return"], years=[2026, 2024])}
    assert stages["received"]["done"] is True
    assert stages["membershipList"]["date"] == "2026-10-09" and stages["membershipList"]["authority"] == "CIV 5210(b)"
    assert stages["currentYear"]["date"] == "2026-10-16" and stages["currentYear"]["authority"] == "CIV 5210(b)(1)"
    assert stages["priorYears"]["date"] == "2026-11-01" and stages["priorYears"]["authority"] == "CIV 5210(b)(2)"
    # Only the list: only its stage. Only prior years: no current-year stage. No years given: the current year.
    assert [s["key"] for s in store.deadlines("2026-10-02", ["membership_list"])] == ["received", "membershipList"]
    assert [s["key"] for s in store.deadlines("2026-10-02", ["minutes"], years=[2025])] == ["received", "priorYears"]
    assert [s["key"] for s in store.deadlines("2026-10-02", ["minutes"])] == ["received", "currentYear"]
    assert store.add_business_days(date(2026, 10, 3), 1) == date(2026, 10, 5)  # a Saturday request: Monday is day one
    assert "Monday through Friday" in store.add_business_days.__doc__


def test_open_decide_roundtrip(tmp_path):
    r = store.open_request(tmp_path, "2026-10-02", "Unit 12", "email", ["membership_list", "minutes"],
                           purpose="to contact owners about the roof vote", by="Manager")
    assert r.id == "2026-10-02--unit-12" and r.membershipList is True and r.purpose == "to contact owners about the roof vote"
    assert r.history == [f"{r.recorded[:10]}: received via email"]
    assert store.standing(r, date(2026, 10, 5)) == "open"
    assert store.standing(r, date(2026, 10, 10)) == "overdue"  # the list's five business days ran out on the 9th
    again = store.open_request(tmp_path, "2026-10-02", "Unit 12", "mail", ["minutes"])
    assert again.id == "2026-10-02--unit-12-2" and again.membershipList is False
    d = store.decide(tmp_path, r.id, purposeAdequate=True, withheld=[{"record": "minutes", "reason": "executive session minutes, CIV 4935"}],
                     by="Manager")
    assert d.decisions.purposeAdequate is True and d.history[-2].endswith("purpose (undecided) -> adequate (CIV 5225)")
    assert d.history[-1].endswith("withheld 1 record kind(s) (CIV 5215)")
    d = store.decide(tmp_path, r.id, producedOn="2026-10-08", inspectedOrCopies="copies", feeCents=1250, note="mailed")
    assert store.standing(d, date(2026, 12, 1)) == "produced"
    raw = json.loads((tmp_path / "records-requests" / "requests.json").read_text())
    assert raw["requests"][0]["decisions"]["feeCents"] == 1250 and raw["requests"][0]["decisions"]["producedOn"] == "2026-10-08"
    assert store.get(tmp_path, r.id).decisions.inspectedOrCopies == "copies"
    out = store.as_dict(store.load(tmp_path)[0], date(2026, 12, 1))
    assert out["standing"] == "produced" and out["dueBy"] == "2026-10-09" and out["citations"]["membership_list"] == "CIV 5200(a)(9)"


def test_refusals(tmp_path):
    with pytest.raises(ValueError):
        store.open_request(tmp_path, "soon", "Unit 1", "email", ["minutes"])
    with pytest.raises(ValueError):
        store.open_request(tmp_path, "2026-10-02", "", "email", ["minutes"])
    with pytest.raises(ValueError):
        store.open_request(tmp_path, "2026-10-02", "Unit 1", "fax", ["minutes"])
    with pytest.raises(ValueError):
        store.open_request(tmp_path, "2026-10-02", "Unit 1", "email", ["diary"])
    with pytest.raises(ValueError):
        store.open_request(tmp_path, "2026-10-02", "Unit 1", "email", [])
    r = store.open_request(tmp_path, "2026-10-02", "Unit 1", "email", ["minutes"])
    with pytest.raises(ValueError):  # no membership list asked, so 5225 adequacy does not arise
        store.decide(tmp_path, r.id, purposeAdequate=True)
    with pytest.raises(ValueError):
        store.decide(tmp_path, r.id, withheld=[{"record": "minutes", "reason": ""}])
    with pytest.raises(ValueError):
        store.decide(tmp_path, r.id, withheld=[{"record": "diary", "reason": "x"}])
    with pytest.raises(ValueError):
        store.decide(tmp_path, r.id, inspectedOrCopies="fax")
    with pytest.raises(ValueError):
        store.decide(tmp_path, r.id, feeCents=-1)
    with pytest.raises(ValueError):
        store.decide(tmp_path, r.id, feeCents=True)
    with pytest.raises(ValueError):
        store.decide(tmp_path, r.id, producedOn="later")
    with pytest.raises(ValueError):
        store.decide(tmp_path, r.id, purpose="rewritten")  # the member's words are not a decision field
    with pytest.raises(KeyError):
        store.decide(tmp_path, "nope", note="n")
    with pytest.raises(KeyError):
        store.get(tmp_path, "nope")


def test_loader_standing_and_write(tmp_path, monkeypatch):
    import jason.mcp.county as county
    from jason.web.extra import records_requests as web

    monkeypatch.setattr(county, "_data_dir", lambda _d: tmp_path)
    monkeypatch.setattr(county, "records_inventory", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("no shelf")))
    out = web.records_requests({"today": "2026-10-05"})
    assert out["count"] == 0 and out["requests"] == [] and "unavailable" in out["note"]
    assert {k["record"] for k in out["kinds"]} == {r.value for r in store.AssociationRecord}
    assert next(k for k in out["kinds"] if k["record"] == "membership_list")["citation"] == "CIV 5200(a)(9)"
    assert any("does not hand the list" in c for c in out["caveats"])

    opened = web.write("new", {"receivedOn": "2026-10-02", "unit": "Unit 12", "via": "form", "records": ["membership_list", "minutes"],
                               "purpose": "roof vote", "by": "Manager"})
    assert opened["id"] == "2026-10-02--unit-12" and [s["key"] for s in opened["stages"]] == ["received", "membershipList", "currentYear"]
    assert web.records_requests({"today": "2026-10-05"})["requests"][0]["standing"] == "open"
    assert web.records_requests({"today": "2026-10-12"})["counts"] == {"overdue": 1}
    one = web.records_requests({"id": opened["id"], "today": "2026-10-12"})
    assert one["request"]["standing"] == "overdue" and one["request"]["dueBy"] == "2026-10-09"

    decided = web.write(opened["id"], {"purposeAdequate": False, "producedOn": "2026-10-08", "inspectedOrCopies": "inspection", "by": "Manager"})
    assert decided["decisions"]["purposeAdequate"] is False and decided["standing"] == "produced"
    assert web.records_requests({"today": "2026-10-12"})["counts"] == {"produced": 1}
    with pytest.raises(ValueError):
        web.write(opened["id"], {"feeCents": "ten"})
    with pytest.raises(KeyError):
        web.write("missing", {"note": "n"})
    with pytest.raises(KeyError):
        web.records_requests({"id": "missing"})

    # With the shelf readable, the kinds carry its meaning and retention.
    monkeypatch.setattr(county, "records_inventory", lambda *a, **k: {"records": [{"record": "minutes", "meaning": "what the board did", "retention": "permanent", "files": 3, "gap": ""}]})
    kinds = {k["record"]: k for k in web.records_requests({})["kinds"]}
    assert kinds["minutes"]["meaning"] == "what the board did" and kinds["minutes"]["files"] == 3 and kinds["tax_return"]["files"] is None
