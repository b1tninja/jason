"""Google Groups in the association's Gmail: the writer behind a group's rewritten From, the groups a message came
through, and what a group's purpose changes."""

from __future__ import annotations

import json
from pathlib import Path

from jason.community.groups import GoogleGroup, GroupPurpose, group_of, groups_for
from jason.tasks.gmail import _groups, _senders, fetch_documents, group_lines

OWN = {"mystiquecommunity.com"}
AP = GoogleGroup("ap@mystiquecommunity.com", "Accounts Payable", GroupPurpose.ACCOUNTS_PAYABLE)
BOARD = GoogleGroup("board@mystiquecommunity.com", "Board", GroupPurpose.BOARD, confidential=True)


def test_a_rewritten_from_is_the_original_writer() -> None:
    head = {"From": "\"'Esme Kettleby' via Accounts Payable\" <AP@mystiquecommunity.com>",
            "X-Original-From": "Esme Kettleby <EsmeK@hoa-insurance.com>", "X-Original-Sender": "esmek@hoa-insurance.com"}
    assert _senders(head, OWN) == ([("Esme Kettleby", "esmek@hoa-insurance.com")], "ap@mystiquecommunity.com")
    only_sender = {"From": "Accounts Payable <ap@mystiquecommunity.com>", "X-Original-Sender": "billing@smud.org"}
    assert _senders(only_sender, OWN) == ([("", "billing@smud.org")], "ap@mystiquecommunity.com")
    # The association writing through its own group stays the association's; a vendor writing directly is the vendor's.
    assert _senders({"From": "Board <board@mystiquecommunity.com>", "X-Original-Sender": "director@mystiquecommunity.com"}, OWN) == (
        [("Board", "board@mystiquecommunity.com")], "")
    assert _senders({"From": "SMUD <billing@smud.org>"}, OWN) == ([("SMUD", "billing@smud.org")], "")


def test_the_groups_a_message_came_through() -> None:
    assert _groups({"List-Id": "Accounts Payable <ap.mystiquecommunity.com>"}, OWN, "") == ["ap@mystiquecommunity.com"]
    assert _groups({"List-Id": "<board.mystiquecommunity.com>"}, OWN, "ap@mystiquecommunity.com") == [
        "ap@mystiquecommunity.com", "board@mystiquecommunity.com"]
    # Google writes "List-ID", and a group that did not rewrite the sender still names itself in X-BeenThere.
    assert _groups({"List-ID": "<AP.mystiquecommunity.com>"}, OWN, "") == ["ap@mystiquecommunity.com"]
    assert _groups({"X-BeenThere": 'board@mystiquecommunity.com; h="x"'}, OWN, "") == ["board@mystiquecommunity.com"]
    # Another domain's mailing list is not the association's group.
    assert _groups({"List-Id": "Newsletter <news.example.com>"}, OWN, "") == []


def test_group_lookups_and_the_report() -> None:
    groups = (AP, BOARD)
    assert group_of("AP@mystiquecommunity.com", groups) is AP and group_of("x@mystiquecommunity.com", groups) is None
    assert groups_for(GroupPurpose.ACCOUNTS_PAYABLE, groups) == {"ap@mystiquecommunity.com"}
    lines = group_lines([{"groups": ["ap@mystiquecommunity.com"], "via": "ap@mystiquecommunity.com"},
                         {"groups": ["ap@mystiquecommunity.com"], "via": ""},
                         {"groups": ["info@mystiquecommunity.com"], "via": ""}], groups)
    assert "  ap@mystiquecommunity.com: 2 messages, 1 rewritten; Accounts Payable (accounts payable: invoices, bills, and statements to pay)" in lines
    assert "  info@mystiquecommunity.com: 1 messages, 0 rewritten; not in mystique/groups.py" in lines
    assert group_lines([{"groups": []}], groups) == []


class Community:
    def senders(self):
        return ()

    def google_groups(self):
        return (AP, BOARD)


class Gmail:
    def __init__(self) -> None:
        self.read: list[str] = []

    def get_metadata(self, message_id: str) -> dict:
        self.read.append(message_id)
        return {"attachments": [{"name": "Invoice.pdf", "attachmentId": "a1", "type": "application/pdf"}]}

    def get_attachment(self, message_id: str, attachment_id: str) -> bytes:
        return b"%PDF-1.4 " + message_id.encode()


def test_mail_to_accounts_payable_is_saved_even_from_inside(tmp_path: Path) -> None:
    messages = [
        # Forwarded into accounts payable by a board member: no business domain, still a bill.
        {"messageId": "m1", "at": "2026-09-30", "direction": "in", "domains": [], "groups": ["ap@mystiquecommunity.com"],
         "subject": "Fwd: statement", "attachments": ["Invoice.pdf"]},
        # A board member's PDF to the board group is theirs, not a vendor's document.
        {"messageId": "m2", "at": "2026-09-30", "direction": "in", "domains": [], "groups": ["board@mystiquecommunity.com"],
         "subject": "notes", "attachments": ["Invoice.pdf"]},
        # What the association sends out through accounts payable is not a bill it received.
        {"messageId": "m3", "at": "2026-09-30", "direction": "out", "domains": [], "groups": ["ap@mystiquecommunity.com"],
         "subject": "paid", "attachments": ["Invoice.pdf"]},
    ]
    (tmp_path / "gmail").mkdir()
    (tmp_path / "gmail" / "correspondence.json").write_text(json.dumps({"messages": messages}), encoding="utf-8")
    gmail = Gmail()
    fetch_documents(gmail, tmp_path, Community())
    assert gmail.read == ["m1"]
    index = json.loads((tmp_path / "gmail" / "files.json").read_text(encoding="utf-8"))
    assert [(f["messageId"], f["groups"]) for f in index["files"]] == [("m1", ["ap@mystiquecommunity.com"])]
