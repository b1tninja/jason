"""The words of the law on the shelf, section by section, each with a digest of its words.

``jason export-authorities`` writes one page per span under ``data/authorities``; a section is the body under its
``## CITATION`` heading, split as ``context_pack.law_corpus`` splits it. A section's **words** are that body with line
endings and trailing spaces normalized, less jason's own ``- History:`` note (an annotation from the law history, not
the Legislature's words). Its **digest** is the SHA-256 of those words. The page's header (the session, the official
page, why jason holds it) is outside every section, so a new session label alone changes no digest.

The digest is what a derived record is tied to: a reading of the law (``jason.community.law_readings``) names the
digest of the words it read, and is stale when the shelf no longer holds words with that digest. When an export
replaces a section's words, the replaced words are kept under ``data/authorities/history/<citation>/<digest>.md`` and
the change is a row in ``data/authorities/changes.json`` (``jason.tasks.authority_digests`` writes both). That log is
jason's record of its own shelf; the Act's amendment history from lawlibrary is ``history/changes.json``
(``jason.community.succession``), a different file.

A page may hold one section more than once: the Legislature's publication prints two versions of some sections, each
under the same number. ``versions`` gives every one; ``law_text`` and ``section_digest`` give the first. The first is
not always the one in force: the order is the publication's. ``authority_text`` quotes the one in force today where
the versions' own words say which.

**The words in force on a day.** The history folder also holds earlier versions of a section, each with the range it
was in force where a record says it: ``jason law-history --versions`` reads them from the session publications
lawlibrary holds (``jason.tasks.statute_fetch.prior_versions``), and a person may add one by hand. ``in_force`` says
which words governed on a day, and how it knows: an earlier version whose recorded range holds the day, the current
words where a record says they were in force by then, or, between two versions printed under one number, the one the
versions' own operative words pick. Where the disk does not show it, it says so and picks nothing.
``law_text(citation, data_dir, as_of=day)`` gives those words, or None.

This module reads the disk only. It never asks lawlibrary for a section: a miss is a miss.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import date
from enum import Enum
from pathlib import Path
from typing import Any

HISTORY_DIR = "authorities/history"
CHANGES_FILE = "authorities/changes.json"
# What ``jason law-history --versions`` read from lawlibrary, by citation: each version's digest, act, and range.
VERSIONS_FILE = "authorities/history/versions.json"
# The fewest characters of a digest a record may carry and still be matched against the full digest.
MIN_DIGEST = 12

_NOTE = re.compile(r"^- History:\s*(.*)$")
# A code, a section number (dotted, with the letter some sections end in: "2924a"), and any subdivisions.
_CITATION = re.compile(r"^\s*(?:(\d+)[\s-]+)?([A-Za-z]{2,5})[\s-]*(?:section\s+|§\s*)?(\d+(?:\.\d+)*[a-z]?)\s*((?:\([^)]*\))*)\s*$",
                       re.IGNORECASE)
_HEX = re.compile(r"^[0-9a-f]+$")


def normal_citation(citation: str) -> tuple[str, str] | None:
    """A statute citation as the shelf's headings write it, with any subdivision apart: "civ-5855" and "CIV 5855(a)"
    give ("CIV 5855", "") and ("CIV 5855", "(a)"); "10-CCR-2792.23" gives ("10 CCR 2792.23", ""). None when the text
    is not a code and a section number."""
    m = _CITATION.match(citation or "")
    if not m:
        return None
    code = (m.group(1) + " " if m.group(1) else "") + m.group(2).upper()
    return f"{code} {m.group(3).lower()}", m.group(4) or ""


def slug(citation: str) -> str:
    """A citation as a folder name: "CIV 5855" is "CIV-5855"."""
    return re.sub(r"[^A-Za-z0-9.]+", "-", citation).strip("-")


def split_note(body: str) -> tuple[str, str]:
    """A section's body as (its words, jason's History note). The note is the ``- History:`` line the export writes
    first under the heading; everything else is the words, with line endings and trailing spaces normalized and the
    blank lines at either end dropped."""
    lines = [line.rstrip() for line in (body or "").replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    while lines and not lines[0]:
        lines.pop(0)
    note = ""
    if lines:
        m = _NOTE.match(lines[0])
        if m:
            note = m.group(1).strip()
            lines.pop(0)
    while lines and not lines[0]:
        lines.pop(0)
    while lines and not lines[-1]:
        lines.pop()
    return "\n".join(lines), note


def section_words(body: str) -> str:
    """The words a digest is taken over (``split_note`` without the note)."""
    return split_note(body)[0]


def words_digest(body: str) -> str:
    """The SHA-256 of a section's words, as hex. Two bodies that differ only in line endings, trailing spaces, or the
    History note have the same digest."""
    return hashlib.sha256(section_words(body).encode("utf-8")).hexdigest()


def same_digest(recorded: str, now: str) -> bool:
    """Whether a digest a record carries names the words whose digest is ``now``. A record may carry the leading
    ``MIN_DIGEST`` or more characters."""
    recorded, now = (recorded or "").strip().lower(), (now or "").strip().lower()
    return len(recorded) >= MIN_DIGEST and bool(_HEX.match(recorded)) and bool(now) and now.startswith(recorded)


def split_page(text: str) -> tuple[str, list[tuple[str, str]]]:
    """A page as (its header, each section's heading and body), split where ``law_corpus`` splits it."""
    blocks = (text or "").replace("\r\n", "\n").split("\n## ")
    sections = []
    for block in blocks[1:]:
        head, _, body = block.partition("\n")
        sections.append((head.strip(), body))
    return blocks[0], sections


def source_line(header: str) -> str:
    """The page's ``- Source:`` line: who published the words, and the session."""
    for line in header.split("\n"):
        if line.startswith("- Source:"):
            return line[len("- Source:"):].strip()
    return ""


@dataclass(frozen=True)
class LawText:
    """One section's words as the shelf holds or held them."""

    citation: str               # "CIV 5855"
    words: str                  # verbatim, as hashed
    digest: str
    source: str = ""            # the page's Source line ("California Legislature, 2025 session publication, ...")
    session: str = ""
    page: str = ""              # the file under the data folder that holds or held it
    note: str = ""              # jason's History note, not part of the words
    current: bool = True        # False for words read from the history: an export replaced them, or an earlier version
    replaced: str = ""          # the day an export replaced them, for a historical text
    # The range the words were in force, where a record says it (an earlier version's header, or the versions ledger).
    # Days are ISO; "" is not recorded, never a guess.
    act: str = ""               # the act that made them ("Stats. 2012, Ch. 180, Sec. 2 (AB 805)")
    start: str = ""             # the day they came into force
    # Where the Legislature's note names no day and the act is older than the first session publication on the shelf:
    # the first day of that publication's session, by which the publications show these were the section's words.
    floor: str = ""
    until: str = ""             # the day they ceased to be the section's words; "" for words still in force too
    until_by: str = ""          # what ended them: the next act, or their own provisions
    credit: str = ""            # the Legislature's history note, as its table printed it beside the section
    editions: tuple[str, ...] = ()   # the session publications that printed them
    added: str = ""             # for a version a person added by hand: who, and when


def page_sections(root: Path, page: Any) -> list[LawText]:
    """Each section a manifest page holds, in order. Nothing when the file is not on disk."""
    path = Path(root) / page.file
    if not path.is_file():
        return []
    header, sections = split_page(path.read_text(encoding="utf-8", errors="ignore"))
    source = source_line(header)
    out = []
    for head, body in sections:
        words, note = split_note(body)
        out.append(LawText(head, words, hashlib.sha256(words.encode("utf-8")).hexdigest(), source, page.session,
                           page.file, note))
    return out


def _pages(root: Path) -> tuple[Any, ...]:
    from jason.tasks.export_authorities import authority_pages, on_demand_pages

    return (*authority_pages(Path(root)), *on_demand_pages(Path(root)))


def shelf_sections(root: Path) -> list[LawText]:
    """Every section on the shelf: the curated pages, then the pages fetched on demand, each as its page holds it. A
    section two pages hold, or one page holds in two versions, comes back each time."""
    out: list[LawText] = []
    for page in _pages(root):
        out += page_sections(Path(root), page)
    return out


def versions(citation: str, data_dir: Path) -> list[LawText]:
    """Every text the shelf holds under a section's citation, in the shelf's order (the curated pages, then those
    fetched on demand), each digest once. Usually one; two when the publication prints two versions of the section.
    Empty when the section is not on the shelf."""
    found = normal_citation(citation)
    if found is None:
        return []
    code, _, number = found[0].rpartition(" ")
    out: list[LawText] = []
    for page in _pages(Path(data_dir)):
        if page.code != code or (page.sections and number not in page.sections):
            continue
        for text in page_sections(Path(data_dir), page):
            if text.citation == found[0] and all(text.digest != other.digest for other in out):
                out.append(text)
    return out


def history_dir(root: Path, citation: str) -> Path:
    return Path(root) / HISTORY_DIR / slug(citation)


_ISO = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def iso_day(text: str) -> str:
    """The ISO day a header line or a ledger row starts with, or "" when it records none ("not recorded")."""
    word = (text or "").strip().split(" ", 1)[0]
    if not _ISO.match(word):
        return ""
    try:
        date.fromisoformat(word)
    except ValueError:
        return ""
    return word


def header_fields(header: str) -> dict[str, str]:
    """A history file's header lines (``- Name: value``) by name."""
    return {k.strip(): v.strip() for k, _, v in (line[2:].partition(":") for line in header.split("\n")
                                                 if line.startswith("- "))}


def version_ledger(data_dir: Path, citation: str) -> dict[str, Any]:
    """What ``jason law-history --versions`` recorded for one section: the day lawlibrary was read (``read``), the
    session publications it holds for the code (``editions``) and those that print the section (``printed``), and
    each version's ``digest``, ``act``, ``from`` and ``until``. Empty when the section was never read."""
    found = normal_citation(citation)
    path = Path(data_dir) / VERSIONS_FILE
    if found is None or not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8") or "{}")
    except json.JSONDecodeError:
        return {}
    row = (data.get("sections") or {}).get(found[0])
    return row if isinstance(row, dict) else {}


def history_texts(citation: str, data_dir: Path) -> list[LawText]:
    """The words the history holds for one section: those an export replaced, and the earlier versions fetched or
    added by hand, oldest first (by the day they came into force, then the day replaced). Each file is read and
    hashed again, so a text is only ever returned under the digest its words have now. A range comes from the file's
    own header (``From``, ``Until``), else from the versions ledger's row for the same digest; "" is not recorded."""
    found = normal_citation(citation)
    if found is None:
        return []
    folder = history_dir(Path(data_dir), found[0])
    if not folder.is_dir():
        return []
    recorded = {str(r.get("digest") or ""): r for r in version_ledger(Path(data_dir), found[0]).get("versions") or []}
    out = []
    for path in folder.glob("*.md"):
        header, sections = split_page(path.read_text(encoding="utf-8", errors="ignore"))
        fields = header_fields(header)
        for head, body in sections:
            if head != found[0]:
                continue
            words = section_words(body)
            digest = hashlib.sha256(words.encode("utf-8")).hexdigest()
            row = recorded.get(digest, {})
            editions = fields.get("Editions") or ", ".join(str(e) for e in row.get("editions") or [])
            out.append(LawText(
                head, words, digest, fields.get("Source", ""), fields.get("Session", ""), fields.get("Page", ""),
                fields.get("History", ""), False, fields.get("Replaced", "").split(" ", 1)[0],
                act=fields.get("Act") or str(row.get("act") or ""),
                start=iso_day(fields.get("From", "")) or iso_day(str(row.get("from") or "")),
                floor=iso_day(fields.get("Printed by", "")) or iso_day(str(row.get("floor") or "")),
                until=iso_day(fields.get("Until", "")) or iso_day(str(row.get("until") or "")),
                until_by=fields.get("Until by") or str(row.get("until_by") or ""),
                credit=fields.get("Legislature's note") or str(row.get("note") or ""),
                editions=tuple(e.strip() for e in editions.split(",") if e.strip()),
                added=fields.get("Added by hand", "")))
    return sorted(out, key=lambda t: (t.start, t.replaced, t.digest))


def law_text(citation: str, data_dir: Path, digest: str | None = None, *, as_of: date | None = None) -> LawText | None:
    """A section's words: the current ones (the first version, when the shelf holds two), or with ``digest`` the
    words that have it (a version on the shelf, else a text the history holds), or with ``as_of`` the words in force
    on that day where the disk shows which they were (``in_force``). None when the section is not on the shelf, no
    text held has that digest, or the disk does not show which words governed that day."""
    if digest is None and as_of is not None:
        return in_force(citation, Path(data_dir), as_of).text
    now = versions(citation, Path(data_dir))
    if digest is None:
        return now[0] if now else None
    held = next((t for t in now if same_digest(digest, t.digest)), None)
    if held is not None:
        return held
    return next((t for t in history_texts(citation, Path(data_dir)) if same_digest(digest, t.digest)), None)


# --- The words in force on a day --------------------------------------------------------------------------------------

_MONTHS = ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
           "November", "December")
