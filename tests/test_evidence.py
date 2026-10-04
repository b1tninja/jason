"""Evidence you can open (``jason.approvals.evidence``): each kind of address resolved from disk, the plan's snapshot
written when the plan is stored, ``changed`` true, false, and null, masking, misses, and the route and the tool.

Example Village (tests/test_approvals.py): four fake owners on a fake PayHOA client. Nothing here reaches PayHOA,
Google, or Keeper, and nothing reads data/: every store is in ``tmp_path``.
"""

from __future__ import annotations

import copy
import json
import sqlite3
from contextlib import contextmanager
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest
import webclient

from jason.approvals import engine, evidence, model, store
from jason.approvals.evidence import CAVEAT, DOT, EvidenceKind, mask_field, resolve, rule_for
from jason.tasks import submission_cache
from test_approvals import (FIXTURES, FORMS, _approve_partly, _validator, village)  # noqa: F401 - fixtures
from test_web_approvals import web  # noqa: F401 - fixture

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


# --- the last full read of a request (payhoa-files/requests/N/submission.json) --------------------------------------------

QUESTIONS = {"7001": "delivery", "7002": "occupancy", "7003": "second-mailing-address"}


def _record(data_dir: Path) -> None:
    """The recorded PayHOA form with its question ids, as ``jason forms --payhoa`` writes it."""
    (data_dir / "payhoa").mkdir(exist_ok=True)
    (data_dir / "payhoa" / "forms.json").write_text(json.dumps({"forms": [{
        "key": "owner-info", "formId": 900, "title": "Owner information", "questions": QUESTIONS, "options": {}}]}),
        encoding="utf-8")


def _raw(sid: int, unit_id: int, unit: str, status: str = "pending", **answers: str) -> dict:
    """A raw ``get_form_submission`` answer: answers by question id, each with PayHOA's label."""
    ids = {v: k for k, v in QUESTIONS.items()}
    labels = {"delivery": "Delivery", "occupancy": "Occupancy", "second-mailing-address": "Second mailing address"}
    return {"submission": {"id": sid, "formId": 900, "status": status, "unitId": unit_id, "membershipId": 11,
                           "createdAt": "2026-10-05T00:00:00Z", "unit": {"id": unit_id, "title": unit},
                           "answers": [{"questionId": int(ids[k]), "answer": v, "question": {"label": labels[k]}}
                                       for k, v in answers.items()]}}


BEN = dict(delivery="By email", occupancy="Owner-occupied")                       # 502's answers, as the plan read them
CY = dict(BEN, **{"second-mailing-address": "PO Box 12, Example City"})              # 503's


def _keep(data_dir: Path, sid: int, raw: dict, *, read_at: str = "", via: str = "jason sync-request-files",
          status: str = "") -> Path:
    return submission_cache.write(submission_cache.files_dir(data_dir), sid, raw, via=via, read_at=read_at,
                                  status=status)


LATER = "2999-01-01T00:00:00+00:00"


class _FormsClient:
    """A fake PayHOA that reads one form's submissions: it lists them and answers each in full, and has no writes."""

    def __init__(self, raws: dict[int, dict]) -> None:
        self.raws, self.reads = raws, []

    def list_form_submissions(self, form_id):
        self.reads.append(("list", form_id))
        return [{"id": sid, "status": raw["submission"]["status"], "formId": form_id} for sid, raw in self.raws.items()]

    def get_form_submission(self, org, sid):
        self.reads.append(("get", sid))
        return copy.deepcopy(self.raws[sid])


