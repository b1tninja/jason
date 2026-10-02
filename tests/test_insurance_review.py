"""The insurance review: each policy's term against the carriers' letters and the premiums PayHOA paid."""

from __future__ import annotations

import json
from datetime import date
from types import SimpleNamespace

from jason.community.base import Policy
from jason.community.symbols import Building, PolicyKind
from jason.tasks.insurance import fold_number, review


def _community(*policies: Policy):
    return SimpleNamespace(insurance=lambda: SimpleNamespace(policies=policies))


def _write(tmp_path, letters: list[tuple[str, str, str, list[str], list[str]]], txs: list[dict]) -> None:
    rows = []
    for mail_id, received, text, policies, dates in letters:
        (tmp_path / "mail" / mail_id).mkdir(parents=True)
        (tmp_path / "mail" / mail_id / "text.txt").write_text(text, encoding="utf-8")
        rows.append({"mailId": mail_id, "received": received, "from": "Agency", "kind": "insurance policy, renewal, or invoice",
                     "facts": {"policies": policies}, "deadlines": [{"label": "expire", "date": d} for d in dates]})
    (tmp_path / "mail").mkdir(exist_ok=True)
    (tmp_path / "mail" / "items.json").write_text(json.dumps({"items": rows}), encoding="utf-8")
    (tmp_path / "payhoa").mkdir()
    snap = {"syncedAt": "2026-09-29T15:00:00+00:00", "vendors": {}, "transactions": txs,
            "categories": {"1": {"name": "Flood"}, "2": {"name": "Master"}}}
    (tmp_path / "payhoa" / "transactions.json").write_text(json.dumps(snap), encoding="utf-8")


def _tx(tx_id: int, day: str, cents: int, category: int) -> dict:
    return {"id": tx_id, "transactionDate": day, "amount": cents, "originalAmount": cents, "categoryId": category}


def test_policy_numbers_fold_the_letter_o_and_punctuation() -> None:
    assert fold_number("NO30PK2940-01") == fold_number("N030PK2940-01") == "N030PK294001"


def test_a_flood_payment_goes_to_the_building_whose_renewal_bill_prints_it(tmp_path) -> None:
    three = Policy(PolicyKind.FLOOD, "5010000092", date(2026, 12, 3), Building.BLDG_3, premium_categories=("Flood",))
    eight = Policy(PolicyKind.FLOOD, "5010022696", date(2026, 12, 3), Building.BLDG_8, premium_categories=("Flood",))
    _write(tmp_path, [
        ("1", "2026-09-21", "RENEWAL BILL\nYour flood insurance policy will expire 12/03/2026.\nRenewal premium $1,596.00", ["5010000092"], ["2026-12-03"]),
        ("2", "2026-09-21", "RENEWAL BILL\nRenewal premium $1,636.00", ["5010022696"], ["2026-12-03"]),
    ], [_tx(1, "2026-09-17", 159600, 1), _tx(2, "2026-09-17", 163600, 1), _tx(3, "2026-09-17", 99900, 1)])
    result = review(tmp_path, _community(three, eight), today=date(2026, 9, 29))
    by_building = {p["building"]: p for p in result["policies"]}
    assert by_building[3]["nextTermPayments"] == [{"date": "2026-09-17", "amountCents": 159600}]
    assert by_building[8]["nextTermPayments"][0]["amountCents"] == 163600
    assert "next term paid 2026-09-17" in by_building[3]["standing"]
    assert [u["amountCents"] for u in result["unplacedFloodPayments"]] == [99900]


def test_a_term_that_ended_with_no_premium_and_a_conditional_renewal_is_raised(tmp_path) -> None:
    master = Policy(PolicyKind.MASTER, "N030PK2940-01", date(2026, 9, 28), prior_numbers=("N030PK2940-00",), premium_categories=("Master",))
    _write(tmp_path, [
        ("7", "2026-08-02", "NOTICE OF POLICY CONDITIONAL RENEWAL\nPolicy No.: NO30PK2940-01\n09/28/2026", ["NO30PK2940-01"], ["2026-09-28"]),
        ("8", "2026-07-03", "letter acknowledges receipt of your Notice of Claim.\nDate of Loss: 06/04/2026\nClaim Number: AZ200001\n"
                            "policy NO30PK2940-01", ["NO30PK2940-01"], []),
    ], [_tx(1, "2025-09-30", 782130, 2), _tx(2, "2025-11-13", 228121, 2)])
    result = review(tmp_path, _community(master), today=date(2026, 9, 29))
    [row] = result["policies"]
    assert row["standing"].startswith("term ended 2026-09-28; no premium for the next term")
    assert row["terms"][0]["paidCents"] == 782130 + 228121
    assert any("Conditional renewal" in f for f in row["findings"])
    [claim] = result["claims"]
    assert claim["dateOfLoss"] == "06/04/2026" and claim["claimNumber"] == "AZ200001"


def test_a_renewal_notice_before_the_sheets_date_is_raised(tmp_path) -> None:
    six = Policy(PolicyKind.FLOOD, "5010000095", date(2027, 12, 3), Building.BLDG_6, premium_categories=("Flood",))
    _write(tmp_path, [("3", "2026-09-21", "RENEWAL BILL\nwill expire 12/03/2026", ["5010000095"], ["2026-12-03"])], [])
    [row] = review(tmp_path, _community(six), today=date(2026, 9, 29))["policies"]
    assert any("before the sheet's 2027-12-03" in f for f in row["findings"])


def test_a_renewal_handled_by_email_is_not_reported_as_missing(tmp_path) -> None:
    from jason.community.sources import Sender, SourceKind

    umbrella = Policy(PolicyKind.UMBRELLA, "G75199788", date(2026, 9, 28), agent="Agency", premium_categories=("Umbrella",))
    _write(tmp_path, [], [])
    (tmp_path / "gmail").mkdir()
    messages = [{"messageId": "m1", "threadId": "t1", "at": "2026-09-10T21:29:48+00:00", "direction": "out", "domains": ["agency.com"],
                 "subject": "Re: CORRECT Proposal 26-27: Mystique Community Association", "attachments": ["Renewal Ltr - Umbrella.pdf"]},
                {"messageId": "m2", "threadId": "t2", "at": "2026-09-12T01:41:13+00:00", "direction": "in", "domains": ["other.com"],
                 "subject": "Proposal", "attachments": []}]
    (tmp_path / "gmail" / "correspondence.json").write_text(json.dumps({"messages": messages}), encoding="utf-8")
    community = SimpleNamespace(insurance=lambda: SimpleNamespace(policies=(umbrella,)),
                                senders=lambda: (Sender("Agency", SourceKind.INSURER, ("AGENCY",), domains=("agency.com",)),))
    [row] = review(tmp_path, community, today=date(2026, 9, 29))["policies"]
    assert "renewal handled by email (latest 2026-09-10" in row["standing"]
    assert [m["subject"][:12] for m in row["email"]] == ["Re: CORRECT "]
