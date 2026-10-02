"""The roof inspection model, on synthetic excerpts in RoofChecks' two layouts.

The job numbers, inspectors, license, counts, and prices are made up. The public reports and reserve components are a
fake slice of the specification: building 8 sold in 2007 (phase 1), building 1 in 2020 (phase 3).
"""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace

from jason.community.document_models import ModelContext, Severity, read
from jason.community.models.inspections_roof import RoofInspectionModel, read_sections
from jason.community.symbols import Building, ComponentMajor, CostCenter, DocumentKind

TODAY = date(2026, 9, 29)


class FakeCommunity:
    def public_reports(self):
        return (SimpleNamespace(building=Building.BLDG_8, phase=1, first_conveyance=date(2007, 11, 15), opened=date(2007, 9, 28), issued=None),
                SimpleNamespace(building=Building.BLDG_1, phase=3, first_conveyance=date(2020, 2, 28), opened=None, issued=None))

    def reserve_components(self):
        return (SimpleNamespace(cost_center=CostCenter.PHASE_1_AND_2, major=ComponentMajor.ROOFING,
                                description="660 - Pitched: Tile 160 Squares- Buildings", useful_life_years=30, last_completed_year=2007),
                SimpleNamespace(cost_center=CostCenter.PHASE_3_TO_8, major=ComponentMajor.ROOFING,
                                description="670 - Pitched: Tile 730 Squares- Buildings", useful_life_years=30, last_completed_year=2020))


def ctx(name: str = "") -> ModelContext:
    return ModelContext(community=FakeCommunity(), today=TODAY, name=name)


# The older layout (OCR of a scanned estimate): roof info, findings, repairs, and a subtotal for each building.
PER_BUILDING = """NORTH AMERICAN
HOME SERVICES ROOFCHECKS
ESTIMATE
For:
Mystique Community Association
Job ID: 2300-1111111-2222
3000 Macon Drive
Date:
07/01/2023
This estimate is based on the visual roof inspection conducted at this property in accordance with the
inspection service contract.
Proposed By:
Pat Roofer
ROOF INFO: Building 8
Type:
Layers:
Estimated Age:
Est. Life Remaining:
| Roof Pitch:
Monier Flat Tile
1
16 yrs
30+ yrs
4/12
ROOF FINDINGS: Building 8
- Roof has been inspected via drone, these inspections are limited to visual surface damage only.
- Broken tiles noted.
- Debris noted to be accumulating in valley. Debris build up is believed to be due to
pigeon nesting occurring under solar panels.
- Roof under solar panels could not be inspected, therefore condition of roof unknown.
A complete set of roof pictures is attached as a PDF with the report
ROOF REPAIRS: Building 8
- Replace 4 broken field tiles on the upper roof level.
- Using the 2 spare field tiles, replace the 2 broken tiles at the left side.
- Seal 12 joints on the upper roof level.
- Remove tiles around (2) valley(s) (~30ft) with noted debris and expose metal.
We hereby propose to furnish materials and labor complete in accordance with above specifications for the sum of:
SUBTOTAL:
$1,200
To schedule repairs please contact North American Home Services Office
10. Contractor's License Number: 123456
ROOF INFO: Building 1
Type:
Layers:
Estimated Age:
Est. Life Remaining:
| Roof Pitch:
Monier Flat Tile
1
16 yrs
30+ yrs
4/12
ROOF FINDINGS: Building 1
- Slipped/loose tiles noted.
- Roof under solar panels could not be inspected, therefore condition of roof unknown.
ROOF REPAIRS: Building 1
- Reset and secure 3 slipped/loose tiles on the upper roof level.
We hereby propose to furnish materials and labor complete in accordance with above specifications for the sum of:
SUBTOTAL:
$300
To schedule repairs please contact North American Home Services Office
"""

# The newer layout (text PDF): one roof info block, findings and repairs per building, one subtotal.
ONE_PRICE = """For:  Mystique Community Association
      3000 Macon Drive
                                                                         ESTIMATE
                                                      Job ID: 2600-3333333-4444
                                                        Date: 01/05/2026
     This estimate is based on the visual roof inspection conducted at this property in accordance with the
Proposed By: Sam Shingle
ROOF INFO:        Layers:             Estimated Age:  Est. Life Remaining:  Roof Pitch:
Type:             1                   18 yrs          30+ yrs               4/12
Tile
ROOF FINDINGS: BUILDING 8
- 2 Broken tiles noted on the roof
- RoofChecks does not offer repairs for metal roofs. We recommend to contact a metal roof specialist for further
evaluation of metal roof sections.
- Roof inspection was completed with a drone, drone inspections are a limited visual inspection of the roof.
ROOF FINDINGS: BUILDING 1
- 5 Slipped tiles noted on the roof
ROOF REPAIRS: BUILDING 8
- Remove and replace 2 broken tiles on the roof
ROOF REPAIRS: BUILDING 1
- Reset and secure 5 slipped tiles on the roof
We hereby propose to furnish materials and labor complete in accordance with above specifications for the sum of:
SUBTOTAL:  $900
                             To schedule repairs please contact the Good Life Inspections Office
"""

