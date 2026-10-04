"""Each UI loader forwards its query args to the right ``jason.mcp.county`` tool with the right keywords and defaults.

The real ``jason.mcp.county`` needs PayHOA and the stores; the loaders import it inside the function body, so a fake
module in ``sys.modules`` is picked up on every call and records what each loader passed.
"""

from __future__ import annotations

import re
import sys
import types

import pytest

from jason.web import sources

# loader name -> county tool name
TOOLS = {
    "board-digest": "board_digest",
    "board-items": "board_items",
    "association-records": "association_records",
    "records-inventory": "records_inventory",
    "library-status": "library_status",
    "document-readings": "document_readings",
    "jobs": "jobs_status",
    "calendar": "association_calendar",
    "meetings": "meeting_records",
    "insurance": "insurance_review",
    "budget": "budget_status",
    "reconciliations": "bank_reconciliations",
    "invoices": "invoice_review",
    "collections": "association_collections",
    "reserves": "reserve_transfers",
    "hearings": "hearings",
    "title-watch": "title_watch",
    "open-items": "open_items",
    "utility-payments": "utility_payments",
    "ledger-validation": "ledger_validation",
    "legal-cases": "legal_cases",
    "audit-chains": "audit_chains",
    "request-links": "request_links",
    "library": "library_search",
}


class _Recorder:
    def __init__(self, name: str, calls: list):
        self.name = name
        self.calls = calls

    def __call__(self, *args, **kwargs):
        self.calls.append((self.name, args, kwargs))
        return {"found": True, "stub": self.name}


@pytest.fixture
def county(tmp_path):
    """A fake ``jason.mcp.county`` whose every attribute records its call; ``county.calls`` is the log. Its data folder
    (``_data_dir``, which loaders that build document references ask for) is an empty made-up one."""
    saved = {k: sys.modules.get(k) for k in ("jason.mcp", "jason.mcp.county")}
    calls: list = []
    fake = types.ModuleType("jason.mcp.county")
    fake.calls = calls
    fake._data_dir = lambda data_dir=None: data_dir if data_dir is not None else tmp_path
    for name in set(TOOLS.values()) | {"duty_brief"}:
        setattr(fake, name, _Recorder(name, calls))
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


def _one(county):
    assert len(county.calls) == 1, county.calls
    name, args, kwargs = county.calls[0]
    assert args == (), "loaders pass keywords only"
    return name, kwargs


def test_every_loader_is_kebab_case_and_callable_with_empty_args(county):
    loaders = sources.default_loaders()
    assert set(TOOLS) | {"leads", "duties", "canvases", "templates", "drive-files", "photos", "meeting", "decisions", "embeds", "communities", "onboarding", "request-letter", "owner-info", "rule-changes"} | set(sources.EXTRA_LOADERS) == set(loaders)
    for name, fn in loaders.items():
        assert re.fullmatch(r"[a-z]+(-[a-z]+)*", name), name
        assert callable(fn)
        if name in ("canvases", "templates", "drive-files", "photos", "meeting", "decisions", "embeds", "communities", "onboarding", "request-letter", "owner-info", "rule-changes") or name in sources.EXTRA_LOADERS:  # stores under data/ or the profile, not county tools; their own tests below
            continue
        out = fn({})
        assert isinstance(out, dict), name


@pytest.mark.parametrize("loader", sorted(TOOLS))
def test_loader_calls_its_tool(county, loader):
    out = sources.default_loaders()[loader]({})
    name, _ = _one(county)
    assert name == TOOLS[loader]
    if loader == "hearings":  # decorates each row with its key and stages; its own test below
        assert out["found"] is True and out["hearings"] == []
    else:
        assert out == {"found": True, "stub": TOOLS[loader]}


@pytest.mark.parametrize("loader", [k for k, v in TOOLS.items() if v in (
    "association_records", "records_inventory", "library_status", "document_readings", "association_calendar",
    "insurance_review", "bank_reconciliations", "association_collections", "reserve_transfers", "hearings",
    "ledger_validation", "legal_cases")])
