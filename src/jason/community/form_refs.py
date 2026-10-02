"""The marker on a copy of a form jason sends: which campaign it belongs to, and, when copies differ, which copy it is.

A marker is a hint, never something the reading depends on. The form is recognised from its own printed text and layout
(``form_reader.identify_form``), and every answer is read from the page; a marker, when it reads back, only names the
campaign or the copy so the answers can be compared with what was sent. A marker that is missing, smudged, or fails its
check changes nothing but that.

``NP27E-4RK9T-C7``:

- ``NP``: the form's code (``FormTemplate.code``), two letters of the alphabet below;
- ``27``: the cycle's year; ``E``: the channel (``E`` email, ``M`` mail, ``P`` PayHOA): together, the campaign;
- ``4RK9T``: the copy, five characters from a hash of the campaign, the owner, and the unit; left out when every copy of
  the campaign is the same (the mailed letter: ``NP27M-H3``);
- ``C7``: two check characters, weighted sums modulo 23 (the alphabet's size, a prime), which catch every single misread
  character and every swap of two neighbours.

**The alphabet** is 23 characters that OCR does not confuse with one another: ``0-9 A C E F H K M N P R T V X``. Every
look-alike OCR returns instead is read as the character it stands for (O, D, Q as 0; I, J, L as 1; Z as 2; S as 5; G as
6; B as 8; U, Y as V). Trials on simulated scans (``docs/form-identifiers.md``) found OCR reading J as I, 5 as S, B as 8,
and 0 as @ in Crockford's base 32, a machine typeface (OCR A) reading worst of all, and text under 10 points lost
entirely in a 150 dpi home scan.

``parse`` reads markers out of any text; ``closest`` takes a marker that failed its check to the one sent marker it is a
single character away from, if there is exactly one: a hint checked against what was really sent, never a guess.

(``jason.community.references`` is a different thing: the citations a document's text makes to the law and to other
documents.)
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from enum import Enum
from typing import Iterable

ALPHABET = "0123456789ACEFHKMNPRTVX"                    # 23 characters OCR keeps apart
LOOKALIKE = str.maketrans({"O": "0", "D": "0", "Q": "0", "I": "1", "J": "1", "L": "1", "Z": "2", "S": "5", "G": "6",
                           "B": "8", "U": "V", "Y": "V"})
_SEP = r"[\s\-‐-―.,:]{0,3}"
# Tried at every position (a look-ahead), so a label run into the marker ("RefNP27E…") cannot hide it; each position is
# read both with a copy part and without, so a campaign's marker followed by a word ("NP27M-H3 Owner") is not swallowed.
_CAMPAIGN = rf"([0-9A-Z]{{2}}{_SEP}[0-9A-Z]{{2}}{_SEP}[0-9A-Z])"
_TAIL = rf"((?:{_SEP}[0-9A-Z]){{2}})"
TOKENS = (re.compile(rf"(?={_CAMPAIGN}((?:{_SEP}[0-9A-Z]){{5}}){_TAIL})", re.IGNORECASE),     # with a copy part
          re.compile(rf"(?={_CAMPAIGN}(){_TAIL})", re.IGNORECASE))                               # a campaign alone


class Channel(Enum):
    EMAIL = "E"
    MAIL = "M"
    PAYHOA = "P"


def _clean(text: str) -> str:
    return re.sub(r"[^0-9A-Z]", "", text.upper()).translate(LOOKALIKE)


def check(body: str) -> str:
    """Two characters: the body's values weighted by position, and by its square, each summed modulo 23."""
    values = [ALPHABET.index(ch) for ch in body]
    first = sum((i + 1) * v for i, v in enumerate(values)) % 23
    second = sum((i + 1) ** 2 * v for i, v in enumerate(values)) % 23
    return ALPHABET[first] + ALPHABET[second]


@dataclass(frozen=True)
class Marker:
    campaign: str             # "NP27E": the form's code, the cycle's year, the channel
    copy: str = ""            # "4RK9T", or "" when every copy of the campaign is the same

    @property
    def text(self) -> str:
        return "-".join(x for x in (self.campaign, self.copy, check(self.campaign + self.copy)) if x)

    def __str__(self) -> str:
        return self.text


def campaign(form_code: str, year: int, channel: Channel) -> str:
    code = form_code.upper().translate(LOOKALIKE)
    if len(code) != 2 or any(ch not in ALPHABET for ch in code) or not code.isalpha():
        raise ValueError(f"a form's code is two letters from {ALPHABET}: {form_code!r}")
    return f"{code}{year % 100:02d}{channel.value}"


