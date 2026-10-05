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
under the same number. ``versions`` gives every one. The publication's order is not the order they operate in, so a
reader never quotes "the first": ``quoted`` says which version is in force on a day by the versions' own operative
words, quoting them, or that nothing decides and every version is to be shown. ``authority_text``, ``jason cite``,
the packets, and the context pack quote through it. ``law_text`` and ``section_digest`` with no digest and no day
give the first print: a handle for a record to compare digests with, not a quotation of the law.

A section's number may end in a letter ("CIV 2924a"): the letter is part of the number, and the section is its own
heading on the page. A citation is read by the one grammar (``references.statute_citation``); the shelf's own section
lists (``shelf_numbers``) say whether a lettered number is a section at all.

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
_HEX = re.compile(r"^[0-9a-f]+$")


def normal_citation(citation: str) -> tuple[str, str] | None:
    """A statute citation as the shelf's headings write it, with any subdivision apart: "civ-5855" and "CIV 5855(a)"
    give ("CIV 5855", "") and ("CIV 5855", "(a)"); "CIV 2924f" keeps its letter; "10-CCR-2792.23" gives
    ("10 CCR 2792.23", ""). None when the text is not a code and a section number. Read by the one citation grammar
    (``references.statute_citation``)."""
    from jason.community.references import statute_citation

    found = statute_citation(citation)
    return (found.base, found.subdivisions) if found is not None else None


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


def shelf_numbers(root: Path) -> dict[str, frozenset[str]]:
    """Each code's section numbers as the shelf's own pages list them (the manifest's ``sections``; a page that lists
    none is read for its headings). This list, not a page's span, says whether a number is a section the shelf
    holds: "2924a" is one where a page lists it, and "5855a" is not where the page lists only 5855."""
    out: dict[str, set[str]] = {}
    for page in _pages(Path(root)):
        numbers = list(page.sections) or [t.citation.rpartition(" ")[2] for t in page_sections(Path(root), page)]
        out.setdefault(page.code, set()).update(str(n) for n in numbers)
    return {code: frozenset(numbers) for code, numbers in out.items()}


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


@dataclass(frozen=True)
class Quoted:
    """What a reader quotes of a section on a day, of the texts the shelf holds under its number, and why.

    One text on the shelf is that text, with no note. Of several, ``text`` is the one in force on the day where the
    disk decides it (``in_force``: the versions' own operative words, or a recorded range) and ``note`` says which it
    is and why, with the deciding words. Where nothing decides, ``text`` is None: the reader shows every version,
    each under its ``label``. Never the first by position."""

    citation: str
    day: date
    held: tuple[LawText, ...] = ()       # every version on the shelf, in the publication's order
    text: LawText | None = None          # the one to quote; None when the shelf holds none, or several and nothing decides
    decided: Decided | None = None       # how it was picked among several; None when the shelf holds one or none
    note: str = ""                       # which version is quoted and why, in a sentence; "" when the shelf holds one
    quotes: tuple[str, ...] = ()         # the versions' own words that decide it
    caveats: tuple[str, ...] = ()        # what else ``in_force`` said of the day
    whys: tuple[tuple[str, str], ...] = ()   # each version's digest with why it is, or is not, the one in force

    @property
    def several(self) -> bool:
        return len(self.held) > 1

    @property
    def undecided(self) -> bool:
        """The shelf holds several versions and the disk does not show which is in force on the day."""
        return self.several and self.text is None

    def label(self, digest: str) -> str:
        """One version's label, as jason's own words beside the law's: its place in the publication's order, its
        digest, and whether it is the one in force on the day, with why. "" when the shelf holds one version."""
        if not self.several:
            return ""
        place = next((n for n, v in enumerate(self.held, 1) if v.digest == digest), 0)
        if not place:
            return ""
        day, why = self.day.isoformat(), dict(self.whys).get(digest, "")
        head = (f"version {place} of {len(self.held)} the publication prints under {self.citation} "
                f"(digest {digest[:MIN_DIGEST]})")
        if self.text is None:
            return f"{head}; the disk does not show which version is in force on {day}" + (f": {why}" if why else "")
        if self.text.digest == digest:
            return f"{head}; the one in force on {day}" + (f": {why}" if why else "")
        return f"{head}; not in force on {day}" + (f": {why}" if why else "")

    def labels(self) -> dict[str, str]:
        """Each version's digest with its label; empty when the shelf holds one version."""
        return {v.digest: self.label(v.digest) for v in self.held} if self.several else {}

    def as_dict(self) -> dict[str, Any]:
        return {"asOf": self.day.isoformat(), "decided": self.decided.value if self.decided else "",
                "digest": self.text.digest if self.text else "", "note": self.note, "quotes": list(self.quotes),
                "caveats": list(self.caveats),
                "versions": [{"digest": v.digest, "quoted": self.text is None or v.digest == self.text.digest,
                              "label": self.label(v.digest)} for v in self.held]}