_DAY = r"(?P<month>" + "|".join(_MONTHS) + r")\s+(?P<day>\d{1,2}),\s+(?P<year>\d{4})"
# To the end of the sentence: a period inside a section number ("Section 2924.5") does not end it.
_REST = r"(?:[^.]|\.(?=\d))*\."
# What a section says of itself. Only a sentence whose subject is the section: "The amendments made to this section
# ... shall become operative on" speaks of an amendment, and is not read.
_OWN_UNTIL = tuple(re.compile(p + _DAY + _REST) for p in (
    r"This section shall remain in effect only until ",
    r"This section shall remain operative only until ",
    r"This section shall (?:become|be) inoperative (?:on |as of )?",
    r"This section (?:is|shall be) repealed (?:on|as of|effective) ",
))
_OWN_FROM = tuple(re.compile(p + _DAY + _REST) for p in (
    r"This section shall (?:become|be) operative (?:on |as of )?",
    r"This section (?:becomes|is) operative (?:on |as of )?",
))
# The credit the publication prints as a section's first line: "5855. (Amended by Stats. 2025, Ch. 22, Sec. 4.)".
_CREDIT = re.compile(r"^(?:\d+(?:\.\d+)*[a-z]?\.\s*)?\((?:Added|Amended|Repealed|Enacted|Renumbered)\b.*\)\s*$")


