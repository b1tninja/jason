"""The record checklist: the slots assembled from jason's catalog, their states computed from pins, answers, and the
library, a pasted Drive link parsed, the three writes and their history, a collision on a slot that holds one, a wrong-slot
pick surfaced, the dry run that writes nothing, and what the read-only tools and the console's page show of a confidential
file. Made-up names, ids, and files only."""

import json
import sqlite3
from dataclasses import replace
from types import SimpleNamespace

import pytest

import webclient
from jason.community.documents import DocumentPin
from jason.community.record_slots import (
    Answer,
    AnswerKind,
    Cardinality,
    Origin,
    Pin,
    PinKind,
    Reading,
    Slot,
    SlotRule,
    SlotSource,
    SlotState,
    apply_rules,
    citations_in,
    merge_holders,
    parse_drive_ref,
    pin_status,
    slot_state,
)
from jason.community.symbols import DocumentKind
from jason.tasks import record_slots as rs

FILE_A = "1AbCdEfGhIjKlMnOpQrS"
FILE_B = "1ZyXwVuTsRqPoNmLkJiH"
LINK_A = f"https://drive.google.com/file/d/{FILE_A}/view?usp=sharing"
BY = "Jane Example"
KD = DocumentKind


class _Community:
    """A made-up association: no profile, one pin by kind, one Drive file for its declaration."""

    org_id = 7
    slug = "example"

    def __init__(self, rules=(), pins=(), declaration=None):
        self._rules, self._pins, self.ccrs = rules, pins, declaration

    def record_slots(self):
        return self._rules

    def pins(self):
        return self._pins

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
    """A data folder with a library of three files, a spec folder of its own, and the console's data root pointed at it."""
    root = tmp_path / "data"
    (root / "library" / "text").mkdir(parents=True)
    from jason.tasks.library import SCHEMA

    with sqlite3.connect(root / "library" / "library.db") as conn:
        conn.execute(SCHEMA)
        rows = [
            ("1001", "payhoa", "Minutes/minutes-2099-06.pdf", "minutes-2099-06.pdf", "minutes", "meeting", "minutes", "NAME", "2099-06", 0),
            ("1002", "payhoa", "Governing/bylaws.pdf", "bylaws.pdf", "bylaws", "governing", "governing_documents", "NAME", "", 0),
            ("1003", "payhoa", "Confidential/Bank/stmt-2099-06.pdf", "stmt-2099-06.pdf", "bank_statement", "financial", "enhanced", "NAME", "2099-06", 1),
            ("1004", "payhoa", "Governing/rules.pdf", "rules.pdf", "operating_rules", "governing", "governing_documents", "PERSON", "", 0),
        ]
        for r in rows:
            evidence = "chosen by Pat Example on 2099-01-02" if r[7] == "PERSON" else ""
            conn.execute("INSERT INTO documents (id, source, path, name, kind, category, records, method, period, confidential, evidence)"
                         " VALUES (?,?,?,?,?,?,?,?,?,?,?)", (*r, evidence))
    (root / "library" / "text" / "1001.txt").write_text("Minutes of the board meeting.", encoding="utf-8")
    spec = tmp_path / "spec"
    spec.mkdir()
    monkeypatch.setenv("JASON_SPEC_DIR", str(spec))
    monkeypatch.setattr("jason.mcp.county._data_dir", lambda given=None: root)
    return SimpleNamespace(root=root, spec=spec, community=_Community())


def slots_by_key(community=None):
    return {s.key: s for s in rs.assemble(community).slots}


# --- the slots come from code, not a typed list -------------------------------------------------------------------------------

def test_the_slots_are_assembled_from_the_catalog_and_name_no_association():
    slots = slots_by_key()
    assert slots["records/5200/minutes"].requires == ("CIV 5200(a)(8)",)
    assert slots["records/5200/minutes"].cardinality is Cardinality.SERIES
    assert slots["records/5200/minutes"].source is SlotSource.RECORD_5200
    assert "records/5200/governing_documents" not in slots          # the key documents' slots carry that record
    assert slots["governing/declaration"].cardinality is Cardinality.ONE and slots["governing/declaration"].key_document == "declaration"
    assert slots["governing/amendments"].cardinality is Cardinality.SEVERAL
    assert slots["governing/amendments"].waits_on == ("governing/declaration",)
    assert slots["delivery/bond"].requires[0] == "10 CCR 2792.23" and slots["delivery/bond"].source is SlotSource.DELIVERY
    assert "delivery/declaration" not in slots                      # a key document already carries that delivery
    assert slots["kind/reserve_study"].cardinality is Cardinality.SERIES
    assert slots["governing/policies-resolutions"].source is SlotSource.ONBOARDING
    assert len(slots) == len(rs.assemble().slots)                   # no key twice
    assert slots["records/5200/membership_list"].confidential and not slots["records/5200/minutes"].confidential
    assert all(s.group for s in slots.values())


