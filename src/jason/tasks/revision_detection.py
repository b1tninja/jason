"""Find every version of a document on disk (and, with ``fetch``, in Drive and PayHOA), compare them section by section,
and say what changed when, with the adoption on record or its absence.

**Where versions come from.** For one document (an outline key, ``Community.citable_documents()``), a file is a
candidate when its name names the document (its title, an alias, or a pattern in ``Community.revision_series()``):

- email attachments (``data/gmail/files.json``): dated by the message, sent or received;
- the PayHOA library listing (``data/payhoa-documents.json``): dated by the upload; fetched by id with ``fetch``;
- the association's site copies (``data/artifacts/site-docs``) and local exports (``data/governing``): dated by when
  jason read them, an upper bound only;
- Drive files (``data/drive/files.json``): dated by the file's last change; fetched by id with ``fetch``;
- the Doc's own revisions (Drive API ``revisions.list``), exported as Word files with ``fetch``: dated by when each
  revision was saved. Drive merges older edits, so these are the revisions it kept, not every edit.

A candidate is a version only if it shares its words with the current text (``revision_detection.VERSION_MIN``); one
that holds only part of it (``PARTIAL_BELOW``) is an excerpt, compared but kept off the chain. Files with the same
words (letters and digits) are one version with many sightings, and the first sighting bounds its date. A PDF whose
words match a Drive revision up to export differences is a sighting of that revision, not a version of its own.

**What is compared.** The chain is the Doc's revisions in order, after the versions older than the Doc; with no
revisions fetched, every version in date order. Milestones are the chain's versions someone outside the Doc saw (an
email, an upload, the site), and its first and last: the report compares consecutive milestones, so a draft made and
undone between two of them is not a change. Each change is tied to an adoption where the profile's rule-change rows
(``Community.rule_change_records()``) or the minutes show one in its window; a change with none is a finding.

Writes ``data/revisions/<key>.json`` and the report ``data/reports/revisions-<key>.md`` (private: it quotes the
association's documents). Reading only: nothing in Drive or PayHOA changes.
"""

from __future__ import annotations

import hashlib
import json
import re
import zipfile
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Iterable

from jason.community.revision_detection import (PARTIAL_BELOW, VERSION_MIN, Change, ChangeKind, Flag, Lineage,
                                                RevisionSeries, Unit, align, between, coverage, docx_suggestions,
                                                docx_text, lineages,
                                                name_dates, name_matches, outline_text, outline_version,
                                                printed_dates,
                                                strip_furniture, text_hash, units)
from jason.community.revisions import RecordVersion, Stage

REV_DIR = "revisions"
TEXTS = "revisions/texts"
FILES = "revisions/files"
PAYHOA_FILES = "revisions/payhoa"
REPORTS = "reports"
DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
ADOPTION_AFTER = 120          # days after a change's later version that an adoption may still be the change's
READER = 4                   # the text cache's reader; a cached reading by an older reader is read again
EXCERPT_HELD = 0.9          # an excerpt's words found in an earlier copy
EXCERPT_HOLDS = 0.75         # ... which it holds less of than this
EXPORT_PAUSE = 2.0          # seconds between two revision exports
MATCH_SHARE = 0.01            # words a copy may differ from a revision by (a share of its words) and still be its copy
MATCH_WORDS = 40              # ... and at least this many
_KEEP_PARTS = re.compile(r"^word/(document|numbering|styles|header\d*|footer\d*)\.xml$|^\[Content_Types\]\.xml$")
_ADOPT = re.compile(r"\badopt\w*|\bapprov\w*|\bMSC\b|M/S/P|\bmotion\b", re.I)


def _day(value: Any) -> date | None:
    text = str(value or "")
    try:
        return date.fromisoformat(text[:10]) if len(text) >= 10 else None
    except ValueError:
        return None


def _mtime(path: Path) -> date:
    return datetime.fromtimestamp(path.stat().st_mtime).date()


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------------------------------------------------------------
# The document and its series.

@dataclass
class Series:
    key: str
    title: str
    drive_id: str
    phrases: list[str]
    extra: tuple[str, ...] = ()
    exclude: tuple[str, ...] = ()
    allowed: tuple[str, ...] = ()

    def matches(self, name: str) -> bool:
        return name_matches(name, self.phrases, extra=self.extra, exclude=self.exclude, allowed=self.allowed)


def series_of(community: Any, key: str) -> Series:
    docs = {d.key: d for d in tuple(getattr(community, "citable_documents", lambda: ())() or ())}
    rows = {r.key: r for r in tuple(getattr(community, "revision_series", lambda: ())() or ())}
    doc = docs.get(key)
    row: RevisionSeries | None = rows.get(key)
    if doc is None and row is None:
        raise KeyError(f"{key} is not a document jason outlines (jason revisions --list names them)")
    title = doc.title if doc else key
    phrases = [title, *(doc.aliases if doc else ())]
    try:
        name = str(community.name)
    except Exception:
        name = ""
    return Series(key, title, doc.drive_id if doc else "", phrases, row.names if row else (),
                  row.exclude if row else (), (name,) if name else ())


def keys(community: Any, *, series_only: bool = False) -> list[str]:
    """Every document whose versions can be compared: the citable documents, and any series row beyond them. With
    ``series_only``, the profile's series rows when it names any (``jason revisions all``): a declaration and its
    amendments are separate instruments, read as such by the living documents, not one series of copies."""
    rows = [r.key for r in tuple(getattr(community, "revision_series", lambda: ())() or ())]
    if series_only and rows:
        return rows
    out = [d.key for d in tuple(getattr(community, "citable_documents", lambda: ())() or ())]
    return out + [k for k in rows if k not in out]


# ---------------------------------------------------------------------------------------------------------------------
# Sightings and files.

@dataclass
class Sighting:
    source: str                  # gmail, payhoa, site, governing, drive-file, drive-revision, outline
    ref: str                     # a message id, a library id, a path, a Drive id, "<doc>@<revision>"
    name: str
    on: date | None
    how: str                     # what the date is
    outbound: bool = False       # sent or published: someone outside the Doc saw these words
    path: str = ""               # the file on disk, relative to data/; empty when not fetched
    note: str = ""
    sha: str = ""                # the file's sha256, once read

    def row(self) -> dict[str, Any]:
        return {"source": self.source, "ref": self.ref, "name": self.name, "on": self.on.isoformat() if self.on else None,
                "how": self.how, "outbound": self.outbound, "path": self.path, "note": self.note}


def _gmail(root: Path, series: Series) -> list[Sighting]:
    try:
        rows = json.loads((root / "gmail" / "files.json").read_text(encoding="utf-8")).get("files") or []
    except (OSError, json.JSONDecodeError):
        return []
    out = []
    for f in rows:
        name = str(f.get("name") or "")
        if not series.matches(name):
            continue
        path = str(f.get("path") or "").replace("\\", "/")
        out_bound = f.get("direction") == "out"
        out.append(Sighting("gmail", str(f.get("messageId") or ""), name, _day(f.get("at")),
                            "sent by email" if out_bound else "received by email", out_bound,
                            path if (root / path).is_file() else "", str(f.get("subject") or "")[:90]))
    return out


