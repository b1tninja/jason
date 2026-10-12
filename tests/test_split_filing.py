"""The splitter's backend gaps B3 to B6 (docs/pdf-splitter.md, "Filing, rotation, and the flags"): the measured direction of a page's text, the
per-segment flags before the review, turning pages in the new files only, and the filing choice on the apply (held, library, slots). The
record-intake phase-2 world; made-up PDFs; the library intake is a fake. No service."""

import base64
import dataclasses
import json

import pytest

import webclient
from jason.community import split_gold
from jason.tasks import record_upload as up
from jason.tasks import split_flags
from jason.tasks import split_session as ss

from test_record_intake_phase2 import world  # noqa: F401  (a fixture)
from test_split_surfaces import _signed  # noqa: F401

BY = "A Manager"
MIN = "records/5200/minutes"


def kw(world):
    return {"root": world.root, "community": world.community, "profile": "example"}


def build(world, name, pages):
    """A PDF from page specs: ``("up", seed)`` upright text, ``("side", seed)`` text running up the page, ``("turned", seed)`` upright text on a
    page the PDF rotates 90 degrees (so it is shown sideways), ``("blank",)``."""
    import pymupdf

    doc = pymupdf.open()
    for spec in pages:
        page = doc.new_page(width=612, height=792)
        if spec[0] in ("up", "turned"):
            y = 150.0
            for text in split_gold.para(spec[1]):
                page.insert_text((72, y), text, fontsize=10)
                y += 14
            if spec[0] == "turned":
                page.set_rotation(90)
        elif spec[0] == "side":
            for i, text in enumerate(split_gold.para(spec[1])):
                page.insert_text((100 + i * 14, 700), text, fontsize=10, rotate=90)
    path = world.tmp / name
    path.write_bytes(doc.tobytes())
    return path


def open_(world, path):
    return ss.open_session({"kind": "path", "path": str(path)}, by=BY, **kw(world))["session"]


def set_(world, sid, pages, labels=()):
    ss.act(sid, "boundaries", {"pages": pages}, by=BY, **kw(world))
    for page, field, value in labels:
        ss.act(sid, "label", {"page": page, "field": field, "value": value}, by=BY, **kw(world))


# --- B6: the direction of a page's text is measured, not guessed ---------------------------------------------------------------------

def test_a_pages_text_direction_is_measured_through_the_pdfs_rotation(world):
    path = build(world, "dir.pdf", [("up", 1), ("side", 2), ("turned", 3), ("blank",)])
    facts = ss.read_facts(world.root, open_(world, path)["source"]["sha256"])
    assert [f.turn for f in facts] == [0, 270, 90, -1]
    assert [f.sideways for f in facts] == [False, True, True, False] and [f.fix for f in facts] == [0, 90, 270, 0]
    assert [f.orientation for f in facts] == ["portrait", "portrait", "landscape", "portrait"]     # the rotation turned the third page's frame
    assert facts[2].rotation == 90 and facts[2].to_dict()["sideways"] is True and facts[0].to_dict()["fix"] == 0


def test_a_page_with_no_text_layer_is_never_called_sideways(world):
    scan = world.tmp / "scan.pdf"
    scan.write_bytes(split_gold.strip_text(build(world, "t.pdf", [("up", 1), ("side", 2)]).read_bytes()))
    facts = ss.read_facts(world.root, open_(world, scan)["source"]["sha256"])
    assert [f.turn for f in facts] == [-1, -1] and not any(f.sideways for f in facts)


def test_facts_made_before_the_direction_was_measured_are_measured_again(world):
    path = build(world, "old.pdf", [("up", 1), ("side", 2)])
    sha = open_(world, path)["source"]["sha256"]
    old = json.loads(ss.facts_file(world.root, sha).read_text(encoding="utf-8"))
    old["version"] = 1
    for page in old["pages"]:
        page.pop("turn", None)
    ss.facts_file(world.root, sha).write_text(json.dumps(old), encoding="utf-8")
    assert ss.read_facts(world.root, sha)[1].turn == -1
    assert ss.ensure_facts(world.root, sha)[1].turn == 270
    assert json.loads(ss.facts_file(world.root, sha).read_text(encoding="utf-8"))["version"] == ss.FACTS_VERSION


