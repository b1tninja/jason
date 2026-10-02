"""A pest control visit read from the technician's own note: which buildings, what was treated, what the bait stations showed.

The vendor's note is free text ("I inspected and treated buildings 5,6,7 and 8 ... checked rodent
stations ... minimal activity"). Read into structure, a year of notes becomes the monitoring
record integrated pest management rests on: which buildings each visit covered, the rodent
activity each time the stations were checked, and the pests named. A phrase the reader does not
know stays unread; the note itself is always kept beside the reading.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import IntEnum

from jason.community.symbols import Building


class Activity(IntEnum):
    """Rodent activity at the bait stations, as the technician rated it. Higher is more."""

    NONE = 0
    MINIMAL = 1
    MINIMAL_TO_MODERATE = 2
    MODERATE = 3
    HEAVY = 4
    LIVE = 5


PESTS = (
    ("ants", r"\bants?\b"), ("spiders", r"\bspiders?\b|\bwebs?\b"), ("wasps", r"\bwasps?\b|yellow ?jackets?"),
    ("roaches", r"\broach(?:es)?\b|cockroach"), ("earwigs", r"\bearwigs?\b"), ("crickets", r"\bcrickets?\b"),
    ("rodents", r"\brodents?\b|\brats?\b|\bmice\b|\bmouse\b"), ("bees", r"\bbees?\b"), ("termites", r"\btermites?\b"),
    ("birds", r"\bbirds?\b|pigeons?"), ("fleas", r"\bfleas?\b"), ("mosquitoes", r"\bmosquito(?:es)?\b"),
)
_NUMBER_WORDS = {"one": "1", "two": "2", "three": "3", "four": "4", "five": "5", "six": "6", "seven": "7", "eight": "8"}
# "buildings 1, 2, 3 and 4", "buildings of 1,2,3, and 4", "treated 5,6,7,8": a list of building numbers after the word.
_BUILDINGS = re.compile(r"(?:buildings?(?:\s+of)?|treated|serviced)\s+((?:\d(?:\s*(?:,|&|\band\b)\s*)*)+)", re.I)
_STATIONS = re.compile(r"bait|station|rodent", re.I)


@dataclass(frozen=True)
class VisitReading:
    buildings: tuple[Building, ...]
    stations_checked: bool
    stations_refilled: bool
    rodent_activity: Activity | None
    pests: tuple[str, ...]
    exterior_treated: bool


def rodent_activity(note: str) -> Activity | None:
    """The highest activity the note gives the stations; None when it rates none or never mentions them."""
    text = note.lower()
    if not _STATIONS.search(text):
        return None
    if re.search(r"\blive\b[^.]*activity|activity[^.]*\blive\b|live (?:rat|rodent|mouse|mice)", text):
        return Activity.LIVE
    if re.search(r"\b(heavy|high|significant)\b[^.]*activity", text):
        return Activity.HEAVY
    if re.search(r"minimal to moderate|low to moderate", text):
        return Activity.MINIMAL_TO_MODERATE
    if re.search(r"\bmoderate\b", text):
        return Activity.MODERATE
    if re.search(r"\b(minimal|low|little|light)\b[^.]*activity|activity[^.]*\b(minimal|low)\b", text):
        return Activity.MINIMAL
    if re.search(r"\bno (?:rodent )?activity|no signs of (?:rodent )?activity", text):
        return Activity.NONE
    return None


def buildings_of(note: str) -> tuple[Building, ...]:
    found: set[int] = set()
    text = re.sub(r"\b(one|two|three|four|five|six|seven|eight)\b", lambda m: _NUMBER_WORDS[m.group(1).lower()], note, flags=re.I)
    for match in _BUILDINGS.finditer(text):
        found.update(int(d) for d in re.findall(r"\d", match.group(1)))
    return tuple(Building(n) for n in sorted(found) if n in {b.value for b in Building})


def read_note(note: str) -> VisitReading:
    text = note.lower()
    pests = tuple(name for name, pattern in PESTS if re.search(pattern, text))
    return VisitReading(
        buildings=buildings_of(note),
        stations_checked=bool(re.search(r"(checked|monitored|inspected|serviced)[^.]*(station|bait)|(station|bait)[^.]*(checked|monitored)", text)),
        stations_refilled=bool(re.search(r"refill|replenish|re-bait|rebait", text)),
        rodent_activity=rodent_activity(note),
        pests=pests,
        exterior_treated=bool(re.search(r"treat", text)),
    )


__all__ = ["Activity", "VisitReading", "read_note", "rodent_activity", "buildings_of", "PESTS"]
