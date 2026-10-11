"""``jason controls``: driven through the argument parser in a temporary data folder, over a made-up "Example Bylaws"
outline and a stub community. It lists, shows, suggests (and records), and puts a suggestion before the board; it has no way
to adopt, decline, defer, or retire."""

from __future__ import annotations

import json

import pytest

from controls_support import roster
from controls_world import Home, write_outline
from jason.community.base import OfficerRole as R
from jason.controls import store
from jason.controls.types import ControlState

_PARSER = []


def parser():
    if not _PARSER:
        from jason.cli import build_parser

        _PARSER.append(build_parser())
    return _PARSER[0]


@pytest.fixture
def world(tmp_path, monkeypatch):
    monkeypatch.setenv("JASON_SPEC_DIR", str(tmp_path / "spec"))
    monkeypatch.setattr("jason.commands._shared.data_dir", lambda args=None: tmp_path)
    write_outline(tmp_path)
    home = Home()
    monkeypatch.setattr("jason.community.community", lambda: home)
    home.root = tmp_path
    return home


@pytest.fixture
def run(world, capsys):
    def go(*argv):
        args = parser().parse_args(["controls", *argv])
        code = args.func(args)
        out = capsys.readouterr()
        return code, out.out, out.err

    go.world = world
    return go


def suggested(run, *extra):
    code, out, err = run("--suggest", "--duties-read", "--record", "--by", "A Secretary", *extra)
    assert code == 0, err
    return out


# --- registered, and no way to decide -------------------------------------------------------------------------------------

def test_the_command_is_registered_and_says_it_decides_nothing_and_cannot_retire():
    from jason.commands import MODULES

    assert "controls" in MODULES
    sub = next(a for a in parser()._actions if a.__class__.__name__ == "_SubParsersAction")
    text = " ".join(sub.choices["controls"].format_help().split())
    assert "it decides nothing" in text and "by the secretary" in text
    assert "--retire" not in text
    with pytest.raises(SystemExit):
        parser().parse_args(["controls", "--retire", "payment-signers"])


def test_an_empty_list_says_the_documents_have_not_been_read(run):
    code, out, err = run()
    assert code == 0 and "has not read your governing documents" in out and "0 control(s)" in out
    code, out, _ = run("--list", "--json")
    body = json.loads(out)
    assert body["counts"]["total"] == 0 and body["label"] == "jason suggests; the board adopts"


# --- suggest ------------------------------------------------------------------------------------------------------------------

def test_suggest_waits_for_the_duties_to_be_read(run):
    code, out, err = run("--suggest")
    assert code == 0 and "jason suggests nothing" in out and "not been read and confirmed" in out
    code, out, _ = run("--suggest", "--record", "--by", "A Secretary")
    assert code == 0 and "suggests nothing" in out and not store.acts(run.world.root)


def test_the_profile_confirming_the_duties_is_enough(run, monkeypatch):
    monkeypatch.setattr(run.world, "_duties", True)
    code, out, _ = run("--suggest")
    assert code == 0 and "SUGGESTION payment-signers" in out


def test_suggest_prints_the_provision_whole_the_floor_the_reading_and_a_question_apart(run):
    code, out, err = run("--suggest", "--duties-read")
    assert code == 0, err
    assert "3 suggestion(s), 1 question(s)" in out and "Nothing here is adopted" in out
    assert "All checks, drafts, or orders for payment shall be signed by two directors." in out
    assert "signers = 2" in out and "jason's reading, not the provision" in out
    assert "QUESTION (not a suggestion)" in out and "Drafts on the Association are kept by the treasurer" in out
    assert not store.acts(run.world.root)                                  # reading records nothing
    code, out, _ = run("--suggest", "--duties-read", "--json")
    body = json.loads(out)
    assert {s["type"] for s in body["suggestions"]} == {"payment-signers", "reserve-signers", "contract-authorization"}
    assert len(body["questions"]) == 1 and body["ready"] is True and body["recorded"] is None


def test_one_document_can_be_named_and_an_unknown_one_is_said_not_skipped(run):
    code, out, _ = run("--suggest", "--duties-read", "--document", "no-such-document")
    assert code == 0 and "0 suggestion(s)" in out and "not read: no-such-document" in out


def test_record_needs_by_and_appends_suggested_acts_by_jason(run):
    code, _, err = run("--suggest", "--duties-read", "--record")
    assert code == 2 and "--by" in err and not store.acts(run.world.root)
    out = suggested(run)
    assert "Recorded 3 suggested act(s) by jason at the request of A Secretary" in out
    rows = store.acts(run.world.root)
    assert [(r["act"], r["by"]) for r in rows] == [("suggest", "jason")] * 3
    cs = store.load(run.world.root)
    assert {c.state for c in cs} == {ControlState.SUGGESTED} and all(c.decision == "" for c in cs)
    again = suggested(run)
    assert "Recorded 0 suggested act(s)" in again and "already have a control recorded" in again
    assert len(store.acts(run.world.root)) == 3