def quoted(citation: str, data_dir: Path, day: date | None = None) -> Quoted:
    """Which of the texts the shelf holds under a section's number a reader quotes on ``day`` (today unless given),
    and why. Reads the disk only.

    A section printed once is that print. Printed in several versions, it is the one ``in_force`` places in force on
    the day, and the note quotes the words that decide it ("This section shall remain in effect only until January 1,
    2031 ..." against "This section shall be operative January 1, 2031."). Where the disk does not decide, nothing is
    picked and the reader shows every version: the publication's order is not the order they operate in."""
    day = day or date.today()
    found = normal_citation(citation)
    if found is None:
        return Quoted(citation, day)
    base, iso = found[0], day.isoformat()
    held = tuple(versions(base, Path(data_dir)))
    if len(held) <= 1:
        return Quoted(base, day, held, held[0] if held else None)
    got = in_force(base, Path(data_dir), day)
    picked = next((v for v in held if got.text is not None and v.digest == got.text.digest), None)
    other = "the other version the shelf holds under the number"
    whys: dict[str, str] = {}
    rest: list[str] = []
    for caveat in got.caveats:
        about = next((v for v in held if f"(digest {v.digest[:MIN_DIGEST]})" in caveat), None)
        if about is None or about.digest in whys or (picked is not None and about.digest == picked.digest):
            rest.append(caveat)
            continue
        lead = f"{other} (digest {about.digest[:MIN_DIGEST]}) "
        whys[about.digest] = "it " + caveat[len(lead):] if caveat.startswith(lead) else caveat
    count = f"{base} is printed in {len(held)} versions under the one number"
    if picked is None:
        why = got.basis
        if got.text is not None:
            why = (f"an earlier version jason holds (digest {got.text.digest[:MIN_DIGEST]}) is recorded in force on {iso} "
                   f"({got.basis}), and it is neither print on the shelf")
        note = (f"{count}, and the disk does not show which is in force on {iso}: {why}. Every version is quoted, each "
                "with its digest, in the publication's order, which is not the order they operate in")
        return Quoted(base, day, held, None, Decided.NOT_SHOWN, note, (), tuple(rest), tuple(whys.items()))
    own = own_operative(picked.words)
    mine = tuple(q for q in (own.until_quote, own.start_quote) if q and q in got.quotes)
    said = f"of the {len(held)} versions the shelf holds under the number, the versions' own words place this one in force on {iso}; "
    basis = "by the versions' own words; " + got.basis[len(said):] if got.basis.startswith(said) else got.basis
    whys[picked.digest] = basis + "".join(f"; its own words: \"{q}\"" for q in mine)
    place = held.index(picked) + 1
    note = (f"{count}. Version {place} in the publication's order (digest {picked.digest[:MIN_DIGEST]}) is the one "
            f"in force on {iso}: {whys[picked.digest]}")
    for n, v in enumerate(held, 1):
        if v.digest != picked.digest and whys.get(v.digest):
            note += f". Version {n} (digest {v.digest[:MIN_DIGEST]}): {whys[v.digest]}"
    return Quoted(base, day, held, picked, got.decided, note, got.quotes, tuple(rest), tuple(whys.items()))


# --- The version of a section on a day, with every version held ---------------------------------------------------------

NOT_RESTATEMENT = ("jason's consolidated text is not an official restatement: the words are the Legislature's session "
                   "publication as lawlibrary read it, or a version a person added from an official source, never the "
                   "chaptered act. Where the exact enacted text matters, counsel reads the Statutes.")


