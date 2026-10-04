"""The board's action items, the meeting schedule, and the drafted agenda and minutes."""

from __future__ import annotations

from datetime import date

from jason.community import mystique
from jason.community.board_items import BoardItem, ItemCategory, ItemStatus, Priority, Session, agenda_session
from jason.community.legal_cases import settled_lines
from jason.tasks.board_items import load, notice_date, set_fields, to_rows, upsert
from jason.tasks.meeting_agenda import draft, minutes_template, parse_doc


def _item(item_id: str, **kw) -> BoardItem:
    base = dict(title="A matter", summary="What the records show.", ask="Decide it.", category=ItemCategory.FINANCE)
    base.update(kw)
    return BoardItem(item_id, **base)


def test_upsert_keeps_the_boards_fields(tmp_path):
    upsert(tmp_path, [_item("a", priority=Priority.HIGH)], today=date(2026, 9, 29))
    set_fields(tmp_path, "a", status="proposed", owner="Treasurer", today=date(2026, 9, 30))
    result = upsert(tmp_path, [_item("a", summary="Updated.", priority=Priority.HIGH), _item("b")], today=date(2026, 10, 1))
    items = {i.id: i for i in load(tmp_path)}
    assert result["added"] == 1 and items["a"].summary == "Updated." and items["a"].status is ItemStatus.PROPOSED
    assert items["a"].owner == "Treasurer" and items["a"].opened == date(2026, 9, 29) and len(items["a"].history) == 3


def test_sessions_and_notice():
    assert agenda_session(_item("x", category=ItemCategory.COLLECTIONS)) is Session.EXECUTIVE
    assert agenda_session(_item("y", category=ItemCategory.LEGAL)) is Session.OPEN
    assert agenda_session(_item("z", category=ItemCategory.LEGAL, session=Session.EXECUTIVE)) is Session.EXECUTIVE
    assert notice_date(date(2026, 10, 20)) == date(2026, 10, 16) and notice_date(date(2026, 10, 20), executive_only=True) == date(2026, 10, 18)
    assert to_rows([_item("a")])[1][0] == "a"


def test_the_schedule_is_the_third_tuesday():
    s = mystique().meeting_schedule()
    assert s.day_in(2026, 10) == date(2026, 10, 20) and s.day_in(2026, 11) == date(2026, 11, 17)
    assert s.next_meeting(date(2026, 9, 29), monthly=True) == date(2026, 10, 20)
    assert s.next_meeting(date(2026, 10, 21)) == date(2027, 1, 19)   # the resolution's regular months: January, April, July, October


def _doc(paragraphs):
    def para(text, style="HEADING_4", bullet=True):
        p = {"paragraphStyle": {"namedStyleType": style}, "elements": [{"textRun": {"content": text + "\n"}}]}
        if bullet:
            p["bullet"] = {"listId": "x"}
        return {"paragraph": p}

    content = [{"table": {"tableRows": [{"tableCells": [{"content": [{"paragraph": {"elements": [
        {"textRun": {"content": "To be held on: "}}, {"dateElement": {"dateElementProperties": {"displayText": "Sep 15, 2026 7:00 PM PDT"}}},
        {"textRun": {"content": " via Zoom (555) 000-0000 Meeting ID: 000 0000 0000"}}]}}]}]}]}}]
    content += [para(*p) if isinstance(p, tuple) else para(p) for p in paragraphs]
    return {"title": "Agenda for 9/15/26", "tabs": [{"documentTab": {"body": {"content": content}}}]}


