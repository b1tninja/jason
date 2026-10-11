"""The approvals kind ``payhoa-mailroom-send``: a saved Mailroom preview as a two-person plan, applied only by a person at a
terminal (``jason mailroom --send --yes --approval ID``).

Example Rd, two made-up owners, a PDF letter, and a fake PayHOA client that records what it is asked to mail
(tests/mailroom_support.py). Nothing reaches PayHOA."""

from __future__ import annotations

import json
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest
import webclient
from controls_support import one_person_kind  # noqa: F401 - fixture
from mailroom_support import ORG, kept

import jason.tasks.mailroom as mailroom
from jason.approvals import audit, engine, registry, store
from jason.approvals.engine import Live, Refused
from jason.approvals.kinds import mailroom_send as kind
from jason.approvals.model import ApprovalStatus as S
from jason.approvals.model import ItemClass, Result, Signature, to_dict
from jason.approvals.registry import Approver, Risk
from jason.web.app import create_app

KEY = "payhoa-mailroom-send"
MANAGER, PRESIDENT, TREASURER = "A. Manager", "B. President", "C. Treasurer"


@pytest.fixture
def world(tmp_path, monkeypatch):
    """A saved first-class preview of the two units, a fake client, and the stores in ``tmp_path/data``."""
    monkeypatch.setattr(mailroom, "READ_BACK", (0.0,))
    w = kept(tmp_path, mail_class="first-class")
    monkeypatch.setattr("jason.config.data_dir", lambda *a, **k: w.data)
    w.live = Live(w.client, ORG, w.data)
    w.terminal = Live(w.client, ORG, w.data, terminal=True)
    return w


def plan(w, ref=None, **kw):
    return engine.plan(KEY, w.live, by=kw.pop("by", MANAGER), scope={"preview": ref or w.record["id"]})


def signed(w, a=None, *, second=True):
    """Approved by the president; confirmed by the treasurer when ``second``."""
    a = a or plan(w)
    engine.decide(a.id, "all", by=PRESIDENT, data_dir=w.data)
    a = engine.submit(a.id, by=PRESIDENT, role="president", data_dir=w.data)
    if second:
        a = engine.confirm(a.id, by=TREASURER, role="treasurer", data_dir=w.data)
    return a


def letters_sent(w) -> int:
    return len(w.client.sent)


# --- the kind ---------------------------------------------------------------------------------------------------------------

def test_the_kind_is_two_person_high_risk_costed_terminal_only_and_a_payment():
    k = registry.get(KEY)
    assert registry.get("payhoa.mailroom.send") is k
    assert k.approver is Approver.TWO_PERSON and k.risk is Risk.R3 and k.has_cost
    assert k.categories == ("payment",) and k.terminal_only and k.system == "payhoa"
    assert "jason mailroom --send --yes" in k.cli and "--approval" in k.cli
    assert registry.get("owner-info-tags").terminal_only is False                      # the others apply as before


# --- the plan ---------------------------------------------------------------------------------------------------------------

def test_a_plan_is_one_item_with_the_fingerprint_the_cost_and_the_count_and_no_name_or_address(world):
    a = plan(world)
    assert a.status is S.PLANNED and a.scope == {"preview": world.record["id"]} and len(a.items) == 1
    item = a.items[0]
    assert item.klass is ItemClass.APPROVABLE and item.high_stakes and item.op == "mail letter"
    assert item.basis == world.record["fingerprint"] and item.cost_cents == world.record["totalCents"] == 330
    assert a.cost_cents == 330 and a.requested_by == MANAGER
    assert a.summary["recipients"] == 2 and a.summary["mailClass"] == "first class" and a.summary["tracking"] == ""
    assert a.summary["fingerprint"] == world.record["fingerprint"][:12] and a.summary["billedPages"] == 3
    assert engine.needs_second(a, data_dir=world.data)
    assert world.client.sent == []                                                    # a plan mails nothing
    text = json.dumps(to_dict(a))
    for private in ("A. Owner", "B. Owner", "Example City", "95000"):
        assert private not in text
    assert any("cannot be recalled" in n for n in a.notes)


def test_a_plan_names_the_preview_by_a_prefix_of_its_id_or_its_fingerprint(world):
    a = plan(world, world.record["fingerprint"][:8])
    assert a.scope == {"preview": world.record["id"]}
    with pytest.raises(KeyError, match="no saved preview"):
        plan(world, "nothing")
    with pytest.raises(ValueError, match="scope names the saved preview"):
        engine.plan(KEY, world.live, by=MANAGER, scope={})