@dataclass(frozen=True)
class OwnWords:
    """What a section's own words say of when it operates: each day, with the sentence that states it."""

    start: str = ""              # "This section shall be operative January 1, 2031."
    start_quote: str = ""
    until: str = ""              # "This section shall remain in effect only until January 1, 2031, and as of that date is repealed."
    until_quote: str = ""

    @property
    def stated(self) -> bool:
        return bool(self.start or self.until)


def _stated(patterns: tuple[re.Pattern[str], ...], flat: str) -> list[tuple[str, str]]:
    out = []
    for pattern in patterns:
        for m in pattern.finditer(flat):
            try:
                day = date(int(m.group("year")), _MONTHS.index(m.group("month")) + 1, int(m.group("day")))
            except ValueError:
                continue
            out.append((day.isoformat(), m.group(0).strip()))
    return out


def own_operative(words: str) -> OwnWords:
    """The operative days a section's own words state: the day it becomes operative, and the day it stops (repealed,
    inoperative, in effect "only until"). The earliest stated end and the latest stated start, each with its sentence.
    Nothing when the words state none: jason reads the sentence and never infers a day."""
    flat = " ".join((words or "").split())
    ends, starts = sorted(_stated(_OWN_UNTIL, flat)), sorted(_stated(_OWN_FROM, flat))
    until, until_quote = ends[0] if ends else ("", "")
    start, start_quote = starts[-1] if starts else ("", "")
    return OwnWords(start, start_quote, until, until_quote)


