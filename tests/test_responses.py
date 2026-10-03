import json
import sqlite3
from datetime import date
from types import SimpleNamespace

import pytest

from jason.community.responses import ClockSource, ResponseKind, ResponseRule, classify
from jason.tasks import responses as task


@pytest.mark.parametrize("form,text,kind", [
    ("Architectural Request", "Install solar panels on my roof", ResponseKind.SOLAR),
    ("Architectural Request", "New front door color", ResponseKind.ARCHITECTURAL),
    ("General Request", "I would like to inspect copies of the board minutes and the budget", ResponseKind.RECORDS),
    ("General Request", "Please send the resale disclosure package for our sale", ResponseKind.RESALE),
    ("General Request", "We are in escrow; the appraiser needs the HOA phone number", ResponseKind.QUESTION),
    ("Maintenance Request", "Selling my home, in escrow; the inspection found a loose gutter", ResponseKind.MAINTENANCE),
    ("General Request", "Requesting a payment plan for my balance", ResponseKind.PAYMENT_PLAN),
    ("General Request", "Noise complaint about the unit above", ResponseKind.COMPLAINT),
    ("Other Form", "hello", ResponseKind.OTHER),
    ("", "Solar question 2", ResponseKind.QUESTION),                      # a mention, not an application
    ("", "Request to install an EV charger in my garage", ResponseKind.EV_CHARGER),
    ("", "Re: Courtesy Notice: Noise and Parking Violations", ResponseKind.OTHER),   # a reply to our own notice
    ("", "Offer to meet and confer", ResponseKind.DISPUTE),
    # Something to fix, on the general form: maintenance; whose job it is: a question.
    ("General Request", "The side gate is rusty and will not latch", ResponseKind.MAINTENANCE),
    ("General Request", "Porch light repair, please", ResponseKind.MAINTENANCE),
    ("General Request", "Is the association responsible for the weeds on my patio?", ResponseKind.QUESTION),
    # Conduct reported is a complaint; asking not to be cited is not.
    ("General Request", "A neighbor lets their dog defecate on the walkway", ResponseKind.COMPLAINT),
    ("General Request", "The city missed my bin; please do not mark this as a violation", ResponseKind.QUESTION),
    ("", "Re: Violation Report", ResponseKind.OTHER),
    ("", "Notice of Intent to Rent - 123 Main St", ResponseKind.RENTAL),
    ("", "Copy of Owners Manual / Rules and Regulations", ResponseKind.RECORDS),
    ("", "Permission to paint my front door", ResponseKind.ARCHITECTURAL),
])
def test_classify(form, text, kind):
    assert classify(form, text)[0] is kind


@pytest.mark.parametrize("subject,topics,kind", [
    ("Roof Leak", [], ResponseKind.MAINTENANCE),
    ("Patio", ["maintenance and repairs"], ResponseKind.MAINTENANCE),        # the topic's value, not a bare word
    ("Patio", ["utilities"], ResponseKind.OTHER),                             # the meter reader is not a repair
    ("Re: Notice of Temporary Water Shut-Off - Scheduled Maintenance", ["maintenance and repairs"], ResponseKind.OTHER),
    ("Re: Scheduled Gutter Repairs - Building 9", [], ResponseKind.OTHER),     # our own notice
    ("Landscape Contracts", ["landscaping"], ResponseKind.OTHER),             # business, not a repair
    ("Notice of Intent to Rent", [], ResponseKind.RENTAL),                    # a named kind outranks "notice"
])
def test_classify_email(subject, topics, kind):
    from jason.community.responses import KIND_RULES

    assert task.classify_email(subject, topics, KIND_RULES)[0] is kind


def test_scores_give_precision_and_recall_per_kind():
    from jason.tasks.request_kinds import scores

    s = scores([("complaint", "complaint"), ("complaint", "question"), ("question", "question"), ("other", "question")])
    assert s["complaint"] == {"support": 2, "predicted": 1, "correct": 1, "precision": 1.0, "recall": 0.5}
    assert s["question"]["precision"] == round(1 / 3, 3) and s["question"]["recall"] == 1.0
    assert s["other"]["precision"] is None and s["other"]["recall"] == 0.0


def test_clocks_from_the_statute_the_documents_and_a_policy():
    records = ResponseRule(ResponseKind.RECORDS, ClockSource.STATUTE, notice="records-current-year", authority="CIV 5210")
    due, words = task.due_day(records, date(2026, 10, 2))            # a Friday
    assert due == date(2026, 10, 16) and "10 business days" in words  # ten weekdays later
    rental = ResponseRule(ResponseKind.RENTAL, ClockSource.DOCUMENTS, days=30, authority="CC&Rs 1.1")
    assert task.due_day(rental, date(2026, 10, 2))[0] == date(2026, 11, 1)
    policy = ResponseRule(ResponseKind.MAINTENANCE, ClockSource.POLICY, days=2, business_days=True)
    assert task.due_day(policy, date(2026, 10, 2))[0] == date(2026, 10, 6)


