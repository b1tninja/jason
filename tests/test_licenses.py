"""License mentions, their holders, the register, and the parties a contract names. Every name and number is made up."""

from __future__ import annotations

from jason.community import contract_terms as ct
from jason.community.licenses import Board, by_license, find_licenses, letterhead_line, resolve
from jason.tasks import licenses as register_task


def _one(text, board):
    found = [m for m in find_licenses(text) if m.board is board]
    assert found, f"no {board} in {text!r}: {[(m.board, m.number) for m in find_licenses(text)]}"
    return found[0]


def test_a_contractors_license_and_its_holder_not_the_customer():
    text = ("Acme Roofing Company, Inc.\n123 Main St.\nAnytown, CA 95000\nBill To:\nExample Management, Inc.\n"
            "500 Oak Ave.\nINVOICE\nContractor's License # 1234567\n")
    m = _one(text, Board.CSLB)
    assert m.number == "1234567" and m.holder == "Acme Roofing Company, Inc."
    assert m.verify.endswith("LicNum=1234567")


def test_classes_boards_and_other_states():
    assert _one("C10 654321 EXAMPLE ALARM, INC.", Board.CSLB).classification == "C-10"
    assert _one("CA Contractor Lic. C-10 #527800", Board.CSLB).classification == "C-10"
    alarm = _one("ACO 1234 EXAMPLE ALARM, INC. 1 Main St.", Board.BSIS)
    assert alarm.number == "1234" and alarm.holder == "EXAMPLE ALARM, INC."
    az = _one("AZ ROC Lic. CR-11 #123456; CA Contractor Lic. C-10 #527800", Board.OUT_OF_STATE)
    assert az.jurisdiction == "Arizona" and az.classification == "CR-11"
    assert _one("LICENSE PR1234 DUE DATE", Board.SPCB).number == "PR1234"
    assert _one("Example Realty, Inc. | DRE License #01234567", Board.DRE).verify.endswith("License_id=01234567")
    assert _one("Example Paving Company DIR #1000012345", Board.DIR).number == "1000012345"


def test_what_is_not_a_license():
    assert not find_licenses("DRE 123 456 78901 NNNN 0000 Example Bank")       # a bank line, not a DRE number
    assert not [m for m in find_licenses("We handle business license applications.") if m.board is Board.LOCAL]


def test_a_notarys_commission_names_no_business():
    m = _one("Example Insurance Company Notary Public - California Placer County Commission # 2400000", Board.NOTARY)
    assert m.holder == "" and m.jurisdiction == "California"


def test_a_packet_page_never_takes_another_pages_name():
    text = ("Example Reserve Group\nreserve study line items\n\f"
            "Remit Payment To:\nP.O. Box 1\nBill To:\nExample Management, Inc.\nINVOICE\nContractor's license # 7654321.\n")
    m = _one(text, Board.CSLB)
    assert m.holder == ""


def test_a_letterhead_without_a_company_suffix():
    assert letterhead_line("QUOTE\nAll Seasons Washing\n123 Oak St.\nAnytown, CA 95000\n") == "All Seasons Washing"
    assert letterhead_line("Bill To:\nSample Ridge Community Association\n1 Main St.\n") == ""


def test_an_unspecified_number_takes_the_board_printed_elsewhere():
    a = find_licenses("Acme Landscape Services, Inc.\nLicense #537800\n")
    b = find_licenses("Contractor's License #537800 Acme Landscape Services, Inc.")
    merged = by_license(resolve(a + b))
    assert [m.board for m in merged] == [Board.CSLB]


def test_the_register_groups_by_license():
    docs = [({"id": "1", "path": "a.pdf", "period": "2024"}, m) for m in find_licenses("ACO 1234 EXAMPLE ALARM, INC.")]
    docs += [({"id": "2", "path": "b.pdf", "period": "2025"}, m) for m in find_licenses("ACO-1234 EXAMPLE ALARM, INC.")]
    rows = register_task.register(docs)
    assert len(rows) == 1 and rows[0]["holder"] == "EXAMPLE ALARM, INC." and [d["id"] for d in rows[0]["documents"]] == ["2", "1"]
    assert "EXAMPLE ALARM" in register_task.markdown(rows)


def test_a_contract_written_to_you_names_its_parties():
    text = ct.unwrap("SERVICE AGREEMENT\nExample Alarm, Inc.\n1 Main St.\n" + (
        "You must pay each invoice within thirty (30) days. We will inspect the system each quarter. "
        "You agree to give us access. We will send you a report after each inspection. Your account is due monthly. "
        "We will not share your data. You will notify us of any change. Our technicians are licensed. ") * 2)
    parties = ct.defined_parties(text)
    terms = ct.read_terms(text, source="t", parties=parties)
    inspect = next(t for t in terms if "inspect the system" in t.quote)
    assert inspect.party is ct.Party.COUNTERPARTY and inspect.kind is ct.TermKind.DUTY
    share = next(t for t in terms if "not share" in t.quote)
    assert share.kind is ct.TermKind.PROHIBITION and share.party is ct.Party.COUNTERPARTY
    pay = next(t for t in terms if "must pay" in t.quote)
    assert pay.party is ct.Party.ASSOCIATION
    assert sum(1 for t in terms if "inspect the system" in t.quote) == 1          # the repeated copy is read once


def test_a_firm_that_calls_itself_by_its_initials():
    text = ct.unwrap("PROPOSAL\nThe Example Sprinkler Company\n12 Oak St.\nAnytown, CA 95000\n"
                     "1. Testing T.E.S.C. shall test each riser annually and shall deliver a written report to the owner.\n")
    parties = ct.defined_parties(text)
    assert "t.e.s.c." in parties.counterparty
    term = next(t for t in ct.read_terms(text, source="t", parties=parties) if "riser" in t.quote)
    assert term.party is ct.Party.COUNTERPARTY and term.deliverable


def test_the_counterparty_is_not_a_service_the_contract_names_or_a_sentence():
    text = ("ROOF REPAIR AGREEMENT\nAny dispute shall go to Binding Arbitration conducted by Example Dispute Resolution "
            "Services, Inc.\nIS PART OF THIS CONTRACT. Acme Roofing Company, Inc.\nCA STATE LICENSE #7654321\n")
    assert ct.counterparty_name(text, ct.defined_parties(text)) == "Acme Roofing Company, Inc."


def test_the_reading_carries_licenses_and_flags_another_holder():
    from jason.tasks import contract_terms as terms_task

    text = ("PAINTING CONTRACT\nAcme Painting, Inc. (hereinafter \"Contractor\")\n1 Main St.\n"
            "Contractor's License # 1234567\n2. Work Contractor shall paint the buildings.\n\f"
            "Electrical work by Example Electric Company, Inc. CA Contractor Lic. C-10 #7654321\n")
    reading = terms_task.read(text, key="k")
    assert {m.number for m in reading.licenses} == {"1234567", "7654321"}
    codes = [f.code for f in reading.findings]
    assert codes.count("license-printed") == 2 and "license-holder-differs" in codes
    assert "## Parties" in terms_task.markdown(reading)
