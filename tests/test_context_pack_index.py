"""The context pack reads the passage index when it covers a tier, and cuts the folders when it does not."""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import replace
from pathlib import Path

import pytest

from jason.community import passage_index as pi
from jason.community import retrieval
from jason.community.context_pack import CORPUS, assemble, index_covers, index_law_ranking, law_corpus
from jason.community.prompts import Audience, TaskKind, TaskPrompt
from jason.community.symbols import DocumentKind

GOVERNING = CORPUS[1][0]                 # the site's governing documents folder
POLICIES = CORPUS[3][0]                  # the policies folder, held confidential in these tests

SOURCES = (
    pi.IndexSource("records", GOVERNING, pi.Standing.RECORD),
    pi.IndexSource("records", POLICIES, pi.Standing.RECORD, confidential=True),
    pi.IndexSource("authorities", "authorities", pi.Standing.AUTHORITY, exclude=("*.pdf.md",)),
)

FILLER = " ".join(f"filler{i}" for i in range(400))
CCR = "Each Owner shall keep refuse containers inside the Unit except on the day of collection."
RULE = "Rule 4. Refuse containers shall be returned to the garage by evening on the day of collection."
SECRET = "Executive session policy on refuse containers and the pending claim."


class FakeEmbedder:
    def _vec(self, text: str) -> list[float]:
        v = [0.0] * 16
        for word in text.lower().split():
            v[int(hashlib.md5(word.encode()).hexdigest(), 16) % 16] += 1.0
        return retrieval._normalize(v)

    def embed_passages(self, texts):
        return [self._vec(t) for t in texts]

    def embed_query(self, text):
        return self._vec(text)


class Community:
    """A made-up association: the pack asks only for its context lines and a file's kind."""

    def prompt_context(self):
        return ["Example Commons, 12 units"]

    def classify_document(self, name, folder=None):
        if name.startswith("CCRs"):
            return DocumentKind.DECLARATION
        if "Rules" in name:
            return DocumentKind.OPERATING_RULES
        if "Policy" in name:
            return DocumentKind.POLICY
        return None


TASK = TaskPrompt(TaskKind.RULE_REMINDER, "A reminder of a rule.", Audience.OWNER,
                  topics=("where refuse containers are kept", "the hearing before a fine"),
                  documents=(DocumentKind.DECLARATION, DocumentKind.OPERATING_RULES, DocumentKind.POLICY))


def _page(data: Path, file: str, citation: str, title: str, sections: dict[str, str]) -> dict:
    body = f"# {citation}: {title}\n\n- Source: a made-up session\n\n" + "".join(f"## {c}\n\n{t}\n\n" for c, t in sections.items())
    (data / file).parent.mkdir(parents=True, exist_ok=True)
    (data / file).write_text(body, encoding="utf-8")
    code = citation.split()[0]
    return {"file": file, "citation": citation, "title": title, "code": code, "start": "", "end": "",
            "sections": list(sections), "basis": "duty", "why": [], "session": "2025"}


@pytest.fixture()
def data(tmp_path: Path) -> Path:
    pages = [
        _page(tmp_path, "authorities/CIV/CIV-5850-5875.md", "CIV 5850-5875", "Article 2. Discipline", {
            "CIV 5850": "The board shall adopt and distribute a schedule of monetary penalties.",
            # A long section: the words that answer sit in its last passage, past the first cut.
            "CIV 5855": f"(a) {FILLER} (b) {FILLER} (c) The member shall be notified of the hearing before a fine.",
        }),
        _page(tmp_path, "authorities/CIV/CIV-4075-4190.md", "CIV 4075-4190", "Definitions", {
            "CIV 4100": "Common area means the entire common interest development except the separate interests.",
        }),
    ]
    (tmp_path / "authorities" / "manifest.json").write_text(json.dumps({"pages": pages}), encoding="utf-8")
    governing = tmp_path / GOVERNING
    governing.mkdir(parents=True)
    (governing / "CCRs.md").write_text(CCR, encoding="utf-8")
    (governing / "Owner Rules.md").write_text(RULE, encoding="utf-8")
    policies = tmp_path / POLICIES
    policies.mkdir(parents=True)
    (policies / "Closed Policy.md").write_text(SECRET, encoding="utf-8")
    return tmp_path


