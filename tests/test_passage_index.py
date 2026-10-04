"""The passage index: cut once, re-cut only what changed, scoped by its columns, ranked as the folders are."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from jason.community import passage_index as pi
from jason.community import retrieval
from jason.community.passages import corpus


class FakeEmbedder:
    """A vector from the text's words: passages sharing words point the same way."""

    def __init__(self) -> None:
        self.sent = 0

    def _vec(self, text: str) -> list[float]:
        v = [0.0] * 16
        for word in text.lower().split():
            v[int(hashlib.md5(word.encode()).hexdigest(), 16) % 16] += 1.0
        return retrieval._normalize(v)

    def embed_passages(self, texts):
        self.sent += len(texts)
        return [self._vec(t) for t in texts]

    def embed_query(self, text):
        return self._vec(text)


SOURCES = (
    pi.IndexSource("records", "governing", pi.Standing.RECORD),
    pi.IndexSource("authorities", "authorities", pi.Standing.AUTHORITY, exclude=("*.pdf.md",)),
    pi.IndexSource("private", "private", pi.Standing.RECORD, confidential=True),
)


@pytest.fixture()
def data(tmp_path: Path) -> Path:
    (tmp_path / "governing").mkdir()
    (tmp_path / "governing" / "ccrs.md").write_text(
        "# Declaration\n\n## 7.4 Garage Doors\n\nEach Owner shall maintain the garage door of the Owner's Unit.\n\n"
        "## 8.1 Assessments\n\nThe Association shall levy regular assessments.\n", encoding="utf-8")
    (tmp_path / "authorities").mkdir()
    (tmp_path / "authorities" / "civ-5855.md").write_text(
        "# Civil Code 5855\n\nThe board shall notify the member in writing of its decision within 15 days.\n",
        encoding="utf-8")
    (tmp_path / "authorities" / "re25.pdf.md").write_text("# A publication's title note\n", encoding="utf-8")
    (tmp_path / "private").mkdir()
    (tmp_path / "private" / "minutes.md").write_text("Executive session: the garage door claim.\n", encoding="utf-8")
    return tmp_path


def build(data: Path, embedder=None) -> pi.BuildReport:
    return pi.build(data, sources=SOURCES, embedder=embedder, kind_of=lambda name: "ccrs" if "ccrs" in name else "")


def test_build_cuts_each_file_once_and_only_again_when_it_changes(data):
    emb = FakeEmbedder()
    first = build(data, emb)
    assert (first.files, first.cut, first.removed, first.missing) == (3, 3, 0, 0)
    assert first.embedded == emb.sent > 0
    again = build(data, emb)
    assert (again.cut, again.embedded) == (0, 0)
    (data / "governing" / "ccrs.md").write_text("# Declaration\n\n## 7.4 Garage Doors\n\nChanged words.\n", encoding="utf-8")
    third = build(data, emb)
    assert third.cut == 1 and third.embedded >= 1
    (data / "private" / "minutes.md").unlink()
    assert build(data, emb).removed == 1


def test_a_title_note_is_left_out(data):
    build(data, FakeEmbedder())
    paths = {str(p.path.name) for p in pi.load(data, pi.Scope(confidential=True)).passages}
    assert "re25.pdf.md" not in paths and "civ-5855.md" in paths


def test_without_an_embedder_the_vectors_are_missing_not_made_up(data):
    report = build(data)
    assert report.embedded == 0 and report.missing == report.passages
    assert pi.status(data)["withoutVector"] == report.missing


def test_the_old_cache_is_copied_not_embedded_again(data):
    model = retrieval.EMBED_MODEL
    cache = retrieval.VectorCache(data / "retrieval" / "vectors", model=model)
    items = [p for p in corpus(data / "authorities", chunking=retrieval.CHUNKING, outlines=data / "outlines")
             if p.path.name != "re25.pdf.md"]
    for p in items:
        cache.put(retrieval.text_key(p.ranked), FakeEmbedder()._vec(p.ranked))
    emb = FakeEmbedder()
    report = build(data, emb)
    assert report.copied == len(items) and report.embedded == emb.sent


def test_scope_by_standing_catalog_and_confidentiality(data):
    build(data, FakeEmbedder())
    everyone = pi.load(data)
    assert {p.path.name for p in everyone.passages} == {"ccrs.md", "civ-5855.md"}       # confidential held back
    asked = pi.load(data, pi.Scope(confidential=True))
    assert "minutes.md" in {p.path.name for p in asked.passages}
    law = pi.load(data, pi.Scope(standings=(pi.Standing.AUTHORITY,)))
    assert {p.path.name for p in law.passages} == {"civ-5855.md"}
    ccrs = pi.load(data, pi.Scope(kinds=("ccrs",)))
    assert {p.path.name for p in ccrs.passages} == {"ccrs.md"}
    folder = pi.load(data, pi.Scope(folders=("governing",)))
    assert {p.path.name for p in folder.passages} == {"ccrs.md"}