def test_no_arg_loaders_ignore_query(county, loader):
    sources.default_loaders()[loader]({"anything": "1", "all": "true"})
    _, kwargs = _one(county)
    assert kwargs == {}


@pytest.mark.parametrize("value,expected", [("1", True), ("true", True), ("TRUE", True), ("yes", True),
                                            ("0", False), ("no", False), ("", False), ("maybe", False)])
def test_flag_parsing(value, expected):
    assert sources._flag({"k": value}, "k") is expected
    assert sources._flag({}, "k") is False


def test_board_items(county):
    sources.board_items({})
    assert _one(county) == ("board_items", {"include_closed": False})
    county.calls.clear()
    sources.board_items({"closed": "true"})
    _, kwargs = _one(county)
    assert kwargs == {"include_closed": True} and kwargs["include_closed"] is True


def test_board_digest(county):
    sources.board_digest({})
    assert _one(county) == ("board_digest", {"since": "", "days": 30})
    county.calls.clear()
    sources.board_digest({"since": "2026-01-01", "days": "7"})
    _, kwargs = _one(county)
    assert kwargs == {"since": "2026-01-01", "days": 7} and isinstance(kwargs["days"], int)
    county.calls.clear()
    sources.board_digest({"days": ""})
    assert _one(county)[1]["days"] == 30


def test_duties_list_without_anchor_needs_no_tool(county):
    from jason.community.duties import DUTIES

    out = sources.duties({})
    assert county.calls == []
    assert out["found"] is True and out["count"] == len(DUTIES) == len(out["duties"])
    assert [d["anchor"] for d in out["duties"]] == [d.anchor for d in DUTIES]
    first = out["duties"][0]
    assert set(first) == {"anchor", "keepsStraight", "sections", "artifact", "cadence", "when", "records", "produce", "limit"}
    assert isinstance(first["cadence"], str) and all(isinstance(r, str) for r in first["records"])


def test_duties_with_anchor_calls_duty_brief(county):
    out = sources.duties({"anchor": "  minutes  "})
    assert len(county.calls) == 1
    name, args, kwargs = county.calls[0]
    assert name == "duty_brief" and args == ("minutes",) and kwargs == {}
    assert out == {"found": True, "stub": "duty_brief"}
    county.calls.clear()
    sources.duties({"anchor": "   "})
    assert county.calls == []


def test_meetings(county):
    sources.meetings({})
    assert _one(county) == ("meeting_records", {"date": ""})
    county.calls.clear()
    sources.meetings({"date": "2026-02-03"})
    assert _one(county) == ("meeting_records", {"date": "2026-02-03"})


def test_budget(county):
    sources.budget({})
    assert _one(county) == ("budget_status", {"year": 0})
    county.calls.clear()
    sources.budget({"year": "2026"})
    _, kwargs = _one(county)
    assert kwargs == {"year": 2026} and isinstance(kwargs["year"], int)
    county.calls.clear()
    sources.budget({"year": ""})
    assert _one(county)[1] == {"year": 0}


def test_invoices(county):
    sources.invoices({})
    assert _one(county) == ("invoice_review", {"payee": "", "problems_only": True, "since": "", "limit": 80})
    county.calls.clear()
    sources.invoices({"all": "1", "payee": "Acme", "since": "2026-01-01", "limit": "5"})
    _, kwargs = _one(county)
    assert kwargs == {"payee": "Acme", "problems_only": False, "since": "2026-01-01", "limit": 5}
    assert isinstance(kwargs["limit"], int) and kwargs["problems_only"] is False
    county.calls.clear()
    sources.invoices({"limit": ""})
    assert _one(county)[1]["limit"] == 80


def test_title_watch(county):
    sources.title_watch({})
    assert _one(county) == ("title_watch", {"apn": "", "standing": "", "attention": False})
    county.calls.clear()
    sources.title_watch({"apn": "000-000-000", "standing": "owner", "attention": "yes"})
    _, kwargs = _one(county)
    assert kwargs == {"apn": "000-000-000", "standing": "owner", "attention": True}
    assert kwargs["attention"] is True


