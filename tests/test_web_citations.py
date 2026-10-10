"""The reference shelf and citations in the console: four read-only loaders over disk, board only."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import webclient
from jason.community.reference_shelf import REFERENCE_WORKS
from jason.tasks.citation_coverage import save, survey
from jason.web.app import create_app
from jason.web.extra import citations as loader
from jason.web.extra.owner_view import OWNER_SOURCES
from jason.web.sources import default_loaders

WORK = REFERENCE_WORKS[0]
TEXT = ("\n<<PAGE 1>>\nUnder Government Code Section 66424 a subdivision is the division of land.\n"
        "<<PAGE 2>>\nSee Government Code Section 66427 and BPC Section 11500 and BPC Section 11001.1 of the SLA.\n"
        "<<PAGE 3>>\n")
NAMES = ("reference-works", "citations", "citation-gaps", "reference-page")


class Law:
    def spans(self, spans):
        return tuple(SimpleNamespace(found=(c, a) in {("GOV", "66427"), ("BPC", "11500")}) for c, a, _ in spans)


@pytest.fixture
def data(tmp_path, monkeypatch):
    root = tmp_path / "data"
    (root / "authorities").mkdir(parents=True)
    pages = [{"code": "GOV", "start": "66410", "end": "66424.6", "sections": ["66410", "66424"]},
             {"code": "BPC", "start": "11000", "end": "11023", "sections": ["11000", "11010"]}]
    (root / "authorities" / "manifest.json").write_text(json.dumps({"pages": pages}), encoding="utf-8")
    folder = root / "reference"
    folder.mkdir()
    (folder / WORK.filename).write_bytes(b"%PDF-1.4")
    (folder / (Path(WORK.filename).stem + ".txt")).write_text(TEXT, encoding="utf-8")
    monkeypatch.setattr(loader, "_root", lambda: root)
    return root


@pytest.fixture
def web(data, tmp_path):
    loaders = {k: v for k, v in default_loaders().items() if k in NAMES}
    return webclient.client(create_app(tmp_path / "dist", loaders))


def test_the_works_list_says_how_far_to_trust_each_and_what_is_kept(data, web):
    first = web.get("/api/reference-works").json["works"][0]
    assert first["title"] == WORK.title and first["onDisk"] and first["pages"] == 3
    assert first["caveat"] == WORK.caveat and first["surveyed"] is None and first["counts"] is None
    assert first["command"] == f"jason reference --cites {WORK.filename}"
    save(data, WORK.title, survey({WORK.title: TEXT}, data, library=Law(), external=True))
    kept = web.get("/api/reference-works").json["works"][0]
    assert kept["surveyed"] and kept["lawChecked"] is True and kept["command"] is None
    assert kept["counts"] == {"ON_SHELF": 1, "NOT_EXPORTED": 2, "NOT_FOUND": 1}
    assert web.get("/api/reference-works").json["caveats"]


def test_citations_lists_the_sources_then_one_works_sections(data, web):
    assert [s["source"] for s in web.get("/api/citations").json["sources"]] == [WORK.title, "ingest"]
    one = web.get("/api/citations?source=subdivisions&limit=2").json
    assert one["found"] and one["total"] == 4 and one["shown"] == 2 and len(one["sections"]) == 2
    assert one["sections"][0]["standing"] == "NOT_FOUND" and one["sections"][0]["citation"] == "BPC 11001.1"      # a gap first
    assert web.get("/api/citations?source=ingest").json["found"] is False


def test_the_gaps_join_the_surveys_and_give_one_proposal(data, web):
    assert web.get("/api/citation-gaps").json["found"] is False
    save(data, WORK.title, survey({WORK.title: TEXT}, data, library=Law(), external=True))
    gaps = web.get("/api/citation-gaps").json
    assert gaps["found"] and gaps["proposal"] == "BPC 11500; GOV 66427"
    assert {g["citation"] for g in gaps["gaps"]} == {"BPC 11001.1", "BPC 11500", "GOV 66427"}


def test_a_page_of_a_work_carries_its_banner_and_caveat(data, web):
    page = web.get(f"/api/reference-page?work={WORK.filename}&page=2").json
    assert page["found"] and page["page"] == 2 and page["pages"] == 3 and "Section 66427" in page["text"]
    assert page["banner"].startswith("An explanation, not the law") and page["caveat"] == WORK.caveat and page["noText"] is False
    assert web.get("/api/reference-page?work=subdivisions").json["page"] == 1                 # a title fragment; page defaults to 1
    assert web.get("/api/reference-page?work=subdivisions&page=3").json["noText"] is True      # a page with no text layer


def test_a_missing_work_or_page_is_a_note_and_a_bad_number_is_refused(data, web):
    assert web.get("/api/reference-page?work=nothing").json["found"] is False
    assert web.get("/api/reference-page?work=subdivisions&page=9").json["pages"] == 3
    for bad in ("page=x", "page=0", "page=-2"):
        assert web.get(f"/api/reference-page?work=subdivisions&{bad}").status_code == 400
    assert web.get("/api/citations?limit=abc").status_code == 400 and web.get("/api/citation-gaps?limit=0").status_code == 400


def test_the_works_not_on_disk_give_the_command(data, web):
    (data / "reference" / (Path(WORK.filename).stem + ".txt")).unlink()
    note = web.get(f"/api/reference-page?work={WORK.filename}").json
    assert note["found"] is False and note["command"] == "jason reference --fetch"
    assert web.get("/api/reference-works").json["works"][0]["pages"] == 0


def test_these_are_board_loaders_the_owner_view_never_answers():
    assert not set(NAMES) & set(OWNER_SOURCES)
