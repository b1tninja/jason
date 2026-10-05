"""The read side of facts, a unit's record, and the loss packet, over a made-up community and a made-up shelf."""

import json
from types import SimpleNamespace

import pytest

from jason.community.facts import Fact, FactScope, FactStatus, ScopeKind
from jason.community.loss_packet import LadderStep, OpenQuestion
from jason.community.unit_record import ComponentKind, OriginalSpec, UnitCoverage
from jason.tasks import unit_records_view as v


def _community(**over):
    facts = (
        Fact("flooring", "Plan A floors are carpet.", ("finishes",), FactScope(ScopeKind.PLAN, "A"), FactStatus.ASSUMED),
        Fact("manual", "The owner's manual is on file.", ("documents",), FactScope(ScopeKind.COMMUNITY), FactStatus.DOCUMENTED,
             answers=("Where is the manual?",)),
    )
    base = dict(
        facts=lambda: facts,
        original_specs=lambda: (OriginalSpec("A", "kitchen faucet", ComponentKind.PLUMBING_FIXTURE, "chrome", "file:specs/a.md"),),
        unit_coverage=lambda: UnitCoverage((ComponentKind.PLUMBING_FIXTURE,), (), (), (), "q1", ""),
        open_questions=lambda: (OpenQuestion("q1", "Does the policy list fixtures?", "agent"),),
        loss_ladder=lambda: (LadderStep(1, "What is the item?", ("decl 8.1(a)(i)",), ("q1",)),
                             LadderStep(3, "Is the casualty insured?", ("policy 1",)),
                             LadderStep(5, "What is the deductible?", ("rule 9",))),
        deductible_policy=lambda: None,
    )
    base.update(over)
    return SimpleNamespace(**base)


def test_facts_are_filtered_by_topic_words_and_status_and_counted_by_plan(tmp_path):
    c = _community()
    everything = v.facts_view(tmp_path, c)
    assert everything["found"] and everything["total"] == 2 and everything["topics"] == ["documents", "finishes"]
    assert [f["key"] for f in v.facts_view(tmp_path, c, topic="finishes")["facts"]] == ["flooring"]
    assert [f["key"] for f in v.facts_view(tmp_path, c, q="manual")["facts"]] == ["manual"]
    assert [f["key"] for f in v.facts_view(tmp_path, c, q="where is")["facts"]] == ["manual"]
    assert [f["key"] for f in v.facts_view(tmp_path, c, status="assumed")["facts"]] == ["flooring"]
    assert everything["coverage"] == [{"plan": "A", "documented": 0, "reported": 0, "assumed": 1}]


def test_no_facts_is_a_miss_with_a_note(tmp_path):
    assert v.facts_view(tmp_path, _community(facts=lambda: ()))["found"] is False


def _write_entries(tmp_path, unit, rows):
    from jason.community.profile import profile_name

    folder = tmp_path / profile_name() / "units" / unit
    folder.mkdir(parents=True)
    (folder / "entries.json").write_text(json.dumps(rows), encoding="utf-8")


ENTRY = dict(id="e1", unit="7", component="kitchen faucet", kind="plumbing fixture", what="touchless faucet", status="upgrade",
             visibility="shared", by="owner", at="2099-01-01")


def test_a_unit_with_a_plan_shows_its_components_with_both_readings_and_hides_private_entries(tmp_path):
    _write_entries(tmp_path, "7", [ENTRY, {**ENTRY, "id": "e2", "visibility": "private"}])
    c = _community()
    out = v.unit_record_view(tmp_path, c, "7", plan="A")
    assert out["planMatched"] is True and out["privateHeld"] == 1
    row = out["components"][0]
    assert row["component"] == "kitchen faucet" and row["status"] == "upgrade"
    assert row["declaration"]["points"] and row["policy"]["points"]
    assert len(row["entries"]) == 1 and "private" not in json.dumps(row["entries"])
    assert "decides coverage" in out["caveat"]
    owner = v.unit_record_view(tmp_path, c, "7", plan="A", owner=True)
    assert owner["privateHeld"] == 0 and len(owner["components"][0]["entries"]) == 2


def test_a_unit_with_no_plan_is_all_unknown_and_a_bad_unit_id_is_refused(tmp_path):
    out = v.unit_record_view(tmp_path, _community(), "7")
    assert out["planMatched"] is False
    assert all(r["status"] == "unknown" for r in out["components"])
    with pytest.raises(ValueError):
        v.unit_record_view(tmp_path, _community(), "../..")


