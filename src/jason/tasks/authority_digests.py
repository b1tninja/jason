"""Keep the shelf's digests and its replaced words: the write side of ``jason.community.law_text``.

``jason export-authorities`` overwrites the statute pages. Before it writes, ``snapshot`` reads every section on the
shelf; after, ``keep_replaced`` compares. A section whose words are no longer on the shelf under its citation is
copied to ``data/authorities/history/<citation>/<digest>.md`` with the source line it carried, and the change is a row
in ``data/authorities/changes.json``. ``page_digests`` gives the digests the manifest records for each page, and
``backfill`` (``jason export-authorities --digests``) writes them for the pages already on disk without asking
lawlibrary for anything.

The history also keeps a section's earlier versions, each with the range it was in force: ``edition_versions`` reads
them out of the session publications' rows (``jason.tasks.statute_fetch.prior_versions`` asks lawlibrary for those),
``keep_versions`` writes each as ``history/<citation>/<digest>.md`` with the act that made it and its range,
``write_ledger`` records every version (the current too) in ``history/versions.json``, and ``add_version`` keeps one a
person read from an official source. ``jason.community.law_text.in_force`` reads them back.

Every function but ``backfill`` and ``add_version`` expects its caller to hold the shelf's store lock
(``export_authorities.STORE_KEY``).
"""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from jason.community.law_text import CHANGES_FILE, LawText, history_dir, normal_citation, page_sections, shelf_sections


def snapshot(root: Path) -> dict[str, list[LawText]]:
    """Every section on the shelf by citation, as the pages hold it now: each citation's texts, each digest once."""
    held: dict[str, list[LawText]] = defaultdict(list)
    for text in shelf_sections(Path(root)):
        if all(text.digest != other.digest for other in held[text.citation]):
            held[text.citation].append(text)
    return dict(held)


def merged(first: dict[str, list[LawText]], second: dict[str, list[LawText]]) -> dict[str, list[LawText]]:
    """Two snapshots as one: each citation's texts from both, each digest once."""
    out = {citation: list(texts) for citation, texts in first.items()}
    for citation, texts in second.items():
        have = out.setdefault(citation, [])
        have += [t for t in texts if all(t.digest != other.digest for other in have)]
    return out


def history_markdown(old: LawText, when: str, new: LawText | None) -> str:
    """A replaced section as its history file keeps it: the header it carried, then its words under its heading."""
    lines = [
        f"# {old.citation}: words an export replaced",
        "",
        f"- Source: {old.source}",
        f"- Session: {old.session}",
        f"- Page: {old.page}",
        f"- Digest: {old.digest}",
        f"- Replaced: {when} " + (f"by {new.digest}" if new is not None else "(no longer on the shelf)"),
    ]
    if old.note:
        lines.append(f"- History: {old.note}")
    return "\n".join([*lines, "", f"## {old.citation}", "", old.words, ""])


def keep_replaced(root: Path, before: dict[str, list[LawText]], *, when: str = "") -> list[dict[str, Any]]:
    """Copy to the history each section in ``before`` whose words the shelf no longer holds, and log each as a row of
    ``changes.json``. Returns the new rows. A text already in the history is not written again; its row is still
    logged, since the shelf changed again. ``new`` is the digest of the words now under the citation: the text that
    was not there before, when there is one; empty when the section is no longer on the shelf."""
    root = Path(root)
    when = when or date.today().isoformat()
    after = snapshot(root)
    rows: list[dict[str, Any]] = []
    for citation, texts in before.items():
        now = after.get(citation) or []
        was = {t.digest for t in texts}
        arrived = [t for t in now if t.digest not in was]
        new = arrived[0] if arrived else now[0] if now else None
        for old in texts:
            if any(old.digest == t.digest for t in now):
                continue
            path = history_dir(root, citation) / f"{old.digest}.md"
            if not path.is_file():
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(history_markdown(old, when, new), encoding="utf-8")
            rows.append({"citation": citation, "old": old.digest, "new": new.digest if new else "", "when": when,
                         "old_source": old.source, "new_source": new.source if new else "",
                         "page": new.page if new else old.page, "history": path.relative_to(root).as_posix()})
    if rows:
        log = root / CHANGES_FILE
        try:
            earlier = json.loads(log.read_text(encoding="utf-8") or "[]") if log.is_file() else []
        except json.JSONDecodeError:
            # An unreadable log is set aside, never overwritten: the rows in it are the only record of those changes.
            log.replace(log.with_name(f"{log.stem}.unreadable-{when}.json"))
            earlier = []
        log.parent.mkdir(parents=True, exist_ok=True)
        log.write_text(json.dumps([*earlier, *rows], indent=1), encoding="utf-8")
    return rows