def _payhoa(root: Path, series: Series) -> list[Sighting]:
    try:
        rows = json.loads((root / "payhoa-documents.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    from jason.tasks.library import mirror_index

    mirrors = mirror_index(root)
    out = []
    for r in rows if isinstance(rows, list) else []:
        if r.get("directory") or not series.matches(str(r.get("fileName") or "")):
            continue
        doc_id, name = str(r.get("id")), str(r.get("fileName") or "")
        size = r.get("fileSize")
        local = root / PAYHOA_FILES / doc_id / name
        path = ""
        if local.is_file():
            path = local.relative_to(root).as_posix()
        else:
            # A copy elsewhere on disk under the same name is this file only if its size agrees.
            mirror = mirrors.get(name.casefold())
            if mirror is not None and size is not None and mirror.stat().st_size == int(size):
                path = mirror.relative_to(root).as_posix()
        out.append(Sighting("payhoa", f"payhoa:{doc_id}", str(r.get("path") or name), _day(r.get("updatedAt")),
                            "uploaded to the PayHOA library", bool(r.get("public")), path,
                            f"{size} bytes" if size else ""))
    return out


def _site(root: Path, series: Series) -> list[Sighting]:
    out = []
    for folder, source, how, outbound in (("artifacts/site-docs", "site", "read from the association's site (as of)",
                                           True),
                                          ("governing", "governing", "exported from the Doc (as of)", False)):
        base = root / folder
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*")):
            if not path.is_file() or path.name.lower().endswith((".pdf.md", ".docx.md", ".txt", ".json")):
                continue
            if path.suffix.lower() not in (".pdf", ".docx", ".doc", ".md"):
                continue
            if not series.matches(path.name.replace("-", " ")):
                continue
            out.append(Sighting(source, path.relative_to(root).as_posix(), path.name, _mtime(path), how, outbound,
                                path.relative_to(root).as_posix()))
    return out


def _drive_files(root: Path, series: Series) -> tuple[list[Sighting], list[dict[str, Any]]]:
    """Drive's binary files named like the document, and its other Google Docs named like it (their revisions are
    read with ``fetch``)."""
    try:
        rows = json.loads((root / "drive" / "files.json").read_text(encoding="utf-8")).get("files") or []
    except (OSError, json.JSONDecodeError):
        return [], []
    out, docs = [], []
    for r in rows:
        name, mime = str(r.get("name") or ""), str(r.get("mimeType") or "")
        if mime.startswith(("audio/", "video/", "image/")) or mime.endswith(("folder", "zip")):
            continue
        if not series.matches(name):
            continue
        fid = str(r.get("id") or "")
        if mime == "application/vnd.google-apps.document":
            if fid != series.drive_id:
                docs.append(r)
            continue
        ext = Path(name).suffix.lower() or ".bin"
        local = next((p for p in (root / FILES / f"{fid}{ext}", root / "drive" / "evidence" / f"{fid}{ext}")
                      if p.is_file()), None)
        out.append(Sighting("drive-file", fid, str(r.get("path") or name), _day(r.get("modified")),
                            "in Drive (the file's last change)", False,
                            local.relative_to(root).as_posix() if local else "",
                            f"added to Drive {str(r.get('created') or '')[:10]}"))
    return out, docs


def _revision_sightings(root: Path, series: Series, doc_ids: Iterable[str]) -> list[Sighting]:
    out = []
    for doc_id in doc_ids:
        folder = root / REV_DIR / series.key / "drive" / doc_id
        try:
            listing = json.loads((folder / "revisions.json").read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        for r in listing.get("revisions") or []:
            path = folder / f"{r['id']}.docx"
            if not path.is_file():
                continue
            out.append(Sighting("drive-revision", f"{doc_id}@{r['id']}", listing.get("name") or series.title,
                                _day(r.get("modifiedTime")), "saved in the Doc (a Drive revision)", False,
                                path.relative_to(root).as_posix(), str(r.get("modifiedTime") or "")))
    return out


# ---------------------------------------------------------------------------------------------------------------------
# Reading a file's words.

def _pdf_date(value: str) -> date | None:
    m = re.match(r"D:(\d{4})(\d{2})(\d{2})", value or "")
    try:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3))) if m else None
    except ValueError:
        return None


def read_file(path: Path, *, ocr: bool = False) -> dict[str, Any]:
    """A file's words for comparison: ``text`` (cleaned of page furniture), ``method``, whether OCR read it, the
    dates its words print, and the dates its own metadata gives."""
    suffix = path.suffix.lower()
    out: dict[str, Any] = {"text": "", "method": "", "ocr": False, "printed": [], "meta": []}
    raw = ""
    if suffix == ".pdf":
        import pymupdf

        try:
            with pymupdf.open(str(path)) as doc:
                pages = [p.get_text() for p in doc]
                meta = doc.metadata or {}
        except Exception as exc:
            out["method"] = f"unreadable PDF: {exc}"
            return out
        raw = "\n".join(pages)
        producer = f"{meta.get('producer') or ''} {meta.get('creator') or ''}"
        for field_name, how in (("creationDate", "PDF created"), ("modDate", "PDF modified")):
            d = _pdf_date(meta.get(field_name) or "")
            if d:
                out["meta"].append([d.isoformat(), how])
        if len(raw.strip()) >= 200:
            out["text"] = strip_furniture(pages)
            scanned = re.search(r"paper capture|ocr|scan", producer, re.I) is not None
            out["method"] = "text layer (read by the scanner's OCR)" if scanned else "text layer"
            out["ocr"] = scanned
        elif ocr:
            from jason.community.ocr import TesseractCli

            if TesseractCli.available():
                text = TesseractCli().text_of(path)
                out.update(text=strip_furniture(text.split("\f")), method="ocr: tesseract", ocr=True)
                raw = text
            else:
                out["method"] = "image only; Tesseract is not installed"
        else:
            out["method"] = "image only; not read (--ocr reads it)"
    elif suffix == ".docx":
        data = path.read_bytes()
        try:
            out["text"] = docx_text(data)
            out["method"] = "Word file"
            out["suggestions"] = [[kind, words] for kind, words in docx_suggestions(data)]
            with zipfile.ZipFile(path) as z:
                furniture = " ".join(re.sub(r"<[^>]+>", " ", z.read(n).decode("utf-8", "ignore"))
                                     for n in z.namelist() if re.match(r"word/(header|footer)\d*\.xml$", n))
            raw = out["text"] + "\n" + furniture
        except (KeyError, zipfile.BadZipFile, Exception) as exc:   # a damaged file is a miss, not a crash
            out["method"] = f"unreadable Word file: {exc}"
            return out
    elif suffix in (".md", ".txt"):
        raw = path.read_text(encoding="utf-8", errors="ignore")
        raw = re.sub(r"^- (drive_id|mime|path):.*$", "", raw, flags=re.M)
        out["text"], out["method"] = raw, "Markdown export" if suffix == ".md" else "text"
    elif suffix == ".doc":
        out["method"] = "no reader for a .doc (Word 97) file; save it as .docx or PDF to compare it"
    else:
        out["method"] = f"no reader for {suffix}"
    out["printed"] = [[d.isoformat(), phrase] for d, phrase in printed_dates(raw)]
    return out


def cached_read(root: Path, path: Path, sha: str, *, ocr: bool = False) -> dict[str, Any]:
    cache = root / TEXTS / f"{sha}.json"
    if cache.is_file():
        try:
            got = json.loads(cache.read_text(encoding="utf-8"))
            if got.get("reader") == READER and (got.get("text") or not ocr or got.get("ocr")):
                return got
        except (OSError, json.JSONDecodeError):
            pass
    got = read_file(path, ocr=ocr)
    got["reader"] = READER
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(got, ensure_ascii=False), encoding="utf-8")
    return got


# ---------------------------------------------------------------------------------------------------------------------
# Versions.