def test_pages_are_turned_in_the_new_files_only_and_the_original_is_untouched(world):
    from pypdf import PdfReader

    path = build(world, "turn.pdf", [("up", 1), ("side", 2), ("turned", 3), ("up", 4)])
    before = path.read_bytes()
    sid = open_(world, path)["id"]
    set_(world, sid, [1, 3])
    plan = ss.review(sid, rotate="sideways", **kw(world))
    assert plan["rotated"] == [{"page": 2, "degrees": 90}, {"page": 3, "degrees": 270}] and plan["sidewaysLeft"] == 0
    assert [r["rotated"] for r in plan["parts"]] == [[{"page": 2, "degrees": 90}], [{"page": 3, "degrees": 270}]]
    plain = ss.review(sid, **kw(world))
    assert plain["rotated"] == [] and plain["sidewaysLeft"] == 2 and [x["page"] for x in plain["parts"][0]["sideways"]] == [2]
    assert plan["parts"][0]["sha256"] != plain["parts"][0]["sha256"]                    # the turned file is different bytes
    out = ss.apply(sid, by=BY, confirm=True, rotate={"2": "fix", 3: 270}, **kw(world))
    assert out["ok"] and out["rotated"] == [{"page": 2, "degrees": 90}, {"page": 3, "degrees": 270}]
    first = PdfReader(str(world.root / out["held"][0]["ref"]))
    assert [p.rotation for p in first.pages] == [0, 90]
    assert [p.rotation for p in PdfReader(str(world.root / out["held"][1]["ref"])).pages] == [0, 0]       # the page the PDF itself turned 90, then 270 more: upright
    assert path.read_bytes() == before                                                   # the original is never changed
    text = (world.root / "records" / "history.jsonl").read_text(encoding="utf-8")
    assert '"rotatedPages": 2' in text and "turn.pdf" not in text


def test_a_turn_is_refused_in_words_when_nothing_measured_it(world):
    path = build(world, "r.pdf", [("up", 1), ("up", 2)])
    sid = open_(world, path)["id"]
    with pytest.raises(ValueError, match="measured no sideways text"):
        ss.review(sid, rotate={"2": "fix"}, **kw(world))
    with pytest.raises(ValueError, match="90, 180, or 270"):
        ss.review(sid, rotate={"2": 45}, **kw(world))
    with pytest.raises(ValueError, match="not in a file"):
        ss.review(sid, rotate={"9": 90}, **kw(world))
    assert ss.review(sid, rotate={"2": 180}, **kw(world))["rotated"] == [{"page": 2, "degrees": 180}]
    assert ss.review(sid, rotate={"2": 180}, drop=[2], **kw(world))["rotated"] == []        # a page left out is not turned
    with pytest.raises(ValueError, match="90, 180, or 270"):
        up.cut_pages(path, [(1, 2)], {1: 45})


# --- B3 and B4: the flags before the review --------------------------------------------------------------------------------------------

def test_flags_name_blank_only_repeats_sideways_pages_and_a_part_that_may_hold_more(world):
    path = build(world, "flags.pdf", [("up", 1), ("up", 2), ("up", 1), ("up", 2), ("blank",), ("side", 5)])
    sid = open_(world, path)["id"]
    set_(world, sid, [1, 3, 5, 6])
    out = split_flags.flags(sid, **kw(world))
    by = {r["segment"]: r for r in out["segments"]}
    assert by["s2"]["nearDuplicateOf"] == "s1" and by["s1"]["repeatedBy"] == ["s2"] and by["s1"]["nearDuplicateOf"] is None
    assert by["s3"]["blankOnly"] is True and by["s1"]["blankOnly"] is False
    assert by["s4"]["sideways"] == [{"page": 6, "turn": 270, "fix": 90}] and by["s4"]["flagged"]
    assert out["counts"] == {"blankOnly": 1, "nearDuplicate": 1, "sideways": 1, "overPartLimit": 0, "mayHoldMore": 0, "slotFilled": 0}
    assert out["measured"] == {"pages": 6, "of": 6, "complete": True} and out["parts"]["over"] is False
    text = json.dumps(out)
    assert "flags.pdf" not in text and "t:" not in text and "i:" not in text            # no name and no page hash in the answer


def test_a_picture_scanned_twice_is_a_near_duplicate_by_its_page_hash(world):
    scan = world.tmp / "twice.pdf"
    scan.write_bytes(split_gold.mixed_dpi().pdf)
    sha = open_(world, scan)["source"]["sha256"]
    assert split_flags.same_page("i:" + "0" * 64, "i:" + "0" * 63 + "f") and not split_flags.same_page("i:" + "0" * 64, "i:" + "f" * 64)
    assert not split_flags.same_page("t:ab", "i:ab") and not split_flags.same_page("", "t:ab") and split_flags.same_page("t:ab", "t:ab")
    assert all(f.phash.startswith("i:") for f in ss.read_facts(world.root, sha) if f.blank != "blank")


