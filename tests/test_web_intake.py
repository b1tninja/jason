"""The console's setup view over onboarding and its intake answer route (jason.web.extra.onboarding_setup):
``POST /api/write/intake/<id>`` takes a signed-in roster person's answer into the intake queue and applies nothing; a
secret is refused with the reason and never echoed or stored; a high-stakes answer waits on a second person; and
``GET /api/onboarding-session`` gives the five gates and each item's computed status, with no answer's value. A
made-up roster, a made-up queue, and a tmp data folder; nothing reaches Google, Keeper, or PayHOA."""

from __future__ import annotations

import json

import pytest
import webclient

from jason.community import intake
from jason.community.intake import Ask, AskKind, AskStatus

SECRET = "password: hunter22-Example"


def _fact(subject: str, *, stakes: bool = False) -> Ask:
    return Ask(intake.ask_id(AskKind.FACT, subject, ""), AskKind.FACT, subject, "Who keeps the minute book?",
               serves=subject.split(":", 1)[1], stakes=stakes, detail={"record": "private facts"})


@pytest.fixture
def web(tmp_path, monkeypatch):
    from jason.web.app import create_app

    data = tmp_path / "data"
    data.mkdir()
    dist = tmp_path / "dist"
    dist.mkdir()
    monkeypatch.setattr("jason.mcp.county._data_dir", lambda d: data)
    low, high = _fact("fact:minute-book"), _fact("fact:signers", stakes=True)
    intake.save(data, [low, high])
    app = create_app(dist, approvals_live=None, sign_in=webclient.roster_sign_in(dev=True))
    return app, data, low, high


def _files(data):
    return sorted(p.relative_to(data).as_posix() for p in data.rglob("*") if p.is_file())


def _stored(data, ident):
    return next(a for a in intake.load(data) if a.id == ident)


def test_an_answer_needs_a_signed_in_roster_person(web):
    app, data, low, _ = web
    out = webclient.client(app).post(f"/api/write/intake/{low.id}", json={"answer": "the secretary", "by": "A Manager"})
    assert out.status_code == 401 and _stored(data, low.id).status is AskStatus.OPEN


def test_an_answer_without_by_is_refused(web):
    app, data, low, _ = web
    c = webclient.sign_in(webclient.client(app), "Sam Secretary")
    out = c.post(f"/api/write/intake/{low.id}", json={"answer": "the secretary"})
    assert out.status_code == 400 and "names who gave it" in out.json["error"]
    other = c.post(f"/api/write/intake/{low.id}", json={"answer": "the secretary", "by": "Dana Director"})
    assert other.status_code == 403 and _stored(data, low.id).status is AskStatus.OPEN


def test_a_secret_is_refused_with_its_reason_and_never_kept_or_echoed(web):
    app, data, low, _ = web
    c = webclient.sign_in(webclient.client(app), "Sam Secretary")
    out = c.post(f"/api/write/intake/{low.id}", json={"answer": SECRET, "by": "Sam Secretary"})
    assert out.status_code == 400 and "it gives a password" in out.json["error"] and "Keeper" in out.json["error"]
    assert "hunter22" not in out.get_data(as_text=True)
    assert all("hunter22" not in p.read_text(encoding="utf-8", errors="replace") for p in data.rglob("*") if p.is_file())
    assert _stored(data, low.id).status is AskStatus.OPEN


def test_writes_are_refused_while_an_admin_views_as_someone_else(web):
    app, data, low, _ = web
    c = webclient.sign_in(webclient.client(app), "Ada Admin")
    with c.session_transaction() as s:
        s["acting"] = {"name": "A Manager", "role": "manager"}
    out = c.post(f"/api/write/intake/{low.id}", json={"answer": "the secretary", "by": "A Manager"})
    assert out.status_code == 403 and "admin view" in out.json["error"]
    assert _stored(data, low.id).status is AskStatus.OPEN


def test_an_answer_is_queued_and_never_applied(web):
    app, data, low, _ = web
    c = webclient.sign_in(webclient.client(app), "Sam Secretary")
    out = c.post(f"/api/write/intake/{low.id}", json={"answer": "the secretary keeps it", "by": "Sam Secretary"})
    assert out.status_code == 200, out.json
    body = out.json
    assert body["status"] == "answered" and body["answeredBy"] == "Sam Secretary" and body["applied"] is False
    assert body["apply"] == "jason onboard --apply" and "jason onboard --apply" in body["next"]
    assert "answer" not in body and body["needsConfirmation"] is False
    stored = _stored(data, low.id)
    assert stored.status is AskStatus.ANSWERED and stored.answer == "the secretary keeps it" and not stored.applied_to
    assert _files(data) == ["intake/asks.json"]                       # no data/spec, no proposal: only the queue
    missing = c.post("/api/write/intake/no-such-id", json={"answer": "x", "by": "Sam Secretary"})
    assert missing.status_code == 404


