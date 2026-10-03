"""The dock store (tasks, notes, asks, translations), the dock loader against a fake county module, and the writer."""

from __future__ import annotations

import json
import sys
import types
from datetime import date

import pytest

from jason.tasks import dock as store

TODAY = date(2026, 10, 3)


def test_tasks_complete_stamps_who_and_when(tmp_path):
    t = store.add_task(tmp_path, "Collect two landscape bids", by="D. Okafor", owner="the manager", due="2026-10-17", source="manual")
    assert t["id"] == "t1" and t["done"] is False and t["doneBy"] == "" and t["source"] == "manual"
    t = store.complete_task(tmp_path, "t1", by="P. Quinn")
    assert t["done"] is True and t["doneBy"] == "P. Quinn" and len(t["doneAt"]) >= 19   # ISO UTC stamp
    assert t["history"][-1].endswith("done by P. Quinn")
    t = store.complete_task(tmp_path, "t1", by="P. Quinn", done=False)
    assert t["done"] is False and t["doneBy"] == "" and t["doneAt"] == ""
    t = store.update_task(tmp_path, "t1", by="D. Okafor", owner="the treasurer", due="2026-11-01")
    assert t["owner"] == "the treasurer" and t["due"] == "2026-11-01"
    saved = json.loads((tmp_path / "dock" / "dock.json").read_text(encoding="utf-8"))
    assert saved["tasks"][0]["owner"] == "the treasurer" and saved["notes"] == []
    with pytest.raises(ValueError):
        store.add_task(tmp_path, "   ", by="D")
    with pytest.raises(ValueError):
        store.add_task(tmp_path, "x", by="")
    with pytest.raises(ValueError):
        store.add_task(tmp_path, "x", by="D", due="next week")
    with pytest.raises(ValueError):
        store.update_task(tmp_path, "t1", by="D", done=True)
    with pytest.raises(KeyError):
        store.complete_task(tmp_path, "t9", by="D")


def test_notes_are_working_notes(tmp_path):
    n = store.add_note(tmp_path, "Reserve study vendors", by="D. Okafor", body="Ask three firms.", sources=["CIV 5550"])
    assert n["id"] == "n1" and n["status"] == "researching" and n["sources"] == ["CIV 5550"]
    n = store.update_note(tmp_path, "n1", by="D. Okafor", status="question", sources=["CIV 5550", "Drive/Reserves/2021 study.pdf"])
    assert n["status"] == "question" and "researching -> question" in n["history"][-1] and len(n["sources"]) == 2
    with pytest.raises(ValueError):
        store.update_note(tmp_path, "n1", by="D", status="maybe")
    with pytest.raises(ValueError):
        store.update_note(tmp_path, "n1", by="D", sources="CIV 5550")
    with pytest.raises(ValueError):
        store.update_note(tmp_path, "n1", by="D", created="x")
    assert store.NOTE_CAVEAT.startswith("Working notes")


def test_ask_with_no_sources_is_routed_and_becomes_a_task(tmp_path):
    a = store.record_ask(tmp_path, "Can we fine without a hearing?", by="D. Okafor")
    assert a["routed"] is True and a["answer"] == store.ROUTED_ANSWER and a["sources"] == [] and a["task"] == "t1"
    tasks = store.load(tmp_path)["tasks"]
    assert len(tasks) == 1 and tasks[0]["source"] == "ask" and "Can we fine" in tasks[0]["text"] and tasks[0]["done"] is False
    b = store.record_ask(tmp_path, "When is the next meeting?", by="D. Okafor", answer="2026-10-21", sources=["meeting()"], screen="meetings")
    assert b["routed"] is False and b["task"] == "" and len(store.load(tmp_path)["tasks"]) == 1
    with pytest.raises(ValueError):
        store.record_ask(tmp_path, "  ", by="D")


def test_translation_state(tmp_path):
    x = store.add_translation(tmp_path, english_key="notice-2026-10-21", english="The board meets October 21.", language="Spanish", draft="La junta se reúne el 21 de octubre.", by="D. Okafor")
    assert x["state"] == "needs review" and x["id"] == "x1"
    x = store.translation_state(tmp_path, "x1", "sent for review", by="D. Okafor", note="approvals translations/x1")
    assert x["state"] == "sent for review" and x["history"][-1].endswith("needs review -> sent for review by D. Okafor: approvals translations/x1")
    x = store.translation_state(tmp_path, "x1", "approved", by="M. Reyes")
    assert x["state"] == "approved" and x["by"] == "M. Reyes"
    with pytest.raises(ValueError):
        store.translation_state(tmp_path, "x1", "sent", by="D")
    with pytest.raises(ValueError):
        store.add_translation(tmp_path, english_key="k", english="Hello", language="Spanish", draft="", by="D")
    with pytest.raises(ValueError):
        store.add_translation(tmp_path, english_key="k", english="", language="Spanish", draft="Hola", by="D")