def test_a_plans_live_read_keeps_each_submission_in_full(tmp_path, monkeypatch):
    from jason.tasks.owner_info_apply import gather_answers
    from jason.tasks.payhoa_forms import fetch_submissions, record_for

    _record(tmp_path)
    monkeypatch.setattr("jason.config.test_memberships", lambda *a, **k: set())
    raws = {502: _raw(502, 2, "102 EXAMPLE WAY", **BEN), 503: _raw(503, 3, "103 EXAMPLE WAY", status="complete", **CY)}
    client = _FormsClient(raws)
    answers, _ = gather_answers(tmp_path, FORMS, client, 1, via="jason owner-info --apply")
    assert {a.source: a.answers for a in answers}["payhoa:502"] == {"delivery": ["By email"],
                                                                    "occupancy": ["Owner-occupied"]}
    assert client.reads == [("list", 900), ("get", 502), ("get", 503)]              # one read each, nothing written
    kept = json.loads((tmp_path / "payhoa-files" / "requests" / "503" / "submission.json").read_text(encoding="utf-8"))
    assert kept == {**kept, "via": "jason owner-info --apply", "formId": 900, "formName": "Owner information",
                    "status": "complete", "submission": raws[503]}
    assert kept["readAt"].endswith("+00:00")
    assert not list((tmp_path / "payhoa-files" / "requests" / "503").glob("*.tmp"))     # written whole, then replaced
    # without keep, fetch_submissions answers as it always did
    same = fetch_submissions(_FormsClient(raws), 1, record_for(tmp_path, "owner-info"), FORMS.OWNER_INFO)
    assert [a.answers for a in same] == [a.answers for a in answers]


def test_the_last_read_opens_by_question_title_masked(village):
    _record(village.data_dir)
    _keep(village.data_dir, 503, _raw(503, 3, "103 EXAMPLE WAY", **CY), read_at="2026-10-06T00:00:00+00:00")
    out = resolve("payhoa:submission:503", data_dir=village.data_dir)
    _validator("evidence.schema.json").validate(out)
    last = _source(out, "Last read from PayHOA")
    assert out["found"] and last["readAt"] == "2026-10-06T00:00:00+00:00" and len(last["digest"]) == 64
    assert _field(last, "Status")["value"] == "pending" and _field(last, "Form")["value"] == "Owner information"
    assert _field(last, "Unit")["value"] == "103 EXAMPLE WAY" and _field(last, "Delivery")["value"] == "By email"
    assert _field(last, "Second mailing address") == {"name": "Second mailing address", "value": MASK, "masked": True}
    assert _field(last, "Occupancy") == {"name": "Occupancy", "value": MASK, "masked": True}    # the occupancy rule
    assert "PO Box" not in json.dumps(out) and "Owner-occupied" not in json.dumps(out)
    assert last["note"] == "Read by jason sync-request-files."
    assert out["refreshable"] == {"system": "PayHOA", "what": "Read this request again from PayHOA"}
    assert [r["command"] for r in out["refresh"]] == ["jason sync-request-files --requests 503",
                                                      "jason sync-catalog --only requests"]
    assert out["refresh"][0]["what"] == "re-read this request in full: its answers, comments, notes, and attachments"
    assert "jason sync-request-files --requests 503" in out["note"]                 # the request files, still missing


def test_a_form_the_profile_does_not_define_shows_payhoas_labels_masked_by_name(village):
    raw = {"submission": {"id": 610, "formId": 950, "status": "pending", "answers": [
        {"questionId": 1, "answer": "<p>The gutter at 102 EXAMPLE WAY leaks</p>", "question": {"label": "Message"}},
        {"questionId": 2, "answer": "ben@example.com", "question": {"label": "Email"}},
        {"questionId": 3, "answer": '<i class="fa fa-check-square-o"></i>', "label": "Photos attached"}]}}
    _keep(village.data_dir, 610, raw)
    last = _source(resolve("payhoa:submission:610", data_dir=village.data_dir), "Last read from PayHOA")
    assert _field(last, "Message")["value"] == "The gutter at 102 EXAMPLE WAY leaks"
    assert _field(last, "Email") == {"name": "Email", "value": f"b{MASK}@example.com", "masked": True}
    assert _field(last, "Photos attached")["value"] == "yes" and last["digest"] == ""
    assert "not compared" in last["note"]


