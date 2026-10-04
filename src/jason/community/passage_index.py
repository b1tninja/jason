"""One search index over the passages jason reads, with columns a search can be scoped by.

``retrieval`` ranks passages (BM25, dense, the exact-token boost, near copies folded), but it cuts its corpus from
folders at every call and keeps one vector file per passage, so a search cannot be scoped by what a document is.
This module keeps the passages in one SQLite file (``data/retrieval/index.db``) with columns:

- **catalog** and **standing**: where a passage comes from and how far its words can be relied on (``Standing``);
- **kind**: the profile's ``DocumentKind`` for the file, by its kind rules (a miss is empty);
- **confidential** and **generated**: whether the file is held back unless asked, and whether jason wrote it.

Its vectors sit beside the passages, keyed by the text they embed, so two copies of a passage share one.

- ``build`` takes ``SOURCES`` (or any rows given) and re-cuts only the files whose bytes changed. It drops the files
  that are gone, and embeds only the text no vector exists for. A vector the old per-passage cache already holds
  (``retrieval.VectorCache``) is copied, not embedded again.
- ``search`` selects the rows a scope allows, then ranks them with ``retrieval``'s own functions. With no scope it
  ranks the same passages the folders would give, so the measured recall holds (``scripts/eval_retrieval.py --index``).

It is search, not extraction: a hit is a passage to read, and nothing here pins a fact. The index is a derived store
under ``data/``; deleting it loses nothing that ``build`` cannot make again. See docs/applicability.md.
"""

from __future__ import annotations

import fnmatch
import hashlib
import re
import sqlite3
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence

from jason.community import retrieval
from jason.community.passages import Hit, Passage

INDEX_FILE = "index.db"
SCHEMA_VERSION = 2            # 2: files.context (a file's context line, read by the rankers)
_BULLET = re.compile(r"^- ([A-Z][^:]{1,40}): (.*)$")


class Standing(Enum):
    """How far a passage's words can be relied on (docs/applicability.md). The order of authority within the law and
    the governing documents is ``authority_order.Tier``; this is the coarser shelf."""

    AUTHORITY = "authority"          # the law: statutes, regulations, and the agencies' publications
    RECORD = "record"                # the association's governing documents and records, quoted as the record
    REFERENCE = "reference"          # learned from, never quoted as binding
    PAGE = "page"                    # a page jason wrote from its stores: a summary, never quoted as the rule
    EVIDENCE = "evidence"            # gathered for one matter (a legal case's file): neither the record nor the law


@dataclass(frozen=True)
class IndexFile:
    """One text file for the index, with what it is. A source gives these (``entries``); a source whose files differ
    one from another (a library where some files are confidential) gives each file its own flags."""

    path: Path                        # absolute
    catalog: str
    standing: Standing
    kind: str | None = None           # None: the active profile's kind rules, by the file's name
    confidential: bool = False
    generated: bool = False
    context: str = ""                 # where the file sits, in a line; the rankers read it before each passage
    front_matter: bool = False        # leave out a passage that is only a title and "- Label: value" lines


def front_matter_labels(path: Path) -> dict[str, list[str]]:
    """The "- Label: value" lines under a page's title, before its first section: the page's own description of itself."""
    out: dict[str, list[str]] = {}
    try:
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()[:60]
    except OSError:
        return out
    for line in lines:
        if line.startswith("## "):
            break
        m = _BULLET.match(line.strip())
        if m:
            out.setdefault(m.group(1), []).append(m.group(2))
    return out


def is_front_matter(text: str) -> bool:
    """A passage that is only headings and "- Label: value" lines: a page's description, with none of its words."""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return bool(lines) and all(line.startswith("#") or _BULLET.match(line) for line in lines)


