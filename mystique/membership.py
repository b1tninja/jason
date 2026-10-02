"""Membership workbook. PayHOA is current for units and people; these tabs keep facts PayHOA does not store.

Walk the named tabs. Do not treat every other tab as a catalog of files or people.
"""

from jason.community.symbols import KnownFile, MembershipTab

WORKBOOK = KnownFile.MEMBERSHIP

# Keyed by property address, which matches PayHOA unit address_line1.
# Properties adds building, plan, size, occupancy, and board role.
# Roster adds mailing address and registration.
# Buildings adds phase, annexation, and assessment schedule.
TABS = (
    MembershipTab.PROPERTIES,
    MembershipTab.ROSTER,
    MembershipTab.BUILDINGS,
)