def test_open_items(county):
    sources.open_items({})
    assert _one(county) == ("open_items", {"days": 30})
    county.calls.clear()
    sources.open_items({"days": "90"})
    _, kwargs = _one(county)
    assert kwargs == {"days": 90} and isinstance(kwargs["days"], int)


def test_utility_payments(county):
    sources.utility_payments({})
    assert _one(county) == ("utility_payments", {"problems_only": True, "since": "", "limit": 80})
    county.calls.clear()
    sources.utility_payments({"all": "true", "since": "2026-03", "limit": "12"})
    _, kwargs = _one(county)
    assert kwargs == {"problems_only": False, "since": "2026-03", "limit": 12}


def test_audit_chains(county):
    sources.audit_chains({})
    assert _one(county) == ("audit_chains", {"apn": ""})
    county.calls.clear()
    sources.audit_chains({"apn": "000-000-000"})
    assert _one(county) == ("audit_chains", {"apn": "000-000-000"})


def test_jobs(county):
    sources.jobs_status({})
    assert _one(county) == ("jobs_status", {"job": 0, "every": False})
    county.calls.clear()
    sources.jobs_status({"job": "7", "all": "1"})
    _, kwargs = _one(county)
    assert kwargs == {"job": 7, "every": True}
    assert isinstance(kwargs["job"], int) and kwargs["every"] is True
    county.calls.clear()
    sources.jobs_status({"job": ""})
    assert _one(county)[1]["job"] == 0


def test_leads_reads_four_tools_through_the_fake(county):
    out = sources.leads({})
    assert [c[0] for c in county.calls] == ["library_status", "records_inventory", "document_readings", "association_records"]
    assert all(kw == {} for _, _, kw in county.calls)
    # the stubs return no rows, so there are no leads and no notes
    assert out == {"count": 0, "counts": {}, "rows": [], "notes": [], "caveats": out["caveats"]}
    assert out["caveats"] and "not a pin" in out["caveats"][0]


def test_leads_rows_come_from_the_named_loaders(county, monkeypatch):
    monkeypatch.setattr(sources, "library_status", lambda a: {"unclassified": ["a.pdf", "b.pdf"]})
    monkeypatch.setattr(sources, "records_inventory", lambda a: {"records": [{"record": "minutes", "gap": ""}, {"record": "budget", "gap": "none", "citation": "CIV 5200"}]})
    monkeypatch.setattr(sources, "document_readings", lambda a: {"supersessions": [
        {"number": "1", "supersededBy": "2", "source": "x.pdf", "phase": 1, "pinned": True},
        {"number": "3", "supersededBy": "4", "source": "y.pdf", "pinned": False}]})
    monkeypatch.setattr(sources, "association_records", lambda a: {"deliveries": [], "unplaced": [
        {"number": "5", "filing": "deed", "recorded": "", "recordedBy": None}]})
    out = sources.leads({})
    assert county.calls == []  # the loaders are looked up by name on the module
    assert out["count"] == 5 and out["notes"] == []
    assert out["counts"] == {"unclassified file": 2, "records gap": 1, "supersession not pinned": 1, "unplaced instrument": 1}
    gap = next(r for r in out["rows"] if r["kind"] == "records gap")
    assert gap["title"] == "budget" and gap["authority"] == "CIV 5200"
    sup = next(r for r in out["rows"] if r["kind"] == "supersession not pinned")
    assert sup["title"] == "3 superseded by 4" and "phase ?" in sup["detail"]
    unplaced = next(r for r in out["rows"] if r["kind"] == "unplaced instrument")
    assert unplaced["title"] == "5" and "recorded ? by ?" in unplaced["detail"]
    assert all({"source", "kind", "title", "detail", "next"} <= set(r) for r in out["rows"])


def test_request_links_forwards(county):
    from jason.web.sources import request_links

    request_links({"unit": "12", "drafts": "1", "limit": "5"})
    assert county.calls[-1] == ("request_links", (), {"unit": "12", "drafts_only": True, "limit": 5})