def test_a_segment_that_spans_a_likely_start_may_hold_more_than_one_document_unless_a_person_said_no(world):
    path = world.tmp / "numbered.pdf"
    path.write_bytes(split_gold.numbered().pdf)                                             # documents start at 1, 4, 6, 10, 11
    s = open_(world, path)
    sid = s["id"]
    out = split_flags.flags(sid, **kw(world))
    row = out["segments"][0]
    assert [m["page"] for m in row["mayHoldMore"]] == sorted((m["page"] for m in row["mayHoldMore"]), key=lambda p: -next(
        m["score"] for m in row["mayHoldMore"] if m["page"] == p)) and {4, 6}.issubset({m["page"] for m in row["mayHoldMore"]})
    ss.act(sid, "reject", {"id": "g4"}, by=BY, **kw(world))
    after = split_flags.flags(sid, **kw(world))["segments"][0]
    assert 4 not in [m["page"] for m in after["mayHoldMore"]] and 6 in [m["page"] for m in after["mayHoldMore"]]
    set_(world, sid, [1, 4, 6, 10, 11])
    assert split_flags.flags(sid, **kw(world))["counts"]["mayHoldMore"] == 0                  # every start is marked: nothing spans one


def test_a_part_over_the_upload_limit_and_too_many_parts_are_flagged(world, monkeypatch):
    path = build(world, "big.pdf", [("up", 1), ("up", 2), ("up", 3), ("up", 4)])
    sid = open_(world, path)["id"]
    set_(world, sid, [1, 3])
    monkeypatch.setenv("JASON_LIMIT_SPLIT_MAX_PARTS", "2")
    session = ss.load(world.root, sid)
    session.source = dataclasses.replace(session.source, size=6 * 1024 * 1024)
    ss.save(world.root, session)
    monkeypatch.setenv("JASON_LIMIT_UPLOAD_MAX_BYTES", str(1024 * 1024))
    out = split_flags.flags(sid, **kw(world))
    assert [r["overPartLimit"] for r in out["segments"]] == [True, True] and out["segments"][0]["estimatedBytes"] == 3 * 1024 * 1024
    assert out["counts"]["overPartLimit"] == 2 and out["parts"] == {"count": 2, "limit": 2, "over": False}
    assert split_flags.CAVEATS[1].startswith("Over the limit is an estimate")


def test_a_segment_for_a_slot_that_already_holds_a_file_is_flagged(world):
    path = build(world, "slot.pdf", [("up", 1), ("up", 2)])
    other = world.tmp / "o.pdf"
    other.write_bytes(path.read_bytes())
    sid = open_(world, path)["id"]
    set_(world, sid, [1, 2], [(2, "slot", MIN), (2, "period", "2099-06")])
    assert split_flags.flags(sid, **kw(world))["counts"]["slotFilled"] == 0
    from test_record_intake_phase2 import FILE_A

    from jason.tasks import record_slots as rs

    rs.pick(MIN, FILE_A, period="2099-06", by=BY, dry_run=False, community=world.community, root=world.root, profile="example")
    flagged = split_flags.flags(sid, **kw(world))
    assert flagged["counts"]["slotFilled"] == 1 and flagged["segments"][1]["slotFilled"] is True
    assert ss.review(sid, **kw(world))["parts"][1]["action"] == "collision"                 # the review says the same, with the cut bytes


def test_the_review_carries_each_parts_flags_and_the_flags_cut_nothing(world, monkeypatch):
    path = build(world, "rf.pdf", [("up", 1), ("up", 1), ("blank",)])
    sid = open_(world, path)["id"]
    set_(world, sid, [1, 2, 3])

    def boom(*a, **k):
        raise AssertionError("the flags cut a part")

    monkeypatch.setattr(up, "cut_pages", boom)
    split_flags.flags(sid, **kw(world))
    monkeypatch.undo()
    parts = ss.review(sid, **kw(world))["parts"]
    assert parts[1]["flags"] == {"nearDuplicateOf": "s1"} and parts[2]["flags"] == {"blankOnly": True} and parts[0]["flags"] == {"repeatedBy": ["s2"]}


# --- B5: the filing choice on the apply ------------------------------------------------------------------------------------------------

