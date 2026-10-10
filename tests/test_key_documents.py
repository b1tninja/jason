"""The key documents checklist: the list as data, the expansion from the specification, the index, the locator's leads,
and the copies on disk; the status rule; and the store a person links, uploads, unlinks, and marks. Made-up names."""

import base64
import json
from datetime import date
from types import SimpleNamespace

import pytest

import webclient
from jason.community.documents import Amendment, Document, GoverningDocument, deliver, pin
from jason.community.governing import GoverningRecord, Supersession
from jason.community.key_documents import (
    KEY_DOCUMENTS,
    Copy,
    Entry,
    KeyDocumentStore,
    KeyStatus,
    LinkKind,
    drive_id,
    expected_entries,
    max_upload_bytes,
    status_of,
    valid_key,
)
from jason.community.symbols import DeveloperDelivery, DocumentKind
from jason.tasks import key_documents as kd

BUILDER = "EXAMPLE BUILDERS LLC"


class _First(Amendment, Document):
    def __init__(self):
        super().__init__(title="First Amendment", drive_id="amend1amend1", sections=("4.2",), recorder_number="2010-0000100",
                         recorded=date(2010, 2, 1))


class _Draft(Amendment, Document):
    def __init__(self):
        super().__init__(title="Second Amendment", drive_id="amend2amend2")


class _Declaration(GoverningDocument):
    def __init__(self):
        super().__init__(title="CC&Rs", drive_id="declaration1", document_kind=DocumentKind.DECLARATION,
                         recorder_number="2001-0000020", recorded=date(2001, 3, 8), amendments=(_First(), _Draft()))

    def cite(self):
        return "CC&Rs"


def _record(number, day, role, delivery=DeveloperDelivery.DECLARATION, phase=None, superseded_by=""):
    return GoverningRecord(number, date.fromisoformat(day), "220 AMENDED RESTRICTION", role, delivery, (BUILDER,), phase, (), "", superseded_by)


GOVERNING = (
    _record("2001-0000010", "2001-03-01", "declaration", superseded_by="2001-0000020"),
    _record("2001-0000020", "2001-03-08", "restated declaration"),
    _record("2001-0000012", "2001-03-01", "condominium plan", DeveloperDelivery.CONDOMINIUM_PLAN),
    _record("2003-0000050", "2003-06-01", "annexation", phase=2),
    _record("2010-0000100", "2010-02-01", "amendment"),
    _record("2001-0000011", "2001-03-01", "common area deed", DeveloperDelivery.COMMON_AREA_DEED),
)
PINS = (
    pin("CC&Rs", "declaration1", DocumentKind.DECLARATION),
    pin("CC&Rs.pdf", "declarationpdf", DocumentKind.DECLARATION),
    pin("First Amendment.pdf", "amend1pdfpdf", DocumentKind.AMENDMENT),
    pin("Annexation - Phase 2.pdf", "annex2annex2", DocumentKind.ANNEXATION),
    deliver("Condominium Plan 2001-0000012.pdf", "plan12plan12", DocumentKind.CONDOMINIUM_PLAN, DeveloperDelivery.CONDOMINIUM_PLAN),
    deliver("Final Map.pdf", "finalmapfile", DocumentKind.MAP, DeveloperDelivery.SUBDIVISION_MAP),
)
REPORTS = (SimpleNamespace(phase=1, annexation=None), SimpleNamespace(phase=2, annexation=date(2003, 6, 1)),
           SimpleNamespace(phase=3, annexation=date(2005, 1, 1)))
LOCATED = (
    {"number": "2012-0000300", "recorded": "2012-01-01", "filing": "MODIFICATION OF RESTRICTIONS", "item": "amendments", "tie": "names the association"},
    {"number": "2001-0000020", "recorded": "2001-03-08", "filing": "AMENDED RESTRICTION", "item": "declaration", "tie": "names the association"},
    {"number": "2015-0000001", "item": "recorded-liens"},
)