def _stub_shelf(monkeypatch, found, policies=None, events=()):
    import jason.mcp.county as county
    import jason.tasks.cite as cite

    monkeypatch.setattr(cite, "cite", lambda *a, **k: object())
    monkeypatch.setattr(cite, "resolve", lambda expr, **k: ({"found": True, "citation": expr, "text": found[expr]} if expr in found
                                                            else {"found": False, "reason": "not-found"}))
    monkeypatch.setattr(county, "insurance_policies",
                        lambda **k: {"policies": policies if policies is not None else [{"key": "master", "kind": "master",
                                                                                         "carrier": "Carrier", "number": "N1",
                                                                                         "renewal": "2099-09-28", "deductibleCents": 1000000}]})
    monkeypatch.setattr(county, "incident_history", lambda **k: {"events": list(events)})


def test_the_packet_recites_each_provision_and_holds_what_is_missing(tmp_path, monkeypatch):
    _stub_shelf(monkeypatch, {"decl 8.1(a)(i)": "The words of the provision.", "policy 1": "The policy's words."},
                events=({"date": "2098-03-01", "title": "Water heater replaced"},))
    out = v.loss_packet_view(tmp_path, _community(), "7", "inc1", address="123 Main St")
    steps = {s["step"]: s for s in out["steps"]}
    assert steps[1]["recited"] == ["The words of the provision."] and steps[1]["held"] == ""
    assert "Provision not found on file: rule 9" in steps[5]["held"]
    assert "deductible guideline" in steps[5]["held"]
    assert out["confirmed"] is False and out["note"].startswith("Unconfirmed")
    assert out["history"] == ["2098-03-01 Water heater replaced"]
    assert out["policy"]["number"] == "N1" and [q["key"] for q in out["open_questions"]] == ["q1"]


def test_no_policy_on_file_is_held_at_step_three(tmp_path, monkeypatch):
    _stub_shelf(monkeypatch, {"policy 1": "x"}, policies=[])
    steps = {s["step"]: s for s in v.loss_packet_view(tmp_path, _community(), "7")["steps"]}
    assert "No policy is on file" in steps[3]["held"]


def test_a_person_s_confirmations_are_read_from_the_packet_store(tmp_path, monkeypatch):
    from jason.community.profile import profile_name

    _stub_shelf(monkeypatch, {"decl 8.1(a)(i)": "w", "policy 1": "w", "rule 9": "w"})
    folder = tmp_path / profile_name() / "units" / "7" / "packets"
    folder.mkdir(parents=True)
    (folder / "inc1.json").write_text(json.dumps({"steps": {"1": {"shows": ["the faucet"], "confirmed_by": "A Manager",
                                                                   "confirmed_at": "2099-02-01"}}}), encoding="utf-8")
    steps = {s["step"]: s for s in v.loss_packet_view(tmp_path, _community(), "7", "inc1")["steps"]}
    assert steps[1]["state"] == "confirmed" and steps[1]["confirmed_by"] == "A Manager" and steps[3]["state"] == "unconfirmed"


def test_no_ladder_is_a_miss(tmp_path):
    assert v.loss_packet_view(tmp_path, _community(loss_ladder=lambda: ()), "7")["found"] is False


def test_the_routes_answer_from_the_profile(tmp_path):
    from jason.web.app import create_app

    c = create_app().test_client()
    r = c.get("/api/facts")
    assert r.status_code == 200 and r.json["found"] is True and r.json["total"] >= 1
    assert c.get("/api/unit-record?unit=7").status_code == 200
    assert c.get("/api/unit-record").status_code == 400


def test_every_provision_of_the_profiles_ladder_recites_words_from_the_shelf():
    """A provision the shelf cannot recite is a held note in the packet, so the profile's ladder names only sections that
    resolve to words (an article is an outline, never words). Skipped where the documents are not on disk."""
    from pathlib import Path

    from jason.community import community
    from jason.tasks.cite import resolve

    c = community()
    expressions = sorted({p for row in c.loss_ladder() for p in row.provisions})
    if not expressions or not resolve(expressions[0], community=c).get("found"):
        pytest.skip("the governing documents are not on disk here")
    missing = [e for e in expressions if not (resolve(e, community=c, text=True).get("text") or "").strip()]
    assert missing == []
