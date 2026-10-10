"""The PDF splitter's sessions and apply (docs/pdf-splitter.md, sections 2, 6, and 9): open, resume, limits, the draft's acts, and
the write through the record intake's one split writer. The record-intake phase-2 world (a made-up association and data folder);
made-up PDFs; no service."""

import hashlib
import json

import pytest

from jason import limits
from jason.community import split_gold
from jason.community.split_session import SplitConflict
from jason.tasks import record_upload as up
from jason.tasks import split_session as ss

from test_record_intake_phase2 import world  # noqa: F401  (a fixture)

BY = "Jane Example"
MIN = "records/5200/minutes"


@pytest.fixture
def pdf(world):
    path = world.tmp / "numbered.pdf"
    path.write_bytes(split_gold.numbered().pdf)        # 13 pages; documents start at 1, 4, 6, 10, 11
    return path


def kw(world):
    return {"root": world.root, "community": world.community, "profile": "example"}


def open_(world, pdf, **extra):
    return ss.open_session({"kind": "path", "path": str(pdf)}, by=BY, **kw(world), **extra)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_opening_keeps_a_copy_makes_a_draft_and_suggests_with_reasons(world, pdf):
    out = open_(world, pdf)
    s = out["session"]
    assert out["ok"] and not out["resumed"] and s["status"] == "draft" and s["source"]["pages"] == 13 and s["version"] == 1
    assert [b["page"] for b in s["boundaries"]] == [1]                          # a suggestion is not a boundary
    assert [x["page"] for x in s["suggestions"]] == [4, 6, 10, 11] and all(x["why"].startswith("Page ") for x in s["suggestions"])
    assert ss.source_file(world.root, s["source"]["sha256"]).read_bytes() == pdf.read_bytes()
    assert ss.read_facts(world.root, s["source"]["sha256"])[3].label == (1, 2)
    text = json.dumps(s)
    assert "numbered.pdf" not in text and str(world.tmp) not in text                  # no name or path in the session
    again = open_(world, pdf)
    assert again["resumed"] is True and again["session"]["id"] == s["id"]
    history = (world.root / "records" / "history.jsonl").read_text(encoding="utf-8")
    assert "numbered.pdf" not in history and '"act": "split-open"' in history


def test_a_dry_run_open_keeps_nothing_and_a_file_over_the_page_limit_is_refused_in_words(world, pdf, monkeypatch):
    dry = open_(world, pdf, dry_run=True)
    assert dry["dryRun"] is True and dry["would"]["pages"] == 13 and not (world.root / "split").exists()
    big = world.tmp / "big.pdf"
    import pymupdf

    doc = pymupdf.open()
    for _ in range(51):
        doc.new_page()
    big.write_bytes(doc.tobytes())
    monkeypatch.setenv("JASON_LIMIT_SPLIT_MAX_PAGES", "50")
    with pytest.raises(limits.LimitReached, match="This file has 51 pages; the splitter opens files of up to 50"):
        open_(world, big)
    assert not (world.root / "split").exists()                                    # nothing was kept
    encrypted = world.tmp / "locked.pdf"
    doc = pymupdf.open()
    doc.new_page()
    encrypted.write_bytes(doc.tobytes(encryption=pymupdf.PDF_ENCRYPT_AES_256, user_pw="x", owner_pw="y"))
    with pytest.raises(ValueError, match="could not be read: it is protected with a password"):
        open_(world, encrypted)
    with pytest.raises(ValueError, match="Drive file is split from a copy"):
        ss.open_session({"kind": "drive", "id": "x"}, by=BY, **kw(world))
    with pytest.raises(ValueError, match="no such file"):
        ss.open_session({"kind": "path", "path": str(world.tmp / "nope.pdf")}, by=BY, **kw(world))


