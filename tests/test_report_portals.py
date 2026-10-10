"""A vendor's public report portal: a QR link names it, its reports are listed and kept, a protected one is skipped."""

from __future__ import annotations

import json
from types import SimpleNamespace

import httpx
import pytest

from jason.community.portal_links import identify
from jason.community.symbols import PortalPlatform
from jason.firenspec.client import Firenspec, FirenspecError, FirenspecProtected, parse_reports
from jason.tasks.report_portals import discover, report_brief, sync_reports

PORTAL = "da4b8ba0-a3a8-11ec-b40e-e1561aa67388"
OTHER = "a2cf3590-a48f-11ec-aa8c-87eabde63d0d"           # the same customer's portal for another building
LINK = f"https://reports.example-firenspec.test/#/{PORTAL}"
FIREN = f"https://reports.firenspec.com/#/{PORTAL}"
NEW, OLD = "5194a490-1d93-11f1-835f-ef968616de60", "848fd2a0-9591-11f0-b35d-75056e3c24ae"
SITE = "Example Community Association -Bldg. 8"


def _pdf(text: str) -> bytes:
    import pymupdf

    document = pymupdf.open()
    document.new_page().insert_text((72, 72), text)
    return document.tobytes()


PDFS = {NEW: _pdf(f"Inspection Report For {SITE}"), OLD: _pdf("Inspection Report For Some Other Building")}


def _listing(protected: bool = False):
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("viewReport.php"):
            return httpx.Response(200, content=PDFS[request.url.params["id"]], headers={"content-type": "application/pdf"})
        data = json.loads(request.content)["data"]
        if path.endswith("publicGetPortalDetails"):
            assert data["uuid"] in (PORTAL, OTHER)
            return httpx.Response(200, json={"result": {"success": True, "siteID": "S8", "companyInfo": {"uuid": "C1", "name": "Example Alarm", "license": "L-1"},
                                                        "customerInfo": {"uuid": "U1", "BillName": "Example HOA"}}})
        if path.endswith("publicIsPortalPasswordProtected"):
            return httpx.Response(200, json={"result": {"isPasswordProtected": protected}})
        assert path.endswith("publicGetReportsForCustomerPortal") and data == {"customerID": "U1", "companyID": "C1"}
        row = {"siteID": "S8", "siteName": SITE, "templateName": "Fire Alarm System - NFPA 72 (2013)", "uploaderName": "A. Tech",
               "siteAddress": "123 Main St", "uuid": "1"}
        return httpx.Response(200, json={"result": {"success": True, "pdfs": {"inspection": [
            {**row, "url_uuid": NEW, "date": 1773265399130, "ticketCompletionDate": 1773265415466},
            {**row, "url_uuid": OLD, "date": 1758311267531}], "timeline": []}}})
    return handler


def _client(protected: bool = False) -> Firenspec:
    return Firenspec(http=httpx.Client(transport=httpx.MockTransport(_listing(protected))))


def _box(tmp_path):
    codes = tmp_path / "onboarding" / "ingest" / "codes"
    codes.mkdir(parents=True)
    (codes / ("a" * 64 + ".json")).write_text(json.dumps([{"text": FIREN, "link": True, "page": 1, "host": "reports.firenspec.com"},
                                                           {"text": "https://example.com/", "link": True}]), encoding="utf-8")
    note = tmp_path / "onboarding" / "ingest" / "text" / ("a" * 64 + ".json")
    note.parent.mkdir(parents=True)
    note.write_text(json.dumps({"file": "report.pdf"}), encoding="utf-8")
    return SimpleNamespace(key="signalreports", vendor="Example Alarm, Inc", reports=PortalPlatform.FIRENSPEC)


def test_a_link_is_identified_by_its_host_and_key():
    found = identify(FIREN.upper().replace("HTTPS", "https").replace("REPORTS.FIRENSPEC.COM", "reports.firenspec.com"))
    assert found and found.platform is PortalPlatform.FIRENSPEC and found.key == PORTAL
    assert identify(LINK) is None and identify("https://reports.firenspec.com/#/not-a-uuid") is None and identify("") is None


