"""Record intake, phase 3 backend: upload from the computer, the confirmed split, what reads a slot, and acknowledging a change.

Fakes only (the phase-2 world: a fake Drive that refuses writes, a made-up association, made-up PDFs, a data folder of its own).
Nothing here reaches Google, Keeper, PayHOA, or a county."""

import base64
import io
import json

import pytest

import webclient
from jason.tasks import record_readback as rb
from jason.tasks import record_slots as rs
from jason.tasks import record_upload as up

from test_record_intake_phase2 import (  # noqa: F401  (world is a fixture)
    BY, FILE_A, FILE_C, MINUTES, NAME_A, _app, fake_segments, make_pdf, pick, quiet_preflight, read, slot_row, store, world,
)

MIN = "records/5200/minutes"
BYL = "governing/bylaws"


def _pdf(n=1):
    from pypdf import PdfWriter

    w = PdfWriter()
    for _ in range(n):
        w.add_blank_page(width=200, height=200)
    buf = io.BytesIO()
    w.write(buf)
    return buf.getvalue()


def _up(world, slot=MIN, name="Scan.pdf", data=None, **kw):
    kw.setdefault("preflighter", quiet_preflight)
    kw.setdefault("dry_run", False)
    kw.setdefault("period", "2099-06" if slot == MIN else "")
    return up.upload(slot, by=BY, name=name, data=data if data is not None else _pdf(), community=world.community, root=world.root,
                     profile="example", **kw)


# --- upload ------------------------------------------------------------------------------------------------------------------

def test_a_dry_run_checks_the_file_and_keeps_nothing(world):
    out = _up(world, dry_run=True)
    assert out["dryRun"] is True and out["would"]["type"] == "a PDF" and out["would"]["sha256"]
    assert not (world.root / "record-intake").exists() and not (world.spec / "example" / "records.json").exists()


def test_an_upload_is_kept_by_hash_in_jasons_own_store_pinned_and_read_back(world):
    data = _pdf()
    out = _up(world, data=data)
    assert out["ok"] and out["pin"].startswith("p-")
    kept = list((world.root / "record-intake" / "example" / "files").glob("*/*"))
    assert len(kept) == 1 and kept[0].read_bytes() == data and kept[0].parent.name == out["sha256"] + kept[0].parent.name[12:]
    row = store(world)["pins"][0]
    assert row["kind"] == "file" and row["ref"].startswith("record-intake/example/files/")
    assert out["read"]["reads"][0]["ok"] is True                                 # the same read-back as phase 2
    view = slot_row(world, MIN)
    assert view["holders"][0]["readback"] is not None and view["holders"][0]["kind"] == "file"
    assert world.drive.calls == [] and world.drive.writes == []                  # never Drive
    # the same bytes again are one copy and one pin
    again = _up(world, data=data)
    assert again["already"] is True and again["pin"] == out["pin"]
    assert len(list((world.root / "record-intake" / "example" / "files").glob("*/*"))) == 1


def test_a_file_that_is_too_big_or_the_wrong_type_is_refused_in_words(world, monkeypatch):
    with pytest.raises(ValueError, match="does not read as a PDF"):
        _up(world, name="Fake.pdf", data=b"<html>not a pdf</html>")
    with pytest.raises(ValueError, match="takes a PDF"):
        _up(world, name="Run.exe", data=b"MZ\x00\x00")
    with pytest.raises(ValueError, match="empty"):
        _up(world, data=b"")
    with pytest.raises(ValueError, match="not a Word package"):
        _up(world, name="Letter.docx", data=b"PK\x03\x04junk")
    monkeypatch.setattr(up, "MAX_UPLOAD_BYTES", 100)
    with pytest.raises(ValueError, match="the limit is"):
        _up(world, data=_pdf(3))
    assert not (world.spec / "example" / "records.json").exists()


def test_a_word_file_and_an_image_pass_the_type_check():
    import zipfile

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("word/document.xml", "<w/>")
    assert up.check("Agenda.docx", buf.getvalue())[1].startswith("a Word file")
    assert up.check("Photo.JPG", b"\xff\xd8\xff\xe0abc")[1] == "a JPEG image"
    assert up.check("a/b/Scan.tif", b"II*\x00abc")[0] == "Scan.tif"