@dataclass(frozen=True)
class Held:
    """One version of a section jason holds, on the shelf or in the history, with its recorded range and whether it
    is the one in force on the day asked."""

    digest: str
    current: bool                # on the shelf now
    start: str = ""              # ISO; "" is not recorded
    floor: str = ""
    until: str = ""
    act: str = ""
    source: str = ""
    added: str = ""              # a version a person added by hand: who, and when
    in_force: bool = False       # the version ``version_on`` places in force on the day
    place: str = ""              # "earlier", "later", "in force", or "" where its range does not say

    @property
    def range(self) -> str:
        return range_words(LawText("", "", self.digest, start=self.start, floor=self.floor, until=self.until, act=self.act))

    def as_dict(self) -> dict[str, Any]:
        return {"digest": self.digest, "current": self.current, "from": self.start, "printedBy": self.floor,
                "until": self.until, "act": self.act, "source": self.source, "addedByHand": self.added,
                "inForce": self.in_force, "place": self.place, "range": self.range}


@dataclass(frozen=True)
class VersionOn:
    """The version of a section in force on a day, as far as the disk shows, with the words and every version held.

    ``found`` is True when the disk shows which words governed that day (``in_force``); then ``text`` is that version,
    ``words`` its words whole, and ``subdivision_words`` the words of the subdivision asked, split as jason splits a
    section (``cite.label_text``), or "" when none was asked or it was not found. When ``found`` is False nothing is
    picked: ``reason`` says why, and ``held`` still lists every version with its range for a person to read."""

    citation: str                         # "CIV 5855"
    subdivisions: str                     # "(b)(3)" as asked, or ""
    day: date
    found: bool
    decided: Decided
    text: LawText | None = None
    subdivision_words: str = ""
    basis: str = ""
    quotes: tuple[str, ...] = ()
    caveats: tuple[str, ...] = ()
    held: tuple[Held, ...] = ()           # every version held, oldest first
    reason: str = ""

    @property
    def words(self) -> str:
        return self.text.words if self.text is not None else ""

    @property
    def digest(self) -> str:
        return self.text.digest if self.text is not None else ""

    @property
    def start(self) -> str:
        return self.text.start if self.text is not None else ""

    @property
    def until(self) -> str:
        return self.text.until if self.text is not None else ""

    def label(self) -> str:
        """The version in one line, as a check names it: "the version in force on 2026-01-01 (digest ..., from
        2025-06-30; made by ...)", or that none is shown."""
        day = self.day.isoformat()
        if not self.found:
            return f"no version shown in force on {day}: {self.reason}"
        t = self.text
        return f"the version in force on {day} (digest {t.digest[:MIN_DIGEST]}, {range_words(t)})"

    def as_dict(self) -> dict[str, Any]:
        t = self.text
        return {"citation": self.citation, "subdivisions": self.subdivisions, "asOf": self.day.isoformat(),
                "found": self.found, "decided": self.decided.value, "basis": self.basis, "reason": self.reason,
                "digest": self.digest, "words": self.words, "subdivisionWords": self.subdivision_words,
                "from": self.start, "printedBy": t.floor if t else "", "until": self.until,
                "untilBy": t.until_by if t else "", "act": t.act if t else "", "source": t.source if t else "",
                "current": t.current if t else False, "addedByHand": t.added if t else "",
                "decidingWords": list(self.quotes), "caveats": list(self.caveats),
                "versions": [h.as_dict() for h in self.held]}


def place_of(version: LawText, picked: LawText | None, day: str) -> str:
    """Where a held version stands against the one in force on the day: earlier, later, in force, or "" where its
    recorded range does not say."""
    if picked is not None and version.digest == picked.digest:
        return "in force"
    starts, ends = version.start or version.floor, version.until
    if picked is not None:
        if ends and (picked.start or picked.floor) and ends <= (picked.start or picked.floor):
            return "earlier"
        if starts and picked.until and starts >= picked.until:
            return "later"
    if ends and ends <= day:
        return "earlier"
    if starts and starts > day:
        return "later"
    return ""


