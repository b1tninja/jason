"""The Controls loaders and writer (``jason.web.extra.controls``): the safeguards the board opts into, read by a signed-in
person whose offices open P2, and the one write that puts a suggestion before the board in the signer's name. Made-up bylaws,
roster, and data folder; nothing is reached."""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest
import webclient

from controls_support import make, one_person_kind, roster  # noqa: F401 - fixture
from controls_world import Home, write_outline
from jason.community.base import OfficerRole as R
from jason.controls import store, suggest
from jason.controls.types import ControlAct, Scope, ScopeKind

ROWS = webclient.ROSTER + (("Rae Roster", "", "rae@example.org", False),)
LOADERS = ("controls", "control", "control-notices")


@pytest.fixture
def home():
    return Home(duties=True)


@pytest.fixture
def world(tmp_path, monkeypatch, home):
    monkeypatch.setenv("JASON_SPEC_DIR", str(tmp_path / "spec"))
    monkeypatch.setattr("jason.mcp.county._data_dir", lambda d=None: tmp_path)
    monkeypatch.setattr("jason.community.community", lambda: home)
    write_outline(tmp_path)
    return tmp_path


@pytest.fixture
def app(world):
    from jason.web.app import create_app
    from jason.web.extra import controls as ctl

    dist = world / "dist"
    dist.mkdir(exist_ok=True)
    loaders = {"controls": ctl.controls, "control": ctl.control, "control-notices": ctl.control_notices}
    return create_app(dist, loaders, approvals_live=None, extra_writes=True,
                      sign_in=webclient.roster_sign_in(ROWS, dev=True))


def read_documents(world, home):
    """The reader's suggestions recorded as suggested acts, the way ``jason controls --suggest --record`` does."""
    found = suggest.suggest(home, suggest.ShelfDocuments(home, world), duties_read=True, prior=())
    suggest.record(found, by="A Secretary", data_dir=world, community=home)
    return found


def as_(app, name):
    return webclient.sign_in(webclient.client(app), name, rows=ROWS)


def adopt(world, key, ctype, params, *, scope=None, effective="2020-01-01"):
    c = make(ctype, params, key=key, scope=scope or Scope())
    store.record(ControlAct.SUGGEST, key, by="jason", why="found", control=c, data_dir=world)
    store.record(ControlAct.PROPOSE, key, by="A Secretary", why="to the board", data_dir=world)
    store.record(ControlAct.ADOPT, key, by="A Secretary", why="voted", decision="dec-1", effective=effective,
                 data_dir=world, now=datetime(2099, 1, 1, tzinfo=timezone.utc))


# --- who may open them --------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("name", LOADERS)
def test_signed_out_is_a_401_and_a_roster_person_with_no_office_or_an_admin_with_none_is_a_403(app, name):
    url = f"/api/{name}?key=x&subject=y"
    assert webclient.client(app).get(url).status_code == 401
    for who in ("Rae Roster", "Ada Admin"):
        r = as_(app, who).get(url)
        assert r.status_code == 403, who
        assert "open contact details and members' submissions (P2)" in r.json["error"]      # access.may_see's sentence


@pytest.mark.parametrize("who", ("Pat Example", "Dana Director", "Sam Secretary", "Lee President", "Vic Vice", "A Manager"))
def test_any_board_office_and_the_manager_read(app, world, home, who):
    read_documents(world, home)
    r = as_(app, who).get("/api/controls")
    assert r.status_code == 200 and r.json["found"] is True and r.json["counts"]["suggested"] == 3


def test_the_owner_view_never_reads_them(app):
    c = as_(app, "Pat Example")
    for name in LOADERS:
        assert c.get(f"/api/{name}?view=owner").status_code == 403


def test_they_are_registered_and_no_owner_source():
    from jason.web.extra.owner_view import OWNER_SOURCES
    from jason.web.sources import EXTRA_LOADERS, EXTRA_WRITERS

    for name in LOADERS:
        assert name not in OWNER_SOURCES
        assert EXTRA_LOADERS[name].startswith("jason.web.extra.controls:")
    assert EXTRA_WRITERS["controls"] == "jason.web.extra.controls:write"


# --- the list ------------------------------------------------------------------------------------------------------------------

def test_an_empty_store_says_the_documents_have_not_been_read(app):
    body = as_(app, "Pat Example").get("/api/controls").json
    assert body["empty"] == "jason has not read your governing documents. Ingest them from Onboarding."
    assert body["counts"]["total"] == 0 and body["families"] == [] and body["label"] == "jason suggests; the board adopts"


