"""The members' copy of the board packet: what it keeps, what it leaves out and says so, and its way through Approvals."""

from __future__ import annotations

import argparse
from datetime import date

import pytest

from jason.community import community
from jason.community.board_items import BoardItem, ItemCategory, Priority, Session
from jason.tasks import approvals as store
from jason.tasks import board_packet
from jason.tasks.board_items import set_fields, upsert
from jason.tasks.board_packet import Audience, Omission, Withheld, members_copy, packet, request_members_copy

DAY = date(2099, 3, 17)
# The made-up officers in tests/fixtures/spec.
SECRETARY, TREASURER, MANAGER = "Odo Fennimore", "Ilse Varnholt", "Pell Marchbanks"
REPAINT, SETTLE = "1. Repaint the carports", "2. Disclose the builder settlement"


def _item(item_id: str, **kw) -> BoardItem:
    base = dict(title="A matter", summary="What the records show.", ask="Decide it.", category=ItemCategory.FINANCE)
    base.update(kw)
    return BoardItem(item_id, **base)


@pytest.fixture
def board(tmp_path, monkeypatch):
    """Made-up items: an open one with public and closed records, an open one drawing on mediation figures and counsel's
    file, and an executive one whose title names a member."""
    (tmp_path / "board").mkdir()
    (tmp_path / "board" / "agenda-2099-03-17.md").write_text("# Agenda\n", encoding="utf-8")
    (tmp_path / "legal").mkdir()
    (tmp_path / "legal" / "memo.md").write_text("counsel's memo\n", encoding="utf-8")
    upsert(tmp_path, [
        _item("repaint", title="Repaint the carports", summary="The carports' paint is failing.", ask="Approve a painting bid.",
              priority=Priority.HIGH, special_notice="the bid's amount", due=date(2099, 4, 1),
              evidence=("jason paint --bids", "Drive: Example bid.pdf", "data/board/agenda-2099-03-17.md", "data/legal/memo.md")),
        _item("settle", title="Disclose the builder settlement", category=ItemCategory.LEGAL,
              summary="Figures shared for mediation only (Evidence Code 1119): $12,345 net.",
              ask="Direct counsel to prepare the disclosure to members.", notes="Call Pat Placeholder about it."),
        _item("plan", title="Payment plan for John Sample", ask="Accept John Sample's offer.", category=ItemCategory.COLLECTIONS),
    ], today=date(2099, 3, 1))
    for item_id in ("repaint", "settle", "plan"):
        set_fields(tmp_path, item_id, status="proposed", today=date(2099, 3, 1))

    def books(data_dir, c):
        return ["The bid is $9,000.", "Counsel's advice on the bid: a line only the directors read."]

    def counsel(data_dir, c):
        return ["Gross $55,555 under the settlement."]

    monkeypatch.setitem(board_packet.RESEARCHERS, "repaint", board_packet._placed("P1")(books))
    monkeypatch.setitem(board_packet.RESEARCHERS, "settle", board_packet._placed("P3", Withheld.PRIVILEGED)(counsel))
    monkeypatch.setitem(board_packet.OPTIONS, "repaint", (["Option alpha: take the low bid"], "Move that the board ZZMOTION."))
    return tmp_path


def test_the_members_copy_leaves_out_motions_options_privileged_and_executive_words(board):
    copy = members_copy(board, community(), DAY)
    text = "\n".join(copy.lines)
    assert text == "\n".join(packet(board, community(), DAY, audience="members"))
    for gone in ("ZZMOTION", "Option alpha", "**Options.**", "**Draft motion.**", "$12,345", "$55,555", "Pat Placeholder",
                 "John Sample", "a line only the directors read", "jason paint", "memo.md", "Confidential: for the directors"):
        assert gone not in text, gone
    # It keeps the open items' question, the records a member may see, the research at P1, and the notice and deadline.
    for kept in ("Repaint the carports", "**The question for the board.** Approve a painting bid.", "The bid is $9,000.",
                 "agenda-2099-03-17.md", "the bid's amount", "2099-04-01", "Direct counsel to prepare the disclosure to members."):
        assert kept in text, kept
    # The executive matter by its general line only.
    assert "Executive session (Civil Code 4935), noted generally:" in text
    # The header: the members' copy, approved by the roster's approver before it is posted.
    assert text.startswith("# Meeting packet for members: March 17, 2099")
    assert "The members' copy of the board packet. The secretary approves it before it is posted" in text


