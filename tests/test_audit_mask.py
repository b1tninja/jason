"""Contact details are masked when an append-only log is written, not only on the way out: the approvals audit log
(``audit.mask``), the private view's stated reason (``access/private.jsonl``, ``access/served.jsonl``), and a sign-in's
free-text ``why`` (``web/sign-ins.jsonl``). Ids, dates, cents, and paths survive. Lesson ``audit-log-masks-email-only``.
Every value here is made up."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from jason.approvals import audit

PHONES = ["916-555-0123", "(916) 555-0123", "916.555.0123", "+1 916 555 0123", "1-916-555-0123"]
ADDRESSES = ["123 Main St", "123 Main Street", "4567 N Elm Ave.", "12 Old Mill Rd, Apt 4", "88 Oak Ct #12",
             "900 21st St", "123 Main St, Springfield, CA 95814", "123 MAIN ST UNIT 5", "PO Box 123",
             "P.O. Box 4567, Springfield, CA 95814-1234"]
SURVIVE = ["apr-20261004-ab12", "submission:12345", "unit:42", "member:9876543", "2026-10-04",
           "2026-10-04T12:00:00+00:00", "6120", "$61.20", "data/approvals/audit.jsonl", "access/served.jsonl",
           r"D:\code\jason\data\mail\2026\scan-0001.pdf", "file:mail/2026/10/0001.pdf", "payhoa:submission:12345",
           "Civil Code 4360", "Building 2", "applied 3 of 4 writes in the same way", "row 12 of 40",
           "3f2a9c0d1e4b5a6978c0d1e2f3a4b5c6", "12345678901", "owner_responses.RULES: mailing-address",
           "jason approvals apply apr-1 --by A Manager --yes", "2 items held for the board"]


@pytest.mark.parametrize("phone", PHONES)
def test_a_phone_number_is_masked(phone):
    assert audit.mask(f"call {phone} after five") == "call [phone] after five"


@pytest.mark.parametrize("address", ADDRESSES)
def test_a_street_or_mailing_address_is_masked(address):
    out = audit.mask(f"mail to {address}; then file it")
    assert out == "mail to [address]; then file it", out


@pytest.mark.parametrize("text", SURVIVE)
def test_ids_dates_cents_and_paths_survive(text):
    assert audit.mask(text) == text


def test_numbers_and_structure_survive():
    value = {"amount": 6120, "items": ["unit:42", "apr-1"], "ok": True, "detail": "owner@example.com at 123 Main St"}
    assert audit.mask(value) == {"amount": 6120, "items": ["unit:42", "apr-1"], "ok": True,
                                 "detail": "[email] at [address]"}


def test_addresses_false_keeps_the_address():
    assert audit.mask("123 Main St, 916-555-0123", addresses=False) == "123 Main St, [phone]"


def test_the_line_is_masked_before_it_is_written_and_the_chain_holds(tmp_path):
    audit.append(tmp_path, "item.failed", approval="apr-1", target="unit:42", value="123 Main St, Springfield, CA 95814",
                 detail="bounced: owner@example.com, 916-555-0123, PO Box 123", result={"applied": 0, "cents": 6120})
    raw = audit.path(tmp_path).read_text(encoding="utf-8")
    for leaked in ("owner@example.com", "555-0123", "Main St", "Box 123"):
        assert leaked not in raw
    line = json.loads(raw.splitlines()[-1])
    assert line["value"] == "[address]" and line["detail"] == "bounced: [email], [phone], [address]"
    assert line["target"] == "unit:42" and line["approval"] == "apr-1" and line["result"]["cents"] == 6120
    assert audit.verify(tmp_path)[0]


def test_the_console_still_shows_an_address_but_never_a_phone():
    from jason.web.approvals import mask

    assert mask({"value": "123 Main St", "why": "call 916-555-0123"}) == {"value": "123 Main St", "why": "call [phone]"}


def test_a_private_view_reason_is_masked_before_it_is_logged():
    from jason.web.access import clean_reason

    assert clean_reason("prep for 123 Main St, owner@example.com, 916-555-0123") == "prep for [address], [email], [phone]"
    assert clean_reason("executive session prep") == "executive session prep"


def test_a_sign_in_refusal_is_masked_before_it_is_logged(tmp_path):
    from jason.web.signin import _log

    log = tmp_path / "sign-ins.jsonl"
    _log(SimpleNamespace(log=log), "refused", why="stranger@example.com is not on the roster")
    _log(SimpleNamespace(log=log), "signed in", name="A Manager", email="manager@example.com", sub="123")
    rows = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
    assert rows[0]["why"] == "[email] is not on the roster"
    assert rows[1]["email"] == "manager@example.com"            # the signed-in account's own id, not free text