def credit_line(words: str) -> str:
    """The credit the publication prints as the section's first line ("(Amended by Stats. 2025, Ch. 22, Sec. 4.)"),
    or "" when the first line is not one."""
    first = (words or "").split("\n", 1)[0].strip()
    return first if _CREDIT.match(first) else ""


def _body(words: str) -> str:
    """A section's words without the publication's credit line, spacing aside: what two prints are compared by."""
    credit = credit_line(words)
    return " ".join((words.split("\n", 1)[1] if credit and "\n" in words else "" if credit else words).split())


def made_year(words: str) -> int | None:
    """The year of the latest statute the section's credit line names: the words cannot be older than that act."""
    years = [int(y) for y in re.findall(r"Stats\. (\d{4})", credit_line(words))]
    return max(years) if years else None


class Decided(Enum):
    """How ``in_force`` knows which words governed on a day."""

    PRIOR = "prior"              # an earlier version on disk whose recorded range holds the day
    CURRENT = "current"          # the words on the shelf now: a record says they were in force by that day
    OWN_WORDS = "own_words"      # one of several versions under the number, picked by the versions' own operative words
    NOT_SHOWN = "not_shown"      # the disk does not show which words governed that day: nothing is picked


@dataclass(frozen=True)
class InForce:
    """Which words of a section were in force on a day, as far as the disk shows."""

    citation: str
    day: date
    decided: Decided
    text: LawText | None = None          # the words in force that day; None when the disk does not show which
    basis: str = ""                      # how it is known, in a sentence
    quotes: tuple[str, ...] = ()         # the section's own words that decide it
    caveats: tuple[str, ...] = ()
    current: tuple[LawText, ...] = ()    # the versions on the shelf now
    earlier: tuple[LawText, ...] = ()    # the earlier versions the history holds

    @property
    def shown(self) -> bool:
        return self.decided is not Decided.NOT_SHOWN


