"""The three subdividers. The original developer did not finish the project.

John Laing Homes, indexed as John Laing Homes and as WL Homes, recorded the
declaration and sold the first units. The lender's bankruptcy conveyance is
not a developer. Mystique Builders took units from that estate and sold them.
Watt Communities at Mystique bought what remained and completed the project.
The recorder doubles the I in Watt on one deed. Aldea Homes, David Pick, and
Wachovia conveyed the land between these developers. They are not developers.
"""

from jason.community.base import Developer

# The declaration is indexed under this word. The association's deeds are
# indexed under the longer leading name, however the recorder abbreviates it.
PROJECT = "MYSTIQUE"
ASSOCIATION = "MYSTIQUE COMMUNITY"

DEVELOPERS: tuple[Developer, ...] = (
    Developer("John Laing Homes", ("JOHN LAING HOMES", "WL HOMES")),
    Developer("Mystique Builders", ("MYSTIQUE BLDRS", "MYSTIQUE BUILDERS")),
    Developer(
        "Watt Communities at Mystique",
        ("WATT COMMUNITIES AT MYSTIQUE", "WATT COMMUNIITIES AT MYSTIQUE"),
    ),
)
