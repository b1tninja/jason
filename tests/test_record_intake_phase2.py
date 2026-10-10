"""Record intake, phase 2: the Drive chooser's backend and the reading back after a pick.

A fake Drive (read methods only: any write call is recorded and fails the test), a fake association, made-up PDFs, and a
data folder of its own. Nothing here reaches Google, Keeper, PayHOA, or a county."""

import json
import logging
import sqlite3
from types import SimpleNamespace

import pytest

import webclient
from jason.community.record_slots import PinKind, SlotState
from jason.community.symbols import DocumentKind
from jason.google.errors import GoogleAuthRequired, GoogleHttpError
from jason.tasks import drive_choose as dc
from jason.tasks import record_acts as acts
from jason.tasks import record_readback as rb
from jason.tasks import record_slots as rs

KD = DocumentKind
BY = "Jane Example"
FILE_A = "1MinutesFileAbCdEfGhIj"
FILE_B = "1BylawsFileZyXwVuTsRq"
FILE_C = "1CombinedScanQpOnMlKj"
FILE_DOC = "1GoogleDocAbCdEfGhIjKl"
FILE_SHEET = "1SheetFileAbCdEfGhIjKl"
FILE_HELD = "1HeldFileAbCdEfGhIjKlMn"
FOLDER = "1RecordsFolderAbCdEfGh"
SUB = "1SubFolderAbCdEfGhIjKl"
DRIVE_ID = "0SharedDriveAbCdEfGhIj"
TOKEN = "tok-SECRET-0123456789"
NAME_A = "Secret Board Minutes 2099-06.pdf"
NAME_B = "Secret Bylaws 2099.pdf"
NAME_C = "Secret Combined Scan.pdf"


def make_pdf(pages):
    pymupdf = pytest.importorskip("pymupdf")
    doc = pymupdf.open()
    for text in pages:
        page = doc.new_page()
        page.insert_textbox(pymupdf.Rect(40, 40, 560, 780), text, fontsize=9)
    data = doc.tobytes()
    doc.close()
    return data


FILLER = " The association keeps this record in its files for the members to inspect." * 8
MINUTES = "Minutes of the board meeting held on June 3, 2099. Called to order at 7:00 pm. Motion carried." + FILLER
BYLAWS = "Bylaws of Example Village Homeowners Association. Article I. Name and offices." + FILLER


class FakeDrive:
    """The read methods of GoogleDrive, over a dict of files. Any other call is a write: it is recorded and refused."""

    def __init__(self, files, drives=()):
        self.files = files
        self.drives = list(drives)
        self.calls = []
        self.writes = []
        self.downloads = 0
        self.exports = 0
        self.closed = False
        self._token = TOKEN

    @staticmethod
    def meta(ident, name, mime="application/pdf", size=None, parents=("root",), modified="2099-09-30T10:00:00Z", **extra):
        return {"id": ident, "name": name, "mimeType": mime, "size": None if size is None else str(size), "modifiedTime": modified,
                "parents": list(parents), "owners": [{"displayName": "Pat Owner", "emailAddress": "pat@example.org"}],
                "capabilities": {"canDownload": True, "canListChildren": True}, **extra}

    def file_metadata(self, file_id, fields):
        self.calls.append("file_metadata")
        if file_id not in self.files:
            raise GoogleHttpError(f"HTTP 404 reading {file_id}'s metadata", status=404, reason="notFound")
        return dict(self.files[file_id]["meta"])

    def list_page(self, query, *, page_token="", page_size=50, fields="", drive_id="", order_by=""):
        self.calls.append("list_page")
        self.last = {"query": query, "page_size": page_size, "token": page_token, "drive_id": drive_id}
        if "in parents" in query:
            parent = query.split("'")[1]
            rows = [f["meta"] for f in self.files.values() if parent in f["meta"].get("parents", [])]
        else:
            needle = query.split("contains '")[1].split("' and")[0].replace("\\'", "'").casefold()
            rows = [f["meta"] for f in self.files.values() if needle in f["meta"]["name"].casefold()]
        start = int(page_token or 0)
        page = rows[start:start + page_size]
        more = str(start + page_size) if start + page_size < len(rows) else ""
        return [dict(r) for r in page], more

    def list_shared_drives(self, **kw):
        self.calls.append("list_shared_drives")
        return list(self.drives)

    def about_user(self):
        self.calls.append("about_user")
        return {"displayName": "jason", "emailAddress": "jason@example.org"}

    def download_bytes(self, file_id):
        self.calls.append("download_bytes")
        self.downloads += 1
        return self.files[file_id]["data"]

    def export_file(self, file_id, mime_type):
        self.calls.append("export_file")
        self.exports += 1
        return self.files[file_id]["data"]

    def close(self):
        self.closed = True

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        self.writes.append(name)

        def refuse(*a, **kw):
            raise AssertionError(f"jason called a Drive write: {name}")
        return refuse


class _Community:
    """A made-up association: kind rules by file name, no pins, no folders."""

    org_id = 7
    slug = "example"
    ccrs = None

    def __init__(self, rules=()):
        self._rules = rules

    def record_slots(self):
        return self._rules

    def classify_document(self, name, folder=None, path=""):
        low = str(name).lower()
        for word, kind in (("minutes", KD.MINUTES), ("bylaws", KD.BYLAWS), ("operating", KD.OPERATING_RULES), ("policy", KD.POLICY)):
            if word in low:
                return kind
        return None

    def pins(self):
        return ()

    def supersessions(self):
        return ()

    def public_reports(self):
        return ()

    def developer_file(self):
        return {}

    def known_files(self):
        return ()

    def library_folders(self):
        return ()

    @property
    def sync_rules(self):
        return ()


