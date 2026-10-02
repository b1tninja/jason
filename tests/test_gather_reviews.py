"""Gather-review tasks: who owes, violations, notes, communications, vendors."""

from __future__ import annotations

from typing import Any

from jason.tasks.communications import (
    list_owner_communications,
    summarize_communication,
)
from jason.tasks.context_notes import fetch_context_notes
from jason.tasks.vendor_match import (
    match_vendors_in_transactions,
    suggest_vendor_matches,
)
from jason.tasks.violations_pull import pull_violations
from jason.tasks.who_owes import build_who_owes_rows, who_owes


class _FakeGatherClient:
    def __init__(self) -> None:
        self.violation_statuses: list[str] = []

    def iter_issued_charges(self, org_id: int, status: str = "unpaid"):
        assert org_id == 1
        assert status == "unpaid"
        yield {
            "id": 501,
            "unitId": 10,
            "amount": 12500,
            "title": "Q3 Assessment",
            "ownerName": "Ada Lovelace",
        }
        yield {
            "id": 502,
            "unitId": 10,
            "amount": 2500,
            "title": "Late Fee",
        }

    def iter_recurring_charge_templates(self, org_id: int):
        assert org_id == 1
        yield {"id": 1, "unitId": 10, "title": "Monthly Assessment"}
        yield {"id": 2, "title": "Reserve Contribution"}

    def iter_units(self, org_id: int):
        assert org_id == 1
        yield {
            "id": 10,
            "title": "Lot 1",
            "pastDueBalance": 5000,
            "owners": [{"profile": {"givenNames": "Ada", "familyName": "Lovelace"}}],
        }
        yield {
            "id": 11,
            "title": "Lot 2",
            "pastDueBalance": 100,
            "owners": [{"name": "Grace Hopper"}],
        }

    def iter_violations(self, org_id: int, status="All Outstanding", filters=None):
        del filters
        assert org_id == 1
        self.violation_statuses.append(status)
        if status == "All Outstanding":
            return iter(())
        yield {
            "id": 90,
            "unitId": 10,
            "status": "Closed",
            "title": "Fence (closed)",
        }

    def list_unit_notes(self, org_id: int, unit_id: int):
        assert org_id == 1 and unit_id == 10
        return [{"id": 1, "note": "Gate code on file"}]

    def list_member_notes(self, org_id: int, membership_id: int):
        assert org_id == 1 and membership_id == 20
        return [{"id": 2, "note": "Prefers email"}]

    def iter_communications(self, org_id: int, recipient_id: int | None = None):
        assert org_id == 1 and recipient_id == 20
        yield {
            "id": 7,
            "type": "email",
            "sentAt": "2026-03-01",
            "subject": "Assessment reminder",
        }
        yield {"id": 8, "kind": "letter"}

    def list_vendors(self, org_id: int):
        assert org_id == 1
        return [
            {"id": 1, "name": "Acme Landscaping"},
            {"id": 2, "name": "Pool Pros"},
            {"id": 3, "name": "Water Works"},
        ]

    def list_bill_payments(self, org_id: int):
        assert org_id == 1
        return [{"id": 99, "name": "Roof Co", "vendorId": 9}]

    def iter_transactions(self, org_id: int, reviewed=False):
        del reviewed
        assert org_id == 1
        yield {
            "id": 100,
            "description": "ACH ACME LANDSCAPING INVOICE 12",
            "amount": 4500,
        }
        yield {
            "id": 101,
            "description": "POOL PROS AND WATER WORKS",
            "amount": 2000,
        }
        yield {
            "id": 102,
            "description": "ORIG CO NAME:SMUD ORIG ID:1",
            "amount": 6000,
            "transactionRule": {"name": "SMUD"},
        }
        yield {
            "id": 103,
            "description": "CITY OF SACRAMEN UTIL WATER",
            "amount": 3000,
        }
        yield {
            "id": 104,
            "description": "ROOF CO PAYMENT",
            "amount": 8000,
        }
        yield {"id": 105, "description": "UNKNOWN PAYEE", "amount": 100}


def test_build_who_owes_rows_groups_charges_and_recurring():
    rows = build_who_owes_rows(
        [
            {
                "id": 1,
                "unitId": 10,
                "amount": 1000,
                "title": "Dues",
                "ownerName": "Ada",
            }
        ],
        units=[
            {"id": 10, "title": "Lot 1", "pastDueBalance": 500},
            {"id": 11, "title": "Lot 2", "pastDueBalance": 50},
        ],
        recurring_templates=[
            {"unitId": 10, "title": "Monthly Assessment"},
            {"title": "Reserve"},
        ],
    )
    by_id = {r.unit_id: r for r in rows}
    assert by_id[10].unpaid_amount_cents == 1000
    assert by_id[10].past_due_balance_cents == 500
    assert by_id[10].owner_name == "Ada"
    assert "Monthly Assessment" in by_id[10].recurring_titles
    assert "Reserve" in by_id[10].recurring_titles
    assert by_id[11].unpaid_amount_cents == 0
    assert by_id[11].past_due_balance_cents == 50


