"""Copies of one document across channels: the identity rules, the grouping, and the best copy."""

from __future__ import annotations

from datetime import date

from jason.community.copies import Channel, DocumentCopy, JoinRule, best, group, join_rule

PRIORITY = (Channel.ISSUER_PORTAL, Channel.EMAIL, Channel.PAYHOA, Channel.PAPER, Channel.LIBRARY)


def _copy(channel: Channel, ref: str, **kw) -> DocumentCopy:
    return DocumentCopy(channel, ref, **kw)


def test_the_same_file_is_one_document_whoever_sent_it() -> None:
    a = _copy(Channel.PAYHOA, "a.pdf", sha256="abc", payhoa_tx=1)
    b = _copy(Channel.PAYHOA, "b.pdf", sha256="abc", payhoa_tx=2)
    assert join_rule(a, b) is JoinRule.SAME_FILE


def test_numbers_decide_when_both_copies_print_one() -> None:
    portal = _copy(Channel.ISSUER_PORTAL, "1763857.pdf", issuer="ProActive", number="1763857", total_cents=25000)
    attached = _copy(Channel.PAYHOA, "inv.pdf", issuer="ProActive", number="#01763857", total_cents=25000)
    other = _copy(Channel.PAYHOA, "inv2.pdf", issuer="ProActive", number="1743521", total_cents=25000, issued=date(2026, 4, 1))
    assert join_rule(portal, attached) is JoinRule.SAME_NUMBER
    assert join_rule(portal, other) is None


def test_a_utility_bill_joins_on_account_and_date() -> None:
    portal = _copy(Channel.ISSUER_PORTAL, "p.pdf", issuer="City", number="2026-04-16_x", account="3100000065", issued=date(2026, 4, 16))
    attached = _copy(Channel.PAYHOA, "a.pdf", issuer="City", account="3100000065", issued=date(2026, 4, 16))
    assert join_rule(portal, attached) is JoinRule.SAME_ACCOUNT_DATE


def test_a_letter_with_no_date_or_number_joins_on_amount_and_arrival() -> None:
    attached = _copy(Channel.PAYHOA, "400255.pdf", issuer="Signal", number="400255", issued=date(2025, 3, 17), total_cents=47100)
    letter = _copy(Channel.PAPER, "mail 1", issuer="Signal", total_cents=47100, received=date(2025, 3, 25))
    late = _copy(Channel.PAPER, "mail 2", issuer="Signal", total_cents=47100, received=date(2025, 5, 1))
    assert join_rule(attached, letter) is JoinRule.SAME_AMOUNT_ARRIVAL
    assert join_rule(attached, late) is None


def test_no_issuer_means_no_join_but_the_same_file() -> None:
    a = _copy(Channel.PAPER, "x", number="100", total_cents=500)
    b = _copy(Channel.PAYHOA, "y", number="100", total_cents=500)
    assert join_rule(a, b) is None


def test_the_best_copy_follows_the_priority_and_every_copy_stays() -> None:
    copies = [
        _copy(Channel.PAPER, "mail 1", issuer="Signal", total_cents=47100, received=date(2025, 3, 25)),
        _copy(Channel.PAYHOA, "400255.pdf", issuer="Signal", number="400255", issued=date(2025, 3, 17), total_cents=47100, payhoa_tx=9),
        _copy(Channel.PAYHOA, "400255 (2).pdf", issuer="Signal", number="400255", issued=date(2025, 3, 17), total_cents=47100, payhoa_tx=10),
        _copy(Channel.ISSUER_PORTAL, "1763857.pdf", issuer="ProActive", number="1763857"),
    ]
    docs = group(copies)
    signal = next(d for d in docs if d.issuer == "Signal")
    assert len(signal.copies) == 3 and set(signal.channels) == {Channel.PAPER, Channel.PAYHOA}
    assert best(signal, PRIORITY).channel is Channel.PAYHOA
    assert {rule for _a, _b, rule in signal.joins} == {JoinRule.SAME_NUMBER, JoinRule.SAME_AMOUNT_ARRIVAL}
    assert sum(len(d.copies) for d in docs) == len(copies)


