"""Embedded references on disk: fill ``{QUOTE:key#n}`` and ``{CITE:key#n}``, find the copies of a governing document's
sections in other documents, propose tokens for jason's own copies, and compile the guide agents read.

- ``DiskResolver`` fills a reference (``jason.community.section_refs``) from the document kept as amended
  (``living_docs.build``), else from the document's outline (``data/outlines/KEY.json``, a Doc as read). The versions
  of a living document (its text before each amendment in effect, and a draft's proposed words) are built once and
  cached in ``data/section-refs/versions-KEY.json`` until a source, a transcription, or the specification row changes.
- ``hosts`` gathers what may carry a copy, with who owns it (``Owner``): jason's own Markdown and base templates (a
  token may replace the copy, with a person's ``--apply``), the reference material agents read (never a token; a stale
  quote is corrected by hand), the adopted documents and the vendor's templates (report only: a finding for the next
  revision), sent letters and minutes (history: never rewritten), and recorded instruments (never touched).
- ``scan`` runs the detector (``jason.community.embedded_copies``) and writes ``data/section-refs/copies.json`` and
  ``copies.md``. ``proposals`` turns a whole-section copy in jason's own source into a patch; ``apply`` writes one.
- ``guide`` compiles ``data/section-refs/guide/KEY.md``: each section's citation, caption, an excerpt, who set its
  words and when, where it is copied, the statutes it cites, what cites it, the conflicts, notice clauses, and duties
  read from it. It is regenerated, never edited, and is profile data: it stays in ``data/``.

Nothing here writes to Drive, PayHOA, or the mail; ``apply`` writes only a file in jason's own sources a person names.
"""

from __future__ import annotations

import difflib
import hashlib
import json
import re
import sqlite3
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Iterable

from jason.community.embedded_copies import (Copy, CopyKind, Currency, Index, SectionVersion, Version, find,
                                             paraphrases, shared_runs, without)
from jason.community.living import CurrentDocument, Provision, Standing, provisions_of
from jason.community.outlines import DocumentOutline, normalize_number
from jason.community.section_refs import (CAVEAT, AmendedPart, Embedded, SectionRefError, SectionText, TOKEN,
                                          citation_of, expand_html, expand_markdown)

VERSIONS_FORMAT = 1


def store_dir(data_dir: Path) -> Path:
    return Path(data_dir) / "section-refs"


def default_data_dir() -> Path:
    from jason.config import Settings

    return Settings.load().ownership_db.parent


def repo_root() -> Path | None:
    root = Path(__file__).resolve().parents[3]
    return root if (root / "AGENTS.md").is_file() else None


# --- Versions of a living document ------------------------------------------------------------------------------------

def _provision_dict(p: Provision) -> dict[str, Any]:
    return {"number": p.number, "caption": p.caption, "body": p.body, "depth": p.depth, "set_by": p.set_by,
            "dated": p.dated.isoformat() if p.dated else None, "standing": p.standing.value if p.standing else None,
            "history": list(p.history), "removed": p.removed}


def _provision(raw: dict[str, Any]) -> Provision:
    return Provision(raw["number"], raw["caption"], raw["body"], raw["depth"], raw["set_by"],
                     date.fromisoformat(raw["dated"]) if raw.get("dated") else None,
                     Standing(raw["standing"]) if raw.get("standing") else None, list(raw.get("history") or []),
                     bool(raw.get("removed")))


def _fingerprint(living: Any, data_dir: Path) -> str:
    """What a living document's versions depend on: its specification row, its sources and transcriptions on disk,
    and the code that reads and consolidates them."""
    from jason.tasks import living_docs

    h = hashlib.sha256(re.sub(r" object at 0x[0-9A-Fa-f]+", "", repr(living)).encode("utf-8"))
    for li in living.instruments:                  # an instrument's Document by what a build reads of it
        d = li.document
        h.update(repr((li.key, getattr(d, "title", ""), getattr(d, "adopted", None), getattr(d, "recorded", None),
                       getattr(d, "recorder_number", ""))).encode("utf-8"))
    folder = living_docs.living_dir(data_dir, living.key)
    inputs = [*sorted((folder / "sources").glob("*")), folder / "transcriptions.json", folder / "reading.json"]
    for path in inputs:
        if path.is_file():
            st = path.stat()
            h.update(f"{path.name}:{st.st_size}:{int(st.st_mtime)}".encode())
    import jason.community.living as living_mod
    import jason.community.scan_marks as scan_marks
    # scan_marks: a scanned base's text is its kept OCR lines less the furniture as the pass judges it at each read.
    for module in (living_mod, living_docs, scan_marks):
        h.update(hashlib.sha256(Path(module.__file__).read_bytes()).digest())
    return h.hexdigest()[:24]


@dataclass
class Snapshot:
    """The document's text over one period: ``until`` the day before an amendment took effect (None: now)."""

    until: date | None
    through: str                                  # the last instrument applied, described
    provisions: list[Provision]

    def current(self, key: str, title: str, base: str) -> CurrentDocument:
        return CurrentDocument(key, title, base, self.provisions)


@dataclass
class Versions:
    key: str
    title: str
    base: str                                     # base_from
    snapshots: list[Snapshot]                     # oldest first; the last is the text now
    instruments: dict[str, dict[str, Any]] = field(default_factory=dict)   # key -> title, describe, dated, standing
    pending: list[dict[str, Any]] = field(default_factory=list)           # a draft's operations: instrument, section,
                                                                           # caption, after

    @property
    def now(self) -> Snapshot:
        return self.snapshots[-1]

    def at(self, as_of: date | None) -> Snapshot:
        if as_of is None:
            return self.now
        for snap in self.snapshots:
            if snap.until is None or as_of <= snap.until:
                return snap
        return self.now

    def to_dict(self, fingerprint: str) -> dict[str, Any]:
        return {"format": VERSIONS_FORMAT, "fingerprint": fingerprint, "built": date.today().isoformat(),
                "key": self.key, "title": self.title, "base": self.base, "instruments": self.instruments,
                "pending": self.pending,
                "snapshots": [{"until": s.until.isoformat() if s.until else None, "through": s.through,
                               "provisions": [_provision_dict(p) for p in s.provisions]} for s in self.snapshots]}

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> Versions:
        snaps = [Snapshot(date.fromisoformat(s["until"]) if s.get("until") else None, s.get("through", ""),
                          [_provision(p) for p in s["provisions"]]) for s in raw["snapshots"]]
        return cls(raw["key"], raw["title"], raw["base"], snaps, raw.get("instruments") or {}, raw.get("pending") or [])


