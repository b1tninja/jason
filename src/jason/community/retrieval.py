"""Hybrid retrieval over the document passages: the keyword ranking, dense embeddings, and exact tokens, fused.

``jason.community.passages`` ranks passages by BM25 over the question's words. That ranker is exact about rare
tokens (a recording number, an APN, a policy number) and blind to paraphrase ("who fixes the garage door" against
"Owner Maintenance Responsibility ... Garage Doors"). The embedder AnythingLLM already uses, ``qwen3-embedding:8b``
on the system Ollama, is the reverse. This module fuses the two:

- ``rrf`` is reciprocal rank fusion: each ranking adds ``1 / (k + rank)`` to an item, so an item near the top of
  either list rises, and no score scale has to agree with another's.
- ``exact_tokens`` picks the tokens a person means literally: a word of five or more characters with a digit in it
  (``202001170712``, ``N030PK2940-01``), an APN (``201-1170-024-0007``), and a statute section named as one
  (``Civil Code 5855``, ``Section 7.4``). A passage that carries them verbatim ranks first, whatever the fusion says.
- ``OllamaEmbedder`` embeds passages through ``/api/embed`` under the GPU lock (``ollama_extractor._post``), at the
  context window the resident embedder was loaded with (read from ``/api/ps``) so Ollama does not reload it, and
  keeps each passage's vector on disk (float16, keyed by the SHA-256 of the text) under ``data/retrieval/vectors``.
  A cold corpus runs ``jason.local_ai.preflight`` first; a warm one sends only the question.
- ``hybrid`` fuses the keyword and dense rankings and applies the exact boost; ``rerank`` optionally asks the
  resident chat model to score the top passages (``LlmReranker``), off by default.

It is search, not extraction: a hit is a passage for a person to read, and nothing here pins a fact.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Hashable, Iterable, Protocol, Sequence

from jason.community.ollama_extractor import DEFAULT_CONTEXT, DEFAULT_MODEL, OLLAMA_URL
from jason.community.passages import Hit, Passage, corpus, rank

EMBED_MODEL = "qwen3-embedding:8b"
RRF_K = 60
DENSE_DEPTH = 50           # how deep each ranking goes into the fusion
# The hybrid's fusion, measured on the gold questions (October 2, 2026; docs/document-tools.md, model trials): a
# small k lets each ranking's first places count, and the dense ranking weighed 1.5 keeps its paraphrase recall
# that equal weights gave up (recall@5 0.75 to 0.88). Tuned on 24 questions: measure again as the gold set grows.
HYBRID_RRF_K = 10
DENSE_WEIGHT = 1.5
# Qwen3-Embedding is trained with an instruction on the query side only; passages are embedded bare.
QUERY_INSTRUCTION = "Instruct: Given a question about a homeowners association's documents, retrieve the passages that answer it\nQuery: "
# How the search cuts passages, and whether it folds near copies (measured October 2, 2026; docs/document-tools.md).
# Section-aware passages raised the held-out hybrid recall@5 from 0.80 to 0.86 (12 won, 5 lost), and folding near
# copies to 0.91 (5 won, none lost); the "nothing relevant" score did not separate (see NO_ANSWER_COSINE).
CHUNKING = "sections"
COLLAPSE_COPIES = True

# --- fusion ---------------------------------------------------------------------------------------------------------


def rrf(rankings: Iterable[Sequence[Hashable]], k: int = RRF_K,
        weights: Sequence[float] | None = None) -> list[tuple[Hashable, float]]:
    """Reciprocal rank fusion: each item scores the sum of ``weight / (k + rank)`` over the rankings it appears in (rank
    from 1; every weight 1 unless given). Highest first; ties keep the order in which items were first seen."""
    scores: dict[Hashable, float] = {}
    for n, ranking in enumerate(rankings):
        weight = weights[n] if weights is not None and n < len(weights) else 1.0
        for position, item in enumerate(ranking, start=1):
            scores[item] = scores.get(item, 0.0) + weight / (k + position)
    order = {item: i for i, item in enumerate(scores)}
    return sorted(scores.items(), key=lambda pair: (-pair[1], order[pair[0]]))


# --- exact tokens ---------------------------------------------------------------------------------------------------

_APN = re.compile(r"\b\d{3}-\d{4}-\d{3}-\d{4}\b")
_SECTION = re.compile(r"(?:civil\s+code|civ\.?(?:\s+code)?|code\s+of\s+civil\s+procedure|ccp|§+|sections?)\s*(\d{1,5}(?:\.\d+)*(?:\([a-z0-9]+\))*)", re.I)
_TOKEN = re.compile(r"[A-Za-z0-9][A-Za-z0-9\-/.]*[A-Za-z0-9]|[A-Za-z0-9]")
_AMOUNT = re.compile(r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+\.\d{2}")


def exact_tokens(query: str) -> tuple[str, ...]:
    """The tokens of ``query`` a passage should carry verbatim: APNs, statute sections named as such, and any word of
    five or more characters with a digit in it (recording, policy, claim, and account numbers). Amounts ("$10,000")
    are left to the rankers: a figure recurs across unrelated passages."""
    found: list[str] = []

    def add(token: str) -> None:
        token = token.strip(".-/")
        if token and token.upper() not in {t.upper() for t in found}:
            found.append(token)

    for m in _APN.finditer(query):
        add(m.group(0))
    for m in _SECTION.finditer(query):
        add(m.group(1))
    for m in _TOKEN.finditer(query):
        word = m.group(0)
        if len(word) >= 5 and any(c.isdigit() for c in word) and not _AMOUNT.fullmatch(word):
            add(word)
    return tuple(found)


def _compact(text: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", text.upper())


def carries(token: str, text: str) -> bool:
    """Whether ``text`` has ``token`` as a whole token (not inside a longer number); a token with separators also
    matches its compact form (``201-1170-024-0007`` against ``20111700240007``)."""
    if re.search(r"(?<![A-Za-z0-9])" + re.escape(token) + r"(?![A-Za-z0-9])", text, re.I):
        return True
    compact = _compact(token)
    if compact != token.upper() and len(compact) >= 8:
        return re.search(r"(?<![0-9])" + re.escape(compact) + r"(?![0-9])", text.upper()) is not None
    return False


def exact_count(tokens: Sequence[str], text: str) -> int:
    return sum(1 for token in tokens if carries(token, text))


# --- dense ----------------------------------------------------------------------------------------------------------


class Embedder(Protocol):
    def embed_passages(self, texts: Sequence[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


def text_key(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _normalize(vector: Sequence[float]) -> list[float]:
    norm = math.sqrt(sum(v * v for v in vector)) or 1.0
    return [v / norm for v in vector]


def _slug(model: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", model)


@dataclass
class VectorCache:
    """Passage vectors on disk, one float16 ``.npy`` per passage, keyed by the SHA-256 of its text, per model."""

    root: Path
    model: str = EMBED_MODEL

    def _path(self, key: str) -> Path:
        return Path(self.root) / _slug(self.model) / key[:2] / f"{key}.npy"

    def get(self, key: str) -> list[float] | None:
        import numpy as np

        path = self._path(key)
        if not path.is_file():
            return None
        try:
            return np.load(path).astype("float32").tolist()
        except (OSError, ValueError):
            return None

    def put(self, key: str, vector: Sequence[float]) -> None:
        import numpy as np

        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp.npy")
        np.save(tmp, np.asarray(vector, dtype="float16"))
        tmp.replace(path)

    def stats(self) -> dict[str, Any]:
        folder = Path(self.root) / _slug(self.model)
        files = list(folder.rglob("*.npy")) if folder.is_dir() else []
        return {"vectors": len(files), "bytes": sum(f.stat().st_size for f in files), "folder": str(folder)}


class EmbeddingUnavailable(RuntimeError):
    """Ollama or the embedder cannot answer; nothing was embedded."""


@dataclass
class OllamaEmbedder:
    """``qwen3-embedding:8b`` on the system Ollama, with a disk cache for passages.

    ``post`` and ``get`` are for tests; left unset, requests go through ``ollama_extractor._post`` (which holds the GPU
    lock for ``/api/embed``) and a plain GET for ``/api/ps``."""

    model: str = EMBED_MODEL
    base_url: str = OLLAMA_URL
    cache: VectorCache | None = None
    batch: int = 16
    timeout: int = 600
    post: Callable[[str, dict[str, Any]], dict[str, Any]] | None = None
    get: Callable[[str], dict[str, Any]] | None = None
    preflight: bool = True
    _context: int | None = field(default=None, init=False, repr=False)
    _checked: bool = field(default=False, init=False, repr=False)
    sent: int = field(default=0, init=False)          # passages embedded by Ollama in this object's life
    # Vectors read in this object's life, so a second question does not read every .npy file again.
    _memo: dict[str, list[float]] = field(default_factory=dict, init=False, repr=False)

    def _post(self, url: str, body: dict[str, Any]) -> dict[str, Any]:
        if self.post is not None:
            return self.post(url, body)
        from jason.community.ollama_extractor import _post

        return _post(url, body, self.timeout)

    def _get(self, url: str) -> dict[str, Any]:
        if self.get is not None:
            return self.get(url)
        from jason.community.ollama_extractor import _get

        return _get(url)

    def context(self) -> int | None:
        """The context window the resident embedder was loaded with, so a request does not reload it; ``None`` when
        it is not loaded (Ollama then loads it at its default, as AnythingLLM's requests do)."""
        if self._context is None:
            try:
                for m in self._get(f"{self.base_url}/api/ps").get("models", []):
                    if m.get("name") == self.model or m.get("model") == self.model:
                        self._context = int(m.get("context_length") or 0) or None
            except (OSError, ValueError) as exc:
                raise EmbeddingUnavailable(f"Ollama at {self.base_url} is not answering ({exc})") from exc
        return self._context

    def _check(self) -> None:
        if self._checked:
            return
        self._checked = True
        if self.preflight and self.post is None:
            from jason.local_ai import LocalAIUnavailable, preflight

            try:
                preflight(self.model, ollama_url=self.base_url)
            except LocalAIUnavailable as exc:
                raise EmbeddingUnavailable(str(exc)) from exc

    def _embed(self, texts: list[str]) -> list[list[float]]:
        self._check()
        body: dict[str, Any] = {"model": self.model, "input": texts, "truncate": True}
        ctx = self.context()
        if ctx:
            body["options"] = {"num_ctx": ctx}
        try:
            answer = self._post(f"{self.base_url}/api/embed", body)
        except (OSError, ValueError) as exc:
            raise EmbeddingUnavailable(f"{self.model} did not embed ({exc})") from exc
        vectors = answer.get("embeddings") or []
        if len(vectors) != len(texts):
            raise EmbeddingUnavailable(f"{self.model} returned {len(vectors)} vectors for {len(texts)} texts")
        self.sent += len(texts)
        return [_normalize(v) for v in vectors]

    def embed_passages(self, texts: Sequence[str]) -> list[list[float]]:
        out: list[list[float] | None] = []
        missing: list[int] = []
        for i, text in enumerate(texts):
            key = text_key(text)
            vector = self._memo.get(key)
            if vector is None and self.cache:
                vector = self.cache.get(key)
                if vector is not None:
                    self._memo[key] = vector
            out.append(vector)
            if vector is None:
                missing.append(i)
        for start in range(0, len(missing), self.batch):
            chunk = missing[start: start + self.batch]
            for i, vector in zip(chunk, self._embed([texts[i] for i in chunk])):
                out[i] = vector
                self._memo[text_key(texts[i])] = vector
                if self.cache:
                    self.cache.put(text_key(texts[i]), vector)
        return [v or [] for v in out]

    def embed_query(self, text: str) -> list[float]:
        return self._embed([QUERY_INSTRUCTION + text])[0]


def _cosine(a: Sequence[float], b: Sequence[float]) -> float:
    try:
        import numpy as np

        return float(np.dot(np.asarray(a, dtype="float32"), np.asarray(b, dtype="float32")))
    except ImportError:  # pragma: no cover
        return sum(x * y for x, y in zip(a, b))


def dense_rank(query: str, items: Sequence[Passage], embedder: Embedder, *, k: int | None = None) -> tuple[Hit, ...]:
    """The passages by cosine similarity to the question (both vectors unit length)."""
    if not items or not query.strip():
        return ()
    vectors = embedder.embed_passages([p.ranked for p in items])
    q = embedder.embed_query(query)
    try:
        import numpy as np

        matrix = np.asarray(vectors, dtype="float32")
        scores = (matrix @ np.asarray(q, dtype="float32")).tolist()
    except (ImportError, ValueError):
        scores = [_cosine(v, q) for v in vectors]
    hits = [Hit(p, round(s, 4)) for p, s in zip(items, scores)]
    hits.sort(key=lambda h: (-h.score, h.passage.path.name, h.passage.index))
    return tuple(hits[:k] if k else hits)


# --- rerank ---------------------------------------------------------------------------------------------------------


class Reranker(Protocol):
    def rerank(self, query: str, hits: Sequence[Hit]) -> tuple[Hit, ...]: ...


RERANK_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {"scores": {"type": "array", "items": {"type": "integer", "minimum": 0, "maximum": 3}}},
    "required": ["scores"],
}
RERANK_PROMPT = (
    "You judge search results for a question about a homeowners association's documents.\n"
    "Score each numbered passage: 3 answers the question, 2 is on point but does not answer it, 1 is related, "
    "0 is not relevant. Return JSON {\"scores\": [...]} with one integer per passage, in order.\n\n"
    "Question: {query}\n\n{passages}"
)


