"""Public reports from the Membership Buildings tab.

Each row is one Bureau file and the phase it opened. Building number and
phase number are different sequences. The monthly assessment is integer cents.
Phase 1 leaves that amount blank.
"""

from datetime import date

from jason.community.reports import HeldUnits, PhaseFile, PlanBlock, PublicReport
from jason.community.symbols import Building

REPORTS: tuple[PublicReport, ...] = (
    PublicReport(
        "130654SA",
        Building.BLDG_8,
        1,
        12,
        date(2007, 11, 15),
        "John Laing Homes",
        opened=date(2007, 9, 28),
        issued=date(2007, 9, 26),
    ),
    PublicReport(
        "132246SA",
        Building.BLDG_3,
        2,
        12,
        date(2008, 2, 29),
        "John Laing Homes",
        annexation=date(2007, 12, 17),
        assessment_cents=28_500,
        issued=date(2008, 2, 1),
    ),
    # The declaration numbers Watt's phases by annexation. Phase 3 (201912201433, recorded
    # 2019-12-20) annexes units 1 through 7 and A.C.A. 1: building 1, whose first sale on
    # 2020-02-28 could not precede its annexation. Phase 4 (202003021215, recorded 2020-03-02)
    # annexes units 48 through 57 and A.C.A. 7: building 7, and its Bureau file 160779SA says
    # "units 48 through 57 of building no. 7". An earlier pass had the two phases crossed.
    PublicReport(
        "154410SA",
        Building.BLDG_1,
        3,
        7,
        date(2020, 2, 28),
        "Watt Communities at Mystique",
        annexation=date(2019, 12, 20),
        assessment_cents=27_500,
    ),
    PublicReport(
        "160779SA",
        Building.BLDG_7,
        4,
        10,
        date(2020, 4, 20),
        "Watt Communities at Mystique",
        annexation=date(2020, 3, 2),
        assessment_cents=27_500,
    ),
    PublicReport(
        "163389SA",
        Building.BLDG_6,
        5,
        10,
        date(2021, 2, 24),
        "Watt Communities at Mystique",
        annexation=date(2020, 4, 28),
        assessment_cents=29_500,
    ),
    PublicReport(
        "164002SA",
        Building.BLDG_5,
        6,
        10,
        date(2021, 11, 30),
        "Watt Communities at Mystique",
        annexation=date(2020, 7, 17),
        assessment_cents=29_500,
    ),
    PublicReport(
        "165814SA",
        Building.BLDG_4,
        7,
        10,
        date(2021, 12, 29),
        "Watt Communities at Mystique",
        annexation=date(2021, 1, 8),
        assessment_cents=29_500,
    ),
    PublicReport(
        "165817SA",
        Building.BLDG_2,
        8,
        10,
        date(2022, 3, 18),
        "Watt Communities at Mystique",
        annexation=date(2021, 1, 8),
        assessment_cents=29_500,
        related=(
            PhaseFile(
                "Bond Release Letter Portisol at Mystique Phase 8 (RE 643J).pdf",
                "1GqV-sOxaZb6E039XW-J1VIfnRa3b1XeN",
                "bond_release",
            ),
        ),
    ),
)

# Buildings 3 and 8 were on the 2007 plan of 92 units. Subparcel 0001 of block
# 024 is unit 21, and subparcel 0001 of block 017 is unit 81: the John Laing
# deeds print the unit in the legal description (unit 86 is 017-0006, unit 88 is
# 017-0008, unit 91 is 017-0011) and the parent parcel, not the unit parcel, in
# the header. The parent parcels are the numbers those headers print.
#
# Watt then numbered its six buildings 1 through 57 (building 1 is 1 to 7,
# building 2 is 8 to 17, building 4 is 18 to 27, building 5 is 28 to 37,
# building 6 is 38 to 47, building 7 is 48 to 57) without noticing that
# building 3 already held 21 to 32. Units 21 to 32 therefore name a building 3
# unit and a building 4 or 5 unit alike, so no Watt building is a plan block,
# and a unit number places a deed only with the John Laing parent parcel.
PLAN_BLOCKS: tuple[PlanBlock, ...] = (
    PlanBlock(Building.BLDG_3, "024", 21, 12, ("20111700160000",)),
    PlanBlock(Building.BLDG_8, "017", 81, 12, ("20111700040000", "20111700190000")),
)

# Watt's numbering. The assessor started each of these blocks at subparcel
# 0010 or 0014, and the unit numbers run down the street numbers. No parent
# parcel is pinned, so none of these blocks places a deed by unit number.
WATT_BLOCKS: tuple[PlanBlock, ...] = (
    PlanBlock(Building.BLDG_1, "022", 1, 7, (), 10, "Watt numbering"),
    PlanBlock(Building.BLDG_2, "023", 8, 10, (), 14, "Watt numbering"),
    PlanBlock(Building.BLDG_4, "025", 18, 10, (), 14, "Watt numbering"),
    PlanBlock(Building.BLDG_5, "026", 28, 10, (), 14, "Watt numbering"),
    PlanBlock(Building.BLDG_6, "027", 38, 10, (), 14, "Watt numbering"),
    PlanBlock(Building.BLDG_7, "028", 48, 10, (), 14, "Watt numbering"),
)

# Every block, both numberings. This is what a unit number is read against.
UNIT_BLOCKS: tuple[PlanBlock, ...] = PLAN_BLOCKS + WATT_BLOCKS

# The receiver's deed to David Pick. These four building 3 units were still held.
HELD_UNITS: tuple[HeldUnits, ...] = (
    HeldUnits("201010121565", date(2010, 10, 12), Building.BLDG_3, (25, 26, 27, 30)),
)
