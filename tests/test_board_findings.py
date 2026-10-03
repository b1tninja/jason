"""The board's decision recorded beside the facts: insurance renewals and reserve findings.

The stores round-trip and refuse bad entries; the loaders join a faked ``insurance_review`` / ``reserve_transfers`` to
the records on disk and flag what needs the board.
"""

from __future__ import annotations

import json
import sys

import pytest

from jason.tasks import insurance_renewals as renewals
from jason.tasks import reserve_findings as findings
from jason.web.extra import insurance_renewals as renewals_web
from jason.web.extra import reserve_findings as findings_web

# the web test's fake county module, reused here so the loaders pick it up on their lazy import
from test_web_sources import county  # noqa: F401


def test_renewal_record_roundtrip_and_history(tmp_path):
    assert renewals.load(tmp_path) == {}
    rec = renewals.record(tmp_path, " 12345-00 ", decision="renew as quoted", decided_on="2026-10-20", by="Secretary", premium_cents=612000)
    assert rec["number"] == "12345-00" and rec["decidedOn"] == "2026-10-20" and rec["premiumCents"] == 612000
    assert rec["limitsChanged"] is False and rec["memberNoticeNeeded"] is False and rec["noticeAuthority"] == ""
    assert rec["history"] == [f"{rec['recorded'][:10]}: recorded renew as quoted by Secretary"]
    again = renewals.record(tmp_path, "12345-00", decision="Renew with changes", decided_on="2026-10-21", by="Treasurer", limits_changed=True, note="deductible up")
    assert again["decision"] == "renew with changes" and again["memberNoticeNeeded"] is True and again["noticeAuthority"] == "CIV 5810"
    assert "memberNoticeDueBy" not in again, "5810 sets no date; the flag says the notice is needed"
    assert len(again["history"]) == 2 and again["history"][-1].endswith("re-recorded renew with changes by Treasurer (was renew as quoted)")
    on_disk = json.loads((tmp_path / "insurance" / "renewals.json").read_text())
    assert set(on_disk["renewals"]) == {"12345-00"} and on_disk["renewals"]["12345-00"]["note"] == "deductible up"
    lapse = renewals.record(tmp_path, "FLD-7", decision="let lapse", decided_on="2026-10-20", by="S")
    assert lapse["memberNoticeNeeded"] is True and lapse["premiumCents"] is None
    assert set(renewals.load(tmp_path)) == {"12345-00", "FLD-7"}


@pytest.mark.parametrize("kwargs", [
    dict(decision="renew", decided_on="2026-10-20", by="S"),
    dict(decision="renew as quoted", decided_on="October 20", by="S"),
    dict(decision="renew as quoted", decided_on="2026-10-20", by="  "),
    dict(decision="renew as quoted", decided_on="2026-10-20", by="S", premium_cents=61.20),
    dict(decision="renew as quoted", decided_on="2026-10-20", by="S", premium_cents=-1),
    dict(decision="renew as quoted", decided_on="2026-10-20", by="S", premium_cents=True),
    dict(decision="renew as quoted", decided_on="2026-10-20", by="S", limits_changed="yes"),
])
def test_renewal_record_refuses(tmp_path, kwargs):
    with pytest.raises(ValueError):
        renewals.record(tmp_path, "12345-00", **kwargs)
    with pytest.raises(ValueError):
        renewals.record(tmp_path, "  ", decision="renew as quoted", decided_on="2026-10-20", by="S")
    assert not (tmp_path / "insurance").exists()


