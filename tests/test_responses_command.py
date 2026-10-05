"""``jason responses`` (docs/responses-design.md, step 2): the command over the inbox of step 1.

Everything is made up and offline: the fakes of ``test_response_inbox`` (a Gmail, a PayHOA, an association), a fake agent
the command is handed in place of ``Jason``, and a clock. Nothing here reaches a service, Keeper, a real mailbox, a
model, or an owner's data; ``at_terminal`` is patched where the command looks it up.
"""

from __future__ import annotations

import json
from argparse import Namespace
from collections import Counter
from datetime import date, timedelta
from types import SimpleNamespace

import pytest
from test_response_inbox import (Assoc, CYCLE, FORMS, NOW, TAGS, FakeGmail, FakePayhoa, Village, _community,  # noqa: F401
                                 data, msg, payhoa_rows)

from jason.commands import responses as cmd
from jason.community.forms import FormAnswers, FormKey
from jason.community.response_inbox import State
from jason.google.errors import GoogleAuthRequired
from jason.secrets import KeeperAuthRequired
from jason.tasks import response_inbox as ri
from jason.tasks.response_inbox import OwnerRef

PAT = {"pat@example.org": OwnerRef("101 Example Way", "Pat Example", 1, 11)}
PRIVATE = ("pat@example.org", "pat@example.com", "916-555-0100", "PO Box 9")


class Agent:
    """What the command is handed in place of ``Jason``: clients made on demand, a record of what was asked."""

    org_id = 7

    def __init__(self, gmail=None, payhoa=None, gmail_error=None, payhoa_error=None) -> None:
        self._gmail, self._payhoa = gmail, payhoa
        self.gmail_error, self.payhoa_error = gmail_error, payhoa_error
        self.entered = 0
        self.gmail_asks: list[bool] = []

    def __enter__(self):
        self.entered += 1
        return self

    def __exit__(self, *exc):
        return False

    def gmail(self, *, interactive=False):
        self.gmail_asks.append(interactive)
        if self.gmail_error is not None:
            raise self.gmail_error
        return self._gmail

    def payhoa(self):
        if self.payhoa_error is not None:
            raise self.payhoa_error
        return self._payhoa


class Clock:
    now = NOW


@pytest.fixture
def clock(monkeypatch):
    Clock.now = NOW
    monkeypatch.setattr(ri, "now_utc", lambda: Clock.now)
    return Clock


@pytest.fixture
def env(data, tmp_path, monkeypatch, clock):
    """A made-up .env whose data folder is the tmp dir, the fake association, a console, and PayHOA's test account 99."""
    path = tmp_path / ".env"
    path.write_text(f"PAYHOA_CATALOG={data / 'payhoa.db'}\n", encoding="utf-8")
    monkeypatch.setattr(cmd, "_community", lambda: Assoc())
    monkeypatch.setattr(cmd, "at_terminal", lambda: True)
    monkeypatch.setattr("jason.config.test_memberships", lambda env_file=None: {99})
    return SimpleNamespace(path=path, data=data)


def hand(monkeypatch, agent):
    """Make ``agent`` what the command's factory builds (``jason.cli.build_parser`` looks ``_agent`` up when it runs)."""
    monkeypatch.setattr("jason.cli._agent", lambda args: agent)
    return agent


def run(env, capsys, *argv):
    from jason.cli import main

    with pytest.raises(SystemExit) as done:
        main([*argv, "--env", str(env.path)])
    out = capsys.readouterr()
    return int(done.value.code or 0), out.out, out.err


def no_private(text: str) -> None:
    assert not [p for p in PRIVATE if p in text], [p for p in PRIVATE if p in text]


def kept_all(env, capsys, monkeypatch, *messages):
    """A check of Gmail and PayHOA that keeps payhoa 1001 (new), 1002 (seen: complete), and the given Gmail messages."""
    agent = hand(monkeypatch, Agent(FakeGmail(*messages), FakePayhoa(payhoa_rows())))
    code, out, err = run(env, capsys, "responses", "--check", "--channel", "payhoa", "--channel", "gmail")
    assert code == 0, err
    return agent


