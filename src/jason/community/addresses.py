"""Record addresses: one name for a section, a version, or a record, after Akoma Ntoso's naming, simplified.

The grammar (docs/record-addresses.md)::

    jason://decl/4.15(a)                    the current text
    jason://decl@2023-12-06/4.15(a)         the version made effective that day (a miss when none was)
    jason://decl:2025-01-01/4.15(a)         the version in force on that day
    jason://decl@base/4.15(a)               the text as first recorded or adopted
    jason://decl/history/4.15(a)            the section's timeline
    jason://rules@proposed-2026-11-01       a stage version (``RecordVersion.label()``): not in force
    jason://rules.parking/B-1               a part of a book: a separately adopted document
    jason://res/20990101-1                  a resolution by its number
    jason://min/2099-01-01#item-4           minutes by the meeting's day, and an item in them
    jason://inst/209901010001               a recorded instrument by the county's document number
    jason://ccrs/4.15(a)                    a document's own key stands in for its book (an alias)

The key is a book (``jason.community.books``), a book's part (``rules.parking``), or a document's own key. A living
book's path is a section number, a span (``6.2..6.4``), or siblings (``6.2(a),6.2(b)``); a series book's path is the
item, then optionally a section inside it. The version (``@``) and the day in force (``:``) sit on the key for a living
book and on the item for a series.

A **permanent id** is an address without its scheme, at the version where the section first appeared:
``decl@base/4.15(a)`` was in the base, ``decl@2023-12-06/4.15(o)`` was added by the instrument effective that day.
``jason.community.permanent_ids`` computes and keeps them.

Pure: parsing and formatting only. ``AddressError`` carries why a text is not an address.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from datetime import date

from jason.community.books import Book, Shape, split_key
from jason.community.revisions import Stage

SCHEME = "jason://"
_KEY = r"[a-z0-9][a-z0-9-]*(?:\.[a-z0-9][a-z0-9-]*)?"
_DAY = r"\d{4}-\d{2}-\d{2}"
_STAGES = "|".join(s.value for s in Stage)
_LABEL = rf"(?:base|{_DAY}|(?:{_STAGES})(?:-(?:{_DAY}|undated))?)"
_HEAD = re.compile(rf"^(?P<key>{_KEY})(?:@(?P<version>{_LABEL}))?(?::(?P<day>{_DAY}))?$")
_ITEM = re.compile(rf"^(?P<item>[A-Za-z0-9][\w.-]*?)(?:@(?P<version>{_LABEL}))?(?::(?P<day>{_DAY}))?$")
_SECTION = re.compile(r"^[A-Za-z0-9][A-Za-z0-9.()\-,~]*$")     # "~2": the second section a document numbers the same


class AddressError(ValueError):
    """A text that is not an address, with what was wrong."""


def _day(text: str | None) -> date | None:
    if not text:
        return None
    try:
        return date.fromisoformat(text)
    except ValueError as exc:
        raise AddressError(f"{text} is not a date (YYYY-MM-DD)") from exc


@dataclass(frozen=True)
class VersionLabel:
    """The part after ``@``: the base, the day a version took effect, or a stage with its day."""

    text: str

    @property
    def base(self) -> bool:
        return self.text == "base"

    @property
    def stage(self) -> Stage | None:
        head = self.text.split("-", 1)[0]
        return Stage(head) if head in {s.value for s in Stage} else None

    @property
    def day(self) -> date | None:
        m = re.search(_DAY + "$", self.text)
        return _day(m.group(0)) if m else None

    @property
    def effective(self) -> date | None:
        """The day a version took effect, for ``@YYYY-MM-DD``; None for the base or a stage."""
        return self.day if re.fullmatch(_DAY, self.text) else None


@dataclass(frozen=True)
class Address:
    key: str                         # "decl", "rules.parking", "res", or a document's own key
    section: str = ""                # a living book's section, or a section inside a series record
    item: str = ""                   # a series book's item
    version: str = ""                # the label after "@" ("base", "2023-12-06", "proposed-2026-11-01")
    in_force: date | None = None     # ":" a day: the version in force on it
    history: bool = False            # "/history": the timeline
    fragment: str = ""               # "#item-4"

    @property
    def book(self) -> Book | None:
        return split_key(self.key)[0]

    @property
    def part(self) -> str:
        return split_key(self.key)[1] if self.book is not None else ""

    @property
    def series(self) -> bool:
        return self.book is not None and self.book.info.shape is Shape.SERIES

    @property
    def label(self) -> VersionLabel | None:
        return VersionLabel(self.version) if self.version else None

    def format(self, *, scheme: bool = True) -> str:
        head = SCHEME if scheme else ""
        stamp = (f"@{self.version}" if self.version else "") + (f":{self.in_force.isoformat()}" if self.in_force else "")
        if self.series:
            out = f"{head}{self.key}" + (f"/{self.item}{stamp}" if self.item else stamp)
        else:
            out = f"{head}{self.key}{stamp}" + ("/history" if self.history else "")
        if self.section:
            out += f"/{self.section}"
        return out + (f"#{self.fragment}" if self.fragment else "")

    def __str__(self) -> str:
        return self.format()

    def at(self, version: str = "", in_force: date | None = None) -> Address:
        return replace(self, version=version, in_force=in_force)


def is_address(text: str) -> bool:
    return str(text or "").strip().lower().startswith(SCHEME)


def parse(text: str) -> Address:
    """An address from its text; ``AddressError`` says what is wrong. The scheme is optional, so a permanent id
    (``decl@base/4.15(a)``) parses too."""
    raw = str(text or "").strip()
    body = raw[len(SCHEME):] if raw.lower().startswith(SCHEME) else raw
    if not body:
        raise AddressError("an address names a book: jason://decl/4.15(a)")
    body, _, fragment = body.partition("#")
    parts = body.split("/")
    head = _HEAD.match(parts[0])
    if head is None:
        raise AddressError(f"{parts[0]!r} is not a key with a version: decl, decl@2099-01-01, decl:2099-01-01, "
                           "rules@proposed-2099-01-01")
    key = head.group("key")
    book = split_key(key)[0]
    rest = parts[1:]
    if book is not None and book.info.shape is Shape.SERIES:
        if head.group("version") or head.group("day"):
            raise AddressError(f"{key} is a series: put the version on the item ({key}/ITEM@VERSION)")
        if not rest or not rest[0]:
            return Address(key, fragment=fragment)
        item = _ITEM.match(rest[0])
        if item is None:
            raise AddressError(f"{rest[0]!r} is not an item of {key} ({book.info.item})")
        section = "/".join(rest[1:])
        if section and not _SECTION.match(section):
            raise AddressError(f"{section!r} is not a section number")
        return Address(key, section, item.group("item"), item.group("version") or "", _day(item.group("day")),
                       fragment=fragment)
    history = bool(rest) and rest[0] == "history"
    if history:
        rest = rest[1:]
    section = "/".join(rest)
    if section and not _SECTION.match(section):
        raise AddressError(f"{section!r} is not a section number (4.15(a), B-1, 6.2..6.4, 6.2(a),6.2(b))")
    if head.group("version") and head.group("day"):
        raise AddressError("name a version (@) or a day in force (:), not both")
    return Address(key, section, "", head.group("version") or "", _day(head.group("day")), history, fragment)


def pid(key: str, version: str, number: str) -> str:
    """A permanent id: the address, without its scheme, of a section at the version it first appeared in."""
    return Address(key, number, version=version or "base").format(scheme=False)


def parse_pid(text: str) -> Address:
    a = parse(text)
    if not a.section or not a.version:
        raise AddressError(f"{text!r} is not a permanent id (KEY@VERSION/SECTION)")
    return a


__all__ = ["Address", "AddressError", "SCHEME", "VersionLabel", "is_address", "parse", "parse_pid", "pid"]
