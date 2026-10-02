"""Approvals in the minutes followed to payments: by the cited proposal, the named payee, or the approved amount."""

from __future__ import annotations

import json

from jason.tasks.paid_vs_approved import build


def _write(tmp, readings, payments, asked=None):
    (tmp / "documents").mkdir()
    (tmp / "documents" / "readings.json").write_text(json.dumps({"readings": readings}), encoding="utf-8")
    (tmp / "payhoa").mkdir()
    (tmp / "payhoa" / "invoice-review.json").write_text(json.dumps({"payments": payments}), encoding="utf-8")
    if asked:
        (tmp / "documents" / "questions-minutes.json").write_text(json.dumps(asked), encoding="utf-8")


def _minutes(id_, day, *actions):
    return {"id": id_, "kind": "minutes", "name": f"Minutes {day}", "fields": {"meeting_date": day, "actions": list(actions)}}


def _pay(key, day, cents, payee):
    return {"key": key, "date": day, "amountCents": cents, "payee": payee, "documents": []}


def test_payee_amount_and_model_answers_link_payments_and_investments_are_not_spending(tmp_path) -> None:
    readings = [
        _minutes("1", "2025-07-15", {"text": "The group approves the tree pruning plan.", "outcome": "approved", "amount": None},
                 {"text": "The board approved Summit Roofing for $2,584.", "outcome": "approved", "amount": 258400},
                 {"text": "The board agreed to invest $97,000 in a CD.", "outcome": "approved", "amount": 9700000}),
    ]
    asked = {"files": [{"id": "1", "name": "Minutes 2025-07-15", "answers": [
        {"key": "amounts_approved", "verdict": "model only", "model": ["$9,871 for tree pruning"]}]}]}
    payments = [_pay(1, "2025-08-17", 987100, "Monarch Landscape"), _pay(2, "2025-09-01", 258400, "Summit Roofing Company"),
                _pay(3, "2025-10-01", 880000, "GoodLife Construction Inc.")]
    _write(tmp_path, readings, payments, asked)
    result = build(tmp_path)
    by_amount = {a["amountCents"]: a for a in result["approvals"]}
    assert 9700000 not in by_amount                                              # an investment pays no vendor
    assert by_amount[258400]["outcome"] == "paid within the approval" and "names the payee" in by_amount[258400]["how"]
    assert by_amount[987100]["payments"][0]["payee"] == "Monarch Landscape"       # by the approved amount
    assert [p["payee"] for p in result["unapprovedLarge"]] == ["GoodLife Construction Inc."]


def test_insurance_renewal_sums_financed_installments_and_places_flood_premium_on_its_building(tmp_path) -> None:
    from datetime import date

    readings = [
        _minutes("1", "2025-09-23", {"text": "The board approved a $3,000 insurance renewal.", "outcome": "approved", "amount": 300000}),
        {"id": "2", "kind": "insurance_policy", "name": "FLOOD POLICY 25-26 BLDG 5.pdf",
         "fields": {"policy_number": "5010022209", "coverage": "flood", "term_start": "2025-11-20", "term_end": "2026-11-20", "premium": 140200}},
    ]
    payments = [
        # The master premium financed: three installments to a premium finance company, one named only by its bank line.
        {**_pay(1, "2025-09-30", 100000, "Imperial PFS"), "categories": ["Master"]},
        {**_pay(2, "2025-10-30", 100000, ""), "description": "ORIG CO NAME:IPFS CORP CO ENTRY DESCR:PAYMENT", "categories": ["Master"]},
        {**_pay(3, "2025-11-30", 100000, "Imperial PFS"), "categories": ["Master"]},
        # Building 5's flood premium to NFIP Direct, its policy number on the bank line.
        {**_pay(4, "2025-10-01", 140200, "NFIP Direct"), "description": "NFIP DIRECT PREMIUM 5010022209", "categories": ["Flood"]},
        # A premium two years later is outside the 300 days.
        {**_pay(5, "2027-09-30", 100000, "Imperial PFS"), "categories": []},
    ]
    _write(tmp_path, readings, payments)
    (tmp_path / "insurance").mkdir()
    (tmp_path / "insurance" / "sheet.json").write_text(json.dumps([{"kind": "Master", "building": "", "premiums": {"2025": 300000}}]),
                                                       encoding="utf-8")
    result = build(tmp_path, today=date(2026, 9, 30))
    approval = result["approvals"][0]
    assert approval["outcome"] == "paid within the approval" and approval["paidCents"] == 300000
    assert approval["insuranceKeys"] == [1, 2, 3]                     # the flood premium is not the package renewal
    assert "flood" not in approval["coverages"]
    by = {(p["coverage"], p["building"]): p for p in result["insurance"]["policies"]}
    flood = next(t for t in by[("flood", 5)]["terms"] if t["start"] == "2025-11-20")
    assert flood["premiumCents"] == 140200 and flood["paidCents"] == 140200 and flood["payees"] == ["NFIP Direct"]
    assert "declarations" in flood["premiumSource"]
    master = next(t for t in by[("master", None)]["terms"] if t["start"] == "2025-09-28")
    assert master["installments"] == 3 and master["paidCents"] == 300000 and master["premiumCents"] == 300000
    assert master["approved"][0]["amountCents"] == 300000 and not master["findings"]


def test_an_approval_with_no_amount_links_through_its_item_to_the_one_vendor_paid(tmp_path) -> None:
    items = [{"number": "d", "title": "Bird Exclusion - two proposals to install netting",
              "notes": "Pro Active Pest Control - HighClass Gutter and Glass - the gutter vendor proposed netting on all 6 "
                       "buildings. The board accepted the proposal and will schedule the work.",
              "attachments": ["proactive-form-100148.pdf", "Square - Estimate - 000865.pdf"], "subitems": []}]
    readings = [{"id": "1", "kind": "minutes", "name": "Minutes 7/16/24", "fields": {
        "meeting_date": "2024-07-16", "items": items,
        "actions": [{"text": "The board accepted the proposal and will schedule the work.", "outcome": "approved", "amount": None}]}}]
    payments = [_pay(1, "2024-07-24", 666000, "HighClass Window and Gutter")] + \
               [_pay(10 + m, f"2024-{m:02d}-03", 25000, "Pro Active Pest Control") for m in range(1, 9)]   # monthly: not the one
    _write(tmp_path, readings, payments)
    result = build(tmp_path)
    approval = next(a for a in result["approvals"] if a["date"] == "2024-07-16")
    assert approval["payments"][0]["payee"] == "HighClass Window and Gutter" and approval["proposals"] == ["000865"]
    assert "minutes state no amount" in approval["outcome"] and not result["unapprovedLarge"]