def stub_reading(path, request, layout, model):
    """The made-up scan reading: the owner's own email and a second mailing address in the answers, a phone in a note."""
    from jason.community.form_refs import Channel as MarkerChannel, make

    marker = make("AC", 2027, MarkerChannel.EMAIL, membership_id=11, unit_id=1).text
    fields = {"delivery.by-mail": SimpleNamespace(value=True, how="mark", confidence=0.9),
              "email": SimpleNamespace(value="pat@example.org", how="writing", confidence=0.55)}
    answers = {"name": "Pat Example", "unit-address": "101 Example Way", "delivery": ["By mail"], "occupancy": ["Rented out"],
               "email": "pat@example.org", "second-mailing-address": "PO Box 9, Example City"}
    return ri.FileReading(path.name, "scan", fields, answers, marker, "text", ["call 916-555-0100 to check the unit"], 12, 0.4)


@pytest.fixture
def reading(env, monkeypatch):
    monkeypatch.setattr(ri, "read_file", stub_reading)
    monkeypatch.setattr(ri, "owner_directory", lambda data_dir, community: dict(PAT))
    return stub_reading


def read_one(env, capsys, monkeypatch, *, by="Treasurer"):
    """Keep message m1 (a PDF from an owner), then read it at a console."""
    hand(monkeypatch, Agent(FakeGmail(msg("m1"), attachments={("m1", "att-m1-0"): b"made-up bytes"})))
    assert run(env, capsys, "responses", "--check", "--channel", "gmail")[0] == 0
    code, out, err = run(env, capsys, "responses", "--read", "gmail:m1", "--by", by)
    assert code == 0, err
    return out


# -- no option: the inbox from disk -------------------------------------------------------------------------------------

def test_an_empty_inbox_says_so_and_names_the_check_and_each_channel_never_checked(env, capsys):
    code, out, err = run(env, capsys, "responses")
    assert code == 0 and not err
    assert "0 new, 0 kept" in out and "Nothing new." in out
    for channel in ("payhoa", "gmail", "mail", "forms"):
        assert f"{channel}" in out
    assert out.count("never checked") == 4 and "jason responses --check" in out and "live read" in out


def test_a_profile_that_watches_no_request_says_so(env, capsys, monkeypatch):
    class Quiet:
        def response_requests(self):
            return ()

    monkeypatch.setattr(cmd, "_community", lambda: Quiet())
    code, out, _ = run(env, capsys, "responses")
    assert code == 0 and "watches no request" in out


def test_the_inbox_groups_what_is_new_by_request_and_says_how_old_each_channel_is(env, capsys, monkeypatch, clock):
    kept_all(env, capsys, monkeypatch, msg("m1"), msg("m2", files=(), subject="a question"))
    clock.now = NOW + timedelta(hours=3)
    code, out, _ = run(env, capsys, "responses")
    assert code == 0
    assert "2 new, 3 kept" in out and "survey-2027: Owner survey (2)" in out
    assert "payhoa:1001" in out and "gmail:m1" in out and "payhoa:1002" not in out       # the complete one was kept as seen
    assert "Kept, in other states: seen 1" in out
    assert "payhoa  last succeeded 2026-10-05T12:00:00+00:00 (3h ago); last try" in out and "ended ok" in out
    assert "mail    never checked (reads disk)" in out and "forms   never checked (reads disk)" in out
    assert "jason responses --check" in out
    no_private(out)
    code, out, _ = run(env, capsys, "responses", "--json")
    body = json.loads(out)
    assert {a["id"] for a in body["new"]} == {"payhoa:1001", "gmail:m1"} and body["kept"] == 3
    assert {c["channel"]: c["ended"] for c in body["checked"]} == {"payhoa": "ok", "gmail": "ok"}