@dataclass(frozen=True)
class IndexSource:
    """A folder under the data directory whose text files go into the index, with what they are."""

    catalog: str
    folder: str
    standing: Standing
    suffixes: tuple[str, ...] = (".md", ".txt")
    # Patterns left out, matched on the file's name or its path under the folder ("*.pdf.md", a publication's title
    # note; "publications/*", a subfolder another source gives).
    exclude: tuple[str, ...] = ()
    confidential: bool = False
    generated: bool = False
    front_matter: bool = False        # the pages open with a title and "- Label: value" lines: leave that passage out
    context_of: Callable[[Path], str] | None = None      # a file's context line (``IndexFile.context``)

    @property
    def catalogs(self) -> tuple[str, ...]:
        return (self.catalog,)

    def files(self, data_dir: Path) -> list[Path]:
        root = data_dir / self.folder
        if not root.is_dir():
            return []
        return [p for p in sorted(root.rglob("*")) if p.is_file() and p.suffix.lower() in self.suffixes
                and not any(fnmatch.fnmatch(p.name, pattern) or fnmatch.fnmatch(p.relative_to(root).as_posix(), pattern)
                            for pattern in self.exclude)]

    def entries(self, data_dir: Path) -> Iterable[IndexFile]:
        for path in self.files(data_dir):
            yield IndexFile(path, self.catalog, self.standing, confidential=self.confidential, generated=self.generated,
                            context=self.context_of(path) if self.context_of else "", front_matter=self.front_matter)


# The text jason holds for the governing documents, the policies' pages, the reserve studies, and the law. The mail,
# the reports, the library, and jason's documentation are ``jason.tasks.index_sources``: each of their files gets its
# own flags, so they are not folders here.
SOURCES: tuple[IndexSource, ...] = (
    IndexSource("records", "artifacts/site-docs/governing_documents", Standing.RECORD),
    IndexSource("records", "artifacts/site-docs/governing_documents_Annexations", Standing.RECORD),
    IndexSource("records", "artifacts/site-docs/governing_documents_Policies", Standing.RECORD),
    IndexSource("records", "artifacts/site-docs/governing_documents_Resolutions", Standing.RECORD),
    IndexSource("records", "artifacts/site-docs/dre_reports", Standing.RECORD),
    IndexSource("records", "governing", Standing.RECORD),
    IndexSource("records", "reserve-studies", Standing.RECORD),
    IndexSource("insurance", "artifacts/site-docs/insurance", Standing.RECORD),
    IndexSource("insurance", "insurance/pages", Standing.PAGE, generated=True),
    # A law page opens with its title and "- Label: value" lines (source, path, why it is held). That passage carries
    # the topic's words and none of the law's, so it is left out: measured October 4, 2026 on the law's gold questions
    # over the whole index, hybrid MRR@10 0.71 to 0.75 with recall unchanged, and no change on the other gold sets.
    # A context line on each passage (the chapter path, why it is held, the standing) was measured too and gained
    # nothing clear, so the law's passages carry none (docs/document-tools.md, model trials).
    IndexSource("authorities", "authorities", Standing.AUTHORITY, exclude=("publications/*",), front_matter=True),
    IndexSource("reference", "reference", Standing.REFERENCE, exclude=("*.pdf.md",)),
)

_DDL = """
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS files (
    path TEXT PRIMARY KEY, catalog TEXT NOT NULL, standing TEXT NOT NULL, kind TEXT NOT NULL DEFAULT '',
    confidential INTEGER NOT NULL DEFAULT 0, generated INTEGER NOT NULL DEFAULT 0,
    sha256 TEXT NOT NULL, chunking TEXT NOT NULL, indexed_at REAL NOT NULL, context TEXT NOT NULL DEFAULT '');
CREATE TABLE IF NOT EXISTS passages (
    id INTEGER PRIMARY KEY, path TEXT NOT NULL REFERENCES files(path) ON DELETE CASCADE, idx INTEGER NOT NULL,
    start_word INTEGER NOT NULL, heading TEXT NOT NULL, text TEXT NOT NULL, key TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS passages_path ON passages(path);
CREATE INDEX IF NOT EXISTS passages_key ON passages(key);
CREATE TABLE IF NOT EXISTS vectors (key TEXT NOT NULL, model TEXT NOT NULL, dim INTEGER NOT NULL, vec BLOB NOT NULL,
    PRIMARY KEY (key, model));
"""


def index_path(data_dir: Path | str) -> Path:
    return Path(data_dir) / "retrieval" / INDEX_FILE