def build_versions(living: Any, data_dir: Path, *, refresh: bool = False, log=None) -> Versions:
    """The living document's text now and before each amendment in effect, from the saved sources (no network),
    cached until a source or the specification changes."""
    from jason.tasks import living_docs

    data_dir = Path(data_dir)
    path = store_dir(data_dir) / f"versions-{living.key}.json"
    fingerprint = _fingerprint(living, data_dir)
    if path.is_file() and not refresh:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if raw.get("format") == VERSIONS_FORMAT and raw.get("fingerprint") == fingerprint:
            return Versions.from_dict(raw)
    if log:
        log(f"building {living.key} as amended, and as it read before each amendment (from the saved sources)")
    now = living_docs.build(living, data_dir)
    cur = now.current
    instruments = {i.key: {"title": i.title or i.key, "describe": i.describe(),
                           "dated": i.dated.isoformat() if i.dated else None, "standing": i.standing.value}
                   for i in [*cur.applied, *cur.pending]}
    pending = [{"instrument": i.key, "section": op.section, "caption": op.caption, "after": op.after}
               for i in cur.pending for op in i.operations if op.after.strip()]
    dates = sorted({i.dated for i in cur.applied if i.dated})
    snapshots = []
    for d in dates:
        before = living_docs.build(living, data_dir, as_of=d - timedelta(days=1)).current
        snapshots.append(Snapshot(d - timedelta(days=1), before.through.describe() if before.through else "",
                                  before.provisions))
    snapshots.append(Snapshot(None, cur.through.describe() if cur.through else "", cur.provisions))
    out = Versions(living.key, living.title, living.base_from, snapshots, instruments, pending)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out.to_dict(fingerprint), indent=1), encoding="utf-8")
    return out


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip().lower()


def section_versions(v: Versions) -> list[SectionVersion]:
    """Every section's current words, the different words each earlier period had, and a draft's proposed words."""
    now = {p.number: p for p in v.now.provisions if p.number}
    out = [SectionVersion(v.key, p.number, p.caption, p.body, Version.CURRENT,
                          "base" if p.set_by == v.key else p.set_by, removed=p.removed) for p in now.values()]
    seen = {(n, _norm(p.body)) for n, p in now.items() if not p.removed}
    for snap in v.snapshots[:-1]:
        for p in snap.provisions:
            if not p.number or p.removed or (p.number, _norm(p.body)) in seen:
                continue
            seen.add((p.number, _norm(p.body)))
            out.append(SectionVersion(v.key, p.number, p.caption, p.body, Version.SUPERSEDED,
                                      "base" if p.set_by == v.key else p.set_by))
    for op in v.pending:
        number = normalize_number(op["section"])
        if (number, _norm(op["after"])) in seen:
            continue
        out.append(SectionVersion(v.key, number, op.get("caption", ""), op["after"], Version.PENDING,
                                  f"{op['instrument']} (draft)"))
    return out


def outline_versions(outline: DocumentOutline) -> list[SectionVersion]:
    """A document not kept as amended: its sections as its outline reads them, one version each."""
    return [SectionVersion(outline.key, p.number, p.caption, p.body, Version.CURRENT, "as written")
            for p in provisions_of(outline) if p.number]


# --- Filling references ------------------------------------------------------------------------------------------------

def load_outline(data_dir: Path, key: str) -> DocumentOutline | None:
    path = Path(data_dir) / "outlines" / f"{key}.json"
    return DocumentOutline.from_dict(json.loads(path.read_text(encoding="utf-8"))) if path.is_file() else None


_ARTICLE = re.compile(r"^\s*ARTICLE\b", re.I)