def test_a_channel_that_failed_says_how_it_ended_and_never_succeeded(env, capsys, monkeypatch):
    hand(monkeypatch, Agent(gmail_error=GoogleAuthRequired("no human is present; pass interactive=True")))
    run(env, capsys, "responses", "--check", "--channel", "gmail")
    code, out, _ = run(env, capsys, "responses")
    assert code == 0 and "gmail   never succeeded; last try" in out and "ended sign-in: GoogleAuthRequired" in out


# -- --list and --show --------------------------------------------------------------------------------------------------

def test_list_filters_by_state_channel_unit_and_days_and_prints_json(env, capsys, monkeypatch):
    kept_all(env, capsys, monkeypatch, msg("m1"))
    _, out, _ = run(env, capsys, "responses", "--list")
    assert "3 arrival(s), newest first" in out and "payhoa:1002" in out and "gmail:m1" in out
    _, out, _ = run(env, capsys, "responses", "--list", "--state", "seen")
    assert "1 arrival(s)" in out and "payhoa:1002" in out and "payhoa:1001" not in out
    _, out, _ = run(env, capsys, "responses", "--list", "--new", "--channel", "gmail")
    assert "gmail:m1" in out and "payhoa:1001" not in out
    _, out, _ = run(env, capsys, "responses", "--list", "--unit", "101")
    assert "payhoa:1001" in out and "payhoa:1002" not in out
    _, out, _ = run(env, capsys, "responses", "--list", "--request", "no-such")
    assert "No arrival matches." in out
    _, out, _ = run(env, capsys, "responses", "--list", "--days", "1")
    assert "No arrival matches." in out or "arrival(s)" in out
    _, out, _ = run(env, capsys, "responses", "--list", "--json")
    assert {a["id"] for a in json.loads(out)["arrivals"]} == {"payhoa:1001", "payhoa:1002", "gmail:m1"}
    code, _, err = run(env, capsys, "responses", "--list", "--new", "--state", "seen")
    assert code == 2 and "jason responses:" in err


def test_an_option_that_does_not_go_with_the_action_is_refused(env, capsys):
    code, out, err = run(env, capsys, "responses", "--state", "new")
    assert code == 2 and err.startswith("jason responses: --state does not go with") and not out
    code, _, err = run(env, capsys, "responses", "--list", "--model", "m")
    assert code == 2 and "--model" in err
    code, _, err = run(env, capsys, "responses", "--check", "--set", "a=b", "--by", "scheduler")
    assert code == 2 and "--set" in err


def test_show_is_masked_and_says_what_is_left(env, capsys, monkeypatch, reading):
    read_one(env, capsys, monkeypatch)
    code, out, _ = run(env, capsys, "responses", "--show", "gmail:m1")
    assert code == 0
    no_private(out)
    assert "gmail:m1" in out and "[read]" in out and "101 Example Way" in out        # a unit's label is not a contact detail
    assert "[email]" in out and "[phone]" in out and "[address]" in out
    assert "delivery.by-mail" in out and "0.90" in out and "0.55" in out
    assert "kept: found by a check of gmail" in out and "read: 1 file(s) read: scan" in out
    assert "Left: confirm the reading" in out
    code, out, _ = run(env, capsys, "responses", "--show", "gmail:m1", "--json")
    no_private(out)
    body = json.loads(out)
    assert body["arrival"]["state"] == "read" and body["reading"]["owner"]["unit"] == "101 Example Way"
    code, _, err = run(env, capsys, "responses", "--show", "gmail:nope")
    assert code == 2 and err.startswith("jason responses: no arrival 'gmail:nope'")


# -- --check ------------------------------------------------------------------------------------------------------------