def test_canvases_source_reads_the_store(county, tmp_path, monkeypatch):
    import sys

    from jason.tasks import canvases as store
    from jason.web.sources import canvases, write_canvas

    monkeypatch.setattr(sys.modules["jason.mcp.county"], "_data_dir", lambda _: tmp_path, raising=False)
    assert canvases({}) == {"found": True, "count": 0, "statuses": ["research", "preparing", "on agenda", "done"], "canvases": []}
    made = write_canvas("", {"title": "Pool deck bids", "duty": "Money"})
    assert made["key"] == "pool-deck-bids" and made["status"] == "research"
    write_canvas("pool-deck-bids", {"clip": {"source": "budget_status", "text": "Pool: $3,000 over budget", "args": {"year": 2026}}})
    write_canvas("pool-deck-bids", {"notes": "three quotes in hand", "status": "preparing"})
    one = canvases({"key": "pool-deck-bids"})["canvas"]
    assert one["notes"] == "three quotes in hand" and one["clips"][0]["source"] == "budget_status" and one["status"] == "preparing"
    listed = canvases({})["canvases"][0]
    assert listed["clips"] == 1 and listed["notes"] == ""
    assert canvases({"key": "nope"})["found"] is False
    assert store.load(tmp_path, "pool-deck-bids").history[-1].endswith("research -> preparing")


class _FakeCommunity:
    """A profile with one template row and no private facts; template_values reads what it has and defaults the rest."""

    def document_templates(self):
        from jason.community.templates import DocumentTemplate, TemplateKind

        return (DocumentTemplate(TemplateKind.HEARING_NOTICE, "Notice of Hearing", "1DocIdHearing", folder_id="1Folder"),)

    def identity(self):
        from jason.community.identity import Identity

        return Identity("The Association")


def test_templates_lists_lint_and_previews(county, tmp_path, monkeypatch):
    import sys

    from jason.web import sources

    monkeypatch.setattr(sys.modules["jason.mcp.county"], "_data_dir", lambda _: tmp_path, raising=False)
    monkeypatch.setattr(sources, "_community", lambda: _FakeCommunity())
    listing = sources.templates({})
    assert listing["found"] and listing["templates"][0]["kind"] == "hearing-notice"
    t = listing["templates"][0]
    assert set(t["lint"]) == {"profile", "general", "run"} and set(t["tokens"]) >= set(t["lint"]["run"])
    # The template's Doc is a document reference; its original is the header's "the template Doc" link.
    assert t["doc"]["address"] == "drive:1DocIdHearing" and t["doc"]["original"]["label"] == "Open in Google"
    assert "1DocIdHearing" in t["doc"]["original"]["url"]
    one = sources.templates({"kind": "hearing-notice", "name": "Hearing, unit 12", "V_OWNER_NAME": "J. Doe", "V_IGNORED": ""})
    assert one["found"] and "J. Doe" in one["markdown"] or "OWNER_NAME" not in one["tokens"]
    assert one["command"].startswith("jason letter --template hearing-notice --name 'Hearing, unit 12'") and one["command"].endswith("--yes")
    assert "--set OWNER_NAME=J.\\ Doe" in one["command"] or "--set 'OWNER_NAME=J. Doe'" in one["command"]
    assert "IGNORED" not in one["command"]
    assert all(x not in one["markdown"] for x in ("{", "}")), "no raw token survives"
    assert sources.templates({"kind": "nope"})["found"] is False


