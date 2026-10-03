"""scripts/eval_retrieval.py: scoring, the tables by kind and family, unanswerable questions, and several gold files."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from jason.community.passages import Hit, Passage

_SPEC = importlib.util.spec_from_file_location(
    "eval_retrieval", Path(__file__).resolve().parents[1] / "scripts" / "eval_retrieval.py")
ev = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(ev)


def _p(name: str, index: int, text: str) -> Passage:
    return Passage(Path("docs") / name, index, 0, text)


PASSAGES = (
    _p("rules.md", 0, "Guest parking is limited to 72 hours in any seven days."),
    _p("rules.md", 1, "Trash containers go back by 6:00 pm on collection day."),
    _p("bylaws.md", 0, "Directors serve terms of two years."),
)


def _fixed(order: list[int]):
    return lambda q: tuple(Hit(PASSAGES[i], 1.0) for i in order)


QUESTIONS = [
    {"id": "guest", "kind": "paraphrase", "family": "parking", "q": "visitor car", "files": ["rules"], "text": ["72 hours"]},
    {"id": "trash", "kind": "paraphrase", "family": "trash", "q": "bins", "files": [], "text": ["6:00 pm"]},
    {"id": "term", "kind": "exact", "family": "board", "q": "term", "files": ["bylaws"], "text": ["two years"]},
]


def test_first_ranks_and_tables_by_kind_and_family():
    methods = {"a": _fixed([0, 1, 2]), "b": _fixed([2, 1])}
    detail, seconds = ev.first_ranks(QUESTIONS, methods)
    assert detail == {"guest": {"a": 1, "b": 0}, "trash": {"a": 2, "b": 2}, "term": {"a": 3, "b": 1}}
    assert set(seconds) == {"a", "b"}
    whole = ev.table(QUESTIONS, detail, ["a", "b"])["all"]
    assert whole["a"]["recall@5"] == 1.0 and round(whole["a"]["mrr@10"], 3) == round((1 + 1 / 2 + 1 / 3) / 3, 3)
    assert round(whole["b"]["recall@5"], 3) == round(2 / 3, 3)
    kinds = ev.table(QUESTIONS, detail, ["a", "b"], "kind")
    assert kinds["exact"]["b"] == {"n": 1, "recall@5": 1.0, "mrr@10": 1.0}
    assert kinds["paraphrase"]["b"]["n"] == 2 and kinds["paraphrase"]["b"]["recall@5"] == 0.5
    assert set(ev.table(QUESTIONS, detail, ["a"], "family")) == {"parking", "trash", "board"}


def test_unanswerable_counts_parts_and_names_the_first_file():
    items = [
        {"id": "spans", "q": "x", "parts": [{"files": ["rules"], "text": ["72 hours"]}, {"files": ["bylaws"], "text": ["two years"]}]},
        {"id": "absent", "q": "y"},
    ]
    out = ev.unanswerable(items, {"a": _fixed([0, 1]), "none": _fixed([])})
    assert out["spans"] == {"a": "1/2", "none": "0/2"}
    assert out["absent"] == {"a": "rules.md", "none": "-"}


def test_parse_fusion():
    assert ev.parse_fusion("60:1.0") == (60, 1.0)
    assert ev.parse_fusion("10") == (10, 1.0)


def test_main_offline_pools_several_gold_files(tmp_path, capsys):
    folder = tmp_path / "docs"
    folder.mkdir()
    (folder / "rules.md").write_text("Guest parking is limited to 72 hours in any seven days.", encoding="utf-8")
    (folder / "bylaws.md").write_text("Directors serve terms of two years.", encoding="utf-8")
    one = tmp_path / "one.json"
    two = tmp_path / "two.json"
    one.write_text(json.dumps({"folders": ["docs"], "questions": [QUESTIONS[0]]}), encoding="utf-8")
    two.write_text(json.dumps({"folders": ["docs"], "questions": [QUESTIONS[2]],
                               "unanswerable": [{"id": "gone", "q": "backflow test"}]}), encoding="utf-8")
    out = tmp_path / "runs" / "run.json"
    assert ev.main(["--data", str(tmp_path), "--offline", "--gold", str(one), "--gold", str(two), "--json", str(out)]) == 0
    printed = capsys.readouterr().out
    assert "pooled over 2 gold files" in printed and "gone" in printed
    saved = json.loads(out.read_text(encoding="utf-8"))
    assert [Path(r["gold"]).name for r in saved["runs"]] == ["one.json", "two.json"]
    assert saved["pooled"]["all"]["keyword (BM25)"]["n"] == 2
    assert saved["runs"][1]["unanswerable"]["gone"]


def test_relevance_ignores_spacing_and_counts_a_folded_copy():
    item = {"files": ["rules"], "text": ["limited to 72 hours"]}
    spread = Hit(_p("rules.md", 5, "Guest parking is limited\nto  72 hours."), 1.0)
    assert ev.relevant(spread, item)
    folded = Hit(_p("bylaws.md", 0, "Directors serve terms of two years."), 1.0, also=(PASSAGES[0],))
    assert ev.relevant(folded, item) and not ev.relevant(folded, item, also=False)


def test_compare_lists_questions_won_and_lost_and_families_moved():
    before = {"runs": [{"gold": "g/one.json", "detail": {"guest": {"m": 7}, "trash": {"m": 1}, "term": {"m": 3}}}]}
    after = {"runs": [{"gold": "g/one.json", "detail": {"guest": {"m": 2}, "trash": {"m": 0}, "term": {"m": 1}}}]}
    row = ev.compare(before, after, {"one.json": QUESTIONS})["one.json / m"]
    assert row["won"] == ["guest(7>2)"] and row["lost"] == ["trash(1>-)"] and row["rank up"] == ["term(3>1)"]
    assert row["families moved"] == {"parking": 1, "trash": -1}


def test_separation_finds_the_threshold_that_flags_no_answer():
    answerable = {"a": {"cosine": 0.62}, "b": {"cosine": 0.55}, "c": {"cosine": 0.41}}
    absent = {"x": {"cosine": 0.38}, "y": {"cosine": 0.45}}
    row = ev.separation(answerable, absent)["cosine"]
    assert row["recall"] == 1.0 and row["precision"] == 0.667 and row["flagged answerable"] == 1
