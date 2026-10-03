"""``jason ingest``: a made-up box of documents taken in as one step. A duplicate, a scan with no text layer read by a
faked OCR engine, two versions of a known policy, two drafts of rules no document claims, a kind no folder holds (a MAP
question), a file nothing classifies (a CLASSIFY question), and a file the library already holds; a dry run against
``--apply`` and ``--park``. A made-up profile throughout."""

import json
import sqlite3

import pytest

from jason.community import Community, intake
from jason.community.base import LibraryFolder
from jason.community.books import Book, BookEntry
from jason.community.documents import KindRule
from jason.community.intake import AskKind
from jason.community.outlines import CitableDocument
from jason.community.symbols import AssociationRecord, DocumentKind
from jason.tasks import ingest
from jason.tasks import library as library_task

K = DocumentKind
POLICY_V1 = ("Pet Policy. 1. Dogs must be leashed in the common area at all times. 2. No more than two pets live in "
             "a unit. 3. Owners clean up after their pets at once. 4. A pet that disturbs the neighbors may be "
             "removed after notice and a hearing before the board. 5. Exotic animals are not kept.")
POLICY_V2 = POLICY_V1.replace("No more than two pets", "No more than three pets") + \
    " 6. Service animals are not pets under this policy."
RULES_A = ("Guest Parking Rules. Guests park only in the marked guest spaces for up to seventy-two hours. A vehicle "
           "left longer is towed at the owner's cost after a notice on its windshield. Residents never park in guest "
           "spaces overnight. Commercial vehicles park off site.")
RULES_B = RULES_A.replace("seventy-two hours", "forty-eight hours")
SCAN_WORDS = ("MINUTES OF THE REGULAR MEETING OF THE BOARD OF DIRECTORS held on January 10, 2099 at the clubhouse. "
              "The meeting was called to order at 6:00 pm. Present: three directors. A motion to approve the budget "
              "was seconded and carried. The meeting adjourned at 7:00 pm.")


def _stub():
    members = {name: (lambda self, *a, **k: ()) for name in Community.__abstractmethods__}
    members.update(
        name="Oakview Example Association", slug="oakview", org_id=0, root=None,
        document_sync_rules=lambda self: {"rules": [], "exclude": []},
        kind_rules=lambda self: (KindRule(K.MINUTES, ("*minutes*",)), KindRule(K.POLICY, ("*policy*",)),
                                 KindRule(K.OPERATING_RULES, ("*rules*",)), KindRule(K.POLICE_REPORT, ("*police*",))),
        library_folders=lambda self: (
            LibraryFolder(None, 1, "Meetings/", records=(AssociationRecord.MINUTES,)),
            LibraryFolder(None, 2, "Governing Documents/", records=(AssociationRecord.GOVERNING_DOCUMENTS,)),
            LibraryFolder(None, 3, "Governing Documents/Policies/", records=(AssociationRecord.GOVERNING_DOCUMENTS,))),
        citable_documents=lambda self: (CitableDocument("pet-policy", "Pet Policy", "doc-1", K.POLICY),),
        book_entries=lambda self: (BookEntry("pet-policy", Book.RULES, part="pets"),),
    )
    return type("Oakview", (Community,), members)()


def _pdf(path, text=""):
    import pymupdf

    doc = pymupdf.open()
    page = doc.new_page()
    if text:
        page.insert_textbox(pymupdf.Rect(36, 36, 560, 800), text, fontsize=10)
    doc.save(str(path))
    doc.close()


class _FakeOcr:
    name = "fake-ocr"

    def __init__(self):
        self.read = []

    def text_of(self, path):
        self.read.append(path.name)
        return SCAN_WORDS