def _entries(**over):
    args = dict(governing_document=_Declaration(), governing=GOVERNING, supersessions=(Supersession("2001-0000010", "2001-0000020", role="declaration", reason="recital F"),),
                pins=PINS, public_reports=REPORTS, located=LOCATED, on_disk={"2003-0000050": "governing/annexation-2.pdf"})
    args.update(over)
    return {e.key: e for e in expected_entries(**args)}


def test_the_list_is_data_with_the_onboarding_items():
    keys = [row.key for row in KEY_DOCUMENTS]
    assert keys[:3] == ["declaration", "amendments", "annexations"]
    assert {"condominium-plans", "maps", "common-area-deeds", "notices-of-completion", "public-reports", "bylaws", "articles"} <= set(keys)
    assert valid_key("declaration") and valid_key("amendments/2010-0000100") and valid_key("other/insurance-binder")
    assert not valid_key("nothing") and not valid_key("other") and not valid_key("../x")


def test_the_expansion_reads_the_specification_the_index_the_leads_and_the_disk():
    entries = _entries()
    declaration = entries["declaration"]
    assert declaration.number == "2001-0000020" and {"specification", "county index"} <= set(declaration.sources)
    assert {c.name for c in declaration.copies} == {"CC&Rs", "CC&Rs.pdf"}
    assert declaration.leads and declaration.leads[0]["number"] == "2001-0000020"
    rescinded = entries["declaration/2001-0000010"]
    assert rescinded.superseded_by == "2001-0000020" and "recital F" in rescinded.notes
    first = entries["amendments/2010-0000100"]
    assert first.sections == ("4.2",) and [c.name for c in first.copies] == ["First Amendment.pdf"]   # by its title
    draft = entries["amendments/second-amendment"]
    assert not draft.number and "takes effect when recorded" in draft.notes[0]
    located = entries["amendments/2012-0000300"]
    assert located.title == "Modification of restrictions" and located.sources == ["locator"]
    annex = entries["annexations/2003-0000050"]
    assert annex.phase == 2 and {c.kind for c in annex.copies} == {"drive", "disk"}
    assert "annexations/phase-3" in entries and "annexations/phase-1" not in entries
    assert [c.name for c in entries["condominium-plans/2001-0000012"].copies] == ["Condominium Plan 2001-0000012.pdf"]
    assert [c.name for c in entries["maps/files"].copies] == ["Final Map.pdf"]
    assert "common-area-deeds/2001-0000011" in entries
    assert not any("2015-0000001" in k for k in entries)                 # the association's own liens are not key documents


def test_status_is_computed_and_missing_is_only_a_persons_word():
    bare = Entry("bylaws", "bylaws", "Bylaws")
    assert status_of(bare, None)[0] is KeyStatus.EXPECTED
    numbered = Entry("maps/1", "maps", "Map", number="1", sources=["county index"])
    assert status_of(numbered, None)[0] is KeyStatus.LOCATED
    held = Entry("maps/1", "maps", "Map", number="1", copies=[Copy("drive", "abc", "Map.pdf", "specification pin")])
    assert status_of(held, None)[0] is KeyStatus.HELD
    said = {"status": {"value": "missing", "by": "Jane Example", "at": "2026-10-03T00:00:00+00:00", "note": "not in the files"}, "links": []}
    status, why = status_of(held, said)
    assert status is KeyStatus.MISSING and "Jane Example" in why
    linked = {**said, "links": [{"id": "l-1", "unlinked": None}]}
    assert status_of(held, linked)[0] is KeyStatus.LINKED
    gone = {**said, "links": [{"id": "l-1", "unlinked": {"by": "Jane Example"}}]}
    assert status_of(held, gone)[0] is KeyStatus.MISSING