def page_digests(root: Path, page: Any) -> list[list[str]]:
    """Each section of a page with the digest of its words, as [citation, digest] in the page's order, for the
    manifest. A section the page holds in two versions is there twice."""
    return [[text.citation, text.digest] for text in page_sections(Path(root), page)]


@dataclass
class DigestReport:
    pages: int = 0
    sections: int = 0
    # Pages the manifest lists whose file has no ``## CITATION`` heading.
    no_sections: list[str] = field(default_factory=list)
    # A citation more than one page holds: {"citation", "pages", "same"} (``same``: every copy has the same words).
    duplicates: list[dict[str, Any]] = field(default_factory=list)
    # A citation one page holds more than once, with different words: the publication's two versions of a section.
    versions: list[dict[str, Any]] = field(default_factory=list)
    # What could not be read as the manifest says it should be: a missing file, a heading that is not a citation, a
    # section the manifest lists that the page has no heading for, a heading the manifest does not list.
    unparsed: list[str] = field(default_factory=list)
    # A section whose words no longer have the digests the manifest recorded: its page was changed outside an export.
    drift: list[dict[str, Any]] = field(default_factory=list)
    written: bool = False

    def lines(self) -> list[str]:
        out = [f"{self.sections} sections digested on {self.pages} pages"
               + ("; the manifest now records them" if self.written else "; nothing written")]
        out.append(f"pages with no sections: {len(self.no_sections)}")
        out += [f"  {name}" for name in self.no_sections]
        out.append(f"citations on more than one page: {len(self.duplicates)}")
        out += [f"  {d['citation']}: {', '.join(d['pages'])} ({'the same words' if d['same'] else 'DIFFERENT words'})"
                for d in self.duplicates]
        out.append(f"sections a page holds in more than one version: {len(self.versions)}")
        out += [f"  {v['citation']}: {v['count']} versions in {v['page']} (readers quote the one in force today where "
                "its own words say which, else the first)" for v in self.versions]
        out.append(f"did not parse: {len(self.unparsed)}")
        out += [f"  {item}" for item in self.unparsed]
        out.append(f"changed since the manifest recorded a digest: {len(self.drift)}")
        out += [f"  {d['citation']} ({d['page']}): recorded {_short(d['recorded'])}, now {_short(d['now'])}" for d in self.drift]
        return out


@dataclass(frozen=True)
class _Row:
    file: str
    session: str


