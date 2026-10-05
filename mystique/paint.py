"""The exterior color and materials palette the developer filed, as the schedule printed it.

Source: ``Plans/Paint Schedule.png`` in the public Drive (file id 1890We-MR0jTDX1e2PVf2LwgG7tmQpdGO), "Mystique
Exterior Color and Materials Palette, Prepared for Watt Communities", job 20170075, November 17, 2017. Three schemes
(columns 1 to 3); most surfaces take scheme 1 only. Names are as printed: the catalog's name for a number has moved
since 2017 (``jason paint --check`` reports it), and the number governs.

The roof row is the Monier tile (Saxon 900 Slate), not a paint; its color is a tile manufacturer's code, so the check
skips it. Which building takes which scheme is not on the schedule; it is the architectural record's to say.
"""

from jason.community.paint import Maker, PaintRow, PaintSchedule, PaintSpec, Surface

PAINT_SCHEDULES = (
    PaintSchedule(
        title="Mystique Exterior Color and Materials Palette",
        source="Drive 1890We-MR0jTDX1e2PVf2LwgG7tmQpdGO (Plans/Paint Schedule.png)",
        prepared="Prepared for Watt Communities, job 20170075, 11/17/2017",
        schemes=(1, 2, 3),
        rows=(
            PaintRow(Surface.FASCIA, "FASCIA", (PaintSpec(1, "SW 7027", "Well-Bred Brown"),)),
            PaintRow(Surface.TRIM, "STUCCO TRIM", (PaintSpec(1, "SW 7000", "Ibis White"),)),
            PaintRow(
                Surface.FIELD,
                "STUCCO FIELD",
                (
                    PaintSpec(1, "SW 7029", "Agreeable Grey"),
                    PaintSpec(2, "SW 7637", "Oyster White"),
                    PaintSpec(3, "SW 6431", "Leap Frog"),
                ),
            ),
            PaintRow(Surface.ENTRY_DOORS, "ENTRY DOORS", (PaintSpec(1, "SW 7545", "Pier"),)),
            PaintRow(
                Surface.GARAGE_DOORS,
                "GARAGE DOORS",
                (PaintSpec(1, "SW 7029", "Agreeable Grey"), PaintSpec(2, "SW 7637", "Oyster White")),
            ),
            PaintRow(
                Surface.ROOF,
                "MONIER ROOF",
                (PaintSpec(1, "1FACS 0024", "Desert Sage", Maker.OTHER),),
                note="Saxon 900 Slate tile; a tile color, not paint",
            ),
        ),
    ),
)
