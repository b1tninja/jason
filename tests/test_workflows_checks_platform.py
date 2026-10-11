"""The platform family's reads (src/jason/workflows/checks/platform.py): each in a temporary data folder over made-up stores.

Everything is made up ("vendor.example", opaque thread and mail ids, dates in 2099); no real store, no network, no profile, no
service is contacted. A test pins that every read leaves the data folder exactly as it was (files and folders), that a store
that is missing or cannot be read gives ``ok=False`` and never an exception, and that a message names no sender, subject, or
address.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from types import SimpleNamespace

import pytest

from jason import jobs
from jason.community.response_inbox import Channel
from jason.tasks import form_references
from jason.tasks import mail_triage
from jason.tasks import response_inbox as ri
from jason.workflows import checks
from jason.workflows.checks import platform as plat
from jason.workflows.readers import CHECKS, StoreReaders
from jason.workflows.types import CheckResult
from test_workflows_support import data  # noqa: F401 - the `data` fixture

TODAY = date(2099, 10, 1)                      # the day a test is read on; a check judges freshness at noon UTC of it
NOON = datetime(2099, 10, 1, 12, 0, tzinfo=timezone.utc)
NAMES = ("mail-fresh", "mail-lanes", "mail-scanned", "mail-period-chosen", "gmail-fresh", "thread-status", "responses-channels",
         "responses-outstanding", "instance-which", "service-heartbeat", "service-queue")


def tree(root):
    """Every file and folder under a folder, files with their bytes: what a read must leave exactly as it was."""
    return {p.relative_to(root).as_posix(): (p.read_bytes() if p.is_file() else None) for p in sorted(root.rglob("*"))}


def put(data, relative, body):
    path = data / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body if isinstance(body, str) else json.dumps(body), encoding="utf-8")
    return path


def run(name, readers, *, subject="", item="", items=()):
    view = SimpleNamespace(id="run-test", subject=subject, items=tuple(items), opened_at="2099-01-01T00:00:00Z", dates={})
    out = CHECKS[name](readers, view, item)
    assert isinstance(out, CheckResult)
    return out


@pytest.fixture
def readers(data):
    data.mkdir(parents=True, exist_ok=True)
    return StoreReaders(data, community=None, today=TODAY)


def stamp(**delta):
    from datetime import timedelta

    return (NOON - timedelta(**delta)).isoformat(timespec="seconds")


# --- registration ---------------------------------------------------------------------------------------------------------

def test_the_eleven_reads_are_registered_by_name():
    checks.load_all()
    assert set(NAMES) <= set(CHECKS)
    assert all(callable(CHECKS[n]) for n in NAMES)


def test_the_figures_copied_from_their_sources_still_match_them():
    from jason import serve
    from jason.integrations.registry import REGISTRY

    sources = {c.source_key: c for i in REGISTRY for c in i.sources}
    assert plat.MAIL_STALE_AFTER == sources["mail"].stale_delta
    assert plat.GMAIL_STALE_AFTER == sources["gmail"].stale_delta
    assert plat.HEARTBEAT_BEAT_SECONDS == serve.BEAT_SECONDS and plat.HEARTBEAT_STALE_AFTER == serve.STALE_AFTER


# --- mail-fresh, gmail-fresh ----------------------------------------------------------------------------------------------

def test_mail_fresh_passes_within_three_days_and_fails_beyond_it_naming_the_command(data, readers):
    put(data, "mail/items.json", {"syncedAt": stamp(days=2), "items": []})
    ok = run("mail-fresh", readers)
    assert ok.ok and "within 3 days" in ok.message and ok.evidence and ok.evidence[0].startswith("file:mail/items.json@")
    put(data, "mail/items.json", {"syncedAt": stamp(days=4), "items": []})
    old = run("mail-fresh", readers)
    assert not old.ok and "more than 3 days ago" in old.message and "`jason mail`" in old.message


def test_gmail_fresh_passes_within_an_hour_and_fails_beyond_it(data, readers):
    put(data, "gmail/correspondence.json", {"syncedAt": stamp(minutes=30), "messages": []})
    assert run("gmail-fresh", readers).ok
    put(data, "gmail/correspondence.json", {"syncedAt": stamp(hours=2), "messages": []})
    stale = run("gmail-fresh", readers)
    assert not stale.ok and "more than 1 hour ago" in stale.message and "jason gmail --sync" in stale.message


@pytest.mark.parametrize("name, relative", [("mail-fresh", "mail/items.json"), ("gmail-fresh", "gmail/correspondence.json")])
def test_a_freshness_read_fails_on_a_missing_unreadable_or_unstamped_store(data, readers, name, relative):
    missing = run(name, readers)
    assert not missing.ok and "no" in missing.message and not (data / relative).exists()
    put(data, relative, "{not json")
    assert not run(name, readers).ok
    put(data, relative, {"items": []})
    assert "no read time" in run(name, readers).message
    put(data, relative, {"syncedAt": "yesterday-ish"})
    assert not run(name, readers).ok
    put(data, relative, "[1, 2]")
    assert not run(name, readers).ok


# --- mail-lanes ----------------------------------------------------------------------------------------------------------

def letter(mail_id, *, urgency="file", scanned=True, received="2099-09-25", kind="advertising"):
    return {"mailId": mail_id, "received": received, "sender": "Vendor Example", "kind": kind, "urgency": urgency, "scanned": scanned,
            "deadlines": [], "aiSummary": []}


def test_mail_lanes_counts_act_review_and_unscanned_and_names_no_sender(data, readers):
    put(data, "mail/items.json", {"syncedAt": stamp(hours=1), "items": [
        letter("m-1", urgency="act", kind="legal"), letter("m-2", urgency="review"), letter("m-3"),
        letter("m-4", scanned=False), letter("m-5", received="2098-01-01")]})
    got = run("mail-lanes", readers)
    assert got.ok and got.message.startswith("4 letter(s) in the last 30 days: 1 to act on, 1 to review, 2 other; 1 not scanned")
    assert "Vendor Example" not in got.message and "m-1" not in got.message


def test_mail_lanes_fails_with_no_mail_on_disk_or_an_unreadable_store(data, readers):
    assert not run("mail-lanes", readers).ok
    put(data, "mail/items.json", "{broken")
    assert not run("mail-lanes", readers).ok


# --- mail-scanned --------------------------------------------------------------------------------------------------------

def test_mail_scanned_ends_a_wait_only_for_a_letter_the_store_says_is_scanned(data, readers):
    put(data, "mail/items.json", {"syncedAt": stamp(hours=1), "items": [letter("m-1"), letter("m-2", scanned=False)]})
    done = run("mail-scanned", readers, item="m-1")
    assert done.ok and "m-1 is scanned" in done.message and "Vendor Example" not in done.message
    waiting = run("mail-scanned", readers, item="m-2")
    assert not waiting.ok and "not scanned yet" in waiting.message
    assert not run("mail-scanned", readers, item="m-9").ok
    assert "names no letter" in run("mail-scanned", readers).message


def test_mail_scanned_fails_when_the_store_is_missing_or_unreadable(data, readers):
    assert not run("mail-scanned", readers, item="m-1").ok
    put(data, "mail/items.json", "not json")
    assert not run("mail-scanned", readers, item="m-1").ok


# --- mail-period-chosen --------------------------------------------------------------------------------------------------

def test_mail_period_chosen_wants_a_recorded_choice_for_every_letter_of_the_run(data, readers):
    items = ("m-1", "m-2", "m-3")
    none = run("mail-period-chosen", readers, items=items)
    assert not none.ok and "0 of 3" in none.message and "m-1" in none.message
    mail_triage.choose(data, "m-1", choice="keep", by="A. Manager")
    mail_triage.choose(data, "m-2", choice="scan", by="A. Manager")
    part = run("mail-period-chosen", readers, items=items)
    assert not part.ok and "2 of 3" in part.message and "m-3" in part.message and "m-1" not in part.message
    mail_triage.choose(data, "m-3", choice="shred", by="A. Manager")
    full = run("mail-period-chosen", readers, items=items)
    assert full.ok and "3 of 3" in full.message and full.evidence
    assert run("mail-period-chosen", readers).ok                                  # a period with no letters has none left to choose


def test_mail_period_chosen_fails_on_an_unreadable_triage_record(data, readers):
    put(data, "mail/triage.json", "{broken")
    assert not run("mail-period-chosen", readers, items=("m-1",)).ok


# --- thread-status -------------------------------------------------------------------------------------------------------

def message(thread, at, direction, *, parties=("vendor.example",), sender="v@vendor.example", subject="Invoice question"):
    return {"messageId": f"{thread}-{at}", "threadId": thread, "at": at, "direction": direction, "domains": [], "parties": list(parties),
            "subject": subject, "people": [["Vendor Example", sender, "from"]], "attachments": []}


def gmail(data, *messages):
    put(data, "gmail/correspondence.json", {"syncedAt": stamp(minutes=5), "messages": list(messages)})


def test_thread_status_reads_whose_move_it_is_from_the_last_message(data, readers):
    gmail(data,
          message("t-us", "2099-09-28T10:00:00+00:00", "out"), message("t-us", "2099-09-29T10:00:00+00:00", "in"),
          message("t-them", "2099-09-28T10:00:00+00:00", "in"), message("t-them", "2099-09-29T10:00:00+00:00", "out"),
          message("t-int", "2099-09-28T10:00:00+00:00", "in", parties=("association",), sender="board@assoc.test"),
          message("t-note", "2099-09-28T10:00:00+00:00", "in", sender="no-reply@vendor.example", subject="Your statement"))
    expect = {"t-us": "awaiting us: 2 message(s), the last on 2099-09-29", "t-them": "awaiting them", "t-int": "internal",
              "t-note": "notice"}
    for thread, words in expect.items():
        got = run("thread-status", readers, subject=f"thread:{thread}")
        assert got.ok and got.message.startswith(words), (thread, got.message)
        assert "@" not in got.message and "Invoice question" not in got.message and "Vendor Example" not in got.message
        assert "an answer by phone" in got.message                                  # the caveat is always said
        assert got.evidence and got.evidence[0].startswith("file:gmail/correspondence.json@")
    assert run("thread-status", readers, item="t-them").message.startswith("awaiting them")     # an item names the thread too


def test_thread_status_fails_for_an_unknown_thread_a_missing_store_or_one_that_cannot_be_read(data, readers):
    assert not run("thread-status", readers, subject="thread:t-us").ok
    gmail(data, message("t-us", "2099-09-29T10:00:00+00:00", "in"))
    assert not run("thread-status", readers, subject="thread:nowhere").ok
    assert not run("thread-status", readers, subject="request:t-us").ok            # another kind of subject is no thread
    assert "names no thread" in run("thread-status", readers, subject="").message
    put(data, "gmail/correspondence.json", "{broken")
    assert not run("thread-status", readers, subject="thread:t-us").ok
    put(data, "gmail/correspondence.json", {"messages": [{"threadId": "t-us", "at": "2099-09-29"}]})   # a message missing its fields
    assert not run("thread-status", readers, subject="thread:t-us").ok


# --- responses-channels --------------------------------------------------------------------------------------------------

def inbox_with(data, **channels):
    ri.save_inbox(data, ri.Inbox(channels=channels))


def test_responses_channels_passes_when_every_channel_ended_ok_or_skipped(data, readers):
    inbox_with(data, payhoa={"ended": "ok", "lastOk": "2099-10-01T10:00:00+00:00", "lastTried": "2099-10-01T10:00:00+00:00"},
               gmail={"ended": "ok", "lastOk": "2099-10-01T09:00:00+00:00"}, mail={"ended": "skipped", "reason": "no request uses it"},
               forms={"ended": "skipped"})
    got = run("responses-channels", readers)
    assert got.ok and "gmail ok (last ok 2099-10-01T09:00)" in got.message and "mail skipped" in got.message
    assert "no request uses it" not in got.message                                  # a reason may hold a masked error: not repeated


def test_responses_channels_fails_on_a_sign_in_a_failure_or_a_channel_never_checked(data, readers):
    inbox_with(data, payhoa={"ended": "sign-in", "reason": "PayhoaAuthError: nope"}, gmail={"ended": "ok", "lastOk": "2099-10-01T09:00:00+00:00"},
               mail={"ended": "failed"}, forms={"ended": "ok"})
    got = run("responses-channels", readers)
    assert not got.ok and "payhoa sign-in" in got.message and "mail failed" in got.message and "PayhoaAuthError" not in got.message
    inbox_with(data, gmail={"ended": "ok"})
    never = run("responses-channels", readers)
    assert not never.ok and "payhoa never checked" in never.message


def test_responses_channels_fails_with_no_check_yet_or_an_unreadable_inbox(data, readers):
    assert not run("responses-channels", readers).ok and not (data / "responses").exists()
    put(data, "responses/inbox.json", "{broken")
    assert not run("responses-channels", readers).ok


# --- responses-outstanding -----------------------------------------------------------------------------------------------

def request_stub():
    from test_campaigns import REQUEST, Stub

    return Stub(requests=(REQUEST,)), REQUEST.key


def send_a_copy(data):
    from jason.community.form_refs import Channel as Via, make

    ref = make("KM", 2027, Via.EMAIL, membership_id=1, unit_id=2).text
    form_references.record(data, ref, form="annual-info", year=2027, membershipId=1, unitId=2, unit="1 Example Way", channel="email")


def test_responses_outstanding_counts_copies_sent_less_answers_and_names_no_owner(data):
    data.mkdir(parents=True, exist_ok=True)
    community, key = request_stub()
    readers = StoreReaders(data, community=community, today=TODAY)
    assert not run("responses-outstanding", readers, subject=f"request:{key}").ok            # no catalog: nobody is counted as asked
    send_a_copy(data)
    got = run("responses-outstanding", readers, subject=f"request:{key}")
    assert got.ok and got.message.startswith("1 copy(ies) sent, 0 answered, 1 not responded")
    assert "owner list is not on disk" in got.message and "Example Way" not in got.message
    assert got.evidence and got.evidence[0].startswith("file:forms/references.json@")


def test_responses_outstanding_fails_for_a_request_the_profile_does_not_have_or_no_profile(data):
    data.mkdir(parents=True, exist_ok=True)
    community, key = request_stub()
    send_a_copy(data)
    readers = StoreReaders(data, community=community, today=TODAY)
    unknown = run("responses-outstanding", readers, subject="request:no-such-request")
    assert not unknown.ok and "no-such-request" in unknown.message
    bare = StoreReaders(data, community=SimpleNamespace(response_requests=lambda: ()), today=TODAY)
    assert not run("responses-outstanding", bare, subject=f"request:{key}").ok
    broken = StoreReaders(data, community=SimpleNamespace(), today=TODAY)                    # a profile with no such method
    assert not run("responses-outstanding", broken, subject=f"request:{key}").ok


# --- instance-which ------------------------------------------------------------------------------------------------------

def test_instance_which_names_the_community_and_where_the_choice_came_from(readers, monkeypatch):
    monkeypatch.setenv("JASON_COMMUNITY", "example_hoa")
    got = run("instance-which", readers)
    assert got.ok and "community example_hoa, chosen by JASON_COMMUNITY: a choice a person made" in got.message


def test_instance_which_says_when_the_choice_is_a_default_the_code_made_and_fails_when_none_is_chosen(readers, monkeypatch):
    from jason.community import profile

    monkeypatch.setattr(profile, "resolve_community", lambda: profile.Resolved("example_hoa", "built-in default", shim=True))
    got = run("instance-which", readers)
    assert got.ok and "a default the code chose" in got.message and "jason use KEY" in got.message

    def none_chosen():
        raise profile.CommunityNotChosen("no community chosen")

    monkeypatch.setattr(profile, "resolve_community", none_chosen)
    assert not run("instance-which", readers).ok


def test_instance_which_loads_no_profile(readers, monkeypatch):
    import sys

    monkeypatch.setenv("JASON_COMMUNITY", "example_hoa")
    before = {m for m in sys.modules if "mystique" in m}
    run("instance-which", readers)
    assert {m for m in sys.modules if "mystique" in m} == before


# --- service-heartbeat ---------------------------------------------------------------------------------------------------

def beat(data, **record):
    put(data, "jobs/heartbeat.json", {"pid": 1, "host": "example-host", **record})


def test_service_heartbeat_passes_for_a_recent_running_or_draining_beat(data, readers):
    for said in ("running", "draining"):
        beat(data, state=said, beat=stamp(seconds=20))
        got = run("service-heartbeat", readers)
        assert got.ok and got.message.startswith(f"{said}: the last beat is within 90 s") and "example-host" not in got.message


def test_service_heartbeat_message_does_not_change_while_the_beat_does(data, readers):
    beat(data, state="running", beat=stamp(seconds=5))
    first = run("service-heartbeat", readers)
    beat(data, state="running", beat=stamp(seconds=25))
    assert run("service-heartbeat", readers) == first                               # nothing new to record on the next resume


def test_service_heartbeat_fails_when_stale_stopped_never_written_or_unreadable(data, readers):
    assert run("service-heartbeat", readers).message.startswith("none")
    beat(data, state="running", beat=stamp(seconds=200))
    stale = run("service-heartbeat", readers)
    assert not stale.ok and stale.message.startswith("stale: no beat for more than 90 s") and "it said running" in stale.message
    beat(data, state="stopped", beat=stamp(seconds=5))
    assert not run("service-heartbeat", readers).ok and run("service-heartbeat", readers).message.startswith("stopped")
    beat(data, state="running", beat="not a time")
    assert run("service-heartbeat", readers).message.startswith("stale")
    put(data, "jobs/heartbeat.json", "{broken")
    assert not run("service-heartbeat", readers).ok
    put(data, "jobs/heartbeat.json", "{}")
    assert run("service-heartbeat", readers).message.startswith("none")


def test_service_heartbeat_agrees_with_the_judgement_of_jason_serve(data, readers):
    from jason import serve

    for record in ({"state": "running", "beat": stamp(seconds=10)}, {"state": "draining", "beat": stamp(seconds=89)},
                   {"state": "running", "beat": stamp(seconds=91)}, {"state": "stopped", "beat": stamp(seconds=1)}):
        beat(data, **record)
        theirs = serve.judge(serve.read_heartbeat(data), now=NOON)
        assert run("service-heartbeat", readers).ok == bool(theirs["alive"]), record


# --- service-queue -------------------------------------------------------------------------------------------------------

def test_service_queue_counts_the_jobs_by_status_and_creates_no_queue(data, readers):
    got = run("service-queue", readers)
    assert not got.ok and "no job queue" in got.message and not (data / "jobs.db").exists()
    first = jobs.add(data, ["gmail", "--sync"])
    jobs.add(data, ["mail"])
    jobs.add(data, ["sync-catalog"])
    jobs.cancel(data, first.id)
    got = run("service-queue", readers)
    assert got.ok and got.message == "jobs: 2 queued, 0 running, 0 failed, 0 done, 1 cancelled (of the newest 5000)"


def test_service_queue_fails_on_a_queue_that_cannot_be_read(data, readers):
    put(data, "jobs.db", "this is not a database")
    assert not run("service-queue", readers).ok


# --- the family as a whole -----------------------------------------------------------------------------------------------

def populate(data):
    """Every store the family reads, in one folder."""
    put(data, "mail/items.json", {"syncedAt": stamp(hours=1), "items": [letter("m-1", urgency="act", kind="legal"), letter("m-2", scanned=False)]})
    mail_triage.choose(data, "m-1", choice="keep", by="A. Manager")
    gmail(data, message("t-us", "2099-09-29T10:00:00+00:00", "in"))
    inbox_with(data, payhoa={"ended": "ok", "lastOk": "2099-10-01T10:00:00+00:00"}, gmail={"ended": "ok"}, mail={"ended": "skipped"},
               forms={"ended": "skipped"})
    send_a_copy(data)
    beat(data, state="running", beat=stamp(seconds=10))
    jobs.add(data, ["gmail", "--sync"])


def test_every_read_leaves_the_data_folder_exactly_as_it_was_files_and_folders(data, monkeypatch):
    monkeypatch.setenv("JASON_COMMUNITY", "example_hoa")
    data.mkdir(parents=True, exist_ok=True)
    populate(data)
    community, key = request_stub()
    readers = StoreReaders(data, community=community, today=TODAY)
    before = tree(data)
    for name, kw in (("mail-fresh", {}), ("mail-lanes", {}), ("mail-scanned", {"item": "m-1"}), ("mail-scanned", {"item": "m-2"}),
                     ("mail-period-chosen", {"items": ("m-1", "m-2")}), ("gmail-fresh", {}),
                     ("thread-status", {"subject": "thread:t-us"}), ("responses-channels", {}),
                     ("responses-outstanding", {"subject": f"request:{key}"}), ("instance-which", {}), ("service-heartbeat", {}),
                     ("service-queue", {})):
        run(name, readers, **kw)
    assert tree(data) == before
    empty = data.parent / "empty"
    empty.mkdir()
    bare = StoreReaders(empty, community=SimpleNamespace(response_requests=lambda: ()), today=TODAY)
    for name in NAMES:
        run(name, bare, subject="thread:t-us", item="m-1", items=("m-1",))
    assert tree(empty) == {}                                                       # not even a folder: no read makes a store


def test_a_store_that_cannot_be_read_fails_the_read_and_raises_nothing(data):
    data.mkdir(parents=True, exist_ok=True)
    for relative in ("mail/items.json", "mail/triage.json", "gmail/correspondence.json", "responses/inbox.json", "jobs/heartbeat.json",
                     "forms/references.json"):
        put(data, relative, "\x00{garbage")
    put(data, "jobs.db", "garbage")
    community, key = request_stub()
    readers = StoreReaders(data, community=community, today=TODAY)
    for name, kw in (("mail-fresh", {}), ("mail-lanes", {}), ("mail-scanned", {"item": "m-1"}),
                     ("mail-period-chosen", {"items": ("m-1",)}), ("gmail-fresh", {}), ("thread-status", {"subject": "thread:t-us"}),
                     ("responses-channels", {}), ("responses-outstanding", {"subject": f"request:{key}"}), ("service-heartbeat", {}),
                     ("service-queue", {})):
        got = run(name, readers, **kw)
        assert not got.ok and got.message, name


def test_no_message_carries_an_address_a_subject_or_a_sender(data, monkeypatch):
    monkeypatch.setenv("JASON_COMMUNITY", "example_hoa")
    data.mkdir(parents=True, exist_ok=True)
    populate(data)
    community, key = request_stub()
    readers = StoreReaders(data, community=community, today=TODAY)
    seen = []
    for name, kw in (("mail-lanes", {}), ("mail-scanned", {"item": "m-1"}), ("thread-status", {"subject": "thread:t-us"}),
                     ("responses-outstanding", {"subject": f"request:{key}"}), ("responses-channels", {}), ("service-heartbeat", {})):
        seen.append(run(name, readers, **kw).message)
    text = "\n".join(seen)
    for word in ("@", "Vendor Example", "Invoice question", "vendor.example", "Example Way", "example-host"):
        assert word not in text, word


def test_channels_named_by_the_read_are_the_inboxs_own_channels_less_the_manual_one():
    assert [c.value for c in Channel if c is not Channel.MANUAL] == ["payhoa", "gmail", "mail", "forms"]