def test_standing():
    assert task._standing(date(2026, 10, 10), date(2026, 10, 9), date(2026, 10, 20)) == "answered on time"
    assert task._standing(date(2026, 10, 10), date(2026, 10, 12), date(2026, 10, 20)) == "answered late (2 days)"
    assert task._standing(date(2026, 10, 10), None, date(2026, 10, 12)) == "OVERDUE (2 days)"
    assert task._standing(date(2026, 10, 10), None, date(2026, 10, 7)) == "due soon"


def _db(tmp_path, rows):
    with sqlite3.connect(tmp_path / "payhoa.db") as c:
        c.execute("CREATE TABLE units (id INTEGER, label TEXT)")
        c.execute("INSERT INTO units VALUES (1, '100 EXAMPLE WALK')")
        c.execute("CREATE TABLE requests (id INTEGER, form_name TEXT, unit_id INTEGER, status TEXT, created_at TEXT, raw_json TEXT)")
        for rid, form, status, created, title, comments, completed in rows:
            raw = {"answers": [{"question": {"label": "Title"}, "answer": title}, {"question": {"label": "Message"}, "answer": ""}],
                   "comments": comments, "completionDate": completed, "updatedAt": completed or created}
            c.execute("INSERT INTO requests VALUES (?,?,?,?,?,?)", (rid, form, 1, status, created, json.dumps(raw)))


def test_an_acknowledgment_promises_a_date_only_where_the_law_or_documents_set_one():
    received = date(2026, 10, 2)
    records = ResponseRule(ResponseKind.RECORDS, ClockSource.STATUTE, notice="records-current-year", authority="CIV 5210")
    due, clock = task.due_day(records, received)
    h = task.Handled({"id": 1}, ResponseKind.RECORDS, "", records, received, due, clock, None, None, None, None, "open")
    text = task.acknowledgment(h, SimpleNamespace(name="Example Association"))
    assert "October 2, 2026" in text and "Under CIV 5210" in text and "October 16, 2026" in text
    assert text.endswith("- Example Association")
    policy = ResponseRule(ResponseKind.MAINTENANCE, ClockSource.POLICY, days=10, business_days=True)
    h = task.Handled({"id": 2}, ResponseKind.MAINTENANCE, "", policy, received, date(2026, 10, 16), "", None, None, None,
                     None, "open")
    assert "October 16" not in task.acknowledgment(h, SimpleNamespace(name="X"))


def test_handle_judges_the_first_response_not_the_closing(tmp_path):
    _db(tmp_path, [
        (1, "Maintenance Request", "complete", "2026-09-01T17:00:00Z", "Leak",
         [{"createdAt": "2026-09-03T17:00:00Z", "isAdmin": True}], "2026-10-30T17:00:00Z"),
        (2, "General Request", "pending", "2026-09-01T17:00:00Z", "Inspect copies of the minutes", [], None),
    ])
    community = SimpleNamespace(topic_rules=lambda: (), response_rules=lambda: (
        ResponseRule(ResponseKind.MAINTENANCE, ClockSource.POLICY, days=10, business_days=True, assignment="maintenance",
                     acknowledge_days=2),))
    found = {h.request["id"]: h for h in task.handle(community, tmp_path, today=date(2026, 10, 2))}
    assert found[1].answered == date(2026, 9, 3) and found[1].closed == date(2026, 10, 30)
    assert found[1].standing == "answered on time"
    assert found[2].kind is ResponseKind.RECORDS and found[2].standing.startswith("OVERDUE")
    assert task.summary(list(found.values()))["onTime"] == {"maintenance request": 1}


def test_payhoa_fields_due_date_and_tags_beside_the_clock(tmp_path):
    _db(tmp_path, [(1, "Maintenance Request", "pending", "2026-09-24T17:00:00Z", "Gutter came loose", [], None)])
    with sqlite3.connect(tmp_path / "payhoa.db") as c:
        raw = json.loads(c.execute("SELECT raw_json FROM requests WHERE id = 1").fetchone()[0])
        raw.update({"dueDate": "2026-10-01", "aiAnalysis": None, "assigneeMembershipId": None, "approvals": [],
                    "tags": [{"tag": "Gutter"}, {"tag": "Association Responsibility"}]})
        c.execute("UPDATE requests SET raw_json = ? WHERE id = 1", (json.dumps(raw),))
    assert task.payhoa_fields(tmp_path) == {1: {"dueDate": "2026-10-01", "tags": ["Gutter", "Association Responsibility"]}}
    community = SimpleNamespace(topic_rules=lambda: (), response_rules=lambda: (
        ResponseRule(ResponseKind.MAINTENANCE, ClockSource.POLICY, days=10, business_days=True),))
    h = task.handle(community, tmp_path, today=date(2026, 9, 28))[0]
    assert h.kind is ResponseKind.MAINTENANCE and h.payhoa_due == date(2026, 10, 1) and h.due == date(2026, 10, 8)
    assert h.hints == ('PayHOA tag "Gutter" (agrees)', 'PayHOA tag "Association Responsibility"')
    text = "\n".join(task.lines([h]))
    assert "due 2026-10-01 as set in PayHOA (earlier than jason's clock)" in text