# -- the loader against a fake county module ---------------------------------------------------------------------------


CALENDAR = {"asOf": "2026-10-03", "caveats": ["A payment is evidence, not proof."], "obligations": [
    {"name": "Insurance renewal: directors and officers (D-1)", "authority": "the policy term", "standing": "overdue", "next": "2026-09-30", "note": ""},
    {"name": "Budget report to members", "authority": "CIV 5300", "standing": "due soon", "next": "2026-10-10", "note": ""},
    {"name": "Draft minutes to members", "authority": "CIV 4950", "standing": "upcoming", "next": "2026-10-16", "note": ""},
    {"name": "Secretary of State statement", "authority": "Corp. Code 8210", "standing": "upcoming", "next": "2026-12-01", "note": ""},
    {"name": "Property tax, first installment", "authority": "county", "standing": "done", "next": "2026-12-10", "note": ""},
    {"name": "Backflow test", "authority": "city", "standing": "listed", "next": None, "note": ""},
]}


@pytest.fixture
def county(tmp_path):
    saved = {k: sys.modules.get(k) for k in ("jason.mcp", "jason.mcp.county")}
    fake = types.ModuleType("jason.mcp.county")
    fake.calls = []
    fake._data_dir = lambda d=None: tmp_path
    fake.association_calendar = lambda: CALENDAR
    fake.records_inventory = lambda: {"records": [{"record": "minutes", "citation": "CIV 5200(a)(8)", "folders": ["Board/Minutes"], "files": 12, "newest": "Board/Minutes/2026-09-16.pdf", "gap": ""}]}

    def library_search(**kw):
        fake.calls.append(kw)
        if kw.get("kind") == "minutes":
            return {"found": True, "count": 1, "rows": [{"path": "Board/Minutes/2026-09-16.pdf", "kind": "minutes", "period": "2026-09"}]}
        if "landscape" in str(kw.get("words", "")).lower():
            return {"found": True, "count": 1, "rows": [{"path": "Contracts/landscape-2025.pdf", "kind": "contract", "period": "2025"}]}
        return {"found": False, "note": "no hit"}
    fake.library_search = library_search
    pkg = types.ModuleType("jason.mcp")
    pkg.__path__ = []
    pkg.county = fake
    sys.modules["jason.mcp"] = pkg
    sys.modules["jason.mcp.county"] = fake
    try:
        yield fake
    finally:
        for k, v in saved.items():
            if v is None:
                sys.modules.pop(k, None)
            else:
                sys.modules[k] = v


@pytest.fixture
def loader(county, monkeypatch):
    from jason.web.extra import dock as mod

    monkeypatch.setattr(mod, "_today", lambda: TODAY)
    monkeypatch.setattr(mod, "_q_next_meeting", lambda: {"answer": "The next board meeting is 2026-10-21.", "sources": ["meeting()", "CIV 4920"]})
    return mod


def test_deadlines_grouped_with_screen_hints(loader):
    d = loader.dock({"part": "deadlines"})
    assert d["found"] and [g["label"] for g in d["groups"]] == ["Overdue", "Next 14 days", "Later"]
    assert [r["title"] for r in d["groups"][0]["rows"]] == ["Insurance renewal: directors and officers (D-1)"]
    assert [r["date"] for r in d["groups"][1]["rows"]] == ["2026-10-10", "2026-10-16"]
    assert [r["title"] for r in d["groups"][2]["rows"]] == ["Secretary of State statement"]   # done and undated rows are left out
    screens = {r["title"]: r["screen"] for g in d["groups"] for r in g["rows"]}
    assert screens["Insurance renewal: directors and officers (D-1)"] == "insurance"
    assert screens["Budget report to members"] == "reserves"
    assert screens["Draft minutes to members"] == "meetings"
    assert screens["Secretary of State statement"] == "calendar"
    assert [s["key"] for s in d["clock"]] == ["d1", "d2", "d3"] and d["clock"][0]["authority"] == "the policy term"
    assert d["counts"] == {"overdue": 1, "soon": 2, "later": 1} and d["caveats"] == CALENDAR["caveats"]
    assert loader.screen_for("Lien release, unit 7") == "liens" and loader.screen_for("Records request response, CIV 5210") == "records"
    assert loader.screen_for("Annual policy statement, CIV 5310") == "disclosures"


