"""The two "a person records a choice" stores and their web sources: collection steps and mail triage.

Each store roundtrips through its JSON under data/ and refuses a bad step, choice, date, or vote. Each loader joins a
faked ``jason.mcp.county`` tool's rows to the store and repeats its caveat; ``write`` takes the URL key and the body.
"""

from __future__ import annotations

import inspect
import json
import sys
import types

import pytest

from jason.tasks import collection_steps as steps
from jason.tasks import mail_triage as triage

COLLECTIONS = {"found": True, "counts": {"OWED_NO_LIEN": 1, "RELEASE_DUE": 1}, "pastDueCents": 123400, "note": "the ledger as of its last sync; Jason does not submit an account to a collection agency, record a lien, or start a foreclosure",
               "rows": [
                   {"apn": "000-0000-001", "address": "123 Main St #12", "owners": ["Owner Twelve"], "standing": "OWED_NO_LIEN", "meaning": "past due, no lien of record",
                    "balanceCents": 123400, "pastDueCents": 123400, "lien": "", "lienRecorded": "", "lienStatus": "", "lienDays": None, "floorQuestion": "", "nextStep": "pre-lien notice (CIV 5660), then a board vote"},
                   {"apn": "000-0000-002", "address": "123 Main St #7", "owners": ["Owner Seven"], "standing": "RELEASE_DUE", "meaning": "paid; lien still of record",
                    "balanceCents": 0, "pastDueCents": 0, "lien": "2024-0000123", "lienRecorded": "2024-03-01", "lienStatus": "open", "lienDays": 900, "floorQuestion": "", "nextStep": "record the release within 21 days (CIV 5685)"},
               ]}
BRIEF = {"found": True, "since": "2026-09-03", "items": 3, "byKind": {"legal": 1, "bank": 1, "ad": 1},
         "act": [{"mailId": "9001", "received": "2026-10-01", "sender": "Superior Court", "from": None, "kind": "legal", "urgency": "act", "evidence": ["summons"], "deadlines": [{"date": "2026-10-31", "label": "respond by"}], "status": "scanned", "folder": "Inbox", "scanned": True, "summary": []}],
         "review": [{"mailId": "9002", "received": "2026-09-28", "sender": "A Bank", "from": None, "kind": "bank", "urgency": "review", "evidence": [], "deadlines": [], "status": "scanned", "folder": "Inbox", "scanned": True, "summary": []}],
         "unscanned": [{"mailId": "9003", "received": "2026-09-30", "sender": "Ad Co", "from": None, "kind": "ad", "urgency": "file", "evidence": [], "deadlines": [], "status": "new", "folder": "Inbox", "scanned": False, "summary": []}],
         "upcomingDeadlines": [], "policyReadings": [], "caveats": ["The kind comes from the sender's name and the letter's words; it is a sort, not a reading of what the letter means."]}


class _Recorder:
    def __init__(self, name, calls, result):
        self.name, self.calls, self.result = name, calls, result

    def __call__(self, *args, **kwargs):
        self.calls.append((self.name, args, kwargs))
        return json.loads(json.dumps(self.result))


@pytest.fixture
def county(tmp_path):
    """A fake ``jason.mcp.county`` with the two tools the loaders call and ``_data_dir`` pointing at tmp_path."""
    saved = {k: sys.modules.get(k) for k in ("jason.mcp", "jason.mcp.county")}
    calls: list = []
    fake = types.ModuleType("jason.mcp.county")
    fake.calls = calls
    fake.association_collections = _Recorder("association_collections", calls, COLLECTIONS)

    def mail_brief(days: int = 30, kind: str = "", urgency: str = ""):
        calls.append(("mail_brief", (), {"days": days, "kind": kind, "urgency": urgency}))
        return json.loads(json.dumps(BRIEF))
    fake.mail_brief = mail_brief
    fake._data_dir = lambda _: tmp_path
    pkg = types.ModuleType("jason.mcp")
    pkg.__path__ = []
    pkg.county = fake
    sys.modules["jason.mcp"] = pkg
    sys.modules["jason.mcp.county"] = fake
    try:
        yield fake
    finally:
        for k, v in saved.items():
            if v is None:
                sys.modules.pop(k, None)
            else:
                sys.modules[k] = v


# --- collection steps -------------------------------------------------------------------------------------------------

