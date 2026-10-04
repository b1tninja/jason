"""Evidence you can open (``jason.approvals.evidence``): each kind of address resolved from disk, the plan's snapshot
written when the plan is stored, ``changed`` true, false, and null, masking, misses, and the route and the tool.

Example Village (tests/test_approvals.py): four fake owners on a fake PayHOA client. Nothing here reaches PayHOA,
Google, or Keeper, and nothing reads data/: every store is in ``tmp_path``.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest
import webclient

from jason.approvals import engine, evidence, model, store
from jason.approvals.evidence import CAVEAT, DOT, EvidenceKind, mask_field, resolve, rule_for
from test_approvals import (FIXTURES, _approve_partly, _validator, village)  # noqa: F401 - fixtures

MASK = DOT * 4


def _plan(village):
    return engine.plan("owner-info-tags", village.live, by="A Manager")


def _source(out, name):
    return next((s for s in out["sources"] if s["name"] == name), None)


def _field(src, name):
    return next(f for f in src["fields"] if f["name"] == name)


def _catalog(data_dir: Path, rows: list[tuple[int, str]], synced_at: str | None = None) -> Path:
    from jason.catalog import PayhoaCatalog

    path = data_dir / "payhoa.db"
    with PayhoaCatalog(path) as cat:
        cat.upsert_requests(1, [{"id": sid, "formId": 900, "unitId": sid - 500, "status": status,
                                 "createdAt": "2026-10-05T00:00:00Z"} for sid, status in rows],
                            form_names={900: "Owner information"})
    if synced_at is not None:
        with sqlite3.connect(path) as conn:
            conn.execute("UPDATE requests SET synced_at = ?", (synced_at,))
    return path


# --- the record -----------------------------------------------------------------------------------------------------------

def test_an_old_approval_without_read_at_still_loads_and_validates():
    planned = json.loads((FIXTURES / "example-village-planned.json").read_text(encoding="utf-8"))
    a = model.from_dict(planned)
    rows = [e for i in a.items for e in i.evidence]
    assert rows and all(e.read_at == "" and e.digest == "" for e in rows)
    again = model.to_dict(a)
    assert all("readAt" not in e and "digest" not in e for i in again["items"] for e in i["evidence"])
    _validator("approval.schema.json").validate(again)


def test_a_plan_stamps_its_request_evidence_and_keeps_what_it_read(village):
    a = _plan(village)
    snaps = store.load_snapshots(a.id, village.data_dir)
    assert store.snapshot_file(a.id, village.data_dir).is_file()
    assert set(snaps) == {f"payhoa:submission:{sid}" for sid in (501, 502, 503, 504)}
    stamped = [e for i in a.items for e in i.evidence if e.address.startswith("payhoa:submission:")]
    assert stamped and all(e.read_at == a.read_at and e.digest == snaps[e.address]["digest"] for e in stamped)
    assert all(not e.read_at for i in a.items for e in i.evidence if not e.address.startswith("payhoa:"))
    s503 = snaps["payhoa:submission:503"]
    assert s503["status"] == "pending" and s503["readAt"] == a.read_at and s503["unitId"] == 3
    fields = {f["name"]: f for f in s503["fields"]}
    assert fields["second-mailing-address"]["value"] == "PO Box 12, Example City"     # kept whole on disk
    assert fields["occupancy"]["p2"] and not fields["delivery"]["p2"]                 # reported occupancy is P2
    # the sidecar is not an approval: the store lists one approval, and the JSON round-trips with the stamps
    assert store.ids(village.data_dir) == [a.id] and len(store.load_all(village.data_dir)) == 1
    assert model.from_dict(model.to_dict(a)) == a
    _validator("approval.schema.json").validate(model.to_dict(store.load(a.id, village.data_dir)))


def test_a_re_plan_after_a_change_keeps_its_own_snapshot(village):
    a = _approve_partly(village)
    village.client._person(11)["tags"].append({"tag": "Notices by Mail", "id": 7777})
    done = engine.apply(a.id, village.live, by="A Manager")
    fresh = done.superseded_by
    assert fresh is not None and store.load_snapshots(fresh.id, village.data_dir)
    assert store.load_snapshots(a.id, village.data_dir)                               # the first plan's read stays


# --- a PayHOA request -----------------------------------------------------------------------------------------------------

def test_a_request_opens_from_the_plans_read_masked_with_its_refreshes(village):
    from jason.tasks.payhoa_forms import requests_link

    a = _plan(village)
    out = resolve("payhoa:submission:503", approval_id=a.id[:12], data_dir=village.data_dir)
    _validator("evidence.schema.json").validate(out)
    assert out["found"] and out["kind"] == "payhoa_submission" and out["label"] == "PayHOA request 503"
    read = _source(out, "This plan's read")
    assert read["readAt"] == a.read_at and len(read["digest"]) == 64 and read["text"] == ""
    assert _field(read, "Status") == {"name": "Status", "value": "pending", "masked": False}
    assert _field(read, "Second mailing address") == {"name": "Second mailing address", "value": MASK, "masked": True}
    assert _field(read, "Occupancy")["masked"] and _field(read, "Occupancy")["value"] == MASK
    assert _field(read, "Delivery") == {"name": "Delivery", "value": "By email", "masked": False}
    assert "PO Box" not in json.dumps(out)                                             # never leaves the server
    assert out["changed"] is None and out["link"] == requests_link(3)
    assert CAVEAT in out["caveats"] and any(f"jason approvals apply {a.id}" in c for c in out["caveats"])
    assert {"command": f"jason approvals apply {a.id}", "live": True, "system": "PayHOA",
            "what": "re-read PayHOA and compare with this plan, writing nothing"} in out["refresh"]
    assert "jason sync-catalog --only requests" in out["note"]                        # the missing copies, named


def test_without_an_approval_a_request_is_a_miss_naming_what_fills_it(village):
    out = resolve("payhoa:submission:999", data_dir=village.data_dir)
    _validator("evidence.schema.json").validate(out)
    assert not out["found"] and out["sources"] == [] and out["kind"] == "payhoa_submission"
    assert out["note"].startswith("No copy on disk") and "jason sync-request-files --requests 999" in out["note"]
    assert all(not r["command"].startswith("jason approvals apply") for r in out["refresh"])


def test_changed_is_true_false_or_null_against_a_later_catalog(village):
    a = _plan(village)
    later = "2999-01-01T00:00:00+00:00"
    _catalog(village.data_dir, [(502, "complete"), (504, "pending")], synced_at=later)
    moved = resolve("payhoa:submission:502", approval_id=a.id, data_dir=village.data_dir)
    assert moved["changed"] is True and "status complete" in moved["changedNote"]
    assert _field(_source(moved, "PayHOA catalog"), "Status")["value"] == "complete"
    same = resolve("payhoa:submission:504", approval_id=a.id, data_dir=village.data_dir)
    assert same["changed"] is False and "same status" in same["changedNote"]
    _catalog(village.data_dir, [(502, "complete")], synced_at="2000-01-01T00:00:00+00:00")
    before = resolve("payhoa:submission:502", approval_id=a.id, data_dir=village.data_dir)
    assert before["changed"] is None and "before the plan" in before["changedNote"]
    alone = resolve("payhoa:submission:502", data_dir=village.data_dir)               # no plan read to compare
    assert alone["found"] and alone["changed"] is None and _source(alone, "This plan's read") is None


def test_request_files_are_counted_not_copied(village):
    folder = village.data_dir / "payhoa-files" / "requests" / "502"
    folder.mkdir(parents=True)
    (folder / "comments.json").write_text(json.dumps([{"createdAt": "2026-10-06T00:00:00Z", "body": "Thanks",
                                                       "email": "ben@example.com"}]), encoding="utf-8")
    (folder / "notes.json").write_text("[]", encoding="utf-8")
    (folder / "77_answer.pdf").write_bytes(b"%PDF-1.4")
    out = resolve("payhoa:submission:502", data_dir=village.data_dir)
    files = _source(out, "Request files")
    assert out["found"] and files["readAt"]
    assert {f["name"]: f["value"] for f in files["fields"]} == {"Comments": "1", "Internal notes": "0",
                                                                "Latest comment": "2026-10-06T00:00:00Z",
                                                                "Attachments": "1"}
    assert "ben@example.com" not in json.dumps(out)


def test_a_snapshot_changed_after_the_plan_is_said(village):
    a = _plan(village)
    file = store.snapshot_file(a.id, village.data_dir)
    snaps = json.loads(file.read_text(encoding="utf-8"))
    snaps["payhoa:submission:502"]["digest"] = "0" * 64
    file.write_text(json.dumps(snaps), encoding="utf-8")
    out = resolve("payhoa:submission:502", approval_id=a.id, data_dir=village.data_dir)
    assert "changed after" in _source(out, "This plan's read")["note"]


# --- masking --------------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("name, value, shown, masked", [
    ("Email", "ana@example.com", f"a{MASK}@example.com", True),
    ("Phone", "(916) 555-0100", MASK, True),
    ("Mailing address", "PO Box 12", MASK, True),
    ("Comment", "write to ana@example.com or 916-555-0100",
     f"write to a{MASK}@example.com or ({DOT * 3}) {DOT * 3}-{DOT * 4}", True),
    ("Unit address", "101 EXAMPLE WAY", "101 EXAMPLE WAY", False),
    ("Delivery", "By email", "By email", False),
    ("Occupancy", "Rented out", MASK, True),
])
def test_contact_details_are_masked_by_the_server(name, value, shown, masked):
    assert mask_field(name, value, p2=name == "Occupancy") == {"name": name, "value": shown, "masked": masked}


# --- a citation, a board item, a command, a miss --------------------------------------------------------------------------

STATUTE = """- History: made-up