def test_a_check_is_refused_without_a_console_and_the_scheduler_is_allowed(env, capsys, monkeypatch):
    monkeypatch.setattr(cmd, "at_terminal", lambda: False)
    agent = hand(monkeypatch, Agent(FakeGmail(msg("m1")), FakePayhoa(payhoa_rows())))
    code, out, err = run(env, capsys, "responses", "--check")
    assert code == 2 and err.startswith("jason responses: a live check") and "--by scheduler" in err and not out
    assert agent.entered == 0 and not agent.gmail_asks                     # nothing was reached
    code, _, err = run(env, capsys, "responses", "--check", "--by", "Treasurer")
    assert code == 2 and "terminal" in err
    code, out, err = run(env, capsys, "responses", "--check", "--by", "scheduler")
    assert code == 0 and not err and "by scheduler" in out and "Kept 3 new" in out
    assert "Read-only: nothing was written to Gmail or PayHOA" in out
    assert agent.gmail_asks == [False]                                       # Gmail is never asked to sign in with a prompt
    assert {a.id for a in ri.list_arrivals(env.data)} == {"payhoa:1001", "payhoa:1002", "gmail:m1"}
    assert [r["by"] for r in ri.acts_for(env.data, "gmail:m1")] == ["scheduler"]


def test_a_check_of_the_disk_channels_alone_builds_no_agent(env, capsys, monkeypatch):
    agent = hand(monkeypatch, Agent())
    code, out, _ = run(env, capsys, "responses", "--check", "--channel", "mail", "--channel", "forms", "--by", "scheduler")
    assert code == 0 and agent.entered == 0
    assert "mail    ok" in out and "forms   ok" in out and "Nothing new was kept." in out


def test_a_failing_channel_does_not_stop_the_others_and_sets_exit_1(env, capsys, monkeypatch):
    hand(monkeypatch, Agent(FakeGmail(), FakePayhoa(payhoa_rows()), gmail_error=GoogleAuthRequired(
        "no human is present; pass interactive=True")))
    code, out, err = run(env, capsys, "responses", "--check", "--channel", "gmail", "--channel", "payhoa")
    assert code == 1 and not err
    assert "gmail   sign-in" in out and "needs a sign-in: GoogleAuthRequired" in out
    assert "payhoa  ok" in out and "payhoa:1001" in out and "Kept 2 new" in out
    assert "Failed: gmail" in out and "scheduler's pause" in out
    # PayHOA's sign-in failing is reported the same way, and Gmail is still read
    agent2 = hand(monkeypatch, Agent(FakeGmail(msg("m1")), payhoa_error=KeeperAuthRequired("run jason login")))
    code, out, _ = run(env, capsys, "responses", "--check", "--channel", "gmail", "--channel", "payhoa")
    assert code == 1 and "payhoa  sign-in" in out and "KeeperAuthRequired" in out and "gmail:m1" in out
    assert agent2.gmail_asks == [False]
    code, out, _ = run(env, capsys, "responses", "--check", "--channel", "gmail", "--json")
    assert code == 0 and json.loads(out)["channels"][0]["ended"] == "ok"
    hand(monkeypatch, Agent(gmail_error=RuntimeError("Gmail answered 500")))
    code, out, _ = run(env, capsys, "responses", "--check", "--channel", "gmail", "--json")
    body = json.loads(out)
    assert code == 1 and body["channels"][0]["ended"] == "failed" and "500" in body["channels"][0]["reason"]


def test_from_marks_which_messages_were_kept_and_never_prints_the_address(env, capsys, monkeypatch):
    gmail = FakeGmail(msg("a1"), msg("a2", files=(), subject="a question"), msg("b1", frm="Other <other@example.net>"))
    hand(monkeypatch, Agent(gmail))
    code, out, _ = run(env, capsys, "responses", "--check", "--from", "pat@example.org")
    assert code == 0 and "pat@example.org" not in out
    assert "Messages from that address in the window: 2 found, 1 kept now" in out
    assert "gmail:a1" in out and "[kept]" in out and "gmail:b1" not in out
    assert "gmail:a2" in out and "[listed only, not kept: no PDF or image, and not from a current owner's address]" in out
    assert [a.id for a in ri.list_arrivals(env.data)] == ["gmail:a1"]                  # only the candidate
    code, out, _ = run(env, capsys, "responses", "--check", "--from", "pat@example.org", "--json")
    listed = {m["id"]: m for m in json.loads(out)["listed"]}
    assert listed["gmail:a1"]["candidate"] and not listed["gmail:a1"]["kept"] and not listed["gmail:a2"]["candidate"]
    code, out, _ = run(env, capsys, "responses", "--check", "--from", "pat@example.org")
    assert "[already kept]" in out
    code, _, err = run(env, capsys, "responses", "--check", "--since", "last tuesday")
    assert code == 2 and "--since takes a day" in err


