"""OCR of the parts a split files to the library, as background jobs (docs/pdf-splitter.md 9.5, docs/record-intake.md Phase 4).
Fakes only: no OCR engine, no GPU, no Tesseract."""

import json
import sqlite3
from types import SimpleNamespace

import pytest

from jason import jobs, limits
from jason.tasks import library as lib
from jason.tasks import library_ocr
from jason.tasks import split_session as ss

from test_split_filing import BY, build, kw, open_, set_
from test_record_intake_phase2 import world  # noqa: F401  (a fixture)

LONG = "word " * 100            # 500 characters: a text layer


def _library(world, docs):
    """``docs``: id -> (sha, cached text, note source). A file is written for each."""
    db = world.root / "library" / "library.db"
    db.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db) as conn:
        conn.execute(lib.SCHEMA)
        for doc_id, (sha, text, source) in docs.items():
            conn.execute("INSERT INTO documents (id, path, sha256) VALUES (?,?,?)", (doc_id, f"x/{doc_id}.pdf", sha))
            f = world.root / "library" / "files" / "x" / f"{doc_id}.pdf"
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_bytes(b"%PDF-1.4 fake")
            t = world.root / lib.TEXT_DIR
            t.mkdir(parents=True, exist_ok=True)
            (t / f"{doc_id}.txt").write_text(text, encoding="utf-8")
            (t / f"{doc_id}.json").write_text(json.dumps({"source": source, "sha256": sha}), encoding="utf-8")


def _split(world, n, name):
    path = build(world, name, [("up", i + 1) for i in range(n)])
    sid = open_(world, path)["id"]
    set_(world, sid, list(range(1, n + 1)))
    return sid


def _intake(ids):
    def intake(root, community, files, by):
        return {label: {"filed": True, "id": ids[i], "kind": "minutes"} for i, (label, _d) in enumerate(files)}
    return intake


def _ocr_jobs(world):
    return [j for j in jobs.jobs(world.root, limit=100) if j.argv[:2] == ["library", "--ocr-doc"]]


def test_the_limit_is_registered_with_its_words():
    l = limits.limit("split.ocr_queue_max")
    assert (l.default, l.minimum, l.maximum, l.unit) == (25, 1, 200, "count")
    assert l.why and l.when_hit


def test_a_library_filing_queues_one_local_job_per_scan_in_the_persons_name_and_skips_the_rest(world):
    _library(world, {"d1": ("h1", "", "image-only; OCR skipped (--no-ocr)"), "d2": ("h2", LONG, "text layer"),
                     "d3": ("h3", "", "ocr: tesseract-cli")})
    sid = _split(world, 3, "o1.pdf")
    out = ss.apply(sid, by=BY, confirm=True, filing="library", library_filer=_intake(["d1", "d2", "d3"]), **kw(world))
    assert out["ok"] and out["ocr"] is True
    assert [q["libraryId"] for q in out["ocrQueued"]] == ["d1"]
    assert {s["libraryId"]: s["why"] for s in out["ocrSkipped"]} == {"d2": "has a text layer", "d3": "already read by OCR (same file hash)"}
    [job] = _ocr_jobs(world)
    assert job.job_class is jobs.JobClass.LOCAL and job.confirmed_by == BY and job.writes
    assert job.argv == ["library", "--ocr-doc", "d1", "--yes", "--by", BY]
    text = (world.root / "records" / "history.jsonl").read_text(encoding="utf-8")
    assert '"ocrQueued": 1' in text and "o1.pdf" not in text
    again = library_ocr.queue(world.root, ["d1"], BY, community=world.community)          # the same ids again queue nothing twice
    assert again["ocrQueued"] == [] and again["ocrSkipped"][0]["why"] == "an OCR job is already queued for it"
    assert len(_ocr_jobs(world)) == 1


def test_no_ocr_opts_out_and_names_why(world):
    _library(world, {"d1": ("h1", "", "x")})
    sid = _split(world, 1, "o2.pdf")
    out = ss.apply(sid, by=BY, confirm=True, filing="library", library_filer=_intake(["d1"]), ocr=False, **kw(world))
    assert out["ocr"] is False and out["ocrQueued"] == [] and _ocr_jobs(world) == []
    assert "--no-ocr" in out["notQueued"][0]["why"]