4920. (Made up for a test.)

(a) Except as provided in subdivision (b), notice of a meeting is given four days before it.

(b) An emergency meeting needs no notice.
"""


@pytest.fixture
def shelf(tmp_path, monkeypatch):
    """A made-up statute in tmp_path/authorities, read through ``jason cite``'s own resolver."""
    from jason.tasks import cite

    law = tmp_path / "authorities" / "CIV"
    law.mkdir(parents=True)
    (law / "CIV-4900-4955.md").write_text("# Board meetings\n\n## CIV 4920\n" + STATUTE, encoding="utf-8")
    (tmp_path / "authorities" / "manifest.json").write_text(json.dumps({"pages": [{
        "file": "authorities/CIV/CIV-4900-4955.md", "citation": "CIV 4900-4955", "title": "Board Meeting",
        "code": "CIV", "start": "4900", "end": "4955", "sections": ["4920"], "basis": "duty", "why": [],
        "session": "2099"}]}), encoding="utf-8")
    community = SimpleNamespace(living_documents=lambda: (), citable_documents=lambda: (), conflicts=lambda: (),
                                notice_provisions=lambda: ())
    real = cite.resolve
    monkeypatch.setattr("jason.tasks.cite.resolve", lambda expression, **kw: real(
        expression, shelf=cite.Shelf(community, tmp_path, repo=tmp_path / "no-repo")))
    return tmp_path


