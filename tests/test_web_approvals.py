"""The approvals engine through jason-web: the reads, the writes to jason's own store, the check, the apply (off by
default; on, it refuses a stale fingerprint and writes only the approved items), and the write guard.

Example Village (tests/test_approvals.py): four fake owners on a fake PayHOA client. Nothing here reaches PayHOA:
the live context the routes use is the fake client, through a factory the test passes to ``create_app``.
"""

from __future__ import annotations

import json
from contextlib import contextmanager

import pytest
import webclient

from jason.approvals import engine, store
from jason.approvals.engine import Live
from jason.approvals.model import ApprovalStatus as S
from jason.approvals.model import ItemClass
from jason.web.app import create_app
from test_approvals import (_Tags, _by, _completion, _validator, _writes, fake_kind,  # noqa: F401 - fixtures
                            village)


def _factory(live):
    calls = []

    @contextmanager
    def factory(kind):
        calls.append(kind.key)
        yield live
    factory.calls = calls
    return factory


def _dist(tmp_path):
    dist = tmp_path / "dist"
    dist.mkdir(exist_ok=True)
    (dist / "index.html").write_text("<!doctype html><html><head><title>t</title></head><body><div id=root></div>"
                                     "</body></html>", encoding="utf-8")
    return dist


@pytest.fixture
def web(village, monkeypatch):
    """The app over Example Village, apply off, with the letters inbox reading an empty folder."""
    monkeypatch.setattr("jason.mcp.county._data_dir", lambda d: village.data_dir / "letters")
    factory = _factory(village.live)
    app = create_app(_dist(village.data_dir), None, approvals_live=factory)
    village.factory, village.app, village.c = factory, app, webclient.client(app)
    return village


def _apply_on(village):
    app = create_app(_dist(village.data_dir), None, approvals_live=village.factory, allow_apply=True)
    return webclient.client(app)


def _plan(village):
    return engine.plan("owner-info-tags", village.live, by="A Manager")


def _post(c, ident, step, **body):
    return c.post(f"/api/approvals/{ident}/{step}", json=body)


def _review(village, a, by="A Manager"):
    """Through the web: Ben's and Dee's writes and requests approved, the rest rejected, submitted."""
    c = village.c
    keep = [i.id for i in _writes(a, 11) + _writes(a, 13)] + [_completion(a, 502).id, _completion(a, 504).id]
    assert _post(c, a.id, "decide", items=keep, decision="approved", by=by).status_code == 200
    rest = [i.id for i in a.approvable if i.id not in keep]
    assert _post(c, a.id, "decide", items=rest, decision="rejected", reason="next week", by=by).status_code == 200
    r = _post(c, a.id, "submit", by=by)
    assert r.status_code == 200, r.json
    return r.json


# --- reads --------------------------------------------------------------------------------------------------------------

def test_list_and_show(web, monkeypatch):
    a = _plan(web)
    listed = web.c.get("/api/approvals").json
    assert [r["id"] for r in listed["approvals"]] == [a.id] and listed["approvalsOpen"] == 1
    assert listed["approvalsWaiting"] == 1                             # planned: waits on a person's decision
    assert listed["approvals"][0]["status"] == "planned" and listed["approvals"][0]["fingerprint"] == a.fingerprint
    assert "lettersError" in listed or "letters" in listed           # the letters inbox still answers beside it
    assert web.c.get("/api/approvals?status=planned").json["approvals"][0]["id"] == a.id
    assert web.c.get("/api/approvals?status=applied").json["approvals"] == []
    assert web.c.get("/api/approvals?status=nope").status_code == 400
    shown = web.c.get(f"/api/approvals/{a.id}")
    assert shown.status_code == 200
    beside = {"kindFacts", "needsSecond", "recitations"}                 # what the screen reads beside the record
    assert beside <= set(shown.json)
    _validator("approval.schema.json").validate({k: v for k, v in shown.json.items() if k not in beside})
    assert shown.json["fingerprint"] == a.fingerprint and len(shown.json["items"]) == len(a.items)
    assert web.c.get(f"/api/approvals/{a.id[:16]}").json["id"] == a.id       # a unique prefix
    assert web.c.get("/api/approvals/apr-none").status_code == 404
    assert web.factory.calls == []                                     # a read never builds a live context


