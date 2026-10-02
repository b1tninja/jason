"""Gmail as a second source: PostScanMail's notices against the synced mail, and vendor contacts against PayHOA."""

from __future__ import annotations

import json
from types import SimpleNamespace

from jason.community.sources import Sender, SourceKind
from jason.tasks.contacts import directory
from jason.tasks.gmail import correspondence, notice_check, parse_notice


def _meta(subject: str, *files: tuple[str, str], at_ms: int = 1_790_000_000_000) -> dict:
    return {"id": subject[:5] + str(len(files)), "threadId": "t", "internalDate": str(at_ms), "labels": [],
            "headers": {"Subject": subject}, "attachments": [{"name": n, "type": t, "size": 1} for n, t in files]}


def test_a_scan_notice_names_its_mail_id_and_envelope_image() -> None:
    notice = parse_notice(_meta("PostScan Mail – Scan Complete", ("6abb.jpeg", "image/jpeg"),
                                ("LaBarreOksnee-Insurance-Agency,-LLC_Envelope-124638.pdf", "application/pdf")))
    assert notice["event"] == "Scan Complete" and notice["mailId"] == "124638" and notice["image"] == "6abb.jpeg"
    assert parse_notice(_meta("PostScan Mail – Scan Complete", ("Envelope-124326.pdf", "application/pdf")))["mailId"] == "124326"


def test_the_notice_check_finds_missing_and_unscanned_items(tmp_path) -> None:
    notices = [
        {"messageId": "a", "at": "2026-09-15T23:06:16+00:00", "event": "New Mail Delivered", "image": "x.jpeg", "mailId": "", "scan": ""},
        {"messageId": "b", "at": "2026-09-16T17:43:04+00:00", "event": "Scan Complete", "image": "x.jpeg", "mailId": "124324", "scan": "Envelope-124324.pdf"},
        {"messageId": "c", "at": "2026-09-20T10:00:00+00:00", "event": "New Mail Delivered", "image": "y.jpeg", "mailId": "", "scan": ""},
        {"messageId": "d", "at": "2026-09-21T10:00:00+00:00", "event": "Scan Complete", "image": "z.jpeg", "mailId": "999", "scan": "Envelope-999.pdf"},
    ]
    (tmp_path / "gmail").mkdir()
    (tmp_path / "gmail" / "postscanmail.json").write_text(json.dumps({"notices": notices}), encoding="utf-8")
    (tmp_path / "mail").mkdir()
    (tmp_path / "mail" / "items.json").write_text(json.dumps({"items": [{"mailId": "124324", "received": "2026-09-15"}]}), encoding="utf-8")
    check = notice_check(tmp_path)
    assert [m["mailId"] for m in check["notInApiSync"]] == ["999"]
    assert [d["image"] for d in check["deliveredNotScanned"]] == ["y.jpeg"]
    assert check["medianDaysToScan"] == 0.8


def _sender() -> Sender:
    return Sender("LaBarre/Oksnee Insurance Agency", SourceKind.INSURER, ("LABARRE",), payhoa_vendor="LaBarre/Oksnee Insurance Agency, LLC",
                  domains=("hoa-insurance.com",))


def test_the_sender_is_resolved_when_the_email_is_read(tmp_path) -> None:
    (tmp_path / "gmail").mkdir()
    messages = [{"messageId": "1", "threadId": "t", "at": "2026-09-10T00:00:00+00:00", "direction": "in", "domains": ["hoa-insurance.com"],
                 "subject": "Proposal 26-27", "attachments": []},
                {"messageId": "2", "threadId": "t", "at": "2026-09-11T00:00:00+00:00", "direction": "in", "domains": ["unknown.com"],
                 "subject": "hello", "attachments": []}]
    (tmp_path / "gmail" / "correspondence.json").write_text(json.dumps({"messages": messages}), encoding="utf-8")
    rows = correspondence(tmp_path, community=SimpleNamespace(senders=lambda: (_sender(),)))
    assert [(r["messageId"], r["sender"]) for r in rows] == [("1", "LaBarre/Oksnee Insurance Agency")]


def test_vendor_contacts_propose_what_payhoa_lacks(tmp_path) -> None:
    (tmp_path / "payhoa").mkdir()
    info = {"rows": [{"vendorName": "LaBarre/Oksnee Insurance Agency, LLC", "email": "", "contactName": "", "phone": "949-555-0171"},
                     {"vendorName": "Pro Active Pest Control", "email": "office@proactivepest.com", "contactName": "Old Name", "phone": ""},
                     {"vendorName": "Sac Val Plumbing", "email": "", "contactName": "", "phone": ""}]}
    (tmp_path / "payhoa" / "vendor-info.json").write_text(json.dumps(info), encoding="utf-8")
    contacts = [
        {"address": "orlaf@hoa-insurance.com", "domain": "hoa-insurance.com", "names": ["Orla Fennimore"], "first": "2026-09-10", "last": "2026-09-29",
         "wroteUs": 5, "weWrote": 4},
        {"address": "accounting@hoa-insurance.com", "domain": "hoa-insurance.com", "names": ["Accounting"], "first": "2025-01-01", "last": "2026-09-30",
         "wroteUs": 2, "weWrote": 0},
        {"address": "tech@proactivepest.com", "domain": "proactivepest.com", "names": ["New Tech"], "first": "2026-01-01", "last": "2026-08-01",
         "wroteUs": 3, "weWrote": 1},
        {"address": "bob@sacvalplumbing.com", "domain": "sacvalplumbing.com", "names": ["Bob"], "first": "2026-01-01", "last": "2026-02-01",
         "wroteUs": 1, "weWrote": 1},
    ]
    (tmp_path / "gmail").mkdir()
    (tmp_path / "gmail" / "correspondence.json").write_text(json.dumps({"messages": [], "contacts": contacts}), encoding="utf-8")
    result = directory(tmp_path, SimpleNamespace(senders=lambda: (_sender(),)))
    rows = {v["vendor"]: v for v in result["vendors"]}
    labarre = rows["LaBarre/Oksnee Insurance Agency, LLC"]["proposals"]
    assert any(p.startswith("PayHOA has no email; orlaf@hoa-insurance.com") for p in labarre)
    assert any(p.startswith("PayHOA has no contact name; Orla Fennimore") for p in labarre)
    pest = rows["Pro Active Pest Control"]["proposals"]
    assert any("office@proactivepest.com does not appear" in p for p in pest)
    assert any("Old Name is on no message" in p for p in pest)
    [unclaimed] = result["unclaimedDomains"]
    assert unclaimed["domain"] == "sacvalplumbing.com" and unclaimed["vendorByName"] == ["Sac Val Plumbing"]
