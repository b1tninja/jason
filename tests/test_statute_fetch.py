"""The statutes shelf's read-through: a miss is asked of lawlibrary (a fake worker here), written in the export's format, and logged."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from jason.community.authorities import Authority, Basis
from jason.sources.lawlibrary import LawLibrary, LawLibraryUnavailable
from jason.tasks import statute_fetch
from jason.tasks.export_authorities import AUTHORITIES_DIR, MANIFEST, authority_text, export_authorities, on_demand_pages
from jason.tasks.statute_fetch import ON_DEMAND_LOG, Miss, ensure, log_rows, promotions

HEADING = "ARTICLE 3. Standards of Conduct [7230. - 7238.]"


def _section(code: str, number: str) -> dict:
    return {"citation": f"{code} {number}", "code": code, "section": number, "title": f"{number}. (Added by Stats. 2099, Ch. 1.)",
            "text": f"Made-up words of section {number}.", "path": [{"heading": "DIVISION 2. MADE-UP DIVISION [5000. - 9999.]"},
                                                                    {"heading": HEADING}], "session": "2099"}


class FakeWorker:
    """Answers spans of CORP 7230 to 7238 with made-up words; anything else is not in the library."""

    def __init__(self) -> None:
        self.calls: list[list] = []

    def __call__(self, payload: dict) -> dict:
        self.calls.append(payload["spans"])
        out = {"spans": [], "acts": {}}
        for code, start, end in payload.get("spans", []):
            numbers = [n for n in ("7231", "7233", "7234") if code == "CORP" and float(start) <= float(n) <= float(end)]
            out["spans"].append({"code": code, "start": start, "end": end, "sections": [_section(code, n) for n in numbers]})
        return out


@pytest.fixture
def fetch_on(monkeypatch):
    monkeypatch.setenv(statute_fetch.FETCH_ENV, "1")
    statute_fetch._misses.clear()
    worker = FakeWorker()
    monkeypatch.setattr(statute_fetch, "default_library", lambda: LawLibrary(Path("unused"), run=worker))
    yield worker
    statute_fetch._misses.clear()


def test_a_miss_is_fetched_written_in_the_export_format_listed_and_logged(tmp_path: Path, fetch_on):
    hit = authority_text(tmp_path, "CORP 7233", asked_by="a test")
    assert hit["found"] and hit["text"].endswith("Made-up words of section 7233.") and hit["session"] == "2099"
    assert hit["page"] == "authorities/CORP/CORP-7233.md" and hit["title"] == "Article 3. Standards of Conduct"
    text = (tmp_path / hit["page"]).read_text(encoding="utf-8")
    assert text.startswith("# CORP 7233: Article 3. Standards of Conduct")
    assert "- Source: California Legislature, 2099 session publication, read with lawlibrary" in text
    assert f"- Fetched: {date.today().isoformat()}, on demand (asked by a test); not on the curated list" in text
    assert "## CORP 7233" in text and "- Basis:" not in text
    [page] = on_demand_pages(tmp_path)
    assert page.citation == "CORP 7233" and page.sections == ["7233"] and page.asked_by == "a test"
    [row] = log_rows(tmp_path)
    assert row["code"] == "CORP" and row["section"] == "7233" and row["edition"] == "2099" and row["found"] is True
    assert row["reason"] == "" and row["asked_by"] == "a test" and row["at"]
    # The second read is from disk: the worker is not asked again.
    assert authority_text(tmp_path, "CORP 7233")["found"] and len(fetch_on.calls) == 1


def test_a_section_the_library_does_not_hold_stays_a_miss_with_its_reason_and_is_asked_once(tmp_path: Path, fetch_on):
    got = authority_text(tmp_path, "CORP 7299", asked_by="a test")
    assert not got["found"] and got["miss"] == "not_in_library" and "lawlibrary does not hold it" in got["reason"]
    assert not (tmp_path / AUTHORITIES_DIR / "CORP").exists() and on_demand_pages(tmp_path) == ()
    assert [r["reason"] for r in log_rows(tmp_path)] == ["not_in_library"]
    authority_text(tmp_path, "CORP 7299")
    assert len(fetch_on.calls) == 1 and len(log_rows(tmp_path)) == 1
    # A code lawlibrary has no shelf for is never sent to the worker.
    assert ensure(tmp_path, "XYZ", "1").miss is Miss.NOT_IN_LIBRARY and len(fetch_on.calls) == 1


def test_an_unavailable_library_and_a_failed_worker_are_told_apart(tmp_path: Path, monkeypatch, fetch_on):
    nowhere = ensure(tmp_path, "CORP", "7233", library=LawLibrary(tmp_path / "nowhere"))
    assert not nowhere.found and nowhere.miss is Miss.LIBRARY_UNAVAILABLE and "not found" in nowhere.detail

    def broken(payload):
        raise LawLibraryUnavailable("lawlibrary worker failed: Traceback")

    failed = ensure(tmp_path, "CORP", "7234", library=LawLibrary(tmp_path, run=broken))
    assert not failed.found and failed.miss is Miss.WORKER_FAILED and "worker failed" in failed.detail
    assert [r["reason"] for r in log_rows(tmp_path)] == ["library_unavailable", "worker_failed"]
    assert not (tmp_path / AUTHORITIES_DIR / "CORP").exists()


def test_the_read_through_off_reads_the_disk_only(tmp_path: Path, monkeypatch, fetch_on):
    monkeypatch.setenv(statute_fetch.FETCH_ENV, "0")
    got = authority_text(tmp_path, "CORP 7233")
    assert not got["found"] and "not in the exported" in got["reason"] and "miss" not in got
    assert fetch_on.calls == [] and not (tmp_path / AUTHORITIES_DIR / ON_DEMAND_LOG).exists()


def test_cite_tells_a_library_miss_from_a_section_not_exported(tmp_path: Path, fetch_on):
    from jason.tasks.cite import resolve

    assert resolve("CORP 7233", data_dir=tmp_path)["found"]
    assert resolve("CORP 7299", data_dir=tmp_path)["reason"] == "statute_not_in_library"
    span = resolve("CORP 7230-7238", data_dir=tmp_path)
    assert span["found"] and span["kind"] == "outline"


def test_the_export_keeps_an_uncovered_on_demand_page_lists_it_and_drops_one_a_curated_span_holds(tmp_path: Path, fetch_on):
    authority_text(tmp_path, "CORP 7233", asked_by="jason.tasks.cite")
    library = LawLibrary(tmp_path, run=fetch_on)
    narrow = (Authority("CORP", "7231", "7231", "care", Basis.GOVERNANCE),)
    report = export_authorities(library, tmp_path, spans=narrow, acts=())
    assert [p.citation for p in report.pages] == ["CORP 7231"] and [p.citation for p in report.on_demand] == ["CORP 7233"]
    manifest = json.loads((tmp_path / AUTHORITIES_DIR / MANIFEST).read_text(encoding="utf-8"))
    assert [p["citation"] for p in manifest["on_demand"]] == ["CORP 7233"] and "on_demand=1" in report.summary()
    [lead] = promotions(tmp_path, narrow)
    assert lead["citation"] == "CORP 7233" and lead["asked_by"] == ["jason.tasks.cite"] and lead["session"] == "2099"
    assert authority_text(tmp_path, "CORP 7233")["found"]

    whole = (Authority("CORP", "7230", "7238", "the article", Basis.GOVERNANCE),)
    assert promotions(tmp_path, whole) == []
    report = export_authorities(library, tmp_path, spans=whole, acts=())
    assert report.on_demand == [] and not (tmp_path / AUTHORITIES_DIR / "CORP" / "CORP-7233.md").exists()
    hit = authority_text(tmp_path, "CORP 7233")
    assert hit["found"] and hit["page"] == "authorities/CORP/CORP-7230-7238.md" and "fetched" not in hit