def test_show_carries_the_kinds_facts_and_each_rule_recited(web, monkeypatch):
    recited = []
    monkeypatch.setattr("jason.web.approvals.recite",
                        lambda rule: recited.append(rule) or {"found": True, "citation": rule, "text": f"words of {rule}"})
    a = _plan(web)
    shown = web.c.get(f"/api/approvals/{a.id}").json
    facts = shown["kindFacts"]
    assert facts["key"] == "owner-info-tags" and facts["maxAgeHours"] == 24 and facts["twoPerson"] is False
    assert facts["risk"] and facts["riskWords"] and facts["approver"] and "reversible" in facts
    assert shown["needsSecond"] is False                               # one person; no high-stakes item approved yet
    rules = {i.rule for i in a.items if i.rule}
    assert rules and set(shown["recitations"]) == rules == set(recited)
    assert all(c["found"] and c["text"] == f"words of {r}" for r, c in shown["recitations"].items())


def test_a_rule_that_cannot_be_read_is_a_miss_not_an_error(web, monkeypatch):
    def broken(*a, **k):
        raise OSError("disk gone")
    monkeypatch.setattr("jason.tasks.cite.resolve", broken)
    a = _plan(web)
    shown = web.c.get(f"/api/approvals/{a.id}")
    assert shown.status_code == 200
    miss = next(iter(shown.json["recitations"].values()))
    assert miss["found"] is False and "disk gone" in miss["reason"]


def test_a_signed_plan_waits_only_to_be_applied(web):
    a = _plan(web)
    _review(web, a)                                                    # decided and submitted by one person
    listed = web.c.get("/api/approvals").json
    assert listed["approvalsOpen"] == 1 and listed["approvalsWaiting"] == 0


def test_the_kinds_route_lists_what_each_kind_declares(web):
    listed = web.c.get("/api/approvals/kinds").json["kinds"]
    tags = next(k for k in listed if k["key"] == "owner-info-tags")
    assert tags["maxAgeHours"] == 24 and tags["approver"] and tags["riskWords"]
    assert web.factory.calls == []                                     # listing kinds reads nothing live


def test_no_get_route_changes_the_approvals_store(web, monkeypatch):
    """Every GET the approvals routes answer (the list, one plan, the kinds, the audit, the evidence and its document
    link, and the refused GETs of a check or an apply) leaves data/approvals/ byte for byte as it was."""
    monkeypatch.setattr("jason.web.approvals.recite", lambda rule: {"found": False, "citation": rule, "reason": "test"})
    a = _plan(web)
    _review(web, a)
    store_dir = web.data_dir / "approvals"
    before = {p.relative_to(store_dir): p.read_bytes() for p in sorted(store_dir.rglob("*")) if p.is_file()}
    assert before
    walked = []
    for rule in web.app.url_map.iter_rules():
        if "GET" not in rule.methods or not (rule.endpoint.startswith("approvals.") or rule.rule == "/api/<source>"):
            continue
        url = rule.rule.replace("<ident>", a.id).replace("<token>", "no-such-token").replace("<source>", "approvals")
        url = url.replace("<path:path>", "x")
        if "<" in url:
            continue
        for query in ("", f"?approval={a.id}&verify=1", f"?address=board-item:x&approval={a.id}"):
            web.c.get(url + query)
            walked.append(url + query)
    assert len(walked) >= 8
    after = {p.relative_to(store_dir): p.read_bytes() for p in sorted(store_dir.rglob("*")) if p.is_file()}
    assert after == before
    assert web.factory.calls == []


def test_the_letters_inbox_keeps_its_shape(web, monkeypatch):
    seen = []
    monkeypatch.setattr("jason.web.extra.approvals.approvals",
                        lambda args: seen.append(dict(args)) or {"found": True, "pending": 2, "people": [], "letters": []})
    page = web.c.get("/api/approvals").json
    assert page["pending"] == 2 and page["people"] == [] and page["approvals"] == []
    assert web.c.get("/api/approvals?key=Drive/x").json == {"found": True, "pending": 2, "people": [], "letters": []}
    assert seen[-1] == {"key": "Drive/x"}


def test_what_the_web_shows_is_masked(web):
    a = _plan(web)
    ben = [i.id for i in _writes(a, 11)]
    r = _post(web.c, a.id, "decide", items=ben, decision="rejected", by="A Manager",
              reason="owner wrote from ben@example.com; call 916-555-0123")
    assert r.status_code == 200
    for text in (json.dumps(r.json), web.c.get(f"/api/approvals/{a.id}").get_data(as_text=True),
                 web.c.get("/api/approvals/audit").get_data(as_text=True)):
        assert "@example.com" not in text and "555-0123" not in text
    assert "[email]" in json.dumps(r.json) and "[phone]" in json.dumps(r.json)