def test_drive_files_and_photos_read_the_stores(county, tmp_path, monkeypatch):
    import json
    import sys

    from jason.web import sources

    monkeypatch.setattr(sys.modules["jason.mcp.county"], "_data_dir", lambda _: tmp_path, raising=False)
    assert sources.drive_files({})["found"] is False and sources.photos({})["found"] is False
    (tmp_path / "drive").mkdir()
    (tmp_path / "drive" / "files.json").write_text(json.dumps({"syncedAt": "2026-10-01", "files": [
        {"id": "1A", "name": "Minutes 2026-09", "path": "Board/Minutes", "mimeType": "application/vnd.google-apps.document", "link": "https://d/1A", "modified": "2026-09-20"},
        {"id": "1B", "name": "Budget 2027", "path": "Finance", "mimeType": "application/vnd.google-apps.spreadsheet", "link": "https://d/1B", "modified": "2026-09-25"},
        {"id": "1C", "name": "roof.jpg", "path": "Photos", "mimeType": "image/jpeg", "link": "https://d/1C", "modified": "2026-08-01"},
    ]}))
    out = sources.drive_files({"q": "minutes"})
    assert out["matching"] == 1 and out["files"][0]["kind"] == "doc"
    kinds = [f["kind"] for f in sources.drive_files({})["files"]]
    assert kinds == ["sheet", "doc", "image"]
    (tmp_path / "photos" / "east-bed").mkdir(parents=True)
    (tmp_path / "photos" / "east-bed" / "manifest.json").write_text(json.dumps({"slug": "east-bed", "label": "East bed, before", "items": [
        {"filename": "a.jpg", "path": "photos/east-bed/a.jpg", "createTime": "2026-09-01", "mimeType": "image/jpeg"},
        {"filename": "b.mp4", "path": "photos/east-bed/b.mp4", "createTime": "2026-09-01", "mimeType": "video/mp4"},
    ]}))
    albums = sources.photos({})["albums"]
    assert albums[0]["count"] == 1 and albums[0]["items"][0]["path"] == "photos/east-bed/a.jpg"


def test_embeds_reads_the_zoom_index_and_the_profile(county, tmp_path, monkeypatch):
    import json
    import sys

    from jason.tasks.zoom import INDEX, ZOOM_DIR
    from jason.web import sources

    monkeypatch.setattr(sys.modules["jason.mcp.county"], "_data_dir", lambda _: tmp_path, raising=False)
    monkeypatch.setattr(sources, "_community", lambda: _FakeCommunity())  # no calendar_id, no time zone
    out = sources.embeds({})
    assert out["found"] is True and out["calendarId"] == "" and out["timeZone"] == "America/Los_Angeles"
    assert out["recordings"] == [] and out["maps"] == {} and any("no Zoom index" in n for n in out["notes"])

    class Community(_FakeCommunity):
        def calendar_id(self):
            return "abc123@group.calendar.google.com"

        def time_zone(self):
            return "America/Denver"

    monkeypatch.setattr(sources, "_community", lambda: Community())
    zoom = tmp_path / ZOOM_DIR
    old, new, closed = zoom / "meetings" / "2026-08-18-aaaaaaaaaa", zoom / "meetings" / "2026-09-15-bbbbbbbbbb", zoom / "meetings" / "2026-09-16-cccccccccc"
    for folder in (old, new, closed):
        folder.mkdir(parents=True)
    (new / "audio.m4a").write_bytes(b"\x00\x00")
    (new / "transcript.vtt").write_text("WEBVTT\n")
    (new / "transcript.txt").write_text("[00:00] A: hello\n")
    (new / "participants.json").write_text("[]")  # not a recording file
    (closed / "audio.m4a").write_bytes(b"\x00")
    (zoom / INDEX).write_text(json.dumps({"syncedAt": "2026-10-01T00:00:00+00:00", "since": "2026-01-01", "through": "2026-10-01", "meetings": [
        {"uuid": "u-old", "meetingId": "1", "topic": "Board meeting", "start": "2026-08-18T18:00-07:00", "date": "2026-08-18", "kind": "board",
         "confidential": False, "files": {}, "folder": "meetings/2026-08-18-aaaaaaaaaa", "cloud": ["MP4", "M4A"]},
        {"uuid": "u-new", "meetingId": "1", "topic": "Board meeting", "start": "2026-09-15T18:00-07:00", "date": "2026-09-15", "kind": "board",
         "confidential": False, "files": {"transcript": "meetings/2026-09-15-bbbbbbbbbb/transcript.txt"}, "folder": "meetings/2026-09-15-bbbbbbbbbb", "cloud": ["M4A", "TRANSCRIPT"]},
        {"uuid": "u-none", "meetingId": "2", "topic": "Chat only", "start": "2026-09-20T10:00-07:00", "date": "2026-09-20", "kind": "other",
         "confidential": False, "files": {}, "folder": "meetings/2026-09-20-dddddddddd"},
        {"uuid": "u-exec", "meetingId": "3", "topic": "Executive session", "start": "2026-09-16T19:00-07:00", "date": "2026-09-16", "kind": "executive session",
         "confidential": True, "files": {}, "folder": "meetings/2026-09-16-cccccccccc", "cloud": ["M4A"]},
    ]}))
    out = sources.embeds({})
    assert out["calendarId"] == "abc123@group.calendar.google.com" and out["timeZone"] == "America/Denver" and out["syncedAt"] == "2026-10-01T00:00:00+00:00"
    assert [r["uuid"] for r in out["recordings"]] == ["u-new", "u-old"], "newest first; no recording and confidential are left out"
    newest = out["recordings"][0]
    assert set(newest) == {"date", "topic", "uuid", "kind", "confidential", "shareUrl", "playUrl", "cloud", "files"}
    assert newest["date"] == "2026-09-15" and newest["shareUrl"] == "" and newest["playUrl"] == ""
    assert sorted((f["type"], f["name"], f["path"]) for f in newest["files"]) == [
        ("audio", "audio.m4a", "zoom/meetings/2026-09-15-bbbbbbbbbb/audio.m4a"),
        ("transcript", "transcript.txt", "zoom/meetings/2026-09-15-bbbbbbbbbb/transcript.txt"),
        ("transcript", "transcript.vtt", "zoom/meetings/2026-09-15-bbbbbbbbbb/transcript.vtt")]
    # each file carries its reference, at the server's level: the audio plays in Doc, never through /api/file
    audio = next(f for f in newest["files"] if f["type"] == "audio")["doc"]
    assert (audio["address"], audio["kind"], audio["level"]) == (
        "file:zoom/meetings/2026-09-15-bbbbbbbbbb/audio.m4a", "audio", "P1")
    assert out["recordings"][1]["files"] == [] and out["recordings"][1]["cloud"] == ["MP4", "M4A"]
    assert any("1 confidential" in n for n in out["notes"])
    assert [r["uuid"] for r in sources.embeds({"limit": "1"})["recordings"]] == ["u-new"]
    with_exec = sources.embeds({"confidential": "1"})
    assert [r["uuid"] for r in with_exec["recordings"]] == ["u-exec", "u-new", "u-old"] and with_exec["recordings"][0]["confidential"] is True
    assert with_exec["recordings"][0]["files"][0]["path"] == "zoom/meetings/2026-09-16-cccccccccc/audio.m4a"
    assert county.calls == [], "embeds reads disk only"