def test_what_is_left_out_is_listed_by_item_count_and_reason(board):
    copy = members_copy(board, community(), DAY)
    got = set(copy.withheld)
    assert {Omission(REPAINT, Withheld.OPTIONS, 1), Omission(REPAINT, Withheld.MOTION, 1),
            Omission(REPAINT, Withheld.PRIVILEGED, 1), Omission(REPAINT, Withheld.COMMAND, 1),
            Omission(REPAINT, Withheld.UNPLACED, 1), Omission(REPAINT, Withheld.RESTRICTED, 1)} <= got
    assert {Omission(SETTLE, Withheld.PRIVILEGED, 2), Omission(SETTLE, Withheld.NOTES, 1),
            Omission(SETTLE, Withheld.OPTIONS, 3), Omission(SETTLE, Withheld.MOTION, 1)} <= got
    assert Omission("Executive session", Withheld.EXECUTIVE, 1) in got
    text = "\n".join(copy.lines)
    listed = text.split("## What this copy leaves out")[1].split("## 1.")[0]
    settle = next(line for line in listed.splitlines() if line.startswith(f"- {SETTLE}: "))
    assert "privileged or mediation material (counsel's advice; Evidence Code 1119) (2)" in settle and "$12,345" not in settle
    assert "- Executive session: executive session matter beyond its general line (CIV 4935) (1)" in listed
    assert "_Left out of this copy: " in text.split("## 1.")[1]


def test_the_copy_goes_to_the_secretary_through_approvals_and_nothing_posts(board):
    copy = members_copy(board, community(), DAY)
    assert copy.approver == "the secretary" and copy.approver_names == (SECRETARY,)
    path = board / "board" / "packet-2099-03-17-members.md"
    path.write_text("\n".join(copy.lines), encoding="utf-8")
    letter = request_members_copy(board, community(), copy, path, by=MANAGER)
    assert letter["key"] == "board/packet-2099-03-17-members.md" and letter["stage"] == "requested"
    assert letter["approver"] == "the secretary" and letter["kind"] == "Meeting packet (members' copy)"
    assert letter["sentCommand"] == "" and letter["sentRef"] == "" and store.pending_count(board) == 1
    assert [e["by"] for e in letter["log"]] == [MANAGER, MANAGER, MANAGER]
    assert "ZZMOTION" not in "\n".join(letter["body"])
    with pytest.raises(ValueError, match="fixed"):
        request_members_copy(board, community(), copy, path, by=MANAGER)       # requested: its text is fixed
    with pytest.raises(ValueError):
        store.step(board, letter["key"], "approve", by=TREASURER)               # not the secretary
    assert store.step(board, letter["key"], "approve", by=SECRETARY)["stage"] == "approved"
    assert not (board / "mailroom").exists() and not (board / "notices").exists()


def test_no_approver_on_file_is_a_miss_never_the_board(board):
    class NoApprovers:
        def officers(self):
            return community().officers()

    copy = members_copy(board, NoApprovers(), DAY)
    assert copy.approver == "" and "No approver for the members' copy is on file" in copy.lines[2]
    with pytest.raises(ValueError, match="no approver"):
        request_members_copy(board, NoApprovers(), copy, board / "board" / "x.md", by=MANAGER)
    assert store.load(board) == {}


def test_the_command_writes_the_draft_and_requests_only_with_by(board):
    from jason.cli import _board_members_copy

    args = argparse.Namespace(doc=False, by="")
    assert _board_members_copy(args, board, DAY) == 0
    assert (board / "board" / "packet-2099-03-17-members.md").is_file() and store.load(board) == {}
    assert _board_members_copy(argparse.Namespace(doc=True, by=MANAGER), board, DAY) == 2
    assert _board_members_copy(argparse.Namespace(doc=False, by=MANAGER), board, DAY) == 0
    assert store.get(board, "board/packet-2099-03-17-members.md")["stage"] == "requested"


def test_the_directors_packet_is_unchanged(board):
    text = "\n".join(packet(board, community(), DAY, audience=Audience.DIRECTORS))
    assert "ZZMOTION" in text and "**Options.**" in text and "Confidential: for the directors and counsel" in text
    assert "John Sample" not in text