@dataclass
class LlmReranker:
    """One listwise request to the resident chat model (``qwen3.6:27b`` at its shared window, no thinking) that
    scores the top passages 0 to 3; the order is by score, then by the incoming order. Off by default: see
    docs/document-tools.md ("Hybrid retrieval") for its cost."""

    model: str = DEFAULT_MODEL
    base_url: str = OLLAMA_URL
    top: int = 12
    chars: int = 1600
    timeout: int = 300
    post: Callable[[str, dict[str, Any]], dict[str, Any]] | None = None
    last_seconds: float = field(default=0.0, init=False)
    model_seconds: list[float] = field(default_factory=list, init=False)

    def rerank(self, query: str, hits: Sequence[Hit]) -> tuple[Hit, ...]:
        head, tail = list(hits[: self.top]), list(hits[self.top:])
        if len(head) < 2:
            return tuple(hits)
        listing = "\n\n".join(f"[{i}] ({h.passage.title}) {h.passage.ranked[: self.chars]}" for i, h in enumerate(head, 1))
        body = {
            "model": self.model, "stream": False, "think": False, "format": RERANK_SCHEMA,
            "options": {"temperature": 0, "num_ctx": DEFAULT_CONTEXT},
            "messages": [{"role": "user", "content": RERANK_PROMPT.replace("{query}", query).replace("{passages}", listing)}],
        }
        started = time.monotonic()
        if self.post is not None:
            answer = self.post(f"{self.base_url}/api/chat", body)
        else:
            from jason.community.ollama_extractor import _post
            from jason.local_ai import LocalAIUnavailable, preflight

            try:
                preflight(self.model, ollama_url=self.base_url)
            except LocalAIUnavailable:
                return tuple(hits)          # no reranking rather than a model load the machine cannot hold
            answer = _post(f"{self.base_url}/api/chat", body, self.timeout)
        self.last_seconds = time.monotonic() - started            # with any wait for the GPU lock
        self.model_seconds.append(float(answer.get("total_duration") or 0) / 1e9)  # Ollama's own time
        try:
            scores = json.loads((answer.get("message") or {}).get("content") or "{}").get("scores") or []
        except (ValueError, AttributeError):
            scores = []
        if len(scores) < len(head):
            scores = list(scores) + [0] * (len(head) - len(scores))
        order = sorted(range(len(head)), key=lambda i: (-int(scores[i] or 0), i))
        return tuple(head[i] for i in order) + tuple(tail)


