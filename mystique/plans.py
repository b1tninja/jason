"""The floor plans each developer offered.

The 2007 plan is the city's entitlement file P05-164 (staff report, Table 3):
six unit types on a complex of 92, forty-eight with two bedrooms and
forty-four with three, from 1,041 to 1,527 square feet. Only buildings 3 and
8 were built to it. The Watt plans are the December 2020 sales brochure,
which pairs each plan name with a stated area; the brochure calls every
figure approximate. A unit's plan is read from the assessor's living area
(``classify_plan``), and the assessor's figure is the one the reports use.

What the assessor measured on the 2007 buildings is not Table 3. Those two
buildings hold six as-built types: 1,064 (two bedrooms), 1,351 and 1,360
(three), 1,396 (two), 1,535 (two), and 1,579 (three) square feet. The plans
changed between the 2005 entitlement and construction, so a Table 3 name on a
2007 unit is the nearest proposed type, not the builder's own name, and the
1,535 two-bedroom type has no counterpart there and stays unmatched. Watt's
units match the brochure within a foot or two: 1,491 is Plan 1, 1,502 Plan 2,
1,696 or 1,697 Plan 3, 1,410 Plan 4A, and 1,326 Plan 4B.
"""

from jason.community.characteristics import FloorPlan

JOHN_LAING = "John Laing Homes"
WATT = "Watt Communities at Mystique"
_P05 = "P05-164 staff report, Table 3"
_BROCHURE = "Watt Floor Plans brochure, December 2020"

FLOOR_PLANS: tuple[FloorPlan, ...] = (
    FloorPlan("Unit 1", JOHN_LAING, 2, 1_041, 2, source=_P05),
    FloorPlan("Unit 2", JOHN_LAING, 3, 1_279, 2, source=_P05),
    FloorPlan("Unit 3", JOHN_LAING, 3, 1_312, 2, source=_P05),
    FloorPlan("Unit 4", JOHN_LAING, 2, 1_362, 2, source=_P05),
    FloorPlan("Unit 5", JOHN_LAING, 2, 1_421, 2, source=_P05),
    FloorPlan("Unit 6", JOHN_LAING, 3, 1_527, 2, source=_P05),
    FloorPlan("Plan 1", WATT, 3, 1_492, 2, baths=2.5, source=_BROCHURE),
    FloorPlan("Plan 2", WATT, 3, 1_502, 2, baths=2.5, source=_BROCHURE),
    FloorPlan("Plan 3", WATT, 3, 1_697, 2, baths=2.5, source=_BROCHURE),
    FloorPlan("Plan 4A", WATT, 2, 1_410, 3, baths=2.5, source=_BROCHURE),
    FloorPlan("Plan 4B", WATT, 2, 1_326, 3, baths=2.5, source=_BROCHURE),
)