def test_a_high_stakes_answer_waits_on_a_second_person(web):
    app, data, _, high = web
    first = webclient.sign_in(webclient.client(app), "Pat Example")
    out = first.post(f"/api/write/intake/{high.id}", json={"answer": "two board officers", "by": "Pat Example"})
    assert out.status_code == 200 and out.json["highStakes"] is True and out.json["needsConfirmation"] is True
    assert "second person" in out.json["next"] and out.json["confirm"].startswith(f"jason onboard --confirm {high.id}")
    same = first.post(f"/api/write/intake/{high.id}", json={"confirm": True, "by": "Pat Example"})
    assert same.status_code == 400 and "second person" in same.json["error"]
    second = webclient.sign_in(webclient.client(app), "Lee President")
    ok = second.post(f"/api/write/intake/{high.id}", json={"confirm": True, "by": "Lee President"})
    assert ok.status_code == 200 and ok.json["confirmedBy"] == "Lee President" and ok.json["applied"] is False
    stored = _stored(data, high.id)
    assert stored.status is AskStatus.ANSWERED and stored.confirmed_by == "Lee President"
    assert _files(data) == ["intake/asks.json"]


def test_the_session_gives_five_gates_and_computed_statuses_and_no_answer(web):
    app, data, low, _ = web
    c = webclient.sign_in(webclient.client(app), "Sam Secretary")
    c.post(f"/api/write/intake/{low.id}", json={"answer": "kept by Example Person", "by": "Sam Secretary"})
    out = c.get("/api/onboarding-session")
    assert out.status_code == 200, out.json
    d = out.json
    assert [g["stage"] for g in d["gates"]] == ["start", "ingest", "establish", "operate", "adopt"]
    assert {i["status"] for i in d["items"]} <= {"present", "partial", "missing"}
    vault = next(i for i in d["items"] if i["key"] == "vault")
    assert vault["connect"]["commands"][0] == "jason login"
    codes = next(i for i in d["items"] if i["key"] == "keys-and-codes")         # a Keeper-held answer: a command only
    assert codes["connect"]["commands"] == [f'jason onboard --answer {codes["ask"]["id"]} "KEEPER RECORD NAME" --by "YOUR NAME"']
    orientation = next(i for i in d["items"] if i["key"] == "orientation")          # a private fact: an answer field
    assert orientation["connect"] is None and orientation["ask"]["record"] == "private facts"
    assert [a["id"] for a in d["answered"]] == [low.id] and d["answered"][0]["answeredBy"] == "Sam Secretary"
    assert d["apply"]["command"] == "jason onboard --apply"
    assert "kept by Example Person" not in json.dumps(d)                # who answered, never the value
    assert all(q["connect"] is None or "commands" in q["connect"] for q in d["next"])
    assert {q["kind"] for q in d["next"]} <= {"fact", "map"} and d["otherOpen"]["command"] == "jason intake"


def test_an_items_ask_carries_its_clock_and_standing_and_a_standing_question_sorts_last(web, monkeypatch):
    """The Setup tab labels a standing question "standing" and shows the legal clock the profile names (never a date);
    a standing question whose item is present sorts after the questions an item is missing."""
    from dataclasses import replace

    from jason.community.onboarding import ITEMS, Status
    from jason.tasks import onboarding_session as task

    standing = next(i.key for i in ITEMS if i.ask is not None and i.ask.standing)
    clocked = next(i for i in ITEMS if i.ask is not None and i.ask.clock)
    build = task.build

    def held(*a, **k):                                          # the standing item is present; its question stays open
        s = build(*a, **k)
        s.results = tuple(replace(r, status=Status.PRESENT) if r.item.key == standing else r for r in s.results)
        return s

    monkeypatch.setattr(task, "build", held)
    app, _, _, _ = web
    d = webclient.sign_in(webclient.client(app), "Sam Secretary").get("/api/onboarding-session?limit=200&kinds=fact").json
    items = {i["key"]: i for i in d["items"]}
    assert items[standing]["status"] == "present" and items[standing]["ask"]["standing"] is True
    assert items[clocked.key]["ask"]["clock"] == clocked.ask.clock
    assert all(i["ask"]["standing"] is False for i in d["items"] if i["ask"] and i["key"] != standing
               and not next(x for x in ITEMS if x.key == i["key"]).ask.standing)
    marks = [(q["serves"], q["standing"]) for q in d["next"]]
    assert marks[-1] == (standing, True) and len(marks) > 1             # after every question an item is missing
    assert all(serves != standing for serves, _ in marks[:-1])
