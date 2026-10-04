"""Where a document comes from: the named sender, the kind of source, other associations, and the counterparty report."""

from __future__ import annotations

import json

from jason.community import mystique
from jason.community.sources import Level, Sender, SourceKind, other_associations, resolve
from jason.postscanmail.models import MailKind, Urgency, classify
from jason.tasks.mail import shareable, sort
from jason.tasks.mail_links import _notice_amount, lien_notices
from jason.tasks.sources import report_lines, sources_report

SENDERS = (
    Sender("Franchise Tax Board", SourceKind.GOVERNMENT, ("FRANCHISE TAX BOARD",), Level.STATE),
    Sender("JPMorgan Chase", SourceKind.BANK, ("JPMORGAN", "CHASE BANK")),
    Sender("JB Bostick Company", SourceKind.VENDOR, ("BOSTICK",), payhoa_vendor="JB BOSTICK COMPANY"),
)


def test_a_named_sender_outranks_the_generic_words() -> None:
    named, kind, level, word = resolve("", "STATE OF CALIFORNIA\nFRANCHISE TAX BOARD\nPO Box 942857", SENDERS)
    assert named is SENDERS[0] and kind is SourceKind.GOVERNMENT and level is Level.STATE and word == "FRANCHISE TAX BOARD"


def test_an_unnamed_sender_takes_its_kind_from_the_generic_words() -> None:
    named, kind, level, _ = resolve("", "COUNTY OF YOLO\nAssessor's Office", SENDERS)
    assert named is None and kind is SourceKind.GOVERNMENT and level is Level.COUNTY
    assert resolve("", "Dear Owner, automatic payments make life easier.", SENDERS)[1] is SourceKind.UNKNOWN


def test_the_association_is_the_addressee_not_the_sender() -> None:
    # "MYSTIQUE COMMUNITY ASSOCIATION" on the address line is not a letterhead word, by the profile's name pattern.
    own = mystique().name_pattern()
    assert resolve("", "MYSTIQUE COMMUNITY BANK ASSOCIATION\n901 H ST", SENDERS, own_name=own)[1] is SourceKind.UNKNOWN
    # A profile that names no pattern takes no line for its own: the bank word there counts.
    assert resolve("", "MYSTIQUE COMMUNITY BANK ASSOCIATION\n901 H ST", SENDERS)[1] is SourceKind.BANK


def test_a_payer_block_below_the_addressee_names_the_sender() -> None:
    text = "P.O. BOX 44921\nTax Year 2026 Form 1099-INT\n" + "x " * 250 + "\nMYSTIQUE COMMUNITY ASSOCIATION\nJPMORGAN CHASE BANK, N.A."
    assert resolve("", text, SENDERS)[0] is SENDERS[1]
    assert resolve("", text, SENDERS, wide=300)[0] is None


def test_other_associations_keep_the_name_and_drop_our_own() -> None:
    text = ("Bk i University District Detached Homes Association\nc/o Mystique Community Association\n"
            "Longmeadow Village 2 Homeowners Association\nthe Homeowners Association\nlystique Community Association")
    assert other_associations(text, own_name=mystique().name_pattern()) == (
        "University District Detached Homes Association", "Longmeadow Village 2 Homeowners Association")


def test_a_preliminary_notice_is_its_own_kind_and_a_claim_is_for_now() -> None:
    notice = classify("", "CALIFORNIA PRELIMINARY NOTICE for PRIVATE WORKS\n***THIS IS NOT A LIEN***")
    assert notice.kind is MailKind.LIEN_NOTICE and notice.urgency is Urgency.REVIEW
    claim = classify("", "RECORDING REQUESTED BY\nCLAIM OF MECHANICS LIEN\n")
    assert claim.kind is MailKind.LIEN_NOTICE and claim.urgency is Urgency.ACT


def test_ocr_split_digits_still_read_as_the_notice_amount() -> None:
    assert _notice_amount("In the Amount of:\nAddress: 3000 MACON DRIVE\n§ 1 9,377.00\n") == 1937700


