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
}


class _Recorder:
    def __init__(self, name: str, calls: list):
        self.name = name
        self.calls = calls

    def __call__(self, *args, **kwargs):
        self.calls.append((self.name, args, kwargs))
        return {"found": True, "stub": self.name}


@pytest.fixture
def county():
    """A fake ``jason.mcp.county`` whose every attribute records its call; ``county.calls`` is the log."""
    saved = {k: sys.modules.get(k) for k in ("jason.mcp", "jason.mcp.county")}
    calls: list = []
    fake = types.ModuleType("jason.mcp.county")
    fake.calls = calls
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
    assert set(TOOLS) | {"leads", "duties", "canvases"} == set(loaders)
    for name, fn in loaders.items():
        assert re.fullmatch(r"[a-z]+(-[a-z]+)*", name), name
        assert callable(fn)
        if name == "canvases":  # a store under data/, not a county tool; its own test below
            continue
        out = fn({})
        assert isinstance(out, dict), name


@pytest.mark.parametrize("loader", sorted(TOOLS))
def test_loader_calls_its_tool(county, loader):
    out = sources.default_loaders()[loader]({})
    name, _ = _one(county)
    assert name == TOOLS[loader]
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