class DiskResolver:
    """Fills references from the documents on disk: a living document's versions, else an outline."""

    def __init__(self, data_dir: Path | None = None, community: Any = None, *, log=None):
        self.data_dir = Path(data_dir) if data_dir is not None else default_data_dir()
        if community is None:
            from jason.community import community as active

            community = active()
        self.community = community
        self.log = log
        self._versions: dict[str, Versions] = {}
        self._outlines: dict[str, DocumentOutline | None] = {}

    def living(self, key: str) -> Any:
        return next((d for d in self.community.living_documents() if d.key == key), None)

    def citable(self, key: str) -> Any:
        return next((d for d in self.community.citable_documents() if d.key == key), None)

    def keys(self) -> list[str]:
        keys = [d.key for d in self.community.living_documents()]
        return keys + [d.key for d in self.community.citable_documents() if d.key not in keys]

    def versions(self, key: str) -> Versions:
        if key not in self._versions:
            living = self.living(key)
            if living is None:
                raise SectionRefError(f"{key} is not kept as amended", "not_kept_as_amended")
            try:
                self._versions[key] = build_versions(living, self.data_dir, log=self.log)
            except ValueError as exc:                     # a base that cannot be read: say so, never render nothing
                raise SectionRefError(f"{key}: {exc}", "unreadable") from exc
        return self._versions[key]

    def outline(self, key: str) -> DocumentOutline | None:
        if key not in self._outlines:
            self._outlines[key] = load_outline(self.data_dir, key)
        return self._outlines[key]

    def known(self, key: str) -> bool:
        """A document the profile keeps (living or citable), or any outline on disk (an annexation read from the
        library, a resolution read from its folder)."""
        return self.living(key) is not None or self.citable(key) is not None or self.outline(key) is not None

    def name(self, key: str) -> str:
        """The name a citation uses: the specification's ``cite_as``, else its title; an outline's title for a
        document only an outline knows."""
        doc = self.citable(key)
        if doc is not None:
            return getattr(doc, "cite_as", "") or self._book_name(key) or doc.title
        living = self.living(key)
        if living is not None:
            return living.title
        outline = self.outline(key)
        if outline is not None:
            return outline.title or key
        raise SectionRefError(f"no document {key!r}: the documents are {', '.join(self.keys()) or 'none'}",
                              "unknown_document")

    def _book_name(self, key: str) -> str:
        """The name the community's documents cite this document's book by (``BookEntry.cite_as``), if a row gives
        one."""
        for e in getattr(self.community, "book_entries", lambda: ())():
            if getattr(e, "document", "") == key and getattr(e, "cite_as", ""):
                return e.cite_as
        return ""

    def document(self, key: str, as_of: date | None = None) -> tuple[CurrentDocument, Versions | None]:
        """The document as amended (on ``as_of``, or now) with its versions, or as its outline reads it. The one reader
        a token, ``jason cite``, and the guide share."""
        if self.living(key) is not None:
            v = self.versions(key)
            return v.at(as_of).current(v.key, v.title, v.base), v
        if not self.known(key):
            raise SectionRefError(f"no document {key!r}: the documents are {', '.join(self.keys()) or 'none'}",
                                  "unknown_document")
        if as_of is not None:
            raise SectionRefError(f"{key} is not kept as amended (Community.living_documents()): its text in force on "
                                  f"{as_of.isoformat()} is not known; quote it without as-of", "not_kept_as_amended")
        outline = self.outline(key)
        if outline is None:
            raise SectionRefError(f"{key} has no outline on disk (jason outlines)", "no_outline")
        return CurrentDocument(key, outline.title, f"revision {outline.revision}" if outline.revision else key,
                               provisions_of(outline)), None

    _document = document

    def provision(self, doc: CurrentDocument, key: str, number: str) -> Provision:
        """The one provision numbered ``number``; a miss names the nearest section that is there."""
        found = [p for p in doc.provisions if p.number == number]
        if not found:
            from jason.community.references import ancestors

            parent = next((a for a in ancestors(number) if doc.provision(a) is not None), "")
            near = sorted({p.number for p in doc.provisions if p.number.startswith(number.split("(")[0])})[:8]
            raise SectionRefError(f"{key} has no section {number}" + (f" (near: {', '.join(near)})" if near else ""),
                                  "parent_only" if parent else "not_in_document")
        if len(found) > 1:
            raise SectionRefError(f"{key} numbers {len(found)} sections {number}: the reference is ambiguous",
                                  "ambiguous")
        return found[0]

    _provision = provision

    def citation(self, key: str, number: str) -> str:
        name = self.name(key)
        number = normalize_number(number)
        doc, _ = self._document(key, None)
        p = self._provision(doc, key, number)
        return citation_of(name, number, article=_is_article(p))

    def section(self, key: str, number: str, as_of: date | None = None) -> SectionText:
        number = normalize_number(number)
        doc, versions = self._document(key, as_of)
        p = self._provision(doc, key, number)
        if p.removed:
            raise SectionRefError(f"{key} {number} was removed by {p.set_by}"
                                  + (f" ({p.dated.isoformat()})" if p.dated else "") + "; quote it with an earlier as-of",
                                  "removed")
        words = doc.text_of(number)
        amended = p.standing is not None
        note = ""
        parts: tuple[AmendedPart, ...] = ()
        if versions is not None:
            info = versions.instruments.get(p.set_by) or {}
            set_by_title = (info.get("describe") or p.set_by) if amended else versions.title
            # A subsection another instrument set is part of the words recited: the provenance names it, so it agrees
            # with the section's history (``Citation.history``, which lists its subsections' instruments too).
            parts = tuple(AmendedPart(q.number, (versions.instruments.get(q.set_by) or {}).get("describe") or q.set_by,
                                      q.dated)
                          for q in doc.provisions
                          if q.number != number and (q.number.startswith(number + "(") or q.number.startswith(number + "."))
                          and q.standing is not None and not (amended and q.set_by == p.set_by))
            source = versions.base
            now = versions.now.current(versions.key, versions.title, versions.base)
            if as_of is None or now.text_of(number) == words:
                words, note = self._typeset(key, number, words)
            elif not amended:
                note = "earlier words, as the base was read (by OCR, if it was scanned): check them against the recorded copy"
        else:
            set_by_title, source = doc.title, doc.base
        return SectionText(key, number, p.caption, words, self.citation(key, number), doc.title, p.set_by,
                           set_by_title, p.dated, amended, as_of, source, note, parts)

    def _typeset(self, key: str, number: str, words: str) -> tuple[str, str]:
        """A base read by OCR runs words together ("EachOwner shallpurchase"). When the working copy kept by hand has
        the very same letters and digits for the section, its spacing and punctuation are used: an editorial change
        only, as a spacing correction is. When the letters differ, the consolidated words stay, with a note to check
        them before the document goes out (``jason intake`` takes the corrections)."""
        living = self.living(key)
        copy = self.outline(key)
        if living is None or copy is None or not living.working_doc or copy.source != living.working_doc:
            return words, ""
        from jason.community.embedded_copies import stream

        theirs = CurrentDocument(key, copy.title, "", provisions_of(copy))
        if theirs.provision(number) is None:
            return words, "not in the working copy: check the words before sending"
        other = theirs.text_of(number)
        if stream(other) == stream(words):
            return other, ""
        if re.sub(r"\s+", " ", other).strip() == re.sub(r"\s+", " ", words).strip():
            return words, ""
        return words, ("its letters differ from the working copy's (an OCR slip, or drift): check the words before "
                       "sending (jason living KEY --working; jason intake)").replace("KEY", key)


def _first_line(text: str) -> str:
    return (text or "").strip().split("\n", 1)[0]


def fill_markdown(text: str, data_dir: Path | None = None, community: Any = None) -> tuple[str, list[Embedded]]:
    """Markdown with its references filled; text with none is returned as it is, without reading anything. Raises
    ``SectionRefError`` on a reference that cannot be filled."""
    if not TOKEN.search(text or ""):
        return text, []
    return expand_markdown(text, DiskResolver(data_dir, community))


def fill_html(text: str, data_dir: Path | None = None, community: Any = None) -> tuple[str, list[Embedded]]:
    if not TOKEN.search(text or ""):
        return text, []
    return expand_html(text, DiskResolver(data_dir, community))


def record_lines(records: Iterable[Embedded]) -> list[str]:
    return [f"{r.token}: {r.citation}" + (f", set by {r.set_by_title}" if r.set_by_title else "")
            + (f" ({r.dated})" if r.dated else "") + (f", as of {r.as_of}" if r.as_of else "")
            + (f", words {r.digest}" if r.digest else "") + (f"; NOTE: {r.note}" if r.note else "") for r in records]