def test_an_upload_names_its_person_and_the_history_holds_no_file_name(world):
    with pytest.raises(ValueError, match="who"):
        up.upload(MIN, by="", name="x.pdf", data=_pdf(), period="2099-06", dry_run=False, community=world.community, root=world.root, profile="example")
    with pytest.raises(ValueError, match="never writes in its own name"):
        up.upload(MIN, by="jason", name="x.pdf", data=_pdf(), period="2099-06", dry_run=False, community=world.community, root=world.root, profile="example")
    _up(world, name="Secret Board Minutes.pdf")
    history = (world.root / "records" / "history.jsonl").read_text(encoding="utf-8")
    assert "Secret Board Minutes" not in history and '"act": "upload"' in history


def test_a_series_needs_its_period_and_a_path_reads_from_the_computer(world):
    with pytest.raises(ValueError, match="series|period"):
        up.upload(MIN, by=BY, name="x.pdf", data=_pdf(), period="June", dry_run=True, community=world.community, root=world.root, profile="example")
    path = world.tmp / "Local Scan.pdf"
    path.write_bytes(_pdf())
    out = up.upload(MIN, by=BY, path=str(path), period="2099-06", dry_run=False, read=False, community=world.community, root=world.root,
                    profile="example")
    assert out["ok"] and "read" not in out and out["reading"].startswith("not read yet")
    with pytest.raises(ValueError, match="no such file"):
        up.upload(MIN, by=BY, path=str(world.tmp / "nope.pdf"), community=world.community, root=world.root, profile="example")


def test_an_upload_to_a_recorded_instrument_goes_through_the_key_documents_writer(world):
    out = _up(world, slot=BYL)
    assert out["pin"].startswith("k-")
    from jason.tasks import key_documents as kd

    assert kd.KeyDocumentStore(world.root, "example").load()["entries"]["bylaws"]["links"][0]["kind"] == "upload"
    assert not (world.spec / "example" / "records.json").exists()


# --- the confirmed split ---------------------------------------------------------------------------------------------------------

def _combined(world):
    path = world.tmp / "combined.pdf"
    path.write_bytes(_pdf(3))
    made = up.upload(BYL, by=BY, path=str(path), dry_run=False, read=False, community=world.community, root=world.root, profile="example")
    parts = [(1, 1, "bylaws", "likely"), (2, 2, "minutes", "suggested"), (3, 3, "operating_rules", "suggested")]
    rb.read(BYL, pin=made["pin"], by=BY, dry_run=False, segmenter=fake_segments(parts), preflighter=quiet_preflight,
            community=world.community, root=world.root, profile="example")
    return made["pin"]


def _split(world, pin, parts, **kw):
    kw.setdefault("dry_run", False)
    return up.split(BYL, pin=pin, parts=parts, by=BY, community=world.community, root=world.root, profile="example", **kw)


def test_with_no_parts_named_the_split_shows_the_proposal_and_fills_nothing(world):
    pin = _combined(world)
    out = _split(world, pin, [])
    assert out["dryRun"] is True and [p["segment"] for p in out["proposal"]] == ["s1", "s2", "s3"] and out["proposal"][0]["slots"]
    assert slot_row(world, MIN)["state"] == "empty"


def test_a_split_fills_only_the_parts_a_person_confirmed_each_a_file_of_just_its_pages(world):
    pin = _combined(world)
    dry = _split(world, pin, ["s2=" + MIN + "@2099-06"], dry_run=True)
    assert dry["dryRun"] is True and dry["parts"][0]["action"] == "fill"
    assert slot_row(world, MIN)["state"] == "empty"
    out = _split(world, pin, [{"segment": "s2", "slot": MIN, "period": "2099-06"}])
    assert [m["slot"] for m in out["filled"]] == [MIN]
    assert slot_row(world, MIN)["state"] == "uploaded"
    assert slot_row(world, "governing/operating-rules")["state"] == "empty"      # s3 was not confirmed: it fills nothing
    new = next(p for p in store(world)["pins"] if p["slot"] == MIN)
    from pypdf import PdfReader

    assert len(PdfReader(str(world.root / new["ref"])).pages) == 1 and new["splitFrom"] == pin and new["period"] == "2099-06"
    reading = rb.load(world.root, "example", pin)
    assert reading["split"]["confirmed"]["s2"]["by"] == BY
    prop = {p["segment"]: p for p in reading["segments"]["proposal"]}
    assert prop["s2"]["confirmed"] is True and prop["s3"]["confirmed"] is False
    history = (world.root / "records" / "history.jsonl").read_text(encoding="utf-8")
    assert "combined.pdf" not in history and "part-pages" not in history and '"act": "split"' in history
    # the original scan and its pin are untouched
    assert slot_row(world, BYL)["holders"][0]["pin"] == pin


