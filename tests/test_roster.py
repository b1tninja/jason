"""The board roster kept as it changes (jason.community.roster): onboarding's board-roster question records a change of
office the board made (high stakes: a second person confirms), appended to the officers topic with the minutes that
record it, and the election-status question records each seat's term with its election record. Made-up people, a
made-up queue, and tmp private facts folders; the fixture topics in tests/fixtures/spec are read, never written."""

from __future__ import annotations

import json
from datetime import date
from types import SimpleNamespace

import pytest
import webclient

from jason.community import Community, community, intake
from jason.community.base import OfficerRole, SeatKind, Term
from jason.community.intake import AskKind, AskStatus
from jason.community.onboarding import Context, FactRecord, ItemResult, Status, item
from jason.community.roster import FormError, change_rows, in_force, term_rows, terms_of
from jason.tasks import intake as intake_task
from jason.tasks import onboarding_answers as answers
from jason.tasks import onboarding_session as session

CHANGE = "Secretary; Pat Sample; 2099-05-01; Minutes of the sample board meeting, 2099-05-01"


def _stub():
    members = {name: (lambda self, *a, **k: ()) for name in Community.__abstractmethods__}
    members.update(name="Oakview Example Association", slug="oakview", org_id=0, root=None,
                   document_sync_rules=lambda self: {"rules": [], "exclude": []})
    return type("Oakview", (Community,), members)()


def _asked(key: str, status: Status, tmp_path):
    """The FACT onboarding generates for this item at this status (None when it asks nothing)."""
    ctx = Context(community=_stub(), profile="oakview")
    return next(iter(session.fact_asks([ItemResult(item(key), status)], ctx, tmp_path)), None)


# --- The questions ----------------------------------------------------------------------------------------------------

def test_the_board_roster_question_has_stakes_and_a_private_topic():
    ask = item("board-roster").ask
    assert ask is not None and ask.stakes and ask.record is FactRecord.PRIVATE and ask.topic == "officers"
    for words in ("office", "board act", "minutes", "OFFICE; PERSON; YYYY-MM-DD; MINUTES"):
        assert words in ask.question
    terms = item("election-status").ask
    assert terms is not None and terms.stakes and terms.record is FactRecord.PRIVATE and terms.topic == "terms"
    for words in ("seat", "start", "at the pleasure of the board", "inspector of elections' report", "provision"):
        assert words in terms.question
    assert item("election-status").private


def test_a_standing_question_is_asked_even_when_its_item_is_present(tmp_path):
    a = _asked("board-roster", Status.PRESENT, tmp_path)
    assert a is not None and a.subject == "fact:board-roster" and a.stakes and intake.high_stakes(a)
    assert a.detail["topic"] == "officers" and a.detail["record"] == FactRecord.PRIVATE.value
    assert _asked("tax-id", Status.PRESENT, tmp_path) is None                  # not standing: present asks nothing


def test_an_answer_not_in_the_form_is_refused_and_not_stored(tmp_path):
    a = _asked("board-roster", Status.PRESENT, tmp_path)
    for text in ("Pat Sample is the secretary now", "Treasurer-ish; Pat Sample; 2099-05-01; minutes",
                 "Secretary; Pat Sample; May 1; minutes", "Secretary; Pat Sample; 2099-05-01; "):
        with pytest.raises(ValueError, match="form"):
            intake.answer([a], a.id, text, "A Person")
    assert a.status is AskStatus.OPEN and not a.answer
    assert intake.answer([a], a.id, "dismiss", "A Person").status is AskStatus.DISMISSED


# --- The route: queued, and a second person confirms ----------------------------------------------------------------

@pytest.fixture
def web(tmp_path, monkeypatch):
    from jason.web.app import create_app

    data = tmp_path / "data"
    data.mkdir()
    dist = tmp_path / "dist"
    dist.mkdir()
    monkeypatch.setattr("jason.mcp.county._data_dir", lambda d: data)
    ask = _asked("board-roster", Status.PRESENT, tmp_path)
    intake.save(data, [ask])
    app = create_app(dist, approvals_live=None, sign_in=webclient.roster_sign_in(dev=True))
    return app, data, ask


def _files(data):
    return sorted(p.relative_to(data).as_posix() for p in data.rglob("*") if p.is_file())