# --- Hosts: what may carry a copy, and who owns it ---------------------------------------------------------------------

class Owner(Enum):
    JASON = "jason's source"             # Markdown owner documents and base templates: a token may replace a copy
    REFERENCE = "agent reference"        # docs and notes agents read: keep the words; correct a stale quote
    ADOPTED = "adopted document"         # bylaws, rules, policies, resolutions: a finding for the next revision
    TEMPLATE = "vendor template"         # templates jason does not own (PayHOA's, Drive's): report only
    HISTORY = "sent"                     # letters, notices, minutes as sent: history, never rewritten
    RECORDED = "recorded"                # recorded instruments and public records: never touched
    SELF = "the document itself"         # a copy or an instrument of the document looked for


TOKENIZABLE = frozenset({Owner.JASON})

_RECORDED_KINDS = frozenset({"declaration", "amendment", "annexation", "articles", "condominium_plan", "map",
                             "grant_deed", "recorded_lien", "dre_report", "plan_set", "owner_history"})
_ADOPTED_KINDS = frozenset({"operating_rules", "policy", "bylaws", "election_rules", "resolution"})
_TEMPLATE_KINDS = frozenset({"template", "form"})


@dataclass
class Host:
    name: str                            # how the report names it: a library path, a repo path, an outline key
    path: str                            # where it is read ("" for an outline held in data/outlines)
    text: str
    owner: Owner
    kind: str = ""                       # the library's kind, or "outline", "markdown", "template"
    also: list[str] = field(default_factory=list)       # the same file under other names (one digest)
    paraphrase: bool = False             # also look for paraphrases (short sources only)


def masked(text: str) -> str:
    """HTML with its tags and entities blanked to spaces of the same length, so the words are matched and the offsets
    still point into the file."""
    return re.sub(r"<[^>]*>|&[#a-zA-Z0-9]+;", lambda m: " " * len(m.group(0)), text)


def _library_owner(kind: str, own_kinds: set[str] | frozenset[str] = frozenset()) -> Owner:
    if kind in own_kinds:
        return Owner.SELF
    if kind in _RECORDED_KINDS:
        return Owner.RECORDED
    if kind in _ADOPTED_KINDS:
        return Owner.ADOPTED
    if kind in _TEMPLATE_KINDS:
        return Owner.TEMPLATE
    return Owner.HISTORY


def _outline_owner(outline: DocumentOutline, targets: set[str], community: Any) -> Owner:
    kind = (outline.kind or "").lower()
    if outline.key in targets or (outline.amends and outline.amends in targets):
        return Owner.SELF
    if kind in ("annexation", "declaration", "amendment"):
        return Owner.RECORDED
    return Owner.ADOPTED


def hosts(data_dir: Path, community: Any, targets: Iterable[str], *, library: bool = True,
          confidential: bool = False, repo: Path | None = None, own_sources: bool = True) -> list[Host]:
    """Every document that may carry a copy of the ``targets``' sections, with its owner."""
    data_dir = Path(data_dir)
    targets = set(targets)
    out: list[Host] = []
    # The outlines: the association's Docs as read (its adopted documents), and the recorded ones read from extracts.
    odir = data_dir / "outlines"
    if odir.is_dir():
        for path in sorted(odir.glob("*.json")):
            if path.name == "references.json":
                continue
            o = DocumentOutline.from_dict(json.loads(path.read_text(encoding="utf-8")))
            out.append(Host(f"outline:{o.key}", str(path), o.text, _outline_owner(o, targets, community), "outline",
                            paraphrase=True))
    # jason's own sources: owner documents in Markdown, and the base and profile templates.
    drafts = data_dir / "drafts"
    if drafts.is_dir():
        for path in sorted(drafts.rglob("*")):
            if not path.is_file() or "superseded" in path.parts or ".preview" in path.name or path.name.endswith(".bak"):
                continue
            if path.suffix in (".md", ".html"):
                text = path.read_text(encoding="utf-8", errors="replace")
                out.append(Host(path.relative_to(data_dir).as_posix(), str(path),
                                masked(text) if path.suffix == ".html" else text, Owner.JASON,
                                "markdown" if path.suffix == ".md" else "html", paraphrase=True))
    repo = (repo or repo_root()) if own_sources else None
    if repo is not None:
        from jason.community.profile import profile_root

        templates = [repo / "src" / "jason" / "templates"]
        root = profile_root()
        if root is not None:
            templates.append(root / "packet_templates")
        for folder in templates:
            for path in sorted(folder.rglob("*")) if folder.is_dir() else ():
                if path.is_file() and path.suffix in (".md", ".html"):
                    text = path.read_text(encoding="utf-8")
                    out.append(Host(path.relative_to(repo).as_posix(), str(path),
                                    masked(text) if path.suffix == ".html" else text, Owner.JASON, "template",
                                    paraphrase=True))
        # The reference material agents read: never a token, a stale quote corrected by hand.
        refs = [repo / "AGENTS.md", repo / "SKILLS.md", repo / "README.md", *sorted((repo / "docs").rglob("*.md"))]
        if root is not None:
            refs += sorted(root.rglob("*.md"))
        for path in refs:
            if path.is_file():
                out.append(Host(path.relative_to(repo).as_posix(), str(path),
                                path.read_text(encoding="utf-8", errors="replace"), Owner.REFERENCE, "markdown",
                                paraphrase=False))
    governing = data_dir / "governing"
    if governing.is_dir():
        for path in sorted(governing.glob("*.md")):
            owner = Owner.SELF if any(path.stem == t or path.stem.startswith(t + "-") for t in targets) else Owner.ADOPTED
            out.append(Host(f"data/governing/{path.name}", str(path), path.read_text(encoding="utf-8", errors="replace"),
                            owner, "export"))
    if library:
        out += library_hosts(data_dir, community, targets, confidential=confidential)
    return out


