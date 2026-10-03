import json
from datetime import date
from types import SimpleNamespace

import pytest

from jason.community.base import MeetingSchedule
from jason.community.schedule import Anchor, Assignment, Role, Trigger
from jason.community.schedule_evidence import RULES, EvidenceRule, EvidenceSource, Weight, rules_for
from jason.tasks import schedule as schedule_task
from jason.tasks import schedule_evidence as task

REVIEW = Assignment("review", "Monthly review", Role.TREASURER, ("CIV 5500", "CIV 5501"), Trigger.ANCHORED,
                    anchor=Anchor.BOARD_MEETING)
NOTICE = Assignment("notice", "Meeting notice", Role.SECRETARY, ("notice:board-meeting",), Trigger.ANCHORED,
                    anchor=Anchor.BOARD_MEETING, offset_days=-4)
BUDGET = Assignment("budget", "Budget report", Role.TREASURER, ("CIV 5300",), Trigger.ANCHORED,
                    anchor=Anchor.FISCAL_YEAR_END, offset_days=-30)
TAXES = Assignment("taxes", "Taxes", Role.TREASURER, ("obligation:Property tax",), Trigger.EVENT, handled_by="x")
LOCAL = Assignment("local", "A document's own duty", Role.BOARD, ("bylaws#9",), Trigger.ANCHORED,
                   anchor=Anchor.BOARD_MEETING)


def _community(*rows, rules=()):
    # The board meets on the third Tuesday: 2026-01-20, 2026-02-17, 2026-03-17.
    return SimpleNamespace(assignments=lambda: rows, evidence_rules=lambda: rules, hearing_policy=lambda: None,
                           meeting_schedule=lambda: MeetingSchedule(1, 3, "7:00 pm", "Zoom"),
                           fiscal_year_end=lambda: (12, 31), obligations=lambda: ())


def _minutes(data, doc_id, day, name, text, kind="minutes", confidential=False):
    (data / "library" / "text").mkdir(parents=True, exist_ok=True)
    (data / "library" / "text" / f"{doc_id}.txt").write_text(text, encoding="utf-8")
    store = data / "documents" / "readings.json"
    store.parent.mkdir(parents=True, exist_ok=True)
    rows = json.loads(store.read_text(encoding="utf-8"))["readings"] if store.is_file() else []
    rows.append({"id": doc_id, "name": name, "period": day, "kind": kind, "hasText": True,
                 "confidential": confidential})
    store.write_text(json.dumps({"readings": rows}), encoding="utf-8")


def _catalog(data, meetings):
    (data / "meetings").mkdir(parents=True, exist_ok=True)
    (data / "meetings" / "catalog.json").write_text(json.dumps({"meetings": meetings}), encoding="utf-8")


@pytest.fixture
def data(tmp_path):
    _minutes(tmp_path, "1", "2026-01-20", "Minutes of 1_20_26.pdf",
             "III. Treasurer's Report\nThe board ratified the treasurer's review of the bank reconciliations for "
             "December, under Civil Code 5501.\nIV. Adjourn")
    _minutes(tmp_path, "2", "2026-02-17", "Minutes of 2_17_26.pdf",
             "III. Treasurer’s Report See: Treasurer's Report - 2026-01_Redacted.pdf\nIV. Landscaping")
    _minutes(tmp_path, "3", "2026-01", "Treasurer's Report - 2026-01_Redacted.pdf",
             "Treasurer's Report - 2026-01\nBank Reconciliation: Operating Account\nBalance Sheet\n$1.00",
             kind="treasurer_report")
    _minutes(tmp_path, "4", "2026-03-17", "Executive session minutes 3_17_26.pdf",
             "The board reviewed the bank reconciliations.", confidential=True)
    _catalog(tmp_path, [
        {"date": "2026-01-20", "has": {"meeting notice": {"PayHOA communication": 1}}, "records": [
            {"kind": "meeting notice", "where": "PayHOA communication", "name": "Regular Meeting - Jan 20",
             "sent": "2026-01-15T18:00:00Z", "note": "100 recipients"}]},
        {"date": "2026-02-17", "has": {"meeting notice": {"PayHOA communication": 1}}, "records": [
            {"kind": "meeting notice", "where": "PayHOA communication", "name": "Regular Meeting - Feb 17",
             "sent": "2026-02-15T18:00:00Z"}]},
    ])
    return tmp_path


def test_a_rule_serves_what_an_assignment_covers_and_the_profile_comes_first():
    assert [r.key for r in rules_for(REVIEW)][:2] == ["financial-review-reconciliations", "financial-review-ratified"]
    assert {r.source for r in rules_for(TAXES)} == {EvidenceSource.PAYMENTS}
    assert rules_for(LOCAL) == []
    own = EvidenceRule("own", ("bylaws#9",), EvidenceSource.MINUTES_TEXT, words=(r"review",))
    assert rules_for(LOCAL, _community(rules=(own,))) == [own]
    first = EvidenceRule("financial-review-reconciliations", ("CIV 5500",), EvidenceSource.MINUTES_TEXT, words=("x",))
    served = rules_for(REVIEW, _community(rules=(first,)))
    assert served[0] is first and [r.key for r in served].count("financial-review-reconciliations") == 1
    assert all(r.covers for r in RULES)


def test_passages_quote_the_words_as_written_with_what_must_be_near():
    text = "Old business. The board ratified the review of the reconciliations. New business: ratify the contract."
    found = task.passages(text, [r"\bratif\w*"], [r"reconcil"])
    assert len(found) >= 1 and "ratified the review of the reconciliations" in found[0]
    assert task.passages("The board approved the mulch.", [r"\breconcil\w*"]) == []


