"""A notice's evidence and a notice as a record, from made-up ledgers: a general notice posted (delivered), an
individual notice with a bounce owed a resend, a send whose outcomes are not synced, and a file with no send. The
shared reader (``notice_evidence``), the clocks that read it (the meeting watch, record stages, the evidence finder),
and ``jason://notice/KEY`` through the Shelf, ``jason cite``, the MCP resources, and the HTML reader."""

import json
from datetime import date
from types import SimpleNamespace

import pytest

from jason import batches
from jason.community.books import Book, Shape
from jason.community.cite import Target, Unit, of_address
from jason.community.notices import NoticeStrength
from jason.community.record_stages import RuleChangeRecord, Standing, Strength
from jason.tasks import attention
from jason.tasks import meeting_watch as mw
from jason.tasks import notice_evidence as ne
from jason.tasks import notice_record as nr
from jason.tasks import record_stages as rs
from jason.tasks.attention import Urgency
from jason.tasks.notice_ledger import Attempt, Delivery, save, set_general
from jason.tasks.schedule_evidence import Stores, notice_on_record

GENERAL = "board-meeting-2099-01-14"          # a general notice, posted: delivered
INDIVIDUAL = "annual-budget-report-2099"      # an individual notice: a bounce owed a resend
UNSYNCED = "assessment-increase-2099"         # letters with no outcome yet: sent
ON = date(2099, 2, 20)


def _a(notice, member, unit, channel, status, sent="2099-01-08T18:00:00Z", reason=""):
    return Attempt(notice, member, member, unit, channel, f"{notice}-{channel}", f"{notice}-{member}-{channel}", sent,
                   status, sent, reason)


def _community(rows=()):
    return SimpleNamespace(notice_provisions=lambda: (), hearing_policy=lambda: None, living_documents=lambda: (),
                           citable_documents=lambda: (), rule_change_records=lambda: rows, rule_changes=lambda: ())


@pytest.fixture
def data(tmp_path):
    save(tmp_path, [
        _a(GENERAL, 1, "UNIT 1", "email", Delivery.DELIVERED),
        _a(GENERAL, 2, "UNIT 2", "email", Delivery.BOUNCED, reason="550 no such user"),
        _a(GENERAL, 3, "UNIT 3", "email", Delivery.SKIPPED),
        _a(INDIVIDUAL, 1, "UNIT 1", "email", Delivery.OPENED, "2098-11-20T18:00:00Z"),
        _a(INDIVIDUAL, 2, "UNIT 2", "email", Delivery.BOUNCED, "2098-11-20T18:00:00Z", "550 no such user"),
        _a(UNSYNCED, 1, "UNIT 1", "letter", Delivery.PENDING, "2098-12-01T18:00:00Z"),
        _a(UNSYNCED, 2, "UNIT 2", "letter", Delivery.PENDING, "2098-12-01T18:00:00Z"),
    ])
    set_general(tmp_path, GENERAL, True, posted="the posting board, 2099-01-09", by="A Secretary")
    (tmp_path / "meetings").mkdir()
    (tmp_path / "meetings" / "catalog.json").write_text(json.dumps({"builtAt": "2099-02-15T00:00:00+00:00",
                                                                    "meetings": [
        {"date": "2099-01-14", "titles": [], "has": {"meeting notice": {"PayHOA communication": 1}}, "records": [
            {"kind": "meeting notice", "where": "PayHOA communication", "name": "Board meeting January 14",
             "sent": "2099-01-08T18:00:00Z", "ref": "", "note": ""}]},
        # February: only the notice's file on Drive, written before the meeting, and no send on record.
        {"date": "2099-02-11", "titles": [], "has": {"meeting notice": {"Drive": 1}}, "records": [
            {"kind": "meeting notice", "where": "Drive", "name": "Notice of the February meeting", "ref": "febnotice",
             "sent": "", "note": ""}]},
    ]}), encoding="utf-8")
    (tmp_path / "drive").mkdir()
    (tmp_path / "drive" / "files.json").write_text(json.dumps({"files": [
        {"id": "febnotice", "name": "Notice of the February meeting", "created": "2099-02-01T18:00:00Z",
         "modified": "2099-02-02T18:00:00Z"}]}), encoding="utf-8")
    folder = tmp_path / "notices" / GENERAL
    folder.mkdir(parents=True)
    (folder / "notice.md").write_text("Notice of the board meeting of January 14, 2099, at the example hall.\n",
                                      encoding="utf-8")
    (folder / "notice.md.refs.json").write_text(json.dumps({"source": "notice.src.md", "rendered": "2099-01-07",
                                                            "references": [{
        "token": "{QUOTE:bylaws#3.1}", "verb": "quote", "key": "bylaws", "section": "3.1", "as_of": "",
        "citation": "Bylaws Section 3.1", "set_by": "base", "set_by_title": "the Bylaws", "dated": "",
        "digest": "0123456789abcdef", "note": ""}]}), encoding="utf-8")
    (folder / "recipients.json").write_text(json.dumps({"notice": "board-meeting", "unitTag": "",
                                                        "emailMembershipIds": [1, 2, 3], "mail": [],
                                                        "secondary": []}), encoding="utf-8")
    batches.create(tmp_path, f"{INDIVIDUAL}-mail", "example-mail", "Budget report letters",
                   [("u2", "UNIT 2", {"unitIds": [2], "ownerIds": [2]})], confirmed_by="A Treasurer",
                   params={"subject": "The annual budget report", "pdf": str(tmp_path / "packets" / "budget.pdf"),
                           "pages": 4})
    return tmp_path


