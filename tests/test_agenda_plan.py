"""The agenda plan store (data/meetings/plan-<date>.json) and the plan-a-meeting loader's computed readiness checks."""

import json
import sys
import types

import pytest

from jason.tasks import agenda_plan as store


def test_update_merges_fields_and_keeps_history(tmp_path):
    plan = store.update(tmp_path, "2026-10-21", {"basics": {"start": "18:30", "format": "hybrid", "location": "Clubhouse, 123 Main St"}}, by="D. Okafor")
    assert plan["basics"]["format"] == "hybrid" and plan["basics"]["date"] == "2026-10-21"
    assert plan["history"] == [f"{plan['updated'][:10]}: D. Okafor changed basics.start, basics.format, basics.location"]
    plan = store.update(tmp_path, "2026-10-21", {"items": {"reserve-loan": {"include": True, "kind": "action", "allot": 15, "order": 0,
                                                                            "motion": "Move to restore $12,500.00 to reserves by 2026-10-31.",
                                                                            "packet": [{"id": "f1", "name": "Resolution.docx", "kind": "doc", "url": "https://docs.google.com/document/d/f1"}]}}}, by="D. Okafor")
    assert plan["items"]["reserve-loan"]["allot"] == 15 and plan["items"]["reserve-loan"]["packet"][0]["name"] == "Resolution.docx"
    assert plan["history"][-1].endswith("items.reserve-loan.include, items.reserve-loan.kind, items.reserve-loan.allot, items.reserve-loan.order, items.reserve-loan.motion, items.reserve-loan.packet")
    plan = store.update(tmp_path, "2026-10-21", {"brief": {"reserve-loan": {"question": "How is the loan restored?", "criteria": ["How", "When"],
                                                                            "options": [{"label": "Transfer", "values": ["from operating", "by 2026-10-31"]}], "facts": ["Due 2026-11-03 (CIV 5515(b))"]}},
                                                 "zoom": {"joinUrl": "https://zoom.us/j/1", "dialIn": "+1 555 0100"}}, by="D. Okafor")
    assert plan["items"]["reserve-loan"]["brief"]["options"][0]["label"] == "Transfer" and plan["items"]["reserve-loan"]["motion"].startswith("Move")
    assert plan["zoom"]["joinUrl"] == "https://zoom.us/j/1"
    assert "items.reserve-loan.brief, zoom.joinUrl, zoom.dialIn" in plan["history"][-1]
    on_disk = json.loads((tmp_path / "meetings" / "plan-2026-10-21.json").read_text())
    assert on_disk["items"]["reserve-loan"]["include"] is True and len(on_disk["history"]) == 3
    assert store.load(tmp_path, "2026-10-21") == plan
    assert store.load(tmp_path, "2026-11-18")["items"] == {} and store.load(tmp_path, "2026-11-18")["history"] == []


def test_refusals(tmp_path):
    with pytest.raises(ValueError, match="by"):
        store.update(tmp_path, "2026-10-21", {"basics": {"start": "18:30"}}, by="")
    with pytest.raises(ValueError, match="YYYY-MM-DD"):
        store.update(tmp_path, "next tuesday", {"basics": {"start": "18:30"}}, by="D")
    with pytest.raises(ValueError, match="recommend"):
        store.update(tmp_path, "2026-10-21", {"brief": {"x": {"question": "q", "criteria": [], "options": [], "facts": [], "recommended": "A"}}}, by="D")
    with pytest.raises(ValueError, match="recommend"):
        store.update(tmp_path, "2026-10-21", {"items": {"x": {"brief": {"question": "q", "options": [{"label": "A", "values": [], "recommendation": True}]}}}}, by="D")
    with pytest.raises(ValueError, match="format"):
        store.update(tmp_path, "2026-10-21", {"basics": {"format": "zoom"}}, by="D")
    with pytest.raises(ValueError, match="kind"):
        store.update(tmp_path, "2026-10-21", {"items": {"x": {"kind": "report"}}}, by="D")
    with pytest.raises(ValueError, match="minutes"):
        store.update(tmp_path, "2026-10-21", {"items": {"x": {"allot": -5}}}, by="D")
    with pytest.raises(ValueError, match="key"):
        store.update(tmp_path, "2026-10-21", {"basics": {"date": "2026-11-18", "start": "18:30"}}, by="D")
    with pytest.raises(ValueError, match="not part of the plan"):
        store.update(tmp_path, "2026-10-21", {"approved": True}, by="D")
    with pytest.raises(ValueError, match="nothing to change"):
        store.update(tmp_path, "2026-10-21", {"basics": {"start": ""}}, by="D")
    assert not (tmp_path / "meetings").exists()