@dataclass(frozen=True)
class _Out:
    """A version on the shelf that was not in force on the day, and why."""

    text: LawText
    why: str = ""                # completes "the words on the shelf now (digest ...) ..."
    quote: str = ""              # the version's own sentence that says so
    whole: str = ""              # or the reason as a sentence of its own (a later act the Act's history names)

    def sentence(self, subject: str) -> str:
        if self.whole:
            return self.whole
        return (f"{subject} (digest {self.text.digest[:MIN_DIGEST]}) {self.why}"
                + (f": \"{self.quote}\"" if self.quote else ""))


def range_words(text: LawText) -> str:
    """A version's recorded range in words: "from 2014-01-01 until 2025-06-30; made by ...; ended by ..."."""
    out = f"from {text.start}" if text.start else "from a day not recorded"
    if not text.start and text.floor:
        out += f" (the session publications show them as the section's words by {text.floor})"
    if text.until:
        out += f" until {text.until}"
    if text.act:
        out += f"; made by {text.act}"
    if text.until and text.until_by:
        out += f"; ended by {text.until_by}"
    return out


def _published(root: Path) -> dict[str, str]:
    """Each page of the shelf with the day jason took it from the publication."""
    from jason.tasks.export_authorities import read_manifest

    manifest = read_manifest(root)
    out = {str(p.get("file") or ""): str(manifest.get("exported") or "") for p in manifest.get("pages") or []}
    out.update({str(p.get("file") or ""): str(p.get("fetched") or "") for p in manifest.get("on_demand") or []})
    return out


def _later_acts(root: Path, citation: str, day: str) -> list[dict[str, Any]]:
    """The changes the Act's amendment history (``jason law-history --export``) places after a day."""
    code, _, number = citation.rpartition(" ")
    if code != "CIV":
        return []
    from jason.community.succession import changes as amendments

    return [c for c in amendments(root, number) if str(c.get("operative") or "") > day]


def _fetch_hint(citation: str, ledger: dict[str, Any], stale: bool = False) -> str:
    """What would bring the missing words: the fetch (again, when the shelf changed since it ran), or after it a
    person with an official source."""
    if not ledger:
        return (f"jason law-history --versions --citation {slug(citation)} reads the earlier session publications "
                "lawlibrary holds, with each version's range")
    if stale:
        return (f"the words on the shelf changed since the versions were read on {ledger.get('read') or 'a day not recorded'}: "
                f"jason law-history --versions --citation {slug(citation)} reads them again and records the ranges")
    printed = [str(e) for e in ledger.get("printed") or []]
    span = f"the {printed[0]} to {printed[-1]} session publications print it" if printed else "none prints it"
    return (f"lawlibrary's session publications were read on {ledger.get('read') or 'a day not recorded'} ({span}); "
            "words they do not hold are added by a person from an official source (docs/law-readings.md)")