def test_a_change_of_office_is_queued_and_waits_on_a_second_person(web):
    app, data, ask = web
    first = webclient.sign_in(webclient.client(app), "Pat Example")
    bad = first.post(f"/api/write/intake/{ask.id}", json={"answer": "Pat Sample took over", "by": "Pat Example"})
    assert bad.status_code == 400 and "form" in bad.json["error"]
    out = first.post(f"/api/write/intake/{ask.id}", json={"answer": CHANGE, "by": "Pat Example"})
    assert out.status_code == 200, out.json
    assert out.json["highStakes"] is True and out.json["needsConfirmation"] is True and out.json["applied"] is False
    assert out.json["confirm"].startswith(f"jason onboard --confirm {ask.id}")
    same = first.post(f"/api/write/intake/{ask.id}", json={"confirm": True, "by": "Pat Example"})
    assert same.status_code == 400 and "second person" in same.json["error"]
    second = webclient.sign_in(webclient.client(app), "Lee President")
    ok = second.post(f"/api/write/intake/{ask.id}", json={"confirm": True, "by": "Lee President"})
    assert ok.status_code == 200 and ok.json["confirmedBy"] == "Lee President" and ok.json["applied"] is False
    stored = next(a for a in intake.load(data) if a.id == ask.id)
    assert stored.status is AskStatus.ANSWERED and stored.confirmed_by == "Lee President"
    assert _files(data) == ["intake/asks.json"]                       # queued only: no private facts written


# --- Applying: appended to the officers topic, in force for the office --------------------------------------------

ROSTER = [{"role": ["secretary", "treasurer"], "name": "Tess Sample"}, {"role": "president", "name": "Lee Sample"},
          {"role": "director", "name": "Dana Sample"}]


def test_apply_appends_the_change_and_the_new_holder_is_in_force(tmp_path):
    spec = tmp_path / "spec"
    (spec / "oakview").mkdir(parents=True)
    topic = spec / "oakview" / "officers.json"
    topic.write_text(json.dumps(ROSTER), encoding="utf-8")
    ask = _asked("board-roster", Status.PRESENT, tmp_path)
    asks = [ask]
    intake.answer(asks, ask.id, CHANGE, "A Person")
    refused: list = []
    assert intake_task.apply(asks, tmp_path, refused=refused, profile="oakview", spec_dir=spec) == []
    assert "second person" in refused[0][1] and json.loads(topic.read_text(encoding="utf-8")) == ROSTER
    intake.confirm(asks, ask.id, "B Person")
    shown: list = []
    assert intake_task.apply(asks, tmp_path, shown=shown, profile="oakview", spec_dir=spec) == [ask]
    rows = json.loads(topic.read_text(encoding="utf-8"))
    assert rows[:3] == ROSTER                                          # nothing already there is changed
    added = rows[3]
    assert added["role"] == "secretary" and added["name"] == "Pat Sample" and added["acted"] == "2099-05-01"
    assert added["source"].startswith("Minutes") and added["answered_by"] == "A Person" and added["confirmed_by"] == "B Person"
    assert ask.status is AskStatus.APPLIED and "officers" in ask.applied_to
    assert len(list((spec / "backups").glob("oakview-officers-*.json"))) == 1
    assert '"acted": "2099-05-01"' in shown[0][1]
    held = {(role, row["name"]) for role, row in in_force(rows)}
    assert held == {("secretary", "Pat Sample"), ("treasurer", "Tess Sample"), ("president", "Lee Sample"),
                    ("director", "Dana Sample")}
    # The same answer again adds nothing; a later change is answered on the same question and appended.
    assert answers.apply_fact(ask, profile="oakview", data_dir=tmp_path, spec_dir=spec).record.startswith("already")
    intake.answer(asks, ask.id, "Secretary; vacant; 2099-07-01; Minutes of the sample board meeting, 2099-07-01",
                  "A Person")
    intake.confirm(asks, ask.id, "B Person")
    assert intake_task.apply(asks, tmp_path, profile="oakview", spec_dir=spec) == [ask]
    held = {role for role, _ in in_force(json.loads(topic.read_text(encoding="utf-8")))}
    assert "secretary" not in held and "treasurer" in held