def test_held_parts_queue_no_ocr(world):
    sid = _split(world, 2, "o3.pdf")
    out = ss.apply(sid, by=BY, confirm=True, filing="held", **kw(world))
    assert out["ocrQueued"] == [] and _ocr_jobs(world) == []


def test_the_limit_caps_one_apply_and_the_rest_are_named_not_queued(world, monkeypatch):
    monkeypatch.setenv("JASON_LIMIT_SPLIT_OCR_QUEUE_MAX", "1")
    _library(world, {"d1": ("h1", "", "x"), "d2": ("h2", "", "x")})
    sid = _split(world, 2, "o4.pdf")
    out = ss.apply(sid, by=BY, confirm=True, filing="library", library_filer=_intake(["d1", "d2"]), **kw(world))
    assert [q["libraryId"] for q in out["ocrQueued"]] == ["d1"]
    assert [n["libraryId"] for n in out["notQueued"]] == ["d2"] and "at most 1" in out["notQueued"][0]["why"]


def test_a_dry_run_shows_how_many_jobs_would_queue_and_queues_none(world):
    sid = _split(world, 3, "o5.pdf")
    dry = ss.apply(sid, by=BY, filing="library", **kw(world))
    assert dry["dryRun"] and dry["would"]["ocr"]["jobsAtMost"] == 3 and dry["would"]["ocr"]["notQueuedAtMost"] == 0
    assert _ocr_jobs(world) == []
    off = ss.apply(sid, by=BY, filing="library", ocr=False, **kw(world))
    assert "ocr" not in off["would"]


class _Engine:
    name = "fake-ocr"

    def __init__(self, text):
        self.text, self.calls = text, 0

    def text_of(self, path):
        self.calls += 1
        return self.text


def test_the_job_keeps_the_words_beside_the_cache_and_is_idempotent_by_hash(world):
    _library(world, {"d1": ("h1", "", "image-only; OCR skipped (--no-ocr)")})
    engine = _Engine("hello " * 80)
    res = library_ocr.run(world.root, "d1", BY, engines=[engine])
    assert res["read"] and res["engine"] == "fake-ocr" and "x/d1" not in json.dumps(res)
    assert lib.text_for(world.root, "d1").startswith("hello")
    note = json.loads((world.root / lib.TEXT_DIR / "d1.json").read_text(encoding="utf-8"))
    assert note["source"] == "ocr: fake-ocr" and note["sha256"] == "h1" and note["ocrBy"] == BY
    again = library_ocr.run(world.root, "d1", BY, engines=[engine])
    assert again["read"] is False and "already read" in again["why"] and engine.calls == 1


def test_the_job_fails_fast_with_no_engine_and_reads_nothing(world, monkeypatch):
    _library(world, {"d1": ("h1", "", "x")})
    from jason.community import ocr

    monkeypatch.setattr(ocr, "local_engines", lambda: ())
    with pytest.raises(RuntimeError, match="no OCR engine"):
        library_ocr.run(world.root, "d1", BY)
    assert lib.text_for(world.root, "d1") == ""


def test_the_command_needs_a_person_and_reports_in_ids_only(world, monkeypatch, capsys):
    import jason.cli as cli

    monkeypatch.setattr("jason.mcp.county._data_dir", lambda _x: world.root)
    monkeypatch.setattr(library_ocr, "run", lambda root, doc, by, **k: {"libraryId": doc, "read": True, "engine": "fake-ocr", "chars": 9})
    assert cli.cmd_library(SimpleNamespace(ocr_doc="d1", yes=False, by="")) == 2
    ns = SimpleNamespace(ocr_doc="d1", yes=True, by=BY)
    assert cli.cmd_library(ns) == 0 and "ocr d1: read 9 chars with fake-ocr" in capsys.readouterr().out
    monkeypatch.setattr(library_ocr, "run", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("no OCR engine runs on this machine")))
    assert cli.cmd_library(ns) == 1