@dataclass
class Version:
    hash: str
    text: str
    method: str
    ocr: bool
    units: list[Unit]
    sightings: list[Sighting] = field(default_factory=list)
    files: dict[str, str] = field(default_factory=dict)          # sha256 -> path
    printed: list[tuple[date, str]] = field(default_factory=list)
    meta: list[tuple[date, str]] = field(default_factory=list)
    id: str = ""
    role: str = "chain"            # chain, side (differs from every revision), partial (an excerpt), excluded
    revision: str = ""             # "<doc>@<revision>" when it is one of the Doc's own revisions
    matched: str = ""              # the version it was found to be a copy of
    residual: list[Change] = field(default_factory=list)
    share: float = 1.0             # the share of the current text it holds
    milestone: bool = False
    suggestions: list[list[str]] = field(default_factory=list)   # a Doc revision's pending suggestions
    titled: bool = False           # a file of it is named by the document's title or alias (not only a profile pattern)

    @property
    def existed(self) -> list[tuple[date, str, str]]:
        """Dates by which these words existed (an upper bound on when they were written): each sighting, the file's
        own metadata, and a full date in a file's name. Earliest first."""
        out = [(s.on, s.how, s.ref) for s in self.sightings if s.on]
        out += [(d, how, "file metadata") for d, how in self.meta]
        for s in self.sightings:
            out += [(d, "printed in the file's name", s.name) for d in name_dates(s.name)]
        return sorted(set(out))

    @property
    def claims(self) -> list[tuple[date, str, str]]:
        """Dates the words claim for themselves ("EFFECTIVE: ...", "Revised ...") and a bare year in a file's name:
        a claim, read as written, and a lower bound at best (a later copy keeps printing an old date)."""
        out = [(d, "printed in the text", phrase) for d, phrase in self.printed]
        for s in self.sightings:
            if not name_dates(s.name):
                y = re.search(r"(?<!\d)(19[89]\d|20[0-4]\d)(?!\d)", re.sub(r"\([^)]*\)", " ", s.name))
                if y:
                    out.append((date(int(y.group(1)), 1, 1), "a year in the file's name", s.name))
        return sorted(set(out))

    @property
    def dates(self) -> list[tuple[date, str, str]]:
        return sorted(set(self.existed + self.claims))

    @property
    def on(self) -> date | None:
        """For a Doc revision, when it was saved; otherwise the earliest date the words are known to have existed;
        with none, the latest date they claim."""
        if self.revision:
            saved = [s.on for s in self.sightings if s.source == "drive-revision" and s.on]
            if saved:
                return min(saved)
        if self.existed:
            return self.existed[0][0]
        return self.claims[-1][0] if self.claims else None

    @property
    def order(self) -> tuple[date, date]:
        """Where a version older than the Doc sits: by the latest date it claims, then by when it existed."""
        on = self.on or date.max
        return (self.claims[-1][0] if self.claims and not self.revision else on, on)

    @property
    def on_how(self) -> str:
        if self.revision:
            return "saved in the Doc (a Drive revision)"
        if self.existed:
            d = self.existed[0]
            return f"existed by: {d[1]} ({d[2]})"
        if self.claims:
            d = self.claims[-1]
            return f"claims: {d[1]} ({d[2]})"
        return "undated"

    @property
    def outbound(self) -> list[Sighting]:
        return [s for s in self.sightings if s.outbound]

    @property
    def label(self) -> str:
        return self.on.isoformat() if self.on else "undated"

    @property
    def runs(self) -> frozenset[str]:
        return frozenset().union(*(u.runs for u in self.units)) if self.units else frozenset()

    def row(self) -> dict[str, Any]:
        return {"id": self.id, "on": self.on.isoformat() if self.on else None, "onFrom": self.on_how,
                "role": self.role, "milestone": self.milestone, "method": self.method, "ocr": self.ocr,
                "hash": self.hash[:16], "revision": self.revision, "matched": self.matched, "share": round(self.share, 3),
                "sections": len(self.units),
                "dates": [{"on": d.isoformat(), "how": how, "from": ref} for d, how, ref in self.dates],
                "files": [{"sha256": sha, "path": p} for sha, p in self.files.items()],
                "sightings": [s.row() for s in sorted(self.sightings, key=lambda s: (s.on or date.max, s.ref))],
                "residual": [_change_row(c) for c in self.residual]}


def _wording(changes: Iterable[Change]) -> list[Change]:
    """The changes that change words: a rewording, or a section added or removed that is not found elsewhere."""
    out = []
    for c in changes:
        if c.kind is ChangeKind.REWORDED or (c.kind in (ChangeKind.ADDED, ChangeKind.REMOVED) and not c.noise):
            out.append(c)
        elif c.kind in (ChangeKind.SPLIT, ChangeKind.MERGED) and any(not o.noise for o in c.ops):
            out.append(c)
    return out


def _outline_fallback(root: Path, key: str) -> Version | None:
    """The current text from the Doc's outline (``data/outlines/<key>.json``) when no revision was fetched: its text
    with each section's label written back in."""
    path = root / "outlines" / f"{key}.json"
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    text = str(raw.get("text") or "")
    for s in sorted(raw.get("sections") or [], key=lambda s: -int(s.get("start") or 0)):
        at = int(s.get("start") or 0)
        if s.get("label"):
            text = text[:at] + f"{s['label']} " + text[at:]
        elif not s.get("number") and int(s.get("depth") or 1) <= 2:
            text = text[:at] + "## " + text[at:]
    us = units(outline_text(text, key=key))
    v = Version(text_hash(text), text, "the Doc's outline (Docs API)", False, us)
    v.sightings.append(Sighting("outline", f"outlines/{key}.json", str(raw.get("title") or key), _mtime(path),
                                "read from the Doc (as of)", False, f"outlines/{key}.json",
                                f"Docs revision {str(raw.get('revision') or '')[:16]}"))
    return v


def collect(community: Any, data_dir: Path, key: str, *, ocr: bool = False,
            log: Callable[[str], None] = lambda s: None) -> tuple[Series, list[Version], list[Sighting], list[str]]:
    """Every version of the document on disk, by its words: (the series, the versions, the sightings with no file on
    disk, notes)."""
    root = Path(data_dir)
    series = series_of(community, key)
    files, other_docs = _drive_files(root, series)
    doc_ids = [series.drive_id] if series.drive_id else []
    doc_ids += [str(d.get("id")) for d in other_docs]
    sightings = (_gmail(root, series) + _payhoa(root, series) + _site(root, series) + files
                 + _revision_sightings(root, series, doc_ids))
    missing = [s for s in sightings if not s.path]
    notes: list[str] = []
    by_hash: dict[str, Version] = {}
    sha_of: dict[str, str] = {}
    for s in sightings:
        if not s.path:
            continue
        path = root / s.path
        sha = sha_of.get(s.path) or _sha(path)
        sha_of[s.path] = sha
        s.sha = sha
        got = cached_read(root, path, sha, ocr=ocr)
        if not got.get("text"):
            notes.append(f"{s.name} ({s.source} {s.ref}): {got.get('method')}")
            continue
        h = text_hash(got["text"])
        v = by_hash.get(h)
        if v is None:
            v = Version(h, got["text"], got["method"], bool(got.get("ocr")),
                        units(outline_version(got["text"], key=key, title=series.title, ocr=bool(got.get("ocr")))))
            by_hash[h] = v
        v.sightings.append(s)
        v.files.setdefault(sha, s.path)
        if s.source != "drive-revision" and name_matches(s.name.rsplit("/", 1)[-1], series.phrases,
                                                         exclude=series.exclude, allowed=series.allowed):
            v.titled = True
        if got.get("suggestions") and not v.suggestions:
            v.suggestions = list(got["suggestions"])
        for d, phrase in got.get("printed") or []:
            if (date.fromisoformat(d), phrase) not in v.printed:
                v.printed.append((date.fromisoformat(d), phrase))
        for d, how in got.get("meta") or []:
            if (date.fromisoformat(d), how) not in v.meta:
                v.meta.append((date.fromisoformat(d), how))
        if s.source == "drive-revision" and s.ref.startswith(f"{series.drive_id}@"):
            if not v.revision or (s.on and v.on and s.on < v.on):
                v.revision = s.ref
    versions = list(by_hash.values())
    if not any(v.revision for v in versions):
        fallback = _outline_fallback(root, key)
        if fallback is not None and fallback.hash not in by_hash:
            versions.append(fallback)
    log(f"{key}: {len(sightings)} sightings, {len(versions)} distinct texts, {len(missing)} not on disk")
    return series, versions, missing, notes


# ---------------------------------------------------------------------------------------------------------------------
# The chain.

def _current(versions: list[Version]) -> Version | None:
    revs = [v for v in versions if v.revision]
    if revs:
        return max(revs, key=lambda v: (v.on or date.min))
    fallback = [v for v in versions if any(s.source == "outline" for s in v.sightings)]
    if fallback:
        return fallback[0]
    dated = [v for v in versions if v.on]
    return max(dated, key=lambda v: v.on) if dated else (versions[0] if versions else None)


