"""Governing instruments a later one rescinded, which the index does not cross-reference.

Watt did this twice. The phase 3 annexation of January 16, 2019 (201901161003)
was replaced and rescinded by the amended and restated one of December 20,
2019 (201912201433), whose recital says so. Then Watt recorded a Declaration
of Annexation and Reservation of Easements for Mystique, Phase 4, on May 22,
2019, as 201905221469. Under its section 4
the declarant could rescind it while no unit of that phase had been
conveyed, and the Amended and Restated Declaration of Annexation and
Reservation of Easements for Mystique, Phase 4, recorded March 2, 2020, as
202003021215 (indexed as an amended restriction) says in its recital D that
on its recording the prior declaration "is hereby rescinded and superseded"
and has no force on any portion of the development. The recital is the
only record of the rescission: the index cites the condominium plan from
the 2020 instrument, not the 2019 one.
"""

from jason.community.governing import Supersession

SUPERSESSIONS: tuple[Supersession, ...] = (
    Supersession(
        "200709120758",
        "200709200938",
        role="declaration",
        reason="the Restated Declaration rescinded and revoked the declaration of September 12, 2007 before any unit was conveyed",
        source="recital F of the Restated Declaration of Covenants, Conditions and Restrictions for Mystique, recorded 2007-09-20 as "
               "200709200938 (CCRs.pdf); confirmed by the board 2026-09-29",
    ),
    Supersession(
        "201901161003",
        "201912201433",
        phase=3,
        role="annexation",
        reason="the amended and restated phase 3 annexation replaced and rescinded the January 2019 instrument",
        source="recital of the Amended and Restated Declaration of Annexation and Reservation of Easements for Mystique, Phase 3, recorded 2019-12-20 as 201912201433 (Annexation - Phase 3.pdf on Drive)",
    ),
    Supersession(
        "201905221469",
        "202003021215",
        phase=4,
        role="annexation",
        reason="section 4 of the 2019 declaration let the declarant rescind it while no unit of the phase had been conveyed",
        source="recital D of the Amended and Restated Declaration of Annexation and Reservation of Easements for Mystique, Phase 4, recorded 2020-03-02 as 202003021215",
    ),
)
