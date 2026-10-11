"""The platform family's reads of the integration state, the limits, the storage and the recognition of an arrival
(src/jason/workflows/checks/platform.py: ``responses-recognized``, ``integration-state``, ``service-limits``,
``service-verify``), each in a temporary data folder over made-up stores. Nothing is called outside: no PayHOA, Google, Keeper,
network, or service, and no vault is asked. A test pins that every read leaves the data folder exactly as it was, that an
unreadable store gives ``ok=False`` and never an exception, and that a message holds counts, states, and dates but no name,
account, error text, or reason.
"""

from __future__ import annotations

import re
from datetime import date
from types import SimpleNamespace

import pytest

from jason.community.response_inbox import Arrival, Channel
from jason.tasks import form_references
from jason.tasks import response_inbox as ri
from jason.workflows import checks
from jason.workflows.checks import platform as plat
from jason.workflows.readers import CHECKS, StoreReaders
from test_workflows_checks_platform import beat, populate, put, run, stamp, tree
from test_workflows_support import data  # noqa: F401 - the `data` fixture

TODAY = date(2099, 10, 1)
NEW_NAMES = ("responses-recognized", "integration-state", "service-limits", "service-verify")
GB = 1024 ** 3


def stub_community():
    """A profile with nothing to say: no limits of its own and no sign-in or portal rows."""
    return SimpleNamespace(limits=lambda: {}, sign_in=lambda: (), vendor_portals=lambda: (), slug="example_hoa")


@pytest.fixture
def more(data, monkeypatch):
    """A data folder, an instance limits file beside it, no settings, and plenty of room on every drive."""
    data.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("JASON_LIMITS_FILE", str(data.parent / "instance-limits.json"))
    monkeypatch.setattr(plat, "_settings", lambda: None)
    monkeypatch.setattr(plat, "_free", lambda path: 100 * GB)
    return StoreReaders(data, community=stub_community(), today=TODAY)


def test_the_four_new_reads_are_registered_by_name():
    checks.load_all()
    assert set(NEW_NAMES) <= set(CHECKS) and all(callable(CHECKS[n]) for n in NEW_NAMES)


# --- responses-recognized ------------------------------------------------------------------------------------------------

def arrival(data, arrival_id, channel, *, summary="Re: the form", who="Owner Example", unit="1 Example Way"):
    inbox = ri.load_inbox(data)
    inbox.arrivals[arrival_id] = Arrival(arrival_id, "annual-info", channel, "2099-09-30T10:00:00+00:00", who, unit, summary)
    ri.save_inbox(data, inbox)
    return inbox.arrivals[arrival_id]


def reference(membership_id=1, unit_id=2):
    from jason.community.form_refs import Channel as Via, make

    return make("KM", 2027, Via.EMAIL, membership_id=membership_id, unit_id=unit_id).text


def test_responses_recognized_reads_the_subject_of_an_arrival_not_yet_read(data, more):
    ref = reference()
    form_references.record(data, ref, form="annual-info", year=2027, membershipId=1, unitId=2, unit="1 Example Way", channel="email")
    arrival(data, "gmail:a1", Channel.GMAIL, summary=f"Re: your form {ref}")
    arrival(data, "gmail:a2", Channel.GMAIL, summary="Question about the pool")
    arrival(data, "gmail:a3", Channel.GMAIL, summary=f"Re: {reference(9, 9)}")                 # a marker no copy of ours carries
    hit = run("responses-recognized", more, item="gmail:a1")
    assert hit.ok and hit.message.startswith("recognized by rung 1 (subject), how sure:") and "not yet read" in hit.message
    undecided = run("responses-recognized", more, item="gmail:a2")
    assert undecided.ok and undecided.message.startswith("not decided") and "not ours" not in undecided.message
    unsent = run("responses-recognized", more, item="gmail:a3")
    assert unsent.ok and unsent.message.startswith("not ours by its subject")
    for got in (hit, undecided, unsent):
        assert got.evidence and got.evidence[0].startswith("file:responses/inbox.json@")
        for word in ("Owner Example", "Example Way", "pool", ref):
            assert word not in got.message