def test_finding_record_roundtrip_and_history(tmp_path):
    assert findings.load(tmp_path) == {}
    key = findings.key_of({"day": "2025-03-01", "number": "77", "cents": 1000000})
    assert key == "2025-03-01|77"
    rec = findings.record(tmp_path, key, finding="Needed to pay the roof contractor; repaid from the April assessments by June.", kind="finding at borrowing",
                          made_on="2025-02-25", by="Secretary", meeting="2025-02-25")
    assert rec["key"] == key and rec["authority"] == "CIV 5515(c)" and rec["meeting"] == "2025-02-25" and rec["madeOn"] == "2025-02-25"
    assert rec["history"][0].endswith("recorded finding at borrowing by Secretary")
    late = findings.record(tmp_path, key, finding="Restoration deferred to 2026-09; the delay is in the association's best interest.", kind="Finding for a late restoration",
                           made_on="2026-03-20", by="Secretary", meeting="2026-03-17")
    assert late["kind"] == "finding for a late restoration" and late["authority"] == "CIV 5515(d)" and len(late["history"]) == 2
    on_disk = json.loads((tmp_path / "payhoa" / "reserve-findings.json").read_text())
    assert on_disk["findings"][key]["finding"].startswith("Restoration deferred")


@pytest.mark.parametrize("key,kwargs", [
    ("2025-03-01|77", dict(finding="  ", kind="finding at borrowing", made_on="2025-02-25", by="S", meeting="2025-02-25")),
    ("2025-03-01|77", dict(finding="x", kind="a finding", made_on="2025-02-25", by="S", meeting="2025-02-25")),
    ("2025-03-01|77", dict(finding="x", kind="finding at borrowing", made_on="2025-02-25", by="", meeting="2025-02-25")),
    ("2025-03-01|77", dict(finding="x", kind="finding at borrowing", made_on="2025-02-25", by="S", meeting="")),
    ("2025-03-01|77", dict(finding="x", kind="finding at borrowing", made_on="soon", by="S", meeting="2025-02-25")),
    ("2025-03-01|77", dict(finding="x", kind="finding at borrowing", made_on="2025-02-20", by="S", meeting="2025-02-25")),   # recorded before the meeting
    ("2025-03-01|77", dict(finding="x", kind="finding for a late restoration", made_on="2025-02-25", by="S", meeting="2025-02-25")),  # before the borrowing
    ("77", dict(finding="x", kind="finding at borrowing", made_on="2025-02-25", by="S", meeting="2025-02-25")),
    ("03/01/2025|77", dict(finding="x", kind="finding at borrowing", made_on="2025-02-25", by="S", meeting="2025-02-25")),
    ("2025-03-01|", dict(finding="x", kind="finding at borrowing", made_on="2025-02-25", by="S", meeting="2025-02-25")),
])
def test_finding_record_refuses(tmp_path, key, kwargs):
    with pytest.raises(ValueError):
        findings.record(tmp_path, key, **kwargs)
    assert not (tmp_path / "payhoa").exists()


REVIEW = {"found": True, "asOf": "2026-10-03", "claims": [], "caveats": ["the sheet is the specification"], "policies": [
    {"kind": "property", "building": None, "number": "P-1", "priorNumbers": [], "carrier": "Acme", "program": "", "agent": "Agent", "standing": "in term",
     "termEnd": "2026-12-01", "terms": [], "nextTermPayments": [], "notices": [], "findings": []},
    {"kind": "flood", "building": 5, "number": "F-5", "priorNumbers": ["F-5-00"], "carrier": "NFIP", "program": "", "agent": "Agent", "standing": "renewal notice received",
     "termEnd": "2027-06-01", "terms": [], "nextTermPayments": [], "notices": [{"kind": "renewal bill", "received": "2026-09-01"}], "findings": []},
    {"kind": "umbrella", "building": None, "number": "U-9", "priorNumbers": [], "carrier": "Acme", "program": "", "agent": "Agent", "standing": "the term ended",
     "termEnd": "2026-09-01", "terms": [], "nextTermPayments": [], "notices": [], "findings": ["the term ended with no premium for the next"]},
    {"kind": "d_and_o", "building": None, "number": "D-2", "priorNumbers": [], "carrier": "Acme", "program": "", "agent": "Agent", "standing": "in term",
     "termEnd": None, "terms": [], "nextTermPayments": [], "notices": [], "findings": []},
]}