def test_the_store_links_unlinks_and_records_who(tmp_path):
    store = KeyDocumentStore(tmp_path, "example")
    link = store.link("maps", LinkKind.DRIVE, "abcdefghijkl", by="Jane Example", name="Final Map.pdf")
    assert store.link("maps", LinkKind.DRIVE, "abcdefghijkl", by="Casey Sample")["id"] == link["id"]   # one link, not two
    gone = store.unlink("maps", link["id"], by="Casey Sample", note="wrong map")
    assert gone["unlinked"]["by"] == "Casey Sample"
    data = json.loads((tmp_path / "key-documents" / "example.json").read_text(encoding="utf-8"))
    entry = data["entries"]["maps"]
    assert [x["action"] for x in entry["log"]] == ["link", "unlink"] and entry["links"][0]["by"] == "Jane Example"
    with pytest.raises(ValueError):
        store.link("maps", LinkKind.DRIVE, "x" * 12, by="")
    with pytest.raises(ValueError):
        store.link("maps", LinkKind.DRIVE, "x" * 12, by="jason")
    with pytest.raises(ValueError):
        store.set_status("maps", KeyStatus.MISSING, by="Jane Example")          # missing says what was looked for
    with pytest.raises(ValueError):
        store.set_status("maps", KeyStatus.LINKED, by="Jane Example")
    with pytest.raises(KeyError):
        store.link("nothing", LinkKind.DRIVE, "x" * 12, by="Jane Example")
    with pytest.raises(KeyError):
        store.unlink("maps", "l-none", by="Jane Example")
    assert store.set_status("maps", "missing", by="Jane Example", note="asked the prior manager")["value"] == "missing"


def test_uploads_keep_the_name_never_overwrite_and_are_capped(tmp_path, monkeypatch):
    monkeypatch.setenv("JASON_LIMIT_UPLOAD_MAX_BYTES", "1048576")                 # the limit's smallest value: a small file shows the cap
    store = KeyDocumentStore(tmp_path, "example")
    rel, digest, size = store.save_upload("Declaration.pdf", b"%PDF one")
    assert rel.startswith("key-documents/example/files/") and rel.endswith("/Declaration.pdf") and size == 8
    assert store.save_upload("Declaration.pdf", b"%PDF one")[0] == rel                     # the same file is one copy
    other, _, _ = store.save_upload("Declaration.pdf", b"%PDF two")
    assert other != rel and (tmp_path / rel).read_bytes() == b"%PDF one"                  # never overwritten
    assert store.save_upload("..\\..\\evil\\Map.pdf", b"x")[0].endswith("/Map.pdf")         # no folder from the name
    with pytest.raises(ValueError):
        store.save_upload("run.exe", b"x")
    with pytest.raises(ValueError):
        store.save_upload("big.pdf", b"x" * (max_upload_bytes() + 1))
    assert max_upload_bytes() == 1048576


def test_drive_ids_come_from_links_or_ids():
    assert drive_id("https://drive.google.com/file/d/1AbCdEfGhIjKlMnOp/view?usp=sharing") == "1AbCdEfGhIjKlMnOp"
    assert drive_id("https://docs.google.com/document/d/1AbCdEfGhIjKlMnOp/edit") == "1AbCdEfGhIjKlMnOp"
    assert drive_id("https://drive.google.com/open?id=1AbCdEfGhIjKlMnOp") == "1AbCdEfGhIjKlMnOp"
    with pytest.raises(ValueError):
        drive_id("not a link")


class _Community:
    name = "Example Village Homeowners Association"
    region = "ca/example"
    ccrs = _Declaration()

    def supersessions(self):
        return ()

    def pins(self):
        return PINS

    def public_reports(self):
        return REPORTS