def test_responses_recognized_prefers_the_stored_reading_and_says_the_rung(data, more):
    a = arrival(data, "gmail:r1", Channel.GMAIL)
    where = ri.reading_path(data, a).relative_to(data).as_posix()
    put(data, where, {"id": a.id, "recognition": {"outcome": "candidate", "rung": "layout", "rungNumber": 5, "sure": "medium",
                                                  "note": "Owner Example"}})
    got = run("responses-recognized", more, item="gmail:r1")
    assert got.ok and got.message.startswith("candidate by rung 5 (layout), how sure: medium (from its reading)")
    assert "Owner Example" not in got.message and len(got.evidence) == 2
    put(data, where, {"id": a.id, "recognition": {"outcome": "maybe"}})
    assert not run("responses-recognized", more, item="gmail:r1").ok
    put(data, where, "{broken")
    assert run("responses-recognized", more, item="gmail:r1").message.startswith("not decided")     # an unreadable reading is none


def test_responses_recognized_has_nothing_to_find_for_a_structured_or_keyed_arrival(data, more):
    arrival(data, "payhoa:1001", Channel.PAYHOA)
    arrival(data, "forms:9", Channel.FORMS)
    arrival(data, "manual:1", Channel.MANUAL)
    assert "a payhoa arrival" in run("responses-recognized", more, item="payhoa:1001").message
    assert "a forms arrival" in run("responses-recognized", more, item="forms:9").message
    assert "keyed by a person" in run("responses-recognized", more, item="manual:1").message


def test_responses_recognized_fails_for_no_item_an_unknown_arrival_or_an_unreadable_inbox(data, more):
    assert "names no arrival" in run("responses-recognized", more).message
    assert not run("responses-recognized", more, item="gmail:nope").ok and not (data / "responses").exists()
    put(data, "responses/inbox.json", "{broken")
    assert not run("responses-recognized", more, item="gmail:a1").ok


# --- integration-state ---------------------------------------------------------------------------------------------------

def connection(data, key="postscanmail", **fields):
    from jason.integrations import connections

    connections.save("example_hoa", [connections.Connection("example_hoa", key, **fields)], data / connections.FILE)


def keeper(tmp_path):
    login = tmp_path / "keeper-config.json"
    login.write_text("{}", encoding="utf-8")
    return login


SUBJECT = "integration:postscanmail"


def test_integration_state_walks_from_not_set_up_to_connected(data, more, monkeypatch, tmp_path):
    first = run("integration-state", more, subject=SUBJECT)
    assert first.ok and first.message.startswith("not set up; its credential is not set; 1 source(s): 1 never read; never checked")
    assert "the vault was not asked" in first.message
    monkeypatch.setattr(plat, "_settings", lambda: SimpleNamespace(postscanmail_record_uid="a-record", keeper_config=str(tmp_path / "gone.json")))
    assert run("integration-state", more, subject=SUBJECT).message.startswith("needs sign-in; its credential is set")
    monkeypatch.setattr(plat, "_settings", lambda: SimpleNamespace(postscanmail_record_uid="a-record", keeper_config=str(keeper(tmp_path))))
    assert run("integration-state", more, subject=SUBJECT).message.startswith("not set up; its credential is set")      # not read: not proved
    put(data, "mail/items.json", {"syncedAt": stamp(days=1), "items": []})
    done = run("integration-state", more, subject=SUBJECT)
    assert done.ok and done.message.startswith("connected; its credential is set; 1 source(s): 1 current; last read 2099-09-30")
    assert "never checked" in done.message
    put(data, "mail/items.json", {"syncedAt": stamp(days=9), "items": []})
    assert run("integration-state", more, subject=SUBJECT).message.startswith("connected; its credential is set; 1 source(s): 1 stale")