def test_record_goes_only_with_suggest(run):
    code, _, err = run("--record", "--by", "A Secretary")
    assert code == 2 and "--suggest" in err


# --- list, show, roster ---------------------------------------------------------------------------------------------------------

def test_list_groups_by_family_with_the_state_in_words_and_filters(run):
    suggested(run)
    code, out, _ = run("--list")
    assert "MONEY" in out and "CONTRACTS" in out and "payment-signers: Payment signers [suggested]" in out
    assert "QUESTION Example Bylaws Section 9.4" in out
    code, out, _ = run("--list", "--family", "contracts")
    assert "contract-authorization" in out and "payment-signers" not in out
    code, out, _ = run("--list", "--state", "adopted")
    assert "payment-signers" not in out
    code, out, _ = run("--list", "--json")
    body = json.loads(out)
    assert body["counts"]["suggested"] == 3 and body["counts"]["questions"] == 1
    assert all(r["inForce"]["ok"] is False and r["standing"] == "suggested" for r in body["controls"])


def test_show_prints_the_six_bands_and_a_suggestion_never_says_in_force(run):
    suggested(run)
    code, out, err = run("--show", "payment-signers")
    assert code == 0, err
    for band in ("1 THE PROVISION", "2 WHAT JASON SUGGESTED", "4 WHAT IT CHANGES", "5 CAN THE ROSTER SATISFY IT", "6 HISTORY"):
        assert band in out, band
    assert "3 WHAT THE BOARD DECIDED" not in out and "in force" not in out.split("4 WHAT IT CHANGES")[0]
    assert "All checks, drafts, or orders for payment shall be signed by two directors." in out
    assert "suggest by jason" in out
    code, _, err = run("--show", "nope")
    assert code == 2 and "no control nope" in err


def test_roster_check_names_offices_and_counts_never_a_person(run):
    suggested(run)
    code, out, _ = run("--roster-check", "payment-signers")
    assert code == 0 and "needs 2 board member; 1 treasurer" in out and "The roster can satisfy it" in out
    assert "Person" not in out                                                       # the made-up names stay out
    run.world._roster = tuple(roster(R.DIRECTOR))
    code, out, _ = run("--roster-check", "payment-signers", "--json")
    check = json.loads(out)
    assert {"office": "treasurer"} in check["missing"] and check["lacks"]
    assert all(set(s) == {"office", "count"} for s in check["seated"])


# --- propose --------------------------------------------------------------------------------------------------------------------

def test_propose_needs_by_and_a_key_that_exists(run):
    suggested(run)
    code, _, err = run("--propose", "payment-signers")
    assert code == 2 and "--by" in err
    code, _, err = run("--propose", "nope", "--by", "A Secretary")
    assert code == 2 and "no control nope" in err


def test_propose_makes_a_board_item_with_the_provision_and_adopts_nothing(run):
    from jason.tasks import board_items

    suggested(run)
    code, out, err = run("--propose", "payment-signers", "--by", "A Secretary")
    assert code == 0, err
    assert "board item control-payment-signers" in out and "It is not adopted" in out
    item = next(i for i in board_items.load(run.world.root) if i.id == "control-payment-signers")
    assert item.status.value == "proposed" and item.authority == "Example Bylaws Section 9.1"
    assert any("signed by two directors" in e for e in item.evidence)
    c = store.get("payment-signers", run.world.root)
    assert c.state is ControlState.PROPOSED and c.decision == "" and c.effective is None
    assert c.history[-1].by == "A Secretary" and "control-payment-signers" in c.history[-1].why
    # again: refreshes the item, records no further act
    before = len(store.acts(run.world.root))
    code, out, _ = run("--propose", "payment-signers", "--by", "A Secretary")
    assert code == 0 and "Refreshed" in out and len(store.acts(run.world.root)) == before
    assert len([i for i in board_items.load(run.world.root) if i.id.startswith("control-")]) == 1
    # the list now says so
    body = json.loads(run("--list", "--json")[1])
    row = next(r for r in body["controls"] if r["key"] == "payment-signers")
    assert row["state"] == "proposed" and row["proposedAs"] == "control-payment-signers"


def test_one_act_at_a_time(run):
    code, _, err = run("--suggest", "--show", "payment-signers")
    assert code == 2 and "one act at a time" in err