def test_citations_are_read_from_the_prose_jason_already_has():
    assert citations_in("CIV 4135, 4150; every buyer gets it (4525(a)(1))") == ("CIV 4135", "CIV 4150")
    assert citations_in("starts the lien clocks (CIV 8412, 8414); BPC 11018.5 and 10 CCR 2792.23(a)") == (
        "CIV 8412", "CIV 8414", "BPC 11018.5", "10 CCR 2792.23(a)")
    assert citations_in("jason's own design needs it") == ()


def test_a_profile_adds_a_slot_and_hides_one_with_its_reason_and_is_never_silent(world):
    mine = Slot("local/permit-condition", "A permit's condition of approval", "maintenance", ("MUN 1.1",), Cardinality.SEVERAL)
    rules = (SlotRule("local/permit-condition", slot=mine),
             SlotRule("records/5200/check_register", hide=True, reason="the association keeps no register apart from the ledger"),
             SlotRule("records/5200/minutes", hide=True, reason=""),                      # no reason: ignored, never silent
             SlotRule("records/5200/minutes", slot=replace(mine, key="records/5200/minutes")))   # cannot replace jason's slot
    community = _Community(rules=rules)
    assembly = rs.assemble(community)
    keys = {s.key for s in assembly.slots}
    assert "local/permit-condition" in keys and assembly.hidden == {"records/5200/check_register": "the association keeps no register apart from the ledger"}
    assert "records/5200/check_register" in keys and next(s for s in assembly.slots if s.key == "records/5200/minutes").title != mine.title
    row = next(r for g in rs.view(community, world.root, "example")["groups"] for r in g["slots"] if r["key"] == "records/5200/check_register")
    assert row["hidden"] and "no register" in row["hidden"]
    with pytest.raises(ValueError, match="hidden by the profile"):
        rs.pick("records/5200/check_register", FILE_A, by=BY, community=community, root=world.root, profile="example")


def test_the_pure_rules_do_not_need_a_profile():
    slots, hidden = apply_rules([Slot("a/b", "t", "g")], [SlotRule("a/b", hide=True, reason="no")])
    assert hidden == {"a/b": "no"} and len(slots) == 1


# --- links ---------------------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("text, ident, folder", [
    (LINK_A, FILE_A, False),
    (f"https://docs.google.com/document/d/{FILE_A}/edit", FILE_A, False),
    (f"https://docs.google.com/spreadsheets/d/{FILE_A}/edit#gid=0", FILE_A, False),
    (f"https://drive.google.com/open?id={FILE_A}", FILE_A, False),
    (f"https://drive.google.com/uc?export=download&id={FILE_A}", FILE_A, False),
    (f"https://drive.google.com/drive/folders/{FILE_A}?usp=sharing", FILE_A, True),
    (f"https://drive.google.com/drive/u/0/folders/{FILE_A}", FILE_A, True),
    (f"drive.google.com/file/d/{FILE_A}/view", FILE_A, False),
    (FILE_A, FILE_A, False),
])
def test_a_pasted_drive_link_or_id_is_parsed(text, ident, folder):
    got = parse_drive_ref(text)
    assert got.id == ident and got.folder is folder


@pytest.mark.parametrize("text, words", [
    ("", "give a Drive link"),
    ("https://example.org/file/d/" + FILE_A, "not a Drive link"),
    ("https://drive.google.com/drive/my-drive", "no file id"),
    ("short", "neither a Drive link nor a file id"),
])
def test_text_that_is_not_a_drive_file_is_refused_in_a_sentence(text, words):
    with pytest.raises(ValueError, match=words):
        parse_drive_ref(text)


def test_a_folder_link_is_not_a_pin(world):
    with pytest.raises(ValueError, match="folder"):
        rs.pick("records/5200/minutes", f"https://drive.google.com/drive/folders/{FILE_A}", by=BY, dry_run=False,
                community=world.community, root=world.root, profile="example")