def test_a_citation_is_recited_from_disk(shelf):
    out = resolve("CIV 4920(a)", data_dir=shelf)
    _validator("evidence.schema.json").validate(out)
    assert out["found"] and out["kind"] == "citation"
    law = _source(out, "Statutes on disk")
    assert law["citation"] == "CIV 4920(a)" and "four days before it" in law["text"] and law["readAt"]
    assert law["caveat"] and CAVEAT in out["caveats"]
    assert out["refresh"][0] == {"command": "jason export-authorities", "live": False, "system": "",
                                 "what": "export the statutes' words from lawlibrary into data/authorities"}
    whole = _source(resolve("CIV 4920", data_dir=shelf), "Statutes on disk")
    assert whole["text"].startswith("4920.") and "History" not in whole["text"]      # the recital opens with the section
    assert {"name": "History", "value": "made-up", "masked": False} in whole["fields"]
    miss = resolve("CIV 5300", data_dir=shelf)
    assert not miss["found"] and miss["kind"] == "citation" and "jason export-authorities" in miss["note"]


def test_a_board_item_opens_and_an_executive_ones_summary_is_held_back(tmp_path):
    from jason.community.board_items import BoardItem, ItemCategory, Session
    from jason.tasks.board_items import save

    save(tmp_path, [BoardItem("example-rule", "Adopt an example rule", "The records show a gap.", "decide",
                              ItemCategory.GOVERNANCE, authority="CIV 4360"),
                    BoardItem("example-plan", "A payment plan", "Owner X owes.", "decide", ItemCategory.COLLECTIONS,
                              session=Session.EXECUTIVE)])
    out = resolve("board-item:example-rule", data_dir=tmp_path)
    _validator("evidence.schema.json").validate(out)
    item = _source(out, "Board items")
    assert out["found"] and out["kind"] == "board_item" and out["label"] == "Board item example-rule: Adopt an example rule"
    assert _field(item, "Summary")["value"] == "The records show a gap." and item["readAt"]
    hidden = _source(resolve("board-item:example-plan", data_dir=tmp_path), "Board items")
    assert all(f["name"] != "Summary" for f in hidden["fields"]) and "held back" in hidden["note"]
    gone = resolve("board-item:nothing-here", data_dir=tmp_path)
    assert not gone["found"] and "No board item nothing-here" in gone["note"]