# --- near copies ----------------------------------------------------------------------------------------------------

# One document is often on the shelf two or three times: the Google Doc's export, the PDF's text, a recorded scan's
# OCR. Their passages crowd a ranking with the same words. ``collapse`` keeps the best-ranked passage of each group of
# near copies and lists the rest as "also in", so the slots go to other passages and a person still sees every source.
SHINGLE = 5                     # letters in a shingle (case, spaces, and punctuation aside, so OCR's spacing is ignored)
COPY_SIMILARITY = 0.6           # the share of the shorter passage's shingles the longer one holds
CONTAINED_MIN = 200             # a passage with fewer shingles than this (about 40 words) is short
SHORT_SIMILARITY = 0.9          # the share a short passage must have inside the other


def shingles(text: str, size: int = SHINGLE) -> frozenset[str]:
    """The passage's runs of ``size`` letters and digits, with case, spaces, and punctuation dropped."""
    letters = re.sub(r"[^a-z0-9]", "", text.lower())
    if len(letters) <= size:
        return frozenset({letters}) if letters else frozenset()
    return frozenset(letters[i: i + size] for i in range(len(letters) - size + 1))


def containment(a: frozenset[str], b: frozenset[str]) -> float:
    """How much of the smaller set the larger one holds (1.0 when one passage's words sit inside the other's)."""
    if not a or not b:
        return 0.0
    return len(a & b) / min(len(a), len(b))