ITEM = {"id": "reserve-loan", "title": "Reserve loan not restored", "summary": "s", "ask": "Decide whether to restore the loan", "category": "reserves",
        "priority": "high", "status": "proposed", "authority": "CIV 5515(d)", "evidence": ["jason reserves --transfers"], "session": None,
        "special_notice": "", "due": None, "opened": "2026-09-01", "owner": "", "meeting": "", "notes": "", "source": "jason", "history": [], "agendaSession": "open session"}
EXEC = {**ITEM, "id": "payment-plan-7", "title": "Payment plan, unit 7", "ask": "Decide the plan", "category": "collections", "evidence": [], "agendaSession": "executive session"}
CONFLICT = {**ITEM, "id": "paint-contract", "title": "Painting contract", "ask": "Approve the contract", "interested": ["A. Director"]}


def _meeting(items, today="2026-10-03", packet=""):
    return {"found": True, "date": "2026-10-21", "today": today, "noticeBy": "2026-10-17", "executiveNoticeBy": "2026-10-19", "directors": ["A. Director"],
            "decisions": [], "items": items, "openCount": 1, "executiveCount": 0, "agendaMarkdown": "# Agenda", "packetMarkdown": packet, "minutesTemplate": "", "notes": [],
            "commands": {"agendaDoc": "jason board --agenda <id> --date 2026-10-21 --doc --yes", "packetDoc": "jason board --packet --date 2026-10-21 --doc --yes",
                         "minutesDraft": "jason board --minutes 2026-10-21", "notice": "jason board --set <item id> --status \"on agenda\" --meeting 2026-10-21"},
            "caveats": ["No action may be taken on an item not on the noticed agenda (CIV 4930)."]}


@pytest.fixture
def fakes(tmp_path, monkeypatch):
    """A fake county module for the data root and a fake meeting loader whose items each test sets."""
    saved = {k: sys.modules.get(k) for k in ("jason.mcp", "jason.mcp.county")}
    county = types.ModuleType("jason.mcp.county")
    county._data_dir = lambda _arg=None: tmp_path
    pkg = types.ModuleType("jason.mcp")
    pkg.__path__ = []
    pkg.county = county
    sys.modules["jason.mcp"], sys.modules["jason.mcp.county"] = pkg, county
    import jason.web.sources as sources

    holder = {"meeting": _meeting([ITEM])}
    monkeypatch.setattr(sources, "meeting", lambda args: holder["meeting"])
    try:
        yield holder
    finally:
        for k, v in saved.items():
            if v is None:
                sys.modules.pop(k, None)
            else:
                sys.modules[k] = v


