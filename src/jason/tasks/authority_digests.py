"""Keep the shelf's digests and its replaced words: the write side of ``jason.community.law_text``.

``jason export-authorities`` overwrites the statute pages. Before it writes, ``snapshot`` reads every section on the
shelf; after, ``keep_replaced`` compares. A section whose words are no longer on the shelf under its citation is
copied to ``data/authorities/history/<citation>/<digest>.md`` with the source line it carried, and the change is a row
in ``data/authorities/changes.json``. ``page_digests`` gives the digests the manifest records for each page, and
``backfill`` (``jason export-authorities --digests``) writes them for the pages already on disk without asking
lawlibrary for anything.

Every function but ``backfill`` expects its caller to hold the shelf's store lock (``export_authorities.STORE_KEY``).
"""

from __future__ import annotations

import json
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
        out += [f"  {v['citation']}: {v['count']} versions in {v['page']} (readers quote the first)" for v in self.versions]
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


__all__ = ["DigestReport", "backfill", "history_markdown", "keep_replaced", "merged", "page_digests", "snapshot",
           "stamp"]
