"""Hybrid retrieval: RRF, the exact-token boost, the dense ranker's cache and context, and the reranker, all without
Ollama (the embed and chat calls are fakes)."""

from __future__ import annotations

import json
from pathlib import Path

from jason.community import retrieval
from jason.community.passages import Hit, Passage, rank
from jason.community.retrieval import (
    LlmReranker,
    OllamaEmbedder,
    VectorCache,
    boost_exact,
    carries,
    dense_rank,
    exact_tokens,
    hybrid,
    keyword_exact,
    rrf,
)

TOPICS = ("garage", "roof", "pool", "insurance", "lease")


def _vector(text: str) -> list[float]:
    """A toy embedding: one dimension per topic word family, so paraphrases land together."""
    low = text.lower()
    families = (("garage", "door", "overhead"), ("roof", "shingle", "gutter"), ("pool", "swim"),
                ("insurance", "deductible", "policy", "coverage"), ("lease", "rent", "tenant"))
    return [float(sum(low.count(w) for w in fam)) + 0.01 for fam in families]


class FakeOllama:
    def __init__(self, context: int | None = 2048) -> None:
        self.context = context
        self.embeds: list[dict] = []
        self.gets: list[str] = []

    def get(self, url: str) -> dict:
        self.gets.append(url)
        models = [{"name": "qwen3-embedding:8b", "context_length": self.context}] if self.context else []
        return {"models": [{"name": "qwen3.6:27b", "context_length": 65536}] + models}

    def post(self, url: str, body: dict) -> dict:
        assert url.endswith("/api/embed")
        self.embeds.append(body)
        return {"embeddings": [_vector(t) for t in body["input"]]}


def _passages() -> tuple[Passage, ...]:
    texts = [
        "Article 7 Section 7.4(c) Garage Doors. Each Owner shall maintain the overhead door of the Unit.",
        "The Association shall maintain the roof coverings, shingles, and gutters of the buildings.",
        "Recorded January 17, 2020 as Document No. 202001170712 in the Official Records.",
        "The master policy carries a deductible of ten thousand dollars on the building coverage.",
        "An Owner who wishes to rent the Unit to a tenant shall submit a written application.",
        "Swimming pool hours are 8 a.m. to 10 p.m.; no glass in the pool area.",
        "Special Resolution authorizing foreclosure of the lien on APN 201-1170-024-0007.",
        "Document No. 2020011707120 is a different, longer number.",
    ]
    return tuple(Passage(Path(f"doc{i}.md"), 0, 0, t) for i, t in enumerate(texts))


def test_rrf_sums_reciprocal_ranks_and_keeps_first_seen_order_on_ties():
    fused = rrf([["a", "b", "c"], ["b", "a", "d"]], k=60)
    assert [item for item, _ in fused][:2] == ["a", "b"]           # tie: a seen first
    assert dict(fused)["a"] == 1 / 61 + 1 / 62
    assert [item for item, _ in fused][2:] == ["c", "d"]
    assert rrf([]) == []


def test_exact_tokens_pick_numbers_apns_and_sections_not_amounts():
    tokens = exact_tokens("Was 202001170712 or APN 201-1170-024-0007 under Civil Code 5855? Policy N030PK2940-01, $10,000, 2026")
    assert "202001170712" in tokens and "201-1170-024-0007" in tokens and "5855" in tokens and "N030PK2940-01" in tokens
    assert "10,000" not in tokens and "2026" not in tokens
    assert exact_tokens("who fixes the garage door?") == ()


def test_carries_needs_the_whole_token():
    assert carries("202001170712", "as Document No. 202001170712, in the")
    assert not carries("202001170712", "Document No. 2020011707120")
    assert carries("201-1170-024-0007", "APN 20111700240007 on the roll")


def test_boost_exact_is_stable_and_puts_carriers_first():
    items = _passages()
    hits = [Hit(p, 1.0) for p in items]
    boosted = boost_exact("what is 202001170712", hits)
    assert boosted[0].passage.text.startswith("Recorded January 17")
    assert [h.passage.path.name for h in boosted[1:]] == [h.passage.path.name for h in hits if h.passage.path.name != "doc2.md"]


def test_keyword_exact_without_a_model_keeps_bm25_and_adds_the_boost():
    items = _passages()
    hits = keyword_exact("foreclosure APN 201-1170-024-0007", items, k=3)
    assert hits[0].passage.path.name == "doc6.md"
    # without exact tokens it is BM25's order
    plain = keyword_exact("swimming pool hours", items, k=2)
    assert plain[0].passage.path.name == rank("swimming pool hours", items, k=2)[0].passage.path.name