def test_filing_held_keeps_every_part_in_the_store_even_one_with_a_slot(world):
    path = build(world, "f1.pdf", [("up", 1), ("up", 2), ("up", 3)])
    sid = open_(world, path)["id"]
    set_(world, sid, [1, 2], [(2, "slot", MIN), (2, "period", "2099-06")])
    default = ss.review(sid, **kw(world))
    assert [p["action"] for p in default["parts"]] == ["held", "fill"] and default["filing"]["asked"] == "as labelled"
    held = ss.review(sid, filing="held", **kw(world))
    assert [p["action"] for p in held["parts"]] == ["held", "held"] and held["filing"]["held"] == 2 and held["filing"]["slots"] == 0
    out = ss.apply(sid, by=BY, confirm=True, filing="held", **kw(world))
    assert len(out["held"]) == 2 and out["filled"] == [] and out["library"] == []
    assert not (world.spec / "example" / "records.json").exists() or not json.loads(
        (world.spec / "example" / "records.json").read_text(encoding="utf-8"))["pins"]
    assert '"filing": "held"' in (world.root / "records" / "history.jsonl").read_text(encoding="utf-8")


def test_filing_slots_fills_the_named_slot_through_the_intake_writer_and_a_part_can_choose_its_own(world):
    path = build(world, "f2.pdf", [("up", 1), ("up", 2), ("up", 3)])
    sid = open_(world, path)["id"]
    set_(world, sid, [1, 2, 3], [(2, "slot", MIN), (2, "period", "2099-06"), (3, "slot", MIN), (3, "period", "2099-07")])
    plan = ss.review(sid, filing="slots", parts=["s3=held"], **kw(world))
    assert [p["action"] for p in plan["parts"]] == ["held", "fill", "held"] and plan["filing"]["slots"] == 1
    out = ss.apply(sid, by=BY, confirm=True, filing="slots", parts=["s3=held"], **kw(world))
    assert len(out["filled"]) == 1 and len(out["held"]) == 2
    with pytest.raises(ValueError, match="names none"):
        ss.review(sid, parts=[{"segment": "s1", "filing": "slot"}], **kw(world))
    with pytest.raises(ValueError, match="filing is one of"):
        ss.review(sid, filing="drive", **kw(world))


def test_filing_library_gives_the_parts_to_the_library_intake_and_holds_what_it_cannot_file(world):
    path = build(world, "f3.pdf", [("up", 1), ("up", 2), ("up", 3)])
    sid = open_(world, path)["id"]
    set_(world, sid, [1, 2, 3])
    seen = {}

    def intake(root, community, files, by):
        seen["labels"] = [label for label, _data in files]
        seen["by"] = by
        return {files[0][0]: {"filed": True, "id": "ingest-abc", "kind": "minutes"},
                files[1][0]: {"filed": False, "why": "held: no kind"}}

    plan = ss.review(sid, filing="library", **kw(world))
    assert [p["action"] for p in plan["parts"]] == ["library"] * 3 and plan["library"] == ["s1", "s2", "s3"]
    dry = ss.apply(sid, by=BY, filing="library", library_filer=intake, **kw(world))
    assert dry["dryRun"] is True and "labels" not in seen                                  # a dry run asks the library nothing
    out = ss.apply(sid, by=BY, confirm=True, filing="library", library_filer=intake, **kw(world))
    assert out["ok"] and [m["libraryId"] for m in out["library"]] == ["ingest-abc"] and out["library"][0]["kind"] == "minutes"
    reasons = {m["segment"]: m["why"] for m in out["held"]}
    assert reasons["s2"] == "not taken in by the library: held: no kind" and "no answer" in reasons["s3"]
    assert seen["by"] == BY and all(label.startswith("Part-") for label in seen["labels"]) and "f3.pdf" not in " ".join(seen["labels"])
    assert ss.load(world.root, sid).status == "applied"
    text = (world.root / "records" / "history.jsonl").read_text(encoding="utf-8")
    assert '"library": 1' in text and "f3.pdf" not in text and "ingest-abc" not in text


def test_the_library_intake_failing_holds_every_part_with_the_reason_type_only(world, monkeypatch):
    path = build(world, "f4.pdf", [("up", 1), ("up", 2)])
    sid = open_(world, path)["id"]
    set_(world, sid, [1, 2])
    from jason.tasks import ingest

    def broken(*a, **k):
        raise RuntimeError("secret text")

    monkeypatch.setattr(ingest, "run", broken)
    out = ss.apply(sid, by=BY, confirm=True, filing="library", **kw(world))
    assert out["library"] == [] and len(out["held"]) == 2
    assert all("could not run (RuntimeError)" in m["why"] and "secret" not in m["why"] for m in out["held"])