@pytest.fixture
def world(tmp_path, monkeypatch):
    from jason.community import community
    from jason.tasks.library import SCHEMA

    community()          # the profile reads its made-up private facts under the fixtures before this test changes the folder
    root = tmp_path / "data"
    (root / "library" / "text").mkdir(parents=True)
    with sqlite3.connect(root / "library" / "library.db") as conn:
        conn.execute(SCHEMA)
        conn.execute("INSERT INTO documents (id, source, path, name, kind, category, records, method, period, confidential, evidence)"
                     " VALUES ('9001','payhoa','Confidential/Held Statement.pdf','Held Statement.pdf','bank_statement','financial',"
                     "'enhanced','NAME','2099-06',1,'')")
    spec = tmp_path / "spec"
    spec.mkdir()
    monkeypatch.setenv("JASON_SPEC_DIR", str(spec))
    monkeypatch.setattr("jason.mcp.county._data_dir", lambda given=None: root)
    monkeypatch.setattr(rs, "_profile", lambda profile, community=None: profile or "example")
    community_ = _Community()
    files = {
        FILE_A: {"meta": FakeDrive.meta(FILE_A, NAME_A, size=0), "data": make_pdf([MINUTES])},
        FILE_B: {"meta": FakeDrive.meta(FILE_B, NAME_B, size=0), "data": make_pdf([BYLAWS])},
        FILE_C: {"meta": FakeDrive.meta(FILE_C, NAME_C, size=0), "data": make_pdf([BYLAWS, MINUTES, "Operating rules page." + FILLER])},
        FILE_DOC: {"meta": FakeDrive.meta(FILE_DOC, "Agenda Doc", mime="application/vnd.google-apps.document"), "data": b"PK-docx-bytes"},
        FILE_SHEET: {"meta": FakeDrive.meta(FILE_SHEET, "Roster Sheet", mime="application/vnd.google-apps.spreadsheet"), "data": b""},
        FILE_HELD: {"meta": FakeDrive.meta(FILE_HELD, "Held Statement.pdf", size=10), "data": b""},
        SUB: {"meta": FakeDrive.meta(SUB, "Amendments", mime="application/vnd.google-apps.folder", parents=(FOLDER,)), "data": b""},
        FOLDER: {"meta": FakeDrive.meta(FOLDER, "Records", mime="application/vnd.google-apps.folder"), "data": b""},
    }
    for ident in (FILE_A, FILE_B, FILE_C):
        files[ident]["meta"]["size"] = str(len(files[ident]["data"]))
        files[ident]["meta"]["parents"] = [FOLDER]
    drive = FakeDrive(files, drives=[{"id": DRIVE_ID, "name": "Board Drive"}])
    return SimpleNamespace(root=root, spec=spec, community=community_, drive=drive, tmp=tmp_path)


def quiet_preflight(path, root):
    return {"pages": 1, "blank": 0, "marked": 0, "content": 1, "withText": 1, "suspectShare": None, "locked": False, "recommend": []}


def fake_segments(parts):
    """A segmenter that returns the given (start, end, kind, tier) top-level documents; the rule pass itself is tested apart."""
    from jason.community.document_segments import Reader, Tier

    def run(path, **kw):
        segs = [SimpleNamespace(key=f"s{i}", start=a, end=b, title=f"Part {i}", kind=k, date="", parent="",
                                tier=Tier.LIKELY if t == "likely" else Tier.SUGGESTED, readers=(Reader.RULES,))
                for i, (a, b, k, t) in enumerate(parts, 1)]
        return SimpleNamespace(segments=segs, parts=[], page_count=parts[-1][1], readers={"rules": "1"})
    return run


def read(world, slot="records/5200/minutes", *, dry=True, **kw):
    kw.setdefault("preflighter", quiet_preflight)
    return rb.read(slot, by=BY, dry_run=dry, drive=world.drive, community=world.community, root=world.root, profile="example", **kw)


def pick(world, slot, ident, **kw):
    return rs.pick(slot, ident, by=BY, dry_run=False, community=world.community, root=world.root, profile="example", **kw)


def store(world):
    return json.loads((world.spec / "example" / "records.json").read_text(encoding="utf-8"))


def slot_row(world, key, **kw):
    return rs.slot_view(key, world.community, world.root, "example", private=True, **kw)


# --- the chooser's reads ----------------------------------------------------------------------------------------------------------

def test_the_root_listing_gives_a_chooser_what_it_needs_and_nothing_more(world):
    out = dc.list_folder(world.drive, community=world.community, root=world.root, profile="example")
    assert out["found"] and out["driveConnected"] and out["account"] == "jason@example.org"
    assert out["drives"] == [{"name": "Board Drive", "id": DRIVE_ID, "type": "drive"}]
    assert out["parent"]["name"] == "My Drive"
    names = {i["name"] for i in out["items"]}
    assert {"Records", "Agenda Doc", "Roster Sheet"} <= names
    folder = next(i for i in out["items"] if i["name"] == "Records")
    assert folder["type"] == "folder" and folder["readable"] and folder["children"] is None
    doc = next(i for i in out["items"] if i["name"] == "Agenda Doc")
    assert doc["type"] == "doc" and "Word copy" in doc["doc"] and doc["owner"] == "Pat Owner" and doc["sharedDrive"] is False
    assert set(doc) >= {"id", "name", "type", "mime", "size", "modified", "parents", "owner", "sharedDrive", "readable", "why", "held", "jason"}
    assert doc["modified"] == "2099-09-30"
    sheet = next(i for i in out["items"] if i["name"] == "Roster Sheet")
    assert sheet["readable"] is False and "no document for jason to read" in sheet["why"]
    assert "emailAddress" not in json.dumps(out["items"])          # the owner's address is not in a listing


def test_a_folder_is_listed_a_page_at_a_time_with_a_capped_page_and_a_breadcrumb(world):
    out = dc.list_folder(world.drive, folder=FOLDER, page_size=2, community=world.community, root=world.root, profile="example")
    assert len(out["items"]) == 2 and out["next"] == "2" and world.drive.last["page_size"] == 2
    assert [p["name"] for p in out["parent"]["path"]][-1] == "Records"
    more = dc.list_folder(world.drive, folder=FOLDER, page_size=2, page_token=out["next"], community=world.community,
                          root=world.root, profile="example")
    assert len(more["items"]) == 2 and more["next"] is None
    dc.list_folder(world.drive, folder=FOLDER, page_size=5000, community=world.community, root=world.root, profile="example")
    assert world.drive.last["page_size"] == dc.MAX_PAGE
    by_link = dc.list_folder(world.drive, folder=f"https://drive.google.com/drive/folders/{FOLDER}", community=world.community,
                             root=world.root, profile="example")
    assert by_link["found"] and len(by_link["items"]) == 4
    empty = dc.list_folder(world.drive, folder=SUB, community=world.community, root=world.root, profile="example")
    assert empty["found"] and empty["items"] == [] and empty["empty"] == "This folder is empty."
    bad = dc.list_folder(world.drive, folder="https://example.com/x", community=world.community, root=world.root, profile="example")
    assert bad["found"] is False and "not a Drive link" in bad["why"]


def test_search_sends_the_text_to_google_escaped_and_pages(world):
    out = dc.search(world.drive, "minutes", community=world.community, root=world.root, profile="example")
    assert out["found"] and [i["name"] for i in out["items"]] == [NAME_A]
    assert "name contains 'minutes'" in world.drive.last["query"]
    dc.search(world.drive, "o'brien", community=world.community, root=world.root, profile="example")
    assert "o\\'brien" in world.drive.last["query"]            # a quote cannot break out of the query
    assert dc.search(world.drive, "a", community=world.community, root=world.root, profile="example")["found"] is False
    assert dc.search(world.drive, "x" * 101, community=world.community, root=world.root, profile="example")["found"] is False
    none = dc.search(world.drive, "nothing like it", community=world.community, root=world.root, profile="example")
    assert none["found"] and none["items"] == [] and "not listed" in none["empty"]