def test_insurance_renewals_loader_joins_the_store(county, tmp_path, monkeypatch):
    fake = sys.modules["jason.mcp.county"]
    monkeypatch.setattr(fake, "_data_dir", lambda _: tmp_path, raising=False)
    monkeypatch.setattr(fake, "insurance_review", lambda: REVIEW, raising=False)
    out = renewals_web.insurance_renewals({"today": "2026-10-03"})
    assert out["found"] is True and out["asOf"] == "2026-10-03" and out["today"] == "2026-10-03" and out["windowDays"] == 90
    assert out["decisions"] == list(renewals.DECISIONS) and out["decisions"][0] == "renew as quoted"
    by = {p["key"]: p for p in out["policies"]}
    assert set(by) == {"P-1", "F-5", "U-9", "D-2"}
    assert by["P-1"]["renewalWindow"] is True and by["P-1"]["daysToTermEnd"] == 59
    assert by["F-5"]["renewalWindow"] is False and by["F-5"]["daysToTermEnd"] > 90
    assert by["U-9"]["renewalWindow"] is True and by["U-9"]["daysToTermEnd"] < 0, "a term already ended is inside the window"
    assert by["D-2"]["renewalWindow"] is False and by["D-2"]["daysToTermEnd"] is None
    assert all(p["renewal"] is None and p["memberNoticeNeeded"] is False for p in out["policies"])
    assert by["F-5"]["notices"][0]["kind"] == "renewal bill", "the review's facts ride along"
    assert out["caveats"][0] == "the sheet is the specification" and any("buys, renews, cancels, and claims nothing" in c for c in out["caveats"])
    assert any("5810" in c for c in out["caveats"])

    rec = renewals_web.write("P-1", {"decision": "renew with changes", "decidedOn": "2026-10-20", "by": "Secretary", "premiumCents": 612000, "limitsChanged": True, "note": "deductible up"})
    assert rec["decision"] == "renew with changes" and rec["memberNoticeNeeded"] is True
    assert renewals_web.write("U-9", {"decision": "let lapse", "decidedOn": "2026-10-20", "by": "Secretary", "premiumCents": ""})["premiumCents"] is None
    out = renewals_web.insurance_renewals({"today": "2026-10-03"})
    by = {p["key"]: p for p in out["policies"]}
    assert by["P-1"]["renewal"]["by"] == "Secretary" and by["P-1"]["memberNoticeNeeded"] is True and by["P-1"]["renewal"]["premiumCents"] == 612000
    assert by["U-9"]["renewal"]["decision"] == "let lapse" and by["F-5"]["renewal"] is None
    with pytest.raises(ValueError):
        renewals_web.write("F-5", {"decision": "maybe", "decidedOn": "2026-10-20", "by": "S"})
    with pytest.raises(ValueError):
        renewals_web.write("F-5", {"decision": "re-bid", "decidedOn": "2026-10-20", "by": "S", "premiumCents": "612000"})


TRANSFERS = {"found": True, "ledgerThrough": "2026-09-30", "budgetYears": [], "caveats": ["a match is a lead"], "borrowings": [
    {"day": "2025-03-01", "cents": 1000000, "account": "Reserve", "number": "77", "memo": "roof", "deadline": "2026-03-01", "repaidCents": 400000, "outstandingCents": 600000, "repaidOn": None,
     "documents": {"notice": {"path": "a.pdf"}, "minutes": None, "resolution": None},
     "gaps": ["no minutes in the library for the meeting that considered it (5515(c) finding)", "no resolution in the library authorizes it",
              "not restored within a year (due 2026-03-01); a delay needs a noticed finding (5515(d))"]},
    {"day": "2024-06-01", "cents": 250000, "account": "Reserve", "number": "41", "memo": "", "deadline": "2025-06-01", "repaidCents": 250000, "outstandingCents": 0, "repaidOn": "2024-09-01",
     "documents": {"notice": {"path": "n.pdf"}, "minutes": {"path": "m.pdf", "draft": False}, "resolution": {"path": "r.pdf"}}, "gaps": []},
    {"day": "2024-01-15", "cents": 50000, "account": "Reserve", "number": "12", "memo": "", "deadline": "2025-01-15", "repaidCents": 0, "outstandingCents": 50000, "repaidOn": None,
     "documents": {"notice": None, "minutes": {"path": "m2.pdf", "draft": True}, "resolution": None},
     "gaps": ["no agenda in the library gives notice of intent to borrow (5515(a))", "the library holds only DRAFT minutes of that meeting", "no transfer back to the reserve restores it"]},
]}