def test_changed_between_the_plans_read_and_a_later_last_read(village):
    _record(village.data_dir)
    a = _plan(village)
    _keep(village.data_dir, 502, _raw(502, 2, "102 EXAMPLE WAY", **BEN), read_at=LATER)
    same = resolve("payhoa:submission:502", approval_id=a.id, data_dir=village.data_dir)
    _validator("evidence.schema.json").validate(same)
    assert same["changed"] is False and "same status and the answers" in same["changedNote"]
    snap = _source(same, "This plan's read")
    assert _source(same, "Last read from PayHOA")["digest"] == snap["digest"]       # the same read, the same digest
    _keep(village.data_dir, 502, _raw(502, 2, "102 EXAMPLE WAY", status="complete", **BEN), read_at=LATER)
    moved = resolve("payhoa:submission:502", approval_id=a.id, data_dir=village.data_dir)
    assert moved["changed"] is True and "status complete (the plan read pending)" in moved["changedNote"]
    assert "the answers" not in moved["changedNote"]
    _keep(village.data_dir, 502, _raw(502, 2, "102 EXAMPLE WAY", delivery="By mail", occupancy="Owner-occupied"),
          read_at=LATER)
    answered = resolve("payhoa:submission:502", approval_id=a.id, data_dir=village.data_dir)
    assert answered["changed"] is True and answered["changedNote"].endswith("differs from the plan's read: the answers.")
    _keep(village.data_dir, 502, _raw(502, 2, "102 EXAMPLE WAY", status="complete", **BEN),
          read_at="2000-01-01T00:00:00+00:00")
    before = resolve("payhoa:submission:502", approval_id=a.id, data_dir=village.data_dir)
    assert before["changed"] is None and "before the plan read" in before["changedNote"]
    # a catalog synced later still speaks: a later status there is a change even when the last read is older
    _catalog(village.data_dir, [(502, "complete")], synced_at=LATER)
    both = resolve("payhoa:submission:502", approval_id=a.id, data_dir=village.data_dir)
    assert both["changed"] is True and "The catalog, synced later" in both["changedNote"]


def test_a_last_read_that_cannot_be_opened_is_a_miss_naming_its_command(village):
    file = submission_cache.path_for(submission_cache.files_dir(village.data_dir), 502)
    file.parent.mkdir(parents=True)
    file.write_text("{not json", encoding="utf-8")
    out = resolve("payhoa:submission:502", data_dir=village.data_dir)
    _validator("evidence.schema.json").validate(out)
    assert not out["found"] and _source(out, "Last read from PayHOA") is None
    assert "could not be opened" in out["note"] and "jason sync-request-files --requests 502" in out["note"]
    assert _source(out, "Request files") is None                                     # a folder with no comments saved


# --- refresh one record ----------------------------------------------------------------------------------------------------

def _factory(client, org=1, fail: BaseException | None = None):
    from contextlib import contextmanager

    calls = []

    @contextmanager
    def factory():
        calls.append("live")
        if fail is not None:
            raise fail
        yield SimpleNamespace(client=client, org_id=org)
    factory.calls = calls
    return factory


def _log(data_dir: Path) -> list[dict]:
    file = data_dir / "evidence" / "refreshes.jsonl"
    return [json.loads(line) for line in file.read_text(encoding="utf-8").splitlines()] if file.is_file() else []


def test_a_refresh_reads_one_request_keeps_it_and_logs_who(village):
    _record(village.data_dir)
    a = _plan(village)
    client = _FormsClient({502: _raw(502, 2, "102 EXAMPLE WAY", status="complete", **BEN)})
    out = evidence.refresh("payhoa:submission:502", by="A Manager", approval_id=a.id, data_dir=village.data_dir,
                           client_factory=_factory(client))
    _validator("evidence.schema.json").validate(out)
    assert client.reads == [("get", 502)]                                            # one read, nothing written
    kept = submission_cache.read(submission_cache.files_dir(village.data_dir), 502)
    assert kept["via"] == "console refresh by A Manager" and kept["status"] == "complete" and kept["formId"] == 900
    assert kept["formName"] == "Owner information"                                   # the recorded form's title
    last = _source(out, "Last read from PayHOA")
    assert last["readAt"] == kept["readAt"] == out["refreshed"]["at"]
    assert out["refreshed"] == {"at": kept["readAt"], "by": "A Manager", "system": "PayHOA"}
    assert out["changed"] is True and "status complete" in out["changedNote"]
    assert _log(village.data_dir) == [{"at": kept["readAt"], "by": "A Manager", "address": "payhoa:submission:502",
                                       "system": "PayHOA", "ok": True, "error": ""}]
    assert "Owner-occupied" not in (village.data_dir / "evidence" / "refreshes.jsonl").read_text(encoding="utf-8")