def test_audit_reads_and_verifies(web):
    a = _plan(web)
    _post(web.c, a.id, "decide", items=[_writes(a, 11)[0].id], decision="approved", by="A Manager")
    out = web.c.get(f"/api/approvals/audit?approval={a.id[:16]}&verify=1").json
    assert out["verify"] == {"whole": True, "line": None, "why": "the chain is whole"}
    assert [e["event"] for e in out["entries"]] == ["plan.created", "item.decided"]
    assert out["entries"][-1]["via"] == "console" and out["entries"][-1]["actor"] == "A Manager"
    _validator("audit-entry.schema.json").validate(out["entries"][-1])
    assert "verify" not in web.c.get("/api/approvals/audit").json


# --- writes to jason's own store ----------------------------------------------------------------------------------------

def test_decide_partial(web):
    a = _plan(web)
    ben = [i.id for i in _writes(a, 11)]
    r = _post(web.c, a.id, "decide", items=[i[:8] for i in ben], decision="approved", by="A Manager")
    assert r.status_code == 200 and r.json["status"] == "in_review"
    assert {i["id"] for i in r.json["items"] if i["decision"] == "approved"} == set(ben)
    assert r.json["decisions"][-1]["via"] == "console"
    assert store.load(a.id).status is S.IN_REVIEW


def test_refusals_are_400_in_the_engines_words(web):
    a = _plan(web)
    ben = [i.id for i in _writes(a, 11)]
    held = _by(a, ItemClass.HELD_FOR_BOARD)[0].id
    cases = [
        (dict(items=ben, decision="approved", by="  "), "names the person"),
        (dict(items=[held], decision="approved", by="A Manager"), "held for the board"),
        (dict(items=[_by(a, ItemClass.FOR_A_PERSON)[0].id], decision="approved", by="A Manager"), "never approvable"),
        (dict(items=ben, decision="rejected", by="A Manager"), "says why"),
        (dict(items=[_completion(a, 502).id], decision="approved", by="A Manager"), "waits on"),
        (dict(items=ben, decision="maybe", by="A Manager"), "decision is one of"),
        (dict(items="some", decision="approved", by="A Manager"), "items is a list"),
        (dict(items=["ffffffff"], decision="approved", by="A Manager"), "no item"),
    ]
    for body, words in cases:
        r = _post(web.c, a.id, "decide", **body)
        assert r.status_code == 400 and words in r.json["error"], (body, r.json)
    _post(web.c, a.id, "decide", items=ben, decision="approved", by="A Manager")
    r = _post(web.c, a.id, "submit", by="A Manager")
    assert r.status_code == 400 and "undecided" in r.json["error"]
    assert _post(web.c, "apr-none", "submit", by="A Manager").status_code == 404
    assert _post(web.c, a.id, "nope", by="A Manager").status_code == 404
    assert _post(web.c, a.id, "withdraw", by="A Manager").json["error"].endswith("(reason)")
    assert store.load(a.id).status is S.IN_REVIEW                     # nothing changed by a refusal


@pytest.fixture
def fake(tmp_path, monkeypatch, fake_kind):
    """A two-signature plan: the fake kind's second item is high stakes."""
    monkeypatch.setattr("jason.config.data_dir", lambda *a, **k: tmp_path)
    live = Live(_Tags(), 1, tmp_path)
    factory = _factory(live)
    app = create_app(_dist(tmp_path), None, approvals_live=factory, allow_apply=True)
    a = engine.plan("fake-tags", live, by="A Manager")
    return a, live, factory, webclient.client(app)