def _by_citation(pairs: list[list[str]]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = defaultdict(list)
    for citation, digest in pairs:
        out[citation].append(digest)
    return dict(out)


def _short(digests: list[str]) -> str:
    return ", ".join(d[:12] for d in digests) or "nothing"


def stamp(root: Path, *, write: bool = True) -> DigestReport:
    """Compute each page's section digests from the disk and record them in the manifest (``digests`` on each page
    row). Nothing is fetched and no page is changed. The caller holds the shelf's store lock."""
    from jason.tasks.export_authorities import AUTHORITIES_DIR, MANIFEST, read_manifest

    root = Path(root)
    manifest = read_manifest(root)
    report = DigestReport()
    held: dict[str, list[LawText]] = defaultdict(list)
    for group in ("pages", "on_demand"):
        for row in manifest.get(group) or []:
            report.pages += 1
            name = str(row.get("file") or "")
            if not (root / name).is_file():
                report.unparsed.append(f"{name}: listed in the manifest, not on disk")
                continue
            texts = page_sections(root, _Row(name, str(row.get("session") or "")))
            if not texts:
                report.no_sections.append(name)
            code = str(row.get("code") or "")
            listed = {f"{code} {n}" for n in row.get("sections") or []}
            for text in texts:
                if normal_citation(text.citation) != (text.citation, ""):
                    report.unparsed.append(f"{name}: heading \"## {text.citation}\" is not a code and a section number")
                elif listed and text.citation not in listed:
                    report.unparsed.append(f"{name}: has {text.citation}, which the manifest does not list for it")
                if not text.words:
                    report.unparsed.append(f"{name}: {text.citation} has no words under its heading")
            seen = Counter(text.citation for text in texts)
            for citation in sorted(listed - set(seen)):
                report.unparsed.append(f"{name}: the manifest lists {citation}; the page has no heading for it")
            for citation, count in seen.items():
                if count > 1:
                    words = {t.digest for t in texts if t.citation == citation}
                    if len(words) > 1:
                        report.versions.append({"citation": citation, "page": name, "count": len(words)})
                    else:
                        report.unparsed.append(f"{name}: has {citation} {count} times with the same words")
            now = [[text.citation, text.digest] for text in texts]
            recorded = [list(pair) for pair in row.get("digests") or []]
            if recorded and recorded != now:
                was, are = _by_citation(recorded), _by_citation(now)
                for citation in sorted(set(was) | set(are)):
                    if was.get(citation) != are.get(citation):
                        report.drift.append({"citation": citation, "page": name, "recorded": was.get(citation, []),
                                             "now": are.get(citation, [])})
            row["digests"] = now
            for citation in seen:
                held[citation].append(next(t for t in texts if t.citation == citation))
            report.sections += len(texts)
    for citation, texts in held.items():
        if len(texts) > 1:
            report.duplicates.append({"citation": citation, "pages": [t.page for t in texts],
                                      "same": len({t.digest for t in texts}) == 1})
    if write and manifest:
        (root / AUTHORITIES_DIR / MANIFEST).write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        report.written = True
    return report


def backfill(root: Path, *, write: bool = True) -> DigestReport:
    """``jason export-authorities --digests``: record the digests of the pages already on disk, under the shelf's
    store lock. Reads the disk only."""
    from jason.locks import Resource, hold
    from jason.tasks.export_authorities import STORE_KEY

    with hold(Resource.STORE, STORE_KEY, purpose="jason export-authorities --digests"):
        return stamp(Path(root), write=write)


# --- Earlier versions, each with the range it was in force ------------------------------------------------------------

# The header lines that record a version's range. ``keep_version`` sets these and leaves a file's other lines alone.
RANGE_LINES = ("Editions", "Act", "Legislature's note", "From", "Printed by", "Until", "Until by")
PRINTED_IN = "California Legislature, {span} session publication{s}, read with lawlibrary"
# The occasions in a Legislature's note that end a version's words, each as what ended them.
_ENDS = {"repealed": "its own provisions", "inoperative": "its own provisions",
         "superseded": "a later amendment the Legislature's note names (superseded)"}


def _one_line(text: str) -> str:
    return " ".join((text or "").split())


def _range_lines(text: LawText) -> list[str]:
    """A version's range as header lines. A day that is not recorded says so in words: never a guessed day."""
    lines = []
    if text.editions:
        lines.append(f"- Editions: {', '.join(text.editions)}")
    if text.act:
        lines.append(f"- Act: {text.act}")
    if text.credit:
        lines.append(f"- Legislature's note: {_one_line(text.credit)}")
    lines.append(f"- From: {text.start or 'not recorded'}")
    if not text.start and text.floor:
        lines.append(f"- Printed by: {text.floor} (the first session publication on the shelf already printed these words)")
    if text.until:
        lines.append(f"- Until: {text.until}")
        if text.until_by:
            lines.append(f"- Until by: {_one_line(text.until_by)}")
    else:
        lines.append("- Until: not recorded" + (f" ({_one_line(text.until_by)})" if text.until_by else ""))
    return lines


def version_markdown(text: LawText, kept: str) -> str:
    """An earlier version as its history file keeps it: the source, the act that made it, the range it was in force,
    and then its words under its heading. ``kept`` says how it came to the shelf (the fetch, or a person by hand)."""
    # The range lines come last, as ``keep_version`` leaves them when it brings a file's range up to date.
    lines = [f"# {text.citation}: an earlier version", "", f"- Source: {text.source}", f"- Digest: {text.digest}",
             f"- {kept}", *_range_lines(text)]
    return "\n".join([*lines, "", f"## {text.citation}", "", text.words, ""])


def keep_version(root: Path, text: LawText, kept: str) -> tuple[Path, str]:
    """Write an earlier version to ``history/<citation>/<digest>.md``, or record its range on the file already there
    (words an export replaced keep the header they carried; only the range lines are set). Returns the path and what
    was done: ``written``, ``updated``, ``same``, or ``refused`` when a file of that name holds other words (it is
    left alone: a person looks at it). The caller holds the shelf's store lock."""
    from jason.community.law_text import split_page, words_digest

    path = history_dir(Path(root), text.citation) / f"{text.digest}.md"
    if not path.is_file():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(version_markdown(text, kept), encoding="utf-8")
        return path, "written"
    was = path.read_text(encoding="utf-8", errors="ignore")
    header, sections = split_page(was)
    body = next((b for head, b in sections if head == text.citation), None)
    if body is None or words_digest(body) != text.digest:
        return path, "refused"
    lines = [line for line in header.rstrip("\n").split("\n")
             if not (line.startswith("- ") and line[2:].partition(":")[0].strip() in RANGE_LINES)]
    while lines and not lines[-1].strip():
        lines.pop()
    now = "\n".join([*lines, *_range_lines(text), "", f"## {text.citation}", "", text.words, ""])
    if now == was.replace("\r\n", "\n"):
        return path, "same"
    path.write_text(now, encoding="utf-8")
    return path, "updated"


def _act_year(note: dict[str, Any]) -> int | None:
    """The year of the act a history note names: a chapter of the Statutes, the enactment, or a code amendment."""
    statute = note.get("statute") if isinstance(note.get("statute"), dict) else {}
    for value in (statute.get("year"), note.get("enacted"), note.get("measure")):
        found = re.search(r"\d{4}", str(value or ""))
        if found:
            return int(found.group(0))
    return None


def _row_words(row: dict[str, Any]) -> str:
    """An edition's row as the shelf's page would hold it: the credit line, then the text (``page_markdown``)."""
    from jason.community.law_text import section_words

    return section_words("\n".join([str(row.get("title") or ""), "", str(row.get("text") or "").strip(), ""]))


def edition_versions(citation: str, editions: list[str], rows: list[dict[str, Any]], *, repealed: str = "",
                     repealed_by: str = "") -> list[LawText]:
    """One section's versions from the session publications' rows, oldest first, each with the range it was in force.

    ``editions`` is every session publication that carries the code, oldest first; ``rows`` is each row a publication
    prints for the section (``session``, ``title``, ``text``, the Legislature's note as ``history``, and the note
    read into days as ``note``). Rows with the same words are one version. A version the newest publication prints
    is ``current``.

    - **From** is the latest of the note's effective day, its operative day, and the operative day the section's own
      words name. A note that names no day leaves it not recorded; then, when the act is older than the first
      publication on the shelf and that publication printed the words, ``floor`` is the first day of its session.
    - **Until** is the day the next version came into force: the earliest later From among the versions the next
      publication prints (the one after the last that printed these words). Words not yet operative when the next
      act took effect never operated: their Until is that act's effective day, before their From. A version's own
      end ("Repealed as of", "Inoperative", "Superseded on", or its own words) ends it sooner. Where the next
      publication prints other words under the same act (a reprint or correction), the day is not recorded. A
      section absent from the next publication ended on ``repealed`` when the caller knows the day (the Act's
      history), else its end is not recorded: a repeal leaves no note.

    A note names only the latest act, so an act between two publications that a later one overwrote is not seen:
    Until is the next act the publications show. Nothing here is inferred beyond what a note or the words state."""
    import hashlib

    from jason.community.law_text import iso_day, own_operative

    order = {session: n for n, session in enumerate(editions)}
    groups: dict[tuple[str, str], dict[str, Any]] = {}
    for row in sorted(rows, key=lambda r: order.get(str(r.get("session") or ""), -1)):
        session = str(row.get("session") or "")
        if session not in order:
            continue
        title = re.sub(r"^\d+(?:\.\d+)*[a-z]?\.\s*", "", str(row.get("title") or "").strip())
        group = groups.setdefault((title, _one_line(str(row.get("text") or ""))), {"editions": []})
        if session not in group["editions"]:
            group["editions"].append(session)
        group["row"] = row                                    # the newest publication's print of these words
    found: list[dict[str, Any]] = []
    for group in groups.values():
        row = group["row"]
        note = row.get("note") if isinstance(row.get("note"), dict) else {}
        words = _row_words(row)
        own = own_operative(words)
        # An amendment is not in force before its act takes effect, nor before its operative day, nor before the day
        # the section's own words name: the latest of the three.
        effective = iso_day(str(note.get("effective") or ""))
        start = max(effective, iso_day(str(note.get("operative") or "")), own.start)
        ends = [(iso_day(str(d.get("day") or "")), _ENDS[d.get("occasion")]) for d in note.get("dates") or []
                if isinstance(d, dict) and d.get("occasion") in _ENDS]
        if own.until:
            ends.append((own.until, "its own provisions"))
        # A day not after the start is not an end ("inoperative from ... until" names a start).
        own_end = min((e for e in ends if e[0] and e[0] > start), default=("", ""))
        key = str(note.get("citation") or "")
        act = key + (f" ({note['bill']})" if note.get("bill") else "")
        if act.startswith("Enacted "):
            act = f"the code's enactment in {act[len('Enacted '):]}"
        # Only for words the first publication on the shelf already printed: a later first printing under an older
        # act's note is not evidence of when the words came in.
        first, year = group["editions"][0], _act_year(note)
        floor = (f"{first}-01-01" if not start and first == editions[0] and first.isdigit() and year is not None
                 and year < int(first) else "")
        found.append({"words": words, "editions": group["editions"], "start": start, "effective": effective,
                      "own_end": own_end, "act": act, "key": key, "floor": floor,
                      "credit": _one_line(str(row.get("history") or note.get("note") or ""))})
    out: list[LawText] = []
    for v in found:
        printed = v["editions"]
        span = editions[order[printed[0]]:order[printed[-1]] + 1]
        source = PRINTED_IN.format(span=printed[0] if len(printed) == 1 else f"{printed[0]} to {printed[-1]}",
                                   s="" if len(printed) == 1 else "s")
        start, floor, until, by = v["start"], v["floor"], "", ""
        current = printed[-1] == editions[-1]
        if span != printed:
            # Printed, then not, then printed again: one file cannot hold two ranges, so none is recorded.
            start, floor, by = "", "", f"printed in publications that are not consecutive: {', '.join(printed)}"
        elif not current:
            after = editions[order[printed[-1]] + 1]
            others = [w for w in found if w is not v and after in w["editions"]]
            later = sorted((w["start"], w["act"]) for w in others if w["start"] and (not start or w["start"] > start))
            sooner = sorted((w["effective"], w["act"]) for w in others if start and w["effective"] and w["effective"] < start)
            if any(w["key"] and w["key"] == v["key"] and w["start"] == start for w in others):
                by = (f"the {after} session publication prints the section under the same act with other words (a reprint "
                      "or a correction); the day is not on the shelf")
            elif sooner:
                # An act of the next publication took effect before these words' operative day: they never operated.
                until, by = sooner[0]
                by = f"{by or 'the next act'}, in effect before these words' operative day"
            elif later:
                until, by = later[0]
                by = by or f"the next version, in the {after} session publication"
            elif others:
                # Other words in force from the same day (two acts of one day), or notes that name no day.
                by = f"the {after} session publication prints other words, and their notes name no later day"
            elif repealed:
                until, by = repealed, repealed_by or f"absent from the {after} session publication"
            else:
                by = f"absent from the {after} session publication; a repeal leaves no note"
        if v["own_end"][0] and span == printed and (not until or v["own_end"][0] < until):
            until, by = v["own_end"]
        out.append(LawText(citation, v["words"], hashlib.sha256(v["words"].encode("utf-8")).hexdigest(), source,
                           printed[-1], "", "", current, "", act=v["act"], start=start, floor=floor, until=until,
                           until_by=by, credit=v["credit"], editions=tuple(printed)))
    return sorted(out, key=lambda t: (t.editions[0], t.start or t.floor, t.digest))


def keep_versions(root: Path, citation: str, editions: list[str], found: list[LawText], *, when: str = "",
                  shelf: set[str] | None = None, command: str = "jason law-history --versions") -> dict[str, Any]:
    """Store one section's versions: each earlier one as a history file with its range. Returns ``ledger`` (the
    section's entry for the versions ledger, a row for every version, the current too: ``write_ledger`` stores it),
    ``files`` (each path and what was done), and ``differs`` when the newest publication's words are not the words
    on the shelf. ``shelf`` is the digests the shelf holds under the citation (read from the disk when not given).
    The caller holds the shelf's store lock."""
    from jason.community.law_text import versions

    root = Path(root)
    when = when or date.today().isoformat()
    if shelf is None:
        shelf = {t.digest for t in versions(citation, root)}
    files: list[dict[str, str]] = []
    rows: list[dict[str, Any]] = []
    for text in found:
        row = {"digest": text.digest, "editions": list(text.editions), "act": text.act, "note": text.credit,
               "from": text.start, "floor": text.floor, "until": text.until, "until_by": text.until_by,
               "newest": text.current, "file": ""}
        if not text.current and text.digest not in shelf:
            path, did = keep_version(root, text, f"Kept: {when} ({command})")
            row["file"] = path.relative_to(root).as_posix()
            files.append({"file": row["file"], "did": did})
        rows.append(row)
    newest = {t.digest for t in found if t.current}
    entry = {"read": when, "source": "the session publications lawlibrary holds", "editions": list(editions),
             "printed": sorted({e for t in found for e in t.editions}), "versions": rows}
    return {"ledger": entry, "files": files, "differs": bool(shelf) and bool(newest) and not (shelf & newest)}


def write_ledger(root: Path, entries: dict[str, dict[str, Any]], *, when: str = "") -> Path:
    """Record each section's entry in the versions ledger (``history/versions.json``), keeping the entries of the
    sections not named. The ledger is what says when the words on the shelf came into force. An unreadable ledger is
    set aside, never overwritten. The caller holds the shelf's store lock."""
    from jason.community.law_text import VERSIONS_FILE

    when = when or date.today().isoformat()
    log = Path(root) / VERSIONS_FILE
    if not entries:
        return log
    try:
        data = json.loads(log.read_text(encoding="utf-8") or "{}") if log.is_file() else {}
    except json.JSONDecodeError:
        log.replace(log.with_name(f"{log.stem}.unreadable-{when}.json"))
        data = {}
    data.setdefault("sections", {}).update(entries)
    data["written"] = when
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text(json.dumps(data, indent=1), encoding="utf-8")
    return log


def add_version(root: Path, citation: str, words: str, *, source: str, by: str, start: str = "", until: str = "",
                act: str = "", until_by: str = "", when: str = "") -> tuple[Path, str]:
    """Keep an earlier version a person read from an official source: its words, with the source's citation, who
    added it, and the range as that person found it (a day left out is not recorded). Refused without the words, a
    source, or a name, and when a day is not an ISO day or the range is empty. Words the history already holds are
    left as they are (``held``): their header is corrected by hand. Takes the shelf's store lock."""
    import hashlib

    from jason.community.law_text import iso_day, section_words
    from jason.locks import Resource, hold
    from jason.tasks.export_authorities import STORE_KEY

    found = normal_citation(citation)
    if found is None or found[1]:
        raise ValueError("say a code and a section, such as CIV 5855 (the whole section, not a subdivision)")
    body = section_words(words)
    if not body:
        raise ValueError("no words to keep")
    if not source.strip() or not by.strip():
        raise ValueError("an added version names its official source (the citation a reader can check) and who added it")
    for name, value in (("from", start), ("until", until)):
        if value and iso_day(value) != value:
            raise ValueError(f"--{name} is a day, YYYY-MM-DD")
    if start and until and until <= start:
        raise ValueError("the range is empty: until is not after from")
    when = when or date.today().isoformat()
    text = LawText(found[0], body, hashlib.sha256(body.encode("utf-8")).hexdigest(), _one_line(source), "", "", "", False, "",
                   act=_one_line(act), start=start, until=until, until_by=_one_line(until_by))
    with hold(Resource.STORE, STORE_KEY, purpose="jason law-history --add-version"):
        path = history_dir(Path(root), text.citation) / f"{text.digest}.md"
        if path.is_file():
            return path, "held"
        return keep_version(Path(root), text, f"Added by hand: {_one_line(by)}, {when}")


__all__ = ["DigestReport", "add_version", "backfill", "edition_versions", "history_markdown", "keep_replaced",
           "keep_version", "keep_versions", "merged", "page_digests", "snapshot", "stamp", "version_markdown",
           "write_ledger"]