def connect(data_dir: Path | str) -> sqlite3.Connection:
    path = index_path(data_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path)
    db.execute("PRAGMA foreign_keys = ON")
    db.executescript(_DDL)
    if "context" not in {row[1] for row in db.execute("PRAGMA table_info(files)")}:      # an index built at schema 1
        db.execute("ALTER TABLE files ADD COLUMN context TEXT NOT NULL DEFAULT ''")
    db.execute("INSERT OR REPLACE INTO meta VALUES ('schema', ?)", (str(SCHEMA_VERSION),))
    return db


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _rel(path: Path, data_dir: Path) -> str:
    """How the index names a file: its path under the data directory. A file outside it (jason's own documentation, in
    the project checkout) is named by its absolute path, which ``data_dir / name`` gives back unchanged, so ``load``
    reads both the same way. A folder scope (``Scope.folders``) is a place under the data directory and never matches
    one."""
    resolved = path.resolve()
    try:
        return resolved.relative_to(data_dir.resolve()).as_posix()
    except ValueError:
        return resolved.as_posix()


def _default_kind(name: str) -> str:
    """The active profile's kind for a file name, or empty: a miss stays a miss."""
    try:
        from jason.community import community

        kind = community().classify_document(name)
    except Exception:
        return ""
    return str(getattr(kind, "value", kind) or "")


@dataclass
class BuildReport:
    files: int = 0
    cut: int = 0                      # files (re)cut because their bytes changed or they were new
    removed: int = 0
    passages: int = 0
    copied: int = 0                   # vectors taken from the old per-passage cache
    embedded: int = 0                 # vectors Ollama made in this build
    missing: int = 0                  # passages still without a vector (no embedder, or it failed)
    seconds: float = 0.0
    notes: list[str] = field(default_factory=list)

    def lines(self) -> list[str]:
        return [f"files {self.files} (cut {self.cut}, removed {self.removed}); passages {self.passages}",
                f"vectors: copied {self.copied}, embedded {self.embedded}, missing {self.missing}; {self.seconds:.1f} s",
                *self.notes]


def build(data_dir: Path | str, *, sources: Sequence[Any] = SOURCES, embedder: retrieval.Embedder | None = None,
          model: str = retrieval.EMBED_MODEL, chunking: str = retrieval.CHUNKING,
          kind_of: Callable[[str], str] = _default_kind, batch: int = 64, say: Callable[[str], None] | None = None,
          held: Callable[[Path], bool] | None = None) -> BuildReport:
    """Bring the index up to date with ``sources``: each gives its files (``entries(data_dir)``, as ``IndexFile``) and
    names the catalogs it fills (``catalogs``), so a file it no longer gives leaves the index. Without ``embedder`` the passages are cut and the old cache's
    vectors copied, and the rest are counted as missing. ``held`` is asked of every file and can only add the
    confidential flag: a file one source gives openly is still held back when another store holds the same file as
    confidential. The caller holds the store lock (``Resource.STORE``, ``retrieval-index``); the embedder holds the GPU
    lock per request."""
    from jason.community.passage_sections import OutlineIndex, section_passages
    from jason.community.passages import passages_of

    data_dir = Path(data_dir)
    started = time.monotonic()
    report = BuildReport()
    outlines = OutlineIndex.load(data_dir / "outlines") if chunking == "sections" else None
    db = connect(data_dir)
    try:
        seen: set[str] = set()
        claimed: set[str] = set()
        for source in sources:
            claimed.update(source.catalogs)
            for entry in source.entries(data_dir):
                path = entry.path
                rel = _rel(path, data_dir)
                if rel in seen:
                    continue
                seen.add(rel)
                report.files += 1
                sha = _sha(path)
                cutting = f"{chunking}+front" if entry.front_matter else chunking
                kind = kind_of(path.name) if entry.kind is None else entry.kind
                confidential = int(bool(entry.confidential or (held is not None and held(path))))
                row = db.execute("SELECT sha256, chunking, catalog, standing, context, kind, confidential, generated "
                                 "FROM files WHERE path = ?", (rel,)).fetchone()
                if row and row[:5] == (sha, cutting, entry.catalog, entry.standing.value, entry.context):
                    if row[5:] != (kind, confidential, int(entry.generated)):       # a flag moved: no re-cut
                        db.execute("UPDATE files SET kind = ?, confidential = ?, generated = ? WHERE path = ?",
                                   (kind, confidential, int(entry.generated), rel))
                    continue
                cut = section_passages(path, outlines=outlines) if outlines is not None else passages_of(path)
                if entry.front_matter:
                    cut = tuple(p for p in cut if not is_front_matter(p.text))
                db.execute("DELETE FROM files WHERE path = ?", (rel,))
                db.execute("INSERT INTO files (path, catalog, standing, kind, confidential, generated, sha256, chunking, "
                           "indexed_at, context) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                           (rel, entry.catalog, entry.standing.value, kind, confidential, int(entry.generated),
                            sha, cutting, time.time(), entry.context))
                db.executemany(
                    "INSERT INTO passages (path, idx, start_word, heading, text, key) VALUES (?, ?, ?, ?, ?, ?)",
                    [(rel, p.index, p.start_word, p.heading, p.text,
                      retrieval.text_key(Passage(p.path, p.index, p.start_word, p.text, p.heading, entry.context).ranked))
                     for p in cut])
                report.cut += 1
        # A file the index holds that no source gave this time is gone, when a source in this build claims its catalog.
        for rel, catalog in db.execute("SELECT path, catalog FROM files").fetchall():
            if rel not in seen and catalog in claimed:
                db.execute("DELETE FROM files WHERE path = ?", (rel,))
                report.removed += 1
        db.commit()
        report.passages = db.execute("SELECT COUNT(*) FROM passages").fetchone()[0]
        _fill_vectors(db, data_dir, model, embedder, report, batch=batch, say=say)
    finally:
        db.close()
    report.seconds = time.monotonic() - started
    return report


