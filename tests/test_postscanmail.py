"""PostScanMail: the read-only client, the mail record, and the sort into what to act on."""

from __future__ import annotations

import json
from datetime import date

import httpx
import pytest

from jason.postscanmail.client import PostScanMail, PostScanMailError
from jason.postscanmail.models import MailItem, MailKind, Urgency, classify, deadlines

ITEM = {
    "mail_id": "6182234",
    "sender_name": "LaBarre/Oksnee Insurance Agency, LLC",
    "address_id": 1234,
    "cover_image": "https://api.postscanmail.com/account-docs/v2/items/6182234/cover-image?signature=abc",
    "pdf_content": "https://api.postscanmail.com/account-docs/v2/items/6182234/pdf-content?signature=def",
    "pdf_metadata": {"received_at": "2026-09-29 16:53:09", "current_status": "Scan Complete", "assigned_user": "Pat Example",
                     "current_folder_name": "Inbox"},
    "ai_summary": None,
    "ai_summary_version": None,
}


def _client(pages: dict[int, list[dict]], seen: list[httpx.Request]) -> PostScanMail:
    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if "pdf-content" in request.url.path:
            return httpx.Response(200, content=b"%PDF-1.4 fake")
        page = int(request.url.params.get("page", "1"))
        body = {"status": 1, "data": {"current_page": page, "last_page": max(pages), "per_page": 20, "total": 3, "data": pages.get(page, [])}}
        return httpx.Response(200, json=body)

    return PostScanMail("key-123", http=httpx.Client(transport=httpx.MockTransport(handler)))


def test_the_client_pages_with_the_key_and_stops_at_known_mail() -> None:
    seen: list[httpx.Request] = []
    pages = {1: [dict(ITEM, mail_id="3"), dict(ITEM, mail_id="2")], 2: [dict(ITEM, mail_id="1")]}
    client = _client(pages, seen)
    assert [i["mail_id"] for i in client.iter_items()] == ["3", "2", "1"]
    assert all(r.headers["x-api-key"] == "key-123" and r.method == "GET" for r in seen)
    seen.clear()
    assert [i["mail_id"] for i in client.iter_items(stop_at={"3", "2"})] == ["3", "2"]
    assert len(seen) == 1


def test_a_download_sends_the_signature_not_the_key(tmp_path) -> None:
    seen: list[httpx.Request] = []
    client = _client({1: []}, seen)
    path = client.download(ITEM["pdf_content"], tmp_path / "a.pdf")
    assert path.read_bytes().startswith(b"%PDF") and "x-api-key" not in seen[0].headers


def test_a_refused_key_fails_fast() -> None:
    client = PostScanMail("bad", http=httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(401))))
    with pytest.raises(PostScanMailError):
        client.items_page(1)
    with pytest.raises(PostScanMailError):
        PostScanMail("")


def test_the_client_has_no_action_calls() -> None:
    names = {n for n in dir(PostScanMail) if not n.startswith("_")}
    assert not names & {"open", "shred", "discard", "rescan", "forward", "update_rule"}


def test_the_record_keeps_no_signed_links() -> None:
    item = MailItem.from_api(ITEM)
    assert item.scanned and item.received.date() == date(2026, 9, 29) and item.ai_summary == ()
    record = item.record()
    assert "signature" not in json.dumps(record) and record["folder"] == "Inbox"


def test_the_sort_puts_notices_first_and_lists_their_dates() -> None:
    cancel = classify("Philadelphia Insurance Companies", "NOTICE OF CANCELLATION\nThis policy will be cancelled effective 10/15/2026.",
                      received=date(2026, 9, 29))
    assert cancel.kind is MailKind.INSURANCE_CANCELLATION and cancel.urgency is Urgency.ACT
    assert [d.isoformat() for _l, d in cancel.deadlines] == ["2026-10-15"]
    assert classify("Absolute Law Group", "Dear Board").kind is MailKind.LEGAL
    assert classify("Someone", "SUMMONS\nSuperior Court of California, County of Sacramento").kind is MailKind.LEGAL
    renewal = classify("LaBarre/Oksnee Insurance Agency, LLC", "Your renewal declarations for the policy period")
    assert renewal.kind is MailKind.INSURANCE and renewal.urgency is Urgency.REVIEW
    assert classify("City of Sacramento Department of Utilities", "Amount due").kind is MailKind.UTILITY
    assert classify("First Citizens Bank", "Certificate of Deposit Statement").kind is MailKind.BANK
    assert classify("A stranger", "hello").kind is MailKind.OTHER


