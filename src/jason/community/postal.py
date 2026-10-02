"""A US mailing address as an owner typed it on a form, read into the parts PayHOA's profile keeps.

``parse_mailing_address`` is strict: a street line that starts with a number (or a PO Box), a city, a state (its
two-letter code or its name), and a five-digit ZIP. Anything else is a miss, and a miss goes to a person; it never
guesses. The address is read in memory and handed to PayHOA; jason does not store it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

US_STATES = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas", "CA": "California", "CO": "Colorado",
    "CT": "Connecticut", "DE": "Delaware", "DC": "District of Columbia", "FL": "Florida", "GA": "Georgia",
    "HI": "Hawaii", "ID": "Idaho", "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas", "KY": "Kentucky",
    "LA": "Louisiana", "ME": "Maine", "MD": "Maryland", "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota",
    "MS": "Mississippi", "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada", "NH": "New Hampshire",
    "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York", "NC": "North Carolina", "ND": "North Dakota",
    "OH": "Ohio", "OK": "Oklahoma", "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island",
    "SC": "South Carolina", "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah", "VT": "Vermont",
    "VA": "Virginia", "WA": "Washington", "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming",
}
_BY_NAME = {name.casefold(): code for code, name in US_STATES.items()}
_STATE = "|".join([*US_STATES, *(re.escape(n) for n in US_STATES.values())])
_LINE2 = r"(?:apt|apartment|unit|ste|suite|pmb|#|bldg|building|fl|floor|rm|room)\.?\s*[\w-]+"
# The street line ends at a comma or a line break: without one, where the street ends and the city begins is a guess.
ADDRESS = re.compile(
    rf"^\s*(?:(?P<lead2>{_LINE2})\s*,\s*)?"            # "PMB 188" written first, as its own line
    rf"(?P<street>(?:\d+[\w-]*|p\.?\s*o\.?\s*box)\s+[^,]+?)(?:\s+(?P<inline2>{_LINE2}))?\s*,\s*"
    rf"(?:(?P<line2>{_LINE2})\s*,\s*)?"
    rf"(?P<city>[A-Za-z][A-Za-z .'-]*?)\s*,?\s+(?P<state>{_STATE})\.?\s*,?\s*(?P<zip>\d{{5}})(?:-\d{{4}})?"
    rf"\s*(?:,?\s*(?:usa|us|united states))?\s*$",
    re.I,
)


@dataclass(frozen=True)
class MailingAddress:
    line1: str
    line2: str
    city: str
    state: str          # two-letter code
    zip: str

    def region(self) -> dict[str, str]:
        """PayHOA's region record."""
        return {"countryCode": "US", "region": US_STATES[self.state], "abbreviation": self.state}

    def same_street(self, other_line1: str) -> bool:
        """Whether ``other_line1`` is this street line, ignoring case, punctuation, and spacing."""
        return _key(self.line1) == _key(other_line1 or "")


def _key(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.casefold())


# USPS street suffixes and unit designators (Publication 28), with the variants people write, to their standard short
# forms; and the directions. Enough to tell "3028 Macon Drive" and "3028 MACON DR." apart from a real change.
_WORDS = {
    "drive": "dr", "drv": "dr", "street": "st", "str": "st", "avenue": "ave", "av": "ave", "avn": "ave",
    "boulevard": "blvd", "boul": "blvd", "lane": "ln", "road": "rd", "court": "ct", "crt": "ct", "circle": "cir",
    "circ": "cir", "place": "pl", "parkway": "pkwy", "pky": "pkwy", "terrace": "ter", "terr": "ter", "highway": "hwy",
    "walk": "walk", "wk": "walk", "wlk": "walk", "way": "way", "wy": "way", "trail": "trl", "square": "sq",
    "apartment": "apt", "suite": "ste", "unit": "unit", "building": "bldg", "floor": "fl", "room": "rm", "number": "#",
    "no": "#", "post": "po", "office": "", "box": "box", "p": "", "o": "",
    "north": "n", "south": "s", "east": "e", "west": "w", "northeast": "ne", "northwest": "nw", "southeast": "se",
    "southwest": "sw", "usa": "", "us": "", "united": "", "states": "", "america": "",
}


def normalize_address(text: str) -> str:
    """An address reduced to what tells two addresses apart: lower case, no punctuation, USPS short forms, state names
    as codes, a ZIP+4 cut to its five digits. "3028 Macon Drive, Sacramento, California 95835-1234" and "3028 MACON
    DR SACRAMENTO CA 95835" read the same; a different number, street, or ZIP does not."""
    flat = (text or "").casefold().replace("p.o.", "po ").replace("p. o.", "po ")
    for name, code in sorted(((n.casefold(), c.casefold()) for c, n in US_STATES.items()), key=lambda x: -len(x[0])):
        flat = re.sub(rf"\b{re.escape(name)}\b", code, flat)
    flat = re.sub(r"\b(\d{5})-\d{4}\b", r"\1", flat)
    words = re.findall(r"[a-z0-9#]+", flat)
    return " ".join(w for w in (_WORDS.get(w, w) for w in words) if w)