def _fill_vectors(db: sqlite3.Connection, data_dir: Path, model: str, embedder: retrieval.Embedder | None,
                  report: BuildReport, *, batch: int, say: Callable[[str], None] | None) -> None:
    import numpy as np

    wanted = db.execute(
        "SELECT p.key, MIN(f.context), MIN(p.heading), MIN(p.text) FROM passages p JOIN files f ON f.path = p.path "
        "LEFT JOIN vectors v ON v.key = p.key AND v.model = ? WHERE v.key IS NULL GROUP BY p.key", (model,)).fetchall()
    old = retrieval.VectorCache(data_dir / "retrieval" / "vectors", model=model)
    pending: list[tuple[str, str]] = []
    for key, context, heading, text in wanted:
        vector = old.get(key)
        if vector is not None:
            _put(db, key, model, np.asarray(vector, dtype="float16"))
            report.copied += 1
        else:
            pending.append((key, "\n".join(part for part in (context, heading, text) if part)))
    db.commit()
    if pending and embedder is None:
        report.missing = len(pending)
        report.notes.append(f"{len(pending)} passages have no vector: build again with the embedder")
        return
    for start in range(0, len(pending), batch):
        chunk = pending[start: start + batch]
        try:
            vectors = embedder.embed_passages([text for _, text in chunk])
        except retrieval.EmbeddingUnavailable as exc:
            report.missing += len(pending) - start
            report.notes.append(f"embedding stopped: {exc}")
            break
        for (key, _), vector in zip(chunk, vectors):
            if vector:
                _put(db, key, model, np.asarray(vector, dtype="float16"))
                report.embedded += 1
            else:
                report.missing += 1
        db.commit()
        if say:
            say(f"embedded {min(start + batch, len(pending))} of {len(pending)}")


def _put(db: sqlite3.Connection, key: str, model: str, vector: Any) -> None:
    db.execute("INSERT OR REPLACE INTO vectors VALUES (?, ?, ?, ?)", (key, model, int(vector.shape[0]), vector.tobytes()))