# --- states, computed ---------------------------------------------------------------------------------------------------------

def test_an_untouched_slot_is_empty_and_missing_is_never_inferred(world):
    computed = {c.slot.key: c for c in rs.compute(world.community, world.root, "example")}
    assert {c.state for c in computed.values()} == {SlotState.EMPTY}
    assert all(not c.holders and c.answer is None for c in computed.values())


def test_the_states_follow_what_the_library_shows(world):
    slot = Slot("x/y", "t", "g", kinds=(KD.MINUTES,))
    pin = Pin("p-1", "x/y", PinKind.LIBRARY, "1001")
    assert pin_status(slot, pin, None).state is SlotState.PICKED
    assert pin_status(slot, pin, Reading(found=True, kind=None)).state is SlotState.PICKED          # a miss stays a miss
    assert pin_status(slot, pin, Reading(found=True, kind="minutes")).state is SlotState.CLASSIFIED
    assert pin_status(slot, pin, Reading(found=True, kind="minutes", read=True)).state is SlotState.READ
    assert pin_status(slot, pin, Reading(found=True, kind="minutes", read=True, confirmed_by="Pat Example")).state is SlotState.CONFIRMED
    upload = Pin("p-2", "x/y", PinKind.FILE, "key-documents/example/files/0123456789abcdef/scan.pdf")
    assert pin_status(slot, upload, None).state is SlotState.UPLOADED
    assert pin_status(slot, pin, Reading(found=True, kind="minutes", confidential=True)).held


def test_a_slot_with_several_pins_is_as_far_along_as_its_least_advanced(world):
    slot = Slot("x/y", "t", "g", cardinality=Cardinality.SEVERAL, kinds=(KD.MINUTES,))
    a = pin_status(slot, Pin("p-1", "x/y", PinKind.LIBRARY, "1001"), Reading(found=True, kind="minutes", read=True))
    b = pin_status(slot, Pin("p-2", "x/y", PinKind.DRIVE, FILE_A), None)
    assert slot_state(slot, [a, b], None) is SlotState.PICKED and slot_state(slot, [a], None) is SlotState.READ


def test_an_answer_gives_the_state_and_a_pin_outranks_an_older_answer(world):
    slot = Slot("x/y", "t", "g")
    none = Answer("a-1", "x/y", AnswerKind.NONE, "looked in the office files", BY, "2099-01-01T00:00:00+00:00")
    waiting = Answer("a-2", "x/y", AnswerKind.WAITING, "asked the prior manager", BY, "2099-02-01T00:00:00+00:00", "the prior manager")
    assert slot_state(slot, [], none) is SlotState.DOES_NOT_EXIST and slot_state(slot, [], waiting) is SlotState.WAITING
    assert slot_state(slot, [pin_status(slot, Pin("p", "x/y", PinKind.DRIVE, FILE_A), None)], waiting) is SlotState.PICKED


def test_a_pick_reads_through_to_the_library(world):
    rs.pick("records/5200/minutes", "library:1001", by=BY, period="2099-06", dry_run=False, community=world.community, root=world.root, profile="example")
    detail = rs.slot_view("records/5200/minutes", world.community, world.root, "example")
    assert detail["state"] == "read" and detail["holders"][0]["reading"]["readsAs"] == "minutes"
    assert detail["holders"][0]["reading"]["tier"] == "suggested" and detail["periods"] == [{"period": "2099-06", "state": "read"}]
    again = rs.pick("records/5200/minutes", "library:1001", by=BY, period="2099-06", dry_run=False, community=world.community,
                    root=world.root, profile="example")
    assert again["already"] and len(rs.load_store("example")["pins"]) == 1


def test_a_person_confirmed_kind_is_confirmed_with_who(world):
    rs.pick("governing/operating-rules", "library:1004", by=BY, dry_run=False, community=world.community, root=world.root, profile="example")
    detail = rs.slot_view("governing/operating-rules", world.community, world.root, "example")
    assert detail["state"] == "confirmed" and detail["holders"][0]["reading"]["confirmedBy"] == "Pat Example"