def test_resolve_names_a_file_a_folder_and_what_it_cannot_open(world):
    ok = dc.resolve(world.drive, f"https://drive.google.com/file/d/{FILE_A}/view?usp=sharing", community=world.community,
                    root=world.root, profile="example")
    assert ok["found"] and ok["kind"] == "file" and ok["name"] == NAME_A and ok["type"] == "pdf" and ok["readable"]
    assert ok["ownerDomain"] == "example.org" and ok["modified"] == "2099-09-30" and ok["size"] == len(world.drive.files[FILE_A]["data"])
    folder = dc.resolve(world.drive, FOLDER, community=world.community, root=world.root, profile="example")
    assert folder["kind"] == "folder" and "Choose this folder" in folder["offer"]
    missing = dc.resolve(world.drive, "1NoSuchFileAbCdEfGhIj", community=world.community, root=world.root, profile="example")
    assert missing["found"] is False and "Share it with the account" in missing["why"] and "1NoSuchFile" not in missing["why"]
    notdrive = dc.resolve(world.drive, "https://example.com/file", community=world.community, root=world.root, profile="example")
    assert notdrive["found"] is False and "not a Drive link" in notdrive["why"]


def test_a_confidential_file_is_named_by_its_kind_and_carries_no_id_outside_the_private_view(world):
    world.drive.files[FILE_HELD]["meta"]["parents"] = [FOLDER]
    held = dc.list_folder(world.drive, folder=FOLDER, community=world.community, root=world.root, profile="example")
    row = next(i for i in held["items"] if i["held"])
    assert row["name"] == "a confidential file (kind: bank statement)" and row["id"] == "" and row["parents"] == []
    assert row["opens"] == "opens in the private view" and "Held Statement" not in json.dumps(held)
    assert FILE_HELD not in json.dumps(held)
    shown = dc.list_folder(world.drive, folder=FOLDER, community=world.community, root=world.root, profile="example", private=True)
    row = next(i for i in shown["items"] if i["held"])
    assert row["name"] == "Held Statement.pdf" and row["id"] == FILE_HELD
    one = dc.resolve(world.drive, FILE_HELD, community=world.community, root=world.root, profile="example")
    assert one["name"].startswith("a confidential file") and one["id"] == "" and one["ownerDomain"] == ""


def test_what_jason_knows_of_a_file_is_shown_beside_it(world):
    pick(world, "records/5200/minutes", FILE_A, period="2099-06")
    out = dc.list_folder(world.drive, folder=FOLDER, community=world.community, root=world.root, profile="example")
    row = next(i for i in out["items"] if i["name"] == NAME_A)
    assert row["jason"]["pinnedFor"] == ["records/5200/minutes"] and row["jason"]["kind"] == "minutes"


def test_a_drive_that_refuses_is_told_without_the_exception_text(world, caplog):
    class Limited(FakeDrive):
        def list_page(self, *a, **kw):
            raise GoogleHttpError(f"HTTP 429 listing {FOLDER}", status=429, reason="rateLimitExceeded")

    caplog.set_level(logging.DEBUG)
    out = dc.list_folder(Limited({}), folder=FOLDER, community=world.community, root=world.root, profile="example")
    assert out["found"] is False and "limiting" in out["why"] and "Nothing was picked" in out["why"]
    assert FOLDER not in out["why"] and FOLDER not in caplog.text


# --- not connected: fail fast, no browser -----------------------------------------------------------------------------------------

def test_a_missing_sign_in_fails_fast_with_words_a_console_can_show_and_never_opens_a_browser():
    seen = {}

    class Agent:
        def drive(self, *, interactive=False):
            seen["interactive"] = interactive
            raise GoogleAuthRequired("no human is present")

    with pytest.raises(dc.DriveUnavailable) as caught:
        dc.open_client(Agent())
    assert seen == {"interactive": False}
    assert "no Google sign-in" in str(caught.value) and caught.value.command.startswith("jason google sign-in")
    shown = dc.unavailable_answer(caught.value)
    assert shown["found"] is False and shown["driveConnected"] is False and shown["command"]

    from jason.secrets import KeeperAuthRequired

    class Vault:
        def drive(self, *, interactive=False):
            raise KeeperAuthRequired("password needed")

    with pytest.raises(dc.DriveUnavailable) as vault:
        dc.open_client(Vault())
    assert vault.value.command == "jason login"


# --- the read-back ------------------------------------------------------------------------------------------------------------

def test_a_dry_run_lists_what_it_would_fetch_and_the_size_and_fetches_nothing(world):
    pick(world, "records/5200/minutes", FILE_A, period="2099-06")
    out = read(world)
    r = out["reads"][0]
    assert out["dryRun"] and out["ok"] and r["plan"]["willFetch"] is True and r["plan"]["size"] == len(world.drive.files[FILE_A]["data"])
    assert r["plan"]["name"] == NAME_A and "Add --yes" in out["note"]
    assert world.drive.downloads == 0 and world.drive.exports == 0 and world.drive.writes == []
    assert not (world.root / "record-intake").exists()             # nothing was staged, read, or recorded
    history = world.root / "records" / "history.jsonl"
    assert '"act": "read"' not in (history.read_text(encoding="utf-8") if history.exists() else "")


def test_yes_fetches_once_reads_the_file_and_keeps_the_reading_beside_the_pin(world):
    made = pick(world, "records/5200/minutes", FILE_A, period="2099-06")
    out = read(world, dry=False)
    r = out["reads"][0]
    assert out["ok"] and r["fetched"] is True and world.drive.downloads == 1 and world.drive.writes == []
    assert r["picked"] == {"for": "Minutes of member, board, and committee meetings", "file": NAME_A}
    assert r["readAs"]["kind"] == "minutes" and r["readAs"]["tier"] == "likely"
    assert r["readAs"]["readers"] == {"name rule": "minutes", "phrase rule": "minutes"}
    assert r["compare"]["verdict"] == "agrees" and r["compare"]["wrongSlot"] is None
    assert r["preflight"]["pages"] == 1 and r["segments"]["proposes"] is False
    kept = rb.load(world.root, "example", made["pin"])
    assert kept["sha256"] and kept["kind"] == "minutes" and kept["text"]["chars"] > 100 and kept["libraryId"] == ""
    staged = list((world.root / "record-intake" / "example" / "fetched").glob("*/*"))
    assert len(staged) == 1 and staged[0].read_bytes() == world.drive.files[FILE_A]["data"]
    view = slot_row(world, "records/5200/minutes")
    holder = view["holders"][0]
    assert holder["state"] == "read" and holder["readback"]["tier"] == "likely" and holder["readback"]["readers"]["name rule"] == "minutes"
    assert view["acts"]["read"] is True
    # not filed into the library, and the original in Drive was not written
    assert not any(r_["name"] == NAME_A for r_ in rs.Library(world.root).rows)