def test_deadlines_keep_only_dates_after_arrival() -> None:
    text = "Statement date 01/02/2026. Payment due by 10/20/2026. Hearing on November 3, 2026."
    assert [d.isoformat() for _l, d in deadlines(text, after=date(2026, 9, 29))] == ["2026-10-20", "2026-11-03"]


def test_boilerplate_deep_in_a_policy_packet_is_not_a_notice() -> None:
    packet = "PHILADELPHIA INSURANCE COMPANIES\nYour renewal declarations for the policy period\n" + ("x " * 3000) + \
        "Case No. and notice of cancellation clause"
    found = classify("", packet)
    assert found.kind is MailKind.INSURANCE and found.urgency is Urgency.REVIEW


def test_advertising_tax_bills_and_county_pin_letters() -> None:
    assert classify("Absolute Law Group", "als Is an Advertisement\nSuperior Court of nothing").kind is MailKind.MARKETING
    assert classify("", "DALE OSTERFELD\nSACRAMENTO COUNTY PROPERTY TAX BILL\nDUE BY NOVEMBER 1, 2025").kind is MailKind.TAX_BILL
    pin = classify("", "COUNTY OF SACRAMENTO\nDEPARTMENT OF FINANCE\nyou have requested online ownership verification\nYour Pin:")
    assert pin.kind is MailKind.GOVERNMENT and pin.urgency is Urgency.REVIEW


def test_reread_ocr_reads_tesseracts_scans_again_and_keeps_the_old_text(tmp_path, monkeypatch) -> None:
    from jason.tasks import mail

    for mail_id, source in (("1", "ocr: pymupdf-tesseract"), ("2", "text layer")):
        folder = tmp_path / "mail" / mail_id
        folder.mkdir(parents=True)
        (folder / "contents.pdf").write_bytes(b"%PDF-1.4")
        (folder / "text.txt").write_text("P0LICY 87O739", encoding="utf-8")
    rows = [{"mailId": "1", "textSource": "ocr: pymupdf-tesseract"}, {"mailId": "2", "textSource": "text layer"}]
    (tmp_path / "mail" / "items.json").write_text(json.dumps({"items": rows}), encoding="utf-8")
    monkeypatch.setattr(mail, "_text_of", lambda pdf: ("POLICY 8707390702", "ocr: ollama-vision"))
    monkeypatch.setattr(mail, "resort", lambda data_dir, community=None: 2)
    assert mail.reread_ocr(tmp_path) == {"candidates": 1, "reread": 1, "unchanged": 0, "failed": 0}
    assert (tmp_path / "mail" / "1" / "text.txt").read_text(encoding="utf-8") == "POLICY 8707390702"
    assert (tmp_path / "mail" / "1" / "text.pymupdf-tesseract.txt").read_text(encoding="utf-8") == "P0LICY 87O739"
    assert (tmp_path / "mail" / "2" / "text.txt").read_text(encoding="utf-8") == "P0LICY 87O739"
    assert mail.load_items(tmp_path)["1"]["textSource"] == "ocr: ollama-vision"


def test_a_letter_carrying_a_credential_is_withheld(tmp_path) -> None:
    from jason.tasks.mail import mail_text

    folder = tmp_path / "mail" / "7"
    folder.mkdir(parents=True)
    (folder / "text.txt").write_text("Your Pin:\nStep One: sign in\n9O9583", encoding="utf-8")
    (tmp_path / "mail" / "items.json").write_text(json.dumps({"items": [{"mailId": "7", "sender": "County"}]}), encoding="utf-8")
    body = mail_text(tmp_path, "7")["textBody"]
    assert "9O9583" not in body and body.startswith("[withheld")


def test_letter_facts_read_parcels_addresses_policies_and_escrows() -> None:
    from jason.postscanmail.models import letter_facts

    text = ("APN 201-1170-022-0016\nProperty: 3021 Enchanted Walk\nPolicy Number: 5010000092\n"
            "Escrow No.: FSSE-0100000033\nAccount Number ****4455")
    facts = letter_facts(text)
    assert facts.parcels == ("20111700220016",) and facts.addresses == ("3021 ENCHANTED WALK",)
    assert facts.policies == ("5010000092",) and facts.escrows == ("FSSE-0100000033",) and facts.accounts == ("4455",)
    # A policy named in running text, with no "No." or "Number", is read whole (not a fragment after a misread "No").
    assert letter_facts("issued for the AssocNational policy N030PK2940-01. The agent is").policies == ("N030PK2940-01",)