def test_a_suggestion_carries_the_provision_whole_before_jasons_labeled_reading_and_is_never_in_force(app, world, home):
    read_documents(world, home)
    body = as_(app, "Pat Example").get("/api/controls").json
    assert body["empty"] == "" and body["readingLabel"] == "jason's reading, not the provision"
    assert [g["family"] for g in body["families"]] == ["money", "contracts"]
    row = next(r for g in body["families"] for r in g["controls"] if r["key"] == "payment-signers")
    assert row["basis"]["citation"] == "Example Bylaws Section 9.1"
    assert row["basis"]["words"].endswith("All checks, drafts, or orders for payment shall be signed by two directors.")
    assert row["basis"]["floor"] == {"signers": 2} and row["floor"]["read"] is True
    assert row["reading"].startswith("jason's reading, not the provision") and row["readingLabel"] == body["readingLabel"]
    assert row["state"] == "suggested" and row["standing"] == "suggested" and row["stateWord"] == "suggested"
    assert row["inForce"]["ok"] is False and row["effective"] == "" and row["decision"] is None
    assert row["proposedAs"] is None and row["boardSets"] == ["over_cents"]
    assert row["history"][0]["act"] == "suggest" and row["history"][0]["by"] == "jason"
    assert {"kind": "approval kind", "key": None} == {k: row["touches"][0][k] for k in ("kind", "key")}
    assert "carries this category" in row["touches"][0]["note"]               # no registered kind names "payment" yet
    assert body["counts"]["suggested"] == 3 and "3 suggested" in body["heading"] and "1 question" in body["heading"]


def test_the_roster_check_names_offices_and_counts_never_a_person(app, world, home):
    read_documents(world, home)
    text = as_(app, "Pat Example").get("/api/controls").get_data(as_text=True)
    assert "Person " not in text                                                    # FULL's made-up names
    row = next(r for r in json.loads(text)["controls"] if r["key"] == "payment-signers")
    assert row["roster"]["needs"] == [{"office": "board member", "count": 2}, {"office": "treasurer", "count": 1}]
    assert row["roster"]["missing"] == [] and row["missing"] == []
    assert all(set(s) == {"office", "count"} for s in row["roster"]["seated"])
    home._roster = tuple(roster(R.DIRECTOR))
    row = next(r for r in as_(app, "Pat Example").get("/api/controls").json["controls"] if r["key"] == "payment-signers")
    assert row["missing"] == ["board member", "treasurer"] and row["roster"]["lacks"]


def test_a_question_is_listed_apart_and_is_not_a_control(app, world, home):
    read_documents(world, home)
    body = as_(app, "Pat Example").get("/api/controls").json
    assert len(body["questions"]) == 1 and body["questions"][0]["kind"] == "question"
    q = body["questions"][0]
    assert q["citation"] == "Example Bylaws Section 9.4" and q["question"] and q["key"] == ""
    assert "Drafts on the Association are kept by the treasurer" in q["words"]
    assert all(r["key"] for g in body["families"] for r in g["controls"])
    assert body["counts"]["total"] == 3 and body["counts"]["questions"] == 1


def test_the_filters_and_a_bad_filter_is_a_400(app, world, home):
    read_documents(world, home)
    c = as_(app, "Pat Example")
    assert [r["key"] for r in c.get("/api/controls?family=contracts").json["controls"]] == ["contract-authorization"]
    assert c.get("/api/controls?state=adopted").json["controls"] == []
    assert c.get("/api/controls?family=nope").status_code == 400
    assert c.get("/api/controls?state=nope").status_code == 400


def test_an_adopted_control_is_in_force_only_from_its_date_and_says_when_the_roster_cannot_satisfy_it(app, world, home):
    adopt(world, "pay-now", "payment-signers", {"signers": 2}, effective="2020-01-01")
    adopt(world, "pay-later", "payment-signers", {"signers": 2, "must_include": [R.TREASURER]}, effective="2099-12-01")
    home._roster = tuple(roster(R.PRESIDENT, R.DIRECTOR))
    body = as_(app, "Pat Example").get("/api/controls").json
    rows = {r["key"]: r for r in body["controls"]}
    assert rows["pay-now"]["standing"] == "in-force" and rows["pay-now"]["stateWord"] == "adopted, in force since 2020-01-01"
    assert rows["pay-later"]["standing"] == "adopted-not-in-force" and "takes effect 2099-12-01" in rows["pay-later"]["stateWord"]
    assert rows["pay-later"]["inForce"]["ok"] is False and rows["pay-later"]["inForce"]["lacks"]
    assert rows["pay-now"]["decision"] == {"id": "dec-1"}
    assert body["counts"]["adopted"] == 2 and body["counts"]["inForce"] == 1 and body["counts"]["adoptedNotInForce"] == 1
    home._roster = tuple(roster(R.PRESIDENT))                       # a seat falls vacant: in force, and cannot be satisfied
    row = next(r for r in as_(app, "Pat Example").get("/api/controls").json["controls"] if r["key"] == "pay-now")
    assert row["standing"] == "in-force-roster-lacks" and "refused" in row["stateWord"]


