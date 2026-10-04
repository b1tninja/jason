"""The context pack's records tier read from the passage index's library catalog, and when it falls back to the library."""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from dataclasses import replace
from pathlib import Path

import pytest

from jason.community import context_pack
from jason.community import passage_index as pi
from jason.community import retrieval
from jason.community.context_pack import RecordReach, assemble
from jason.community.passages import Passage
from jason.community.prompts import Audience, TaskKind, TaskPrompt
from jason.community.symbols import DocumentKind
from jason.tasks import index_sources as sources
from jason.tasks import library

ROOF = "The contractor shall complete a roof inspection each spring and send photographs of the roof."
PATROL = "The officer shall patrol the grounds each night, and patrol the garages and the grounds on weekends."
PAINT = "The painter shall prepare the exterior trim and apply two coats."
ALARM = "The vendor shall carry out the inspection and testing of the fire alarm system each year and list every deficiency."
LAWN = "The landscaper shall mow and edge the lawns weekly."
FORUM = "Open forum. Any member may speak to the board for two minutes before the board takes up its agenda."
REPORT = "Treasurer's report. The board reviewed the finances for the month. Aging by unit follows."
STATEMENT = "Statement of account for the reserve fund, reviewed by the board with the finances."

# (id, path, kind, sha256, period, confidential)
ROWS = [
    ("10", "Contracts/Roof inspection.pdf", "contract", "c10", "2025-07", False),
    ("11", "Contracts/Night patrol.pdf", "contract", "c11", "2025-02", False),
    ("12", "Contracts/Painting.pdf", "contract", "c12", "2024-04", False),
    ("13", "Contracts/Fire alarm testing.pdf", "contract", "c13", "2021-03", False),
    ("14", "Contracts/Landscape.pdf", "contract", "c14", "", False),
    ("20", "Meetings/Minutes of January.pdf", "minutes", "m20", "2026-01", False),
    ("21", "Meetings/Minutes of February.pdf", "minutes", "m21", "2026-02", False),
    ("22", "Meetings/Minutes of March.pdf", "minutes", "m22", "2026-03", False),
    ("23", "Meetings/Minutes of April.pdf", "minutes", "m23", "2026-04", False),
    # A kind the library does not flag and the index holds back (``index_sources.HELD_KINDS``).
    ("30", "Financials/Treasurer's Report March_Redacted.pdf", "treasurer_report", "t30", "2026-03", False),
    ("31", "Financials/Reserve statement.pdf", "financial_statement", "f31", "2026-03", True),
]
TEXTS = {"10": ROOF, "11": PATROL, "12": PAINT, "13": ALARM, "14": LAWN, "20": FORUM, "21": FORUM, "22": FORUM, "23": FORUM,
         "30": REPORT, "31": STATEMENT}

FIRE = TaskPrompt(TaskKind.FIRE_SYSTEM_TESTING, "Tell residents when a system will be tested.", Audience.SOME_MEMBERS,
                  topics=("inspection and testing of fire alarm systems", "who may patrol the grounds"),
                  documents=(DocumentKind.CONTRACT,))
MEETING = TaskPrompt(TaskKind.MEETING_NOTICE, "Notice of a board meeting.", Audience.MEMBERS,
                     topics=("members' right to speak to the board",), documents=(DocumentKind.MINUTES,))
FINANCES = TaskPrompt(TaskKind.TREASURER_REPORT, "Share the monthly summary.", Audience.MEMBERS,
                      topics=("the board's review of the finances",),
                      documents=(DocumentKind.TREASURER_REPORT, DocumentKind.FINANCIAL_STATEMENT))


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
        return None


