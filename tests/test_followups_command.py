"""``jason followups``, ``jason campaigns`` (the funnel), and ``jason responses --add-manual`` (docs/followups-design.md, build
steps 1 and 2): the output, the refusals, and that no address, email, phone, or answer is printed.

Made up and offline, with the fixtures of ``test_followups`` (a made-up association and its data folder) and a fake clock.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from test_followups import NOON, PRIVATE, TODAY, Quiet, World, board, data, keep, arrival, offline  # noqa: F401

from jason.commands import followups as cmd
from jason.commands import responses as responses_cmd
from jason.community.response_inbox import Channel
from jason.tasks import response_inbox as ri


class Parsing:
    """The made-up association for what a command asks of it, and the active profile for what the parser asks (the choices of
    other commands' options are read from it when the parser is built)."""

    def __init__(self, real) -> None:
        self.real, self.made = real, World()

    def __getattr__(self, name):
        return getattr(self.made if hasattr(self.made, name) else self.real, name)


@pytest.fixture
def env(data, tmp_path, monkeypatch):
    """A made-up .env whose data folder is the tmp dir, the made-up association, and the fake clock."""
    from jason import community as package

    path = tmp_path / ".env"
    path.write_text(f"PAYHOA_CATALOG={data / 'payhoa.db'}\n", encoding="utf-8")
    real = package.community
    monkeypatch.setattr(cmd, "_community", lambda: World())
    monkeypatch.setattr(cmd, "_today", lambda: TODAY)
    monkeypatch.setattr(responses_cmd, "_community", lambda: World())
    monkeypatch.setattr(package, "community", lambda *a, **k: Parsing(real(*a, **k)))
    monkeypatch.setattr(ri, "now_utc", lambda: NOON)
    return SimpleNamespace(path=path, data=data)


def run(env, capsys, *argv):
    from jason.cli import main

    with pytest.raises(SystemExit) as done:
        main([*argv, "--env", str(env.path)])
    out = capsys.readouterr()
    return int(done.value.code or 0), out.out, out.err


def clean(text: str) -> None:
    assert not [p for p in PRIVATE if p in text] and "@" not in text, text


def listed(env, capsys, *args):
    code, out, err = run(env, capsys, "followups", "--json", *args)
    assert code == 0, err
    return json.loads(out)


def ident(env, capsys, kind, subject):
    return next(i["id"] for i in listed(env, capsys, "--all")["items"] if i["kind"] == kind and i["subject"] == subject)


# -- the listing -----------------------------------------------------------------------------------------------------------

def test_the_listing_groups_the_items_with_basis_outstanding_command_and_the_age_of_the_source(env, board, capsys, offline):
    code, out, err = run(env, capsys, "followups")
    assert code == 0 and not err
    clean(out)
    assert out.startswith("Follow-ups as of 2026-10-05: 0 overdue, 0 due today, ")
    assert "jason sends, resends, and completes nothing" in out and "Disk only" in out
    assert "campaign record: written" in out and "sent-copy catalog: written 2026-10-05 05:00 (7h ago)" in out
    assert "last check that succeeded 2026-10-05 10:00 (2h ago)" in out and "notice ledger: synced" in out
    assert "Coming up (" in out and "Overdue" not in out
    assert "2026-10-16  remind         " in out and "Remind 1 owner who has not answered the KM27E request" in out
    assert "basis: proposed policy (proposed: remind 7 days before the return-by date (the board has not adopted a number)" in out
    assert "outstanding: 1: 105 Example Way (Eve Holder)" in out and "window: until 2026-10-23" in out
    assert "basis: law (CIV 4041(e), 4040(a)(2)); proposed: 3 days after the outcome was read (2026-10-03)" in out
    assert 'run: jason owner-info --mail-batch --only "104 Example Way" --resend' in out
    assert "run: jason owner-info --email-batch --follow-up reminder" in out and "run: jason responses --read gmail:m1 --by NAME" in out
    assert "source: the notice ledger was synced" in out and "source: the inbox was last checked 2026-10-05T10:00:00+00:00 (2h ago)" in out
    assert "--done ID --by NAME" in out and "A number marked proposed is the board's to adopt" in out
    assert "2026-12-01" not in out                                              # the reports' day is past the 14 days


def test_the_listing_narrows_by_campaign_kind_days_and_overdue_and_prints_json(env, board, capsys, offline):
    code, out, _ = run(env, capsys, "followups", "--kind", "return_by", "--within", "30")
    assert code == 0 and "Answers to the KM27E request are due" in out and "Remind" not in out
    code, out, _ = run(env, capsys, "followups", "--all", "--campaign", "km27e", "--kind", "enter-by")
    assert code == 0 and "basis: law (CIV 4041(b)(1)" in out and "2026-11-01" in out
    code, out, _ = run(env, capsys, "followups", "--overdue")
    assert code == 0 and "Nothing matches as of 2026-10-05" in out and "jason followups --all" in out
    body = listed(env, capsys, "--within", "60")
    assert body["asOf"] == "2026-10-05" and body["within"] == 60 and body["counts"]["coming"] == len(body["items"])
    first = body["items"][0]
    assert {"id", "kind", "due", "basis", "cite", "outstanding", "names", "state", "command", "sourceAge"} <= set(first)
    assert body["ages"]["catalog"]["ageHours"] == 7.0 and body["note"].startswith("disk only")
    clean(json.dumps(body))
    assert [i["kind"] for i in listed(env, capsys, "--kind", "resend")["items"]] == ["resend", "resend"]


def test_nothing_due_says_when_it_was_true_and_what_is_missing(env, capsys, monkeypatch, offline):
    monkeypatch.setattr(cmd, "_community", lambda: Quiet())
    code, out, _ = run(env, capsys, "followups")
    assert code == 0 and "0 overdue, 0 due today, 0 coming up" in out
    assert "Nothing matches as of 2026-10-05 (0 follow-up(s) in all" in out
    assert "campaign record: not on disk (no campaign is recorded" in out and "notice ledger: not on disk" in out
    assert "response inbox: not on disk (no check has been run" in out


# -- a person's acts -------------------------------------------------------------------------------------------------------

def test_done_defer_drop_and_add_are_a_persons_acts_and_are_kept(env, board, capsys, offline):
    remind = ident(env, capsys, "remind", "KM27E")
    resend = ident(env, capsys, "resend", "notice-1")
    ending = ident(env, capsys, "close", "KM27E")
    code, out, _ = run(env, capsys, "followups", "--done", remind, "--by", "Pat Example", "--note", "sent the reminder")
    assert code == 0 and f"Marked {remind} done by Pat Example" in out and "sends, resends, and completes nothing" in out
    code, out, _ = run(env, capsys, "followups", "--defer", resend, "--to", "2026-10-09", "--by", "Pat Example", "--why", "owner will call")
    assert code == 0 and f"Deferred {resend} to 2026-10-09 by Pat Example: owner will call" in out
    code, out, _ = run(env, capsys, "followups", "--drop", ending, "--by", "Pat Example", "--why", "kept open by the board")
    assert code == 0 and f"Dropped {ending} by Pat Example: kept open by the board" in out
    code, out, _ = run(env, capsys, "followups", "--add", "--date", "2026-10-08", "--text", "Call the printer", "--by", "Pat Example",
                       "--campaign", "km27e")
    assert code == 0 and "Added fu-" in out and "due 2026-10-08" in out
    shown = {i["id"] for i in listed(env, capsys)["items"]}
    assert not {remind, resend, ending} & shown and listed(env, capsys, "--kind", "manual")["items"][0]["what"] == "Call the printer"
    code, out, _ = run(env, capsys, "followups", "--all")
    assert code == 0 and "Done (1)" in out and "[done by Pat Example]" in out and "Deferred (1)" in out and "Dropped (1)" in out
    assert "[deferred to 2026-10-09 by Pat Example]" in out and "owner will call" in out
    clean(out)
    rows = [json.loads(line) for line in (env.data / "followups" / "acts.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [r["act"] for r in rows] == ["done", "defer", "drop", "add"] and all(r["by"] == "Pat Example" for r in rows)


def test_every_refusal_is_a_reason_on_stderr_and_exit_two_and_writes_nothing(env, board, capsys, offline):
    remind = ident(env, capsys, "remind", "KM27E")

    def refused(match, *argv):
        code, out, err = run(env, capsys, "followups", *argv)
        assert code == 2 and err.startswith("jason followups: ") and match in err and not out, (argv, out, err)

    refused("--by is required", "--done", remind)
    refused("--by is required", "--done", remind, "--by", " ")
    refused("--to is required with --defer", "--defer", remind, "--by", "Pat Example", "--why", "later")
    refused("--to is a day, YYYY-MM-DD", "--defer", remind, "--to", "2026-13-45", "--by", "Pat Example", "--why", "later")
    refused("--to must be a day after today", "--defer", remind, "--to", "2026-10-05", "--by", "Pat Example", "--why", "later")
    refused("--why is required with --defer", "--defer", remind, "--to", "2026-10-09", "--by", "Pat Example")
    refused("--why is required with --drop", "--drop", remind, "--by", "Pat Example")
    refused("--by is required", "--drop", remind, "--why", "no")
    refused("no follow-up 'fu-nothing'", "--done", "fu-nothing", "--by", "Pat Example")
    refused("--date is required with --add", "--add", "--text", "x", "--by", "Pat Example")
    refused("--date is a day, YYYY-MM-DD", "--add", "--date", "soon", "--text", "x", "--by", "Pat Example")
    refused("--text is required", "--add", "--date", "2026-10-09", "--by", "Pat Example")
    refused("--by is required", "--add", "--date", "2026-10-09", "--text", "x")
    refused("--to does not go with the listing", "--to", "2026-10-09")
    refused("--by does not go with the listing", "--by", "Pat Example")
    refused("--why does not go with --done", "--done", remind, "--by", "Pat Example", "--why", "x")
    refused("--kind does not go with --drop", "--drop", remind, "--by", "Pat Example", "--why", "x", "--kind", "remind")
    refused("--all shows every date", "--all", "--within", "3")
    refused("--overdue and --all do not go together", "--all", "--overdue")
    refused("--within is a number of days", "--within", "-1")
    refused("no kind 'nope'", "--kind", "nope")
    code, _, err = run(env, capsys, "followups", "--done", remind, "--drop", remind)
    assert code == 2 and "not allowed with" in err                                       # one act at a time
    assert not (env.data / "followups").exists(), "a refused act writes nothing"


# -- the funnel on `jason campaigns` ----------------------------------------------------------------------------------------

def test_campaigns_shows_each_funnel_by_channel_and_its_next_follow_up(env, board, capsys, offline):
    code, out, err = run(env, capsys, "campaigns")
    assert code == 0 and not err
    clean(out)
    assert "funnel: asked 5; answered 3 (payhoa 1, gmail 1, manual 1); outstanding 1; unreachable 1; next: " in out
    assert "funnel: asked 0 + 1 mailing(s); answered 3 (payhoa 1, gmail 1, manual 1); outstanding -; unreachable 1" in out
    assert "jason followups --campaign KM27E" in out and "`jason campaigns --show CODE` has its ages" in out


def test_show_prints_the_full_funnel_with_ages_the_outstanding_and_the_unreachable(env, board, capsys, offline):
    code, out, err = run(env, capsys, "campaigns", "--show", "km27e")
    assert code == 0 and not err
    clean(out)
    assert "funnel as of 2026-10-05 12:00 UTC (disk only; an owner who answered by any method is not outstanding):" in out
    assert "asked: 5 copies (email 5); the catalog is 7h old" in out
    assert "answered: 3 to request annual-2027; read 1, confirmed 1, recorded 0" in out
    assert "payhoa  answered 1, read 1, confirmed 1, recorded 0" in out and "manual  answered 1, read 0, confirmed 0, recorded 0  (keyed by a person)" in out
    assert "gmail   answered 1, read 0, confirmed 0, recorded 0  (checked 2h old)" in out
    assert "outstanding: 1; sources 7h old, last check 2h old" in out and "105 Example Way  Eve Holder  (email, sent 3d ago)" in out
    assert "unreachable: 1 (no delivery reached them: not counted as outstanding); ledger synced" in out
    assert "104 Example Way  email bounced" in out and "note: request annual-2027 is watched by several campaigns" in out
    assert "next follow-up: " in out
    body = json.loads(run(env, capsys, "campaigns", "--show", "KM27E", "--json")[1])
    assert body["funnel"]["unreachable"]["count"] == 1 and body["nextFollowUp"]["campaign"] in ("KM27E", "")
    clean(json.dumps(body))


def test_a_campaign_with_no_catalog_inbox_or_ledger_says_what_is_missing(env, data, capsys, offline):
    from jason.tasks import campaigns
    from test_campaigns import CYCLE

    campaigns.open_campaign(World(), "annual-info", channel="email", cycle=CYCLE, by="Pat Example", data_dir=data, now=NOON)
    code, out, _ = run(env, capsys, "campaigns", "--show", "KM27E")
    assert code == 0
    assert "outstanding: not known" in out and "unreachable: not known" in out
    assert "missing: sent-copy catalog: no copy has been recorded as sent" in out
    assert "missing: response inbox: no check has been run" in out and "missing: notice ledger: no notice ledger is on disk" in out


# -- the manual intake channel ---------------------------------------------------------------------------------------------

def test_add_manual_keys_a_return_as_an_arrival_and_prints_no_address(env, board, capsys, tmp_path, offline):
    scan = tmp_path / "form.pdf"
    scan.write_bytes(b"%PDF-1.4 made up")
    code, out, err = run(env, capsys, "responses", "--add-manual", "--request", "annual-2027", "--how", "handed in at the office",
                         "--who", "Eve Holder eve@example.org", "--unit", "105 Example Way", "--file", str(scan), "--by", "Secretary")
    assert code == 0 and not err
    clean(out)
    assert "Added manual:" in out and "Eve Holder [email], 105 Example Way; handed in at the office; 1 file(s)" in out
    assert "Nothing was sent, and nothing was written to PayHOA" in out and "jason responses --read manual:" in out
    code, out, _ = run(env, capsys, "responses", "--list", "--channel", "manual")
    assert code == 0 and "2 arrival(s)" in out and "[new]" in out and "handed in at the office" in out and "form.pdf" in out
    clean(out)
    code, out, _ = run(env, capsys, "responses")
    assert "manual  keyed by a person from paper or a call (nothing to check)" in out
    code, out, _ = run(env, capsys, "responses", "--add-manual", "--request", "annual-2027", "--how", "by phone", "--who", "Ana Example",
                       "--by", "Secretary", "--json")
    body = json.loads(out)
    assert code == 0 and body["channel"] == "manual" and body["state"] == "new" and body["attachments"] == []
    assert ri.get(env.data, body["id"]).channel is Channel.MANUAL


def test_add_manual_refusals_follow_the_commands_style(env, board, capsys, offline):
    def refused(match, *argv):
        code, out, err = run(env, capsys, "responses", *argv)
        assert code == 2 and err.startswith("jason responses: ") and match in err and not out, (argv, out, err)

    base = ("--add-manual", "--request", "annual-2027", "--how", "by phone", "--who", "Ana Example", "--by", "Secretary")

    def without(flag):
        args = list(base)
        at = args.index(flag)
        return args[:at] + args[at + 2:]

    refused("--how is required with --add-manual", *without("--how"))
    refused("--request is required with --add-manual", *without("--request"))
    refused("--who is required with --add-manual", *without("--who"))
    refused("--by is required", *without("--by"))
    refused("no request 'another'", *base[:2], "another", *base[3:])
    refused("no file 'missing.pdf'", *base, "--file", "missing.pdf")
    refused("--how does not go with the inbox view", "--how", "by phone")
    refused("--who does not go with --list", "--list", "--who", "Ana Example")
    refused("--file does not go with --check", "--check", "--file", "x.pdf")
    refused("--state does not go with --add-manual", *base, "--state", "new")
