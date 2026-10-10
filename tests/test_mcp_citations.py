"""The MCP tools for the statutes documents cite: reference works and the last ingest, against the authorities shelf."""

from __future__ import annotations

import json
from pathlib import Path

from jason import api
from jason.community.reference_shelf import REFERENCE_WORKS
from jason.mcp.citations import citation_gaps, document_citations
from jason.mcp.server import ALL_TOOLS, tools_for
from jason.tasks import ingest
from jason.tasks.citation_coverage import Standing, save, survey

WORK = REFERENCE_WORKS[0]
TEXT = ("<<PAGE 1>>\nUnder Government Code Section 66424 a subdivision is the division of land. "
        "<<PAGE 2>>\nSee Government Code Section 66427 and BPC Section 11500 and BPC Section 11001.1 of the SLA.")


def _shelf(root: Path, pages: list[dict]) -> None:
    (root / "authorities").mkdir(exist_ok=True)
    (root / "authorities" / "manifest.json").write_text(json.dumps({"pages": pages}), encoding="utf-8")


GOV_PAGE = {"code": "GOV", "start": "66410", "end": "66424.6", "sections": ["66410", "66424"]}
BPC_PAGE = {"code": "BPC", "start": "11000", "end": "11023", "sections": ["11000", "11010"]}


def _work(root: Path) -> None:
    folder = root / "reference"
    folder.mkdir(exist_ok=True)
    (folder / WORK.filename).write_bytes(b"%PDF-1.4")
    (folder / (Path(WORK.filename).stem + ".txt")).write_text(TEXT, encoding="utf-8")


class Law:
    def spans(self, spans):
        from types import SimpleNamespace

        return tuple(SimpleNamespace(found=(c, a) in {("GOV", "66427"), ("BPC", "11500")}) for c, a, _ in spans)


def test_the_tools_are_served_with_the_governance_systems_and_not_the_board_or_onboarding_sets():
    assert {"document_citations", "citation_gaps"} <= {t.__name__ for t in ALL_TOOLS}
    assert {"document_citations", "citation_gaps"} <= {t.__name__ for t in tools_for("governance")}
    assert not {"document_citations", "citation_gaps"} & {t.__name__ for t in tools_for("board") + tools_for("onboarding")}
    assert api.document_citations is document_citations and "citation_gaps" in api.__all__


def test_with_no_source_it_lists_what_can_be_read(tmp_path: Path):
    _work(tmp_path)
    found = document_citations(data_dir=tmp_path)
    assert [s["source"] for s in found["sources"]] == [WORK.title, "ingest"]
    assert found["sources"][0]["onDisk"] and found["sources"][0]["surveyed"] is None and found["caveats"]


def test_a_work_not_yet_surveyed_is_read_against_the_shelf_only_and_says_so(tmp_path: Path):
    _work(tmp_path)
    _shelf(tmp_path, [GOV_PAGE, BPC_PAGE])
    found = document_citations("subdivisions in california", data_dir=tmp_path)
    by = {s["citation"]: s for s in found["sections"]}
    assert by["GOV 66424"]["standing"] == "ON_SHELF" and by["GOV 66427"]["standing"] == "UNCHECKED"
    assert by["BPC 11001.1"]["standing"] == "NOT_FOUND" and by["BPC 11001.1"]["page"] == "2"       # inside a page's range, and lacking
    assert found["sections"][0]["citation"] == "BPC 11001.1"                                         # a gap is listed first
    assert found["lawChecked"] is False and "jason reference --cites" in found["note"]


def test_a_kept_survey_is_read_and_a_gap_since_exported_is_no_longer_a_gap(tmp_path: Path):
    _work(tmp_path)
    _shelf(tmp_path, [GOV_PAGE, BPC_PAGE])
    save(tmp_path, WORK.title, survey({WORK.title: TEXT}, tmp_path, library=Law(), external=True))
    before = document_citations(WORK.filename, data_dir=tmp_path)
    assert before["lawChecked"] and before["made"] and {"GOV 66427", "BPC 11500"} <= {s["citation"] for s in before["sections"] if s["standing"] == "NOT_EXPORTED"}
    assert before["proposal"] == "BPC 11500; GOV 66427"
    # The shelf grows: GOV 66427 and BPC 11500 are exported. The kept survey is placed against the shelf as it is now.
    _shelf(tmp_path, [{**GOV_PAGE, "end": "66430", "sections": ["66410", "66424", "66427"]}, BPC_PAGE,
                      {"code": "BPC", "start": "11500", "end": "11506", "sections": ["11500"]}])
    after = document_citations(WORK.filename, data_dir=tmp_path)
    assert after["proposal"] == "" and all(s["standing"] != "NOT_EXPORTED" for s in after["sections"])


def test_the_last_ingest_is_read_by_file_and_its_gaps_join_the_works(tmp_path: Path):
    _shelf(tmp_path, [GOV_PAGE])
    result = survey({"notice.pdf": "Under Government Code Section 66427 a notice is given.",
                     "other.pdf": "See Civil Code Section 4000."}, tmp_path, library=None)
    report = {"day": "2026-10-03", "citations": result.as_dict()}
    folder = tmp_path / ingest.FOLDER
    folder.mkdir()
    (folder / f"{ingest.REPORT_PREFIX}2026-10-03.json").write_text(json.dumps(report), encoding="utf-8")
    one = document_citations("ingest", file="notice", data_dir=tmp_path)
    assert [s["citation"] for s in one["sections"]] == ["GOV 66427"] and one["file"] == "notice"
    assert document_citations("ingest", data_dir=tmp_path)["total"] == 2

    _work(tmp_path)
    save(tmp_path, WORK.title, survey({WORK.title: TEXT}, tmp_path, library=Law(), external=True))
    gaps = citation_gaps(data_dir=tmp_path)
    by = {g["citation"]: g for g in gaps["gaps"]}
    assert sorted(by["GOV 66427"]["citedBy"]) == sorted([WORK.title, "notice.pdf"]) and by["GOV 66427"]["mentions"] == 2
    assert gaps["unchecked"] == 1 and {s["kind"] for s in gaps["surveys"]} == {"reference", "ingest"}      # CIV 4000: not asked
    assert gaps["proposal"] == "BPC 11500; GOV 66427"


def test_nothing_surveyed_is_a_note_and_a_missing_source_names_the_choices(tmp_path: Path):
    assert not citation_gaps(data_dir=tmp_path)["found"] and "jason reference --cites" in citation_gaps(data_dir=tmp_path)["note"]
    assert not document_citations("ingest", data_dir=tmp_path)["found"]
    missing = document_citations("no such guide", data_dir=tmp_path)
    assert not missing["found"] and [s["source"] for s in missing["sources"]][0] == WORK.title
    assert not (tmp_path / "citations").exists()                       # reading writes nothing


def test_standing_names_are_the_ones_the_tools_report():
    assert {s.name for s in Standing} >= {"ON_SHELF", "NOT_EXPORTED", "NOT_FOUND", "RENUMBERED", "UNCHECKED"}