def _add(data: Path, row: tuple, words: str) -> None:
    doc_id, path, kind, sha, period, confidential = row
    with sqlite3.connect(data / library.STORE) as conn:
        conn.execute(library.SCHEMA)
        conn.execute("INSERT INTO documents VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                     (doc_id, "payhoa", path, path.rsplit("/", 1)[-1], kind, "", "", "NAME", period, int(confidential), "",
                      1.0, "2026-01-01T00:00:00+00:00", sha))
    conn.close()
    (data / "library" / "text" / f"{doc_id}.txt").write_text(words + "\n", encoding="utf-8")


@pytest.fixture()
def data(tmp_path: Path) -> Path:
    (tmp_path / "library" / "text").mkdir(parents=True)
    for row in ROWS:
        _add(tmp_path, row, TEXTS[row[0]])
    return tmp_path


def _build(data: Path) -> None:
    pi.build(data, sources=(sources.LibrarySource(),), embedder=FakeEmbedder(), kind_of=lambda name: "")


def _later(path: Path) -> None:
    """Date a file after the index cut it."""
    stamp = path.stat().st_mtime + 60
    os.utime(path, (stamp, stamp))


def _pack(data: Path, task: TaskPrompt, **kw):
    kw.setdefault("mode", "keyword")
    return assemble(Community(), task, data, law=[], search=lambda *a, **k: (), fact_runner=lambda tool, args: {}, **kw)


def _records(pack) -> list[tuple]:
    return [(s.id, int(s.tier), s.title, s.text, s.place) for s in pack.sources if s.id.startswith("R")]


def _no_index(monkeypatch) -> None:
    def refuse(*a, **k):
        raise AssertionError("the index was read")

    monkeypatch.setattr(pi, "load", refuse)
    monkeypatch.setattr(pi, "search", refuse)


def test_the_latest_files_from_the_index_are_the_library_reader_s_sources(data):
    _build(data)
    old = _pack(data, FIRE, use_index=False)
    new = _pack(data, FIRE, records_index=True)
    assert [title for _, _, title, _, _ in _records(old)] == ["Contracts/Night patrol.pdf (2025-02)", "Contracts/Roof inspection.pdf (2025-07)"]
    assert _records(new) == _records(old)                       # the same ids, tiers, titles, words, and places
    assert all(s.standing is pi.Standing.RECORD for s in new.sources if s.id.startswith("R"))
    assert new.gaps == old.gaps


def test_by_default_the_records_are_read_from_the_library(data, monkeypatch):
    _build(data)
    assert context_pack.RECORDS_FROM_INDEX is False and context_pack.RECORDS_REACH is RecordReach.LATEST
    _no_index(monkeypatch)
    pack = _pack(data, FIRE)
    assert [title for _, _, title, _, _ in _records(pack)] == ["Contracts/Night patrol.pdf (2025-02)", "Contracts/Roof inspection.pdf (2025-07)"]


def test_the_index_s_passages_are_cut_on_sections_so_a_file_with_headings_reads_differently(data):
    # Why the index is not the default: the library reader cuts 220-word windows, the index cuts on a file's headings.
    (data / "library" / "text" / "10.txt").write_text(
        "SCOPE OF WORK\n\nThe contractor shall complete a roof inspection each spring.\n\n"
        "PAYMENT TERMS\n\nThe fee for each inspection is due on the day of the inspection, before the report.\n", encoding="utf-8")
    _build(data)
    old = {text for _, _, title, text, _ in _records(_pack(data, FIRE, use_index=False)) if "Roof" in title}
    new = {text for _, _, title, text, _ in _records(_pack(data, FIRE, records_index=True)) if "Roof" in title}
    assert len(old) == 1 and "SCOPE OF WORK" in next(iter(old)) and "PAYMENT TERMS" in next(iter(old))     # one window
    assert new and all(("SCOPE OF WORK" in text) != ("PAYMENT TERMS" in text) for text in new)             # a section each


