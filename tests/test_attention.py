import argparse
import json
import sqlite3
from datetime import date
from types import SimpleNamespace

from jason import api
from jason.community import community, intake
from jason.community.authority_order import Clarity, Conflict, ConflictStatus, Tier
from jason.community.deontic import Bearer, Deadline, DeadlineRelation, DocumentDuty, DutyKind
from jason.community.intake import Ask, AskKind, AskStatus
from jason.community.schedule import Assignment, Role, Trigger
from jason.tasks import attention, notice_ledger
from jason.tasks import document_duties as dd
from jason.tasks import schedule as schedule_task
from jason.tasks.attention import Urgency

ON = date(2026, 10, 2)
EMPTY = SimpleNamespace()


def _urgencies(section):
    """The lines' urgencies, the coverage check's noted line aside (the notice catalog is always there to own)."""
    return [i.urgency for i in section.ordered() if not i.text.endswith("a standing assignment owns")]


# --- The schedule -----------------------------------------------------------------------------------------------------

def _monthly(**kw):
    fields = dict(title="Monthly review", role=Role.TREASURER, covers=("bylaws#9.6",), trigger=Trigger.CADENCE,
                  every_months=1, day=15)
    fields.update(kw)
    return Assignment("monthly-review", **fields)


def test_the_schedule_with_nothing_assigned_is_quiet(tmp_path):
    s = attention.schedule_section(EMPTY, tmp_path, ON)
    assert _urgencies(s) == [] and s.available and "0 overdue" in s.summary
    # the coverage check still says what nobody owns: here, every notice the law requires
    assert s.counts["unassigned"] > 0 and s.items[0].command == "jason schedule --coverage"


def test_the_schedule_lists_overdue_and_due_soon_by_role_and_a_recorded_completion_clears_one(tmp_path):
    c = SimpleNamespace(assignments=lambda: (_monthly(),))
    s = attention.schedule_section(c, tmp_path, ON)
    # September 15 passed (a duty the bylaws set: legal); October 15 is within two weeks
    assert _urgencies(s) == [Urgency.LEGAL, Urgency.SOON]
    assert s.counts["byRole"] == {"treasurer": {"overdue": 1, "due soon": 1}}
    assert "17 days late" in s.ordered()[0].text and s.ordered()[0].command == "jason schedule --role treasurer"
    assert any("No completion is recorded" in n for n in s.notes)
    schedule_task.record_done(tmp_path, "monthly-review", date(2026, 9, 15), date(2026, 9, 15), "A Person", "minutes")
    assert _urgencies(attention.schedule_section(c, tmp_path, ON)) == [Urgency.SOON]


def test_an_assignment_on_a_policy_alone_is_overdue_not_legal(tmp_path):
    c = SimpleNamespace(assignments=lambda: (_monthly(covers=()),))
    assert _urgencies(attention.schedule_section(c, tmp_path, ON))[0] is Urgency.OVERDUE
    assert attention.cover_rank(("notice:board-meeting",)) == attention.STATUTE
    assert attention.cover_rank(("CIV 5500",)) == attention.STATUTE
    assert attention.cover_rank(("collection-policy",)) == attention.DOCUMENTS


# --- Members' requests ------------------------------------------------------------------------------------------------

def _requests(tmp_path, rows):
    with sqlite3.connect(tmp_path / "payhoa.db") as conn:
        conn.execute("CREATE TABLE units (id INTEGER, label TEXT)")
        conn.execute("INSERT INTO units VALUES (1, '100 EXAMPLE WALK')")
        conn.execute("CREATE TABLE requests (id INTEGER, form_name TEXT, unit_id INTEGER, status TEXT, created_at TEXT, "
                     "raw_json TEXT)")
        for rid, form, created, title in rows:
            raw = {"answers": [{"question": {"label": "Title"}, "answer": title},
                               {"question": {"label": "Message"}, "answer": ""}], "comments": [], "updatedAt": created}
            conn.execute("INSERT INTO requests VALUES (?,?,?,?,?,?)", (rid, form, 1, "pending", created, json.dumps(raw)))


