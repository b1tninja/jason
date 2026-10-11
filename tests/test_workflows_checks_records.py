"""The reads of the records family (src/jason/workflows/checks/records.py), in a temporary data folder with made-up stores.

Nothing here reads a real store, reaches the network, or loads a profile. Each read is tried where it passes and where it does
not, with a store it cannot read, and with the data folder compared byte for byte before and after (a read writes nothing).
Everything is made up ("Jane Example", "example", 2099).
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest

from jason.community import intake
from jason.community import onboarding as ob
from jason.community.intake import Ask, AskKind, AskStatus, ask_id
from jason.community.key_documents import KeyDocumentStore, LinkKind
from jason.community.split_session import Source, SplitSession, new_id
from jason.tasks import split_session
from jason.workflows import checks
from jason.workflows.checks import records as reads
from jason.workflows.readers import CHECKS, StoreReaders
from test_workflows_support import data  # noqa: F401 - the `data` fixture

BY = "Jane Example"
GATES = ("start", "ingest", "establish", "operate", "adopt")
NAMES = ("active-community", "onboard-gates-read", *(f"onboard-gate-{g}" for g in GATES), "onboard-checklist",
         "record-slots-read", "key-document-status", "ingest-gate", "split-review", "scratch-room", "profile-own-facts",
         "key-document-verified", "request-kinds-mapped", "record-compare")


def tree(root: Path) -> dict[str, bytes]:
    """Every file under a folder, with its bytes: what a read must leave exactly as it was."""
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}


def view(subject="association:example"):
    return SimpleNamespace(id="run-test", opened_at="2020-01-01T00:00:00Z", dates={}, subject=subject)


@pytest.fixture
def world(data, tmp_path, monkeypatch):
    """A data folder, a private-facts folder of its own, and the community the runs are about chosen."""
    data.mkdir(parents=True)
    (tmp_path / "spec").mkdir()
    monkeypatch.setenv("JASON_COMMUNITY", "example")
    monkeypatch.setenv("JASON_SPEC_DIR", str(tmp_path / "spec"))
    monkeypatch.setattr(reads, "_settings", lambda: None)
    checks.load_all()
    return data


def run(name, data, subject="association:example", community=None):
    readers = StoreReaders(data, community=community if community is not None else SimpleNamespace(), today=date(2099, 1, 1))
    return CHECKS[name](readers, view(subject), "")


# --- a made-up association for the readers of the record checklist and the key documents ------------------------------------

class Association:
    """No profile: it answers the few questions the record checklist and the key documents list ask of one."""

    org_id = 7
    slug = "example"
    name = "Example Association"
    region = ""
    ccrs = None

    def __init__(self, rules=()):
        self._rules = rules

    def record_slots(self):
        return self._rules

    def pins(self):
        return ()

    def developer_file(self):
        return {}

    def known_files(self):
        return ()

    def library_folders(self):
        return ()

    def supersessions(self):
        return ()

    def public_reports(self):
        return ()

    @property
    def sync_rules(self):
        return ()


# --- the registry -----------------------------------------------------------------------------------------------------------

def test_the_seventeen_reads_are_registered_once_and_loading_twice_changes_nothing(world):
    assert len(NAMES) == 17 and len(set(NAMES)) == 17
    before = dict(CHECKS)
    checks.load_all()
    assert dict(CHECKS) == before
    for name in NAMES:
        assert name in CHECKS and CHECKS[name].__module__ == reads.__name__, name


def test_no_read_is_ok_by_default_against_nothing(world):
    # no subject, no stores, a community that answers nothing: a read that cannot tell says so
    for name in NAMES:
        got = run(name, world, subject="")
        if name == "onboard-gates-read":
            assert got.ok and "closed" in got.message                       # it reads (information), and every gate reads closed
        elif name == "record-slots-read":
            assert got.ok and "empty" in got.message                # it reads the catalog's slots: all of them empty
        elif name == "scratch-room":
            assert got.message and "scratch is on" in got.message   # it reads the machine, not the run: it says what it found
        else:
            assert not got.ok and got.message, name


# --- the active community ---------------------------------------------------------------------------------------------------

def test_the_active_community_is_the_one_the_run_is_about(world):
    got = run("active-community", world)
    assert got.ok and "example" in got.message
    assert run("active-community", world, subject="example").ok                    # a bare handle is the profile key too


def test_another_community_fails_and_says_which(world):
    got = run("active-community", world, subject="association:other")
    assert not got.ok and "example" in got.message and "other" in got.message


def test_no_profile_in_the_subject_or_no_community_chosen_fails(world, monkeypatch):
    assert not run("active-community", world, subject="campaign:EX-1").ok
    from jason.community import profile

    def none_chosen():
        raise profile.CommunityNotChosen("none is chosen")

    monkeypatch.setattr(profile, "resolve_community", none_chosen)
    got = run("active-community", world)
    assert not got.ok and "no community is chosen" in got.message


# --- the onboarding checklist and its gates ---------------------------------------------------------------------------------

def patch_checklist(monkeypatch, *, with_missing_fillable=True):
    """Three items and five gates: start and establish wait on an item the community answers, ingest on one it cannot answer
    (a command could read it), operate on a fact only a person supplies, adopt on nothing."""
    items = [
        ob.OnboardingItem("have-units", ob.Group.MEMBERS, "Units", "why", (ob.Source.BOARD,), "units", (ob.Method("units"),),
                          fetch="jason sync-catalog"),
        ob.OnboardingItem("person-fact", ob.Group.MEMBERS, "A fact", "why", (ob.Source.BOARD,), "facts", (ob.Fact("person-fact"),)),
    ]
    if with_missing_fillable:
        items.append(ob.OnboardingItem("no-such", ob.Group.MEMBERS, "Nothing", "why", (ob.Source.BOARD,), "x",
                                       (ob.Method("nothing_here"),), fetch="jason nothing"))
    gate = lambda stage, keys: ob.Gate(stage, f"The {stage.value} gate", f"opens when {', '.join(keys) or 'nothing waits'}", keys)  # noqa: E731
    gates = (gate(ob.Stage.START, ("have-units",)), gate(ob.Stage.INGEST, ("no-such",) if with_missing_fillable else ("person-fact",)),
             gate(ob.Stage.ESTABLISH, ("have-units",)), gate(ob.Stage.OPERATE, ("person-fact",)), gate(ob.Stage.ADOPT, ()))
    monkeypatch.setattr(ob, "ITEMS", tuple(items))
    monkeypatch.setattr(ob, "GATES", gates)


COMMUNITY = SimpleNamespace(units=lambda: ("100 Example Way", "102 Example Way"))


def test_a_gate_reads_open_when_its_items_are_present_and_closed_with_the_keys_it_waits_on(world, monkeypatch):
    patch_checklist(monkeypatch)
    for stage in ("start", "establish", "adopt"):
        got = run(f"onboard-gate-{stage}", world, community=COMMUNITY)
        assert got.ok and f"the {stage} gate reads open" in got.message, stage
    ingest = run("onboard-gate-ingest", world, community=COMMUNITY)
    assert not ingest.ok and "reads closed" in ingest.message and "no-such missing" in ingest.message
    operate = run("onboard-gate-operate", world, community=COMMUNITY)
    assert not operate.ok and "person-fact missing" in operate.message
    assert "the board decides" in operate.message                                 # the read says what is missing; the board decides


def test_the_gates_read_counts_and_says_which_gates_are_open(world, monkeypatch):
    patch_checklist(monkeypatch)
    got = run("onboard-gates-read", world, community=COMMUNITY)
    assert got.ok
    assert "3 checklist items: 1 present, 0 partial, 2 missing" in got.message
    assert "start open, ingest closed, establish open, operate closed, adopt open" in got.message


def test_the_checklist_passes_only_when_what_is_missing_is_a_persons_to_supply(world, monkeypatch):
    patch_checklist(monkeypatch)
    got = run("onboard-checklist", world, community=COMMUNITY)
    assert not got.ok and "no-such" in got.message and "person-fact" not in got.message.split(";")[0]
    patch_checklist(monkeypatch, with_missing_fillable=False)
    got = run("onboard-checklist", world, community=COMMUNITY)
    assert got.ok and "1 missing or partial are a person's to supply" in got.message
    assert "the schedule's owners are not read here" in got.message              # the half of the step it cannot read, said so


def test_a_gate_of_another_community_is_not_read(world, monkeypatch):
    patch_checklist(monkeypatch)
    for name in ("onboard-gates-read", "onboard-gate-start", "onboard-checklist"):
        got = run(name, world, subject="association:other", community=COMMUNITY)
        assert not got.ok and "not the run's other" in got.message and "nothing was read" in got.message, name


def test_a_checklist_that_cannot_be_read_fails_with_the_reason(world, monkeypatch):
    import jason.tasks.onboarding as task

    def broken(*args, **kwargs):
        raise OSError("the disk is gone")

    monkeypatch.setattr(task, "load_context", broken)
    for name in ("onboard-gates-read", "onboard-checklist", *(f"onboard-gate-{g}" for g in GATES)):
        got = run(name, world, community=COMMUNITY)
        assert not got.ok and "the checklist cannot be read (OSError: the disk is gone)" in got.message, name


def test_a_damaged_question_queue_fails_the_checklist_reads_and_never_raises(world, monkeypatch):
    patch_checklist(monkeypatch)
    (world / "intake").mkdir()
    (world / "intake" / "asks.json").write_text("{", encoding="utf-8")
    for name in ("onboard-gates-read", "onboard-gate-start"):
        got = run(name, world, community=COMMUNITY)
        assert not got.ok and "cannot be read" in got.message, name


# --- the record checklist ----------------------------------------------------------------------------------------------------

def test_the_record_checklist_is_read_and_its_slots_counted(world):
    got = run("record-slots-read", world, community=Association())
    assert got.ok and " slots (" in got.message and "empty" in got.message
    assert "some slots hold nothing yet" in got.message                              # nothing is pinned or answered in an empty folder


def test_a_record_checklist_that_cannot_be_read_fails_with_the_reason(world, tmp_path):
    # the checklist reads a damaged store as an empty one; the read does not
    (world / "library").mkdir()
    (world / "library" / "library.db").write_bytes(b"this is not a database")
    got = run("record-slots-read", world, community=Association())
    assert not got.ok and "cannot be read" in got.message
    (world / "library" / "library.db").unlink()
    (tmp_path / "spec" / "example").mkdir()
    (tmp_path / "spec" / "example" / "records.json").write_text("[1, 2]", encoding="utf-8")
    got = run("record-slots-read", world, community=Association())
    assert not got.ok and "cannot be read" in got.message
    (tmp_path / "spec" / "example" / "records.json").write_text("{", encoding="utf-8")
    assert not run("record-slots-read", world, community=Association()).ok
    (tmp_path / "spec" / "example" / "records.json").unlink()
    assert run("record-slots-read", world, community=Association()).ok
    assert not run("record-slots-read", world, subject="association:other", community=Association()).ok


# --- one key document --------------------------------------------------------------------------------------------------------

def test_a_key_document_entry_is_read_with_its_status_and_a_file_is_counted_never_named(world):
    got = run("key-document-status", world, subject="entry:bylaws", community=Association())
    assert got.ok and "entry bylaws is expected" in got.message and "0 link(s)" in got.message
    KeyDocumentStore(world, "example").link("bylaws", LinkKind.DRIVE, "abcdefghijkl", by=BY, name="Private-Statement-2099.pdf")
    got = run("key-document-status", world, subject="entry:bylaws", community=Association())
    assert got.ok and "entry bylaws is linked" in got.message and "1 link(s)" in got.message
    assert "Private-Statement" not in got.message and "abcdefghijkl" not in got.message
    assert got.evidence and got.evidence[0].startswith("file:key-documents/example.json@")


def test_an_entry_that_is_not_on_the_list_or_a_list_that_cannot_be_read_fails(world):
    got = run("key-document-status", world, subject="entry:amendments/2099-0000001", community=Association())
    assert not got.ok and "is not on the key documents list" in got.message
    assert not run("key-document-status", world, subject="association:example", community=Association()).ok       # no entry named
    (world / "key-documents").mkdir()
    (world / "key-documents" / "example.json").write_text('{"entries": 5}', encoding="utf-8")
    got = run("key-document-status", world, subject="entry:bylaws", community=Association())
    assert not got.ok and "cannot be read" in got.message


# --- the last ingest ---------------------------------------------------------------------------------------------------------

def write_report(data, **over):
    report = {"day": "2099-01-02", "mode": "applied", "counts": {"files": 10, "distinct": 9, "new": 8, "filed": 6, "versions": 1,
                                                                   "byStatus": {"held: needs a kind": 2}},
              "questions": [{"id": "q-open"}], "parked": True, "versions": [], "moved": []}
    report.update(over)
    (data / "onboarding").mkdir(exist_ok=True)
    (data / "onboarding" / f"ingest-{report['day']}.json").write_text(json.dumps(report), encoding="utf-8")


def park(data, status):
    ask = Ask("q-open", AskKind.CLASSIFY, "library:example/file", "What kind is it?", status=status)
    intake.save(data, [ask])


def test_an_applied_ingest_with_no_question_open_passes(world):
    write_report(world)
    park(world, AskStatus.ANSWERED)
    got = run("ingest-gate", world)
    assert got.ok and "6 filed, 2 held, 1 version(s) found, 1 question(s)" in got.message
    assert any(e.startswith("glob:onboarding/ingest-*.json@") for e in got.evidence)


def test_a_dry_run_an_open_question_or_no_report_fails(world):
    assert not run("ingest-gate", world).ok and "nothing was ever ingested" in run("ingest-gate", world).message
    write_report(world, mode="dry run")
    got = run("ingest-gate", world)
    assert not got.ok and "dry run" in got.message
    write_report(world, mode="applied")
    park(world, AskStatus.OPEN)
    got = run("ingest-gate", world)
    assert not got.ok and "1 of its questions are still open" in got.message
    write_report(world, parked=False)
    got = run("ingest-gate", world)
    assert not got.ok and "not parked" in got.message


def test_an_ingest_report_or_queue_that_cannot_be_read_fails_with_the_reason(world):
    write_report(world)
    (world / "intake").mkdir()
    (world / "intake" / "asks.json").write_text("{", encoding="utf-8")
    got = run("ingest-gate", world)
    assert not got.ok and "cannot be read" in got.message
    (world / "intake" / "asks.json").unlink()
    (world / "onboarding" / "ingest-2099-01-02.json").write_text("not json", encoding="utf-8")
    assert not run("ingest-gate", world).ok


# --- a draft split -----------------------------------------------------------------------------------------------------------

def make_draft(data, *, status="draft", parts=2):
    session = SplitSession(new_id(), Source("ab" * 32, 1000, 12), "draft", "2099-01-01T00:00:00+00:00", "2099-01-01T00:00:00+00:00", BY)
    session.mark(1, by=BY)
    for page in (5, 9)[: parts - 1]:
        session.mark(page, by=BY)
    session.status = status
    split_session.save(data, session)
    return session.id


def test_a_draft_is_reviewed_by_its_counts_and_the_flags_are_listed_not_failed(world):
    sid = make_draft(world)
    got = run("split-review", world, subject=f"draft:{sid}")
    assert got.ok and f"draft {sid} is draft: 12 pages, 2 part(s)" in got.message
    assert "flags" in got.message                                                    # read or said why not, never a verdict


def test_a_declined_stale_missing_or_damaged_draft_fails(world):
    for status in ("declined", "stale"):
        sid = make_draft(world, status=status)
        got = run("split-review", world, subject=f"draft:{sid}")
        assert not got.ok and status in got.message
    assert not run("split-review", world, subject="draft:deadbeef").ok
    assert not run("split-review", world, subject="draft:not-an-id").ok
    assert not run("split-review", world, subject="association:example").ok
    sid = make_draft(world)
    split_session.session_file(world, sid).write_text("{", encoding="utf-8")
    got = run("split-review", world, subject=f"draft:{sid}")
    assert not got.ok and "cannot be read" in got.message


# --- round two: scratch, the profile's own facts, a verified key document, a request's kinds, a pick compared ---------------------

def run_item(name, data, subject="association:example", item="", community=None):
    readers = StoreReaders(data, community=community if community is not None else SimpleNamespace(), today=date(2099, 1, 1))
    return CHECKS[name](readers, view(subject), item)


def fake_report(free_gb=500, **more):
    gb = 1024 ** 3
    rep = {"places": [{"name": "data directory", "drive": "C:", "free": free_gb * gb},
                      {"name": "temp (JASON_TEMP_DIR)", "drive": "D:", "free": 900 * gb},
                      {"name": "ASSPY_HOME (county index cache)", "drive": "D:", "free": 900 * gb}],
           "problems": [], "minFreeGb": 20.0}
    rep.update(more)
    return lambda *a, **k: rep


def test_scratch_on_a_roomy_drive_passes_and_names_drives_and_gigabytes_never_a_path(world, monkeypatch):
    monkeypatch.setattr("jason.storage.report", fake_report())
    got = run("scratch-room", world, subject="")
    assert got.ok and "scratch is on D: with 900 GB free" in got.message and "county cache is on D: with 900 GB free" in got.message
    assert "data folder is on C: with 500 GB free" in got.message and "floor is 20 GB" in got.message and "no drive is short of room" in got.message
    assert "\\" not in got.message and "/" not in got.message


def test_a_drive_short_of_room_or_a_report_that_cannot_be_made_fails_and_counts_the_problems(world, monkeypatch):
    monkeypatch.setattr("jason.storage.report", fake_report(problems=["C: has 3.0 GB free, under 20 GB", "JASON_TEMP_DIR is unset"]))
    got = run("scratch-room", world, subject="")
    assert not got.ok and "2 problem(s): jason storage --check says which" in got.message and "C: has 3.0" not in got.message

    def broken(*a, **k):
        raise OSError("the drive is gone")

    monkeypatch.setattr("jason.storage.report", broken)
    got = run("scratch-room", world, subject="")
    assert not got.ok and "cannot be made (OSError: the drive is gone)" in got.message
    monkeypatch.setattr("jason.storage.report", fake_report(places=[{"name": "data directory", "drive": "C:", "free": None}]))
    assert "none set" in run("scratch-room", world, subject="").message


def test_the_real_storage_report_is_read_without_writing_anything(world):
    before = tree(world)
    got = run("scratch-room", world, subject="")
    assert got.message and "scratch is on" in got.message
    assert tree(world) == before


def test_the_profiles_topics_in_its_own_folder_pass_and_none_yet_is_said(world, tmp_path):
    got = run("profile-own-facts", world)
    assert got.ok and "0 topic file(s) for the profile: 0 in its own folder, 0 in the old shared layout" in got.message
    assert "its own facts file is not there yet" in got.message
    (tmp_path / "spec" / "example").mkdir()
    (tmp_path / "spec" / "example" / "records.json").write_text("{}", encoding="utf-8")
    (tmp_path / "spec" / "example" / "senders.json").write_text("{}", encoding="utf-8")
    (tmp_path / "spec" / "example.json").write_text("{}", encoding="utf-8")
    got = run("profile-own-facts", world)
    assert got.ok and "2 topic file(s) for the profile: 2 in its own folder, 0 in the old shared layout" in got.message
    assert "its own facts file is there" in got.message and "records" not in got.message and "senders" not in got.message


def test_a_topic_read_from_the_old_shared_layout_fails_and_another_community_is_not_read(world, tmp_path, monkeypatch):
    monkeypatch.setattr("jason.community.private.default_profile", lambda: "example")        # the old layout is the default profile's
    (tmp_path / "spec" / "senders.json").write_text("{}", encoding="utf-8")
    got = run("profile-own-facts", world)
    assert not got.ok and "1 in the old shared layout" in got.message and "jason spec --migrate" in got.message
    got = run("profile-own-facts", world, subject="association:other")
    assert not got.ok and "not the run's other" in got.message
    assert not run("profile-own-facts", world, subject="").ok and "names no profile" in run("profile-own-facts", world, subject="").message


def entry_listing(*entries):
    return {"found": True, "groups": [{"item": "x", "entries": list(entries)}]}


def entry(key="amendments/2099-0000001", number="2099-0000001", copies=()):
    return {"key": key, "number": number, "status": "held", "copies": list(copies), "links": []}


def test_an_entry_with_a_number_and_a_recorded_copy_on_disk_is_verified_and_nothing_is_named(world, monkeypatch):
    listing = entry_listing(entry("amendments/first", number="2099-0000009",
                                  copies=[{"kind": "disk", "name": "Secret-Name.pdf", "ref": "x/secret.pdf"},
                                          {"kind": "drive", "name": "Drive-Copy.pdf", "ref": "abc"}]))
    monkeypatch.setattr("jason.tasks.key_documents.checklist", lambda *a, **k: listing)
    got = run("key-document-verified", world, subject="entry:amendments/first")
    assert got.ok and "has a recording number" in got.message and "1 recorded copy(ies) on disk carry it" in got.message
    assert "1 other copy(ies) are pinned" in got.message and "2099-0000009" not in got.message and "Secret" not in got.message


def test_an_entry_with_no_number_or_no_recorded_copy_on_disk_is_not_verified(world, monkeypatch):
    monkeypatch.setattr("jason.tasks.key_documents.checklist",
                        lambda *a, **k: entry_listing(entry("amendments/a", number=""), entry("amendments/b", copies=[{"kind": "drive"}])))
    got = run("key-document-verified", world, subject="entry:amendments/zzz")
    assert not got.ok and got.message == "entry amendments/zzz is not on the key documents list (2 entries read)"
    got = run("key-document-verified", world, subject="entry:")
    assert not got.ok and "names no key document entry" in got.message
    none = run("key-document-verified", world, subject="entry:amendments/a")
    assert not none.ok and "has no recording number: it is noted as not recorded" in none.message
    unmatched = run("key-document-verified", world, subject="entry:amendments/b")
    assert not unmatched.ok and "no recorded copy has been matched to the number yet" in unmatched.message


def test_a_key_document_list_that_cannot_be_read_or_another_community_fails(world, monkeypatch):
    got = run("key-document-verified", world, subject="entry:bylaws", community=Association())
    assert not got.ok and ("is not on the key documents list" in got.message or "no recording number" in got.message)

    def broken(*a, **k):
        raise OSError("the store is gone")

    monkeypatch.setattr("jason.tasks.key_documents.checklist", broken)
    got = run("key-document-verified", world, subject="entry:bylaws")
    assert not got.ok and "cannot be read (OSError: the store is gone)" in got.message


def open_request(world, *kinds):
    from jason.tasks import records_requests

    return records_requests.open_request(world, "2099-01-05", "123 Main St", "email", list(kinds), by=BY).id


def test_each_kind_a_request_asks_for_maps_to_a_paragraph_and_a_slot_and_no_kind_is_named(world):
    rid = open_request(world, "minutes", "financial_disclosure")
    got = run("request-kinds-mapped", world, subject=f"request:{rid}", community=Association())
    assert got.ok and "2 of 2 kind(s) asked map to a paragraph of CIV 5200(a) and a slot of the record checklist" in got.message
    assert "empty" in got.message and "minutes" not in got.message and "financial" not in got.message and "123 Main" not in got.message
    assert got.evidence and got.evidence[0].startswith("file:records-requests/requests.json@")
    one = run_item("request-kinds-mapped", world, subject=f"request:{rid}", item="minutes", community=Association())
    assert one.ok and "1 of 1 kind(s)" in one.message


def test_a_kind_with_no_slot_a_missing_request_or_no_handle_fails(world, monkeypatch):
    rid = open_request(world, "minutes")
    other = run_item("request-kinds-mapped", world, subject=f"request:{rid}", item="tax_return", community=Association())
    assert not other.ok and "does not ask for that kind" in other.message
    assert "no such request" in run("request-kinds-mapped", world, subject="request:2099-01-01--nobody", community=Association()).message
    assert not run("request-kinds-mapped", world, subject="", community=Association()).ok
    monkeypatch.setattr("jason.tasks.record_slots.view", lambda *a, **k: {"groups": [{"slots": [{"key": "k", "state": "empty", "requires": ["CIV 4000"]}]}]})
    got = run("request-kinds-mapped", world, subject=f"request:{rid}", community=Association())
    assert not got.ok and "0 of 1 kind(s)" in got.message and "a miss stays a miss" in got.message


def slot_with(monkeypatch, world, pins, readings):
    monkeypatch.setattr("jason.tasks.record_slots.slot_view", lambda key, *a, **k: {"found": key == "governing/bylaws", "holders": [
        {"pin": p, "kind": "file"} for p in pins] + [{"pin": "folder-1", "kind": "folder"}]})
    monkeypatch.setattr("jason.tasks.record_readback.load", lambda root, profile, pin: readings.get(pin))


def test_every_pin_with_a_kept_reading_passes_whatever_the_verdicts_and_a_difference_is_said(world, monkeypatch):
    slot_with(monkeypatch, world, ("p1", "p2", "p3"), {"p1": {"compare": {"verdict": "agrees"}}, "p2": {"compare": {"verdict": "differs"}},
                                                      "p3": {"compare": {"verdict": "unclassified"}}})
    got = run_item("record-compare", world, item="governing/bylaws")
    assert got.ok and "3 pinned file(s)" in got.message and "1 agree with the slot, 1 differ, 1 are unclassified, 0 not read yet" in got.message
    assert "resolved in the next step" in got.message and "p1" not in got.message


def test_a_pin_not_read_yet_or_a_slot_with_no_pin_or_no_item_fails(world, monkeypatch):
    slot_with(monkeypatch, world, ("p1", "p2"), {"p1": {"compare": {"verdict": "agrees"}}, "p2": {}})
    got = run_item("record-compare", world, item="governing/bylaws")
    assert not got.ok and "1 not read yet" in got.message and "jason records --read KEY" in got.message
    slot_with(monkeypatch, world, (), {})
    assert "nothing to compare" in run_item("record-compare", world, item="governing/bylaws").message
    assert "not a slot of the record checklist" in run_item("record-compare", world, item="nope").message
    assert "one slot at a time" in run_item("record-compare", world, item="").message
    assert not run_item("record-compare", world, subject="association:other", item="governing/bylaws").ok


def test_a_slot_that_cannot_be_read_fails_with_the_reason(world, monkeypatch):
    def broken(*a, **k):
        raise OSError("the pins are gone")

    monkeypatch.setattr("jason.tasks.record_slots.slot_view", broken)
    got = run_item("record-compare", world, item="governing/bylaws")
    assert not got.ok and "cannot be compared (OSError: the pins are gone)" in got.message


# --- a read writes nothing ----------------------------------------------------------------------------------------------------

def test_every_read_leaves_the_data_folder_and_the_private_facts_byte_for_byte_as_they_were(world, monkeypatch, tmp_path):
    patch_checklist(monkeypatch)
    write_report(world)
    park(world, AskStatus.OPEN)
    KeyDocumentStore(world, "example").link("bylaws", LinkKind.DRIVE, "abcdefghijkl", by=BY, name="Private-Statement-2099.pdf")
    sid = make_draft(world)
    (tmp_path / "spec" / "example").mkdir()
    (tmp_path / "spec" / "example" / "records.json").write_text(json.dumps({"pins": [], "answers": []}), encoding="utf-8")
    before, spec_before = tree(world), tree(tmp_path / "spec")
    assert len(before) >= 4
    subjects = {"key-document-status": "entry:bylaws", "split-review": f"draft:{sid}"}
    for name in NAMES:
        community = (Association() if name in ("record-slots-read", "key-document-status", "split-review", "key-document-verified",
                                                "request-kinds-mapped", "record-compare") else COMMUNITY)
        run(name, world, subject=subjects.get(name, "association:example"), community=community)
    assert tree(world) == before
    assert tree(tmp_path / "spec") == spec_before


def test_a_read_has_no_network_or_profile_in_its_imports():
    import ast

    tree_ = ast.parse(Path(reads.__file__).read_text(encoding="utf-8"))
    names = {n.module for n in ast.walk(tree_) if isinstance(n, ast.ImportFrom) and n.module}
    names |= {a.name for n in ast.walk(tree_) if isinstance(n, ast.Import) for a in n.names}
    assert not any(n.split(".")[0] in ("payhoa", "requests", "httpx", "anthropic", "mystique", "jason_mystique") for n in names)
    assert not any(n.startswith(("jason.google", "jason.keeper", "jason.vault", "jason.web", "jason.zoom")) for n in names)