def test_a_drive_file_is_found_through_the_drive_catalog_by_name(world):
    (world.root / "drive").mkdir()
    (world.root / "drive" / "files.json").write_text(json.dumps(
        {"syncedAt": "2099-01-01", "files": [{"id": FILE_A, "name": "bylaws.pdf", "path": "My Drive/bylaws.pdf"}]}), encoding="utf-8")
    rs.pick("governing/bylaws", LINK_A, by=BY, dry_run=False, community=world.community, root=world.root, profile="example")
    detail = rs.slot_view("governing/bylaws", world.community, world.root, "example")
    assert detail["holders"][0]["name"] == "bylaws.pdf" and detail["state"] == "classified"
    assert rs.view(world.community, world.root, "example")["driveCatalog"] == {"syncedAt": "2099-01-01", "files": 1}


# --- a wrong-slot pick is surfaced --------------------------------------------------------------------------------------------

def test_a_file_that_reads_as_another_kind_is_a_problem_with_the_slots_it_fits(world):
    rs.pick("governing/bylaws", "library:1001", by=BY, dry_run=False, community=world.community, root=world.root, profile="example")
    detail = rs.slot_view("governing/bylaws", world.community, world.root, "example")
    assert detail["state"] == "problem" and "reads this as minutes" in detail["problem"]
    wrong = detail["holders"][0]["wrongSlot"]
    assert wrong["readsAs"] == "minutes" and "records/5200/minutes" in {f["key"] for f in wrong["fits"]}
    assert "unpin" in wrong["acts"]
    listing = rs.view(world.community, world.root, "example", state="problem")
    assert [s["key"] for g in listing["groups"] for s in g["slots"]] == ["governing/bylaws"]
    assert listing["counts"]["byState"]["problem"] == 1                         # the counts stay whole when the list is narrowed


# --- collisions ---------------------------------------------------------------------------------------------------------------

def test_two_different_files_on_a_slot_that_holds_one_collide_and_neither_wins(world):
    declaration = SimpleNamespace(drive_id=FILE_B, title="The declaration", amendments=())
    community = _Community(declaration=declaration)
    rs.pick("governing/declaration", LINK_A, by=BY, dry_run=False, community=community, root=world.root, profile="example")
    detail = rs.slot_view("governing/declaration", community, world.root, "example")
    assert len(detail["holders"]) == 2 and {h["origin"] for h in detail["holders"]} == {"specification", "person"}
    assert detail["collisions"] and detail["collisions"][0]["slot"] == "governing/declaration"
    assert "Neither wins" in detail["collisions"][0]["note"] and detail["collision"] is True


def test_the_same_file_in_the_specification_and_in_a_pin_is_one_holder(world):
    declaration = SimpleNamespace(drive_id=FILE_A, title="The declaration", amendments=())
    community = _Community(declaration=declaration)
    rs.pick("governing/declaration", FILE_A, by=BY, dry_run=False, community=community, root=world.root, profile="example")
    detail = rs.slot_view("governing/declaration", community, world.root, "example")
    assert len(detail["holders"]) == 1 and detail["collisions"] == [] and detail["holders"][0]["origin"] == "person"
    assert "specification" in detail["holders"][0]["source"]


def test_a_set_unions_the_specifications_pins_and_a_persons():
    slot = Slot("x/y", "t", "g", cardinality=Cardinality.SEVERAL)
    code = [Pin("c-1", "x/y", PinKind.DRIVE, FILE_A, origin=Origin.CODE, source="specification")]
    data = [Pin("p-1", "x/y", PinKind.DRIVE, FILE_B, origin=Origin.DATA, source="records.json")]
    holders, collisions = merge_holders(slot, code, data)
    assert len(holders) == 2 and collisions == []


def test_two_files_for_one_period_of_a_series_collide():
    slot = Slot("x/y", "t", "g", cardinality=Cardinality.SERIES)
    holders, collisions = merge_holders(slot, [], [Pin("p-1", "x/y", PinKind.DRIVE, FILE_A, period="2099"),
                                                   Pin("p-2", "x/y", PinKind.DRIVE, FILE_B, period="2099")])
    assert len(holders) == 2 and collisions and collisions[0]["period"] == "2099"


# --- the writes ---------------------------------------------------------------------------------------------------------------

def test_a_dry_run_writes_nothing(world):
    out = rs.pick("records/5200/minutes", LINK_A, by=BY, community=world.community, root=world.root, profile="example")
    assert out["dryRun"] and out["would"]["ref"] == FILE_A and out["would"]["writes"] == "spec/example/records.json"
    assert rs.answer("records/5200/minutes", "none", by=BY, reason="looked in the office", community=world.community,
                     root=world.root, profile="example")["dryRun"]
    assert not (world.spec / "example" / "records.json").exists() and not rs.history_path(world.root).exists()
    rs.pick("records/5200/minutes", LINK_A, by=BY, dry_run=False, community=world.community, root=world.root, profile="example")
    assert rs.unpin("records/5200/minutes", by=BY, community=world.community, root=world.root, profile="example")["dryRun"]
    assert len(rs.load_store("example")["pins"]) == 1 and not rs.load_store("example")["pins"][0]["unpinned"]