def test_the_draft_carries_the_last_agenda_forward_and_adds_the_law():
    previous = parse_doc(_doc(["Call to Order", "Approval of minutes of previous meeting(s)", "Treasurer's Report", "Proposals",
                               ("Paving", "HEADING_5"), "Open Forum - 2 minutes per member", "Time and Place of next Regular Meeting",
                               "Adjourn to Executive Session", ("Legal Matters", "HEADING_5"), ("Decorum Rules", "HEADING_4", False),
                               ("No recording.", "NORMAL_TEXT", False)]))
    assert previous.header.startswith("To be held on:") and previous.closing == ["Decorum Rules", "No recording."]
    items = [_item("loan", title="Reserve loan", status=ItemStatus.PROPOSED, category=ItemCategory.RESERVES, special_notice="CIV 5515(b)"),
             _item("suit", title="Lawsuit", status=ItemStatus.PROPOSED, category=ItemCategory.LEGAL, session=Session.EXECUTIVE),
             _item("later", title="Not yet", status=ItemStatus.OPEN)]
    lines = draft(previous, items, date(2026, 11, 17), mystique().meeting_schedule(), previous_meeting=date(2026, 10, 20))
    text = "\n".join(lines)
    assert "via Zoom (555) 000-0000" in text and "Tuesday, November 17, 2026" in text and "4926(a)(3)" in text
    assert "Friday, November 13" in text and "physical location must be open" in text      # the annual meeting, CIV 4926(b)
    assert "special meeting" in text                                                       # November is not a regular month
    assert "See: ==[Minutes of 10/20/26]==" in text and "Paving ==keep or drop==" in text
    assert text.index("New Business") < text.index("Reserve loan") < text.index("Open Forum") < text.index("Executive Session")
    assert "Not yet" not in text and "Notice: CIV 5515(b)" in text and "4935(e)" in text
    # The executive session is noticed by its general nature: the lawsuit falls under the last agenda's Legal Matters.
    assert "Lawsuit" not in text and text.count("Legal Matters") == 1
    from jason.tasks.meeting_agenda import agenda_values

    previous.links = ["https://us02web.zoom.us/j/81392024127?pwd=x"]
    values = agenda_values(previous, date(2026, 10, 20), mystique().meeting_schedule())
    assert values["ZOOM_PHONE"] == "(555) 000-0000" and values["ZOOM_MEETING_ID"] == "000 0000 0000"
    assert values["MEETING_DATE"] == "Tuesday, October 20, 2026" and "TECH_CONTACT" not in values and values["ZOOM_LINK"].startswith("https")
    minutes = "\n".join(minutes_template(date(2026, 11, 17), ["A", "B", "C", "D"], lines, quorum=3))
    assert "Quorum: 3 directors" in minutes and "| A | B | C | D |" in minutes and "4950(a)" in minutes


def test_packet_citations_and_insertion_requests(tmp_path):
    from jason.tasks.board_packet import citations
    from jason.tasks.meeting_agenda import insertion_requests

    assert citations("CIV 5515(d), (e)") == [("CIV 5515", "(d)(e)")]
    assert citations("CIV 5660, 5673; HSC 13195") == [("CIV 5660", ""), ("CIV 5673", ""), ("HSC 13195", "")]
    doc = {"tabs": [{"documentTab": {"body": {"content": [
        {"startIndex": 1, "paragraph": {"elements": [{"textRun": {"content": "Call to Order\n"}}]}},
        {"startIndex": 15, "paragraph": {"elements": [{"textRun": {"content": "Open Forum - 2 minutes per member\n"}}]}}]}}}]}
    item = _item("a", title="New item", ask="Decide it.", authority="CIV 4930")
    requests = insertion_requests(doc, [item], highlight=True)
    assert requests[0] == {"insertText": {"location": {"index": 15}, "text": "New item\nDecide it. (CIV 4930)\n"}}
    note = {"startIndex": 24, "endIndex": 24 + len("Decide it. (CIV 4930)") + 1}
    assert requests[1] == {"deleteParagraphBullets": {"range": note}} and requests[-1]["updateTextStyle"]["fields"] == "backgroundColor"
    assert insertion_requests(doc, [item], before="Nowhere") == []


def test_google_feature_status_reads_the_preview_mark():
    from jason.google.discovery import feature_status

    preview = {"revision": "1", "schemas": {"WriteControl": {"properties": {"writeMode": {
        "enum": ["WRITE_MODE_UNSPECIFIED", "EDIT", "SUGGEST"], "description": "How. [Developer Preview](x).",
        "enumDescriptions": ["", "", "Apply all updates as suggestions. [Developer Preview](x)."]}}}}}
    assert feature_status(preview)["features"]["suggest_mode"]["status"] == "preview"
    assert feature_status(preview)["features"]["anchored_comments"]["status"] == "absent"
    ga = {"schemas": {"WriteControl": {"properties": {"writeMode": {"enum": ["EDIT", "SUGGEST"], "description": "How.",
                                                                     "enumDescriptions": ["", "Apply all updates as suggestions."]}}},
                      "InsertCommentRequest": {"description": "Inserts a CommentThread into the document."}}}
    status = feature_status(ga)["features"]
    assert status["suggest_mode"]["status"] == status["anchored_comments"]["status"] == "general availability"