def test_the_acts_are_held_to_the_version_and_a_second_writer_is_told_not_overwritten(world, pdf):
    s = open_(world, pdf)["session"]
    sid = s["id"]
    a = ss.act(sid, "accept", {"id": "all"}, by=BY, version=s["version"], **kw(world))
    assert a["accepted"] == 4 and a["version"] == s["version"] + 1 and a["changed"]
    with pytest.raises(SplitConflict, match="changed since you opened") as err:
        ss.act(sid, "mark", {"pages": [8]}, by=BY, version=s["version"], **kw(world))
    assert err.value.current["version"] == a["version"] and 8 not in [b["page"] for b in err.value.current["boundaries"]]
    dry = ss.act(sid, "clear", {}, by=BY, dry_run=True, **kw(world))
    assert dry["dryRun"] and dry["session"]["counts"]["segments"] == 1
    assert ss.load(world.root, sid).top_segments().__len__() == 5               # a dry run saved nothing
    assert ss.act(sid, "undo", {}, by=BY, **kw(world))["undone"] is True
    assert ss.act(sid, "redo", {}, by=BY, **kw(world))["redone"] is True
    with pytest.raises(ValueError, match="first page always starts"):
        ss.act(sid, "unmark", {"page": 1}, by=BY, **kw(world))
    with pytest.raises(ValueError, match="a person"):
        ss.act(sid, "mark", {"page": 3}, by="jason", **kw(world))
    with pytest.raises(KeyError):
        ss.act("ffffffff", "mark", {"page": 3}, by=BY, **kw(world))


def _set(world, sid, pages, labels=()):
    ss.act(sid, "boundaries", {"pages": pages}, by=BY, **kw(world))
    for page, field, value in labels:
        ss.act(sid, "label", {"page": page, "field": field, "value": value}, by=BY, **kw(world))


def test_apply_is_a_dry_run_until_a_person_confirms_and_the_review_adds_up(world, pdf):
    sid = open_(world, pdf)["session"]["id"]
    _set(world, sid, [1, 4, 6, 10, 11], [(4, "slot", MIN), (4, "period", "2099-06")])
    dry = ss.apply(sid, by=BY, **kw(world))
    assert dry["dryRun"] is True and dry["review"]["files"] == 5 and dry["review"]["totalsOk"]
    assert [p["action"] for p in dry["review"]["parts"]] == ["held", "fill", "held", "held", "held"]
    assert dry["review"]["pagesInFiles"] == 13 and not (world.spec / "example" / "records.json").exists()
    assert ss.load(world.root, sid).status == "draft"
    still = ss.apply(sid, by=BY, confirm=False, **kw(world))                   # without confirm, still a dry run
    assert still["dryRun"] is True
    bad = ss.review(sid, drop=[2], **kw(world))
    assert bad["totalsOk"] and bad["pagesInFiles"] == 12 and bad["dropped"] == [2]
    with pytest.raises(ValueError, match="would be empty"):
        ss.review(sid, drop=[10], **kw(world))                                   # the one-page segment would have no pages
    with pytest.raises(ValueError, match="not in a file"):
        ss.review(sid, drop=[99], **kw(world))


