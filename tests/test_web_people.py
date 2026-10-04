"""The People and offices loader (``jason.web.extra.people``, ``GET /api/people``): a signed-in roster person only, never
the owner view; each office with who holds it and what it approves, a person holding two offices, a vacant office that
says so and routes nothing, and jason's admins apart as no office. Made-up people, tmp data folders, and the made-up
private facts in tests/fixtures/spec only; nothing reaches Google, Keeper, or PayHOA.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import webclient

from jason.access import Admin, Manager
from jason.community.base import Officer, OfficerRole, VacancyProvision
from jason.community.schedule import Adoption, Assignment, Role, Trigger
from jason.web.extra.people import CHANGE, NO_PROVISION, NOT_AN_OFFICE, TERMS, people_of
from jason.web.signin import Person

P, VP, S, T, D, M = (OfficerRole.PRESIDENT, OfficerRole.VICE_PRESIDENT, OfficerRole.SECRETARY, OfficerRole.TREASURER,
                     OfficerRole.DIRECTOR, OfficerRole.MANAGER)

# A made-up board: one person holds secretary and treasurer, no one holds vice president.
OFFICERS = (
    Officer(P, "Lee President", ("the president",), "lee@example.org"),
    Officer(S, "Tess Two", ("the secretary",), "tess@example.org"),
    Officer(T, "Tess Two", ("the treasurer",), "tess@example.org"),
    Officer(D, "Dana Director", (), ""),
)
ROSTER = (Person("Lee President", "president", "lee@example.org"), Person("Tess Two", "secretary, treasurer", "tess@example.org"),
          Person("Dana Director", "director", ""), Person("Ada Admin", "admin", "ada@example.org", True))
DUTIES = (
    Assignment("vp-review", "Review the sample policy", Role.VICE_PRESIDENT, ("CIV 0000",), Trigger.STANDING),
    Assignment("books", "Review the sample reconciliations", Role.TREASURER, ("CIV 0001",), Trigger.STANDING,
               adoption=Adoption.ADOPTED),
)


def _office(out: dict, name: str) -> dict:
    return next(o for o in out["offices"] if o["office"] == name)


def test_one_person_holding_two_offices_is_grouped_by_office_and_by_person():
    out = people_of(OFFICERS, roster=ROSTER)
    assert [h["name"] for h in _office(out, "secretary")["holders"]] == ["Tess Two"]
    assert [h["name"] for h in _office(out, "treasurer")["holders"]] == ["Tess Two"]
    tess = next(p for p in out["people"] if p["name"] == "Tess Two")
    assert tess["offices"] == ["secretary", "treasurer"]
    assert tess["approves"] == ["the secretary", "the treasurer"] and tess["recordsBoard"] is True
    assert tess["canSignIn"] is True
    assert next(p for p in out["people"] if p["name"] == "Dana Director")["canSignIn"] is False
    assert [h["name"] for h in out["directors"]["holders"]] == ["Dana Director"]


def test_a_vacant_office_says_so_and_routes_nothing():
    out = people_of(OFFICERS, roster=ROSTER, duties=DUTIES)
    vp = _office(out, "vice president")
    assert vp["vacant"] is True and vp["holders"] == []
    assert vp["vacancy"] == "No one holds the office of vice president."
    assert vp["provision"] is None and vp["provisionNote"] == NO_PROVISION
    [duty] = vp["duties"]
    assert duty["assigned"] is False and duty["owners"] == []
    assert duty["routing"].startswith("unassigned") and "president" not in duty["routing"].replace("vice president", "")
    assert out["vacant"] == ["vice president"]
    [books] = _office(out, "treasurer")["duties"]                                     # a held office's duty is routed to it
    assert books["assigned"] is True and books["owners"] == [{"role": "treasurer", "name": "Tess Two", "adoption": "adopted"}]


def test_a_vacancy_recites_the_provision_the_profile_keeps():
    said = VacancyProvision("Bylaws 9.9", "A sample vacancy is filled by the sample body.")
    out = people_of(OFFICERS, vacancy=lambda office: said if office is VP else None)
    vp = _office(out, "vice president")
    assert vp["provision"] == {"source": "Bylaws 9.9", "words": "A sample vacancy is filled by the sample body."}
    assert vp["provisionNote"] == ""
    assert _office(out, "president")["provision"] is None                        # held: no provision recited


def test_an_admin_is_not_an_office_and_approves_nothing():
    out = people_of(OFFICERS, roster=ROSTER, admins=(Admin("Ada Admin", "ada@example.org"), Admin("Lee President", "lee@example.org")))
    ada = next(a for a in out["admins"] if a["name"] == "Ada Admin")
    assert ada == {"name": "Ada Admin", "holds": [], "canSignIn": True, "note": NOT_AN_OFFICE}
    assert next(a for a in out["admins"] if a["name"] == "Lee President")["holds"] == ["president"]
    person = next(p for p in out["people"] if p["name"] == "Ada Admin")
    assert person["offices"] == [] and person["approves"] == [] and person["admin"] is True
    assert all("Ada Admin" not in [h["name"] for h in o["holders"]] for o in out["offices"])


def test_a_portfolio_manager_is_management_not_an_office():
    out = people_of(OFFICERS, managers=(Manager("Pat Manager", "pat@example.org", ("sample",)),), community="sample")
    [m] = out["management"]["holders"]
    assert m["name"] == "Pat Manager" and m["approves"] == ["the manager"] and m["portfolio"] is True
    assert out["management"]["note"] == "Management, not an office of the board."
    assert "manager" not in [o["office"] for o in out["offices"]]


def test_emails_are_masked_unless_shown_and_terms_are_not_on_file():
    out = people_of(OFFICERS, roster=ROSTER)
    assert "example.org" not in json.dumps(out)
    assert next(p for p in out["people"] if p["name"] == "Lee President")["email"] == "[email]"
    shown = people_of(OFFICERS, roster=ROSTER, unmask=True)
    assert next(p for p in shown["people"] if p["name"] == "Lee President")["email"] == "lee@example.org"
    assert out["terms"] == {"onFile": False, "note": TERMS}
    assert out["change"]["note"] == CHANGE and out["change"]["onboardingItem"] == "board-roster"


# --- the route -----------------------------------------------------------------------------------------------------------

# The made-up officers in tests/fixtures/spec, on the sign-in roster with made-up addresses.
FIXTURE_ROSTER = (("Quill Ashgrove", "president", "quill@example.org", False), ("Ilse Varnholt", "treasurer", "ilse@example.org", False),
                  ("Odo Fennimore", "secretary", "odo@example.org", False), ("Ada Admin", "admin", "ada@example.org", True))


@pytest.fixture
def app(tmp_path, monkeypatch):
    from jason.web.app import create_app
    from jason.web.extra.people import people

    root = tmp_path / "data"
    root.mkdir()
    monkeypatch.setattr("jason.mcp.county._data_dir", lambda d: Path(d) if d is not None else root)
    monkeypatch.setenv("JASON_ACCESS_DIR", str(tmp_path / "access"))              # no admins or managers on disk
    dist = tmp_path / "dist"
    dist.mkdir()
    return create_app(dist, {"people": people}, approvals_live=None, extra_writes=False,
                      sign_in=webclient.roster_sign_in(FIXTURE_ROSTER))


def test_the_route_needs_a_sign_in(app):
    r = webclient.client(app).get("/api/people")
    assert r.status_code == 401 and r.json["signIn"] == "/auth/google"


def test_the_owner_view_is_refused(app):
    c = webclient.sign_in(webclient.client(app), "Quill Ashgrove", rows=FIXTURE_ROSTER)
    r = c.get("/api/people?view=owner")
    assert r.status_code == 403 and r.json["ownerView"] is True


def test_the_route_answers_a_roster_person_with_emails_masked(app):
    c = webclient.sign_in(webclient.client(app), "Ilse Varnholt", rows=FIXTURE_ROSTER)
    r = c.get("/api/people")
    assert r.status_code == 200, r.json
    out = r.json
    assert [h["name"] for h in _office(out, "president")["holders"]] == ["Quill Ashgrove"]
    assert _office(out, "treasurer")["holders"][0]["canSignIn"] is True
    assert "example.org" not in r.get_data(as_text=True) and out["emailsShown"] is False


def test_the_private_view_shows_emails_and_logs_it(app, tmp_path):
    c = webclient.sign_in(webclient.client(app), "Odo Fennimore", rows=FIXTURE_ROSTER)
    assert c.post("/api/private", json={"reason": "board roster check"}).status_code == 200
    out = c.get("/api/people").json
    assert out["emailsShown"] is True
    assert next(p for p in out["people"] if p["name"] == "Odo Fennimore")["email"] == "odo@example.org"
    log = (tmp_path / "data" / "access" / "served.jsonl").read_text(encoding="utf-8")
    assert '"address": "api/people"' in log and '"level": "P2"' in log


def test_people_is_no_owner_source():
    from jason.web.extra.owner_view import OWNER_SOURCES

    assert "people" not in OWNER_SOURCES