def test_dense_rank_uses_the_resident_context_and_caches_vectors(tmp_path):
    fake = FakeOllama(context=2048)
    cache = VectorCache(tmp_path / "vectors")
    embedder = OllamaEmbedder(cache=cache, post=fake.post, get=fake.get, batch=3)
    items = _passages()
    hits = dense_rank("who repairs the overhead door", items, embedder, k=2)
    assert hits[0].passage.path.name == "doc0.md"
    passage_calls = [b for b in fake.embeds if not b["input"][0].startswith("Instruct:")]
    assert [len(b["input"]) for b in passage_calls] == [3, 3, 2]                   # batched
    assert all(b["options"] == {"num_ctx": 2048} for b in fake.embeds)             # the resident window, no reload
    assert fake.embeds[-1]["input"][0].startswith(retrieval.QUERY_INSTRUCTION)
    assert cache.stats()["vectors"] == len(items)
    # a second run embeds only the question
    fake.embeds.clear()
    again = OllamaEmbedder(cache=cache, post=fake.post, get=fake.get)
    dense_rank("who repairs the overhead door", items, again, k=2)
    assert len(fake.embeds) == 1 and again.sent == 1


def test_embedder_not_resident_sends_no_num_ctx(tmp_path):
    fake = FakeOllama(context=None)
    embedder = OllamaEmbedder(cache=None, post=fake.post, get=fake.get)
    embedder.embed_query("roof")
    assert "options" not in fake.embeds[0]


def test_hybrid_finds_paraphrase_and_keeps_exact_first(tmp_path):
    fake = FakeOllama()
    embedder = OllamaEmbedder(cache=VectorCache(tmp_path), post=fake.post, get=fake.get)
    items = _passages()
    # BM25 alone misses: no word of the question is in the garage passage besides "door"
    para = hybrid("who has to fix my overhead garage door", items, k=3, embedder=embedder)
    assert para[0].passage.path.name == "doc0.md"
    exact = hybrid("the insurance policy on 202001170712", items, k=3, embedder=embedder)
    assert exact[0].passage.path.name == "doc2.md"                                # the exact number beats the topic
    assert hybrid("", items, embedder=embedder) == ()


def test_reranker_orders_by_score_and_keeps_exact_hits_pinned(tmp_path):
    fake = FakeOllama()
    embedder = OllamaEmbedder(cache=VectorCache(tmp_path), post=fake.post, get=fake.get)
    items = _passages()
    chats: list[dict] = []

    def chat(url: str, body: dict) -> dict:
        chats.append(body)
        n = body["messages"][0]["content"].count("\n[")
        scores = [0] * (n + 1)
        scores[-1] = 3
        return {"message": {"content": json.dumps({"scores": scores})}}

    reranker = LlmReranker(post=chat, top=4)
    hits = hybrid("pool hours 202001170712", items, k=5, embedder=embedder, reranker=reranker)
    assert hits[0].passage.path.name == "doc2.md"                                  # exact, never reranked away
    body = chats[0]
    assert body["think"] is False and body["options"]["num_ctx"] == 65536 and body["format"] == retrieval.RERANK_SCHEMA
    assert "doc2.md" not in body["messages"][0]["content"]


def test_reranker_tolerates_a_bad_answer():
    items = [Hit(p, 1.0) for p in _passages()[:3]]
    reranker = LlmReranker(post=lambda url, body: {"message": {"content": "not json"}})
    assert reranker.rerank("q", items) == tuple(items)


def test_passage_search_modes(tmp_path, monkeypatch):
    from jason.mcp.county import passage_search

    folder = tmp_path / "governing"
    folder.mkdir()
    (folder / "ccrs.md").write_text("Section 7.4 Garage Doors. Each Owner shall maintain the garage door.", encoding="utf-8")
    (folder / "rules.md").write_text("Recorded as Document No. 202001170712.", encoding="utf-8")
    default = passage_search("garage door", data_dir=tmp_path)
    assert "mode" not in default and default["hits"][0]["file"] == "ccrs.md"      # unchanged default output
    exact = passage_search("202001170712", data_dir=tmp_path, mode="exact")
    assert exact["mode"] == "exact" and exact["hits"][0]["file"] == "rules.md"

    def down(self, texts):
        raise retrieval.EmbeddingUnavailable("Ollama is down")

    monkeypatch.setattr(OllamaEmbedder, "_embed", down)
    hybrid_down = passage_search("garage door", data_dir=tmp_path, mode="hybrid")
    assert hybrid_down["available"] is False and "Ollama" in hybrid_down["note"]