def _row(mail_id: str) -> dict:
    return {"mailId": mail_id, "received": "2024-05-03T10:00:00", "sender": "", "aiSummary": [], "text": True}


def test_another_associations_statement_is_misdirected_and_stays_out_of_the_catalog() -> None:
    text = "Savannah Community Association\nSTATEMENT\nPO Box 803555\nCurrent Account Balance $86.00\n"
    row = sort(_row("1"), text, mystique())
    # The lockbox is a prior manager's: the statement is theirs to send, and another association's to keep.
    assert row["source"]["misdirected"] and row["source"]["name"] == "RealManage"
    assert not shareable(row)
    unmanaged = sort(_row("3"), "Savannah Community Association\nSTATEMENT\nCurrent Account Balance $86.00\n", mystique())
    assert unmanaged["source"]["kind"] == SourceKind.OTHER_ASSOCIATION.value
    ours = sort(_row("2"), "City of Sacramento\nMILL AT BROADWAY COMMUNITY Association\nMystique Community Association\n", mystique())
    assert ours["source"]["otherAssociations"] and not ours["source"]["misdirected"]


def test_a_preliminary_notice_joins_the_claimants_payments(tmp_path) -> None:
    text = ("CALIFORNIA PRELIMINARY NOTICE for PRIVATE WORKS\nTHIS IS NOT A LIEN\nOWNER: MYSTIQUE COMMUNITYASSOC\n"
            "THE UNDERSIGNED CLAIMANT:\nCompany Name:\nJB BOSTICK COMPANY\nIn the Amount of:\n§ 1 9,377.00\n")
    row = sort(_row("107194"), text, mystique())
    assert row["kind"] == MailKind.LIEN_NOTICE.value and row["source"]["name"] == "JB Bostick Company"
    mail = tmp_path / "mail"
    (mail / "107194").mkdir(parents=True)
    (mail / "107194" / "text.txt").write_text(text, encoding="utf-8")
    (mail / "items.json").write_text(json.dumps({"items": [row]}), encoding="utf-8")
    (tmp_path / "payhoa").mkdir()
    txs = [{"id": 1, "vendorId": 7, "amount": 1000000, "originalAmount": 1000000, "transactionDate": "2024-04-20"},
           {"id": 2, "vendorId": 7, "amount": 937700, "originalAmount": 937700, "transactionDate": "2024-05-28"},
           {"id": 3, "vendorId": 7, "amount": 500000, "originalAmount": 500000, "transactionDate": "2022-01-01"}]
    (tmp_path / "payhoa" / "transactions.json").write_text(json.dumps({"transactions": txs, "vendors": {"7": "JB BOSTICK COMPANY"}}),
                                                           encoding="utf-8")
    [found] = lien_notices(tmp_path, mystique())
    assert found["noticeCents"] == 1937700 and found["paidCents"] == 1937700 and found["finding"] == "paid in full"


def test_the_report_counts_payments_not_money_coming_in(tmp_path) -> None:
    (tmp_path / "mail").mkdir()
    (tmp_path / "mail" / "items.json").write_text(json.dumps({"items": []}), encoding="utf-8")
    (tmp_path / "payhoa").mkdir()
    txs = [{"id": 1, "vendorId": 0, "amount": 8930991, "originalAmount": 8930991, "transactionDate": "2026-03-01",
            "description": "FEDWIRE CREDIT VIA: FIRST-CITIZENS BANK"},
           {"id": 2, "vendorId": 9, "amount": 16500, "originalAmount": 16500, "transactionDate": "2026-04-01", "description": ""}]
    snap = {"transactions": txs, "vendors": {"9": "Pro Active Pest Control"}, "categories": {}}
    (tmp_path / "payhoa" / "transactions.json").write_text(json.dumps(snap), encoding="utf-8")
    report = sources_report(tmp_path, mystique())
    rows = {r["name"]: r for r in report["senders"]}
    assert rows["First Citizens Bank"]["payments"] == 0
    assert rows["ProActive Pest Control"]["paidCents"] == 16500
    assert any("ProActive Pest Control" in line for line in report_lines(report))