def test_collection_steps_roundtrip(tmp_path):
    assert steps.load(tmp_path) == {} and steps.account(tmp_path, "000-0000-001")["latest"] is None
    one = steps.record_step(tmp_path, "000-0000-001", step="pre-lien notice sent (CIV 5660)", decided_on="2026-09-15", by="Treasurer", note="certified mail")
    assert one["apn"] == "000-0000-001" and one["latest"]["step"] == "pre-lien notice sent (CIV 5660)" and one["latest"]["vote"] == ""
    assert one["latest"]["history"] == [f"{one['latest']['recorded'][:10]}: pre-lien notice sent (CIV 5660) recorded by Treasurer"]
    two = steps.record_step(tmp_path, " 000-0000-001 ", step=steps.Step.LIEN_RECORDED.value, decided_on="2026-10-20", by="Secretary", vote="3-0")
    assert len(two["steps"]) == 2 and two["latest"]["step"].startswith("lien recorded") and two["latest"]["vote"] == "3-0" and two["latest"]["decidedOn"] == "2026-10-20"
    assert len(two["latest"]["history"]) == 2 and two["latest"]["history"][0] == one["latest"]["history"][0]
    on_disk = json.loads((tmp_path / "board" / "collection-steps.json").read_text())
    assert set(on_disk) == {"savedAt", "accounts"} and [s["step"] for s in on_disk["accounts"]["000-0000-001"]] == [one["latest"]["step"], two["latest"]["step"]]
    assert set(two["latest"]) == {"step", "decidedOn", "by", "vote", "note", "recorded", "history"}
    assert steps.load(tmp_path)["000-0000-001"] == two["steps"]


def test_collection_steps_refusals(tmp_path):
    ok = dict(step="written off", decided_on="2026-10-01", by="S")
    with pytest.raises(ValueError, match="one of"):
        steps.record_step(tmp_path, "000-0000-001", **{**ok, "step": "foreclosed"})
    with pytest.raises(ValueError, match="who recorded"):
        steps.record_step(tmp_path, "000-0000-001", **{**ok, "by": "  "})
    with pytest.raises(ValueError):
        steps.record_step(tmp_path, "000-0000-001", **{**ok, "decided_on": "soon"})
    with pytest.raises(ValueError, match="ayes"):
        steps.record_step(tmp_path, "000-0000-001", **ok, vote="three to none")
    with pytest.raises(ValueError, match="parcel"):
        steps.record_step(tmp_path, "", **ok)
    assert not (tmp_path / "board").exists(), "a refused step writes nothing"
    assert len(steps.STEPS) == 7 and "lien recorded (CIV 5673, open session roll call)" in steps.STEPS and "foreclosure authorized (CIV 5720)" in steps.STEPS


def test_delinquency_loader_joins_the_steps(county, tmp_path):
    from jason.web.extra import delinquency as src

    steps.record_step(tmp_path, "000-0000-001", step="payment plan offered", decided_on="2026-09-01", by="Treasurer")
    steps.record_step(tmp_path, "000-0000-001", step="pre-lien notice sent (CIV 5660)", decided_on="2026-09-15", by="Treasurer")
    steps.record_step(tmp_path, "000-0000-999", step="written off", decided_on="2026-01-01", by="Treasurer")
    out = src.delinquency({})
    assert county.calls == [("association_collections", (), {})]
    assert out["found"] is True and out["pastDueCents"] == 123400 and out["counts"] == COLLECTIONS["counts"]
    twelve, seven = out["rows"]
    assert twelve["nextStep"].startswith("pre-lien") and twelve["latestStep"]["step"] == "pre-lien notice sent (CIV 5660)" and [s["step"] for s in twelve["steps"]] == ["payment plan offered", "pre-lien notice sent (CIV 5660)"]
    assert seven["standing"] == "RELEASE_DUE" and seven["steps"] == [] and seven["latestStep"] is None
    assert [o["apn"] for o in out["recordedOnly"]] == ["000-0000-999"]
    assert out["steps"] == list(steps.STEPS) and out["lienStep"].startswith("lien recorded") and "roll call" in out["rollCall"]
    assert any("records the board's step" in c and "forecloses on nothing" in c for c in out["caveats"])
    assert any("roll call" in c and "5673" in c for c in out["caveats"])
    assert out["caveats"][-1] == COLLECTIONS["note"]


def test_delinquency_loader_passes_a_missing_catalog_through(county):
    from jason.web.extra import delinquency as src

    county.association_collections = lambda: {"found": False, "note": "no PayHOA catalog"}
    out = src.delinquency({})
    assert out["found"] is False and out["rows"] == [] and out["note"] == "no PayHOA catalog"


def test_delinquency_write_takes_the_apn_and_body(county, tmp_path):
    from jason.web.extra import delinquency as src

    out = src.write("000-0000-002", {"step": "release recorded", "decidedOn": "2026-10-02", "by": "Secretary", "vote": "", "note": "release 2026-0000456"})
    assert out["apn"] == "000-0000-002" and out["latest"]["step"] == "release recorded" and out["latest"]["note"] == "release 2026-0000456"
    assert steps.load(tmp_path)["000-0000-002"][0]["by"] == "Secretary"
    with pytest.raises(ValueError):
        src.write("000-0000-002", {"step": "sold the unit", "decidedOn": "2026-10-02", "by": "S"})
    with pytest.raises(ValueError):
        src.write("000-0000-002", {"step": "release recorded", "by": "S"})  # no date
    assert src.delinquency({})["rows"][1]["latestStep"]["step"] == "release recorded"