def test_integration_state_reads_a_failed_check_and_a_pause_without_repeating_their_words(data, more, monkeypatch, tmp_path):
    from jason.integrations.registry import ConnectionState

    monkeypatch.setattr(plat, "_settings", lambda: SimpleNamespace(postscanmail_record_uid="a-record", keeper_config=str(keeper(tmp_path))))
    put(data, "mail/items.json", {"syncedAt": stamp(days=2), "items": []})
    connection(data, state=ConnectionState.CONNECTED, last_checked=stamp(days=1), last_check="failed: HTTP 500 for key AbC123secret")
    failing = run("integration-state", more, subject=SUBJECT)
    assert failing.ok and failing.message.startswith("failing") and "last check failed on 2099-09-30" in failing.message
    assert "AbC123secret" not in failing.message and "500" not in failing.message
    assert failing.evidence and failing.evidence[0].startswith("file:integrations.json@")
    connection(data, state=ConnectionState.PAUSED, note="paused by A. Admin: vendor outage", last_checked=stamp(days=1), last_check="ok: read")
    paused = run("integration-state", more, item="postscanmail")                      # the item names it too
    assert paused.message.startswith("paused") and "A. Admin" not in paused.message and "outage" not in paused.message


def test_integration_state_fails_for_no_integration_an_unknown_one_or_an_unreadable_store(data, more):
    assert "names no integration" in run("integration-state", more, subject="").message
    assert "not an integration" in run("integration-state", more, subject="integration:nope").message
    assert not run("integration-state", more, subject="request:postscanmail").ok
    put(data, "integrations.json", "{broken")
    assert not run("integration-state", more, subject=SUBJECT).ok


def test_integration_state_reads_an_instance_integration_from_the_installations_store(data, more, monkeypatch, tmp_path):
    from jason.integrations import connections

    monkeypatch.setattr(connections, "store_path", lambda community, env_file=None: tmp_path / "instance" / "integrations.json")
    got = run("integration-state", more, subject="integration:instance-sign-in")
    assert got.ok and got.message.startswith("not set up") and not got.evidence
    assert not (tmp_path / "instance").exists()                                       # the installation's store is not made


# --- service-limits ------------------------------------------------------------------------------------------------------

def test_service_limits_counts_the_limits_and_names_each_one_that_is_not_the_codes_default(data, more):
    import jason.limits as limits

    plain = run("service-limits", more)
    assert plain.ok and plain.message.endswith("; last change none on record")
    assert plain.message.startswith(f"{len(limits.LIMITS)} limit(s) in force: {len(limits.LIMITS)} default") and "set:" not in plain.message
    inst = data.parent / "instance-limits.json"
    limits.set_limits({"split.max_pages": 1000}, scope="community", reason="a longer scan", by="A. Admin", dry_run=False,
                      community=more.community, data_folder=data, instance_file=inst)
    limits.set_limits({"split.max_parts": 100}, scope="instance", reason="a smaller split", by="O. Operator", dry_run=False,
                      role=limits.ROLE_INSTANCE, community=more.community, data_folder=data, instance_file=inst)
    got = run("service-limits", more)
    assert got.ok and "split.max_pages 1,000 (community, range 50 to 10,000, changed " in got.message
    assert "split.max_parts 100 (instance, range 2 to 2,000, changed " in got.message
    assert "1 instance, 1 community" in got.message
    for word in ("A. Admin", "a longer scan", "O. Operator", "a smaller split"):
        assert word not in got.message
    assert re.search(r"last change \d{4}-\d\d-\d\d", got.message) and got.evidence and got.evidence[0].startswith("file:limits.json@")


def test_service_limits_fails_on_a_limits_file_that_cannot_be_read_and_says_which(data, more):
    put(data, "limits.json", "{broken")
    got = run("service-limits", more)
    assert not got.ok and "cannot be read: this community's limits file" in got.message and "stricter" in got.message
    put(data.parent, "instance-limits.json", "[]")
    assert "the instance limits file" in run("service-limits", more).message


def test_service_limits_records_no_clamp_and_writes_nothing(data, more):
    put(data, "limits.json", {"version": 1, "limits": {"split.max_pages": {"value": 99999999, "by": "A. Admin", "at": "2099-09-01T00:00:00Z",
                                                                           "reason": "x"}}})
    before = tree(data)
    got = run("service-limits", more)
    assert got.ok and "1 held to its range" in got.message and "split.max_pages 10,000 (community" in got.message
    assert "changed 2099-09-01" in got.message
    assert tree(data) == before                                                       # no trail line, no lock file in the data folder


# --- service-verify ------------------------------------------------------------------------------------------------------