def test_a_refresh_without_keeper_says_to_sign_in_and_is_logged(village):
    from jason.secrets import KeeperAuthRequired

    with pytest.raises(evidence.RefreshFailed) as failed:
        evidence.refresh("payhoa:submission:502", by="A Manager", data_dir=village.data_dir,
                         client_factory=_factory(None, fail=KeeperAuthRequired("device approval needed")))
    assert str(failed.value) == evidence.KEEPER_SIGN_IN and "jason login" in str(failed.value)
    assert [(e["ok"], e["error"]) for e in _log(village.data_dir)] == [(False, evidence.KEEPER_SIGN_IN)]
    assert submission_cache.read(submission_cache.files_dir(village.data_dir), 502) is None


@pytest.mark.parametrize("address, by, why", [
    ("CIV 4041", "A Manager", "no live refresher"),
    ("board-item:example", "A Manager", "no live refresher"),
    ("nothing:here", "A Manager", "no live refresher"),
    ("payhoa:submission:502", "  ", "names the person"),
])
def test_a_refresh_is_refused_for_a_kind_without_one_or_without_a_person(village, address, by, why):
    factory = _factory(_FormsClient({}))
    with pytest.raises(ValueError, match=why):
        evidence.refresh(address, by=by, data_dir=village.data_dir, client_factory=factory)
    assert factory.calls == [] and _log(village.data_dir) == []                      # refused before any sign-in
    if not address.startswith("payhoa:"):
        assert resolve(address, data_dir=village.data_dir)["refreshable"] is None


def test_the_refresh_route_is_a_guarded_write_that_reads_payhoa_once(web, monkeypatch):
    from jason.secrets import KeeperAuthRequired
    from jason.web.app import create_app
    from test_web_approvals import _dist

    _record(web.data_dir)
    a = _plan(web)
    monkeypatch.setattr(web.client, "get_form_submission",
                        lambda org, sid: _raw(sid, 2, "102 EXAMPLE WAY", status="complete", **BEN))
    url, body = "/api/evidence/refresh", {"address": "payhoa:submission:502", "approval": a.id, "by": "A Manager"}
    assert web.app.test_client().post(url, json=body).status_code == 403              # no Origin, no token
    assert web.c.post(url, json=body, headers={"X-Jason-Token": ""}).status_code == 403   # the header, not the cookie
    assert web.c.get(url).status_code in (404, 405) and web.factory.calls == []
    r = web.c.post(url, json=body)
    assert r.status_code == 200, r.json
    _validator("evidence.schema.json").validate(r.json)
    assert r.json["refreshed"]["by"] == "A Manager" and _source(r.json, "Last read from PayHOA")
    assert r.json["changed"] is True and web.factory.calls == ["evidence-refresh"] and web.client.writes == []
    assert "Owner-occupied" not in json.dumps(r.json)                                  # masked on the way out
    citation = web.c.post(url, json={"address": "CIV 4041", "by": "A Manager"})
    assert citation.status_code == 400 and "no live refresher" in citation.json["error"]
    assert web.c.post(url, json={**body, "by": ""}).status_code == 400

    @contextmanager
    def no_keeper(kind):
        raise KeeperAuthRequired("device approval needed")
        yield  # pragma: no cover

    locked_out = webclient.client(create_app(_dist(web.data_dir), None, approvals_live=no_keeper))
    r = locked_out.post(url, json=body)
    assert r.status_code == 409 and "run `jason login` in a terminal" in r.json["error"]
    off = webclient.client(create_app(_dist(web.data_dir), None, approvals_live=None))
    assert off.post(url, json=body).status_code == 405


# --- refresh every record of one plan --------------------------------------------------------------------------------------

REQUESTS = (501, 502, 503, 504)


def _raws() -> dict[int, dict]:
    return {sid: _raw(sid, sid - 500, f"10{sid - 500} EXAMPLE WAY", status="complete", **BEN) for sid in REQUESTS}


def _addresses(a) -> list[str]:
    return [e.address for e in list(a.evidence) + [e for i in a.items for e in i.evidence]]