def test_who_owes_orchestration():
    report = who_owes(_FakeGatherClient(), 1)
    assert report.unit_count == 2
    assert report.total_unpaid_cents == 15000
    lot1 = next(r for r in report.rows if r.unit_id == 10)
    assert lot1.charge_ids == [501, 502]
    assert lot1.owner_name == "Ada Lovelace"
    assert "Monthly Assessment" in lot1.recurring_titles
    assert "units_owing=2" in report.summary()


def test_pull_violations_always_runs_broader():
    client = _FakeGatherClient()
    report = pull_violations(client, 1)
    assert report.outstanding_count == 0
    assert report.broader_count == 1
    assert client.violation_statuses == ["All Outstanding", ""]
    assert report.broader[0]["id"] == 90
    assert "outstanding=0" in report.summary()


def test_fetch_context_notes_unit_and_member():
    notes = fetch_context_notes(
        _FakeGatherClient(), 1, unit_id=10, membership_id=20
    )
    assert len(notes.unit_notes) == 1
    assert len(notes.member_notes) == 1
    assert "Gate code" in notes.unit_notes[0]["note"]
    assert "unit_notes=1" in notes.summary()


def test_fetch_context_notes_requires_an_id():
    try:
        fetch_context_notes(_FakeGatherClient(), 1)
    except ValueError as exc:
        assert "unit_id" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_summarize_communication_only_existing_fields():
    full = summarize_communication(
        {"id": 1, "type": "email", "sentAt": "2026-01-01", "subject": "Hi"}
    )
    assert full == {
        "id": 1,
        "type": "email",
        "date": "2026-01-01",
        "subject": "Hi",
    }
    sparse = summarize_communication({"id": 2, "kind": "letter"})
    assert sparse == {"id": 2, "type": "letter"}
    assert "subject" not in sparse
    assert "date" not in sparse


def test_list_owner_communications():
    report = list_owner_communications(_FakeGatherClient(), 1, 20)
    assert len(report.items) == 2
    assert report.summaries[0]["subject"] == "Assessment reminder"
    assert report.summaries[1] == {"id": 8, "type": "letter"}
    assert "communications=2" in report.summary()


def test_match_vendors_unique_ambiguous_and_exclusions():
    report = match_vendors_in_transactions(
        [
            {"id": 1, "description": "Payment to Acme Landscaping"},
            {"id": 2, "description": "Pool Pros and Water Works dual"},
            {
                "id": 3,
                "description": "ORIG CO NAME:SMUD",
                "transactionRule": {"name": "SMUD"},
            },
            {"id": 4, "description": "CITY OF SACRAMEN UTIL"},
            {"id": 5, "description": "no vendor here"},
        ],
        [
            {"id": 10, "name": "Acme Landscaping"},
            {"id": 11, "name": "Pool Pros"},
            {"id": 12, "name": "Water Works"},
        ],
    )
    assert report.unique_count == 1
    assert report.ambiguous_count == 1
    assert report.excluded_count == 2
    assert report.unmatched_count == 1
    unique = next(m for m in report.matches if m.unique)
    assert unique.matched_vendor_names == ["Acme Landscaping"]
    ambiguous = next(m for m in report.matches if len(m.matched_vendor_names) > 1)
    assert ambiguous.unique is False
    assert set(ambiguous.matched_vendor_names) == {"Pool Pros", "Water Works"}
    smud = next(m for m in report.matches if m.exclusion_reason == "smud")
    assert smud.excluded is True


def test_suggest_vendor_matches_uses_bill_payments():
    report = suggest_vendor_matches(_FakeGatherClient(), 1)
    assert report.unique_count >= 2  # Acme + Roof Co from bill-payments
    roof = next(
        m for m in report.matches if m.transaction_id == 104 and m.unique
    )
    assert roof.matched_vendor_names == ["Roof Co"]
    excluded = {m.exclusion_reason for m in report.matches if m.excluded}
    assert excluded == {"smud", "city_sacramento"}
    ambiguous = next(m for m in report.matches if m.transaction_id == 101)
    assert ambiguous.unique is False