def test_the_checklist_names_each_copy_by_a_document_reference(tmp_path, monkeypatch):
    """Copies and links are ``DocRef``s (docs/console/doc-component.md): a recorded copy on disk is a ``file:`` reference
    labelled "Recorded copy", a Drive pin or link a ``drive:`` one with Open in Google; never a URL into data/. Each
    resolves."""
    from jason.approvals.evidence import resolve

    root = tmp_path / "data"
    (root / "governing").mkdir(parents=True)
    (root / "governing" / "Condominium Plan 2001-0000012.pdf").write_bytes(b"%PDF")
    monkeypatch.setenv("JASON_SPEC_DIR", str(tmp_path / "spec"))
    (root / "drive").mkdir()
    listed = [p.drive_id for p in PINS] + ["1AbCdEfGhIjKlMnOp"]
    (root / "drive" / "files.json").write_text(json.dumps({"syncedAt": "2099-01-05T00:00:00+00:00", "files": [
        {"id": i, "name": f"File {i}.pdf", "path": f"Board/File {i}.pdf", "mimeType": "application/pdf"} for i in listed]}),
        encoding="utf-8")
    kd.link("maps", by="Jane Example", drive="1AbCdEfGhIjKlMnOp", root=root, profile="example")
    kd.upload("articles", by="Jane Example", name="Articles.pdf", base64_body=base64.b64encode(b"%PDF articles").decode(),
              root=root, profile="example")
    data = kd.checklist(_Community(), root, "example")
    assert "/api/file" not in json.dumps(data) and str(root) not in json.dumps(data)
    entries = [e for g in data["groups"] for e in g["entries"]]
    disk = [c for e in entries for c in e["copies"] if c["kind"] == "disk"]
    drive = [c for e in entries for c in e["copies"] if c["kind"] == "drive"]
    links = {lk["kind"]: lk for e in entries for lk in e["links"]}
    assert disk and all(c["doc"]["source"] == "Recorded copy" and c["doc"]["address"] == f"file:{c['ref']}" and "url" not in c
                        for c in disk)
    assert drive and all(c["doc"]["address"] == f"drive:{c['ref']}" and c["doc"]["original"]["label"] == "Open in Google"
                         for c in drive)
    assert links["drive"]["doc"]["address"] == "drive:1AbCdEfGhIjKlMnOp" and links["drive"]["url"]
    assert links["upload"]["doc"]["address"].startswith("file:key-documents/example/files/") and "url" not in links["upload"]
    for doc in [c["doc"] for c in disk + drive] + [links["drive"]["doc"], links["upload"]["doc"]]:
        assert resolve(doc["address"], data_dir=root)["found"], doc["address"]