# ---------------------------------------------------------------------------------------------------------------
# The shared reader.


def test_the_four_strengths_from_made_up_ledgers(data):
    found = ne.ledger(data)
    general, individual, unsynced = found[GENERAL], found[INDIVIDUAL], found[UNSYNCED]
    # A general notice posted where the policy statement designates: delivered on the posting's day (4045(a)); the
    # bounce still asks for a working email, and no resend is owed (nobody asked for individual delivery, 4045(b)).
    assert general.strength is NoticeStrength.DELIVERED and general.on == date(2099, 1, 9)
    assert general.owed == 0 and general.asks == 1 and "posted (the posting board, 2099-01-09)" in general.describe()
    # An individual notice whose email bounced: sent, with the resend owed under 4041(e) listed.
    assert individual.strength is NoticeStrength.FOLLOW_UPS and individual.owed == 1
    assert individual.follow_ups == (("email-bounced", "required", "CIV 4041(e), 4040(a)(2)", 1),)
    assert "4041(e)" in individual.describe() and individual.address == f"jason://notice/{INDIVIDUAL}"
    # Letters with no outcome yet: sent, not synced.
    assert unsynced.strength is NoticeStrength.SENT and unsynced.unsynced == 2 and "--sync" in unsynced.describe()
    assert all("UNIT" not in json.dumps(r.row()) for r in found.values())           # counts only


def test_a_resend_with_no_outcome_yet_is_unsynced_not_owed():
    rows = [_a(INDIVIDUAL, 2, "UNIT 2", "email", Delivery.BOUNCED), _a(INDIVIDUAL, 2, "UNIT 2", "letter",
                                                                      Delivery.PENDING, "2098-11-25T18:00:00Z")]
    rec = ne.weigh(INDIVIDUAL, rows)
    assert rec.strength is NoticeStrength.SENT and rec.owed == 0 and rec.unsynced == 1
    assert ne.weigh(INDIVIDUAL, []) is None


def test_a_file_never_meets_a_clock_and_a_send_does_on_time(data):
    stores = Stores(data, _community())
    february = ne.meeting_notices(stores, date(2099, 2, 11))
    assert [(r.strength, r.on) for r in february] == [(NoticeStrength.FILE, date(2099, 2, 1))]
    verdict, r = ne.judge(february, date(2099, 2, 7), ON)
    assert verdict is ne.Verdict.FILE and r.source == "drive:febnotice"
    assert notice_on_record(stores, date(2099, 2, 11)) is None        # the compat reader takes only what counts
    january = ne.meeting_notices(stores, date(2099, 1, 14))
    verdict, r = ne.judge(january, date(2099, 1, 10), ON)
    # the ledger's delivery beats the catalog's send on the same clock
    assert verdict is ne.Verdict.MET and r.key == GENERAL and r.strength is NoticeStrength.DELIVERED
    assert ne.judge([], date(2099, 3, 7), ON)[0] is ne.Verdict.OPEN
    assert ne.judge([], date(2099, 2, 7), ON)[0] is ne.Verdict.PASSED
    late = ne.NoticeRecord("late send", date(2099, 2, 9), NoticeStrength.SENT)
    assert ne.judge([late], date(2099, 2, 7), ON)[0] is ne.Verdict.LATE