def test_a_write_names_its_person_and_never_jason(world):
    for who in ("", "  ", "Jason", "jason"):
        with pytest.raises(ValueError, match="who|never writes"):
            rs.pick("records/5200/minutes", LINK_A, by=who, community=world.community, root=world.root, profile="example")
    with pytest.raises(KeyError):
        rs.pick("records/5200/nothing", LINK_A, by=BY, community=world.community, root=world.root, profile="example")


def test_pin_answer_and_unpin_are_kept_and_nothing_is_rewritten(world):
    kw = dict(community=world.community, root=world.root, profile="example")
    a = rs.pick("records/5200/minutes", LINK_A, by=BY, period="2099", note="the June minutes", dry_run=False, **kw)
    b = rs.pick("records/5200/minutes", "library:1001", by="Pat Example", period="2098", dry_run=False, **kw)
    assert a["written"] == "spec/example/records.json" and a["pin"].startswith("p-")
    stored = json.loads((world.spec / "example" / "records.json").read_text(encoding="utf-8"))
    assert [p["id"] for p in stored["pins"]] == [a["pin"], b["pin"]] and stored["pins"][0]["by"] == BY
    ans = rs.answer("records/5200/vendor_approval", "none", by=BY, reason="looked in the secretary's binder and Drive", dry_run=False, **kw)
    wait = rs.answer("records/5200/tax_return", "waiting", by=BY, reason="asked on 2099-10-01", who="the prior manager", dry_run=False, **kw)
    na = rs.answer("records/5200/reserve_litigation_accounting", "notApplicable", by=BY, reason="no reserves were used for litigation", dry_run=False, **kw)
    states = {c.slot.key: c.state for c in rs.compute(**kw)}
    assert states["records/5200/vendor_approval"] is SlotState.DOES_NOT_EXIST
    assert states["records/5200/tax_return"] is SlotState.WAITING
    assert states["records/5200/reserve_litigation_accounting"] is SlotState.NOT_APPLICABLE
    gone = rs.unpin("records/5200/minutes", by=BY, pin=a["pin"], note="wrong month", dry_run=False, **kw)
    assert gone["pin"] == a["pin"]
    stored = json.loads((world.spec / "example" / "records.json").read_text(encoding="utf-8"))
    kept = next(p for p in stored["pins"] if p["id"] == a["pin"])
    assert kept["unpinned"]["by"] == BY and kept["unpinned"]["note"] == "wrong month"            # kept, marked, never deleted
    assert (world.spec / "example" / "records.json.bak").is_file()
    log = rs.read_history(world.root)
    assert [r["act"] for r in log] == ["pick", "pick", "answer", "answer", "answer", "unpin"]
    assert log[0]["slot"] == "records/5200/minutes" and ans["answer"] == log[2]["answerId"] and wait["ok"] and na["ok"]
    assert all(r["by"] for r in log) and "ref" not in json.dumps(log)                              # who, and no file id in the trail
    with pytest.raises(ValueError, match="no active pin"):
        rs.unpin("records/5200/minutes", by=BY, pin="p-nope", dry_run=False, **kw)


def test_an_answer_needs_its_words_and_refuses_a_secret(world):
    kw = dict(community=world.community, root=world.root, profile="example", dry_run=False)
    with pytest.raises(ValueError, match="say"):
        rs.answer("records/5200/minutes", "none", by=BY, reason="", **kw)
    with pytest.raises(ValueError, match="password"):
        rs.answer("records/5200/minutes", "notApplicable", by=BY, reason="the password is hunter2 for the file", **kw)
    with pytest.raises(ValueError, match="notApplicable"):
        rs.answer("records/5200/minutes", "maybe", by=BY, reason="x", **kw)
    assert not (world.spec / "example" / "records.json").exists()


def test_a_period_belongs_to_a_series(world):
    kw = dict(community=world.community, root=world.root, profile="example", dry_run=False)
    with pytest.raises(ValueError, match="not a series"):
        rs.pick("records/5200/membership_list", LINK_A, by=BY, period="2099", **kw)
    with pytest.raises(ValueError, match="a year"):
        rs.pick("records/5200/minutes", LINK_A, by=BY, period="last June", **kw)