def test_confirming_writes_through_the_intake_writer_with_provenance_and_leaves_the_original_alone(world, pdf, monkeypatch):
    from pypdf import PdfReader

    before = sha(pdf)
    sid = open_(world, pdf)["session"]["id"]
    copy = ss.source_file(world.root, ss.load(world.root, sid).source.sha256)
    _set(world, sid, [1, 4, 6, 10, 11], [(4, "slot", MIN), (4, "period", "2099-06"), (4, "title", "A guess")])
    out = ss.apply(sid, by=BY, confirm=True, **kw(world))
    assert out["ok"] and not out["dryRun"] and len(out["filled"]) == 1 and len(out["held"]) == 4 and not out["failed"]
    pin = out["filled"][0]["pin"]
    row = next(p for p in json.loads((world.spec / "example" / "records.json").read_text(encoding="utf-8"))["pins"] if p["id"] == pin)
    assert row["slot"] == MIN and row["period"] == "2099-06" and row["splitFrom"] == f"session:{sid}" and row["splitSession"] == sid
    assert row["pages"] == {"ranges": [[4, 5]], "of": 13} and row["confirmedBy"]["name"] == BY and row["segment"]["kindIsGuess"] is True
    assert len(PdfReader(str(world.root / row["ref"])).pages) == 2 and row["by"] == BY
    held = [world.root / m["ref"] for m in out["held"]]
    assert sorted(len(PdfReader(str(p)).pages) for p in held) == [1, 3, 3, 4]
    assert sum(len(PdfReader(str(p)).pages) for p in held) + 2 == 13            # every page is in a file exactly once
    assert sha(pdf) == before and sha(copy) == before                              # the original and the copy are untouched
    s = ss.load(world.root, sid)
    assert s.status == "applied" and s.confirmed["by"] == BY and s.confirmed["boundaries"] == "1,4,6,10,11"
    history = (world.root / "records" / "history.jsonl").read_text(encoding="utf-8")
    assert "numbered.pdf" not in history and "Part-" not in history and '"act": "split-apply"' in history
    with pytest.raises(ValueError, match="applied already"):
        ss.apply(sid, by=BY, confirm=True, **kw(world))
    with pytest.raises(ValueError, match="only a draft"):
        ss.act(sid, "mark", {"page": 3}, by=BY, **kw(world))
    # the slotted part is queued for a read-back in the person's name; the held ones say why not
    from jason import jobs

    assert out["autoRead"] is True and len(out["queued"]) == 1 and "--read" in jobs.get(world.root, out["queued"][0]["job"]).argv
    assert all("held" in n["why"] for n in out["notQueued"])


def test_auto_read_off_queues_nothing(world, pdf, monkeypatch):
    monkeypatch.setenv("JASON_LIMIT_SPLIT_AUTO_READ", "off")
    sid = open_(world, pdf)["session"]["id"]
    _set(world, sid, [1, 4], [(4, "slot", MIN), (4, "period", "2099-06")])
    out = ss.apply(sid, by=BY, confirm=True, **kw(world))
    assert out["autoRead"] is False and "queued" not in out and "split.auto_read" in out["reading"]


def test_the_same_boundaries_make_the_same_bytes(world, pdf):
    a = up.cut_pages(pdf, [(4, 5)])
    b = up.cut_pages(pdf, [(4, 5)])
    assert a == b
    assert up.cut_pages(pdf, [(1, 1), (3, 3)]) != a
    with pytest.raises(ValueError, match="not in a file"):
        up.cut_pages(pdf, [(10, 14)])


def test_a_collision_is_reported_not_written_and_a_duplicate_is_skipped_by_hash(world, pdf):
    first = open_(world, pdf)["session"]["id"]
    _set(world, first, [1, 4], [(4, "slot", MIN), (4, "period", "2099-06")])
    ss.apply(first, by=BY, confirm=True, **kw(world))
    # the same bytes and boundaries again: every part is already filed
    again = open_(world, pdf)["session"]["id"]
    assert again != first
    _set(world, again, [1, 4], [(4, "slot", MIN), (4, "period", "2099-06")])
    plan = ss.review(again, **kw(world))
    assert [p["action"] for p in plan["parts"]] == ["duplicate", "duplicate"] and plan["duplicates"] == ["s1", "s2"]
    out = ss.apply(again, by=BY, confirm=True, **kw(world))
    assert out["filled"] == [] and len(out["skipped"]) == 2
    pins = json.loads((world.spec / "example" / "records.json").read_text(encoding="utf-8"))["pins"]
    assert len([p for p in pins if p["slot"] == MIN]) == 1                        # nothing was written twice
    # a different part for the same slot is a collision
    other = world.tmp / "other.pdf"
    other.write_bytes(split_gold.letters(4).pdf)
    third = open_(world, other)["session"]["id"]
    _set(world, third, [1, 2], [(2, "slot", MIN), (2, "period", "2099-06")])
    plan = ss.review(third, **kw(world))
    assert [p["action"] for p in plan["parts"]] == ["held", "collision"] and plan["collisions"] == [MIN]
    done = ss.apply(third, by=BY, confirm=True, **kw(world))
    assert len(done["skipped"]) == 1 and done["skipped"][0]["action"] == "collision"
    # keeping a copy anyway is the person's choice
    kept = ss.review(again, keep_copies=True, **kw(world))
    assert "duplicate" not in [p["action"] for p in kept["parts"]]