def test_an_unreadable_copy_is_never_the_best() -> None:
    copies = [_copy(Channel.ISSUER_PORTAL, "scan.pdf", issuer="X", number="1", readable=False),
              _copy(Channel.PAPER, "mail", issuer="X", number="1")]
    [doc] = group(copies)
    assert best(doc, PRIORITY).channel is Channel.PAPER


def test_a_payment_with_no_payhoa_vendor_matches_by_the_issuers_words() -> None:
    from jason.community.copies import LogicalDocument
    from jason.tasks.copies import _payment

    invoice = LogicalDocument([_copy(Channel.EMAIL, "INV-56431.pdf", issuer="Flock Safety", number="INV-56431",
                                     issued=date(2025, 1, 14), total_cents=500000)])
    paid = {"id": 7, "date": date(2025, 1, 23), "amountCents": 500000, "vendor": "",
            "description": "Online Payment 23472636932 To Flock Group Inc 01/23"}
    other = {"id": 8, "date": date(2025, 1, 23), "amountCents": 500000, "vendor": "Some Vendor",
             "description": "Online Payment To Flock Group Inc"}
    words = {"Flock Safety": ("FLOCK GROUP", "FLOCK SAFETY")}
    assert _payment(invoice, [paid, other], {}, words_of=words) == {"txIds": [7], "how": "amount and date", "date": "2025-01-23"}
    # Without the sender's words, nothing ties a vendorless payment to the invoice.
    assert _payment(invoice, [paid], {}) is None
    # A word must stand whole: "FLOCK GROUP" does not match "FLOCKGROUPS".
    assert _payment(invoice, [{**paid, "description": "To FLOCKGROUPS"}], {}, words_of=words) is None


def test_a_bid_and_the_invoice_that_followed_it_are_two_documents_linked_forward() -> None:
    from jason.community.copies import Fulfilment, fulfilments
    from jason.community.incidents import Stage

    bid = _copy(Channel.EMAIL, "roof repair bid.pdf", issuer="Summit Roofing Company", issued=date(2024, 12, 23),
                total_cents=113800, stage=Stage.PROPOSAL)
    invoice = _copy(Channel.PAYHOA, "Invoice 1022.pdf", issuer="Summit Roofing Company", number="1022",
                    issued=date(2024, 12, 24), total_cents=113800, stage=Stage.INVOICE, payhoa_tx=9)
    # Within three days and the same amount, but a bid is not its invoice.
    assert join_rule(bid, invoice) is None
    docs = group([bid, invoice])
    assert len(docs) == 2
    by_stage = {d.stage: n for n, d in enumerate(docs)}
    links = fulfilments(docs)
    assert links == {by_stage[Stage.PROPOSAL]: (by_stage[Stage.INVOICE], Fulfilment.SAME_AMOUNT)}
    assert docs[by_stage[Stage.PROPOSAL]].before_work and not docs[by_stage[Stage.INVOICE]].before_work


def test_a_final_bill_that_moved_a_little_still_fulfils_the_proposal_but_an_earlier_one_does_not() -> None:
    from jason.community.copies import Fulfilment, LogicalDocument, fulfilments
    from jason.community.incidents import Stage

    proposal = LogicalDocument([_copy(Channel.EMAIL, "proposal.pdf", issuer="E&R Landscaping", issued=date(2025, 6, 23),
                                      total_cents=275000, stage=Stage.PROPOSAL)])
    earlier = LogicalDocument([_copy(Channel.PAYHOA, "old.pdf", issuer="E&R Landscaping", issued=date(2025, 6, 1),
                                     total_cents=275000, stage=Stage.INVOICE)])
    final = LogicalDocument([_copy(Channel.PAYHOA, "final.pdf", issuer="E&R Landscaping", issued=date(2025, 8, 1),
                                   total_cents=290000, stage=Stage.INVOICE)])
    far = LogicalDocument([_copy(Channel.PAYHOA, "far.pdf", issuer="E&R Landscaping", issued=date(2025, 8, 2),
                                 total_cents=400000, stage=Stage.INVOICE)])
    assert fulfilments([proposal, earlier, final, far]) == {0: (2, Fulfilment.NEAR_AMOUNT)}


