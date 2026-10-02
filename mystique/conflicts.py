"""Mystique's written provisions that a higher authority displaces, wholly or in part
(``jason.community.authority_order.Conflict``). Each is followed as written except the part that yields. The rows
paraphrase; the board items they name carry the findings and the sources."""

from datetime import date

from jason.community.authority_order import Clarity, Conflict, ConflictStatus, Tier
from jason.community.lessons import Area

AB_130 = date(2025, 6, 30)          # Stats. 2025, ch. 22: Civil Code 5850 and 5855 as amended, operative

CONFLICTS = (
    Conflict(
        "rental-cap-below-floor", "CC&Rs 4.15(a)", Tier.DECLARATION,
        "As restated in 2007, caps rentals at 20 percent of the units.",
        "CIV 4741(b), (f)", Tier.STATUTE, date(2021, 1, 1),
        "A cap below 25 percent may not be adopted or enforced, and 4741(f) had the board restate it by July 1, 2022. "
        "The Second Amendment restates 4.15(a) at 25 percent; the county index shows an amended restriction the "
        "association recorded December 6, 2023 (202312060284), most likely that amendment. An index hit is not a "
        "pin: once the recorded copy is read and matches, this row is resolved by it.",
        "Apply a 25 percent cap: lawful whether or not the amendment took effect (the 20 percent cap cannot be "
        "enforced either way). The rest of 4.15 still governs, read against 4741(a)'s bar on unreasonable "
        "restrictions.",
        Clarity.PLAIN, ConflictStatus.NOTED, (Area.RENTALS, Area.OWNER_INFO, Area.GOVERNING),
        board_item="rental-cap-20-percent"),
    Conflict(
        "fines-over-the-cap", "the 2022 Enforcement Policy and fine schedule", Tier.OPERATING_RULES,
        "Fines a safety violation up to $300, and lists late fees and interest beside the fines.",
        "CIV 5850(c)-(e)", Tier.STATUTE, AB_130,
        "A penalty is the lesser of the schedule or $100 a violation; more only for a violation that may harm health "
        "or safety, after a written finding at an open board meeting (5850(d)); no late charge or interest on a "
        "penalty (5850(e)).",
        "Fine at most $100 a violation unless the board first makes a 5850(d) finding; charge no late fee or interest "
        "on a penalty. The rest of the schedule stands until the board adopts the new policy.",
        Clarity.PLAIN, ConflictStatus.BOARD, (Area.ENFORCEMENT,), board_item="enforcement-policy-ab130"),
    Conflict(
        "per-day-fines", "the 2022 fine schedule's per-day fines", Tier.OPERATING_RULES,
        "Fines a continuing violation by the day until it is cured.",
        "CIV 5850(c), 5865", Tier.STATUTE, AB_130,
        "Whether a fine accruing by the day survives the $100 cap is unsettled; the bylaws allow per-day fines, and "
        "5865 says 5850 neither expands nor reduces the board's authority.",
        "Accrue no per-day fine until counsel advises; a violation that continues after the decision and its cure "
        "period is a new violation, with a new notice and hearing.",
        Clarity.UNCLEAR, ConflictStatus.COUNSEL, (Area.ENFORCEMENT,), board_item="enforcement-policy-ab130"),
    Conflict(
        "hearing-procedure", "the 2022 Enforcement Policy's hearing procedure", Tier.OPERATING_RULES,
        "Notices the hearing by first-class mail, decides within fifteen days, gives no chance to cure, and re-fines a "
        "continuing violation without a further hearing.",
        "CIV 5855(a)-(g)", Tier.STATUTE, AB_130,
        "Notice by personal delivery or the member's 4040 method; no discipline if the member cures before the "
        "hearing (5855(c)); the decision in writing within 14 days (5855(f)); no discipline without these steps "
        "(5855(g)).",
        "Follow the policy's hearing steps with the statute's: 4040 delivery of the notice stating the right to cure, "
        "the member's right to executive session, the decision within 14 days, and a hearing for each penalty.",
        Clarity.PLAIN, ConflictStatus.BOARD, (Area.ENFORCEMENT,), board_item="enforcement-policy-ab130"),
    Conflict(
        "pre-2014-citations", "CC&Rs and Bylaws (their Davis-Stirling citations)", Tier.DECLARATION,
        "Cite about 60 Davis-Stirling sections by their numbers before 2014 (Civil Code 1350 to 1378).",
        "the Davis-Stirling Act as recodified (Stats. 2012, ch. 180)", Tier.STATUTE, date(2014, 1, 1),
        "No conflict of substance: each citation is read as its successor section, as the law now stands.",
        "Read each citation through jason law-history; where the successor or a later amendment changed the rule, "
        "the current text governs.",
        Clarity.RENUMBERED, ConflictStatus.BOARD, (Area.GOVERNING, Area.DOCUMENTS),
        board_item="governing-documents-old-statute-numbers"),
)