def test_search_ranks_as_the_folders_do(data):
    emb = FakeEmbedder()
    build(data, emb)
    query = "who maintains the garage door"
    folders = (data / "governing", data / "authorities")
    items = corpus(*folders, chunking=retrieval.CHUNKING, outlines=data / "outlines")
    items = tuple(p for p in items if p.path.name != "re25.pdf.md")
    want = retrieval.hybrid(query, items, k=5, embedder=emb)
    got = pi.search(query, data_dir=data, k=5, embedder=emb)
    assert [(h.passage.path.name, h.passage.index) for h in want] == [(h.hit.passage.path.name, h.hit.passage.index) for h in got]
    assert got[0].row.standing is pi.Standing.RECORD and got[0].row.catalog == "records"


def test_search_uses_stored_vectors_and_embeds_only_the_question(data):
    build(data, FakeEmbedder())
    emb = FakeEmbedder()
    pi.search("garage door", data_dir=data, k=3, embedder=emb)
    assert emb.sent == 0


def test_the_mcp_search_scopes_by_catalog_and_names_the_standing(data):
    from jason.mcp.county import passage_search

    build(data, FakeEmbedder())
    records = passage_search("garage door", data_dir=data, mode="exact")
    assert records["index"] and {h["catalog"] for h in records["hits"]} == {"records"}
    law = passage_search("notify the member in writing", data_dir=data, mode="exact", catalog="all", standing="authority")
    assert [h["file"] for h in law["hits"]] == ["civ-5855.md"] and law["hits"][0]["standing"] == "authority"
    assert passage_search("x", data_dir=data, standing="binding")["available"] is False


def test_no_index_says_how_to_build_one(tmp_path):
    with pytest.raises(FileNotFoundError, match="jason index --build"):
        pi.load(tmp_path)
    assert pi.status(tmp_path)["built"] is False


def test_document_search_returns_passages_with_their_caveats_and_no_answer(data):
    from jason.mcp.county import document_search

    missing = document_search("garage door", data_dir=data)
    assert missing["available"] is False and "jason index --build" in missing["note"]
    build(data, FakeEmbedder())
    found = document_search("garage door", data_dir=data, mode="exact")
    assert found["available"] and "answer" not in found and any("not a pin" in c for c in found["caveats"])
    assert {h["catalog"] for h in found["hits"]} == {"records"} and not any(h["confidential"] for h in found["hits"])
    hit = found["hits"][0]
    assert hit["file"] == "ccrs.md" and hit["section"] and hit["standing"] == "record" and hit["kind"] == "ccrs"
    assert hit["generated"] is False
    law = document_search("notify the member in writing", data_dir=data, mode="keyword", standing="authority")
    assert [h["file"] for h in law["hits"]] == ["civ-5855.md"]
    assert document_search("x", data_dir=data, standing="binding")["available"] is False


def test_document_search_falls_back_to_keywords_without_the_embedder(data, monkeypatch):
    from jason.mcp.county import document_search

    class Down:
        def embed_passages(self, texts):
            raise retrieval.EmbeddingUnavailable("down")

        def embed_query(self, text):
            raise retrieval.EmbeddingUnavailable("down")

    build(data)
    monkeypatch.setattr(retrieval, "default_embedder", lambda data_dir, **kw: Down())
    found = document_search("garage door", data_dir=data)
    assert found["available"] and found["mode"] == "exact" and "embedder" in found["note"] and found["hits"]


def test_a_page_s_description_is_left_out_and_its_context_is_read_by_the_rankers(data):
    (data / "authorities" / "civ-5855.md").write_text(
        "# Civil Code 5850-5875\n\n- Source: a legislature\n- Path: Part 5 > Chapter 10. Dispute Resolution > Article 1. Discipline\n\n"
        "## CIV 5855\n\nThe board shall notify the member in writing of its decision within 15 days.\n", encoding="utf-8")
    sources = (pi.IndexSource("authorities", "authorities", pi.Standing.AUTHORITY, exclude=("*.pdf.md",), front_matter=True,
                              context_of=lambda path: "; ".join(pi.front_matter_labels(path).get("Path", []))),)
    emb = FakeEmbedder()
    pi.build(data, sources=sources, embedder=emb, kind_of=lambda name: "")
    loaded = pi.load(data)
    assert all(not pi.is_front_matter(p.text) for p in loaded.passages) and loaded.passages
    passage = loaded.passages[0]
    assert passage.context.startswith("Part 5 > Chapter 10") and "Dispute Resolution" in passage.ranked
    assert "Dispute Resolution" not in passage.text                       # the words shown stay the document's own
    hits = pi.search("dispute resolution discipline", data_dir=data, k=3, mode="keyword")
    assert hits and hits[0].hit.passage.path.name == "civ-5855.md"       # found by its context alone
    assert pi.search("notify the member", data_dir=data, k=3, embedder=emb) and emb.sent == len(loaded.passages)


