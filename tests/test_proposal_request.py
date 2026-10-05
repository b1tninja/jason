"""A proposal request to a life safety system's servicer, drafted from the inspection record (made-up records)."""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace

from jason.tasks import proposal_request as pr
from jason.tasks.inspections import Coverage, Period

AS_OF = date(2026, 10, 5)


def _row(name, authority, months=12):
    return SimpleNamespace(name=name, authority=authority, months=months, fixed=False,
                           cadence=lambda: f"every {months} months" if months != 12 else "every 1 year")


def _obligation(row, *, calendar=None, periods=(), counted_from=None):
    return SimpleNamespace(row=row, calendar=calendar, periods=tuple(periods), counted_from=counted_from, earlier=())


def _records(*obligations, servicer="Example Fire Protection, Inc.", not_read=()):
    system = SimpleNamespace(key="sprinklers-a", name="Fire sprinklers, building A", serves_label="building A",
                             servicer=servicer)
    return SimpleNamespace(as_of=AS_OF, community="Example Village HOA",
                           systems=(SimpleNamespace(system=system, obligations=tuple(obligations),
                                                    not_read=tuple(SimpleNamespace(name=n) for n in not_read)),))


ANNUAL = _row("Annual inspection and test", "19 CCR 904 (NFPA 25), form AES 2.1: valves, gauges, and alarms")
QUARTERLY = _row("Quarterly inspection", "19 CCR 904 (NFPA 25)", months=3)
GAUGES = _row("Gauges replaced or tested", "NFPA 25 5.3.2", months=60)
SAMPLE = _row("Sample test", "NFPA 25 5.3.1", months=120)


def test_each_need_is_read_from_the_record_in_order():
    records = _records(
        _obligation(SAMPLE, calendar={"next": "2027-11-15", "standing": "upcoming"}),
        _obligation(GAUGES, periods=[Period(date(2018, 3, 15), date(2023, 3, 14), Coverage.NOT_ON_FILE),
                                     Period(date(2023, 3, 15), date(2028, 3, 14), Coverage.NOT_YET_DUE)],
                    counted_from=date(2023, 3, 14)),
        _obligation(QUARTERLY),
        _obligation(ANNUAL, calendar={"next": "2024-03-14", "standing": "overdue", "lastDone": "2023-03-14"},
                    counted_from=date(2023, 3, 14)),
    )
    req = pr.request_for(records, "sprinklers-a")
    assert [(i.obligation, i.need) for i in req.items] == [
        ("Annual inspection and test", pr.Need.OVERDUE), ("Quarterly inspection", pr.Need.NO_RECORD),
        ("Gauges replaced or tested", pr.Need.NOT_ON_FILE)]
    assert req.items[0].why == "due 2024-03-14, now overdue; last done 2023-03-14 by our records"
    assert req.items[2].why == "no record on file for 2018-03-15 to 2023-03-14"
    assert req.last_on_file == date(2023, 3, 14)
    assert pr.request_for(records, "no-such-system") is None


def test_the_vendor_gets_the_citation_not_the_rows_summary():
    req = pr.request_for(_records(_obligation(ANNUAL, calendar={"next": "2024-03-14", "standing": "overdue"})),
                         "sprinklers-a")
    assert req.items[0].citation == "19 CCR 904 (NFPA 25), form AES 2.1"
    text = pr.draft(req, "office@example.com").message.text
    assert "19 CCR 904 (NFPA 25), form AES 2.1" in text and "valves, gauges" not in text


def test_due_soon_only_within_the_horizon_and_never_an_offer_alone():
    soon = _records(_obligation(ANNUAL, calendar={"next": "2026-12-01", "standing": "upcoming"}))
    assert [i.need for i in pr.request_for(soon, "sprinklers-a").items] == [pr.Need.DUE_SOON]
    assert pr.request_for(soon, "sprinklers-a", horizon=30).items == ()
    assert pr.offers(soon) == []
    overdue = _records(_obligation(ANNUAL, calendar={"next": "2024-03-14", "standing": "overdue"}))
    assert pr.offers(overdue) == [("sprinklers-a", 1)]


def test_the_draft_asks_for_reports_and_a_proposal_and_never_sends():
    records = _records(_obligation(ANNUAL, calendar={"next": "2024-03-14", "standing": "overdue",
                                                     "lastDone": "2023-03-14"}),
                       not_read=("Annual report 2023.pdf",))
    req = pr.request_for(records, "sprinklers-a")
    waiting = [{"last": "2025-06-18", "subject": "Annual inspection", "link": "https://mail.example/1"}]
    agreements = [{"name": "Inspection Proposal - Signed.pdf", "key": "file-proposal"}]
    plan = pr.draft(req, "office@example.com", waiting=waiting, agreements=agreements)
    m = plan.message
    assert m.to == ("office@example.com",)
    assert m.subject == "Request for proposal and reports: Fire sprinklers, building A, Example Village HOA"
    assert "fire sprinklers, building A, and for copies" in m.text           # the served buildings said once
    assert "no report for this system after 2023-03-14" in m.text
    assert "license number and classification" in m.text
    assert m.text.rstrip().endswith("Board of Directors, Example Village HOA")
    reminders = " ".join(plan.reminders)
    assert "board's decision" in reminders and "2025-06-18" in reminders and "A signed agreement" in reminders
    assert "Annual report 2023.pdf" in reminders
    assert pr.draft(req, "office@example.com", signer="Jane Example, Secretary").message.text.rstrip().endswith(
        "Jane Example, Secretary")


def test_recipients_put_the_contact_on_file_first_then_who_wrote_last():
    directory = {"vendors": [{"vendor": "Example Fire Protection, Inc.", "sender": "Example Fire Protection, Inc.",
                              "onFile": {"email": "office@example.com", "contactName": ""},
                              "people": [{"address": "pat@example.com", "names": ["Pat Example"], "last": "2024-01-02",
                                          "wroteUs": 3},
                                         {"address": "sam@example.com", "names": ["Sam Example"], "last": "2025-06-18",
                                          "wroteUs": 1},
                                         {"address": "office@example.com", "names": [], "last": "2026-01-01"}]}]}
    got = pr.recipients(directory, "Example Fire Protection, Inc.")
    assert [r.address for r in got] == ["office@example.com", "sam@example.com", "pat@example.com"]
    assert pr.recipients(directory, "Another Vendor") == []