def library_hosts(data_dir: Path, community: Any, targets: set[str], *, confidential: bool = False) -> list[Host]:
    """The library's text extracts, one host per file digest (the same PDF in several folders is read once)."""
    db = Path(data_dir) / "library" / "library.db"
    if not db.is_file():
        return []
    pinned = set()
    own_kinds: set[str] = set()
    for living in community.living_documents():
        if living.key in targets:
            refs = [living.base, *[i.source for i in living.instruments],
                    *[i.check for i in living.instruments if i.check]]
            pinned |= {r.ref for r in refs}
            # The document's own kind, and its amendments, are copies or instruments of it (a resale copy, a recording).
            own_kinds |= {getattr(living.kind, "value", str(living.kind)), "amendment"}
    with sqlite3.connect(f"{db.resolve().as_uri()}?mode=ro", uri=True) as conn:
        rows = conn.execute("SELECT id, path, kind, confidential, sha256 FROM documents ORDER BY path").fetchall()
    by_digest: dict[str, Host] = {}
    out: list[Host] = []
    for doc_id, path, kind, secret, sha in rows:
        if secret and not confidential:
            continue
        text_path = Path(data_dir) / "library" / "text" / f"{doc_id}.txt"
        if not text_path.is_file():
            continue
        if sha and sha in by_digest:
            by_digest[sha].also.append(path)
            continue
        owner = Owner.SELF if path in pinned else _library_owner(kind or "", own_kinds)
        host = Host(path, str(text_path), text_path.read_text(encoding="utf-8", errors="replace"), owner, kind or "")
        if sha:
            by_digest[sha] = host
        out.append(host)
    return out


# --- The scan ----------------------------------------------------------------------------------------------------------

WHOLE_COPY = 0.25          # a host holding this share of a document's sections (and at least 15) is a copy of it
BOILERPLATE_HOSTS = 8      # a run in more documents than this (and BOILERPLATE_SHARE of them) is boilerplate
BOILERPLATE_SHARE = 0.02


@dataclass
class HostResult:
    host: Host
    copies: list[Copy]
    whole: str = ""                      # the document key when the host is a copy of the whole document

    def as_dict(self) -> dict[str, Any]:
        h = self.host
        return {"host": h.name, "path": h.path, "owner": h.owner.value, "kind": h.kind, "also": h.also,
                "offsetsIn": {"outline": "the outline's text field", "html": "the file (tags blanked)",
                              "template": "the file (tags blanked)"}.get(h.kind, "the file"),
                "whole": self.whole, "copies": [c.as_dict() for c in self.copies]}


@dataclass
class Scan:
    built: str
    documents: dict[str, dict[str, Any]]
    results: list[HostResult]

    def copies(self) -> list[tuple[Host, Copy]]:
        return [(r.host, c) for r in self.results if not r.whole for c in r.copies]


def target_versions(resolver: DiskResolver, keys: Iterable[str]) -> tuple[list[SectionVersion], dict[str, dict[str, Any]]]:
    versions: list[SectionVersion] = []
    documents: dict[str, dict[str, Any]] = {}
    for key in keys:
        if resolver.living(key) is not None:
            v = resolver.versions(key)
            mine = section_versions(v)
            documents[key] = {"title": v.title, "through": v.now.through, "living": True,
                              "superseded": sum(1 for s in mine if s.version is Version.SUPERSEDED),
                              "pending": sum(1 for s in mine if s.version is Version.PENDING)}
        else:
            outline = resolver.outline(key)
            if outline is None:
                raise SectionRefError(f"{key} has neither a living document nor an outline on disk")
            mine = outline_versions(outline)
            documents[key] = {"title": outline.title, "through": "", "living": False, "superseded": 0, "pending": 0}
        documents[key]["sections"] = len({s.number for s in mine})
        versions += mine
    return versions, documents


def scan(data_dir: Path, community: Any, keys: Iterable[str] = (), *, library: bool = True,
         confidential: bool = False, log=None, host_list: list[Host] | None = None, own_sources: bool = True
         ) -> Scan:
    """Find the copies of the documents ``keys`` (default: every document kept as amended) in every host."""
    resolver = DiskResolver(data_dir, community, log=log)
    keys = list(keys) or [d.key for d in community.living_documents()]
    versions, documents = target_versions(resolver, keys)
    index = Index.build(versions)
    sections = {k: d["sections"] for k, d in documents.items()}
    found_hosts = host_list if host_list is not None else hosts(data_dir, community, keys, library=library,
                                                                confidential=confidential, own_sources=own_sources)
    # A run carried by many documents that are not the document itself is boilerplate the base text also carries (a
    # notary's acknowledgment, a recorder's stamp): it is left out before the copies are read.
    counts: dict[str, int] = defaultdict(int)
    others = [h for h in found_hosts if h.owner is not Owner.SELF]
    for host in others:
        for run in shared_runs(host.text, index):
            counts[run] += 1
    common = {run for run, n in counts.items() if n > max(BOILERPLATE_HOSTS, BOILERPLATE_SHARE * len(others))}
    if common:
        index = without(index, common)
    for d in documents.values():
        d["boilerplateRuns"] = len(common)
    results = []
    for host in found_hosts:
        found = find(host.name, host.text, index)
        if host.paraphrase and host.owner is not Owner.SELF:
            found += paraphrases(host.name, host.text, versions, taken=[(c.start, c.end) for c in found])
        if not found:
            continue
        whole = ""
        for key, n in sections.items():
            hit = {c.number for c in found if c.key == key and c.kind is not CopyKind.PARAPHRASE}
            if len(hit) >= max(15, WHOLE_COPY * n):
                whole = key
        results.append(HostResult(host, sorted(found, key=lambda c: c.start), whole))
    return Scan(date.today().isoformat(), documents, results)


def save(found: Scan, data_dir: Path) -> Path:
    folder = store_dir(data_dir)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "copies.json").write_text(json.dumps({"built": found.built, "documents": found.documents,
                                                    "hosts": [r.as_dict() for r in found.results]}, indent=1),
                                        encoding="utf-8")
    path = folder / "copies.md"
    path.write_text("\n".join(report_lines(found)) + "\n", encoding="utf-8")
    return path


def load_saved(data_dir: Path) -> dict[str, Any] | None:
    path = store_dir(data_dir) / "copies.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None


WHAT_TO_DO = {
    Owner.JASON: "replace the copy with a token (jason section-refs --patch; --apply PATH --yes)",
    Owner.REFERENCE: "keep the words; correct a stale quote by hand (never a token in reference material)",
    Owner.ADOPTED: "a finding for the document's next revision; a stale copy is a conflict lead (not a Conflict row)",
    Owner.TEMPLATE: "update the template where it lives (report only)",
    Owner.HISTORY: "history as sent: never rewritten",
    Owner.RECORDED: "a recorded instrument or public record: never touched",
    Owner.SELF: "a copy or an instrument of the document itself",
}