@pytest.mark.parametrize("reach", list(RecordReach))
def test_a_member_s_task_never_gets_a_document_the_index_holds_back(data, reach):
    _build(data)
    old = _pack(data, FINANCES, use_index=False)
    assert [title for _, _, title, _, _ in _records(old)] == ["Financials/Treasurer's Report March_Redacted.pdf (2026-03)"]
    member = _pack(data, FINANCES, records_index=True, records_reach=reach)
    assert _records(member) == []
    assert not any(REPORT in s.text or STATEMENT in s.text for s in member.sources)
    assert [g for g in member.gaps if "holds back" in g] == [
        "the passage index holds back 1 treasurer report file as confidential that the library does not flag; "
        "this task's audience is all members: nothing from it is in this pack"]
    board = _pack(data, replace(FINANCES, audience=Audience.BOARD), records_index=True, records_reach=reach)
    assert {text for _, _, _, text, _ in _records(board)} == {REPORT, STATEMENT}
    assert not any("holds back" in g for g in board.gaps)


def test_a_member_s_scope_never_opens_a_held_file_named_by_its_path(data):
    _build(data)
    names = ("library/text/30.txt", "library/text/10.txt")
    assert {p.path.name for p in pi.load(data, pi.Scope(paths=names), vectors=False).passages} == {"10.txt"}
    assert {p.path.name for p in pi.load(data, pi.Scope(paths=names, confidential=True), vectors=False).passages} == {"10.txt", "30.txt"}


@pytest.mark.parametrize("reach", list(RecordReach))
def test_without_an_index_the_library_is_read(data, monkeypatch, reach):
    _no_index(monkeypatch)
    pack = _pack(data, FIRE, records_index=True, records_reach=reach)
    assert _records(pack) == _records(_pack(data, FIRE, use_index=False))
    assert len(_records(pack)) == 2


@pytest.mark.parametrize("reach", list(RecordReach))
def test_a_file_changed_since_the_cut_sends_the_tier_back_to_the_library(data, monkeypatch, reach):
    _build(data)
    changed = data / "library" / "text" / "11.txt"
    changed.write_text("The officer shall patrol the grounds twice each night.\n", encoding="utf-8")
    _later(changed)
    _no_index(monkeypatch)
    pack = _pack(data, FIRE, records_index=True, records_reach=reach)
    assert any("twice each night" in text for _, _, _, text, _ in _records(pack))


@pytest.mark.parametrize("reach", list(RecordReach))
def test_a_file_the_index_lacks_sends_the_tier_back_to_the_library(data, monkeypatch, reach):
    _build(data)
    _add(data, ("15", "Contracts/Sprinkler testing.pdf", "contract", "c15", "2026-01", False),
         "The vendor shall carry out the inspection and testing of the fire sprinkler system and the fire alarm.")
    _no_index(monkeypatch)
    pack = _pack(data, FIRE, records_index=True, records_reach=reach)
    assert "Contracts/Sprinkler testing.pdf (2026-01)" in [title for _, _, title, _, _ in _records(pack)]


def test_a_reading_of_some_pages_joined_with_the_older_text_is_not_in_the_index(data, monkeypatch):
    folder = data / "library" / "text"
    (folder / "10.vision.txt").write_text("A vision reading of the first page: roof inspection photographs.\n", encoding="utf-8")
    (folder / "10.vision.json").write_text(json.dumps({"pages": 3, "pagesRead": 1}), encoding="utf-8")
    assert library.text_joined(data, "10") and not library.text_joined(data, "11")
    assert library.text_path(data, "10") == folder / "10.txt"
    _build(data)
    _no_index(monkeypatch)                                       # the library reader's words are in no one file
    pack = _pack(data, FIRE, records_index=True)
    assert any(library.VISION_MARK in text for _, _, _, text, _ in _records(pack))


def test_a_text_file_names_its_document(data):
    assert library.text_owner("library/text/10.txt") == "10" and library.text_owner("library/text/10.vision.txt") == "10"
    assert library.text_owner("meetings/minutes-files/abc.txt") == "drive-abc"
    assert library.text_owner("mail/10/letter.md") == "" and library.text_owner("library/text/10.json") == ""