# --- mail triage ------------------------------------------------------------------------------------------------------

def test_mail_triage_roundtrip(tmp_path):
    assert triage.load(tmp_path) == {}
    one = triage.choose(tmp_path, 9001, choice="Scan", by="Secretary", note="a summons")
    assert one["mailId"] == "9001" and one["choice"] == "scan" and one["note"] == "a summons" and one["history"] == [f"{one['on'][:10]}: scan by Secretary"]
    assert set(one) == {"mailId", "choice", "by", "on", "note", "history"}
    two = triage.choose(tmp_path, "9001", choice="forward", by="Treasurer")
    assert two["choice"] == "forward" and two["note"] == "" and len(two["history"]) == 2 and two["history"][-1].endswith("scan -> forward by Treasurer")
    same = triage.choose(tmp_path, "9001", choice="forward", by="Treasurer")
    assert same["history"][-1].endswith(": forward by Treasurer") and "->" not in same["history"][-1]
    on_disk = json.loads((tmp_path / "mail" / "triage.json").read_text())
    assert set(on_disk) == {"savedAt", "items"} and set(on_disk["items"]) == {"9001"} and triage.load(tmp_path) == on_disk["items"]


def test_mail_triage_refusals(tmp_path):
    with pytest.raises(ValueError, match="one of"):
        triage.choose(tmp_path, "9001", choice="burn", by="S")
    with pytest.raises(ValueError, match="who"):
        triage.choose(tmp_path, "9001", choice="shred", by=" ")
    with pytest.raises(ValueError, match="mail item"):
        triage.choose(tmp_path, "", choice="shred", by="S")
    assert not (tmp_path / "mail").exists()
    assert triage.CHOICES == ("scan", "forward", "shred", "discard", "keep")


def test_mail_triage_loader_joins_the_choices_and_forwards_days(county, tmp_path):
    from jason.web.extra import mail_triage as src

    assert "days" in inspect.signature(county.mail_brief).parameters
    triage.choose(tmp_path, "9003", choice="discard", by="Secretary")
    out = src.mail_triage({})
    assert county.calls == [("mail_brief", (), {"days": 30, "kind": "", "urgency": ""})], "no days arg: the tool's default"
    assert [r["mailId"] for r in out["act"]] == ["9001"] and out["act"][0]["choice"] is None and out["act"][0]["deadlines"][0]["date"] == "2026-10-31"
    assert out["review"][0]["choice"] is None
    assert out["unscanned"][0]["choice"]["choice"] == "discard" and out["unscanned"][0]["choice"]["by"] == "Secretary"
    assert out["chosen"] == 1 and out["choices"] == ["scan", "forward", "shred", "discard", "keep"] and out["byKind"] == BRIEF["byKind"]
    assert out["caveats"][0].startswith("jason scans, forwards, shreds, and discards nothing") and out["caveats"][-1] == BRIEF["caveats"][0]
    county.calls.clear()
    src.mail_triage({"days": "7"})
    assert county.calls == [("mail_brief", (), {"days": 7, "kind": "", "urgency": ""})]


def test_mail_triage_loader_skips_days_when_the_tool_lacks_it(county):
    from jason.web.extra import mail_triage as src

    county.mail_brief = lambda: {"found": False, "note": "no mail on disk"}
    out = src.mail_triage({"days": "7"})
    assert out["found"] is False and out["act"] == [] and out["review"] == [] and out["unscanned"] == [] and out["note"] == "no mail on disk"


def test_mail_triage_write_takes_the_mail_id_and_body(county, tmp_path):
    from jason.web.extra import mail_triage as src

    out = src.write("9001", {"choice": "forward", "by": "Secretary", "note": "to counsel"})
    assert out == {**triage.load(tmp_path)["9001"]} and out["choice"] == "forward" and out["note"] == "to counsel"
    with pytest.raises(ValueError):
        src.write("9001", {"choice": "open", "by": "S"})
    with pytest.raises(ValueError):
        src.write("9001", {"choice": "keep"})  # no name
    assert src.mail_triage({})["act"][0]["choice"]["choice"] == "forward"


def test_both_are_registered_as_extra_sources():
    from jason.web import sources

    assert sources.EXTRA_LOADERS["delinquency"] == "jason.web.extra.delinquency:delinquency" and sources.EXTRA_WRITERS["delinquency"] == "jason.web.extra.delinquency:write"
    assert sources.EXTRA_LOADERS["mail-triage"] == "jason.web.extra.mail_triage:mail_triage" and sources.EXTRA_WRITERS["mail-triage"] == "jason.web.extra.mail_triage:write"
    assert callable(sources.extra_writer("delinquency")) and callable(sources.extra_writer("mail-triage"))