_LONG_NUMBER = re.compile(r"\d[\d,/-]{3,}\d")


def _numbers(text: str) -> frozenset[str]:
    return frozenset(n for m in _LONG_NUMBER.finditer(text) if len(n := re.sub(r"\D", "", m.group(0))) >= 5)


def near_copies(a: Passage, b: Passage, *, threshold: float = COPY_SIMILARITY,
                cache: dict[int, frozenset[str]] | None = None) -> bool:
    """Whether two passages are copies of the same words: their shingles overlap by ``threshold`` or more (the shorter
    one inside the longer; a short passage nearly whole), and when
    both carry long numbers (a recording number, a policy number, a date) they share one. Two declarations of
    annexation written from one form differ only in their numbers and are not copies."""
    def grams(p: Passage) -> frozenset[str]:
        if cache is None:
            return shingles(p.text)
        key = id(p)
        if key not in cache:
            cache[key] = shingles(p.text)
        return cache[key]

    ga, gb = grams(a), grams(b)
    # A short passage (a page's boilerplate heading and table row) sits largely inside many others: it must sit
    # inside nearly whole.
    need = threshold if min(len(ga), len(gb)) >= CONTAINED_MIN else max(threshold, SHORT_SIMILARITY)
    if containment(ga, gb) < need:
        return False
    na, nb = _numbers(a.text), _numbers(b.text)
    return not (na and nb and not (na & nb))


