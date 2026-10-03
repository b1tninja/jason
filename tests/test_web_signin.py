"""Sign in with Google for jason-web (jason.web.signin): the flow round trip with Google faked, every check on the ID
token, the session it makes, and what it changes about writes. Nothing here reaches Google or Keeper: the client, the
token exchange, the roster, and the domains are passed in.
"""

from __future__ import annotations

import base64
import hashlib
import json
import time
from urllib.parse import parse_qs, quote, urlsplit

import pytest
import webclient

from jason.approvals import engine, store
from jason.approvals.model import Decision
from jason.web import signin
from jason.web.app import create_app
from jason.web.signin import Client, Person, Refused, SignIn, account_for, claims_of
from test_approvals import (_Tags, _by, _completion, _validator, _writes, fake_kind,  # noqa: F401 - fixtures
                            village)

ROSTER = (Person("A Manager", "manager", "a.manager@example.org"), Person("Pat Example", "treasurer", "pat@example.org"))


def _jwt(claims: dict) -> str:
    enc = lambda d: base64.urlsafe_b64encode(json.dumps(d).encode()).rstrip(b"=").decode()  # noqa: E731
    return f"{enc({'alg': 'RS256'})}.{enc(claims)}.sig"


def _claims(_nonce: str, **over) -> dict:
    base = {"iss": "https://accounts.google.com", "aud": "cid", "exp": time.time() + 3600, "nonce": _nonce,
            "sub": "1234567890", "email": "a.manager@example.org", "email_verified": True, "hd": "example.org"}
    base.update(over)
    return base


class FakeGoogle:
    """The token endpoint: answers with an ID token for whatever claims the test sets, keeping what it was sent."""

    def __init__(self):
        self.sent: list[tuple] = []
        self.claims: dict = {}

    def __call__(self, client, code, redirect_uri, verifier):
        self.sent.append((client, code, redirect_uri, verifier))
        return {"id_token": _jwt(self.claims), "access_token": "unused"}


def _sign_in(google, *, required=False, configured=True, roster=ROSTER, domains=("example.org",), tmp_path=None):
    return SignIn(configured=configured, client=lambda: Client("cid", "secret"), roster=lambda: roster,
                  domains=lambda: domains, exchange=google, required=required,
                  log=(tmp_path / "sign-ins.jsonl") if tmp_path else None)


def _dist(tmp_path):
    dist = tmp_path / "dist"
    dist.mkdir(exist_ok=True)
    (dist / "index.html").write_text("<!doctype html><html><head></head><body></body></html>", encoding="utf-8")
    return dist


def _app(tmp_path, sign_in, **kw):
    kw.setdefault("board_writer", lambda item, body: {"item": item, **body})
    return create_app(_dist(tmp_path), {}, approvals_live=None, sign_in=sign_in, **kw)


def _go(c, google, *, nxt="#/approvals", **claims):
    """Start a sign-in, let Google answer with ``claims``, and follow the callback; returns (start, callback)."""
    start = c.get(f"/auth/google?next={quote(nxt, safe='')}")
    q = {k: v[0] for k, v in parse_qs(urlsplit(start.headers["Location"]).query).items()}
    google.claims = _claims(q["nonce"], **claims)
    back = c.get(f"/auth/google/callback?state={q['state']}&code=the-code")
    return q, back


def test_round_trip_signs_in_the_officer(tmp_path):
    google = FakeGoogle()
    c = webclient.client(_app(tmp_path, _sign_in(google, tmp_path=tmp_path)))
    q, back = _go(c, google)
    assert q["scope"] == "openid email profile" and q["response_type"] == "code" and q["client_id"] == "cid"
    assert q["redirect_uri"] == "http://localhost/auth/google/callback" and q["hd"] == "example.org"
    assert q["code_challenge_method"] == "S256" and q["prompt"] == "select_account"
    client, code, redirect_uri, verifier = google.sent[0]
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    assert code == "the-code" and redirect_uri == q["redirect_uri"] and challenge == q["code_challenge"]
    assert back.status_code == 302 and back.headers["Location"] == "/#/approvals"
    s = c.get("/api/session").json
    assert s["signedIn"] == {"name": "A Manager", "role": "manager", "email": "a.manager@example.org",
                             "provider": "google", "at": s["signedIn"]["at"]}
    assert s["signIn"]["configured"] is True and s["signIn"]["required"] is False and s["signInError"] == ""
    log = [json.loads(line) for line in (tmp_path / "sign-ins.jsonl").read_text(encoding="utf-8").splitlines()]
    assert log[-1]["event"] == "signed in" and log[-1]["name"] == "A Manager"