# -- --read -------------------------------------------------------------------------------------------------------------

def test_read_prints_each_fields_confidence_the_reference_and_whether_it_matches_the_copy(env, capsys, monkeypatch, reading):
    from jason.community.form_refs import Channel as MarkerChannel, make

    marker = make("AC", 2027, MarkerChannel.EMAIL, membership_id=11, unit_id=1).text
    (env.data / "forms").mkdir()
    (env.data / "forms" / "references.json").write_text(json.dumps({marker: {
        "form": "owner-info", "year": 2027, "membershipId": 11, "unitId": 1, "unit": "101 Example Way", "channel": "email"}}),
        encoding="utf-8")
    out = read_one(env, capsys, monkeypatch)
    no_private(out)
    assert "Read gmail:m1 by Treasurer: 1 file(s)" in out and "Nothing was written to Gmail or PayHOA" in out
    assert "evidence for a person to check against the scan, never an answer" in out
    assert "sender matched to: Pat Example, 101 Example Way (the sender's address)" in out
    assert f"reference: {marker} (read from text)" in out and "campaign AC27E names this request" in out
    assert "sent to Pat Example at 101 Example Way; matches the sender's unit: yes; owner: yes" in out
    assert "delivery.by-mail" in out and "mark" in out and "0.90" in out and "writing" in out and "0.55" in out
    assert "call [phone] to check the unit" in out
    assert "Next: check it against the scan, then `jason responses --confirm gmail:m1 --by NAME" in out
    assert ri.get(env.data, "gmail:m1").state is State.READ
    assert (env.data / "responses" / "files" / "gmail-m1" / "form.pdf").read_bytes() == b"made-up bytes"
    # a copy sent to another unit does not match
    refs = json.loads((env.data / "forms" / "references.json").read_text(encoding="utf-8"))
    refs[marker]["unitId"], refs[marker]["membershipId"] = 2, 12
    (env.data / "forms" / "references.json").write_text(json.dumps(refs), encoding="utf-8")
    monkeypatch.setattr(ri, "owner_directory", lambda d, c: {**PAT, "ben@example.org": OwnerRef("102 Example Way", "Ben Sample", 2, 12)})
    _, out, _ = run(env, capsys, "responses", "--show", "gmail:m1")
    assert "sent to Ben Sample at 101 Example Way; matches the sender's unit: NO; owner: NO" in out


def test_a_copy_with_no_record_cannot_be_compared(env, capsys, monkeypatch, reading):
    out = read_one(env, capsys, monkeypatch)
    assert "the copy sent under it: none on file" in out and "cannot be compared" in out


def test_read_needs_a_console_or_the_scheduler_a_name_and_an_arrival_that_needs_reading(env, capsys, monkeypatch, reading):
    hand(monkeypatch, Agent(FakeGmail(msg("m1")), FakePayhoa(payhoa_rows())))
    run(env, capsys, "responses", "--check", "--channel", "gmail", "--channel", "payhoa")
    code, _, err = run(env, capsys, "responses", "--read", "gmail:m1")
    assert code == 2 and err.startswith("jason responses: --by is required")
    code, _, err = run(env, capsys, "responses", "--read", "payhoa:1001", "--by", "Treasurer")
    assert code == 2 and "needs no reading" in err
    monkeypatch.setattr(cmd, "at_terminal", lambda: False)
    code, _, err = run(env, capsys, "responses", "--read", "gmail:m1", "--by", "Treasurer")
    assert code == 2 and "terminal" in err and ri.get(env.data, "gmail:m1").state is State.NEW
    code, out, _ = run(env, capsys, "responses", "--read", "gmail:m1", "--by", "scheduler")
    assert code == 0 and ri.get(env.data, "gmail:m1").state is State.READ