def test_a_proposal_is_never_matched_to_a_payment_by_amount() -> None:
    from jason.community.copies import LogicalDocument
    from jason.community.incidents import Stage
    from jason.tasks.copies import _payment

    bid = LogicalDocument([_copy(Channel.EMAIL, "bid.pdf", issuer="Summit Roofing Company", issued=date(2024, 12, 23),
                                 total_cents=113800, stage=Stage.PROPOSAL)])
    pay = {"id": 5, "date": date(2025, 2, 3), "amountCents": 113800, "vendor": "SUMMIT", "description": ""}
    assert _payment(bid, [pay], {"Summit Roofing Company": "SUMMIT"}) is None


def test_an_emailed_documents_issuer_is_its_writer_and_never_a_platform() -> None:
    from jason.community.sources import Sender, SourceKind
    from jason.tasks.copies import email_issuer

    class Community:
        def senders(self):
            return (Sender("The Helsing Group", SourceKind.MANAGER, ("HELSING",), domains=("helsing.com",)),
                    Sender("Flock Safety", SourceKind.VENDOR, ("FLOCK SAFETY",), domains=("flocksafety.com",)),
                    Sender("PayHOA", SourceKind.PLATFORM, ("PAYHOA",), domains=("payhoa.com",)),
                    Sender("GoodLife Construction", SourceKind.VENDOR, ("GOODLIFE CONSTRUCTION",)))

    c = Community()
    # The manager copied on the vendor's message is not the issuer.
    assert email_issuer(["helsing.com", "flocksafety.com"], ["flocksafety.com"], "", "Past Due Balance", c) == "Flock Safety"
    # A platform's notice carries a vendor's proposal: the letterhead names the issuer, else nobody does.
    assert email_issuer(["payhoa.com"], ["payhoa.com"], "GOODLIFE CONSTRUCTION\nProposal 750977", "Notice", c) == "GoodLife Construction"
    assert email_issuer(["payhoa.com"], ["payhoa.com"], "Proposal", "Notice of Board Decision", c) == ""


def test_a_proposal_with_no_invoice_on_file_is_searched_for_among_the_vendors_payments() -> None:
    from jason.community.copies import LogicalDocument
    from jason.community.incidents import Stage
    from jason.tasks.copies import proposal_payments

    def estimate(cents: int) -> LogicalDocument:
        return LogicalDocument([_copy(Channel.EMAIL, "estimate.pdf", issuer="E&R Landscaping", issued=date(2026, 4, 28),
                                      total_cents=cents, stage=Stage.PROPOSAL)])

    def pay(i: int, day: date, cents: int, vendor: str = "E&R Landscaping", description: str = "") -> dict:
        return {"id": i, "date": day, "amountCents": cents, "vendor": vendor, "description": description}

    vendors, words = {"E&R Landscaping": "E&R Landscaping"}, {"E&R Landscaping": ("E&R LANDSCAPING",)}
    payments = [pay(1, date(2026, 4, 1), 336500),                       # before the estimate: not its payment
                pay(2, date(2026, 6, 4), 336500),
                pay(3, date(2026, 6, 4), 175000),
                pay(4, date(2026, 5, 1), 160000),
                pay(5, date(2026, 7, 1), 340000, vendor="", description="Online Payment To E&R Landscaping Inc")]
    assert proposal_payments(estimate(336500), payments, vendors, words) == {
        "paid": {"txIds": [2], "how": "same vendor and amount after the proposal", "date": "2026-06-04"}}
    near = proposal_payments(estimate(335000), payments, vendors, words)["candidates"]
    assert [c["txIds"] for c in near] == [[2], [5], [4, 3]]        # within 10% (one vendorless by its words), then a pair
    assert proposal_payments(estimate(999900), payments, vendors, words) == {}
    assert proposal_payments(estimate(336500), payments, {}, {}) == {}