def test_no_requests_stored_is_quiet(tmp_path):
    s = attention.requests_section(community(), tmp_path, ON)
    assert s.available and s.items == [] and s.counts["unanswered"] == 0


def test_a_statute_clock_passed_comes_first_and_the_packet_leaves_the_unit_out(tmp_path):
    _requests(tmp_path, [
        (1, "Maintenance Request", "2026-09-25T17:00:00Z", "A loose gutter"),
        (2, "General Request", "2026-09-01T17:00:00Z", "I would like to inspect copies of the board minutes"),
    ])
    s = attention.requests_section(community(), tmp_path, ON)
    first = s.ordered()[0]
    assert first.urgency is Urgency.LEGAL and first.text.startswith("#2 records request") and "CIV" in first.text
    assert "100 EXAMPLE WALK" in first.text
    assert s.counts["pastOrNear"]["statute"] == 1
    private = attention.requests_section(community(), tmp_path, ON, private=True)
    assert not any("EXAMPLE" in i.text for i in private.items)


# --- Intake questions -------------------------------------------------------------------------------------------------

def test_no_questions_parked(tmp_path):
    s = attention.intake_section(tmp_path)
    assert s.items == [] and "jason intake --scan" in s.summary


def test_open_questions_by_kind_with_the_likely_ones_apart(tmp_path):
    def ask(n, kind, **kw):
        return Ask(intake.ask_id(kind, f"ccrs#{n}", ""), kind, f"ccrs#{n}", "?", **kw)

    intake.save(tmp_path, [ask(1, AskKind.OCR_READING, likely=True), ask(2, AskKind.OCR_READING),
                           ask(3, AskKind.BEFORE_DIFFERS), ask(4, AskKind.CLASSIFY, status=AskStatus.ANSWERED),
                           ask(5, AskKind.DRIFT, status=AskStatus.STALE)])
    s = attention.intake_section(tmp_path)
    texts = [i.text for i in s.ordered()]
    assert texts[0] == "before differs: 1 open"                 # what an amendment changed, before OCR slips
    assert "ocr reading: 1 open" in texts and any(t.startswith("1 likely") for t in texts)
    assert any("1 answered and not yet applied" in t for t in texts)
    assert s.counts["open"] == 3 and "drift" not in s.counts["byKind"]


# --- Conflicts --------------------------------------------------------------------------------------------------------

def _conflict(key, status, **kw):
    fields = dict(provision="Bylaws 1.1", tier=Tier.BYLAWS, says="x", authority="CIV 1234", authority_tier=Tier.STATUTE,
                  since=None, extent="part", apply="as written", clarity=Clarity.PLAIN, status=status)
    fields.update(kw)
    return Conflict(key, **fields)


def test_no_conflicts_recorded():
    s = attention.conflicts_section(EMPTY)
    assert s.items == [] and s.summary == "No open conflicts recorded."


def test_open_conflicts_by_status_counsel_first_and_resolved_left_out():
    rows = (_conflict("a", ConflictStatus.NOTED), _conflict("b", ConflictStatus.COUNSEL, clarity=Clarity.UNCLEAR),
            _conflict("c", ConflictStatus.BOARD, board_item="item-1"),
            _conflict("d", ConflictStatus.RESOLVED, resolved_by="an amendment"))
    s = attention.conflicts_section(SimpleNamespace(conflicts=lambda: rows))
    assert s.counts["byStatus"] == {"counsel": 1, "board": 1, "noted": 1}
    texts = [i.text for i in s.ordered()]
    assert "with counsel" in texts[0] and "board item item-1" in texts[1] and "no one is acting" in texts[2]


# --- Notices ----------------------------------------------------------------------------------------------------------

def test_no_ledger_reads_nothing_and_creates_nothing(tmp_path):
    s = attention.notices_section(tmp_path)
    assert s.items == [] and not (tmp_path / "notices").exists()