def test_a_second_read_is_idempotent_by_hash_and_does_not_ask_drive_for_the_bytes_again(world):
    pick(world, "records/5200/minutes", FILE_A, period="2099-06")
    read(world, dry=False)
    again = read(world, dry=False)
    assert again["reads"][0]["unchanged"] is True and again["reads"][0]["fetched"] is False and world.drive.downloads == 1
    plan = read(world)["reads"][0]["plan"]
    assert plan["willFetch"] is False
    forced = read(world, dry=False, force=True)
    assert forced["reads"][0]["fetched"] is True and world.drive.downloads == 2          # asked again, by request
    assert len(list((world.root / "record-intake" / "example" / "fetched").glob("*/*"))) == 1       # the same bytes are one copy
    assert forced["reads"][0]["changed"] is None


def test_a_changed_file_marks_the_pin_changed_and_shows_a_diff_of_facts_not_text(world):
    made = pick(world, "records/5200/minutes", FILE_A, period="2099-06")
    read(world, dry=False)
    world.drive.files[FILE_A]["data"] = make_pdf([MINUTES, MINUTES])
    world.drive.files[FILE_A]["meta"]["modifiedTime"] = "2099-10-02T10:00:00Z"
    world.drive.files[FILE_A]["meta"]["size"] = str(len(world.drive.files[FILE_A]["data"]))
    out = read(world, dry=False, preflighter=lambda p, r: {**quiet_preflight(p, r), "pages": 2})
    r = out["reads"][0]
    assert r["fetched"] is True and world.drive.downloads == 2
    diff = {d["fact"] for d in r["changed"]["diff"]}
    assert {"size", "pages"} <= diff
    assert all(isinstance(d["before"], (int, type(None), str)) for d in r["changed"]["diff"])
    holder = slot_row(world, "records/5200/minutes")["holders"][0]
    assert holder["changed"]["diff"] and holder["readback"]["history"] and len(holder["readback"]["history"]) == 2
    assert "Called to order" not in json.dumps(holder["changed"])         # the change is facts, never the file's words
    assert rb.load(world.root, "example", made["pin"])["lastChange"]["to"] != rb.load(world.root, "example", made["pin"])["lastChange"]["from"]


def test_a_google_doc_is_exported_as_a_word_file_and_the_doc_stays_the_original(world):
    pick(world, "records/5200/minutes", FILE_DOC, period="2099-06")
    out = read(world, dry=False)
    assert world.drive.exports == 1 and world.drive.downloads == 0 and world.drive.writes == []
    assert out["ok"] and any(f["code"] == "exported" for f in out["reads"][0]["found"])
    assert list((world.root / "record-intake" / "example" / "fetched").glob("*/*.docx"))
    plan = read(world, force=True)["reads"][0]["plan"]
    assert "Word copy" in plan["export"]


def test_a_type_with_no_document_and_a_folder_are_not_fetched(world):
    pick(world, "records/5200/minutes", FILE_SHEET, period="2099-06")
    out = read(world, dry=False)
    assert out["ok"] is False and "no document" in out["reads"][0]["problem"] and world.drive.downloads == 0


def test_a_file_drive_cannot_open_is_a_problem_in_words_and_nothing_is_written(world):
    pick(world, "records/5200/minutes", "1GoneFileAbCdEfGhIjKlMn", period="2099-06")
    out = read(world, dry=False)
    assert out["ok"] is False and "Share it with the account" in out["reads"][0]["problem"]
    assert not (world.root / "record-intake").exists()


def test_a_read_without_a_drive_client_refuses_before_fetching(world):
    pick(world, "records/5200/minutes", FILE_A, period="2099-06")
    with pytest.raises(dc.DriveUnavailable):
        rb.read("records/5200/minutes", by=BY, dry_run=False, drive=None, community=world.community, root=world.root, profile="example")


def test_a_wrong_slot_pick_is_surfaced_never_silently_accepted(world):
    pick(world, "records/5200/minutes", FILE_B, period="2099-06")
    out = read(world, dry=False)
    r = out["reads"][0]
    assert r["compare"]["verdict"] == "differs" and r["compare"]["wrongSlot"]["readsAs"] == "bylaws"
    assert {"key": "governing/bylaws", "title": "The association's bylaws"} in r["compare"]["wrongSlot"]["fits"] or \
        "governing/bylaws" in [f["key"] for f in r["compare"]["wrongSlot"]["fits"]]
    assert any(f["code"] == "wrong slot" for f in r["found"]) and "keep it in this slot" in r["confirm"]
    view = slot_row(world, "records/5200/minutes")
    assert view["state"] == "problem" and view["holders"][0]["wrongSlot"]["acts"] == ["repin", "keep", "unpin"]
    assert slot_row(world, "governing/bylaws")["state"] == "empty"             # the slot it fits is not filled by jason
    queued = rb.queue_items(world.community, world.root, "example", private=True)
    assert queued["counts"]["wrongSlot"] == 1 and queued["items"][0]["kind"] == "record reading"
    assert queued["items"][0]["acts"] == ["keep", "repin", "unpin"] and queued["items"][0]["fits"]


def test_a_combined_scan_proposes_several_slots_and_fills_none(world):
    pick(world, "governing/bylaws", FILE_C)
    parts = [(1, 1, "bylaws", "likely"), (2, 2, "minutes", "suggested"), (3, 3, "operating_rules", "suggested")]
    out = read(world, slot="governing/bylaws", dry=False, segmenter=fake_segments(parts))
    seg = out["reads"][0]["segments"]
    assert seg["proposes"] is True and [p["kind"] for p in seg["proposal"]] == ["bylaws", "minutes", "operating_rules"]
    keys = {x["key"] for p in seg["proposal"] for x in p["slots"]}
    assert {"governing/bylaws", "records/5200/minutes", "governing/operating-rules"} <= keys
    assert all(p["confirmed"] is False for p in seg["proposal"])
    assert next(p for p in seg["proposal"] if p["kind"] == "bylaws")["slots"][0]["current"] is True
    # nothing was pinned for another slot: the pins on disk are what the person picked, and the other slots stay empty
    assert slot_row(world, "records/5200/minutes")["state"] == "empty" and slot_row(world, "governing/operating-rules")["state"] == "empty"
    assert not (world.spec / "example" / "records.json").exists()                  # the split pinned nothing anywhere
    from jason.tasks import key_documents as kd

    assert list(kd.KeyDocumentStore(world.root, "example").load()["entries"]) == ["bylaws"]       # only the person's own pick
    assert any(f["code"] == "combined scan" for f in out["reads"][0]["found"])
    items = rb.queue_items(world.community, world.root, "example", private=True)["items"]
    assert any(i["reason"] == "combined scan" for i in items)