def test_shareable_letters_leave_out_credentials_and_confidential_kinds() -> None:
    from jason.tasks.mail import letter_page, shareable

    insurance = {"mailId": "1", "kind": MailKind.INSURANCE.value, "text": True}
    assert shareable(insurance)
    assert not shareable({**insurance, "credential": True}, include_confidential=True)
    legal = {"mailId": "2", "kind": MailKind.LEGAL.value, "text": True}
    assert not shareable(legal) and shareable(legal, include_confidential=True)
    page = letter_page({**insurance, "received": "2026-09-29 16:53:09", "from": "Philadelphia", "facts": {"policies": ["5010000092"]}}, "text")
    assert page.startswith("# 2026-09-29 Philadelphia (insurance policy, renewal, or invoice) [mail 1]") and "5010000092" in page


def test_policy_readings_place_a_policy_on_the_building_its_letters_name() -> None:
    from jason.tasks.mail import policy_readings

    def letter(policy: str, building: int, day: str) -> dict:
        return {"kind": MailKind.INSURANCE.value, "received": day, "deadlines": [],
                "facts": {"policies": [policy], "ourBuildings": [{"address": "x", "building": building}]}}

    rows = [letter("5010000092", 3, "2026-09-21"), letter("5010000092", 3, "2025-10-02"), letter("5010000095", 6, "2026-09-29"),
            letter("5010000095", 8, "2025-10-02"), letter("9999", 1, "2026-01-01")]
    readings = {r["policy"]: r for r in policy_readings(rows)}
    assert readings["5010000092"]["building"] == 3 and readings["5010000092"]["latestLetter"] == "2026-09-21"
    assert readings["5010000095"]["building"] is None and "9999" not in readings


def test_the_addressee_block_names_an_old_address_and_a_care_of_party() -> None:
    from jason.postscanmail.models import AddressKind, MailAddress, address_of, care_of

    addresses = (MailAddress(AddressKind.CURRENT, "box", ("901 H ST", "PMB 188")),
                 MailAddress(AddressKind.FORMER_MANAGER, "prior manager", ("BOLLINGER CANYON",)))
    bank = "FIRST CITIZENS BANK\nStatement\nMYSTIQUE COMMUNITY ASSOCIATION\n6101 BOLLINGER CANYON RD STE 200\nSAN RAMON CA 94583"
    assert address_of(bank, addresses)[0] is AddressKind.FORMER_MANAGER
    irs = "IRS\nMYSTIQUE COMMUNITY ASSOCIATION\n% VIERRAMOORE\n901 H'ST STE 120"
    kind, _label, block = address_of(irs, addresses)
    assert kind is AddressKind.CURRENT and care_of(block) == "VIERRAMOORE"
    assert address_of("no addressee here", addresses)[0] is AddressKind.UNREAD


def test_delinquency_notices_outrank_the_tax_bill_they_quote() -> None:
    notice = ("COUNTY OF SACRAMENTO\nNOTICE OF DELINQUENT SECURED TAXES AND NOTICE OF POTENTIAL JUDICIAL FORECLOSURE\n"
              "the referenced current year secured property tax bill is unpaid")
    found = classify("", notice)
    assert found.kind is MailKind.GOVERNMENT and found.urgency is Urgency.ACT
    assert classify("", "County of Sacramento\nSubject: NOTICE OF ERROR IN PAYMENT").urgency is Urgency.ACT


def test_a_printed_bill_number_names_the_stored_bill() -> None:
    from types import SimpleNamespace

    from jason.tasks.mail_links import _stored_bill

    bills = [SimpleNamespace(number="20250312211", year=2025), SimpleNamespace(number="20240409912", year=2024)]
    assert _stored_bill(bills, "24409912").year == 2024 and _stored_bill(bills, "24409999") is None


def test_the_current_address_without_its_box_number_is_incomplete() -> None:
    from jason.community import mystique
    from jason.postscanmail.models import AddressKind, classify_address

    addresses = mystique().mail_addresses()
    assert classify_address("901 H ST BLDG STE 120 UNIT PMB 188 SACRAMENTO CA 95814", addresses)[0] is AddressKind.CURRENT
    assert classify_address("901 HST STE 120 PMBi88 SACRAMENTO", addresses)[0] is AddressKind.CURRENT
    assert classify_address("901 H ST STE 120 SACRAMENTO CA 95814", addresses)[0] is AddressKind.INCOMPLETE
    assert classify_address("3000 MACON DR SACRAMENTO CA 95835", addresses)[0] is AddressKind.PROPERTY