def test_a_bounce_owes_a_resend_by_law_and_a_delivered_notice_owes_nothing(tmp_path):
    A = notice_ledger.Attempt
    notice_ledger.save(tmp_path, [
        A("owner-info-2099", 1, 1, "UNIT 1", "email", "b", "r1", status=notice_ledger.Delivery.BOUNCED),
        A("owner-info-2099", 2, 2, "UNIT 2", "email", "b", "r2", status=notice_ledger.Delivery.DELIVERED),
        A("annual-budget-2099", 1, 1, "UNIT 1", "email", "b", "r3", status=notice_ledger.Delivery.DELIVERED),
    ])
    s = attention.notices_section(tmp_path)
    assert [i.urgency for i in s.items] == [Urgency.LEGAL]
    item = s.items[0]
    assert item.text.startswith("owner-info-2099: 1 owed a resend by law") and "CIV 4041(e)" in item.text
    assert item.command == "jason notices owner-info-2099" and "UNIT" not in item.text
    assert s.counts["nothingOwed"] == 1


# --- Living documents -------------------------------------------------------------------------------------------------

def test_no_living_documents():
    s = attention.living_section(EMPTY, None, ON)
    assert s.items == [] and "No document" in s.summary


def test_a_living_document_not_built_and_one_with_a_failed_check_held_source_and_drift(tmp_path):
    folder = tmp_path / "living" / "decl"
    folder.mkdir(parents=True)
    (folder / "report.json").write_text(json.dumps({
        "key": "decl", "built": "2026-06-01", "held": ["first-amendment: not in the library"],
        "checks": [{"rule": "rental-cap", "section": "4.1", "expect": "twenty percent", "found": False},
                   {"rule": "lease-term", "section": "4.2", "expect": "six months", "found": True}],
        "drift": ["4.1: words differ"], "findings": ["before differs: 4.1: x", "correction stale: 1.1: y"]}),
        encoding="utf-8")
    docs = (SimpleNamespace(key="decl"), SimpleNamespace(key="bylaws"))
    s = attention.living_section(SimpleNamespace(living_documents=lambda: docs), tmp_path, ON)
    texts = {i.urgency: [] for i in s.items}
    for i in s.items:
        texts[i.urgency].append(i.text)
    assert texts[Urgency.SOON] == ['decl: the rule row rental-cap reads "twenty percent" in 4.1, and the current text '
                                   'does not: a person decides which is wrong']
    assert "bylaws: not built yet" in texts[Urgency.OPEN]
    assert any("1 sources held" in t for t in texts[Urgency.OPEN]) and any("differs in 1 places" in t
                                                                           for t in texts[Urgency.OPEN])
    assert any("last built 2026-06-01" in t for t in texts[Urgency.NOTED]) and s.counts["failedChecks"] == 1


# --- The documents' timed duties --------------------------------------------------------------------------------------

def _duty(section, bearer, quote, **kw):
    return DocumentDuty("bylaws", section, 0, len(quote), quote, DutyKind.DUTY, bearer, "shall", **kw)


def test_no_duties_read(tmp_path):
    s = attention.duties_section(EMPTY, tmp_path)
    assert s.items == [] and not (tmp_path / "duties").exists()


def test_a_timed_duty_nothing_tracks_and_one_an_assignment_owns(tmp_path):
    dd.save(tmp_path, "bylaws", [
        _duty("5.1", Bearer.BOARD, "The Board shall inspect the drains annually.", recurrence="annually",
              recurrence_months=12),
        _duty("5.2", Bearer.BOARD, "The Board shall audit the books annually.", recurrence="annually",
              recurrence_months=12),
        _duty("5.3", Bearer.OWNER, "Each Owner shall clean the vents within 30 days.",
              deadline=Deadline("within 30 days", DeadlineRelation.WITHIN, 30, "days")),
        _duty("5.4", Bearer.BOARD, "The Board shall keep the books."),                      # not timed
    ])
    owns = Assignment("audit", "Audit", Role.TREASURER, ("bylaws#5.2",), Trigger.CADENCE, every_months=12, month=6)
    s = attention.duties_section(SimpleNamespace(assignments=lambda: (owns,)), tmp_path)
    assert [i.text.split(" [")[0] for i in s.items if i.urgency is Urgency.OPEN] == ["bylaws#5.1"]
    assert s.counts["ownedBySchedule"] == 1 and s.counts["others"] == 1
    assert s.items[0].command == "jason duties --documents bylaws --timed --untracked"