def parse_mailing_address(text: str) -> MailingAddress | None:
    """The address's parts, or None when it does not read as one US mailing address."""
    flat = re.sub(r"\s*[\r\n]+\s*", ", ", (text or "").strip())
    m = ADDRESS.match(flat)
    if not m:
        return None
    state = m.group("state")
    code = state.upper() if state.upper() in US_STATES else _BY_NAME.get(state.casefold())
    if not code:
        return None
    street = re.sub(r"\s+", " ", m.group("street")).strip(" ,")
    # a suite and a private mailbox both kept, in USPS order: "Ste 120 PMB 188"
    line2 = " ".join(x.strip() for x in (m.group("line2") or m.group("inline2") or "", m.group("lead2") or "") if x)
    return MailingAddress(street, line2, m.group("city").strip(" ,"), code, m.group("zip"))


# The state a ZIP code is in, by its first three digits (USPS ZIP prefix ranges): for putting a misread or missing
# state right from the ZIP beside it. A reading hint, marked as one; never the record of what an owner wrote.
_ZIP3 = (
    (10, 27, "MA"), (28, 29, "RI"), (30, 38, "NH"), (39, 49, "ME"), (50, 59, "VT"), (60, 69, "CT"), (70, 89, "NJ"),
    (100, 149, "NY"), (150, 196, "PA"), (197, 199, "DE"), (200, 205, "DC"), (206, 219, "MD"), (220, 246, "VA"),
    (247, 268, "WV"), (270, 289, "NC"), (290, 299, "SC"), (300, 319, "GA"), (320, 349, "FL"), (350, 369, "AL"),
    (370, 385, "TN"), (386, 397, "MS"), (398, 399, "GA"), (400, 427, "KY"), (430, 459, "OH"), (460, 479, "IN"),
    (480, 499, "MI"), (500, 528, "IA"), (530, 549, "WI"), (550, 567, "MN"), (570, 577, "SD"), (580, 588, "ND"),
    (590, 599, "MT"), (600, 629, "IL"), (630, 658, "MO"), (660, 679, "KS"), (680, 693, "NE"), (700, 714, "LA"),
    (716, 729, "AR"), (730, 749, "OK"), (750, 799, "TX"), (800, 816, "CO"), (820, 831, "WY"), (832, 838, "ID"),
    (840, 847, "UT"), (850, 865, "AZ"), (870, 884, "NM"), (885, 885, "TX"), (889, 898, "NV"), (900, 961, "CA"),
    (967, 968, "HI"), (970, 979, "OR"), (980, 994, "WA"), (995, 999, "AK"),
)


def state_for_zip(zip_code: str) -> str:
    """The two-letter state a five-digit ZIP code is in, or "" (a military, territory, or unknown prefix)."""
    m = re.match(r"\s*(\d{3})\d{2}", zip_code or "")
    if not m:
        return ""
    prefix = int(m.group(1))
    return next((code for lo, hi, code in _ZIP3 if lo <= prefix <= hi), "")


def is_state(text: str) -> bool:
    word = (text or "").strip(" .,")
    return word.upper() in US_STATES or word.casefold() in _BY_NAME


# A street line at one of the community's units, with nothing after it but its own city, state, or ZIP (in part).
_LOCAL = re.compile(r"^\s*(\d{3,5})\s+([A-Za-z]+)(?:\s+([A-Za-z]+)\.?)?\s*(?:[,\n]\s*(.*?))?\s*$", re.S)
COMPLETED = "completed with the community's city, state, and ZIP"


def read_mailing_address(text: str, city_line: str = "") -> tuple[MailingAddress | None, str]:
    """The address as written (``parse_mailing_address``), or, when it is only a street line at one of the community's
    units ("5651 Whimsical Lane", "3006 magical wlk"), completed with ``city_line`` (the community's "City, ST ZIP").
    Returns the address and how it was read ("" as written, ``COMPLETED``), or (None, "") when it reads neither way."""
    found = parse_mailing_address(text)
    if found is not None or not city_line:
        return found, ""
    m = _LOCAL.match(text or "")
    city = parse_mailing_address(f"1 X St, {city_line}")
    if not m or city is None:
        return None, ""
    from jason.community.base import read_unit_address

    number, street = read_unit_address(f"{m.group(1)} {m.group(2)}")
    if street is None:
        return None, ""
    suffix, rest = m.group(3), normalize_address(m.group(4) or "")
    if suffix and normalize_address(suffix) not in normalize_address(street.value).split():
        return None, ""                                    # "5651 Whimsical Court": another street, not ours
    if rest and not normalize_address(city_line).startswith(rest) and rest not in normalize_address(city_line):
        return None, ""                                    # a different city or ZIP: not the community
    return MailingAddress(f"{number} {street.value}", "", city.city, city.state, city.zip), COMPLETED


__all__ = ["COMPLETED", "MailingAddress", "US_STATES", "is_state", "normalize_address", "parse_mailing_address", "state_for_zip",
           "read_mailing_address"]
