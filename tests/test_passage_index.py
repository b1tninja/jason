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