def test_submit_confirm_decline_withdraw(fake):
    a, live, factory, c = fake
    assert _post(c, a.id, "decide", items="all", decision="approved", by="A Manager").status_code == 200
    r = _post(c, a.id, "submit", by="A Manager")
    assert r.status_code == 200 and r.json["status"] == "approved" and r.json["first"]["via"] == "console"
    r = _post(c, a.id, "decide", items="all", decision="approved", by="A Manager")
    assert r.status_code == 400 and "decided before it is submitted" in r.json["error"]      # the wrong state
    r = _post(c, a.id, "apply", by="A Manager", confirm=a.fingerprint)
    assert r.status_code == 400 and "second, distinct person" in r.json["error"] and live.client.writes == []
    assert factory.calls == []                                         # refused before any live context was built
    r = _post(c, a.id, "apply", by=" ", confirm=a.fingerprint)
    assert r.status_code == 400 and "names the person" in r.json["error"] and factory.calls == []
    r = _post(c, a.id, "confirm", by=" a manager ")
    assert r.status_code == 400 and "submitted it" in r.json["error"]                         # the same person
    r = _post(c, a.id, "decline", by="A Manager", reason="x")
    assert r.status_code == 400 and "second person declines" in r.json["error"]
    r = _post(c, a.id, "decline", by="B Treasurer", reason="C is not for this cycle")
    assert r.status_code == 200 and r.json["status"] == "in_review" and r.json["first"] is None
    _post(c, a.id, "submit", by="A Manager")
    r = _post(c, a.id, "confirm", by="B Treasurer", role="director")
    assert r.status_code == 200 and r.json["second"]["name"] == "B Treasurer" and r.json["second"]["role"] == "director"
    r = _post(c, a.id, "confirm", by="C Secretary")
    assert r.status_code == 400 and "already confirmed" in r.json["error"]
    r = _post(c, a.id, "apply", by="A Manager", confirm=a.fingerprint)
    assert r.status_code == 200 and r.json["status"] == "applied"
    assert live.client.writes == [("member:1", "B"), ("member:2", "C")] and factory.calls == ["fake-tags"]
    r = _post(c, a.id, "withdraw", by="A Manager", reason="done")
    assert r.status_code == 400 and "cannot be withdrawn" in r.json["error"]


def test_withdraw(fake):
    a, live, factory, c = fake
    r = _post(c, a.id, "withdraw", by="A Manager", reason="a newer cycle")
    assert r.status_code == 200 and r.json["status"] == "withdrawn"
    assert any("withdrawn by A Manager" in n for n in r.json["notes"])


# --- check and apply ----------------------------------------------------------------------------------------------------

def test_check_reads_live_and_writes_nothing(web):
    a = _plan(web)
    _review(web, a)
    assert web.c.get(f"/api/approvals/{a.id}/check").status_code == 405           # never a GET
    r = web.c.post(f"/api/approvals/{a.id}/check")
    assert r.status_code == 200, r.json
    assert r.json["ok"] and r.json["unchanged"] and r.json["readLive"] and r.json["then"] == r.json["now"]
    assert {i["id"] for i in r.json["wouldApply"]} == {i.id for i in store.load(a.id).approved}
    assert web.client.writes == [] and web.factory.calls == ["owner-info-tags"]
    web.client._person(11)["tags"].append({"tag": "Notices by Mail", "id": 7777})
    r = web.c.post(f"/api/approvals/{a.id}/check").json
    assert not r["ok"] and {c["id"] for c in r["changed"]} >= {i.id for i in _writes(a, 11)}
    assert store.load(a.id).status is S.PARTIALLY_APPROVED and web.client.writes == []


def test_apply_is_off_by_default(web):
    a = _plan(web)
    _review(web, a)
    r = _post(web.c, a.id, "apply", by="A Manager", confirm=a.fingerprint)
    assert r.status_code == 403 and "--allow-apply" in r.json["error"]
    assert web.client.writes == [] and web.factory.calls == [] and web.app.config["JASON_ALLOW_APPLY"] is False
    assert web.c.get("/api/session").json["applyEnabled"] is False
    assert store.load(a.id).status is S.PARTIALLY_APPROVED


def test_apply_refuses_a_stale_fingerprint(web):
    a = _plan(web)
    _review(web, a)
    c = _apply_on(web)
    assert c.get("/api/session").json["applyEnabled"] is True
    r = _post(c, a.id, "apply", by="A Manager")
    assert r.status_code == 400 and "fingerprint" in r.json["error"]
    r = _post(c, a.id, "apply", by="A Manager", confirm="0" * 64)               # not the plan reviewed
    assert r.status_code == 409 and r.json["fingerprint"] == a.fingerprint
    assert web.client.writes == [] and web.factory.calls == []
    web.client._person(11)["tags"].append({"tag": "Notices by Mail", "id": 7777})   # PayHOA changed since review
    r = _post(c, a.id, "apply", by="A Manager", confirm=a.fingerprint)
    assert r.status_code == 409 and "changed since review" in r.json["error"]
    assert web.client.writes == []
    fresh = store.load(r.json["supersededBy"])
    assert fresh.status is S.PLANNED and fresh.supersedes == a.id and r.json["approval"]["status"] == "superseded"
    assert {c["id"] for c in r.json["changed"]} >= {i.id for i in _writes(a, 11)}