def test_a_failure_part_way_leaves_a_retryable_state_and_deletes_nothing(world, pdf, monkeypatch):
    sid = open_(world, pdf)["session"]["id"]
    _set(world, sid, [1, 4, 6, 10, 11])
    real = up.keep_held
    calls = {"n": 0}

    def flaky(root, profile, data, name):
        calls["n"] += 1
        if calls["n"] == 3:
            raise OSError("the disk went away")
        return real(root, profile, data, name)

    monkeypatch.setattr(up, "keep_held", flaky)
    out = ss.apply(sid, by=BY, confirm=True, **kw(world))
    assert out["ok"] is False and out["failed"][0]["segment"] == "s3" and len(out["held"]) == 2
    s = ss.load(world.root, sid)
    assert s.status == "confirmed" and s.applied["partial"] is True
    monkeypatch.setattr(up, "keep_held", real)
    again = ss.apply(sid, by=BY, confirm=True, **kw(world))
    assert again["ok"] and len(again["held"]) == 5 and ss.load(world.root, sid).status == "applied"
    kept = list((world.root / "record-intake" / "example" / "files").glob("*/*.pdf"))
    assert len(kept) == 5                                                           # the first two were not written again


def test_a_source_that_changed_under_the_draft_is_refused(world, pdf):
    sid = open_(world, pdf)["session"]["id"]
    _set(world, sid, [1, 4])
    copy = ss.source_file(world.root, ss.load(world.root, sid).source.sha256)
    copy.write_bytes(copy.read_bytes() + b"\n%tampered")
    with pytest.raises(ValueError, match="copy of the file changed"):
        ss.apply(sid, by=BY, confirm=True, **kw(world))
    assert ss.load(world.root, sid).status == "stale"


def test_a_library_file_that_changed_makes_the_draft_stale(world):
    import sqlite3

    root = world.root
    (root / "library" / "files").mkdir(parents=True, exist_ok=True)
    path = root / "library" / "files" / "Doc.pdf"
    path.write_bytes(split_gold.numbered().pdf)
    with sqlite3.connect(root / "library" / "library.db") as conn:
        conn.execute("INSERT INTO documents (id, source, path, name, kind, category, records, method, period, confidential, evidence, sha256)"
                     " VALUES ('7001','payhoa','Doc.pdf','Doc.pdf','minutes','board','enhanced','NAME','2099-06',0,'','')")
    s = ss.open_session({"kind": "library", "id": "7001"}, by=BY, **kw(world))["session"]
    assert s["source"]["kind"] == "library" and s["source"]["ref"] == "7001"
    path.write_bytes(split_gold.letters(3).pdf)
    with pytest.raises(ValueError, match="changed after you started"):
        ss.act(s["id"], "mark", {"page": 3}, by=BY, **kw(world))
    assert ss.load(root, s["id"]).status == "stale" and "kept here" in ss.load(root, s["id"]).notes[-1]


def test_the_parts_limit_and_the_suggestions_switch_speak_in_the_registrys_words(world, pdf, monkeypatch):
    monkeypatch.setenv("JASON_LIMIT_SPLIT_MAX_PARTS", "2")
    sid = open_(world, pdf)["session"]["id"]
    _set(world, sid, [1, 4, 6])
    with pytest.raises(limits.LimitReached, match="would write 3 files; one split writes at most 2"):
        ss.review(sid, **kw(world))
    monkeypatch.setenv("JASON_LIMIT_SPLIT_SUGGEST_ENABLED", "off")
    with pytest.raises(limits.LimitReached, match="Suggestions are off for this community. You can still mark each first page yourself."):
        ss.suggest(sid, by=BY, **kw(world))
    off = world.tmp / "off.pdf"
    off.write_bytes(split_gold.letters(3).pdf)
    s = open_(world, off)["session"]
    assert s["suggestions"] == []                                                   # none made on opening
    assert ss.act(s["id"], "mark", {"pages": [2]}, by=BY, **kw(world))["changed"]  # the editor still works