def test_the_real_preflight_and_segment_passes_read_a_small_pdf(world):
    path = world.tmp / "small.pdf"
    path.write_bytes(make_pdf([BYLAWS, MINUTES]))
    facts = rb.preflight_facts(path, world.root, text_quality=False)
    assert facts["pages"] == 2 and facts["withText"] == 2 and facts["locked"] is False and facts["blank"] == 0
    seg = rb.segments_facts(path, world.root, world.community, None, rs.assemble(world.community).slots, set(), "governing/bylaws")
    assert seg["pageCount"] == 2 and seg["note"].startswith("A proposal only") and "readers" in seg
    assert (world.root / "library" / "segments").is_dir()


def test_a_read_is_a_signed_act_and_records_no_file_name_in_the_history(world):
    pick(world, "records/5200/minutes", FILE_A, period="2099-06")
    with pytest.raises(ValueError, match="who"):
        rb.read("records/5200/minutes", by="", dry_run=False, drive=world.drive, community=world.community, root=world.root, profile="example")
    read(world, dry=False)
    history = (world.root / "records" / "history.jsonl").read_text(encoding="utf-8")
    row = json.loads(history.strip().splitlines()[-1])
    assert row["act"] == "read" and row["by"] == BY and row["verdict"] == "agrees"
    assert NAME_A not in history and FILE_A not in history


# --- keep, repin, more, reopen, bind ----------------------------------------------------------------------------------------------

def _wrong(world):
    made = pick(world, "records/5200/minutes", FILE_B, period="2099-06")
    read(world, dry=False)
    return made["pin"]


def test_keep_needs_a_reason_and_a_pick_jason_doubts_and_writes_only_the_record_and_history(world):
    pin = _wrong(world)
    with pytest.raises(ValueError, match="reason"):
        acts.keep("records/5200/minutes", by=BY, reason="", dry_run=False, community=world.community, root=world.root, profile="example")
    with pytest.raises(ValueError, match="nothing to keep"):
        acts.keep("governing/bylaws", by=BY, reason="it is right", dry_run=False, community=world.community, root=world.root, profile="example")
    before = (world.spec / "example" / "records.json").read_text(encoding="utf-8")
    dry = acts.keep("records/5200/minutes", reason="These are the bylaws our minutes adopt", by=BY, community=world.community,
                    root=world.root, profile="example")
    assert dry["dryRun"] and (world.spec / "example" / "records.json").read_text(encoding="utf-8") == before
    out = acts.keep("records/5200/minutes", reason="These are the bylaws our minutes adopt", by=BY, dry_run=False,
                    community=world.community, root=world.root, profile="example")
    assert out["pin"] == pin and out["written"] == "spec/example/records.json"
    data = store(world)
    assert data["keeps"][0]["by"] == BY and data["keeps"][0]["pin"] == pin and len(data["pins"]) == 1 and not data["pins"][0]["unpinned"]
    view = slot_row(world, "records/5200/minutes")
    assert view["state"] == "read" and view["holders"][0]["kept"]["reason"].startswith("These are")
    assert view["holders"][0]["readback"]["readsAs"] == "bylaws"                  # jason still says what it read
    assert rb.queue_items(world.community, world.root, "example", private=True)["counts"]["wrongSlot"] == 0
    assert (world.root / "records" / "history.jsonl").read_text(encoding="utf-8").count('"act": "keep"') == 1
    assert "bylaws our minutes" not in (world.root / "records" / "history.jsonl").read_text(encoding="utf-8")


def test_repin_moves_the_pick_and_its_reading_to_the_slot_it_fits(world):
    pin = _wrong(world)
    before = (world.spec / "example" / "records.json").read_text(encoding="utf-8")
    dry = acts.repin("records/5200/minutes", to="governing/bylaws", by=BY, community=world.community, root=world.root, profile="example")
    assert dry["dryRun"] and (world.spec / "example" / "records.json").read_text(encoding="utf-8") == before
    with pytest.raises(ValueError, match="another slot"):
        acts.repin("records/5200/minutes", to="records/5200/minutes", by=BY, dry_run=False, community=world.community, root=world.root)
    out = acts.repin("records/5200/minutes", to="governing/bylaws", by=BY, dry_run=False, community=world.community, root=world.root,
                     profile="example")
    assert out["to"] == "governing/bylaws" and out["readingMoved"] is True and out["unpinned"] == pin
    assert slot_row(world, "records/5200/minutes")["state"] == "empty"
    moved = slot_row(world, "governing/bylaws")
    assert moved["state"] == "read" and moved["holders"][0]["readback"]["readsAs"] == "bylaws"      # the recorded instrument's slot: a key-documents link
    assert moved["holders"][0]["source"] == "key-documents"
    kinds = [json.loads(line)["act"] for line in (world.root / "records" / "history.jsonl").read_text(encoding="utf-8").splitlines()]
    assert kinds.count("repin") == 1 and "unpin" in kinds
    assert world.drive.writes == []


def test_more_is_a_signed_answer_for_a_set_and_only_for_a_set(world):
    slot = "governing/policies-resolutions"
    with pytest.raises(ValueError, match="not a set that grows"):
        acts.more("records/5200/minutes", "no", by=BY, dry_run=False, community=world.community, root=world.root)
    with pytest.raises(ValueError, match="yes"):
        acts.more(slot, "maybe", by=BY, dry_run=False, community=world.community, root=world.root)
    dry = acts.more(slot, "no", by=BY, community=world.community, root=world.root, profile="example")
    assert dry["dryRun"] and not (world.spec / "example" / "records.json").exists()
    acts.more(slot, "no", by=BY, dry_run=False, community=world.community, root=world.root, profile="example")
    view = slot_row(world, slot)
    assert view["more"]["complete"] is True and view["more"]["by"] == BY and view["closed"] is True
    row = next(r for g in rs.view(world.community, world.root, "example")["groups"] for r in g["slots"] if r["key"] == slot)
    assert row["closed"] is True and row["state"] == "empty"                          # saying "this is all" is not a file
    with pytest.raises(ValueError, match="who"):
        acts.more(slot, "yes", by="", dry_run=False, community=world.community, root=world.root)