def test_a_change_goes_to_the_topic_file_the_profile_reads(tmp_path):
    """The default profile's officers kept at the older spec/officers.json: the change is appended there, not to a new
    file that would hide it."""
    spec = tmp_path / "spec"
    spec.mkdir()
    (spec / "officers.json").write_text(json.dumps(ROSTER), encoding="utf-8")
    ask = _asked("board-roster", Status.PRESENT, tmp_path)
    intake.answer([ask], ask.id, CHANGE, "A Person")
    assert answers.apply_fact(ask, profile="mystique", data_dir=tmp_path, spec_dir=spec).applied
    assert len(json.loads((spec / "officers.json").read_text(encoding="utf-8"))) == 4
    assert not (spec / "mystique" / "officers.json").exists()


def test_the_change_form():
    assert change_rows(CHANGE + " | treasurer; Ola Sample; 2099-05-01; the same minutes")[1]["role"] == "treasurer"
    [vacant] = change_rows("vice president; vacant; 2099-05-01; Minutes, 2099-05-01")
    assert vacant == {"role": "vice president", "name": "", "acted": "2099-05-01", "source": "Minutes, 2099-05-01",
                      "vacant": True}
    with pytest.raises(FormError):
        change_rows("director; Pat Sample; 2099-05-01; minutes")          # a director's seat is a term, not an office
    # A roster with no recorded change is read as written.
    assert [(r, row["name"]) for r, row in in_force(ROSTER)][:2] == [("secretary", "Tess Sample"), ("treasurer", "Tess Sample")]


# --- Terms ------------------------------------------------------------------------------------------------------------

def test_terms_are_read_from_the_fixture_topic():
    terms = community().terms()
    assert [t.person for t in terms] == ["Wren Castlebury", "Quill Ashgrove", "Odo Fennimore"]   # the nameless row skipped
    secretary = terms[-1]
    assert secretary.seat is SeatKind.OFFICER and secretary.office is OfficerRole.SECRETARY and secretary.end is None
    assert secretary.source.startswith("Minutes") and secretary.provision == "Bylaws 9.2"
    assert terms[0].ended(date(2099, 1, 1)) and not terms[1].ended(date(2099, 1, 1))
    assert not secretary.ended(date(2999, 1, 1))                      # no end on record: never ended by jason


def test_a_missing_terms_topic_is_none(tmp_path, monkeypatch):
    monkeypatch.setenv("JASON_SPEC_DIR", str(tmp_path))
    assert community().terms() == ()
    assert Community.terms(_stub()) == ()
    assert terms_of({"not": "a list"}) == ()


def test_a_term_answer_is_appended_to_the_terms_topic(tmp_path):
    spec = tmp_path / "spec"
    ask = _asked("election-status", Status.MISSING, tmp_path)
    text = ("director; Pat Sample; 2099-03-01; 2101-02-28; Inspector's report, sample election; Bylaws 1.1 | "
            "treasurer; Ola Sample; 2099-03-10; at the pleasure of the board; Minutes, 2099-03-10; Bylaws 1.2")
    intake.answer([ask], ask.id, text, "A Person")
    intake.confirm([ask], ask.id, "B Person")
    assert intake_task.apply([ask], tmp_path, profile="oakview", spec_dir=spec) == [ask]
    rows = json.loads((spec / "oakview" / "terms.json").read_text(encoding="utf-8"))
    [director, treasurer] = terms_of(rows)
    assert director == Term("Pat Sample", SeatKind.DIRECTOR, date(2099, 3, 1), date(2101, 2, 28), None,
                            "Inspector's report, sample election", "Bylaws 1.1")
    assert treasurer.office is OfficerRole.TREASURER and treasurer.end is None
    with pytest.raises(FormError):
        term_rows("director; Pat Sample; 2099-03-01; 2098-01-01; report; Bylaws 1.1")   # ends before it starts
    with pytest.raises(FormError):
        term_rows("director; Pat Sample; 2099-03-01; 2101-02-28; ; Bylaws 1.1")         # no election record


def test_the_term_question_waits_on_the_terms_check():
    found = item("election-status")
    ctx = Context(community=SimpleNamespace(assignments=lambda: (), terms=lambda: ()))
    from jason.community.onboarding import check_item

    assert "Community.terms(): 0" in check_item(found, ctx).evidence