# --- search ---------------------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Scope:
    """Which rows a search may rank. Every field empty means every row a person may see; ``confidential`` adds the
    files held back unless asked. ``confidential_in`` adds them for the catalogs it names and no other: a confidential
    catalog asked for by name (a legal case's) opens its own files, not another catalog's."""

    catalogs: tuple[str, ...] = ()
    standings: tuple[Standing, ...] = ()
    kinds: tuple[str, ...] = ()
    folders: tuple[str, ...] = ()          # path prefixes under the data directory
    confidential: bool = False
    generated: bool | None = None          # None: both; False: only what jason did not write
    confidential_in: tuple[str, ...] = ()

    def where(self) -> tuple[str, list[Any]]:
        clauses: list[str] = []
        args: list[Any] = []

        def any_of(column: str, values: Iterable[Any]) -> None:
            values = list(values)
            if values:
                clauses.append(f"f.{column} IN ({', '.join('?' * len(values))})")
                args.extend(values)

        any_of("catalog", self.catalogs)
        any_of("standing", [s.value for s in self.standings])
        any_of("kind", self.kinds)
        if self.folders:
            clauses.append("(" + " OR ".join("f.path LIKE ? ESCAPE '\\'" for _ in self.folders) + ")")
            args.extend(_like_prefix(f) for f in self.folders)
        if not self.confidential and self.confidential_in:
            clauses.append(f"(f.confidential = 0 OR f.catalog IN ({', '.join('?' * len(self.confidential_in))}))")
            args.extend(self.confidential_in)
        elif not self.confidential:
            clauses.append("f.confidential = 0")
        if self.generated is not None:
            clauses.append("f.generated = ?")
            args.append(int(self.generated))
        return (" WHERE " + " AND ".join(clauses)) if clauses else "", args


def _like_prefix(folder: str) -> str:
    folder = folder.strip("/").replace("\\", "/")
    return folder.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "/%"


@dataclass(frozen=True)
class Row:
    """A passage's columns, beside the ``Passage`` the rankers read."""

    catalog: str
    standing: Standing
    kind: str
    confidential: bool
    generated: bool
    key: str


@dataclass
class Loaded:
    passages: tuple[Passage, ...]
    rows: dict[tuple[str, int], Row]
    vectors: dict[str, Any]                # text key -> float32 vector


_MEMO: dict[tuple[str, float, Scope, str], Loaded] = {}


def load(data_dir: Path | str, scope: Scope = Scope(), *, model: str = retrieval.EMBED_MODEL,
         vectors: bool = True) -> Loaded:
    """The passages a scope allows, with their rows and (``vectors``) their stored vectors; kept in memory until the
    index file changes."""
    import numpy as np

    data_dir = Path(data_dir)
    path = index_path(data_dir)
    if not path.is_file():
        raise FileNotFoundError(f"no passage index at {path}: run jason index --build")
    memo_key = (str(path), path.stat().st_mtime, scope, model if vectors else "")
    if memo_key in _MEMO:
        return _MEMO[memo_key]
    db = connect(data_dir)
    try:
        where, args = scope.where()
        rows = db.execute(
            "SELECT p.path, p.idx, p.start_word, p.heading, p.text, p.key, f.catalog, f.standing, f.kind, "
            f"f.confidential, f.generated, f.context FROM passages p JOIN files f ON f.path = p.path{where} ORDER BY p.path, p.idx",
            args).fetchall()
        passages: list[Passage] = []
        meta: dict[tuple[str, int], Row] = {}
        for rel, idx, start, heading, text, key, catalog, standing, kind, conf, gen, context in rows:
            # ``rel`` is under the data directory, or absolute for a file outside it (``_rel``); the join keeps either.
            passage = Passage(data_dir / rel, idx, start, text, heading, context)
            passages.append(passage)
            meta[(str(passage.path), idx)] = Row(catalog, Standing(standing), kind, bool(conf), bool(gen), key)
        found: dict[str, Any] = {}
        if vectors and rows:
            keys = sorted({r[5] for r in rows})
            for start in range(0, len(keys), 900):
                part = keys[start: start + 900]
                for key, blob in db.execute(
                        f"SELECT key, vec FROM vectors WHERE model = ? AND key IN ({', '.join('?' * len(part))})",
                        [model, *part]):
                    found[key] = np.frombuffer(blob, dtype="float16").astype("float32")
    finally:
        db.close()
    loaded = Loaded(tuple(passages), meta, found)
    _MEMO.clear()
    _MEMO[memo_key] = loaded
    return loaded