def test_a_second_plan_of_the_same_preview_supersedes_the_first(world):
    first = plan(world)
    second = plan(world)
    assert store.load(first.id, world.data).status is S.SUPERSEDED and second.status is S.PLANNED


def test_a_stale_preview_is_planned_as_an_item_nobody_can_approve(world):
    world.pdf.write_bytes(world.pdf.read_bytes() + b"\n% edited")
    a = plan(world)
    assert a.items[0].klass is ItemClass.INFORMATIONAL and "the PDF changed" in a.items[0].why
    with pytest.raises(Refused, match="never approvable"):
        engine.decide(a.id, [a.items[0].id], by=PRESIDENT, data_dir=world.data)
    world.pdf.write_bytes(world.pdf.read_bytes()[: -len(b"\n% edited")])             # put the file back
    assert plan(world).items[0].klass is ItemClass.APPROVABLE


def test_an_old_preview_is_planned_as_stale(world):
    saved = world.path
    record = json.loads(saved.read_text(encoding="utf-8"))
    record["read"] = "2020-01-01T00:00:00+00:00"
    saved.write_text(json.dumps(record), encoding="utf-8")
    a = plan(world)
    assert a.items[0].klass is ItemClass.INFORMATIONAL and "24-hour limit" in a.items[0].why


# --- two people ---------------------------------------------------------------------------------------------------------------

def test_two_distinct_people_sign_before_anything_can_apply(world):
    a = plan(world)
    engine.decide(a.id, "all", by=PRESIDENT, data_dir=world.data)
    a = engine.submit(a.id, by=PRESIDENT, data_dir=world.data)
    with pytest.raises(Refused, match="submitted it"):
        engine.confirm(a.id, by=" b. president ", data_dir=world.data)
    with pytest.raises(Refused, match="asked for the plan"):
        engine.confirm(a.id, by=MANAGER, data_dir=world.data)
    assert any("second, distinct person must confirm" in p for p in engine.problems(a, world.data))
    with pytest.raises(Refused, match="second, distinct person must confirm"):
        engine.apply(a.id, world.terminal, by=PRESIDENT, data_dir=world.data)
    assert letters_sent(world) == 0


# --- apply is a terminal's -----------------------------------------------------------------------------------------------------

def test_the_engine_refuses_to_apply_it_anywhere_but_the_terminal_command(world):
    a = signed(world)
    with pytest.raises(Refused, match="applied by a person at a terminal: jason mailroom --send --yes"):
        engine.apply(a.id, world.live, by=PRESIDENT, data_dir=world.data)          # what jason-web and approvals apply do
    assert letters_sent(world) == 0 and store.load(a.id, world.data).status is S.APPROVED
    refused = [e for e in audit.read(world.data, a.id) if e["event"] == "apply.refused"]
    assert refused and "terminal" in refused[0]["detail"]


def test_the_applier_alone_never_mails_without_the_terminal_flag(world):
    a = signed(world)
    planned = registry.get(KEY).plan(world.live, a.scope)
    recorder = engine.Recorder(store.load(a.id, world.data), world.data, actor=PRESIDENT, via="test")
    registry.get(KEY).apply(world.live, planned, planned.items, recorder)
    assert letters_sent(world) == 0 and recorder.result(a.items[0].id) is Result.BLOCKED