def test_a_refusal_is_said_once_and_signs_no_one_in(tmp_path):
    google = FakeGoogle()
    c = webclient.client(_app(tmp_path, _sign_in(google)))
    _, back = _go(c, google, email="stranger@example.org")
    assert back.headers["Location"] == "/#/approvals"
    s = c.get("/api/session").json
    assert s["signedIn"] is None and "not an officer's account" in s["signInError"]
    assert c.get("/api/session").json["signInError"] == ""          # said once


def test_state_must_round_trip(tmp_path):
    google = FakeGoogle()
    c = webclient.client(_app(tmp_path, _sign_in(google)))
    c.get("/auth/google")
    c.get("/auth/google/callback?state=forged&code=x")
    s = c.get("/api/session").json
    assert s["signedIn"] is None and "state" in s["signInError"] and google.sent == []


def test_a_callback_not_started_here_is_refused(tmp_path):
    google = FakeGoogle()
    c = webclient.client(_app(tmp_path, _sign_in(google)))
    c.get("/auth/google/callback?state=x&code=y")
    assert "not started here" in c.get("/api/session").json["signInError"] and google.sent == []


def test_google_error_and_unset_client_are_said(tmp_path):
    google = FakeGoogle()
    c = webclient.client(_app(tmp_path, _sign_in(google)))
    start = c.get("/auth/google")
    state = parse_qs(urlsplit(start.headers["Location"]).query)["state"][0]
    c.get(f"/auth/google/callback?state={state}&error=access_denied")
    assert "access_denied" in c.get("/api/session").json["signInError"]
    off = webclient.client(_app(tmp_path, _sign_in(google, configured=False)))
    assert off.get("/auth/google?next=%23%2Fapprovals").headers["Location"] == "/#/approvals"
    assert signin.RECORD_KEY in off.get("/api/session").json["signInError"]


def test_next_is_a_console_route_only(tmp_path):
    google = FakeGoogle()
    c = webclient.client(_app(tmp_path, _sign_in(google)))
    _, back = _go(c, google, nxt="https://evil.example/")
    assert back.headers["Location"] == "/"


def test_sign_in_answers_only_on_this_servers_name(tmp_path):
    c = _app(tmp_path, _sign_in(FakeGoogle())).test_client()
    assert c.get("/auth/google", headers={"Host": "evil.example"}).status_code == 421
    assert c.get("/auth/google/callback", headers={"Host": "evil.example"}).status_code == 421


@pytest.mark.parametrize("over, why", [
    ({"iss": "https://evil.example"}, "not from Google"),
    ({"aud": "someone-else"}, "another client"),
    ({"exp": time.time() - 3600}, "expired"),
    ({"nonce": "replayed"}, "nonce"),
    ({"email_verified": False}, "vouch"),
    ({"hd": "gmail.com"}, "Google Workspace"),
    ({"hd": None}, "Google Workspace"),
    ({"email": "stranger@example.org"}, "not an officer's account"),
])
def test_every_check_on_the_id_token(over, why):
    with pytest.raises(Refused, match=why):
        account_for(_claims("n", **over), client_id="cid", nonce="n", roster=ROSTER, domains=("example.org",))