def test_a_specification_pin_is_not_removed_by_an_unpin(world):
    declaration = SimpleNamespace(drive_id=FILE_B, title="The declaration", amendments=())
    community = _Community(declaration=declaration)
    code_id = rs.code_pins(community, rs.assemble(community).slots)["governing/declaration"][0].id
    with pytest.raises(ValueError, match="specification's"):
        rs.unpin("governing/declaration", by=BY, pin=code_id, dry_run=False, community=community, root=world.root, profile="example")


def test_a_pick_on_a_recorded_instrument_is_the_key_documents_link_one_writer(world):
    kw = dict(community=world.community, root=world.root, profile="example", dry_run=False)
    out = rs.pick("governing/bylaws", LINK_A, by=BY, note="from the box", **kw)
    assert out["written"] == "key-documents/example.json" and out["pin"].startswith("k-")
    store = json.loads((world.root / "key-documents" / "example.json").read_text(encoding="utf-8"))
    assert store["entries"]["bylaws"]["links"][0]["ref"] == FILE_A
    assert not (world.spec / "example" / "records.json").exists()                  # no second store of the same fact
    assert [h["pin"] for h in rs.slot_view("governing/bylaws", world.community, world.root, "example")["holders"]] == [out["pin"]]
    with pytest.raises(ValueError, match="recording number"):
        rs.pick("governing/amendments", LINK_A, by=BY, **kw)
    amended = rs.pick("governing/amendments", LINK_A, by=BY, entry="2010-0000100", **kw)
    assert amended["pin"].startswith("k-")
    none = rs.answer("governing/articles", "none", by=BY, reason="not in the box or on Drive", **kw)
    assert none["written"] == "key-documents/example.json"
    assert rs.slot_view("governing/articles", world.community, world.root, "example")["state"] == "doesNotExist"
    gone = rs.unpin("governing/bylaws", by=BY, **kw)
    assert gone["written"] == "key-documents/example.json"
    assert rs.slot_view("governing/bylaws", world.community, world.root, "example")["holders"] == []


def test_a_resolved_link_names_the_file_and_a_file_jason_cannot_open_writes_nothing(world):
    class Drive:
        def get_file(self, ident):
            if ident == FILE_B:
                raise RuntimeError("404")
            return {"name": "Bylaws 2099.pdf", "mimeType": "application/pdf", "size": "4123", "modifiedTime": "2099-09-30T01:02:03Z"}

    kw = dict(community=world.community, root=world.root, profile="example")
    out = rs.pick("governing/bylaws", LINK_A, by=BY, drive=Drive(), dry_run=True, **kw)
    assert out["would"]["name"] == "Bylaws 2099.pdf"
    with pytest.raises(ValueError, match="cannot open that file"):
        rs.pick("records/5200/minutes", FILE_B, by=BY, drive=Drive(), dry_run=False, **kw)
    assert not (world.spec / "example" / "records.json").exists()
    assert rs.resolve(LINK_A, Drive())["modified"] == "2099-09-30"


# --- what is shown, by level ----------------------------------------------------------------------------------------------------

def test_a_confidential_file_is_named_by_its_kind_and_its_id_is_shortened_outside_the_private_view(world):
    kw = dict(community=world.community, root=world.root, profile="example", dry_run=False)
    rs.pick("records/5200/enhanced", "library:1003", by=BY, note="the June statement", **kw)
    shown = rs.slot_view("records/5200/enhanced", world.community, world.root, "example")
    holder = shown["holders"][0]
    assert holder["held"] and holder["name"] == "a confidential file (kind: bank statement)" and holder["note"] == ""
    assert "stmt-2099-06" not in json.dumps(shown) and holder["opens"]
    assert shown["state"] == "classified" and rs.view(world.community, world.root, "example")["counts"]["held"] == 1
    private = rs.slot_view("records/5200/enhanced", world.community, world.root, "example", private=True)
    assert private["holders"][0]["name"] == "stmt-2099-06.pdf" and private["holders"][0]["note"] == "the June statement"
    assert all("stmt-2099-06" not in c["name"] for c in shown["candidates"])