def _copy_line(c: Copy) -> str:
    stale = f" STALE (reads as {c.matched})" if c.currency is Currency.STALE else \
        f" reads as a draft ({c.matched})" if c.currency is Currency.DRAFT else ""
    twins = f" (the same words as {', '.join(c.also)})" if c.also else ""
    return (f"  - {c.target}{twins} {c.kind.value}, {c.currency.value}{stale}: coverage {c.coverage:.2f}, "
            f"fidelity {c.fidelity:.2f}, {c.words} words at {c.start}-{c.end}: \"{c.excerpt}...\"")


def report_lines(found: Scan) -> list[str]:
    out = [f"# Copies of the governing documents' sections", "",
           f"Built {found.built} by `jason section-refs --scan`. A copy is a lead to read beside the section: it is "
           "found by shared runs of words, and a paraphrase by shared rare words. " + CAVEAT, ""]
    for key, d in found.documents.items():
        out.append(f"- {key}: {d['title']}; {d['sections']} sections" + (f"; through {d['through']}" if d["through"] else "")
                   + (f"; {d['superseded']} superseded and {d['pending']} draft versions looked for" if d["living"] else ""))
    out.append("")
    wholes = [r for r in found.results if r.whole]
    if wholes:
        out += ["## Whole copies", ""]
        for r in wholes:
            stale = [c.number for c in r.copies if c.currency is Currency.STALE]
            draft = [c.number for c in r.copies if c.currency is Currency.DRAFT]
            out.append(f"- {r.host.name} ({r.host.owner.value}): a copy of {r.whole}, {len({c.number for c in r.copies})} "
                       f"sections" + (f"; reads as superseded words in {', '.join(stale)}" if stale else "")
                       + (f"; reads as a draft's words in {', '.join(draft)}" if draft else "")
                       + (f"; also {', '.join(r.host.also)}" if r.host.also else ""))
        out.append("")
    by_owner: dict[Owner, list[HostResult]] = defaultdict(list)
    for r in found.results:
        if not r.whole:
            by_owner[r.host.owner].append(r)
    for owner in Owner:
        rows = by_owner.get(owner)
        if not rows:
            continue
        out += [f"## {owner.value.capitalize()}", "", f"What to do: {WHAT_TO_DO[owner]}.", ""]
        for r in rows:
            out.append(f"- {r.host.name}" + (f" (also {', '.join(r.host.also)})" if r.host.also else ""))
            out += [_copy_line(c) for c in r.copies]
        out.append("")
    stale = [(h, c) for h, c in found.copies() if c.currency is Currency.STALE and h.owner is not Owner.SELF]
    if stale:
        out += ["## Stale copies", ""] + [f"- {h.name} ({h.owner.value}): {c.target} reads as {c.matched}"
                                          for h, c in stale] + [""]
    return out


# --- Proposals: a token in place of a whole-section copy in jason's own source -----------------------------------------

@dataclass
class Proposal:
    path: str
    copy: Copy
    old: str
    new: str
    token: str

    def diff(self) -> str:
        a = Path(self.path).read_text(encoding="utf-8")
        return "".join(difflib.unified_diff(a.splitlines(True), self.new.splitlines(True), fromfile=self.path,
                                            tofile=self.path + " (proposed)", n=2))


_QUOTE_MARKS = "\"'“”‘’"


_OPEN = re.compile(r"(?:<(?:em|i|q|blockquote)\b[^>]*>\s*)?[\"“]")
_CLOSE = re.compile(r"[\"”](?:\s*</(?:em|i|q|blockquote)>)?")


def _widen(text: str, start: int, end: int) -> tuple[int, int, bool]:
    """The span to replace: the copy with its quotation marks (and an ``<em>`` around them), or its lines when the
    copy is all they hold (a block quote's markers, a list bullet). A copy that opens a quotation within its first
    words starts there: the words before it are the host's lead-in (a caption the section also carries). Returns the
    span and whether it is whole lines."""
    head = text[start:min(end, start + 160)]
    opened = list(_OPEN.finditer(head))
    if opened:
        start += opened[0].start()
    else:
        back = text[max(0, start - 12):start]
        if m := re.search(r"(?:<(?:em|i|q)\b[^>]*>\s*)?[\"“]\s*$", back):
            start -= len(back) - m.start()
    tail = text[end:end + 16]
    if m := re.match(r"\s*[.,;]?" + _CLOSE.pattern, tail):
        end += m.end()
    while start > 0 and text[start - 1] in _QUOTE_MARKS:
        start -= 1
    line_start = text.rfind("\n", 0, start) + 1
    line_end = text.find("\n", end)
    line_end = len(text) if line_end < 0 else line_end
    head, tail = text[line_start:start], text[end:line_end]
    if re.fullmatch(r"[ \t>*_-]*", head) and re.fullmatch(r"[ \t*_.]*", tail):
        return line_start, line_end, True
    return start, end, False


def proposals(found: Scan) -> list[Proposal]:
    """A token for each whole-section copy (verbatim or near-verbatim, current or stale) in jason's own sources. An
    excerpt is not replaced: a quote of the whole section would say more than the copy did."""
    by_path: dict[str, list[Copy]] = defaultdict(list)
    for r in found.results:
        if r.host.owner not in TOKENIZABLE or r.whole:
            continue
        for c in r.copies:
            if c.kind in (CopyKind.VERBATIM, CopyKind.NEAR_VERBATIM) and c.coverage >= 0.85 \
                    and c.currency is not Currency.DRAFT and not c.also:
                by_path[r.host.path].append(c)
    out = []
    for path, copies in by_path.items():
        text = Path(path).read_text(encoding="utf-8")
        new = text
        for c in sorted(copies, key=lambda c: c.start, reverse=True):
            start, end, lines = _widen(new, c.start, c.end)
            token = "{" + f"QUOTE:{c.target}" + "}"
            new = new[:start] + token + new[end:]
        out.append(Proposal(path, copies[0], text, new, ", ".join(c.target for c in copies)))
    return out