CHANGE_ORDER = """ROOFCHECKS
Job ID: 2300-1111111-2222
Date:
12/01/2023
Proposed By:
Lee Framer
ROOF FINDINGS:
- Water damaged sheathing found during replacement of damaged underlayment.
ROOF REPAIRS:
- Building 8: Replace up to 20 ft sq of damaged sheathing near sidewall.
- Building 1: Replace up to 10 ft sq of damaged sheathing near valley.
We hereby propose to furnish materials and labor complete in accordance with above specifications for the sum of:
SUBTOTAL:
$800
To schedule repairs please contact North American Home Services Office
visual roof inspection
"""


def codes(reading):
    return {f.code: f for f in reading.findings}


def test_per_building_layout():
    reading = read(DocumentKind.INSPECTION_REPORT, PER_BUILDING, ctx())
    assert reading and reading.model == RoofInspectionModel.name and reading.complete
    r = reading.record
    assert (r.firm, r.license, r.job_id, r.dated, r.inspector) == ("North American Home Services", "123456", "2300-1111111-2222",
                                                                    date(2023, 7, 1), "Pat Roofer")
    assert [s.building for s in r.sections] == [Building.BLDG_8, Building.BLDG_1]
    eight, one = r.sections
    assert (eight.covering, eight.stated_age_years, eight.stated_life_remaining, eight.pitch) == ("Monier Flat Tile", 16, "30+ yrs", "4/12")
    assert (eight.subtotal, one.subtotal, r.total) == (120000, 30000, 150000)
    assert (eight.tiles_replaced, eight.joints_sealed, eight.valleys_cleaned, one.tiles_reset) == (6, 12, 2, 3)
    assert eight.debris and eight.not_inspected_under_solar and not one.debris
    assert not any("drone" in f for f in eight.findings), "the drone disclaimer is how, not what"


def test_ages_against_the_public_reports_and_reserve_study():
    found = codes(read(DocumentKind.INSPECTION_REPORT, PER_BUILDING, ctx()))
    age = found["stated-roof-age"]
    assert "16 years for every building" in age.message and "building 1 to 2020 (about 3 years)" in age.message
    assert "building 8" not in age.message, "building 8 was about 16 in 2023"
    life = found["life-remaining-vs-reserve-study"]
    assert "building 8" in life.message and "2037 (14 years)" in life.message and life.severity is Severity.INFO
    assert found["not-inspected-under-solar"].message.startswith("the roof under the solar panels was not inspected on buildings 8, 1")
    assert "license-not-in-text" not in found


def test_one_price_layout():
    reading = read(DocumentKind.INSPECTION_REPORT, ONE_PRICE, ctx())
    r = reading.record
    assert (r.firm, r.job_id, r.dated, r.inspector, r.total) == ("Good Life Inspections", "2600-3333333-4444", date(2026, 1, 5), "Sam Shingle", 90000)
    assert [(s.building, s.stated_age_years, s.subtotal) for s in r.sections] == [(Building.BLDG_8, 18, None), (Building.BLDG_1, 18, None)]
    assert (r.sections[0].tiles_replaced, r.sections[1].tiles_reset) == (2, 5)
    found = codes(reading)
    assert found["metal-roof-referral"].message.startswith("the standing-seam metal sections on buildings 8")
    assert found["license-not-in-text"].authority == "BPC 7030.5"
    assert "drone-limited" in found


def test_change_order_by_building():
    reading = read(DocumentKind.INSPECTION_REPORT, CHANGE_ORDER, ctx("3000 Macon Drive Change Order.pdf"))
    r = reading.record
    assert r.change_order and r.total == 80000 and r.firm == "North American Home Services"
    repairs = {s.building: s.repairs for s in r.sections if s.building}
    assert repairs == {Building.BLDG_8: ("Replace up to 20 ft sq of damaged sheathing near sidewall.",),
                       Building.BLDG_1: ("Replace up to 10 ft sq of damaged sheathing near valley.",)}
    assert "license-not-in-text" not in codes(reading), "a change order rides on the estimate's license"


def test_not_a_roof_report():
    assert RoofInspectionModel().parse("Fire Alarm Inspection Report\nInspection Date: 01/01/2026", ctx()) is None
    sections, whole = read_sections("nothing here")
    assert sections == [] and whole is None