def _build(data: Path) -> None:
    pi.build(data, sources=SOURCES, embedder=FakeEmbedder(), kind_of=lambda name: "")


def _pack(data: Path, task: TaskPrompt = TASK, **kw):
    return assemble(Community(), task, data, mode="keyword", files=lambda kind: [], fact_runner=lambda tool, args: {}, **kw)


def _rewind(path: Path) -> None:
    """Date a file before the index cut it, as if its words had not changed since."""
    os.utime(path, (1_000_000, 1_000_000))


def test_the_law_sections_know_where_they_start(data):
    sections = {s.citation: s for s in law_corpus(data)}
    words = (data / "authorities/CIV/CIV-5850-5875.md").read_text(encoding="utf-8").split()
    assert words[sections["CIV 5855"].start_word: sections["CIV 5855"].start_word + 2] == ["##", "CIV"]
    assert sections["CIV 5855"].start_word > sections["CIV 5850"].start_word > 0


def test_the_pack_reads_the_index_s_passages(data, monkeypatch):
    _build(data)
    scopes = []
    real = pi.search
    monkeypatch.setattr(pi, "search", lambda *a, **k: scopes.append(k["scope"]) or real(*a, **k))
    # The index holds these words; the files on disk now say something else but are dated before the cut, so only a
    # pack that reads the index can show the indexed words.
    governing = data / GOVERNING / "CCRs.md"
    governing.write_text("Each Owner may paint the front door any color.", encoding="utf-8")
    _rewind(governing)
    page = data / "authorities/CIV/CIV-5850-5875.md"
    page.write_text(page.read_text(encoding="utf-8").replace("schedule of monetary penalties", "list of charges"), encoding="utf-8")
    _rewind(page)
    pack = _pack(data, law_index=True)
    g = [s for s in pack.sources if s.id.startswith("G")]
    assert any(CCR in s.text for s in g)
    s = {src.title: src for src in pack.sources if src.id.startswith("S")}
    assert "CIV 5855" in s                                   # found by its last passage, recited whole from the page
    assert s["CIV 5855"].text.startswith("(a) filler0") and s["CIV 5855"].text.endswith("before a fine.")
    assert "CIV 5850-5875: Article 2. Discipline" in pack.shelf
    law = [scope for scope in scopes if scope.standings]
    assert law and all(scope.folders == ("authorities/CIV",) and not scope.confidential for scope in law)
    assert any(GOVERNING in scope.folders for scope in scopes if not scope.standings)


def test_short_law_sections_joined_in_one_passage_are_each_found_by_their_label(data, monkeypatch):
    # Two sections under the minimum share one passage; its heading carries each one's label, and it answers for both.
    from jason.community import passage_sections

    monkeypatch.setattr(passage_sections, "MIN_PASSAGE_WORDS", 25)
    manifest = data / "authorities" / "manifest.json"
    pages = json.loads(manifest.read_text(encoding="utf-8"))["pages"]
    pages.append(_page(data, "authorities/CIV/CIV-4200-4205.md", "CIV 4200-4205", "Names", {
        "CIV 4200": "The declaration shall name the association.",
        "CIV 4205": "The articles shall name the managing agent of the association.",
    }))
    manifest.write_text(json.dumps({"pages": pages}), encoding="utf-8")
    _build(data)
    joined = [p for p in pi.load(data).passages if "managing agent" in p.text]
    assert len(joined) == 1 and "The declaration shall name" in joined[0].text
    assert joined[0].heading.split(" > ")[1:] == ["CIV 4200", "CIV 4205"]
    sections = law_corpus(data)
    found = index_law_ranking(sections, data, mode="keyword")("the managing agent named in the articles", 2)
    assert [sections[i].citation for i in found] == ["CIV 4200", "CIV 4205"]
    # A long section is still one passage a piece, each read as its section by the label in its heading.
    last = [p for p in pi.load(data).passages if "before a fine" in p.text]
    assert last and last[0].heading.split(" > ")[1:] == ["CIV 5855"]
    first = index_law_ranking(sections, data, mode="keyword")("notified of the hearing before a fine", 1)
    assert [sections[i].citation for i in first] == ["CIV 5855"]