def test_refresh_all_reads_each_request_once_on_one_sign_in(village, monkeypatch):
    import jason.locks

    _record(village.data_dir)
    a = _plan(village)
    rows = [x for x in _addresses(a) if x.startswith("payhoa:submission:")]
    assert len(rows) > len(set(rows))                                                # the plan names some twice
    holds, real = [], jason.locks.hold
    monkeypatch.setattr("jason.locks.hold", lambda *args, **kw: (holds.append(args), real(*args, **kw))[1])
    client = _FormsClient(_raws())
    factory = _factory(client)
    out = evidence.refresh_all(a.id[:12], by="A Manager", data_dir=village.data_dir, client_factory=factory)
    want = list(dict.fromkeys(rows))                                                 # distinct, in plan order
    assert factory.calls == ["live"] and len(holds) == 1                             # one sign-in, one hold
    assert client.reads == [("get", int(x.rsplit(":", 1)[1])) for x in want]         # each once, nothing written
    assert out["approval"] == a.id and out["by"] == "A Manager" and out["at"].endswith("+00:00")
    assert out["refreshed"] == want and out["failed"] == []
    others = {x for x in _addresses(a) if x and not x.startswith("payhoa:submission:")}
    assert out["skipped"] == len(others) > 0                                         # citations, commands: counted
    for sid in REQUESTS:
        kept = submission_cache.read(submission_cache.files_dir(village.data_dir), sid)
        assert kept["via"] == "console refresh by A Manager" and kept["status"] == "complete"
    log = _log(village.data_dir)
    assert [e["address"] for e in log] == want                                       # one line each
    assert all(e["ok"] and e["by"] == "A Manager" and e["batch"] == a.id and e["system"] == "PayHOA" for e in log)
    assert "Owner-occupied" not in json.dumps(out) + json.dumps(log)
    opened = resolve("payhoa:submission:502", approval_id=a.id, data_dir=village.data_dir)
    assert opened["changed"] is True and "status complete" in opened["changedNote"]


def test_refresh_all_puts_a_failed_read_in_failed_and_goes_on(village):
    _record(village.data_dir)
    a = _plan(village)
    raws = _raws()
    del raws[502]                                                                    # PayHOA has no 502 to answer
    client = _FormsClient(raws)
    out = evidence.refresh_all(a.id, by="A Manager", data_dir=village.data_dir, client_factory=_factory(client))
    assert "payhoa:submission:502" not in out["refreshed"] and len(out["refreshed"]) == 3
    assert [f["address"] for f in out["failed"]] == ["payhoa:submission:502"]
    assert out["failed"][0]["error"].startswith("PayHOA could not be read: KeyError")
    assert submission_cache.read(submission_cache.files_dir(village.data_dir), 502) is None
    assert submission_cache.read(submission_cache.files_dir(village.data_dir), 504) is not None   # read after it
    assert [(e["address"], e["ok"]) for e in _log(village.data_dir) if not e["ok"]] == [("payhoa:submission:502",
                                                                                          False)]


def test_refresh_all_without_keeper_raises_before_any_read(village):
    from jason.secrets import KeeperAuthRequired

    a = _plan(village)
    factory = _factory(None, fail=KeeperAuthRequired("device approval needed"))
    with pytest.raises(evidence.RefreshFailed) as failed:
        evidence.refresh_all(a.id, by="A Manager", data_dir=village.data_dir, client_factory=factory)
    assert str(failed.value) == evidence.KEEPER_SIGN_IN and factory.calls == ["live"]
    assert all(submission_cache.read(submission_cache.files_dir(village.data_dir), sid) is None for sid in REQUESTS)
    log = _log(village.data_dir)
    assert len(log) == len(REQUESTS) and all(not e["ok"] and e["error"] == evidence.KEEPER_SIGN_IN for e in log)


@pytest.mark.parametrize("ident, by, why", [
    ("apr-none", "A Manager", "no approval apr-none"),
    ("", "A Manager", "name the approval"),
    (None, "  ", "names the person"),
])
def test_refresh_all_refuses_no_person_or_no_approval(village, ident, by, why):
    a = _plan(village)
    factory = _factory(_FormsClient(_raws()))
    with pytest.raises(ValueError, match=why):
        evidence.refresh_all(a.id if ident is None else ident, by=by, data_dir=village.data_dir,
                             client_factory=factory)
    assert factory.calls == [] and _log(village.data_dir) == []