def apply(proposal: Proposal, *, keep: bool = True) -> Path:
    """Write a proposal to its file (a jason source a person named), keeping the old text as ``.bak``."""
    path = Path(proposal.path)
    if path.read_text(encoding="utf-8") != proposal.old:
        raise ValueError(f"{path} changed since the scan: scan again")
    if keep:
        path.with_suffix(path.suffix + ".bak").write_text(proposal.old, encoding="utf-8")
    path.write_text(proposal.new, encoding="utf-8")
    return path


# --- The guide ----------------------------------------------------------------------------------------------------------

EXCERPT_WORDS = 40


def _excerpt(text: str, words: int = EXCERPT_WORDS) -> str:
    flat = re.sub(r"\s+", " ", text or "").strip()
    parts = flat.split(" ")
    return flat if len(parts) <= words else " ".join(parts[:words]) + " ..."


def _section_numbers(text: str, key: str, aliases: dict[str, str]) -> set[str]:
    """The section numbers ``text`` (a conflict's provision, "CC&Rs 2.3(d) and 10.5(c)") gives for document ``key``:
    each number after a name of the document, until another document is named."""
    from jason.community.references import alias_pattern

    pattern = alias_pattern(aliases)
    if pattern is None:
        return set()
    out: set[str] = set()
    names = list(pattern.finditer(text))
    for k, m in enumerate(names):
        if aliases.get(m.group("doc").lower()) != key:
            continue
        stop = names[k + 1].start() if k + 1 < len(names) else len(text)
        for n in re.finditer(r"\b\d+(?:\.\d+)+(?:\([a-z0-9]{1,5}\))*|\b[A-Z]-\d+(?:\([a-z0-9]{1,5}\))*", text[m.end():stop]):
            out.add(normalize_number(n.group(0)))
    return out


def _alias_matches(text: str, aliases: dict[str, str]) -> list[re.Match]:
    from jason.community.references import alias_pattern

    pattern = alias_pattern(aliases)
    return list(pattern.finditer(text)) if pattern is not None else []


def _is_article(p: Provision) -> bool:
    """A top-level section the document heads "ARTICLE n"."""
    return bool(_ARTICLE.match(p.caption or "")) or bool(_ARTICLE.match(_first_line(p.body)))


is_article = _is_article


def _within(number: str, listed: Iterable[str]) -> bool:
    return any(number == n or number.startswith(n + "(") or number.startswith(n + ".") for n in listed)


def guide(data_dir: Path, community: Any, keys: Iterable[str] = (), *, saved: dict[str, Any] | None = None,
          log=None) -> list[Path]:
    """Compile the guide to each document (default: every document kept as amended, and every other governing document
    with an outline): ``data/section-refs/guide/KEY.md`` and an index. Regenerated each run; never edit it."""
    data_dir = Path(data_dir)
    resolver = DiskResolver(data_dir, community, log=log)
    keys = list(keys) or resolver.keys()
    saved = saved if saved is not None else load_saved(data_dir)
    from jason.tasks.outlines import load_rows

    rows = load_rows(data_dir)
    aliases: dict[str, str] = {}
    for d in community.citable_documents():
        for a in (*d.aliases, d.title, getattr(d, "cite_as", "")):
            if a:
                aliases[a.lower()] = d.key
    copies_of: dict[str, list[tuple[str, str, dict[str, Any]]]] = defaultdict(list)
    if saved:
        for h in saved.get("hosts") or ():
            if h.get("whole"):
                copies_of[f"{h['whole']}#"].append((h["host"], h["owner"], {}))
                continue
            for c in h.get("copies") or ():
                for number in [c["number"], *(c.get("also") or ())]:
                    copies_of[f"{c['key']}#{number}"].append((h["host"], h["owner"], c))
    folder = store_dir(data_dir) / "guide"
    folder.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    index = ["# Guide to the governing documents", "",
             f"Compiled {date.today().isoformat()} by `jason section-refs --guide` from the documents on disk. "
             "Generated: never edit it; run the command again. It is an index for agents: read the section itself "
             "before relying on it. " + CAVEAT, ""]
    for key in keys:
        try:
            lines, summary = _guide_lines(resolver, key, rows, aliases, copies_of, community, data_dir, saved)
        except SectionRefError as exc:
            index.append(f"- {key}: not compiled ({exc})")
            continue
        path = folder / f"{key}.md"
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        written.append(path)
        index.append(f"- [{key}]({key}.md): {summary}")
    (folder / "README.md").write_text("\n".join(index) + "\n", encoding="utf-8")
    return [folder / "README.md", *written]


