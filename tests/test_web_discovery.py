"""Discovery in the console: the county's associations from asspy's directory and the documents the locator saved, read
from disk; a fresh locate is a job a person queues, never a county read in the web process."""

import json
from datetime import date

import pytest

import webclient
from jason import jobs
from jason.community.locator import Tie
from jason.tasks import document_locator
from jason.tasks.document_locator import Located, Location
from jason.web.extra import discovery

ASSOCIATION = "EXAMPLE CREEK HOMEOWNERS ASSOCIATION"
OWN = ("example_creek", "Example Creek Homeowners Association", "placer")
OWNER = "PRIVATE OWNER"


@pytest.fixture
def data(tmp_path, monkeypatch):
    root = tmp_path / "data"
    monkeypatch.setattr(discovery, "_root", lambda: root)
    monkeypatch.setattr(discovery, "_active", lambda: OWN)
    monkeypatch.setenv("ASSPY_HOME", str(tmp_path / "asspy"))
    monkeypatch.setenv("JASON_LOCK_DIR", str(tmp_path / "locks"))
    return root


def _survey(tmp_path):
    from asspy.associations import Directory, Governing, Link, Sighting, key

    lien = "NOTICE OF DELINQUENT ASSESSMENT - HOMEOWNERS ASSOCIATION"
    with Directory(tmp_path / "asspy" / "counties" / "placer" / "associations.db") as directory:
        directory.store((
            Sighting(key(ASSOCIATION), ASSOCIATION, "2020-0000001", lien, date(2020, 1, 2)),
            Sighting(key("EXAMPLE CREEK HOA"), "EXAMPLE CREEK HOA", "2005-0000001", lien, date(2005, 1, 2)),
            Sighting(key("EXAMPLE OAKS OWNERS ASSN"), "EXAMPLE OAKS OWNERS ASSN", "2011-0000009", "DEED", date(2011, 4, 1)),
            Sighting(key("EXAMPLE BANK NATIONAL ASSOCIATION"), "EXAMPLE BANK NATIONAL ASSOCIATION", "2020-0000002",
                     "DEED OF TRUST", date(2020, 1, 2)),
        ), (Governing("2001-0000010", date(2001, 3, 1), "DECLARATION OF RESTRICTIONS", ("EXAMPLE BUILDERS LLC",),
                      (key(ASSOCIATION),)),))
        directory.add_link(Link("2003-0000050", key(ASSOCIATION), "2003-0000049", "recorded beside"))


def test_a_county_not_surveyed_gives_the_command_and_creates_nothing(data, tmp_path):
    out = discovery.associations({"county": "Placer County"})
    assert out["surveyed"] is False and out["results"] == []
    assert out["command"].startswith("python -m asspy.associations_cli placer")
    assert not (tmp_path / "asspy").exists()
    assert discovery.associations({"county": "", "q": "x"})["county"] == "placer"      # the profile's region
    assert any("lead, not a pin" in c for c in out["caveats"])


def test_the_directory_is_searched_with_its_summary(data, tmp_path):
    _survey(tmp_path)
    out = discovery.associations({"county": "Placer", "q": "creek", "limit": "5"})
    assert out["surveyed"] is True and "command" not in out
    assert [r["name"] for r in out["results"]] == [ASSOCIATION]
    row = out["results"][0]
    assert row["key"] and row["kind"] == "homeowners" and row["standing"] == "confirmed"
    assert set(row["spellings"]) == {ASSOCIATION, "EXAMPLE CREEK HOA"}
    assert row["governing"] == 1 and row["links"] == 1 and row["score"] is not None
    assert row["first"] == "2005-01-02" and row["last"] == "2020-01-02"
    assert isinstance(out["summary"], dict) and out["summary"]
    every = discovery.associations({"county": "Placer"})
    names = [r["name"] for r in every["results"]]
    assert ASSOCIATION in names and "EXAMPLE OAKS OWNERS ASSN" in names
    assert "EXAMPLE BANK NATIONAL ASSOCIATION" not in names                         # a bank is not an association
    assert discovery.associations({"county": "Placer", "limit": "1"})["count"] == 1
    with pytest.raises(ValueError):
        discovery.associations({"county": "Placer", "limit": "many"})


def _location() -> Location:
    return Location(ASSOCIATION, "Placer County", (ASSOCIATION,), [
        Located("2001-0000010", date(2001, 3, 1), "DECLARATION OF RESTRICTIONS", "declaration", Tie.BESIDE,
                ("EXAMPLE BUILDERS LLC",), via="2001-0000011"),
        Located("2001-0000011", date(2001, 3, 1), "DEED", "common-area-deeds", Tie.NAMED,
                ("EXAMPLE BUILDERS LLC", ASSOCIATION)),
        Located("2003-0000050", date(2003, 6, 1), "DECLARATION ANNEX SUBDV", "annexations", Tie.DECLARANT,
                ("EXAMPLE BUILDERS LLC",), via="EXAMPLE BUILDERS LLC"),
    ], liens=12, notes=["builders on its governing instruments: EXAMPLE BUILDERS LLC"], searches=9)


