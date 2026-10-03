"""Permanent section ids: a section keeps one id through amendments, renumberings, and new readings of its text.

In Akoma Ntoso a work-level id (wId) is fixed by the element's place in a master expression. Here a section's
permanent id is its address at the version where it first appeared (``jason.community.addresses.pid``):

- ``decl@base/4.15(a)`` was in the base text;
- ``decl@2099-01-01/4.15(o)`` was added by the instrument that took effect that day.

A section numbered differently later keeps its id. Every number it has gone by is a ``Name`` in its history:

- **from a version**: "known as 4.16 from 2099-01-01" (an amendment renumbered it);
- **under a reading**: "known as 4.20(ii)(a) under the outline" (the working copy, or an earlier OCR reading, numbers
  the same words differently). A reading never makes an id; it only names one. A reading's section whose words the
  text as amended runs inline inside another section is a ``within`` name of that section.

``from_versions`` builds a table from a document's versions (oldest first), ``add_reading`` names its sections as
another reading numbers them, and ``carry`` keeps the ids of a stored table when a rebuild (a new OCR reading, a new
numbering) numbers the same words differently. ``IdTable.permanent_id`` and ``IdTable.number_of`` are the two
directions. A document that prints one number twice keeps both apart: the second is ``~2`` (``B-1~2``).

Sections are paired by their opening words (letters and digits, ``outline_align.opening_key``) in order, within an
article of each other, the same number helping; a miss stays a miss. Pure: the readers are in
``jason.tasks.permanent_ids``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field, replace
from datetime import date, timedelta
from typing import Any, Iterable, Sequence

from jason.community.addresses import pid as make_pid
from jason.community.outline_align import opening_key, similarity

FORMAT = 1
MIN_RATIO = 0.6            # two openings this alike are one section
SAME_NUMBER_RATIO = 0.35   # ... or this alike under the same number
WITHIN_KEY = 24            # letters of a reading's opening looked for inside a section the text does not split


@dataclass(frozen=True)
class Name:
    """One number a section went by: in the text as amended from a day (``reading`` empty), or under a reading."""

    number: str
    reading: str = ""                # "" the text as amended; else the reading's name ("outline", "original")
    since: date | None = None        # the first day it went by this number (None: from its birth)
    until: date | None = None        # the last day (None: still)
    within: bool = False             # the reading prints it as a part of this section, which the text does not split
    note: str = ""

    def covers(self, day: date | None) -> bool:
        if day is None:
            return self.until is None
        return (self.since is None or self.since <= day) and (self.until is None or day <= self.until)

    def describe(self) -> str:
        if self.reading:
            return f"known as {self.number} under the {self.reading} reading" + (" (a part it prints)" if self.within
                                                                                 else "")
        span = (f" from {self.since.isoformat()}" if self.since else "") + (f" until {self.until.isoformat()}"
                                                                            if self.until else "")
        return f"{self.number}{span}"

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"number": self.number}
        if self.reading:
            out["reading"] = self.reading
        if self.since:
            out["since"] = self.since.isoformat()
        if self.until:
            out["until"] = self.until.isoformat()
        if self.within:
            out["within"] = True
        if self.note:
            out["note"] = self.note
        return out

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> Name:
        day = lambda k: date.fromisoformat(raw[k]) if raw.get(k) else None  # noqa: E731
        return cls(raw["number"], raw.get("reading", ""), day("since"), day("until"), bool(raw.get("within")),
                   raw.get("note", ""))


@dataclass
class SectionId:
    pid: str
    born: date | None                # None: the base
    names: list[Name]
    removed: date | None = None      # the day an amendment removed it (its words are gone; the id stays)
    key: str = ""                    # its opening words, to find it again when a reading changes

    def name(self, day: date | None = None, reading: str = "") -> Name | None:
        if reading:
            mine = sorted((n for n in self.names if n.reading == reading), key=lambda n: n.within)
            if mine:
                return mine[0]
        here = [n for n in self.names if not n.reading]
        if day is not None and self.born is not None and day < self.born:
            return None
        found = [n for n in here if n.covers(day)]
        if found:
            return found[-1]
        if day is None and here:
            return here[-1]                    # gone from the text now: its last number
        return None

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"pid": self.pid, "born": self.born.isoformat() if self.born else None,
                               "names": [n.to_dict() for n in self.names]}
        if self.removed:
            out["removed"] = self.removed.isoformat()
        if self.key:
            out["key"] = self.key
        return out

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> SectionId:
        return cls(raw["pid"], date.fromisoformat(raw["born"]) if raw.get("born") else None,
                   [Name.from_dict(n) for n in raw.get("names") or ()],
                   date.fromisoformat(raw["removed"]) if raw.get("removed") else None, raw.get("key", ""))


def base_number(number: str) -> tuple[str, int]:
    """"B-1~2" -> ("B-1", 2); "B-1" -> ("B-1", 1)."""
    head, _, n = (number or "").partition("~")
    return head, int(n) if n.isdigit() else 1


@dataclass
class IdTable:
    key: str                          # the address key the ids print ("decl", "rules.parking", a document's key)
    document: str                     # the document it was built from
    basis: str = ""                   # the reading of the text as amended (a re-read's name; "" for the first)
    built: str = ""
    ids: list[SectionId] = field(default_factory=list)
    readings: dict[str, str] = field(default_factory=dict)        # a reading's name -> what it is
    unmatched: dict[str, list[str]] = field(default_factory=dict)  # a reading's sections no id answers to
    source: str = ""                  # what built it: "versions" (a living document), "outline", or another history
                                      # source (a revision detector); jason rebuilds only its own
    fingerprint: str = ""

    def get(self, pid: str) -> SectionId | None:
        return next((s for s in self.ids if s.pid == pid), None)

    def candidates(self, number: str, reading: str = "", day: date | None = None) -> list[str]:
        """Every id a number may name: under ``reading`` first, then in the text as amended on ``day``; with a
        document that prints the number twice, each of them (``B-1``, ``B-1~2``)."""
        head, _ = base_number(number)
        exact = "~" in (number or "")

        def match(n: Name) -> bool:
            return n.number == number or (not exact and base_number(n.number)[0] == head)

        if reading and reading in self.readings:
            if number in (self.unmatched.get(reading) or ()):
                return []
            out = [s.pid for s in self.ids if any(n.reading == reading and match(n) for n in s.names)]
            if out:
                return list(dict.fromkeys(out))
            # A section the reading does not print (no name under it) answers by its number in the text.
            return [s.pid for s in self.ids if not any(n.reading == reading for n in s.names)
                    and (n := s.name(day)) is not None and match(n)]
        return [s.pid for s in self.ids if (n := s.name(day)) is not None and match(n)]

    def permanent_id(self, number: str, as_of: date | None = None, reading: str = "") -> str | None:
        """The id of the section ``number`` names: in the text as amended on ``as_of`` (now when None), or as
        ``reading`` numbers it. None when no section answers to it."""
        found = self.candidates(number, reading, as_of)
        exact = [p for p in found if self._named(p, number, reading, as_of)]
        return (exact or found or [None])[0]

    def _named(self, pid: str, number: str, reading: str, day: date | None) -> bool:
        s = self.get(pid)
        n = s.name(day, reading) if s else None
        return n is not None and n.number == number

    def number_of(self, pid: str, as_of: date | None = None, reading: str = "") -> str | None:
        """The number the section goes by in the text as amended on ``as_of`` (or under ``reading``); None before it
        was born. A removed section answers with its last number (the reader says it was removed)."""
        s = self.get(pid)
        if s is None:
            return None
        n = s.name(as_of, reading)
        return n.number if n is not None else None

    def name_of(self, pid: str, as_of: date | None = None, reading: str = "") -> Name | None:
        s = self.get(pid)
        return s.name(as_of, reading) if s else None

    def renamed(self) -> list[SectionId]:
        """The ids known by more than one number."""
        return [s for s in self.ids if len({n.number for n in s.names}) > 1]

    def to_dict(self) -> dict[str, Any]:
        return {"format": FORMAT, "key": self.key, "document": self.document, "source": self.source,
                "basis": self.basis, "built": self.built, "fingerprint": self.fingerprint, "readings": self.readings,
                "unmatched": self.unmatched, "ids": [s.to_dict() for s in self.ids]}

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> IdTable:
        return cls(raw["key"], raw.get("document", raw["key"]), raw.get("basis", ""), raw.get("built", ""),
                   [SectionId.from_dict(s) for s in raw.get("ids") or ()], dict(raw.get("readings") or {}),
                   {k: list(v) for k, v in (raw.get("unmatched") or {}).items()}, raw.get("source", ""),
                   raw.get("fingerprint", ""))


# --- Pairing sections by their words ---------------------------------------------------------------------------------

def _words(p: Any) -> str:
    return " ".join(x for x in (getattr(p, "caption", ""), getattr(p, "body", "")) if x)


def numbered(provisions: Iterable[Any]) -> list[tuple[str, Any]]:
    """The numbered provisions, each with its number; a number printed again gets ``~2``, ``~3`` in order."""
    seen: dict[str, int] = {}
    out = []
    for p in provisions:
        if not getattr(p, "number", ""):
            continue
        seen[p.number] = seen.get(p.number, 0) + 1
        out.append((p.number if seen[p.number] == 1 else f"{p.number}~{seen[p.number]}", p))
    return out


def _article(number: str) -> int:
    m = re.match(r"\d+", number)
    return int(m.group(0)) if m else 0


def align(a: Sequence[tuple[str, str]], b: Sequence[tuple[str, str]], *, keep: set[int] = frozenset(),
          min_ratio: float = MIN_RATIO) -> list[tuple[int, int]]:
    """The best order-keeping pairing of ``a`` and ``b`` (each (number, opening key)): a pair scores how alike its
    openings are, the same number adds half; a pair must be ``min_ratio`` alike, or ``SAME_NUMBER_RATIO`` under the same
    number, within an article of each other. ``keep`` holds indexes of ``b`` that pair with the same number in ``a``
    whatever their words (a section an instrument restated keeps its id)."""
    n, m = len(a), len(b)
    arts_a = [_article(x[0]) for x in a]
    arts_b = [_article(x[0]) for x in b]
    score = [[0.0] * (m + 1) for _ in range(n + 1)]
    step = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        row, prev = score[i], score[i - 1]
        na, ka = a[i - 1]
        for j in range(1, m + 1):
            best, how = prev[j], 1
            if row[j - 1] > best:
                best, how = row[j - 1], 2
            if abs(arts_a[i - 1] - arts_b[j - 1]) <= 1:
                nb, kb = b[j - 1]
                same = na == nb
                if same and (j - 1) in keep:
                    ratio = max(similarity(ka, kb), SAME_NUMBER_RATIO)
                elif ka == kb:
                    ratio = 1.0
                else:
                    ratio = similarity(ka, kb)
                if ratio >= min_ratio or (same and ratio >= SAME_NUMBER_RATIO):
                    value = prev[j - 1] + ratio + (0.5 if same else 0.0)
                    if value > best:
                        best, how = value, 0
            row[j], step[i][j] = best, how
    pairs = []
    i, j = n, m
    while i and j:
        if step[i][j] == 0:
            pairs.append((i - 1, j - 1))
            i, j = i - 1, j - 1
        elif step[i][j] == 1:
            i -= 1
        else:
            j -= 1
    return pairs[::-1]


def _keyed(provisions: Iterable[Any]) -> list[tuple[str, Any, str]]:
    return [(n, p, opening_key(_words(p))) for n, p in numbered(provisions)]


# --- Building ------------------------------------------------------------------------------------------------------------

def from_versions(key: str, versions: Sequence[tuple[date | None, Sequence[Any]]], *, document: str = "",
                  basis: str = "", built: str = "") -> IdTable:
    """The ids of a document's sections from its versions, oldest first: each ``(the day it took effect (None for the
    base), its provisions)``. A provision is anything with ``number``, ``caption``, ``body``, and optionally ``set_by``,
    ``dated``, and ``removed`` (``jason.community.living.Provision``)."""
    table = IdTable(key, document or key, basis, built)
    prev: list[tuple[str, Any, str]] = []
    prev_ids: list[SectionId] = []
    for k, (effective, provisions) in enumerate(versions):
        rows = _keyed(provisions)
        if k == 0 or effective is None:
            ids = []
            for number, p, words in rows:
                s = SectionId(make_pid(key, "base", number), None, [Name(number)], key=words)
                if getattr(p, "removed", False):
                    s.removed = getattr(p, "dated", None)
                table.ids.append(s)
                ids.append(s)
            prev, prev_ids = rows, ids
            continue
        # A section an instrument set at this version keeps its id under its number, whatever its new words.
        keep = {j for j, (_, p, _) in enumerate(rows) if getattr(p, "dated", None) == effective}
        pairs = dict((j, i) for i, j in align([(n, w) for n, _, w in prev], [(n, w) for n, _, w in rows], keep=keep))
        ids = []
        paired_prev: set[int] = set()
        day_before = effective - timedelta(days=1)
        for j, (number, p, words) in enumerate(rows):
            i = pairs.get(j)
            if i is None:
                s = SectionId(make_pid(key, effective.isoformat(), number), effective, [Name(number, since=effective)],
                              key=words)
                table.ids.append(s)
            else:
                s = prev_ids[i]
                paired_prev.add(i)
                old = s.name(day_before)
                if old is not None and old.number != number:
                    at = s.names.index(old)
                    s.names[at] = replace(old, until=day_before)
                    s.names.append(Name(number, since=effective, note=f"renumbered at the version of "
                                                                      f"{effective.isoformat()}"))
            if getattr(p, "removed", False) and s.removed is None:
                s.removed = effective
            ids.append(s)
        for i, s in enumerate(prev_ids):
            if i not in paired_prev and s.removed is None:
                # Gone from the text (a restated section's subsections give way): the id stays, its words end.
                old = s.name(day_before)
                if old is not None:
                    s.names[s.names.index(old)] = replace(old, until=day_before)
                s.removed = effective
        prev, prev_ids = rows, ids
    return table


def _contains(haystack: str, key: str, *, fuzzy: bool = False) -> bool:
    """Whether a section's run of letters holds a reading's opening: exactly, or (``fuzzy``) as alike as two
    openings must be, so an OCR slip ("benefitting") does not hide it."""
    if len(key) < 16:
        return False
    if key[:WITHIN_KEY] in haystack:
        return True
    if not fuzzy:
        return False
    from difflib import SequenceMatcher

    key = key[:WITHIN_KEY + 16]
    m = SequenceMatcher(None, haystack, key, autojunk=False).find_longest_match(0, len(haystack), 0, len(key))
    if m.size < 8:
        return False
    start = max(0, m.a - m.b)
    window = haystack[start:start + len(key) + 2]
    return SequenceMatcher(None, window, key, autojunk=False).ratio() >= 0.85


def add_reading(table: IdTable, reading: str, provisions: Sequence[Any], current: Sequence[Any], *,
                as_of: date | None = None, describe: str = "") -> list[str]:
    """Name each section of another reading of the document (the outline of a working copy, an earlier OCR reading) by
    the id of the section in ``current`` (the text as amended on ``as_of``) with the same words. A section paired
    under the same number needs no name; one the text runs inline inside a section is named ``within`` it; one with
    no match is left unmatched (``permanent_id`` answers None for it under the reading). Returns the unmatched."""
    theirs = _keyed(provisions)
    ours = _keyed(current)
    table.readings[reading] = describe or reading
    for s in table.ids:                           # a rebuild names the reading afresh
        s.names = [n for n in s.names if n.reading != reading]
    pairs = dict((j, i) for i, j in align([(n, w) for n, _, w in ours], [(n, w) for n, _, w in theirs]))
    pid_of = {n: table.permanent_id(n, as_of) for n, _, _ in ours}
    # The run of letters each section of the text holds, for a reading's section the text does not split out.
    full = {n: re.sub(r"[^a-z0-9]", "", _words(p).lower()) for n, p, _ in ours}
    unmatched: list[str] = []
    for j, (number, p, words) in enumerate(theirs):
        i = pairs.get(j)
        if i is not None:
            target = ours[i][0]
            pid = pid_of.get(target)
            if pid:
                table.get(pid).names.append(Name(number, reading, note="" if target == number else
                                                 f"{target} in the text as amended"))
            continue
        art = _article(number)
        head = base_number(number)[0]
        # The section's own ancestors first (9.2 for a reading's 9.2(e)), longest first, then its article, then all.
        ancestors = sorted((n for n, _, _ in ours if head.startswith(n + "(") or head.startswith(n + ".")),
                           key=len, reverse=True)
        article = [n for n, _, _ in ours if _article(n) == art and n not in ancestors]
        holder = next((n for n in [*ancestors, *article] if _contains(full[n], words)), None)
        if holder is None:
            holder = next((n for n, _, _ in ours if _contains(full[n], words)), None)
        if holder is None:
            holder = next((n for n in [*ancestors, *article] if _contains(full[n], words, fuzzy=True)), None)
        if holder is not None and pid_of.get(holder):
            table.get(pid_of[holder]).names.append(Name(number, reading, within=True,
                                                        note=f"inside {holder} in the text as amended"))
            continue
        unmatched.append(number)
    table.unmatched[reading] = unmatched
    return unmatched


def carry(previous: IdTable, fresh: IdTable, *, reading_was: str = "earlier") -> IdTable:
    """``fresh`` with ``previous``'s ids kept: a section found again (by its opening words, in order) keeps its id,
    and a number it went by in the earlier reading that differs is kept as a name "under the ``reading_was``
    reading". An id the fresh build lacks is kept, its names closed; a fresh section with no earlier id keeps its new
    one (made distinct when the earlier table already used it). An id is never dropped and never reused."""
    old_rows = [(s.name(None).number if s.name(None) else "", s.key) for s in previous.ids]
    new_rows = [(s.name(None).number if s.name(None) else "", s.key) for s in fresh.ids]
    pairs = dict((j, i) for i, j in align(old_rows, new_rows))
    used = {s.pid for s in previous.ids}
    out = IdTable(fresh.key, fresh.document, fresh.basis, fresh.built, [], dict(previous.readings),
                  dict(previous.unmatched), fresh.source, fresh.fingerprint)
    out.readings.update(fresh.readings)
    out.unmatched.update(fresh.unmatched)
    taken: set[int] = set()
    for j, s in enumerate(fresh.ids):
        i = pairs.get(j)
        if i is None:
            pid = s.pid
            k = 2
            while pid in used:
                pid = f"{s.pid}~{k}" if "~" not in s.pid else f"{s.pid.rsplit('~', 1)[0]}~{k}"
                k += 1
            used.add(pid)
            out.ids.append(replace(s, pid=pid))
            continue
        taken.add(i)
        old = previous.ids[i]
        names = list(s.names)
        for n in old.names:
            if n.reading and n.reading not in fresh.readings and n not in names:
                names.append(n)                              # a reading the fresh build did not redo
        mine = {n.number for n in s.names if not n.reading}
        for n in old.names:
            if not n.reading and n.number not in mine:
                names.append(replace(n, reading=reading_was, since=None, until=None,
                                     note=f"its number under the {reading_was} reading"))
        out.ids.append(SectionId(old.pid, old.born, names, s.removed, s.key or old.key))
    for i, old in enumerate(previous.ids):
        if i not in taken:
            names = [replace(n, reading=n.reading or reading_was) for n in old.names]
            out.ids.append(SectionId(old.pid, old.born, names, old.removed, old.key))
    return out


def from_lineages(key: str, lineages: Iterable[tuple[str, date | None, Sequence[Name]]], *, document: str = "",
                  source: str = "", basis: str = "", built: str = "") -> IdTable:
    """A table from another history source's lineages (a revision detector's): each ``(permanent id, the day it was
    born (None for the base), the numbers it went by)``. The id is the source's, made by the same rule
    (``addresses.pid``: the number in the version where the section first appeared)."""
    table = IdTable(key, document or key, basis, built, source=source or "lineages")
    for pid, born, names in lineages:
        table.ids.append(SectionId(pid, born, list(names)))
    return table


__all__ = ["FORMAT", "IdTable", "Name", "SectionId", "add_reading", "align", "base_number", "carry", "from_lineages",
           "from_versions", "numbered"]