def test_a_broken_store_is_said_not_shown_as_adopted(app, world):
    (world / "controls").mkdir()
    (world / "controls" / "acts.jsonl").write_text(json.dumps({"key": "x", "act": "adopt", "by": "A", "why": "w", "seq": 1,
                                                               "at": "t", "prev": "", "hash": "h"}) + "\n", encoding="utf-8")
    r = as_(app, "Pat Example").get("/api/controls")
    assert r.status_code == 400 and "cannot adopt" in r.json["error"]


# --- one control ---------------------------------------------------------------------------------------------------------------

def test_one_control_with_its_provision_as_the_documents_hold_it_now(app, world, home):
    read_documents(world, home)
    body = as_(app, "Pat Example").get("/api/control?key=payment-signers").json
    assert body["found"] is True and body["control"]["key"] == "payment-signers"
    assert body["provision"]["found"] is True and body["provision"]["citation"] == "Example Bylaws Section 9.1"
    assert body["control"]["changed"] is None
    assert as_(app, "Pat Example").get("/api/control?key=nope").json == {"found": False, "key": "nope", "note": "no control nope"}
    assert as_(app, "Pat Example").get("/api/control").status_code == 400


def test_a_provision_that_changed_since_the_control_was_recorded_is_flagged_and_the_control_stays(app, world, home):
    read_documents(world, home)
    write_outline(world, (("9.1", "Checks", "9.1 Checks. All checks, drafts, or orders for payment shall be signed by three "
                                              "directors."),))
    body = as_(app, "Pat Example").get("/api/control?key=payment-signers").json
    ch = body["control"]["changed"]
    assert "two directors" in ch["was"] and "three directors" in ch["now"] and ch["basis"] == "the governing documents' date"
    assert body["control"]["state"] == "suggested" and body["control"]["basis"]["words"] == ch["was"]


# --- the notice at the point of an act -----------------------------------------------------------------------------------------------

def test_a_notice_gives_the_effective_rule_where_it_came_from_and_the_controls_waiting(app, world, one_person_kind):
    adopt(world, "pay-now", "payment-signers", {"signers": 2}, scope=Scope(ScopeKind.KIND, one_person_kind.key))
    adopt(world, "pay-later", "payment-signers", {"signers": 2}, scope=Scope(ScopeKind.KIND, one_person_kind.key),
          effective="2099-12-01")
    body = as_(app, "Pat Example").get(f"/api/control-notices?subject={one_person_kind.key}").json
    assert body["found"] and body["builtin"] == "one person" and body["stricter"] is True
    assert "two signers: the board adopted this on" in body["why"] and "one person: the kind's own rule" in body["why"]
    assert [c["key"] for c in body["controls"]] == ["pay-now"] and body["controls"][0]["link"] == "#/controls?key=pay-now"
    assert [w["key"] for w in body["waiting"]] == ["pay-later"] and "not in force until 2099-12-01" in body["waiting"][0]["reason"]
    assert body["second"] == {"always": True, "aboveCents": None} and body["refusals"] == []


def test_a_notice_names_a_control_in_force_the_roster_cannot_satisfy_and_never_shows_a_suggestion(app, world, home,
                                                                                                 one_person_kind):
    read_documents(world, home)                                     # suggestions only: no notice
    scope = Scope(ScopeKind.KIND, one_person_kind.key)
    quiet = as_(app, "Pat Example").get(f"/api/control-notices?subject={one_person_kind.key}").json
    assert quiet["controls"] == [] and quiet["waiting"] == [] and quiet["stricter"] is False
    adopt(world, "pay-now", "payment-signers", {"signers": 2, "must_include": [R.TREASURER]}, scope=scope)
    home._roster = tuple(roster(R.PRESIDENT, R.DIRECTOR))
    body = as_(app, "Pat Example").get(f"/api/control-notices?subject={one_person_kind.key}").json
    assert body["refusals"] and "the roster has no treasurer" in body["refusals"][0] and "Person" not in json.dumps(body)