@pytest.fixture
def box(tmp_path, monkeypatch):
    data = tmp_path / "data"
    box = tmp_path / "Box"
    (box / "copies").mkdir(parents=True)
    minutes = "Minutes of the board meeting held on February 14, 2099. " + SCAN_WORDS.split("held on", 1)[1] * 2
    _pdf(box / "Board Minutes 2099-02-14.pdf", minutes)
    (box / "copies" / "Board Minutes 2099-02-14 copy.pdf").write_bytes((box / "Board Minutes 2099-02-14.pdf").read_bytes())
    _pdf(box / "scan-001.pdf")                                                   # no text layer
    (box / "Pet Policy 2098.txt").write_text(POLICY_V1, encoding="utf-8")
    (box / "Pet Policy 2099.txt").write_text(POLICY_V2, encoding="utf-8")
    (box / "Guest Parking Rules draft.txt").write_text(RULES_A, encoding="utf-8")
    (box / "Guest Parking Rules final.txt").write_text(RULES_B, encoding="utf-8")
    (box / "Police Report 2099.txt").write_text("Incident 99-1: a car was broken into in the north lot.", encoding="utf-8")
    (box / "notes.txt").write_text("Bring folding chairs and the projector. Coffee for twelve.", encoding="utf-8")
    (box / "Old Fence Policy.txt").write_text("Fences are wood, no taller than six feet.", encoding="utf-8")
    # The library already holds one policy (the fence policy's bytes), filed under Policies.
    held = box / "Old Fence Policy.txt"
    lib = data / "library"
    (lib / "files" / "Governing Documents" / "Policies").mkdir(parents=True)
    (lib / "files" / "Governing Documents" / "Policies" / "Fence Policy.txt").write_bytes(held.read_bytes())
    with sqlite3.connect(lib / "library.db") as conn:
        conn.execute(library_task.SCHEMA)
        conn.execute("INSERT INTO documents VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                     ("1", "payhoa", "Governing Documents/Policies/Fence Policy.txt", "Fence Policy.txt", "policy",
                      "governing", "governing_documents", "NAME", "", 0, "rules", None, "", ingest.sha256_of(held)))
    # The known policy's current text is the 2099 version (its outline).
    (data / "outlines").mkdir(parents=True)
    (data / "outlines" / "pet-policy.json").write_text(json.dumps({"key": "pet-policy", "title": "Pet Policy",
                                                                   "kind": "policy", "text": POLICY_V2, "sections": []}),
                                                       encoding="utf-8")
    ocr = _FakeOcr()
    monkeypatch.setattr("jason.community.ocr.engines", lambda: (ocr,))
    return {"data": data, "box": box, "ocr": ocr, "community": _stub()}


def _by_name(result):
    return {i.name: i for i in result.items}