def test_meeting_builds_the_spine_from_the_board_items(county, tmp_path, monkeypatch):
    import json
    import sys
    from datetime import date

    from jason.web import sources

    class Community(_FakeCommunity):
        name = "The Association"
        corporate_name = ""

        def next_meeting(self, after, *, monthly=False):
            return date(2026, 10, 20)

        def unit_city_state_zip(self):
            return ""

    monkeypatch.setattr(sys.modules["jason.mcp.county"], "_data_dir", lambda _: tmp_path, raising=False)
    monkeypatch.setattr(sources, "_community", lambda: Community())
    (tmp_path / "board").mkdir()
    (tmp_path / "board" / "items.json").write_text(json.dumps({"items": [
        {"id": "reserve-loan", "title": "Reserve loan not restored", "summary": "s", "ask": "Decide whether to restore", "category": "reserves", "priority": "high", "status": "on agenda", "authority": "CIV 5515(d)", "evidence": [], "session": None, "special_notice": "", "due": None, "opened": "2026-09-01", "owner": "", "meeting": "2026-10-20", "notes": "", "source": "jason", "history": []},
        {"id": "unit-14-delinquency", "title": "Unit 14 delinquency", "summary": "s", "ask": "Vote to record a lien", "category": "collections", "priority": "normal", "status": "proposed", "authority": "CIV 5673", "evidence": [], "session": None, "special_notice": "", "due": None, "opened": "2026-09-01", "owner": "", "meeting": "", "notes": "", "source": "jason", "history": []},
        {"id": "closed-one", "title": "Done", "summary": "s", "ask": "a", "category": "finance", "priority": "normal", "status": "closed", "authority": "", "evidence": [], "session": None, "special_notice": "", "due": None, "opened": None, "owner": "", "meeting": "", "notes": "", "source": "jason", "history": []},
    ]}))
    out = sources.meeting({})
    assert out["found"] and out["date"] == "2026-10-20" and out["noticeBy"] == "2026-10-16" and out["executiveNoticeBy"] == "2026-10-18"
    assert [i["id"] for i in out["items"]] == ["reserve-loan", "unit-14-delinquency"]
    assert out["openCount"] == 1 and out["executiveCount"] == 1
    assert "Reserve loan not restored" in out["agendaMarkdown"]
    assert out["commands"]["packetDoc"] == "jason board --packet --date 2026-10-20 --doc --yes"
    assert sources.meeting({"date": "2026-11-17"})["noticeBy"] == "2026-11-13"
    assert sources.meeting({"date": "soon"})["found"] is False


