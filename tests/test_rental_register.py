"""The rental register: managers recognized by lease, other contact, and email; tenants beside the unit's other
contacts; and the 4.15 actions that follow."""

from datetime import date

from jason.community.sources import Sender, SourceKind
from jason.community.tags import PayhoaTag, TagPurpose, TagScope
from jason.tasks.leases import Lease
from jason.tasks.rental_register import manager_threads, markdown, register

TODAY = date(2026, 10, 1)
TAGS = (PayhoaTag("Rental", TagScope.UNIT, TagPurpose.OCCUPANCY, "Rented out"),
        PayhoaTag("Rental Approved", TagScope.UNIT, TagPurpose.RENTAL_APPROVAL),
        PayhoaTag("Property Manager", TagScope.MEMBER, TagPurpose.PROPERTY_MANAGER))
SENDERS = (Sender("Belong", SourceKind.PROPERTY_MANAGER, ("BELONG",), domains=("belonghome.com",)),)
UNITS = [{"id": 1, "label": "999 MAGICAL WALK", "tags": [{"tag": "Rental"}], "owners": [{"membershipId": 9}]},
         {"id": 2, "label": "998 MACON DR", "tags": [], "owners": [{"membershipId": 8}]}]
PEOPLE = {9: {"name": "Avery Owner", "tags": set()}, 8: {"name": "Pat Seller", "tags": set()}}
MESSAGES = [
    {"threadId": "t1", "domains": ["belonghome.com"], "parties": ["owner of 999 MAGICAL WALK"], "subject": "Parking pass"},
    {"threadId": "t2", "domains": ["exclusiverealty.com"], "parties": ["owner of 998 MACON DR"], "subject": "Solar transfer"},
    {"threadId": "t3", "domains": ["acmepropertymanagement.com"], "parties": [], "subject": "998 Macon Dr gate"},
]


def test_a_directory_manager_is_tied_to_a_unit_by_its_threads_and_a_look_alike_is_only_a_candidate():
    named, candidates = manager_threads(MESSAGES, SENDERS, [u["label"] for u in UNITS])
    assert named == {"999 MAGICAL WALK": {"Belong": 1}}
    assert candidates == {"998 MACON DR": {"acmepropertymanagement.com": 1}}     # a realty is not even a candidate


def test_the_register_lists_tenants_managers_and_the_actions_a_running_lease_supports():
    lease = Lease("lease.pdf", "drive", unit_address="999 MAGICAL WALK", start="2025-11-28", end="2026-11-27",
                  manager_company="Belong, Inc.", tenants=["Eli Sample", "Ira Sample"])
    contacts = {1: [{"name": "Eli Sample"}, {"name": "Lea Former"}]}
    rows, _ = register(UNITS, PEOPLE, contacts, [lease], TAGS, MESSAGES, SENDERS, TODAY)
    row = next(r for r in rows if r.unit == "999 MAGICAL WALK")
    assert row.rental and not row.approved and row.lease_runs is True
    assert row.tenants_on_lease_unlisted == ["Ira Sample"]
    manager = row.managers[0]
    assert "Belong" in manager.name and manager.how[0].startswith("lease") and "email: 1 thread" in manager.how
    actions = " | ".join(row.actions)
    assert "no approval on file" in actions and "add as other contacts: Ira Sample" in actions
    assert "may have left" in actions and "Lea Former" in actions and "list the manager as an other contact" in actions
    assert not any(r.unit == "998 MACON DR" for r in rows)                        # not rented, no lease, no manager
    text = "\n".join(markdown(rows, {}, today=TODAY))
    assert "@" not in text                                                          # names only


def test_an_ended_lease_or_a_sale_asks_before_anything_is_listed():
    lease = Lease("old.pdf", "drive", unit_address="999 MAGICAL WALK", start="2025-08-15", end="2026-07-31",
                  month_to_month=True, manager_company="Belong, Inc.", tenants=["Bree Example"])
    rows, _ = register(UNITS, PEOPLE, {}, [lease], TAGS, [], SENDERS, TODAY,
                       deeds={"999 MAGICAL WALK": date(2026, 8, 17)})
    actions = " | ".join(rows[0].actions)
    assert "add as other contacts" not in actions and "confirm with the owner" in actions
    assert "changed hands 2026-08-17" in actions and "confirm the manager with the owner" in actions