def test_service_verify_passes_with_a_fresh_heartbeat_roomy_drives_and_no_source_stale(data, more):
    beat(data, state="running", beat=stamp(seconds=10))
    put(data, "mail/items.json", {"syncedAt": stamp(hours=2), "items": []})
    first = run("service-verify", more)
    assert first.ok and "1 current" in first.message and "heartbeat running" in first.message
    assert "data drive at least 20 GB free; temp drive at least 20 GB free" in first.message
    beat(data, state="running", beat=stamp(seconds=25))
    assert run("service-verify", more) == first                                       # the clock alone changes nothing


def test_service_verify_counts_a_source_never_read_and_does_not_fail_for_it(data, more):
    beat(data, state="running", beat=stamp(seconds=10))
    got = run("service-verify", more)
    assert got.ok and "never read" in got.message and "current" not in got.message


def test_service_verify_fails_for_a_stale_source_a_stale_heartbeat_a_short_drive_or_a_missing_sign_in(data, more, monkeypatch, tmp_path):
    beat(data, state="running", beat=stamp(seconds=10))
    put(data, "mail/items.json", {"syncedAt": stamp(days=9), "items": []})
    stale = run("service-verify", more)
    assert not stale.ok and "1 stale" in stale.message
    put(data, "mail/items.json", {"syncedAt": stamp(hours=1), "items": []})
    assert run("service-verify", more).ok
    beat(data, state="running", beat=stamp(seconds=300))
    cold = run("service-verify", more)
    assert not cold.ok and "heartbeat stale" in cold.message
    beat(data, state="running", beat=stamp(seconds=10))
    monkeypatch.setattr(plat, "_free", lambda path: 5 * GB)
    short = run("service-verify", more)
    assert not short.ok and "data drive under 20 GB free" in short.message and "5." not in short.message
    monkeypatch.setattr(plat, "_free", lambda path: None)
    unreadable = run("service-verify", more)
    assert not unreadable.ok and "data drive not readable" in unreadable.message
    monkeypatch.setattr(plat, "_free", lambda path: 100 * GB)
    monkeypatch.setattr(plat, "_settings", lambda: SimpleNamespace(google_oauth_token_file=str(tmp_path / "no-token.json")))
    out = run("service-verify", more)
    assert not out.ok and "not signed in" in out.message


def test_service_verify_fails_with_no_heartbeat_and_reads_a_broken_store_as_a_failure(data, more):
    got = run("service-verify", more)
    assert not got.ok and "heartbeat none" in got.message
    put(data, "integrations.json", "{broken")
    assert not run("service-verify", more).ok


# --- the four, with the rest ---------------------------------------------------------------------------------------------

def test_the_four_new_reads_write_nothing_and_make_no_store(data, more):
    populate(data)
    arrival(data, "gmail:a2", Channel.GMAIL, summary="Question about the pool")
    put(data, "mail/items.json", {"syncedAt": stamp(hours=2), "items": []})
    before = tree(data)
    for name, kw in (("responses-recognized", {"item": "gmail:a2"}), ("integration-state", {"subject": SUBJECT}),
                     ("service-limits", {}), ("service-verify", {})):
        run(name, more, **kw)
    assert tree(data) == before
    empty = data.parent / "empty-new"
    empty.mkdir()
    bare = StoreReaders(empty, community=stub_community(), today=TODAY)
    for name in NEW_NAMES:
        run(name, bare, subject=SUBJECT, item="gmail:a2")
    assert tree(empty) == {}


def test_a_store_that_cannot_be_read_fails_each_of_the_new_reads_and_raises_nothing(data, more):
    for relative in ("responses/inbox.json", "integrations.json", "limits.json", "mail/items.json", "jobs/heartbeat.json"):
        put(data, relative, "\x00{garbage")
    put(data, "jobs.db", "garbage")
    for name, kw in (("responses-recognized", {"item": "gmail:a2"}), ("integration-state", {"subject": SUBJECT}),
                     ("service-limits", {}), ("service-verify", {})):
        got = run(name, more, **kw)
        assert not got.ok and got.message, name


def test_the_floor_copied_from_the_storage_report_still_matches_it():
    from jason import storage

    assert plat.DRIVE_FLOOR_GB == storage.DEFAULT_MIN_FREE_GB