def test_the_ledger_is_read_only_and_a_missing_one_is_empty(data, tmp_path_factory):
    db = data / "notices" / "deliveries.db"
    before = db.stat().st_mtime_ns
    ne.ledger(data)
    assert db.stat().st_mtime_ns == before
    empty = tmp_path_factory.mktemp("empty")
    assert ne.ledger(empty) == {} and not (empty / "notices").exists()


def test_a_posting_recorded_with_no_messages_is_a_delivery(data):
    set_general(data, "board-meeting-2099-03-11", True, posted="the posting board, 2099-03-05", by="A Secretary")
    rec = ne.ledger(data)["board-meeting-2099-03-11"]
    assert rec.strength is NoticeStrength.DELIVERED and rec.on == date(2099, 3, 5) and rec.members == 0
    assert ne.recent(data)[0] == ("board-meeting-2099-03-11", "2099-03-05")


# ---------------------------------------------------------------------------------------------------------------
# The readers that use it.


def test_the_meeting_watch_names_the_notice_and_a_file_only_clock(data):
    w = mw.watch(_community(), data, on=ON)
    by = {m.day: m for m in w.meetings}
    jan = next(c for c in by[date(2099, 1, 14)].clocks if c.what == "notice")
    assert jan.standing is mw.Standing.MET and jan.strength == "delivered"
    assert jan.notice == f"jason://notice/{GENERAL}" and f"[jason://notice/{GENERAL}]" in "\n".join(w.lines())
    feb = next(c for c in by[date(2099, 2, 11)].clocks if c.what == "notice")
    assert feb.standing is mw.Standing.FILE_ONLY and feb.strength == "file" and not feb.done
    items = attention.meetings_section(_community(), data, ON).items
    filed = next(i for i in items if "2099-02-11" in i.text and "notice" in i.text)
    assert filed.urgency is Urgency.LEGAL and "met only by a file" in filed.text and "--sync" in filed.text
    # near its deadline, not yet past: due soon
    soon = attention.meetings_section(_community(), data, date(2099, 2, 3)).items
    assert any(i.urgency is Urgency.SOON and "met only by a file" in i.text for i in soon)


def test_a_rule_change_clock_reads_the_ledger_and_names_the_notice(tmp_path):
    save(tmp_path, [
        _a("rule-change-proposed-example-2099", 1, "UNIT 1", "email", Delivery.DELIVERED, "2099-01-02T18:00:00Z"),
        _a("rule-change-adopted-example-2099", 1, "UNIT 1", "email", Delivery.DELIVERED, "2099-02-14T18:00:00Z"),
        _a("rule-change-adopted-example-2099", 2, "UNIT 2", "email", Delivery.BOUNCED, "2099-02-14T18:00:00Z"),
    ])
    set_general(tmp_path, "rule-change-proposed-example-2099", True, posted="the posting board, 2099-01-03",
                by="A Secretary")
    record = RuleChangeRecord("example-2099", "Example rule", "example-rules", "Example Rules",
                              decided=date(2099, 2, 11))
    (h,) = rs.rule_change_histories(_community((record,)), tmp_path, on=ON)
    proposed, adopted = h.clocks
    assert proposed.standing is Standing.MET and proposed.evidence.strength is Strength.DELIVERED
    assert proposed.notice == "jason://notice/rule-change-proposed-example-2099"
    # sent on time with a bounce owed a resend: met, with the follow-up listed
    assert adopted.standing is Standing.MET and adopted.evidence.strength is Strength.FOLLOW_UPS
    assert "email-bounced" in adopted.note and adopted.notice.endswith("rule-change-adopted-example-2099")
    assert h.notices() == {"proposed": ["jason://notice/rule-change-proposed-example-2099"],
                           "distributed": ["jason://notice/rule-change-adopted-example-2099"]}
    assert h.row()["notices"] == h.notices() and any("notice of the proposed stage" in x for x in h.lines())
    # the notice links back to its stage
    r = nr.build("rule-change-proposed-example-2099", community=_community((record,)), data_dir=tmp_path, today=ON)
    assert r["stage"]["ruleChange"] == "example-2099" and r["stage"]["stage"] == "proposed"
    assert r["stage"]["clock"]["standing"] == Standing.MET.value
    assert r["stage"]["version"] == "example-rules@proposed-2099-01-03"


# ---------------------------------------------------------------------------------------------------------------
# A notice as a record.