def test_legal_cases_from_the_specification():
    m = mystique()
    cases = {c.key: c for c in m.legal_cases()}
    watt = cases["watt-construction-defects-2022"]
    # The settlement's figures are private facts; the tests read made-up ones (tests/fixtures/spec/mystique/cases.json).
    assert (watt.gross_cents, watt.net_cents, watt.opened) == (10000000, 6000000, date(2022, 7, 5))
    assert [d.statute for d in watt.open_duties] == ["CIV 6100(a)", "CIV 4525(a)(7)", "CIV 4177(b), 5565(b)(3)",
                                                     "CIV 941(a)"]   # 6150 never applied
    assert next(d for d in watt.duties if d.statute == "CIV 941(a)").due == date(2029, 2, 24)
    # The released items, priced from the settlement's exhibit; an unpriced item adds nothing.
    assert watt.settled_hard_cents == 300000 and "2.2" not in {i.section for i in watt.settled_items}
    lines = settled_lines(watt)
    assert "priced at $3,000 before markups, against $60,000.00 net received" in lines[-2]
    assert "Evidence Code 1119" in lines[-1]
    suit = cases["sacramento-26cv016125"]
    assert suit.case_number == "26CV016125" and suit.confidential and suit.board_item == "lawsuit-26cv016125"
    board = {i for i in ("lawsuit-26cv016125", "settlement-disclosure-6100")}
    assert {c.board_item for c in cases.values() if c.board_item} == board


class _FakeTasks:
    def __init__(self, tasks=()):
        self.items = [dict(t) for t in tasks]
        self.inserted, self.patched = [], []

    def task_list(self, title):
        return "L1"

    def tasks(self, list_id):
        return self.items

    def insert(self, list_id, body):
        self.inserted.append(body)
        self.items.append({"id": f"T{len(self.items)}", **body})
        return body

    def patch(self, list_id, task_id, body):
        self.patched.append((task_id, body))
        return body


def test_board_items_as_google_tasks(tmp_path):
    from jason.google.tasks import marker_of
    from jason.tasks.board_items import sync_tasks, task_body

    upsert(tmp_path, [_item("a", due=date(2029, 2, 24)), _item("b"), _item("c")], today=date(2026, 9, 29))
    set_fields(tmp_path, "c", status="closed", today=date(2026, 9, 29))
    body = task_body(load(tmp_path)[0], "SHEET")
    assert body["due"] == "2029-02-24T00:00:00.000Z" and marker_of(body) == "a" and "spreadsheets/d/SHEET" in body["notes"]
    fake = _FakeTasks()
    first = sync_tasks(fake, tmp_path, today=date(2026, 9, 29))
    assert first["created"] == 2 and {marker_of(t) for t in fake.inserted} == {"a", "b"}   # a closed item gets no new task
    # A person checks off b in Google Tasks: the item closes, with the change in its history; a stray task is reported.
    fake.items[1]["status"] = "completed"
    fake.items.append({"id": "X", "title": "old", "notes": "jason:gone"})
    second = sync_tasks(fake, tmp_path, today=date(2026, 9, 30))
    b = next(i for i in load(tmp_path) if i.id == "b")
    assert second["closedFromTasks"] == ["b"] and b.status is ItemStatus.CLOSED and "closed" in b.history[-1]
    assert second["unknown"] == ["gone"] and second["created"] == 0
    assert second["updated"] == 1 and "Status: closed" in fake.patched[-1][1]["notes"]   # b's notes follow its status


def test_the_notice_period_honors_a_longer_one_in_the_documents():
    from types import SimpleNamespace

    from jason.community.base import NoticePeriod
    from jason.tasks.board_items import notice_period

    meeting = date(2099, 3, 20)
    none = SimpleNamespace(board_notice_period=lambda: None)
    assert notice_period(community=none) == (4, "CIV 4920(a)") and notice_period(executive_only=True, community=none) == (2, "CIV 4920(b)(2)")
    longer = SimpleNamespace(board_notice_period=lambda: NoticePeriod(days=10, source="Bylaws 1.2"))
    assert notice_period(community=longer) == (10, "Bylaws 1.2; CIV 4920(b)(3)")
    assert notice_date(meeting, community=longer) == date(2099, 3, 10)
    # A documents' period does not reach a meeting held solely in executive session unless its provision says so (4920(b)(3)).
    assert notice_date(meeting, executive_only=True, community=longer) == date(2099, 3, 18)
    both = SimpleNamespace(board_notice_period=lambda: NoticePeriod(days=10, source="Bylaws 1.2", executive_days=5))
    assert notice_period(executive_only=True, community=both) == (5, "Bylaws 1.2; CIV 4920(b)(3)")
    # Shorter than the statute: the statute's floor stands.
    shorter = SimpleNamespace(board_notice_period=lambda: NoticePeriod(days=2, source="Bylaws 1.2"))
    assert notice_period(community=shorter) == (4, "CIV 4920(a)")
    # The fixture profile's documents say four days: the statute's period, with both sources shown.
    assert notice_period() == (4, f"CIV 4920(a); {mystique().board_notice_period().source}")