def test_payhoa_ai_analysis_is_a_lead_never_the_kind():
    from jason.community.responses import KIND_RULES

    hints = task.payhoa_hints({"aiAnalysis": "The owner reports a roof leak"}, ResponseKind.QUESTION, KIND_RULES)
    assert hints == ("PayHOA's AI analysis reads as maintenance request (a lead; jason's kind stands)",)


def test_a_reply_draft_is_filed_in_its_thread_and_keeps_no_address(tmp_path):
    received = date(2026, 9, 1)
    rule = ResponseRule(ResponseKind.MAINTENANCE, ClockSource.POLICY, days=10, business_days=True)
    h = task.Handled({"id": "email:abc", "threadId": "abc123", "title": "Re: Re: Roof leak", "link": "L"},
                     ResponseKind.MAINTENANCE, "", rule, received, date(2026, 9, 15), "", None, None, None, None, "open")
    plan = task.reply_plan(h, SimpleNamespace(name="Example Association"))
    assert plan["subject"] == "Re: Roof leak" and plan["threadId"] == "abc123"

    class Gmail:
        def get_metadata(self, message_id, headers=()):
            assert message_id == "m2"
            return {"headers": {"From": "Group <group@example.org>", "X-Original-From": "Owner <owner@example.com>",
                                "Message-ID": "<m2@example.com>", "References": "<m1@example.com>"}}

    class Drafts:
        made = []

        def create(self, draft):
            self.made.append(draft)
            return {"id": "d1"}

    messages = [{"messageId": "m1", "direction": "in", "at": "1"}, {"messageId": "m2", "direction": "in", "at": "2"},
                {"messageId": "m3", "direction": "out", "at": "0"}]
    drafts = Drafts()
    out = task.make_reply(plan, Gmail(), drafts, tmp_path, messages=sorted(messages, key=lambda m: m["at"]))
    draft = drafts.made[0]
    assert out == {"draftId": "d1", "threadId": "abc123", "to": True, "threaded": True}
    assert draft.to == ("owner@example.com",) and draft.thread_id == "abc123"
    assert draft.in_reply_to == "<m2@example.com>" and draft.references == "<m1@example.com> <m2@example.com>"
    email = draft.email()
    assert email["In-Reply-To"] == "<m2@example.com>" and "Example Association" in email.get_content()
    saved = (tmp_path / task.REPLY_DRAFTS).read_text(encoding="utf-8")
    assert "d1" in saved and "@" not in saved
    assert task.drafted(tmp_path)["email:abc"]["draftId"] == "d1"
    with pytest.raises(ValueError):
        task.reply_plan(task.Handled({"id": 7}, ResponseKind.QUESTION, "", None, None, None, "", None, None, None, None,
                                     "open"), SimpleNamespace(name="X"))


def test_gmail_drafts_create_files_a_reply_in_its_thread():
    import httpx

    from jason.google.gmail_drafts import DraftMessage, GmailDrafts

    seen = []

    def handler(request):
        seen.append(json.loads(request.content))
        return httpx.Response(200, json={"id": "d9"})

    client = GmailDrafts("tok", http=httpx.Client(transport=httpx.MockTransport(handler)))
    client.create(DraftMessage(to=(), subject="Re: x", text="hi", thread_id="t1", in_reply_to="<a@b>"))
    client.create(DraftMessage(to=("a@example.org",), subject="x", text="hi"))
    assert seen[0]["message"]["threadId"] == "t1" and "threadId" not in seen[1]["message"]


def test_catalog_matches_skip_the_words_every_name_carries():
    from jason.tasks.response_sources import catalog_matches

    catalog = [("Request to Meet and Confer.pdf", "Email Attachments/Request to Meet and Confer.pdf"),
               ("Board Meeting Agenda.docx", "Resources/Board Meeting Agenda.docx"),
               ("100 Example Walk.pdf", "Resident Registration Forms/100 Example Walk.pdf")]
    found = catalog_matches("Offer to meet and confer, from 102 Example Walk, to the board", catalog,
                            common={"example", "walk"})
    assert [d["name"] for d in found] == ["Request to Meet and Confer.pdf"]


def test_measure_scores_the_payhoa_requests_against_the_gold_set(tmp_path):
    from jason.tasks.request_kinds import measure

    _db(tmp_path, [(1, "General Request", "pending", "2026-09-01T17:00:00Z", "The porch light is out", [], None),
                   (2, "General Request", "pending", "2026-09-01T17:00:00Z", "How many parking permits?", [], None)])
    gold = tmp_path / "gold.json"
    gold.write_text(json.dumps({"labelled": "2026-10-02", "payhoa": {"1": {"kind": "maintenance request"},
                                                                     "2": {"kind": "complaint"}}}), encoding="utf-8")
    result = measure(tmp_path, SimpleNamespace(topic_rules=lambda: ()), gold)
    assert result["payhoa"]["n"] == 2 and result["payhoa"]["accuracy"] == 0.5
    assert result["payhoa"]["kinds"]["maintenance request"]["recall"] == 1.0
    assert [m["id"] for m in result["misses"]] == ["2"]