def test_a_confidential_slots_answer_words_are_masked_outside_the_private_view(world):
    kw = dict(community=world.community, root=world.root, profile="example", dry_run=False)
    rs.answer("records/5200/membership_list", "waiting", by=BY, reason="asked the prior manager for the roster of owners", who="Sam Prior", **kw)
    shown = rs.slot_view("records/5200/membership_list", world.community, world.root, "example")
    assert shown["existence"]["answer"]["word"] == "waiting on someone else" and shown["existence"]["answer"]["reason"] == ""
    assert shown["existence"]["answer"]["who"] == "" and shown["existence"]["answer"]["held"]
    assert rs.slot_view("records/5200/membership_list", world.community, world.root, "example", private=True)["existence"]["answer"]["who"] == "Sam Prior"


def test_the_mcp_tools_read_only_and_hold_no_name_a_file_or_an_id(world, monkeypatch):
    from jason.mcp import record_slots as tools
    from jason.mcp.server import PROFILES, tools_for

    monkeypatch.setattr(tools, "_community", lambda: world.community)
    monkeypatch.setattr(rs, "_profile", lambda profile, community=None: profile or "example")
    kw = dict(community=world.community, root=world.root, profile="example", dry_run=False)
    rs.pick("records/5200/enhanced", "library:1003", by=BY, **kw)
    rs.pick("records/5200/minutes", LINK_A, by=BY, **kw)
    listing = tools.record_slots(data_dir=world.root)
    assert listing["found"] and listing["counts"]["total"] == len(rs.assemble().slots)
    text = json.dumps(listing) + json.dumps(tools.record_slot("records/5200/enhanced", data_dir=world.root))
    assert "stmt-2099-06" not in text and FILE_A not in text and "caveats" in listing
    assert any("not none" in c or "Empty means" in c for c in listing["caveats"])
    one = tools.record_slot("records/5200/minutes", data_dir=world.root)
    assert one["holders"][0]["ref"] == FILE_A[:6] + "…"
    assert tools.record_slot("nope/none", data_dir=world.root)["found"] is False
    assert {"record_slots", "record_slot"} <= set(PROFILES["board"]) and {"record_slots", "record_slot"} <= set(PROFILES["onboarding"])
    served = {t.__name__ for t in tools_for("board")} | {t.__name__ for t in tools_for("onboarding")}
    assert not {n for n in served if "pick" in n or "unpin" in n or n.startswith("answer_record")}     # no write tool
    from jason import api

    assert api.record_slots is tools.record_slots and api.record_slot is tools.record_slot


def test_the_console_loaders_match_the_handoffs_shapes_and_mask_a_confidential_slot(world, monkeypatch):
    from jason.web.extra import record_slots as web
    from jason.web.sources import EXTRA_LOADERS, EXTRA_WRITERS

    assert "record-slots" in EXTRA_LOADERS and "record-slot" in EXTRA_LOADERS and "records" in EXTRA_WRITERS
    monkeypatch.setattr(web, "_community", lambda: world.community)
    monkeypatch.setattr(rs, "_profile", lambda profile, community=None: profile or "example")
    web.write("records/5200/enhanced", {"act": "pick", "file": "library:1003", "by": BY})
    page = web.record_slot({"key": "records/5200/enhanced"})
    assert page["found"] and page["route"] == "#/onboarding/records/records%2F5200%2Fenhanced"
    assert page["holders"][0]["name"].startswith("a confidential file") and "stmt-2099-06" not in json.dumps(page)
    assert {"key", "title", "requires", "cardinality", "state", "held", "cells", "periods", "confidential", "route"} <= set(page)
    data = web.record_slots({})
    assert {"found", "asOf", "profile", "counts", "groups", "biggestUnknowns", "caveats"} <= set(data)
    assert {"total", "byState", "held"} <= set(data["counts"])
    assert {"key", "title", "law", "opensGate", "counts", "slots"} <= set(data["groups"][0])
    assert data["biggestUnknowns"] and {"key", "why", "blocks"} <= set(data["biggestUnknowns"][0])
    assert [s["key"] for g in web.record_slots({"group": "governing"})["groups"] for s in g["slots"]] and \
        {g["key"] for g in web.record_slots({"group": "governing"})["groups"]} == {"governing"}
    with pytest.raises(ValueError, match="key"):
        web.record_slot({})


