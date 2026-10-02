"""The developer's shared rooftop solar and who leases it.

Watt sold each unit of phases 3 to 8 (buildings 1, 2, 4, 5, 6, 7) with a
share of the building's SunPower system. The buyer chose at closing to
purchase the share or to lease it. A leased share carries a UCC fixture
filing the lease fund records against the buyer, and a resale must carry
the lease to the next owner or buy it out. The association keeps no roster
of who chose which; the recorder's index is the record.

The lease funds are SunPower's: Ultralight Residential Solar and Ultralight
2 Residential Solar each signed lease servicing agreements with SunPower
Capital Services (2019 and 2020), and Dorado 1 Residential Solar did in
March 2022. In SunPower's 2024 bankruptcy the leases and their servicing
went to SunStrong Management; Complete Solaria bought the new-homes and
dealer businesses and the SunPower name, not the leases. A lease question
therefore goes to SunStrong, not to the company now trading as SunPower.
Sources: SunPower's bankruptcy docket (In re SunPower Corporation, D. Del.
2024, docket 962), SunPower's 2024 acquisition notice, and Complete
Solaria's 2024 annual report.
"""

from jason.community.solar import SolarProgram
from jason.community.symbols import Building

SOLAR_PROGRAM = SolarProgram(
    name="SunPower shared rooftop solar, leased or purchased at the developer closing",
    developer="Watt Communities at Mystique",
    buildings=(Building.BLDG_1, Building.BLDG_2, Building.BLDG_4, Building.BLDG_5, Building.BLDG_6, Building.BLDG_7),
    lessors=(
        "ULTRALIGHT RESIDENTIAL SOLAR LLC",
        "ULTRALIGHT RESIDENTIAL SOALR LLC",
        "ULTRALIGHT 2 RESIDENTIAL SOLAR LLC",
        "ULTRALIGHT 2 SOLARBLOOM LLC",
        "DORADO I RESI SOLAR LLC",
        "DORADO I SOLARBLOOM LLC",
        "DORADO 1 RESIDENTIAL SOLAR LLC",
        "DORADO 1 SOLARBLOOM LLC",
    ),
    index_queries=("ULTRALIGHT", "DORADO"),
    servicer="SunStrong Management, which took SunPower's leases and their servicing in the 2024 bankruptcy",
    note=(
        "Escrow is told on every resale in these buildings that the association does not maintain the panels "
        "and that a lease, if there is one, passes to the buyer with its payments."
    ),
)