def test_reopen_takes_back_an_answer_and_a_closed_set_and_keeps_them_in_the_trail(world):
    rs.answer("records/5200/tax_return", "none", by=BY, reason="looked in the files", dry_run=False, community=world.community,
              root=world.root, profile="example")
    assert slot_row(world, "records/5200/tax_return")["state"] == "doesNotExist"
    with pytest.raises(ValueError, match="no answer to reopen"):
        acts.reopen("records/5200/minutes", by=BY, dry_run=False, community=world.community, root=world.root)
    assert acts.reopen("records/5200/tax_return", by=BY, community=world.community, root=world.root, profile="example")["dryRun"]
    assert slot_row(world, "records/5200/tax_return")["state"] == "doesNotExist"
    acts.reopen("records/5200/tax_return", by=BY, note="found a return", dry_run=False, community=world.community, root=world.root, profile="example")
    assert slot_row(world, "records/5200/tax_return")["state"] == "empty"
    answers = store(world)["answers"]
    assert answers[0]["reopened"]["by"] == BY and answers[0]["reason"] == "looked in the files"        # the answer stays
    slot = "governing/policies-resolutions"
    acts.more(slot, "no", by=BY, dry_run=False, community=world.community, root=world.root, profile="example")
    acts.reopen(slot, by=BY, dry_run=False, community=world.community, root=world.root, profile="example")
    assert slot_row(world, slot)["more"] is None and store(world)["more"][0]["reopened"]["by"] == BY


def test_reopening_a_recorded_instruments_none_exists_goes_through_the_key_documents_writer(world):
    rs.answer("governing/bylaws", "none", by=BY, reason="not in the files", dry_run=False, community=world.community, root=world.root,
              profile="example")
    assert slot_row(world, "governing/bylaws")["state"] == "doesNotExist"
    out = acts.reopen("governing/bylaws", by=BY, dry_run=False, community=world.community, root=world.root, profile="example")
    assert out["written"] == "key-documents/example.json" and slot_row(world, "governing/bylaws")["state"] == "empty"


def test_bind_names_a_folder_for_a_slot_and_proposes_a_sync_rule_without_editing_anything(world):
    dry = acts.bind("records/5200/minutes", FOLDER, by=BY, drive=world.drive, community=world.community, root=world.root, profile="example")
    assert dry["dryRun"] and dry["would"]["folder"] == "Records" and "SyncRule(" in dry["proposal"]["text"]
    assert "AssociationRecord.MINUTES" in dry["proposal"]["text"] and "<choose>" in dry["proposal"]["text"]
    assert not (world.spec / "example" / "records.json").exists()
    out = acts.bind("records/5200/minutes", f"https://drive.google.com/drive/folders/{FOLDER}", by=BY, drive=world.drive, dry_run=False,
                    community=world.community, root=world.root, profile="example")
    assert out["written"] == "spec/example/records.json" and "SyncRule(" in out["proposal"]["text"]
    assert store(world)["bindings"][0]["name"] == "Records" and store(world)["pins"] == []          # a binding is not a pin
    view = slot_row(world, "records/5200/minutes")
    assert view["bindings"][0]["name"] == "Records" and view["acts"]["pickFolder"] is True and view["state"] == "empty"
    again = acts.bind("records/5200/minutes", FOLDER, by=BY, drive=world.drive, dry_run=False, community=world.community, root=world.root,
                      profile="example")
    assert again["already"] is True and len(store(world)["bindings"]) == 1
    with pytest.raises(ValueError, match="file, not a folder"):
        acts.bind("records/5200/minutes", FILE_A, by=BY, drive=world.drive, dry_run=False, community=world.community, root=world.root)
    with pytest.raises(ValueError, match="who"):
        acts.bind("records/5200/minutes", FOLDER, by="", dry_run=False, community=world.community, root=world.root)
    from jason.community.record_slots import Slot

    assert dc.propose_sync_rule(Slot("local/thing", "A local thing", "maintenance"), "Records", FOLDER) is None      # no 5200 record, no rule
    assert world.drive.writes == []


def test_the_files_of_a_bound_folder_are_candidates_here_elsewhere_or_nowhere_and_none_is_pinned(world):
    world.drive.files[FILE_HELD]["meta"]["parents"] = [FOLDER]
    world.drive.files["1NoKindFileAbCdEfGhIjK"] = {"meta": FakeDrive.meta("1NoKindFileAbCdEfGhIjK", "Mystery.pdf", parents=(FOLDER,)), "data": b""}
    out = dc.bound_files(world.drive, FOLDER, "records/5200/minutes", community=world.community, root=world.root, profile="example")
    where = {f["name"]: f["where"] for f in out["files"]}
    assert where[NAME_A] == "here" and where[NAME_B] == "elsewhere" and where["Mystery.pdf"] == "nowhere"
    assert next(f for f in out["files"] if f["name"] == NAME_B)["offeredFor"] == ["governing/bylaws"]
    assert out["counts"]["files"] == len(out["files"]) and not (world.spec / "example" / "records.json").exists()


def test_every_act_names_a_person_and_never_jason(world):
    for call in (lambda: acts.keep("records/5200/minutes", reason="x", by="jason", dry_run=False, community=world.community, root=world.root),
                 lambda: acts.more("governing/policies-resolutions", "no", by="Jason", dry_run=False, community=world.community, root=world.root),
                 lambda: acts.reopen("records/5200/minutes", by="", dry_run=False, community=world.community, root=world.root),
                 lambda: rb.read("records/5200/minutes", by="jason", dry_run=False, drive=world.drive, community=world.community, root=world.root)):
        with pytest.raises(ValueError):
            call()


# --- the key documents join --------------------------------------------------------------------------------------------------------

def test_the_key_documents_checklist_shows_its_slot_and_per_instrument_counts_through_the_same_reader(world):
    from jason.tasks import key_documents as kd

    pick(world, "governing/bylaws", FILE_B)
    read(world, slot="governing/bylaws", dry=False)
    summary = rb.key_document_summary(world.community, world.root, "example")
    assert summary["bylaws"]["slot"] == "governing/bylaws" and summary["bylaws"]["pins"] == 1 and summary["bylaws"]["read"] == 1
    assert summary["bylaws"]["entries"]["bylaws"] == {"pins": 1, "read": 1, "wrongSlot": 0, "held": 0}
    data = kd.checklist(world.community, world.root, "example")
    group = next(g for g in data["groups"] if g["item"] == "bylaws")
    assert group["slot"]["state"] == "read" and group["slot"]["pins"] == 1 and group["slot"]["route"].startswith("#/onboarding/records/")
    assert group["entries"][0]["slot"] == {"pins": 1, "read": 1, "wrongSlot": 0, "held": 0}
    assert data["slotCounts"]["pins"] == 1 and data["slotCounts"]["read"] == 1
    # one writer: the pick for this slot is the key documents' own link
    assert kd.KeyDocumentStore(world.root, "example").load()["entries"]["bylaws"]["links"][0]["ref"] == FILE_B


# --- the console ---------------------------------------------------------------------------------------------------------------------

def _app(world, monkeypatch, **kw):
    from jason.web.app import create_app
    from jason.web.extra import drive_choose as web_drive
    from jason.web.extra import record_slots as web_slots
    from jason.web.sources import default_loaders

    monkeypatch.setattr(web_drive, "_community", lambda: world.community)
    monkeypatch.setattr(web_drive, "_root", lambda: world.root)
    monkeypatch.setattr(web_drive, "_open", lambda: world.drive)
    monkeypatch.setattr(web_slots, "_community", lambda: world.community)
    return create_app(world.tmp, default_loaders(), **kw)