def test_refresh_all_refuses_a_batch_over_the_cap_and_signs_in_for_none(village, monkeypatch):
    a = _plan(village)
    assert evidence.MAX_BATCH == 200
    monkeypatch.setattr(evidence, "MAX_BATCH", 3)
    factory = _factory(_FormsClient(_raws()))
    with pytest.raises(ValueError, match="names 4 records to read again; one batch reads at most 3"):
        evidence.refresh_all(a.id, by="A Manager", data_dir=village.data_dir, client_factory=factory)
    assert factory.calls == [] and _log(village.data_dir) == []


def test_refresh_all_with_nothing_refreshable_skips_without_a_sign_in(village):
    a = _plan(village)
    file = store._file(village.data_dir, a.id)
    raw = json.loads(file.read_text(encoding="utf-8"))
    raw["evidence"] = [{"label": "Civil Code 4041", "address": "CIV 4041"},
                       {"label": "Civil Code 4041 again", "address": "CIV 4041"}]
    for item in raw["items"]:
        item["evidence"] = [e for e in item.get("evidence") or () if not e["address"].startswith("payhoa:")]
    file.write_text(json.dumps(raw), encoding="utf-8")
    factory = _factory(_FormsClient(_raws()))
    out = evidence.refresh_all(a.id, by="A Manager", data_dir=village.data_dir, client_factory=factory)
    assert out["refreshed"] == [] and out["failed"] == [] and out["skipped"] >= 1
    assert factory.calls == [] and _log(village.data_dir) == []


def test_the_refresh_all_route_is_a_guarded_write_on_one_sign_in(web, monkeypatch):
    from jason.secrets import KeeperAuthRequired
    from jason.web.app import create_app
    from test_web_approvals import _dist

    _record(web.data_dir)
    a = _plan(web)
    reads = []

    def answer(org, sid):
        reads.append(sid)
        if sid == 503:
            raise RuntimeError("PayHOA answered 500 for owner ana@example.com")
        return _raw(sid, sid - 500, "102 EXAMPLE WAY", status="complete", **BEN)
    monkeypatch.setattr(web.client, "get_form_submission", answer)
    url, body = "/api/evidence/refresh-all", {"approval": a.id, "by": "A Manager"}
    assert web.app.test_client().post(url, json=body).status_code == 403              # no Origin, no token
    assert web.c.post(url, json=body, headers={"X-Jason-Token": ""}).status_code == 403   # the header, not the cookie
    assert web.c.get(url).status_code in (404, 405) and web.factory.calls == [] and reads == []
    r = web.c.post(url, json=body)
    assert r.status_code == 200, r.json
    assert set(r.json) == {"approval", "by", "at", "refreshed", "failed", "skipped"}
    assert r.json["approval"] == a.id and r.json["by"] == "A Manager" and r.json["skipped"] > 0
    assert sorted(r.json["refreshed"]) == [f"payhoa:submission:{s}" for s in sorted(set(reads)) if s != 503]
    assert r.json["failed"][0]["address"] == "payhoa:submission:503" and "ana@example.com" not in json.dumps(r.json)
    assert web.factory.calls == ["evidence-refresh"] and web.client.writes == [] and len(reads) == len(set(reads))
    assert "Owner-occupied" not in json.dumps(r.json)                                  # no answers come back
    assert web.c.post(url, json={**body, "by": ""}).status_code == 400
    missing = web.c.post(url, json={**body, "approval": "apr-none"})
    assert missing.status_code == 400 and "no approval apr-none" in missing.json["error"]

    @contextmanager
    def no_keeper(kind):
        raise KeeperAuthRequired("device approval needed")
        yield  # pragma: no cover

    locked_out = webclient.client(create_app(_dist(web.data_dir), None, approvals_live=no_keeper))
    r = locked_out.post(url, json=body)
    assert r.status_code == 409 and r.json["error"] == evidence.KEEPER_SIGN_IN
    off = webclient.client(create_app(_dist(web.data_dir), None, approvals_live=None))
    assert off.post(url, json=body).status_code == 405