def test_accepted_account_and_email_case():
    a = account_for(_claims("n", email="A.Manager@Example.org"), client_id="cid", nonce="n", roster=ROSTER,
                    domains=("example.org",))
    assert (a.name, a.role, a.email, a.sub) == ("A Manager", "manager", "a.manager@example.org", "1234567890")
    assert account_for(_claims("n", hd=None), client_id="cid", nonce="n", roster=ROSTER, domains=()).name == "A Manager"


def test_one_email_for_two_people_is_refused():
    twice = ROSTER + (Person("Someone Else", "director", "a.manager@example.org"),)
    with pytest.raises(Refused, match="more than one person"):
        account_for(_claims("n"), client_id="cid", nonce="n", roster=twice, domains=())


def test_claims_of_reads_the_payload_only():
    assert claims_of(_jwt({"sub": "1"}))["sub"] == "1"
    with pytest.raises(Refused):
        claims_of("not-a-jwt")


def test_writes_carry_the_signed_in_name(tmp_path):
    google = FakeGoogle()
    c = webclient.client(_app(tmp_path, _sign_in(google)))
    assert c.post("/api/board-items/x", json={"by": "Pat Example"}).status_code == 200   # not signed in: as before
    _go(c, google)
    assert c.post("/api/board-items/x", json={"by": ""}).json["by"] == "A Manager"
    assert c.post("/api/board-items/x", json={"by": "a manager"}).status_code == 200
    r = c.post("/api/board-items/x", json={"by": "Pat Example"})
    assert r.status_code == 403 and "signed in as A Manager" in r.json["error"]


def test_required_sign_in_refuses_writes_until_signed_in(tmp_path):
    google = FakeGoogle()
    c = webclient.client(_app(tmp_path, _sign_in(google, required=True)))
    assert c.get("/api/session").status_code == 200                                    # reads stay open
    r = c.post("/api/board-items/x", json={"by": "A Manager"})
    assert r.status_code == 401 and "sign in with Google" in r.json["error"]
    _go(c, google)
    assert c.post("/api/board-items/x", json={"by": "A Manager"}).status_code == 200
    assert c.post("/auth/signout").json["ok"] is True
    assert c.get("/api/session").json["signedIn"] is None
    assert c.post("/api/board-items/x", json={"by": "A Manager"}).status_code == 401


def test_sign_out_is_a_guarded_write(tmp_path):
    c = _app(tmp_path, _sign_in(FakeGoogle())).test_client()
    assert c.post("/auth/signout").status_code == 403                                 # no Origin, no token


def test_an_officer_taken_off_the_roster_is_signed_out(tmp_path):
    google = FakeGoogle()
    roster = list(ROSTER)
    si = SignIn(configured=True, client=lambda: Client("cid", "secret"), roster=lambda: tuple(roster),
                domains=lambda: ("example.org",), exchange=google)
    c = webclient.client(_app(tmp_path, si))
    _go(c, google)
    roster.pop(0)
    r = c.post("/api/board-items/x", json={"by": ""})
    assert r.status_code == 401 and "no longer on the officers' roster" in r.json["error"]
    assert c.get("/api/session").json["signedIn"] is None


def test_approvals_record_the_signed_in_officer(village, monkeypatch, tmp_path):
    monkeypatch.setattr("jason.mcp.county._data_dir", lambda d: village.data_dir / "letters")
    google = FakeGoogle()
    app = create_app(_dist(tmp_path), None, approvals_live=None, sign_in=_sign_in(google))
    c = webclient.client(app)
    a = engine.plan("owner-info-tags", village.live, by="A Manager")
    _go(c, google)
    item = a.approvable[0].id
    r = c.post(f"/api/approvals/{a.id}/decide", json={"items": [item], "decision": "approved"})
    assert r.status_code == 200, r.json
    got = store.load(a.id)
    assert got.decisions[-1].by == "A Manager" and got.decisions[-1].via == signin.VIA
    assert got.decisions[-1].decision is Decision.APPROVED
    r = c.post(f"/api/approvals/{a.id}/decide", json={"items": [item], "decision": "rejected", "by": "Pat Example",
                                                     "reason": "x"})
    assert r.status_code == 403