def test_a_document_on_several_payments_is_explained_by_the_other_audits(tmp_path) -> None:
    import json

    from jason.tasks.copies import _explain, audit_notes

    (tmp_path / "payhoa").mkdir()
    (tmp_path / "payhoa" / "utility-audit.json").write_text(json.dumps({"payments": [
        {"key": 2, "findings": ["paid twice: the payment already paid 3547596", "evidence: the next bill asked $0.91"],
         "rows": [{"txId": 2}]},
        {"key": 4, "findings": ["same amount as the 2024-04-25 payment, and the next bill shows no credit for it"], "rows": [{"txId": 4}]},
        {"key": 6, "findings": ["attached bill(s) this payment did not pay: 7200000072 2025-11-06"], "rows": [{"txId": 6}]},
        {"key": 9, "findings": ["no set of bills on disk sums to this payment"], "rows": [{"txId": 9}]}]}), encoding="utf-8")
    (tmp_path / "vendors" / "proactive").mkdir(parents=True)
    (tmp_path / "vendors" / "proactive" / "verification.json").write_text(json.dumps({"payments": [
        {"transactionId": 8, "findings": ["the vendor applied this payment to invoice 1783598; attached: x.pdf (invoice 1703833)"]}]}),
        encoding="utf-8")
    notes = audit_notes(tmp_path)
    assert _explain([1, 2], {}, notes).startswith("paid twice")
    assert _explain([3, 4], {}, notes).startswith("two payments of the same amount")
    assert _explain([5, 6], {}, notes).startswith("attached to the wrong payment, per the utility audit")
    assert _explain([7, 8], {}, notes).startswith("attached to the wrong payment, per the vendor's portal")
    assert _explain([10, 11], {10: 100, 11: 100}, notes) == "split lines of one payment"
    assert _explain([9, 12], {}, notes) == ""


def test_one_months_bill_on_several_monthly_payments_reads_as_a_recurring_bill() -> None:
    from jason.tasks.copies import _explain

    monthly = {1: {"date": date(2026, 4, 2), "amountCents": 150}, 2: {"date": date(2026, 5, 4), "amountCents": 149},
               3: {"date": date(2026, 6, 2), "amountCents": 150}, 4: {"date": date(2026, 6, 10), "amountCents": 150}}
    assert _explain([1, 2, 3], {}, {}, monthly, 150).startswith("a recurring bill")
    # Two payments a week apart are not months of a recurring bill; nor are payments of another amount.
    assert _explain([3, 4], {}, {}, monthly, 150) == ""
    assert _explain([1, 3], {}, {}, monthly, 900) == ""


def test_two_accounts_bills_of_the_same_amount_and_day_are_two_documents() -> None:
    first = _copy(Channel.PAYHOA, "139826-DistributionView2.pdf", issuer="SMUD", account="6906859",
                  issued=date(2024, 10, 24), total_cents=7743, payhoa_tx=8668867)
    second = _copy(Channel.PAYHOA, "139834-DistributionView2 (9).pdf", issuer="SMUD", account="6906880",
                   issued=date(2024, 10, 24), total_cents=7743, payhoa_tx=8668872)
    assert join_rule(first, second) is None and len(group([first, second])) == 2
    # The same account's copies still join.
    portal = _copy(Channel.ISSUER_PORTAL, "2024-10-24_340009342199.pdf", issuer="SMUD", account="6906859",
                   issued=date(2024, 10, 24), total_cents=7743)
    assert join_rule(first, portal) is not None


def test_a_utility_bill_paid_twice_shows_the_credit_on_the_next_bill(tmp_path) -> None:
    import sqlite3

    from jason.tasks.copies import _explain, next_bill_credit

    with sqlite3.connect(tmp_path / "utilities.db") as db:
        db.execute("create table bills (account text, bill_date text, total_cents int, due_cents int)")
        db.executemany("insert into bills values (?, ?, ?, ?)", [
            ("2188483088", "2025-12-03", 1123, 1123), ("2188483088", "2026-01-05", 1123, 0),
            ("6906859", "2024-10-24", 7743, 7743), ("6906859", "2024-11-22", 7517, 7517)])
    credit = next_bill_credit(tmp_path, "2188483088", date(2025, 12, 3), 1123)
    assert credit == "the 2026-01-05 bill asked $0.00 against $11.23 of charges"
    assert _explain([1, 2], {}, {}, credit=credit).startswith("paid twice; the next bill shows the credit")
    # Paid once: the next bill asks for all of its charges.
    assert next_bill_credit(tmp_path, "6906859", date(2024, 10, 24), 7743) == ""
    assert next_bill_credit(tmp_path, "", date(2024, 10, 24), 7743) == ""


