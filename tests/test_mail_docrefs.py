"""The mail group's document references (docs/console/doc-component.md): each letter a screen names carries a ``DocRef``
to its scan (``mail/<id>/contents.pdf``) or, unscanned, its envelope (``mail/<id>/cover.jpg``); a pending PayHOA
request carries its submission. Mail triage, the Inbox's letters and requests, and insurance notices and claims.
Everything here is made up."""

from __future__ import annotations

import json
import re
import sqlite3
import sys
import types
from types import SimpleNamespace

import pytest

from jason.approvals.evidence import resolve
from jason.tasks.mail import scan_ref

ABSOLUTE = re.compile(r"^(?:[A-Za-z]:[\\/]|/)")
SPEC_KEYS = {"address", "document", "name", "kind", "level", "source", "readAt", "size", "thumb", "original",
             "refreshable", "stale"}
RECENT = "2099-01-20"


def _row(mail_id: str, *, scanned: bool, kind: str = "legal", urgency: str = "act", **extra) -> dict:
    return {"mailId": mail_id, "received": f"{RECENT}T10:00:00", "sender": "Example Sender", "from": "Example Insurer",
            "kind": kind, "urgency": urgency, "scanned": scanned, "deadlines": [], "evidence": [], **extra}


@pytest.fixture
def data(tmp_path, monkeypatch):
    """A made-up data folder: a scanned letter, an unscanned envelope, a scanned insurance notice and a claim letter,
    the items list, and a PayHOA catalog with one pending request and its kept read."""
    monkeypatch.setenv("JASON_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("PAYHOA_CATALOG", str(tmp_path / "payhoa.db"))
    mail = tmp_path / "mail"
    for mail_id in ("100", "102", "103"):
        (mail / mail_id).mkdir(parents=True)
        (mail / mail_id / "contents.pdf").write_bytes(b"%PDF-1.4 letter")
    (mail / "101").mkdir()
    (mail / "101" / "cover.jpg").write_bytes(b"\xff\xd8\xff example envelope")
    (mail / "102" / "text.txt").write_text("Policy EX1234567: notice of conditional renewal.", encoding="utf-8")
    (mail / "103" / "text.txt").write_text("Policy EX1234567. Notice of claim. Claim number CL-12345. Date of loss 1/2/2099.",
                                           encoding="utf-8")
    items = [_row("100", scanned=True), _row("101", scanned=False, kind="ad", urgency="file"),
             _row("102", scanned=True, kind="insurance", urgency="review", facts={"policies": ["EX1234567"]}),
             _row("103", scanned=True, kind="insurance", urgency="review", facts={"policies": ["EX1234567"]})]
    (mail / "items.json").write_text(json.dumps({"syncedAt": RECENT, "items": items}), encoding="utf-8")
    with sqlite3.connect(tmp_path / "payhoa.db") as conn:
        conn.execute("CREATE TABLE units (id INTEGER, label TEXT, balance INTEGER, past_due_balance INTEGER)")
        conn.execute("CREATE TABLE people (raw_json TEXT)")
        conn.execute("CREATE TABLE requests (id INTEGER, unit_id INTEGER, form_name TEXT, status TEXT, created_at TEXT)")
        conn.execute("CREATE TABLE violations (unit_id INTEGER, title TEXT, status TEXT, reported_at TEXT)")
        conn.execute("INSERT INTO units VALUES (1, '123 Main St #1', 0, 0)")
        conn.execute("INSERT INTO requests VALUES (42, 1, 'Example Form', 'Pending', '2099-01-10')")
        conn.execute("INSERT INTO requests VALUES (43, 1, 'Example Form', 'Approved', '2099-01-11')")
    conn.close()
    kept = tmp_path / "payhoa-files" / "requests" / "42"
    kept.mkdir(parents=True)
    (kept / "submission.json").write_text(json.dumps({"readAt": "2099-01-12T00:00:00+00:00", "submission": {}}),
                                          encoding="utf-8")
    return tmp_path


def _no_absolute(value) -> None:
    if isinstance(value, str):
        assert not ABSOLUTE.match(value), value
    elif isinstance(value, dict):
        for v in value.values():
            _no_absolute(v)
    elif isinstance(value, list):
        for v in value:
            _no_absolute(v)


def _resolves(ref: dict, data) -> None:
    assert set(ref) <= SPEC_KEYS
    assert resolve(ref["address"], data_dir=data)["found"], ref["address"]
    _no_absolute(ref)


# --- the helper ---------------------------------------------------------------------------------------------------------

def test_a_scanned_letter_is_its_pdf_at_p2(data):
    ref = scan_ref(data, _row("100", scanned=True))
    assert (ref["address"], ref["kind"], ref["level"], ref["source"], ref["document"]) == (
        "file:mail/100/contents.pdf", "pdf", "P2", "Scan", "pdf")
    assert ref["name"] == f"Letter from Example Insurer, {RECENT}" and ref["thumb"] is True
    _resolves(ref, data)


def test_an_unscanned_letter_is_its_envelope(data):
    ref = scan_ref(data, _row("101", scanned=False))
    assert (ref["address"], ref["kind"], ref["level"]) == ("file:mail/101/cover.jpg", "image", "P2")
    assert ref["name"].startswith("Envelope from ")
    _resolves(ref, data)


def test_a_letter_with_nothing_on_disk_is_still_a_reference(data):
    ref = scan_ref(data, _row("999", scanned=True))
    assert ref["address"] == "file:mail/999/contents.pdf" and "document" not in ref and ref["level"] == "P2"


def _flag(data, mail_id: str, **flags) -> None:
    items_file = data / "mail" / "items.json"
    body = json.loads(items_file.read_text(encoding="utf-8"))
    for row in body["items"]:
        if row["mailId"] == mail_id:
            row.update(flags)
    items_file.write_text(json.dumps(body), encoding="utf-8")


def test_a_letter_holding_a_credential_has_no_reference_and_says_it_is_held(data):
    from jason.tasks.mail import HELD, scan_fields

    _flag(data, "100", credential=True)
    assert scan_ref(data, _row("100", scanned=True)) is None
    assert scan_fields(data, _row("100", scanned=True)) == {"scan": None, "held": HELD}
    assert HELD == "Held: this letter holds a credential; it opens in no screen."
    assert scan_fields(data, _row("102", scanned=True))["scan"]["level"] == "P2"


def test_another_associations_letter_is_p3(data):
    _flag(data, "100", source={"misdirected": True})
    assert scan_ref(data, _row("100", scanned=True))["level"] == "P3"


@pytest.mark.parametrize("bad", ["", "../etc", "a/b", None])
def test_a_row_without_a_usable_mail_id_has_no_reference(data, bad):
    assert scan_ref(data, {"mailId": bad, "scanned": True}) is None


# --- the loaders ----------------------------------------------------------------------------------------------------------

@pytest.fixture
def county(data):
    """A fake ``jason.mcp.county`` whose ``mail_brief`` reads the made-up folder."""
    from jason.tasks.mail import mail_brief

    saved = {k: sys.modules.get(k) for k in ("jason.mcp", "jason.mcp.county")}
    fake = types.ModuleType("jason.mcp.county")
    fake.mail_brief = lambda days=30, kind="", urgency="": mail_brief(data, days=days, kind=kind, urgency=urgency,
                                                                     today=__import__("datetime").date(2099, 1, 25))
    fake._data_dir = lambda _: data
    pkg = types.ModuleType("jason.mcp")
    pkg.__path__ = []
    pkg.county = fake
    sys.modules["jason.mcp"] = pkg
    sys.modules["jason.mcp.county"] = fake
    try:
        yield fake
    finally:
        for k, v in saved.items():
            if v is None:
                sys.modules.pop(k, None)
            else:
                sys.modules[k] = v


def test_mail_triage_gives_each_letter_its_scan_or_envelope(county, data):
    from jason.web.extra.mail_triage import mail_triage

    out = mail_triage({})
    act = {r["mailId"]: r["scan"] for r in out["act"]}
    assert act == {"100": scan_ref(data, _row("100", scanned=True))}
    unscanned = {r["mailId"]: r["scan"]["address"] for r in out["unscanned"]}
    assert unscanned == {"101": "file:mail/101/cover.jpg"}
    for lane in ("act", "review", "unscanned"):
        for row in out[lane]:
            _resolves(row["scan"], data)
    _no_absolute(out)


def test_mail_triage_holds_a_credential_letter(county, data):
    from jason.tasks.mail import HELD
    from jason.web.extra.mail_triage import mail_triage

    _flag(data, "100", credential=True)
    [row] = mail_triage({})["act"]
    assert row["mailId"] == "100" and row["scan"] is None and row["held"] == HELD


def test_the_inbox_letters_carry_their_scans_and_requests_their_submissions(data, monkeypatch):
    from datetime import date

    from jason.tasks import party

    monkeypatch.setattr(party, "_threads", lambda *_: {"rows": []})
    out = party.open_items(data, SimpleNamespace(senders=lambda: (), insurance=lambda: SimpleNamespace(policies=())),
                           days=30, today=date(2099, 1, 25))
    letters = {r["mailId"]: r["scan"] for r in out["lettersToAct"]}
    assert set(letters) == {"100"} and letters["100"]["address"] == "file:mail/100/contents.pdf"
    _resolves(letters["100"], data)
    [pending] = out["requestsPending"]
    assert pending["id"] == 42 and pending["form"] == "Example Form"          # the old fields stay
    doc = pending["doc"]
    assert (doc["address"], doc["kind"], doc["level"], doc["source"]) == ("payhoa:submission:42", "submission", "P2", "PayHOA")
    _resolves(doc, data)
    _no_absolute(out)


def test_insurance_notices_and_claims_carry_their_scans(data):
    from datetime import date

    from jason.community.base import Policy
    from jason.community.symbols import PolicyKind
    from jason.tasks.insurance import review

    community = SimpleNamespace(senders=lambda: (),
                                insurance=lambda: SimpleNamespace(policies=(Policy(kind=PolicyKind.MASTER, number="EX1234567"),)))
    out = review(data, community, today=date(2099, 1, 25))
    [policy] = out["policies"]
    notices = {n["mailId"]: n["scan"]["address"] for n in policy["notices"]}
    assert notices == {"102": "file:mail/102/contents.pdf", "103": "file:mail/103/contents.pdf"}
    assert all(letter["scan"]["level"] == "P2" for letter in policy["letters"])
    [claim] = out["claims"]
    assert claim["mailId"] == "103" and claim["claimNumber"] == "CL-12345"
    assert claim["scan"]["address"] == "file:mail/103/contents.pdf"
    for ref in [*(n["scan"] for n in policy["notices"]), claim["scan"]]:
        _resolves(ref, data)
    _no_absolute(out)