def test_counts_are_overdue_deadlines_and_overdue_open_tasks(loader, tmp_path):
    store.add_task(tmp_path, "late and open", by="D", due="2026-09-01")
    store.add_task(tmp_path, "late and done", by="D", due="2026-09-01")
    store.complete_task(tmp_path, "t2", by="D")
    store.add_task(tmp_path, "ahead", by="D", due="2026-10-20")
    store.add_task(tmp_path, "undated", by="D")
    assert loader.dock({"part": "counts"}) == {"found": True, "deadlines": 1, "tasks": 1}
    everything = loader.dock({})
    assert everything["counts"] == {"deadlines": 1, "tasks": 1} and everything["tasks"]["count"] == 4 and everything["notes"]["caveat"] == store.NOTE_CAVEAT
    assert loader.dock({"part": "nope"})["found"] is False


def test_common_questions_are_sourced_or_routed(loader):
    ask = loader.dock({"part": "ask"})
    by_q = {c["question"]: c for c in ask["common"]}
    assert by_q["When is the next board meeting?"]["sources"] == ["meeting()", "CIV 4920"] and by_q["When is the next board meeting?"]["routed"] is False
    due = by_q["What is due this month?"]
    assert "Budget report to members by 2026-10-10" in due["answer"] and "association_calendar()" in due["sources"] and "CIV 5300" in due["sources"]
    assert "directors and officers" in by_q["What is overdue?"]["answer"]
    minutes = by_q["Where are the minutes?"]
    assert "Board/Minutes" in minutes["answer"] and "records_inventory()" in minutes["sources"] and "library_search(kind=minutes)" in minutes["sources"]
    decided = by_q["What did the board decide last meeting?"]       # no decisions store on disk: no answer, never a guess
    assert decided["answer"] == "" and decided["sources"] == [] and decided["routed"] is True
    assert ask["translateCommand"] == "" and store.TRANSLATION_CAVEAT in ask["caveats"]


def test_free_question_hits_the_library_or_routes_to_the_manager(loader, tmp_path):
    hit = loader.write("", {"action": "ask", "by": "D. Okafor", "question": "landscape contract term"})
    assert hit["routed"] is False and "Contracts/landscape-2025.pdf" in hit["sources"] and hit["sources"][0].startswith("library_search(words=")
    assert "where the words were found, not a finding" in hit["answer"]
    miss = loader.write("", {"action": "ask", "by": "D. Okafor", "question": "Can the board fine an owner without a hearing?"})
    assert miss["routed"] is True and miss["answer"] == store.ROUTED_ANSWER and miss["sources"] == []
    tasks = store.load(tmp_path)["tasks"]
    assert len(tasks) == 1 and tasks[0]["source"] == "ask" and tasks[0]["id"] == miss["task"]
    common = loader.write("", {"action": "ask", "by": "D. Okafor", "question": "when is the next board meeting"})
    assert common["routed"] is False and common["sources"] == ["meeting()", "CIV 4920"] and common["screen"] == "meetings"


def test_writer_actions_and_refusals(loader, tmp_path):
    with pytest.raises(ValueError):
        loader.write("", {"action": "send", "by": "D"})
    with pytest.raises(ValueError):
        loader.write("", {"action": "task_add", "text": "x"})            # no by
    t = loader.write("", {"action": "task_add", "by": "D. Okafor", "text": "Bring three reserve study bids", "owner": "the manager", "due": "2026-11-18", "source": "reserves"})
    assert t["source"] == "reserves"
    assert loader.write(t["id"], {"action": "task_done", "by": "P. Quinn"})["doneBy"] == "P. Quinn"
    assert loader.write(t["id"], {"action": "task_update", "by": "D", "owner": "the treasurer", "done": False})["owner"] == "the treasurer"
    n = loader.write("", {"action": "note_add", "by": "D", "title": "Translated notices", "body": "Ask counsel.", "sources": ["Owner requests"]})
    assert loader.write(n["id"], {"action": "note_update", "by": "D", "status": "parked"})["status"] == "parked"
    x = loader.write("", {"action": "translate", "by": "D", "englishKey": "notice-2026-10-21", "english": "The board meets.", "language": "Spanish", "draft": "La junta se reúne."})
    assert x["state"] == "needs review"
    with pytest.raises(ValueError):
        loader.write("", {"action": "translate", "by": "D", "englishKey": "k", "english": "The board meets.", "language": "Spanish", "draft": ""})
    sent = loader.write(x["id"], {"action": "translation_state", "by": "D", "state": "sent for review"})
    assert sent["state"] == "sent for review" and "approvals" in sent["history"][-1]   # a draft made, or the reason it was not; either is said
    with pytest.raises(KeyError):
        loader.write("x9", {"action": "translation_state", "by": "D", "state": "sent for review"})


def test_calendar_failure_is_a_note_not_a_crash(loader, county):
    def boom():
        raise RuntimeError("no payments on disk")
    county.association_calendar = boom
    d = loader.dock({"part": "deadlines"})
    assert d["found"] is False and "no payments on disk" in d["note"] and d["counts"]["overdue"] == 0
    assert loader.dock({"part": "counts"}) == {"found": True, "deadlines": 0, "tasks": 0}
