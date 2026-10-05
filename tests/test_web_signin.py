"""Sign in with Google for jason-web (jason.web.signin): the flow round trip with Google faked, every check on the ID
token, the session it makes, what it changes about writes, one provider or several, the roster (two offices,
portfolio managers, jason's admins), the admin view under --dev, and ``jason sign-in``. Nothing here reaches Google
or Keeper: the clients, the token exchange, and the roster are passed in.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import time
from contextlib import contextmanager
from urllib.parse import parse_qs, quote, urlsplit

import pytest
import webclient

from jason.access import Admin, Manager
from jason.approvals import engine, store
from jason.approvals.model import Decision
from jason.web import signin
from jason.web.app import create_app
from jason.web.signin import Client, Person, Provider, Refused, SignIn, account_for, claims_of
from test_approvals import (_Tags, _by, _completion, _validator, _writes, fake_kind,  # noqa: F401 - fixtures
                            village)

ROSTER = (Person("A Manager", "manager", "a.manager@example.org"), Person("Pat Example", "treasurer", "pat@example.org"))
SECRET = "GOCSPX-not-a-real-secret"


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


def _provider(key="google", cid="cid", domains=("example.org",), label="", source="community"):
    return Provider(key, label, source, domains, lambda: Client(cid, "secret"))


def _sign_in(google, *, required=False, configured=True, roster=ROSTER, domains=("example.org",), tmp_path=None,
             providers=None, dev=False):
    found = providers if providers is not None else ((_provider(domains=domains),) if configured else ())
    return SignIn(providers=lambda: found, roster=roster if callable(roster) else (lambda: roster), exchange=google,
                  required=required, log=(tmp_path / "sign-ins.jsonl") if tmp_path else None, dev=dev)


def _dist(tmp_path):
    dist = tmp_path / "dist"
    dist.mkdir(exist_ok=True)
    (dist / "index.html").write_text("<!doctype html><html><head></head><body></body></html>", encoding="utf-8")
    return dist


def _app(tmp_path, sign_in, **kw):
    kw.setdefault("board_writer", lambda item, body: {"item": item, **body})
    return create_app(_dist(tmp_path), {}, approvals_live=None, sign_in=sign_in, **kw)


def _go(c, google, *, nxt="#/approvals", provider="", **claims):
    """Start a sign-in, let Google answer with ``claims``, and follow the callback; returns (start, callback)."""
    start = c.get(f"/auth/google?next={quote(nxt, safe='')}" + (f"&provider={provider}" if provider else ""))
    q = {k: v[0] for k, v in parse_qs(urlsplit(start.headers["Location"]).query).items()}
    google.claims = _claims(q["nonce"], **{"aud": q["client_id"], **claims})
    back = c.get(f"/auth/google/callback?state={q['state']}&code=the-code")
    return q, back


# --- the flow ----------------------------------------------------------------------------------------------------

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
                             "provider": "google", "at": s["signedIn"]["at"], "admin": False}
    assert s["signIn"]["configured"] is True and s["signIn"]["required"] is False and s["signInError"] == ""
    assert s["signIn"]["providers"] == [{"key": "google", "label": "", "source": "community"}]
    log = [json.loads(line) for line in (tmp_path / "sign-ins.jsonl").read_text(encoding="utf-8").splitlines()]
    assert log[-1]["event"] == "signed in" and log[-1]["name"] == "A Manager" and log[-1]["provider"] == "google"


def test_a_refusal_is_said_once_and_signs_no_one_in(tmp_path):
    google = FakeGoogle()
    c = webclient.client(_app(tmp_path, _sign_in(google)))
    _, back = _go(c, google, email="stranger@example.org")
    assert back.headers["Location"] == "/#/approvals"
    s = c.get("/api/session").json
    assert s["signedIn"] is None and "not on the roster" in s["signInError"]
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
    assert off.get("/api/session").json["signIn"]["configured"] is False
    assert off.get("/auth/google?next=%23%2Fapprovals").headers["Location"] == "/#/approvals"
    assert signin.DESKTOP_KEY in off.get("/api/session").json["signInError"]


def test_the_env_fallback_is_the_web_client_when_set_else_jasons_desktop_one():
    class S:
        def __init__(self, web="", desktop=""):
            self.record_uids = {signin.RECORD_KEY: web} if web else {}
            self.google_oauth_record_uid = desktop

    assert signin.client_record(S(desktop="D")) == ("D", signin.DESKTOP_KEY)
    assert signin.client_record(S(web="W", desktop="D")) == ("W", signin.RECORD_KEY)
    assert signin.client_record(S()) == ("", "")


def test_next_is_a_console_route_only(tmp_path):
    google = FakeGoogle()
    c = webclient.client(_app(tmp_path, _sign_in(google)))
    _, back = _go(c, google, nxt="https://evil.example/")
    assert back.headers["Location"] == "/"


def test_sign_in_answers_only_on_this_servers_name(tmp_path):
    c = _app(tmp_path, _sign_in(FakeGoogle())).test_client()
    assert c.get("/auth/google", headers={"Host": "evil.example"}).status_code == 421
    assert c.get("/auth/google/callback", headers={"Host": "evil.example"}).status_code == 421


# --- the ID token ------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("over, why", [
    ({"iss": "https://evil.example"}, "not from Google"),
    ({"aud": "someone-else"}, "another client"),
    ({"exp": time.time() - 3600}, "expired"),
    ({"nonce": "replayed"}, "nonce"),
    ({"email_verified": False}, "vouch"),
    ({"hd": "gmail.com"}, "Google Workspace"),
    ({"hd": None}, "Google Workspace"),
    ({"email": "stranger@example.org"}, "not on the roster"),
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


# --- several providers -------------------------------------------------------------------------------------------

def test_each_provider_uses_its_own_client_and_domains(tmp_path):
    google = FakeGoogle()
    roster = ROSTER + (Person("Mo Manager", "manager", "mo@mgmt.example"),)
    providers = (_provider("google", "community-cid", ("example.org",)),
                 _provider("mgmt", "mgmt-cid", ("mgmt.example",), label="Management company", source="jason"))
    c = webclient.client(_app(tmp_path, _sign_in(google, roster=roster, providers=providers)))
    s = c.get("/api/session").json
    assert [p["key"] for p in s["signIn"]["providers"]] == ["google", "mgmt"]
    q, _ = _go(c, google, provider="mgmt", email="mo@mgmt.example", hd="mgmt.example")
    assert q["client_id"] == "mgmt-cid" and q["hd"] == "mgmt.example"
    assert c.get("/api/session").json["signedIn"]["name"] == "Mo Manager"
    c.post("/auth/signout")
    _go(c, google, provider="google", email="mo@mgmt.example", hd="mgmt.example")       # the community's: not its domain
    assert "Google Workspace" in c.get("/api/session").json["signInError"]
    q, _ = _go(c, google, provider="nope")                                              # unknown: the first
    assert q["client_id"] == "community-cid"


def test_default_providers_order_community_then_installation_then_env(monkeypatch, tmp_path):
    from jason.community.base import SignInProvider

    class C:
        def __init__(self, own):
            self.own = own

        def sign_in(self):
            return self.own

        def email_domains(self):
            return ("example.org",)

    paths = {}

    def loader(uid, path="", source=""):
        paths[uid] = path
        return lambda: Client(uid, "s")

    monkeypatch.setattr(signin, "keeper_client", loader)
    monkeypatch.setattr("jason.community.profile.profile_name", lambda: "oakview")
    monkeypatch.setattr("jason.access.installation_sign_in", lambda root=None: (SignInProvider("mgmt", "R2", domains=("mgmt.example",)),))
    monkeypatch.setattr("jason.community.community", lambda: C((SignInProvider("google", "R1"),)))
    got = signin.default_providers()
    assert [(p.key, p.source, p.domains, p.load().client_id) for p in got] == [
        ("google", "community", ("example.org",), "R1"), ("mgmt", "jason", ("mgmt.example",), "R2")]
    assert paths == {"R1": "jason/community/oakview/signin/oauth-client/google",          # the vault path first
                     "R2": "jason/instance/instance/signin/oauth-client/mgmt"}
    monkeypatch.setattr("jason.access.installation_sign_in", lambda root=None: ())
    monkeypatch.setattr("jason.community.community", lambda: C(()))

    class S:
        record_uids = {}
        google_oauth_record_uid = "D"
    monkeypatch.setattr(signin, "_settings", lambda: S())
    got = signin.default_providers()
    assert [(p.key, p.source, p.load().client_id) for p in got] == [("google", signin.DESKTOP_KEY, "D")]
    assert paths["D"] == "jason/community/oakview/google-workspace/oauth-client"


# --- writes ------------------------------------------------------------------------------------------------------

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


def test_a_person_taken_off_the_roster_is_signed_out(tmp_path):
    google = FakeGoogle()
    roster = list(ROSTER)
    c = webclient.client(_app(tmp_path, _sign_in(google, roster=lambda: tuple(roster))))
    _go(c, google)
    roster.pop(0)
    r = c.post("/api/board-items/x", json={"by": ""})
    assert r.status_code == 401 and "no longer on the roster" in r.json["error"]
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


# --- the roster: two offices, portfolio managers, jason's admins -------------------------------------------------

def _officer(role, name, email=""):
    from jason.community.base import Officer, OfficerRole
    from mystique.officers import DEFAULT_APPROVES

    r = OfficerRole(role)
    return Officer(r, name, DEFAULT_APPROVES[r], email)


def test_two_offices_portfolio_managers_and_admins_on_one_roster():
    rows = (_officer("secretary", "Sam Example", "sam@example.org"), _officer("treasurer", "Sam Example", "sam@example.org"),
            _officer("president", "Pat Example"))
    people = signin.roster_of(rows, admins=(Admin("Sam Example", "SAM@example.org"), Admin("Ada Admin", "ada@jason.example")),
                              managers=(Manager("Mo Manager", "mo@mgmt.example", ("this", "other")),
                                        Manager("Not Ours", "no@mgmt.example", ("other",)),
                                        Manager("Everywhere", "all@mgmt.example", ("*",))),
                              community="this")
    by = {p.name: p for p in people}
    assert by["Sam Example"] == Person("Sam Example", "secretary, treasurer", "sam@example.org", True)
    assert by["Pat Example"] == Person("Pat Example", "president", "", False)            # no address: cannot sign in
    assert by["Mo Manager"] == Person("Mo Manager", "manager", "mo@mgmt.example", False)
    assert by["Everywhere"].role == "manager" and "Not Ours" not in by
    assert by["Ada Admin"] == Person("Ada Admin", "admin", "ada@jason.example", True)    # an admin holds no office
    a = account_for(_claims("n", email="sam@example.org"), client_id="cid", nonce="n", roster=people, domains=())
    assert (a.name, a.role, a.admin) == ("Sam Example", "secretary, treasurer", True)


def test_the_letters_check_reads_every_office_and_the_portfolio_manager(monkeypatch, tmp_path):
    from jason.tasks import approvals as letters

    class C:
        def officers(self):
            return (_officer("secretary", "Sam Example"), _officer("treasurer", "Sam Example"))

    (tmp_path / "managers.json").write_text(json.dumps([{"name": "Mo Manager", "email": "mo@mgmt.example",
                                                         "communities": ["mystique"]}]), encoding="utf-8")
    monkeypatch.setenv("JASON_ACCESS_DIR", str(tmp_path))
    monkeypatch.setenv("JASON_PROFILE", "mystique")
    monkeypatch.setattr("jason.community.community", lambda: C())
    assert "as the treasurer" in letters._approval_check({"approver": "the treasurer"}, "Sam Example", None)
    assert "recorded by Sam Example, secretary" in letters._approval_check({"approver": "the board"}, "Sam Example", "2026-10-20")
    assert "Mo Manager (manager) as the manager" in letters._approval_check({"approver": "the manager"}, "Mo Manager", None)
    monkeypatch.setenv("JASON_PROFILE", "elsewhere")
    with pytest.raises(ValueError, match="not one of the association's officers"):
        letters._approval_check({"approver": "the manager"}, "Mo Manager", None)


def test_access_files_read_and_write(tmp_path):
    from jason.access import admins, managers, providers_from, write_sign_in
    from jason.community.base import IdentityProvider, SignInProvider

    (tmp_path / "admins.json").write_text(json.dumps([{"name": "Ada", "email": "ADA@x.example"}, {"name": ""}]), encoding="utf-8")
    (tmp_path / "managers.json").write_text(json.dumps([{"name": "Mo", "email": "mo@x.example", "communities": "*"}]), encoding="utf-8")
    assert admins(tmp_path) == (Admin("Ada", "ada@x.example"),)
    assert managers(tmp_path)[0].manages("anything")
    assert providers_from([{"record_uid": "R", "provider": "facebook"}, {"record_uid": ""}, {"record_uid": "R2"}]) == (
        SignInProvider("google-3", "R2"),)
    vault = "jason/community/oakview/signin/oauth-client/google"
    assert providers_from([{"key": "google", "vault": vault}]) == (SignInProvider("google", "", vault=vault),)
    path = tmp_path / "sign_in.json"
    write_sign_in(path, SignInProvider("google", "R1", IdentityProvider.GOOGLE, ("x.example",), "Board"))
    write_sign_in(path, SignInProvider("google", "R9"))                                   # same key: replaced
    assert json.loads(path.read_text(encoding="utf-8")) == [{"key": "google", "provider": "google", "record_uid": "R9"}]
    write_sign_in(path, SignInProvider("google", "", vault=vault))                         # the vault form
    assert json.loads(path.read_text(encoding="utf-8")) == [{"key": "google", "provider": "google", "vault": vault}]
    with pytest.raises(ValueError, match="neither"):
        write_sign_in(path, SignInProvider("google", ""))


# --- the admin view (--dev) --------------------------------------------------------------------------------------

DEV_ROSTER = (Person("Sam Example", "secretary, treasurer", "sam@example.org", True), Person("Pat Example", "president", ""),
              Person("A Manager", "manager", "a.manager@example.org"))


def _dev_app(tmp_path, *, dev=True):
    google = FakeGoogle()
    return webclient.client(_app(tmp_path, _sign_in(google, roster=DEV_ROSTER, dev=dev))), google


def test_an_admin_views_as_anyone_under_dev_and_writes_nothing_meanwhile(tmp_path):
    c, google = _dev_app(tmp_path)
    _go(c, google, email="sam@example.org")
    s = c.get("/api/session").json
    assert s["canActAs"] is True and s["signedIn"]["admin"] is True and "director" in s["actAsRoles"]
    assert [p["name"] for p in s["actAsPeople"]] == ["Sam Example", "Pat Example", "A Manager"]
    r = c.post("/auth/act-as", json={"name": "Pat Example"})
    assert r.status_code == 200 and r.json["acting"] == {"name": "Pat Example", "role": "president"}
    assert c.get("/api/session").json["acting"] == {"name": "Pat Example", "role": "president"}
    w = c.post("/api/board-items/x", json={"by": ""})
    assert w.status_code == 403 and "admin view" in w.json["error"]
    assert c.post("/auth/act-as", json={"role": "director"}).json["acting"] == {"name": "", "role": "director"}
    assert c.post("/auth/act-as", json={"role": "emperor"}).status_code == 400
    assert c.post("/auth/act-as", json={"name": "Nobody"}).status_code == 400
    assert c.post("/auth/act-as", json={}).json["acting"] is None
    assert c.post("/api/board-items/x", json={"by": ""}).json["by"] == "Sam Example"     # back to themselves


def test_viewing_as_someone_else_needs_dev_and_an_admin(tmp_path):
    c, google = _dev_app(tmp_path, dev=False)
    _go(c, google, email="sam@example.org")
    assert c.get("/api/session").json["canActAs"] is False
    assert c.post("/auth/act-as", json={"name": "Pat Example"}).status_code == 403      # production: no
    c2, google2 = _dev_app(tmp_path)
    _go(c2, google2, email="a.manager@example.org")
    assert c2.get("/api/session").json["canActAs"] is False
    assert c2.post("/auth/act-as", json={"name": "Pat Example"}).status_code == 403    # not an admin


# --- jason sign-in --import-client -------------------------------------------------------------------------------

def _download(tmp_path, kind="web"):
    path = tmp_path / "client_secret_123.apps.googleusercontent.com.json"
    path.write_text(json.dumps({kind: {"client_id": "123-abc.apps.googleusercontent.com", "project_id": "proj-1",
                                       "client_secret": SECRET}}), encoding="utf-8")
    return path


def _args(**kw):
    base = {"import_client": None, "for_": "community", "key": None, "label": None, "domain": None, "title": None,
            "delete_file": False, "yes": False}
    base.update(kw)
    return argparse.Namespace(**base)


def test_import_client_says_what_it_would_do_without_yes(tmp_path, capsys, monkeypatch):
    from jason.commands import sign_in as cmd

    monkeypatch.setattr(cmd, "_target", lambda where: tmp_path / f"{where}-sign_in.json")
    path = _download(tmp_path)
    assert cmd.cmd_sign_in(_args(import_client=str(path)), lambda a: None) == 0
    out = capsys.readouterr().out
    assert "Nothing written" in out and SECRET not in out and path.is_file()
    assert not (tmp_path / "community-sign_in.json").exists()


def _vault_agent(monkeypatch, store):
    """A real ``Jason`` whose vault is ``store`` (a MemoryStore): nothing reaches Keeper."""
    from jason.agent import Jason
    from jason.config import Settings

    settings = Settings(keeper_username="", payhoa_record_uid="", smud_record_uid="", idoxs_record_uid="",
                        payhoa_org_id=1, smud_category_id=None, idoxs_category_id=None)
    agent = Jason(settings=settings)
    monkeypatch.setattr(agent, "vault_store", lambda: store)
    return agent


def test_import_client_stores_in_the_vault_records_its_path_and_never_prints_the_secret(tmp_path, capsys, monkeypatch,
                                                                                        memory_vault):
    from jason.commands import sign_in as cmd

    agent = _vault_agent(monkeypatch, memory_vault)

    @contextmanager
    def factory(args):
        yield agent

    monkeypatch.setattr(cmd, "_target", lambda where: tmp_path / f"{where}-sign_in.json")
    path = _download(tmp_path)
    args = _args(import_client=str(path), for_="jason", label="Management company", domain=["Mgmt.example"],
                 delete_file=True, yes=True)
    assert cmd.cmd_sign_in(args, factory) == 0
    out = capsys.readouterr().out
    where = "jason/instance/instance/signin/oauth-client/jason-google"
    assert SECRET not in out and where in out and "_record_uid" not in out
    stored = memory_vault.get(where)
    assert (stored["client_id"], stored["login"], stored["password"], stored["project_id"]) == (
        "123-abc.apps.googleusercontent.com", "123-abc.apps.googleusercontent.com", SECRET, "proj-1")
    assert json.loads((tmp_path / "jason-sign_in.json").read_text(encoding="utf-8")) == [
        {"key": "jason-google", "provider": "google", "vault": where, "domains": ["mgmt.example"],
         "label": "Management company"}]
    assert not path.exists()                                                          # --delete-file
    # Create only: a second import to the same path leaves the vault and the file as they are.
    again = _download(tmp_path)
    assert cmd.cmd_sign_in(_args(import_client=str(again), for_="jason", yes=True), factory) == 2
    out = capsys.readouterr().out
    assert "already holds" in out and SECRET not in out and again.exists()
    assert memory_vault.describe(where).version == 1


def test_a_sign_in_client_reads_its_vault_path_first_then_the_old_record(monkeypatch, memory_vault):
    import jason.secrets as secrets
    from jason.vault.keeper import KeeperStore

    where = "jason/community/oakview/signin/oauth-client/google"
    loaded = []

    class Session:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return None

    class Store:
        def get(self, path):
            return memory_vault.get(path)

        def load_by_uid(self, uid):
            loaded.append(uid)
            return {"login": "old-client", "password": "old-made-up"}

    monkeypatch.setattr(secrets.VaultSession, "from_settings", classmethod(lambda cls, s, interactive=False: Session()))
    monkeypatch.setattr(KeeperStore, "from_session", classmethod(lambda cls, session, folder="jason": Store()))
    monkeypatch.setattr(signin, "_settings", lambda: None)
    assert signin.keeper_client("R1", where)().client_id == "old-client" and loaded == ["R1"]   # not moved yet
    memory_vault.put(where, {"client_id": "new-client", "client_secret": SECRET})
    client = signin.keeper_client("R1", where)()
    assert (client.client_id, client.client_secret, loaded) == ("new-client", SECRET, ["R1"])   # the vault first
    assert SECRET not in repr(client)
    with pytest.raises(Refused, match="no sign-in client"):
        signin.keeper_client("", "jason/community/oakview/signin/oauth-client/other")()


def test_import_client_refuses_a_file_that_is_not_a_client(tmp_path):
    from jason.commands import sign_in as cmd

    bad = tmp_path / "x.json"
    bad.write_text(json.dumps({"type": "service_account"}), encoding="utf-8")
    with pytest.raises(ValueError, match="not a Google OAuth client"):
        cmd._read_client(bad)