def test_reserve_findings_loader_joins_the_store(county, tmp_path, monkeypatch):
    fake = sys.modules["jason.mcp.county"]
    monkeypatch.setattr(fake, "_data_dir", lambda _: tmp_path, raising=False)
    monkeypatch.setattr(fake, "reserve_transfers", lambda: TRANSFERS, raising=False)
    out = findings_web.reserve_findings({})
    assert out["found"] is True and out["ledgerThrough"] == "2026-09-30" and out["kinds"] == list(findings.KINDS)
    by = {b["key"]: b for b in out["borrowings"]}
    assert set(by) == {"2025-03-01|77", "2024-06-01|41", "2024-01-15|12"}
    assert by["2025-03-01|77"]["findingNeeded"] is True and by["2025-03-01|77"]["finding"] is None
    assert by["2024-06-01|41"]["findingNeeded"] is False, "a complete record needs nothing"
    assert by["2024-01-15|12"]["findingNeeded"] is False, "its gaps name no finding; a DRAFT-minutes gap is not a missing finding"
    assert out["needed"] == 1
    assert by["2025-03-01|77"]["documents"]["notice"]["path"] == "a.pdf" and len(by["2025-03-01|77"]["gaps"]) == 3, "the tool's documents and gaps ride along"
    assert out["caveats"][0] == "a match is a lead" and any("only the board's resolution says which loan" in c for c in out["caveats"])
    assert any("board's call" in c for c in out["caveats"])

    rec = findings_web.write("2025-03-01|77", {"finding": "Needed for the roof; repaid from the April assessments.", "kind": "finding at borrowing", "madeOn": "2025-02-25", "by": "Secretary", "meeting": "2025-02-25"})
    assert rec["authority"] == "CIV 5515(c)"
    out = findings_web.reserve_findings({})
    by = {b["key"]: b for b in out["borrowings"]}
    assert by["2025-03-01|77"]["findingNeeded"] is False and by["2025-03-01|77"]["finding"]["by"] == "Secretary" and out["needed"] == 0
    assert by["2024-06-01|41"]["finding"] is None
    with pytest.raises(ValueError):
        findings_web.write("2025-03-01|77", {"finding": "", "kind": "finding at borrowing", "madeOn": "2025-02-25", "by": "S", "meeting": "2025-02-25"})
    with pytest.raises(ValueError):
        findings_web.write("77", {"finding": "x", "kind": "finding at borrowing", "madeOn": "2025-02-25", "by": "S", "meeting": "2025-02-25"})


def test_registry_resolves_both_extras(county, tmp_path, monkeypatch):
    from jason.web import sources

    fake = sys.modules["jason.mcp.county"]
    monkeypatch.setattr(fake, "_data_dir", lambda _: tmp_path, raising=False)
    monkeypatch.setattr(fake, "insurance_review", lambda: {"found": False, "policies": []}, raising=False)
    monkeypatch.setattr(fake, "reserve_transfers", lambda: {"found": False, "borrowings": []}, raising=False)
    loaders = sources.default_loaders()
    assert loaders["insurance-renewals"]({})["policies"] == [] and loaders["reserve-findings"]({})["borrowings"] == []
    assert sources.extra_writer("insurance-renewals")("P-1", {"decision": "re-bid", "decidedOn": "2026-10-20", "by": "S"})["decision"] == "re-bid"
    assert sources.extra_writer("reserve-findings")("2025-03-01|77", {"finding": "x", "kind": "finding at borrowing", "madeOn": "2025-02-25", "by": "S", "meeting": "2025-02-25"})["key"] == "2025-03-01|77"