def _guide_lines(resolver: DiskResolver, key: str, rows: list[dict[str, Any]], aliases: dict[str, str],
                 copies_of: dict[str, list], community: Any, data_dir: Path, saved: dict[str, Any] | None
                 ) -> tuple[list[str], str]:
    doc, versions = resolver._document(key, None)
    name = resolver.name(key)
    living = versions is not None
    sources = [f"the living document ({versions.base}; through {versions.now.through or 'no amendment'})"] if living \
        else [f"the outline data/outlines/{key}.json ({doc.base})"]
    sources += ["data/outlines/references.json"] + (["data/section-refs/copies.json (" + saved["built"] + ")"]
                                                    if saved else ["no copies scan yet (jason section-refs --scan)"])
    conflicts = [(c, _section_numbers(c.provision, key, aliases)) for c in community.conflicts()]
    notices = [n for n in community.notice_provisions() if n.document == key]
    duties = _duty_counts(data_dir, key)
    statutes: dict[str, list[str]] = defaultdict(list)
    cited: dict[str, list[str]] = defaultdict(list)
    for r in rows:
        if r.get("source") == key and r.get("kind") == "statute" and r.get("source_section"):
            statutes[normalize_number(r["source_section"])].append(r["target"])
        if r.get("kind") == "section" and str(r.get("target", "")).startswith(key + "#") and r.get("source") != key:
            cited[normalize_number(r["target"].split("#", 1)[1])].append(f"{r['source']} {r.get('source_section') or ''}".strip())
    lines = [f"# {doc.title}: guide", "",
             f"Compiled {date.today().isoformat()} by `jason section-refs --guide KEY`; generated, never edited. "
             f"Sources: {'; '.join(sources)}. " + CAVEAT, "",
             f"Cite a section as `{{CITE:{key}#N}}` and quote it as `{{QUOTE:{key}#N}}` in a document jason renders "
             f"(never in reference material). Read a whole section with `jason section-refs --show {key}#N`"
             + (f" or the governance tool `living_document(key=\"{key}\", section=N)`." if living else "."), ""]
    if not any(p.number for p in doc.provisions):
        raise SectionRefError("no numbered sections in its outline")
    if living:
        lines += ["A section marked **Amended** has an amendment's words; every other section reads as the base text.", ""]
    if living and versions.pending:
        drafts = sorted({p["instrument"] for p in versions.pending})
        lines += [f"Not in effect: {', '.join((versions.instruments.get(d) or {}).get('describe', d) for d in drafts)}: "
                  + ", ".join(sorted({p['section'] for p in versions.pending})) + ".", ""]
    whole = copies_of.get(f"{key}#") or []
    if whole:
        lines += ["Whole copies: " + "; ".join(f"{h} ({o})" for h, o, _ in whole) + ".", ""]
    general = [c for c, nums in conflicts if not nums and c.provision and
               any(aliases.get(m.group("doc").lower()) == key for m in _alias_matches(c.provision, aliases))]
    if general:
        lines += ["Conflict rows on the document as a whole: " + ", ".join(f"{c.key} ({c.authority})" for c in general)
                  + ".", ""]
    amended = 0
    for p in doc.provisions:
        if not p.number or (not p.body.strip() and not p.caption):
            continue
        cite = citation_of(name, p.number, article=_is_article(p))
        head = f"{'#' * min(6, 1 + max(1, p.depth))} {cite}" + (f": {p.caption.rstrip('.')}" if p.caption else "")
        lines.append(head)
        lines.append("")
        if p.removed:
            lines += [f"Removed by {p.set_by}" + (f" ({p.dated.isoformat()})" if p.dated else "") + ".", ""]
            continue
        if p.body.strip():
            lines += [f"> {_excerpt(p.body)}", ""]
        facts = []
        if p.standing is not None:
            amended += 1
            info = (versions.instruments.get(p.set_by) if living else None) or {}
            facts.append(f"**Amended**: set by {info.get('describe') or p.set_by}"
                         + (f"; the earlier words: `jason section-refs --show {key}#{p.number} --as-of "
                            f"{(p.dated - timedelta(days=1)).isoformat()}`" if p.dated else ""))
        if statutes.get(p.number):
            facts.append("cites " + ", ".join(dict.fromkeys(statutes[p.number])))
        if cited.get(p.number):
            facts.append("cited by " + ", ".join(dict.fromkeys(cited[p.number]))[:300])
        mine = [c for c, nums in conflicts if p.number in nums or any(_within(p.number, [n]) for n in nums)]
        if mine:
            facts.append("conflict rows: " + ", ".join(f"{c.key} ({c.authority})" for c in mine))
        notes = [n for n in notices if _within(p.number, [normalize_number(s) for s in re.split(r",\s*", n.section)])]
        if notes:
            facts.append("notice clauses: " + ", ".join(n.key for n in notes))
        if duties.get(p.number):
            n = duties[p.number]
            facts.append(f"{n} {'duty' if n == 1 else 'duties'} read (jason document-duties)")
        found = copies_of.get(f"{key}#{p.number}") or []
        if found:
            facts.append("copied in " + "; ".join(
                f"{h} ({o}; {c['kind']}, {c['currency']})" for h, o, c in found[:8])
                + (f"; and {len(found) - 8} more" if len(found) > 8 else ""))
        if facts:
            lines += ["- " + "\n- ".join(facts), ""]
    summary = f"{name}, {sum(1 for p in doc.provisions if p.number)} sections" + (f", {amended} amended" if living else "")
    return lines, summary


def _duty_counts(data_dir: Path, key: str) -> dict[str, int]:
    path = Path(data_dir) / "duties" / f"{key}.json"
    if not path.is_file():
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    counts: dict[str, int] = defaultdict(int)
    for d in raw.get("duties") or ():
        if d.get("section"):
            counts[normalize_number(d["section"])] += 1
    return counts


# --- The read-only view the governance tools can serve -------------------------------------------------------------------

def embedded_copies(data_dir: Path | None = None, key: str = "", host: str = "", stale_only: bool = False,
                    owner: str = "") -> dict[str, Any]:
    """The last scan's copies of governing-document sections in other documents (``jason section-refs --scan``),
    read from disk: each host with who owns it and what may be done, and each copy's section, kind, coverage, and
    whether it reads as the current words or superseded ones. ``key`` narrows to a document, ``host`` to hosts whose
    name contains it, ``owner`` to one owner (jason's source, agent reference, adopted document, vendor template,
    sent, recorded), ``stale_only`` to stale copies. A copy is a lead to read beside the section."""
    saved = load_saved(Path(data_dir) if data_dir is not None else default_data_dir())
    if saved is None:
        return {"error": "no scan yet: run jason section-refs --scan"}
    out = []
    for h in saved.get("hosts") or ():
        if host and host.lower() not in h["host"].lower():
            continue
        if owner and h["owner"] != owner:
            continue
        if stale_only and not owner and h["owner"] == Owner.SELF.value:
            continue                               # an instrument shows the words it replaced; a copy of it is no lead
        copies = [c for c in h.get("copies") or () if (not key or c["key"] == key)
                  and (not stale_only or c["currency"] == Currency.STALE.value)]
        if not copies:
            continue
        what = next((WHAT_TO_DO[o] for o in Owner if o.value == h["owner"]), "")
        out.append({"host": h["host"], "owner": h["owner"], "whatToDo": what, "wholeCopyOf": h.get("whole") or "",
                    "also": h.get("also") or [],
                    "copies": [{k: c[k] for k in ("target", "kind", "currency", "matched", "coverage", "fidelity",
                                                  "words", "excerpt")} for c in copies[:50]]})
    return {"built": saved.get("built"), "documents": saved.get("documents"), "hosts": out,
            "caveat": "A copy is found by shared words: a lead to read beside the section, not a finding. " + CAVEAT}


__all__ = ["DiskResolver", "Host", "HostResult", "Owner", "Proposal", "Scan", "Versions", "WHAT_TO_DO", "apply",
           "build_versions", "embedded_copies", "fill_html", "fill_markdown", "guide", "hosts", "load_saved",
           "outline_versions", "proposals", "record_lines", "report_lines", "save", "scan", "section_versions"]