def collapse(hits: Sequence[Hit], *, threshold: float = COPY_SIMILARITY, prefer: Callable[[Passage], Any] | None = None,
             tie: float = 0.0) -> tuple[Hit, ...]:
    """Each group of near copies as one hit: the best-ranked copy, with the others in ``Hit.also`` (in rank order).

    ``prefer`` orders copies when their scores tie (lowest first; ``tie`` is the relative margin within which scores
    count as tied): pass the association's order of authority, the recorded or adopted document before a working
    copy, as a key on the passage. Neither the library nor the profile ranks a governing document's copies yet, so
    without ``prefer`` the ranking's own order stands."""
    groups: list[list[Hit]] = []
    cache: dict[int, frozenset[str]] = {}
    for hit in hits:
        for group in groups:
            if near_copies(group[0].passage, hit.passage, threshold=threshold, cache=cache):
                group.append(hit)
                break
        else:
            groups.append([hit])
    out: list[Hit] = []
    for group in groups:
        best = group[0]
        lead = best
        if prefer is not None and len(group) > 1:
            floor = best.score - abs(best.score) * tie
            tied = [h for h in group if h.score >= floor]
            lead = min(tied, key=lambda h: (prefer(h.passage), group.index(h)))
        also = tuple(h.passage for h in group if h is not lead) + tuple(p for h in group for p in h.also)
        out.append(Hit(lead.passage, best.score, also))
    return tuple(out)


# --- "nothing relevant" ---------------------------------------------------------------------------------------------

# Measured on the held-out set's six questions with no answer in the corpus against the 116 answerable ones (October 2,
# 2026; docs/document-tools.md, Evaluation): no threshold separates them. The best on the dense cosine (0.67) flags 3
# of the 6 and 14 answerable questions (precision 0.18); the best on BM25 flags 1 of 6 (precision 0.33). So ``None``:
# no advisory is given until a threshold earns one.
NO_ANSWER_COSINE: float | None = None


def no_answer_advisory(top_cosine: float | None, *, threshold: float | None = None) -> str:
    """An advisory for a search whose best passage scored low against the question: never a reason to drop a result,
    only a note for the person reading them. Empty when no threshold is set or a passage scored above it."""
    limit = NO_ANSWER_COSINE if threshold is None else threshold
    if limit is None or top_cosine is None or top_cosine >= limit:
        return ""
    return (f"no passage scored above {limit:.2f} against the question (best {top_cosine:.2f}); "
            "the answer may not be in these documents")


# --- hybrid ---------------------------------------------------------------------------------------------------------


def _key(p: Passage) -> tuple[str, int]:
    return (str(p.path), p.index)


def boost_exact(query: str, hits: Sequence[Hit]) -> tuple[Hit, ...]:
    """Stable reorder: passages carrying more of the question's exact tokens first."""
    tokens = exact_tokens(query)
    if not tokens:
        return tuple(hits)
    counted = [(exact_count(tokens, h.passage.ranked), i, h) for i, h in enumerate(hits)]
    counted.sort(key=lambda t: (-t[0], t[1]))
    return tuple(h for _, _, h in counted)


def exact_rank(query: str, items: Sequence[Passage]) -> tuple[Hit, ...]:
    """The passages that carry any of the question's exact tokens, most tokens first."""
    tokens = exact_tokens(query)
    if not tokens:
        return ()
    hits = [Hit(p, float(n)) for p in items if (n := exact_count(tokens, p.ranked))]
    hits.sort(key=lambda h: -h.score)
    return tuple(hits)