def test_onboarding_and_communities_overlay_the_stores(county, tmp_path, monkeypatch):
    import sys

    from jason.web import sources

    class Community(_FakeCommunity):
        name = "The Association"

        def bank_accounts(self):
            return ({"suffix": "1234"},)

        def buildings(self):
            return ()

        def calendar_id(self):
            return ""

    monkeypatch.setattr(sys.modules["jason.mcp.county"], "_data_dir", lambda _: tmp_path, raising=False)
    monkeypatch.setattr(sources, "_community", lambda: Community())
    monkeypatch.setattr(sources, "records_inventory", lambda a: {"records": [{"record": "minutes", "gap": ""}, {"record": "tax_return", "gap": "nothing pinned"}]})
    monkeypatch.setattr(sources, "association_records", lambda a: {"deliveries": [{"delivery": "declaration", "found": ["1"], "missing": []}, {"delivery": "bond", "found": [], "missing": ["x"]}]})
    monkeypatch.setattr(sources, "_accounts", lambda: [{"service": "PayHOA", "set": True, "how": ""}, {"service": "Google", "set": False, "how": ""}])
    sources.write_request("declaration", {"status": "asked", "asked_of": "the prior manager", "asked_on": "2026-10-03"})
    out = sources.onboarding({})
    s = out["summary"]
    assert s["accountsSet"] == 1 and s["accountsTotal"] == 2 and s["recordsHeld"] == 1 and s["recordsTotal"] == 2 and s["deliveriesFound"] == 1 and s["gaps"] == 1
    assert s["factsSupplied"] >= 1 and s["factsTotal"] > 40
    by = {i["key"]: i for i in out["items"]}
    assert by["declaration"]["status"] == "asked" and by["declaration"]["askedOf"] == "the prior manager"
    assert "delivery is found" in by["declaration"]["storeSays"] and "gap" in by["tax-returns"]["storeSays"]
    assert by["minutes"]["storeSays"].startswith("a holder is pinned")
    assert by["bonds-warranties"]["storeSays"].endswith("the delivery is missing")
    assert s["requests"]["asked"] == 1
    letter = sources.request_letter({})
    assert letter["count"] == 1 and "The recorded declaration" in letter["markdown"] and "The Association" in letter["markdown"]
    assert sources.request_letter({"keys": "budget,minutes"})["count"] == 2
    monkeypatch.setattr(sys.modules.setdefault("jason.community.profile", type(sys)("jason.community.profile")), "profiles", lambda: [{"name": "mystique", "where": "/x/mystique", "active": True}, {"name": "sample", "where": "/x/profiles/sample", "active": False}], raising=False)
    comm = sources.communities({})
    assert comm["count"] == 2 and comm["communities"][0]["progress"]["accountsSet"] == 1 and "progress" not in comm["communities"][1]