def test_the_local_model_is_a_refusal_when_it_is_unavailable(env, capsys, monkeypatch, reading):
    import jason.local_ai as local_ai

    def refuse(model, **more):
        raise local_ai.LocalAIUnavailable("Ollama at http://localhost:11434 is not answering; start the Ollama app")

    monkeypatch.setattr(local_ai, "preflight", refuse)
    hand(monkeypatch, Agent(FakeGmail(msg("m1"))))
    run(env, capsys, "responses", "--check", "--channel", "gmail")
    code, out, err = run(env, capsys, "responses", "--read", "gmail:m1", "--by", "Treasurer", "--model", "qwen-made-up")
    assert code == 2 and err.startswith("jason responses: Ollama") and not out
    assert ri.get(env.data, "gmail:m1").state is State.NEW and not (env.data / "responses" / "files").exists()


# -- --confirm ----------------------------------------------------------------------------------------------------------

def test_confirm_needs_a_name_and_a_read_arrival_and_prints_the_keyed_answers_masked(env, capsys, monkeypatch, reading):
    read_one(env, capsys, monkeypatch)
    code, out, err = run(env, capsys, "responses", "--confirm", "gmail:m1")
    assert code == 2 and err.startswith("jason responses: --by is required") and not out
    assert ri.get(env.data, "gmail:m1").state is State.READ
    code, _, err = run(env, capsys, "responses", "--confirm", "gmail:m1", "--by", "Treasurer", "--set", "no-equals-sign")
    assert code == 2 and "--set takes FIELD=VALUE" in err
    code, _, err = run(env, capsys, "responses", "--confirm", "gmail:m1", "--by", "Treasurer", "--set", "nonesuch=x")
    assert code == 2 and "not a question" in err
    code, out, err = run(env, capsys, "responses", "--confirm", "gmail:m1", "--by", "Treasurer", "--why", "checked the scan",
                         "--set", "email=pat@example.com", "--set", "occupancy=Owner-occupied", "--set", "second-mailing-address=")
    assert code == 0, err
    no_private(out)
    assert "Confirmed gmail:m1 by Treasurer: keyed answers kept (source email:m1; values masked)" in out
    assert "  name: Pat Example" in out and "  email: [email]" in out and "  occupancy: Owner-occupied" in out
    assert "second-mailing-address" not in out.split("corrected:")[0]                      # cleared
    assert "corrected: email, occupancy, second-mailing-address" in out and "problems: none" in out
    assert "Nothing was written to PayHOA." in out and "`jason owner-info --apply` plans" in out
    assert ri.get(env.data, "gmail:m1").state is State.KEYED
    last = ri.acts_for(env.data, "gmail:m1")[-1]
    assert last["act"] == "confirm" and last["by"] == "Treasurer" and last["why"] == "checked the scan"
    code, out, _ = run(env, capsys, "responses", "--confirm", "gmail:m1", "--by", "Treasurer")
    assert code == 2 and "only a read arrival" in out + _
    code, out, _ = run(env, capsys, "responses", "--list", "--state", "keyed", "--json")
    assert [a["id"] for a in json.loads(out)["arrivals"]] == ["gmail:m1"]


def test_confirm_refuses_an_arrival_that_was_never_read(env, capsys, monkeypatch):
    hand(monkeypatch, Agent(FakeGmail(msg("m1"))))
    run(env, capsys, "responses", "--check", "--channel", "gmail")
    code, _, err = run(env, capsys, "responses", "--confirm", "gmail:m1", "--by", "Treasurer")
    assert code == 2 and "only a read arrival is confirmed" in err


# -- --seen, --seen-all, --dismiss --------------------------------------------------------------------------------------