def arrange(versions: list[Version], *, log: Callable[[str], None] = lambda s: None) -> tuple[list[Version], Version | None]:
    """Each version's role, the chain in order, and the current version (see the module's notes)."""
    current = _current(versions)
    if current is None:
        return [], None
    cur_runs = current.runs
    for v in versions:
        v.share = 1.0 if v is current else len(v.runs & cur_runs) / len(cur_runs) if cur_runs else 0.0
        held = len(v.runs & cur_runs) / len(v.runs) if v.runs else 0.0
        if v is current:
            continue
        if max(v.share, held) < VERSION_MIN:
            # Named by the document's own title and older than the current text, it is an earlier text the current one
            # replaced wholesale: listed, never aligned. Otherwise it only shares a name.
            older = v.on is not None and current.on is not None and v.on < current.on
            v.role = "rewritten" if (v.titled and older) else "excluded"
        elif v.share < PARTIAL_BELOW and held >= VERSION_MIN:
            v.role = "partial"
    # An excerpt of an earlier copy: a scan of some pages, a copy missing its appendices. Its words are almost all in
    # a copy at least as old, which holds much more. (A later copy that grew is not an excerpt of anything.)
    loose = [v for v in versions if not v.revision and v.role == "chain" and v is not current]
    for v in loose:
        vr = v.runs
        for o in loose + [current]:
            if o is v or not vr or not o.runs or o.order > v.order:
                continue
            both = len(vr & o.runs)
            if both / len(vr) >= EXCERPT_HELD and both / len(o.runs) < EXCERPT_HOLDS:
                v.role = "partial"
                break
    revisions = sorted((v for v in versions if v.revision and v.role == "chain"), key=lambda v: v.on or date.min)
    others = [v for v in versions if not v.revision and v.role == "chain"]
    if revisions:
        first = revisions[0].on or date.min
        for v in others:
            best = _best_match(v, revisions)
            if best is not None:
                v.role, v.matched = "copy", best.hash
                v.residual = _wording(align(v.units, best.units, ocr=v.ocr or best.ocr))
                best.sightings.extend(v.sightings)
                best.printed.extend(p for p in v.printed if p not in best.printed)
                best.meta.extend(m for m in v.meta if m not in best.meta)
                for sha, p in v.files.items():
                    best.files.setdefault(sha, p)
                continue
            if v.on is not None and v.on < first:
                v.role = "chain"
            else:
                v.role = "side"
        pre = _merge_copies(sorted((v for v in others if v.role == "chain"), key=lambda v: v.order))
        chain = pre + revisions
    else:
        chain = _merge_copies(sorted(others + ([current] if current not in others else []), key=lambda v: v.order))
        if current.role == "copy":
            current = next(v for v in chain if v.hash == current.matched)
    for k, v in enumerate(sorted(versions, key=lambda v: (v.on or date.max, v.order, v.hash))):
        v.id = f"v{k + 1}"                           # in the order the words are known to have existed
    log(f"chain of {len(chain)} versions; {sum(v.role == 'copy' for v in versions)} copies matched; "
        f"{sum(v.role == 'side' for v in versions)} side; {sum(v.role == 'partial' for v in versions)} excerpts; "
        f"{sum(v.role == 'excluded' for v in versions)} excluded")
    return chain, current


def _merge_copies(ordered: list[Version]) -> list[Version]:
    """Consecutive versions whose words match up to export differences (a PDF and the Word file it was printed from)
    are one version: the later is a copy of the earlier, keeps its residual, and lends it its sightings. A Word file is
    kept over a PDF of the same words, since it reads the way the Doc's revisions do."""
    out: list[Version] = []
    for v in ordered:
        prev = out[-1] if out else None
        if prev is not None and _best_match(v, [prev]) is not None:
            keep, copy = (v, prev) if (v.method == "Word file" and prev.method != "Word file") else (prev, v)
            copy.role, copy.matched = "copy", keep.hash
            copy.residual = _wording(align(copy.units, keep.units, ocr=copy.ocr or keep.ocr))
            keep.sightings.extend(copy.sightings)
            keep.printed.extend(p for p in copy.printed if p not in keep.printed)
            keep.meta.extend(m for m in copy.meta if m not in keep.meta)
            for sha, p in copy.files.items():
                keep.files.setdefault(sha, p)
            out[-1] = keep
            continue
        out.append(v)
    return out


def _bag(v: Version) -> Counter:
    return Counter(t for u in v.units for t in re.findall(r"[a-z0-9]+", u.words.lower()))


def _best_match(v: Version, candidates: list[Version]) -> Version | None:
    """The revision a copy was made from: the one whose words, counted as a bag, differ least from the copy's (a tie
    goes to the latest saved on or before the copy's date). It is a copy only if the difference is within
    ``MATCH_SHARE`` of its words (at least ``MATCH_WORDS``): what is left is export noise (file chips, a header the
    PDF prints in the text, a form's table) or an edit Drive did not keep, and stays on the copy as its residual."""
    bag = _bag(v)
    total = sum(bag.values())
    if not total or not candidates:
        return None
    day = v.on or date.max

    def score(c: Version) -> tuple:
        other = _bag(c)
        diff = sum(((bag - other) + (other - bag)).values())
        on = c.on or date.min
        return (diff, 0 if on <= day else 1, -on.toordinal() if on <= day else on.toordinal())

    best = min(candidates, key=score)
    if score(best)[0] > max(MATCH_WORDS, MATCH_SHARE * total):
        return None
    if _format(v) == _format(best) and _wording(align(v.units, best.units, ocr=v.ocr or best.ocr)):
        return None          # two files read the same way have no export noise between them: a difference is an edit
    return best


def _format(v: Version) -> str:
    return "ocr" if v.ocr else v.method.split(" (")[0]


def milestones(chain: list[Version]) -> list[int]:
    """The chain positions someone outside the Doc saw (an email, an upload, the site, a copy on Drive), with the first
    and the last."""
    out = {0, len(chain) - 1} if chain else set()
    for k, v in enumerate(chain):
        if any(s.source != "drive-revision" for s in v.sightings):
            out.add(k)
    for k in out:
        chain[k].milestone = True
    return sorted(out)


# ---------------------------------------------------------------------------------------------------------------------
# Adoption on record.