def make(form_code: str, year: int, channel: Channel, *, membership_id: int | None = None,
         unit_id: int | None = None) -> Marker:
    """The campaign's marker, with the copy's part when ``membership_id`` and ``unit_id`` name one copy. The same inputs
    always give the same marker (a resend does not change it), and it says nothing about the owner."""
    name = campaign(form_code, year, channel)
    if membership_id is None or unit_id is None:
        return Marker(name)
    number = int.from_bytes(hashlib.sha256(f"{name}|{membership_id}|{unit_id}".encode()).digest()[:8], "big")
    copy = ""
    for _ in range(5):
        number, digit = divmod(number, 23)
        copy += ALPHABET[digit]
    return Marker(name, copy)


def _candidates(text: str) -> Iterable[tuple[int, str, str, str]]:
    """Each reading at each position: its start, the campaign, the copy part (or ""), and the check characters."""
    for token in TOKENS:
        for m in token.finditer(text or ""):
            name, copy, tail = _clean(m.group(1)), _clean(m.group(2) or ""), _clean(m.group(3))
            if len(name) == 5 and name[:2].isalpha() and name[2:4].isdigit() and name[4] in {c.value for c in Channel} \
                    and all(ch in ALPHABET for ch in name + copy + tail):
                yield m.start(), name, copy, tail


def parse(text: str) -> list[Marker]:
    """The markers in ``text`` (an email's subject or body, a page's OCR), read the way OCR and people write them, kept
    only when their check holds. Where a copy's reading and a campaign's both hold at one place, the copy's is kept."""
    found: dict[int, Marker] = {}
    for start, name, copy, tail in _candidates(text):
        if check(name + copy) == tail and start not in found:
            found[start] = Marker(name, copy)
    out: list[Marker] = []
    for _, marker in sorted(found.items()):
        if marker not in out:
            out.append(marker)
    return out


def correct(symbols: str) -> str | None:
    """``symbols`` (a marker's characters with its two check characters, no separators) with one wrong character
    put right, or None. The two checks are syndromes: a single error of size ``d`` at position ``p`` leaves
    ``(p+1)·d`` in the first and ``(p+1)²·d`` in the second, so their ratio names the position and the first the size;
    an error in a check character leaves the other check at zero. Two errors can look like one put right somewhere
    else, so a correction is a hint to confirm (against what was sent, or a second reading), never a reading."""
    if len(symbols) < 3 or any(ch not in ALPHABET for ch in symbols):
        return None
    body, tail = symbols[:-2], symbols[-2:]
    values = [ALPHABET.index(ch) for ch in body]
    s1 = (sum((i + 1) * v for i, v in enumerate(values)) - ALPHABET.index(tail[0])) % 23
    s2 = (sum((i + 1) ** 2 * v for i, v in enumerate(values)) - ALPHABET.index(tail[1])) % 23
    if not s1 and not s2:
        return symbols
    if not s2:                                     # the first check character misread
        return body + ALPHABET[(ALPHABET.index(tail[0]) + s1) % 23] + tail[1]
    if not s1:                                     # the second
        return body + tail[0] + ALPHABET[(ALPHABET.index(tail[1]) + s2) % 23]
    place = s2 * pow(s1, -1, 23) % 23              # p + 1
    if not 1 <= place <= len(body):
        return None                                # more than one error
    size = s1 * pow(place, -1, 23) % 23
    p = place - 1
    return body[:p] + ALPHABET[(values[p] - size) % 23] + body[p + 1:] + tail


def _as_marker(symbols: str) -> Marker | None:
    """The marker these symbols spell, when they have a marker's shape (campaign, an optional copy, the checks)."""
    name, rest = symbols[:5], symbols[5:-2]
    if len(name) != 5 or len(rest) not in (0, 5) or not (name[:2].isalpha() and name[2:4].isdigit()) \
            or name[4] not in {c.value for c in Channel} or check(name + rest) != symbols[-2:]:
        return None
    return Marker(name, rest)


def repaired(text: str) -> list[Marker]:
    """The markers in ``text`` that fail their check but read as a marker with one character put right
    (``correct``). Hints only: a caller confirms each against what was sent."""
    out: list[Marker] = []
    for _, name, copy, tail in _candidates(text):
        if check(name + copy) == tail:
            continue
        fixed = correct(name + copy + tail)
        if fixed and (marker := _as_marker(fixed)) and marker not in out:
            out.append(marker)
    return out


def closest(text: str, sent: Iterable[Marker]) -> Marker | None:
    """A marker in ``text`` that failed its check, taken to the one sent marker it differs from in a single character
    (the check characters included), when there is exactly one. None otherwise: never a guess among several."""
    sent = list(sent)
    for _, name, copy, tail in _candidates(text):
        read = name + copy + tail
        near = [m for m in sent if len(m.text.replace("-", "")) == len(read)
                and sum(a != b for a, b in zip(m.text.replace("-", ""), read)) == 1]
        if len(near) == 1:
            return near[0]
    return None


__all__ = ["ALPHABET", "Channel", "LOOKALIKE", "Marker", "campaign", "check", "closest", "correct", "make", "parse",
           "repaired"]