def test_a_command_is_found_with_itself_as_the_refresh(tmp_path):
    out = resolve("jason owner-info --apply --payhoa", data_dir=tmp_path)
    _validator("evidence.schema.json").validate(out)
    assert out["found"] and out["kind"] == "command" and out["sources"] == []
    assert out["refresh"] == [{"command": "jason owner-info --apply --payhoa", "live": True,
                               "what": "the command that produced this", "system": "PayHOA"}]
    quiet = resolve("jason owner-info --responses", data_dir=tmp_path)
    assert quiet["refresh"][0]["live"] is False and quiet["refresh"][0]["system"] == ""


@pytest.mark.parametrize("address", ["", "nothing:here", "a sentence with no citation in it"])
def test_an_unresolvable_address_is_a_miss_not_an_exception(tmp_path, address):
    out = resolve(address, approval_id="apr-none", data_dir=tmp_path)
    _validator("evidence.schema.json").validate(out)
    assert out == {**out, "found": False, "kind": "unknown", "sources": [], "changed": None}
    assert out["note"] and "opened without a plan" in out["note"]


def test_the_rule_rows_take_addresses_in_order():
    kinds = [r.kind for r in evidence.RULES]
    assert kinds == [EvidenceKind.PAYHOA_SUBMISSION, EvidenceKind.BOARD_ITEM, EvidenceKind.COMMAND,
                     EvidenceKind.CITATION]
    assert rule_for("payhoa:submission:1")[0].kind is EvidenceKind.PAYHOA_SUBMISSION
    assert rule_for("jason cite CIV 4041")[0].kind is EvidenceKind.COMMAND               # a command, not its citation
    assert rule_for("CIV 4040(a)(2)")[0].kind is EvidenceKind.CITATION
    assert rule_for("payhoa:submission:x")[0].kind is EvidenceKind.UNKNOWN


# --- jason-web and jason-mcp ----------------------------------------------------------------------------------------------

def test_the_route_reads_only_and_a_miss_is_200(village, monkeypatch):
    from test_web_approvals import _dist

    from jason.web.app import create_app

    monkeypatch.setattr("jason.mcp.county._data_dir", lambda d: village.data_dir / "letters")
    a = _plan(village)
    c = webclient.client(create_app(_dist(village.data_dir), None, approvals_live=None))
    r = c.get(f"/api/evidence?address=payhoa:submission:503&approval={a.id}")
    assert r.status_code == 200 and r.json["found"] and _source(r.json, "This plan's read")
    assert "PO Box" not in json.dumps(r.json) and village.client.reads["list_units"] == 1     # the plan's read only
    miss = c.get("/api/evidence?address=nothing:here")
    assert miss.status_code == 200 and miss.json["found"] is False and miss.json["address"] == "nothing:here"
    assert c.post("/api/evidence?address=x").status_code in (404, 405)


def test_the_mcp_tool_is_read_only_in_the_governance_set(village):
    from jason import api
    from jason.mcp import governance
    from jason.mcp.server import tools_for

    a = _plan(village)
    assert governance.evidence in governance.TOOLS and api.evidence is governance.evidence
    assert "evidence" in {t.__name__ for t in tools_for("governance")}
    assert len(tools_for("board")) == 38
    out = governance.evidence("payhoa:submission:502", approval_id=a.id, data_dir=village.data_dir)
    assert out["found"] and out == resolve("payhoa:submission:502", approval_id=a.id, data_dir=village.data_dir)