@dataclass
class Adoptions:
    community: Any
    root: Path
    key: str
    names: list[str]
    _minutes: Any = None

    def records(self) -> list[Any]:
        rows = tuple(getattr(self.community, "rule_change_records", lambda: ())() or ())
        return [r for r in rows if getattr(r, "document", "") == self.key]

    def minutes(self) -> dict[date, list[Any]]:
        if self._minutes is None:
            try:
                from jason.tasks.schedule_evidence import Stores

                stores = Stores(self.root, self.community)
                self._minutes = (stores, stores.minutes())
            except Exception:
                self._minutes = (None, {})
        return self._minutes[1]

    def find(self, start: date | None, end: date | None, head: str, title: str = "") -> list[dict[str, Any]]:
        """The adoptions that may be this change's: a rule-change row decided in the window, then minutes in the window
        that name the document or the section near an adoption word. The window runs from the earlier version's date
        to ``ADOPTION_AFTER`` days after the later one's (a Doc is often edited before the board adopts the text). A
        section is named by its head's number ("R-4") or by its caption's words ("Fine Schedule")."""
        if end is None:
            return []
        last = end + timedelta(days=ADOPTION_AFTER)
        out: list[dict[str, Any]] = []
        pats = []
        if re.match(r"^[A-Z]{1,3}-\d", head or ""):
            pats.append(re.escape(head))
        caption = re.sub(r"^\(?[A-Za-z0-9]{1,3}[.)]\s*", "", title or "").strip()
        words = re.findall(r"[A-Za-z]+", caption)
        if 2 <= len(words) <= 5 and len(caption) <= 40 and not caption.isupper():   # a letterhead is not a caption
            pats.append(r"\s+".join(re.escape(w) for w in words))
        head_re = re.compile(rf"(?<![\w-])(?:{'|'.join(pats)})(?![\w-])", re.I) if pats else None
        for r in self.records():
            decided = getattr(r, "decided", None)
            if decided is None or decided > last or (start is not None and decided < start):
                continue
            said = " ".join([r.title, *r.words, r.files, r.note])
            names = bool(head_re and head_re.search(said))
            out.append({"what": f"rule change {r.key}: {r.title}", "on": decided.isoformat(),
                        "source": f"specification:rule_change_records/{r.key}",
                        "strength": "names this section" if names else "same document, in the window",
                        "outcome": getattr(getattr(r, "outcome", None), "value", ""), "passage": r.note[:300]})
        stores_minutes = self.minutes()
        stores = self._minutes[0] if self._minutes else None
        if stores is None:
            return out
        name_re = re.compile("|".join(re.escape(n) for n in self.names if len(n) > 4), re.I) if self.names else None
        for day in sorted(stores_minutes):
            if day > last or (start is not None and day < start):
                continue
            for m in stores_minutes[day]:
                if getattr(m, "confidential", False):
                    continue
                text = stores.text(m.id)
                for pat, strength in ((head_re, "the minutes name this section"),
                                      (name_re, "the minutes name the document")):
                    hit = None
                    for found in (pat.finditer(text) if pat else ()):
                        window = text[max(0, found.start() - 300):found.end() + 300]
                        if _ADOPT.search(window):
                            hit = window
                            break
                    if hit:
                        out.append({"what": f"the minutes of {day}", "on": day.isoformat(), "source": m.label,
                                    "strength": strength, "passage": " ".join(hit.split())[:400]})
                        break
        return out


# ---------------------------------------------------------------------------------------------------------------------
# Building the history.

def _change_row(c: Change) -> dict[str, Any]:
    return c.row()


def _first_saved(lin: Lineage, chain: list[Version], a: int, b: int, after: Unit | None) -> str:
    """The first chain version between ``a`` and ``b`` that already has the later words (or no longer has the
    section): when the change was first saved."""
    for k in range(a + 1, b + 1):
        u = lin.unit_at(k)
        if (after is None and u is None) or (after is not None and u is not None and u.stream == after.stream):
            return chain[k].label
    return chain[b].label


STRONG = ("names this section", "the minutes name this section")


def _finding(va: Version, vb: Version, adoption: list[dict[str, Any]]) -> str:
    """Empty when an adoption on record names the section; otherwise the finding, with any adoption of the same
    document in the window named as only a possibility (it does not name this section)."""
    if any(a["strength"] in STRONG for a in adoption):
        return ""
    text = f"changed between {va.label} ({va.id}) and {vb.label} ({vb.id}); no adoption found"
    weak = [a for a in adoption if a["strength"] not in STRONG]
    if weak:
        text += ("; in the window, but it does not name this section: "
                 + "; ".join(f"{a['what']} ({a['on']})" for a in weak[:2]))
    return text


def _stage(version: Version, adoption: list[dict[str, Any]]) -> Stage:
    if any(a.get("strength") in STRONG for a in adoption):
        return Stage.ADOPTED
    if version.outbound:
        return Stage.DISTRIBUTED
    return Stage.DRAFT


def build(community: Any, data_dir: Path, key: str, *, ocr: bool = False,
          log: Callable[[str], None] = lambda s: None) -> dict[str, Any]:
    """The document's versions, its sections' lineages, and every change between consecutive milestones, with the
    adoption on record for each (or the finding that none is)."""
    root = Path(data_dir)
    series, versions, missing, notes = collect(community, root, key, ocr=ocr, log=log)
    chain, current = arrange(versions, log=log)
    result: dict[str, Any] = {"key": key, "title": series.title, "driveId": series.drive_id,
                              "built": date.today().isoformat(), "versions": [], "missing": [s.row() for s in missing],
                              "notes": notes, "chain": [], "milestones": [], "changes": [], "lineages": [],
                              "side": [], "counts": {}}
    if current is None or not chain:
        result["notes"].append("no version of this document is on disk")
        return result
    steps = [align(chain[k].units, chain[k + 1].units, ocr=chain[k].ocr or chain[k + 1].ocr)
             for k in range(len(chain) - 1)]
    lins = lineages(key, [v.label for v in chain], [v.units for v in chain], steps)
    marks = milestones(chain)
    adoptions = Adoptions(community, root, key, series.phrases)
    streams = ["".join(u.stream for u in v.units) for v in chain]
    changes: list[dict[str, Any]] = []
    timelines: dict[str, list[RecordVersion]] = {lin.id: [] for lin in lins}
    for lin in lins:
        if lin.first in marks or lin.first == 0:
            u0 = lin.steps[0].unit
            v0 = chain[lin.first]
            timelines[lin.id].append(RecordVersion(key, "", _stage(v0, []), v0.on, None, _source(v0),
                                                   "first seen", f"{u0.number}: first seen in {v0.id}"))
    for a, b in zip(marks, marks[1:]):
        va, vb = chain[a], chain[b]
        for lin in lins:
            c = between(lin, a, b, ocr=va.ocr or vb.ocr, old=streams[a], new=streams[b])
            if c is None or not c.real:
                continue
            unit = c.after or c.before
            head = unit.head if unit else ""
            adoption = adoptions.find(va.on, vb.on, head, unit.title if unit else "")
            first = _first_saved(lin, chain, a, b, c.after)
            row = {"lineage": lin.id, "from": va.id, "to": vb.id,
                   "fromOn": va.label, "toOn": vb.label, "firstSaved": first,
                   "kind": c.kind.value, "renumbered": c.renumbered, "moved": c.moved,
                   "numberBefore": c.before.number if c.before else "", "numberAfter": c.after.number if c.after else "",
                   "head": head, "title": (unit.title if unit else "")[:120],
                   "flags": [f.value for f in c.flags],
                   "before": c.before.words if c.before else "", "after": c.after.words if c.after else "",
                   "ops": [o.row() for o in c.ops if not o.noise],
                   "adoption": adoption,
                   "finding": _finding(va, vb, adoption)}
            changes.append(row)
            stage = _stage(vb, adoption)
            decided = next((x["on"] for x in adoption if x["strength"] in STRONG), None)
            timelines[lin.id].append(RecordVersion(
                key, "", stage, vb.on, date.fromisoformat(decided) if decided else None, _source(vb),
                "; ".join(x["what"] for x in adoption[:2]) or "no adoption found",
                f"{c.kind.value}" + (f" ({', '.join(f.value for f in c.flags)})" if c.flags else "")
                + f": {row['numberBefore'] or '-'} -> {row['numberAfter'] or '-'}; first saved {first}"))
    for v in versions:
        if v.role in ("side", "partial") and v.units:
            near = max(chain, key=lambda c: len(c.runs & v.runs))
            got = [c for c in align(near.units, v.units, ocr=v.ocr or near.ocr) if c.real]
            if v.role == "partial":
                got = [c for c in got if c.kind is not ChangeKind.REMOVED]
            result["side"].append({"version": v.id, "role": v.role, "against": near.id,
                                   "changes": [_change_row(c) for c in _wording(got)]})
    for lin in lins:
        last = lin.unit_at(len(chain) - 1)
        result["lineages"].append({
            "id": lin.id, "first": chain[lin.first].id, "numbers": _numbers(lin),
            "current": last.number if last else "", "ended": chain[lin.ended].id if lin.ended is not None else "",
            "splitFrom": lin.split_from, "mergedInto": lin.merged_into,
            "timeline": [_version_row(rv) for rv in timelines[lin.id]]})
    result["suggestions"] = _suggestions(root, versions, current)
    result["versions"] = [v.row() for v in sorted(versions, key=lambda v: int(v.id[1:]))]
    result["chain"] = [v.id for v in chain]
    result["current"] = current.id
    result["milestones"] = [chain[k].id for k in marks]
    flagged = [c for c in changes if c["flags"]]
    result["changes"] = sorted(changes, key=_change_order)
    result["counts"] = {"versions": len([v for v in versions if v.role != "excluded"]), "chain": len(chain),
                        "milestones": len(marks), "changes": len(changes), "flagged": len(flagged),
                        "noAdoption": sum(1 for c in changes if c["finding"]),
                        "renumberedOnly": sum(1 for c in changes if c["kind"] in ("renumbered", "moved")),
                        "lineages": len(lins)}
    return result