def test_a_part_whose_slot_already_holds_a_file_is_a_collision_and_is_not_overwritten(world):
    pin = _combined(world)
    held = _up(world, slot="governing/operating-rules", data=_pdf(2))
    out = _split(world, pin, ["s3=governing/operating-rules", "s2=" + MIN + "@2099-06", "s1=" + MIN + "@2099-06"])
    actions = {p["segment"]: p["action"] for p in out["parts"]}
    assert actions == {"s3": "collision", "s2": "fill", "s1": "collision"}        # s1 collides with s2 in the same request
    assert [f["slot"] for f in out["filled"]] == [MIN]
    from jason.tasks import key_documents as kd

    links = kd.KeyDocumentStore(world.root, "example").load()["entries"]["operating-rules"]["links"]
    assert ["k-" + l["id"] for l in links] == [held["pin"]]                       # the file already there is the only one
    assert "kept" in out["parts"][0]


def test_a_split_refuses_a_stale_file_a_hidden_slot_and_an_unknown_part(world):
    pin = _combined(world)
    with pytest.raises(ValueError, match="no part s9"):
        _split(world, pin, ["s9=" + MIN + "@2099-06"])
    with pytest.raises(ValueError, match="series"):
        _split(world, pin, ["s2=" + MIN])
    with pytest.raises(KeyError):
        _split(world, pin, ["s2=nope/none"])
    with pytest.raises(ValueError, match="who"):
        up.split(BYL, pin=pin, parts=["s2=" + MIN + "@2099-06"], by="", dry_run=False, community=world.community, root=world.root, profile="example")
    rec = rb.load(world.root, "example", pin)
    next(world.root.joinpath(rec["stored"]).parent.glob("*"), None)
    from pathlib import Path

    Path(rec["stored"]).write_bytes(_pdf(4))                                      # the bytes changed after the reading
    with pytest.raises(ValueError, match="changed since jason read it"):
        _split(world, pin, ["s2=" + MIN + "@2099-06"])


def test_a_person_may_decline_the_proposal_and_the_queue_forgets_it(world):
    pin = _combined(world)
    assert any(i["reason"] == "combined scan" for i in rb.queue_items(world.community, world.root, "example", private=True)["items"])
    out = _split(world, pin, [], decline=True)
    assert out["declined"] is True
    assert not any(i["reason"] == "combined scan" for i in rb.queue_items(world.community, world.root, "example", private=True)["items"])


def test_the_queue_keeps_a_split_open_until_every_part_is_confirmed(world):
    pin = _combined(world)
    _split(world, pin, ["s2=" + MIN + "@2099-06"])
    items = rb.queue_items(world.community, world.root, "example", private=True)["items"]
    assert [i["confirmedParts"] for i in items if i["reason"] == "combined scan"] == [1]
    state = slot_row(world, BYL)["holders"][0]["readback"]["split"]
    assert state["open"] is True and state["confirmed"][0]["slot"] == MIN
    assert slot_row(world, BYL)["acts"]["split"] is True


# --- acknowledging a change --------------------------------------------------------------------------------------------------------

def _changed(world):
    made = pick(world, MIN, FILE_A, period="2099-06")
    read(world, dry=False)
    world.drive.files[FILE_A]["data"] = make_pdf([MINUTES, MINUTES])
    world.drive.files[FILE_A]["meta"]["modifiedTime"] = "2099-10-02T10:00:00Z"
    world.drive.files[FILE_A]["meta"]["size"] = str(len(world.drive.files[FILE_A]["data"]))
    read(world, dry=False, preflighter=lambda p, r: {**quiet_preflight(p, r), "pages": 2})
    return made["pin"]