def test_a_credit_that_paid_a_missing_months_bill_shows_as_its_remainder(tmp_path) -> None:
    import sqlite3

    from jason.tasks.copies import next_bill_credit

    with sqlite3.connect(tmp_path / "utilities.db") as db:
        db.execute("create table bills (account text, bill_date text, total_cents int, due_cents int)")
        # $250.11 paid twice on the March bill; April's bill is not on file; May's asks $5.92 less than its charges.
        db.executemany("insert into bills values (?, ?, ?, ?)", [("3547597", "2024-03-28", 25011, 25011),
                                                                   ("3547597", "2024-05-28", 25939, 25347)])
    assert next_bill_credit(tmp_path, "3547597", date(2024, 3, 28), 25011).startswith("no bill on file between")


def test_a_reused_invoice_number_on_another_amount_and_month_is_another_invoice() -> None:
    may = _copy(Channel.PAYHOA, "Invoice (1-5MS).pdf", issuer="All Year Pressure Washing", number="1-5MS",
                issued=date(2024, 5, 7), total_cents=120000)
    september = _copy(Channel.PAYHOA, "invoice (1-6MS).pdf", issuer="All Year Pressure Washing", number="1-5MS",
                      issued=date(2024, 9, 11), total_cents=85000)
    assert join_rule(may, september) is None
    same = _copy(Channel.EMAIL, "1-5MS.pdf", issuer="All Year Pressure Washing", number="1-5MS", issued=date(2024, 5, 7),
                 total_cents=120000)
    assert join_rule(may, same) is JoinRule.SAME_NUMBER


def test_a_bill_paid_in_parts_and_a_deposit_that_is_not_a_payment() -> None:
    from jason.community.copies import LogicalDocument
    from jason.tasks.copies import _explain, _payment

    fines = {1: {"date": date(2024, 9, 17), "amountCents": 40400}, 2: {"date": date(2024, 9, 17), "amountCents": 46700}}
    assert _explain([1, 2], {}, {}, fines, 87100) == "one bill paid in parts (the payments add up to it)"
    envelope = LogicalDocument([_copy(Channel.PAYHOA, "Envelope.pdf", payhoa_tx=10), _copy(Channel.PAYHOA, "Envelope.pdf", payhoa_tx=11)])
    found = _payment(envelope, [], {}, money_in={10})
    assert found["txIds"] == [11] and found["deposits"] == [10] and "onSeveralPayments" not in found


def test_an_issuer_named_only_by_the_words_needs_a_bill_and_never_the_recipients_of_outgoing_mail() -> None:
    from jason.community.sources import Sender, SourceKind
    from jason.tasks.copies import email_issuer

    class Community:
        def senders(self):
            return (Sender("RCS TC", SourceKind.VENDOR, ("RCS TC",)),
                    Sender("California Builder Services", SourceKind.VENDOR, ("CALIFORNIA BUILDER",), domains=("cabuilderservices.com",)))

    c = Community()
    # Sent to the reserve study preparer: the quote is RCS TC's, read from its letterhead.
    assert email_issuer([], [], "RCS TC\nPrice $6,000.00", "Re: Reserve Study", c) == "RCS TC"
    # Minutes that mention the vendor are not the vendor's document.
    assert email_issuer([], [], "The board approved the RCS TC bid", "Minutes", c, bill=False) == ""


def test_a_deposit_request_on_two_payments_is_a_deposit_and_its_balance() -> None:
    from jason.tasks.copies import _explain

    title = "Mystique Community Association Mail - Job #651706803 - Deposit Required.pdf"
    assert _explain([1, 2], {}, {}, title=title) == "a deposit and the balance of one job"
    assert _explain([1, 2, 3], {}, {}, title=title) == ""
    assert _explain([1, 2], {}, {}, title="Invoice.pdf") == ""


def test_one_quote_on_payments_for_its_jobs_months_apart() -> None:
    from jason.tasks.copies import _explain

    jobs = {1: {"date": date(2025, 5, 7), "amountCents": 600000}, 2: {"date": date(2025, 10, 9), "amountCents": 750000}}
    assert _explain([1, 2], {}, {}, jobs, title="1JR Landscaping Quote.pdf", stage="proposal") == "one quote for several jobs, each paid when done"
    assert _explain([1, 2], {}, {}, jobs, title="Invoice.pdf", stage="invoice") == ""
