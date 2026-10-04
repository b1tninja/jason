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
import sqlite3
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence

from jason.community import retrieval
from jason.community.passages import Hit, Passage

INDEX_FILE = "index.db"
SCHEMA_VERSION = 1


class Standing(Enum):
    """How far a passage's words can be relied on (docs/applicability.md). The order of authority within the law and
    the governing documents is ``authority_order.Tier``; this is the coarser shelf."""

    AUTHORITY = "authority"          # the law: statutes, regulations, and the agencies' publications
    RECORD = "record"                # the association's governing documents and records, quoted as the record
    REFERENCE = "reference"          # learned from, never quoted as binding
    PAGE = "page"                    # a page jason wrote from its stores: a summary, never quoted as the rule


@dataclass(frozen=True)
class IndexSource:
    """A folder under the data directory whose text files go into the index, with what they are."""

    catalog: str
    folder: str
    standing: Standing
    suffixes: tuple[str, ...] = (".md", ".txt")
    exclude: tuple[str, ...] = ()     # file-name patterns left out ("*.pdf.md", a publication's title note)
    confidential: bool = False
    generated: bool = False

    def files(self, data_dir: Path) -> list[Path]:
        root = data_dir / self.folder
        if not root.is_dir():
            return []
        return [p for p in sorted(root.rglob("*")) if p.is_file() and p.suffix.lower() in self.suffixes
                and not any(fnmatch.fnmatch(p.name, pattern) for pattern in self.exclude)]


# The text jason holds for the governing documents, the policies' pages, the reserve studies, and the law. Mail, the
# reports, and the library wait for their confidentiality rows (docs/rag-roadmap.md, items 1 and 2) before they join.
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
    IndexSource("authorities", "authorities", Standing.AUTHORITY, exclude=("*.pdf.md",)),
    IndexSource("reference", "reference", Standing.REFERENCE, exclude=("*.pdf.md",)),
)

_DDL = """
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS files (
    path TEXT PRIMARY KEY, catalog TEXT NOT NULL, standing TEXT NOT NULL, kind TEXT NOT NULL DEFAULT '',
    confidential INTEGER NOT NULL DEFAULT 0, generated INTEGER NOT NULL DEFAULT 0,
    sha256 TEXT NOT NULL, chunking TEXT NOT NULL, indexed_at REAL NOT NULL);
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
    db.execute("INSERT OR IGNORE INTO meta VALUES ('schema', ?)", (str(SCHEMA_VERSION),))
    return db


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _rel(path: Path, data_dir: Path) -> str:
    return path.resolve().relative_to(data_dir.resolve()).as_posix()


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


def build(data_dir: Path | str, *, sources: Sequence[IndexSource] = SOURCES, embedder: retrieval.Embedder | None = None,
          model: str = retrieval.EMBED_MODEL, chunking: str = retrieval.CHUNKING,
          kind_of: Callable[[str], str] = _default_kind, batch: int = 64, say: Callable[[str], None] | None = None,
          ) -> BuildReport:
    """Bring the index up to date with ``sources``. Without ``embedder`` the passages are cut and the old cache's
    vectors copied, and the rest are counted as missing. The caller holds the store lock (``Resource.STORE``,
    ``retrieval-index``); the embedder holds the GPU lock per request."""
    from jason.community.passage_sections import OutlineIndex, section_passages
    from jason.community.passages import passages_of

    data_dir = Path(data_dir)
    started = time.monotonic()
    report = BuildReport()
    outlines = OutlineIndex.load(data_dir / "outlines") if chunking == "sections" else None
    db = connect(data_dir)
    try:
        seen: set[str] = set()
        for source in sources:
            for path in source.files(data_dir):
                rel = _rel(path, data_dir)
                if rel in seen:
                    continue
                seen.add(rel)
                report.files += 1
                sha = _sha(path)
                row = db.execute("SELECT sha256, chunking, catalog, standing FROM files WHERE path = ?", (rel,)).fetchone()
                if row and row[0] == sha and row[1] == chunking and row[2] == source.catalog and row[3] == source.standing.value:
                    continue
                cut = section_passages(path, outlines=outlines) if outlines is not None else passages_of(path)
                db.execute("DELETE FROM files WHERE path = ?", (rel,))
                db.execute("INSERT INTO files VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                           (rel, source.catalog, source.standing.value, kind_of(path.name), int(source.confidential),
                            int(source.generated), sha, chunking, time.time()))
                db.executemany("INSERT INTO passages (path, idx, start_word, heading, text, key) VALUES (?, ?, ?, ?, ?, ?)",
                               [(rel, p.index, p.start_word, p.heading, p.text, retrieval.text_key(p.ranked)) for p in cut])
                report.cut += 1
        folders = {s.folder.rstrip("/") + "/" for s in sources}
        for (rel,) in db.execute("SELECT path FROM files").fetchall():
            if rel not in seen and any(rel.startswith(f) for f in folders):
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
        "SELECT p.key, MIN(p.heading), MIN(p.text) FROM passages p LEFT JOIN vectors v ON v.key = p.key AND v.model = ? "
        "WHERE v.key IS NULL GROUP BY p.key", (model,)).fetchall()
    old = retrieval.VectorCache(data_dir / "retrieval" / "vectors", model=model)
    pending: list[tuple[str, str]] = []
    for key, heading, text in wanted:
        vector = old.get(key)
        if vector is not None:
            _put(db, key, model, np.asarray(vector, dtype="float16"))
            report.copied += 1
        else:
            pending.append((key, f"{heading}\n{text}" if heading else text))
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
    files held back unless asked."""

    catalogs: tuple[str, ...] = ()
    standings: tuple[Standing, ...] = ()
    kinds: tuple[str, ...] = ()
    folders: tuple[str, ...] = ()          # path prefixes under the data directory
    confidential: bool = False
    generated: bool | None = None          # None: both; False: only what jason did not write

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
        if not self.confidential:
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
            f"f.confidential, f.generated FROM passages p JOIN files f ON f.path = p.path{where} ORDER BY p.path, p.idx",
            args).fetchall()
        passages: list[Passage] = []
        meta: dict[tuple[str, int], Row] = {}
        for rel, idx, start, heading, text, key, catalog, standing, kind, conf, gen in rows:
            passage = Passage(data_dir / rel, idx, start, text, heading)
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


__all__ = ["BuildReport", "IndexHit", "IndexSource", "Loaded", "Row", "SOURCES", "Scope", "Standing", "StoredEmbedder",
           "build", "connect", "index_path", "load", "search", "status"]