def test_seen_seen_all_and_dismiss_name_the_person_and_log_the_act(env, capsys, monkeypatch):
    kept_all(env, capsys, monkeypatch, msg("m1"), msg("m2", subject="another"))
    code, _, err = run(env, capsys, "responses", "--seen", "gmail:m1")
    assert code == 2 and err.startswith("jason responses: --by is required")
    code, out, _ = run(env, capsys, "responses", "--seen", "gmail:m1", "payhoa:1002", "--by", "Secretary")
    assert code == 0 and "Marked seen: gmail:m1." in out and "Left as they were" in out and "payhoa:1002" in out
    code, _, err = run(env, capsys, "responses", "--seen", "gmail:m1", "gmail:nope", "--by", "Secretary")
    assert code == 2 and "no arrival 'gmail:nope'" in err
    code, out, _ = run(env, capsys, "responses", "--seen-all", "--by", "Secretary")
    assert code == 0 and "payhoa:1001" in out and "gmail:m2" in out and not ri.list_arrivals(env.data, new=True)
    assert ri.acts_for(env.data, "gmail:m1")[-1]["by"] == "Secretary"
    code, _, err = run(env, capsys, "responses", "--dismiss", "gmail:m2", "--by", "Secretary")
    assert code == 2 and err.startswith("jason responses: --why is required")
    code, out, _ = run(env, capsys, "responses", "--dismiss", "gmail:m2", "--by", "Secretary", "--why", "a question, not the form")
    assert code == 0 and "Dismissed gmail:m2 by Secretary: a question, not the form" in out
    act = ri.acts_for(env.data, "gmail:m2")[-1]
    assert (act["act"], act["by"], act["why"]) == ("dismiss", "Secretary", "a question, not the form")
    assert ri.get(env.data, "gmail:m2").state is State.DISMISSED
    code, _, err = run(env, capsys, "responses", "--dismiss", "gmail:m2", "--by", "Secretary", "--why", "again")
    assert code == 2 and "cannot be dismissed" in err


def test_dismissing_a_keyed_arrival_sets_its_answers_aside_and_says_so(env, capsys, monkeypatch, reading):
    read_one(env, capsys, monkeypatch)
    run(env, capsys, "responses", "--confirm", "gmail:m1", "--by", "Treasurer")
    code, out, _ = run(env, capsys, "responses", "--dismiss", "gmail:m1", "--by", "Treasurer", "--why", "wrong unit")
    assert code == 0 and "set aside" in out and "not deleted" in out
    assert (env.data / "responses" / "keyed" / "withdrawn" / "gmail-m1.json").is_file()


# -- owner-info --apply: keyed answers and the zero-write call ----------------------------------------------------------

class Apply:
    """What ``owner-info --apply`` is handed in place of ``Jason``: a made-up PayHOA."""

    org_id = 7

    def __init__(self, payhoa) -> None:
        self._payhoa = payhoa

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def payhoa(self):
        return self._payhoa


def apply_args(**more):
    return Namespace(**{"payhoa": False, "env": None, "yes": False, "show": 15, "by": None, "confirmed_by": None, **more})


def keyed_by_command(env, capsys, monkeypatch):
    """Message m1 kept, read, and confirmed through the command, for the unit and owner in ``Village``."""
    read_one(env, capsys, monkeypatch)
    code, out, err = run(env, capsys, "responses", "--confirm", "gmail:m1", "--by", "Treasurer",
                         "--set", "occupancy=Owner-occupied", "--set", "delivery=By mail", "--set", "email=",
                         "--set", "second-mailing-address=")
    assert code == 0, err