def test_a_member_s_pack_never_sees_a_confidential_row_and_the_board_s_does(data):
    _build(data)
    member = _pack(data)
    assert not any(SECRET in s.text for s in member.sources)
    board = _pack(data, replace(TASK, audience=Audience.BOARD))
    assert any(SECRET in s.text for s in board.sources if s.id.startswith("G"))


def test_without_an_index_the_folders_are_cut(data, monkeypatch):
    def no_index(*a, **k):
        raise AssertionError("the index was searched")

    monkeypatch.setattr(pi, "search", no_index)
    pack = _pack(data)
    assert any(CCR in s.text for s in pack.sources if s.id.startswith("G"))
    assert "CIV 5855" in {s.title for s in pack.sources if s.id.startswith("S")}


def test_a_file_changed_since_the_cut_sends_its_tier_back_to_the_folders(data):
    _build(data)
    governing = data / GOVERNING / "CCRs.md"
    governing.write_text("Each Owner shall keep refuse containers in the garage, always.", encoding="utf-8")
    os.utime(governing, None)
    later = governing.stat().st_mtime + 60
    os.utime(governing, (later, later))
    assert not index_covers(data, [governing])
    pack = _pack(data)
    assert any("in the garage, always" in s.text for s in pack.sources if s.id.startswith("G"))


def test_a_file_the_index_lacks_sends_its_tier_back_to_the_folders(data, monkeypatch):
    _build(data)
    (data / GOVERNING / "Late Rules.md").write_text("Rule 9. Refuse containers on the day of collection only.", encoding="utf-8")
    calls = []
    real = pi.search
    monkeypatch.setattr(pi, "search", lambda *a, **k: calls.append(k["scope"]) or real(*a, **k))
    pack = _pack(data, law_index=True)
    assert any("Rule 9" in s.text for s in pack.sources if s.id.startswith("G"))
    assert calls and all(pi.Standing.AUTHORITY in scope.standings for scope in calls)   # the law still read the index


def test_by_default_the_law_is_ranked_whole_and_the_governing_documents_from_the_index(data, monkeypatch):
    _build(data)
    calls = []
    real = pi.search
    monkeypatch.setattr(pi, "search", lambda *a, **k: calls.append(k["scope"]) or real(*a, **k))
    pack = _pack(data)
    assert calls and not any(scope.standings for scope in calls)
    assert "CIV 5855" in {s.title for s in pack.sources if s.id.startswith("S")}


def test_use_index_false_cuts_every_tier(data, monkeypatch):
    _build(data)
    monkeypatch.setattr(pi, "search", lambda *a, **k: (_ for _ in ()).throw(AssertionError("the index was searched")))
    pack = _pack(data, use_index=False, law_index=True)
    assert any(s.id.startswith("G") for s in pack.sources) and any(s.id.startswith("S") for s in pack.sources)


def test_hybrid_ranks_the_index_with_its_stored_vectors(data):
    _build(data)
    pack = assemble(Community(), TASK, data, mode="hybrid", embedder=FakeEmbedder(), law_index=True, files=lambda kind: [],
                    fact_runner=lambda tool, args: {})
    assert any(CCR in s.text for s in pack.sources if s.id.startswith("G"))
    assert "CIV 5855" in {s.title for s in pack.sources if s.id.startswith("S")}