def test_the_minutes_show_the_review_or_name_the_report_that_holds_it(data):
    c = _community(REVIEW)
    found = {p.due.isoformat(): p for p in task.propose(c, data, start=date(2026, 1, 1), end=date(2026, 3, 31))}
    jan, feb, mar = found["2026-01-20"], found["2026-02-17"], found["2026-03-17"]
    assert jan.standing == "proposed" and jan.done_on == date(2026, 1, 20)
    direct = [f for f in jan.findings if f.weight is Weight.DIRECT]
    assert "ratified the treasurer's review of the bank reconciliations" in direct[0].passage
    assert direct[0].file.startswith("Minutes of 1_20_26.pdf")
    assert feb.standing == "partial"
    report = next(f for f in feb.findings if f.source is EvidenceSource.MINUTES_REPORT)
    assert "Bank Reconciliation: Operating Account" in report.note and "2026-01" in report.note
    assert "Treasurer's Report - 2026-01_Redacted.pdf" in report.passage
    assert mar.standing == "none"                       # the only minutes that month are confidential: not read


def test_a_notice_sent_late_is_evidence_against(data):
    found = {p.due.isoformat(): p for p in task.propose(_community(NOTICE), data, start=date(2026, 1, 1),
                                                        end=date(2026, 2, 28))}
    assert found["2026-01-16"].standing == "proposed"
    assert "5 days before" in found["2026-01-16"].findings[0].note
    late = found["2026-02-13"]
    assert late.standing == "contrary" and late.findings[0].weight is Weight.AGAINST


def test_a_mailing_in_the_window_and_a_payment_for_an_obligation(data, monkeypatch):
    (data / "payhoa").mkdir()
    (data / "payhoa" / "communications.json").write_text(json.dumps({"notices": [
        {"subject": "2027 Annual Budget Report and Policy Statement", "sent": "2026-11-10T18:00:00Z"},
        {"subject": "Pool party", "sent": "2026-11-12T18:00:00Z"}]}), encoding="utf-8")
    budget = task.propose(_community(BUDGET), data, start=date(2026, 1, 1), end=date(2026, 12, 31))
    assert [(p.due.isoformat(), p.standing) for p in budget] == [("2026-12-01", "proposed")]
    assert "Annual Budget Report" in budget[0].findings[0].file

    rows = [{"name": "Property tax", "history": [
        {"deadline": "2025-12-10", "standing": "done", "evidence": [
            {"date": "2025-11-01", "amountCents": 12345, "payee": "County", "category": "Property Tax"}]},
        {"deadline": "2026-04-10", "standing": "no evidence", "evidence": []}]}]
    monkeypatch.setattr(task.Stores, "obligations", lambda self: rows)
    taxes = task.propose(_community(TAXES), data, start=date(2025, 1, 1), end=date(2026, 12, 31))
    assert [(p.due.isoformat(), p.standing) for p in taxes] == [("2025-12-10", "partial")]
    assert "$123.45" in taxes[0].findings[0].file


def test_nothing_is_recorded_until_a_person_confirms_one(data):
    c = _community(REVIEW)
    proposals = task.propose(c, data, start=date(2026, 1, 1), end=date(2026, 3, 31))
    assert schedule_task.completions(data) == []
    jan = task.find(proposals, "review", date(2026, 1, 20))
    row = task.record(data, jan, "A Treasurer")
    assert row["key"] == "review" and row["due"] == "2026-01-20" and row["done"] == "2026-01-20"
    assert "Minutes of 1_20_26.pdf" in row["evidence"] and row["by"] == "A Treasurer"
    again = task.find(task.propose(c, data, start=date(2026, 1, 1), end=date(2026, 3, 31)), "review",
                      date(2026, 1, 20))
    assert again.standing == "recorded"
    with pytest.raises(ValueError):
        task.record(data, task.find(proposals, "review", date(2026, 3, 17)), "A Treasurer")
    own = task.record(data, task.find(proposals, "review", date(2026, 3, 17)), "A Treasurer",
                      on=date(2026, 3, 20), evidence="reviewed by every director outside the meeting")
    assert own["done"] == "2026-03-20"


def test_the_store_and_the_summary(data):
    proposals = task.propose(_community(REVIEW, LOCAL), data, start=date(2026, 1, 1), end=date(2026, 3, 31))
    assert {p.assignment.key for p in proposals} == {"review"}
    assert task.summary(proposals)["review"] == {"occurrences": 3, "recorded": 0, "proposed": 1, "partial": 1,
                                                 "contrary": 0, "none": 1}
    assert task.unserved(_community(REVIEW, LOCAL)) == ["local"]
    path = task.write(data, proposals, start=date(2026, 1, 1), end=date(2026, 3, 31))
    stored = json.loads(path.read_text(encoding="utf-8"))
    assert stored["proposals"][0]["findings"][0]["weight"] == "direct"
    assert any("2026-01-20" in line for line in task.lines(proposals))


def test_the_command_is_registered():
    from jason.commands import MODULES

    assert "schedule_evidence" in MODULES
    import jason.commands.schedule_evidence as cmd

    assert callable(cmd.register)


def test_the_profile_rules_serve_its_own_sections():
    from jason.community import community
    from jason.community.schedule import assignments

    c = community()
    served = {a.key: [r.key for r in rules_for(a, c)] for a in assignments(c)}
    assert "financial-review-reconciliations" in served["monthly-financial-review"]
    assert served["officers-committees"]