def test_the_loaders_and_the_post_routes_answer_the_boards_chooser(world, monkeypatch):
    c = webclient.client(_app(world, monkeypatch))
    listed = c.get("/api/drive-list")
    assert listed.status_code == 200 and listed.json["found"] and listed.json["drives"][0]["name"] == "Board Drive"
    assert world.drive.closed is True
    by_folder = c.post("/api/write/drive/list", json={"parent": FOLDER, "size": 2})
    assert by_folder.status_code == 200 and len(by_folder.json["items"]) == 2 and by_folder.json["next"] == "2"
    found = c.post("/api/write/drive/search", json={"q": "bylaws"})
    assert found.status_code == 200 and [i["name"] for i in found.json["items"]] == [NAME_B]
    resolved = c.post("/api/write/drive/resolve", json={"ref": f"https://drive.google.com/file/d/{FILE_A}/view"})
    assert resolved.status_code == 200 and resolved.json["name"] == NAME_A and resolved.json["kind"] == "file"
    bound = c.post("/api/write/drive/bound", json={"slot": "records/5200/minutes", "folder": FOLDER})
    assert bound.status_code == 200 and bound.json["counts"]["files"] == 3
    assert c.post("/api/write/drive/bound", json={"slot": "nope/none", "folder": FOLDER}).status_code == 404
    assert c.post("/api/write/drive/bound", json={"folder": FOLDER}).status_code == 400
    assert c.post("/api/write/drive/other", json={}).status_code == 404
    assert webclient.client(_app(world, monkeypatch), token=False).post("/api/write/drive/search", json={"q": "bylaws"}).status_code == 403


def test_a_name_or_a_link_is_never_accepted_in_a_url(world, monkeypatch):
    c = webclient.client(_app(world, monkeypatch))
    assert c.get("/api/drive-search?q=minutes").status_code == 400
    assert c.get("/api/drive-resolve?ref=" + FILE_A).status_code == 400
    plain = c.get("/api/drive-search")
    assert plain.status_code == 200 and plain.json["post"] == "/api/write/drive/search"
    assert world.drive.calls == []                                                 # asking the loader never asked Google


def test_the_owner_view_gets_403_on_every_drive_and_reading_loader_and_post(world, monkeypatch):
    c = webclient.client(_app(world, monkeypatch))
    for url in ("/api/drive-list?view=owner", "/api/drive-search?view=owner", "/api/drive-resolve?view=owner",
                "/api/record-readings?view=owner"):
        refused = c.get(url)
        assert refused.status_code == 403 and "items" not in refused.json
    for key in ("search", "resolve", "list", "bound"):
        assert c.post(f"/api/write/drive/{key}?view=owner", json={"q": "bylaws", "ref": FILE_A, "slot": "records/5200/minutes"}).status_code == 403
    assert world.drive.calls == []


def test_where_console_sign_in_is_set_up_the_chooser_needs_a_signed_in_roster_person(world, monkeypatch):
    app = _app(world, monkeypatch, sign_in=webclient.roster_sign_in(required=False))
    c = webclient.client(app)
    assert c.get("/api/drive-list").status_code == 401
    assert c.post("/api/write/drive/search", json={"q": "bylaws"}).status_code == 401
    webclient.sign_in(c, "A Manager")
    assert c.get("/api/drive-list").status_code == 200
    assert c.post("/api/write/drive/search", json={"q": "bylaws"}).status_code == 200


def test_drive_not_connected_is_a_state_the_console_shows_not_an_error(world, monkeypatch):
    from jason.web.extra import drive_choose as web_drive

    def refuse():
        raise dc.DriveUnavailable(dc.NOT_SIGNED_IN, "jason google sign-in --name drive --interactive")

    c = webclient.client(_app(world, monkeypatch))
    monkeypatch.setattr(web_drive, "_open", refuse)
    for out in (c.get("/api/drive-list"), c.post("/api/write/drive/search", json={"q": "bylaws"})):
        assert out.status_code == 200 and out.json["driveConnected"] is False and out.json["command"] and "no Google sign-in" in out.json["why"]


def test_the_console_acts_go_through_the_guard_and_a_read_queues_a_job_in_the_persons_name(world, monkeypatch):
    c = webclient.client(_app(world, monkeypatch))
    slot = "records/5200/minutes"
    url = "/api/write/records/" + slot
    made = c.post(url, json={"act": "pick", "file": FILE_B, "by": BY, "period": "2099-06"})
    assert made.status_code == 200
    plan = c.post(url, json={"act": "read", "dryRun": True, "by": BY})
    assert plan.status_code == 200 and plan.json["dryRun"] is True and plan.json["reads"][0]["plan"]["willFetch"] is True
    assert world.drive.downloads == 0
    queued = c.post(url, json={"act": "read", "by": BY})
    assert queued.status_code == 200 and queued.json["queued"] is True and queued.json["command"].startswith("jason records --read")
    from jason import jobs

    job = jobs.get(world.root, queued.json["job"])
    assert job.argv[:3] == ["records", "--read", slot] and "--yes" in job.argv and job.confirmed_by == BY
    assert world.drive.downloads == 0                                              # the page never reads inline
    pin = made.json["pin"]
    read(world, dry=False)
    assert c.post(url, json={"act": "keep", "pin": pin, "note": "", "by": BY}).status_code == 400          # no reason
    kept = c.post(url, json={"act": "keep", "pin": pin, "note": "they are the bylaws", "by": BY, "dryRun": True})
    assert kept.status_code == 200 and kept.json["dryRun"] is True
    assert c.post(url, json={"act": "repin", "pin": pin, "to": "governing/bylaws", "by": BY}).json["to"] == "governing/bylaws"
    assert c.post("/api/write/records/governing/policies-resolutions", json={"act": "more", "value": "no", "by": BY}).status_code == 200
    assert c.post("/api/write/records/governing/policies-resolutions", json={"act": "reopen", "by": BY}).status_code == 200
    assert c.post(url, json={"act": "bind", "folder": FOLDER, "by": BY}).json["proposal"]["kind"] == "sync rule"
    assert c.post(url, json={"act": "upload", "by": BY}).status_code == 400
    assert c.post(url, json={"act": "keep", "pin": pin, "note": "x", "by": ""}).status_code == 400
    queue = c.get("/api/record-readings")
    assert queue.status_code == 200 and queue.json["kind"] == "record reading"


# --- no secret, no file name, and never a write to Drive ------------------------------------------------------------------------------