def test_apply_writes_only_the_approved_items(web):
    a = _plan(web)
    _review(web, a)
    c = _apply_on(web)
    assert c.post(f"/api/approvals/{a.id}/apply", json={"by": "A Manager", "confirm": a.fingerprint},
                  headers={"X-Jason-Token": ""}).status_code == 403             # the header itself, not the cookie
    r = _post(c, a.id, "apply", by="A Manager", confirm=a.fingerprint)
    assert r.status_code == 200 and r.json["status"] == "applied", r.json
    _validator("approval.schema.json").validate(r.json)
    members = {m for w in web.client.writes if w[0] == "member" for m in w[1]}
    assert members == {11, 13}                                         # Ana's and Cy's writes were rejected
    assert not any(w[0].startswith("unit") for w in web.client.writes)  # held for the board: never written
    assert {w[1] for w in web.client.writes if w[0] == "complete"} == {502, 504}
    applied = {i["id"] for i in r.json["items"] if i["result"] == "applied"}
    assert applied == {i.id for i in store.load(a.id).approved}
    events = [e for e in web.c.get(f"/api/approvals/audit?approval={a.id}").json["entries"]]
    assert events[-1]["event"] == "approval.applied" and events[-1]["via"] == "console"


# --- the write guard ----------------------------------------------------------------------------------------------------

def test_the_write_guard(web):
    a = _plan(web)
    body = {"items": [_writes(a, 11)[0].id], "decision": "approved", "by": "A Manager"}
    url = f"/api/approvals/{a.id}/decide"
    token = web.app.config["JASON_TOKEN"]
    bare = web.app.test_client(use_cookies=False)
    assert bare.post(url, json=body).status_code == 403                                     # no Origin
    assert bare.post(url, json=body, headers={"Origin": "http://evil.example", "X-Jason-Token": token}).status_code == 403
    assert bare.post(url, json=body, headers={"Origin": "null", "X-Jason-Token": token}).status_code == 403
    assert bare.post(url, json=body, headers={"Origin": "http://localhost"}).status_code == 403   # no token
    assert bare.post(url, json=body, headers={"Origin": "http://localhost", "X-Jason-Token": "x"}).status_code == 403
    assert bare.post(url, json=body, headers={"Origin": "http://localhost", "X-Jason-Token": token,
                                              "Sec-Fetch-Site": "cross-site"}).status_code == 403
    assert store.load(a.id).status is S.PLANNED                        # nothing got through
    # DNS rebinding: another name for this server is refused, reads included
    assert bare.get("/api/approvals", base_url="http://rebind.example:8080").status_code == 421
    assert bare.post(url, json=body, base_url="http://rebind.example",
                     headers={"Origin": "http://rebind.example", "X-Jason-Token": token}).status_code == 421
    # the page: the token in index.html and /api/session, and the cookie the older pages write with
    page = web.app.test_client()
    first = page.get("/")
    assert f'<meta name="jason-token" content="{token}">' in first.get_data(as_text=True)
    assert "no-store" in first.headers["Cache-Control"]
    cookie = first.headers.get("Set-Cookie", "")
    assert f"jason_token={token}" in cookie and "HttpOnly" in cookie and "SameSite=Strict" in cookie
    assert page.get("/api/session").json["token"] == token
    r = page.post(url, json=body, headers={"Origin": "http://localhost"})                  # cookie, same origin
    assert r.status_code == 200 and r.json["status"] == "in_review"
    assert page.post(f"/api/approvals/{a.id}/check", headers={"Origin": "http://localhost"}).status_code == 403
    assert web.factory.calls == []
    # a host a person named with --host
    other = create_app(_dist(web.data_dir), {}, approvals_live=None, hosts=("192.168.1.5",)).test_client()
    assert other.get("/api/session", base_url="http://192.168.1.5:8080").status_code == 200


def test_jason_web_apply_flag(monkeypatch):
    import waitress

    from jason.web.app import main

    served = []
    monkeypatch.setattr(waitress, "serve", lambda app, **kw: served.append((app, kw)))
    main([])
    main(["--allow-apply", "--port", "8181"])
    assert served[0][0].config["JASON_ALLOW_APPLY"] is False
    assert served[1][0].config["JASON_ALLOW_APPLY"] is True and served[1][1] == {"host": "127.0.0.1", "port": 8181}
