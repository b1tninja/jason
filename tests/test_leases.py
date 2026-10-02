"""The leases: which are running, and what they suggest beside PayHOA's owners and other contacts."""

from datetime import date

from jason.tasks.leases import Lease, _iso, lease_files, proposals

TODAY = date(2026, 10, 1)
UNITS = [{"id": 1, "label": "3091 MAGICAL WALK"}, {"id": 2, "label": "5699 WHIMSICAL LN"}]


def test_a_lease_runs_until_its_end_and_after_that_only_a_person_can_say():
    assert Lease("a", "", end="2026-11-27").current(TODAY) is True
    assert Lease("a", "", end="2025-02-23").current(TODAY) is False
    assert Lease("a", "", end="2025-02-23", month_to_month=True).current(TODAY) is None
    assert Lease("a", "").current(TODAY) is None


def test_dates_are_read_in_the_forms_leases_print():
    assert _iso("11/16/2025") == _iso("November 16, 2025") == _iso("2025-11-16") == "2025-11-16"


def test_applications_and_screening_reports_are_never_lease_files():
    files = [{"path": "My Drive/R/Copy of Lease Agreement (File responses)/Lease1.pdf", "name": "Lease1.pdf"},
             {"path": "My Drive/R/Copy of Lease Agreement (File responses)/A - Application.pdf", "name": "A - Application.pdf"},
             {"path": "My Drive/R/Proof of Credit Check (File responses)/Report.pdf", "name": "Report.pdf"}]
    assert [f["name"] for f in lease_files(files)] == ["Lease1.pdf"]


def test_a_current_lease_lists_its_tenants_and_manager_and_an_ended_one_asks():
    current = Lease("cur.pdf", "", unit_address="3091 MAGICAL WALK", start="2025-11-28", end="2026-11-27",
                    manager_company="Belong, Inc.", tenants=["Elias Varrow", "Ilsa Varrow", "Noor Quennell"])
    ended = Lease("old.pdf", "", unit_address="5699 WHIMSICAL LN", start="2025-08-15", end="2026-07-31",
                  month_to_month=True, manager_company="Allegiance Property Management", tenants=["Bree Ostrander"])
    contacts = {1: [{"name": "Elias Varrow"}]}
    owners = {1: ["Noor Quennell"], 2: ["Edwin Fenwright"]}
    out = proposals([current, ended], UNITS, contacts, owners, TODAY, deeds={"5699 WHIMSICAL LN": date(2026, 8, 17)})
    kinds = {(p.unit, p.kind, p.who) for p in out}
    assert ("3091 MAGICAL WALK", "add other contact", "Ilsa Varrow") in kinds
    assert not any(p.who == "Elias Varrow" for p in out)                  # already an other contact
    assert not any(p.who == "Noor Quennell" and "contact" in p.kind for p in out)   # the owner is no tenant contact
    assert ("3091 MAGICAL WALK", "manager contact", "Belong, Inc.") in kinds
    assert ("3091 MAGICAL WALK", "ask: manager's role", "Noor Quennell") in kinds   # the owner says what the manager gets
    assert ("5699 WHIMSICAL LN", "ask: tenant may remain", "Bree Ostrander") in kinds
    sale = next(p for p in out if p.who == "Bree Ostrander")
    assert "changed hands 2026-08-17" in sale.why
    assert ("5699 WHIMSICAL LN", "ask: manager's role", "Edwin Fenwright") in kinds
