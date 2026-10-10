"""The inspections and portals loaders: the codes read off documents (masked), a report portal's holdings, the last filing
plan, the backflow program (clocks, discrepancies, the tester check), and the watchlist. Each reads disk only."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import date
from types import SimpleNamespace

import pytest

from jason.community import community
from jason.community.backflow import (AssemblyType, BackflowAssembly, BackflowProgram, ProgramNotice, Service)
from jason.community.backflow import TesterList as _List, TesterRef as _Ref          # a leading underscore: pytest collects "Test*" names
from jason.tasks import backflow
from jason.tasks.document_codes import view as codes_view
from jason.tasks.report_portals import filing_plan_view, plan_as_dict, portal_view, save_plan


def _pdf(lines: list[str]) -> bytes:
    import pymupdf

    document = pymupdf.open()
    page = document.new_page()
    for n, line in enumerate(lines):
        page.insert_text((40, 40 + 14 * n), line)
    return document.tobytes()


# --- The clocks ---------------------------------------------------------------------------------------------------------

def _notice(settled: str = "", runs=(("failed test", "2030-05-05"), ("dated", "2030-06-02"), ("postmarked", "2030-06-11"), ("scanned", "2030-07-03"))):
    return ProgramNotice("Example program", "the notice's words", 15, tuple(runs), settled_on=settled)


def test_a_clock_counts_from_every_date_and_picks_none():
    clock = backflow.notice_clock(_notice(settled="2030-06-18"), date(2030, 10, 4))
    by = {r["label"]: r for r in clock["runsFrom"]}
    assert (by["failed test"]["elapsed"], by["failed test"]["met"]) == (44, False)
    assert (by["dated"]["elapsed"], by["dated"]["met"]) == (16, False)
    assert (by["postmarked"]["elapsed"], by["postmarked"]["met"]) == (7, True)
    assert (by["scanned"]["elapsed"], by["scanned"]["met"]) == (0, None)         # the reading came after the repair
    assert clock["standing"] == "unknown" and "program's to say" in clock["caveat"]


def test_a_clock_is_met_passed_or_running_only_when_every_reading_agrees():
    assert backflow.notice_clock(_notice("2030-06-10", (("dated", "2030-06-02"),)), date(2030, 10, 4))["standing"] == "met"
    assert backflow.notice_clock(_notice("", (("dated", "2030-01-01"), ("scanned", "2030-02-01"))), date(2030, 10, 4))["standing"] == "passed"
    assert backflow.notice_clock(_notice("", (("dated", "2030-10-01"),)), date(2030, 10, 4))["standing"] == "running"


# --- The tester lists ---------------------------------------------------------------------------------------------------

COUNTY = ["COUNTY OF EXAMPLE TESTERS", "Updated 9/1/2030", "PI0000001", "JANE EXAMPLE TESTER", "EXAMPLE PLUMBING", "TOWN",
          "(916) 555-0100", "jane@example.test", "PI0000002", "SAM SAMPLE", "SAMPLE BACKFLOW CO", "TOWN", "(916) 555-0101", "sam@example.test"]
CITY = ["CITY TESTERS", "LAST NAME", "FIRST NAME", "BUSINESS NAME", "CITY", "PHONE", "EMAIL", "EXAMPLE", "JANE", "EXAMPLE PLUMBING",
        "TOWN", "(916) 555-0100", "JANE@EXAMPLE.TEST", "SAMPLE", "SAM", "SAMPLE BACKFLOW CO", "TOWN", "(916) 555-0101", "SAM@EXAMPLE.TEST"]


def test_a_list_is_kept_as_names_and_ids_without_phones_or_emails():
    dated, entries = backflow.parse_tester_list(_pdf(COUNTY))
    assert dated == "2030-09-01" and [e["id"] for e in entries] == ["PI0000001", "PI0000002"]
    assert "EXAMPLE PLUMBING" in entries[0]["text"] and "555" not in json.dumps(entries) and "@" not in json.dumps(entries)
    dated, entries = backflow.parse_tester_list(_pdf(CITY))
    assert dated == "" and len(entries) == 2 and entries[0]["text"].startswith("EXAMPLE JANE") and "555" not in json.dumps(entries)


def _program(tester: _Ref) -> BackflowProgram:
    return BackflowProgram("Annual testing", "Example Utilities", tester=tester,
                           lists=(_List("City", "https://example.test/city.pdf"), _List("County", "https://example.test/county.pdf")))


def test_the_tester_check_says_listed_not_certified_and_names_a_mismatched_business():
    snapshot = {"lists": [{"name": "City", "entries": [{"id": "", "text": "EXAMPLE JANE EXAMPLE PLUMBING TOWN"}]},
                          {"name": "County", "dated": "2030-09-01", "entries": [{"id": "PI0000009", "text": "JANE EXAMPLE JANE EXAMPLE TOWN"}]}]}
    found = backflow.check_tester(_program(_Ref("Jane Example", business="Example Plumbing", certificate="1")), snapshot)
    assert [(x["name"], x["found"]) for x in found["lists"]] == [("City", "listed"), ("County", "listed under another business")]
    assert found["lists"][1]["id"] == "PI0000009" and found["contactsMasked"] is True and "certified" not in json.dumps(found).lower()
    assert backflow.check_tester(_program(_Ref("Nobody Known")), snapshot)["lists"][0]["found"] == "not listed"
    assert {x["found"] for x in backflow.check_tester(_program(_Ref("Jane Example")), None)["lists"]} == {"not fetched"}


# --- The backflow view --------------------------------------------------------------------------------------------------

class _Profile:
    def __init__(self, program):
        self._program = program

    def backflow_program(self):
        return self._program


def test_the_view_shows_a_difference_between_sources_and_settles_nothing(tmp_path):
    fire = lambda serial: BackflowAssembly(Service.FIRE, AssemblyType.DC, 6, serial, "north", ids=(("County id", "BD" + serial),))
    program = BackflowProgram("Annual testing", "Example Utilities", assemblies=(fire("1"), fire("2")), notices=(_notice("2030-06-18"),),
                              counts=(("the reserve study", "fire", 3, "reserves.py"),))
    out = backflow.view(tmp_path, _Profile(program), today=date(2030, 10, 4))
    assert out["found"] and len(out["assemblies"]) == 2 and out["assemblies"][0]["ids"] == [{"source": "County id", "id": "BD1"}]
    (diff,) = out["discrepancies"]
    assert [s["says"] for s in diff["sources"]] == ["two", "three"] and "neither is chosen" in diff["next"]
    assert out["tester"] == {} or out["tester"].get("lists") is None
    assert backflow.view(tmp_path, _Profile(None))["found"] is False


def test_the_real_profile_has_six_assemblies_and_flags_the_reserve_count(tmp_path):
    out = backflow.view(tmp_path, community(), today=date(2030, 10, 4))
    assert len(out["assemblies"]) == 6 and [d["subject"] for d in out["discrepancies"]] == ["The number of fire backflow assemblies"]
    assert out["tester"]["lists"][0]["found"] == "not fetched" and "backflow --fetch-testers" in out["tester"]["note"]


# --- The codes ----------------------------------------------------------------------------------------------------------

def test_codes_are_masked_and_a_meeting_says_whether_the_zoom_index_has_it(tmp_path):
    cache = tmp_path / "onboarding" / "ingest" / "codes"
    cache.mkdir(parents=True)
    zoom = lambda i: {"text": f"https://us06web.zoom.us/j/{i}?pwd=SECRET123", "link": True, "format": "QRCode", "page": 1, "host": "us06web.zoom.us"}
    portal = {"text": "https://reports.firenspec.com/#/da4b8ba0-a3a8-11ec-b40e-e1561aa67388", "link": True, "format": "QRCode", "page": 2,
              "host": "reports.firenspec.com"}
    (cache / ("a" * 64 + ".json")).write_text(json.dumps([zoom("81392024127"), zoom("88077490565"), portal]), encoding="utf-8")
    (tmp_path / "zoom").mkdir()
    (tmp_path / "zoom" / "meetings.json").write_text(json.dumps({"meetings": [{"meetingId": "81392024127"}]}), encoding="utf-8")
    out = codes_view(tmp_path)
    codes = out["documents"][0]["codes"]
    assert all("SECRET123" not in json.dumps(c) for c in codes) and codes[0]["masked"] is True and "pwd=***" in codes[0]["text"]
    assert [c["meeting"]["recorded"] for c in codes[:2]] == [True, False]
    assert codes[2]["portal"]["platform"] == "firenspec" and codes[2]["masked"] is False
    assert codes_view(tmp_path, "zzzz")["found"] is False
    assert codes_view(tmp_path / "none")["found"] is False


# --- A report portal and a filing plan ----------------------------------------------------------------------------------

def test_a_portal_view_reads_where_each_report_is_held_now_and_a_plan_is_read_from_disk(tmp_path):
    root = tmp_path / "vendors" / "signalservice"
    (root / "reports" / "_mismatch").mkdir(parents=True)
    held, loose = b"%PDF-1.4 held", b"%PDF-1.4 loose"
    for name, data in (("held.pdf", held), ("loose.pdf", loose)):
        (root / "reports" / name).write_bytes(data)
    (root / "reports" / "_mismatch" / "refused.pdf").write_bytes(b"%PDF-1.4 x")
    row = lambda uid, name, data: {"urlUuid": uid, "day": "2030-01-01", "site": "Example Village HOA, Bldg. 1", "template": "Fire Alarm System",
                                   "inspector": "Inspector A", "file": f"reports/{name}", "pdfUrl": f"https://reports.example.test/viewReport.php?id={uid}",
                                   "portal": "p1", "sha256": hashlib.sha256(data).hexdigest()}
    (root / "reports.json").write_text(json.dumps({"fetched": "2030-10-04", "portals": [
        {"key": "p1", "protected": False, "customer": "Example Village HOA", "readFrom": ["a.pdf"]},
        {"key": "p2", "protected": False, "customer": "Example Village HOA", "readFrom": ["b.pdf"], "sameCustomerAs": "p1"}],
        "reports": [row("r1", "held.pdf", held), row("r2", "loose.pdf", loose)]}), encoding="utf-8")
    (tmp_path / "library").mkdir()
    with sqlite3.connect(tmp_path / "library" / "library.db") as conn:
        conn.execute("CREATE TABLE documents (id TEXT, path TEXT, name TEXT, sha256 TEXT)")
        conn.execute("INSERT INTO documents VALUES ('d1', 'Email Attachments/held.pdf', 'held.pdf', ?)", (hashlib.sha256(held).hexdigest(),))
    (tmp_path / "drive").mkdir()
    (tmp_path / "drive" / "files.json").write_text(json.dumps({"files": [
        {"id": "f1", "path": "My Drive/Reports/Fire Protection/Fire Alarm/held.pdf", "md5": hashlib.md5(held).hexdigest()}]}), encoding="utf-8")
    portal = SimpleNamespace(key="signalservice", vendor="Example Alarm Co.")
    out = portal_view(tmp_path, portal)
    first, second = out["portals"]
    assert [r["held"] for r in first["reports"]] == ["library and drive", "not filed"] and first["counts"]["notFiled"] == 1
    assert second["sameCustomerAs"] == "p1" and second["reports"] == [] and out["refused"] == ["refused.pdf"]
    assert {h["place"] for h in first["reports"][0]["holdings"]} == {"library", "drive", "portal"}
    assert portal_view(tmp_path / "none", portal)["found"] is False

    assert filing_plan_view(tmp_path, "signalservice")["found"] is False
    attachment = lambda action, copy_of="": SimpleNamespace(name="n.pdf", action=action, where="My Drive/Reports", why="the rule", kind="inspection_report", copy_of=copy_of)
    plan = plan_as_dict(SimpleNamespace(vendor="Example Alarm Co.", attachments=[attachment("file"), attachment("copy", "My Drive/Other/x.pdf"), attachment("move")]),
                        "jason vendors --reports --drive --yes")
    assert plan["counts"]["file"] == 1 and plan["counts"]["copy"] == 1 and plan["rows"][1]["original"] == "My Drive/Other/x.pdf"
    save_plan(tmp_path, "signalservice", plan)
    assert filing_plan_view(tmp_path, "signalservice")["found"] is True


# --- The watchlist ------------------------------------------------------------------------------------------------------

def test_the_watchlist_takes_a_calendar_standing_and_never_reads_unknown_as_overdue(tmp_path):
    out = __import__("jason.tasks.backflow", fromlist=["x"]).watchlist(tmp_path, community(), today=date(2030, 10, 4))
    assert out["found"] and {i["standing"] for i in out["items"]} <= {"overdue", "unknown", "partly answered", "current", "not applicable"}
    unknown = [i for i in out["items"] if i["standing"] == "unknown"]
    assert unknown and all(i["searched"] for i in unknown)
    assert out["items"][0]["standing"] in ("overdue", "unknown")                      # worst first
    assert backflow.watchlist(tmp_path, SimpleNamespace(life_safety_watch=lambda: ()))["found"] is False


def test_the_loaders_are_registered_and_answer_a_missing_store_with_a_note(tmp_path, monkeypatch):
    monkeypatch.setenv("JASON_DATA_DIR", str(tmp_path))
    from jason.web.sources import default_loaders

    loaders = default_loaders()
    for name in ("document-codes", "report-portal", "filing-plan", "backflow", "watchlist"):
        out = loaders[name]({})
        assert "found" in out
        if not out["found"]:
            assert out["note"]


def test_the_backflow_answer_leaves_out_what_is_empty_and_names_an_unresolved_document_as_text(tmp_path):
    out = backflow.view(tmp_path, community(), today=date(2030, 10, 4))
    assert all(v is not None for a in out["assemblies"] for v in a.values())          # a key with no value is left out
    assert "tag" not in out["assemblies"][0] and out["assemblies"][1]["tag"]            # the domestic one has a tag
    assert backflow.doc_refs(["No Such File.pdf"], tmp_path) == [{"text": "No Such File.pdf"}]      # no "Drive: " prefix