def test_decline_records_a_persons_wish_and_changes_no_file(world, pdf):
    sid = open_(world, pdf)["session"]["id"]
    assert ss.decline(sid, by=BY, **kw(world))["dryRun"] is True
    assert ss.load(world.root, sid).status == "draft"
    assert ss.decline(sid, by=BY, dry_run=False, **kw(world))["declined"] is True
    assert ss.load(world.root, sid).status == "declined"
    assert not (world.root / "record-intake").exists()
    reopened = open_(world, pdf)
    assert reopened["resumed"] is False                                              # a declined draft is not resumed


def test_purge_and_the_sweep_remove_drafts_with_their_copy_and_pictures_but_never_an_original(world, pdf):
    from datetime import datetime, timedelta, timezone

    from jason.tasks import split_thumbs as th

    sid = open_(world, pdf)["session"]["id"]
    sha_ = ss.load(world.root, sid).source.sha256
    th.get(world.root, ss.source_file(world.root, sha_), sha_, 1, 96)
    assert ss.purge(sid=sid, root=world.root)["dryRun"] is True and ss.session_file(world.root, sid).is_file()
    with pytest.raises(ValueError, match="names who made it"):
        ss.purge(sid=sid, dry_run=False, by="", root=world.root)
    out = ss.purge(sid=sid, dry_run=False, by=BY, root=world.root, community=world.community)
    assert out["removed"] == [sid] and out["freed"] > 0
    assert not ss.session_file(world.root, sid).exists() and not ss.source_file(world.root, sha_).exists()
    assert not th.folder_of(world.root, sha_).exists() and pdf.is_file()
    # the retention sweep: sixty days after the last change
    sid2 = open_(world, pdf)["session"]["id"]
    assert ss.sweep(dry_run=False, root=world.root, community=world.community)["removed"] == []
    later = datetime.now(timezone.utc) + timedelta(days=61)
    assert ss.sweep(root=world.root, community=world.community, today=later)["would"]["sessions"] == [sid2]
    assert ss.sweep(dry_run=False, root=world.root, community=world.community, today=later)["removed"] == [sid2]
    assert ss.listing(world.root) == []
    # an applied split's record stays
    sid3 = open_(world, pdf)["session"]["id"]
    _set(world, sid3, [1, 4])
    ss.apply(sid3, by=BY, confirm=True, **kw(world))
    ss.sweep(dry_run=False, root=world.root, community=world.community, today=later)
    assert ss.session_file(world.root, sid3).is_file() and ss.load(world.root, sid3).status == "applied"


def test_a_long_file_leaves_its_facts_to_a_job_and_the_job_fills_them_in(world, monkeypatch):
    import pymupdf

    doc = pymupdf.open()
    for i in range(ss.INLINE_PAGES + 2):
        page = doc.new_page()
        page.insert_text((72, 100), f"Page {i + 1} of {ss.INLINE_PAGES + 2}")
    big = world.tmp / "long.pdf"
    big.write_bytes(doc.tobytes())
    out = ss.open_session({"kind": "path", "path": str(big)}, by=BY, **kw(world))
    assert out["factsPending"] is True and ss.facts_view(world.root, out["session"]["id"], 1, 3)["facts"][0]["pending"] is True
    job = ss.queue_facts(world.root, out["session"]["id"], BY)
    from jason import jobs

    queued = jobs.get(world.root, job["job"])
    assert queued.argv[:2] == ["split", out["session"]["id"]] and queued.job_class.value == "local"
    done = ss.build_facts(out["session"]["id"], by=BY, **kw(world))
    assert done["pages"] == ss.INLINE_PAGES + 2
    view = ss.facts_view(world.root, out["session"]["id"], 1, 2, lqip=False)
    assert view["ready"] == ss.INLINE_PAGES + 2 and view["facts"][0]["pending"] is False and "lqip" not in view["facts"][0]
    assert len(ss.read_facts(world.root, out["session"]["source"]["sha256"])[0].lqip) == 512