def test_a_fully_signed_plan_whose_letter_still_matches_is_mailed_and_recorded(world):
    a = signed(world, plan(world, world.record["fingerprint"][:8]))
    done = engine.apply(a.id, world.terminal, by=PRESIDENT, data_dir=world.data)
    assert done.superseded_by is None and done.approval.status is S.APPLIED
    item = done.approval.items[0]
    assert item.result is Result.APPLIED and "mailed: batch 2" in item.result_detail
    assert letters_sent(world) == 1
    sent = world.client.sent[0]
    assert sent["owner_ids"] == [1101, 1102] and sent["unit_ids"] == [101, 102] and sent["mail_class"] == "first class"
    logged = json.loads((world.data / "mailroom" / "sent.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert logged["approval"] == a.id and logged["fingerprint"] == world.record["fingerprint"]
    assert logged["by"] == PRESIDENT and logged["previewId"] == world.record["id"]
    events = [e["event"] for e in audit.read(world.data, a.id)]
    assert {"item.applying", "item.applied", "approval.applied", "apply.started"} <= set(events)


def test_a_letter_that_changed_after_signing_is_not_mailed_and_the_plan_is_superseded(world):
    a = signed(world)
    world.client.rows[101]["ownerId"] = 2001                                           # PayHOA names a different owner
    done = engine.apply(a.id, world.terminal, by=PRESIDENT, data_dir=world.data)
    assert letters_sent(world) == 0 and done.superseded_by is not None
    assert store.load(a.id, world.data).status is S.SUPERSEDED
    assert done.superseded_by.items[0].klass is ItemClass.INFORMATIONAL               # the preview no longer matches
    assert "different owners" in done.superseded_by.items[0].why
    assert not (world.data / "mailroom" / "sent.jsonl").exists()


def test_a_pdf_edited_after_signing_is_not_mailed(world):
    a = signed(world)
    world.pdf.write_bytes(world.pdf.read_bytes() + b"\n% edited")
    done = engine.apply(a.id, world.terminal, by=PRESIDENT, data_dir=world.data)
    assert letters_sent(world) == 0 and done.superseded_by is not None and "the PDF changed" in done.superseded_by.items[0].why


def test_signatures_must_be_two_distinct_people_on_this_plan(world):
    a = signed(world)
    stored = store.load(a.id, world.data)
    stored.second = Signature(PRESIDENT, stored.second.at, stored.fingerprint)       # the same person twice
    store.save(stored, world.data)
    done = engine.apply(a.id, world.terminal, by=PRESIDENT, data_dir=world.data)
    assert letters_sent(world) == 0 and done.approval.items[0].result is Result.BLOCKED
    assert "signed twice" in done.approval.items[0].result_detail
    # and a signature on some other plan
    b = signed(world, plan(world))
    stored = store.load(b.id, world.data)
    stored.second = replace(stored.second, fingerprint="0" * 64)
    store.save(stored, world.data)
    done = engine.apply(b.id, world.terminal, by=PRESIDENT, data_dir=world.data)
    assert letters_sent(world) == 0 and "different plan" in done.approval.items[0].result_detail


def test_a_send_that_fails_before_it_goes_out_is_failed_and_one_that_may_have_gone_is_uncertain(world):
    from payhoa.exceptions import PayhoaError

    a = signed(world)
    world.client.send_mail_pdf = lambda *args, **kw: (_ for _ in ()).throw(PayhoaError("no payment method"))
    done = engine.apply(a.id, world.terminal, by=PRESIDENT, data_dir=world.data)
    assert done.approval.items[0].result is Result.FAILED and "PayHOA refused" in done.approval.items[0].result_detail
    b = signed(world, plan(world))
    world.client.send_mail_pdf = lambda *args, **kw: (_ for _ in ()).throw(TimeoutError("read timed out"))
    done = engine.apply(b.id, world.terminal, by=PRESIDENT, data_dir=world.data)
    assert done.approval.items[0].result is Result.UNCERTAIN and "look in PayHOA's Mailroom" in done.approval.items[0].result_detail


def test_a_notice_preview_is_kept_as_the_notice_when_it_is_mailed(tmp_path, monkeypatch):
    monkeypatch.setattr(mailroom, "READ_BACK", (0.0,))
    w = kept(tmp_path, mail_class="first-class", notice="mailing-notice-2099-10")
    monkeypatch.setattr("jason.config.data_dir", lambda *a, **k: w.data)
    live = Live(w.client, ORG, w.data, terminal=True)
    a = engine.plan(KEY, live, by=MANAGER, scope={"preview": w.record["id"]})
    a = signed(SimpleNamespace(data=w.data), a)
    done = engine.apply(a.id, live, by=PRESIDENT, data_dir=w.data)
    assert done.approval.status is S.APPLIED and "kept as the notice mailing-notice-2099-10" in done.approval.items[0].result_detail
    assert (w.data / "notices" / "mailing-notice-2099-10").is_dir()


# --- the web never applies it ------------------------------------------------------------------------------------------------

def _dist(tmp_path: Path) -> Path:
    dist = tmp_path / "dist"
    dist.mkdir(exist_ok=True)
    (dist / "index.html").write_text("<!doctype html><html><head><title>t</title></head><body></body></html>", encoding="utf-8")
    return dist


def test_the_web_apply_route_refuses_this_kind_even_with_apply_on(world, tmp_path):
    calls = []

    @contextmanager
    def factory(k):
        calls.append(k.key)
        yield world.terminal                       # even a live context that says terminal: the route never gets that far

    app = create_app(_dist(tmp_path), None, approvals_live=factory, allow_apply=True)
    c = webclient.client(app)
    a = signed(world)
    r = c.post(f"/api/approvals/{a.id}/apply", json={"by": PRESIDENT, "confirm": a.fingerprint})
    assert r.status_code == 403 and r.json["terminalOnly"] and "jason mailroom --send --yes" in r.json["error"]
    assert calls == [] and letters_sent(world) == 0 and store.load(a.id, world.data).status is S.APPROVED
    kinds = {k["key"]: k for k in c.get("/api/approvals/kinds").json["kinds"]}
    assert kinds[KEY]["terminalOnly"] is True and kinds[KEY]["twoPerson"] and kinds["owner-info-tags"]["terminalOnly"] is False


# --- jason mailroom --approval ------------------------------------------------------------------------------------------------

def cli_run(monkeypatch, capsys, world, *argv):
    from jason import cli

    @contextmanager
    def agent(args):
        yield SimpleNamespace(settings=SimpleNamespace(ownership_db=world.data / "ownership.db"),
                              payhoa=lambda: world.client, org_id=ORG)

    monkeypatch.setattr(cli, "_agent", agent)
    args = cli.build_parser().parse_args(list(argv))
    code = args.func(args)
    out = capsys.readouterr()
    return code, out.out, out.err


def test_the_cli_mails_a_plan_only_when_two_distinct_people_signed(world, monkeypatch, capsys):
    fp = world.record["fingerprint"][:12]
    a = plan(world)
    mail = ("mailroom", "--approval", a.id, "--send", "--yes", "--expect", fp, "--by", "D. Terminal")
    code, out, err = cli_run(monkeypatch, capsys, world, *mail)                      # planned, nobody signed
    assert code == 2 and letters_sent(world) == 0 and "nothing mailed" in err and "approved or partially approved" in err
    engine.decide(a.id, "all", by=PRESIDENT, data_dir=world.data)
    engine.submit(a.id, by=PRESIDENT, data_dir=world.data)
    code, out, err = cli_run(monkeypatch, capsys, world, *mail)                      # one signature
    assert code == 2 and letters_sent(world) == 0 and "second, distinct person must confirm" in err
    engine.confirm(a.id, by=TREASURER, data_dir=world.data)
    code, out, err = cli_run(monkeypatch, capsys, world, "mailroom", "--approval", a.id)    # a check: no --send
    assert code == 0 and letters_sent(world) == 0 and "Nothing mailed" in out
    code, out, err = cli_run(monkeypatch, capsys, world, "mailroom", "--approval", a.id, "--send", "--yes", "--expect", "ab" * 6)
    assert code == 2 and letters_sent(world) == 0 and "not the plan's fingerprint" in err
    code, out, err = cli_run(monkeypatch, capsys, world, *mail)
    assert code == 0, err
    assert letters_sent(world) == 1 and "applied" in out and "mailed: batch 2" in out
    assert store.load(a.id, world.data).status is S.APPLIED
    logged = json.loads((world.data / "mailroom" / "sent.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert logged["approval"] == a.id and logged["by"] == "D. Terminal"
    code, out, err = cli_run(monkeypatch, capsys, world, *mail)                      # applied once: never again
    assert code == 2 and letters_sent(world) == 1 and "applied" in err


def test_the_cli_mails_nothing_when_the_letter_changed_since_signing(world, monkeypatch, capsys):
    a = signed(world)
    world.client.rows[102]["address"] = "9 Other Rd\nExample City, CA 95000"
    code, out, err = cli_run(monkeypatch, capsys, world, "mailroom", "--approval", a.id, "--send", "--yes")
    assert code == 1 and letters_sent(world) == 0 and "nothing mailed" in out and "superseded" in out


def test_jason_approvals_apply_never_mails_this_kind(world, monkeypatch, capsys):
    a = signed(world)
    monkeypatch.setattr("jason.commands.approvals._data_dir", lambda args: world.data)
    code, out, err = cli_run(monkeypatch, capsys, world, "approvals", "apply", a.id, "--yes", "--by", PRESIDENT)
    assert code == 2 and letters_sent(world) == 0 and "applied by a person at a terminal" in err
    code, out, err = cli_run(monkeypatch, capsys, world, "mailroom", "--approval", "apr-nope", "--send", "--yes")
    assert code == 2 and "nothing mailed" in err


def test_the_cli_refuses_an_approval_of_another_kind(world, monkeypatch, capsys, one_person_kind):
    other = engine.plan(one_person_kind.key, world.live, by=MANAGER)
    code, out, err = cli_run(monkeypatch, capsys, world, "mailroom", "--approval", other.id, "--send", "--yes")
    assert code == 2 and letters_sent(world) == 0 and f"not {KEY}" in err


def test_the_legacy_one_person_kinds_are_unchanged_by_the_terminal_flag():
    assert Live().terminal is False and all(not k.terminal_only for k in registry.kinds() if k.key != KEY)