def test_across_the_kind_an_older_file_that_answers_the_question_is_found(data):
    _build(data)
    old = [title for _, _, title, _, _ in _records(_pack(data, FIRE, use_index=False))]
    latest = [title for _, _, title, _, _ in _records(_pack(data, FIRE, records_index=True))]
    assert "Contracts/Fire alarm testing.pdf (2021-03)" not in old + latest     # it is not among the latest three
    pack = _pack(data, FIRE, records_index=True, records_reach=RecordReach.KIND)
    found = _records(pack)
    assert [(rid, title) for rid, _, title, _, _ in found] == [("R1", "Contracts/Night patrol.pdf (2025-02)"),
                                                               ("R2", "Contracts/Fire alarm testing.pdf (2021-03)")]
    assert found[1][3] == ALARM and found[1][4] == "contract, passage 0"


def test_across_the_kind_one_file_gives_one_passage(data):
    long = " ".join([ALARM] * 30)                               # several windows, each answering the question
    (data / "library" / "text" / "13.txt").write_text(long + "\n", encoding="utf-8")
    _build(data)
    assert len(pi.load(data, pi.Scope(paths=("library/text/13.txt",)), vectors=False).passages) > 2
    titles = [title for _, _, title, _, _ in _records(_pack(data, FIRE, records_index=True, records_reach=RecordReach.KIND))]
    assert titles.count("Contracts/Fire alarm testing.pdf (2021-03)") == context_pack.RECORD_PER_FILE == 1
    assert len(titles) == context_pack.RECORD_PASSAGES


def test_across_the_kind_copies_of_a_passage_fold_onto_the_latest_file(data):
    _build(data)
    pack = _pack(data, MEETING, records_index=True, records_reach=RecordReach.KIND)
    assert [(title, text) for _, _, title, text, _ in _records(pack)] == [("Meetings/Minutes of April.pdf (2026-04)", FORUM)]


def test_across_the_kind_recency_orders_files_the_questions_rank_alike_and_no_more(data, monkeypatch):
    _build(data)

    def titles() -> list[str]:
        return [title for _, _, title, _, _ in _records(_pack(data, FIRE, records_index=True, records_reach=RecordReach.KIND))]

    # Each is first for one question: the later file leads. The roof contract, the latest of all, shares one word with
    # a question and stays behind both.
    assert titles() == ["Contracts/Night patrol.pdf (2025-02)", "Contracts/Fire alarm testing.pdf (2021-03)"]
    monkeypatch.setattr(context_pack, "RECORD_RECENCY_WEIGHT", 0.0)
    assert titles() == ["Contracts/Fire alarm testing.pdf (2021-03)", "Contracts/Night patrol.pdf (2025-02)"]


@pytest.mark.parametrize("reach", list(RecordReach))
def test_hybrid_ranks_the_records_with_the_index_s_stored_vectors(data, reach):
    _build(data)
    embedder = FakeEmbedder()
    asked: list[int] = []
    real = embedder.embed_passages
    embedder.embed_passages = lambda texts: asked.append(len(texts)) or real(texts)
    pack = _pack(data, FIRE, mode="hybrid", embedder=embedder, records_index=True, records_reach=reach)
    assert _records(pack) and not asked                         # no passage was embedded again


def test_a_dense_floor_keeps_a_far_passage_out_of_the_hybrid_ranking():
    items = (Passage(Path("a.txt"), 0, 0, "The vendor shall test the fire alarm each year."),
             Passage(Path("b.txt"), 0, 0, "The landscaper shall mow the lawns weekly."))
    query = "testing the fire alarm"
    assert len(retrieval.hybrid(query, items, k=5, embedder=FakeEmbedder())) == 2          # the dense ranking places both
    floored = retrieval.hybrid(query, items, k=5, embedder=FakeEmbedder(), dense_floor=2.0)
    assert [h.passage.path.name for h in floored] == ["a.txt"]                              # only the keyword hit is left