def test_hearings_adds_keys_stages_and_decisions(county, tmp_path, monkeypatch):
    import sys

    from jason.web import sources

    fake = sys.modules["jason.mcp.county"]
    monkeypatch.setattr(fake, "hearings", lambda: {"found": True, "hearings": [
        {"address": "123 Main St #12", "start": "2026-10-20T18:00:00", "noticeBy": "2026-10-10", "noticeOn": "2026-10-05", "decisionByIfHeld": "2026-11-03", "standing": "s", "scheduled": True},
        {"address": "123 Main St #7", "start": "2026-09-01T18:00:00", "noticeBy": "2026-08-22", "decisionByIfHeld": "2026-09-15", "standing": "s", "scheduled": False,
         "decision": {"findings": "A $50 fine", "decidedOn": "2026-09-01", "noticeDueBy": "2026-09-15", "by": "Secretary", "recorded": "x", "history": []}},
    ]}, raising=False)
    out = sources.hearings({})
    a, b = out["hearings"]
    assert a["key"] == "2026-10-20|123-main-st-12" and [st["key"] for st in a["stages"]] == ["noticeBy", "hearing", "decisionBy"] and a["stages"][0]["done"] is True
    assert b["decision"]["findings"] == "A $50 fine" and [st["key"] for st in b["stages"]] == ["noticeBy", "hearing", "noticeDueBy"] and b["stages"][1]["done"] is True


def test_library_forwards(county):
    from jason.web.sources import library

    library({"kind": "minutes", "record": "minutes", "period": "2026", "words": "quorum", "confidential": "1", "limit": "5"})
    assert county.calls[-1] == ("library_search", (), {"kind": "minutes", "record": "minutes", "period": "2026", "words": "quorum", "include_confidential": True, "limit": 5})


def test_rule_changes_list_timeline_and_fill(county, tmp_path, monkeypatch):
    import sys
    from datetime import date, timedelta

    from jason.community.rule_changes import RuleChange, SectionChange
    from jason.web import sources

    class Schedule:
        def next_meeting(self, after, *, monthly=True):
            d = after + timedelta(days=1)
            while d.day != 15:
                d += timedelta(days=1)
            return d

    change = RuleChange("parking-tags", "Visitor parking tags", "parking-rules", "Parking Rules", "fewer tows", "owners register visitors",
                        (SectionChange("4", "Visitor parking", proposed="A visitor may park for [number of days] days with a tag."),
                         SectionChange("9", "Towing", strike="24 hours", proposed="48 hours")),
                        decisions=("the number of days",), caveats=("a lead,",))

    class Community(_FakeCommunity):
        def rule_changes(self):
            return (change,)

        def meeting_schedule(self):
            return Schedule()

    monkeypatch.setattr(sys.modules["jason.mcp.county"], "_data_dir", lambda _: tmp_path, raising=False)
    monkeypatch.setattr(sources, "_community", lambda: Community())
    listing = sources.rule_changes({})
    assert listing["found"] and listing["changes"][0]["placeholders"] == ["[number of days]"] and listing["changes"][0]["sections"] == 2
    one = sources.rule_changes({"key": "parking-tags", "notice": "2026-10-03"})
    assert one["found"] and one["open"] == ["[number of days]"] and "[number of days]" in one["sectionsMarkdown"]
    stages = {s["key"]: s["date"] for s in one["stages"]}
    assert stages["notice"] == "2026-10-03" and date.fromisoformat(stages["decision"]) >= date(2026, 10, 31) and stages["decision"].endswith("-15")
    assert date.fromisoformat(stages["adoptionNoticeBy"]) > date.fromisoformat(stages["decision"])
    assert one["command"] == "jason rule-change parking-tags --notice-date 2026-10-03 --draft-email --yes"
    filled = sources.rule_changes({"key": "parking-tags", "V_number of days": "3"})
    assert filled["open"] == [] and "for 3 days" in filled["sectionsMarkdown"]
    assert "current text not on disk" in filled["sectionsMarkdown"] or filled["currentNote"]
    soon = sources.rule_changes({"key": "parking-tags", "notice": "2026-10-03", "decision": "2026-10-10"})
    assert soon["stages"] == [] and "28" in soon["timelineNote"]
    assert sources.rule_changes({"key": "nope"})["found"] is False
