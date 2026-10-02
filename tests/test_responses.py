import json
import sqlite3
from datetime import date
from types import SimpleNamespace

import pytest

from jason.community.responses import ClockSource, ResponseKind, ResponseRule, classify
from jason.tasks import responses as task


@pytest.mark.parametrize("form,text,kind", [
    ("Architectural Request", "Install solar panels on my roof", ResponseKind.SOLAR),
    ("Architectural Request", "New front door color", ResponseKind.ARCHITECTURAL),
    ("General Request", "I would like to inspect copies of the board minutes and the budget", ResponseKind.RECORDS),
    ("General Request", "Please send the resale disclosure package for our sale", ResponseKind.RESALE),
    ("General Request", "We are in escrow; the appraiser needs the HOA phone number", ResponseKind.QUESTION),
    ("Maintenance Request", "Selling my home, in escrow; the inspection found a loose gutter", ResponseKind.MAINTENANCE),
    ("General Request", "Requesting a payment plan for my balance", ResponseKind.PAYMENT_PLAN),
    ("General Request", "Noise complaint about the unit above", ResponseKind.COMPLAINT),
    ("Other Form", "hello", ResponseKind.OTHER),
    ("", "Solar question 2", ResponseKind.OTHER),                         # a mention, not an application
    ("", "Request to install an EV charger in my garage", ResponseKind.EV_CHARGER),
    ("", "Re: Courtesy Notice: Noise and Parking Violations", ResponseKind.OTHER),   # a reply to our own notice
    ("", "Offer to meet and confer", ResponseKind.DISPUTE),
])
def test_classify(form, text, kind):
    assert classify(form, text)[0] is kind


def test_clocks_from_the_statute_the_documents_and_a_policy():
    records = ResponseRule(ResponseKind.RECORDS, ClockSource.STATUTE, notice="records-current-year", authority="CIV 5210")
    due, words = task.due_day(records, date(2026, 10, 2))            # a Friday
    assert due == date(2026, 10, 16) and "10 business days" in words  # ten weekdays later
    rental = ResponseRule(ResponseKind.RENTAL, ClockSource.DOCUMENTS, days=30, authority="CC&Rs 1.1")
    assert task.due_day(rental, date(2026, 10, 2))[0] == date(2026, 11, 1)
    policy = ResponseRule(ResponseKind.MAINTENANCE, ClockSource.POLICY, days=2, business_days=True)
    assert task.due_day(policy, date(2026, 10, 2))[0] == date(2026, 10, 6)


def test_standing():
    assert task._standing(date(2026, 10, 10), date(2026, 10, 9), date(2026, 10, 20)) == "answered on time"
    assert task._standing(date(2026, 10, 10), date(2026, 10, 12), date(2026, 10, 20)) == "answered late (2 days)"
    assert task._standing(date(2026, 10, 10), None, date(2026, 10, 12)) == "OVERDUE (2 days)"
    assert task._standing(date(2026, 10, 10), None, date(2026, 10, 7)) == "due soon"


def _db(tmp_path, rows):
    with sqlite3.connect(tmp_path / "payhoa.db") as c:
        c.execute("CREATE TABLE units (id INTEGER, label TEXT)")
        c.execute("INSERT INTO units VALUES (1, '100 EXAMPLE WALK')")
        c.execute("CREATE TABLE requests (id INTEGER, form_name TEXT, unit_id INTEGER, status TEXT, created_at TEXT, raw_json TEXT)")
        for rid, form, status, created, title, comments, completed in rows:
            raw = {"answers": [{"question": {"label": "Title"}, "answer": title}, {"question": {"label": "Message"}, "answer": ""}],
                   "comments": comments, "completionDate": completed, "updatedAt": completed or created}
            c.execute("INSERT INTO requests VALUES (?,?,?,?,?,?)", (rid, form, 1, status, created, json.dumps(raw)))


def test_an_acknowledgment_promises_a_date_only_where_the_law_or_documents_set_one():
    received = date(2026, 10, 2)
    records = ResponseRule(ResponseKind.RECORDS, ClockSource.STATUTE, notice="records-current-year", authority="CIV 5210")
    due, clock = task.due_day(records, received)
    h = task.Handled({"id": 1}, ResponseKind.RECORDS, "", records, received, due, clock, None, None, None, None, "open")
    text = task.acknowledgment(h, SimpleNamespace(name="Example Association"))
    assert "October 2, 2026" in text and "Under CIV 5210" in text and "October 16, 2026" in text
    assert text.endswith("- Example Association")
    policy = ResponseRule(ResponseKind.MAINTENANCE, ClockSource.POLICY, days=10, business_days=True)
    h = task.Handled({"id": 2}, ResponseKind.MAINTENANCE, "", policy, received, date(2026, 10, 16), "", None, None, None,
                     None, "open")
    assert "October 16" not in task.acknowledgment(h, SimpleNamespace(name="X"))


def test_handle_judges_the_first_response_not_the_closing(tmp_path):
    _db(tmp_path, [
        (1, "Maintenance Request", "complete", "2026-09-01T17:00:00Z", "Leak",
         [{"createdAt": "2026-09-03T17:00:00Z", "isAdmin": True}], "2026-10-30T17:00:00Z"),
        (2, "General Request", "pending", "2026-09-01T17:00:00Z", "Inspect copies of the minutes", [], None),
    ])
    community = SimpleNamespace(topic_rules=lambda: (), response_rules=lambda: (
        ResponseRule(ResponseKind.MAINTENANCE, ClockSource.POLICY, days=10, business_days=True, assignment="maintenance",
                     acknowledge_days=2),))
    found = {h.request["id"]: h for h in task.handle(community, tmp_path, today=date(2026, 10, 2))}
    assert found[1].answered == date(2026, 9, 3) and found[1].closed == date(2026, 10, 30)
    assert found[1].standing == "answered on time"
    assert found[2].kind is ResponseKind.RECORDS and found[2].standing.startswith("OVERDUE")
    assert task.summary(list(found.values()))["onTime"] == {"maintenance request": 1}
