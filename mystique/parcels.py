"""Assessor parcels for Mystique.

``UNITS`` is the membership roll. Those rows on the secured roll are
residential. ``COMMON_AREAS`` are the association parcels on the same map
page: land use ``AQ000A``, owned by the association, with no structure value.
The association is taxed on the common-area parcels.
"""

UNITS: tuple[str, ...] = (
    "20111700220010",
    "20111700220011",
    "20111700220012",
    "20111700220013",
    "20111700220014",
    "20111700220015",
    "20111700220016",
    "20111700230023",
    "20111700230022",
    "20111700230021",
    "20111700230020",
    "20111700230019",
    "20111700230018",
    "20111700230017",
    "20111700230016",
    "20111700230015",
    "20111700230014",
    "20111700240001",
    "20111700240002",
    "20111700240003",
    "20111700240004",
    "20111700240005",
    "20111700240006",
    "20111700240007",
    "20111700240008",
    "20111700240009",
    "20111700240010",
    "20111700240011",
    "20111700240012",
    "20111700250023",
    "20111700250022",
    "20111700250021",
    "20111700250020",
    "20111700250019",
    "20111700250018",
    "20111700250017",
    "20111700250016",
    "20111700250015",
    "20111700250014",
    "20111700260014",
    "20111700260015",
    "20111700260016",
    "20111700260017",
    "20111700260018",
    "20111700260019",
    "20111700260020",
    "20111700260021",
    "20111700260022",
    "20111700260023",
    "20111700270023",
    "20111700270022",
    "20111700270021",
    "20111700270020",
    "20111700270019",
    "20111700270018",
    "20111700270017",
    "20111700270016",
    "20111700270015",
    "20111700270014",
    "20111700280014",
    "20111700280015",
    "20111700280016",
    "20111700280017",
    "20111700280018",
    "20111700280019",
    "20111700280020",
    "20111700280021",
    "20111700280022",
    "20111700280023",
    "20111700170001",
    "20111700170002",
    "20111700170003",
    "20111700170004",
    "20111700170005",
    "20111700170006",
    "20111700170007",
    "20111700170008",
    "20111700170009",
    "20111700170010",
    "20111700170011",
    "20111700170012",
)

from jason.community.base import AssociationCommonArea, CostCenter, CostCenterRule
from jason.community.symbols import Building

# The Condominium Plan's Association Common Areas (its legend: "A.C.A. ASSOCIATION COMMON AREA"), owned in fee by the
# association and holding each building's structure (CC&Rs, Common Area (a)). Each annexation annexes one: "Association
# Common Area designated A.C.A. 3, Condominium Common Area designated C.C.A. 3, Units 21 through 32" (phase 2). The number
# is the building's. The parcel is the common-area parcel of the building's assessor block (the City's storm-drain accounts
# bill ACA 3 at 201-1170-024-0013 and ACA 8 at 201-1170-017-0013). ACA 3 and ACA 8, built by WL Homes in 2008, are the
# "Phases 1 and 2 Property", a separate cost center from Watt's annexed buildings (each Watt annexation, section 1.3(d)).
# Confirmed by the board 2026-09-29.
ASSOCIATION_COMMON_AREAS: tuple[AssociationCommonArea, ...] = (
    AssociationCommonArea(1, "20111700220017", Building.BLDG_1, 3, (1, 7), "Watt Communities", CostCenter.ANNEXED),
    AssociationCommonArea(2, "20111700230024", Building.BLDG_2, 8, (8, 17), "Watt Communities", CostCenter.ANNEXED),
    AssociationCommonArea(3, "20111700240013", Building.BLDG_3, 2, (21, 32), "WL Homes", CostCenter.PHASES_1_AND_2),
    AssociationCommonArea(4, "20111700250024", Building.BLDG_4, 7, (18, 27), "Watt Communities", CostCenter.ANNEXED),
    AssociationCommonArea(5, "20111700260024", Building.BLDG_5, 6, (28, 37), "Watt Communities", CostCenter.ANNEXED),
    AssociationCommonArea(6, "20111700270024", Building.BLDG_6, 5, (38, 47), "Watt Communities", CostCenter.ANNEXED),
    AssociationCommonArea(7, "20111700280024", Building.BLDG_7, 4, (48, 57), "Watt Communities", CostCenter.ANNEXED),
    AssociationCommonArea(8, "20111700170013", Building.BLDG_8, 1, (81, 92), "WL Homes", CostCenter.PHASES_1_AND_2),
)

# Each Watt annexation, section 1.3: a Regular Assessment is a General Assessment Component (the declaration's budgeted
# expenses, shared under section 6.5(b)) plus the unit's cost center component, "allocated and assessed equally among the
# Units within" that cost center. The Annexed Property Cost Center carries "the maintenance, repair, replacement and
# insurance of Common Area building Improvements within the Annexed Property" (1.3(d)(iii)). The Phases 1 and 2 Property
# Cost Center carries "the maintenance, repair, replacement and insurance of Common Area building Improvements within
# the Phases 1 and 2 Property" (1.3(d)(ii), in the Phase 3 annexation and its amendment; read from the library's text
# 2026-09-29). Phases 6 and 7 cite 1.3(d)(ii) in 1.3(a)(ii) but their 1.3(d) goes from (i) to (iii); the Phase 4, 5, and 8
# copies lack those pages. The reason (1.3(d)(i)): the WL Homes buildings' components are older,
# their defect period has expired, and the association has funded their reserves. Confirmed by the board 2026-09-29.
COST_CENTERS: tuple[CostCenterRule, ...] = (
    CostCenterRule(CostCenter.ANNEXED, "maintenance, repair, replacement and insurance of Common Area building Improvements within the "
                   "Annexed Property", "equally among the Units within the Annexed Property", "Declarations of Annexation, phases 3-8, 1.3(b)(ii), (d)(iii)"),
    CostCenterRule(CostCenter.PHASES_1_AND_2, "maintenance, repair, replacement and insurance of Common Area building Improvements within the "
                   "Phases 1 and 2 Property", "equally among the Units within the Phases 1 and 2 Property",
                   "Declaration of Annexation, phase 3 (and its amendment), 1.3(b)(ii), (d)(ii)"),
)

COMMON_AREAS: tuple[str, ...] = (
    "20111700170013",
    "20111700180000",
    "20111700190000",
    "20111700220017",
    "20111700230024",
    "20111700240013",
    "20111700250024",
    "20111700260024",
    "20111700270024",
    "20111700280024",
)