def test_a_dry_run_inventories_reads_classifies_versions_and_files_nothing(box):
    data = box["data"]
    result = ingest.run(box["community"], data, [str(box["box"])], today=ingest.date(2099, 3, 1))
    items = _by_name(result)

    # Inventory: every file hashed and dated; the copy is a duplicate; the library's own copy is noted.
    assert len(result.items) == 10
    assert items["Board Minutes 2099-02-14 copy.pdf"].duplicate_of == "Box/Board Minutes 2099-02-14.pdf"
    assert ("2099-02-14", "printed in the file's name") in items["Board Minutes 2099-02-14.pdf"].dates
    assert any(how == "file modified" for _, how in items["notes.txt"].dates)
    assert items["Old Fence Policy.txt"].library_path == "Governing Documents/Policies/Fence Policy.txt"
    assert items["Old Fence Policy.txt"].status == "in the library"

    # The scan had no text layer: OCR read it, and the phrase rules classified it.
    scan = items["scan-001.pdf"]
    assert box["ocr"].read == ["scan-001.pdf"]
    assert scan.text_source == "ocr: fake-ocr" and scan.kind == "minutes" and scan.method == "CONTENT"
    assert ("2099-01-10", "printed in the text") in scan.dates or scan.period.startswith("2099")

    # Versions: the 2099 policy is the known document's current text, the 2098 one a version not on record; the two
    # parking drafts no document claims are grouped.
    assert items["Pet Policy 2099.txt"].version["status"] == "current"
    old = items["Pet Policy 2098.txt"].version
    assert old["document"] == "pet-policy" and old["status"] == "not on record" and old["citable"]
    assert len(result.groups) == 1 and len(result.groups[0]["files"]) == 2

    # Filing: the book from book_entries, the record, and the folder where the library files the kind.
    assert items["Pet Policy 2098.txt"].book == "rules.pets"
    assert items["Pet Policy 2098.txt"].folder == "Governing Documents/Policies/"
    assert items["Board Minutes 2099-02-14.pdf"].folder == "Meetings/"           # pinned to its record
    assert items["Board Minutes 2099-02-14.pdf"].records == ("minutes",)

    # Questions: an unclassified file (CLASSIFY) and a kind no folder holds (MAP); listed, not parked.
    kinds = {(a.kind, a.detail["file"]) for a in result.asks}
    assert (AskKind.CLASSIFY, "Box/notes.txt") in kinds
    assert (AskKind.MAP, "Box/Police Report 2099.txt") in kinds
    classify = next(a for a in result.asks if a.kind is AskKind.CLASSIFY)
    assert any(e.startswith("begins: Bring folding chairs") for e in classify.evidence)
    assert intake.load(data) == []
    assert items["Police Report 2099.txt"].status == "held: no folder"

    # Nothing filed: the library is as it was; the report is written, and the checklist would move.
    assert not (data / "library" / "files" / "Meetings").exists()
    with sqlite3.connect(data / "library" / "library.db") as conn:
        assert conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0] == 1
    report = (data / "onboarding" / "ingest-2099-03-01.md").read_text(encoding="utf-8")
    assert "dry run" in report.lower() and "new version" in report
    assert any(m["key"] == "minutes" for m in result.moved)


def test_apply_files_the_ready_files_and_park_parks_the_questions(box):
    data = box["data"]
    result = ingest.run(box["community"], data, [str(box["box"])], apply_files=True, park=True,
                        today=ingest.date(2099, 3, 1))
    filed = {i.name for i in result.filed}
    assert {"Board Minutes 2099-02-14.pdf", "scan-001.pdf", "Pet Policy 2098.txt", "Pet Policy 2099.txt"} <= filed
    assert "Board Minutes 2099-02-14 copy.pdf" not in filed                       # the duplicate
    assert "Police Report 2099.txt" not in filed and "notes.txt" not in filed    # held for their questions
    assert "Old Fence Policy.txt" not in filed                                    # already in the library
    assert (data / "library" / "files" / "Meetings" / "scan-001.pdf").is_file()

    with sqlite3.connect(data / "library" / "library.db") as conn:
        rows = conn.execute("SELECT path, kind, method, sha256 FROM documents WHERE source = 'ingest'").fetchall()
        prov = conn.execute("SELECT origin, dates FROM ingested WHERE path = 'Meetings/scan-001.pdf'").fetchone()
    assert len(rows) == len(filed) and all(r[3] for r in rows)
    assert prov[0].endswith("scan-001.pdf") and json.loads(prov[1])
    scan = next(i for i in result.filed if i.name == "scan-001.pdf")
    assert "MINUTES OF THE REGULAR MEETING" in library_task.text_for(data, scan.library_doc_id)
    assert box["ocr"].read == ["scan-001.pdf"]                                    # read once, not again to file it

    # A library run rebuilds documents from the catalog and keeps the ingested rows.
    library_task.save(data, ())
    assert len(library_task.load(data)) == len(filed)

    # The questions are parked in the intake queue under the file's subject.
    queue = intake.load(data)
    assert {a.kind for a in queue} == {AskKind.CLASSIFY, AskKind.MAP}
    assert all(a.subject.startswith("ingest:") for a in queue)

    # The gate reads the last report.
    g = ingest.gate(data)
    assert g["mode"] == "applied" and g["filed"] == len(filed) and g["stillOpen"] == len(queue) and g["parked"]
    assert any("Ingest: last run 2099-03-01" in line for line in ingest.gate_lines(data))


