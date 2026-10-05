"""The preliminary kind analysis and the kind readers ingest runs after it. Every text here is made up."""

from __future__ import annotations

from types import SimpleNamespace

from jason.community.kind_analysis import Verdict, analyze, association_is_party, signals_of
from jason.community.kind_readers import KindReader, ReaderContext, readers_for, run_readers

COMMUNITY = SimpleNamespace(name="Sample Ridge Community Association", corporate_name="Sample Ridge Community Association")

CONTRACT = """MANAGEMENT SERVICE AGREEMENT
This Agreement is made and entered into by and between Acme Community Management, Inc. (hereinafter "MANAGER") and
Sample Ridge Community Association (hereinafter "ASSOCIATION").
1.1 Term The term of this Agreement shall be one (1) year and shall automatically renew unless either party gives notice.
2.1 Compensation The Association shall pay Manager $1,000.00 per month.
3.1 Meetings Manager shall attend four meetings of the Board each year.
3.2 Records Manager shall maintain the books and records of the Association.
4.1 Insurance Manager shall maintain a fidelity bond.
5.1 Termination This Agreement may be terminated by either party upon sixty (60) days written notice.
6.1 Notices All notices shall be in writing.
IN WITNESS WHEREOF, the parties hereto have executed this Agreement.
By: ____________________ By: ____________________
""" + "This Agreement binds the parties and their successors. " * 10

ASSIGNMENT = """ASSIGNMENT OF MANAGEMENT AGREEMENT AND SUBORDINATION OF MANAGEMENT FEES
This Assignment is made by and among Example Rental Fund LLC (the "Borrower"), Example Lender LLC (the "Lender"), and
Example Property Management, Inc. (the "Manager").
1. The Borrower assigns to the Lender all of its rights under the Management Agreement as security for the Loan.
2. The Management Fees are subordinate to the lien of the Lender's deed of trust and the Loan Agreement.
3. The Manager shall cooperate with any replacement manager the Lender selects.
4. This Assignment terminates when the Loan is paid in full.
5. Notices go to the Borrower and the Lender at the addresses on the signature pages.
6. This Assignment is governed by the laws of the State of New York.
""" + "The Lender may exercise its rights under the Loan Agreement. " * 10

INVOICE = """INVOICE
Example Plumbing Co.
Invoice #: 1001
Invoice Date: 01/05/2026
Bill To: Sample Ridge Community Association
Description: repair a leaking valve at the pump room
Labor $180.00
Parts $70.00
Amount Due: $250.00
Make checks payable to Example Plumbing Co.
"""


def test_a_contract_named_and_read_as_one_is_confirmed():
    a = analyze("agreement.pdf", CONTRACT, classified="contract", method="NAME", community=COMMUNITY)
    assert a.verdict is Verdict.CONFIRMED and a.kind == "contract"
    assert {"parties-clause", "signature-block", "term-and-termination"} <= set(a.signals)
    assert association_is_party(CONTRACT, COMMUNITY) is True


def test_an_agreement_between_others_is_a_question_with_no_suggestion():
    a = analyze("Assignment of Management Agreement.pdf", ASSIGNMENT, classified="contract", method="NAME",
                community=COMMUNITY)
    assert association_is_party(ASSIGNMENT, COMMUNITY) is False
    assert a.verdict is Verdict.DISAGREES
    assert any("not named as a party" in n and "lender" in n for n in a.notes)
    assert a.suggestion == "" and a.as_dict()["suggestion"] == ""


def test_an_owners_rental_papers_point_to_the_units_file():
    from jason.community.kind_analysis import third_party_kind

    words = ("PROPERTY MANAGEMENT AGREEMENT Example Rental Fund LLC (hereinafter \"Owner\") and Example Realty "
             "(hereinafter \"Broker\"). The Owner appoints the Broker to lease, rent, operate and manage the property.")
    assert [k for k, _ in third_party_kind(words)] == ["property-management"]
    assert [k for k, _ in third_party_kind("The Landlord leases to the Tenant the premises.")] == ["lease"]


def test_a_file_with_no_kind_gets_a_proposal_not_a_kind():
    a = analyze("scan001.pdf", INVOICE, community=COMMUNITY)
    assert a.verdict is Verdict.PROPOSED and a.suggestion == "invoice"
    assert any("reader" in r for r in a.candidates[0].reasons)


def test_a_kind_the_text_barely_supports_is_weak():
    a = analyze("notes.pdf", "Some notes about the weekend. Nothing else here at all. " * 10, classified="ballot",
                method="CONTENT", community=COMMUNITY)
    assert a.verdict is Verdict.WEAK and a.suggestion == ""


def test_a_persons_answer_is_not_weighed_again():
    a = analyze("x.pdf", INVOICE, classified="minutes", method="PERSON")
    assert a.verdict is Verdict.PERSON and a.kind == "minutes"


def test_signals_need_their_minimum():
    assert not [s for s, _ in signals_of("a motion was made") if s.key == "meeting-acts"]
    assert [s for s, _ in signals_of("called to order; a motion; seconded; carried") if s.key == "meeting-acts"]


def test_readers_follow_the_kind():
    assert [r.key for r in readers_for("contract")] == ["document-model", "contract-terms", "licenses"]
    assert [r.key for r in readers_for("bylaws")] == ["document-model", "norms", "licenses"]
    assert [r.key for r in readers_for("invoice")] == ["document-model", "licenses"]
    assert readers_for("") == []


def test_a_reader_that_fails_is_reported_not_fatal(tmp_path):
    def boom(text, ctx):
        raise RuntimeError("cannot read")

    rows = (KindReader("fine", "ok", frozenset({"invoice"}), lambda text, ctx: {"ok": True}),
            KindReader("broken", "fails", frozenset({"invoice"}), boom))
    out = run_readers(INVOICE, ReaderContext(key="k", name="n", kind="invoice", data_dir=tmp_path), rows)
    assert out["fine"] == {"ok": True} and "cannot read" in out["broken"]["error"]


def test_the_contract_reader_saves_its_reading(tmp_path):
    out = run_readers(CONTRACT, ReaderContext(key="ingest-abc", name="a.pdf", kind="contract", data_dir=tmp_path))
    assert out["contract-terms"]["terms"] > 0 and out["document-model"]["read"] is True
    assert (tmp_path / "contracts" / "terms" / "ingest-abc.json").is_file()