def test_loader_computes_readiness_from_the_plan_and_the_meeting(fakes, tmp_path):
    from jason.web.extra.agenda_plan import agenda_plan, write

    fakes["meeting"] = _meeting([ITEM, EXEC, CONFLICT])
    out = agenda_plan({})
    assert out["steps"] == ["Meeting", "Ready to act", "Order and motions", "Notice"]
    by_id = {c["id"]: c for c in out["candidates"]}
    loan = by_id["reserve-loan"]
    assert loan["readiness"]["ready"] is False and loan["kind"] == "action" and loan["include"] is False
    labels = {c["label"]: c["ok"] for c in loan["readiness"]["checks"]}
    assert labels["Motion drafted"] is False and labels["Supporting documents"] is True
    assert labels["Notice can still be given by 2026-10-17 (CIV 4920)"] is True
    assert "Executive session marked (CIV 4935)" not in labels and not any("Conflict" in k for k in labels)
    assert loan["suggestion"].startswith("no motion drafted yet")
    plan = by_id["payment-plan-7"]
    assert plan["kind"] == "executive" and plan["session"] == "executive session"
    exec_labels = {c["label"]: c["ok"] for c in plan["readiness"]["checks"]}
    assert exec_labels["Executive session marked (CIV 4935)"] is True and exec_labels["Supporting documents"] is False
    assert exec_labels["Notice can still be given by 2026-10-19 (CIV 4920)"] is True
    conflict = {c["label"]: c for c in by_id["paint-contract"]["readiness"]["checks"]}
    assert conflict["Conflict disclosure recorded (Corp. Code 7233; CIV 5350)"]["ok"] is False
    assert out["candidates"][-1]["id"] == "payment-plan-7", "executive matters sort after open ones"
    assert out["zoom"]["command"] is None and "no command" in out["zoom"]["note"]
    assert out["commands"]["onAgenda"] == [] and out["notice"]["by"] == "2026-10-17"
    required = {r["label"]: r for r in out["notice"]["required"]}
    assert required["Time and place of the meeting (CIV 4920)"]["ready"] is False
    assert required["The agenda: every item the board will discuss or act on (CIV 4930)"]["ready"] is False

    out = write("2026-10-21", {"by": "D. Okafor", "basics": {"start": "18:30", "format": "teleconference", "join": "https://zoom.us/j/1", "dialIn": "+1 555 0100", "help": "manager, 555-0100, help@example.org"},
                               "items": {"reserve-loan": {"include": True, "motion": "Move to restore the loan by 2026-10-31.", "packet": [{"id": "f1", "name": "Resolution", "kind": "doc", "url": ""}]},
                                         "payment-plan-7": {"include": True, "kind": "action"}}})
    by_id = {c["id"]: c for c in out["candidates"]}
    assert by_id["reserve-loan"]["readiness"]["ready"] is True and by_id["reserve-loan"]["suggestion"] == ""
    exec_labels = {c["label"]: c for c in by_id["payment-plan-7"]["readiness"]["checks"]}
    assert exec_labels["Executive session marked (CIV 4935)"]["ok"] is False and "CIV 4935" in exec_labels["Executive session marked (CIV 4935)"]["why"]
    assert out["commands"]["onAgenda"] == ['jason board --set reserve-loan --status "on agenda" --meeting 2026-10-21', 'jason board --set payment-plan-7 --status "on agenda" --meeting 2026-10-21']
    required = {r["label"]: r for r in out["notice"]["required"]}
    assert required["Time and place of the meeting (CIV 4920)"]["ready"] is True
    assert required["Clear instructions for joining (CIV 4926(a)(1))"]["ready"] is True
    assert required["A telephone option for everyone entitled to take part (CIV 4926(a)(4))"]["ready"] is True
    assert required["Phone and email of a person who can help before and during the meeting (CIV 4926(a)(1))"]["ready"] is True
    assert required["Executive session matters described generally (CIV 4935)"]["ready"] is True
    assert required["Delivered by 2026-10-17, four days ahead (CIV 4920)"]["ready"] is True
    assert "A physical location where members may attend, with a director or designee present (CIV 4090(b))" not in required
    assert out["history"][-1].startswith(out["updated"][:10]) and "D. Okafor" in out["history"][-1]
    assert any("CIV 4926(a)(3)" in r for r in out["rules"])
    assert (tmp_path / "meetings" / "plan-2026-10-21.json").is_file()


def test_loader_notice_passed_and_packet_motion(fakes):
    from jason.web.extra.agenda_plan import agenda_plan

    packet = "# Board packet\n\n## 1. Reserve loan not restored\n\n**Background.** s\n\n**Draft motion.** Move to restore $12,500.00 by 2026-10-31 (CIV 5515).\n\n## 2. Other\n\n**Draft motion.** Move that the board do the thing\n"
    fakes["meeting"] = _meeting([ITEM, {**ITEM, "id": "other", "title": "Other", "ask": "Do the thing", "evidence": []}], today="2026-10-18", packet=packet)
    out = agenda_plan({})
    by_id = {c["id"]: c for c in out["candidates"]}
    assert by_id["reserve-loan"]["motion"].startswith("Move to restore") and {c["label"]: c["ok"] for c in by_id["reserve-loan"]["readiness"]["checks"]}["Motion drafted"] is True
    assert {c["label"]: c["ok"] for c in by_id["other"]["readiness"]["checks"]}["Motion drafted"] is False, "the generic frame is not a drafted motion"
    notice = next(c for c in by_id["reserve-loan"]["readiness"]["checks"] if c["label"].startswith("Notice"))
    assert notice["ok"] is False and "2026-10-17" in notice["why"]
    assert by_id["reserve-loan"]["suggestion"].startswith("notice was due")
    assert {r["label"]: r["ready"] for r in out["notice"]["required"]}["Delivered by 2026-10-17, four days ahead (CIV 4920)"] is False


def test_writer_refuses_a_recommendation_and_passes_not_found_through(fakes):
    from jason.web.extra.agenda_plan import agenda_plan, write

    with pytest.raises(ValueError, match="recommend"):
        write("2026-10-21", {"by": "D", "brief": {"reserve-loan": {"question": "q", "criteria": [], "options": [], "facts": [], "recommended": 0}}})
    with pytest.raises(ValueError, match="by"):
        write("2026-10-21", {"items": {"reserve-loan": {"include": True}}})
    fakes["meeting"] = {"found": False, "note": "date is YYYY-MM-DD"}
    assert agenda_plan({"date": "x"}) == {"found": False, "note": "date is YYYY-MM-DD"}