def test_the_console_write_goes_through_the_guard_and_records_the_pin(world, tmp_path, monkeypatch):
    from jason.web.app import create_app
    from jason.web.extra import record_slots as web

    monkeypatch.setattr(web, "_community", lambda: world.community)
    monkeypatch.setattr(rs, "_profile", lambda profile, community=None: profile or "example")
    c = webclient.client(create_app(tmp_path, {}))
    no_token = webclient.client(create_app(tmp_path, {}), token=False)
    body = {"act": "pick", "file": LINK_A, "by": BY}
    assert no_token.post("/api/write/records/records/5200/minutes", json=body).status_code == 403
    assert not (world.spec / "example" / "records.json").exists()
    posted = c.post("/api/write/records/records/5200/minutes", json=body)
    assert posted.status_code == 200 and posted.json["written"] == "spec/example/records.json"
    assert c.post("/api/write/records/records/5200/minutes", json={**body, "by": ""}).status_code == 400
    assert c.post("/api/write/records/records/5200/minutes", json={"act": "upload", "by": BY}).status_code == 400
    assert c.post("/api/write/records/records/5200/nope", json=body).status_code == 404
    answered = c.post("/api/write/records/records/5200/tax_return", json={"act": "answer", "value": "none", "note": "looked in the files", "by": BY})
    assert answered.status_code == 200
    from jason.web.sources import default_loaders

    board = webclient.client(create_app(tmp_path, default_loaders()))
    assert board.get("/api/record-slots").status_code == 200
    assert board.get("/api/record-slot?key=records/5200/minutes").json["found"] is True
    for url in ("/api/record-slots?view=owner", "/api/record-slot?view=owner&key=records/5200/minutes"):
        refused = board.get(url)
        assert refused.status_code == 403 and "groups" not in refused.json        # the owner view never carries the checklist


# --- the command ----------------------------------------------------------------------------------------------------------------

def _cli(world, monkeypatch, *argv):
    import argparse

    from jason.commands import record_slots as command

    monkeypatch.setattr("jason.commands._shared.data_dir", lambda args=None: world.root)
    monkeypatch.setattr(command, "_community", lambda: world.community)
    monkeypatch.setattr(rs, "_profile", lambda profile, community=None: profile or "example")
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers()
    command.register(sub, lambda p: p.add_argument("--env"), lambda args: None)
    args = parser.parse_args(["records", *argv])
    return args.func(args)


def test_the_command_lists_shows_and_makes_every_write_a_dry_run_without_yes(world, monkeypatch, capsys):
    assert _cli(world, monkeypatch) == 0
    out = capsys.readouterr().out
    assert "Record checklist (example)" in out and "records/5200/minutes" in out and "empty" in out
    assert _cli(world, monkeypatch, "--list", "--group", "meetings", "--json") == 0
    assert json.loads(capsys.readouterr().out)["groups"][0]["key"] == "meetings"
    assert _cli(world, monkeypatch, "--pick", "records/5200/minutes", "--file", LINK_A, "--by", BY) == 0
    assert "dry run" in capsys.readouterr().out and not (world.spec / "example" / "records.json").exists()
    assert _cli(world, monkeypatch, "--pick", "records/5200/minutes", "--file", LINK_A, "--by", BY, "--yes") == 0
    assert "wrote spec/example/records.json" in capsys.readouterr().out
    assert _cli(world, monkeypatch, "--slot", "records/5200/minutes") == 0
    assert "picked" in capsys.readouterr().out
    assert _cli(world, monkeypatch, "--answer", "records/5200/tax_return", "--none", "--reason", "looked in the files", "--by", BY, "--yes") == 0
    assert _cli(world, monkeypatch, "--unpin", "records/5200/minutes", "--by", BY, "--yes") == 0
    assert json.loads((world.spec / "example" / "records.json").read_text(encoding="utf-8"))["pins"][0]["unpinned"]["by"] == BY
    capsys.readouterr()
    assert _cli(world, monkeypatch, "--pick", "records/5200/minutes", "--file", LINK_A) == 2          # no --by
    assert "who" in capsys.readouterr().err
    assert _cli(world, monkeypatch, "--answer", "records/5200/minutes", "--by", BY) == 2              # no flag
    assert _cli(world, monkeypatch, "--slot", "nope/none") == 1
    assert _cli(world, monkeypatch, "--pins") == 0


def test_the_command_is_registered_and_its_name_was_free():
    import jason.cli as cli
    from jason.commands import MODULES

    assert "record_slots" in MODULES
    choices = cli.build_parser()._subparsers._group_actions[0].choices
    assert list(choices).count("records") == 1 and "records-request" in choices