def _suggestions(root: Path, versions: list[Version], current: Version) -> list[dict[str, Any]]:
    """The current Doc's pending suggestions (words proposed in the Doc, not accepted), each with the first revision
    that already carried it. A suggestion is neither the text in force nor a noticed proposal: it is a lead."""
    latest = max((s for s in current.sightings if s.source == "drive-revision" and s.on), key=lambda s: s.on,
                 default=None)
    if latest is None:
        return []
    now = cached_read(root, root / latest.path, latest.sha).get("suggestions") or []
    revs = sorted((s for v in versions for s in v.sightings if s.source == "drive-revision" and s.on and s.sha
                   and s.ref.split("@")[0] == latest.ref.split("@")[0]), key=lambda s: s.on)
    out = []
    for kind, words in now:
        since = next((s for s in revs if [kind, words] in (cached_read(root, root / s.path, s.sha).get("suggestions")
                                                            or [])), latest)
        out.append({"kind": kind, "words": words, "since": since.on.isoformat() if since.on else None,
                    "revision": since.ref})
    return out


def _source(v: Version) -> str:
    if v.revision:
        return f"drive:{v.revision}"
    s = min(v.sightings, key=lambda s: (s.on or date.max)) if v.sightings else None
    return f"{s.source}:{s.ref}" if s else ""


def _numbers(lin: Lineage) -> list[str]:
    out: list[str] = []
    for s in lin.steps:
        if not out or out[-1] != s.unit.number:
            out.append(s.unit.number)
    return out


def _version_row(v: RecordVersion) -> dict[str, Any]:
    return {"stage": v.stage.value, "on": v.on.isoformat() if v.on else None,
            "effective": v.effective.isoformat() if v.effective else None, "source": v.source, "event": v.event,
            "note": v.note, "label": v.label()}


_FLAG_RANK = {f.value: k for k, f in enumerate(Flag)}


def _change_order(c: dict[str, Any]) -> tuple:
    rank = min((_FLAG_RANK[f] for f in c["flags"]), default=len(_FLAG_RANK))
    kind = {"reworded": 0, "added": 1, "removed": 1, "split": 2, "merged": 2, "moved": 3, "renumbered": 4}
    return (c["toOn"], rank, kind.get(c["kind"], 5), c["numberAfter"] or c["numberBefore"])


# ---------------------------------------------------------------------------------------------------------------------
# Fetching (reading Drive and PayHOA; nothing there changes).

def _slim(data: bytes) -> bytes:
    """A Word export without its images and fonts: the parts ``docx_text`` and the printed dates read."""
    import io

    src = zipfile.ZipFile(io.BytesIO(data))
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as out:
        for n in src.namelist():
            if _KEEP_PARTS.match(n):
                out.writestr(n, src.read(n))
    return buf.getvalue()


def fetch_drive(drive: Any, community: Any, data_dir: Path, key: str, *,
                log: Callable[[str], None] = print) -> dict[str, Any]:
    """Read the Doc's kept revisions (each exported as a Word file) and the Drive files named like the document that
    are not on disk yet. Read-only."""
    root = Path(data_dir)
    series = series_of(community, key)
    files, other_docs = _drive_files(root, series)
    report = {"revisions": 0, "exported": 0, "files": 0, "errors": []}
    docs = ([{"id": series.drive_id, "name": series.title}] if series.drive_id else []) + other_docs
    for doc in docs:
        doc_id = str(doc["id"])
        folder = root / REV_DIR / key / "drive" / doc_id
        folder.mkdir(parents=True, exist_ok=True)
        try:
            revs = drive.list_revisions(doc_id)
        except Exception as exc:
            report["errors"].append(f"{doc_id}: listing revisions: {exc}")
            continue
        keep = [{k: r.get(k) for k in ("id", "modifiedTime", "keepForever", "published")} for r in revs]
        (folder / "revisions.json").write_text(json.dumps({"id": doc_id, "name": doc.get("name") or series.title,
                                                           "path": doc.get("path") or "", "read": date.today().isoformat(),
                                                           "revisions": keep}, indent=1), encoding="utf-8")
        report["revisions"] += len(revs)
        import time

        for r in revs:
            out = folder / f"{r['id']}.docx"
            link = (r.get("exportLinks") or {}).get(DOCX_MIME)
            if out.is_file() or not link:
                continue
            try:
                out.write_bytes(_slim(drive.export_revision(link)))
                report["exported"] += 1
                time.sleep(EXPORT_PAUSE)          # Google limits revision exports; a steady pace avoids its 429s
            except Exception as exc:
                report["errors"].append(f"{doc_id}@{r['id']}: {exc}")
        log(f"{key}: {doc_id}: {len(revs)} revisions kept by Drive")
    for s in files:
        if s.path:
            continue
        ext = Path(s.name).suffix.lower() or ".bin"
        dest = root / FILES / f"{s.ref}{ext}"
        try:
            drive.download(s.ref, dest)
            report["files"] += 1
        except Exception as exc:
            report["errors"].append(f"{s.ref} {s.name}: {exc}")
    return report


def fetch_payhoa(client: Any, org_id: int, community: Any, data_dir: Path, key: str, *,
                 log: Callable[[str], None] = print) -> dict[str, Any]:
    """Download the PayHOA library files named like the document that are not on disk, one by one (two uploads may
    share a name). Read-only."""
    root = Path(data_dir)
    series = series_of(community, key)
    report = {"files": 0, "errors": []}
    for s in _payhoa(root, series):
        doc_id = s.ref.split(":", 1)[1]
        target = root / PAYHOA_FILES / doc_id
        if s.path and s.path.startswith(PAYHOA_FILES):
            continue
        tmp = target / "_download.zip"
        try:
            target.mkdir(parents=True, exist_ok=True)
            client.bulk_download_documents(org_id, [int(doc_id)], tmp)
            with zipfile.ZipFile(tmp) as archive:
                for info in archive.infolist():
                    if not info.is_dir():
                        (target / Path(info.filename).name).write_bytes(archive.read(info))
                        report["files"] += 1
        except Exception as exc:
            report["errors"].append(f"payhoa {doc_id} {s.name}: {exc}")
        finally:
            if tmp.exists():
                tmp.unlink()
    log(f"{key}: {report['files']} PayHOA files fetched")
    return report


# ---------------------------------------------------------------------------------------------------------------------
# Storing, reading back, and the report.

def path_of(data_dir: Path, key: str) -> Path:
    return Path(data_dir) / REV_DIR / f"{key}.json"


def write(data_dir: Path, result: dict[str, Any]) -> tuple[Path, Path]:
    root = Path(data_dir)
    out = path_of(root, result["key"])
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=1, ensure_ascii=False), encoding="utf-8")
    page = root / REPORTS / f"revisions-{result['key']}.md"
    page.parent.mkdir(parents=True, exist_ok=True)
    page.write_text("\n".join(report_lines(result)) + "\n", encoding="utf-8")
    return out, page