def in_force(citation: str, data_dir: Path, as_of: date) -> InForce:
    """Which words of a section were in force on a day, read from the disk only, and how it is known.

    1. An earlier version in the history whose recorded range holds the day (``PRIOR``).
    2. Else the words on the shelf now, where a record says they were in force by then (``CURRENT``): the versions
       ledger's day for these words, the section's own operative words, or, for a day on or after the day jason took
       the page from the publication, the publication itself.
    3. Where the publication prints several versions under the number, the one their own operative words pick
       (``OWN_WORDS``), each deciding sentence quoted. Never by position.

    Anything else is ``NOT_SHOWN``: no words are picked, and the caveats say what is missing and what would bring
    it. A version is never picked by inference: a day that is not recorded is not recorded."""
    root = Path(data_dir)
    found = normal_citation(citation)
    if found is None:
        return InForce(citation, as_of, Decided.NOT_SHOWN, basis="say a code and a section, such as CIV 5855")
    base, day = found[0], as_of.isoformat()
    now = tuple(versions(base, root))
    earlier = tuple(t for t in history_texts(base, root) if all(t.digest != v.digest for v in now))
    ledger = version_ledger(root, base)
    caveats: list[str] = []

    covering = [t for t in earlier if (t.start or t.floor) and t.until and (t.start or t.floor) <= day < t.until]
    if len(covering) > 1 and len({_body(t.words) for t in covering}) == 1:
        # The publications print some sections twice with identical words, each under its own act ("See identical
        # section added by ..."): the words are one, whichever credit they carry.
        caveats.append(f"the publications print these words {len(covering)} times, each under its own credit line "
                       f"(digests {', '.join(t.digest[:MIN_DIGEST] for t in covering)}); the words are the same")
        covering = covering[:1]
    if len(covering) == 1:
        text = covering[0]
        if text.editions and text.editions[-1].isdigit() and day > f"{int(text.editions[-1]) + 1}-12-31":
            last = int(text.editions[-1])
            caveats.append(f"{day} is after the last session publication that printed these words (the {last} session's, "
                           f"which covers {last} and {last + 1}) and before the next act jason knows ({text.until}): an "
                           "act between the two that a later one overwrote would not show in the publications")
        if text.added:
            caveats.append(f"this version was added by hand ({text.added}); its range and source are as that person "
                           "recorded them")
        return InForce(base, as_of, Decided.PRIOR, text, range_words(text), (), tuple(caveats), now, earlier)
    if len(covering) > 1:
        names = ", ".join(f"{t.digest[:MIN_DIGEST]} ({range_words(t)})" for t in covering)
        caveats.append(f"jason holds {len(covering)} earlier versions of {base} whose recorded ranges each include "
                       f"{day}: {names}; a person reads which governed")

    rows = {str(r.get("digest") or ""): r for r in ledger.get("versions") or []}
    stale = bool(ledger) and any(v.digest not in rows for v in now)      # an export changed the shelf since the fetch
    published = _published(root)
    later = _later_acts(root, base, day)
    live: list[tuple[LawText, str, tuple[str, ...]]] = []      # the text, how it is known, its own deciding sentences
    unknown: list[tuple[LawText, OwnWords]] = []
    out: list[_Out] = []
    for v in ([] if len(covering) > 1 else now):
        own, row = own_operative(v.words), rows.get(v.digest, {})
        start = max(iso_day(str(row.get("from") or "")), own.start)
        until = min((d for d in (iso_day(str(row.get("until") or "")), own.until) if d), default="")
        by = "its own provisions" if until and until == own.until else str(row.get("until_by") or "")
        floor = "" if start else iso_day(str(row.get("floor") or ""))
        text = LawText(v.citation, v.words, v.digest, v.source, v.session, v.page, v.note, True, "",
                       act=str(row.get("act") or ""), start=start, floor=floor, until=until, until_by=by,
                       credit=str(row.get("note") or ""), editions=tuple(str(e) for e in row.get("editions") or []))
        year = made_year(v.words)
        if start and day < start:
            out.append(_Out(text, f"came into force on {start}, after {day}", own.start_quote if start == own.start else ""))
        elif until and day >= until:
            out.append(_Out(text, f"ceased on {until}, not after {day}", own.until_quote if until == own.until else ""))
        elif not start and later:
            c = later[-1]
            out.append(_Out(text, whole=f"{c.get('change') or 'changed'} by {c.get('statute') or 'a later act'}, operative "
                                        f"{c.get('operative')}, after {day}: the words on disk may differ from the words "
                                        "in force on that day"))
        elif not start and year is not None and year > as_of.year:
            out.append(_Out(text, f"cannot be the words of {day}: the credit line names Stats. {year} "
                                  f"(\"{credit_line(v.words)}\")"))
        elif start or (floor and day >= floor):
            live.append((text, range_words(text), tuple(q for q in (own.start_quote, own.until_quote) if q)))
        elif published.get(v.page) and day >= published[v.page]:
            live.append((text, f"the publication jason took on {published[v.page]} prints these words, and nothing on "
                               "disk is later", tuple(q for q in (own.until_quote,) if q)))
        else:
            unknown.append((text, own))

    several = len(now) > 1
    if len(live) > 1 and not unknown and len({_body(t.words) for t, _, _ in live}) == 1:
        caveats.append(f"the shelf holds these words {len(live)} times, each under its own credit line (digests "
                       f"{', '.join(t.digest[:MIN_DIGEST] for t, _, _ in live)}); the words are the same")
        live = live[:1]
    if len(live) == 1 and not unknown:
        text, how, quotes = live[0]
        caveats += [o.sentence("the other version the shelf holds under the number") for o in out]
        quotes = (*quotes, *(o.quote for o in out if o.quote))
        if several and quotes:
            basis = (f"of the {len(now)} versions the shelf holds under the number, the versions' own words place this "
                     f"one in force on {day}; {how}")
            return InForce(base, as_of, Decided.OWN_WORDS, text, basis, quotes, tuple(caveats), now, earlier)
        return InForce(base, as_of, Decided.CURRENT, text, how, quotes, tuple(caveats), now, earlier)
    if several and not live and len(unknown) == 1 and out and all(o.quote for o in out) and unknown[0][1].until_quote:
        # Every other version is out by its own words, and this one's own words keep it in effect past the day.
        text, own = unknown[0]
        caveats += [o.sentence("the other version the shelf holds under the number") for o in out]
        credit = credit_line(text.words)
        caveats.append("jason has no record of the day these words came into force"
                       + (f" (their credit line: \"{credit}\")" if credit else "")
                       + f"; if that day is after {day}, earlier words governed. {_fetch_hint(base, ledger, stale)}")
        basis = (f"of the {len(now)} versions the shelf holds under the number, the versions' own words leave this one "
                 f"in effect on {day}")
        return InForce(base, as_of, Decided.OWN_WORDS, text, basis, (own.until_quote, *(o.quote for o in out)),
                       tuple(caveats), now, earlier)

    caveats += [o.sentence("the words on the shelf now") for o in out]
    for text, _own in unknown:
        credit = credit_line(text.words)
        caveats.append(f"jason has no record of the day the words on the shelf (digest {text.digest[:MIN_DIGEST]}) came "
                       "into force" + (f"; their credit line: \"{credit}\"" if credit else ""))
    if len(live) > 1:
        caveats.append(f"the shelf holds {len(live)} versions that the disk each places in force on {day}; their own "
                       "words do not decide between them")
    for text in ([] if len(covering) > 1 else earlier[:6]):
        caveats.append(f"an earlier version is held (digest {text.digest[:MIN_DIGEST]}): "
                       + (f"in force {range_words(text)}, which does not include {day}"
                          if (text.start or text.floor) and text.until
                          else f"its range is not recorded in full ({range_words(text)})"))
    if not now:
        basis = (f"{base} is not on the shelf (jason cite or jason export-authorities brings its current words down), and "
                 + (f"no earlier version's recorded range includes {day}" if earlier else "the history holds no earlier version"))
    else:
        basis = f"the disk does not show which words of {base} were in force on {day}"
    caveats.append(f"the words in force on {day} are not held as such. {_fetch_hint(base, ledger, stale)}")
    return InForce(base, as_of, Decided.NOT_SHOWN, None, basis, (), tuple(caveats), now, earlier)