def test_no_token_file_name_or_file_id_reaches_a_log_the_history_or_a_stat_and_drive_is_never_written(world, caplog):
    caplog.set_level(logging.DEBUG)
    pin = pick(world, "records/5200/minutes", FILE_B, period="2099-06")["pin"]
    dc.list_folder(world.drive, folder=FOLDER, community=world.community, root=world.root, profile="example")
    dc.search(world.drive, "Secret", community=world.community, root=world.root, profile="example")
    dc.resolve(world.drive, FILE_A, community=world.community, root=world.root, profile="example")
    dc.resolve(world.drive, "1NoSuchFileAbCdEfGhIj", community=world.community, root=world.root, profile="example")
    read(world)
    read(world, dry=False)
    acts.keep("records/5200/minutes", reason="Secret reasons stay in the record", by=BY, dry_run=False, community=world.community,
              root=world.root, profile="example")
    acts.bind("records/5200/minutes", FOLDER, by=BY, drive=world.drive, dry_run=False, community=world.community, root=world.root,
              profile="example")
    acts.repin("records/5200/minutes", to="governing/bylaws", by=BY, pin=pin, dry_run=False, community=world.community, root=world.root,
               profile="example")
    rb.queue_items(world.community, world.root, "example")
    history = (world.root / "records" / "history.jsonl").read_text(encoding="utf-8")
    seen = "\n".join([caplog.text, history])
    for secret in (TOKEN, NAME_A, NAME_B, "Secret Board", "Secret Bylaws", FILE_A, FILE_B, FOLDER, "Secret reasons"):
        assert secret not in seen, secret
    assert world.drive.writes == [] and set(world.drive.calls) <= {"file_metadata", "list_page", "list_shared_drives", "about_user",
                                                                   "download_bytes", "export_file"}
    stats = json.dumps(rb.queue_items(world.community, world.root, "example")["counts"])
    assert NAME_B not in stats


def test_the_drive_client_has_no_write_the_chooser_could_reach():
    """The chooser's module imports no Drive write: the methods it calls are the reads GoogleDrive already has."""
    import inspect

    from jason.google.drive import GoogleDrive

    import ast

    called = set()
    for module in (dc, rb):
        for node in ast.walk(ast.parse(inspect.getsource(module))):
            if isinstance(node, ast.Attribute):
                called.add(node.attr)
    for write in ("create_folder", "upload_bytes", "replace_content", "update_metadata", "trash", "copy", "move", "share_with_link", "_post",
                  "child_folder", "root_id"):
        assert write not in called, write
    for name in ("list_page", "list_shared_drives", "about_user"):
        body = inspect.getsource(getattr(GoogleDrive, name))
        assert "_post" not in body and "files.create" not in body and "method" not in body


def test_slot_states_are_unchanged_for_a_slot_nobody_read(world):
    pick(world, "records/5200/minutes", FILE_A, period="2099-06")
    row = slot_row(world, "records/5200/minutes")
    assert row["state"] == SlotState.PICKED.value and "readback" not in row["holders"][0] and row["holders"][0]["kind"] == PinKind.DRIVE.value


# --- the command -------------------------------------------------------------------------------------------------------------------

def _cli(world, monkeypatch, *argv, connected=True):
    import argparse
    from contextlib import contextmanager

    from jason.commands import record_slots as command

    seen = {}

    @contextmanager
    def agent(args):
        class Agent:
            def drive(self_, *, interactive=False):
                seen["interactive"] = interactive
                if not connected:
                    raise GoogleAuthRequired("no human is present")
                return world.drive
        yield Agent()

    monkeypatch.setattr("jason.commands._shared.data_dir", lambda args=None: world.root)
    monkeypatch.setattr(command, "_community", lambda: world.community)
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers()
    command.register(sub, lambda p: p.add_argument("--interactive", action="store_true"), agent)
    args = parser.parse_args(["records", *argv])
    return args.func(args), seen


def test_the_command_reads_binds_keeps_repins_and_asks_more_each_a_dry_run_until_yes(world, monkeypatch, capsys):
    slot = "records/5200/minutes"
    assert _cli(world, monkeypatch, "--pick", slot, "--file", FILE_B, "--period", "2099-06", "--by", BY, "--yes")[0] == 0
    code, seen = _cli(world, monkeypatch, "--read", slot)
    out = capsys.readouterr().out
    assert code == 0 and "dry run" in out.lower() and "would fetch" in out and seen["interactive"] is False
    assert world.drive.downloads == 0
    assert _cli(world, monkeypatch, "--read", slot, "--yes", "--by", BY, "--no-ocr")[0] == 0
    out = capsys.readouterr().out
    assert world.drive.downloads == 1 and "jason read it as bylaws" in out and "wrong slot" in out
    assert _cli(world, monkeypatch, "--read", slot, "--json")[0] == 0 and json.loads(capsys.readouterr().out)["dryRun"] is True
    assert _cli(world, monkeypatch, "--keep", slot, "--reason", "they are our bylaws", "--by", BY)[0] == 0
    assert "dry run" in capsys.readouterr().out and not store(world).get("keeps")
    assert _cli(world, monkeypatch, "--keep", slot, "--reason", "they are our bylaws", "--by", BY, "--yes")[0] == 0
    assert store(world)["keeps"][0]["by"] == BY
    assert _cli(world, monkeypatch, "--more", "governing/policies-resolutions", "--value", "no", "--by", BY, "--yes")[0] == 0
    assert _cli(world, monkeypatch, "--reopen", "governing/policies-resolutions", "--by", BY, "--yes")[0] == 0
    assert _cli(world, monkeypatch, "--repin", slot, "--to", "governing/bylaws", "--by", BY, "--yes")[0] == 0
    assert _cli(world, monkeypatch, "--bind", "records/5200/minutes", "--folder", FOLDER, "--resolve", "--by", BY)[0] == 0
    printed = capsys.readouterr().out
    assert "SyncRule(" in printed and "AssociationRecord.MINUTES" in printed
    assert _cli(world, monkeypatch, "--slot", "governing/bylaws")[0] == 0
    assert "read" in capsys.readouterr().out
    assert _cli(world, monkeypatch, "--read", slot, "--keep", slot)[0] == 2
    assert world.drive.writes == []


def test_a_command_that_needs_drive_fails_fast_with_the_fix_when_it_is_not_connected(world, monkeypatch, capsys):
    slot = "records/5200/minutes"
    _cli(world, monkeypatch, "--pick", slot, "--file", FILE_A, "--period", "2099-06", "--by", BY, "--yes")
    code, seen = _cli(world, monkeypatch, "--read", slot, "--yes", "--by", BY, connected=False)
    err = capsys.readouterr().err
    assert code == 2 and "no Google sign-in" in err and "jason google sign-in" in err and seen["interactive"] is False
    code, _ = _cli(world, monkeypatch, "--read", slot, connected=False)           # a dry run still answers from the catalog
    assert code == 0 and "note:" in capsys.readouterr().err