def load(data_dir: Path, key: str) -> dict[str, Any] | None:
    try:
        return json.loads(path_of(data_dir, key).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def history(data_dir: Path, key: str) -> dict[str, Any]:
    """The stored revision history of one document, read-only (``jason revisions KEY`` builds it). A miss says how to
    build it. For the governance MCP: repeat that a change with no adoption found is a finding, not proof that none
    happened, and that a Drive revision is a saved draft, not an adopted text."""
    got = load(data_dir, key)
    if got is None:
        return {"key": key, "error": f"no revision history for {key}; run: jason revisions {key}"}
    return got


def section_history(data_dir: Path, key: str, number: str) -> dict[str, Any]:
    """One section's lineage and every change to it, by any number it has had or its lineage id (read-only)."""
    got = history(data_dir, key)
    if "error" in got:
        return got
    want = number.strip()
    lins = [l for l in got.get("lineages") or [] if l["id"] == want or want in l["numbers"] or l["current"] == want]
    ids = {l["id"] for l in lins}
    return {"key": key, "section": want, "lineages": lins,
            "changes": [c for c in got.get("changes") or [] if c["lineage"] in ids]}


def _q(words: str, limit: int = 600) -> str:
    w = " ".join((words or "").split())
    return (w[:limit] + " ...") if len(w) > limit else w


def _version_line(v: dict[str, Any]) -> str:
    seen = [s for s in v["sightings"]]
    outbound = sum(1 for s in seen if s["outbound"])
    sources = sorted({s["source"] for s in seen})
    return (f"| {v['id']} | {v['on'] or 'undated'} | {v['onFrom'][:70]} | {v['role']}{' (milestone)' if v['milestone'] else ''}"
            f" | {v['method'][:40]} | {len(seen)} ({outbound} sent or published) | {', '.join(sources)} |"
            f" {v['hash'][:10]} |")


def report_lines(result: dict[str, Any]) -> list[str]:
    """The Markdown report: the versions, then each change between milestones with its words before and after, quoted,
    the adoption on record or the finding that none was found."""
    out = [f"# Revisions: {result['title']}", "",
           f"_Built {result['built']}. Private: it quotes the association's documents. A Drive revision is a saved "
           f"edit of the working Doc, not an adopted text; \"no adoption found\" is a finding for a person, not proof "
           f"that none happened._", ""]
    c = result.get("counts") or {}
    out += [f"**{c.get('versions', 0)} versions** ({c.get('chain', 0)} on the chain, {c.get('milestones', 0)} "
            f"milestones). **{c.get('changes', 0)} changes** between milestones, {c.get('flagged', 0)} touching an "
            f"amount, a period, a fine, a number, or a shall/may; {c.get('noAdoption', 0)} with no adoption found; "
            f"{c.get('renumberedOnly', 0)} only moved or renumbered.", ""]
    out += ["## Versions", "", "| id | date | the date is | role | read as | sightings | sources | words |",
            "|---|---|---|---|---|---|---|---|"]
    out += [_version_line(v) for v in result.get("versions") or []]
    out += ["", "Roles: **chain** (compared in order), **copy** (the same words as a chain version up to export "
            "differences), **side** (differs from every revision), **partial** (an excerpt), **rewritten** (an earlier "
            "text under the document's own title that the current one replaced wholesale: listed, not aligned), "
            "**excluded** (named like the document, but its words are not this document's)."]
    if result.get("missing"):
        out += ["", "### Named like the document, not on disk", ""]
        out += [f"- {s['source']} {s['ref']}: {s['name']} ({s['on']}, {s['how']})" for s in result["missing"]]
        out += ["", "`jason revisions KEY --fetch` reads these (Drive and PayHOA, read-only)."]
    if result.get("notes"):
        out += ["", "### Files not read", ""] + [f"- {n}" for n in result["notes"]]
    versions = {v["id"]: v for v in result.get("versions") or []}
    for v in result.get("versions") or []:
        if v.get("printed") or any(d["how"] == "printed in the text" for d in v.get("dates") or []):
            pass
    printed = [(v["id"], d) for v in result.get("versions") or [] for d in v.get("dates") or []
               if d["how"] in ("printed in the text",)]
    if printed:
        out += ["", "### Dates the versions print", ""]
        out += [f"- {vid}: {d['on']}: \"{d['from']}\"" for vid, d in printed]
    if result.get("suggestions"):
        out += ["", "## Pending suggestions in the Doc", "",
                "Words suggested in the working Doc and not accepted. The Doc's text and its PDF leave them out; a "
                "suggestion is not the text in force and not a noticed proposal.", ""]
        out += [f"- {s['kind']} \"{_q(s['words'], 300)}\" (in the Doc since {s['since']})" for s in result["suggestions"]]
    changes = [x for x in result.get("changes") or [] if x["kind"] not in ("moved", "renumbered")]
    if changes:
        out += ["", "## Changes", "", "Flagged changes first within each milestone (an amount, a period, a fine, a "
                "shall/may, a number). Words are quoted as each version has them.", ""]
    milestone = None
    for x in changes:
        key = (x["from"], x["to"])
        if key != milestone:
            milestone = key
            out += ["", f"### {x['fromOn']} ({x['from']}) to {x['toOn']} ({x['to']})", ""]
        num = x["numberAfter"] or x["numberBefore"]
        renum = f" (was {x['numberBefore']})" if x["numberBefore"] and x["numberAfter"] and \
            x["numberBefore"] != x["numberAfter"] else ""
        flags = f" **[{', '.join(x['flags'])}]**" if x["flags"] else ""
        out.append(f"#### {num}{renum}: {x['kind']}{flags}")
        out.append("")
        out.append(f"- lineage `{x['lineage']}`; first saved {x['firstSaved']}")
        if x["kind"] == "reworded" and x["ops"]:
            for o in x["ops"][:12]:
                b, a = _q(o["before"], 300), _q(o["after"], 300)
                tag = f" [{', '.join(o['flags'])}]" if o["flags"] else ""
                if o["op"] == "replace":
                    out.append(f"- replaced \"{b}\" with \"{a}\"{tag}")
                elif o["op"] == "delete":
                    out.append(f"- struck \"{b}\"{tag}")
                else:
                    out.append(f"- added \"{a}\"{tag}")
            out.append(f"- before: \"{_q(x['before'])}\"")
            out.append(f"- after: \"{_q(x['after'])}\"")
        elif x["kind"] in ("added", "split"):
            out.append(f"- words: \"{_q(x['after'])}\"")
        elif x["kind"] in ("removed", "merged"):
            out.append(f"- words removed: \"{_q(x['before'])}\"")
        if x["adoption"]:
            for a in x["adoption"][:3]:
                out.append(f"- adoption on record: {a['what']} ({a['on']}; {a['strength']})"
                           + (f": \"{_q(a.get('passage', ''), 300)}\"" if a.get("passage") else ""))
        else:
            out.append(f"- **finding:** {x['finding']}")
        out.append("")
    moved = [x for x in result.get("changes") or [] if x["kind"] in ("moved", "renumbered")]
    if moved:
        out += ["", "## Moved or renumbered, words unchanged", ""]
        out += [f"- {x['fromOn']} to {x['toOn']}: {x['numberBefore']} -> {x['numberAfter']} ({x['kind']})"
                for x in moved]
    if result.get("side"):
        out += ["", "## Copies that match no revision", ""]
        for s in result["side"]:
            v = versions.get(s["version"], {})
            out += [f"### {s['version']} ({v.get('on')}, {s['role']}) against {s['against']}", ""]
            for ch in s["changes"][:40]:
                before = (ch.get("before") or {}).get("words", "")
                after = (ch.get("after") or {}).get("words", "")
                num = (ch.get("after") or ch.get("before") or {}).get("number", "")
                out.append(f"- {num}: {ch['kind']}" + (f" [{', '.join(ch['flags'])}]" if ch["flags"] else "")
                           + (f"; \"{_q(before, 200)}\" -> \"{_q(after, 200)}\"" if ch["kind"] == "reworded" else
                              f"; \"{_q(after or before, 200)}\""))
            out.append("")
    return out


def lines(result: dict[str, Any], *, versions: bool = False) -> list[str]:
    """A terminal summary."""
    c = result.get("counts") or {}
    out = [f"{result['key']}: {c.get('versions', 0)} versions, chain {c.get('chain', 0)}, milestones "
           f"{c.get('milestones', 0)}; {c.get('changes', 0)} changes ({c.get('flagged', 0)} flagged, "
           f"{c.get('noAdoption', 0)} with no adoption found)"]
    if versions:
        for v in result.get("versions") or []:
            out.append(f"  {v['id']:>4} {v['on'] or 'undated':10} {v['role']:8}{'*' if v['milestone'] else ' '} "
                       f"{len(v['sightings']):3} sightings  {v['method'][:30]:30} {v['onFrom'][:60]}")
    for x in result.get("changes") or []:
        if not x["flags"]:
            continue
        out.append(f"  {x['toOn']} {x['numberAfter'] or x['numberBefore']}: {x['kind']} [{', '.join(x['flags'])}]"
                   + ("" if x["adoption"] else "  (no adoption found)"))
    return out


# ---------------------------------------------------------------------------------------------------------------------
# The manual's adoption history: dated copies and section changes, for a document jason manual takes apart.

def _ordinal(n: int) -> str:
    return {2: "2nd", 3: "3rd"}.get(n, f"{n}th")


def outline_names(data_dir: Path, key: str, current: list[Unit]) -> dict[str, str]:
    """Each current section's name as the Doc's outline (``data/outlines/<key>.json``) gives it: its number, or its
    title, with " (2nd)" for a name used again, matched by opening words. A section the outline lacks is left out."""
    from jason.community.outline_align import opening_key, similarity
    from jason.community.outlines import DocumentOutline

    path = Path(data_dir) / "outlines" / f"{key}.json"
    try:
        outline = DocumentOutline.from_dict(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError, TypeError):
        return {}
    seen: dict[str, int] = {}
    names: list[tuple[str, str]] = []
    for i, s in enumerate(outline.sections):
        end = outline.sections[i + 1].start if i + 1 < len(outline.sections) else len(outline.text)
        name = s.number or s.title
        seen[name] = seen.get(name, 0) + 1
        names.append((f"{name} ({_ordinal(seen[name])})" if seen[name] > 1 else name,
                      opening_key(outline.text[s.start:end])))
    out: dict[str, str] = {}
    taken: set[int] = set()
    for u in current:
        key_u = u.opening
        if len(key_u) < 6:
            continue
        best = max(((similarity(key_u, k), -abs(i - u.index), i) for i, (_, k) in enumerate(names)
                    if i not in taken and len(k) >= 6), default=None)
        if best and best[0] >= 0.85:
            out[u.number] = names[best[2]][0]
            taken.add(best[2])
    return out


def _current_units(data_dir: Path, result: dict[str, Any]) -> list[Unit]:
    cur = next((v for v in result.get("versions") or [] if v["id"] == result.get("current")), None)
    for f in (cur or {}).get("files") or []:
        path = Path(data_dir) / f["path"]
        if path.is_file():
            got = cached_read(Path(data_dir), path, f["sha256"])
            if got.get("text"):
                return units(outline_text(got["text"], key=result["key"]))
    return []


def manual_history(data_dir: Path, result: dict[str, Any], current: list[Unit] | None = None) -> Path | None:
    """Write the detector's rows to the manual's history (``jason.tasks.manual.history_path``) when jason manual keeps
    a store for this document: one "in force" row for each dated copy someone outside the Doc saw, and one for each
    section change that copy shows, named by its new address where the concordance has one. Other sources' rows are
    kept; the detector's own are replaced."""
    try:
        from jason.community.manual import AdoptionAction, AdoptionEvent, Concordance, resolve_old
        from jason.tasks.manual import history_path, store
    except ImportError:
        return None
    key = result["key"]
    folder = Path(data_dir) / "manual" / key
    if not folder.is_dir():
        return None
    rows: list[Concordance] = []
    try:
        raw = json.loads((folder / "concordance.json").read_text(encoding="utf-8"))
        rows = [Concordance(**r) for r in raw.get("rows") or []]
    except (OSError, json.JSONDecodeError, TypeError):
        pass
    names = outline_names(data_dir, key, current if current is not None else _current_units(data_dir, result))
    lineage_now = {l["id"]: l["current"] for l in result.get("lineages") or []}

    def address(lineage: str, number: str) -> tuple[str, str]:
        now = lineage_now.get(lineage, "")
        old = names.get(now, "") if now else ""
        new = resolve_old(rows, old) if (old and rows) else ""
        return (new or old or number), old

    versions = {v["id"]: v for v in result.get("versions") or []}
    events: list[AdoptionEvent] = []
    for vid in result.get("milestones") or []:
        v = versions[vid]
        sent = [s for s in v["sightings"] if s["outbound"]]
        if not sent or not v["on"]:
            continue
        first = min(sent, key=lambda s: s["on"] or "9999")
        events.append(AdoptionEvent(date.fromisoformat(v["on"]), AdoptionAction.IN_FORCE, (),
                                    f"a dated copy ({vid}, {v['onFrom']}); {len(sent)} sent or published, first "
                                    f"{first['how']} {first['on']} ({first['source']} {first['ref']})",
                                    source="detector", version=f"{vid}@{v['on']}", digest=v["hash"], note=v["method"]))
    for c in result.get("changes") or []:
        v = versions.get(c["to"]) or {}
        if c["kind"] in ("moved", "renumbered") or not any(s["outbound"] for s in v.get("sightings") or []):
            continue                     # a number that moved with its words is the concordance's, not a change
        where, old = address(c["lineage"], c["numberAfter"] or c["numberBefore"])
        words = c["after"] or c["before"]
        digest = hashlib.sha256(" ".join(words.split()).encode("utf-8")).hexdigest()[:16]
        what = c["kind"] + (f" [{', '.join(c['flags'])}]" if c["flags"] else "")
        summary = "; ".join(f"\"{o['before'][:80]}\" -> \"{o['after'][:80]}\"" for o in c["ops"][:3])
        adoption = "; ".join(f"{a['what']} ({a['on']}, {a['strength']})" for a in c["adoption"][:2])
        events.append(AdoptionEvent(date.fromisoformat(c["toOn"]), AdoptionAction.IN_FORCE, (where,),
                                    f"{what} between {c['fromOn']} and {c['toOn']}, first saved {c['firstSaved']}"
                                    + (f": {summary}" if summary else ""),
                                    source="detector", version=f"{c['to']}@{c['toOn']}", digest=digest,
                                    note=(c["finding"] or adoption) + (f" (outline: {old})" if old else
                                                                       f" (lineage {c['lineage']})")))
    path = history_path(data_dir, key)
    kept: list[dict[str, Any]] = []
    if path.is_file():
        try:
            kept = [r for r in json.loads(path.read_text(encoding="utf-8")) if r.get("source") != "detector"]
        except (OSError, json.JSONDecodeError):
            kept = []
    store(data_dir, key)
    path.write_text(json.dumps(kept + [e.to_dict() for e in events], indent=1, ensure_ascii=False), encoding="utf-8")
    return path


def diff(community: Any, data_dir: Path, key: str, a: str, b: str, *, ocr: bool = False) -> dict[str, Any]:
    """Two versions compared directly, by id (``v3``), a date (the version current on it), or a hash prefix."""
    _, versions, _, _ = collect(community, data_dir, key, ocr=ocr)
    chain, _ = arrange(versions)

    def pick(token: str) -> Version:
        found = [v for v in versions if v.id == token or v.hash.startswith(token)]
        if not found and re.fullmatch(r"\d{4}-\d{2}-\d{2}", token):
            day = date.fromisoformat(token)
            dated = [v for v in chain if v.on and v.on <= day]
            found = [max(dated, key=lambda v: v.on)] if dated else []
        if not found:
            raise KeyError(f"no version {token} of {key}")
        return found[0]

    va, vb = pick(a), pick(b)
    got = [c for c in align(va.units, vb.units, ocr=va.ocr or vb.ocr) if c.real]
    return {"key": key, "from": va.row(), "to": vb.row(), "changes": [_change_row(c) for c in got]}


__all__ = ["build", "collect", "arrange", "diff", "fetch_drive", "fetch_payhoa", "history", "keys", "lines", "load",
           "milestones", "read_file", "report_lines", "section_history", "series_of", "write"]