def test_the_checklist_and_the_task_writes(tmp_path, monkeypatch):
    root = tmp_path / "data"
    (root / "governing").mkdir(parents=True)
    (root / "governing" / "Annexation 2003-0000050.pdf").write_bytes(b"%PDF")
    (root / "onboarding").mkdir()
    (root / "onboarding" / "example-documents-located.json").write_text(json.dumps({"items": [
        {"item": "maps", "located": [{"number": "2001-0000013", "recorded": "2001-03-01", "filing": "SUBDIVISION MAP",
                                      "tie": "beside", "tie_label": "recorded with the association's documents", "via": "2001-0000020"}]},
    ]}), encoding="utf-8")
    spec = tmp_path / "spec"
    spec.mkdir()
    (spec / "example.json").write_text(json.dumps({"leads": [{"key": "located-bylaws", "item": "bylaws", "choices": [
        "2002-0000001 (2002-01-01, BYLAWS; names the association)", "none of these: dismiss"]}]}), encoding="utf-8")
    monkeypatch.setenv("JASON_SPEC_DIR", str(spec))
    data = kd.checklist(_Community(), root, "example")
    assert data["found"] and data["county"] == "Example" and any("no index cache" in n for n in data["notes"])
    entries = {e["key"]: e for g in data["groups"] for e in g["entries"]}
    assert entries["annexations/phase-2"]["status"] == "held"                    # the pin, placed by its phase
    assert entries["maps/2001-0000013"]["status"] == "located"
    assert entries["maps/2001-0000013"]["leads"][0]["tie"] == "recorded with the association's documents"
    assert entries["bylaws"]["leads"][0]["number"] == "2002-0000001"
    # A file under data/ links; one outside it is uploaded instead.
    (root / "governing" / "Bylaws.pdf").write_bytes(b"%PDF bylaws")
    linked = kd.link("bylaws", by="Jane Example", file="governing/Bylaws.pdf", root=root, profile="example")
    assert linked["kind"] == "file" and "url" not in linked and len(linked["sha256"]) == 64
    assert linked["doc"]["address"] == "file:governing/Bylaws.pdf" and linked["doc"]["level"] == "P0"
    outside = tmp_path / "Articles.pdf"
    outside.write_bytes(b"%PDF articles")
    with pytest.raises(ValueError):
        kd.link("articles", by="Jane Example", file=str(outside), root=root, profile="example")
    uploaded = kd.upload("articles", by="Jane Example", path=str(outside), root=root, profile="example")
    assert (root / uploaded["ref"]).read_bytes() == b"%PDF articles" and outside.exists()
    sent = kd.upload("other/insurance-binder", by="Jane Example", name="Binder.pdf",
                     base64_body=base64.b64encode(b"%PDF binder").decode(), title="Insurance binder", root=root, profile="example")
    assert sent["name"] == "Binder.pdf"
    with pytest.raises(ValueError):
        kd.link("bylaws", by="Jane Example", file="governing/Bylaws.pdf", drive="1AbCdEfGhIjK", root=root, profile="example")
    kd.unlink("bylaws", linked["id"], by="Casey Sample", root=root, profile="example")
    assert (root / "governing" / "Bylaws.pdf").exists()
    data = kd.checklist(_Community(), root, "example")
    entries = {e["key"]: e for g in data["groups"] for e in g["entries"]}
    assert entries["articles"]["status"] == "linked" and entries["bylaws"]["status"] == "located"
    assert entries["bylaws"]["unlinked"][0]["unlinked"]["by"] == "Casey Sample"
    assert entries["other/insurance-binder"]["title"] == "Insurance binder"
    assert "Key documents" in kd.markdown(data)


def test_the_web_write_and_routes(tmp_path, monkeypatch):
    from jason.web.app import create_app
    from jason.web.extra import key_documents as web
    from jason.web.sources import EXTRA_LOADERS, EXTRA_WRITERS

    assert "key-documents" in EXTRA_LOADERS and "instrument-graph" in EXTRA_LOADERS and "key-documents" in EXTRA_WRITERS
    root = tmp_path / "data"
    root.mkdir()
    monkeypatch.setattr(kd, "_root", lambda given=None: root)
    out = web.write("maps", {"action": "link", "kind": "drive", "ref": "https://drive.google.com/file/d/1AbCdEfGhIjKlMnOp/view", "by": "Jane Example"})
    assert out["ok"] and out["result"]["ref"] == "1AbCdEfGhIjKlMnOp"
    with pytest.raises(ValueError):
        web.write("maps", {"action": "erase", "by": "Jane Example"})
    c = webclient.client(create_app(tmp_path, {}))
    body = {"action": "upload", "name": "Map.pdf", "base64": base64.b64encode(b"%PDF map").decode(), "by": "Jane Example"}
    posted = c.post("/api/write/key-documents/maps/2001-0000013", json=body)
    assert posted.status_code == 200 and posted.json["result"]["kind"] == "upload"
    assert c.post("/api/write/key-documents/maps", json={"action": "status", "value": "missing", "by": "Jane Example"}).status_code == 400
    assert c.post("/api/write/key-documents/nothing", json={"action": "link", "kind": "drive", "ref": "1AbCdEfGhIjK", "by": "Jane Example"}).status_code == 400
    assert c.post("/api/write/key-documents/maps", json={"action": "unlink", "link": "l-none", "by": "Jane Example"}).status_code == 404