def keyword_exact(query: str, items: Sequence[Passage], *, k: int = 8, copies: bool | None = None) -> tuple[Hit, ...]:
    """BM25 with the exact boost: the passages carrying the exact tokens first, then BM25's order. With ``copies``
    (default ``COLLAPSE_COPIES``) near copies fold into the best-ranked one before the cut (``collapse``)."""
    exact = exact_rank(query, items)
    keyword = rank(query, tuple(items), k=max(k, DENSE_DEPTH))
    fused = rrf([[_key(h.passage) for h in exact], [_key(h.passage) for h in keyword]])
    by_key = {_key(p): p for p in items}
    hits = boost_exact(query, [Hit(by_key[key], round(score, 5)) for key, score in fused])
    if COLLAPSE_COPIES if copies is None else copies:
        hits = collapse(hits)
    return hits[:k]


def hybrid(query: str, items: Sequence[Passage], *, k: int = 8, embedder: Embedder | None = None,
           reranker: Reranker | None = None, depth: int = DENSE_DEPTH, rrf_k: int = HYBRID_RRF_K,
           dense_weight: float = DENSE_WEIGHT, copies: bool | None = None) -> tuple[Hit, ...]:
    """Keyword (BM25) and dense rankings fused by RRF, the exact-token passages first, near copies folded (``copies``,
    default ``COLLAPSE_COPIES``), optionally reranked. A hit's score is its fused RRF score. Without an embedder this
    is ``keyword_exact``."""
    items = tuple(items)
    if not items or not query.strip():
        return ()
    fold = COLLAPSE_COPIES if copies is None else copies
    if embedder is None:
        hits = keyword_exact(query, items, k=max(k, depth), copies=fold)
    else:
        keyword = rank(query, items, k=depth)
        dense = dense_rank(query, items, embedder, k=depth)
        exact = exact_rank(query, items)
        rankings = [[_key(h.passage) for h in keyword], [_key(h.passage) for h in dense]]
        weights = [1.0, dense_weight]
        if exact:
            rankings.append([_key(h.passage) for h in exact])
            weights.append(1.0)
        by_key = {_key(p): p for p in items}
        fused = rrf(rankings, k=rrf_k, weights=weights)
        hits = boost_exact(query, [Hit(by_key[key], round(score, 5)) for key, score in fused])
        if fold:
            hits = collapse(hits)
    if reranker is not None:
        tokens = exact_tokens(query)
        pinned = [h for h in hits if tokens and exact_count(tokens, h.passage.ranked)]
        rest = [h for h in hits if h not in pinned]
        hits = tuple(pinned) + tuple(reranker.rerank(query, rest))
    return tuple(hits[:k])


def default_embedder(data_dir: Path | str, **kwargs: Any) -> OllamaEmbedder:
    return OllamaEmbedder(cache=VectorCache(Path(data_dir) / "retrieval" / "vectors"), **kwargs)


def search(query: str, *folders: Path | str, k: int = 8, data_dir: Path | str = "data", mode: str = "hybrid",
           rerank: bool = False, embedder: Embedder | None = None) -> tuple[Hit, ...]:
    """``passages.search`` with a mode: "keyword" (BM25, as ``passages.search``), "exact" (BM25 with the exact
    boost), "dense", or "hybrid". "dense" and "hybrid" embed through Ollama and cache under ``data_dir``. The passages
    are cut as ``CHUNKING`` says, with the outlines under ``data_dir``."""
    items = corpus(*folders, chunking=CHUNKING, outlines=Path(data_dir) / "outlines")

    def fold(hits: Sequence[Hit]) -> tuple[Hit, ...]:
        return collapse(hits)[:k] if COLLAPSE_COPIES else tuple(hits)[:k]

    if mode == "keyword":
        return fold(rank(query, items, k=max(k, DENSE_DEPTH) if COLLAPSE_COPIES else k))
    if mode == "exact":
        return keyword_exact(query, items, k=k)
    emb = embedder or default_embedder(data_dir)
    if mode == "dense":
        return fold(dense_rank(query, items, emb, k=max(k, DENSE_DEPTH) if COLLAPSE_COPIES else k))
    if mode != "hybrid":
        raise ValueError(f"unknown retrieval mode {mode!r}: keyword, exact, dense, or hybrid")
    return hybrid(query, items, k=k, embedder=emb, reranker=LlmReranker() if rerank else None)