def test_a_flag_that_moves_is_updated_without_cutting_the_file_again(data):
    emb = FakeEmbedder()
    build(data, emb)
    opened = tuple(pi.IndexSource(s.catalog, s.folder, s.standing, exclude=s.exclude) for s in SOURCES)   # none confidential
    report = pi.build(data, sources=opened, embedder=emb, kind_of=lambda name: "")
    assert report.cut == 0 and "minutes.md" in {p.path.name for p in pi.load(data).passages}


def test_a_source_gives_each_file_its_own_flags(data):
    class Mixed:
        catalogs = ("library",)

        def entries(self, data_dir):
            yield pi.IndexFile(data_dir / "governing" / "ccrs.md", "library", pi.Standing.RECORD, kind="ccrs")
            yield pi.IndexFile(data_dir / "private" / "minutes.md", "library", pi.Standing.RECORD, kind="minutes", confidential=True)

    pi.build(data, sources=(Mixed(),), embedder=FakeEmbedder())
    assert {p.path.name for p in pi.load(data).passages} == {"ccrs.md"}
    asked = pi.load(data, pi.Scope(confidential=True, kinds=("minutes",)))
    assert {p.path.name for p in asked.passages} == {"minutes.md"}


def test_a_subfolder_another_source_gives_is_left_out(data):
    (data / "authorities" / "publications").mkdir()
    (data / "authorities" / "publications" / "guide.txt").write_text("An agency's guidance on reserve studies.\n", encoding="utf-8")
    source = pi.IndexSource("authorities", "authorities", pi.Standing.AUTHORITY, exclude=("publications/*", "*.pdf.md"))
    assert [p.name for p in source.files(data)] == ["civ-5855.md"]


def test_publications_are_searched_by_what_each_is(tmp_path):
    from jason.community.authorities import Publication, PublicationText
    from jason.tasks.export_authorities import PUBLICATIONS_DIR, PublicationSource

    pubs = (Publication("Adopted regulation text", "https://example.test/reg.pdf", "who may inspect", text=PublicationText.REGULATION),
            Publication("A guide", "https://example.test/guide.pdf", "how a budget is built", number="G 1", text=PublicationText.GUIDANCE),
            Publication("A compilation", "https://example.test/all.pdf", "every section"))
    folder = tmp_path / PUBLICATIONS_DIR
    folder.mkdir(parents=True)
    for pub in pubs:
        (folder / pub.text_filename).write_text("<<PAGE 1>>\nThe owner shall keep records of inspections.\n", encoding="utf-8")
    entries = {e.path.name: e for e in PublicationSource(pubs).entries(tmp_path)}
    assert set(entries) == {"reg.txt", "guide.txt"}                       # the compilation is not searched whole
    assert entries["reg.txt"].standing is pi.Standing.AUTHORITY and entries["guide.txt"].standing is pi.Standing.REFERENCE
    assert "A guide (G 1)" in entries["guide.txt"].context and "how a budget is built" in entries["guide.txt"].context


def test_a_search_with_no_catalog_ranks_the_core_catalogs_and_says_what_it_left_out(data):
    from jason.mcp.county import document_search

    (data / "library").mkdir()
    (data / "library" / "note.md").write_text("A vendor's note about the garage door opener.\n", encoding="utf-8")
    sources = (*SOURCES[:2], pi.IndexSource("library", "library", pi.Standing.RECORD))
    pi.build(data, sources=sources, embedder=FakeEmbedder(), kind_of=lambda name: "")
    core = document_search("garage door", data_dir=data, mode="exact")
    assert core["searched"] == ["records", "authorities"] and core["notSearched"] == ["library"]
    assert {h["catalog"] for h in core["hits"]} == {"records"} and "library" in core["caveats"][-1]
    everything = document_search("garage door", data_dir=data, mode="exact", catalog="all")
    assert "library" in {h["catalog"] for h in everything["hits"]} and "searched" not in everything
    named = document_search("garage door", data_dir=data, mode="exact", catalog="library")
    assert {h["catalog"] for h in named["hits"]} == {"library"}