def test_documents_located_is_missing_until_a_locate_ran_then_the_saved_result(data):
    out = discovery.documents_located({})
    assert out["missing"] is True and out["command"] == "jason onboard --locate --county placer"
    assert out["profile"] == "example_creek" and "job" not in out
    assert not (data / "jobs.db").exists()                                          # reading never creates the queue

    found = _location()
    document_locator.save(found, data, "example_creek", located_at="2099-01-01T00:00:00+00:00")
    out = discovery.documents_located({})
    assert "missing" not in out and out["located_at"] == "2099-01-01T00:00:00+00:00"
    assert out["association"] == ASSOCIATION and out["liens"] == 12 and out["searches"] == 9
    items = {i["item"]: i for i in out["items"]}
    decl = items["declaration"]
    assert decl["stakes"] is True and decl["question"] and decl["title"]
    assert decl["located"] == [{"number": "2001-0000010", "recorded": "2001-03-01", "filing": "DECLARATION OF RESTRICTIONS",
                                "tie": "beside", "tie_label": Tie.BESIDE.value, "strong": True, "via": "2001-0000011",
                                "parties": ["EXAMPLE BUILDERS LLC"]}]
    assert items["annexations"]["located"][0]["strong"] is False
    assert {n["item"] for n in out["not_located"]} == {"amendments", "maps"}
    assert out["report"] == "onboarding/example_creek-documents-located.md" and out["caveats"]
    assert OWNER not in json.dumps(out)
    # read back as a Location: the same instruments and ties
    again = Location.from_dict(json.loads((data / "onboarding" / "example_creek-documents-located.json").read_text("utf-8")))
    assert [(x.number, x.item, x.tie, x.via) for x in again.found] == [(x.number, x.item, x.tie, x.via) for x in found.found]
    assert again.markdown() == found.markdown()

    other = discovery.documents_located({"county": "Placer", "name": "Example Oaks Owners Assn"})
    assert other["missing"] is True and other["profile"] == ""
    assert other["command"] == 'jason onboard --locate --county Placer --name "Example Oaks Owners Assn"'


def test_a_locate_is_a_job_a_person_queues(data):
    with pytest.raises(ValueError, match="by"):
        discovery.write("locate", {})
    with pytest.raises(ValueError, match="no reader"):
        discovery.write("locate", {"county": "Nowhere", "by": "A Person"})
    with pytest.raises(KeyError):
        discovery.write("other", {"by": "A Person"})

    out = discovery.write("locate", {"by": "A Person"})
    assert out["existing"] is False and out["command"] == "jason onboard --locate --county placer"
    job = jobs.get(data, out["job"]["id"])
    assert job.argv == ["onboard", "--locate", "--county", "placer"] and job.job_class is jobs.JobClass.COUNTY
    assert job.status is jobs.JobStatus.QUEUED and not job.writes and job.confirmed_by == ""
    asked = [json.loads(line) for line in (data / "onboarding" / "locate-requests.jsonl").read_text("utf-8").splitlines()]
    assert asked[0]["job"] == job.id and asked[0]["by"] == "A Person"

    again = discovery.write("locate", {"county": "placer", "by": "Another Person"})
    assert again["existing"] is True and again["job"]["id"] == job.id                  # one locate at a time
    shown = discovery.documents_located({})
    assert shown["missing"] is True and shown["job"] == {**shown["job"], "id": job.id, "status": "queued",
                                                         "requested_by": "A Person", "resource": "county"}

    named = discovery.write("locate", {"county": "Placer", "name": "Example Oaks Owners Assn", "by": "A Person"})
    assert named["job"]["id"] != job.id
    assert jobs.get(data, named["job"]["id"]).argv[-2:] == ["--name", "Example Oaks Owners Assn"]
    assert discovery.documents_located({"county": "Placer", "name": "Example Oaks Owners Assn"})["job"]["id"] == named["job"]["id"]


def test_the_routes_serve_the_loaders_and_the_write(data, tmp_path):
    from jason.web.app import create_app
    from jason.web.sources import default_loaders

    loaders = {k: v for k, v in default_loaders().items() if k in ("associations", "documents-located")}
    c = webclient.client(create_app(tmp_path, loaders))
    assert c.get("/api/associations?county=Placer").json["surveyed"] is False
    assert c.get("/api/documents-located").json["missing"] is True
    posted = c.post("/api/write/documents-located/locate", json={"by": "A Person"})
    assert posted.status_code == 200 and posted.json["job"]["status"] == "queued"
    assert c.post("/api/write/documents-located/locate", json={}).status_code == 400
    assert c.post("/api/write/documents-located/other", json={"by": "A Person"}).status_code == 404


def test_the_mcp_tools_read_the_same(data, tmp_path, monkeypatch):
    from jason.mcp import discovery as tools

    monkeypatch.setattr(document_locator, "active", lambda: OWN)
    assert tools.association_directory("Placer")["surveyed"] is False
    assert tools.documents_located(data_dir=data)["missing"] is True
    document_locator.save(_location(), data, "example_creek", located_at="2099-01-01T00:00:00+00:00")
    assert tools.documents_located(data_dir=data)["items"]


def test_the_county_lane():
    assert jobs.job_class(["onboard", "--locate", "--county", "placer"]) is jobs.JobClass.COUNTY
    assert jobs.job_class(["onboard", "--lookup"]) is jobs.JobClass.COUNTY
    assert jobs.job_class(["onboard", "--checklist"]) is jobs.JobClass.LOCAL