def test_the_notice_book_and_its_address():
    assert Book.NOTICE.info.shape is Shape.SERIES and not Book.NOTICE.restricted
    t = of_address("jason://notice/board-meeting-2099-01-14/proof", set())
    assert t == Target(Unit.NOTICE, "board-meeting-2099-01-14", "proof")
    assert t.id == "notice:board-meeting-2099-01-14/proof"


def test_a_notice_resolves_through_the_shelf_with_counts_only(data):
    from jason.tasks.cite import Shelf, markdown, resolve

    shelf = Shelf(_community(), data)
    c = shelf(f"jason://notice/{GENERAL}")
    assert c.found and c.address == f"jason://notice/{GENERAL}" and str(c) == f"notice {GENERAL}"
    assert c.text.startswith("Notice of the board meeting of January 14, 2099")         # the text as sent
    r = c.state.extra["notice"]
    assert r["requirement"]["key"] == "board-meeting" and r["requirement"]["statute"] == "CIV 4920"
    assert r["text"]["fills"][0]["digest"] == "0123456789abcdef"
    assert r["recipients"]["plan"]["emails"] == 3
    assert r["standing"]["strength"] == "delivered" and r["standing"]["members"] == 3
    assert r["stage"]["meeting"] == "2099-01-14" and r["stage"]["agenda"] == "jason://agenda/2099-01-14"
    assert r["proof"]["event"] == "2099-01-14" and r["proof"]["onTime"] is True
    shared = json.dumps(resolve(f"jason://notice/{GENERAL}", shelf=shelf))
    assert "UNIT" not in shared and "Counts only" in markdown(c)
    proof = shelf(f"jason://notice/{GENERAL}/proof")
    assert proof.found and proof.state.extra["proof"]["requirement"] == "board-meeting"
    assert shelf.notice(GENERAL, proof=True).address == f"jason://notice/{GENERAL}/proof"
    assert shelf("notice:annual-budget-report-2099").found
    budget = shelf(f"jason://notice/{INDIVIDUAL}").state.extra["notice"]
    assert budget["text"]["files"][0]["pages"] == 4 and budget["recipients"]["batches"][0]["owners"] == 1
    assert budget["proof"]["items"] and "UNIT" not in json.dumps(budget)
    book = shelf("jason://notice")
    assert book.found and {n["address"] for n in book.state.nodes} >= {f"jason://notice/{GENERAL}"}
    miss = shelf("jason://notice/no-such-notice")
    assert not miss.found and miss.reason.value == "unknown_record"
    private = Shelf(_community(), data, private=True)(f"jason://notice/{INDIVIDUAL}").state.extra["notice"]
    assert any(m["unit"] == "UNIT 2" for m in private["standing"]["memberRows"])


def test_a_key_that_names_no_requirement_says_so_and_a_form_key_finds_its_row():
    assert nr.requirement_for("owner-info-2099")[0].key == "owner-info-solicitation"
    assert nr.requirement_for("board-meeting-2099-01-14")[0].key == "board-meeting"
    assert nr.requirement_for("meeting-2099-01-14") == (None, "")


def test_the_resources_list_the_recent_notices_and_read_one(data):
    from jason.mcp import resources

    for n in range(22):
        save(data, [_a(f"example-notice-{n:02}", 1, "UNIT 1", "email", Delivery.DELIVERED,
                       f"2099-01-{n + 1:02}T18:00:00Z")])
    rows = [r for r in resources.listing(community=_community(), data_dir=data) if "/notice/" in r["uri"]]
    assert len(rows) == resources.NOTICES == 20
    assert rows[0]["uri"] == f"jason://notice/{GENERAL}" or rows[0]["lastModified"] >= rows[-1]["lastModified"]
    page = resources.read(f"jason://notice/{GENERAL}", community=_community(), data_dir=data)
    assert "## Delivery" in page.text and "## Proof of notice" in page.text and "UNIT" not in page.text
    assert {t.name for t in resources.TEMPLATES} >= {"notice", "notice_proof"}


def test_the_reader_writes_each_notice_and_its_proof(data, tmp_path_factory):
    from jason.tasks.cite import Shelf
    from jason.tasks.reader import write

    out = tmp_path_factory.mktemp("reader")
    write(Shelf(_community(), data), out)
    page = out / "notice" / f"{GENERAL}.html"
    assert page.is_file() and (out / "notice" / GENERAL / "proof.html").is_file()
    text = page.read_text(encoding="utf-8")
    assert "Proof of notice" in text and "UNIT" not in text and "<blockquote>" in text