def test_acknowledging_a_change_keeps_the_mark_as_history_and_clears_the_flag(world):
    pin = _changed(world)
    view = slot_row(world, MIN)
    assert view["holders"][0]["changed"] and view["acts"]["ack"] is True
    dry = up.ack(MIN, by=BY, community=world.community, root=world.root, profile="example")
    assert dry["dryRun"] is True and dry["would"]["changed"]
    assert slot_row(world, MIN)["holders"][0]["changed"]                          # a dry run changed nothing
    out = up.ack(MIN, by=BY, dry_run=False, community=world.community, root=world.root, profile="example")
    assert out["acknowledged"] == pin
    after = slot_row(world, MIN)
    assert after["holders"][0]["changed"] is None and after["holders"][0]["readback"]["acknowledged"]["by"] == BY
    assert after["acts"]["ack"] is False
    assert rb.load(world.root, "example", pin)["lastChange"]["diff"]              # the trail keeps it
    with pytest.raises(ValueError, match="no changed mark|0 changed marks"):
        up.ack(MIN, by=BY, dry_run=False, community=world.community, root=world.root, profile="example")
    # reading again, unchanged, does not bring the flag back
    read(world, dry=False, force=True, preflighter=lambda p, r: {**quiet_preflight(p, r), "pages": 2})
    assert slot_row(world, MIN)["holders"][0]["changed"] is None


# --- what reads a slot -------------------------------------------------------------------------------------------------------------

def test_the_slot_shows_which_duties_conflicts_and_programs_read_it_and_decides_nothing(world):
    from jason.community.authority_order import Clarity, Conflict, ConflictStatus, Tier

    row = Conflict("c1", "the 2099 board policy", Tier.OPERATING_RULES, "says a thing", "CIV 5200", Tier.STATUTE, None, "the part", "apply",
                   Clarity.UNCLEAR, ConflictStatus.COUNSEL)
    world.community.conflicts = lambda: (row,)
    st = slot_row(world, MIN)["standing"]
    assert st["duties"] and all("because" in d for d in st["duties"])
    assert st["conflicts"]["count"] == 1 and st["conflicts"]["items"][0]["key"] == "c1" and st["conflicts"]["open"] == 1
    assert st["programs"]["available"] is False and "not built" in st["programs"]["why"]
    assert st["pinned"] == 0
    assert any("decides nothing" in c for c in st["caveats"])
    plain = slot_row(world, BYL)["standing"]
    assert plain["conflicts"]["count"] == 0                                       # a conflict citing another section is not listed


# --- the console -------------------------------------------------------------------------------------------------------------------

def test_the_console_uploads_bytes_queues_the_read_and_splits_and_acknowledges(world, monkeypatch):
    c = webclient.client(_app(world, monkeypatch))
    url = "/api/write/records/" + MIN
    body = {"act": "upload", "name": "Minutes.pdf", "base64": base64.b64encode(_pdf()).decode(), "period": "2099-06", "by": BY}
    plan = c.post(url, json={**body, "dryRun": True})
    assert plan.status_code == 200 and plan.json["dryRun"] is True and not (world.root / "record-intake").exists()
    made = c.post(url, json=body)
    assert made.status_code == 200 and made.json["pin"].startswith("p-") and made.json["queued"] is True
    assert made.json["command"].startswith("jason records --read")
    from jason import jobs

    assert any("--read" in j.argv for j in jobs.list_jobs(world.root)) if hasattr(jobs, "list_jobs") else True
    assert c.post(url, json={**body, "path": "C:/secret.pdf"}).status_code == 400
    assert c.post(url, json={"act": "upload", "name": "x.exe", "base64": base64.b64encode(b"MZ").decode(), "by": BY}).status_code == 400
    assert c.post(url, json={"act": "upload", "name": "x.pdf", "base64": "not base64!!", "by": BY}).status_code == 400
    assert c.post(url, json={"act": "replace", "by": BY}).status_code == 400
    assert c.post(url, json={"act": "ack", "by": BY}).status_code == 400            # nothing changed to acknowledge


def test_the_console_split_confirms_parts_and_shows_collisions(world, monkeypatch):
    c = webclient.client(_app(world, monkeypatch))
    pin = _combined(world)
    url = "/api/write/records/" + BYL
    shown = c.post(url, json={"act": "split", "pin": pin, "by": BY})
    assert shown.status_code == 200 and len(shown.json["proposal"]) == 3
    done = c.post(url, json={"act": "split", "pin": pin, "by": BY, "parts": [{"segment": "s2", "slot": MIN, "period": "2099-06"}]})
    assert done.status_code == 200 and done.json["filled"][0]["slot"] == MIN
    again = c.post(url, json={"act": "split", "pin": pin, "by": BY, "parts": [{"segment": "s1", "slot": MIN, "period": "2099-06"}]})
    assert again.json["parts"][0]["action"] == "collision" and again.json["filled"] == []
    assert c.post(url, json={"act": "split", "pin": pin, "by": ""}).status_code == 400
    assert world.drive.calls == []