def test_the_default_library_intake_runs_over_staged_copies_and_files_what_it_can(world, monkeypatch):
    from types import SimpleNamespace

    from jason.tasks import ingest

    path = build(world, "f5.pdf", [("up", 1), ("up", 2)])
    sid = open_(world, path)["id"]
    set_(world, sid, [1, 2])
    asked = {}

    def fake_run(community, data_dir, sources, **options):
        import pathlib

        asked.update(options)
        names = sorted(p.name for p in pathlib.Path(sources[0]).iterdir())
        asked["names"] = names
        items = [SimpleNamespace(local=pathlib.Path(sources[0]) / names[0], filed=True, library_doc_id="ingest-1", kind="minutes",
                                 status="filed", library_path=""),
                 SimpleNamespace(local=pathlib.Path(sources[0]) / names[1], filed=False, library_doc_id="ingest-2", kind="",
                                 status="held: no kind", library_path="")]
        return SimpleNamespace(items=items)

    monkeypatch.setattr(ingest, "run", fake_run)
    out = ss.apply(sid, by=BY, confirm=True, filing="library", **kw(world))
    assert asked["apply_files"] is True and asked["ocr"] is False and len(asked["names"]) == 2
    assert len(out["library"]) == 1 and out["held"][0]["why"] == "not taken in by the library: held: no kind"


# --- the console and the command --------------------------------------------------------------------------------------------------------

def test_the_console_serves_the_flags_and_takes_filing_and_rotate_on_the_apply(world, monkeypatch):
    c = _signed(world, monkeypatch)
    path = build(world, "web.pdf", [("up", 1), ("side", 2), ("up", 3)])
    body = {"act": "open", "by": BY, "ref": {"kind": "upload", "name": "scan.pdf", "base64": base64.b64encode(path.read_bytes()).decode()}}
    sid = c.post("/api/write/split/new", json=body).json["session"]["id"]
    url = f"/api/write/split/{sid}"
    c.post(url, json={"act": "boundaries", "boundaries": [[1, 0], [2, 0], [3, 0]], "by": BY})
    got = c.get(f"/api/split-session?id={sid}&flags=1&facts=1-3")
    assert got.status_code == 200 and got.json["flags"]["segments"][1]["sideways"] == [{"page": 2, "turn": 270, "fix": 90}]
    assert [f["sideways"] for f in got.json["facts"]] == [False, True, False] and got.json["facts"][1]["fix"] == 90
    assert "flags" not in c.get(f"/api/split-session?id={sid}").json
    shown = c.post(url, json={"act": "apply", "by": BY, "filing": "held", "rotate": "sideways"})
    assert shown.json["dryRun"] is True and shown.json["review"]["rotated"] == [{"page": 2, "degrees": 90}]
    assert shown.json["review"]["filing"]["asked"] == "held"
    assert c.post(url, json={"act": "review", "by": BY, "filing": "drive"}).status_code == 400
    assert c.get(f"/api/split-session?id={sid}&flags=1&view=owner").status_code == 403
    same = {"act": "apply", "by": BY, "filing": "held", "rotate": {"2": "fix"}}
    fingerprint = c.post(url, json=same).json["planFingerprint"]
    done = c.post(url, json={**same, "dryRun": False, "confirm": True, "expect": fingerprint})
    assert done.status_code == 200 and done.json["rotated"] == [{"page": 2, "degrees": 90}] and len(done.json["held"]) == 3


def test_the_command_prints_the_flags_and_takes_filing_and_rotate(world, monkeypatch, capsys):
    from test_split_surfaces import _cli

    path = build(world, "cmd.pdf", [("up", 1), ("side", 2), ("up", 3)])
    sid = open_(world, path)["id"]
    set_(world, sid, [1, 2, 3])
    assert _cli(world, monkeypatch, sid, "--flags") == 0
    out = capsys.readouterr().out
    assert "1 sideways pages" in out and "sideways: 2 (turn 90)" in out
    assert _cli(world, monkeypatch, sid, "--review", "--rotate", "2=fix", "--filing", "held") == 0
    out = capsys.readouterr().out
    assert "turn 2 by 90" in out and "(held, no slot yet)" in out
    assert _cli(world, monkeypatch, sid, "--apply", "--yes", "--by", BY, "--rotate", "sideways", "--filing", "held") == 0
    assert "turned 1 pages" in capsys.readouterr().out