# --- The digest -------------------------------------------------------------------------------------------------------

def test_a_broken_store_is_one_unavailable_section_and_the_rest_stands(tmp_path):
    (tmp_path / "intake").mkdir()
    (tmp_path / "intake" / "asks.json").write_text("{not json", encoding="utf-8")
    broken = SimpleNamespace(conflicts=lambda: 1 / 0)
    found = attention.digest(broken, tmp_path, on=ON)
    by = {s.key: s for s in found.sections}
    assert not by["intake"].available and "JSONDecodeError" in by["intake"].error
    assert not by["conflicts"].available and "ZeroDivisionError" in by["conflicts"].error
    assert by["notices"].available and by["living"].available
    out = found.as_dict()
    assert sorted(out["unavailable"]) == ["conflicts", "intake"]
    assert [s["key"] for s in out["sections"]][-2:] in (["intake", "conflicts"], ["conflicts", "intake"])
    assert any(line.startswith("Unavailable:") for line in found.lines())


def test_sections_are_ordered_by_their_most_urgent_line_and_capped(tmp_path):
    rows = tuple(_conflict(f"c{n}", ConflictStatus.COUNSEL) for n in range(5))
    c = SimpleNamespace(conflicts=lambda: rows, assignments=lambda: (_monthly(),))
    found = attention.digest(c, tmp_path, on=ON, limit=2, sections=("conflicts", "schedule"))
    assert [s.key for s in found.ordered()] == ["schedule", "conflicts"]       # a legal clock before open conflicts
    out = found.as_dict()
    conflicts = next(s for s in out["sections"] if s["key"] == "conflicts")
    assert len(conflicts["items"]) == 2 and conflicts["more"] == 3 and conflicts["total"] == 5
    lines = found.lines()
    assert lines[0].startswith("As of 2026-10-02: 1 on a legal clock")
    assert "- ... 3 more: `jason conflicts`" in lines
    assert all("(`jason" in line for line in lines if line.startswith("- **"))  # every line names its command


def test_an_unknown_section_is_refused(tmp_path):
    try:
        attention.digest(EMPTY, tmp_path, sections=("nope",))
    except ValueError as exc:
        assert "schedule" in str(exc)
    else:
        raise AssertionError("an unknown section must be refused")


def test_the_tool_the_api_and_the_packet_report(tmp_path):
    out = api.governance_digest(data_dir=tmp_path)
    assert {s["key"] for s in out["sections"]} == set(attention.SECTIONS) and "caveat" in out
    assert "error" in api.governance_digest(section="nope", data_dir=tmp_path)
    assert [s["key"] for s in api.governance_digest(section="intake", data_dir=tmp_path)["sections"]] == ["intake"]

    from jason.tasks.live_reports import REPORTS

    report = REPORTS["attention"]
    assert report.offline
    rows = report.run(tmp_path, EMPTY, {"section": "conflicts"}, {})
    assert any(r.startswith("### Provisions that yield") for r in rows)


def test_the_command_is_registered():
    from jason.commands import MODULES
    from jason.commands import attention as command

    assert "attention" in MODULES
    parser = argparse.ArgumentParser()
    command.register(parser.add_subparsers(), lambda p: p.add_argument("--env"), lambda a: None)
    args = parser.parse_args(["attention", "--section", "notices", "--json"])
    assert args.section == ["notices"] and args.json and args.func is command.cmd_attention