def section_digest(citation: str, data_dir: Path) -> str | None:
    """The digest of a section's words as they are on disk now (the first version, when the shelf holds two), or None
    when the section is not on the shelf."""
    now = versions(citation, Path(data_dir))
    return now[0].digest if now else None


def changes(data_dir: Path, citation: str = "") -> list[dict[str, Any]]:
    """The shelf's own change log, oldest first: each time an export replaced a section's words (``citation``, the
    ``old`` and ``new`` digests, ``when``, and the old and new source lines). One section's rows with ``citation``."""
    path = Path(data_dir) / CHANGES_FILE
    if not path.is_file():
        return []
    try:
        rows = json.loads(path.read_text(encoding="utf-8") or "[]")
    except json.JSONDecodeError:
        return []
    if citation:
        found = normal_citation(citation)
        rows = [r for r in rows if found is not None and r.get("citation") == found[0]]
    return rows


__all__ = ["CHANGES_FILE", "Decided", "HISTORY_DIR", "InForce", "LawText", "MIN_DIGEST", "OwnWords", "VERSIONS_FILE",
           "changes", "credit_line", "header_fields", "history_dir", "history_texts", "in_force", "iso_day", "law_text",
           "made_year", "normal_citation", "own_operative", "page_sections", "range_words", "same_digest",
           "section_digest", "section_words", "shelf_sections", "slug", "source_line", "split_note", "split_page",
           "version_ledger", "versions", "words_digest"]