def test_an_answered_map_question_files_the_file_on_the_next_run(box):
    data = box["data"]
    ingest.run(box["community"], data, [str(box["box"])], park=True, today=ingest.date(2099, 3, 1))
    asks = intake.load(data)
    ask = next(a for a in asks if a.kind is AskKind.MAP)
    intake.answer(asks, ask.id, "Legal/", "A. Person")
    intake.save(data, asks)
    again = ingest.run(box["community"], data, [str(box["box"])], today=ingest.date(2099, 3, 2))
    police = _by_name(again)["Police Report 2099.txt"]
    assert police.folder == "Legal/" and police.folder_how == "a person's answer" and police.status == "ready"


def test_the_model_is_asked_only_when_given_and_a_weak_answer_is_a_question(box):
    from jason.community.content import ModelAnswer

    class _Model:
        model = "fake"

        def __init__(self):
            self.asked = []

        def classify(self, name, text):
            self.asked.append(name)
            return ModelAnswer(K.CONTRACT, 0.6, "", "it lists supplies for a meeting")

    model = _Model()
    result = ingest.run(box["community"], box["data"], [str(box["box"])], model=model, today=ingest.date(2099, 3, 1))
    notes = _by_name(result)["notes.txt"]
    assert model.asked == ["notes.txt"]                       # only the file the rules and phrases missed
    assert notes.kind == "contract" and notes.method == "MODEL"
    ask = next(a for a in result.asks if a.kind is AskKind.CLASSIFY and a.detail["file"] == "Box/notes.txt")
    assert ask.suggestion == "contract" and any(e.startswith("model: contract at 0.60") for e in ask.evidence)
    assert notes.status.startswith("held")                    # filed only once a person confirms the kind


def test_a_packet_that_carries_a_document_is_a_copy_not_a_version(box):
    filler = " ".join(f"Line {n}: the reserve account balance and the insurance summary for the year." for n in range(60))
    (box["box"] / "Annual Disclosures 2099.txt").write_text(filler + " " + POLICY_V2 + " " + filler, encoding="utf-8")
    result = ingest.run(box["community"], box["data"], [str(box["box"])], today=ingest.date(2099, 3, 1))
    packet = _by_name(result)["Annual Disclosures 2099.txt"]
    assert packet.version["status"] == "carries a copy" and packet.version["share"] > 0.9
    assert not ingest.is_version(packet.version) and packet.book != "rules.pets"
    assert result.counts()["copies"] == 1


def test_no_gate_before_an_ingest(tmp_path):
    assert ingest.gate(tmp_path) is None
    assert ingest.gate_lines(tmp_path) == ["Ingest: nothing taken in yet (jason ingest SOURCE)"]


def test_a_zip_is_staged_and_a_drive_source_needs_a_client(box, tmp_path):
    import zipfile

    archive = tmp_path / "handover.zip"
    with zipfile.ZipFile(archive, "w") as z:
        z.write(box["box"] / "Pet Policy 2099.txt", "Policies/Pet Policy 2099.txt")
        z.writestr("../escape.txt", "outside")
    items, notes = ingest.inventory([archive], box["data"])
    assert [i.rel for i in items] == ["handover/Policies/Pet Policy 2099.txt"]
    assert any(how == "zip entry time" for _, how in items[0].dates)
    assert any("outside the archive" in n for n in notes)
    assert ingest.drive_folder_id("https://drive.google.com/drive/folders/1AbCdEfGhIjK?usp=sharing") == "1AbCdEfGhIjK"
    with pytest.raises(ValueError):
        ingest.inventory(["drive:1AbCdEfGhIjK"], box["data"])