def test_a_confirmed_answer_plans_the_same_writes_as_a_payhoa_answer_with_the_same_answers(env, capsys, monkeypatch, reading):
    from jason.commands import owner_info
    from jason.tasks import owner_info_apply as oia
    from jason.tasks.owner_info import plan_writes

    keyed_by_command(env, capsys, monkeypatch)
    capsys.readouterr()
    owner_info._apply(apply_args(by="Treasurer"), lambda a: Apply(Village()), _community(monkeypatch), FORMS, CYCLE, env.data,
                      date(2026, 10, 10))
    out = capsys.readouterr().out
    assert "Dry run" in out and "Notices by Mail" in out and "Owner Occupied" in out
    assert ri.get(env.data, "gmail:m1").state is State.KEYED                 # a dry run records nothing
    shown = {}
    for line in out.splitlines():                                             # the counts the dry run prints, a kind a line
        if line.startswith(("  member tag", "  unit tag")):
            kind, count = line.strip().rsplit(None, 1)
            shown[kind] = int(count)
    village = Village()
    submission = FormAnswers(FormKey.OWNER_INFO, {"name": "Pat Example", "delivery": ["By mail"], "occupancy": ["Owner-occupied"]},
                             source="payhoa:501", submitted="2026-10-04T15:00:00+00:00", membership_id=11, unit_id=1)
    found, rows = oia.ledger_rows(village.units, village.people, [submission], env.data / "elsewhere", _community(monkeypatch),
                                  CYCLE, date(2026, 10, 10), earlier=FORMS.EARLIER_ELECTIONS)
    from_payhoa = Counter(w.kind for w in plan_writes(rows, found, TAGS, earlier=FORMS.EARLIER_ELECTIONS,
                                                      today=date(2026, 10, 10)))
    assert shown and shown == dict(from_payhoa)                               # the same writes a PayHOA answer plans


def test_a_yes_records_the_arrival_as_the_person_named_by_by(env, capsys, monkeypatch, reading):
    from jason.commands import owner_info

    keyed_by_command(env, capsys, monkeypatch)
    monkeypatch.setattr(owner_info, "_audit_cli", lambda *a, **k: None)             # the approvals audit has its own tests
    village = Village()
    owner_info._apply(apply_args(yes=True, by="Secretary"), lambda a: Apply(village), _community(monkeypatch), FORMS, CYCLE,
                      env.data, date(2026, 10, 10))
    assert village.writes and ri.get(env.data, "gmail:m1").state is State.RECORDED
    last = ri.acts_for(env.data, "gmail:m1")[-1]
    assert last["act"] == "recorded" and last["by"] == "Secretary" and "PayHOA write" in last["why"]


def test_a_plan_with_no_writes_marks_the_arrival_recorded(env, capsys, monkeypatch, reading):
    from jason.commands import owner_info

    keyed_by_command(env, capsys, monkeypatch)
    village = Village()
    village.units = village.units[:1]
    village.people = village.people[:1]
    village.units[0]["tags"] = [{"tag": "Owner Occupied"}]
    village.people[0]["tags"] = [{"id": 5, "tag": "Notices by Mail"}, {"id": 6, "tag": "Owner Info 2027"}]
    capsys.readouterr()
    owner_info._apply(apply_args(by="Secretary"), lambda a: Apply(village), _community(monkeypatch), FORMS, CYCLE, env.data,
                      date(2026, 10, 10))
    out = capsys.readouterr().out
    assert "PayHOA is up to date for this cycle." in out and not village.writes
    assert "the responses inbox marks gmail:m1 recorded" in out
    assert ri.get(env.data, "gmail:m1").state is State.RECORDED
    last = ri.acts_for(env.data, "gmail:m1")[-1]
    assert last["act"] == "recorded" and last["by"] == "Secretary" and "nothing to write" in last["why"]


def test_a_plan_with_no_writes_and_no_inbox_prints_what_it_always_did(env, capsys, monkeypatch):
    from jason.commands import owner_info

    village = Village()
    village.units, village.people = [], []
    owner_info._apply(apply_args(), lambda a: Apply(village), _community(monkeypatch), FORMS, CYCLE, env.data, date(2026, 10, 10))
    out = capsys.readouterr().out
    assert "PayHOA is up to date for this cycle." in out and "responses inbox" not in out
    assert not (env.data / "responses").exists()


def test_the_command_registers_without_a_clash_and_answers_help():
    from jason.cli import build_parser

    parser = build_parser()
    sub = next(a for a in parser._actions if a.__class__.__name__ == "_SubParsersAction")
    assert "responses" in sub.choices
    text = sub.choices["responses"].format_help()
    for option in ("--check", "--list", "--show", "--read", "--confirm", "--seen-all", "--dismiss", "--from", "--since",
                   "--set", "--model", "--json"):
        assert option in text