def test_a_notice_for_a_workflow_step_lists_the_adopted_controls_that_govern_it(app, world):
    adopt(world, "authorize", "contract-authorization", {"resolution_first": True})
    body = as_(app, "Pat Example").get("/api/control-notices?subject=contract-signing").json
    assert body["found"] and [c["key"] for c in body["controls"]] == ["authorize"] and body["subjectKind"] == "step or send"
    assert as_(app, "Pat Example").get("/api/control-notices?subject=notice-letter").json["controls"] == []
    assert as_(app, "Pat Example").get("/api/control-notices?subject=nothing-known").status_code == 400
    assert as_(app, "Pat Example").get("/api/control-notices").status_code == 400


# --- the one write ---------------------------------------------------------------------------------------------------------------

def post(c, key, body=None):
    return c.post(f"/api/write/controls/{key}", json={"act": "propose"} if body is None else body)


def test_the_writer_needs_a_sign_in_and_an_office(app, world, home):
    read_documents(world, home)
    assert post(webclient.client(app), "payment-signers").status_code == 401
    assert post(as_(app, "Rae Roster"), "payment-signers").status_code == 403
    assert post(as_(app, "Ada Admin"), "payment-signers").status_code == 403
    assert store.get("payment-signers", world).state.value == "suggested"


def test_propose_makes_a_board_item_in_the_signers_name_and_changes_no_control_to_adopted(app, world, home):
    from jason.tasks import board_items

    read_documents(world, home)
    r = post(as_(app, "Pat Example"), "payment-signers")
    assert r.status_code == 200, r.json
    assert r.json["item"] == "control-payment-signers" and r.json["state"] == "proposed" and r.json["refreshed"] is False
    assert r.json["control"]["state"] == "proposed" and r.json["control"]["proposedAs"] == "control-payment-signers"
    item = next(i for i in board_items.load(world) if i.id == "control-payment-signers")
    assert item.status.value == "proposed" and item.authority == "Example Bylaws Section 9.1"
    assert any("signed by two directors" in e for e in item.evidence)          # the provision, as the item's evidence
    c = store.get("payment-signers", world)
    assert c.history[-1].act is ControlAct.PROPOSE and c.history[-1].by == "Pat Example"
    assert {x.state.value for x in store.load(world)} <= {"suggested", "proposed"}           # nothing adopted
    assert all(x.decision == "" and x.effective is None for x in store.load(world))
    again = post(as_(app, "Dana Director"), "payment-signers")
    assert again.status_code == 200 and again.json["refreshed"] is True
    assert len([i for i in board_items.load(world) if i.id.startswith("control-")]) == 1
    listed = as_(app, "Pat Example").get("/api/controls").json
    assert next(r for r in listed["controls"] if r["key"] == "payment-signers")["proposedAs"] == "control-payment-signers"


def test_a_body_by_naming_someone_else_is_refused_and_the_signed_name_is_used(app, world, home):
    read_documents(world, home)
    c = as_(app, "Pat Example")
    assert post(c, "payment-signers", {"act": "propose", "by": "Somebody Else"}).status_code == 403
    assert store.get("payment-signers", world).state.value == "suggested"
    assert post(c, "payment-signers", {"act": "propose", "by": "Pat Example"}).status_code == 200
    assert store.get("payment-signers", world).history[-1].by == "Pat Example"


def test_nobody_writes_while_an_admin_views_as_someone_else(app, world, home):
    read_documents(world, home)
    c = as_(app, "Ada Admin")
    with c.session_transaction() as s:
        s["acting"] = {"name": "Pat Example", "role": "treasurer"}
    assert post(c, "payment-signers").status_code in (403, 405)
    assert store.get("payment-signers", world).state.value == "suggested"


def test_no_other_act_is_taken_here_adopting_included(app, world, home):
    read_documents(world, home)
    c = as_(app, "Pat Example")
    for act in ("adopt", "decline", "defer", "retire", "approve", ""):
        r = post(c, "payment-signers", {"act": act})
        assert r.status_code == 400 and "board's decisions" in r.json["error"], act
    assert post(c, "payment-signers", {}).status_code == 400
    assert store.get("payment-signers", world).state.value == "suggested"


def test_an_unknown_key_is_a_404_and_a_deferred_control_may_not_be_asked_before_its_date_and_leaves_nothing(app, world, home):
    from jason.tasks import board_items

    read_documents(world, home)
    c = as_(app, "Pat Example")
    assert post(c, "nope").status_code == 404
    assert post(c, "reserve-signers").status_code == 200
    store.record(ControlAct.DEFER, "reserve-signers", by="A Secretary", why="later", again_on="2099-01-01", data_dir=world)
    items = len(board_items.load(world))
    r = post(c, "reserve-signers")
    assert r.status_code == 400 and "may be asked again on 2099-01-01" in r.json["error"]
    assert len(board_items.load(world)) == items and store.get("reserve-signers", world).state.value == "deferred"