def test_the_reports_list_is_parsed_with_dates_and_the_pdf_link():
    reports = parse_reports({"result": {"success": True, "pdfs": {"inspection": [
        {"url_uuid": NEW, "siteName": SITE, "date": 1773265399130, "ticketCompletionDate": 1773265415466}, {"siteName": "no id"}]}}})
    assert len(reports) == 1 and str(reports[0].day) == "2026-03-11" and reports[0].pdf_url.endswith(f"viewReport.php?id={NEW}")
    with pytest.raises(FirenspecError):
        parse_reports({"result": {"success": False}})


def test_portals_are_found_from_the_codes_ingest_decoded(tmp_path):
    _box(tmp_path)
    assert discover(tmp_path, PortalPlatform.FIRENSPEC) == {PORTAL: ["report.pdf"]}


def test_the_sync_keeps_reports_that_print_their_site_and_refuses_the_rest(tmp_path):
    portal = _box(tmp_path)
    result = sync_reports(_client(), portal, tmp_path)
    assert (result.portals, result.reports, result.downloaded) == (1, 2, 1) and len(result.mismatches) == 1
    kept = list((tmp_path / "vendors" / "signalreports" / "reports").glob("*.pdf"))
    assert [p.name for p in kept] == [f"2026-03-11-Example-Community-Association-Bldg-8-{NEW[:8]}.pdf"]
    assert list((tmp_path / "vendors" / "signalreports" / "reports" / "_mismatch").glob("*.pdf"))
    brief = report_brief(tmp_path, portal)
    assert brief["found"] and [r["day"] for r in brief["reports"]] == ["2026-03-11"] and len(brief["missingFromLibrary"]) == 1
    again = sync_reports(_client(), portal, tmp_path)                     # the kept one is on disk; the refused one is asked again
    assert again.downloaded == 0 and again.present == 1


def test_a_protected_portal_is_recorded_and_skipped(tmp_path):
    portal = _box(tmp_path)
    with pytest.raises(FirenspecProtected):
        _client(True).reports(_client().details(PORTAL))
    result = sync_reports(_client(True), portal, tmp_path)
    assert result.protected == [PORTAL] and result.reports == 0 and result.downloaded == 0
    saved = json.loads((tmp_path / "vendors" / "signalreports" / "reports.json").read_text(encoding="utf-8"))
    assert saved["portals"][0]["protected"] is True


def test_two_portals_of_one_customer_list_its_reports_once(tmp_path):
    portal = _box(tmp_path)
    cache = tmp_path / "onboarding" / "ingest" / "codes" / ("b" * 64 + ".json")
    cache.write_text(json.dumps([{"text": f"https://reports.firenspec.com/#/{OTHER}", "link": True}]), encoding="utf-8")
    result = sync_reports(_client(), portal, tmp_path)
    assert (result.portals, result.reports, result.downloaded, len(result.mismatches)) == (2, 2, 1, 1)
    saved = json.loads((tmp_path / "vendors" / "signalreports" / "reports.json").read_text(encoding="utf-8"))
    assert sorted(bool(p.get("sameCustomerAs")) for p in saved["portals"]) == [False, True]
    assert sync_reports(_client(), portal, tmp_path).present == 1


def test_the_brief_reads_the_library_now_not_as_of_the_sync(tmp_path):
    import sqlite3

    portal = _box(tmp_path)
    sync_reports(_client(), portal, tmp_path)
    assert len(report_brief(tmp_path, portal)["missingFromLibrary"]) == 1
    sha = json.loads((tmp_path / "vendors" / "signalreports" / "reports.json").read_text(encoding="utf-8"))["reports"][0]["sha256"]
    (tmp_path / "library").mkdir()
    with sqlite3.connect(tmp_path / "library" / "library.db") as conn:
        conn.execute("CREATE TABLE documents (id TEXT, path TEXT, sha256 TEXT)")
        conn.execute("INSERT INTO documents VALUES ('d1', 'Email Attachments/report.pdf', ?)", (sha,))
    assert report_brief(tmp_path, portal)["missingFromLibrary"] == []
