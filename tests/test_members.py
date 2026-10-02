from datetime import date

from jason.community.members import AGREES, MEMBER_NOT_TITLE, NO_MEMBER, TITLE_NOT_MEMBER, check_members, occupancies

UNIT = {
    "id": 606976,
    "title": "3031 MESMERIZING WALK",
    "owners": [
        {"membershipId": 1480827, "unitOccupancyId": 1316640, "deletedAt": None},
        {"membershipId": 1493670, "unitOccupancyId": 1316640, "deletedAt": None},
        {"membershipId": 900001, "unitOccupancyId": 649485, "deletedAt": None},
        {"membershipId": 900002, "unitOccupancyId": 649485, "deletedAt": "2025-01-01T00:00:00.000000Z"},
    ],
    "occupancies": [
        {"id": 1316640, "unitId": 606976, "fromDate": "2026-07-24T14:06:07.000000Z", "toDate": None},
        {"id": 649485, "unitId": 606976, "fromDate": "2024-01-14T01:42:08.000000Z", "toDate": "2026-07-24T14:06:07.000000Z"},
    ],
}
PEOPLE = {1480827: "Wren Halloway", 1493670: "Jasper Halloway", 900001: "Omar Pellam"}


def test_occupancies_list_each_period_with_its_members_oldest_first():
    found = occupancies([UNIT], PEOPLE)
    assert [(item.occupancy_id, item.from_date, item.to_date, item.members) for item in found] == [
        (649485, date(2024, 1, 14), date(2026, 7, 24), ("Omar Pellam",)),
        (1316640, date(2026, 7, 24), None, ("Wren Halloway", "Jasper Halloway")),
    ]
    assert found[-1].current and not found[0].current


def test_the_current_members_are_checked_against_the_newest_deed():
    periods = occupancies([UNIT], PEOPLE)
    owners = ("HALLOWAY WREN ADELE", "HALLOWAY JASPER EDMUND THORNE")
    found = check_members("20111700270016", "3031 MESMERIZING WALK", owners, periods)
    assert found.verdict == AGREES and found.since == date(2026, 7, 24)
    stale = check_members("20111700270016", "3031 MESMERIZING WALK", ("OMAR PELLAM LLC", "PELLAM OMAR"), periods)
    assert stale.verdict == f"{TITLE_NOT_MEMBER}; {MEMBER_NOT_TITLE}"
    assert stale.unmatched_owners == ("OMAR PELLAM LLC", "PELLAM OMAR")
    company = check_members("x", "y", ("AIRES BLOCK LLC",), occupancies([{**UNIT, "owners": [{"membershipId": 5, "unitOccupancyId": 1316640}]}], {5: "Aires Block LLC"}))
    assert company.verdict == AGREES
    trust = check_members("x", "y", ("HALLOWAY FAMILY TRUST", "HALLOWAY WREN TRUSTEE"), periods)
    assert trust.verdict == AGREES
    nobody = check_members("x", "y", owners, ())
    assert nobody.verdict == NO_MEMBER and nobody.unmatched_owners == owners
    tenant = check_members("x", "y", ("KESTREL ABBOTT C",), periods)
    assert tenant.verdict == f"{TITLE_NOT_MEMBER}; {MEMBER_NOT_TITLE}"