@dataclass
class StoredEmbedder:
    """The ``retrieval.Embedder`` a search over the index uses: passages' vectors from the index, the question's from
    the live embedder. A passage the index has no vector for is embedded live (and counted in ``live``)."""

    stored: dict[str, Any]
    query_embedder: retrieval.Embedder
    live: int = 0

    def embed_passages(self, texts: Sequence[str]) -> list[list[float]]:
        out: list[Any] = []
        missing = [i for i, t in enumerate(texts) if retrieval.text_key(t) not in self.stored]
        fresh = dict(zip(missing, self.query_embedder.embed_passages([texts[i] for i in missing]))) if missing else {}
        self.live += len(missing)
        for i, text in enumerate(texts):
            out.append(fresh[i] if i in fresh else self.stored[retrieval.text_key(text)])
        return out

    def embed_query(self, text: str) -> list[float]:
        return self.query_embedder.embed_query(text)


@dataclass(frozen=True)
class IndexHit:
    hit: Hit
    row: Row


def search(query: str, *, data_dir: Path | str | None = None, scope: Scope = Scope(), k: int = 8, mode: str = "hybrid",
           embedder: retrieval.Embedder | None = None, rerank: bool = False) -> tuple[IndexHit, ...]:
    """The passages a scope allows, ranked as ``retrieval.search`` ranks a folder's: "keyword", "exact", "dense", or
    "hybrid". Each hit carries its row (catalog, standing, kind)."""
    if data_dir is None:
        from jason.config import data_dir as active_data_dir

        data_dir = active_data_dir()
    loaded = load(data_dir, scope, vectors=mode in ("dense", "hybrid"))
    items = loaded.passages
    fold = (lambda hits: retrieval.collapse(hits)[:k]) if retrieval.COLLAPSE_COPIES else (lambda hits: tuple(hits)[:k])
    depth = max(k, retrieval.DENSE_DEPTH) if retrieval.COLLAPSE_COPIES else k
    if mode == "keyword":
        from jason.community.passages import rank

        hits = fold(rank(query, items, k=depth))
    elif mode == "exact":
        hits = retrieval.keyword_exact(query, items, k=k)
    elif mode in ("dense", "hybrid"):
        stored = StoredEmbedder(loaded.vectors, embedder or retrieval.default_embedder(data_dir))
        if mode == "dense":
            hits = fold(retrieval.dense_rank(query, items, stored, k=depth))
        else:
            hits = retrieval.hybrid(query, items, k=k, embedder=stored,
                                    reranker=retrieval.LlmReranker() if rerank else None)
    else:
        raise ValueError(f"unknown retrieval mode {mode!r}: keyword, exact, dense, or hybrid")
    return tuple(IndexHit(h, loaded.rows[(str(h.passage.path), h.passage.index)]) for h in hits)


def catalogs(data_dir: Path | str) -> tuple[str, ...]:
    """The catalogs the index holds, in order; none without an index."""
    if not index_path(data_dir).is_file():
        return ()
    db = connect(data_dir)
    try:
        return tuple(name for (name,) in db.execute("SELECT DISTINCT catalog FROM files ORDER BY 1"))
    finally:
        db.close()


def status(data_dir: Path | str, *, model: str = retrieval.EMBED_MODEL) -> dict[str, Any]:
    """What the index holds: files and passages by catalog and standing, and the passages with no vector."""
    path = index_path(data_dir)
    if not path.is_file():
        return {"index": str(path), "built": False}
    db = connect(data_dir)
    try:
        by = db.execute("SELECT f.catalog, f.standing, COUNT(DISTINCT f.path), COUNT(p.id) FROM files f "
                        "LEFT JOIN passages p ON p.path = f.path GROUP BY f.catalog, f.standing ORDER BY 1, 2").fetchall()
        missing = db.execute("SELECT COUNT(DISTINCT p.key) FROM passages p LEFT JOIN vectors v ON v.key = p.key AND "
                             "v.model = ? WHERE v.key IS NULL", (model,)).fetchone()[0]
        vectors = db.execute("SELECT COUNT(*) FROM vectors WHERE model = ?", (model,)).fetchone()[0]
    finally:
        db.close()
    return {"index": str(path), "built": True, "bytes": path.stat().st_size, "model": model, "vectors": vectors,
            "withoutVector": missing,
            "catalogs": [{"catalog": c, "standing": s, "files": f, "passages": n} for c, s, f, n in by]}


__all__ = ["BuildReport", "IndexFile", "IndexHit", "IndexSource", "Loaded", "Row", "SOURCES", "Scope", "Standing", "StoredEmbedder",
           "build", "catalogs", "connect", "index_path", "load", "search", "status"]
