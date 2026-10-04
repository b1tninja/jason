"""Filing classes and encumbrance pairing (implemented in asspy).

The day a lifecycle's status is read is asspy's ``asspy.filings.today_for_status``;
a test that fixes the day replaces that one.
"""

from __future__ import annotations

from datetime import date

import asspy.filings as _asspy

from asspy.filings import (  # noqa: F401
    ADVANCES,
    CLOSES,
    CURES,
    ESCALATES,
    FILINGS,
    LIEN_LIFE,
    MECHANICS_EXTENSION_DAYS,
    MECHANICS_LIEN_DAYS,
    OPENS,
    PROCESS_NOTES,
    Encumbrance,
    Family,
    InstrumentClass,
    LienLife,
    NameMatch,
    Process,
    Step,
    encumbrances,
    instrument_class,
    name_match,
    naming,
    party_is,
    same_party,
)


def today_for_status() -> date:
    """The day a lifecycle's status is read: asspy's, so a test fixes one day for both."""
    return _asspy.today_for_status()
