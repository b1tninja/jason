"""Mystique's life safety systems: what each is, the standard a record states for it, and who keeps it.

Read October 4, 2026 from the association's own records: the board's minutes of September 19, 2022, December 27, 2022,
and July 18, 2023; the fire protection notes (mystique/notes/fire-protection-records.md, which quote the association's
email of July 12, 2022); and the obligation rows (obligations.py). No plan, permit, or installer's record that states a
sprinkler system's installation standard is on file, so each standard below is entered with the record that states it,
and that record is the board's own statement:

- **Buildings 3 and 8.** Two records, two standards: the July 2022 email says 13R and the September 2022 minutes say
  NFPA 13. Both are entered and jason picks neither. NFPA 25 reaches the systems under either.
- **Buildings 1, 2, and 4 to 7.** The minutes say NFPA 13D each time. That is what takes these systems out of NFPA 25,
  so the plans or the installer's record should confirm it: a question for the board, with the insurer's condition in
  the note below.
- **The fire alarm.** Its installation standard is not entered. The reports are on NFPA 72's inspection forms, which
  say how it is tested, not what it was installed under; the submittal in Drive has not been read for it.

Each obligation's ``applies`` condition (obligations.py) is asked of each system here: ``jason applies``.
"""

from jason.community.applicability import InstallationStandard, SystemKind
from jason.community.life_safety import LifeSafetySystem, StandardReading
from jason.community.symbols import Building

SYSTEMS: tuple[LifeSafetySystem, ...] = (
    LifeSafetySystem(
        key="sprinklers-3-8", name="Fire sprinklers, buildings 3 and 8", kind=SystemKind.FIRE_SPRINKLER,
        standard=InstallationStandard.NFPA_13R,
        standard_from="the association's email to its manager of July 12, 2022: \"Just the 2 buildings with sprinklers "
                      "installed per 13R\" (as mystique/notes/fire-protection-records.md quotes it)",
        also_stated=(StandardReading(
            InstallationStandard.NFPA_13,
            "the board's minutes of September 19, 2022: \"Unit Entry - Buildings 3 and 8 (NFPA 13 cf. NFPA 13D)\""),),
        serves=(Building.BLDG_3, Building.BLDG_8), serves_label="buildings 3 and 8",
        servicer="The Fire Sprinkler Company", monitor="Signal Service",
        note="Wet systems with two risers and heads inside the units. The association inspects and "
             "maintains them (the minutes of September 19, 2022: \"a shared sprinkler system that the HOA must inspect "
             "and maintain\"). Signal Service monitors the waterflow and tamper switches and does not service the "
             "sprinklers. The master policy schedules the sprinklers as a protective safeguard (P-1, buildings 1 to 8)."),
    LifeSafetySystem(
        key="sprinklers-1-2-4-7", name="Fire sprinklers, buildings 1, 2, and 4 to 7", kind=SystemKind.FIRE_SPRINKLER,
        standard=InstallationStandard.NFPA_13D,
        standard_from="the board's minutes of September 19, 2022 (\"Newer buildings are considered One and Two-Family "
                      "Dwellings\"), December 27, 2022, and July 18, 2023 (\"built to a different standard, NFPA 13D\"); "
                      "the board's own statement, with no plan, permit, or installer's record on file",
        serves=(Building.BLDG_1, Building.BLDG_2, Building.BLDG_4, Building.BLDG_5, Building.BLDG_6, Building.BLDG_7),
        serves_label="buildings 1, 2, and 4 to 7",
        note="Each unit has its own system, independent of the other units; the minutes of September 19, 2022 say they "
             "\"are not maintained by the HOA\". No inspection record is on file and no vendor keeps them. The master "
             "policy's protective safeguard (P-1) schedules buildings 1 to 8, so the insurer's condition reaches these "
             "systems whatever the inspection standard. Who maintains them under the declaration is a question for "
             "counsel (mystique/notes/fire-protection-records.md)."),
    LifeSafetySystem(
        key="fire-alarm-3-8", name="Fire alarm and sprinkler monitoring, buildings 3 and 8", kind=SystemKind.FIRE_ALARM,
        serves=(Building.BLDG_3, Building.BLDG_8), serves_label="buildings 3 and 8",
        servicer="Signal Service", monitor="Signal Service",
        note="One system a building in Signal Service's records. It watches the sprinklers' waterflow and tamper "
             "switches and reports to Signal Service's supervising station; Signal Service inspects and tests it and "
             "leases the equipment. A failed waterflow or tamper device is the sprinkler contractor's to repair."),
    LifeSafetySystem(
        key="backflow", name="Backflow prevention assemblies", kind=SystemKind.BACKFLOW,
        serves_label="the fire service",
        servicer="LeDoux Backflow Testing Services",
        note="Tested yearly for the City's cross-connection program (the row \"Backflow assembly test\"). The "
             "forward-flow test of the assemblies on the fire service is part of the sprinkler annual (NFPA 25 13.6), "
             "not of this test. The records count the assemblies differently: the obligation row says six are tested, "
             "and the fire protection notes list five on the fire service."),
)