def every_version(citation: str, data_dir: Path) -> list[LawText]:
    """Every version of a section jason holds, the shelf's and the history's, each digest once, oldest first by its
    recorded start (the shelf's versions last among those with no start). Reads the disk only."""
    root = Path(data_dir)
    now = versions(citation, root)
    earlier = [t for t in history_texts(citation, root) if all(t.digest != v.digest for v in now)]
    ledger = {str(r.get("digest") or ""): r for r in version_ledger(root, citation).get("versions") or []}
    current: list[LawText] = []
    for v in now:
        row, own = ledger.get(v.digest, {}), own_operative(v.words)
        start = max(iso_day(str(row.get("from") or "")), own.start)
        until = min((d for d in (iso_day(str(row.get("until") or "")), own.until) if d), default="")
        current.append(LawText(v.citation, v.words, v.digest, v.source, v.session, v.page, v.note, True, "",
                               act=str(row.get("act") or ""), start=start,
                               floor="" if start else iso_day(str(row.get("floor") or "")), until=until,
                               until_by=str(row.get("until_by") or ""), credit=str(row.get("note") or ""),
                               editions=tuple(str(e) for e in row.get("editions") or [])))
    return sorted(earlier + current, key=lambda t: (t.start or t.floor or "9999", t.current, t.digest))


def version_on(citation: str, data_dir: Path, day: date) -> VersionOn:
    """The version of a section in force on a day, read from the disk only (``in_force``), with its words, the words
    of the subdivision the citation names, its range and act, and every version held with where each stands. A
    citation may carry a subdivision ("CIV 4920(b)(3)"), a lettered number ("CIV 2924f"), or a doubled section
    (one printed in two versions under its number). Writes nothing and asks no network: where the disk does not
    show which words governed, nothing is picked and ``reason`` says what would bring them."""
    root = Path(data_dir)
    found = normal_citation(citation)
    if found is None:
        return VersionOn(citation, "", day, False, Decided.NOT_SHOWN,
                         reason="say a code and a section, such as CIV 5855 or CIV 5855(a)",
                         caveats=(NOT_RESTATEMENT,))
    base, subdivisions = found
    got = in_force(base, root, day)
    picked = got.text
    held = tuple(Held(t.digest, t.current, t.start, t.floor, t.until, t.act, t.source, t.added,
                      picked is not None and t.digest == picked.digest, place_of(t, picked, day.isoformat()))
                 for t in every_version(base, root))
    caveats = [*got.caveats, NOT_RESTATEMENT]
    if picked is None:
        return VersionOn(base, subdivisions, day, False, got.decided, basis=got.basis, caveats=tuple(caveats),
                         held=held, reason=got.basis)
    words = ""
    if subdivisions:
        from jason.community.cite import label_text

        labels = re.findall(r"\(([^)]+)\)", subdivisions)
        words = label_text(picked.words, labels)
        if words:
            caveats.append(f"the words of {subdivisions} are split from the section as jason splits it; the section "
                           "itself is the source")
        else:
            caveats.append(f"{base}{subdivisions}: no paragraph of this version opens with {subdivisions} as jason "
                           "splits the section; the whole section is given")
    return VersionOn(base, subdivisions, day, True, got.decided, picked, words, got.basis, got.quotes, tuple(caveats), held)


def section_digest(citation: str, data_dir: Path) -> str | None:
    """The digest of a section's words as they are on disk now, or None when the section is not on the shelf. Where
    the shelf holds two versions this is the first print's: a handle to compare with, not the version in force
    (``quoted`` says which that is)."""
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


__all__ = ["CHANGES_FILE", "Decided", "HISTORY_DIR", "Held", "InForce", "LawText", "MIN_DIGEST", "NOT_RESTATEMENT",
           "OwnWords", "Quoted", "VERSIONS_FILE", "VersionOn", "changes", "credit_line", "every_version",
           "header_fields", "history_dir", "history_texts", "in_force", "iso_day", "law_text", "made_year",
           "normal_citation", "own_operative", "page_sections", "place_of", "quoted", "range_words", "same_digest",
           "section_digest", "section_words", "shelf_numbers", "shelf_sections", "slug", "source_line", "split_note",
           "split_page", "version_ledger", "version_on", "versions", "words_digest"]
